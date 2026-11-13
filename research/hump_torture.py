#!/usr/bin/env python3
"""
Stress battery for the five Loma presets (research/results/hump_refined.csv rows 0, 6, 2, 8, 12).
  A costs      spread x1..x3, slippage on entries and stops, commission, combined harsh / brutal
  B execution  entry 1-2 minutes late, pessimistic same-bar trailing, both, plus harsh costs
  C settings   400 random joint perturbations (every numeric setting moved -1 / 0 / +1 step)
  D statistics bootstrap PF interval, Monte-Carlo drawdown and losing streak, chance of a losing year
  E luck test  is the hump filter better than picking the same number of zero-cross trades at random?
  F calendar   month-by-month results, worst month and quarter
Usage: python3 hump_torture.py <out_dir>
"""
import json, os, sys
import numpy as np, pandas as pd
import hump_engine as H, hump_search as X

PICKS = {"M5_Buy_H1": 0, "M5_Buy_H4": 6, "M2_Sell_London_H1": 2, "M3_Sell_H4": 8, "M2_Sell_NY_H1": 12}
RNG = np.random.default_rng(20261113)


def pf(r):
    r = np.asarray(r, float); w = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(w / l) if l > 0 else float("inf")


def summ(df):
    t = df.entry_time.values; r = df.r.values
    m26 = t >= np.datetime64("2026-01-01")
    s = H.stats(r)
    return dict(n=s["n"], pf=round(s["pf"], 2), net=round(s["net"], 1), dd=round(s["dd"], 1),
                pf25=round(pf(r[~m26]), 2), pf26=round(pf(r[m26]), 2), n26=int(m26.sum()))


def main(out):
    os.makedirs(out, exist_ok=True)
    L = pd.read_csv("results/hump_refined.csv")
    mk = H.Market()
    res = {}
    for name, row in PICKS.items():
        p = {k: X.cast(L.iloc[row][k], X.SPACE[k]) for k in X.SPACE}
        p["max_spread"] = 5.0                       # the spread cap must not hide the stress
        if os.environ.get("HUMP_FIXES") == "1":      # v1.31: skip big pullback humps, close before the weekend
            p.update(skip_big_pb=1, weekend_close=1)
        R = {}
        base = mk.run(p)
        R["base"] = summ(base)
        # ---- A costs
        A = {}
        for label, ch in [("slip 0.05", dict(slip=0.05)), ("slip 0.10", dict(slip=0.10)), ("slip 0.20", dict(slip=0.20)),
                          ("commission 0.07", dict(comm=0.07)),
                          ("harsh: slip 0.10 + comm 0.07", dict(slip=0.10, comm=0.07)),
                          ("brutal: slip 0.20 + comm 0.07", dict(slip=0.20, comm=0.07))]:
            A[label] = summ(mk.run(dict(p, **ch)))
        R["costs"] = A
        # ---- B execution
        Bx = {}
        for label, ch in [("entry 1 min late", dict(delay=1)), ("entry 2 min late", dict(delay=2)),
                          ("pessimistic trailing", dict(trail_worst=1)),
                          ("late 1 + pessimistic trailing", dict(delay=1, trail_worst=1)),
                          ("late 1 + pess. trailing + harsh costs", dict(delay=1, trail_worst=1, slip=0.10, comm=0.07)),
                          ("no trailing at all", dict(trail_start=0.0))]:
            Bx[label] = summ(mk.run(dict(p, **ch)))
        R["execution"] = Bx
        # ---- C settings Monte Carlo
        num = [k for k in X.SPACE if k not in ("tf", "sides", "session", "htf", "tp_mode", "stoch_req")]
        pfs, pf26s = [], []
        for _ in range(400):
            q = dict(p)
            for k in num:
                lv = X.SPACE[k]; i = lv.index(p[k]) + int(RNG.integers(-1, 2))
                q[k] = lv[min(max(i, 0), len(lv) - 1)]
            s = summ(mk.run(q))
            if s["n"] >= 30:
                pfs.append(s["pf"]); pf26s.append(s["pf26"])
        pfs = np.array(pfs); pf26s = np.array([x for x in pf26s if np.isfinite(x)])
        R["settings_mc"] = dict(runs=len(pfs), pf_p5=round(float(np.percentile(pfs, 5)), 2),
                                pf_median=round(float(np.median(pfs)), 2), share_profitable=round(float((pfs > 1).mean()), 2),
                                share_pf_above_1_3=round(float((pfs > 1.3).mean()), 2),
                                pf26_median=round(float(np.median(pf26s)), 2),
                                share_2026_profitable=round(float((pf26s > 1).mean()), 2))
        # ---- D statistics (on the harsh-cost trades: slip 0.10 + commission)
        hr = mk.run(dict(p, slip=0.10, comm=0.07)).r.values
        n = len(hr)
        bs = np.array([pf(hr[RNG.integers(0, n, n)]) for _ in range(5000)])
        dds, streaks, neg = [], [], 0
        per_year = max(1, int(round(n / 1.37)))                     # 16.5 months of data
        for _ in range(5000):
            x = hr[RNG.integers(0, n, per_year)]
            eq = np.cumsum(x); dds.append(float((np.maximum.accumulate(eq) - eq).max()))
            run = best = 0
            for v in x:
                run = run + 1 if v < 0 else 0; best = max(best, run)
            streaks.append(best); neg += eq[-1] < 0
        R["statistics_harsh"] = dict(trades=n, pf=round(pf(hr), 2), pf_ci5=round(float(np.percentile(bs, 5)), 2),
                                     pf_ci95=round(float(np.percentile(bs, 95)), 2),
                                     prob_pf_below_1=round(float((bs < 1).mean()), 3),
                                     trades_per_year=per_year, year_dd_median_R=round(float(np.median(dds)), 1),
                                     year_dd_p95_R=round(float(np.percentile(dds, 95)), 1),
                                     losing_streak_p95=int(np.percentile(streaks, 95)),
                                     prob_losing_year=round(neg / 5000, 3),
                                     expectancy_R=round(float(hr.mean()), 3))
        # ---- E luck test: random subsets of the every-zero-cross trades in the same setting
        cl = mk.run(dict(p, classic=1)).r.values
        k = len(base)
        if len(cl) > k:
            rnd = np.array([pf(RNG.choice(cl, k, replace=False)) for _ in range(5000)])
            R["luck_test"] = dict(zero_cross_trades=len(cl), zero_cross_pf=round(pf(cl), 2), hump_pf=R["base"]["pf"],
                                  random_subset_pf_p95=round(float(np.percentile(rnd, 95)), 2),
                                  p_value=round(float((rnd >= R["base"]["pf"]).mean()), 4))
        # ---- F calendar
        b = base.copy(); b["month"] = pd.DatetimeIndex(b.entry_time).to_period("M")
        mth = b.groupby("month").r.sum()
        q = b.groupby(pd.DatetimeIndex(b.entry_time).to_period("Q")).r.sum()
        R["calendar"] = dict(months=len(mth), losing_months=int((mth < 0).sum()), worst_month_R=round(float(mth.min()), 1),
                             best_month_R=round(float(mth.max()), 1), losing_quarters=int((q < 0).sum()),
                             worst_quarter_R=round(float(q.min()), 1),
                             top3_months_share=round(float(mth.sort_values().tail(3).sum() / mth.sum()), 2))
        res[name] = R
        print(name, json.dumps(R["base"]), flush=True)
    json.dump(res, open(os.path.join(out, "torture.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
