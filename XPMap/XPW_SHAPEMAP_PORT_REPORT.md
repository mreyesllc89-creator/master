PORTED | rows=108 exact=84 equivalent=11 assumed=6 different=7 omitted=0 | A pass, B skipped, C pass-emulated/live-pending | DECISION: yes — ready to run once the host compile is clean; smoke stays closed until the axis receipt arrives (BLOCKED_AXIS_RECEIPT_MISSING)

# XPW Shape Map v0.4 — Pine → MQL5 port report (2026-09-22)

Source of truth: the Pine pasted with the task (`XPW Shape Map v0.4`, `//@version=6`). Nothing was trimmed,
renamed or "improved". Deliverables live in `XPMap/`:

| File | What |
|---|---|
| `XPW_ShapeMap_v0.4.mq5` | the indicator (separate window, 25 buffers, 5 plots, 27 Pine inputs + 3 port-only inputs) |
| `XPW_ShapeMap_v0.4_export.pine` | Gate B build: identical logic + `display.data_window` plots of every internal series |
| `reference/shapemap_ref.py` | pure-Python transliteration of the Pine, same na rules, function by function |
| `reference/diff_harness.py` | Gate C (MQL5 dump vs reference), Gate B (`--tv`), S3 replay diff (`--s3`), zero-result funnel |
| `reference/run_fixtures.py`, `reference/fixtures/*.csv`, `fixtures/DERIVATIONS.md` | Gate A: hand-derived fixtures and the runner |
| `reference/emu/` | stub lint + runtime emulator used for the receipts below (no MetaEditor in the box) |

**Branch note.** The task names `claude/nifty-hamilton-s8s49e`; this session is pinned to `claude/cool-curie-89fhgg`
and may not push elsewhere. `claude/cool-curie-89fhgg` was rebuilt on top of `origin/claude/nifty-hamilton-s8s49e`
(same engine sources, same history) and only adds `XPMap/`, so a fast-forward merge into nifty-hamilton is one command.
No pull request was opened.

**Not in the box.** `axischeck_XAUUSD-ECNc_S1.csv` and `heartbeat_XAUUSD-ECNc_S1.csv` were not attached and are
not in the repo or on disk (searched `/`). MetaEditor is not available; `www.mql5.com` is blocked by the egress
proxy, so the DRAW_FILLING colour-order note was settled by construction instead (R9 row below).

---

## 1. GATE 0

### G0.1 Axis verdict — BLOCKED_AXIS_RECEIPT_MISSING
`axischeck_XAUUSD-ECNc_S1.csv` is not attached. No verdict word can be reported. Per the gate: the port ships,
the smoke (section 5) stays closed. When the receipt arrives: `SECONDS_AXIS_REAL` → open the smoke; `M1_AXIS`
or `EMPTY` → BLOCKED_AXIS. The indicator also measures the axis itself (R10 row 9 and the init line), so a wrong
axis is visible on the chart the moment it is attached.

### G0.2 Engine write semantics (`XPChart/XP ChartEngine v2.mq5`, v2.01)

**(a) Is the last bar a closed second, and can a later CustomTicksAdd mutate it?**

With the deployed default `UpdateRatesEveryTick=false` the engine itself writes only CLOSED seconds:

```
L63   input bool                 UpdateRatesEveryTick = false;                // Write current bar every poll (false = on close)
L740        CloseBar();                                                        // F2: close old ...
L695     AppendRate(r, bar_slot);                       (CloseBar: the closed bar joins pend_rates)
L809     bool with_current = bar_active && include_current;
L810     int nb = ArraySize(pend_rates) + (with_current ? 1 : 0);
L817        if(with_current) CurrentBar(wr[nb - 1]);
L819        int r = CustomRatesUpdate(custom_name, wr);
L1041          if((processed > 0 && UpdateRatesEveryTick) || ArraySize(pend_ticks) > 0 || ArraySize(pend_rates) > 0)
L1042             FlushPending(UpdateRatesEveryTick);                             // false: bars reach the chart on close (+ final flush), as in the August variant
```

`include_current` is `UpdateRatesEveryTick` (false), so `CustomRatesUpdate` never carries the forming second.
But `PushTicks` defaults to true and every tick is pushed:

```
L56   input bool                 PushTicks            = true;                 // Push ticks to custom symbol (off = bars only)
L772     if(PushTicks)                                                         // F11: time and time_msc always consistent
L778        AppendTick(o);
L791        int r = CustomTicksAdd(custom_name, pend_ticks);
```

