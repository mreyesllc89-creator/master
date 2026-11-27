# Component 3 (strategy + broker emulator): reconciliation of engine_a and engine_b

Ground truth: `/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine`, the STRATEGY
section (line 1380 `int nLong = array.size(longSrc)` through the limit bookkeeping, line 1514) and
the `strategy()` declaration (line 223), plus SPEC.md's broker rules 1-10.

**Result.** There was one disagreement: the `exit_comment` of trades closed at the window end
(`kind "end"`). After fixing it, `engine_a.py` and `engine_b.py` agree on 100% of trade rows, on all
16 common columns and every mapped summary key. That holds on:

- the 7 required cases, filter OFF and ON;
- the 2-year BTC 1m window;
- 896 non-default runs.

A third reference, written by the reconciler from the Pine (`reconcile_engine_ref.py`), also agrees
with the canonical module on 728 runs. 20 hand-traced trades all match the broker rules.

- **Canonical module:** `engine.py`, a copy of `engine_b.py`. Only the module docstring differs.
  It has the same interface: `backtest(pair, chart_tf, sig, perm, params=None) -> (trades,
  summary)`, plus `backtest_bars` and `load_bars`.
- **Inputs everywhere:** sig from the canonical `xpw.py` and perm from the canonical `fgf.py`.
  Defaults are used unless stated.
- **Saved output:** `out/engine_BTC_60.parquet`, the canonical default run (filter ON, BTC 60,
  2025-01-01..03-01): 155 trades. It is identical on the 11 spec columns to the implementers'
  `out/engine_a_BTC_60.parquet` and `out/engine_b_BTC_60.parquet`.

## Harness (all in this directory, run with `python3 -I`)

| script | what it does |
|---|---|
| `reconcile_engine_inputs.py` | builds and caches sig / perm for every case (`cache_engine/*.pkl`) |
| `reconcile_engine_cmp.py` | the 7 cases, OFF and ON; row-by-row comparison of every common trade column and the summaries; with `engine.py` present it also checks canonical == B |
| `reconcile_engine_extra.py` | 4 sig variants x 16 engine parameter sets x OFF/ON x 7 cases = 896 runs (`build` creates the sig variants) |
| `reconcile_engine_long.py` | the 2-year BTC 1m window: `build` (re-creates its cached sig / perm, about 11 s; deleted after the run to save 780 MB), `cmp`, `time MOD` |
| `reconcile_engine_ref.py` | the reconciler's own plain pure-Python reference (explicit long / short branches, explicit per-bar order list), compared with `engine.py`; mutation-checked: a reversed path order gives 48 differing trades and a stricter touch test gives 5 on BTC 60, so the comparison does bite |
| `reconcile_engine_trace.py` | prints the raw bars / sig / perm needed for the hand traces below |
| `reconcile_engine_time.py`, `reconcile_engine_pipeline_time.py` | timings |
| `reconcile_engine_find.py`, `reconcile_engine_expo.py` | locate trace candidates; exposure and exit-branch coverage |

### What was compared

**Trade columns (16).**
- Same name in both: `id, dir, src, entry_row, entry_time, entry_px, exit_row, exit_time, exit_px, exit_kind, exit_comment, entry_comment, bars_held`.
- Renamed, same meaning:
  - A `entry_bar_open` = B `entry_bar_time`
  - A `exit_bar_open` = B `exit_bar_time`
  - A `pnl_pts` = B `pl`

Floats are compared exactly (no tolerance), strings exactly.

**Summary keys (16 mapped, plus the 5 exit-kind counts).**
- Entries: entries, long / short entries, entry bars.
- FGD funnel: raw long / short, blocked long / short, go long / short.
- Room and pyramiding: entries held by room, entries ignored by pyramiding.
- Close bars: close_all bars.
- P/L: gross P/L total, long, short.

## Agreement table (default params)

