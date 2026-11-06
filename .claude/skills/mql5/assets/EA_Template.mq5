//+------------------------------------------------------------------+
//|                                                  EA_Template.mq5 |
//|  Stop-order entry EA skeleton: the money-management pattern of    |
//|  the FlashGold v5 / XPW Orientation TDI Pine strategies.          |
//|                                                                   |
//|  - Signals computed once per bar on CLOSED bars (index 1)         |
//|  - Entry = stop order at ask + distance (buy) / bid - distance    |
//|    (sell), cancelled after N bars if unfilled                     |
//|  - SL / TP in ATR multiples or points; TP as an R multiple        |
//|  - Exit styles: Fixed TP (optional trailing) or Partial + runner  |
//|    (partial close at TP, stop to breakeven, ATR trail)            |
//|  - Time stop, opposite-signal exit / reverse, one entry per bar   |
//|  - Fixed lots or risk % of equity                                 |
//|  Fill in Signal() with the strategy's rules.                      |
//+------------------------------------------------------------------+
#property copyright "Template"
#property version   "1.00"

#include <Trade\Trade.mqh>

//--- enums
enum ENUM_DIRECTION { DIR_BOTH,  // Both
                      DIR_LONG,  // Long only
                      DIR_SHORT  // Short only
                    };
enum ENUM_DIST_UNIT { UNIT_ATR,    // ATR multiple
                      UNIT_POINTS  // Points
                    };
enum ENUM_TP_STYLE  { TP_FIXED,    // Fixed
                      TP_PARTIAL   // Partial + runner
                    };
enum ENUM_QTY_MODE  { QTY_FIXED,   // Fixed lots
                      QTY_RISK     // Risk % of equity
                    };

//--- inputs
input group "Core"
input long           InpMagic           = 240501;     // Magic number
input int            InpAtrLen          = 14;         // ATR length
input bool           InpDebug           = false;      // Verbose logging

input group "S1. Entries"
input ENUM_DIRECTION InpDirection       = DIR_BOTH;   // Direction
input ENUM_DIST_UNIT InpEntryUnit       = UNIT_ATR;   // Entry distance unit
input double         InpEntryDistAtr    = 0.25;       // Entry distance, ATR mult
input double         InpEntryDistPoints = 50;         // Entry distance, points
input int            InpEntryValidBars  = 3;          // Cancel unfilled entry after N bars (0 = keep)
input bool           InpOneEntryPerBar  = true;       // One entry per bar
input bool           InpAllowReverse    = true;       // Opposite signal may reverse
input bool           InpExitOnOpposite  = false;      // Close at market on opposite signal

input group "S2. Exits"
input ENUM_DIST_UNIT InpExitUnit        = UNIT_ATR;   // SL / TP / trail unit
input double         InpSlAtr           = 0.10;       // Stop loss, ATR mult
input double         InpSlPoints        = 3900;       // Stop loss, points
input double         InpTpR             = 2.0;        // Take profit, R multiple of SL (0 = none)
input ENUM_TP_STYLE  InpTpStyle         = TP_PARTIAL; // Take profit style
input double         InpPartPct         = 30;         // Partial: % closed at TP
input bool           InpRunBE           = true;       // Runner: stop to breakeven after TP
input double         InpRunTrailAtr     = 1.5;        // Runner: trail distance, ATR mult
input double         InpRunTrailPoints  = 58000;      // Runner: trail distance, points
input bool           InpUseTrail        = false;      // Fixed style: trailing stop
input double         InpTrailActAtr     = 1.0;        // Fixed style: trail activation, ATR mult
input double         InpTrailDstAtr     = 0.25;       // Fixed style: trail distance, ATR mult
input int            InpMaxBarsHeld     = 0;          // Time stop, bars (0 = off)

input group "S3. Sizing"
input ENUM_QTY_MODE  InpQtyMode         = QTY_FIXED;  // Quantity
input double         InpFixedLots       = 0.10;       // Fixed lots
input double         InpRiskPct         = 1.0;        // Risk % of equity per trade

//--- globals
CTrade        trade;
int           hAtr = INVALID_HANDLE;
datetime      lastBarTime = 0;
datetime      lastEntryBar = 0;
bool          isHedging = false;

