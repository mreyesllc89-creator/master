// FlashGold Direction Filter v1.2 -- independently ported from the supplied Pine.
// Provenance and verification status are in ORIGIN.json and REVIEW.md.
// Indicator only. No trading, file writing, DLLs, network calls or alerts.
// Data uses the attached symbol's broker candles and SYMBOL_TRADE_TICK_SIZE.
// Native MT5 timeframes are supported. Broker sessions/timezone can differ
// from TradingView; identical formulas do not establish cross-feed parity.
#property version "1.20"
#property description "FlashGold Direction Filter v1.2: signal levels, ATR band, TDI zones and direction score."
#property indicator_chart_window
#property indicator_buffers 9
#property indicator_plots 9
#include "../Include/FlashGold/DirectionFilterCore.mqh"
#include "../Include/FlashGold/DirectionFilterClock.mqh"
#include "../Include/FlashGold/DirectionFilterRender.mqh"

enum FGF_LEVEL { FGF_ENTRY=0, FGF_CLOSE=1 };
enum FGF_WINDOW { FGF_NEXT=0, FGF_MINUTES=1, FGF_CANDLES=2 };
enum FGF_CHECK { FGF_TICK=0, FGF_OPEN=1, FGF_BAR_CLOSE=2 };
enum FGF_UNIT { FGF_ATR=0, FGF_POINTS=1 };
enum FGF_POSITION { FGF_TOP_RIGHT=0,FGF_MIDDLE_RIGHT=1,FGF_BOTTOM_RIGHT=2,
                    FGF_TOP_LEFT=3,FGF_MIDDLE_LEFT=4,FGF_BOTTOM_LEFT=5,
                    FGF_TOP_CENTER=6,FGF_BOTTOM_CENTER=7 };

input group "Direction filter"
input bool fgfOn=true;                         // Enable filter
input ENUM_TIMEFRAMES fgfTf=PERIOD_H1;          // Filter timeframe (current = chart)
input FGF_LEVEL fgfLvMode=FGF_ENTRY;            // Level: Entry price / Signal close
input FGF_WINDOW fgfLast=FGF_NEXT;              // Permission lasts
input int fgfMinutes=60;                       // Minutes
input int fgfBars=1;                           // Candles
input FGF_CHECK fgfCheck=FGF_TICK;              // Check price on
input double fgfBandAtr=0.25;                  // No-trade band, ATR mult
input bool fgfAgainst=true;                    // Allow trading against the signal
input bool fgfAllowBuy=true;                   // Allow buys
input bool fgfAllowSell=true;                  // Allow sells
input bool fgfShowBg=true;                     // Shade
input bool fgfShowLv=true;                     // Level line
input bool fgfSigMark=true;                    // Signal marks
input bool fgfShowTbl=true;                    // Status box
input FGF_POSITION fgfTblPos=FGF_TOP_RIGHT;     // Status box position
input group "Direction score"
input bool fgsShow=false;                      // Show the direction score
input int fgsWin=500;                          // Window, filter candles (0 = all history)
input int fgsH=10;                             // Longer horizon H, filter candles
input group "FlashGold signal: core"
input double fgfSpreadPts=25.0;                // Spread pts (modeled, in trade tick units)
input double fgfEntryDistPts=50.0;             // Entry distance pts (Points unit)
input int fgfHoldBars=0;                       // Entry hold bars
input double fgfHoldFavPts=5.0;                // Hold minimum favorable pts
input bool fgfOnePerBar=true;                  // One signal per bar
input group "FlashGold signal: burst / direction"
input FGF_UNIT fgfDistUnit=FGF_ATR;             // Burst / entry distance / hold unit
input double fgfBurstAtr=0.5;                  // Burst threshold ATR multiplier
input double fgfEntryDistAtr=0.25;             // Entry distance ATR multiplier
input double fgfHoldFavAtr=0.1;                // Hold favorable ATR multiplier
input double fgfBurstPts=172.0;                // Burst threshold pts
input bool fgfUseBurst=true;                   // Require burst gate
input bool fgfAnyCombo=false;                  // Allow any combo
input int fgfDriftBars=60;                     // Prior drift bars
input bool fgfUseDrift=false;                  // Use prior drift filter
input group "FlashGold signal: TDI trade zone"
input bool fgfUseZones=true;                   // Use TDI trade-zone filter
input ENUM_TIMEFRAMES fgfParentTf=PERIOD_H1;    // Parent obedience timeframe
input int fgfRsiLen=14;                        // TDI RSI length
input int fgfFastLen=2;                        // TDI white fast length
input int fgfMinAligned=2;                     // Minimum child zones aligned
input bool fgfFlatParent=false;                // Allow trade if parent is flat
input bool fgfIgnoreNa=true;                   // Ignore zones without data
input bool fgfHtfClosed=true;                  // Higher TF zones use last CLOSED bar
input bool fgfUseZ1=true;
input ENUM_TIMEFRAMES fgfZTf1=PERIOD_H1;
input bool fgfUseZ2=true;
input ENUM_TIMEFRAMES fgfZTf2=PERIOD_H2;
input bool fgfUseZ3=true;
input ENUM_TIMEFRAMES fgfZTf3=PERIOD_H4;
input bool fgfUseZ4=false;
input ENUM_TIMEFRAMES fgfZTf4=PERIOD_H8;
input bool fgfUseZ5=false;
input ENUM_TIMEFRAMES fgfZTf5=PERIOD_M1;
input bool fgfUseZ6=false;
input ENUM_TIMEFRAMES fgfZTf6=PERIOD_M2;

