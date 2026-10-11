//+------------------------------------------------------------------+
//|                                              XPW_ShapeMap_EA.mq5 |
//| XPW Shape Map v0.9 STRATEGY — MQL5 port.                         |
//| Reads every signal from the XPW_ShapeMap indicator (iCustom), so |
//| the EA and the map always agree. ONE entry signal at a time:     |
//|   SQUARE  BOT square = LONG, TOP square = SHORT                  |
//|   TURN    Turn ▲ = LONG, Turn ▼ = SHORT (Predict / At cross /    |
//|           After hold)                                            |
//|   TICK    BOT tick = LONG, TOP tick = SHORT                      |
//|   CONT    CONT ▲ = LONG, CONT ▼ = SHORT (at close / stop past    |
//|           the signal candle)                                     |
//| "Points" here = MetaTrader points (_Point). XAUUSD: 1 pt = 0.01  |
//| so 700 pts = $7/oz. BTCUSD at a 0.01-point broker: 70000 pts =   |
//| $700. Check your broker's point size and scale the inputs.       |
//| Place XPW_ShapeMap.mq5 in MQL5\Indicators and this file in       |
//| MQL5\Experts, compile both.                                      |
//+------------------------------------------------------------------+
#property copyright "XPW"
#property version   "0.90"
#property description "XPW Shape Map v0.9 strategy: squares / turns / ticks / CONT entries with SL, TP, trailing and risk sizing."
#include <Trade\Trade.mqh>

enum ENUM_SIG_MODE   { SIG_SQUARE = 0,  // BOT/TOP square
                       SIG_TURN   = 1,  // Turn up/down
                       SIG_TICK   = 2,  // BOT/TOP tick
                       SIG_CONT   = 3 };// CONT up/down
enum ENUM_TRADE_DIR  { DIR_BOTH = 0, DIR_LONG = 1, DIR_SHORT = 2 };
enum ENUM_TURN_ENTRY { TURN_PREDICT = 0,     // Predict (stop at cross price)
                       TURN_AT_CROSS = 1,    // At the cross
                       TURN_AFTER_HOLD = 2 };// After hold (when arrow confirms)
enum ENUM_OPP_MODE   { OPP_REVERSE = 0, OPP_CLOSE = 1, OPP_IGNORE = 2 };
enum ENUM_ARM_MODE   { ARM_SQUARES = 0, ARM_EVERY = 1 };
enum ENUM_CONT_ENTRY { CONT_AT_CLOSE = 0, CONT_STOP = 1 };
enum ENUM_EXIT_UNIT  { EXIT_POINTS = 0, EXIT_ATR = 1 };
enum ENUM_QTY_MODE   { QTY_FIXED = 0, QTY_RISK = 1 };

