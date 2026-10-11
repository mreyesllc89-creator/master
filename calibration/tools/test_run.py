import sys, time, numpy as np
sys.path.insert(0, '/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad/tools')
import rt_model as rt
D='/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad/data'
m1 = rt.load_m1(D, [2018])
mkt = rt.Market(m1)
bt = rt.Backtester(mkt)
for tf in ["M5","M15","M30","H1"]:
    ind = dict(rt.IND_DEFAULTS); ind["chart_tf"]=tf
    t=time.time()
    I = bt.indicators(ind)
    cb = mkt.bars(tf)
    n=len(cb["t"]); 
    st = I["state"]
    print(tf, "bars", n, "ind time %.2fs"%(time.time()-t), "states: up",(st==1).sum(),"down",(st==-1).sum(),"range",(st==0).sum(),"neutral",(st==2).sum(),"unset",(st==-999).sum(),
          "macro up/down/flat/unset", [(I["macro"]==v).sum() for v in (1,-1,0,-2)], "ER valid", (I["er"]>=0).sum())
    ea = rt.ea_params()
    t=time.time()
    stats, trades, eq = bt.run(ind, ea)
    dt=time.time()-t
    t=time.time(); stats, trades, eq = bt.run(ind, ea); dt2=time.time()-t
    yrs = (m1["t"][-1]-m1["t"][0])/86400/365.25
    print("  bt first %.2fs second %.3fs"%(dt,dt2), rt.summarize(stats, trades, eq, 10000, yrs))
    if tf=="M15":
        np.set_printoptions(suppress=True, linewidth=200, precision=2)
        for tr in trades[:8]:
            print("   ", tr[:9], np.datetime64(int(tr[9]),'s'), np.datetime64(int(tr[10]),'s'))