`CustomTicksAdd` feeds the terminal's own bar builder, which creates and MUTATES a forming bar on the chart
from those ticks (the reconcile report §5 already lists this as fidelity item A2: "the live bar is whatever the
terminal builds from CustomTicksAdd"). So the last element of the chart's rates array CAN be a forming bar that a
later `CustomTicksAdd` mutates, and the engine's closed second for that slot only lands when the slot ends.
**Answer: the last bar is NOT reliably closed → `LastBarIsClosed` defaults to `false`; the indicator evaluates
`rates_total-2` and treats `rates_total-1` as forming.** Whether the terminal-built bar sits at the second or at
the minute boundary is exactly what the missing axis receipt decides; the time-cursor in R3 handles either
ordering without double-processing.

**(b) Empty seconds.** Skipped by default; when enabled, marked by `tick_volume = 0` with a flat OHLC at `last_close`:

```
L54   input bool                 WriteEmptyBars       = false;                // Write flat bars for empty intervals
L744           empty_slots += gap;
L745           if(WriteEmptyBars) WriteGap(prev, gap);
L709        r.open        = last_close;            (WriteGap: open=high=low=close=last_close)
L713        r.tick_volume = 0;
```

**Answer: the deployed engine writes NO bar for a second with no ticks, matching TradingView → `SkipEmptyBars`
defaults to `false`.** If a host runs with `WriteEmptyBars=true`, set `SkipEmptyBars=true`: the marker is
`tick_volume==0` and such bars are then skipped everywhere (RSI, run tracker, ticks, continuity, dump).

### G0.3 Symbol specs
```
L463     SyncInt(SYMBOL_DIGITS,              "SYMBOL_DIGITS");            (custom := parent, read back, PASS/FAIL)
L464     InfoDbl(SYMBOL_POINT,               "SYMBOL_POINT");             (derived from digits, shown only)
L465     SyncDbl(SYMBOL_TRADE_TICK_SIZE,     "SYMBOL_TRADE_TICK_SIZE");   (custom := parent)
```
The engine sets the custom symbol's digits and tick size from the parent and reports the readback in the
`F7 SPEC` lines of the Experts log, so `XAUUSD-ECNc_S1` is expected to carry the same digits / point / tick size
as `XAUUSD-ECNc`. The numeric values are not in the repo (no F7 log or census row carries them), so they are
reported as `parent = custom = <see F7 SPEC lines on the host>`. The indicator never hardcodes them: it reads
`SYMBOL_DIGITS`, `SYMBOL_POINT`, `SYMBOL_TRADE_TICK_SIZE` of the chart symbol in `OnInit` (used for
`format.mintick` and the init line). A `FAIL` on the `SYMBOL_DIGITS` row of the host log would make the table's
`vel` cells print with the custom symbol's digits rather than the parent's; nothing else depends on it.

---

## 2. Design decisions that implement the zero-loss rules

* **R1** ta.rsi / ta.sma / ta.atr / ta.lowest / ta.highest are classes in the indicator (`CXpRsi`, `CXpSma`,
  `CXpRma`, `CXpAtr`, `CXpExtreme`), one instance per Pine call site, no handles. RMA = alpha 1/len, SMA-seeded
  over the first len valid values. RSI edge cases `down==0 → 100`, `up==0 → 0`. TR on the first bar = high−low.
  Windows include the current bar. First-valid bars: RSI at `rsiLen`, fast at `rsiLen+fastLen−1`, slow at
  `rsiLen+slowLen−1`, ATR at `atrLen−1` (checked in the emulator against the reference: identical inside warm-up).
* **R2** Every series carries a valid flag; na never rides on NaN or EMPTY_VALUE arithmetic. The na rule list is
  section 4. The run tracker starts on bar 0 with `stUp=false` and na tops, exactly as the Pine.
* **R3** One pass per closed bar, cursor = time of the last processed bar (`g_lastProcTime`, index hint re-derived
  each call, so index shifts and jumps of any size are safe). `prev_calculated==0` → `ResetAll()` and replay from
  bar 0. Nothing written for a bar is ever touched again (the only later write is the fill-bridge of the previous
  bar's own fast/slow into the new colour's fill buffer, a visual buffer, never a consumption buffer).
* **R4** `SkipEmptyBars` (default false, per G0.2b); marker `tick_volume==0`.
* **R5** All 41 Pine `var`s are globals reset only in `ResetAll()` (table rows below).
* **R6** 27 inputs, same names, defaults, order and groups; `OnInit` clamps to the Pine minval/maxval and prints
  one warning per clamped input. Three port-only inputs sit in their own group `Port (MQL5 only)`.
* **R7** Detectors copied term for term, evaluated in the Pine order: run tracker → ticks → continuity → table.
  Hits stamped at the confirmation bar; the square spans `prevStart..prevEnd` (bar times from a ring keyed by
  Pine `bar_index`) with the same padding rule.
* **R8** Buffer map in section 5 and in the file header.
* **R9** Separate window fixed 0..100; two single-colour DRAW_FILLING plots keyed to `isRedNow` per bar (see row);
  OBJ_RECTANGLE (border 2, no alpha) + OBJ_TEXT tags; tick labels on window 0 at high/low or in the pane at
  95/5; exact Pine colours; caps 500/500 with oldest-first deletion; names `XPWMAP_<chartid>_…`; `OnDeinit`
  removes them.
* **R10** 9-row table of OBJ_LABELs, middle-right; row 0 col 1 = measured interval; row 8 = axis check; one init
  line printed on the first `OnCalculate`.
* **R11** No omissions (count 0), no additions beyond R8/R10 and the three port inputs.

---

## 3. Equivalence table (every Pine statement → MQL5 counterpart)

Classes: EXACT, EQUIVALENT, EQUIVALENT-ASSUMED, DIFFERENT, OMITTED. Line numbers are in `XPW_ShapeMap_v0.4.mq5`
(`mq5:`) and `reference/shapemap_ref.py` (`py:`).

| # | Pine | MQL5 counterpart | Class | Reason / note |
|---|---|---|---|---|
| 1 | `indicator("XPW Shape Map v0.4", "XPW MAP v0.4", overlay=false, max_boxes_count=500, max_labels_count=500)` | `#property indicator_separate_window`, `INDICATOR_SHORTNAME "XPW MAP v0.4"`, `XPW_MAX_BOXES/LABELS 500` | EXACT | separate window; caps enforced in `PushName()` |
| 2 | `rsiLen = input.int(14, "RSI length", minval=2, group="TDI")` | `input int rsiLen = 14` (group TDI) + `ClampInt(rsiLen, 2)` | EXACT | clamp replaces minval, one warning |
| 3 | `fastLen = input.int(2, …, minval=1)` | `input int fastLen = 2` + clamp 1 | EXACT | |
| 4 | `slowLen = input.int(7, …, minval=1)` | `input int slowLen = 7` + clamp 1 | EXACT | |
| 5 | `invertFill = input.bool(true, …)` | `input bool invertFill = true` | EXACT | |
| 6 | `extLook = input.int(20, …, minval=5)` | `input int extLook = 20` + clamp 5 | EXACT | |
| 7 | `loFrac = input.float(0.33, …, minval=0.05, maxval=0.5, step=0.01)` | `input double loFrac = 0.33` + clamp [0.05,0.5] | EXACT | step is a UI hint only |
| 8 | `hiFrac = input.float(0.67, …, 0.5..0.95)` | `input double hiFrac = 0.67` + clamp | EXACT | |
| 9 | `sqBotOn = input.bool(true, "Draw bottom squares", group=gB)` | `input bool sqBotOn = true` (group P1a) | EXACT | |
| 10 | `sqBotMin = input.int(1, minval=1)` | `input int sqBotMin = 1` + clamp | EXACT | |
| 11 | `sqBotMax = input.int(3, minval=1)` | `input int sqBotMax = 3` + clamp | EXACT | |
| 12 | `sqBotCtx = input.int(2, minval=1)` | `input int sqBotCtx = 2` + clamp | EXACT | |
| 13 | `sqBotSep = input.float(0.0, minval=0.0, step=0.1)` | `input double sqBotSep = 0.0` + clamp | EXACT | |
| 14 | `sqBotArea = input.bool(true)` | `input bool sqBotArea = true` | EXACT | |
| 15 | `sqTopOn = input.bool(true)` (group gTp) | `input bool sqTopOn = true` (group P1b) | EXACT | |
| 16 | `sqTopMin = input.int(1, minval=1)` | `input int sqTopMin = 1` + clamp | EXACT | |
| 17 | `sqTopMax = input.int(2, minval=1)` | `input int sqTopMax = 2` + clamp | EXACT | |
| 18 | `sqTopCtx = input.int(3, minval=1)` | `input int sqTopCtx = 3` + clamp | EXACT | |
| 19 | `sqTopSep = input.float(0.0, minval=0.0)` | `input double sqTopSep = 0.0` + clamp | EXACT | |
| 20 | `sqTopArea = input.bool(true)` | `input bool sqTopArea = true` | EXACT | |
| 21 | `tickOn = input.bool(true, "Mark ticks", group=gW)` | `input bool tickOn = true` (group P2) | EXACT | |
| 22 | `atrLen = input.int(14, minval=1)` | `input int atrLen = 14` + clamp | EXACT | |
| 23 | `dnWickFrac = input.float(0.55, 0.1..1.0)` | `input double dnWickFrac = 0.55` + clamp | EXACT | |
| 24 | `dnWickAtr = input.float(0.8, minval=0.0)` | `input double dnWickAtr = 0.8` + clamp | EXACT | |
| 25 | `upWickFrac = input.float(0.70, 0.1..1.0)` | `input double upWickFrac = 0.70` + clamp | EXACT | |
| 26 | `upWickAtr = input.float(1.2, minval=0.0)` | `input double upWickAtr = 1.2` + clamp | EXACT | |
| 27 | `tickPrice = input.bool(true)` | `input bool tickPrice = true` | EXACT | |
| 28 | `showTbl = input.bool(true, group="P3 - continuity")` | `input bool showTbl = true` (group P3) | EXACT | |
| 29 | *(none)* | `input bool LastBarIsClosed = false` | DIFFERENT | port-only, required by R3; default from G0.2a |
| 30 | *(none)* | `input bool SkipEmptyBars = false` | DIFFERENT | port-only, required by R4; default from G0.2b |
| 31 | *(none)* | `input bool DumpCSV = false` | DIFFERENT | port-only, required by Gate C |
| 32 | `rsiv = ta.rsi(close, rsiLen)` | `CXpRsi::Update` (`mq5` class CXpRsi; `py:` class Rsi) | EXACT | RMA(1/len) of up/down, SMA-seeded, down==0→100, up==0→0, na for bars < rsiLen |
| 33 | `fast = ta.sma(rsiv, fastLen)` | `CXpSma g_fast` | EXACT | na while the window holds na |
| 34 | `slow = ta.sma(rsiv, slowLen)` | `CXpSma g_slow` | EXACT | |
| 35 | `stUp = fast > slow` | `stUp = (fastOk && slowOk) ? fast > slow : false` | EXACT | NA1 |
| 36 | `isRedNow = invertFill ? stUp : not stUp` | same | EXACT | NA10 |
| 37 | `cRed = color.new(#ff3b30, 0)`, `cLime = color.new(#32d74b, 0)` | `XPW_RED = C'255,59,48'`, `XPW_LIME = C'50,215,75'` | EXACT | |
| 38 | `plot(rsiv, "RSI", color.new(color.gray, 60))` | plot 1 DRAW_LINE `C'120,123,134'` | EQUIVALENT | Pine gray #787B86 exact; 60 % transparency has no MQL5 counterpart |
| 39 | `pF = plot(fast, "Fast", color.new(color.white, 40))` | plot 2 DRAW_LINE clrWhite | EQUIVALENT | no alpha |
| 40 | `pS = plot(slow, "Slow", color.new(color.aqua, 40))` | plot 3 DRAW_LINE `C'0,188,212'` | EQUIVALENT | Pine aqua #00BCD4 exact; no alpha |
| 41 | `fill(pF, pS, color.new(isRedNow ? cRed : cLime, 62))` | plots 4/5: two DRAW_FILLING plots, "Fill RED" (both colours RED) fed on bars where `isRedNow`, "Fill LIME" otherwise; at a colour change the previous bar's fast/slow is also written into the new colour so the transition segment is drawn | EQUIVALENT | by construction independent of the DRAW_FILLING "first>second" colour order (docs unreachable from the box); no alpha. The forming bar IS filled: `PreviewBars()` recomputes it on every tick (rev 2) |
| 42 | `var bool runInit = false` … `var float runSep = 0.0` (7 vars) | globals `runInit, runState, runLen, runStart, runTop/runTopOk, runBot/runBotOk, runSep/runSepOk`, reset in `ResetAll()` | EXACT | R5 |
| 43 | `var int prevLen = 0` … `var int prev2Len = 0` (8 vars) | `prevLen, prevState, prevStart, prevEnd, prevTop/Ok, prevBot/Ok, prevSep/Ok, prev2Len` | EXACT | R5 |
| 44 | `var int botCount = 0` … `var float lastTopSep = na` (8 vars) | `botCount, topCount, lastBotBar, lastTopBar, lastBotW, lastTopW, lastBotSep/Ok, lastTopSep/Ok` | EXACT | R5 |
| 45 | `sep = math.abs(fast - slow)` | `sepOk = fastOk && slowOk; sep = MathAbs(fast - slow)` | EXACT | NA2/NA8 |
| 46 | `drawSquare(...)`: `h = t - b` | `DrawSquare()`: `h = t - b`, `hOk = tOk && bOk` | EXACT | |
| 47 | `padMin = math.max(refRng * 0.03, 0.10)` | `XpMax(refRng*0.03, refOk, 0.10, true)` | EQUIVALENT-ASSUMED | NA7: na refRng → padMin na (never reached with area gates on; with area off and hi/lo na it yields padv 0) |
| 48 | `padv = h < padMin ? (padMin - h) / 2.0 : 0.0` | `padv = (hOk && padOk && h < padMin) ? (padMin-h)/2 : 0` | EXACT | NA1/NA9 |
| 49 | `box.new(left=l, top=t+padv, right=r, bottom=b-padv, border_color=…, border_width=2, bgcolor=color.new(…,76), xloc=bar_index)` | `OBJ_RECTANGLE` in the sub-window from `time[prevStart]` to `time[prevEnd]`, `t+padv`/`b-padv`, colour, width 2, `OBJPROP_FILL=false`, `OBJPROP_BACK=true` | EQUIVALENT | border kept; translucent bg omitted (no alpha); when t or b is na the Pine box has na coordinates and the MQL5 draws nothing (EQUIVALENT-ASSUMED sub-case, unreachable with the area gates on) |
| 50 | `label.new(x=r, y=isRed ? b-padv : t+padv, text=tag, style=isRed ? label_up : label_down, color=color.new(black,100), textcolor=…, size=tiny)` | `OBJ_TEXT` at `(time[prevEnd], y)`, `ANCHOR_UPPER` for red (hangs below like label_up), `ANCHOR_LOWER` for lime (sits above like label_down), font Arial 7, colour cRed/cLime, no background | EQUIVALENT | size.tiny ≈ 7 pt; transparent background = no background |
| 51 | `if barstate.isconfirmed` (run tracker block) | `ProcessBar()` is called once per closed bar (R3) | EXACT | |
| 52 | `curUp = stUp` | same | EXACT | |
| 53 | `if not runInit: runInit:=true, runState:=curUp, runLen:=1, runStart:=bar_index, runTop:=math.max(fast,slow), runBot:=math.min(fast,slow), runSep:=sep` | same, tops via `XpMax/XpMin` with valid flags, `runStart = g_barIndex` | EQUIVALENT-ASSUMED | NA7 on `math.max(fast, slow)` during warm-up (top/bot stay na for the first run); everything else exact |
| 54 | `else if curUp != runState: prev2Len:=prevLen … prevEnd:=bar_index-1 … runSep:=sep` (14 assignments) | same 14 assignments, flags carried | EQUIVALENT-ASSUMED | NA7 as row 53 |
| 55 | `else: runLen:=runLen+1, runTop:=math.max(runTop, math.max(fast,slow)), runBot:=math.min(…), runSep:=math.max(runSep, sep)` | same via `XpMax/XpMin` | EQUIVALENT-ASSUMED | NA7: a na runTop stays na for the rest of the run (propagation); the alternative branch is compiled-out behind `XPW_NA_MAX_PROPAGATES` |
| 56 | `lo = ta.lowest(slow, extLook)`, `hi = ta.highest(slow, extLook)` | `CXpExtreme g_ext.Update(slow, slowOk, lo, hi)` | EQUIVALENT-ASSUMED | window of extLook bars including the current one; na while the window holds na (NA5, the rule given in the task; Gate B settles it) |
| 57 | `mid = (prevTop + prevBot) / 2.0` | `midOk = prevTopOk && prevBotOk; mid = …` | EXACT | NA2 |
| 58 | `frac = hi > lo ? (mid - lo) / (hi - lo) : 0.5` | `if(extOk && hi > lo) {fracOk = midOk; frac = …} else frac = 0.5` | EXACT | NA1/NA9 |
| 59 | `isLow = frac <= loFrac`, `isHigh = frac >= hiFrac` | `isLow = fracOk && frac <= g_loFrac` etc. | EXACT | NA1 |
| 60 | `wasRed = invertFill ? prevState : not prevState` | same | EXACT | |
| 61 | `botHit = wasRed and runLen == sqBotCtx and prevLen >= sqBotMin and prevLen <= sqBotMax and prev2Len >= sqBotCtx and (not sqBotArea or isLow) and (sqBotSep == 0.0 or prevSep >= sqBotSep)` | same seven terms in the same order (`prevSep >= …` guarded by `prevSepOk`, NA1) | EXACT | |
| 62 | `topHit = (not wasRed) and runLen == sqTopCtx and … isHigh … sqTopSep` | same | EXACT | |
| 63 | `if botHit: botCount+=1, lastBotBar:=prevEnd, lastBotW:=prevLen, lastBotSep:=prevSep` | same | EXACT | |
| 64 | `if sqBotOn: drawSquare(prevStart, prevEnd, prevTop, prevBot, true, hi - lo, str.format("BOT {0}b sep {1}", prevLen, str.tostring(prevSep, "#.##")))` | `DrawSquare(…, true, hi-lo, extOk, StringFormat("BOT %db sep %s", prevLen, Fmt2(prevSep)))` | EXACT | tag text identical (`Fmt2` = "#.##", row 96) |
| 65 | `if topHit: topCount+=1, lastTopBar, lastTopW, lastTopSep` | same | EXACT | |
| 66 | `if sqTopOn: drawSquare(…, false, hi - lo, "TOP {0}b sep {1}")` | same | EXACT | |
| 67 | `atrv = ta.atr(atrLen)` | `CXpAtr g_atr` | EXACT | RMA of TR, SMA-seeded, TR(bar 0) = high−low |
| 68 | `rng = high - low` | `rng = hh - ll` | EXACT | |
| 69 | `upW = high - math.max(open, close)` | `upW = hh - MathMax(oo, cc)` | EXACT | |
| 70 | `dnW = math.min(open, close) - low` | `dnW = MathMin(oo, cc) - ll` | EXACT | |
| 71 | `upTick = tickOn and barstate.isconfirmed and rng > 0 and upW >= upWickFrac * rng and upW >= upWickAtr * atrv` | `upTick = tickOn && rng > 0 && upW >= g_upWickFrac*rng && (atrOk && upW >= g_upWickAtr*atrv)` | EXACT | isconfirmed is implicit (closed bars only); NA1 on the ATR term |
| 72 | `dnTick = …` | same | EXACT | |
| 73 | `var int upTickN = 0` … `var float lastDnAtr = na` (6 vars) | `upTickN, dnTickN, lastUpTk, lastDnTk, lastUpAtr/Ok, lastDnAtr/Ok` | EXACT | R5 |
| 74 | `if upTick: upTickN+=1, lastUpTk:=bar_index, lastUpAtr:=upW/atrv, txt = str.format("^ {0} ATR", …"#.##")` | same, `StringFormat("^ %s ATR", Fmt2(lastUpAtr))` | EXACT | |
| 75 | `if tickPrice: label.new(bar_index, high, txt, style=label_down, color=black/100, textcolor=orange, size=tiny, force_overlay=true)` | `OBJ_TEXT` in window 0 at `(time[i], high)`, `ANCHOR_LOWER`, `C'255,152,0'`, Arial 7 | EQUIVALENT | Pine orange #FF9800 exact; size/anchor approximation |
| 76 | `else: label.new(bar_index, 95, txt, style=label_down, …)` | `OBJ_TEXT` in the sub-window at `(time[i], 95)`, `ANCHOR_LOWER` | EQUIVALENT | fixed 0..100 scale keeps 95 meaningful |
| 77 | `if dnTick: dnTickN+=1, lastDnTk, lastDnAtr:=dnW/atrv, txt2 = "v {0} ATR"` | same | EXACT | |
| 78 | `if tickPrice: label.new(bar_index, low, txt2, style=label_up, textcolor=yellow, force_overlay=true)` | `OBJ_TEXT` in window 0 at low, `ANCHOR_UPPER`, `C'255,235,59'` | EQUIVALENT | Pine yellow #FFEB3B exact |
| 79 | `else: label.new(bar_index, 5, txt2, style=label_up, …)` | `OBJ_TEXT` in the sub-window at 5, `ANCHOR_UPPER` | EQUIVALENT | |
| 80 | `var int mDir = 0` … `var float m2Path = na` (10 vars) | `mDir, mBars, mStart/Ok, mPath/Ok, m1Bars, m1Net/Ok, m1Path/Ok, m2Bars, m2Net/Ok, m2Path/Ok` | EXACT | R5 |
| 81 | `if barstate.isconfirmed` (continuity block) | inside `ProcessBar()` | EXACT | |
| 82 | `stp = close - close[1]` | `stpOk = g_prevCloseOk; stp = cc - g_prevClose` | EXACT | NA11 on bar 0 |
| 83 | `d = stp > 0 ? 1 : stp < 0 ? -1 : mDir` | `d = (stpOk && stp > 0) ? 1 : (stpOk && stp < 0) ? -1 : mDir` | EXACT | NA1/NA9 |
| 84 | `if mDir == 0: mDir:=d, mBars:=1, mStart:=close[1], mPath:=math.abs(stp)` | same with flags (`mStartOk = g_prevCloseOk`, `mPathOk = stpOk`) | EXACT | |
| 85 | `else if d == mDir: mBars+=1, mPath:=mPath+math.abs(stp)` | same, na-propagating | EXACT | |
| 86 | `else: m2Bars:=m1Bars, m2Net:=m1Net, m2Path:=m1Path, m1Bars:=mBars, m1Net:=close[1]-mStart, m1Path:=mPath, mDir:=d, mBars:=1, mStart:=close[1], mPath:=math.abs(stp)` | same ten assignments with flags | EXACT | |
| 87 | `eff1 = na(m1Path) or m1Path == 0 ? na : math.abs(m1Net) / m1Path` | `eff1Ok = m1PathOk && m1Path != 0 && m1NetOk` | EXACT | the extra `m1NetOk` term only encodes that `abs(na)/x` is na (NA2) |
| 88 | `eff2 = …` | same | EXACT | |
| 89 | `vel1 = na(m1Net) or m1Bars == 0 ? na : math.abs(m1Net) / m1Bars` | `vel1Ok = m1NetOk && m1Bars != 0` | EXACT | |
| 90 | `vel2 = …` | same | EXACT | |
| 91 | `f(x, p) => na(x) ? "-" : str.tostring(x, p)` | `FmtNa(x, ok, mintick)` | EXACT | |
| 92 | `var table tb = table.new(position.middle_right, 2, 8, border_width=1)` | 9×2 `OBJ_LABEL`s in the sub-window, `CORNER_RIGHT_UPPER`, y centred on the window height, column 1 right-aligned and column 0 placed left of the widest column-1 string (`TextGetSize`) | EQUIVALENT | Pine's default table has no visible bg/border (border_color na), so no frame is drawn either |
| 93 | `if showTbl and barstate.islast` | `UpdateTable()` on every tick; `isRedNow` and `sep` come from the forming-bar preview, `runLen` and the counters from confirmed state | EXACT | rev 2: same bar the Pine reads (`barstate.islast`) |
| 94 | `table.cell(0,0, "XPW MAP v0.4", white, small)`; `table.cell(1,0, timeframe.period, white, small)` | row 0: `"XPW MAP v0.4"` / measured interval string (`"1s"`), Arial 9 | DIFFERENT | R10: measured median of `time[i]-time[i-1]` over the last 200 bars, never `Period()` |
| 95 | `table.cell(1,1, str.format("{0} {1}b sep {2}", isRedNow ? "RED" : "LIME", runLen, f(sep,"#.##")), text_color = isRedNow ? cRed : cLime, tiny)` | `StringFormat("%s %db sep %s", …)`, colour cRed/cLime, Arial 7 | EXACT | string identical; see row 93 for the bar it reads |
| 96 | `str.tostring(x, "#.##")` | `Fmt2()`: `DoubleToString(x, 2)` with trailing zeros and dot trimmed | EQUIVALENT-ASSUMED | assumes TradingView prints `0.5` (not `.5`) and rounds half away from zero like `DoubleToString`; only strings are affected |
| 97 | `table.cell(1,2, botCount == 0 ? "none" : str.format("n={0}  last {1}b sep {2}, {3} bars ago", botCount, lastBotW, f(lastBotSep,"#.##"), bar_index - lastBotBar), cRed)` | `StringFormat("n=%d  last %db sep %s, %d bars ago", botCount, lastBotW, FmtNa(lastBotSep), g_barIndex - lastBotBar)` | EXACT | `g_barIndex` is the Pine `bar_index` (logical bar count) |
| 98 | `table.cell(1,3, topCount == 0 ? "none" : …, cLime)` | same | EXACT | |
| 99 | `table.cell(1,4, dnTickN == 0 ? "none" : str.format("n={0}  last {1} ATR, {2} bars ago", dnTickN, f(lastDnAtr,"#.##"), bar_index - lastDnTk), yellow)` | same | EXACT | |
| 100 | `table.cell(1,5, upTickN == 0 ? "none" : …, orange)` | same | EXACT | |
| 101 | `table.cell(1,6, m1Bars == 0 ? "-" : str.format("{0}b eff {1} vel {2}  \|  {3}b eff {4} vel {5}", m1Bars, f(eff1,"#.##"), f(vel1, format.mintick), m2Bars, f(eff2,"#.##"), f(vel2, format.mintick)), white)` | same; `format.mintick` → `FmtMintick()` = rounded to `SYMBOL_TRADE_TICK_SIZE`, printed with `SYMBOL_DIGITS` (G0.3) | EXACT | |
| 102 | `table.cell(1,7, na(eff1) or na(eff2) ? "-" : (eff1 > eff2 ? "move-1 more continuous" : eff1 < eff2 ? "move-2 more continuous" : "equal"), aqua)` | same | EXACT | |
| 103 | column-0 labels `"state"`, `"BOTTOM squares"`, `"TOP squares"`, `"BOTTOM ticks"`, `"TOP ticks"`, `"move -1 / -2"`, `"continuity"` (gray, tiny) | same strings, `C'120,123,134'`, Arial 7 | EXACT | |
| 104 | *(none)* | row 8 `"axis"` = `"<measured>s measured, expected <n>s: OK/MISMATCH"`; expected n parsed from the `_S<n>` suffix of the chart symbol (engine F14 naming), default 1 | DIFFERENT | the one permitted R10 addition |
| 105 | *(none)* | init line: `XPW MAP v0.4 init: symbol= digits= point= tick_size= measured_interval_s= expected_interval_s= axis_ok= LastBarIsClosed= SkipEmptyBars= DumpCSV= bars_loaded= subwindow=` | DIFFERENT | required by R10 |
| 106 | *(none)* | consumption buffers 7..24 (R8) and the `DumpCSV` writer (Gate C) | DIFFERENT | required by R8 / Gate C; values are the Pine series stamped at the confirmation bar |
| 107 | TradingView draws one bar per second that had ticks | `SkipEmptyBars` + `tick_volume==0` marker | EXACT | R4; default false because the deployed engine writes no empty bars (G0.2b) |
| 108 | Pine `bar_index` | `g_barIndex` (count of processed logical bars, −1 before the first) | EXACT | time-to-index ring `g_timeRing` gives the bar time of any index a square can reference |

Every row was checked in three ways: fixtures (Gate A), the reference (reviewed line by line against the Pine),
and the emulated MQL5 run (Gate C-emulated), which compares the MQL5 code's own output with the reference on
every bar including warm-up.

---

### Rev 2 (2026-09-22): the realtime bar moves with every tick
Rev 1 left the forming bar empty, so the RSI/fast/slow lines and the fill froze until the bar closed (the host saw the
lines stop one bar short). Rev 2 adds `PreviewBars()`: on every `OnCalculate`, the RSI, fast and slow calculators are
COPIED (`CopyFrom`), the copy is advanced over the forming bar(s), and only the visual buffers (RSI, FAST, SLOW, the two
fills) and the table's live cells (`isRedNow`, `sep`) are written for those bars. Consumption buffers of a forming bar
stay EMPTY_VALUE, the detectors still run once per closed bar, and no confirmed value is ever touched; the one write into
the last closed bar is the fill bridge into the preview colour (visual only, restored on every tick). This is what
TradingView does: the realtime bar's plot updates with each tick and is fixed at close. Emulator receipt (1 500 bars,
seed 7): `preview: checks=1041 mismatches_vs_confirmed=0 empty_forming_bars=0` — the preview on the last tick equals the
value stamped when the bar closes, and the forming bar is never left empty; Gate C and the replay diff are unchanged
(PASS / 0 rows). Rows 38–41 and 93 updated above.

