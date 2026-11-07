import itertools, sys, time, hashlib, numpy as np, pandas as pd
from multiprocessing import Pool
from engine import *
SPLIT = pd.Timestamp("2026-09-01", tz="UTC")
df = None
def init():
    global df; df = load_1m()

TFSETS = {"all":(1,1,1,1,1), "no1m":(0,1,1,1,1), "15-60":(0,0,1,1,1), "60only":(0,0,0,0,1), "1-5":(1,1,0,0,0)}
DIVSETS = {"RB":(1,0,0,0), "RB+RR":(1,1,0,0), "all4":(1,1,1,1), "none":(0,0,0,0)}
LEVELS = {"off":None, "38/62":(38,62), "30/70":(30,70), "45/55":(45,55)}

def sig_configs():
    out=[]
    for tf,(L,R),(mn,mx),dh,dv,req4,lv,ts,fix in itertools.product(
        [1,5,15],[(3,3),(5,5),(8,8)],[(5,60),(10,120)],[0,13],DIVSETS,[False,True],LEVELS,TFSETS,[False,True]):
        if not req4 and not fix and ts!="all": continue      # toggles irrelevant as written
        if fix and ts=="all": continue                        # same as unfixed
        out.append(dict(chart_tf=tf,divL=L,divR=R,divMin=mn,divMax=mx,dayH=dh,div=dv,req4=req4,levels=lv,tfs=ts,fix=fix))
    return out

def exit_grid(full):
    g=[]
    sls=[200,500,1000,2000,5000,10000,20000,40000,80000] if full else [200,2000,10000,30000]
    tpm=[0.5,1,1.5,2,3,5] if full else [1,2,3]
    trails=[None,(0.5,0.25),(0.5,0.5),(1,0.25),(1,0.5)] if full else [None,(0.75,0.25)]
    for sl,m,tr in itertools.product(sls,tpm,trails):
        g.append((sl,int(sl*m),tr is not None, int(sl*tr[0]) if tr else 0, int(sl*tr[1]) if tr else 0))
    if not full: g.append((200,400,True,150,50))
    return g

COMM=0.0002  # per side (exchange taker ~0.02%); fee-free also reported for defaults

def run(args):
    cfg, full = args
    d=DIVSETS[cfg["div"]]; lv=LEVELS[cfg["levels"]]
    ch,L,S=signals(df,chart_tf=cfg["chart_tf"],divL=cfg["divL"],divR=cfg["divR"],divMin=cfg["divMin"],divMax=cfg["divMax"],
        dayH=cfg["dayH"],tfs_on=TFSETS[cfg["tfs"]],regBull=d[0],regBear=d[1],hidBull=d[2],hidBear=d[3],
        req4=cfg["req4"],levels=lv is not None,buyLevel=lv[0] if lv else 38,sellLevel=lv[1] if lv else 62,fix_toggles=cfg["fix"])
    o,h,l,c=(ch[k].to_numpy() for k in "ohlc")
    cut=np.searchsorted(ch.index.values, SPLIT.to_datetime64())
    rows=[]
    for (sl,tp,ut,a,f) in exit_grid(full):
        p,b,m=simulate(o,h,l,c,L,S,sl,tp,ut,a,f,TICK,COMM,1e4,0.01)
        isp=p[b<cut]; oos=p[b>=cut]
        def st(x):
            if x.size==0: return (0,0.0,np.nan,np.nan)
            gl=-x[x<0].sum(); return (x.size, 1e4*x.mean()/100, 100*(x>0).mean(), x[x>0].sum()/gl if gl>0 else np.inf)
        r=dict(cfg); r.update(sl=sl,tp=tp,trail=ut,act=a,off=f,nsig=int(L.sum()+S.sum()))
        for k,x in (("is",isp),("oos",oos),("all",p)):
            n,bp,w,pf=st(x); r.update({f"{k}_n":n,f"{k}_bp":bp,f"{k}_win":w,f"{k}_pf":pf})
        r["mdd"]=100*m
        rows.append(r)
    return rows

if __name__=="__main__":
    stage=sys.argv[1]
    if stage=="1":
        cfgs=sig_configs(); jobs=[(c,False) for c in cfgs]
    else:
        top=pd.read_pickle("stage2_cfgs.pkl"); jobs=[(c,True) for c in top]
    print(len(jobs),"signal configs",flush=True); t=time.time()
    with Pool(4,initializer=init) as P:
        res=[r for rows in P.imap_unordered(run,jobs,chunksize=4) for r in rows]
    pd.DataFrame(res).to_pickle(f"stage{stage}.pkl"); print("done",len(res),time.time()-t)
