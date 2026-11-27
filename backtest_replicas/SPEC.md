# XPW v2.8 (trailing-TP variant) + FlashGold Direction Filter: Python replica spec

Goal: reproduce, bar for bar on historical data, what TradingView's Strategy
Tester does with `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine`
(the fused script; with "Enable filter" off it is exactly
`/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp.pine`).
The Pine source is the ground truth. Read it. Where this spec and the Pine
disagree, the Pine wins and you must say so in your report.

Work dir: `/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/`
(below: `$W`). Python 3 with numpy, pandas, numba, pyarrow is installed. Run
Python as `python3 -I`. Do not modify files you were not asked to write.
Do not read the other implementation of your own component (the files named
`*_a.py` vs `*_b.py`): the two are meant to be independent.

## Data

`$W/data/<PAIR>_<TF>.parquet`, PAIR in {BTC, XAU}, TF in
{"1","5","15","30","60","120","240","D","W","M"}. Columns: open, high, low,
close (float), t_open, t_close (int64 UTC epoch seconds; t_close = the moment
the bar is complete), sess (int64 session id). Rows in time order. Built by
`$W/build_bars.py` (read its docstring: BTC on a UTC grid; XAU on a
TradingView-style 18:00-17:00 New York session, 120/240 bars anchored at
18:00 ET with the last bar of a session truncated at 17:00). XAU files may not
exist yet while gold ticks are being processed; develop and test on BTC first.
The last bar of each BTC file is still forming at the data end: ignore bars
with t_close > 1795392000 is NOT needed; callers pass an explicit window.

Seconds timeframes (1S, 5S, 15S, 30S) have NO data: every value requested
from them is na (as TradingView returns for a seconds feed with no history).

Symbol constants: mintick 0.01 for both pairs.

## How request.security maps another timeframe onto a chart bar (history)

Every `request.security(syminfo.tickerid, TF, expr, lookahead=barmerge.lookahead_off)`
in these scripts is evaluated as: compute `expr` on TF's own bar series (all
its history), then on a chart bar whose close time is Tc take the value of
the LAST TF bar with t_close <= Tc. If there is none, the value is na. This one
rule covers higher, equal and lower timeframes (a lower timeframe gives the
last lower-TF bar that closed inside or at the end of the chart bar).

`lookahead=barmerge.lookahead_on` with an expression that indexes `[1]` (the
filter's fgfTdiDirPrev) means: the previous TF bar's value, taken from the TF
bar that CONTAINS the chart bar (t_open <= chart t_open < t_close). Read the
filter block's own comments on its two request.security calls in
fgfZoneDir and implement exactly what they say; document your reading.

Nested request.security (the filter's fgfRead() is evaluated inside a
request.security on the filter timeframe and itself calls request.security):
the inner calls are evaluated relative to the OUTER timeframe's bars (the
"chart" of the inner call is the filter-timeframe series), then the outer
result is mapped onto the chart by the rule above.

Pine semantics to respect: ta.rsi = Wilder RMA; ta.sma; ta.stdev = population
(biased) standard deviation; ta.lowest/ta.highest(x, n) include the current
bar; `x[n]` is na before n bars exist; any comparison with na is false; v6
bools are never na; `nz()`; integer/float division as in Pine.

## Component 1: the direction filter  ->  fgf_a.py / fgf_b.py

Source: the block between `BEGIN FLASHGOLD DIRECTION FILTER` and
`END FLASHGOLD DIRECTION FILTER` (identical in
`/home/user/master/FlashGold_Direction_Filter_v1_2.pine`). Implement ALL of its
trading logic (FlashGold signal on the filter timeframe, entry price / level,
burst gate, prior drift, TDI trade-zone filter with parent and child zones,
the band, permission lifetime, "Check price on", against-the-signal, allow
buys / sells). Ignore pure display (shading, lines, labels, tables, the
direction score fgs*).

Interface:

    def fgf_permissions(pair: str, chart_tf: str, start: int, end: int,
                        params: dict | None = None) -> pandas.DataFrame

