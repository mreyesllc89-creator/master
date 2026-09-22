PORTED | rows=70 exact=52 equivalent=12 assumed=4 different=2 omitted=0 | A pass, B skipped, C pass-emulated/live-pending | DECISION: yes — ready to run once the host compile is clean; smoke stays closed until the axis receipt arrives (BLOCKED_AXIS_RECEIPT_MISSING)

# XPW Shape Map v0.5 — Pine → MQL5 port report (2026-09-22)

Same method and gates as the v0.4 port (`XPMap/XPW_SHAPEMAP_PORT_REPORT.md`); everything below is specific to v0.5.
Source of truth: the v0.5 Pine pasted with the request. Deliverables in `XPMap/v0.5/`:

| File | What |
|---|---|
| `XPW_ShapeMap_v0.5.mq5` | the indicator (separate window 0..100, 29 buffers, 4 plots, 29 Pine inputs + 3 port-only) |
| `XPW_ShapeMap_v0.5_export.pine` | Gate B build: the v0.5 Pine verbatim + `display.data_window` plots of every internal series |
| `reference/shapemap_ref.py` | Python transliteration, same na rules, same order within a bar |
| `reference/diff_harness.py` | Gate C (dump vs reference), Gate B (`--tv`), S3 replay diff (`--s3`), S2 funnel |
| `reference/run_fixtures.py`, `reference/fixtures/` | Gate A: 4 hand-derived fixtures (1 754 asserts) + `DERIVATIONS.md` |
| `reference/emu/` | stub lint + runtime emulator (`run_emu.sh`) that executes the MQL5 source on synthetic bars |

Gate 0 is unchanged from v0.4 (same engine, same symbol): **G0.1 BLOCKED_AXIS_RECEIPT_MISSING** (axischeck CSV still
not attached), **G0.2a** last bar not reliably closed → `LastBarIsClosed=false`, **G0.2b** empty seconds skipped by the
deployed engine → `SkipEmptyBars=false`, **G0.3** digits/point/tick size read from the chart symbol at init. The engine
line quotes are in the v0.4 report §1.

---

## 1. What changed from v0.4 and how the port follows it

* **Detectors are offset-based.** v0.5 has no run tracker; `detect()` reads `isRed[k]`/`isLime[k]` for k up to
  `2·ctx+maxW−1`, the turn logic reads `fast[k]`/`slow[k]` up to `turnHold+1`, the area gate reads `inLow[ctx]`.
  The port keeps rings keyed by the Pine `bar_index` (logical bar count), capacity ≥ the largest offset + 8, and every
  `x[k]` with `k > bar_index` is na (NA8) so it fails the same comparisons the Pine fails.
* **Two-stage shape.** The square (wedge) arms a turn watch (`botArmed/topArmed`, `botArmBar`), which expires after
  `turnMax` bars and fires on `ta.crossover(fast, slow)[turnHold]` held for `turnHold+1` bars. Ported term for term;
  the mark is drawn at `bar_index − turnHold`, the buffers are stamped at the confirmation bar.
* **Legs** replace the v0.4 continuity block: path accumulates while a leg is open (before the turn test on the same
  bar, as in the Pine), a turn closes the leg into the `leg1`/`leg2` strings and opens the next.
* **Inputs**: 29, same names/defaults/order/groups (TDI, Areas, BOTTOM, TOP, Turn mark, Ticks, Display) plus the three
  port-only ones. `atrLen` minval is 2 here (was 1). `loFrac/hiFrac` are 0..1 here.
* **Visuals**: the fast/slow plots are gray/silver (no RSI plot in v0.5; RSI is still exposed as buffer 27); fill
  red/lime by `isRed`; boxes red/lime with `±1.5` padding; wedge tags `"BOT w"`/`"TOP w"`; turn marks `▲`/`▼`; tick
  labels `"BOT"`/`"TOP"` always on the price chart (no `tickPrice` input in v0.5); 10-row table with a gray frame and a
  blue header row.

