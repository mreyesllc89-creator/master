//+------------------------------------------------------------------+
//|                     XAUUSD_M1_LiquidityZeroCross_Bearish.mq5     |
//|                                                                  |
//|  Strategy : XAUUSD M1 Liquidity Zero-Cross (BEARISH / SHORT ONLY)|
//|  Version  : 1.20                                                 |
//+------------------------------------------------------------------+
//
//  "No señal = no operación"  ->  no signal = no trade.
//
//  v1.20 (refined spec, Nov 2026; every new input defaults to v1.10 behaviour):
//    + HTF_Condition    : what counts as bearish on a trend timeframe: MACD<0 AND close<EMA
//                         (clearly bearish, default), OR, MACD only, EMA only
//    + UseHTF2 / HTF2_Timeframe / HTF_Combine : second trend timeframe (spec: "M15 and/or
//                         D1"), both or either must be bearish
//    + TP_Mode = TP_ZONE : liquidity zones ("blue rectangles"): swing lows within
//                         Zone_Tolerance_Points form a zone; TP sits TP_Buffer_Points above the
//                         zone top. Zone_MinTouches, Manual_Zone_Levels
//    + UseRSISoft       : RSI(12) "preferred, not mandatory": tag / RSIUnconfirmedRiskFactor
//    + chart: red line at the liquidity high, blue rectangle at the TP zone; panel shows the
//      live win rate (spec claims ~9 of 10 trades win under valid conditions)
//
//  v1.10 (calibration release, defaults keep v1.00 behaviour):
//    + TriggerTimeframe  : trigger/structure timeframe (default M1 = rules)
//    + TP_LookbackBars   : search the TP liquidity pool further back than the
//                          SL structure (0 = same as LiquidityLookbackBars)
//    + TP_FallbackRR     : fixed-RR target when no pool pays MinRewardRisk
//                          (0 = skip the trade, as in v1.00)
//    + MaxEntryDelaySeconds : only enter within N seconds of the bar open
//                          (0 = any tick of the signal bar, as in v1.00)
//    Strongest backtested edge: presets/XLZC_Bearish_M3_H1_NY.set
//    See research/ and presets/ for the backtest calibration.
//
//  OVERVIEW
//  --------
//  Short-only Expert Advisor for XAUUSD on M1. A short is opened only when
//  ALL mechanical conditions line up on CLOSED bars (no repainting):
//
//    R1  HTF bias (M15 default, or M5): MACD(12,26,9) main < 0 AND
//        close < EMA(50) on the last closed HTF bar.
//    R2  M1 trigger: MACD(12,26,9) main crosses the zero line DOWN
//        (bar[2] main >= 0 and bar[1] main < 0, bar[1] = last closed bar).
//    R3  Stochastic(7,1,7) on M1 coming from overbought (>= 80) and
//        turning down. SOFT filter by default (it tags / optionally
//        down-sizes the trade, it does not block it).
//    R4  Liquidity structure in the last N M1 bars:
//          SL  = above the most recent liquidity wick (a candle that swept
//                a prior swing high and closed back below it) or, if none,
//                the most recent swing high above price; + buffer (+ spread).
//          TP  = the next lower liquidity pool (nearest swing low below
//                price that still pays MinRewardRisk x the risk).
//        No usable structure -> no trade.
//    R5  Risk: RiskPercent of equity per trade, lot size from SL distance,
//        max ONE open position, spread filter, optional trailing (server
//        or hybrid/virtual) and optional partial close.
//    R6  Session filter (London/NY overlap by default) and optional
//        high-impact USD news filter (+/- 30 min, MT5 economic calendar).
//
//  MECHANICAL vs DISCRETIONARY
//  ---------------------------
//  Mechanical (implemented exactly, default ON):
//    R1 HTF bias, R2 M1 zero-cross trigger, R4 swing-based SL/TP,
//    R5 risk sizing / one position / spread, R6 session window.
//  Quality / soft filters (default ON but non-blocking):
//    R3 Stochastic confirmation (set StochHardBlock=true to make it hard).
//  Discretionary / partial elements (inputs, default OFF):
//    RSI(12) confluence, manual SL/TP override, HTF (M5/M15) liquidity
//    levels as TP candidates, partial close.
//  Not automated in v1:
//    visual order blocks / "blue rectangle" zones drawn by hand in the
//    source videos. DrawLiquidityZone() is the hook to add them later.
//
//  POINT UNITS
//  -----------
//  All *_Points inputs are written for a 2-digit XAUUSD quote
//  (1 point = 0.01, 10 points = 1 pip = 0.10). With AutoScalePoints=true
//  they are automatically multiplied by 10 on 3-digit gold feeds.
//
//  SUGGESTED PRESETS (also shipped as .set files in /presets)
//  -----------------
//  Conservative: RiskPercent=0.5, SL_Buffer_Points=50, MaxSpread_Points=25,
//    UseHTF_Filter=true, UseStochasticFilter=true, StochHardBlock=true,
//    LiquidityLookbackBars=25, SwingStrength=3, MinRewardRisk=1.5,
//    UseTradingHours=true 12:00-16:30 GMT, UseNewsFilter=true,
//    EnableTrailing=true (server) start 200 / distance 150 / step 20.
//  Aggressive:   RiskPercent=1.0, SL_Buffer_Points=30, MaxSpread_Points=35,
//    UseHTF_Filter=true, HTF=M5, UseStochasticFilter=true,
//    StochHardBlock=false, LiquidityLookbackBars=30, SwingStrength=2,
//    MinRewardRisk=1.0, UseTradingHours=true 07:00-20:00 GMT,
//    UseNewsFilter=true, EnableTrailing=true (hybrid) start 120 /
//    distance 100 / step 10, EnablePartialClose=true at 1R 50%.
//
//  KNOWN LIMITATIONS
//  -----------------
//  * Liquidity detection is simplified: fractal swing highs/lows and a
//    single "sweep" candle pattern over the last N bars. Hand-drawn
//    zones ("blue rectangles"), order blocks and equal-high/low clusters
//    from the source videos are NOT auto-detected in v1.
//  * The MT5 economic calendar is not available in the Strategy Tester:
//    the news filter is bypassed there (a warning is printed once).
//  * In the tester TimeGMT() equals server time; TesterGMTOffsetHours is
//    used to approximate GMT for the session filter when backtesting.
//  * Stochastic(7,1,7) notation is ambiguous between platforms. It is
//    mapped here as %K=7, Slowing=1, %D=7 (so the signal line can be
//    crossed). All three values are inputs.
//  * Long trades are never opened (strategy is bearish only).
//+------------------------------------------------------------------+
#property copyright   "mreyesllc89"
#property version     "1.20"
#ifdef XLZC_WITH_FGF
#property description "XAUUSD M1 Liquidity Zero-Cross Bearish (short-only) + FlashGold Direction Filter v1.2."
#property description "Shorts are only opened while the FlashGold filter allows sells."
#else
#property description "XAUUSD M1 Liquidity Zero-Cross Bearish (short-only)."
#property description "HTF MACD/EMA bias + M1 MACD zero-cross down + swing liquidity SL/TP."
#endif
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

enum ENUM_HTF_COND
  {
   HTF_MACD_AND_EMA = 0, // MACD < 0 AND close < EMA (clearly bearish)
   HTF_MACD_OR_EMA  = 1, // MACD < 0 OR close < EMA
   HTF_MACD_ONLY    = 2, // MACD < 0
   HTF_EMA_ONLY     = 3  // close < EMA
  };

enum ENUM_HTF_COMBINE
  {
   HTF_BOTH   = 0, // both trend timeframes bearish
   HTF_EITHER = 1  // at least one trend timeframe bearish
  };

enum ENUM_TP_MODE
  {
   TP_SWING_LOW = 0, // nearest swing low (v1.10)
   TP_ZONE      = 1  // nearest liquidity zone (cluster of swing lows), TP just above its top
  };

enum ENUM_TRAIL_MODE
  {
   TRAIL_SERVER = 0, // Server: modify the position SL
   TRAIL_HYBRID = 1  // Hybrid: hard SL stays, trailing level is virtual
  };

