"""Seed strategy library. Each function takes a bar DataFrame (and optional extra series) and
returns a DataFrame with 'target' (-1/0/1) and 'stop' (price distance) using only data up to
each bar (shift where a value would otherwise peek). Mechanism for each edge is in its docstring;
an edge without a mechanism does not belong here."""
import numpy as np
import pandas as pd


def atr(df, n=14):
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _out(df, target, stop):
    return pd.DataFrame({"target": target.astype(int), "stop": stop}, index=df.index)


def range_breakout(df, lookback=288, tight_window=30, atr_mult=2.0, hold=48):
    """Breakout from the tightest N-bar range of the last `tight_window` days. Mechanism: compression
    -> expansion; stops of range traders and option gamma hedging pay. Loses in chop (false breaks)."""
    hi = df.high.rolling(lookback).max().shift(); lo = df.low.rolling(lookback).min().shift()
    width = (hi - lo) / df.close
    bars_per_day = int(round(86400 / (df.index[1] - df.index[0]).total_seconds()))
    tight = width <= width.rolling(tight_window * bars_per_day).quantile(0.1)
    a = atr(df)
    long_ = tight & (df.close > hi); short = tight & (df.close < lo)
    target = pd.Series(0, index=df.index); target[long_] = 1; target[short] = -1
    # hold for `hold` bars then flat
    target = target.replace(0, np.nan).ffill(limit=hold).fillna(0)
    return _out(df, target, a * atr_mult)


def funding_reset(df, funding, thresh=0.0003, hold=36, atr_mult=1.5):
    """After an extreme funding print (crowded longs pay shorts), fade the crowd for `hold` bars.
    Mechanism: funding is a tax on the crowded side; forced de-risking follows. Who pays: late leveraged
    longs/shorts. Dies when a real trend keeps funding high for weeks (2021 Q1, 2024 Q1)."""
    f = funding.reindex(df.index).ffill().shift()  # the last settled funding, known at the bar
    a = atr(df)
    target = pd.Series(0, index=df.index)
    target[f >= thresh] = -1; target[f <= -thresh] = 1
    target = target.replace(0, np.nan).ffill(limit=hold).fillna(0)
    return _out(df, target, a * atr_mult)


def btc_leads(df, btc, lookback=12, move=1.5, hold=24, atr_mult=1.5):
    """Alt follows a BTC move that it has not yet matched. Mechanism: index/ETF-driven BTC flow arrives
    first; alt market makers lag. Who pays: slow alt participants. Dies when alt/BTC correlation breaks
    (alt-specific news) or when the lag closes to minutes (2025+ crowding)."""
    b = btc.close.reindex(df.index).ffill()
    bret = b.pct_change(lookback) * 100; aret = df.close.pct_change(lookback) * 100
    gap = bret - aret
    a = atr(df)
    target = pd.Series(0, index=df.index)
    target[(bret > move) & (gap > move / 2)] = 1; target[(bret < -move) & (gap < -move / 2)] = -1
    target = target.replace(0, np.nan).ffill(limit=hold).fillna(0)
    return _out(df, target, a * atr_mult)


def oi_flush_continuation(df, metrics, oi_drop=0.03, lookback=12, hold=24, atr_mult=1.5):
    """After open interest drops > oi_drop in `lookback` bars with price down (long liquidations), go
    with the move for `hold` bars. Mechanism: forced liquidation cascades continue until OI stabilises.
    Who pays: liquidated leveraged traders. Dies in V-shaped reversals after cascades (needs tight stops)."""
    oi = metrics.set_index("time")["sum_open_interest"].astype(float).reindex(df.index).ffill().shift()
    doi = oi.pct_change(lookback); ret = df.close.pct_change(lookback)
    a = atr(df)
    target = pd.Series(0, index=df.index)
    target[(doi < -oi_drop) & (ret < 0)] = -1; target[(doi < -oi_drop) & (ret > 0)] = 1
    target = target.replace(0, np.nan).ffill(limit=hold).fillna(0)
    return _out(df, target, a * atr_mult)


def session_open_drift(df, hour_utc=13, direction_lookback=6, hold=6, atr_mult=1.5):
    """Trade the US cash open (13:30 UTC) in the direction of the pre-open drift. Mechanism: ETF creation
    flow and US desks arrive at a fixed clock; Asia/Europe positioning gets run. Who pays: pre-open
    positioners. Dies when ETF flow turns two-sided / volumes fall."""
    a = atr(df)
    pre = df.close.pct_change(direction_lookback)
    at_open = (df.index.hour == hour_utc) & (df.index.minute == 0)
    target = pd.Series(0, index=df.index)
    target[at_open & (pre > 0)] = 1; target[at_open & (pre < 0)] = -1
    target = target.replace(0, np.nan).ffill(limit=hold).fillna(0)
    return _out(df, target, a * atr_mult)


def donchian_trend(df, n=96, atr_mult=3.0):
    """Classic Donchian channel trend following; always in the market direction of the last breakout.
    Mechanism: trend persistence from slow capital flows; pays for itself only in strong trends. Kept
    as the boring benchmark every other idea must beat."""
    hi = df.high.rolling(n).max().shift(); lo = df.low.rolling(n).min().shift()
    target = pd.Series(np.nan, index=df.index)
    target[df.close > hi] = 1; target[df.close < lo] = -1
    target = target.ffill().fillna(0)
    return _out(df, target, atr(df) * atr_mult)


LIBRARY = {
    "range_breakout": (range_breakout, [dict(lookback=l, atr_mult=m, hold=h) for l in (144, 288) for m in (1.5, 2.5) for h in (24, 72)]),
    "donchian_trend": (donchian_trend, [dict(n=n, atr_mult=m) for n in (48, 96, 192) for m in (2.0, 3.0, 4.0)]),
    "session_open_drift": (session_open_drift, [dict(direction_lookback=d, hold=h) for d in (3, 6, 12) for h in (3, 6, 12)]),
}
LIBRARY_WITH_FUNDING = {
    "funding_reset": (funding_reset, [dict(thresh=t, hold=h) for t in (0.0002, 0.0003, 0.0005) for h in (12, 36, 72)]),
}
LIBRARY_WITH_BTC = {
    "btc_leads": (btc_leads, [dict(lookback=l, move=m, hold=h) for l in (6, 12) for m in (1.0, 2.0) for h in (12, 24)]),
}
LIBRARY_WITH_METRICS = {
    "oi_flush_continuation": (oi_flush_continuation, [dict(oi_drop=d, hold=h) for d in (0.02, 0.04) for h in (12, 24, 48)]),
}
