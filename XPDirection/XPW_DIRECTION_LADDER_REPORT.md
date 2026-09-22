WIRED | G0 BLOCKED_NO_TESTER (pre-check PASS: static 9/9, executed 606 checks 0 failures) | G1 asserts=833 mismatches=0 | G2 pending | G3 pending | POLARITY CONFIRMED | OWNER_TO_CONFIRM: EarlySepMult=2.0, RequireFreshS1=false, S1RequiredAgainstParent=true | DECISION: yes

# XPW Direction Ladder v1 — report

The EA keeps its trigger. It stops choosing its side.

Build: `XPDirection/FlashGold_Continuation_v2_XPDIR.mq5`, `#property version "1.05-XPDIR"`.
Base: the attached `FlashGold_Continuation_v2.mq5`, `1.03`, 4,495 lines,
sha256 `75820278a87ee5b65d9e6c4518a1ab0936d229fed6025893c188bca2f3d87498` — verified
by `patch.py` before a single edit was applied. Nothing from the 1.04 direction-lock,
ANAT1 or TRIGREC builds is in this file.

Direction source: `XPMap/XPW_ShapeMap_v0.4.mq5` at commit `579cb33` on
`claude/cool-curie-89fhgg`. Not modified. Not one of its 27 detector inputs retuned.

**The ladder's direction is only as good as the map. The map's Gate C (mapdump diff)
and Gate B (TradingView export diff) are still open. Until they close, a correct
ladder can still point the wrong way, because it is reading an unverified map.**

---

## 0. What the files said that the prompt did not

These are stated first because one of them can invert every trade, and one of them was
a live risk until the contract zip arrived and closed it.

### DISCREPANCY-1 — RESOLVED by the contract zip: two buffer maps existed

The `XPW_ShapeMap_v0.4.mq5` attached to the original prompt was a 37-line sketch with
`indicator_buffers 26` and a buffer map placing `FAST` at 24, `SLOW` at 25, `STATE` at
20 and `RUNLEN` at 21. The map named in §0 as the source of truth
(`XPMap/XPW_ShapeMap_v0.4.mq5` @ `579cb33`) is 1,191 lines with `indicator_buffers 25`,
`FAST` at 1, `SLOW` at 2, `STATE` at 22, `RUNLEN` at 23. Different programs, and reading
the sketch's indices would have had the ladder voting on `VEL2` against `SLOW`.

**`XPMap_ShapeMap_v0.4.zip`, supplied 2026-09-22, settles it.** Its
`XPMap/XPW_ShapeMap_v0.4.mq5` is **byte-identical** to the repository file at `579cb33`:

```
$ diff <(git show 579cb33:XPMap/XPW_ShapeMap_v0.4.mq5) mapzip/XPMap/XPW_ShapeMap_v0.4.mq5
IDENTICAL
sha256  5653130d70853b643630854ea1bb22b780028acd8d47c9198aa56b9759b52120
```

The zip's `XPW_SHAPEMAP_PORT_REPORT.md` §5 gives the same map ("25 buffers, 5 plots, 27
Pine inputs + 3 port-only inputs"; `1 FAST`, `2 SLOW`, EMPTY_VALUE for na), and its 30
inputs parse in exactly the declaration order this build binds positionally. **The
contract and the build agree on every index and every parameter position.** The prompt's
37-line attachment is a stub and nothing was taken from it.

**`BLOCKED_MAP_CONTRACT_MISSING` therefore does not apply** — the contract is in hand,
and no index was guessed.

### The build checks the contract at runtime anyway

Because two buffer maps were in circulation, `XPDir_ProbeBufferContract` runs once per
rung on its first valid read. `FAST` and `SLOW` are SMAs of RSI, so a valid value sits
inside [0, 100] — the map declares `INDICATOR_MINIMUM 0` / `INDICATOR_MAXIMUM 100`
itself. Values outside that band mean the indicator answering `InpDirMapIndicator` does
not have the buffer map this build was compiled against:

```
XPDIR BUF_CONTRACT rung=S1 verdict=OK fast_idx=1 slow_idx=2 fast=54.3117 slow=51.8802
XPDIR BLOCKED_MAP_CONTRACT_MISMATCH rung=S1 fast_idx=1 slow_idx=2 fast=... slow=...
   - these are not SMAs of RSI ... this rung is silenced.
```

A mismatching rung is silenced rather than voted on. If the host ever drops the wrong
build of the indicator into `MQL5\Indicators`, the log says so in one line instead of
the ladder trading on `VEL2`.

### DISCREPANCY-2 — there is no "expected interval" input to override

§3.3 lists "expected interval = the rung's seconds" among the five overrides. The map
has no such input. It derives it:

```mql5
long ParseExpectedInterval(string sym)   // XPW_ShapeMap_v0.4.mq5:493
{
   int p = StringFind(sym, "_S");        // engine naming: <parent>_S<n> -> n seconds
   ...
}
g_expectedInterval = ParseExpectedInterval(_Symbol);   // OnInit
```

Because every child rung's symbol is `<parent>_S<n>`, the derivation is already
correct for S1..S45 and there is nothing to pass. The **parent** rung runs on
`XAUUSD-ECNc`, which has no `_S<n>`, so `ParseExpectedInterval` returns 1 and the
map's axis row reads `MISMATCH` for the parent. That flag is cosmetic — `g_axisOk`
is written at line 794 and read only by the table and the init print; it gates no
computation. The EA logs one `XPDIR NOTE rung=P` line at init saying so, so the host
does not chase it.

### XPDIR_POLARITY — RESOLVED by the owner, 2026-09-22

**Ignore the fill entirely. Read the two lines.** White is fast, darker is slow. Fast
moves first because it is the shorter average. Fast above slow is momentum up, fast
below slow is momentum down, and the moment fast crosses slow is the signal.

```
fast > slow  ->  BUY
fast < slow  ->  SELL
the cross    ->  the moment
```

That is what the build already does, and it is now confirmed rather than assumed.
`XPDir_Sign` is the single place polarity is decided, and Gate 1 covers it.

**The owner's own frames are the proof, and they show the colour lying twice:**

| Window | Price | Lines | Fill painted |
|---|---|---|---|
| 20:56 → 20:57 | climbing | fast **above** slow | **RED** |
| 20:57 → | dropping | fast **below** slow | **GREEN** |

The fill ran opposite to price both times. That is `invertFill = true` doing exactly
what it says on the input — `isRedNow = invertFill ? stUp : !stUp` at
`XPW_ShapeMap_v0.4.mq5:814` — and it is why a ladder that read the colour would have
bought every top and sold every bottom in those two minutes.

So the earlier question — "is the bullish state the RED fill or the LIME one?" — was
the wrong question to answer in the first place. The colour is not a thing to be read
correctly. It is a thing not to be read. The build reads `FAST` (buffer 1) and `SLOW`
(buffer 2) and **never touches `STATE`** (buffer 22) for direction.

### Why `STATE` is logged but never voted on

`BufState` is not usable as either a vote or a validity flag:

- it is `isRedNow`, so `invertFill` flips its meaning;
- `stUp` is forced `false` when `!fastOk || !slowOk`, so `STATE == 0` means *either*
  "fast ≤ slow" *or* "the bar is invalid" — indistinguishable.

