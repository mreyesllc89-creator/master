"""Every EA preset over all tick data merged, broken down by month.  usage: full_period.py <pkl dirs...>"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from oos_test import segments, run_seg
from oos_test2 import PRESETS
data = {}
for sym in ('XAUUSD-ECNc', 'BTCUSD.c'):
    df = pd.concat([pd.read_pickle(f'{d}/{sym}.pkl') for d in sys.argv[1:]]).drop_duplicates('ts').sort_values('ts').reset_index(drop=True)
    data[sym] = df
    print(sym, df['ts'].iloc[0], '->', df['ts'].iloc[-1], 'segments', len(segments(df)))
for name, sym, comm, step, tf, sig, un, slm, N, sl, act, dist, ts, pf0 in PRESETS:
    P, S, T = [], [], []
    for seg in segments(data[sym]):
        p, s, k, t = run_seg(seg, tf, sig, un, slm, N, sl, act, dist, ts, comm)
        P += list(p); S += list(s); T += t
    o = np.argsort(np.array(T, dtype='datetime64[ns]')); p = np.array(P)[o]; s = np.array(S)[o]; T = [T[i] for i in o]
    R = p / s; mon = np.array([pd.Timestamp(t).strftime('%b') for t in T])
    pf = lambda x: x[x > 0].sum() / -x[x < 0].sum() if (x < 0).any() else 99
    eq = 1e4; cu = [eq]
    for pi, si in zip(p, s):
        q = np.floor(eq * 0.005 / si / step) * step
        if q > 0: eq += q * pi; cu.append(eq)
    cu = np.array(cu); dd = np.max(1 - cu / np.maximum.accumulate(cu)) * 100
    months = ' '.join('%s %.2f(%d)' % (m, pf(R[mon == m]), (mon == m).sum()) for m in ['Jul', 'Aug', 'Sep', 'Oct'] if (mon == m).any())
    print('%-15s n=%3d win %2.0f%% PF %.2f exp %+.3fR | 0.5%%: %+6.1f%% DD %4.1f%% | by month PF(trades): %s'
          % (name, len(R), 100 * np.mean(R > 0), pf(R), R.mean(), (eq / 1e4 - 1) * 100, dd, months))
