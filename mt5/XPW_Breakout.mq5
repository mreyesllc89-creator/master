//+------------------------------------------------------------------+
//| XPW_Breakout.mq5                                                 |
//| MQL5 port of the XPW Breakout v2.10 Pine strategy (TradingView). |
//|                                                                  |
//| STEP 1 of 6 (skeleton):                                          |
//|   - symbol presets (BTCUSD / XAUUSD / custom) with VT Markets     |
//|     cost figures (used from step 2 on)                           |
//|   - ATR and confirmed pivots on CLOSED bars (ta.atr / pivothigh)  |
//|   - nearest pivot above / below the last close                   |
//|   - stop straddle: BuyStop at the upper level, SellStop at the    |
//|     lower one, SL/TP attached to the pending order itself so the  |
//|     position is protected from the fill (Pine F1)                |
//|   - the buffer ARMS the order; once resting it stays until it    |
//|     fills, the level changes (re-priced), the level goes away,   |
//|     or a position exists (Pine F11, base form)                   |
//|   - OCA: the fill of one leg deletes the other (Pine F5)          |
//|   - fixed lot size, magic number, status panel, logging          |
//|   Decisions are taken once per bar on the CLOSED bar, exactly    |
//|   like the Pine build in Execution = BarClose. This makes the    |
//|   Strategy Tester comparable with the TradingView trade list.    |
//|                                                                  |
//| Later steps: 2 cost model + risk sizing + deal-history referee,  |
//|   3 hard/soft gates, MaxDist, loss cap, cooldown, day cap,       |
//|   4 trail / breakeven / time stop on every tick,                 |
//|   5 Donchian + previous-day levels, CloseConfirm + Retest,       |
//|   6 panel polish, tick-mode arming, alerts.                      |
//+------------------------------------------------------------------+
#property copyright "XPW"
#property version   "0.11"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//============== INPUTS ==============//
enum ENUM_XPW_PRESET { PRESET_BTCUSD = 0, PRESET_XAUUSD = 1, PRESET_CUSTOM = 2 };
enum ENUM_XPW_GEO    { GEO_ATR = 0, GEO_PCT = 1 };

input group "1. Symbol preset"
input ENUM_XPW_PRESET InpPreset      = PRESET_XAUUSD;  // Preset (sets costs and lot defaults below when not Custom)
input long            InpMagic       = 210001;         // Magic number
input int             InpDeviation   = 50;             // Max deviation, points (market/stop fills)

input group "2. Costs (VT Markets MT5; informational in step 1, used from step 2)"
input double InpCommPerLotSide  = 0.0;   // Commission per lot per side, account currency (Custom preset)
input double InpSpreadPrice     = 0.0;   // Typical spread in price units (Custom preset)
input double InpSlipPrice       = 0.0;   // Expected slippage per side in price units (Custom preset)

input group "3. Sizing (step 1: fixed lots)"
input double InpLots            = 0.0;   // Lots (0 = preset default: BTC 0.10, XAU 0.10)

input group "4. Geometry"
input ENUM_XPW_GEO InpGeoMode   = GEO_ATR;  // Geometry
input double InpSlAtrMult       = 0.0;   // SL, ATR mult (0 = preset: BTC 3.0, XAU 1.5)
input double InpTpR             = 0.0;   // TP, R multiple of SL (0 = preset: BTC 3.0, XAU 2.5)
input double InpTPasPct         = 0.25;  // TP % of entry (Pct mode)
input double InpSLasPct         = 0.10;  // SL % of entry (Pct mode)
input int    InpAtrLen          = 14;    // ATR length

input group "5. Levels"
input int    InpBarsN           = 3;     // Pivot bars each side
input double InpBufAtrMult      = 0.0;   // Entry buffer, ATR mult (0 = preset: BTC 0.5, XAU 1.0)

input group "6. Display"
input bool   InpShowPanel       = true;  // Status panel (Comment)
input bool   InpVerbose         = true;  // Log decisions to the Experts tab

//============== STATE ==============//
CTrade        trade;
CPositionInfo posInfo;
COrderInfo    ordInfo;

int      atrHandle   = INVALID_HANDLE;
datetime lastBarTime = 0;

// resolved preset values
double   pCommPerLotSide, pSpreadPrice, pSlipPrice, pLots, pSlAtr, pTpR, pBufAtr;
string   pName;

// confirmed pivot levels (latched on closed bars)
double   swingH = 0.0, swingL = 0.0;      // 0 = none yet
double   lvlUp = 0.0,  lvlDn = 0.0;       // nearest level above / below last close (0 = none)
double   atrRef = 0.0;                    // ATR of the last closed bar
double   lastClose = 0.0;

