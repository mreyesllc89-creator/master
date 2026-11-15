"""Compare the port with the author's MT5 basket logs on the only overlapping data: 2026-07-01 to
2026-08-31 (Octa M1 bid/ask here, Exness real ticks in MT5).
usage: python fidelity.py <CESTAS dir>"""
import sys, time
import numpy as np, pandas as pd
import common as C

d = C.load("XAUUSD", 2026)
t0, t1 = int(d["t"][0]), int(d["t"][-1])
p = C.shipped_for("XAUUSD")
rows = []
for name in ["cestas_2026_1ms.csv", "cestas_2026_189ms.csv", "cestas_2025-2026_189ms.csv"]:
    log = pd.read_csv(f"{sys.argv[1]}/{name}")
    start_bal = 1000 + log[log.end < t0].net.sum()
    w = log[(log.start >= t0 + 86400) & (log.start <= t1)]
    s = time.time()
    b = C.backtest(p, "XAUUSD", 2026, start_balance=start_bal, t_from=t0 + 86400, baskets=True)["baskets"]
    bc = C.backtest(p, "XAUUSD", 2026, start_balance=start_bal, t_from=t0 + 86400, baskets=True, coarse=True)["baskets"]
    for label, x in (("MT5 " + name[7:-4], w), ("port, interpolated ticks", b), ("port, M1 closes only", bc)):
        dur = (x.end - x.start) / 60
        g = x.groupby("reason").net.agg(["size", "sum"])
        rows.append(dict(run=label, start_balance=round(start_bal), baskets=len(x), net=round(x.net.sum()),
                         trail_n=int(g["size"].get("TRAIL", 0)), trail_net=round(g["sum"].get("TRAIL", 0)),
                         stop_n=int(g["size"].get("STOP_PCT_CESTA", 0)), stop_net=round(g["sum"].get("STOP_PCT_CESTA", 0)),
                         age_n=int(g["size"].get("EDAD_MAXIMA", 0)), age_net=round(g["sum"].get("EDAD_MAXIMA", 0)),
                         median_minutes=round(dur.median()), win_pct=round(100 * (x.net > 0).mean())))
out = pd.DataFrame(rows)
print(out.to_string(index=False))
out.to_csv("../results/fidelity_2026_jul_aug.csv", index=False)
