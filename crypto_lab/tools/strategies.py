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


def _hold(df, target, hold):
    return target.replace(0, np.nan).ffill(limit=hold).fillna(0)


def crowded_unwind(df, metrics, ratio=2.5, oi_drop=0.03, lookback=24, hold=24, atr_mult=1.5):
    """Top-trader long/short account ratio above `ratio` while OI falls > oi_drop over `lookback` bars and price is
    down: short the unwind. Mechanism: over-positioned longs are forced out leg by leg; leveraged longs pay. Dies when
    a short squeeze starts from the same crowded state (ratio stays high but OI rises)."""
    m = metrics.set_index("time")
    r = m["count_toptrader_long_short_ratio"].astype(float).reindex(df.index).ffill().shift()
    oi = m["sum_open_interest"].astype(float).reindex(df.index).ffill().shift()
    doi = oi.pct_change(lookback); ret = df.close.pct_change(lookback)
    target = pd.Series(0, index=df.index)
    target[(r > ratio) & (doi < -oi_drop) & (ret < 0)] = -1
    target[(r < 1 / ratio) & (doi < -oi_drop) & (ret > 0)] = 1
    return _out(df, _hold(df, target, hold), atr(df) * atr_mult)


def oi_flush_reversal(df, metrics, oi_drop=0.03, lookback=12, confirm_bars=1, hold=12, atr_mult=1.5):
    """After an OI flush with price down, go long once a close recovers above the flush window's midpoint.
    Mechanism: cascades overshoot and market makers refill; panic sellers at the lows pay. Dies in a real trend
    change where the flush is the first leg of many."""
    oi = metrics.set_index("time")["sum_open_interest"].astype(float).reindex(df.index).ffill().shift()
    doi = oi.pct_change(lookback); ret = df.close.pct_change(lookback)
    flush = (doi < -oi_drop) & (ret < 0)
    mid = (df.high.rolling(lookback).max() + df.low.rolling(lookback).min()) / 2
    recovered = df.close > mid.shift(confirm_bars)
    armed = flush.replace(False, np.nan).ffill(limit=lookback).fillna(False).astype(bool)
    target = pd.Series(0, index=df.index); target[armed & recovered & ~flush] = 1
    return _out(df, _hold(df, target, hold), atr(df) * atr_mult)


def asia_open_fade(df, atr_mult=1.0, hold=6, stop_mult=1.5):
    """Fade the first bar after 00:00 UTC when it moves more than atr_mult ATR. Mechanism: thin Asian liquidity
    overshoots and Europe refills; Asia breakout chasers pay. Dies on genuine overnight news (then the move extends)."""
    a = atr(df)
    first = (df.index.hour == 0) & (df.index.minute == 0)
    move = df.close - df.open
    target = pd.Series(0, index=df.index)
    target[first & (move > a * atr_mult)] = -1; target[first & (move < -a * atr_mult)] = 1
    return _out(df, _hold(df, target, hold), a * stop_mult)


def weekend_fade(df, atr_mult=1.5, stop_mult=2.0):
    """Fade a bar move > atr_mult ATR between Saturday 00:00 and Sunday 12:00 UTC; hold until Monday 00:00 UTC.
    Mechanism: weekend books are thin, stop-runs reverse when liquidity returns; weekend stop-hunt victims pay.
    Dies when weekend news is real (exchange hacks, geopolitics)."""
    a = atr(df)
    wk = (df.index.dayofweek == 5) | ((df.index.dayofweek == 6) & (df.index.hour < 12))
    move = df.close - df.open
    raw = pd.Series(0, index=df.index); raw[wk & (move > a * atr_mult)] = -1; raw[wk & (move < -a * atr_mult)] = 1
    target = raw.replace(0, np.nan).ffill().fillna(0)
    target[df.index.dayofweek <= 4] = 0  # flat from Monday 00:00 UTC through Friday
    return _out(df, target, a * stop_mult)


