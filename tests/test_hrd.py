import numpy as np, pandas as pd
from hrd import *
def synth(seed,n=12000):
    r=np.random.default_rng(seed); t=pd.date_range('2022-01-03',periods=n,freq='h')
    drift=np.repeat(r.normal(0,0.0006,n//200+1),200)[:n]
    ret=drift+r.normal(0,0.004,n); c=100*np.exp(np.cumsum(ret)); o=np.r_[c[0],c[:-1]]
    w=np.abs(r.normal(0,0.003,n))*c; h=np.maximum(o,c)+w; l=np.minimum(o,c)-np.abs(r.normal(0,0.003,n))*c
    return pd.DataFrame(dict(open=o,high=h,low=l,close=c),index=t)

# 1) Known pattern: price lower low + momentum higher low -> must detect Regular Bullish
def pattern():
    seg=np.r_[np.linspace(110,100,40),np.linspace(100,106,25)[1:],np.linspace(106,99,12)[1:],np.linspace(99,108,30)[1:]]
    c=np.r_[np.linspace(120,110,250),seg[1:]]; t=pd.date_range('2023-01-02',periods=len(c),freq='h')
    o=np.r_[c[0],c[:-1]]; return pd.DataFrame(dict(open=o,high=c+.3,low=c-.3,close=c),index=t)
S,_=signals(pattern(),{**P,'minOsc':1})
reg=S[(S.dir==1)&(S.kind==1)]
print("1) pattern test: regular bullish found:",len(reg)>0); print(reg[['bar','pivot_bar','prev_bar','pivot','prev','score']].to_string())
assert len(reg)>0

# 2) No repaint / no lookahead: signals from truncated history == signals from full history
df=synth(1); Sf,_=signals(df); ok=True
for cut in (3000,5000,7777,9999):
    St,_=signals(df.iloc[:cut]); a=Sf[Sf.bar<cut-1].reset_index(drop=True); b=St[St.bar<cut-1].reset_index(drop=True)
    ok&= a[['bar','dir','kind','score']].equals(b[['bar','dir','kind','score']])
print("2) no-repaint check (truncated == full):",ok); assert ok
# signal bar must be >= pivot+ps (confirmation)
assert (Sf.bar-Sf.pivot_bar==P['ps']).all() and (Sf.score.between(0,100)).all()
print("   confirmation lag == pivotStrength, scores within 0..100: True")

# 3) Coverage + backtest across seeds (random walk -> expect ~zero edge minus costs)
allS=[];res=[]
for sd in range(10):
    tr,S=backtest(synth(sd)); allS.append(S)
    res.append((sd,len(tr),(tr>0).mean() if len(tr) else 0,tr.sum()*100, tr[tr>0].sum()/max(1e-9,-tr[tr<0].sum())))
A=pd.concat(allS)
print("3) divergences per type (all scores):"); print(A.groupby(['dir','kind']).size().rename({1:'Regular',2:'Hidden',3:'Exag'},level=1).to_string())
print("   share passing threshold %d: %.1f%%; with horizon bonus: %.1f%%"%(P['thr'],100*(A.score>=P['thr']).mean(),100*(A.hz>0).mean()))
R=pd.DataFrame(res,columns=['seed','trades','winrate','sum_ret_%','profit_factor']); print(R.round(3).to_string(index=False))
print("   mean PF %.2f  (random-walk data: ~1.0 or below after costs = no lookahead bias)"%R.profit_factor.mean())
