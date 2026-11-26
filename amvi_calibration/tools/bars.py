"""1-minute bars and the higher timeframes built from them, as TradingView builds them
for a 24/7 symbol: a bar of timeframe T minutes opens at every multiple of T since
00:00 UTC (all timeframes used here divide a day evenly), contains the 1-minute bars
that open inside it, and is absent when none exists.

All times are integer milliseconds since the epoch (bar OPEN time).
"""
import os

import numpy as np
import pandas as pd
from numba import njit

MIN_MS = 60_000
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class Bars:
    """OHLC arrays of one timeframe plus, per bar, the slice [i0, i1) of 1m rows inside it."""

    __slots__ = ("tf", "t", "o", "h", "l", "c", "v", "i0", "i1")

    def __init__(self, tf, t, o, h, l, c, v, i0, i1):
        self.tf, self.t, self.o, self.h, self.l, self.c, self.v, self.i0, self.i1 = tf, t, o, h, l, c, v, i0, i1

    def __len__(self):
        return self.t.size

    @property
    def tf_ms(self):
        return self.tf * MIN_MS

    @property
    def t_close(self):
        return self.t + self.tf * MIN_MS


def load_1m(symbol="BTCUSDT", start=None, end=None, path=None):
    """Bars(1) from the merged parquet written by fetch_1m.py. start / end: 'YYYY-MM-DD' (UTC),
    start inclusive, end exclusive."""
    path = path or os.path.join(DATA_DIR, f"{symbol}_1m.parquet")
    df = pd.read_parquet(path, columns=["open_time", "open", "high", "low", "close", "volume"])
    t = df["open_time"].to_numpy(np.int64)
    if t[-1] > 10 ** 14:  # microseconds in recent archive files
        t = np.where(t > 10 ** 14, t // 1000, t)
    order = np.argsort(t, kind="stable")
    t = t[order]
    keep = np.ones(t.size, bool)
    keep[1:] = t[1:] != t[:-1]
    cols = {k: df[k].to_numpy(np.float64)[order][keep] for k in ("open", "high", "low", "close", "volume")}
    t = t[keep]
    if start is not None:
        s = int(pd.Timestamp(start, tz="UTC").value // 10 ** 6)
        m = t >= s
        t = t[m]
        cols = {k: v[m] for k, v in cols.items()}
    if end is not None:
        e = int(pd.Timestamp(end, tz="UTC").value // 10 ** 6)
        m = t < e
        t = t[m]
        cols = {k: v[m] for k, v in cols.items()}
    n = t.size
    idx = np.arange(n, dtype=np.int64)
    return Bars(1, t, cols["open"], cols["high"], cols["low"], cols["close"], cols["volume"], idx, idx + 1)


@njit(cache=True)
def _agg(t, o, h, l, c, v, tf_ms):
    n = t.size
    key = t // tf_ms
    nb = 1
    for i in range(1, n):
        if key[i] != key[i - 1]:
            nb += 1
    T = np.empty(nb, np.int64)
    O = np.empty(nb)
    H = np.empty(nb)
    L = np.empty(nb)
    C = np.empty(nb)
    V = np.empty(nb)
    I0 = np.empty(nb, np.int64)
    I1 = np.empty(nb, np.int64)
    b = -1
    for i in range(n):
        if i == 0 or key[i] != key[i - 1]:
            b += 1
            T[b] = key[i] * tf_ms
            O[b] = o[i]
            H[b] = h[i]
            L[b] = l[i]
            V[b] = 0.0
            I0[b] = i
        if h[i] > H[b]:
            H[b] = h[i]
        if l[i] < L[b]:
            L[b] = l[i]
        C[b] = c[i]
        V[b] += v[i]
        I1[b] = i + 1
    return T, O, H, L, C, V, I0, I1


def aggregate(m1, tf):
    """Bars of timeframe tf (minutes) from Bars(1)."""
    if tf == 1:
        return m1
    T, O, H, L, C, V, I0, I1 = _agg(m1.t, m1.o, m1.h, m1.l, m1.c, m1.v, tf * MIN_MS)
    return Bars(tf, T, O, H, L, C, V, I0, I1)


class Market:
    """The 1m bars and a cache of every timeframe built from them."""

    def __init__(self, m1):
        self.m1 = m1
        self._tf = {1: m1}

    def tf(self, minutes):
        b = self._tf.get(minutes)
        if b is None:
            b = aggregate(self.m1, minutes)
            self._tf[minutes] = b
        return b


def tf_minutes(tf):
    """Minutes of a TradingView timeframe string ('5', '60', '240', 'D')."""
    tf = str(tf)
    if tf in ("D", "1D"):
        return 1440
    return int(tf)
