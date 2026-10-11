//+------------------------------------------------------------------+
//|                                               RegimeTrend_EA.mq5 |
//|      Trades the RegimeTrend indicator's own signal, nothing else |
//+------------------------------------------------------------------+
//| Purpose: Institutional companion EA trading RegimeTrend signals  |
//| with advanced money management:                                  |
//|                                                                  |
//| 1. ENTRY: Flat, and Regime (buffer 5) transitioned into TRENDING  |
//|    on the last closed bar (shift 1). Traded in direction buffer 6.|
//| 2. MONEY MANAGEMENT: Dynamic % Risk per trade sizing based on     |
//|    the distance to the SuperTrend Stop Loss.                     |
//| 3. BREAK-EVEN: Moves SL to entry once profit reaches N x Risk.    |
//| 4. TRAILING STOP: Dynamic SuperTrend trailing with step buffer.  |
//| 5. CONFLUENCE: H4 Macro Trend filter (buffer 7).                 |
//| 6. TIMING: Session filter for London & New York hours.           |
//|                                                                  |
//| Decisions are evaluated ONCE PER NEW BAR on fully closed bars.   |
//| A bar that opens before the broker accepts orders is evaluated   |
//| at the first tick of its trade session.                          |
//|                                                                  |
//| v1.50 adds switchable entry / exit / trailing improvements (all  |
//| off by default, so defaults reproduce v1.49 exactly):            |
//|   Entry : spread cap, min ER, prior-state filter, late entry /   |
//|           re-entry into a young leg, ATR stop, SL distance cap.  |
//|   Exit  : raw SuperTrend flip, ER weakening, time stop, Friday.  |
//|   Trail : tight SuperTrend / Chandelier / ATR-close sources,     |
//|           activation in R, R lock-in stage, partial close.       |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property version   "1.50"
#property strict
#property icon      "xpworx.ico"
#property description "Mechanical companion EA for RegimeTrend. Features dynamic % risk lot sizing, SuperTrend trailing stops, Break-Even protection, and H4 Macro Trend confluence."
#property description "Licensed to Maynor."

#include <Trade\Trade.mqh>
#include <Foundry\xpMoneyManagement.mqh>
#include <Foundry\RegimeTrend\RegimeTypes.mqh>
#include <Foundry\RegimeTrend\RegimeGauge.mqh>

//--- Embed indicator resource so the EA runs 100% self-contained
#resource "\\Indicators\\Foundry\\RegimeTrend.ex5"
#define REGIME_INDICATOR_RESOURCE "::Indicators\\Foundry\\RegimeTrend.ex5"

//--- Exit criteria
enum ENUM_EXIT_MODE
  {
   EXIT_ON_LEAVE_TREND    = 0, // Exit when regime leaves Trending (Strict)
   EXIT_ON_CHOPPY_OR_FLIP = 1  // Hold through Neutral, exit on Choppy or Direction flip
  };

//--- Money management modes
enum ENUM_RISK_MODE
  {
   RISK_FIXED_LOT         = 0, // Fixed lot size
   RISK_PERCENT_EQUITY    = 1  // Dynamic lot size (% Risk of Account Equity)
  };

//--- Which sides the EA may open
enum ENUM_TRADE_DIRECTION
  {
   TRADE_BOTH       = 0, // Long and short
   TRADE_LONG_ONLY  = 1, // Long only
   TRADE_SHORT_ONLY = 2  // Short only
  };

//--- Where the trailing stop candidate comes from (v1.50)
enum ENUM_TRAIL_SOURCE
  {
   TRAIL_SRC_SUPERTREND       = 0, // SuperTrend line (indicator buffer 0)
   TRAIL_SRC_SUPERTREND_TIGHT = 1, // Second SuperTrend with its own ATR multiplier
   TRAIL_SRC_CHANDELIER       = 2, // Highest high / lowest low since entry -/+ K x ATR
   TRAIL_SRC_ATR_CLOSE        = 3  // Last closed bar close -/+ K x ATR
  };

//--- Which state the regime must come from on the entry bar (v1.50)
enum ENUM_ENTRY_PREV_STATE
  {
   ENTRY_PREV_ANY     = 0, // Any (Choppy or Neutral)
   ENTRY_PREV_NEUTRAL = 1, // Only Neutral -> Trending
   ENTRY_PREV_CHOPPY  = 2  // Only Choppy -> Trending
  };

//--- Broker server daylight-saving convention (used only in the tester,
//--- where TimeGMT() just returns server time)
enum ENUM_SERVER_DST
  {
   SERVER_DST_NONE = 0, // No DST (fixed offset all year)
   SERVER_DST_US   = 1, // US dates (most "NY close" GMT+2/+3 brokers)
   SERVER_DST_EU   = 2  // EU dates
  };

//--- indicator settings, mirrored so the handle matches the chart's ---
//--- NOTE: this argument list's ORDER must match RegimeTrend.mq5's   ---
//--- inputs exactly - see that file's OnInit() input block.          ---
input group            "Indicator settings (must match the chart)"
input ENUM_TIMEFRAMES  InpRegimeTF         = PERIOD_H1;   // Regime timeframe
input int              InpErPeriod         = 20;          // ER lookback (HTF bars)
input double           InpEnterTrend       = 0.42;        // ER to ENTER a trend state
input double           InpExitTrend        = 0.18;        // ER to LEAVE a trend state
input int              InpAtrPeriod        = 10;          // ATR period
input double           InpAtrMult          = 4.0;         // ATR multiplier
input int              InpMinDwell         = 6;           // Minimum bars in a state
input double           InpShockMult        = 3.0;         // Shock: bar range > N * ATR
input bool             InpUseClosedBars    = true;        // Use closed bars only
input ENUM_TIMEFRAMES  InpMacroTF          = PERIOD_H4;    // Macro trend timeframe
input int              InpMacroEmaPeriod   = 50;           // Macro EMA period (HTF bars)
input int              InpMacroSlopeBars   = 3;            // Macro slope lookback (HTF bars)
input double           InpMacroDeadbandPct = 0.05;         // Macro flat deadband (% of EMA)
input int              InpMacroMinDwell    = 2;            // Macro minimum HTF bars before a flip

input group            "Money Management & Position Sizing"
input ENUM_RISK_MODE   InpRiskMode         = RISK_PERCENT_EQUITY; // Lot sizing mode
input double           InpRiskPercent      = 1.0;         // Risk % per trade (if dynamic)
input double           InpLotSize          = 0.10;        // Fixed lot size (if fixed)
input double           InpMinStopAtr       = 1.0;         // Min SL distance in ATR multiples (0 = off)
input int              InpMinStopPoints    = 0;           // Min SL distance in points (0 = off)
input double           InpMaxLots          = 5.0;         // Max lot size per trade (0 = broker max)
input double           InpMaxMarginPct     = 25.0;        // Max % of free margin one position may use (0 = off)
input ulong            InpMagic            = 20260922;    // Magic number
input int              InpSlippagePoints   = 20;          // Max slippage (points)