| case | window | rows | filter | trades A / B | rows agree before fix | after fix | trail / sl / close_all / reverse / end | FGD raw L/S | blocked L/S | gross P/L (per 1 unit) | max open / max exposure* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC 60 | 2025-01-01..03-01 | 1417 | OFF | 329 / 329 | 329 | 329 (100%) | 326 / 0 / 0 / 3 / 0 | 170/148 | 0/0 | +90,124.00 | 3 / 0.30 |
| BTC 60 | | | ON | 155 / 155 | 155 | 155 (100%) | 153 / 0 / 2 / 0 / 0 | 170/148 | 91/79 | +49,738.00 | 3 / 0.30 |
| BTC 5 | 2025-01-01..01-15 | 4031 | OFF | 456 / 456 | 455 | 456 (100%) | 421 / 0 / 0 / 34 / 1 | 230/221 | 0/0 | +17,852.00 | 3 / 0.30 |
| BTC 5 | | | ON | 171 / 171 | 170 | 171 (100%) | 155 / 0 / 15 / 0 / 1 | 230/221 | 128/154 | +4,431.00 | 2 / 0.20 |
| BTC 240 | 2024-11-17..2025-11-17 | 2191 | OFF | 556 / 556 | 555 | 556 (100%) | 549 / 0 / 0 / 6 / 1 | 267/278 | 0/0 | +267,014.00 | 3 / 0.31 |
| BTC 240 | | | ON | 251 / 251 | 251 | 251 (100%) | 247 / 0 / 1 / 3 / 0 | 267/278 | 144/159 | +117,116.00 | 2 / 0.21 |
| BTC 1 | 2025-02-01..02-08 | 10021 | OFF | 658 / 658 | 657 | 658 (100%) | 593 / 0 / 0 / 64 / 1 | 388/270 | 0/0 | +16,957.00 | 3 / 0.30 |
| BTC 1 | | | ON | 214 / 214 | 214 | 214 (100%) | 193 / 0 / 21 / 0 / 0 | 388/270 | 240/204 | +9,111.00 | 2 / 0.20 |
| BTC 120 | 2025-06-01..09-01 | 1105 | OFF | 250 / 250 | 250 | 250 (100%) | 244 / 0 / 0 / 6 / 0 | 100/146 | 0/0 | +63,862.00 | 3 / 0.31 |
| BTC 120 | | | ON | 117 / 117 | 117 | 117 (100%) | 114 / 0 / 2 / 1 / 0 | 100/146 | 57/76 | +33,100.00 | 2 / 0.21 |
| XAU 60 | 2017-03-01..06-01 | 1428 | OFF | 303 / 303 | 303 | 303 (100%) | 176 / 0 / 0 / 127 / 0 | 121/175 | 0/0 | -280.31 | 15 / **1.50** |
| XAU 60 | | | ON | 137 / 137 | 137 | 137 (100%) | 76 / 0 / 44 / 17 / 0 | 121/175 | 71/91 | -251.13 | 12 / **1.20** |
| XAU 15 | 2017-03-01..03-15 | 878 | OFF | 157 / 157 | 156 | 157 (100%) | 56 / 0 / 0 / 100 / 1 | 87/66 | 0/0 | +4.56 | 8 / 0.80 |
| XAU 15 | | | ON | 65 / 65 | 65 | 65 (100%) | 28 / 0 / 27 / 10 / 0 | 87/66 | 51/37 | +20.27 | 7 / 0.70 |
| BTC 1 (2 years) | 1731801600..1794873600 | 1,039,430 | OFF | 63,358 / 63,358 | 63,358 | 63,358 (100%) | 55,553 / 0 / 0 / 7,805 / 0 | 33,071/30,287 | 0/0 | +1,087,842.37 | 6 / 0.60 |
| BTC 1 (2 years) | | | ON | 22,169 / 22,169 | 22,169 | 22,169 (100%) | 19,275 / 0 / 2,770 / 124 / 0 | 33,071/30,287 | 20,882/20,307 | +354,745.69 | 6 / 0.60 |

\* Footnotes to the table:
- **max open** = the most trades open at once after a bar's close fills (engine_a's definition).
- **max exposure** = position value / equity under the 10%-of-equity sizing. It comes from engine_a's
  approximate equity model and is reported only to flag the margin question (open issue 1).
- **Summaries.** Every mapped summary key agreed on every run, before and after the fix.

### Non-default coverage (`reconcile_engine_extra.py`): 896 runs, 0 disagreeing after the fix

**sig variants** (built with `xpw.py`):
- defaults;
- `sigRung = every rung` (up to 4 labels per bar, so stacking and multi-entry reversals);
- `actDL = actDS = actEnd = "exit only"` (exitL / exitS, the "exit | ..." close_all branch);
- `reverseAll` with `actL2 = enter opposite`, `actEnd = actInf = exit only`.

