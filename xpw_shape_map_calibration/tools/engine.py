import numpy as np, pandas as pd
from numba import njit
import os
U=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','data','')
d=pd.read_csv(U+'CAPITALCOM_XAUUSD_15.csv')
d['ts']=d['time'].str.slice(0,16).str.replace('T',' ')
tl=pd.read_csv(U+'XPW-SM9.2_trades_2026-11-17.csv')
O=d.open.values.astype(float);H=d.high.values.astype(float);L=d.low.values.astype(float);C=d.close.values.astype(float)
N=len(d)
# Wilder ATR(14) like ta.atr
tr=np.maximum(H-L,np.maximum(abs(H-np.r_[C[0],C[:-1]]),abs(L-np.r_[C[0],C[:-1]]))); tr[0]=H[0]-L[0]
ATR=np.full(N,np.nan); ATR[13]=tr[:14].mean()
for i in range(14,N): ATR[i]=(ATR[i-1]*13+tr[i])/14
rl=d['FGD raw long'].fillna(0).values;rs=d['FGD raw short'].fillna(0).values
bl=d['FGD blocked long'].fillna(0).values;bs=d['FGD blocked short'].fillna(0).values
sigB=np.where(rl==1,1,np.where(rs==1,-1,0))                       # all raw CONT signals
sigA=np.where((rl==1)&(bl==0),1,np.where((rs==1)&(bs==0),-1,0))   # passed the direction filter
ix={t:i for i,t in enumerate(d.ts)}
for _,r in tl[tl.Type.str.startswith('Entry')].iterrows():
    sigA[ix[r['Date and time']]]=1 if 'long' in r.Type else -1    # + trades actually taken
sigA[:20]=0; sigB[:20]=0

def tv_paths():
    P=np.empty((N,4)); up=(H-O)<(O-L)   # open nearer the high -> O,H,L,C
    P[:,0]=O;P[:,3]=C
    P[:,1]=np.where(up,H,L);P[:,2]=np.where(up,L,H)
    return P
def mc_paths(seed,n=90):
    rng=np.random.default_rng(seed)
    P=np.empty((N,n+1))
    for i in range(N):
        while True:
            w=np.cumsum(rng.standard_normal(n)); w=np.r_[0,w]
            b=w-np.linspace(0,1,n+1)*w[-1]            # bridge 0 -> 0
            sc=(H[i]-L[i])/max(b.max()-b.min(),1e-9)
            p=b*sc+np.linspace(0,1,n+1)*(C[i]-O[i])   # ends at C-O
            M=p.max();m=p.min();c=C[i]-O[i]
            xs=[m,min(0,c),max(0,c),M];ys=[L[i]-O[i],min(0,c),max(0,c),H[i]-O[i]]
            if xs[0]<xs[1]-1e-12 or abs(ys[0]-ys[1])<1e-12:
                if xs[3]>xs[2]+1e-12 or abs(ys[3]-ys[2])<1e-12: break
        X=[];Y=[]
        for x,y in zip(xs,ys):
            if not X or x>X[-1]+1e-12: X.append(x);Y.append(y)
        P[i]=O[i]+np.interp(p,X,Y)
    return P

