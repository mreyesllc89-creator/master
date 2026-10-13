//+------------------------------------------------------------------+
//|                                                 FlashGold_v5.mq5 |
//|  MQL5 port of pine/FlashGold_v5_Strategy_*.pine  -  STEP 1       |
//|                                                                  |
//|  Step 1 (this file): symbol presets with the calibrated defaults  |
//|  (CALIBRATION.md section 17), TDI direction on the chart and on   |
//|  higher-timeframe child zones read from their last CLOSED bar,    |
//|  burst gate / any-combo / prior drift / entry hold / one entry    |
//|  per bar exactly as the Pine strategy, pending BuyStop / SellStop |
//|  at Ask + distance / Bid - distance with attached SL and TP,      |
//|  pending lifetime in bars, OCA, reversal on the opposite signal   |
//|  (netting and hedging accounts), server-side trailing stop after  |
//|  activation, time stop, fixed or risk-percent lots, panel.        |
//|  Step 2: commission referee against the deal history, session     |
//|  filter, Points unit for the thresholds, alerts.                  |
//|                                                                  |
//|  Decisions once per bar on the CLOSED bar (Pine: bar close).      |
//|  Orders rest on the server and fill on ticks. The trailing stop   |
//|  is moved on every tick once activated.                           |
//+------------------------------------------------------------------+
#property copyright "XPW / FlashGold port"
#property version   "0.10"
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>

//============== INPUTS ==============//
enum ENUM_FG_PRESET   { FG_XAUUSD = 0, FG_SPX500 = 1, FG_BTCUSD = 2, FG_CUSTOM = 3 };
enum ENUM_FG_ZONEMODE { ZONES_PRESET = 0, ZONES_MANUAL = 1 };
enum ENUM_FG_DIR      { DIR_BOTH = 0, DIR_LONG = 1, DIR_SHORT = 2 };

input group "1. Symbol preset"
input ENUM_FG_PRESET InpPreset     = FG_XAUUSD;   // Preset (calibrated defaults; 0 / -1 inputs below take the preset value)
input long           InpMagic      = 220001;      // Magic number
input int            InpDeviation  = 50;          // Max deviation, points

input group "2. FlashGold signal (ATR units, as calibrated)"
input bool   InpUseAnyCombo     = false;  // Allow any combo (parent alone may fire; calibrated OFF)
input double InpBurstAtr        = 0.0;    // Burst threshold, ATR mult (0 = preset)
input double InpEntryDistAtr    = 0.0;    // Entry distance, ATR mult (0 = preset)
input int    InpHoldBars        = -1;     // Entry hold bars (-1 = preset)
input double InpHoldFavAtr      = 0.10;   // Hold min favourable move, ATR mult
input bool   InpOneEntryPerBar  = true;   // One entry per bar
input bool   InpUsePriorFilter  = false;  // Use prior drift filter
input int    InpPriorDriftBars  = 60;     // Prior drift bars
input int    InpAtrLen          = 14;     // ATR length

input group "3. TDI trade-zone filter"
input int    InpRsiLen          = 14;     // TDI RSI length
input int    InpFastLen         = 2;      // TDI fast SMA length
input int    InpMinAligned      = 0;      // Minimum child zones aligned (0 = preset)
input bool   InpAllowNeutralParent = false; // Allow trade if parent is flat
input ENUM_FG_ZONEMODE InpZoneMode = ZONES_PRESET; // Zones: preset multiples of the chart TF, or the manual list below
input bool   InpUseZone1        = true;   // Manual: use zone 1
input ENUM_TIMEFRAMES InpZoneTf1 = PERIOD_CURRENT; // Manual: zone 1 timeframe
input bool   InpUseZone2        = true;   // Manual: use zone 2
input ENUM_TIMEFRAMES InpZoneTf2 = PERIOD_H2;      // Manual: zone 2 timeframe
input bool   InpUseZone3        = true;   // Manual: use zone 3
input ENUM_TIMEFRAMES InpZoneTf3 = PERIOD_H4;      // Manual: zone 3 timeframe
input bool   InpUseZone4        = false;  // Manual: use zone 4
input ENUM_TIMEFRAMES InpZoneTf4 = PERIOD_H8;      // Manual: zone 4 timeframe
input bool   InpUseZone5        = false;  // Manual: use zone 5
input ENUM_TIMEFRAMES InpZoneTf5 = PERIOD_M1;      // Manual: zone 5 timeframe
input bool   InpUseZone6        = false;  // Manual: use zone 6
input ENUM_TIMEFRAMES InpZoneTf6 = PERIOD_M2;      // Manual: zone 6 timeframe