double bufActive[],bufBuy[],bufSell[],bufLevel[],bufSignal[],bufEnded[],bufZone[],bufConfirmed[],bufScore[];
FgfConfig g_cfg;
FgfVisualConfig g_vis;
CFgfRenderer g_renderer;
FgfBar g_chart[];
FgfFilterPoint g_picked[],g_closePick[],g_filter[];
FgfGate g_gate[];
string g_prefix,g_shortName;
long g_renderChart=-1;
bool g_ready=false;
bool g_historyChanged=false;
FgfQuoteSession g_quoteSessions[];
FgfLastBarObservation g_chartObservation,g_filterObservation;
FgfExecutionClock g_executionClock;
long g_quoteRevision=0,g_tickMs=-1;
MqlTick g_lastTick;
bool g_haveTick=false,g_sessionsChanged=false;
string g_renderError="";
int g_parentSlot=-1,g_filterSlot=-1,g_childSlot[6],g_slots=0;

long FgfBarEnd(const datetime start,const ENUM_TIMEFRAMES tf)
  {
   if(tf!=PERIOD_MN1)
      return FgfSessionBarEnd((long)start*1000,((long)start+PeriodSeconds(tf))*1000,
                              PeriodSeconds(tf)<86400,g_quoteSessions);
   MqlDateTime d; TimeToStruct(start,d); d.mon++;
   if(d.mon>12) { d.mon=1; d.year++; }
   d.day=1; d.hour=0; d.min=0; d.sec=0;
   return (long)StructToTime(d)*1000;
  }

void FgfLoadQuoteSessions(void)
  {
   FgfQuoteSession next[];
   bool complete=true;
   for(int day=0;day<7;day++)
      for(uint i=0;i<=64;i++)
        {
         datetime begin,end;
         if(!SymbolInfoSessionQuote(_Symbol,(ENUM_DAY_OF_WEEK)day,i,begin,end)) break;
         if(i==64) { complete=false; break; }
         MqlDateTime a,b;
         if(!TimeToStruct(begin,a) || !TimeToStruct(end,b)) { complete=false; break; }
         int n=ArraySize(next);
         if(ArrayResize(next,n+1)!=n+1) { complete=false; break; }
         next[n].day=day; next[n].fromSecond=a.hour*3600+a.min*60+a.sec;
         next[n].toSecond=b.hour*3600+b.min*60+b.sec;
        }
   if(!complete) ArrayResize(next,0);
   g_sessionsChanged=ArraySize(next)!=ArraySize(g_quoteSessions);
   if(!g_sessionsChanged)
      for(int i=0;i<ArraySize(next);i++)
         if(next[i].day!=g_quoteSessions[i].day || next[i].fromSecond!=g_quoteSessions[i].fromSecond ||
            next[i].toSecond!=g_quoteSessions[i].toSecond) { g_sessionsChanged=true; break; }
   if(g_sessionsChanged)
     {
      int n=ArraySize(next);
      if(ArrayResize(g_quoteSessions,n)!=n) { ArrayResize(g_quoteSessions,0); return; }
      for(int i=0;i<n;i++) g_quoteSessions[i]=next[i];
     }
  }