Rows = the chart bars of data/<pair>_<chart_tf>.parquet with start <= t_close
<= end, in order, index = their row numbers in that file. Columns at least:
t_close, buyOk, sellOk (bool), level, upLv, dnLv (float, na when none),
open_ (bool, fgfOpen), sigDir (int, the signal in force: 1, -1, 0),
newSig (bool, fgfNewSig on this chart bar), band (float). `params` keys are
the Pine input variable names (fgfOn, fgfTf, fgfLvMode, fgfLast, fgfMinutes,
fgfBars, fgfCheck, fgfBandAtr, fgfAgainst, fgfAllowBuy, fgfAllowSell,
fgfSpreadPts, fgfEntryDistPts, fgfHoldBars, fgfHoldFavPts, fgfOnePerBar,
fgfDistUnit, fgfBurstAtr, fgfEntryDistAtr, fgfHoldFavAtr, fgfBurstPts,
fgfUseBurst, fgfAnyCombo, fgfDriftBars, fgfUseDrift, fgfUseZones,
fgfParentTf, fgfRsiLen, fgfFastLen, fgfMinAligned, fgfFlatParent,
fgfIgnoreNa, fgfHtfClosed, fgfUseZ1..6, fgfZTf1..6); missing keys take the
Pine defaults. Timeframe strings as in Pine ("60", "240", "D", "" = chart).
History only: the script runs once per chart bar at its close, so "Tick"
judges the chart bar's close (closed candles keep their close). Compute every
series from the start of the data (warm-up), return only the window.
Also write `fgf_<a|b>_notes.md`: every place where you had to interpret the
Pine, and anything you could not implement.

## Component 2: the XPW ladder and labels  ->  xpw_a.py / xpw_b.py

Source: the fused script from `// PER-RUNG WINDOWS` through the end of the
`SIGNAL RUNGS` section (the AGREE block included only as far as it affects
entries: with the default agreeOn = false nothing from it trades).

Interface:

    def xpw_signals(pair: str, chart_tf: str, start: int, end: int,
                    params: dict | None = None) -> pandas.DataFrame

Rows as for the filter. Columns at least: t_close, chartIdx, readAt,
nLongRaw, nShortRaw (array sizes of longSrc / shortSrc), nLong, nShort (after
the "both sides cancel" zeroing), longSrc, shortSrc (lists of the source
strings exactly as the Pine builds them, e.g. "1 Hour * 1st LEG LONGS"),
exitL, exitS (bool), exitLSrc, exitSSrc, pos_0..pos_12 (str), orient_0..12
(+1/-1), inh_0..12 (bool), shape_0..12. Params: Pine input names (rsiLen,
fastLen, slowLen, bbLen, bbMult, scaleWin, flatWin, areaLen, areaFrac,
trendLen, sigRung, lblRead, actL1, actL2, actS1, actS2, actDL, actDS, actEnd,
actInf, agreeOn (only False supported; raise if True), reverseAll,
tradeAgree); missing keys take the Pine defaults. Rung TFs: "M","W","D",
"240","60","30","15","5","1","30S","15S","5S","1S" (seconds = na).
chartIdx from timeframe.in_seconds of the chart TF (120 -> the 4 Hour rung,
etc.; follow the Pine loop exactly). prevPosA / prevReadAt are carried bar to
bar; start them as the Pine does on the first bar of the window minus a
warm-up you choose (state it), so that the first window bars behave as on a
long chart. Labels are display only: do not draw, but an event's existence
does not depend on showLbl / tick boxes (as the Pine says).
Also write `xpw_<a|b>_notes.md`.

## Component 3: the strategy and the broker  ->  engine_a.py / engine_b.py

Source: the fused script's STRATEGY section (from `int nLong  = array.size(longSrc)`
to the end of the limit bookkeeping) and the strategy() declaration:
process_orders_on_close=true, pyramiding=100, default_qty percent_of_equity 10.

