//+------------------------------------------------------------------+
//|                                                  RegimeTrend.mq5 |
//|              Two-layer market regime + direction indicator (XAUUSD)|
//+------------------------------------------------------------------+
//| Non-repainting, non-redrawing, non-lagging on closed bars.        |
//|                                                                   |
//| LAYER 1 - REGIME                                                  |
//|   Kaufman Efficiency Ratio over InpErPeriod bars of InpRegimeTF   |
//|   (default H1), mapped onto the chart timeframe using the last    |
//|   FULLY CLOSED higher timeframe bar, so a value can never be      |
//|   revised after the chart bar exists.                             |
//|                                                                   |
//| LAYER 2 - DIRECTION                                               |
//|   SuperTrend (Wilder ATR, InpAtrPeriod / InpAtrMult) on the chart |
//|   timeframe.                                                      |
//|                                                                   |
//| STATE MACHINE                                                     |
//|   0 = Range (choppy), 1 = TrendUp, -1 = TrendDown, 2 = Neutral.   |
//|   Hysteresis (enter above InpEnterTrend, leave below              |
//|   InpExitTrend), a minimum dwell of InpMinDwell bars, and a shock |
//|   circuit breaker (bar range > InpShockMult * ATR forces Range    |
//|   and resets the dwell counter, overriding the dwell lock).       |
//|                                                                   |
//| BUFFER MAP                                                        |
//|   0  SuperTrend line                (plotted, DRAW_COLOR_LINE)    |
//|   1  colour index driven by state   (plot 0 colour buffer)        |
//|   2  Efficiency Ratio               (DRAW_NONE, "ER")             |
//|   3  STATE  <-- the iCustom interface for EAs                     |
//|                 0 Range, 1 TrendUp, -1 TrendDown, 2 Neutral       |
//|                                     (DRAW_NONE, "State")          |
//|   4  dwell counter, bars in state   (DRAW_NONE, "Bars in state")  |
//|   5  REGIME    <-- EA friendly: 2 Trending, 1 Neutral, 0 Choppy,  |
//|                    -1 while warming up  (DRAW_NONE, "Regime")     |
//|   6  DIRECTION <-- EA friendly: +1 up, -1 down, 0 when not        |
//|                    trending             (DRAW_NONE, "Direction")  |
//|   7  MACRO TREND <-- HTF EMA slope: +1 up, -1 down, 0 flat, -2    |
//|                    warming up. A SEPARATE axis from buffers 3/5/6:|
//|                    it is NOT fed by, and never reset by, the      |
//|                    regime state machine, so it keeps reporting    |
//|                    the structural trend through choppy regimes.   |
//|                                          (DRAW_NONE, "Macro Trend")|
//|   8  Buy Signal arrow buffer        (plotted, DRAW_ARROW)         |
//|   9  Sell Signal arrow buffer       (plotted, DRAW_ARROW)         |
//|  10  SuperTrend final upper band    (calculations)                |
//|  11  SuperTrend final lower band    (calculations)                |
//|  12  SuperTrend direction, +1 / -1  (calculations)                |
//|  13  ATR used by layer 2 and by the shock rule (calculations)     |
//|  14  macro trend min-dwell counter, in HTF bars (calculations)    |
//|                                                                   |
//|   Buffers 2-7 are DRAW_NONE plots, buffers 8-9 are DRAW_ARROW     |
//|   plots. MQL5 only lists PLOTTED buffers in the Data Window, and  |
//|   all plots must precede calculation buffers.                     |
//|                                                                   |
//|   Buffers 5 and 6 are buffer 3 split in two, so an EA never has   |
//|   to read a sign to learn the regime:                             |
//|       regime >= 2 && direction > 0   ->  confirmed uptrend        |
//|       regime == 0                    ->  stand aside, choppy      |
//|                                                                   |
//|   Buffers 10-14 exist so that EVERY recursive term lives in an    |
//|   indicator buffer. Bar i reads bar i-1 from these buffers and    |
//|   never from a static or global variable, which is what makes a   |
//|   full recalculation reproduce the incremental series exactly.    |
//|   Buffer 14 exists for the same reason buffers 3/4 do: the        |
//|   macro-trend min-dwell debounce is a genuine recursion (today's  |
//|   answer depends on yesterday's), so it cannot be recomputed      |
//|   fresh from an arbitrary truncated window the way buffer 2 (ER)  |
//|   or buffer 7's raw classification can - see RegimeMacroTrend.mqh |
//|   for why an earlier, stateless version of this was wrong.        |
//|   Set InpSelfCheck to verify the no-repaint claim at runtime.     |
//|                                                                   |
//|   Colour index: 0 Range, 1 TrendUp, 2 TrendDown, 3 Neutral.       |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property link      ""
#property version   "1.03"
#property strict
#property icon      "xpworx.ico"
#property description "RegimeTrend - efficiency-ratio regime filter with a SuperTrend direction layer and an on-chart gauge."
#property description "Licensed to Maynor."