void FgfCaptureExecution(void)
  {
   MqlTick tick;
   bool have=SymbolInfoTick(_Symbol,tick);
   if(have)
     {
      if(!g_haveTick || tick.time_msc!=g_lastTick.time_msc || tick.bid!=g_lastTick.bid ||
         tick.ask!=g_lastTick.ask || tick.last!=g_lastTick.last || tick.volume!=g_lastTick.volume ||
         tick.volume_real!=g_lastTick.volume_real || tick.flags!=g_lastTick.flags) g_quoteRevision++;
      g_lastTick=tick;
      g_tickMs=tick.time_msc>0 ? tick.time_msc : (long)tick.time*1000;
     }
   else { if(g_haveTick) g_quoteRevision++; g_tickMs=-1; }
   g_haveTick=have;
   long clock=(long)TimeTradeServer()*1000;
   if(clock<=0) clock=(long)TimeCurrent()*1000;
   FgfCaptureClock(g_executionClock,clock,g_tickMs);
  }

// One cache per distinct requested timeframe. CopyRates requests all currently
// available bars: Pine max_bars_back is not a history truncation instruction.
class CFgfTimeframe
  {
public:
   ENUM_TIMEFRAMES tf;
   FgfBar bars[];
   int dirs[];
   bool Load(void)
     {
      MqlRates rates[]; ArraySetAsSeries(rates,false);
      int total=Bars(_Symbol,tf);
      if(total<1) { CopyRates(_Symbol,tf,0,1,rates); return false; }
      int n=CopyRates(_Symbol,tf,0,total,rates);
      if(n<1 || !SeriesInfoInteger(_Symbol,tf,SERIES_SYNCHRONIZED)) return false;
      int old=ArraySize(bars);
      if(old==0 || n<old || (old>0 && bars[0].time!=(long)rates[0].time*1000)) g_historyChanged=true;
      // Detect corrections to finalized requested history independently of
      // the chart timeframe's prev_calculated reset notification.
      if(!g_historyChanged)
         for(int i=0;i<MathMin(old-1,n);i++)
            if(bars[i].time!=(long)rates[i].time*1000 || bars[i].open!=rates[i].open ||
               bars[i].high!=rates[i].high || bars[i].low!=rates[i].low || bars[i].close!=rates[i].close)
              { g_historyChanged=true; break; }
      if(ArrayResize(bars,n)!=n) return false;
      for(int i=0;i<n;i++)
        {
         bars[i].time=(long)rates[i].time*1000;
         bars[i].end=FgfBarEnd(rates[i].time,tf);
         bars[i].open=rates[i].open; bars[i].high=rates[i].high;
         bars[i].low=rates[i].low; bars[i].close=rates[i].close;
        }
      return FgfTdiSeries(bars,g_cfg.rsiLen,g_cfg.fastLen,dirs);
     }
   int OpenAt(const long time) const
     {
      int lo=0,hi=ArraySize(bars)-1,answer=-1;
      while(lo<=hi) { int m=(lo+hi)/2; if(bars[m].time<=time) {answer=m;lo=m+1;} else hi=m-1; }
      return answer;
     }
   int ClosedAt(const long time) const
     {
      int lo=0,hi=ArraySize(bars)-1,answer=-1;
      while(lo<=hi) { int m=(lo+hi)/2; if(bars[m].end<=time) {answer=m;lo=m+1;} else hi=m-1; }
      return answer;
     }
   int Read(const long open,const long end,const bool previousOn,const bool realtime,const long now) const
     {
      int k=previousOn ? OpenAt(open)-1 : realtime ? OpenAt(now) : ClosedAt(end);
      return k<0 ? 99 : dirs[k];
     }
  };