Interface:

    def backtest(pair: str, chart_tf: str, sig: DataFrame, perm: DataFrame | None,
                 params: dict | None = None) -> tuple[DataFrame, dict]

`sig` = xpw_signals output, `perm` = fgf_permissions output on the same rows
(None = filter off: buyOk = sellOk = True). Chart OHLC from the data file.
Params: tradeDir, oppCloses, fgfOn, fgfBlkClose, maxOpen, trailOn,
trailUnit, trailAct, trailOff, slOn, slDist, entryFill (only "Signal tick"
required; raise otherwise), mintick (0.01). Defaults = the Pine defaults.

Return (trades, summary). trades: one row per entry: id (Pine id string
"L<bar_index>-<k>", use the chart row number as bar_index), dir (+1/-1),
src, entry_row, entry_time, entry_px, exit_row, exit_time, exit_px,
exit_kind ("trail", "sl", "close_all", "reverse", "end"), exit_comment
(the Pine comment string). summary: counts of entries, blocked long / short
candles (the FGD funnel), and the gross P/L in price units per 1 unit.

Broker emulator rules (TradingView, history, no Bar Magnifier):
1. Per chart bar: first, open trades' pending exit orders (each entry's own
   strategy.exit: trailing stop and / or stop loss) are evaluated intrabar
   along the price path; then the script runs at the bar close with the
   updated position (strategy.position_size, strategy.opentrades); market
   orders it places fill at this bar's close, in the order the script
   places them (close_all before entries).
2. Intrabar path: if (high - open) < (open - low) the path is
   open -> high -> low -> close, otherwise open -> low -> high -> close.
3. An entry filled at bar i's close has its exits active from bar i+1.
4. Trailing stop (long; short mirrored): activation price = entry_px +
   trail_points * mintick. Once price reaches it, the stop = best price since
   activation - trail_offset * mintick, ratcheting up only. Exit when price
   touches the stop; fill at the stop, or at the bar open if the bar opens
   beyond it. Walk the path segment by segment so activation and exit can
   happen in the same bar when the path first rises then falls.
   trail_points 0 = active from the entry price.
5. Stop loss: stop at entry_px - loss * mintick (long); fill at the stop or
   at the open if gapped. If a trailing stop and the stop loss are both
   touched in a bar, the first touched along the path wins.
6. strategy.entry in the direction opposite to the open position: closes ALL
   open trades (kind "reverse", at this close) and opens the new entry.
   Further same-direction entries on that bar add trades.
7. strategy.close_all: closes all open trades at this close (kind
   "close_all"), removing their exit orders.
8. Units: trailUnit "price" converts with d / mintick (as toTicks), "ticks"
   as is, "percent" uses the entry reference price (this bar's close).
9. room / maxOpen and `room > 0 or strategy.position_size < 0` exactly as
   the Pine (position and opentrades are the values before this bar's
   close fills).
10. With the filter: implement the gate (sigLong, fgfBlkL, goLong, ...) and
   the blocked-entry close exactly as the fused script. History has one
   execution per bar, so doneL never equals the current bar beforehand.
Open trades at the window end: close them at the last bar's close (kind
"end").
Also write `engine_<a|b>_notes.md`.

## Self-checks every implementer must run before finishing

- Runs without error on BTC chart "60" for the window 2025-01-01 ->
  2025-03-01 (start 1735689600, end 1740787200) and on chart "5" for
  2025-01-01 -> 2025-01-15, with default params.
- Prints row counts, how many bars have a signal / permission / trade, and
  timing. A 2-year BTC 1m window (about 1.05 million chart bars) must finish
  in under 10 minutes; use numpy / numba where loops are hot.
- Save the default outputs for BTC 60 2025-01-01 -> 2025-03-01 as
  `$W/out/<component>_<a|b>_BTC_60.parquet` (trades for the engine, using
  YOUR OWN component's inputs where needed: engine implementers build sig
  with `$W/xpw_a.py` if it exists, else a minimal stub you write in
  `engine_<x>_stub.py`).
