# Loma EA v1.35: the best trailing system per timeframe (tick replay), start here

`XAUUSD_Loma_TrendPullback.mq5` v1.35 (the same file as in the gold and BTC zips) with one set of presets per timeframe: the trailing system that did best on that timeframe when the re-calibration's setups were replayed tick by tick with the EA's own rules. 6 gold and 6 BTC timeframes have a set. **The file names say Gold or BTC: do not load gold presets on BTC or BTC presets on gold.**

> **Nothing in this zip is proven. Strategy Tester and demo only.**
> - Each timeframe's trailing system was chosen by its result in the unseen months of 2026 (16 May – 13 November). That makes the 2026 figure the score it was chosen by, not a test, and the best of up to 14 systems is flattered by the choice.
> - The check is the earlier data, which played no part in any choice (gold: 15 July – 31 December 2024; BTC: 2023 and 2024): none of the 12 chosen systems held there (profit factor 1.3 or more in every earlier period).
> - On 3 timeframes even the best system lost money in the 2026 months it was chosen on: gold M3 (0.98), gold M15 (0.74), BTC M15 (0.96). They are here only because the zip has one set per timeframe.

## How it was measured

- **The setups** are the re-calibration's picks (November 2026): for every timeframe and trailing system, up to 10 setups chosen on 1 January 2025 – 15 May 2026 only, one per direction, session and trend filter, each with an in-sample score of 1.3 or more. M1 and H1 had no setup that passed, for gold or BTC, so they have no presets.
- **The replay** runs every setup tick by tick with the EA's execution rules: entry on the first tick of the entry minute at the ask (buys) or the bid (sells) after the spread check; stop and target checked on every tick, a stop filled at the tick price (worse on a gap); the trailing systems updated as the EA does (TrailMode 0 and 4 on every tick in steps of `TrailStep_Points`, the others once per closed one-minute bar); the time exits, the Friday close (gold) and one position per preset. It was checked against the EA's own code run on the same ticks in a simulated terminal, on samples of setups covering every TrailMode: 470 of 470 gold trades and 804 of 804 BTC trades identical in entry, stop, target, stop moves, exit and result. An independent re-trace of all 20,087 gold trades of July – December 2024 found the same trades.
- **Gold prices:** Dukascopy ticks. **VT costs:** Dukascopy's mid price with VT Markets' 0.15 spread, scaled by Dukascopy's own spread so its spikes stay, and $0.60 commission per ounce. **Stressed:** one minute late, $0.10 slippage, $0.67 commission.
- **BTC prices:** Binance BTCUSDT one-second prices (the same source as the study's one-minute bars), with a $10 spread and no commission. **Stressed:** one minute late, $3 slippage, $2 commission per BTC.
- **The choice** (written down before the full replay ran, `research/results/tick/best_trailing_rule.md`): on each timeframe, among the EA's trailing systems with at least 100 trades in the 2026 months (at least 30 where none had 100: marked thin), the highest profit factor at VT costs. **Held** = profit factor 1.3 or more in every earlier period.

## Gold (XAUUSD)

| Timeframe | Best trailing (TrailMode) | Presets | Unseen 2026: PF (trades) | Stressed | One-minute engine, same months | Jul 15 - Dec 31 2024: PF (trades) | Held on earlier data | Runner-up (2026 PF) |
|---|---|---|---|---|---|---|---|---|
| M1 | none: no setup passed the calibration | – | – | – | – | – | – | – |
| M2 | stepped (4) | 2 | **1.06 (105)** | 0.98 | 1.02 | 0.76 (70) | no | Bollinger band 0.83 |
| M3 | EMA (7) | 3 | **0.98 (125)** lost | 0.78 | 0.99 | 0.62 (86) | no | higher-timeframe candle 0.97 |
| M5 | hump structure (13) | 4 | **1.27 (141)** | 1.10 | 1.31 | 0.69 (116) | no | chandelier 1.19 |
| M10 | ATR at entry (1) | 4 | **1.57 (203)** | 1.38 | 1.56 | 0.58 (154) | no | percent of price 1.25 |
| M15 | higher-timeframe candle (11) | 5 | **0.74 (246)** lost | 0.67 | 0.76 | 0.99 (280) | no | hump structure 0.69 |
| M30 | swing pivots (12) – thin | 2 | **1.06 (68)** | 1.05 | 1.12 | 0.97 (81) | no | candle lows / highs 0.69 |
| H1 | none: no setup passed the calibration | – | – | – | – | – | – | – |

## BTC (BTCUSD)

| Timeframe | Best trailing (TrailMode) | Presets | Unseen 2026: PF (trades) | Stressed | One-minute engine, same months | 2024: PF (trades) | 2023 (from Jan 15): PF (trades) | Held on earlier data | Runner-up (2026 PF) |
|---|---|---|---|---|---|---|---|---|---|
| M1 | none: no setup passed the calibration | – | – | – | – | – | – | – | – |
| M2 | ATR at entry (1) | 3 | **1.97 (121)** | 1.53 | 2.14 | 1.05 (214) | 0.56 (187) | no | Parabolic SAR 1.37 |
| M3 | candle lows / highs (6) | 3 | **1.41 (140)** | 1.08 | 1.44 | 0.82 (271) | 0.84 (242) | no | – |
| M5 | candle lows / highs (6) | 3 | **1.81 (156)** | 1.61 | 1.89 | 0.97 (306) | 0.90 (320) | no | higher-timeframe candle 1.69 |
| M10 | EMA (7) | 2 | **1.90 (102)** | 2.03 | 1.95 | 1.02 (156) | 0.96 (201) | no | swing pivots 1.49 |
| M15 | Bollinger band (10) | 5 | **0.96 (169)** lost | 0.91 | 0.98 | 1.06 (360) | 0.84 (359) | no | higher-timeframe candle 0.87 |
| M30 | ATR at entry (1) | 3 | **1.06 (100)** | 1.04 | 1.09 | 1.07 (219) | 0.63 (209) | no | percent of price 0.66 |
| H1 | none: no setup passed the calibration | – | – | – | – | – | – | – | – |

- PF = profit factor (gross wins / gross losses). Trades of all the setups of a timeframe's set together.
- *One-minute engine, same months*: the study's one-minute backtest on the same prices and costs, for comparison with the tick replay.
- Every preset's header gives its own figures; `BEST_TRAILING_PRESETS.csv` lists them all, `BEST_TRAILING_BY_TIMEFRAME.csv` the choice of every timeframe with its runner-up, and `TICK_REPLAY_ALL_CELLS.csv` every trailing system on every timeframe, period and cost model, tick and one-minute.

## Ticks against one minute

All the setups of the EA's 14 systems together, VT costs. The tick replay takes almost the same trades as the one-minute engine on the same prices and costs, and its profit factor is 0.00 to 0.05 lower: the one-minute figures of the study were close, slightly optimistic.

| Symbol | Period | Tick replay: trades, PF, net | One-minute engine: trades, PF, net |
|---|---|---|---|
| XAUUSD | May 16 - Nov 13 2026 | 11225, 0.81, -972R | 11222, 0.82, -915R |
| XAUUSD | Jan 2025 - May 15 2026 (the setups were picked on it) | 23290, 1.49, +4085R | 23287, 1.51, +4176R |
| XAUUSD | Jul 15 - Dec 31 2024 | 8184, 0.78, -870R | 8189, 0.78, -846R |
| BTCUSD | May 16 - Nov 13 2026 | 6091, 1.11, +225R | 6091, 1.14, +276R |
| BTCUSD | Jan 2025 - May 15 2026 (the setups were picked on it) | 16627, 1.65, +3110R | 16627, 1.69, +3215R |
| BTCUSD | 2024 | 12990, 0.98, -97R | 12990, 1.00, +8R |
| BTCUSD | 2023 (from Jan 15) | 12577, 0.73, -1332R | 12576, 0.75, -1180R |

## The 15 earlier trailing results, tick by tick

The combinations of timeframe and trailing system that had reached a profit factor of 1.3 on the 2026 months in the one-minute backtest (the `Loma_T15` presets of the gold and BTC zips), re-measured here. The one-minute figures were at the study's costs (gold: FTMO spread, no commission; BTC: $10 spread); the tick figures are at VT costs.

| Symbol | Timeframe | Trailing | 2026 one-minute (study): PF (trades) | 2026 tick, VT costs: PF (trades) | Stressed | Earlier data, tick: PF (trades) |
|---|---|---|---|---|---|---|
| XAUUSD | M5 | hump structure | 1.41 (141) | 1.27 (141) | 1.10 | Jul 15 - Dec 31 2024: 0.69 (116) |
| XAUUSD | M5 | chandelier | 1.31 (157) | 1.19 (157) | 1.10 | Jul 15 - Dec 31 2024: 0.66 (111) |
| XAUUSD | M10 | percent of price | 1.31 (181) | 1.25 (182) | 1.13 | Jul 15 - Dec 31 2024: 0.66 (137) |
| XAUUSD | M10 | ATR at entry | 1.57 (206) | 1.57 (203) | 1.38 | Jul 15 - Dec 31 2024: 0.58 (154) |
| BTCUSD | M2 | Parabolic SAR | 1.48 (109) | 1.37 (109) | 1.19 | 2024: 0.74 (227); 2023 (from Jan 15): 0.67 (204) |
| BTCUSD | M2 | ATR at entry | 2.14 (121) | 1.97 (121) | 1.53 | 2024: 1.05 (214); 2023 (from Jan 15): 0.56 (187) |
| BTCUSD | M3 | candle lows / highs | 1.44 (140) | 1.41 (140) | 1.08 | 2024: 0.82 (271); 2023 (from Jan 15): 0.84 (242) |
| BTCUSD | M5 | candle lows / highs | 1.89 (156) | 1.81 (156) | 1.61 | 2024: 0.97 (306); 2023 (from Jan 15): 0.90 (320) |
| BTCUSD | M5 | SMA | 1.51 (205) | 1.44 (205) | 1.37 | 2024: 1.07 (462); 2023 (from Jan 15): 0.70 (425) |
| BTCUSD | M5 | profit lock | 1.35 (214) | 1.28 (214) | 1.08 | 2024: 0.72 (400); 2023 (from Jan 15): 0.70 (397) |
| BTCUSD | M5 | Bollinger band | 1.37 (112) | 1.33 (112) | 1.22 | 2024: 0.74 (267); 2023 (from Jan 15): 0.63 (250) |
| BTCUSD | M5 | higher-timeframe candle | 1.71 (166) | 1.69 (166) | 1.49 | 2024: 1.12 (321); 2023 (from Jan 15): 0.70 (337) |
| BTCUSD | M10 | EMA | 1.95 (102) | 1.90 (102) | 2.03 | 2024: 1.02 (156); 2023 (from Jan 15): 0.96 (201) |
| BTCUSD | M10 | stepped | 1.36 (161) | 1.32 (161) | 1.24 | 2024: 1.10 (310); 2023 (from Jan 15): 0.77 (291) |
| BTCUSD | M10 | swing pivots | 1.56 (129) | 1.49 (129) | 1.48 | 2024: 1.08 (283); 2023 (from Jan 15): 0.72 (269) |

## How to run the presets

- **One timeframe's set is one result:** its setups were tested together. Run them together on one **hedging** account (on a netting account the presets on one symbol share one position).
- **Overlap:** in the replay the most positions open at once were XAUUSD M2: 2, XAUUSD M3: 3, XAUUSD M5: 4, XAUUSD M10: 4, XAUUSD M15: 5, XAUUSD M30: 2, BTCUSD M2: 3, BTCUSD M3: 2, BTCUSD M5: 3, BTCUSD M10: 2, BTCUSD M15: 4, BTCUSD M30: 3; all gold sets together 10, all BTC sets together 8. Each preset has `RiskPercent=0.5`: lower it (for example to 0.1) if you run several sets at once.
- **Gold commission:** the figures include $0.60 per ounce. Set `CommissionPerLot` to your round-trip commission per lot in the account currency, so a stop-out costs `RiskPercent` including commission.
- **BTC:** points are 0.01 USD (`AutoScalePoints=true`); `MaxSpread_Points=3000` ($30), `TrailStep_Points=200` ($2), no weekend close. BTC stops are wide (hundreds of dollars): with a 0.01 minimum lot a trade is skipped when the equity is too small for its stop (`SkipIfBelowMinLot=true`); test with a large deposit first.
- **Server time:** sessions and the end-of-day close are broker server time (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer), the clock of VT Markets and FTMO.
- **News filter** is on in the presets but was not in the replay; it does nothing in the Strategy Tester.

## If you want to test it

1. **Strategy Tester:** "Every tick based on real ticks" on your broker's symbol, one timeframe's set at a time, over 16 May – 13 November 2026 and over the earlier period, and compare with the tables above. In the tester the Load dialog usually opens in `MQL5\Profiles\Tester`; browse to `MQL5\Presets`.
2. **Then demo.** A tester run that matches shows that the EA trades its backtest, not that the edge is real.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35. |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_BT_Gold_*.set` | 20 gold presets: every setup of each gold timeframe's best system. |
| `MQL5/Presets/Loma_BT_BTC_*.set` | 19 BTC presets: every setup of each BTC timeframe's best system. |
| `BEST_TRAILING_BY_TIMEFRAME.csv` | The choice of every timeframe, with its runner-up and the earlier-data check. |
| `BEST_TRAILING_PRESETS.csv` | Every preset with its figures. |
| `TICK_REPLAY_ALL_CELLS.csv` | Every trailing system on every timeframe: each period and cost model, tick replay and one-minute engine. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile). It has not been compiled in MetaEditor yet: if the compiler reports anything, send the log rather than editing the file.
4. Attach the EA to an XAUUSD or BTCUSD chart (any timeframe: it reads its own from the preset). In **Inputs** click **Load** and pick a preset of that symbol.
5. Enable **Algo Trading**.
