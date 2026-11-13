"""Stress test of the candidate 15m settings (exits on 1-minute bars)."""
import numpy as np, pandas as pd
from opt15_final import run, BASE, line, ts, H
L42 = dict(BASE, levels="42/58")
FIN = {
 "P0 current default (levels off, 5xATR60 TP2R)": (BASE, ("atr", 60, 5, 2, None)),
 "P1 levels 42/58, 5xATR(60m) TP2R": (L42, ("atr", 60, 5, 2, None)),
 "P2 levels 42/58, 8xATR(60m) TP3R": (L42, ("atr", 60, 8, 3, None)),
 "P3 levels 42/58, 5xATR(240m) TP2R": (L42, ("atr", 240, 5, 2, None)),
 "P4 levels 45/55, 5xATR(60m) TP2R": (dict(BASE, levels="45/55"), ("atr", 60, 5, 2, None)),
}
if __name__ == "__main__":
    rng = np.random.default_rng(2)
    for name, (cfg, ex) in FIN.items():
        r, t, sd, L, S, ch = run(cfg, ex)
        print(f"\n== {name} ==\n  all  :", line(r)); print("  year1:", line(r[t < H])); print("  year2:", line(r[t >= H]))
        print("  long :", line(r[sd > 0])); print("  short:", line(r[sd < 0]))
        q = pd.Series(r).groupby(t.tz_convert(None).to_period("Q").astype(str)).sum()
        m = pd.Series(r).groupby(t.tz_convert(None).to_period("M").astype(str)).sum()
        print("  quarterly sum bp:", " ".join(f"{k}:{v:+.0f}" for k, v in q.items()), f"| quarters + {(q>0).sum()}/{len(q)}, months + {(m>0).sum()}/{len(m)}")
        eq = np.cumsum(r); print(f"  max drawdown {(np.maximum.accumulate(eq)-eq).max():.0f}bp, worst trade {r.min():.0f}bp, total {r.sum():+.0f}bp | fees 0%: {run(cfg, ex, comm=0)[0].mean():+.1f}  0.05%: {run(cfg, ex, comm=0.0005)[0].mean():+.1f}  0.10%: {run(cfg, ex, comm=0.001)[0].mean():+.1f}")
        n = len(ch); rnd = []
        for _ in range(200):
            rL = np.zeros(n, bool); rS = np.zeros(n, bool)
            rL[rng.choice(n, L.sum(), replace=False)] = True; rS[rng.choice(n, S.sum(), replace=False)] = True
            rnd.append(run(cfg, ex, L=rL, S=rS)[0].mean())
        rnd = np.array(rnd); print(f"  random entries: avg {rnd.mean():+.1f}bp, best {rnd.max():+.1f}bp, beat real {100*(rnd>=r.mean()).mean():.1f}%")
    print("\n== P1 with one input changed (all | year1 | year2 avg bp, trades) ==")
    ex = ("atr", 60, 5, 2, None)
    for nm, c in [("pivot 3", dict(divL=3, divR=3)), ("pivot 4", dict(divL=4, divR=4)), ("pivot 5 (pick)", {}), ("pivot 6", dict(divL=6, divR=6)), ("pivot 8", dict(divL=8, divR=8)),
                  ("swing 10-120", dict(divMin=10, divMax=120)), ("levels 38/62", dict(levels="38/62")), ("levels 45/55", dict(levels="45/55")), ("levels off", dict(levels="off")),
                  ("day 00", dict(dayH=0)), ("day 08", dict(dayH=8)), ("day 12", dict(dayH=12)), ("day 14", dict(dayH=14)), ("day 20", dict(dayH=20))]:
        r, t, *_ = run(dict(L42, **c), ex); print(f"  {nm:15s} {r.mean():+6.1f} | {r[t<H].mean():+6.1f} | {r[t>=H].mean():+6.1f}   ({len(r)})")
