import pandas as pd, numpy as np
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
d=pd.read_pickle("stage2.pkl"); print(len(d))
cols=["chart_tf","divL","divMin","dayH","div","req4","levels","tfs","fix","sl","tp","trail","act","off","is_n","is_bp","is_pf","oos_n","oos_bp","oos_pf","all_n","all_win","all_pf","mdd"]
dfl=d[(d.divL==5)&(d.divMin==5)&(d.dayH==0)&(d["div"]=="RB")&(~d.req4)&(d.levels=="off")&(d.tfs=="all")&(~d.fix)]
print("\nDEFAULT signals, exit grid summary (median all-data bp by SL):")
print(dfl.groupby(["chart_tf","sl"]).all_bp.agg(["median","max"]).unstack(0).round(2))
print("\nDefault exits exact:"); print(dfl[(dfl.sl==200)&(dfl.tp==400)][cols].round(2).to_string()) if len((dfl[(dfl.sl==200)&(dfl.tp==400)])) else None
q=d[(d.is_n>=40)]
print("\nIS profitable:",(q.is_bp>0).sum(),"/",len(q)," of those OOS profitable:",((q.is_bp>0)&(q.oos_bp>0)).sum())
print("Spearman IS vs OOS bp:", q[["is_bp","oos_bp"]].corr("spearman").iloc[0,1].round(3))
top=q.sort_values("is_bp",ascending=False)
print("\nTop 20 by IS (selection), with OOS:"); print(top[cols].head(20).round(2).to_string())
# robust choice: profitable both halves, rank by min
r=q[(q.oos_n>=15)].assign(mn=lambda x: np.minimum(x.is_bp,x.oos_bp)).sort_values("mn",ascending=False)
print("\nBest by min(IS,OOS) bp:"); print(r[cols+["mn"]].head(15).round(2).to_string())
# t-stat of best all-data
