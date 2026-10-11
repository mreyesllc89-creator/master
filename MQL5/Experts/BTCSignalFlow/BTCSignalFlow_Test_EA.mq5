#property copyright "MQL5-Foundry"
#property version "1.11"
#property strict
#property description "BTC SignalFlow Test EA. Configurable-timeframe breakout strategy for demo and real accounts."
#property description "v1.11: switchable exit / trailing improvements (defaults reproduce v1.10)."

#include <Foundry\SignalFlowTest\xpMoneyManagement.mqh>
#include <Foundry\SignalFlowTest\BTCMethodSignals.mqh>

input group "BTC SignalFlow Test signals"
input ENUM_BTC_METHOD InpMethod=BTC_EFFICIENCY_BREAKOUT;
input ENUM_TIMEFRAMES InpSignalPeriod=PERIOD_CURRENT;

ENUM_TIMEFRAMES g_period;
input int InpBreakoutBars=30;
input int InpExitBars=10;
input double InpMinER=0.20;
input int InpPullbackEMA=20;
input double InpClearanceATR=0.20;
input group "Risk and exits"
input double InpRiskPercent=0.50;
input double InpStopATR=2.50;
input double InpTrailATR=3.50;
input double InpTakeProfitR=4.00;
input int InpMaxHoldBars=0;
input double InpMaxSpreadATR=0.30;
input double InpMaxMarginPct=10;
input int InpSlippagePoints=1000;
input ulong InpMagic=2026101103;

//--- v1.11 improvements. Every default reproduces v1.10 exactly.
enum ENUM_BTC_TRAIL_SOURCE
  {
   BTC_TRAIL_ATR_CLOSE=0,   // Last closed bar close -/+ TrailATR x ATR (v1.10)
   BTC_TRAIL_CHANDELIER=1   // Highest high / lowest low since entry -/+ TrailATR x ATR
  };
enum ENUM_BTC_DIRECTION
  {
   BTC_BOTH=0,              // Long and short
   BTC_LONG_ONLY=1,         // Long only
   BTC_SHORT_ONLY=2         // Short only
  };
input group "v1.11 improvements (defaults = v1.10 behaviour)"
input bool InpUseSignalExit=true;                        // Close on the method's opposite signal state
input ENUM_BTC_TRAIL_SOURCE InpTrailSource=BTC_TRAIL_ATR_CLOSE; // Trailing stop source
input double InpTrailActivateR=0.0;                      // Start trailing only after N x initial risk (0 = at once)
input bool InpUseBreakEven=false;                        // Move SL to entry after N x R
input double InpBreakEvenR=1.0;                          // Break-even trigger (R)
input double InpLockTriggerR=0.0;                        // Lock-in stage: when profit >= N x R ... (0 = off)
input double InpLockR=0.0;                               // ... move SL to entry + N x R (must be < trigger)
input double InpPartialR=0.0;                            // Partial close at N x R (0 = off)
input double InpPartialPercent=50.0;                     // Partial close % of the original volume
input double InpErExit=0.0;                              // Close when the 20-bar efficiency ratio drops below (0 = off)
input ENUM_BTC_DIRECTION InpTradeDirection=BTC_BOTH;     // Allowed direction

CBTCMethodSignals g_signals;
CXPMoneyManager g_money;
datetime g_bar=0;
bool g_exit_pending=false,g_wait_logged=false;
bool g_restore_tick_management=false;
int g_signals_count=0,g_entries=0;

bool Own(ulong &ticket,ulong &id,int &side,datetime &opened)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong t=PositionGetTicket(i);
      if(t==0 || !PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=(long)InpMagic) continue;
      ticket=t; id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? 1 : -1;
      opened=(datetime)PositionGetInteger(POSITION_TIME);
      return true;
     }
   return false;
  }