`BufFast`/`BufSlow` carry the map's own valid flag (`BufFast[i] = fastOk ? fast :
EMPTY_VALUE`, line 973). The cross is computed from those, and `STATE` is carried into
the logs for cross-check only. This is what §3.2's "use it if the map exposes a state
buffer" becomes once the file is read rather than described — and it is reinforced by
§1: the map's `STATE` is a colour, and the colour is not the signal.

---

## 1. The cross is the signal

Owner's correction of 2026-09-22 plus the six answers of the same day, which supersede
the earlier paste. Direction is not the fill colour. It is the cross of the fast (white)
line through the slow line; the colour is what the cross leaves behind. A cross has a
moment and an age. A colour has neither.

Every rung reports a cross event:

| Field | Meaning |
|---|---|
| `crossDir` | direction of the **most recent cross since warm-up**, +1 up / −1 down, **held until the next cross**; 0 only while none has been seen |
| `crossAge` | closed bars since that cross; **0 = it happened on the bar just closed**; −1 = none seen yet |
| `crossSep` | `fast − slow` at the cross bar, in the map's own units |
| `sepNow` | `fast − slow` on the bar being read |
| `carriedSign` | the sign carried forward through ties — the state floor, never the signal |

"Crossed on this bar" is `crossAge == 0`. There is no separate flag.

### Equality is not a sign

A bar where `fast == slow` **inherits the previous closed bar's carried sign**. A touch
is not a cross. A touch that resumes the same side is not a cross either. Only a
**strict flip of the carried sign** is a cross, and it is stamped on the bar where the
new non-zero sign appears — not on the touch bar. If the very first valid bar is a tie,
the sign is 0 and the rung does not vote until it resolves.

**This deliberately differs from Pine's `ta.crossover`,** which fires on the touch bar.
Fixtures `touch_and_resume_is_not_a_cross` and `touch_then_flip_stamps_on_new_sign` pin
both halves.

### Closed bars only

`XPDir_ReadRung` copies from chart index **1**. Index 0 — the forming bar — is never in
the array and no code path can put it there. `LastBarIsClosed=false` is passed to every
rung so the map also stops at `rates_total-2`. An early cross read off a forming bar is
the easiest way to fake good results and lose real money; both layers refuse.

The walk is **incremental**: only bars newer than the last one seen are processed, and
`carriedSign` / `crossDir` / `crossAge` / `crossSep` persist per rung between reads. So
`crossAge` is an exact **bar** count across gaps, missing bars and stalls — not a
division of timestamps. The first read of a rung walks up to 256 closed bars to
establish the carried sign and any cross inside that reach.

### The vote

| Condition | Vote | Grade |
|---|---|---|
| `crossAge` inside `InpDirCrossMaxAgeBars` | `crossDir` | `EARLY` or `FRESH` |
| `crossAge` older than the window, **or −1 (none seen yet)**, or ageing disabled | `carriedSign` | `STALE_STATE` |
| map warm-up (`EMPTY_VALUE` on the read bar), stale feed, or sign still 0 | NO_VOTE | — |

An **unknown age is treated as old**, not as absent: a rung that has not yet been seen
to cross still votes its carried sign, marked `STALE_STATE`, exactly like a cross that
has aged out. NO_VOTE is reserved for the three cases in the last row.

`InpDirCrossMaxAgeBars = 3` counts the **rung's own bars**: three seconds on S1, 135
seconds on S45. Early is fractal, like everything else here. `0` is the **pure-colour
baseline, for comparison only** — every vote becomes the carried sign and every grade
`STALE_STATE`, while the cross fields keep being logged. The build prints a
`XPDIR WARN` line at init when it is set, so nobody runs the baseline by accident.

### Grading

| Grade | Condition |
|---|---|
| `EARLY` | `crossAge == 0`, or inside the window with `abs(sepNow) ≤ abs(crossSep) × InpDirEarlySepMult` — the lines have barely separated, the move has not been paid out |
| `FRESH` | inside the window, separation already past the EARLY band |
| `STALE_STATE` | the vote is the carried sign, not a cross in the window |

`InpDirEarlySepMult = 2.0` is **EQUIVALENT-ASSUMED** and in the header line. Every
rung's grade and cross age is written to the CSV and printed on every `DIR_STATE` line
from this first build, with `c1_cross_sep` and `c1_sep_now` beside them, so the band can
be chosen from data instead of guessed twice.

Grades are three labels. Nothing multiplies them into a score. The only thing a grade
decides on its own is `InpDirRequireFreshS1`.

### `InpDirRequireFreshS1` — a condition on the rules, not a veto on the vote

Default **false** (`OWNER_TO_CONFIRM`). When true, **any rule that needs `C1 == X` also
needs S1's grade to be `EARLY` or `FRESH`**: that is R1, and R3 when
`InpDirS1RequiredAgainstParent` is on. **R2 is unaffected.** No other rung's grade is
enforced anywhere; all of them are logged.

A stale S1 is **not** deleted — it still counts toward R3's child total. Fixture
`fresh_s1_stale_still_counts_in_r3` pins that distinction, which is the difference
between this and the cruder "zero the vote" reading.

**Named consequence, implemented literally.** R2's own condition is `C1 != X`. So when
`RequireFreshS1` is on, P and a stale C1 both pointing at X with two supporting
children gives **NONE**: R1 is blocked by the freshness test, and R2 cannot take over
because `C1 != X` is false. Flip C1 to dissent and the same ladder returns X on R2.
That follows directly from "R2 unaffected", it is not an accident, and fixture
`fresh_s1_blocks_r1_and_r2_cannot_cover` holds it in place. If the owner wants R2 to
cover a stale-C1 R1, that is a one-word change to R2's condition — say so and it moves.

### FINDING — at the defaults, the cross changes nothing a colour ladder would not do

This has to be said plainly, because it decides whether the owner needs to change a
setting today.

`crossDir` is assigned the new sign at the moment of a cross, and `carriedSign` only
ever changes at a cross. So **`crossDir` and `carriedSign` are the same value whenever
`crossDir` is non-zero**, and when it is zero the cross branch cannot fire. The cross
branch and the state branch therefore **return the same sign, always**. Fixtures
`unknown_age_votes_state` and `ageing_off_all_stale` show the two branches side by side
producing the same votes.

Combined with answer 3 — unknown age votes state rather than NO_VOTE — the arithmetic
is: **at the shipped defaults, this ladder's direction output is identical to a
pure-colour ladder.** What the cross machinery adds at defaults is measurement: an age,
a separation and a grade on every rung, on every decision, in a file that sorts.

The one switch that makes the cross *decide* something today is
**`InpDirRequireFreshS1 = true`**, which is off by default because it is the owner's
call. Turn it on and a stale S1 stops carrying R1 and R3 — the ladder then trades only
when the one-second rung has actually crossed inside its window, which is the
"it crossed early and it's even better" case expressed as a rule. Any further weighting
belongs in §5 as rules, which is why no scoring formula was invented here.

### Why the carried sign is kept at all

It is the floor. Without it, a ladder in the middle of a long trend where nothing has
crossed recently goes blind and every rung falls to NO_VOTE. `STALE_STATE` keeps the
rung voting while making it obvious, in the log and the CSV, that the vote is the floor
and not a signal. The only path to `STALE_STATE` is the one where no cross sits inside
the window — reading state where a cross was available is not reachable from here.

---

## 2. The cut — what changed in the EA

The direction ladder replaces **seven** 1.03 lines; everything else it adds is
insertion. A second, separate change — `InpBurstThresholdFixed`, §2.4 below — replaces
another eight. The two are audited separately by the Gate 0 pre-check so neither hides
behind the other.

The ladder's seven:

```
-#property version   "1.03" // Added Money Management
-   if(isBuy) g_VirtualBuyStopPrice = 0.0;
-   if(g_EntryHoldCandidate.active &&
-   if(buyHoldActive || (!g_EntryHoldCandidate.active && buyCrossing))
-   // SELL TRIGGER
-   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
-   if(sellHoldActive || (!g_EntryHoldCandidate.active && sellCrossing))
```

Untouched by the ladder: every gate, the 3,000 ms hold, prior-60, the burst bundle,
friction, one-entry-per-bar, `CalculateLotSize`/`OrderCalcProfit`, the virtual SL,
the trailing geometry, `CContinuationTrade::OrderSend` (CP), `LA_*`, `XA_*`,
`ValidateAndLogBrokerProfile`, and the dashboard's existing geometry. **No existing
input is renamed, removed or re-defaulted** — the build has 53 inputs to 1.03's 36, and
every one of 1.03's is present with its original name and default. `MarkCurrentBarEntered`, ticket resolution,
`RegisterVirtualSL`, `LA_VirtualFill` and `LogEntryRisk` still run inside their own
side's block, on the side that actually executed.

### The exact diff (wiring)

The full machine diff is `reference/ea_1.03_to_1.05_xpdir.diff` (+1112 / −15). It
contains two further hunks that are pure insertions with no 1.03 line replaced: the
input group at 1.03:2170 (+27) and the XPDir module at 1.03:3759 (+1019, immediately
before `ManageVirtualPendings`). Everything else is below, verbatim.

```diff
@@ -9,7 +9,7 @@
 //+------------------------------------------------------------------+
 #property copyright "Senior MQL5 Engineer"
 #property link      "https://www.mql5.com"
-#property version   "1.03" // Added Money Management
+#property version   "1.05-XPDIR" // 1.03 + XPW Direction Ladder v1 (DIR_OFF = 1.03)
 #property strict
 
 #include <Trade\Trade.mqh>
@@ -2565,6 +2596,10 @@
    g_MasterVwapTerminalId = MasterVwapTerminalIdFromDataPath();
 
    if(!ValidateAndLogBrokerProfile())
+      return(INIT_FAILED);
+
+   // XPDIR: the direction ladder. DIR_OFF creates no handle and reads nothing.
+   if(!XPDir_Init())
       return(INIT_FAILED);
 
    // Set the Magic Number properly using the input we just defined
@@ -2613,6 +2648,7 @@
 //+------------------------------------------------------------------+
 void OnDeinit(const int reason)
 {
+   XPDir_Deinit();          // XPDIR: IndicatorRelease on every rung handle
    CP_Deinit();
    LA_FlushOpenPairs();
    XA_ReconcileHistory();
@@ -3584,7 +3620,14 @@
       return ENTRY_HOLD_PASS;
 
    g_LastEntryHoldFailureBar = signalBar;
-   if(isBuy) g_VirtualBuyStopPrice = 0.0;
+   if(InpDirMode == DIR_TRANSLATE)
+   {
+      // XPDIR: in TRANSLATE the level that crossed is not necessarily the exec
+      // side's level. Zero both, or the crossed level re-fires every tick.
+      g_VirtualBuyStopPrice  = 0.0;
+      g_VirtualSellStopPrice = 0.0;
+   }
+   else if(isBuy) g_VirtualBuyStopPrice = 0.0;
    else g_VirtualSellStopPrice = 0.0;
 
    { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=%s crossing=1 burst_speed_failed=0 burst_direction_failed=0 continuation_failed=0 friction_failed=0 one_entry_per_bar_failed=0 entry_hold_failed=1 prior60_failed=0 hold_move_points=%.1f prior60_drift_points=0.0",
@@ -3806,15 +4868,27 @@
       g_LastModTime = TimeCurrent();
    }
 
-   if(g_EntryHoldCandidate.active &&
+   // XPDIR (DIR_LOCK): the ladder disarms the side it does not want.
+   XPDir_ApplyArmingLock();
+
+   if(InpDirMode == DIR_TRANSLATE)
+      XPDir_ReviewHoldCandidate();
+   else if(g_EntryHoldCandidate.active &&
       ((g_EntryHoldCandidate.isBuy && g_VirtualBuyStopPrice <= 0.0) ||
        (!g_EntryHoldCandidate.isBuy && g_VirtualSellStopPrice <= 0.0)))
       ResetEntryHoldCandidate();
 
    // BUY TRIGGER
    const bool buyCrossing = (g_VirtualBuyStopPrice > 0 && ask >= g_VirtualBuyStopPrice);
+   // XPDIR: sellCrossing hoisted out of the SELL TRIGGER block so DIR_TRANSLATE
+   // sees both crossings before either side-specific block runs. In DIR_OFF and
+   // DIR_LOCK neither block writes g_VirtualSellStopPrice or bid, so this is the
+   // same value the SELL block computed in 1.03 (report: HOIST-1).
+   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
+   XPDir_NoteTrigger(buyCrossing, sellCrossing);
+
    const bool buyHoldActive = g_EntryHoldCandidate.active && g_EntryHoldCandidate.isBuy;
-   if(buyHoldActive || (!g_EntryHoldCandidate.active && buyCrossing))
+   if(XPDir_BuyBlockRuns(buyHoldActive, buyCrossing, sellCrossing))
    {
       const bool cheapGatesPassed = buyHoldActive ||
                                     EntryCandidateApproved(true, tickTimeMsc,
@@ -3854,6 +4928,8 @@
                {
                   MarkCurrentBarEntered();
                   g_VirtualBuyStopPrice = 0;
+                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
+                  XPDir_LogSent(true);
                   ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_BUY, trade.ResultOrder());
                   double virtualSL = bid - virtualSLDist;
                   if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
@@ -3878,10 +4954,9 @@
       }
    }
 
-   // SELL TRIGGER
-   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
+   // SELL TRIGGER  (sellCrossing is computed above, with buyCrossing)
    const bool sellHoldActive = g_EntryHoldCandidate.active && !g_EntryHoldCandidate.isBuy;
-   if(sellHoldActive || (!g_EntryHoldCandidate.active && sellCrossing))
+   if(XPDir_SellBlockRuns(sellHoldActive, buyCrossing, sellCrossing))
    {
       const bool cheapGatesPassed = sellHoldActive ||
                                     EntryCandidateApproved(false, tickTimeMsc,
@@ -3921,6 +4996,8 @@
                {
                   MarkCurrentBarEntered();
                   g_VirtualSellStopPrice = 0;
+                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
+                  XPDir_LogSent(false);
                   ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_SELL, trade.ResultOrder());
                   double virtualSL = ask + virtualSLDist;
                   if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
@@ -4424,6 +5501,26 @@
       ObjectDelete(0, "Lbl_Pos_0");
       ObjectDelete(0, "Lbl_PosSL_0"); 
    }
+
+   // XPDIR: one added line, last, so no existing dashboard line moves.
+   if(InpDirMode == DIR_OFF)
+      ObjectDelete(0, "Lbl_XPDir");
+   else
+   {
+      const ENUM_XPDIR d = XPDir_Current();
+      string dirTxt = StringFormat("DIR: %-4s %-2s P=%s/%s 1:%s/%s 5:%s/%s 10:%s/%s 15:%s 30:%s 45:%s",
+                                   XPDir_DirName(d),
+                                   g_XPDirCachedRule > 0 ? "R" + IntegerToString(g_XPDirCachedRule) : "- ",
+                                   XPDir_VoteTag(XPDIR_IDX_PARENT), XPDir_GradeLetter(g_XPDirGrade[XPDIR_IDX_PARENT]),
+                                   XPDir_VoteTag(0), XPDir_GradeLetter(g_XPDirGrade[0]),
+                                   XPDir_VoteTag(1), XPDir_GradeLetter(g_XPDirGrade[1]),
+                                   XPDir_VoteTag(2), XPDir_GradeLetter(g_XPDirGrade[2]),
+                                   XPDir_VoteTag(3), XPDir_VoteTag(4), XPDir_VoteTag(5));
+      color dirClr = (d == XPDIR_BUY) ? InpDashColor2
+                     : ((d == XPDIR_SELL) ? InpDashColor3 : clrGray);
+      CreateLabel("Lbl_XPDir", InpDashX, y, dirTxt, dirClr);
+      y += lineHeight;
+   }
 }
 
 void CreateLabel(string name, int x, int y, string text, color clr)
```

**The `InpBurstThresholdFixed` diff (§2.4), separately:**

```diff
@@ -2142,6 +2142,7 @@
    input int      InpBurstLookbackMs      = 1000;   // Burst midpoint displacement window (ms)
    input bool     InpUseBurstGate         = false;  // Burst bundle gate (magnitude/direction/continuation)
    input ENUM_BURST_THRESHOLD_MODE InpBurstThresholdMode = BURST_THRESHOLD_FIXED;
+   input double   InpBurstThresholdFixed  = 172.0;   // Fixed burst threshold (Points); used when mode = FIXED
    input double   InpBurstPercentile      = 99.0;   // Rolling absolute-burst percentile
    input int      InpBurstWindowSamples   = 2000;   // Prior observations; current sample excluded
@@ -2219,7 +2247,9 @@
 
 //--- Hard pre-entry signal gates and conflict-resolution limits
 #define BURST_BUFFER_CAPACITY 20000
-const double   BURST_MIN_POINTS            = 172.0;
+// BURST_MIN_POINTS retired: the fixed-mode threshold is now the input
+// InpBurstThresholdFixed, whose default is the 172.0 this constant held.
+// One number, one place to edit - a dead constant beside a live input is a trap.
 const int      CONTINUATION_TICKS          = 5;
 
 double         internalOrderDistance = 0.0;
@@ -2537,7 +2567,7 @@
 {
    if(InpBurstThresholdMode == BURST_THRESHOLD_FIXED)
    {
-      thresholdPoints = BURST_MIN_POINTS;
+      thresholdPoints = InpBurstThresholdFixed;
       sampleCount = g_BurstPercentileCount;
       return true;
    }
@@ -2552,12 +2582,13 @@
    if(!CP_Init()) return INIT_PARAMETERS_INCORRECT;
    if(InpBurstPercentile < 0.0 || InpBurstPercentile > 100.0 ||
       InpBurstWindowSamples < 2 || InpBurstLookbackMs <= 0 ||
-      InpEntryHoldMs < 0 || InpEntryHoldMinFavPoints < 0.0)
-   {
-      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT invalid gate settings burst_percentile=%.4f burst_window_samples=%d burst_lookback_ms=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f",
+      InpEntryHoldMs < 0 || InpEntryHoldMinFavPoints < 0.0 ||
+      InpBurstThresholdFixed <= 0.0)
+   {
+      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT invalid gate settings burst_percentile=%.4f burst_window_samples=%d burst_lookback_ms=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f burst_threshold_fixed_points=%.1f",
                   InpBurstPercentile, InpBurstWindowSamples,
                   InpBurstLookbackMs, InpEntryHoldMs,
-                  InpEntryHoldMinFavPoints);
+                  InpEntryHoldMinFavPoints, InpBurstThresholdFixed);
       return(INIT_PARAMETERS_INCORRECT);
    }
@@ -2592,7 +2627,7 @@
                PROVISIONAL_ROUND_TRIP_COST_POINTS,
                MAX_ENTRY_DISTANCE_POINTS,
                InpUseBurstGate ? 1 : 0,
-               BurstThresholdModeName(), BURST_MIN_POINTS,
+               BurstThresholdModeName(), InpBurstThresholdFixed,
                InpBurstPercentile, InpBurstWindowSamples,
                InpUseEntryHold ? 1 : 0, InpEntryHoldMs,
                InpEntryHoldMinFavPoints);
@@ -3479,7 +3515,7 @@
                BurstThresholdModeName(),
                burstAvailable ? 1 : 0, burstPoints,
                burstThresholdAvailable ? 1 : 0,
-               burstThresholdPoints, BURST_MIN_POINTS,
+               burstThresholdPoints, InpBurstThresholdFixed,
                InpBurstPercentile, burstThresholdSampleCount,
                InpBurstWindowSamples,
                burstSpeedPassed ? 1 : 0,
```

### DIR_LOCK

At the arming block the ladder decides which virtual stop stays armed: BUY ⇒
`g_VirtualSellStopPrice = 0`, SELL ⇒ `g_VirtualBuyStopPrice = 0`, NONE ⇒ both zero.
The trigger then only exists on the ladder's side, and `g_EntryHoldCandidate` stays
free for that side instead of being occupied for 3 s by a wrong-side candidate.

**DEVIATION-1 (deliberate).** §2.2 places this "at the arming block (3800–3804)",
which runs once every `InpModInterval` (15 s). `XPDir_ApplyArmingLock()` is instead
called on **every tick**, immediately after that block. If it ran only inside the
refresh, a direction change 1 s after a refresh would leave a live level armed on the
now-wrong side for up to 14 s, and that level can cross and fill. Enforcing per tick
is the only reading under which "the trigger only exists on the filter's side" is
true. In `DIR_OFF` and `DIR_TRANSLATE` the function returns at its first line.

### DIR_TRANSLATE

Both stops stay armed. `triggerFired = buyCrossing || sellCrossing`,
`triggerSideIsBuy = buyCrossing` (a simultaneous cross counts as BUY),
`execSideIsBuy = (XPDir_Current() == XPDIR_BUY)`. The native BUY block runs when
`triggerFired && exec == BUY`, the native SELL block when `triggerFired && exec ==
SELL`, neither when NONE. Neither block's body was edited: the hold gate measures the
favourable move in the exec direction, and the virtual SL registers on the exec side,
because it is that side's own code running.

The two consequences §2.2 names are handled explicitly:

**Virtual-stop reset targets the level that crossed.** After a fill
(`XPDir_ClearTriggerLevels()` at both fill sites) and after a hold-gate failure (the
edit inside `EvaluateEntryHoldGate`), TRANSLATE zeroes **both** levels. Otherwise the
crossed level stays crossed and re-fires on the next tick.

**The hold-candidate reset is re-derived.** 1.03 keys the reset on
`g_EntryHoldCandidate.isBuy` — the exec side — against that side's virtual stop. In
TRANSLATE the exec side's stop can be armed and uncrossed while the trigger came from
the other level, so that condition never fires and a stale candidate would sit in the
hold forever. `XPDir_ReviewHoldCandidate()` replaces it: the trigger side is recorded
in `g_XPDirHoldTriggerIsBuy` when the candidate is armed (updated only while no
candidate is active, so it survives the hold), and the candidate is dropped when that
**trigger** level is gone, or when the direction moves away from the exec side
mid-hold — the latter logged as `XPDIR HOLD_DROPPED reason=direction_changed`.

### HOIST-1 — `sellCrossing` moved above the BUY block

`const bool sellCrossing` was hoisted from the SELL TRIGGER block up beside
`buyCrossing`, because TRANSLATE must see both crossings before either side-specific
block runs. This is behaviour-identical in `DIR_OFF` and `DIR_LOCK`: its only inputs
are `g_VirtualSellStopPrice` and `bid`, and in those modes the BUY block writes
neither (it can zero `g_VirtualBuyStopPrice` on a fill or a hold failure, never the
sell level). Gate 0 is the receipt for that claim.

### The fade — stated plainly, not softened

**In DIR_TRANSLATE, an entry after an opposite-side crossing is a fade.** Price broke
*down* through the sell level, the ladder says *up*, and the EA buys. The hold gate
then requires a ≥5-point reclaim **in the buy direction** within 3,000 ms before the
order sends, measured from the midpoint at the moment of the crossing. That is the
only thing standing between a translated entry and buying into a live break lower. It
is a real fade with a 3-second confirmation window, not a continuation trade, and it
is what "the EA is good at triggering the position, not at the direction" turns into
when the trigger is kept and the side is taken away. Gate 3 exists to count how many
of these there are and what they do.

### 2.4 `InpBurstThresholdFixed` — the fixed burst threshold becomes editable

Requested 2026-09-22. **This one is a change to the EA proper, not to the ladder**, and
it is the only such change in the build. It is called out separately for that reason.

1.03 held the fixed-mode burst threshold in a compile-time constant:

```mql5
const double   BURST_MIN_POINTS            = 172.0;
```

It is now an input, sitting directly under the mode enum that selects it:

```mql5
input ENUM_BURST_THRESHOLD_MODE InpBurstThresholdMode = BURST_THRESHOLD_FIXED;
input double   InpBurstThresholdFixed  = 172.0;   // Fixed burst threshold (Points); used when mode = FIXED
```

and `BURST_THRESHOLD_FIXED` routes to it:

```mql5
   if(InpBurstThresholdMode == BURST_THRESHOLD_FIXED)
   {
      thresholdPoints = InpBurstThresholdFixed;
```

**`BURST_MIN_POINTS` is retired, not left behind.** A dead 172.0 sitting beside a live
input is how someone edits the wrong number and cannot work out why nothing changed. The
two log sites that printed the constant (`REPORT_HEADER` at init and `ENTRY_CANDIDATE`)
now print the input, so the log states the threshold actually in force rather than a
number that used to be.

**Same default behaviour, and that is checked rather than asserted.** The default is the
exact value the constant held, so at defaults the same number reaches the same
comparison by the same path. Gate 0's pre-check A7 reads the default out of the source
and fails the build if it is not 172.0 — a deliberately mis-set default was tried and
it caught it:

```
G0 PRE-CHECK FAIL (1)
  InpBurstThresholdFixed defaults to 150.0, but the retired BURST_MIN_POINTS held
  172.0 - the build no longer reproduces 1.03 at defaults
```

**One addition beyond what was asked, and why.** `OnInit` now rejects
`InpBurstThresholdFixed <= 0.0` alongside the gate settings it already validates. An
editable threshold of 0 would pass every magnitude test — `MathAbs(burstPoints) >= 0` is
always true — silently disabling the magnitude leg of the burst bundle while the log
still read `burst_gate_active=1`. A constant could not be set to 0 by accident; an input
can. The check follows the file's existing treatment of `InpEntryHoldMinFavPoints < 0.0`
and costs nothing at defaults. Say the word if you would rather it clamp than refuse.

**Note on the Inputs dialog.** The new input sits between `InpBurstThresholdMode` and
`InpBurstPercentile`, so those two move one row down in the dialog. Nothing depends on
input order here — the EA is not read through `iCustom`, and `.set` preset files key by
name — but the ladder's own group is still appended last, and no 1.03 input changed its
name or default.

**Scope note.** Both `InpUseBurstGate` (false) and `InpDirMode` (`DIR_OFF`) are off by
default, so at defaults this input changes the number in two log lines and nothing else.
With the burst gate switched on it is the live magnitude threshold.

### PHASE_3_PENDING_TYPES — not in this build

Pending order placement (buy/sell stop, buy/sell limit) is out. Every entry in 1.03 is
`trade.Buy` / `trade.Sell` at market; converting a market request to a broker pending
breaks the post-fill block wholesale — `trade.ResultOrder()` would be a pending ticket,
`ResolveOwnPositionTicket(POSITION_TYPE_BUY, ...)` would not resolve, `RegisterVirtualSL`
would register against nothing, and `LA_VirtualFill` would record a fill that has not
happened. That is a separate build with its own gates. Named and stopped here.

### Why not an `OrderSend`-level swap

`CContinuationTrade::OrderSend` (1.03:323) already intercepts every request and could
flip `request.type`. It must not. Items 5 of §1: the post-fill block is side-specific
and runs *after* the send returns. A BUY→SELL swap inside the send would leave the
BUY block registering `virtualSL = bid − dist` on a short position, and
`ManageOpenPositions` would then trail a sell against a stop placed below it. The
direction has to enter before the side-specific block runs, which is exactly where
`XPDir_BuyBlockRuns` / `XPDir_SellBlockRuns` sit.

---

## 3. The ladder

| Rung | Symbol | TF passed to `iCustom` | Presence |
|---|---|---|---|
| S1 | `_Symbol + "_S1"` | `PERIOD_M1` | Mandatory. `XPDIR_INIT_ABORT rung=S1 reason=symbol_missing` ⇒ `INIT_FAILED` |
| S5, S10, S15, S30, S45 | `_Symbol + "_S<n>"` | `PERIOD_M1` | Optional; enabled-but-absent ⇒ `XPDIR_RUNG_ABSENT`, continue without it |
| Parent | `_Symbol` | `InpDirParentTF` (default `PERIOD_M5`) | Mandatory |

Every symbol name derives from `_Symbol`. There is no literal `XAUUSD-ECNc` anywhere
in the build — grep it and you get nothing. `SymbolSelect(name, true)` precedes every
handle.

Per rung, per read (a window of closed bars ending at index 1 — see §1):

- **vote** — the cross, aged out: `crossDir` inside the window, the carried sign
  outside it or before the first observed cross. Graded `EARLY` / `FRESH` /
  `STALE_STATE`.
- **valid** — `EMPTY_VALUE` in FAST or SLOW on the read bar ⇒ NO_VOTE (the map's own
  warm-up). `EMPTY_VALUE` **deeper** in the window is skipped rather than treated as a
  sign, so a warm-up boundary can never manufacture a cross
  (fixture `warmup_empty_is_skipped_not_a_cross`).
- **stale** — `TimeCurrent() − iTime(sym, tf, 1) > InpDirMaxRungStaleBars × interval`
  ⇒ NO_VOTE. Interval: the rung's declared seconds for children,
  `PeriodSeconds(InpDirParentTF)` for the parent (the map does not expose its measured
  interval in a buffer).
- **sign zero** — a rung whose first valid bar was a tie and never resolved ⇒ NO_VOTE.
- **RUNLEN** — buffer 23 is read and logged. It is **never voted on**.
  `InpDirMaxRunLenBars` is gone from this build: the owner's "just at the beginning of
  the line" is carried by `InpDirCrossMaxAgeBars` and the `EARLY` grade, which measure
  the cross, and steering by the colour-run length is the thing §1 says not to do.

NO_VOTE is never counted as disagreement — it simply fails to be counted for either
direction.

**Tuning note on staleness.** The default `InpDirMaxRungStaleBars = 3` gives S1 a
3-second window. Under live gold flow index 1 is ~2 s old, so the margin is one
second. If Gate 2 shows S1 flapping to `NV` with `why=stale_4s`, raise the input; it
is not a code change. The funnel prints the measured age, so the host does not have to
guess.

**Warm-up.** RSI(14) + slow SMA(7) + extLook(20) ⇒ ~21 closed bars before a rung is
valid: S1 ≈ 30 s, S10 ≈ 4 min, S45 ≈ 16 min. No second warm-up counter was added — the
map's own valid flag is the warm-up. `XPDIR RUNG_READY` prints once, the first time a
rung votes, and carries the cross that made it vote.

**Scan width.** The first read of a rung walks up to 256 closed bars to establish its
carried sign and any cross in reach. After that only the bars newer than the last one
seen are walked (`newBars + 2`, floor 4, cap 256), and the cross state persists between
reads — so a stall cannot hide a cross and `crossAge` stays an exact bar count.

### Voting rules

| Rule | Condition |
|---|---|
| R1 aligned | `C1 == X and P == X` — and, when `InpDirRequireFreshS1`, C1 graded `EARLY`/`FRESH` |
| R2 parent carries | `P == X`, `C1 != X`, and ≥ `InpDirMinChildrenWithParent` (2) of the enabled optional children `== X`. **Freshness never applies here.** |
| R3 children overrule | `P != X` and ≥ `InpDirMinChildrenAgainstParent` (3) children `== X` counting S1 as a child; and if `InpDirS1RequiredAgainstParent` (true) then `C1 == X` too — with freshness on that leg when `InpDirRequireFreshS1` |

Direction = X if exactly one direction passes a rule. Both ⇒ NONE +
`XPDIR DIR_CONFLICT`. Neither ⇒ NONE. R1 and R2 are mutually exclusive by construction
(`C1 == X` vs `C1 != X`), R3 excludes both (`P != X`), so the reported rule is never
ambiguous.

**The owner's contradiction, as instructed.** "At least the first second has to be
agreed" versus "at least two together, five and ten, even though the one does not
agree". R2 encodes the second. `InpDirS1RequiredAgainstParent = true` encodes the first
**for the against-parent case only**. Both defaults are `OWNER_TO_CONFIRM`, in the
header line, and both are single inputs he can flip without a rebuild.

**AMBIGUITY-R3-P-NV (resolved literally).** R3 is written "P != X". A NO_VOTE parent
satisfies that, so with the parent silent, three agreeing children can still carry a
direction. The alternative reading — that R3 needs the parent to actively disagree —
would make a silent parent veto everything. The literal text is implemented; fixture
`r3_parent_novote_children_carry` pins it, and `parent_novote_only_s1` shows it does
not degenerate into "one rung decides".

**DEFECT in the prompt's §4 (found by Gate 1).** §4 says both directions passing is
"possible only with `InpDirS1RequiredAgainstParent=false`". That is false. With
`P=BUY, C1=SELL, C5=BUY, C10=BUY, C15=SELL, C30=SELL`: BUY passes R2 (parent plus two
children), and SELL passes R3 (S15+S30+C1 = 3 against the parent, with `C1 == SELL`
satisfying the requirement). Fixture `conflict_with_s1_required` is exactly that
ladder, and the build returns NONE + `DIR_CONFLICT`, which is what §4 prescribes for a
conflict. Only the parenthetical was wrong, not the rule.

**Caching.** Re-evaluated on every tick, cached by the S1 closed-bar time — and
additionally re-read once per server second, because staleness is the one thing §4
itself names as able to change between S1 bars. Without that, a dead S1 feed would
freeze the cached direction forever, since the cache key is that feed's own bar time.
Cost is up to seven `CopyBuffer(…, 1, 1, …)` calls per second.

`XPDIR DIR_STATE` prints only when the change key moves. That key holds the direction,
the rule, and every rung's vote **and grade** — but deliberately **not** the cross ages,
because an age ticks up every bar and would put a line in the log on every bar. The
printed line still carries the ages as of the moment of the change, which is the moment
worth reading. A grade decaying `EARLY → FRESH → STALE_STATE` is three lines per cross
per rung, bounded and meaningful. The Experts tab already carries the EA's per-tick
lines; nothing was added to that flood.

### `iCustom` parameter list — 30 inputs, positional, map declaration order

Identical for every rung. Logged at init as
`XPDIR RUNG_INIT rung=… symbol=… params=[…]`.

```
 1 rsiLen=14          11 sqBotCtx=2         21 atrLen=14
 2 fastLen=2          12 sqBotSep=0.0       22 dnWickFrac=0.55
 3 slowLen=7          13 sqBotArea=true     23 dnWickAtr=0.8
 4 invertFill=true    14 sqTopOn=false  *   24 upWickFrac=0.70
 5 extLook=20         15 sqTopMin=1         25 upWickAtr=1.2
 6 loFrac=0.33        16 sqTopMax=2         26 tickPrice=false *
 7 hiFrac=0.67        17 sqTopCtx=3         27 showTbl=false   *
 8 sqBotOn=false  *   18 sqTopSep=0.0       28 LastBarIsClosed=false *
 9 sqBotMin=1         19 sqTopArea=true     29 SkipEmptyBars=false   *
10 sqBotMax=3         20 tickOn=true        30 DumpCSV=false         *
```

`*` = the only values that are not simply the map's default. Note 28/29/30 are *also*
the map's defaults — the prompt names them as overrides and they are passed explicitly,
but they change nothing. The five that matter:

- **`tickPrice = false` is the one that is not cosmetic.** `DrawTickLabel` (line 572)
  computes `int win = tickPrice ? 0 : g_subwin`. Window 0 is the *calling EA's chart*.
  Every other drawing path in the map returns early on `g_subwin < 0`, which is what an
  `iCustom` instance has; this one does not. Left at its default, each rung would
  scribble tick labels on the chart the EA trades from.
- `sqBotOn`, `sqTopOn`, `showTbl = false` are belt-and-braces: their draw paths are
  already guarded by `g_subwin < 0`. Confirmed at lines 888/898 that these flags gate
  **drawing only** — `botCount`, `lastBot*` and every buffer are written before the
  `if(sqBotOn)`, so no buffer value changes.
- `tickOn` is deliberately left at `true`. It is the one "visual" flag that also
  changes buffers (`upTick = tickOn && …`, line 909, feeding `BufUpTick`/`BufDnTick`),
  and turning it off would be retuning a detector. With `tickPrice = false` its drawing
  is already dead.

No detector parameter is overridden. The ladder reads the map the owner validated.

---

## 4. New inputs

One group, appended after `--- Master Order-Flow Telemetry Only ---`. Nothing existing
moved.

```mql5
input group "--- XPW Direction Ladder ---"
input ENUM_XPDIR_MODE InpDirMode                    = DIR_OFF;
input string          InpDirMapIndicator            = "XPW_ShapeMap_v0.4";
input ENUM_TIMEFRAMES InpDirParentTF                = PERIOD_M5;
input bool            InpDirUseS5                   = true;
input bool            InpDirUseS10                  = true;
input bool            InpDirUseS15                  = false;
input bool            InpDirUseS30                  = false;
input bool            InpDirUseS45                  = false;
input int             InpDirMinChildrenWithParent   = 2;
input int             InpDirMinChildrenAgainstParent= 3;
input bool            InpDirS1RequiredAgainstParent = true;
input int             InpDirMaxRungStaleBars        = 3;
input bool            InpDirWriteCsv                = true;  // XPDir decision CSV
//--- the cross is the signal (owner's correction 2026-09-22)
input int             InpDirCrossMaxAgeBars         = 3;     // in that rung's OWN bars (0 = off)
input double          InpDirEarlySepMult            = 2.0;   // EARLY band
input bool            InpDirRequireFreshS1          = false; // S1 must vote a cross
```

The three cross inputs are appended at the **end** of the group, so no other input in
the group moves position. `InpDirMaxRunLenBars` is **removed** per the owner's answer 4:
RUNLEN is logged, never voted on.

Clamped in `OnInit` (one `XPDIR CLAMP` line when any clamp bites):
`MinChildrenWithParent ≥ 1`, `MinChildrenAgainstParent ≥ 2`, `MaxRungStaleBars ≥ 1`,
`CrossMaxAgeBars ≥ 0`, `EarlySepMult ≥ 0`. A separate `XPDIR WARN` line fires when
`CrossMaxAgeBars = 0`, because that is the pure-colour baseline and not a tuning.

**Dashboard** — one added line, written **last** in `UpdateDashboard()` so that no
existing label's Y coordinate moves:

```
DIR: BUY  R2 P=BUY/E 1:SELL/F 5:BUY/E 10:BUY/S 15:- 30:- 45:-
```

`-` = rung disabled or absent, `NV` = enabled but no vote. The letter after the slash
is the grade: `E` EARLY, `F` FRESH, `S` STALE_STATE. In `DIR_OFF` the label is deleted
rather than drawn.

**CSV** — `MQL5\Files\XPChart\FlashGold_Continuation_v2_XPDir_v1_<symbol>_<magic>.csv`,
header written once, appended with `FILE_SHARE_READ|FILE_SHARE_WRITE` (the
`MasterVwapDecision` idiom already in 1.03).

**DEVIATION-3.** §5 named a single fixed filename. It is per instance instead, and every
row carries `symbol` and `magic`, because two charts writing one file with no way to
tell the rows apart makes a second chart useless for exactly the comparison it is for
(`DIR_LOCK` against `DIR_TRANSLATE`, or `RequireFreshS1` off against on). The naming
follows `VirtualSLFileName()`, which 1.03 already keys by account + symbol + magic.
Gate 0's A9 checks the header and the row format cannot drift apart:

```
server_msc,event,mode,dir,rule,P,C1,C5,C10,C15,C30,C45,runlen1,trigger_side,exec_side,action,
P_g,C1_g,C5_g,C10_g,C15_g,C30_g,C45_g,c1_cross_dir,c1_cross_age,c1_cross_sep,c1_sep_now,c1_state
```

The §5 columns come first and in their original order, so anything already parsing this
file keeps working; the cross columns are appended. Each `*_g` cell is
`GRADE@crossAge`, e.g. `EARLY@0`, `FRESH@2`, `STALE_STATE@37`, `-`. **This is the file
that answers `InpDirEarlySepMult`** — sort by `c1_cross_sep` and `c1_sep_now` and the
"barely separated" band stops being a guess.

`event` ∈ `DIR_STATE | DECISION | HOLD_DROPPED`;
`action` ∈ `ARMED_BUY | ARMED_SELL | ARMED_NONE | SENT | BLOCKED_NONE | BLOCKED_CONFLICT`.
Blocked rows are rate-limited to one per server second per trigger, because a
still-crossed level re-fires on every tick and would otherwise write thousands of
identical rows a minute.

---

## 5. Standing clauses

**Broker-agnostic calibration.** The ladder adds no numeric constant tied to a broker.
Digits, point, tick size, stops level, contract size and volume min/max/step are still
read from the symbol by `ValidateAndLogBrokerProfile` and `CalculateLotSize`, untouched.
Custom symbol names derive from `_Symbol`. The only numbers the ladder introduces are
vote counts, a bar count and a bar age.

**Same defect, same lineage — BLOCKED_LINEAGE_SOURCES_ABSENT.** The sibling EAs named
in §6 (`FlashGold_v2_StackSL`, `FlashGoldVirtual`, `GM3`, `SAR`) are **not in this
repository and not in any inventory available in the box**. The branch carries only
`XPChart/` (5 chart-engine variants + axis check) and `XPMap/` (v0.4, v0.5); the only
host inventory present, `XPChart/census/2026-09-22/census_files.csv`, has 8 rows and
covers the chart engine alone. A repo-wide
`grep -rln "g_VirtualBuyStopPrice" --include=*.mq5 --include=*.mqh` returns exactly one
file: the new build. There is nothing to report and nothing was modified.

The host can produce the list in one command against the real tree:

```powershell
Get-ChildItem -Recurse -Include *.mq5,*.mqh $env:APPDATA\MetaQuotes\Terminal\*\MQL5 |
  Select-String -Pattern 'g_VirtualBuyStopPrice\s*=\s*ask\s*\+','g_VirtualSellStopPrice\s*=\s*bid\s*-' |
  Select-Object Path,LineNumber,Line
```

Every hit is a file where this hook lands, at the line the arming block sits on; the
matching trigger sites are the `ask >= g_VirtualBuyStopPrice` / `bid <=
g_VirtualSellStopPrice` pair below it. Attach those files and the list becomes a
finding rather than a blocker.

**Zero-result contingency — DEFECT FOUND AND FIXED 2026-09-22.** `XPDir_PrintFunnel()`
shipped in the first build **defined but never called**: this report described a
diagnostic the build could not produce. It is now driven by `XPDir_FunnelHeartbeat()`
on the EA's existing one-second timer — while the ladder has produced no `DIR_STATE`
line at all it dumps every 30 s starting immediately, then every 300 s while the
direction is stuck on `NONE`, stopping by itself once the ladder decides and capping at
30 dumps. Gate 0's pre-check A8 now fails the build if any `XPDir_*` function is defined
and never called, so a dead instrument cannot ship again. The funnel prints, per rung:
handle, enabled, bars available, the index-1 bar time, the vote, the grade, `crossDir`,
`crossAge`, `crossSep`, `sepNow`, `sign`, `ever_crossed`, the map's raw STATE, the run
length, and the exact reason (`disabled`, `handle_invalid`, `no_data`, `map_invalid`,
`no_bar_time`, `stale_<n>s`, `sign_zero`, `buffer_contract`, `state_no_cross_seen`,
`state_cross_aged_out`, `cross`).

A failing rung also now says what to do about it rather than only what went wrong: a
missing S1 symbol triggers `XPDir_DiagnoseSymbols`, which lists every `<parent>_S*`
symbol the terminal can actually see, and detects the commonest cause outright — an EA
attached to a `_S<n>` chart instead of the parent, which sends the ladder looking for
`XAUUSD-ECNc_S1_S1`. An `iCustom` failure prints where the indicator has to live.
`XPDirection/TROUBLESHOOTING.md` maps every one of these lines to its fix.
If a Gate 2 or Gate 3 run produces zero `DIR_STATE` lines after the longest enabled
rung's warm-up, or stays NONE for the whole run, that is a broken run: re-check symbol
names, `SymbolSelect`, handle validity, buffer index and closed-bar index **once**, then
call the funnel and report the still-blocked item as `BLOCKED_RUNG_HANDLE_INVALID`,
`BLOCKED_BUFFER_INDEX` or `BLOCKED_S1_NEVER_VALID`. A run where every rung shows
`why=state_no_cross_seen` is not a broken ladder — it is a ladder whose rungs have not
been seen to cross yet, still voting their carried signs, and the funnel says so in as
many words. `why=buffer_contract` means the probe above fired: that one is a real stop.

---

## 6. Gates

### Gate 0 — unchanged behaviour: `BLOCKED_NO_TESTER`, pre-check `PASS`

**The Strategy Tester run cannot happen here.** There is no MetaEditor and no terminal
in this box, and Gate 0 is a comparison of two real trade lists on real ticks. That run
is the host's, and it is the only thing that proves the gate. Shipped for it:

- `reference/gate0_tester_settings.ini` — XAUUSD-ECNc, M1, **Model=4 (every tick based
  on real ticks)**, a fixed 5-day window, everything else at build defaults. Run it
  twice, changing only `Expert=`.
- `reference/compare_trades.py` — parses both HTML tester reports, compares the Deals
  tables row by row (order, time, type, volume, price) and prints every difference.
  Exit 0 only on `G0 identical`. It fails the gate rather than passing it if the
  baseline has no deals, because an empty trade list proves nothing.

**What could be established here, was.** `reference/run_gate0_precheck.py` proves the
layer underneath the trade list: that with `InpDirMode = DIR_OFF` the build's entry
path *is* the 1.03 entry path, branch for branch.

```
$ cd XPDirection/reference && python3 run_gate0_precheck.py --base <1.03.mq5>
A. STATIC
  A1 removed 1.03 lines: 7 (all authorised)
  A2 DIR_OFF guards on injected entry points: 5 checked
  A3 XPDir_Init returns before any iCustom handle in DIR_OFF
  A4 hold-gate failure edit reduces to the 1.03 pair outside TRANSLATE
  A5 hoisted sellCrossing expression byte-identical to 1.03, computed once
  A6 dashboard DIR line deleted, not drawn, in DIR_OFF
  A7 InpBurstThresholdFixed = 172.0 (the retired constant), routed from FIXED,
     guarded at init, no dead BURST_MIN_POINTS
  A8 XPDir functions defined: 35, dead: 0; funnel heartbeat wired to OnTimer
  A9 XPDir CSV: 30 columns = 30 row fields, carries symbol+magic, one file per instance
B. EXECUTED
  gate0 entry-path: states=144 checks=606 failures=0
    DIR_OFF divergences from 1.03: 0 (must be 0)
    DIR_LOCK states exercised: 48   DIR_TRANSLATE states exercised: 48
    DIR_TRANSLATE fades observed (sell crossing -> buy executes): 2 (must be > 0)

G0 PRE-CHECK PASS - DIR_OFF is the 1.03 entry path.
```

**Part A** re-derives the diff against the 1.03 file (sha256 checked first) and refuses
any removed line outside the authorised set — kept as **two separate lists**, seven for
the direction ladder and eight for `InpBurstThresholdFixed` (§2.4), so one change cannot
hide behind the other. It then audits each injected entry point for its `DIR_OFF` guard
*as the function's first statement*, not merely somewhere in the body, and checks that
the new burst input still defaults to the value the retired constant held.

**Part B** lifts the entry-path wiring out of the `.mq5` between the
`XPDIR_GATE0_CORE` markers, compiles it with g++ against a stub layer that supplies the
globals, and runs **all 144 combinations** of mode × candidate state × candidate side ×
buy crossing × sell crossing × ladder direction. For every `DIR_OFF` state it asserts:

| Assertion | Why it matters |
|---|---|
| `XPDir_BuyBlockRuns` ≡ `buyHoldActive \|\| (!active && buyCrossing)` | the literal 1.03 condition |
| `XPDir_SellBlockRuns` ≡ `sellHoldActive \|\| (!active && sellCrossing)` | same, sell side |
| no virtual stop level is written | `ApplyArmingLock` / `ClearTriggerLevels` inert |
| the hold candidate is never reset | `ReviewHoldCandidate` inert |
| no CSV row is written | the observer is silent |
| **`XPDir_Current()` is never called** | in DIR_OFF the ladder is not merely ignored, it is not asked |

It also asserts the other two modes do what they claim, so a build that silently
no-ops `DIR_LOCK` or `DIR_TRANSLATE` fails here too — including that the fade path
really exists (a sell crossing executing a buy, 2 states).

**The pre-check was verified against a deliberately broken build.** Two mutations were
injected — `return buyCrossing` widened to `return buyCrossing || sellCrossing`, and the
`DIR_TRANSLATE` guard removed from `XPDir_ClearTriggerLevels` — and it caught both:

```
G0 PRE-CHECK FAIL (2)
  XPDir_ClearTriggerLevels first statement is 'g_XPDirLastArmed = g_XPDirLastArmed;',
    expected the guard 'if(InpDirMode != DIR_TRANSLATE) return;'
  the executed entry-path check reported failures
      -> DIR_OFF divergences from 1.03: 6, checks failed: 60
exit code 1
```

A check that cannot fail proves nothing, so that negative control is part of the record.

**What the pre-check does not prove.** It says nothing about `OnInit` ordering against
the broker profile, about `OnTimer`, about the observers' file handles, or about
anything downstream of the entry decision — lot sizing, the virtual SL, the trailing.
Those are identical by diff and by inspection, and the tester is what turns that into
evidence. **`G0 BLOCKED_NO_TESTER` stands until the host runs it.**

### Gate 1 — vote logic: `asserts=403 mismatches=0`

```
$ cd XPDirection/reference && python3 run_fixtures.py
extracted 167 lines of MQL5 rule core -> /tmp/xpdir_emu_*/core.cpp
stub lint: 0 errors 0 warnings
fixtures=49 asserts=833 mismatches=0 emu=on
```

Three independent sources must agree on all 49 fixtures, or the gate fails:

1. the hand-derived expectation written into `fixtures/vote_rules.csv`;
2. `reference/vote_ref.py`, a transliteration written from §4's text;
3. **the EA's own rule core, executed.** `reference/emu/extract_core.py` lifts
   everything between the `XPDIR_RULE_CORE_BEGIN` / `XPDIR_RULE_CORE_END` markers
   straight out of the `.mq5`, applies the same mechanical MQL5→C++ rewrite the Shape
   Map port uses (`const T &a[]` → `const Arr<T>&`, and nothing else), `g++
   -fsyntax-only -Wall -Wextra` lints it, then compiles and runs it against the
   fixtures. What g++ executes *is* the EA's source text for those functions, not a
   paraphrase — which is why the rule core was written as pure functions with no
   global read and no runtime call beyond `MathAbs` / `MathIsValidNumber`.

Fixtures cover, on the rule side: R1/R2/R3 each passing alone; R1 winning over an
also-satisfied R2; R2 at exactly the minimum and one child short; R2 with the minimum
raised to 3; R3 with and without `S1RequiredAgainstParent`; R3 one short; R3 with the
minimum raised to 4; both-directions conflict **with** `S1Required` true (the §4 defect
above) and with it false; every rung NO_VOTE; parent NO_VOTE; parent-only and S1-only
degenerate ladders; staleness at the boundary, one second over, on a child with a 5 s
interval, on the parent, and with the window raised.

On the cross side: `EARLY` at age 0 and by the separation band; `FRESH` past the band
and at the window edge; the band widened by the multiplier; `STALE_STATE` from a cross
past the window and from an age of −1; **the tie rules** — a touch that resumes the same
side is not a cross, a touch that flips stamps the cross on the bar carrying the new
non-zero sign, a tie on the read bar inherits and still votes, and a sign that never
resolves is NO_VOTE; **persisted cross state** ageing out and staying fresh across a
read; ageing disabled as the pure-colour baseline; `EMPTY_VALUE` on the read bar and
deeper in the window; and all five `InpDirRequireFreshS1` cases — R1 blocked with R2
unable to cover, R1 passing when fresh, R2 unaffected, R3's required leg blocked, and a
stale S1 still counting toward R3's child total.

### Gate 2 — wiring, host smoke, DIR_LOCK: pending

### Gate 3 — DIR_TRANSLATE smoke: pending

Both are host runs; instructions in §6.

---

## 7. Host instructions

**1. Engine services.** Start one `XP ChartEngine v2` service per enabled seconds
value. With the defaults that is **S1, S5 and S10** (S15/S30/S45 are off). Parent
symbol string for the F6 override — exactly as the axis-check receipt has it:

```
XAUUSD-ECNc
```

Custom symbols land at `Custom\XPChart\XAUUSD-ECNc_S1`, `…_S5`, `…_S10`. Confirm with
`XP_AxisCheck` on `XAUUSD-ECNc_S1` that the verdict is still `SECONDS_AXIS_REAL`
before attaching the EA — a stale axis means a lying ladder.

**2. Compile.**
- `XPW_ShapeMap_v0.4.mq5` → `MQL5\Indicators\XPW_ShapeMap_v0.4.mq5`. Use the file
  from `XPMap_ShapeMap_v0.4.zip` (sha256 `5653130d…b52120`, identical to the repository
  file at `579cb33`) — **not** the 37-line attachment from the original prompt, which
  has a different buffer map. `InpDirMapIndicator` resolves relative to
  `MQL5\Indicators`; if you put it in a subfolder, set the input to
  `Subfolder\\XPW_ShapeMap_v0.4`. The build's `BUF_CONTRACT` probe will tell you at
  runtime if the wrong one is installed.
- `FlashGold_Continuation_v2_XPDIR.mq5` → `MQL5\Experts\`.
- Both must show **0 errors, 0 warnings**. This build was written without MetaEditor;
  the rule core is the only part that has been compiled (by g++, Gate 1). **Report any
  compiler diagnostic verbatim rather than fixing it locally** — a silent local fix
  breaks the diff this report rests on.

**3. Gate 0 — first, before any live attach.** Two steps.

*3a, no terminal needed, ~5 seconds:* drop the 1.03 file next to the build and run the
pre-check, so a broken build is caught before you spend a tester run on it.

```
cd XPDirection/reference
python3 run_gate0_precheck.py --base /path/to/FlashGold_Continuation_v2.mq5
```

Expect `G0 PRE-CHECK PASS`. It needs only python3 and g++.

*3b, the gate itself:* `reference/gate0_tester_settings.ini`, two runs, then
`python3 compare_trades.py baseline_1.03.html candidate_1.05.html`. Expect
`G0 identical`. If it is not identical, stop: something other than the ladder moved,
and Gates 2 and 3 would be measuring the wrong program.

**4. Gate 2 — DIR_LOCK, 20 minutes.** Attach to `XAUUSD-ECNc` **M1** (the parent — the
EA trades `_Symbol`, and custom symbols do not trade). Inputs: `InpDirMode = DIR_LOCK`,
`InpDirWriteCsv = true`, everything else default.

Pass requires all of:
- every enabled rung logs `XPDIR RUNG_READY` (S1 ≈ 30 s, S5 ≈ 2 min, S10 ≈ 4 min);
- `XPDIR DIR_STATE` lines **change** over the run — a single line for 20 minutes is a
  frozen ladder, not a calm market;
- the dashboard's armed side matches `dir` (BUY ⇒ `V-SellStop: [Inactive]`, SELL ⇒
  `V-BuyStop: [Inactive]`, NONE ⇒ both inactive);
- no `ENTRY_CANDIDATE` line ever carries a side opposite to the current `dir`;
- every rung logs `XPDIR BUF_CONTRACT … verdict=OK` — a `BLOCKED_MAP_CONTRACT_MISMATCH`
  means the wrong build of the indicator is installed, and the run is void;
- the CSV contains rows graded `EARLY` **and** `FRESH` **and** `STALE_STATE`. If every
  row is `STALE_STATE`, either no rung crossed in 20 minutes (check `c1_cross_age`) or
  `InpDirCrossMaxAgeBars` was left at 0.

Then **detach and re-attach** mid-run: the armed side must be unchanged afterwards and
no handle may leak (`XPDIR DEINIT handles_released` prints on every detach;
`IndicatorRelease` runs on all seven slots).

**5. Gate 3 — DIR_TRANSLATE, 30 minutes, demo.** Same attach, `InpDirMode =
DIR_TRANSLATE`.

Pass requires all of:
- every `DECISION` row has `exec_side == dir`;
- rows with `trigger_side != exec_side` **exist** — if none do, the run did not test
  translation and proves nothing;
- each such row shows the hold gate evaluated in the **exec** direction (the
  `ENTRY_GATE_EVAL gate=ENTRY_HOLD side=…` line preceding it carries the exec side);
- no double-fire: no two `SENT` rows within `InpModInterval` (15 s) from the same
  trigger level.

**6. Answer `InpDirEarlySepMult` from the Gate 2/3 CSV, not from a guess.** Sort the
rows by `c1_cross_sep` and `c1_sep_now`. The ratio `abs(c1_sep_now) / abs(c1_cross_sep)`
at the moment you would call a cross "still early" is the number. 2.0 is a placeholder.

**7. If you want the cross to actually decide something, set
`InpDirRequireFreshS1 = true`.** See the FINDING in §1: at the shipped defaults the
ladder's direction output is identical to a pure-colour ladder, and this is the switch
that changes that. Run Gate 3 once with it off and once with it on, and compare the
`DECISION` rows.

Send back: the Experts log, the XPDir CSV, and the tester reports from Gate 0.

---

## 8. Out of scope, confirmed untouched

Pending order types (`PHASE_3_PENDING_TYPES`). Any change to the map — none was made,
and the things that looked like defects are written up in §0 as discrepancies between
the prompt and the file, not as changes. Any change to the EA's gates, hold, money
management, trailing, CP filter or observers — with the single, requested exception of
`InpBurstThresholdFixed` (§2.4), which promotes one compile-time constant in the burst
bundle to an input without changing its value. Multi-symbol. Retuning any of the
map's 27 inputs. Reading the parent through anything other than `iCustom` on `_Symbol`.

## DECISION: yes

The ladder is wired, the cross reader is built to the owner's six answers, the rule
logic is proved against the EA's own executed source, and the three remaining gates are
host runs with their settings and comparison scripts shipped. The map contract is in
hand and byte-verified, so no buffer index was guessed and the build checks the contract
again at runtime.

Polarity is settled: fast above slow is BUY, the cross is the moment, the fill is never
read. Three things are still open, and none of them blocks Gate 0:

1. **`InpDirEarlySepMult = 2.0`** — EQUIVALENT-ASSUMED. Answer it from the Gate 2/3 CSV
   (`c1_cross_sep` vs `c1_sep_now`), not from a guess.
2. **`InpDirRequireFreshS1 = false`** — and the FINDING in §1 that goes with it: at the
   shipped defaults this ladder's direction output is identical to a pure-colour
   ladder. This is the switch that makes the cross decide something.
3. **`InpDirS1RequiredAgainstParent = true`** — one half of the owner's two
   contradictory statements about S1.

And the standing caveat holds: **its direction is only as good as the map, and the
map's Gates B and C are still open.**
