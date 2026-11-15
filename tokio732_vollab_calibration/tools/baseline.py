"""Shipped preset, every year as an independent 1000 USD start (BTCUSD: scale-equivalent transform)."""
import time
import numpy as np, pandas as pd
import common as C, engine as E

rows = []
for sym in ["XAUUSD", "BTCUSD"]:
    p = C.shipped_for(sym)
    for y in C.years(sym):
        for label, kw in (("base", {}), ("spread x2", dict(spread_mult=2.0)),
                          ("slip", dict(slip=0.5 * C.SPEC[sym]["spread"]))):
            s = time.time()
            r = C.backtest(p, sym, y, **kw)
            rs = r["reason"]
            rows.append(dict(symbol=sym, year=y, test=label, scale=round(C.load(sym, y)["c"], 2), baskets=r["n"],
                             net=round(r["net"]), final=round(r["final"]), dd_pct=round(r["dd"], 1),
                             trail=int((rs == E.R_TRAIL).sum()), stop=int((rs == E.R_STOP).sum()),
                             age=int((rs == E.R_AGE).sum()), mean_r_pct=round(100 * r["r"].mean(), 2) if r["n"] else 0,
                             secs=round(time.time() - s, 1)))
            print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv("../results/baseline.csv", index=False)
