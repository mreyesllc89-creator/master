"""Bitstamp BTC/USD 1-minute data from 2018-01-01 (2018-2019: dry run and warm-up only), UTC.
Usage: python -I prep_long.py <historical.csv.gz> <latest.csv> <out.parquet>"""
import sys, pandas as pd
hist, latest, out = sys.argv[1], sys.argv[2], sys.argv[3]
start = int(pd.Timestamp("2018-01-01", tz="UTC").timestamp())
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
g = df.index.to_series().diff().dt.total_seconds().div(60)
print("gaps > 1 min:", int((g > 1).sum()), " > 60 min:", int((g > 60).sum()), " largest:", float(g.max()), "min at", g.idxmax())
for y in range(2018, 2027):
    s = g[g.index.year == y]
    print(y, "rows", int((df.index.year == y).sum()), "gaps>1m", int((s > 1).sum()), "missing min", int((s[s > 1] - 1).sum()),
          "zero-volume share", round(float((df.volume[df.index.year == y] == 0).mean()), 3))
df.to_parquet(out)
