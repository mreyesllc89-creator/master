//+------------------------------------------------------------------+
//| FlashGoldV5_Core.mqh                                             |
//| MT5 port of "FlashGold v5 Strategy" (Pine, BTCUSD / XAUUSD).     |
//| The logic follows the Pine script rule by rule:                  |
//|  - TDI direction: RSI(14) -> SMA fast(2); fast rising = BUY      |
//|  - parent + child zones as multiples of the chart timeframe      |
//|    (auto = chart / 2x / 4x), zones read from the last CLOSED     |
//|    higher-timeframe bar, parent as Pine's lookahead_off history  |
//|  - burst gate, prior-drift filter, entry hold, one entry per bar |
//|  - entry STOP order at ask + entry distance (buy) / bid - entry  |
//|    distance (sell), cancelled after N bars, OCA between sides,   |
//|    reversal on the opposite fill                                 |
//|  - exits: SL, Fixed TP (+ optional trail) or Partial + runner    |
//|    (part closed at TP, stop to breakeven, runner trail), time    |
//|    stop, exit on opposite signal; units Pips / ATR / Points      |
//|  - spread aware: live bid/ask, max-spread entry filter, stop     |
//|    widened by the spread at fill so the real distance matches    |
//| Signals are evaluated once per closed bar, as in the Pine script |
//| (calc_on_every_tick = false). Exits are managed on every tick.   |
//| Each symbol file (FlashGoldV5_BTCUSD.mq5 / _XAUUSD.mq5) #defines |
//| the calibrated defaults and includes this file.                  |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

enum ENUM_FG_UNIT    { FG_UNIT_PIPS = 0,   // Pips
                       FG_UNIT_ATR = 1,    // ATR
                       FG_UNIT_POINTS = 2  // Points (_Point)
                     };
enum ENUM_FG_DUNIT   { FG_DUNIT_ATR = 0,   // ATR
                       FG_DUNIT_POINTS = 1 // Points (_Point)
                     };
enum ENUM_FG_SIDE    { FG_BOTH = 0,        // Both
                       FG_LONG = 1,        // Long only
                       FG_SHORT = 2        // Short only
                     };
enum ENUM_FG_TPSTYLE { FG_TP_FIXED = 0,    // Fixed
                       FG_TP_PARTIAL = 1   // Partial + runner
                     };
enum ENUM_FG_QTY     { FG_QTY_FIXED = 0,   // Fixed lots
                       FG_QTY_RISK = 1     // Risk % of equity
                     };
enum ENUM_FG_SPREAD  { FG_SPREAD_LIVE = 0, // Live bid / ask
                       FG_SPREAD_MODEL = 1 // Model (fixed spread input, like the Pine script)
                     };

//============================== INPUTS ==============================
input group "Spread"
input ENUM_FG_SPREAD InpSpreadMode   = FG_SPREAD_LIVE;      // Entry price from
input double InpModelSpread          = FG_MODEL_SPREAD;     // Model spread, price units (Model mode)
input double InpMaxSpreadPips        = FG_MAX_SPREAD_PIPS;  // Max spread for a NEW entry, pips (0 = off)
input bool   InpSpreadToSL           = true;                // Widen the stop by the spread at fill
input bool   InpCancelOnWideSpread   = false;               // Delete pending entries while the spread is too wide

input group "FlashGold Core"
input double InpEntryDistPoints      = 50.0;   // Entry distance, points (Points unit)
input int    InpEntryHoldBars        = 0;      // Entry hold bars
input double InpHoldMinFavPoints     = 5.0;    // Hold min favorable, points (Points unit)
input bool   InpOneEntryPerBar       = true;   // One entry per bar

input group "Burst / Direction"
input ENUM_FG_DUNIT InpDistUnit      = FG_DUNIT_ATR; // Burst / entry distance / hold unit
input double InpBurstAtrMult         = 0.5;    // Burst threshold, ATR mult
input double InpEntryDistAtrMult     = 0.25;   // Entry distance, ATR mult
input double InpHoldFavAtrMult       = 0.1;    // Hold min favorable, ATR mult
input double InpBurstPoints          = 172.0;  // Burst threshold, points (Points unit)
input bool   InpUseBurstGate         = true;   // Require burst gate
input bool   InpUseAnyCombo          = false;  // Allow any combo
input int    InpPriorDriftBars       = 60;     // Prior drift bars
input bool   InpUsePriorFilter       = false;  // Use prior drift filter

