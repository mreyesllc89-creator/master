"""Calibrate exits on MT5 ticks.  usage: tick_calib.py <ticks.csv> <tick size> <commission per unit per side>"""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import load_ticks, build, run
path, tick, comm = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
df = pd.read_pickle(path) if path.endswith('.pkl') else load_ticks(path)
sp = (df['ask'] - df['bid']).values
print(path.split('/')[-1], len(df), 'ticks', df['ts'].iloc[0], '->', df['ts'].iloc[-1])
print('spread median %.3f  p90 %.3f  p99 %.3f  (%.4f%% of price)' % (np.median(sp), np.percentile(sp, 90), np.percentile(sp, 99), np.median(sp) / df['bid'].median() * 100))
GRID = list(itertools.product([1, 1.5, 2, 3, 4, 6, 8], [0, 2, 4], [0, 0.5, 1, 1.5, 2, 3], [0.25, 0.5, 0.75, 1, 1.5, 2]))
def st(r):
    gp = r[r > 0].sum(); gl = -r[r < 0].sum()
    return len(r), r.sum(), (gp / gl if gl > 0 else 99)
for rule, lab in [('1min', '1m'), ('5min', '5m'), ('15min', '15m'), ('30min', '30m'), ('60min', '60m'), ('120min', '2h')]:
    D, barid = build(df, rule)
    nb = len(D['c']); split = 60 + (nb - 60) * 6 // 10
    atrp = np.nanmedian(D['atr'] / D['c']) * 100
    res = []
    for g in GRID:
        ret, pnl, eb, kind = run(df, D, barid, *g, comm, tick)
        a, b = ret[eb < split], ret[eb >= split]
        res.append((min(a.sum(), b.sum()) / atrp, g, st(ret), st(a), st(b), pnl.sum()))
    res.sort(key=lambda x: x[0], reverse=True)
    print('\n%s  bars %d  ATR %.3f%%' % (lab, nb, atrp))
    for nm, g in [('script default 6/0/3/1.5', (6, 0, 3, 1.5))] + [('best', res[0][1]), ('2nd', res[1][1]), ('3rd', res[2][1])]:
        ret, pnl, eb, kind = run(df, D, barid, *g, comm, tick)
        r0, p0, _, _ = run(df, D, barid, *g, 0.0, tick, spread=False)
        a, b = ret[eb < split], ret[eb >= split]
        kinds = {k: int((kind == v).sum()) for k, v in [('SL', 1), ('trail', 2), ('TP', 3), ('fail', 4), ('rev', 0)]}
        print('  %-26s %s  n=%3d net=%+6.2f%% pf=%.2f  $/unit=%+9.2f | train %+6.2f%% test %+6.2f%% | no spread/comm %+6.2f%% | %s'
              % (nm, g, len(ret), ret.sum(), st(ret)[2], pnl.sum(), a.sum(), b.sum(), r0.sum(), kinds))
    print('  share of grid positive in both halves: %.0f%%' % (100 * np.mean([x[0] > 0 for x in res])))
