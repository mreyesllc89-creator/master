# Calibrated presets, one per timeframe

Load the `.set` file into MT5 Strategy Tester (Inputs → Load), on the chart timeframe named in the
section, on a USD account, and give each independent run its own `RecoverySession`. The strategy's
sizing (`Risk % = 1.0`, margin cap) and all inputs not listed are the shipped values. Statistics are
from the Python replica described in `../REPORT.md`, with today's spread ($0.12 gold, 2.2 bp bitcoin),
1 % risk per trade and a $10 000 start; 'OOS' = 2016-2018 (gold) / 2018-2019 (bitcoin), '2026' = your
July-August 2026 Octa export. Verdicts: RECOMMENDED > USABLE > PAPER-TRADE > NOT RECOMMENDED > DO NOT TRADE.

| Preset | Chart | Verdict | Trades/yr | PF | Win % | Return | Max DD | OOS t | 2026 |
|---|---|---|---|---|---|---|---|---|---|
| `DPFX_BTCUSD_M1_calibrated.set` | BTCUSD M1 | DO NOT TRADE | 27540 | 1.24 | 43 | 94,243 % | 83.4 % | 12.9 | 4409 tr, -0.23 R |
| `DPFX_BTCUSD_M2_calibrated.set` | BTCUSD M2 | DO NOT TRADE | 22843 | 1.24 | 43 | 63,097 % | 97.8 % | 21.0 | 4045 tr, -0.18 R |
| `DPFX_BTCUSD_M3_calibrated.set` | BTCUSD M3 | DO NOT TRADE | 3416 | 0.92 | 24 | -100 % | 100.0 % | 0.4 | 2687 tr, -0.38 R |
| `DPFX_BTCUSD_M5_calibrated.set` | BTCUSD M5 | DO NOT TRADE | 19370 | 1.18 | 31 | 40,763 % | 88.1 % | 12.8 | 2466 tr, -0.41 R |
| `DPFX_BTCUSD_M10_calibrated.set` | BTCUSD M10 | DO NOT TRADE | 9627 | 1.31 | 29 | 35,159 % | 6.0 % | 8.4 | 1767 tr, -0.31 R |
| `DPFX_BTCUSD_M15_calibrated.set` | BTCUSD M15 | DO NOT TRADE | 10508 | 1.20 | 32 | 28,857 % | 11.6 % | 9.4 | 1792 tr, -0.19 R |
| `DPFX_BTCUSD_M30_calibrated.set` | BTCUSD M30 | DO NOT TRADE | 5640 | 1.15 | 27 | 16,858 % | 14.6 % | 3.4 | 1037 tr, -0.15 R |
| `DPFX_BTCUSD_M60_calibrated.set` | BTCUSD H1 | PAPER-TRADE FIRST | 236 | 1.38 | 42 | 1,199 % | 20.8 % | 2.4 | 37 tr, -0.16 R |
| `DPFX_BTCUSD_M240_calibrated.set` | BTCUSD H4 | RECOMMENDED — rank 4 | 221 | 1.61 | 39 | 585 % | 8.1 % | 2.7 | 37 tr, +0.12 R |
| `DPFX_XAUUSD_M1_calibrated.set` | XAUUSD M1 | NOT RECOMMENDED | 287 | 1.25 | 24 | 307 % | 13.8 % | 2.5 | 1038 tr, +0.11 R |
| `DPFX_XAUUSD_M2_calibrated.set` | XAUUSD M2 | NOT RECOMMENDED | 154 | 1.42 | 26 | 260 % | 10.8 % | 1.0 | 1043 tr, -0.00 R |
| `DPFX_XAUUSD_M3_calibrated.set` | XAUUSD M3 | NOT RECOMMENDED | 663 | 1.10 | 32 | 429 % | 37.3 % | 1.1 | 631 tr, -0.08 R |
| `DPFX_XAUUSD_M5_calibrated.set` | XAUUSD M5 | USABLE — secondary | 70 | 1.56 | 34 | 224 % | 9.8 % | 1.7 | no trades |
| `DPFX_XAUUSD_M10_calibrated.set` | XAUUSD M10 | USABLE — secondary | 86 | 1.47 | 29 | 207 % | 16.1 % | 1.3 | no trades |
| `DPFX_XAUUSD_M15_calibrated.set` | XAUUSD M15 | RECOMMENDED — rank 3 | 70 | 1.54 | 61 | 158 % | 7.8 % | 2.1 | no trades |
| `DPFX_XAUUSD_M30_calibrated.set` | XAUUSD M30 | RECOMMENDED — rank 2 | 243 | 1.21 | 59 | 227 % | 15.1 % | 2.3 | 24 tr, -0.03 R |
| `DPFX_XAUUSD_M60_calibrated.set` | XAUUSD H1 | RECOMMENDED — rank 1 | 136 | 1.30 | 44 | 259 % | 13.7 % | 1.7 | 26 tr, +0.04 R |
| `DPFX_XAUUSD_M240_calibrated.set` | XAUUSD H4 | USABLE — secondary | 32 | 1.69 | 50 | 111 % | 8.3 % | 1.1 | 2 tr, -0.60 R |

