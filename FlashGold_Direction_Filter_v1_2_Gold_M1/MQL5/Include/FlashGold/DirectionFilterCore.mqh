// Literal calculation core for FlashGold Direction Filter v1.2 (Pine v6).
// Reference SHA256: 387f49dc5c4b7a1050a85407b9e70dded367cffeeb15d24078d4cca63bbb204f
// Chronological bars; times are milliseconds. No terminal, drawing, file, or
// trading dependencies. Replaying the full input avoids Pine var intrabar
// accumulation. The adapter owns request.security mapping and chart clocks.
#ifndef FLASHGOLD_DIRECTION_FILTER_CORE_MQH
#define FLASHGOLD_DIRECTION_FILTER_CORE_MQH

#define FGF_MISSING_DIRECTION 99

struct FgfConfig
  {
   bool enabled;
   int levelMode,windowMode,minutes,bars,checkMode;
   double bandAtr;
   bool against,allowBuy,allowSell;
   double spreadPts,entryDistPts;
   int holdBars;
   double holdFavPts;
   bool onePerBar;
   int distUnit;
   double burstAtr,entryDistAtr,holdFavAtr,burstPts;
   bool useBurst,anyCombo;
   int driftBars;
   bool useDrift,useZones;
   int rsiLen,fastLen,minAligned;
   bool flatParent,ignoreNa,childEnabled[6];
   int scoreWindow,scoreHorizon;
   double tickSize;
  };

struct FgfBar
  {
   long time,end;
   double open,high,low,close;
  };

struct FgfFilterPoint
  {
   int index;
   long time,end;
   double atr;
   int parent,aligned,active;
   bool buy,sell;
   double signalPrice;
   long armedAt;
   int armedBar;
   double armedPrice;
   int armedDir,armedId;
   double armedAtr;
   double scores[7]; // level1, levelH, signal1, signalH, reverse1, reverseH, level1 count
  };

struct FgfGate
  {
   bool armed,open,onSigBar,buyOK,sellOK,sigOk,newSignal,ended,expired,displayOpen;
   int zone;
   long clock,endMs;
   int index;
   double value,band,upper,lower;
  };

bool FgfNumber(const double value)
  {
   return value!=EMPTY_VALUE && MathIsValidNumber(value);
  }

// Actual Pine v6 probes (2026-10-13) measured an absolute 1e-10 tolerance.
// In particular, 4.9e-10 != 0 and 100.0000000001 > 100, while 1e-10 == 0.
// Preserve binary64 cancellation before applying the tolerance; rounding each
// operand to nine decimals contradicts those observed results.
const double FGF_COMPARE_EPSILON=1e-10;
bool FgfGT(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && a-b>FGF_COMPARE_EPSILON; }
bool FgfLT(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && a-b< -FGF_COMPARE_EPSILON; }
bool FgfGE(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && a-b>= -FGF_COMPARE_EPSILON; }
bool FgfLE(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && a-b<=FGF_COMPARE_EPSILON; }
bool FgfEQ(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && MathAbs(a-b)<=FGF_COMPARE_EPSILON; }
bool FgfNE(const double a,const double b) { return FgfNumber(a) && FgfNumber(b) && MathAbs(a-b)>FGF_COMPARE_EPSILON; }

void FgfDefaults(FgfConfig &c)
  {
   ZeroMemory(c);
   c.enabled=true; c.levelMode=0; c.windowMode=0; c.minutes=60; c.bars=1;
   c.checkMode=0; c.bandAtr=0.25; c.against=true; c.allowBuy=true; c.allowSell=true;
   c.spreadPts=25.0; c.entryDistPts=50.0; c.holdBars=0; c.holdFavPts=5.0;
   c.onePerBar=true; c.distUnit=0; c.burstAtr=0.5; c.entryDistAtr=0.25;
   c.holdFavAtr=0.1; c.burstPts=172.0; c.useBurst=true; c.anyCombo=false;
   c.driftBars=60; c.useDrift=false; c.useZones=true; c.rsiLen=14; c.fastLen=2;
   c.minAligned=2; c.flatParent=false; c.ignoreNa=true;
   c.childEnabled[0]=true; c.childEnabled[1]=true; c.childEnabled[2]=true;
   c.scoreWindow=500; c.scoreHorizon=10;
   c.tickSize=0.01; // Adapter must replace this with the instrument's trade tick size.
  }