CFgfTimeframe g_tf[8];

// Live request.security observations stay committed for filter bars seen in
// this session. Replaying the forming bar from scratch implements var rollback.
struct FgfObserved { long time; int parent; int child[6]; };
FgfObserved g_observed[];

int FgfAddTf(ENUM_TIMEFRAMES tf)
  {
   if(tf==PERIOD_CURRENT) tf=_Period;
   for(int i=0;i<g_slots;i++) if(g_tf[i].tf==tf) return i;
   if(g_slots>=8 || PeriodSeconds(tf)<=0) return -1;
   int i=g_slots++; g_tf[i].tf=tf; return i;
  }
long FgfNow(void)
  {
   // Pine timenow is an execution clock. Rendering does not advance it.
   // Only OnCalculate captures a fresh broker-domain execution timestamp.
   return FgfClockNow(g_executionClock);
  }
string FgfTimeframeLabel(const ENUM_TIMEFRAMES tf)
  {
   int seconds=PeriodSeconds(tf);
   if(seconds<60) return IntegerToString(seconds)+"s";
   if(seconds<3600) return IntegerToString(seconds/60)+"m";
   if(seconds<86400) return IntegerToString(seconds/3600)+"H";
   if(tf==PERIOD_D1) return "1D";
   if(tf==PERIOD_W1) return "1W";
   if(tf==PERIOD_MN1) return "1M";
   return EnumToString(tf);
  }
void FgfConfigure(void)
  {
   FgfDefaults(g_cfg);
   g_cfg.enabled=fgfOn; g_cfg.levelMode=(int)fgfLvMode;
   g_cfg.windowMode=(int)fgfLast; g_cfg.minutes=fgfMinutes; g_cfg.bars=fgfBars;
   g_cfg.checkMode=(int)fgfCheck; g_cfg.bandAtr=fgfBandAtr; g_cfg.against=fgfAgainst;
   g_cfg.allowBuy=fgfAllowBuy; g_cfg.allowSell=fgfAllowSell;
   g_cfg.spreadPts=fgfSpreadPts; g_cfg.entryDistPts=fgfEntryDistPts;
   g_cfg.holdBars=fgfHoldBars; g_cfg.holdFavPts=fgfHoldFavPts; g_cfg.onePerBar=fgfOnePerBar;
   g_cfg.distUnit=(int)fgfDistUnit; g_cfg.burstAtr=fgfBurstAtr;
   g_cfg.entryDistAtr=fgfEntryDistAtr; g_cfg.holdFavAtr=fgfHoldFavAtr;
   g_cfg.burstPts=fgfBurstPts; g_cfg.useBurst=fgfUseBurst; g_cfg.anyCombo=fgfAnyCombo;
   g_cfg.driftBars=fgfDriftBars; g_cfg.useDrift=fgfUseDrift;
   g_cfg.useZones=fgfUseZones; g_cfg.rsiLen=fgfRsiLen; g_cfg.fastLen=fgfFastLen;
   g_cfg.minAligned=fgfMinAligned; g_cfg.flatParent=fgfFlatParent; g_cfg.ignoreNa=fgfIgnoreNa;
   g_cfg.childEnabled[0]=fgfUseZ1; g_cfg.childEnabled[1]=fgfUseZ2; g_cfg.childEnabled[2]=fgfUseZ3;
   g_cfg.childEnabled[3]=fgfUseZ4; g_cfg.childEnabled[4]=fgfUseZ5; g_cfg.childEnabled[5]=fgfUseZ6;
   g_cfg.scoreWindow=fgsWin; g_cfg.scoreHorizon=fgsH;
   g_cfg.tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   g_vis.showBg=fgfShowBg; g_vis.showLv=fgfShowLv; g_vis.sigMark=fgfSigMark;
   g_vis.showTbl=fgfShowTbl; g_vis.showScore=fgsShow;
   g_vis.tablePos=(int)fgfTblPos; g_vis.digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   ENUM_TIMEFRAMES tf=fgfTf==PERIOD_CURRENT ? _Period : fgfTf;
   g_vis.filterLabel=FgfTimeframeLabel(tf);
   g_vis.filterSeconds=PeriodSeconds(tf); g_vis.nowMs=FgfNow();
  }
