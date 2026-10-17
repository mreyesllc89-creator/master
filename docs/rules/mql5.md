# MQL5 rules (MetaTrader 5 EAs and indicators)

Read this before writing or changing any `.mq5` or `.mqh` file.

## Structure

- Layout: `MQL5/Experts/`, `MQL5/Indicators/`, `MQL5/Include/XPW/`. Code that
  more than one EA needs (lot sizing, order sending, filters, signal math) goes
  in an include. Never copy it into a second EA.
- Indicator handles (`iRSI`, `iMA`, `iATR`, `iCustom`, ...) are created once in
  `OnInit`, checked against `INVALID_HANDLE`, and released with
  `IndicatorRelease` in `OnDeinit`. Never create a handle in `OnTick`.
- Read indicator values with `CopyBuffer`, and check the number of values
  returned before using them. `ArraySetAsSeries(buf, true)` so index 1 is the
  last closed bar.

## Signals match TradingView

- Signals run once per new bar on the trading timeframe, read from closed bars
  (shift 1). This is what the Pine strategies do, and it keeps the EA's
  backtest comparable to theirs.

```mql5
bool IsNewBar(ENUM_TIMEFRAMES tf)
{
   static datetime last = 0;
   datetime t = iTime(_Symbol, tf, 0);
   if(t == 0 || t == last) return false;
   last = t;
   return true;
}
```

- Higher-timeframe values come from that timeframe's last closed bar. This is
  the MQL5 version of Pine's `[1]` + `lookahead_on` idiom.
- When an EA ports a Pine strategy, the header lists every difference from the
  TradingView fill model: market fill at Ask/Bid instead of the exact stop
  price, spread, slippage, and pending orders held virtually by the EA.
  `FlashGold_v5_EA.mq5` (branch `claude/jolly-rubin-xk3c4b`) is the reference
  for this section.

## Orders

- Use `CTrade` with `SetExpertMagicNumber(InpMagic)`. Each EA instance gets its
  own magic number, and the EA only manages positions and orders that carry it.
- Normalize lots to `SYMBOL_VOLUME_MIN` / `SYMBOL_VOLUME_MAX` /
  `SYMBOL_VOLUME_STEP`. Normalize prices to `_Digits` / `SYMBOL_TRADE_TICK_SIZE`.
- Check `SYMBOL_TRADE_STOPS_LEVEL` before placing SL/TP or pending orders, and
  `SYMBOL_TRADE_FREEZE_LEVEL` before modifying them.
- After every order call, check `ResultRetcode()`. Do not resend on every tick:
  retry after a delay, and wait for the next bar after a hard refusal (no
  money, invalid volume, invalid stops, market closed). Retry failed exits
  every second.
- Risk-based sizing uses `SYMBOL_TRADE_TICK_VALUE` and `SYMBOL_TRADE_TICK_SIZE`,
  never a hard-coded pip value. Check `OrderCalcMargin` before sending.
- Handle netting and hedging accounts. On netting accounts, do not trade into
  a position the EA does not own.

## Risk limits

- Grid, martingale, recovery and hedge logic (for example
  `TokioXAU_SinLimites_V3`) must have a hard equity stop and a max-exposure
  input that are on by default. Their test reports always show max drawdown
  and worst floating loss next to profit.
- Every EA has a daily loss limit input and a spread filter.

## File header

Same as the Pine rules: source, what was kept, what was added, the differences
from TradingView, and a **CALIBRATION** block per [validation.md](validation.md).
State the account type (netting or hedging) and broker it was tested on.