bool FgfValidate(const FgfConfig &c,string &error)
  {
   error="";
   if(c.levelMode<0 || c.levelMode>1 || c.windowMode<0 || c.windowMode>2 ||
      c.checkMode<0 || c.checkMode>2 || c.distUnit<0 || c.distUnit>1)
      error="Unknown level, permission, price-check, or distance mode.";
   else if(c.minutes<1 || c.bars<1 || c.holdBars<0 || c.driftBars<1)
      error="Minutes/candles/drift must be positive; hold bars must be nonnegative.";
   else if(c.rsiLen<2 || c.fastLen<1 || c.minAligned<0 || c.minAligned>6)
      error="RSI length >= 2, fast length >= 1, and alignment in [0,6] are required.";
   else if(c.scoreWindow<0 || c.scoreWindow>500 || c.scoreHorizon<2 || c.scoreHorizon>100)
      error="Score window must be in [0,500] and horizon in [2,100].";
   else if(!FgfNumber(c.tickSize) || c.tickSize<=0.0)
      error="The instrument trade tick size must be finite and positive.";
   else if(!FgfNumber(c.bandAtr) || c.bandAtr<0.0 ||
           !FgfNumber(c.spreadPts) || c.spreadPts<0.0 ||
           !FgfNumber(c.entryDistPts) || c.entryDistPts<0.0 ||
           !FgfNumber(c.holdFavPts) || c.holdFavPts<0.0 ||
           !FgfNumber(c.burstAtr) || c.burstAtr<0.0 ||
           !FgfNumber(c.entryDistAtr) || c.entryDistAtr<0.0 ||
           !FgfNumber(c.holdFavAtr) || c.holdFavAtr<0.0 ||
           !FgfNumber(c.burstPts) || c.burstPts<0.0)
      error="Price thresholds and spread must be finite and nonnegative.";
   return error=="";
  }

void FgfEmptyPoint(FgfFilterPoint &p)
  {
   ZeroMemory(p);
   p.index=-1; p.time=-1; p.end=-1; p.atr=EMPTY_VALUE;
   p.parent=FGF_MISSING_DIRECTION; p.aligned=-1; p.active=-1;
   p.signalPrice=EMPTY_VALUE; p.armedAt=-1; p.armedBar=-1;
   p.armedPrice=EMPTY_VALUE; p.armedAtr=EMPTY_VALUE;
   for(int k=0;k<7;k++) p.scores[k]=EMPTY_VALUE;
  }

bool FgfBarValid(const FgfBar &b)
  {
   return b.time>=0 && b.end>=b.time && FgfNumber(b.open) && FgfNumber(b.high) &&
          FgfNumber(b.low) && FgfNumber(b.close) && b.high>=b.low &&
          b.high>=b.open && b.high>=b.close && b.low<=b.open && b.low<=b.close;
  }

bool FgfDirectionValid(const int dir)
  {
   return dir==-1 || dir==0 || dir==1 || dir==FGF_MISSING_DIRECTION;
  }

// Wilder RMA seed: rsiLen changes, starting at chronological index 1.
// SMA needs fastLen valid RSI samples. Missing fast comparisons return flat,
// matching the Pine ternary even during warm-up. As in the earlier XPW core,
// a completely flat RSI seed uses down==0 -> 100; its TDI direction is flat.
bool FgfTdiSeries(const FgfBar &bars[],const int rsiLen,const int fastLen,int &dirs[])
  {
   const int n=ArraySize(bars);
   ArrayResize(dirs,0);
   if(rsiLen<2 || fastLen<1) return false;
   if(ArrayResize(dirs,n)!=n) return false;
   ArrayInitialize(dirs,0);
   double rsi[];
   if(ArrayResize(rsi,n)!=n) { ArrayResize(dirs,0); return false; }
   ArrayInitialize(rsi,EMPTY_VALUE);
   double gain=0.0,loss=0.0,fastPrev=EMPTY_VALUE,fastSum=0.0;
   for(int i=0;i<n;i++)
     {
      if(!FgfBarValid(bars[i]) || (i>0 && bars[i].time<=bars[i-1].time))
        { ArrayResize(dirs,0); return false; }
      if(i==0) continue;
      const double up=MathMax(bars[i].close-bars[i-1].close,0.0);
      const double dn=MathMax(bars[i-1].close-bars[i].close,0.0);
      if(i<=rsiLen)
        {
         gain+=up; loss+=dn;
         if(i<rsiLen) continue;
         gain/=rsiLen; loss/=rsiLen;
        }
      else
        {
         gain=(gain*(rsiLen-1)+up)/rsiLen;
         loss=(loss*(rsiLen-1)+dn)/rsiLen;
        }
      // The built-in Pine ta.rsi uses tolerant zero guards as verified on a
      // tiny-move series. Loss-zero takes precedence when both are near zero.
      rsi[i]=FgfEQ(loss,0.0) ? 100.0 : FgfEQ(gain,0.0) ? 0.0 : 100.0-100.0/(1.0+gain/loss);
      fastSum+=rsi[i];
      if(i-rsiLen>=fastLen) fastSum-=rsi[i-fastLen];
      if(i-rsiLen+1>=fastLen)
        {
         const double fast=fastSum/fastLen;
         if(FgfNumber(fastPrev)) dirs[i]=FgfGT(fast,fastPrev) ? 1 : FgfLT(fast,fastPrev) ? -1 : 0;
         fastPrev=fast;
        }
     }
   return true;
  }