input group            "Risk Management & Trailing Stop"
input bool             InpUseSuperTrendSL  = true;        // Protective Stop Loss at SuperTrend line
input bool             InpTrailSuperTrend  = true;        // Trail Stop Loss with SuperTrend
input int              InpTrailStepPoints  = 50;          // Min trailing step (points)
input bool             InpUseBreakEven     = false;       // Move Stop Loss to Break-Even (false for Gold noise tolerance)
input double           InpBreakEvenR       = 1.0;         // Trigger Break-Even at N x Initial Risk
input double           InpBreakEvenBuffer  = 10.0;        // Break-Even profit buffer (points)
input double           InpTakeProfitR      = 0.0;         // Take Profit in R-multiples (0.0 = disabled)
input ENUM_EXIT_MODE   InpExitMode         = EXIT_ON_CHOPPY_OR_FLIP; // Exit criteria
input int              InpExitOrderTimeout = 120;         // Max wait for a placed close order to settle (s)

input group            "Confluence & Session Filters"
input ENUM_TRADE_DIRECTION InpTradeDirection = TRADE_BOTH; // Allowed trade direction
input bool             InpUseMacroFilter   = true;        // Filter entries by H4 Macro Trend (Buffer 7)
input bool             InpStrictMacroShorts = true;       // Shorts only when H4 Macro Trend is Down (not Flat)
input bool             InpStrictMacroLongs = true;        // Longs only when H4 Macro Trend is Up (not Flat)
input bool             InpUseSessionFilter = false;       // Filter entries by session hours (GMT)
input int              InpStartHourGMT     = 7;           // Session start hour (GMT)
input int              InpEndHourGMT       = 18;          // Session end hour (GMT, exclusive; < start wraps midnight)
input int              InpTesterGMTOffset  = 2;           // Tester only: broker server GMT offset in winter (hours)
input ENUM_SERVER_DST  InpTesterDst        = SERVER_DST_US; // Tester only: broker DST convention

input group            "Entry improvements (v1.50, 0/false = original behaviour)"
input int              InpMaxSpreadPoints  = 0;           // Skip entries when spread > N points (0 = off)
input double           InpMinErEntry       = 0.0;         // Min Efficiency Ratio on the entry bar (0 = off)
input ENUM_ENTRY_PREV_STATE InpEntryPrevState = ENTRY_PREV_ANY; // Required state before Trending
input int              InpLateEntryBars    = 0;           // Also enter up to N bars after the transition (0 = off)
input bool             InpReentryAfterStop = false;       // Late entry may re-enter a leg after a stop-out
input double           InpSlAtrMult        = 0.0;         // Initial SL = entry -/+ N x ATR instead of SuperTrend (0 = off)
input double           InpMaxStopAtr       = 0.0;         // Cap initial SL distance at N x ATR (0 = off)

input group            "Exit improvements (v1.50, 0/false = original behaviour)"
input bool             InpExitOnStFlip     = false;       // Exit when the raw SuperTrend flips against the trade
input double           InpErExit           = 0.0;         // Exit when ER drops below this level (0 = off)
input int              InpMaxBarsInTrade   = 0;           // Time stop: close after N chart bars (0 = off)
input int              InpCloseFridayHour  = 0;           // Close open trades on Friday from this GMT hour (0 = off)

input group            "Trailing improvements (v1.50, defaults = original behaviour)"
input ENUM_TRAIL_SOURCE InpTrailSource     = TRAIL_SRC_SUPERTREND; // Trailing stop source
input double           InpTrailAtrMult     = 2.0;         // Tight SuperTrend ATR multiplier (source 1)
input double           InpTrailAtrK        = 3.0;         // ATR multiple K for Chandelier / ATR-close trailing
input double           InpTrailActivateR   = 0.0;         // Start trailing only after N x Initial Risk (0 = at once)
input double           InpLockTriggerR     = 0.0;         // Lock-in stage: when profit >= N x R ... (0 = off)
input double           InpLockR            = 0.0;         // ... move SL to entry + N x R (must be < trigger)
input double           InpPartialR         = 0.0;         // Partial close at N x R (0 = off)
input double           InpPartialPercent   = 50.0;        // Partial close % of the original volume

input group            "Chart Gauge"
input bool             InpShowGauge        = true;        // Show XPWorx regime gauge
input ENUM_BASE_CORNER InpGaugeCorner      = CORNER_LEFT_LOWER; // Gauge corner (indicator's gauge uses top-right)
input int              InpGaugeX           = 20;          // Gauge horizontal margin (px)
input int              InpGaugeY           = 20;          // Gauge vertical margin (px)
input int              InpGaugeSize        = 220;         // Gauge width (px)

CTrade   g_trade;
CXPMoneyManager g_money;
int      g_handle         = INVALID_HANDLE;
int      g_trail_handle   = INVALID_HANDLE; // second SuperTrend for TRAIL_SRC_SUPERTREND_TIGHT
int      g_atr_handle     = INVALID_HANDLE;
datetime g_last_bar_time  = 0;
//--- v1.50 leg tracking for late entries / re-entries. A "leg" is one
//--- uninterrupted Trending state in one direction; it is identified by
//--- the open time of the bar on which it started (dwell == 1).
datetime g_leg_traded_time  = 0;  // leg in which the EA last opened a trade
datetime g_leg_stopped_time = 0;  // leg whose trade ended without an EA exit signal (SL/TP)
bool     g_had_pos          = false;
bool     g_signal_exit      = false;
ulong    g_exit_ticket    = 0; // position whose exit signal has been committed
ulong    g_exit_order     = 0; // accepted close order awaiting a final server state
datetime g_exit_last_try  = 0;
datetime g_exit_order_time = 0; // when g_exit_order was accepted
datetime g_entry_retry_bar = 0; // bar whose entry the server refused as "market closed"
datetime g_entry_retry_at  = 0; // ...re-evaluated no earlier than this
CRegimeGauge g_ea_gauge;
datetime g_gauge_bar_time = 0;
double   g_gauge_er       = -1.0;
int      g_gauge_state    = REGIME_UNSET;
int      g_gauge_dwell    = 0;
int      g_gauge_macro    = REGIME_MACRO_UNSET;

