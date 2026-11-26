# Reconciliation: HRD Full Divergence v1.03 + FGF, `hrd_a.py` vs `hrd_b.py`

Ground truth: `/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine`. With the filter off
it trades exactly like `/home/user/master/HRD_Full_Divergence_Strategy_v1_03.pine`.

**Result.** There were two disagreements, and replica B was wrong on both: D1, ta.sma over na
values (1m charts only), and D2, the time stamp of a window-end close. After fixing B, the two
builds agree on **100% of trades, in every column**, and on every summary field. That holds in all
48 required cases and in 36 extra ones (charts 15, 30 and 120). The canonical module `hrd.py` is
a copy of `hrd_a.py`, with only the docstring changed.

## Procedure

- Script: `reconcile_hrd_cmp.py PAIR [TF ...]`. Logs are `reconcile_hrd_cmp_<PAIR>_r0.log` (before
  the fixes), `reconcile_hrd_cmp_<PAIR>_r1prop.log` (isolation run), `reconcile_hrd_cmp_<PAIR>.log`
  (after the fixes) and `reconcile_hrd_cmp_<PAIR>_extra.log`. The JSON copies are
  `out/reconcile_hrd_<PAIR>{_r0,_r1prop,,_extra}.json`.
- Cases: BTC and XAU, charts 1, 5, 60 and 240, full windows. Params: default, fgfOn False,
  blkClose False, cost 'ours', reverse True, and pivotTies 'left_strict'.
- Trades are compared row by row, every column:
  - integer columns, compared exactly: dir, entry_time, exit_time, entry_bar, exit_bar, signal_bar and exit_kind;
  - float columns, within rtol 1e-10 / atol 1e-7: entry_px, qty, exit_px, pnl, sl_px, tp_px, costs and pnl_gross.

  B's columns were mapped onto these: stop / limit to sl_px / tp_px, entry_cost + exit_cost to
  costs, and pnl + costs to pnl_gross.
- Summary fields compared: trades, net_pct, pf, win_pct, max_dd_pct, long, short, raw_long, raw_short,
  blocked_long, blocked_short, half1_pct, half2_pct, exposure, final_equity and exits per kind.
- Round 0 (as built): 5, 60 and 240 matched except for 3 'end' time stamps. On 1m, BTC disagreed
  in every case and XAU in fgfOff and reverse. XAU 1m default, blkOff and ours matched trade by
  trade but had raw / blocked short counts 2 apart.
- Isolation (r1prop): rerunning A with `smaNa='propagate'` made it agree with B on every 1m row
  except the 'end' time stamps. So D1 and D2 explain every difference; nothing was hidden behind
  them.

## D1. ta.sma over na stoch values (B fixed)

**Where.** `stochVal = ta.sma(ta.stoch(close, high, low, 5), 3)`, the third leg of `osc`.

- When the 5-bar range is 0 (highest high == lowest low), ta.stoch divides by zero and returns na.
- Within the windows this happens only on 1m charts: 97 BTC bars and 31 XAU bars. There are 0 such
  bars on 5m and above.

**The two readings.**
- A: `smaNa='skip'`. ta.sma ignores na values and averages the last 3 non-na stoch values, also on
  the na bar itself.
- B: the SMA is na if any of its 3 inputs is na. So osc is na on up to 3 bars per zero-range bar.

**Which follows Pine.** A. The Pine reference remark on ta.sma says: "na values in the source
series are ignored; the function calculates on the length quantity of non-na values".
- This is the same rule the XPW reconciliation applied to ta.sma / ta.stdev in this project
  (`reconcile_xpw.md`).
- B's reading turns one flat 5-minute stretch into an na osc. That kills any divergence whose
  pivot falls on those bars. Through the state machine it also stores na as prevPlOsc / prevPhOsc,
  so the next pivot's comparison is false too.
- I could not re-open the TradingView reference from this session: www.tradingview.com is not in
  the session's allowed network domains. Secondary references found by search agree that ta.sma
  skips na values.
- The rule stays switchable as `smaNa`, and the results by time frame state it.

**Size.** It changes osc beyond float rounding on 217 BTC and 53 XAU 1m window bars. It changes
longCondition / shortCondition on 7 / 2 BTC bars and 0 / 2 XAU bars. BTC 1m default goes from
10182 to 10186 trades, net -11.550% to -11.558%. BTC 1m filter off goes from 25621 to 25630 trades,
-11.600% to -11.591%.

