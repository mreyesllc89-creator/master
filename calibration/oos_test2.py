"""Out-of-sample test of the EA v1.20 presets on ticks that came after the sweep data.
usage: oos_test2.py <dir with SYMBOL.pkl>   (only trades entered after CUT[symbol] are counted)"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from oos_test import segments, run_seg
CUT = {'XAUUSD-ECNc': '2026-08-07 18:00', 'BTCUSD.c': '2026-08-13 18:00'}
# name, symbol, comm, step, tf, sig, unit, slMode, swingN, sl, act, dist, timeStop, sweep PF
PRESETS = [
 ('Gold M15',       'XAUUSD-ECNc', 0.03, 1,    '15min', (21, 2, 5, 6, 2, False),  'ATR14',   'unit',  0,  2,   1, 0.5,  0,  1.35),
 ('Gold M30 swing', 'XAUUSD-ECNc', 0.03, 1,    '30min', (10, 2, 10, 12, 2, True), 'ATR14',   'swing', 5,  0,   2, 2,    0,  1.71),
 ('Gold M15 time',  'XAUUSD-ECNc', 0.03, 1,    '15min', (21, 2, 5, 6, 1, False),  'ATR14',   'unit',  0,  1.5, 1, 0.75, 24, 1.29),
 ('Gold H1 swing',  'XAUUSD-ECNc', 0.03, 1,    '60min', (14, 3, 7, 24, 2, True),  'ATR14',   'swing', 20, 0,   0, 1.5,  0,  3.31),
 ('Gold M30',       'XAUUSD-ECNc', 0.03, 1,    '30min', (14, 2, 7, 12, 2, True),  'ATR14',   'unit',  0,  3,   1, 1.5,  0,  1.37),
 ('BTC H1 range',   'BTCUSD.c',    3,    0.01, '60min', (14, 2, 10, 6, 1, False), 'Range14', 'unit',  0,  1,   1, 2,    0,  2.28),
 ('BTC M30 ATR50',  'BTCUSD.c',    3,    0.01, '30min', (21, 2, 5, 6, 1, False),  'ATR50',   'unit',  0,  4,   2, 0.5,  0,  1.38),
 ('BTC M15 time',   'BTCUSD.c',    3,    0.01, '15min', (21, 2, 10, 6, 1, False), 'ATR14',   'unit',  0,  4,   0, 0,    24, 1.46),
 ('BTC M30',        'BTCUSD.c',    3,    0.01, '30min', (21, 2, 5, 6, 2, False),  'ATR14',   'unit',  0,  3, 1.5, 0.75, 0,  1.24),
]
if __name__ == '__main__':
    data = {s: pd.read_pickle(f'{sys.argv[1]}/{s}.pkl') for s in CUT}
    for name, sym, comm, step, tf, sig, un, slm, N, sl, act, dist, ts, pf0 in PRESETS:
        P, S, T = [], [], []
        for seg in segments(data[sym]):
            p, s, k, t = run_seg(seg, tf, sig, un, slm, N, sl, act, dist, ts, comm)
            P += list(p); S += list(s); T += t
        cut = np.datetime64(pd.Timestamp(CUT[sym]))
        m = np.array([np.datetime64(pd.Timestamp(x)) >= cut for x in T], bool)
        p, s = np.array(P)[m], np.array(S)[m]; T = [t for t, mm in zip(T, m) if mm]
        if len(p) == 0: print('%-15s no trades' % name); continue
        R = p / s
        eq = 1e4; cu = [eq]; wk = {}
        for pi, si, ti in zip(p, s, T):
            q = np.floor(eq * 0.005 / si / step) * step
            if q > 0: eq += q * pi; cu.append(eq); w = pd.Timestamp(ti).strftime('%G-W%V'); wk[w] = wk.get(w, 0) + q * pi
        cu = np.array(cu); dd = np.max(1 - cu / np.maximum.accumulate(cu)) * 100
        pf = R[R > 0].sum() / -R[R < 0].sum() if (R < 0).any() else 99
        print('%-15s sweep PF %.2f | NEW n=%3d win %2.0f%% PF %5.2f exp %+.3fR 0.5%%: %+6.2f%% DD %.2f%% weeks+ %d/%d %s'
              % (name, pf0, len(R), 100 * np.mean(R > 0), pf, R.mean(), (eq / 1e4 - 1) * 100, dd,
                 sum(v > 0 for v in wk.values()), len(wk), {w: round(v) for w, v in sorted(wk.items())}))
