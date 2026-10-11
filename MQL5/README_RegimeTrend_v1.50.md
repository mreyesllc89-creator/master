# RegimeTrend_EA v1.50 — what changed

The indicator (`Indicators/Foundry/RegimeTrend.mq5`, v1.03) and the money
management include are untouched. The EA gained three input groups. **Every
new input defaults to 0 / false / "original", so a v1.49 `.set` file runs
exactly as before.**

## Entry improvements

| Input | Meaning |
|---|---|
| `InpMaxSpreadPoints` | Skip an entry when the current spread is wider than N points (0 = off). |
| `InpMinErEntry` | Require the Efficiency Ratio of the signal bar to be at least this value (0 = off). |
| `InpEntryPrevState` | Only take transitions that come from Neutral (1) or from Choppy (2). 0 = any. |
| `InpLateEntryBars` | Besides the transition bar, allow an entry during the first N bars of a Trending leg if the EA has not traded that leg yet (e.g. the macro filter blocked the first bar and then agreed). 0 = off. |
| `InpReentryAfterStop` | With late entry on: also allow one re-entry into the same leg after a stop-out / take-profit, while the leg is still younger than N bars. |
| `InpSlAtrMult` | Initial stop at entry ∓ N × ATR instead of the SuperTrend line (0 = SuperTrend stop). The stop floor (`InpMinStopAtr`, `InpMinStopPoints`) still applies. |
| `InpMaxStopAtr` | Cap the SuperTrend stop distance at N × ATR so one far-away SuperTrend line does not shrink the position to dust (0 = off). |

## Exit improvements

| Input | Meaning |
|---|---|
| `InpExitOnStFlip` | Close when the raw SuperTrend direction (indicator buffer 12) flips against the trade, without waiting for the state machine's dwell lock. |
| `InpErExit` | Close when the Efficiency Ratio drops below this level (0 = off). Acts earlier than the state machine's `InpExitTrend` because it ignores the dwell lock. |
| `InpMaxBarsInTrade` | Time stop: close after N chart bars (0 = off). |
| `InpCloseFridayHour` | Close any open trade on Friday from this GMT hour on (0 = off). Uses the same GMT clock as the session filter. |

The order of evaluation on a new bar is unchanged: money-manager stop
management first, then the original regime/direction exit, then the new
exits in the order of the table above.

## Trailing improvements

| Input | Meaning |
|---|---|
| `InpTrailSource` | Where the trailing-stop candidate comes from: SuperTrend (original), a second tighter SuperTrend (`InpTrailAtrMult`), Chandelier (highest high / lowest low since entry ∓ K × ATR), or last close ∓ K × ATR. `InpTrailSuperTrend` is still the master switch and `InpTrailStepPoints` the minimum step. |
| `InpTrailAtrMult` | ATR multiplier of the tight SuperTrend (source 1). Loaded as a second instance of the embedded indicator. |
| `InpTrailAtrK` | K for the Chandelier / ATR-close sources. |
| `InpTrailActivateR` | Only start trailing once open profit reaches N × initial risk (0 = at once). |
| `InpLockTriggerR` / `InpLockR` | Lock-in stage: when profit reaches `trigger` R, move the stop to entry + `lock` R (lock must be < trigger). |
| `InpPartialR` / `InpPartialPercent` | Close this % of the original volume once profit reaches N × R. |

All stop moves still go through `CXPMoneyManager::Manage()`, which never
loosens a stop and respects the broker's stops/freeze levels.

## Calibration

See `calibration/README.md` for the backtest replica, the sweep results on
XAUUSD and the recommended `.set` files.
