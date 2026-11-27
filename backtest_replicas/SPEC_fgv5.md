# SPEC_fgv5: FlashGold v5 Strategy (BTCUSD) + FGF [Update 1] (key `fgv5`), stage 1 brief

Work dir `$W` = `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`.
Read first: `$W/REPLICA_SPEC.md` (stages, interface, data, windows, cost modes), `$W/SPEC_AH.md` (Pine
built-ins, the intrabar path = "rule 4"), `$W/SWEEP_AH_SPEC.md` section 2 (prepare / simulate, 'mag',
'stress', fair halves, the trailing exit), `$W/fgf.py` (docstring; the functions named in section 4) with
`$W/reconcile_fgf.md`. Worked examples of the broker: `$W/hrd.py` (`_walk`: stop + limit + trailing stop
along one path, `summary_fast`, `extra_fields`, `sub_bars`, `COSTS`) and `$W/gvl.py` (`_walk_bar`: pending
stop / limit ENTRY orders and the open trade's bracket on one path; the closest sibling of this script).
`$W/danny.py` / `SPEC_danny.md` section 8 show slippage in ticks handled in fill prices.

Ground truth: `/home/user/master/FlashGold_v5_Strategy_BTCUSD_FGF.pine` at HEAD (1,402 lines; `Lnnn` below
are its line numbers). It is **Pine `//@version=5`** (L300), not v6: section 2.1 lists where that matters.
Unfused original: `/home/user/master/FlashGold_v5_Strategy_BTCUSD.pine` (518 lines). Update 1 diff:
`git -C /home/user/master diff 6c59b9f HEAD -- FlashGold_v5_Strategy_BTCUSD_FGF.pine`. Where this brief and
the Pine disagree, the Pine wins; say so in your notes. Builders write `$W/fgv5_a.py` / `$W/fgv5_b.py` and
`$W/fgv5_<a|b>_notes.md`, without reading the other build. Never edit an existing module (`fgf.py` included).
Never write inside `/home/user/master`. `python3 -I`, at most 2 processes, under 3 GB each.

The stage-1 probes are in `$W/fgv5_spec_tmp/` (`probe_lib.py`, `probe_ident.py`, `probe_sig.py`,
`probe_960.py`, `probe_sim.py`, `probe_batch.py`, `probe_best.py`). **Builders must NOT read that directory**
(they would make the two builds share its mistakes). Its numbers are quoted below as "probe, unverified": one
pure-Python implementation, no cross-check. If your two builds agree with each other and not with a probe
number, trust the builds and say so.

Ten facts shape everything below:

1. **The strategy's signal IS the filter's FlashGold signal code, run on the chart.** Lines L1003-1165 (price
   model, TDI zones, burst, candidates, entry hold) are, token for token after renaming, the body of the
   filter block's `fgfSignal` (L509-623); the only differences are where the timeframes come from (the chart
   and "Auto timeframes" here, the filter timeframe there) and display-only helpers (`conflictZones`,
   `mixedZones`, `zoneRiskText`, the unused slow TDI line). Checked mechanically (probe_ident). So `fgf.py`'s
   verified kernels `_tdi_dir` and `_signal_arm` compute this strategy's signals (section 4).
2. **On a 60-minute chart with default inputs the filter blocks every signal** (both pairs, 0 trades). With
   "Auto timeframes" on (default) the strategy runs parent / zones on chart / 2x / 4x, which on "60" is
   exactly the filter's 60 / 120 / 240 with the same inputs: the strategy's signals ARE the filter's signals
   (BTC 60: 1,882 / 1,918, equal to the filter's own new signals). Level "Entry price" puts the BUY level at
   ask + 0.25 ATR above the close, so at the signal bar's close price sits in the SELL ZONE: `fgfBuyOk` is
   false on every BUY bar (`fgfSellOk` true), and the mirror for sells. The header says the same (L236-247).
   On other charts the filter's 60-minute level is from another candle and lets part of the signals through
   (table in section 4.6).
3. **Entries are STOP orders above / below the market** (buy stop at ask + entry distance, sell stop at bid -
   entry distance; with "Inverted direction" a LIMIT order of the other side at the same price), placed at a
   bar close, live from the next bar, cancelled after `entryValidBars` = 3 bars, both ids in one OCA group.
   They fill intrabar, and the exits are live from the fill: a trade can open and close on the same leg of
   the same bar.
4. **Two exit orders per side, re-sent on every bar** (L1320-1340): with the default "Partial + runner",
   `XL1` closes 30 % at the take profit (with the stop loss), `XL2` (the rest) keeps the stop loss, trails
   from the take-profit level, and from the bar after the take-profit level was reached its stop moves to
   the entry price (breakeven). The breakeven flag is hand-coded from the whole bar's high / low (L1315).
5. **The default exit unit is "Pips" = fixed DOLLAR distances** (`pipSize` 1.0): stop $30, target $150 (5 R),
   runner trail $600. On BTC 2024-26 (median close 88,161) a $30 stop is 0.034 % of price, 0.06 ATR(14) of a
   60-minute bar and 0.79 ATR of a 1-minute bar; the 'tv' path (one O-H-L-C walk) then books most of the
   result inside the entry bar (probe: BTC 60 default, filter off, +2,158 %, 1,157 of 2,207 trades closed on
   their entry bar; inverted -1,181 %). On gold $30 is 12.6 ATR of a 60-minute bar and the $150 target is
   never reached: every default gold trade ends by a reversal (probe: 433 of 434 on XAU 60).
6. **`strategy()` sizes with a FIXED 10 contracts on 100,000 of capital** (`QtyMode` "Fixed", `fixedQty` 10):
   10 BTC is about 9 times the account, 10 oz of gold 0.13 times. Under v5 the margin default is 0, so
   TradingView does not refuse entries or margin-call; equity can go negative and trading continues (probe:
   BTC 60 inverted default, filter off: minimum equity -1.09 M). Section 9.
7. **Cost 'tv' = commission 0.02 % of every fill's value + slippage 5 ticks (0.05) on every stop and market
   fill**, none on limit fills. The normal stop entry pays the slippage, the inverted limit entry does not.
   On BTC the commission alone is about $35 per coin per round trip, more than the default $30 stop.
8. **Update 1 (`fgvInv`) flips the ORDER after every decision** (L1199-1272): a BUY signal the filter allows
   places a SELL LIMIT at the buy stop's price (id "Short", the S locks), a SELL signal a BUY LIMIT (id
   "Long"); decisions read the mirrored position (`fgvNL`, `fgvNS`); exits, cancel, breakeven, time stop are
   keyed by id and work on the real trade. No other reverse option exists. One literal asymmetry: the
   breakeven flag reads the whole bar's high / low, so an inverted limit fill can set breakeven from a price
   reached BEFORE the fill (section 8, counted `be_no_tp`).
9. **Every input default of the filter block equals `fgf.DEFAULTS`** (`fgfOn` = true included; the block is
   byte-identical to the one `fgf.py` replicates apart from `FGF_FORCE_OVERLAY`, a drawing switch). The filter
   timeframe is fixed at "60" by default whatever the chart; the strategy's own TDI / burst inputs do not
   change the filter (it has its own `fgf*` copies).
