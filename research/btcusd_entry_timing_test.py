# BTCUSD entry-timing test (Python replica). Data: github.com/ff137/bitstamp-btcusd-minute-data, data/updates/btcusd_bitstamp_1min_latest.csv
# Run: FEE=0.0005 python3 research/btcusd_entry_timing_test.py <that csv> 1h 15min 5min 1min   (FEE = fraction per side)
import numpy as np, pandas as pd, sys
sys.path.insert(0,'.')
from entry_timing_test import prep, signals
raw=pd.read_csv(sys.argv[1], usecols=['timestamp','open','high','low','close']).set_index('timestamp').pipe(lambda d: d.set_axis(pd.to_datetime(d.index, unit='s')))
raw.columns=['Open','High','Low','Close']

def run(D,pushes,mode,flip,ex):
    o,h,l,c,atr=D['o'],D['h'],D['l'],D['c'],D['atr']
    ev={}
    for p in pushes:
        if mode=="E0": ev.setdefault(p['start'],[]).append(("in",p['e0'],max(o[p['start']],p['P']),True,p))
        if mode=="E1": ev.setdefault(p['start'],[]).append(("in",p['e1'],c[p['start']],False,p))
        if mode=="E2": ev.setdefault(p['end'],[]).append(("in",p['lab'],c[p['end']],False,p))
        if flip and mode!="E2": ev.setdefault(p['end'],[]).append(("lab",p['lab'],c[p['end']],False,p))
    pos=None;pnl=[];dist=[]
    def close(px):
        nonlocal pos
        pnl.append(pos['side']*(px-pos['px'])-FEE*(px+pos['px'])); pos=None
    for i in range(D['n']):
        if pos and i>pos['bar']:
            s=pos['side'];sl=pos['px']-s*pos['sl'];tp=pos['px']+s*pos['tp']
            adverse=l[i] if s>0 else h[i]; fav=h[i] if s>0 else l[i]
            stop=max(sl,pos['trail']) if s>0 else min(sl,pos['trail'])
            if (s>0 and adverse<=stop) or (s<0 and adverse>=stop): close(stop)
            elif (s>0 and fav>=tp) or (s<0 and fav<=tp): close(tp)
            else:
                pos['best']=max(pos['best'],s*(fav-pos['px']))
                if pos['best']>=pos['act']:
                    t=pos['px']+s*(pos['best']-pos['off'])
                    pos['trail']=max(pos['trail'],t) if s>0 else min(pos['trail'],t)
        for kind,side,px,intrabar,p in ev.get(i,[]):
            if kind=="lab":
                if pos and pos['push'] is p and side!=pos['side']: close(c[i])
                continue
            if side==0 or (pos and pos['side']==side): continue
            if pos: close(px)
            sl,tp,act,off=ex(atr[i-1])
            pos=dict(side=side,px=px,sl=sl,tp=tp,act=act,off=off,bar=i,push=p,best=0.0,trail=-np.inf if side>0 else np.inf)
            dist.append(abs(p['ph']-px))
            if intrabar and side<0 and h[i]>=px+sl: close(px+sl)
    if pos: close(c[-1])
    P=np.array(pnl); w=P[P>0].sum(); ls=-P[P<0].sum()
    return len(P),(P>0).mean(),P.sum(),w/ls if ls else np.inf,np.mean(dist)

EXITS={
 "ATR (2 ATR SL, 2R TP, trail 4/0.2 ATR)": lambda a:(2*a,4*a,4*a,0.2*a),
 "Points, tick $1 (SL $5000, TP $50000, trail $1500/$100)": lambda a:(5000,50000,1500,100),
 "Points, tick $0.01 (SL $50, TP $500, trail $15/$1)": lambda a:(50,500,15,1),
}
FEE=float(__import__('os').environ.get('FEE','0'))
MODES=[("E0",True,"E0 breakout order"),("E1",True,"E1 first new-high close"),("E2",False,"E2 label (push end)")]
for tf in sys.argv[2:]:
    df=raw if tf=="1min" else raw.resample(tf).agg({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna()
    D=prep(df); P=signals(D)
    lab=np.array([p['lab'] for p in P]); e0=np.array([p['e0'] for p in P]); e1=np.array([p['e1'] for p in P])
    print(f"\n=== BTCUSD {tf}: {len(df)} bars, {len(P)} pushes (labels {np.sum(lab>0)} long / {np.sum(lab<0)} short) | read = label: E0 {np.mean(e0==lab):.0%}, E1 {np.mean(e1==lab):.0%}")
    for en,ex in EXITS.items():
        print(f"  [{en}]")
        for m,f,d in MODES:
            n,w,tot,pf,dd=run(D,P,m,f,ex)
            print(f"    {d:26s} trades {n:6d}  win {w:4.0%}  P&L/1 BTC ${tot:>12,.0f}  PF {pf:5.2f}  entry vs label ${dd:,.0f}")
    sys.stdout.flush()
