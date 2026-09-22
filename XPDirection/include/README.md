# Putting the direction filter in another EA

The ladder is a **direction oracle**. It reads the Shape Map on S1/S5/S10/S15/S30/S45
and one parent timeframe, decides BUY, SELL or NONE, and answers one question. It
touches no order, no position, no stop and no chart object belonging to the host EA.

For a new EA the mode you want is **`DIR_VETO`**: the EA keeps its own trigger **and**
its own direction, and the ladder only blocks trades it disagrees with.

## Files

| File | What it is |
|---|---|
| `XPW_DirectionLadder.mqh` | The ladder. **Generated** from the audited EA — do not edit it; edit `FlashGold_Continuation_v2_XPDIR.mq5` and regenerate (`reference/emu/make_include.py`). The Gate 0 pre-check fails if the two disagree. |
| `XPW_DirectionVeto.mqh` | Optional. A `CTrade` subclass that applies the veto at `OrderSend`. Only for EAs that trade through `CTrade`. |

Both go in `MQL5\Include\`. `XPW_ShapeMap_v0.4.mq5` still goes in `MQL5\Indicators\` and
still needs its engine services running — the ladder reads the same custom symbols
whatever EA hosts it.

## Integration — four calls

### If your EA uses `CTrade`

```mql5
#include <XPW_DirectionVeto.mqh>

CXPDirTrade trade;               // was: CTrade trade;

int OnInit()
{
   if(!XPDir_Init(InpMagic)) return INIT_FAILED;
   EventSetTimer(1);
   ...
}
void OnDeinit(const int reason) { XPDir_Deinit(); ... }
void OnTimer()                  { XPDir_FunnelHeartbeat(); ... }
```

That is all. Every `trade.Buy()`, `trade.Sell()`, `trade.PositionOpen()` and pending
placement now passes through the filter; every close, modify and SL/TP change does not.

### If your EA calls `OrderSend()` directly

```mql5
#include <XPW_DirectionLadder.mqh>

// at the point you have decided a side, before sending:
if(!XPDir_Allows(isBuy))
   return;                       // the ladder disagrees; your EA does nothing
```

or, if you have a filled `MqlTradeRequest` in hand:

```mql5
if(!XPDir_AllowsRequest(request))
   return;                       // same test, and it ignores non-entries for you
```

## The API

| Call | Returns | Notes |
|---|---|---|
| `XPDir_Init(hostMagic)` | `bool` | `false` means abort `OnInit`. Pass your EA's own magic; it is used only to name the CSV and take the duplicate-instance claim. In `DIR_OFF` it creates no indicator handle. |
| `XPDir_Deinit()` | — | `IndicatorRelease` on every rung, releases the instance claim. |
| `XPDir_Current()` | `ENUM_XPDIR` | `XPDIR_BUY` / `XPDIR_SELL` / `XPDIR_NONE`. Cached per S1 closed bar, re-read once a second. |
| `XPDir_Allows(isBuy)` | `bool` | The veto. `true` in `DIR_OFF`. On `XPDIR_NONE` it follows `InpDirOnNone`. |
| `XPDir_AllowsRequest(request)` | `bool` | `XPDir_Allows` plus the entry test; returns `true` for anything that is not an entry. |
| `XPDir_FunnelHeartbeat()` | — | Call from `OnTimer`. Explains in the log why the ladder is silent, and stops on its own once it decides. |
| `XPDir_PrintFunnel()` | — | Force one funnel dump now. |

## Modes

| `InpDirMode` | What the host keeps | What the ladder does |
|---|---|---|
| `DIR_OFF` | everything | nothing — no handle, no read, `XPDir_Allows` always `true` |
| `DIR_VETO` | trigger **and** side | blocks entries it disagrees with. **This is the one for a foreign EA.** |
| `DIR_LOCK` | trigger | disarms one of two virtual stop levels — only meaningful for an EA built that way |
| `DIR_TRANSLATE` | trigger only | picks the side that executes — same, and it needs the host's post-fill code to be side-correct |

`DIR_LOCK` and `DIR_TRANSLATE` are FlashGold's wiring and are **not** in this include.
A new EA uses `DIR_VETO`.

`InpDirOnNone` decides what happens when the ladder has no opinion. Default
`XPDIR_NONE_BLOCK`, because a filter that passes everything when it cannot decide is
not a filter. Set `XPDIR_NONE_ALLOW` if you would rather trade unfiltered than not
trade.

## Why a veto and not a side swap

Refusing a send creates no position and no state, so there is nothing to get wrong.
Swapping BUY for SELL inside `OrderSend` would return a filled order on the opposite
side to the one the caller asked for, and the caller's own post-fill code — ticket
resolution, stop registration, logging — would then be operating on a position that is
the wrong way round. That is why this is a filter and not a reverser.

## What the veto will never block

- `TRADE_ACTION_SLTP`, `TRADE_ACTION_MODIFY`, `TRADE_ACTION_REMOVE`
- anything with `request.position` or `request.position_by` set — every close, partial
  close and close-by
- on a **netting** account, any order that reduces or closes an open position, including
  a deliberate reversal

Blocking a close would strand a live position with no stop management. That is worse
than any entry the filter might have prevented, so the entry test errs toward allowing.

## Before you rely on it

1. Start the engine services and confirm one custom symbol per enabled rung —
   `TROUBLESHOOTING.md` §4c.
2. Run with `InpDirMode = DIR_VETO` and `InpDirWriteCsv = true` and read the CSV. Rows
   with `action = BLOCKED_DISAGREE` are the trades the filter removed; `BLOCKED_NONE`
   are the ones it removed for having no opinion.
3. Compare against the same EA with `InpDirMode = DIR_OFF` over the same window. That
   difference is the filter's entire contribution, and it is the only honest measure of
   whether it helps.
4. The standing caveat still applies: **the ladder is only as good as the map, and the
   map's Gate B and Gate C are still open.**
