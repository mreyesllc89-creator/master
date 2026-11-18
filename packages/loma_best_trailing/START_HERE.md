# Loma EA v1.35: the best trailing system per timeframe (tick replay), start here

`XAUUSD_Loma_TrendPullback.mq5` v1.35 (the same file as in the gold and BTC zips) with one set of presets per timeframe. On each timeframe the set is the trailing system whose own setups made the highest profit factor in the 2026 months, among those with at least 100 trades there (at least 30 where none had 100), when the re-calibration's setups were replayed with the EA's own rules on every tick (gold) or every second (BTC). Each trailing system was calibrated with its own setups (no two share one), so this compares setups and trailing together, not trailing systems on the same trades. 6 gold and 6 BTC timeframes have a set (39 presets). **The file names say Gold or BTC: do not load gold presets on BTC or BTC presets on gold.**

> **Nothing in this zip is proven. Strategy Tester and demo only.**
> - Each timeframe's set was chosen by its result in the 2026 months (16 May – 13 Nov), which its setups had not seen. That makes the 2026 figure the score it was chosen by, not a test, and the best of up to 14 systems is flattered by the choice.
> - The check is the earlier data, which played no part in any choice (gold: 15 Jul – 31 Dec 2024; BTC: 2023 and 2024): none of the 12 chosen sets held there (held = profit factor 1.3 or more in every earlier period). Every gold set lost money from 15 Jul to 31 Dec 2024 (0.58 to 0.99). Every BTC set lost money in 2023 (0.56 to 0.96); in 2024 the BTC sets made 0.82 to 1.07.
> - On 3 timeframes even the best set lost money in the 2026 months it was chosen on: gold M3 (0.98), gold M15 (0.74), BTC M15 (0.96). They are here only because the zip has one set per timeframe.
> - On some sets the trailing rarely decides a trade: in the 2026 months it decided 1 of gold M2's 105 trades and 9 of BTC M15's 169 trades. Their results come mostly from the entries, the stop, the target and the time exits.
> - 6 of the 12 sets (19 presets: BTC M2, BTC M3, BTC M5, BTC M10, gold M5, gold M10) are the same setups as `Loma_T15` presets of the gold and BTC zips, with other magic numbers. Load one or the other, not both, or every trade is taken twice.
> - The gold figures assume VT's narrow spread (about $0.15) and $0.60 commission per ounce. At Dukascopy's own wider spreads only 60% of the gold sets' 2026 trades were taken and their profit factors moved (column *At Dukascopy's own spreads*).
> - The EA v1.35 has not been compiled or run in MetaTrader yet: its trailing systems were checked only in a simulated terminal (see *Checks of the replay*). If the compiler reports anything, send the log.

## How it was measured

