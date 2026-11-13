//+------------------------------------------------------------------+
//|                                  XAUUSD_Loma_TrendPullback.mq5   |
//|                                                                  |
//|  Strategy : XAUUSD "Loma" (MACD hump) Trend Pullback, both sides |
//|  Version  : 1.33                                                 |
//+------------------------------------------------------------------+
//
//  "No signal = no trade."
//
//  Reference implementation of the rules: research/hump_engine.py (signals() / simulate()).
//
//  VOCABULARY
//  ----------
//  A HUMP ("loma") is a run of consecutive CLOSED TriggerTimeframe bars with the MACD(12,26,9)
//  main line on one side of zero: >= 0 is a positive hump, < 0 a negative hump. For every hump
//  the EA tracks: number of bars, peak (largest |MACD|), highest high, lowest low and the
//  Stochastic(7,1,7) main-line minimum and maximum reached while it lasted.
//
//  RULES
//  -----
//    R1  Trend comes first. The peaks of the last BigHumpHistory completed humps are kept in a
//        ring. A completed hump is BIG when at least 5 peaks are known, its peak is
//        >= BigHumpMultiplier x the median of the ring (before this hump is added), it lasted
//        >= BigHumpMinBars bars and, with RequireStochLevel, the Stochastic reached <= StochLow
//        during a negative hump / >= StochHigh during a positive hump.
//        Big negative hump -> BEARISH trend. Big positive hump -> BULLISH trend. The trend is
//        anchored on that hump (anchor peak, anchor bar, signals used = 0).
//        No big hump in force -> LINEAL (linear market): no trades.
//    R2  Trend break: an opposite hump (completed or still forming) whose peak reaches
//        TrendBreakRatio x the anchor peak ends the trend -> LINEAL. (A completed opposite hump
//        that is itself big starts the opposite trend instead.)
//    R3  Trend lapse: no more signals once MaxSignalsPerBigHump signals were produced after the
//        anchor hump, or more than TrendMaxBars bars passed since the anchor hump ended. A new
//        big hump resets both.
//    R4  SELL signal (BEARISH and alive): on the closed bar where the MACD crosses below zero
//        (previous bar >= 0, this bar < 0), provided the positive (pullback) hump that just
//        ended had >= PullbackMinBars bars and a peak <= PullbackMaxRatio x the anchor peak, and
//        a previous negative hump low exists. A bare touch of zero without a hump is no signal.
//        With SkipBigPullback, a pullback hump that is itself BIG (R1) is a trend change, not a
//        pullback: no signal is produced and it does not count against MaxSignalsPerBigHump.
//        Ordering (as in signals()): the signal check uses the trend in force BEFORE the hump
//        that just ended is classified; then that hump is classified (big -> new trend, or
//        trend break); then the previous-hump extremes and the ring are updated.
//    R5  SELL plan, entry at market on the first tick of the next bar (bid):
//          SL = max(high of the pullback hump, high of the signal bar) + SL_Buffer_Points
//               + current spread (a short is stopped on the ask).
//          TP (TP_PREV_HUMP) = low of the previous negative hump, anticipated:
//               TP = low + TP_Anticipation x (entry - low), + current spread.
//          TP (TP_FIXED_RR)  = entry - TP_RR x risk.
//          Skipped when reward < MinRewardRisk x risk or the risk is outside
//          MinSL_Points / MaxSL_Points.
//    R6  BUY is the exact mirror (BULLISH trend, negative pullback hump, MACD crossing above
//        zero, SL below the pullback low, TP before the previous positive hump high).
//        MT5 charts are BID charts: a long is stopped and paid on the bid, so the buy SL/TP
//        need no spread term (the reference backtest works on mid quotes and applies half a
//        spread to both sides, which is the same thing).
//    R7  Optional higher-timeframe filter: sell only if the last closed HTF bar closed below
//        its EMA(50), buy only if above.
//    R8  Risk: RiskPercent of equity per trade, lot from the SL distance, ONE position at a
//        time (magic number), spread filter, trading hours (broker server time), news filter,
//        optional trailing in R multiples (TrailStartR / TrailDistanceR).
//    R9  Optional weekend flat (CloseBeforeWeekend): on Friday from WeekendCloseTime (broker
//        server time) on, no new entries are taken and the open position is closed at market
//        on the first tick. A position found open on a Saturday or Sunday (restart, missed
//        close) is closed on the first tick available, unless it was opened on that same
//        day: entries are blocked on Friday only, so on a broker whose week opens on Sunday
//        (server time) the Sunday session trades normally. A failed close is retried at
//        most once every WEEKEND_RETRY_SEC seconds, and not at all while algo trading is off.
//    R10 Optional time exits; neither blocks new entries (only the signal of the trigger bar
//        on which the time exit happens is not traded, as in the reference backtest):
//        MaxHoldMinutes > 0: the position is closed at market once it has been open that many
//        minutes, counted in M1 bars after the entry bar as in the reference backtest (minutes
//        without quotes - daily break, weekend - do not count). Without M1 history the
//        clock time since the position was opened is used.
//        CloseAtEndOfDay: the position is closed at market once the server time of day is at
//        or after EndOfDayTime, if it was opened before today's EndOfDayTime. A position
//        opened after that time is kept until the next day's EndOfDayTime. A close that was
//        due on an earlier day but did not happen (algo trading off, EA not running) is
//        made on the first tick available.
//        Failed closes are retried like the weekend close (WEEKEND_RETRY_SEC).
//
//  STATE AFTER ATTACH / RESTART
//  ----------------------------
//  The hump state (trend, anchor, ring, current hump) is rebuilt by replaying the last
//  HumpWarmupBars closed TriggerTimeframe bars through the same state machine, without trading.
//  Afterwards every newly closed bar is processed exactly once; when several bars closed
//  between two ticks the missed ones are replayed in order and only a signal on the most
//  recent closed bar can be traded.
//
//  POINT UNITS
//  -----------
//  All *_Points inputs are written for a 2-digit XAUUSD quote (1 point = 0.01). With
//  AutoScalePoints=true they are rescaled automatically on other quote precisions.
//
//  NOTES
//  -----
//  * Signals are computed on TriggerTimeframe bars whatever the chart timeframe is.
//  * The MT5 economic calendar is not available in the Strategy Tester: the news filter is
//    bypassed there (a warning is printed once).
//  * Entry parity with the reference backtest: a signal is decided once, on the first tick
//    of the bar after the cross. If a position is open, the spread is too wide, the session
//    is closed or news is blocking at that moment, the signal is dropped (no retry later in
//    the bar). A signal whose bar is followed by a market gap (next bar more than one period
//    late: daily break, weekend) is not traded. After a restart inside the entry bar the
//    deal history is checked so the same signal is never entered twice.
//  * A signal counts against MaxSignalsPerBigHump when it is produced, even if the trade is
//    then skipped (spread, session, reward/risk, HTF filter, position already open), exactly
//    as in the reference backtest.
//  * Weekend close: the reference backtest (weekend_close / weekend_min) closes at the close of
//    the first M1 bar inside the Friday window, and also on the last bar before any closure of
//    24 hours or more (holidays). The EA closes on the first tick of the window and cannot
//    foresee a holiday closure: only Friday and Saturday/Sunday are handled.
//  * Time exits: the reference backtest (max_hold / eod) closes at the close of the M1 bar that
//    reaches the holding limit or crosses the end-of-day time; the EA closes on the first tick
//    at or after that moment.
//+------------------------------------------------------------------+
#property copyright   "mreyesllc89"
#property version     "1.33"
#property strict
#property description "XAUUSD Loma (MACD hump) Trend Pullback, sells and buys."
#property description "Big MACD hump defines the trend; trade the zero-cross after a small pullback hump."
#property description "No signal = no trade."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
//--- EA Validation Kit: records every trade in the Strategy Tester and exports
//    each optimization pass for  python -m evk analyze  (no effect on live trading).
//    Remove this line if EVK is not installed in MQL5/Include/EVK/.
#include <EVK/EVK.mqh>

//--- enums -----------------------------------------------------------
enum ENUM_SIGNAL_STATE
  {
   SIG_NONE     = 0, // evaluated: no valid signal on this bar
   SIG_VALID    = 1, // evaluated: valid signal
   SIG_NOTREADY = 2  // indicator / multi-timeframe data not up to date yet: retry next tick
  };

enum ENUM_LOMA_DIRECTION
  {
   DIR_BOTH      = 0, // BOTH: sells and buys
   DIR_SELL_ONLY = 1, // SELL_ONLY
   DIR_BUY_ONLY  = 2  // BUY_ONLY
  };

enum ENUM_LOMA_TP_MODE
  {
   TP_PREV_HUMP = 0, // extreme of the previous hump on the trend side (anticipated)
   TP_FIXED_RR  = 1  // fixed reward:risk (TP_RR)
  };

//====================================================================
// INPUTS
//====================================================================
input group "=== General ==="
input ulong   MagicNumber              = 26113001;     // Magic number
input string  TradeComment             = "LOMA";       // Order comment prefix
input ENUM_LOMA_DIRECTION TradeDirection = DIR_BOTH;   // Trade direction
input bool    AutoScalePoints          = true;         // *_Points are 0.01 price steps on any quote (rescale other digits)
input bool    VerboseLog               = true;         // Print decision log to Experts tab
input bool    ShowLevels               = true;         // Draw the SL/TP reference lines of the last signal
input bool    ShowStatusPanel          = true;         // Panel: trend state, anchor hump, signals used, current hump
input bool    MarkSignals              = true;         // Arrow on the chart at every valid signal
input bool    ShowHumpLabels           = true;         // Mark big humps on the chart

