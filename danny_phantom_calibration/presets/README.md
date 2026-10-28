# Calibrated presets, one per timeframe

Load the `.set` file into MT5 Strategy Tester (Inputs → Load), on the chart timeframe named in the
section, on a USD account, and give each independent run its own `RecoverySession`. The strategy's
sizing (`Risk % = 1.0`, margin cap) and all inputs not listed are the shipped values. Statistics are
from the Python replica described in `../REPORT.md`, with today's spread ($0.12 gold, 2.2 bp bitcoin),
1 % risk per trade and a $10 000 start; 'OOS' = 2016-2018 (gold) / 2018-2019 (bitcoin), '2026' = your
July-August 2026 Octa export. Verdicts: RECOMMENDED > USABLE > PAPER-TRADE > NOT RECOMMENDED > DO NOT TRADE.

| Preset | Chart | Verdict | Trades/yr | PF | Win % | Return | Max DD | OOS t | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| `DPFX_BTCUSD_M1_calibrated.set` | BTCUSD M1 | DO NOT TRADE | 27462 | 1.28 | 45 | 105,608 % | 10.8 % | 14.2 | 4404 tr, -0.24 R |
| `DPFX_BTCUSD_M2_calibrated.set` | BTCUSD M2 | DO NOT TRADE | 22757 | 1.27 | 45 | 70,956 % | 7.7 % | 22.4 | 4086 tr, -0.18 R |
| `DPFX_BTCUSD_M3_calibrated.set` | BTCUSD M3 | DO NOT TRADE | 19320 | 1.19 | 29 | 43,146 % | 17.5 % | 17.5 | 2682 tr, -0.38 R |
| `DPFX_BTCUSD_M5_calibrated.set` | BTCUSD M5 | DO NOT TRADE | 19296 | 1.20 | 33 | 45,643 % | 8.0 % | 13.5 | 2468 tr, -0.41 R |
| `DPFX_BTCUSD_M10_calibrated.set` | BTCUSD M10 | DO NOT TRADE | 9674 | 1.30 | 28 | 33,415 % | 5.6 % | 8.0 | 1767 tr, -0.33 R |
| `DPFX_BTCUSD_M15_calibrated.set` | BTCUSD M15 | DO NOT TRADE | 10547 | 1.19 | 31 | 27,634 % | 12.5 % | 9.0 | 1793 tr, -0.23 R |
| `DPFX_BTCUSD_M30_calibrated.set` | BTCUSD M30 | DO NOT TRADE | 5678 | 1.16 | 27 | 17,309 % | 13.7 % | 3.6 | 1040 tr, -0.18 R |
| `DPFX_BTCUSD_M60_calibrated.set` | BTCUSD H1 | PAPER-TRADE FIRST | 233 | 1.43 | 43 | 1,754 % | 16.9 % | 2.9 | 37 tr, -0.17 R |
| `DPFX_BTCUSD_M240_calibrated.set` | BTCUSD H4 | RECOMMENDED — rank 4 | 221 | 1.61 | 39 | 585 % | 8.1 % | 2.8 | 36 tr, +0.22 R |
| `DPFX_XAUUSD_M1_calibrated.set` | XAUUSD M1 | NOT RECOMMENDED | 288 | 1.27 | 25 | 332 % | 13.2 % | 2.6 | 1036 tr, +0.10 R |
| `DPFX_XAUUSD_M2_calibrated.set` | XAUUSD M2 | NOT RECOMMENDED | 154 | 1.44 | 27 | 266 % | 10.8 % | 1.4 | 1045 tr, -0.02 R |
| `DPFX_XAUUSD_M3_calibrated.set` | XAUUSD M3 | NOT RECOMMENDED | 664 | 1.09 | 32 | 399 % | 37.2 % | 1.0 | 632 tr, -0.08 R |
| `DPFX_XAUUSD_M5_calibrated.set` | XAUUSD M5 | USABLE — secondary | 70 | 1.55 | 34 | 220 % | 10.1 % | 1.8 | no trades |
| `DPFX_XAUUSD_M10_calibrated.set` | XAUUSD M10 | USABLE — secondary | 86 | 1.46 | 29 | 206 % | 16.8 % | 1.1 | no trades |
| `DPFX_XAUUSD_M15_calibrated.set` | XAUUSD M15 | RECOMMENDED — rank 3 | 70 | 1.54 | 61 | 157 % | 8.0 % | 2.3 | no trades |
| `DPFX_XAUUSD_M30_calibrated.set` | XAUUSD M30 | RECOMMENDED — rank 2 | 242 | 1.22 | 59 | 229 % | 15.3 % | 2.3 | 24 tr, -0.03 R |
| `DPFX_XAUUSD_M60_calibrated.set` | XAUUSD H1 | RECOMMENDED — rank 1 | 136 | 1.32 | 44 | 275 % | 12.2 % | 1.9 | 26 tr, +0.03 R |
| `DPFX_XAUUSD_M240_calibrated.set` | XAUUSD H4 | USABLE — secondary | 32 | 1.76 | 51 | 125 % | 7.2 % | 1.4 | 2 tr, -0.59 R |

