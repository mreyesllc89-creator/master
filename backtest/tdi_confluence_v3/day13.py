"""v3.1 with day start 13:00 UTC as default: full-period stats + fresh Nov 1-12 data (never used for tuning)."""
import numpy as np, pandas as pd
from finalists import run, BASE, tstat
NOV = pd.Timestamp("2026-11-01", tz="UTC")
EX = ("atr", 60, 5, 2, None)
rng = np.random.default_rng(5)

def line(r):
    if len(r) == 0: return "0 trades"
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    return f"{len(r):4d} tr  win {100*(r>0).mean():4.1f}%  avg {r.mean():+6.1f}bp  t {tstat(r):+5.2f}  PF {pf:4.2f}  sum {r.sum():+7.0f}bp"

for chart in (1, 5, 15):
    for dh in (13, 0):
        cfg = dict(BASE, chart_tf=chart, dayH=dh)
        ch, L, S, r, eb, sd = run(cfg, EX)
        t = ch.index[eb]; old = t < NOV
        print(f"\n== {chart}m chart, day start {dh:02d}:00, SL 5xATR(60m) TP 2R, 0.02%/side ==")
        print(" Apr-Oct :", line(r[old])); print(" Nov 1-12:", line(r[~old]))
        if dh == 13:
            print("  long :", line(r[sd > 0])); print("  short:", line(r[sd < 0]))
            m = pd.Series(r).groupby(t.tz_convert(None).to_period("M").astype(str)).agg(["size", "sum"])
            print("  monthly sum bp:", "  ".join(f"{k[5:]}:{v['sum']:+.0f}({int(v['size'])})" for k, v in m.iterrows()))
            eq = np.cumsum(r); print(f"  max drawdown {(np.maximum.accumulate(eq)-eq).max():.0f}bp of notional;  fees 0%: {run(cfg, EX, comm=0)[3].mean():+.1f}bp  0.05%: {run(cfg, EX, comm=0.0005)[3].mean():+.1f}bp")
            n = len(ch); rnd = []
            for _ in range(300):
                rL = np.zeros(n, bool); rS = np.zeros(n, bool)
                rL[rng.choice(n, L.sum(), replace=False)] = True; rS[rng.choice(n, S.sum(), replace=False)] = True
                rnd.append(run(cfg, EX, rL, rS)[3].mean())
            rnd = np.array(rnd); print(f"  random entries: avg {rnd.mean():+.1f}bp, beat real {100*(rnd>=r.mean()).mean():.1f}% of the time")

print("\n== 5m chart, day 13:00: stop/target neighbourhood, avg bp | trades (all data incl. Nov) ==")
tab = {}
for atf, ks in ((60, (2, 3, 4, 5, 6, 8)), (0, (5, 8, 12))):
    for k in ks:
        for m in (1, 1.5, 2, 3):
            r = run(dict(BASE, dayH=13), ("atr", atf, k, m, None))[3]
            tab[(f"{k}xATR({'60m' if atf else 'chart'})", f"TP{m}R")] = f"{r.mean():+.1f} | {len(r)}"
print(pd.Series(tab).unstack().to_string())

print("\n== 5m chart, day 13:00, default exits: other inputs one at a time (all data) ==")
for name, ch_ in [("default", {}), ("pivot 3/3", dict(divL=3, divR=3)), ("pivot 8/8", dict(divL=8, divR=8)), ("swing 10-120", dict(divMin=10, divMax=120)),
                  ("div RB+RR", dict(div="RB+RR")), ("div all4", dict(div="all4")), ("levels 38/62", dict(levels="38/62")), ("levels 45/55", dict(levels="45/55")),
                  ("levels 30/70", dict(levels="30/70")), ("4th signal on", dict(req4=True)), ("gated no1m", dict(tfs="no1m", fix=True)),
                  ("gated 15-60", dict(tfs="15-60", fix=True)), ("trail 1R/0.5R", None)]:
    ex = ("atr", 60, 5, 2, (1.0, 0.5)) if ch_ is None else EX
    r = run(dict(BASE, dayH=13, **(ch_ or {})), ex)[3]
    print(f" {name:14s}", line(r))
