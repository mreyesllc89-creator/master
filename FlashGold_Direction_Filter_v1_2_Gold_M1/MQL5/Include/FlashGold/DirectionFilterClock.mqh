#ifndef FLASHGOLD_DIRECTION_FILTER_CLOCK_MQH
#define FLASHGOLD_DIRECTION_FILTER_CLOCK_MQH
#include "DirectionFilterCore.mqh"

// Current broker quote sessions, in server-calendar day/seconds. This metadata
// has no historical holiday/early-close calendar. Unknown/out-of-session bars
// retain nominal ends; D1 and higher are not reconstructed from weekly hours.
struct FgfQuoteSession { int day,fromSecond,toSecond; };
struct FgfLastBarObservation { long time,revision; bool live; };
struct FgfExecutionClock { long nowMs; };

void FgfCaptureClock(FgfExecutionClock &clock,const long executionMs,const long tickMs)
  { clock.nowMs=MathMax(executionMs,tickMs); }
long FgfClockNow(const FgfExecutionClock &clock) { return clock.nowMs; }

void FgfResetObservation(FgfLastBarObservation &state)
  { state.time=-1; state.revision=-1; state.live=true; }

// Union touching sessions, including overnight and week-boundary continuations.
// Exact session end is excluded. An API-returned equal start/end is a full day.
bool FgfQuoteWindow(const FgfQuoteSession &sessions[],const long when,
                    long &from,long &to)
  {
   from=-1; to=-1;
   if(when<0 || ArraySize(sessions)==0) return false;
   MqlDateTime d;
   if(!TimeToStruct((datetime)(when/1000),d)) return false;
   const long dayMs=86400000,weekMs=604800000;
   long midnight=when-(long)(d.hour*3600+d.min*60+d.sec)*1000-when%1000;
   long week=midnight-(long)d.day_of_week*dayMs;
   int n=ArraySize(sessions);
   for(int pass=0;pass<=n*3;pass++)
     {
      bool changed=false;
      for(int copy=-1;copy<=1;copy++)
         for(int i=0;i<n;i++)
           {
            if(sessions[i].day<0 || sessions[i].day>6 ||
               sessions[i].fromSecond<0 || sessions[i].fromSecond>=86400 ||
               sessions[i].toSecond<0 || sessions[i].toSecond>=86400) continue;
            long a=week+(long)copy*weekMs+(long)sessions[i].day*dayMs+
                   (long)sessions[i].fromSecond*1000;
            long b=week+(long)copy*weekMs+(long)sessions[i].day*dayMs+
                   (long)sessions[i].toSecond*1000;
            if(b<=a) b+=dayMs;
            if(from<0)
              { if(a<=when && when<b) { from=a; to=b; changed=true; } }
            else if(a<=to && b>=from && (a<from || b>to))
              { from=MathMin(from,a); to=MathMax(to,b); changed=true; }
           }
      if(!changed) break;
     }
   return from>=0;
  }

long FgfSessionBarEnd(const long open,const long nominalEnd,const bool intraday,
                       const FgfQuoteSession &sessions[])
  {
   long from,to;
   if(intraday && FgfQuoteWindow(sessions,open,from,to) && to>open && to<nominalEnd)
     {
      // A native fixed-timeframe candle can aggregate ticks on both sides of
      // an intraday break. Weekly sessions do not prove separate candles at
      // that break: retain the nominal end if quoting resumes inside it.
      MqlDateTime d;
      if(!TimeToStruct((datetime)(open/1000),d)) return nominalEnd;
      const long dayMs=86400000,weekMs=604800000;
      long midnight=open-(long)(d.hour*3600+d.min*60+d.sec)*1000-open%1000;
      long week=midnight-(long)d.day_of_week*dayMs;
      for(int copy=-1;copy<=1;copy++)
         for(int i=0;i<ArraySize(sessions);i++)
           {
            if(sessions[i].day<0 || sessions[i].day>6 ||
               sessions[i].fromSecond<0 || sessions[i].fromSecond>=86400 ||
               sessions[i].toSecond<0 || sessions[i].toSecond>=86400) continue;
            long next=week+(long)copy*weekMs+(long)sessions[i].day*dayMs+
                      (long)sessions[i].fromSecond*1000;
            if(next>to && next<nominalEnd) return nominalEnd;
           }
      return to;
     }
   return nominalEnd;
  }

