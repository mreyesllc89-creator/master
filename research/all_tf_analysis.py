#!/usr/bin/env python3
"""
Every-timeframe calibration summary: combine calibration grids, rank every trigger/filter pair
on 2025 ONLY, and show how each pair did in 2026 (never used for the ranking).

  python3 all_tf_analysis.py <out.json> <grid.csv[.gz]> [<grid2.csv[.gz]> ...]

Per pair:
  * all setups with >= 15 trades in each 2025 half-year ("tradable")
  * share of them profitable in BOTH 2025 halves, median worst-half 2025 PF
  * the same setups in 2026: median PF and share profitable
  * best "family" on 2025 (session x trailing x stochastic, median over the structure grid)
    and that family's 2026 median PF
"""
import json
import sys

import numpy as np
import pandas as pd

import xlzc_backtest as B


def main():
    out = sys.argv[1]
    d = pd.concat([pd.read_csv(f) for f in sys.argv[2:]], ignore_index=True).drop_duplicates(
        ["tf", "N", "S", "buffer", "NT", "min_rr", "fb", "stoch", "session", "trail"])
    d["min25"] = d[["2025H1_pf", "2025H2_pf"]].min(axis=1)
    d["t25"] = d[["2025H1_trades", "2025H2_trades"]].min(axis=1)
    rows = []
    for tf, g in d.groupby("tf"):
        tr = g[g.t25 >= 15]
        fam = (tr.groupby(["session", "trail", "stoch"])
               .agg(m25=("min25", "median"), n=("min25", "size"), m26=("2026_pf", "median"),
                    s26=("2026_pf", lambda x: (x > 1).mean()))
               .reset_index())
        fam = fam[fam.n >= 20].sort_values("m25", ascending=False)
        best = fam.iloc[0] if len(fam) else None
        trig, htf = tf.split("/")
        rows.append(dict(
            tf=tf, trigger=trig, filter=htf, configs=int(len(g)), tradable=int(len(tr)),
            trades_med=float(g.all_trades.median()),
            share25=float((tr.min25 > 1).mean()) if len(tr) else np.nan,
            med25=float(tr.min25.median()) if len(tr) else np.nan,
            med26=float(tr["2026_pf"].median()) if len(tr) else np.nan,
            share26=float((tr["2026_pf"] > 1).mean()) if len(tr) else np.nan,
            fam=None if best is None else f"{best.session}, trailing {'on' if best.trail else 'off'}, stoch {best.stoch}",
            fam25=None if best is None else float(best.m25), fam26=None if best is None else float(best.m26),
            fam26share=None if best is None else float(best.s26)))
    t = pd.DataFrame(rows).sort_values(["med25"], ascending=False)
    # does a 2025 pair ranking predict 2026?  rank correlation over pairs with enough setups
    ok = t[t.tradable >= 50]
    rho = float(ok[["med25", "med26"]].rank().corr().iloc[0, 1]) if len(ok) > 3 else np.nan
    top = ok.head(5)
    res = dict(symbol=B.SYMBOL, inst=B.INST, pairs=t.to_dict("records"), rank_corr_2025_2026=rho,
               top5_by_2025=top.tf.tolist(), top5_med26=float(top.med26.median()) if len(top) else np.nan,
               all_med26=float(ok.med26.median()) if len(ok) else np.nan)
    json.dump(res, open(out, "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    print(t[["tf", "configs", "tradable", "trades_med", "share25", "med25", "med26", "share26", "fam", "fam25", "fam26"]]
          .round(2).to_string(index=False))
    print(f"\nrank correlation of 2025 vs 2026 pair medians: {rho:.2f}")
    print(f"top 5 pairs by 2025 {res['top5_by_2025']}: median 2026 PF {res['top5_med26']:.2f} "
          f"(all tradable pairs {res['all_med26']:.2f})")


if __name__ == "__main__":
    main()
