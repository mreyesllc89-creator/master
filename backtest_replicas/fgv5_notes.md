# fgv5: FlashGold v5 Strategy (BTCUSD) + FGF [Update 1], canonical replica (stage 3): interpretations and limits

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Ground truth: `/home/user/master/FlashGold_v5_Strategy_BTCUSD_FGF.pine` at HEAD (Pine **`//@version=5`**, 1,402 lines; Update 1
= input `fgvInv`, "Inverted direction: opposite side at the same entries"). Unfused original:
`/home/user/master/FlashGold_v5_Strategy_BTCUSD.pine`. Brief: `$W/SPEC_fgv5.md`.

Files:
- `$W/fgv5.py`: the canonical module. It is implementation B plus path 'mag'; see `$W/reconcile_fgv5.md` for the
  choice and the exact changes.
- `$W/fgv5_ref.py`: a slow pure-Python reference of the orders and exits on both paths, written in this stage.
- `$W/tests_fgv5.py` with `$W/tests_fgv5.log`: 89 PASS, 0 FAIL.
- `$W/run_inv_fgv5.py`, its logs `$W/run_inv_fgv5_{BTC,XAU}.log` and its outputs `$W/out/inv_fgv5_<PAIR>_<TF>.json`
  (14 cells).
- `$W/reconcile_fgv5.md`, with `$W/fgv5_cases.py`, `$W/reconcile_fgv5_cmp.py` and the round logs
  `reconcile_fgv5_r{0,1,2}_*.log`.
- The two builds `fgv5_a.py` / `fgv5_b.py` and their notes. B carries the two reconcile fixes (D1, D2); A is
  unchanged.

## 1. Interface

    prepare(pair, chart_tf, params=None, _perm=None) -> P      SIGNAL inputs (SPEC 3.1) + every fgf* input
    simulate(P, x=None, full=False, log_cap=0, sub=None) -> R  ORDER / EXIT inputs (SPEC 3.2) by Pine name, plus
                                                               path 'tv' | 'mag', cost 'tv' | 'ours' | 'stress',
                                                               inv / fgvInv (aliases; both given and different: error)
    trades(P, R) -> DataFrame      one row per entry fill; dir = the REAL side, sig = the signal's side
    summary(P, R) -> dict          the common fields (as hrd.summary_fast + extra_fields) and SPEC 12's own fields
    run(pair, chart_tf, params=None) -> (trades, summary)
    prepare_arrays(...)            P from injected arrays (tests)
    sub_bars / get_sub / fake_sub_bars / clear_cache

ORDER keys given to `prepare` become that P's defaults. A SIGNAL key in `x` raises unless it repeats P's value.
Unknown keys raise, and drawing inputs are accepted and ignored. Validation follows the Pine `minval` / `maxval` and
the option lists. `priorDriftBars > 500` raises, because of `max_bars_back = 500`.

## 2. Pine v5, not v6: where it matters here

| topic | v5 (this file) | v6 | effect here |
|---|---|---|---|
| `margin_long` / `margin_short` not set | default 0: no margin simulation | default 100 % | **Matters.** 10 BTC (about $880k) on 100,000 would be refused or margin-called under v6. v5 never refuses or calls. Replica: no margin rule (V15). Equity can fall below 0 and trading continues: every inverted BTC default run does so. Counted in `neg_equity_bars`, `min_equity`, `max_notional_x`. The fair halves are NaN once an `eq_before <= 0` falls in a half. |
| trade limit | the strategy stops with an error after about 9,000 trades (as remembered; not checkable) | the oldest trades are trimmed | TradingView cannot show the full windows of BTC 1 / 5 / 15 and XAU 1 at the defaults (85,682 / 22,468 / 8,241 / 16,658 trades). The replica has no limit. |
| `bool` can be `na`; `and` / `or` evaluate both operands | yes | no / short-circuit | None. The strategy part has no `bool[1]`, no bool from `request.security`, and no call with history or side effects inside a condition (`calcQty` is called inside the `if` body). |
| a comparison with `na` | false | false | Same in both. A zone with na direction is not aligned. The first `burstPts` is na and gives no candidate. `high >= position_avg_price + na` is false. |
| `math.max(na, 1.0)` | na | na | Kept: the ATR-mode trail / runner distances stay na while ATR is na. |
| `request.security` defaults | gaps_off, lookahead_off | the same | None: every call passes both arguments (L1026-1038). |
| `strategy.exit` with a relative and an absolute parameter of one kind | the absolute one is used | the one reached first | None: no call mixes them. XL2 in breakeven mode passes `stop =` and no `loss =`. |
| `dynamic_requests` | default false, set true here | default true | None on history. |
| integer division, implicit casts | allowed | removed | None in the trading logic. |

