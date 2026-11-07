import pandas as pd, numpy as np
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
d=pd.read_pickle("stage1.pkl"); print(len(d))
print("share of combos profitable (all data, 0.02% fees):", (d.all_bp>0).mean().round(3), " with >=30 trades:", ((d.all_bp>0)&(d.all_n>=30)).sum(),"/",(d.all_n>=30).sum())
q=d[d.is_n>=30]
print("\nIS-profitable (>=30 trades) ->share also OOS-profitable:", ((q.is_bp>0)&(q.oos_bp>0)).sum(), "/", (q.is_bp>0).sum())
for col in ["chart_tf","div","req4","levels","tfs","fix","dayH","divL"]:
    print("\n",q.groupby(col).agg(n=("is_n","size"),is_bp=("is_bp","median"),oos_bp=("oos_bp","median"),trades=("all_n","median")).round(2))
print("\nby SL:",q.groupby("sl").agg(is_bp=("is_bp","median"),oos_bp=("oos_bp","median"),win=("all_win","median")).round(2))
cols=["chart_tf","divL","divMin","dayH","div","req4","levels","tfs","fix","sl","tp","trail","is_n","is_bp","is_pf","oos_n","oos_bp","oos_pf","all_win","mdd"]
print("\nTop 25 by IS bp (>=40 IS trades):"); print(d[d.is_n>=40].sort_values("is_bp",ascending=False)[cols].head(25).round(2).to_string())
