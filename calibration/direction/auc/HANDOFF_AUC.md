# BTC/USD parent / child-zone calibration of the FlashGold Direction Filter (AUC) - handoff

Evidence for an MT5 port of the FlashGold Direction Filter v1.2 (`flashgold_direction_filter.pine`). **BTC only**
(Bitstamp BTC/USD 1-minute data, UTC); keep it separate from any XAUUSD evidence.

## What was scored
- **Output**: the filter's zone at each closed filter-timeframe candle: +1 BUY ZONE (close > level + band), -1 SELL ZONE
  (close < level - band), 0 NO TRADE. v1.2 defaults: Level = Entry price (ask + 0.25 ATR after a BUY, bid - 0.25 ATR
  after a SELL), band = 0.25 x ATR(14) of the signal candle (Wilder, as Pine `ta.atr`), trading against the signal
  allowed. Signal inputs at their defaults: spread 25 x mintick, burst 0.5 ATR, entry hold 0, one signal per bar, TDI RSI
  14 / fast 2 (fast rising = BUY), "allow trade if parent flat" off, "ignore zones without data" on, child zones above
  the filter timeframe read from their last CLOSED bar.
- **Label**: sign(close[t+H] - close[t]) at H = 1, 3 and 10 filter candles; ties dropped; first 300 candles warm-up.
- **ROC-AUC** of the 3-valued zone vs the label, ties counted half (0.5 = no information; independent of drift).
  **Accuracy** = share right among the candles with a zone (zone != 0); **balanced accuracy** (in the CSV) = mean of
  P(up | BUY ZONE) and P(down | SELL ZONE); **coverage** = share of candles with a zone.
- **Splits**: train = 2023; validation = 2024-01 .. 2025-06; final test = 2025-07 .. 2026-10-11.

## Search and selection rule (train + validation only)
- Grid per filter timeframe (5m, 15m, 30m, 1H, 2H, 4H, 8H, 1D): parent x1 / x2 / x4 / x8 / x16 of the filter timeframe;
  child-zone sets x1, x2, x4, x1/x2, x1/x4, x2/x4, x1/x2/x4, x2/x4/x8, x1/x4/x16, x4/x8/x16, x1/x2/x4/x8; minimum aligned
  1 .. size of the set; plus zones off = 126 sets per timeframe (`auc_grid_all.csv`, 1008 rows).
  Multiples above a day are rounded to whole days (32H -> 1D), as the Pine code does; intraday intervals that do not
  divide the day restart at 00:00 UTC (16H = 00-16, 16-24).
- **Tuned candidate**: the highest train+validation AUC (mean of H = 1, 3, 10) among the sets whose H=10 AUC is above 0.5
  in each of 2023, 2024 and 2025 H1.
- **Use it only if** the Spearman rank correlation of all 126 sets' AUC between train and validation is above 0.3
  (the ranking carries from one period to the next); otherwise keep the default (parent x1, zones x1/x2/x4, 2 aligned).
- **Caveat on the rule itself**: the fallback rule and its 0.3 threshold were written after a first run of the same
  grid that printed final-test AUC and final-test rank correlations. Every per-timeframe choice uses train/validation
  numbers only, but the rule's design was not blind to the test period; read the test column as slightly optimistic for
  the rule (the per-setting test values themselves are plain measurements).

## Result (chosen settings; all have parent = the filter timeframe)

| Filter TF | Rule result | Parent TF | Child zone TFs | Min aligned | AUC train / valid / **test** (mean of H=1,3,10) | Accuracy train / valid / **test** | Coverage test | Test AUC H=1 / H=10 | Default test AUC |
|---|---|---|---|---|---|---|---|---|---|
| 5m | tuned (rank corr 0.86) | 5m | 10m/20m/40m | 1 | 0.520 / 0.511 / **0.511** | 0.521 / 0.512 / **0.512** | 0.83 | 0.508 / 0.512 | 0.509 |
| 15m | tuned (rank corr 0.76) | 15m | 15m/30m/1H/2H | 2 | 0.532 / 0.513 / **0.515** | 0.533 / 0.513 / **0.515** | 0.83 | 0.515 / 0.515 | 0.512 |
| 30m | default (rank corr 0.22) | 30m | 30m/1H/2H | 2 | 0.533 / 0.511 / **0.510** | 0.533 / 0.511 / **0.511** | 0.83 | 0.505 / 0.517 | 0.510 |
| 1H | tuned (rank corr 0.33) | 1H | 4H/8H/16H | 1 | 0.520 / 0.521 / **0.497** | 0.520 / 0.522 / **0.497** | 0.82 | 0.497 / 0.493 | 0.499 |
| 2H | tuned (rank corr 0.84) | 2H | 2H/8H/1D | 2 | 0.521 / 0.526 / **0.524** | 0.522 / 0.526 / **0.524** | 0.84 | 0.517 / 0.530 | 0.512 |
| 4H | default (rank corr -0.62) | 4H | 4H/8H/16H | 2 | 0.518 / 0.493 / **0.508** | 0.518 / 0.494 / **0.510** | 0.83 | 0.492 / 0.525 | 0.508 |
| 8H | default (rank corr 0.01) | 8H | 8H/16H/1D | 2 | 0.550 / 0.510 / **0.501** | 0.548 / 0.511 / **0.501** | 0.85 | 0.516 / 0.480 | 0.501 |
| 1D | default (rank corr 0.00) | 1D | 1D/2D/4D | 2 | 0.518 / 0.504 / **0.519** | 0.506 / 0.504 / **0.519** | 0.81 | 0.475 / 0.577 | 0.519 |

