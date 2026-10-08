import sys, glob, itertools, json, numpy as np
from multiprocessing import Pool
sys.path.insert(0, sys.argv[1])
from xpw import *
TF = {'1_8': '1m', '15_': '15m', '30_': '30m', '60_': '60m', '120': '2h', '180': '3h', '240': '4h', '1D_': '1D', '1W_2': '1W'}
files = {}
for p in sorted(glob.glob(sys.argv[2] + '/*.csv')):
    tag = p.split('/')[-1][14:]
    for k, v in TF.items():
        if tag.startswith(k): files[v] = p
COST = dict(comm=0.05, slip=5.0, spread=1.0); W = 60
DS = {tf: signals(indicators(load(f))) for tf, f in files.items()}
GRID = list(itertools.product([1, 1.5, 2, 3, 4, 6, 8], [0, 1.5, 2, 3, 4, 6], [0, 0.5, 1, 1.5, 2, 3], [0.25, 0.5, 0.75, 1, 1.5, 2]))
def ev(args):
    tf, g = args; D = DS[tf]; n = len(D['c']); mid = W + (n - W) * 6 // 10
    R = float(np.nanmedian(D['atr'] / D['c'])) * 100
    sl, tpR, act, dist = g
    a = stats(backtest(D, sl, tpR, act, dist, **COST, lo=W, hi=mid, mode='pess', atr=D['atr']))['net'] / R
    b = stats(backtest(D, sl, tpR, act, dist, **COST, lo=mid, mode='pess', atr=D['atr']))['net'] / R
    return tf, g, a, b
if __name__ == '__main__':
    HTF = ['60m', '2h', '3h', '4h', '1D', '1W']
    with Pool() as pool: rs = pool.map(ev, [(tf, g) for g in GRID for tf in files])
    tab = {}
    for tf, g, a, b in rs: tab.setdefault(g, {})[tf] = (a, b)
    def score(g, tfs): return sum(min(tab[g][t]) for t in tfs)
    for tfs in (HTF[1:], HTF):
        best = sorted(GRID, key=lambda g: score(g, tfs), reverse=True)[:8]
        print('joint on', tfs)
        for g in best: print('  ', g, round(score(g, tfs), 2), {t: tuple(round(x, 1) for x in tab[g][t]) for t in files})
    json.dump({str(g): v for g, v in tab.items()}, open('joint.json', 'w'))
