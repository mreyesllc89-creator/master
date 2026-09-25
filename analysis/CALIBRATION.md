# Calibration: earlier entry and profit-aware time exit

Requested on 2026-09-25: an earlier entry trigger and a better calibration of the max-bars
exit, closing when the trade is in profit. Implemented in `strategies/gold_vovix_devma_v2_2.pine`.

## Data and method

The TradingView trade lists cannot be used for calibration (their fills are artifacts, see
`REPORT.md`). Instead `analysis/simulate.py` re-runs the strategy bar by bar on the chart
exports in `data/bars/` with:

- the same indicators (fast EMA reproduced to 0.0000, trend EMA to within 0.03),
- tick-correct trailing stop (activation 0.9 x target distance, offset 0.3 x stop distance),
- pessimistic fills: stop checked before target when both are touched in one bar, trail
  breaches after a ratchet fill at the close, gaps fill at the open,
- a cost of 0.25 gold points spread plus 1.24 commission per round trip (1 oz),
- the session actually used in the exports (entries 04:00 to 22:30 chart time, flat by 23:30)
  for 5m to 60m, and no session filter for 240m and daily.

The VoVix/DEVMA regime filter is treated as pass-through. The local reproduction of it blocks
about a third of the signals TradingView plotted, while "always on" matches 255 of the 258
plotted signals across the six exports. Either the chart's regime rarely blocks anything, or
the exports were made with it effectively off. `simulate_strict_regime.out.txt` holds the
strict version; the conclusions below do not change.

Sample sizes are small. Each export is 2018 bars, which is 10 days of 5m, one month of 15m,
two months of 30m, four months of 60m, 16 months of 240m and eight years of daily. Per
timeframe that is 30 to 50 trades. Treat every number below as directional.

## Earlier entry

Four candidates were compared with the base fast/slow EMA cross, measuring how many bars
before the base cross each one fires in the same direction (within six bars) and how often
no cross follows at all.

| Variant | Lead (bars, avg over TFs) | Fires with no cross following | Notes |
|---|---|---|---|
| Projected cross: fast EMA still on the wrong side, but one bar of slope extrapolation puts it across | 1.2 to 1.7 | 25 to 30 % | Fewest false starts, best on 15m and 30m |
| Fast EMA turn: gap to slow EMA narrowing for two bars, price already across slow EMA | 1.4 to 1.9 | 30 to 45 % | Best on 240m, worst on daily |
| Close crosses slow EMA before the fast EMA does | 1.7 to 2.1 | 25 to 45 % | Earliest but noisiest |
| EMA 3/8 cross | 0.8 to 1.1 | 40 to 55 % | Not meaningfully earlier, many extra trades |

Net result with the corrected exit stack and no time exit (net $ per 1 oz, profit factor):

| TF | EMA cross (v2) | Projected cross | Fast EMA turn |
|---|---|---|---|
| 5m | -114 / 0.54 | -96 / 0.50 | -103 / 0.48 |
| 15m | -100 / 0.77 | +22 / 1.08 | -48 / 0.82 |
| 30m | -254 / 0.55 | -136 / 0.68 | -104 / 0.76 |
| 60m | -94 / 0.86 | -265 / 0.60 | -239 / 0.60 |
| 240m | -413 / 0.81 | -3 / 1.00 | +240 / 1.20 |
| 1D | +631 / 1.44 | -342 / 0.73 | -343 / 0.71 |

The projected cross is the earlier entry that costs the least in false starts and is the
best trigger on the 15m chart the strategy is built for, so it is the v2.2 default. It is not
a universal improvement: on 60m and daily the plain cross does better.

## Time exit, calibrated to close when in profit

Two exit styles were swept for N = 1 to 8 bars (full grid in `simulate.out.txt`):

- hard: close after N bars regardless (the v2 behaviour),
- profit: once N bars have passed, close at the first bar that closes in profit; stop,
  target and trail stay active meanwhile.

Averaged over the six timeframes with the base entry:

| Setting | Win % | Avg PF | Net $ summed over TFs |
|---|---|---|---|
| No time exit | 50 | 0.83 | -344 |
| Hard, N = 1 (v2 default) | 40 | 0.61 | -1086 |
| Hard, N = 4 | 44 | 0.76 | -949 |
| Profit, N = 1 | 62 | 0.68 | -1098 |
| Profit, N = 4 | 58 | 0.80 | -664 |
| Profit, N = 6 | 58 | 0.76 | -1107 |

The profit-aware exit raises the win rate by about ten points at every N, and N = 4 is the
most consistent value across timeframes for both the base and the projected-cross entry
(avg PF 0.80 and 0.81, the best of any time-exit setting). The hard exit at N = 1 that v2
shipped with is the worst setting in the grid; it only looked good on phantom fills.

On the 15m chart specifically, projected cross plus profit exit at N = 6 is the best cell
(+40, PF 1.2) and N = 4 is -10; with one month of data that difference is noise, so the
default is the cross-timeframe value N = 4.

## What v2.2 changes

- `Entry Trigger` input: EMA cross, Projected cross (early, default), Fast EMA turn (early).
- `Time Exit` input: Off, Close after N bars, Close when in profit after N bars (default).
- `N Bars For Time Exit` default 4 (was 1). Optional `Hard Cap Bars`, off by default.
- Alerts and comments distinguish `profit_time_exit`, `max_bars_exit` and `hard_cap_exit`.
- Everything from v2.1 (tick-correct trailing stop) is kept.

## The uncomfortable part

With realistic fills and costs, no combination in this grid is robustly profitable across
timeframes. The daily chart is the only one with a positive expectancy under the base
entry, and it has 49 trades in eight years. Before spending more time on entry and exit
timing, re-run v2.2 on the full 15m history in TradingView with commission on and read the
result as the first honest backtest of this idea. If it is still negative, the edge is in
the filters (session, trend, regime) or it is not there, and no exit calibration will fix
that.

## Reproducing

```
python3 analysis/simulate.py 0.25 1.24            # default: regime pass-through
python3 analysis/simulate.py 0.25 1.24 strict     # local regime reproduction
python3 analysis/simulate.py 0.0 0.0              # zero-cost sensitivity
```
