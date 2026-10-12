# Port contract: option 2 (score veto) for an optional MQL5 implementation

> **Status: coefficients and contract are frozen (model fitted before any 2026 evaluation; commit `196d771`).
> The independent historical verification of the option-2 result (recompute, regime, leakage) is still running; its
> recompute part has already matched the frozen CSV to rounding. This file is published so the MT5 study can build
> and run its fresh 2026 broker test without waiting. Nothing here is a default change.**

Research deliverable for the MT5 study. **No Pine or MT5 default changes**; a port is a separate, optional output,
off by default. Model file: `results/veto/veto_model_2026.json` (fitted on Bitstamp BTC/USD re-stamped to the broker
server clock New York + 7h, 2020-01-01 with labels ending before 2026-01-01). Private parity fixture: sent apart, not
in the repository (it holds broker candles).

## 1. Prerequisites (P0 must match first)
The score reads the filter's own state, so the port's P0 must equal the calibrated zone before the score can match:
- Native default: parent = the filter timeframe; child zones = the native x1 / x2 / x4 set (M5: M5/M10/M20, M15:
  M15/M30/H1, M30: M30/H1/H2, H1: H1/H2/H4); minimum aligned 2; "ignore zones without data" on; signal inputs at the
  v1.2 defaults (spread 25 points, burst 0.5 ATR, entry distance 0.25 ATR, hold 0, one signal per bar, TDI RSI 14 /
  fast 2, flat parent off).
- Reads: parent from the last parent bar closed by the filter candle's close (parent = filter TF, so the same candle);
  child zones above the filter TF from the last child bar closed by the filter candle's **open** (`[1]` +
  lookahead_on; `map_prev_on`); child zones equal to the filter TF from the same closed candle.
- Zone edges: level +- 0.25 x ATR(14) of the signal candle, edges rounded outward to the tick (0.01) and the close must
  clear the rounded edge by more than half a tick (v1.2 rule).
- Everything on **closed** filter candles only.

## 2. Features (17 inputs in this order; `features` in the JSON has 18 entries, `b0` first then the 17 inputs)
All at the close of filter candle t. ATR = Wilder ATR(14) of the filter timeframe (SMA seed, as Pine `ta.atr`);
RSI = Wilder RSI(14) (SMA seed); fast line F = SMA(2) of RSI.

| # | name | definition | note |
|---|---|---|---|
| 1 | `zone` | P0 as a number: +1 BUY ZONE, -1 SELL ZONE, 0 NO TRADE | |
| 2 | `dist` | (close - level) / ATR_signal, clipped to [-5, +5]; 0 when there is no level yet | ATR_signal = ATR(14) at the signal candle |
| 3 | `side` | last FlashGold signal: +1 BUY, -1 SELL, 0 none yet | |
| 4 | `r1` | (close - close[1]) / ATR(14)[t], clipped to [-10, 10] | ATR of candle t, not the signal's |
| 5 | `r5` | (close - close[5]) / ATR(14)[t], clipped | |
| 6 | `r20` | (close - close[20]) / ATR(14)[t], clipped | |
| 7 | `vol` | ATR(14)[t] / SMA(100)(ATR(14))[t], clipped to [0, 5] | SMA over the last 100 ATR values, all present |
| 8 | `age` | ln(1 + candles since the last signal candle) (0 on the signal candle) | |
| 9 | `zone_vol` | zone x vol | |
| 10 | `dist_vol` | dist x vol | |
| 11 | `fdir` | FDF structure direction of the filter timeframe: +1 / -1 / 0 (pivots L=5 R=3; as `CFdf` in the EA) | |
| 12-13 | `f<tf>`, `s<tf>` | zone 1 (the filter TF): level (F - 50) / 50 and slope (F - F[1]) / 10 of its fast line | same candle |
| 14-15 | `f<2tf>`, `s<2tf>` | zone 2 (x2 native): same, from the bar closed by the filter candle's open | e.g. M10 for M5 |
| 16-17 | `f<4tf>`, `s<4tf>` | zone 3 (x4 native): same | e.g. M20 for M5 |
| - | `b0` | intercept = `w[0]` (listed first in `features`) | not an input |

