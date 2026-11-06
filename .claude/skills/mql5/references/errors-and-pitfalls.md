# Errors, retcodes and pitfalls

## Trade server return codes (`MqlTradeResult.retcode`, `trade.ResultRetcode()`)
| Code | Name | Meaning / fix |
|------|------|---------------|
| 10008 | TRADE_RETCODE_PLACED | Pending order placed (success) |
| 10009 | TRADE_RETCODE_DONE | Request completed (success) |
| 10004 | REQUOTE | Price moved; refresh prices and retry a few times |
| 10006 | REJECT | Rejected by dealer; check symbol trade mode and session |
| 10013 | INVALID | Malformed request: wrong action/type combo, missing position ticket |
| 10014 | INVALID_VOLUME | Volume not on step or outside min/max |
| 10015 | INVALID_PRICE | Price not normalised, or wrong side for a stop/limit |
| 10016 | INVALID_STOPS | SL/TP/pending too close (stops level) or on the wrong side |
| 10017 | TRADE_DISABLED | Trading disabled for the symbol/account |
| 10018 | MARKET_CLOSED | Outside session |
| 10019 | NO_MONEY | Insufficient margin; reduce volume (`OrderCalcMargin`) |
| 10020 | PRICE_CHANGED | Refresh and retry |
| 10021 | PRICE_OFF | No quotes |
| 10024 | TOO_MANY_REQUESTS | Back off |
| 10025 | NO_CHANGES | Modify with identical values; skip the call |
| 10026/10027 | SERVER_DISABLES_AT / CLIENT_DISABLES_AT | AutoTrading off on server/terminal (the toolbar button) |
| 10029 | FROZEN | Within freeze level; wait |
| 10030 | INVALID_FILL | Wrong `type_filling`; use `SetTypeFillingBySymbol` or read `SYMBOL_FILLING_MODE` |
| 10031 | CONNECTION | No connection |
| 10038 | INVALID_CLOSE_VOLUME | Partial close volume exceeds position |
| 10044 | CLOSE_ORDER_EXIST / 10045 LIMIT_POSITIONS | Broker limits |

Log the request alongside: `PrintFormat("send %s vol=%.2f price=%.5f sl=%.5f tp=%.5f -> %d %s", EnumToString(type), vol, price, sl, tp, trade.ResultRetcode(), trade.ResultRetcodeDescription());`

## Runtime errors (`GetLastError()`, call `ResetLastError()` first)
`4301 ERR_MARKET_UNKNOWN_SYMBOL`, `4302 ERR_MARKET_NOT_SELECTED`, `4401 ERR_HISTORY_NOT_FOUND`,
`4806 ERR_INDICATOR_DATA_NOT_FOUND` (CopyBuffer too early), `4807 ERR_INDICATOR_WRONG_HANDLE`,
`5004 ERR_CANNOT_OPEN_FILE`, `4756 ERR_TRADE_SEND_FAILED`, `4753 ERR_TRADE_POSITION_NOT_FOUND`,
`4754 ERR_TRADE_ORDER_NOT_FOUND`. Array out of range (`4002`) aborts the EA with a critical
error: always check `CopyBuffer` counts and `ArraySize` before indexing.

## Compile-time traps
- Handler signatures: `void OnDeinit(const int reason)`, `OnCalculate` with `const`
  and `&[]`. A wrong signature compiles as an unused function and the handler never runs.
- Arrays must be passed by reference: `void f(double &a[])`; constant arrays `const double &a[]`.
- Enum/int conversions warn or error: cast explicitly `(ENUM_TIMEFRAMES)value`,
  `(int)PositionGetInteger(...)`, `(datetime)OrderGetInteger(...)`.
- `string` literals in double quotes; `'A'` is a `ushort` char. Concatenate with `+` and
  convert numbers with `DoubleToString`/`IntegerToString` or `StringFormat`.
- No implicit `bool` from `double`; write `if(x != 0)`.
- Switch cases need constants; strings cannot be `switch`ed.
- Structures with dynamic arrays or strings cannot be used in `ArrayCopy` of structs or
  as `union` members; keep structs POD when passing to `FileWriteStruct`.
- Global `input` variables cannot be assigned; copy to a global if you need to adjust.
- `#include <Trade\Trade.mqh>` uses backslashes; `#include "x.mqh"` relative.
- `#property strict` is MQL4; harmless in MQL5. `#property indicator_buffers` must count
  all buffers, `indicator_plots` only drawn ones.

## Runtime traps
- Creating indicator handles in `OnTick`; forgetting `IndicatorRelease`.
- Reading bar `0` as if closed: bar 0 is forming and repaints; use bar 1 for signals.
- Comparing doubles with `==`; use `MathAbs(a - b) < _Point / 2` or compare rounded values.
- Not normalising volume to `SYMBOL_VOLUME_STEP` (10014) or price to tick size (10015).
- Modifying SL on every tick with the same value (10025 spam); check for a real change.
- Assuming hedging: on a netting account `PositionsTotal()` is at most one per symbol.
- `TimeCurrent()` is server time; the chart, Pine labels in `America/New_York`, and your
  Python data may each be in a different zone. Convert once at the boundary.
- In the tester the first `CopyBuffer` can return -1; return from `OnTick` and wait, do
  not `INIT_FAILED`.
- Slow tester: `Print` per tick, objects drawn in non-visual mode, `CopyRates` of thousands
  of bars per tick, or `iCustom` of a heavy indicator. Cache per bar.
- `OrderSend` in `OnInit` or `OnDeinit` is refused; trade in `OnTick`/`OnTimer`.
- `Sleep()` does nothing in the tester and freezes the EA live; use timers.

## MQL4 → MQL5 differences (for users coming from MT4)
- No `OrderSend(Symbol(), OP_BUY, ...)` with `OrderSelect` loops over mixed orders and
  positions. MQL5 separates **orders** (pending), **positions** (open), **deals**
  (history), accessed with `OrderGetTicket/PositionGetTicket/HistoryDealGetTicket`.
- `iMA(...)` returns a handle, not a value; values come from `CopyBuffer`.
- Series arrays are not series by default: call `ArraySetAsSeries`.
- `Bid/Ask` globals do not exist: `SymbolInfoDouble(_Symbol, SYMBOL_BID)`.
- `Point/Digits` → `_Point/_Digits`. `Time[]`, `Close[]` predefined arrays → `iTime`, `iClose`, `CopyRates`.
- `start()/init()/deinit()` → `OnTick()/OnInit()/OnDeinit()`.
- Netting accounts exist; MQL4 was hedging-only.
- `StringConcatenate` → `StringFormat` or `+`. `datetime` arithmetic is in seconds in both.