input group "=== Hump engine (MACD / Stochastic on the trigger timeframe) ==="
input ENUM_TIMEFRAMES TriggerTimeframe = PERIOD_M2;    // Trigger timeframe (humps are built on its closed bars)
input int     MACD_Fast                = 12;    // MACD fast EMA
input int     MACD_Slow                = 26;    // MACD slow EMA
input int     MACD_Signal              = 9;     // MACD signal SMA
input int     Stoch_K                  = 7;     // Stochastic %K period
input int     Stoch_Slowing            = 1;     // Stochastic slowing
input int     Stoch_D                  = 7;     // Stochastic %D (signal) period
input int     HumpWarmupBars           = 3000;  // Closed bars replayed on init to rebuild the hump state

input group "=== R1: Big hump -> trend ==="
input int     BigHumpHistory           = 20;    // Completed hump peaks kept for the median
input double  BigHumpMultiplier        = 1.5;   // Big hump: peak >= this x median peak
input int     BigHumpMinBars           = 5;     // Big hump: minimum bars
input bool    RequireStochLevel        = true;  // Big hump must reach the Stochastic level below
input double  StochLow                 = 20.0;  // Negative big hump: Stochastic reached <= this
input double  StochHigh                = 80.0;  // Positive big hump: Stochastic reached >= this

input group "=== R2/R3: Trend break and lapse ==="
input double  TrendBreakRatio          = 1.0;   // Opposite hump peak >= this x anchor peak ends the trend
input int     MaxSignalsPerBigHump     = 2;     // Signals taken after one big hump
input int     TrendMaxBars             = 120;   // Trend lapses this many bars after the anchor hump ended

input group "=== R4: Pullback hump ==="
input int     PullbackMinBars          = 3;     // Pullback hump: minimum bars
input double  PullbackMaxRatio         = 0.6;   // Pullback hump: peak <= this x anchor peak
input bool    SkipBigPullback          = true;  // No signal when the pullback hump is itself a big hump (trend change)

input group "=== R5: Stop loss / take profit ==="
input int     SL_Buffer_Points         = 30;    // SL buffer beyond the pullback hump extreme (points)
input ENUM_LOMA_TP_MODE TP_Mode        = TP_PREV_HUMP; // Take-profit mode
input double  TP_Anticipation          = 0.10;  // TP_PREV_HUMP: fraction of the distance left before the level
input double  TP_RR                    = 1.5;   // TP_FIXED_RR: reward:risk
input double  MinRewardRisk            = 0.8;   // Skip when reward < this x risk
input int     MinSL_Points             = 50;    // Min SL distance (points)
input int     MaxSL_Points             = 0;     // Max SL distance (points, 0 = off)

input group "=== R7: Higher-timeframe filter ==="
input bool            UseHTFFilter     = false;      // Sell only below / buy only above the HTF EMA
input ENUM_TIMEFRAMES HTF_Timeframe    = PERIOD_H4;  // Higher timeframe
input int             HTF_EMA_Period   = 50;         // HTF EMA period

input group "=== R8: Risk & Position ==="
input double  RiskPercent              = 0.75;  // Risk per trade, % of equity
input double  MaxLotSize               = 0.0;   // Max lot (0 = broker max)
input bool    SkipIfBelowMinLot        = true;  // Skip trade if risk lot < broker min lot
input int     MaxSpread_Points         = 60;    // Max spread (points)
input int     MaxSlippage_Points       = 20;    // Max slippage (points)
input int     MaxEntryDelaySeconds     = 0;     // Enter only within N s of bar open (0 = no limit, first tick)

input group "=== R8: Trailing stop (R multiples) ==="
input double  TrailStartR              = 0.0;   // Start trailing at this profit in R (0 = off)
input double  TrailDistanceR           = 0.5;   // Trailing distance in R
input int     TrailStep_Points         = 10;    // Min SL improvement per modification (points)

input group "=== R8: Session / News ==="
input bool    UseTradingHours          = false;    // Restrict to trading hours (broker server time)
input string  TradingHoursStart        = "07:00";  // Start HH:MM, server time
input string  TradingHoursEnd          = "20:00";  // End   HH:MM, server time
input bool    CloseBeforeWeekend       = false;    // Friday: no new entries and close the open position
input string  WeekendCloseTime         = "23:00";  // Friday HH:MM, server time
input bool    UseNewsFilter            = true;     // Skip around high-impact news
input string  NewsCurrency             = "USD";    // News currency
input int     NewsWindowMinutes        = 30;       // +/- minutes around the event

input group "=== R10: Time exits ==="
input int     MaxHoldMinutes           = 0;        // Close the position after this many minutes open (0 = off)
input bool    CloseAtEndOfDay          = false;    // Close the open position at EndOfDayTime every day
input string  EndOfDayTime             = "22:00";  // End of day HH:MM, server time

//====================================================================
// GLOBALS
//====================================================================
CTrade        g_trade;
CPositionInfo g_pos;

int      g_hMacd     = INVALID_HANDLE;   // MACD on the trigger timeframe
int      g_hStoch    = INVALID_HANDLE;   // Stochastic on the trigger timeframe
int      g_hEmaHTF   = INVALID_HANDLE;   // EMA on the higher timeframe (optional)

double   g_ptScale        = 1.0;   // point scale factor (AutoScalePoints)
int      g_sessStartMin   = 0;
int      g_sessEndMin     = 0;
int      g_weekendMin     = 0;     // WeekendCloseTime in minutes from midnight
bool     g_weekendLogged  = false; // weekend close announced (once per weekend window)
bool     g_weekendFailLog = false; // failed weekend close reported (once per weekend window)
datetime g_weekendLastTry = 0;     // server time of the last failed weekend close (retry throttle)
// minimum seconds between weekend close retries (also used by the R10 time exits)
#define  WEEKEND_RETRY_SEC 5
int      g_eodMin         = 0;     // EndOfDayTime in minutes from midnight
ulong    g_timeExitLogged  = 0;    // ticket whose time exit was announced (once per position)
ulong    g_timeExitFailLog = 0;    // ticket whose failed time exit was reported (once per position)
datetime g_timeExitLastTry = 0;    // server time of the last failed time exit (retry throttle)
datetime g_timeExitBar     = 0;    // trigger bar on which a time exit was last due (its signal is not traded)

datetime g_lastBarTime    = 0;     // last evaluated trigger bar (open time of the forming bar)
datetime g_signalBarTime  = 0;     // forming bar on which a valid signal is active
bool     g_signalActive   = false;
datetime g_lastTradeBar   = 0;     // bar on which we last opened a trade

datetime g_newsCheckTime  = 0;
bool     g_newsBlocked    = false;
bool     g_newsWarned     = false;
string   g_lastSkipReason = "";    // de-duplicates the journal (reset every bar)
string   g_panelSkip      = "none";// last skip reason shown on the panel

const string OBJ_PREFIX   = "LOMA_";

//--- hump state machine (mirrors signals() in research/hump_engine.py) ---
bool     g_stateReady  = false;    // history replay done
bool     g_quiet       = false;    // true while replaying history (no journal lines)
datetime g_lastProcTime = 0;       // open time of the last closed bar fed to the state machine
datetime g_prevBarTime = 0;        // open time of the bar processed before the current one
long     g_barIdx      = 0;        // index of the next bar to process ("i" in signals())

int      g_cs          = 0;        // sign of the hump being formed (+1 / -1, 0 = none yet)
int      g_cN          = 0;        // its bar count
double   g_cPeak       = 0.0;      // its peak |MACD|
double   g_cHi         = -DBL_MAX; // its highest high
double   g_cLo         = DBL_MAX;  // its lowest low
double   g_cSmin       = 101.0;    // its Stochastic minimum
double   g_cSmax       = -1.0;     // its Stochastic maximum

bool     g_hasNegLo    = false;    // a negative hump has completed
double   g_lastNegLo   = 0.0;      // low of the previous completed negative hump
bool     g_hasPosHi    = false;    // a positive hump has completed
double   g_lastPosHi   = 0.0;      // high of the previous completed positive hump

int      g_trend       = 0;        // -1 BEARISH, +1 BULLISH, 0 LINEAL
double   g_anchorPeak  = 0.0;      // peak of the big hump that anchors the trend
long     g_anchorBar   = -1;       // index of the last bar of the anchor hump
int      g_used        = 0;        // signals produced since the anchor hump

double   g_peaks[];                // ring of completed hump peaks
int      g_pkN         = 0;        // humps completed so far
int      g_pkI         = 0;        // ring write position

//--- signal produced by the most recent closed bar (0 = none)
int      g_sigSide     = 0;        // +1 buy, -1 sell
datetime g_sigClosedBar = 0;       // open time of the closed bar the pending signal belongs to
double   g_sigSlRef    = 0.0;      // pullback hump extreme (incl. the signal bar)
double   g_sigTpRef    = 0.0;      // previous hump extreme on the trend side
double   g_sigRatio    = 0.0;      // pullback peak / anchor peak
int      g_sigPbBars   = 0;        // bars of the pullback hump

//--- trade plan
struct TradePlan
  {
   int    side;       // +1 buy, -1 sell
   double entry;      // Bid (sell) / Ask (buy) at planning time
   double sl;         // final SL price
   double tp;         // final TP price
   double slRef;      // pullback hump extreme used for the SL
   double tpRef;      // previous hump extreme used for the TP (0 in fixed-RR mode)
  };

//====================================================================
// HELPERS
//====================================================================
void Log(const string msg)
  {
   if(VerboseLog)
      Print("[LOMA] ", msg);
  }

//--- log a "no trade" reason only when it changes (avoid per-tick spam)
void LogSkip(const string reason)
  {
   if(reason == g_lastSkipReason)
      return;
   g_lastSkipReason = reason;
   g_panelSkip      = TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES) + " " + reason;
   Log("No trade: " + reason);
  }

//--- convert an input in "2-digit gold points" to a price distance
double Pts(const double points)
  {
   return points * g_ptScale * _Point;
  }

double NormalizePrice(const double price)
  {
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = _Point;
   return NormalizeDouble(MathRound(price / tick) * tick, _Digits);
  }

