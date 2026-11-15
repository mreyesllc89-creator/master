//+------------------------------------------------------------------+
//|                                  XAUUSD_Loma_TrendPullback.mq5   |
//|                                                                  |
//|  Strategy : XAUUSD "Loma" (MACD hump) Trend Pullback, both sides |
//|  Version  : 1.35                                                 |
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
//        a previous negative hump low exists. The pullback must last PullbackMinBars bars: with
//        1, a single bar across zero counts as a pullback hump.
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
//    R5b Optional price scaling (ScaleWithPrice, v1.35): SL_Buffer_Points, MinSL_Points and
//        MaxSL_Points are multiplied by bid / ReferencePrice each time a trade plan is built, so
//        that a preset calibrated at ReferencePrice keeps the same proportions at another price
//        level (reference: the price scale in research/hump_wf.py outcomes()). The level-based
//        trailing uses the buffer scaled by the position's open price / ReferencePrice. Spread
//        and slippage limits are not scaled.
//    R7  Optional higher-timeframe filter: sell only if the last closed HTF bar closed below
//        its EMA(50), buy only if above.
//    R7b Optional Stochastic turn filter (UseStochTurnFilter, v1.35), with its own
//        Stochastic(7,1,7) on TriggerTimeframe: a sell is taken only when the main line was
//        >= StochTurnHigh on one of the last StochTurnBars closed bars (signal bar included) and
//        on the signal bar it is below its signal line or below StochTurnHigh; a buy is the
//        mirror with StochTurnLow. Applied where the R7 filter is: the signal still counts
//        against MaxSignalsPerBigHump, only the entry is skipped (research/hump_wf.py xlzc_stoch).
//    R8  Risk: RiskPercent of equity per trade, lot from the SL distance, ONE position at a
//        time (magic number), spread filter, trading hours (broker server time), news filter,
//        optional trailing in R multiples (TrailStartR / TrailDistanceR).
//    R8b Trailing systems (TrailMode, v1.35); the units of TrailStartR / TrailDistanceR and the
//        meaning of TrailParam depend on the system (see ENUM_LOMA_TRAIL_MODE). TRAIL_RISK is the
//        trailing of R8, on every tick. TRAIL_STEP also works on every tick: once the best profit
//        has reached k x TrailStartR x 1R the stop is at entry + (k - 1) x TrailStartR x 1R. All
//        other systems act once per closed one-minute bar, on the first tick of the next M1 bar:
//        from the best price of the completed M1 bars since the entry (bid highs for a buy, bid
//        lows + spread for a sell) and, for TRAIL_CHANDELIER and the level systems (candles, EMA,
//        SMA, Parabolic SAR, Bollinger band, higher candle, swings, MACD hump), from the last
//        closed TriggerTimeframe bar. A level stop is the level -/+ SL_Buffer_Points (+ the
//        spread for a sell). The stop is only ever tightened and the take profit never changed;
//        when the price is already through the new stop the position is closed at market, as
//        the reference backtest fills at that minute's open (research/hump_trail.py and
//        hump_trail2.py simulate_y with closed = 1).
//    R9  Optional weekend flat (CloseBeforeWeekend): on Friday from WeekendCloseTime (broker
//        server time) on, no new entries are taken and the open position is closed at market
//        on the first tick. Any position opened on or before that Friday that is still open
//        later (EA or algo trading off on Friday evening, or the broker's Friday session ended
//        before WeekendCloseTime) is closed on the first tick available, on any day. Positions
//        opened after that Friday are left alone: entries are blocked on Friday only, so on a
//        broker whose week opens on Sunday (server time) the Sunday session trades normally.
//        A failed close is retried at most once every WEEKEND_RETRY_SEC seconds, and not at
//        all while algo trading is off.
//    R10 Optional time exits; neither blocks new entries (only the signal of the trigger bar
//        on which the time exit happens is not traded, as in the reference backtest):
//        MaxHoldMinutes > 0: the position is closed at market once it has been open that many
//        minutes, counted in M1 bars after the entry bar as in the reference backtest (minutes
//        without quotes - daily break, weekend - do not count). While the M1 history is not
//        available yet the check is repeated; clock time decides 4 hours past the limit.
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
//    24 hours or more (holidays). The EA closes on the first tick of the window (or on the first
//    tick after it, if that close was missed) and cannot foresee a holiday closure.
//  * Time exits: the reference backtest (max_hold / eod) closes at the close of the M1 bar that
//    reaches the holding limit or crosses the end-of-day time; the EA closes on the first tick
//    of that M1 bar, about one minute earlier.
//  * Trailing systems (R8b): nothing is kept in memory only. The best price is read from the M1
//    history on every evaluation, the initial risk and the ATR at entry are terminal global
//    variables. The M1 bar in which the position was opened counts as a whole, as in the
//    reference backtest (which enters at that bar's open). A new stop is rounded to the tick on
//    the looser side (down for a buy, up for a sell): it is then hit exactly when the unrounded
//    stop of the backtest is. A stop that is closer to the price than the broker's stops level is
//    not placed in that minute. Levels of minutes in which the EA was not running are not
//    applied afterwards.
//+------------------------------------------------------------------+
#property copyright   "mreyesllc89"
#property version     "1.35"
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