**Hand trace 1: BTC 1m, signal bar 5530044 (2024-12-29 08:06 UTC).**
Source: `reconcile_hrd_trace_sma.py` / `.log` and `reconcile_hrd_trace_more.py` / `.log`.

| bar | time UTC | O | H | L | C | stoch raw | SMA skip (A) | SMA propagate (B) | osc A | osc B |
|---|---|---|---|---|---|---|---|---|---|---|
| 5530009 | 07:22 | | 95038 | 95038 | 95038 | 100.000 | 94.737 | 94.737 | 52.9486 | 52.9486 |
| 5530036 | 07:57 | 95090 | 95090 | 95090 | 95090 | 100.000 | 100.000 | 100.000 | 63.1190 | 63.1190 |
| 5530037 | 07:58 | 95090 | 95090 | 95090 | 95090 | **na** (bars 5530033..37 all 95090) | 100.000 | na | 63.0140 | na |
| 5530038 | 07:59 | 95090 | 95101 | 95090 | 95101 | 100.000 | 100.000 | na | 64.0711 | na |
| 5530039 | 08:00 | 95101 | **95124** | 95085 | 95085 | 0.000 | 66.667 = (100+100+0)/3 | na | **51.1854** | **na** |
| 5530040 | 08:01 | 95053 | 95055 | 95053 | 95055 | 2.817 | 34.272 | 34.272 | 36.5292 | 36.5292 |

- **Pivot high.** Bar 5530039, high 95124, is confirmed on bar 5530044. It is strictly above the
  left highs 95090, 95090, 95090, 95090, 95101 and the right highs 95055, 95098, 95073, 95052, 95051.
- **Previous pivot high.** Bar 5530009 (95038, osc 52.9486), 30 bars back, within maxDivLookback 60.
- **A.** 95124 > 95038 and 51.1854 < 52.9486, so a regular bearish divergence: shortCondition on
  bar 5530044.
- **B.** `currPhOsc` is na, so both comparisons are false: no signal, and prevPhOsc becomes na.
- **The trade only A has (fgfOn False).**
  - Short, filled at the open of 5530045 at 95028.
  - qty = equity 967,715.7611 x 1% / (95051 x 2%) = 5.0905080.
  - SL = 95051 x 1.02 = 96952.02 and TP = 95051 x 0.96 = 91248.96. Neither is reached: highs are
    at most 95028 and lows at least 94971 on 5530045..51.
  - entryBarIndex = 5530045. On bar 5530050 (5530050 - 5530045 = 5) the time close_all is placed.
    It fills at the open of 5530051, 95008: pnl = 5.0905080 x 20 = +101.81.

  The run without that signal (B) holds no trade there.

**Hand trace 2: XAU 1m, signal bar 2114364 (2017-08-11 03:59 UTC).**
- Bars 2114356, 2114357 and 2114358 have a zero 5-bar range (all 1286.300), so stoch is na on
  each of them.
- The pivot high is bar 2114359 (1286.589). A: SMA = (100 + 100 + 0)/3 = 66.667 and osc 40.5349.
  The previous pivot high is 2114346 (1286.329, osc 42.0425). 1286.589 > 1286.329 and
  40.5349 < 42.0425, so A gives a regular bearish divergence.
- B: osc is na, so no signal.
- With the filter on the short is blocked, which is why XAU 1m default matched trade by trade but
  raw_short / blocked_short were 2 apart. With the filter off A shorts at the 2114365 open, 1286.262.

**Fix.** In `hrd_b.py`:
- `_stoch_sma(..., skip_na)` now has A's na-skipping mean, the new param `smaNa` defaults to
  'skip', and the signal cache key includes it. 'propagate' keeps B's old rule.
- `hrd_b_check.py`: its pandas reference is now `raw.dropna().rolling(3).mean().reindex().ffill()`.
  It still passes 136 / 0 (`reconcile_hrd_b_check_after.log`).
- `hrd_b_notes.md`, Signals item 4, was rewritten.

A was not changed.

## D2. Time stamp of the window-end close, kind 'end' (B fixed)

- A trade still open after the last window bar is closed at that bar's close (spec rule 5).
- A stamped `exit_time` = the last bar's t_close. B stamped its t_open.
- Every other column agreed.

