//+------------------------------------------------------------------+
//| FlashGold v5 Strategy (BTCUSD) - MQL5 Expert Advisor             |
//| Port of FlashGold_v5_Strategy_BTCUSD.pine (TradingView strategy  |
//| conversion of "FlashGold Continuation v5 - TDI Trade Zone        |
//| Filter", (c) ghostsmartfire).                                    |
//| Subject to the terms of the Mozilla Public License 2.0,          |
//| https://mozilla.org/MPL/2.0/                                     |
//+------------------------------------------------------------------+
// What is ported 1:1 from the Pine strategy
//  - price model: bid/ask = bar close -/+ half of the "Spread pts" input
//  - TDI direction per timeframe: RSI -> SMA fast, fast rising = BUY, falling = SELL
//  - parent + six child zones alignment filter, burst gate, prior-drift filter,
//    entry hold, one entry per bar
//  - entry = STOP order at ask + entry distance (buy) / bid - entry distance (sell),
//    cancelled after N bars, one-cancels-other between the two sides
//  - exits: SL / TP in Pips, ATR or Points, locked at signal time; Fixed style with
//    optional trailing stop, or Partial + runner (partial at TP, runner to breakeven
//    from the next bar, trail from the TP level); time stop; exit / reverse on the
//    opposite signal; Fixed or Risk % sizing
//  - signals are evaluated once per closed bar (first tick of the next bar)
//
// Where MetaTrader differs from TradingView (read before trading)
//  - "Points" = _Point of the broker symbol (Pine: syminfo.mintick). Check that your
//    broker's BTCUSD point is 0.01, otherwise rescale the Points inputs.
//  - Quantity is in LOTS. The Pine default was 10 contracts (= 10 BTC); the default
//    here is 0.10 lot. Check the contract size of your symbol.
//  - Auto timeframes uses chart, 2x and 4x the chart. MetaTrader only has fixed
//    timeframes; when 2x or 4x does not exist (for example 4x H4) that zone has no
//    data and is dropped ("Ignore zones without data") or counts as MIX.
//  - ATR is Wilder's (RMA), computed in the EA, to match ta.atr. iATR is not used.
//  - The stop loss (and the Fixed-style take profit) sit on the broker side. The
//    partial close, the breakeven move and the trailing stop are done by the EA on
//    ticks, so they only work while the terminal is running.
//  - A buy stop triggers on Ask and a long exits on Bid (real spread), in addition
//    to the modelled spread used for the entry price.
//  - Chart labels, lines and the table are replaced by a text panel (Comment).
#property copyright "Port of FlashGold v5 Strategy (BTCUSD). MPL 2.0"
#property link      "https://mozilla.org/MPL/2.0/"
#property version   "1.00"
#property description "FlashGold v5 Strategy (BTCUSD): TDI trade-zone filter + burst gate, stop entries,"
#property description "SL / TP in pips, ATR or points, partial take profit with a trailed runner."

#include <Trade\Trade.mqh>

enum ENUM_FG_UNIT   { FG_UNIT_ATR = 0,    /* ATR */      FG_UNIT_POINTS = 1  /* Points */ };
enum ENUM_FG_DIR    { FG_DIR_BOTH = 0,    /* Both */     FG_DIR_LONG = 1,    /* Long */  FG_DIR_SHORT = 2 /* Short */ };
enum ENUM_FG_EXIT   { FG_EXIT_PIPS = 0,   /* Pips */     FG_EXIT_ATR = 1,    /* ATR */   FG_EXIT_POINTS = 2 /* Points */ };
enum ENUM_FG_TPSTYLE{ FG_TP_FIXED = 0,    /* Fixed */    FG_TP_PARTIAL = 1   /* Partial + runner */ };
enum ENUM_FG_QTY    { FG_QTY_FIXED = 0,   /* Fixed */    FG_QTY_RISK = 1     /* Risk % */ };

input group "FlashGold Core"
input double InpSpreadPoints       = 25.0;   // Spread pts (half offsets bid and ask)
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
input ENUM_TIMEFRAMES InpParentTf  = PERIOD_H1; // Parent obedience timeframe (Auto off)
input int    InpRsiLen             = 14;     // TDI RSI length
input int    InpFastLen            = 2;      // TDI white fast length
input int    InpSlowLen            = 7;      // TDI slow length (panel only)
input int    InpMinAlignedZones    = 2;      // Minimum child zones aligned (0..6)
input bool   InpAllowNeutralParent = false;  // Allow trade if parent is flat
input bool   InpIgnoreNaZones      = true;   // Ignore zones without data
input bool   InpHtfNoRepaint       = true;   // Higher-TF zones use the last CLOSED bar
input bool   InpShowPanel          = true;   // Show TDI zone panel
input bool   InpUseZone1           = true;   // Use child zone 1
input ENUM_TIMEFRAMES InpZoneTf1   = PERIOD_H1; // Zone 1 timeframe (Auto off)
input bool   InpUseZone2           = true;   // Use child zone 2
input ENUM_TIMEFRAMES InpZoneTf2   = PERIOD_H2; // Zone 2 timeframe (Auto off)
input bool   InpUseZone3           = true;   // Use child zone 3
input ENUM_TIMEFRAMES InpZoneTf3   = PERIOD_H4; // Zone 3 timeframe (Auto off)
input bool   InpUseZone4           = false;  // Use child zone 4
input ENUM_TIMEFRAMES InpZoneTf4   = PERIOD_H8; // Zone 4 timeframe
input bool   InpUseZone5           = false;  // Use child zone 5
input ENUM_TIMEFRAMES InpZoneTf5   = PERIOD_M1; // Zone 5 timeframe
input bool   InpUseZone6           = false;  // Use child zone 6
input ENUM_TIMEFRAMES InpZoneTf6   = PERIOD_M2; // Zone 6 timeframe
input bool   InpAutoTf             = true;   // Auto timeframes (parent/zone1 = chart, zone2 = 2x, zone3 = 4x)