Exact JSON names per timeframe: M5 `f5 s5 f10 s10 f20 s20`; M15 `f15 s15 f30 s30 f60 s60`; M30 `f30 s30 f60 s60 f120
s120`; H1 `f60 s60 f120 s120 f240 s240`.

**Missing features:** a candle with any undefined input (warm-up: fewer than 100 ATR values, no RSI yet, a child zone
without data) is **not scored**: the veto returns NO TRADE and the candle is excluded from metrics. The calibration
never imputes. `dist` is the one exception: it is 0 (not missing) when no signal has fired yet, and `age` is missing
until the first signal.

## 3. Score
`logit = w[0] + sum_{i=1..17} w[i] * (x_i - mu[i-1]) / sd[i-1]` with `w` (length 18, `w[0]` = b0), `mu` and `sd`
(length 17, aligned with `features[1:]`) from the JSON. Units: log-odds of "close H candles later is higher"; no sigmoid is needed for the rule. Double precision.

## 4. Permission and veto
- `G2P = BUY if logit > q_hi; SELL if logit < q_lo; else NO TRADE` (strict inequalities; equality = NO TRADE).
  `q_lo` / `q_hi` are the 41.5% / 58.5% quantiles of the training scores, stored per model.
- **Option 2 (R2s, the version to port): one model for every use, the `"3"` entry (H = 3).**
  `veto = P0 if (P0 != 0 and G2P == P0) else NO TRADE`. It never reverses P0.
- The horizon-specific variant (R2: model "1" for a 1-candle view, "3", "10") is reported in the research for
  completeness; the frozen test shows R2s within 0.3-0.5 points of R2. Use "3" unless the study asks otherwise.
- `k_dist` is the threshold of the DV baseline (|dist| >= k keeps the zone); it is for research comparison only.

## 5. Timing and clock
- Compute everything on the closed candle; the permission applies from the next candle's open until the next close
  (same lifetime as the zone's "Permission lasts = next candle").
- Models were fitted on the broker server clock (New York + 7h). Child-zone boundaries (M10 / M20 / H2 / H4) must
  follow the same clock as the terminal's native bars.
- Warm-up: at least 100 filter candles for `vol`, plus 16 x 4 = 64 candles of the x4 child for its RSI/SMA; use the
  terminal's full history.

## 6. Parity fixture (private, sent apart)
`fixture_<TF>.csv`: the last 2,000 scorable broker candles of 2025 per timeframe with `time_server` (epoch seconds,
server clock), `close`, every feature, `P0_zone`, `logit_H1/H3/H10`, `G2P_H1/H3/H10`, `G2P_used` (= H3), `veto_R2s`,
`DV_baseline`. Expected parity: features to 1e-6 relative, logits to 1e-6, P0 / G2P / veto identical on every row.
`fixture_aggregates.csv`: coverage and raw accuracy of P0 and R2s on the slice per horizon (labels ending inside the
slice), for an aggregate check after the row-level one.

## 7. What the frozen test says (for the study's record, `PREREG_VETO.md`, `results/veto/`)
Fresh Bitstamp 2018-2019 (never evaluated before): R2 raises raw accuracy over the zone by +4.3 / +4.1 / +4.0 points
on M5 / M15 / M30 (95% CIs entirely above +3.5) at about 46-48% coverage instead of 85%, AUC +0.024; 2021-2022:
+2.2 / +2.4 / +2.4; 2026 (Jan-Oct): +1.8 / +2.0 / +1.1. A distance-only veto of the same size is worse than the zone.
Caveat (HANDOFF section 11): about 1-1.5 pt of the 2018-19 M5 figure is Bitstamp's last-trade bounce and the rest
is an era-specific regime; the deployment-relevant size is the fresh broker test, M5 H = 1 **+1.1 pts [+0.6, +1.5]**
at coverage 84% -> 53% (`results/veto/codex_fresh_broker_2026.md`).
The independent verification of this run is reported in `HANDOFF_WF.md` section 11 when complete (recompute part
done: all M5 / M15 / M30 metrics, thresholds and training-window checks match). The 2026 broker
candles are the remaining fully fresh test: `python wf_veto.py apply <broker_csv> 2026-01-01 <end> veto_model_2026.json`.
