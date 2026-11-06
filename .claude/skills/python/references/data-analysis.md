# Data analysis with pandas and numpy

## Loading
```python
df = pd.read_csv(path, parse_dates=["time"], dtype={"volume": "int64"}, usecols=[...])
df = df.set_index("time").sort_index()
df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")
```
- Parquet (`pd.read_parquet`, needs `pyarrow`) for anything you reload often: 10x
  faster and keeps dtypes.
- TradingView exports: columns `time, open, high, low, close, Volume` plus one column per
  plot; `time` is Unix seconds (`pd.to_datetime(df["time"], unit="s", utc=True)`).
- MetaTrader exports (`History Center` / `Tools > History`): `<DATE> <TIME> <OPEN> ...`
  tab separated, server time (not UTC). Record the broker's UTC offset next to the data.

## OHLC conventions
- Index: tz-aware `DatetimeIndex`, unique, sorted. Assert it:
  `assert df.index.is_monotonic_increasing and df.index.is_unique`.
- Column names lowercase `open high low close volume`.
- Resample with the bar's *open* time as the label (pandas default for `resample("1h")` is
  left label/left closed, which matches TradingView and MT5):
  `df.resample("1h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()`.
- Higher-timeframe values aligned to lower bars without lookahead: compute on the HTF
  frame, `shift(1)` (the last *closed* HTF bar), then `reindex(lower.index, method="ffill")`.
  This is the pandas equivalent of Pine's `request.security(..., lookahead_on)` with `[1]`.

## Vectorise, then loop only where state is path-dependent
- Rolling: `s.rolling(n).mean()`, `.max()`, `.std(ddof=0)` (TradingView's `ta.stdev`
  uses population std, ddof=0).
- Wilder smoothing (Pine `ta.rma`, MT5 RSI): `s.ewm(alpha=1/n, adjust=False).mean()`.
  Seed differences vs the SMA-seeded version fade after ~5n bars; for exact parity with a
  platform seed with the SMA of the first n values (see `python-trading/scripts/indicators.py`).
- EMA: `s.ewm(span=n, adjust=False).mean()`.
- Crosses: `(a > b) & (a.shift(1) <= b.shift(1))`.
- Stateful logic (a stop order waiting to fill, a trailing stop, "one entry per bar") is a
  `for` loop over numpy arrays, or `numba.njit` when it is too slow. Do not fake it with
  `cumsum` tricks that are wrong on the edge cases.

## Copy-on-write and assignment
- pandas 2.x: enable `pd.options.mode.copy_on_write = True` to make the semantics simple.
- Assign new columns with `df = df.assign(rsi=rsi)` or `df.loc[:, "rsi"] = rsi`.
- Boolean masks: `df.loc[mask, "col"]`; never `df[mask]["col"] = x`.

## Memory and speed
- Downcast: `df["close"].astype("float32")` only for plotting; keep float64 for maths.
- `df.itertuples()` is 10x faster than `iterrows()`; a numpy loop is 10x faster again.
- Profile before optimising: `%timeit`, `python -X importtime`, `cProfile`.

## Plotting
- `matplotlib` for static figures; `mplfinance` for candles; `plotly` for interactive.
- Always label axes and units, and plot the trade markers on the same time axis as price.
- Save with `fig.savefig(path, dpi=150, bbox_inches="tight")`; do not call `plt.show()` in scripts.

## Sanity checks before trusting a result
- Count NaNs per column after indicator warm-up; drop or `bfill` only consciously.
- Check for gaps and duplicate timestamps (`df.index.to_series().diff().value_counts()`).
- Compare one bar's indicator value to the platform's own value on the chart.
