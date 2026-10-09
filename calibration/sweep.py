"""Swept calibration on ALL tick data, scored on 4 time blocks (blocked cross-validation).
usage: sweep.py <SYMBOL> <comm/unit/side> <qty step> <out.json> <pkl> [<pkl> ...]
Each contiguous data segment (split at gaps > 3 days) is replayed separately. Trades are assigned to
4 calendar blocks by entry time. Score = 0.5 * worst block + 0.5 * mean block, in R per week."""
import sys, itertools, json, numpy as np, pandas as pd
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, engine2
from xpw import indicators, signals, rma
SYM, COMM, STEP, OUT, PKLS = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5:]
BLOCKS = [('2026-07-01', '2026-07-24'), ('2026-07-24', '2026-08-17'), ('2026-08-17', '2026-09-14'), ('2026-09-14', '2026-10-31')]
BT0 = np.array([np.datetime64(a) for a, b in BLOCKS]); BT1 = np.array([np.datetime64(b) for a, b in BLOCKS])

def segments(df):
    cut = np.where(df['ts'].diff() > pd.Timedelta('3D'))[0]; e = [0, *cut, len(df)]
    return [df.iloc[a:b].reset_index(drop=True) for a, b in zip(e[:-1], e[1:])]
SEGS = [s for p in PKLS for s in segments(pd.read_pickle(p))]
WEEKS = np.zeros(4)
for s in SEGS:
    for i in range(4):
        a = max(s['ts'].iloc[0].to_datetime64(), BT0[i]); b = min(s['ts'].iloc[-1].to_datetime64(), BT1[i])
        if b > a: WEEKS[i] += (b - a) / np.timedelta64(7, 'D')
TFS = [('5min', '5m'), ('15min', '15m'), ('30min', '30m'), ('60min', '1h'), ('120min', '2h')]
BASE = {lab: [build(s, rule) for s in SEGS] for rule, lab in TFS}
SIG = list(itertools.product([10, 14, 21], [2, 3], [5, 7, 10], [6, 12, 24], [1, 2], [True, False]))
UNITS = ['ATR14', 'ATR50', 'StdDev20', 'Range14', 'Percent', 'Fixed', 'Donchian20']

def roll(x, n, f): return getattr(pd.Series(x).rolling(n), f)().values

def prep(D0, s):
    D = {k: D0[k] for k in ('t', 'o', 'h', 'l', 'c', 'fastx', 'slowx', 'xpx')}
    D = signals(indicators(D, *s[:3]), turnMax=s[3], turnHold=s[4])
    h, l, c, atr = D['h'], D['l'], D['c'], D['atr']; med = np.nanmedian(atr)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))
    raw = {'ATR14': atr, 'ATR50': rma(tr, 50), 'StdDev20': roll(c, 20, 'std'), 'Range14': roll(h - l, 14, 'mean'),
           'Percent': c.copy(), 'Fixed': np.ones_like(c), 'Donchian20': roll(h, 20, 'max') - roll(l, 20, 'min')}
    D['U'] = {k: np.where(np.isnan(v), atr, v) * med / np.nanmedian(np.where(np.isnan(v), atr, v)) for k, v in raw.items()}
    ema = pd.Series(c).ewm(span=20, adjust=False).mean().values
    z = np.zeros(len(c), bool)
    D['EX'] = {'none': (z, z), 'TDI cross': (D['fast'] < D['slow'], D['fast'] > D['slow']), 'EMA20 close': (c < ema, c > ema)}
    x = np.where(np.isnan(D['xpxc']), c, D['xpxc'])
    D['SW'] = {N: (np.maximum(x - roll(l, N, 'min') + 0.1 * atr, 0.3 * atr), np.maximum(roll(h, N, 'max') - x + 0.1 * atr, 0.3 * atr)) for N in (5, 10, 20)}
    D['tt'] = np.array(D['t'], dtype='datetime64[ns]')
    return D

