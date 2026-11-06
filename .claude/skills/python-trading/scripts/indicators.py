"""Indicators with explicit smoothing semantics for parity with TradingView Pine and MetaTrader 5.

Usage as a library::

    from indicators import rsi_wilder, sma, ema, atr_wilder, atr_sma, tdi

Run ``python indicators.py --selftest`` to verify the implementations against the
closed-form definitions on random data.

All functions take and return pandas Series aligned to the input index. Warm-up bars are NaN.
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd


def sma(x: pd.Series, n: int) -> pd.Series:
    """Simple moving average. Pine ta.sma, MT5 MODE_SMA."""
    return x.rolling(n, min_periods=n).mean()


def rma(x: pd.Series, n: int) -> pd.Series:
    """Wilder's smoothing (Pine ta.rma). Seeded with the SMA of the first n values, like Pine."""
    vals = x.to_numpy(dtype=float)
    out = np.full_like(vals, np.nan)
    valid = ~np.isnan(vals)
    if valid.sum() < n:
        return pd.Series(out, index=x.index)
    first = int(np.argmax(valid))  # first non-NaN
    start = first + n - 1
    out[start] = vals[first : start + 1].mean()
    alpha = 1.0 / n
    for i in range(start + 1, len(vals)):
        out[i] = alpha * vals[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=x.index)


def ema(x: pd.Series, n: int) -> pd.Series:
    """Exponential moving average seeded with the SMA of the first n values (Pine ta.ema)."""
    vals = x.to_numpy(dtype=float)
    out = np.full_like(vals, np.nan)
    valid = ~np.isnan(vals)
    if valid.sum() < n:
        return pd.Series(out, index=x.index)
    first = int(np.argmax(valid))
    start = first + n - 1
    out[start] = vals[first : start + 1].mean()
    alpha = 2.0 / (n + 1)
    for i in range(start + 1, len(vals)):
        out[i] = alpha * vals[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=x.index)


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI with Wilder smoothing. Matches Pine ta.rsi and MT5 iRSI."""
    diff = close.diff()
    gain = diff.clip(lower=0.0)
    loss = (-diff).clip(lower=0.0)
    avg_gain = rma(gain.iloc[1:], n).reindex(close.index)
    avg_loss = rma(loss.iloc[1:], n).reindex(close.index)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0.0, 100.0)
    out[avg_gain.isna()] = np.nan
    return out


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    return tr


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """ATR as Pine ta.atr: RMA of true range."""
    return rma(true_range(high, low, close), n)


def atr_sma(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """ATR as MetaTrader 5 iATR: simple moving average of true range."""
    return sma(true_range(high, low, close), n)


def tdi(close: pd.Series, rsi_len: int = 14, fast_len: int = 2, slow_len: int = 7) -> pd.DataFrame:
    """Traders Dynamic Index lines used by the FlashGold / XPW strategies.

    Returns columns rsi, fast, slow, direction (+1 fast rising, -1 falling, 0 flat/NaN).
    """
    r = rsi_wilder(close, rsi_len)
    fast = sma(r, fast_len)
    slow = sma(r, slow_len)
    d = np.sign(fast.diff()).fillna(0.0).astype(int)
    return pd.DataFrame({"rsi": r, "fast": fast, "slow": slow, "direction": d})


def htf_no_lookahead(htf: pd.Series, target_index: pd.DatetimeIndex) -> pd.Series:
    """Align a higher-timeframe series to a lower-timeframe index using the last CLOSED HTF bar.

    Equivalent to Pine ``request.security(sym, tf, expr[1], lookahead=barmerge.lookahead_on)``.
    ``htf`` must be indexed by the HTF bar OPEN time.
    """
    closed = htf.shift(1)
    return closed.reindex(closed.index.union(target_index)).ffill().reindex(target_index)


# ----------------------------------------------------------------------------- self test
def _selftest() -> int:
    rng = np.random.default_rng(1)
    n = 600
    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC")
    close = pd.Series(100 + rng.standard_normal(n).cumsum(), index=idx)
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)

    # SMA of a constant is the constant
    const = pd.Series(5.0, index=idx)
    assert np.allclose(sma(const, 10).dropna(), 5.0)
    assert np.allclose(rma(const, 10).dropna(), 5.0)
    assert np.allclose(ema(const, 10).dropna(), 5.0)

    # RMA equals pandas ewm(alpha=1/n) after the seed difference fades
    ref = close.ewm(alpha=1 / 14, adjust=False).mean()
    assert np.allclose(rma(close, 14).iloc[300:], ref.iloc[300:], atol=1e-6)

    # EMA converges to pandas ewm(span)
    ref_e = close.ewm(span=20, adjust=False).mean()
    assert np.allclose(ema(close, 20).iloc[300:], ref_e.iloc[300:], atol=1e-6)

    # RSI in range, monotonic series gives 100 / 0
    r = rsi_wilder(close, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    up = pd.Series(np.arange(100, dtype=float), index=idx[:100])
    assert np.allclose(rsi_wilder(up, 14).dropna(), 100.0)
    down = pd.Series(np.arange(100, 0, -1, dtype=float), index=idx[:100])
    assert np.allclose(rsi_wilder(down, 14).dropna(), 0.0)

    # ATR non-negative, SMA variant is the rolling mean of TR
    tr = true_range(high, low, close)
    assert (atr_wilder(high, low, close, 14).dropna() >= 0).all()
    assert np.allclose(atr_sma(high, low, close, 14).dropna(), tr.rolling(14).mean().dropna())

    # TDI shape and direction values
    t = tdi(close)
    assert list(t.columns) == ["rsi", "fast", "slow", "direction"]
    assert set(t["direction"].unique()) <= {-1, 0, 1}

    # HTF alignment never sees the future
    htf = close.resample("1h").last()
    aligned = htf_no_lookahead(htf, idx)
    # at 01:00 the aligned value must be the 00:00 bar's value (last closed), not 01:00's
    assert aligned.loc["2024-01-01 01:00:00+00:00"] == htf.loc["2024-01-01 00:00:00+00:00"]
    assert aligned.loc["2024-01-01 01:55:00+00:00"] == htf.loc["2024-01-01 00:00:00+00:00"]

    print("indicators selftest: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)
    if a.selftest:
        return _selftest()
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