input group "TDI Trade Zone Filter (timeframes as multiples of the chart)"
input bool   InpUseTdiZone           = true;   // Use TDI trade-zone filter
input int    InpParentMult           = 1;      // Parent timeframe = chart x (1 = chart)
input int    InpRsiLen               = 14;     // TDI RSI length
input int    InpFastLen              = 2;      // TDI white fast length
input int    InpMinAligned           = 2;      // Minimum child zones aligned
input bool   InpAllowNeutralParent   = false;  // Allow trade if parent is flat
input bool   InpIgnoreNaZones        = true;   // Ignore zones without data
input bool   InpHtfNoRepaint         = true;   // Higher-TF zones use the last CLOSED bar
input bool   InpUseZone1             = true;   // Use child zone 1
input int    InpZone1Mult            = 1;      // Zone 1 = chart x
input bool   InpUseZone2             = true;   // Use child zone 2
input int    InpZone2Mult            = 2;      // Zone 2 = chart x
input bool   InpUseZone3             = true;   // Use child zone 3
input int    InpZone3Mult            = 4;      // Zone 3 = chart x
input bool   InpUseZone4             = false;  // Use child zone 4
input int    InpZone4Mult            = 8;      // Zone 4 = chart x
input bool   InpUseZone5             = false;  // Use child zone 5
input int    InpZone5Mult            = 16;     // Zone 5 = chart x
input bool   InpUseZone6             = false;  // Use child zone 6
input int    InpZone6Mult            = 32;     // Zone 6 = chart x
input int    InpLookbackBars         = 3000;   // History bars used for RSI / ATR / zones

input group "S1. Entry order"
input ENUM_FG_SIDE InpDirection      = FG_BOTH; // Direction
input int    InpEntryValidBars       = 3;      // Cancel unfilled entry after N bars (0 = keep)
input bool   InpAllowReverse         = true;   // Opposite signal may reverse an open position
input bool   InpExitOnOpposite       = false;  // Close at market on the opposite signal

input group "S2. Exits"
input ENUM_FG_UNIT InpExitUnit       = FG_UNIT_PIPS; // SL / TP / trail unit
input double InpPipSize              = FG_PIP_SIZE;  // Pip size, price units
input double InpSlPips               = FG_SL_PIPS;   // Stop loss, pips (Pips)
input double InpTpRPips              = FG_TPR_PIPS;  // Take profit, R multiple of SL (Pips)
input double InpRunTrailPips         = FG_RUN_PIPS;  // Runner trail distance, pips (Pips)
input double InpTrailActPips         = FG_TRAIL_ACT_PIPS; // Trail activation, pips (Pips, Fixed style)
input double InpTrailPips            = FG_TRAIL_PIPS;     // Trail distance, pips (Pips, Fixed style)
input int    InpAtrLen               = 14;           // ATR length (ATR unit)
input double InpSlAtr                = FG_SL_ATR;    // Stop loss, ATR mult (ATR)
input double InpTpRAtr               = FG_TPR_ATR;   // Take profit, R multiple of SL (ATR)
input double InpRunTrailAtr          = FG_RUN_ATR;   // Runner trail distance, ATR mult (ATR)
input double InpTrailActAtr          = 1.0;          // Trail activation, ATR mult (ATR, Fixed style)
input double InpTrailDstAtr          = 0.25;         // Trail distance, ATR mult (ATR, Fixed style)
input double InpSlPoints             = FG_SL_POINTS;    // Stop loss, points (Points)
input double InpTpPoints             = FG_TP_POINTS;    // Take profit, points (Points)
input double InpRunTrailPoints       = FG_RUN_POINTS;   // Runner trail distance, points (Points)
input double InpTrailActPoints       = FG_TRAIL_ACT_POINTS; // Trail activation, points (Points, Fixed style)
input double InpTrailPoints          = FG_TRAIL_POINTS;     // Trail distance, points (Points, Fixed style)
input ENUM_FG_TPSTYLE InpTpStyle     = FG_TP_PARTIAL; // Take profit style
input double InpPartPct              = 30.0;   // Partial: % closed at the take profit
input bool   InpRunnerBE             = true;   // Runner: stop to breakeven after the take profit
input bool   InpBEAtBarClose         = true;   // Breakeven at the close of the TP bar (as the Pine script)
input bool   InpUseTrail             = false;  // Trailing stop (Fixed style only)
input int    InpMaxBarsHeld          = 0;      // Time stop, bars (0 = off)

input group "S3. Sizing"
input ENUM_FG_QTY InpQtyMode         = FG_QTY_FIXED; // Quantity
input double InpFixedLots            = FG_LOTS;      // Fixed lots
input double InpRiskPct              = 1.0;          // Risk % of equity per trade (Risk mode)
input double InpMaxLots              = 50.0;         // Max lots

input group "EA"
input long   InpMagic                = FG_MAGIC;     // Magic number
input bool   InpShowPanel            = true;         // Show status panel
input bool   InpDrawSignals          = true;         // Draw BUY / SELL arrows

//============================== STATE ==============================
CTrade   trade;
const int NA_DIR = -99;
datetime g_lastBarTime = 0;
bool     g_hedging = true;

// entry hold / one entry per bar (Pine vars)
bool     g_holdActive = false;
bool     g_holdIsBuy = false;
int      g_holdBars = 0;        // bars elapsed since the hold started
double   g_holdMid = 0.0;
datetime g_lastEntryBar = 0;