input group "S1. Entry"
input ENUM_SIG_MODE   SigMode     = SIG_TURN;        // Entry signal (one only)
input ENUM_TRADE_DIR  TradeDir    = DIR_BOTH;        // Trade direction
input bool            EnterOnTick = true;            // Enter on tick (don't wait for candle close)
input ENUM_TURN_ENTRY TurnEntry   = TURN_PREDICT;    // Turn entry timing
input bool            FailExit    = false;           // Turn: exit if the cross fails to hold
input ENUM_OPP_MODE   OppMode     = OPP_REVERSE;     // Opposite signal while in a trade
input group "S1b. Predict calibration"
input ENUM_ARM_MODE   ArmMode     = ARM_SQUARES;     // Predict arms on
input double          PredBuf     = 100;             // Predict buffer, pts (+ past the cross, - earlier)
input bool            CatchUp     = true;            // Catch missed crosses at candle close
input double          MaxChase    = 0;               // Catch-up: max chase from cross price, pts (0 = no limit)
input group "S1c. CONT entry"
input ENUM_CONT_ENTRY ContEntry   = CONT_AT_CLOSE;   // CONT entry timing
input double          ContStopBuf = 50;              // CONT stop buffer, pts past the candle
input int             ContStopBars= 3;               // CONT stop valid for N bars, then cancel
input group "S2. Exits"
input ENUM_EXIT_UNIT  ExitUnit    = EXIT_POINTS;     // SL / TP / trail unit
input double          SlPts       = 7000;            // Stop loss, pts (Points mode, 0 = none)
input double          TpPts       = 50000;           // Take profit, pts (Points mode, 0 = none)
input int             ExAtrLen    = 14;              // ATR length (ATR mode)
input double          SlAtrM      = 2.0;             // Stop loss, ATR mult (ATR mode)
input double          TpR         = 2.0;             // Take profit, R multiple of SL (ATR mode)
input bool            TrailOn     = true;            // Trailing stop
input double          TrActPts    = 1000;            // Trail activation, pts of profit (Points mode)
input double          TrDisPts    = 100;             // Trail distance, pts (Points mode)
input double          TrActAtr    = 4.0;             // Trail activation, ATR mult (ATR mode)
input double          TrDisAtr    = 0.2;             // Trail distance, ATR mult (ATR mode)
input int             TimeStop    = 0;               // Time stop, bars (0 = off)
input group "S3. Sizing"
input ENUM_QTY_MODE   QtyMode     = QTY_RISK;        // Quantity
input double          LotsFixed   = 0.10;            // Fixed lots
input double          RiskPct     = 1.0;             // Risk % of equity per trade (Risk mode)
input double          LotsMax     = 5.0;             // Max lots
input bool            MarginCap   = true;            // Cap lots to free margin
input group "S4. Engine"
input string          IndicatorName = "XPW_ShapeMap"; // Indicator file name (in MQL5\Indicators)
input long            Magic       = 90907;           // Magic number
input int             SlippagePts = 30;              // Max slippage, pts
input bool            ShowMap     = true;            // Draw the map (boxes, arrows) in the tester
input bool            Diagnostics = true;            // Print signal counts and skipped-entry reasons to the Experts log
//--- indicator inputs, SAME ORDER as in XPW_ShapeMap.mq5
input group "TDI"
input int    RsiLen      = 14;
input int    FastLen     = 2;
input int    SlowLen     = 7;
input bool   InvertFill  = true;
input group "Areas"
input int    AreaLook    = 20;
input double LoFrac      = 0.20;
input double HiFrac      = 0.67;
input group "Label ALL opportunities"
input bool   AllOn       = true;
input int    AllCtx      = 1;
input group "BOTTOM square"
input bool   BotOn       = true;
input int    BotMinW     = 1;
input int    BotMaxW     = 3;
input int    BotCtxIn    = 2;
input bool   BotNeedLow  = true;
input int    BotSepIn    = 5;
input group "TOP square"
input bool   TopOn       = true;
input int    TopMinW     = 1;
input int    TopMaxW     = 2;
input int    TopCtxIn    = 3;
input bool   TopNeedHigh = true;
input int    TopSepIn    = 5;
input group "Turn mark"
input bool   TurnOn      = true;
input int    TurnMax     = 12;
input int    TurnHold    = 2;
input group "Ticks"
input bool   TickOn      = true;
input int    AtrLen      = 14;
input double BotWickRange= 0.55;
input double BotWickAtr  = 0.8;
input double TopWickRange= 0.70;
input double TopWickAtr  = 1.20;
input group "CONT"
input bool   ContOn      = true;
input double ContBigAtr  = 1.0;
input int    ContLook    = 30;
input bool   ContNeedRed = true;
input int    ContRedMax  = 12;
input double ContPinch   = 1.0;
input int    ContAfter   = 6;
input int    ContSep     = 5;
input bool   ContMirror  = true;