10. **One bar-construction exception**: with "Auto timeframes" a 240-minute chart reads zone 3 on "960"
   minutes. `fgf._bars` builds BTC "960" on the epoch grid; TradingView (and `build_bars.py`'s own rule, "BTC
   intraday bars aligned to UTC midnight") restarts it at 00:00 UTC every day. It changes 131 of 910 BTC 240
   signal bars (probe_960). Assumption V17: build it with the daily reset (section 4.2).

---------------------------------------------------------------------------------------------------

## 1. What the file is made of

| part | lines | replica |
|---|---|---|
| header: UPDATE 1 block, strategy description, INVERTED DIRECTION, two CALIBRATION records, data notes | 1-299 | read it; not a source of numbers (other feeds: MEXC / Bitfinex BTC, OANDA gold; other windows; another replica with R units and no sizing) |
| `strategy()` | 301-306 | section 2 |
| indicator inputs (core, burst, TDI zones), effective timeframes, visuals | 309-366 | section 3 |
| strategy inputs S1 entry order, S2 exits, S3 sizing | 369-405 | section 3 |
| FlashGold Direction Filter block | 407-987 | `$W/fgf.py`, never reimplemented (`fgf.fgf_permissions` gives `fgfBuyOk` / `fgfSellOk`) |
| `fgvInv` (Update 1), declared last | 990 | section 8 |
| exported "FGF" plots | 993-1001 | ignored (Data Window) |
| price model, TDI zones, burst / candidates, entry hold (the signal) | 1003-1165 | `prepare`, section 4 |
| exit geometry, locks, `calcQty` | 1167-1196 | `simulate`, sections 7 and 9 |
| orders (Update 1 lines 1199-1272), FGD funnel, stale cancel, breakeven flag, the 10 `strategy.exit`, time stop | 1198-1346 | `simulate`, sections 6-8 |
| plots, labels, table | 1348-1402 | ignored |

Against the unfused original (`diff` of the code): the strategy part of the fused file at `6c59b9f` differs
from the original only by `and fgfBuyOk` / `and fgfSellOk` at the end of the two entry conditions (original
L382 / L394), the FGD funnel plots (L1274-1287) and `dynamic_requests = true` in `strategy()`. Update 1 then
added `allowL` / `allowS` remapping, `fgvNL` / `fgvNS` and the two `if fgvInv ... else` order blocks, each of
which reduces to the `6c59b9f` text with the option off (L1210-1211 say so; inv notes section 6). So with
`fgfOn = false` and `fgvInv = false` the fused file trades exactly like the original.

There are no alerts, no `strategy.order`, no `strategy.cancel_all`, no sessions, no day boundary, no time
zone, no cooldown and no daily limit anywhere in the strategy part (`labelTimeZone` is display only).

---------------------------------------------------------------------------------------------------

## 2. The `strategy()` call (L301-306)

```
strategy("FlashGold v5 Strategy (BTCUSD) [Update 1]", "FlashGold v5 S (BTCUSD) U1", overlay = true,
  max_labels_count = 500, max_lines_count = 500, pyramiding = 0, initial_capital = 100000,
  currency = currency.NONE, default_qty_type = strategy.fixed, default_qty_value = 10,
  commission_type = strategy.commission.percent, commission_value = 0.02, slippage = 5,
  calc_on_every_tick = false, process_orders_on_close = false, calc_on_order_fills = false,
  max_bars_back = 500, dynamic_requests = true)
```

| argument | meaning for the replica |
|---|---|
| `pyramiding = 0` | one entry per side. The script never sends an entry on the side already held (`not fgvNL` / `not fgvNS`, section 7). An opposite entry that fills while a position is open closes it and opens the new one (reversal, V9) |
| `initial_capital = 100000`, `currency.NONE` | `INITIAL_CAPITAL = 100000.0`, no conversion. Net % depends on it (`fixedQty`, `maxQty`, `qtyStep` are absolute) |
| `default_qty_type = strategy.fixed`, `default_qty_value = 10` | never used: both `strategy.entry` calls pass `qty = qL / qS` from `calcQty` (whose Fixed branch is also 10) |
| `commission_type = percent`, `commission_value = 0.02` | 0.02 % of the fill value per fill (entry, every exit fill, both legs of a reversal): `0.0002 x fill_px x qty`, on the slipped price |
| `slippage = 5` | 5 ticks = **0.05 in price** (mintick 0.01), against the order, on every STOP fill (entry stops, stop loss, breakeven stop, trailing stops) and every MARKET fill (`strategy.close`, `strategy.close_all`, the replica's 'end'); LIMIT fills (take profit, inverted limit entries) get none. Section 9 |
| `calc_on_every_tick = false` | one run per bar at its close, live too. No effect on history |
| `process_orders_on_close = false` | orders placed in the run of bar j are processed from bar j+1 on: market orders at its open, stop / limit orders along its path (SPEC_AH rule 1) |
| `calc_on_order_fills = false` | no extra run after a fill: exactly one script run per bar |
| `max_bars_back = 500` | `midPrice[priorDriftBars]` needs `priorDriftBars <= 500`; the replica raises above 500 (TradingView would raise a runtime error) |
| `dynamic_requests = true` | needed for the filter block's nested requests; no effect on history values |
| not set: `margin_long`, `margin_short` | **v5 default 0: no margin simulation at all** (section 2.1, V15) |
| not set: `close_entries_rule` | FIFO; irrelevant (one trade at a time) |
| not set: `backtest_fill_limits_assumption` | 0: a limit order fills when price touches it (the take profit; the inverted entry) |
| not set: `use_bar_magnifier` | false = path 'tv'; path 'mag' (stage 3) = Bar Magnifier on |
| `overlay`, `max_labels_count`, `max_lines_count`, titles | drawing / buffers: ignored |

Symbol constants: `syminfo.mintick = 0.01`, `syminfo.pointvalue = 1`, both pairs. `pt = syminfo.mintick`.
`bar_index` = the row number in the data file; only differences of it are used, so window-relative indices
are fine. `time` = `t_open` (ms in Pine, s here); `strategy.opentrades.entry_time` / `entry_bar_index` = the
fill bar's time / index.

### 2.1 Pine v5, not v6: what differs and whether it matters here

| topic | v5 (this file) | v6 (the sibling files) | effect here |
|---|---|---|---|
| margin default (`margin_long`, `margin_short` not set) | 0 = margin logic off: no refused entry, no margin call | 100 % | **matters**: 10 BTC on 100,000 would be refused / margin-called under v6. Replica: no margin (V15); count `max_notional_x`, `neg_equity_bars` |
| trade limit | TradingView stops the strategy with an error after 9,000 trades (as remembered; v6 trims the oldest instead) | trims | TradingView cannot show a full 2-year report on BTC 1 / 5 / 15 or XAU 1 / 5 (probe: 85,682 / 22,468 / 8,241 / 16,658 / 4,374 default trades). Replica: no limit (section 11) |
| `bool` may be `na`; `and` / `or` evaluate both operands (no short-circuit) | yes | no / lazy | none: the strategy part has no `bool[1]`, no bool from `request.security`, no function with history or side effects inside an `and` / `or`. The filter block's only bool history (`fgfEnded[1]`) feeds the display-only "FGF ended" mark, and its first bar is excluded by `not barstate.isfirst` |
| a comparison with an `na` operand | false | false | same: a zone with `na` direction is not aligned; `burstPts` na on the first bar gives no candidate; `high >= position_avg_price + na` is false |
| `request.security` defaults | gaps_off, lookahead_off | same | none: every call passes both arguments (L1026-1038) |
| `strategy.exit` with a relative AND an absolute parameter of one kind | the absolute one is used | the one reached first | none: no call mixes them (the breakeven `XL2` passes `stop =` and no `loss =`; `trail_points` has no `trail_price` partner) |
| `dynamic_requests` default | false (set true here) | true | none on history |
| implicit number-to-bool casting, integer division | allowed / int result for const ints | removed / float | none in the trading logic (only display strings divide integers) |

The filter block runs under v5 here and under v6 in the file `fgf.py` was built from; its gates
(`fgfBuyOk`, `fgfSellOk`) use none of the constructs above in a way that differs, so `fgf.py` applies as is.

---------------------------------------------------------------------------------------------------

## 3. Inputs

### 3.1 SIGNAL inputs -> `prepare(pair, chart_tf, params)`

| Pine name (line) | default | used for |
|---|---|---|
| `spreadPoints` (310) | 25.0 | half spread `25 x 0.01 x 0.5 = 0.125` offsets `bid` / `ask`; `midPrice` (burst) and the entry prices. Kept in `P` (the entry price is computed in `simulate`) |
| `entryHoldBars` (312), `entryHoldMinFavPoints` (313), `holdFavAtrMult` (320) | 0, 5.0, 0.1 | the entry hold ("virtual stop"); 0 = off |
| `oneEntryPerBar` (314) | true | **inert** (L1122: `lastEntryBar` is only ever set to the current bar, after `canFire` was computed). Accept it; prove it in a self-check |
| `DistUnit` (317) | "ATR" | "ATR": burst / entry distance / hold thresholds in ATR(14) of the chart; "Points": the point inputs. It also selects the entry-distance unit used in `simulate` |
| `burstAtrMult` (318), `burstPointsInput` (321) | 0.5, 172.0 | burst threshold |
| `useBurstGate` (322) | true | read ONLY when `useAnyCombo` is on (L1104-1105) |
| `useAnyCombo` (323) | false | |
| `priorDriftBars` (324), `usePriorFilter` (325) | 60, false | prior drift filter (`priorDriftBars <= 500`, `strategy()`'s `max_bars_back`) |
| `useTdiTradeZone` (328) | true | the TDI trade-zone filter |
| `tdiParentTf` (329), `zoneTf1`, `zoneTf2`, `zoneTf3` (340-344) | "60", "60", "120", "240" | used only when `autoTf` is off |
| `tdiRsiLen` (330), `tdiFastLen` (331) | 14, 2 | the TDI direction |
| `minAlignedZones` (333) | 2 | `requiredAligned = min(minAlignedZones, activeZones)` |
| `allowNeutralParent` (334), `ignoreNaZones` (335), `htfNoRepaint` (336) | false, true, true | |
| `useZone1..6` (339-349), `zoneTf4..6` (346-350) | T, T, T, F, F, F; "480", "1", "2" | zones 5 / 6 are MINUTE timeframes "1" / "2" (not seconds), off |
| `autoTf` (351) | true | parent = chart; zones 1 / 2 / 3 = chart, `timeframe.from_seconds(2 x chart)`, `from_seconds(4 x chart)` (L354-358); the four inputs above are then ignored; zones 4-6 always use their inputs |
| `fgfOn` (413) | **true** | false: `fgfBuyOk = fgfSellOk = true` on every bar; do not call `fgf` then |
| every other trading input of the filter block (414-423, 437-474): `fgfTf`, `fgfLvMode`, `fgfLast`, `fgfMinutes`, `fgfBars`, `fgfCheck`, `fgfBandAtr`, `fgfAgainst`, `fgfAllowBuy`, `fgfAllowSell`, `fgfSpreadPts` ... `fgfZTf6` | `fgf.DEFAULTS` (all equal, checked) | passed unchanged to `fgf.fgf_permissions` (its own validation applies). They do not touch the strategy's signal |
| replica: `start`, `end` | the pair's window | window by `t_close`, as `hrd._window` |

### 3.2 ORDER / EXIT inputs -> `simulate(P, x)` (also accepted by `prepare` / `run` as defaults)

| Pine name (line) | default | used for |
|---|---|---|
| `entryDistAtrMult` (319), `entryDistPoints` (311) | 0.25, 50.0 | entry distance (ATR unit / Points unit, by `P`'s `DistUnit`). It changes no signal, only the order price, so it lives in `simulate` (section 4.5) |
| `Direction` (370) | "Both" | "Both" / "Long" / "Short": the REAL orders (section 8) |
| `entryValidBars` (371) | 3 | stale-order cancel; 0 = keep until filled |
| `allowReverse` (372) | true | an opposite signal may place its entry while a position is open |
| `exitOnOpposite` (373) | false | close at market on the opposite signal |
| `ExitMode` (376) | **"Pips"** | "Pips" / "ATR" / "Points" |
| `pipSize` (377) | 1.0 | price units per pip ("1 pip = $1 per BTC") |
| `slPips`, `tpRPips`, `runTrailPips`, `trailActPips`, `trailPips` (378-382) | 30, 5, 600, 150, 600 | Pips mode |
| `slPoints`, `tpPoints` (383-384) | 3900, 19500 | Points mode, ticks; 0 = none |
| `atrLen` (385) | 14 | `atrV = ta.atr(atrLen)` of the chart (stop and runner trail in ATR mode) |
| `slAtrMult`, `tpR` (386-387) | 0.1, 2.0 | ATR mode |
| `useTrail` (388) | false | trailing stop of the Fixed style only |
| `trailActPoints`, `trailPoints` (389-390) | 4500, 1000 | Points mode, Fixed style trail |
| `trailActAtr`, `trailDstAtr` (391-392) | 1.0, 0.25 | ATR mode, Fixed style trail, in **ATR(14)** (`atrPts`, L1182-1183), not ATR(`atrLen`) |
| `maxBarsHeld` (393) | 0 | time stop, bars; 0 = off |
| `TpStyle` (394) | "Partial + runner" | "Fixed" / "Partial + runner" |
| `partPct` (395) | 30 | % closed at the take profit; 100 = the Fixed branch |
| `runBE` (396) | true | runner stop to breakeven after the take-profit level |
| `runTrailAtr` (397), `runTrailPts` (398) | 1.5, 58000 | runner trail, ATR mode (ATR(`atrLen`)) / Points mode |
| `QtyMode`, `fixedQty`, `riskPct`, `maxQty`, `qtyStep` (401-405) | "Fixed", 10, 1.0, 50, 1 | `calcQty` (section 9) |
| `fgvInv` (990), alias `inv` | false | Update 1 (section 8). Raise if both are given and disagree |
| replica: `path` | 'tv' | 'tv'; 'mag' raises `NotImplementedError` until stage 3 |
| replica: `cost` | 'tv' | 'tv' / 'ours' / 'stress' (section 9) |

`simulate` raises if `x` holds a 3.1 key that differs from `P`'s (as `hrd.simulate`). Validate as the Pine
inputs do: option strings exactly as written (else `ValueError`); `pipSize >= 0.000001`, `slAtrMult >= 0.01`,
`runTrailPips >= 1`, `trailPips >= 1`, `trailPoints >= 1`, `trailDstAtr >= 0.005`, `runTrailAtr >= 0.05`,
`runTrailPts >= 1`, `atrLen >= 1`, `qtyStep >= 0.000001`, `0 <= partPct <= 100`, `entryValidBars` and
`maxBarsHeld` integers `>= 0`, every other number `>= 0`. Any unknown key: `ValueError`.

### 3.3 Accepted, no effect

`oneEntryPerBar` (inert, see 3.1), `tdiSlowLen` (331; the slow line is computed and returned but never read
by a decision), `useBurstGate` without `useAnyCombo`.

### 3.4 Drawing only: listed once, ignored (accepted, no effect)

`showEntryLabels`, `showEntryLines`, `showSideTags`, `priceTagOffsetBars`, `entryLineBars`,
`labelTimeZone`, `showZoneTable`, `fgfShowBg`, `fgfShowLv`, `fgfSigMark`, `fgfShowTbl`, `fgfTblPos`,
`fgsShow`, `fgsWin`, `fgsH`, `FGF_FORCE_OVERLAY`; every `plot`, `plotshape`, label, line and table; the
order comments (they become the exit kinds of section 12).

---------------------------------------------------------------------------------------------------

## 4. `prepare`: series, zones, signals, gates

Window rows of `$W/data/<PAIR>_<TF>.parquet`: `w0 = searchsorted(t_close, start, 'left')`, `w1 =
searchsorted(t_close, end, 'right')`, `n = w1 - w0`, window bar `j` = file row `w0 + j`. Every series below
is computed on the WHOLE chart file from row 0 (warm-up), then sliced to the window.

### 4.1 Chart series

```
pt = 0.01 ; half = spreadPoints * pt * 0.5
bid = close - half ; ask = close + half ; midPrice = (bid + ask) * 0.5        # float64, in exactly this order
atr14 = ta.atr(14) of the chart = fgf._atr(high, low, close, 14)            # atrChart, L1089
atrPts = atr14 / pt
```
`ta.atr(n)` = `ta.rma(ta.tr(true), n)` as `fgf._atr` computes it (tr[0] = high - low; seed = plain mean of
tr[0..n-1] at row n-1; na before). Keep an ATR cache per length for `simulate` (`atrLen`, from row 0).

### 4.2 The TDI zones (L1010-1078): timeframes and the request rule

Effective timeframes (L354-358): `parentTfEff = autoTf ? chart : tdiParentTf`; `zoneTf1Eff = autoTf ? chart
: zoneTf1`; `zoneTf2Eff = autoTf ? from_seconds(2 * chartSec) : zoneTf2`; `zoneTf3Eff = autoTf ?
from_seconds(4 * chartSec) : zoneTf3`; zones 4-6 always `zoneTf4..6`. On our charts `from_seconds` gives
minute strings: chart 1 -> "2", "4"; 5 -> "10", "20"; 15 -> "30", "60"; 30 -> "60", "120"; 60 -> "120",
"240"; 120 -> "240", "480"; 240 -> "480", "960".

Per timeframe T: `d_T = fgf._tdi_dir(close_T, tdiRsiLen, tdiFastLen)` on T's own bars, from T's first bar
(= `tdiDir()`'s `d`: `f > f[1] ? 1 : f < f[1] ? -1 : 0`, with RSI = Wilder, f = SMA of RSI; na comparisons
give 0; fgf's docstring). T's bars: `fgf._bars(pair, T)` (files for 1..240, D, W, M; other minute
timeframes built from the 1-minute file by `fgf._build_minutes`: XAU anchored at the 18:00 New York
session start and truncated at 17:00, BTC on the epoch grid) **except a BTC minute timeframe that does not
divide 1,440 minutes** (here only "960"): build it from the 1-minute file with a daily reset (V17):
```
day = (t_open_1m // 86400) * 86400 ; s = T_minutes * 60
o = day + ((t_open_1m - day) // s) * s ; c = minimum(o + s, day + 86400)     # bar keys; t_close = c
open = first, high = max, low = min, close = last of each key (1-minute rows in time order)
```
(probe_960: 10,847 such "960" bars against fgf's 8,140 epoch-grid bars.) Seconds timeframes ("30S") have
no data: their direction is na on every bar (fgf returns None for them).

Mapping onto the chart bars (SPEC_AH request rule, the same as fgf's `_zone_dir` with the chart as context):
```
lookahead_off  (parentDir, zDir0):  value of the last T bar with t_close <= chart t_close    fgf._map_off + fgf._take
lookahead_on + [1]  (zDirP):        the T bar containing the chart bar's open, minus one      fgf._map_on_prev + fgf._take
isHigher(T) = timeframe.in_seconds(T) > timeframe.in_seconds(chart)       (fgf.tf_seconds)
zDir = (htfNoRepaint and isHigher(T)) ? zDirP : zDir0                     # zones 1-6; the parent is always lookahead_off
```
On the chart's own timeframe both rules return the chart bar's own value. `_take` gives na where no T bar
exists yet. With "Auto timeframes" zone 1 IS the parent (same request), so it is always aligned when the
parent is not flat: `minAlignedZones` 0 and 1 are the same setting, 2 = the parent plus one of 2x / 4x, 3 =
all three (the header says so for 1, L159-160).

Counts (L1047-1078), per chart bar:
```
on_k   = useZone_k and (not ignoreNaZones or not na(zDir_k))
activeZones  = sum(on_k)
parentSide   = parentDir > 0 ? 1 : parentDir < 0 ? -1 : 0          # na parent -> 0
alignedZones = sum(on_k and parentSide != 0 and zDir_k == parentSide)  # na zDir never equal
requiredAligned   = min(minAlignedZones, activeZones)
parentFlatAllowed = allowNeutralParent and parentSide == 0
zoneReady         = activeZones == 0 or alignedZones >= requiredAligned
tzBuy  = not useTdiTradeZone or ((parentSide ==  1 or parentFlatAllowed) and zoneReady)
tzSell = not useTdiTradeZone or ((parentSide == -1 or parentFlatAllowed) and zoneReady)
```

### 4.3 Burst, candidates, entry hold (L1088-1165): `fgf._signal_arm`

The rest of the signal is `fgf._signal_arm` verbatim (identity: fact 1). Call it on the chart file from
row 0:
```
bs, ss, _px, *_ = fgf._signal_arm(close, t_close, atr14, tzBuy, tzSell, parentSide, 0.01,
    float(spreadPoints), DistUnit == "ATR", float(burstAtrMult), 0.25, float(holdFavAtrMult),
    float(burstPointsInput), 50.0, float(entryHoldMinFavPoints),
    bool(useBurstGate), bool(useAnyCombo), int(priorDriftBars), bool(usePriorFilter),
    int(entryHoldBars), bool(oneEntryPerBar), True)
```
(`close`, `t_close`, `atr14` of the whole chart file; `tzBuy` / `tzSell` bool arrays, `parentSide` int64, as
`fgf._filter_series` passes them.) `bs` / `ss` = `buySignal` / `sellSignal`. The two entry-distance
arguments (0.25, 50.0) do not change `bs` / `ss` (they only set `_px` and the filter's arm, which this
strategy does not use; its own entry distance is applied in `simulate`, 4.5). The kernel is, line for line:
`burstPts = (mid - mid[1]) / pt`, `priorDriftPts = (mid - mid[priorDriftBars]) / pt` (na at the start of
the file), `burstBuy = burstPts >= burstThrPts`, `burstSell = burstPts <= -burstThrPts`, the candidate
formulas of L1104-1108 (`useBurstGate` only inside the `useAnyCombo` branch), and the hold block of
L1111-1165 with `var` state from row 0. A builder may also write this part from the Pine; then assert
equality with `fgf._signal_arm` on every cell.

Cross-check that both builders must run: on every chart except BTC "240" (the only one with a non-divisor
timeframe), the arrays equal `fgf._filter_series(pair, chart_tf, fgf._params(mapped))['buy' / 'sell']` with
the mapping `fgfParentTf = parentTfEff`, `fgfZTf1..3 = zoneTf1..3Eff`, `fgfZTf4..6 = zoneTf4..6`,
`fgfUseZ* = useZone*`, `fgfRsiLen = tdiRsiLen`, `fgfFastLen = tdiFastLen`, `fgfMinAligned =
minAlignedZones`, `fgfFlatParent = allowNeutralParent`, `fgfIgnoreNa = ignoreNaZones`, `fgfHtfClosed =
htfNoRepaint`, `fgfUseZones = useTdiTradeZone`, `fgfSpreadPts = spreadPoints`, `fgfHoldBars =
entryHoldBars`, `fgfHoldFavPts = entryHoldMinFavPoints`, `fgfOnePerBar = oneEntryPerBar`, `fgfDistUnit =
DistUnit`, `fgfBurstAtr = burstAtrMult`, `fgfHoldFavAtr = holdFavAtrMult`, `fgfBurstPts = burstPointsInput`,
`fgfUseBurst = useBurstGate`, `fgfAnyCombo = useAnyCombo`, `fgfDriftBars = priorDriftBars`, `fgfUseDrift =
usePriorFilter`. And on chart "60" with default inputs they equal the filter's own signals
(`fgf.filter_signals(pair, "60")`). Do not use `_filter_series` as the production path: its cache key and bar
source are the filter's, and it builds BTC "960" on the epoch grid.

### 4.4 The filter gate

`fgfOn` true: `F = fgf.fgf_permissions(pair, chart_tf, start, end, fgf_params)` with `fgf_params` = the keys
of `params` that are in `fgf.DEFAULTS`; assert `F.index[0] == w0` and `len(F) == n`; `buyOk =
F.buyOk.values`, `sellOk = F.sellOk.values`. `fgfOn` false: both all True. The filter call does not depend
on any strategy input: cache it per (pair, chart, filter params).

### 4.5 Entry prices (computed in `simulate`; the arrays they need are in `P`)

```
entryDistPts = DistUnit == "ATR" ? entryDistAtrMult * atrPts : entryDistPoints       # atrPts = atr14 / pt
buyEntryPrice  = ask + entryDistPts * pt          # only on buySignal bars, else na
sellEntryPrice = bid - entryDistPts * pt          # only on sellSignal bars, else na
```
In exactly this operation order (float64). Prices are not on the tick grid (half spread 0.125, ATR
distance); they are used as they are (V16). na (ATR warm-up) places nothing (L1234 `not na(...)`).

### 4.6 What `P` holds; reference counts

`pair`, `tf`, `start`, `end`, `mid = start + (end - start) // 2`, `mid_j = searchsorted(t_close_window, mid,
'right') - 1`, `w0`, `w1`, `n`, window arrays `open high low close t_open t_close`, `buySig`, `sellSig`,
`ask`, `bid`, `atr14` (window), `buyOk`, `sellOk`, an ATR cache per length (window slice of the series from
row 0), `DistUnit`, the resolved 3.1 parameters, signal counts. Nothing in `P` may depend on a 3.2 input.
Cache the chart bars, the zone directions per (pair, T, rsi, fast) and the filter call; `fgf` caches its own.

Default inputs, full windows (probe_sig; BTC 240 with the daily-reset "960", V17; with fgf's epoch grid it
would be 447 / 463 and 107 / 103):

| cell | bars | `buySignal` / `sellSignal` | of them `fgfBuyOk` / `fgfSellOk` | median ATR(14) | $30 in ATR |
|---|---|---|---|---|---|
| BTC 1 | 1,039,430 | 157,774 / 158,903 | 73,828 / 70,563 | 38.2 | 0.79 |
| BTC 5 | 210,155 | 27,642 / 28,561 | 15,685 / 15,560 | 113.7 | 0.26 |
| BTC 15 | 70,058 | 8,496 / 8,605 | 5,049 / 5,000 | 226.2 | 0.13 |
| BTC 30 | 35,032 | 3,966 / 4,041 | 2,040 / 2,026 | 336.5 | 0.09 |
| BTC 60 | 17,518 | 1,882 / 1,918 | **0 / 0** | 495.8 | 0.06 |
| BTC 120 | 8,760 | 881 / 918 | 150 / 162 | 723.9 | 0.04 |
| BTC 240 | 4,381 | 429 / 468 | 105 / 101 | 1,053.9 | 0.03 |
| XAU 1 | 493,819 | 62,608 / 62,409 | 27,822 / 28,416 | 0.237 | 126 |
| XAU 5 | 98,787 | 11,229 / 11,111 | 6,147 / 6,157 | 0.592 | 51 |
| XAU 15 | 32,935 | 3,472 / 3,457 | 1,996 / 2,065 | 1.102 | 27 |
| XAU 30 | 16,471 | 1,662 / 1,701 | 823 / 871 | 1.639 | 18 |
| XAU 60 | 8,238 | 851 / 847 | **0 / 0** | 2.387 | 12.6 |
| XAU 120 | 4,493 | 481 / 470 | 70 / 88 | 3.256 | 9.2 |
| XAU 240 | 2,246 | 240 / 232 | 34 / 39 | 4.748 | 6.3 |

Never both signals on one bar at the defaults (0 bars in every cell): `burstThrPts > 0` makes `burstBuy` and
`burstSell` exclusive, and the zone filter needs `parentSide` 1 vs -1. Both are possible with a zero
threshold, `useAnyCombo`, the zone filter off or a flat parent allowed: implement them (section 7).

---------------------------------------------------------------------------------------------------

## 5. How TradingView runs this script on history

History bars: the script runs once per bar at its close (`calc_on_every_tick` and `calc_on_order_fills`
false); orders of that run are processed from the next bar on. Per window bar `j`:

    A. the open of j:  market closes of the run of j-1, then gap tests of the open trade's exits and of the pending entries
    B. the bar's path: the open trade's exit orders and the pending entry orders, in the order price reaches them
    C. the script run at the close of j, on the position and equity left by A and B (section 7)
    D. the bar-close equity point

What lives between runs: up to two pending ENTRY orders (one per id, "Long" and "Short", OCA group "FG"),
the exit orders of both ids (re-sent every run, in force from the next bar), and at most one market close.
Same-bar exit: yes (an exit is live from its entry's fill, also on the rest of that leg). Same-bar re-entry:
yes, by a pending order that was already live when the previous trade closed (a stop loss and then the
reversal stop further down the same leg); never by a new decision (decisions are at the close).

Live-only code, dead on history: `barstate.islast` tables, `timenow`, the filter's live branches (inside
`fgf.py`). Nothing in the strategy part depends on `barstate`.

---------------------------------------------------------------------------------------------------

## 6. The broker inside a bar (path 'tv')

### 6.1 Orders the script can place (all of them)

| call (lines) | type | replica |
|---|---|---|
| `strategy.entry("Long", strategy.long, qty = qL, stop = buyEntryPrice, oca_name = "FG", oca_type = strategy.oca.cancel, comment = "FG buy stop")` (1249) | buy STOP, normal BUY signal | slot `+1`: `{typ stop, P, qty, seq}` |
| `strategy.entry("Short", strategy.short, qty = qS, stop = sellEntryPrice, ...)` (1271) | sell STOP, normal SELL signal | slot `-1` |
| `strategy.entry("Short", strategy.short, qty = qL, limit = buyEntryPrice, ...)` (1241) | sell LIMIT, inverted BUY signal | slot `-1`: `{typ limit, ...}` |
| `strategy.entry("Long", strategy.long, qty = qS, limit = sellEntryPrice, ...)` (1263) | buy LIMIT, inverted SELL signal | slot `+1` |
| `strategy.cancel("Long" / "Short")` (1292 / 1295) | removes that id's pending entry | empties the slot |
| `strategy.exit("XL1" / "XS1", qty_percent = partPct, loss, profit)` (1323-1324) | partial exit of the Partial style | exit params of the id |
| `strategy.exit("XL2" / "XS2", qty_percent = 100, loss or stop, trail_points = tpX, trail_offset = lockRunX)` (1327-1333) | runner of the Partial style | exit params of the id |
| `strategy.exit("XL" / "XS", loss, profit[, trail_points = lockActX, trail_offset = lockDstX])` (1336-1340) | Fixed style (or `partPct` 100) | exit params of the id |
| `strategy.close("Long" / "Short", comment = "opp signal")` (1225 / 1227) | market close at the next open | `close_req = 'opp'` |
| `strategy.close_all(comment = "time stop")` (1346) | market close at the next open | `close_req = 'time'` (if none set) |

Ids: "Long" is always a real buy, "Short" a real sell (also inverted). One slot per id: a new
`strategy.entry` with the id of a pending order replaces its type, price and quantity (V8 / G7 of
SPEC_gvl), and the placing bar restarts its lifetime. A pending order is always on the side opposite to an
open position, or the position is flat (an entry is placed only when the position is not on its side, and
the fill empties the slot): assert it. So a pending order that fills while a position is open is a REVERSAL.

Trigger and fill (V2, V12): a buy stop and a sell limit at `P` both trigger when price `>= P`; a sell stop
and a buy limit when price `<= P`. Fill at `P`, or at the open when the bar opens at or beyond `P`. Booked
fill price = that raw price `+ d x slip` for a stop entry of real side `d` (`slip` = 0.05 with cost 'tv',
else 0), the raw price for a limit entry. `trig = +1` for slot +1 normal / slot -1 inverted, i.e. `trig =
sig`, the normal-frame side of the signal.

### 6.2 A trade's exit orders, fixed at its fill (real side `d`, booked fill `e`, quantity `Q`)

The ticks come from the id's LOCKS (written when its entry order was last placed, section 7 C3): `slT =
lockSl`, `tpT = lockTp`, `actT = lockAct`, `dstT = lockDst`, `runT = lockRun` (na stays na; `slT`, `tpT`
"exist" only if > 0, L1299-1302).
```
SL = e - d * slT * pt          exists if slT > 0
TP = e + d * tpT * pt          exists if tpT > 0
Partial style (TpStyle == "Partial + runner" and partPct < 100):
   XL1 (only if partPct > 0): quantity q1 = Q * partPct / 100 (exact, V6); stop SL; limit TP
   XL2: quantity q2 = Q - q1; stop = SL (loss mode) ; trailing: exists if tpT > 0 and runT not na:
        activation A = TP level, offset off = runT * pt ; armed = False ; best = e
   breakeven mode (from the bar after the close where tpHit was set, section 7 C5): XL2's stop = BE = the
        position_avg_price sent at that close (= e); the trailing state is kept (V5)
Fixed style (else):
   XL: quantity Q; stop SL; limit TP; trailing if useTrail and actT, dstT not na:
        A = e + d * actT * pt, off = dstT * pt (dstT >= 1 tick by L1183); armed = (actT <= 0), best = e
```
Stop in force of an exit order with a trailing part (long; short with `min`, inequalities turned): `S* =
max(own stop, best - off if armed)`; a missing level does not take part. It is the trailing stop that fills
(kind 'runner' / 'trail') if `best - off >= own stop` or there is no own stop, else the own stop ('sl', or
'be' in breakeven mode). XL1 has no trailing part: its stop is SL.

Before breakeven the two orders share one stop level `SL` and the trail cannot be above `SL` before the
take-profit level has been reached (A = TP and the trail only rises from there); after the take profit XL1 is
gone. So in every normal case the stop event closes the whole position at once; the two orders stop at
DIFFERENT levels only in the inverted breakeven case of section 8 (`be_no_tp`).

### 6.3 One bar `j`

**A. The open `o`.**
- A1. `close_req` set and a position open: close the whole remaining position at `o - pos x slip` (market,
  kind = `close_req`). Clear `close_req` (also when flat: a close of nothing is dropped).
- A2. (no market entry exists in this script)
- A3. The trade that was open before this bar, gap test of its exit orders at `o` (long; short mirrored:
  `>=` for stops, `<=` for the target, `+ slip`):
  - Partial style: every open exit order whose stop is at or above `o` (XL1: `o <= SL`; XL2: `o <= S*`)
    fills at `o - slip`; if both do, it is one joint fill (kind = XL2's). Then, if XL1 is still open, `TP`
    exists and `o >= TP`: XL1 fills at `o` ('tp_part'). Then XL2's trailing part, if XL2 is still open: if
    armed `best = max(best, o)`, elif `o >= A`: `armed = True, best = o`.
  - Fixed style (one order XL): `o <= S*` -> the whole trade at `o - slip` ('sl' / 'trail'); elif `TP`
    exists and `o >= TP` -> at `o` ('tp'); else the trailing update with `o` as above.
- A4. Pending entries crossed at the open (trigger as 6.1), the earlier placement first (`seq`; on one bar
  the BUY signal's order was placed first): fill at `o` (6.1 booking), a reversal if a position is open
  (close it at the same booked price, kind 'reverse'), OCA-cancel the other slot (V8); then the new trade's
  exits are tested at `o` as in A3 (V11). The second order, if it was crossed too, is gone (OCA).

**B. The path** (SPEC_AH rule 4: `v1, v2 = high, low` if `(high - o) < (o - low)` else `low, high`; legs `o ->
v1`, `v1 -> v2`, `v2 -> close`; skip a leg of length 0). On a leg from `cur` to `b`, loop:
```
UP leg (b > cur), candidates (raw prices):                 DOWN leg (b < cur):
  long open:  XL1 TP (or XL TP) exists, b >= TP  -> max(TP, cur)      short open: TP, b <= TP -> min(TP, cur)
  short open: XS1 stop SL,  b >= SL  -> max(SL, cur)                 long open:  XL1 SL,  b <= SL -> min(SL, cur)
              XS2/XS stop S*, b >= S* -> max(S*, cur)                            XL2/XL S*, b <= S* -> min(S*, cur)
  pending trig +1 order, b >= P     -> max(P, cur)                  pending trig -1 order, b <= P -> min(P, cur)
take the candidate reached FIRST (UP: the lowest price; DOWN: the highest).
Ties: exit orders before entry orders (V4); XL1 and XL2 stops at the same price = ONE joint fill.
Before acting, update the trailing part of the open trade with that price if the leg is favourable to it
(armed: best = better(best, price); not armed and price reached A: armed, best = price).
  exit   -> stop fills booked at price - d*slip, limit fills at price; the order's quantity leaves;
            the trade ends when nothing is left; cur = price; loop on the rest of the leg
  entry  -> 6.1 booking; reversal if a position is open (whole remainder closed at the booked price, 'reverse');
            OCA-cancel the other slot; the new trade's exits (6.2) are live at once; test them at the raw
            price (V11); cur = price; loop on the rest of the leg
no candidate -> if the leg is favourable to the open trade: trailing update with b. Leg done.
```
`S*` is fixed along an adverse leg (the trail does not move on it). On a favourable leg the take profit is
tested before the trail arms; for the runner the activation level IS the take-profit level, so XL1's limit
fills and XL2 arms at the same price. For one trade and no pending order, A3 + B is the logic of `hrd._walk`
(long space: negate a short's prices) extended to two exit orders with their own quantities.

**Worked checks** (BTC-like numbers, default Pips exits, cost 'tv', `Q = 10`):
- Normal entry and the runner. Bar j: BUY signal, close 90,000.00, ATR(14) 500.00: `ask` 90,000.125,
  distance 0.25 x 50,000 = 12,500 ticks, `buyEntryPrice` 90,125.125; locks `sl` 3,000, `tp` 15,000, `run`
  60,000 ticks. Bar j+1 O 90,050 H 90,400 L 89,990 C 90,100: `(H-O) = 350 < (O-L) = 60` is false -> path
  O-L-H-C. The rise L -> H crosses 90,125.125: long 10 at 90,125.175 (`e`, slipped); `SL` 90,095.175, `TP` =
  `A` 90,275.175; the same rise reaches `TP`: XL1 3 BTC at 90,275.175 ('tp_part', no slippage), XL2 arms,
  `best` 90,400; the fall to 90,100 stays above `S* = max(90,095.175, 89,800)`. Close of j+1: `high >=
  position_avg_price + 150` -> `tpHitL`. Bar j+2 opens 90,080 <= BE 90,125.175: XL2 7 BTC at 90,079.95
  ('be'). Trade: `pnl_gross` +133.425, commission 180.250 + 54.165 + 126.112, `pnl` -227.102; `exit_px`
  (qty-weighted) 90,138.5175; `part_kind` 'tp_part'; `exit_kind` 'be'.
- The same BUY signal inverted: sell LIMIT 90,125.125 ("Short", S locks). Bar j+1: the rise fills it at
  90,125.125 (no slippage); `SL` 90,155.125, `TP` 89,975.125; the same rise to 90,400 reaches `SL`: XS1 and
  XS2 jointly at 90,155.175 ('sl', same bar). `pnl` -300.50 - 360.56 = -661.06.
- Gap: the buy stop at 90,125.125, next bar opens 90,200.00: fill at 90,200.05 (A4); levels from 90,200.05.
- Stale order: placed at the close of bar b, not filled, `entryValidBars` 3: live on bars b+1, b+2, b+3,
  cancelled at the close of b+3 (if the position is not on its side then).

**Window.** Flat, empty slots, no `close_req`, clean `var`s (locks na, `placedBar*` na, `tpHit*` false,
`tradeId*` na) at the first window bar; its run is the first decision, so the first possible fill is on the
second window bar. On the last window bar A-D run; then an open position is closed at the last close as a
market fill (`close - pos x slip`, exit cost charged), kind 'end', `exit_time = t_close`; pending orders and a
`close_req` placed there are dropped (`orders_unfilled_end` = 1 if any slot is non-empty at the end).

**Path 'mag' (stage 3; keep A3, A4 and B in one function so that it can be swapped).** A1 stays on the
chart bar's open. Then every 1-minute sub-bar of the chart bar (rows of `<PAIR>_1` with `t_open` in
`[t_open[j], t_close[j])`, `hrd.sub_bars`), in time order: A3 and A4 at its own open, then B on its own
open / high / low / close. Pending entries, OCA, trailing state and the partial state carry over. C and D
stay on the chart bar's close; the breakeven flag (C5) reads the CHART bar's high / low. Chart "1": 'mag' ==
'tv'.

---------------------------------------------------------------------------------------------------

## 7. The script run at the close of bar `j` (step C), in the Pine's order

State it reads: the position after A and B (`pos` in 0 / +1 / -1 = sign of `strategy.position_size`, the
remaining quantity, `e`, the fill bar `ebar`, a trade id), `cash`, its `var`s (`lockSl/Tp/Act/Dst/Run` per
id, `placedBarL/S`, `tradeIdL/S`, `tpHitL/S`), and the slots. `c = close[j]`, `equity = cash + pos x
remaining_qty x (c - e)` (`strategy.equity`, V14).

**C1. Exit geometry (L1168-1184), from this bar** (float64, in this order):
```
atrV = ta.atr(atrLen)[j] ; atrPts = atr14[j] / pt ; pipTicks = pipSize / pt
slTicksNow  = Points: slPoints     | Pips: slPips * pipTicks          | ATR: na(atrV) ? na : slAtrMult * atrV / pt
tpTicksNow  = Points: tpPoints     | else: na(slTicksNow) ? na : slTicksNow * (Pips ? tpRPips : tpR)
trailActNow = Points: trailActPoints | Pips: trailActPips * pipTicks   | ATR: trailActAtr * atrPts
trailDstNow = Points: trailPoints  | Pips: max(trailPips * pipTicks, 1.0) | ATR: max(trailDstAtr * atrPts, 1.0)
runDstNow   = Points: runTrailPts  | Pips: max(runTrailPips * pipTicks, 1.0) | ATR: max(runTrailAtr * atrV / pt, 1.0)
```
(`math.max(na, 1.0)` is na. In Points mode `tpTicksNow` ignores the stop. The ATR-mode Fixed-style trail uses
ATR(14), the stop and the runner ATR(`atrLen`).)

**C2. Positions and gates (L1212-1218).**
```
allowL = inv ? Direction != "Long"  : Direction != "Short"       # may a BUY signal place its order
allowS = inv ? Direction != "Short" : Direction != "Long"
inLong = pos > 0 ; inShort = pos < 0 ; flat = pos == 0           # REAL position after A and B
NL = inv ? inShort : inLong ; NS = inv ? inLong : inShort         # fgvNL / fgvNS: the mirrored reads
```
**C3. Opposite close, then the two entry blocks, in this order (L1224-1272).**
```
if exitOnOpposite and sellSignal[j] and NL:  close_req = 'opp'        # the real open trade (id inv ? "Short" : "Long")
if exitOnOpposite and buySignal[j]  and NS:  close_req = 'opp'
gate = flat or allowReverse or exitOnOpposite                         # flat as read in C2 (the close is only pending)
BUY:  if buySignal[j] and allowL and not NL and gate and buyOk[j]:
          q = calcQty(slTicksNow)                                      # section 9: this equity, this bar
          if q > 0 and not na(buyEntryPrice[j]):
              s = inv ? -1 : +1                                        # the real side / id
              lock[s] = (slTicksNow, tpTicksNow, trailActNow, trailDstNow, runDstNow)
              slot[s] = {typ: inv ? limit : stop, P: buyEntryPrice[j], qty: q, seq: next}   # replaces a pending one
              placedBar[s] = j
          else: zero_qty += 1
SELL: the same with sellSignal, allowS, NS, sellOk, sellEntryPrice; s = inv ? +1 : -1
```
The SELL block reads the same `flat`, `NL`, `NS` as the BUY block (series values computed before both).
`exitOnOpposite` closes whatever the filter or `Direction` says about the opposite signal: the close is not
gated, only the new entry is. With `exitOnOpposite` on and `allowReverse` off the entry is still placed (the
close fills first at the next open, V22).

**C4. Funnel (L1276-1279), normal frame:** `rawL = buySignal and allowL and not NL and gate`; `rawS` alike;
`raw_long += rawL`, `blocked_long += rawL and not buyOk`; short alike. (`zero_qty` above counts allowed
signals whose quantity is 0 or whose price is na.)

**C5. Stale cancel (L1290-1296), then the breakeven flag (L1299-1318).**
```
if entryValidBars > 0:
    if placedBarL not na and not inLong  and j - placedBarL >= entryValidBars: empty slot +1 ; placedBarL = na
    if placedBarS not na and not inShort and j - placedBarS >= entryValidBars: empty slot -1 ; placedBarS = na
tpL = lock[+1].tp > 0 ? lock[+1].tp : na ; tpS likewise                # after C3 (it may have rewritten a lock)
cur = the open trade's id (na if flat)                                  # curEntryTime; a trade counter is equivalent
if not inLong  or na(tradeIdL) or cur != tradeIdL:  tpHitL = False ; tradeIdL = inLong  ? cur : na
if not inShort or na(tradeIdS) or cur != tradeIdS:  tpHitS = False ; tradeIdS = inShort ? cur : na
if inLong  and tpL not na and high[j] >= e + tpL * pt:  tpHitL = True   # the WHOLE bar's high (V18)
if inShort and tpS not na and low[j]  <= e - tpS * pt:  tpHitS = True
```
`placedBar*` is NOT reset by a fill: the test is skipped while the position is on that id's side and fires
(a no-op cancel) once it is not. A cancel of an empty slot does nothing.

**C6. Exits re-sent (L1320-1340)**, in force from bar j+1, for BOTH ids, whatever the position: the Partial
or Fixed structure of 6.2 with the id's current locks; XL2 / XS2 in breakeven mode iff `runBE and tpHitX`,
with `stop = strategy.position_avg_price` (= `e` of the trade open now; tpHitX implies that trade is on side
X). A new trade therefore always starts in loss mode (assert it at every fill). Re-sending changes nothing
else (V5).

**C7. Time stop (L1343-1346):** `if maxBarsHeld > 0 and pos != 0: if j - ebar >= maxBarsHeld: close_req =
close_req or 'time'`. A trade filled during bar k gets its close order at the close of bar k + maxBarsHeld
and leaves at the open of the next bar.

**D.** Bar-close equity `E[j] = cash + pos x remaining_qty x (c - e)`; exposure counts bars with `pos != 0`
after C.

To keep exactly:
- The ticks and the quantity are those of the PLACING bar (its ATR, its equity); the fill is later, at
  another price; every exit is measured from the booked fill.
- A signal on the side already held does nothing (no order, no new locks, no lifetime renewal).
- With `allowReverse` and `exitOnOpposite` both off no reversal can happen: an opposite signal is ignored
  while in a position, an order of one id is placed only while flat, and a position opened afterwards came
  from the other id of the same OCA group, whose fill cancelled it. Assert `exit_reverse == 0` then.
- Both signals on one bar: the BUY block runs first; both slots may end up pending (OCA).

---------------------------------------------------------------------------------------------------

## 8. Update 1 ("Inverted direction", `fgvInv`), line by line

| Pine | effect | replica |
|---|---|---|
| L990 | the input, declared after the filter block | `fgvInv` / `inv` |
| L1212-1213 `allowL = fgvInv ? Direction != "Long" : Direction != "Short"` (and `allowS`) | `Direction` restricts the REAL orders: inverted, a BUY signal (a sell order) needs `Direction != "Long"` | C2 |
| L1217-1218 `fgvNL = fgvInv ? inShort : inLong` (and `fgvNS`) | decisions read the mirrored position: inverted, the trade a BUY signal opened is the real short | C2 |
| L1224-1227 | opposite close on the mirrored read; id = the trade really open | C3 |
| L1232, L1254 | entry conditions with `fgvNL` / `fgvNS`; the gate is the SIGNAL's (`fgfBuyOk` for a BUY signal) | C3 |
| L1235-1242, L1257-1264 | inverted: the BUY signal writes the S locks and places "Short" as a sell LIMIT at `buyEntryPrice`, `placedBarS`; the SELL signal the L locks and "Long" as a buy LIMIT at `sellEntryPrice` | C3, 6.1 |
| L1243-1250, L1265-1272 | `else` branch: the previous version, verbatim | |
| L1276-1277 | FGD funnel in the normal frame | C4 |
| unchanged: L1290-1296 cancel, L1299-1340 locks / breakeven / exits, L1343-1346 time stop, `calcQty` | keyed by id ("Long" = real buy), they work on the real trade: a sell has its stop above, its target below, its runner trailing below | 6.2, C5-C7 |

How the exits are "mirrored": the Pine mirrors no price. `loss`, `profit`, `trail_points`, `trail_offset`
are side-agnostic tick distances applied to the real fill; the breakeven stop is the real fill. Because the
normal stop and the inverted limit at the same `P` fill at the same raw price at the same moment (V2), the
inverted exits equal INVERT_SPEC's M3 mirror about `R` = the fill price, up to the 'tv' slippage the stop
entry pays and the limit entry does not. M2's STOP -> LIMIT swap is literal (L1241, L1263).

**The one literal asymmetry (`be_no_tp`).** The breakeven flag (L1315-1318) tests the whole bar's high /
low. A normal stop entry fills when price first reaches `P`, so the bar's favourable extreme always comes at
or after the fill, and `tpHit` is set only on a bar where XL1's limit really filled (probe: 0 cases in every
normal run). An inverted limit fills on the ADVERSE move, so the bar's favourable extreme may come BEFORE the
fill: `tpHit` is then set at the close of the fill bar although XL1 did not fill and the trail never armed.
From the next bar XL2 (the 70 %) sits at breakeven while XL1 (30 %) keeps `SL` / `TP`. Example (ATR mode, SL
1 x ATR 500, TP 1.5 R): SELL signal, close 90,000 -> inverted buy LIMIT at 89,874.875; next bar O 90,700 H
90,900 L 89,800 C 89,850 (path O-H-L-C, 200 < 900): the fall fills the long at 89,874.875 (`SL` 89,374.875,
`TP` 90,624.875); at the close `high 90,900 >= 90,624.875` -> `tpHitL`; the next bar opens 89,860: XL2 7
units at 89,859.95 ('be', a part), XL1 3 units stay. Count `be_no_tp` (trades whose XL2 entered breakeven
mode while XL1 was still open, or with `partPct` 0 while the trail was not armed). Probe: 63 inverted trades
on BTC 60 (filter off), 203 on BTC 15, 331 on BTC 5.

There is no other reverse option and no pre-filter flip. "Opposite signal may reverse an open position" is
about an open trade; `Direction` is a side restriction. The filter's "Allow buys / Allow sells" stay in the
normal frame (inside `fgf`).

Properties (stage 2 self-checks, stage 3 tests):
- P1, exact mirror. Fixed style with a symmetric bracket (`TpStyle` "Fixed", `useTrail` false, `tpR = 1` in
  ATR mode, or `tpRPips = 1`, or `tpPoints == slPoints`), `QtyMode` "Fixed", `Direction` "Both", cost
  **'ours'** (no slippage), any `allowReverse`, `exitOnOpposite`, `entryValidBars`, `maxBarsHeld`, filter on
  or off: `inv` True gives the trade list of `inv` False with `dir` negated, `sig` equal, `pnl_gross` negated,
  'sl' <-> 'tp' swapped, and every bar, entry / exit price, quantity and other kind equal (costs equal; `pnl`
  = `-pnl_gross - costs`). Not with 'tv' (the stop entry's slippage) and not with the Partial style (the
  breakeven flag).
- P2, single decisions: from the same state with the position negated, the order placed with `inv` True is
  the order placed with `inv` False on the other side: same bar, same `P`, same `trig`, STOP <-> LIMIT, same
  quantity, same five lock values on the other id; a filter-blocked or `Direction`-blocked decision is
  blocked in both (with `Direction` swapped).
- P3: the first trade of a run has the same entry bar and entry price (up to the 'tv' slippage) with `inv`
  False and True, opposite `dir`.
- P4: `Direction` "Long": every trade `dir = +1`; normal: every `sig = +1`; inverted: every `sig = -1`.
- P5: on chart "60" with default inputs and the filter on: zero trades in both directions (header L236-247).
- P6: `fgfOn` False equals `fgfOn` True with all-True permissions injected; with `inv` False it is the
  unfused original's logic.

---------------------------------------------------------------------------------------------------

## 9. Sizing, money, costs, margin

`calcQty(slTicks)` (L1188-1196), in this order, float64:
```
q = fixedQty
if QtyMode == "Risk %":
    riskCash = equity * riskPct / 100.0                      # strategy.equity of the placing bar (V14)
    stopCash = slTicks * pt * pointvalue                     # na -> the comparison below is false
    q = riskCash / stopCash  if stopCash > 0  else 0.0
q = min(q, maxQty)
q = floor(q / qtyStep + 1e-9) * qtyStep                      # qtyStep >= 0.000001 (minval)
```
The quantity is fixed at placement (a pending order keeps it until filled, replaced or cancelled). With the
defaults every order is 10 units. With "Risk %" and the default `qtyStep` 1 a stop wider than 1 % of equity
per unit gives `q = 0` (BTC 240, 2 ATR stop: 0.47 -> 0): `zero_qty`.

What the defaults do: BTC 10 coins, notional about 880,000 = 8.8 accounts, R = 10 x $30 = $300 (0.3 %); XAU
10 oz, notional about 12,800 = 0.13 accounts, R = $300. Fixed contracts do not compound.

Money model:
- `cash` starts at 100,000. Cost of a fill = `qty x (fixed + fraction x booked_px)`, charged when the fill
  happens (entry; every exit fill; a reversal = the closing fill + the opening fill at one price):
  'tv' `(0, 0.0002)` both pairs, plus `slip` = 0.05 inside the booked price of stop and market fills;
  'ours' XAU `(0.15, 0)`, BTC `(0.10, 0.0002)`, no slippage; 'stress' XAU `(0.26, 0)`, BTC `(0.11, 0.00035)`,
  no slippage (= `hrd.COSTS`).
- `pnl_gross = dir x sum(part_qty x (part_px - entry_px))`; `pnl = pnl_gross - entry cost - exit costs`.
- `eq_before` of a trade = `cash` just before its entry fill (after the closing leg of a reversal, before
  its own entry cost).
- R: `sl_dist = lockSl x pt` of the order (NaN without a stop); `r_mult = pnl / (sl_dist x qty)`.
- `slippage_paid` = sum of `0.05 x qty` over slipped fills ('tv').

What 'tv' costs mean (window medians; default Pips stop $30): BTC commission 0.0002 x 88,161 = $17.6 per coin
per fill: a round trip is $35.3 + $0.10 slippage = **1.18 R**; 'ours' $35.5 = 1.18 R. XAU: $0.256 per oz per
fill, round trip $0.61 with slippage = 0.02 R ('ours' $0.30 = 0.01 R). The default BTC strategy cannot cover
its costs unless the 'tv' path books most trades inside their entry bar (fact 5).

**Margin and negative equity (V15).** v5 margin default 0: TradingView applies no margin rule; with Fixed
contracts equity can fall below 0 and the strategy keeps trading. Replica: no refusal, no margin call, no
stop. Count `neg_equity_bars` (bar-close equity <= 0), report `min_equity` and `max_notional_x` (largest
`qty x entry_px / eq_before` with `eq_before > 0`). Fair halves with an `eq_before <= 0` trade in a half:
that half's `hXr_pct` is NaN (the product is undefined).

---------------------------------------------------------------------------------------------------

## 10. Assumptions (one each; both builders implement exactly these)

| id | assumption | why |
|---|---|---|
| V1 | One script run per bar, at its close; no other run. | Both `calc_on_*` flags false; documented behaviour of history bars. |
| V2 | A pending stop / limit entry placed at bar j's close is live from bar j+1; buy stop and sell limit trigger at price `>= P`, sell stop and buy limit at `<= P`; fill at `P` or at the open when the bar opens at / beyond `P`; a limit fills on touch. | SPEC_AH rule 4; `backtest_fill_limits_assumption` 0 (not set); the Pine header (L44-49, L83-90) states the same-candle, same-price equivalence. |
| V3 | Exit orders sent at a close are in force from the next bar; attached to a pending entry they act from its fill, on the rest of the fill's leg and path. | SPEC_AH rule 3; the Pine comment "also cover a fill on the same bar" (L1298); gvl G3. |
| V4 | Intrabar path = SPEC_AH rule 4 (tie: low first); along a leg the first price reached wins; at one price exits before entries; two exit orders of one trade at one price fill together. | Documented broker emulator; gvl G10. Only labels depend on the tie rules. |
| V5 | `strategy.exit` re-sent with the same id and parameters changes nothing; switching XL2 from `loss` to `stop` keeps its trailing state (armed, best); an exit order that has filled for a trade is not created again by later calls (XL1 takes its partial once). | The widely used multi-target pattern (exits re-sent every bar) takes each partial once; the Pine header's own calibration and the Update 1 emulator model one partial per trade; SWEEP_AH_SPEC section 1 keeps the trailing state on a re-send. Not checkable here. |
| V6 | XL1 closes `partPct %` of the entry quantity, exact (no rounding); XL2 (`qty_percent = 100`) covers the rest: each order fills independently. | Exit orders reserve their quantity (TradingView's documented partial-exit behaviour, as remembered). Matters only when XL2 fills before XL1 (`be_no_tp`, inverted). |
| V7 | Trailing stop: activation at `e +/- trail_points` ticks (`trail_points` 0: armed at the fill, best = fill), then `best - offset`, moving only in favour; the order's own stop and the trail: the nearer one is in force; the take profit is tested before arming on a favourable leg. | SWEEP_AH_SPEC section 1, `hrd._walk`, the verified reading of apex / hrd / gvl. |
| V8 | A new `strategy.entry` with a pending id replaces its price, type and quantity. OCA "FG" cancel: when one entry fills, the other pending entry is cancelled at once (it cannot fill later in that bar); entries placed later in the same OCA group are unaffected. | Documented order modification by id and `strategy.oca.cancel`. |
| V9 | An entry that fills against an open position closes the whole remainder at the fill's booked price (kind 'reverse') and opens exactly the order's quantity; the closed trade's exits are gone. | `strategy.entry` reverses; `pyramiding = 0` only limits same-side entries. |
| V10 | At an open: A1 market closes, A3 the open trade's exits, A4 pending entries (earlier placement first, the second OCA-cancelled). | gvl G10; only labels and the OCA winner of a double gap depend on it (probe: 0 double gaps). |
| V11 | Right after an entry fill at raw price `x`, the new trade's exits are tested at `x` as at an open. | Only reachable when the stop distance is under the 'tv' slippage (5 ticks): the slipped long's stop then lies above the market and fills at once. Count `sl_lt_slip`. |
| V12 | 'tv': slippage 0.05 against the order on stop and market fills (entry stops, stop loss, breakeven, trailing, `strategy.close`, `close_all`, 'end'), none on limit fills; commission 0.02 % of each booked fill value. | `strategy()` L304-305; TradingView applies slippage to market and stop orders (the header says so, L83-86). |
| V13 | `strategy.position_avg_price` = the booked entry fill (slippage included), unchanged by a partial exit; `loss` / `profit` / `trail_points` are measured from it; `strategy.opentrades.entry_time` / `entry_bar_index` = the fill bar, also after a partial exit. | TradingView's trade list shows the slipped entry; a partial exit splits the trade without moving the open part's entry. |
| V14 | `strategy.equity` = `cash` + open P/L at the close (costs paid included). | SPEC_AH rule 6. |
| V15 | No TradingView margin logic (v5 default 0); equity may go negative and trading continues. | v5 `strategy()` reference: margin 0 disables margin simulation. Counters in section 9. |
| V16 | No rounding: order prices and levels stay off the tick grid, tick distances fractional, quantities only by `qtyStep` and the exact `partPct` fraction. | As apex / hrd / gvl (G12). At most half a tick per level. |
| V17 | Bars of timeframe T: `fgf._bars(pair, T)`, except a BTC minute timeframe not dividing 1,440 ("960" here), built from 1-minute bars restarting at 00:00 UTC every day. | TradingView starts intraday bars at the session (day) start and truncates the last one; `build_bars.py` states "BTC intraday bars aligned to UTC midnight". fgf's epoch grid differs (131 of 910 BTC 240 signal bars). |
| V18 | The breakeven flag reads the whole bar's high / low, including prices before an intrabar fill (literal Pine). | L1315-1318. Counted `be_no_tp`. |
| V19 | A `strategy.exit` whose levels are all na places nothing; `strategy.cancel` / `strategy.close` of nothing do nothing. | Reachable before the first order of an id, or with zero distances. |
| V20 | Signals and the hold state warm up from the start of the data; trading starts flat with clean `var`s at the first window bar; orders of the last window bar do not fill; 'end' at the last close as a market fill. | REPLICA_SPEC; SPEC_AH rule 5. |
| V21 | Several market closes from one run: one close; the kind is the first in code order ('opp' before 'time'). | Same price, same flat account. |
| V22 | A market close and a pending entry both acting at the same open: the close first, then the entry from flat. | Same final position as a reversal at the open; only the label differs. |

---------------------------------------------------------------------------------------------------

## 11. What cannot be reproduced, and what the replica does instead

- TradingView itself: nothing can be compiled or backtested here. V2-V13 are readings of its engine.
- v5's 9,000-trade stop and the bars a plan can load: TradingView cannot show these windows on the low
  timeframes at all; the replica runs them in full.
- TradingView's rounding of the off-tick entry prices and levels to the tick, of the 30 % partial to the
  symbol's lot, and the feeds: the header's BTC numbers are MEXC / Bitfinex, ours Bitstamp; its gold is
  OANDA, ours Dukascopy bid with TradingView-style sessions. Another feed changes signals and fills.
- Seconds timeframes: no data below 1 minute. Nothing in the defaults uses them (zones 5 / 6 are "1" / "2"
  minutes, off). A seconds zone is na, which `ignoreNaZones` drops: the same as TradingView without seconds
  history (header L292-295).
- Live behaviour: a limit order may stay unfilled when price only touches it (header L89-90), a stop fills
  at a real tick with real slippage, the spread is real (the script's spread is a model input).
- Bar Magnifier inside TradingView: path 'mag' is OUR 1-minute walk of entries and exits, with decisions,
  market closes and the breakeven flag on the chart bars.
- `fgf.py`'s own residuals (reconcile_fgf.md).

**XAUUSD: inputs that only make sense at BTC prices, and what the replica does.** The file is the "BTCUSD
build". Every distance in dollars or points is applied literally on gold (the replica does what the Pine
does, nothing is rescaled):
- `ExitMode` "Pips" with `pipSize` 1.0 ("1 pip = $1 per BTC"): `slPips` 30 = $30, target 5 R = $150, runner
  trail `runTrailPips` 600 = $600, `trailActPips` 150, `trailPips` 600. On gold $30 is 12.6 ATR(14) of a
  60-minute bar (126 on "1"), and no default gold trade reached the $150 target in the probe: the default gold
  strategy is a stop-and-reverse system whose exits almost never fire (probe: every normal default gold
  trade ends by 'reverse' or 'end'; inverted a few by 'sl').
- `ExitMode` "Points": `slPoints` 3900 ($39), `tpPoints` 19500 ($195), `trailActPoints` 4500, `trailPoints`
  1000, `runTrailPts` 58000 ($580): "0.1 x the median ATR of the calibration month" of BTC.
- `fixedQty` 10 ("contracts = BTC"): 10 oz on gold, 0.13 of the account; `maxQty` 50, `qtyStep` 1 likewise
  coin-sized.
- The other way round: the Points-unit SIGNAL inputs `entryDistPoints` 50 ($0.50), `entryHoldMinFavPoints` 5,
  `burstPointsInput` 172 ($1.72) are the original GOLD indicator's; with the default `DistUnit` "ATR" they
  are inert. `spreadPoints` 25 = $0.25: a gold-like spread, negligible on BTC.
- Portable inputs: everything in ATR (`DistUnit` "ATR", `ExitMode` "ATR"), the TDI and zone inputs, `partPct`,
  `maxBarsHeld`, `entryValidBars`, `QtyMode` "Risk %". The calibration grid (section 14) uses those.

---------------------------------------------------------------------------------------------------

## 12. Interface, trade record, summary

    prepare(pair, chart_tf, params=None) -> P
    simulate(P, x=None) -> R
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)        # splits one dict into 3.1 / 3.2 keys

`DEFAULTS` = every Pine default of 3.1 and 3.2 (`fgfOn` True, `ExitMode` "Pips", `QtyMode` "Fixed",
`inv` False), plus the replica controls (`path` 'tv', `cost` 'tv'). `INITIAL_CAPITAL = 100000.0`. One numba
kernel for A, B, C, D over the window bars (no Python object in the loop). Speed: one `simulate` on BTC "1"
(1,039,430 bars) well under 1 s after compilation (the probe in pure Python takes 24 s); first `prepare`
under 2 minutes; under 3 GB.

`KINDS = ['', 'sl', 'tp', 'tp_part', 'be', 'runner', 'trail', 'reverse', 'opp', 'time', 'end']` ('sl' =
comment "SL" of XL1 / XL2 / XL; 'tp' = "TP" of XL; 'tp_part' = "TP part" of XL1; 'be' = "BE" of XL2;
'runner' = XL2's trailing stop; 'trail' = XL's trailing stop; 'reverse' = an opposite entry fill; 'opp' =
"opp signal"; 'time' = "time stop"; 'end').

**Trades**, one row per ENTRY fill (a position from its fill to its last exit), in fill order:

| column | content |
|---|---|
| `dir` | REAL side, +1 / -1 |
| `sig` | normal-frame side of the signal that placed the order (+1 BUY); `= dir` normal, `-dir` inverted |
| `sig_bar`, `entry_bar`, `exit_bar` | file rows: where the order was last placed, where it filled, where the last part left |
| `entry_time`, `exit_time` | `t_open` of the fill bar / of the exit bar (chart bars, also in 'mag'); 'end': `t_close` |
| `entry_px`, `entry_type`, `qty` | booked fill price, 'stop' / 'limit', units |
| `exit_px` | qty-weighted mean of all exit fills (so `pnl_gross = dir x qty x (exit_px - entry_px)`) |
| `exit_kind` | kind of the fill that closed the last part; a joint XL1 + XL2 fill: XL2's kind |
| `part_kind`, `part_bar`, `part_px`, `part_qty` | an earlier fill that closed only part ('tp_part'; in `be_no_tp` trades 'be' / 'runner' / 'sl'); '' / -1 / NaN / 0 if none |
| `pnl`, `pnl_gross`, `costs`, `eq_before` | section 9 |
| `sl_dist`, `sl_px`, `tp_px`, `r_mult` | the order's stop distance, the levels at the fill (NaN if absent), `pnl / (sl_dist x qty)` |
| `rev`, `gap`, `be`, `be_no_tp` | opened by a reversal fill; filled at an open; XL2 reached breakeven mode; section 8 |

**Summary.** The common fields exactly as `hrd.summary_fast` + `hrd.extra_fields` compute them, with
`INITIAL_CAPITAL = 100000` and one trade = one row above: `start, end, bars, trades, net_pct, pf, win_pct,
max_dd_pct, max_dd_init_pct, long, short, raw_long, raw_short, blocked_long, blocked_short, half1_pct,
half2_pct, exposure, final_equity, exit_<kind>` (final kinds, every kind of KINDS), `zero_length` (entries
whose last part left on the entry bar), `h1r_pct, h2r_pct, h1_trades, h2_trades, avg_bars_held, costs`.
- `long` / `short`: real sides. `raw_*` / `blocked_*`: the FGD funnel (C4), normal frame.
- Equity curve for `max_dd_pct` / `max_dd_init_pct`: 100,000, then `E[0] .. E[n-2]`, then the final equity
  (after the 'end' close and its cost) in place of `E[n-1]`; running peak starts at 100,000. `half1_pct` /
  `half2_pct` from `E[mid_j]`, as `hrd`.
- Fair halves: entries with `entry_time <= mid` / `> mid`, `100 x (prod(1 + pnl / eq_before) - 1)`, 0 for an
  empty half, NaN if a half holds an entry with `eq_before <= 0`.

Fields of this strategy: `part_<kind>` (partial fills by kind), `tv_rows` (rows of TradingView's List of
Trades: per entry, one per exit order that filled, XL1 and XL2 counted apart even when they fill together,
plus one for a 'reverse' / 'opp' / 'time' / 'end' close of a remainder), `be_trades`, `be_no_tp`, `net_r`,
`h1_r`, `h2_r` (sum of `r_mult`, NaN skipped: all / per half; the header's unit), `orders_placed`,
`orders_replaced`, `orders_filled`, `orders_cancelled` (stale cancels that removed a live order),
`oca_cancelled`, `orders_unfilled_end`, `both_pending_bars`, `gap_entries`, `zero_qty`, `sl_lt_slip`,
`slippage_paid`, `neg_equity_bars`, `min_equity`, `max_notional_x`, `sig_buy`, `sig_sell` (signal bars in
the window, from `P`).

Comparing A and B: bars, kinds, flags and counts exactly; prices, quantities, P/L and equity fields to a
relative 1e-9.

---------------------------------------------------------------------------------------------------

## 13. Builders: outputs, self-checks, sanity numbers

- Saved trade lists (cost 'tv', path 'tv', default inputs): `$W/out/fgv5_<a|b>_<PAIR>_<TF>.parquet` for BTC
  60, BTC 5, XAU 60, XAU 15, one file per cell with a column `variant` in `off_normal`, `off_inv`,
  `on_normal`, `on_inv`. On BTC 60 and XAU 60 the two `on_*` variants have no rows (fact 2); record every
  variant's summary in `$W/out/fgv5_<a|b>_summaries.json`.
- Signal checks: the 4.3 cross-checks (`fgf._filter_series` on every chart but BTC 240; the filter's own
  signals on "60"); `oneEntryPerBar` False gives the same signals (inert); 3.3's no-effect inputs.
- `fgfOn` False reproduces the original: P6 (gates all True), plus kernel tests on INJECTED arrays,
  independent of `fgf`: small hand-built inputs (10 to 40 bars of OHLC, ATR, `buySig`, `sellSig`, `buyOk`,
  `sellOk`) checked against the bar-by-bar expectation written in the test, for: a stop entry and its take
  profit on the same leg; an entry and its stop on the same bar; a gap entry; a gap through the stop; a
  partial + breakeven exit; a partial + runner trailing exit; a Fixed + trail exit; a reversal by a pending
  order; an 'opp' close with `exitOnOpposite`; a 'time' close; a stale cancel; an OCA cancel with both
  orders pending; an order replaced by a new signal; `Direction` "Long" / "Short" in both modes; an inverted
  `be_no_tp` case.
- Hand traces from real data with the bars printed, at least 3 trades of each exit kind: 'sl', 'tp' (Fixed),
  'tp_part', 'be', 'runner', 'trail' (Fixed + `useTrail`), 'reverse', 'opp', 'time' (`maxBarsHeld` 5),
  'end'; plus a same-bar entry and exit, a gap entry, an OCA cancel, a stale cancel, a `be_no_tp` trade, and
  a "Risk %" quantity against a direct evaluation of `calcQty`.
- P1 to P6 of section 8; the mirror on 5 single decisions (P2).
- Asserts: at most one pending order per id and never on the side held; a new trade starts in loss mode;
  `exit_bar >= entry_bar`; quantities of the parts sum to `qty`.
- Sanity numbers (probe_sim / probe_batch, single pure-Python implementation, unverified, order of
  magnitude only; default inputs, cost 'tv', path 'tv', Fixed 10; BTC 240 with fgf's epoch-grid "960", so
  expect small differences there). Trades (entries) and net %:

  | cell | filter off, normal | off, inverted | on, normal | on, inverted |
  |---|---|---|---|---|
  | BTC 1 | 85,682, -11,066 % | 160,486, -62,622 % | 27,779, -3,251 % | 52,279, -18,302 % |
  | BTC 5 | 22,468, +64.6 % | 37,994, -14,184 % | 12,585, +375 % | 19,711, -7,014 % |
  | BTC 15 | 8,241, +2,011 % | 12,448, -4,512 % | 5,344, +1,366 % | 7,273, -2,554 % |
  | BTC 30 | 4,218, +2,475 % | 6,075, -2,375 % | 2,564, +1,475 % | 3,076, -1,202 % |
  | BTC 60 | 2,207, +2,158 % | 2,962, -1,181 % | 0 | 0 |
  | BTC 120 | 1,100, +1,997 % | 1,424, -661 % | 238, +420 % | 243, -95.7 % |
  | BTC 240 | 613, +1,580 % | 741, -292 % | 161, +407 % | 165, -92.0 % |
  | XAU 1 | 16,658, -100.4 % | 16,658, -86.8 % | 2,109, -13.9 % | 2,109, -9.8 % |
  | XAU 5 | 4,374, -27.5 % | 4,374, -21.6 % | 1,479, -11.2 % | 1,479, -5.4 % |
  | XAU 15 | 1,521, -9.6 % | 1,521, -7.5 % | 883, -7.2 % | 883, -2.7 % |
  | XAU 30 | 727, -0.8 % | 729, -7.4 % | 475, -1.1 % | 480, -4.1 % |
  | XAU 60 | 434, -3.6 % | 438, -1.4 % | 0 | 0 |
  | XAU 120 | 245, -2.1 % | 251, -1.0 % | 63, -0.5 % | 65, -0.1 % |
  | XAU 240 | 120, -1.1 % | 127, -0.5 % | 28, +0.4 % | 37, -1.2 % |

  BTC 60 filter off, normal: final kinds sl 1,225 / be 462 / runner 508 / reverse 12; 1,358 entries with a
  'tp_part'; 1,157 closed on their entry bar; 212 bars with both orders pending, 106 OCA cancels, 461 stale
  cancels; `tv_rows` 3,565. Inverted: sl 2,682 of 2,962, 2,653 closed on their entry bar, 63 `be_no_tp`,
  equity below zero from the first months (minimum -1.09 M). XAU: every normal trade ends by 'reverse' (or
  'end'). The BTC 'tv' results are an artefact of the one-path bar model with a stop of 0.03-0.8 ATR; the
  'mag' path (stage 3) is the one to read. With cost 'ours' the BTC numbers barely move (same 0.02 %).

Additions for stage 3 (beyond REPLICA_SPEC):
- In `out/inv_fgv5_<PAIR>_<TF>.json` print next to every row `neg_equity_bars`, `min_equity`, `be_no_tp`,
  `tv_rows`, `zero_length`; the "script" cost = 'tv' (0.02 % + 5 ticks).
- Tests: P1 (both exit units, with and without `exitOnOpposite`, a time stop, `entryValidBars` 0 and 1),
  P2-P6; 'mag' on chart "1" == 'tv'; 'mag' with one fake sub-bar per chart bar == 'tv'; the header
  properties: (i) every 'tp_part' fill is at `entry_px + dir x tpT x 0.01` (or a better open), every 'sl' fill
  at the stop minus the slippage (or a worse open); (ii) `qty` of every trade = `calcQty` on `sig_bar` with
  the equity recomputed from the trade list; (iii) every 'time' exit at bar x has `x - entry_bar ==
  maxBarsHeld + 1`; (iv) every 'be' fill is at `entry_px` minus the slippage (or a worse open); (v) normal
  runs have `be_no_tp == 0`.
- The random reconcile settings must draw both exit units with both styles, `partPct` 0 / 30 / 70 / 100,
  `runBE` off, `useTrail`, `tpR` 0 (no target), `maxBarsHeld > 0`, `exitOnOpposite`, `allowReverse` off,
  `entryValidBars` 0 / 1 / 10, `Direction` "Long" / "Short", "Risk %" sizing, `entryHoldBars` 2,
  `usePriorFilter`, `useAnyCombo`, `burstAtrMult` 0 (both signals on one bar), `autoTf` off, `htfNoRepaint`
  off, zones 4-6 on, and filter settings outside the grid (`fgfTf` "15" / "240", `fgfLvMode` "Signal
  close", `fgfBandAtr` 0, `fgfAgainst` off).

---------------------------------------------------------------------------------------------------

## 14. Calibration grid proposal (for `$W/CALIB_SPEC.md`)

Scored as CALIB_SPEC says (path 'mag', cost 'ours'). **15,984 settings per cell**, the same in every cell:
9 signal settings x filter {off, on} = 18 `prepare` settings; per `prepare` setting 888 `simulate` settings.

| # | dimension (Pine names) | values | kind | side | default |
|---|---|---|---|---|---|
| 1 | `burstAtrMult` | 0.3, 0.5, 1.0 | ordinal | prepare | 0.5 |
| 2 | `minAlignedZones` | 1, 2, 3 (1 = parent only, 3 = parent + 2x + 4x; 0 would equal 1) | ordinal | prepare | 2 |
| 3 | `fgfOn` | False, True | categorical | prepare | True |
| 4 | `inv` (`fgvInv`) | False, True | categorical (the direction control) | simulate | False |
| 5 | `entryDistAtrMult` | 0.0, 0.25, 0.5 | ordinal | simulate | 0.25 |
| 6 | `allowReverse` | True, False | categorical | simulate | True |
| 7 | `exitStyle` | 'pips_default', 'fixed', 'part30', 'run' | categorical | simulate | 'pips_default' |
| 8 | `slAtrMult` | 0.25, 0.5, 1.0, 2.0 (None for 'pips_default') | ordinal | simulate | None |
| 9 | `tpR` | 1.5, 3.0, 5.0 (None for 'pips_default') | ordinal | simulate | None |
| 10 | `maxBarsHeld` | 0, 12 | categorical (0 = off) | simulate | 0 |

`exitStyle` members (whole exit rules; the Pine inputs they set go in extra columns that do not start with
`p_`):
- 'pips_default': `ExitMode` "Pips", `pipSize` 1, `slPips` 30, `tpRPips` 5, "Partial + runner", `partPct` 30,
  `runBE` on, `runTrailPips` 600: the script's default exit.
- 'fixed': `ExitMode` "ATR", `TpStyle` "Fixed", `useTrail` off: stop `slAtrMult` x ATR(14), target `tpR` R.
- 'part30': `ExitMode` "ATR", "Partial + runner", `partPct` 30, `runBE` on, `runTrailAtr` = r1.
- 'run': `ExitMode` "ATR", "Partial + runner", `partPct` 0 (all runner: breakeven and trail from the `tpR`
  level), `runBE` on, `runTrailAtr` = r2 (the header's BEST family, L156-162).

Runner trail distances per cell (CALIB_SPEC floor: offset >= 0.1 % of price on BTC, 0.05 % on gold, at the
10th percentile of ATR(14) / close over the window; ladder 1.5, 2.5, 3.5, 5, 6.5, 8.5; r1 = the smallest
ladder value >= max(1.5, floor / p10), r2 = the next ladder value):

| cell | BTC 1 | BTC 5 | BTC 15-240 | XAU 1 | XAU 5 | XAU 15-240 |
|---|---|---|---|---|---|---|
| p10 of ATR(14) / close, % | 0.0157 | 0.0574 | 0.125 / 0.198 / 0.318 / 0.512 / 0.826 | 0.0101 | 0.0290 | 0.0599 / 0.094 / 0.145 / 0.203 / 0.311 |
| floor / p10 | 6.37 | 1.74 | <= 0.80 | 4.95 | 1.72 | <= 0.83 |
| (r1, r2) | (6.5, 8.5) | (2.5, 3.5) | (1.5, 2.5) | (5, 6.5) | (2.5, 3.5) | (1.5, 2.5) |

The 'pips_default' runner ($600) is 0.68 % of the BTC price and 47 % of the gold price: above both floors.
Every row is `floor_ok`.

Count: 3 x 3 x 2 = 18 `prepare` settings; `simulate`: 2 x 3 x 2 x (1 + 4 x 3 x 3 = 37) x 2 = 888; total
**15,984**. Combinations that cannot differ are listed once ('pips_default' with `slAtrMult` / `tpR` None;
'fixed' carries no runner). The script default is one grid point in every dimension: 0.5, 2, filter on,
normal, 0.25, reverse on, 'pips_default', None, None, 0. Everything else at the script defaults (`autoTf`,
zones 1-3, `DistUnit` "ATR", `entryValidBars` 3, `exitOnOpposite` off, `Direction` "Both", `atrLen` 14, the
filter's own inputs).

**Sizing of the grid (not a dimension).** Every row uses the script's own "Risk %" branch scale-free:
`QtyMode` "Risk %", `riskPct` 1.0 (its default), `maxQty` 1e9, `qtyStep` 0.000001: each trade risks 1 % of
equity over its own stop, whatever the stop width and the pair. The default Fixed 10 contracts is 8.8
accounts of BTC and 0.13 of gold: results of different stops are not comparable in risk, nothing
compounds, and BTC equity goes below zero (probe: inverted defaults on BTC 1 / 5 / 15 / 30 / 60 / 120 / 240),
which leaves the fair halves undefined. A runner `--one ... --script-sizing` re-runs a setting with `QtyMode`
"Fixed" 10 (the published file's sizing) for the default row and any pick. Keep `net_r`, `h1_r`, `h2_r`,
`zero_qty`, `neg_equity_bars`, `be_no_tp`, `tv_rows` in the rows.

The filter dimension: off / on only; the script has no blocked-signal close. On chart "60" the filter-on rows
with `burstAtrMult` 0.5 and `minAlignedZones` 2 have no trades at all (fact 2; the strategy's signal is then
the filter's own), and every filter-on row there sees only signals the filter's 60-minute candle did not
produce.

Why these dimensions (header record and probe):
- The signal family: the header's BEST differs from the default in the burst threshold (0.3), the zones (1)
  and the entry distance (0): "entry distance 0.25 ATR -> -31.6R" worst half, "Minimum zones 2 -> +1.4R"
  (L172-176). The burst sets how many signals exist.
- The stop width decides whether the strategy can pay its costs on BTC (a round trip is 0.26 to 4 ATR of a
  1-minute bar at 0.25-1 ATR stops; header: "any SL <= 0.25 ATR -> below -170R"), and how far the 'tv' and
  'mag' views differ.
- The take-profit structure: fixed target vs partial + runner vs all runner (header L114-118, L156-162);
  `tpR` moves the target, the trail activation and the breakeven trigger together.
- `allowReverse` ("reverse on -> -16.4R", L172-174) and the time stop ("time stop off -> -1.1R"; 12 bars in
  BEST).
- Left out, in order of expected weight: `entryValidBars` (3 in every header result), `exitOnOpposite`,
  `partPct` other than 0 / 30 / 100, `runBE` off, the Fixed-style trail, `useTdiTradeZone` off,
  `entryHoldBars`, `usePriorFilter`, `useAnyCombo`, `tdiRsiLen` / `tdiFastLen`, a 4th zone, `Direction`,
  `riskPct`, every filter input (its timeframe "60", level "Entry price", band 0.25).

Notes for the orchestrator:
- **The 'tv' path is not a view of this strategy on BTC** with stops below about 1 ATR: the one-path bar
  fills the entry and the target on the same leg (probe: +2,158 % on BTC 60 at the defaults). The grid is
  scored on 'mag'; quote 'tv' only next to it.
- **Thin cells.** Gold 120 / 240 with the filter on: 63 / 28 default trades (probe). Filter-on rows on "60"
  are zero or near zero by construction. They fail the 30-trades-per-half rule; that is the finding, not a
  defect.
- **Identical rows.** `minAlignedZones` 1 with the zone filter makes zones 2-3 irrelevant; rows can repeat
  results across `allowReverse` when positions rarely overlap a signal (BTC 'tv'); rule C counts equal
  results once.
- **Memory / speed.** Per cell one `fgf.fgf_permissions` call (the filter does not depend on any grid
  dimension) and 9 signal computations (TDI per timeframe cached; BTC "1" builds "2" and "4" from the
  6.5 M-row minute file once; BTC "240" builds the daily-reset "960"). `simulate` on BTC 1 must stay well
  under 1 s for the 45-minute budget (15,984 rows / 3 workers).
- **Margin.** A file published from a pick keeps v5's margin 0 unless changed; with "Risk %" and small
  stops the notional is large (1 % risk over a 0.25 ATR stop on BTC 1 is about 100 accounts). Report
  `max_notional_x` with any pick.
