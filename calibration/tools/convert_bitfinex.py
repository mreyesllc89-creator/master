"""Bitfinex 1m candles (ts_ms,open,close,high,low,volume) -> M1 npz with a synthetic
proportional spread (bid = mid - s/2, ask = mid + s/2).  Usage: convert_bitfinex.py <spread_pct> <out.npz> <merged.csv...>"""
import sys, numpy as np, pandas as pd
spread_pct = float(sys.argv[1]) / 100.0; out = sys.argv[2]
parts = []
for f in sys.argv[3:]:
    df = pd.read_csv(f, header=None, names=["ts", "o", "c", "h", "l", "v"])
    parts.append(df)
df = pd.concat(parts); df["t"] = (df["ts"] // 1000).astype(np.int64)
df = df.sort_values("t").drop_duplicates("t", keep="last")
df = df[(df.o > 0) & (df.h >= df.l) & (df.c > 0)]
# clip absurd single-minute spikes (bad prints) to 20% of close
df["h"] = np.minimum(df["h"], df["c"] * 1.2); df["l"] = np.maximum(df["l"], df["c"] * 0.8)
half = df["c"].values * spread_pct / 2.0
mk = lambda col: df[col].values.astype(np.float64)
np.savez_compressed(out, t=df["t"].values, bo=mk("o") - half, bh=mk("h") - half, bl=mk("l") - half, bc=mk("c") - half,
                    ao=mk("o") + half, ah=mk("h") + half, al=mk("l") + half, ac=mk("c") + half, n=np.ones(len(df), np.int32))
print("bars:", len(df), "from", pd.to_datetime(df.t.iloc[0], unit="s"), "to", pd.to_datetime(df.t.iloc[-1], unit="s"))