#property indicator_chart_window
#property indicator_buffers 15
#property indicator_plots   9

#property indicator_type1   DRAW_COLOR_LINE
#property indicator_label1  "RegimeTrend"
#property indicator_width1  2
//--- values-only plots: nothing is drawn, they exist so that the
//--- regime read-out is visible in the Data Window.
#property indicator_type2   DRAW_NONE
#property indicator_label2  "ER"
#property indicator_type3   DRAW_NONE
#property indicator_label3  "State"
#property indicator_type4   DRAW_NONE
#property indicator_label4  "Bars in state"
#property indicator_type5   DRAW_NONE
#property indicator_label5  "Regime"
#property indicator_type6   DRAW_NONE
#property indicator_label6  "Direction"
#property indicator_type7   DRAW_NONE
#property indicator_label7  "Macro Trend"
//--- visual signal arrows
#property indicator_type8   DRAW_ARROW
#property indicator_label8  "Buy Signal"
#property indicator_width8  2
#property indicator_type9   DRAW_ARROW
#property indicator_label9  "Sell Signal"
#property indicator_width9  2

#include <Foundry\RegimeTrend\RegimeTypes.mqh>
#include <Foundry\RegimeTrend\RegimeER.mqh>
#include <Foundry\RegimeTrend\RegimeDirection.mqh>
#include <Foundry\RegimeTrend\RegimeStateMachine.mqh>
#include <Foundry\RegimeTrend\RegimeMacroTrend.mqh>
#include <Foundry\RegimeTrend\RegimeGauge.mqh>

//--- Layer 1: regime (Efficiency Ratio) ------------------------------
input ENUM_TIMEFRAMES      InpRegimeTF      = PERIOD_H1;   // Regime timeframe
input int                  InpErPeriod      = 20;          // ER lookback (HTF bars)
input double               InpEnterTrend    = 0.42;        // ER to ENTER a trend state
input double               InpExitTrend     = 0.18;        // ER to LEAVE a trend state
//--- Layer 2: direction (SuperTrend) ---------------------------------
input int                  InpAtrPeriod     = 10;          // ATR period
input double               InpAtrMult       = 4.0;         // ATR multiplier
//--- State machine ---------------------------------------------------
input int                  InpMinDwell      = 6;           // Minimum bars in a state
input double               InpShockMult     = 3.0;         // Shock: bar range > N * ATR
input bool                 InpUseClosedBars = true;        // Use closed bars only
input bool                 InpSelfCheck     = false;       // Verify full-recalc identity
//--- Macro trend (HTF EMA slope) -------------------------------------
input ENUM_TIMEFRAMES      InpMacroTF          = PERIOD_H4;  // Macro trend timeframe
input int                  InpMacroEmaPeriod   = 50;         // EMA period (HTF bars)
input int                  InpMacroSlopeBars   = 3;          // Slope lookback (HTF bars)
input double               InpMacroDeadbandPct = 0.05;       // Flat deadband (% of EMA)
input int                  InpMacroMinDwell    = 2;          // Minimum HTF bars before a flip
//--- Gauge -----------------------------------------------------------
input bool                 InpShowGauge     = true;        // Show the gauge
input ENUM_BASE_CORNER     InpGaugeCorner   = CORNER_RIGHT_UPPER; // Corner
input int                  InpGaugeX        = 20;          // X distance (px)
input int                  InpGaugeY        = 20;          // Y distance (px)
input int                  InpGaugeSize     = 220;         // Width (px)
input uchar                InpGaugeOpacity  = 215;         // Panel opacity 0-255
input color                InpClrChoppy     = C'176,68,68';   // Zone: choppy
input color                InpClrNeutral    = C'196,150,62';  // Zone: neutral
input color                InpClrTrending   = C'70,150,100';  // Zone: trending
//--- Plot colours ----------------------------------------------------
input color                InpLineRange     = C'130,134,140'; // Line: Range
input color                InpLineUp        = C'70,150,100';  // Line: TrendUp
input color                InpLineDown      = C'176,68,68';   // Line: TrendDown
input color                InpLineNeutral   = C'196,150,62';  // Line: Neutral
//--- Signal arrows ---------------------------------------------------
input bool                 InpShowArrows    = true;           // Show Buy/Sell signal arrows
input bool                 InpSignalsWithMacro = true;        // Arrows/alerts only with the macro trend (as the EA trades)
input color                InpClrArrowBuy   = C'70,150,100';  // Buy arrow colour
input color                InpClrArrowSell  = C'176,68,68';   // Sell arrow colour
//--- Alerts ----------------------------------------------------------
input bool                 InpAlertPopup    = true;           // Popup alerts
input bool                 InpAlertPush     = false;          // Mobile push notifications
input bool                 InpAlertEmail    = false;          // Email alerts
input bool                 InpAlertSound    = true;           // Play alert sound
input string               InpSoundFile     = "alert.wav";    // Alert sound file