double Bid() { return SymbolInfoDouble(_Symbol, SYMBOL_BID); }
double Ask() { return SymbolInfoDouble(_Symbol, SYMBOL_ASK); }

//--- minimum distance from price for SL/TP enforced by the broker
double StopsLevelDistance()
  {
   long stops  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freeze = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   return (double)MathMax(stops, freeze) * _Point;
  }

//--- parse "HH:MM" into minutes from midnight
bool ParseHHMM(const string s, int &minutes)
  {
   string parts[];
   if(StringSplit(s, ':', parts) != 2)
      return false;
   int h = (int)StringToInteger(parts[0]);
   int m = (int)StringToInteger(parts[1]);
   if(h < 0 || h > 23 || m < 0 || m > 59)
      return false;
   minutes = h * 60 + m;
   return true;
  }

string GVKey(const string kind, const ulong ticket)
  {
   return OBJ_PREFIX + (string)MagicNumber + "_" + kind + "_" + (string)ticket;
  }

bool CopyOne(const int handle, const int buffer, const int shift, double &value)
  {
   double tmp[];
   ArraySetAsSeries(tmp, false);
   if(CopyBuffer(handle, buffer, shift, 1, tmp) != 1)
      return false;
   value = tmp[0];
   return true;
  }

//--- "M3", "H1" ... instead of PERIOD_M3
string TFName(const ENUM_TIMEFRAMES tf)
  {
   ENUM_TIMEFRAMES t = (tf == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : tf;
   string n = EnumToString(t);
   StringReplace(n, "PERIOD_", "");
   return n;
  }

string SideName(const int side)
  {
   return (side > 0) ? "BUY" : (side < 0) ? "SELL" : "none";
  }

bool VisualsOff()
  {
   return (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE));
  }