## 4. na rules applied (each one is implemented with an explicit valid flag, never with NaN arithmetic)

| Rule | Pine behaviour reproduced | Where |
|---|---|---|
| NA1 | na in a comparison → false (`stUp`, `isLow/isHigh`, `hi > lo`, wick/ATR terms, `prevSep >= sqXSep`, `stp > 0`) | `mq5 ProcessBar`, `py gt/ge/lt/le` |
| NA2 | na in arithmetic → na (`sep`, `mid`, `frac`, `mPath`, `m1Net`, `eff/vel`) | flags `*Ok` |
| NA3 | `ta.rsi` na for bars 0..rsiLen−1 (first change is na, RMA seeds on the first rsiLen valid changes) | `CXpRsi` / `Rsi` |
| NA4 | `ta.sma` na while its window holds na | `CXpSma` / `Sma` |
| NA5 | `ta.lowest/highest` na while the window (extLook bars incl. current) holds na — rule from the task, ASSUMED for TradingView (Gate B) | `CXpExtreme` / `Extreme` |
| NA6 | `ta.atr` = RMA(TR, len), SMA-seeded, TR(bar 0) = high−low; first valid at atrLen−1 | `CXpAtr` / `Atr` |
| NA7 | `math.max/math.min` with an na argument → na (ASSUMED; `#define XPW_NA_MAX_PROPAGATES` / `NA_MAX_PROPAGATES = True`; both branches compile) | `XpMax/XpMin` / `pmax/pmin` |
| NA8 | `math.abs(na)` → na | `pabs`, flags |
| NA9 | ternary with an na condition takes the else branch (`frac`, `d`) | rows 58, 83 |
| NA10 | bools are never na: `stUp` is false while fast/slow are na, so `not stUp` is true and the warm-up run has `isRedNow = not invertFill` | row 36 |
| NA11 | `close[1]` is na on bar 0: `stp` na → `d = mDir = 0`, `mStart` na, `mPath` na; `ta.tr` uses high−low | rows 67, 82, 84 |
| NA12 | `var float x = na` initialisers: `runTop, runBot, prevTop, prevBot, lastBotSep, lastTopSep, lastUpAtr, lastDnAtr, mStart, m1Net, m1Path, m2Net, m2Path`; `var int lastBotBar/lastTopBar/lastUpTk/lastDnTk = na` (only read behind the `count == 0` guards) | `ResetAll()` |
| NA13 | warm-up run tracker: bar 0 starts a run with `runState=false`, `runTop/runBot` na (NA7) and `runSep` na; the first flip inherits na `prevTop/prevBot/prevSep`, so `mid` is na, `isLow/isHigh` false and the first prev run cannot pass an area gate; with the area gate off `sqXSep == 0.0` short-circuits the sep gate and a hit with na coordinates stamps the flag buffers with EMPTY_VALUE tops and draws nothing (row 49) | reproduced, not "fixed" |

