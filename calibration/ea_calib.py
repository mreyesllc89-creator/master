"""Full EA calibration on MT5 ticks: entry settings + timeframe, then exits, then risk sizing.
usage: ea_calib.py <SYMBOL.pkl> <comm/unit/side> <qty step> <tf,tf,...> <out.json>"""
import sys, itertools, json, numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, run
from xpw import indicators, signals
path, COMM, STEP, TFS, OUT = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4].split(','), sys.argv[5]
DF = pd.read_pickle(path)
BASE = {}
for tf in TFS:
    D, b = build(DF, tf)
    BASE[tf] = (D, b)
SIG = list(itertools.product([10, 14, 21], [2, 3], [5, 7, 10], [6, 12, 24], [1, 2, 3], [True, False]))
EX1 = [(3, 0, 1, 1.5), (6, 0, 3, 1.5), (2, 0, 0.5, 1), (4, 0, 2, 2)]
def mk(tf, s):
    rsiLen, fastLen, slowLen, turnMax, turnHold, fe = s
    D0, b = BASE[tf]
    D = {k: D0[k] for k in ('t', 'o', 'h', 'l', 'c', 'fastx', 'slowx', 'xpx')}
    D = signals(indicators(D, rsiLen, fastLen, slowLen), turnMax=turnMax, turnHold=turnHold)
    return D, b
def ev(D, b, s, g):
    r, p, eb, k = run(DF, D, b, *g, COMM, 0.01, turnHold=s[4], failExit=s[5])
    nb = len(D['c']); sp = 60 + (nb - 60) * 6 // 10
    R = p / (g[0] * D['atr'][eb - 1])      # result in R = multiples of the stop-loss distance
    return R, p, eb, k, sp
def stage1(args):
    tf, s = args
    D, b = mk(tf, s)
    sc = []; n = 0
    for g in EX1:
        r, p, eb, k, sp = ev(D, b, s, g)
        sc.append(min(r[eb < sp].sum(), r[eb >= sp].sum())); n = len(r)
    return tf, s, float(np.median(sc)), float(np.min(sc)), n
SL = [1, 1.5, 2, 3, 4, 6, 8]; ACT = [0, 0.5, 1, 1.5, 2, 3]; DIS = [0.5, 0.75, 1, 1.5, 2, 3]
def stage2(args):
    tf, s, g = args
    D, b = mk(tf, s)
    r, p, eb, k, sp = ev(D, b, s, g)
    return g, min(r[eb < sp].sum(), r[eb >= sp].sum()), r.sum(), len(r)
def sizing(D, b, s, g, risk, rnd):
    r, p, eb, k, sp = ev(D, b, s, g)
    sld = g[0] * D['atr'][eb - 1]
    eq = 10000.0; cur = [eq]; rr = []
    for pi, si in zip(p, sld):
        q = eq * risk / 100 / si
        if rnd: q = np.floor(q / STEP) * STEP
        if q <= 0: continue
        pnl = q * pi; rr.append(pnl / eq * 100); eq += pnl; cur.append(eq)
    cu = np.array(cur); rr = np.array(rr)
    ls = m = 0
    for x in rr: m = m + 1 if x < 0 else 0; ls = max(ls, m)
    gp = rr[rr > 0].sum(); gl = -rr[rr < 0].sum()
    return dict(risk=risk, rounded=rnd, trades=len(rr), ret=(eq / 1e4 - 1) * 100, maxdd=float(np.max(1 - cu / np.maximum.accumulate(cu)) * 100),
                win=float(np.mean(rr > 0) * 100), pf=float(gp / gl) if gl else 99.0, avgwin=float(rr[rr > 0].mean()) if gp else 0, avgloss=float(rr[rr < 0].mean()) if gl else 0,
                streak=ls, exits={nm: int((k == v).sum()) for nm, v in [('SL', 1), ('trail', 2), ('TP', 3), ('cross failed', 4), ('reversed', 5)]},
                train=float(r[eb < sp].sum()), test=float(r[eb >= sp].sum()), expR=float(r.mean()), totR=float(r.sum()))
if __name__ == '__main__':
    with Pool(4) as pool:
        s1 = pool.map(stage1, [(tf, s) for tf in TFS for s in SIG], chunksize=8)
        s1 = [x for x in s1 if x[4] >= 25]
        s1.sort(key=lambda x: (x[3], x[2]), reverse=True)
        print('stage 1 (tf, rsi, fast, slow, turnMax, hold, failExit) median / worst min(train,test) R over 4 exit sets, trades')
        for x in s1[:10]: print('  ', x)
        default = next((x for x in s1 if x[1] == (14, 2, 7, 12, 2, True)), None)
        results = []
        for tf, s, med, mn, n in s1[:3]:
            grid = list(itertools.product(SL, [0], ACT, DIS))
            r2 = pool.map(stage2, [(tf, s, g) for g in grid])
            tab = {g: sc for g, sc, net, n in r2}
            def smooth(g):
                i, j, kk = SL.index(g[0]), ACT.index(g[2]), DIS.index(g[3])
                nb = [tab[(SL[a], 0, ACT[c], DIS[d])] for a in range(max(i-1,0), min(i+2,len(SL))) for c in range(max(j-1,0), min(j+2,len(ACT))) for d in range(max(kk-1,0), min(kk+2,len(DIS)))]
                return float(np.mean(nb)), float(np.mean([v > 0 for v in nb]))
            best = max(grid, key=lambda g: smooth(g)[0])
            D, b = mk(tf, s)
            sz = [sizing(D, b, s, best, rk, rnd) for rk in (0.25, 0.5, 0.75, 1.0, 1.5) for rnd in (True, False)]
            results.append(dict(tf=tf, sig=s, s1=med, exits=best, smooth=smooth(best), grid_pos=float(np.mean([v > 0 for v in tab.values()])), sizing=sz))
            print('\n', tf, 'sig', s, 'exits', best, 'neighbour mean %.2f, neighbours positive %.0f%%, grid positive %.0f%%' % (smooth(best)[0], 100 * smooth(best)[1], 100 * results[-1]['grid_pos']))
            for z in sz: print('   risk %.2f%% %-7s n=%d ret %+.2f%% dd %.2f%% win %.0f%% pf %.2f avgW %+.2f avgL %+.2f streak %d R train %+.1f test %+.1f exp %+.3fR %s' % (z['risk'], 'rounded' if z['rounded'] else 'exact', z['trades'], z['ret'], z['maxdd'], z['win'], z['pf'], z['avgwin'], z['avgloss'], z['streak'], z['train'], z['test'], z['expR'], z['exits']))
        if default:
            print('\n current default signal settings rank: %d / %d  %s' % (s1.index(default) + 1, len(s1), default))
    json.dump(dict(top=s1[:30], results=results), open(OUT, 'w'), default=str, indent=1)