## BTCUSD M1 — `DPFX_BTCUSD_M1_calibrated.set`

**Chart:** BTCUSD, M1 (1-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 20-bar volume-delta lookback with a 1.25x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 2 x ATR(50), no fixed target; trailing stop armed at 0.5 ATR profit, trailing 1 ATR behind; time stop after 100 bars; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 137312 trades (27462/yr), PF 1.28, 45 % wins, avg +0.12 R, return 105,608 % with 10.8 % max drawdown; in-sample t 27.5, out-of-sample t 14.2 (68246 trades, +0.09 R). With the broker spread recorded at the time: 87,071 %; with no spread (TradingView default): 190,232 %. 2026 export: 4404 trades, -0.24 R.

Exits: stop 110690 / tp 0 / dead 0 / time 2 / blackout 0 / reverse 26620.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **2.0** | 0.5 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **1.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **100** | 50 |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **20** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **20** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |

## BTCUSD M2 — `DPFX_BTCUSD_M2_calibrated.set`

**Chart:** BTCUSD, M2 (2-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 1 x ATR(50), 10 R target; trailing stop armed at 0.5 ATR profit, trailing 0.5 ATR behind; dead-trade exit after 10 bars without profit; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2015-2019):** 113787 trades (22757/yr), PF 1.27, 45 % wins, avg +0.16 R, return 70,956 % with 7.7 % max drawdown; in-sample t 20.8, out-of-sample t 22.4 (58194 trades, +0.17 R). With the broker spread recorded at the time: 56,299 %; with no spread (TradingView default): 129,272 %. 2026 export: 4086 trades, -0.18 R.

Exits: stop 101603 / tp 1021 / dead 0 / time 0 / blackout 230 / reverse 10933.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.0** | 0.5 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.5** | 0.01 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **10** | 15 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |

## BTCUSD M3 — `DPFX_BTCUSD_M3_calibrated.set`

**Chart:** BTCUSD, M3 (3-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter on; stop 0.75 x ATR(50), 15 R target; trailing stop armed at 1 ATR profit, trailing 0.5 ATR behind; dead-trade exit after 5 bars without profit; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 96599 trades (19320/yr), PF 1.19, 29 % wins, avg +0.18 R, return 43,146 % with 17.5 % max drawdown; in-sample t 17.7, out-of-sample t 17.5 (45896 trades, +0.19 R). With the broker spread recorded at the time: 32,207 %; with no spread (TradingView default): 89,929 %. 2026 export: 2682 trades, -0.38 R.

Exits: stop 91421 / tp 584 / dead 0 / time 0 / blackout 0 / reverse 4594.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.75** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **15.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **1.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.5** | 0.01 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **5** | 15 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |

## BTCUSD M5 — `DPFX_BTCUSD_M5_calibrated.set`

**Chart:** BTCUSD, M5 (5-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 1.0x spike threshold, entry on a retest touch; EMA(20) trend filter off; stop 0.5 x ATR(30), no fixed target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 50 bars; dead-trade exit after 10 bars without profit; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 96478 trades (19296/yr), PF 1.20, 33 % wins, avg +0.18 R, return 45,643 % with 8.0 % max drawdown; in-sample t 16.3, out-of-sample t 13.5 (44603 trades, +0.17 R). With the broker spread recorded at the time: 33,357 %; with no spread (TradingView default): 96,069 %. 2026 export: 2468 trades, -0.41 R.

Exits: stop 88412 / tp 0 / dead 0 / time 0 / blackout 5 / reverse 8061.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **10** | 15 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Session & quality filters | `manualLossClusterCount` — Losses before pause | **3** | 5 |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |

## BTCUSD M10 — `DPFX_BTCUSD_M10_calibrated.set`

**Chart:** BTCUSD, M10 (10-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 100-bar volume-delta lookback with a 1.0x spike threshold, entry on a retest touch; EMA(20) trend filter on; stop 0.3 x ATR(30), 6 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 50 bars; dead-trade exit after 15 bars without profit; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 48369 trades (9674/yr), PF 1.30, 28 % wins, avg +0.14 R, return 33,415 % with 5.6 % max drawdown; in-sample t 12.5, out-of-sample t 8.0 (21350 trades, +0.11 R). With the broker spread recorded at the time: 28,319 %; with no spread (TradingView default): 55,037 %. 2026 export: 1767 trades, -0.33 R.

Exits: stop 43547 / tp 3154 / dead 0 / time 0 / blackout 7 / reverse 1661.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.3** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **6.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **5** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |

## BTCUSD M15 — `DPFX_BTCUSD_M15_calibrated.set`

**Chart:** BTCUSD, M15 (15-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 100-bar volume-delta lookback with a 1.25x spike threshold, entry on a retest touch; EMA(50) trend filter off; stop 0.3 x ATR(50), 15 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 200 bars; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 52734 trades (10547/yr), PF 1.19, 31 % wins, avg +0.13 R, return 27,634 % with 12.5 % max drawdown; in-sample t 10.7, out-of-sample t 9.0 (23266 trades, +0.12 R). With the broker spread recorded at the time: 22,900 %; with no spread (TradingView default): 48,716 %. 2026 export: 1793 trades, -0.23 R.

Exits: stop 43136 / tp 209 / dead 0 / time 0 / blackout 44 / reverse 9345.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.3** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **15.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **200** | 50 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |

## BTCUSD M30 — `DPFX_BTCUSD_M30_calibrated.set`

**Chart:** BTCUSD, M30 (30-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 30-bar volume-delta lookback with a 1.25x spike threshold, entry on a retest touch; EMA(20) trend filter off; stop 0.3 x ATR(50), 6 R target; time stop after 10 bars; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 28390 trades (5678/yr), PF 1.16, 27 % wins, avg +0.11 R, return 17,309 % with 13.7 % max drawdown; in-sample t 9.3, out-of-sample t 3.6 (12454 trades, +0.06 R). With the broker spread recorded at the time: 14,659 %; with no spread (TradingView default): 28,769 %. 2026 export: 1040 trades, -0.18 R.

Exits: stop 20510 / tp 1908 / dead 0 / time 42 / blackout 0 / reverse 5930.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.3** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **6.0** | 10 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **10** | 50 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |

## BTCUSD H1 — `DPFX_BTCUSD_M60_calibrated.set`

**Chart:** BTCUSD, H1 (60-minute bars). **Verdict: PAPER-TRADE FIRST.** Good 2015-2019 history (PF 1.43, every year profitable) but slightly negative on the 37 trades of the 2026 export.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 2 x ATR(7), 6 R target; time stop after 20 bars; NY session filter 0200-1700; gold NY-time window filters: directional; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 1167 trades (233/yr), PF 1.43, 43 % wins, avg +0.28 R, return 1,754 % with 16.9 % max drawdown; in-sample t 5.0, out-of-sample t 2.9 (481 trades, +0.22 R). With the broker spread recorded at the time: 1,709 %; with no spread (TradingView default): 1,909 %. 2026 export: 37 trades, -0.17 R.

Exits: stop 454 / tp 41 / dead 0 / time 565 / blackout 0 / reverse 106.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **2.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **6.0** | 10 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **20** | 50 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `useSessionFilter` — Use NY cash session filter | **True** | False |
| Session & quality filters | `nySession` — NY session | **0200-1700** | 0930-1600 |

## BTCUSD H4 — `DPFX_BTCUSD_M240_calibrated.set`

**Chart:** BTCUSD, H4 (240-minute bars). **Verdict: RECOMMENDED — rank 4.** The only bitcoin set that survives every test: profitable every year, cost-insensitive, positive on the 2026 export.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 2 x ATR(7), 2 R target; trailing stop armed at 0.5 ATR profit, trailing 2 ATR behind; time stop after 20 bars; breakeven at 1 ATR; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2015-2019):** 1104 trades (221/yr), PF 1.61, 39 % wins, avg +0.18 R, return 585 % with 8.1 % max drawdown; in-sample t 5.2, out-of-sample t 2.8 (494 trades, +0.11 R). With the broker spread recorded at the time: 594 %; with no spread (TradingView default): 641 %. 2026 export: 36 trades, +0.22 R.

Exits: stop 223 / tp 150 / dead 0 / time 4 / blackout 217 / reverse 509.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **2.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **2.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **2.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **20** | 50 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |

## XAUUSD M1 — `DPFX_XAUUSD_M1_calibrated.set`

**Chart:** XAUUSD, M1 (1-minute bars). **Verdict: NOT RECOMMENDED.** Edge halves with $0.05 extra slippage per fill; too cost-sensitive for live use.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1 x ATR(30), 15 R target; trailing stop armed at 3 ATR profit, trailing 0.5 ATR behind; gold NY-time window filters: all off; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2011-2018):** 2307 trades (288/yr), PF 1.27, 25 % wins, avg +0.20 R, return 332 % with 13.2 % max drawdown; in-sample t 3.7, out-of-sample t 2.6 (192 trades, +0.41 R). With the broker spread recorded at the time: -97 %; with no spread (TradingView default): 476 %. 2026 export: 1036 trades, +0.10 R.

Exits: stop 2273 / tp 4 / dead 0 / time 0 / blackout 0 / reverse 30.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **15.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **3.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.5** | 0.01 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **5** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **100** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |

## XAUUSD M2 — `DPFX_XAUUSD_M2_calibrated.set`

**Chart:** XAUUSD, M2 (2-minute bars). **Verdict: NOT RECOMMENDED.** Cost-sensitive and flat on the 2026 export (1 045 trades).

**Character:** inverted signals (as shipped); XAUUSD 5m auto profile; EMA(100) trend filter off; stop 0.5 x ATR(30), 10 R target; gold NY-time window filters: all off; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2011-2018):** 1232 trades (154/yr), PF 1.44, 27 % wins, avg +0.32 R, return 266 % with 10.8 % max drawdown; in-sample t 3.9, out-of-sample t 1.4 (102 trades, +0.38 R). With the broker spread recorded at the time: 31 %; with no spread (TradingView default): 354 %. 2026 export: 1045 trades, -0.02 R.

Exits: stop 902 / tp 36 / dead 0 / time 0 / blackout 7 / reverse 287.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |

## XAUUSD M3 — `DPFX_XAUUSD_M3_calibrated.set`

**Chart:** XAUUSD, M3 (3-minute bars). **Verdict: NOT RECOMMENDED.** Weakest gold set (PF 1.09, 37 % drawdown), negative on the 2026 export.

**Character:** inverted signals (as shipped); XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1.25 x ATR(7), 15 R target; gold NY-time window filters: robust-hour, V10.10; weekend blackout on, daily 16:55-18:00 blackout on.

**History (2011-2018):** 5310 trades (664/yr), PF 1.09, 32 % wins, avg +0.08 R, return 399 % with 37.2 % max drawdown; in-sample t 2.8, out-of-sample t 1.0 (716 trades, +0.08 R). With the broker spread recorded at the time: -94 %; with no spread (TradingView default): 740 %. 2026 export: 632 trades, -0.08 R.

Exits: stop 3598 / tp 4 / dead 0 / time 0 / blackout 508 / reverse 1200.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.25** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **15.0** | 10 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |

## XAUUSD M5 — `DPFX_XAUUSD_M5_calibrated.set`

**Chart:** XAUUSD, M5 (5-minute bars). **Verdict: USABLE — secondary.** Strong R per trade (+0.42) and 1.55 PF, but ~70 trades a year and an out-of-sample t-stat of only 1.8; no 2026 trades in the 28-day sample.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 4.0x spike threshold, entry on a retest touch; EMA(100) trend filter off; stop 1.5 x ATR(14), 8 R target; trailing stop armed at 4 ATR profit, trailing 2 ATR behind; time stop after 200 bars; entries only 08:00-17:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 563 trades (70/yr), PF 1.55, 34 % wins, avg +0.42 R, return 220 % with 10.1 % max drawdown; in-sample t 3.6, out-of-sample t 1.8 (129 trades, +0.37 R). With the broker spread recorded at the time: 110 %; with no spread (TradingView default): 255 %. 2026 export: no trades in the short sample.

Exits: stop 531 / tp 27 / dead 0 / time 0 / blackout 0 / reverse 5.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.5** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **8.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **4.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **2.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **200** | 50 |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **0800-1700** | 0800-1200 |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **5** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |

## XAUUSD M10 — `DPFX_XAUUSD_M10_calibrated.set`

**Chart:** XAUUSD, M10 (10-minute bars). **Verdict: USABLE — secondary.** Similar profile to M5; 2 losing years out of 8 and OOS t-stat 1.1.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 4.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter on; stop 0.75 x ATR(7), no fixed target; trailing stop armed at 4 ATR profit, trailing 2 ATR behind; time stop after 20 bars; entries only 08:00-12:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 688 trades (86/yr), PF 1.46, 29 % wins, avg +0.44 R, return 206 % with 16.8 % max drawdown; in-sample t 3.5, out-of-sample t 1.1 (115 trades, +0.39 R). With the broker spread recorded at the time: 90 %; with no spread (TradingView default): 237 %. 2026 export: no trades in the short sample.

Exits: stop 493 / tp 0 / dead 0 / time 193 / blackout 0 / reverse 2.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.75** | 0.5 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **4.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **2.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **20** | 50 |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |

## XAUUSD M15 — `DPFX_XAUUSD_M15_calibrated.set`

**Chart:** XAUUSD, M15 (15-minute bars). **Verdict: RECOMMENDED — rank 3.** Best quality per trade on gold (PF 1.54, 61 % wins, 8 % drawdown) at the price of only ~70 trades a year.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 100-bar volume-delta lookback with a 4.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 3 x ATR(14), 8 R target; trailing stop armed at 2 ATR profit, trailing 0.2 ATR behind; time stop after 100 bars; breakeven at 2 ATR; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2011-2018):** 561 trades (70/yr), PF 1.54, 61 % wins, avg +0.17 R, return 157 % with 8.0 % max drawdown; in-sample t 3.8, out-of-sample t 2.3 (109 trades, +0.17 R). With the broker spread recorded at the time: 81 %; with no spread (TradingView default): 185 %. 2026 export: no trades in the short sample.

Exits: stop 496 / tp 1 / dead 0 / time 10 / blackout 46 / reverse 8.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **3.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **8.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **2.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **100** | 50 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **2.0** | 1.0 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |

## XAUUSD M30 — `DPFX_XAUUSD_M30_calibrated.set`

**Chart:** XAUUSD, M30 (30-minute bars). **Verdict: RECOMMENDED — rank 2.** Profitable in all 8 years and the best out-of-sample t-stat, but the thinnest margin per trade (+0.10 R): keep costs low, do not run it on a wide-spread account.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.5x spike threshold, entry on a close beyond the key zone; EMA(200) trend filter off; stop 1.5 x ATR(14), 10 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 100 bars; breakeven at 0.5 ATR; entries only 02:00-10:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 1940 trades (242/yr), PF 1.22, 59 % wins, avg +0.10 R, return 229 % with 15.3 % max drawdown; in-sample t 3.2, out-of-sample t 2.3 (653 trades, +0.09 R). With the broker spread recorded at the time: 47 %; with no spread (TradingView default): 349 %. 2026 export: 24 trades, -0.03 R.

Exits: stop 1932 / tp 0 / dead 0 / time 0 / blackout 0 / reverse 8.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.5** | 0.5 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **100** | 50 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **0200-1000** | 0800-1200 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **2** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |

## XAUUSD H1 — `DPFX_XAUUSD_M60_calibrated.set`

**Chart:** XAUUSD, H1 (60-minute bars). **Verdict: RECOMMENDED — rank 1.** Most trades of the robust gold sets, 7 of 8 years profitable, loses only a fifth of its edge under double slippage, flat-positive on the 2026 export.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 75-bar volume-delta lookback with a 1.25x spike threshold, entry on a close beyond the key zone; EMA(50) trend filter on; stop 1 x ATR(10), 4.1667 R target; trailing stop armed at 1 ATR profit, trailing 0.5 ATR behind; time stop after 50 bars; dead-trade exit after 10 bars without profit; entries only 18:00-02:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 1084 trades (136/yr), PF 1.32, 44 % wins, avg +0.21 R, return 275 % with 12.2 % max drawdown; in-sample t 4.2, out-of-sample t 1.9 (414 trades, +0.14 R). With the broker spread recorded at the time: 138 %; with no spread (TradingView default): 308 %. 2026 export: 26 trades, +0.03 R.

Exits: stop 966 / tp 75 / dead 0 / time 0 / blackout 0 / reverse 43.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **10** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **4.1667** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **1.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.5** | 0.01 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **10** | 15 |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **1800-0200** | 0800-1200 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **75** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **50** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |

## XAUUSD H4 — `DPFX_XAUUSD_M240_calibrated.set`

**Chart:** XAUUSD, H4 (240-minute bars). **Verdict: USABLE — secondary.** Highest profit factor on gold (1.76) and 7 % drawdown, but only ~30 trades a year, so the statistics are thin.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1.25 x ATR(10), 2 R target; trailing stop armed at 0.5 ATR profit, trailing 1 ATR behind; NY session filter 0930-1600; gold NY-time window filters: robust-hour, V10.5; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 257 trades (32/yr), PF 1.76, 51 % wins, avg +0.32 R, return 125 % with 7.2 % max drawdown; in-sample t 4.3, out-of-sample t 1.4 (103 trades, +0.16 R). With the broker spread recorded at the time: 63 %; with no spread (TradingView default): 126 %. 2026 export: 2 trades, -0.59 R.

Exits: stop 179 / tp 78 / dead 0 / time 0 / blackout 0 / reverse 0.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **10** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.25** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **2.0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **1.0** | 0.01 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **2** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `useSessionFilter` — Use NY cash session filter | **True** | False |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |

## Mirroring a preset on TradingView

The Pine strategy exposes the same inputs under the same names; `Preset Mode` is the dropdown at the top.
Set `Trade Original (Un-Inverted) Signals` first (it changes the whole signal set), then the S2 exit group,
then the filters. TradingView charges no spread by default: set *Properties → Commission* to about
0.003 % per order on gold (≈ $0.06 each side at $4 300) or 0.11 % on bitcoin, or *Slippage* to 60 ticks on
gold, or every result will be overstated — the M1-M30 bitcoin sets will look spectacular there and lose live.
