# Expert Advisor structure

## Files and folders
Terminal data folder (`File > Open Data Folder`, usually
`%APPDATA%\MetaQuotes\Terminal\<id>\MQL5\`): `Experts\`, `Indicators\`, `Scripts\`,
`Services\`, `Include\` (`.mqh`), `Libraries\`, `Files\` (sandbox for FileOpen),
`Logs\`. Compiled `.ex5` sits beside the source. `#include <Trade\Trade.mqh>` resolves in
`MQL5\Include`; `#include "my.mqh"` is relative to the source file.

## Properties and inputs
```mql5
#property copyright "..."
#property version   "1.00"
#property description "FlashGold v5 port"
#property strict
```
- `input` variables are shown in the EA dialog and the tester; `sinput` excludes from
  optimisation; `input group "Title"` groups the following inputs (MT5 build 2000+).
- Enums with comments become dropdowns: `enum ENUM_DIR { DIR_BOTH, // Both
  DIR_LONG, // Long only  DIR_SHORT // Short only };`
- Inputs are constants at runtime; copy to a working variable if you need to adjust
  (e.g. snap volume to the step).
- Use `//` comments right of each input: that text is the label in the dialog.

## Event handlers
| Handler | When | Notes |
|---------|------|-------|
| `int OnInit()` | load, input change, chart period change | Create handles, validate inputs, `EventSetTimer`. Return `INIT_SUCCEEDED`, `INIT_FAILED`, or `INIT_PARAMETERS_INCORRECT` (stops the tester pass). |
| `void OnDeinit(const int reason)` | unload | `IndicatorRelease`, `EventKillTimer`, `Comment("")`. `reason` is `REASON_PARAMETERS`, `REASON_CHARTCHANGE`, ... |
| `void OnTick()` | each tick of the chart symbol | The trading loop. Nothing else arrives while it runs. |
| `void OnTimer()` | after `EventSetTimer(seconds)` / `EventSetMillisecondTimer` | Work independent of ticks (multi-symbol EAs, weekend logic). Not called in the tester before the first tick. |
| `void OnTrade()` | after any trade event | Cheap notification; query `PositionsTotal()` etc. |
| `void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)` | every transaction step | Detect fills: `trans.type == TRADE_TRANSACTION_DEAL_ADD` then `HistoryDealSelect(trans.deal)` and read `DEAL_ENTRY`, `DEAL_MAGIC`, `DEAL_POSITION_ID`. |
| `double OnTester()` | end of a tester pass | Custom optimisation criterion. |
| `void OnTesterInit/OnTesterPass/OnTesterDeinit()` | optimisation frames | Collect `FrameAdd` results. |
| `void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)` | keys, clicks, custom events | Buttons/panels. |

Handler signatures must match exactly (including `const` and `&`) or the handler is
silently ignored or fails to compile.

## New-bar detection
```mql5
bool IsNewBar()
{
   static datetime last = 0;
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == last) return false;
   last = t;
   return true;
}
```
Trade logic on the first tick of a new bar reads bar `1` (just closed). For Pine
`process_orders_on_close` semantics there is no equivalent "fill at close" in live
trading; filling at the open of the next bar is the honest version.

## Multi-timeframe and multi-symbol
- Any `iXXX(symbol, timeframe, ...)` handle can read another symbol/timeframe; data for a
  symbol not on any chart may need a moment to load (`CopyBuffer` returns -1, try next tick).
- For HTF values without lookahead use index `1` of the HTF handle (the last closed HTF
  bar) — the MQL5 twin of Pine `request.security(..., lookahead_on)[1]`.
- Multi-symbol EAs run from one chart with `OnTimer` and `SymbolInfoTick(sym, tick)`; the
  tester generates ticks for all symbols used if "every tick" modelling is chosen.

## State and persistence
- `static` locals or globals for per-run state. The EA restarts on recompile/terminal
  restart: rebuild state from open positions/orders (`PositionGetInteger(POSITION_TIME)`,
  comments, magic) instead of trusting memory.
- `GlobalVariableSet("EA_lastSignalBar", t)` for values that must survive a restart
  (terminal global variables, 4 weeks lifetime, `double` only).
- Files: `FileOpen("ea_state.csv", FILE_WRITE|FILE_CSV|FILE_ANSI)` writes under
  `MQL5\Files` (or `FILE_COMMON` for the shared folder). In the tester the sandbox is
  `Tester\...\Files`.

## Output
- `Print()`/`PrintFormat()` to the Experts tab (and tester journal). Keep tick-level
  printing behind a `InpDebug` input; printing on every tick slows the tester 10x.
- `Comment()` for a chart overlay, `Alert()` for a popup, `SendNotification()` to the
  mobile app (needs MetaQuotes ID), `SendMail()`.

## Minimal EA
See `assets/EA_Template.mq5` for the full version. The shape:
```mql5
#include <Trade\Trade.mqh>
CTrade trade; int hAtr = INVALID_HANDLE;
int OnInit() {
   trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);
   hAtr = iATR(_Symbol, _Period, 14);
   return hAtr == INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { IndicatorRelease(hAtr); }
void OnTick() {
   if(!IsNewBar()) return;
   ManageOpenPositions();
   int sig = Signal();           // +1 / -1 / 0 from closed bars
   if(sig != 0) PlaceEntry(sig);
}
```
