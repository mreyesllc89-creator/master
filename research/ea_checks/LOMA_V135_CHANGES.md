# XAUUSD_Loma_TrendPullback.mq5 v1.34 -> v1.35: changes

File: `v135/XAUUSD_Loma_TrendPullback.mq5` (spec: `v135/SPEC.md`); the last file, with the restart fixes 9 and 10 of
`FIXES.md` as finally made and fix 11: `v135/last/XAUUSD_Loma_TrendPullback.mq5`, md5 3be59db21448e224c952af618237bb8f
(the intermediates: `v135/restart/XAUUSD_Loma_TrendPullback.mq5`, md5 b2dea501c395ed446825331f9fcb85b2, had fix 10
without the handling of a signal that waits for algo trading and without the Strategy Tester guard;
`v135/final/XAUUSD_Loma_TrendPullback.mq5`, md5 156f018a42570cc037808d99b068c525, had them, but did not save the
deletion of that handling to disk at once, named the variable per magic number and symbol only, and had no fix 11).
Everything not listed here is unchanged. Paths below (`finish/...`, `implement/...`, `fix/...`, `parity/...`,
`recheck/...`, `restart/...`, `final/...`, `last/...`) are relative to the folder of this file.
With the 8 new inputs at their defaults the EA trades exactly like v1.34, with two deliberate exceptions: `SpreadOK`
(fix 1 in `FIXES.md`): a spread exactly equal to `MaxSpread_Points` is now always accepted, as in the backtest, where
v1.34 refused it about half the time through floating-point noise; and a restart inside a trigger bar (fix 10, item
15): the bar's signal is not decided a second time. 71 of 71 shipped setups (16 gold, 55 BTC) gave identical trades
and an identical journal in the simulated terminal (`finish/rt/reg_*.txt`; again on the fixed file: `fix/rt/reg_*.txt`,
on the restart-fixed file: `restart/patcher/rt/reg_*.txt`, on the final file: `final/finisher/rt/reg_*.txt`, and on the
last file: `last/patcher/rt/reg_*.txt`). The fixes made after the verification are listed in `FIXES.md`, one entry per
reported defect (9 and 10: the two restart defects found by the re-check; fix 10 was completed after the review in
`restart/reviewer/` and after the final review in `final/final-reviewer/`; 11: an explicit cast found by a
compile-readiness review).

## New inputs (60 -> 68; existing inputs keep their names, order and defaults)

| Group | Input | Default | Meaning |
|---|---|---|---|
| R5: Stop loss / take profit (after `MaxSL_Points`) | `ScaleWithPrice` | false | multiply `SL_Buffer_Points`, `MinSL_Points`, `MaxSL_Points` by bid / `ReferencePrice` |
| | `ReferencePrice` | 0.0 | price at which the `*_Points` values were calibrated (must be > 0 when `ScaleWithPrice`) |
| R7b: Stochastic turn filter (new group after R7) | `UseStochTurnFilter` | false | entry only when the filter's own Stochastic(7,1,7) came from the extreme and turned |
| | `StochTurnBars` | 5 | closed bars looked at, signal bar included |
| | `StochTurnHigh` | 80.0 | sells: main line was at or above this |
| | `StochTurnLow` | 20.0 | buys: main line was at or below this |
| R8: Trailing stop (after `TrailStep_Points`) | `TrailMode` | TRAIL_RISK | trailing system 0-13 (`ENUM_LOMA_TRAIL_MODE`); the units of `TrailStartR` / `TrailDistanceR` depend on it |
| | `TrailParam` | 0 | period, bars or variant of the level systems |

`TrailMode` values: 0 RISK, 1 ATR_ENTRY, 2 PERCENT, 3 PROFIT_LOCK, 4 STEP, 5 CHANDELIER, 6 CANDLES, 7 EMA, 8 SMA,
9 PSAR, 10 BOLLINGER, 11 HTF_CANDLE, 12 PIVOTS, 13 HUMP (table A of SPEC.md).

## Added functions