**engine parameter sets:**

| set | parameters |
|---|---|
| E0 | defaults |
| E1 | slOn |
| E2 | ticks 50 / 20, SL 100 |
| E3 | percent 0.5 / 0.2, SL 0.8 |
| E4 | trail off (exits only by close_all / reverse / end) |
| E5 | trail off, maxOpen 3 |
| E6 | maxOpen 1 |
| E7 | Long only |
| E8 | Short only, oppCloses off |
| E9 | fgfBlkClose off |
| E10 | trailAct 0, trailOff 50 |
| E11 | price 300 / 150, SL 400 |
| E12 | Long only, trail off, maxOpen 5 |
| E13 | SL only, 2.0 |
| E14 | Short only, trail off, maxOpen 2 |
| E15 | percent 0 / 0.001, SL 0 (the 1-tick floors) |

**Totals.**
- 268,788 trades:
  - 125,277 trail
  - 56,399 sl
  - 36,111 close_all
  - 50,289 reverse
  - 712 end
- 17,316 entries held back by `room`.
- Before the fix, the only differing rows were the 712 `end` rows, and only in exit_comment.
- After the fix: 268,788 / 268,788 rows agree.
- All three close_all comment branches occur: "exit |", "filter blocked LONG/SHORT, close |" and "opp ENTER |".

**Third reference** (`reconcile_engine_ref.py`), compared with `engine.py`:
- 13 parameter sets x 4 sig variants x OFF/ON x 7 cases = 728 runs.
- 233,768 trades compared: 0 mismatches.
- Comparison: id, dir, src, rows, kind and comment exact; prices to 1e-7.

## Disagreements found and fixed

### R1. Exit comment of a window-end close (engine_a fixed)

- **Symptom.** 1 row in each of these runs: BTC 5 OFF / ON, BTC 240 OFF, BTC 1 OFF, XAU 15 OFF.
  There were 712 such rows over the extra runs. Everything else in those rows agreed (rows, prices,
  kind `end`).
  - A wrote `exit_comment = "end of window"`.
  - B wrote `"end"`.
- **Root cause.** This is not a Pine reading. The Pine has no order for this. TradingView leaves such
  a trade open ("Open" in the List of Trades). Closing it at the last close is SPEC.md's rule
  ("Open trades at the window end: close them at the last bar's close (kind "end")"), and the spec
  gives no comment string. Each implementer invented one.
- **Fix.** engine_a now writes `"end"`, the canonical module's string (`engine_a.py` line 541).
  `engine_a_notes.md` is updated. engine_a's own checks still pass after the change:
  - `engine_a_check.py --no-1m`: ALL CHECKS PASSED
  - `engine_a_fuzz.py`: 400 cases, 8007 trades, 0 bad
  - the log is `reconcile_engine_a_check.log`
- **Originals.** Saved in `reconcile_orig/engine_a.py.orig`, `engine_a_notes.md.orig` and
  `engine_b.py.orig` (B unchanged).

No other disagreement was found. Both engines read the Pine the same way on every point below. I
checked each point against the Pine lines.

- **Gate.**
  - `sigLong = nLong > 0 and allowLong`: on history `doneL != bar_index` always holds (1393-1394).
  - `fgfBlkL = sigLong and not fgfBuyOk`: Signal tick, so `fgfLimOkL = true` (1404-1407).
  - `goLong = sigLong and not fgfBlkL`.
  - Shorts are mirrored.
- **Closes.**
  - `oppL = nShort > 0 and ((oppCloses and not allowShort) or (fgfBlkClose and fgfBlkS))` (1420-1421).
  - `closeL = position_size > 0 and not goLong and not goShort and (exitL or oppL)` in market mode (1422-1423). So close_all and an entry never happen on the same bar, and a reversal is always made by the entry.
  - The comment ternary (1430-1433) uses `firstLong` / `firstShort` from the RAW lists. They exist even when "both sides cancel" zeroed nLong / nShort.
