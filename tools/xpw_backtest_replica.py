"""Replica backtester for XPW Breakout v2.11 (Stop trigger, bar-close history).

Follows the TradingView broker emulator on historical bars: stop entry filled at the
level plus slippage (or at the open on a gap), open-high-low-close path assumption
(high first when it is closer to the open), bracket active on the fill bar, emulator
trail (trigger / offset), percent commission per fill, risk sizing with the cost
reserve, cost gate, OCA straddle, arm latch with Follow. Pivot levels (BarsN 3) and
optional previous-day high/low (UTC day). It is a replica, not the tester itself.

Usage: python3 tools/xpw_backtest_replica.py [data_dir]
Reads every BITGET_BTCUSDT_<tf>_*.csv in data_dir (default data/bitget_btcusdt_exports),
merging duplicate exports per timeframe by timestamp.
"""
import csv,glob,re,sys,math,os
from collections import defaultdict

COMM=0.0001; SLIP=4.0; SLK=3.0; TPR=3.0; BUF=0.5; TRG=1.0; DST=1.5; ATRLEN=14; N=3
RISK=0.01; CAP=2.0; STEP=0.0001; GATE=0.20; TICK=0.01

DATA=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data','bitget_btcusdt_exports')

def load(tf):
    rows={}
    for f in glob.glob(os.path.join(DATA,'*.csv')):
        if int(re.search(r'BTCUSDT_(\d+)_',f).group(1))!=tf: continue
        for r in csv.DictReader(open(f)): rows[r['time']]=r
    return [rows[k] for k in sorted(rows)]

def rnd(x): return round(round(x/TICK)*TICK,2)

