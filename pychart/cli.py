"""Command line: `pychart AAPL --tf 1d --period 1y -i sma:20 ema:50 rsi macd`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .chart import Chart
from .data import PROVIDERS, TIMEFRAME_SECONDS, load, save_csv
from .indicators import INDICATORS, parse_spec


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pychart",
        description="TradingView-style charts from Python. Loads candles, computes indicators, writes an interactive HTML chart.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="indicators:\n  " + "\n  ".join(d.describe() for d in INDICATORS.values())
        + "\n\nexamples:\n  pychart AAPL\n  pychart BTC-USD --tf 1h --period 30d -i ema:21 ema:55 rsi\n"
          "  pychart SPY --csv data/spy.csv -i bb:20:2 macd\n  pychart DEMO --source synthetic -i sma:50 vwap --no-open",
    )
    p.add_argument("symbol", help="ticker, e.g. AAPL, BTC-USD, EURUSD=X (Yahoo syntax)")
    p.add_argument("--tf", "--timeframe", dest="timeframe", default="1d", choices=list(TIMEFRAME_SECONDS), help="bar size (default 1d)")
    p.add_argument("--period", default="1y", help="how much history: 5d, 60d, 6mo, 1y, 5y, max (default 1y)")
    p.add_argument("--source", default="yahoo", choices=list(PROVIDERS), help="data provider (default yahoo)")
    p.add_argument("--csv", type=Path, help="load candles from this CSV instead of a provider")
    p.add_argument("-i", "--indicator", dest="indicators", nargs="*", action="extend", default=[], metavar="SPEC",
                   help="indicator specs like sma:20 ema:50 bb:20:2 rsi:14 macd vwap (repeatable)")
    p.add_argument("-o", "--out", type=Path, help="output HTML path (default charts/<SYMBOL>_<tf>.html)")
    p.add_argument("--save", type=Path, metavar="CSV", help="also save the downloaded candles to this CSV")
    p.add_argument("--theme", default="dark", choices=["dark", "light"])
    p.add_argument("--title", help="chart title override")
    p.add_argument("--no-open", action="store_true", help="do not open the chart in a browser")
    p.add_argument("--list-indicators", action="store_true", help="list available indicators and exit")
    p.add_argument("--version", action="version", version=f"pychart {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_indicators:
        for d in INDICATORS.values():
            print(d.describe())
        return 0

    try:
        specs = [parse_spec(s) for s in args.indicators]
        df = load(args.symbol, timeframe=args.timeframe, period=args.period, source=args.source, csv=args.csv)
    except Exception as exc:  # noqa: BLE001 - surface any provider/parse error cleanly
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.save:
        save_csv(df, args.save)
        print(f"saved {len(df)} candles to {args.save}")

    chart = Chart(df, symbol=args.symbol.upper(), timeframe=args.timeframe, indicators=specs, theme=args.theme, title=args.title)
    out = args.out or Path("charts") / f"{args.symbol.upper().replace('/', '-')}_{args.timeframe}.html"
    chart.save(out, open_browser=not args.no_open)
    print(f"chart: {out}  ({len(df)} bars, {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}, {len(specs)} indicator(s))")
    return 0