//--- Display the same closed indicator bar the EA evaluates. Retry until
//--- history is ready, then refresh once per bar; no trade calls here.
void UpdateEAGauge(void)
  {
   if(!g_ea_gauge.IsCreated() || g_handle == INVALID_HANDLE)
      return;
   datetime bar_time = iTime(_Symbol,_Period,0);
   if(bar_time == 0 || bar_time == g_gauge_bar_time)
      return;
   double er[],state[],dwell[],macro[];
   if(CopyBuffer(g_handle,2,1,1,er) != 1 ||
      CopyBuffer(g_handle,3,1,1,state) != 1 ||
      CopyBuffer(g_handle,4,1,1,dwell) != 1 ||
      CopyBuffer(g_handle,7,1,1,macro) != 1)
      return;
   g_gauge_er = er[0];
   g_gauge_state = (int)state[0];
   g_gauge_dwell = (int)dwell[0];
   g_gauge_macro = (int)macro[0];
   g_ea_gauge.Render(g_gauge_er,g_gauge_state,g_gauge_dwell,g_gauge_macro);
   if(g_gauge_state != REGIME_UNSET && g_gauge_macro != REGIME_MACRO_UNSET)
      g_gauge_bar_time = bar_time;
  }

void OnTimer(void)
  {
   UpdateEAGauge();
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE && g_ea_gauge.IsCreated())
     {
      g_ea_gauge.OnChartResize();
      g_ea_gauge.Render(g_gauge_er,g_gauge_state,g_gauge_dwell,g_gauge_macro);
     }
  }

//+------------------------------------------------------------------+
//| Calculate lot size based on fixed lot or account equity risk %   |
//+------------------------------------------------------------------+
double CalculateLotSize(const ENUM_ORDER_TYPE order_type,const double entry_price,const double stop_loss,double &take_profit)
  {
   XPMM_ENTRY entry; ZeroMemory(entry);
   entry.type=order_type; entry.entry=entry_price; entry.sl=stop_loss; entry.tp=take_profit;
   XPMM_PLAN plan;
   if(!g_money.PrepareEntry(entry,plan))
     {
      Print("RegimeTrend_EA: sizing skipped: ",g_money.Reason());
      return 0.0;
     }
   take_profit=plan.tp;
   return plan.volume;
  }
//+------------------------------------------------------------------+
//| A CTrade call returning true only means the request was sent;    |
//| confirm the server actually executed it.                         |
//+------------------------------------------------------------------+
bool TradeDone(const bool sent,const string what)
  {
   uint rc = g_trade.ResultRetcode();
   if(sent && rc == TRADE_RETCODE_DONE)
      return(true);
   if(sent && rc == TRADE_RETCODE_DONE_PARTIAL)
     {
      //--- a position exists, but smaller than requested
      PrintFormat("RegimeTrend_EA: %s PARTIALLY filled - %.2f of %.2f lots (deal #%I64u).",
                  what,g_trade.ResultVolume(),g_trade.RequestVolume(),g_trade.ResultDeal());
      return(true);
     }
   if(sent && rc == TRADE_RETCODE_PLACED)
     {
      //--- accepted but not executed yet: not an open/closed position
      PrintFormat("RegimeTrend_EA: %s order placed (#%I64u) but not filled yet.",what,g_trade.ResultOrder());
      return(false);
     }
   PrintFormat("RegimeTrend_EA: %s FAILED - retcode %u (%s).",what,rc,g_trade.ResultRetcodeDescription());
   return(false);
  }

//--- Keep an exit committed across bars. Never submit a second close while
//--- the server still has a placed close order for the same position.
void ManagePendingExit(void)
  {
   if(g_exit_ticket == 0)
      return;
   if(g_exit_order != 0)
     {
      if(OrderSelect(g_exit_order))
         return; // still live; another close could over-close the position
      bool unsettled = true;   // not live, and no final state in history yet
      if(!HistoryOrderSelect(g_exit_order))
         HistorySelect(g_exit_order_time - 60,TimeCurrent() + 60);   // refresh the local cache
      if(HistoryOrderSelect(g_exit_order))
        {
         ENUM_ORDER_STATE state = (ENUM_ORDER_STATE)HistoryOrderGetInteger(g_exit_order,ORDER_STATE);
         unsettled = (state == ORDER_STATE_STARTED || state == ORDER_STATE_PLACED ||
                      state == ORDER_STATE_REQUEST_ADD || state == ORDER_STATE_REQUEST_MODIFY ||
                      state == ORDER_STATE_REQUEST_CANCEL);
        }
      //--- an order that is neither live nor final would otherwise block the
      //--- EA forever (no exit, no trailing, no entries): stop waiting after
      //--- InpExitOrderTimeout seconds and let the position check decide
      if(unsettled)
        {
         if(TimeCurrent() - g_exit_order_time < InpExitOrderTimeout)
            return;
         PrintFormat("RegimeTrend_EA: close order #%I64u has no final state after %d s - resuming the exit.",
                     g_exit_order,InpExitOrderTimeout);
        }
      g_exit_order = 0;
     }

   if(!PositionSelectByTicket(g_exit_ticket))
     {
      g_exit_ticket   = 0;
      g_exit_last_try = 0;
      return;
     }

   //--- never send into a closed trade session; its first tick closes
   if(!XPMM_TradeSessionOpen(_Symbol,TimeCurrent()))
      return;

   datetime now = TimeCurrent();
   if(g_exit_last_try != 0 && now - g_exit_last_try < 5)
      return;
   g_exit_last_try = now;
   bool sent = g_trade.PositionClose(g_exit_ticket);
   uint rc = g_trade.ResultRetcode();
   TradeDone(sent,"close");
   if(sent && rc == TRADE_RETCODE_PLACED)
     {
      g_exit_order      = g_trade.ResultOrder();
      g_exit_order_time = now;
     }
  }

//+------------------------------------------------------------------+
//| Security Configuration & State                                   |
//+------------------------------------------------------------------+
const long     UserAccountNumber        = 0;                   // Authorized Account Number (0 = any)
const bool     DemoOnly                 = false;               // Demo accounts only
const datetime ExpirationDate           = 0; // Expiration Date (0 = disabled)
const bool     EnableAllPopups          = true;                // Enable security alert popups
bool           securityRemovalRequested = false;

#define AccountNumber() (long)AccountInfoInteger(ACCOUNT_LOGIN)
#define IsDemo()        ((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO)

void AlertOnce(const string msg, const int id)
  {
   static datetime last_alert_time[10] = {0};
   int idx = (id >= 0 && id < 10) ? id : 0;
   datetime now = TimeCurrent();
   if(now - last_alert_time[idx] >= 60)
     {
      Alert(msg);
      Print("Security Alert [", id, "]: ", msg);
      last_alert_time[idx] = now;
     }
  }

