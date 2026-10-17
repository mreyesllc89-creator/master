# FlashGold Direction Filter: off vs on

`fgf_ab.py` runs FlashGold v5 (BTCUSD FGF build, input defaults) on one
TradingView chart export three ways and writes a report:

1. **Filter off.**
2. **Filter on** (60m, band 0.25 ATR, against on: the defaults).
3. **20 random filters** that block the same share of signals as the real one
   (the placebo). Any filter that trades less pays less in costs, so the
   real filter has to beat these, not just "filter off".

Each run is scored as `docs/rules/validation.md` asks: TradingView-style fills
and worst-case fills, each without and with costs (0.02% per side + 5 ticks),
on the whole period and on each half. The verdict is **PASS** only if, with
worst-case fills and costs, the real filter beats at least 90% of the random
filters on the whole period and in each half.

## 1. Export the data from TradingView

1. Open the chart you trade, e.g. BTCUSD on **5m** (1m to 1H work; lower
   timeframes give the 60m filter more candles).
2. Scroll left until enough history is loaded (aim for 2+ months).
3. Chart menu (top right, or the arrow next to the layout name) ->
   **Export chart data...** -> time format **UNIX timestamp** -> Export.
   (Needs a paid TradingView plan.)

## 2. Run it

```
pip install numpy pandas
python -I tools/fgf_ab/fgf_ab.py BITSTAMP_BTCUSD_5.csv --out fgf_ab_report.md
```

Options: `--qty`, `--comm-pct`, `--slip-ticks`, `--tick` (use 0.01 for
XAUUSD / BTCUSD), `--filter-tf`, `--band-atr`, `--no-against`,
`--exit-mode Pips|ATR|Points`, `--warmup-days`, `--placebos`. The report is
written as Markdown plus a CSV of every run.

## What it is and is not

- The engine is `fg5.py`, the Python replay of the strategy and the FGF gate
  copied unchanged from `tools/vt_top10_stress/engines` (branch
  `claude/hopeful-meitner-4ky6wl`).
- It replays OHLC bars, not ticks: TradingView-style fills walk each bar open,
  nearer extreme, other extreme, close. Trade counts will differ a little
  from the Strategy Tester; compare the two before trusting either.
- One export is one market and one period. A PASS on one month is a reason to
  test another month, not a reason to go live.