- **The setups** are the re-calibration's picks (November 2026): for every timeframe and trailing system, up to 10 setups chosen on 1 Jan 2025 – 15 May 2026 only, one per direction, session and trend filter, each with a score of 1.3 or more (score = its lowest profit factor in three parts of those months, Jan – Jun 2025, Jul – Dec 2025 and Jan – 15 May 2026, at normal and at stressed costs, with at least 20 trades in each part). No setup of the EA's 14 trailing systems passed on M1 or H1, for gold or BTC, so they have no presets.
- **The replay** runs every setup with the EA's execution rules: entry on the first price of the entry minute at the ask (buys) or the bid (sells) after the spread check; stop and target checked on every price, a stop filled at that price (worse on a gap); the trailing systems updated as the EA does (TrailMode 0 and 4 on every price, moving the stop only when it gains at least `TrailStep_Points`, TrailMode 4 in steps of `TrailStartR` x R; the others once per closed one-minute bar); the time exits, the Friday close (gold) and one position per preset. Gold: every Dukascopy tick. BTC: Binance BTCUSDT one-second prices, four points per second (open, the extreme nearer the open, the other extreme, close; on 33 of the 68 BTC combinations of timeframe and system, Jan 2025 – Nov 2026, the other order changes 1 of 12,310 trades).
- **Checks of the replay.** The EA's code (translated from the MQL5 source and run in a simulated terminal) took the same trades on samples of setups covering every TrailMode: gold, 33 setups on Dukascopy's prices of Sep – Oct 2024 with VT's constant 0.15 spread, 470 of 470 trades identical in entry, stop, target, stop moves, exit and result; BTC, 32 setups on 16 May – 16 Aug 2026, 804 of 804. The gold figures use a spread that varies with Dukascopy's; that part was not in the EA check. An independent re-trace from the ticks of the final 15 Jul – 31 Dec 2024 gold run agreed on 25,383 of the 25,399 trades it compared (the 6 still open at the end of 2024 were left out): 16 sells with a previous-hump target differ, 15 of them reaching the target a moment earlier or later (R within 0.02) and one leaving at its stop instead, and one trade is only in the re-trace; none of them is in the chosen sets. BTC's one-minute trades equal the study's stored trades in 326 of 326 runs.
- **Gold costs (VT):** Dukascopy's mid price with VT Markets' 0.15 spread, scaled by Dukascopy's own spread so its spikes stay, and $0.60 commission per ounce. **Stressed:** one minute late, $0.10 slippage, $0.67 commission. The presets refuse an entry above a $0.60 spread.
- **BTC costs:** a constant $10 spread (the presets accept up to $30), no commission. **Stressed:** one minute late, $3 slippage, $2 commission per BTC.
- **The choice** follows a rule written down before the full replay ran (`BEST_TRAILING_RULE.md`): on each timeframe, among the EA's trailing systems with at least 100 trades in the 2026 months (at least 30 where none had 100: marked thin), the highest profit factor at VT costs. For gold no 2026 replay result existed before the rule. For BTC a test run with every setup's 2026 result had already been computed (only its M10 and M15 rows had been looked at), and an earlier replay of four BTC combinations (among them M2 ATR at entry, the later M2 choice) too, so for BTC the timing does not protect the choice. **Held** = profit factor 1.3 or more in every earlier period.

## Gold (XAUUSD)

| Timeframe | Best trailing (TrailMode) | Presets | 16 May – 13 Nov 2026, chosen on it: PF (trades) | Stressed | One-minute engine, same prices and costs | Trailing decided (2026) | At Dukascopy's own spreads: PF (trades) | 15 Jul – 31 Dec 2024: PF (trades) | Runner-up among the eligible: PF (trades) |
|---|---|---|---|---|---|---|---|---|---|
| M1 | none: no setup of the EA's systems passed the calibration | – | – | – | – | – | – | – | – |
| M2 | stepped (4) | 2 | 1.06 (105) | 0.98 | 1.02 | 1 of 105 | 1.12 (81) | 0.76 (70) | Bollinger band 0.83 (168) |
| M3 | EMA (7) | 3 | 0.98 (125), lost | 0.78 | 0.99 | 48 of 125 | 0.89 (82) | 0.62 (86) | higher-timeframe candle 0.97 (135) |
| M5 | hump structure (13) | 4 | 1.27 (141) | 1.10 | 1.31 | 20 of 141 | 1.37 (94) | 0.69 (116) | chandelier 1.19 (157) |
| M10 | ATR at entry (1) | 4 | 1.57 (203) | 1.38 | 1.56 | 116 of 203 | 1.21 (106) | 0.58 (154) | percent of price 1.25 (182) |
| M15 | higher-timeframe candle (11) | 5 | 0.74 (246), lost | 0.67 | 0.76 | 54 of 246 | 0.69 (133) | 0.99 (280) | hump structure 0.69 (101) |
| M30 | swing pivots (12), thin | 2 | 1.06 (68) | 1.05 | 1.12 | 10 of 68 | 0.67 (37) | 0.97 (81) | candle lows / highs 0.69 (56) |
| H1 | none: no setup of the EA's systems passed the calibration | – | – | – | – | – | – | – | – |

