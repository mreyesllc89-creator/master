"""Cross-check one entry configuration on several symbols / timeframes at a given risk."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, run
S = sys.argv[1]
CASES = [  # symbol, comm, step, tf, signal (rsi, fast, slow, turnMax, hold, failExit), exits (sl, tpR, act, dist)
 ('XAUUSD-ECNc', 0.03, 1, '15min', (21, 2, 5, 6, 2, False), (2, 0, 1, 0.5)),
 ('XAUUSD-ECNc', 0.03, 1, '30min', (21, 2, 5, 6, 2, False), (2, 0, 1, 0.5)),
 ('XAUUSD-ECNc', 0.03, 1, '30min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('XAUUSD-ECNc', 0.03, 1, '60min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('XAUUSD-ECNc', 0.03, 1, '15min', (14, 2, 10, 12, 2, True), (2, 0, 1.5, 3)),
 ('XAUUSD-ECNc', 0.03, 1, '30min', (14, 2, 7, 12, 2, True), (3, 0, 1, 1.5)),
 ('BTCUSD.c', 3, 0.01, '15min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('BTCUSD.c', 3, 0.01, '30min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('BTCUSD.c', 3, 0.01, '30min', (21, 2, 5, 6, 2, False), (2, 0, 1, 0.5)),
 ('BTCUSD.c', 3, 0.01, '60min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('BTCUSD.c', 3, 0.01, '120min', (21, 2, 5, 6, 2, False), (3, 0, 1.5, 0.75)),
 ('BTCUSD.c', 3, 0.01, '30min', (14, 2, 10, 12, 2, True), (2, 0, 1.5, 3)),
]
cache = {}
for sym, comm, step, tf, sig, g in CASES:
    if sym not in cache: cache[sym] = pd.read_pickle(f'{S}/{sym}.pkl')
    df = cache[sym]
    D, b = build(df, tf, *sig[:5])
    r, p, eb, k = run(df, D, b, *g, comm, 0.01, turnHold=sig[4], failExit=sig[5])
    R = p / (g[0] * D['atr'][eb - 1]); nb = len(D['c']); sp = 60 + (nb - 60) * 6 // 10
    eq = 1e4; cu = [eq]; wk = {}
    for pi, si, e in zip(p, g[0] * D['atr'][eb - 1], eb):
        q = np.floor(eq * 0.005 / si / step) * step
        pnl = q * pi; eq += pnl; cu.append(eq)
        w = pd.Timestamp(D['t'][e]).strftime('%V'); wk[w] = wk.get(w, 0) + pnl
    cu = np.array(cu); dd = np.max(1 - cu / np.maximum.accumulate(cu)) * 100
    print('%-12s %-6s sig %-24s ex %-18s n=%3d win %2.0f%% exp %+.3fR  R train %+5.1f test %+5.1f | 0.5%% risk, rounded: %+6.2f%% dd %.2f%%  weeks + %d/%d'
          % (sym, tf, sig, g, len(R), 100 * np.mean(R > 0), R.mean(), R[eb < sp].sum(), R[eb >= sp].sum(), (eq / 1e4 - 1) * 100, dd, sum(v > 0 for v in wk.values()), len(wk)))