## BTCUSD M1 — `DPFX_BTCUSD_M1_calibrated.set`

**Chart:** BTCUSD, M1 (1-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 20-bar volume-delta lookback with a 1.25x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 2 x ATR(50), no fixed target; trailing stop armed at 0.5 ATR profit, trailing 1 ATR behind; time stop after 100 bars; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 137700 trades (27540/yr), PF 1.24, 43 % wins, avg +0.08 R, return 94,243 % with 83.4 % max drawdown; in-sample t 12.5, out-of-sample t 12.9 (68387 trades, +0.09 R). With the broker spread recorded at the time: -100 %; with no spread (TradingView default): 179,593 %. 2026 export: 4409 trades, -0.23 R.

Exits: stop 111592 / tp 0 / dead 0 / time 2 / blackout 0 / reverse 26106.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **2.0** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **1.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **100** | 50 |
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **20** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **20** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## BTCUSD M2 — `DPFX_BTCUSD_M2_calibrated.set`

**Chart:** BTCUSD, M2 (2-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 1 x ATR(50), 10 R target; trailing stop armed at 0.5 ATR profit, trailing 0.5 ATR behind; dead-trade exit after 10 bars without profit; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2015-2019):** 114213 trades (22843/yr), PF 1.24, 43 % wins, avg +0.09 R, return 63,097 % with 97.8 % max drawdown; in-sample t 2.5, out-of-sample t 21.0 (58274 trades, +0.16 R). With the broker spread recorded at the time: -100 %; with no spread (TradingView default): 122,426 %. 2026 export: 4045 trades, -0.18 R.

Exits: stop 102424 / tp 1015 / dead 0 / time 0 / blackout 218 / reverse 10556.

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
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **10** | 15 |
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## BTCUSD M3 — `DPFX_BTCUSD_M3_calibrated.set`

**Chart:** BTCUSD, M3 (3-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter on; stop 0.75 x ATR(50), 15 R target; trailing stop armed at 1 ATR profit, trailing 0.5 ATR behind; dead-trade exit after 5 bars without profit; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 17081 trades (3416/yr), PF 0.92, 24 % wins, avg -0.14 R, return -100 % with 100.0 % max drawdown; in-sample t -8.4, out-of-sample t 0.4 (5 trades, +0.46 R). With the broker spread recorded at the time: -100 %; with no spread (TradingView default): 82,496 %. 2026 export: 2687 trades, -0.38 R.

Exits: stop 15888 / tp 81 / dead 0 / time 0 / blackout 0 / reverse 1112.

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
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **5** | 15 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## BTCUSD M5 — `DPFX_BTCUSD_M5_calibrated.set`

**Chart:** BTCUSD, M5 (5-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 1.0x spike threshold, entry on a retest touch; EMA(20) trend filter off; stop 0.5 x ATR(30), no fixed target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 50 bars; dead-trade exit after 10 bars without profit; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 96849 trades (19370/yr), PF 1.18, 31 % wins, avg +0.09 R, return 40,763 % with 88.1 % max drawdown; in-sample t 1.8, out-of-sample t 12.8 (44688 trades, +0.17 R). With the broker spread recorded at the time: -100 %; with no spread (TradingView default): 92,226 %. 2026 export: 2466 trades, -0.41 R.

Exits: stop 89224 / tp 0 / dead 0 / time 0 / blackout 4 / reverse 7621.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **0.5** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **0.2** | 0.01 |
| V2 optimisations (Manual mode only) | `deadBarsIn` — Dead trade bars | **10** | 15 |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `manualLossClusterCount` — Losses before pause | **3** | 5 |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |

## BTCUSD M10 — `DPFX_BTCUSD_M10_calibrated.set`

**Chart:** BTCUSD, M10 (10-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 100-bar volume-delta lookback with a 1.0x spike threshold, entry on a retest touch; EMA(20) trend filter on; stop 0.3 x ATR(30), 6 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 50 bars; dead-trade exit after 15 bars without profit; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 48133 trades (9627/yr), PF 1.31, 29 % wins, avg +0.20 R, return 35,159 % with 6.0 % max drawdown; in-sample t 18.0, out-of-sample t 8.4 (21327 trades, +0.12 R). With the broker spread recorded at the time: 30,302 %; with no spread (TradingView default): 55,894 %. 2026 export: 1767 trades, -0.31 R.

Exits: stop 43070 / tp 3366 / dead 0 / time 0 / blackout 6 / reverse 1691.

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
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **5** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |

## BTCUSD M15 — `DPFX_BTCUSD_M15_calibrated.set`

**Chart:** BTCUSD, M15 (15-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 100-bar volume-delta lookback with a 1.25x spike threshold, entry on a retest touch; EMA(50) trend filter off; stop 0.3 x ATR(50), 15 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 200 bars; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2015-2019):** 52539 trades (10508/yr), PF 1.20, 32 % wins, avg +0.16 R, return 28,857 % with 11.6 % max drawdown; in-sample t 14.0, out-of-sample t 9.4 (23272 trades, +0.13 R). With the broker spread recorded at the time: 23,999 %; with no spread (TradingView default): 50,142 %. 2026 export: 1792 trades, -0.19 R.

Exits: stop 42881 / tp 216 / dead 0 / time 0 / blackout 44 / reverse 9398.

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
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |

## BTCUSD M30 — `DPFX_BTCUSD_M30_calibrated.set`

**Chart:** BTCUSD, M30 (30-minute bars). **Verdict: DO NOT TRADE.** Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.

**Character:** inverted signals (as shipped); Manual profile; zones from a 30-bar volume-delta lookback with a 1.25x spike threshold, entry on a retest touch; EMA(20) trend filter off; stop 0.3 x ATR(50), 6 R target; time stop after 10 bars; breakeven at 0.5 ATR; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 28202 trades (5640/yr), PF 1.15, 27 % wins, avg +0.13 R, return 16,858 % with 14.6 % max drawdown; in-sample t 10.9, out-of-sample t 3.4 (12405 trades, +0.06 R). With the broker spread recorded at the time: 13,896 %; with no spread (TradingView default): 28,521 %. 2026 export: 1037 trades, -0.15 R.

Exits: stop 20270 / tp 1935 / dead 0 / time 74 / blackout 0 / reverse 5923.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| S2. Exits | `atrLenS2` — ATR length | **50** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.3** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **6.0** | 10 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **10** | 50 |
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## BTCUSD H1 — `DPFX_BTCUSD_M60_calibrated.set`

**Chart:** BTCUSD, H1 (60-minute bars). **Verdict: PAPER-TRADE FIRST.** Good 2015-2019 history (PF 1.43, every year profitable) but slightly negative on the 37 trades of the 2026 export.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 2 x ATR(7), 6 R target; time stop after 20 bars; NY session filter 0200-1700; gold NY-time window filters: directional; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2015-2019):** 1179 trades (236/yr), PF 1.38, 42 % wins, avg +0.24 R, return 1,199 % with 20.8 % max drawdown; in-sample t 4.5, out-of-sample t 2.4 (486 trades, +0.17 R). With the broker spread recorded at the time: 1,159 %; with no spread (TradingView default): 1,388 %. 2026 export: 37 trades, -0.16 R.

Exits: stop 463 / tp 35 / dead 0 / time 581 / blackout 0 / reverse 99.

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
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## BTCUSD H4 — `DPFX_BTCUSD_M240_calibrated.set`

**Chart:** BTCUSD, H4 (240-minute bars). **Verdict: RECOMMENDED — rank 4.** The only bitcoin set that survives every test: profitable every year, cost-insensitive, positive on the 2026 export.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 2 x ATR(7), 2 R target; trailing stop armed at 0.5 ATR profit, trailing 2 ATR behind; time stop after 20 bars; breakeven at 1 ATR; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2015-2019):** 1103 trades (221/yr), PF 1.61, 39 % wins, avg +0.18 R, return 585 % with 8.1 % max drawdown; in-sample t 5.2, out-of-sample t 2.7 (493 trades, +0.10 R). With the broker spread recorded at the time: 594 %; with no spread (TradingView default): 636 %. 2026 export: 37 trades, +0.12 R.

Exits: stop 222 / tp 150 / dead 0 / time 7 / blackout 215 / reverse 508.

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
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.0** | 1.5 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD M1 — `DPFX_XAUUSD_M1_calibrated.set`

**Chart:** XAUUSD, M1 (1-minute bars). **Verdict: NOT RECOMMENDED.** Edge halves with $0.05 extra slippage per fill; too cost-sensitive for live use.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1 x ATR(30), 15 R target; trailing stop armed at 3 ATR profit, trailing 0.5 ATR behind; gold NY-time window filters: all off; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2011-2018):** 2298 trades (287/yr), PF 1.25, 24 % wins, avg +0.19 R, return 307 % with 13.8 % max drawdown; in-sample t 3.4, out-of-sample t 2.5 (191 trades, +0.39 R). With the broker spread recorded at the time: -96 %; with no spread (TradingView default): 447 %. 2026 export: 1038 trades, +0.11 R.

Exits: stop 2266 / tp 3 / dead 0 / time 0 / blackout 0 / reverse 29.

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
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **5** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **100** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD M2 — `DPFX_XAUUSD_M2_calibrated.set`

**Chart:** XAUUSD, M2 (2-minute bars). **Verdict: NOT RECOMMENDED.** Cost-sensitive and flat on the 2026 export (1 045 trades).

**Character:** inverted signals (as shipped); XAUUSD 5m auto profile; EMA(100) trend filter off; stop 0.5 x ATR(30), 10 R target; gold NY-time window filters: all off; weekend blackout off, daily 16:55-18:00 blackout on.

**History (2011-2018):** 1232 trades (154/yr), PF 1.42, 26 % wins, avg +0.31 R, return 260 % with 10.8 % max drawdown; in-sample t 4.0, out-of-sample t 1.0 (102 trades, +0.25 R). With the broker spread recorded at the time: 26 %; with no spread (TradingView default): 352 %. 2026 export: 1043 trades, -0.00 R.

Exits: stop 904 / tp 36 / dead 0 / time 0 / blackout 7 / reverse 285.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| S2. Exits | `atrLenS2` — ATR length | **30** | 14 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **6.0** | 4.0 |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |

## XAUUSD M3 — `DPFX_XAUUSD_M3_calibrated.set`

**Chart:** XAUUSD, M3 (3-minute bars). **Verdict: NOT RECOMMENDED.** Weakest gold set (PF 1.09, 37 % drawdown), negative on the 2026 export.

**Character:** inverted signals (as shipped); XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1.25 x ATR(7), 15 R target; gold NY-time window filters: robust-hour, V10.10; weekend blackout on, daily 16:55-18:00 blackout on.

**History (2011-2018):** 5302 trades (663/yr), PF 1.10, 32 % wins, avg +0.08 R, return 429 % with 37.3 % max drawdown; in-sample t 2.9, out-of-sample t 1.1 (717 trades, +0.08 R). With the broker spread recorded at the time: -95 %; with no spread (TradingView default): 724 %. 2026 export: 631 trades, -0.08 R.

Exits: stop 3589 / tp 4 / dead 0 / time 0 / blackout 508 / reverse 1201.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **1.25** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **15.0** | 10 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |

## XAUUSD M5 — `DPFX_XAUUSD_M5_calibrated.set`

**Chart:** XAUUSD, M5 (5-minute bars). **Verdict: USABLE — secondary.** Strong R per trade (+0.42) and 1.55 PF, but ~70 trades a year and an out-of-sample t-stat of only 1.8; no 2026 trades in the 28-day sample.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 4.0x spike threshold, entry on a retest touch; EMA(100) trend filter off; stop 1.5 x ATR(14), 8 R target; trailing stop armed at 4 ATR profit, trailing 2 ATR behind; time stop after 200 bars; entries only 08:00-17:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 563 trades (70/yr), PF 1.56, 34 % wins, avg +0.42 R, return 224 % with 9.8 % max drawdown; in-sample t 3.8, out-of-sample t 1.7 (130 trades, +0.34 R). With the broker spread recorded at the time: 106 %; with no spread (TradingView default): 251 %. 2026 export: no trades in the short sample.

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
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **0800-1700** | 0800-1200 |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `cooldownIn` — Cooldown bars | **5** | 10 |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **25** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD M10 — `DPFX_XAUUSD_M10_calibrated.set`

**Chart:** XAUUSD, M10 (10-minute bars). **Verdict: USABLE — secondary.** Similar profile to M5; 2 losing years out of 8 and OOS t-stat 1.1.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 150-bar volume-delta lookback with a 4.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter on; stop 0.75 x ATR(7), no fixed target; trailing stop armed at 4 ATR profit, trailing 2 ATR behind; time stop after 20 bars; entries only 08:00-12:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 690 trades (86/yr), PF 1.47, 29 % wins, avg +0.43 R, return 207 % with 16.1 % max drawdown; in-sample t 3.3, out-of-sample t 1.3 (115 trades, +0.43 R). With the broker spread recorded at the time: 100 %; with no spread (TradingView default): 239 %. 2026 export: no trades in the short sample.

Exits: stop 494 / tp 0 / dead 0 / time 194 / blackout 0 / reverse 2.

**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):