//====================================================================
// INPUTS
//====================================================================
input group "=== General ==="
input ulong   MagicNumber              = 20261107;     // Magic number
input string  TradeComment             = "XLZC_Bear";  // Order comment prefix
input bool    AutoScalePoints          = true;         // *_Points are 0.01 price steps on any quote (rescale other digits)
input bool    VerboseLog               = true;         // Print decision log to Experts tab
input bool    ShowLevels               = true;         // Draw SL/TP liquidity levels on chart
input bool    ShowStatusPanel          = true;         // Panel: signal/trend timeframes, last trigger bar, MACD
input bool    MarkSignals              = true;         // Arrow on the chart at every valid signal
input bool    ShowLiquidityLines       = true;         // Red line at the liquidity high, blue rectangle at the TP zone
input bool    SwitchChartToTriggerTF   = false;        // Switch this chart to the trigger timeframe (e.g. M3)

input group "=== R5: Risk & Position ==="
input double  RiskPercent              = 0.75;  // Risk per trade, % of equity (0.5-1.0)
input double  MaxLotSize               = 0.0;   // Max lot (0 = broker max)
input bool    SkipIfBelowMinLot        = true;  // Skip trade if risk lot < broker min lot
input int     MaxSpread_Points         = 30;    // Max spread (points)
input int     MaxSlippage_Points       = 20;    // Max slippage (points)
input int     MaxEntryDelaySeconds     = 0;     // Enter only within N s of bar open (0 = whole bar)

input group "=== R1: HTF Bias Filter ==="
input bool            UseHTF_Filter    = true;        // Require HTF bearish bias
input ENUM_TIMEFRAMES HTF_Timeframe    = PERIOD_M15;  // HTF (M15 or M5)
input int             HTF_EMA_Period   = 50;          // HTF EMA period
input ENUM_HTF_COND   HTF_Condition    = HTF_MACD_AND_EMA; // What counts as bearish (spec: MA and/or MACD)
input bool            UseHTF2          = false;       // v1.20: second trend timeframe (spec: M15 and/or D1)
input ENUM_TIMEFRAMES HTF2_Timeframe   = PERIOD_D1;   // Second trend timeframe
input ENUM_HTF_COMBINE HTF_Combine     = HTF_BOTH;    // Both timeframes bearish, or either

input group "=== R1/R2: MACD (HTF and trigger) ==="
input ENUM_TIMEFRAMES TriggerTimeframe = PERIOD_M1; // Trigger timeframe (M1 per rules)
input int     MACD_Fast                = 12;   // MACD fast EMA
input int     MACD_Slow                = 26;   // MACD slow EMA
input int     MACD_Signal              = 9;    // MACD signal SMA

input group "=== R3: Stochastic Confirmation (M1) ==="
input bool    UseStochasticFilter      = true;  // Evaluate Stochastic quality filter
input int     Stoch_K                  = 7;     // %K period
input int     Stoch_Slowing            = 1;     // Slowing
input int     Stoch_D                  = 7;     // %D (signal) period
input double  Stoch_OB_Level           = 80.0;  // Overbought level
input int     Stoch_LookbackBars       = 5;     // Bars to look back for overbought
input bool    StochHardBlock           = false; // true = block trade if not confirmed
input double  StochUnconfirmedRiskFactor = 1.0; // Risk multiplier if unconfirmed (soft mode)

input group "=== R4: Liquidity Structure ==="
input int     LiquidityLookbackBars    = 25;    // Lookback for swing/liquidity (M1 bars)
input int     SwingStrength            = 2;     // Bars each side to confirm a swing
input int     SL_Buffer_Points         = 40;    // SL buffer above liquidity high (points)
input bool    SL_AddSpread             = true;  // Add current spread to SL (short closes on Ask)
input bool    RequireLiquiditySweep    = false; // Require a sweep candle (else swing high is enough)
input int     TP_Buffer_Points         = 0;     // TP placed this far ABOVE the liquidity pool
input double  MinRewardRisk            = 1.0;   // Min reward:risk to accept a TP pool
input int     TP_LookbackBars          = 0;     // TP pool lookback (0 = LiquidityLookbackBars)
input ENUM_TP_MODE TP_Mode             = TP_SWING_LOW; // v1.20: TP at a swing low or at a liquidity zone ("blue rectangle")
input int     Zone_Tolerance_Points    = 100;   // Swing lows within this distance form one zone
input int     Zone_MinTouches          = 1;     // Lows a zone needs (2+ = only repeated lows)
input string  Manual_Zone_Levels       = "";    // Extra TP zone tops, e.g. "2650.5;2641" (empty = none)
input double  TP_FallbackRR            = 0.0;   // Fixed RR target if no pool qualifies (0 = skip trade)
input int     MinSL_Points             = 50;    // Min SL distance (points, sanity)
input int     MaxSL_Points             = 1000;  // Max SL distance (points, 0 = off)

input group "=== R5: Trade Management ==="
input bool            EnableTrailing          = false;        // Enable trailing stop
input ENUM_TRAIL_MODE TrailingMode            = TRAIL_SERVER; // Trailing mode
input int             TrailingStart_Points    = 150;          // Start trailing after X points profit
input int             TrailingDistance_Points = 100;          // Trailing distance from Ask
input int             TrailingStep_Points     = 20;           // Min SL improvement per step
input bool            EnablePartialClose      = false;        // Optional partial close
input double          PartialCloseAtR         = 1.0;          // Partial close at X * initial risk
input double          PartialClosePercent     = 50.0;         // % of volume to close
input bool            MoveSLToBreakevenAfterPartial = true;   // Move SL to entry after partial

input group "=== R6: Session / News ==="
input bool    UseTradingHours          = true;     // Restrict to trading hours
input bool    TradingHoursAreGMT       = true;     // Hours are GMT (false = server time)
input string  TradingHoursStart        = "12:00";  // Start HH:MM (London/NY overlap)
input string  TradingHoursEnd          = "16:30";  // End   HH:MM
input int     TesterGMTOffsetHours     = 2;        // Server GMT offset used in tester only
input bool    UseNewsFilter            = true;     // Skip around high-impact news
input string  NewsCurrency             = "USD";    // News currency
input int     NewsWindowMinutes        = 30;       // +/- minutes around the event

input group "=== Optional / Discretionary (default OFF) ==="
input bool    UseRSIFilter             = false; // RSI(12) confluence as a HARD filter
input bool    UseRSISoft               = false; // v1.20: RSI(12) confluence as a SOFT filter (spec: preferred, not mandatory)
input double  RSIUnconfirmedRiskFactor = 1.0;   // Soft mode: risk multiplier when RSI does not confirm
input int     RSI_Period               = 12;    // RSI period
input double  RSI_MaxLevel             = 50.0;  // Require RSI below this level
input bool    UseManualLevels          = false; // Manual SL/TP override
input double  ManualSL_Price           = 0.0;   // Manual SL price (0 = structural)
input double  ManualTP_Price           = 0.0;   // Manual TP price (0 = structural)
input bool    UseHTFLiquidityLevels    = false; // Add HTF swing lows as TP candidates
input int     HTFLiquidityLookbackBars = 30;    // HTF bars to scan for swing lows

#ifdef XLZC_WITH_FGF
//--- FlashGold Direction Filter v1.2 (FGF build only). The indicator must be
//    installed as MQL5/Indicators/FlashGold_Direction_Filter_v1_2.ex5; it is
//    loaded with its own default inputs (filter TF H1). Buffer 2 = "sell allowed".
input group "=== FlashGold Direction Filter (FGF build) ==="
input bool            UseFGF_Filter          = true;   // Only sell while FlashGold allows sells
input string          FGF_IndicatorName      = "FlashGold_Direction_Filter_v1_2"; // Path under MQL5/Indicators
input ENUM_TIMEFRAMES FGF_CalcTimeframe      = PERIOD_CURRENT; // Indicator chart TF (CURRENT = TriggerTimeframe)
input int             FGF_Shift              = 0;      // 0 = permission now (live bar), 1 = last closed bar
input bool            FGF_BlockIfUnavailable = true;   // No trade if the indicator has no data yet
//--- Indicator inputs. Used only when FGF_PassInputs=true; otherwise the indicator
//    runs with the defaults compiled into it (same values as below).
input bool            FGF_PassInputs         = false;  // Pass the inputs below to the indicator
input ENUM_TIMEFRAMES FGF_FilterTF           = PERIOD_H1; // fgfTf: filter timeframe
input ENUM_TIMEFRAMES FGF_ParentTF           = PERIOD_H1; // fgfParentTf: parent obedience timeframe
input int             FGF_LevelMode          = 0;      // fgfLvMode: 0 entry price, 1 signal close
input int             FGF_Window             = 0;      // fgfLast: 0 next signal, 1 minutes, 2 candles
input int             FGF_Minutes            = 60;     // fgfMinutes
input int             FGF_Candles            = 1;      // fgfBars
input int             FGF_CheckMode          = 0;      // fgfCheck: 0 tick, 1 open, 2 bar close
input double          FGF_BandAtr            = 0.25;   // fgfBandAtr: no-trade band, ATR mult
input bool            FGF_Against            = true;   // fgfAgainst: allow trading against the signal
input int             FGF_HoldBars           = 0;      // fgfHoldBars
input double          FGF_BurstAtr           = 0.5;    // fgfBurstAtr
input bool            FGF_AnyCombo           = false;  // fgfAnyCombo
input bool            FGF_UseZones           = true;   // fgfUseZones
input int             FGF_MinAligned         = 2;      // fgfMinAligned
#endif