// per-position runner state (hedging: one per ticket; netting: one per symbol)
struct RunnerState { ulong ticket; bool tpReached; double best; double atrAtEntry; };
RunnerState runners[];

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpAtrLen < 1 || InpPartPct < 0 || InpPartPct > 100) return INIT_PARAMETERS_INCORRECT;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(InpDebug ? LOG_LEVEL_ALL : LOG_LEVEL_ERRORS);
   isHedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   hAtr = iATR(_Symbol, _Period, InpAtrLen);
   if(hAtr == INVALID_HANDLE) { Print("iATR failed: ", GetLastError()); return INIT_FAILED; }
   RebuildRunnerState();
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { if(hAtr != INVALID_HANDLE) IndicatorRelease(hAtr); }

//+------------------------------------------------------------------+
void OnTick()
{
   // tick-level work: trailing stops and runner management
   ManagePositions();

   if(!IsNewBar()) return;

   double atr = AtrClosed();
   if(atr <= 0) return;                       // history not ready yet

   ExpireOldOrders();
   TimeStop();

   int sig = Signal();                        // +1 buy, -1 sell, 0 none
   if(sig == 0) return;
   if(InpDirection == DIR_LONG && sig < 0)  { if(InpExitOnOpposite) CloseSide(POSITION_TYPE_BUY);  return; }
   if(InpDirection == DIR_SHORT && sig > 0) { if(InpExitOnOpposite) CloseSide(POSITION_TYPE_SELL); return; }

   int net = NetDirection();                  // +1 long, -1 short, 0 flat
   if(net != 0 && net != sig)
   {
      if(InpExitOnOpposite) CloseSide(net > 0 ? POSITION_TYPE_BUY : POSITION_TYPE_SELL);
      else if(!InpAllowReverse) return;
   }
   if(net == sig) return;                     // already positioned this way (no pyramiding)
   if(InpOneEntryPerBar && lastEntryBar == iTime(_Symbol, _Period, 0)) return;

   PlaceEntry(sig, atr);
}

//+------------------------------------------------------------------+
//| Strategy signal on CLOSED bars. Replace with the real rules.      |
//+------------------------------------------------------------------+
int Signal()
{
   // Example placeholder: none. Read indicator buffers at index 1 / 2 here.
   return 0;
}

//+------------------------------------------------------------------+
//| Helpers                                                           |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime t = iTime(_Symbol, _Period, 0);
   if(t == lastBarTime) return false;
   lastBarTime = t;
   return true;
}

double AtrClosed()
{
   double a[];
   ArraySetAsSeries(a, true);
   if(CopyBuffer(hAtr, 0, 0, 2, a) < 2) return 0;
   return a[1];
}

double Dist(ENUM_DIST_UNIT unit, double atrMult, double points, double atr)
{
   return (unit == UNIT_ATR) ? atrMult * atr : points * _Point;
}

double RoundPrice(double p)
{
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) return NormalizeDouble(p, _Digits);
   return NormalizeDouble(MathRound(p / tick) * tick, _Digits);
}

double NormalizeVolume(double v)
{
   double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = minV;
   v = MathFloor(v / step + 1e-9) * step;
   v = MathMax(minV, MathMin(maxV, v));
   int digits = (int)MathRound(-MathLog10(step));
   if(digits < 0) digits = 0;
   return NormalizeDouble(v, digits);
}

double LotsFor(double slDistPrice)
{
   if(InpQtyMode == QTY_FIXED) return NormalizeVolume(InpFixedLots);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || slDistPrice <= 0) return 0;
   double riskMoney  = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double lossPerLot = slDistPrice / tickSize * tickVal;
   return NormalizeVolume(riskMoney / lossPerLot);
}

bool Mine()   // after PositionGetTicket / OrderGetTicket selected the item
{
   return PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic;
}

int NetDirection()
{
   double net = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0 || !Mine()) continue;
      net += (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1) * PositionGetDouble(POSITION_VOLUME);
   }
   return net > 0 ? 1 : (net < 0 ? -1 : 0);
}