input group "S1. Entry order"
input ENUM_FG_DIR InpDirection     = FG_DIR_BOTH; // Direction
input int    InpEntryValidBars     = 3;      // Cancel unfilled entry after N bars (0 = keep)
input bool   InpAllowReverse       = true;   // Opposite signal may reverse an open position
input bool   InpExitOnOpposite     = false;  // Close at market on the opposite signal

input group "S2. Exits"
input ENUM_FG_EXIT InpExitMode     = FG_EXIT_PIPS; // SL / TP / trail unit
input double InpPipSize            = 1.0;    // Pip size, price units (Pips mode)
input double InpSlPips             = 30;     // Stop loss, pips (Pips mode)
input double InpTpRPips            = 5;      // Take profit, R multiple of SL (Pips mode)
input double InpRunTrailPips       = 600;    // Runner: trail distance, pips (Pips mode)
input double InpTrailActPips       = 150;    // Trail activation, pips of profit (Pips, Fixed style)
input double InpTrailPips          = 600;    // Trail distance, pips (Pips, Fixed style)
input double InpSlPoints           = 3900;   // Stop loss, pts (Points mode)
input double InpTpPoints           = 19500;  // Take profit, pts (Points mode)
input int    InpAtrLen             = 14;     // ATR length (ATR mode)
input double InpSlAtrMult          = 0.1;    // Stop loss, ATR mult (ATR mode)
input double InpTpR                = 2.0;    // Take profit, R multiple of SL (ATR mode)
input bool   InpUseTrail           = false;  // Trailing stop (Fixed style)
input double InpTrailActPoints     = 4500;   // Trail activation, pts of profit (Points mode)
input double InpTrailPoints        = 1000;   // Trail distance, pts (Points mode)
input double InpTrailActAtr        = 1.0;    // Trail activation, ATR mult (ATR mode)
input double InpTrailDstAtr        = 0.25;   // Trail distance, ATR mult (ATR mode)
input int    InpMaxBarsHeld        = 0;      // Time stop, bars (0 = off)
input ENUM_FG_TPSTYLE InpTpStyle   = FG_TP_PARTIAL; // Take profit style
input double InpPartPct            = 30;     // Partial: % closed at the take profit
input bool   InpRunBE              = true;   // Runner: stop to breakeven after the take profit
input double InpRunTrailAtr        = 1.5;    // Runner: trail distance, ATR mult (ATR mode)
input double InpRunTrailPts        = 58000;  // Runner: trail distance, pts (Points mode)

input group "S3. Sizing"
input ENUM_FG_QTY InpQtyMode       = FG_QTY_FIXED; // Quantity
input double InpFixedQty           = 0.10;   // Fixed quantity, lots (Pine default was 10 BTC)
input double InpRiskPct            = 1.0;    // Risk % of equity per trade (Risk mode)
input double InpMaxQty             = 50;     // Max quantity, lots
input double InpQtyStep            = 0.01;   // Quantity step (rounds down)

input group "EA"
input long   InpMagic              = 50526;  // Magic number
input int    InpDeviationPoints    = 50;     // Max slippage for market orders, points

//--- constants
#define NA_DIR   99      // "no data" for a TDI direction (Pine na)
#define NA_VAL  -1.0     // "no value" for distances in points (Pine na)
#define ZN       7       // slot 0 = parent, 1..6 = child zones

//--- globals
CTrade          trade;
bool            g_hedging = false;
ENUM_TIMEFRAMES g_tf[ZN];
int             g_h[ZN];
bool            g_use[ZN];
bool            g_ok[ZN];
datetime        g_lastBar = 0;
long            g_barIdx = 0;          // index of the last closed bar (Pine bar_index)

// entry hold (Pine var state)
bool   g_holdActive = false;
bool   g_holdIsBuy = false;
long   g_holdSignalBar = -1;
double g_holdSignalMid = 0;
long   g_lastEntryBar = -1;

// per side pending locks: 0 = long, 1 = short
double g_pSl[2], g_pTp[2], g_pAct[2], g_pDst[2], g_pRun[2], g_pQty[2];
long   g_placedBar[2];

// open trade state
ulong  g_posTicket = 0;
int    g_posType = -1;
double g_lockSl = NA_VAL, g_lockTp = NA_VAL, g_lockAct = 0, g_lockDst = 1, g_lockRun = 1;
double g_initVol = 0, g_best = 0;
bool   g_tpReached = false, g_beOn = false, g_partialDone = false, g_aligned = false;

// panel values
int    g_dir[ZN];
int    g_aligned_n = 0, g_active_n = 0, g_conflict_n = 0, g_mixed_n = 0;
double g_atrV = 0, g_burstThr = 0, g_entryDist = 0, g_slNow = NA_VAL, g_tpNow = NA_VAL;

//+------------------------------------------------------------------+
//| helpers                                                          |
//+------------------------------------------------------------------+
double TickSize()
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return(ts > 0 ? ts : _Point);
  }

double NormPrice(const double p)
  {
   double ts = TickSize();
   return(NormalizeDouble(MathRound(p / ts) * ts, _Digits));
  }

double VolStep()
  {
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   return(st > 0 ? st : 0.01);
  }

// rounds down to the broker volume step, 0 when below the minimum
double NormVol(const double v)
  {
   double st = VolStep();
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double q = MathFloor(v / st + 1e-9) * st;
   if(mx > 0 && q > mx)
      q = mx;
   if(q < mn - 1e-12)
      return(0.0);
   return(NormalizeDouble(q, 8));
  }