// Clock age alone is never confirmation. Require a quote belonging to this
// newest bar, the known containing quote session to have ended, and no session
// open at this execution. Missing quotes/calendars and delayed open-session
// bars remain provisional. This is scoped to the supplied weekly calendar.
bool FgfLatestLive(const FgfBar &bar,const bool intraday,const long now,
                   const FgfQuoteSession &sessions[],const long tickMs)
  {
   if(!intraday || now<bar.end || tickMs<bar.time || tickMs>bar.end) return true;
   long from,to,currentFrom,currentTo;
   if(!FgfQuoteWindow(sessions,bar.time,from,to) || now<to) return true;
   return FgfQuoteWindow(sessions,now,currentFrom,currentTo);
  }

bool FgfObserveLatest(const FgfBar &bar,const bool intraday,const long now,
                      const FgfQuoteSession &sessions[],const long tickMs,
                      const long revision,const bool reset,FgfLastBarObservation &state)
  {
   // A redraw/repeated calculation cannot close a previously observed live
   // bar merely because its wall clock passed the schedule boundary.
   if(!reset && state.time==bar.time && state.revision==revision) return state.live;
   state.time=bar.time; state.revision=revision;
   state.live=FgfLatestLive(bar,intraday,now,sessions,tickMs);
   return state.live;
  }

// Literal chart-clock selector from Pine v1.2 lines533-602. All times ms.
// The caller supplies the request.security tuple (fp,fq), not arbitrary
// nearest bars. Missing history must remain missing through the fallback.
void FgfChartPick(const FgfConfig &cfg,const FgfBar &bar,
                  const double previousClose,const bool live,const long now,
                  const FgfFilterPoint &fp,const FgfFilterPoint &fq,
                  const FgfFilterPoint &previousClosePick,
                  FgfFilterPoint &pick,FgfFilterPoint &closePick,
                  long &clock,int &index,double &value)
  {
   const bool atOpen=cfg.checkMode==1 || (cfg.checkMode==2 && live);
   long clockC=bar.end;
   if(live)
     {
      clockC=now;
      if(bar.end>=0 && bar.end-1<clockC) clockC=bar.end-1;
      if(fp.end>=0 && fp.end-1<clockC) clockC=fp.end-1;
      if(clockC<bar.time) clockC=bar.time;
     }
   int selC=fp.end>=0 && clockC>=fp.end ? 1 : 2;
   int sel=atOpen ? (fp.end>=0 && fp.end<=bar.time ? 1 :
                     fq.end>=0 && fq.end<=bar.time ? 2 : 0) : selC;
   if(selC==1) closePick=fp; else closePick=fq;
   if(sel==1) pick=fp; else if(sel==2) pick=fq; else pick=previousClosePick;
   clock=atOpen ? bar.time : clockC;
   if(!atOpen)
      index=selC==1 ? (clockC==fp.end ? fp.index : fp.index+1) :
                         (clockC==fq.end ? fp.index-1 : fp.index);
   else if(sel==1) index=bar.time==fp.end ? fp.index : fp.index+1;
   else if(sel==2) index=bar.time==fq.end ? fp.index-1 : fp.index;
   else index=bar.time==previousClosePick.end ? previousClosePick.index : previousClosePick.index+1;
   value=cfg.checkMode==1 ? bar.open : cfg.checkMode==2 && live ? previousClose : bar.close;
  }
#endif
