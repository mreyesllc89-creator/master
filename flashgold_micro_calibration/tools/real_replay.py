"""Replay the REAL entries (from the saved chart) on the tick feed with any exit inputs.

usage: python -I real_replay.py <real_trades.csv> <variants.json> <out_prefix> [server_utc_offset_hours=3] [spread_pts=12]

For every real trade a position is opened at the real entry price at the real entry second; the
EA's own entries are switched off, its position management runs unchanged. The first variant should
be the configuration the trades were made with: its simulated exits are compared with the real ones
(this measures how far the tick feed and the port can be trusted), the other variants answer "what
would these same entries have made with other exit inputs".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import sim
import sweep
import ticks

SCN = {v: k for k, v in engine.SCENARIO.items()}
ACT = {v: k for k, v in engine.ACTION.items()}
NOM_SL = {"BM": 80, "SM": 80, "BS": 90, "SS": 90, "BL": 90, "SL": 90}
NOM_TP = {"BM": 160, "SM": 160, "BS": 180, "SS": 180, "BL": 160, "SL": 160}


def load_real(path, offset_h):
    d = pd.read_csv(path, parse_dates=["open_time", "close_time"])
    d["ms"] = d.open_time.astype("datetime64[ms]").astype("int64") - int(offset_h * 3600 * 1000)
    d["close_ms"] = d.close_time.astype("datetime64[ms]").astype("int64") - int(offset_h * 3600 * 1000)
    d = d[d.scenario.isin(SCN) & d.action.isin(ACT)].reset_index(drop=True)
    d["id"] = np.arange(len(d))
    return d


def externals(d, feed, sl_points=None, tp_points=None):
    """Fills to inject. Stop and target sit at the EA's nominal distance from the real entry price,
    except where the chart shows the real level (trades that ended at their stop or target)."""
    slp = d.action.map(NOM_SL).to_numpy(float) if sl_points is None else np.full(len(d), float(sl_points))
    tpp = d.action.map(NOM_TP).to_numpy(float) if tp_points is None else np.full(len(d), float(tp_points))
    sl = d.entry - d.side * slp * 0.01
    tp = d.entry + d.side * tpp * 0.01
    if sl_points is None:
        known = (d.exit_kind == "SL") & d.exit_level.notna()
        sl = np.where(known, d.exit_level, sl)
    if tp_points is None:
        known = (d.exit_kind == "TP") & d.exit_level.notna()
        tp = np.where(known, d.exit_level, tp)
    return pd.DataFrame(dict(ms=d.ms.to_numpy(), side=d.side.to_numpy(), action=d.action.map(ACT).to_numpy(),
                             scenario=d.scenario.map(SCN).to_numpy(), entry=d.entry.to_numpy(), sl=np.round(sl, 2),
                             tp=np.round(tp, 2), id=d.id.to_numpy()))


def covered(d, feed, lead_ms=60000, tail_ms=5000):
    """Real trades that lie inside one stretch of tick data: a quote within 3 s of the entry, a minute
    of quotes before it (the speed alert needs history) and quotes until after the real close."""
    ms = d.ms.to_numpy()
    i = np.searchsorted(feed.t, ms)
    i = np.minimum(i, len(feed.t) - 1)
    near = np.abs(feed.t[i] - ms) < 3000
    lo = np.full(len(d), np.iinfo(np.int64).max)
    hi = np.full(len(d), np.iinfo(np.int64).min)
    for a, b in feed.chunks:
        inside = (i >= a) & (i < b)
        lo[inside] = feed.t[a]
        hi[inside] = feed.t[b - 1]
    near &= (ms - lo >= lead_ms) & (d.close_ms.to_numpy() + tail_ms <= hi)
    px = np.where(d.side > 0, feed.ask[i], feed.bid[i])
    return near, (d.entry.to_numpy() - px) * d.side.to_numpy() / 0.01


def stats(pts):
    pts = np.asarray(pts, float)
    w, l = pts[pts > 0].sum(), -pts[pts < 0].sum()
    return dict(n=len(pts), net=pts.sum(), pf=w / l if l > 0 else np.inf, win=(pts > 0).mean(), avg=pts.mean())


def main():
    real_path, spec_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    offset = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
    spread = float(sys.argv[5]) if len(sys.argv) > 5 else 12.0
    spec = json.load(open(spec_path))
    feed = ticks.Feed(spec.get("data_dir", "../data"), spread, months=spec.get("months"),
                      gap_ms=int(float(spec.get("gap_minutes", 360)) * 60000))
    S = sim.Sim(feed)
    d = load_real(real_path, offset)
    near, gap = covered(d, feed)
    d = d[near].reset_index(drop=True)
    d["id"] = np.arange(len(d))
    print(f"{len(d)} real trades inside the tick data ({d.open_time.min()} .. {d.open_time.max()} server time), "
          f"{d.open_time.dt.date.nunique()} days, {len(feed.chunks)} stretches of ticks")
    print("real entry vs feed quote at that second, points (trade side +): median %.1f, p10 %.1f, p90 %.1f"
          % (np.median(gap[near]), np.percentile(gap[near], 10), np.percentile(gap[near], 90)))
    rows = []
    for k, item in enumerate(spec["variants"]):
        p = sweep.base(item.get("preset", "FlashGold_NativeReference"))
        p.update(item["set"])
        p["X_TradeBuys"] = 0
        p["X_TradeSells"] = 0
        ext = externals(d, feed, item.get("sl_points"), item.get("tp_points"))
        df = S.run(p, external=ext)
        m = d.merge(df, left_on="id", right_on="decision_ms", suffixes=("", "_sim"))
        r = dict(name=item["name"], **{"sim_" + a: b for a, b in stats(m.pts_sim).items()})
        r.update({"real_" + a: b for a, b in stats(m.pts).items()})
        for scn, g in m.groupby("scenario"):
            r[f"sim_pf_{scn}"] = stats(g.pts_sim)["pf"]
        rows.append(r)
        print(f"{item['name'][:60]:60s} sim: n {r['sim_n']} pf {r['sim_pf']:.3f} avg {r['sim_avg']:.1f} | real: pf {r['real_pf']:.3f} avg {r['real_avg']:.1f}", flush=True)
        if k == 0:
            m["sim_kind"] = m.reason.map(engine.REASON)
            m.to_csv(out + "_baseline_trades.csv", index=False)
            agree = dict(trades=int(len(m)), days=int(d.open_time.dt.date.nunique()), stretches=int(len(feed.chunks)),
                         corr=float(np.corrcoef(m.pts, m.pts_sim)[0, 1]), same_sign=float((np.sign(m.pts) == np.sign(m.pts_sim)).mean()),
                         within_15=float(((m.pts - m.pts_sim).abs() <= 15).mean()),
                         real_stop_exits=int((m.exit_kind == "SL").sum()),
                         both_stop_exits=int(((m.exit_kind == "SL") & (m.sim_kind == "SL")).sum()))
            json.dump(agree, open(out + "_agreement.json", "w"), indent=1)
            print("  per-trade agreement with the real outcome: points correlation %.3f, same sign %.3f, |difference| <= 15 points %.3f"
                  % (agree["corr"], agree["same_sign"], agree["within_15"]))
            print(pd.crosstab(m.exit_kind, m.sim_kind).to_string())
        pd.DataFrame(rows).to_csv(out + "_variants.csv", index=False)


if __name__ == "__main__":
    main()