//--- buffers ---------------------------------------------------------
double BufST[];         // 0
double BufColor[];      // 1
double BufER[];         // 2
double BufState[];      // 3
double BufDwell[];      // 4
double BufRegime[];     // 5
double BufDirection[];  // 6
double BufMacroTrend[]; // 7
double BufBuySignal[];  // 8
double BufSellSignal[]; // 9
double BufFU[];         // 10
double BufFL[];         // 11
double BufDir[];        // 12
double BufATR[];        // 13
double BufMacroDwell[]; // 14

//--- engines ---------------------------------------------------------
CRegimeEfficiencyRatio g_er;
CSuperTrendEngine      g_st;
CRegimeStateMachine    g_machine;
CMacroTrendEngine      g_macro;
CRegimeGauge           g_gauge;

//--- presentation-only memory (never feeds the calculation) ----------
datetime g_last_bar_time  = 0;
int      g_macro_from     = -1;   // oldest chart bar whose macro is still UNSET because HTF data was missing (-1 = none)
int      g_last_state     = REGIME_UNSET;
double   g_last_er        = REGIME_ER_INVALID;
int      g_last_dwell     = 0;
string   g_gauge_name     = "";

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

   bool removeIndicator = false;
   long accountNumber = AccountNumber();
   if(UserAccountNumber != 0 && UserAccountNumber != accountNumber && accountNumber != 0)
     {
      if(EnableAllPopups) AlertOnce("Wrong account number", 3);
      removeIndicator = true;
     }
   if(DemoOnly && !IsDemo())
     {
      if(EnableAllPopups) AlertOnce("Demo accounts only", 4);
      removeIndicator = true;
     }
   if(ExpirationDate != 0 && (TimeCurrent() >= ExpirationDate || TimeLocal() >= ExpirationDate))
     {
      if(EnableAllPopups) AlertOnce("This indicator has expired", 5);
      removeIndicator = true;
     }
   if(removeIndicator)
     {
      securityRemovalRequested = true;
     }
  }

