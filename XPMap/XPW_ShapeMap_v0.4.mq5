//+------------------------------------------------------------------+
//|                                            XPW_ShapeMap_v0.4.mq5 |
//|  Port of the TradingView Pine script "XPW Shape Map v0.4"         |
//|  (map layer only: no entries, no signals, no alerts).             |
//|                                                                   |
//|  Zero-logic-loss port rules (see XPW_SHAPEMAP_PORT_REPORT.md):    |
//|   - ta.rsi / ta.sma / ta.atr / ta.lowest / ta.highest are         |
//|     reimplemented in buffers (no iRSI/iATR/iMA handles).          |
//|   - Pine na semantics via explicit valid flags per series.        |
//|   - Confirmed bars only, each processed exactly once, tracked by   |
//|     bar time. Full replay when prev_calculated == 0. No repaint.  |
//|                                                                   |
//|  CONSUMPTION (iCustom) - buffer index map, all stamped at the     |
//|  confirmation bar (the bar where the Pine `if` evaluated true):   |
//|    0 RSI      1 FAST     2 SLOW                                   |
//|    3,4 fill red (fast,slow)   5,6 fill lime (fast,slow)  [visual] |
//|    7 BOT_HIT  (=prevLen, 0 otherwise)                             |
//|    8 BOT_SEP  9 BOT_TOP  10 BOT_BOT      (EMPTY_VALUE otherwise)  |
//|   11 TOP_HIT  (=prevLen, 0 otherwise)                             |
//|   12 TOP_SEP 13 TOP_TOP  14 TOP_BOT      (EMPTY_VALUE otherwise)  |
//|   15 UP_TICK (=upW/atrv, 0 otherwise)  16 DN_TICK (=dnW/atrv)     |
//|   17 EFF1  18 EFF2  19 VEL1  20 VEL2    (EMPTY_VALUE when na)     |
//|   21 MBARS 22 STATE (isRedNow 1/0)  23 RUNLEN  24 ATR             |
//|  Bars not yet processed (forming bar, skipped empty bars) hold    |
//|  EMPTY_VALUE in every buffer.                                     |
//|                                                                   |
//|  NOTE FOR ANY EA READING THESE BUFFERS: an EA on a custom chart   |
//|  (XAUUSD-ECNc_S1) must trade the PARENT symbol (XAUUSD-ECNc).     |
//|  Custom symbols do not trade.                                     |
//+------------------------------------------------------------------+
#property copyright   "xpworx"
#property link        "ghostmaster"
#property description "XPW Shape Map v0.4 - Pine port. Map layer only: bottom/top squares, wick ticks, continuity readout."
#define  XPW_VERSION  "0.4"
#property version     "0.40"

#property indicator_separate_window
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_buffers 25
#property indicator_plots   5

//--- plot 1: RSI
#property indicator_label1  "RSI"
#property indicator_type1   DRAW_LINE
#property indicator_color1  C'120,123,134'
#property indicator_style1  STYLE_SOLID
#property indicator_width1  1
//--- plot 2: Fast
#property indicator_label2  "Fast"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrWhite
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1
//--- plot 3: Slow
#property indicator_label3  "Slow"
#property indicator_type3   DRAW_LINE
#property indicator_color3  C'0,188,212'
#property indicator_style3  STYLE_SOLID
#property indicator_width3  1
//--- plot 4: fill (bars where isRedNow) - both colours RED, so the
//    DRAW_FILLING "first > second" colour order is irrelevant
#property indicator_label4  "Fill RED"
#property indicator_type4   DRAW_FILLING
#property indicator_color4  C'255,59,48',C'255,59,48'
//--- plot 5: fill (bars where not isRedNow) - both colours LIME
#property indicator_label5  "Fill LIME"
#property indicator_type5   DRAW_FILLING
#property indicator_color5  C'50,215,75',C'50,215,75'

//+------------------------------------------------------------------+
//| Inputs - the 27 Pine inputs, same names, defaults, order, groups  |
//| (minval/maxval are clamped in OnInit with one warning each).      |
//+------------------------------------------------------------------+
input group "TDI"
input int    rsiLen     = 14;      // RSI length (min 2)
input int    fastLen    = 2;       // Fast MA (your RED line) (min 1)
input int    slowLen    = 7;       // Slow MA (your LIME line) (min 1)
input bool   invertFill = true;    // Panel colours inverted (fast>slow renders RED)
input int    extLook    = 20;      // Lookback for LOW/MID/HIGH area (min 5)
input double loFrac     = 0.33;    // LOW area below this fraction (0.05..0.5)
input double hiFrac     = 0.67;    // HIGH area above this fraction (0.5..0.95)

input group "P1a - BOTTOM square (odd RED at a low)"
input bool   sqBotOn    = true;    // Draw bottom squares
input int    sqBotMin   = 1;       // Min width (bars) (min 1)
input int    sqBotMax   = 3;       // Max width (bars) (min 1)
input int    sqBotCtx   = 2;       // Context bars each side (min 1)
input double sqBotSep   = 0.0;     // Min separation (0 = off) (min 0)
input bool   sqBotArea  = true;    // Require LOW area

input group "P1b - TOP square (odd LIME at a high)"
input bool   sqTopOn    = true;    // Draw top squares
input int    sqTopMin   = 1;       // Min width (bars) (min 1)
input int    sqTopMax   = 2;       // Max width (bars) (min 1)
input int    sqTopCtx   = 3;       // Context bars each side (min 1)
input double sqTopSep   = 0.0;     // Min separation (0 = off) (min 0)
input bool   sqTopArea  = true;    // Require HIGH area

input group "P2 - tick as compressed cycle"
input bool   tickOn     = true;    // Mark ticks
input int    atrLen     = 14;      // ATR length (min 1)
input double dnWickFrac = 0.55;    // BOTTOM tick: min wick / range (0.1..1.0)
input double dnWickAtr  = 0.8;     // BOTTOM tick: min wick / ATR (min 0)
input double upWickFrac = 0.70;    // TOP tick: min wick / range (0.1..1.0)
input double upWickAtr  = 1.2;     // TOP tick: min wick / ATR (min 0)
input bool   tickPrice  = true;    // Put tick marks on the price chart

input group "P3 - continuity"
input bool   showTbl    = true;    // Show readout table

//--- port-only inputs (R3, R4, Gate C) - not Pine inputs
input group "Port (MQL5 only)"
input bool   LastBarIsClosed = false;  // rates_total-1 is a CLOSED bar (false: forming, evaluate rates_total-2)
input bool   SkipEmptyBars   = false;  // Skip bars with tick_volume==0 (engine WriteEmptyBars=true marker)
input bool   DumpCSV         = false;  // Write MQL5\Files\XPChart\mapdump_<symbol>.csv (Gate C)

//--- NA7 assumption: math.max/math.min with an na argument returns na.
//    Comment the define out if Gate B shows TradingView returns the other argument.
#define XPW_NA_MAX_PROPAGATES

//--- TradingView drawing caps (max_boxes_count / max_labels_count)
#define XPW_MAX_BOXES  500
#define XPW_MAX_LABELS 500
const string XPW_DUMP_DIR = "XPChart";