def mk(lab, s): return [(prep(D0, s), b, seg) for (D0, b), seg in zip(BASE[lab], SEGS)]

def run(packs, s, mode, g):
    """mode: ('unit', name) g=(sl, act, dis) | ('swing', N) g=(act, dis) | ('exit', rule)/('time', bars) g=(sl, act, dis)"""
    P, S, T, K = [], [], [], []
    for D, b, seg in packs:
        U = D['U']['ATR14']; ex = D['EX']['none']; ts = 0
        if mode[0] == 'unit': U = D['U'][mode[1]]; slL = slS = g[0] * U; act, dis = g[1], g[2]
        elif mode[0] == 'swing': slL, slS = D['SW'][mode[1]]; act, dis = g
        else:
            slL = slS = g[0] * U; act, dis = g[1], g[2]
            if mode[0] == 'exit': ex = D['EX'][mode[1]]
            else: ts = mode[1]
        p, sl, eb, k = engine2(seg['bid'].values, seg['ask'].values, b, D['wantL'], D['wantS'], D['xpxc'], D['fast'], D['slow'],
                               U, slL, slS, ex[0], ex[1], 0.01, 0, act, dis, COMM, s[4], s[5], ts, 60)
        P.append(p); S.append(sl); T.append(D['tt'][eb]); K.append(k)
    p, sl, t, k = np.concatenate(P), np.concatenate(S), np.concatenate(T), np.concatenate(K)
    o = np.argsort(t, kind='stable')
    return p[o] / sl[o], p[o], sl[o], t[o], k[o]

def blocks(R, t):
    return np.array([R[(t >= BT0[i]) & (t < BT1[i])].sum() / max(WEEKS[i], 1e-9) for i in range(4)])

def score(R, t):
    bw = blocks(R, t); return 0.5 * bw.min() + 0.5 * bw.mean()

def stage1(a):
    lab, s = a; packs = mk(lab, s); sc = []; n = 0
    for g in [(3, 1, 1.5), (6, 3, 1.5), (2, 0.5, 1), (4, 2, 2)]:
        R, p, sl, t, k = run(packs, s, ('unit', 'ATR14'), g); sc.append(score(R, t)); n = len(R)
    return lab, s, float(min(sc)), float(np.median(sc)), n

SLG = [1, 1.5, 2, 3, 4]; ACT = [0, 0.5, 1, 2]; DIS = [0.5, 0.75, 1, 1.5, 2]
def grid(mode):
    if mode[0] == 'unit': return list(itertools.product(SLG, ACT, DIS))
    if mode[0] == 'swing': return list(itertools.product(ACT, DIS))
    return list(itertools.product([1.5, 2, 3, 4], [0, 1, 99], [0.75, 1.5]))

def stage2(a):
    lab, s, mode = a; packs = mk(lab, s); res = {}
    for g in grid(mode):
        R, p, sl, t, k = run(packs, s, mode, g); res[g] = (score(R, t), len(R))
    keys = list(res)
    def smooth(key): return float(np.mean([res[k2][0] for k2 in keys if all(abs(i - j) <= 0.6 * max(abs(i), 1) for i, j in zip(key, k2))]))
    best = max(keys, key=smooth)
    return lab, s, mode, best, smooth(best), res[best][1], float(np.mean([v[0] > 0 for v in res.values()]))

def detail(lab, s, mode, g):
    packs = mk(lab, s); R, p, sl, t, k = run(packs, s, mode, g)
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else 99.0
    bpf = [pf(R[(t >= BT0[i]) & (t < BT1[i])]) for i in range(4)]
    eq = 1e4; cu = [eq]
    for pi, si in zip(p, sl):
        q = np.floor(eq * 0.005 / si / STEP) * STEP
        if q > 0: eq += q * pi; cu.append(eq)
    cu = np.array(cu)
    return dict(tf=lab, sig=list(s), mode=list(mode), exits=list(g), n=int(len(R)), win=float(np.mean(R > 0) * 100), pf=pf(R),
                block_pf=bpf, block_Rwk=[float(x) for x in blocks(R, t)], expR=float(R.mean()), ret05=float((eq / 1e4 - 1) * 100),
                dd05=float(np.max(1 - cu / np.maximum.accumulate(cu)) * 100), weeks=float(WEEKS.sum()))