def funding_time_premium(df, funding, thresh=0.0002, bars_before=2, atr_mult=1.0):
    """Short the last `bars_before` bars before each 8-hour funding timestamp when the last funding print was above
    `thresh` (long when below -thresh); flat at the print. Mechanism: the perp premium decays into the funding
    exchange; longs paying funding pay. Dies when funding stays elevated because of a sustained trend (premium
    persists)."""
    f = funding.reindex(df.index).ffill().shift()
    bars_per_hour = int(round(3600 / (df.index[1] - df.index[0]).total_seconds()))
    into = pd.Series(df.index, index=df.index)
    mins_to_print = ((8 - (df.index.hour % 8)) * 60 - df.index.minute) % 480
    window = (mins_to_print > 0) & (mins_to_print <= bars_before * 60 / bars_per_hour)
    target = pd.Series(0, index=df.index)
    target[window & (f > thresh)] = -1; target[window & (f < -thresh)] = 1
    return _out(df, target, atr(df) * atr_mult)


def taker_exhaustion(df, metrics, q=0.95, window=720, fail_bars=6, hold=12, atr_mult=1.5):
    """Taker buy/sell volume ratio in its top q-quantile of `window` bars while price fails to make a new
    `fail_bars` high: short (mirror for the bottom quantile). Mechanism: aggressive flow absorbed by passive
    sellers; late market buyers pay. Dies in breakouts where absorption finally gives way."""
    tk = metrics.set_index("time")["sum_taker_long_short_vol_ratio"].astype(float).reindex(df.index).ffill().shift()
    hi_q = tk.rolling(window).quantile(q); lo_q = tk.rolling(window).quantile(1 - q)
    no_new_high = df.close < df.high.rolling(fail_bars).max().shift()
    no_new_low = df.close > df.low.rolling(fail_bars).min().shift()
    target = pd.Series(0, index=df.index)
    target[(tk > hi_q) & no_new_high] = -1; target[(tk < lo_q) & no_new_low] = 1
    return _out(df, _hold(df, target, hold), atr(df) * atr_mult)


LIBRARY = {
    "range_breakout": (range_breakout, [dict(lookback=l, atr_mult=m, hold=h) for l in (144, 288) for m in (1.5, 2.5) for h in (24, 72)]),
    "donchian_trend": (donchian_trend, [dict(n=n, atr_mult=m) for n in (48, 96, 192) for m in (2.0, 3.0, 4.0)]),
    "session_open_drift": (session_open_drift, [dict(direction_lookback=d, hold=h) for d in (3, 6, 12) for h in (3, 6, 12)]),
    "asia_open_fade": (asia_open_fade, [dict(atr_mult=a, hold=h) for a in (0.75, 1.0, 1.5) for h in (3, 6, 12)]),
    "weekend_fade": (weekend_fade, [dict(atr_mult=a, stop_mult=s) for a in (1.0, 1.5, 2.0) for s in (1.5, 2.5)]),
}
LIBRARY_WITH_FUNDING = {
    "funding_reset": (funding_reset, [dict(thresh=t, hold=h) for t in (0.0002, 0.0003, 0.0005) for h in (12, 36, 72)]),
    "funding_time_premium": (funding_time_premium, [dict(thresh=t, bars_before=b) for t in (0.0001, 0.0002, 0.0004) for b in (1, 2)]),
}
LIBRARY_WITH_BTC = {
    "btc_leads": (btc_leads, [dict(lookback=l, move=m, hold=h) for l in (6, 12) for m in (1.0, 2.0) for h in (12, 24)]),
}
LIBRARY_WITH_METRICS = {
    "oi_flush_continuation": (oi_flush_continuation, [dict(oi_drop=d, hold=h) for d in (0.02, 0.04) for h in (12, 24, 48)]),
    "oi_flush_reversal": (oi_flush_reversal, [dict(oi_drop=d, hold=h) for d in (0.02, 0.04) for h in (6, 12, 24)]),
    "crowded_unwind": (crowded_unwind, [dict(ratio=r, oi_drop=d, hold=h) for r in (2.0, 2.5) for d in (0.02, 0.04) for h in (12, 24, 48)]),
    "taker_exhaustion": (taker_exhaustion, [dict(q=q, hold=h) for q in (0.9, 0.95) for h in (6, 12, 24)]),
}
