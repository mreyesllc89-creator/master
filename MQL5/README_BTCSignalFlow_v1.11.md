# BTCSignalFlow_Test_EA v1.11 — what changed

`BTCMethodSignals.mqh`, the indicator and the money-management include are
untouched. The EA gained one input group; **every new input defaults to the
v1.10 behaviour**, so the shipped `BTCSignalFlow_Test_EA_Default.set` runs
exactly as before.

| Input | Meaning |
|---|---|
| `InpUseSignalExit` | `true` = v1.10 exit on the method's opposite state (trend / macro / mean). `false` = exits only by stop, trailing stop, take-profit, time stop or ER exit. |
| `InpTrailSource` | `BTC_TRAIL_ATR_CLOSE` (v1.10: last close ∓ TrailATR × ATR) or `BTC_TRAIL_CHANDELIER` (highest high / lowest low since entry ∓ TrailATR × ATR). |
| `InpTrailActivateR` | Trailing starts only once open profit reaches N × initial risk (0 = at once). |
| `InpUseBreakEven` / `InpBreakEvenR` | Move the stop to the entry price after N × R. |
| `InpLockTriggerR` / `InpLockR` | Lock-in stage: at `trigger` R move the stop to entry + `lock` R (lock < trigger). |
| `InpPartialR` / `InpPartialPercent` | Close this % of the original volume at N × R. |
| `InpErExit` | Close when the 20-bar efficiency ratio of the signal timeframe drops below this value (0 = off). |
| `InpTradeDirection` | Both / long only / short only. |

All stop moves still go through `CXPMoneyManager::Manage()` (never loosens,
minimum step 50 points, broker stop levels respected). Calibration results:
`calibration/BTC_REPORT.md`.