//+------------------------------------------------------------------+
//| Colours exactly as the Pine constants                             |
//+------------------------------------------------------------------+
const color XPW_RED    = C'255,59,48';    // #ff3b30
const color XPW_LIME   = C'50,215,75';    // #32d74b
const color XPW_GRAY   = C'120,123,134';  // color.gray   #787B86
const color XPW_WHITE  = clrWhite;        // color.white  #FFFFFF
const color XPW_AQUA   = C'0,188,212';    // color.aqua   #00BCD4
const color XPW_ORANGE = C'255,152,0';    // color.orange #FF9800
const color XPW_YELLOW = C'255,235,59';   // color.yellow #FFEB3B

//+------------------------------------------------------------------+
//| Indicator buffers                                                 |
//+------------------------------------------------------------------+
double BufRSI[], BufFast[], BufSlow[];
double BufFillRedA[], BufFillRedB[], BufFillLimeA[], BufFillLimeB[];
double BufBotHit[], BufBotSep[], BufBotTop[], BufBotBot[];
double BufTopHit[], BufTopSep[], BufTopTop[], BufTopBot[];
double BufUpTick[], BufDnTick[];
double BufEff1[], BufEff2[], BufVel1[], BufVel2[];
double BufMBars[], BufState[], BufRunLen[], BufATR[];

//+------------------------------------------------------------------+
//| Clamped copies of the inputs (R6)                                 |
//+------------------------------------------------------------------+
int    g_rsiLen, g_fastLen, g_slowLen, g_extLook;
double g_loFrac, g_hiFrac;
int    g_sqBotMin, g_sqBotMax, g_sqBotCtx;
double g_sqBotSep;
int    g_sqTopMin, g_sqTopMax, g_sqTopCtx;
double g_sqTopSep;
int    g_atrLen;
double g_dnWickFrac, g_dnWickAtr, g_upWickFrac, g_upWickAtr;

//+------------------------------------------------------------------+
//| ta.* reimplementations with explicit valid flags (R1, R2)         |
//+------------------------------------------------------------------+
// ta.sma(src, len): na while the window holds na (NA4)
class CXpSma
{
private:
   int    m_len;
   double m_val[];
   bool   m_ok[];
   int    m_count;   // values seen (capped at m_len)
   int    m_pos;     // next write position
public:
   void Init(int len)
   {
      m_len = (len < 1) ? 1 : len;
      ArrayResize(m_val, m_len);
      ArrayResize(m_ok, m_len);
      Reset();
   }
   void Reset()
   {
      ArrayInitialize(m_val, 0.0);
      ArrayInitialize(m_ok, false);
      m_count = 0;
      m_pos   = 0;
   }
   bool Update(double x, bool xValid, double &out)
   {
      m_val[m_pos] = x;
      m_ok[m_pos]  = xValid;
      m_pos = (m_pos + 1) % m_len;
      if(m_count < m_len) m_count++;
      out = 0.0;
      if(m_count < m_len) return false;
      double s = 0.0;
      for(int k = 0; k < m_len; k++)
      {
         if(!m_ok[k]) return false;
         s += m_val[k];
      }
      out = s / (double)m_len;
      return true;
   }
};
// ta.rma(src, len): sum := na(sum[1]) ? ta.sma(src, len) : (src + (len-1)*sum[1]) / len
class CXpRma
{
private:
   int    m_len;
   CXpSma m_seed;
   double m_value;
   bool   m_valid;
public:
   void Init(int len)
   {
      m_len = (len < 1) ? 1 : len;
      m_seed.Init(m_len);
      Reset();
   }
   void Reset()
   {
      m_seed.Reset();
      m_value = 0.0;
      m_valid = false;
   }
   bool Update(double x, bool xValid, double &out)
   {
      if(!m_valid)
      {
         double s = 0.0;
         if(m_seed.Update(x, xValid, s)) { m_value = s; m_valid = true; }
      }
      else
      {
         if(xValid) m_value = (x + (double)(m_len - 1) * m_value) / (double)m_len;
         else       m_valid = false;   // NA2: na source makes the RMA na again (never happens after bar 0 here)
      }
      out = m_value;
      return m_valid;
   }
};
// ta.rsi(src, len) per the Pine reference implementation (NA3 + down==0 / up==0 edge cases)
class CXpRsi
{
private:
   CXpRma m_up;
   CXpRma m_dn;
   double m_prev;
   bool   m_prevValid;
public:
   void Init(int len) { m_up.Init(len); m_dn.Init(len); Reset(); }
   void Reset()       { m_up.Reset(); m_dn.Reset(); m_prev = 0.0; m_prevValid = false; }
   bool Update(double src, double &out)
   {
      bool   chgValid = m_prevValid;
      double chg      = chgValid ? (src - m_prev) : 0.0;
      m_prev      = src;
      m_prevValid = true;
      double u = chgValid ? MathMax(chg, 0.0)  : 0.0;
      double d = chgValid ? MathMax(-chg, 0.0) : 0.0;
      double au = 0.0, ad = 0.0;
      bool okU = m_up.Update(u, chgValid, au);
      bool okD = m_dn.Update(d, chgValid, ad);
      out = 0.0;
      if(!okU || !okD) return false;
      if(ad == 0.0)      { out = 100.0; return true; }
      if(au == 0.0)      { out = 0.0;   return true; }
      double rs = au / ad;
      out = 100.0 - 100.0 / (1.0 + rs);
      return true;
   }
};
// ta.atr(len) = ta.rma(ta.tr(true), len); TR on the first bar = high - low (NA6, NA11)
class CXpAtr
{
private:
   CXpRma m_rma;
   double m_prevClose;
   bool   m_prevValid;
public:
   void Init(int len) { m_rma.Init(len); Reset(); }
   void Reset()       { m_rma.Reset(); m_prevClose = 0.0; m_prevValid = false; }
   bool Update(double h, double l, double c, double &out)
   {
      double tr = h - l;
      if(m_prevValid)
         tr = MathMax(h - l, MathMax(MathAbs(h - m_prevClose), MathAbs(l - m_prevClose)));
      m_prevClose = c;
      m_prevValid = true;
      return m_rma.Update(tr, true, out);
   }
};
// ta.lowest / ta.highest over the last len values INCLUDING the current bar; na while the window holds na (NA5)
class CXpExtreme
{
private:
   int    m_len;
   double m_val[];
   bool   m_ok[];
   int    m_count;
   int    m_pos;
public:
   void Init(int len)
   {
      m_len = (len < 1) ? 1 : len;
      ArrayResize(m_val, m_len);
      ArrayResize(m_ok, m_len);
      Reset();
   }
   void Reset()
   {
      ArrayInitialize(m_val, 0.0);
      ArrayInitialize(m_ok, false);
      m_count = 0;
      m_pos   = 0;
   }
   bool Update(double x, bool xValid, double &lo, double &hi)
   {
      m_val[m_pos] = x;
      m_ok[m_pos]  = xValid;
      m_pos = (m_pos + 1) % m_len;
      if(m_count < m_len) m_count++;
      lo = 0.0; hi = 0.0;
      if(m_count < m_len) return false;
      bool first = true;
      for(int k = 0; k < m_len; k++)
      {
         if(!m_ok[k]) return false;
         if(first || m_val[k] < lo) lo = m_val[k];
         if(first || m_val[k] > hi) hi = m_val[k];
         first = false;
      }
      return true;
   }
};
// math.max / math.min with na (NA7): propagate by default (XPW_NA_MAX_PROPAGATES)
bool XpMax(double a, bool aOk, double b, bool bOk, double &out)
{
   if(aOk && bOk) { out = (a >= b) ? a : b; return true; }
#ifdef XPW_NA_MAX_PROPAGATES
   out = 0.0;
   return false;
#else
   if(aOk) { out = a; return true; }
   if(bOk) { out = b; return true; }
   out = 0.0;
   return false;
#endif
}
bool XpMin(double a, bool aOk, double b, bool bOk, double &out)
{
   if(aOk && bOk) { out = (a <= b) ? a : b; return true; }
#ifdef XPW_NA_MAX_PROPAGATES
   out = 0.0;
   return false;
#else
   if(aOk) { out = a; return true; }
   if(bOk) { out = b; return true; }
   out = 0.0;
   return false;
#endif
}