// The four counters belonging to one resolved forecast at evaluation bar at.
// Each score window contains evaluation bars, including unscored/flat bars.
void FgfHit(const FgfBar &bars[],const int &directions[],const int at,
            const int rule,const int horizon,double &upN,double &upH,double &dnN,double &dnH)
  {
   upN=0.0; upH=0.0; dnN=0.0; dnH=0.0;
   if(at<horizon || at<0 || at>=ArraySize(bars)) return;
   const int pd=directions[(at-horizon)*3+rule];
   const double move=bars[at].close-bars[at-horizon].close;
   if(pd==1 && FgfNE(move,0.0)) { upN=1.0; if(FgfGT(move,0.0)) upH=1.0; }
   if(pd==-1 && FgfNE(move,0.0)) { dnN=1.0; if(FgfLT(move,0.0)) dnH=1.0; }
  }

// parents/zones are the adapter's already-mapped request.security results.
// All supplied arrays are chronological and every filter bar is evaluated.
bool FgfBuildFilter(const FgfConfig &c,const FgfBar &bars[],const int &parents[],
                    const int &zonesFlat[],FgfFilterPoint &out[])
  {
   ArrayResize(out,0);
   string error;
   if(!FgfValidate(c,error)) return false;
   const int n=ArraySize(bars);
   if(ArraySize(parents)!=n || (long)ArraySize(zonesFlat)!=(long)n*6) return false;
   // Preflight before constructing output, so failure never exposes partial state.
   for(int i=0;i<n;i++)
     {
      if(!FgfBarValid(bars[i]) || !FgfDirectionValid(parents[i]) ||
         (i>0 && bars[i].time<=bars[i-1].time)) return false;
      for(int z=0;z<6;z++) if(!FgfDirectionValid(zonesFlat[i*6+z])) return false;
     }
   if(ArrayResize(out,n)!=n) return false;
   int directions[];
   if(ArrayResize(directions,n*3)!=n*3) { ArrayResize(out,0); return false; }
   ArrayInitialize(directions,0);
   double counts[6][4];
   for(int s=0;s<6;s++) for(int k=0;k<4;k++) counts[s][k]=0.0;
   bool holdActive=false,holdIsBuy=false;
   int holdSignalBar=-1,lastEntryBar=-1;
   double holdSignalMid=EMPTY_VALUE,atr=EMPTY_VALUE,trSeed=0.0;
   long armedAt=-1;
   int armedBar=-1,armedDir=0,armedId=0;
   double armedPrice=EMPTY_VALUE,armedAtr=EMPTY_VALUE;
   for(int i=0;i<n;i++)
     {
      FgfFilterPoint p;
      FgfEmptyPoint(p);
      p.index=i; p.time=bars[i].time; p.end=bars[i].end;
      const double tr=i==0 ? bars[i].high-bars[i].low :
         MathMax(bars[i].high-bars[i].low,MathMax(MathAbs(bars[i].high-bars[i-1].close),MathAbs(bars[i].low-bars[i-1].close)));
      if(i<14)
        {
         trSeed+=tr;
         if(i==13) atr=trSeed/14.0;
        }
      else atr=(atr*13.0+tr)/14.0;
      p.atr=atr;
      p.parent=parents[i]==FGF_MISSING_DIRECTION ? 0 : parents[i];
      p.aligned=0; p.active=0;
      for(int z=0;z<6;z++)
        {
         const int d=zonesFlat[i*6+z];
         const bool on=c.childEnabled[z] && (!c.ignoreNa || d!=FGF_MISSING_DIRECTION);
         if(on) p.active++;
         if(on && p.parent!=0 && d==p.parent) p.aligned++;
        }
      const int required=MathMin(c.minAligned,p.active);
      const bool parentFlatAllowed=c.flatParent && p.parent==0;
      const bool zoneReady=p.active==0 || p.aligned>=required;
      const bool zoneBuy=!c.useZones || ((p.parent==1 || parentFlatAllowed) && zoneReady);
      const bool zoneSell=!c.useZones || ((p.parent==-1 || parentFlatAllowed) && zoneReady);
      const double halfSpread=c.spreadPts*c.tickSize*0.5;
      const double bid=bars[i].close-halfSpread,ask=bars[i].close+halfSpread;
      const double mid=(bid+ask)*0.5;
      // Keep the Pine /tick then *tick evaluation order; do not grid-round entries.
      const double atrPts=FgfNumber(atr) ? atr/c.tickSize : EMPTY_VALUE;
      const double burstThreshold=c.distUnit==0 ? (FgfNumber(atrPts) ? c.burstAtr*atrPts : EMPTY_VALUE) : c.burstPts;
      const double entryDistance=c.distUnit==0 ? (FgfNumber(atrPts) ? c.entryDistAtr*atrPts : EMPTY_VALUE) : c.entryDistPts;
      const double holdFavorable=c.distUnit==0 ? (FgfNumber(atrPts) ? c.holdFavAtr*atrPts : EMPTY_VALUE) : c.holdFavPts;
      const double burst=i>0 ? (mid-((bars[i-1].close-halfSpread)+(bars[i-1].close+halfSpread))*0.5)/c.tickSize : EMPTY_VALUE;
      const double drift=i>=c.driftBars ? (mid-((bars[i-c.driftBars].close-halfSpread)+(bars[i-c.driftBars].close+halfSpread))*0.5)/c.tickSize : EMPTY_VALUE;
      const bool burstBuy=FgfGE(burst,burstThreshold);
      const bool burstSell=FgfNumber(burstThreshold) && FgfLE(burst,-burstThreshold);
      const bool driftBuy=!c.useDrift || FgfGT(drift,0.0);
      const bool driftSell=!c.useDrift || FgfLT(drift,0.0);
      // Literal Pine: UseBurst is only consulted in the AnyCombo branch.
      const bool rawBuy=c.anyCombo ? zoneBuy && (!c.useBurst || burstBuy || p.parent==1) : zoneBuy && burstBuy;
      const bool rawSell=c.anyCombo ? zoneSell && (!c.useBurst || burstSell || p.parent==-1) : zoneSell && burstSell;
      const bool buyCandidate=rawBuy && driftBuy,sellCandidate=rawSell && driftSell;
      const bool canFire=!c.onePerBar || lastEntryBar<0 || lastEntryBar!=i;
      double buyEntry=EMPTY_VALUE,sellEntry=EMPTY_VALUE;
      if(buyCandidate && canFire)
        {
         if(c.holdBars==0)
           { buyEntry=FgfNumber(entryDistance) ? ask+entryDistance*c.tickSize : EMPTY_VALUE; p.buy=true; lastEntryBar=i; }
         else if(!holdActive)
           { holdActive=true; holdIsBuy=true; holdSignalBar=i; holdSignalMid=mid; }
         else if(holdIsBuy)
           {
            const double move=(mid-holdSignalMid)/c.tickSize;
            if(i-holdSignalBar>=c.holdBars && FgfGE(move,holdFavorable))
              { buyEntry=FgfNumber(entryDistance) ? ask+entryDistance*c.tickSize : EMPTY_VALUE; p.buy=true; lastEntryBar=i; holdActive=false; }
           }
        }
      // canFire deliberately remains the value computed before the buy branch.
      if(sellCandidate && canFire)
        {
         if(c.holdBars==0)
           { sellEntry=FgfNumber(entryDistance) ? bid-entryDistance*c.tickSize : EMPTY_VALUE; p.sell=true; lastEntryBar=i; }
         else if(!holdActive)
           { holdActive=true; holdIsBuy=false; holdSignalBar=i; holdSignalMid=mid; }
         else if(!holdIsBuy)
           {
            const double move=(holdSignalMid-mid)/c.tickSize;
            if(i-holdSignalBar>=c.holdBars && FgfGE(move,holdFavorable))
              { sellEntry=FgfNumber(entryDistance) ? bid-entryDistance*c.tickSize : EMPTY_VALUE; p.sell=true; lastEntryBar=i; holdActive=false; }
           }
        }
      if(holdActive && ((holdIsBuy && !zoneBuy) || (!holdIsBuy && !zoneSell)))
        { holdActive=false; holdSignalBar=-1; holdSignalMid=EMPTY_VALUE; }
      p.signalPrice=p.buy ? buyEntry : p.sell ? sellEntry : EMPTY_VALUE;
      if(p.buy || p.sell)
        {
         armedAt=bars[i].end; armedBar=i;
         armedPrice=c.levelMode==0 && FgfNumber(p.signalPrice) ? p.signalPrice : bars[i].close;
         armedDir=p.buy ? 1 : -1; armedId++; armedAtr=atr;
        }
      p.armedAt=armedAt; p.armedBar=armedBar; p.armedPrice=armedPrice;
      p.armedDir=armedDir; p.armedId=armedId; p.armedAtr=armedAtr;
      directions[i*3]=!FgfNumber(armedPrice) ? 0 : FgfGT(bars[i].close,armedPrice) ? 1 :
         FgfLT(bars[i].close,armedPrice) ? -1 : armedBar==i ? armedDir : 0;
      directions[i*3+1]=armedDir; directions[i*3+2]=-armedDir;
      for(int s=0;s<6;s++)
        {
         const int rule=s/2,horizon=s%2==0 ? 1 : c.scoreHorizon;
         double a,b,d,e;
         FgfHit(bars,directions,i,rule,horizon,a,b,d,e);
         counts[s][0]+=a; counts[s][1]+=b; counts[s][2]+=d; counts[s][3]+=e;
         if(c.scoreWindow>0 && i>=c.scoreWindow)
           {
            FgfHit(bars,directions,i-c.scoreWindow,rule,horizon,a,b,d,e);
            counts[s][0]-=a; counts[s][1]-=b; counts[s][2]-=d; counts[s][3]-=e;
           }
         p.scores[s]=counts[s][0]>0.0 && counts[s][2]>0.0 ?
            0.5*(counts[s][1]/counts[s][0]+counts[s][3]/counts[s][2]) : EMPTY_VALUE;
        }
      p.scores[6]=counts[0][0]+counts[0][2];
      out[i]=p;
     }
   return true;
  }

