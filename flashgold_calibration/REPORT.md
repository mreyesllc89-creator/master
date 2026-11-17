# FlashGold v5 Strategy (BTCUSD) EA: calibration

Date: 2026-11-17. Subject: `FlashGold_v5_Strategy_BTCUSD.mq5` (the MQL5 conversion of the TradingView strategy).

## Short version

1. **No setting was found that makes money at a normal broker spread.** With a $15 BTCUSD spread, 96,000
   random input combinations were tested on H4, H2, H1 and M30. Of the 1,402 that looked good on the first two
   years, 44% made money on the held-out third year, with a median profit factor of 0.97. That is what chance
   looks like. The best 30 in-sample lost 7% on average on the held-out year.
2. **The EA's default exits (30-pip stop) only work if the spread is about $2 or less.** On 1-second data for
   the last 12 months: profit factor 1.17 at a $2 spread, break-even around $3 to $5, a loss from $5 up, and
   every trade stopped out at $30.
3. **A slightly wider stop is better in the same low-spread niche.** Stop 50 pips, 30% closed at 3R, runner
   trailed 600 pips with breakeven: profit factor 1.29 at a $2 spread, still positive at $8, break-even at $10,
   losing at $15. Positive in 3 of 4 quarters. The evidence is weak (t = 1.7, one year, picked from 84 variants).
   Preset: `presets/FlashGold_BTCUSD_H1_lowspread.set`.
4. **A commission of 0.02% per side kills it even at a $2 spread** (profit factor 0.68). That is roughly $36
   per BTC round trip against a $50 stop.
5. **The TradingView calibration in the Pine header does not hold up.** It was done on hourly bars for one
   month. A 30-pip stop is far smaller than a single minute's range (median $40), so an hourly backtest cannot
   tell whether the stop or the target was hit first. On 1-minute data the same settings range from -120% to
   +75% over three years depending only on that assumption.

Recommendation: do not trade this EA on a broker whose BTCUSD spread plus commission exceeds about $5 per BTC
round trip. If yours is below that, test the low-spread preset in the MetaTrader Strategy Tester on real ticks
from your own broker before using it.

## What was tested, and how

MetaTrader's Strategy Tester could not be used: it refuses to start without a broker account, and the terminal
cannot log in from this environment. The EA's rules were therefore ported to Python (`tools/engine.py`):

- Signals on chart bars built from the fine data: TDI parent and child zones (chart, 2x, 4x, read from the last
  closed higher-timeframe bar), burst gate, stop-order entry at ask + distance or bid - distance.
- Trades simulated bar by bar on the fine data, as the EA does on ticks: entry stops with expiry and
  one-cancels-other, reversal, broker stop loss, fixed take profit or partial + runner with breakeven and trail,
  time stop.
- Prices are bid; ask = bid + spread. Longs open at ask and close at bid, shorts the reverse.
- The stop is always checked before any favourable move. For the bar in which an entry fills, "worst" counts the
  trade as stopped if that bar's range reaches the stop, "best" only if the bar closes beyond it.
- Results are the sum of trade returns as a percentage of the position's notional value, for a constant
  quantity. Example: +17% over a year on 0.10 lot at a $90,000 price is about +$1,500.

The port has not been checked against MetaTrader or TradingView trade lists. Entry and exit rules were ported
from the EA source line by line, but a difference in detail is possible.

Data (Binance, public archive):

| Set | Instrument | Resolution | Period | Use |
|---|---|---|---|---|
| A | BTCUSDT perpetual | 1 minute | 2023-11-01 to 2026-11-11 | random search, wide stops |
| B | BTCUSDT spot | 1 second | 2025-11-01 to 2026-10-31 | tight stops |

Binance prices are not your broker's. Spreads widen in fast markets, which is exactly when this strategy
enters, so a fixed spread is optimistic.

## 1. Why 1-minute data cannot judge the default stop

Default settings on H1, three years of 1-minute data:

| Spread | Worst case | Best case |
|---|---|---|
| $0 | -121%, PF 0.24 | +75%, PF 1.61 |
| $5 | -130%, PF 0.20 | +56%, PF 1.44 |
| $15 | -155%, PF 0.09 | +18%, PF 1.13 |
| $30 | -178%, PF 0.00 | -36%, PF 0.76 |

