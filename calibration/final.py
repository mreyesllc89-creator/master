import sys, glob, numpy as np
sys.path.insert(0, sys.argv[1])
from xpw import *
TF = {'1_8': '1m', '15_': '15m', '30_': '30m', '60_': '60m', '120': '2h', '180': '3h', '240': '4h', '1D_': '1D', '1W_2': '1W'}
W = 60
def dd(tr):
    eq = np.cumsum([t[0] for t in tr]); return float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq])) if tr else 0
for p in sorted(glob.glob(sys.argv[2] + '/*.csv')):
    tag = p.split('/')[-1][14:]; tf = next((v for k, v in TF.items() if tag.startswith(k)), None)
    if not tf: continue
    D = signals(indicators(load(p)))
    row = [tf, D['t'][W][:10], D['t'][-1][:10]]
    for name, kw in [('nocost', dict(comm=0, slip=0, spread=0)), ('mexc spot', dict(comm=0.05, slip=5, spread=1)), ('mexc fut', dict(comm=0.02, slip=5, spread=1)), ('slip $20', dict(comm=0.05, slip=20, spread=2))]:
        tr = backtest(D, 6, 0, 3, 1.5, **kw, lo=W, mode='pess', atr=D['atr']); s = stats(tr)
        row.append('%s n=%d net=%+.1f%% pf=%.2f dd=%.1f%%' % (name, s['n'], s['net'], min(s['pf'], 99), dd(tr)))
    tr = backtest(D, 6, 0, 3, 1.5, comm=0.05, slip=5, spread=1, lo=W, mode='tv', atr=D['atr']); s = stats(tr)
    row.append('TVpath net=%+.1f%% pf=%.2f win=%.0f%%' % (s['net'], s['pf'], s['win']))
    print(' | '.join(row))