**Which is right.** The Pine does not decide this: it is a replica output convention, since
TradingView shows that trade as open. A's stamp is the better fit:
- The fill is at the close price, which exists only at t_close.
- The windows are defined by t_close: the last bar's t_close is exactly the window end,
  1794873600 for BTC and 1529366400 for XAU. So the trade's exit_time falls at the window end, not
  one bar inside it.
- The canonical engine (`engine.py`) and apex_b stamp 'end' at t_close as well.

All other exits keep the TradingView convention: the t_open of the fill bar.

**Hand trace: XAU 1m, pivotTies left_strict, the last trade.**
- Long, signal bar 2401811 (close 1281.558), filled at the 2401812 open (t_open 1529366160), 1281.559.
- The SL is 1255.927 and the TP is 1332.820. Neither is touched: lows are at least 1281.192 and
  highs at most 1281.612 on 2401812..15. The 5-candle time exit has not come yet.
- The window's last bar is 2401815: t_open 1529366340, t_close 1529366400 (= the window end),
  C 1281.511. So kind 'end' at 1281.511, pnl = 373.9642 x (1281.511 - 1281.559) = -17.95.
- A stamped 1529366400; B stamped 1529366340. Now both stamp 1529366400.

The same disagreement was in BTC 60 fgfOff / blkOff / reverse and BTC 1m fgfOff / reverse.

**Fix.** In `hrd_b.py` run(): `exit_time = np.where(t_kind == K_END, tc[t_xbar], to[t_xbar])`.
`hrd_b_notes.md` Broker item 6 was updated to match.

## Agreement table

Each cell gives "A / B" trades and "agreeing rows / rows". "Summary equal" compares every field
listed above.

