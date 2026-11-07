import numpy as np, pandas as pd
from engine import *
from sweep import TFSETS, DIVSETS, LEVELS, COMM
df=load_1m(); d=pd.read_pickle("stage2.pkl")
q=d[d.is_n>=40].assign(mn=lambda x: np.minimum(x.is_bp,x.oos_bp))
cands=pd.concat([q.sort_values("mn",ascending=False).head(4), q.sort_values("is_bp",ascending=False).head(2)])
rng=np.random.default_rng(7)
for _,c in cands.iterrows():
    dv=DIVSETS[c["div"]]; lv=LEVELS[c.levels]
    ch,L,S=signals(df,chart_tf=c.chart_tf,divL=c.divL,divR=c.divR,divMin=c.divMin,divMax=c.divMax,dayH=c.dayH,tfs_on=TFSETS[c.tfs],
        regBull=dv[0],regBear=dv[1],hidBull=dv[2],hidBear=dv[3],req4=c.req4,levels=lv is not None,buyLevel=lv[0] if lv else 38,sellLevel=lv[1] if lv else 62,fix_toggles=c.fix)
    o,h,l,cl=(ch[k].to_numpy() for k in "ohlc")
    p,_,_=simulate(o,h,l,cl,L,S,int(c.sl),int(c.tp),bool(c.trail),int(c.act),int(c.off),TICK,COMM,1e4,0.01)
    real=p.mean(); nL,nS=L.sum(),S.sum(); n=len(o); res=[]
    for _ in range(300):
        rL=np.zeros(n,bool); rS=np.zeros(n,bool)
        rL[rng.choice(n,nL,replace=False)]=True; rS[rng.choice(n,nS,replace=False)]=True
        rp,_,_=simulate(o,h,l,cl,rL,rS,int(c.sl),int(c.tp),bool(c.trail),int(c.act),int(c.off),TICK,COMM,1e4,0.01)
        res.append(rp.mean())
    res=np.array(res); se=p.std(ddof=1)/np.sqrt(len(p))
    print(f"tf{c.chart_tf} L{c.divL} dayH{c.dayH} {c['div']} lv={c.levels} tfs={c.tfs} SL={c.sl} TP={c.tp}: trades={len(p)} avg={100*real:.1f}bp t={real/se:.2f}  random-entry avg={100*res.mean():.1f}bp, p(random>=real)={(res>=real).mean():.3f}")
