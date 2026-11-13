import sys, os, numpy as np, pandas as pd
sys.path.insert(0,"/workspace/master/research")
import hump_engine as H, hump_search as X
L=pd.read_csv(sys.argv[1]); mk=H.Market()
def line(df):
    t=df.entry_time.values; r=df.r.values
    f=lambda a,b: H.stats(r[(t>=np.datetime64(a))&(t<np.datetime64(b))])
    a=f("2025-01-01","2026-01-01"); b=f("2026-01-01","2027-01-01"); c=f("2026-02-01","2027-01-01"); al=H.stats(r)
    q=[f(x,y)["pf"] for x,y in [("2025-01-01","2025-04-01"),("2025-04-01","2025-07-01"),("2025-07-01","2025-10-01"),("2025-10-01","2026-01-01"),("2026-01-01","2026-04-01"),("2026-04-01","2026-07-01")]]
    return f"2025 {a['pf']:.2f}({a['n']}) 2026 {b['pf']:.2f}({b['n']}) FebMay {c['pf']:.2f} all {al['pf']:.2f} net {al['net']:+.0f}R DD {al['dd']:.1f} | quarters "+" ".join(f"{x:.1f}" for x in q)
for i in [0,2,5,6,7,8,12]:
    p={k:X.cast(L.iloc[i][k],X.SPACE[k]) for k in X.SPACE}
    print(f"#{i} {p['tf']} sides={p['sides']} {p['session']} htf={p['htf']} spread x{os.environ.get('HUMP_SPREAD_MULT','1')}")
    p["max_spread"]=float(os.environ.get("HUMP_MAXSP","0.6"))
    print("   hump   :",line(mk.run(p)))
    print("   classic:",line(mk.run(dict(p,classic=1))))
