#!/usr/bin/env python3
"""Convert Dukascopy bi5 one-minute candles (BID and ASK, UTC) into the hump engine's input:
mid-price M1 bars (with a tick-volume column) indexed by broker server time (New York + 7h) and a per-bar half spread."""
import datetime as dt, glob, lzma, os, struct
import numpy as np, pandas as pd

# price unit of the bi5 integers, by Dukascopy instrument (DUK_INSTRUMENT, default XAUUSD)
DIVISOR = {"XAUUSD": 1000.0, "EURUSD": 100000.0, "USA500IDXUSD": 1000.0}[os.environ.get("DUK_INSTRUMENT", "XAUUSD")]


def read_day(path, day):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    raw = lzma.decompress(open(path, "rb").read())
    a = np.frombuffer(raw, dtype=">i4").reshape(-1, 6)
    t = pd.Timestamp(day) + pd.to_timedelta(a[:, 0].astype(np.int64), unit="s")
    px = a[:, 1:5].astype(float) / DIVISOR                      # open, close, low, high
    vol = np.frombuffer(raw, dtype=">f4").reshape(-1, 6)[:, 5].astype(float)
    return pd.DataFrame(dict(open=px[:, 0], close=px[:, 1], low=px[:, 2], high=px[:, 3], vol=vol), index=t)


def load(folder, keep_moving=False):
    """keep_moving=True (hump_wf protocol 2): a minute with volume 0 on both sides is dropped only when it is flat on both
    sides (Dukascopy's fill bar of a closed minute); one whose BID or ASK prices move is a quote without a volume figure
    (US500 2013-2017, EURUSD 2024-10-10) and is kept with vol = NaN (volume unknown). Default: every minute with volume 0
    on both sides is dropped, as for gold."""
    days = sorted({os.path.basename(f)[:10] for f in glob.glob(os.path.join(folder, "*_???.bi5"))})
    parts = []; half_missing = []
    for d in days:
        b = read_day(os.path.join(folder, f"{d}_BID.bi5"), d); a = read_day(os.path.join(folder, f"{d}_ASK.bi5"), d)
        if (b is None) != (a is None):
            half_missing.append(d)                 # one side failed to download: the day would be silently lost
        if b is None or a is None:
            continue
        j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
        if keep_moving:
            v0 = (j.vol_b == 0) & (j.vol_a == 0)
            j = j[~(v0 & (j.high_b == j.low_b) & (j.high_a == j.low_a))]
        else:
            j = j[(j.vol_b > 0) | (j.vol_a > 0)]                   # Dukascopy fills closed minutes with flat bars
        parts.append(j)
    if half_missing:
        raise SystemExit(f"Dukascopy data incomplete: BID or ASK file missing for {half_missing}. Re-run duk_download.py.")
    j = pd.concat(parts)
    m = pd.DataFrame({k: (j[f"{k}_b"] + j[f"{k}_a"]) / 2 for k in ("open", "high", "low", "close")})
    m["high"] = np.maximum(m["high"], m[["open", "close"]].max(axis=1))
    m["low"] = np.minimum(m["low"], m[["open", "close"]].min(axis=1))
    m["vol"] = (j["vol_b"] + j["vol_a"]).values                    # tick volume of the two sides (relative use only)
    if keep_moving:                                                 # the kept minutes without a volume figure
        m["vol"] = np.where((j["vol_b"].values == 0) & (j["vol_a"].values == 0), np.nan, m["vol"].values)
    half = ((j["close_a"] - j["close_b"]).clip(lower=0) / 2).values
    utc = m.index.tz_localize("UTC")
    m.index = utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
    keep = ~m.index.duplicated()
    # one ordering for the bars and their half spread (a bar of the hour that repeats when New York leaves summer time
    # could come out of order; the two would then no longer match)
    o = np.argsort(m.index[keep].values, kind="stable")
    return m[keep].iloc[o], half[keep][o]


if __name__ == "__main__":
    import sys
    m, h = load(sys.argv[1])
    print(m.index[0], m.index[-1], len(m), "median spread", round(np.median(h) * 2, 3))
