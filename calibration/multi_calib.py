"""Multi-method calibration on MT5 ticks: every timeframe, several distance units, stop styles and exit rules.
usage: multi_calib.py <SYMBOL.pkl> <comm/unit/side> <qty step> <out.json>
Scores are in R (multiples of the stop-loss distance), min(first 60%, last 40%), smoothed over neighbouring settings."""
import sys, itertools, json, numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, engine2
from xpw import indicators, signals, rma, sma
path, COMM, STEP, OUT = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
DF = pd.read_pickle(path); BID = DF['bid'].values; ASK = DF['ask'].values
TFS = [('1min', '1m'), ('5min', '5m'), ('15min', '15m'), ('30min', '30m'), ('60min', '1h'), ('120min', '2h'), ('240min', '4h')]
BASE = {lab: build(DF, rule) for rule, lab in TFS}
DEFAULT = (14, 2, 7, 12, 2, True)
SIG = list(itertools.product([10, 14, 21], [2, 3], [5, 7, 10], [6, 12, 24], [1, 2], [True, False]))
UNITS = ['ATR14', 'ATR50', 'StdDev20', 'Range14', 'Percent', 'Fixed', 'Donchian20']
NOEXIT = None

def roll(x, n, f):
    s = pd.Series(x); return getattr(s.rolling(n), f)().values

def psar(h, l, af0=0.02, afmax=0.2):
    n = len(h); ps = np.full(n, np.nan); up = True; af = af0; ep = h[0]; ps[0] = l[0]
    for i in range(1, n):
        p = ps[i-1] + af * (ep - ps[i-1])
        if up:
            p = min(p, l[i-1], l[i-2] if i > 1 else l[i-1])
            if l[i] < p: up = False; p = ep; ep = l[i]; af = af0
            elif h[i] > ep: ep = h[i]; af = min(af + af0, afmax)
        else:
            p = max(p, h[i-1], h[i-2] if i > 1 else h[i-1])
            if h[i] > p: up = True; p = ep; ep = h[i]; af = af0
            elif l[i] < ep: ep = l[i]; af = min(af + af0, afmax)
        ps[i] = p
    return ps

def mk(lab, s):
    D0, b = BASE[lab]
    D = {k: D0[k] for k in ('t', 'o', 'h', 'l', 'c', 'fastx', 'slowx', 'xpx')}
    D = signals(indicators(D, *s[:3]), turnMax=s[3], turnHold=s[4])
    h, l, c = D['h'], D['l'], D['c']; atr = D['atr']; med = np.nanmedian(atr)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))
    raw = {'ATR14': atr, 'ATR50': rma(tr, 50), 'StdDev20': roll(c, 20, 'std'), 'Range14': roll(h - l, 14, 'mean'),
           'Percent': c.copy(), 'Fixed': np.ones_like(c), 'Donchian20': roll(h, 20, 'max') - roll(l, 20, 'min')}
    U = {}
    for k, v in raw.items():
        v = np.where(np.isnan(v), atr, v)
        U[k] = v * med / np.nanmedian(v)          # same median as ATR14, so multipliers compare
    ema = pd.Series(c).ewm(span=20, adjust=False).mean().values; ps = psar(h, l)
    EX = {'none': (np.zeros(len(c), bool), np.zeros(len(c), bool)),
          'TDI cross': (D['fast'] < D['slow'], D['fast'] > D['slow']),
          'EMA20 close': (c < ema, c > ema),
          'PSAR flip': (c < ps, c > ps)}
    SW = {}
    for N in (5, 10, 20):
        ll = roll(l, N, 'min'); hh = roll(h, N, 'max'); x = np.where(np.isnan(D['xpxc']), c, D['xpxc'])
        SW[N] = (np.maximum(x - ll + 0.1 * atr, 0.3 * atr), np.maximum(hh - x + 0.1 * atr, 0.3 * atr))
    return D, b, U, EX, SW