| pair | chart | case | trades before | rows agree before | trades after | rows agree after | summary equal after | net % (A = B) |
|---|---|---|---|---|---|---|---|---|
| BTC | 1 | default | 10186 / 10182 | 1302 / 10186 | 10186 / 10186 | 10186 / 10186 | yes | -11.5585 |
| BTC | 1 | fgfOff | 25630 / 25621 | 1430 / 25630 | 25630 / 25630 | 25630 / 25630 | yes | -11.5910 |
| BTC | 1 | blkOff | 10182 / 10178 | 1302 / 10182 | 10182 / 10182 | 10182 / 10182 | yes | -13.0258 |
| BTC | 1 | ours | 10186 / 10182 | 1302 / 10186 | 10186 / 10186 | 10186 / 10186 | yes | -88.6080 |
| BTC | 1 | reverse | 9496 / 9492 | 536 / 9496 | 9496 / 9496 | 9496 / 9496 | yes | -2.2592 |
| BTC | 1 | leftStrict | 11815 / 11806 | 1430 / 11815 | 11815 / 11815 | 11815 / 11815 | yes | -6.7820 |
| BTC | 5 | default | 2282 / 2282 | 2282 / 2282 | 2282 / 2282 | 2282 / 2282 | yes | -5.0254 |
| BTC | 5 | fgfOff | 5648 / 5648 | 5648 / 5648 | 5648 / 5648 | 5648 / 5648 | yes | -5.8640 |
| BTC | 5 | blkOff | 2279 / 2279 | 2279 / 2279 | 2279 / 2279 | 2279 / 2279 | yes | -3.1456 |
| BTC | 5 | ours | 2282 / 2282 | 2282 / 2282 | 2282 / 2282 | 2282 / 2282 | yes | -39.9926 |
| BTC | 5 | reverse | 2007 / 2007 | 2007 / 2007 | 2007 / 2007 | 2007 / 2007 | yes | -7.9779 |
| BTC | 5 | leftStrict | 2425 / 2425 | 2425 / 2425 | 2425 / 2425 | 2425 / 2425 | yes | -6.3617 |
| BTC | 60 | default | 248 / 248 | 248 / 248 | 248 / 248 | 248 / 248 | yes | +4.6559 |
| BTC | 60 | fgfOff | 621 / 621 | 620 / 621 | 621 / 621 | 621 / 621 | yes | +2.7200 |
| BTC | 60 | blkOff | 248 / 248 | 247 / 248 | 248 / 248 | 248 / 248 | yes | +4.8570 |
| BTC | 60 | ours | 248 / 248 | 248 / 248 | 248 / 248 | 248 / 248 | yes | -0.4372 |
| BTC | 60 | reverse | 299 / 299 | 298 / 299 | 299 / 299 | 299 / 299 | yes | -8.1015 |
| BTC | 60 | leftStrict | 254 / 254 | 254 / 254 | 254 / 254 | 254 / 254 | yes | +5.4382 |
| BTC | 240 | default | 48 / 48 | 48 / 48 | 48 / 48 | 48 / 48 | yes | -6.0713 |
| BTC | 240 | fgfOff | 190 / 190 | 190 / 190 | 190 / 190 | 190 / 190 | yes | -8.6552 |
| BTC | 240 | blkOff | 48 / 48 | 48 / 48 | 48 / 48 | 48 / 48 | yes | -4.4534 |
| BTC | 240 | ours | 48 / 48 | 48 / 48 | 48 / 48 | 48 / 48 | yes | -6.9744 |
| BTC | 240 | reverse | 119 / 119 | 119 / 119 | 119 / 119 | 119 / 119 | yes | +9.0562 |
| BTC | 240 | leftStrict | 48 / 48 | 48 / 48 | 48 / 48 | 48 / 48 | yes | -6.0713 |
| XAU | 1 | default | 7237 / 7237 | 7237 / 7237 (counts differed) | 7237 / 7237 | 7237 / 7237 | yes | -3.5950 |
| XAU | 1 | fgfOff | 17905 / 17903 | 7394 / 17905 | 17905 / 17905 | 17905 / 17905 | yes | -0.9941 |
| XAU | 1 | blkOff | 7217 / 7217 | 7217 / 7217 (counts differed) | 7217 / 7217 | 7217 / 7217 | yes | -3.7238 |
| XAU | 1 | ours | 7237 / 7237 | 7237 / 7237 (counts differed) | 7237 / 7237 | 7237 / 7237 | yes | -58.7825 |
| XAU | 1 | reverse | 7014 / 7013 | 2898 / 7014 | 7014 / 7014 | 7014 / 7014 | yes | -1.7150 |
| XAU | 1 | leftStrict | 8271 / 8271 | 8270 / 8271 | 8271 / 8271 | 8271 / 8271 | yes | -4.1504 |
| XAU | 5 | default | 1731 / 1731 | 1731 / 1731 | 1731 / 1731 | 1731 / 1731 | yes | -2.4201 |
| XAU | 5 | fgfOff | 4091 / 4091 | 4091 / 4091 | 4091 / 4091 | 4091 / 4091 | yes | -2.3211 |
| XAU | 5 | blkOff | 1728 / 1728 | 1728 / 1728 | 1728 / 1728 | 1728 / 1728 | yes | -2.7658 |
| XAU | 5 | ours | 1731 / 1731 | 1731 / 1731 | 1731 / 1731 | 1731 / 1731 | yes | -20.3693 |
| XAU | 5 | reverse | 1508 / 1508 | 1508 / 1508 | 1508 / 1508 | 1508 / 1508 | yes | -0.7961 |
| XAU | 5 | leftStrict | 1769 / 1769 | 1769 / 1769 | 1769 / 1769 | 1769 / 1769 | yes | -2.0174 |
| XAU | 60 | default | 165 / 165 | 165 / 165 | 165 / 165 | 165 / 165 | yes | +0.6702 |
| XAU | 60 | fgfOff | 394 / 394 | 394 / 394 | 394 / 394 | 394 / 394 | yes | +2.9738 |
| XAU | 60 | blkOff | 164 / 164 | 164 / 164 | 164 / 164 | 164 / 164 | yes | +1.2292 |
| XAU | 60 | ours | 165 / 165 | 165 / 165 | 165 / 165 | 165 / 165 | yes | -1.2660 |
| XAU | 60 | reverse | 188 / 188 | 188 / 188 | 188 / 188 | 188 / 188 | yes | -0.7065 |
| XAU | 60 | leftStrict | 166 / 166 | 166 / 166 | 166 / 166 | 166 / 166 | yes | +0.5920 |
| XAU | 240 | default | 38 / 38 | 38 / 38 | 38 / 38 | 38 / 38 | yes | -0.0398 |
| XAU | 240 | fgfOff | 141 / 141 | 141 / 141 | 141 / 141 | 141 / 141 | yes | -3.1504 |
| XAU | 240 | blkOff | 38 / 38 | 38 / 38 | 38 / 38 | 38 / 38 | yes | -0.2593 |
| XAU | 240 | ours | 38 / 38 | 38 / 38 | 38 / 38 | 38 / 38 | yes | -0.4822 |
| XAU | 240 | reverse | 86 / 86 | 86 / 86 | 86 / 86 | 86 / 86 | yes | +4.1324 |
| XAU | 240 | leftStrict | 38 / 38 | 38 / 38 | 38 / 38 | 38 / 38 | yes | -0.0398 |

