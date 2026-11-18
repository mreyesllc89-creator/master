# XPW Shape Map v0.9.2 — trailing-stop calibration (XAUUSD 15m, CONT entries)

Date: 2026-11-18. Entries are fixed; only the exit after entry was varied.

## Data
* `data/CAPITALCOM_XAUUSD_15.csv` — chart export, 2026-08-12 → 2026-11-17 (6 356 candles), with the
  strategy's own signal columns.
* `data/XPW-SM9.2_trades_2026-11-17.csv` — the 14 trades TradingView listed.
* Set A (39 entries): signals that passed the direction filter, plus the 14 listed trades.
  Set B (249 entries): every raw CONT signal, filter ignored (a larger cross-check).

## Method
`tools/engine.py` replays each entry at the signal candle's close and manages the exit on the 15m
candles: SL 1 × ATR(14), optional TP, opposite signal reverses. With the current settings and
TradingView's intrabar rule it reproduces all 14 listed exits to within one cent.

15m candles do not say in which order the high and low were made, so each variant was run twice:
* **TV rule** — TradingView's assumption (open → nearer extreme → farther extreme → close).
* **Random paths** — 4 random 600-step paths per candle that match its open/high/low/close.

Results are in R (1 R = the 1 ATR stop = the 2 % risk per trade). Two cost cases: the 0.02 % per
side commission from the trade list (≈ 0.22 R per trade) and a spread-only $0.50 round trip
(≈ 0.07 R per trade). `tools/sweep.py` runs 5 322 variants; `results/sweep.csv` has all of them
(gross R; `_ea`/`_ia` columns give the cost terms).

## Results, set A (39 trades)

| Exit | TV rule, 0.02 % | Random paths, 0.02 % | Random paths, spread only |
|---|---|---|---|
| Current: trail 0.02 / 0.02 ATR, TP 2 R | +11.6 R | −6.0 R | 0.0 R |
| No trail, TP 3 R | +3.0 R | +3.0 R | +8.6 R |
| **Trail after 3 same-direction candles, 0.02 / 0.1 ATR, TP 5 R** | +7.8 R | **+6.5 R** | **+12.4 R** |

* The current 0.02 ATR trail (about $0.15) only looks good under the TV rule, which lets the stop
  sit just under the candle's high before price comes back. On random paths it exits at the first
  wiggle and the commission is larger than the average gain.
* Best family across the sweep: keep SL/TP only, and switch a tight trail on after 3 candles in a
  row close in the trade's direction. Both halves of the period are positive; N = 2 and TP 3–5 R
  are also positive, N = 4+ is mixed. Trail distance 0.02–0.2 ATR barely matters.
* With the 0.02 % commission, 17 % of all variants are positive on set A and none on set B. On set
  B the recommended exit is −34.5 R with commission and +2.8 R spread-only.

## Limits
* 38 trades. Bootstrap 5–95 % range for the recommended exit: −9.6 R … +23.8 R with commission.
  This is a lead, not proof.
* No tick or 1-minute data was available; the random paths are a model.

## Pine change
`trail_after_n_candles.pine.patch.txt` — one new input and one replaced block.
