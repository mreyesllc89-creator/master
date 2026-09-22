WIRED | G0 BLOCKED_NO_TESTER | G1 asserts=403 mismatches=0 | G2 pending | G3 pending | OWNER_TO_CONFIRM: S1RequiredAgainstParent=true, MaxRunLenBars=0, XPDIR_POLARITY | DECISION: yes

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

## 0. Three things found in the files that contradict the prompt

These are stated first because two of them change what the code does, and one of
them can invert every trade.

### DISCREPANCY-1 — the attached `XPW_ShapeMap_v0.4.mq5` is not the map

The file attached to the prompt is 37 lines with `#property indicator_buffers 26`
and a buffer map that places `STATE` at 20 and `RUNLEN` at 21. The map named as the
source of truth (`XPMap/XPW_ShapeMap_v0.4.mq5` @ `579cb33`) is 1,191 lines with
`indicator_buffers 25` and `STATE` at 22, `RUNLEN` at 23. They are different
programs — the attachment is a sketch, not the indicator.

§0 of the prompt makes the repository file the source of truth and §3.2 says to take
buffer indices "from the file, never from this prompt". **This build reads buffer 1
(FAST), 2 (SLOW), 22 (STATE) and 23 (RUNLEN) per the repository file.** Had the
attachment been believed, every rung would have read `VEL2` as the state and `MBARS`
as the run length, and the ladder would have voted on noise.

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

### OWNER_TO_CONFIRM: XPDIR_POLARITY — "green" is the map's RED fill

§3.2 defines the bullish vote as **"GREEN (fast above slow on the closed bar) → BUY"**.
In the map, with its default `invertFill = true`:

```mql5
bool stUp     = (fastOk && slowOk) ? (fast > slow) : false;   // line 813
bool isRedNow = invertFill ? stUp : !stUp;                    // line 814
BufState[i]   = isRedNow ? 1.0 : 0.0;                         // line 1008
```

`fast > slow` — the bullish TDI state — renders **RED** on the panel, and the LIME
fill is `fast < slow`. So the owner's spoken "the beginning of the green line" and the
prompt's written "GREEN (fast above slow)" cannot both be the same thing.

This build implements the prompt's operational definition: **`fast > slow` votes BUY**,
because that is the bullish TDI reading and it is what §3.2 states in parentheses. If
the owner meant the panel's LIME fill, every trade this ladder produces is backwards.
The one-line change if he says LIME: in `XPDir_RungVote`, swap the two returns.

`XPDir_RungVote` is the only place polarity is decided, and Gate 1 covers it.

### Why `STATE` is logged but never voted on

`BufState` is not usable as either a vote or a validity flag:

- it is `isRedNow`, so `invertFill` flips its meaning;
- `stUp` is forced `false` when `!fastOk || !slowOk`, so `STATE == 0` means *either*
  "fast ≤ slow" *or* "the bar is invalid" — indistinguishable.

