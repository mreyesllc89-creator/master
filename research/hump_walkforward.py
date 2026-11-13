#!/usr/bin/env python3
"""
Walk-forward test of the Loma method with a REDUCED setting space.

Locked to the method as described in the videos: MACD 12/26, Stochastic 7 with levels 20/80 required on the big
hump, pullback hump of at least 3 bars, at most 2 signals per big hump, no signal off a big pullback hump,
weekend close. Searched (576 setups): trigger timeframe, direction, trend filter, session, big-hump size,
target and trailing.

Rolling: calibrate on TRAIN months, then trade the next TEST months with the chosen setting(s), untouched,
and roll forward by TEST months. Only the untouched test trades are reported. Pass mark (fixed beforehand):
PF > 1.2 on all test trades combined, after costs, with at least 100 test trades.

Selection inside each training window: score = the lower PF of the two halves of the training window (each
needs >= MIN_HALF trades), smoothed by the median over one-step neighbours on the ordered settings. Variants:
  top1  - the single best-scoring setup
  top5  - the five best setups, all traded (results in R, each trade counted)
  stress versions of both: entry 1 minute late, pessimistic trailing, slippage and commission.
Usage: python3 hump_walkforward.py <out_dir> [train_months] [test_months]
"""
import itertools, os, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
import hump_engine as H

GRID = dict(tf=["M2", "M3", "M5", "M10"], sides=[-1, 1, 0], htf=["none", "H1", "H4"], session=["all", "ldn_ny_07-20"],
            big_mult=[1.5, 2.5], tp_rr=[1.5, 3.0], trail=[(0.0, 0.5), (0.5, 0.5)])
ORDERED = {"tf": GRID["tf"], "big_mult": GRID["big_mult"], "tp_rr": GRID["tp_rr"], "trail": GRID["trail"]}
LOCKED = dict(stoch_req=1, pb_min_bars=3, pb_max_ratio=0.6, max_signals=2, hist=20, big_min_bars=5, break_ratio=1.0,
              trend_max_bars=120, tp_mode=1, buf=0.3, min_risk=0.5, min_rr=0.3, skip_big_pb=1, weekend_close=1)
STRESS = dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0)
MIN_HALF = 12
MK = None


def init():
    global MK
    MK = H.Market()


def cfg_of(p):
    c = dict(LOCKED, tf=p["tf"], sides=p["sides"], htf=p["htf"], session=p["session"], big_mult=p["big_mult"],
             tp_rr=p["tp_rr"], trail_start=p["trail"][0], trail_dist=p["trail"][1])
    return c


def trades(p):
    c = cfg_of(p)
    a = MK.run(c); b = MK.run(dict(c, **STRESS))
    return [(a.entry_time.values, a.r.values), (b.entry_time.values, b.r.values)]


def pf(r):
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return w / l if l > 0 else (np.inf if w > 0 else np.nan)


def main(out, train_m=6, test_m=2):
    os.makedirs(out, exist_ok=True)
    pts = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    with Pool(4, initializer=init) as pool:
        res = pool.map(trades, pts, chunksize=4)
    keys = [tuple(str(p[k]) for k in GRID) for p in pts]
    index = {k: i for i, k in enumerate(keys)}
    start = pd.Timestamp("2025-01-01"); end = pd.Timestamp("2026-05-16")
    rows, picks = [], []
    t0 = start
    while True:
        tr0, tr1 = t0, t0 + pd.DateOffset(months=train_m)
        te0, te1 = tr1, min(tr1 + pd.DateOffset(months=test_m), end)
        if te0 >= end:
            break
        mid = tr0 + (tr1 - tr0) / 2
        raw = np.zeros(len(pts))
        for i, ((t, r), _) in enumerate(res):
            a = r[(t >= np.datetime64(tr0)) & (t < np.datetime64(mid))]
            b = r[(t >= np.datetime64(mid)) & (t < np.datetime64(tr1))]
            if len(a) >= MIN_HALF and len(b) >= MIN_HALF:
                raw[i] = min(pf(a), pf(b))
        raw = np.nan_to_num(raw, nan=0.0, posinf=5.0)
        sm = np.zeros(len(pts))
        for i, p in enumerate(pts):
            vals = [raw[i]]
            for k, lv in ORDERED.items():
                j = lv.index(p[k])
                for d in (-1, 1):
                    if 0 <= j + d < len(lv):
                        q = dict(p); q[k] = lv[j + d]
                        vals.append(raw[index[tuple(str(q[x]) for x in GRID)]])
            sm[i] = np.median(vals)
        order = np.argsort(-sm)
        for variant, n in (("top1", 1), ("top5", 5)):
            for mode in (0, 1):
                rr = []
                for i in order[:n]:
                    t, r = res[i][mode]
                    m = (t >= np.datetime64(te0)) & (t < np.datetime64(te1))
                    rr.append(r[m])
                rr = np.concatenate(rr) if rr else np.array([])
                rows.append(dict(window=f"{te0:%Y-%m}..{te1:%Y-%m-%d}", variant=variant, stress=bool(mode), n=len(rr),
                                 pf=pf(rr), net=float(rr.sum())))
                if mode == 0:
                    for i in order[:n]:
                        picks.append(dict(window=f"{te0:%Y-%m}", variant=variant, score=round(sm[i], 2), **{k: str(pts[i][k]) for k in GRID}))
        t0 = t0 + pd.DateOffset(months=test_m)
    w = pd.DataFrame(rows); w.to_csv(os.path.join(out, "windows.csv"), index=False)
    pd.DataFrame(picks).to_csv(os.path.join(out, "picks.csv"), index=False)
    # combined untouched results
    summ = []
    for (v, s), g in w.groupby(["variant", "stress"]):
        summ.append(dict(variant=v, stress=s, windows=len(g), windows_profitable=int((g.net > 0).sum()), n=int(g.n.sum())))
    print(w.round(2).to_string(index=False))
    return w


if __name__ == "__main__":
    out = sys.argv[1]
    tr = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    te = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    main(out, tr, te)