// arm state
bool     armedL = false, armedS = false;
double   armLvlL = 0.0, armLvlS = 0.0;

//+------------------------------------------------------------------+
//| Preset resolution                                                |
//+------------------------------------------------------------------+
void ResolvePreset()
{
   // VT Markets MT5 figures supplied by the account holder (Sept 2026):
   //   BTCUSD: 1 lot = 1 BTC, spread ~2100 points = $21, no commission
   //   XAUUSD: 1 lot = 100 oz, spread 2.5 pips = $0.25, commission $0.6 per lot
   switch(InpPreset)
   {
      case PRESET_BTCUSD:
         pName = "BTCUSD"; pCommPerLotSide = 0.0;  pSpreadPrice = 21.0;  pSlipPrice = 5.0;
         pLots = 0.10; pSlAtr = 3.0; pTpR = 3.0; pBufAtr = 0.5;
         break;
      case PRESET_XAUUSD:
         pName = "XAUUSD"; pCommPerLotSide = 0.6; pSpreadPrice = 0.25;  pSlipPrice = 0.05;
         pLots = 0.10; pSlAtr = 1.5; pTpR = 2.5; pBufAtr = 1.0;
         break;
      default:
         pName = "Custom"; pCommPerLotSide = InpCommPerLotSide; pSpreadPrice = InpSpreadPrice; pSlipPrice = InpSlipPrice;
         pLots = 0.10; pSlAtr = 3.0; pTpR = 3.0; pBufAtr = 0.5;
         break;
   }
   if(InpLots      > 0) pLots   = InpLots;
   if(InpSlAtrMult > 0) pSlAtr  = InpSlAtrMult;
   if(InpTpR       > 0) pTpR    = InpTpR;
   if(InpBufAtrMult> 0) pBufAtr = InpBufAtrMult;
}

//+------------------------------------------------------------------+
int OnInit()
{
   ResolvePreset();
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviation);
   trade.SetTypeFillingBySymbol(_Symbol);
   atrHandle = iATR(_Symbol, _Period, InpAtrLen);
   if(atrHandle == INVALID_HANDLE) { Print("XPW: iATR failed"); return INIT_FAILED; }
   lastBarTime = 0;
   PrintFormat("XPW step1 init: preset=%s lots=%.2f SL=%.2f ATR TP=%.2fR buffer=%.2f ATR BarsN=%d geo=%s",
               pName, pLots, pSlAtr, pTpR, pBufAtr, InpBarsN, InpGeoMode == GEO_ATR ? "ATR" : "Pct");
   PrintFormat("XPW symbol: digits=%d point=%s contract=%.2f volmin=%.2f volstep=%.2f stoplevel=%d pts freeze=%d pts",
               _Digits, DoubleToString(_Point,_Digits), SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL));
   if(InpGeoMode == GEO_ATR && pSlAtr < 0.5) PrintFormat("XPW WARNING: SL %.2f ATR is very tight; calibrated values are BTC 3.0 / XAU 1.5 (leave the input at 0 for the preset)", pSlAtr);
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) Print("XPW WARNING: trading is not allowed in the terminal (Algo Trading button)");
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) Print("XPW WARNING: trading is not allowed for this EA (check 'Allow Algo Trading' in the EA settings)");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
   Comment("");
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double NormPrice(double p) { return NormalizeDouble(p, _Digits); }

double NormLots(double lots)
{
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vstep <= 0) vstep = vmin;
   double v = MathFloor(lots / vstep + 1e-9) * vstep;
   v = MathMax(vmin, MathMin(vmax, v));
   return NormalizeDouble(v, 8);
}

// Is there an open position of ours on this symbol?
bool HavePosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

// Ticket of our pending order of the given type on this symbol, 0 if none
ulong FindPending(ENUM_ORDER_TYPE type)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(t == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == type) return t;
   }
   return 0;
}