| Group | Input | Value | Shipped |
|---|---|---|---|
| Preset / direction | `presetMode` — Preset Mode | **Manual** | XAUUSD 5m |
| Preset / direction | `tradeOriginalDirection` — Trade Original (Un-Inverted) Signals | **True** | False |
| S2. Exits | `atrLenS2` — ATR length | **7** | 14 |
| S2. Exits | `slAtrMultS2` — Stop loss, ATR mult | **0.75** | 0.5 |
| S2. Exits | `tpRS2` — Take profit, R multiple of SL (0 = off) | **0** | 10 |
| S2. Exits | `useTrailS2` — Trailing stop | **True** | False |
| S2. Exits | `trailActAtr` — Trail activation, ATR mult | **4.0** | 0.01 |
| S2. Exits | `trailDstAtr` — Trail distance, ATR mult | **2.0** | 0.01 |
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **20** | 50 |
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **150** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **20** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD M15 — `DPFX_XAUUSD_M15_calibrated.set`

**Chart:** XAUUSD, M15 (15-minute bars). **Verdict: RECOMMENDED — rank 3.** Best quality per trade on gold (PF 1.54, 61 % wins, 8 % drawdown) at the price of only ~70 trades a year.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 100-bar volume-delta lookback with a 4.0x spike threshold, entry on a close beyond the key zone; EMA(20) trend filter off; stop 3 x ATR(14), 8 R target; trailing stop armed at 2 ATR profit, trailing 0.2 ATR behind; time stop after 100 bars; breakeven at 2 ATR; weekend blackout on, daily 16:55-18:00 blackout off.