//+------------------------------------------------------------------+
//| Series calculators (one instance per Pine call site)              |
//+------------------------------------------------------------------+
CXpRsi     g_rsi;      // ta.rsi(close, rsiLen)
CXpSma     g_fast;     // ta.sma(rsiv, fastLen)
CXpSma     g_slow;     // ta.sma(rsiv, slowLen)
CXpExtreme g_ext;      // ta.lowest / ta.highest(slow, extLook)
CXpAtr     g_atr;      // ta.atr(atrLen)

//+------------------------------------------------------------------+
//| Pine `var` state (R5) - reset only on full recalc (R3)            |
//+------------------------------------------------------------------+
// run tracker
bool   runInit, runState;
int    runLen, runStart;
double runTop, runBot;  bool runTopOk, runBotOk;
double runSep;          bool runSepOk;
int    prevLen;
bool   prevState;
int    prevStart, prevEnd;
double prevTop, prevBot; bool prevTopOk, prevBotOk;
double prevSep;          bool prevSepOk;
int    prev2Len;
int    botCount, topCount;
int    lastBotBar, lastTopBar;
int    lastBotW, lastTopW;
double lastBotSep, lastTopSep;  bool lastBotSepOk, lastTopSepOk;
// ticks
int    upTickN, dnTickN;
int    lastUpTk, lastDnTk;
double lastUpAtr, lastDnAtr;    bool lastUpAtrOk, lastDnAtrOk;
// continuity
int    mDir, mBars;
double mStart;  bool mStartOk;
double mPath;   bool mPathOk;
int    m1Bars;
double m1Net;   bool m1NetOk;
double m1Path;  bool m1PathOk;
int    m2Bars;
double m2Net;   bool m2NetOk;
double m2Path;  bool m2PathOk;

//--- non-Pine bookkeeping ------------------------------------------------
int      g_barIndex   = -1;     // Pine bar_index of the last processed (logical) bar
double   g_prevClose  = 0.0;    // close[1]
bool     g_prevCloseOk = false;
datetime g_lastProcTime = 0;    // time of the last processed chart bar (R3 cursor)
int      g_lastProcIdx  = -1;   // chart index hint for the cursor
int      g_lastProcColour = -1; // isRedNow of the last processed chart bar (fill transitions)
int      g_lastProcChartIdx = -1;
datetime g_timeRing[];          // logical bar_index -> bar time (ring)
int      g_ringCap = 64;
int      g_subwin  = -1;
string   g_prefix  = "";
string   g_boxNames[];
string   g_labelNames[];
string   g_dumpRows[];
string   g_dumpPath = "";
bool     g_initPrinted = false;
long     g_fullRecalcs = 0;
long     g_measuredInterval = 0;
long     g_expectedInterval = 1;
bool     g_axisOk = false;
int      g_digits = 2;
double   g_point  = 0.01;
double   g_tickSize = 0.01;
string   g_tableNames[];
// last-bar values for the table (Pine reads them on barstate.islast)
double   g_tblSep;  bool g_tblSepOk;
bool     g_tblIsRedNow;
double   g_tblEff1, g_tblEff2, g_tblVel1, g_tblVel2;
bool     g_tblEff1Ok, g_tblEff2Ok, g_tblVel1Ok, g_tblVel2Ok;

