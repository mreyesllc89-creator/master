#ifndef FLASHGOLD_DIRECTION_FILTER_RENDER_MQH
#define FLASHGOLD_DIRECTION_FILTER_RENDER_MQH
#include <Canvas\Canvas.mqh>
#include "DirectionFilterCore.mqh"

// Pine v6 named colors, https://www.tradingview.com/pine-script-docs/visuals/colors/.
// All drawings use pixel resources: none contributes a value to the price scale.
#define FGF_RGB_GREEN  0x4CAF50
#define FGF_RGB_LIME   0x00E676
#define FGF_RGB_RED    0xF23645
#define FGF_RGB_GRAY   0x787B86
#define FGF_RGB_BLACK  0x363A45
#define FGF_RGB_WHITE  0xFFFFFF
#define FGF_RGB_ORANGE 0xFF9800
#define FGF_RGB_AQUA   0x00BCD4

struct FgfVisualConfig
  {
   bool showBg,showLv,sigMark,showTbl,showScore;
   int tablePos; // right top/middle/bottom, left top/middle/bottom, center top/bottom
   string filterLabel;
   int digits;
   int filterSeconds;
   long nowMs; // Same broker-time basis as chart[]; only the display countdown uses it.
  };

struct FgfVisualSegment
  {
   int from,to,labelFrom,dir;
   long born;
   double level,upper,lower;
   bool drawn,band;
  };

// CCanvas normally deletes an object by name even if someone has rebound it.
// Own the resource separately, and only remove an object whose binding is ours.
class CFgfOwnedCanvas : public CCanvas
  {
private:
   string m_binding;
public:
                    ~CFgfOwnedCanvas(void) { Destroy(); }
   virtual bool Create(const string name,const int width,const int height,
                       ENUM_COLOR_FORMAT format=COLOR_FORMAT_XRGB_NOALPHA)
     {
      Destroy();
      if(width<=0 || height<=0 || (long)width*height>2147483647 ||
         ArrayResize(m_pixels,width*height)!=width*height) return false;
      // Resources are scoped to this MQL program. The monotonic suffix keeps
      // separate canvases distinct even when their caller prefixes coincide.
      static ulong serial=0; serial++;
      m_rcname="::FGF12C_"+(string)GetMicrosecondCount()+"_"+(string)serial;
      ArrayInitialize(m_pixels,0);
      if(!ResourceCreate(m_rcname,m_pixels,width,height,0,0,0,format))
        { Destroy(); return false; }
      m_width=width; m_height=height; m_format=format;
      return true;
     }
   bool CreateSurface(const long chartId,const string name,const int width,const int height)
     {
      if(ObjectFind(chartId,name)>=0 || !Create(name,width,height,COLOR_FORMAT_ARGB_NORMALIZE)) return false;
      if(!ObjectCreate(chartId,name,OBJ_BITMAP_LABEL,0,0,0)) { Destroy(); return false; }
      m_chart_id=chartId; m_objname=name; m_objtype=OBJ_BITMAP_LABEL;
      m_binding=ObjectGetString(chartId,name,OBJPROP_BMPFILE);
      // MT5 bitmap-label pixels are inset one pixel from chart XY coordinates.
      // Use the same origin for native price/time coordinates on both axes.
      // This MT5 distinction is independently reproduced by canvas authors:
      // https://www.mql5.com/en/forum/455324/page4 (#32 and #33).
      if(!ObjectSetInteger(chartId,name,OBJPROP_CORNER,CORNER_LEFT_UPPER) ||
         !ObjectSetInteger(chartId,name,OBJPROP_ANCHOR,ANCHOR_LEFT_UPPER) ||
         !ObjectSetInteger(chartId,name,OBJPROP_XDISTANCE,-1) ||
         !ObjectSetInteger(chartId,name,OBJPROP_YDISTANCE,-1)) { Destroy(); return false; }
      if(!ObjectSetString(chartId,name,OBJPROP_BMPFILE,m_rcname)) { Destroy(); return false; }
      m_binding=ObjectGetString(chartId,name,OBJPROP_BMPFILE);
      if(m_binding=="") { Destroy(); return false; }
      return true;
     }
   bool OwnsObject(void) const
     {
      return m_objname!="" && ObjectFind(m_chart_id,m_objname)>=0 &&
             ObjectGetString(m_chart_id,m_objname,OBJPROP_BMPFILE)==m_binding;
     }
   virtual void Destroy(void)
     {
      if(m_objname!="" && !OwnsObject()) m_objname="";
      CCanvas::Destroy(); m_binding="";
     }
  };