//+------------------------------------------------------------------+
int OnInit(void)
  {
   Security();
   if(securityRemovalRequested)
      return(INIT_FAILED);

   if(InpErPeriod < 2)
     {
      PrintFormat("RegimeTrend: InpErPeriod (%d) must be >= 2. (InpRegimeTF=%d)",InpErPeriod,InpRegimeTF);
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpAtrPeriod < 1 || InpAtrMult <= 0.0)
     {
      Print("RegimeTrend: ATR period must be >= 1 and the multiplier > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpEnterTrend <= InpExitTrend || InpExitTrend < 0.0 || InpEnterTrend > 1.0)
     {
      Print("RegimeTrend: require 0 <= InpExitTrend < InpEnterTrend <= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpMinDwell < 1 || InpShockMult <= 0.0)
     {
      Print("RegimeTrend: InpMinDwell must be >= 1 and InpShockMult > 0.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpMacroEmaPeriod < 2 || InpMacroSlopeBars < 1 ||
      InpMacroDeadbandPct < 0.0 || InpMacroMinDwell < 1)
     {
      Print("RegimeTrend: invalid macro trend configuration - EMA period >= 2, ",
            "slope bars >= 1, deadband >= 0, min dwell >= 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(PeriodSeconds(InpRegimeTF) < PeriodSeconds(_Period))
      Print("RegimeTrend: warning - the regime timeframe is lower than the chart timeframe.");
   if(PeriodSeconds(InpMacroTF) < PeriodSeconds(InpRegimeTF))
      Print("RegimeTrend: warning - the macro trend timeframe is faster than the regime ",
            "timeframe; it is meant to be the slower, structural anchor.");

//--- Plotted buffers must precede the calculation buffers, so the six
//--- read-out buffers sit at 2..7. Indices 2, 3 and 4 keep the meaning
//--- they always had; Regime, Direction and Macro Trend moved here.
   SetIndexBuffer(0,BufST,INDICATOR_DATA);
   SetIndexBuffer(1,BufColor,INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2,BufER,INDICATOR_DATA);
   SetIndexBuffer(3,BufState,INDICATOR_DATA);
   SetIndexBuffer(4,BufDwell,INDICATOR_DATA);
   SetIndexBuffer(5,BufRegime,INDICATOR_DATA);
   SetIndexBuffer(6,BufDirection,INDICATOR_DATA);
   SetIndexBuffer(7,BufMacroTrend,INDICATOR_DATA);
   SetIndexBuffer(8,BufBuySignal,INDICATOR_DATA);
   SetIndexBuffer(9,BufSellSignal,INDICATOR_DATA);
   SetIndexBuffer(10,BufFU,INDICATOR_CALCULATIONS);
   SetIndexBuffer(11,BufFL,INDICATOR_CALCULATIONS);
   SetIndexBuffer(12,BufDir,INDICATOR_CALCULATIONS);
   SetIndexBuffer(13,BufATR,INDICATOR_CALCULATIONS);
   SetIndexBuffer(14,BufMacroDwell,INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(0,PLOT_COLOR_INDEXES,4);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,REGIME_CLRIDX_RANGE,InpLineRange);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,REGIME_CLRIDX_UP,InpLineUp);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,REGIME_CLRIDX_DOWN,InpLineDown);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,REGIME_CLRIDX_NEUTRAL,InpLineNeutral);
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetInteger(0,PLOT_DRAW_BEGIN,InpAtrPeriod + 1);

   //--- Plot 7 (Buy Signal arrow)
   PlotIndexSetInteger(7,PLOT_ARROW,233);
   PlotIndexSetInteger(7,PLOT_LINE_COLOR,InpClrArrowBuy);
   PlotIndexSetDouble(7,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetInteger(7,PLOT_DRAW_BEGIN,InpAtrPeriod + 1);

   //--- Plot 8 (Sell Signal arrow)
   PlotIndexSetInteger(8,PLOT_ARROW,234);
   PlotIndexSetInteger(8,PLOT_LINE_COLOR,InpClrArrowSell);
   PlotIndexSetDouble(8,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   PlotIndexSetInteger(8,PLOT_DRAW_BEGIN,InpAtrPeriod + 1);

   if(!InpShowArrows)
     {
      PlotIndexSetInteger(7,PLOT_DRAW_TYPE,DRAW_NONE);
      PlotIndexSetInteger(8,PLOT_DRAW_TYPE,DRAW_NONE);
     }

   IndicatorSetInteger(INDICATOR_DIGITS,_Digits);
   IndicatorSetString(INDICATOR_SHORTNAME,
                      StringFormat("RegimeTrend(%s,%d,%.2f/%.2f,ATR %d x %.1f)",
                                   EnumToString(InpRegimeTF),InpErPeriod,
                                   InpEnterTrend,InpExitTrend,InpAtrPeriod,InpAtrMult));

   if(!g_er.Init(_Symbol,InpRegimeTF,InpErPeriod))
     {
      Print("RegimeTrend: failed to initialise the efficiency ratio layer.");
      return(INIT_FAILED);
     }
   if(!g_st.Init(_Symbol,_Period,InpAtrPeriod,InpAtrMult))
     {
      Print("RegimeTrend: failed to create the ATR handle.");
      return(INIT_FAILED);
     }
   if(!g_machine.Init(InpEnterTrend,InpExitTrend,InpMinDwell,InpShockMult))
     {
      Print("RegimeTrend: invalid state machine configuration.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(!g_macro.Init(_Symbol,InpMacroTF,InpMacroEmaPeriod,InpMacroSlopeBars,
                    InpMacroDeadbandPct,InpMacroMinDwell))
     {
      Print("RegimeTrend: invalid macro trend configuration.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_last_bar_time = 0;
   g_last_state    = REGIME_UNSET;
   g_last_er       = REGIME_ER_INVALID;
   g_last_dwell    = 0;

   if(InpShowGauge)
     {
      g_gauge_name = "RegimeTrendGauge_" + IntegerToString((int)ChartID()) + "_" +
                     IntegerToString(ChartWindowFind());
      g_gauge.SetThresholds(InpExitTrend,InpEnterTrend);
      g_gauge.SetZoneColors(InpClrChoppy,InpClrNeutral,InpClrTrending);
      g_gauge.SetOpacity(InpGaugeOpacity);
      g_gauge.SetMacroConfirm(InpSignalsWithMacro);
      if(!g_gauge.Create(ChartID(),g_gauge_name,InpGaugeCorner,InpGaugeX,InpGaugeY,InpGaugeSize))
         Print("RegimeTrend: could not create the gauge canvas; continuing without it.");
      else
        {
         g_gauge.ApplyTheme();
         g_gauge.Render(REGIME_ER_INVALID,REGIME_UNSET,0);
        }
     }
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   g_gauge.Destroy();
   g_st.Deinit();
   ChartRedraw();
  }
//+------------------------------------------------------------------+
//| Recompute the whole history into scratch arrays and compare it   |
//| with the live buffers. Any difference means something repainted. |
//+------------------------------------------------------------------+
bool RegimeSelfCheck(const int rates_total,const datetime &time[],
                     const double &high[],const double &low[],const double &close[])
  {
   int seed = g_st.WarmupBars();
   int last = InpUseClosedBars ? rates_total - 2 : rates_total - 1;
   if(last <= seed)
      return(true);

   double er[],st[],fu[],fl[],dir[],atr[],state[],dwell[];
   if(ArrayResize(er,rates_total)    != rates_total ||
      ArrayResize(st,rates_total)    != rates_total ||
      ArrayResize(fu,rates_total)    != rates_total ||
      ArrayResize(fl,rates_total)    != rates_total ||
      ArrayResize(dir,rates_total)   != rates_total ||
      ArrayResize(atr,rates_total)   != rates_total ||
      ArrayResize(state,rates_total) != rates_total ||
      ArrayResize(dwell,rates_total) != rates_total)
     {
      Print("RegimeTrend self-check: out of memory.");
      return(false);
     }
   for(int i = 0; i < seed; i++)
     {
      er[i]    = REGIME_ER_INVALID;
      st[i]    = EMPTY_VALUE;
      fu[i]    = 0.0;
      fl[i]    = 0.0;
      dir[i]   = 0.0;
      atr[i]   = 0.0;
      state[i] = (double)REGIME_UNSET;
      dwell[i] = 0.0;
     }

   if(!g_st.LoadAtr(rates_total,seed))
     {
      Print("RegimeTrend self-check: ATR not available, skipped.");
      return(true);
     }
   if(!g_er.Calculate(rates_total,seed,time,er))
     {
      Print("RegimeTrend self-check: higher timeframe not available, skipped.");
      return(true);
     }
   for(int i = seed; i < rates_total; i++)
      atr[i] = g_st.Atr(i);
   if(!g_st.Calculate(rates_total,seed,high,low,close,st,fu,fl,dir))
     {
      Print("RegimeTrend self-check: SuperTrend recomputation failed, skipped.");
      return(true);
     }
   g_machine.Calculate(seed,last,high,low,er,dir,atr,state,dwell);

//--- macro trend: recompute the same boundary-gated debounce OnCalculate
//--- uses, seeded fresh at `seed` (mirrors a full recalculation).
   double macro[],macroDwell[];
   bool   macro_ready = ArrayResize(macro,rates_total) == rates_total &&
                        ArrayResize(macroDwell,rates_total) == rates_total;
   if(macro_ready)
     {
      for(int i = 0; i < seed; i++)
        {
         macro[i]      = (double)REGIME_MACRO_UNSET;
         macroDwell[i] = 0.0;
        }
      double macroRaw[];
      int    macroBoundary[];
      if(ArrayResize(macroRaw,rates_total) == rates_total &&
         ArrayResize(macroBoundary,rates_total) == rates_total &&
         g_macro.CalculateRaw(rates_total,seed,time,macroRaw,macroBoundary))
        {
         for(int i = seed; i <= last; i++)
           {
            int prev_trend = (i > 0) ? (int)macro[i-1] : REGIME_MACRO_UNSET;
            int prev_dwell = (i > 0) ? (int)macroDwell[i-1] : 0;
            if(macroBoundary[i] == 0)
              {
               macro[i]      = (double)prev_trend;
               macroDwell[i] = (double)prev_dwell;
               continue;
              }
            int nt, nd;
            g_macro.Step(prev_trend,prev_dwell,(int)macroRaw[i],nt,nd);
            macro[i]      = (double)nt;
            macroDwell[i] = (double)nd;
           }
        }
      else
        {
         Print("RegimeTrend self-check: macro trend higher timeframe not available, ",
               "skipping the macro trend comparison.");
         macro_ready = false;
        }
     }

   int  mismatches = 0;
   int  first_bad  = -1;
   for(int i = seed; i <= last; i++)
     {
      bool bad = ((int)state[i] != (int)BufState[i]) ||
                 ((int)dwell[i] != (int)BufDwell[i]) ||
                 (MathAbs(er[i] - BufER[i]) > 1e-12) ||
                 (BufST[i] != EMPTY_VALUE && MathAbs(st[i] - BufST[i]) > 1e-10) ||
                 (macro_ready && ((int)macro[i] != (int)BufMacroTrend[i] ||
                                  (int)macroDwell[i] != (int)BufMacroDwell[i]));
      if(bad)
        {
         mismatches++;
         if(first_bad < 0)
            first_bad = i;
        }
     }
   if(mismatches == 0)
      PrintFormat("RegimeTrend self-check PASSED: %d closed bars reproduce identically.",last - seed + 1);
   else
     {
      PrintFormat("RegimeTrend self-check FAILED: %d of %d bars differ, first at index %d (%s) "
                  "live state=%d dwell=%d er=%.6f | recomputed state=%d dwell=%d er=%.6f",
                  mismatches,last - seed + 1,first_bad,
                  TimeToString(time[first_bad],TIME_DATE|TIME_MINUTES),
                  (int)BufState[first_bad],(int)BufDwell[first_bad],BufER[first_bad],
                  (int)state[first_bad],(int)dwell[first_bad],er[first_bad]);
      if(macro_ready)
         PrintFormat("  at that same index: live macro=%d dwell=%d | recomputed macro=%d dwell=%d",
                     (int)BufMacroTrend[first_bad],(int)BufMacroDwell[first_bad],
                     (int)macro[first_bad],(int)macroDwell[first_bad]);
     }
   return(mismatches == 0);
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(securityRemovalRequested)
      return(prev_calculated);
   Security();
   if(securityRemovalRequested)
      return(prev_calculated);

   int seed = g_st.WarmupBars();
   if(rates_total < seed + 2)
      return(0);

   int first = (prev_calculated == 0) ? seed : prev_calculated - 1;
   if(first < seed)
      first = seed;
   if(first >= rates_total)
      first = rates_total - 1;

//--- Layer inputs. If anything is not ready yet, leave every buffer
//--- untouched and retry on the next tick: never write a partial state.
   if(!g_st.LoadAtr(rates_total,first))
      return(prev_calculated);
   if(!g_er.Calculate(rates_total,first,time,BufER))
      return(prev_calculated);

   if(prev_calculated == 0)
     {
      for(int i = 0; i < seed; i++)
        {
         BufER[i]         = REGIME_ER_INVALID;
         BufATR[i]        = 0.0;
         BufState[i]      = (double)REGIME_UNSET;
         BufDwell[i]      = 0.0;
         BufColor[i]      = (double)REGIME_CLRIDX_RANGE;
         BufRegime[i]     = (double)REGIME_LEVEL_UNSET;
         BufDirection[i]  = 0.0;
         BufMacroTrend[i] = (double)REGIME_MACRO_UNSET;
         BufMacroDwell[i] = 0.0;
         BufBuySignal[i]  = EMPTY_VALUE;
         BufSellSignal[i] = EMPTY_VALUE;
        }
     }
   for(int i = first; i < rates_total; i++)
      BufATR[i] = g_st.Atr(i);

   if(!g_st.Calculate(rates_total,first,high,low,close,BufST,BufFU,BufFL,BufDir))
      return(prev_calculated);

//--- state machine on closed bars
   int last = InpUseClosedBars ? rates_total - 2 : rates_total - 1;
   if(last >= first)
      g_machine.Calculate(first,last,high,low,BufER,BufDir,BufATR,BufState,BufDwell);

//--- bar 0 mirrors bar 1 when only closed bars are trusted
   if(InpUseClosedBars)
     {
      BufState[rates_total-1] = BufState[rates_total-2];
      BufDwell[rates_total-1] = BufDwell[rates_total-2];
     }

   for(int i = first; i < rates_total; i++)
     {
      int st_i = (int)BufState[i];
      BufColor[i]     = (double)RegimeColorIndex(st_i);
      BufRegime[i]    = (double)RegimeLevel(st_i);
      BufDirection[i] = (double)RegimeDirection(st_i);
     }

//--- Macro trend: a SEPARATE axis, deliberately independent of the
//--- state machine above (never gated on it, never reset by it). If
//--- its own higher timeframe is not ready yet, that must not block
//--- the primary regime/state buffers this tick - only buffer 7/12
//--- fall back to "warming up" while everything else keeps working.
   double macroRaw[];
   int    macroBoundary[];
   if(ArrayResize(macroRaw,rates_total) != rates_total ||
      ArrayResize(macroBoundary,rates_total) != rates_total)
     {
      Print("RegimeTrend: out of memory sizing the macro trend scratch arrays.");
      return(prev_calculated);
     }
//--- if an earlier call had to leave bars UNSET (HTF not ready), start
//--- from there so history and the dwell recursion get rebuilt too
   if(prev_calculated == 0)
      g_macro_from = -1;
   int macro_first = first;
   if(g_macro_from >= 0 && g_macro_from < macro_first)
      macro_first = g_macro_from;
   if(g_macro.CalculateRaw(rates_total,macro_first,time,macroRaw,macroBoundary))
     {
      g_macro_from = -1;
      for(int i = macro_first; i < rates_total; i++)
        {
         int prev_trend = (i > 0) ? (int)BufMacroTrend[i-1] : REGIME_MACRO_UNSET;
         int prev_dwell = (i > 0) ? (int)BufMacroDwell[i-1] : 0;
         if(macroBoundary[i] == 0)
           {
            //--- no new HTF bar closed since the previous chart bar:
            //--- nothing changed at the macro level, copy forward so
            //--- the debounce counts HTF bars, not chart bars.
            BufMacroTrend[i] = (double)prev_trend;
            BufMacroDwell[i] = (double)prev_dwell;
            continue;
           }
         int nt, nd;
         g_macro.Step(prev_trend,prev_dwell,(int)macroRaw[i],nt,nd);
         BufMacroTrend[i] = (double)nt;
         BufMacroDwell[i] = (double)nd;
        }
     }
   else
     {
      for(int i = first; i < rates_total; i++)
        {
         BufMacroTrend[i] = (double)REGIME_MACRO_UNSET;
         BufMacroDwell[i] = 0.0;
        }
      if(g_macro_from < 0 || first < g_macro_from)
         g_macro_from = first;
     }

//--- Signal arrows, after the macro trend so they can be gated on it.
//--- With InpSignalsWithMacro they mark exactly the EA's entries: the
//--- bar the regime becomes Trending, with the macro trend agreeing
//--- (Up for buys, Down for sells). Starts at macro_first so bars whose
//--- macro was just backfilled get their arrows re-evaluated.
   for(int i = MathMin(first,macro_first); i < rates_total; i++)
     {
      BufBuySignal[i]  = EMPTY_VALUE;
      BufSellSignal[i] = EMPTY_VALUE;
      if(i < seed)
         continue;

      int st_i    = (int)BufState[i];
      int prev_st = (i > 0) ? (int)BufState[i-1] : REGIME_UNSET;
      if(InpSignalsWithMacro)
        {
         if(RegimeLevel(st_i) != REGIME_LEVEL_TRENDING || RegimeLevel(prev_st) == REGIME_LEVEL_TRENDING)
            continue;
         int m = (int)BufMacroTrend[i];
         if(st_i == REGIME_TREND_UP && m == REGIME_MACRO_UP)
            BufBuySignal[i] = low[i] - BufATR[i] * 0.5;
         else if(st_i == REGIME_TREND_DOWN && m == REGIME_MACRO_DOWN)
            BufSellSignal[i] = high[i] + BufATR[i] * 0.5;
        }
      else if(st_i == REGIME_TREND_UP && prev_st != REGIME_TREND_UP)
         BufBuySignal[i] = low[i] - BufATR[i] * 0.5;
      else if(st_i == REGIME_TREND_DOWN && prev_st != REGIME_TREND_DOWN)
         BufSellSignal[i] = high[i] + BufATR[i] * 0.5;
     }

//--- presentation: new bar / state change only, never per tick
   int    disp        = InpUseClosedBars ? rates_total - 2 : rates_total - 1;
   int    state       = (int)BufState[disp];
   int    dwell       = (int)BufDwell[disp];
   double er          = BufER[disp];
   int    macro_trend = (int)BufMacroTrend[disp];
   bool   new_bar     = (time[rates_total-1] != g_last_bar_time);

   if(InpSelfCheck && (prev_calculated == 0 || new_bar))
      RegimeSelfCheck(rates_total,time,high,low,close);

   if(InpShowGauge && g_gauge.IsCreated() && (new_bar || state != g_last_state))
     {
      g_gauge.Render(er,state,dwell,macro_trend);
      ChartRedraw();
     }

//--- alerts on closed bar transition
   static datetime s_last_alert_time = 0;
   if(new_bar && time[disp] != s_last_alert_time && prev_calculated > 0)
     {
      int st_curr = (int)BufState[disp];
      int st_prev = (disp > 0) ? (int)BufState[disp-1] : REGIME_UNSET;

      //--- buy/sell alerts follow the arrows, so they obey the macro gate
      string macro_note = InpSignalsWithMacro ? ", with macro trend" : "";
      string msg = "";
      if(BufBuySignal[disp] != EMPTY_VALUE)
         msg = StringFormat("RegimeTrend [%s, %s]: BUY SIGNAL (TrendUp Confirmed%s, ER=%.2f)",
                            _Symbol,EnumToString(_Period),macro_note,BufER[disp]);
      else if(BufSellSignal[disp] != EMPTY_VALUE)
         msg = StringFormat("RegimeTrend [%s, %s]: SELL SIGNAL (TrendDown Confirmed%s, ER=%.2f)",
                            _Symbol,EnumToString(_Period),macro_note,BufER[disp]);
      else if(st_curr == REGIME_RANGE && st_prev != REGIME_RANGE && st_prev != REGIME_UNSET)
         msg = StringFormat("RegimeTrend [%s, %s]: Trend Exit / Market Choppy (ER=%.2f)",
                            _Symbol,EnumToString(_Period),BufER[disp]);

      if(msg != "")
        {
         s_last_alert_time = time[disp];
         if(InpAlertPopup)
            Alert(msg);
         if(InpAlertPush)
            SendNotification(msg);
         if(InpAlertEmail)
            SendMail(StringFormat("RegimeTrend Signal - %s",_Symbol),msg);
         if(InpAlertSound)
            PlaySound(InpSoundFile);
        }
     }

   g_last_bar_time = time[rates_total-1];
   g_last_state    = state;
   g_last_er       = er;
   g_last_dwell    = dwell;

   return(rates_total);
  }
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE && InpShowGauge && g_gauge.IsCreated())
     {
      int disp = InpUseClosedBars ? Bars(_Symbol,_Period) - 2 : Bars(_Symbol,_Period) - 1;
      int macro_trend = (disp >= 0 && disp < ArraySize(BufMacroTrend)) ? (int)BufMacroTrend[disp] : REGIME_MACRO_UNSET;
      g_gauge.OnChartResize();
      g_gauge.Render(g_last_er,g_last_state,g_last_dwell,macro_trend);
      ChartRedraw();
     }
  }
//+------------------------------------------------------------------+
