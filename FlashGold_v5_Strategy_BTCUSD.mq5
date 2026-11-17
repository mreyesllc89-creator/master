//+------------------------------------------------------------------+
//|                              FlashGold_v5_Strategy_BTCUSD.mq5     |
//| This Source Code Form is subject to the terms of the Mozilla      |
//| Public License 2.0 at https://mozilla.org/MPL/2.0/                |
//+------------------------------------------------------------------+
// MQL5 Expert Advisor conversion of the TradingView strategy
// "FlashGold v5 Strategy (BTCUSD)" (FlashGold_v5_Strategy_BTCUSD.pine), itself a
// strategy conversion of "FlashGold Continuation v5 - TDI Trade Zone Filter"
// (indicator, (c) ghostsmartfire).
//
// Kept from the Pine strategy, same rules and same default values:
//  - signals are evaluated once per closed chart bar;
//  - the bid/ask model from the spread input (close -/+ half the spread);
//  - TDI direction (RSI -> SMA fast, fast rising = BUY) for the parent and six child zones,
//    with "auto timeframes" (chart, 2x, 4x) and last-closed-bar reads on higher timeframes;
//  - burst gate, prior-drift filter, entry hold, one entry per bar;
//  - entry as a STOP order at ask + distance (buy) / bid - distance (sell), cancelled after N bars,
//    one-cancels-the-other between the buy and the sell stop;
//  - stop loss / take profit in Pips, ATR or Points, locked at signal time;
//  - Fixed take profit (with optional trailing stop) or Partial + runner (part closed at the
//    take profit, runner stop to breakeven after the bar closes, trail starting at the TP level);
//  - time stop, exit / reversal on the opposite signal, direction filter, fixed or risk sizing.
//
// Differences that come from MetaTrader, not from the strategy:
//  - "Points" = the symbol's tick size (TradingView's mintick). Override with "Point size" if
//    your broker's BTCUSD tick is not 0.01.
//  - Quantity is in LOTS. The Pine default was 10 contracts (10 BTC); the default here is 0.10
//    lot so that attaching the EA with defaults does not open a very large position.
//  - Buy stops trigger on the real Ask and sell stops on the real Bid; commission, swap and
//    slippage are the broker's, not inputs.
//  - The partial close, the breakeven move and the trailing stop are done by the EA on ticks,
//    so the terminal must be running. The stop loss itself is always placed at the broker.
//  - MetaTrader has a fixed list of timeframes. If "auto timeframes" needs one that does not
//    exist (for example 4x of H4), that zone has no data and is dropped or counted as MIX
//    according to "Ignore zones without data".
//  - ATR is Wilder's (RMA), computed here, because MetaTrader's iATR is a simple average.
//  - The Pine labels, right-side tags and table are replaced by arrows, entry lines and a
//    text panel.
#property copyright "MPL 2.0"
#property version   "1.00"
#property description "FlashGold v5 Strategy (BTCUSD) - MQL5 conversion of the TradingView strategy"

#include <Trade\Trade.mqh>

enum ENUM_FG_UNIT
  {
   FG_UNIT_ATR,     // ATR
   FG_UNIT_POINTS   // Points
  };
enum ENUM_FG_DIR
  {
   FG_DIR_BOTH,     // Both
   FG_DIR_LONG,     // Long
   FG_DIR_SHORT     // Short
  };
enum ENUM_FG_EXIT
  {
   FG_EXIT_PIPS,    // Pips
   FG_EXIT_ATR,     // ATR
   FG_EXIT_POINTS   // Points
  };
enum ENUM_FG_TP
  {
   FG_TP_FIXED,     // Fixed
   FG_TP_RUNNER     // Partial + runner
  };
enum ENUM_FG_QTY
  {
   FG_QTY_FIXED,    // Fixed
   FG_QTY_RISK      // Risk %
  };

//============================== INPUTS ==============================
input group "FlashGold Core"
input double InpSpreadPts          = 25.0;   // Spread pts (half offsets bid and ask)
input double InpEntryDistPoints    = 50.0;   // Entry distance pts (Points unit)
input int    InpEntryHoldBars      = 0;      // Entry hold bars
input double InpHoldMinFavPoints   = 5.0;    // Hold min favorable pts (Points unit)
input bool   InpOneEntryPerBar     = true;   // One entry per bar

input group "Burst / Direction"
input ENUM_FG_UNIT InpDistUnit     = FG_UNIT_ATR; // Burst / entry distance / hold unit
input double InpBurstAtrMult       = 0.5;    // Burst threshold, ATR mult (ATR unit)
input double InpEntryDistAtrMult   = 0.25;   // Entry distance, ATR mult (ATR unit)
input double InpHoldFavAtrMult     = 0.1;    // Hold min favorable, ATR mult (ATR unit)
input double InpBurstPoints        = 172.0;  // Burst threshold pts (Points unit)
input bool   InpUseBurstGate       = true;   // Require burst gate
input bool   InpUseAnyCombo        = false;  // Allow any combo
input int    InpPriorDriftBars     = 60;     // Prior drift bars
input bool   InpUsePriorFilter     = false;  // Use prior drift filter

input group "TDI Trade Zone Filter"
input bool   InpUseTdiTradeZone    = true;   // Use TDI trade-zone filter
input ENUM_TIMEFRAMES InpParentTf  = PERIOD_H1; // Parent obedience timeframe (auto off)
input int    InpRsiLen             = 14;     // TDI RSI length
input int    InpFastLen            = 2;      // TDI white fast length
input int    InpSlowLen            = 7;      // TDI slow length (not used by the rules, as in Pine)
input int    InpMinAlignedZones    = 2;      // Minimum child zones aligned (0..6)
input bool   InpAllowNeutralParent = false;  // Allow trade if parent is flat
input bool   InpIgnoreNaZones      = true;   // Ignore zones without data
input bool   InpHtfNoRepaint       = true;   // Higher-TF zones use the last CLOSED bar
input bool   InpShowPanel          = true;   // Show TDI zone panel
input bool   InpUseZone1           = true;   // Use child zone 1
input ENUM_TIMEFRAMES InpZoneTf1   = PERIOD_H1; // Zone 1 timeframe (auto off)
input bool   InpUseZone2           = true;   // Use child zone 2
input ENUM_TIMEFRAMES InpZoneTf2   = PERIOD_H2; // Zone 2 timeframe (auto off)
input bool   InpUseZone3           = true;   // Use child zone 3
input ENUM_TIMEFRAMES InpZoneTf3   = PERIOD_H4; // Zone 3 timeframe (auto off)
input bool   InpUseZone4           = false;  // Use child zone 4
input ENUM_TIMEFRAMES InpZoneTf4   = PERIOD_H8; // Zone 4 timeframe
input bool   InpUseZone5           = false;  // Use child zone 5
input ENUM_TIMEFRAMES InpZoneTf5   = PERIOD_M1; // Zone 5 timeframe
input bool   InpUseZone6           = false;  // Use child zone 6
input ENUM_TIMEFRAMES InpZoneTf6   = PERIOD_M2; // Zone 6 timeframe
input bool   InpAutoTf             = true;   // Auto timeframes: parent/zone1 = chart, zone2 = 2x, zone3 = 4x

