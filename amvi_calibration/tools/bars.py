"""1-minute bars and the higher timeframes built from them, as TradingView builds them
for a 24/7 symbol: a bar of timeframe T minutes opens at every multiple of T since
00:00 UTC (all timeframes used here divide a day evenly), contains the 1-minute bars
that open inside it, and is absent when none exists. A minute without a single trade is
not a bar (the exchange's kline files carry such minutes as flat filler rows).

Optionally the one-second bars inside each minute (fetch_1s.py), used by the order
simulation to follow the price second by second where an order could fill.

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


def load_1m(symbol="BTCUSDT", start=None, end=None, path=None, drop_empty=True):
    """Bars(1) from the merged parquet written by fetch_1m.py. start / end: 'YYYY-MM-DD' (UTC),
    start inclusive, end exclusive. drop_empty: leave out minutes with zero volume (no trade
    happened: TradingView has no bar there)."""
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
    if drop_empty:
        m = cols["volume"] > 0
        t = t[m]
        cols = {k: v[m] for k, v in cols.items()}
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


class Seconds:
    """One-second bars (only seconds with a trade): epoch seconds and prices times `mult`,
    all int32, plus per 1-minute bar the slice [s0, s1) of the seconds inside it and their
    highest and lowest price (hi, lo). The slice is empty when the minute has no seconds or
    when they contradict the minute's bar (another close, or a price outside its range)."""

    __slots__ = ("sec", "o", "h", "l", "c", "mult", "s0", "s1", "hi", "lo", "covered", "refused", "open_differs")

    def __init__(self, sec, o, h, l, c, mult):
        self.sec, self.o, self.h, self.l, self.c, self.mult = sec, o, h, l, c, float(mult)
        self.s0 = self.s1 = self.hi = self.lo = None
        self.covered = self.refused = self.open_differs = 0

    def __len__(self):
        return self.sec.size


def load_1s(symbol="BTCUSDT", start=None, end=None, folder=None):
    """Seconds from the monthly files written by fetch_1s.py; None when there is none in range.
    start / end: 'YYYY-MM-DD' (UTC), start inclusive, end exclusive."""
    folder = folder or os.path.join(DATA_DIR, "sec")
    s = pd.Timestamp(start or "2019-01-01")
    e = pd.Timestamp(end) if end else pd.Timestamp.now("UTC").tz_localize(None)
    parts = []
    for ym in pd.period_range(s.to_period("M"), (e - pd.Timedelta(seconds=1)).to_period("M"), freq="M"):
        p = os.path.join(folder, f"{symbol}_1s_{ym}.npz")
        if os.path.exists(p):
            z = np.load(p)
            parts.append((z["sec"], z["o"], z["h"], z["l"], z["c"]))
    if not parts:
        return None
    sec, o, h, l, c = (np.concatenate([q[k] for q in parts]) for k in range(5))
    lo = int(s.tz_localize("UTC").value // 10 ** 9)
    hi = int(e.tz_localize("UTC").value // 10 ** 9)
    a, b = np.searchsorted(sec, lo, side="left"), np.searchsorted(sec, hi, side="left")
    return Seconds(sec[a:b].copy(), o[a:b].copy(), h[a:b].copy(), l[a:b].copy(), c[a:b].copy(), 100)


@njit(cache=True)
def _attach(mt, mo, mh, ml, mc, sec, so, sh, sl, sc, mult):
    n = mt.size
    s0 = np.zeros(n, np.int64)
    s1 = np.zeros(n, np.int64)
    fh = np.zeros(n)
    fl = np.zeros(n)
    covered = 0
    bad = 0
    odiff = 0
    k = 0
    ns = sec.size
    tol = 0.5 / mult
    for j in range(n):
        t0 = mt[j] // 1000
        while k < ns and sec[k] < t0:
            k += 1
        a = k
        while k < ns and sec[k] < t0 + 60:
            k += 1
        if k == a:
            continue
        hi = sh[a]
        lo = sl[a]
        for q in range(a + 1, k):
            if sh[q] > hi:
                hi = sh[q]
            if sl[q] < lo:
                lo = sl[q]
        # the seconds must end at the minute's close and stay inside its range. The minute's
        # open may differ: the exchange's kline often opens at the previous close, not at the
        # first trade of the minute
        if abs(sc[k - 1] / mult - mc[j]) > tol or hi / mult > mh[j] + tol or lo / mult < ml[j] - tol:
            bad += 1
            continue
        if abs(so[a] / mult - mo[j]) > tol:
            odiff += 1
        s0[j] = a
        s1[j] = k
        fh[j] = hi / mult
        fl[j] = lo / mult
        covered += 1
    return s0, s1, fh, fl, covered, bad, odiff


def attach_seconds(m1, sec):
    """Fill, for every 1-minute bar, the slice of seconds inside it and their extremes."""
    sec.s0, sec.s1, sec.hi, sec.lo, sec.covered, sec.refused, sec.open_differs = _attach(
        m1.t, m1.o, m1.h, m1.l, m1.c, sec.sec, sec.o, sec.h, sec.l, sec.c, sec.mult)
    return sec


class Market:
    """The 1m bars, a cache of every timeframe built from them, and optionally the seconds."""

    def __init__(self, m1, sec=None):
        self.m1 = m1
        self._tf = {1: m1}
        self.sec = attach_seconds(m1, sec) if sec is not None else None

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