//====================================================================
// GLOBALS
//====================================================================
CTrade        g_trade;
CPositionInfo g_pos;

int      g_hMacdM1   = INVALID_HANDLE;
int      g_hMacdHTF  = INVALID_HANDLE;
int      g_hEmaHTF   = INVALID_HANDLE;
int      g_hStochM1  = INVALID_HANDLE;
int      g_hRsiM1    = INVALID_HANDLE;
int      g_hMacdHTF2 = INVALID_HANDLE;   // v1.20 second trend timeframe
int      g_hEmaHTF2  = INVALID_HANDLE;
int      g_hFGF      = INVALID_HANDLE;   // FlashGold filter (FGF build only)

double   g_ptScale        = 1.0;   // point scale factor (AutoScalePoints)
int      g_sessStartMin   = 0;
int      g_sessEndMin     = 0;

datetime g_lastBarTime    = 0;     // last processed M1 bar (bar-based logic)
datetime g_signalBarTime  = 0;     // bar on which a valid signal is active
bool     g_signalActive   = false;
datetime g_lastTradeBar   = 0;     // bar on which we last opened a trade
double   g_riskFactor     = 1.0;   // from soft Stochastic filter
string   g_signalTag      = "";

datetime g_newsCheckTime  = 0;
bool     g_newsBlocked    = false;
bool     g_newsWarned     = false;
string   g_lastSkipReason = "";

bool     g_quietLog       = false;   // suppress Log() inside HTFBiasState for the panel
const string OBJ_PREFIX   = "XLZC_";

//--- trade plan built from the liquidity structure (R4)
struct TradePlan
  {
   double entry;      // Bid at planning time
   double sl;         // final SL price
   double tp;         // final TP price
   double slRef;      // liquidity high used for SL
   double tpRef;      // liquidity pool used for TP (zone top in zone mode)
   double tpZoneLow;  // zone bottom (zone mode), else = tpRef
   datetime slRefTime;
   datetime tpRefTime;
   string slSource;
   string tpSource;
  };

//====================================================================
// HELPERS
//====================================================================
void Log(const string msg)
  {
   if(VerboseLog)
      Print("[XLZC] ", msg);
  }

//--- log a "no trade" reason only when it changes (avoid per-tick spam)
void LogSkip(const string reason)
  {
   if(reason == g_lastSkipReason)
      return;
   g_lastSkipReason = reason;
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
   if(CopyBuffer(handle, buffer, shift, 1, tmp) != 1)
      return false;
   value = tmp[0];
   return true;
  }

