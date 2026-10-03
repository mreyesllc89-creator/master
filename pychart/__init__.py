"""pychart: a TradingView-style charting toolkit in Python.

Load OHLCV candles from a data source, compute indicators with pandas,
and render an interactive chart (TradingView's open-source Lightweight
Charts engine) as a self-contained HTML file.
"""

from .data import load, CSVProvider, SyntheticProvider, YahooProvider
from .indicators import INDICATORS, parse_spec, compute
from .chart import Chart

__version__ = "0.1.0"
__all__ = [
    "load",
    "CSVProvider",
    "SyntheticProvider",
    "YahooProvider",
    "INDICATORS",
    "parse_spec",
    "compute",
    "Chart",
]