- **Room.**
  - `room = maxOpen - strategy.opentrades` (`pendId` is always empty in Signal tick mode).
  - An entry is placed while `room > 0 or strategy.position_size < 0` (longs) or `> 0` (shorts).
  - position_size / opentrades are the values after the intrabar exits and before this close's
    fills. On a reversal bar EVERY entry is placed whatever maxOpen is (see trace 11).
- **placeEntry** (1469-1477):
  - `trail_points = max(toTicks(trailAct, close), 0)`
  - `trail_offset = max(toTicks(trailOff, close), 1)`
  - `loss = max(toTicks(slDist, close), 1)`
  - No strategy.exit at all when trailOn and slOn are both off.
- **Not modelled, and why.** `tickPx` / `entryPx` only feed label text. The limit-mode block is inert
  in Signal tick mode. Both raise on `entryFill = "Limit at label price"`, as SPEC allows.

## Hand traces of the canonical engine (20 trades)

Each trace was worked out by hand from the raw bars, sig and perm (printed with
`reconcile_engine_trace.py`). It was then compared with the `engine.py` row.

Notation:
- **Path:** rule 2. `H-O < O-L` gives O-H-L-C, otherwise O-L-H-C.
- **Default exit order:** `trailUnit = price`, `trailAct 2.0` = 200 ticks, `trailOff 1.0` = 100
  ticks. A long's activation = entry + 2.00, and its stop = best - 1.00 (shorts mirrored).

All prices are BTC/USD unless the case is XAU. Every engine value matched the hand result.

1. **S110550-1 (BTC 60, ON): trail armed and hit in one bar, short, O-H-L-C.**
   - Entry: bar 110550, shortSrc `["30 Min << 1st LEG SHORTS"]`, sellOk -> goShort, filled at close 98213.00. Activation 98211.00.
   - Bar 110551: O 98214 H 98215 L 98044 C 98165. 1 < 170, so O-H-L-C.
   - O->H is adverse.
   - H->L falls to 98044 <= 98211: armed, best 98044, stop 98045.
   - L->C rises to 98165 >= 98045: exit at **98045.00**, `trail TP | 30 Min << 1st LEG SHORTS`. Engine: same.
2. **L110613-1 (BTC 60, ON): one bar, long.**
   - Entry 97245.00, activation 97247.
   - Bar 110614: O 97238 H 97490 L 96574 C 96707. 252 < 664, so O-H-L-C.
   - O->H: 97490 arms it, stop 97489.
   - H->L reaches 96574: exit at **97489.00**. Engine: same.
3. **S110471-1 (BTC 60, ON): one bar, low-first path.**
   - Entry 94419, activation 94417.
   - Bar 110472: O 94423 H 94657 L 94398 C 94597. 234 < 25 is false, so O-L-H-C.
   - O->L to 94398: armed, stop 94399.
   - L->H reaches 94657: exit at **94399.00**. Engine: same.
4. **S111214-1 (BTC 60, ON): trail armed by the open.**
   - Entry 102005, activation 102003.
   - Bar 111215: O 102001 H 102012 L 101456. 11 < 545, so O-H-L-C.
   - Nothing was armed before the open, so there is no gap test. The open 102001 <= 102003 arms the trail: best 102001, stop 102002.
   - O->H reaches 102012: exit at **102002.00**. Engine: same.
5. **S111135-1 (BTC 60, ON): gap through the trailing stop.**
   - Entry 102585, activation 102583.
   - Bar 111136: O 102591 H 102761 L 102188 C 102188 (O-H-L-C). H->L arms it: best 102188, stop 102189. L->C is flat, so no exit.
   - Bar 111137 opens at 102209 >= 102189: filled at the open, **102209.00**, kind trail. Engine: same.
6. **S110551-1 (BTC 60, ON): multi-bar.**
   - Entry 98165 (bar 110551), activation 98163.
   - Lows of bars 110552-110555 are 98204, 98268, 98289 and 98257, all above 98163, so it is never armed.
   - Bar 110556: O 98256 H 98256 L 97786 C 97812 (O-H-L-C). H->L arms it: best 97786, stop 97787. L->C reaches 97812.
   - Exit at **97787.00**, 5 bars held. Engine: same.