void Security()
  {
   if(MQLInfoInteger(MQL_TESTER))
      return;

   bool removeExpert = false;
   long accountNumber = AccountNumber();
   if(UserAccountNumber != 0 && UserAccountNumber != accountNumber && accountNumber != 0)
     {
      if(EnableAllPopups) AlertOnce("Wrong account number", 3);
      removeExpert = true;
     }
   if(DemoOnly && !IsDemo())
     {
      if(EnableAllPopups) AlertOnce("Demo accounts only", 4);
      removeExpert = true;
     }
   if(ExpirationDate != 0 && (TimeCurrent() >= ExpirationDate || TimeLocal() >= ExpirationDate))
     {
      if(EnableAllPopups) AlertOnce("This EA has expired", 5);
      removeExpert = true;
     }
   if(removeExpert)
     {
      securityRemovalRequested = true;
      ExpertRemove();
     }
  }

//+------------------------------------------------------------------+
//| n-th Sunday (n >= 1) or last Sunday (n = -1) of a month, 00:00    |
//+------------------------------------------------------------------+
datetime SundayOfMonth(const int year,const int mon,const int n)
  {
   MqlDateTime d;
   ZeroMemory(d);
   d.year = year;
   d.mon  = mon;
   d.day  = 1;
   TimeToStruct(StructToTime(d),d);
   int first_sun = 1 + (7 - d.day_of_week) % 7;

   if(n > 0)
      d.day = first_sun + 7 * (n - 1);
   else
     {
      MqlDateTime e;
      ZeroMemory(e);
      e.year = (mon == 12) ? year + 1 : year;
      e.mon  = (mon == 12) ? 1 : mon + 1;
      e.day  = 1;
      TimeToStruct(StructToTime(e) - 86400,e);   // last day of `mon`
      d.day = first_sun + 7 * ((e.day - first_sun) / 7);
     }
   d.hour = 0;
   d.min  = 0;
   d.sec  = 0;
   return(StructToTime(d));
  }
//+------------------------------------------------------------------+
//| Real GMT. In the tester TimeGMT() equals server time, so derive  |
//| it from the configured broker offset and DST convention instead. |
//+------------------------------------------------------------------+
datetime SessionClockGMT(void)
  {
   if(!MQLInfoInteger(MQL_TESTER))
      return(TimeGMT());

   datetime gmt = TimeCurrent() - InpTesterGMTOffset * 3600;
   if(InpTesterDst == SERVER_DST_NONE)
      return(gmt);

   MqlDateTime d;
   TimeToStruct(gmt,d);
   datetime dst_start, dst_end;
   if(InpTesterDst == SERVER_DST_US)
     {
      dst_start = SundayOfMonth(d.year,3,2) + 7 * 3600;    // 2nd Sun Mar, 02:00 EST
      dst_end   = SundayOfMonth(d.year,11,1) + 6 * 3600;   // 1st Sun Nov, 02:00 EDT
     }
   else
     {
      dst_start = SundayOfMonth(d.year,3,-1) + 3600;       // last Sun Mar, 01:00 UTC
      dst_end   = SundayOfMonth(d.year,10,-1) + 3600;      // last Sun Oct, 01:00 UTC
     }
   if(gmt >= dst_start && gmt < dst_end)
      gmt -= 3600;
   return(gmt);
  }
//+------------------------------------------------------------------+
bool InSession(const int hour)
  {
   if(InpStartHourGMT < InpEndHourGMT)
      return(hour >= InpStartHourGMT && hour < InpEndHourGMT);
   return(hour >= InpStartHourGMT || hour < InpEndHourGMT);   // wraps midnight
  }