//====================================================================
// OnInit
//====================================================================
int OnInit()
  {
   //--- sanity checks on inputs
   if(RiskPercent <= 0.0 || RiskPercent > 5.0)
     {
      Print("[XLZC] RiskPercent must be in (0, 5]. Got ", RiskPercent);
      return INIT_PARAMETERS_INCORRECT;
     }
   if(SwingStrength < 1 || LiquidityLookbackBars < 2 * SwingStrength + 3)
     {
      Print("[XLZC] LiquidityLookbackBars must be >= 2*SwingStrength+3");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(MACD_Fast >= MACD_Slow)
     {
      Print("[XLZC] MACD_Fast must be < MACD_Slow");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(UseTradingHours)
     {
      if(!ParseHHMM(TradingHoursStart, g_sessStartMin) || !ParseHHMM(TradingHoursEnd, g_sessEndMin))
        {
         Print("[XLZC] TradingHoursStart/End must be HH:MM");
         return INIT_PARAMETERS_INCORRECT;
        }
     }
   if(HTF_Timeframe != PERIOD_M5 && HTF_Timeframe != PERIOD_M15)
      Print("[XLZC] Warning: strategy rules specify M5 or M15 for the HTF bias; using ",
            EnumToString(HTF_Timeframe));
   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0 && StringFind(_Symbol, "BTC") < 0)
      Print("[XLZC] Warning: EA calibrated for XAUUSD and BTCUSD, attached to ", _Symbol);
   if(TriggerTimeframe != PERIOD_M1)
      Print("[XLZC] Note: trigger timeframe ", EnumToString(TriggerTimeframe),
            " differs from the M1 rule (calibration option).");
   if(TriggerTimeframe >= HTF_Timeframe)
     {
      Print("[XLZC] TriggerTimeframe must be lower than HTF_Timeframe");
      return INIT_PARAMETERS_INCORRECT;
     }

   //--- point scaling: inputs are written for 2-digit gold (0.01 point)
   //    i.e. every *_Points input is a 0.01 price step. Other quotes are rescaled:
   //    3 digits -> x10, 1 digit (e.g. some BTCUSD feeds) -> x0.1, 0 digits -> x0.01.
   g_ptScale = 1.0;
   if(AutoScalePoints && _Digits != 2)
      g_ptScale = MathPow(10.0, _Digits - 2);

   //--- indicator handles
   g_hMacdM1  = iMACD(_Symbol, TriggerTimeframe, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   g_hMacdHTF = iMACD(_Symbol, HTF_Timeframe, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   g_hEmaHTF  = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_hStochM1 = iStochastic(_Symbol, TriggerTimeframe, Stoch_K, Stoch_D, Stoch_Slowing, MODE_SMA, STO_LOWHIGH);
   if(UseRSIFilter || UseRSISoft)
      g_hRsiM1 = iRSI(_Symbol, TriggerTimeframe, RSI_Period, PRICE_CLOSE);
   if(UseHTF_Filter && UseHTF2)
     {
      g_hMacdHTF2 = iMACD(_Symbol, HTF2_Timeframe, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
      g_hEmaHTF2  = iMA(_Symbol, HTF2_Timeframe, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hMacdHTF2 == INVALID_HANDLE || g_hEmaHTF2 == INVALID_HANDLE)
        {
         Print("[XLZC] Failed to create the second trend timeframe handles, error ", GetLastError());
         return INIT_FAILED;
        }
     }

   if(g_hMacdM1 == INVALID_HANDLE || g_hMacdHTF == INVALID_HANDLE ||
      g_hEmaHTF == INVALID_HANDLE || g_hStochM1 == INVALID_HANDLE ||
      ((UseRSIFilter || UseRSISoft) && g_hRsiM1 == INVALID_HANDLE))
     {
      Print("[XLZC] Failed to create indicator handles, error ", GetLastError());
      return INIT_FAILED;
     }

#ifdef XLZC_WITH_FGF
   if(UseFGF_Filter)
     {
      ENUM_TIMEFRAMES fgfTf = (FGF_CalcTimeframe == PERIOD_CURRENT) ? TriggerTimeframe : FGF_CalcTimeframe;
      if(!FGF_PassInputs)
         g_hFGF = iCustom(_Symbol, fgfTf, FGF_IndicatorName);   // indicator defaults
      else
         //--- all 53 inputs, in the indicator's declaration order (input groups are
         //    not parameters). Display inputs are off: the handle is not drawn.
         g_hFGF = iCustom(_Symbol, fgfTf, FGF_IndicatorName,
                          true, FGF_FilterTF, FGF_LevelMode, FGF_Window, FGF_Minutes, FGF_Candles,
                          FGF_CheckMode, FGF_BandAtr, FGF_Against, true, true,
                          false, false, false, false, 0,                 // shade, level, marks, box, box pos
                          false, 500, 10,                                // direction score
                          25.0, 50.0, FGF_HoldBars, 5.0, true,           // spread, entry dist, hold, hold fav, one/bar
                          0, FGF_BurstAtr, 0.25, 0.1, 172.0,             // unit ATR, burst, entry dist, hold fav, burst pts
                          true, FGF_AnyCombo, 60, false,                 // use burst, any combo, drift bars, use drift
                          FGF_UseZones, FGF_ParentTF, 14, 2, FGF_MinAligned, false, true, true,
                          true, PERIOD_H1, true, PERIOD_H2, true, PERIOD_H4,
                          false, PERIOD_H8, false, PERIOD_M1, false, PERIOD_M2);
      if(g_hFGF == INVALID_HANDLE)
        {
         Print("[XLZC] Cannot load FlashGold indicator '", FGF_IndicatorName,
               "' (install it in MQL5/Indicators). Error ", GetLastError());
         return INIT_FAILED;
        }
     }
#endif

   //--- trade object
   g_trade.SetExpertMagicNumber(MagicNumber);
   g_trade.SetDeviationInPoints((ulong)MathMax(0.0, MaxSlippage_Points * g_ptScale));
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.LogLevel(LOG_LEVEL_ERRORS);

   Print(StringFormat("[XLZC] Signals are computed on %s bars (TriggerTimeframe) with the %s trend filter "
                      "(HTF_Timeframe). This chart is %s: the chart timeframe does not change the signals.",
                      TFName(TriggerTimeframe), TFName(HTF_Timeframe), TFName((ENUM_TIMEFRAMES)_Period)));
   if(SwitchChartToTriggerTF && !MQLInfoInteger(MQL_TESTER) && _Period != TriggerTimeframe)
     {
      Print("[XLZC] Switching this chart to ", TFName(TriggerTimeframe), " (SwitchChartToTriggerTF=true)");
      ChartSetSymbolPeriod(0, _Symbol, TriggerTimeframe);   // the EA restarts on the new timeframe
     }
   UpdatePanel();
   Log(StringFormat("Init OK on %s | digits=%d pointScale=%.0f | HTF=%s | risk=%.2f%%",
                    _Symbol, _Digits, g_ptScale, EnumToString(HTF_Timeframe), RiskPercent));
   return INIT_SUCCEEDED;
  }

//====================================================================
// OnDeinit - release handles and chart objects
//====================================================================
void OnDeinit(const int reason)
  {
   if(g_hMacdM1  != INVALID_HANDLE) IndicatorRelease(g_hMacdM1);
   if(g_hMacdHTF != INVALID_HANDLE) IndicatorRelease(g_hMacdHTF);
   if(g_hEmaHTF  != INVALID_HANDLE) IndicatorRelease(g_hEmaHTF);
   if(g_hStochM1 != INVALID_HANDLE) IndicatorRelease(g_hStochM1);
   if(g_hRsiM1   != INVALID_HANDLE) IndicatorRelease(g_hRsiM1);
   if(g_hMacdHTF2 != INVALID_HANDLE) IndicatorRelease(g_hMacdHTF2);
   if(g_hEmaHTF2  != INVALID_HANDLE) IndicatorRelease(g_hEmaHTF2);
   if(g_hFGF     != INVALID_HANDLE) IndicatorRelease(g_hFGF);
   ObjectsDeleteAll(0, OBJ_PREFIX);
   Comment("");
  }

//====================================================================
// OnTick
//====================================================================
void OnTick()
  {
   //--- always manage what is already open (R5 trailing / partial)
   ManageOpenPositions();

   //--- refresh the status panel about once a minute (spread, session, bias)
   static datetime lastPanel = 0;
   if(TimeCurrent() - lastPanel >= 60)
     {
      lastPanel = TimeCurrent();
      UpdatePanel();
     }

   //--- bar-based signal evaluation: once per new M1 bar, on CLOSED bars
   datetime barTime = iTime(_Symbol, TriggerTimeframe, 0);
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
      if(g_signalActive && MarkSignals)
         MarkSignal(barTime);
      UpdatePanel();
     }

   //--- a signal is valid only during the bar right after the cross
   if(!g_signalActive || g_signalBarTime != barTime)
      return;
   if(g_lastTradeBar == barTime)
      return;
   //--- v1.10: optional entry window (the calibration backtest enters at bar open)
   if(MaxEntryDelaySeconds > 0 && TimeCurrent() - barTime > MaxEntryDelaySeconds)
     {
      LogSkip("entry window after bar open has passed");
      g_signalActive = false;
      return;
     }

   //--- per-tick execution filters (re-checked until the bar ends)
   if(CountOwnPositions() > 0)                 // R5: max one open position
     {
      LogSkip("a position is already open (max 1)");
      return;
     }
   if(!SpreadOK())                             // R5: spread filter
      return;
   if(!SessionOK())                            // R6: trading hours
     {
      LogSkip("outside trading hours");
      return;
     }
   if(NewsBlocked())                           // R6: news filter
     {
      LogSkip("high-impact news window");
      return;
     }
   if(!TradingAllowed())
      return;
#ifdef XLZC_WITH_FGF
   if(!FGFAllowsSell())                        // FlashGold direction filter
      return;
#endif

   if(TryOpenShort())
     {
      g_lastTradeBar = barTime;
      g_signalActive = false;
     }
  }

//====================================================================
// OnTrade - clean up per-ticket state of positions that are closed
//====================================================================
void OnTrade()
  {
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string name   = GlobalVariableName(i);
      string prefix = OBJ_PREFIX + (string)MagicNumber + "_";
      if(StringFind(name, prefix) != 0)
         continue;
      int    pos    = StringFind(name, "_", StringLen(prefix) + 1);
      if(pos < 0)
         continue;
      ulong  ticket = (ulong)StringToInteger(StringSubstr(name, pos + 1));
      if(ticket > 0 && !PositionSelectByTicket(ticket))
         GlobalVariableDel(name);
     }
  }

//====================================================================
// SIGNAL (R1, R2, R3, optional RSI) - evaluated on closed bars only
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
   return (bars > MACD_Slow + MACD_Signal + 3 && BarsCalculated(handle) >= bars);
  }

//--- all data the signal reads is current for the trigger bar opening at barTime
bool SignalDataReady(const datetime barTime)
  {
   if(!HandleReady(g_hMacdM1, TriggerTimeframe) || !HandleReady(g_hStochM1, TriggerTimeframe))
      return false;
   if((UseRSIFilter || UseRSISoft) && !HandleReady(g_hRsiM1, TriggerTimeframe))
      return false;
   if(UseHTF_Filter)
     {
      if(!HandleReady(g_hMacdHTF, HTF_Timeframe) || !HandleReady(g_hEmaHTF, HTF_Timeframe))
         return false;
      //--- the HTF series must already contain the HTF bar that holds barTime,
      //    otherwise "shift 1" would still be the HTF bar before the last closed one
      datetime htf0 = iTime(_Symbol, HTF_Timeframe, 0);
      if(htf0 == 0 || barTime < htf0 || barTime >= htf0 + PeriodSeconds(HTF_Timeframe))
         return false;
      if(UseHTF2)
        {
         if(!HandleReady(g_hMacdHTF2, HTF2_Timeframe) || !HandleReady(g_hEmaHTF2, HTF2_Timeframe))
            return false;
         datetime h2 = iTime(_Symbol, HTF2_Timeframe, 0);
         if(h2 == 0 || barTime < h2)
            return false;   // the bar holding barTime is not in the series yet (D1 may start later than a session)
        }
     }
   return true;
  }

int EvaluateSignal(const datetime barTime)
  {
   if(!SignalDataReady(barTime))
      return SIG_NOTREADY;

   //--- R2: M1 MACD main line zero-cross DOWN, bar-based (no repaint)
   //    bar[2] main >= 0  and  bar[1] main < 0   (bar[1] = last closed)
   double macd[];
   ArraySetAsSeries(macd, true);
   if(CopyBuffer(g_hMacdM1, 0, 1, 2, macd) != 2)
      return SIG_NOTREADY;
   bool zeroCrossDown = (macd[1] >= 0.0 && macd[0] < 0.0);
   if(!zeroCrossDown)
      return SIG_NONE;   // No señal = no operación
   Log(StringFormat("R2 trigger: M1 MACD zero-cross down (%.3f -> %.3f)", macd[1], macd[0]));

   //--- R1: HTF bias - MACD main < 0 AND close < EMA(50), last closed HTF bar
   if(UseHTF_Filter)
     {
      int bias = HTFBiasState();
      if(bias != SIG_VALID)
         return bias;
     }

   //--- optional: RSI(12) confluence. Hard = block, soft = tag / smaller risk (spec: preferred)
   double rsiFactor = 1.0;
   string rsiTag    = "";
   if(UseRSIFilter || UseRSISoft)
     {
      double rsi;
      if(!CopyOne(g_hRsiM1, 0, 1, rsi))
         return SIG_NOTREADY;
      bool rsiOK = (rsi < RSI_MaxLevel);
      if(!rsiOK && UseRSIFilter)
        {
         Log(StringFormat("RSI filter: RSI=%.1f >= %.1f -> skip", rsi, RSI_MaxLevel));
         return SIG_NONE;
        }
      rsiTag = rsiOK ? " RSI+" : " RSI-";
      if(!rsiOK)
         rsiFactor = MathMax(0.0, MathMin(1.0, RSIUnconfirmedRiskFactor));
     }

   //--- R3: Stochastic quality filter (soft by default)
   g_riskFactor = rsiFactor;
   g_signalTag  = "";
   if(UseStochasticFilter)
     {
      bool stochOK = StochasticConfirmed();
      g_signalTag  = stochOK ? "STO+" : "STO-";
      if(!stochOK)
        {
         if(StochHardBlock)
           {
            Log("R3 Stochastic not confirmed and StochHardBlock=true -> skip");
            return SIG_NONE;
           }
         g_riskFactor *= MathMax(0.0, MathMin(1.0, StochUnconfirmedRiskFactor));
         Log(StringFormat("R3 Stochastic not confirmed (soft) -> risk factor %.2f", g_riskFactor));
        }
     }

   g_signalTag += rsiTag;
   Log("Signal VALID on bar " + TimeToString(barTime) + " " + g_signalTag);
   return SIG_VALID;
  }

//--- R1: one trend timeframe -> SIG_VALID (bearish) / SIG_NONE / SIG_NOTREADY
int TFBearState(const int hMacd, const int hEma, const ENUM_TIMEFRAMES tf)
  {
   double m, e;
   if(!CopyOne(hMacd, 0, 1, m) || !CopyOne(hEma, 0, 1, e))
      return SIG_NOTREADY;
   double c = iClose(_Symbol, tf, 1);
   bool macdBear = (m < 0.0);
   bool belowEma = (c > 0.0 && c < e);
   bool bear;
   switch(HTF_Condition)
     {
      case HTF_MACD_OR_EMA: bear = macdBear || belowEma; break;
      case HTF_MACD_ONLY:   bear = macdBear;             break;
      case HTF_EMA_ONLY:    bear = belowEma;             break;
      default:              bear = macdBear && belowEma; break;
     }
   if(!bear && !g_quietLog)
      Log(StringFormat("R1 %s not bearish: MACD=%.3f (<0? %s) close=%.2f EMA=%.2f (below? %s)", TFName(tf),
                       m, macdBear ? "yes" : "no", c, e, belowEma ? "yes" : "no"));
   return bear ? SIG_VALID : SIG_NONE;
  }

//--- R1: HTF bearish bias over one or two trend timeframes
int HTFBiasState()
  {
   int s1 = TFBearState(g_hMacdHTF, g_hEmaHTF, HTF_Timeframe);
   if(!UseHTF2)
      return s1;
   int s2 = TFBearState(g_hMacdHTF2, g_hEmaHTF2, HTF2_Timeframe);
   if(s1 == SIG_NOTREADY || s2 == SIG_NOTREADY)
      return SIG_NOTREADY;
   bool b1 = (s1 == SIG_VALID), b2 = (s2 == SIG_VALID);
   return (HTF_Combine == HTF_EITHER ? (b1 || b2) : (b1 && b2)) ? SIG_VALID : SIG_NONE;
  }

//--- R3: Stochastic came from overbought and is turning/turned down
bool StochasticConfirmed()
  {
   int n = MathMax(1, Stoch_LookbackBars);
   double mainB[], sigB[];
   ArraySetAsSeries(mainB, true);
   ArraySetAsSeries(sigB, true);
   if(CopyBuffer(g_hStochM1, 0, 1, n, mainB) != n || CopyBuffer(g_hStochM1, 1, 1, n, sigB) != n)
      return false;

   bool wasOverbought = false;
   for(int i = 0; i < n; i++)
      if(mainB[i] >= Stoch_OB_Level)
        {
         wasOverbought = true;
         break;
        }
   bool turnedDown = (mainB[0] < sigB[0] || mainB[0] < Stoch_OB_Level);
   return (wasOverbought && turnedDown);
  }

//====================================================================
// LIQUIDITY STRUCTURE (R4)
//====================================================================
bool IsSwingHigh(const MqlRates &r[], const int i, const int s)
  {
   for(int k = 1; k <= s; k++)
     {
      if(r[i - k].high >= r[i].high) return false; // newer bars
      if(r[i + k].high >  r[i].high) return false; // older bars
     }
   return true;
  }

bool IsSwingLow(const MqlRates &r[], const int i, const int s)
  {
   for(int k = 1; k <= s; k++)
     {
      if(r[i - k].low <= r[i].low) return false;
      if(r[i + k].low <  r[i].low) return false;
     }
   return true;
  }

//--- build SL/TP from the last N bars. Returns false (with reason) if no
//    clear liquidity structure exists -> the trade is skipped.
bool BuildTradePlan(TradePlan &p, string &reason)
  {
   int N    = LiquidityLookbackBars;
   int S    = SwingStrength;
   int NT   = (TP_LookbackBars > 0) ? TP_LookbackBars : N;   // TP pool lookback
   int need = MathMax(N, NT) + S + 1;

   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, TriggerTimeframe, 0, need, r) != need)
     {
      reason = "not enough trigger-timeframe history";
      return false;
     }

   double bid    = Bid();
   double ask    = Ask();
   p.entry       = bid;
   p.slRef       = 0.0;
   p.tpRef       = 0.0;
   p.slRefTime   = 0;
   p.tpRefTime   = 0;
   p.slSource    = "";
   p.tpSource    = "";
   p.tpZoneLow   = 0.0;

   //--- (a) liquidity candle: most recent bar j that swept an older swing
   //        high (high above it) and closed back below it
   int sweepBar = -1;
   for(int j = 1; j <= N && sweepBar < 0; j++)
      for(int i = j + S + 1; i <= N && i + S < need; i++)
        {
         if(!IsSwingHigh(r, i, S))
            continue;
         if(r[j].high > r[i].high && r[j].close < r[i].high)
           {
            sweepBar = j;
            break;
           }
        }

   int structBar = -1;
   if(sweepBar > 0 && r[sweepBar].high > bid)
     {
      structBar  = sweepBar;
      p.slSource = "sweep";
     }
   else
     {
      if(RequireLiquiditySweep)
        {
         reason = "no liquidity sweep candle in lookback";
         return false;
        }
      //--- (b) most recent confirmed swing high above price
      for(int i = 1 + S; i <= N && i + S < need; i++)
         if(IsSwingHigh(r, i, S) && r[i].high > bid)
           {
            structBar  = i;
            p.slSource = "swingHigh";
            break;
           }
     }

   if(structBar < 0)
     {
      reason = "no liquidity high above price in last " + (string)N + " bars";
      return false;
     }

   //--- SL reference = the structural high, or any higher high printed since
   //    (the most recent significant high must stay protected)
   double slRef = r[structBar].high;
   for(int k = 0; k < structBar; k++)
      slRef = MathMax(slRef, r[k].high);
   p.slRef     = slRef;
   p.slRefTime = r[structBar].time;

   double sl = slRef + Pts(SL_Buffer_Points);
   if(SL_AddSpread)
      sl += (ask - bid);
   p.sl = NormalizePrice(sl);

   //--- optional: manual SL override (discretionary, default OFF). Applied
   //    BEFORE the TP search so MinRewardRisk / TP_FallbackRR use the final risk.
   if(UseManualLevels && ManualSL_Price > p.entry)
     {
      p.sl = NormalizePrice(ManualSL_Price);
      p.slSource = "manual";
     }
   double risk = p.sl - p.entry;

   //--- TP: next lower liquidity pool (nearest swing low that pays MinRR)
   double   lows[];
   datetime lowTimes[];
   string   lowSrc[];
   int      cnt = 0;
   for(int i = 1 + S; i <= NT && i + S < need; i++)
      if(IsSwingLow(r, i, S) && r[i].low < bid)
        {
         ArrayResize(lows, cnt + 1);
         ArrayResize(lowTimes, cnt + 1);
         ArrayResize(lowSrc, cnt + 1);
         lows[cnt] = r[i].low; lowTimes[cnt] = r[i].time; lowSrc[cnt] = "swingLow";
         cnt++;
        }

   //--- optional: HTF liquidity levels (discretionary, default OFF)
   if(UseHTFLiquidityLevels)
     {
      int hn = HTFLiquidityLookbackBars + S + 1;
      MqlRates h[];
      ArraySetAsSeries(h, true);
      if(CopyRates(_Symbol, HTF_Timeframe, 0, hn, h) == hn)
         for(int i = 1 + S; i + S < hn; i++)
            if(IsSwingLow(h, i, S) && h[i].low < bid)
              {
               ArrayResize(lows, cnt + 1);
               ArrayResize(lowTimes, cnt + 1);
               ArrayResize(lowSrc, cnt + 1);
               lows[cnt] = h[i].low; lowTimes[cnt] = h[i].time;
               lowSrc[cnt] = EnumToString(HTF_Timeframe) + " swingLow";
               cnt++;
              }
     }

   //--- v1.20: liquidity ZONES ("blue rectangles"). Swing lows within Zone_Tolerance_Points
   //    of each other form one zone [bottom, top]; zones with fewer than Zone_MinTouches lows
   //    are dropped. Manual levels are added as one-price zones. The TP then sits
   //    TP_Buffer_Points above the zone TOP, i.e. just before price reaches the zone.
   double zoneLow[];
   ArrayResize(zoneLow, cnt);
   for(int i = 0; i < cnt; i++)
      zoneLow[i] = lows[i];
   if(TP_Mode == TP_ZONE)
     {
      //--- sort candidates by price, highest first (insertion sort; a few dozen items)
      for(int i = 1; i < cnt; i++)
        {
         double lv = lows[i]; datetime lt = lowTimes[i]; string ls = lowSrc[i];
         int j = i - 1;
         while(j >= 0 && lows[j] < lv)
           {
            lows[j + 1] = lows[j]; lowTimes[j + 1] = lowTimes[j]; lowSrc[j + 1] = lowSrc[j];
            j--;
           }
         lows[j + 1] = lv; lowTimes[j + 1] = lt; lowSrc[j + 1] = ls;
        }
      double   zTop[], zBot[];
      datetime zTime[];
      int      zN[];
      int      zc = 0;
      double   tol = Pts(Zone_Tolerance_Points);
      for(int i = 0; i < cnt; i++)
        {
         if(zc > 0 && zBot[zc - 1] - lows[i] <= tol)
           {
            zBot[zc - 1] = lows[i];                      // extend the zone downwards
            zN[zc - 1]++;
            zTime[zc - 1] = MathMin(zTime[zc - 1], lowTimes[i]);
            continue;
           }
         ArrayResize(zTop, zc + 1); ArrayResize(zBot, zc + 1); ArrayResize(zTime, zc + 1); ArrayResize(zN, zc + 1);
         zTop[zc] = lows[i]; zBot[zc] = lows[i]; zTime[zc] = lowTimes[i]; zN[zc] = 1;
         zc++;
        }
      //--- manual zone tops
      string parts[];
      int np = (StringLen(Manual_Zone_Levels) > 0) ? StringSplit(Manual_Zone_Levels, ';', parts) : 0;
      int keep = 0;
      cnt = 0;
      ArrayResize(lows, 0); ArrayResize(lowTimes, 0); ArrayResize(lowSrc, 0); ArrayResize(zoneLow, 0);
      for(int z = 0; z < zc; z++)
        {
         if(zN[z] < MathMax(1, Zone_MinTouches))
            continue;
         ArrayResize(lows, cnt + 1); ArrayResize(lowTimes, cnt + 1); ArrayResize(lowSrc, cnt + 1); ArrayResize(zoneLow, cnt + 1);
         lows[cnt] = zTop[z]; zoneLow[cnt] = zBot[z]; lowTimes[cnt] = zTime[z];
         lowSrc[cnt] = StringFormat("zone x%d", zN[z]);
         cnt++;
        }
      for(int k = 0; k < np; k++)
        {
         double lv = StringToDouble(parts[k]);
         if(lv <= 0.0 || lv >= bid)
            continue;
         ArrayResize(lows, cnt + 1); ArrayResize(lowTimes, cnt + 1); ArrayResize(lowSrc, cnt + 1); ArrayResize(zoneLow, cnt + 1);
         lows[cnt] = lv; zoneLow[cnt] = lv; lowTimes[cnt] = r[MathMin(NT, need - 1)].time; lowSrc[cnt] = "manual zone";
         cnt++;
        }
     }

   //--- pick the nearest pool below price (highest low first) that gives >= MinRR
   bool   found  = false;
   bool   used[];
   ArrayResize(used, cnt);
   ArrayInitialize(used, false);
   double minDist = StopsLevelDistance();
   for(int pass = 0; pass < cnt && !found; pass++)
     {
      int best = -1;
      for(int i = 0; i < cnt; i++)
         if(!used[i] && (best < 0 || lows[i] > lows[best]))
            best = i;
      if(best < 0)
         break;
      used[best] = true;

      double tp     = NormalizePrice(lows[best] + Pts(TP_Buffer_Points));
      double reward = p.entry - tp;
      if(reward <= minDist || reward <= 0.0)
         continue;
      if(MinRewardRisk > 0.0 && reward < MinRewardRisk * risk)
         continue;
      p.tp        = tp;
      p.tpRef     = lows[best];
      p.tpZoneLow = zoneLow[best];
      p.tpRefTime = lowTimes[best];
      p.tpSource  = lowSrc[best];
      found       = true;
     }

   //--- v1.1: fixed-RR fallback when no liquidity pool pays MinRewardRisk
   if(!found && TP_FallbackRR > 0.0)
     {
      double tp = NormalizePrice(p.entry - TP_FallbackRR * risk);
      if(p.entry - tp > minDist)
        {
         p.tp        = tp;
         p.tpRef     = tp;
         p.tpRefTime = 0;
         p.tpSource  = StringFormat("fixed %.1fR", TP_FallbackRR);
         found       = true;
        }
     }

   //--- optional: manual TP override (discretionary, default OFF)
   if(UseManualLevels)
     {
      if(ManualTP_Price > 0.0 && ManualTP_Price < p.entry)
        {
         p.tp = NormalizePrice(ManualTP_Price);
         p.tpSource = "manual";
         found = true;
        }
     }

   if(!found)
     {
      reason = StringFormat("no lower liquidity pool with RR >= %.2f (%d candidates)", MinRewardRisk, cnt);
      return false;
     }

   //--- SL distance sanity (points are in 2-digit gold units)
   double riskPts = risk / (_Point * g_ptScale);
   if(risk <= minDist)
     {
      reason = "SL inside broker stops level";
      return false;
     }
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
   return true;
  }