def run(rows, verbose=False, comm=COMM, slip=SLIP, geo='ATR', slpct=0.02, tppct=1.5, prevday=False):
    import datetime
    pdH=[None]*len(rows); pdL=[None]*len(rows)
    if prevday:
        days={}
        for i,r in enumerate(rows):
            t=datetime.datetime.fromisoformat(r['time']).astimezone(datetime.timezone.utc).date(); days.setdefault(t,[]).append(i)
        ks=sorted(days)
        for k1,k2 in zip(ks,ks[1:]):
            hh=max(float(rows[i]['high']) for i in days[k1]); ll=min(float(rows[i]['low']) for i in days[k1])
            for i in days[k2]: pdH[i]=hh; pdL[i]=ll
    o=[float(r['open']) for r in rows];h=[float(r['high']) for r in rows];l=[float(r['low']) for r in rows];c=[float(r['close']) for r in rows]
    n=len(c)
    # ATR (RMA)
    atr=[None]*n; tr=[h[0]-l[0]]+[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,n)]
    for i in range(n):
        if i==ATRLEN-1: atr[i]=sum(tr[:ATRLEN])/ATRLEN
        elif i>=ATRLEN: atr[i]=(atr[i-1]*(ATRLEN-1)+tr[i])/ATRLEN
    swingH=swingL=None; armedL=armedS=False
    equity=100000.0; trades=[]; pos=None; orders={}   # orders: {'L':(px,qty,sl,tp,trg,dst),'S':...}
    lvlUps=[None]*n; lvlDns=[None]*n
    for i in range(n):
        # ---- fills on bar i from orders placed at close of i-1 ----
        O,H,L,C=o[i],h[i],l[i],c[i]
        first,second=(H,L) if (H-O)<(O-L) else (L,H)
        pts=[O,first,second,C]
        newTrade=False
        if pos is None and orders:
            # walk path: find first entry trigger
            filled=None
            def try_fill(px_from,px_to,at_open):
                for side,(px,qty,sl,tp,trg,dst) in orders.items():
                    if side=='L':
                        if at_open and px_from>=px: return side,px_from
                        if not at_open and px_to>px_from and px_from<px<=px_to: return side,px
                    else:
                        if at_open and px_from<=px: return side,px_from
                        if not at_open and px_to<px_from and px_to<=px<px_from: return side,px
                return None
            res=try_fill(O,O,True); seg=0
            if res is None:
                for s in range(3):
                    res=try_fill(pts[s],pts[s+1],False)
                    if res: seg=s; break
            if res:
                side,fp=res; px,qty,sl,tp,trg,dst=orders[side]
                d=1 if side=='L' else -1
                fill=fp+d*slip
                pos={'d':d,'fill':fill,'qty':qty,'sl':fill-d*sl,'tp':fill+d*tp,'trg':fill+d*trg,'dst':dst,'act':False,'ts':None,'bar':i,'ext':fill,'comm':qty*fill*comm}
                newTrade=True
                # remaining path from fill point
                rem=[(fill if False else fp,pts[seg+1])]+[(pts[s],pts[s+1]) for s in range(seg+1,3)]
                pos=exit_walk(pos,rem,i,trades,slip,comm) and pos
            orders={}
        elif pos is not None:
            # gap at open then segments
            rem=[(c[i-1],O,'gap')]+[(pts[s],pts[s+1]) for s in range(3)]
            pos=exit_walk(pos,rem,i,trades,slip,comm) and pos
        if pos is None and trades and trades[-1]['xbar']==i:
            equity=100000.0+sum(t['pnl'] for t in trades)
        # ---- close-run of bar i: levels, arming, orders ----
        if i>=2*N and max(h[i-2*N:i-N])<h[i-N] and h[i-N]>max(h[i-N+1:i+1]): swingH=h[i-N]
        if i>=2*N and min(l[i-2*N:i-N])>l[i-N] and l[i-N]<min(l[i-N+1:i+1]): swingL=l[i-N]
        ups=[v for v in (swingH,pdH[i]) if v is not None and v>C]; dns=[v for v in (swingL,pdL[i]) if v is not None and v<C]
        lvlUp=min(ups) if ups else None; lvlDn=max(dns) if dns else None
        lvlUps[i]=lvlUp; lvlDns[i]=lvlDn
        a=atr[i]
        if newTrade: armedL=armedS=False
        flat=pos is None
        hardOK=flat and a is not None and a>0
        orders={}
        if not hardOK: armedL=armedS=False; continue
        buf=a*BUF; rt=2*(C*comm+slip)
        slAt=(lambda px: a*SLK) if geo=='ATR' else (lambda px: px*slpct/100)
        tpAt=(lambda px: a*SLK*TPR) if geo=='ATR' else (lambda px: px*tppct/100)
        tpN=tpAt(C); costOK=rt<=tpN*GATE
        def q(px):
            per=slAt(px)+2*(px*comm+slip); raw=equity*RISK/per
            return round(math.floor(min(raw,CAP)/STEP+1e-9)*STEP,8)
        if lvlUp is None: armedL=False
        elif not armedL: armedL=C<lvlUp-buf
        if armedL and costOK:
            qq=q(lvlUp)
            if qq>0: orders['L']=(rnd(lvlUp),qq,slAt(lvlUp),tpAt(lvlUp)+2*lvlUp*comm,a*TRG,a*DST)
            else: armedL=False
        if lvlDn is None: armedS=False
        elif not armedS: armedS=C>lvlDn+buf
        if armedS and costOK:
            qq=q(lvlDn)
            if qq>0: orders['S']=(rnd(lvlDn),qq,slAt(lvlDn),tpAt(lvlDn)+2*lvlDn*comm,a*TRG,a*DST)
            else: armedS=False
    if pos is not None:
        pos['mtm']=pos['d']*(c[-1]-pos['fill'])*pos['qty']-pos['comm']-pos['qty']*c[-1]*comm
    return trades,lvlUps,lvlDns,pos

