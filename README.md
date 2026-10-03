# pychart

TradingView-style charts from Python, without TradingView.

Load candles from a data source, compute indicators with pandas, and render an
interactive chart to a single HTML file that works offline: candlesticks, volume,
overlay indicators, oscillator panes, crosshair legend, pan and zoom, dark and
light themes.

The chart engine is TradingView's open-source
[Lightweight Charts](https://github.com/tradingview/lightweight-charts)
(Apache-2.0), vendored into the package so nothing is loaded from the network.

## Install

```bash
pip install -e ".[yahoo]"      # yfinance for free delayed data
pip install -e ".[dev]"        # pytest + playwright for development
```

## Use

```bash
pychart AAPL                                        # 1 year of daily bars, opens in your browser
pychart BTC-USD --tf 1h --period 30d -i ema:21 ema:55 rsi
pychart SPY --period 5y -i sma:50 sma:200 bb:20:2 macd volsma
pychart ES=F --csv data/es.csv -i vwap atr          # from a CSV you saved earlier
pychart AAPL --save data/aapl.csv --no-open         # download and keep the candles
pychart DEMO --source synthetic -i sma:20 rsi       # no network, random-walk demo data
pychart --list-indicators x
```

Output goes to `charts/<SYMBOL>_<tf>.html` unless `-o` says otherwise.

Indicator specs look like Pine Script inputs: `name:param1:param2`. Missing
parameters take the defaults listed by `--list-indicators`.

| spec | draws | defaults |
|------|-------|----------|
| `sma:N` | simple moving average | 20 |
| `ema:N` | exponential moving average (SMA-seeded, like Pine) | 20 |
| `bb:N:K` | Bollinger bands | 20, 2.0 |
| `vwap` | session VWAP (resets each UTC day) | |
| `rsi:N` | RSI, Wilder smoothing, 30/70 guides | 14 |
| `macd:F:S:SIG` | MACD line, signal, histogram | 12, 26, 9 |
| `atr:N` | average true range | 14 |
| `volsma:N` | moving average on the volume pane | 20 |

## Python API

```python
from pychart import load, Chart

df = load("AAPL", timeframe="1d", period="2y")          # pandas DataFrame: open high low close volume
chart = Chart(df, symbol="AAPL", timeframe="1d").add("ema:50").add("rsi:14")
chart.save("charts/aapl.html", open_browser=True)
```

Any DataFrame with a datetime index and open/high/low/close/volume columns works,
so you can plug in a broker API, a database, or your own files. See
`examples/api_demo.py` and `pychart/data.py` for the provider contract.

Adding an indicator is one function in `pychart/indicators.py` that takes the
DataFrame and returns `{name: Series}`, plus one line in the `INDICATORS` registry.

## Layout

```
pychart/
  data.py        providers (Yahoo, CSV, synthetic), normalization, resampling
  indicators.py  indicator functions + registry + spec parser
  chart.py       builds the chart model and writes the HTML
  cli.py         command line
  static/        template.html, vendored Lightweight Charts
tests/           pytest suite (python -m pytest)
```

## Roadmap

- Phase 1 (this): charts, volume, indicators, CLI, offline HTML. Done.
- Phase 2: more indicators (Stochastic, Supertrend, Ichimoku), multi-symbol
  compare, drawing tools, saved layouts.
- Phase 3: live updates over websocket from a broker feed, alerts.
- Pine Script is not planned. Port scripts to Python indicator functions instead.

## Notes

- Yahoo caps intraday history: 7 days for 1m, 60 days for other intraday bars.
  Use `--save` to build your own archive over time.
- Yahoo data is delayed and free-tier reliability varies. A broker API is the
  right source once you trade from this.