def run(D, b, s, unit, slL, slS, ex, tpR, act, dis, ts=0):
    p, sl, eb, k = engine2(BID, ASK, b, D['wantL'], D['wantS'], D['xpxc'], D['fast'], D['slow'], unit, slL, slS, ex[0], ex[1],
                          0.01, tpR, act, dis, COMM, s[4], s[5], ts, 60)
    nb = len(D['c']); sp = 60 + (nb - 60) * 6 // 10
    return p / sl, p, eb, k, sp

def score(R, eb, sp): return min(R[eb < sp].sum(), R[eb >= sp].sum())

def stage1(a):
    lab, s = a
    D, b, U, EX, SW = mk(lab, s); u = U['ATR14']; sc = []; n = 0
    for g in [(3, 1, 1.5), (6, 3, 1.5), (2, 0.5, 1), (4, 2, 2)]:
        R, p, eb, k, sp = run(D, b, s, u, g[0] * u, g[0] * u, EX['none'], 0, g[1], g[2]); sc.append(score(R, eb, sp)); n = len(R)
    return lab, s, float(min(sc)), float(np.median(sc)), n

SLG = [1, 1.5, 2, 3, 4]; ACT = [0, 0.5, 1, 2]; DIS = [0.5, 0.75, 1, 1.5, 2]
def stage2(a):
    lab, s, mode = a     # mode = ('unit', name) | ('swing', N) | ('exit', rule) | ('time', bars)
    D, b, U, EX, SW = mk(lab, s); res = {}
    if mode[0] == 'unit':
        u = U[mode[1]]
        for sm, am, dm in itertools.product(SLG, ACT, DIS):
            R, p, eb, k, sp = run(D, b, s, u, sm * u, sm * u, EX['none'], 0, am, dm); res[(sm, am, dm)] = (score(R, eb, sp), len(R))
    elif mode[0] == 'swing':
        u = U['ATR14']; slL, slS = SW[mode[1]]
        for am, dm in itertools.product(ACT, DIS):
            R, p, eb, k, sp = run(D, b, s, u, slL, slS, EX['none'], 0, am, dm); res[(mode[1], am, dm)] = (score(R, eb, sp), len(R))
    else:
        u = U['ATR14']; ex = EX[mode[1]] if mode[0] == 'exit' else EX['none']; ts = mode[1] if mode[0] == 'time' else 0
        for sm, am, dm in itertools.product([1.5, 2, 3, 4], [0, 1, 99], [0.75, 1.5]):   # act 99 = no trail
            R, p, eb, k, sp = run(D, b, s, u, sm * u, sm * u, ex, 0, am, dm, ts); res[(sm, am, dm)] = (score(R, eb, sp), len(R))
    keys = list(res)
    def smooth(key):
        nb = [res[k2][0] for k2 in keys if all(abs(i - j) <= 0.6 * max(abs(i), 1) for i, j in zip(key, k2))]
        return float(np.mean(nb))
    best = max(keys, key=smooth)
    return lab, s, mode, best, smooth(best), res[best][0], res[best][1], float(np.mean([v[0] > 0 for v in res.values()]))