CURRENT = {'XAUUSD-ECNc': [('30m', (14, 2, 7, 12, 2, True), ('unit', 'ATR14'), (3, 1, 1.5), 'Gold M30'),
                           ('15m', (21, 2, 5, 6, 2, False), ('unit', 'ATR14'), (2, 1, 0.5), 'Gold M15'),
                           ('30m', (10, 2, 10, 12, 2, True), ('swing', 5), (2, 2), 'Gold M30 swing'),
                           ('15m', (21, 2, 5, 6, 1, False), ('time', 24), (1.5, 1, 0.75), 'Gold M15 time'),
                           ('1h', (14, 3, 7, 24, 2, True), ('swing', 20), (0, 1.5), 'Gold H1 swing')],
           'BTCUSD.c':    [('30m', (21, 2, 5, 6, 2, False), ('unit', 'ATR14'), (3, 1.5, 0.75), 'BTC M30'),
                           ('15m', (21, 2, 10, 6, 1, False), ('time', 24), (4, 99, 0.75), 'BTC M15 time'),
                           ('30m', (21, 2, 5, 6, 1, False), ('unit', 'ATR50'), (4, 2, 0.5), 'BTC M30 ATR50'),
                           ('1h', (14, 2, 10, 6, 1, False), ('unit', 'Range14'), (1, 1, 2), 'BTC H1 range')]}

def fmt(d):
    return 'n=%d win %.0f%% PF %.2f | block PF %s | exp %+.3fR | 0.5%%: %+.1f%% DD %.1f%%' % (
        d['n'], d['win'], d['pf'], ' '.join('%.2f' % x for x in d['block_pf']), d['expR'], d['ret05'], d['dd05'])

if __name__ == '__main__':
    print(SYM, 'segments', len(SEGS), 'weeks per block', WEEKS.round(1), flush=True)
    out = {'current': {}, 'best': {}}
    for lab, s, mode, g, name in CURRENT[SYM]:
        d = detail(lab, s, mode, g); out['current'][name] = d; print('current %-15s %-4s %s' % (name, lab, fmt(d)), flush=True)
    with Pool(4) as pool:
        s1 = pool.map(stage1, [(lab, s) for _, lab in TFS for s in SIG], chunksize=4)
        tops = {}
        for _, lab in TFS:
            rows = sorted([x for x in s1 if x[0] == lab and x[4] >= 30], key=lambda x: (x[2], x[3]), reverse=True)
            tops[lab] = [r[1] for r in rows[:2]]
            print(lab, 'top entries', [(r[1], round(r[2], 2), r[4]) for r in rows[:2]], flush=True)
        modes = [('unit', u) for u in UNITS] + [('swing', N) for N in (5, 10, 20)] + [('exit', 'TDI cross'), ('exit', 'EMA20 close')] + [('time', b) for b in (12, 24, 48)]
        jobs = [(lab, s, m) for _, lab in TFS for s in tops[lab] for m in modes]
        s2 = pool.map(stage2, jobs, chunksize=1)
    for _, lab in TFS:
        rs = [r for r in s2 if r[0] == lab and r[5] >= 30]
        if not rs: continue
        rs.sort(key=lambda r: r[4], reverse=True)
        out['best'][lab] = []
        print('\n== %s' % lab)
        for r in rs[:3]:
            d = detail(r[0], r[1], r[2], r[3]); d['smooth'] = r[4]; d['gridpos'] = r[6]; out['best'][lab].append(d)
            print('   %-26s %-24s ex %-16s grid+ %3.0f%% | %s' % (r[2], r[1], r[3], 100 * r[6], fmt(d)), flush=True)
    json.dump(out, open(OUT, 'w'), default=str, indent=1)
