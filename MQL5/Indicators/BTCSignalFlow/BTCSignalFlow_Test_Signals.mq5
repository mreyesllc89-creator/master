#property copyright "MQL5-Foundry"
#property version "1.10"
#property strict
#property indicator_chart_window
#property indicator_buffers 4
#property indicator_plots 4
#property indicator_label1 "SignalFlow buy signal"
#property indicator_type1 DRAW_ARROW
#property indicator_color1 clrLimeGreen
#property indicator_width1 2
#property indicator_label2 "SignalFlow sell signal"
#property indicator_type2 DRAW_ARROW
#property indicator_color2 clrTomato
#property indicator_width2 2
#property indicator_label3 "ATR 14"
#property indicator_type3 DRAW_NONE
#property indicator_label4 "Exit direction"
#property indicator_type4 DRAW_NONE
#property description "BTC SignalFlow Test Signals. Completed-candle buy and sell arrows; ATR and direction buffers."

#include <Foundry\SignalFlowTest\BTCMethodSignals.mqh>

// No input groups: preserve the positional iCustom interface.
input ENUM_BTC_METHOD InpMethod=BTC_EFFICIENCY_BREAKOUT;
input ENUM_TIMEFRAMES InpSignalPeriod=PERIOD_CURRENT;

ENUM_TIMEFRAMES g_period;
input int InpBreakoutBars=30;
input int InpExitBars=10;
input double InpMinER=0.20;
input int InpPullbackEMA=20;
input double InpClearanceATR=0.20;
input int InpHistoryBars=1000;

CBTCMethodSignals g_engine;
double Buy[],Sell[],ATR[],Direction[];

int OnInit()
  {
   g_period=InpSignalPeriod==PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : InpSignalPeriod;
   if(InpBreakoutBars<1 || InpExitBars<1 || InpPullbackEMA<1 ||
      InpMinER<0 || InpClearanceATR<0 || InpHistoryBars<1)
      { Print("Invalid mathematical parameter: periods/history must be positive; distances cannot be negative."); return INIT_PARAMETERS_INCORRECT; }
   SetIndexBuffer(0,Buy,INDICATOR_DATA); SetIndexBuffer(1,Sell,INDICATOR_DATA);
   SetIndexBuffer(2,ATR,INDICATOR_DATA); SetIndexBuffer(3,Direction,INDICATOR_DATA);
   ArraySetAsSeries(Buy,true); ArraySetAsSeries(Sell,true);
   ArraySetAsSeries(ATR,true); ArraySetAsSeries(Direction,true);
   PlotIndexSetInteger(0,PLOT_ARROW,233); PlotIndexSetInteger(1,PLOT_ARROW,234);
   for(int i=0;i<4;i++) PlotIndexSetDouble(i,PLOT_EMPTY_VALUE,EMPTY_VALUE);
   BTC_METHOD_CONFIG c;
   c.method=InpMethod; c.period=g_period; c.length=InpBreakoutBars; c.exit_bars=InpExitBars;
   c.efficiency=InpMinER; c.pullback_ema=InpPullbackEMA; c.clearance_atr=InpClearanceATR;
   if(!g_engine.Create(_Symbol,c)) return INIT_FAILED;
   IndicatorSetString(INDICATOR_SHORTNAME,"BTC SignalFlow Test Signals");
   IndicatorSetInteger(INDICATOR_DIGITS,_Digits);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { g_engine.Release(); }

int OnCalculate(const int rates_total,const int prev_calculated,const datetime &time[],
                const double &open[],const double &high[],const double &low[],const double &close[],
                const long &tick_volume[],const long &volume[],const int &spread[])
  {
   if(rates_total<206) return 0;
   ArraySetAsSeries(time,true);
   ArraySetAsSeries(high,true); ArraySetAsSeries(low,true);
   if(prev_calculated==0)
     {
      ArrayInitialize(Buy,EMPTY_VALUE); ArrayInitialize(Sell,EMPTY_VALUE);
      ArrayInitialize(ATR,EMPTY_VALUE); ArrayInitialize(Direction,EMPTY_VALUE);
     }
   int limit=prev_calculated==0 ? MathMin(rates_total-205,InpHistoryBars) :
                                 MathMin(MathMax(rates_total-prev_calculated+1,1),InpHistoryBars);
   bool latest_ready=false;
   for(int shift=limit;shift>=1;shift--)
     {
      BTC_METHOD_SIGNAL s;
      int signal_shift=shift;
      if(g_period!=(ENUM_TIMEFRAMES)_Period)
        {
         datetime decision=time[shift]+PeriodSeconds((ENUM_TIMEFRAMES)_Period);
         signal_shift=iBarShift(_Symbol,g_period,decision,false);
         if(signal_shift<0) continue;
         if(iTime(_Symbol,g_period,signal_shift)+PeriodSeconds(g_period)>decision) signal_shift++;
        }
      if(!g_engine.Evaluate(signal_shift,s)) continue;
      Buy[shift]=s.side==1 ? low[shift]-0.20*s.atr : EMPTY_VALUE;
      Sell[shift]=s.side==-1 ? high[shift]+0.20*s.atr : EMPTY_VALUE;
      ATR[shift]=s.atr;
      Direction[shift]=(InpMethod==BTC_TREND_PULLBACK || InpMethod==BTC_BREAKOUT_RETEST) ? s.macro : s.trend;
      if(shift==1) latest_ready=true;
     }
   // No entry signal or exit-state value is published on an unfinished candle.
   Buy[0]=Sell[0]=ATR[0]=Direction[0]=EMPTY_VALUE;
   return latest_ready ? rates_total : prev_calculated;
  }