## BTC (BTCUSD)

| Timeframe | Best trailing (TrailMode) | Presets | 16 May – 13 Nov 2026, chosen on it: PF (trades) | Stressed | One-minute engine, same prices and costs | Trailing decided (2026) | 2024: PF (trades) | 2023 (from 15 Jan): PF (trades) | Runner-up among the eligible: PF (trades) |
|---|---|---|---|---|---|---|---|---|---|
| M1 | none: no setup of the EA's systems passed the calibration | – | – | – | – | – | – | – | – |
| M2 | ATR at entry (1) | 3 | 1.97 (121) | 1.53 | 2.14 | 94 of 121 | 1.05 (214) | 0.56 (187) | Parabolic SAR 1.37 (109) |
| M3 | candle lows / highs (6) | 3 | 1.41 (140) | 1.08 | 1.44 | 85 of 140 | 0.82 (271) | 0.84 (242) | none: no other eligible system |
| M5 | candle lows / highs (6) | 3 | 1.81 (156) | 1.61 | 1.89 | 103 of 156 | 0.97 (306) | 0.90 (320) | higher-timeframe candle 1.69 (166) |
| M10 | EMA (7) | 2 | 1.90 (102) | 2.03 | 1.95 | 53 of 102 | 1.02 (156) | 0.96 (201) | swing pivots 1.49 (129) |
| M15 | Bollinger band (10) | 5 | 0.96 (169), lost | 0.91 | 0.98 | 9 of 169 | 1.06 (360) | 0.84 (359) | higher-timeframe candle 0.87 (124) |
| M30 | ATR at entry (1) | 3 | 1.06 (100) | 1.04 | 1.09 | 18 of 100 | 1.07 (219) | 0.63 (209) | percent of price 0.66 (128) |
| H1 | none: no setup of the EA's systems passed the calibration | – | – | – | – | – | – | – | – |

- PF = profit factor (gross wins / gross losses), all the setups of a timeframe's set together. R = a trade's initial risk (entry to stop): a 1.5R target is 1.5 times the risk, and net +4.1R is 4.1 times one trade's risk. *lost* = the set lost money in the months it was chosen on.
- *One-minute engine, same prices and costs*: the study's one-minute backtest run on the same prices, for comparison with the replay. *Trailing decided*: trades the trailing closed, at market or at a stop it had moved (at least that many).
- Eligible = at least 100 trades in the 2026 months (at least 30 on a thin timeframe: gold M30). The runner-up column leaves out the others too. Some of them had a higher profit factor than the chosen set on fewer trades: gold M15 (chosen 0.74): percent of price 1.41 (25), Parabolic SAR 0.96 (96), profit lock 0.80 (86), swing pivots 0.743 against 0.739 (66); BTC M3 (chosen 1.41): percent of price 2.59 (23), swing pivots 2.25 (90), SMA 2.11 (83), Parabolic SAR 1.63 (67); BTC M5 (chosen 1.81): chandelier 1.93 (25), EMA 1.92 (31), risk multiples (EA default) 1.86 (52); BTC M15 (chosen 0.96): EMA 1.34 (34).
- The trailing never decided an exit of `Loma_BT_Gold_M2_Step_2of2_Sell_1200-2000_M30`, `Loma_BT_BTC_M15_Bollinger_1of5_Buy_AllDay_NoFilter`, `Loma_BT_BTC_M15_Bollinger_4of5_Sell_1200-2000_NoFilter`: in the first the trailing starts at or beyond the fixed target, so the stop cannot move before the target; in the others it never came into play in the replay (most of their trades end at their time limit). Their results come from the stop, the target and the time exits.
- 16 of the 39 presets lost money on their own in the 2026 months, 7 of them in sets that made money. A set's figure needs all its presets: dropping the losers would be one more choice made on those months.
- Every preset's header gives its own figures. `BEST_TRAILING_PRESETS.csv` lists them all, `BEST_TRAILING_BY_TIMEFRAME.csv` the choice of every timeframe, and `TICK_REPLAY_ALL_CELLS.csv` every trailing system that has setups on a timeframe (143 of the 224 combinations of symbol, timeframe and system; the others had no setup), with every period and cost model, replay and one-minute engine.
- CSV names. Models: `vt` = VT costs (gold) or the $10 spread (BTC), `vt_stress` = stressed, `duk_raw` = Dukascopy's own bid and ask with $0.60 commission (gold). Periods: `earlier` and `earlier_2024h2_*` = 15 Jul – 31 Dec 2024 (gold), `2023` (from 15 Jan) and `2024` (BTC), `calibration` and `picked_on_*` = 1 Jan 2025 – 15 May 2026 (the setups were picked on it), `unseen` and `chosen_on_2026_*` = 16 May – 13 Nov 2026 (the trailing was chosen on it). `tick_*` = the replay (BTC: one-second prices), `one_minute_*` = the one-minute engine on the same prices; `picked_on_score`, `picked_on_trades`, `picked_on_pf` and `study_one_minute_2026_pf` = the study's own one-minute figures at its costs (gold: FTMO spread, no commission); `picked_on_replay_*` and `picked_on_tick_pf` = the replay of the calibration months; `runner_up*` = the best other eligible system. Systems: `R` = risk multiples, `atr` = ATRentry = ATR at entry, `percent`, `profitlock`, `step` = stepped, `chandelier`, `candles` = candle lows / highs, `ema`, `sma`, `psar` = Parabolic SAR, `bollinger`, `htfcandle` = higher-timeframe candle, `pivots` = swing pivots, `hump` = hump structure.

