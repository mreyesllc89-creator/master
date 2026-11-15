#ifndef XPW_V092_FIXTURE
#property strict
#property version "9.21"
#property description "Supplied XPW v0.9.2 + FlashGold: all 141 Pine settings."
#property tester_indicator "XPW_ShapeMap_v092_FGF_Map.ex5"
#property tester_indicator "XPW_ShapeMap_v092_FGF_Filter.ex5"
#endif
#include <XPW/ShapeMapV92Inputs.mqh>
#include <XPW/ShapeMapV92FgfInputs.mqh>
#include <XPW/ShapeMapV92Execution.mqh>
#include <XPW/ShapeMapV92Runtime.mqh>
#include <XPW/ShapeMapV92Draw.mqh>
#include <XPW/ShapeMapFgdNative.mqh>
#include <XPW/ShapeMapV92TimerPreview.mqh>
#include <XPW/ShapeMapV92DeferredTick.mqh>
XPW_V92_INPUT bool EnableTrading=false; // Explicit broker execution switch (default disabled).
#include <XPW/OnTester_ProfitFactor.mqh> // Profit-factor optimization score (Custom max).
#include <XPW/ShapeMapV92FgfBridge.mqh>

XpwV92Inputs g_v92_config;
XpwV8Inputs g_v92_oldConfig;
XpwV92SignalState g_v92_signalCommitted;
XpwV92ChartState g_v92_chartCommitted,g_v92_chartPreview;
XpwV92PlanState g_v92_planPreview;
XpwV92DrawState g_v92_drawCommitted,g_v92_drawPreview;
XpwV92Payload g_v92_payloads[];
XpwV92ChartBar g_v92_chartBars[];
XpwV7Bar g_v92_numeric[];
XpwV8Bar g_v92_tradeBars[];
MqlRates g_v92_chartRates[],g_v92_signalRates[];
datetime g_v92_times[],g_v92_signalTimes[],g_v92_signalClose[];
double g_v92_open[],g_v92_high[],g_v92_low[],g_v92_close[];
double g_v92_signalOpen[],g_v92_signalHigh[],g_v92_signalLow[],g_v92_signalPrice[];
CXpwV92FgfNativeGateway g_v92_gateway;
CXpwV92Runtime g_v92_runtime;
CXpwV92FrameWriter g_v92_frames;
XpwV92TimerPreviewCache g_v92_timerPreview;
CXpwFgdNativeCache g_v92_fgd;
XpwV8Spec g_v92_spec;
ENUM_TIMEFRAMES g_v92_signalPeriod=PERIOD_CURRENT;
int g_v92_chartSeconds=0,g_v92_signalSeconds=0,g_v92_mapHandle=INVALID_HANDLE;
datetime g_v92_currentBar=0,g_v92_lastConfirmed=0;
bool g_v92_initialized=false,g_v92_busy=false,g_v92_historyDirty=false,g_v92_mathCurrent=false,g_v92_reloadPending=false;
string g_v92_mapName="",g_v92_mapGeometry="";
ulong g_v92_mapRefreshAt=0,g_v92_frameAt=0;
string g_v92_mapPublishStage="NOT_ATTEMPTED";
int g_v92_mapPublishNativeError=0;
double g_v92_quantity=0;
int g_v92_fgfHandle=INVALID_HANDLE;
string g_v92_fgfName="",g_v92_fgfError="";
FgfConfig g_v92_fgfConfig;
FgfVisualConfig g_v92_fgfVisual;
double g_v92_fgfLabelBirth[];
int g_v92_fgfZones=0,g_v92_previousLiveZones=0;
ulong g_v92_fgfQuoteRevision=0;
datetime g_v92_previousVisualBar=0;
bool g_v92_startupPending=true;
bool g_v92_fgfVisualReady=false,g_v92_fgfVisualRebuild=true;
bool g_v92_sourceGap=false;
XpwV92DeferredTick g_v92_deferredTick;
bool g_v92_noMutationUnready=false;
// A19 observations only: at most eight OnTick calculation-outcome lines.
// Values come from the original calls; no reset, retry, source re-read or publish.
bool g_v92_mathDiagActive=false;
int g_v92_mathDiagPrinted=0,g_v92_mathDiagCallError=0,g_v92_mathDiagFailureError=0;
string g_v92_mathDiagStage="",g_v92_mathDiagFailure="",g_v92_mathDiagCountStage="",g_v92_mathDiagTimeStage="";
long g_v92_mathDiagCount=-1,g_v92_mathDiagExpected=-1,g_v92_mathDiagTime=0,g_v92_mathDiagExpectedTime=0;
int g_v92_mathDiagChartBars=-1,g_v92_mathDiagSignalBars=-1;
bool g_v92_mathDiagChartBarsObserved=false,g_v92_mathDiagSignalBarsObserved=false;
int g_v92_mathDiagWorkChartBars=-1,g_v92_mathDiagWorkSignalBars=-1;
bool g_v92_mathDiagWorkChartBarsObserved=false,g_v92_mathDiagWorkSignalBarsObserved=false;
int g_v92_mathDiagChartClockError=0,g_v92_mathDiagSignalClockError=0;
ulong g_v92_mathDiagStarted=0;
void XpwV92MathDiagBegin()
  {
   g_v92_mathDiagActive=g_v92_mathDiagPrinted<8;
   if(!g_v92_mathDiagActive) return;
   g_v92_mathDiagStarted=GetMicrosecondCount();
   g_v92_mathDiagStage="DISPATCH"; g_v92_mathDiagFailure="";
   g_v92_mathDiagCountStage="UNREAD"; g_v92_mathDiagTimeStage="UNREAD";
   g_v92_mathDiagCount=-1; g_v92_mathDiagExpected=-1;
   g_v92_mathDiagTime=0; g_v92_mathDiagExpectedTime=0; g_v92_mathDiagCallError=0; g_v92_mathDiagFailureError=0;
   g_v92_mathDiagChartBars=-1; g_v92_mathDiagSignalBars=-1;
   g_v92_mathDiagChartBarsObserved=false; g_v92_mathDiagSignalBarsObserved=false;
   g_v92_mathDiagWorkChartBars=-1; g_v92_mathDiagWorkSignalBars=-1;
   g_v92_mathDiagWorkChartBarsObserved=false; g_v92_mathDiagWorkSignalBarsObserved=false;
   g_v92_mathDiagChartClockError=0; g_v92_mathDiagSignalClockError=0;
  }
void XpwV92MathDiagStage(const string stage)
  { if(g_v92_mathDiagActive) g_v92_mathDiagStage=stage; }
bool XpwV92MathDiagFailure(const string stage)
  {
   if(g_v92_mathDiagActive && g_v92_mathDiagFailure=="")
     { const int observedError=GetLastError(); g_v92_mathDiagFailureError=observedError; g_v92_mathDiagFailure=stage; }
   return false;
  }
int XpwV92MathDiagCount(const int value,const int expected,const string stage)
  {
   if(g_v92_mathDiagActive)
     {
      const int observedError=GetLastError();
      g_v92_mathDiagCountStage=stage; g_v92_mathDiagCount=value; g_v92_mathDiagExpected=expected;
      g_v92_mathDiagCallError=observedError;
      if(stage=="DISPATCH.chart_bars") { g_v92_mathDiagChartBars=value; g_v92_mathDiagChartBarsObserved=true; }
      else if(stage=="DISPATCH.signal_bars") { g_v92_mathDiagSignalBars=value; g_v92_mathDiagSignalBarsObserved=true; }
      else if(stage=="WORK.chart_bars") { g_v92_mathDiagWorkChartBars=value; g_v92_mathDiagWorkChartBarsObserved=true; }
      else if(stage=="WORK.signal_bars") { g_v92_mathDiagWorkSignalBars=value; g_v92_mathDiagWorkSignalBarsObserved=true; }
     }
   return value;
  }
datetime XpwV92MathDiagClock(const datetime value,const bool chart)
  {
   if(g_v92_mathDiagActive)
     {
      const int observedError=GetLastError();
      if(chart) g_v92_mathDiagChartClockError=observedError;
      else g_v92_mathDiagSignalClockError=observedError;
     }
   return value;
  }
bool XpwV92MathDiagTime(const bool value,const datetime observed,const datetime expected,const string stage)
  {
   if(g_v92_mathDiagActive)
     { g_v92_mathDiagTimeStage=stage; g_v92_mathDiagTime=(long)observed; g_v92_mathDiagExpectedTime=(long)expected; }
   return value;
  }