"Default test AUC" = parent x1, zones x1/x2/x4, 2 aligned, on the same test period. Full metrics per split and horizon
(AUC, accuracy, balanced accuracy, up rate, calls, coverage, buy/sell-zone shares) for the chosen, default and
tuned-but-not-chosen settings: `handoff_chosen.csv`. Choice details: `auc_pick.json`.

## Caveats
- The effects are small: AUC 0.50-0.53, accuracy within a point or two of AUC. The tuned choice beat the default on the
  test period on 5m (+0.002), 15m (+0.003) and 2H (+0.012), and was 0.002 worse on 1H, whose test AUC is below 0.5.
- Across all 126 sets, the train+validation vs test rank correlation is 0.86 (5m), 0.70 (15m), 0.64 (30m) and -0.57 to
  -0.06 from 1H up: above 30m the ordering of the settings does not carry into new data (2H's good test AUC included).
- Multiple testing: 1008 sets; one asset; one chronological split; Bitstamp UTC bars (a broker's server-time bars differ).
- "Signal only" (trade only the confirmed signal side, i.e. "Allow trading against the signal" off) scored AUC 0.49-0.50
  on average, below the zones; the bare level (band 0) scored about the same as the 0.25 ATR band.

## Multi-timeframe repainting notes for an all-closed-bar MQL5 port
1. Judge the zone only on closed filter-timeframe candles (the score uses the close of candle t and data up to it).
2. **Parent**: every chosen preset uses parent = the filter timeframe, so no higher-timeframe parent is needed. If a user
   sets a higher parent, read its last CLOSED bar. The Pine filter's own parent read is a plain `lookahead_off`
   request, which sees the parent bar still forming live (it repaints); the calibration used the closed-bar read.
3. **Child zones** above the filter timeframe: the calibration reads the zone bar BEFORE the one that contains the
   filter candle's OPEN time (Pine `[1]` + `lookahead_on`; engine `map_prev_on`). This is stricter than "the last zone
   bar closed by the filter candle's close": on the filter candle that closes together with a zone bar, the calibrated
   read still uses the previous zone bar. MQL5 equivalent: `iBarShift(sym, zoneTF, filterBarOpenTime, false) + 1` (check
   the exact-match flag and gaps). A zone equal to the filter timeframe uses the same closed candle.
4. **Timeframes MT5 does not have**: 40m (5m preset) and 16H (1H preset; also 4H/8H defaults) must be aggregated from
   lower bars on UTC-midnight-anchored bins (16H = 00:00-16:00 and 16:00-24:00, the second bar 8 hours). 2D / 4D (1D
   default) are anchored to 2023-01-01 in the engine (TradingView's anchor is unverified). 32H is rounded to D1.
5. **Server time**: MT5 H4 / H8 / D1 bars follow the broker's server time (often UTC+2/+3), so their boundaries differ
   from these UTC bars. Build the zone timeframes from M1/H1 in UTC to match this calibration, or recalibrate on
   server-time bars.
6. **Indicators**: Pine `ta.atr` / `ta.rsi` are Wilder RMA with an SMA seed; MT5's `iATR` is a plain SMA of the true
   range. Compute RSI, the SMA(2) fast line and ATR yourself (the earlier port's `CTf::Calc` in
   `mt5/FlashGold_Direction_Filter.mq5` already mirrors Pine). TDI direction compares the fast line's last two closed
   values.
7. **Units**: the spread input is in mintick units (25 x 0.01 on BTC here); MT5 `_Point` may differ per broker.
   Burst, entry distance and band are in ATR units and need no conversion.
8. **Warm-up**: zones at 16 x the filter timeframe need about 16 x 16 filter candles before their RSI(14) + SMA(2)
   exist; a 999-bar H1 sample holds fewer than 100 16H zone bars (two per day with the 00:00 reset), far less than this
   calibration's 2023-2026 history.

## Files
- `auc_grid_all.csv`: every set, every split (train2023 / valid2024_25H1 / trainvalid / test), H = 1, 3, 10, for the zone
  output, the bare level and signal-only, with coverage and per-year minimum.
- `handoff_chosen.csv`, `auc_pick.json`: the chosen settings and their metrics.
- Scripts (in `calibration/`): `dir_auc.py` (grid), `eval_chosen.py` (handoff metrics), the engine `fgengine.py` / `fgrun.py`
  (parity-checked against a TradingView export), `prep_data.py` (data).
