import sys, os, json
sys.path.insert(0,'/tmp/claude-0/-home-user-master/132b1502-5b33-502e-bebd-2c02a6cae884/scratchpad/tools')
import numpy as np, pandas as pd, rt_model as rt, sweep
m1 = rt.load_m1(sweep.DATA, sweep.YEARS); mkt = rt.Market(m1); bt = rt.Backtester(mkt)
rows=[]
for tf in ["M5","M15","M30","H1"]:
    ind=dict(rt.IND_DEFAULTS); ind["chart_tf"]=tf
    for wname,(a,b) in sweep.DEFAULT_WINDOWS.items():
        st,tr,eq = bt.run(ind, rt.ea_params(), t_from=sweep._epoch(a), t_to=sweep._epoch(b))
        s = rt.summarize(st,tr,eq,10000,sweep._years_between(a,b)); s["tf"]=tf; s["window"]=wname; rows.append(s)
        if wname=="all":
            pd.DataFrame(tr, columns=["entry_bar","exit_bar","side","entry","exit","lots","pnl","reason","R","t_in","t_out","balance"]).assign(
                t_in=lambda d: pd.to_datetime(d.t_in,unit="s"), t_out=lambda d: pd.to_datetime(d.t_out,unit="s")).to_csv(f"data/baseline_trades_{tf}.csv", index=False)
df=pd.DataFrame(rows); df.to_csv("data/baseline.csv",index=False)
pd.set_option("display.width",250)
print(df[["tf","window","trades","net","ret_pct","cagr_pct","pf","win_pct","max_dd_pct","avg_r","sqn","max_loss_streak","exit_sl_pct"]].round(2).to_string())