---

## 2. Equivalence table (every Pine statement → MQL5 counterpart)

| # | Pine | MQL5 counterpart | Class | Reason / note |
|---|---|---|---|---|
| 1 | `indicator("XPW Shape Map v0.5", overlay=false, max_boxes_count=500, max_labels_count=500, max_bars_back=500)` | separate window, shortname, caps 500/500 in `PushName()` | EXACT | `max_bars_back` is a Pine buffer hint; the rings cover every offset the script uses |
| 2 | `rsiLen = input.int(14, minval=2, group="TDI")` | `input int rsiLen = 14` + `ClampInt(2)` | EXACT | |
| 3 | `fastLen = input.int(2, minval=1)` | `input int fastLen = 2` + clamp | EXACT | |
| 4 | `slowLen = input.int(7, minval=1)` | `input int slowLen = 7` + clamp | EXACT | |
| 5 | `invertFill = input.bool(true, "My panel paints fast>slow as RED")` | `input bool invertFill = true` | EXACT | |
| 6 | `areaLook = input.int(20, minval=5, group="Areas")` | `input int areaLook = 20` + clamp | EXACT | |
| 7 | `loFrac = input.float(0.20, 0..1, step 0.01)` | `input double loFrac = 0.20` + clamp | EXACT | |
| 8 | `hiFrac = input.float(0.67, 0..1)` | `input double hiFrac = 0.67` + clamp | EXACT | |
| 9 | `botOn, botMinW(1), botMaxW(3), botCtx(2), botNeedLow(true), botSep(5, minval 0)` (group BOTTOM) | same six inputs, clamps 1/1/1/0 | EXACT | |
| 10 | `topOn, topMinW(1), topMaxW(2), topCtx(3), topNeedHigh(true), topSep(5)` (group TOP) | same six inputs | EXACT | |
| 11 | `turnOn(true), turnMax(12, minval 1), turnHold(2, minval 1)` (group Turn mark) | same three inputs | EXACT | |
| 12 | `tickOn(true), atrLen(14, minval 2), botWickRange(0.55), botWickAtr(0.8), topWickRange(0.70), topWickAtr(1.20)` (group Ticks) | same six inputs; wick inputs have no minval in the Pine and none here | EXACT | |
| 13 | `showTable = input.bool(true, group="Display")` | `input bool showTable = true` | EXACT | |
| 14 | *(none)* | `LastBarIsClosed=false`, `SkipEmptyBars=false`, `DumpCSV=false` (group Port) | DIFFERENT | port-only (R3/R4/Gate C) |
| 15 | `r = ta.rsi(close, rsiLen)` | `CXpRsi` | EXACT | RMA(1/len), SMA-seeded, down==0→100, up==0→0 |
| 16 | `fast = ta.sma(r, fastLen)`, `slow = ta.sma(r, slowLen)` | `CXpSma g_fast/g_slow` | EXACT | NA4 |
| 17 | `pF = plot(fast, "Fast", color.new(color.gray, 30), linewidth=1)` | plot 1 DRAW_LINE `C'120,123,134'` width 1 | EQUIVALENT | no alpha |
| 18 | `pS = plot(slow, "Slow", color.new(color.silver, 30))` | plot 2 DRAW_LINE `C'178,181,190'` | EQUIVALENT | Pine silver #B2B5BE exact; no alpha |
| 19 | `isRed = invertFill ? fast > slow : fast < slow` | `isRed = invertFill ? (both && fast > slow) : (both && fast < slow)` | EXACT | NA1 |
| 20 | `isLime = not isRed` | `IsLimeAt(k)` = stored `isRed == 0` | EXACT | NA10: lime during warm-up |
| 21 | `fill(pF, pS, isRed ? color.new(color.red, 82) : color.new(color.lime, 82))` | two single-colour DRAW_FILLING plots keyed per bar to `isRed`, transition segment bridged in the new colour | EQUIVALENT | colour-order independent; no alpha. The forming bar is filled and its lines move with every tick (`PreviewBars()`, rev 2) |
| 22 | `hiW = ta.highest(slow, areaLook)`, `loW = ta.lowest(slow, areaLook)` | `CXpExtreme g_ext` | EQUIVALENT-ASSUMED | NA5 (na while the window holds na; Gate B settles) |
| 23 | `rngW = hiW - loW` | `rngW = extOk ? hiW - loW : 0` with `extOk` | EXACT | NA2 |
| 24 | `posW = rngW > 0 ? (slow - loW) / rngW : 0.5` | `posW = (extOk && rngW > 0) ? … : 0.5` | EXACT | NA9; slow is valid whenever the window is |
| 25 | `inLow = posW <= loFrac`, `inHigh = posW >= hiFrac` | same | EXACT | |
| 26 | `detect(wantRedWedge, minW, maxW, ctx)`: `wHi = math.max(minW, maxW)`, `for w = minW to wHi`, `if not fired`, three offset loops, `fired := true; wOut := w` | `Detect()` — same loops, same order, same early-fire semantics (`if(fired) continue`) | EXACT | offsets beyond bar 0 read false (NA8) |
| 27 | `[botRaw, botWid] = detect(true, botMinW, botMaxW, botCtx)`; `[topRaw, topWid] = detect(false, …)` | same two calls | EXACT | |
| 28 | `var int lastBotBar = -10000` … `lastTopWedge = -10000` (4 vars) | globals, reset to −10000 in `ResetAll()` | EXACT | |
| 29 | `botOK = botOn and botRaw and barstate.isconfirmed and (not botNeedLow or inLow[botCtx]) and (bar_index - lastBotBar >= botSep)` | `botOK = botOn && botRaw && (!botNeedLow \|\| InLowAt(g_botCtx)) && (bi - lastBotBar >= g_botSep)` | EXACT | isconfirmed implicit (closed bars only) |
| 30 | `topOK = …inHigh[topCtx]…topSep` | same | EXACT | |
| 31 | `var int nBotSq = 0`, `nTopSq` | globals | EXACT | |
| 32 | `if botOK: lastBotBar := bar_index; lastBotWedge := bar_index - botCtx; nBotSq += 1; lft = bar_index - botCtx - botWid + 1; rgt = bar_index - botCtx` | same | EXACT | |
| 33 | `hh = -1e10; ll = 1e10; for i = 0 to botWid-1: hh := math.max(hh, math.max(fast[botCtx+i], slow[botCtx+i])); ll := math.min(…)` | same loop through `XpMax/XpMin` with valid flags | EQUIVALENT-ASSUMED | NA7 on `math.max` with na — unreachable: a red/lime wedge bar bounded by valid context bars always has valid fast/slow |
| 34 | `box.new(lft, hh + 1.5, rgt, ll - 1.5, border_color=color.new(color.red, 0), border_width=1, bgcolor=color.new(color.red, 65))` | `OBJ_RECTANGLE` from `time[lft]` to `time[rgt]`, `hh+1.5`/`ll−1.5`, `C'255,82,82'`, width 1, no fill | EQUIVALENT | translucent bg omitted (no alpha) |
| 35 | `label.new(rgt, ll - 2.0, "BOT " + str.tostring(botWid), style=label_up, color=color.new(color.red, 25), textcolor=color.white, size=tiny)` | `OBJ_TEXT` at `(time[rgt], ll−2)`, `ANCHOR_UPPER`, text `"BOT w"`, Arial 7 | EQUIVALENT | MQL5 text has no background: the text takes the Pine label's background colour (red) instead of white-on-red |
| 36 | `if topOK: … box.new(… color.lime …)`, `label.new(rgt, hh + 2.0, "TOP " + …, label_down, color=color.new(color.green, 25), textcolor=white)` | same with `C'0,230,118'` box, `ANCHOR_LOWER` text in `C'76,175,80'` (Pine green) | EQUIVALENT | as row 35 |
| 37 | `var bool botArmed`, `var int botArmBar`, `topArmed`, `topArmBar` | globals | EXACT | |
| 38 | `if botOK: botArmed := true; botArmBar := bar_index` (and top) | same, evaluated after the square block, as in the Pine | EXACT | |
| 39 | `if botArmed and bar_index - botArmBar > turnMax: botArmed := false` (and top) | same | EXACT | never true on the arming bar |
| 40 | `holdUp/holdDn = true; for i = 0 to turnHold: if not (fast[i] > slow[i]) holdUp := false; if not (fast[i] < slow[i]) holdDn := false` | same loop over `FastGtSlowAt(k)` / `FastLtSlowAt(k)` (false on na) | EXACT | NA1 |
| 41 | `crossedUpAt = ta.crossover(fast, slow)[turnHold]` | `FastGtSlowAt(turnHold) && FastLeSlowAt(turnHold+1)` | EXACT | Pine reference: crossover = `a > b` now and `a <= b` on the previous bar (NA11) |
| 42 | `crossedDnAt = ta.crossunder(fast, slow)[turnHold]` | `FastLtSlowAt(turnHold) && FastGeSlowAt(turnHold+1)` | EXACT | |
| 43 | `botTurn = turnOn and barstate.isconfirmed and botArmed and crossedUpAt and holdUp`; `topTurn = …` | same | EXACT | |
| 44 | `var int nBotTurn, nTopTurn, lastBotGap, lastTopGap` | globals | EXACT | |
| 45 | `if botTurn: botArmed := false; nBotTurn += 1; tb = bar_index - turnHold; lastBotGap := tb - lastBotWedge` | same | EXACT | |
| 46 | `label.new(tb, math.min(fast[turnHold], slow[turnHold]) - 3.0, "▲", label_up, color=color.new(color.yellow, 10), textcolor=black, tiny)` | `OBJ_TEXT` "▲" (`ShortToString(0x25B2)`) at `(time[tb], min−3)`, `ANCHOR_UPPER`, `C'255,235,59'`, Arial 8 | EQUIVALENT | glyph in the label's background colour; `math.min` with na unreachable (a crossover bar has valid fast/slow) |
| 47 | `if topTurn: … "▼" at math.max(…) + 3.0, label_down, orange` | `OBJ_TEXT` "▼" (`0x25BC`), `ANCHOR_LOWER`, `C'255,152,0'` | EQUIVALENT | |
| 48 | `atrV = ta.atr(atrLen)` | `CXpAtr` | EXACT | NA6 |
| 49 | `rngBar = high - low`, `upWick = high - math.max(open, close)`, `dnWick = math.min(open, close) - low` | same | EXACT | |
| 50 | `botTick = tickOn and isconfirmed and rngBar > 0 and atrV > 0 and dnWick / rngBar >= botWickRange and dnWick / atrV >= botWickAtr` | `tickOn && rngBar > 0 && (atrOk && atrV > 0) && dnWick/rngBar >= botWickRange && dnWick/atrV >= botWickAtr` | EXACT | NA1 on `atrV > 0` |
| 51 | `topTick = …upWick…` | same | EXACT | |
| 52 | `var int nBotTk, nTopTk` | globals | EXACT | |
| 53 | `if botTick: nBotTk += 1; label.new(bar_index, low, "BOT", label_up, color.new(color.yellow, 20), textcolor=black, tiny, force_overlay=true)` | `OBJ_TEXT` "BOT" in window 0 at `(time, low)`, `ANCHOR_UPPER`, yellow, Arial 7 | EQUIVALENT | as row 35 |
| 54 | `if topTick: … "TOP" at high, label_down, orange, force_overlay` | `OBJ_TEXT` "TOP" in window 0 at high, `ANCHOR_LOWER`, orange | EQUIVALENT | |
| 55 | `var bool legOpen=false; var int legDir=0; var float legP0=na; var int legB0=0; var float legPath=0.0; var string leg1="—"; leg2="—"` | globals; `"—"` = `ShortToString(0x2014)` | EXACT | |
| 56 | `if legOpen and barstate.isconfirmed: legPath += math.abs(close - close[1])` | `if(legOpen && g_prevCloseOk) legPath += MathAbs(cc - g_prevClose)` — before the turn test, as in the Pine | EXACT | `close[1]` is always valid once a leg is open |
| 57 | `if botTurn or topTurn: if legOpen: dist = math.abs(close - legP0); bars = bar_index - legB0; eff = legPath > 0 ? dist / legPath : 0.0; leg2 := leg1; leg1 := (legDir > 0 ? "UP " : "DN ") + str.tostring(dist, "#.##") + " / " + str.tostring(bars) + "b / eff " + str.tostring(eff, "#.00")` | same; `Fmt2` = "#.##", `Fmt00` = "#.00" | EQUIVALENT-ASSUMED | number formats: assumes TradingView prints `0.5` not `.5` and `0.00` for zero, rounding half away from zero like `DoubleToString` |
| 58 | `legOpen := true; legDir := botTurn ? 1 : -1; legP0 := close; legB0 := bar_index; legPath := 0.0` | same | EXACT | |
| 59 | `var table t = table.new(position.middle_right, 2, 10, border_width=1, frame_width=1, frame_color=color.new(color.gray, 50))` | 10×2 `OBJ_LABEL`s + `OBJ_RECTANGLE_LABEL` frame (gray border, transparent) + `OBJ_RECTANGLE_LABEL` blue header, centred on the window height | EQUIVALENT | cell borders have no colour in the Pine (border_color na) so none are drawn |
| 60 | `if showTable and barstate.islast` | `UpdateTable()` on every tick; `isRed`, `posW`, `inLow/inHigh` come from the forming-bar preview, counters/gaps/legs from confirmed state | EXACT | rev 2: same bar the Pine reads |
| 61 | `table.cell(0,0, "XPW Shape Map v0.5", white, bgcolor=color.new(color.blue, 40), tiny)`; `table.cell(1,0, isRed ? "RED" : "LIME", …)` | row 0 white on the blue header rect | EQUIVALENT | no alpha |
| 62 | `table.cell(1,1, str.tostring(posW, "#.00") + (inLow ? " LOW" : inHigh ? " HIGH" : " MID"))` | `Fmt00(posW) + …` | EQUIVALENT-ASSUMED | "#.00" leading-zero assumption (row 57) |
| 63 | `"BOT squares"` / `str.tostring(nBotSq)`; `"TOP squares"` / `nTopSq` | same strings | EXACT | |
| 64 | `"BOT turns"` / `str.tostring(nBotTurn) + "  gap " + str.tostring(lastBotGap) + "b"`; `"TOP turns"` likewise | same strings | EXACT | |
| 65 | `"BOT ticks"` / `nBotTk`; `"TOP ticks"` / `nTopTk` | same | EXACT | |
| 66 | `"Leg -1"` / `leg1`; `"Leg -2"` / `leg2` | same | EXACT | |
| 67 | table cells without `text_color` → Pine default `color.black` | `XPW_BLACK` on rows 1..9 | EXACT | reproduced as is (invisible on a black chart background in the Pine too) |
| 68 | *(none)* | row 10 `"axis"` = measured interval vs expected `_S<n>`, init line, consumption buffers 6..28, dump | DIFFERENT | R8/R10/Gate C additions, as in v0.4 |
| 69 | TradingView draws one bar per second that had ticks | `SkipEmptyBars` + `tick_volume==0` marker | EXACT | R4; default false (G0.2b) |
| 70 | Pine `bar_index` and `x[k]` history | `g_barIndex` + rings keyed by it; `k > bar_index` → na (NA8) | EXACT | rings sized from the inputs in `OnInit` |