bool FgfCalculateFilter(const long now,const bool reset)
  {
   g_historyChanged=g_sessionsChanged;
   for(int i=0;i<g_slots;i++) if(!g_tf[i].Load()) return false;
   int n=ArraySize(g_tf[g_filterSlot].bars);
   int parents[],children[];
   if(ArrayResize(parents,n)!=n || ArrayResize(children,n*6)!=n*6) return false;
   if(reset || g_historyChanged) ArrayResize(g_observed,0);
   bool newestLive=FgfObserveLatest(g_tf[g_filterSlot].bars[n-1],
       PeriodSeconds(g_tf[g_filterSlot].tf)<86400,now,g_quoteSessions,g_tickMs,
       g_quoteRevision,reset || g_historyChanged,g_filterObservation);
   int oi=0,obs=ArraySize(g_observed);
   for(int k=0;k<n;k++)
     {
      FgfBar b=g_tf[g_filterSlot].bars[k];
      bool realtime=k==n-1 && newestLive;
      long tickClock=MathMax(b.time,MathMin(now,b.end-1));
      parents[k]=g_tf[g_parentSlot].Read(b.time,b.end,false,realtime,tickClock);
      for(int z=0;z<6;z++)
        {
         int slot=g_childSlot[z];
         bool previousOn=slot>=0 && fgfHtfClosed &&
             PeriodSeconds(g_tf[slot].tf)>PeriodSeconds(g_tf[g_filterSlot].tf);
         children[k*6+z]=slot<0 ? 99 : g_tf[slot].Read(b.time,b.end,previousOn,realtime,tickClock);
        }
      while(oi<obs && g_observed[oi].time<b.time) oi++;
      if(k<n-1 && oi<obs && g_observed[oi].time==b.time)
        {
         parents[k]=g_observed[oi].parent;
         for(int z=0;z<6;z++) children[k*6+z]=g_observed[oi].child[z];
        }
      if(k==n-1)
        {
         int j=obs>0 && g_observed[obs-1].time==b.time ? obs-1 : obs;
         if(j==obs && ArrayResize(g_observed,obs+1)!=obs+1) return false;
         g_observed[j].time=b.time; g_observed[j].parent=parents[k];
         for(int z=0;z<6;z++) g_observed[j].child[z]=children[k*6+z];
        }
     }
   return FgfBuildFilter(g_cfg,g_tf[g_filterSlot].bars,parents,children,g_filter);
  }

void FgfResetDisplay(void)
  {
   g_renderer.Destroy();
   // A later successful calculation must create the surfaces again even if
   // this instance is still attached to the same chart after a history retry.
   g_renderChart=-1; g_renderError="";
  }
bool FgfAttachedTo(const long chartId)
  {
   if(chartId<=0) return false;
   for(int i=0;i<ChartIndicatorsTotal(chartId,0);i++)
      if(ChartIndicatorName(chartId,0,i)==g_shortName) return true;
   return false;
  }
long FgfDisplayChart(void)
  {
   if(FgfAttachedTo(g_renderChart)) return g_renderChart;
   // iCustom initially belongs to its caller's calculation context, even
   // when ChartIndicatorAdd later displays it on a different chart. Resolve
   // only this exact instance's attached name, never a symbol/TF lookalike.
   long chartId=ChartFirst();
   for(int i=0;i<CHARTS_MAX && chartId>=0;i++,chartId=ChartNext(chartId))
      if(FgfAttachedTo(chartId)) return chartId;
   return -1;
  }
void FgfRender(void)
  {
   long chartId=FgfDisplayChart();
   if(chartId!=g_renderChart)
     {
      g_renderer.Destroy(); g_renderChart=chartId;
      if(chartId>0 && !g_renderer.Init(g_prefix,chartId))
        { Print("FlashGold v1.2 drawing: ",g_renderer.Error()); g_renderChart=-1; return; }
     }
   // Unattached handles expose the same buffers without creating chart UI.
   if(chartId<=0) return;
   bool ok=g_renderer.Render(g_cfg,g_vis,g_chart,g_picked,g_gate);
   string error=ok ? "" : g_renderer.Error();
   if(error!="" && error!=g_renderError) Print("FlashGold v1.2 drawing: ",error);
   g_renderError=error;
  }

