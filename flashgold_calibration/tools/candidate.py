"""The low-spread candidate (SL 50 pips, 30% at 3R, runner trail 600 pips, breakeven) against the EA defaults,
on 1-second data, across spreads, and by quarter."""
import numpy as np
import pandas as pd

import engine as E

S1 = E.load("../data/BTCUSDT_spot_1s.npz")
sig = E.make_signals(S1, 60, E.SIG_DEFAULT, bpm=60)
T = lambda d: int(pd.Timestamp(d, tz="UTC").timestamp())
CAND = dict(sl_abs=50, tp_r=3, runner=True, part_pct=0.3, run_be=True, run_abs=600)
rows = []
for name, ex in (("default SL30 TP5R", {}), ("candidate SL50 TP3R", CAND)):
    for sp in (0, 2, 3, 5, 8, 10, 15):
        for pess in (True, False):
            st = E.stats(E.run(S1, 60, E.SIG_DEFAULT, ex, spread=sp, pess=pess, signals=sig, bpm=60), S1["t"])
            rows.append(dict(setting=name, spread=sp, entry_second="worst" if pess else "best", trades=st["n"], net_pct=round(st["net"], 1),
                             pf=round(st["pf"], 2), win_pct=round(st["win"], 1), max_dd_pct=round(st["dd"], 1), t=round(st["t"], 2)))
d = pd.DataFrame(rows)
d.to_csv("../results/candidate_spreads_1s.csv", index=False)
print(d.to_string(index=False))
print("\ncandidate by quarter, spread $2, worst-case entry second")
r = E.run(S1, 60, E.SIG_DEFAULT, CAND, spread=2, pess=True, signals=sig, bpm=60)
q = ["2025-11-01", "2026-02-01", "2026-05-01", "2026-08-01", "2026-11-01"]
for a, b in zip(q[:-1], q[1:]):
    st = E.stats(r, S1["t"], T(a), T(b))
    print(a, "->", b, f"trades {st['n']}, net {st['net']:.1f}%, PF {st['pf']:.2f}")
print("with a 0.02% per side commission on top of a $2 spread:", {k: round(v, 2) for k, v in E.stats(E.run(S1, 60, E.SIG_DEFAULT, CAND, spread=2, fee=0.0002, pess=True, signals=sig, bpm=60), S1["t"]).items()})