---

### Rev 2 (2026-09-22): the realtime bar moves with every tick
As in the v0.4 rev 2: `PreviewBars()` advances COPIES of the RSI, SMA and highest/lowest calculators over the forming
bar on every tick and writes only the visual buffers (FAST, SLOW, RSI, fills) and the table's live cells (`isRed`,
`posW`, `inLow/inHigh`). Detectors, turn marks, ticks, legs and every consumption buffer stay confirmed-bar only.
Emulator receipt (1 500 bars, seed 7): `preview: checks=1041 mismatches_vs_confirmed=0 empty_forming_bars=0`; Gate C
PASS, replay diff 0 unchanged. Rows 17–21 and 60 updated above.

## 3. na rules applied
NA1 comparison with na → false (`isRed`, hold loops, crossover terms, `atrV > 0`, `rngW > 0`); NA2 arithmetic with na → na
(`rngW`, wedge tops); NA3 `ta.rsi` na for bars 0..rsiLen−1; NA4 `ta.sma` na while its window holds na; NA5 `ta.highest/
lowest` na while the window holds na (ASSUMED, Gate B); NA6 `ta.atr` RMA of TR, SMA-seeded, TR(0) = high−low; NA7
`math.max/min` with na → na (ASSUMED, `#define XPW_NA_MAX_PROPAGATES`, unreachable with the v0.5 gates); NA8 `x[k]` with
`k > bar_index` → na, so every `if not v` in `detect()` and every hold/crossover term is false there; NA9 `posW` = 0.5
while `rngW` is na; NA10 bools are never na: `isRed` false and `isLime` true during warm-up, so a warm-up stretch can be
the lime context of a bottom wedge but never a red wedge; NA11 `ta.crossover(a,b)` = `a > b and a[1] <= b[1]`,
`ta.crossunder` = `a < b and a[1] >= b[1]`, false on na; NA12 `var float legP0 = na` (only read once a leg is open).

