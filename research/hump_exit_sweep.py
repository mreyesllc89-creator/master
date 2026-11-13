#!/usr/bin/env python3
"""
Exhaustive sweep of stop / target / trailing UNITS on the five Loma v1.31 presets (entries fixed).
  stop     hump extreme + buffer | points | percent of price | ATR multiple
  target   previous hump | multiple of risk | points | percent | ATR multiple
  trailing off | multiples of risk | points | percent | ATR multiple   (start x distance)
Chosen on 2025 only: score = worst half-year PF (>= MIN_TRADES per half), smoothed by the median
over the one-step neighbours of the same units. 2026 is out of sample.
Usage: python3 hump_exit_sweep.py <out_dir>
"""
import itertools, os, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
import hump_engine as H, hump_search as X

MIN_TRADES = 25
PICKS = {"M5_Buy_H1": 0, "M5_Buy_H4": 6, "M2_Sell_London_H1": 2, "M3_Sell_H4": 8, "M2_Sell_NY_H1": 12}
SL = {"hump": [0.1, 0.3, 0.6, 1.0, 1.5], "points": [1, 1.5, 2, 3, 4, 6, 8, 12],
      "percent": [0.03, 0.05, 0.08, 0.12, 0.18, 0.25], "atr": [0.5, 0.75, 1, 1.5, 2, 3, 4]}
TP = {"prev_hump": [0.0, 0.1, 0.2, 0.35], "risk_multiple": [0.75, 1, 1.5, 2, 3, 4, 6],
      "points": [1.5, 2, 3, 5, 8, 12, 20], "percent": [0.04, 0.07, 0.1, 0.15, 0.25, 0.4], "atr": [1, 1.5, 2, 3, 5, 8]}
TR = {"off": ([0.0], [0.5]), "risk_multiple": ([0.3, 0.5, 1, 1.5, 2], [0.2, 0.3, 0.5, 1, 1.5]),
      "points": ([0.5, 1, 2, 3, 5], [0.3, 0.5, 1, 2, 3]),
      "percent": ([0.02, 0.04, 0.07, 0.12, 0.2], [0.01, 0.02, 0.04, 0.07, 0.1]),
      "atr": ([0.3, 0.5, 1, 2, 3], [0.2, 0.3, 0.5, 1, 1.5])}
SLM = {"hump": 0, "points": 1, "percent": 2, "atr": 3}
TPM = {"prev_hump": 0, "risk_multiple": 1, "points": 2, "percent": 3, "atr": 4}
TRM = {"off": 0, "risk_multiple": 0, "points": 1, "percent": 2, "atr": 3}


def exits(slu, slv, tpu, tpv, tru, ts, td):
    e = dict(sl_mode=SLM[slu], tp_mode=TPM[tpu], trail_mode=TRM[tru], trail_start=ts, trail_dist=td, min_rr=0.3)
    if slu == "hump": e["buf"] = slv
    else: e["sl_val"] = slv
    if tpu == "prev_hump": e["anticip"] = tpv
    elif tpu == "risk_multiple": e["tp_rr"] = tpv
    else: e["tp_val"] = tpv
    return e


def pf(r):
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return w / l if l > 0 else (np.inf if w > 0 else np.nan)


def sweep(item):
    name, row = item
    L = pd.read_csv("results/hump_refined.csv")
    mk = H.Market()
    p = {k: X.cast(L.iloc[row][k], X.SPACE[k]) for k in X.SPACE}
    p.update(skip_big_pb=1, weekend_close=1)
    prep = mk.prepare(p)
    rows = []
    d0, d1, d2 = np.datetime64("2025-07-01"), np.datetime64("2026-01-01"), np.datetime64("2026-02-01")
    for slu, tpu, tru in itertools.product(SL, TP, TR):
        for (i, slv), (j, tpv), (a, ts), (b, td) in itertools.product(enumerate(SL[slu]), enumerate(TP[tpu]),
                                                                    enumerate(TR[tru][0]), enumerate(TR[tru][1])):
            df = mk.sim(prep, exits(slu, slv, tpu, tpv, tru, ts, td))
            t = df.entry_time.values; r = df.r.values
            h1 = r[t < d0]; h2 = r[(t >= d0) & (t < d1)]; o = r[t >= d1]
            s = H.stats(r)
            ok = len(h1) >= MIN_TRADES and len(h2) >= MIN_TRADES
            rows.append((slu, slv, tpu, tpv, tru, ts, td, i, j, a, b, len(h1), pf(h1), len(h2), pf(h2), len(o), pf(o),
                         pf(r[t >= d2]), s["n"], s["pf"], s["net"], s["dd"],
                         float(min(pf(h1), pf(h2))) if ok else 0.0))
    df = pd.DataFrame(rows, columns=["sl_unit", "sl", "tp_unit", "tp", "trail_unit", "trail_start", "trail_dist", "i", "j",
                                     "a", "b", "h1_n", "h1_pf", "h2_n", "h2_pf", "oos_n", "oos_pf", "oos_fm_pf", "n", "pf",
                                     "net", "dd", "raw"])
    # neighbour median within the same units (one step on one of the four value axes)
    df["raw"] = df.raw.replace([np.inf], 10.0).fillna(0.0)
    key = {k: v for v, k in enumerate(zip(df.sl_unit, df.tp_unit, df.trail_unit, df.i, df.j, df.a, df.b))}
    raw = df.raw.values; sm = np.zeros(len(df))
    for n, k in enumerate(zip(df.sl_unit, df.tp_unit, df.trail_unit, df.i, df.j, df.a, df.b)):
        vals = [raw[n]]
        for ax in (3, 4, 5, 6):
            for d in (-1, 1):
                q = list(k); q[ax] += d
                m = key.get(tuple(q))
                if m is not None: vals.append(raw[m])
        sm[n] = np.median(vals)
    df["score"] = sm
    df.insert(0, "preset", name)
    return df


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    with Pool(4) as pool:
        parts = pool.map(sweep, list(PICKS.items()), chunksize=1)
    df = pd.concat(parts)
    df.to_csv(os.path.join(out, "exit_sweep.csv.gz"), index=False)
    print(len(df), "combinations")
