"""Does choosing settings on the search window carry to the untouched period?

usage: python untouched_check.py [results_dir] [n_random=400]

For every chart timeframe: the candidates of the search window (positive in both halves at
base and stressed costs, the 25 steadiest with distinct entries, from holdout_<tf>m.json) and
a random sample of the sweep's settings (at least 30 trades in each half of the search window)
are run over the untouched period 2021-01-01 to 2023-10-31, which the search and the selection
do not use. Net of 0.05 % per side, 1 tick and funding.

The test (the same three conditions as the hold-out tests inside the search window): the
candidates' mean must be positive, above the 95th percentile of the mean of equally many
random settings, and their basket must stay positive in 95 % of resamples of the months.

The same test is repeated against random settings of the SAME trade direction as the
candidates (as many inverted and as many with-the-filter ones): did the search find anything
beyond which direction to trade?

This is a test of the selection method on a timeframe. It does not choose anything: the pick
of a timeframe is fixed by plateau.py before this runs, and no pick may ever be swapped using
the numbers written here. "Above random settings" is the easy leg (random settings mostly
bleed commission); being positive and staying positive when the months are resampled are the
legs that bind.

Writes results/untouched_<tf>m.json.
"""
import json
import os
import sys
from multiprocessing import get_context

import numpy as np

import final_eval as F
import holdout
import space
import sweep

N_DRAWS = 20000


def _work(job):
    kind, row, p = job
    r = sweep.evaluate(p)
    net = r["gross"].astype(np.float64) - holdout.BASE_FEE * r["feeu"] - r["fund"]
    net_s = r["gross"].astype(np.float64) - holdout.STRESS_FEE * r["feeu"] - r["fund"]
    return kind, row, net, float(net_s.sum()), int(r["n"])


