# Parity export for the Pine filter's score veto

Made by `calibration/wf/veto_pine_parity.py` from Bitstamp BTC/USD 1-minute candles (UTC bars as TradingView builds
them; 10m / 20m / 2H / 4H child bars start at 00:00 UTC). One file per model timeframe, the last 3,000 closed filter
candles up to 2026-10-11 02:00 UTC:

| column | meaning |
|---|---|
| `time_open`, `time_open_utc` | the filter candle's open time (epoch seconds; UTC text) |
| `close` | its close |
| `zone` .. `f_slope_4tf` | the score's 17 inputs, in the order of the Pine Data Window plots `FGV in 1 .. 17` |
| `inputs_ready` | 1 when every input is defined (Pine: `FGV answer` can be non-zero only then) |
| `score` | the frozen H = 3 model's log-odds (Pine: `FGV score (last filter candle)` / `FGF veto score`) |
| `answer` | 1 UP (score > q_hi), -1 DOWN (score < q_lo), 0 undecided (Pine: `FGV answer`) |
| `zone_P0` | the filter's zone at that close: 1 BUY ZONE, -1 SELL ZONE, 0 NO TRADE (Pine: `FGV in 1 zone`) |
| `veto_permission` | the zone where the answer agrees with it, else 0 (Pine: `FGF score veto` with the veto on, read on the next candle) |

## How to compare on TradingView
1. Chart **BITSTAMP:BTCUSD**, chart timeframe = the filter timeframe (5, 15, 30 or 60 minutes), exchange time zone UTC.
2. Add `flashgold_direction_filter.pine` with every input at its default, **Filter timeframe = the chart timeframe**,
   and switch on "Score inputs in the Data Window" (group "Score veto"). The veto switch itself may stay off: the
   inputs and the score are computed either way.
3. Hover a closed candle; in the Data Window read `FGV in 1 .. 17`, `FGV score (last filter candle)` and `FGV answer
   (last filter candle)` and compare with the row of the same `time_open_utc` (the candle's open time).
4. Expect the inputs to agree to about 1e-6 and the answer to be identical, once the chart has a few hundred candles of
   history before the compared candle: the RSI / ATR seeds, the 100-candle ATR average, the FDF structure state and the
   last signal all need history to line up (Bitstamp's data in TradingView and in this export can also differ by a
   missing or corrected 1-minute candle; such a difference is local and disappears after the next signal).
5. `zone` must equal the filter's own zone at that close (`FGF zone` with the veto off, judged at the candle's close,
   "Check price on" = Tick on a closed candle), by construction.

## The frozen model on TradingView's UTC bars (aggregate, 2026-01-01 .. 2026-10-11)
`aggregates_2026_utc.csv`: the frozen `veto_model_2026.json` (fitted on the broker's clock, New York + 7 h) applied to
Bitstamp UTC candles, raw accuracy of the allowed side (P0 = zone alone, R2s = zone + veto) and the share of candles
with a permission, labels ending inside the window. At 1 candle ahead:

| TF | P0 acc / coverage | R2s acc / coverage | gain |
|---|---|---|---|
| M5 | 50.87% / 84.6% | 52.24% / 54.0% | +1.4 pt |
| M15 | 51.56% / 84.5% | 53.51% / 53.1% | +1.9 pt |
| M30 | 51.08% / 83.5% | 52.29% / 54.0% | +1.2 pt |
| H1 | 50.27% / 82.6% | 52.46% / 45.1% | +2.2 pt |

These are within 0.3 pt of the clock-matched run in `../veto_eval.csv` (secondary 2026, R2s, H = 1): the 2H / 4H child
bars of the M30 / H1 models starting at 00:00 UTC instead of the broker's hour costs little here. No confidence
intervals were computed for this table; it is a consistency check, not a new test. 2026 was inspected during the veto
study, so these are not fresh numbers either.