input group "4. Orders and exits"
input ENUM_FG_DIR InpDirection  = DIR_BOTH; // Direction
input int    InpValidBars       = 3;      // Cancel unfilled entry after N bars (0 = keep)
input bool   InpAllowReverse    = true;   // Opposite signal may reverse an open position
input bool   InpExitOnOpposite  = false;  // Close at market on the opposite signal
input double InpSlAtr           = 0.0;    // Stop loss, ATR mult (0 = preset)
input double InpTpR             = 0.0;    // Take profit, R multiple of SL (0 = preset)
input bool   InpUseTrail        = true;   // Trailing stop (calibrated ON)
input double InpTrailActAtr     = 1.0;    // Trail activation, ATR mult of profit
input double InpTrailDstAtr     = 0.75;   // Trail distance, ATR mult
input int    InpMaxBarsHeld     = 0;      // Time stop, bars (0 = off)

input group "5. Sizing"
input double InpLots            = 0.0;    // Fixed lots (0 = preset 0.10)
input double InpRiskPct         = 0.0;    // Risk % of equity per trade (0 = fixed lots)
input double InpMaxLots         = 1.0;    // Max lots

input group "6. Display"
input bool   InpShowPanel       = true;   // Status panel (Comment)
input bool   InpVerbose         = true;   // Log decisions to the Experts tab

//============== STATE ==============//
CTrade        trade;
CPositionInfo posInfo;

int      atrHandle = INVALID_HANDLE;
int      rsiChart  = INVALID_HANDLE;
int      rsiZone[6];
ENUM_TIMEFRAMES zoneTf[6];
bool     zoneUse[6];
datetime lastBarTime = 0;
long     barCounter  = 0;                 // closed-bar counter (Pine bar_index analogue)

// preset values
string   pName; double pSpread, pCommLot, pLots, pBurst, pDist, pSl, pTpR; int pHold, pMinAligned; int pMults[4]; int pNMults;
ENUM_TIMEFRAMES pChartTf;

// closed-bar values
double   atrRef = 0, lastClose = 0, burstNow = 0;
int      parentDir = 0, alignedZones = 0, activeZones = 0, conflictZones = 0;
bool     buySignal = false, sellSignal = false, buyAllowed = false, sellAllowed = false;

// entry hold
bool     holdActive = false, holdIsBuy = false; long holdBar = -1; double holdMid = 0;
long     lastEntryBar = -1;

// pending bookkeeping (bar counter at placement, trail distances locked at placement)
long     placedBarL = -1, placedBarS = -1;
double   pendActL = 0, pendDstL = 0, pendActS = 0, pendDstS = 0;
// open position bookkeeping
double   posAct = 0, posDst = 0, posExt = 0; bool posTrailOn = false; ulong posTicketSeen = 0; datetime posOpenTime = 0;

//+------------------------------------------------------------------+
//| Presets (CALIBRATION.md section 17)                              |
//+------------------------------------------------------------------+
const int TF_MINS[] = {1,2,3,4,5,6,10,12,15,20,30,60,120,180,240,360,480,720,1440,10080,43200};
const ENUM_TIMEFRAMES TF_LIST[] = {PERIOD_M1,PERIOD_M2,PERIOD_M3,PERIOD_M4,PERIOD_M5,PERIOD_M6,PERIOD_M10,PERIOD_M12,PERIOD_M15,PERIOD_M20,PERIOD_M30,
                                   PERIOD_H1,PERIOD_H2,PERIOD_H3,PERIOD_H4,PERIOD_H6,PERIOD_H8,PERIOD_H12,PERIOD_D1,PERIOD_W1,PERIOD_MN1};
ENUM_TIMEFRAMES TfFromMinutes(int m)
{
   // nearest MT5 timeframe at or above m minutes
   for(int i = 0; i < ArraySize(TF_MINS); i++) if(TF_MINS[i] >= m) return TF_LIST[i];
   return PERIOD_MN1;
}