## 4. Buffer index map (iCustom)
| idx | name | set to | otherwise |
|---|---|---|---|
| 0 / 1 | FAST / SLOW | `fast` / `slow` | EMPTY_VALUE |
| 2,3 / 4,5 | fill red / fill lime | visual | EMPTY_VALUE |
| 6 | BOT_SQ | `botWid` when `botOK` | 0 |
| 7 / 8 | BOT_SQ_TOP / BOT_SQ_BOT | `hh` / `ll` of the wedge | EMPTY_VALUE |
| 9 / 10 / 11 | TOP_SQ / TOP_SQ_TOP / TOP_SQ_BOT | as 6..8 | 0 / EMPTY_VALUE |
| 12 / 13 | BOT_TURN / BOT_TURN_GAP | 1 / `tb − lastBotWedge` | 0 / EMPTY_VALUE |
| 14 / 15 | TOP_TURN / TOP_TURN_GAP | as 12/13 | |
| 16 / 17 | BOT_TICK / TOP_TICK | `dnWick/atrV` / `upWick/atrV` | 0 |
| 18 | STATE | `isRed` 1/0 | — |
| 19 | POSW | `posW` | — |
| 20 | AREA | −1 LOW, 0 MID, +1 HIGH | — |
| 21 / 22 | BOT_ARMED / TOP_ARMED | armed state after the bar, 1/0 | — |
| 23 | LEG_DIR | +1/−1 when a leg closes on this bar | 0 |
| 24 / 25 / 26 | LEG_DIST / LEG_BARS / LEG_EFF | closed-leg values | EMPTY_VALUE |
| 27 / 28 | RSI / ATR | `r` / `atrV` | EMPTY_VALUE |
Dump (`MQL5\Files\XPChart\mapdump05_<symbol>.csv`): `time, open, high, low, close, tick_volume` + the 25 columns above
(`bot_sq … atr`) + `bar_index`.

