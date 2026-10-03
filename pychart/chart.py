"""Render candles + indicators to a self-contained HTML chart.

The page embeds TradingView's open-source Lightweight Charts engine
(Apache-2.0, vendored in `pychart/static/`), so it works offline and looks
like the chart you are used to: candlesticks, volume, overlays, oscillator
panes, crosshair legend, pan and zoom.
"""

from __future__ import annotations

import json
import math
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .data import is_intraday
from .indicators import IndicatorSpec, compute, parse_spec

STATIC = Path(__file__).parent / "static"
LWC_JS = STATIC / "lightweight-charts.standalone.production.js"

# Indicator line colors, validated for the dark surface (adjacent-pair CVD
# and normal-vision separation both pass). Assigned in fixed order.
SERIES_COLORS = ["#3987e5", "#d95926", "#9085e9", "#c98500", "#d55181"]

THEMES = {
    "dark": {
        "bg": "#131722", "panel": "#1e222d", "text": "#d1d4dc", "muted": "#787b86",
        "grid": "#1f2430", "border": "#2a2e39", "up": "#26a69a", "down": "#ef5350",
        "crosshair": "#758696",
    },
    "light": {
        "bg": "#ffffff", "panel": "#f0f3fa", "text": "#131722", "muted": "#787b86",
        "grid": "#e6e9ef", "border": "#d1d4dc", "up": "#26a69a", "down": "#ef5350",
        "crosshair": "#9598a1",
    },
}


def _time_key(index: pd.DatetimeIndex, intraday: bool) -> list:
    if intraday:
        # Unit-independent (pandas 3 may store microseconds, not nanoseconds).
        epoch = pd.Timestamp(0, tz="UTC")
        return [int(v) for v in (index - epoch) // pd.Timedelta(seconds=1)]
    return index.strftime("%Y-%m-%d").tolist()


def _points(times: list, values: pd.Series) -> list[dict]:
    out = []
    for t, v in zip(times, values.to_numpy(dtype="float64")):
        if not math.isnan(v):
            out.append({"time": t, "value": round(float(v), 6)})
    return out


@dataclass
class Chart:
    df: pd.DataFrame
    symbol: str = "SYMBOL"
    timeframe: str = "1d"
    indicators: list[IndicatorSpec] = field(default_factory=list)
    theme: str = "dark"
    title: str | None = None

    def add(self, spec: str | IndicatorSpec) -> "Chart":
        self.indicators.append(parse_spec(spec) if isinstance(spec, str) else spec)
        return self

    # --- model -----------------------------------------------------------

    def model(self) -> dict:
        df = self.df
        intraday = is_intraday(self.timeframe)
        times = _time_key(df.index, intraday)

        candles = [
            {"time": t, "open": o, "high": h, "low": l, "close": c}
            for t, o, h, l, c in zip(times, df["open"].round(6), df["high"].round(6), df["low"].round(6), df["close"].round(6))
        ]
        volume = [
            {"time": t, "value": float(v), "up": bool(c >= o)}
            for t, v, o, c in zip(times, df["volume"], df["open"], df["close"])
        ]

        overlays, panes, volume_overlays = [], [], []
        color_i = 0
        for spec in self.indicators:
            d = spec.definition
            outputs = compute(df, spec)
            series = []
            if d.kind == "pane":
                # Each oscillator line gets its own hue; histograms are up/down colored.
                for name, s in outputs.items():
                    style = d.styles.get(name, "line")
                    color = None
                    if style != "histogram":
                        color = SERIES_COLORS[color_i % len(SERIES_COLORS)]
                        color_i += 1
                    series.append({"name": name, "style": style, "color": color, "data": _points(times, s)})
            else:
                # One hue per overlay indicator: Bollinger's three lines share a color.
                color = SERIES_COLORS[color_i % len(SERIES_COLORS)]
                color_i += 1
                for name, s in outputs.items():
                    style = next((v for k, v in d.styles.items() if name.startswith(k)), "line")
                    series.append({"name": name, "style": style, "color": color, "data": _points(times, s)})
            block = {"key": spec.label, "title": d.title, "series": series, "levels": list(d.levels)}
            {"overlay": overlays, "pane": panes, "volume": volume_overlays}[d.kind].append(block)

        last = df.iloc[-1]
        prev_close = df["close"].iloc[-2] if len(df) > 1 else last["open"]
        change = float(last["close"] - prev_close)
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "title": self.title or f"{self.symbol} · {self.timeframe}",
            "intraday": intraday,
            "theme": self.theme,
            "themes": THEMES,
            "candles": candles,
            "volume": volume,
            "overlays": overlays,
            "panes": panes,
            "volumeOverlays": volume_overlays,
            "last": {
                "close": float(last["close"]),
                "change": change,
                "changePct": (change / prev_close * 100.0) if prev_close else 0.0,
            },
            "bars": len(df),
            "precision": _precision(df["close"]),
        }

    # --- output ----------------------------------------------------------

    def to_html(self) -> str:
        if self.theme not in THEMES:
            raise ValueError(f"unknown theme {self.theme!r}; choose dark or light")
        js = LWC_JS.read_text(encoding="utf-8")
        model = json.dumps(self.model(), separators=(",", ":"))
        # Guard against a closing script tag inside the JSON payload.
        model = model.replace("</", "<\\/")
        return (
            _template().replace("/*__LWC__*/", js)
            .replace("/*__MODEL__*/", model)
            .replace("__TITLE__", _escape(self.model_title()))
        )

    def model_title(self) -> str:
        return self.title or f"{self.symbol} {self.timeframe}"

    def save(self, path: str | Path, open_browser: bool = False) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_html(), encoding="utf-8")
        if open_browser:
            webbrowser.open(path.resolve().as_uri())
        return path


def _precision(close: pd.Series) -> int:
    p = float(close.abs().median())
    if p >= 1000:
        return 1
    if p >= 10:
        return 2
    if p >= 1:
        return 3
    return 5


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _template() -> str:
    return (STATIC / "template.html").read_text(encoding="utf-8")
