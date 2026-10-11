#ifndef BTC_METHOD_SIGNALS_MQH
#define BTC_METHOD_SIGNALS_MQH

// Research hypotheses, not claims of a profitable trading edge.
enum ENUM_BTC_METHOD
  {
   BTC_TREND_PULLBACK=0,
   BTC_BREAKOUT_RETEST=1,
   BTC_EFFICIENCY_BREAKOUT=2,
   BTC_RANGE_REVERSION=3,
   BTC_TIME_MOMENTUM=4,
   BTC_DONCHIAN_TREND=5
  };

struct BTC_METHOD_CONFIG
  {
   ENUM_BTC_METHOD method;
   ENUM_TIMEFRAMES period;
   int length;                 // Channel or momentum lookback (bars)
   int exit_bars;              // Opposite channel exit for Donchian method
   double efficiency;          // Minimum trend ER / maximum range ER
   int pullback_ema;
   double clearance_atr;
  };

struct BTC_METHOD_SIGNAL
  {
   datetime time,decision_time,macro_close;
   int side,trend,macro;
   double close,atr,mean,er;
  };

class CBTCMethodSignals
  {
private:
   string m_symbol;
   BTC_METHOD_CONFIG m_c;
   int m_atr,m_fast,m_slow,m_pull,m_bands,m_rsi,m_hfast,m_hslow,m_hatr;

   bool Value(const int handle,const int buffer,const int shift,double &value)
     {
      double a[];
      if(CopyBuffer(handle,buffer,shift,1,a)!=1 || !MathIsValidNumber(a[0]) || a[0]==EMPTY_VALUE)
         return false;
      value=a[0]; return true;
     }

   void Channel(const MqlRates &r[],const int start,const int count,double &high,double &low)
     {
      high=-DBL_MAX; low=DBL_MAX;
      for(int i=start;i<start+count;i++) { high=MathMax(high,r[i].high); low=MathMin(low,r[i].low); }
     }

public:
   CBTCMethodSignals(void)
     {
      m_atr=m_fast=m_slow=m_pull=m_bands=m_rsi=m_hfast=m_hslow=m_hatr=INVALID_HANDLE;
     }

   void Release(void)
     {
      int h[]={m_atr,m_fast,m_slow,m_pull,m_bands,m_rsi,m_hfast,m_hslow,m_hatr};
      for(int i=0;i<ArraySize(h);i++) if(h[i]!=INVALID_HANDLE) IndicatorRelease(h[i]);
      m_atr=m_fast=m_slow=m_pull=m_bands=m_rsi=m_hfast=m_hslow=m_hatr=INVALID_HANDLE;
     }

   bool Create(const string symbol,const BTC_METHOD_CONFIG &c)
     {
      m_symbol=symbol; m_c=c;
      m_atr=iATR(symbol,c.period,14);
      m_fast=iMA(symbol,c.period,50,0,MODE_EMA,PRICE_CLOSE);
      m_slow=iMA(symbol,c.period,200,0,MODE_EMA,PRICE_CLOSE);
      m_pull=iMA(symbol,c.period,c.pullback_ema,0,MODE_EMA,PRICE_CLOSE);
      m_bands=iBands(symbol,c.period,20,0,2.0,PRICE_CLOSE);
      m_rsi=iRSI(symbol,c.period,14,PRICE_CLOSE);
      m_hfast=iMA(symbol,PERIOD_H4,50,0,MODE_EMA,PRICE_CLOSE);
      m_hslow=iMA(symbol,PERIOD_H4,200,0,MODE_EMA,PRICE_CLOSE);
      m_hatr=iATR(symbol,PERIOD_H4,14);
      if(m_atr==INVALID_HANDLE || m_fast==INVALID_HANDLE || m_slow==INVALID_HANDLE ||
         m_pull==INVALID_HANDLE || m_bands==INVALID_HANDLE || m_rsi==INVALID_HANDLE ||
         m_hfast==INVALID_HANDLE || m_hslow==INVALID_HANDLE || m_hatr==INVALID_HANDLE)
        { Release(); return false; }
      return true;
     }

   // shift is always >= 1. Every channel excludes the candle being tested.
   // Historical macro values use the last H4 candle completed by decision_time.
   bool Evaluate(const int shift,BTC_METHOD_SIGNAL &s)
     {
      if(shift<1) return false;
      ZeroMemory(s);
      int count=MathMax(MathMax(m_c.length+12,m_c.exit_bars+2),35);
      MqlRates r[]; ArraySetAsSeries(r,true);
      if(CopyRates(m_symbol,m_c.period,shift,count,r)!=count) return false;
      s.time=r[0].time;
      s.decision_time=s.time+PeriodSeconds(m_c.period);
      s.close=r[0].close;
      if(s.close<=0) return false;
      double fast,slow,old_slow,pull;
      // Request CopyBuffer first: tester calculates indicator handles lazily.
      if(!Value(m_atr,0,shift,s.atr) || !Value(m_fast,0,shift,fast) ||
         !Value(m_slow,0,shift,slow) || !Value(m_slow,0,shift+4,old_slow) ||
         !Value(m_pull,0,shift,pull) || s.atr<=0 || BarsCalculated(m_slow)<205)
         return false;
      double atr_pct=100*s.atr/s.close;
      double max_atr_pct=m_c.period==PERIOD_D1 ? 6.0 : 4.0;
      bool allow_entry=atr_pct>=0.10 && atr_pct<=max_atr_pct;
      s.trend=(fast>slow && slow>old_slow) ? 1 : (fast<slow && slow<old_slow ? -1 : 0);
      double change=0;
      for(int i=0;i<20;i++) change+=MathAbs(r[i].close-r[i+1].close);
      s.er=change>0 ? MathAbs(r[0].close-r[20].close)/change : 0;
      s.mean=pull;

      int hs=iBarShift(m_symbol,PERIOD_H4,s.decision_time,false);
      if(hs<0) return false;
      datetime ht=iTime(m_symbol,PERIOD_H4,hs);
      if(ht+PeriodSeconds(PERIOD_H4)>s.decision_time) hs++;
      double hf,hl,ho,ha;
      if(!Value(m_hfast,0,hs,hf) || !Value(m_hslow,0,hs,hl) ||
         !Value(m_hslow,0,hs+3,ho) || !Value(m_hatr,0,hs,ha) || ha<=0 ||
         BarsCalculated(m_hslow)<204) return false;
      s.macro_close=iTime(m_symbol,PERIOD_H4,hs)+PeriodSeconds(PERIOD_H4);
      if(s.macro_close>s.decision_time) return false;
      if(MathAbs(hf-hl)>=0.25*ha)
         s.macro=(hf>hl && hl>ho) ? 1 : (hf<hl && hl<ho ? -1 : 0);

      if(m_c.method==BTC_TREND_PULLBACK)
        {
         bool touch_buy=false,touch_sell=false;
         for(int j=0;j<3;j++)
           {
            double p;
            if(!Value(m_pull,0,shift+j,p)) return false;
            if(r[j].low<=p) touch_buy=true;
            if(r[j].high>=p) touch_sell=true;
           }
         if(s.macro==1 && touch_buy && s.close>pull && s.close>r[1].high &&
            s.close>r[0].open && s.close-pull<=1.5*s.atr) s.side=1;
         if(s.macro==-1 && touch_sell && s.close<pull && s.close<r[1].low &&
            s.close<r[0].open && pull-s.close<=1.5*s.atr) s.side=-1;
        }
      else if(m_c.method==BTC_BREAKOUT_RETEST)
        {
         // Scan the last eight completed candles for the newest breakout.
         for(int j=1;j<=8;j++)
           {
            double high,low,ba;
            Channel(r,j+1,m_c.length,high,low);
            if(!Value(m_atr,0,shift+j,ba)) return false;
            int direction=r[j].close>high+m_c.clearance_atr*ba ? 1 :
                          (r[j].close<low-m_c.clearance_atr*ba ? -1 : 0);
            if(direction==0) continue;
            double level=direction==1 ? high : low;
            bool invalid=false,already_confirmed=false;
            for(int k=j-1;k>=1;k--)
              {
               if(direction==1 && r[k].close<level-0.75*ba) invalid=true;
               if(direction==-1 && r[k].close>level+0.75*ba) invalid=true;
               if(direction==1 && r[k].low<=level+0.25*ba && r[k].close>level+0.10*ba && r[k].close>r[k].open)
                  already_confirmed=true;
               if(direction==-1 && r[k].high>=level-0.25*ba && r[k].close<level-0.10*ba && r[k].close<r[k].open)
                  already_confirmed=true;
              }
            if(!invalid && !already_confirmed && direction==s.macro)
              {
               if(direction==1 && r[0].low<=level+0.25*ba && s.close>level+0.10*ba && s.close>r[0].open)
                  s.side=1;
               if(direction==-1 && r[0].high>=level-0.25*ba && s.close<level-0.10*ba && s.close<r[0].open)
                  s.side=-1;
              }
            break;
           }
        }
      else if(m_c.method==BTC_EFFICIENCY_BREAKOUT)
        {
         double high,low; Channel(r,1,m_c.length,high,low);
         if(s.er>=m_c.efficiency)
           {
            if(s.trend==1 && s.close>high+m_c.clearance_atr*s.atr) s.side=1;
            if(s.trend==-1 && s.close<low-m_c.clearance_atr*s.atr) s.side=-1;
           }
        }
      else if(m_c.method==BTC_RANGE_REVERSION)
        {
         double upper,lower,old_upper,old_lower,rsi;
         if(!Value(m_bands,0,shift,s.mean) || !Value(m_bands,1,shift,upper) ||
            !Value(m_bands,2,shift,lower) || !Value(m_bands,1,shift+1,old_upper) ||
            !Value(m_bands,2,shift+1,old_lower) || !Value(m_rsi,0,shift+1,rsi)) return false;
         if(s.er<=m_c.efficiency)
           {
            if(r[1].close<old_lower && s.close>lower && s.close<upper && rsi<=35) s.side=1;
            if(r[1].close>old_upper && s.close<upper && s.close>lower && rsi>=65) s.side=-1;
           }
        }
      else if(m_c.method==BTC_TIME_MOMENTUM)
        {
         // Direction of a fixed 7/14-day return, with a 200-bar price filter.
         s.trend=s.close>r[m_c.length].close && s.close>slow ? 1 :
                 (s.close<r[m_c.length].close && s.close<slow ? -1 : 0);
         s.side=s.trend;
        }
      else if(m_c.method==BTC_DONCHIAN_TREND)
        {
         // Daily trend following without an EMA-direction entry gate.
         double high,low,exit_high,exit_low;
         Channel(r,1,m_c.length,high,low);
         Channel(r,1,m_c.exit_bars,exit_high,exit_low);
         s.trend=s.close>exit_high ? 1 : (s.close<exit_low ? -1 : 0);
         if(s.close>high+m_c.clearance_atr*s.atr) s.side=1;
         if(s.close<low-m_c.clearance_atr*s.atr) s.side=-1;
        }
      // A volatility gate affects entries, never the state needed for exits.
      if(!allow_entry) s.side=0;
      return true;
     }
  };
#endif