def detail(lab, s, mode, g):
    D, b, U, EX, SW = mk(lab, s)
    if mode[0] == 'unit': u = U[mode[1]]; R, p, eb, k, sp = run(D, b, s, u, g[0] * u, g[0] * u, EX['none'], 0, g[1], g[2])
    elif mode[0] == 'swing': u = U['ATR14']; R, p, eb, k, sp = run(D, b, s, u, *SW[g[0]], EX['none'], 0, g[1], g[2])
    else:
        u = U['ATR14']; ex = EX[mode[1]] if mode[0] == 'exit' else EX['none']; ts = mode[1] if mode[0] == 'time' else 0
        R, p, eb, k, sp = run(D, b, s, u, g[0] * u, g[0] * u, ex, 0, g[1], g[2], ts)
    sld = p / R
    eq = 1e4; cu = [eq]
    for pi, si in zip(p, sld):
        q = np.floor(eq * 0.005 / si / STEP) * STEP
        if q > 0: eq += q * pi; cu.append(eq)
    cu = np.array(cu)
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else 99.0
    tr, te = R[eb < sp], R[eb >= sp]
    return dict(tf=lab, sig=s, mode=mode, exits=g, n=int(len(R)), win=float(np.mean(R > 0) * 100), pf=pf(R), pf_train=pf(tr), pf_test=pf(te),
                expR=float(R.mean()), R_train=float(tr.sum()), R_test=float(te.sum()), ret05=float((eq / 1e4 - 1) * 100),
                dd05=float(np.max(1 - cu / np.maximum.accumulate(cu)) * 100))

if __name__ == '__main__':
    out = {}
    with Pool(4) as pool:
        s1 = pool.map(stage1, [(lab, s) for _, lab in TFS for s in SIG], chunksize=4)
        tops = {}
        for _, lab in TFS:
            rows = sorted([x for x in s1 if x[0] == lab and x[4] >= 20], key=lambda x: (x[2], x[3]), reverse=True)
            tops[lab] = [r[1] for r in rows[:2]]
            print(lab, 'top entries', [(r[1], round(r[2], 2), r[4]) for r in rows[:2]], flush=True)
        jobs = []
        for _, lab in TFS:
            for s in tops[lab] + [DEFAULT]:
                for un in UNITS: jobs.append((lab, s, ('unit', un)))
                for N in (5, 10, 20): jobs.append((lab, s, ('swing', N)))
                for ex in ('TDI cross', 'EMA20 close', 'PSAR flip'): jobs.append((lab, s, ('exit', ex)))
                for tsb in (6, 12, 24): jobs.append((lab, s, ('time', tsb)))
        s2 = pool.map(stage2, jobs, chunksize=1)
    rows = []
    for lab, s, mode, g, sm, raw, n, gp in s2:
        rows.append(dict(tf=lab, sig=s, mode=mode, exits=g, smooth=sm, raw=raw, n=n, gridpos=gp))
    for _, lab in TFS:
        rs = [r for r in rows if r['tf'] == lab and r['n'] >= 20]
        if not rs: continue
        best = max(rs, key=lambda r: r['smooth'])
        dflt = next(r for r in rows if r['tf'] == lab and r['sig'] == DEFAULT and r['mode'] == ('unit', 'ATR14'))
        out[lab] = dict(best=detail(lab, best['sig'], best['mode'], best['exits']), best_gridpos=best['gridpos'], best_smooth=best['smooth'],
                        default=detail(lab, DEFAULT, ('unit', 'ATR14'), (3, 1, 1.5)),
                        by_method={str(r['mode']): (round(r['smooth'], 2), r['n'], round(r['gridpos'], 2)) for r in rs if r['sig'] == best['sig']})
        d = out[lab]['best']; f = out[lab]['default']
        print('\n%s BEST %s %s %s n=%d win %.0f%% PF %.2f (train %.2f test %.2f) exp %+.3fR  0.5%%: %+.2f%% dd %.2f%% | grid+ %.0f%% | DEFAULT PF %.2f n=%d exp %+.3fR'
              % (lab, d['sig'], d['mode'], d['exits'], d['n'], d['win'], d['pf'], d['pf_train'], d['pf_test'], d['expR'], d['ret05'], d['dd05'], 100 * best['gridpos'], f['pf'], f['n'], f['expR']))
        for m, v in sorted(out[lab]['by_method'].items(), key=lambda x: -x[1][0]): print('     %-26s smooth %+6.2f  n=%d  grid+ %.0f%%' % (m, v[0], v[1], 100 * v[2]))
    json.dump(out, open(OUT, 'w'), default=str, indent=1)