---

## 5. Buffer index map for `iCustom` (all stamped at the confirmation bar)

| idx | name | value when set | otherwise |
|---|---|---|---|
| 0 | RSI | `rsiv` | EMPTY_VALUE (na) |
| 1 | FAST | `fast` | EMPTY_VALUE |
| 2 | SLOW | `slow` | EMPTY_VALUE |
| 3, 4 | fill RED (fast, slow) | visual only | EMPTY_VALUE |
| 5, 6 | fill LIME (fast, slow) | visual only | EMPTY_VALUE |
| 7 | BOT_HIT | `prevLen` on a bottom hit | 0 |
| 8 | BOT_SEP | `prevSep` | EMPTY_VALUE |
| 9 | BOT_TOP | `prevTop` | EMPTY_VALUE |
| 10 | BOT_BOT | `prevBot` | EMPTY_VALUE |
| 11 | TOP_HIT | `prevLen` on a top hit | 0 |
| 12 | TOP_SEP | `prevSep` | EMPTY_VALUE |
| 13 | TOP_TOP | `prevTop` | EMPTY_VALUE |
| 14 | TOP_BOT | `prevBot` | EMPTY_VALUE |
| 15 | UP_TICK | `upW/atrv` | 0 |
| 16 | DN_TICK | `dnW/atrv` | 0 |
| 17 | EFF1 | `eff1` | EMPTY_VALUE (na) |
| 18 | EFF2 | `eff2` | EMPTY_VALUE |
| 19 | VEL1 | `vel1` | EMPTY_VALUE |
| 20 | VEL2 | `vel2` | EMPTY_VALUE |
| 21 | MBARS | `mBars` | — (every processed bar) |
| 22 | STATE | `isRedNow` 1/0 | — |
| 23 | RUNLEN | `runLen` | — |
| 24 | ATR | `atrv` | EMPTY_VALUE |

