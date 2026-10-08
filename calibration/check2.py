import sys, glob, numpy as np
sys.path.insert(0, sys.argv[1])
from xpw import *
for p in sorted(glob.glob(sys.argv[2] + '/*.csv')):
    D = signals(indicators(load(p)))
    mine = D['wantL'] | D['wantS']; theirs = ~np.isnan(D['xpx'])
    k = 100
    print(p.split('/')[-1][13:20], 'agree', np.mean(mine[k:] == theirs[k:]).round(3), 'mine', mine[k:].sum(), 'tv', theirs[k:].sum())
