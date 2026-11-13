"""2-year backtest (Nov 2024 - Nov 12 2026) of the v3.1 defaults. Settings were chosen on Apr-Oct 2026,
so Nov 2024 - Mar 2026 (17 months) and Nov 2026 are unseen data."""
import numpy as np, pandas as pd
from finalists import run, BASE, tstat
T0 = pd.Timestamp("2026-04-01", tz="UTC"); T1 = pd.Timestamp("2026-11-01", tz="UTC")
EX = ("atr", 60, 5, 2, None)
rng = np.random.default_rng(3)

def line(r):
    if len(r) < 2: return f"{len(r)} trades"
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    return f"{len(r):4d} tr  win {100*(r>0).mean():4.1f}%  avg {r.mean():+6.1f}bp  t {tstat(r):+5.2f}  PF {pf:4.2f}  sum {r.sum():+7.0f}bp"

def parts(ch, r, eb):
    t = ch.index[eb]; return t, t < T0, (t >= T0) & (t < T1), t >= T1

print("######## Defaults by chart and day start (SL 5xATR(60m), TP 2R, 0.02%/side) ########")
for chart in (1, 5, 15):
    for dh in (13, 0):
        cfg = dict(BASE, chart_tf=chart, dayH=dh)
        ch, L, S, r, eb, sd = run(cfg, EX); t, un, tu, nv = parts(ch, r, eb)
        print(f"\n== {chart}m chart, day start {dh:02d}:00 ==")
        print(" ALL 2 years          :", line(r))
        print(" unseen Nov24-Mar26   :", line(r[un]))
        print(" tuned  Apr-Oct 26    :", line(r[tu]))
        print(" unseen Nov 1-12 26   :", line(r[nv]))
        if dh == 13:
            print("  long (all):", line(r[sd > 0])); print("  short(all):", line(r[sd < 0]))
            print("  unseen long:", line(r[un & (sd > 0)])); print("  unseen short:", line(r[un & (sd < 0)]))
            m = pd.Series(r).groupby(t.tz_convert(None).to_period("M").astype(str)).sum()
            print(f"  months positive: {(m > 0).sum()}/{len(m)}"); print("  monthly sum bp:", " ".join(f"{k[2:]}:{v:+.0f}" for k, v in m.items()))
            eq = np.cumsum(r); print(f"  max drawdown {(np.maximum.accumulate(eq)-eq).max():.0f}bp;  no fees {run(cfg, EX, comm=0)[3].mean():+.1f}bp  0.05% fees {run(cfg, EX, comm=0.0005)[3].mean():+.1f}bp")
            n = len(ch); rnd = []
            for _ in range(200):
                rL = np.zeros(n, bool); rS = np.zeros(n, bool)
                rL[rng.choice(n, L.sum(), replace=False)] = True; rS[rng.choice(n, S.sum(), replace=False)] = True
                rnd.append(run(cfg, EX, rL, rS)[3].mean())
            rnd = np.array(rnd); print(f"  random entries: avg {rnd.mean():+.1f}bp; beat real {100*(rnd>=r.mean()).mean():.1f}%")

def cell(cfg, ex):
    ch, L, S, r, eb, sd = run(cfg, ex); t, un, tu, nv = parts(ch, r, eb)
    return f"{r.mean():+6.1f} ({len(r)}) | unseen {r[un].mean():+6.1f} ({un.sum()})"

print("\n######## 5m chart, day 13: stop/target grid  [all 2y avg bp (trades) | unseen Nov24-Mar26] ########")
for atf, ks in ((60, (1, 2, 3, 5, 8, 12)), (0, (2, 5, 8, 12))):
    for k in ks:
        print(f" {k:>2}xATR({'60m' if atf else 'chart'}):", "   ".join(f"TP{m}R {cell(dict(BASE, dayH=13), ('atr', atf, k, m, None))}" for m in (1, 2, 3)))
for p in (0.5, 1, 2):
    print(f" {p}% stop      :", "   ".join(f"TP{m}R {cell(dict(BASE, dayH=13), ('pct', 0, p, m, None))}" for m in (1, 2, 3)))
print(" v3.0 ticks 200/400 trail:", cell(dict(BASE, dayH=13), ("ticks", 0, 200, 2, (0.75, 0.25))))

print("\n######## 5m chart, default exits: other inputs one at a time ########")
for name, c in [("default (day13)", {}), ("pivot 3/3", dict(divL=3, divR=3)), ("pivot 8/8", dict(divL=8, divR=8)), ("swing 10-120", dict(divMin=10, divMax=120)),
                ("levels 38/62", dict(levels="38/62")), ("levels 45/55", dict(levels="45/55")), ("gated no1m", dict(tfs="no1m", fix=True)),
                ("gated 15-60", dict(tfs="15-60", fix=True)), ("4th signal", dict(req4=True))]:
    print(f" {name:16s}", cell(dict(BASE, dayH=13, **c), EX))
print(f" {'trail 1R/0.5R':16s}", cell(dict(BASE, dayH=13), ("atr", 60, 5, 2, (1.0, 0.5))))

print("\n######## Day-start hour, 5m & 15m chart, default exits ########")
for dh in range(24):
    print(f" {dh:02d}:00  5m {cell(dict(BASE, dayH=dh), EX)}    15m {cell(dict(BASE, chart_tf=15, dayH=dh), EX)}")