void FgfEmptyBuffers(void)
  {
   ArrayInitialize(bufActive,EMPTY_VALUE); ArrayInitialize(bufBuy,EMPTY_VALUE);
   ArrayInitialize(bufSell,EMPTY_VALUE); ArrayInitialize(bufLevel,EMPTY_VALUE);
   ArrayInitialize(bufSignal,EMPTY_VALUE); ArrayInitialize(bufEnded,EMPTY_VALUE);
   ArrayInitialize(bufZone,EMPTY_VALUE); ArrayInitialize(bufConfirmed,EMPTY_VALUE);
   ArrayInitialize(bufScore,EMPTY_VALUE);
  }
int OnInit(void)
  {
   FgfResetObservation(g_chartObservation); FgfResetObservation(g_filterObservation);
   FgfCaptureClock(g_executionClock,0,-1);
   FgfConfigure(); string error;
   if(!FgfValidate(g_cfg,error)) { Print("FGF inputs: ",error); return INIT_PARAMETERS_INCORRECT; }
   g_filterSlot=FgfAddTf(fgfTf); g_parentSlot=FgfAddTf(fgfParentTf);
   ENUM_TIMEFRAMES ztf[6]={fgfZTf1,fgfZTf2,fgfZTf3,fgfZTf4,fgfZTf5,fgfZTf6};
   for(int z=0;z<6;z++)
     {
      g_childSlot[z]=g_cfg.childEnabled[z] ? FgfAddTf(ztf[z]) : -1;
      if(g_cfg.childEnabled[z] && g_childSlot[z]<0) return INIT_PARAMETERS_INCORRECT;
     }
   if(g_filterSlot<0 || g_parentSlot<0) return INIT_PARAMETERS_INCORRECT;
   SetIndexBuffer(0,bufActive,INDICATOR_DATA); SetIndexBuffer(1,bufBuy,INDICATOR_DATA);
   SetIndexBuffer(2,bufSell,INDICATOR_DATA); SetIndexBuffer(3,bufLevel,INDICATOR_DATA);
   SetIndexBuffer(4,bufSignal,INDICATOR_DATA); SetIndexBuffer(5,bufEnded,INDICATOR_DATA);
   SetIndexBuffer(6,bufZone,INDICATOR_DATA); SetIndexBuffer(7,bufConfirmed,INDICATOR_DATA);
   SetIndexBuffer(8,bufScore,INDICATOR_DATA);
   string labels[9]={"FGF active","FGF buy allowed","FGF sell allowed","FGF level",
       "FGF signal (1 buy, -1 sell)","FGF ended","FGF zone (1 buy, -1 sell, 0 no trade, 2 off)",
       "FGF signal confirmed","FGF score (next candle)"};
   for(int i=0;i<9;i++)
     {
      PlotIndexSetInteger(i,PLOT_DRAW_TYPE,DRAW_NONE);
      PlotIndexSetDouble(i,PLOT_EMPTY_VALUE,EMPTY_VALUE);
      PlotIndexSetString(i,PLOT_LABEL,labels[i]);
     }
   string instance=(string)GetTickCount64()+"."+(string)GetMicrosecondCount();
   g_prefix="FGF12_"+instance+"_";
   g_shortName="FlashGold Direction Filter v1.2 [MT5 "+instance+"]";
   IndicatorSetString(INDICATOR_SHORTNAME,g_shortName);
   IndicatorSetInteger(INDICATOR_DIGITS,g_vis.digits);
   g_renderChart=-1;
   if(!EventSetTimer(1)) { Print("FGF could not start display timer: ",GetLastError()); return INIT_FAILED; }
   return INIT_SUCCEEDED;
  }