//+------------------------------------------------------------------+
//| helpers                                                           |
//+------------------------------------------------------------------+
string SanitizeFileName(string s)
{
   string bad = "\\/:*?\"<>|";
   string out = s;
   for(int i = 0; i < StringLen(bad); i++)
   {
      string ch = StringSubstr(bad, i, 1);
      StringReplace(out, ch, "_");
   }
   return out;
}
// str.tostring(x, "#.##"): two decimals, trailing zeros (and the dot) trimmed
string Fmt2(double x)
{
   string s = DoubleToString(x, 2);
   int dot = StringFind(s, ".");
   if(dot >= 0)
   {
      int end = StringLen(s);
      while(end > dot && (StringGetCharacter(s, end - 1) == '0')) end--;
      if(end == dot + 1) end = dot;
      s = StringSubstr(s, 0, end);
   }
   if(s == "-0") s = "0";
   return s;
}
// str.tostring(x, format.mintick): rounded to the nearest tick, symbol digits
string FmtMintick(double x)
{
   double v = (g_tickSize > 0.0) ? MathRound(x / g_tickSize) * g_tickSize : x;
   return DoubleToString(v, g_digits);
}
string FmtNa(double x, bool ok, bool mintick)
{
   if(!ok) return "-";
   return mintick ? FmtMintick(x) : Fmt2(x);
}
string DumpNum(double x, bool ok)
{
   return ok ? DoubleToString(x, 8) : "na";
}
int ClampInt(int v, int lo, string name)
{
   if(v < lo) { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", v, " below minval ", lo, " - clamped"); return lo; }
   return v;
}
double ClampDbl(double v, double lo, double hi, bool hasHi, string name)
{
   if(v < lo)          { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", DoubleToString(v, 4), " below minval ", DoubleToString(lo, 4), " - clamped"); return lo; }
   if(hasHi && v > hi) { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", DoubleToString(v, 4), " above maxval ", DoubleToString(hi, 4), " - clamped"); return hi; }
   return v;
}
long ParseExpectedInterval(string sym)
{
   // engine naming: <parent>_S<n>[suffix]  ->  n seconds; default 1
   int p = StringFind(sym, "_S");
   if(p < 0) return 1;
   string rest = StringSubstr(sym, p + 2);
   long n = 0;
   for(int i = 0; i < StringLen(rest); i++)
   {
      ushort ch = StringGetCharacter(rest, i);
      if(ch < '0' || ch > '9') break;
      n = n * 10 + (long)(ch - '0');
   }
   return (n > 0) ? n : 1;
}
datetime RingTime(int barIndex)
{
   if(barIndex < 0) return 0;
   return g_timeRing[barIndex % g_ringCap];
}

//+------------------------------------------------------------------+
//| object helpers (R9)                                               |
//+------------------------------------------------------------------+
void PushName(string &arr[], string name, int cap)
{
   int n = ArraySize(arr);
   while(n >= cap)
   {
      ObjectDelete(0, arr[0]);
      ArrayRemove(arr, 0, 1);
      n--;
   }
   ArrayResize(arr, n + 1);
   arr[n] = name;
}
void DrawSquare(int l, int r, double t, bool tOk, double b, bool bOk, bool isRed, double refRng, bool refOk, string tag)
{
   // h = t - b ; padMin = max(refRng*0.03, 0.10) ; padv = h < padMin ? (padMin - h)/2 : 0
   double h = t - b;
   bool   hOk = tOk && bOk;
   double padMin = 0.0;
   bool   padOk = XpMax(refRng * 0.03, refOk, 0.10, true, padMin);
   double padv = 0.0;
   if(hOk && padOk && h < padMin) padv = (padMin - h) / 2.0;   // NA1: na comparison is false -> 0.0
   if(!hOk) return;                                            // box.new with na coordinates: nothing drawable (EQUIVALENT-ASSUMED)
   if(g_subwin < 0) return;
   datetime tl = RingTime(l);
   datetime tr = RingTime(r);
   color    c  = isRed ? XPW_RED : XPW_LIME;
   string   key = (string)(long)tr;
   string   boxName = g_prefix + (isRed ? "SQB_" : "SQT_") + key;
   string   tagName = g_prefix + (isRed ? "TGB_" : "TGT_") + key;
   if(ObjectCreate(0, boxName, OBJ_RECTANGLE, g_subwin, tl, t + padv, tr, b - padv))
   {
      ObjectSetInteger(0, boxName, OBJPROP_COLOR, c);
      ObjectSetInteger(0, boxName, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, boxName, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, boxName, OBJPROP_FILL, false);       // no alpha in MQL5: border kept, translucent bg omitted
      ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
      ObjectSetInteger(0, boxName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, boxName, OBJPROP_HIDDEN, true);
      ObjectSetString(0, boxName, OBJPROP_TOOLTIP, tag);
      PushName(g_boxNames, boxName, XPW_MAX_BOXES);
   }
   double y = isRed ? (b - padv) : (t + padv);
   if(ObjectCreate(0, tagName, OBJ_TEXT, g_subwin, tr, y))
   {
      ObjectSetString(0, tagName, OBJPROP_TEXT, tag);
      ObjectSetString(0, tagName, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, tagName, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, tagName, OBJPROP_COLOR, c);
      // label.style_label_up hangs below its anchor (ANCHOR_UPPER); label_down sits above it (ANCHOR_LOWER)
      ObjectSetInteger(0, tagName, OBJPROP_ANCHOR, isRed ? ANCHOR_UPPER : ANCHOR_LOWER);
      ObjectSetInteger(0, tagName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tagName, OBJPROP_HIDDEN, true);
      PushName(g_labelNames, tagName, XPW_MAX_LABELS);
   }
}
void DrawTickLabel(datetime t, double price, bool isUp, string txt)
{
   int    win = tickPrice ? 0 : g_subwin;
   double y   = tickPrice ? price : (isUp ? 95.0 : 5.0);
   if(win < 0) return;
   string name = g_prefix + (isUp ? "TKU_" : "TKD_") + (string)(long)t;
   if(ObjectCreate(0, name, OBJ_TEXT, win, t, y))
   {
      ObjectSetString(0, name, OBJPROP_TEXT, txt);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 7);
      ObjectSetInteger(0, name, OBJPROP_COLOR, isUp ? XPW_ORANGE : XPW_YELLOW);
      // up tick: label_down at high (text above the point) ; down tick: label_up at low (text below the point)
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, isUp ? ANCHOR_LOWER : ANCHOR_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      PushName(g_labelNames, name, XPW_MAX_LABELS);
   }
}

//+------------------------------------------------------------------+
//| table (R10): 8 Pine rows + 1 permitted "axis" row, OBJ_LABELs      |
//+------------------------------------------------------------------+
void TableCell(int row, int col, string text, color clr, int fontSize, int xRight, int yTop)
{
   string name = g_prefix + "TBL_" + (string)row + "_" + (string)col;
   if(ObjectFind(0, name) < 0)
   {
      if(!ObjectCreate(0, name, OBJ_LABEL, g_subwin, 0, 0)) return;
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      int n = ArraySize(g_tableNames);
      ArrayResize(g_tableNames, n + 1);
      g_tableNames[n] = name;
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xRight);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yTop);
}
int TextWidthPx(string text, int fontSize)
{
   uint w = 0, h = 0;
   TextSetFont("Arial", -fontSize * 10);
   if(!TextGetSize(text, w, h)) return StringLen(text) * (fontSize * 2 / 3 + 1);
   return (int)w;
}
void UpdateTable()
{
   if(!showTbl || g_subwin < 0) return;
   string period = (g_measuredInterval > 0) ? (string)g_measuredInterval + "s" : "?";
   string c0[9], c1[9];
   color  k0[9], k1[9];
   int    fs[9];
   for(int i = 0; i < 9; i++) { k0[i] = XPW_GRAY; fs[i] = 7; }
   c0[0] = "XPW MAP v0.4";                    k0[0] = XPW_WHITE; fs[0] = 9;
   c1[0] = period;                            k1[0] = XPW_WHITE;
   c0[1] = "state";
   c1[1] = StringFormat("%s %db sep %s", g_tblIsRedNow ? "RED" : "LIME", runLen, FmtNa(g_tblSep, g_tblSepOk, false));
   k1[1] = g_tblIsRedNow ? XPW_RED : XPW_LIME;
   c0[2] = "BOTTOM squares";
   c1[2] = (botCount == 0) ? "none" :
           StringFormat("n=%d  last %db sep %s, %d bars ago", botCount, lastBotW, FmtNa(lastBotSep, lastBotSepOk, false), g_barIndex - lastBotBar);
   k1[2] = XPW_RED;
   c0[3] = "TOP squares";
   c1[3] = (topCount == 0) ? "none" :
           StringFormat("n=%d  last %db sep %s, %d bars ago", topCount, lastTopW, FmtNa(lastTopSep, lastTopSepOk, false), g_barIndex - lastTopBar);
   k1[3] = XPW_LIME;
   c0[4] = "BOTTOM ticks";
   c1[4] = (dnTickN == 0) ? "none" :
           StringFormat("n=%d  last %s ATR, %d bars ago", dnTickN, FmtNa(lastDnAtr, lastDnAtrOk, false), g_barIndex - lastDnTk);
   k1[4] = XPW_YELLOW;
   c0[5] = "TOP ticks";
   c1[5] = (upTickN == 0) ? "none" :
           StringFormat("n=%d  last %s ATR, %d bars ago", upTickN, FmtNa(lastUpAtr, lastUpAtrOk, false), g_barIndex - lastUpTk);
   k1[5] = XPW_ORANGE;
   c0[6] = "move -1 / -2";
   c1[6] = (m1Bars == 0) ? "-" :
           StringFormat("%db eff %s vel %s  |  %db eff %s vel %s", m1Bars, FmtNa(g_tblEff1, g_tblEff1Ok, false), FmtNa(g_tblVel1, g_tblVel1Ok, true),
                        m2Bars, FmtNa(g_tblEff2, g_tblEff2Ok, false), FmtNa(g_tblVel2, g_tblVel2Ok, true));
   k1[6] = XPW_WHITE;
   c0[7] = "continuity";
   if(!g_tblEff1Ok || !g_tblEff2Ok) c1[7] = "-";
   else c1[7] = (g_tblEff1 > g_tblEff2) ? "move-1 more continuous" : (g_tblEff1 < g_tblEff2) ? "move-2 more continuous" : "equal";
   k1[7] = XPW_AQUA;
   c0[8] = "axis";                                                   // permitted 9th row (R10)
   c1[8] = StringFormat("%s measured, expected %ds: %s", period, (int)g_expectedInterval, g_axisOk ? "OK" : "MISMATCH");
   k1[8] = g_axisOk ? XPW_LIME : XPW_RED;

   int rowH = 13, w1 = 0;
   for(int i = 0; i < 9; i++)
   {
      int w = TextWidthPx(c1[i], fs[i]);
      if(w > w1) w1 = w;
   }
   int winH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, g_subwin);
   int yTop = winH / 2 - (9 * rowH) / 2;
   if(yTop < 2) yTop = 2;
   for(int i = 0; i < 9; i++)
   {
      TableCell(i, 1, c1[i], k1[i], fs[i], 6, yTop + i * rowH);
      TableCell(i, 0, c0[i], k0[i], fs[i], 6 + w1 + 12, yTop + i * rowH);
   }
}