7. **L111215-1 (BTC 60, ON): blocked-entry close, "filter blocked SHORT".**
   - Bar 111215: S111214-1 left intrabar (trace 4), so the script sees a flat position. nLong 1, buyOk: L111215-1 at 101663, activation 101665.
   - Bars 111216-111220: the highest high is 101663, so it is never armed.
   - Bar 111216: nLong 2, room = 20 - 1 = 19: L111216-1 and -2 at 101288. Both exit at 111217 at 101539 (H 101540 arms them, H->L hits the stop).
   - Bar 111217: nLong 1 but buyOk false, so fgfBlkL. oppS needs a short position, so nothing happens.
   - Bar 111220: nShort 1 `["1 Min << 1st LEG SHORTS"]`, sellOk false, so fgfBlkS and oppL. closeL fires: close_all at **101245.00**, `filter blocked SHORT, close | 1 Min << 1st LEG SHORTS`. Engine: same.
8. **S110842-1 (BTC 60): "filter blocked LONG" (ON) against a reversal (OFF) on the same bar.**
   - Entry 101380, activation 101378. The lowest low of 110843-110863 is 101398, so it is never armed.
   - Bar 110864: nLong 1 `["5 Min << 1st LEG LONGS"]`, buyOk false.
   - ON: fgfBlkL, oppS, closeS: close_all at **103557.00**, `filter blocked LONG, close | 5 Min << 1st LEG LONGS`.
   - OFF: goLong with a short position. `room > 0 or position_size < 0` places L110864-1, and its fill reverses: S110842-1 closes as `reverse` at 103557.00 with `ENTER LONG | 5 Min << 1st LEG LONGS`, and the long opens at 103557.
   - Engine: same, both ways.
9. **L111242-1 (BTC 60, OFF): reversal.**
   - Entry 97962, activation 97964. Highs of 111243-111252 are at most 97962, so it is never armed.
   - The stacked longs exit on their own before the reversal:
     - L111244-1 (96480): armed by the open 96492, H 96875 gives stop 96874, hit on H->L. Exit 96874.
     - L111248-1 (92831): armed by the open 92929, stop 92928. O-L-H-C, so O->L to 92746 hits it. Exit 92928.
   - Bar 111252: nShort 1, so goShort with 1 long open. S111252-1 reverses: L111242-1 closes as `reverse` at **95422.00**, `ENTER SHORT | 5 Min << 1st LEG SHORTS`. Engine: same.
10. **maxOpen = 3 (every-rung sig, trail off, ON), bar 110479.**
    - Bar 110477: nShort 1, sellOk, with 1 long open. S110477-1 reverses L110470-1 at 94680.
    - Bar 110478: nShort 2 but sellOk false. Blocked, and there is no long to close.
    - Bar 110479: nShort 3, sellOk, opentrades 1, so room = 2:
      - k=1: placed, room 1.
      - k=2: placed, room 0.
      - k=3: `room > 0 or position_size > 0` is false, so it is held.
    - Engine: S110479-1 and -2 only (held-by-room 1).
    - Bar 110480: nLong 3, buyOk false, so close_all of all 3 shorts at 95509.00, `filter blocked LONG, close | 15 Min staircase`. Engine: same.
11. **maxOpen = 1 bypassed by a reversal (every-rung sig, maxOpen 1, OFF), bar 111185.**
    - S111182-1 is open, so room = 0. nLong 4, and position_size stays short for the whole script run, so all 4 entries are placed.
    - The first reverses: S111182-1 closes at 104625.00, `ENTER LONG | 30 Min staircase`. The other 3 add, giving 4 longs open with maxOpen 1. This is exactly the Pine.
    - Bar 111186: O 104658 >= activation 104627, so all four are armed by the open. O-H-L-C: H 104834 gives stop 104833, and H->L to 104119 hits it. All exit at **104833.00**.
    - Bar 111184 had labels on both sides, which cancel, so nothing happened there. Engine: same.
12. **S110807-1 (BTC 60, E11 = trail 300 / 150, SL 400 price, ON): trail and SL in one bar, trail touched first.**
    - Entry 99870: activation 99570, offset 150, SL 100270.
    - Bar 110808: O 99870 H 100715 L 99484 C 99618. 845 < 386 is false, so O-L-H-C.
    - O->L to 99484 arms it: stop 99634.
    - L->H rises. The lower of (99634, 100270) is met first: exit at **99634.00**, trail. The SL is inside the bar too, but later on the path. Engine: same.
