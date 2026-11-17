"""Re-score the settings that passed the in-sample filter at other spreads (held-out year, 1-minute data)."""
import numpy as np
import pandas as pd

import engine as E
from space import *

M1 = E.load("../data/BTCUSDT_1m.npz")
d = pd.read_csv("../results/sweep_seed1.csv")
s = d[(d.is_n >= 150) & (d.h1_net > 0) & (d.h2_net > 0) & (d.h1_t > 1) & (d.h2_t > 1)].copy()
s["score"] = s[["h1_t", "h2_t"]].min(axis=1)
s = s.sort_values("score", ascending=False).head(300)
sigk = ["rsi_len", "fast_len", "min_aligned", "burst_atr", "entry_dist_atr", "atr_len", "use_zone_filter"]
exk = ["sl_atr", "sl_abs", "tp_r", "runner", "part_pct", "run_be", "run_atr", "run_abs", "use_trail", "act_atr", "act_abs",
       "dst_atr", "dst_abs", "valid_bars", "allow_rev", "exit_opp", "direction", "max_held"]
rows = []
for _, r in s.iterrows():
    sig = {k: (bool(r[k]) if k == "use_zone_filter" else (float(r[k]) if k in ("burst_atr", "entry_dist_atr") else int(r[k]))) for k in sigk}
    ex = {k: r[k] for k in exk}
    sg = E.make_signals(M1, int(r.tf), sig)
    row = dict(tf=int(r.tf), is_net=r.is_net)
    for sp in (2, 15, 30):
        st = E.stats(E.run(M1, int(r.tf), sig, ex, spread=sp, pess=True, signals=sg), M1["t"], IS_END, OOS_END)
        row[f"oos_net_{sp}"] = st["net"]; row[f"oos_pf_{sp}"] = st["pf"]
    rows.append(row)
o = pd.DataFrame(rows)
o.to_csv("../results/stress_top300.csv", index=False)
for sp in (2, 15, 30):
    print(f"spread ${sp}: held-out positive {100 * (o[f'oos_net_{sp}'] > 0).mean():.0f}% of 300, median PF {o[f'oos_pf_{sp}'].median():.2f}, median net {o[f'oos_net_{sp}'].median():.1f}%")
for n in (10, 30, 100):
    print(f"best {n} in-sample: held-out positive {100 * (o.head(n).oos_net_15 > 0).mean():.0f}%, mean net {o.head(n).oos_net_15.mean():.1f}%, median PF {o.head(n).oos_pf_15.median():.2f}")