//====================================================================
// OnInit
//====================================================================
int OnInit()
  {
   //--- sanity checks on inputs
   if(RiskPercent <= 0.0 || RiskPercent > 5.0)
     {
      Print("[LOMA] RiskPercent must be in (0, 5]. Got ", RiskPercent);
      return INIT_PARAMETERS_INCORRECT;
     }
   if(MACD_Fast >= MACD_Slow)
     {
      Print("[LOMA] MACD_Fast must be < MACD_Slow");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(BigHumpHistory < 5 || BigHumpMultiplier <= 0.0 || BigHumpMinBars < 1)
     {
      Print("[LOMA] BigHumpHistory must be >= 5, BigHumpMultiplier > 0 and BigHumpMinBars >= 1");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(PullbackMinBars < 1 || PullbackMaxRatio <= 0.0 || TrendBreakRatio <= 0.0 ||
      MaxSignalsPerBigHump < 1 || TrendMaxBars < 1)
     {
      Print("[LOMA] PullbackMinBars, PullbackMaxRatio, TrendBreakRatio, MaxSignalsPerBigHump and TrendMaxBars must be positive");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(HumpWarmupBars < 200)
     {
      Print("[LOMA] HumpWarmupBars must be >= 200");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(TP_Anticipation < 0.0 || TP_Anticipation >= 1.0)
     {
      Print("[LOMA] TP_Anticipation must be in [0, 1)");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(TP_Mode == TP_FIXED_RR && TP_RR <= 0.0)
     {
      Print("[LOMA] TP_RR must be > 0 in TP_FIXED_RR mode");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(TrailStartR > 0.0 && TrailDistanceR <= 0.0)
     {
      Print("[LOMA] TrailDistanceR must be > 0 when TrailStartR > 0");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(UseTradingHours)
     {
      if(!ParseHHMM(TradingHoursStart, g_sessStartMin) || !ParseHHMM(TradingHoursEnd, g_sessEndMin))
        {
         Print("[LOMA] TradingHoursStart/End must be HH:MM");
         return INIT_PARAMETERS_INCORRECT;
        }
     }
   if(CloseBeforeWeekend && !ParseHHMM(WeekendCloseTime, g_weekendMin))
     {
      Print("[LOMA] WeekendCloseTime must be HH:MM");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(MaxHoldMinutes < 0)
     {
      Print("[LOMA] MaxHoldMinutes must be >= 0 (0 = off). Got ", MaxHoldMinutes);
      return INIT_PARAMETERS_INCORRECT;
     }
   if(CloseAtEndOfDay && !ParseHHMM(EndOfDayTime, g_eodMin))
     {
      Print("[LOMA] EndOfDayTime must be HH:MM");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(UseHTFFilter && PeriodSeconds(HTF_Timeframe) <= PeriodSeconds(TriggerTimeframe))
     {
      Print("[LOMA] HTF_Timeframe must be higher than TriggerTimeframe");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0)
      Print("[LOMA] Warning: EA calibrated for XAUUSD, attached to ", _Symbol);

   //--- point scaling: inputs are written for 2-digit gold (0.01 point)
   g_ptScale = 1.0;
   if(AutoScalePoints && _Digits != 2)
      g_ptScale = MathPow(10.0, _Digits - 2);

   //--- indicator handles
   g_hMacd  = iMACD(_Symbol, TriggerTimeframe, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   g_hStoch = iStochastic(_Symbol, TriggerTimeframe, Stoch_K, Stoch_D, Stoch_Slowing, MODE_SMA, STO_LOWHIGH);
   if(UseHTFFilter)
      g_hEmaHTF = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   if(g_hMacd == INVALID_HANDLE || g_hStoch == INVALID_HANDLE ||
      (UseHTFFilter && g_hEmaHTF == INVALID_HANDLE))
     {
      Print("[LOMA] Failed to create indicator handles, error ", GetLastError());
      return INIT_FAILED;
     }

   //--- trade object
   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints((ulong)MathMax(0.0, MaxSlippage_Points * g_ptScale));
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.LogLevel(LOG_LEVEL_ERRORS);

   //--- hump state: rebuilt from history as soon as the indicator data is calculated
   //    (usually on the first tick; tried here too so the panel is right at once)
   ResetHumpState();
   g_lastBarTime   = 0;
   g_signalActive  = false;
   g_signalBarTime = 0;
   if(HandleReady(g_hMacd, TriggerTimeframe) && HandleReady(g_hStoch, TriggerTimeframe))
      AdvanceHumps();

   Print(StringFormat("[LOMA] Signals are computed on %s bars (TriggerTimeframe)%s. This chart is %s: "
                      "the chart timeframe does not change the signals.",
                      TFName(TriggerTimeframe),
                      UseHTFFilter ? " with the " + TFName(HTF_Timeframe) + " EMA filter" : "",
                      TFName((ENUM_TIMEFRAMES)_Period)));
   UpdatePanel();
   Log(StringFormat("Init OK on %s | digits=%d pointScale=%.2f | direction=%s | risk=%.2f%%",
                    _Symbol, _Digits, g_ptScale, EnumToString(TradeDirection), RiskPercent));
   return INIT_SUCCEEDED;
  }

//====================================================================
// OnDeinit - release handles and chart objects
//====================================================================
void OnDeinit(const int reason)
  {
   if(g_hMacd   != INVALID_HANDLE) IndicatorRelease(g_hMacd);
   if(g_hStoch  != INVALID_HANDLE) IndicatorRelease(g_hStoch);
   if(g_hEmaHTF != INVALID_HANDLE) IndicatorRelease(g_hEmaHTF);
   g_hMacd   = INVALID_HANDLE;
   g_hStoch  = INVALID_HANDLE;
   g_hEmaHTF = INVALID_HANDLE;
   ObjectsDeleteAll(0, OBJ_PREFIX);
   Comment("");
  }

//====================================================================
// OnTick
//====================================================================
void OnTick()
  {
   //--- R9: flat before the weekend (Friday from WeekendCloseTime on; leftovers on Saturday, Sunday)
   WeekendClosePositions();

   //--- R10: time exits (maximum holding time, end-of-day close); new entries are not blocked
   bool timeExitDue = TimeExitPositions();

   //--- always manage what is already open (trailing)
   ManageOpenPositions();

   //--- refresh the status panel about once a minute (spread, session)
   static datetime lastPanel = 0;
   if(TimeCurrent() - lastPanel >= 60)
     {
      lastPanel = TimeCurrent();
      UpdatePanel();
     }

   //--- bar-based signal evaluation: once per new trigger bar, on CLOSED bars
   datetime barTime = iTime(_Symbol, TriggerTimeframe, 0);
   if(timeExitDue)
      g_timeExitBar = barTime;
   if(barTime == 0)
      return;

   if(barTime != g_lastBarTime)
     {
      //--- evaluate once per bar, but only on up-to-date data; a not-ready
      //    read is retried on the next tick instead of losing the signal
      int state = EvaluateSignal(barTime);
      if(state == SIG_NOTREADY)
        {
         LogSkip("indicator data not up to date yet - retrying on next tick");
         return;
        }
      g_lastBarTime    = barTime;
      g_lastSkipReason = "";
      g_signalActive   = (state == SIG_VALID);
      g_signalBarTime  = g_signalActive ? barTime : 0;
      //--- restart / re-init inside the entry bar: never enter the same signal twice
      if(g_signalActive && EnteredSinceBar(barTime))
        {
         g_lastTradeBar = barTime;
         g_signalActive = false;
         LogSkip("this bar's signal was already traded (found in the deal history)");
        }
      if(g_signalActive)
        {
         if(MarkSignals)
            MarkSignal(g_sigClosedBar, g_sigSide);
         if(ShowLevels)
            DrawSignalRefs();
        }
      UpdatePanel();
     }

   //--- a signal is valid only during the bar right after the cross
   if(!g_signalActive || g_signalBarTime != barTime)
      return;
   if(g_lastTradeBar == barTime)
      return;
   //--- optional entry window (the reference backtest enters at the bar open)
   if(MaxEntryDelaySeconds > 0 && TimeCurrent() - barTime > MaxEntryDelaySeconds)
     {
      LogSkip("entry window after bar open has passed");
      g_signalActive = false;
      return;
     }

   //--- execution filters: decided ONCE, on the first tick of the entry bar, as in the
   //    reference backtest (a blocked signal is dropped, not retried later in the bar)
   if(CountOwnPositions() > 0)                 // max one open position
     {
      LogSkip("a position is already open (max 1)");
      g_signalActive = false;
      return;
     }
   if(g_timeExitBar == barTime)                // as in the backtest: no entry on the bar of a time exit
     {
      LogSkip("a position was open at the bar open (time exit on this bar)");
      g_signalActive = false;
      return;
     }
   if(!SpreadOK())                             // spread filter
     {
      g_signalActive = false;
      return;
     }
   if(!SessionOK())                            // trading hours (server time)
     {
      LogSkip("outside trading hours");
      g_signalActive = false;
      return;
     }
   if(PreWeekendEntryBlock())                  // R9: no new entries before the weekend
     {
      LogSkip(StringFormat("pre-weekend window (no new entries from Friday %s server time)", WeekendTimeText()));
      g_signalActive = false;
      return;
     }
   if(NewsBlocked())                           // news filter
     {
      LogSkip("high-impact news window");
      g_signalActive = false;
      return;
     }
   if(!TradingAllowed(g_sigSide))
      return;

   if(TryOpen(g_sigSide))
     {
      g_lastTradeBar = barTime;
      g_signalActive = false;
      UpdatePanel();
     }
  }

//====================================================================
// OnTrade - clean up per-ticket state of positions that are closed
//====================================================================
void OnTrade()
  {
   string prefix = OBJ_PREFIX + (string)MagicNumber + "_";
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, prefix) != 0)
         continue;
      int pos = StringFind(name, "_", StringLen(prefix));
      if(pos < 0)
         continue;
      ulong ticket = (ulong)StringToInteger(StringSubstr(name, pos + 1));
      if(ticket > 0 && !PositionSelectByTicket(ticket))
         GlobalVariableDel(name);
     }
  }

//====================================================================
// DATA READINESS
//====================================================================
//--- true when a handle has calculated every bar of its series and the
//    series is synchronized (first tick of a new bar can arrive before that)
bool HandleReady(const int handle, const ENUM_TIMEFRAMES tf)
  {
   if(handle == INVALID_HANDLE)
      return true;
   if(!SeriesInfoInteger(_Symbol, tf, SERIES_SYNCHRONIZED))
      return false;
   int bars = Bars(_Symbol, tf);
   if(bars <= MACD_Slow + MACD_Signal + 3)
      return false;
   // The non-visual Strategy Tester calculates indicators lazily: request a closed-bar value
   // first, otherwise BarsCalculated() stays behind and the EA never trades there.
   double probe[1];
   if(CopyBuffer(handle, 0, 1, 1, probe) != 1)
      return false;
   return (BarsCalculated(handle) >= bars);
  }

//--- the series of tf already holds the bar that contains barTime (not a stale bar)
bool HTFBarCurrent(const ENUM_TIMEFRAMES tf, const datetime barTime)
  {
   datetime h0 = iTime(_Symbol, tf, 0);
   if(h0 == 0 || barTime < h0)
      return false;
   if(tf == PERIOD_MN1)
     {
      MqlDateTime a, b;
      TimeToStruct(h0, a);
      TimeToStruct(barTime, b);
      return (a.year == b.year && a.mon == b.mon);
     }
   return barTime < h0 + PeriodSeconds(tf);
  }

//--- all data the signal reads is current for the trigger bar opening at barTime
bool SignalDataReady(const datetime barTime)
  {
   if(!HandleReady(g_hMacd, TriggerTimeframe) || !HandleReady(g_hStoch, TriggerTimeframe))
      return false;
   if(UseHTFFilter)
     {
      if(!HandleReady(g_hEmaHTF, HTF_Timeframe))
         return false;
      //--- the HTF series must already contain the HTF bar that holds barTime,
      //    otherwise "shift 1" would still be the HTF bar before the last closed one
      if(!HTFBarCurrent(HTF_Timeframe, barTime))
         return false;
     }
   return true;
  }

//====================================================================
// HUMP STATE MACHINE (R1-R4) - mirrors signals() in research/hump_engine.py
//====================================================================
void ResetHumpState()
  {
   g_stateReady   = false;
   g_lastProcTime = 0;
   g_prevBarTime  = 0;
   g_barIdx       = 0;
   g_cs = 0; g_cN = 0; g_cPeak = 0.0; g_cHi = -DBL_MAX; g_cLo = DBL_MAX; g_cSmin = 101.0; g_cSmax = -1.0;
   g_hasNegLo = false; g_lastNegLo = 0.0;
   g_hasPosHi = false; g_lastPosHi = 0.0;
   g_trend = 0; g_anchorPeak = 0.0; g_anchorBar = -1; g_used = 0;
   ArrayResize(g_peaks, BigHumpHistory);
   ArrayInitialize(g_peaks, 0.0);
   g_pkN = 0; g_pkI = 0;
   g_sigSide = 0; g_sigClosedBar = 0; g_sigSlRef = 0.0; g_sigTpRef = 0.0; g_sigRatio = 0.0; g_sigPbBars = 0;
  }

//--- median of the hump peaks currently in the ring (0 when fewer than 5 are known)
double RingMedian()
  {
   int n = MathMin(g_pkN, BigHumpHistory);
   if(g_pkN < 5 || n < 1)
      return 0.0;
   double tmp[];
   ArrayResize(tmp, n);
   for(int k = 0; k < n; k++)
      tmp[k] = g_peaks[k];
   ArraySort(tmp);
   if(n % 2 == 1)
      return tmp[n / 2];
   return 0.5 * (tmp[n / 2 - 1] + tmp[n / 2]);
  }

bool SideAllowed(const int side)
  {
   if(TradeDirection == DIR_BOTH)
      return true;
   return (side < 0) ? (TradeDirection == DIR_SELL_ONLY) : (TradeDirection == DIR_BUY_ONLY);
  }

//--- the trend can still produce signals on the bar with index barIdx
bool TrendAlive(const long barIdx)
  {
   return (g_trend != 0 && g_used < MaxSignalsPerBigHump && (barIdx - g_anchorBar) <= TrendMaxBars);
  }

//--- feed ONE closed bar to the state machine. side = -1 / +1 when this bar is a signal bar
//    (with the SL / TP references), else 0.
void ProcessBar(const datetime barTime, const double high, const double low, const double macd,
                const double stoch, int &side, double &slRef, double &tpRef, double &ratio, int &pbBars)
  {
   side = 0; slRef = 0.0; tpRef = 0.0; ratio = 0.0; pbBars = 0;
   long i = g_barIdx;
   g_barIdx++;
   if(macd == EMPTY_VALUE || !MathIsValidNumber(macd))
     {
      g_prevBarTime = barTime;
      return;
     }
   int s = (macd >= 0.0) ? 1 : -1;
   if(g_cs == 0)
      g_cs = s;
   if(s != g_cs)
     {
      //--- hump g_cs just completed on the previous bar; this bar starts the new hump
      double med = RingMedian();
      bool   big = (g_pkN >= 5 && g_cPeak >= BigHumpMultiplier * med && g_cN >= BigHumpMinBars);
      if(big && RequireStochLevel)
         big = (g_cs < 0) ? (g_cSmin <= StochLow) : (g_cSmax >= StochHigh);

      //--- R4: the signal check uses the trend in force BEFORE this hump is classified
      bool alive = TrendAlive(i);
      if(SkipBigPullback && big)
         alive = false;                            // big opposite hump: trend change, no signal (not counted)
      if(alive && g_trend == -1 && g_cs > 0 && s < 0 && SideAllowed(-1))
        {
         if(g_cN >= PullbackMinBars && g_cPeak <= PullbackMaxRatio * g_anchorPeak && g_hasNegLo)
           {
            side   = -1;
            slRef  = MathMax(g_cHi, high);
            tpRef  = g_lastNegLo;
            ratio  = (g_anchorPeak > 0.0) ? g_cPeak / g_anchorPeak : 0.0;
            pbBars = g_cN;
            g_used++;
           }
        }
      if(alive && g_trend == 1 && g_cs < 0 && s > 0 && SideAllowed(1))
        {
         if(g_cN >= PullbackMinBars && g_cPeak <= PullbackMaxRatio * g_anchorPeak && g_hasPosHi)
           {
            side   = 1;
            slRef  = MathMin(g_cLo, low);
            tpRef  = g_lastPosHi;
            ratio  = (g_anchorPeak > 0.0) ? g_cPeak / g_anchorPeak : 0.0;
            pbBars = g_cN;
            g_used++;
           }
        }

      //--- R1/R2: classify the completed hump
      if(big)
        {
         g_trend      = g_cs;
         g_anchorPeak = g_cPeak;
         g_anchorBar  = i - 1;
         g_used       = 0;
         if(!g_quiet)
            Log(StringFormat("Big %s hump ended %s: %d bars, peak %.3f = %.2f x median %.3f -> trend %s",
                             g_cs < 0 ? "negative" : "positive", TimeToString(g_prevBarTime, TIME_DATE | TIME_MINUTES),
                             g_cN, g_cPeak, (med > 0.0) ? g_cPeak / med : 0.0, med,
                             g_cs < 0 ? "BEARISH" : "BULLISH"));
         DrawHumpLabel(g_prevBarTime, g_cs, (g_cs < 0) ? g_cLo : g_cHi, g_cPeak, med);
        }
      else
         if(g_trend != 0 && g_cs == -g_trend && g_cPeak >= TrendBreakRatio * g_anchorPeak)
           {
            g_trend = 0;                           // trend break -> lineal
            if(!g_quiet)
               Log(StringFormat("Trend break: opposite hump peak %.3f >= %.2f x anchor %.3f -> LINEAL",
                                g_cPeak, TrendBreakRatio, g_anchorPeak));
           }

      //--- previous-hump extremes and the ring are updated AFTER the signal check
      if(g_cs < 0)
        {
         g_lastNegLo = g_cLo;
         g_hasNegLo  = true;
        }
      else
        {
         g_lastPosHi = g_cHi;
         g_hasPosHi  = true;
        }
      g_peaks[g_pkI] = g_cPeak;
      g_pkI = (g_pkI + 1) % BigHumpHistory;
      g_pkN++;

      g_cs = s; g_cN = 0; g_cPeak = 0.0; g_cHi = -DBL_MAX; g_cLo = DBL_MAX; g_cSmin = 101.0; g_cSmax = -1.0;
     }

   //--- accumulate this bar into the hump being formed
   g_cN++;
   double a = MathAbs(macd);
   if(a > g_cPeak) g_cPeak = a;
   if(high > g_cHi) g_cHi = high;
   if(low < g_cLo)  g_cLo = low;
   if(stoch != EMPTY_VALUE && MathIsValidNumber(stoch))
     {
      if(stoch < g_cSmin) g_cSmin = stoch;
      if(stoch > g_cSmax) g_cSmax = stoch;
     }

   //--- R2: a hump still forming that already breaks the trend ends it at once
   if(g_trend != 0 && g_cs == -g_trend && g_cPeak >= TrendBreakRatio * g_anchorPeak)
     {
      g_trend = 0;
      if(!g_quiet)
         Log(StringFormat("Trend break: forming opposite hump peak %.3f >= %.2f x anchor %.3f -> LINEAL",
                          g_cPeak, TrendBreakRatio, g_anchorPeak));
     }
   g_prevBarTime = barTime;
  }

//--- bring the state machine up to the last closed bar. First call (or after a history gap):
//    replay the last HumpWarmupBars closed bars. Later calls: process every bar closed since
//    the last call, in order, each exactly once. Only a signal on the most recent closed bar
//    is kept (g_sigSide). Returns false when the data could not be read (retry next tick);
//    in that case the state is left untouched.
bool AdvanceHumps()
  {
   datetime lastClosed = iTime(_Symbol, TriggerTimeframe, 1);
   if(lastClosed == 0)
      return false;
   if(g_stateReady && g_lastProcTime == lastClosed)
      return true;                                   // nothing new

   int total = Bars(_Symbol, TriggerTimeframe);
   if(total < 3)
      return false;

   bool rebuild = !g_stateReady;
   int  count   = 0;
   if(!rebuild)
     {
      int sh = iBarShift(_Symbol, TriggerTimeframe, g_lastProcTime, true);
      if(sh < 1 || sh - 1 > HumpWarmupBars)
         rebuild = true;                             // bar not found / long gap: start over
      else
         count = sh - 1;                             // closed bars at shifts sh-1 .. 1 are new
     }
   if(rebuild)
      count = MathMin(HumpWarmupBars, total - 1);
   if(count < 1)
      return !rebuild;

   //--- read everything first; the state is only touched when all three reads agree
   MqlRates rates[];
   double   macd[], stoch[];
   ArraySetAsSeries(rates, false);                   // index 0 = oldest bar
   ArraySetAsSeries(macd, false);
   ArraySetAsSeries(stoch, false);
   if(CopyRates(_Symbol, TriggerTimeframe, 1, count, rates) != count)
      return false;
   if(CopyBuffer(g_hMacd, 0, 1, count, macd) != count)
      return false;
   if(CopyBuffer(g_hStoch, 0, 1, count, stoch) != count)
      return false;
   //--- a new bar appeared while reading: the three arrays may be misaligned
   if(rates[count - 1].time != lastClosed || iTime(_Symbol, TriggerTimeframe, 1) != lastClosed)
      return false;
   if(!rebuild && rates[0].time <= g_lastProcTime)
      return false;

   int skip = 0;
   if(rebuild)
     {
      ResetHumpState();
      ObjectsDeleteAll(0, OBJ_PREFIX + "HUMP_");
      //--- replay reaches the start of the history: the first MACD values are not settled
      if(count >= total - 1)
         skip = MathMin(60, count - 1);
     }
   g_quiet = rebuild;

   int    side = 0, pbBars = 0;
   double slRef = 0.0, tpRef = 0.0, ratio = 0.0;
   for(int k = 0; k < count; k++)
     {
      double v = (k < skip) ? EMPTY_VALUE : macd[k];
      ProcessBar(rates[k].time, rates[k].high, rates[k].low, v, stoch[k], side, slRef, tpRef, ratio, pbBars);
     }
   g_quiet = false;

   //--- only the most recent closed bar can be traded
   g_sigSide      = side;
   g_sigClosedBar = lastClosed;
   g_sigSlRef     = slRef;
   g_sigTpRef     = tpRef;
   g_sigRatio     = ratio;
   g_sigPbBars    = pbBars;
   g_lastProcTime = lastClosed;
   g_stateReady   = true;

   if(rebuild)
      Print(StringFormat("[LOMA] Hump state rebuilt from %d closed %s bars (%s .. %s): %d humps, trend %s, "
                         "anchor peak %.3f, signals used %d/%d",
                         count, TFName(TriggerTimeframe), TimeToString(rates[0].time, TIME_DATE | TIME_MINUTES),
                         TimeToString(lastClosed, TIME_DATE | TIME_MINUTES), g_pkN, TrendText(),
                         g_anchorPeak, g_used, MaxSignalsPerBigHump));
   else
      if(count > 1)
         Log(StringFormat("%d bars closed since the last tick: replayed in order, only the last one can trade", count));
   return true;
  }

//====================================================================
// SIGNAL - evaluated once per new trigger bar, on closed bars only
//====================================================================
int EvaluateSignal(const datetime barTime)
  {
   if(!SignalDataReady(barTime))
      return SIG_NOTREADY;

   //--- R1-R4: feed the newly closed bar(s) to the hump state machine (each bar once)
   if(!AdvanceHumps())
      return SIG_NOTREADY;

   //--- the pending signal must belong to the bar that closed right before barTime
   if(g_sigSide == 0 || g_sigClosedBar != iTime(_Symbol, TriggerTimeframe, 1))
      return SIG_NONE;   // no signal = no trade

   //--- market gap (daily break, weekend, EA attached while the market was closed): the
   //    reference only fills a signal when the next bar opens at most one period late.
   //    The signal stays counted in g_used; only the entry is suppressed.
   if((long)(barTime - g_sigClosedBar) > 2 * (long)PeriodSeconds(TriggerTimeframe))
     {
      LogSkip(StringFormat("%s signal of %s is stale (market gap) - not traded", SideName(g_sigSide),
                           TimeToString(g_sigClosedBar, TIME_DATE | TIME_MINUTES)));
      return SIG_NONE;
     }

   //--- R7: optional higher-timeframe filter, last CLOSED HTF bar: close vs EMA.
   //    Read before the signal is logged: a not-ready read is retried on every tick
   //    and must not print the signal line again each time.
   double ema = 0.0;
   double c   = 0.0;
   if(UseHTFFilter)
     {
      if(!CopyOne(g_hEmaHTF, 0, 1, ema))
         return SIG_NOTREADY;                        // the pending signal is kept for the retry
      c = iClose(_Symbol, HTF_Timeframe, 1);
      if(c <= 0.0)
         return SIG_NOTREADY;
     }

   Log(StringFormat("%s signal on the %s bar of %s: MACD zero-cross after a %d-bar pullback hump "
                    "(peak %.2f x anchor) | SL ref %.2f | TP ref %.2f | signal %d/%d of this trend",
                    SideName(g_sigSide), TFName(TriggerTimeframe),
                    TimeToString(g_sigClosedBar, TIME_DATE | TIME_MINUTES), g_sigPbBars, g_sigRatio,
                    g_sigSlRef, g_sigTpRef, g_used, MaxSignalsPerBigHump));

   if(UseHTFFilter)
     {
      bool ok = (g_sigSide < 0) ? (c < ema) : (c > ema);
      if(!ok)
        {
         LogSkip(StringFormat("%s filter: close %.2f %s EMA(%d) %.2f -> %s not allowed", TFName(HTF_Timeframe),
                              c, (c < ema) ? "<" : ">=", HTF_EMA_Period, ema, SideName(g_sigSide)));
         return SIG_NONE;
        }
     }
   return SIG_VALID;
  }

//====================================================================
// TRADE PLAN (R5 / R6)
//====================================================================
bool BuildTradePlan(const int side, TradePlan &p, string &reason)
  {
   double bid    = Bid();
   double ask    = Ask();
   double spread = MathMax(0.0, ask - bid);
   double minD   = StopsLevelDistance();
   if(bid <= 0.0 || ask <= 0.0)
     {
      reason = "no quotes";
      return false;
     }

   p.side  = side;
   p.slRef = g_sigSlRef;
   p.tpRef = (TP_Mode == TP_PREV_HUMP) ? g_sigTpRef : 0.0;
   p.sl    = 0.0;
   p.tp    = 0.0;

   double risk   = 0.0;
   double reward = 0.0;
   if(side < 0)
     {
      //--- SELL at the bid; stopped and paid on the ask -> + spread on SL and TP
      p.entry = bid;
      p.sl    = NormalizePrice(g_sigSlRef + Pts(SL_Buffer_Points) + spread);
      risk    = p.sl - p.entry;
      if(risk <= 0.0)
        {
         reason = "SL not above the entry price";
         return false;
        }
      if(TP_Mode == TP_PREV_HUMP)
         p.tp = NormalizePrice(g_sigTpRef + TP_Anticipation * (p.entry - g_sigTpRef) + spread);
      else
         p.tp = NormalizePrice(p.entry - TP_RR * risk);
      reward = p.entry - p.tp;
      if(p.sl - ask <= minD || ask - p.tp <= minD)
        {
         reason = (reward <= 0.0) ? "previous hump low is not below the entry price" : "SL/TP inside broker stops level";
         return false;
        }
     }
   else
     {
      //--- BUY at the ask; stopped and paid on the bid (chart prices are bid) -> no spread term
      p.entry = ask;
      p.sl    = NormalizePrice(g_sigSlRef - Pts(SL_Buffer_Points));
      risk    = p.entry - p.sl;
      if(risk <= 0.0)
        {
         reason = "SL not below the entry price";
         return false;
        }
      if(TP_Mode == TP_PREV_HUMP)
         p.tp = NormalizePrice(g_sigTpRef - TP_Anticipation * (g_sigTpRef - p.entry));
      else
         p.tp = NormalizePrice(p.entry + TP_RR * risk);
      reward = p.tp - p.entry;
      if(bid - p.sl <= minD || p.tp - bid <= minD)
        {
         reason = (reward <= 0.0) ? "previous hump high is not above the entry price" : "SL/TP inside broker stops level";
         return false;
        }
     }

   //--- SL distance sanity (points are in 2-digit gold units)
   double riskPts = risk / (_Point * g_ptScale);
   if(riskPts < MinSL_Points)
     {
      reason = StringFormat("SL too tight (%.0f < %d points)", riskPts, MinSL_Points);
      return false;
     }
   if(MaxSL_Points > 0 && riskPts > MaxSL_Points)
     {
      reason = StringFormat("SL too wide (%.0f > %d points)", riskPts, MaxSL_Points);
      return false;
     }
   if(reward <= 0.0 || reward < MinRewardRisk * risk)
     {
      reason = StringFormat("reward/risk %.2f < %.2f (SL %.2f, TP %.2f)", reward / risk, MinRewardRisk, p.sl, p.tp);
      return false;
     }
   return true;
  }

//====================================================================
// RISK / LOT SIZE (R8)
//====================================================================
double CalcLots(const ENUM_ORDER_TYPE type, const double entry, const double sl)
  {
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * RiskPercent / 100.0;
   if(riskMoney <= 0.0)
      return 0.0;

   //--- money lost per 1.0 lot if SL is hit
   double lossPerLot = 0.0;
   if(!OrderCalcProfit(type, _Symbol, 1.0, entry, sl, lossPerLot) || lossPerLot == 0.0)
     {
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tickValue <= 0.0)
         tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize <= 0.0 || tickValue <= 0.0)
         return 0.0;
      lossPerLot = MathAbs(sl - entry) / tickSize * tickValue;
     }
   lossPerLot = MathAbs(lossPerLot);
   if(lossPerLot <= 0.0)
      return 0.0;

   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(MaxLotSize > 0.0)
      volMax = MathMin(volMax, MaxLotSize);
   if(volStep <= 0.0)
      volStep = 0.01;

   double lots = riskMoney / lossPerLot;
   lots = MathFloor(lots / volStep + 1e-9) * volStep;

   if(lots < volMin)
     {
      if(SkipIfBelowMinLot)
        {
         LogSkip(StringFormat("risk lot %.4f < min lot %.2f", riskMoney / lossPerLot, volMin));
         return 0.0;
        }
      lots = volMin;
     }
   lots = MathMin(lots, volMax);

   //--- margin check: shrink until it fits the free margin
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double margin     = 0.0;
   while(lots >= volMin)
     {
      if(!OrderCalcMargin(type, _Symbol, lots, entry, margin))
        {
         LogSkip(StringFormat("OrderCalcMargin failed (error %d) - trade skipped", GetLastError()));
         return 0.0;   // never send a lot size whose margin could not be checked
        }
      if(margin <= freeMargin * 0.95)
         break;
      lots -= volStep;
     }
   if(lots < volMin)
     {
      LogSkip("not enough free margin");
      return 0.0;
     }

   int volDigits = (int)MathMax(0, MathCeil(-MathLog10(volStep)));
   return NormalizeDouble(lots, volDigits);
  }

//====================================================================
// EXECUTION
//====================================================================
bool IsTransientRetcode(const uint rc)
  {
   return (rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED ||
           rc == TRADE_RETCODE_PRICE_OFF || rc == TRADE_RETCODE_TIMEOUT ||
           rc == TRADE_RETCODE_CONNECTION || rc == TRADE_RETCODE_TOO_MANY_REQUESTS);
  }

bool TryOpen(const int side)
  {
   const int maxAttempts = 3;
   ENUM_ORDER_TYPE type = (side < 0) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   for(int attempt = 1; attempt <= maxAttempts; attempt++)
     {
      //--- R5: SL / TP from the hump references (rebuilt each attempt with fresh prices)
      TradePlan plan;
      string    reason = "";
      if(!BuildTradePlan(side, plan, reason))
        {
         LogSkip(reason);
         g_signalActive = false;   // decided once per signal, as in the backtest
         return false;
        }

      //--- R8: position size from the SL distance
      double lots = CalcLots(type, plan.entry, plan.sl);
      if(lots <= 0.0)
        {
         g_signalActive = false;
         return false;
        }

      double risk = MathAbs(plan.entry - plan.sl);
      Log(StringFormat("%s %.2f @%.2f SL=%.2f (hump %s %.2f) TP=%.2f (%s) RR=%.2f",
                       SideName(side), lots, plan.entry, plan.sl, side < 0 ? "high" : "low", plan.slRef, plan.tp,
                       (TP_Mode == TP_PREV_HUMP) ? StringFormat("previous hump %s %.2f", side < 0 ? "low" : "high", plan.tpRef)
                                                 : StringFormat("fixed %.1fR", TP_RR),
                       MathAbs(plan.entry - plan.tp) / MathMax(_Point, risk)));

      ResetLastError();
      bool sent = (side < 0) ? g_trade.Sell(lots, _Symbol, 0.0, plan.sl, plan.tp, TradeComment)
                             : g_trade.Buy(lots, _Symbol, 0.0, plan.sl, plan.tp, TradeComment);
      uint rc   = g_trade.ResultRetcode();
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         Log(StringFormat("Order filled: deal #%I64u price %.2f", g_trade.ResultDeal(), g_trade.ResultPrice()));
         if(ShowLevels)
            DrawPlan(plan);
         return true;
        }

      Print(StringFormat("[LOMA] OrderSend failed (attempt %d/%d): retcode=%u (%s) lastError=%d",
                         attempt, maxAttempts, rc, g_trade.ResultRetcodeDescription(), GetLastError()));
      if(!IsTransientRetcode(rc))
        {
         g_signalActive = false;   // hard error: drop this signal
         return false;
        }
      //--- transient error (timeout, requote, connection): the order may still
      //    have been executed. Pause, then check before sending again.
      Sleep(300);
      if(CountOwnPositions() > 0)
        {
         Log("Position found after a transient OrderSend error - treating as filled");
         return true;
        }
     }
   g_signalActive = false;   // no repeated bursts on later ticks
   return false;
  }

//--- true when this EA (magic + symbol) already opened a position at or after 'fromTime'
bool EnteredSinceBar(const datetime fromTime)
  {
   if(!HistorySelect(fromTime, TimeCurrent() + 86400))
      return false;
   for(int k = HistoryDealsTotal() - 1; k >= 0; k--)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol ||
         (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber)
         continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN &&
         (datetime)HistoryDealGetInteger(d, DEAL_TIME) >= fromTime)
         return true;
     }
   return false;
  }

int CountOwnPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(g_pos.SelectByIndex(i) && g_pos.Symbol() == _Symbol && (ulong)g_pos.Magic() == MagicNumber)
         n++;
   return n;
  }

//====================================================================
// FILTERS (spread, session, news)
//====================================================================
bool SpreadOK()
  {
   double spreadPts = (Ask() - Bid()) / (_Point * g_ptScale);
   if(spreadPts > MaxSpread_Points)
     {
      LogSkip(StringFormat("spread %.0f > %d points", spreadPts, MaxSpread_Points));
      return false;
     }
   return true;
  }

//--- trading hours in broker server time
bool SessionOK()
  {
   if(!UseTradingHours)
      return true;
   MqlDateTime dt;
   TimeToStruct(TimeTradeServer(), dt);
   int m = dt.hour * 60 + dt.min;
   if(g_sessStartMin <= g_sessEndMin)
      return (m >= g_sessStartMin && m < g_sessEndMin);
   return (m >= g_sessStartMin || m < g_sessEndMin);   // window crosses midnight
  }

//--- "hh:mm" of the parsed WeekendCloseTime
string WeekendTimeText()
  {
   return StringFormat("%02d:%02d", g_weekendMin / 60, g_weekendMin % 60);
  }

//--- R9 entry filter: Friday at or after WeekendCloseTime only (broker server time)
bool PreWeekendEntryBlock()
  {
   if(!CloseBeforeWeekend)
      return false;
   MqlDateTime dt;
   TimeToStruct(TimeTradeServer(), dt);
   return (dt.day_of_week == 5 && dt.hour * 60 + dt.min >= g_weekendMin);
  }

//--- R9 close window: Friday at or after WeekendCloseTime, Saturday or Sunday (broker server time)
bool InWeekendWindow()
  {
   if(!CloseBeforeWeekend)
      return false;
   MqlDateTime dt;
   TimeToStruct(TimeTradeServer(), dt);
   if(dt.day_of_week == 6 || dt.day_of_week == 0)
      return true;
   return (dt.day_of_week == 5 && dt.hour * 60 + dt.min >= g_weekendMin);
  }

bool NewsBlocked()
  {
   if(!UseNewsFilter)
      return false;
   if(MQLInfoInteger(MQL_TESTER))
     {
      if(!g_newsWarned)
        {
         Print("[LOMA] News filter: economic calendar unavailable in tester -> bypassed.");
         g_newsWarned = true;
        }
      return false;
     }

   datetime now = TimeTradeServer();
   if(now - g_newsCheckTime < 60)      // refresh at most once per minute
      return g_newsBlocked;
   g_newsCheckTime = now;
   g_newsBlocked   = false;

   int win = NewsWindowMinutes * 60;
   MqlCalendarValue vals[];
   ResetLastError();
   if(!CalendarValueHistory(vals, now - win, now + win, NULL, NewsCurrency))
     {
      int err = GetLastError();
      if(err != 0 && !g_newsWarned)
        {
         Print("[LOMA] News filter: calendar query failed, error ", err, " (trading allowed)");
         g_newsWarned = true;
        }
      return false;
     }
   for(int i = 0; i < ArraySize(vals); i++)
     {
      MqlCalendarEvent ev;
      if(!CalendarEventById(vals[i].event_id, ev))
         continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH)
         continue;
      if(MathAbs((long)(vals[i].time - now)) <= win)
        {
         g_newsBlocked = true;
         Log("News filter: " + ev.name + " at " + TimeToString(vals[i].time));
         break;
        }
     }
   return g_newsBlocked;
  }

