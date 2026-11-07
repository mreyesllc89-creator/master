import time, numpy as np
from engine import *
df=load_1m(); print(df.index[0], df.index[-1], len(df))
for tf in [1,5,15]:
    t=time.time(); ch,L,S=signals(df,chart_tf=tf)
    o,h,l,c=(ch[k].to_numpy() for k in "ohlc")
    for comm in [0,0.0005]:
        p,b,m=simulate(o,h,l,c,L,S,200,400,True,150,50,TICK,comm,1e4,0.01)
        print(tf, comm, L.sum(),S.sum(), stats(p,m), round(time.time()-t,1))