input group "Visuals"
input bool   InpShowArrows         = true;   // Show BUY / SELL arrows
input bool   InpShowEntryLines     = true;   // Show entry price lines
input int    InpEntryLineBars      = 20;     // Entry line length bars

input group "S1. Entry order"
input ENUM_FG_DIR InpDirection     = FG_DIR_BOTH; // Direction
input int    InpEntryValidBars     = 3;      // Cancel unfilled entry after N bars (0 = keep)
input bool   InpAllowReverse       = true;   // Opposite signal may reverse an open position
input bool   InpExitOnOpposite     = false;  // Close at market on the opposite signal

input group "S2. Exits"
input ENUM_FG_EXIT InpExitMode     = FG_EXIT_PIPS; // SL / TP / trail unit
input double InpPipSize            = 1.0;    // Pip size, price units (Pips mode)
input double InpSlPips             = 30;     // Stop loss, pips (Pips mode, 0 = none)
input double InpTpRPips            = 5;      // Take profit, R multiple of SL (Pips mode)
input double InpRunTrailPips       = 600;    // Runner: trail distance, pips (Pips mode)
input double InpTrailActPips       = 150;    // Trail activation, pips of profit (Pips mode, Fixed style)
input double InpTrailPips          = 600;    // Trail distance, pips (Pips mode, Fixed style)
input double InpSlPoints           = 3900;   // Stop loss, pts (Points mode, 0 = none)
input double InpTpPoints           = 19500;  // Take profit, pts (Points mode, 0 = none)
input int    InpAtrLen             = 14;     // ATR length (ATR mode)
input double InpSlAtrMult          = 0.1;    // Stop loss, ATR mult (ATR mode)
input double InpTpR                = 2.0;    // Take profit, R multiple of SL (ATR mode)
input bool   InpUseTrail           = false;  // Trailing stop (Fixed style)
input double InpTrailActPoints     = 4500;   // Trail activation, pts of profit (Points mode)
input double InpTrailPoints        = 1000;   // Trail distance, pts (Points mode)
input double InpTrailActAtr        = 1.0;    // Trail activation, ATR mult (ATR mode)
input double InpTrailDstAtr        = 0.25;   // Trail distance, ATR mult (ATR mode)
input int    InpMaxBarsHeld        = 0;      // Time stop, bars (0 = off)
input ENUM_FG_TP InpTpStyle        = FG_TP_RUNNER; // Take profit style
input double InpPartPct            = 30;     // Partial: % closed at the take profit
input bool   InpRunBE              = true;   // Runner: stop to breakeven after the take profit
input double InpRunTrailAtr        = 1.5;    // Runner: trail distance, ATR mult (ATR mode)
input double InpRunTrailPts        = 58000;  // Runner: trail distance, pts (Points mode)

input group "S3. Sizing"
input ENUM_FG_QTY InpQtyMode       = FG_QTY_FIXED; // Quantity
input double InpFixedLots          = 0.10;   // Fixed quantity, lots (Pine calibration used 10)
input double InpRiskPct            = 1.0;    // Risk % of equity per trade (Risk mode)
input double InpMaxLots            = 50;     // Max quantity, lots
input double InpQtyStep            = 0.01;   // Quantity step (rounds down)

input group "MetaTrader"
input long   InpMagic              = 5202601; // Magic number
input int    InpDeviation          = 50;     // Max slippage for market orders, symbol points
input double InpPointSize          = 0.0;    // Point size, price units (0 = symbol tick size)
input double InpTrailStepPts       = 100;    // Move the broker stop only when it improves by, pts

//============================== GLOBALS ==============================
#define NA_DIR  INT_MIN
#define LONG_S  0
#define SHORT_S 1

struct SideState
  {
   double            sl, tp, act, dst, run; // distances locked at signal time, in points (0 = none)
   double            qty;                   // quantity of the pending entry, before any netting top-up
   double            price;                 // pending entry price
   datetime          placed;                // time of the signal bar of the pending entry (0 = none)
   datetime          tradeId;               // open time of the tracked position (0 = none)
   bool              tpTouched;             // price reached the take profit level
   bool              tpHit;                 // ... and the bar that reached it has closed
   bool              partDone;              // the partial close was done
   bool              anchored;              // stops were re-based on the real fill price
   double            ext;                   // best price since the entry
  };

CTrade          trade;
SideState       st[2];
double          g_pt, g_tick;
bool            g_hedging, g_persist;
ENUM_TIMEFRAMES g_tf[7];       // 0 = parent, 1..6 = child zones
bool            g_use[7], g_tfOk[7];
int             g_h[7];
datetime        g_lastBar = 0;
datetime        g_lastTry[2];
long            g_barIdx = 0;
string          g_pfx;

// entry hold (virtual stop) state, as in the indicator
bool     holdActive = false, holdIsBuy = false;
long     holdSignalBar = -1, lastEntryBar = -1;
double   holdSignalMid = 0;