//+------------------------------------------------------------------+
//| Entry: stop order beyond the market                               |
//+------------------------------------------------------------------+
void PlaceEntry(int sig, double atr)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entryDist = Dist(InpEntryUnit, InpEntryDistAtr, InpEntryDistPoints, atr);
   double slDist    = Dist(InpExitUnit,  InpSlAtr,        InpSlPoints,        atr);
   double tpDist    = InpTpR > 0 ? slDist * InpTpR : 0;

   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist  = stopsLevel * _Point;
   if(entryDist < minDist) entryDist = minDist;
   if(slDist > 0 && slDist < minDist) slDist = minDist;

   double price, sl = 0, tp = 0;
   if(sig > 0) { price = RoundPrice(ask + entryDist); if(slDist > 0) sl = RoundPrice(price - slDist); if(tpDist > 0 && InpTpStyle == TP_FIXED) tp = RoundPrice(price + tpDist); }
   else        { price = RoundPrice(bid - entryDist); if(slDist > 0) sl = RoundPrice(price + slDist); if(tpDist > 0 && InpTpStyle == TP_FIXED) tp = RoundPrice(price - tpDist); }
   // Partial + runner: no server TP, the EA closes the partial itself (see ManagePositions)

   double lots = LotsFor(slDist);
   int net = NetDirection();
   if(net != 0 && net != sig && InpAllowReverse && !InpExitOnOpposite)
      lots = NormalizeVolume(lots + OpenVolume());           // netting: reverses; hedging: closed on fill in OnTradeTransaction
   if(lots <= 0) { Print("lots = 0, skip"); return; }

   // one working entry at a time: delete our other pendings
   DeleteOurOrders();

   datetime expiry = 0;
   ENUM_ORDER_TYPE_TIME tt = ORDER_TIME_GTC;
   if(InpEntryValidBars > 0) { expiry = iTime(_Symbol, _Period, 0) + (datetime)(PeriodSeconds(_Period) * InpEntryValidBars); tt = ORDER_TIME_SPECIFIED; }

   string comment = StringFormat("%s|atr=%.5f", sig > 0 ? "BUY" : "SELL", atr);
   bool ok = (sig > 0) ? trade.BuyStop(lots, price, _Symbol, sl, tp, tt, expiry, comment)
                       : trade.SellStop(lots, price, _Symbol, sl, tp, tt, expiry, comment);
   PrintFormat("entry %s lots=%.2f price=%s sl=%s tp=%s -> %d %s", sig > 0 ? "BUY STOP" : "SELL STOP", lots,
               DoubleToString(price, _Digits), DoubleToString(sl, _Digits), DoubleToString(tp, _Digits),
               trade.ResultRetcode(), trade.ResultRetcodeDescription());
   if(ok) lastEntryBar = iTime(_Symbol, _Period, 0);
}

double OpenVolume()
{
   double v = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) != 0 && Mine()) v += PositionGetDouble(POSITION_VOLUME);
   return v;
}

void DeleteOurOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(t == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      trade.OrderDelete(t);
   }
}

void ExpireOldOrders()
{
   if(InpEntryValidBars <= 0) return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(t == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      datetime placed = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      int barsAgo = iBarShift(_Symbol, _Period, placed, false);
      if(barsAgo >= InpEntryValidBars) trade.OrderDelete(t);
   }
}

//+------------------------------------------------------------------+
//| Exits                                                             |
//+------------------------------------------------------------------+
void CloseSide(ENUM_POSITION_TYPE side)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !Mine() || PositionGetInteger(POSITION_TYPE) != side) continue;
      trade.PositionClose(t);
   }
}

void TimeStop()
{
   if(InpMaxBarsHeld <= 0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !Mine()) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      int held = iBarShift(_Symbol, _Period, opened, false);     // bars since the entry bar
      if(held >= InpMaxBarsHeld) trade.PositionClose(t);
   }
}