- `PriceScale(price)`: bid / `ReferencePrice` when `ScaleWithPrice` is on, else 1.
- `StochTurnCheck(side, why)`: R7b rule on the signal bar with the filter's Stochastic(7,1,7); 1 allowed, 0 not (reason in `why`), -1 data not ready.
- `TrailModeText()`: "EMA (start 0.50, distance 0.50, param 34)" for the journal and the panel.
- `TrailIsLevelMode()`: true for the 8 level systems (CANDLES .. HUMP).
- `TrailHtfPeriod()`: timeframe of the HTF_CANDLE candle (15, 30, 60, 240 minutes; else PERIOD_CURRENT = invalid).
- `TrailInputsOK()`: OnInit checks of `TrailStartR`, `TrailDistanceR`, `TrailParam` per `TrailMode` (Print + false).
- `TrailBarsMissing(need, have)`: one journal line when the history holds fewer closed trigger bars than a level needs.
- `TrailRates(shift, count, barTime, r[])`: `count` closed trigger bars ending at `shift`, checked against the expected bar time (1 / 0 too short / -1 retry, also while `Bars()` is 0 or the series is not synchronized).
- `WilderATR(r[], count)`: Wilder ATR(14) (alpha 1/14) at the last of `count` bars.
- `EntryATR(ticket, opened, atr)`: ATR(14) at the signal bar of a position, from history once, then kept in terminal variable `LOMA_<magic>_A_<ticket>`.
- `BestSince(fromBar, m1, isSell, best)`: highest bid high (buy) / lowest bid low + bar spread (sell) of the completed M1 bars, read from history. The M1 bars are requested first (this makes the terminal build the M1 series when nothing else uses it), then `SERIES_SYNCHRONIZED` is checked and the bar of the current minute must be in the series, so that the bar before it is complete.
- `TrailLevel(isSell, lastClosed, m1, level)`: level of the 8 level systems from the last closed trigger bar (ports of `MarketX/MarketY._levels`, `psar_levels`, `pivot_levels`, `hump_levels`). HTF_CANDLE requests the higher series (`iTime` in `HTFBarCurrent`) before it reads its `SERIES_SYNCHRONIZED` state; PIVOTS retries while `Bars()` is 0.
- `TrailStopPrice(price, isSell)`: puts a trailing stop on the tick grid, rounded to the looser side (down for a buy, up for a sell).
- `TrailApply(ticket, isSell, sl, tp, cand, minStep, nowT)`: tightens the stop (never loosens, never touches the TP), closes at market when the price is already through it, skips a stop inside the stops level (one journal line per position); false = retry on a later tick.
- `TrailPosition(ticket, opened, open, sl, tp, isSell, initRisk, m1, nowT)`: one evaluation of a position for every system except RISK (STEP every tick, with the best of the live tick and of the completed M1 bars from the entry bar on; the others once per closed M1 bar).

## Changed functions

