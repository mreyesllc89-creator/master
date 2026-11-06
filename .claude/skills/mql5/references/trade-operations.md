# Trade operations

## CTrade (`#include <Trade\Trade.mqh>`)
```mql5
CTrade trade;
trade.SetExpertMagicNumber(InpMagic);
trade.SetDeviationInPoints(20);                 // max slippage for market orders
trade.SetTypeFillingBySymbol(_Symbol);          // picks FOK/IOC/RETURN the broker allows
trade.SetAsyncMode(false);                      // synchronous: ResultRetcode() is valid after the call
trade.LogLevel(LOG_LEVEL_ERRORS);
```
| Action | Call |
|--------|------|
| Market buy/sell | `trade.Buy(vol, _Symbol, 0, sl, tp, comment)` / `trade.Sell(...)` (price 0 = current) |
| Pending | `trade.BuyStop(vol, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, comment)`, `SellStop`, `BuyLimit`, `SellLimit`; expiry: `ORDER_TIME_SPECIFIED, expirationDatetime` |
| Modify position SL/TP | `trade.PositionModify(ticket, sl, tp)` |
| Modify pending | `trade.OrderModify(ticket, price, sl, tp, ORDER_TIME_GTC, 0)` |
| Close position | `trade.PositionClose(ticket)`; partial: `trade.PositionClosePartial(ticket, vol)` |
| Delete pending | `trade.OrderDelete(ticket)` |
| Result | `trade.ResultRetcode()`, `ResultRetcodeDescription()`, `ResultOrder()`, `ResultDeal()`, `ResultPrice()`, `ResultVolume()` |

`trade.Buy` returns `true` when the request was *sent and accepted* (retcode DONE or
PLACED); always check `ResultRetcode()` too.

Raw alternative: fill an `MqlTradeRequest`, call `OrderCheck(req, checkResult)` then
`OrderSend(req, result)`. Needed for `TRADE_ACTION_CLOSE_BY` and exotic fields.

## Reading positions and orders
```mql5
for(int i = PositionsTotal() - 1; i >= 0; i--)
{
   ulong ticket = PositionGetTicket(i);                 // selects the position
   if(ticket == 0) continue;
   if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
   long   type  = PositionGetInteger(POSITION_TYPE);    // POSITION_TYPE_BUY / SELL
   double vol   = PositionGetDouble(POSITION_VOLUME);
   double open  = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl    = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   datetime t   = (datetime)PositionGetInteger(POSITION_TIME);
   ...
}
for(int i = OrdersTotal() - 1; i >= 0; i--)
{
   ulong ticket = OrderGetTicket(i);
   long type = OrderGetInteger(ORDER_TYPE);             // ORDER_TYPE_BUY_STOP ...
   datetime placed = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
}
```
Iterate backwards when closing or deleting, because indices shift. Helper classes:
`CPositionInfo`, `COrderInfo`, `CSymbolInfo`, `CAccountInfo`, `CDealInfo`,
`CHistoryOrderInfo` in `<Trade\*.mqh>`.

Netting account (`AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING`):
`PositionSelect(_Symbol)` selects the single net position; an opposite market order
reduces/reverses it. Hedging: each deal is its own position with its own ticket.

## Prices, points, digits
```mql5
double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);        // == _Point
int    digits  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS); // == _Digits
double tick    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
long stopsLevel  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);   // points
long freezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);  // points
double RoundToTick(double p) { return MathRound(p / tick) * tick; }
```
- SL/TP/pending prices must be at least `stopsLevel * point` away from the current
  bid/ask (buy stop above ask, sell stop below bid; long SL below bid, long TP above bid).
  Some brokers report 0 and reject anyway; keep a configurable minimum.
- Orders/positions within `freezeLevel` of the market cannot be modified.
- Pip vs point: 5-digit forex pip = 10 points; the repo's BTCUSD strategy defines a pip as
  $1 = 100 points when digits = 2. Make it an input (`InpPipPoints`).

## Lot sizing
```mql5
double LotsForRisk(double riskMoney, double slDistancePrice)
{
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || slDistancePrice <= 0) return 0;
   double lossPerLot = slDistancePrice / tickSize * tickVal;     // money lost per 1.0 lot
   return NormalizeVolume(riskMoney / lossPerLot);
}
double NormalizeVolume(double v)
{
   double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   v = MathFloor(v / step) * step;
   v = MathMax(minV, MathMin(maxV, v));
   int digits = (int)MathRound(-MathLog10(step));
   return NormalizeDouble(v, digits);
}
```
`SYMBOL_TRADE_TICK_VALUE` is in account currency; for cross-currency pairs it already
includes the conversion. Check margin with `OrderCalcMargin` before large orders and
`AccountInfoDouble(ACCOUNT_MARGIN_FREE)`.

## Trailing stop, breakeven, partial + runner
```mql5
void TrailPosition(ulong ticket, double distPrice, double activatePrice)
{
   if(!PositionSelectByTicket(ticket)) return;
   long type = PositionGetInteger(POSITION_TYPE);
   double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double newSl = sl;
   if(type == POSITION_TYPE_BUY && bid - open >= activatePrice)  newSl = MathMax(sl, bid - distPrice);
   if(type == POSITION_TYPE_SELL && open - ask >= activatePrice) newSl = (sl == 0) ? ask + distPrice : MathMin(sl, ask + distPrice);
   newSl = NormalizeDouble(newSl, _Digits);
   if(MathAbs(newSl - sl) >= _Point) trade.PositionModify(ticket, newSl, tp);
}
```
- Modify only when the new stop improves by at least one tick; otherwise the server
  rejects with `TRADE_RETCODE_NO_CHANGES` and spams the log.
- **Partial + runner** (the Pine `TpStyle = "Partial + runner"`): place the position
  without a server TP, and when price reaches the target close `partPct` of the volume
  with `PositionClosePartial` (volume normalised to the step, remainder ≥ min volume),
  then set SL to breakeven and trail the rest. On a netting account a partial close is an
  opposite deal of the partial volume.
- Track per-position state (TP reached, best price) in a struct array keyed by ticket;
  rebuild it in `OnInit` from open positions and `POSITION_COMMENT`/history.

## Pending entry lifecycle (Pine `entryValidBars`, `allowReverse`, `oneEntryPerBar`)
- Place `BuyStop` at `ask + entryDistance` (sell: `bid - entryDistance`) with SL/TP
  attached if they are fixed distances from the entry price; otherwise set them on fill in
  `OnTradeTransaction`.
- Expire: on each new bar, delete orders whose `ORDER_TIME_SETUP` is older than N bars
  (`iBarShift(_Symbol, _Period, placed) >= N`), or use `ORDER_TIME_SPECIFIED` with an
  expiration time = N bars ahead (the tester honours it).
- One entry per bar: remember the bar time of the last placed order.
- Opposite signal while in position: `allowReverse` → place the opposite stop with the
  volume of the open position plus the new size (hedging: close then open on fill;
  netting: a single larger opposite deal reverses).

## Time stop
On new bar: `if(Bars(_Symbol, _Period, (datetime)PositionGetInteger(POSITION_TIME), TimeCurrent()) - 1 >= InpMaxBarsHeld) trade.PositionClose(ticket);`

## Closing everything (Pine `strategy.close_all`)
Loop positions backwards and `PositionClose`; loop orders backwards and `OrderDelete`;
check each retcode.