void ResolvePreset()
{
   // VT Markets figures from the account holder; SPX spread is the 0.5 point placeholder
   pNMults = 0;
   switch(InpPreset)
   {
      case FG_XAUUSD:
         pName = "XAUUSD"; pSpread = 0.25; pCommLot = 0.6; pLots = 0.10; pChartTf = PERIOD_H1;
         pBurst = 0.5; pDist = 0.25; pHold = 0; pSl = 2.0; pTpR = 2.0; pMinAligned = 2;
         pMults[0] = 1; pMults[1] = 2; pMults[2] = 4; pNMults = 3;
         break;
      case FG_SPX500:
         pName = "SPX500"; pSpread = 0.5; pCommLot = 0.0; pLots = 0.10; pChartTf = PERIOD_M15;
         pBurst = 0.5; pDist = 0.25; pHold = 3; pSl = 3.0; pTpR = 1.5; pMinAligned = 1;
         pMults[0] = 1; pNMults = 1;
         break;
      case FG_BTCUSD:
         pName = "BTCUSD"; pSpread = 21.0; pCommLot = 0.0; pLots = 0.10; pChartTf = PERIOD_H1;
         pBurst = 0.25; pDist = 0.25; pHold = 0; pSl = 3.0; pTpR = 1.0; pMinAligned = 3;
         pMults[0] = 1; pMults[1] = 2; pMults[2] = 4; pMults[3] = 8; pNMults = 4;
         break;
      default:
         pName = "Custom"; pSpread = 0; pCommLot = 0; pLots = 0.10; pChartTf = _Period;
         pBurst = 0.5; pDist = 0.25; pHold = 0; pSl = 2.0; pTpR = 2.0; pMinAligned = 2;
         pMults[0] = 1; pMults[1] = 2; pMults[2] = 4; pNMults = 3;
         break;
   }
   if(InpBurstAtr     > 0) pBurst = InpBurstAtr;
   if(InpEntryDistAtr > 0) pDist  = InpEntryDistAtr;
   if(InpHoldBars    >= 0) pHold  = InpHoldBars;
   if(InpSlAtr        > 0) pSl    = InpSlAtr;
   if(InpTpR          > 0) pTpR   = InpTpR;
   if(InpMinAligned   > 0) pMinAligned = InpMinAligned;
   if(InpLots         > 0) pLots  = InpLots;

   int chartMin = PeriodSeconds(_Period) / 60;
   for(int i = 0; i < 6; i++) { zoneUse[i] = false; zoneTf[i] = _Period; rsiZone[i] = INVALID_HANDLE; }
   if(InpZoneMode == ZONES_PRESET)
   {
      for(int i = 0; i < pNMults; i++) { zoneUse[i] = true; zoneTf[i] = pMults[i] == 1 ? _Period : TfFromMinutes(chartMin * pMults[i]); }
   }
   else
   {
      zoneUse[0] = InpUseZone1; zoneTf[0] = InpZoneTf1 == PERIOD_CURRENT ? _Period : InpZoneTf1;
      zoneUse[1] = InpUseZone2; zoneTf[1] = InpZoneTf2 == PERIOD_CURRENT ? _Period : InpZoneTf2;
      zoneUse[2] = InpUseZone3; zoneTf[2] = InpZoneTf3 == PERIOD_CURRENT ? _Period : InpZoneTf3;
      zoneUse[3] = InpUseZone4; zoneTf[3] = InpZoneTf4 == PERIOD_CURRENT ? _Period : InpZoneTf4;
      zoneUse[4] = InpUseZone5; zoneTf[4] = InpZoneTf5 == PERIOD_CURRENT ? _Period : InpZoneTf5;
      zoneUse[5] = InpUseZone6; zoneTf[5] = InpZoneTf6 == PERIOD_CURRENT ? _Period : InpZoneTf6;
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   ResolvePreset();
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviation);
   trade.SetTypeFillingBySymbol(_Symbol);
   atrHandle = iATR(_Symbol, _Period, InpAtrLen);
   rsiChart  = iRSI(_Symbol, _Period, InpRsiLen, PRICE_CLOSE);
   if(atrHandle == INVALID_HANDLE || rsiChart == INVALID_HANDLE) { Print("FG: indicator handle failed"); return INIT_FAILED; }
   string zl = "";
   for(int i = 0; i < 6; i++)
   {
      if(!zoneUse[i]) continue;
      rsiZone[i] = iRSI(_Symbol, zoneTf[i], InpRsiLen, PRICE_CLOSE);
      if(rsiZone[i] == INVALID_HANDLE) { PrintFormat("FG: iRSI on %s failed", EnumToString(zoneTf[i])); return INIT_FAILED; }
      zl += EnumToString(zoneTf[i]) + " ";
   }
   lastBarTime = 0; barCounter = 0;
   PrintFormat("FG step1 init: preset=%s chart=%s (calibrated on %s) zones=[%s] minAligned=%d burst=%.2f dist=%.2f hold=%d SL=%.2f ATR TP=%.2fR trail=%s lots=%.2f",
               pName, EnumToString(_Period), EnumToString(pChartTf), zl, pMinAligned, pBurst, pDist, pHold, pSl, pTpR, InpUseTrail ? "on" : "off", pLots);
   if(_Period != pChartTf && InpPreset != FG_CUSTOM)
      PrintFormat("FG WARNING: the %s preset was calibrated on %s; this chart is %s. The zone multiples follow the chart.", pName, EnumToString(pChartTf), EnumToString(_Period));
   PrintFormat("FG symbol: digits=%d point=%s contract=%.2f volmin=%.2f volstep=%.2f stoplevel=%d pts margin mode=%s",
               _Digits, DoubleToString(_Point,_Digits), SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
               (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), IsHedging() ? "hedging" : "netting");
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) Print("FG WARNING: trading is not allowed in the terminal (Algo Trading button)");
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) Print("FG WARNING: trading is not allowed for this EA (Allow Algo Trading in the EA settings)");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(atrHandle != INVALID_HANDLE) IndicatorRelease(atrHandle);
   if(rsiChart  != INVALID_HANDLE) IndicatorRelease(rsiChart);
   for(int i = 0; i < 6; i++) if(rsiZone[i] != INVALID_HANDLE) IndicatorRelease(rsiZone[i]);
   Comment("");
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
bool IsHedging() { return (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING; }
double NormPrice(double p) { return NormalizeDouble(p, _Digits); }

double NormLots(double lots)
{
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vstep <= 0) vstep = vmin;
   double v = MathFloor(lots / vstep + 1e-9) * vstep;
   v = MathMax(vmin, MathMin(MathMin(vmax, InpMaxLots), v));
   return NormalizeDouble(v, 8);
}

