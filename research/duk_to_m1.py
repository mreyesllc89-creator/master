#!/usr/bin/env python3
"""Convert Dukascopy XAUUSD bi5 one-minute candles (BID and ASK, UTC) into the hump engine's input:
mid-price M1 bars indexed by broker server time (New York + 7h) and a per-bar half spread."""
import datetime as dt, glob, lzma, os, struct
import numpy as np, pandas as pd


def read_day(path, day):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6)
    t = pd.Timestamp(day) + pd.to_timedelta(a[:, 0].astype(np.int64), unit="s")
    px = a[:, 1:5].astype(float) / 1000.0                       # open, close, low, high
    vol = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5].astype(float)
    return pd.DataFrame(dict(open=px[:, 0], close=px[:, 1], low=px[:, 2], high=px[:, 3], vol=vol), index=t)


def load(folder):
    days = sorted({os.path.basename(f)[:10] for f in glob.glob(os.path.join(folder, "*_BID.bi5"))})
    parts = []
    for d in days:
        b = read_day(os.path.join(folder, f"{d}_BID.bi5"), d); a = read_day(os.path.join(folder, f"{d}_ASK.bi5"), d)
        if b is None or a is None:
            continue
        j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
        j = j[(j.vol_b > 0) | (j.vol_a > 0)]                       # Dukascopy fills closed minutes with flat bars
        parts.append(j)
    j = pd.concat(parts)
    m = pd.DataFrame({k: (j[f"{k}_b"] + j[f"{k}_a"]) / 2 for k in ("open", "high", "low", "close")})
    m["high"] = np.maximum(m["high"], m[["open", "close"]].max(axis=1))
    m["low"] = np.minimum(m["low"], m[["open", "close"]].min(axis=1))
    half = ((j["close_a"] - j["close_b"]).clip(lower=0) / 2).values
    utc = m.index.tz_localize("UTC")
    m.index = utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    keep = ~m.index.duplicated()
    return m[keep].sort_index(), half[keep]


if __name__ == "__main__":
    import sys
    m, h = load(sys.argv[1])
    print(m.index[0], m.index[-1], len(m), "median spread", round(np.median(h) * 2, 3))
