"""Out-of-sample test of the EA presets on new MT5 ticks.  usage: oos_test.py <dir with SYMBOL.pkl>"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, engine2
from xpw import rma
# name, symbol, comm/side, lot step(units), tf, (rsi, fast, slow, turnMax, hold, failExit), unit, slMode, swingN, sl, act, dist, timeStop
PRESETS = [
 ('Gold M30',        'XAUUSD-ECNc', 0.03, 1,    '30min', (14, 2, 7, 12, 2, True),   'ATR14',   'unit',  0, 3,   1,   1.5,  0),
 ('Gold M15',        'XAUUSD-ECNc', 0.03, 1,    '15min', (21, 2, 5, 6, 2, False),   'ATR14',   'unit',  0, 2,   1,   0.5,  0),
 ('Gold M30 swing',  'XAUUSD-ECNc', 0.03, 1,    '30min', (10, 2, 10, 12, 2, True),  'ATR14',   'swing', 5, 0,   2,   2,    0),
 ('Gold M15 time',   'XAUUSD-ECNc', 0.03, 1,    '15min', (21, 2, 5, 6, 1, False),   'ATR14',   'unit',  0, 1.5, 1,   0.75, 24),
 ('BTC M30',         'BTCUSD.c',    3,    0.01, '30min', (21, 2, 5, 6, 2, False),   'ATR14',   'unit',  0, 3,   1.5, 0.75, 0),
 ('BTC M15 range',   'BTCUSD.c',    3,    0.01, '15min', (10, 3, 7, 6, 1, False),   'Range14', 'unit',  0, 4,   2,   0.5,  0),
 ('BTC M30 ATR50',   'BTCUSD.c',    3,    0.01, '30min', (21, 2, 5, 6, 1, False),   'ATR50',   'unit',  0, 4,   2,   0.5,  0),
]
CAL = {'Gold M30': (72, 32, 1.78), 'Gold M15': (192, 61, 1.44), 'Gold M30 swing': (68, 31, 1.55), 'Gold M15 time': (206, 56, 1.36),
       'BTC M30': (146, 58, 1.39), 'BTC M15 range': (127, 65, 1.52), 'BTC M30 ATR50': (140, 56, 1.49)}

def segments(df, gap='3D'):
    cut = np.where(df['ts'].diff() > pd.Timedelta(gap))[0]
    edges = [0, *cut, len(df)]
    return [df.iloc[a:b].reset_index(drop=True) for a, b in zip(edges[:-1], edges[1:])]

def run_seg(df, tf, sig, unitName, slMode, N, sl, act, dist, ts, comm):
    D, b = build(df, tf, *sig[:5])
    h, l, c, atr = D['h'], D['l'], D['c'], D['atr']
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))
    raw = {'ATR14': atr, 'ATR50': rma(tr, 50), 'Range14': pd.Series(h - l).rolling(14).mean().values}[unitName]
    raw = np.where(np.isnan(raw), atr, raw)
    u = raw * np.nanmedian(atr) / np.nanmedian(raw)
    if slMode == 'swing':
        x = np.where(np.isnan(D['xpxc']), c, D['xpxc'])
        ll = pd.Series(l).rolling(N).min().values; hh = pd.Series(h).rolling(N).max().values
        slL = np.maximum(x - ll + 0.1 * atr, 0.3 * atr); slS = np.maximum(hh - x + 0.1 * atr, 0.3 * atr); u = atr
    else:
        slL = slS = sl * u
    z = np.zeros(len(c), bool)
    p, s, eb, k = engine2(df['bid'].values, df['ask'].values, b, D['wantL'], D['wantS'], D['xpxc'], D['fast'], D['slow'],
                          u, slL, slS, z, z, 0.01, 0, act, dist, comm, sig[4], sig[5], ts, 60)
    t = [D['t'][e] for e in eb]
    return p, s, k, t

if __name__ == '__main__':
    data = {s: pd.read_pickle(f'{sys.argv[1]}/{s}.pkl') for s in ('XAUUSD-ECNc', 'BTCUSD.c')}
    print('%-15s | %-22s | %s' % ('preset', 'calibration (Jul-Aug)', 'OUT-OF-SAMPLE (Sep 1-15, Sep 28-Oct 8)'))
    for name, sym, comm, step, tf, sig, un, slm, N, sl, act, dist, ts in PRESETS:
        P, S, K, T = [], [], [], []
        for seg in segments(data[sym]):
            p, s, k, t = run_seg(seg, tf, sig, un, slm, N, sl, act, dist, ts, comm)
            P += list(p); S += list(s); K += list(k); T += t
        p, s, k = np.array(P), np.array(S), np.array(K); R = p / s
        eq = 1e4; cu = [eq]; wk = {}
        for pi, si, ti in zip(p, s, T):
            q = np.floor(eq * 0.005 / si / step) * step
            if q > 0:
                eq += q * pi; cu.append(eq); w = pd.Timestamp(ti).strftime('%G-W%V'); wk[w] = wk.get(w, 0) + q * pi
        cu = np.array(cu); dd = np.max(1 - cu / np.maximum.accumulate(cu)) * 100
        pf = R[R > 0].sum() / -R[R < 0].sum() if (R < 0).any() else 99
        c0 = CAL[name]
        print('%-15s | n=%3d win %2d%% PF %.2f    | n=%3d win %2.0f%% PF %.2f  exp %+.3fR  0.5%%: %+6.2f%% DD %.2f%%  weeks+ %d/%d  %s'
              % (name, c0[0], c0[1], c0[2], len(R), 100 * np.mean(R > 0), pf, R.mean(), (eq / 1e4 - 1) * 100, dd,
                 sum(v > 0 for v in wk.values()), len(wk), {w: round(v) for w, v in sorted(wk.items())}))
