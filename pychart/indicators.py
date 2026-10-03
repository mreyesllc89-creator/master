"""Technical indicators, implemented in plain pandas.

Each indicator is a function `df -> dict[name, Series]` registered in
`INDICATORS` together with its default parameters and where it draws
("overlay" on the price pane, or "pane" below it). Specs on the command line
look like Pine Script inputs: `sma:20`, `bb:20:2`, `macd:12:26:9`, `vwap`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

Series = pd.Series


# --- building blocks ---------------------------------------------------------

def sma(s: Series, length: int) -> Series:
    return s.rolling(length, min_periods=length).mean()


def ema(s: Series, length: int) -> Series:
    # TradingView seeds the EMA with the SMA of the first `length` bars.
    out = s.ewm(span=length, adjust=False, min_periods=length).mean()
    seed = s.iloc[:length].mean() if len(s) >= length else np.nan
    if len(s) >= length:
        alpha = 2.0 / (length + 1)
        vals = out.to_numpy(copy=True)
        vals[length - 1] = seed
        for i in range(length, len(vals)):
            vals[i] = alpha * s.iloc[i] + (1 - alpha) * vals[i - 1]
        out = pd.Series(vals, index=s.index)
    return out


def rma(s: Series, length: int) -> Series:
    """Wilder's smoothing (Pine `ta.rma`): alpha = 1/length, SMA-seeded."""
    valid = s.dropna()  # leading NaNs (e.g. the first diff) do not count toward the warm-up
    vals = valid.to_numpy(dtype="float64")
    out = np.full_like(vals, np.nan)
    if len(vals) >= length:
        out[length - 1] = vals[:length].mean()
        alpha = 1.0 / length
        for i in range(length, len(vals)):
            out[i] = alpha * vals[i] + (1 - alpha) * out[i - 1]
    return pd.Series(out, index=valid.index).reindex(s.index)


def true_range(df: pd.DataFrame) -> Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


# --- indicators --------------------------------------------------------------

def ind_sma(df: pd.DataFrame, length: int = 20) -> dict[str, Series]:
    return {f"SMA {length}": sma(df["close"], length)}


def ind_ema(df: pd.DataFrame, length: int = 20) -> dict[str, Series]:
    return {f"EMA {length}": ema(df["close"], length)}


def ind_bollinger(df: pd.DataFrame, length: int = 20, mult: float = 2.0) -> dict[str, Series]:
    basis = sma(df["close"], length)
    dev = mult * df["close"].rolling(length, min_periods=length).std(ddof=0)
    return {
        f"BB basis {length}": basis,
        f"BB upper {length}": basis + dev,
        f"BB lower {length}": basis - dev,
    }


def ind_vwap(df: pd.DataFrame) -> dict[str, Series]:
    """Session VWAP, anchored at each UTC calendar day (the TradingView default)."""
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    day = df.index.normalize()
    cum_pv = pv.groupby(day).cumsum()
    cum_v = df["volume"].groupby(day).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)
    return {"VWAP": vwap}


def ind_rsi(df: pd.DataFrame, length: int = 14) -> dict[str, Series]:
    delta = df["close"].diff()
    up = rma(delta.clip(lower=0), length)
    down = rma((-delta).clip(lower=0), length)
    rs = up / down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(down != 0, 100.0)
    rsi[delta.isna()] = np.nan
    return {f"RSI {length}": rsi}


def ind_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Series]:
    macd_line = ema(df["close"], fast) - ema(df["close"], slow)
    signal_line = ema(macd_line.dropna(), signal).reindex(df.index)
    hist = macd_line - signal_line
    return {"MACD": macd_line, "Signal": signal_line, "Histogram": hist}


def ind_atr(df: pd.DataFrame, length: int = 14) -> dict[str, Series]:
    return {f"ATR {length}": rma(true_range(df), length)}


def ind_volume_sma(df: pd.DataFrame, length: int = 20) -> dict[str, Series]:
    return {f"Vol SMA {length}": sma(df["volume"], length)}


# --- registry ----------------------------------------------------------------

@dataclass(frozen=True)
class IndicatorDef:
    key: str
    title: str
    kind: str                      # "overlay" | "pane" | "volume"
    fn: Callable[..., dict[str, Series]]
    params: tuple[tuple[str, type, float], ...] = ()   # (name, type, default)
    styles: dict[str, str] = field(default_factory=dict)  # output name -> "line"|"histogram"|"dashed"
    levels: tuple[float, ...] = ()  # horizontal guide lines for pane indicators

    def describe(self) -> str:
        ps = ":".join(f"{n}={d}" for n, _, d in self.params)
        return f"{self.key}{(':' + ps) if ps else ''}  {self.title}"


INDICATORS: dict[str, IndicatorDef] = {
    d.key: d
    for d in [
        IndicatorDef("sma", "Simple Moving Average", "overlay", ind_sma, (("length", int, 20),)),
        IndicatorDef("ema", "Exponential Moving Average", "overlay", ind_ema, (("length", int, 20),)),
        IndicatorDef(
            "bb", "Bollinger Bands", "overlay", ind_bollinger,
            (("length", int, 20), ("mult", float, 2.0)),
            styles={"BB basis": "dashed"},
        ),
        IndicatorDef("vwap", "VWAP (session)", "overlay", ind_vwap),
        IndicatorDef("rsi", "Relative Strength Index", "pane", ind_rsi, (("length", int, 14),), levels=(30, 70)),
        IndicatorDef(
            "macd", "MACD", "pane", ind_macd,
            (("fast", int, 12), ("slow", int, 26), ("signal", int, 9)),
            styles={"Histogram": "histogram"}, levels=(0,),
        ),
        IndicatorDef("atr", "Average True Range", "pane", ind_atr, (("length", int, 14),)),
        IndicatorDef("volsma", "Volume SMA", "volume", ind_volume_sma, (("length", int, 20),)),
    ]
}


@dataclass(frozen=True)
class IndicatorSpec:
    definition: IndicatorDef
    args: tuple

    @property
    def label(self) -> str:
        return ":".join([self.definition.key, *(_fmt_arg(a) for a in self.args)])


def _fmt_arg(a) -> str:
    if isinstance(a, float) and a.is_integer():
        return str(int(a))
    return str(a)


def parse_spec(spec: str) -> IndicatorSpec:
    """'ema:50' -> IndicatorSpec(ema, (50,)). Missing params take defaults."""
    parts = [p for p in spec.strip().split(":") if p != ""]
    if not parts:
        raise ValueError("empty indicator spec")
    key, raw_args = parts[0].lower(), parts[1:]
    try:
        d = INDICATORS[key]
    except KeyError:
        raise ValueError(f"unknown indicator {key!r}; available: {', '.join(INDICATORS)}") from None
    if len(raw_args) > len(d.params):
        raise ValueError(f"{key} takes at most {len(d.params)} parameter(s)")
    args = []
    for (name, typ, default), raw in zip(d.params, raw_args + [None] * (len(d.params) - len(raw_args))):
        if raw is None:
            args.append(default)
            continue
        try:
            args.append(typ(raw))
        except ValueError:
            raise ValueError(f"{key}: parameter {name!r} must be {typ.__name__}, got {raw!r}") from None
    return IndicatorSpec(d, tuple(args))


def compute(df: pd.DataFrame, spec: IndicatorSpec | str) -> dict[str, Series]:
    if isinstance(spec, str):
        spec = parse_spec(spec)
    return spec.definition.fn(df, *spec.args)
