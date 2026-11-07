# consistency: simulate_d with constant tick distances & arm_on_fill=False must match simulate()
import numpy as np
from engine import *
df=load_1m()
for tf in (1,5):
    ch,L,S=signals(df,chart_tf=tf)
    o,h,l,c=(ch[k].to_numpy() for k in "ohlc"); one=np.ones(len(o))
    p,_,_=simulate(o,h,l,c,L,S,200,400,True,150,50,TICK,0.0,1e4,0.01)
    r,_,_=simulate_d(o,h,l,c,L,S,one*2.0,one*4.0,one*1.5,one*0.5,True,False,0.0)
    print(tf,len(p),len(r),np.sign(p).tolist()==np.sign(r).tolist())
    a=atr_on_chart(df,ch,tf,60,14); print(" 60m ATR on chart: median $%.1f"%np.nanmedian(a), " chart ATR $%.1f"%np.nanmedian(atr_on_chart(df,ch,tf,0,14)))