// our position on this symbol: ticket (0 = none), type, volume
ulong OurPosition(ENUM_POSITION_TYPE &type, double &vol)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE); vol = PositionGetDouble(POSITION_VOLUME);
      return t;
   }
   type = POSITION_TYPE_BUY; vol = 0; return 0;
}

ulong FindPending(ENUM_ORDER_TYPE type)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(t == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != InpMagic || OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == type) return t;
   }
   return 0;
}

void DeletePending(ENUM_ORDER_TYPE type, string why)
{
   ulong t = FindPending(type);
   if(t == 0) return;
   if(trade.OrderDelete(t)) { if(InpVerbose) PrintFormat("FG: deleted %s #%I64u (%s)", EnumToString(type), t, why); }
   else PrintFormat("FG: OrderDelete %I64u failed: %d %s", t, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   if(type == ORDER_TYPE_BUY_STOP) placedBarL = -1; else placedBarS = -1;
}

double MinStopDist()
{
   double stops = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return stops + spread + _Point;
}

// TDI direction from an RSI handle: fast SMA(len) of RSI on the last CLOSED bar versus the bar before.
// +1 rising, -1 falling, 0 flat, -99 = no data
int TdiDir(int handle)
{
   int need = InpFastLen + 1;
   double r[];
   if(CopyBuffer(handle, 0, 1, need, r) != need) return -99;          // shifts 1 .. need (oldest last after SetAsSeries)
   ArraySetAsSeries(r, true);
   double f0 = 0, f1 = 0;
   for(int k = 0; k < InpFastLen; k++) { f0 += r[k]; f1 += r[k + 1]; }
   if(f0 > f1) return 1;
   if(f0 < f1) return -1;
   return 0;
}

double LotsFor(double slDist)
{
   double lots = pLots;
   if(InpRiskPct > 0 && slDist > 0)
   {
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize > 0 && tickVal > 0)
      {
         double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
         double lossPerLot = slDist / tickSize * tickVal;
         if(lossPerLot > 0) lots = riskMoney / lossPerLot;
      }
   }
   return NormLots(lots);
}