13. **L110633-1 (E11, ON): SL before the activation in one bar.**
    - Entry 95361: activation 95661, SL 94961.
    - Bar 110634: O 95360 H 95836 L 94896. 476 < 464 is false, so O-L-H-C.
    - O->L to 94896 hits the SL: **94961.00**, sl. The high that would have armed the trail comes later on the path. Engine: same.
14. **S110956-1 (E11, ON): exact touch of the SL.**
    - Entry 105970: SL 106370.
    - Bar 110957: O 105963 H 106370 L 105466. 407 < 497, so O-H-L-C.
    - O->H: H = 106370 = SL, which counts as a touch: **106370.00**, sl. Engine: same.
15. **S110510-1 (E2 = ticks 50 / 20, SL 100 ticks, ON).**
    - Entry 96436: activation 96435.50, offset 0.20, SL 96437.00.
    - Bar 110511: O 96433 H 96747 L 96413. 314 < 20 is false, so O-L-H-C.
    - The open is below the SL, so no gap. The open 96433 <= 96435.5 arms the trail: best 96433.
    - O->L: best 96413, stop 96413.20.
    - L->H: exit at **96413.20**, trail. Engine: same.
16. **S110487-1 (E3 = percent 0.5 / 0.2, SL 0.8, ON).** Entry 96618.
    - trail_points = 96618 * 0.5 / 100 / 0.01 = 48309 ticks, so activation = 96134.91.
    - offset = 19323.6 ticks = 193.236.
    - loss = 77294.4 ticks, so SL = 97390.944.
    - Bars 110488 and 110489: lows 96538 / 96354 do not arm it; highs 96777 / 96840 are below the SL.
    - Bar 110490: O 96363 H 97284 L 95869 (O-L-H-C). O->L arms it: best 95869, stop 96062.236. L->H: exit at **96062.236**, trail. Engine: same.
17. **S110471-1 (E10 = trailAct 0, trailOff 50, ON).**
    - The trail is armed at the entry: best 94419, stop 94469.
    - Bar 110472: the open 94423 is below the stop, so no gap. O-L-H-C: best 94398, stop 94448. L->H reaches 94657.
    - Exit at **94448.00**. Engine: same.
18. **L28133-1 and L28133-2 (BTC 240, E7 = Long only, OFF): "opp ENTER" close in one-side mode.**
    - Bar 28133: nLong 2: two longs at 94281, activation 94283.
    - Bar 28134: O 94268 H 98200 L 93933 C 98200 (O-L-H-C). L->H arms them: stop 98199. H->C is flat, so they stay open.
    - Script: nShort 1. allowShort is false, so sigShort is false. oppL = oppCloses and not allowShort, so closeL fires.
    - close_all of both at **98200.00**, `opp ENTER | 1 Min << 1st LEG SHORTS`. Engine: same.
19. **S110687-1 and S110695-1 (BTC 60, sig with actEnd = exit only, E4 = trail off, OFF): exit label.**
    - Bar 110701: exitS, exitSSrc `1 Hour * END 2nd LEG SHORTS`, with a short position and no goLong / goShort. closeS fires.
    - close_all of both at **94309.00**, `exit | 1 Hour * END 2nd LEG SHORTS`. Engine: same.
20. **S131906-1 (XAU 15, OFF): window end.**
    - Entered at the last window bar's close, 1200.652. Closed at that same close as `end`, P/L 0. Engine: same.

The required kinds are covered:

| kind | traces |
|---|---|
| trail exit within one bar | 1, 2, 3, 4, 12, 15 |
| reversal | 8 (OFF), 9, 10, 11 |
| close_all | 7, 8, 10, 18, 19 |
| blocked-entry close | 7, 8, 10 |
| maxOpen limit | 10 (held entry), 11 (reversal bypass) |

Also covered: a gap (5), multi-bar (6), SL (13, 14), units (15, 16), trailAct 0 (17) and end (20).

## Choice of the canonical implementation and timing

Both engines are numba kernels with the same algorithm. Timings are fresh processes with the numba
cache warm and sig / perm loaded from `cache_engine/`.