void FgfEvaluateGate(const FgfConfig &c,const FgfFilterPoint &p,const long clock,
                     const int index,const double value,const int prevId,
                     const bool prevEnded,const bool first,const long now,FgfGate &g)
  {
   ZeroMemory(g);
   g.clock=clock; g.index=index; g.value=value; g.endMs=-1;
   g.upper=EMPTY_VALUE; g.lower=EMPTY_VALUE;
   g.armed=p.armedAt>=0 && clock>=p.armedAt;
   if(c.windowMode==1 && g.armed) g.endMs=p.armedAt+(long)c.minutes*60000;
   g.open=g.armed && (c.windowMode==1 ? clock<g.endMs :
          c.windowMode==2 ? (long)index<(long)p.armedBar+c.bars : true);
   g.onSigBar=g.armed && index==p.armedBar;
   g.band=c.bandAtr*(FgfNumber(p.armedAtr) ? p.armedAtr : 0.0);
   bool inUp=false,inDn=false;
   if(FgfNumber(p.armedPrice))
     {
      const bool hasBand=FgfGT(g.band,0.0);
      g.upper=hasBand ? MathCeil((p.armedPrice+g.band)/c.tickSize-1e-9)*c.tickSize : p.armedPrice;
      g.lower=hasBand ? MathFloor((p.armedPrice-g.band)/c.tickSize+1e-9)*c.tickSize : p.armedPrice;
      if(FgfNumber(value))
        {
         const bool atBuy=g.onSigBar && p.armedDir>0 && FgfGE(value,p.armedPrice);
         const bool atSell=g.onSigBar && p.armedDir<0 && FgfLE(value,p.armedPrice);
         inUp=hasBand ? FgfGT(value,g.upper+c.tickSize/2.0) : FgfGT(value,p.armedPrice) || atBuy;
         inDn=hasBand ? FgfLT(value,g.lower-c.tickSize/2.0) : FgfLT(value,p.armedPrice) || atSell;
        }
     }
   g.sigOk=g.armed && (p.armedDir>0 ? inUp : p.armedDir<0 ? inDn : false);
   g.buyOK=!c.enabled || (g.open && c.allowBuy && inUp && (c.against || p.armedDir>0));
   g.sellOK=!c.enabled || (g.open && c.allowSell && inDn && (c.against || p.armedDir<0));
   g.newSignal=!first && p.armedId>prevId;
   g.zone=!c.enabled ? 2 : g.buyOK ? 1 : g.sellOK ? -1 : 0;
   g.ended=g.armed && !g.open;
   g.expired=c.enabled && g.ended && !prevEnded && !first;
   g.displayOpen=g.open && !(c.checkMode==0 && c.windowMode==1 && now>=g.endMs);
  }

#endif