//--- indicator buffer indexes (see the indicator header)
#define B_FAST     2
#define B_SLOW     3
#define B_BOTSQ    10
#define B_TOPSQ    11
#define B_TURNUP   12
#define B_TURNDN   13
#define B_BOTTICK  14
#define B_TOPTICK  15
#define B_CONTUP   16
#define B_CONTDN   17
#define B_CROSSUP  18
#define B_CROSSDN  19
#define B_ARML     20
#define B_ARMS     21
#define B_PREDICT  22
#define B_ATR      24

CTrade   trade;
int      hMap = INVALID_HANDLE, hAtr = INVALID_HANDLE;
datetime g_lastBar = 0;           // time of the current bar
datetime g_lastEntryBar = 0;      // bar on which the last entry was sent
datetime g_contStopBar = 0;       // bar on which a CONT stop order was placed
int      g_contStopDir = 0;
double   g_tick, g_point;
int      g_digits;

//+------------------------------------------------------------------+
int OnInit()
  {
   hMap = iCustom(_Symbol, _Period, IndicatorName,
                  RsiLen, FastLen, SlowLen, InvertFill,
                  AreaLook, LoFrac, HiFrac,
                  AllOn, AllCtx,
                  BotOn, BotMinW, BotMaxW, BotCtxIn, BotNeedLow, BotSepIn,
                  TopOn, TopMinW, TopMaxW, TopCtxIn, TopNeedHigh, TopSepIn,
                  TurnOn, TurnMax, TurnHold,
                  TickOn, AtrLen, BotWickRange, BotWickAtr, TopWickRange, TopWickAtr,
                  ContOn, ContBigAtr, ContLook, ContNeedRed, ContRedMax, ContPinch, ContAfter, ContSep, ContMirror,
                  EnterOnTick,                       // PreviewFormingBar
                  ShowMap, ShowMap, ShowMap, ShowMap, // ShowBoxes, ShowTurns, ShowTicks, ShowCont
                  false);                            // ShowPanel (the EA has its own)
   if(hMap == INVALID_HANDLE) { Print("XPW EA: cannot load indicator ", IndicatorName); return INIT_FAILED; }
   hAtr = iATR(_Symbol, _Period, ExAtrLen);
   if(hAtr == INVALID_HANDLE) return INIT_FAILED;
   if(ShowMap && !MQLInfoInteger(MQL_TESTER)) ChartIndicatorAdd(0, (int)ChartGetInteger(0, CHART_WINDOWS_TOTAL), hMap);
   trade.SetExpertMagicNumber(Magic);
   trade.SetDeviationInPoints(SlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_tick   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_point  = _Point;
   g_digits = _Digits;
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason) { Comment(""); }
//+------------------------------------------------------------------+
//| helpers                                                          |
//+------------------------------------------------------------------+
double Buf(const int idx, const int shift)
  {
   double a[1];
   if(CopyBuffer(hMap, idx, shift, 1, a) != 1) return 0.0;
   return a[0];
  }
bool BufOn(const int idx, const int shift) { return Buf(idx, shift) > 0.5; }
double AtrNow(const int shift)
  {
   double a[1];
   if(CopyBuffer(hAtr, 0, shift, 1, a) != 1) return 0.0;
   return a[0];
  }
double NormPrice(const double p) { return NormalizeDouble(MathRound(p / g_tick) * g_tick, g_digits); }
double Ask() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK); }
double Bid() { return SymbolInfoDouble(_Symbol, SYMBOL_BID); }
double StopsLevel() { return SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * g_point; }

// signed position volume for this symbol + magic (hedging: sum of both sides)
double PosVolume(ulong &ticket)
  {
   double v = 0; ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic) continue;
      double vol = PositionGetDouble(POSITION_VOLUME);
      v += (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? vol : -vol;
      ticket = t;
     }
   return v;
  }
double Pos() { ulong t; return PosVolume(t); }
int BarsHeld()      // bars since the position was opened, Pine style (0 = opened on the bar that just closed)
  {
   ulong t; if(PosVolume(t) == 0 || t == 0) return 0;
   PositionSelectByTicket(t);
   datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
   return MathMax(iBarShift(_Symbol, _Period, ot) - 1, 0);
  }
