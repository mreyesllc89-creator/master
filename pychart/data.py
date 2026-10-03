"""Data providers.

Every provider returns the same shape, so indicators and the chart never
care where candles came from:

    DatetimeIndex (tz-aware UTC, ascending, unique)
    columns: open, high, low, close, volume  (float64)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

# Timeframe label -> seconds. Used for synthetic data and axis formatting.
TIMEFRAME_SECONDS = {
    "1m": 60,
    "2m": 120,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
}


def timeframe_seconds(timeframe: str) -> int:
    try:
        return TIMEFRAME_SECONDS[timeframe]
    except KeyError:
        raise ValueError(
            f"unknown timeframe {timeframe!r}; choose one of {', '.join(TIMEFRAME_SECONDS)}"
        ) from None


def is_intraday(timeframe: str) -> bool:
    return timeframe_seconds(timeframe) < 86400


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce any OHLCV-ish frame into the pychart contract."""
    if df is None or len(df) == 0:
        raise ValueError("no candles returned")

    out = df.copy()

    # yfinance returns a (field, ticker) MultiIndex for a single ticker too.
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [str(c[0]) for c in out.columns]

    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]

    # Promote a time column to the index if the index is not datetime.
    if not isinstance(out.index, pd.DatetimeIndex):
        for cand in ("time", "timestamp", "date", "datetime"):
            if cand in out.columns:
                out = out.set_index(cand)
                break
        else:
            raise ValueError("no datetime index or time/date column found")

    idx = out.index
    if not isinstance(idx, pd.DatetimeIndex):
        # Unix seconds or milliseconds?
        numeric = pd.to_numeric(idx, errors="coerce")
        if numeric.notna().all():
            unit = "ms" if numeric.max() > 1e11 else "s"
            idx = pd.to_datetime(numeric, unit=unit, utc=True)
        else:
            idx = pd.to_datetime(idx, utc=True)
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out.index = idx
    out.index.name = "time"

    aliases = {"adj_close": None, "vol": "volume", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    for src, dst in aliases.items():
        if src in out.columns and dst and dst not in out.columns:
            out = out.rename(columns={src: dst})

    missing = [c for c in OHLCV_COLUMNS if c not in out.columns and c != "volume"]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if "volume" not in out.columns:
        out["volume"] = 0.0

    out = out[OHLCV_COLUMNS].astype("float64")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out["volume"] = out["volume"].fillna(0.0)
    return out


class Provider(Protocol):
    def fetch(self, symbol: str, timeframe: str, period: str) -> pd.DataFrame: ...


@dataclass
class YahooProvider:
    """Free, delayed data via the yfinance package. Fine for daily bars and
    recent intraday history (Yahoo caps 1m at 7 days, other intraday at 60)."""

    def fetch(self, symbol: str, timeframe: str = "1d", period: str = "1y") -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:  # pragma: no cover
            raise ImportError("pip install yfinance") from None

        interval = {"1M": "1mo", "1w": "1wk", "4h": "1h"}.get(timeframe, timeframe)
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df is None or df.empty:
            raise ValueError(f"Yahoo returned no data for {symbol} ({timeframe}, {period})")
        df = normalize(df)
        if timeframe == "4h":
            df = resample(df, "4h")
        return df


@dataclass
class CSVProvider:
    """Load candles from a CSV you exported or saved earlier (see `save_csv`)."""

    path: str | Path

    def fetch(self, symbol: str = "", timeframe: str = "1d", period: str = "") -> pd.DataFrame:
        df = pd.read_csv(self.path)
        return normalize(df)


@dataclass
class SyntheticProvider:
    """Deterministic random-walk candles for demos and tests. No network."""

    seed: int = 7
    start_price: float = 100.0

    def fetch(self, symbol: str = "DEMO", timeframe: str = "1d", period: str = "1y") -> pd.DataFrame:
        step = timeframe_seconds(timeframe)
        n = _period_to_bars(period, step)
        rng = np.random.default_rng(self.seed + sum(map(ord, symbol)))

        rets = rng.normal(loc=0.0003, scale=0.012, size=n)
        close = self.start_price * np.exp(np.cumsum(rets))
        open_ = np.concatenate([[self.start_price], close[:-1]]) * (1 + rng.normal(0, 0.002, n))
        wick = np.abs(rng.normal(0, 0.006, n)) * close
        high = np.maximum(open_, close) + wick
        low = np.minimum(open_, close) - wick
        volume = rng.lognormal(mean=13, sigma=0.4, size=n).round()

        end = pd.Timestamp.now(tz="UTC").floor("D")
        if is_intraday(timeframe):
            # Place intraday bars inside US regular hours, weekdays only.
            idx = _intraday_index(end, n, step)
        else:
            idx = pd.bdate_range(end=end, periods=n, tz="UTC") if timeframe == "1d" else pd.date_range(
                end=end, periods=n, freq=pd.Timedelta(seconds=step), tz="UTC"
            )

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx
        )
        return normalize(df)


def _intraday_index(end: pd.Timestamp, n: int, step: int) -> pd.DatetimeIndex:
    per_day = int(6.5 * 3600 // step) or 1
    days = math.ceil(n / per_day)
    sessions = pd.bdate_range(end=end, periods=days, tz="UTC")
    stamps = []
    for day in sessions:
        session_open = day + pd.Timedelta(hours=14, minutes=30)  # 09:30 New York in UTC (approx.)
        stamps.extend(session_open + pd.Timedelta(seconds=step * i) for i in range(per_day))
    return pd.DatetimeIndex(stamps[-n:])


def _period_to_bars(period: str, step: int) -> int:
    units = {"d": 86400, "w": 604800, "mo": 2592000, "y": 31536000}
    p = period.strip().lower()
    for suffix in sorted(units, key=len, reverse=True):
        if p.endswith(suffix):
            qty = float(p[: -len(suffix)])
            span = qty * units[suffix]
            break
    else:
        raise ValueError(f"bad period {period!r}; use e.g. 5d, 3mo, 1y")
    if step >= 86400:
        # Trading days, not calendar days.
        return max(2, int(span / step * (252 / 365)))
    return max(2, int(span / 86400 * (252 / 365) * (6.5 * 3600 / step)))


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Aggregate candles to a coarser timeframe (e.g. '4h', '1W')."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = df.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return out


def save_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="time")
    return path


PROVIDERS = {"yahoo": YahooProvider, "synthetic": SyntheticProvider}


def load(
    symbol: str,
    timeframe: str = "1d",
    period: str = "1y",
    source: str = "yahoo",
    csv: str | Path | None = None,
) -> pd.DataFrame:
    """One-call loader used by the CLI: pick a provider and fetch."""
    timeframe_seconds(timeframe)  # validate early
    if csv is not None:
        return CSVProvider(csv).fetch(symbol, timeframe, period)
    try:
        provider = PROVIDERS[source]()
    except KeyError:
        raise ValueError(f"unknown source {source!r}; choose one of {', '.join(PROVIDERS)} or pass csv=") from None
    return provider.fetch(symbol, timeframe, period)