//============================== HELPERS ==============================
bool TfFromSeconds(const int sec, ENUM_TIMEFRAMES &tf)
  {
   ENUM_TIMEFRAMES all[] = {PERIOD_M1, PERIOD_M2, PERIOD_M3, PERIOD_M4, PERIOD_M5, PERIOD_M6, PERIOD_M10, PERIOD_M12,
                            PERIOD_M15, PERIOD_M20, PERIOD_M30, PERIOD_H1, PERIOD_H2, PERIOD_H3, PERIOD_H4, PERIOD_H6,
                            PERIOD_H8, PERIOD_H12, PERIOD_D1, PERIOD_W1, PERIOD_MN1
                           };
   for(int i = 0; i < ArraySize(all); i++)
      if(PeriodSeconds(all[i]) == sec)
        {
         tf = all[i];
         return true;
        }
   return false;
  }

ENUM_TIMEFRAMES Tf(const ENUM_TIMEFRAMES tf) { return tf == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : tf; }

double NormPrice(const double p)
  {
   return NormalizeDouble(MathRound(p / g_tick) * g_tick, _Digits);
  }

double NormVol(double v)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0)
      step = 0.01;
   v = MathFloor(v / step + 1e-9) * step;
   if(v < vmin - 1e-12)
      return 0.0;
   if(vmax > 0 && v > vmax)
      v = vmax;
   return NormalizeDouble(v, 8);
  }

double StopLevel() { return (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point; }

bool IsRunner() { return InpTpStyle == FG_TP_RUNNER && InpPartPct < 100.0; }

bool IsOurs(const string sym, const long magic) { return sym == _Symbol && magic == InpMagic; }

ulong FindPosition(const int s)
  {
   ENUM_POSITION_TYPE want = (s == LONG_S) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(IsOurs(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)) &&
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == want)
         return tk;
     }
   return 0;
  }

double PosVolume(const int s)
  {
   ENUM_POSITION_TYPE want = (s == LONG_S) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   double v = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(IsOurs(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)) &&
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == want)
         v += PositionGetDouble(POSITION_VOLUME);
     }
   return v;
  }

void ClosePositions(const int s)
  {
   ENUM_POSITION_TYPE want = (s == LONG_S) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(IsOurs(PositionGetString(POSITION_SYMBOL), PositionGetInteger(POSITION_MAGIC)) &&
         (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == want)
         if(!trade.PositionClose(tk))
            Print("FlashGold: close failed, ", trade.ResultRetcodeDescription());
     }
  }

ulong FindPending(const int s)
  {
   ENUM_ORDER_TYPE want = (s == LONG_S) ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0)
         continue;
      if(IsOurs(OrderGetString(ORDER_SYMBOL), OrderGetInteger(ORDER_MAGIC)) &&
         (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == want)
         return tk;
     }
   return 0;
  }

void DeletePending(const int s)
  {
   for(int guard = 0; guard < 20; guard++)
     {
      ulong tk = FindPending(s);
      if(tk == 0)
         return;
      if(!trade.OrderDelete(tk))
        {
         Print("FlashGold: order delete failed, ", trade.ResultRetcodeDescription());
         return;
        }
     }
  }

//--- state persistence (live only): lets the EA resume a trade after a restart
string GvName(const int s, const string f) { return g_pfx + (s == LONG_S ? "L." : "S.") + f; }

void SaveState(const int s)
  {
   if(!g_persist)
      return;
   GlobalVariableSet(GvName(s, "sl"), st[s].sl);
   GlobalVariableSet(GvName(s, "tp"), st[s].tp);
   GlobalVariableSet(GvName(s, "act"), st[s].act);
   GlobalVariableSet(GvName(s, "dst"), st[s].dst);
   GlobalVariableSet(GvName(s, "run"), st[s].run);
   GlobalVariableSet(GvName(s, "qty"), st[s].qty);
   GlobalVariableSet(GvName(s, "price"), st[s].price);
   GlobalVariableSet(GvName(s, "placed"), (double)st[s].placed);
   GlobalVariableSet(GvName(s, "tradeId"), (double)st[s].tradeId);
   GlobalVariableSet(GvName(s, "tpTouched"), st[s].tpTouched ? 1.0 : 0.0);
   GlobalVariableSet(GvName(s, "tpHit"), st[s].tpHit ? 1.0 : 0.0);
   GlobalVariableSet(GvName(s, "partDone"), st[s].partDone ? 1.0 : 0.0);
   GlobalVariableSet(GvName(s, "anchored"), st[s].anchored ? 1.0 : 0.0);
   GlobalVariableSet(GvName(s, "ext"), st[s].ext);
  }

double GvGet(const int s, const string f)
  {
   string n = GvName(s, f);
   return GlobalVariableCheck(n) ? GlobalVariableGet(n) : 0.0;
  }

void LoadState(const int s)
  {
   if(!g_persist)
      return;
   st[s].sl        = GvGet(s, "sl");
   st[s].tp        = GvGet(s, "tp");
   st[s].act       = GvGet(s, "act");
   st[s].dst       = GvGet(s, "dst");
   st[s].run       = GvGet(s, "run");
   st[s].qty       = GvGet(s, "qty");
   st[s].price     = GvGet(s, "price");
   st[s].placed    = (datetime)(long)GvGet(s, "placed");
   st[s].tradeId   = (datetime)(long)GvGet(s, "tradeId");
   st[s].tpTouched = GvGet(s, "tpTouched") > 0.5;
   st[s].tpHit     = GvGet(s, "tpHit") > 0.5;
   st[s].partDone  = GvGet(s, "partDone") > 0.5;
   st[s].anchored  = GvGet(s, "anchored") > 0.5;
   st[s].ext       = GvGet(s, "ext");
  }