- `OnInit`: the v1.34 `TrailDistanceR` check now applies to TRAIL_RISK only; adds `TrailInputsOK()`, the turn-filter (`StochTurnBars` 1 .. 1000) and price-scaling input checks, the turn filter's Stochastic handle, `g_trailBar` reset and three journal lines; in the Strategy Tester (`MQL_TESTER`) it deletes this chart's decided-bar variable `LOMA_<magic>_D_0_<symbol>_<timeframe>`, since a pass calls OnInit once and a value left by an earlier pass is stale (fix 10, item 15).
- `OnDeinit`: releases the turn filter's Stochastic handle.
- `OnTick`: a trailing close at market on this tick marks the trigger bar (`g_trailExitBar`); a signal of that bar is not entered (the backtest's one-position rule). The trigger bar whose signal was decided (evaluated as valid) is kept in terminal variable `LOMA_<magic>_D_0_<symbol>_<timeframe>` (one per magic number, symbol and trigger timeframe, e.g. `LOMA_26113001_D_0_XAUUSD_M2`); after a restart or re-init inside that bar the signal is not decided again (journal "this bar's signal was already decided before a restart"; v1.34 code, fix 10, item 15). A signal still waiting for algo trading (`TradingAllowed()` false) is not decided yet: the variable is deleted while it waits, and the deletion is saved to disk at once (`GlobalVariablesFlush`, so that it also holds after a terminal crash), and written again just before the order is sent.
- `SignalDataReady`: also waits for the turn filter's Stochastic.
- `EvaluateSignal`: R7b check next to the R7 filter: read before the signal line (not ready = retry), skip reason in the journal and on the panel; the signal stays counted.
- `BuildTradePlan`: SL buffer, minimum and maximum stop multiplied by `PriceScale(bid)`.
- `ManageOpenPositions`: for `TrailMode` other than RISK, calls `TrailPosition` (STEP on every tick, the others on the first tick of each M1 bar; a failed request or unready data is repeated on the next tick after the `TrailFailed` throttle). The 1R fallback to the current SL (no `R` terminal variable and the opening deal not found) is used by these systems only while that SL is still on the loss side of the open price; otherwise the opening deal is looked up again on the next tick, and while 1R is not known the M1 bar is not marked as evaluated, so the once-a-minute systems evaluate it on the first tick on which the deal is found (fix 9). TRAIL_RISK code unchanged.
- `SpreadOK` (v1.34 function): the spread is counted in whole points, `MathRound((ask - bid) / point) / scale`, so that a spread equal to `MaxSpread_Points` passes every time, as in the backtest (`2 x hs > max_spread` refuses only a wider one). v1.34 compared `(ask - bid) / point`, which is a hair above or below the whole number depending on the price, and refused such a spread in about half the cases.
- `InitialRiskFromHistory` (v1.34 function): the position id is passed to `HistorySelectByPosition` as `(ulong)positionId`, the parameter type MetaEditor declares (fix 11); the same value, no change in behaviour.
- `UpdatePanel`: "v1.35" and the trailing system when it is not RISK.
- Also: `#property version "1.35"`, header comment (R5b, R7b, R8b, the NOTES paragraphs on the trailing systems, on the terminal variables and on charts that share a magic number, and the restart sentence of the entry-parity note), `ENUM_LOMA_TRAIL_MODE`, globals `g_hStochTurn`, `g_trail*`, `g_step*`, defines `TRAIL_ATR_PERIOD` (14), `TRAIL_ATR_BARS` (300), `TRAIL_EMA_BARS` (500), `TRAIL_PSAR_BARS` (1000), `TRAIL_PIVOT_BARS` (1000).

## Where the EA cannot do exactly what the backtest does

Measured in the simulated terminal (`finish/rt`): the real OnTick on the backtest's own one-minute bars (4 ticks per
minute: open, adverse extreme, favourable extreme, close; constant spread), 16 May - 13 Nov 2026, every shipped
trailing setup (gold 16, BTC 55, which include all setups of the 15 combinations). Result: of 684 gold and 2,129
BTC backtest trades, the EA makes 684 and 2,103 with the same entry minute, exit minute and R (|dR| <= 0.0015 gold,
<= 0.0002 BTC apart from item 13); the 26 missing BTC trades are item 12. The fixed file gives byte-identical trades
and journals in these runs (`fix/rt/out_*_cases.txt`).

New in v1.35:

1. Stop on the tick grid. A trailing stop is rounded to the looser side, so on prices that lie on the grid it is hit
   exactly when the backtest's unrounded stop is; the fill is up to 1 tick worse. Size: |dR| <= 0.0015 (gold),
   <= 0.0002 (BTC). (Before this fix the stop was rounded to the nearest tick: a buy stop up to half a tick above the
   backtest's was touched one minute early, gold case 08, 1 trade in 684.)
2. 1R: the EA's 1R is |fill price - stop sent| (stop on the tick grid, real fill); the backtest's uses the
   unrounded stop and the bar's open. R-based thresholds and step sizes move by at most `TrailStartR` x half a
   tick in price (relative to 1R: 0.005 USD / stop, e.g. 0.5% of a 1 USD gold stop, 0.05% of a 10 USD BTC stop).
3. Intra-minute order, STEP only (and the existing RISK). STEP works on every tick; the backtest moves the step
   stop from the minute's extreme and stops out only when the minute closes beyond it (base) or whenever the low
   reaches it (stress, `trail_worst`). Real ticks fall between the two; one-minute data cannot tell which. Size:
   bounded by the published base and stress runs (stress also adds a one-minute entry delay, slippage and
   commission): unseen PF 1.36 / 1.26 for M10 step. The other 12 systems use completed minutes only and have no
   such ambiguity.
4. Bid chart against mid prices. Everything the EA reads from the chart comes from bid bars: the MACD and the
   Stochastic of the signals and the hump extremes of the initial stop and target (v1.34 code), and the trailing
   levels, ATR and best prices (v1.35). The backtest computes all of them on mid prices and adds or removes half a
   spread (for the initial stop and target, that of the entry minute). A sell's best price is bid low + that M1
   bar's `MqlRates.spread` (the current spread when it is 0), and a level sell stop adds the spread of the minute's
   first tick. With a constant spread this is the same thing (0 such differences in any constant-spread run). With
   a spread that changes over time it is not, and it changes signals, not only trailing levels. Measured by the
   parity verifier on the FTMO spread table by hour (gold, 49 setups, 2 Mar - 13 Nov 2026,
   `parity/out/A_gold_goldv`, rerun on the fixed file in `fix/parity_ea`): 291 of the 9,681 mid-chart signals
   (3.0%) do not exist on the bid chart and 232 bid-chart signals do not exist on the mid chart. Of the 3,744
   backtest trades, 3,622 have the same entry in the EA (3,611 before fix 1 of `FIXES.md`): 122 backtest trades
   (3.3%) have no EA trade and 87 EA trades (2.4%) have no backtest trade; of the trades with the same entry, 47 leave in another
   minute (1.3%), 33 of them on the initial stop, whose bid hump extreme carries the spread of its own minute while
   the backtest uses the mid extreme and the half spread of the entry minute. Profit factor of the 4 gold
   combinations on the unseen months (16 May - 13 Nov 2026, clean exits, `fix/parity_ea/goldv_pf_0516.txt`),
   backtest -> EA: M10 ATR 1.440 -> 1.438, M10 percent 1.272 -> 1.276, M5 chandelier 1.216 -> 1.277, M5 hump
   1.496 -> 1.522. Neither side is wrong: the EA uses the bid chart MT5 gives it, the backtest models mid prices.
   (Computing the indicators on mid prices, bid + `MqlRates.spread` / 2, would remove this; not done in v1.35.)
5. Timing. The minute systems act on the first tick of the next M1 bar; the backtest from that minute's open.
   With no tick for a while the stop moves later (the previous stop stays in place). A close at market fills at
   the first tick (plus slippage), the backtest at the open.
6. Broker stops / freeze level: a new stop closer to the price than that level is not placed in that minute
   (one journal line per position); the backtest has no such limit. Size: none with a stops level of 0.
7. Finite history windows. Wilder ATR over 301 bars (seed weight 2e-10), EMA over max(500, 10 x period) bars,
   Parabolic SAR over 1,000 bars, swings searched in 1,000 bars, hump levels from the `HumpWarmupBars` replay. Probe
   of the EA's own functions against the backtest's arrays on 42,000-63,000 sampled minutes per timeframe
   (`implement/rt2/probe_*.txt`): candles, SMA, Bollinger, HTF candle, swings, hump, ATR, best price, ATR at entry
   identical; EMA within 1.5e-5 USD; SAR identical once 1,000 bars exist (`implement/psar_window.txt`: 1,000 bars
   reproduce the full-history SAR on 20,000 samples per timeframe and variant, 300 bars do not).
8. HTF_CANDLE 240: MT5 builds H4 candles from server midnight, the backtest from midnight of its data's clock.
   Identical when the backtest data is in server time (as for these presets); 15, 30 and 60 minutes are never
   affected.
9. Restart. Best prices, the initial risk and the ATR at entry are rebuilt from history and terminal variables, but
   the level of a minute in which the EA was not running is not applied afterwards, and a stop crossed during the
   downtime is closed at market on the first tick after it (the backtest at the stop). STEP reads the entry bar
   back from history too (from the minute after the entry), so a step reached in the entry minute survives a
   restart or a failed modification there. The "no entry on the bar of a trailing close" mark is in memory; a
   signal decided on that bar is not decided again after a restart (item 15).
   Measured on the restart-fixed file and again on the final and the last file: a restart every 211 minutes at
   second 20 with the R and A variables erased changes no trade, with the deal history present and with it missing
   for the 3 ticks after each restart (71 of 71 setups each, trade files byte-identical to the runs without restarts;
   `FIXES.md` fixes 9 and 10).
   1R when the `R` variable is missing (attached on another terminal or VPS, variables erased) and the opening
   deal is not in the terminal's history yet: the current SL is taken as 1R only while it is still on the loss
   side of the open price; a stop already moved past the entry is not (the deal is looked up again on the next
   tick, and the position is not trailed until then). Meanwhile the M1 bar is not marked as evaluated, so the
   once-a-minute systems make that minute's move on the first tick on which the deal is found (fix 9; before it,
   the move waited for the next minute: 30 of 91 moves after a restart in the test above). A loss-side stop that a
   system had already moved (chandelier, ATR, percent, levels) would still be taken as 1R, which lowers that
   position's R thresholds.
   The entry M1 bar counts as a whole for every system, as in the backtest, which enters at the bar's open. The EA
   enters on the first tick of the trigger bar; when it fills later in that M1 bar (algo trading was off at the
   first tick, or the EA was not running at the bar's open and started inside the bar), the part of the bar before
   the fill counts as well.
10. Stochastic turn filter: MT5's Stochastic gives 100 when the 7-bar high-low range is 0, the backtest gives no
    value (no entry). Size: never in the probe (0 differing decisions in 42,000-63,000 bars per timeframe).
11. Price scaling: the EA scales by bid / `ReferencePrice` when the plan is built, the backtest by the entry
    minute's mid open / anchor: half a spread relative (BTC about 7e-5, gold about 2e-5 of the scaled distances).
    The level trailing scales the buffer by the position's open price (the ask for a buy): one spread relative.
    `ReferencePrice` must be the backtest's anchor price, otherwise every scaled distance is off by that ratio.

Present in v1.34 already (listed so that the list is complete; unchanged except item 15, changed by fix 10):

12. Reward test at equality (`TP_Mode` 1 with `TP_RR` = `MinRewardRisk`). The backtest's arithmetic is exact there
    (entry, stop and risk are multiples of one binary unit in these price ranges), so it accepts every such trade;
    the EA rounds the target to the tick and refuses the trade whenever the target rounds toward the entry
    ("reward/risk 1.00 < 1.00"): BTC cases 11, 20, 25 lost 11 of 34, 10 of 34 and 5 of 18 trades. With
    `MinRewardRisk = TP_RR - 0.05` (presets) and `min_rr = tp_rr - 0.05` (backtest) all three match trade for
    trade (34/34, 34/34, 18/18), and the published figures do not change (same trades, unseen and in-sample:
    `finish/tie/tie_effect_btc.txt`). Of the 15 combinations only BTC M5 SMA holds such a setup (case 20).
13. `TP_PREV_HUMP` target: the EA's anticipated target is `TP_Anticipation` x half spread higher than the
    backtest's: further from the entry for a buy, nearer to it for a sell (the EA measures the anticipated distance
    from the bid-chart hump extreme to the fill, the backtest from the mid extreme). BTC M15 SMA setup with
    anticipation 0.2 and a half spread of 5 USD (case 24 of `finish/rt`, `btc_51` of `parity/out/A_btc`): +1 USD on every
    trade, e.g. a sell of 2 Mar 2026 09:30 with backtest target 65208.80 and EA target 65209.80; |dR| <= 0.0038 on a
    target exit, no exit minute changed. None of the 15 combinations uses this mode.