bool TfFromSeconds(const int sec, ENUM_TIMEFRAMES &tf)
  {
   static const ENUM_TIMEFRAMES all[] =
     {
      PERIOD_M1, PERIOD_M2, PERIOD_M3, PERIOD_M4, PERIOD_M5, PERIOD_M6, PERIOD_M10, PERIOD_M12, PERIOD_M15,
      PERIOD_M20, PERIOD_M30, PERIOD_H1, PERIOD_H2, PERIOD_H3, PERIOD_H4, PERIOD_H6, PERIOD_H8, PERIOD_H12,
      PERIOD_D1, PERIOD_W1, PERIOD_MN1
     };
   for(int i = 0; i < ArraySize(all); i++)
      if(PeriodSeconds(all[i]) == sec)
        {
         tf = all[i];
         return(true);
        }
   return(false);
  }

string DirText(const int d)
  {
   return(d == NA_DIR ? "N/A" : d > 0 ? "BUY" : d < 0 ? "SELL" : "MIX");
  }

// Wilder ATR (RMA of true range), the same smoothing as Pine ta.atr. 0 = not enough bars.
double WilderATR(const int len, const int shift)
  {
   int avail = Bars(_Symbol, _Period) - shift;
   if(len < 1 || avail < len + 1)
      return(0.0);
   int n = MathMin(len * 21 + 1, avail);
   MqlRates r[];
   if(CopyRates(_Symbol, _Period, shift, n, r) != n)
      return(0.0);
   double atr = 0.0;
   for(int i = 1; i < n; i++)
     {
      double tr = MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
      if(i <= len)
        {
         atr += tr;
         if(i == len)
            atr /= len;
        }
      else
         atr = (atr * (len - 1) + tr) / len;
     }
   return(atr);
  }

// TDI direction of slot i as Pine sees it at the close of the last closed chart bar.
// t0 = open time of the forming chart bar, t1 = open time of the last closed chart bar.
int ZoneDir(const int i, const bool lastClosedHigher, const datetime t0, const datetime t1)
  {
   if(!g_ok[i] || g_h[i] == INVALID_HANDLE)
      return(NA_DIR);
   ENUM_TIMEFRAMES tf = g_tf[i];
   bool higher = PeriodSeconds(tf) > PeriodSeconds(_Period);
   int s;
   if(lastClosedHigher && higher)
     {
      // lookahead_on + [1]: the bar before the higher-TF bar that contains the chart bar
      s = iBarShift(_Symbol, tf, t1, false);
      if(s < 0)
         return(NA_DIR);
      s += 1;
     }
   else
     {
      // the latest bar of that timeframe that started before the chart bar closed
      s = iBarShift(_Symbol, tf, t0 - 1, false);
      if(s < 0)
         return(NA_DIR);
     }
   int need = InpFastLen + 1;
   if(BarsCalculated(g_h[i]) < s + need + InpRsiLen)
      return(NA_DIR);
   double r[];
   if(CopyBuffer(g_h[i], 0, s, need, r) != need)
      return(NA_DIR);
   double fNow = 0.0, fPrev = 0.0;
   for(int k = 0; k < need; k++)
     {
      if(r[k] == EMPTY_VALUE)
         return(NA_DIR);
      if(k >= 1)
         fNow += r[k];        // newest InpFastLen values
      if(k < need - 1)
         fPrev += r[k];       // the same window one bar earlier
     }
   fNow /= InpFastLen;
   fPrev /= InpFastLen;
   return(fNow > fPrev ? 1 : fNow < fPrev ? -1 : 0);
  }

// exit distances "now" in points (Pine slTicksNow, tpTicksNow, trailActNow, trailDstNow, runDstNow)
void ExitDistancesNow(const double atr14, const double atrV, double &sl, double &tp, double &act, double &dst, double &run)
  {
   double pt = _Point;
   double pipTicks = InpPipSize / pt;
   double atrPts = atr14 / pt;
   if(InpExitMode == FG_EXIT_POINTS)
      sl = InpSlPoints;
   else
      if(InpExitMode == FG_EXIT_PIPS)
         sl = InpSlPips * pipTicks;
      else
         sl = (atrV > 0 ? InpSlAtrMult * atrV / pt : NA_VAL);
   if(InpExitMode == FG_EXIT_POINTS)
      tp = InpTpPoints;
   else
      tp = (sl == NA_VAL ? NA_VAL : sl * (InpExitMode == FG_EXIT_PIPS ? InpTpRPips : InpTpR));
   act = (InpExitMode == FG_EXIT_POINTS ? InpTrailActPoints : InpExitMode == FG_EXIT_PIPS ? InpTrailActPips * pipTicks : InpTrailActAtr * atrPts);
   dst = (InpExitMode == FG_EXIT_POINTS ? InpTrailPoints : InpExitMode == FG_EXIT_PIPS ? MathMax(InpTrailPips * pipTicks, 1.0) : MathMax(InpTrailDstAtr * atrPts, 1.0));
   run = (InpExitMode == FG_EXIT_POINTS ? InpRunTrailPts : InpExitMode == FG_EXIT_PIPS ? MathMax(InpRunTrailPips * pipTicks, 1.0) : MathMax(InpRunTrailAtr * atrV / pt, 1.0));
  }

// Pine calcQty, then the broker volume limits
double CalcQty(const double slTicks)
  {
   double q = InpFixedQty;
   if(InpQtyMode == FG_QTY_RISK)
     {
      double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
      double stopCash = (slTicks > 0 && ts > 0) ? slTicks * _Point / ts * tv : 0.0;
      q = (stopCash > 0 ? riskCash / stopCash : 0.0);
     }
   q = MathMin(q, InpMaxQty);
   if(InpQtyStep > 0)
      q = MathFloor(q / InpQtyStep + 1e-9) * InpQtyStep;
   return(NormVol(q));
  }

//+------------------------------------------------------------------+
//| positions and orders of this EA                                  |
//+------------------------------------------------------------------+
void FindPositions(ulong &longT, ulong &shortT)
  {
   longT = 0;
   shortT = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
         longT = t;
      else
         shortT = t;
     }
  }