Unprocessed bars (the forming bar with `LastBarIsClosed=false`, bars skipped by `SkipEmptyBars`) hold EMPTY_VALUE
in every buffer. Header comment in the file: an EA on a custom chart must trade the PARENT symbol; custom symbols
do not trade.

Dump columns (`MQL5\Files\XPChart\mapdump_<symbol>.csv`, `DumpCSV=true`): `time, open, high, low, close,
tick_volume, bot_hit, bot_sep, bot_top, bot_bot, top_hit, top_sep, top_top, top_bot, up_tick, dn_tick, eff1,
eff2, vel1, vel2, mbars, state, runlen, rsi, fast, slow, atr, bar_index` — one row per processed closed bar,
`na` for EMPTY_VALUE, 8 decimals. The file is truncated and rewritten on every full recalc (`prev_calculated==0`).

---

## 6. Gate receipts

### GATE A — fixtures: PASS
`python3 reference/run_fixtures.py`
```
PASS  bottom_area.csv    asserts=65  bars=12 bot=1 top=0 up=0 dn=0 squares=1 labels=1
PASS  bottom_gates.csv   asserts=90  bars=18 bot=1 top=0 up=0 dn=0 squares=1 labels=1
PASS  bottom_sep_block.csv asserts=8   bars=8 bot=0 top=0 up=0 dn=0 squares=0 labels=0
PASS  bottom_sep_pass.csv asserts=8   bars=8 bot=1 top=0 up=0 dn=0 squares=1 labels=1
PASS  continuity.csv     asserts=70  bars=14 bot=0 top=0 up=0 dn=0 squares=0 labels=0
PASS  ticks.csv          asserts=33  bars=10 bot=0 top=0 up=2 dn=1 squares=0 labels=3
PASS  top_area.csv       asserts=68  bars=13 bot=0 top=1 up=0 dn=0 squares=1 labels=1
PASS  top_gates.csv      asserts=85  bars=19 bot=0 top=1 up=0 dn=0 squares=1 labels=1
PASS  top_sep_block.csv  asserts=9   bars=9 bot=0 top=0 up=0 dn=0 squares=0 labels=0
PASS  top_sep_pass.csv   asserts=9   bars=9 bot=0 top=1 up=0 dn=0 squares=1 labels=1
GATE A: PASS
```
Coverage (fixtures/DERIVATIONS.md has every number): bottom square fires (bottom_area t=7) and is blocked by
width (bottom_gates t=17), ctx (bump at t=8 never confirmed), prev2Len (t=12), area (bottom_area t=11), sep
(bottom_sep_block); top square fires (top_area t=8) and is blocked by width (top_gates t=13), ctx (dip at t=14),
prev2Len (t=18), area (top_area t=12), sep (top_sep_block); up tick fires (ticks t=4, t=9) and is blocked by
rng==0 (t=3), wick/range (t=1), wick/ATR (t=2, 7, 8); down tick fires (t=5) and is blocked by rng==0 (t=3),
wick/range (t=1), wick/ATR (t=6); continuity covers direction flips, zero step while `mDir==0`, zero step as a
continuation, and the na chain of the first move. RSI/ATR/state/runLen are asserted bar by bar. 445 asserts, all
derived by hand before the runner was executed; the runner passed on its first execution.

