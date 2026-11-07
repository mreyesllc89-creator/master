#!/usr/bin/env python3
"""
Pick presets for any instrument the way the gold M2/H1 preset was picked, then stress-test them.

  XLZC_SYMBOL=BTCUSD python3 select_and_verify.py <data_dir> <calibration_grid.csv[.gz]> <out.json> [pairs...]

Selection uses 2025 data ONLY (2025-H1 and 2025-H2): among setups with >= 30 trades in each
half-year, take the one with the best median worst-half PF over itself and its grid
neighbours. 2026 is never used, so its figures are out of sample.
If no pairs are given, the two best pair families on 2025 are used.
"""
import json
import sys

import numpy as np
import pandas as pd

import fgf_backtest as FB
import xlzc_backtest as B
import xlzc_calibrate as C

KEYS = ["N", "S", "buffer", "NT", "min_rr", "fb", "stoch", "session", "trail"]
VALS = {"N": [15, 25, 40], "S": [2, 3, 4], "buffer": [40, 80, 120], "NT": [0, 60, 120], "min_rr": [1.0, 1.5, 2.0]}


def family_rank(d):
    fam = d[(d.session == "ny_12-1630") & d.trail & (d.NT == 120) & (d.fb == 0) & (d.stoch == "soft")]
    rows = []
    for tf, g in fam.groupby("tf"):
        rows.append(dict(tf=tf, median_min25=float(g.min25.median()), share_both_halves_gt1=float((g.min25 > 1).mean()),
                         median_2026=float(g["2026_pf"].median()), share_2026_gt1=float((g["2026_pf"] > 1).mean())))
    return sorted(rows, key=lambda r: (-r["median_min25"], -r["share_both_halves_gt1"]))


def select(d, pair, min_trades=30):
    g = d[d.tf == pair].copy()
    idx = g.set_index(KEYS)
    cand = g[(g.t25 >= min_trades) & (g.min25 > 1.0)].copy()
    if cand.empty:
        return None
    sm, share = [], []
    for _, r in cand.iterrows():
        v = [r.min25]
        for k, vs in VALS.items():
            i = vs.index(r[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vs):
                    rr = dict(r[KEYS]); rr[k] = vs[j]
                    try:
                        v.append(idx.loc[tuple(rr[x] for x in KEYS)].min25)
                    except KeyError:
                        pass
        v = np.array(v, float)
        sm.append(float(np.median(v))); share.append(float((v > 1).mean()))
    cand["smooth25"] = sm; cand["nb_share"] = share
    best = cand.sort_values(["smooth25", "t25"], ascending=False).iloc[0]
    return best


def verify(data_dir, cfg):
    p = FB.prepare(data_dir, [cfg["tf"]])
    FB.init_worker(p)
    out = {}

    def run(label, c=cfg, mask=None):
        tr = FB.run_with_mask(c, mask)
        s = {k: (None if not np.isfinite(v) else round(float(v), 4)) for k, v in C.seg_stats(tr).items()}
        r = np.array([x[1] for x in tr])
        s["win"] = round(float((r > 0).mean()), 3) if len(r) else None
        out[label] = s
        print(f"  {label:30s} {s['all_trades']:.0f} tr PF {s['all_pf']} net {s['all_net_r']}R dd {s['all_maxdd_r']}R | "
              f"{s['2025H1_pf']} / {s['2025H2_pf']} / {s['2026_pf']} ({s['2026_trades']:.0f} tr 2026)", flush=True)
        return tr
    tr = run("chosen")
    for mode in ("next", "worst"):
        B.M1Path.TRAIL_MODE = mode; C.G["cache"] = {}
        run("trailing same-bar: " + mode)
    B.M1Path.TRAIL_MODE = "close"; C.G["cache"] = {}
    run("trailing off", dict(cfg, trail=False))
    run("session ldn_ny_07-20", dict(cfg, session="ldn_ny_07-20"))
    run("session all_day", dict(cfg, session="all_day"))
    months = {}
    for t, r in tr:
        k = str(t)[:7]; months[k] = round(months.get(k, 0) + r, 2)
    out["monthly"] = months
    # spread stress: same trades, bigger spread
    base_hs = C.G["path"].hs.copy()
    for mult in (1.25, 1.5):
        C.G["path"].hs = base_hs * mult; C.G["cache"] = {}
        run(f"spread x{mult}")
    C.G["path"].hs = base_hs; C.G["cache"] = {}
    return out


def main():
    data_dir, grid, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    d = pd.read_csv(grid)
    d["min25"] = d[["2025H1_pf", "2025H2_pf"]].min(axis=1)
    d["t25"] = d[["2025H1_trades", "2025H2_trades"]].min(axis=1)
    fams = family_rank(d)
    print(f"{B.SYMBOL}: pair families ranked on 2025 only")
    for r in fams:
        print(f"  {r['tf']:7s} 2025 median worst-half PF {r['median_min25']:.2f} (both halves >1: "
              f"{r['share_both_halves_gt1']:.0%}) -> 2026 median PF {r['median_2026']:.2f} ({r['share_2026_gt1']:.0%} >1)")
    pairs = sys.argv[4:] or [r["tf"] for r in fams[:2]]
    res = dict(symbol=B.SYMBOL, inst=B.INST, families=fams, presets=[])
    for pair in pairs:
        best = select(d, pair)
        if best is None:
            print(f"\n{pair}: no setup with >=30 trades per half-year profitable in both 2025 halves")
            res["presets"].append(dict(pair=pair, chosen=None))
            continue
        cfg = {k: (best[k].item() if hasattr(best[k], "item") else best[k]) for k in KEYS}
        cfg["tf"] = pair
        print(f"\n{pair}: chosen on 2025 -> {cfg}\n  2025 worst-half PF {best.min25:.2f}, neighbourhood median "
              f"{best.smooth25:.2f} ({best.nb_share:.0%} of neighbours >1), {best.t25:.0f}+ trades per half-year")
        res["presets"].append(dict(pair=pair, cfg=cfg, smooth25=float(best.smooth25), nb_share=float(best.nb_share),
                                   verify=verify(data_dir, cfg)))
    json.dump(res, open(out_path, "w"), indent=1, default=float)
    print("written", out_path)


if __name__ == "__main__":
    main()