//====================================================================
// RISK / LOT SIZE (R5)
//====================================================================
double CalcLots(const double entry, const double sl, const double riskFactor)
  {
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * RiskPercent / 100.0 * riskFactor;
   if(riskMoney <= 0.0)
      return 0.0;

   //--- money lost per 1.0 lot if SL is hit
   double lossPerLot = 0.0;
   if(!OrderCalcProfit(ORDER_TYPE_SELL, _Symbol, 1.0, entry, sl, lossPerLot) || lossPerLot == 0.0)
     {
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tickValue <= 0.0)
         tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      if(tickSize <= 0.0 || tickValue <= 0.0)
         return 0.0;
      lossPerLot = (sl - entry) / tickSize * tickValue;
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
      if(!OrderCalcMargin(ORDER_TYPE_SELL, _Symbol, lots, entry, margin))
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

bool TryOpenShort()
  {
   const int maxAttempts = 3;
   for(int attempt = 1; attempt <= maxAttempts; attempt++)
     {
      //--- R4: liquidity structure (rebuilt each attempt with fresh prices)
      TradePlan plan;
      string    reason = "";
      if(!BuildTradePlan(plan, reason))
        {
         LogSkip(reason);
         g_signalActive = false;   // decided once per signal, as in the backtest
         return false;
        }

      //--- R5: position size from SL distance
      double lots = CalcLots(plan.entry, plan.sl, g_riskFactor);
      if(lots <= 0.0)
        {
         g_signalActive = false;
         return false;
        }

      string comment = TradeComment + (g_signalTag != "" ? " " + g_signalTag : "");
      Log(StringFormat("SELL %.2f @%.2f SL=%.2f (%s %.2f) TP=%.2f (%s %.2f) RR=%.2f",
                       lots, plan.entry, plan.sl, plan.slSource, plan.slRef,
                       plan.tp, plan.tpSource, plan.tpRef,
                       (plan.entry - plan.tp) / MathMax(_Point, plan.sl - plan.entry)));

      ResetLastError();
      bool   sent = g_trade.Sell(lots, _Symbol, 0.0, plan.sl, plan.tp, comment);
      uint   rc   = g_trade.ResultRetcode();
      if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
        {
         Log(StringFormat("Order filled: deal #%I64u price %.2f", g_trade.ResultDeal(), g_trade.ResultPrice()));
         if(ShowLevels)
            DrawPlan(plan);
         return true;
        }

      Print(StringFormat("[XLZC] OrderSend failed (attempt %d/%d): retcode=%u (%s) lastError=%d",
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

int CountOwnPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(g_pos.SelectByIndex(i) && g_pos.Symbol() == _Symbol && (ulong)g_pos.Magic() == MagicNumber)
         n++;
   return n;
  }

//====================================================================
// FILTERS (R5 spread, R6 session/news)
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

datetime CurrentGMT()
  {
   if(MQLInfoInteger(MQL_TESTER))
      return TimeTradeServer() - TesterGMTOffsetHours * 3600;
   return TimeGMT();
  }

bool SessionOK()
  {
   if(!UseTradingHours)
      return true;
   datetime t = TradingHoursAreGMT ? CurrentGMT() : TimeTradeServer();
   MqlDateTime dt;
   TimeToStruct(t, dt);
   int m = dt.hour * 60 + dt.min;
   if(g_sessStartMin <= g_sessEndMin)
      return (m >= g_sessStartMin && m < g_sessEndMin);
   return (m >= g_sessStartMin || m < g_sessEndMin);   // window crosses midnight
  }

bool NewsBlocked()
  {
   if(!UseNewsFilter)
      return false;
   if(MQLInfoInteger(MQL_TESTER))
     {
      if(!g_newsWarned)
        {
         Print("[XLZC] News filter: economic calendar unavailable in tester -> bypassed.");
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
         Print("[XLZC] News filter: calendar query failed, error ", err, " (trading allowed)");
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

#ifdef XLZC_WITH_FGF
//--- FlashGold Direction Filter: buffer 2 ("FGF sell allowed") is 1 while
//    price is below the FlashGold level, outside the ATR no-trade band and
//    the permission window is open. 0 = sells not allowed.
bool FGFAllowsSell()
  {
   if(!UseFGF_Filter || g_hFGF == INVALID_HANDLE)
      return true;
   double v[];
   if(BarsCalculated(g_hFGF) <= 0 || CopyBuffer(g_hFGF, 2, FGF_Shift, 1, v) != 1 || v[0] == EMPTY_VALUE)
     {
      if(FGF_BlockIfUnavailable)
        {
         LogSkip("FlashGold filter has no data yet");
         return false;
        }
      return true;
     }
   if(v[0] < 0.5)
     {
      LogSkip("FlashGold filter does not allow sells");
      g_signalActive = false;   // decided once per signal, as in the backtest
      return false;
     }
   return true;
  }
#endif

bool TradingAllowed()
  {
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
     {
      LogSkip("algo trading disabled in terminal/EA settings");
      return false;
     }
   long mode = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if(mode != SYMBOL_TRADE_MODE_FULL && mode != SYMBOL_TRADE_MODE_SHORTONLY)
     {
      LogSkip("symbol does not allow opening shorts");
      return false;
     }
   return true;
  }

//====================================================================
// POSITION MANAGEMENT (R5: trailing + optional partial close)
//====================================================================
void ManageOpenPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!g_pos.SelectByIndex(i))
         continue;
      if(g_pos.Symbol() != _Symbol || (ulong)g_pos.Magic() != MagicNumber)
         continue;
      if(g_pos.PositionType() != POSITION_TYPE_SELL)
         continue;

      ulong  ticket = g_pos.Ticket();
      double open   = g_pos.PriceOpen();
      double sl     = g_pos.StopLoss();
      double tp     = g_pos.TakeProfit();
      double vol    = g_pos.Volume();
      double ask    = Ask();
      double minD   = StopsLevelDistance();

      //--- remember the initial risk the first time we see the position
      string rKey = GVKey("R", ticket);
      if(!GlobalVariableCheck(rKey) && sl > open)
         GlobalVariableSet(rKey, sl - open);
      double initRisk = GlobalVariableCheck(rKey) ? GlobalVariableGet(rKey) : 0.0;

      //--- hybrid trailing: close at market if the virtual level is hit
      string vKey = GVKey("V", ticket);
      if(EnableTrailing && TrailingMode == TRAIL_HYBRID && GlobalVariableCheck(vKey))
        {
         double vsl = GlobalVariableGet(vKey);
         if(vsl > 0.0 && ask >= vsl)
           {
            if(g_trade.PositionClose(ticket))
              {
               Log(StringFormat("Hybrid trailing stop hit at %.2f -> closed #%I64u", vsl, ticket));
               GlobalVariableDel(vKey);
              }
            else
               Print("[XLZC] Hybrid close failed: ", g_trade.ResultRetcodeDescription());
            continue;
           }
        }

      //--- optional partial close at X * R
      string pKey = GVKey("P", ticket);
      if(EnablePartialClose && initRisk > 0.0 && !GlobalVariableCheck(pKey) &&
         open - ask >= PartialCloseAtR * initRisk)
        {
         double volStep  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double volMin   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double closeVol = MathFloor(vol * PartialClosePercent / 100.0 / volStep + 1e-9) * volStep;
         if(closeVol >= volMin && vol - closeVol >= volMin - 1e-9)
           {
            //--- the ticket overload only works on hedging accounts; netting
            //    accounts reduce the symbol's single position by volume instead
            bool hedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
            bool closed  = hedging ? g_trade.PositionClosePartial(ticket, closeVol)
                                   : g_trade.PositionClosePartial(_Symbol, closeVol);
            if(closed)
              {
               GlobalVariableSet(pKey, 1.0);
               Log(StringFormat("Partial close %.2f lots of #%I64u at %.1fR", closeVol, ticket, PartialCloseAtR));
               if(MoveSLToBreakevenAfterPartial && (sl == 0.0 || sl > open) && open - ask > minD)
                 {
                  if(g_trade.PositionModify(ticket, NormalizePrice(open), tp))
                     sl = open;
                 }
              }
            else
              {
               Print("[XLZC] Partial close failed: retcode ", g_trade.ResultRetcode(), " ",
                     g_trade.ResultRetcodeDescription(), " - not retried for this position");
               GlobalVariableSet(pKey, 1.0);   // log once instead of on every tick
              }
           }
         else
            GlobalVariableSet(pKey, 1.0);  // volume too small to split; don't retry
        }

      //--- trailing stop
      if(!EnableTrailing)
         continue;
      double profit = open - ask;
      if(profit < Pts(TrailingStart_Points))
         continue;
      double newSL = NormalizePrice(ask + Pts(TrailingDistance_Points));
      double step  = Pts(TrailingStep_Points);

      if(TrailingMode == TRAIL_SERVER)
        {
         if((sl == 0.0 || newSL <= sl - step) && newSL - ask > minD)
           {
            if(g_trade.PositionModify(ticket, newSL, tp))
               Log(StringFormat("Trailing SL #%I64u -> %.2f", ticket, newSL));
            else
               Print("[XLZC] Trailing modify failed: ", g_trade.ResultRetcodeDescription());
           }
        }
      else // TRAIL_HYBRID: hard SL stays at broker, trailing level is virtual
        {
         double vsl = GlobalVariableCheck(vKey) ? GlobalVariableGet(vKey) : 0.0;
         if((vsl == 0.0 || newSL <= vsl - step) && (sl == 0.0 || newSL < sl))
           {
            GlobalVariableSet(vKey, newSL);
            Log(StringFormat("Virtual trailing #%I64u -> %.2f", ticket, newSL));
           }
        }
     }
  }

//====================================================================
// VISUALS (hooks for future liquidity rectangles)
//====================================================================
void DrawLevel(const string name, const double price, const color clr, const string text)
  {
   string n = OBJ_PREFIX + name;
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, OBJ_HLINE, 0, 0, price);
   ObjectSetDouble(0, n, OBJPROP_PRICE, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, n, OBJPROP_STYLE, STYLE_DOT);
   ObjectSetString(0, n, OBJPROP_TEXT, text);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
  }

//--- Hook for v2: hand-drawn style "blue rectangle" liquidity zones.
//    v1 draws a small box around the detected liquidity high / pool.
void DrawLiquidityZone(const string name, const datetime t1, const double p1,
                       const datetime t2, const double p2, const color clr)
  {
   string n = OBJ_PREFIX + name;
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, n, OBJPROP_TIME, 0, t1);
   ObjectSetDouble(0, n, OBJPROP_PRICE, 0, p1);
   ObjectSetInteger(0, n, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, n, OBJPROP_PRICE, 1, p2);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, n, OBJPROP_FILL, true);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
  }

void DrawPlan(const TradePlan &p)
  {
   string id    = TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES);
   datetime now = iTime(_Symbol, TriggerTimeframe, 0);
   DrawLevel("SL", p.sl, clrTomato, "XLZC SL " + p.slSource);
   DrawLevel("TP", p.tp, clrDodgerBlue, "XLZC TP " + p.tpSource);
   if(!ShowLiquidityLines)
      return;
   //--- red line: the liquidity high the SL protects (spec: "the red horizontal line")
   string rl = OBJ_PREFIX + "LiqHighLine_" + id;
   if(p.slRefTime > 0 && ObjectCreate(0, rl, OBJ_TREND, 0, p.slRefTime, p.slRef, now, p.slRef))
     {
      ObjectSetInteger(0, rl, OBJPROP_COLOR, clrRed);
      ObjectSetInteger(0, rl, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, rl, OBJPROP_RAY_RIGHT, true);
      ObjectSetInteger(0, rl, OBJPROP_SELECTABLE, false);
     }
   //--- blue rectangle: the liquidity zone / swing low the TP targets
   if(p.tpRefTime > 0)
      DrawLiquidityZone("LiqPool_" + id, p.tpRefTime, MathMin(p.tpZoneLow > 0.0 ? p.tpZoneLow : p.tpRef, p.tp),
                        now + PeriodSeconds(TriggerTimeframe) * 30, MathMax(p.tpRef, p.tp), clrDodgerBlue);
  }