//============================== INIT ==============================
int OnInit()
  {
   g_tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(g_tick <= 0)
      g_tick = _Point;
   g_pt = InpPointSize > 0 ? InpPointSize : g_tick;
   g_hedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   g_persist = !MQLInfoInteger(MQL_TESTER);
   g_pfx = "FG5." + (string)InpMagic + "." + _Symbol + ".";

   if(InpRsiLen < 2 || InpFastLen < 1 || InpAtrLen < 1 || InpPriorDriftBars < 1 || InpQtyStep <= 0 || InpPipSize <= 0)
     {
      Print("FlashGold: invalid input (lengths must be positive, quantity step and pip size above 0)");
      return INIT_PARAMETERS_INCORRECT;
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviation);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);

   // effective timeframes (auto = chart, 2x, 4x)
   int cs = PeriodSeconds((ENUM_TIMEFRAMES)_Period);
   for(int i = 0; i < 7; i++)
     {
      g_tfOk[i] = true;
      g_h[i] = INVALID_HANDLE;
     }
   g_tf[0] = InpAutoTf ? (ENUM_TIMEFRAMES)_Period : Tf(InpParentTf);
   g_tf[1] = InpAutoTf ? (ENUM_TIMEFRAMES)_Period : Tf(InpZoneTf1);
   g_tf[2] = Tf(InpZoneTf2);
   g_tf[3] = Tf(InpZoneTf3);
   if(InpAutoTf)
     {
      g_tfOk[2] = TfFromSeconds(cs * 2, g_tf[2]);
      g_tfOk[3] = TfFromSeconds(cs * 4, g_tf[3]);
     }
   g_tf[4] = Tf(InpZoneTf4);
   g_tf[5] = Tf(InpZoneTf5);
   g_tf[6] = Tf(InpZoneTf6);
   g_use[0] = true;
   g_use[1] = InpUseZone1;
   g_use[2] = InpUseZone2;
   g_use[3] = InpUseZone3;
   g_use[4] = InpUseZone4;
   g_use[5] = InpUseZone5;
   g_use[6] = InpUseZone6;

   for(int i = 0; i < 7; i++)
     {
      if(!g_use[i])
         continue;
      if(!g_tfOk[i])
        {
         PrintFormat("FlashGold: zone %d needs a timeframe MetaTrader does not have (%dx the chart); the zone has no data", i, i == 2 ? 2 : 4);
         continue;
        }
      g_h[i] = iRSI(_Symbol, g_tf[i], InpRsiLen, PRICE_CLOSE);
      if(g_h[i] == INVALID_HANDLE)
         PrintFormat("FlashGold: could not create RSI on %s (zone %d)", EnumToString(g_tf[i]), i);
     }
   if(g_h[0] == INVALID_HANDLE)
      return INIT_FAILED;

   ZeroMemory(st);
   LoadState(LONG_S);
   LoadState(SHORT_S);
   g_lastTry[0] = 0;
   g_lastTry[1] = 0;
   g_lastBar = iTime(_Symbol, _Period, 0);   // the first signal is taken from the first bar that closes after the start
   if(InpShowPanel)
      Comment("FlashGold v5 S: waiting for the first bar close");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   for(int i = 0; i < 7; i++)
      if(g_h[i] != INVALID_HANDLE)
         IndicatorRelease(g_h[i]);
   if(InpShowPanel)
      Comment("");
   if(reason == REASON_REMOVE)
      ObjectsDeleteAll(0, "FG5_");
  }

//============================== TDI / ATR ==============================
// Direction of the fast TDI line on timeframe slot i, as seen at the close of the chart bar that
// ended just before tNew. SMA(n) - SMA(n)[1] has the sign of rsi - rsi[n].
int TdiDir(const int i, const datetime tNew)
  {
   if(g_h[i] == INVALID_HANDLE)
      return NA_DIR;
   int sh = iBarShift(_Symbol, g_tf[i], tNew - 1, false);
   if(sh < 0)
      return NA_DIR;
   // child zone on a higher timeframe: last closed bar instead of the forming one
   if(i > 0 && InpHtfNoRepaint && PeriodSeconds(g_tf[i]) > PeriodSeconds((ENUM_TIMEFRAMES)_Period))
      sh++;
   int n = InpFastLen + 1;
   if(BarsCalculated(g_h[i]) < sh + n + InpRsiLen)
      return NA_DIR;
   double r[];
   if(CopyBuffer(g_h[i], 0, sh, n, r) != n)
      return NA_DIR;
   ArraySetAsSeries(r, true);
   if(r[0] == EMPTY_VALUE || r[n - 1] == EMPTY_VALUE)
      return NA_DIR;
   return r[0] > r[n - 1] ? 1 : (r[0] < r[n - 1] ? -1 : 0);
  }

// Wilder ATR (TradingView ta.atr) at r[0]; r is a series array, r[0] = newest. 0 = not enough bars.
double AtrRma(const MqlRates &r[], const int len)
  {
   int n = ArraySize(r);
   if(n < len + 1)
      return 0.0;
   double atr = 0;
   int cnt = 0;
   for(int k = n - 2; k >= 0; k--)
     {
      double tr = MathMax(r[k].high - r[k].low, MathMax(MathAbs(r[k].high - r[k + 1].close), MathAbs(r[k].low - r[k + 1].close)));
      cnt++;
      if(cnt <= len)
        {
         atr += tr;
         if(cnt == len)
            atr /= len;
        }
      else
         atr = (atr * (len - 1) + tr) / len;
     }
   return atr;
  }

string DirText(const int d) { return d == NA_DIR ? "N/A" : (d > 0 ? "BUY" : (d < 0 ? "SELL" : "MIX")); }

//============================== ORDERS ==============================
double CalcQty(const double slPts)
  {
   double q = InpFixedLots;
   if(InpQtyMode == FG_QTY_RISK)
     {
      double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tv <= 0)
         tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double stopCash = slPts * g_pt / g_tick * tv;   // loss of 1 lot at the stop
      q = stopCash > 0 ? riskCash / stopCash : 0.0;
     }
   q = MathMin(q, InpMaxLots);
   q = MathFloor(q / InpQtyStep + 1e-9) * InpQtyStep;
   return NormVol(q);
  }

// stop loss / take profit prices for an order of side s at price ref; minD = closest stop the broker accepts
double SlFor(const int s, const double ref, const double minD)
  {
   if(st[s].sl <= 0)
      return 0.0;
   double d = MathMax(st[s].sl * g_pt, minD);
   return NormPrice(s == LONG_S ? ref - d : ref + d);
  }

double TpFor(const int s, const double ref, const double minD)
  {
   if(IsRunner() || st[s].tp <= 0)
      return 0.0;   // the runner's target is handled by the EA (partial close + trail)
   double d = MathMax(st[s].tp * g_pt, minD);
   return NormPrice(s == LONG_S ? ref + d : ref - d);
  }

