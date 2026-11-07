import pandas as pd, numpy as np
d=pd.read_pickle("stage1.pkl")
key=["chart_tf","divL","divR","divMin","divMax","dayH","div","req4","levels","tfs","fix"]
g=d.groupby(key).agg(is_bp=("is_bp","mean"),is_n=("is_n","max"),oos_n=("oos_n","max")).reset_index()
g=g[g.is_n>=30]
# dedupe signal-equivalent configs: same trade counts and stats across all exits
sig=d.groupby(key).apply(lambda x: hash(tuple(np.round(x.sort_values(["sl","tp","trail"]).all_bp.fillna(0).values,6)))).rename("h").reset_index()
g=g.merge(sig,on=key).sort_values("is_bp",ascending=False).drop_duplicates("h")
print(len(g),"distinct signal sets with >=30 IS trades")
top=g.head(60)
defaults=[dict(chart_tf=t,divL=5,divR=5,divMin=5,divMax=60,dayH=0,div="RB",req4=False,levels="off",tfs="all",fix=False) for t in (1,5,15)]
cfgs=defaults+[{k:(v.item() if hasattr(v,"item") else v) for k,v in r.items()} for r in top[key].to_dict("records")]
pd.to_pickle(cfgs,"stage2_cfgs.pkl"); print(len(cfgs))