//--- "M3", "H1" ... instead of PERIOD_M3
string TFName(const ENUM_TIMEFRAMES tf)
  {
   ENUM_TIMEFRAMES t = (tf == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : tf;
   string n = EnumToString(t);
   StringReplace(n, "PERIOD_", "");
   return n;
  }

//--- sell arrow at the trigger bar that produced the signal (drawn at that bar's
//    time, so on an M1 chart it sits on the M1 bar where the M3 bar closed)
void MarkSignal(const datetime barTime)
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   string n = OBJ_PREFIX + "SIG_" + (string)(long)barTime;
   double price = iHigh(_Symbol, TriggerTimeframe, 1);
   if(ObjectFind(0, n) < 0)
      ObjectCreate(0, n, OBJ_ARROW_SELL, 0, barTime, price);
   ObjectSetInteger(0, n, OBJPROP_COLOR, clrTomato);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetString(0, n, OBJPROP_TOOLTIP,
                   StringFormat("XLZC %s signal: MACD(%s) crossed below zero on the %s bar closed at %s",
                                TFName(TriggerTimeframe), TFName(TriggerTimeframe), TFName(TriggerTimeframe),
                                TimeToString(barTime, TIME_DATE | TIME_MINUTES)));
  }

//--- closed trades of this EA (magic + symbol): positions closed, positions won
void WinStats(int &closed, int &wins)
  {
   closed = 0; wins = 0;
   if(!HistorySelect(0, TimeCurrent() + 1))
      return;
   long   ids[];
   double pnl[];
   int    n = 0;
   for(int k = 0; k < HistoryDealsTotal(); k++)
     {
      ulong d = HistoryDealGetTicket(k);
      if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol ||
         (ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != MagicNumber)
         continue;
      long et = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(et != DEAL_ENTRY_OUT && et != DEAL_ENTRY_OUT_BY && et != DEAL_ENTRY_INOUT)
         continue;
      long id = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      double v = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) +
                 HistoryDealGetDouble(d, DEAL_COMMISSION);
      int i = -1;
      for(int q = n - 1; q >= 0; q--)
         if(ids[q] == id) { i = q; break; }
      if(i < 0)
        {
         i = n++;
         ArrayResize(ids, n); ArrayResize(pnl, n);
         ids[i] = id; pnl[i] = 0.0;
        }
      pnl[i] += v;                                     // partial closes add up per position
     }
   closed = n;
   for(int i = 0; i < n; i++)
      if(pnl[i] > 0.0)
         wins++;
  }