bool SendPending(const int s)
  {
   // netting account: the stop must also close the opposite position, as strategy.entry does
   double vol = NormVol(st[s].qty + (g_hedging ? 0.0 : PosVolume(1 - s)));
   if(vol <= 0)
      return false;
   double price = st[s].price;
   double lvl = StopLevel();
   trade.SetTypeFilling(ORDER_FILLING_RETURN);
   bool ok = trade.OrderOpen(_Symbol, s == LONG_S ? ORDER_TYPE_BUY_STOP : ORDER_TYPE_SELL_STOP, vol, 0.0, price,
                             SlFor(s, price, lvl), TpFor(s, price, lvl), ORDER_TIME_GTC, 0,
                             s == LONG_S ? "FG buy stop" : "FG sell stop");
   trade.SetTypeFillingBySymbol(_Symbol);
   if(!ok)
      Print("FlashGold: entry stop rejected, ", trade.ResultRetcodeDescription());
   return ok;
  }

// Place (or replace) the entry of side s: a stop order at 'price', or a market order when the
// market is already through that price (TradingView fills such a stop at the next open).
void PlaceEntry(const int s, double price, const double q, const datetime tSig)
  {
   int o = 1 - s;
   DeletePending(s);
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   price = NormPrice(price);
   st[s].qty = q;
   st[s].price = price;
   st[s].placed = tSig;
   double lvl = StopLevel();
   bool through = (s == LONG_S) ? (price <= tk.ask) : (price >= tk.bid);
   if(through)
     {
      DeletePending(o);
      st[o].placed = 0;
      ClosePositions(o);
      st[s].placed = 0;
      double minD = lvl + (tk.ask - tk.bid);
      bool ok = (s == LONG_S) ? trade.Buy(q, _Symbol, 0.0, SlFor(s, tk.ask, minD), TpFor(s, tk.ask, minD), "FG buy stop")
                : trade.Sell(q, _Symbol, 0.0, SlFor(s, tk.bid, minD), TpFor(s, tk.bid, minD), "FG sell stop");
      if(!ok)
         Print("FlashGold: market entry rejected, ", trade.ResultRetcodeDescription());
      SaveState(s);
      SaveState(o);
      return;
     }
   // keep the broker's minimum distance from the market
   if(s == LONG_S && price < tk.ask + lvl)
      st[s].price = NormPrice(tk.ask + lvl + g_tick);
   if(s == SHORT_S && price > tk.bid - lvl)
      st[s].price = NormPrice(tk.bid - lvl - g_tick);
   if(!SendPending(s))
      st[s].placed = 0;
   SaveState(s);
  }

// netting account: keep the pending stop's volume = entry quantity + the opposite position
void SyncNettingPending()
  {
   if(g_hedging)
      return;
   for(int s = 0; s < 2; s++)
     {
      ulong ot = FindPending(s);
      if(ot == 0 || st[s].placed == 0 || st[s].qty <= 0 || !OrderSelect(ot))
         continue;
      double have = OrderGetDouble(ORDER_VOLUME_CURRENT);
      double want = NormVol(st[s].qty + PosVolume(1 - s));
      if(want > 0 && MathAbs(have - want) > 1e-8)
         if(trade.OrderDelete(ot))
            SendPending(s);
     }
  }

