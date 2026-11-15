"""Baseline tables: every shipped preset by month, the fidelity check against the real trades and the
forward price path after entries.

usage: python -I baseline.py <results_dir> [spread_pts]
writes baseline_by_month.csv, baseline_summary.csv, fidelity_exit_mix.csv, fidelity_routes.csv,
forward_drift.csv and trades_reference_preset.csv
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import oat
import params
import sim
import sweep
import ticks


def by_month(df, **tags):
    if len(df) == 0:
        r = sim.metrics(df)
        r.update(month="ALL", **tags)
        return [r]
    L = sim.label(df)
    L["month"] = L.entry_time.dt.to_period("M").astype(str)
    rows = []
    for m, g in L.groupby("month"):
        r = sim.metrics(g)
        r.update(month=m, **tags)
        rows.append(r)
    r = sim.metrics(L)
    r.update(month="ALL", **tags)
    rows.append(r)
    return rows


def main():
    res = sys.argv[1]
    spread = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    print(feed.describe(), flush=True)
    months, summary = [], []
    presets = [os.path.basename(f).replace("_DISABLED.set", "") for f in sorted(glob.glob("../shipped_presets/*.set"))]
    cases = [(name, "real fills", sweep.REAL_FILLS, {}) for name in presets]
    cases += [(name, "real fills, micro capacity block as shipped", sweep.REAL_FILLS, {"X_MicroRestart": 0}) for name in presets if "Native" not in name]
    cases += [("FlashGold_NativeReference", "tester fills (no order delay)", sweep.TESTER_FILLS, {}),
              ("FlashGold_NativeReference", "strict fills", sweep.STRICT_FILLS, {}),
              ("FlashGold_NativeReference", "real fills, FlashGold filter off", sweep.REAL_FILLS, {"UseFlashGoldDirectionFilter": 0})]
    ref = None
    for name, label, fills, over in cases:
        p = sweep.base(name, fills=fills, **over)
        df, cnt = S.run(p, True)
        months += by_month(df, preset=name, case=label)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m.update(preset=name, case=label, **cnt)
        summary.append(m)
        print(f"{name:32s} {label:44s} n {m['n']:6d} pf {m['pf']:.3f} avg {m['avg']:+.1f}", flush=True)
        if name == "FlashGold_NativeReference" and label == "real fills":
            ref = df
    p = params.defaults()
    p.update(sweep.REAL_FILLS)
    df = S.run(p)
    months += by_month(df, preset="source code defaults", case="real fills")
    m = sim.metrics(df)
    m.update(oat.split_row(df))
    m.update(preset="source code defaults", case="real fills")
    summary.append(m)
    pd.DataFrame(months).to_csv(os.path.join(res, "baseline_by_month.csv"), index=False)
    pd.DataFrame(summary).to_csv(os.path.join(res, "baseline_summary.csv"), index=False)

    # ---- reference preset trades, fidelity against the real account
    L = sim.label(ref)
    L.drop(columns=["entry_ms", "exit_ms", "decision_ms"]).round(3).to_csv(os.path.join(res, "trades_reference_preset.csv"), index=False)
    real = pd.read_csv(os.path.join(res, "real", "real_trades_sar.csv"))
    kinds = {"SL": "stop loss", "SA_PROFIT_EXIT": "speed profit exit", "TP": "take profit"}

    def mix(kind_series):
        k = kind_series.map(lambda x: kinds.get(x, "defensive close" if str(x).startswith("SA_") or "HOLD" in str(x) else "other"))
        return (k.value_counts(normalize=True) * 100)

    rr = real[real.scenario.isin(["FLXQ", "EXHL"])]
    a = mix(rr.exit_kind)
    b = mix(L.exit_reason.map(lambda x: "SA_PROFIT_EXIT" if x.startswith("SA_PROFIT") else x))
    order = ["stop loss", "speed profit exit", "defensive close", "take profit", "other"]
    fid = pd.DataFrame({"kind": order, "real": [a.get(k, 0.0) for k in order], "replay": [b.get(k, 0.0) for k in order]})
    fid["note"] = (f"Stop and limit routes only (the replay has no order-flow feed): {len(rr)} real trades, Sep 7 - Oct 8 2026, "
                   f"against {len(L):,} replayed trades over eight months")
    fid.to_csv(os.path.join(res, "fidelity_exit_mix.csv"), index=False)

    def st(g, col):
        pts = g[col]
        w, l = pts[pts > 0].sum(), -pts[pts < 0].sum()
        return dict(n=len(g), pf=w / l if l > 0 else np.inf, win=(pts > 0).mean(), avg=pts.mean(),
                    avg_win=pts[pts > 0].mean(), avg_loss=pts[pts < 0].mean())

    rows = []
    for route in ("FLXQ:BS", "FLXQ:SS", "EXHL:BL", "EXHL:SL"):
        scn, act = route.split(":")
        rows.append(dict(route=route, source="real", **st(real[(real.scenario == scn) & (real.action == act)], "pts")))
        rows.append(dict(route=route, source="replay", **st(L[L.route == route], "pts")))
    pd.DataFrame(rows).to_csv(os.path.join(res, "fidelity_routes.csv"), index=False)

    # ---- forward path after the fill
    T, M, B, A = feed.t, feed.mid, feed.bid, feed.ask
    ms = ref.entry_ms.to_numpy().astype(np.int64)
    i0 = np.searchsorted(T, ms)
    side = ref.side.to_numpy()
    flxq = (ref.scenario == engine.S_FLXQ).to_numpy()
    exhl = (ref.scenario == engine.S_EXHL).to_numpy()
    cost = -float(ref.pts[flxq].mean())
    rows = []
    for h in (1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1800):
        j = np.minimum(np.searchsorted(T, ms + h * 1000, side="right") - 1, len(T) - 1)
        mid = side * (M[j] - M[i0]) / 0.01
        exe = np.where(side > 0, B[j], A[j])
        net = side * (exe - ref.entry.to_numpy()) / 0.01
        rows.append(dict(h_s=h, mid_drift_FLXQ=mid[flxq].mean(), mid_drift_EXHL=mid[exhl].mean(), net_if_closed_FLXQ=net[flxq].mean(),
                         net_if_closed_EXHL=net[exhl].mean(), n_FLXQ=int(flxq.sum()), n_EXHL=int(exhl.sum())))
    d = pd.DataFrame(rows)
    spread_paid = float(ref.spread_pts[flxq].mean())
    slip_entry = float((ref.side * (ref.entry - ref.requested) / 0.01)[flxq].mean())
    d["cost"] = spread_paid + slip_entry + float(-(ref.pts[flxq & (ref.reason == engine.R_SL).to_numpy()].mean() + 90.0 + slip_entry)) * float((ref.reason[flxq] == engine.R_SL).mean())
    d["spread_paid"] = spread_paid
    d["entry_slip"] = slip_entry
    d.to_csv(os.path.join(res, "forward_drift.csv"), index=False)
    print(d.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
