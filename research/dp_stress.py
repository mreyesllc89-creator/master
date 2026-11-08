import os, sys, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/master/research")
import dp_engine as D, dp_search as X
sym, src = sys.argv[1], sys.argv[2]
X.init(sym)
sp = X.space(sym)
L = pd.read_csv(src)
rows = []
for i, r in L.head(12).iterrows():
    p = {k: X._cast(r[k], sp[k]) for k in sp}
    for name, extra in [("barclose", dict(intrabar=0)), ("tick", dict(intrabar=1))]:
        cfg = X.to_cfg(sym, p); cfg.update(extra)
        df = X.MK.run(int(p["tf"]), cfg)
        t = df.entry_time.values
        m26 = t >= np.datetime64("2026-01-01"); fm = t >= np.datetime64("2026-02-01")
        rows.append(dict(i=i, mode=name, spread=os.environ.get("DP_SPREAD_MULT", os.environ.get("DP_BTC_SPREAD", "base")),
                         n26=int(m26.sum()), pf26=X.pf_of(df.pnl.values[m26]), pf_febmay=X.pf_of(df.pnl.values[fm]),
                         pf25=X.pf_of(df.pnl.values[~m26])))
print(pd.DataFrame(rows).round(2).to_string())
