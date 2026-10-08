//+------------------------------------------------------------------+
//| AsiaLondonBreakout.mq5                                           |
//| Asia-range breakout at the London open, for XAUUSD and BTCUSD.   |
//|                                                                  |
//| Rule (all times = broker SERVER time, VT Markets = GMT+3):       |
//|  1. Asia range = bid high / low from RangeStart to RangeEnd      |
//|     (default 03:00-10:00 server = 00:00-07:00 UTC).              |
//|  2. At RangeEnd: BUY STOP at the range high, SELL STOP at the    |
//|     range low (+ optional buffer). First fill cancels the other: |
//|     at most one trade per day.                                   |
//|  3. Stop loss = the range size from the fill (opposite side of   |
//|     the range), or half the range (Midpoint mode).               |
//|  4. Exit at ExitTime (default 19:00 server), or at the take      |
//|     profit (R multiple of the stop) if set. Unfilled orders are  |
//|     deleted at ExitTime.                                         |
//|  5. Monday to Friday only.                                       |
//|                                                                  |
//| Tested tick by tick on VT Markets ticks, Jul 13 - Oct 8 2026     |
//| (real bid/ask, real spreads): see presets/README.md. Every       |
//| range/exit hour combination from 02-04 / 09-11 / 17-21 was       |
//| profitable on both symbols. Demo-test before live trading.       |
//+------------------------------------------------------------------+
#property copyright "Asia London Breakout"
#property version   "1.00"
#property description "Asia range breakout at the London open (server-time sessions, spread filter, one trade per day)"

#include <Trade\Trade.mqh>

enum ENUM_ALB_STOP  { ALB_STOP_OPPOSITE = 0, // Opposite side of the range
                      ALB_STOP_MID = 1       // Range midpoint
                    };
enum ENUM_ALB_QTY   { ALB_QTY_FIXED = 0,     // Fixed lots
                      ALB_QTY_RISK = 1       // Risk % of equity
                    };
enum ENUM_ALB_FILTER{ ALB_FLT_NONE = 0,      // None
                      ALB_FLT_SKIPWIDE = 1,  // Skip ranges wider than 2x the 10-day median
                      ALB_FLT_SKIPNARROW = 2 // Skip ranges narrower than 0.5x the 10-day median
                    };

input group "Session (broker SERVER time)"
input int    InpRangeStartHour = 3;     // Asia range start, hour
input int    InpRangeStartMin  = 0;     // Asia range start, minute
input int    InpRangeEndHour   = 10;    // Asia range end = breakout start (London open), hour
input int    InpRangeEndMin    = 0;     // Asia range end, minute
input int    InpExitHour       = 19;    // Exit time (close trade, delete orders), hour
input int    InpExitMin        = 0;     // Exit time, minute
input bool   InpMon            = true;  // Trade Monday
input bool   InpTue            = true;  // Trade Tuesday
input bool   InpWed            = true;  // Trade Wednesday
input bool   InpThu            = true;  // Trade Thursday
input bool   InpFri            = true;  // Trade Friday

input group "Entry / exit"
input double InpBufferPct      = 0.0;   // Entry buffer beyond the range, % of range size
input ENUM_ALB_STOP InpStopMode = ALB_STOP_OPPOSITE; // Stop loss
input double InpTpR            = 0.0;   // Take profit, R multiple of the stop (0 = exit at Exit time)
input ENUM_ALB_FILTER InpRangeFilter = ALB_FLT_NONE; // Range-size filter
input double InpMinRange       = 0.0;   // Minimum range size, price units (0 = off)
input double InpMaxRange       = 0.0;   // Maximum range size, price units (0 = off)

input group "Spread"
input double InpMaxSpread      = 0.50;  // Max spread when placing the orders, price units (0 = off; waits until it narrows)

input group "Sizing"
input ENUM_ALB_QTY InpQtyMode  = ALB_QTY_FIXED; // Quantity
input double InpLots           = 0.10;  // Fixed lots
input double InpRiskPct        = 0.5;   // Risk % of equity per trade (Risk mode)
input double InpMaxLots        = 5.0;   // Max lots

input group "EA"
input long   InpMagic          = 60601; // Magic number
input bool   InpDrawRange      = true;  // Draw the Asia range on the chart
input bool   InpShowPanel      = true;  // Show status panel

CTrade   trade;
datetime g_dayDone = 0;      // server date whose orders were already placed
datetime g_dayFilled = 0;    // server date that already got its one trade
double   g_rangeHigh = 0, g_rangeLow = 0, g_slDist = 0;
string   g_status = "waiting for the range";

//------------------------------------------------------------------ helpers
datetime DayStart(datetime t)            { return t - (t % 86400); }
datetime At(datetime day, int h, int m)  { return day + h * 3600 + m * 60; }

double NormPrice(double p)
{
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
}

double NormVol(double v)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = 0.01;
   v = MathFloor(v / step + 1e-9) * step;
   if(v < vmin) return 0.0;
   return NormalizeDouble(MathMin(v, vmax), 8);
}

double Spread() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }

bool DayAllowed(datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   switch(d.day_of_week)
   {
      case 1: return InpMon; case 2: return InpTue; case 3: return InpWed;
      case 4: return InpThu; case 5: return InpFri;
   }
   return false;
}

// bid high / low of the M1 bars inside [from, to)
bool RangeOf(datetime from, datetime to, double &hi, double &lo)
{
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, from, to - 60, r);
   if(n < 10) return false;
   hi = -DBL_MAX; lo = DBL_MAX;
   for(int i = 0; i < n; i++)
   {
      if(r[i].time < from || r[i].time >= to) continue;
      hi = MathMax(hi, r[i].high); lo = MathMin(lo, r[i].low);
   }
   return hi > lo;
}

// median Asia-range size of the previous 10 trading days (range filter)
double MedianPastRange(datetime today)
{
   double v[]; int k = 0;
   for(int back = 1; back <= 20 && k < 10; back++)
   {
      datetime d = today - back * 86400;
      if(!DayAllowed(d)) continue;
      double h, l;
      if(!RangeOf(At(d, InpRangeStartHour, InpRangeStartMin), At(d, InpRangeEndHour, InpRangeEndMin), h, l)) continue;
      ArrayResize(v, k + 1); v[k++] = h - l;
   }
   if(k < 5) return 0;
   ArraySort(v);
   return k % 2 == 1 ? v[k / 2] : 0.5 * (v[k / 2 - 1] + v[k / 2]);
}

int CountPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) c++;
   }
   return c;
}

int CountOrders()
{
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || !OrderSelect(tk)) continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic) c++;
   }
   return c;
}

void DeleteOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || !OrderSelect(tk)) continue;
      if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic) trade.OrderDelete(tk);
   }
}

void CloseAll(string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         if(!trade.PositionClose(tk)) PrintFormat("ALB: close (%s) failed %d", why, trade.ResultRetcode());
   }
}

double Lots(double slDist)
{
   double q = InpLots;
   if(InpQtyMode == ALB_QTY_RISK)
   {
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double perLot = (tv > 0 && ts > 0) ? slDist / ts * tv : 0;
      q = perLot > 0 ? AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0 / perLot : 0;
   }
   return NormVol(MathMin(q, InpMaxLots));
}

void DrawRange(datetime day)
{
   if(!InpDrawRange) return;
   string n = "ALB_" + TimeToString(day, TIME_DATE);
   if(ObjectFind(0, n) < 0)
   {
      ObjectCreate(0, n, OBJ_RECTANGLE, 0, At(day, InpRangeStartHour, InpRangeStartMin), g_rangeHigh, At(day, InpRangeEndHour, InpRangeEndMin), g_rangeLow);
      ObjectSetInteger(0, n, OBJPROP_COLOR, clrSteelBlue);
      ObjectSetInteger(0, n, OBJPROP_FILL, true);
      ObjectSetInteger(0, n, OBJPROP_BACK, true);
   }
}

//------------------------------------------------------------------ core
void PlaceOrders(datetime day)
{
   if(CountOrders() > 0 || CountPositions() > 0) { g_dayDone = day; g_status = "orders / trade already open (restart)"; return; }
   double hi, lo;
   datetime rs = At(day, InpRangeStartHour, InpRangeStartMin), re = At(day, InpRangeEndHour, InpRangeEndMin);
   if(!RangeOf(rs, re, hi, lo)) { g_status = "no range data today"; g_dayDone = day; return; }
   double R = hi - lo;
   g_rangeHigh = hi; g_rangeLow = lo; DrawRange(day);
   if(InpMinRange > 0 && R < InpMinRange) { g_status = "range too small, no trade"; g_dayDone = day; return; }
   if(InpMaxRange > 0 && R > InpMaxRange) { g_status = "range too large, no trade"; g_dayDone = day; return; }
   if(InpRangeFilter != ALB_FLT_NONE)
   {
      double med = MedianPastRange(day);
      if(med > 0 && InpRangeFilter == ALB_FLT_SKIPWIDE && R > 2.0 * med)   { g_status = "range > 2x median, no trade"; g_dayDone = day; return; }
      if(med > 0 && InpRangeFilter == ALB_FLT_SKIPNARROW && R < 0.5 * med) { g_status = "range < 0.5x median, no trade"; g_dayDone = day; return; }
   }
   if(InpMaxSpread > 0 && Spread() > InpMaxSpread) { g_status = StringFormat("spread %.2f too wide, waiting", Spread()); return; }   // retry next tick

   double buf = R * InpBufferPct / 100.0;
   double bs = hi + buf, ss = lo - buf;
   g_slDist = InpStopMode == ALB_STOP_OPPOSITE ? (bs - ss) : (R / 2.0 + buf);
   double vol = Lots(g_slDist);
   if(vol <= 0) { g_status = "lot size 0, no trade"; g_dayDone = day; return; }
   double tpD = InpTpR > 0 ? g_slDist * InpTpR : 0;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stops = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   trade.SetExpertMagicNumber(InpMagic);

   // price already beyond a level at the breakout time: enter at market (the tested rule fills at the first tick past the level)
   if(ask >= bs)
   {
      trade.Buy(vol, _Symbol, 0, NormPrice(ask - g_slDist), tpD > 0 ? NormPrice(ask + tpD) : 0, "ALB buy");
      g_dayDone = day; g_status = "bought at market (opened above the range)"; return;
   }
   if(bid <= ss)
   {
      trade.Sell(vol, _Symbol, 0, NormPrice(bid + g_slDist), tpD > 0 ? NormPrice(bid - tpD) : 0, "ALB sell");
      g_dayDone = day; g_status = "sold at market (opened below the range)"; return;
   }
   datetime exp = At(day, InpExitHour, InpExitMin);
   double bp = NormPrice(MathMax(bs, ask + stops + _Point)), sp = NormPrice(MathMin(ss, bid - stops - _Point));
   bool okB = trade.BuyStop(vol, bp, _Symbol, NormPrice(bp - g_slDist), tpD > 0 ? NormPrice(bp + tpD) : 0, ORDER_TIME_SPECIFIED, exp, "ALB buy stop");
   if(!okB) okB = trade.BuyStop(vol, bp, _Symbol, NormPrice(bp - g_slDist), tpD > 0 ? NormPrice(bp + tpD) : 0, ORDER_TIME_GTC, 0, "ALB buy stop");     // broker without expiry support: deleted at exit time by the EA
   bool okS = trade.SellStop(vol, sp, _Symbol, NormPrice(sp + g_slDist), tpD > 0 ? NormPrice(sp - tpD) : 0, ORDER_TIME_SPECIFIED, exp, "ALB sell stop");
   if(!okS) okS = trade.SellStop(vol, sp, _Symbol, NormPrice(sp + g_slDist), tpD > 0 ? NormPrice(sp - tpD) : 0, ORDER_TIME_GTC, 0, "ALB sell stop");
   if(!okB || !okS) PrintFormat("ALB: order placement buy=%d sell=%d retcode %d", okB, okS, trade.ResultRetcode());
   g_dayDone = day;
   g_status = StringFormat("orders placed: buy %.2f / sell %.2f, stop %.2f", bp, sp, g_slDist);
}