//============================== POSITION MANAGEMENT (every tick) ==============================
void ManageSide(const int s)
  {
   int o = 1 - s;
   ulong tk = FindPosition(s);
   if(tk == 0)
     {
      if(st[s].tradeId != 0)
        {
         st[s].tradeId = 0;
         SaveState(s);
        }
      return;
     }
   if(!PositionSelectByTicket(tk))
      return;
   datetime tm = (datetime)PositionGetInteger(POSITION_TIME);
   bool changed = false;
   if(tm != st[s].tradeId)
     {
      // a new trade of this side: reset its state, cancel the other entry (OCA) and finish a reversal
      st[s].tradeId   = tm;
      st[s].tpTouched = false;
      st[s].tpHit     = false;
      st[s].partDone  = false;
      st[s].anchored  = false;
      st[s].ext       = PositionGetDouble(POSITION_PRICE_OPEN);
      st[s].placed    = 0;
      DeletePending(o);
      st[o].placed = 0;
      if(FindPosition(o) != 0)
         ClosePositions(o);
      SaveState(o);
      changed = true;
      if(!PositionSelectByTicket(tk))
         return;
     }
   double open  = PositionGetDouble(POSITION_PRICE_OPEN);
   double vol   = PositionGetDouble(POSITION_VOLUME);
   double curSl = PositionGetDouble(POSITION_SL);
   double curTp = PositionGetDouble(POSITION_TP);
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
      return;
   int    sg = (s == LONG_S) ? 1 : -1;
   double px = (s == LONG_S) ? t.bid : t.ask;   // the price this position closes at
   bool   runner = IsRunner();
   bool   canTry = (TimeCurrent() - g_lastTry[s] >= 5);   // do not hammer the server after a rejection

   if(sg * (px - st[s].ext) > 0)
      st[s].ext = px;
   if(st[s].tp > 0 && !st[s].tpTouched && sg * (st[s].ext - open) >= st[s].tp * g_pt)
     {
      st[s].tpTouched = true;
      changed = true;
     }

   // partial close at the take profit level
   if(runner && InpPartPct > 0 && st[s].tpTouched && !st[s].partDone && canTry)
     {
      double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      if(step <= 0)
         step = 0.01;
      double cv = NormalizeDouble(MathFloor(vol * InpPartPct / 100.0 / step + 1e-9) * step, 8);
      bool ok = true;
      if(cv >= vol - 1e-9)
        {
         ok = trade.PositionClose(tk);
         if(ok)
           {
            st[s].partDone = true;
            SaveState(s);
            return;
           }
        }
      else
         if(cv >= vmin - 1e-12)
           {
            if(g_hedging)
               ok = trade.PositionClosePartial(tk, cv);
            else
               ok = (s == LONG_S) ? trade.Sell(cv, _Symbol, 0.0, curSl, curTp, "FG TP part")
                    : trade.Buy(cv, _Symbol, 0.0, curSl, curTp, "FG TP part");
           }
      // a part smaller than the broker's minimum lot is skipped: the whole position runs
      if(ok)
        {
         st[s].partDone = true;
         changed = true;
        }
      else
        {
         g_lastTry[s] = TimeCurrent();
         Print("FlashGold: partial close failed, ", trade.ResultRetcodeDescription());
        }
      if(!PositionSelectByTicket(tk))
        {
         SaveState(s);
         return;
        }
      curSl = PositionGetDouble(POSITION_SL);
      curTp = PositionGetDouble(POSITION_TP);
     }

   // wanted stop: stop loss (or breakeven for the runner) and the trailing stop, whichever is closer
   bool   haveWant = false;
   double want = 0;
   if(runner && InpRunBE && st[s].tpHit)
     {
      want = open;
      haveWant = true;
     }
   else
      if(st[s].sl > 0)
        {
         want = open - sg * st[s].sl * g_pt;
         haveWant = true;
        }
   double act = 0, dst = 0;
   bool hasTrail = false;
   if(runner)
     {
      hasTrail = (st[s].tp > 0);     // the runner's trail starts at the take profit level
      act = st[s].tp;
      dst = st[s].run;
     }
   else
      if(InpUseTrail)
        {
         hasTrail = true;
         act = st[s].act;
         dst = st[s].dst;
        }
   if(hasTrail && dst > 0 && sg * (st[s].ext - open) >= act * g_pt)
     {
      double tr = st[s].ext - sg * dst * g_pt;
      if(!haveWant || sg * (tr - want) > 0)
        {
         want = tr;
         haveWant = true;
        }
     }

   double lvl = StopLevel();
   double newSl = curSl, newTp = curTp;
   bool mod = false;
   if(haveWant)
     {
      want = NormPrice(want);
      if(sg * (px - want) <= 0)
        {
         // the stop is already crossed (breakeven set below the market, or a stop the broker could not hold)
         if(canTry && !trade.PositionClose(tk))
            g_lastTry[s] = TimeCurrent();
         SaveState(s);
         return;
        }
      double lim = NormPrice(px - sg * (lvl + g_tick));   // closest stop the broker accepts now
      double set = (sg * (want - lim) > 0) ? lim : want;
      if(curSl == 0 || !st[s].anchored)
         mod = MathAbs(set - curSl) >= g_tick * 0.5;
      else
         mod = sg * (set - curSl) >= MathMax(InpTrailStepPts * g_pt, g_tick) - g_tick * 0.01;
      if(mod)
         newSl = set;
     }
   if(!st[s].anchored)
     {
      double wantTp = (!runner && st[s].tp > 0) ? NormPrice(open + sg * st[s].tp * g_pt) : 0.0;
      bool tpOk = (wantTp == 0) || (sg * (wantTp - px) > lvl);
      if(tpOk && MathAbs(curTp - wantTp) >= g_tick * 0.5)
        {
         newTp = wantTp;
         mod = true;
        }
     }
   if(mod)
     {
      if(canTry)
        {
         if(trade.PositionModify(tk, newSl, newTp) || trade.ResultRetcode() == TRADE_RETCODE_NO_CHANGES)
           {
            st[s].anchored = true;
            changed = true;
           }
         else
           {
            g_lastTry[s] = TimeCurrent();
            Print("FlashGold: stop modify failed, ", trade.ResultRetcodeDescription());
           }
        }
     }
   else
      if(!st[s].anchored)
        {
         st[s].anchored = true;
         changed = true;
        }
   if(changed)
      SaveState(s);
  }

void ManageAll()
  {
   ManageSide(LONG_S);
   ManageSide(SHORT_S);
   SyncNettingPending();
  }

