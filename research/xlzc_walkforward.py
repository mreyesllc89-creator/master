#!/usr/bin/env python3
"""
Walk-forward check of the selection procedure (review finding: the headline was
chosen with all 17 months, so nothing was held out).

Select using 2025 only (2025-H1 and 2025-H2), then measure on 2026 Jan-May,
which the selection never sees. Compares:
  * config-level picks (top-k by worst-half 2025 PF)
  * pair-level picks (the trigger/HTF pair whose configs did best in 2025)
  * the base rate: share of all configs profitable in 2026
Usage: python3 xlzc_walkforward.py <calibration_grid.csv[.gz]> <out.json>
"""
import json
import sys

import numpy as np
import pandas as pd

CHOSEN = dict(tf="M3/H1", N=40, S=2, buffer=120, NT=120, min_rr=1.5, fb=0.0, stoch="soft",
              session="ny_12-1630", trail=True)


def pf_of(df, col):
    return float(df[col].median()) if len(df) else float("nan")


def main():
    d = pd.read_csv(sys.argv[1])
    d["min25"] = d[["2025H1_pf", "2025H2_pf"]].min(axis=1)
    d["t25"] = d[["2025H1_trades", "2025H2_trades"]].min(axis=1)
    out = {"n_configs": int(len(d))}
    base = d[d["2026_trades"] >= 10]
    out["base_rate_2026_pf_gt1"] = float((base["2026_pf"] > 1).mean())
    out["base_median_2026_pf"] = float(base["2026_pf"].median())
    rows = []
    for floor in (10, 15, 20):
        pool = d[(d.t25 >= floor) & (d["2026_trades"] >= 5)].sort_values("min25", ascending=False)
        for k in (1, 10, 50, 200):
            top = pool.head(k)
            rows.append(dict(min_trades_per_half=floor, top_k=k,
                             median_2025_minpf=float(top.min25.median()),
                             median_2026_pf=float(top["2026_pf"].median()),
                             share_2026_pf_gt1=float((top["2026_pf"] > 1).mean()),
                             pairs=top.tf.value_counts().head(3).to_dict()))
    out["config_level"] = rows
    # where the published M3/H1 setup ranks when only 2025 is used
    m = np.ones(len(d), bool)
    for k, v in CHOSEN.items():
        m &= (d[k] == v).values
    ch = d[m].iloc[0]
    pool = d[d.t25 >= 10].sort_values("min25", ascending=False).reset_index(drop=True)
    rank = int(pool.index[(pool[list(CHOSEN)] == pd.Series(CHOSEN)).all(axis=1)][0]) + 1 \
        if ((pool[list(CHOSEN)] == pd.Series(CHOSEN)).all(axis=1)).any() else None
    out["chosen"] = dict(rank_on_2025_only=rank, of=int(len(pool)), min25=float(ch.min25),
                         pf_2026=float(ch["2026_pf"]), trades_2026=int(ch["2026_trades"]))
    # pair level: family = NY session, trailing, TP lookback 120, soft, no fallback
    fam = d[(d.session == "ny_12-1630") & d.trail & (d.NT == 120) & (d.fb == 0) & (d.stoch == "soft")]
    pr = []
    for tf, g in fam.groupby("tf"):
        pr.append(dict(tf=tf, share_2025_both_halves_gt1=float((g.min25 > 1).mean()),
                       median_min25=float(g.min25.median()),
                       median_2026_pf=float(g["2026_pf"].median()),
                       share_2026_gt1=float((g["2026_pf"] > 1).mean())))
    pr.sort(key=lambda r: -r["median_min25"])
    out["pair_level"] = pr
    best25 = pr[0]
    out["note"] = (f"Walk-forward: picking on 2025 only, the top-10 configs had median 2026 PF "
                   f"{[r for r in rows if r['min_trades_per_half']==10 and r['top_k']==10][0]['median_2026_pf']:.2f}; "
                   f"the best 2025 pair family ({best25['tf']}) had median 2026 PF {best25['median_2026_pf']:.2f}. "
                   f"Base rate: {out['base_rate_2026_pf_gt1']*100:.0f}% of all configs were profitable in 2026.")
    json.dump(out, open(sys.argv[2], "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
