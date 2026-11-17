"""Tight-stop check at 1-second resolution (Binance spot, 2025-11 .. 2026-10), chart H1.
Part 1: the EA's default settings under several spreads, worst-case and best-case entry second.
Part 2: a grid of tight exits, scored on the first 8 months and on the last 4 months separately."""
import itertools
import sys

import numpy as np
import pandas as pd

import engine as E

S1 = E.load("../data/BTCUSDT_spot_1s.npz")
T = lambda d: int(pd.Timestamp(d, tz="UTC").timestamp())
A0, A1, B1 = T("2025-11-01"), T("2026-07-01"), T("2026-11-01")
sig = E.make_signals(S1, 60, E.SIG_DEFAULT, bpm=60)
print("H1 signals in 12 months:", int(sig["buy"].sum()), "buy,", int(sig["sell"].sum()), "sell")

print("\nPART 1  EA defaults (SL 30 pips, 30% at 5R, runner trail 600 pips, breakeven)")
rows = []
for sp in (0, 2, 5, 10, 15, 30):
    for pess in (True, False):
        r = E.run(S1, 60, E.SIG_DEFAULT, {}, spread=sp, pess=pess, signals=sig, bpm=60)
        st = E.stats(r, S1["t"])
        rows.append(dict(spread=sp, entry_second="worst" if pess else "best", trades=st["n"], net_pct=round(st["net"], 1),
                         pf=round(st["pf"], 2), win_pct=round(st["win"], 1), max_dd_pct=round(st["dd"], 1), t=round(st["t"], 2)))
d1 = pd.DataFrame(rows)
print(d1.to_string(index=False))
d1.to_csv("../results/tight_defaults_1s.csv", index=False)

print("\nPART 2  tight exits grid (worst-case entry second)")
rows = []
for sp in (2, 15):
    for sl, tpr, style in itertools.product((20, 30, 50, 75, 100, 150, 250), (2, 3, 5, 8), ("fixed", "runner600", "runner1500")):
        ex = dict(sl_abs=sl, sl_atr=0, tp_r=tpr, runner=style != "fixed", part_pct=0.3, run_be=True,
                  run_abs=600 if style == "runner600" else 1500)
        r = E.run(S1, 60, E.SIG_DEFAULT, ex, spread=sp, pess=True, signals=sig, bpm=60)
        a, b = E.stats(r, S1["t"], A0, A1), E.stats(r, S1["t"], A1, B1)
        rows.append(dict(spread=sp, sl_pips=sl, tp_r=tpr, style=style, n_a=a["n"], net_a=round(a["net"], 1), pf_a=round(a["pf"], 2),
                         n_b=b["n"], net_b=round(b["net"], 1), pf_b=round(b["pf"], 2)))
d2 = pd.DataFrame(rows)
d2.to_csv("../results/tight_grid_1s.csv", index=False)
for sp, g in d2.groupby("spread"):
    print(f"spread ${sp}: {len(g)} settings, positive in first 8 months: {(g.net_a > 0).sum()}, in last 4 months: {(g.net_b > 0).sum()}, in both: {((g.net_a > 0) & (g.net_b > 0)).sum()}")
    print(g.sort_values("net_a", ascending=False).head(8).to_string(index=False))