void XpwV92MathDiagOutcome(const bool complete,const int immediateError,const datetime current,const datetime sourceCurrent,
                            const bool rebuild,const datetime expectedBar,const int chartSize,const int signalSize)
  {
   if(!g_v92_mathDiagActive) return;
   g_v92_mathDiagActive=false; g_v92_mathDiagPrinted++;
   const ulong finished=GetMicrosecondCount();
   Print("XPW_V092_MATH_DIAGNOSTIC owner="+g_v92_frames.Token()+" config="+g_v92_frames.Config(),
      " complete=",complete ? 1 : 0," rebuild=",rebuild ? 1 : 0," current=",(long)current,
      " source_current=",(long)sourceCurrent," expected_bar=",(long)expectedBar,
      " chart_size=",chartSize," signal_size=",signalSize," chart_bars_observed=",g_v92_mathDiagChartBarsObserved ? 1 : 0,
      " chart_bars=",g_v92_mathDiagChartBars," signal_bars_observed=",g_v92_mathDiagSignalBarsObserved ? 1 : 0,
      " signal_bars=",g_v92_mathDiagSignalBars," work_chart_bars_observed=",g_v92_mathDiagWorkChartBarsObserved ? 1 : 0,
      " work_chart_bars=",g_v92_mathDiagWorkChartBars," work_signal_bars_observed=",g_v92_mathDiagWorkSignalBarsObserved ? 1 : 0,
      " work_signal_bars=",g_v92_mathDiagWorkSignalBars," chart_clock_last_error=",g_v92_mathDiagChartClockError,
      " signal_clock_last_error=",g_v92_mathDiagSignalClockError," stage=",g_v92_mathDiagStage,
      " failure=",g_v92_mathDiagFailure," count_stage=",g_v92_mathDiagCountStage,
      " returned=",g_v92_mathDiagCount," expected_count=",g_v92_mathDiagExpected,
      " time_stage=",g_v92_mathDiagTimeStage," observed_time=",g_v92_mathDiagTime,
      " expected_time=",g_v92_mathDiagExpectedTime," call_last_error=",g_v92_mathDiagCallError,
      " failure_last_error=",g_v92_mathDiagFailureError," outcome_last_error=",immediateError," microseconds=",finished," elapsed_us=",finished-g_v92_mathDiagStarted,
      " scope=SAME_CALL_OBSERVATIONS_NO_RESET_NO_RETRY");
  }

// One immutable native observation before this callback's strategy commands.
// This never rewrites planner context or substitutes native fills for Pine fills.
void XpwV92CaptureFgd(const int index,const bool confirmed,const bool inventorySynced)
  {
   if(index<0 || index>=ArraySize(g_v92_chartBars)) return;
   XpwFgdExecutionSnapshot s; if(!g_v92_fgd.Begin(index,s)) return;
   const XpwV92ChartBar b=g_v92_chartBars[index];
   s.phase=confirmed ? FGD_NATIVE_DELAYED : FGD_NATIVE_CURRENT;
   s.canLong=g_v92_config.tradeDir!="Short only"; s.canShort=g_v92_config.tradeDir!="Long only";
   s.reverseOpposite=g_v92_config.oppMode=="Reverse";
   s.contStop=g_v92_config.sigMode=="CONT ▲/▼" && g_v92_config.contEntry=="Stop past signal candle";
   s.turnPredict=g_v92_config.sigMode=="Turn ▲/▼" && g_v92_config.turnEntry=="Predict (stop at cross price)";
   s.catchUp=g_v92_config.catchUp; s.filterDisabled=!fgfOn;
   s.sigBarOK=XpwFgdBool(g_v92_config.enterTick || confirmed); s.confirmed=XpwFgdBool(confirmed);
   s.selectedLong=XpwFgdBool(b.trade.longSig); s.selectedShort=XpwFgdBool(b.trade.shortSig);
   s.contUp=XpwFgdBool(b.events.contUp); s.contDown=XpwFgdBool(b.events.contDn);
   s.armLong=XpwFgdBool(b.trade.armL); s.armShort=XpwFgdBool(b.trade.armS);
   s.crossUpNow=XpwFgdBool(b.trade.crossUpNow); s.crossDownNow=XpwFgdBool(b.trade.crossDnNow);
   s.fast.observed=true; s.fast.value=b.payload.validFast ? b.payload.fast : EMPTY_VALUE;
   s.slow.observed=true; s.slow.value=b.payload.validSlow ? b.payload.slow : EMPTY_VALUE;
   // Each observed stop has its own na semantics; no coupled validPrediction.
   s.stopLong.observed=true; s.stopLong.value=b.trade.stopL;
   s.stopShort.observed=true; s.stopShort.value=b.trade.stopS;
   bool openEntryKnown=false,closedEntryKnown=false; long openEntryMs=0,closedEntryMs=0;
   if(inventorySynced)
      g_v92_runtime.FgdInventory(s.position.observed,s.position.value,s.openTrades.countObserved,s.openTrades.count,
         openEntryKnown,openEntryMs,s.closedTrades.countObserved,s.closedTrades.count,closedEntryKnown,closedEntryMs);
   if(openEntryKnown) s.openTrades.indexObserved=XpwFgdNativeEntryIndex(openEntryMs,g_v92_times,_Period,s.openTrades.lastEntryIndex);
   if(closedEntryKnown) s.closedTrades.indexObserved=XpwFgdNativeEntryIndex(closedEntryMs,g_v92_times,_Period,s.closedTrades.lastEntryIndex);
   bool buy=false,sell=false; int mask=-1; string error;
   const bool ready=XpwV92ReadFgfPermissions(g_v92_fgfHandle,g_v92_times[index],g_v92_fgfQuoteRevision,buy,sell,mask,error);
   s.permissionEpoch=ready && fgfOn ? (long)g_v92_fgfQuoteRevision : 0;
   s.buyAllowed=s.filterDisabled ? 1 : (ready ? XpwFgdBool(buy) : -1);
   s.sellAllowed=s.filterDisabled ? 1 : (ready ? XpwFgdBool(sell) : -1);
   // Diagnostic failure does not veto source protection or broker management.
   if(!g_v92_fgd.Record(s)) { g_v92_fgd.Invalidate(index); Print("XPW_FGD3 capture refused index=",index); }
   if(confirmed) g_v92_historyDirty=true;
  }
bool XpwV92RealtimeSource()
  { return !MQLInfoInteger(MQL_TESTER); }

bool XpwV92FgfVisualSnapshot(const int charts,const datetime oldest,const datetime newest)
  {
   if(charts<1 || iTime(_Symbol,_Period,0)!=newest || iTime(_Symbol,_Period,charts-1)!=oldest) return false;
   double before[],after[],births[],zones[];
   if(!fgfOn)
     {
      if(ArrayResize(births,charts)!=charts) return false;
      ArrayInitialize(births,0); ArraySwap(g_v92_fgfLabelBirth,births); g_v92_fgfZones=0;
      if(CopyBuffer(g_v92_fgfHandle,12,0,1,before)==1 && MathIsValidNumber(before[0]) && before[0]>=0 && before[0]!=EMPTY_VALUE)
         g_v92_fgfQuoteRevision=(ulong)before[0];
      return true;
     }
   if(BarsCalculated(g_v92_fgfHandle)<charts || CopyBuffer(g_v92_fgfHandle,12,0,1,before)!=1 ||
      CopyBuffer(g_v92_fgfHandle,10,0,charts,births)!=charts || CopyBuffer(g_v92_fgfHandle,11,0,1,zones)!=1 ||
      CopyBuffer(g_v92_fgfHandle,12,0,1,after)!=1 || before[0]!=after[0] ||
      !MathIsValidNumber(before[0]) || before[0]==EMPTY_VALUE || before[0]<0 || before[0]!=MathFloor(before[0]) ||
      !MathIsValidNumber(zones[0]) || (zones[0]!=0 && zones[0]!=2 && zones[0]!=3) ||
      iTime(_Symbol,_Period,0)!=newest || iTime(_Symbol,_Period,charts-1)!=oldest) return false;
   for(int i=0;i<charts;i++) if(births[i]!=0 && births[i]!=1) return false;
   ArraySwap(g_v92_fgfLabelBirth,births);
   g_v92_fgfZones=(int)zones[0]; g_v92_fgfQuoteRevision=(ulong)before[0];
   return true;
  }
void XpwV92ObserveFgfVisuals(const int charts,const datetime oldest,const datetime newest)
  {
   g_v92_fgfVisualReady=XpwV92FgfVisualSnapshot(charts,oldest,newest);
   if(!g_v92_fgfVisualReady) g_v92_fgfVisualRebuild=true;
  }
bool XpwV92FgfLabelBirth(const int index)
  { return g_v92_fgfVisualReady && index>=0 && index<ArraySize(g_v92_fgfLabelBirth) && g_v92_fgfLabelBirth[index]>0; }
bool XpwV92RebuildFgfDraw()
  {
   if(!g_v92_fgfVisualReady) return false;
   const int last=ArraySize(g_v92_times)-1;
   if(last<1 || ArraySize(g_v92_fgfLabelBirth)!=last+1) return false;
   XpwV92DrawState committed,candidate; ZeroMemory(committed);
   for(int i=0;i<last;i++)
      if(!XpwV92DrawFgfApply(g_v92_config,i,g_v92_chartSeconds,g_v92_times,g_v92_chartBars[i],committed,
                            XpwV92FgfLabelBirth(i),false,0)) return false;
   if(!XpwV92DrawEvaluateFgf(g_v92_config,last,g_v92_chartSeconds,g_v92_times,g_v92_chartBars[last],committed,candidate,
                           XpwV92FgfLabelBirth(last),true,g_v92_fgfZones)) return false;
   g_v92_drawCommitted=committed; g_v92_drawPreview=candidate; g_v92_fgfVisualRebuild=false;
   g_v92_previousVisualBar=g_v92_times[last]; g_v92_previousLiveZones=g_v92_fgfZones;
   return true;
  }