## The replay against the one-minute backtest

All the setups of the EA's 14 systems pooled, VT costs. The replay takes almost the same trades as the one-minute engine on the same prices and costs, and its pooled profit factor is 0.004 to 0.045 lower. For the setups of one system on one timeframe and period (at least 30 trades) the difference runs from 0.18 lower (BTC M2 ATR at entry, 16 May – 13 Nov 2026: 2.14 to 1.97) to 0.10 higher (gold M15 swing pivots, 15 Jul – 31 Dec 2024: 1.10 to 1.20, not in this zip); for the 12 sets in this zip, from 0.18 lower to 0.06 higher (gold M2 stepped, 1 Jan 2025 – 15 May 2026: 1.44 to 1.50). The study's own gold figures were at FTMO's spread without commission, and higher: all its gold setups together made 0.87 in the 2026 months (11,177 trades) against 0.81 in the replay at VT costs, so for gold most of the drop comes from VT's costs, not from the ticks.

| Symbol | Period | Replay: trades, PF, net | One-minute engine: trades, PF, net |
|---|---|---|---|
| XAUUSD | 16 May – 13 Nov 2026 | 11,225, 0.81, -972R | 11,222, 0.82, -915R |
| XAUUSD | 1 Jan 2025 – 15 May 2026 (the setups were picked on it) | 23,290, 1.49, +4,085R | 23,287, 1.51, +4,176R |
| XAUUSD | 15 Jul – 31 Dec 2024 | 8,184, 0.78, -870R | 8,189, 0.78, -846R |
| BTCUSD | 16 May – 13 Nov 2026 | 6,091, 1.11, +225R | 6,091, 1.14, +276R |
| BTCUSD | 1 Jan 2025 – 15 May 2026 (the setups were picked on it) | 16,627, 1.65, +3,110R | 16,627, 1.69, +3,215R |
| BTCUSD | 2024 | 12,990, 0.98, -97R | 12,990, 1.00, +8R |
| BTCUSD | 2023 (from 15 Jan) | 12,577, 0.73, -1,332R | 12,576, 0.75, -1,180R |

## The 15 earlier trailing results, re-measured

The combinations of timeframe and trailing system that had reached a profit factor of 1.3 on the 2026 months in the one-minute backtest (the `Loma_T15` presets of the gold and BTC zips). They were selected on these same months, so this is a re-measurement, not a test: 11 of the 15 stay at 1.3 or more in the replay. On the earlier data none of the 15 reaches 1.3 in the replay (highest 1.12).

