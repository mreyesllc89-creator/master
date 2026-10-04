# Entry-timing test for XPW Refusal Log v0.3 Strategy (Python replica, not TradingView).
# E0 = resting order at the breakout level, leg read from the hypothetical red at that price.
# E1 = close of the first new-high candle. E2 = label (push end). ATR exits: SL 2 ATR, TP 2R, trail 4/0.2 ATR.
# Run: pip install backtesting pandas numpy && python3 research/entry_timing_test.py
import numpy as np, pandas as pd
from backtesting.test import EURUSD, GOOG
RSI,RED,PUSH,JOIN,LEGW=14,2,20,3,60
def prep(df):
    o,h,l,c=[df[k].to_numpy(float) for k in ("Open","High","Low","Close")]
    n=len(c); d=np.diff(c,prepend=np.nan)
    up=pd.Series(np.where(d>0,d,0.0)).ewm(alpha=1/RSI,adjust=False).mean().to_numpy()
    dn=pd.Series(np.where(d<0,-d,0.0)).ewm(alpha=1/RSI,adjust=False).mean().to_numpy()
    rsi=100-100/(1+up/np.where(dn==0,1e-12,dn))
    red=pd.Series(rsi).rolling(RED).mean().to_numpy()
    top=pd.Series(red).rolling(LEGW).max().to_numpy()
    hh=pd.Series(h).rolling(PUSH).max().shift(1).to_numpy()
    tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
    atr=pd.Series(tr).ewm(alpha=1/14,adjust=False).mean().to_numpy()
    return dict(o=o,h=h,l=l,c=c,up=up,dn=dn,rsi=rsi,red=red,top=top,hh=hh,atr=atr,n=n)

def signals(D):
    """Walk the pushes. Per push: E0 (resting order at breakout, pre-bar hypothetical read),
    E1 (first new-high close), E2 (label, push-end close), plus the final label side."""
    h,c,red,top,hh=D['h'],D['c'],D['red'],D['top'],D['hh']
    out=[];inP=False
    for i in range(LEGW+2,D['n']):
        newHi=h[i]>hh[i]
        if newHi and not inP:
            P=hh[i]; L=top[i-1]
            # hypothetical red if this bar closed exactly at the breakout level P
            ch=P-c[i-1]
            uh=(D['up'][i-1]*(RSI-1)+max(ch,0))/RSI; dh=(D['dn'][i-1]*(RSI-1)+max(-ch,0))/RSI
            rh=100-100/(1+uh/max(dh,1e-12)); redh=(rh+D['rsi'][i-1])/2
            cur=dict(start=i,P=P,L=L,e0=np.sign(redh-L),e1=np.sign(red[i]-L),rmax=red[i],ph=h[i])
            inP=True;last=i
        elif newHi: last=i; cur['ph']=max(cur['ph'],h[i])
        if inP:
            cur['rmax']=max(cur['rmax'],red[i])
            if not newHi and i-last>=JOIN:
                cur['end']=i; cur['lab']=np.sign(cur['rmax']-cur['L']); out.append(cur); inP=False
    return out

def backtest(D,pushes,mode,flip):
    o,h,l,c,atr=D['o'],D['h'],D['l'],D['c'],D['atr']
    ev={}
    for p in pushes:
        if mode=="E0": ev.setdefault(p['start'],[]).append(("in",p['e0'],max(o[p['start']],p['P']),True,p))
        if mode=="E1": ev.setdefault(p['start'],[]).append(("in",p['e1'],c[p['start']],False,p))
        if mode=="E2": ev.setdefault(p['end'],[]).append(("in",p['lab'],c[p['end']],False,p))
        if flip and mode!="E2": ev.setdefault(p['end'],[]).append(("lab",p['lab'],c[p['end']],False,p))
    pos=None;R=[];dist=[]
    def close(px,i):
        nonlocal pos
        R.append(pos['side']*(px-pos['px'])/pos['risk']); pos=None
    for i in range(D['n']):
        # manage open trade on this bar (skip the bar it filled at close)
        if pos and i>pos['bar']:
            s=pos['side'];sl=pos['px']-s*pos['risk'];tp=pos['px']+s*2*pos['risk']
            adverse=l[i] if s>0 else h[i]; fav=h[i] if s>0 else l[i]
            stop=max(sl,pos['trail']) if s>0 else min(sl,pos['trail'])
            if (s>0 and adverse<=stop) or (s<0 and adverse>=stop):
                close(stop,i)
            elif (s>0 and fav>=tp) or (s<0 and fav<=tp): close(tp,i)
            else:
                pos['best']=max(pos['best'],s*(fav-pos['px']))
                if pos['best']>=4*pos['a']:
                    t=pos['px']+s*(pos['best']-0.2*pos['a'])
                    pos['trail']=max(pos['trail'],t) if s>0 else min(pos['trail'],t)
        for kind,side,px,intrabar,p in ev.get(i,[]):
            if kind=="lab":
                if pos and pos['push'] is p and side!=pos['side']: close(c[i],i)
                continue
            if side==0 or (pos and pos['side']==side): continue
            if pos: close(px,i)
            a=atr[i-1]
            pos=dict(side=side,px=px,risk=2*a,a=a,bar=i,push=p,best=0.0,trail=-np.inf if side>0 else np.inf)
            dist.append(abs(p['ph']-px)/a)
            if intrabar and side<0 and h[i]>=px+2*a: close(px+2*a,i)   # pessimistic: stop hit inside the fill bar
    R=np.array(R); w=R[R>0].sum(); ls=-R[R<0].sum()
    return dict(trades=len(R),win=(R>0).mean() if len(R) else 0,totR=R.sum(),avgR=R.mean() if len(R) else 0,
                pf=w/ls if ls else np.inf,dist=np.mean(dist))

for name,df in [("EURUSD 1h",EURUSD),("GOOG 1d",GOOG)]:
    D=prep(df); P=signals(D)
    lab=np.array([p['lab'] for p in P]); e0=np.array([p['e0'] for p in P]); e1=np.array([p['e1'] for p in P])
    print(f"\n{name}: {len(P)} pushes | labels long {np.sum(lab>0)} short {np.sum(lab<0)}")
    print(f"  read agrees with label: E0 {np.mean(e0==lab):.0%}   E1 {np.mean(e1==lab):.0%}")
    print(f"  {'mode':34s}{'trades':>7s}{'win':>6s}{'total R':>9s}{'avg R':>7s}{'PF':>6s}{'entry vs label px (ATR)':>25s}")
    for mode,flip,desc in [("E0",True,"E0 resting order at breakout +flip"),("E0",False,"E0 resting order, no flip"),
                           ("E1",True,"E1 first new-high close +flip"),("E1",False,"E1 first new-high close, no flip"),
                           ("E2",False,"E2 label (push end)")]:
        r=backtest(D,P,mode,flip)
        print(f"  {desc:34s}{r['trades']:7d}{r['win']:6.0%}{r['totR']:9.1f}{r['avgR']:7.2f}{r['pf']:6.2f}{r['dist']:25.2f}")
