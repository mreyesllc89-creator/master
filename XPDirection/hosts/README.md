# The direction veto in three EAs

Same filter, same include, three hosts. In every one of them the EA keeps its own
trigger **and** its own direction; the ladder only ever **removes** a trade.

| EA | Filtered build | How it was hooked | Lines changed |
|---|---|---|---|
| `FlashGold_Continuation_v2` 1.03 | `XPDirection/FlashGold_Continuation_v2_XPDIR.mq5` | full integration — `DIR_OFF`, `DIR_VETO`, `DIR_LOCK`, `DIR_TRANSLATE` | +1437 / −15 |
| `SpeedAlert … BurstSettle` 1.498 | `hosts/speedalert/build/v1_498/…_XPDIR.mq5` | `DIR_VETO` via a `CContinuationTrade` subclass | **+40 / −4** |
| `SpeedAlert … BurstSettle` 1.500 | `hosts/speedalert/build/v1_500/…_XPDIR.mq5` | same | **+40 / −4** |

The two SpeedAlert versions are the same EA, so they took the same four edits from the
same script: `hosts/speedalert/apply_xpdir.py`.

## Naming

Each filtered build carries the `_XPDIR` suffix, and MT5 takes an EA's name from its
file name — so `SpeedAlert_ExitGate68_Continuation_BurstSettle_XPDIR.ex5` appears in the
Navigator beside the original, never replacing it. `#property version` gains `-XPDIR`
(`1.500` → `1.500-XPDIR`) and the description says so, so a screenshot of the Inputs tab
tells you which one is loaded.

**The originals are not modified.** Keep them compiled and attachable: they are the
control arm, and without one the filter cannot be measured.

## Every `.mqh` in the SpeedAlert package is byte-identical

The veto is applied by subclassing `CContinuationTrade` **in the main `.mq5`**, not by
editing `SpeedAlertContinuationFilter.mqh`. So the package's own audited `.mqh` files —
the continuation filter, the candle gate, the speed trailing, the capture identity —
are untouched, and this patch survives their next version of any of them.

## Why one hook is enough

Every **entry** in SpeedAlert goes through `CContinuationTrade::OrderSend`, which its own
header already says "covers Buy/Sell, pending entries and recovery entries".

The two raw `OrderSend()` calls that bypass `CTrade` were checked, and both are
**closes**: the auto-close path in the main `.mq5` and `CFRClose` in
`ContinuationExecution.mqh`. Both set `request.position`, so `XPDir_IsEntryRequest`
would pass them through even if they were routed via the veto. Nothing that closes a
position can be blocked.

## Re-running the patch on a newer SpeedAlert

```bash
python3 XPDirection/hosts/speedalert/apply_xpdir.py <package>/source --out <somewhere>
```

It refuses to guess. Each of its four anchors must appear **exactly once**; if a future
version moves one, the script stops and says which, rather than patching the wrong
place. Fix the anchor deliberately and re-run.

## Installing a SpeedAlert build

1. `XPW_DirectionLadder.mqh` → the same `source/` folder as the EA (the patcher copies
   it next to the output), **or** `MQL5\Include\`.
2. `SpeedAlert_ExitGate68_Continuation_BurstSettle_XPDIR.mq5` → into the package's
   `source/` folder beside the original and its `.mqh` files.
3. `XPW_ShapeMap_v0.4.mq5` → `MQL5\Indicators\`, compiled.
4. Engine services running — `TROUBLESHOOTING.md` §4c.
5. Compile. **0 errors, 0 warnings expected; report any diagnostic verbatim** rather
   than fixing it locally, because a silent local fix breaks the audit the ladder rests
   on.

## First run

`InpDirMode` defaults to **`DIR_OFF`**, in which the ladder creates no indicator handle
and `XPDir_AllowsRequest` returns true for everything — the EA behaves exactly as it
does today. That is deliberate: it is the control.

Set `InpDirMode = DIR_VETO` and `InpDirWriteCsv = true` to switch the filter on. Rows
with `action = BLOCKED_DISAGREE` are the trades it removed; `BLOCKED_NONE` are the ones
it removed for having no opinion (`InpDirOnNone`).

**Mind the magic.** The CP log from 2026-09-22 shows `FlashGold_v2_StackSL` running magic
`26090555` on XAUUSD-ECNc — the same magic `FlashGold_Continuation_v2` defaults to.
SpeedAlert defaults to `26090568`. Two EAs sharing a magic on one symbol claim each
other's positions. Give every instance its own before any of them trades.

## A note on the XPDir inputs' position in the dialog

The ladder's include sits near the top of the main `.mq5`, because the veto subclass is
declared there and needs it. So the `--- XPW Direction Ladder ---` group appears at the
**top** of the Inputs tab, above SpeedAlert's own. That is cosmetic only: `.set` preset
files key by input name, not position, and nothing reads these EAs through `iCustom`.