### GATE B — TradingView ground truth: SKIPPED
No TradingView export was attached, none was invented. `XPW_ShapeMap_v0.4_export.pine` is ready: put it on the
1S XAUUSD chart with the panel settings, export chart data, then
`python3 reference/diff_harness.py export.csv --tv [--params k=v …]`. It settles NA5 and NA7 (rows 47, 53–56)
and the `"#.##"` assumption (row 96) is checked by eye against the tags.

### GATE C — MQL5 vs reference on live bars: PASS-EMULATED, LIVE PENDING
No terminal in the box, so the MQL5 source itself was executed through `reference/emu/` (a mechanical
MQL5→C++ translation linked to a stub runtime; `run_emu.sh` reproduces everything below). The driver feeds
synthetic seconds bars the way MT5 does: a 300-bar history load with `prev_calculated=0`, then one new bar at a
time delivered first as a forming bar (first tick only) and then mutated, three calls per bar, 5 % of the bars
arriving as 3-bar jumps, and finally a `prev_calculated=0` replay.

| Run | Inputs | Result |
|---|---|---|
| stub lint | `g++ -fsyntax-only -Wall -Wextra` on the translation | 0 errors, 0 warnings |
| 1 200 bars, seed 7 | defaults, DumpCSV | `GATE C RESULT: PASS (mismatches after warm-up: 0; inside warm-up: 0)`, 1 199 rows (the forming bar is not stamped), 25 boxes + 49 text labels + 18 table labels, replay diff 0 rows, `OnDeinit` leaves 0 objects |
| 1 200 bars, seed 11 | `LastBarIsClosed=true`, feed with mutating forming bars | reference diff PASS, but the replay diff shows 9 766 differing cells: the forming bar was stamped in its partial state. This is the R3 hazard the default `false` guards against, not a defect; with a feed whose last bar is really closed (driver flag 4) the same run gives replay diff 0 rows and 1 201 rows |
| 1 500 bars, seed 5, 15 % empty bars | `SkipEmptyBars=true` | 1 272 rows, none with `tick_volume==0`, reference diff PASS, replay diff 0 |
| 1 500 bars, seed 5, 15 % empty bars | `SkipEmptyBars=false` | 227 empty rows processed as bars, reference diff PASS |
| 40 000 bars, seed 3 | defaults | 39 999 rows, reference diff PASS, replay diff 0; 2 254 objects created over the run, 500 boxes + 500 labels alive at the end (caps hold), 7 556 state flips |
| alternative NA7 branch | `XPW_NA_MAX_PROPAGATES` commented out | compiles clean |