//--- status panel: proves which timeframe the signals come from
void UpdatePanel()
  {
   if(!ShowStatusPanel || (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)))
      return;
#ifdef XLZC_WITH_FGF
   string build = "XLZC Bearish v1.20 + FGF";
#else
   string build = "XLZC Bearish v1.20";
#endif
   //--- last closed trigger bar and its MACD (the exact values the signal uses)
   datetime lastOpen = iTime(_Symbol, TriggerTimeframe, 1);
   double macd[];
   ArraySetAsSeries(macd, true);
   string macdTxt = "not ready";
   if(g_hMacdM1 != INVALID_HANDLE && CopyBuffer(g_hMacdM1, 0, 1, 2, macd) == 2)
      macdTxt = StringFormat("%.3f -> %.3f%s", macd[1], macd[0],
                             (macd[1] >= 0.0 && macd[0] < 0.0) ? "  (zero-cross DOWN)" : "");
   string bias = "off";
   if(UseHTF_Filter)
     {
      g_quietLog = true;                      // same rule as the signal, without log lines
      int st = HTFBiasState();
      g_quietLog = false;
      bias = (st == SIG_VALID) ? "BEARISH (shorts allowed)" : (st == SIG_NONE) ? "not bearish (no shorts)" : "not ready";
     }
   double spreadPts = (Ask() - Bid()) / (_Point * g_ptScale);
   int closedN, winsN;
   WinStats(closedN, winsN);
   string winTxt = (closedN > 0) ? StringFormat("%d of %d closed trades won (%.0f%%)", winsN, closedN,
                                                100.0 * winsN / closedN) : "no closed trades yet";
   Comment(StringFormat("%s | %s | chart %s\n"
                        "Signals on: %s bars   |   Trend filter: %s%s\n"
                        "Last closed %s bar: %s  (closed %s)\n"
                        "MACD(%s) bar[2] -> bar[1]: %s\n"
                        "%s bias: %s\n"
                        "Session %s-%s %s: %s   |   Spread %.0f / %d pts\n"
                        "Signal: %s %s   |   Positions: %d\n"
                        "Results: %s",
                        build, _Symbol, TFName((ENUM_TIMEFRAMES)_Period),
                        TFName(TriggerTimeframe), TFName(HTF_Timeframe),
                        (UseHTF_Filter && UseHTF2) ? (HTF_Combine == HTF_EITHER ? " or " : " and ") + TFName(HTF2_Timeframe) : "",
                        TFName(TriggerTimeframe), TimeToString(lastOpen, TIME_DATE | TIME_MINUTES),
                        TimeToString(lastOpen + PeriodSeconds(TriggerTimeframe), TIME_MINUTES),
                        TFName(TriggerTimeframe), macdTxt,
                        "Trend", bias,
                        TradingHoursStart, TradingHoursEnd, TradingHoursAreGMT ? "GMT" : "server time",
                        SessionOK() ? "open" : "closed", spreadPts, MaxSpread_Points,
                        g_signalActive ? "ACTIVE" : "none", g_signalTag, CountOwnPositions(), winTxt));
  }
//+------------------------------------------------------------------+