void CloseAll(const string why)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic) continue;
      trade.PositionClose(t);
     }
   Print("XPW EA close: ", why);
  }
// pending orders of this EA: type filter (ORDER_TYPE_BUY_STOP / ORDER_TYPE_SELL_STOP / -1 all)
ulong FindPending(const int type)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !OrderSelect(t)) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != Magic) continue;
      if(type < 0 || OrderGetInteger(ORDER_TYPE) == type) return t;
     }
   return 0;
  }
void DeletePending(const int type)
  {
   ulong t;
   while((t = FindPending(type)) != 0) { if(!trade.OrderDelete(t)) break; }
  }
// hedging accounts: a reversing stop order leaves two opposite positions -> keep the newest
void ReconcileHedge()
  {
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return;
   ulong newest = 0; datetime tn = 0; int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic) continue;
      n++;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(ot >= tn) { tn = ot; newest = t; }
     }
   if(n < 2) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || t == newest || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic) continue;
      trade.PositionClose(t);
     }
  }
//+------------------------------------------------------------------+
//| exits distances (price units) and lot sizing                     |
//+------------------------------------------------------------------+
double SlDist()
  {
   if(ExitUnit == EXIT_POINTS) return SlPts * g_point;
   return SlAtrM * AtrNow(EnterOnTick ? 0 : 1);
  }
double TpDist(const double sl)
  {
   if(ExitUnit == EXIT_POINTS) return TpPts * g_point;
   return TpR * sl;
  }
double TrAct()
  {
   if(ExitUnit == EXIT_POINTS) return TrActPts * g_point;
   return TrActAtr * AtrNow(1);
  }
double TrDis()
  {
   if(ExitUnit == EXIT_POINTS) return TrDisPts * g_point;
   return TrDisAtr * AtrNow(1);
  }
double CalcLots(const double slDist)
  {
   double lots = LotsFixed;
   if(QtyMode == QTY_RISK)
     {
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tv <= 0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tv <= 0) tv = g_tick * SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);   // USD-quoted fallback
      double lossPerLot = (g_tick > 0 && slDist > 0) ? slDist / g_tick * tv : 0;
      lots = lossPerLot > 0 ? AccountInfoDouble(ACCOUNT_EQUITY) * RiskPct / 100.0 / lossPerLot : 0;
      if(lots <= 0 && Diagnostics)
         Print("XPW EA sizing: lots=0  equity=", AccountInfoDouble(ACCOUNT_EQUITY), " slDist=", slDist, " tickValue=", tv, " tickSize=", g_tick);
     }
   lots = MathMin(lots, LotsMax);
   if(MarginCap)
     {
      double m = 0;
      if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, 1.0, Ask(), m) && m > 0)
         lots = MathMin(lots, 0.95 * AccountInfoDouble(ACCOUNT_MARGIN_FREE) / m);
     }
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0) lots = MathFloor(lots / step) * step;
   lots = MathMin(lots, vmax);
   if(lots < vmin)
     {
      if(Diagnostics) Print("XPW EA sizing: lots ", lots, " below min volume ", vmin, " (risk ", RiskPct, "%, slDist ", slDist, ", margin cap ", MarginCap, ")");
      return 0.0;
     }
   return NormalizeDouble(lots, 8);
  }