// on a fill: cancel the other order (one trade per day) and re-anchor SL / TP on the real fill price
void OnFill(datetime day)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(g_dayFilled == day) return;
      g_dayFilled = day;
      DeleteOrders();
      if(g_slDist <= 0) return;
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double op = PositionGetDouble(POSITION_PRICE_OPEN);
      double tpD = InpTpR > 0 ? g_slDist * InpTpR : 0;
      double sl = NormPrice(isBuy ? op - g_slDist : op + g_slDist);
      double tp = tpD > 0 ? NormPrice(isBuy ? op + tpD : op - tpD) : 0;
      trade.PositionModify(tk, sl, tp);
      g_status = StringFormat("%s filled at %.2f, SL %.2f%s", isBuy ? "BUY" : "SELL", op, sl, tp > 0 ? StringFormat(", TP %.2f", tp) : ", exit at exit time");
      return;
   }
}

//------------------------------------------------------------------ events
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(At(0, InpRangeEndHour, InpRangeEndMin) <= At(0, InpRangeStartHour, InpRangeStartMin) || At(0, InpExitHour, InpExitMin) <= At(0, InpRangeEndHour, InpRangeEndMin))
   { Print("ALB: times must be RangeStart < RangeEnd < Exit on the same server day"); return INIT_PARAMETERS_INCORRECT; }
   PrintFormat("AsiaLondonBreakout on %s: range %02d:%02d-%02d:%02d, exit %02d:%02d (server time)", _Symbol, InpRangeStartHour, InpRangeStartMin, InpRangeEndHour, InpRangeEndMin, InpExitHour, InpExitMin);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { Comment(""); }

void OnTick()
{
   datetime now = TimeCurrent(), day = DayStart(now);
   datetime re = At(day, InpRangeEndHour, InpRangeEndMin), ex = At(day, InpExitHour, InpExitMin);

   // exit time: close everything and delete unfilled orders
   if(now >= ex)
   {
      if(CountPositions() > 0) CloseAll("exit time");
      DeleteOrders();
      if(g_dayDone != day) g_status = "session over";
   }
   // breakout window: place the two stop orders once per day
   else if(now >= re && g_dayDone != day && g_dayFilled != day && DayAllowed(now))
      PlaceOrders(day);

   if(CountPositions() > 0) OnFill(day);

   if(InpShowPanel)
      Comment(StringFormat("Asia London Breakout  |  %s\nRange %02d:%02d-%02d:%02d  exit %02d:%02d (server)\nToday's range: %.2f - %.2f (%.2f)\nSpread: %.2f (max %.2f)\nStatus: %s",
              _Symbol, InpRangeStartHour, InpRangeStartMin, InpRangeEndHour, InpRangeEndMin, InpExitHour, InpExitMin,
              g_rangeLow, g_rangeHigh, g_rangeHigh - g_rangeLow, Spread(), InpMaxSpread, g_status));
}
//+------------------------------------------------------------------+