double PositionVolume(const ulong ticket)
  {
   if(ticket == 0 || !PositionSelectByTicket(ticket))
      return(0.0);
   return(PositionGetDouble(POSITION_VOLUME));
  }

// side: 0 = buy stops, 1 = sell stops, -1 = both
void DeletePending(const int side)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;
      ENUM_ORDER_TYPE ot = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if((ot == ORDER_TYPE_BUY_STOP && side != 1) || (ot == ORDER_TYPE_SELL_STOP && side != 0))
         trade.OrderDelete(t);
     }
  }

// reduces a position by vol (partial close). Netting accounts need an opposite deal.
bool ReduceVolume(const ulong ticket, const bool isLong, const double vol, const string comment)
  {
   if(g_hedging)
      return(trade.PositionClosePartial(ticket, vol));
   if(isLong)
      return(trade.Sell(vol, _Symbol, 0, 0, 0, comment));
   return(trade.Buy(vol, _Symbol, 0, 0, 0, comment));
  }

void ResetTradeState()
  {
   g_posTicket = 0;
   g_posType = -1;
   g_lockSl = NA_VAL;
   g_lockTp = NA_VAL;
   g_lockAct = 0;
   g_lockDst = 1;
   g_lockRun = 1;
   g_initVol = 0;
   g_best = 0;
   g_tpReached = false;
   g_beOn = false;
   g_partialDone = false;
   g_aligned = false;
  }

//+------------------------------------------------------------------+
//| state that must survive a terminal restart                       |
//+------------------------------------------------------------------+
void GV(const string key, double &v, const bool save)
  {
   string n = StringFormat("FG5_%I64d_%s_%s", InpMagic, _Symbol, key);
   if(save)
      GlobalVariableSet(n, v);
   else
      if(GlobalVariableCheck(n))
         v = GlobalVariableGet(n);
  }

void State(const bool save)
  {
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   double tk = (double)g_posTicket, ty = (double)g_posType;
   double f1 = g_tpReached, f2 = g_beOn, f3 = g_partialDone, f4 = g_aligned;
   GV("ticket", tk, save);
   GV("type", ty, save);
   GV("lockSl", g_lockSl, save);
   GV("lockTp", g_lockTp, save);
   GV("lockAct", g_lockAct, save);
   GV("lockDst", g_lockDst, save);
   GV("lockRun", g_lockRun, save);
   GV("initVol", g_initVol, save);
   GV("best", g_best, save);
   GV("tpReached", f1, save);
   GV("beOn", f2, save);
   GV("partialDone", f3, save);
   GV("aligned", f4, save);
   for(int s = 0; s < 2; s++)
     {
      string p = (s == 0 ? "L_" : "S_");
      GV(p + "sl", g_pSl[s], save);
      GV(p + "tp", g_pTp[s], save);
      GV(p + "act", g_pAct[s], save);
      GV(p + "dst", g_pDst[s], save);
      GV(p + "run", g_pRun[s], save);
      GV(p + "qty", g_pQty[s], save);
     }
   if(!save)
     {
      g_posTicket = (ulong)tk;
      g_posType = (int)ty;
      g_tpReached = (f1 != 0);
      g_beOn = (f2 != 0);
      g_partialDone = (f3 != 0);
      g_aligned = (f4 != 0);
     }
  }

//+------------------------------------------------------------------+
//| init / deinit                                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpRsiLen < 2 || InpFastLen < 1 || InpPriorDriftBars < 1 || InpAtrLen < 1 || InpPipSize <= 0)
     {
      Print("FlashGold v5: invalid inputs (RSI length >= 2, fast length >= 1, prior drift bars >= 1, ATR length >= 1, pip size > 0).");
      return(INIT_PARAMETERS_INCORRECT);
     }
   g_hedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpDeviationPoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   ENUM_TIMEFRAMES cur = Period();
   int chartSec = PeriodSeconds(cur);
   for(int i = 0; i < ZN; i++)
     {
      g_h[i] = INVALID_HANDLE;
      g_ok[i] = true;
      g_dir[i] = NA_DIR;
     }
   g_use[0] = true;
   g_use[1] = InpUseZone1;
   g_use[2] = InpUseZone2;
   g_use[3] = InpUseZone3;
   g_use[4] = InpUseZone4;
   g_use[5] = InpUseZone5;
   g_use[6] = InpUseZone6;
   g_tf[0] = InpAutoTf ? cur : InpParentTf;
   g_tf[1] = InpAutoTf ? cur : InpZoneTf1;
   g_tf[2] = InpZoneTf2;
   g_tf[3] = InpZoneTf3;
   g_tf[4] = InpZoneTf4;
   g_tf[5] = InpZoneTf5;
   g_tf[6] = InpZoneTf6;
   if(InpAutoTf)
     {
      g_ok[2] = TfFromSeconds(chartSec * 2, g_tf[2]);
      g_ok[3] = TfFromSeconds(chartSec * 4, g_tf[3]);
      if(g_use[2] && !g_ok[2])
         PrintFormat("FlashGold v5: MetaTrader has no timeframe of 2x %s. Child zone 2 has no data.", EnumToString(cur));
      if(g_use[3] && !g_ok[3])
         PrintFormat("FlashGold v5: MetaTrader has no timeframe of 4x %s. Child zone 3 has no data.", EnumToString(cur));
     }
   for(int i = 0; i < ZN; i++)
     {
      if(g_tf[i] == PERIOD_CURRENT)
         g_tf[i] = cur;
      if(!g_use[i] || !g_ok[i])
         continue;
      g_h[i] = iRSI(_Symbol, g_tf[i], InpRsiLen, PRICE_CLOSE);
      if(g_h[i] == INVALID_HANDLE)
        {
         PrintFormat("FlashGold v5: cannot create RSI on %s (error %d).", EnumToString(g_tf[i]), GetLastError());
         return(INIT_FAILED);
        }
     }
   for(int s = 0; s < 2; s++)
     {
      g_pSl[s] = NA_VAL;
      g_pTp[s] = NA_VAL;
      g_pAct[s] = 0;
      g_pDst[s] = 1;
      g_pRun[s] = 1;
      g_pQty[s] = 0;
      g_placedBar[s] = -1;
     }
   ResetTradeState();
   State(false);
   g_lastBar = 0;
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   for(int i = 0; i < ZN; i++)
      if(g_h[i] != INVALID_HANDLE)
         IndicatorRelease(g_h[i]);
   State(true);
   if(InpShowPanel)
      Comment("");
  }