---

## 5. Gate receipts

### GATE A — PASS
```
PASS  bottom_gates.csv       asserts=761 sq=4/2 turns=3/1 ticks=0/0
PASS  main_area.csv          asserts=325 sq=1/1 turns=1/1 ticks=0/0
PASS  ticks.csv              asserts=30  sq=0/0 turns=0/0 ticks=1/2
PASS  top_gates.csv          asserts=638 sq=1/3 turns=1/2 ticks=0/0
GATE A: PASS
```
Coverage (`fixtures/DERIVATIONS.md`): bottom wedge fires (main t9) and is blocked by AREA (main t24), SEP
(bottom_gates t27), WIDTH (t37), CTX (t42); top wedge fires (main t16) and is blocked by AREA (main: the t22 wedge is
not HIGH), SEP (top_gates t20), WIDTH (t26), CTX (t32); bottom turn fires (t12, t30, t70) and is blocked by EXPIRY (t60)
and HOLD (t68); top turn fires (t19, t23, t39) and is blocked by EXPIRY (top_gates t61); ticks fire and are blocked by
each of rng, ATR, wick/range, wick/ATR; legs close three times with hand-derived strings (`UP 0.5 / 7b / eff 0.08`,
`DN 0 / 11b / eff 0.00`, `UP 1.5 / 40b / eff 0.07`, `UP 3 / 11b / eff 0.33`, `DN 2 / 16b / eff 0.25`). Two hand-division
slips in the first draft (RSI at t12 and t19, 6th decimal) were recomputed by hand from the fractions and corrected before
the second run; every other hand value agreed on the first run.

