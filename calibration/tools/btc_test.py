import sys, time; sys.path.insert(0,'/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad/tools')
import numpy as np, rt_model as rt, btc_model as bm
D='/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad/data'
for label, years in [("bitfinex 2015-2019",[2015,2016,2017,2018,2019]),("broker 2026",[2026])]:
    m1=rt.load_m1(D,years,"btcusd"); mkt=rt.Market(m1); bt=bm.BtcBacktester(mkt)
    yrs=(m1["t"][-1]-m1["t"][0])/86400/365.25
    print("==",label,"M1 bars",len(m1["t"]))
    for tf in ["M15","H1","H4"]:
        for method in range(6):
            sig=dict(bm.SIG_DEFAULTS); sig["chart_tf"]=tf; sig["method"]=method
            t=time.time(); S=bt.signals(sig); st,tr,eq=bt.run(sig, bm.ea_params()); dt=time.time()-t
            s=bm.summarize(st,tr,eq,10000,yrs)
            print(f"  {tf} method {method}: signals {int((S['side']!=0).sum())} trades {s['trades']} ret {s['ret_pct']:.1f}% pf {s['pf']:.2f} dd {s['max_dd_pct']:.1f}% avgR {s['avg_r']:.2f} sqn {s['sqn']:.2f} ({dt:.1f}s)")