int OnInit()
  {
   g_period=InpSignalPeriod==PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : InpSignalPeriod;
   if(InpBreakoutBars<1 || InpExitBars<1 || InpPullbackEMA<1 ||
      InpRiskPercent<=0 || InpStopATR<=0 || InpMinER<0 || InpClearanceATR<0 ||
      InpTrailATR<0 || InpTakeProfitR<0 || InpMaxHoldBars<0 ||
      InpMaxSpreadATR<0 || InpMaxMarginPct<0 || InpSlippagePoints<0)
      { Print("Invalid mathematical parameter: periods and risk/stop must be positive; distances cannot be negative."); return INIT_PARAMETERS_INCORRECT; }
   if(InpTrailActivateR<0 || InpBreakEvenR<=0 || InpLockTriggerR<0 || InpLockR<0 ||
      (InpLockTriggerR>0 && InpLockR>=InpLockTriggerR) || InpPartialR<0 ||
      (InpPartialR>0 && (InpPartialPercent<=0 || InpPartialPercent>=100)) || InpErExit<0)
      { Print("Invalid v1.11 parameter: R multiples must be >= 0, lock R < lock trigger, partial percent in (0,100)."); return INIT_PARAMETERS_INCORRECT; }
   BTC_METHOD_CONFIG c;
   c.method=InpMethod; c.period=g_period; c.length=InpBreakoutBars;
   c.exit_bars=InpExitBars;
   c.efficiency=InpMinER; c.pullback_ema=InpPullbackEMA; c.clearance_atr=InpClearanceATR;
   if(!g_signals.Create(_Symbol,c)) return INIT_FAILED;
   XPMM_CONFIG mm; XPMM_Defaults(mm);
   mm.symbol=_Symbol; mm.magic=InpMagic; mm.instance="BTCSignalFlow.Test.v1.11";
   mm.lot_mode=XPMM_PERCENT_EQUITY; mm.value=InpRiskPercent;
   mm.max_margin_percent=InpMaxMarginPct; mm.require_sl=true;
   mm.tp_mode=XPMM_TP_EXTERNAL; mm.exclusive_netting=true;
   mm.deviation_points=InpSlippagePoints;
   mm.trail_mode=InpTrailATR>0 ? XPMM_TRAIL_EXTERNAL : XPMM_TRAIL_OFF;
   mm.trail_step_points=50;
   mm.trail_trigger_unit=XPMM_R;                 // v1.11: optional activation in R
   mm.trail_trigger=InpTrailActivateR>0 ? InpTrailActivateR : 0;
   if(!g_money.Configure(mm)) { Print(g_money.Reason()); g_signals.Release(); return INIT_FAILED; }
   if(InpUseBreakEven)
     {
      XPMM_BE_STAGE be; ZeroMemory(be);
      be.unit=XPMM_R; be.trigger=InpBreakEvenR; be.lock_points=0; be.lock_r=0;
      if(!g_money.AddBreakEven(be)) { Print(g_money.Reason()); g_signals.Release(); return INIT_PARAMETERS_INCORRECT; }
     }
   if(InpLockTriggerR>0)
     {
      XPMM_R_STAGE lock; ZeroMemory(lock);
      lock.trigger_r=InpLockTriggerR; lock.lock_r=InpLockR;
      if(!g_money.AddRTrail(lock)) { Print(g_money.Reason()); g_signals.Release(); return INIT_PARAMETERS_INCORRECT; }
     }
   if(InpPartialR>0)
     {
      XPMM_PARTIAL_STAGE part; ZeroMemory(part);
      part.unit=XPMM_R; part.trigger=InpPartialR; part.percent_original=InpPartialPercent;
      if(!g_money.AddPartial(part)) { Print(g_money.Reason()); g_signals.Release(); return INIT_PARAMETERS_INCORRECT; }
     }
   // The shared manager reloads committed closes from terminal globals.
   // An adopted position gets tick-level retries until it is gone.
   if(!MQLInfoInteger(MQL_TESTER))
     {
      ulong restored_ticket,restored_id; int restored_side; datetime restored_opened;
      g_restore_tick_management=Own(restored_ticket,restored_id,restored_side,restored_opened);
     }
   PrintFormat("BTC_METHOD_READY method=%d period=%d risk=%.2f",InpMethod,g_period,InpRiskPercent);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { g_money.Shutdown(); g_signals.Release(); }
void OnTradeTransaction(const MqlTradeTransaction &tx,const MqlTradeRequest &request,const MqlTradeResult &result)
  { g_money.OnTradeTransaction(tx,request,result); }

//--- v1.11: trailing candidate according to the selected source
double TrailCandidate(const int side,const datetime opened,const BTC_METHOD_SIGNAL &s)
  {
   if(InpTrailATR<=0) return 0;
   if(InpTrailSource==BTC_TRAIL_CHANDELIER)
     {
      int held=iBarShift(_Symbol,g_period,opened,false);
      if(held<1) held=1;
      if(side==1)
        {
         int hi=iHighest(_Symbol,g_period,MODE_HIGH,held,1);
         return hi>=0 ? iHigh(_Symbol,g_period,hi)-InpTrailATR*s.atr : 0;
        }
      int lo=iLowest(_Symbol,g_period,MODE_LOW,held,1);
      return lo>=0 ? iLow(_Symbol,g_period,lo)+InpTrailATR*s.atr : 0;
     }
   return s.close-side*InpTrailATR*s.atr;
  }

void OnTick()
  {
   ulong ticket,id; int side; datetime opened;
   if(g_restore_tick_management)
     {
      if(Own(ticket,id,side,opened))
        {
         g_money.Manage();
         if(!Own(ticket,id,side,opened))
           { g_restore_tick_management=false; g_bar=iTime(_Symbol,g_period,0); return; }
        }
      else g_restore_tick_management=false;
     }
   if(g_exit_pending)
     {
      if(Own(ticket,id,side,opened)) { g_money.Manage(); return; }
      g_exit_pending=false;
     }
   datetime bar=iTime(_Symbol,g_period,0);
   if(bar==0 || bar==g_bar) return;
   BTC_METHOD_SIGNAL s;
   if(!g_signals.Evaluate(1,s) || s.atr<=0)
     {
      if(!g_wait_logged) { Print("BTC_METHOD_WAIT history/indicator data"); g_wait_logged=true; }
      return;
     }
   if(g_wait_logged) { Print("BTC_METHOD_DATA_READY"); g_wait_logged=false; }
   g_bar=bar; g_money.Refresh();
   if(Own(ticket,id,side,opened))
     {
      double trail=TrailCandidate(side,opened,s);
      g_money.SetContext(id,s.atr,trail);
      bool close=false;
      if(InpUseSignalExit)
        {
         if(InpMethod==BTC_RANGE_REVERSION)
            close=side==1 ? s.close>=s.mean : s.close<=s.mean;
         else if(InpMethod==BTC_TREND_PULLBACK || InpMethod==BTC_BREAKOUT_RETEST)
            close=side==1 ? s.macro<0 : s.macro>0;
         else close=side==1 ? s.trend<0 : s.trend>0;
        }
      int age=iBarShift(_Symbol,g_period,opened,false);
      if(InpMaxHoldBars>0 && age>=InpMaxHoldBars) close=true;
      if(InpErExit>0 && s.er<InpErExit) close=true;      // v1.11 efficiency exit
      if(close && g_money.RequestClose(id)) g_exit_pending=true;
      g_money.Manage(); return;
     }
   if(s.side==0) return;
   if((InpTradeDirection==BTC_LONG_ONLY && s.side!=1) || (InpTradeDirection==BTC_SHORT_ONLY && s.side!=-1)) return;
   g_signals_count++;
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING &&
      PositionSelect(_Symbol)) return;
   MqlTick q;
   if(!SymbolInfoTick(_Symbol,q) || q.bid<=0 || q.ask<=q.bid) return;
   if(InpMaxSpreadATR>0 && q.ask-q.bid>InpMaxSpreadATR*s.atr) return;
   double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT),ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(point<=0 || ts<=0) return;
   double minimum=MathMax((double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),
                          (double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*point;
   minimum=MathMax(minimum,ts);
   double entry=s.side==1 ? q.ask : q.bid;
   double sl=s.side==1 ? MathMin(entry-InpStopATR*s.atr,q.bid-minimum) :
                        MathMax(entry+InpStopATR*s.atr,q.ask+minimum);
   sl=NormalizeDouble(s.side==1 ? MathFloor(sl/ts+1e-9)*ts : MathCeil(sl/ts-1e-9)*ts,_Digits);
   if(sl<=0) return;
   double tp=InpTakeProfitR>0 ? entry+s.side*InpTakeProfitR*MathAbs(entry-sl) : 0;
   if(tp>0) tp=NormalizeDouble(s.side==1 ? MathCeil(tp/ts-1e-9)*ts : MathFloor(tp/ts+1e-9)*ts,_Digits);
   XPMM_ENTRY order; ZeroMemory(order);
   order.type=s.side==1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   order.entry=entry; order.sl=sl; order.tp=tp; order.comment="BTCSignalFlow Test";
   XPMM_PLAN plan;
   if(!g_money.SubmitEntry(order,plan)) { Print("BTC_METHOD_SKIP ",g_money.Reason()); return; }
   g_entries++;
   PrintFormat("BTC_METHOD_ENTRY signal=%s decision=%s macro=%s side=%d ER=%.4f lots=%.4f",
               TimeToString(s.time,TIME_DATE|TIME_MINUTES),TimeToString(s.decision_time,TIME_DATE|TIME_MINUTES),
               TimeToString(s.macro_close,TIME_DATE|TIME_MINUTES),s.side,s.er,plan.volume);
  }

double OnTester()
  {
   PrintFormat("BTC_METHOD_COUNTS signals=%d entries=%d",g_signals_count,g_entries);
   return TesterStatistics(STAT_PROFIT);
  }
