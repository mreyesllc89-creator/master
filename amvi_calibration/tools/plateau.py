"""Plateau test: among the rows that are positive in both halves, prefer the one whose
neighbours (every input moved one grid step, one at a time) are positive in both halves too.
A lone peak surrounded by losing neighbours is fragile: it depends on one input's exact value.

This is a screen against fragility, NOT evidence against luck: neighbours take mostly the
candidate's own trades (a median 70 to 90 % of its entries), so a setting that is positive in
both halves by luck has positive neighbours too in about nine cases of ten. A neighbour that
takes exactly the candidate's trades (the moved input is not read by this setting) is not
counted.

The pick of a timeframe = the candidate with the largest share of neighbours positive in both
halves; ties go to the steadier neighbourhood (the neighbours' median monthly t-statistic of
their worse half). Steadiness, not the sum in R: sums in R are not comparable between a
0.5 x ATR stop and a 6 x ATR stop, and they favour settings that live on a few huge trades.

usage: python plateau.py <chart_tf_minutes> [results_dir]
Reads results/holdout_<tf>m.json (candidates), writes results/plateau_<tf>m.json.
"""
import json
import os
import sys
from multiprocessing import get_context

import numpy as np

import holdout
import space
import sweep


def _score(job):
    ci, name, p = job
    r = sweep.evaluate(p)
    nm = r["gross"].size
    M = holdout.split_masks(nm)
    net = r["gross"].astype(np.float64) - holdout.BASE_FEE * r["feeu"] - r["fund"]
    net_s = r["gross"].astype(np.float64) - holdout.STRESS_FEE * r["feeu"] - r["fund"]
    t1 = float(holdout.month_t(net[None, M["h1"]])[0])
    t2 = float(holdout.month_t(net[None, M["h2"]])[0])
    return (ci, name, float(net[M["h1"]].sum()), float(net[M["h2"]].sum()), float(net_s.sum()), int(r["n"]), min(t1, t2),
            int(r["h"]), r["gross"].tobytes())


def run(chart_tf, res_dir, max_candidates=20, procs=4):
    hold = json.load(open(os.path.join(res_dir, f"holdout_{chart_tf}m.json")))
    cands = hold["candidates"][:max_candidates]
    if not cands:
        json.dump(dict(chart_tf=chart_tf, picks=[]), open(os.path.join(res_dir, f"plateau_{chart_tf}m.json"), "w"))
        print(f"chart {chart_tf}m: no candidate is positive in both halves")
        return
    ft, fund = sweep.load_context()
    sweep.precompute(ft, chart_tf)
    sweep.G.update(ft=ft, fund=fund, chart_tf=chart_tf, start_ms=sweep.ms(sweep.WINDOW_START), end_ms=sweep.ms(sweep.WINDOW_END))
    jobs = []
    for ci, c in enumerate(cands):
        jobs.append((ci, "self", space.normalize(c["setting"])))
        for name, q in space.neighbours(c["setting"], chart_tf):
            jobs.append((ci, name, q))
    with get_context("fork").Pool(procs) as pool:
        out = pool.map(_score, jobs, chunksize=8)
    rows = []
    for ci, c in enumerate(cands):
        own = next(o for o in out if o[0] == ci and o[1] == "self")
        every = [o for o in out if o[0] == ci and o[1] != "self"]
        mine = [o for o in every if not (o[7] == own[7] and o[8] == own[8])]     # same entries and same months = the candidate itself
        if not mine:
            continue
        worst = np.array([min(o[2], o[3]) for o in mine])
        both = np.array([o[2] > 0 and o[3] > 0 for o in mine])
        tot = np.array([o[2] + o[3] for o in mine])
        wt = np.array([o[6] for o in mine])
        bad_inputs = sorted({o[1] for o in mine if not (o[2] > 0 and o[3] > 0)})
        rows.append(dict(row=c["row"], own_worst=min(c["h1"], c["h2"]), own_total=c["total"], n=c["n"], dd=c["dd"],
                         neighbours=len(mine), identical_dropped=len(every) - len(mine),
                         share_both_positive=float(both.mean()), share_total_positive=float((tot > 0).mean()),
                         median_worst_half=float(np.median(worst)), min_worst_half=float(worst.min()),
                         median_worst_t=float(np.median(wt)), own_worst_t=min(c["t_h1"], c["t_h2"]),
                         fragile_inputs=bad_inputs, setting=c["setting"], h1=c["h1"], h2=c["h2"], stress_total=c["stress_total"]))
    # a plateau first (share of neighbours positive in both halves), then its steadiness
    rows.sort(key=lambda r: (-round(r["share_both_positive"], 2), -r["median_worst_t"]))
    json.dump(dict(chart_tf=chart_tf, picks=rows), open(os.path.join(res_dir, f"plateau_{chart_tf}m.json"), "w"))
    print(f"chart {chart_tf}m: {len(cands)} candidates, {len(jobs) - len(cands)} neighbour backtests "
          f"({sum(r['identical_dropped'] for r in rows)} took exactly the candidate's trades and are not counted)")
    for r in rows[:8]:
        print(f"  row {r['row']}: own halves {r['h1']:+.1f} / {r['h2']:+.1f}R; {r['share_both_positive'] * 100:.0f}% of {r['neighbours']} neighbours positive in both halves, "
              f"their median worse-half steadiness t {r['median_worst_t']:.2f} (median worse half {r['median_worst_half']:+.1f}R, worst {r['min_worst_half']:+.1f}R); "
              f"fragile: {', '.join(r['fragile_inputs']) or 'none'}")


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    rdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(ctf, rdir)