//+------------------------------------------------------------------+
//| dump (Gate C)                                                     |
//+------------------------------------------------------------------+
void DumpReset()
{
   if(!DumpCSV) return;
   FolderCreate(XPW_DUMP_DIR);
   g_dumpPath = XPW_DUMP_DIR + "\\mapdump_" + SanitizeFileName(_Symbol) + ".csv";
   int h = FileOpen(g_dumpPath, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE) { Print("XPW MAP v", XPW_VERSION, " dump open failed: ", g_dumpPath, " err=", GetLastError()); return; }
   FileWrite(h, "time,open,high,low,close,tick_volume,bot_hit,bot_sep,bot_top,bot_bot,top_hit,top_sep,top_top,top_bot,up_tick,dn_tick,eff1,eff2,vel1,vel2,mbars,state,runlen,rsi,fast,slow,atr,bar_index");
   FileClose(h);
   ArrayResize(g_dumpRows, 0);
}
void DumpFlush()
{
   int n = ArraySize(g_dumpRows);
   if(!DumpCSV || n == 0) return;
   int h = FileOpen(g_dumpPath, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE) { Print("XPW MAP v", XPW_VERSION, " dump append failed: ", g_dumpPath, " err=", GetLastError()); ArrayResize(g_dumpRows, 0); return; }
   FileSeek(h, 0, SEEK_END);
   for(int i = 0; i < n; i++) FileWrite(h, g_dumpRows[i]);
   FileClose(h);
   ArrayResize(g_dumpRows, 0);
}
void DumpRow(string row)
{
   if(!DumpCSV) return;
   int n = ArraySize(g_dumpRows);
   ArrayResize(g_dumpRows, n + 1, 4096);
   g_dumpRows[n] = row;
}

//+------------------------------------------------------------------+
//| full reset (R3: prev_calculated == 0)                             |
//+------------------------------------------------------------------+
void ResetAll()
{
   g_rsi.Reset(); g_fast.Reset(); g_slow.Reset(); g_ext.Reset(); g_atr.Reset();

   runInit = false; runState = false; runLen = 0; runStart = 0;
   runTop = 0.0; runBot = 0.0; runTopOk = false; runBotOk = false;
   runSep = 0.0; runSepOk = true;
   prevLen = 0; prevState = false; prevStart = 0; prevEnd = 0;
   prevTop = 0.0; prevBot = 0.0; prevTopOk = false; prevBotOk = false;
   prevSep = 0.0; prevSepOk = true;
   prev2Len = 0;
   botCount = 0; topCount = 0;
   lastBotBar = 0; lastTopBar = 0;
   lastBotW = 0; lastTopW = 0;
   lastBotSep = 0.0; lastTopSep = 0.0; lastBotSepOk = false; lastTopSepOk = false;
   upTickN = 0; dnTickN = 0;
   lastUpTk = 0; lastDnTk = 0;
   lastUpAtr = 0.0; lastDnAtr = 0.0; lastUpAtrOk = false; lastDnAtrOk = false;
   mDir = 0; mBars = 0;
   mStart = 0.0; mStartOk = false;
   mPath = 0.0; mPathOk = true;
   m1Bars = 0; m1Net = 0.0; m1NetOk = false; m1Path = 0.0; m1PathOk = false;
   m2Bars = 0; m2Net = 0.0; m2NetOk = false; m2Path = 0.0; m2PathOk = false;

   g_barIndex = -1;
   g_prevClose = 0.0; g_prevCloseOk = false;
   g_lastProcTime = 0; g_lastProcIdx = -1; g_lastProcColour = -1; g_lastProcChartIdx = -1;
   for(int k = 0; k < ArraySize(g_timeRing); k++) g_timeRing[k] = 0;
   g_tblSep = 0.0; g_tblSepOk = false; g_tblIsRedNow = false;
   g_tblEff1 = 0.0; g_tblEff2 = 0.0; g_tblVel1 = 0.0; g_tblVel2 = 0.0;
   g_tblEff1Ok = false; g_tblEff2Ok = false; g_tblVel1Ok = false; g_tblVel2Ok = false;

   ArrayInitialize(BufRSI, EMPTY_VALUE);      ArrayInitialize(BufFast, EMPTY_VALUE);     ArrayInitialize(BufSlow, EMPTY_VALUE);
   ArrayInitialize(BufFillRedA, EMPTY_VALUE); ArrayInitialize(BufFillRedB, EMPTY_VALUE);
   ArrayInitialize(BufFillLimeA, EMPTY_VALUE);ArrayInitialize(BufFillLimeB, EMPTY_VALUE);
   ArrayInitialize(BufBotHit, EMPTY_VALUE);   ArrayInitialize(BufBotSep, EMPTY_VALUE);   ArrayInitialize(BufBotTop, EMPTY_VALUE);  ArrayInitialize(BufBotBot, EMPTY_VALUE);
   ArrayInitialize(BufTopHit, EMPTY_VALUE);   ArrayInitialize(BufTopSep, EMPTY_VALUE);   ArrayInitialize(BufTopTop, EMPTY_VALUE);  ArrayInitialize(BufTopBot, EMPTY_VALUE);
   ArrayInitialize(BufUpTick, EMPTY_VALUE);   ArrayInitialize(BufDnTick, EMPTY_VALUE);
   ArrayInitialize(BufEff1, EMPTY_VALUE);     ArrayInitialize(BufEff2, EMPTY_VALUE);     ArrayInitialize(BufVel1, EMPTY_VALUE);    ArrayInitialize(BufVel2, EMPTY_VALUE);
   ArrayInitialize(BufMBars, EMPTY_VALUE);    ArrayInitialize(BufState, EMPTY_VALUE);    ArrayInitialize(BufRunLen, EMPTY_VALUE);  ArrayInitialize(BufATR, EMPTY_VALUE);

   ObjectsDeleteAll(0, g_prefix, -1, -1);
   ArrayResize(g_boxNames, 0);
   ArrayResize(g_labelNames, 0);
   ArrayResize(g_tableNames, 0);
   DumpReset();
   g_fullRecalcs++;
   if(g_fullRecalcs == 1 || g_fullRecalcs == 10 || g_fullRecalcs == 100 || g_fullRecalcs == 1000 || g_fullRecalcs % 10000 == 0)
      Print("XPW MAP v", XPW_VERSION, " full recalc #", g_fullRecalcs, " (prev_calculated==0): state reset, replay from bar 0");
}
void ClearBar(int i)
{
   BufRSI[i] = EMPTY_VALUE; BufFast[i] = EMPTY_VALUE; BufSlow[i] = EMPTY_VALUE;
   BufFillRedA[i] = EMPTY_VALUE; BufFillRedB[i] = EMPTY_VALUE; BufFillLimeA[i] = EMPTY_VALUE; BufFillLimeB[i] = EMPTY_VALUE;
   BufBotHit[i] = EMPTY_VALUE; BufBotSep[i] = EMPTY_VALUE; BufBotTop[i] = EMPTY_VALUE; BufBotBot[i] = EMPTY_VALUE;
   BufTopHit[i] = EMPTY_VALUE; BufTopSep[i] = EMPTY_VALUE; BufTopTop[i] = EMPTY_VALUE; BufTopBot[i] = EMPTY_VALUE;
   BufUpTick[i] = EMPTY_VALUE; BufDnTick[i] = EMPTY_VALUE;
   BufEff1[i] = EMPTY_VALUE; BufEff2[i] = EMPTY_VALUE; BufVel1[i] = EMPTY_VALUE; BufVel2[i] = EMPTY_VALUE;
   BufMBars[i] = EMPTY_VALUE; BufState[i] = EMPTY_VALUE; BufRunLen[i] = EMPTY_VALUE; BufATR[i] = EMPTY_VALUE;
}