14. A stop or target filled by the server on the first tick of a trigger bar that carries a new signal: the
    backtest makes no entry on its exit minute, the EA can enter on that tick (a trailing close at market is
    covered by `g_trailExitBar`, a server fill is not). Not seen in the harness.
15. Restart inside a trigger bar (v1.34 code, changed in v1.35 by fix 10 of `FIXES.md`). v1.34 evaluated the bar's
    signal again after a restart or re-init inside the bar and decided it a second time: a signal dropped at the bar
    open (a position was open, a filter or the reward test refused it) could be entered later in the bar, which the
    backtest, deciding at the bar open only, never does; and while the deal history was not available
    (`HistorySelect` failing, for example right after the terminal starts on another computer) `EnteredSinceBar()`
    could not see an earlier entry, so a signal already traded and closed inside the bar was entered a second time.
    v1.35 keeps the trigger bar whose signal was decided (evaluated as valid, then entered or refused) in terminal
    variable `LOMA_<magic>_D_0_<symbol>_<timeframe>` (one per magic number, symbol and trigger timeframe, e.g.
    `LOMA_26113001_D_0_XAUUSD_M2`) and does not decide that bar's signal again (journal "this bar's signal was already
    decided before a restart"); the deal-history check stays in front of it with its own line. A signal still waiting
    for algo trading to be switched on (every filter passed, `TradingAllowed()` false, tried again on every tick) is not
    decided yet: the variable is deleted while it waits, the deletion is saved to disk at once (so that it also holds
    after a terminal crash), and it is written again just before the order is sent, so a restart, re-init or crash
    during the wait decides the signal again, as v1.34 does. In the Strategy Tester, OnInit deletes the variable (a
    pass calls OnInit once), so a value left by an earlier pass cannot skip a signal.
    Measured (restart every 211 minutes at second 20, R and A erased, full hump replay; `restart/patcher`, again on the
    final file in `final/finisher` and on the last file in `last/patcher`): with the deal history missing for the 3
    ticks after each restart the bd96c372 file made 7 extra trades (BTC cases 03, 17, 23, 25 twice, gold 03 and 10),
    with it present 2 (BTC case 25: signal refused at the bar open by item 12, entered after a restart: 23 Jan 18:34:30
    and 23 Apr 18:48:30); the final and the last file none, 71 of 71 setups trade as without restarts in both. A re-init
    while the signal waits for algo trading (algo trading off on the first tick of every minute in which the run
    without restarts entered, on again from second 15, re-init at second 14; the reviewer's scenario, all 71 setups):
    the final and the last file make exactly the trades of bd96c372 (b2dea501, which held the bar while the signal
    waited, made only 83 of the 1,119 gold trades); the journal differs from bd96c372's only where the re-init fell into
    a bar whose signal had been refused at the bar open (a position was open): "already decided" instead of the same
    refusal a second time. A terminal crash at second 14 of that wait (the variables come back as last saved; the final
    reviewer's scenario, all 71 setups): the last file makes exactly the trades of bd96c372; the final file, which did
    not save the deletion, kept 3 of the 1,119 gold and 4 of the 3,453 BTC entries. Two charts with the same magic
    number on one symbol and different trigger timeframes (two EA instances in one simulated terminal, 64 gold pairs
    and 30 BTC pairs, both call orders): the last file trades as bd96c372, byte for byte; the final file, whose variable
    had no timeframe, skipped signals of a bar time the other chart had decided (gold 301 times, BTC 1,167, without any
    restart). Charts with the same magic number on one symbol and the same trigger timeframe share the variable (and
    their positions: the EA counts and trails the positions of its magic number and symbol), so give each chart its own
    magic number, as the presets do (header note). Remaining: the variable lives in the terminal; if it is lost too
    (erased, or a restart on another terminal inside the bar), the EA falls back to the v1.34 check. A signal that
    waited for algo trading and was then refused by a filter later in the bar (spread, session, news) is not kept
    either, so a re-init in the rest of that bar decides it again (code reading). An input change, re-attach or chart
    change inside the bar re-initialises the EA like a restart: that bar's signal is not decided again either; a change
    of `TriggerTimeframe` uses the new timeframe's variable, so the new timeframe's bar is decided on its own (measured:
    37 changes inside a decided bar, the last file as bd96c372 in all; the final file took the new timeframe's bar as
    decided in 18).
16. Time exits about one minute earlier, weekend and holiday closes: as described in the v1.34 header.

## Checks run on the last file

The last file (`last/XAUUSD_Loma_TrendPullback.mq5`, md5 3be59db21448e224c952af618237bb8f: the final file 156f018a with
fix 10 as finally made (the deletion of item 15 saved to disk at once, the trigger timeframe in the variable's name, the
header note on charts that share a magic number) and fix 11 (the explicit cast); outputs in `last/patcher/`, the
comparison listings in `last/patcher/checks/`, every figure in `FIXES.md`, "Checks run on the last file"):
- C++ shim compile (clang++ and g++, the flags of the v1.34 final check), the extended shim declaring
  `HistorySelectByPosition(ulong)` as MetaEditor does: 0 errors and the 2 pre-existing warnings, diagnostics identical to
  v1.34's; an error injected into each of the 28 code lines that differ from bd96c372 (7 of them changed since 156f018a)
  is caught by both compilers at that line (`last/patcher/cc/run_cc_out.txt`).
- Plain runs of the 71 shipped setups: trade files and journals byte-identical to 156f018a (and so to bd96c372); EA
  against the backtest unchanged (gold 16 of 16, BTC 52 of 55, the 3 others item 12); v1.34 with default inputs: 71 of
  71 identical.
- Restart every 211 minutes at second 20 with R and A erased (full hump replay), deal history missing for the 3 ticks
  after each restart and, separately, present (`MQL_TESTER` false during the restarts): trade files and journals
  byte-identical to 156f018a's runs, 71 of 71 each (71 of 71 setups trade as without restarts).
- Re-init while the signal waits for algo trading (all 71 setups): byte-identical to 156f018a's runs, the same trades as
  bd96c372 with and without the re-init (item 15).
- Terminal crash while the signal waits (the final reviewer's scenario, all 71 setups): the trades of bd96c372, 71 of
  71 (156f018a: 0 of 71); the reviewer's other five modes as before (item 15).
- Two EA instances with one magic number on one symbol in one simulated terminal, different trigger timeframes (gold
  128 runs, BTC 60): byte-identical to bd96c372's runs; a TriggerTimeframe change inside a decided bar (37 runs):
  byte-identical to bd96c372's (item 15).
- A stale decided-bar value before OnInit, OnTrade after every tick, other EAs' variables (with the new names):
  byte-identical to the runs without them and to 156f018a's runs.
- Parity check parts A and B (`last/patcher/parity`): all 813 EA output files (271 runs) and every comparison report
  identical to the final file's runs (part B from the final file's own 20 configs, since the inputs of its setup pick
  have been removed from `<scratchpad>/wf/btc2` by another job).

## Checks run on the final file

The final file (`final/XAUUSD_Loma_TrendPullback.mq5`, md5 156f018a42570cc037808d99b068c525: b2dea501 with fix 10
completed as in item 15, and the header notes; outputs in `final/finisher/`, summary
`final/finisher/report/summary.txt`):
- C++ shim compile (clang++ and g++, the flags of the v1.34 final check): diagnostics identical to v1.34 (own shim and
  extended shim), bd96c372, b2dea501 and e65dc0ba: 0 errors and the 2 pre-existing warnings; an error injected into
  each of the 24 changed code lines (against bd96c372) is caught by both compilers at that line
  (`final/finisher/cc/run_cc_out.txt`).
- Plain runs of the 71 shipped setups: trade files and journals byte-identical to bd96c372 (and to b2dea501); EA
  against the backtest unchanged (gold 16 of 16, BTC 52 of 55, the 3 others item 12); v1.34 with default inputs: 71 of
  71 identical.
- Restart every 211 minutes at second 20 with R and A erased (full hump replay), deal history missing for the 3 ticks
  after each restart and, separately, present: trade files and journals byte-identical to b2dea501's runs, 71 of 71
  each (71 of 71 setups trade as without restarts; bd96c372: 7 and 2 extra trades; no trailing move a minute late).
- Re-init while the signal waits for algo trading (the reviewer's scenario, all 71 setups): the same trades as
  bd96c372, with and without the re-init; the journal differs only by fix 10's line in the 14 re-inits that fell
  into a bar whose signal had been refused at the bar open (item 15).
- A stale decided-bar value before OnInit in the Strategy Tester: deleted by OnInit, 71 of 71 runs byte-identical to
  the run without it.
- The terminal-variable checks of the re-check (OnTrade after every tick, other EAs' variables): byte-identical to the
  b2dea501 runs.
- Parity check parts A and B (`final/finisher/parity`, the rebuild of `recheck/parity`): all 813 EA output files (271
  runs) and every comparison report identical to the bd96c372 runs.

After the restart fixes 9 and 10 of `FIXES.md` in their first form (restart-fixed file
`restart/XAUUSD_Loma_TrendPullback.mq5`, md5 b2dea501c395ed446825331f9fcb85b2; outputs in `restart/patcher/`, summary
`restart/patcher/report/summary.txt`):
- C++ shim compile (clang++ and g++, the flags of the v1.34 final check): diagnostics identical to v1.34 (own shim and
  extended shim) and to bd96c372, 0 errors and the 2 pre-existing warnings; an error injected into each of the 12
  changed code lines is caught by both compilers at that line (`restart/patcher/cc/run_cc_out.txt`).
- Plain runs of the 71 shipped setups (the harness of `recheck/rt`): trade files and journals byte-identical to
  bd96c372 (the new journal line appears only after a restart); EA against the backtest unchanged (gold 16 of 16, BTC
  52 of 55, the 3 others item 12); v1.34 with default inputs: 71 of 71 identical; stale trigger series (gold, BTC),
  failing requests and stops level 50 (gold) and the tie runs: byte-identical to bd96c372.
- Restart every 211 minutes at second 20 with R and A erased (full hump replay), deal history missing for the 3 ticks
  after each restart and, separately, present: 71 of 71 setups with trade files byte-identical to the runs without
  restarts (bd96c372: 7 and 2 extra trades); no trailing move a minute late (bd96c372: 30). Every journal difference
  is listed in `FIXES.md` fix 10, with the checks of the new terminal variable (OnTrade clean-up after every tick,
  variables of other EAs, a stale value before OnInit).
- Parity check parts A and B (`restart/patcher/parity`, the rebuild of `recheck/parity`): all 813 EA output files
  (271 runs) and every comparison report identical to the bd96c372 runs.

After the fixes of `FIXES.md` (fixed file, md5 bd96c3724532156a93d70db87e498bdb):
- C++ shim compile against v1.34 taken from git (5de5c52; the copy in `/workspace/master` then held the pre-fix v1.35):
  identical diagnostics with g++ and clang++, 0 errors and the 2 pre-existing warnings (`fix/cc/run_cc_out.txt`).
- Parity, regression (71 of 71 identical to v1.34) and the scenarios listed below, rerun on the fixed file
  (`fix/rt/`): trades and journals byte-identical to the runs of the pre-fix file.
- Tests of the fixes (spread exactly at the limit, steps lost in the entry minute, restarts with the `R` variable
  erased and the deal history missing) and the parity verifier's varying-spread gold run: `FIXES.md`.

Before the fixes:

- C++ shim compile (g++ and clang++, the flags of the v1.34 final check): diagnostics identical to v1.34 (the two
  pre-existing warnings), `finish/cc/run_cc.sh`; an injected error is caught (`finish/cc/neg`).
- Parity with the backtest (`finish/rt/out_*_cases.txt`): gold 16 of 16, BTC 52 of 55 trade for trade; the 3 others
  are item 12 and match with the preset rule (`finish/rt/out_btc_tie.txt`).
- v1.34 against v1.35 with default new inputs: 71 of 71 identical (`finish/rt/reg_*.txt`).
- Trigger series one bar stale on the first tick of every minute: gold 16 of 16, BTC 55 of 55 setups trade
  exactly as without it (`finish/rt/scen_*_lag.txt`).
- Restart every 211 minutes (between two ticks of a minute) with the terminal variables R and A erased and the
  hump state replayed: gold 16 of 16 (1,406 restarts per run) and BTC 54 of 55 setups trade exactly as without
  restarts (`finish/rt/scen_*_rst.txt`); the other one is BTC case 25 (item 15). The three item-12 setups with
  the preset rule: identical with and without restarts and 34/34, 34/34, 18/18 against the backtest
  (`finish/rt/scen_btc_tie_rst.txt`). The first run of this scenario (`implement/rt2/scen_*_rst.txt`) had 13 BTC
  setups killed and 4 extra trades: both were faults of the simulated terminal, fixed in `finish/rt/patch_shim.py`
  (indicator handles were never freed; `HistorySelect` returned no deals, so `EnteredSinceBar()` could not see an
  entry already made in the bar and the EA entered the same signal again after a restart).
- Broker stops level of 50 points (gold): 4,125 modification requests, none rejected, the skip line at most once
  per position (`finish/rt/scen_gold_stops.txt`).
- Trailing requests failing on the first tick of every 7th minute (gold): 607 failures; after 603 of 610 reported
  failures the stop was placed on the next tick of the same minute (the 5 s throttle), not a minute later; all
  684 backtest trades still made with the same exit minute, 678 within 0.02 R (`finish/rt/scen_gold_fail.txt`).
- No stop was ever loosened and no target changed in any run (request audit of the simulated terminal).