The median 1-minute range is $40 and the stop is $30, so for most trades the entry and the stop fall inside
the same minute. With ATR stops the two cases only agree from about 1 x ATR (about $480 on H1) upwards.

## 2. Random search with wide stops (set A)

`tools/sweep.py`: 600 signal settings x 40 exit settings on each of M30, H1, H2, H4 = 96,000 backtests at a $15
spread, worst case. Sampled: RSI length, fast length, minimum aligned zones, zone filter on/off, burst threshold
0.2 to 2 ATR, entry distance 0 to 0.6 ATR, stop 0.3 to 4 ATR, target 1 to 8 R, fixed or partial + runner,
trailing stop, entry lifetime, reversal, exit on opposite, direction, time stop.

Settings were chosen on 2023-11 to 2025-10 only (at least 150 trades, both years positive with t > 1). The year
2025-11 to 2026-11 was held out.

| | Held-out year positive | Median held-out PF |
|---|---|---|
| All 96,000 runs | 34% | |
| 1,402 that passed in-sample | 44% | 0.97 |
| Best 300 at $2 spread | 54% | 1.02 |
| Best 300 at $15 spread | 48% | 0.99 |
| Best 300 at $30 spread | 37% | 0.95 |
| Best 30 at $15 spread | 40% | 0.97 |

The best in-sample t-statistic per half-year was about 2.5, which is expected by chance from 96,000 trials. There
is no wide-stop setting to recommend.

## 3. Tight stops on 1-second data (set B)

`tools/tight_1s.py` and `tools/candidate.py`, chart H1, default signal settings, 1,743 signals in 12 months.

EA defaults (stop 30 pips, 30% at 5R, runner 600 pips, breakeven):

| Spread | Worst case | Best case |
|---|---|---|
| $0 | +8.3%, PF 1.20 | +24.5%, PF 1.63 |
| $2 | +7.1%, PF 1.17 | +23.4%, PF 1.60 |
| $5 | -2.7%, PF 0.94 | +16.0%, PF 1.39 |
| $10 | -11.0%, PF 0.76 | +9.0%, PF 1.21 |
| $15 | -21.8%, PF 0.54 | +2.8%, PF 1.06 |
| $30 | -57.0%, PF 0.00 | -26.8%, PF 0.46 |

Grid of 84 tight exits (stop 20 to 250 pips, target 2 to 8 R, fixed / runner 600 / runner 1500), scored on the
first 8 months and the last 4 months separately:

- $2 spread: 34 of 84 positive in both periods. Stop 50 pips with the 600-pip runner is the most consistent
  (positive in both periods for every target tested). No stop of 150 pips or wider is positive in both.
- $15 spread: 0 of 84 positive in both periods.

Candidate (stop 50 pips, 30% at 3R, runner 600 pips, breakeven), 12 months, about 1,230 trades:

| Spread | Worst case | Best case |
|---|---|---|
| $0 | +19.4%, PF 1.33 | +27.9%, PF 1.49 |
| $2 | +17.2%, PF 1.29 | +25.8%, PF 1.44 |
| $5 | +10.8%, PF 1.17 | +19.5%, PF 1.33 |
| $8 | +5.0%, PF 1.08 | +17.2%, PF 1.28 |
| $10 | +2.2%, PF 1.03 | +14.2%, PF 1.23 |
| $15 | -7.8%, PF 0.89 | +4.7%, PF 1.07 |

By quarter at $2, worst case: +7.5% (PF 1.66), -3.5% (PF 0.80), +2.4% (PF 1.14), +10.9% (PF 1.76). Win rate 27%,
maximum drawdown 7.3% of notional. With a 0.02% per side commission added: -32%, PF 0.68.

## Reproduce

```
cd flashgold_calibration/tools
python fetch_1m.py ../data/BTCUSDT_1m.npz 2023-11 2026-11-11
python fetch_1s.py ../data/BTCUSDT_spot_1s.npz 2025-11 2026-10
python sweep.py 600 40 1        # writes ../results/sweep_seed1.csv (not committed, 96,000 rows)
python stress.py
python tight_1s.py
python candidate.py
```

Needs numpy, pandas, numba, requests.