//============================== VISUALS ==============================
void DrawSignal(const bool isBuy, const datetime tSig, const double barPrice, const double entry)
  {
   if(MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   string id = (isBuy ? "B" : "S") + (string)(long)tSig;
   if(InpShowArrows)
     {
      string n = "FG5_A" + id;
      if(ObjectCreate(0, n, OBJ_ARROW, 0, tSig, barPrice))
        {
         ObjectSetInteger(0, n, OBJPROP_ARROWCODE, isBuy ? 233 : 234);
         ObjectSetInteger(0, n, OBJPROP_COLOR, isBuy ? clrLime : clrRed);
         ObjectSetInteger(0, n, OBJPROP_ANCHOR, isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM);
         ObjectSetString(0, n, OBJPROP_TOOLTIP, (isBuy ? "BUY @ " : "SELL @ ") + DoubleToString(entry, _Digits));
        }
     }
   if(InpShowEntryLines)
     {
      string n = "FG5_L" + id;
      datetime t2 = tSig + (datetime)(MathMax(InpEntryLineBars, 1) * PeriodSeconds((ENUM_TIMEFRAMES)_Period));
      if(ObjectCreate(0, n, OBJ_TREND, 0, tSig, entry, t2, entry))
        {
         ObjectSetInteger(0, n, OBJPROP_COLOR, isBuy ? clrLime : clrRed);
         ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, n, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
        }
     }
  }

//============================== BAR CLOSE LOGIC ==============================
void OnNewBar(const datetime tNew)
  {
   g_barIdx++;
   int need = MathMax(MathMax(InpPriorDriftBars + 1, 3), MathMax(14, InpAtrLen) * 40 + 1);
   need = MathMin(need, Bars(_Symbol, _Period) - 1);
   if(need < 3)
      return;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, _Period, 1, need, r);
   if(got < 3)
      return;
   datetime tSig = r[0].time;       // the bar that just closed
   double c = r[0].close;

   // ---------- price model (indicator) ----------
   double halfSpread = InpSpreadPts * g_pt * 0.5;
   double bid = c - halfSpread, ask = c + halfSpread;
   double midPrice = (bid + ask) * 0.5;
   double midPrev  = r[1].close;

   // ---------- TDI parent and zones ----------
   int pd = TdiDir(0, tNew);
   int parentSide = (pd == NA_DIR) ? 0 : pd;
   int zd[7];
   bool on[7];
   int activeZones = 0, alignedZones = 0, conflictZones = 0, mixedZones = 0;
   for(int z = 1; z <= 6; z++)
     {
      zd[z] = g_use[z] ? TdiDir(z, tNew) : NA_DIR;
      on[z] = g_use[z] && (!InpIgnoreNaZones || zd[z] != NA_DIR);
      if(!on[z])
         continue;
      activeZones++;
      if(zd[z] == NA_DIR)
         continue;
      if(parentSide != 0 && zd[z] == parentSide)
         alignedZones++;
      if(parentSide != 0 && zd[z] == -parentSide)
         conflictZones++;
      if(zd[z] == 0)
         mixedZones++;
     }
   int  requiredAligned   = MathMin(InpMinAlignedZones, activeZones);
   bool parentFlatAllowed = InpAllowNeutralParent && parentSide == 0;
   bool zoneReady         = (activeZones == 0) || (alignedZones >= requiredAligned);
   bool tradeZoneBuyAllowed  = !InpUseTdiTradeZone || ((parentSide == 1  || parentFlatAllowed) && zoneReady);
   bool tradeZoneSellAllowed = !InpUseTdiTradeZone || ((parentSide == -1 || parentFlatAllowed) && zoneReady);

   // ---------- burst / prior drift ----------
   double atrChart = AtrRma(r, 14);
   double atrV     = AtrRma(r, InpAtrLen);
   double atrPts   = atrChart / g_pt;
   bool   unitOk   = (InpDistUnit == FG_UNIT_POINTS) || atrChart > 0;
   double burstThrPts  = InpDistUnit == FG_UNIT_ATR ? InpBurstAtrMult * atrPts     : InpBurstPoints;
   double entryDistPts = InpDistUnit == FG_UNIT_ATR ? InpEntryDistAtrMult * atrPts : InpEntryDistPoints;
   double holdFavPts   = InpDistUnit == FG_UNIT_ATR ? InpHoldFavAtrMult * atrPts   : InpHoldMinFavPoints;

   double burstPts  = (midPrice - midPrev) / g_pt;
   bool   burstBuy  = unitOk && burstPts >= burstThrPts;
   bool   burstSell = unitOk && burstPts <= -burstThrPts;
   bool   haveDrift = got > InpPriorDriftBars;
   double priorDriftPts = haveDrift ? (midPrice - r[InpPriorDriftBars].close) / g_pt : 0.0;
   bool   priorBuyOk  = !InpUsePriorFilter || (haveDrift && priorDriftPts > 0);
   bool   priorSellOk = !InpUsePriorFilter || (haveDrift && priorDriftPts < 0);

   bool rawBuy  = InpUseAnyCombo ? (tradeZoneBuyAllowed  && (!InpUseBurstGate || burstBuy  || parentSide == 1))
                  : (tradeZoneBuyAllowed  && burstBuy);
   bool rawSell = InpUseAnyCombo ? (tradeZoneSellAllowed && (!InpUseBurstGate || burstSell || parentSide == -1))
                  : (tradeZoneSellAllowed && burstSell);
   bool buyCandidate  = unitOk && rawBuy  && priorBuyOk;
   bool sellCandidate = unitOk && rawSell && priorSellOk;

   // ---------- entry hold / virtual stop (indicator) ----------
   double buyEntryPrice = 0, sellEntryPrice = 0;
   bool   buySignal = false, sellSignal = false;
   bool   canFire = !InpOneEntryPerBar || lastEntryBar < 0 || lastEntryBar != g_barIdx;

   if(buyCandidate && canFire)
     {
      if(InpEntryHoldBars == 0)
        {
         buyEntryPrice = ask + entryDistPts * g_pt;
         buySignal = true;
         lastEntryBar = g_barIdx;
        }
      else
         if(!holdActive)
           {
            holdActive = true;
            holdIsBuy = true;
            holdSignalBar = g_barIdx;
            holdSignalMid = midPrice;
           }
         else
            if(holdIsBuy)
              {
               long   elapsedBars = g_barIdx - holdSignalBar;
               double holdMovePoints = (midPrice - holdSignalMid) / g_pt;
               if(elapsedBars >= InpEntryHoldBars && holdMovePoints >= holdFavPts)
                 {
                  buyEntryPrice = ask + entryDistPts * g_pt;
                  buySignal = true;
                  lastEntryBar = g_barIdx;
                  holdActive = false;
                 }
              }
     }
   if(sellCandidate && canFire)
     {
      if(InpEntryHoldBars == 0)
        {
         sellEntryPrice = bid - entryDistPts * g_pt;
         sellSignal = true;
         lastEntryBar = g_barIdx;
        }
      else
         if(!holdActive)
           {
            holdActive = true;
            holdIsBuy = false;
            holdSignalBar = g_barIdx;
            holdSignalMid = midPrice;
           }
         else
            if(!holdIsBuy)
              {
               long   elapsedBars = g_barIdx - holdSignalBar;
               double holdMovePoints = (holdSignalMid - midPrice) / g_pt;
               if(elapsedBars >= InpEntryHoldBars && holdMovePoints >= holdFavPts)
                 {
                  sellEntryPrice = bid - entryDistPts * g_pt;
                  sellSignal = true;
                  lastEntryBar = g_barIdx;
                  holdActive = false;
                 }
              }
     }
   if(holdActive && ((holdIsBuy && !tradeZoneBuyAllowed) || (!holdIsBuy && !tradeZoneSellAllowed)))
     {
      holdActive = false;
      holdSignalBar = -1;
      holdSignalMid = 0;
     }

   // ---------- exit geometry, in points (0 = none) ----------
   double pipTicks = InpPipSize / g_pt;
   double slNow = 0, tpNow = 0;
   if(InpExitMode == FG_EXIT_POINTS)
     {
      slNow = InpSlPoints;
      tpNow = InpTpPoints;
     }
   else
      if(InpExitMode == FG_EXIT_PIPS)
        {
         slNow = InpSlPips * pipTicks;
         tpNow = slNow * InpTpRPips;
        }
      else
        {
         slNow = atrV > 0 ? InpSlAtrMult * atrV / g_pt : 0.0;
         tpNow = slNow * InpTpR;
        }
   double trailActNow = InpExitMode == FG_EXIT_POINTS ? InpTrailActPoints
                        : InpExitMode == FG_EXIT_PIPS ? InpTrailActPips * pipTicks : InpTrailActAtr * atrPts;
   double trailDstNow = InpExitMode == FG_EXIT_POINTS ? InpTrailPoints
                        : InpExitMode == FG_EXIT_PIPS ? MathMax(InpTrailPips * pipTicks, 1.0) : MathMax(InpTrailDstAtr * atrPts, 1.0);
   double runDstNow   = InpExitMode == FG_EXIT_POINTS ? InpRunTrailPts
                        : InpExitMode == FG_EXIT_PIPS ? MathMax(InpRunTrailPips * pipTicks, 1.0) : MathMax(InpRunTrailAtr * atrV / g_pt, 1.0);
   bool exitOk = (InpExitMode != FG_EXIT_ATR) || atrV > 0;   // ATR exits need an ATR value

   // ---------- orders ----------
   bool allowL  = InpDirection != FG_DIR_SHORT;
   bool allowS  = InpDirection != FG_DIR_LONG;
   bool inLong  = FindPosition(LONG_S) != 0;
   bool inShort = FindPosition(SHORT_S) != 0;
   bool flat    = !inLong && !inShort;

   if(InpExitOnOpposite && sellSignal && inLong)
      ClosePositions(LONG_S);
   if(InpExitOnOpposite && buySignal && inShort)
      ClosePositions(SHORT_S);

   if(buySignal && allowL && exitOk && !inLong && (flat || InpAllowReverse || InpExitOnOpposite))
     {
      double qL = CalcQty(slNow);
      if(qL > 0)
        {
         st[LONG_S].sl  = slNow;
         st[LONG_S].tp  = tpNow;
         st[LONG_S].act = trailActNow;
         st[LONG_S].dst = trailDstNow;
         st[LONG_S].run = runDstNow;
         PlaceEntry(LONG_S, buyEntryPrice, qL, tSig);
        }
      else
         Print("FlashGold: buy signal skipped, quantity is 0 (check the sizing inputs and the minimum lot)");
     }
   if(sellSignal && allowS && exitOk && !inShort && (flat || InpAllowReverse || InpExitOnOpposite))
     {
      double qS = CalcQty(slNow);
      if(qS > 0)
        {
         st[SHORT_S].sl  = slNow;
         st[SHORT_S].tp  = tpNow;
         st[SHORT_S].act = trailActNow;
         st[SHORT_S].dst = trailDstNow;
         st[SHORT_S].run = runDstNow;
         PlaceEntry(SHORT_S, sellEntryPrice, qS, tSig);
        }
      else
         Print("FlashGold: sell signal skipped, quantity is 0 (check the sizing inputs and the minimum lot)");
     }

   // cancel a stale unfilled entry
   if(InpEntryValidBars > 0)
      for(int s = 0; s < 2; s++)
        {
         ulong ot = FindPending(s);
         if(ot == 0)
            continue;
         if(st[s].placed == 0 && OrderSelect(ot))   // state lost: rebuild it from the order's setup time
            st[s].placed = iTime(_Symbol, _Period, iBarShift(_Symbol, _Period, (datetime)OrderGetInteger(ORDER_TIME_SETUP), false) + 1);
         int barsSince = iBarShift(_Symbol, _Period, st[s].placed, false) - 1;
         if(barsSince >= InpEntryValidBars && FindPosition(s) == 0)
           {
            DeletePending(s);
            st[s].placed = 0;
            SaveState(s);
           }
        }

   // runner breakeven: applied from the close of the bar that reached the take profit level
   for(int s = 0; s < 2; s++)
      if(st[s].tpTouched && !st[s].tpHit && FindPosition(s) != 0)
        {
         st[s].tpHit = true;
         SaveState(s);
        }

   // time stop
   if(InpMaxBarsHeld > 0)
      for(int s = 0; s < 2; s++)
        {
         ulong tk = FindPosition(s);
         if(tk == 0 || !PositionSelectByTicket(tk))
            continue;
         int heldBars = iBarShift(_Symbol, _Period, (datetime)PositionGetInteger(POSITION_TIME), false) - 1;
         if(heldBars >= InpMaxBarsHeld)
           {
            ClosePositions(LONG_S);
            ClosePositions(SHORT_S);
            break;
           }
        }

   ManageAll();

   // ---------- visuals ----------
   if(buySignal)
      DrawSignal(true, tSig, r[0].low, buyEntryPrice);
   if(sellSignal)
      DrawSignal(false, tSig, r[0].high, sellEntryPrice);
   if(InpShowPanel && !MQLInfoInteger(MQL_OPTIMIZATION))
     {
      string risk = (alignedZones >= requiredAligned && conflictZones == 0) ? "LOW" : (alignedZones >= requiredAligned ? "MIX" : "HIGH");
      double lv = PosVolume(LONG_S), sv = PosVolume(SHORT_S);
      string pos = lv > 0 ? "LONG " + DoubleToString(lv, 2) : (sv > 0 ? "SHORT " + DoubleToString(sv, 2) : "flat");
      string txt = "FlashGold v5 S | TDI FILTER\n";
      txt += "Parent: " + DirText(parentSide) + "\n";
      txt += StringFormat("Aligned: %d/%d   Conflict: %d   Mixed: %d   Risk: %s\n", alignedZones, activeZones, conflictZones, mixedZones, risk);
      txt += "Z1 / Z2: " + DirText(zd[1]) + " / " + DirText(zd[2]) + "\n";
      txt += "Z3 / Z4: " + DirText(zd[3]) + " / " + DirText(zd[4]) + "\n";
      txt += "Z5 / Z6: " + DirText(zd[5]) + " / " + DirText(zd[6]) + "\n";
      txt += StringFormat("ATR / burst / dist / SL pts: %.0f / %.0f / %.0f / %.0f\n", atrV / g_pt, burstThrPts, entryDistPts, slNow);
      txt += StringFormat("SL / TP in price: %.2f / %.2f\n", slNow * g_pt, tpNow * g_pt);
      txt += "Position: " + pos;
      Comment(txt);
     }
  }

//============================== EVENTS ==============================
void OnTick()
  {
   // bar-close logic first, so a take profit touched on this very tick is not treated as a closed bar
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 != 0 && t0 != g_lastBar)
     {
      g_lastBar = t0;
      OnNewBar(t0);
     }
   ManageAll();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   // react to a fill at once: cancel the other entry, finish a reversal, re-base the stops
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD && trans.symbol == _Symbol)
      ManageAll();
  }
//+------------------------------------------------------------------+