bool XpwV92AttachFgf()
  {
   g_v92_fgfHandle=XpwV92CreateFgfHandle(g_v92_frames.Token(),g_v92_frames.Config());
   if(g_v92_fgfHandle==INVALID_HANDLE) return false;
   const int before=ChartIndicatorsTotal(0,0);
   if(!ChartIndicatorAdd(0,0,g_v92_fgfHandle)) return false;
   const int after=ChartIndicatorsTotal(0,0);
   if(after!=before+1) return false;
   g_v92_fgfName=ChartIndicatorName(0,0,after-1);
   return g_v92_fgfName!="";
  }

int XpwV92EntryIndex(const int index,const datetime entry)
  {
   if(entry<=0) return index;
   for(int i=index;i>=0;i--) if(g_v92_times[i]<=entry) return i;
   return index>=499 ? 0 : -1;
  }
bool XpwV92CurrentExit(const int index,XpwV8Exit &x)
  {
   const bool has=g_v92_runtime.Count()>0;
   const int anchor=has && g_v92_runtime.EntryBar()>g_v92_times[index] ? ArraySize(g_v92_tradeBars)-1 : index;
   const int entry=has ? XpwV92EntryIndex(anchor,g_v92_runtime.EntryBar()) : anchor;
   return XpwV8ExitDistances(g_v92_oldConfig,anchor,has,entry,g_v92_spec.tickSize,g_v92_tradeBars,x);
  }
bool XpwV92EvaluateCurrentSignal()
  {
   XpwV92MathDiagStage("XpwV92EvaluateCurrentSignal");
   const int index=ArraySize(g_v92_signalTimes)-1; MqlRates last[];
   if(index<0 || XpwV92MathDiagCount(CopyRates(_Symbol,g_v92_signalPeriod,0,1,last),1,"XpwV92EvaluateCurrentSignal.CopyRates.signal_last")!=1 || XpwV92MathDiagTime(last[0].time!=g_v92_signalTimes[index],last[0].time,g_v92_signalTimes[index],"XpwV92EvaluateCurrentSignal.last_time")) return XpwV92MathDiagFailure("XpwV92EvaluateCurrentSignal.false_1");
   g_v92_signalRates[index]=last[0]; g_v92_signalOpen[index]=last[0].open; g_v92_signalHigh[index]=last[0].high;
   g_v92_signalLow[index]=last[0].low; g_v92_signalPrice[index]=last[0].close;
   XpwV92SignalState candidate;
   XpwV92MathDiagStage("XpwV92EvaluateCurrentSignal.evaluate");
   return XpwV92SignalEvaluate(g_v92_config,index,false,g_v92_signalTimes,g_v92_signalOpen,g_v92_signalHigh,g_v92_signalLow,
                              g_v92_signalPrice,g_v92_numeric,g_v92_signalCommitted,candidate,g_v92_payloads[index]);
  }
bool XpwV92EvaluateCurrentChart()
  {
   XpwV92MathDiagStage("XpwV92EvaluateCurrentChart");
   const int index=ArraySize(g_v92_times)-1; MqlTick tick;
   if(index<1 || !g_v92_gateway.Quote(tick)) return XpwV92MathDiagFailure("XpwV92EvaluateCurrentChart.false_1");
   const int source=XpwV92RelayIndex(g_v92_times[index],XpwV92BarClose(g_v92_times[index],_Period),tick.time,XpwV92RealtimeSource(),g_v92_signalTimes,g_v92_signalClose);
   XpwV92Payload payload; XpwV92PayloadReset(payload);
   if(source>=0) payload=g_v92_payloads[source];
   if(!XpwV92ChartEvaluate(g_v92_config,index,false,g_v92_chartSeconds,g_v92_signalSeconds,g_v92_spec.tickSize,
                         g_v92_times,g_v92_open,g_v92_high,g_v92_low,g_v92_close,payload,g_v92_chartCommitted,g_v92_chartPreview,
                         g_v92_tradeBars,g_v92_chartBars[index])) return XpwV92MathDiagFailure("XpwV92EvaluateCurrentChart.false_2");
   if(!XpwV92DrawEvaluateFgf(g_v92_config,index,g_v92_chartSeconds,g_v92_times,g_v92_chartBars[index],g_v92_drawCommitted,g_v92_drawPreview,
                           XpwV92FgfLabelBirth(index),true,g_v92_fgfVisualReady ? g_v92_fgfZones : 0)) return XpwV92MathDiagFailure("XpwV92EvaluateCurrentChart.false_3");
   g_v92_previousVisualBar=g_v92_times[index]; g_v92_previousLiveZones=g_v92_fgfZones;
   g_v92_fgd.Invalidate(index);
   return true;
  }
bool XpwV92History(const bool initialize)
  {
   XpwV92MathDiagStage("XpwV92History");
   const int charts=XpwV92MathDiagCount(Bars(_Symbol,_Period),-1,"WORK.chart_bars"),signals=XpwV92MathDiagCount(Bars(_Symbol,g_v92_signalPeriod),-1,"WORK.signal_bars");
   if(charts<2 || signals<1) return XpwV92MathDiagFailure("XpwV92History.false_1");
   ArraySetAsSeries(g_v92_chartRates,false); ArraySetAsSeries(g_v92_signalRates,false);
   if(XpwV92MathDiagCount(CopyRates(_Symbol,_Period,0,charts,g_v92_chartRates),charts,"XpwV92History.CopyRates.chart_history")!=charts) return XpwV92MathDiagFailure("XpwV92History.false_2");
   if(g_v92_signalPeriod==_Period) { ArrayResize(g_v92_signalRates,charts); ArrayCopy(g_v92_signalRates,g_v92_chartRates); }
   else if(XpwV92MathDiagCount(CopyRates(_Symbol,g_v92_signalPeriod,0,signals,g_v92_signalRates),signals,"XpwV92History.CopyRates.signal_history")!=signals) return XpwV92MathDiagFailure("XpwV92History.false_3");
   const int actualSignals=ArraySize(g_v92_signalRates);
   XpwV92ObserveFgfVisuals(charts,g_v92_chartRates[0].time,g_v92_chartRates[charts-1].time);
   ArrayResize(g_v92_times,charts); ArrayResize(g_v92_open,charts); ArrayResize(g_v92_high,charts); ArrayResize(g_v92_low,charts); ArrayResize(g_v92_close,charts);
   ArrayResize(g_v92_chartBars,charts); ArrayResize(g_v92_tradeBars,charts);
   ArrayResize(g_v92_signalTimes,actualSignals); ArrayResize(g_v92_signalClose,actualSignals);
   ArrayResize(g_v92_signalOpen,actualSignals); ArrayResize(g_v92_signalHigh,actualSignals); ArrayResize(g_v92_signalLow,actualSignals); ArrayResize(g_v92_signalPrice,actualSignals);
   ArrayResize(g_v92_numeric,actualSignals); ArrayResize(g_v92_payloads,actualSignals);
   for(int i=0;i<charts;i++)
     {
      g_v92_times[i]=g_v92_chartRates[i].time; g_v92_open[i]=g_v92_chartRates[i].open; g_v92_high[i]=g_v92_chartRates[i].high;
      g_v92_low[i]=g_v92_chartRates[i].low; g_v92_close[i]=g_v92_chartRates[i].close;
      if(g_v92_times[i]<=0 || (i>0 && g_v92_times[i]<=g_v92_times[i-1])) return XpwV92MathDiagFailure("XpwV92History.false_4");
     }
   for(int i=0;i<actualSignals;i++)
     {
      g_v92_signalTimes[i]=g_v92_signalRates[i].time; g_v92_signalClose[i]=XpwV92BarClose(g_v92_signalTimes[i],g_v92_signalPeriod);
      g_v92_signalOpen[i]=g_v92_signalRates[i].open; g_v92_signalHigh[i]=g_v92_signalRates[i].high;
      g_v92_signalLow[i]=g_v92_signalRates[i].low; g_v92_signalPrice[i]=g_v92_signalRates[i].close;
     }
   string error; if(!XpwV92ValidateClock(g_v92_signalTimes,g_v92_signalClose,error)) return XpwV92MathDiagFailure("XpwV92History.false_5");
   XpwV92SignalReset(g_v92_signalCommitted); XpwV92SignalState signalCandidate;
   for(int i=0;i<actualSignals-1;i++)
     {
      if(!XpwV92SignalEvaluate(g_v92_config,i,true,g_v92_signalTimes,g_v92_signalOpen,g_v92_signalHigh,g_v92_signalLow,
                               g_v92_signalPrice,g_v92_numeric,g_v92_signalCommitted,signalCandidate,g_v92_payloads[i])) return XpwV92MathDiagFailure("XpwV92History.false_6");
      g_v92_signalCommitted=signalCandidate;
     }
   if(!XpwV92EvaluateCurrentSignal()) return XpwV92MathDiagFailure("XpwV92History.false_7");
   XpwV92ChartReset(g_v92_chartCommitted); ZeroMemory(g_v92_drawCommitted);
   XpwV92ChartState chartCandidate;
   for(int i=0;i<charts-1;i++)
     {
      const int source=XpwV92RelayIndex(g_v92_times[i],XpwV92BarClose(g_v92_times[i],_Period),g_v92_times[i],false,g_v92_signalTimes,g_v92_signalClose);
      XpwV92Payload payload; XpwV92PayloadReset(payload);
      if(source>=0) payload=g_v92_payloads[source];
      if(!XpwV92ChartEvaluate(g_v92_config,i,true,g_v92_chartSeconds,g_v92_signalSeconds,g_v92_spec.tickSize,g_v92_times,g_v92_open,
                            g_v92_high,g_v92_low,g_v92_close,payload,g_v92_chartCommitted,chartCandidate,g_v92_tradeBars,g_v92_chartBars[i])) return XpwV92MathDiagFailure("XpwV92History.false_8");
      if(!XpwV92DrawFgfApply(g_v92_config,i,g_v92_chartSeconds,g_v92_times,g_v92_chartBars[i],g_v92_drawCommitted,
                            XpwV92FgfLabelBirth(i),false,0)) return XpwV92MathDiagFailure("XpwV92History.false_9");
      g_v92_chartCommitted=chartCandidate;
     }
   g_v92_currentBar=g_v92_times[charts-1];
   if(initialize) g_v92_lastConfirmed=g_v92_times[charts-2];
   g_v92_historyDirty=true;
   if(!XpwV92EvaluateCurrentChart()) return XpwV92MathDiagFailure("XpwV92History.false_10");
   // Reload has no historical execution/position tape: every old FGD row is unknown.
   if(!g_v92_fgd.Reset(g_v92_times)) Print("XPW_FGD3 history cohort unavailable");
   return true;
  }