//+------------------------------------------------------------------+
int OnInit(void)
  {
   Security();
   if(securityRemovalRequested)
      return(INIT_FAILED);

   // 1. Try embedded resource indicator first (self-contained EA)
   g_handle = iCustom(_Symbol,_Period,REGIME_INDICATOR_RESOURCE,
                      InpRegimeTF,InpErPeriod,InpEnterTrend,InpExitTrend,
                      InpAtrPeriod,InpAtrMult,
                      InpMinDwell,InpShockMult,InpUseClosedBars,false,
                      InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                      InpMacroDeadbandPct,InpMacroMinDwell,
                      false);

   // 2. Fallback: try subfolder path (Foundry\RegimeTrend)
   if(g_handle == INVALID_HANDLE)
     {
      g_handle = iCustom(_Symbol,_Period,"Foundry\\RegimeTrend",
                         InpRegimeTF,InpErPeriod,InpEnterTrend,InpExitTrend,
                         InpAtrPeriod,InpAtrMult,
                         InpMinDwell,InpShockMult,InpUseClosedBars,false,
                         InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                         InpMacroDeadbandPct,InpMacroMinDwell,
                         false);
     }

   // 3. Fallback: check root Indicators directory if client copied directly without Foundry folder
   if(g_handle == INVALID_HANDLE)
     {
      g_handle = iCustom(_Symbol,_Period,"RegimeTrend",
                         InpRegimeTF,InpErPeriod,InpEnterTrend,InpExitTrend,
                         InpAtrPeriod,InpAtrMult,
                         InpMinDwell,InpShockMult,InpUseClosedBars,false,
                         InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                         InpMacroDeadbandPct,InpMacroMinDwell,
                         false);
     }

   if(g_handle == INVALID_HANDLE)
     {
      PrintFormat("RegimeTrend_EA: iCustom failed, error %d. Indicator resource or file could not be loaded.",
                  GetLastError());
      return(INIT_FAILED);
     }

   PrintFormat("RegimeTrend_EA: indicator loaded successfully, handle=%d (RegimeTF=%d, ErPeriod=%d).",
               g_handle,InpRegimeTF,InpErPeriod);

   if(InpRiskMode == RISK_FIXED_LOT)
     {
      double vol_min = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
      double vol_max = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
      if(InpLotSize < vol_min || InpLotSize > vol_max)
        {
         PrintFormat("RegimeTrend_EA: InpLotSize %.2f is outside the symbol's allowed range [%.2f, %.2f].",
                     InpLotSize,vol_min,vol_max);
         return(INIT_PARAMETERS_INCORRECT);
        }
     }
   else
     {
      if(InpRiskPercent <= 0.0 || InpRiskPercent > 10.0)
        {
         PrintFormat("RegimeTrend_EA: InpRiskPercent %.2f must be between 0.1%% and 10.0%%.",InpRiskPercent);
         return(INIT_PARAMETERS_INCORRECT);
        }
     }

   if(InpUseSessionFilter &&
      (InpStartHourGMT < 0 || InpStartHourGMT > 23 || InpEndHourGMT < 0 || InpEndHourGMT > 24 ||
       InpStartHourGMT == InpEndHourGMT))
     {
      PrintFormat("RegimeTrend_EA: invalid session hours [%d-%d] GMT.",InpStartHourGMT,InpEndHourGMT);
      return(INIT_PARAMETERS_INCORRECT);
     }

   if(InpMinStopAtr > 0.0 || InpMaxStopAtr > 0.0 || InpSlAtrMult > 0.0 ||
      InpTrailSource == TRAIL_SRC_CHANDELIER || InpTrailSource == TRAIL_SRC_ATR_CLOSE)
     {
      g_atr_handle = iATR(_Symbol,_Period,InpAtrPeriod);
      if(g_atr_handle == INVALID_HANDLE)
        {
         PrintFormat("RegimeTrend_EA: iATR failed, error %d.",GetLastError());
         return(INIT_FAILED);
        }
     }

   //--- v1.50 validation of the new inputs
   if(InpLockTriggerR > 0.0 && InpLockR >= InpLockTriggerR)
     {
      Print("RegimeTrend_EA: InpLockR must be smaller than InpLockTriggerR.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpPartialR > 0.0 && (InpPartialPercent <= 0.0 || InpPartialPercent >= 100.0))
     {
      Print("RegimeTrend_EA: InpPartialPercent must be between 0 and 100 (exclusive).");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpTrailSource == TRAIL_SRC_SUPERTREND_TIGHT)
     {
      if(InpTrailAtrMult <= 0.0)
        {
         Print("RegimeTrend_EA: InpTrailAtrMult must be > 0 for the tight SuperTrend trailing source.");
         return(INIT_PARAMETERS_INCORRECT);
        }
      //--- same indicator, same inputs, only the ATR multiplier differs
      g_trail_handle = iCustom(_Symbol,_Period,REGIME_INDICATOR_RESOURCE,
                               InpRegimeTF,InpErPeriod,InpEnterTrend,InpExitTrend,
                               InpAtrPeriod,InpTrailAtrMult,
                               InpMinDwell,InpShockMult,InpUseClosedBars,false,
                               InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                               InpMacroDeadbandPct,InpMacroMinDwell,
                               false);
      if(g_trail_handle == INVALID_HANDLE)
         g_trail_handle = iCustom(_Symbol,_Period,"Foundry\\RegimeTrend",
                                  InpRegimeTF,InpErPeriod,InpEnterTrend,InpExitTrend,
                                  InpAtrPeriod,InpTrailAtrMult,
                                  InpMinDwell,InpShockMult,InpUseClosedBars,false,
                                  InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                                  InpMacroDeadbandPct,InpMacroMinDwell,
                                  false);
      if(g_trail_handle == INVALID_HANDLE)
        {
         PrintFormat("RegimeTrend_EA: iCustom for the tight trailing SuperTrend failed, error %d.",GetLastError());
         return(INIT_FAILED);
        }
     }

   XPMM_CONFIG mm; XPMM_Defaults(mm);
   mm.magic=InpMagic; mm.instance="RegimeTrend.v1";
   mm.lot_mode=InpRiskMode==RISK_FIXED_LOT ? XPMM_FIXED_LOTS : XPMM_PERCENT_EQUITY;
   mm.value=InpRiskMode==RISK_FIXED_LOT ? InpLotSize : InpRiskPercent;
   mm.max_lots=InpMaxLots; mm.max_margin_percent=InpMaxMarginPct;
   mm.require_sl=InpUseSuperTrendSL || InpRiskMode==RISK_PERCENT_EQUITY;
   mm.tp_mode=XPMM_TP_EXTERNAL; // EA calculates TP; library validates/rounds it
   mm.exclusive_netting=true;
   mm.deviation_points=InpSlippagePoints;
   mm.trail_mode=InpTrailSuperTrend ? XPMM_TRAIL_EXTERNAL : XPMM_TRAIL_OFF;
   mm.trail_step_points=InpTrailStepPoints;
   //--- v1.50: optional trailing activation threshold in R multiples
   mm.trail_trigger_unit=XPMM_R;
   mm.trail_trigger=InpTrailActivateR > 0.0 ? InpTrailActivateR : 0.0;
   if(!g_money.Configure(mm))
     {
      Print("RegimeTrend_EA: money manager: ",g_money.Reason());
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpUseBreakEven)
     {
      XPMM_BE_STAGE be; ZeroMemory(be);
      be.unit=XPMM_R; be.trigger=InpBreakEvenR; be.lock_points=InpBreakEvenBuffer;
      if(!g_money.AddBreakEven(be))
         return INIT_PARAMETERS_INCORRECT;
     }
   //--- v1.50: R-multiple lock-in stage and partial close, both handled by
   //--- the money manager alongside break-even and the trailing stop.
   if(InpLockTriggerR > 0.0)
     {
      XPMM_R_STAGE lock; ZeroMemory(lock);
      lock.trigger_r=InpLockTriggerR; lock.lock_r=InpLockR;
      if(!g_money.AddRTrail(lock))
        {
         Print("RegimeTrend_EA: money manager: ",g_money.Reason());
         return INIT_PARAMETERS_INCORRECT;
        }
     }
   if(InpPartialR > 0.0)
     {
      XPMM_PARTIAL_STAGE part; ZeroMemory(part);
      part.unit=XPMM_R; part.trigger=InpPartialR; part.percent_original=InpPartialPercent;
      if(!g_money.AddPartial(part))
        {
         Print("RegimeTrend_EA: money manager: ",g_money.Reason());
         return INIT_PARAMETERS_INCORRECT;
        }
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpSlippagePoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   g_last_bar_time = 0;
   if(InpShowGauge && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)))
     {
      g_ea_gauge.SetThresholds(InpExitTrend,InpEnterTrend);
      g_ea_gauge.SetMacroConfirm(InpUseMacroFilter || InpStrictMacroLongs || InpStrictMacroShorts);
      string name = "RegimeTrendEAGauge_" + (string)ChartID() + "_" + (string)InpMagic;
      if(g_ea_gauge.Create(ChartID(),name,InpGaugeCorner,InpGaugeX,InpGaugeY,InpGaugeSize))
        {
         g_ea_gauge.Render(-1.0,REGIME_UNSET,0);
         EventSetTimer(1);
         UpdateEAGauge();
        }
      else
         Print("RegimeTrend_EA: could not create the chart gauge.");
     }
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_money.Shutdown();
   EventKillTimer();
   g_ea_gauge.Destroy();
   if(g_handle != INVALID_HANDLE)
      IndicatorRelease(g_handle);
   if(g_trail_handle != INVALID_HANDLE)
      IndicatorRelease(g_trail_handle);
   if(g_atr_handle != INVALID_HANDLE)
      IndicatorRelease(g_atr_handle);
  }
//+------------------------------------------------------------------+
//| Finds this EA's own open position on this symbol.                |
//+------------------------------------------------------------------+
bool FindOwnPosition(ulong &ticket,int &side,double &open_price,double &current_sl,double &current_tp)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk))
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic)
         continue;
      ticket     = tk;
      side       = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      open_price = PositionGetDouble(POSITION_PRICE_OPEN);
      current_sl = PositionGetDouble(POSITION_SL);
      current_tp = PositionGetDouble(POSITION_TP);
      return(true);
     }
   return(false);
  }
