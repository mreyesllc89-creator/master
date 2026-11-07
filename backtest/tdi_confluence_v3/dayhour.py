"""Is the day-start hour a spike or a plateau? 5m defaults, SL 5xATR(60m), TP 2R."""
import numpy as np, pandas as pd
from finalists import run, BASE, tstat
rows = []
for chart in (5, 15):
    for dh in range(24):
        ch, L, S, r, eb, sd = run(dict(BASE, chart_tf=chart, dayH=dh), ("atr", 60, 5, 2, None))
        cut = ch.index[eb] >= pd.Timestamp("2026-09-01", tz="UTC")
        rows.append(dict(chart=chart, dayH=dh, trades=len(r), avg_bp=r.mean(), t=tstat(r), is_bp=r[~cut].mean(), oos_bp=r[cut].mean()))
R = pd.DataFrame(rows).round(1)
print(R.pivot(index="dayH", columns="chart", values=["trades", "avg_bp", "t", "is_bp", "oos_bp"]).to_string())