bool XpwV92Preview()
  {
   XpwV92MathDiagStage("XpwV92Preview");
   const int index=ArraySize(g_v92_times)-1; MqlRates last[];
   if(index<1 || XpwV92MathDiagCount(CopyRates(_Symbol,_Period,0,1,last),1,"XpwV92Preview.CopyRates.chart_last")!=1 || XpwV92MathDiagTime(last[0].time!=g_v92_currentBar,last[0].time,g_v92_currentBar,"XpwV92Preview.last_time") || !XpwV92EvaluateCurrentSignal()) return XpwV92MathDiagFailure("XpwV92Preview.false_1");
   XpwV92ObserveFgfVisuals(index+1,g_v92_times[0],g_v92_times[index]);
   g_v92_chartRates[index]=last[0]; g_v92_open[index]=last[0].open; g_v92_high[index]=last[0].high;
   g_v92_low[index]=last[0].low; g_v92_close[index]=last[0].close;
   return XpwV92EvaluateCurrentChart();
  }

// Ordinary appends must preserve values committed while an HTF candle was
// developing. Rebuilding these chart bars through historical security would
// repaint their seen stamps/counters/stop[1] during an otherwise running EA.
// A true historical-prefix/correction reload remains a separate full rebuild.
bool XpwV92ReloadHistory()
  {
   XpwV92MathDiagStage("XpwV92ReloadHistory");
   g_v92_reloadPending=true;
   const bool complete=XpwV92History(false);
   if(complete) g_v92_reloadPending=false;
   return complete;
  }