// Store straight ARGB and composite every translucent foreground primitive
// before publishing the normalized resource. Standard Canvas fills replace
// pixels, which would erase a level beneath a translucent label or table.
class CFgfBlendCanvas : public CFgfOwnedCanvas
  {
private:
   void Blend(const int index,const uint src)
     {
      uint sa=src>>24;
      if(sa==0) return;
      uint dst=m_pixels[index],da=dst>>24;
      if(sa==255 || da==0) { m_pixels[index]=src; return; }
      uint weight=sa*255+da*(255-sa),out=(((weight+127)/255)<<24);
      for(int shift=0;shift<=16;shift+=8)
        {
         uint channel=(((src>>shift)&255)*sa*255+((dst>>shift)&255)*da*(255-sa)+weight/2)/weight;
         out|=channel<<shift;
        }
      m_pixels[index]=out;
     }
   void Pixel(const int x,const int y,const uint clr)
     { if(x>=0 && y>=0 && x<m_width && y<m_height) Blend(y*m_width+x,clr); }
public:
   void LineHorizontal(int x1,int x2,const int y,const uint clr)
     {
      if(y<0 || y>=m_height) return;
      if(x1>x2) { int swap=x1; x1=x2; x2=swap; }
      x1=MathMax(0,x1); x2=MathMin(m_width-1,x2);
      for(int x=x1;x<=x2;x++) Blend(y*m_width+x,clr);
     }
   void LineVertical(const int x,int y1,int y2,const uint clr)
     {
      if(x<0 || x>=m_width) return;
      if(y1>y2) { int swap=y1; y1=y2; y2=swap; }
      y1=MathMax(0,y1); y2=MathMin(m_height-1,y2);
      for(int y=y1;y<=y2;y++) Blend(y*m_width+x,clr);
     }
   void FillRectangle(int x1,int y1,int x2,int y2,const uint clr)
     {
      if(x1>x2) { int swap=x1; x1=x2; x2=swap; }
      if(y1>y2) { int swap=y1; y1=y2; y2=swap; }
      x1=MathMax(0,x1); x2=MathMin(m_width-1,x2);
      y1=MathMax(0,y1); y2=MathMin(m_height-1,y2);
      if(x1>x2 || y1>y2) return;
      for(int y=y1;y<=y2;y++) LineHorizontal(x1,x2,y,clr);
     }
   void Rectangle(int x1,int y1,int x2,int y2,const uint clr)
     {
      if(x1>x2) { int swap=x1; x1=x2; x2=swap; }
      if(y1>y2) { int swap=y1; y1=y2; y2=swap; }
      LineHorizontal(x1,x2,y1,clr);
      if(y2!=y1) LineHorizontal(x1,x2,y2,clr);
      if(y2-y1>1)
        { LineVertical(x1,y1+1,y2-1,clr); if(x2!=x1) LineVertical(x2,y1+1,y2-1,clr); }
     }
   void Line(int x1,int y1,const int x2,const int y2,const uint clr)
     {
      if(x1==x2) { LineVertical(x1,y1,y2,clr); return; }
      if(y1==y2) { LineHorizontal(x1,x2,y1,clr); return; }
      if(MathMax(x1,x2)<0 || MathMin(x1,x2)>=m_width ||
         MathMax(y1,y2)<0 || MathMin(y1,y2)>=m_height) return;
      int dx=MathAbs(x2-x1),dy=-MathAbs(y2-y1),sx=x1<x2?1:-1,sy=y1<y2?1:-1,err=dx+dy;
      while(true)
        {
         Pixel(x1,y1,clr); if(x1==x2 && y1==y2) break;
         int twice=2*err;
         if(twice>=dy) { err+=dy; x1+=sx; }
         if(twice<=dx) { err+=dx; y1+=sy; }
        }
     }
   void FillTriangle(const int x1,const int y1,const int x2,const int y2,
                     const int x3,const int y3,const uint clr)
     {
      int left=MathMax(0,MathMin(x1,MathMin(x2,x3))),right=MathMin(m_width-1,MathMax(x1,MathMax(x2,x3)));
      int top=MathMax(0,MathMin(y1,MathMin(y2,y3))),bottom=MathMin(m_height-1,MathMax(y1,MathMax(y2,y3)));
      for(int y=top;y<=bottom;y++) for(int x=left;x<=right;x++)
        {
         long a=(long)(x2-x1)*(y-y1)-(long)(y2-y1)*(x-x1);
         long b=(long)(x3-x2)*(y-y2)-(long)(y3-y2)*(x-x2);
         long c=(long)(x1-x3)*(y-y3)-(long)(y1-y3)*(x-x3);
         if((a>=0 && b>=0 && c>=0) || (a<=0 && b<=0 && c<=0)) Pixel(x,y,clr);
        }
     }
  };