**History (2011-2018):** 561 trades (70/yr), PF 1.54, 61 % wins, avg +0.17 R, return 158 % with 7.8 % max drawdown; in-sample t 3.8, out-of-sample t 2.1 (109 trades, +0.16 R). With the broker spread recorded at the time: 75 %; with no spread (TradingView default): 177 %. 2026 export: no trades in the short sample.

Exits: stop 495 / tp 1 / dead 0 / time 11 / blackout 46 / reverse 8.

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
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **2.0** | 1.0 |
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **100** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **4.0** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **2.0** | 4.0 |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD M30 — `DPFX_XAUUSD_M30_calibrated.set`

**Chart:** XAUUSD, M30 (30-minute bars). **Verdict: RECOMMENDED — rank 2.** Profitable in all 8 years and the best out-of-sample t-stat, but the thinnest margin per trade (+0.10 R): keep costs low, do not run it on a wide-spread account.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 30-bar volume-delta lookback with a 1.5x spike threshold, entry on a close beyond the key zone; EMA(200) trend filter off; stop 1.5 x ATR(14), 10 R target; trailing stop armed at 0.5 ATR profit, trailing 0.2 ATR behind; time stop after 100 bars; breakeven at 0.5 ATR; entries only 02:00-10:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 1944 trades (243/yr), PF 1.21, 59 % wins, avg +0.09 R, return 227 % with 15.1 % max drawdown; in-sample t 3.1, out-of-sample t 2.3 (652 trades, +0.09 R). With the broker spread recorded at the time: 50 %; with no spread (TradingView default): 361 %. 2026 export: 24 trades, -0.03 R.

