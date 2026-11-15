# XAUUSD_Loma_TrendPullback.mq5 v1.35: fixes after verification

Paths are relative to the folder of this file (`v135/`). Line numbers: sections 1-8 refer to bd96c372, section 9 to
b2dea501, sections 10 and 11 to the last file.

| File | md5 |
|---|---|
| `before_fix.mq5` (the verified file, commit bd22d1d) | d2605330f75233bde03a1c7cb0ac08e6 |
| `XAUUSD_Loma_TrendPullback.mq5` (fixes 1-8; also the copy in `/workspace/master` and in both zips, commit 0b10db8) | bd96c3724532156a93d70db87e498bdb |
| `restart/XAUUSD_Loma_TrendPullback.mq5` (fixes 1-8 plus the restart fixes 9 and 10 in their first form) | b2dea501c395ed446825331f9fcb85b2 |
| `restart/reviewer/XAUUSD_Loma_TrendPullback_alt.mq5` (b2dea501 with the reviewer's change to fix 10) | e65dc0bac9639975346cb102b91a64ae |
| `final/XAUUSD_Loma_TrendPullback.mq5` (the final file: fixes 1-10, fix 10 in its third form: e65dc0ba plus the Strategy Tester guard and the header notes) | 156f018a42570cc037808d99b068c525 |
| `final/final-reviewer/rt_flush/v135.mq5` (156f018a with the final reviewer's flush after the deletion of fix 10) | 0d97c84b89c04432196557dddd6d58d5 |
| **`last/XAUUSD_Loma_TrendPullback.mq5`** (the last file: fixes 1-11; fix 10 as finally made: 156f018a plus the flush after the deletion, the trigger timeframe in the variable's name and the note on charts that share a magic number; fix 11: the explicit cast) | **3be59db21448e224c952af618237bb8f** |
| v1.34 (git 5de5c52, = `implement/v134.mq5`) | 3614ef90a3f15c64f3ddac60aadc314b |

Diff of the fixes: `fix/fix.diff` (47 changed lines). Full diff from v1.34: `fix/v134_to_fixed.diff`. Diff of the final
file against bd96c372: `final/finisher/final_vs_bd96.diff` (36 lines added, 3 of them replacing 2 header lines; 24
changed code lines: fix 9, fix 10 and the tester guard; version string and the 68 inputs unchanged); against b2dea501
and e65dc0ba: `final/finisher/final_vs_b2dea501.diff`, `final/finisher/final_vs_e65dc0.diff` (the latter: the guard,
2 code lines, and the header notes). Fixes 9 and 10 in their first form against bd96c372:
`restart/patcher/restart_fix.diff` (15 added lines). Diff of the last file against the final file:
`last/patcher/last_vs_156f018a.diff` (7 code lines: the variable's name with the trigger timeframe in its 3 places, the
flush after the deletion with its 2 braces, the cast; comments: the in-code comment on the variable, the two header
notes that name it, and the new note on charts that share a magic number); against bd96c372:
`last/patcher/last_vs_bd96.diff` (45 lines added, 3 removed); version string and the 68 inputs unchanged.

**Delivery note.** `/workspace/master/XAUUSD_Loma_TrendPullback.mq5` and `dist/Loma_*_v1_35.zip` hold the file of
fixes 1-8 (md5 bd96c372..., commit 0b10db8). The file to deliver is the last file, `last/XAUUSD_Loma_TrendPullback.mq5`
(md5 3be59db2...): fixes 1-8, fixes 9 and 10 (found by the re-check in `recheck/`; fix 10 completed after the review in
`restart/reviewer/` and again after the final review in `final/final-reviewer/`) and fix 11 (a compile-readiness
review of the final file). The final file `final/XAUUSD_Loma_TrendPullback.mq5` (md5 156f018a...) is superseded.
Nothing under `/workspace/master` was edited here, so the last file has to be copied there and the zips rebuilt before
delivery.

## Summary

| # | Reported defect | Verdict | Change |
|---|---|---|---|
| 1 | `SpreadOK` refuses a spread equal to `MaxSpread_Points` about half the time | real, reproduced | fixed: spread counted in whole points |
| 2 | CHANGES item 4 understates the bid-chart effect | real (wording) | CHANGES item 4 rewritten with the measured figures |
| 3 | CHANGES item 13: TP_PREV_HUMP sell target is nearer, not further | real (wording) | CHANGES item 13 rewritten |
| 4 | `BestSince` / HTF_CANDLE test `SERIES_SYNCHRONIZED` before requesting the series | plausible, not reproducible without MT5 | fixed: request first, then check |
| 5 | TRAIL_STEP leaves the entry M1 bar out of its history best | real, reproduced | fixed: history from the entry bar |
| 6 | `TrailRates` treats `Bars() == 0` as a short history | real (code reading) | fixed in `TrailRates` and in the PIVOTS branch |
| 7 | 1R fallback to the current SL can store a stop already moved past the entry | real (code reading), reproduced | fixed for the R8b systems; TRAIL_RISK unchanged |
| 8 | `StochTurnBars` has no upper limit | real (code reading) | fixed: OnInit accepts 1 .. 1000 |
| 9 | Fix 7 side effect (re-check): without 1R the M1 bar is marked done, a stop move after a restart waits a minute | real, reproduced | fixed: the bar stays open while 1R is not known |
| 10 | After a restart inside a trigger bar its signal is decided again; without the deal history a traded signal is entered twice (CHANGES item 15, v1.34 code) | real, reproduced | fixed: the decided bar is kept in a terminal variable per magic number, symbol and trigger timeframe (not while the signal waits for algo trading, and that deletion is saved to disk at once; deleted when a Strategy Tester pass starts) |
| 11 | `InitialRiskFromHistory` passes its `long` position id to `HistorySelectByPosition`, whose parameter MetaEditor declares `ulong` (compile-readiness review of the final file) | real (implicit sign conversion; no behaviour change) | fixed: explicit `(ulong)` cast; the C++ stand-in shims declare the parameter `ulong` |

Compile check (`fix/cc/run_cc.sh`, output `fix/cc/run_cc_out.txt`): clang++ and g++ with the flags of the v1.34 final
check give exactly the diagnostics of v1.34 (0 errors, the same 2 warnings: EVK.mqh switch-enum, unused `reason` in
OnDeinit), against v1.34 with its own shim, v1.34 with the extended shim and the pre-fix v1.35. The script that the
finisher and the reviewer used compares with `/workspace/master/XAUUSD_Loma_TrendPullback.mq5`, which then held the
pre-fix v1.35, so it was changed to take v1.34 from git. An injected error in the changed lines is caught (`fix/cc/neg`).
Fixes 9 and 10 in their first form: `restart/patcher/cc/run_cc.sh`, same result. The final file:
`final/finisher/cc/run_cc.sh`, same result, and an error injected into each of its 24 changed code lines is caught. The
last file: `last/patcher/cc/run_cc.sh`, with the extended shim declaring `HistorySelectByPosition(ulong)` as MetaEditor
does (fix 11): the diagnostics of v1.34, 0 errors and the same 2 warnings, and an error injected into each of its 28 code
lines that differ from bd96c372 (7 of them changed since 156f018a) is caught by both compilers at that line (last
section).

## 1. SpreadOK refuses a spread equal to MaxSpread_Points about half the time

**Verdict: real.** `(Ask() - Bid()) / (_Point * g_ptScale)` is not a whole number in binary floating point:
(5097.50 - 5096.90) / 0.01 = 60.00000000003638 > 60, so the EA refuses; the backtest tests `2 * hs > max_spread`, 0.6 >
0.6 is false, and enters. Whether the ratio lands above or below 60 depends on the price (300,000 random gold prices
here: 36% above, 64% below, never exactly 60; the verifier found 52% / 48% on the 2026 bids). v1.34 code.

**Change** (line 1601): `double spreadPts = MathRound((Ask() - Bid()) / _Point) / g_ptScale;`. The rounding error of
`(ask - bid) / point` is below 2e-9 points even for BTC at 100,000 USD, so `MathRound` gives the exact whole number of
points; dividing it by `g_ptScale` (a power of ten) gives exactly `MaxSpread_Points` at the limit for every quote
precision. The panel keeps the raw ratio (it prints it with `%.0f`). With default inputs this is the one place where
the fixed file trades differently from v1.34 (only when the spread is exactly at the limit).

**Tests.**
- Spread exactly at the limit in the simulated terminal (`MaxSpread_Points=15`, the harness's constant gold spread,
  16 gold setups, `fix/rt*/scen_gold_sp15.txt`): pre-fix 901 of 1,121 trades (542 journal lines "spread 15 > 15"),
  0 of 16 setups as the plain run; fixed 1,121 of 1,121, 16 of 16 setups trade for trade as the plain run, 0 refusals.
- The parity verifier's varying-spread gold run (FTMO table by hour, 49 setups, 2 Mar - 13 Nov 2026), rerun with the
  fixed file through the verifier's own driver (`fix/parity_ea/goldv_all49.txt`): the 15 refusals at 60 points are
  gone. 11 of them were backtest trades (2026-03-03 23:00, 11 M10 setups) that the EA now makes with the same entry
  minute and side; the other 4 are refused by the trading hours anyway (the spread is tested first). Same-entry
  trades 3,611 -> 3,622 of 3,744, same exit minute 3,562 -> 3,573, EA-only trades 87 -> 87, no trade lost.

## 2. CHANGES.md item 4 understates the bid-chart effect

**Verdict: real** (documentation). With a spread that changes over time, the MACD and Stochastic of the signals and
the hump extremes of the initial stop come from bid bars too, so signals and initial stops differ, not only trailing
levels; and the sentence "the harness uses a constant spread, so it does not measure this" no longer holds. I
reproduced the verifier's totals with my own script (3,611 same entries, 3,562 same exit minutes,
`fix/scripts/goldv_spread_check.py`) and the profit factors on the unseen months (16 May - 13 Nov 2026,
`fix/scripts/goldv_pf_0516.py` -> `fix/parity_ea/goldv_pf_0516.txt`): M10 ATR 1.440 -> 1.438, M10 percent 1.272 ->
1.276, M5 chandelier 1.216 -> 1.277, M5 hump 1.496 -> 1.522 (backtest -> EA; the fixed file gives the same values).

**Change:** CHANGES.md item 4 rewritten: every chart value (signals, initial stop and target, trailing levels, ATR,
best prices) is read from bid bars; identical with a constant spread; on the FTMO table 3.0% of the signals and about
3% of the trades differ either way and 1.3% of the matched trades exit in another minute; the profit factors above.
No code change: computing the indicators on mid prices is outside v1.35.

## 3. CHANGES.md item 13: the TP_PREV_HUMP target of a sell is nearer, not further

**Verdict: real** (documentation). From `hump_engine.simulate` (lines 185 and 239) and `BuildTradePlan`: with a
constant half spread hs, EA - backtest = +TP_Anticipation x hs for both sides (buy: EA = ref - hs - a(ref - o) + 2a
hs, backtest = ref - hs - a(ref - o) + a hs; sell: EA = ref + hs + a(o - ref), backtest = the same - a hs). Higher is
further for a buy and nearer for a sell. Confirmed on the verifier's output (`parity/out/A_btc/cmp.txt`, btc_51 M15
SMA, anticipation 0.2, hs 5 USD): +1.00 USD on all 32 trades, e.g. sell 2026-03-02 09:30 backtest 65208.80 / EA
65209.80, buy 2026-03-05 12:30 backtest 73866.36 / EA 73867.36.

**Change:** CHANGES.md item 13 rewritten ("higher than the backtest's: further from the entry for a buy, nearer to it
for a sell", with the example). No code change: v1.34 code, which the SPEC keeps byte for byte, none of the 15
combinations uses TP_PREV_HUMP, and the size is |dR| <= 0.0038 with no exit minute changed.

## 4. BestSince and the HTF_CANDLE level test SERIES_SYNCHRONIZED before requesting the series

**Verdict: plausible, fixed because the fix is harmless either way.** It cannot be reproduced here: there is no MT5
terminal, and the simulated terminal returns true for `SERIES_SYNCHRONIZED` on every timeframe. In MQL5 a series is
built when something requests it (a chart, an indicator handle, a `Copy*` / `i*` call), and `SeriesInfoInteger` only
reads its state; the documentation's history-loading example (`CheckLoadHistory`) calls `CopyTime` to start the build
before it waits on `SERIES_SYNCHRONIZED`. In the pre-fix file `BestSince` returned before its `CopyRates`, so on a
chart of another timeframe nothing in the EA requested M1 regularly, and every system that reads the best price
(ATR_ENTRY, PERCENT, PROFIT_LOCK, CHANDELIER, the level systems with `TrailStartR` > 0, and STEP's history part) would
stop without a journal line if the flag stayed false; HTF_CANDLE likewise for its higher series.

**Change.**
- `BestSince` (lines 2060-2072): `CopyRates` first, then `SERIES_SYNCHRONIZED`, and the bar of the current minute must
  be in the M1 series (`iTime(_Symbol, PERIOD_M1, 0) < m1` = not yet), which also proves the bar before it complete.
- HTF_CANDLE in `TrailLevel` (line 2238): `HTFBarCurrent` (its `iTime` requests the series) before `SERIES_SYNCHRONIZED`.
- Not changed: the same test on `TriggerTimeframe` in `TrailPosition` (line 2428), because the EA's MACD and
  Stochastic handles keep that series built, so the order does not matter there. The optional journal line after 5
  minutes of failed reads was not added (not needed for the fix).

**Tests.** Parity (16 gold, 55 BTC), regression and the finisher's lag, restart, fail and stops scenarios give
byte-identical trades (and journals) to the pre-fix file; in the simulated terminal the current M1 bar is always in
the series, so the new test never waits there.

## 5. TRAIL_STEP leaves the entry M1 bar out of its history best

**Verdict: real.** `from = entryBar + 60` read the best price from the minute after the entry bar only, so a step
reached in the entry minute and given back was lost for good after a failed modification (5 s pause) or a restart
inside that minute. The reference counts the entry bar: `hump_trail2.simulate_y` (kind 6, lines 151-158) moves the
step stop from j = e, and every other system of the EA counts the entry bar as a whole.

**Change** (line 2365): `datetime from = entryBar;` with the guard `if(m1 > from)` unchanged, so from the minute after
the entry the cached best includes the entry bar; inside the entry minute only live ticks count, as before.
CHANGES.md item 9 no longer lists this limitation and now says that the entry bar counts as a whole for every system
(if the fill came later in its M1 bar than the bar's first tick - algo trading off at that tick, a restart inside the
entry bar, or the few hundred milliseconds of `TryOpen`'s retries - the part before the fill counts too).

**Tests** (BTC STEP setups 48-50, trailing modifications made to fail inside the entry minute after the entry tick,
hook `run.failentry` of `fix/rt/drv_bt.cpp`):
- With the shipped step sizes (TrailStartR 0.5 and 1.5) no step is reached and given back inside an entry minute:
  both files trade as the plain run (3 of 3, `fix/rt*/scen_btc_fe.txt`).
- With steps of 0.1 R (`TrailStartR=0.1`; the run with failures against the run without, same file;
  `fix/rt*/cmp_btc_ts01fe_vs_ts01.txt`): the pre-fix file loses the step of 5 trades, which then run on to another
  exit (e.g. entry 2026-03-02 12:00, out at 12:13:15 instead of 12:01:15). The fixed file reads that step back on
  the first tick of the next minute for all 5: 2 then trade exactly as without failures, 3 were already through the
  step and are closed at market on that tick (0.04 to 0.12 R from the run without failures; the stop could not be
  placed earlier).
Parity, regression and all other scenarios are unchanged (the live ticks of the harness already see the entry
minute's extreme).

## 6. TrailRates treats Bars() == 0 as "history too short"

**Verdict: real.** `Bars()` returns 0 while a series is not formed or not synchronized; `TrailRates` then returned 0
("too short"), so `TrailPosition` returned true, the minute was marked done instead of retried (SPEC rule 11), and the
only shortage warning was spent on "the history has -1" (a later real shortage would go unreported). `EntryATR`
reaches `TrailRates` without any
`SERIES_SYNCHRONIZED` test. The PIVOTS branch of `TrailLevel` had the same pattern
(`MathMin(TRAIL_PIVOT_BARS, Bars() - 1)` -> `TrailBarsMissing(.., -1)`). Not reproducible in the simulated terminal
(its `Bars()` is never 0 after OnInit); verdict from the code and the documented meaning of `Bars() == 0`.

**Change.** `TrailRates` (lines 1991-1993): `Bars() <= 0` or not synchronized -> -1 (retry on the next tick); 0 only
for a real shortage. PIVOTS (lines 2207-2209): `Bars() <= 0` -> -1.

**Tests.** Parity, regression and scenarios unchanged (byte-identical).

## 7. The 1R fallback can store a stop that a v1.35 system already moved past the entry

**Verdict: real.** When the `R` terminal variable is missing (EA attached on another terminal or VPS, variables
erased) and `InitialRiskFromHistory` returns 0 (deal history not loaded yet), the pre-fix code stored |SL - open| for
good. After STEP or PROFIT_LOCK had moved the stop past the entry, that is a fraction of the real 1R (STEP at entry +
a stores a = TrailStartR x R, so the steps shrink to TrailStartR^2 x R).

**Change** (line 1804): for `TrailMode` other than TRAIL_RISK the current SL is used only while it is on the loss side
of the open price (`isSell ? sl > open : sl < open`); otherwise nothing is stored and the opening deal is looked up
again on the next tick (the position is not trailed until then). TRAIL_RISK is byte for byte the v1.34 code (SPEC).
Remaining limitation, now in CHANGES.md item 9: a loss-side stop that a system had already moved (chandelier, ATR,
percent, levels) is still taken as 1R.

**Tests** (restart every 211 minutes, the `R` variable erased, the deal history missing for the 2 ticks after each
restart, full hump replay; hook `run.nohist` of `fix/rt/drv_bt.cpp`):
- BTC STEP and PROFIT_LOCK (7 setups, `fix/rt*/scen_btc_rnh.txt`, `fix/rt*/cmp_btc_rnh_vs_plain.txt`): pre-fix 6 of
  7 setups trade as the plain run; setup 48 (M10 STEP) has 6 of 117 trades different (28.0 R in total against
  30.5 R) through a 1R taken from a stop already moved past the entry. Fixed: 7 of 7 trade for trade as the plain
  run.
- Gold (16 setups, hump, chandelier, percent, ATR): fixed and pre-fix identical (16 of 16): percent and ATR do not use
  1R, hump and chandelier only for their start threshold, which a position whose stop has moved has already passed.
  14 of 16 setups trade as the plain run; the other 2 have one extra trade
  each with both files: a signal entered a second time after a restart inside its entry bar, because
  `EnteredSinceBar()` (v1.34) cannot see the first entry while the deal history is missing. Not a reported defect and
  not changed with fixes 1-8; documented in CHANGES.md item 15 and fixed later (fix 10).

## 8. StochTurnBars has no upper limit

**Verdict: real** (code reading). With `StochTurnBars` above the bars the Stochastic has calculated, `CopyBuffer`
cannot return that many values, `StochTurnCheck` returns -1 and every signal stays "not ready" for good, with only the
"indicator data not up to date yet" journal line.

**Change** (OnInit, line 561): `StochTurnBars` must be 1 .. 1000 (the bound of the bar counts of `TrailParam`); the
message says so. The presets use 5.

## 9. Fix 7 side effect: an M1 bar without 1R is marked done (re-check)

**Verdict: real** (found and reproduced by the re-check: `recheck/rt/lost_minutes_rnh3.txt`, patch tested in
`recheck/rt_patch`). Since fix 7, when the `R` terminal variable is missing, the opening deal is not in the history
yet and the stop is already past the entry, nothing is stored, and `ManageOpenPositions` left the position with
`if(initRisk <= 0.0) continue;` (bd96c372 lines 1813-1814) without clearing `allDone`. The M1 bar was then marked
done (`g_trailBar = m1`), so when the deal came back on a later tick of the same minute the once-a-minute systems
waited for the next minute. Re-check scenario `_rnh3` (restart every 211 minutes at second 20, `R` and `A` erased,
deal history missing for the 3 ticks after the restart: seconds 30 and 45 and the next minute's first tick, full
hump replay): of the 91 trailing actions that the plain run made on the first tick after a restart minute, 30 came a
minute later or not at all (BTC 24 of 78, gold 6 of 13); no exit changed, one BTC trade (case 39, profit lock) had one
stop modification fewer. (Before fix 7 the current SL was stored at once: no tick lost, but a wrong 1R.)

**Change** (lines 1824-1829), the re-check's patch:
`if(initRisk <= 0.0) { if(TrailMode != TRAIL_RISK) allDone = false; continue; }`. While 1R is not known the M1 bar
stays open and is evaluated on the first tick on which the deal is found. TRAIL_RISK does not use `g_trailBar`; its
path is still `continue`.

**Tests** (`restart/patcher/rt` = the restart-fixed file, `restart/patcher/rt_base` = bd96c372, same harness and
driver as `recheck/rt`; every figure in `restart/patcher/report/summary.txt`):
- `_rnh3`: no trailing action late (bd96c372: 30). The 30 are made in the same minute, on the first tick with the deal
  history back (second 15, gold 6, BTC 24), the other 61 on the same tick as in the plain run. Trade files
  byte-identical to the plain run, 71 of 71 (with fix 10; the BTC case 39 trade has its 12 modifications again).
- `_rnh3d` (`_rnh3` with the variable of fix 10 erased at every restart as well): gold trades as with bd96c372 (its 2
  extra trades back), journals identical to bd96c372 except these 6 actions, made at second 15 of the same minute
  instead of the next minute. BTC: see fix 10.
- Plain runs, regression, the runs without restarts and parity: byte-identical (checks below).
- The final file (`final/finisher`, `MQL_TESTER` false during the restarts): `_rnh3` trade files and journals
  byte-identical to b2dea501's, 71 of 71; no trailing action late (gold 7 on the same tick, 6 later in the same minute;
  BTC 54 and 24).

## 10. A restart inside a trigger bar decides its signal again (CHANGES item 15, v1.34 code; re-check)

**Verdict: real** (reproduced by the re-check). After a restart or re-init inside a trigger bar `g_lastBarTime` is 0,
so the bar's signal is evaluated and decided again. `EnteredSinceBar()` stops only a signal that was entered, and only
while `HistorySelect` works: with the deal history not available yet (right after a terminal start), a signal already
traded and closed inside the bar was entered a second time; and a signal dropped at the bar open (a position was open,
a filter or the reward test refused it) could be entered later in the bar, which the backtest never does. Re-check
`_rnh3`: 7 extra trades (BTC cases 03, 17, 23, 25 twice, gold 03 and 10); with the deal history present (`_rst`) BTC
case 25 still had its 2 (signal refused at the bar open by item 12, entered after a restart at 23 Jan 18:34:30 and
23 Apr 18:48:30).

**Change, as finally made** (`last/XAUUSD_Loma_TrendPullback.mq5`, md5 3be59db2...: OnTick lines 786-799 and
870-884, OnInit lines 661-663, header NOTES). The forms before it: b2dea501 (`restart/patcher`, items 1 and 4 with the
name per magic number and symbol), e65dc0ba (`restart/reviewer`, item 2 without the flush), 156f018a (`final/finisher`,
item 3); the last file adds the flush of item 2 and the trigger timeframe of item 1 (both found by the final review in
`final/final-reviewer/`) and the note on charts that share a magic number (item 4).
1. The decided bar: when a bar's signal is evaluated as valid, the bar's open time is written to the terminal variable
   `LOMA_<magic>_D_0_<symbol>_<timeframe>` (`GVKey("D", 0) + "_" + _Symbol + "_" + TFName(TriggerTimeframe)`, e.g.
   `LOMA_26113001_D_0_XAUUSD_M2`; `TFName` is the EA's own "M2", "H1" helper of the journal lines, which also resolves
   `PERIOD_CURRENT` to the chart's timeframe), then `GlobalVariablesFlush`; a valid signal of the bar that variable
   holds is not decided again (journal "No trade: this bar's signal was already decided before a restart"). The
   deal-history check stays in front of it with its own line, as in v1.34. Two differences from the re-check's
   proposal: the history check keeps its line (the proposal printed the new line for both, which would have changed the
   journal of restarts that v1.34 already handled), and the name holds more than the magic number.
   - The symbol (b2dea501): the EA allows one magic number on several symbols (positions and the deal-history check are
     filtered by symbol and magic); with a name per magic number only, an EA on another symbol with the same magic would
     make this one skip a signal of the same bar time in normal running, without any restart. Between the 16 gold and
     55 BTC plain runs, 305 of the 880 pairs share at least one decided bar time (453 in all over the 10 months).
   - The trigger timeframe (final review, finding 2): with a name per magic number and symbol (156f018a), two charts
     with the same magic number on one symbol and different trigger timeframes made each other skip a signal of the
     same bar open time in normal running (an M10 bar's open time is also an M5 bar's), and a TriggerTimeframe change
     inside a decided bar made the new timeframe's bar of the same open time count as decided. The input default
     26113001 is the same on every chart; the shipped presets have 74 different magic numbers (checked in both zips).
     Between the plain runs of one symbol with different trigger timeframes, 51 of the 64 gold pairs share decided bar
     times (300 in all) and 477 of the 1,149 BTC pairs (3,053; `last/patcher/scripts/coincide.py`). Measured with two
     EA instances in one simulated terminal and with a timeframe change inside a bar: "Tests on the last file" below.
   - Charts with the same magic number on one symbol and the same trigger timeframe still share the variable, and they
     share their positions as well (the EA counts and trails the positions of its magic number and symbol, one at a
     time); a new header note says to give each chart its own magic number (item 4).
   - The name is at most 4 characters longer than in 156f018a ("_M30", "_MN1"). MT5 limits the names of terminal
     variables to 63 characters: with the 8-digit magic numbers of the presets and of the input default, symbol names of
     up to 41 characters fit (20-digit magic numbers: 29). Not testable here; no broker symbol of that length is known.
2. A signal that waits for algo trading (found by the review of b2dea501 in `restart/reviewer/`; its variant e65dc0ba,
   `restart/reviewer/alt_tradingallowed.diff`): when every filter has passed but `TradingAllowed()` is false (algo
   trading off in the terminal or for the EA, or the symbol's trade mode refuses that side), OnTick returns and tries
   again on the next tick, so the signal is not decided yet. b2dea501 kept the bar from the evaluation on, and a restart
   or re-init during the wait lost the signal, a trade that bd96c372 makes (and the backtest, which enters at the bar
   open). Now the variable of this bar is deleted while the signal waits, and the deletion is saved to disk at once
   (`GlobalVariablesFlush` after `GlobalVariableDel`, final review finding 1; the delete and the flush run once, on the
   first waiting tick, since the variable then no longer holds this bar). Without that flush (156f018a) an unclean exit
   during the wait (terminal crash, power loss, killed process) brings the variables back as last saved, which still
   hold this bar, so the signal that was never sent is skipped after the start: the reviewer's crash scenario (mode 3
   of `final/final-reviewer/drv_fr.cpp`) left 156f018a with 3 of bd96c372's 1,119 gold entries (and 80 others) and 4 of
   its 3,453 BTC entries (and 299 others). The variable is written again just before `TryOpen` (before the order, so a
   restart after it never sends it again; that write is flushed too). A signal that waited and was then refused by a
   filter on a later tick of the bar (spread, session, news) leaves no variable either, so a re-init in the rest of that
   bar decides it again, as v1.34 does (code reading; CHANGES item 15).
3. The Strategy Tester (review item 2): OnInit deletes this chart's variable (the name with the trigger timeframe) when
   `MQLInfoInteger(MQL_TESTER)` is set. A pass calls OnInit once, so this removes only a value left by an earlier pass
   (see "The Strategy Tester" below).
4. Header NOTES: the entry-parity note now says "After a restart or re-init inside the bar the signal is not decided
   again: the bar is kept in terminal variable LOMA_<magic>_D_0_<symbol>_<timeframe>, and an entry already made is also
   found in the deal history." (before: only the deal-history check); a note lists the terminal variables
   (`LOMA_<magic>_R_<ticket>` initial risk, `LOMA_<magic>_A_<ticket>` ATR at entry,
   `LOMA_<magic>_D_0_<symbol>_<timeframe>` with the example `LOMA_26113001_D_0_XAUUSD_M2`); and a new note: "Charts with
   the same magic number on one symbol and trigger timeframe share the decided trigger bar; give each chart its own magic
   number (the presets do)."

The simulated terminal reports `MQL_TESTER` = 1 (a tester run) and simulates a restart by calling OnDeinit and OnInit
again, so with the guard every simulated restart would erase the variable. The drivers of `final/finisher/rt` make
`MQL_TESTER` read false during a simulated restart (a restart is a live-terminal event); `run.rsttester=1` keeps it
true (control run below), `run.tester=0` makes the whole run a live terminal.

The questions of the re-check:
- **The OnTrade clean-up, OnDeinit.** OnTrade deletes `LOMA_<magic>_<kind>_<ticket>` only when the ticket part is above
  0 and no position has that ticket; the ticket part of the new name is `0_<symbol>_<timeframe>` (`0_<symbol>` before
  the last file), which `StringToInteger` reads as 0, so it is kept. OnDeinit deletes no terminal variable
  (`ObjectsDeleteAll` removes chart objects); EVK.mqh uses none. Test (driver hook `run.ontrade`: OnTrade after every
  OnTick; the simulated terminal never calls it otherwise): `_rnh3ot` (116 million calls) is byte-identical to `_rnh3`,
  trades and journals, 71 of 71; the variable was never deleted, there or in the 71 plain runs of `_gvo` (another 116
  million calls). Again on the final file (`final/finisher`): `_rnh3ot` and `_gvo` byte-identical to `_rnh3` and to the
  plain run, and to b2dea501's runs, 71 of 71 each, with the same call counts and no variable deleted. On the last file
  (`last/patcher/rt_hooks`: the same driver with its own key and the other EAs' names written with the trigger
  timeframe): gold `_rnh3ot` (19 million calls) byte-identical to the last file's `_rnh3` and to the final file's
  `_rnh3ot`, 16 of 16, and the 71 `_gvo` runs (116 million calls) byte-identical to the plain run and to the final
  file's `_gvo`; the variable was never deleted.
- **A different bar.** The variable holds the open time of the decided bar and is compared for equality with the bar
  being evaluated; it is written only for a valid signal. Every "already decided" line of the scenarios (gold 80 and
  34, BTC 375 and 247 in `_rnh3` and `_rst`) comes after a restart inside a bar whose valid signal had been decided
  before the restart, in a bar the plain run decided too (`restart/patcher/scripts/decided_check.py`); without
  restarts the line never appears.
- **Several EAs on one terminal.** The name holds the magic number, the symbol and (since the last file) the trigger
  timeframe. `_gvo` (driver hook `run.gvother`): before every tick the variables of other EAs were set to this tick's
  trigger bar: magic + 1, magic x 10 and magic / 10 (names that begin like this one or with which it begins), the same
  magic on the other symbol, and the name without the symbol (the re-check's proposal). 71 of 71 setups byte-identical
  to the plain run (trades and journal), and this EA's OnTrade deleted none of those variables (the same on the final
  file). On the last file the other EAs' names carry a trigger timeframe too, and two more were set: the same magic
  number and symbol with another trigger timeframe (M10, or M5 for the M5 setups) and the final file's name without a
  timeframe: again 71 of 71 byte-identical to the plain run, none deleted. Two real EA instances with one magic number
  on one symbol: "Tests on the last file" below. The tester guard deletes only this EA's own name
  (`GVKey("D", 0) + "_" + _Symbol + "_" + TFName(TriggerTimeframe)`).
- **The Strategy Tester.** MT5 emulates the terminal variables in the testing agent, apart from the terminal's own
  (MQL5 Reference, Testing Trading Strategies, "Global Variables of the Client Terminal"). A pass calls OnInit once, so
  within a pass the variable only holds bars decided in that pass, and each bar is decided once. Whether an agent keeps
  the emulated variables from one pass to the next is not documented (not testable here). If it did, the stale value
  is the previous pass's last decided bar; each decided signal overwrites it, so it can stop at most the new pass's
  first decided signal, and only if that signal is on exactly that bar. Test (`restart/patcher/scripts/seed_test.py`,
  driver hook `run.gvseed`: the EA's variable set before OnInit): with the plain run's last decided bar (what a pass
  over the same period leaves behind) 71 of 71 runs are byte-identical to the plain run; with its first decided bar
  (the degenerate case) that one signal is skipped in each of the 71 runs: 36 lose that trade, 1 trades a later
  signal instead, 34 keep their trades (the signal was refused anyway). That was b2dea501. The final file deletes the
  variable in OnInit when `MQL_TESTER` is set (item 3), which removes even that: the same test on the final file
  (`final/finisher/scripts/seed_test2.py`, `MQL_TESTER` true) gives 71 of 71 runs byte-identical to the plain run with
  either value, and not one "already decided" line; with `MQL_TESTER` false for the whole run (a live terminal, where
  the guard does not act) the runs are byte-identical to b2dea501's, 71 of 71 with either value. On the last file
  (`last/patcher/rt_hooks`, the driver's hook seeding the name with the trigger timeframe, the guard deleting that name):
  `MQL_TESTER` true: 71 of 71 byte-identical to the plain run with either value, no "already decided" line; false:
  the first decided bar's signal skipped in 71 of 71 runs (34 trade files unchanged), the last one's in none; all
  4 x 71 runs byte-identical to the final file's.

**Tests of the first form** (b2dea501: `restart/patcher/rt` = the restart-fixed file, `restart/patcher/rt_base` =
bd96c372; summary and every listing in `restart/patcher/report/`):
- `_rnh3` (the re-check's scenario: restart every 211 minutes at second 20, `R` and `A` erased, deal history missing
  for 3 ticks, full hump replay): trade files byte-identical to the plain run, 71 of 71 (bd96c372: 64; its 7 extra
  trades and the BTC case 39 trade with one modification fewer). Every journal difference against the plain run
  (`classify_*_rnh3.txt`): the OnInit lines of the restarts (gold 89,984, BTC 459,140); the bar's signal line printed
  again when it is evaluated after a restart, and the higher-timeframe filter refusal with it (gold 126 + 46, BTC
  504 + 129); "already decided" (80, 375); the 30 trailing moves of fix 9 at second 15 instead of second 0 of the
  same minute; and lines of the warm-up weeks before any comparison (gold setups 02 and 14 on 14 Jan, 558 lines; 24
  BTC setups up to 26 Feb, 54,780 lines): "indicator data not ready" warnings and retries, whose timer a restart
  resets, and hump-state lines of the catch-up replay printed at other times. The warm-up lines are the same set in
  `_rst` and in the bd96c372 runs (there with 1,335 more BTC and 562 more gold lines of the extra trades and lost
  moves): not from these fixes.
- `_rst` (the same with the deal history present): trade files byte-identical to the plain run, 71 of 71 (bd96c372:
  70, BTC case 25). Journal differences: as in `_rnh3` without the moved actions, with "already decided" 34 and 247 and
  the v1.34 line "already traded (found in the deal history)" 46 and 128 (as with bd96c372).
- `_rnh3d` (`_rnh3` with this variable erased at every restart as well): the 7 extra trades are back (gold 14 of 16,
  BTC 51 of 55 as the plain run): the variable is what stops them; without it the EA falls back to the v1.34 check.
  Against bd96c372's `_rnh3`, only fix 9's 30 trailing moves differ (gold 6, BTC 24, one of which bd96c372 never made).
- Without restarts (71 plain runs, stale trigger series, failing requests, stops level, tie runs): byte-identical to
  bd96c372, the new line never appears; regression 71 of 71; parity identical (checks below).

**Tests on the final file** (`final/finisher/`: `rt` = the final file, `rt_bd96` = bd96c372 built with the same
drivers; every figure in `final/finisher/report/summary.txt`):
- Re-init while the signal waits for algo trading (the reviewer's scenario, `restart/reviewer/scripts/offscen.py` with
  its driver hooks `run.offlist` / `run.offrestart`: algo trading off on the first tick of every minute in which the
  plain run entered, on again from second 15; `_offc` without a re-init, `_offr` with a re-init (OnDeinit / OnInit) at
  second 14; full hump replay), all 71 setups (the reviewer ran 16 gold and 10 BTC): trade files byte-identical to
  bd96c372's in both, 71 of 71 (gold 1,119 and 1,119 trades, BTC 3,453 and 3,453), and the same counters. Of the
  4,604 re-inits, 4,590 came while the signal waited; there the journals are identical to bd96c372's, as are all
  `_offc` journals (71 of 71). The other 14 re-inits (gold 5 in 4 setups, BTC 9 in 8) fell into a bar whose signal
  had been refused at the bar open ("a position is already open (max 1)": an entry delayed to second 15 had left its
  position open longer, e.g. gold 03, 18 Aug, entry 11:05:15 still open at the 16:10 bar), so it was decided: there
  the final file prints "this bar's signal was already decided before a restart" where bd96c372 decides the signal a
  second time and prints the refusal again (`scripts/offdiff.py`); no trade differs. So the `_offr` journals are
  byte-identical to bd96c372's in 59 of 71 setups, and the 12 others differ only by those 14 lines of fix 10. The
  outputs are byte-identical to the reviewer's runs of e65dc0ba (16 gold, 10 BTC setups), and the bd96c372 build's to
  the reviewer's bd96c372 runs. b2dea501 kept 83 of 1,119 gold and 65 of 707 BTC trades (10 setups) in `_offr`
  (reviewer's runs in `restart/reviewer/rt`).
- `_rnh3` and `_rst` (`MQL_TESTER` false during the restarts): trade files and journals byte-identical to b2dea501's,
  71 of 71 each, so every figure of the first form above holds: 71 of 71 setups trade as the plain run (bd96c372: 64
  and 70, its 7 and 2 extra trades), no trailing action late, "already decided" gold 80 and 34, BTC 375 and 247, each
  after a restart inside a bar whose valid signal was decided before it (`scripts/decided_check.py`).
- Control with `MQL_TESTER` kept true during the restarts (`_rnh3t` = `_rnh3` with `run.rsttester=1`): byte-identical
  to b2dea501's `_rnh3d` (the variable erased at every restart), 71 of 71: the guard then deletes the variable at every
  simulated restart and bd96c372's 7 extra trades come back (gold 14 of 16, BTC 51 of 55 as the plain run). This is why
  the restart scenarios run with `MQL_TESTER` false.
- A stale value before OnInit: see "The Strategy Tester" above.
- Without restarts: the plain runs are byte-identical to bd96c372's, regression and parity unchanged (checks below).

**Tests on the last file** (fix 10 as finally made; `last/patcher/`: `rt` = the last file with the finisher's harness and
drivers, `rt_hooks` = the same driver with its hooks writing the names with the trigger timeframe, `fr` = the final
reviewer's crash driver, `two` = two EA instances in one simulated terminal; the runtime shims declare
`HistorySelectByPosition(ulong)` (fix 11); comparison listings in `last/patcher/checks/`):
- A terminal crash while the signal waits for algo trading (final review finding 1; the reviewer's
  `final/final-reviewer/drv_fr.cpp` and configs `final/final-reviewer/fr_out`, all 71 setups, `fr/run_fr.py`, output
  `fr/fr_all.txt`): algo trading off on the first tick of every minute in which the plain run entered; mode 3 = a
  crash at second 14 (the terminal variables come back as last flushed), then a terminal restart, 4,604 crashes. Trade
  files byte-identical to bd96c372's, 71 of 71 (4,572 trades; 156f018a: 0 of 71, see item 2); trades and journals
  byte-identical to the reviewer's run of the flush variant 0d97c84b, 71 of 71; at none of the crashes did the
  variables in memory differ from the saved ones. The reviewer's other modes (control without re-init; re-init at
  second 14; algo trading still off at second 15; re-init by an input change; spread too wide after the wait, re-init
  at second 20): trade files byte-identical to bd96c372's and trades and journals byte-identical to the flush variant's
  and to 156f018a's, 71 of 71 in each mode.
- Two EA instances in one simulated terminal (`two/drv_two.cpp`: the translated EA compiled twice, in two C++
  namespaces; both share the terminal: bars, broker, positions, deal history, terminal variables; on every tick the
  broker, then A's OnTick, then B's; a position belongs to the instance whose OnTick opened it, a journal line to the
  instance that printed it; A's tickets from 1000, B's from 500000; `two/run_pairs.py`). Checks of the driver: one
  instance alone reproduces the drv_bt plain run byte for byte (bd96c372, 156f018a and the last file); two instances
  with two magic numbers (777 and 778) on fixed ticks reproduce each instance's solo run byte for byte (B's tickets
  read as 1000 + k), 128 of 128 instances (the 64 gold pairs with different trigger timeframes).
  - One magic number (777, as every harness setup) on one symbol with different trigger timeframes, every gold pair
    (M5 and M10: 64 pairs, each in both call orders, 128 runs): the last file's runs are byte-identical to bd96c372's
    (no decided-bar variable), both instances' trades and journals, 128 of 128, and never print "already decided";
    156f018a's runs equal bd96c372's in 47 of 128 only: in 81 runs one instance printed "this bar's signal was already
    decided before a restart" (301 lines, no restart anywhere: the other instance had decided a bar of the same open
    time) and in 41 runs the trades differ (17,182 trades against 17,325). BTC, the 30 pairs with different trigger
    timeframes that share the most decided bars (M2 to M30), both call orders (60 runs): the last file byte-identical to
    bd96c372 in 60 of 60, no "already decided" line; 156f018a in 3 of 60 (1,167 lines in 57 runs, trades different in 22
    runs: 7,701 against 7,854). Outputs: `two/pairs_gold_difftf.txt`, `two/pairs_btc_top30.txt`.
  - One magic number and the same trigger timeframe (all 56 gold pairs M5/M5 and M10/M10): the last file and 156f018a
    byte-identical, 56 of 56: the instances share the variable (1,406 "already decided" lines in 53 pairs, 6,645 trades
    against bd96c372's 6,991), as the new header note says; `two/pairs_gold_sametf.txt`.
- TriggerTimeframe changed inside a decided bar (`two/tfswitch.py`; driver hook `run.switchat` / `run.switchtf`:
  OnDeinit(REASON_PARAMETERS) and OnInit with the other timeframe at second 20 of the bar, the EA's globals kept,
  `MQL_TESTER` false meanwhile; full hump replay): for each of the 16 gold setups, up to 3 of the bar times it decides
  both on its own trigger timeframe and on the other one (M5 <-> M10; 54 such bars, 37 runs): the last file's runs are
  byte-identical to bd96c372's, 37 of 37; 156f018a's in 19: in the other 18 it printed "already decided" for the new
  timeframe's bar right after the change, where bd96c372 and the last file decided it (17 refused outside the trading
  hours, 1 entered: setup 08 changed to M5 at 2026.10.15 16:20, a buy); in the 19 runs where the old timeframe's
  signal had been entered, all three found that entry in the deal history first. Output `two/tfswitch_gold.txt`.
- Restart scenarios with `MQL_TESTER` false during the restarts, `_rnh3` and `_rst`: trade files and journals
  byte-identical to 156f018a's, 71 of 71 each (`checks/c_*.txt`), so 71 of 71 setups trade as the plain run in both;
  no journal line differs (the variable's name is never printed).
- Re-init while the signal waits for algo trading (`_offc`, `_offr`, all 71 setups): trade files and journals
  byte-identical to 156f018a's, 71 of 71 each; against bd96c372: trade files identical, 71 of 71 in both, journals
  identical except the same 14 lines in 12 setups of `_offr` as with 156f018a (fix 10's line where the re-init fell
  into a bar whose signal had been refused at the bar open; `final/finisher/scripts/offdiff.py`: no other difference).
- A stale value before OnInit, OnTrade after every tick, other EAs' variables: the questions above.
- Without restarts: the plain runs are byte-identical to 156f018a's, regression and parity unchanged (checks below).

## 11. HistorySelectByPosition is given a long position id (compile-readiness review)

**Verdict: real** (compile readiness; no change in behaviour). `InitialRiskFromHistory(const long positionId)` (v1.34
code) passed its `long` id to `HistorySelectByPosition`, whose parameter MetaEditor declares `ulong` (finding of a
compile-readiness review of the final file): an implicit signed-to-unsigned conversion, which a compiler may report.
The id is a position identifier (a positive number), so the value passed is the same either way.

**Change** (line 1787): `if(!HistorySelectByPosition((ulong)positionId))`. The C++ stand-in shims declared the parameter
`long`, so their compile check could not see the conversion; they now declare it `ulong` as MetaEditor does: the
compile shim `last/patcher/cc/mql5_shim_ext.h` and the runtime shims of `last/patcher/{rt,rt_hooks,fr,parity/ea,two}`
(`HistorySelectByPosition(ulong id)`, same behaviour). v1.34's own shim (`mql5_shim_v134.h`) is left as it was.

**Tests** (`last/patcher/cc/run_cc.sh`, output `last/patcher/cc/run_cc_out.txt`): with the `ulong` declaration the last
file gives exactly the diagnostics of v1.34 (0 errors, the 2 warnings), while v1.34, bd96c372 and 156f018a each get one
more warning, at their `HistorySelectByPosition(positionId)` line (clang "implicit conversion changes signedness: 'const
long' to 'ulong'", g++ "conversion to 'ulong' from 'long int' may change the sign of the result", both
`-Wsign-conversion`); with the old `long` declaration it is the other way round (the cast is converted back: one warning
for the last file, none for the others). An error injected into the line is caught by both compilers. At run time the
last file's outputs are byte-identical to 156f018a's in every scenario above and below, among them `_rnh3`, where the
deal history is missing for 3 ticks after each of the 137,281 restarts of the 71 runs (411,843 ticks) and
`InitialRiskFromHistory` is called until the opening deal is back. Not checked here: the MQL5 Reference online
(mql5.com cannot be reached from this session); as far as I remember, the reference lists the parameter as
`long position_id`, so the first MetaEditor compile should confirm which it is. Either way the call compiles and passes
the same value: with a `long` declaration the explicit `ulong` is converted back.

## Checks run on the fixed file

- Compile: see above (`fix/cc/run_cc_out.txt`).
- Parity with the backtest (`fix/rt/out_gold_cases.txt`, `fix/rt/out_btc_cases.txt`): gold 16 of 16, BTC 52 of 55
  (the 3 others are CHANGES item 12); every trade file and journal is byte-identical to the pre-fix run
  (`finish/rt/out_*`).
- v1.34 against the fixed v1.35 with default new inputs (`fix/rt/reg_*.txt`): 71 of 71 identical, trades and journal
  (1,113 gold and 3,394 BTC trades).
- The finisher's scenarios on the fixed file (`fix/rt/scen_*.txt`): stale trigger series (gold 16/16, BTC 55/55 as the
  plain run), restart with R and A erased and full hump replay (gold 16/16, BTC 54/55, the other is CHANGES item 15,
  as before), failing requests (gold 9/16,
  as before), stops level 50 (gold 13/16, as before); trade files and journals byte-identical to the pre-fix runs.
  The tie runs (BTC 11, 20, 25 with `MinRewardRisk = TP_RR - 0.05`, plain and with restarts, `fix/rt/out_btc_tie.txt`):
  34/34, 34/34, 18/18 against the backtest, byte-identical to the pre-fix runs.
- New scenarios for fixes 1, 5 and 7: above (`fix/rt/scen_*_{sp15,rnh,fe,ts01,ts01fe}.txt`,
  `fix/rt_pre/...` for the pre-fix file).
- The parity verifier's varying-spread gold run, 49 setups, rerun on the fixed file (`fix/parity_ea/goldv_all49.txt`).

## Checks run on the restart-fixed file (fixes 9 and 10 in their first form)

`restart/XAUUSD_Loma_TrendPullback.mq5`, md5 b2dea501c395ed446825331f9fcb85b2 = bd96c372 + fixes 9 and 10 in their
first form (15 added lines). Scripts and outputs in `restart/patcher/`; every figure below is in `restart/patcher/report/summary.txt`.
- Compile (`cc/run_cc.sh`, output `cc/run_cc_out.txt`): clang++ and g++ with the flags of the v1.34 final check give
  the diagnostics of v1.34 (own shim and extended shim) and of bd96c372: 0 errors, the same 2 warnings. An error
  injected into each of the 12 changed code lines (`cc/neg/`) fails both compilers with one error at that line.
- Simulated terminal (`rt/`, the harness, driver and shim of `recheck/rt`; the driver has three test hooks, off by
  default: `run.ontrade`, `run.gvother`, `run.gvseed`; the bd96c372 build in `rt_base/` reproduces the re-check's
  plain runs byte for byte):
  - plain runs, 16 gold and 55 BTC shipped setups: trade files and journals byte-identical to bd96c372, 71 of 71 (no
    journal line added); EA against the backtest unchanged (gold 16 of 16, BTC 52 of 55, the 3 others CHANGES item 12);
  - v1.34 against the restart-fixed file, default new inputs: 71 of 71 identical (1,113 gold, 3,394 BTC trades);
  - no-restart scenarios (stale trigger series gold and BTC, failing requests and stops level 50 gold, the tie runs
    BTC 11, 20, 25): byte-identical to bd96c372;
  - restart scenarios `_rnh3`, `_rst`, `_rnh3ot`, `_rnh3d`, `_gvo` and the stale-value test: fixes 9 and 10 above.
- Parity check parts A and B (`parity/`, the rebuild of `recheck/parity` with this file: part A gold and BTC in both
  tick orders and gold with the FTMO spread table; part B BTC M30 turn filter with price scaling, main and preset): all 813
  EA output files (trades, requests, journals of 271 runs) and every comparison report identical to the re-check's
  bd96c372 runs.

## Checks run on the final file

`final/XAUUSD_Loma_TrendPullback.mq5`, md5 156f018a42570cc037808d99b068c525 = e65dc0ba (b2dea501 with the reviewer's
change to fix 10) + the Strategy Tester guard in OnInit (2 code lines and a comment) + the header notes; version 1.35,
the same 68 inputs. Scripts and outputs in `final/finisher/`; every figure below is in `final/finisher/report/summary.txt`.
- Compile (`cc/run_cc.sh`, output `cc/run_cc_out.txt`): clang++ and g++ with the flags of the v1.34 final check give the
  diagnostics of v1.34 (own shim and extended shim), bd96c372, b2dea501 and e65dc0ba: 0 errors, the same 2 warnings
  (EVK.mqh switch-enum, unused `reason` in OnDeinit). An error injected into each of the 24 changed code lines against
  bd96c372 (`cc/neg/`: the guard 2, fix 10 18, fix 9 4) fails both compilers with one error at that line.
- Simulated terminal (`rt/`: the harness and shim of `restart/patcher/rt`; `rt/drv_bt.cpp` = the patcher's driver with
  its hooks, `rt/drv_rev.cpp` = the reviewer's with `run.offlist` / `run.offrestart`, both changed only so that
  `MQL_TESTER` reads false during a simulated restart (`run.rsttester=1`: true) and `run.tester=0` makes a whole run a
  live terminal; `rt_bd96/` = the same drivers built with bd96c372):
  - plain runs (`MQL_TESTER` true), 16 gold and 55 BTC shipped setups: trade files and journals byte-identical to
    bd96c372's (`restart/patcher/rt_base`, and the re-check's `recheck/rt`), 71 of 71, and to b2dea501's; the configs
    and bar files are the same; EA against the backtest unchanged (gold 16 of 16, BTC 52 of 55, the 3 others CHANGES
    item 12); v1.34 against the final file, default new inputs: 71 of 71 identical (1,113 gold, 3,394 BTC trades);
  - restart scenarios with `MQL_TESTER` false during the restarts: `_rnh3` and `_rst` byte-identical to b2dea501's
    (trades and journals), 71 of 71 each: bd96c372's 7 extra trades gone, no trailing minute lost; the control with
    `MQL_TESTER` true during the restarts equals b2dea501's `_rnh3d`, 71 of 71 (fix 10 above);
  - re-init while the signal waits for algo trading (`restart/reviewer/scripts/offscen.py`, all 71 setups): trade
    files byte-identical to bd96c372's, 71 of 71 with and without the re-init; journals identical except 14 lines in
    12 setups of the re-init run, fix 10's line where the re-init fell into a bar whose signal had been refused at the
    bar open (fix 10 above);
  - stale value before OnInit, `MQL_TESTER` true: 71 of 71 runs byte-identical to the plain run with the first and with
    the last decided bar seeded; with `MQL_TESTER` false: byte-identical to b2dea501's runs (fix 10 above);
  - `_gvo` and `_rnh3ot`: byte-identical to the plain run and to `_rnh3`, and to b2dea501's runs, 71 of 71; OnTrade
    deleted neither this EA's variable nor the other EAs' (fix 10 above).
- Parity check parts A and B (`parity/`, the rebuild of `restart/patcher/parity` with the final file): all 813 EA output
  files (trades, requests, journals of 271 runs) and every comparison report identical to the re-check's bd96c372 runs
  (`recheck/parity`).

## Checks run on the last file

`last/XAUUSD_Loma_TrendPullback.mq5`, md5 3be59db21448e224c952af618237bb8f = the final file 156f018a + fix 10 as finally
made (the flush after the deletion while a signal waits for algo trading; the trigger timeframe in the variable's name,
`LOMA_<magic>_D_0_<symbol>_<timeframe>`; the header note on charts that share a magic number) + fix 11 (the explicit
`(ulong)` cast); version 1.35, the same 68 inputs. Scripts and outputs in `last/patcher/` (`chain1.sh`, `chain2.sh`,
`chain3.sh` ran everything; `checks/` holds the comparison listings; the large output files that are byte-identical to
the final file's were deleted afterwards, their md5 are in `last/patcher/md5/`).
- (a) Compile (`cc/run_cc.sh`, output `cc/run_cc_out.txt`; clang++ and g++ with the flags of the v1.34 final check; the
  extended shim declares `HistorySelectByPosition(ulong)` as MetaEditor does): 0 errors and the 2 warnings of v1.34
  (EVK.mqh switch-enum, unused `reason` in OnDeinit), diagnostics identical to v1.34 with its own shim and with the
  earlier extended shim, and to 156f018a with the earlier shim. With the `ulong` declaration v1.34, bd96c372 and
  156f018a get one more warning each (the conversion of fix 11); with the earlier `long` declaration the last file
  does. An error injected into each of the 28 code lines that differ from bd96c372 (the 7 that differ from 156f018a
  among them) fails both compilers with an error at that line, 28 of 28.
- (b) Plain runs of the 71 shipped setups (`rt/`, `harness.py cases`): trade files, journals, configs and bar files
  byte-identical to 156f018a's (`final/finisher/rt`), 71 of 71, and so to bd96c372's; EA against the backtest
  unchanged (the harness reports are identical: gold 16 of 16, BTC 52 of 55, the 3 others CHANGES item 12). v1.34
  against the last file with default new inputs (`harness.py regress`): 71 of 71 identical, trades and journal (1,113
  gold, 3,394 BTC trades), every file byte-identical to the final file's regression run.
- (c) Restarts (`MQL_TESTER` false during the restarts): `_rnh3` and `_rst` trade files and journals byte-identical to
  156f018a's, 71 of 71 each (71 of 71 setups trade as the plain run in both); no journal line changed by the new name.
  Re-init while the signal waits for algo trading (`_offc`, `_offr`): byte-identical to 156f018a's, 71 of 71 each;
  trades identical to bd96c372's (fix 10 above).
- (d) Terminal crash while the signal waits (the final reviewer's mode 3): trade files byte-identical to bd96c372's, 71
  of 71 (156f018a: 0 of 71); trades and journals byte-identical to the reviewer's flush variant in all six of the
  reviewer's modes, 71 of 71 each (fix 10 above).
- (e) Two EA instances with one magic number on one symbol in one simulated terminal: with different trigger timeframes
  the last file's runs are byte-identical to bd96c372's (gold 128 of 128 runs, BTC 60 of 60), 156f018a's skipped
  signals in 81 and 57 of them; with the same trigger timeframe the instances share the variable, as the header note
  says (56 of 56 gold pairs byte-identical to 156f018a). TriggerTimeframe changed inside a decided bar: byte-identical to
  bd96c372, 37 of 37 (156f018a skipped the new timeframe's signal in 18). Driver checks: 128 of 128 instances with two
  magic numbers reproduce their solo runs (fix 10 above).
- (f) Parity check parts A and B (`parity/`, the finisher's `final/finisher/parity` rebuilt with the last file): all 813
  EA output files (trades, requests, journals of 271 runs) and every comparison report byte-identical to the final
  file's (run times removed; `checks/f_parity.txt`), so to the bd96c372 runs of `recheck/parity`. Part A ran its own
  configs as before; part B (`parity/partB_cfg.py`) ran the finisher's 20 part-B configs unchanged, because the
  inputs of its setup pick (`<scratchpad>/wf/btc2/wf_M30.npy` and `wf_M30_params.pkl`) have since been removed from
  that folder by another job.
- Further checks of the new name: the stale value before OnInit (tester and live), OnTrade after every tick and the
  other EAs' variables (`_gvo` with the names of the last file, among them the same magic number and symbol with another
  trigger timeframe and the final file's name without a timeframe): byte-identical to the plain runs, to `_rnh3` and to
  the final file's runs, 71 of 71 (gold `_rnh3ot` 16 of 16); OnTrade deleted no variable (fix 10 above).