| Symbol | Timeframe | Trailing | 2026, study (one minute, its costs): PF (trades) | 2026, one-minute engine on the replay's prices at VT costs: PF (trades) | 2026, replay at VT costs: PF (trades) | Stressed | Earlier data, replay: PF (trades) |
|---|---|---|---|---|---|---|---|
| XAUUSD | M5 | hump structure | 1.41 (141) | 1.31 (141) | 1.27 (141) | 1.10 | 15 Jul – 31 Dec 2024: 0.69 (116) |
| XAUUSD | M5 | chandelier | 1.31 (157) | 1.19 (157) | 1.19 (157) | 1.10 | 15 Jul – 31 Dec 2024: 0.66 (111) |
| XAUUSD | M10 | percent of price | 1.31 (181) | 1.24 (182) | 1.25 (182) | 1.13 | 15 Jul – 31 Dec 2024: 0.66 (137) |
| XAUUSD | M10 | ATR at entry | 1.57 (206) | 1.56 (203) | 1.57 (203) | 1.38 | 15 Jul – 31 Dec 2024: 0.58 (154) |
| BTCUSD | M2 | Parabolic SAR | 1.48 (109) | 1.48 (109) | 1.37 (109) | 1.19 | 2024: 0.74 (227); 2023 (from 15 Jan): 0.67 (204) |
| BTCUSD | M2 | ATR at entry | 2.14 (121) | 2.14 (121) | 1.97 (121) | 1.53 | 2024: 1.05 (214); 2023 (from 15 Jan): 0.56 (187) |
| BTCUSD | M3 | candle lows / highs | 1.44 (140) | 1.44 (140) | 1.41 (140) | 1.08 | 2024: 0.82 (271); 2023 (from 15 Jan): 0.84 (242) |
| BTCUSD | M5 | candle lows / highs | 1.89 (156) | 1.89 (156) | 1.81 (156) | 1.61 | 2024: 0.97 (306); 2023 (from 15 Jan): 0.90 (320) |
| BTCUSD | M5 | SMA | 1.51 (205) | 1.51 (205) | 1.44 (205) | 1.37 | 2024: 1.07 (462); 2023 (from 15 Jan): 0.70 (425) |
| BTCUSD | M5 | profit lock | 1.35 (214) | 1.35 (214) | 1.28 (214) | 1.08 | 2024: 0.72 (400); 2023 (from 15 Jan): 0.70 (397) |
| BTCUSD | M5 | Bollinger band | 1.37 (112) | 1.37 (112) | 1.33 (112) | 1.22 | 2024: 0.74 (267); 2023 (from 15 Jan): 0.63 (250) |
| BTCUSD | M5 | higher-timeframe candle | 1.71 (166) | 1.71 (166) | 1.69 (166) | 1.49 | 2024: 1.12 (321); 2023 (from 15 Jan): 0.70 (337) |
| BTCUSD | M10 | EMA | 1.95 (102) | 1.95 (102) | 1.90 (102) | 2.03 | 2024: 1.02 (156); 2023 (from 15 Jan): 0.96 (201) |
| BTCUSD | M10 | stepped | 1.36 (161) | 1.36 (161) | 1.32 (161) | 1.24 | 2024: 1.10 (310); 2023 (from 15 Jan): 0.77 (291) |
| BTCUSD | M10 | swing pivots | 1.56 (129) | 1.56 (129) | 1.49 (129) | 1.48 | 2024: 1.08 (283); 2023 (from 15 Jan): 0.72 (269) |

- The study's costs: gold FTMO spread and no commission, BTC a $10 spread (the same as the BTC VT costs).
- The gold zip and its presets give these four gold combinations at VT's costs as M5 hump structure 1.31 (141), M5 chandelier 1.23 (157), M10 percent of price 1.24 (181), M10 ATR at entry 1.61 (206): that was the study's one-minute backtest on its own price file with VT's constant spread. On the replay's prices, with the spread scaled by Dukascopy's, the one-minute engine gives 1.31, 1.19, 1.24, 1.56 and the replay 1.27, 1.19, 1.25, 1.57.