def run(res_dir, n_random=400, seed=77, procs=4):
    ft, fund = sweep.load_context(start=F.PRE_LOAD, end=F.PRESAMPLE[1], sec_start=F.PRESAMPLE[0])
    for tf in space.CHART_TFS:
        hp = os.path.join(res_dir, f"holdout_{tf}m.json")
        if not os.path.exists(hp):
            continue
        hold = json.load(open(hp))
        d, settings = holdout.load(os.path.join(res_dir, "sweeps"), tf)
        nm = d["gross"].shape[1]
        M = holdout.split_masks(nm)
        cnt = d["cnt"]
        ok = np.nonzero((cnt[:, M["h1"]].sum(1) >= 30) & (cnt[:, M["h2"]].sum(1) >= 30))[0]
        rng = np.random.default_rng(seed + tf)
        rnd = rng.choice(ok, size=min(n_random, ok.size), replace=False)
        jobs = [("cand", c["row"], c["setting"]) for c in hold["candidates"]] + [("rand", int(i), settings[int(i)]) for i in rnd]
        sweep.precompute(ft, tf)
        sweep.G.update(ft=ft, fund=fund, chart_tf=tf, start_ms=sweep.ms(F.PRESAMPLE[0]), end_ms=sweep.ms(F.PRESAMPLE[1]))
        with get_context("fork").Pool(procs) as pool:
            out = pool.map(_work, jobs, chunksize=4)
        cand = [o for o in out if o[0] == "cand"]
        rand = [o for o in out if o[0] == "rand"]
        rt = np.array([o[2].sum() for o in rand])
        inv = np.array([bool(settings[o[1]]["inverted"]) for o in rand])
        res = dict(chart_tf=tf, period=list(F.PRESAMPLE), n_candidates=len(cand), n_random=len(rand),
                   random_mean=float(rt.mean()) if rt.size else 0.0, random_median=float(np.median(rt)) if rt.size else 0.0,
                   random_share_positive=float((rt > 0).mean()) if rt.size else 0.0,
                   # the random settings by trade direction: is "with the filter" better on the untouched period too?
                   random_with_filter=dict(n=int((~inv).sum()), share_positive=float((rt[~inv] > 0).mean()) if (~inv).any() else 0.0,
                                           median=float(np.median(rt[~inv])) if (~inv).any() else 0.0),
                   random_inverted=dict(n=int(inv.sum()), share_positive=float((rt[inv] > 0).mean()) if inv.any() else 0.0,
                                        median=float(np.median(rt[inv])) if inv.any() else 0.0),
                   candidates_inverted=int(sum(bool(c["setting"]["inverted"]) for c in hold["candidates"])),
                   candidates=[dict(row=o[1], total=float(o[2].sum()), stress=o[3], n=o[4]) for o in cand])
        if cand and rt.size >= 2 * len(cand):
            ct = np.array([o[2].sum() for o in cand])
            k = ct.size
            null = np.array([rt[rng.choice(rt.size, k, replace=False)].mean() for _ in range(N_DRAWS)])
            basket = np.mean([o[2] for o in cand], axis=0)
            m = basket.size
            boot = float((basket[rng.integers(0, m, size=(N_DRAWS, m))].sum(1) > 0).mean())
            res.update(cand_mean=float(ct.mean()), cand_median=float(np.median(ct)), cand_share_positive=float((ct > 0).mean()),
                       cand_share_positive_stress=float(np.mean([o[3] > 0 for o in cand])),
                       null_p95=float(np.percentile(null, 95)), p=float((null >= ct.mean()).mean()), boot_pos=boot,
                       passed=bool(ct.mean() > 0 and ct.mean() > np.percentile(null, 95) and boot >= 0.95))
            # the same against random settings of the candidates' own trade direction
            cinv = np.array([bool(settings[o[1]]["inverted"]) for o in cand])
            k_inv, k_wf = int(cinv.sum()), int((~cinv).sum())
            r_inv, r_wf = rt[inv], rt[~inv]
            if r_inv.size >= max(2 * k_inv, 1) and r_wf.size >= max(2 * k_wf, 1):
                mnull = np.empty(N_DRAWS)
                for j in range(N_DRAWS):
                    a = r_inv[rng.choice(r_inv.size, k_inv, replace=False)].sum() if k_inv else 0.0
                    b = r_wf[rng.choice(r_wf.size, k_wf, replace=False)].sum() if k_wf else 0.0
                    mnull[j] = (a + b) / k
                res.update(matched_null_mean=float(mnull.mean()), matched_null_p95=float(np.percentile(mnull, 95)),
                           matched_p=float((mnull >= ct.mean()).mean()),
                           passed_matched=bool(ct.mean() > 0 and ct.mean() > np.percentile(mnull, 95) and boot >= 0.95))
        else:
            res.update(passed=False)
        json.dump(res, open(os.path.join(res_dir, f"untouched_{tf}m.json"), "w"))
        if "cand_mean" in res:
            print(f"chart {tf}m: {res['n_candidates']} candidates on the untouched period: mean {res['cand_mean']:+.1f}R, {res['cand_share_positive'] * 100:.0f}% positive "
                  f"(stressed costs {res['cand_share_positive_stress'] * 100:.0f}%), months resampled {res['boot_pos'] * 100:.0f}%; "
                  f"{res['n_random']} random settings: mean {res['random_mean']:+.1f}R, {res['random_share_positive'] * 100:.0f}% positive, "
                  f"p95 of equal-size random groups {res['null_p95']:+.1f}R -> {'PASS' if res['passed'] else 'fail'}", flush=True)
            if "matched_null_p95" in res:
                print(f"    against random settings of the same direction: their groups average {res['matched_null_mean']:+.1f}R, p95 {res['matched_null_p95']:+.1f}R "
                      f"-> {'PASS' if res['passed_matched'] else 'fail'}", flush=True)
        else:
            print(f"chart {tf}m: no candidates; {res['n_random']} random settings: mean {res['random_mean']:+.1f}R, {res['random_share_positive'] * 100:.0f}% positive", flush=True)
        print(f"    random settings by direction on the untouched period: with the filter {res['random_with_filter']['share_positive'] * 100:.0f}% positive "
              f"(median {res['random_with_filter']['median']:+.1f}R, {res['random_with_filter']['n']} settings); inverted {res['random_inverted']['share_positive'] * 100:.0f}% "
              f"(median {res['random_inverted']['median']:+.1f}R, {res['random_inverted']['n']}); {res['candidates_inverted']} of {res['n_candidates']} candidates are inverted", flush=True)


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(rd, int(sys.argv[2]) if len(sys.argv) > 2 else 400)