// pending entry bookkeeping
int      g_barsSinceL = -1, g_barsSinceS = -1;   // -1 = no pending placed by the signal logic
double   g_lockSlL = 0, g_lockTpL = 0, g_lockRunL = 0, g_lockActL = 0, g_lockDstL = 0, g_volL = 0;
double   g_lockSlS = 0, g_lockTpS = 0, g_lockRunS = 0, g_lockActS = 0, g_lockDstS = 0, g_volS = 0;

// managed position
long     g_posId = -1;
int      g_posType = -1;        // POSITION_TYPE_BUY / SELL
double   g_open = 0, g_slD = 0, g_tpD = 0, g_runD = 0, g_actD = 0, g_dstD = 0, g_targetVol = 0;
bool     g_tpHit = false, g_partDone = false, g_beArmed = false, g_trailOn = false;
double   g_best = 0;
int      g_barsHeld = 0;

// panel info
int      g_parentSide = 0, g_aligned = 0, g_active = 0, g_conflict = 0;
double   g_atrPrice = 0, g_slShown = 0;
string   g_lastSignal = "-";

//============================== HELPERS ==============================
double PipPrice(double pips)   { return pips * InpPipSize; }
double Pts(double points)      { return points * _Point; }
double SpreadPrice()           { return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID); }
double SpreadPips()            { return InpPipSize > 0 ? SpreadPrice() / InpPipSize : 0.0; }
bool   SpreadOk()              { return InpMaxSpreadPips <= 0 || SpreadPips() <= InpMaxSpreadPips; }

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
   if(v > vmax) v = vmax;
   return NormalizeDouble(v, 8);
}

double StopsLevelPrice()
{
   return (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
}

// Wilder RMA seeded with an SMA (Pine ta.rma)
void Rma(const double &src[], const bool &valid[], int n, int len, double &out[], bool &ok[])
{
   ArrayResize(out, n); ArrayResize(ok, n);
   double sum = 0; int cnt = 0; bool seeded = false; double prev = 0;
   for(int i = 0; i < n; i++)
   {
      ok[i] = false; out[i] = 0;
      if(!valid[i]) continue;
      if(!seeded)
      {
         sum += src[i]; cnt++;
         if(cnt == len) { prev = sum / len; seeded = true; out[i] = prev; ok[i] = true; }
      }
      else
      {
         prev = (prev * (len - 1) + src[i]) / len;
         out[i] = prev; ok[i] = true;
      }
   }
}

// TDI direction series: RSI(len) -> SMA(fast); +1 rising, -1 falling, 0 flat, NA_DIR not ready
void TdiDirSeries(const double &cl[], int n, int &dir[])
{
   ArrayResize(dir, n);
   double up[], dn[]; bool v[];
   ArrayResize(up, n); ArrayResize(dn, n); ArrayResize(v, n);
   for(int i = 0; i < n; i++)
   {
      if(i == 0) { up[i] = 0; dn[i] = 0; v[i] = false; continue; }
      double ch = cl[i] - cl[i - 1];
      up[i] = MathMax(ch, 0.0); dn[i] = MathMax(-ch, 0.0); v[i] = true;
   }
   double ru[], rd[]; bool oku[], okd[];
   Rma(up, v, n, InpRsiLen, ru, oku);
   Rma(dn, v, n, InpRsiLen, rd, okd);
   double rsi[]; bool okr[];
   ArrayResize(rsi, n); ArrayResize(okr, n);
   for(int i = 0; i < n; i++)
   {
      okr[i] = oku[i] && okd[i];
      if(!okr[i]) { rsi[i] = 0; continue; }
      rsi[i] = rd[i] == 0 ? 100.0 : (ru[i] == 0 ? 0.0 : 100.0 - 100.0 / (1.0 + ru[i] / rd[i]));
   }
   double f[]; bool okf[];
   ArrayResize(f, n); ArrayResize(okf, n);
   for(int i = 0; i < n; i++)
   {
      okf[i] = false; f[i] = 0;
      if(i < InpFastLen - 1) continue;
      double s = 0; bool good = true;
      for(int k = 0; k < InpFastLen; k++) { if(!okr[i - k]) { good = false; break; } s += rsi[i - k]; }
      if(good) { f[i] = s / InpFastLen; okf[i] = true; }
   }
   for(int i = 0; i < n; i++)
   {
      if(i == 0 || !okf[i] || !okf[i - 1]) { dir[i] = NA_DIR; continue; }
      dir[i] = f[i] > f[i - 1] ? 1 : (f[i] < f[i - 1] ? -1 : 0);
   }
}

// bucket key for a higher timeframe = chart x mult, anchored to the server day (as MT5 / TradingView session bars)
long BucketKey(datetime t, int periodSec)
{
   long tt = (long)t;
   if(periodSec <= 86400) return (tt / 86400) * 100000 + (tt % 86400) / periodSec;
   return tt / periodSec;
}

// direction of a timeframe = chart x mult, as seen at the last closed chart bar (index m-1)
// parentMode: Pine plain request (lookahead_off): the bucket just completed counts; else the [1] idiom (previous bucket)
int HtfDir(const MqlRates &r[], int m, datetime formingTime, int mult, bool parentMode, const int &chartDir[])
{
   if(mult <= 1) return chartDir[m - 1];
   int periodSec = PeriodSeconds(_Period) * mult;
   double bc[]; ArrayResize(bc, m);
   int nb = 0; long lastKey = -1;
   for(int i = 0; i < m; i++)
   {
      long k = BucketKey(r[i].time, periodSec);
      if(nb == 0 || k != lastKey) { bc[nb] = r[i].close; nb++; lastKey = k; }
      else bc[nb - 1] = r[i].close;
   }
   int dB[];
   TdiDirSeries(bc, nb, dB);
   int b = nb - 1;
   if(parentMode)
   {
      bool lastOfBucket = BucketKey(formingTime, periodSec) != lastKey;
      if(lastOfBucket) return dB[b];
      return b >= 1 ? dB[b - 1] : NA_DIR;
   }
   return b >= 1 ? dB[b - 1] : NA_DIR;
}

//============================== POSITIONS / ORDERS ==============================
int CountPositions(int type)
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(type < 0 || PositionGetInteger(POSITION_TYPE) == type) c++;
   }
   return c;
}

