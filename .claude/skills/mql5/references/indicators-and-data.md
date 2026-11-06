# Indicators and market data in an EA

## Handles
```mql5
int hRsi  = iRSI(_Symbol, PERIOD_CURRENT, 14, PRICE_CLOSE);
int hFast = iMA(_Symbol, PERIOD_CURRENT, 2, 0, MODE_SMA, hRsi);   // MA *of another indicator*: pass its handle as applied_price
int hSlow = iMA(_Symbol, PERIOD_CURRENT, 7, 0, MODE_SMA, hRsi);
int hAtr  = iATR(_Symbol, PERIOD_CURRENT, 14);
int hH1   = iRSI(_Symbol, PERIOD_H1, 14, PRICE_CLOSE);             // higher timeframe
int hCust = iCustom(_Symbol, PERIOD_CURRENT, "MyFolder\\MyIndicator", param1, param2);
if(hRsi == INVALID_HANDLE || hAtr == INVALID_HANDLE) { Print("handle error ", GetLastError()); return INIT_FAILED; }
```
- Create in `OnInit`, release in `OnDeinit` (`IndicatorRelease(h)`), never per tick.
- Passing a handle as `applied_price` builds an indicator on an indicator; that is exactly
  the TDI "SMA of RSI" and avoids re-implementing the maths.
- Built-ins: `iMA, iRSI, iATR, iMACD, iBands, iStochastic, iADX, iCCI, iMomentum, iStdDev,
  iIchimoku, iSAR, iAlligator, iVolumes, iOBV, iMFI, iWPR, iAO, iAC, iDEMA, iTEMA, iFrAMA,
  iVIDyA, iAMA, iBWMFI, iBearsPower, iBullsPower, iChaikin, iDeMarker, iEnvelopes,
  iForce, iFractals, iGator, iRVI, iStdDev, iTriX`.
- `iCustom` parameters must match the indicator's `input` order and types exactly; the
  path is relative to `MQL5\Indicators` and uses `\\`.

## Reading values
```mql5
double rsi[], atr[];
ArraySetAsSeries(rsi, true); ArraySetAsSeries(atr, true);
if(CopyBuffer(hRsi, 0, 0, 3, rsi) < 3 || CopyBuffer(hAtr, 0, 0, 2, atr) < 2) return;  // data not ready yet
double rsiClosed = rsi[1], rsiPrev = rsi[2], atrClosed = atr[1];
```
- `CopyBuffer(handle, bufferIndex, startPos, count, array)` returns the count copied or
  -1. In the tester the first ticks may return -1 while history loads: return and wait.
- With `ArraySetAsSeries(arr, true)`, index 0 = current forming bar, 1 = last closed.
  Without it, the newest element is `arr[count-1]`.
- `BarsCalculated(handle)` tells how many bars the indicator has computed; check it before
  reading deep history.
- Buffer indices for built-ins: iMACD 0 main 1 signal; iBands 0 base 1 upper 2 lower;
  iStochastic 0 main 1 signal; iADX 0 ADX 1 +DI 2 -DI; iAlligator 0 jaw 1 teeth 2 lips.

## Price data
```mql5
MqlRates rates[]; ArraySetAsSeries(rates, true);
int n = CopyRates(_Symbol, _Period, 0, 100, rates);      // rates[i].time/open/high/low/close/tick_volume/spread/real_volume
double c1 = iClose(_Symbol, _Period, 1), h1 = iHigh(_Symbol, _Period, 1);  // single values
datetime t0 = iTime(_Symbol, _Period, 0);
int shift = iBarShift(_Symbol, _Period, someTime);        // bar index for a time
int bars  = Bars(_Symbol, _Period);                       // or iBars
int hh    = iHighest(_Symbol, _Period, MODE_HIGH, 20, 1); // index of highest high over bars 1..20
MqlTick tick; SymbolInfoTick(_Symbol, tick);              // tick.bid, tick.ask, tick.time, tick.time_msc
```
`CopyClose/CopyHigh/CopyLow/CopyOpen/CopyTime/CopyTickVolume/CopySpread` fill arrays;
`CopyTicks`/`CopyTicksRange` return raw ticks (`MqlTick[]`).

## Pine ↔ MQL5 smoothing parity
| Pine | MQL5 | Same? |
|------|------|-------|
| `ta.rsi(close, n)` | `iRSI(..., n, PRICE_CLOSE)` | yes (Wilder) |
| `ta.sma(x, n)` | `iMA(..., n, 0, MODE_SMA, src)` | yes |
| `ta.ema(x, n)` | `iMA(..., n, 0, MODE_EMA, src)` | converges; different seed |
| `ta.rma(x, n)` | `iMA(..., n, 0, MODE_SMMA, src)` | yes (SMMA = Wilder) |
| `ta.atr(n)` | `iATR(..., n)` | **no**: MT5 ATR is SMA of TR; use `iMA(MODE_SMMA)` over a custom TR buffer or compute by hand |
| `ta.stdev(x, n)` | `iStdDev(..., n, 0, MODE_SMA, src)` | yes (population) |
| `ta.highest(h, n)` | `iHighest(sym, tf, MODE_HIGH, n, 1)` → `iHigh` | yes |
| `request.security(sym, tf, expr[1], lookahead_on)` | HTF handle, read index 1 | yes |

Hand-rolled Wilder ATR (parity with Pine):
```mql5
double AtrWilder(int period, int shift)   // shift = 1 for the last closed bar
{
   static double prev = 0; static datetime prevBar = 0;   // simple cache; recompute fully for correctness in loops
   int need = period * 6 + shift;                          // enough history for the recursion to settle
   MqlRates r[]; if(CopyRates(_Symbol, _Period, shift, need, r) < need) return 0;
   // r[] is NOT series here: r[0] oldest, r[need-1] newest
   double atr = 0;
   for(int i = 1; i < need; i++) {
      double tr = MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i-1].close), MathAbs(r[i].low - r[i-1].close)));
      atr = (i <= period) ? atr + tr / period : (atr * (period - 1) + tr) / period;
   }
   return atr;
}
```

## Timeframes
`ENUM_TIMEFRAMES`: `PERIOD_M1 M2 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1`,
`PERIOD_CURRENT`. `PeriodSeconds(tf)` gives seconds per bar; Pine's "2x and 4x the chart"
child zones map to the nearest ENUM value (M5 → M10 → M20; H1 → H2 → H4). There is no
seconds timeframe in MT5; the Pine "1 Sec" rung has no equivalent.

## Symbol and account info
`SymbolInfoDouble/Integer/String(_Symbol, SYMBOL_*)`, `AccountInfoDouble(ACCOUNT_BALANCE/EQUITY/MARGIN_FREE)`,
`AccountInfoInteger(ACCOUNT_LEVERAGE/ACCOUNT_MARGIN_MODE/ACCOUNT_TRADE_ALLOWED)`,
`TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)`, `MQLInfoInteger(MQL_TESTER / MQL_OPTIMIZATION / MQL_VISUAL_MODE)`.
`SymbolInfoSessionTrade(_Symbol, MONDAY, 0, from, to)` for sessions; `SYMBOL_TRADE_MODE` for
whether trading is allowed at all.
