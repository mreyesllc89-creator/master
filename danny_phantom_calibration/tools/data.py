"""M1 bid/ask npz -> timeframe bars with New York clock fields.

npz layout (calibration/data/<sym>_m1_<year>.npz on origin/claude/sharp-brown-qqghvg):
t (UTC seconds, minute open), bo/bh/bl/bc bid OHLC, ao/ah/al/ac ask OHLC, n tick count.
"""
import glob
import os

import numpy as np
import pandas as pd

SEGMENTS = {
    "XAUUSD": [("2011-2018", range(2011, 2019)), ("2026", [2026])],
    "BTCUSD": [("2015-2019", range(2015, 2020)), ("2026", [2026])],
}


def load_m1(data_dir, symbol, years):
    parts = []
    for y in years:
        f = os.path.join(data_dir, f"{symbol.lower()}_m1_{y}.npz")
        if os.path.exists(f):
            z = np.load(f, allow_pickle=False)
            parts.append({k: z[k] for k in z.files})
    if not parts:
        raise FileNotFoundError(f"no {symbol} npz for {list(years)} in {data_dir}")
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def ny_offset_seconds(utc):
    idx = pd.to_datetime(utc, unit="s", utc=True)
    local = idx.tz_convert("America/New_York")
    naive = local.tz_localize(None).values.astype("datetime64[s]").astype(np.int64)
    return naive - np.asarray(utc, dtype=np.int64)


def resample(m1, tf):
    """tf in minutes. Intraday bins align to UTC; H4+ bins align to the 17:00 NY session."""
    t = m1["t"].astype(np.int64)
    off = ny_offset_seconds(t)
    if tf < 120:
        key = t // (tf * 60)
    else:
        key = (t + off - (1020 % tf) * 60) // (tf * 60)
    brk = np.flatnonzero(np.diff(key)) + 1
    starts = np.concatenate([[0], brk])
    ends = np.concatenate([brk, [len(t)]]) - 1
    out = {
        "bo": m1["bo"][starts], "bc": m1["bc"][ends],
        "bh": np.maximum.reduceat(m1["bh"], starts), "bl": np.minimum.reduceat(m1["bl"], starts),
        "ao": m1["ao"][starts], "ac": m1["ac"][ends],
        "ah": np.maximum.reduceat(m1["ah"], starts), "al": np.minimum.reduceat(m1["al"], starts),
        "v": np.add.reduceat(m1["n"].astype(np.float64), starts),
    }
    k = key[starts]
    if tf < 120:
        open_utc = k * tf * 60
        local = open_utc + ny_offset_seconds(open_utc)
    else:
        local = k * tf * 60 + (1020 % tf) * 60
        open_utc = local - off[starts]
    lt = pd.to_datetime(local, unit="s")
    out["utc"] = open_utc
    out["dow"] = ((lt.dayofweek.values + 1) % 7 + 1).astype(np.int64)  # Pine: 1=Sun .. 7=Sat
    out["hour"] = lt.hour.values.astype(np.int64)
    out["minute"] = lt.minute.values.astype(np.int64)
    out["year"] = lt.year.values.astype(np.int64)
    return out


# Spread models. "recorded" keeps the broker bid/ask in the npz (2011-2018 gold spreads were
# $0.25-0.40, three times today's). "modern" rebuilds bid/ask around the mid with the spread
# seen in the 2026 export: XAUUSD $0.12 absolute, BTCUSD 2.2 bp of price.
# "mid" is TradingView's default: no spread at all.
MODERN = {"XAUUSD": ("abs", 0.12), "BTCUSD": ("bp", 2.2)}


def with_spread(bars, symbol, model):
    if model == "recorded":
        return bars
    kind, val = ("abs", 0.0) if model == "mid" else MODERN[symbol]
    out = dict(bars)
    for k in ("o", "h", "l", "c"):
        mid = 0.5 * (bars["b" + k] + bars["a" + k])
        half = val / 2 if kind == "abs" else mid * val / 2e4
        out["b" + k] = mid - half
        out["a" + k] = mid + half
    return out


def load_bars(data_dir, symbol, tf, cache_dir=None):
    segs = []
    for name, years in SEGMENTS[symbol]:
        cf = cache_dir and os.path.join(cache_dir, f"{symbol}_{name}_{tf}.npz")
        if cf and os.path.exists(cf):
            z = np.load(cf)
            bars = {k: z[k] for k in z.files}
        else:
            bars = resample(load_m1(data_dir, symbol, years), tf)
            if cf:
                os.makedirs(cache_dir, exist_ok=True)
                np.savez(cf, **bars)
        segs.append((name, bars))
    return segs