bool TradingAllowed(const int side)
  {
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      LogSkip("algo trading disabled in terminal/EA settings");
      return false;
     }
   long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(side < 0 && mode != SYMBOL_TRADE_MODE_FULL && mode != SYMBOL_TRADE_MODE_SHORTONLY)
     {
      LogSkip("symbol does not allow opening shorts");
      return false;
     }
   if(side > 0 && mode != SYMBOL_TRADE_MODE_FULL && mode != SYMBOL_TRADE_MODE_LONGONLY)
     {
      LogSkip("symbol does not allow opening longs");
      return false;
     }
   return true;
  }

//====================================================================
// POSITION MANAGEMENT (R8: trailing in R multiples)
//====================================================================
void ManageOpenPositions()
  {
   if(TrailStartR <= 0.0)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i))
         continue;
      if(g_pos.Symbol() != _Symbol || (ulong)g_pos.Magic() != MagicNumber)
         continue;

      ulong  ticket = g_pos.Ticket();
      double open   = g_pos.PriceOpen();
      double sl     = g_pos.StopLoss();
      double tp     = g_pos.TakeProfit();
      bool   isSell = (g_pos.PositionType() == POSITION_TYPE_SELL);
      double minD   = StopsLevelDistance();
      double step   = Pts(TrailStep_Points);

      //--- remember the initial risk (1R) the first time we see the position
      string rKey = GVKey("R", ticket);
      if(!GlobalVariableCheck(rKey) && sl > 0.0 && MathAbs(sl - open) > 0.0)
         GlobalVariableSet(rKey, MathAbs(sl - open));
      double initRisk = GlobalVariableCheck(rKey) ? GlobalVariableGet(rKey) : 0.0;
      if(initRisk <= 0.0)
         continue;

      if(isSell)
        {
         double ask = Ask();
         if(open - ask < TrailStartR * initRisk)
            continue;
         double newSL = NormalizePrice(ask + TrailDistanceR * initRisk);
         if((sl == 0.0 || newSL <= sl - step) && newSL - ask > minD)
           {
            if(g_trade.PositionModify(ticket, newSL, tp))
               Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
            else
               Print("[LOMA] Trailing modify failed: ", g_trade.ResultRetcodeDescription());
           }
        }
      else
        {
         double bid = Bid();
         if(bid - open < TrailStartR * initRisk)
            continue;
         double newSL = NormalizePrice(bid - TrailDistanceR * initRisk);
         if((sl == 0.0 || newSL >= sl + step) && bid - newSL > minD)
           {
            if(g_trade.PositionModify(ticket, newSL, tp))
               Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
            else
               Print("[LOMA] Trailing modify failed: ", g_trade.ResultRetcodeDescription());
           }
        }
     }
  }

