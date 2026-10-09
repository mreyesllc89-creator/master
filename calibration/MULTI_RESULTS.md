# Multi-method calibration — VT Markets ticks (XAUUSD-ECNc, BTCUSD.c)

Script: `multi_calib.py` (engine: `ticks.engine2`). Per timeframe: 216 entry settings ranked
(worst of 4 ATR exit sets, min(train, test) R), then for the top 2 + the default entry:
7 distance units × 100 SL/trail settings, swing stop-loss (5 / 10 / 20 bars), 3 close-based
exit rules (TDI cross, EMA20 close, PSAR flip) and 3 time stops. Score = min(train, test) R,
averaged over neighbouring settings. Units are rescaled to the same median as ATR(14), so a
multiplier means "x typical ATR". PF and win rate are per trade in R. Return / DD use a
$10k account at 0.5% risk, lots rounded down.

## XAUUSD
| TF | Best method | Trades | Win | PF | PF train / test | Exp. | 0.5% return / DD | Neighbours + | Default PF |
|---|---|---|---|---|---|---|---|---|---|
| 1m | Percent | 605 | 35% | 0.91 | 0.92 / 0.89 | −0.018R | −4.9% / 5.9% | 0% | 0.78 |
| 5m | swing-5 SL, trail 2/2 ATR | 581 | 27% | 1.17 | 1.14 / 1.21 | +0.107R | +29.1% / 17.6% | 55% | 0.85 |
| 15m | ATR SL 1.5, trail 1/0.75, time stop 24 | 206 | 56% | 1.36 | 1.29 / 1.49 | +0.112R | +10.4% / 3.0% | 58% | 1.02 |
| 30m | swing-5 SL, trail 2/2 ATR | 68 | 31% | 1.55 | 1.82 / 1.37 | +0.233R | +7.8% / 5.6% | 85% | **1.78** |
| 1h | PSAR flip exit | 22 | 41% | 1.27 | 1.41 / 1.16 | +0.062R | +0.6% / 1.5% | 42% | 0.41 |
| 2h | time stop 24 | 20 | 30% | 1.25 | 1.51 / 1.13 | +0.044R | 0% (lot rounds to 0) | 25% | 0.19 |
| 4h | — fewer than 20 trades | | | | | | | | |

## BTCUSD
| TF | Best method | Trades | Win | PF | PF train / test | Exp. | 0.5% return / DD | Neighbours + | Default PF |
|---|---|---|---|---|---|---|---|---|---|
| 1m | Fixed | 1074 | 55% | 0.50 | 0.53 / 0.44 | −0.167R | −58.8% | 0% | 0.19 |
| 5m | Fixed | 252 | 35% | 0.99 | 1.02 / 0.93 | −0.002R | −0.3% | 0% | 0.52 |
| 15m | Range14 SL 4, trail 2/0.5 | 127 | 65% | 1.52 | 1.31 / 1.81 | +0.100R | +6.1% / 2.3% | 54% | 0.80 |
| 30m | ATR50 SL 4, trail 2/0.5 | 140 | 56% | 1.49 | 1.35 / 1.73 | +0.070R | +4.5% / 1.8% | 47% | 0.91 |
| 1h | Donchian20 SL 1, trail 2/2 | 32 | 41% | 1.46 | 1.23 / 2.85 | +0.241R | +3.5% / 4.2% | 81% | 0.46 |
| 2h | time stop 12 | 20 | 25% | 1.18 | 1.12 / 1.33 | +0.025R | 0% | 46% | 1.05 |
| 4h | TDI-cross exit | 26 | 42% | 1.63 | 1.69 / 1.56 | +0.106R | +1.3% / 0.4% | 17% | 3.37 (16 trades) |

## Which distance method wins
* No unit beats ATR consistently. ATR(14), ATR(50) and Range14 (average high-low) sit at or near
  the top on every profitable timeframe; the winner changes from one timeframe to the next by
  small margins, which is noise at this sample size.
* Swing stop-loss (behind the last 5 bars' low / high) is the one alternative that clearly
  helps gold 5m and 30m (30m expectancy +0.23R vs +0.09R with ATR), and is the worst choice on
  every BTC timeframe.
* Close-based exits (TDI cross, EMA20, PSAR) lose on 15m / 30m and only show up as "best" on
  1h–4h, where there are 20–26 trades.
* Percent-of-price and fixed-$ only "win" on 1m / 5m, where everything loses.

Caveat: ~216 entries × 16 methods × up to 100 settings per timeframe on 5–6 weeks of data.
The best rows are optimistic; trust the timeframes where most neighbouring settings are also
profitable (gold 30m 85%, BTC 1h 81% but only 32 trades).