## How to run the presets

- **One timeframe's set is one result:** its setups were tested together, each as its own EA with one position. Run them together on one **hedging** account (on a netting account the presets on one symbol share one position).
- **Overlap and risk:** in the replay the most positions open at once were gold M2: 2, gold M3: 3, gold M5: 4, gold M10: 4, gold M15: 5, gold M30: 2, BTC M2: 3, BTC M3: 2, BTC M5: 3, BTC M10: 2, BTC M15: 4, BTC M30: 3. Each preset has `RiskPercent=0.5`, so one set alone can have up to 2.5% at risk at once (gold M15: 5 presets). All gold sets together had up to 10 positions open in the replay (5.0%) and all BTC sets 8 (4.0%), but the 20 gold presets can hold 10.0% at once and the 19 BTC presets 9.5%. Lower `RiskPercent` (for example to 0.1) when you run a whole set or several sets. On BTC a lower `RiskPercent` needs a larger deposit before the 0.01 minimum lot fits a stop.
- **Gold commission:** the figures include $0.60 per ounce. Set `CommissionPerLot` to your round-trip commission per lot in the account currency, so a stop-out costs `RiskPercent` including commission.
- **BTC:** points are 0.01 USD (`AutoScalePoints=true`); `MaxSpread_Points=3000` ($30), `TrailStep_Points=200` ($2), no weekend close. BTC stops are wide (hundreds of dollars): with a 0.01 minimum lot a trade is skipped when the equity is too small for its stop (`SkipIfBelowMinLot=true`); test with a large deposit first.
- **Server time:** sessions and the end-of-day close are broker server time (New York + 7 h: GMT+2 in the US winter, GMT+3 in the US summer), the clock of VT Markets and FTMO.
- **News filter:** `UseNewsFilter` is on, as in the other presets: on demo or live the EA skips entries within 30 minutes of high-impact USD news (BTC too), which the replay did not do. It does nothing in the Strategy Tester. Set it to false to trade exactly what was replayed.

## If you want to test it

1. **Strategy Tester:** "Every tick based on real ticks" on your broker's symbol. The figures assume the replay's costs: for gold a spread near VT's $0.15 and $0.60 commission per ounce, for BTC a $10 spread and no commission; with other costs expect other trades and figures. The tester runs one preset at a time: run each preset of a timeframe's set on its own, over 16 May – 13 Nov 2026 and over the earlier period, compare each run with its preset's header, and add the set's runs up to compare with the tables above. In the tester the Load dialog usually opens in `MQL5\Profiles\Tester`; browse to `MQL5\Presets`.
2. **Then demo.** A tester run that matches shows that the EA trades its backtest, not that the edge is real.

## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35. |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_BT_Gold_*.set` | 20 gold presets: every setup of each gold timeframe's best system. |
| `MQL5/Presets/Loma_BT_BTC_*.set` | 19 BTC presets: every setup of each BTC timeframe's best system. |
| `BEST_TRAILING_RULE.md` | The rule of the choice, as written before the full replay ran, with a note added after an independent check. |
| `BEST_TRAILING_BY_TIMEFRAME.csv` | The choice of every timeframe, with its runner-up and the earlier-data check. |
| `BEST_TRAILING_PRESETS.csv` | Every preset with its figures. |
| `TICK_REPLAY_ALL_CELLS.csv` | Every trailing system that has setups on a timeframe: each period and cost model, replay and one-minute engine. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile). If the compiler reports anything, send the log rather than editing the file.
4. Attach the EA to an XAUUSD or BTCUSD chart (any timeframe: it reads its own from the preset). In **Inputs** click **Load** and pick a preset of that symbol.
5. Enable **Algo Trading**.