//--- R9: close this EA's position at market inside the weekend window. A failed close is
//    retried at most once every WEEKEND_RETRY_SEC seconds; the journal gets one line per window.
//    On Saturday/Sunday a position opened on that same day is left alone (Sunday-open brokers).
void WeekendClosePositions()
  {
   if(!CloseBeforeWeekend)
      return;
   if(!InWeekendWindow())
     {
      g_weekendLogged  = false;
      g_weekendFailLog = false;
      g_weekendLastTry = 0;
      return;
     }
   datetime now = TimeTradeServer();
   if(g_weekendLastTry > 0 && now >= g_weekendLastTry && now - g_weekendLastTry < WEEKEND_RETRY_SEC)
      return;                                  // throttle retries after a failed close
   MqlDateTime wdt;
   TimeToStruct(now, wdt);
   bool     onWeekendDay = (wdt.day_of_week == 6 || wdt.day_of_week == 0);
   datetime dayStart     = now - (now % 86400);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i))
         continue;
      if(g_pos.Symbol() != _Symbol || (ulong)g_pos.Magic() != MagicNumber)
         continue;

      if(onWeekendDay && g_pos.Time() >= dayStart)
         continue;                             // opened today (Sunday session): not a leftover

      ulong ticket = g_pos.Ticket();
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
        {
         if(!g_weekendFailLog)
           {
            g_weekendFailLog = true;
            Print(StringFormat("[LOMA] Weekend close of #%I64u not sent: algo trading disabled in terminal/EA settings - retrying once it is enabled",
                               ticket));
           }
         g_weekendLastTry = now;
         return;
        }
      if(!g_weekendLogged)
        {
         g_weekendLogged = true;
         Log(StringFormat("Weekend close: closing position #%I64u at market (Friday %s server time or later)",
                          ticket, WeekendTimeText()));
        }
      ResetLastError();
      bool sent = g_trade.PositionClose(ticket);
      uint rc   = g_trade.ResultRetcode();
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
         continue;
      g_weekendLastTry = now;
      if(!g_weekendFailLog)
        {
         g_weekendFailLog = true;
         Print(StringFormat("[LOMA] Weekend close of #%I64u failed: retcode=%u (%s) lastError=%d - retrying every few seconds",
                            ticket, rc, g_trade.ResultRetcodeDescription(), GetLastError()));
        }
     }
  }

