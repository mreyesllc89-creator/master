"""Shipped preset under execution assumptions from best to worst: interpolated ticks with 0 / 0.1 /
0.25 / 0.5 gold-USD adverse slippage per fill (x17.1 on bitcoin), then OHLC points only.
Each cell: final balance of a 1000 USD start on 1 January (2026: 1 July)."""
import pandas as pd
import common as C

rows = []
for sym in ["XAUUSD", "BTCUSD"]:
    p = C.shipped_for(sym); k = C.K_BTC if sym == "BTCUSD" else 1.0
    for y in C.years(sym):
        row = dict(symbol=sym, year=y)
        for s in (0.0, 0.1, 0.25, 0.5):
            r = C.backtest(p, sym, y, slip=s * k)
            row[f"interp slip {s}"] = round(r["final"])
        r = C.backtest(p, sym, y, coarse=True)
        row["OHLC points"] = round(r["final"]); row["OHLC dd%"] = round(r["dd"])
        rows.append(row)
df = pd.DataFrame(rows)
df.to_csv("../results/execution_sensitivity_shipped.csv", index=False)
print(df.to_string(index=False))

# granularity ladder: how far price may travel between two evaluations of the basket (gold USD)
rows = []
for sym in ["XAUUSD", "BTCUSD"]:
    p = C.shipped_for(sym); k = C.K_BTC if sym == "BTCUSD" else 1.0
    for y in C.years(sym):
        row = dict(symbol=sym, year=y)
        for st in (0.05, 0.25, 0.5, 1.0, 2.0, 4.0):
            row[f"step {st}"] = round(C.backtest(p, sym, y, step=st * k)["final"])
        rows.append(row)
df = pd.DataFrame(rows)
df.to_csv("../results/granularity_shipped.csv", index=False)
print(df.to_string(index=False))