Live Gate C (the real dump from 86AD) is pending the host: attach with `DumpCSV=true`, then
`python3 reference/diff_harness.py MQL5/Files/XPChart/mapdump_XAUUSD-ECNc_S1.csv`.

Caveat on the emulation: it proves the MQL5 *logic* against the reference under C++ semantics; it cannot prove
what only MetaEditor and the terminal can (compile acceptance of every property/enum, object rendering, the
sub-window index, `prev_calculated` behaviour on custom-symbol history updates). Those are the smoke.

---

## 7. Smoke (host-side) — CLOSED until the axis receipt (BLOCKED_AXIS_RECEIPT_MISSING)

S1 procedure once open: compile `XPMap/XPW_ShapeMap_v0.4.mq5` in MetaEditor (strict warnings; paste errors
back), attach to `XAUUSD-ECNc_S1` on 86ADC2D106E3946A8F8D9E6D2FD89531, defaults, `DumpCSV=true`, 10 minutes.
Receipts: pane + table screenshot, `MQL5\Files\XPChart\mapdump_XAUUSD-ECNc_S1.csv`, the
`XPW MAP v0.4 init:` line from the Experts log (it carries symbol, digits, point, tick size, measured interval,
axis_ok, LastBarIsClosed, SkipEmptyBars, bars loaded).