//--- "hh:mm" of the parsed EndOfDayTime
string EndOfDayTimeText()
  {
   return StringFormat("%02d:%02d", g_eodMin / 60, g_eodMin % 60);
  }

//--- true when the position has been open MaxHoldMinutes: M1 bars after the entry bar, as in
//    the reference backtest; clock minutes when the M1 history is not available
bool MaxHoldReached(const datetime opened, const datetime now)
  {
   if((long)(now - opened) < (long)MaxHoldMinutes * 60)
      return false;                            // bars after the entry bar <= clock minutes
   int bars = Bars(_Symbol, PERIOD_M1, opened - (opened % 60), now);   // entry bar included
   if(bars <= 0)
      return true;
   return (bars - 1 >= MaxHoldMinutes);
  }

//--- true when an EndOfDayTime crossing on a day before today was missed: the market traded
//    at or after EndOfDayTime on a day on which the position was already open before that time
bool EodCrossingMissed(const datetime opened, const datetime now)
  {
   datetime first = opened - (opened % 86400) + (datetime)(g_eodMin * 60);
   if(opened >= first)
      first += 86400;                          // opened after that day's EndOfDayTime
   datetime d = now - (now % 86400) - 86400 + (datetime)(g_eodMin * 60);   // yesterday's EndOfDayTime
   for(int k = 0; k < 7 && d >= first; k++, d -= 86400)
      if(Bars(_Symbol, PERIOD_M1, d, d - (d % 86400) + 86399) > 0)
         return true;
   return false;
  }

//--- R10: close this EA's position at market when it has been open MaxHoldMinutes, or when the
//    server time of day is at or after EndOfDayTime and it was opened before today's
//    EndOfDayTime (or an earlier day's crossing was missed). A failed close is retried at most
//    once every WEEKEND_RETRY_SEC seconds; the journal gets one line per position.
//    Returns true when a position was due for a time exit on this tick (closed or attempted).
bool TimeExitPositions()
  {
   if(MaxHoldMinutes <= 0 && !CloseAtEndOfDay)
      return false;
   datetime now = TimeCurrent();
   if(g_timeExitLastTry > 0 && now >= g_timeExitLastTry && now - g_timeExitLastTry < WEEKEND_RETRY_SEC)
      return false;                            // throttle retries after a failed close
   bool due = false;
   datetime eodMoment = now - (now % 86400) + (datetime)(g_eodMin * 60);   // today's EndOfDayTime
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i))
         continue;
      if(g_pos.Symbol() != _Symbol || (ulong)g_pos.Magic() != MagicNumber)
         continue;

      datetime opened = g_pos.Time();
      string   why    = "";
      if(MaxHoldMinutes > 0 && MaxHoldReached(opened, now))
         why = StringFormat("open for %d minutes or more (MaxHoldMinutes)", MaxHoldMinutes);
      else if(CloseAtEndOfDay && now >= eodMoment && opened < eodMoment)
         why = StringFormat("end of day (%s server time or later)", EndOfDayTimeText());
      else if(CloseAtEndOfDay && EodCrossingMissed(opened, now))
         why = StringFormat("end of day (%s server time) of an earlier day was missed", EndOfDayTimeText());
      if(why == "")
         continue;
      due = true;

      ulong ticket = g_pos.Ticket();
      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
        {
         if(g_timeExitFailLog != ticket)
           {
            g_timeExitFailLog = ticket;
            Print(StringFormat("[LOMA] Time exit of #%I64u not sent: algo trading disabled in terminal/EA settings - retrying once it is enabled",
                               ticket));
           }
         g_timeExitLastTry = now;
         return true;
        }
      if(g_timeExitLogged != ticket)
        {
         g_timeExitLogged = ticket;
         Log(StringFormat("Time exit: closing position #%I64u at market, %s", ticket, why));
        }
      ResetLastError();
      bool sent = g_trade.PositionClose(ticket);
      uint rc   = g_trade.ResultRetcode();
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         g_timeExitLastTry = 0;
         continue;
        }
      g_timeExitLastTry = now;
      if(g_timeExitFailLog != ticket)
        {
         g_timeExitFailLog = ticket;
         Print(StringFormat("[LOMA] Time exit of #%I64u failed: retcode=%u (%s) lastError=%d - retrying every few seconds",
                            ticket, rc, g_trade.ResultRetcodeDescription(), GetLastError()));
        }
     }
   return due;
  }