//+------------------------------------------------------------------+
//| measured bar interval (R10): median of time[i]-time[i-1], last 200 |
//+------------------------------------------------------------------+
void MeasureInterval(const datetime &time[], int rates_total)
{
   int n = MathMin(200, rates_total - 1);
   if(n < 1) { g_measuredInterval = 0; g_axisOk = false; return; }
   long d[];
   ArrayResize(d, n);
   for(int k = 0; k < n; k++)
   {
      int i = rates_total - 1 - k;
      d[k] = (long)time[i] - (long)time[i - 1];
   }
   ArraySort(d);
   g_measuredInterval = (n % 2 == 1) ? d[n / 2] : (d[n / 2 - 1] + d[n / 2]) / 2;
   g_axisOk = (g_measuredInterval == g_expectedInterval);
}

//+------------------------------------------------------------------+
//| one confirmed bar (everything under `if barstate.isconfirmed`)    |
//+------------------------------------------------------------------+
void ProcessBar(int i, const datetime &time[], const double &open[], const double &high[], const double &low[],
                const double &close[], const long &tick_volume[])
{
   double oo = open[i], hh = high[i], ll = low[i], cc = close[i];
   g_barIndex++;
   int bi = g_barIndex;
   g_timeRing[bi % g_ringCap] = time[i];

   // ---------------- TDI plots ----------------
   double rsiv = 0.0, fast = 0.0, slow = 0.0;
   bool rsiOk  = g_rsi.Update(cc, rsiv);
   bool fastOk = g_fast.Update(rsiv, rsiOk, fast);
   bool slowOk = g_slow.Update(rsiv, rsiOk, slow);
   bool stUp   = (fastOk && slowOk) ? (fast > slow) : false;      // NA1
   bool isRedNow = invertFill ? stUp : !stUp;                     // NA10
   double sep = 0.0;
   bool   sepOk = fastOk && slowOk;
   if(sepOk) sep = MathAbs(fast - slow);

   // ---------------- Run tracker ----------------
   bool   curUp = stUp;
   double mx = 0.0, mn = 0.0;
   bool   mxOk = XpMax(fast, fastOk, slow, slowOk, mx);
   bool   mnOk = XpMin(fast, fastOk, slow, slowOk, mn);
   if(!runInit)
   {
      runInit  = true;
      runState = curUp;
      runLen   = 1;
      runStart = bi;
      runTop = mx; runTopOk = mxOk;
      runBot = mn; runBotOk = mnOk;
      runSep = sep; runSepOk = sepOk;
   }
   else if(curUp != runState)
   {
      prev2Len  = prevLen;
      prevLen   = runLen;
      prevState = runState;
      prevStart = runStart;
      prevEnd   = bi - 1;
      prevTop = runTop; prevTopOk = runTopOk;
      prevBot = runBot; prevBotOk = runBotOk;
      prevSep = runSep; prevSepOk = runSepOk;
      runState = curUp;
      runLen   = 1;
      runStart = bi;
      runTop = mx; runTopOk = mxOk;
      runBot = mn; runBotOk = mnOk;
      runSep = sep; runSepOk = sepOk;
   }
   else
   {
      runLen = runLen + 1;
      double t2 = 0.0;
      bool ok2 = XpMax(runTop, runTopOk, mx, mxOk, t2);   runTop = t2; runTopOk = ok2;
      ok2 = XpMin(runBot, runBotOk, mn, mnOk, t2);        runBot = t2; runBotOk = ok2;
      ok2 = XpMax(runSep, runSepOk, sep, sepOk, t2);      runSep = t2; runSepOk = ok2;
   }

   double lo = 0.0, hi = 0.0;
   bool   extOk = g_ext.Update(slow, slowOk, lo, hi);
   double mid = 0.0;
   bool   midOk = prevTopOk && prevBotOk;
   if(midOk) mid = (prevTop + prevBot) / 2.0;
   double frac = 0.5;
   bool   fracOk = true;
   if(extOk && hi > lo)                                            // NA1: `hi > lo` false when na -> 0.5
   {
      fracOk = midOk;
      frac   = midOk ? (mid - lo) / (hi - lo) : 0.0;
   }
   bool isLow  = fracOk && (frac <= g_loFrac);
   bool isHigh = fracOk && (frac >= g_hiFrac);
   bool wasRed = invertFill ? prevState : !prevState;

   bool botHit = wasRed && runLen == g_sqBotCtx && prevLen >= g_sqBotMin && prevLen <= g_sqBotMax && prev2Len >= g_sqBotCtx
                 && (!sqBotArea || isLow) && (g_sqBotSep == 0.0 || (prevSepOk && prevSep >= g_sqBotSep));
   bool topHit = (!wasRed) && runLen == g_sqTopCtx && prevLen >= g_sqTopMin && prevLen <= g_sqTopMax && prev2Len >= g_sqTopCtx
                 && (!sqTopArea || isHigh) && (g_sqTopSep == 0.0 || (prevSepOk && prevSep >= g_sqTopSep));

   double refRng = extOk ? (hi - lo) : 0.0;
   if(botHit)
   {
      botCount   = botCount + 1;
      lastBotBar = prevEnd;
      lastBotW   = prevLen;
      lastBotSep = prevSep; lastBotSepOk = prevSepOk;
      if(sqBotOn)
         DrawSquare(prevStart, prevEnd, prevTop, prevTopOk, prevBot, prevBotOk, true, refRng, extOk,
                    StringFormat("BOT %db sep %s", prevLen, prevSepOk ? Fmt2(prevSep) : "NaN"));
   }
   if(topHit)
   {
      topCount   = topCount + 1;
      lastTopBar = prevEnd;
      lastTopW   = prevLen;
      lastTopSep = prevSep; lastTopSepOk = prevSepOk;
      if(sqTopOn)
         DrawSquare(prevStart, prevEnd, prevTop, prevTopOk, prevBot, prevBotOk, false, refRng, extOk,
                    StringFormat("TOP %db sep %s", prevLen, prevSepOk ? Fmt2(prevSep) : "NaN"));
   }

   // ---------------- Ticks ----------------
   double atrv = 0.0;
   bool   atrOk = g_atr.Update(hh, ll, cc, atrv);
   double rng = hh - ll;
   double upW = hh - MathMax(oo, cc);
   double dnW = MathMin(oo, cc) - ll;
   bool upTick = tickOn && rng > 0.0 && upW >= g_upWickFrac * rng && (atrOk && upW >= g_upWickAtr * atrv);
   bool dnTick = tickOn && rng > 0.0 && dnW >= g_dnWickFrac * rng && (atrOk && dnW >= g_dnWickAtr * atrv);
   double upRatio = 0.0, dnRatio = 0.0;
   if(upTick)
   {
      upTickN   = upTickN + 1;
      lastUpTk  = bi;
      lastUpAtr = upW / atrv; lastUpAtrOk = true;
      upRatio   = lastUpAtr;
      DrawTickLabel(time[i], hh, true, StringFormat("^ %s ATR", Fmt2(lastUpAtr)));
   }
   if(dnTick)
   {
      dnTickN   = dnTickN + 1;
      lastDnTk  = bi;
      lastDnAtr = dnW / atrv; lastDnAtrOk = true;
      dnRatio   = lastDnAtr;
      DrawTickLabel(time[i], ll, false, StringFormat("v %s ATR", Fmt2(lastDnAtr)));
   }

   // ---------------- Continuity ----------------
   double stp = 0.0;
   bool   stpOk = g_prevCloseOk;                                   // NA11: close[1] na on bar 0
   if(stpOk) stp = cc - g_prevClose;
   int d = (stpOk && stp > 0.0) ? 1 : (stpOk && stp < 0.0) ? -1 : mDir;
   if(mDir == 0)
   {
      mDir   = d;
      mBars  = 1;
      mStart = g_prevClose; mStartOk = g_prevCloseOk;
      mPath  = stpOk ? MathAbs(stp) : 0.0; mPathOk = stpOk;
   }
   else if(d == mDir)
   {
      mBars = mBars + 1;
      if(mPathOk && stpOk) mPath = mPath + MathAbs(stp); else mPathOk = false;
   }
   else
   {
      m2Bars = m1Bars;
      m2Net  = m1Net;  m2NetOk  = m1NetOk;
      m2Path = m1Path; m2PathOk = m1PathOk;
      m1Bars = mBars;
      m1NetOk = g_prevCloseOk && mStartOk;
      m1Net   = m1NetOk ? (g_prevClose - mStart) : 0.0;
      m1Path  = mPath; m1PathOk = mPathOk;
      mDir   = d;
      mBars  = 1;
      mStart = g_prevClose; mStartOk = g_prevCloseOk;
      mPath  = stpOk ? MathAbs(stp) : 0.0; mPathOk = stpOk;
   }
   g_prevClose = cc; g_prevCloseOk = true;

   bool   eff1Ok = m1PathOk && m1Path != 0.0 && m1NetOk;
   double eff1   = eff1Ok ? MathAbs(m1Net) / m1Path : 0.0;
   bool   eff2Ok = m2PathOk && m2Path != 0.0 && m2NetOk;
   double eff2   = eff2Ok ? MathAbs(m2Net) / m2Path : 0.0;
   bool   vel1Ok = m1NetOk && m1Bars != 0;
   double vel1   = vel1Ok ? MathAbs(m1Net) / (double)m1Bars : 0.0;
   bool   vel2Ok = m2NetOk && m2Bars != 0;
   double vel2   = vel2Ok ? MathAbs(m2Net) / (double)m2Bars : 0.0;

   // ---------------- buffers (R8) ----------------
   BufRSI[i]  = rsiOk  ? rsiv : EMPTY_VALUE;
   BufFast[i] = fastOk ? fast : EMPTY_VALUE;
   BufSlow[i] = slowOk ? slow : EMPTY_VALUE;
   BufATR[i]  = atrOk  ? atrv : EMPTY_VALUE;
   if(fastOk && slowOk)
   {
      if(isRedNow) { BufFillRedA[i] = fast;  BufFillRedB[i] = slow; }
      else         { BufFillLimeA[i] = fast; BufFillLimeB[i] = slow; }
      // colour transition: bridge the segment from the previous processed bar in the NEW colour
      int j = g_lastProcChartIdx;
      if(j >= 0 && g_lastProcColour >= 0 && g_lastProcColour != (isRedNow ? 1 : 0) && BufFast[j] != EMPTY_VALUE && BufSlow[j] != EMPTY_VALUE)
      {
         if(isRedNow) { BufFillRedA[j] = BufFast[j];  BufFillRedB[j] = BufSlow[j]; }
         else         { BufFillLimeA[j] = BufFast[j]; BufFillLimeB[j] = BufSlow[j]; }
      }
      g_lastProcColour = isRedNow ? 1 : 0;
   }
   else
      g_lastProcColour = -1;
   g_lastProcChartIdx = i;

   BufBotHit[i] = botHit ? (double)prevLen : 0.0;
   BufBotSep[i] = (botHit && prevSepOk) ? prevSep : EMPTY_VALUE;
   BufBotTop[i] = (botHit && prevTopOk) ? prevTop : EMPTY_VALUE;
   BufBotBot[i] = (botHit && prevBotOk) ? prevBot : EMPTY_VALUE;
   BufTopHit[i] = topHit ? (double)prevLen : 0.0;
   BufTopSep[i] = (topHit && prevSepOk) ? prevSep : EMPTY_VALUE;
   BufTopTop[i] = (topHit && prevTopOk) ? prevTop : EMPTY_VALUE;
   BufTopBot[i] = (topHit && prevBotOk) ? prevBot : EMPTY_VALUE;
   BufUpTick[i] = upTick ? upRatio : 0.0;
   BufDnTick[i] = dnTick ? dnRatio : 0.0;
   BufEff1[i]   = eff1Ok ? eff1 : EMPTY_VALUE;
   BufEff2[i]   = eff2Ok ? eff2 : EMPTY_VALUE;
   BufVel1[i]   = vel1Ok ? vel1 : EMPTY_VALUE;
   BufVel2[i]   = vel2Ok ? vel2 : EMPTY_VALUE;
   BufMBars[i]  = (double)mBars;
   BufState[i]  = isRedNow ? 1.0 : 0.0;
   BufRunLen[i] = (double)runLen;

   // table inputs (Pine reads these on the last bar)
   g_tblSep = sep; g_tblSepOk = sepOk; g_tblIsRedNow = isRedNow;
   g_tblEff1 = eff1; g_tblEff1Ok = eff1Ok; g_tblEff2 = eff2; g_tblEff2Ok = eff2Ok;
   g_tblVel1 = vel1; g_tblVel1Ok = vel1Ok; g_tblVel2 = vel2; g_tblVel2Ok = vel2Ok;

   // ---------------- dump (Gate C) ----------------
   if(DumpCSV)
   {
      string row = TimeToString(time[i], TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "," +
                   DoubleToString(oo, 8) + "," + DoubleToString(hh, 8) + "," + DoubleToString(ll, 8) + "," + DoubleToString(cc, 8) + "," +
                   (string)tick_volume[i] + "," +
                   (string)(botHit ? prevLen : 0) + "," + DumpNum(prevSep, botHit && prevSepOk) + "," + DumpNum(prevTop, botHit && prevTopOk) + "," + DumpNum(prevBot, botHit && prevBotOk) + "," +
                   (string)(topHit ? prevLen : 0) + "," + DumpNum(prevSep, topHit && prevSepOk) + "," + DumpNum(prevTop, topHit && prevTopOk) + "," + DumpNum(prevBot, topHit && prevBotOk) + "," +
                   DumpNum(upRatio, upTick) + "," + DumpNum(dnRatio, dnTick) + "," +
                   DumpNum(eff1, eff1Ok) + "," + DumpNum(eff2, eff2Ok) + "," + DumpNum(vel1, vel1Ok) + "," + DumpNum(vel2, vel2Ok) + "," +
                   (string)mBars + "," + (string)(isRedNow ? 1 : 0) + "," + (string)runLen + "," +
                   DumpNum(rsiv, rsiOk) + "," + DumpNum(fast, fastOk) + "," + DumpNum(slow, slowOk) + "," + DumpNum(atrv, atrOk) + "," +
                   (string)bi;
      DumpRow(row);
   }
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   // R6 clamps (minval/maxval from the Pine input() calls)
   g_rsiLen     = ClampInt(rsiLen, 2, "rsiLen");
   g_fastLen    = ClampInt(fastLen, 1, "fastLen");
   g_slowLen    = ClampInt(slowLen, 1, "slowLen");
   g_extLook    = ClampInt(extLook, 5, "extLook");
   g_loFrac     = ClampDbl(loFrac, 0.05, 0.5, true, "loFrac");
   g_hiFrac     = ClampDbl(hiFrac, 0.5, 0.95, true, "hiFrac");
   g_sqBotMin   = ClampInt(sqBotMin, 1, "sqBotMin");
   g_sqBotMax   = ClampInt(sqBotMax, 1, "sqBotMax");
   g_sqBotCtx   = ClampInt(sqBotCtx, 1, "sqBotCtx");
   g_sqBotSep   = ClampDbl(sqBotSep, 0.0, 0.0, false, "sqBotSep");
   g_sqTopMin   = ClampInt(sqTopMin, 1, "sqTopMin");
   g_sqTopMax   = ClampInt(sqTopMax, 1, "sqTopMax");
   g_sqTopCtx   = ClampInt(sqTopCtx, 1, "sqTopCtx");
   g_sqTopSep   = ClampDbl(sqTopSep, 0.0, 0.0, false, "sqTopSep");
   g_atrLen     = ClampInt(atrLen, 1, "atrLen");
   g_dnWickFrac = ClampDbl(dnWickFrac, 0.1, 1.0, true, "dnWickFrac");
   g_dnWickAtr  = ClampDbl(dnWickAtr, 0.0, 0.0, false, "dnWickAtr");
   g_upWickFrac = ClampDbl(upWickFrac, 0.1, 1.0, true, "upWickFrac");
   g_upWickAtr  = ClampDbl(upWickAtr, 0.0, 0.0, false, "upWickAtr");

   // G0.3: read the chart symbol's specs, never hardcode
   g_digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(g_tickSize <= 0.0) g_tickSize = g_point;
   g_expectedInterval = ParseExpectedInterval(_Symbol);

   // buffers
   SetIndexBuffer(0,  BufRSI,      INDICATOR_DATA);
   SetIndexBuffer(1,  BufFast,     INDICATOR_DATA);
   SetIndexBuffer(2,  BufSlow,     INDICATOR_DATA);
   SetIndexBuffer(3,  BufFillRedA, INDICATOR_DATA);
   SetIndexBuffer(4,  BufFillRedB, INDICATOR_DATA);
   SetIndexBuffer(5,  BufFillLimeA,INDICATOR_DATA);
   SetIndexBuffer(6,  BufFillLimeB,INDICATOR_DATA);
   SetIndexBuffer(7,  BufBotHit,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(8,  BufBotSep,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(9,  BufBotTop,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(10, BufBotBot,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(11, BufTopHit,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(12, BufTopSep,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(13, BufTopTop,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(14, BufTopBot,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(15, BufUpTick,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(16, BufDnTick,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(17, BufEff1,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(18, BufEff2,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(19, BufVel1,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(20, BufVel2,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(21, BufMBars,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(22, BufState,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(23, BufRunLen,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(24, BufATR,      INDICATOR_CALCULATIONS);
   for(int p = 0; p < 5; p++) PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 0, XPW_RED);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 1, XPW_RED);
   PlotIndexSetInteger(4, PLOT_LINE_COLOR, 0, XPW_LIME);
   PlotIndexSetInteger(4, PLOT_LINE_COLOR, 1, XPW_LIME);

   IndicatorSetString(INDICATOR_SHORTNAME, "XPW MAP v0.4");
   IndicatorSetInteger(INDICATOR_DIGITS, 2);
   IndicatorSetDouble(INDICATOR_MINIMUM, 0.0);
   IndicatorSetDouble(INDICATOR_MAXIMUM, 100.0);

   // series calculators
   g_rsi.Init(g_rsiLen);
   g_fast.Init(g_fastLen);
   g_slow.Init(g_slowLen);
   g_ext.Init(g_extLook);
   g_atr.Init(g_atrLen);

   // time ring must cover prevStart of any drawable square: runLen(=ctx) + prevLen(<=max) + slack
   int need = MathMax(g_sqBotCtx + g_sqBotMax, g_sqTopCtx + g_sqTopMax) + 8;
   g_ringCap = MathMax(64, need);
   ArrayResize(g_timeRing, g_ringCap);

   g_prefix = "XPWMAP_" + (string)ChartID() + "_";
   g_subwin = ChartWindowFind();
   g_initPrinted = false;
   g_fullRecalcs = 0;
   ResetAll();
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DumpFlush();
   ObjectsDeleteAll(0, g_prefix, -1, -1);
   ChartRedraw();
}
//+------------------------------------------------------------------+
//| OnCalculate                                                       |
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
   if(rates_total < 1) return 0;
   if(g_subwin < 0) g_subwin = ChartWindowFind();
   if(prev_calculated == 0 && g_lastProcTime != 0) ResetAll();   // R3: full replay (first call already reset in OnInit)

   MeasureInterval(time, rates_total);
   if(!g_initPrinted && rates_total >= 2)
   {
      Print("XPW MAP v", XPW_VERSION, " init: symbol=", _Symbol, " digits=", g_digits, " point=", DoubleToString(g_point, g_digits),
            " tick_size=", DoubleToString(g_tickSize, g_digits), " measured_interval_s=", g_measuredInterval,
            " expected_interval_s=", g_expectedInterval, " axis_ok=", g_axisOk,
            " LastBarIsClosed=", LastBarIsClosed, " SkipEmptyBars=", SkipEmptyBars, " DumpCSV=", DumpCSV,
            " bars_loaded=", rates_total, " subwindow=", g_subwin);
      g_initPrinted = true;
   }

   int lastClosed = LastBarIsClosed ? rates_total - 1 : rates_total - 2;

   // R3 cursor: first chart index whose time is later than the last processed bar
   int i0 = 0;
   if(g_lastProcTime != 0)
   {
      int idx = g_lastProcIdx;
      if(idx < 0) idx = 0;
      if(idx > rates_total - 1) idx = rates_total - 1;
      while(idx > 0 && time[idx] > g_lastProcTime) idx--;
      while(idx < rates_total - 1 && time[idx + 1] <= g_lastProcTime) idx++;
      i0 = (time[idx] <= g_lastProcTime) ? idx + 1 : idx;
   }
   for(int i = i0; i < rates_total; i++) ClearBar(i);           // forming / unprocessed bars hold EMPTY_VALUE

   bool any = false;
   for(int i = i0; i <= lastClosed; i++)
   {
      if(time[i] <= g_lastProcTime) continue;                    // never twice
      if(!(SkipEmptyBars && tick_volume[i] == 0))               // R4
         ProcessBar(i, time, open, high, low, close, tick_volume);
      g_lastProcTime = time[i];
      g_lastProcIdx  = i;
      any = true;
   }
   if(any)
   {
      UpdateTable();
      DumpFlush();
      ChartRedraw();
   }
   return rates_total;
}
//+------------------------------------------------------------------+
