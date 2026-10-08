"""Neighbourhood check + slippage measurement.  usage: tick_robust.py <ticks.pkl> <comm> <rule> <sl> <tpR> <act> <dis>"""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ticks import build, run
df = pd.read_pickle(sys.argv[1]); comm = float(sys.argv[2]); rule = sys.argv[3]; g0 = tuple(map(float, sys.argv[4:8]))
D, barid = build(df, rule); nb = len(D['c']); split = 60 + (nb - 60) * 6 // 10
def ev(g):
    r, p, eb, k = run(df, D, barid, *g, comm, 0.01)
    return r.sum(), r[eb < split].sum(), r[eb >= split].sum(), len(r)
print(rule, 'center', g0, ['%.2f' % x for x in ev(g0)[:3]])
SL = [g0[0] * m for m in (0.67, 1, 1.5)]; AC = [max(g0[2] + d, 0) for d in (-0.5, 0, 0.5)]; DI = [g0[3] * m for m in (0.67, 1, 1.5)]
rows = [(g, ev(g)) for g in itertools.product(SL, [g0[1]], AC, DI)]
for g, e in rows: print('  sl %.2f act %.2f dis %.2f  net %+.2f%%  train %+.2f test %+.2f  n=%d' % (g[0], g[2], g[3], *e))
print('  neighbours positive: %d / %d   mean net %+.2f%%' % (sum(e[0] > 0 for _, e in rows), len(rows), np.mean([e[0] for _, e in rows])))
# latency slippage: adverse move from a tick to the next one, in price
db = np.abs(np.diff(df['bid'].values)); sp = (df['ask'] - df['bid']).values
print('  next-tick move: median %.3f mean %.3f p90 %.3f | spread median %.3f' % (np.median(db), db.mean(), np.percentile(db, 90), np.median(sp)))