| measurement | engine_a | engine_b |
|---|---|---|
| suite: 14 small calls + 2-year 1m OFF + ON, 3 runs (s) | 3.66 / 3.52 / 3.62 | 3.73 / **3.20** / **3.39** |
| 2-year 1m, OFF, first call in a fresh process (s) | **2.11-2.14** | 2.28-2.43 |
| 2-year 1m, OFF, repeat call (s) | 1.24-1.36 | 1.31-1.42 |
| 2-year 1m, ON (s) | 0.93-1.39 | 0.88-1.20 |
| BTC 1 one-week window, ON, repeat call (s) | 0.25-0.29 | **0.012-0.016** |

- **Small-window gap.** engine_a reads the parquet columns on every call. engine_b caches the chart
  bars per (pair, tf).
- **Choice: B.** It is faster over the suite in 2 of 3 runs and on repeated calls, which is how a
  sweep uses the engine. It is equal on the big window apart from the one-off file read.

**Canonical `engine.py` on BTC chart "1", 2024-11-17..2026-11-17 (1,039,430 bars):**
- **Engine only.**
  - Filter OFF: 63,358 trades.
    - 2.33-2.56 s on the first call in a fresh process (this includes reading the 1m file).
    - 1.11-1.18 s on later calls.
  - Filter ON: 22,169 trades, 0.85-1.18 s.
- **Whole canonical pipeline** (xpw.py 8.2-8.7 s + fgf.py 0.9-1.1 s + engine OFF + ON): 12.6-12.8 s,
  or 13.1-13.3 s wall including interpreter start.
- **Limit.** The spec asks for under 10 minutes.

## Spec vs Pine

- **Rule 8 floors.** Rule 8 omits the floors in `placeEntry`: `trail_offset` and `loss` are at least
  1 tick, and `trail_points` is at least 0. The Pine wins, and both engines (and the reference)
  apply them. Run E15 exercises them.
- **Everything else.** No other difference was found. Rules 1-10 match the Pine, given that orders
  placed in a script run fill after it, which the Pine relies on for `room` and `position_size`.

## Open issues / residuals (shared by both engines; not disagreements)

1. **Margin calls are not modelled.**
   - In Pine v6, `margin_long` / `margin_short` default to 100 when strategy() does not set them, to
     my knowledge (v5 defaulted to 0). Each entry is 10% of equity and up to maxOpen = 20 can stack.
   - XAU 60 with the defaults reaches 15 open trades, about 1.5x equity: 78 bars above 1.0x with the
     filter OFF, 26 with it ON. TradingView would then issue margin-call liquidations that neither
     engine produces.
   - The BTC cases stay at or below 0.31x (0.60x on the 2-year window), so they are unaffected.
   - SPEC.md does not mention margin. Treat XAU 60 default results as diverging from TradingView
     wherever exposure is above 1.0. engine_a's `per_bar=True` gives the per-bar exposure.
2. **Prices off the tick grid are not rounded.**
   - The XAU data has 3 decimals (for example 1200.652) while the spec's mintick is 0.01.
   - Percent units give sub-tick levels (trace 16: 96062.236).
   - Both engines use the formulas unrounded. TradingView may round stop prices to mintick, so
     fills can differ by up to 0.005 in those cases.
3. **The window starts flat.**
   - Positions TradingView would carry in from before the first sig row are absent. That also
     affects `room` and reversals on the first bars.
   - Windows that start after a quiet period are cleanest.
4. **Several opposite entries on one bar.**
   - SPEC rule 6 is followed: the first entry reverses and the later same-side entries add trades
     (trace 11).
   - How TradingView sizes the second and later opposite market orders placed in the same script
     run was not verified against TradingView itself.
5. **Path tie.** When `H - O == O - L`, both use O-L-H-C, as rule 2's "otherwise" says.
   TradingView's documentation does not name the tie case.
6. **Summary `max_open` means different things.**
   - In the canonical module (B) it is the most `strategy.opentrades` the script saw, which is
     before the close fills.
   - In engine_a it is the most open trades after the close fills. On BTC 60 that is 2 against 3.
   - The trade lists are unaffected. The table above uses A's definition.
7. **The default results are path-driven.**
   - With the defaults (2.0 activation and 1.0 offset in price units) the trail arms and exits on
     almost every next bar on BTC (for example 55,553 of 63,358 two-year 1m trades are trail exits).
   - The P/L therefore reflects rule 2's OHLC path assumption more than the signals. Both
     implementers flagged this too.
