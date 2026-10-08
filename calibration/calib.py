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
COST = dict(comm=0.05, slip=5.0, spread=1.0)
W = 60  # warm-up bars skipped
def run(tf):
    D = signals(indicators(load(files[tf])))
    n = len(D['c']); mid = W + (n - W) * 6 // 10
    R = float(np.median((D['h'] - D['l']) / D['c'])) * 100
    px = float(np.median(D['c']))
    # baseline: current script ($ values by TF bucket) at this price
    bk = {'1m': (150, 0), '15m': (1500, 25)}.get(tf, (2500, 200))
    base = dict(sl=bk[0]/px*100, tp=5000/px*100, act=bk[1]/px*100, dist=25/px*100)
    out = dict(tf=tf, R=R, n=n, px=px)
    out['base_nocost'] = stats(backtest(D, **base, comm=0, slip=0, spread=0, lo=W))
    out['base_oldcomm'] = stats(backtest(D, **base, comm=0.055, slip=0, spread=0, lo=W))
    out['base_cost'] = stats(backtest(D, **base, **COST, lo=W))
    out['base_cost_pess'] = stats(backtest(D, **base, **COST, lo=W, mode='pess'))
    res = []
    for sm, tm, am, dm in itertools.product([0.5, 1, 1.5, 2, 3, 4, 6, 10], [2, 4, 8, 16, 0], [0, 0.25, 0.5, 1, 1.5, 2, 3, 4], [0.25, 0.5, 0.75, 1, 1.5, 2, 3]):
        p = dict(sl=sm*R, tp=tm*R, act=am*R, dist=dm*R)
        a = stats(backtest(D, **p, **COST, lo=W, hi=mid, mode='pess'))
        b = stats(backtest(D, **p, **COST, lo=mid, mode='pess'))
        res.append((min(a['net'], b['net']), a['net'] + b['net'], (sm, tm, am, dm), a, b))
    res.sort(key=lambda x: (x[0], x[1]), reverse=True)
    sm, tm, am, dm = res[0][2]
    p = dict(sl=sm*R, tp=tm*R, act=am*R, dist=dm*R)
    out['best_mult'] = res[0][2]; out['best_pct'] = p
    out['best_train'] = res[0][3]; out['best_test'] = res[0][4]
    out['best_full_pess'] = stats(backtest(D, **p, **COST, lo=W, mode='pess'))
    out['best_full_tv'] = stats(backtest(D, **p, **COST, lo=W))
    out['best_full_nocost'] = stats(backtest(D, **p, comm=0, slip=0, spread=0, lo=W))
    out['best_fut'] = stats(backtest(D, **p, comm=0.02, slip=5, spread=1, lo=W, mode='pess'))
    out['best_slip20'] = stats(backtest(D, **p, comm=0.05, slip=20, spread=2, lo=W, mode='pess'))
    out['top5'] = [(r[2], round(r[0], 2), round(r[1], 2)) for r in res[:5]]
    # no-trade alternative check: fraction of grid profitable in both halves
    out['grid_both_pos'] = float(np.mean([r[0] > 0 for r in res]))
    return out
if __name__ == '__main__':
    with Pool() as pool:
        outs = pool.map(run, list(files))
    json.dump(outs, open(sys.argv[3], 'w'), default=float, indent=1)
    for o in outs:
        print(o['tf'], 'R%.3f' % o['R'], 'mult', o['best_mult'], {k: round(v, 3) for k, v in o['best_pct'].items()}, 'bothpos%.2f' % o['grid_both_pos'])
        for k in ['base_nocost', 'base_oldcomm', 'base_cost', 'base_cost_pess', 'best_train', 'best_test', 'best_full_pess', 'best_full_tv', 'best_full_nocost', 'best_fut', 'best_slip20']:
            s = o[k]; print('   %-16s n=%3d net=%7.2f%% pf=%5.2f win=%4.1f avg=%.3f%%' % (k, s['n'], s['net'], min(s['pf'], 99), s['win'], s['avg']))
