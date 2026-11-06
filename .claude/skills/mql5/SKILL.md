---
name: mql5
description: MQL5 / MetaTrader 5 development reference - Expert Advisors (OnInit/OnTick/OnTimer/OnTradeTransaction), CTrade and position/order management, pending stop orders, SL/TP/trailing/partial close, lot sizing with tick value and volume step, indicator handles and CopyBuffer, multi-timeframe data, custom indicators (OnCalculate, buffers, plots), Scripts and Services, input groups, Strategy Tester and optimisation, retcodes and error handling, MetaEditor command-line compile. Use this for ANY .mq5 / .mqh file, any MetaTrader 5 EA, indicator, script or library, when porting a TradingView Pine strategy or Python backtest to MT5, when a user mentions MetaEditor, Strategy Tester, "EA", "expert advisor", "robot", "forex bot", lot size, or trade retcodes, and even for MQL4 questions (explain the MQL5 way and the differences).
---

# MQL5 (MetaTrader 5)

MQL5 is a C++-like compiled language that runs inside the MetaTrader 5 terminal. Three
program kinds matter here: **Expert Advisors** (trade on ticks/timer), **Indicators**
(compute buffers drawn on a chart), **Scripts/Services** (run once / run in background).
The strategies in this repo are TradingView Pine strategies (FlashGold v5, XPW Orientation
TDI); porting them is the usual reason MQL5 comes up, so the `strategy-porting` skill has
the Pine → MQL5 mapping and this skill has the MQL5 facts.

| Need | Read |
|------|------|
| EA skeleton, event handlers, new-bar logic, inputs, magic numbers | `references/ea-structure.md` |
| CTrade, market/pending orders, modify, partial close, trailing, lot sizing, netting vs hedging | `references/trade-operations.md` |
| iRSI/iMA/iATR handles, CopyBuffer, CopyRates, MTF data, series arrays | `references/indicators-and-data.md` |
| Writing a custom indicator (buffers, plots, OnCalculate, iCustom) | `references/custom-indicators.md` |
| Strategy Tester, optimisation, OnTester, tester inputs, command-line runs | `references/strategy-tester.md` |
| Retcodes, GetLastError, common compile and runtime pitfalls, MQL4 differences | `references/errors-and-pitfalls.md` |
| Ready EA template (stop entries, ATR/points SL-TP, trailing, partial+runner, time stop) | `assets/EA_Template.mq5` |

## Working rules

1. **Start from the template** in `assets/` for a new EA; it already handles the things
   that are easy to get wrong (new-bar detection, handle validation, stops-level checks,
   volume normalisation, hedging/netting, retcode logging). Rename, change inputs, fill
   in the signal function.
2. **Compile before you claim it works.** With MetaEditor available:
   `metaeditor64.exe /compile:"C:\...\MQL5\Experts\MyEA.mq5" /log` then read the `.log`
   (UTF-16). Without MetaEditor (Linux container), say so plainly; still review the code
   against the references for the common compile errors listed in
   `errors-and-pitfalls.md` (missing `const` on handler params, implicit enum casts,
   `string` vs `char` quotes, array passing by reference, missing `#include`).
3. **Indicator handles are created once in `OnInit`** and read with `CopyBuffer` in
   `OnTick`. Creating handles in `OnTick` leaks and slows the tester to a crawl.
4. **Compute signals on closed bars** (`index 1`) on a new-bar event unless the strategy
   is explicitly tick-based. This matches Pine's bar-close evaluation and keeps backtests
   reproducible in "Open prices only" mode.
5. **Normalise every price and volume** before sending: `NormalizeDouble(price, _Digits)`
   (or round to `SYMBOL_TRADE_TICK_SIZE`), volume to `SYMBOL_VOLUME_STEP` within
   min/max, and respect `SYMBOL_TRADE_STOPS_LEVEL` and `SYMBOL_TRADE_FREEZE_LEVEL`.
6. **Filter by magic number and symbol** in every loop over positions/orders; the account
   may hold other EAs' trades.
7. **Check the retcode** of every trade request, log `trade.ResultRetcodeDescription()`
   and the request values, and never retry blindly in a tight loop (requotes: a few
   retries with fresh prices; invalid stops: fix the distance, do not retry).
8. **Account type matters.** Hedging accounts allow many positions per symbol
   (`PositionGetTicket(i)` loop); netting accounts have one net position per symbol and
   an opposite deal reduces it. Read `ACCOUNT_MARGIN_MODE` and branch where it matters.

## Quick syntax reminders

```mql5
// (no "#property strict" needed: MQL5 is always strict; that property is MQL4)
input group "S1. Entries"
input int    InpEntryValidBars = 3;         // Cancel unfilled entry after N bars
sinput string InpNote = "";                 // sinput = not optimisable
enum ENUM_EXIT_MODE { EXIT_PIPS, EXIT_ATR, EXIT_POINTS };
input ENUM_EXIT_MODE InpExitMode = EXIT_ATR;

int OnInit() { ...; return INIT_SUCCEEDED; }
void OnDeinit(const int reason) { IndicatorRelease(hAtr); }
void OnTick() { if(!IsNewBar()) return; ... }
double OnTester() { return TesterStatistics(STAT_PROFIT); }
```

- Arrays passed to functions are by reference and need `&`: `void f(double &a[])`.
- `ArraySetAsSeries(buf, true)` makes index 0 the newest bar (like Pine `[0]`).
- Strings use double quotes; `char` uses single quotes. `StringFormat("%.5f", x)`.
- No exceptions: functions return `bool`/`int`, errors via `GetLastError()`.
- Integer division truncates; `(double)a / b` for ratios. `MathPow`, `MathAbs`, `MathMax`.
- `datetime` is seconds since 1970; `TimeCurrent()` is server time, `iTime(sym, tf, i)`
  is the bar open time.
