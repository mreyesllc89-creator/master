"""Trailing-stop study: the same settings with and without a trailing stop.

usage: python trailing_study.py <chart_tf_minutes> [results_dir] [n_settings] [seed]

Takes a random sample of the sweep's settings (those with enough trades in both halves),
switches the trailing stop off (the baseline) and then on with every Trail Activation x Trail
Offset pair of the grid, everything else unchanged, and backtests each version over the search
window with the orders filled on the second-by-second path. Net of 0.05 % per side, 1 tick and
funding. Also runs the 1-minute walk and the chart-candle walk of every version: how much a
coarser price path flatters the trailing stop.

Writes results/trailing_<tf>m.json.
"""
import json
import os
import sys
from multiprocessing import get_context

import numpy as np

import holdout
import space
import sweep

ACTS = space.GRID["trail_act"]
OFFS = space.GRID["trail_off"]


def _halves(r):
    nm = r["gross"].size
    M = holdout.split_masks(nm)
    net = r["gross"].astype(np.float64) - holdout.BASE_FEE * r["feeu"] - r["fund"]
    return float(net[M["h1"]].sum()), float(net[M["h2"]].sum()), int(r["n"])


def _work(job):
    k, p = job
    sig = sweep.signals_for(p)
    q = dict(p)
    q["trail"] = False
    out = dict(k=k, base=_halves(sweep.evaluate(q, signals=sig)), var={}, var_1m={}, var_chart={})
    for a in ACTS:
        for o in OFFS:
            q = dict(p)
            q["trail"], q["trail_act"], q["trail_off"] = True, a, o
            key = f"{a}|{o}"
            out["var"][key] = _halves(sweep.evaluate(q, signals=sig))
            out["var_1m"][key] = _halves(sweep.evaluate(q, signals=sig, walk="1m"))
            out["var_chart"][key] = _halves(sweep.evaluate(q, signals=sig, walk="chart"))
    return out


def run(chart_tf, res_dir, n_settings=300, seed=5, procs=4):
    d, settings = holdout.load(os.path.join(res_dir, "sweeps"), chart_tf)
    nm = d["gross"].shape[1]
    M = holdout.split_masks(nm)
    cnt = d["cnt"]
    ok = (cnt[:, M["h1"]].sum(1) >= 30) & (cnt[:, M["h2"]].sum(1) >= 30)
    idx = np.nonzero(ok)[0]
    rng = np.random.default_rng(seed)
    pick = rng.choice(idx, size=min(n_settings, idx.size), replace=False)
    ft, fund = sweep.load_context()
    sweep.precompute(ft, chart_tf)
    sweep.G.update(ft=ft, fund=fund, chart_tf=chart_tf, start_ms=sweep.ms(sweep.WINDOW_START), end_ms=sweep.ms(sweep.WINDOW_END))
    jobs = [(int(i), settings[int(i)]) for i in pick]
    with get_context("fork").Pool(procs) as pool:
        res = pool.map(_work, jobs, chunksize=4)
    base = np.array([r["base"] for r in res])            # h1, h2, n
    base_tot = base[:, 0] + base[:, 1]
    base_both = (base[:, 0] > 0) & (base[:, 1] > 0)
    good = base_tot > 0
    grid = []
    for a in ACTS:
        for o in OFFS:
            key = f"{a}|{o}"
            v = np.array([r["var"][key] for r in res])
            v1 = np.array([r["var_1m"][key] for r in res])
            vc = np.array([r["var_chart"][key] for r in res])
            tot = v[:, 0] + v[:, 1]
            dlt = tot - base_tot
            n = np.maximum(v[:, 2], 1)
            grid.append(dict(act=a, off=o,
                             share_both=float(((v[:, 0] > 0) & (v[:, 1] > 0)).mean()),
                             share_positive=float((tot > 0).mean()),
                             share_improved=float((dlt > 0).mean()),
                             median_change=float(np.median(dlt)), mean_change=float(dlt.mean()),
                             median_change_good=float(np.median(dlt[good])) if good.sum() >= 10 else None,
                             share_improved_good=float((dlt[good] > 0).mean()) if good.sum() >= 10 else None,
                             trades_ratio=float(np.median(v[:, 2] / np.maximum(base[:, 2], 1))),
                             # how much a coarser path flatters the same version, in R per trade
                             flatter_1m=float(np.mean(((v1[:, 0] + v1[:, 1]) - tot) / n)),
                             flatter_chart=float(np.mean(((vc[:, 0] + vc[:, 1]) - tot) / n)),
                             share_both_1m=float(((v1[:, 0] > 0) & (v1[:, 1] > 0)).mean()),
                             share_both_chart=float(((vc[:, 0] > 0) & (vc[:, 1] > 0)).mean())))
    out = dict(chart_tf=chart_tf, settings=int(len(res)), good=int(good.sum()),
               base_share_both=float(base_both.mean()), base_share_positive=float((base_tot > 0).mean()),
               base_median_total=float(np.median(base_tot)), base_median_trades=float(np.median(base[:, 2])), grid=grid)
    json.dump(out, open(os.path.join(res_dir, f"trailing_{chart_tf}m.json"), "w"))
    best = sorted(grid, key=lambda g: -g["share_both"])[:5]
    print(f"chart {chart_tf}m: {len(res)} settings; without trailing {out['base_share_both'] * 100:.1f}% positive in both halves "
          f"({out['base_share_positive'] * 100:.1f}% positive overall, median {out['base_median_total']:+.1f}R)")
    for g in best:
        print(f"  activation {g['act']} ATR, offset {g['off']} ATR: {g['share_both'] * 100:.1f}% positive in both halves, improves {g['share_improved'] * 100:.0f}% of settings, "
              f"median change {g['median_change']:+.1f}R; chart-candle walk would show {g['share_both_chart'] * 100:.1f}% ({g['flatter_chart']:+.3f}R per trade flattered)")


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    rdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    run(ctf, rdir, n, seed)