S2 zero-result contingency is built into the harness: `diff_harness.py` prints the gate-by-gate funnel (bars
processed, state flips, candidate runs by prev width, width/prev2Len/area/sep passes, tick candidates by
wick/range and wick/ATR) on every run. Reference fires nothing → ZERO_TRUE with that funnel. Reference fires,
indicator does not → the mismatch lines name the bar and the buffer (e.g. `bot_hit: file=0 ref=1` =
BLOCKED_HIT_NOT_STAMPED); fix that one thing, rerun once.

S3 replay: copy the dump to `dump_A.csv`, detach and re-attach (forces `prev_calculated=0`, the file is
rewritten), copy to `dump_B.csv`, then `python3 reference/diff_harness.py --s3 dump_A.csv dump_B.csv` → receipt
is `S3 replay diff rows: 0 -> PASS`. Squares and labels are keyed by bar time, so an identical dump implies
identical objects.

Also watch in the Experts log: `full recalc #n` lines. If the terminal resets `prev_calculated` on every
`CustomRatesUpdate` (possible on custom symbols), n grows by one per second; the indicator stays correct
(deterministic replay) but rewrites the dump and re-creates the objects each time. That would be the first
performance item to report, not a fidelity item.

---

## 8. Open decisions

1. **Axis receipt** (G0.1) — needed before the smoke opens. The indicator's own `axis` row and init line give a
   second reading the moment it is attached.
2. **NA7** `math.max(na, x)` (rows 47, 53–56): propagate-na assumed. Gate B settles it; flipping is one
   `#define` in the MQL5 and one constant in the reference. Effect is confined to the very first run after load
   and to squares drawn with the area gate off.
3. **NA5** `ta.lowest/highest` with na inside the window (row 56): task rule assumed. Gate B settles it. Effect:
   whether an area verdict can exist during the first `rsiLen+slowLen+extLook−2` bars.
4. **Table timing** (row 93): last closed bar instead of the forming bar. Deliberate under R3; say so if the
   host wants the Pine's live flicker back.
5. **DRAW_FILLING** (row 41): implemented as two single-colour fills so the docs' colour order is irrelevant; if
   the host prefers the single-plot form, the colour order must be verified on the terminal first.
6. **`prev_calculated` on custom-symbol updates** (section 7): observe `full recalc #n` in the smoke.
7. **G0.3 numeric digits** — not receipted here; the init line prints them.