class CFgfRenderer
  {
private:
   string m_prefix,m_basePrefix,m_error;
   long m_chartId;
   CFgfOwnedCanvas m_bg;
   CFgfBlendCanvas m_fg;
   int m_width,m_height,m_n,m_lastX;
   double m_spacing,m_min,m_max,m_tickSize;
   datetime m_mapTime;
   bool m_ready;
   long m_labelCutoff,m_lastBarTime;
   int m_committedZones;

   uint Ink(const uint rgb,const int transparency=0) const
     { return ((uint)MathRound(255.0*(100-transparency)/100.0)<<24)|rgb; }
   bool Valid(const double v) const
     { return MathIsValidNumber(v) && v!=EMPTY_VALUE; }
   int X(const int index) const
     { return (int)MathRound(m_lastX+(index-m_n+1)*m_spacing); }
   bool Y(const double value,int &y)
     {
      int x=0; y=0;
      // Interpolating rounded min/max pixel anchors rounded a second time and
      // disagreed with native horizontal lines by a pixel. Convert each price
      // with the native transform, preserving its actual quantization.
      if(!Valid(value)) { m_error="Price coordinate input is unavailable"; return false; }
      if(!ChartTimePriceToXY(m_chartId,0,m_mapTime,value,x,y))
        { m_error="Native price coordinate conversion failed: "+IntegerToString(GetLastError()); return false; }
      return true;
     }
   string Price(const double v,const int digits) const
     {
      if(!Valid(v)) return "-";
      // Pine format.mintick: quantize the displayed value to the symbol's
      // minimum tick (including nondecimal grids such as 0.25), ties up.
      double shown=m_tickSize>0?MathFloor(v/m_tickSize+0.5)*m_tickSize:v;
      return DoubleToString(shown,digits);
     }
   string Pct(const double v) const
     { return Valid(v)?IntegerToString((int)MathRound(v*100))+"%":"-"; }
   string SignalTime(const long time) const
     {
      MqlDateTime d;
      if(!TimeToStruct((datetime)(time/1000),d) || d.mon<1 || d.mon>12) return "-";
      string months[12]={"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
      return StringFormat("%s %02d %02d:%02d",months[d.mon-1],d.day,d.hour,d.min);
     }
   string Duration(const FgfConfig &c,const FgfVisualConfig &v) const
     {
      if(c.windowMode==1) return IntegerToString(c.minutes)+" min";
      if(c.windowMode==2) return IntegerToString(c.bars)+(c.bars==1?" candle ":" candles ")+v.filterLabel;
      return "until next signal";
     }
   string Edge(const bool up,const FgfConfig &c,const FgfVisualConfig &v,
               const FgfFilterPoint &p,const FgfGate &g) const
     {
      double edge=up?g.upper:g.lower;
      if(!Valid(edge)) return "-";
      bool incl=FgfEQ(g.band,0.0) && g.onSigBar && (up?p.armedDir>0:p.armedDir<0);
      if(!FgfGT(g.band,0.0) && c.tickSize>0)
        {
         double k=edge/c.tickSize;
         edge=(up!=incl?MathFloor(k+1e-9):MathCeil(k-1e-9))*c.tickSize;
        }
      return (up?(incl?">= ":"> "):(incl?"<= ":"< "))+Price(edge,v.digits);
     }
   string Reference(const int seconds) const
     {
      int m=(int)MathRound(seconds/60.0);
      if(m>=1 && m<=2) return "1m: level 50/50  signal 50/49  reversed 50/51";
      if(m>=3 && m<=10) return "5m: level 51/51  signal 49/49  reversed 51/51";
      if(m>=11 && m<=22) return "15m: level 51/51  signal 48/48  reversed 52/52";
      if(m>=23 && m<=45) return "30m: level 51/52  signal 49/48  reversed 51/52";
      if(m>=46 && m<=90) return "1H: level 50/49  signal 48/50  reversed 52/50";
      if(m>=91 && m<=180) return "2H: level 49/52  signal 49/48  reversed 51/52";
      if(m>=181 && m<=360) return "4H: level 49/53  signal 49/48  reversed 51/52";
      if(m>=361 && m<=720) return "8H: level 51/48  signal 48/51  reversed 52/49";
      if(m>=1080 && m<=2880) return "1D: level 49/57  signal 53/43  reversed 47/57";
      return "-";
     }
   bool HLine(int x1,int x2,const double price,const uint ink,const bool dashed,const int width)
     {
      // Discard horizontally invisible retained lines before a native call.
      if(x2<0 || x1>=m_width || x2<x1) return true;
      x1=MathMax(0,x1); x2=MathMin(m_width-1,x2);
      int y=0;
      if(!Y(price,y)) return false;
      if(y<0 || y>=m_height) return true;
      for(int w=0;w<width;w++)
        {
         if(!dashed) m_fg.LineHorizontal(x1,x2,y+w,ink);
         else for(int x=x1;x<=x2;x+=9) m_fg.LineHorizontal(x,MathMin(x+4,x2),y+w,ink);
        }
      return true;
     }
   // anchor 0: label ends left of price point; 1: lower-left; 2: upper-left;
   // 3: left-center. Match Pine label orientations without expanding the price scale.
   bool Label(const int px,const double price,const string text,const uint fill,const uint fg,const int anchor)
     {
      string lines[];
      int count=StringSplit(text,'\n',lines),w=0;
      if(count<=0) return true;
      int lineHeight=m_fg.TextHeight("Mg")+2;
      for(int i=0;i<count;i++) w=MathMax(w,m_fg.TextWidth(lines[i]));
      w+=10; int h=count*lineHeight+6;
      int x=px+5;
      if(anchor==0) x=px-w-5;
      if(x+w<0 || x>=m_width) return true;
      int py=0;
      if(!Y(price,py)) return false;
      int y=py-h/2;
      if(anchor==1) y=py-h-5;
      if(anchor==2) y=py+5;
      if(y+h<0 || y>=m_height) return true;
      m_fg.FillRectangle(x,y,x+w,y+h,fill);
      // Adjacent pieces of one label must not double-blend their shared edge.
      if(anchor==0) m_fg.FillTriangle(px,py,x+w+1,py-4,x+w+1,py+4,fill);
      else if(anchor==1) m_fg.FillTriangle(px,py,x,py-4,x+7,py-4,fill);
      else if(anchor==2) m_fg.FillTriangle(px,py,x,py+4,x+7,py+4,fill);
      else m_fg.FillTriangle(px,py,x-1,py-4,x-1,py+4,fill);
      for(int i=0;i<count;i++) m_fg.TextOut(x+5,y+3+i*lineHeight,lines[i],fg);
      return true;
     }
   bool Surfaces()
     {
      int w=(int)ChartGetInteger(m_chartId,CHART_WIDTH_IN_PIXELS,0);
      int h=(int)ChartGetInteger(m_chartId,CHART_HEIGHT_IN_PIXELS,0);
      if(w<=0 || h<=0) { m_error="Chart dimensions are unavailable"; return false; }
      if(!m_ready)
        {
         m_prefix=m_basePrefix;
         int suffix=0;
         while(ObjectFind(m_chartId,m_prefix+"background")>=0 || ObjectFind(m_chartId,m_prefix+"foreground")>=0)
           {
            if(++suffix>99999) { m_error="No free canvas object names"; return false; }
            m_prefix=m_basePrefix+"_"+IntegerToString(suffix)+"_";
           }
         if(!m_bg.CreateSurface(m_chartId,m_prefix+"background",w,h) ||
            !m_fg.CreateSurface(m_chartId,m_prefix+"foreground",w,h))
           { m_error="Could not create chart canvas: "+IntegerToString(GetLastError()); Destroy(); return false; }
         ObjectSetInteger(m_chartId,m_bg.ChartObjectName(),OBJPROP_BACK,true);
         ObjectSetInteger(m_chartId,m_fg.ChartObjectName(),OBJPROP_BACK,false);
         ObjectSetInteger(m_chartId,m_bg.ChartObjectName(),OBJPROP_SELECTABLE,false);
         ObjectSetInteger(m_chartId,m_fg.ChartObjectName(),OBJPROP_SELECTABLE,false);
         ObjectSetInteger(m_chartId,m_bg.ChartObjectName(),OBJPROP_SELECTED,false);
         ObjectSetInteger(m_chartId,m_fg.ChartObjectName(),OBJPROP_SELECTED,false);
         ObjectSetInteger(m_chartId,m_bg.ChartObjectName(),OBJPROP_HIDDEN,true);
         ObjectSetInteger(m_chartId,m_fg.ChartObjectName(),OBJPROP_HIDDEN,true);
         ObjectSetString(m_chartId,m_bg.ChartObjectName(),OBJPROP_TOOLTIP,"\n");
         ObjectSetString(m_chartId,m_fg.ChartObjectName(),OBJPROP_TOOLTIP,"\n");
         m_ready=true;
        }
      else if(!m_bg.OwnsObject() || !m_fg.OwnsObject())
        { m_error="A canvas object was removed or rebound"; Destroy(); return false; }
      else if(w!=m_width || h!=m_height)
        {
         if(!m_bg.Resize(w,h) || !m_fg.Resize(w,h))
           { m_error="Could not resize chart canvas"; Destroy(); return false; }
        }
      m_width=w; m_height=h;
      m_bg.Erase(0); m_fg.Erase(0);
      // CCanvas negative font sizes are tenths of a typographic point.
      if(!m_fg.FontSet("Arial",-90))
        { m_error="Could not initialize chart font"; return false; }
      return true;
     }
   long LabelCutoff(const FgfVisualSegment &segs[],const long through,const long prior,const int capacity) const
     {
      int count=0;
      for(int i=0;i<ArraySize(segs);i++) if(segs[i].born>prior && segs[i].born<=through) count++;
      int discard=count-capacity;
      long cutoff=prior;
      for(int i=0;i<ArraySize(segs) && discard>0;i++)
         if(segs[i].born>prior && segs[i].born<=through) { cutoff=segs[i].born; discard--; }
      return cutoff;
     }
   int ZoneCount(const FgfConfig &c,const FgfVisualConfig &v,const FgfBar &bar,
                 const FgfFilterPoint &p,const FgfGate &g,const bool finalized) const
     {
      if(!v.showLv || !c.enabled || !g.open || !Valid(p.armedPrice)) return 0;
      // MT5 has no Pine closing-execution timenow evidence. Nominal bar end is
      // the available close clock; delayed-close/session-gap GC parity remains
      // subject to the wrapper's explicitly provisional newest-bar limitation.
      bool open=finalized ? !(c.checkMode==0 && c.windowMode==1 && bar.end>=g.endMs) : g.displayOpen;
      return open ? (FgfGT(g.band,0.0)?3:2) : 0;
     }
   long SessionLabelCutoff(const FgfVisualSegment &segs[],const FgfConfig &c,const FgfVisualConfig &v,
                           const FgfBar &chart[],const FgfFilterPoint &picked[],const FgfGate &gates[])
     {
      long current=chart[m_n-1].time;
      if(m_lastBarTime>current) ResetHistory();
      if(m_lastBarTime!=current)
        {
         if(m_lastBarTime>=0)
           {
            int previous=-1;
            for(int i=m_n-2;i>=0;i--) if(chart[i].time==m_lastBarTime) { previous=i; break; }
            if(previous>=0)
              {
               // Resolve the previous provisional bar from its finalized gate,
               // not from the last observed tick. Its old zone labels still
               // exist when a new historical signal label is first created.
               int zones=ZoneCount(c,v,chart[previous],picked[previous],gates[previous],true);
               m_labelCutoff=LabelCutoff(segs,m_lastBarTime,m_labelCutoff,500-MathMax(m_committedZones,zones));
               m_committedZones=zones;
              }
            else ResetHistory();
           }
         // On a fresh load, historical executions have no barstate.islast zone
         // labels. On catch-up, preserve the last committed zone objects until
         // the new last-bar execution deletes them in source order.
         m_labelCutoff=LabelCutoff(segs,current-1,m_labelCutoff,500-m_committedZones);
         m_lastBarTime=current;
        }
      int zones=ZoneCount(c,v,chart[m_n-1],picked[m_n-1],gates[m_n-1],false);
      // This cutoff is provisional. Same-bar timer/redraw/tick calls always
      // restart from committed state, matching Pine's drawing rollback.
      return LabelCutoff(segs,current,m_labelCutoff,500-MathMax(m_committedZones,zones));
     }
   bool Segments(const FgfConfig &c,const FgfVisualConfig &v,const FgfBar &chart[],
                 const FgfFilterPoint &picked[],const FgfGate &gates[])
     {
      if(!v.showLv || !c.enabled) return true;
      FgfVisualSegment segs[];
      int count=0,from=-1,current=-1;
      for(int i=0;i<m_n;i++)
        {
         if(gates[i].newSignal || (from<0 && gates[i].armed)) { from=i; current=-1; }
         if(from<0 || !gates[i].open || !Valid(picked[i].armedPrice)) continue;
         if(current<0)
           {
            current=count++;
            if(ArrayResize(segs,count,128)!=count)
              { m_error="Insufficient memory for historical level drawings"; return false; }
            segs[current].labelFrom=MathMax(from,i-9000);
            segs[current].born=chart[i].time;
            segs[current].drawn=true;
           }
         segs[current].from=MathMax(from,i-9000); segs[current].to=i;
         segs[current].dir=picked[i].armedDir; segs[current].level=picked[i].armedPrice;
         segs[current].upper=gates[i].upper; segs[current].lower=gates[i].lower;
         segs[current].band=FgfGT(gates[i].band,0.0);
        }
      // TradingView has independent 500-line and 500-label budgets. Current
      // zone labels count in the latter; signal plotshapes consume neither.
      long labelCutoff=SessionLabelCutoff(segs,c,v,chart,picked,gates);
      int totalLines=0;
      for(int j=0;j<count;j++) totalLines+=segs[j].band?3:1;
      int skip=MathMax(0,totalLines-500),lineIndex=0;
      for(int j=0;j<count;j++)
        {
         FgfVisualSegment s=segs[j];
         int x1=X(s.from),x2=X(s.to);
         uint col=s.dir>0?FGF_RGB_LIME:FGF_RGB_RED;
         if(lineIndex++>=skip && !HLine(x1,x2,s.level,Ink(col),false,2)) return false;
         if(s.band)
           {
            if(lineIndex++>=skip && !HLine(x1,x2,s.upper,Ink(FGF_RGB_LIME,40),true,1)) return false;
            if(lineIndex++>=skip && !HLine(x1,x2,s.lower,Ink(FGF_RGB_RED,40),true,1)) return false;
           }
        }
      // Pine gives every label a higher z-index than every line.
      for(int j=0;j<count;j++)
        {
         FgfVisualSegment s=segs[j];
         uint col=s.dir>0?FGF_RGB_LIME:FGF_RGB_RED;
         if(s.born>labelCutoff &&
            !Label(X(s.labelFrom),s.level,(s.dir>0?"BUY":"SELL")+" signal "+v.filterLabel+" @ "+Price(s.level,v.digits)+"\n"+Duration(c,v),
                  Ink(col,20),Ink(FGF_RGB_BLACK),0)) return false;
        }
      return true;
     }
   bool ZoneLabels(const FgfConfig &c,const FgfVisualConfig &v,const FgfFilterPoint &p,const FgfGate &g)
     {
      if(!v.showLv || !c.enabled || !g.displayOpen || !Valid(p.armedPrice)) return true;
      bool up=c.allowBuy && (c.against || p.armedDir>0);
      bool dn=c.allowSell && (c.against || p.armedDir<0);
      int x=X(m_n+2);
      if(!Label(x,g.upper,(up?"BUY ZONE ":"NO TRADE ")+Edge(true,c,v,p,g),Ink(up?FGF_RGB_LIME:FGF_RGB_GRAY,30),Ink(FGF_RGB_BLACK),1) ||
         !Label(x,g.lower,(dn?"SELL ZONE ":"NO TRADE ")+Edge(false,c,v,p,g),Ink(dn?FGF_RGB_RED:FGF_RGB_GRAY,30),Ink(FGF_RGB_WHITE),2)) return false;
      if(FgfGT(g.band,0.0) && !Label(x,p.armedPrice,"NO TRADE (band)",Ink(FGF_RGB_GRAY,30),Ink(FGF_RGB_WHITE),3)) return false;
      return true;
     }
   void Table(const FgfConfig &c,const FgfVisualConfig &v,const FgfFilterPoint &p,const FgfGate &g)
     {
      if(!v.showTbl || !c.enabled) return;
      string left[14],right[14]; uint lc[14],rc[14];
      for(int j=0;j<14;j++) { lc[j]=Ink(FGF_RGB_WHITE); rc[j]=Ink(FGF_RGB_WHITE); }
      bool dBuy=g.displayOpen && g.buyOK,dSell=g.displayOpen && g.sellOK;
      bool inUp=false,inDn=false;
      if(Valid(g.value) && Valid(p.armedPrice))
        {
         inUp=FgfGT(g.band,0.0)?FgfGT(g.value,g.upper+c.tickSize/2.0):
              (FgfGT(g.value,p.armedPrice) || (g.onSigBar && p.armedDir>0 && FgfGE(g.value,p.armedPrice)));
         inDn=FgfGT(g.band,0.0)?FgfLT(g.value,g.lower-c.tickSize/2.0):
              (FgfLT(g.value,p.armedPrice) || (g.onSigBar && p.armedDir<0 && FgfLE(g.value,p.armedPrice)));
        }
      string why=!g.armed?"waiting for a signal":!g.displayOpen?"permission ended":
                 !(inUp||inDn)?"price at the level (band)":
                 inUp && !c.against && p.armedDir<0?"above a SELL signal (against it)":
                 inDn && !c.against && p.armedDir>0?"below a BUY signal (against it)":"that side is switched off";
      left[0]="FG filter "+v.filterLabel;
      right[0]=dBuy?"BUY ZONE - buys allowed, no sells":dSell?"SELL ZONE - sells allowed, no buys":"NO TRADE - "+why;
      rc[0]=Ink(dBuy?FGF_RGB_LIME:dSell?FGF_RGB_RED:FGF_RGB_ORANGE);
      left[1]="Signal (server time)";
      right[1]=p.armedAt<0?"-":(p.armedDir>0?"BUY ":"SELL ")+SignalTime(p.armedAt)+" @ "+Price(p.armedPrice,v.digits);
      rc[1]=Ink(p.armedDir>0?FGF_RGB_LIME:p.armedDir<0?FGF_RGB_RED:FGF_RGB_WHITE);
      bool confirmed=g.displayOpen && g.sigOk,sideOn=p.armedDir>0?c.allowBuy:c.allowSell;
      string side=p.armedDir>0?"buy":"sell";
      left[2]="Signal direction";
      right[2]=!g.armed?"-":!g.displayOpen?"- (permission ended)":confirmed?
               (sideOn?"CONFIRMED - "+side+"s allowed":"CONFIRMED - but "+side+"s are switched off"):
               "NOT CONFIRMED - do not "+side;
      rc[2]=Ink(!g.armed?FGF_RGB_WHITE:confirmed && sideOn?(p.armedDir>0?FGF_RGB_LIME:FGF_RGB_RED):FGF_RGB_ORANGE);
      bool up=g.displayOpen && c.allowBuy && (c.against || p.armedDir>0);
      bool dn=g.displayOpen && c.allowSell && (c.against || p.armedDir<0);
      string off=!g.armed?"NO TRADE (no signal yet)":!g.displayOpen?"NO TRADE (permission ended)":"NO TRADE there";
      left[3]="BUY ZONE  "+Edge(true,c,v,p,g); right[3]=dBuy?"ALLOWED (now)":up?"allowed there":off;
      left[4]="SELL ZONE "+Edge(false,c,v,p,g); right[4]=dSell?"ALLOWED (now)":dn?"allowed there":off;
      rc[3]=Ink(dBuy?FGF_RGB_LIME:up?FGF_RGB_GRAY:FGF_RGB_ORANGE);
      rc[4]=Ink(dSell?FGF_RGB_RED:dn?FGF_RGB_GRAY:FGF_RGB_ORANGE);
      left[5]="NO TRADE band";
      right[5]=!Valid(p.armedPrice)?"-":FgfGT(g.band,0.0)?Price(g.lower,v.digits)+" - "+Price(g.upper,v.digits):
               FgfGT(c.bandAtr,0.0) && g.armed && !Valid(p.armedAtr)?"off (no ATR yet at the signal)":"off";
      left[6]=c.checkMode==1?"Candle open":c.checkMode==2?"Last close":"Price now";
      right[6]=Price(g.value,v.digits); left[7]="Left"; right[7]="-";
      if(g.displayOpen)
        {
         if(c.windowMode==1)
           {
            long now=c.checkMode==0 && v.nowMs>0?v.nowMs:g.clock;
            int secs=(int)MathMax(0,MathFloor((g.endMs-now)/1000.0));
            right[7]=StringFormat("%02d:%02d",secs/60,secs%60);
           }
         else if(c.windowMode==2)
           {
            int bars=p.armedBar+c.bars-g.index;
            right[7]=IntegerToString(bars)+(bars==1?" candle ":" candles ")+v.filterLabel;
           }
         else right[7]="until next signal";
        }
      left[8]="Last "+v.filterLabel+" parent / zones";
      string parent=p.parent==1?"BUY":p.parent==-1?"SELL":p.parent==0?"FLAT":"-";
      right[8]=parent+" / "+(p.active<0?"-":IntegerToString(p.aligned)+"/"+IntegerToString(p.active))+" aligned";
      rc[8]=Ink(p.parent==1?FGF_RGB_LIME:p.parent==-1?FGF_RGB_RED:FGF_RGB_WHITE);
      int rows=v.showScore?14:9;
      if(v.showScore)
        {
         string window=c.scoreWindow>0?"last "+IntegerToString(c.scoreWindow):"all";
         left[9]="Direction score ("+window+", "+(Valid(p.scores[6])?DoubleToString(p.scores[6],0):"-")+" level-side calls)";
         right[9]="next 1 / "+IntegerToString(c.scoreHorizon)+" "+v.filterLabel+"  (50% = coin flip)";
         left[10]="Level side (bare level)"; right[10]=Pct(p.scores[0])+" / "+Pct(p.scores[1]);
         left[11]="Signal direction"; right[11]=Pct(p.scores[2])+" / "+Pct(p.scores[3]);
         left[12]="Signal reversed"; right[12]=Pct(p.scores[4])+" / "+Pct(p.scores[5]);
         left[13]="BTC 2025-26 reference (1/10), parent=TF, zones x1/2/4";
         right[13]=Reference(v.filterSeconds>0?v.filterSeconds:(int)((p.end-p.time)/1000));
         for(int j=9;j<14;j++) { lc[j]=Ink(FGF_RGB_GRAY); rc[j]=Ink(FGF_RGB_GRAY); }
         lc[10]=Ink(FGF_RGB_AQUA); rc[10]=Ink(FGF_RGB_AQUA);
        }
      int w1=0,w2=0;
      for(int j=0;j<rows;j++) { w1=MathMax(w1,m_fg.TextWidth(left[j])); w2=MathMax(w2,m_fg.TextWidth(right[j])); }
      w1+=16; w2+=16; int rowHeight=m_fg.TextHeight("Mg")+10,h=rows*rowHeight;
      // The bitmap canvas spans the chart width, including its price-axis
      // region, but native bitmap labels are clipped at the plot boundary.
      // Reserve the actual formatted price text width plus axis padding so
      // the status text and its right border remain inside the visible pane.
      int priceAxis=MathMax(m_fg.TextWidth(DoubleToString(m_min,v.digits)),
                            m_fg.TextWidth(DoubleToString(m_max,v.digits)))+24;
      int plotWidth=MathMax(1,m_width-priceAxis);
      int x=plotWidth-w1-w2-8,y=8;
      if(v.tablePos==3 || v.tablePos==4 || v.tablePos==5) x=8;
      if(v.tablePos==6 || v.tablePos==7) x=(plotWidth-w1-w2)/2;
      if(v.tablePos==1 || v.tablePos==4) y=(m_height-h)/2;
      if(v.tablePos==2 || v.tablePos==5 || v.tablePos==7) y=m_height-h-8;
      x=MathMax(0,x); y=MathMax(0,y);
      m_fg.FillRectangle(x,y,x+w1+w2,y+h,Ink(FGF_RGB_BLACK,20));
      m_fg.Rectangle(x,y,x+w1+w2,y+h,Ink(FGF_RGB_GRAY,45));
      m_fg.LineVertical(x+w1,y,y+h,Ink(FGF_RGB_GRAY,45));
      for(int j=0;j<rows;j++)
        {
         if(j>0) m_fg.LineHorizontal(x,x+w1+w2,y+j*rowHeight,Ink(FGF_RGB_GRAY,45));
         m_fg.TextOut(x+8,y+j*rowHeight+5,left[j],lc[j]);
         m_fg.TextOut(x+w1+8,y+j*rowHeight+5,right[j],rc[j]);
        }
     }
public:
                     CFgfRenderer(void) { m_prefix=""; m_ready=false; m_width=0; m_height=0; m_n=0; ResetHistory(); }
                    ~CFgfRenderer(void) { Destroy(); }
   bool Init(const string prefix,const long chartId=0)
     {
      Destroy(); m_chartId=chartId==0?ChartID():chartId; m_basePrefix=StringSubstr(prefix,0,44); m_prefix=m_basePrefix; m_error="";
      if(StringLen(m_prefix)==0) { m_error="An instance-specific object prefix is required"; return false; }
      return true;
     }
   void Destroy(void)
     {
      m_bg.Destroy(); m_fg.Destroy(); m_ready=false; m_width=0; m_height=0; ResetHistory();
     }
   void ResetHistory(void) { m_labelCutoff=-1; m_lastBarTime=-1; m_committedZones=0; }
   string ForegroundObjectName(void) const { return m_fg.ChartObjectName(); }
   string BackgroundObjectName(void) const { return m_bg.ChartObjectName(); }
   string Error(void) const { return m_error; }
   bool Render(const FgfConfig &c,const FgfVisualConfig &v,const FgfBar &chart[],
               const FgfFilterPoint &picked[],const FgfGate &gates[])
     {
      m_error=""; m_n=ArraySize(chart); m_tickSize=c.tickSize;
      if(m_n<1 || ArraySize(picked)!=m_n || ArraySize(gates)!=m_n)
        { m_error="Renderer inputs must be equally sized chronological arrays"; return false; }
      if(!Surfaces()) return false;
      m_min=ChartGetDouble(m_chartId,CHART_PRICE_MIN,0); m_max=ChartGetDouble(m_chartId,CHART_PRICE_MAX,0);
      if(!Valid(m_min) || !Valid(m_max) || m_max<=m_min)
        { m_error="Chart price range is unavailable"; return false; }
      double mid=(m_min+m_max)*0.5; int lastY=0;
      if(!ChartTimePriceToXY(m_chartId,0,(datetime)(chart[m_n-1].time/1000),mid,m_lastX,lastY))
        { m_error="Chart time mapping is unavailable"; return false; }
      // Native chart properties can briefly report the old range while the
      // transform already uses a newly requested scale. Defer this paint until
      // they agree instead of publishing an overlay at impossible coordinates.
      if(lastY<0 || lastY>=m_height)
        { m_error="Chart price geometry has not settled"; return false; }
      // CHART_HEIGHT_IN_PIXELS includes space that is not the native price
      // coordinate interval. Validate the native mapping, then use its direct
      // price conversion rather than interpolating rounded endpoint pixels.
      int anchorX=0,minY=0,maxY=0;
      datetime anchorTime=(datetime)(chart[m_n-1].time/1000);
      if(!ChartTimePriceToXY(m_chartId,0,anchorTime,m_min,anchorX,minY) ||
         !ChartTimePriceToXY(m_chartId,0,anchorTime,m_max,anchorX,maxY) || minY<=maxY)
        { m_error="Chart price mapping is unavailable"; return false; }
      m_mapTime=anchorTime;
      int offset=MathMin(12,m_n-1),beforeX=0,beforeY=0;
      if(offset>0 && ChartTimePriceToXY(m_chartId,0,(datetime)(chart[m_n-1-offset].time/1000),mid,beforeX,beforeY))
         m_spacing=(m_lastX-beforeX)/(double)offset;
      else m_spacing=8;
      if(m_spacing<=0) { m_error="Chart bar spacing is unavailable"; return false; }
      int first=MathMax(0,(int)MathFloor(m_n-1-m_lastX/m_spacing)-2);
      int last=MathMin(m_n-1,(int)MathCeil(m_n-1+(m_width-m_lastX)/m_spacing)+2);
      for(int i=first;i<=last;i++)
        {
         int x=X(i);
         if(v.showBg && c.enabled && gates[i].open)
           {
            uint col=gates[i].buyOK?FGF_RGB_GREEN:gates[i].sellOK?FGF_RGB_RED:FGF_RGB_GRAY;
            int x1=MathMax(0,(int)MathRound(x-m_spacing/2.0));
            int x2=MathMin(m_width-1,(int)MathRound(x+m_spacing/2.0)-1);
            if(x1<=x2) m_bg.FillRectangle(x1,0,x2,m_height-1,Ink(col,(gates[i].buyOK||gates[i].sellOK)?85:88));
           }
         if(v.sigMark && c.enabled && gates[i].newSignal)
           {
            if(picked[i].armedDir>0)
              { int y=0; if(!Y(chart[i].low,y)) return false; y+=7; m_fg.FillTriangle(x,y,x-4,y+7,x+4,y+7,Ink(FGF_RGB_LIME)); }
            else if(picked[i].armedDir<0)
              { int y=0; if(!Y(chart[i].high,y)) return false; y-=7; m_fg.FillTriangle(x,y,x-4,y-7,x+4,y-7,Ink(FGF_RGB_RED)); }
           }
         if(gates[i].expired)
           {
            m_fg.Line(x-3,8,x+3,14,Ink(FGF_RGB_ORANGE)); m_fg.Line(x-3,14,x+3,8,Ink(FGF_RGB_ORANGE));
            m_fg.TextOut(x-m_fg.TextWidth("FGF end")/2,17,"FGF end",Ink(FGF_RGB_ORANGE));
           }
        }
      long priorCutoff=m_labelCutoff,priorBar=m_lastBarTime;
      int priorZones=m_committedZones;
      if(!Segments(c,v,chart,picked,gates) || !ZoneLabels(c,v,picked[m_n-1],gates[m_n-1]))
        {
         // Failed conversion is not an off-screen drawing. Keep the published
         // resources and committed label state until a complete retry succeeds.
         m_labelCutoff=priorCutoff; m_lastBarTime=priorBar; m_committedZones=priorZones;
         return false;
        }
      Table(c,v,picked[m_n-1],gates[m_n-1]);
      m_bg.Update(false); m_fg.Update(false); ChartRedraw(m_chartId);
      return true;
     }
  };
#endif
