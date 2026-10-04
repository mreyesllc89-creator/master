import numpy as np, pandas as pd, itertools, sys
from sim import *
tf = sys.argv[1]
d = pd.read_parquet(f'btc_{tf}.parquet')
o,h,l,c = (d[k].values.astype(float) for k in ['open','high','low','close'])
A = atr(h,l,c,14)
idx = d.index
tr0 = idx.searchsorted(pd.Timestamp('2018-01-01')); tr1 = idx.searchsorted(pd.Timestamp('2023-01-01')); te1 = len(d)
trends = {0: np.zeros(len(c))}
for n in [50,100,200]: trends[n] = ema(c, n)
sigs = []
for f,s_ in [(5,13),(9,21),(12,26),(20,50),(21,55),(50,100)]:
    for rd in ['open','close']: sigs.append((('ema',rd,f,s_,0), signals(d,'ema',rd,f,s_,0)))
sigs.append((('engulf','x',0,0,0), signals(d,'engulf','close',0,0,0)))
for b in [10,20,30,55]: sigs.append((('brk','x',0,0,b), signals(d,'brk','close',0,0,b)))
rows=[]
for (key,(L,S)) in sigs:
  for tn,dm,slm,tpR,(trA,trO),mb in itertools.product([0,50,100,200],[0,1],[0,1.5,2,3,4],[0,2,3,5],[(0,0),(2,1.5),(3,2),(4,3)],[0]):
    if slm==0 and tpR>0: continue
    r1 = run(o,h,l,c,L,S,trends[tn],A,dm,slm,tpR,trA,trO,mb,0.001,tr0,tr1)
    r2 = run(o,h,l,c,L,S,trends[tn],A,dm,slm,tpR,trA,trO,mb,0.001,tr1,te1)
    rows.append(key+(tn,dm,slm,tpR,trA,trO)+r1+r2)
cols=['mode','read','fast','slow','brk','trend','dir','sl','tpR','trA','trO','ret1','dd1','n1','wr1','pf1','ret2','dd2','n2','wr2','pf2']
R=pd.DataFrame(rows,columns=cols); R.to_csv(f'grid_{tf}.csv',index=False)
print(tf,'B&H train',c[tr1-1]/c[tr0]-1,'test',c[-1]/c[tr1]-1, len(R))