`BufFast`/`BufSlow` carry the map's own valid flag (`BufFast[i] = fastOk ? fast :
EMPTY_VALUE`, line 973). The vote is read from those, and `STATE` is carried into the
logs for cross-check. This is what §3.2's "use it if the map exposes a state buffer"
becomes once the file is read rather than described.

---

## 1. The cut — what changed in the EA

Seven 1.03 lines were replaced. Everything else is insertion.

```
-#property version   "1.03" // Added Money Management
-   if(isBuy) g_VirtualBuyStopPrice = 0.0;
-   if(g_EntryHoldCandidate.active &&
-   if(buyHoldActive || (!g_EntryHoldCandidate.active && buyCrossing))
-   // SELL TRIGGER
-   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
-   if(sellHoldActive || (!g_EntryHoldCandidate.active && sellCrossing))
```

Untouched, as required: every gate, the 3,000 ms hold, prior-60, the burst bundle,
friction, one-entry-per-bar, `CalculateLotSize`/`OrderCalcProfit`, the virtual SL,
the trailing geometry, `CContinuationTrade::OrderSend` (CP), `LA_*`, `XA_*`,
`ValidateAndLogBrokerProfile`, and the dashboard's existing geometry. No existing
input was renamed, moved or re-defaulted. `MarkCurrentBarEntered`, ticket resolution,
`RegisterVirtualSL`, `LA_VirtualFill` and `LogEntryRisk` still run inside their own
side's block, on the side that actually executed.

### The exact diff (wiring)

The full machine diff is `reference/ea_1.03_to_1.05_xpdir.diff` (+765 / −7). It
contains two further hunks that are pure insertions with no 1.03 line replaced: the
input group at 1.03:2170 (+23) and the XPDir module at 1.03:3759 (+690, immediately
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
@@ -2565,6 +2588,10 @@
    g_MasterVwapTerminalId = MasterVwapTerminalIdFromDataPath();
 
    if(!ValidateAndLogBrokerProfile())
+      return(INIT_FAILED);
+
+   // XPDIR: the direction ladder. DIR_OFF creates no handle and reads nothing.
+   if(!XPDir_Init())
       return(INIT_FAILED);
 
    // Set the Magic Number properly using the input we just defined
@@ -2613,6 +2640,7 @@
 //+------------------------------------------------------------------+
 void OnDeinit(const int reason)
 {
+   XPDir_Deinit();          // XPDIR: IndicatorRelease on every rung handle
    CP_Deinit();
    LA_FlushOpenPairs();
    XA_ReconcileHistory();
@@ -3584,7 +3612,14 @@
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
@@ -3806,15 +4531,27 @@
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
@@ -3854,6 +4591,8 @@
                {
                   MarkCurrentBarEntered();
                   g_VirtualBuyStopPrice = 0;
+                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
+                  XPDir_LogSent(true);
                   ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_BUY, trade.ResultOrder());
                   double virtualSL = bid - virtualSLDist;
                   if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
@@ -3878,10 +4617,9 @@
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
@@ -3921,6 +4659,8 @@
                {
                   MarkCurrentBarEntered();
                   g_VirtualSellStopPrice = 0;
+                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
+                  XPDir_LogSent(false);
                   ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_SELL, trade.ResultOrder());
                   double virtualSL = ask + virtualSLDist;
                   if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
@@ -4424,6 +5164,24 @@
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
+      string dirTxt = StringFormat("DIR: %-4s %-2s P=%s 1:%s 5:%s 10:%s 15:%s 30:%s 45:%s",
+                                   XPDir_DirName(d),
+                                   g_XPDirCachedRule > 0 ? "R" + IntegerToString(g_XPDirCachedRule) : "- ",
+                                   XPDir_VoteTag(XPDIR_IDX_PARENT),
+                                   XPDir_VoteTag(0), XPDir_VoteTag(1), XPDir_VoteTag(2),
+                                   XPDir_VoteTag(3), XPDir_VoteTag(4), XPDir_VoteTag(5));
+      color dirClr = (d == XPDIR_BUY) ? InpDashColor2
+                     : ((d == XPDIR_SELL) ? InpDashColor3 : clrGray);
+      CreateLabel("Lbl_XPDir", InpDashX, y, dirTxt, dirClr);
+      y += lineHeight;
+   }
 }
 
 void CreateLabel(string name, int x, int y, string text, color clr)
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

## 2. The ladder

| Rung | Symbol | TF passed to `iCustom` | Presence |
|---|---|---|---|
| S1 | `_Symbol + "_S1"` | `PERIOD_M1` | Mandatory. `XPDIR_INIT_ABORT rung=S1 reason=symbol_missing` ⇒ `INIT_FAILED` |
| S5, S10, S15, S30, S45 | `_Symbol + "_S<n>"` | `PERIOD_M1` | Optional; enabled-but-absent ⇒ `XPDIR_RUNG_ABSENT`, continue without it |
| Parent | `_Symbol` | `InpDirParentTF` (default `PERIOD_M5`) | Mandatory |

Every symbol name derives from `_Symbol`. There is no literal `XAUUSD-ECNc` anywhere
in the build — grep it and you get nothing. `SymbolSelect(name, true)` precedes every
handle.

Per rung, per read (last closed bar, index 1):

- **vote** — `fast > slow` ⇒ BUY, `fast < slow` ⇒ SELL, equality ⇒ NO_VOTE.
- **runlen** — buffer 23, bars since the last colour flip (1 on the flip bar).
- **valid** — `EMPTY_VALUE` in FAST or SLOW is the map's own flag ⇒ NO_VOTE.
- **stale** — `TimeCurrent() − iTime(sym, tf, 1) > InpDirMaxRungStaleBars × interval`
  ⇒ NO_VOTE. Interval: the rung's declared seconds for children,
  `PeriodSeconds(InpDirParentTF)` for the parent (the map does not expose its measured
  interval in a buffer).
- **fresh** — `InpDirMaxRunLenBars > 0 && runlen > InpDirMaxRunLenBars` ⇒ NO_VOTE.
  Default 0 (off): the owner's "just at the beginning of the green line" is
  EQUIVALENT-ASSUMED until he names a number.

NO_VOTE is never counted as disagreement — it simply fails to be counted for either
direction.

**Tuning note on staleness.** The default `InpDirMaxRungStaleBars = 3` gives S1 a
3-second window. Under live gold flow index 1 is ~2 s old, so the margin is one
second. If Gate 2 shows S1 flapping to `NV` with `why=stale_4s`, raise the input; it
is not a code change. The funnel prints the measured age, so the host does not have to
guess.

**Warm-up.** RSI(14) + slow SMA(7) + extLook(20) ⇒ ~21 closed bars before a rung is
valid: S1 ≈ 30 s, S10 ≈ 4 min, S45 ≈ 16 min. No second warm-up counter was added — the
map's own valid flag is the warm-up. `XPDIR RUNG_READY rung=… bars=…` prints once, the
first time a rung votes.

### Voting rules

| Rule | Condition |
|---|---|
| R1 aligned | `C1 == X and P == X` |
| R2 parent carries | `P == X`, `C1 != X`, and ≥ `InpDirMinChildrenWithParent` (2) of the enabled optional children `== X` |
| R3 children overrule | `P != X` and ≥ `InpDirMinChildrenAgainstParent` (3) children `== X` counting S1 as a child; and if `InpDirS1RequiredAgainstParent` (true) then `C1 == X` too |

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

`XPDIR DIR_STATE` prints only when the state line or the rule changes. The Experts tab
already carries the EA's per-tick lines; nothing was added to that flood.

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

## 3. New inputs

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
input int             InpDirMaxRunLenBars           = 0;     // 0 = off
input int             InpDirMaxRungStaleBars        = 3;
input bool            InpDirWriteCsv                = true;  // XPDir decision CSV
```

Clamped in `OnInit` (one `XPDIR CLAMP` line when any clamp bites):
`MinChildrenWithParent ≥ 1`, `MinChildrenAgainstParent ≥ 2`, `MaxRungStaleBars ≥ 1`.

**Dashboard** — one added line, written **last** in `UpdateDashboard()` so that no
existing label's Y coordinate moves:

```
DIR: BUY  R2 P=BUY 1:SELL 5:BUY 10:BUY 15:- 30:- 45:-
```

`-` = rung disabled or absent, `NV` = enabled but no vote. In `DIR_OFF` the label is
deleted rather than drawn.

**CSV** — `MQL5\Files\XPChart\FlashGold_Continuation_v2_XPDir_v1.csv`, header written
once, appended with `FILE_SHARE_READ|FILE_SHARE_WRITE` (the `MasterVwapDecision`
idiom already in 1.03):

```
server_msc,event,mode,dir,rule,P,C1,C5,C10,C15,C30,C45,runlen1,trigger_side,exec_side,action
```

`event` ∈ `DIR_STATE | DECISION | HOLD_DROPPED`;
`action` ∈ `ARMED_BUY | ARMED_SELL | ARMED_NONE | SENT | BLOCKED_NONE | BLOCKED_CONFLICT`.
Blocked rows are rate-limited to one per server second per trigger, because a
still-crossed level re-fires on every tick and would otherwise write thousands of
identical rows a minute.

---

## 4. Standing clauses

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

**Zero-result contingency.** `XPDir_PrintFunnel()` is built in and prints, per rung:
handle, enabled, bars available, the index-1 bar time, the raw STATE, the run length,
the vote and the exact NO_VOTE reason (`disabled`, `handle_invalid`, `no_data`,
`map_invalid`, `no_bar_time`, `stale_<n>s`, `runlen_capped`, `fast_eq_slow`, `ok`).
If a Gate 2 or Gate 3 run produces zero `DIR_STATE` lines after the longest enabled
rung's warm-up, or stays NONE for the whole run, that is a broken run: re-check symbol
names, `SymbolSelect`, handle validity, buffer index and closed-bar index **once**, then
call the funnel and report the still-blocked item as `BLOCKED_RUNG_HANDLE_INVALID`,
`BLOCKED_BUFFER_INDEX` or `BLOCKED_S1_NEVER_VALID`.

---

## 5. Gates

### Gate 0 — unchanged behaviour: `BLOCKED_NO_TESTER`

No MetaEditor and no terminal in the box, so the run belongs to the host. Shipped:

- `reference/gate0_tester_settings.ini` — XAUUSD-ECNc, M1, **Model=4 (every tick based
  on real ticks)**, a fixed 5-day window, everything else at build defaults. Run it
  twice, changing only `Expert=`.
- `reference/compare_trades.py` — parses both HTML tester reports, compares the Deals
  tables row by row (order, time, type, volume, price) and prints every difference.
  Exit 0 only on `G0 identical`. It fails the gate rather than passing it if the
  baseline has no deals, because an empty trade list proves nothing.

`InpDirMode` defaults to `DIR_OFF`, and in `DIR_OFF` `XPDir_Init()` creates no handle,
`XPDir_Current()` returns at its first line, `ApplyArmingLock` / `NoteTrigger` /
`ClearTriggerLevels` / `LogSent` all return at theirs, and
`XPDir_Buy/SellBlockRuns` reduce to the 1.03 condition exactly:

| `g_EntryHoldCandidate.active` | 1.03 `buyHoldActive \|\| (!active && buyCrossing)` | `XPDir_BuyBlockRuns` in DIR_OFF |
|---|---|---|
| true, buy candidate | `true` | `buyHoldActive` = `true` |
| true, sell candidate | `false` | `buyHoldActive` = `false` |
| false | `buyCrossing` | `buyCrossing` |

**This gate is what proves nothing of the EA got modified. Until the host runs it, that
claim rests on the diff alone.**

### Gate 1 — vote logic: `asserts=403 mismatches=0`

```
$ cd XPDirection/reference && python3 run_fixtures.py
extracted 72 lines of MQL5 rule core -> /tmp/xpdir_emu_*/core.cpp
stub lint: 0 errors 0 warnings
fixtures=31 asserts=403 mismatches=0 emu=on
```

Three independent sources must agree on all 31 fixtures, or the gate fails:

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

Fixtures cover: R1/R2/R3 each passing alone; R1 winning over an also-satisfied R2; R2
at exactly the minimum and one child short; R2 with the minimum raised to 3; R3 with
and without `S1RequiredAgainstParent`; R3 one short; R3 with the minimum raised to 4;
both-directions conflict **with** `S1Required` true (the §4 defect above) and with it
false; every rung NO_VOTE; parent NO_VOTE; parent-only and S1-only degenerate ladders;
`fast == slow`; `EMPTY_VALUE` in FAST and in SLOW; staleness at the boundary, one
second over, on a child with a 5 s interval, on the parent, and with the window raised;
the freshness cap off, on, at its boundary, and dropping only some rungs.

### Gate 2 — wiring, host smoke, DIR_LOCK: pending

### Gate 3 — DIR_TRANSLATE smoke: pending

Both are host runs; instructions in §6.

---

## 6. Host instructions

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
- `XPW_ShapeMap_v0.4.mq5` → `MQL5\Indicators\XPW_ShapeMap_v0.4.mq5` (the 1,191-line
  file from `XPMap/`, **not** the 37-line attachment). `InpDirMapIndicator` resolves
  relative to `MQL5\Indicators`; if you put it in a subfolder, set the input to
  `Subfolder\\XPW_ShapeMap_v0.4`.
- `FlashGold_Continuation_v2_XPDIR.mq5` → `MQL5\Experts\`.
- Both must show **0 errors, 0 warnings**. This build was written without MetaEditor;
  the rule core is the only part that has been compiled (by g++, Gate 1). **Report any
  compiler diagnostic verbatim rather than fixing it locally** — a silent local fix
  breaks the diff this report rests on.

**3. Gate 0 — first, before any live attach.** `reference/gate0_tester_settings.ini`,
two runs, then `python3 compare_trades.py baseline_1.03.html candidate_1.05.html`.
Expect `G0 identical`. If it is not identical, stop: something other than the ladder
moved, and Gates 2 and 3 would be measuring the wrong program.

**4. Gate 2 — DIR_LOCK, 20 minutes.** Attach to `XAUUSD-ECNc` **M1** (the parent — the
EA trades `_Symbol`, and custom symbols do not trade). Inputs: `InpDirMode = DIR_LOCK`,
`InpDirWriteCsv = true`, everything else default.

Pass requires all of:
- every enabled rung logs `XPDIR RUNG_READY` (S1 ≈ 30 s, S5 ≈ 2 min, S10 ≈ 4 min);
- `XPDIR DIR_STATE` lines **change** over the run — a single line for 20 minutes is a
  frozen ladder, not a calm market;
- the dashboard's armed side matches `dir` (BUY ⇒ `V-SellStop: [Inactive]`, SELL ⇒
  `V-BuyStop: [Inactive]`, NONE ⇒ both inactive);
- no `ENTRY_CANDIDATE` line ever carries a side opposite to the current `dir`.

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

Send back: the Experts log, the XPDir CSV, and the tester reports from Gate 0.

---

## 7. Out of scope, confirmed untouched

Pending order types (`PHASE_3_PENDING_TYPES`). Any change to the map — none was made,
and the two things that looked like defects are written up in §0 as discrepancies
between the prompt and the file, not as changes. Any change to the EA's gates, hold,
money management, trailing, CP filter or observers. Multi-symbol. Retuning any of the
map's 27 inputs. Reading the parent through anything other than `iCustom` on `_Symbol`.

## DECISION: yes

The ladder is wired, the rule logic is proved against the EA's own executed source, and
the three remaining gates are host runs with their settings and comparison scripts
shipped. Two answers are needed before this trades money: the polarity question
(`XPDIR_POLARITY`) and the two `OWNER_TO_CONFIRM` defaults. And the standing caveat
holds — **its direction is only as good as the map, and the map's Gates B and C are
still open.**
