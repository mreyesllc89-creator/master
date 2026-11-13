"""Finalist check for the 15m optimisation: exits re-simulated on 1-minute bars ('bar magnifier') so the
intrabar path is real data instead of the open->high/low->close assumption; plus fees, sides, halves."""
import numpy as np, pandas as pd
from engine import *
import opt15
df = load_1m(); opt15.df = df
o1, h1, l1, c1 = (df[k].to_numpy() for k in "ohlc")
t1 = df.index.values.astype("int64")
H = pd.Timestamp("2025-11-01", tz="UTC")
BASE = dict(divL=5, divR=5, divMin=5, divMax=60, dayH=13, div="RB", req4=False, levels="off", tfs="all", fix=False)

def dists(ch, ex):
    mode, atf, x, m, tr = ex
    base = atr_on_chart(df, ch, 15, atf, 14) * x if mode == "atr" else ch.c.to_numpy() * x / 100
    ut = tr is not None
    return base, base * m, (base * tr[0] if ut else base * 0), (base * tr[1] if ut else base * 0), ut

def run(cfg, ex, comm=0.0002, magnify=True, L=None, S=None):
    ch, L0, S0 = opt15.make_signals(cfg)
    L = L0 if L is None else L; S = S0 if S is None else S
    sl, tp, a, f, ut = dists(ch, ex)
    if not magnify:
        o, h, l, c = (ch[k].to_numpy() for k in "ohlc")
        r, eb, sd = simulate_d(o, h, l, c, L, S, sl, tp, a, f, ut, True, comm)
        return r, ch.index[eb], sd, L0, S0, ch
    # place each 15m signal on the 1m bar that closes the 15m bar; next 1m open == next 15m open
    pos = np.searchsorted(t1, ch.index.values.astype("int64") + 15 * 60_000_000_000) - 1
    n1 = len(o1); L1 = np.zeros(n1, bool); S1 = np.zeros(n1, bool)
    A = [np.full(n1, np.nan) for _ in range(4)]
    L1[pos[L]] = True; S1[pos[S]] = True
    for arr, src in zip(A, (sl, tp, a, f)): arr[pos] = src
    r, eb, sd = simulate_d(o1, h1, l1, c1, L1, S1, A[0], A[1], A[2], A[3], ut, True, comm)
    return r, df.index[eb], sd, L0, S0, ch

def ts(r): return r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else np.nan
def line(r):
    pf = r[r > 0].sum() / -r[r < 0].sum()
    return f"{len(r):4d} tr win {100*(r>0).mean():4.1f}% avg {r.mean():+6.1f}bp t {ts(r):+5.2f} PF {pf:4.2f}"

FIN = {
 "S1 scalp: 1xATR(chart) TP4R trail .5/.25 (sweep #1 ungated)": (BASE, ("atr", 0, 1, 4, (0.5, 0.25))),
 "S2 scalp: 1xATR(chart) TP2R trail .5/.25": (BASE, ("atr", 0, 1, 2, (0.5, 0.25))),
 "S3 scalp: 1.5xATR(chart) TP3R trail .5/.25": (BASE, ("atr", 0, 1.5, 3, (0.5, 0.25))),
 "S4 scalp, day 00": (dict(BASE, dayH=0), ("atr", 0, 1, 4, (0.5, 0.25))),
 "W1 wide (current default): 5xATR(60m) TP2R": (BASE, ("atr", 60, 5, 2, None)),
 "W2 wide: 5xATR(240m) TP3R": (BASE, ("atr", 240, 5, 3, None)),
 "W3 wide: 12xATR(60m) TP2R": (BASE, ("atr", 60, 12, 2, None)),
 "W4 wide + levels 45/55: 5xATR(60m) TP2R": (dict(BASE, levels="45/55"), ("atr", 60, 5, 2, None)),
}
if __name__ == "__main__":
    rng = np.random.default_rng(1)
    for name, (cfg, ex) in FIN.items():
        print(f"\n== {name} ==")
        r0 = run(cfg, ex, magnify=False)[0]; print("  15m-bar path (as in sweep / TradingView default):", line(r0))
        r, t, sd, L, S, ch = run(cfg, ex); print("  1m-bar exits (realistic)                        :", line(r))
        print("    year 1 (Nov24-Oct25):", line(r[t < H])); print("    year 2 (Nov25-Nov26):", line(r[t >= H]))
        print("    long :", line(r[sd > 0])); print("    short:", line(r[sd < 0]))
        q = pd.Series(r).groupby(t.tz_convert(None).to_period("Q").astype(str)).sum()
        print("    quarterly sum bp:", " ".join(f"{k}:{v:+.0f}" for k, v in q.items()), f"| positive {(q>0).sum()}/{len(q)}")
        eq = np.cumsum(r); print(f"    max drawdown {(np.maximum.accumulate(eq)-eq).max():.0f}bp | avg bp at fees 0%: {run(cfg, ex, comm=0)[0].mean():+.1f}  0.02%: {r.mean():+.1f}  0.04%: {run(cfg, ex, comm=0.0004)[0].mean():+.1f}  0.05%: {run(cfg, ex, comm=0.0005)[0].mean():+.1f}")
        n = len(ch); rnd = []
        for _ in range(100):
            rL = np.zeros(n, bool); rS = np.zeros(n, bool)
            rL[rng.choice(n, L.sum(), replace=False)] = True; rS[rng.choice(n, S.sum(), replace=False)] = True
            rnd.append(run(cfg, ex, L=rL, S=rS)[0].mean())
        rnd = np.array(rnd); print(f"    random entries (1m exits): avg {rnd.mean():+.1f}bp, beat real {100*(rnd>=r.mean()).mean():.0f}%")