int OnCalculate(const int rates_total,const int prev_calculated,const datetime &time[],
                const double &open[],const double &high[],const double &low[],const double &close[],
                const long &tick_volume[],const long &volume[],const int &spread[])
  {
   ArraySetAsSeries(time,false); ArraySetAsSeries(open,false); ArraySetAsSeries(high,false);
   ArraySetAsSeries(low,false); ArraySetAsSeries(close,false);
   if(rates_total<1) return 0;
   FgfCaptureExecution(); FgfLoadQuoteSessions();
   long now=FgfNow(); g_vis.nowMs=now;
   bool reset=prev_calculated<=0 || prev_calculated>rates_total;
   if(!FgfCalculateFilter(now,reset))
     {
      g_ready=false; FgfEmptyBuffers(); FgfResetDisplay(); return 0;
     }
   if(ArrayResize(g_chart,rates_total)!=rates_total || ArrayResize(g_picked,rates_total)!=rates_total ||
      ArrayResize(g_gate,rates_total)!=rates_total || ArrayResize(g_closePick,rates_total)!=rates_total)
     {
      g_ready=false; FgfEmptyBuffers(); FgfResetDisplay();
      Print("FlashGold v1.2: insufficient memory for chart history"); return 0;
     }
   int start=reset || g_historyChanged ? 0 : MathMax(0,prev_calculated-1);
   if(start==0) g_renderer.ResetHistory();
   for(int i=start;i<rates_total;i++)
     {
      g_chart[i].time=(long)time[i]*1000; g_chart[i].end=FgfBarEnd(time[i],_Period);
      g_chart[i].open=open[i]; g_chart[i].high=high[i]; g_chart[i].low=low[i]; g_chart[i].close=close[i];
      // Infer a closed newest intraday bar only from a supported quote-session
      // window and a quote belonging to the bar; never from clock age alone.
      bool live=i==rates_total-1 && FgfObserveLatest(g_chart[i],PeriodSeconds(_Period)<86400,
          now,g_quoteSessions,g_tickMs,g_quoteRevision,start==0,g_chartObservation);
      int fi=live ? g_tf[g_filterSlot].OpenAt(g_chart[i].time) : g_tf[g_filterSlot].ClosedAt(g_chart[i].end);
      if(live && PeriodSeconds(g_tf[g_filterSlot].tf)<PeriodSeconds(_Period)) fi=ArraySize(g_filter)-1;
      FgfFilterPoint fp,fq,previous;
      FgfEmptyPoint(fp); FgfEmptyPoint(fq); FgfEmptyPoint(previous);
      if(fi>=0) { fp=g_filter[fi]; if(fi>0) fq=g_filter[fi-1]; }
      if(i>0) previous=g_closePick[i-1];
      long clock; int index; double value;
      FgfChartPick(g_cfg,g_chart[i],i>0 ? close[i-1] : EMPTY_VALUE,live,now,
                   fp,fq,previous,g_picked[i],g_closePick[i],clock,index,value);
      FgfEvaluateGate(g_cfg,g_picked[i],clock,index,value,i>0 ? g_picked[i-1].armedId : 0,
                     i>0 ? g_gate[i-1].ended : false,i==0,now,g_gate[i]);
      bufActive[i]=g_cfg.enabled && g_gate[i].open ? 1 : 0;
      bufBuy[i]=g_gate[i].buyOK ? 1 : 0; bufSell[i]=g_gate[i].sellOK ? 1 : 0;
      bufLevel[i]=g_picked[i].armedPrice;
      bufSignal[i]=g_gate[i].newSignal ? g_picked[i].armedDir : 0;
      bufEnded[i]=g_gate[i].expired ? 1 : 0; bufZone[i]=g_gate[i].zone;
      bufConfirmed[i]=g_cfg.enabled && g_gate[i].open && g_gate[i].sigOk ? 1 : 0;
      bufScore[i]=fgsShow ? g_picked[i].scores[0] : EMPTY_VALUE;
     }
   g_ready=true;
   FgfRender();
   return rates_total;
  }
void OnTimer(void)
  {
   if(!g_ready) return;
   // Retry attachment/geometry and repaint cached execution results only.
   // A timer or chart redraw cannot expire a permission or confirm a bar.
   FgfRender();
  }
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_CHART_CHANGE && g_ready)
      FgfRender();
  }
void OnDeinit(const int reason) { EventKillTimer(); FgfResetDisplay(); }