//====================================================================
// VISUALS
//====================================================================
void DrawLevel(const string name, const double price, const color clr, const ENUM_LINE_STYLE style,
               const string text)
  {
   if(VisualsOff())
      return;
   string n = OBJ_PREFIX + name;
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, n, OBJPROP_PRICE, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, n, OBJPROP_STYLE, style);
   ObjectSetString(0, n, OBJPROP_TEXT, text);
   ObjectSetString(0, n, OBJPROP_TOOLTIP, text);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
  }

//--- reference lines of the last signal: pullback hump extreme (SL side) and previous hump
//    extreme (TP side)
void DrawSignalRefs()
  {
   if(g_sigSide == 0)
      return;
   DrawLevel("SLref", g_sigSlRef, clrRed, STYLE_DASH,
             StringFormat("LOMA %s: pullback hump %s (SL reference)", SideName(g_sigSide), g_sigSide < 0 ? "high" : "low"));
   DrawLevel("TPref", g_sigTpRef, clrRoyalBlue, STYLE_DASH,
             StringFormat("LOMA %s: previous hump %s (TP reference)", SideName(g_sigSide), g_sigSide < 0 ? "low" : "high"));
  }

//--- final SL / TP of the trade that was opened
void DrawPlan(const TradePlan &p)
  {
   DrawLevel("SL", p.sl, clrTomato, STYLE_DOT, "LOMA " + SideName(p.side) + " SL");
   DrawLevel("TP", p.tp, clrDodgerBlue, STYLE_DOT, "LOMA " + SideName(p.side) + " TP");
  }

//--- label on a big hump: at its last bar, below the low (negative) / above the high (positive)
void DrawHumpLabel(const datetime t, const int sign, const double price, const double peak, const double med)
  {
   if(!ShowHumpLabels || VisualsOff() || t == 0)
      return;
   string n = OBJ_PREFIX + "HUMP_" + (string)(long)t;
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, n, OBJPROP_TIME, 0, t);
   ObjectSetDouble(0, n, OBJPROP_PRICE, 0, price);
   ObjectSetString(0, n, OBJPROP_TEXT,
                   StringFormat("%s %.2f (x%.1f)", sign < 0 ? "BIG-" : "BIG+", peak, (med > 0.0) ? peak / med : 0.0));
   ObjectSetInteger(0, n, OBJPROP_COLOR, sign < 0 ? clrTomato : clrDodgerBlue);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, sign < 0 ? ANCHOR_UPPER : ANCHOR_LOWER);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetString(0, n, OBJPROP_TOOLTIP,
                   StringFormat("Big %s MACD hump: peak %.3f, median %.3f -> %s trend",
                                sign < 0 ? "negative" : "positive", peak, med, sign < 0 ? "BEARISH" : "BULLISH"));
  }

//--- arrow at the trigger bar that produced the signal
void MarkSignal(const datetime closedBarTime, const int side)
  {
   if(VisualsOff() || side == 0)
      return;
   string n = OBJ_PREFIX + "SIG_" + (string)(long)closedBarTime;
   int    sh = iBarShift(_Symbol, TriggerTimeframe, closedBarTime, false);
   if(sh < 0)
      sh = 1;
   double price = (side < 0) ? iHigh(_Symbol, TriggerTimeframe, sh) : iLow(_Symbol, TriggerTimeframe, sh);
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, (side < 0) ? OBJ_ARROW_SELL : OBJ_ARROW_BUY, 0, closedBarTime, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, (side < 0) ? clrTomato : clrDodgerBlue);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetString(0, n, OBJPROP_TOOLTIP,
                   StringFormat("LOMA %s signal: MACD(%s) crossed %s zero after a pullback hump, bar of %s",
                                SideName(side), TFName(TriggerTimeframe), side < 0 ? "below" : "above",
                                TimeToString(closedBarTime, TIME_DATE | TIME_MINUTES)));
  }

//--- closed trades of this EA (magic + symbol): positions fully closed, positions won
void WinStats(int &closed, int &wins)
  {
   closed = 0; wins = 0;
   if(!HistorySelect(0, TimeCurrent() + 1))
      return;
   long   ids[];
   double pnl[];
   bool   hasExit[];
   int    n = 0;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol ||
         (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber)
         continue;
      long dt = HistoryDealGetInteger(d, DEAL_TYPE);
      if(dt != DEAL_TYPE_BUY && dt != DEAL_TYPE_SELL)
         continue;
      long et = HistoryDealGetInteger(d, DEAL_ENTRY);
      long id = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      double v = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) +
                 HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_FEE);
      int idx = -1;
      for(int q = n - 1; q >= 0; q--)
         if(ids[q] == id)
           {
            idx = q;
            break;
           }
      if(idx < 0)
        {
         idx = n++;
         ArrayResize(ids, n);
         ArrayResize(pnl, n);
         ArrayResize(hasExit, n);
         ids[idx] = id; pnl[idx] = 0.0; hasExit[idx] = false;
        }
      pnl[idx] += v;
      if(et == DEAL_ENTRY_OUT || et == DEAL_ENTRY_OUT_BY || et == DEAL_ENTRY_INOUT)
         hasExit[idx] = true;
     }
   for(int j = 0; j < n; j++)
     {
      if(!hasExit[j] || PositionSelectByTicket((ulong)ids[j]))
         continue;                                   // never closed, or partly closed and still open
      closed++;
      if(pnl[j] > 0.0)
         wins++;
     }
  }

//--- BEARISH / BULLISH / LINEAL, with the reason when a trend is in force but can no longer trade
string TrendText()
  {
   if(!g_stateReady && g_pkN == 0 && g_cs == 0)
      return "not ready";
   if(g_trend == 0)
      return "LINEAL (no trades)";
   string name = (g_trend < 0) ? "BEARISH" : "BULLISH";
   if(g_used >= MaxSignalsPerBigHump)
      return "LINEAL (" + name + " trend lapsed: all signals used)";
   if(g_barIdx - g_anchorBar > TrendMaxBars)
      return "LINEAL (" + name + " trend lapsed: too old)";
   return name;
  }

//--- status panel
void UpdatePanel()
  {
   if(!ShowStatusPanel || VisualsOff())
      return;
   string build = "Loma TrendPullback v1.33";

   string anchorTxt = "none";
   if(g_trend != 0)
      anchorTxt = StringFormat("%.3f  |  bars since anchor: %d / %d", g_anchorPeak,
                               (int)(g_barIdx - g_anchorBar), TrendMaxBars);
   double med = RingMedian();
   string humpTxt = "none yet";
   if(g_cs != 0)
     {
      humpTxt = StringFormat("%s, %d bars, peak %.3f", g_cs > 0 ? "POSITIVE" : "NEGATIVE", g_cN, g_cPeak);
      if(g_trend != 0 && g_anchorPeak > 0.0)
         humpTxt += StringFormat(" (%.2f x anchor)", g_cPeak / g_anchorPeak);
     }
   string medTxt = (g_pkN >= 5) ? StringFormat("%.3f -> big hump >= %.3f", med, BigHumpMultiplier * med)
                                : StringFormat("needs 5 humps (%d known)", g_pkN);
   string prevTxt = StringFormat("low %s  |  high %s",
                                 g_hasNegLo ? DoubleToString(g_lastNegLo, _Digits) : "n/a",
                                 g_hasPosHi ? DoubleToString(g_lastPosHi, _Digits) : "n/a");
   string sessTxt = UseTradingHours ? StringFormat("%s-%s server time: %s", TradingHoursStart, TradingHoursEnd,
                                                   SessionOK() ? "open" : "closed")
                                    : "all day";
   if(CloseBeforeWeekend)
      sessTxt += "  |  weekend close ON " + WeekendTimeText();
   if(MaxHoldMinutes > 0)
      sessTxt += StringFormat("  |  max hold %d min", MaxHoldMinutes);
   if(CloseAtEndOfDay)
      sessTxt += "  |  EOD close " + EndOfDayTimeText();
   string htfTxt  = UseHTFFilter ? TFName(HTF_Timeframe) + StringFormat(" EMA(%d)", HTF_EMA_Period) : "off";
   string sigTxt  = g_signalActive ? "ACTIVE " + SideName(g_sigSide) : "none";
   double spreadPts = (Ask() - Bid()) / (_Point * g_ptScale);
   int closedN = 0, winsN = 0;
   WinStats(closedN, winsN);
   string winTxt = (closedN > 0) ? StringFormat("%d of %d closed trades won (%.0f%%)", winsN, closedN,
                                                100.0 * winsN / closedN) : "no closed trades yet";

   Comment(StringFormat("%s | %s | chart %s\n"
                        "Signals on: %s bars   |   HTF filter: %s   |   Direction: %s\n"
                        "Trend: %s\n"
                        "Anchor hump peak: %s\n"
                        "Signals used: %d / %d\n"
                        "Current hump: %s\n"
                        "Median hump peak: %s\n"
                        "Previous humps: %s\n"
                        "Session %s   |   Spread %.0f / %d pts\n"
                        "Signal: %s   |   Positions: %d\n"
                        "Last skip: %s\n"
                        "Results: %s",
                        build, _Symbol, TFName((ENUM_TIMEFRAMES)_Period),
                        TFName(TriggerTimeframe), htfTxt, EnumToString(TradeDirection),
                        TrendText(),
                        anchorTxt,
                        g_used, MaxSignalsPerBigHump,
                        humpTxt,
                        medTxt,
                        prevTxt,
                        sessTxt, spreadPts, MaxSpread_Points,
                        sigTxt, CountOwnPositions(),
                        g_panelSkip,
                        winTxt));
  }
//+------------------------------------------------------------------+
