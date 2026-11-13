#!/usr/bin/env python3
"""Pool the refined setups of both gold passes (results/hump_refined.csv, results/hump2_refined.csv), run them all
with the v1.31 rules, and rank by a 2025-only robustness score: the worse half-year PF of 2025 under harsh
stress (entry 1 min late, pessimistic trailing, 0.10 slippage, commission). 2026 is reported, never used to rank."""
import os, sys
import numpy as np, pandas as pd
os.environ["HUMP_SPACE"] = "2"
import hump_engine as H, hump_search as X

STRESS = dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0)
def pf(r):
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(w / l) if l > 0 else float("inf")

def halves(df):
    t = df.entry_time.values; r = df.r.values
    h1 = t < np.datetime64("2025-07-01"); y26 = t >= np.datetime64("2026-01-01"); h2 = ~h1 & ~y26
    s = H.stats(r)
    return dict(n=s["n"], pf=s["pf"], net=s["net"], dd=s["dd"], n_h1=int(h1.sum()), n_h2=int(h2.sum()),
                w25=min(pf(r[h1]), pf(r[h2])), pf26=pf(r[y26]), n26=int(y26.sum()),
                pf26_fm=pf(r[t >= np.datetime64("2026-02-01")]))

def main():
    mk = H.Market(); rows = []
    for src, path in [("pass1", "results/hump_refined.csv"), ("pass2", "results/hump2_refined.csv")]:
        L = pd.read_csv(path)
        for i in range(len(L)):
            p = {}
            for k in X.SPACE:
                if k in L.columns: p[k] = X.cast(L.iloc[i][k], X.SPACE[k])
            p.setdefault("macd", "12-26"); p.setdefault("stoch_lv", "20-80")
            for k, v in dict(htf_ema=50, stoch_k=7, max_hold=0, eod=-1).items(): p.setdefault(k, v)
            c = X.engine_cfg(dict(p, skip_big_pb=1, weekend_close=1))
            b = halves(mk.run(c)); s = halves(mk.run(dict(c, **STRESS)))
            rows.append(dict(src=src, row=i, **p, **b, **{f"st_{k}": v for k, v in s.items()}))
    d = pd.DataFrame(rows)
    ok = (d.n_h1 >= 25) & (d.n_h2 >= 25)
    d["rank_score"] = np.where(ok, np.minimum(d.w25, d.st_w25), 0.0)      # 2025 only
    d = d.sort_values("rank_score", ascending=False)
    d.to_csv("results/hump_pool_ranked.csv", index=False)
    pd.set_option("display.width", 330)
    cols = ["src", "row", "tf", "sides", "session", "htf", "htf_ema", "macd", "stoch_k", "max_hold", "eod", "n", "pf", "dd", "w25",
            "st_w25", "rank_score", "pf26", "n26", "st_pf", "st_pf26"]
    print(d[cols].round(2).to_string(index=False))

if __name__ == "__main__":
    main()
