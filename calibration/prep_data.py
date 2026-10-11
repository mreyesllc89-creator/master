"""Build UTC-aligned OHLC bars for every timeframe from Bitstamp BTC/USD 1-minute data.
Usage: python -I prep_data.py <historical.csv.gz> <latest.csv> <outdir>"""
import sys, numpy as np, pandas as pd
hist, latest, out = sys.argv[1], sys.argv[2], sys.argv[3]
start = int(pd.Timestamp("2023-01-01", tz="UTC").timestamp())
cols = ["timestamp", "open", "high", "low", "close", "volume"]
parts = []
for chunk in pd.read_csv(hist, usecols=cols, chunksize=2_000_000):
    chunk = chunk[chunk.timestamp >= start]
    if len(chunk): parts.append(chunk)
parts.append(pd.read_csv(latest, usecols=cols))
df = pd.concat(parts).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
df = df[(df.high >= df.low) & (df.close > 0)]
df.index = pd.to_datetime(df.timestamp, unit="s", utc=True)
df = df[["open", "high", "low", "close", "volume"]].astype("float64")
print("1m rows", len(df), df.index[0], "->", df.index[-1])
gaps = df.index.to_series().diff().dt.total_seconds().div(60)
print("1m gaps > 1 min:", int((gaps > 1).sum()), " largest:", float(gaps.max()), "min")
df.to_parquet(f"{out}/btc_1m.parquet")
agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
for tf, rule in [("5", "5min"), ("15", "15min"), ("30", "30min"), ("60", "1h"), ("120", "2h"),
                 ("240", "4h"), ("480", "8h"), ("1D", "1D")]:
    b = df.resample(rule, label="left", closed="left").agg(agg).dropna()
    b.to_parquet(f"{out}/btc_{tf}.parquet")
    print(f"{tf:>4}: {len(b):7d} bars  {b.index[0]} -> {b.index[-1]}")