- "Rows agree before" counts rows that agree at the same index. After the first missing or extra
  trade the rest of a 1m list is shifted, which is why so few rows agreed there.
- "(counts differed)": the trade rows matched, but raw_short / blocked_short were 2 apart (D1, on
  blocked bars).
- The extra check on charts 15, 30 and 120, both pairs and all 6 cases (36 runs), agrees 100% on
  rows and summary: `reconcile_hrd_cmp_<PAIR>_extra.log`.

## Shared readings, audited against the Pine

The two builds were written independently and agree on these points. I checked each one against
the Pine text.

- **Horizons.** `request.security(D/W/M, high[1], lookahead_on)` gives the previous completed
  D / W / M bar. Every window bar lies inside its D / W / M bar.
- **na handling.** `math.max / math.min` with na gives na. `bullBreak` compares close[1] with the
  current bar's maxLevel, as written.
- **Divergence state machine.** prevPl* / prevPh* are updated on every pivot. The hidden branch is
  an `else if`, and the oscillator value used is `osc[pivotStrength]`.
- **Time exit, the quirks of lines 882-888 as written.** A trade opened by a reversal keeps the old
  entryBarIndex. An entry filled at the same open as the time close_all never gets a time exit,
  because position_size[1] != 0 on its first bar.
- **Gate.** The gate uses the position before this bar's orders. The blocked close comes after the
  time exit and before the entries. The hybrid close_all is placed after the entries; its globals
  reset only when flat at a close.
- **Bracket.** SL / TP come from the signal bar's close and are active on the fill bar. The path
  is O-H-L-C when (H-O) < (O-L), otherwise O-L-H-C. A gap fills at the open.
- **Sizing.** qty = strategy.equity at the signal close (open P/L included) x 1% / (close x 2%),
  with a floor of 0.01.

Not verifiable without TradingView, and identical in both builds:
1. **Sizing of an opposite entry that fills right after a time close_all at the same open.** Both
   builds fill the orders in placement order, so the entry opens its own qty from flat. If
   TradingView sized the reversal when the order was placed (qty + |position|), the new position
   would be larger. Counts are in `run_hrd.py`'s field `entries_after_time_exit_same_open`:
   - filter on: 0 to 7 trades per cell;
   - filter off: 3 (BTC 4h) up to 495 (BTC 1m).
2. **Quantity and price rounding** to the symbol steps is not modelled. Margin calls are not
   modelled; positions are about 50% of equity.
3. **The pivot tie rule** ('strict', with 'left_strict' as the control). Its size is measured in
   `out/hrd_report.md`.

## Canonical module and files

- `hrd.py` = `hrd_a.py`, chosen because A was right on both disagreements. A also has the smaNa
  switch and the richer trade columns (signal_bar, exit_order_bar, sl_px, tp_px, pnl_gross,
  costs). It has the same interface:
  `run(pair, chart_tf, params=None, return_state=False) -> (trades, summary)`.
- Changed:
  - `hrd_b.py`: D1 and D2.
  - `hrd_b_check.py`: the D1 reference.
  - `hrd_b_notes.md`: the two items.
- The originals are in `reconcile_orig/`: `hrd_a.py.orig`, `hrd_b.py.orig`,
  `hrd_b_check.py.orig`, `hrd_a_notes.md.orig` and `hrd_b_notes.md.orig`. `hrd_a.py` is unchanged.
- New:
  - `reconcile_hrd_cmp.py`, `reconcile_hrd_trace_sma.py`, `reconcile_hrd_trace_more.py` (+ logs);
  - `run_hrd.py`, `make_hrd_report.py`, `write_hrd_report.py`;
  - `out/hrd_<PAIR>_<TF>.json` (14 cells), `out/hrd_trades/`, `out/hrd_report.md`.