void ManagePositions()
{
   double atr = AtrClosed();
   if(atr <= 0) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !Mine()) continue;
      bool isBuy   = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double vol   = PositionGetDouble(POSITION_VOLUME);
      double px    = isBuy ? bid : ask;                      // price the position would close at
      double gain  = isBuy ? px - open : open - px;

      int r = RunnerIndex(t, true);
      double slDist = Dist(InpExitUnit, InpSlAtr, InpSlPoints, runners[r].atrAtEntry > 0 ? runners[r].atrAtEntry : atr);
      double tpDist = InpTpR > 0 ? slDist * InpTpR : 0;

      if(InpTpStyle == TP_FIXED)
      {
         if(!InpUseTrail) continue;
         double act = InpTrailActAtr * atr, dst = InpTrailDstAtr * atr;
         if(gain >= act) ImproveStop(t, isBuy, isBuy ? px - dst : px + dst, sl, tp);
         continue;
      }

      // Partial + runner
      if(!runners[r].tpReached)
      {
         if(tpDist > 0 && gain >= tpDist)
         {
            runners[r].tpReached = true;
            runners[r].best = px;
            double part = NormalizeVolume(vol * InpPartPct / 100.0);
            double minV = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            if(InpPartPct >= 100 || vol - part < minV) { trade.PositionClose(t); continue; }
            if(part >= minV) trade.PositionClosePartial(t, part);
            if(InpRunBE) ImproveStop(t, isBuy, open, sl, tp);
         }
         continue;
      }
      // trail the runner from the best price since TP was reached
      runners[r].best = isBuy ? MathMax(runners[r].best, px) : MathMin(runners[r].best, px);
      double trail = Dist(InpExitUnit, InpRunTrailAtr, InpRunTrailPoints, atr);
      double newSl = isBuy ? runners[r].best - trail : runners[r].best + trail;
      if(InpRunBE) newSl = isBuy ? MathMax(newSl, open) : MathMin(newSl, open);
      ImproveStop(t, isBuy, newSl, sl, tp);
   }
}

// Move SL only in the favourable direction and only by at least one tick
void ImproveStop(ulong ticket, bool isBuy, double candidate, double sl, double tp)
{
   candidate = RoundPrice(candidate);
   bool better = (sl == 0) || (isBuy ? candidate > sl : candidate < sl);
   if(!better || MathAbs(candidate - sl) < _Point) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(isBuy  && bid - candidate < minDist) return;
   if(!isBuy && candidate - ask < minDist) return;
   if(!trade.PositionModify(ticket, candidate, tp) && InpDebug)
      PrintFormat("modify %I64u sl=%s -> %d %s", ticket, DoubleToString(candidate, _Digits), trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| Runner state                                                      |
//+------------------------------------------------------------------+
int RunnerIndex(ulong ticket, bool create)
{
   for(int i = 0; i < ArraySize(runners); i++) if(runners[i].ticket == ticket) return i;
   if(!create) return -1;
   int n = ArraySize(runners);
   ArrayResize(runners, n + 1);
   runners[n].ticket = ticket; runners[n].tpReached = false; runners[n].best = 0;
   runners[n].atrAtEntry = AtrFromComment(PositionGetString(POSITION_COMMENT));
   return n;
}

double AtrFromComment(string c)   // "BUY|atr=0.01234" written by PlaceEntry, survives restarts
{
   int p = StringFind(c, "atr=");
   return p < 0 ? 0 : StringToDouble(StringSubstr(c, p + 4));
}

void RebuildRunnerState()
{
   ArrayResize(runners, 0);
   for(int i = 0; i < PositionsTotal(); i++)
      if(PositionGetTicket(i) != 0 && Mine()) RunnerIndex(PositionGetInteger(POSITION_TICKET), true);
}

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_IN)
   {
      // hedging reverse: a new position opened while an opposite one exists -> close the opposite
      if(isHedging && InpAllowReverse)
      {
         long newType = HistoryDealGetInteger(trans.deal, DEAL_TYPE);   // DEAL_TYPE_BUY / SELL
         CloseSide(newType == DEAL_TYPE_BUY ? POSITION_TYPE_SELL : POSITION_TYPE_BUY);
      }
      if(InpDebug) PrintFormat("filled deal %I64u at %s", trans.deal, DoubleToString(HistoryDealGetDouble(trans.deal, DEAL_PRICE), _Digits));
   }
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_OUT)
   {
      int r = RunnerIndex(trans.position, false);
      if(r >= 0 && !PositionSelectByTicket(trans.position)) { for(int k = r; k < ArraySize(runners) - 1; k++) runners[k] = runners[k + 1]; ArrayResize(runners, ArraySize(runners) - 1); }
   }
}

double OnTester()
{
   double trades = TesterStatistics(STAT_TRADES);
   if(trades < 30) return 0;
   double net = TesterStatistics(STAT_PROFIT);
   double dd  = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   return (net <= 0 || dd <= 0) ? 0 : net / dd;
}
//+------------------------------------------------------------------+