void DeletePending(ENUM_ORDER_TYPE type, string why)
{
   ulong t = FindPending(type);
   if(t == 0) return;
   if(trade.OrderDelete(t)) { if(InpVerbose) PrintFormat("XPW: deleted %s #%I64u (%s)", EnumToString(type), t, why); }
   else PrintFormat("XPW: OrderDelete %I64u failed: %d %s", t, trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

// Broker minimum distance for stops: stop level + current spread (+1 point safety)
double MinStopDist()
{
   double stops  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return stops + spread + _Point;
}

// Geometry in price units (Pine slDistAt / tpDistAt), from the closed-bar ATR.
// Clamped to the broker minimum so a mis-typed input cannot produce "invalid stops" on every order.
double SlDistAt(double px)
{
   double d = InpGeoMode == GEO_ATR ? atrRef * pSlAtr : px * InpSLasPct / 100.0;
   double m = MinStopDist();
   if(d < m) { if(InpVerbose) PrintFormat("XPW: SL distance %s below broker minimum %s, clamped", DoubleToString(d,_Digits), DoubleToString(m,_Digits)); d = m; }
   return d;
}
double TpDistAt(double px)
{
   double d = InpGeoMode == GEO_ATR ? atrRef * pSlAtr * pTpR : px * InpTPasPct / 100.0;
   double m = MinStopDist();
   if(d < m) { if(InpVerbose) PrintFormat("XPW: TP distance %s below broker minimum %s, clamped", DoubleToString(d,_Digits), DoubleToString(m,_Digits)); d = m; }
   return d;
}

//+------------------------------------------------------------------+
//| Confirmed pivots on closed bars (ta.pivothigh(high, n, n))       |
//| A pivot at shift n+1 is confirmed when the n bars on each side   |
//| are closed: left strictly lower, right lower-or-equal (Pine).    |
//+------------------------------------------------------------------+
void UpdatePivots()
{
   int n = InpBarsN;
   int c = n + 1;                       // candidate bar: n closed bars to its right (shifts 1..n)
   int need = 2 * n + 2;
   if(Bars(_Symbol, _Period) < need) return;
   double hc = iHigh(_Symbol, _Period, c), lc = iLow(_Symbol, _Period, c);
   bool isH = true, isL = true;
   for(int k = 1; k <= n; k++)
   {
      double hl = iHigh(_Symbol, _Period, c + k), hr = iHigh(_Symbol, _Period, c - k);   // left (older), right (newer)
      double ll = iLow(_Symbol, _Period, c + k),  lr = iLow(_Symbol, _Period, c - k);
      if(!(hl < hc && hr <= hc)) isH = false;
      if(!(ll > lc && lr >= lc)) isL = false;
   }
   if(isH) swingH = hc;
   if(isL) swingL = lc;
}

//+------------------------------------------------------------------+
//| Bar-close evaluation (Pine: everything under barstate.isconfirmed)|
//+------------------------------------------------------------------+
void OnClosedBar()
{
   double atrBuf[];
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuf) != 1) return;   // ATR of the last CLOSED bar
   atrRef    = atrBuf[0];
   lastClose = iClose(_Symbol, _Period, 1);
   if(atrRef <= 0) return;

   UpdatePivots();
   // nearest level above / below the last close (pivot source only in step 1)
   lvlUp = (swingH > 0 && swingH > lastClose) ? swingH : 0.0;
   lvlDn = (swingL > 0 && swingL < lastClose) ? swingL : 0.0;

   double buffer = atrRef * pBufAtr;
   bool   flat   = !HavePosition();
   double lots   = NormLots(pLots);
   int    stopsPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist  = stopsPts * _Point;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   //----- long leg -----
   ulong buyT = FindPending(ORDER_TYPE_BUY_STOP);
   if(!flat || lvlUp <= 0)
   {
      armedL = false; armLvlL = 0;
      if(buyT != 0) DeletePending(ORDER_TYPE_BUY_STOP, flat ? "no level above" : "position open");
   }
   else
   {
      bool lvlChanged = (armLvlL <= 0) || MathAbs(lvlUp - armLvlL) > _Point / 2.0;
      if(!armedL || lvlChanged)
         armedL = (lastClose < lvlUp - buffer);               // the buffer ARMS only (F11)
      if(armedL && lvlUp - ask < minDist) armedL = false;    // broker stop level
      if(armedL)
      {
         double px = NormPrice(lvlUp), sl = NormPrice(lvlUp - SlDistAt(lvlUp)), tp = NormPrice(lvlUp + TpDistAt(lvlUp));
         if(buyT == 0)
         {
            if(trade.BuyStop(lots, px, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "XPW L stop"))
            { armLvlL = lvlUp; if(InpVerbose) PrintFormat("XPW: BuyStop %.2f lots @ %s SL %s TP %s", lots, DoubleToString(px,_Digits), DoubleToString(sl,_Digits), DoubleToString(tp,_Digits)); }
            else { armedL = false; PrintFormat("XPW: BuyStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()); }
         }
         else if(lvlChanged)
         {
            if(trade.OrderModify(buyT, px, sl, tp, ORDER_TIME_GTC, 0)) { armLvlL = lvlUp; if(InpVerbose) PrintFormat("XPW: BuyStop re-priced to %s", DoubleToString(px,_Digits)); }
            else PrintFormat("XPW: OrderModify BuyStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
         }
      }
      else
      {
         armLvlL = 0;
         if(buyT != 0) DeletePending(ORDER_TYPE_BUY_STOP, "disarmed");
      }
   }

   //----- short leg -----
   ulong sellT = FindPending(ORDER_TYPE_SELL_STOP);
   if(!flat || lvlDn <= 0)
   {
      armedS = false; armLvlS = 0;
      if(sellT != 0) DeletePending(ORDER_TYPE_SELL_STOP, flat ? "no level below" : "position open");
   }
   else
   {
      bool lvlChanged = (armLvlS <= 0) || MathAbs(lvlDn - armLvlS) > _Point / 2.0;
      if(!armedS || lvlChanged)
         armedS = (lastClose > lvlDn + buffer);
      if(armedS && bid - lvlDn < minDist) armedS = false;
      if(armedS)
      {
         double px = NormPrice(lvlDn), sl = NormPrice(lvlDn + SlDistAt(lvlDn)), tp = NormPrice(lvlDn - TpDistAt(lvlDn));
         if(sellT == 0)
         {
            if(trade.SellStop(lots, px, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "XPW S stop"))
            { armLvlS = lvlDn; if(InpVerbose) PrintFormat("XPW: SellStop %.2f lots @ %s SL %s TP %s", lots, DoubleToString(px,_Digits), DoubleToString(sl,_Digits), DoubleToString(tp,_Digits)); }
            else { armedS = false; PrintFormat("XPW: SellStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()); }
         }
         else if(lvlChanged)
         {
            if(trade.OrderModify(sellT, px, sl, tp, ORDER_TIME_GTC, 0)) { armLvlS = lvlDn; if(InpVerbose) PrintFormat("XPW: SellStop re-priced to %s", DoubleToString(px,_Digits)); }
            else PrintFormat("XPW: OrderModify SellStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
         }
      }
      else
      {
         armLvlS = 0;
         if(sellT != 0) DeletePending(ORDER_TYPE_SELL_STOP, "disarmed");
      }
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 != lastBarTime)
   {
      lastBarTime = t0;
      OnClosedBar();
   }
   if(InpShowPanel) UpdatePanel();
}

//+------------------------------------------------------------------+
//| OCA: when one leg fills, delete the other (Pine F5)              |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_IN) return;
   DeletePending(ORDER_TYPE_BUY_STOP,  "OCA: sibling filled");
   DeletePending(ORDER_TYPE_SELL_STOP, "OCA: sibling filled");
   armedL = false; armedS = false; armLvlL = 0; armLvlS = 0;
}

//+------------------------------------------------------------------+
void UpdatePanel()
{
   string pos = "flat";
   if(HavePosition())
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         pos = StringFormat("%s %.2f lots @ %s SL %s TP %s",
               (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "LONG" : "SHORT",
               PositionGetDouble(POSITION_VOLUME), DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN),_Digits),
               DoubleToString(PositionGetDouble(POSITION_SL),_Digits), DoubleToString(PositionGetDouble(POSITION_TP),_Digits));
      }
   }
   double spreadNow = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
   string s = StringFormat("XPW Breakout step 1  [%s]  %s\n", pName, _Symbol);
   s += StringFormat("ATR(%d) %s   SL %s   TP %s   buffer %s\n", InpAtrLen, DoubleToString(atrRef,_Digits),
                     DoubleToString(SlDistAt(lastClose),_Digits), DoubleToString(TpDistAt(lastClose),_Digits), DoubleToString(atrRef*pBufAtr,_Digits));
   s += StringFormat("Level up %s   level down %s   last close %s\n", lvlUp>0?DoubleToString(lvlUp,_Digits):"-", lvlDn>0?DoubleToString(lvlDn,_Digits):"-", DoubleToString(lastClose,_Digits));
   s += StringFormat("Armed L/S %s/%s   BuyStop %s   SellStop %s\n", armedL?"yes":"no", armedS?"yes":"no",
                     FindPending(ORDER_TYPE_BUY_STOP)?"resting":"-", FindPending(ORDER_TYPE_SELL_STOP)?"resting":"-");
   s += StringFormat("Position: %s\n", pos);
   s += StringFormat("Spread now %s (model %s)   stop level %d pts   lots %.2f\n", DoubleToString(spreadNow,_Digits), DoubleToString(pSpreadPrice,_Digits),
                     (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), NormLots(pLots));
   Comment(s);
}
//+------------------------------------------------------------------+