//+------------------------------------------------------------------+
//| Closed-bar evaluation: the Pine script, line for line             |
//+------------------------------------------------------------------+
void OnClosedBar()
{
   barCounter++;
   double atrBuf[];
   if(CopyBuffer(atrHandle, 0, 1, 1, atrBuf) != 1) return;
   atrRef = atrBuf[0];
   if(atrRef <= 0) return;
   lastClose = iClose(_Symbol, _Period, 1);
   double prevClose = iClose(_Symbol, _Period, 2);
   burstNow = lastClose - prevClose;                       // mid - mid[1]; the constant half-spread cancels

   // ---- TDI parent and zones ----
   parentDir = TdiDir(rsiChart);
   if(parentDir == -99) return;
   int pside = parentDir > 0 ? 1 : parentDir < 0 ? -1 : 0;
   activeZones = 0; alignedZones = 0; conflictZones = 0;
   for(int i = 0; i < 6; i++)
   {
      if(!zoneUse[i]) continue;
      int d = (zoneTf[i] == _Period) ? parentDir : TdiDir(rsiZone[i]);
      if(d == -99) continue;                               // ignore zones without data
      activeZones++;
      if(pside != 0 && d == pside) alignedZones++;
      if(pside != 0 && d == -pside) conflictZones++;
   }
   int  required = MathMin(pMinAligned, activeZones);
   bool parentFlatAllowed = InpAllowNeutralParent && pside == 0;
   bool zoneReady = activeZones == 0 || alignedZones >= required;
   buyAllowed  = (pside == 1  || parentFlatAllowed) && zoneReady;
   sellAllowed = (pside == -1 || parentFlatAllowed) && zoneReady;

   // ---- burst / prior drift / candidates ----
   double bth = pBurst * atrRef;
   bool burstBuy = burstNow >= bth, burstSell = burstNow <= -bth;
   bool priorBuyOk = true, priorSellOk = true;
   if(InpUsePriorFilter)
   {
      double drift = lastClose - iClose(_Symbol, _Period, 1 + InpPriorDriftBars);
      priorBuyOk = drift > 0; priorSellOk = drift < 0;
   }
   bool buyC, sellC;
   if(InpUseAnyCombo) { buyC = buyAllowed && (burstBuy || pside == 1); sellC = sellAllowed && (burstSell || pside == -1); }
   else               { buyC = buyAllowed && burstBuy;                 sellC = sellAllowed && burstSell; }
   buyC = buyC && priorBuyOk; sellC = sellC && priorSellOk;

   // ---- entry hold / one entry per bar ----
   bool canFire = !InpOneEntryPerBar || lastEntryBar != barCounter;
   buySignal = false; sellSignal = false;
   double holdFav = InpHoldFavAtr * atrRef;
   if(buyC && canFire)
   {
      if(pHold == 0) { buySignal = true; lastEntryBar = barCounter; }
      else if(!holdActive) { holdActive = true; holdIsBuy = true; holdBar = barCounter; holdMid = lastClose; }
      else if(holdIsBuy && barCounter - holdBar >= pHold && lastClose - holdMid >= holdFav) { buySignal = true; lastEntryBar = barCounter; holdActive = false; }
   }
   if(sellC && canFire)
   {
      if(pHold == 0) { sellSignal = true; lastEntryBar = barCounter; }
      else if(!holdActive) { holdActive = true; holdIsBuy = false; holdBar = barCounter; holdMid = lastClose; }
      else if(!holdIsBuy && barCounter - holdBar >= pHold && holdMid - lastClose >= holdFav) { sellSignal = true; lastEntryBar = barCounter; holdActive = false; }
   }
   if(holdActive && ((holdIsBuy && !buyAllowed) || (!holdIsBuy && !sellAllowed))) holdActive = false;

   // ---- orders ----
   ENUM_POSITION_TYPE ptype; double pvol; ulong pt = OurPosition(ptype, pvol);
   bool inLong = pt != 0 && ptype == POSITION_TYPE_BUY, inShort = pt != 0 && ptype == POSITION_TYPE_SELL, flat = pt == 0;

   // stale pendings
   if(InpValidBars > 0)
   {
      if(placedBarL >= 0 && FindPending(ORDER_TYPE_BUY_STOP)  != 0 && barCounter - placedBarL >= InpValidBars) DeletePending(ORDER_TYPE_BUY_STOP,  "expired");
      if(placedBarS >= 0 && FindPending(ORDER_TYPE_SELL_STOP) != 0 && barCounter - placedBarS >= InpValidBars) DeletePending(ORDER_TYPE_SELL_STOP, "expired");
   }
   // time stop
   if(pt != 0 && InpMaxBarsHeld > 0)
   {
      int held = iBarShift(_Symbol, _Period, posOpenTime, false);
      if(held >= InpMaxBarsHeld) { if(trade.PositionClose(pt)) { if(InpVerbose) Print("FG: time stop"); } flat = true; inLong = inShort = false; pt = 0; }
   }
   // close on the opposite signal
   if(InpExitOnOpposite && pt != 0 && ((sellSignal && inLong) || (buySignal && inShort)))
   {
      if(trade.PositionClose(pt)) { if(InpVerbose) Print("FG: closed on opposite signal"); flat = true; inLong = inShort = false; pvol = 0; pt = 0; }
   }

   double slD = pSl * atrRef, tpD = slD * pTpR, dist = pDist * atrRef, minD = MinStopDist();
   if(slD < minD) slD = minD;
   if(tpD < minD) tpD = minD;
   double actD = InpUseTrail ? InpTrailActAtr * atrRef : 0.0, dstD = InpUseTrail ? MathMax(InpTrailDstAtr * atrRef, minD) : 0.0;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool allowL = InpDirection != DIR_SHORT, allowS = InpDirection != DIR_LONG;

   if(buySignal && allowL && !inLong && (flat || InpAllowReverse || InpExitOnOpposite))
   {
      double lots = LotsFor(slD);
      if(inShort && !IsHedging()) lots = NormLots(lots + pvol);          // netting: the fill must flip the position
      double px = NormPrice(MathMax(ask + dist, ask + minD));
      double sl = NormPrice(px - slD), tp = NormPrice(px + tpD);
      DeletePending(ORDER_TYPE_BUY_STOP, "re-placing");
      if(trade.BuyStop(lots, px, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG buy stop"))
      { placedBarL = barCounter; pendActL = actD; pendDstL = dstD; if(InpVerbose) PrintFormat("FG: BuyStop %.2f @ %s SL %s TP %s", lots, DoubleToString(px,_Digits), DoubleToString(sl,_Digits), DoubleToString(tp,_Digits)); }
      else PrintFormat("FG: BuyStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      DeletePending(ORDER_TYPE_SELL_STOP, "OCA: opposite placed");
   }
   if(sellSignal && allowS && !inShort && (flat || InpAllowReverse || InpExitOnOpposite))
   {
      double lots = LotsFor(slD);
      if(inLong && !IsHedging()) lots = NormLots(lots + pvol);
      double px = NormPrice(MathMin(bid - dist, bid - minD));
      double sl = NormPrice(px + slD), tp = NormPrice(px - tpD);
      DeletePending(ORDER_TYPE_SELL_STOP, "re-placing");
      if(trade.SellStop(lots, px, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG sell stop"))
      { placedBarS = barCounter; pendActS = actD; pendDstS = dstD; if(InpVerbose) PrintFormat("FG: SellStop %.2f @ %s SL %s TP %s", lots, DoubleToString(px,_Digits), DoubleToString(sl,_Digits), DoubleToString(tp,_Digits)); }
      else PrintFormat("FG: SellStop failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      DeletePending(ORDER_TYPE_BUY_STOP, "OCA: opposite placed");
   }
}

//+------------------------------------------------------------------+
//| Trailing stop on ticks (broker-emulator trail_points/trail_offset)|
//+------------------------------------------------------------------+
void TrailTick()
{
   ENUM_POSITION_TYPE ptype; double pvol; ulong pt = OurPosition(ptype, pvol);
   if(pt == 0) { posTicketSeen = 0; return; }
   if(pt != posTicketSeen)
   {
      // new position: take the distances locked when its order was placed
      posTicketSeen = pt; posTrailOn = false;
      posAct = ptype == POSITION_TYPE_BUY ? pendActL : pendActS;
      posDst = ptype == POSITION_TYPE_BUY ? pendDstL : pendDstS;
      posExt = PositionGetDouble(POSITION_PRICE_OPEN);
      posOpenTime = (datetime)PositionGetInteger(POSITION_TIME);
   }
   if(!InpUseTrail || posAct <= 0 || posDst <= 0) return;
   double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minD = MinStopDist();
   if(ptype == POSITION_TYPE_BUY)
   {
      if(!posTrailOn && bid - open >= posAct) posTrailOn = true;
      if(!posTrailOn) return;
      if(bid > posExt) posExt = bid;
      double newSl = NormPrice(posExt - posDst);
      if(newSl > sl + _Point && newSl <= bid - minD)
         if(!trade.PositionModify(pt, newSl, tp)) PrintFormat("FG: trail modify failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   }
   else
   {
      if(!posTrailOn && open - ask >= posAct) posTrailOn = true;
      if(!posTrailOn) return;
      if(ask < posExt) posExt = ask;
      double newSl = NormPrice(posExt + posDst);
      if((sl == 0 || newSl < sl - _Point) && newSl >= ask + minD)
         if(!trade.PositionModify(pt, newSl, tp)) PrintFormat("FG: trail modify failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
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
   TrailTick();
   if(InpShowPanel) UpdatePanel();
}

//+------------------------------------------------------------------+
//| Fills: OCA delete, and on hedging accounts close the opposite    |
//| position so a reversal behaves like the Pine strategy            |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic || HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT) return;
   ENUM_DEAL_TYPE dtype = (ENUM_DEAL_TYPE)HistoryDealGetInteger(trans.deal, DEAL_TYPE);
   if(dtype == DEAL_TYPE_BUY)  { DeletePending(ORDER_TYPE_SELL_STOP, "OCA: buy filled"); placedBarL = -1; }
   if(dtype == DEAL_TYPE_SELL) { DeletePending(ORDER_TYPE_BUY_STOP,  "OCA: sell filled"); placedBarS = -1; }
   if(IsHedging())
   {
      // close any position of ours in the opposite direction (reversal)
      long thisPos = HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || PositionGetInteger(POSITION_MAGIC) != InpMagic || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if((long)PositionGetInteger(POSITION_IDENTIFIER) == thisPos) continue;
         ENUM_POSITION_TYPE ty = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         if((dtype == DEAL_TYPE_BUY && ty == POSITION_TYPE_SELL) || (dtype == DEAL_TYPE_SELL && ty == POSITION_TYPE_BUY))
         {
            if(trade.PositionClose(t)) { if(InpVerbose) PrintFormat("FG: reversal closed #%I64u", t); }
            else PrintFormat("FG: reversal close failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
         }
      }
   }
}

//+------------------------------------------------------------------+
void UpdatePanel()
{
   ENUM_POSITION_TYPE ptype; double pvol; ulong pt = OurPosition(ptype, pvol);
   string pos = "flat";
   if(pt != 0)
      pos = StringFormat("%s %.2f @ %s SL %s TP %s trail %s", ptype == POSITION_TYPE_BUY ? "LONG" : "SHORT", pvol,
                         DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN),_Digits), DoubleToString(PositionGetDouble(POSITION_SL),_Digits),
                         DoubleToString(PositionGetDouble(POSITION_TP),_Digits), posTrailOn ? "ON" : "armed");
   string s = StringFormat("FlashGold v5 step 1  [%s]  %s %s\n", pName, _Symbol, EnumToString(_Period));
   s += StringFormat("Parent %s   zones aligned %d/%d   conflict %d   buy/sell allowed %s/%s\n",
                     parentDir > 0 ? "BUY" : parentDir < 0 ? "SELL" : "MIX", alignedZones, activeZones, conflictZones, buyAllowed ? "yes" : "no", sellAllowed ? "yes" : "no");
   s += StringFormat("ATR %s   burst %s (thr %s)   dist %s   SL %s   TP %s\n", DoubleToString(atrRef,_Digits), DoubleToString(burstNow,_Digits),
                     DoubleToString(pBurst*atrRef,_Digits), DoubleToString(pDist*atrRef,_Digits), DoubleToString(pSl*atrRef,_Digits), DoubleToString(pSl*atrRef*pTpR,_Digits));
   s += StringFormat("Hold %s   BuyStop %s   SellStop %s\n", holdActive ? (holdIsBuy ? "BUY pending" : "SELL pending") : "-",
                     FindPending(ORDER_TYPE_BUY_STOP) != 0 ? "resting" : "-", FindPending(ORDER_TYPE_SELL_STOP) != 0 ? "resting" : "-");
   s += StringFormat("Position: %s\n", pos);
   Comment(s);
}
//+------------------------------------------------------------------+