bool XpwV92AppendHistory()
  {
   XpwV92MathDiagStage("XpwV92AppendHistory");
   const int oldCharts=ArraySize(g_v92_times),oldSignals=ArraySize(g_v92_signalTimes);
   const int charts=XpwV92MathDiagCount(Bars(_Symbol,_Period),-1,"WORK.chart_bars"),signals=XpwV92MathDiagCount(Bars(_Symbol,g_v92_signalPeriod),-1,"WORK.signal_bars");
   // A22: a transient absent series is not a positive history-shrink observation.
   // No arrays/committed state/reload flag have changed on this refusal path.
   if(charts<2 || signals<1) { g_v92_noMutationUnready=true; return false; }
   if(g_v92_reloadPending) return XpwV92ReloadHistory();
   if(oldCharts<2 || oldSignals<1 || charts<oldCharts || signals<oldSignals) return XpwV92ReloadHistory();
   MqlRates incomingChart[],incomingSignal[]; ArraySetAsSeries(incomingChart,false); ArraySetAsSeries(incomingSignal,false);
   if(XpwV92MathDiagCount(CopyRates(_Symbol,_Period,0,charts,incomingChart),charts,"XpwV92AppendHistory.CopyRates.chart_incoming")!=charts) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_1");
   if(g_v92_signalPeriod==_Period) { if(ArrayResize(incomingSignal,charts)!=charts || ArrayCopy(incomingSignal,incomingChart)!=charts) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_2"); }
   else if(XpwV92MathDiagCount(CopyRates(_Symbol,g_v92_signalPeriod,0,signals,incomingSignal),signals,"XpwV92AppendHistory.CopyRates.signal_incoming")!=signals) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_3");
   bool stable=true;
   for(int i=0;i<oldCharts;i++)
      if(incomingChart[i].time!=g_v92_times[i] || (i<oldCharts-1 &&
         (incomingChart[i].open!=g_v92_open[i] || incomingChart[i].high!=g_v92_high[i] ||
          incomingChart[i].low!=g_v92_low[i] || incomingChart[i].close!=g_v92_close[i]))) { stable=false; break; }
   for(int i=0;i<oldSignals && stable;i++)
      if(incomingSignal[i].time!=g_v92_signalTimes[i] || (i<oldSignals-1 &&
         (incomingSignal[i].open!=g_v92_signalOpen[i] || incomingSignal[i].high!=g_v92_signalHigh[i] ||
          incomingSignal[i].low!=g_v92_signalLow[i] || incomingSignal[i].close!=g_v92_signalPrice[i]))) { stable=false; break; }
   if(!stable)
     { g_v92_runtime.Log("HISTORY_RELOAD",0,"Historical prefix/OHLC changed; native historical rebuild"); return XpwV92ReloadHistory(); }
   XpwV92ObserveFgfVisuals(charts,incomingChart[0].time,incomingChart[charts-1].time);
   MqlTick tick; if(!g_v92_gateway.Quote(tick)) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_4");
   // Nothing below mutates the admitted globals until every calculation has
   // succeeded. A quote/copy/evaluation failure can therefore be retried
   // without advancing the current-bar marker or partially committing state.
   datetime times[],signalTimes[],signalClose[];
   double open[],high[],low[],close[],signalOpen[],signalHigh[],signalLow[],signalPrice[];
   XpwV7Bar numeric[]; XpwV8Bar tradeBars[];
   XpwV92Payload payloads[]; XpwV92ChartBar chartBars[];
   if(ArrayResize(times,charts)!=charts || ArrayResize(open,charts)!=charts || ArrayResize(high,charts)!=charts
      || ArrayResize(low,charts)!=charts || ArrayResize(close,charts)!=charts
      || ArrayResize(signalTimes,signals)!=signals || ArrayResize(signalClose,signals)!=signals
      || ArrayResize(signalOpen,signals)!=signals || ArrayResize(signalHigh,signals)!=signals
      || ArrayResize(signalLow,signals)!=signals || ArrayResize(signalPrice,signals)!=signals) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_5");
   if(ArrayCopy(numeric,g_v92_numeric)!=oldSignals || ArrayResize(numeric,signals)!=signals
      || ArrayCopy(payloads,g_v92_payloads)!=oldSignals || ArrayResize(payloads,signals)!=signals
      || ArrayCopy(tradeBars,g_v92_tradeBars)!=oldCharts || ArrayResize(tradeBars,charts)!=charts
      || ArrayCopy(chartBars,g_v92_chartBars)!=oldCharts || ArrayResize(chartBars,charts)!=charts) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_6");
   for(int i=0;i<charts;i++)
     {
      times[i]=incomingChart[i].time; open[i]=incomingChart[i].open; high[i]=incomingChart[i].high;
      low[i]=incomingChart[i].low; close[i]=incomingChart[i].close;
      if(times[i]<=0 || (i>0 && times[i]<=times[i-1])) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_7");
     }
   for(int i=0;i<signals;i++)
     {
      signalTimes[i]=incomingSignal[i].time; signalClose[i]=XpwV92BarClose(signalTimes[i],g_v92_signalPeriod);
      signalOpen[i]=incomingSignal[i].open; signalHigh[i]=incomingSignal[i].high;
      signalLow[i]=incomingSignal[i].low; signalPrice[i]=incomingSignal[i].close;
     }
   string error; if(!XpwV92ValidateClock(signalTimes,signalClose,error)) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_8");
   XpwV92SignalState signalCommitted=g_v92_signalCommitted,signalCandidate;
   XpwV92ChartState chartCommitted=g_v92_chartCommitted,chartCandidate,chartPreview;
   XpwV92DrawState drawCommitted=g_v92_drawCommitted,drawPreview;
   for(int i=oldSignals-1;i<signals-1;i++)
     {
      if(!XpwV92SignalEvaluate(g_v92_config,i,true,signalTimes,signalOpen,signalHigh,signalLow,
                              signalPrice,numeric,signalCommitted,signalCandidate,payloads[i])) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_9");
      signalCommitted=signalCandidate;
     }
   if(!XpwV92SignalEvaluate(g_v92_config,signals-1,false,signalTimes,signalOpen,signalHigh,signalLow,
                           signalPrice,numeric,signalCommitted,signalCandidate,payloads[signals-1])) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_10");
   const XpwV92Payload priorLivePayload=g_v92_payloads[oldSignals-1];
   const datetime priorSourceOpen=g_v92_signalTimes[oldSignals-1],priorSourceClose=g_v92_signalClose[oldSignals-1];
   for(int i=oldCharts-1;i<charts-1;i++)
     {
      const datetime closeTime=XpwV92BarClose(times[i],_Period);
      XpwV92Payload payload; XpwV92PayloadReset(payload);
      // Only a chart bar actually observed while this source bar was live
      // receives its last observed candidate. Missed bars are reconstructed
      // historically; they are not assigned a fabricated realtime payload.
      if(XpwV92RealtimeSource() && i==oldCharts-1 && priorSourceOpen<closeTime && priorSourceClose>closeTime)
         payload=priorLivePayload;
      else
        {
         const int source=XpwV92RelayIndex(times[i],closeTime,times[i],false,signalTimes,signalClose);
         if(source>=0) payload=payloads[source];
        }
      if(!XpwV92ChartEvaluate(g_v92_config,i,true,g_v92_chartSeconds,g_v92_signalSeconds,g_v92_spec.tickSize,
                            times,open,high,low,close,payload,chartCommitted,chartCandidate,tradeBars,chartBars[i])) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_11");
      const bool wasLive=times[i]==g_v92_previousVisualBar;
      if(!XpwV92DrawFgfApply(g_v92_config,i,g_v92_chartSeconds,times,chartBars[i],drawCommitted,
                            XpwV92FgfLabelBirth(i),wasLive,wasLive ? g_v92_previousLiveZones : 0)) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_12");
      chartCommitted=chartCandidate;
     }
   const int current=charts-1;
   const int source=XpwV92RelayIndex(times[current],XpwV92BarClose(times[current],_Period),tick.time,XpwV92RealtimeSource(),signalTimes,signalClose);
   XpwV92Payload payload; XpwV92PayloadReset(payload); if(source>=0) payload=payloads[source];
   if(!XpwV92ChartEvaluate(g_v92_config,current,false,g_v92_chartSeconds,g_v92_signalSeconds,g_v92_spec.tickSize,
                         times,open,high,low,close,payload,chartCommitted,chartPreview,tradeBars,chartBars[current])) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_13");
   if(!XpwV92DrawEvaluateFgf(g_v92_config,current,g_v92_chartSeconds,times,chartBars[current],drawCommitted,drawPreview,
                           XpwV92FgfLabelBirth(current),true,g_v92_fgfVisualReady ? g_v92_fgfZones : 0)) return XpwV92MathDiagFailure("XpwV92AppendHistory.false_14");
   ArraySwap(g_v92_chartRates,incomingChart); ArraySwap(g_v92_signalRates,incomingSignal);
   ArraySwap(g_v92_times,times); ArraySwap(g_v92_open,open); ArraySwap(g_v92_high,high); ArraySwap(g_v92_low,low); ArraySwap(g_v92_close,close);
   ArraySwap(g_v92_signalTimes,signalTimes); ArraySwap(g_v92_signalClose,signalClose);
   ArraySwap(g_v92_signalOpen,signalOpen); ArraySwap(g_v92_signalHigh,signalHigh); ArraySwap(g_v92_signalLow,signalLow); ArraySwap(g_v92_signalPrice,signalPrice);
   ArraySwap(g_v92_numeric,numeric); ArraySwap(g_v92_payloads,payloads); ArraySwap(g_v92_tradeBars,tradeBars); ArraySwap(g_v92_chartBars,chartBars);
   g_v92_signalCommitted=signalCommitted; g_v92_chartCommitted=chartCommitted; g_v92_chartPreview=chartPreview;
   g_v92_drawCommitted=drawCommitted; g_v92_drawPreview=drawPreview;
   if(!g_v92_fgd.Align(g_v92_times,oldCharts-1)) Print("XPW_FGD3 append cohort unavailable");
   if(charts>oldCharts) g_v92_historyDirty=true;
   g_v92_currentBar=g_v92_times[current];
   g_v92_previousVisualBar=g_v92_times[current]; g_v92_previousLiveZones=g_v92_fgfZones;
   return true;
  }
bool XpwV92Process(const int index,const bool confirmed,const bool protectionOnly=false)
  {
   if(index<0 || index>=ArraySize(g_v92_chartBars) || !g_v92_runtime.Sync()
      || !g_v92_runtime.AdmitHistory(index,g_v92_times) || !g_v92_runtime.RebaseChartState(g_v92_times,index)
      || !g_v92_runtime.SourceReady()) return false;
   const XpwV92ChartBar b=g_v92_chartBars[index]; XpwV8Exit exit;
   if(!XpwV92CurrentExit(index,exit)) return false;
   XpwV92Context context; ZeroMemory(context);
   int permissionMask=-1; string filterError;
   const bool filterReady=XpwV92ReadFgfPermissions(g_v92_fgfHandle,g_v92_times[index],g_v92_fgfQuoteRevision,context.fgfBuyOk,context.fgfSellOk,permissionMask,filterError);
   if(!filterReady)
     {
      // Unready filter data blocks entries, not source close/protective paths.
      if(filterError!=g_v92_fgfError) g_v92_runtime.Log("FGF_NOT_READY",GetLastError(),filterError);
      g_v92_fgfError=filterError;
     }
   else g_v92_fgfError="";
   context.chartIndex=index; context.turnHoldChart=XpwV92Offset(g_v92_config.turnHold,g_v92_signalSeconds,g_v92_chartSeconds);
   context.source.confirmed=confirmed; context.source.longSig=b.trade.longSig; context.source.shortSig=b.trade.shortSig;
   context.source.armL=b.trade.armL; context.source.armS=b.trade.armS;
   context.source.crossUp=b.trade.crossUpNow; context.source.crossDn=b.trade.crossDnNow;
   context.source.fast=b.payload.fast; context.source.slow=b.payload.slow; context.source.validLines=b.payload.validFast && b.payload.validSlow;
   context.source.close=g_v92_close[index]; context.source.position=g_v92_runtime.Position();
   context.source.stopL=b.trade.stopL; context.source.stopS=b.trade.stopS; context.source.validPrediction=b.trade.validPrediction;
   context.source.enteredThisBar=g_v92_runtime.LastEntryBar()==g_v92_times[index]; context.source.tickSize=g_v92_spec.tickSize;
   if(context.source.position!=0)
     {
      if(g_v92_runtime.EntryBar()>g_v92_times[index]) context.source.heldBars=-1;
      else { bool exact=false; if(!XpwV92HeldTimeStop(g_v92_runtime.EntryBar(),index,g_v92_times,g_v92_config.timeStop,context.source.heldBars,exact)) return false; }
     }
   if(index>0)
     { context.source.validPreviousPrediction=g_v92_tradeBars[index-1].validPrediction; context.source.previousStopL=g_v92_tradeBars[index-1].stopL; context.source.previousStopS=g_v92_tradeBars[index-1].stopS; }
   context.contUp=b.events.contUp; context.contDn=b.events.contDn;
   context.contUpHi=b.payload.contUpHi; context.contDnLo=b.payload.contDnLo;
   context.validContUpHi=b.payload.contUpT!=0 && b.payload.contUpHi!=EMPTY_VALUE && MathIsValidNumber(b.payload.contUpHi);
   context.validContDnLo=b.payload.contDnT!=0 && b.payload.contDnLo!=EMPTY_VALUE && MathIsValidNumber(b.payload.contDnLo);
   context.closedTradeCount=g_v92_runtime.ClosedTradeCount(); g_v92_runtime.LatestClosed(context.lastClosed);
   context.sourceSignalTime=(datetime)((b.events.contUp ? b.payload.contUpT : (b.events.contDn ? b.payload.contDnT : 0))/1000);
   if(!filterReady || protectionOnly)
     {
      XpwV92Command protective[];
      XpwV92BuildProtectionPlan(g_v92_config,context,protective);
      g_v92_runtime.Execute(protective,g_v92_times[index],index,exit);
      return false; // Retry this confirmed source bar; do not consume its state.
     }
   MqlTick tick; if(!g_v92_gateway.Quote(tick)) return false;
   XpwV92EntryQuantities quantities; quantities.buy=0; quantities.sell=0;
   bool buyValid=false,sellValid=false;
   string buyReason="",sellReason="";
   XpwV92ValueEntryQuantities(g_v92_oldConfig,g_v92_gateway,g_v92_spec,tick,context.source.close,exit.validSl ? exit.slTk : 0,quantities,buyValid,sellValid,buyReason,sellReason);
   if(!buyValid) g_v92_runtime.Log("QTY_ERROR",0,"BUY: "+buyReason);
   if(!sellValid) g_v92_runtime.Log("QTY_ERROR",0,"SELL: "+sellReason);
   // Existing single-value preview only. This heuristic never sizes commands.
   const int displaySide=b.trade.longSig || (b.trade.turnPredict && context.source.validLines && b.payload.fast<b.payload.slow) || (b.isCont && b.events.contUp) ? 1 : -1;
   g_v92_quantity=displaySide>0 ? quantities.buy : quantities.sell;
   XpwV92PlanState committed,candidate; g_v92_runtime.PlanState(committed); XpwV92Command commands[];
   if(!XpwV92BuildPlan(g_v92_config,context,quantities,committed,candidate,commands)) { g_v92_runtime.Log("SOURCE_REFUSED",0,"Incomplete latest closed-trade snapshot"); return false; }
   g_v92_planPreview=candidate;
   g_v92_runtime.Execute(commands,g_v92_times[index],index,exit);
   // Counters/seen reflect source command emission, not an invented native
   // fill. Native accepted/rejected requests retain their own journal/state.
   if(confirmed && !g_v92_runtime.CommitPlanState(candidate,g_v92_times[index],index))
     { g_v92_runtime.Log("STATE_ERROR",0,"Confirmed source plan persistence failed"); return false; }
   return true;
  }
bool XpwV92MapPublicationRefused(const string stage,const int nativeError=0)
  { XpwV92TimerPreviewReset(g_v92_timerPreview); g_v92_mapPublishStage=stage; g_v92_mapPublishNativeError=nativeError; return false; }
bool XpwV92PublishMap(const bool force=false,const bool timerOnly=false)
  {
   g_v92_mapPublishStage="OK"; g_v92_mapPublishNativeError=0;
   // OnTick and forced publications keep their original publication path.
   if(!timerOnly || force) XpwV92TimerPreviewReset(g_v92_timerPreview);
   if(!g_v92_fgfVisualReady) return XpwV92MapPublicationRefused("FGF_VISUAL_NOT_READY");
   if(g_v92_fgfVisualRebuild) XpwV92TimerPreviewReset(g_v92_timerPreview);
   if(g_v92_fgfVisualRebuild && !XpwV92RebuildFgfDraw()) return XpwV92MapPublicationRefused("FGF_DRAW_REBUILD");
   const ulong now=GetTickCount64(); if(!timerOnly && !force && now-g_v92_frameAt<250) return true;
   const int index=ArraySize(g_v92_times)-1;
   if(index<1) return XpwV92MapPublicationRefused("INSUFFICIENT_CHART_HISTORY");
   // A timer must not turn a failed/stale source observation into a fresh
   // complete frame. Unchanged bars may be repainted without quotes, but a
   // changed chart/source clock requires a successful numerical evaluation.
   const int signalIndex=ArraySize(g_v92_signalTimes)-1;
   if(!g_v92_mathCurrent) return XpwV92MapPublicationRefused("SOURCE_MATH_NOT_CURRENT");
   if(signalIndex<0) return XpwV92MapPublicationRefused("INSUFFICIENT_SIGNAL_HISTORY");
   ResetLastError(); const datetime chartNow=iTime(_Symbol,_Period,0); const int chartError=GetLastError();
   if(chartNow!=g_v92_times[index])
      return XpwV92MapPublicationRefused("CHART_CLOCK expected="+(string)(long)g_v92_times[index]+" actual="+(string)(long)chartNow,chartError);
   ResetLastError(); const datetime signalNow=iTime(_Symbol,g_v92_signalPeriod,0); const int signalError=GetLastError();
   if(signalNow!=g_v92_signalTimes[signalIndex])
      return XpwV92MapPublicationRefused("SIGNAL_CLOCK expected="+(string)(long)g_v92_signalTimes[signalIndex]+" actual="+(string)(long)signalNow,signalError);
   if(g_v92_historyDirty)
     {
      XpwV92TimerPreviewReset(g_v92_timerPreview);
      const string historyBody=XpwFgdHistoryBody(index,g_v92_times,g_v92_tradeBars,g_v92_fgd);
      ResetLastError();
      if(!g_v92_frames.History(historyBody)) return XpwV92MapPublicationRefused("HISTORY_FRAME last_native_error",GetLastError());
      g_v92_historyDirty=false;
     }
   const string body=XpwFgdPreviewBody(g_v92_config,index,_Period,g_v92_times,g_v92_chartBars[index],g_v92_chartPreview,g_v92_planPreview,g_v92_drawPreview,g_v92_quantity,g_v92_fgfQuoteRevision,g_v92_fgd);
   XpwV92FrameIdentity timerIdentity; ZeroMemory(timerIdentity);
   if(timerOnly && !force)
     {
      timerIdentity.chart=ChartID(); timerIdentity.symbol=_Symbol; timerIdentity.period=_Period;
      timerIdentity.token=g_v92_frames.Token(); timerIdentity.config=g_v92_frames.Config();
      if(XpwV92TimerPreviewKey(g_v92_timerPreview,timerIdentity,g_v92_frames.HistoryGeneration(),chartNow,signalNow,body))
        {
         // Never infer validity from the cache: re-read the current complete,
         // fresh owned preview plus its exact referenced history before skipping.
         XpwV92FrameEnvelope observed,observedHistory;
         const bool verified=XpwV92LatestFrame(timerIdentity,observed,observedHistory);
         if(XpwV92TimerPreviewSkip(g_v92_timerPreview,timerIdentity,g_v92_frames.HistoryGeneration(),chartNow,signalNow,body,
                                  GetTickCount64(),verified,observed,observedHistory)) return true;
        }
      XpwV92TimerPreviewReset(g_v92_timerPreview);
     }
   ResetLastError();
   if(!g_v92_frames.Preview(body)) return XpwV92MapPublicationRefused("PREVIEW_FRAME last_native_error",GetLastError());
   g_v92_frameAt=now;
   if(timerOnly && !force)
     {
      XpwV92FrameEnvelope published,publishedHistory;
      const bool verified=XpwV92LatestFrame(timerIdentity,published,publishedHistory);
      // A failed readback only disables coalescing; it does not fabricate a
      // failure for the already successful original Preview publication.
      XpwV92TimerPreviewRemember(g_v92_timerPreview,timerIdentity,g_v92_frames.HistoryGeneration(),chartNow,signalNow,body,
                                GetTickCount64(),verified,published,publishedHistory);
     }
   return true;
  }
bool XpwV92AttachMap()
  {
   if(!ShowMap) return true;
   if(!XpwV92PublishMap(true)) return false;
   ResetLastError(); g_v92_mapHandle=iCustom(_Symbol,_Period,MapIndicator,g_v92_frames.Token(),g_v92_frames.Config());
   if(g_v92_mapHandle==INVALID_HANDLE) { Print("XPW_V092 map handle failed ",GetLastError()); return false; }
   if(!ChartIndicatorAdd(0,(int)ChartGetInteger(0,CHART_WINDOWS_TOTAL),g_v92_mapHandle))
     { IndicatorRelease(g_v92_mapHandle); g_v92_mapHandle=INVALID_HANDLE; return false; }
   g_v92_mapName="XPW Shape Map v0.9.2 + FlashGold ["+g_v92_frames.Token()+"]";
   return true;
  }
void XpwV92RefreshMap()
  {
   if(!g_v92_initialized || (g_v92_mapHandle==INVALID_HANDLE && g_v92_fgfHandle==INVALID_HANDLE)) return;
   const ulong now=GetTickCount64(); if(now-g_v92_mapRefreshAt<500) return;
   g_v92_mapRefreshAt=now;
   // Dependent iCustom has no timer/chart callbacks. Same chart/symbol/period
   // refresh admits the new complete frame and actual viewport every500ms.
   if(!ChartSetSymbolPeriod(ChartID(),_Symbol,_Period)) g_v92_runtime.Log("MAP_REFRESH_ERROR",GetLastError(),"Same-chart dependency refresh failed");
  }
bool XpwV92CompleteStartup()
  {
   if(!XpwV92History(true) || !g_v92_runtime.AdmitHistory(ArraySize(g_v92_times)-1,g_v92_times)
      || !g_v92_runtime.ReconcileSourceAtStartup(ArraySize(g_v92_times)-2,g_v92_times)) return false;
   g_v92_runtime.PlanState(g_v92_planPreview); g_v92_mathCurrent=true;
   g_v92_startupPending=false;
   // Filter/visual history can load asynchronously. Source protection must
   // remain active while entries and shared visual publication are deferred.
   if(g_v92_fgfVisualReady) { XpwV92PublishMap(true); XpwV92AttachMap(); }
   g_v92_runtime.Log("READY",0,"Source141 enum-mapped inputs; independent XPW/FGF/chart clocks; packed permission snapshot; EnableTrading="+(string)(int)EnableTrading+
                     "; execution="+(XpwV92RealtimeSource() ? "LIVE_TICKS" : "PINE_HISTORICAL_CONFIRMED")+"; native fills/management; no retrospective entries");
   return true;
  }
int OnInit()
  {
   XpwV92DeferredReset(g_v92_deferredTick); g_v92_noMutationUnready=false;
   XpwV92TimerPreviewReset(g_v92_timerPreview);
   g_v92_initialized=false; g_v92_busy=false; g_v92_mathCurrent=false; g_v92_reloadPending=false; g_v92_mapName=""; g_v92_mapHandle=INVALID_HANDLE; g_v92_frameAt=0;
   g_v92_fgfHandle=INVALID_HANDLE; g_v92_fgfName=""; g_v92_fgfError="";
   g_v92_startupPending=true; g_v92_previousVisualBar=0; g_v92_previousLiveZones=0; g_v92_fgfQuoteRevision=0;
   g_v92_fgfVisualReady=false; g_v92_fgfVisualRebuild=true;
   g_v92_sourceGap=false;
   XpwV92Configure(g_v92_config); XpwV92ProjectV8(g_v92_config,g_v92_oldConfig); string error;
   ENUM_TIMEFRAMES chartPeriod;
   if(!XpwV92Validate(g_v92_config,error) || !XpwV92LoadFgf(g_v92_fgfConfig,g_v92_fgfVisual,error) || !XpwV92ResolveTimeframe("",_Period,chartPeriod,g_v92_chartSeconds,error)
      || !XpwV92ResolveTimeframe(g_v92_config.sigTF,_Period,g_v92_signalPeriod,g_v92_signalSeconds,error)
      || !XpwV92ClockPairAdmitted(_Period,g_v92_signalPeriod,error))
     { Print("XPW_V092 invalid input: ",error); return INIT_PARAMETERS_INCORRECT; }
   g_v92_gateway.Configure(_Symbol);
   if(!g_v92_gateway.Spec(g_v92_spec) || !g_v92_runtime.ConfigureClosedProfitPolicy(XV92_PROFIT_NATIVE_NET,"3d6f9913492fde01590f1ea0890dedd5cafeba8c8aabba6919db46edf511a7b9")
      || !g_v92_runtime.Initialize(g_v92_config,GetPointer(g_v92_gateway),_Symbol,Magic,(ulong)ChartID(),StateTag,EnableCSV,DeviationPoints,XpwV92TextSHA(XpwV92FullConfigurationKey())))
     { Print("XPW_V092 runtime init failed"); return INIT_FAILED; }
   if(!g_v92_frames.Configure(ChartID(),_Symbol,_Period,XpwV92TextSHA(XpwV92FullConfigurationKey())) ||
      !XpwV92AttachFgf() || !EventSetMillisecondTimer(250)) { Print("XPW_V092_FGF frame/filter/timer init failed ",GetLastError()); return INIT_FAILED; }
   g_v92_fgd.Configure(g_v92_frames.Token(),g_v92_frames.Config(),_Symbol,(int)_Period);
   g_v92_initialized=true;
   if(!XpwV92CompleteStartup()) g_v92_runtime.Log("WAIT_HISTORY",0,"Waiting for synchronized chart, signal and filter history");
   return INIT_SUCCEEDED;
  }
// A22 continuation identity contains only already-admitted source anchors.
void XpwV92DeferredContextNow(XpwV92DeferredContext &context)
  {
   ZeroMemory(context); context.chart=ChartID(); context.symbol=_Symbol; context.period=(int)_Period;
   context.owner=g_v92_frames.Token(); context.config=g_v92_frames.Config();
   context.chartCount=ArraySize(g_v92_times); context.signalCount=ArraySize(g_v92_signalTimes);
   context.chartAnchor=g_v92_currentBar;
   if(context.signalCount>0) context.signalAnchor=g_v92_signalTimes[context.signalCount-1];
   context.lastConfirmed=g_v92_lastConfirmed; context.sourceGap=g_v92_sourceGap; context.reloadPending=g_v92_reloadPending;
  }
void XpwV92ArmObservedTick(const bool observedValid,const MqlTick &observed,
                         const XpwV92DeferredContext &context,const ulong enteredAt)
  {
   MqlTick currentQuote; XpwV92DeferredContext currentContext; XpwV92DeferredContextNow(currentContext);
   if(!observedValid || !g_v92_gateway.Quote(currentQuote) ||
      !XpwV92DeferredArm(g_v92_deferredTick,observed,currentQuote,context,currentContext,enteredAt,GetTickCount64()))
     { XpwV92DeferredReset(g_v92_deferredTick); return; }
   Print("XPW_V092_DEFERRED_TICK event=armed quote_msc=",observed.time_msc," age_ms=",GetTickCount64()-enteredAt);
  }
void XpwV92RunObservedTick(const bool deferred,const bool observedValid,const MqlTick &observed,
                          const XpwV92DeferredContext &context,const ulong enteredAt)
  {
   if(!deferred) XpwV92MathDiagBegin();
   g_v92_noMutationUnready=false;
   const datetime expectedBar=g_v92_currentBar;
   const int chartSize=ArraySize(g_v92_times),signalSize=ArraySize(g_v92_signalTimes);
   const datetime current=XpwV92MathDiagClock(iTime(_Symbol,_Period,0),true),sourceCurrent=XpwV92MathDiagClock(iTime(_Symbol,g_v92_signalPeriod,0),false);
   const int readyCharts=Bars(_Symbol,_Period),readySignals=Bars(_Symbol,g_v92_signalPeriod);
   if(current<=0 || sourceCurrent<=0 || readyCharts<2 || readySignals<1)
     {
      g_v92_mathCurrent=false;
      XpwV92MathDiagFailure("A22.pre_dispatch_unready");
      XpwV92MathDiagOutcome(false,GetLastError(),current,sourceCurrent,false,expectedBar,chartSize,signalSize);
      XpwV92ArmObservedTick(observedValid,observed,context,enteredAt);
      return;
     }
   const bool changed=current!=g_v92_currentBar;
   const bool rebuild=g_v92_reloadPending || changed || sourceCurrent!=g_v92_signalTimes[ArraySize(g_v92_signalTimes)-1]
      || XpwV92MathDiagCount(Bars(_Symbol,_Period),chartSize,"DISPATCH.chart_bars")!=ArraySize(g_v92_times) || XpwV92MathDiagCount(Bars(_Symbol,g_v92_signalPeriod),signalSize,"DISPATCH.signal_bars")!=ArraySize(g_v92_signalTimes);
   g_v92_mathCurrent=false;
   const bool calculated=rebuild ? XpwV92AppendHistory() : XpwV92Preview();
   const int calculationError=GetLastError();
   XpwV92MathDiagOutcome(calculated,calculationError,current,sourceCurrent,rebuild,expectedBar,chartSize,signalSize);
   if(!calculated)
     {
      if(g_v92_noMutationUnready) XpwV92ArmObservedTick(observedValid,observed,context,enteredAt);
      else XpwV92DeferredReset(g_v92_deferredTick); // Later/possibly mutable failures are never deferred.
      return;
     }
   if(deferred)
     {
      MqlTick currentQuote;
      const int last=ArraySize(g_v92_times)-1,signalLast=ArraySize(g_v92_signalTimes)-1;
      // This is the final pre-command endpoint, not a fabricated OnTick call.
      // A changed quote/candle or expired observation cancels the continuation.
      if(!XpwV92DeferredAgeValid(enteredAt,GetTickCount64()) ||
         !g_v92_gateway.Quote(currentQuote) || !XpwV92DeferredSameQuote(observed,currentQuote) ||
         last<1 || signalLast<0 || iTime(_Symbol,_Period,0)!=g_v92_times[last] ||
         iTime(_Symbol,g_v92_signalPeriod,0)!=g_v92_signalTimes[signalLast] ||
         !XpwV92DeferredContains(observed,g_v92_times[last],XpwV92BarClose(g_v92_times[last],_Period)) ||
         !XpwV92DeferredContains(observed,g_v92_signalTimes[signalLast],XpwV92BarClose(g_v92_signalTimes[signalLast],g_v92_signalPeriod)))
        { g_v92_mathCurrent=false; XpwV92DeferredReset(g_v92_deferredTick); return; }
     }
   // Consume BEFORE Sync/capture/Process/requests. Failures below cannot arm a retry.
   XpwV92DeferredReset(g_v92_deferredTick);
   if(deferred) Print("XPW_V092_DEFERRED_TICK event=consumed quote_msc=",observed.time_msc," age_ms=",GetTickCount64()-enteredAt);
   if(calculated)
     {
      const bool inventorySynced=g_v92_runtime.Sync();
      g_v92_mathCurrent=true;
      const int index=ArraySize(g_v92_times)-1;
      // Capture both native execution contexts before Process, admission,
      // quantity/exit calculations, virtual triggers, management or requests.
      if(index>0 && (g_v92_sourceGap || g_v92_times[index-1]>g_v92_lastConfirmed))
         XpwV92CaptureFgd(index-1,true,inventorySynced);
      XpwV92CaptureFgd(index,false,inventorySynced);
      if(!inventorySynced)
        { XpwV92PublishMap(true); XpwV92RefreshMap(); g_v92_busy=false; return; }
      // A delayed source decision is retried only in its next chart candle.
      // Do not silently skip a longer outage or submit stale historical market
      // entries. An explicit restart resynchronizes through the existing
      // no-retrospective-entry bootstrap while independent protection remains.
      if(!g_v92_sourceGap && index>1 && g_v92_times[index-2]>g_v92_lastConfirmed)
        {
         g_v92_sourceGap=true;
         g_v92_runtime.Log("SOURCE_GAP",0,"Unresolved confirmed source bar spans another candle; entries/virtual triggers suspended until restart; protection retained");
        }
      if(g_v92_sourceGap)
        {
         if(index>0) XpwV92Process(index-1,true,true);
         g_v92_runtime.Manage(g_v92_oldConfig,index,g_v92_times,g_v92_tradeBars);
         if(XpwV92RealtimeSource()) XpwV92Process(index,false,true);
         XpwV92PublishMap(true); XpwV92RefreshMap(); g_v92_busy=false; return;
        }
      // Source confirmed cancellations precede virtual CONT crossing on the
      // next bar's first tick. They cannot be raced by a native GTC fill.
      bool confirmedComplete=true;
      if(index>0 && g_v92_times[index-1]>g_v92_lastConfirmed)
        {
         confirmedComplete=XpwV92Process(index-1,true);
         if(confirmedComplete) g_v92_lastConfirmed=g_v92_times[index-1];
        }
      if(!confirmedComplete)
        {
         // Protective management is independent; new entries and virtual
         // triggers cannot overtake a deferred confirmed cancellation.
         g_v92_runtime.Manage(g_v92_oldConfig,index,g_v92_times,g_v92_tradeBars);
         if(XpwV92RealtimeSource()) XpwV92Process(index,false,true);
         if(!XpwV92PublishMap()) g_v92_runtime.Log("MAP_FRAME_ERROR",g_v92_mapPublishNativeError,"Pending source frame publication refused; stage="+g_v92_mapPublishStage);
         XpwV92RefreshMap(); g_v92_busy=false; return;
        }
      XpwV8Exit exit;
      if(XpwV92CurrentExit(index,exit)) g_v92_runtime.Triggers(g_v92_times[index],index,exit);
      g_v92_runtime.Manage(g_v92_oldConfig,index,g_v92_times,g_v92_tradeBars);
      if(XpwV92RealtimeSource()) XpwV92Process(index,false);
      g_v92_runtime.Manage(g_v92_oldConfig,index,g_v92_times,g_v92_tradeBars);
      if(!XpwV92PublishMap(true)) g_v92_runtime.Log("MAP_FRAME_ERROR",g_v92_mapPublishNativeError,"Complete owner frame not published; stage="+g_v92_mapPublishStage);
      if(ShowMap && g_v92_mapHandle==INVALID_HANDLE && g_v92_fgfVisualReady) XpwV92AttachMap();
      XpwV92RefreshMap();
     }
  }
bool XpwV92RetryObservedTick()
  {
   if(!g_v92_deferredTick.pending) return false;
   MqlTick currentQuote; XpwV92DeferredContext context; XpwV92DeferredContextNow(context);
   if(!g_v92_gateway.Quote(currentQuote)) { XpwV92DeferredReset(g_v92_deferredTick); return false; }
   const datetime chartNow=iTime(_Symbol,_Period,0),signalNow=iTime(_Symbol,g_v92_signalPeriod,0);
   const int charts=Bars(_Symbol,_Period),signals=Bars(_Symbol,g_v92_signalPeriod);
   const ulong now=GetTickCount64();
   const XpwV92DeferredDecision decision=XpwV92DeferredDecide(g_v92_deferredTick,currentQuote,context,now,
      chartNow,XpwV92BarClose(chartNow,_Period),charts,signalNow,XpwV92BarClose(signalNow,g_v92_signalPeriod),signals);
   if(decision==XV92_DEFERRED_CANCEL) { XpwV92DeferredReset(g_v92_deferredTick); return false; }
   if(decision!=XV92_DEFERRED_READY) return false;
   // Private copies preserve the original observed identity and non-sliding age.
   const MqlTick observed=g_v92_deferredTick.quote;
   const XpwV92DeferredContext originalContext=g_v92_deferredTick.context;
   const ulong enteredAt=g_v92_deferredTick.enteredAt;
   g_v92_deferredTick.lastAttemptAt=now;
   Print("XPW_V092_DEFERRED_TICK event=retry quote_msc=",observed.time_msc," age_ms=",now-enteredAt);
   XpwV92RunObservedTick(true,true,observed,originalContext,enteredAt);
   return true;
  }
void OnTick()
  {
   if(!g_v92_initialized || g_v92_busy) return; g_v92_busy=true;
   const ulong enteredAt=GetTickCount64();
   // Every actual callback supersedes pending work, including identical quotes.
   XpwV92DeferredReset(g_v92_deferredTick);
   if(g_v92_startupPending) { XpwV92CompleteStartup(); g_v92_busy=false; return; }
   MqlTick observed; ZeroMemory(observed);
   const bool observedValid=g_v92_gateway.Quote(observed) && XpwV92DeferredQuoteValid(observed);
   XpwV92DeferredContext context; XpwV92DeferredContextNow(context);
   XpwV92RunObservedTick(false,observedValid,observed,context,enteredAt);
   g_v92_busy=false;
  }
void OnTimer()
  {
   if(!g_v92_initialized || g_v92_busy) return;
   if(g_v92_startupPending) { g_v92_busy=true; XpwV92CompleteStartup(); g_v92_busy=false; return; }
   if(g_v92_deferredTick.pending)
     {
      g_v92_busy=true; const bool attempted=XpwV92RetryObservedTick(); g_v92_busy=false;
      if(attempted) return;
     }
   g_v92_runtime.RecoverDeals();
   if(!g_v92_fgfVisualReady || g_v92_fgfVisualRebuild)
     {
      const int last=ArraySize(g_v92_times)-1;
      if(last>=1) XpwV92ObserveFgfVisuals(last+1,g_v92_times[0],g_v92_times[last]);
     }
   if(!XpwV92PublishMap(false,true)) g_v92_runtime.Log("MAP_FRAME_ERROR",g_v92_mapPublishNativeError,"Timer frame publication refused; stage="+g_v92_mapPublishStage);
   if(ShowMap && g_v92_mapHandle==INVALID_HANDLE && g_v92_fgfVisualReady) XpwV92AttachMap();
   XpwV92RefreshMap();
  }
void OnTradeTransaction(const MqlTradeTransaction &transaction,const MqlTradeRequest &request,const MqlTradeResult &result)
  { if(transaction.type==TRADE_TRANSACTION_DEAL_ADD) g_v92_runtime.RecordDeal(transaction.deal); }
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  { if(g_v92_initialized && id==CHARTEVENT_CHART_CHANGE) XpwV92RefreshMap(); }
void OnDeinit(const int reason)
  {
   XpwV92DeferredReset(g_v92_deferredTick);
   XpwV92TimerPreviewReset(g_v92_timerPreview);
   g_v92_initialized=false; EventKillTimer();
   if(g_v92_fgfName!="") ChartIndicatorDelete(0,0,g_v92_fgfName);
   if(g_v92_fgfHandle!=INVALID_HANDLE) { IndicatorRelease(g_v92_fgfHandle); g_v92_fgfHandle=INVALID_HANDLE; }
   if(g_v92_mapName!="") { const int pane=ChartWindowFind(0,g_v92_mapName); if(pane>=0) ChartIndicatorDelete(0,pane,g_v92_mapName); }
   if(g_v92_mapHandle!=INVALID_HANDLE) { IndicatorRelease(g_v92_mapHandle); g_v92_mapHandle=INVALID_HANDLE; }
   if(!g_v92_frames.Cleanup()) Print("XPW_V092 frame cleanup preserved changed/locked files");
   g_v92_runtime.Shutdown(true);
   PrintFormat("XPW_V092_FGF_GATEWAY EnableTrading=%d check_attempts=%I64u send_attempts=%I64u raw_checks=%I64u raw_sends=%I64u",
               (int)EnableTrading,g_v92_gateway.CheckAttempts(),g_v92_gateway.SendAttempts(),g_v92_gateway.RawChecks(),g_v92_gateway.RawSends());
  }
double OnTester()
  { return XpwPfTesterScore(g_v92_runtime.ExportTesterLedger()); }