double PositionVolume(int type)
{
   double v = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetInteger(POSITION_TYPE) == type) v += PositionGetDouble(POSITION_VOLUME);
   }
   return v;
}

void ClosePositions(int type, string why)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(type >= 0 && PositionGetInteger(POSITION_TYPE) != type) continue;
      trade.SetExpertMagicNumber(InpMagic);
      if(!trade.PositionClose(tk)) PrintFormat("FG: close %I64u (%s) failed: %d", tk, why, trade.ResultRetcode());
   }
}

void DeletePending(int orderType)   // ORDER_TYPE_BUY_STOP / ORDER_TYPE_SELL_STOP, -1 = both
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || !OrderSelect(tk)) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      long ot = OrderGetInteger(ORDER_TYPE);
      if(orderType >= 0 && ot != orderType) continue;
      if(!trade.OrderDelete(tk)) PrintFormat("FG: delete order %I64u failed: %d", tk, trade.ResultRetcode());
   }
}

bool HasPending(int orderType)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || !OrderSelect(tk)) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(OrderGetInteger(ORDER_TYPE) == orderType) return true;
   }
   return false;
}

// partial close: by ticket on hedging accounts, by symbol on netting accounts
bool ClosePartialVol(ulong ticket, double vol)
{
   trade.SetExpertMagicNumber(InpMagic);
   bool ok = g_hedging ? trade.PositionClosePartial(ticket, vol) : trade.PositionClosePartial(_Symbol, vol);
   if(!ok) PrintFormat("FG: partial close %.2f failed: %d", vol, trade.ResultRetcode());
   return ok;
}

double CalcLots(double slDist)
{
   double q = InpFixedLots;
   if(InpQtyMode == FG_QTY_RISK)
   {
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
      double perLot = (ts > 0 && tv > 0) ? slDist / ts * tv : 0.0;
      q = perLot > 0 ? riskCash / perLot : 0.0;
   }
   q = MathMin(q, InpMaxLots);
   return NormVol(q);
}