enum ENUM_LOMA_TRAIL_MODE
  {
   TRAIL_RISK        = 0,  // RISK: start / distance in R, every tick (TrailStartR 0 = off)
   TRAIL_ATR_ENTRY   = 1,  // ATR_ENTRY: start / distance in ATR(14) of the signal bar
   TRAIL_PERCENT     = 2,  // PERCENT: start / distance in % of the entry price
   TRAIL_PROFIT_LOCK = 3,  // PROFIT_LOCK: from TrailStartR (R) keep the share TrailDistanceR of the best profit
   TRAIL_STEP        = 4,  // STEP: ratchet in steps of TrailStartR (R), every tick
   TRAIL_CHANDELIER  = 5,  // CHANDELIER: best price -/+ TrailDistanceR x live ATR(14)
   TRAIL_CANDLES     = 6,  // CANDLES: low / high of the last TrailParam closed candles
   TRAIL_EMA         = 7,  // EMA: EMA(TrailParam) of the closes
   TRAIL_SMA         = 8,  // SMA: SMA(TrailParam) of the closes
   TRAIL_PSAR        = 9,  // PSAR: Parabolic SAR, TrailParam 0 = 0.02/0.2, 1 = 0.01/0.1, 2 = 0.04/0.2
   TRAIL_BOLLINGER   = 10, // BOLLINGER: SMA(20) -/+ 1 sd (TrailParam 0) or 2 sd (TrailParam 1)
   TRAIL_HTF_CANDLE  = 11, // HTF_CANDLE: low / high of the last closed candle of TrailParam minutes
   TRAIL_PIVOTS      = 12, // PIVOTS: last confirmed swing with TrailParam bars on each side
   TRAIL_HUMP        = 13  // HUMP: low / high of the last completed MACD hump
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
input bool    ScaleWithPrice           = false; // Multiply the *_Points distances by price / ReferencePrice
input double  ReferencePrice           = 0.0;   // Price at which the *_Points values were calibrated

input group "=== R7: Higher-timeframe filter ==="
input bool            UseHTFFilter     = false;      // Sell only below / buy only above the HTF EMA
input ENUM_TIMEFRAMES HTF_Timeframe    = PERIOD_H4;  // Higher timeframe
input int             HTF_EMA_Period   = 50;         // HTF EMA period

input group "=== R7b: Stochastic turn filter ==="
input bool    UseStochTurnFilter       = false; // Entry only when the Stochastic came from the extreme and turned
input int     StochTurnBars            = 5;     // ... within this many closed bars, the signal bar included
input double  StochTurnHigh            = 80.0;  // Sells: Stochastic was at or above this
input double  StochTurnLow             = 20.0;  // Buys: Stochastic was at or below this

input group "=== R8: Risk & Position ==="
input double  RiskPercent              = 0.75;  // Risk per trade, % of equity
input double  MaxLotSize               = 0.0;   // Max lot (0 = broker max)
input bool    SkipIfBelowMinLot        = true;  // Skip trade if risk lot < broker min lot
input double  CommissionPerLot         = 0.0;   // Round-trip commission per 1.0 lot, account currency (counted in the risk, sign ignored, 0 = off)
input int     MaxSpread_Points         = 60;    // Max spread (points)
input int     MaxSlippage_Points       = 20;    // Max slippage (points)
input int     MaxEntryDelaySeconds     = 0;     // Enter only within N s of bar open (0 = no limit, first tick)

input group "=== R8: Trailing stop (R multiples) ==="
input double  TrailStartR              = 0.0;   // Start trailing at this profit in R (0 = off)
input double  TrailDistanceR           = 0.5;   // Trailing distance in R
input int     TrailStep_Points         = 10;    // Min SL improvement per modification (points)
input ENUM_LOMA_TRAIL_MODE TrailMode = TRAIL_RISK;  // Trailing system (units of TrailStartR / TrailDistanceR depend on it)
input int     TrailParam               = 0;     // Period, bars or variant of the level-based systems

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
int      g_hStochTurn = INVALID_HANDLE;  // Stochastic(7,1,7) of the turn filter on the trigger timeframe (optional)

double   g_ptScale        = 1.0;   // point scale factor (AutoScalePoints)
int      g_sessStartMin   = 0;
int      g_sessEndMin     = 0;
int      g_weekendMin     = 0;     // WeekendCloseTime in minutes from midnight
bool     g_weekendLogged  = false; // weekend close announced (once per close episode)
bool     g_weekendFailLog = false; // failed weekend close reported (once per close episode)
datetime g_weekendLastTry = 0;     // server time of the last failed weekend close (retry throttle)
// minimum seconds between weekend close retries (also used by the R10 time exits and the trailing pause)
#define  WEEKEND_RETRY_SEC 5
int      g_eodMin         = 0;     // EndOfDayTime in minutes from midnight
ulong    g_timeExitLogged  = 0;    // ticket whose time exit was announced (once per position)
ulong    g_timeExitFailLog = 0;    // ticket whose failed time exit was reported (once per position)
datetime g_timeExitLastTry = 0;    // server time of the last failed time exit (retry throttle)
datetime g_timeExitBar     = 0;    // trigger bar on which a time exit was last due (its signal is not traded)
datetime g_trailLastFail   = 0;    // server time of the last failed trailing modification (retry throttle)
uint     g_trailFailCode   = 0;    // retcode of the last reported trailing failure (one journal line per new retcode)
//--- trailing systems of v1.35 (TrailMode other than TRAIL_RISK). Closed trigger bars used:
//    Wilder ATR(TRAIL_ATR_PERIOD) smoothed over TRAIL_ATR_BARS bars, EMA level run over TRAIL_EMA_BARS
//    bars (10 x its period if that is more), Parabolic SAR run over TRAIL_PSAR_BARS bars, last
//    confirmed swing searched in TRAIL_PIVOT_BARS bars
#define  TRAIL_ATR_PERIOD  14
#define  TRAIL_ATR_BARS    300
#define  TRAIL_EMA_BARS    500
#define  TRAIL_PSAR_BARS   1000
#define  TRAIL_PIVOT_BARS  1000
datetime g_trailBar        = 0;    // M1 bar on whose first tick the once-a-minute trailing was last completed
ulong    g_trailSkipLog    = 0;    // ticket whose 'stop inside the stops level' skip was reported (once per position)
ulong    g_trailCloseLog   = 0;    // ticket whose trailing close at market was announced (once per position)
ulong    g_trailCloseFail  = 0;    // ticket whose failed trailing close was reported (once per position)
bool     g_trailCloseDue   = false;// a trailing close at market was due on this tick
datetime g_trailExitBar    = 0;    // trigger bar on which a trailing close at market was last due (its signal is not traded)
bool     g_trailBarsWarned = false;// 'not enough closed bars for the trailing level' printed
ulong    g_stepTicket      = 0;    // TRAIL_STEP: position whose best price of the completed M1 bars is cached
datetime g_stepBar         = 0;    // TRAIL_STEP: M1 bar on which that cache was read
double   g_stepBest        = 0.0;  // TRAIL_STEP: the cached best price
bool     g_nettingWarned   = false;// netting-account warning printed
datetime g_notReadySince   = 0;    // first tick on which the signal data was not ready (0 = ready)
datetime g_notReadyWarned  = 0;    // last 'data not ready' warning (at most one every 5 trigger bars)

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

//--- factor of the dollar distances with ScaleWithPrice: price / ReferencePrice (1 when off)
double PriceScale(const double price)
  {
   if(!ScaleWithPrice || ReferencePrice <= 0.0 || price <= 0.0)
      return 1.0;
   return price / ReferencePrice;
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
   if(TrailMode == TRAIL_RISK && TrailStartR > 0.0 && TrailDistanceR <= 0.0)
     {
      Print("[LOMA] TrailDistanceR must be > 0 when TrailStartR > 0");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(!TrailInputsOK())
      return INIT_PARAMETERS_INCORRECT;
   if(UseStochTurnFilter && (StochTurnBars < 1 || StochTurnBars > 1000 || StochTurnLow < 0.0 || StochTurnHigh > 100.0))
     {
      Print("[LOMA] Stochastic turn filter: StochTurnBars must be 1 .. 1000, StochTurnLow >= 0 and StochTurnHigh <= 100. Got ",
            StochTurnBars, ", ", StochTurnLow, ", ", StochTurnHigh);
      return INIT_PARAMETERS_INCORRECT;
     }
   if(ScaleWithPrice && ReferencePrice <= 0.0)
     {
      Print("[LOMA] ScaleWithPrice needs ReferencePrice > 0 (the price at which the *_Points values were calibrated). Got ",
            ReferencePrice);
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
   if(CommissionPerLot < 0.0)
      Print("[LOMA] CommissionPerLot is negative (", CommissionPerLot, "): counted as a round-trip cost of ",
            -CommissionPerLot, " per lot");
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
   if(UseHTFFilter && PeriodSeconds(HTF_Timeframe) >= PeriodSeconds(PERIOD_MN1))
     {
      Print("[LOMA] A monthly HTF_Timeframe is not supported (too few monthly bars for the readiness check)");
      return INIT_PARAMETERS_INCORRECT;
     }
   bool isGold = (StringFind(_Symbol, "XAU") >= 0 || StringFind(_Symbol, "GOLD") >= 0);
   bool isBtc  = (StringFind(_Symbol, "BTC") >= 0);
   if(!isGold && !isBtc)
      Print("[LOMA] Warning: presets exist for XAUUSD and BTCUSD only; attached to ", _Symbol);
   if(isBtc && MaxSpread_Points < 500)
      Print("[LOMA] Warning: ", _Symbol, " with gold-sized distances (MaxSpread_Points=", MaxSpread_Points,
            "): load a Loma_BTC preset.");
   if(isGold && MaxSpread_Points > 500)
      Print("[LOMA] Warning: ", _Symbol, " with BTC-sized distances (MaxSpread_Points=", MaxSpread_Points,
            "): load a gold preset.");

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
   //--- R7b: the turn filter has its own Stochastic(7,1,7), whatever Stoch_K is
   if(UseStochTurnFilter)
     {
      g_hStochTurn = iStochastic(_Symbol, TriggerTimeframe, 7, 7, 1, MODE_SMA, STO_LOWHIGH);
      if(g_hStochTurn == INVALID_HANDLE)
        {
         Print("[LOMA] Failed to create the Stochastic handle of the turn filter, error ", GetLastError());
         return INIT_FAILED;
        }
     }

   //--- trade object
   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints((ulong)MathMax(0.0, MathCeil(MaxSlippage_Points * g_ptScale - 1e-9)));
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.LogLevel(LOG_LEVEL_ERRORS);

   //--- hump state: rebuilt from history as soon as the indicator data is calculated
   //    (usually on the first tick; tried here too so the panel is right at once)
   ResetHumpState();
   g_lastBarTime   = 0;
   g_signalActive  = false;
   g_signalBarTime = 0;
   g_trailBar        = 0;
   g_trailBarsWarned = false;
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
   if(TrailMode != TRAIL_RISK)
      Log("Trailing system: " + TrailModeText());
   if(UseStochTurnFilter)
      Log(StringFormat("Stochastic turn filter on: Stochastic(7,1,7) of %s, last %d closed bars, levels %.1f / %.1f",
                       TFName(TriggerTimeframe), StochTurnBars, StochTurnLow, StochTurnHigh));
   if(ScaleWithPrice)
      Log(StringFormat("Price scaling on: SL_Buffer_Points, MinSL_Points and MaxSL_Points x bid / %.2f", ReferencePrice));
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
   if(g_hStochTurn != INVALID_HANDLE) IndicatorRelease(g_hStochTurn);
   g_hMacd   = INVALID_HANDLE;
   g_hStoch  = INVALID_HANDLE;
   g_hEmaHTF = INVALID_HANDLE;
   g_hStochTurn = INVALID_HANDLE;
   ObjectsDeleteAll(0, OBJ_PREFIX);
   Comment("");
  }

//====================================================================
// OnTick
//====================================================================
void OnTick()
  {
   if(!g_nettingWarned && NettingAccount())
     {
      g_nettingWarned = true;
      Print("[LOMA] Warning: netting account. Every EA and manual trade on ", _Symbol,
            " shares one position here: run only one Loma preset per symbol. No entry is sent while ",
            "another position on ", _Symbol, " is open.");
     }

   //--- R9: flat before the weekend (Friday from WeekendCloseTime on; missed closes on the next tick)
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
   if(g_trailCloseDue)                         // R8b: a trailing stop already crossed was closed at market on this tick
     {
      g_trailExitBar  = barTime;
      g_trailCloseDue = false;
     }
   if(barTime == 0)
      return;

   if(barTime != g_lastBarTime)
     {
      //--- evaluate once per bar, but only on up-to-date data; a not-ready
      //    read is retried on the next tick instead of losing the signal
      int state = EvaluateSignal(barTime);
      if(state == SIG_NOTREADY)
        {
         datetime nowNR = TimeCurrent();
         if(g_notReadySince == 0)
            g_notReadySince = nowNR;
         else
            if(nowNR - g_notReadySince >= 5 * PeriodSeconds(TriggerTimeframe) &&
               nowNR - g_notReadyWarned >= 5 * PeriodSeconds(TriggerTimeframe))
              {
               g_notReadyWarned = nowNR;
               Print(StringFormat("[LOMA] Warning: indicator data not ready since %s - no signals are evaluated",
                                  TimeToString(g_notReadySince, TIME_DATE | TIME_MINUTES)));
              }
         LogSkip("indicator data not up to date yet - retrying on next tick");
         return;
        }
      g_notReadySince  = 0;
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
   if(NettingAccount() && PositionSelect(_Symbol))   // netting: never add to or reverse another position
     {
      LogSkip("netting account: another position on this symbol is open");
      g_signalActive = false;
      return;
     }
   if(g_timeExitBar == barTime)                // as in the backtest: no entry on the bar of a time exit
     {
      LogSkip("a position was open at the bar open (time exit on this bar)");
      g_signalActive = false;
      return;
     }
   if(g_trailExitBar == barTime)               // as in the backtest: no entry on the bar of a trailing close at market
     {
      LogSkip("a position was open at the bar open (trailing stop already crossed, closed at market on this bar)");
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
   if(UseStochTurnFilter && !HandleReady(g_hStochTurn, TriggerTimeframe))
      return false;
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
   //--- R7b: optional Stochastic turn filter on the signal bar, read before the signal is logged
   //    for the same reason
   int    turn    = 1;
   string turnWhy = "";
   if(UseStochTurnFilter)
     {
      turn = StochTurnCheck(g_sigSide, turnWhy);
      if(turn < 0)
         return SIG_NOTREADY;                        // the pending signal is kept for the retry
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
   if(turn == 0)
     {
      LogSkip(turnWhy);
      return SIG_NONE;
     }
   return SIG_VALID;
  }

//--- R7b: Stochastic turn rule on the signal bar (the last closed trigger bar), with the filter's
//    own Stochastic(7,1,7): the main line was at the extreme on one of the last StochTurnBars
//    closed bars and, on the signal bar, is beyond its signal line or back inside the level
//    (Feat.xs_dn / xs_up in research/hump_wf.py).
//    Returns 1 entry allowed, 0 not allowed ('why' is the skip reason), -1 data not ready.
int StochTurnCheck(const int side, string &why)
  {
   double mainBuf[], sigBuf[];
   ArraySetAsSeries(mainBuf, false);                 // index 0 = oldest bar, the last one is the signal bar
   ArraySetAsSeries(sigBuf, false);
   if(CopyBuffer(g_hStochTurn, 0, 1, StochTurnBars, mainBuf) != StochTurnBars ||
      CopyBuffer(g_hStochTurn, 1, 1, 1, sigBuf) != 1)
      return -1;
   if(iTime(_Symbol, TriggerTimeframe, 1) != g_sigClosedBar)
      return -1;                                     // a new bar appeared while reading
   double hi       = -DBL_MAX;
   double lo       = DBL_MAX;
   bool   allValid = true;
   for(int k = 0; k < StochTurnBars; k++)
     {
      double v = mainBuf[k];
      if(v == EMPTY_VALUE || !MathIsValidNumber(v))
        {
         allValid = false;                           // as in the backtest: a missing value in the window, no entry
         break;
        }
      if(v > hi) hi = v;
      if(v < lo) lo = v;
     }
   double m   = mainBuf[StochTurnBars - 1];
   double s   = sigBuf[0];
   bool   sOk = (s != EMPTY_VALUE && MathIsValidNumber(s));
   if(!allValid)
     {
      why = StringFormat("Stochastic turn filter: no Stochastic value on the last %d closed bars -> %s not allowed",
                         StochTurnBars, SideName(side));
      return 0;
     }
   bool ok = (side < 0) ? (hi >= StochTurnHigh && ((sOk && m < s) || m < StochTurnHigh))
                        : (lo <= StochTurnLow && ((sOk && m > s) || m > StochTurnLow));
   if(ok)
      return 1;
   why = StringFormat("Stochastic turn filter: %s of the last %d bars %.1f, main %.1f, signal %.1f (level %.1f) -> %s not allowed",
                      side < 0 ? "highest" : "lowest", StochTurnBars, side < 0 ? hi : lo, m, sOk ? s : 0.0,
                      side < 0 ? StochTurnHigh : StochTurnLow, SideName(side));
   return 0;
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
   double ps     = PriceScale(bid);                  // R5b: bid / ReferencePrice with ScaleWithPrice, else 1
   if(side < 0)
     {
      //--- SELL at the bid; stopped and paid on the ask -> + spread on SL and TP
      p.entry = bid;
      p.sl    = NormalizePrice(g_sigSlRef + Pts(SL_Buffer_Points) * ps + spread);
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
      p.sl    = NormalizePrice(g_sigSlRef - Pts(SL_Buffer_Points) * ps);
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
   //    R5b: the limits are multiplied by ps
   double riskPts = risk / (_Point * g_ptScale);
   if(riskPts < MinSL_Points * ps)
     {
      reason = StringFormat("SL too tight (%.0f < %.0f points)", riskPts, MinSL_Points * ps);
      return false;
     }
   if(MaxSL_Points > 0 && riskPts > MaxSL_Points * ps)
     {
      reason = StringFormat("SL too wide (%.0f > %.0f points)", riskPts, MaxSL_Points * ps);
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
        {
         LogSkip("cannot value the stop: OrderCalcProfit failed and the tick value is 0");
         return 0.0;
        }
      lossPerLot = MathAbs(sl - entry) / tickSize * tickValue;
     }
   lossPerLot = MathAbs(lossPerLot);
   if(lossPerLot <= 0.0)
     {
      LogSkip("cannot value the stop distance");
      return 0.0;
     }
   lossPerLot += MathAbs(CommissionPerLot);             // a stop-out also pays the round-trip commission (sign ignored)

   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(volStep <= 0.0)
      volStep = 0.01;
   if(MaxLotSize > 0.0)
      volMax = MathMin(volMax, MathFloor(MaxLotSize / volStep + 1e-9) * volStep);
   if(volMax < volMin)
     {
      LogSkip(StringFormat("lot cap %.3f (MaxLotSize %.3f on volume step %.3f, or the broker maximum) is below the broker minimum lot %.3f",
                           volMax, MaxLotSize, volStep, volMin));
      return 0.0;
     }

   double lots = riskMoney / lossPerLot;
   lots = MathFloor(lots / volStep + 1e-9) * volStep;

   if(lots < volMin)
     {
      double minLotPct = 100.0 * volMin * lossPerLot / equity;   // risk of the minimum lot, % of equity
      if(SkipIfBelowMinLot || minLotPct > 2.0 * RiskPercent)
        {
         LogSkip(StringFormat("risk lot %.4f < min lot %.2f (the min lot would risk %.2f%%)",
                              riskMoney / lossPerLot, volMin, minLotPct));
         return 0.0;
        }
      Log(StringFormat("Risk lot below the broker minimum: trading the min lot %.2f = %.2f%% risk", volMin, minLotPct));
      lots = volMin;
     }
   lots = MathMin(lots, volMax);
   double sized = lots;                                   // before the free-margin check

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
   if(lots < sized - 0.5 * volStep)
      Log(StringFormat("Lot cut by free margin: %.2f -> %.2f lots (risk below RiskPercent)", sized, lots));

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
   //--- counted in whole points: (ask - bid) / point is not exact in binary floating point, and a spread
   //    equal to MaxSpread_Points must pass every time (as in the reference backtest)
   double spreadPts = MathRound((Ask() - Bid()) / _Point) / g_ptScale;
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

//--- R9: server time of the most recent Friday WeekendCloseTime at or before 'now'
datetime LastWeekendCloseMoment(const datetime now)
  {
   MqlDateTime dt;
   TimeToStruct(now, dt);
   int      back = (dt.day_of_week + 2) % 7;           // days since Friday: Fri 0, Sat 1, Sun 2, Mon 3 ... Thu 6
   datetime m    = now - (now % 86400) - back * 86400 + (datetime)(g_weekendMin * 60);
   if(m > now)
      m -= 7 * 86400;                                    // Friday before WeekendCloseTime: last week's
   return m;
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

//--- netting / exchange account: ONE position per symbol, shared by every EA and manual trade.
//    Read when needed (before the terminal is connected the account mode is not known yet).
bool NettingAccount()
  {
   return (AccountInfoInteger(ACCOUNT_MARGIN_MODE) != (long)ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
  }

//====================================================================
// POSITION MANAGEMENT (R8: trailing in R multiples)
//====================================================================
//--- a trailing modification failed: pause the trailing for WEEKEND_RETRY_SEC seconds and
//    report each new reason once (market closed at the daily open, frozen, ...)
void TrailFailed(const datetime now)
  {
   g_trailLastFail = now;
   uint rc = g_trade.ResultRetcode();
   if(rc != g_trailFailCode)
     {
      g_trailFailCode = rc;
      Print("[LOMA] Trailing modify failed: ", g_trade.ResultRetcodeDescription(),
            " - retrying at most every ", WEEKEND_RETRY_SEC, " s");
     }
  }

//--- 1R of a position from its opening deal: |fill price - SL sent with the order| (0 = unknown)
double InitialRiskFromHistory(const long positionId)
  {
   if(!HistorySelectByPosition(positionId))
      return 0.0;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0 || HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      double price = HistoryDealGetDouble(d, DEAL_PRICE);
      double sl    = HistoryDealGetDouble(d, DEAL_SL);
      if(sl <= 0.0)
        {
         ulong order = (ulong)HistoryDealGetInteger(d, DEAL_ORDER);
         if(order > 0 && HistoryOrderSelect(order))
            sl = HistoryOrderGetDouble(order, ORDER_SL);
        }
      if(price > 0.0 && sl > 0.0)
         return MathAbs(price - sl);
     }
   return 0.0;
  }

void ManageOpenPositions()
  {
   if(TrailMode == TRAIL_RISK && TrailStartR <= 0.0)
      return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      return;                                  // algo trading off: a modification cannot be sent
   datetime nowT = TimeCurrent();
   if(g_trailLastFail > 0 && nowT >= g_trailLastFail && nowT - g_trailLastFail < WEEKEND_RETRY_SEC)
      return;                                  // throttle retries after a failed modification
   datetime m1      = nowT - (nowT % 60);      // R8b: open time of the M1 bar this tick belongs to
   bool     allDone = true;                    // R8b: every position was evaluated on this M1 bar
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

      //--- remember the initial risk (1R) the first time we see the position: from the opening
      //    deal (the SL sent with the order), else from the SL as it is now. R8b systems: the SL as it
      //    is now only while it is still on the loss side of the open price (a stop already moved past
      //    the entry is not the initial risk: the opening deal is looked up again on the next tick)
      string rKey = GVKey("R", ticket);
      if(!GlobalVariableCheck(rKey))
        {
         double r0 = InitialRiskFromHistory(g_pos.Identifier());
         if(r0 <= 0.0 && sl > 0.0 && (TrailMode == TRAIL_RISK || (isSell ? sl > open : sl < open)))
            r0 = MathAbs(sl - open);
         if(r0 > 0.0)
           {
            GlobalVariableSet(rKey, r0);
            GlobalVariablesFlush();
           }
        }
      double initRisk = GlobalVariableCheck(rKey) ? GlobalVariableGet(rKey) : 0.0;
      if(initRisk <= 0.0)
         continue;

      //--- R8b: the trailing systems other than TRAIL_RISK. TRAIL_STEP on every tick, the others
      //    once per closed one-minute bar, on the first tick of the next M1 bar
      if(TrailMode != TRAIL_RISK)
        {
         if(TrailMode != TRAIL_STEP && m1 == g_trailBar)
            continue;
         if(!TrailPosition(ticket, g_pos.Time(), open, sl, tp, isSell, initRisk, m1, nowT))
            allDone = false;                   // data not ready or a request failed: again on the next tick
         continue;
        }

      if(isSell)
        {
         double ask = Ask();
         if(open - ask < TrailStartR * initRisk)
            continue;
         double newSL = NormalizePrice(ask + TrailDistanceR * initRisk);
         if((sl == 0.0 || (newSL <= sl - step && newSL < sl - 0.5 * _Point)) && newSL - ask > minD)
           {
            if(g_trade.PositionModify(ticket, newSL, tp))
              {
               g_trailFailCode = 0;
               Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
              }
            else
               TrailFailed(nowT);
           }
        }
      else
        {
         double bid = Bid();
         if(bid - open < TrailStartR * initRisk)
            continue;
         double newSL = NormalizePrice(bid - TrailDistanceR * initRisk);
         if((sl == 0.0 || (newSL >= sl + step && newSL > sl + 0.5 * _Point)) && bid - newSL > minD)
           {
            if(g_trade.PositionModify(ticket, newSL, tp))
              {
               g_trailFailCode = 0;
               Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
              }
            else
               TrailFailed(nowT);
           }
        }
     }
   if(TrailMode != TRAIL_RISK && allDone)
      g_trailBar = m1;
  }

//====================================================================
// TRAILING SYSTEMS (R8b: TrailMode other than TRAIL_RISK)
// Reference: research/hump_trail.py simulate_x(), hump_trail2.py simulate_y() with closed = 1
//====================================================================
//--- "EMA (start 0.50, distance 0.50, param 34)" for the journal and the panel
string TrailModeText()
  {
   string n = EnumToString(TrailMode);
   StringReplace(n, "TRAIL_", "");
   return StringFormat("%s (start %.2f, distance %.2f, param %d)", n, TrailStartR, TrailDistanceR, TrailParam);
  }

//--- the level systems: the stop follows a level read from the closed trigger bars
bool TrailIsLevelMode()
  {
   return (TrailMode == TRAIL_CANDLES || TrailMode == TRAIL_EMA || TrailMode == TRAIL_SMA ||
           TrailMode == TRAIL_PSAR || TrailMode == TRAIL_BOLLINGER || TrailMode == TRAIL_HTF_CANDLE ||
           TrailMode == TRAIL_PIVOTS || TrailMode == TRAIL_HUMP);
  }

//--- TRAIL_HTF_CANDLE: timeframe of the candle of TrailParam minutes (PERIOD_CURRENT = not supported)
ENUM_TIMEFRAMES TrailHtfPeriod()
  {
   if(TrailParam == 15)
      return PERIOD_M15;
   if(TrailParam == 30)
      return PERIOD_M30;
   if(TrailParam == 60)
      return PERIOD_H1;
   if(TrailParam == 240)
      return PERIOD_H4;
   return PERIOD_CURRENT;
  }

//--- OnInit checks of TrailStartR, TrailDistanceR and TrailParam for the system chosen in TrailMode
//    (TRAIL_RISK keeps its own check). Prints the reason and returns false on a wrong input.
bool TrailInputsOK()
  {
   if(TrailMode == TRAIL_RISK)
      return true;
   int    mode = (int)TrailMode;
   string name = EnumToString(TrailMode);
   if(mode < 0 || mode > (int)TRAIL_HUMP)
     {
      Print("[LOMA] TrailMode ", mode, " is not a trailing system (0 .. ", (int)TRAIL_HUMP, ")");
      return false;
     }
   if(TrailStartR < 0.0)
     {
      Print("[LOMA] TrailStartR must be >= 0 with TrailMode ", name, ". Got ", TrailStartR);
      return false;
     }
   if((TrailMode == TRAIL_ATR_ENTRY || TrailMode == TRAIL_PERCENT || TrailMode == TRAIL_PROFIT_LOCK ||
       TrailMode == TRAIL_STEP) && TrailStartR <= 0.0)
     {
      Print("[LOMA] TrailStartR must be > 0 with TrailMode ", name, ". Got ", TrailStartR);
      return false;
     }
   if((TrailMode == TRAIL_ATR_ENTRY || TrailMode == TRAIL_PERCENT || TrailMode == TRAIL_CHANDELIER) &&
      TrailDistanceR <= 0.0)
     {
      Print("[LOMA] TrailDistanceR must be > 0 with TrailMode ", name, ". Got ", TrailDistanceR);
      return false;
     }
   if(TrailMode == TRAIL_PROFIT_LOCK && (TrailDistanceR < 0.0 || TrailDistanceR > 1.0))
     {
      Print("[LOMA] TrailDistanceR is the share of the best profit kept with TrailMode ", name,
            ": must be in [0, 1]. Got ", TrailDistanceR);
      return false;
     }
   if((TrailMode == TRAIL_CANDLES || TrailMode == TRAIL_EMA || TrailMode == TRAIL_SMA) &&
      (TrailParam < 1 || TrailParam > 1000))
     {
      Print("[LOMA] TrailParam is the number of bars / the period with TrailMode ", name,
            ": must be 1 .. 1000. Got ", TrailParam);
      return false;
     }
   if(TrailMode == TRAIL_PIVOTS && (TrailParam < 1 || TrailParam > 100))
     {
      Print("[LOMA] TrailParam is the number of bars on each side of the swing with TrailMode ", name,
            ": must be 1 .. 100. Got ", TrailParam);
      return false;
     }
   if(TrailMode == TRAIL_PSAR && (TrailParam < 0 || TrailParam > 2))
     {
      Print("[LOMA] TrailParam must be 0 (0.02 / 0.2), 1 (0.01 / 0.1) or 2 (0.04 / 0.2) with TrailMode ", name,
            ". Got ", TrailParam);
      return false;
     }
   if(TrailMode == TRAIL_BOLLINGER && (TrailParam < 0 || TrailParam > 1))
     {
      Print("[LOMA] TrailParam must be 0 (1 standard deviation) or 1 (2 standard deviations) with TrailMode ", name,
            ". Got ", TrailParam);
      return false;
     }
   if(TrailMode == TRAIL_HTF_CANDLE)
     {
      int trigMin = PeriodSeconds(TriggerTimeframe) / 60;
      if(TrailHtfPeriod() == PERIOD_CURRENT || trigMin < 1 || TrailParam <= trigMin || TrailParam % trigMin != 0)
        {
         Print("[LOMA] TrailParam is the minutes of the higher candle with TrailMode ", name,
               ": must be 15, 30, 60 or 240, larger than and a multiple of the ", trigMin,
               " minutes of TriggerTimeframe. Got ", TrailParam);
         return false;
        }
     }
   return true;
  }

//--- the history holds fewer closed trigger bars than the trailing needs: said once
void TrailBarsMissing(const int need, const int have)
  {
   if(g_trailBarsWarned)
      return;
   g_trailBarsWarned = true;
   Print(StringFormat("[LOMA] Trailing %s needs %d closed %s bars, the history has %d: no stop is moved until they are there",
                      TrailModeText(), need, TFName(TriggerTimeframe), have));
  }

//--- 'count' closed TriggerTimeframe bars ending at the bar of 'shift', whose open time must be
//    'barTime' (index 0 = oldest bar). Returns 1 read, 0 the history is shorter than that, -1 not
//    readable yet (series not formed or not synchronized: Bars() is 0) or a new bar appeared while
//    reading (again on the next tick).
int TrailRates(const int shift, const int count, const datetime barTime, MqlRates &r[])
  {
   int total = Bars(_Symbol, TriggerTimeframe);
   if(total <= 0 || !SeriesInfoInteger(_Symbol, TriggerTimeframe, SERIES_SYNCHRONIZED))
      return -1;
   int have = total - shift;
   if(have < count)
     {
      TrailBarsMissing(count, have);
      return 0;
     }
   ArraySetAsSeries(r, false);
   if(CopyRates(_Symbol, TriggerTimeframe, shift, count, r) != count)
      return -1;
   if(r[count - 1].time != barTime)
      return -1;
   return 1;
  }

//--- Wilder ATR(14) at the last of 'count' bars: true range smoothed with alpha = 1/14 from the
//    second bar on (wilder_atr() in research/hump_trail2.py; MetaTrader's iATR is a simple
//    average and is not this). With TRAIL_ATR_BARS bars the first value no longer matters.
double WilderATR(const MqlRates &r[], const int count)
  {
   double atr = 0.0;
   for(int k = 1; k < count; k++)
     {
      double tr = MathMax(r[k].high - r[k].low,
                          MathMax(MathAbs(r[k].high - r[k - 1].close), MathAbs(r[k].low - r[k - 1].close)));
      atr = (k == 1) ? tr : atr + (tr - atr) / TRAIL_ATR_PERIOD;
     }
   return atr;
  }

//--- TRAIL_ATR_ENTRY: Wilder ATR(14) of the trigger timeframe at the signal bar of a position (the
//    last trigger bar closed before it was opened). Computed from the history once and kept in
//    a terminal global variable next to the initial risk, so it is the same after a restart.
//    Returns 1 found, 0 the history is too short, -1 not readable yet.
int EntryATR(const ulong ticket, const datetime opened, double &atr)
  {
   string aKey = GVKey("A", ticket);
   if(GlobalVariableCheck(aKey))
     {
      atr = GlobalVariableGet(aKey);
      return (atr > 0.0) ? 1 : 0;
     }
   int sh = iBarShift(_Symbol, TriggerTimeframe, opened, false);
   if(sh < 0)
      return -1;
   datetime entryTrig = iTime(_Symbol, TriggerTimeframe, sh);       // trigger bar the position was opened in
   datetime sigBar    = iTime(_Symbol, TriggerTimeframe, sh + 1);   // the bar before it: the signal bar
   if(entryTrig == 0 || sigBar == 0 || opened < entryTrig || opened >= entryTrig + PeriodSeconds(TriggerTimeframe))
      return -1;
   MqlRates r[];
   int got = TrailRates(sh + 1, TRAIL_ATR_BARS + 1, sigBar, r);
   if(got <= 0)
      return got;
   if(iBarShift(_Symbol, TriggerTimeframe, opened, false) != sh)
      return -1;                                     // a new bar appeared while reading
   atr = WilderATR(r, TRAIL_ATR_BARS + 1);
   if(atr <= 0.0)
      return 0;
   GlobalVariableSet(aKey, atr);
   GlobalVariablesFlush();
   return 1;
  }

//--- best price of the COMPLETED M1 bars of the symbol with open times fromBar .. m1 - 1 minute:
//    the highest bid high for a buy; the lowest ask low for a sell, where ask low = bid low + that
//    bar's spread (the current spread when the bar has none). Read from the history every time,
//    nothing is remembered. False when the bars cannot be read (yet).
bool BestSince(const datetime fromBar, const datetime m1, const bool isSell, double &best)
  {
   datetime lastBar = m1 - 60;                       // the newest completed M1 bar there can be
   if(lastBar < fromBar)
      return false;
   //--- request first, then check: the request makes the terminal build the M1 series when nothing
   //    else uses it (SERIES_SYNCHRONIZED only reads its state). The bar of m1 must be in the series,
   //    so that the bar before it is complete.
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_M1, fromBar, lastBar, r);
   if(n <= 0 || !SeriesInfoInteger(_Symbol, PERIOD_M1, SERIES_SYNCHRONIZED) || iTime(_Symbol, PERIOD_M1, 0) < m1)
      return false;
   double spreadNow = MathMax(0.0, Ask() - Bid());
   bool   found     = false;
   for(int k = 0; k < n; k++)
     {
      if(r[k].time < fromBar || r[k].time > lastBar)
         continue;
      double v = isSell ? r[k].low + ((r[k].spread > 0) ? r[k].spread * _Point : spreadNow) : r[k].high;
      if(!found || (isSell ? v < best : v > best))
         best = v;
      found = true;
     }
   return found;
  }

//--- level of the level systems for the M1 bar opening at m1, from the closed trigger bars (the
//    newest is 'lastClosed', shift 1): support for a buy, resistance for a sell, in chart (bid)
//    prices. Ports of MarketX._levels() / psar_levels() / hump_levels() in research/hump_trail.py
//    and MarketY._levels() / pivot_levels() in research/hump_trail2.py.
//    Returns 1 level found, 0 no level this minute, -1 data not ready (again on the next tick).
int TrailLevel(const bool isSell, const datetime lastClosed, const datetime m1, double &level)
  {
   MqlRates r[];
   int      got = 0;
   if(TrailMode == TRAIL_CANDLES)
     {
      //--- lowest low / highest high of the last TrailParam closed bars
      got = TrailRates(1, TrailParam, lastClosed, r);
      if(got <= 0)
         return got;
      level = isSell ? r[0].high : r[0].low;
      for(int k = 1; k < TrailParam; k++)
         level = isSell ? MathMax(level, r[k].high) : MathMin(level, r[k].low);
      return 1;
     }
   if(TrailMode == TRAIL_EMA)
     {
      //--- EMA(TrailParam) of the closes, run over so many bars that its first value no longer matters
      int n = MathMax(TRAIL_EMA_BARS, 10 * TrailParam);
      got = TrailRates(1, n, lastClosed, r);
      if(got <= 0)
         return got;
      double alpha = 2.0 / (TrailParam + 1.0);
      level = r[0].close;
      for(int k = 1; k < n; k++)
         level += alpha * (r[k].close - level);
      return 1;
     }
   if(TrailMode == TRAIL_SMA || TrailMode == TRAIL_BOLLINGER)
     {
      //--- SMA(TrailParam) of the closes; Bollinger band: SMA(20) -/+ 1 or 2 population standard
      //    deviations of the same 20 closes
      int n = (TrailMode == TRAIL_SMA) ? TrailParam : 20;
      got = TrailRates(1, n, lastClosed, r);
      if(got <= 0)
         return got;
      double mean = 0.0;
      for(int k = 0; k < n; k++)
         mean += r[k].close;
      mean /= n;
      level = mean;
      if(TrailMode == TRAIL_BOLLINGER)
        {
         double var = 0.0;
         for(int k = 0; k < n; k++)
            var += (r[k].close - mean) * (r[k].close - mean);
         double band = ((TrailParam == 0) ? 1.0 : 2.0) * MathSqrt(var / n);
         level = isSell ? mean + band : mean - band;
        }
      return 1;
     }
   if(TrailMode == TRAIL_PSAR)
     {
      //--- Parabolic SAR for the next bar: support in up mode (buys only), resistance in down mode
      //    (sells only). Run over TRAIL_PSAR_BARS bars: the same values as over the whole history
      double sarStep = (TrailParam == 1) ? 0.01 : (TrailParam == 2) ? 0.04 : 0.02;
      double sarMax  = (TrailParam == 1) ? 0.1 : 0.2;
      int    n       = TRAIL_PSAR_BARS;
      got = TrailRates(1, n, lastClosed, r);
      if(got <= 0)
         return got;
      bool   up  = (r[1].high >= r[0].high);
      double ep  = up ? r[1].high : r[1].low;
      double sar = up ? MathMin(r[0].low, r[1].low) : MathMax(r[0].high, r[1].high);
      double af  = sarStep;
      for(int k = 2; k < n; k++)
        {
         if(up)
           {
            if(r[k].low < sar)                       // reversal to down mode
              {
               up  = false;
               sar = ep;
               ep  = r[k].low;
               af  = sarStep;
              }
            else
               if(r[k].high > ep)
                 {
                  ep = r[k].high;
                  af = MathMin(af + sarStep, sarMax);
                 }
           }
         else
           {
            if(r[k].high > sar)                      // reversal to up mode
              {
               up  = true;
               sar = ep;
               ep  = r[k].high;
               af  = sarStep;
              }
            else
               if(r[k].low < ep)
                 {
                  ep = r[k].low;
                  af = MathMin(af + sarStep, sarMax);
                 }
           }
         sar = sar + af * (ep - sar);
         if(up)
            sar = MathMin(sar, MathMin(r[k].low, r[k - 1].low));
         else
            sar = MathMax(sar, MathMax(r[k].high, r[k - 1].high));
        }
      if(up == isSell)
         return 0;                                   // the SAR is on the other side: no level for this position
      level = sar;
      return 1;
     }
   if(TrailMode == TRAIL_PIVOTS)
     {
      //--- last confirmed swing: a bar strictly beyond the TrailParam bars on each side of it,
      //    known TrailParam bars later
      int w     = TrailParam;
      int total = Bars(_Symbol, TriggerTimeframe);
      if(total <= 0)
         return -1;                                  // series not formed or not synchronized yet
      int n = MathMin(TRAIL_PIVOT_BARS, total - 1);
      if(n < 2 * w + 1)
        {
         TrailBarsMissing(2 * w + 1, n);
         return 0;
        }
      got = TrailRates(1, n, lastClosed, r);
      if(got <= 0)
         return got;
      for(int j = n - 1 - w; j >= w; j--)
        {
         bool swing = true;
         for(int q = j - w; q <= j + w && swing; q++)
            if(q != j && (isSell ? r[q].high >= r[j].high : r[q].low <= r[j].low))
               swing = false;
         if(swing)
           {
            level = isSell ? r[j].high : r[j].low;
            return 1;
           }
        }
      return 0;
     }
   if(TrailMode == TRAIL_HTF_CANDLE)
     {
      //--- low / high of the last candle of TrailParam minutes that had closed by the close of
      //    the last closed trigger bar
      ENUM_TIMEFRAMES htf = TrailHtfPeriod();
      if(!HTFBarCurrent(htf, m1) || !SeriesInfoInteger(_Symbol, htf, SERIES_SYNCHRONIZED))
         return -1;                                  // HTFBarCurrent's iTime requests the series first (it may be unused otherwise)
      datetime latest = lastClosed + PeriodSeconds(TriggerTimeframe) - PeriodSeconds(htf);   // latest open time it can have
      MqlRates h[];
      ArraySetAsSeries(h, false);
      if(CopyRates(_Symbol, htf, latest, 1, h) != 1)
         return -1;
      if(h[0].time > latest)
         return -1;
      level = isSell ? h[0].high : h[0].low;
      return 1;
     }
   //--- TRAIL_HUMP: the hump state machine holds the low of the last completed negative hump and
   //    the high of the last completed positive hump (hump_levels()); it is brought up to the
   //    last closed bar first (the trailing runs before the signal evaluation of the tick)
   if(!HandleReady(g_hMacd, TriggerTimeframe) || !HandleReady(g_hStoch, TriggerTimeframe) || !AdvanceHumps())
      return -1;
   if(!g_stateReady || g_lastProcTime != lastClosed)
      return -1;
   if(isSell ? !g_hasPosHi : !g_hasNegLo)
      return 0;
   level = isSell ? g_lastPosHi : g_lastNegLo;
   return 1;
  }

//--- a trailing stop on the tick grid, rounded to the looser side (down for a buy, up for a sell).
//    Prices lie on the grid, so the stop is then hit exactly when the unrounded stop of the
//    reference backtest is, and it tightens the current stop by a point exactly when the unrounded
//    one does (rounded to the nearest tick, a buy stop can sit up to half a tick higher and close
//    the trade a minute early)
double TrailStopPrice(const double price, const bool isSell)
  {
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0.0)
      tick = _Point;
   double q = price / tick;
   q = isSell ? MathCeil(q - 1e-7) : MathFloor(q + 1e-7);   // 1e-7 tick: floating-point noise of a price on the grid
   return NormalizeDouble(q * tick, _Digits);
  }

//--- move the stop of a position to 'cand', if that tightens it by at least minStep (and by a
//    point). Price already through the new stop: the position is closed at market (the reference
//    backtest fills at that minute's open). New stop closer to the price than the broker's stops
//    level: not placed now (one journal line per position).
//    Returns false when a request failed: it is repeated on a later tick (throttle of TrailFailed).
bool TrailApply(const ulong ticket, const bool isSell, const double sl, const double tp, const double cand,
                const double minStep, const datetime nowT)
  {
   double newSL = TrailStopPrice(cand, isSell);
   if(newSL <= 0.0)
      return true;
   if(sl != 0.0)
     {
      //--- the stop is only ever tightened
      if(isSell && !(newSL <= sl - minStep && newSL < sl - 0.5 * _Point))
         return true;
      if(!isSell && !(newSL >= sl + minStep && newSL > sl + 0.5 * _Point))
         return true;
     }
   double price = isSell ? Ask() : Bid();
   if(price <= 0.0)
      return false;
   if(isSell ? (price >= newSL) : (price <= newSL))
     {
      g_trailCloseDue = true;
      if(g_trailCloseLog != ticket)
        {
         g_trailCloseLog = ticket;
         Log(StringFormat("Trailing stop %.2f of #%I64u is already crossed (%s %.2f): closing at market",
                          newSL, ticket, isSell ? "ask" : "bid", price));
        }
      ResetLastError();
      bool sent = g_trade.PositionClose(ticket);
      uint rc   = g_trade.ResultRetcode();
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         g_trailFailCode = 0;
         return true;
        }
      g_trailLastFail = nowT;
      if(g_trailCloseFail != ticket)
        {
         g_trailCloseFail = ticket;
         Print(StringFormat("[LOMA] Trailing close of #%I64u failed: retcode=%u (%s) lastError=%d - retrying every few seconds",
                            ticket, rc, g_trade.ResultRetcodeDescription(), GetLastError()));
        }
      return false;
     }
   if(MathAbs(newSL - price) <= StopsLevelDistance())
     {
      if(g_trailSkipLog != ticket)
        {
         g_trailSkipLog = ticket;
         Log(StringFormat("Trailing SL %.2f of #%I64u is closer to the price than the broker's stops level: not moved now",
                          newSL, ticket));
        }
      return true;
     }
   if(g_trade.PositionModify(ticket, newSL, tp))
     {
      g_trailFailCode = 0;
      Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
      return true;
     }
   TrailFailed(nowT);
   return false;
  }

//--- one trailing evaluation of a position for the systems other than TRAIL_RISK: on every tick
//    for TRAIL_STEP, on the first tick of an M1 bar (open time m1) for the others.
//    Returns false when it must be repeated on the next tick (data not ready, or a request failed).
bool TrailPosition(const ulong ticket, const datetime opened, const double open, const double sl, const double tp,
                   const bool isSell, const double initRisk, const datetime m1, const datetime nowT)
  {
   datetime entryBar = opened - (opened % 60);       // M1 bar in which the position was opened
   double   bid      = Bid();
   double   ask      = Ask();
   if(bid <= 0.0 || ask <= 0.0)
      return false;

   //--- TRAIL_STEP, every tick: with the best profit seen so far fav and a = TrailStartR x 1R, the
   //    stop is at entry + (floor(fav / a) - 1) x a once fav >= a. Seen so far = this tick and the
   //    completed M1 bars from the entry bar on (read from the history once per M1 bar: restart-safe;
   //    the entry bar counts as a whole, as for the other systems and in the reference backtest)
   if(TrailMode == TRAIL_STEP)
     {
      double   fav  = isSell ? open - ask : bid - open;
      datetime from = entryBar;
      if(m1 > from)
        {
         if(g_stepTicket != ticket || g_stepBar != m1)
           {
            double b = 0.0;
            if(BestSince(from, m1, isSell, b))
              {
               g_stepTicket = ticket;
               g_stepBar    = m1;
               g_stepBest   = b;
              }
           }
         if(g_stepTicket == ticket && g_stepBar == m1)
            fav = MathMax(fav, isSell ? open - g_stepBest : g_stepBest - open);
        }
      double a = TrailStartR * initRisk;
      if(a <= 0.0 || fav < a)
         return true;
      double k = MathFloor(fav / a);
      return TrailApply(ticket, isSell, sl, tp, isSell ? open - (k - 1.0) * a : open + (k - 1.0) * a,
                        Pts(TrailStep_Points), nowT);
     }

   //--- the other systems act on the completed M1 bars from the entry bar on, never in the entry minute
   if(m1 <= entryBar)
      return true;
   bool   isLevel = TrailIsLevelMode();
   double best    = open;
   if((!isLevel || TrailStartR > 0.0) && !BestSince(entryBar, m1, isSell, best))
      return false;
   double fav  = isSell ? open - best : best - open;  // best profit of the completed M1 bars, in price
   double cand = 0.0;
   if(TrailMode == TRAIL_ATR_ENTRY || TrailMode == TRAIL_PERCENT)
     {
      //--- best price -/+ TrailDistanceR units once the profit has reached TrailStartR units;
      //    unit = ATR(14) at the signal bar, or 1% of the entry price
      double unit = 0.01 * open;
      if(TrailMode == TRAIL_ATR_ENTRY)
        {
         int got = EntryATR(ticket, opened, unit);
         if(got <= 0)
            return (got == 0);
        }
      if(fav < TrailStartR * unit)
         return true;
      cand = isSell ? best + TrailDistanceR * unit : best - TrailDistanceR * unit;
     }
   else
      if(TrailMode == TRAIL_PROFIT_LOCK)
        {
         //--- once the profit has reached TrailStartR x 1R: keep the share TrailDistanceR of the best profit
         if(fav < TrailStartR * initRisk)
            return true;
         cand = isSell ? open - TrailDistanceR * fav : open + TrailDistanceR * fav;
        }
      else
        {
         //--- TRAIL_CHANDELIER and the level systems: active from the minute after the entry
         //    (TrailStartR <= 0) or once the profit has reached TrailStartR x 1R; they read the
         //    last trigger bar that had closed when this M1 bar opened
         if(TrailStartR > 0.0 && fav < TrailStartR * initRisk)
            return true;
         if(!SeriesInfoInteger(_Symbol, TriggerTimeframe, SERIES_SYNCHRONIZED) || !HTFBarCurrent(TriggerTimeframe, m1))
            return false;
         datetime lastClosed = iTime(_Symbol, TriggerTimeframe, 1);
         if(lastClosed == 0)
            return false;
         if(TrailMode == TRAIL_CHANDELIER)
           {
            //--- best price -/+ TrailDistanceR x Wilder ATR(14) of that bar; as in the reference
            //    backtest the best price starts at the entry price
            MqlRates r[];
            int got = TrailRates(1, TRAIL_ATR_BARS + 1, lastClosed, r);
            if(got <= 0)
               return (got == 0);
            double atr = WilderATR(r, TRAIL_ATR_BARS + 1);
            cand = isSell ? MathMin(best, open) + TrailDistanceR * atr : MathMax(best, open) - TrailDistanceR * atr;
           }
         else
           {
            //--- level -/+ the SL buffer of the entry (+ the spread for a sell, stopped on the ask)
            double level = 0.0;
            int got = TrailLevel(isSell, lastClosed, m1, level);
            if(got <= 0)
               return (got == 0);
            double buf = Pts(SL_Buffer_Points) * PriceScale(open);
            cand = isSell ? level + buf + MathMax(0.0, ask - bid) : level - buf;
           }
        }
   return TrailApply(ticket, isSell, sl, tp, cand, 0.0, nowT);
  }

//--- R9: close this EA's positions opened before the end of the Friday of the most recent
//    WeekendCloseTime: on the first tick of the Friday window, or on the first tick after it when
//    that close was missed (EA or algo trading off, broker's Friday session ended earlier). A fill
//    stamped inside the Friday window is closed too (the entry block reads the terminal's estimate
//    of the server clock, the fill time is the server's). Positions opened after that Friday (a
//    Sunday session) are left alone. A failed close is retried at most once every
//    WEEKEND_RETRY_SEC seconds; the journal gets one line per episode.
void WeekendClosePositions()
  {
   if(!CloseBeforeWeekend)
      return;
   datetime now     = TimeTradeServer();
   datetime wkClose = LastWeekendCloseMoment(now);
   datetime wkEnd   = wkClose - (wkClose % 86400) + 86400;   // the Saturday 00:00 after it: a fill inside the Friday window is closed too
   bool     due     = false;
   for(int k = PositionsTotal() - 1; k >= 0; k--)
      if(g_pos.SelectByIndex(k) && g_pos.Symbol() == _Symbol && (ulong)g_pos.Magic() == MagicNumber &&
         g_pos.Time() < wkEnd)
         due = true;
   if(!due)
     {
      g_weekendLogged  = false;
      g_weekendFailLog = false;
      g_weekendLastTry = 0;
      return;
     }
   if(g_weekendLastTry > 0 && now >= g_weekendLastTry && now - g_weekendLastTry < WEEKEND_RETRY_SEC)
      return;                                  // throttle retries after a failed close
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i))
         continue;
      if(g_pos.Symbol() != _Symbol || (ulong)g_pos.Magic() != MagicNumber)
         continue;

      if(g_pos.Time() >= wkEnd)
         continue;                             // opened after that Friday (Sunday session, new week)

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
//    the reference backtest. While the M1 series is not available yet the check is repeated on
//    later ticks; clock time decides only once it is 4 hours past the limit.
bool MaxHoldReached(const datetime opened, const datetime now)
  {
   if((long)(now - opened) < (long)MaxHoldMinutes * 60)
      return false;                            // bars after the entry bar <= clock minutes
   datetime t[];
   int bars = CopyTime(_Symbol, PERIOD_M1, opened - (opened % 60), now, t);   // entry bar included
   if(bars <= 0)
      return ((long)(now - opened) >= (long)MaxHoldMinutes * 60 + 4 * 3600);
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
   if(TP_Mode == TP_PREV_HUMP)
      DrawLevel("TPref", g_sigTpRef, clrRoyalBlue, STYLE_DASH,
                StringFormat("LOMA %s: previous hump %s (TP reference)", SideName(g_sigSide), g_sigSide < 0 ? "low" : "high"));
   else
      if(!VisualsOff())
         ObjectDelete(0, OBJ_PREFIX + "TPref");  // fixed-R target: the previous hump is not the target
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
   string build = "Loma TrendPullback v1.35";

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
   if(TrailMode != TRAIL_RISK)
      sessTxt += "  |  trailing " + TrailModeText();
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