### GATE B — SKIPPED
No TradingView export attached; `XPW_ShapeMap_v0.5_export.pine` is ready (`diff_harness.py export.csv --tv`).

### GATE C — PASS-EMULATED, LIVE PENDING (`reference/emu/run_emu.sh`)
| Run | Inputs | Result |
|---|---|---|
| stub lint | `g++ -fsyntax-only -Wall -Wextra` | 0 errors, 0 warnings (both NA7 branches) |
| 1 500 bars, seed 7 | defaults | `PASS (mismatches after warm-up: 0; inside warm-up: 0)`; 1 499 rows; 30 boxes + 92 text labels + 24 table objects; replay diff 0; deinit leaves 0 objects |
| 1 200 bars, seed 11 | `LastBarIsClosed=true`, closed feed | PASS, replay diff 0 |
| 1 500 bars, 15 % empty | `SkipEmptyBars=true` / `false` | PASS both, replay diff 0 |
| 40 000 bars, seed 3 | defaults | PASS, replay diff 0; 3 023 objects created, 500 boxes + 500 labels alive (caps hold) |
The driver feeds a 300-bar load, then each new bar as a forming bar first (first tick) and mutated after, three calls
per bar, 5 % 3-bar jumps, then a `prev_calculated=0` replay. Same caveat as v0.4: this proves the logic under C++
semantics, not MetaEditor acceptance or object rendering.

---

## 6. Smoke (host) — closed until the axis receipt
As in the v0.4 report §7, with `mapdump05_XAUUSD-ECNc_S1.csv` and `XPMap/v0.5/reference/diff_harness.py`. The S2
funnel printed by the harness covers wedges raw by width → area → sep, turns (armed bars, crossover bars, hold), and
ticks (rng&atr → wick/range → wick/ATR).

## 7. Open decisions
1. Axis receipt (G0.1). 2. NA5/NA7 via Gate B (NA7 unreachable with the default gates). 3. Number formats `"#.##"` /
`"#.00"` leading zero (rows 57, 62). 4. Label text colour choice (rows 35, 46, 53): text in the label's background colour
because MQL5 text objects have no background; say if a different rendering is wanted. 5. Table values from the last
closed bar (row 60). 6. Table default text colour black, as the Pine (row 67).
