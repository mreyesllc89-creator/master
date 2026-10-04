# Python port of hrd_full_divergence_v1.03 (indicator + strategy) used to test
# the divergence logic offline. Run: pip install pandas numpy && python3 tests/test_hrd.py
import numpy as np, pandas as pd
P=dict(rsiLen=14,stLen=5,stSmth=3,w=(0.4,0.3,0.3),thr=70,ps=5,lb=60,ncmp=3,minOsc=3.0,eqTol=0.1,
       os=35,ob=65,trendLen=200,hzTol=0.5,stopBuf=0.5,rr=2.0,opp="Reverse",reqHz=False)
def rma(x,n):
    out=np.full(len(x),np.nan); s=None
    for i,v in enumerate(x):
        if np.isnan(v): continue
        if s is None:
            # seed with SMA of first n valid
            pass
        out[i]=v
    return pd.Series(x).ewm(alpha=1/n,adjust=False).mean().values
def ema(x,n): return pd.Series(x).ewm(span=n,adjust=False).mean().values
def indicators(df,p=P):
    c,h,l=df.close.values,df.high.values,df.low.values
    d=np.diff(c,prepend=c[0]); up=rma(np.maximum(d,0),p['rsiLen']); dn=rma(np.maximum(-d,0),p['rsiLen'])
    rsi=np.where(dn==0,100,100-100/(1+up/np.where(dn==0,1,dn)))
    macd=ema(c,12)-ema(c,26)
    hh=pd.Series(h).rolling(p['stLen']).max().values; ll=pd.Series(l).rolling(p['stLen']).min().values
    k=100*(c-ll)/np.where(hh-ll==0,np.nan,hh-ll); st=pd.Series(k).rolling(p['stSmth']).mean().values
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1)))); tr[0]=h[0]-l[0]
    atr=rma(tr,14)
    mn=np.clip(50+25*np.nan_to_num(macd/atr),0,100)
    w=p['w']; osc=(rsi*w[0]+mn*w[1]+st*w[2])/sum(w)
    # HTF previous completed H/L (no lookahead)
    t=df.index; out={}
    for key,rule in (('d','D'),('w','W'),('m','MS')):
        g=df.resample(rule).agg({'high':'max','low':'min'}).shift(1)
        out[key+'h']=g.high.reindex(t,method='ffill').values; out[key+'l']=g.low.reindex(t,method='ffill').values
    return dict(osc=osc,atr=atr,ema=ema(c,p['trendLen']),**out)
def pivots(x,ps,hi):
    n=len(x); res=np.full(n,np.nan)
    for i in range(2*ps,n):
        cidx=i-ps; v=x[cidx]; L=x[cidx-ps:cidx]; R=x[cidx+1:i+1]
        if hi and v>L.max() and v>=R.max() and not (R==v).any(): res[i]=v
        if not hi and v<L.min() and v<=R.min() and not (R==v).any(): res[i]=v
    return res
base={1:55,3:45,2:40}
def find_div(d,cB,cP,cO,tol,hist,p):
    best=(0,-1,0.0,-1)
    for i,(pB,pP,pO) in enumerate(hist[:p['ncmp']]):
        if cB-pB>p['lb']: break
        pm=(cP-pP)*d; om=(cO-pO)*d; k=0
        if pm<-tol and om>=p['minOsc']: k=1
        elif abs(pm)<=tol and om>=p['minOsc']: k=3
        elif pm>tol and om<=-p['minOsc']: k=2
        if k and i>0:
            for j in range(i):
                la=pP+(cP-pP)*(hist[j][0]-pB)/(cB-pB)
                if (hist[j][1]-la)*d<0: k=0;break
        if k:
            part=base[k]+min(15,abs(om)*1.5)
            if part>best[3]: best=(k,i,abs(om),part)
    return best[:3]
def signals(df,p=P):
    I=indicators(df,p); ps=p['ps']; n=len(df)
    PH=pivots(df.high.values,ps,True); PL=pivots(df.low.values,ps,False)
    hl,hh=[],[]; rows=[]
    for i in range(n):
        for d,pv,hist in ((1,PL,hl),(-1,PH,hh)):
            if np.isnan(pv[i]): continue
            cB=i-ps; cO=I['osc'][cB]; a=I['atr'][cB]; px=pv[i]
            if np.isnan(cO): hist.insert(0,(cB,px,cO)); continue
            k,idx,spr=find_div(d,cB,px,cO,p['eqTol']*a,hist,p)
            if k:
                tol=p['hzTol']*a; hz=0
                for key,b in (('d',10),('w',15),('m',20)):
                    lv=[I[key+'h'][cB],I[key+'l'][cB]]
                    if min(abs(px-v) if not np.isnan(v) else 1e20 for v in lv)<=tol: hz+=b
                hz=min(hz,30); s=base[k]+min(15,spr*1.5)
                if k==2: s+=10 if (px>I['ema'][cB] if d==1 else px<I['ema'][cB]) else 0
                else: s+=10 if (cO<=p['os'] if d==1 else cO>=p['ob']) else 0
                s=int(round(min(100,s+hz)))
                rows.append(dict(bar=i,pivot_bar=cB,dir=d,kind=k,score=s,hz=hz,pivot=px,prev_bar=hist[idx][0],prev=hist[idx][1],atr=a))
            hist.insert(0,(cB,px,cO)); del hist[10:]
    return pd.DataFrame(rows),I
def backtest(df,p=P,comm=0.0005):
    S,I=signals(df,p); o,h,l,c=(df[x].values for x in ('open','high','low','close'))
    sig={}; 
    if len(S):
        for r in S[S.score>=p['thr']].itertuples():
            sig.setdefault(r.bar,[]).append(r)
    pos=0; trades=[]; pend=None; ent=stop=tgt=None
    for i in range(len(df)):
        if pend is not None:   # fill at open
            d,st,tg=pend; pend=None
            if pos and pos!=d: trades.append(pos*(o[i]-ent)/ent-2*comm); pos=0
            if pos==0: pos,ent,stop,tgt=d,o[i],st,tg
        if pos:  # stop first (conservative)
            if (pos==1 and l[i]<=stop) or (pos==-1 and h[i]>=stop):
                px=o[i] if (pos==1 and o[i]<stop) or (pos==-1 and o[i]>stop) else stop
                trades.append(pos*(px-ent)/ent-2*comm); pos=0
            elif tgt is not None and ((pos==1 and h[i]>=tgt) or (pos==-1 and l[i]<=tgt)):
                trades.append(pos*(tgt-ent)/ent-2*comm); pos=0
        rs=sig.get(i,[])
        if len(rs)==1:
            r=rs[0]; d=r.dir
            if pos==0 or (pos==-d and p['opp']=="Reverse"):
                st=r.pivot-d*p['stopBuf']*r.atr; risk=(c[i]-st)*d
                if risk>0: pend=(d,st,c[i]+d*p['rr']*risk if p['rr']>0 else None)
    return np.array(trades),S