The filter block runs under v5 here and under v6 in the file `fgf.py` was verified on. Its gates use none of the
constructs above in a way that differs, so `fgf.fgf_permissions` applies as is (SPEC 2.1).

## 3. `strategy()` and the costs

The call sets:
- `pyramiding = 0`, `initial_capital = 100000`, `currency.NONE`;
- `default_qty_type fixed 10`, which is never used: both `strategy.entry` calls pass `qty = calcQty(...)`;
- `calc_on_every_tick = false`, `process_orders_on_close = false`, `calc_on_order_fills = false`: one script run
  per bar at its close, and its orders act from the next bar;
- `max_bars_back = 500`, `dynamic_requests = true`.

Cost **'tv'** (the "script" cost of the runner) applies both of the script's Properties the way TradingView does:
- commission `percent 0.02`: `0.0002 × booked fill price × qty` on **every** fill. That is the entry, each exit
  fill (XL1 and XL2 apart) and both legs of a reversal. It is charged on the slipped price;
- slippage `5` ticks = **0.05 in price**, against the order, on every **stop** fill (stop entries, stop loss,
  breakeven stop, runner and Fixed-style trailing stops) and every **market** fill (`strategy.close` 'opp',
  `strategy.close_all` 'time', the replica's 'end');
- **limit fills get no slippage**: the take profit, the inverted limit entries, and a reversal by a limit entry.
  So the normal stop entry pays 0.05 and the inverted limit entry at the same price does not.

Costs 'ours' / 'stress' replace both Properties with `hrd.COSTS` per-fill costs and no slippage:
- XAU (0.15, 0) / (0.26, 0);
- BTC (0.10, 0.0002) / (0.11, 0.00035).

## 4. The signal: what is reused from fgf.py

The strategy's signal (L1003-1165) is, token for token after renaming, the filter block's `fgfSignal` (L509-623).
That covers the price model, the TDI direction, the zone mapping and counts, burst, drift, candidates and the entry
hold. The differences are display-only (`conflictZones`, `mixedZones`, `zoneRiskText`, the unused slow TDI line),
plus where the timeframes come from: the chart and "Auto timeframes" here, the filter timeframe there. `isHigher`
compares with the chart instead of the filter context, which is the same rule.

The canonical module (B) nevertheless implements the signal side itself from the Pine: `_tdi_dir_k`, `_atr_k`,
`map_lookahead_off`, `map_lookahead_on_prev`, `trade_zone`, `_signal_k`. It uses fgf only for:
- `fgf.fgf_permissions`, which gives `fgfBuyOk` / `fgfSellOk` (the filter block is never reimplemented);
- `fgf._bars`, which gives the zone timeframes that have no data file.

The identity is checked, not assumed:
- the canonical signal arrays equal `fgf._filter_series` (with the chart as the filter timeframe and the mapped
  inputs) on every row of every chart file. That holds for the defaults and 4 non-default signal settings on 4 cells
  (tests `signals`), and for 19 more settings in `fgv5_b_check_sig.log`;
- on "60" with the defaults they equal the filter's own signals;
- the counts of SPEC 4.6 are reproduced.

- **BTC "960" (zone 3 of a 240 chart, V17).** It is built from the 1-minute file restarting at 00:00 UTC every day:
  10,847 bars against fgf's 8,140 epoch-grid bars, which changes 131 BTC 240 signal bars. A BTC minute timeframe
  that divides 1,440 is the same on both grids.
- **`oneEntryPerBar` is inert** (L1122): `lastEntryBar` only ever holds the current bar after `canFire` was
  computed. `tdiSlowLen` and `useBurstGate` without `useAnyCombo` do nothing. Accepted and checked.
- **Seconds timeframes** have no data: such a zone is na and `ignoreNaZones` drops it.
- **`autoTf` on a D / W / M chart** (2D / 4D zones) is not supported.

## 5. The broker on path 'tv' (SPEC 5-7, V1-V22, as both builds implement them)

Per window bar:
- **A1.** A market close of the previous run fills at the open, `open - pos × slip`.
- **A3.** Gap test of the open trade's exits at the open:
  - stops at or beyond the open fill at the open; XL1 and XL2 together are one joint fill with XL2's kind;
  - then the target (a limit at the open);
  - then the trailing update.
- **A4.** Pending entries crossed at the open, earlier placement first: a fill at the open, a reversal if a position
  is open, OCA-cancel the other slot, then the V11 test at the fill price.
- **B.** The rule-4 path O-H-L-C, or O-L-H-C when `(high - open) >= (open - low)`:
  - on each leg, the first price reached wins, and exits go before entries at one price;
  - the favourable trail moves up to each event price before the event;
  - a new trade's exits are live at once on the rest of the leg.
- **C.** The script, in Pine order:
  - exit geometry of this bar;
  - the mirrored reads `fgvNL` / `fgvNS`;
  - the opposite close;
  - the BUY block, then the SELL block, with `calcQty` on this close's `strategy.equity`;
  - the FGD funnel;
  - the stale cancel by id;
  - the breakeven flag from the whole bar's high / low;
  - XL2 into breakeven mode from the next bar;
  - the time stop.
- **D.** Bar-close equity.

The readings this rests on (one line each; the full list with reasons is SPEC 10):
- the exits use the id's locks written when its order was last placed, measured from the booked (slipped) fill;
- Partial style = `TpStyle == "Partial + runner" and partPct < 100`:
  - XL1 = `Q × partPct / 100` exactly, with stop SL and limit TP;
  - XL2 = the rest, with stop SL, then breakeven = `position_avg_price` from the bar after `tpHit`, and a trail
    activated at the TP level with offset `lockRun`;
  - the trailing state is kept when XL2 switches to `stop =`;
  - XL1 fills once;
- Fixed style: XL with SL, TP and, with `useTrail`, a trail from `entry ± lockAct` (armed at the fill when
  `lockAct <= 0`) with offset `lockDst`;
- the nearer of the own stop and the trail is in force, and a tie goes to the trail. Kinds: 'sl' / 'be' / 'runner'
  / 'trail' / 'tp' / 'tp_part', or 'reverse' / 'opp' / 'time' / 'end' for a market or reversal close of the
  remainder;
- the open quantity is the filled Q until an exit order fills (D2; `strategy.position_size`), after that the part
  left;
- **`be_no_tp` (V18, literal L1315-1318).** An inverted limit fill can see the bar's favourable extreme from before
  the fill. From the next bar XL2 (70 %) is then at breakeven while XL1 (30 %) keeps SL / TP. It is counted, and it
  is 0 in every normal run (tests `header` (v));
- window: flat with clean `var`s at the first window bar, signals warmed up from the file's first bar, orders of the
  last bar dropped, an open trade closed at the last close as a market fill ('end', slipped, cost charged,
  `exit_time = t_close`).

## 6. Update 1 (`fgvInv`), L1199-1272

- `allowL = fgvInv ? Direction != "Long" : Direction != "Short"`, and `allowS` alike: `Direction` restricts the REAL
  orders.
- `fgvNL = fgvInv ? inShort : inLong` (and `fgvNS`): the opposite close, the entry conditions and the funnel read
  the mirrored position.
- Inverted, a BUY signal the filter allows (`fgfBuyOk`, the signal's own gate) writes the S locks and places "Short"
  as a **sell LIMIT** at `buyEntryPrice`. A SELL signal writes the L locks and places "Long" as a **buy LIMIT** at
  `sellEntryPrice`. Both trigger on the signal's side, so they fill on the same candle at the same raw price as the
  stop would.
- Cancel, breakeven flag, the 10 `strategy.exit` calls and the time stop are keyed by id and work on the real
  trade.
- There is no other reverse option in this script, so the runner stores no reversed-label run.
- Checked mechanically against the text (tests `inv`):
  - the HEAD order code with `fgvInv` = false equals the 6c59b9f text line for line;
  - 6c59b9f equals the unfused original apart from `and fgfBuyOk` / `and fgfSellOk` and the FGD funnel;
  - so `fgfOn` false with `fgvInv` false is the original script (and P6 holds: `fgfOn` false == injected all-True
    gates).
- Properties (tests `inv`), on paths tv and mag:
  - P1, exact mirror: Fixed style with a symmetric bracket, cost 'ours', both exit units and Pips,
    `exitOnOpposite`, a time stop, `entryValidBars` 0 / 1, filter on and off;
  - P2: 1,800 single decisions through `_decide`, from the negated position with `Direction` swapped;
  - P3: the first trade;
  - P4: `Direction` "Long";
  - P5: chart 60 with the filter on gives no trade.

## 7. Path 'mag' (Bar Magnifier), as implemented

- **Sub-bars.** The sub-bars of chart bar k are the rows of `data/<PAIR>_1.parquet` with `t_open` in
  `[t_open[k], t_close[k])`. They are checked to rebuild every chart bar's OHLC exactly, and no two chart bars share
  one.
- **Per sub-bar, in time order**, with B's unchanged `_walk`:
  - A3: the open trade's exits tested at the sub-bar's open;
  - A4: pending stop / limit entries crossed at the sub-bar's open fill there;
  - B: the sub-bar's own rule-4 path.
- **Carried across sub-bars:** pending orders, OCA, the trailing state and the partial state. A level crossed by a
  jump between two minutes fills at the next minute's open.
- **On the chart bar:**
  - A1 (the market closes 'opp' and 'time') stays at the chart open;
  - the whole script run (C, including the stale cancel, the time stop and the **breakeven flag from the CHART bar's
    high / low**) and the equity point (D) stay at the chart close;
  - the trade times and bars are the chart bar's. `gap` / `gap_entries` mean "filled at the open of the bar walked",
    which on 'mag' is a sub-bar's open: the chart open or a jump between minutes.
- **Tests:**
  - chart "1": 'mag' == 'tv' (XAU 1 and BTC 1 full windows, filter off / on, 3-4 settings each; and every chart-1
    runner row);
  - one fake sub-bar per chart bar == 'tv' (6 cells × 6 settings, and the 29 hand-built scenarios);
  - 4 hand-built 'mag' scenarios with real sub-bars (M1-M4: a stop inside the minutes, an entry by a jump between
    minutes, a Fixed trail that fills inside the bar, the inverted `be_no_tp` from the chart bar's high);
  - `fgv5_ref.py` on 30 random settings over 2-month windows. It agrees trade by trade, on the counters and on the
    equity array, and 'mag' differs from 'tv' in 18 of the 30.
- **Speed** (after compilation): BTC 1 'tv' 0.20 s, 'mag' 0.34 s; BTC 5 'mag' 0.13 s; BTC 60 'mag' 0.016 s.
- **Not TradingView's own Bar Magnifier:** it is our 1-minute walk with the reading above.

## 8. XAUUSD: inputs that only make sense at BTC prices, and what the replica does

This is the "BTCUSD build". On gold every dollar or point distance is applied **literally**; nothing is rescaled,
because the Pine rescales nothing.
- **`ExitMode` "Pips" with `pipSize` 1.0** ("1 pip = $1 per BTC"): stop `slPips` 30 = $30, target 5 R = $150,
  runner trail `runTrailPips` 600 = $600, Fixed trail `trailActPips` 150 / `trailPips` 600.
  - $30 is about 2.4 % of a $1,250 gold price: 12.6 ATR(14) of a 60-minute bar, 27 of a 15-minute bar, 126 of a
    1-minute bar.
  - The $150 target is never reached in the window, so the default gold strategy is a **stop-and-reverse system**.
    XAU 60 normal: 433 of 434 trades end by 'reverse', 1 by 'end'. XAU 60 inverted: 432 'reverse', 5 'sl', 1 'end'.
  - With `Direction` "Long" a single trade opened in January 2017 stays open to the end.
  - 'mag' and 'tv' therefore differ only in the reversal stop fills inside the bar.
- **`ExitMode` "Points"**: `slPoints` 3900 = $39, `tpPoints` 19500 = $195, `trailActPoints` 4500, `trailPoints` 1000,
  `runTrailPts` 58000 = $580. These are "0.1 × the median ATR of the BTC calibration month".
- **Sizing**: `fixedQty` 10 ("contracts = BTC") = 10 oz, about 0.13-0.14 of the account (`max_notional_x` 0.14);
  `maxQty` 50 and `qtyStep` 1 are coin-sized. On BTC the same 10 units are about 9 accounts.
- **The other way round**, the Points-unit SIGNAL inputs are the original GOLD indicator's: `entryDistPoints` 50
  ($0.50), `entryHoldMinFavPoints` 5, `burstPointsInput` 172 ($1.72). With the default `DistUnit` "ATR" they are
  inert. `spreadPoints` 25 ($0.25) is gold-like and negligible on BTC.
- **Portable inputs:** everything in ATR (`DistUnit` "ATR", `ExitMode` "ATR"), the TDI and zone inputs, `partPct`,
  `maxBarsHeld`, `entryValidBars`, `QtyMode` "Risk %".

## 9. Results by time frame (runner, default inputs, full windows)

"TV view" = path 'tv' with the script's cost (0.02 % + 5 ticks); "1-minute" = path 'mag' with our costs. Trades /
net %. Fixed 10 units on 100,000 (BTC: about 9 accounts, so BTC equity goes far below 0 and the fair halves are NaN;
v5 has no margin rule). Full summaries (both paths × both cost modes) are in `out/inv_fgv5_<PAIR>_<TF>.json`.

| cell | normal, filter off: TV / 1-min | normal, filter on: TV / 1-min | inverted, filter off: TV / 1-min | inverted, filter on: TV / 1-min |
|---|---|---|---|---|
| BTC 1 | 85,682 / -11,066 % · 85,658 / -11,150 % | 27,779 / -3,251 % · 27,775 / -3,282 % | 160,503 / -62,629 % · 160,503 / -62,886 % | 52,369 / -18,317 % · 52,369 / -18,398 % |
| BTC 5 | 22,468 / +64.6 % · 23,767 / -2,397 % | 12,585 / +375.0 % · 13,399 / -1,273 % | 38,029 / -14,202 % · 37,885 / -14,134 % | 19,777 / -7,030 % · 19,707 / -7,011 % |
| BTC 15 | 8,241 / +2,011 % · 9,178 / -514.1 % | 5,344 / +1,366 % · 5,868 / -316.5 % | 12,496 / -4,541 % · 12,481 / -4,479 % | 7,310 / -2,578 % · 7,304 / -2,547 % |
| BTC 30 | 4,218 / +2,475 % · 4,951 / -153.2 % | 2,564 / +1,475 % · 2,806 / -74.9 % | 6,079 / -2,378 % · 6,072 / -2,291 % | 3,082 / -1,205 % · 3,080 / -1,150 % |
| BTC 60 | 2,207 / +2,158 % · 2,670 / -198.5 % | 0 · 0 | 2,976 / -1,189 % · 2,976 / -1,081 % | 0 · 0 |
| BTC 120 | 1,100 / +1,997 % · 1,319 / +30.6 % | 238 / +420.4 % · 241 / -7.3 % | 1,424 / -661.2 % · 1,424 / -598.3 % | 243 / -95.7 % · 243 / -99.3 % |
| BTC 240 | 609 / +1,560 % · 719 / -37.3 % | 159 / +383.1 % · 163 / +46.5 % | 734 / -302.6 % · 734 / -277.2 % | 164 / -104.0 % · 164 / -95.2 % |
| XAU 1 | 16,658 / -100.4 % · 16,658 / -48.5 % | 2,109 / -13.9 % · 2,109 / -7.3 % | 16,658 / -86.8 % · 16,658 / -51.5 % | 2,109 / -9.8 % · 2,109 / -5.4 % |
| XAU 5 | 4,374 / -27.5 % · 4,374 / -13.9 % | 1,479 / -11.2 % · 1,479 / -6.6 % | 4,374 / -21.6 % · 4,374 / -12.3 % | 1,479 / -5.4 % · 1,479 / -2.3 % |
| XAU 15 | 1,521 / -9.6 % · 1,521 / -4.8 % | 883 / -7.2 % · 883 / -4.5 % | 1,521 / -7.5 % · 1,521 / -4.3 % | 883 / -2.7 % · 883 / -0.8 % |
| XAU 30 | 727 / -0.8 % · 727 / +1.5 % | 475 / -1.1 % · 475 / +0.4 % | 729 / -7.4 % · 729 / -5.9 % | 480 / -4.1 % · 480 / -3.1 % |
| XAU 60 | 434 / -3.6 % · 434 / -2.2 % | 0 · 0 | 438 / -1.4 % · 438 / -0.5 % | 0 · 0 |
| XAU 120 | 245 / -2.1 % · 245 / -1.4 % | 63 / -0.5 % · 63 / -0.3 % | 251 / -1.0 % · 251 / -0.4 % | 65 / -0.1 % · 65 / +0.0 % |
| XAU 240 | 120 / -1.1 % · 120 / -0.7 % | 28 / +0.4 % · 28 / +0.5 % | 127 / -0.5 % · 127 / -0.3 % | 37 / -1.2 % · 37 / -1.1 % |

Reading it:
- **BTC, normal: the TradingView view is an artefact of the one-path bar.** The $30 stop is 0.03-0.8 ATR of the
  chart bar, so 'tv' fills the stop entry and its 5 R target on the same rising leg. BTC 60: 1,157 of 2,207 trades
  close on their entry bar, PF 4.6. On the 1-minute path the stop is usually reached first: BTC 60 -198.5 %,
  PF 0.85, win 14.7 %. From 5 to 60 minutes every BTC default is a large loss on 'mag'. On 120 / 240 it is near zero
  or small and unstable across the halves (BTC 120 1-minute fair halves -37.9 % / +110.2 %).
- **BTC, inverted:** a large loss on both paths. 'tv' and 'mag' nearly agree because the inverted limit entry fills
  on the adverse leg and is usually stopped at once.
- **BTC 1:** 'tv' == 'mag' for one cost mode (the table's columns differ by the cost mode only). At 0.02 % per side
  the commission (about $35 per coin per round trip) exceeds the $30 stop.
- **XAU:** a stop-and-reverse system (section 8), so 'tv' and 'mag' give the same trades. The two columns differ
  mostly by the cost mode: 'ours' $0.30 / oz against 'tv' about $0.61 / oz per round trip.
- **Chart 60 with the filter on: no trade at all**, both pairs and directions. The strategy's signal IS the
  filter's 60-minute signal, and its level ("Entry price") puts the signal bar's close in the opposite zone. On
  other charts the filter lets 14-59 % of the signals through (XAU 240 34 of 240 buys, BTC 15 5,049 of 8,496).

## 10. What is not implemented / cannot be reproduced

- TradingView itself: nothing can be compiled or backtested here. V2-V13 are readings of its engine. The readings
  both builds share are listed at the end of `reconcile_fgv5.md` (stage 4 audits them).
- TradingView's margin model is not simulated (the v5 default is 0 anyway), nor is v5's 9,000-trade stop.
- TradingView's rounding of the off-tick entry prices and levels, and of the 30 % partial to the symbol's lot (V16).
- The feeds: the header's figures are MEXC / Bitfinex BTC and OANDA gold; ours are Bitstamp BTC and Dukascopy gold
  bid with TradingView-style sessions.
- Live behaviour: a limit touched but not filled, real slippage, real spread, intrabar ticks below 1 minute. Below
  the 1-minute bar the 'mag' path uses rule 4 again.
- Seconds timeframes (no data); `autoTf` on D / W / M charts.
- `fgf.py`'s own residuals (`reconcile_fgf.md`).
- Memory: the A / B / canonical comparison processes on BTC 1 peaked at 3.9-4.1 GB, above the brief's 3 GB, because
  each module keeps its own copy of the 1-minute file. The canonical module alone peaks at 2.23 GB (runner BTC 1).