//+------------------------------------------------------------------+
//| entry order (Pine strategy.entry with a stop price)              |
//+------------------------------------------------------------------+
void PlaceEntry(const bool isBuy, const double rawPrice, const double qty, const double slTicks, const double tpTicks)
  {
   int side = isBuy ? 0 : 1;
   DeletePending(side);                       // the same order id replaces the previous one
   double pt = _Point;
   double price = NormPrice(rawPrice);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stopLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * pt;
   bool fixedStyle = !(InpTpStyle == FG_TP_PARTIAL && InpPartPct < 100);
   ulong longT, shortT;
   FindPositions(longT, shortT);
   ulong oppT = isBuy ? shortT : longT;
   double oppVol = PositionVolume(oppT);
   // on a netting account the order must also cover the opposite position to reverse it
   double vol = g_hedging ? qty : NormVol(qty + oppVol);
   if(vol <= 0)
      return;
   bool asStop = isBuy ? (price > ask + stopLvl) : (price < bid - stopLvl);
   double ref = asStop ? price : (isBuy ? ask : bid);
   double sl = (slTicks > 0 ? NormPrice(isBuy ? ref - slTicks * pt : ref + slTicks * pt) : 0.0);
   double tp = (fixedStyle && tpTicks > 0 ? NormPrice(isBuy ? ref + tpTicks * pt : ref - tpTicks * pt) : 0.0);
   bool ok;
   if(asStop)
     {
      ok = isBuy ? trade.BuyStop(vol, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG buy stop")
                 : trade.SellStop(vol, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG sell stop");
     }
   else
     {
      // price is already through the entry level: Pine fills such a stop at the next bar's open
      if(g_hedging && oppT != 0)
         trade.PositionClose(oppT);
      ok = isBuy ? trade.Buy(vol, _Symbol, 0, sl, tp, "FG buy") : trade.Sell(vol, _Symbol, 0, sl, tp, "FG sell");
     }
   if(!ok)
      PrintFormat("FlashGold v5: %s entry failed, retcode %u (%s).", isBuy ? "buy" : "sell", trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }

// netting only: keep a pending reversal order's volume = quantity + the opposite position
void SyncPendingNetting()
  {
   if(g_hedging)
      return;
   ulong longT, shortT;
   FindPositions(longT, shortT);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;
      ENUM_ORDER_TYPE ot = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(ot != ORDER_TYPE_BUY_STOP && ot != ORDER_TYPE_SELL_STOP)
         continue;
      int side = (ot == ORDER_TYPE_BUY_STOP ? 0 : 1);
      if(g_pQty[side] <= 0)
         continue;
      double want = NormVol(g_pQty[side] + PositionVolume(side == 0 ? shortT : longT));
      double have = OrderGetDouble(ORDER_VOLUME_CURRENT);
      if(want <= 0 || MathAbs(want - have) < VolStep() * 0.5)
         continue;
      double price = OrderGetDouble(ORDER_PRICE_OPEN);
      double sl = OrderGetDouble(ORDER_SL);
      double tp = OrderGetDouble(ORDER_TP);
      if(!trade.OrderDelete(t))
         continue;
      if(side == 0)
         trade.BuyStop(want, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG buy stop");
      else
         trade.SellStop(want, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "FG sell stop");
     }
  }

//+------------------------------------------------------------------+
//| open trade management, every tick (Pine strategy.exit)           |
//+------------------------------------------------------------------+
void ManagePosition()
  {
   ulong longT, shortT;
   FindPositions(longT, shortT);
   // hedging account: a filled reversal leaves both sides open; close the older one
   if(longT != 0 && shortT != 0)
     {
      ulong oldT = (g_posTicket == longT ? longT : g_posTicket == shortT ? shortT : 0);
      if(oldT == 0)
        {
         long tl = 0, tsx = 0;
         if(PositionSelectByTicket(longT))
            tl = PositionGetInteger(POSITION_TIME_MSC);
         if(PositionSelectByTicket(shortT))
            tsx = PositionGetInteger(POSITION_TIME_MSC);
         oldT = (tl <= tsx ? longT : shortT);
        }
      trade.PositionClose(oldT);
      if(oldT == longT)
         longT = 0;
      else
         shortT = 0;
     }
   ulong ticket = (longT != 0 ? longT : shortT);
   if(ticket == 0)
     {
      if(g_posTicket != 0)
        {
         ResetTradeState();
         State(true);
        }
      return;
     }
   if(!PositionSelectByTicket(ticket))
      return;
   bool   isLong = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   int    side = isLong ? 0 : 1;
   double sgn = isLong ? 1.0 : -1.0;
   double pt = _Point;
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double vol = PositionGetDouble(POSITION_VOLUME);
   double curSL = PositionGetDouble(POSITION_SL);
   double curTP = PositionGetDouble(POSITION_TP);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double px = isLong ? bid : ask;          // the price a close would get
   bool   changed = false;

   //--- a new trade: take the distances locked when its entry order was placed
   if(ticket != g_posTicket || (int)side != g_posType)
     {
      ResetTradeState();
      g_posTicket = ticket;
      g_posType = side;
      if(g_pQty[side] > 0)
        {
         g_lockSl = g_pSl[side];
         g_lockTp = g_pTp[side];
         g_lockAct = g_pAct[side];
         g_lockDst = g_pDst[side];
         g_lockRun = g_pRun[side];
        }
      else
        {
         // no stored lock (state lost): use the current settings
         double a14 = WilderATR(14, 1);
         double aV = (InpAtrLen == 14 ? a14 : WilderATR(InpAtrLen, 1));
         ExitDistancesNow(a14, aV, g_lockSl, g_lockTp, g_lockAct, g_lockDst, g_lockRun);
        }
      // netting: a reversal order that was larger than needed leaves an excess
      if(!g_hedging && g_pQty[side] > 0 && vol > g_pQty[side] + VolStep() * 0.5)
        {
         double excess = NormVol(vol - g_pQty[side]);
         if(excess > 0 && ReduceVolume(ticket, isLong, excess, "FG excess"))
            vol -= excess;
        }
      g_initVol = vol;
      g_best = open;
      DeletePending(-1);                     // one-cancels-other: the other entry is cancelled
      g_pQty[side] = 0;
      changed = true;
     }

   //--- levels
   double slTicks = (g_lockSl > 0 ? g_lockSl : 0.0);
   double tpTicks = (g_lockTp > 0 ? g_lockTp : 0.0);
   double tpLevel = (tpTicks > 0 ? open + sgn * tpTicks * pt : 0.0);
   double wantSL = (slTicks > 0 ? open - sgn * slTicks * pt : 0.0);
   double wantTP = 0.0;
   bool   trailing = false;
   double trailDist = 0.0;
   if((isLong && px > g_best) || (!isLong && px < g_best))
      g_best = px;
   bool runnerMode = (InpTpStyle == FG_TP_PARTIAL && InpPartPct < 100);

   if(runnerMode)
     {
      if(tpLevel > 0 && !g_tpReached && sgn * (px - tpLevel) >= 0)
        {
         g_tpReached = true;
         changed = true;
        }
      // part 1: partial close at the take profit level
      if(g_tpReached && !g_partialDone)
        {
         g_partialDone = true;
         changed = true;
         if(InpPartPct > 0)
           {
            double st = VolStep();
            double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double part = MathFloor(g_initVol * InpPartPct / 100.0 / st + 1e-9) * st;
            if(part >= mn - 1e-12 && vol - part >= mn - 1e-12)
              {
               if(!ReduceVolume(ticket, isLong, NormalizeDouble(part, 8), "FG TP part"))
                  PrintFormat("FlashGold v5: partial close failed, retcode %u (%s).", trade.ResultRetcode(), trade.ResultRetcodeDescription());
              }
            else
               PrintFormat("FlashGold v5: partial close skipped, %.2f%% of %.2f lots is below the broker minimum; the whole position runs.", InpPartPct, g_initVol);
            if(!PositionSelectByTicket(ticket))
              {
               State(true);
               return;
              }
            curSL = PositionGetDouble(POSITION_SL);
            curTP = PositionGetDouble(POSITION_TP);
           }
        }
      // part 2: runner. Breakeven from the bar after the TP level was reached, trail from the TP level
      if(InpRunBE && g_beOn)
         wantSL = open;
      if(g_tpReached && tpLevel > 0)
        {
         trailing = true;
         trailDist = g_lockRun * pt;
         double ts = g_best - sgn * trailDist;
         if(wantSL <= 0 || sgn * (ts - wantSL) > 0)
            wantSL = ts;
        }
     }
   else
     {
      wantTP = tpLevel;
      if(InpUseTrail && sgn * (g_best - open) >= g_lockAct * pt)
        {
         trailing = true;
         trailDist = g_lockDst * pt;
         double ts = g_best - sgn * trailDist;
         if(wantSL <= 0 || sgn * (ts - wantSL) > 0)
            wantSL = ts;
        }
     }

   //--- apply
   double tick = TickSize();
   double stopLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * pt;
   if(wantSL > 0)
      wantSL = NormPrice(wantSL);
   if(wantTP > 0)
      wantTP = NormPrice(wantTP);
   bool needSL = false;
   if(wantSL > 0)
     {
      if(curSL <= 0 || !g_aligned)
         needSL = (MathAbs(wantSL - curSL) > tick * 0.5);
      else
        {
         double minStep = trailing ? MathMax(tick, trailDist * 0.01) : tick;
         needSL = (sgn * (wantSL - curSL) >= minStep - tick * 0.01);   // only ever tightened
        }
     }
   bool needTP = (MathAbs(wantTP - curTP) > tick * 0.5);
   if(needSL)
     {
      if(sgn * (px - wantSL) <= 0)
        {
         // price is already at or beyond the stop: the stop is hit
         trade.PositionClose(ticket);
         State(true);
         return;
        }
      if(sgn * (px - wantSL) < stopLvl)
         needSL = false;                     // inside the broker's stops level, retry on a later tick
     }
   if(needSL || needTP)
     {
      double newSL = needSL ? wantSL : curSL;
      if(trade.PositionModify(ticket, newSL, wantTP))
        {
         if(needSL)
            g_aligned = true;
         changed = true;
        }
     }
   else
      if(!g_aligned && (wantSL <= 0 || MathAbs(wantSL - curSL) <= tick * 0.5))
        {
         g_aligned = true;
         changed = true;
        }
   if(changed)
      State(true);
  }

//+------------------------------------------------------------------+
//| once per closed bar: signals and orders                          |
//+------------------------------------------------------------------+
void OnNewBar(const datetime t0)
  {
   g_barIdx++;
   double pt = _Point;
   datetime t1 = iTime(_Symbol, _Period, 1);
   if(t1 == 0)
      return;

   //--- closes of the last closed bar, the one before, and priorDriftBars back
   int need = InpPriorDriftBars + 1;
   double c[];
   int got = CopyClose(_Symbol, _Period, 1, need, c);
   if(got < 2)
      return;
   double close1 = c[got - 1];
   double close2 = c[got - 2];
   bool   haveDrift = (got == need);
   double closeN = haveDrift ? c[0] : 0.0;

   //--- price model (indicator)
   double halfSpread = InpSpreadPoints * pt * 0.5;
   double bidM = close1 - halfSpread;
   double askM = close1 + halfSpread;
   double mid = close1;

   //--- TDI directions
   int parentDir = ZoneDir(0, false, t0, t1);
   g_dir[0] = parentDir;
   int parentSide = (parentDir == NA_DIR ? 0 : parentDir);
   int active = 0, aligned = 0, conflict = 0, mixed = 0;
   for(int i = 1; i < ZN; i++)
     {
      int d = g_use[i] ? ZoneDir(i, InpHtfNoRepaint, t0, t1) : NA_DIR;
      g_dir[i] = d;
      bool on = g_use[i] && (!InpIgnoreNaZones || d != NA_DIR);
      if(!on)
         continue;
      active++;
      if(parentSide != 0 && d == parentSide)
         aligned++;
      if(parentSide != 0 && d == -parentSide)
         conflict++;
      if(d == 0)
         mixed++;
     }
   int  requiredAligned = MathMin(InpMinAlignedZones, active);
   bool parentFlatAllowed = InpAllowNeutralParent && parentSide == 0;
   bool zoneReady = (active == 0 || aligned >= requiredAligned);
   bool zoneBuyAllowed = !InpUseTdiTradeZone || ((parentSide == 1 || parentFlatAllowed) && zoneReady);
   bool zoneSellAllowed = !InpUseTdiTradeZone || ((parentSide == -1 || parentFlatAllowed) && zoneReady);
   g_active_n = active;
   g_aligned_n = aligned;
   g_conflict_n = conflict;
   g_mixed_n = mixed;

   //--- burst / thresholds
   double atr14 = WilderATR(14, 1);
   double atrV = (InpAtrLen == 14 ? atr14 : WilderATR(InpAtrLen, 1));
   double atrPts = atr14 / pt;
   bool   unitOk = (InpDistUnit == FG_UNIT_POINTS || atr14 > 0);   // Pine: na thresholds make every comparison false
   double burstThr = (InpDistUnit == FG_UNIT_ATR ? InpBurstAtrMult * atrPts : InpBurstPoints);
   double entryDist = (InpDistUnit == FG_UNIT_ATR ? InpEntryDistAtrMult * atrPts : InpEntryDistPoints);
   double holdFav = (InpDistUnit == FG_UNIT_ATR ? InpHoldFavAtrMult * atrPts : InpHoldMinFavPoints);
   double burstPts = (mid - close2) / pt;
   double driftPts = haveDrift ? (mid - closeN) / pt : 0.0;
   bool burstBuy = unitOk && burstPts >= burstThr;
   bool burstSell = unitOk && burstPts <= -burstThr;
   bool priorBuyOk = !InpUsePriorFilter || (haveDrift && driftPts > 0);
   bool priorSellOk = !InpUsePriorFilter || (haveDrift && driftPts < 0);
   bool rawBuy = InpUseAnyCombo ? (zoneBuyAllowed && (!InpUseBurstGate || burstBuy || parentSide == 1)) : (zoneBuyAllowed && burstBuy);
   bool rawSell = InpUseAnyCombo ? (zoneSellAllowed && (!InpUseBurstGate || burstSell || parentSide == -1)) : (zoneSellAllowed && burstSell);
   bool buyCandidate = rawBuy && priorBuyOk;
   bool sellCandidate = rawSell && priorSellOk;

   //--- entry hold / virtual stop (indicator)
   bool   buySignal = false, sellSignal = false;
   double buyEntryPrice = 0.0, sellEntryPrice = 0.0;
   bool   canFire = (!InpOneEntryPerBar || g_lastEntryBar < 0 || g_lastEntryBar != g_barIdx);
   if(buyCandidate && canFire && unitOk)
     {
      if(InpEntryHoldBars == 0)
        {
         buyEntryPrice = askM + entryDist * pt;
         buySignal = true;
         g_lastEntryBar = g_barIdx;
        }
      else
         if(!g_holdActive)
           {
            g_holdActive = true;
            g_holdIsBuy = true;
            g_holdSignalBar = g_barIdx;
            g_holdSignalMid = mid;
           }
         else
            if(g_holdIsBuy)
              {
               long elapsed = g_barIdx - g_holdSignalBar;
               double move = (mid - g_holdSignalMid) / pt;
               if(elapsed >= InpEntryHoldBars && move >= holdFav)
                 {
                  buyEntryPrice = askM + entryDist * pt;
                  buySignal = true;
                  g_lastEntryBar = g_barIdx;
                  g_holdActive = false;
                 }
              }
     }
   if(sellCandidate && canFire && unitOk)
     {
      if(InpEntryHoldBars == 0)
        {
         sellEntryPrice = bidM - entryDist * pt;
         sellSignal = true;
         g_lastEntryBar = g_barIdx;
        }
      else
         if(!g_holdActive)
           {
            g_holdActive = true;
            g_holdIsBuy = false;
            g_holdSignalBar = g_barIdx;
            g_holdSignalMid = mid;
           }
         else
            if(!g_holdIsBuy)
              {
               long elapsed = g_barIdx - g_holdSignalBar;
               double move = (g_holdSignalMid - mid) / pt;
               if(elapsed >= InpEntryHoldBars && move >= holdFav)
                 {
                  sellEntryPrice = bidM - entryDist * pt;
                  sellSignal = true;
                  g_lastEntryBar = g_barIdx;
                  g_holdActive = false;
                 }
              }
     }
   if(g_holdActive && ((g_holdIsBuy && !zoneBuyAllowed) || (!g_holdIsBuy && !zoneSellAllowed)))
     {
      g_holdActive = false;
      g_holdSignalBar = -1;
      g_holdSignalMid = 0;
     }

   //--- exit geometry now
   double slNow, tpNow, actNow, dstNow, runNow;
   ExitDistancesNow(atr14, atrV, slNow, tpNow, actNow, dstNow, runNow);
   g_atrV = atrV;
   g_burstThr = burstThr;
   g_entryDist = entryDist;
   g_slNow = slNow;
   g_tpNow = tpNow;

   //--- position state
   ulong longT, shortT;
   FindPositions(longT, shortT);
   bool inLong = (longT != 0);
   bool inShort = (shortT != 0);
   bool flat = (!inLong && !inShort);
   bool allowL = (InpDirection != FG_DIR_SHORT);
   bool allowS = (InpDirection != FG_DIR_LONG);

   // breakeven for the runner starts on the bar after the take profit level was reached
   if(!flat && g_tpReached && !g_beOn)
     {
      g_beOn = true;
      State(true);
     }

   //--- opposite-signal handling on an open position
   if(InpExitOnOpposite && sellSignal && inLong)
     {
      if(trade.PositionClose(longT))
        {
         inLong = false;
         flat = !inShort;
        }
     }
   if(InpExitOnOpposite && buySignal && inShort)
     {
      if(trade.PositionClose(shortT))
        {
         inShort = false;
         flat = !inLong;
        }
     }

   //--- long entry: stop order at the indicator's entry price
   if(buySignal && allowL && !inLong && (flat || InpAllowReverse || InpExitOnOpposite))
     {
      double q = CalcQty(slNow);
      if(q > 0 && buyEntryPrice > 0)
        {
         g_pSl[0] = slNow;
         g_pTp[0] = tpNow;
         g_pAct[0] = actNow;
         g_pDst[0] = dstNow;
         g_pRun[0] = runNow;
         g_pQty[0] = q;
         g_placedBar[0] = g_barIdx;
         PlaceEntry(true, buyEntryPrice, q, slNow, tpNow);
        }
     }
   //--- short entry
   if(sellSignal && allowS && !inShort && (flat || InpAllowReverse || InpExitOnOpposite))
     {
      double q = CalcQty(slNow);
      if(q > 0 && sellEntryPrice > 0)
        {
         g_pSl[1] = slNow;
         g_pTp[1] = tpNow;
         g_pAct[1] = actNow;
         g_pDst[1] = dstNow;
         g_pRun[1] = runNow;
         g_pQty[1] = q;
         g_placedBar[1] = g_barIdx;
         PlaceEntry(false, sellEntryPrice, q, slNow, tpNow);
        }
     }
   State(true);

   //--- cancel a stale unfilled entry
   if(InpEntryValidBars > 0)
     {
      FindPositions(longT, shortT);
      if(g_placedBar[0] >= 0 && longT == 0 && g_barIdx - g_placedBar[0] >= InpEntryValidBars)
        {
         DeletePending(0);
         g_placedBar[0] = -1;
        }
      if(g_placedBar[1] >= 0 && shortT == 0 && g_barIdx - g_placedBar[1] >= InpEntryValidBars)
        {
         DeletePending(1);
         g_placedBar[1] = -1;
        }
     }

   //--- time stop
   if(InpMaxBarsHeld > 0)
     {
      FindPositions(longT, shortT);
      ulong t = (longT != 0 ? longT : shortT);
      if(t != 0 && PositionSelectByTicket(t))
        {
         int k = iBarShift(_Symbol, _Period, (datetime)PositionGetInteger(POSITION_TIME), false);
         if(k - 1 >= InpMaxBarsHeld)
           {
            if(longT != 0)
               trade.PositionClose(longT);
            if(shortT != 0)
               trade.PositionClose(shortT);
           }
        }
     }

   //--- panel
   if(InpShowPanel && !MQLInfoInteger(MQL_OPTIMIZATION))
     {
      string risk = (aligned >= requiredAligned && conflict == 0) ? "LOW" : (aligned >= requiredAligned ? "MIX" : "HIGH");
      string pos = inLong ? "LONG " + DoubleToString(PositionVolume(longT), 2) : inShort ? "SHORT " + DoubleToString(PositionVolume(shortT), 2) : "flat";
      string s = "FlashGold v5 S  |  TDI FILTER\n";
      s += "Parent: " + DirText(parentSide) + "\n";
      s += StringFormat("Aligned: %d/%d   Conflict: %d   Mixed: %d   Risk: %s\n", aligned, active, conflict, mixed, risk);
      s += "Z1 / Z2: " + DirText(g_dir[1]) + " / " + DirText(g_dir[2]) + "\n";
      s += "Z3 / Z4: " + DirText(g_dir[3]) + " / " + DirText(g_dir[4]) + "\n";
      s += "Z5 / Z6: " + DirText(g_dir[5]) + " / " + DirText(g_dir[6]) + "\n";
      s += StringFormat("ATR / burst / dist / SL pts: %.0f / %.0f / %.0f / %.0f\n", atrV / pt, burstThr, entryDist, MathMax(slNow, 0.0));
      s += StringFormat("SL / TP in price: %.2f / %.2f\n", MathMax(slNow, 0.0) * pt, MathMax(tpNow, 0.0) * pt);
      s += "Position: " + pos + "\n";
      s += "Last bar: " + (buySignal ? "BUY signal @ " + DoubleToString(buyEntryPrice, _Digits) : sellSignal ? "SELL signal @ " + DoubleToString(sellEntryPrice, _Digits) : "no signal");
      Comment(s);
     }
  }

//+------------------------------------------------------------------+
//| tick                                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   ManagePosition();
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 == 0)
      return;
   if(g_lastBar == 0)
     {
      g_lastBar = t0;          // attached in the middle of a bar: wait for the next bar close
      return;
     }
   if(t0 != g_lastBar)
     {
      g_lastBar = t0;
      OnNewBar(t0);
      ManagePosition();        // an entry filled at market gets its stop right away
     }
   SyncPendingNetting();
  }
//+------------------------------------------------------------------+