//+------------------------------------------------------------------+
//| orders                                                           |
//+------------------------------------------------------------------+
bool MarketEnter(const bool isLong, const string cmt)
  {
   double sl = SlDist(), tp = TpDist(sl);
   double lots = CalcLots(sl);
   if(lots <= 0) { Print("XPW EA: lots = 0, entry skipped"); return false; }
   double pos = Pos();
   // netting: add the opposite volume so the order reverses in one deal
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      if(isLong && pos < 0) lots += -pos;
      if(!isLong && pos > 0) lots += pos;
     }
   else if((isLong && pos < 0) || (!isLong && pos > 0)) CloseAll("reverse");
   double px = isLong ? Ask() : Bid();
   double slp = sl > 0 ? NormPrice(isLong ? px - sl : px + sl) : 0;
   double tpp = tp > 0 ? NormPrice(isLong ? px + tp : px - tp) : 0;
   bool ok = isLong ? trade.Buy(lots, _Symbol, 0, slp, tpp, cmt) : trade.Sell(lots, _Symbol, 0, slp, tpp, cmt);
   if(ok) g_lastEntryBar = iTime(_Symbol, _Period, 0);
   else Print("XPW EA: order failed ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   return ok;
  }
// stop order at price; if price is already passed, enter at market
bool StopEnter(const bool isLong, double price, const string cmt)
  {
   price = NormPrice(price);
   double sl = SlDist(), tp = TpDist(sl);
   double lots = CalcLots(sl);
   if(lots <= 0) return false;
   double pos = Pos();
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
     {
      if(isLong && pos < 0) lots += -pos;
      if(!isLong && pos > 0) lots += pos;
     }
   double lvl = StopsLevel();
   if(isLong ? price <= Ask() + lvl : price >= Bid() - lvl)
      return MarketEnter(isLong, cmt + " mkt");
   double slp = sl > 0 ? NormPrice(isLong ? price - sl : price + sl) : 0;
   double tpp = tp > 0 ? NormPrice(isLong ? price + tp : price - tp) : 0;
   ulong ex = FindPending(isLong ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP);
   if(ex != 0)
     {
      OrderSelect(ex);
      if(MathAbs(OrderGetDouble(ORDER_PRICE_OPEN) - price) < g_tick / 2) return true;   // already there
      return trade.OrderModify(ex, price, slp, tpp, ORDER_TIME_GTC, 0);
     }
   bool ok = isLong ? trade.BuyStop(lots, price, _Symbol, slp, tpp, ORDER_TIME_GTC, 0, cmt)
                    : trade.SellStop(lots, price, _Symbol, slp, tpp, ORDER_TIME_GTC, 0, cmt);
   if(!ok) Print("XPW EA: stop order failed ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   return ok;
  }
//+------------------------------------------------------------------+
//| trailing stop, fail exit, time stop                              |
//+------------------------------------------------------------------+
void ManageExits(const bool newBar)
  {
   ulong t; double pos = PosVolume(t);
   if(pos == 0 || t == 0) return;
   PositionSelectByTicket(t);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl   = PositionGetDouble(POSITION_SL);
   double tp   = PositionGetDouble(POSITION_TP);
   bool isLong = pos > 0;
   if(TrailOn)
     {
      double act = TrAct(), dis = TrDis();
      if(dis > 0)
        {
         if(isLong)
           {
            double b = Bid();
            if(b - open >= act)
              {
               double ns = NormPrice(b - dis);
               if(ns > sl + g_tick / 2 && ns < b - StopsLevel()) trade.PositionModify(t, ns, tp);
              }
           }
         else
           {
            double a = Ask();
            if(open - a >= act)
              {
               double ns = NormPrice(a + dis);
               if((sl == 0 || ns < sl - g_tick / 2) && ns > a + StopsLevel()) trade.PositionModify(t, ns, tp);
              }
           }
        }
     }
   if(!newBar) return;
   int held = BarsHeld();
   if(FailExit && SigMode == SIG_TURN && (TurnEntry == TURN_PREDICT || TurnEntry == TURN_AT_CROSS) && held <= TurnHold)
     {
      double f = Buf(B_FAST, 1), s = Buf(B_SLOW, 1);
      if(isLong && f <= s) CloseAll("cross failed");
      if(!isLong && f >= s) CloseAll("cross failed");
     }
   if(TimeStop > 0 && held >= TimeStop) CloseAll("time stop");
  }
//+------------------------------------------------------------------+
//| Turn PREDICT: stop orders at the next-bar cross price            |
//+------------------------------------------------------------------+
void PredictLogic()
  {
   double px = Buf(B_PREDICT, 1);
   bool valid = px != EMPTY_VALUE && px > 0;
   double f = Buf(B_FAST, 1), s = Buf(B_SLOW, 1);
   bool armL = TurnOn && (ArmMode == ARM_EVERY || BufOn(B_ARML, 1));
   bool armS = TurnOn && (ArmMode == ARM_EVERY || BufOn(B_ARMS, 1));
   bool canLong = TradeDir != DIR_SHORT, canShort = TradeDir != DIR_LONG;
   double pos = Pos();
   double stopL = valid ? MathCeil((px + PredBuf * g_point) / g_tick) * g_tick : 0;
   double stopS = valid ? MathFloor((px - PredBuf * g_point) / g_tick) * g_tick : 0;
   bool wantL = armL && f < s && canLong && valid && pos <= 0 && (pos == 0 || OppMode == OPP_REVERSE);
   bool wantS = armS && f > s && canShort && valid && pos >= 0 && (pos == 0 || OppMode == OPP_REVERSE);
   if(wantL) { if(!StopEnter(true, stopL, "L predict") && Diagnostics) Print("XPW EA predict: buy stop at ", DoubleToString(stopL, g_digits), " not placed"); }
   else DeletePending(ORDER_TYPE_BUY_STOP);
   if(wantS) { if(!StopEnter(false, stopS, "S predict") && Diagnostics) Print("XPW EA predict: sell stop at ", DoubleToString(stopS, g_digits), " not placed"); }
   else DeletePending(ORDER_TYPE_SELL_STOP);
   // catch-up: the lines crossed at this close but no stop filled -> enter now
   bool enteredThisBar = (g_lastEntryBar == iTime(_Symbol, _Period, 1)) || (g_lastEntryBar == iTime(_Symbol, _Period, 0));
   if(CatchUp && !enteredThisBar)
     {
      bool cu = BufOn(B_CROSSUP, 1), cd = BufOn(B_CROSSDN, 1);
      double pxPrev = Buf(B_PREDICT, 2);
      double close1 = iClose(_Symbol, _Period, 1);
      bool okL = MaxChase <= 0 || pxPrev == EMPTY_VALUE || close1 - (pxPrev + PredBuf * g_point) <= MaxChase * g_point;
      bool okS = MaxChase <= 0 || pxPrev == EMPTY_VALUE || (pxPrev - PredBuf * g_point) - close1 <= MaxChase * g_point;
      if(cu && armL && canLong && okL && (pos == 0 || (pos < 0 && OppMode == OPP_REVERSE)))
        { DeletePending(-1); MarketEnter(true, "L cross"); }
      else if(cd && armS && canShort && okS && (pos == 0 || (pos > 0 && OppMode == OPP_REVERSE)))
        { DeletePending(-1); MarketEnter(false, "S cross"); }
     }
   if(OppMode == OPP_CLOSE)
     {
      if(pos < 0 && armL && BufOn(B_CROSSUP, 1)) CloseAll("opp signal");
      if(pos > 0 && armS && BufOn(B_CROSSDN, 1)) CloseAll("opp signal");
     }
  }
//+------------------------------------------------------------------+
//| CONT "stop past signal candle"                                   |
//+------------------------------------------------------------------+
void ContStopLogic()
  {
   bool cu = BufOn(B_CONTUP, 1), cd = BufOn(B_CONTDN, 1);
   bool canLong = TradeDir != DIR_SHORT, canShort = TradeDir != DIR_LONG;
   double pos = Pos();
   if(pos != 0) g_contStopDir = 0;
   if(cu && canLong && (pos == 0 || (pos < 0 && OppMode == OPP_REVERSE)))
     {
      DeletePending(ORDER_TYPE_SELL_STOP);
      if(StopEnter(true, iHigh(_Symbol, _Period, 1) + ContStopBuf * g_point, "L CONT stop")) { g_contStopBar = iTime(_Symbol, _Period, 1); g_contStopDir = 1; }
     }
   else if(cd && canShort && (pos == 0 || (pos > 0 && OppMode == OPP_REVERSE)))
     {
      DeletePending(ORDER_TYPE_BUY_STOP);
      if(StopEnter(false, iLow(_Symbol, _Period, 1) - ContStopBuf * g_point, "S CONT stop")) { g_contStopBar = iTime(_Symbol, _Period, 1); g_contStopDir = -1; }
     }
   else if(g_contStopDir != 0 && iBarShift(_Symbol, _Period, g_contStopBar) - 1 >= ContStopBars)
     {
      DeletePending(-1);
      g_contStopDir = 0;
     }
   if(OppMode == OPP_CLOSE)
     {
      if(pos > 0 && cd) CloseAll("opp signal");
      if(pos < 0 && cu) CloseAll("opp signal");
     }
  }
//+------------------------------------------------------------------+
//| diagnostics: once, count every signal the indicator holds        |
//+------------------------------------------------------------------+
void SelfTest()
  {
   static bool done = false;
   if(done) return;
   int bars = Bars(_Symbol, _Period);
   double a[];
   int got = CopyBuffer(hMap, B_FAST, 0, bars, a);
   if(got <= 0)
     {
      Print("XPW EA self-test: CopyBuffer from ", IndicatorName, " FAILED, error ", GetLastError(), ". Is the indicator compiled and in MQL5\\Indicators? Will retry next tick.");
      return;
     }
   done = true;
   string names[8] = {"BOT sq", "TOP sq", "Turn up", "Turn dn", "BOT tick", "TOP tick", "CONT up", "CONT dn"};
   string txt = "XPW EA self-test on " + _Symbol + " " + EnumToString(_Period) + ", " + (string)bars + " bars, point " + DoubleToString(g_point, g_digits) + ", tick value " + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), 4) + ", min lot " + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), 2) + ": ";
   for(int b = 0; b < 8; b++)
     {
      int n = 0;
      if(CopyBuffer(hMap, B_BOTSQ + b, 0, bars, a) > 0) for(int i = 0; i < ArraySize(a); i++) if(a[i] > 0.5) n++;
      txt += names[b] + " " + (string)n + (b < 7 ? ", " : "");
     }
   Print(txt);
   Print("XPW EA mode: SigMode=", EnumToString(SigMode), " TurnEntry=", EnumToString(TurnEntry), " TradeDir=", EnumToString(TradeDir), " EnterOnTick=", EnterOnTick, " SL pts=", SlPts, " (", DoubleToString(SlPts * g_point, g_digits), " price)  lots now=", CalcLots(SlDist()));
  }
