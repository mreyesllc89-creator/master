from engine import *
import itertools, time
TV=tv_paths(); MC=[mc_fast(100+s) for s in range(4)]
o=run(TV,O,H,L,C,ATR,sigA,P_(ta=0.02,td=0.02),0.0,0.0); print('validation gross TV current',o[:,2].sum(),len(o))
cfgs=[]
def add(style,**k): cfgs.append((style,k))
TPS=[0,1,2,3,5]
for tp in [1,1.5,2,3,4,5,7]: add('no trail (SL/TP only)',tp=tp)
A_=[0,0.02,0.05,0.1,0.2,0.3,0.5,0.75,1,1.5,2,3]; D_=[0.02,0.05,0.1,0.2,0.3,0.5,0.75,1,1.5,2,3]
for ta,td,tp,nd in itertools.product(A_,D_,TPS,[0,1,2,3,4]):
    add('tick trail' if nd==0 else 'tick trail after N candles',ta=ta,td=td,tp=tp,tNeed=nd)
for k,ba,nd,tp in itertools.product([0.5,0.75,1,1.5,2,2.5,3,4],[0,0.5,1,2],[0,1,2,3],[0,2,3,5]):
    add('chandelier (bar close)',bm=1,bk=k,bAct=ba,bNeed=nd,tp=tp)
for n,bf,ba,nd,tp in itertools.product([1,2,3,5,8],[0,0.1,0.25,0.5],[0,0.5,1],[0,1,2,3],[0,2,3,5]):
    add('N-bar low/high',bm=2,bn=n,bk=bf,bAct=ba,bNeed=nd,tp=tp)
for k,ba,nd,tp in itertools.product([0.5,0.75,1,1.5,2,3],[0,0.5,1],[0,1,2,3],[0,2,3,5]):
    add('close - k ATR',bm=3,bk=k,bAct=ba,bNeed=nd,tp=tp)
for beA,beO in [(0.5,0.05),(1,0.05),(1,0.3),(1.5,0.3),(2,0.5)]:
    for tp in [0,2,3,5]: add('breakeven only',beA=beA,beO=beO,tp=tp)
    for k,tp in itertools.product([1,1.5,2,3],[0,3,5]): add('breakeven + chandelier',beA=beA,beO=beO,bm=1,bk=k,tp=tp)
    for n,tp in itertools.product([2,3,5],[0,3,5]): add('breakeven + N-bar',beA=beA,beO=beO,bm=2,bn=n,bk=0.1,tp=tp)
    for ta,td,tp in itertools.product([0.5,1,2],[0.5,1,2],[0,5]): add('breakeven + tick trail',beA=beA,beO=beO,ta=ta,td=td,tp=tp)
for tst,tp in itertools.product([1,2,3,4,6,8,12,16,24,32],[0,2,3,5]): add('time stop only',tst=tst,tp=tp)
print(len(cfgs))
rows=[]
for style,k in cfgs:
    p=P_(**k);row=dict(style=style,**k)
    for nm,sg in (('A',sigA),('B',sigB)):
        o=run(TV,O,H,L,C,ATR,sg,p,0.0,0.0); row[nm+'_tv']=o[:,2].sum()
        g=[];ea=[];ia=[];g1=[];g2=[];w=[];dd=[]
        for M in MC:
            o=run(M,O,H,L,C,ATR,sg,p,0.0,0.0);ei=o[:,0].astype(np.int64);h=len(o)//2
            g.append(o[:,2].sum());ea.append((C[ei]/ATR[ei]).sum());ia.append((1/ATR[ei]).sum());g1.append(o[:h,2].sum());g2.append(o[h:,2].sum())
            net=o[:,2]-0.0004*C[ei]/ATR[ei];w.append((net>0).mean()*100);dd.append(stats(net)['dd'])
        row.update({nm+'_g':np.mean(g),nm+'_gmin':np.min(g),nm+'_ea':np.mean(ea),nm+'_ia':np.mean(ia),nm+'_g1':np.mean(g1),nm+'_g2':np.mean(g2),nm+'_n':len(o),nm+'_win':np.mean(w),nm+'_dd':np.mean(dd),nm+'_bars':(o[:,1]-o[:,0]).mean()})
    rows.append(row)
pd.DataFrame(rows).to_csv(os.path.join(U,'..','results','sweep.csv'),index=False)