# par: 0 sl,1 tp(R,0=off),2 ta(<0 off),3 td,4 tNeed,5 bm,6 bk,7 bn,8 bAct,9 bNeed,10 beAct(<0 off),11 beOff,12 tstop,13 opp(1=reverse)
@njit
def run(P,O,H,L,C,ATR,sig,par,cost_pct,slip):
    N=len(O);npt=P.shape[1]
    out=np.empty((2000,4));k=0
    pos=0;e=0.0;a=0.0;ei=0;stop=0.0;hi=0.0;thi=0.0;tact=False;cnt=0;latchT=False;latchB=False
    sl=par[0];tp=par[1];ta=par[2];td=par[3];tNeed=par[4];bm=par[5];bk=par[6];bn=int(par[7]);bAct=par[8];bNeed=par[9]
    beA=par[10];beO=par[11];tst=par[12];opp=par[13]
    for i in range(N):
        if pos!=0:
            s=float(pos);x=0.0;done=False
            tpl=e+tp*sl*a if tp>0 else 1e18     # in mirrored space (s*price)
            prev=s*C[i-1]
            for j in range(npt):
                p=s*P[i,j]
                if j==0:  # gap
                    if p<=stop: x=p;done=True
                    elif p>=tpl: x=p;done=True
                elif p<prev:
                    if p<=stop: x=stop;done=True
                elif p>prev:
                    if p>=tpl: x=tpl;done=True
                if done: break
                if p>hi:
                    hi=p
                if beA>=0 and hi-e>=beA*a and stop<e+beO*a: stop=e+beO*a
                if ta>=0 and latchT:
                    if p>thi: thi=p
                    if thi-e>=ta*a and thi-td*a>stop: stop=thi-td*a
                prev=p
            if not done:
                # bar close bookkeeping (mirrored)
                c=s*C[i];o=s*O[i]
                if c>o: cnt+=1
                else: cnt=0
                if cnt>=tNeed and not latchT:
                    latchT=True;thi=c
                if cnt>=bNeed: latchB=True
                if bm>0 and latchB and c-e>=bAct*a:
                    ns=-1e18
                    if bm==1:
                        hh=-1e18
                        for q in range(ei+1,i+1):
                            v=H[q] if pos>0 else -L[q]
                            if v>hh: hh=v
                        ns=hh-bk*a
                    elif bm==2:
                        ll=1e18
                        for q in range(max(ei+1,i-bn+1),i+1):
                            v=L[q] if pos>0 else -H[q]
                            if v<ll: ll=v
                        ns=ll-bk*a
                    elif bm==3:
                        ns=c-bk*a
                    if ns>stop: stop=ns
                    if stop>=c: x=c;done=True      # stop already above price: out at the close
                if not done and tst>0 and i-ei>=tst: x=c;done=True
                if not done and sig[i]==-pos and opp>0: x=c;done=True
            if done:
                r=(x-e)/a - cost_pct*abs(e)/a - slip/a
                out[k,0]=ei;out[k,1]=i;out[k,2]=r;out[k,3]=pos;k+=1
                pos=0
        if pos==0 and sig[i]!=0 and i<N-1 and not np.isnan(ATR[i]):
            pos=sig[i];s=float(pos);e=s*C[i];a=ATR[i];ei=i
            stop=e-sl*a;hi=e;thi=e;cnt=0;latchT=tNeed<=0;latchB=bNeed<=0
    return out[:k]

def P_(sl=1,tp=2,ta=-1,td=0,tNeed=0,bm=0,bk=0,bn=1,bAct=0,bNeed=0,beA=-1,beO=0,tst=0,opp=1):
    return np.array([sl,tp,ta,td,tNeed,bm,bk,bn,bAct,bNeed,beA,beO,tst,opp],float)
def stats(r):
    if len(r)==0: return dict(n=0,tot=0,avg=0,win=0,pf=0,dd=0)
    eq=np.cumsum(r);dd=(np.maximum.accumulate(np.r_[0,eq])-np.r_[0,eq]).max()
    g=r[r>0].sum();l=-r[r<0].sum()
    return dict(n=len(r),tot=r.sum(),avg=r.mean(),win=(r>0).mean()*100,pf=g/l if l>0 else 99,dd=dd)

def mc_fast(seed,n=600):
    rng=np.random.default_rng(seed)
    P=np.empty((N,n+1),dtype=np.float64)
    todo=np.arange(N)
    lin=np.linspace(0,1,n+1)
    while len(todo):
        w=np.cumsum(rng.standard_normal((len(todo),n)),axis=1); w=np.c_[np.zeros(len(todo)),w]
        b=w-lin*w[:,-1:]
        rg=(H-L)[todo]; c=(C-O)[todo]
        sc=rg/np.maximum(b.max(1)-b.min(1),1e-9)
        p=b*sc[:,None]+lin*c[:,None]
        M=p.max(1);m=p.min(1);hx=np.maximum(0,c);lx=np.minimum(0,c)
        hy=(H-O)[todo];ly=(L-O)[todo]
        okh=(M>hx+1e-9)|(np.abs(hy-hx)<1e-9); okl=(m<lx-1e-9)|(np.abs(ly-lx)<1e-9); ok=okh&okl
        ku=(hy-hx)/np.maximum(M-hx,1e-12); kd=(ly-lx)/np.minimum(m-lx,-1e-12)
        y=np.where(p>hx[:,None],hx[:,None]+(p-hx[:,None])*ku[:,None],np.where(p<lx[:,None],lx[:,None]+(p-lx[:,None])*kd[:,None],p))
        P[todo[ok]]=O[todo[ok],None]+y[ok]
        todo=todo[~ok]
    return P