void DiagBar()
  {
   if(!Diagnostics) return;
   bool any = false;
   for(int b = 0; b < 8; b++) if(BufOn(B_BOTSQ + b, 1)) any = true;
   if(!any && !BufOn(B_CROSSUP, 1) && !BufOn(B_CROSSDN, 1)) return;
   Print("XPW EA bar ", TimeToString(iTime(_Symbol, _Period, 1)), " sig: BOTsq=", BufOn(B_BOTSQ, 1), " TOPsq=", BufOn(B_TOPSQ, 1), " turnUp=", BufOn(B_TURNUP, 1), " turnDn=", BufOn(B_TURNDN, 1),
         " contUp=", BufOn(B_CONTUP, 1), " contDn=", BufOn(B_CONTDN, 1), " crossUp=", BufOn(B_CROSSUP, 1), " crossDn=", BufOn(B_CROSSDN, 1), " armL=", BufOn(B_ARML, 1), " armS=", BufOn(B_ARMS, 1),
         " pos=", Pos(), " pending=", FindPending(-1) != 0, " predict=", DoubleToString(Buf(B_PREDICT, 1), g_digits));
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime t0 = iTime(_Symbol, _Period, 0);
   bool newBar = (t0 != g_lastBar);
   if(newBar) g_lastBar = t0;
   if(Diagnostics) SelfTest();
   if(newBar) DiagBar();
   ReconcileHedge();
   ManageExits(newBar);

   bool turnPredict = SigMode == SIG_TURN && TurnEntry == TURN_PREDICT;
   bool turnAtCross = SigMode == SIG_TURN && TurnEntry == TURN_AT_CROSS;
   bool contStop    = SigMode == SIG_CONT && ContEntry == CONT_STOP;

   if(turnPredict) { if(newBar) PredictLogic(); Panel(); return; }
   if(contStop)    { if(newBar) ContStopLogic(); Panel(); return; }

   // market signals: closed bar (shift 1, once per new bar) or forming bar (shift 0, every tick)
   int shift = EnterOnTick ? 0 : 1;
   if(!EnterOnTick && !newBar) { Panel(); return; }
   bool longSig = false, shortSig = false;
   switch(SigMode)
     {
      case SIG_SQUARE: longSig = BufOn(B_BOTSQ, shift);   shortSig = BufOn(B_TOPSQ, shift);   break;
      case SIG_TURN:   if(turnAtCross) { longSig = BufOn(B_ARML, shift) && BufOn(B_CROSSUP, shift); shortSig = BufOn(B_ARMS, shift) && BufOn(B_CROSSDN, shift); }
                       else            { longSig = BufOn(B_TURNUP, shift); shortSig = BufOn(B_TURNDN, shift); }
                       break;
      case SIG_TICK:   longSig = BufOn(B_BOTTICK, shift); shortSig = BufOn(B_TOPTICK, shift); break;
      case SIG_CONT:   longSig = BufOn(B_CONTUP, shift);  shortSig = BufOn(B_CONTDN, shift);  break;
     }
   if(longSig && shortSig) { longSig = false; shortSig = false; }   // both on one bar = no direction
   bool canLong = TradeDir != DIR_SHORT, canShort = TradeDir != DIR_LONG;
   datetime sigBar = iTime(_Symbol, _Period, shift);
   bool already = (g_lastEntryBar == sigBar);     // one entry per signal bar
   double pos = Pos();
   if(longSig && !already)
     {
      if(pos < 0)
        {
         if(OppMode == OPP_REVERSE && canLong) MarketEnter(true, "L sig");
         else if(OppMode != OPP_IGNORE) CloseAll("opp signal");
        }
      else if(pos == 0 && canLong) MarketEnter(true, "L sig");
     }
   if(shortSig && !already)
     {
      if(pos > 0)
        {
         if(OppMode == OPP_REVERSE && canShort) MarketEnter(false, "S sig");
         else if(OppMode != OPP_IGNORE) CloseAll("opp signal");
        }
      else if(pos == 0 && canShort) MarketEnter(false, "S sig");
     }
   Panel();
  }
//+------------------------------------------------------------------+
void Panel()
  {
   static int n = 0;
   if(++n % 20 != 1 && !MQLInfoInteger(MQL_TESTER)) return;
   string mode = SigMode == SIG_SQUARE ? "BOT/TOP square" : SigMode == SIG_TURN ? "Turn" : SigMode == SIG_TICK ? "BOT/TOP tick" : "CONT";
   string txt = "XPW Shape Map v0.9 EA   " + mode + " / " + (TradeDir == DIR_BOTH ? "Both" : TradeDir == DIR_LONG ? "Long only" : "Short only") + "\n";
   txt += "Position " + DoubleToString(Pos(), 2) + "   lots now " + DoubleToString(CalcLots(SlDist()), 2) + "   equity " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n";
   txt += "Fast " + DoubleToString(Buf(B_FAST, 0), 2) + "  Slow " + DoubleToString(Buf(B_SLOW, 0), 2) + "  predict " + DoubleToString(Buf(B_PREDICT, 0), g_digits) + "\n";
   Comment(txt);
  }
//+------------------------------------------------------------------+