//+------------------------------------------------------------------+
//| Forward fills and broker responses to the portable manager.     |
//| Original risk is recovered there; no fabricated R fallback.     |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &tx,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   g_money.OnTradeTransaction(tx,request,result);
  }
//+------------------------------------------------------------------+
void OnTick(void)
  {
   if(securityRemovalRequested)
      return;
   Security();
   if(securityRemovalRequested)
      return;

//--- A committed exit has priority and is retried on later ticks even if
//--- the regime signal disappears. This path does not wait for a new bar.
   if(g_exit_ticket != 0)
     {
      ManagePendingExit();
      return;
     }

//--- act once per new bar, off the bar that has just fully closed
   datetime t0[];
   if(CopyTime(_Symbol,_Period,0,1,t0) != 1)
      return;
   if(t0[0] == g_last_bar_time)
      return;
//--- g_last_bar_time is set only after every required read succeeds,
//--- so a transient data delay retries on the next tick instead of
//--- silently skipping this bar's signal.

//--- Quotes can arrive before the broker accepts orders (XM GOLD quotes
//--- from 01:00 and trades from 01:02 server time). Leave the bar pending
//--- until its trade session opens so its entry, exit and trailing stop
//--- are not refused as "market closed".
   if(!XPMM_TradeSessionOpen(_Symbol,TimeCurrent()))
      return;
   if(t0[0] == g_entry_retry_bar && TimeCurrent() < g_entry_retry_at)
      return;

   if(BarsCalculated(g_handle) < 3)
      return;

//--- shift 1 = last closed bar (what this EA acts on), shift 2 = the
//--- bar before it (needed to detect "just became Trending").
   double regime[], direction[], st[], macro[];
   ArraySetAsSeries(regime,true);
   ArraySetAsSeries(direction,true);
   ArraySetAsSeries(st,true);
   ArraySetAsSeries(macro,true);

   if(CopyBuffer(g_handle,5,1,2,regime) != 2)
      return;
   if(CopyBuffer(g_handle,6,1,2,direction) != 2)
      return;

   bool have_st = false;
   if(InpUseSuperTrendSL || InpTrailSuperTrend || InpUseBreakEven)
     {
      if(CopyBuffer(g_handle,0,1,1,st) != 1)
         return;
      have_st = (st[0] != EMPTY_VALUE && st[0] > 0.0);
     }

   bool need_macro = InpUseMacroFilter || InpStrictMacroShorts || InpStrictMacroLongs;
   bool have_macro = false;
   if(need_macro)
     {
      if(CopyBuffer(g_handle,7,1,1,macro) != 1)
         return;
      have_macro = true;
     }

//--- v1.50 extra readings (all shift 1 = last closed bar)
   double er_buf[], dwell_buf[], rawdir_buf[], atr_buf[], st_tight[];
   double er_now = -1.0, atr_now = 0.0, st_tight_now = 0.0;
   int    dwell_now = 0, rawdir_now = 0;
   bool   need_er = (InpMinErEntry > 0.0 || InpErExit > 0.0);
   if(need_er)
     {
      if(CopyBuffer(g_handle,2,1,1,er_buf) != 1)
         return;
      er_now = er_buf[0];
     }
   if(InpLateEntryBars > 0)
     {
      if(CopyBuffer(g_handle,4,1,1,dwell_buf) != 1)
         return;
      dwell_now = (int)dwell_buf[0];
     }
   if(InpExitOnStFlip)
     {
      if(CopyBuffer(g_handle,12,1,1,rawdir_buf) != 1)
         return;
      rawdir_now = (rawdir_buf[0] > 0.0) ? 1 : -1;
     }
   if(g_atr_handle != INVALID_HANDLE)
     {
      if(CopyBuffer(g_atr_handle,0,1,1,atr_buf) != 1)
         return;
      atr_now = atr_buf[0];
     }
   if(g_trail_handle != INVALID_HANDLE)
     {
      if(CopyBuffer(g_trail_handle,0,1,1,st_tight) != 1)
         return;
      st_tight_now = (st_tight[0] != EMPTY_VALUE && st_tight[0] > 0.0) ? st_tight[0] : 0.0;
     }

   g_money.Refresh();
   datetime prev_bar_time = g_last_bar_time;
   g_last_bar_time = t0[0];
   UpdateEAGauge();

   int reg_now   = (int)regime[0];      // Shift 1: last closed bar
   int reg_prev  = (int)regime[1];      // Shift 2: bar before it
   int dir_now   = (int)direction[0];   // Shift 1
   int macro_now = have_macro ? (int)macro[0] : 0;

   ulong  ticket;
   int    open_side;
   double open_price, current_sl, current_tp;
   bool   have_pos = FindOwnPosition(ticket,open_side,open_price,current_sl,current_tp);

//--- v1.50: a position that vanished without an EA exit signal was closed
//--- by its SL/TP - remember the leg so a late re-entry can be allowed.
   if(g_had_pos && !have_pos && !g_signal_exit)
      g_leg_stopped_time = g_leg_traded_time;
   g_had_pos = have_pos;

//--- 1. MANAGE OPEN POSITION
   if(have_pos)
     {
      // One library decision chooses the tightest valid BE/trailing stop.
      if(PositionSelectByTicket(ticket))
        {
         ulong identifier=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         //--- v1.50: trailing candidate from the selected source; the money
         //--- manager still applies the step, validity and "never loosen" rules.
         double trail_candidate = 0.0;
         if(InpTrailSuperTrend)
           {
            int bars_held = iBarShift(_Symbol,_Period,(datetime)PositionGetInteger(POSITION_TIME),false);
            if(bars_held < 1) bars_held = 1;
            switch(InpTrailSource)
              {
               case TRAIL_SRC_SUPERTREND_TIGHT:
                  trail_candidate = st_tight_now;
                  break;
               case TRAIL_SRC_CHANDELIER:
                  if(atr_now > 0.0)
                    {
                     if(open_side == 1)
                       {
                        int hi = iHighest(_Symbol,_Period,MODE_HIGH,bars_held,1);
                        if(hi >= 0) trail_candidate = iHigh(_Symbol,_Period,hi) - InpTrailAtrK * atr_now;
                       }
                     else
                       {
                        int lo = iLowest(_Symbol,_Period,MODE_LOW,bars_held,1);
                        if(lo >= 0) trail_candidate = iLow(_Symbol,_Period,lo) + InpTrailAtrK * atr_now;
                       }
                    }
                  break;
               case TRAIL_SRC_ATR_CLOSE:
                  if(atr_now > 0.0)
                     trail_candidate = (open_side == 1) ? iClose(_Symbol,_Period,1) - InpTrailAtrK * atr_now
                                                        : iClose(_Symbol,_Period,1) + InpTrailAtrK * atr_now;
                  break;
               default:
                  trail_candidate = have_st ? st[0] : 0.0;
              }
           }
         g_money.SetContext(identifier,0.0,trail_candidate);
         g_money.Manage();
        }

      //--- C. Indicator Exit Condition
      bool exit_signal = false;
      string exit_reason = "";

      if(InpExitMode == EXIT_ON_LEAVE_TREND)
        {
         if(reg_now != REGIME_LEVEL_TRENDING)
           {
            exit_signal = true;
            exit_reason = "regime left Trending";
           }
         else if(dir_now != 0 && dir_now != open_side)
           {
            exit_signal = true;
            exit_reason = "direction flipped";
           }
        }
      else // EXIT_ON_CHOPPY_OR_FLIP
        {
         if(reg_now == REGIME_LEVEL_CHOPPY)
           {
            exit_signal = true;
            exit_reason = "regime reached Choppy";
           }
         else if(dir_now != 0 && dir_now != open_side)
           {
            exit_signal = true;
            exit_reason = "direction flipped against position";
           }
        }

      //--- v1.50 additional exits, evaluated in this fixed order
      if(!exit_signal && InpExitOnStFlip && rawdir_now != 0 && rawdir_now != open_side)
        {
         exit_signal = true;
         exit_reason = "raw SuperTrend flipped";
        }
      if(!exit_signal && InpErExit > 0.0 && er_now >= 0.0 && er_now < InpErExit)
        {
         exit_signal = true;
         exit_reason = StringFormat("ER %.2f below exit level %.2f",er_now,InpErExit);
        }
      if(!exit_signal && InpMaxBarsInTrade > 0 && PositionSelectByTicket(ticket))
        {
         int bars_held = iBarShift(_Symbol,_Period,(datetime)PositionGetInteger(POSITION_TIME),false);
         if(bars_held >= InpMaxBarsInTrade)
           {
            exit_signal = true;
            exit_reason = StringFormat("time stop after %d bars",bars_held);
           }
        }
      if(!exit_signal && InpCloseFridayHour > 0)
        {
         MqlDateTime fdt;
         TimeToStruct(SessionClockGMT(),fdt);
         if(fdt.day_of_week == 5 && fdt.hour >= InpCloseFridayHour)
           {
            exit_signal = true;
            exit_reason = "Friday close";
           }
        }

      if(exit_signal)
        {
         PrintFormat("RegimeTrend_EA: closing %s @ %s - regime=%d direction=%d (%s).",
                     (open_side == 1 ? "BUY" : "SELL"),
                     TimeToString(t0[0],TIME_DATE|TIME_MINUTES),
                     reg_now,dir_now,exit_reason);
         g_exit_ticket = ticket;
         g_signal_exit = true;
         ManagePendingExit();
        }
      return;   // One decision per bar: don't also open on the exit bar
     }

//--- 2. OPEN NEW POSITION WHEN FLAT
//--- Enter only on the transition bar into Trending, never chasing...
   bool transition = (reg_now == REGIME_LEVEL_TRENDING && reg_prev != REGIME_LEVEL_TRENDING &&
                      (dir_now == 1 || dir_now == -1));
//--- ...unless v1.50 late entry allows the first N bars of a leg that the
//--- EA has not traded yet (or was stopped out of, with InpReentryAfterStop).
   bool     late_entry = false;
   datetime leg_time   = 0;
   if(!transition && InpLateEntryBars > 0 && reg_now == REGIME_LEVEL_TRENDING &&
      (dir_now == 1 || dir_now == -1) && dwell_now >= 2 && dwell_now - 1 <= InpLateEntryBars)
     {
      leg_time = iTime(_Symbol,_Period,dwell_now);   // bar on which this leg started
      if(leg_time != 0)
        {
         if(leg_time != g_leg_traded_time)
            late_entry = true;
         else if(InpReentryAfterStop && g_leg_stopped_time == leg_time)
            late_entry = true;
        }
     }
   if(transition)
      leg_time = t0[0] == 0 ? 0 : iTime(_Symbol,_Period,1);

   if(transition || late_entry)
     {
      //--- v1.50: required state before the transition
      if(transition && InpEntryPrevState == ENTRY_PREV_NEUTRAL && reg_prev != REGIME_LEVEL_NEUTRAL)
         return;
      if(transition && InpEntryPrevState == ENTRY_PREV_CHOPPY && reg_prev != REGIME_LEVEL_CHOPPY)
         return;

      //--- Direction filter (open positions are still managed and exited)
      if((InpTradeDirection == TRADE_LONG_ONLY && dir_now != 1) ||
         (InpTradeDirection == TRADE_SHORT_ONLY && dir_now != -1))
         return;

      //--- Session filter check
      if(InpUseSessionFilter)
        {
         MqlDateTime dt;
         TimeToStruct(SessionClockGMT(),dt);
         if(!InSession(dt.hour))
           {
            PrintFormat("RegimeTrend_EA: signal detected at %02d:00 GMT but filtered by session [%02d:00-%02d:00].",
                        dt.hour,InpStartHourGMT,InpEndHourGMT);
            return;
           }
        }

      //--- Netting accounts hold one net position per symbol: never add to
      //--- or reverse a position this EA does not own.
      if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING &&
         PositionSelect(_Symbol))
        {
         PrintFormat("RegimeTrend_EA: netting account already has a %s position (magic %I64d). Entry skipped.",
                     _Symbol,PositionGetInteger(POSITION_MAGIC));
         return;
        }

      //--- Macro trend filters need a valid (warmed-up) reading
      if(need_macro && macro_now == REGIME_MACRO_UNSET)
        {
         Print("RegimeTrend_EA: H4 Macro Trend still warming up. Entry skipped.");
         return;
        }

      //--- Macro trend confluence filter
      if(InpUseMacroFilter && have_macro)
        {
         if(dir_now == 1 && macro_now < 0)
           {
            PrintFormat("RegimeTrend_EA: BUY signal filtered out by bearish H4 Macro Trend (%d).",macro_now);
            return;
           }
         if(dir_now == -1 && macro_now > 0)
           {
            PrintFormat("RegimeTrend_EA: SELL signal filtered out by bullish H4 Macro Trend (%d).",macro_now);
            return;
           }
        }
      if(InpStrictMacroShorts && dir_now == -1 && macro_now != REGIME_MACRO_DOWN)
        {
         PrintFormat("RegimeTrend_EA: SELL signal filtered out - H4 Macro Trend not Down (%d).",macro_now);
         return;
        }
      if(InpStrictMacroLongs && dir_now == 1 && macro_now != REGIME_MACRO_UP)
        {
         PrintFormat("RegimeTrend_EA: BUY signal filtered out - H4 Macro Trend not Up (%d).",macro_now);
         return;
        }

      //--- Initial Stop Loss from SuperTrend line
      double sl = 0.0;
      double tp = 0.0;
      double ask = SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
      long stops_lvl = SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
      long freeze_lvl = SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL);
      double min_d = (double)MathMax(stops_lvl,freeze_lvl) * _Point;
      double tick_size = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      if(ask <= bid || bid <= 0.0 || tick_size <= 0.0)
        {
         Print("RegimeTrend_EA: invalid quote or tick size. Entry skipped.");
         return;
        }

      //--- v1.50 spread and signal-strength filters
      if(InpMaxSpreadPoints > 0 && (ask - bid) / _Point > (double)InpMaxSpreadPoints + 1e-9)
        {
         PrintFormat("RegimeTrend_EA: entry skipped - spread %.0f points above %d.",(ask - bid) / _Point,InpMaxSpreadPoints);
         return;
        }
      if(InpMinErEntry > 0.0 && er_now < InpMinErEntry)
        {
         PrintFormat("RegimeTrend_EA: entry skipped - ER %.2f below InpMinErEntry %.2f.",er_now,InpMinErEntry);
         return;
        }

      //--- Stop floor: never size off a stop tighter than the broker minimum,
      //--- InpMinStopPoints, or InpMinStopAtr x ATR of the last closed bar.
      double floor_d = MathMax(min_d,(double)InpMinStopPoints * _Point);
      bool need_atr = (InpMinStopAtr > 0.0 || InpMaxStopAtr > 0.0 || InpSlAtrMult > 0.0);
      if(need_atr && atr_now <= 0.0)
        {
         Print("RegimeTrend_EA: ATR not available for the stop calculation. Entry skipped.");
         return;
        }
      if(InpMinStopAtr > 0.0)
         floor_d = MathMax(floor_d,InpMinStopAtr * atr_now);

      if(InpSlAtrMult > 0.0)
        {
         //--- v1.50 ATR-based initial stop (SuperTrend is then only used for trailing)
         if(dir_now == 1)
           {
            double stop_price = MathMin(bid - InpSlAtrMult * atr_now,bid - floor_d);
            sl = NormalizeDouble(MathFloor(stop_price / tick_size + 1e-9) * tick_size,_Digits);
           }
         else
           {
            double stop_price = MathMax(ask + InpSlAtrMult * atr_now,ask + floor_d);
            sl = NormalizeDouble(MathCeil(stop_price / tick_size - 1e-9) * tick_size,_Digits);
           }
        }
      else if(InpUseSuperTrendSL && have_st)
        {
         double candidate_sl = st[0];
         if(dir_now == 1) // BUY
           {
            if(candidate_sl < bid)
              {
               double stop_price = MathMin(candidate_sl,bid - floor_d);
               //--- v1.50: cap the distance so a far SuperTrend does not shrink R
               if(InpMaxStopAtr > 0.0)
                  stop_price = MathMax(stop_price,bid - InpMaxStopAtr * atr_now);
               sl = NormalizeDouble(MathFloor(stop_price / tick_size + 1e-9) * tick_size,_Digits);
              }
            else
              {
               PrintFormat("RegimeTrend_EA: Rejected BUY entry - SuperTrend SL (%.5f) is at/above Bid (%.5f).",candidate_sl,bid);
               return;
              }
           }
         else if(dir_now == -1) // SELL
           {
            if(candidate_sl > ask)
              {
               double stop_price = MathMax(candidate_sl,ask + floor_d);
               if(InpMaxStopAtr > 0.0)
                  stop_price = MathMin(stop_price,ask + InpMaxStopAtr * atr_now);
               sl = NormalizeDouble(MathCeil(stop_price / tick_size - 1e-9) * tick_size,_Digits);
              }
            else
              {
               PrintFormat("RegimeTrend_EA: Rejected SELL entry - SuperTrend SL (%.5f) is at/below Ask (%.5f).",candidate_sl,ask);
               return;
              }
           }
        }
      else if(InpRiskMode == RISK_PERCENT_EQUITY && sl <= 0.0)
        {
         Print("RegimeTrend_EA: Cannot calculate dynamic % equity risk without a valid Stop Loss. Entry skipped.");
         return;
        }

      //--- Optional Take Profit multiple
      if(InpTakeProfitR > 0.0 && sl > 0.0)
        {
         if(dir_now == 1)
           {
            double r_dist = ask - sl;
            tp = NormalizeDouble(ask + InpTakeProfitR * r_dist,_Digits);
           }
         else if(dir_now == -1)
           {
            double r_dist = sl - bid;
            tp = NormalizeDouble(bid - InpTakeProfitR * r_dist,_Digits);
           }
        }

      double entry_ref = (dir_now == 1) ? ask : bid;
      double lots = CalculateLotSize(dir_now == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,entry_ref,sl,tp);
      if(lots <= 0.0)
         return;

      bool ok = TradeDone((dir_now == 1)
                          ? g_trade.Buy(lots,_Symbol,0.0,sl,tp,"RegimeTrend")
                          : g_trade.Sell(lots,_Symbol,0.0,sl,tp,"RegimeTrend"),
                          "open");

      PrintFormat("RegimeTrend_EA: %s %s %.2f lots @ %s - %s (dir=%d, macro=%d, SL=%.2f, TP=%.2f).",
                  ok ? "opened" : "FAILED to open",
                  (dir_now == 1 ? "BUY" : "SELL"),
                  ok ? g_trade.ResultVolume() : lots,TimeToString(t0[0],TIME_DATE|TIME_MINUTES),
                  transition ? "regime just became Trending" : StringFormat("late entry, %d bars into the leg",dwell_now - 1),
                  dir_now,macro_now,sl,tp);
      if(ok)
        {
         g_leg_traded_time = leg_time;
         g_signal_exit     = false;
         g_had_pos         = true;
        }

      //--- The session table said open but the server still refused (e.g. a
      //--- holiday schedule): keep this bar's signal and retry it in a minute,
      //--- never past the bar.
      if(!ok && g_trade.ResultRetcode() == TRADE_RETCODE_MARKET_CLOSED)
        {
         g_last_bar_time   = prev_bar_time;
         g_entry_retry_bar = t0[0];
         g_entry_retry_at  = TimeCurrent() + 60;
         Print("RegimeTrend_EA: market closed - this bar's entry will be retried in 60 s.");
        }
     }
  }
//+------------------------------------------------------------------+
