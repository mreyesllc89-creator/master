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

## Same-candle entry: stop order at the EMA cross price (v2.3)

Requested next: enter inside the signal candle rather than at its close. A close-of-bar
trigger cannot do that, and `calc_on_every_tick` only works live. What can is a resting stop
order at the price where the cross will happen. At the close of bar t-1 both EMAs are known,
and each updates on bar t as `a * close + (1 - a) * prev`, so the close that makes them equal
is

```
cross = ((1 - a_slow) * slow - (1 - a_fast) * fast) / (a_fast - a_slow)
```

The stop sits at that price plus a buffer and fills the moment bar t trades through it. That
is the same candle in which the close-based cross is confirmed, but at the cross price rather
than the close, and typically earlier in the bar. The trade-off is fills on bars that touch
the level and then close back on the wrong side (unconfirmed crosses).

`analysis/simulate_intrabar.py` compares it with the close entry, no session filter, same
exits and costs. Buffer 0 and arming distance 1 ATR:

| TF | Close of signal bar (net / PF) | Stop at cross price (net / PF) | Confirmed at close | Fill better than close, in ATR |
|---|---|---|---|---|
| 5m | -94 / 0.68 | -56 / 0.72 | 52 % | 0.04 |
| 15m | -47 / 0.90 | -31 / 0.92 | 60 % | 0.15 |
| 30m | -212 / 0.70 | -291 / 0.49 | 41 % | -0.11 |
| 60m | -280 / 0.72 | -443 / 0.47 | 58 % | 0.14 |
| 240m | -413 / 0.81 | +574 / 1.50 | 66 % | 0.11 |
| 1D | +631 / 1.44 | +883 / 1.90 | 66 % | 0.14 |

Unconfirmed fills are the losers everywhere (PF 0.24 to 0.68 outside 240m); confirmed ones
are profitable on 5m, 15m, 240m and daily. A buffer beyond the cross price trades some fills
for a higher confirmation rate. Sweep in `simulate_intrabar_sweep.out.txt`, pooled over the
six timeframes:

| Buffer (x ATR) | Arm within (x ATR) | Net $ sum | Avg PF | Win % | Confirmed |
|---|---|---|---|---|---|
| 0.0 | 1.0 | 636 | 1.00 | 53.7 | 57 % |
| 0.1 | 2.0 | 1007 | 1.06 | 56.1 | 64 % |
| 0.2 | 2.0 | 1184 | 1.18 | 58.2 | 73 % |
| 0.3 | 2.0 | -10 | 0.97 | 56.8 | 83 % |
| 0.5 | 2.0 | -346 | 0.85 | 55.5 | 88 % |

Buffer 0.2 ATR with arming within 2 ATR is the best cell and is positive or near zero on
every timeframe except 30m and 60m (15m: +70, PF 1.2). Beyond 0.3 ATR the buffer eats the
price advantage that motivated the entry.

Combining it with the profit-aware time exit did not help here: with the stop entry the
exits are best left to the ATR stop, target and trail (`off` column of the second table in
`simulate_intrabar.out.txt`), except on 15m where profit-exit N = 6 is marginally better.
v2.3 therefore keeps the time exit input but the two settings should be re-tested together
on full history.

### What v2.3 changes

- `Entry Trigger` gains `Stop at cross price (same candle)` and it is the default.
- `Cross Stop Buffer (x ATR)` default 0.2 and `Max Distance To Arm (x ATR)` default 2.0.
- Each bar close, when flat, filters pass and the fast EMA is still on the wrong side, the
  script parks a stop entry at the cross price plus buffer with the ATR exit bracket attached;
  when conditions lapse it cancels the order. Armed levels are plotted as circles.
- Alerts carry `"reason":"stop_at_cross"` on the entry fill.

Live note for the bridge: a stop entry is a resting order, so the broker side must support
placing and cancelling it each bar, or the bridge must emulate it from the alert's `stop`
price.

## Distance units (v2.4)

`Distance Unit` in the Execution And Sizing group switches how the Stop Loss Distance, Take
Profit Distance, Cross Stop Buffer and Max Distance To Arm values are read:

| Unit | Meaning of a value of 2.0 |
|---|---|
| ATR multiple (default) | 2 x ATR(14), the behaviour of every earlier version |
| Gold points | $2.00 per oz of price movement |
| % of price | 2 % of the current close, about $86 at $4300 gold |

The trailing stop has its own `Trailing Unit` switch: `Fraction of TP / SL` keeps the earlier
relative definition (activation 0.9 x target distance, offset 0.3 x stop distance) and follows
whichever Distance Unit is chosen; `Distance Unit` reads Trail Activation and Trail Offset
directly in ATR multiples, gold points or % of price. The defaults are sized for ATR
multiples; when switching to points or percent, set the values again.

`Trade Direction` (Both, Buy only, Sell only) limits which side is taken; it applies to every
entry trigger including the stop-at-cross order. The calibration above was done in ATR units only; a points or percent
configuration has not been tested here.