def exit_walk(pos,segs,i,trades,slip,comm):
    d=pos['d']
    for seg in segs:
        a,b=seg[0],seg[1]; gap=len(seg)==3
        if gap:
            # open gap: check stop / tp against the open b directly
            stop=pos['sl'] if not pos['act'] else (max(pos['sl'],pos['ts']) if d>0 else min(pos['sl'],pos['ts']))
            if d*(b-pos['tp'])>=0: return close(pos,b,i,'TP',0,trades,comm)
            if d*(stop-b)>=0: return close(pos,b,i,'SL',slip,trades,comm)
            # trail update on the open point
            if d*(b-pos['ext'])>0: pos['ext']=b
            if not pos['act'] and d*(b-pos['trg'])>=0: pos['act']=True
            if pos['act']: pos['ts']=pos['ext']-d*pos['dst']
            continue
        up=(b-a)*d>0   # favourable direction for the position
        if up:
            if d*(b-pos['tp'])>=0 and d*(pos['tp']-a)>0: return close(pos,pos['tp'],i,'TP',0,trades,comm)
            if d*(b-pos['ext'])>0: pos['ext']=b
            if not pos['act'] and d*(b-pos['trg'])>=0: pos['act']=True
            if pos['act']: pos['ts']=pos['ext']-d*pos['dst']
        else:
            stop=pos['sl'] if not pos['act'] else (max(pos['sl'],pos['ts']) if d>0 else min(pos['sl'],pos['ts']))
            if d*(stop-b)>=0:
                px=stop if d*(a-stop)>=0 else a
                return close(pos,px,i,'Trail' if pos['act'] and stop!=pos['sl'] else 'SL',slip,trades,comm)
    return pos

def close(pos,px,i,why,slip,trades,comm):
    d=pos['d']; xp=px-d*slip; q=pos['qty']
    pnl=d*(xp-pos['fill'])*q - pos['comm'] - q*xp*comm
    trades.append({'d':d,'fill':pos['fill'],'exit':xp,'bar':pos['bar'],'xbar':i,'why':why,'pnl':pnl,'qty':q})
    return None

def stats(trades):
    gp=sum(t['pnl'] for t in trades if t['pnl']>0); gl=-sum(t['pnl'] for t in trades if t['pnl']<=0)
    w=sum(1 for t in trades if t['pnl']>0); n=len(trades)
    return n,w,gp,gl,(gp/gl if gl>0 else float('inf')),sum(t['pnl'] for t in trades)

def pf(t,mtm=None):
    p=[x['pnl'] for x in t]+([mtm] if mtm is not None else [])
    gp=sum(x for x in p if x>0); gl=-sum(x for x in p if x<=0)
    return (gp/gl if gl>0 else float('inf')), len(p), sum(1 for x in p if x>0), sum(p)

if __name__=='__main__':
    TFS=[5,10,15,30,45,60]
    print("A) v2.11 defaults (Pivot only, ATR SL 3 / TP 9, trail 1 / 1.5 ATR), MEXC Futures web/app (0.01 % + 4 USD), open trade marked to market")
    for tf in TFS:
        rows=load(tf); t,_,_,p=run(rows); r=pf(t,p['mtm'] if p else None)
        print(f"  {tf:3d}m | PF {r[0]:.2f} trades={r[1]} wins={r[2]} net={r[3]:+,.0f}")
    print("B) exported chart config (Pivot + PrevDay, Pct SL 0.02 % / TP 1.5 %): zero cost vs MEXC Futures web/app")
    for tf in TFS:
        rows=load(tf)
        t0,_,_,p0=run(rows,comm=0,slip=0,geo='Pct',prevday=True); a=pf(t0,p0['mtm'] if p0 else None)
        t1,_,_,p1=run(rows,comm=0.0001,slip=4,geo='Pct',prevday=True); b=pf(t1,p1['mtm'] if p1 else None)
        print(f"  {tf:3d}m | zero cost PF {a[0]:.2f} n={a[1]} net={a[3]:+,.0f} | MEXC PF {b[0]:.2f} n={b[1]} wins={b[2]} net={b[3]:+,.0f}")