Exits: stop 1937 / tp 0 / dead 0 / time 0 / blackout 0 / reverse 7.

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
| V2 optimisations (Manual mode only) | `useDeadExit` — (2) Scratch trades not in profit after N bars | **False** | True |
| V2 optimisations (Manual mode only) | `useBreakeven` — (4) Move stop to breakeven | **True** | False |
| V2 optimisations (Manual mode only) | `beTriggerAtr` — Breakeven trigger (ATR) | **0.5** | 1.0 |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **0200-1000** | 0800-1200 |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **30** | 50 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **2** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualZoneTrend` — Only create zones with EMA trend | **True** | False |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `manualLossClusterPauseBars` — Pause bars | **6** | 12 |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD H1 — `DPFX_XAUUSD_M60_calibrated.set`

**Chart:** XAUUSD, H1 (60-minute bars). **Verdict: RECOMMENDED — rank 1.** Most trades of the robust gold sets, 7 of 8 years profitable, loses only a fifth of its edge under double slippage, flat-positive on the 2026 export.

**Character:** un-inverted (original) signal direction; Manual profile; zones from a 75-bar volume-delta lookback with a 1.25x spike threshold, entry on a close beyond the key zone; EMA(50) trend filter on; stop 1 x ATR(10), 4.1667 R target; trailing stop armed at 1 ATR profit, trailing 0.5 ATR behind; time stop after 50 bars; dead-trade exit after 10 bars without profit; entries only 18:00-02:00 NY; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 1091 trades (136/yr), PF 1.30, 44 % wins, avg +0.19 R, return 259 % with 13.7 % max drawdown; in-sample t 3.9, out-of-sample t 1.7 (418 trades, +0.12 R). With the broker spread recorded at the time: 120 %; with no spread (TradingView default): 301 %. 2026 export: 26 trades, +0.04 R.

Exits: stop 967 / tp 75 / dead 0 / time 0 / blackout 0 / reverse 49.

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
| V2 optimisations (Manual mode only) | `useEntryBuffer` — (5) Block entries before blackout window | **False** | True |
| V2 optimisations (Manual mode only) | `useSundayBlock` — (6) Block all Sunday entries (NY) | **False** | True |
| V2 optimisations (Manual mode only) | `useEntryWindow` — (7) Use entry time window | **True** | False |
| V2 optimisations (Manual mode only) | `entryWindowIn` — Entry window (NY time) | **1800-0200** | 0800-1200 |
| V2 optimisations (Manual mode only) | `useOnePerZone` — (8) One entry per zone | **False** | True |
| V2 optimisations (Manual mode only) | `useCooldown` — (9) Re-entry cooldown after dead/time exit | **False** | True |
| Supply / demand zones | `manualZoneLength` — Zone lookback length | **75** | 50 |
| Supply / demand zones | `manualDeltaThreshold` — Volume delta spike multiplier | **1.25** | 1.5 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **400** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Supply / demand zones | `manualEmaLength` — EMA length | **50** | 100 |
| Supply / demand zones | `manualEntryMode` — Entry mode | **Close Beyond Key Zone** | Normal Retest Touch |
| Session & quality filters | `useRobustHourFilter` — Block robustly losing NY hours | **False** | True |
| Session & quality filters | `useV105DirectionalFilter` — Block V10.5 directional windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `useV1013VolCostFilter` — Block entries when ATR stop is too small vs costs | **False** | True |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## XAUUSD H4 — `DPFX_XAUUSD_M240_calibrated.set`

**Chart:** XAUUSD, H4 (240-minute bars). **Verdict: USABLE — secondary.** Highest profit factor on gold (1.76) and 7 % drawdown, but only ~30 trades a year, so the statistics are thin.

**Character:** un-inverted (original) signal direction; XAUUSD 5m auto profile; EMA(100) trend filter on; stop 1.25 x ATR(10), 2 R target; trailing stop armed at 0.5 ATR profit, trailing 1 ATR behind; NY session filter 0930-1600; gold NY-time window filters: robust-hour, V10.5; weekend blackout off, daily 16:55-18:00 blackout off.

**History (2011-2018):** 257 trades (32/yr), PF 1.69, 50 % wins, avg +0.30 R, return 111 % with 8.3 % max drawdown; in-sample t 4.1, out-of-sample t 1.1 (103 trades, +0.13 R). With the broker spread recorded at the time: 52 %; with no spread (TradingView default): 123 %. 2026 export: 2 trades, -0.60 R.

Exits: stop 181 / tp 76 / dead 0 / time 0 / blackout 0 / reverse 0.

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
| S2. Exits | `timeStopBars` — Time stop, bars (0 = off) | **0** | 50 |
| Supply / demand zones | `manualMinRetestBars` — Minimum bars before retest | **2** | 1 |
| Supply / demand zones | `manualMaxZoneAge` — Max zone age in bars | **50** | 200 |
| Supply / demand zones | `manualInvalidate` — Invalidate broken zones | **False** | True |
| Supply / demand zones | `manualUseEmaFilter` — Use EMA trend filter | **True** | False |
| Session & quality filters | `useSessionFilter` — Use NY cash session filter | **True** | False |
| Session & quality filters | `useDirectionalMicroFilter` — Block directional 15-min windows | **False** | True |
| Session & quality filters | `useV1010PfFilter` — Block V10.10 profit-factor windows | **False** | True |
| Session & quality filters | `useV1011LossClusterPause` — Pause entries after consecutive loss cluster | **False** | True |
| Session & quality filters | `minStopToCostRatio` — Minimum stop distance / round-trip cost | **10.0** | 4.0 |
| Session & quality filters | `useWeekendBlackout` — Weekend close/block | **False** | True |
| Session & quality filters | `useDailyBlackout` — Daily intraday hold filter (Mon-Thu 16:55-18:00 NY) | **False** | True |

## Mirroring a preset on TradingView

The Pine strategy exposes the same inputs under the same names; `Preset Mode` is the dropdown at the top.
Set `Trade Original (Un-Inverted) Signals` first (it changes the whole signal set), then the S2 exit group,
then the filters. TradingView charges no spread by default: set *Properties → Commission* to about
0.003 % per order on gold (≈ $0.06 each side at $4 300) or 0.11 % on bitcoin, or *Slippage* to 60 ticks on
gold, or every result will be overstated — the M1-M30 bitcoin sets will look spectacular there and lose live.