// place (or replace) the entry stop. Pine: strategy.entry(..., stop = price). If price already traded through, Pine fills at the open -> market order.
void PlaceEntry(bool isBuy, double price, double vol, double slD, double tpD)
{
   trade.SetExpertMagicNumber(InpMagic);
   DeletePending(isBuy ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl, tp;
   bool fixedTp = InpTpStyle == FG_TP_FIXED || InpPartPct >= 100.0;
   if(isBuy)
   {
      if(ask >= price)
      {
         sl = slD > 0 ? NormPrice(ask - slD) : 0; tp = (fixedTp && tpD > 0) ? NormPrice(ask + tpD) : 0;
         if(!trade.Buy(vol, _Symbol, 0, sl, tp, "FG buy")) PrintFormat("FG: market buy failed %d", trade.ResultRetcode());
      }
      else
      {
         price = MathMax(price, ask + StopsLevelPrice() + _Point);
         price = NormPrice(price);
         sl = slD > 0 ? NormPrice(price - slD) : 0; tp = (fixedTp && tpD > 0) ? NormPrice(price + tpD) : 0;
         if(!trade.BuyStop(vol, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG buy stop")) PrintFormat("FG: buy stop failed %d", trade.ResultRetcode());
      }
   }
   else
   {
      if(bid <= price)
      {
         sl = slD > 0 ? NormPrice(bid + slD) : 0; tp = (fixedTp && tpD > 0) ? NormPrice(bid - tpD) : 0;
         if(!trade.Sell(vol, _Symbol, 0, sl, tp, "FG sell")) PrintFormat("FG: market sell failed %d", trade.ResultRetcode());
      }
      else
      {
         price = MathMin(price, bid - StopsLevelPrice() - _Point);
         price = NormPrice(price);
         sl = slD > 0 ? NormPrice(price + slD) : 0; tp = (fixedTp && tpD > 0) ? NormPrice(price - tpD) : 0;
         if(!trade.SellStop(vol, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG sell stop")) PrintFormat("FG: sell stop failed %d", trade.ResultRetcode());
      }
   }
}

//============================== SIGNAL (once per closed bar) ==============================
void OnNewBar()
{
   int avail = Bars(_Symbol, _Period);
   int want = MathMin(InpLookbackBars, avail);
   if(want < 50) return;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, _Period, 0, want, r);
   if(got < 50) return;
   int m = got - 1;                       // closed bars 0..m-1, r[m] = forming bar
   datetime formingTime = r[m].time;
   int i = m - 1;

   // ATR(14) for burst / entry distance and ATR(atrLen) for exits
   double tr[]; bool trv[];
   ArrayResize(tr, m); ArrayResize(trv, m);
   for(int k = 0; k < m; k++)
   {
      tr[k] = k == 0 ? r[k].high - r[k].low
                     : MathMax(r[k].high - r[k].low, MathMax(MathAbs(r[k].high - r[k - 1].close), MathAbs(r[k].low - r[k - 1].close)));
      trv[k] = true;
   }
   double atr14[], atrX[]; bool ok14[], okX[];
   Rma(tr, trv, m, 14, atr14, ok14);
   Rma(tr, trv, m, InpAtrLen, atrX, okX);
   if(!ok14[i] || !okX[i]) return;
   g_atrPrice = atrX[i];

   // TDI: chart series, parent, zones
   double cl[]; ArrayResize(cl, m);
   for(int k = 0; k < m; k++) cl[k] = r[k].close;
   int chartDir[];
   TdiDirSeries(cl, m, chartDir);
   int parentDir = HtfDir(r, m, formingTime, InpParentMult, true, chartDir);
   bool useZ[6]; int multZ[6];
   useZ[0] = InpUseZone1; multZ[0] = InpZone1Mult;
   useZ[1] = InpUseZone2; multZ[1] = InpZone2Mult;
   useZ[2] = InpUseZone3; multZ[2] = InpZone3Mult;
   useZ[3] = InpUseZone4; multZ[3] = InpZone4Mult;
   useZ[4] = InpUseZone5; multZ[4] = InpZone5Mult;
   useZ[5] = InpUseZone6; multZ[5] = InpZone6Mult;

   int parentSide = parentDir == NA_DIR ? 0 : (parentDir > 0 ? 1 : (parentDir < 0 ? -1 : 0));
   int active = 0, aligned = 0, conflict = 0;
   for(int z = 0; z < 6; z++)
   {
      if(!useZ[z]) continue;
      int d = HtfDir(r, m, formingTime, multZ[z], !InpHtfNoRepaint || multZ[z] <= 1, chartDir);
      bool on = !InpIgnoreNaZones || d != NA_DIR;
      if(!on) continue;
      active++;
      if(parentSide != 0 && d == parentSide) aligned++;
      if(parentSide != 0 && d == -parentSide) conflict++;
   }
   int required = MathMin(InpMinAligned, active);
   bool parentFlatAllowed = InpAllowNeutralParent && parentSide == 0;
   bool zoneReady = active == 0 || aligned >= required;
   bool zoneBuy  = !InpUseTdiZone || ((parentSide == 1 || parentFlatAllowed) && zoneReady);
   bool zoneSell = !InpUseTdiZone || ((parentSide == -1 || parentFlatAllowed) && zoneReady);
   g_parentSide = parentSide; g_aligned = aligned; g_active = active; g_conflict = conflict;

   // burst / distances (price units). Pine: mid = close (the model bid/ask are symmetric around close)
   double atrB = atr14[i];
   double burstThr = InpDistUnit == FG_DUNIT_ATR ? InpBurstAtrMult * atrB : Pts(InpBurstPoints);
   double entryDist = InpDistUnit == FG_DUNIT_ATR ? InpEntryDistAtrMult * atrB : Pts(InpEntryDistPoints);
   double holdFav = InpDistUnit == FG_DUNIT_ATR ? InpHoldFavAtrMult * atrB : Pts(InpHoldMinFavPoints);
   double mid = r[i].close;
   double burst = r[i].close - r[i - 1].close;
   double drift = i - InpPriorDriftBars >= 0 ? r[i].close - r[i - InpPriorDriftBars].close : 0.0;
   bool burstBuy = burst >= burstThr, burstSell = burst <= -burstThr;
   bool priorBuyOk = !InpUsePriorFilter || drift > 0, priorSellOk = !InpUsePriorFilter || drift < 0;
   bool rawBuy  = InpUseAnyCombo ? (zoneBuy  && (!InpUseBurstGate || burstBuy  || parentSide == 1))  : (zoneBuy  && burstBuy);
   bool rawSell = InpUseAnyCombo ? (zoneSell && (!InpUseBurstGate || burstSell || parentSide == -1)) : (zoneSell && burstSell);
   bool buyCand = rawBuy && priorBuyOk, sellCand = rawSell && priorSellOk;

   // entry price: Pine ask + dist / bid - dist. Live mode uses the real bid / ask, Model mode close +- half the model spread
   double askP = InpSpreadMode == FG_SPREAD_LIVE ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : r[i].close + InpModelSpread * 0.5;
   double bidP = InpSpreadMode == FG_SPREAD_LIVE ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : r[i].close - InpModelSpread * 0.5;

   // entry hold / virtual stop (Pine)
   datetime barId = r[i].time;
   bool canFire = !InpOneEntryPerBar || g_lastEntryBar != barId;
   bool buySignal = false, sellSignal = false;
   double buyPx = 0, sellPx = 0;
   if(g_holdActive) g_holdBars++;
   if(buyCand && canFire)
   {
      if(InpEntryHoldBars == 0) { buyPx = askP + entryDist; buySignal = true; g_lastEntryBar = barId; }
      else if(!g_holdActive) { g_holdActive = true; g_holdIsBuy = true; g_holdBars = 0; g_holdMid = mid; }
      else if(g_holdIsBuy && g_holdBars >= InpEntryHoldBars && mid - g_holdMid >= holdFav)
      { buyPx = askP + entryDist; buySignal = true; g_lastEntryBar = barId; g_holdActive = false; }
   }
   if(sellCand && canFire)
   {
      if(InpEntryHoldBars == 0) { sellPx = bidP - entryDist; sellSignal = true; g_lastEntryBar = barId; }
      else if(!g_holdActive) { g_holdActive = true; g_holdIsBuy = false; g_holdBars = 0; g_holdMid = mid; }
      else if(!g_holdIsBuy && g_holdBars >= InpEntryHoldBars && g_holdMid - mid >= holdFav)
      { sellPx = bidP - entryDist; sellSignal = true; g_lastEntryBar = barId; g_holdActive = false; }
   }
   if(g_holdActive && ((g_holdIsBuy && !zoneBuy) || (!g_holdIsBuy && !zoneSell))) g_holdActive = false;

   // exit geometry (price distances), locked at the signal
   double slD, tpD, runD, actD, dstD;
   if(InpExitUnit == FG_UNIT_PIPS)
   { slD = PipPrice(InpSlPips); tpD = slD * InpTpRPips; runD = PipPrice(InpRunTrailPips); actD = PipPrice(InpTrailActPips); dstD = PipPrice(InpTrailPips); }
   else if(InpExitUnit == FG_UNIT_ATR)
   { slD = InpSlAtr * atrX[i]; tpD = slD * InpTpRAtr; runD = InpRunTrailAtr * atrX[i]; actD = InpTrailActAtr * atrB; dstD = InpTrailDstAtr * atrB; }
   else
   { slD = Pts(InpSlPoints); tpD = Pts(InpTpPoints); runD = Pts(InpRunTrailPoints); actD = Pts(InpTrailActPoints); dstD = Pts(InpTrailPoints); }
   g_slShown = slD;

   // bars-held for the time stop, breakeven arming at the close of the TP bar
   if(g_posId >= 0)
   {
      g_barsHeld++;
      if(g_tpHit && InpRunnerBE && InpBEAtBarClose) g_beArmed = true;
   }

   bool inLong = CountPositions(POSITION_TYPE_BUY) > 0, inShort = CountPositions(POSITION_TYPE_SELL) > 0;
   bool flat = !inLong && !inShort;
   bool allowL = InpDirection != FG_SHORT, allowS = InpDirection != FG_LONG;
   bool spreadOk = SpreadOk();

   if(InpExitOnOpposite && sellSignal && inLong)  { ClosePositions(POSITION_TYPE_BUY, "opp signal");  inLong = false; flat = !inShort; }
   if(InpExitOnOpposite && buySignal  && inShort) { ClosePositions(POSITION_TYPE_SELL, "opp signal"); inShort = false; flat = !inLong; }

   if(buySignal)  { g_lastSignal = "BUY "  + TimeToString(barId); if(InpDrawSignals) DrawArrow(true,  barId, r[i].low); }
   if(sellSignal) { g_lastSignal = "SELL " + TimeToString(barId); if(InpDrawSignals) DrawArrow(false, barId, r[i].high); }

   if(buySignal && allowL && !inLong && (flat || InpAllowReverse || InpExitOnOpposite))
   {
      double q = CalcLots(slD);
      if(!spreadOk) PrintFormat("FG: BUY skipped, spread %.1f pips > max %.1f", SpreadPips(), InpMaxSpreadPips);
      else if(q > 0)
      {
         g_lockSlL = slD; g_lockTpL = tpD; g_lockRunL = runD; g_lockActL = actD; g_lockDstL = dstD; g_volL = q;
         double vol = q;
         if(!g_hedging && inShort) vol = NormVol(q + PositionVolume(POSITION_TYPE_SELL));   // netting: reverse in one order
         PlaceEntry(true, buyPx, vol, slD, tpD);
         g_barsSinceL = 0;
      }
   }
   if(sellSignal && allowS && !inShort && (flat || InpAllowReverse || InpExitOnOpposite))
   {
      double q = CalcLots(slD);
      if(!spreadOk) PrintFormat("FG: SELL skipped, spread %.1f pips > max %.1f", SpreadPips(), InpMaxSpreadPips);
      else if(q > 0)
      {
         g_lockSlS = slD; g_lockTpS = tpD; g_lockRunS = runD; g_lockActS = actD; g_lockDstS = dstD; g_volS = q;
         double vol = q;
         if(!g_hedging && inLong) vol = NormVol(q + PositionVolume(POSITION_TYPE_BUY));
         PlaceEntry(false, sellPx, vol, slD, tpD);
         g_barsSinceS = 0;
      }
   }

   // cancel stale unfilled entries (Pine: bar_index - placedBar >= N)
   if(InpEntryValidBars > 0)
   {
      if(g_barsSinceL >= InpEntryValidBars && !inLong) { DeletePending(ORDER_TYPE_BUY_STOP);  g_barsSinceL = -1; }
      if(g_barsSinceS >= InpEntryValidBars && !inShort) { DeletePending(ORDER_TYPE_SELL_STOP); g_barsSinceS = -1; }
   }

   // time stop
   if(InpMaxBarsHeld > 0 && g_posId >= 0 && g_barsHeld >= InpMaxBarsHeld) ClosePositions(-1, "time stop");
}

// advance the pending-order bar counters at each new bar (before the signal logic)
void AgePending()
{
   if(g_barsSinceL >= 0) { if(HasPending(ORDER_TYPE_BUY_STOP))  g_barsSinceL++; else g_barsSinceL = -1; }
   if(g_barsSinceS >= 0) { if(HasPending(ORDER_TYPE_SELL_STOP)) g_barsSinceS++; else g_barsSinceS = -1; }
}

//============================== POSITION MANAGEMENT (every tick) ==============================
void ManagePosition()
{
   // newest EA position = the one to manage; on a reversal fill the older opposite position is closed (Pine closes it in the same fill)
   ulong newest = 0; long newestMsc = -1; int newestType = -1;
   for(int k = PositionsTotal() - 1; k >= 0; k--)
   {
      ulong tk = PositionGetTicket(k);
      if(tk == 0 || !PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      long msc = PositionGetInteger(POSITION_TIME_MSC);
      if(msc > newestMsc) { newestMsc = msc; newest = tk; newestType = (int)PositionGetInteger(POSITION_TYPE); }
   }
   if(newest == 0) { g_posId = -1; g_posType = -1; return; }
   if(g_hedging)
   {
      int opp = newestType == POSITION_TYPE_BUY ? POSITION_TYPE_SELL : POSITION_TYPE_BUY;
      if(CountPositions(opp) > 0) ClosePositions(opp, "reverse");
   }
   if(!PositionSelectByTicket(newest)) return;
   long pid = PositionGetInteger(POSITION_IDENTIFIER);
   int ptype = (int)PositionGetInteger(POSITION_TYPE);
   bool isBuy = ptype == POSITION_TYPE_BUY;

   // new fill: OCA (cancel the other side), lock the distances of that side, re-anchor SL / TP on the real fill (+ spread)
   if(pid != g_posId || ptype != g_posType)
   {
      g_posId = pid; g_posType = ptype;
      g_open = PositionGetDouble(POSITION_PRICE_OPEN);
      g_slD  = isBuy ? g_lockSlL  : g_lockSlS;
      g_tpD  = isBuy ? g_lockTpL  : g_lockTpS;
      g_runD = isBuy ? g_lockRunL : g_lockRunS;
      g_actD = isBuy ? g_lockActL : g_lockActS;
      g_dstD = isBuy ? g_lockDstL : g_lockDstS;
      g_targetVol = isBuy ? g_volL : g_volS;
      g_tpHit = false; g_partDone = false; g_beArmed = false; g_trailOn = false; g_best = g_open; g_barsHeld = -1;   // Pine: the fill bar is held bar 0 at its close
      DeletePending(-1);
      g_barsSinceL = -1; g_barsSinceS = -1;
      // netting: trim an oversized reversal (the old position closed before the fill)
      if(!g_hedging && g_targetVol > 0)
      {
         double v = PositionGetDouble(POSITION_VOLUME);
         double extra = NormVol(v - g_targetVol);
         if(extra > 0) ClosePartialVol(newest, extra);
         if(!PositionSelectByTicket(newest)) return;
      }
      if(g_slD <= 0 && g_tpD <= 0) return;   // position not opened by this EA run: keep its SL / TP
      double spr = InpSpreadToSL ? SpreadPrice() : 0.0;
      double sl = g_slD > 0 ? NormPrice(isBuy ? g_open - g_slD - spr : g_open + g_slD + spr) : 0;
      bool fixedTp = InpTpStyle == FG_TP_FIXED || InpPartPct >= 100.0;
      double tp = (fixedTp && g_tpD > 0) ? NormPrice(isBuy ? g_open + g_tpD : g_open - g_tpD) : 0;
      trade.SetExpertMagicNumber(InpMagic);
      if(!trade.PositionModify(newest, sl, tp)) PrintFormat("FG: SL/TP set failed %d", trade.ResultRetcode());
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double px = isBuy ? bid : ask;                    // the price a long / short exits at
   double curSL = PositionGetDouble(POSITION_SL), curTP = PositionGetDouble(POSITION_TP);
   double vol = PositionGetDouble(POSITION_VOLUME);
   double s = isBuy ? 1.0 : -1.0;
   double newSL = curSL;
   bool partial = InpTpStyle == FG_TP_PARTIAL && InpPartPct < 100.0;

   if(partial)
   {
      // take profit level reached: close the partial, start the runner
      if(!g_tpHit && g_tpD > 0 && (px - (g_open + s * g_tpD)) * s >= 0)
      {
         g_tpHit = true; g_best = px;
         if(InpRunnerBE && !InpBEAtBarClose) g_beArmed = true;
         if(InpPartPct > 0 && !g_partDone)
         {
            double pv = NormVol(vol * InpPartPct / 100.0);
            trade.SetExpertMagicNumber(InpMagic);
            if(pv > 0 && pv < vol) ClosePartialVol(newest, pv);
            else if(pv >= vol) { trade.PositionClose(newest); return; }
            g_partDone = true;
            if(!PositionSelectByTicket(newest)) return;
            curSL = PositionGetDouble(POSITION_SL); curTP = PositionGetDouble(POSITION_TP); newSL = curSL;
         }
      }
      if(g_tpHit)
      {
         if((px - g_best) * s > 0) g_best = px;
         double trailSL = g_best - s * g_runD;
         if(g_beArmed) trailSL = isBuy ? MathMax(trailSL, g_open) : MathMin(trailSL, g_open);
         if(curSL == 0 || (trailSL - curSL) * s > 0) newSL = trailSL;
      }
   }
   else if(InpUseTrail && g_dstD > 0)
   {
      // Fixed style with the Pine trail: activates after actD of profit, follows the best price by dstD
      if(!g_trailOn && (px - (g_open + s * g_actD)) * s >= 0) { g_trailOn = true; g_best = px; }
      if(g_trailOn)
      {
         if((px - g_best) * s > 0) g_best = px;
         double trailSL = g_best - s * g_dstD;
         if(curSL == 0 || (trailSL - curSL) * s > 0) newSL = trailSL;
      }
   }

   if(newSL != curSL)
   {
      newSL = NormPrice(newSL);
      double minGap = StopsLevelPrice();
      bool valid = isBuy ? (bid - newSL > minGap) : (newSL - ask > minGap);
      if(valid && MathAbs(newSL - curSL) >= _Point)
      {
         trade.SetExpertMagicNumber(InpMagic);
         if(!trade.PositionModify(newest, newSL, curTP)) PrintFormat("FG: trail modify failed %d", trade.ResultRetcode());
      }
   }
}

//============================== VISUALS ==============================
void DrawArrow(bool isBuy, datetime t, double price)
{
   string name = StringFormat("FG_%s_%I64d", isBuy ? "BUY" : "SELL", (long)t);
   if(ObjectFind(0, name) >= 0) return;
   ObjectCreate(0, name, isBuy ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, isBuy ? clrLime : clrRed);
}

string DirTxt(int d) { return d > 0 ? "BUY" : (d < 0 ? "SELL" : "MIX"); }

void ShowPanel()
{
   if(!InpShowPanel) return;
   double spr = SpreadPips();
   double slPips = InpPipSize > 0 ? g_slShown / InpPipSize : 0;
   string pos = g_posId < 0 ? "flat" : StringFormat("%s  tpHit=%s  BE=%s", g_posType == POSITION_TYPE_BUY ? "LONG" : "SHORT", g_tpHit ? "yes" : "no", g_beArmed ? "yes" : "no");
   Comment(StringFormat(
      "%s\nParent: %s   Aligned %d/%d   Conflict %d\nATR: %.2f   SL: %.1f pips (%.2f)\nSpread: %.1f pips (%.0f%% of SL)  %s\nPosition: %s\nLast signal: %s",
      FG_NAME, DirTxt(g_parentSide), g_aligned, g_active, g_conflict,
      g_atrPrice, slPips, g_slShown,
      spr, slPips > 0 ? 100.0 * spr / slPips : 0.0, SpreadOk() ? "ok" : "TOO WIDE: no new entries",
      pos, g_lastSignal));
}

//============================== EVENTS ==============================
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_hedging = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;
   g_lastBarTime = iTime(_Symbol, _Period, 0);   // first signal on the next closed bar
   if(InpPipSize <= 0) { Print("FG: pip size must be > 0"); return INIT_PARAMETERS_INCORRECT; }
   PrintFormat("%s started on %s %s, %s account, pip size %.5f", FG_NAME, _Symbol, EnumToString(_Period), g_hedging ? "hedging" : "netting", InpPipSize);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Comment("");
}

void OnTick()
{
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 != 0 && t0 != g_lastBarTime)
   {
      g_lastBarTime = t0;
      AgePending();
      OnNewBar();
   }
   if(InpCancelOnWideSpread && !SpreadOk()) DeletePending(-1);
   ManagePosition();
   ShowPanel();
}
//+------------------------------------------------------------------+
