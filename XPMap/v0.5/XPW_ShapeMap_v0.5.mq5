//+------------------------------------------------------------------+
//|                                            XPW_ShapeMap_v0.5.mq5 |
//|  Port of the TradingView Pine script "XPW Shape Map v0.5"         |
//|  (map layer only, no signals). Wedge squares, turn marks, ticks,  |
//|  legs, table.                                                     |
//|                                                                   |
//|  Zero-logic-loss port rules (see XPW_SHAPEMAP_V0.5_PORT_REPORT.md)|
//|   - ta.rsi / ta.sma / ta.atr / ta.highest / ta.lowest in buffers  |
//|     (no iRSI/iATR/iMA handles); Pine na semantics via valid flags.|
//|   - Pine history references x[k] come from rings keyed by the     |
//|     Pine bar_index (logical bar count), never by chart index.     |
//|   - Confirmed bars only, once each, tracked by bar time; full     |
//|     replay when prev_calculated == 0. Nothing repaints.           |
//|                                                                   |
//|  CONSUMPTION (iCustom) - buffer index map, stamped at the         |
//|  confirmation bar (the bar where the Pine `if` evaluated true):   |
//|    0 FAST  1 SLOW   2,3 fill red   4,5 fill lime   [visual]       |
//|    6 BOT_SQ (=botWid, 0 otherwise)  7 BOT_SQ_TOP  8 BOT_SQ_BOT    |
//|    9 TOP_SQ (=topWid)              10 TOP_SQ_TOP 11 TOP_SQ_BOT    |
//|   12 BOT_TURN (1/0)  13 BOT_TURN_GAP (=tb-lastBotWedge)           |
//|   14 TOP_TURN (1/0)  15 TOP_TURN_GAP                              |
//|   16 BOT_TICK (=dnWick/atrV, 0 otherwise)  17 TOP_TICK            |
//|   18 STATE (isRed 1/0)  19 POSW  20 AREA (-1 LOW, 0 MID, +1 HIGH) |
//|   21 BOT_ARMED (1/0 after the bar)  22 TOP_ARMED                  |
//|   23 LEG_DIR (+1/-1 when a leg closes on this bar, 0 otherwise)   |
//|   24 LEG_DIST  25 LEG_BARS  26 LEG_EFF   (EMPTY_VALUE otherwise)  |
//|   27 RSI  28 ATR                                                  |
//|  The turn MARK is drawn at bar-turnHold; the buffers are stamped  |
//|  at the confirmation bar. Unprocessed bars hold EMPTY_VALUE.      |
//|                                                                   |
//|  NOTE FOR ANY EA READING THESE BUFFERS: an EA on a custom chart   |
//|  (XAUUSD-ECNc_S1) must trade the PARENT symbol (XAUUSD-ECNc).     |
//|  Custom symbols do not trade.                                     |
//+------------------------------------------------------------------+
#property copyright   "xpworx"
#property link        "ghostmaster"
#property description "XPW Shape Map v0.5 - Pine port. Map layer only: wedge squares, turn marks, ticks, legs."
#define  XPW_VERSION  "0.5"
#property version     "0.50"

#property indicator_separate_window
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_buffers 29
#property indicator_plots   4

#property indicator_label1  "Fast"
#property indicator_type1   DRAW_LINE
#property indicator_color1  C'120,123,134'
#property indicator_width1  1
#property indicator_label2  "Slow"
#property indicator_type2   DRAW_LINE
#property indicator_color2  C'178,181,190'
#property indicator_width2  1
#property indicator_label3  "Fill RED"
#property indicator_type3   DRAW_FILLING
#property indicator_color3  C'255,82,82',C'255,82,82'
#property indicator_label4  "Fill LIME"
#property indicator_type4   DRAW_FILLING
#property indicator_color4  C'0,230,118',C'0,230,118'

//+------------------------------------------------------------------+
//| Inputs - the 29 Pine inputs, same names, defaults, order, groups  |
//+------------------------------------------------------------------+
input group "TDI"
input int    rsiLen     = 14;     // RSI length (min 2)
input int    fastLen    = 2;      // Fast MA length (min 1)
input int    slowLen    = 7;      // Slow MA length (min 1)
input bool   invertFill = true;   // My panel paints fast>slow as RED

input group "Areas"
input int    areaLook   = 20;     // Area lookback (min 5)
input double loFrac     = 0.20;   // LOW area: below this fraction (0..1)
input double hiFrac     = 0.67;   // HIGH area: above this fraction (0..1)

input group "BOTTOM square (odd RED wedge, LOW area)"
input bool   botOn      = true;   // Enable
input int    botMinW    = 1;      // Min width (min 1)
input int    botMaxW    = 3;      // Max width (min 1)
input int    botCtx     = 2;      // Context bars (min 1)
input bool   botNeedLow = true;   // Require LOW area
input int    botSep     = 5;      // Min bars between squares (min 0)

input group "TOP square (odd LIME wedge, HIGH area)"
input bool   topOn       = true;  // Enable
input int    topMinW     = 1;     // Min width (min 1)
input int    topMaxW     = 2;     // Max width (min 1)
input int    topCtx      = 3;     // Context bars (min 1)
input bool   topNeedHigh = true;  // Require HIGH area
input int    topSep      = 5;     // Min bars between squares (min 0)

input group "Turn mark"
input bool   turnOn     = true;   // Enable
input int    turnMax    = 12;     // Max bars to wait after a square (min 1)
input int    turnHold   = 2;      // Bars the cross must hold (min 1)

input group "Ticks"
input bool   tickOn       = true; // Enable
input int    atrLen       = 14;   // ATR length (min 2)
input double botWickRange = 0.55; // BOTTOM: min lower wick / range
input double botWickAtr   = 0.8;  // BOTTOM: min lower wick / ATR
input double topWickRange = 0.70; // TOP: min upper wick / range
input double topWickAtr   = 1.20; // TOP: min upper wick / ATR

input group "Display"
input bool   showTable  = true;   // Show table

input group "Port (MQL5 only)"
input bool   LastBarIsClosed = false;  // rates_total-1 is a CLOSED bar (false: forming, evaluate rates_total-2)
input bool   SkipEmptyBars   = false;  // Skip bars with tick_volume==0 (engine WriteEmptyBars=true marker)
input bool   DumpCSV         = false;  // Write MQL5\Files\XPChart\mapdump05_<symbol>.csv (Gate C)

#define XPW_NA_MAX_PROPAGATES     // NA7: math.max/min with na -> na (comment out if Gate B says otherwise)
#define XPW_MAX_BOXES  500
#define XPW_MAX_LABELS 500
const string XPW_DUMP_DIR = "XPChart";

//--- Pine v6 palette
const color XPW_RED    = C'255,82,82';    // color.red    #FF5252
const color XPW_LIME   = C'0,230,118';    // color.lime   #00E676
const color XPW_GREEN  = C'76,175,80';    // color.green  #4CAF50
const color XPW_YELLOW = C'255,235,59';   // color.yellow #FFEB3B
const color XPW_ORANGE = C'255,152,0';    // color.orange #FF9800
const color XPW_GRAY   = C'120,123,134';  // color.gray   #787B86
const color XPW_SILVER = C'178,181,190';  // color.silver #B2B5BE
const color XPW_BLUE   = C'33,150,243';   // color.blue   #2196F3
const color XPW_WHITE  = clrWhite;
const color XPW_BLACK  = clrBlack;

//+------------------------------------------------------------------+
//| buffers                                                           |
//+------------------------------------------------------------------+
double BufFast[], BufSlow[], BufFillRedA[], BufFillRedB[], BufFillLimeA[], BufFillLimeB[];
double BufBotSq[], BufBotSqTop[], BufBotSqBot[], BufTopSq[], BufTopSqTop[], BufTopSqBot[];
double BufBotTurn[], BufBotTurnGap[], BufTopTurn[], BufTopTurnGap[];
double BufBotTick[], BufTopTick[], BufState[], BufPosW[], BufArea[], BufBotArmed[], BufTopArmed[];
double BufLegDir[], BufLegDist[], BufLegBars[], BufLegEff[], BufRSI[], BufATR[];

//--- clamped inputs (R6)
int    g_rsiLen, g_fastLen, g_slowLen, g_areaLook;
double g_loFrac, g_hiFrac;
int    g_botMinW, g_botMaxW, g_botCtx, g_botSep, g_topMinW, g_topMaxW, g_topCtx, g_topSep, g_turnMax, g_turnHold, g_atrLen;

//+------------------------------------------------------------------+
//| ta.* reimplementations with explicit valid flags                  |
//+------------------------------------------------------------------+
class CXpSma
{
private:
   int    m_len;
   double m_val[];
   bool   m_ok[];
   int    m_count;
   int    m_pos;
public:
   void Init(int len) { m_len = (len < 1) ? 1 : len; ArrayResize(m_val, m_len); ArrayResize(m_ok, m_len); Reset(); }
   void Reset()       { ArrayInitialize(m_val, 0.0); ArrayInitialize(m_ok, false); m_count = 0; m_pos = 0; }
   bool Update(double x, bool xValid, double &out)
   {
      m_val[m_pos] = x; m_ok[m_pos] = xValid;
      m_pos = (m_pos + 1) % m_len;
      if(m_count < m_len) m_count++;
      out = 0.0;
      if(m_count < m_len) return false;
      double s = 0.0;
      for(int k = 0; k < m_len; k++) { if(!m_ok[k]) return false; s += m_val[k]; }
      out = s / (double)m_len;
      return true;
   }
   void CopyFrom(const CXpSma &s)
   {
      m_len = s.m_len;
      ArrayResize(m_val, m_len);
      ArrayResize(m_ok, m_len);
      ArrayCopy(m_val, s.m_val);
      ArrayCopy(m_ok, s.m_ok);
      m_count = s.m_count;
      m_pos   = s.m_pos;
   }
};
class CXpRma
{
private:
   int    m_len;
   CXpSma m_seed;
   double m_value;
   bool   m_valid;
public:
   void Init(int len) { m_len = (len < 1) ? 1 : len; m_seed.Init(m_len); Reset(); }
   void Reset()       { m_seed.Reset(); m_value = 0.0; m_valid = false; }
   bool Update(double x, bool xValid, double &out)
   {
      if(!m_valid) { double s = 0.0; if(m_seed.Update(x, xValid, s)) { m_value = s; m_valid = true; } }
      else if(xValid) m_value = (x + (double)(m_len - 1) * m_value) / (double)m_len;
      else m_valid = false;
      out = m_value;
      return m_valid;
   }
   void CopyFrom(const CXpRma &s)
   {
      m_len = s.m_len;
      m_seed.CopyFrom(s.m_seed);
      m_value = s.m_value;
      m_valid = s.m_valid;
   }
};
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
      double chg = chgValid ? (src - m_prev) : 0.0;
      m_prev = src; m_prevValid = true;
      double u = chgValid ? MathMax(chg, 0.0) : 0.0;
      double d = chgValid ? MathMax(-chg, 0.0) : 0.0;
      double au = 0.0, ad = 0.0;
      bool okU = m_up.Update(u, chgValid, au);
      bool okD = m_dn.Update(d, chgValid, ad);
      out = 0.0;
      if(!okU || !okD) return false;
      if(ad == 0.0) { out = 100.0; return true; }
      if(au == 0.0) { out = 0.0;   return true; }
      out = 100.0 - 100.0 / (1.0 + au / ad);
      return true;
   }
   void CopyFrom(const CXpRsi &s)
   {
      m_up.CopyFrom(s.m_up);
      m_dn.CopyFrom(s.m_dn);
      m_prev = s.m_prev;
      m_prevValid = s.m_prevValid;
   }
};
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
      if(m_prevValid) tr = MathMax(h - l, MathMax(MathAbs(h - m_prevClose), MathAbs(l - m_prevClose)));
      m_prevClose = c; m_prevValid = true;
      return m_rma.Update(tr, true, out);
   }
};
class CXpExtreme
{
private:
   int    m_len;
   double m_val[];
   bool   m_ok[];
   int    m_count;
   int    m_pos;
public:
   void Init(int len) { m_len = (len < 1) ? 1 : len; ArrayResize(m_val, m_len); ArrayResize(m_ok, m_len); Reset(); }
   void Reset()       { ArrayInitialize(m_val, 0.0); ArrayInitialize(m_ok, false); m_count = 0; m_pos = 0; }
   bool Update(double x, bool xValid, double &lo, double &hi)
   {
      m_val[m_pos] = x; m_ok[m_pos] = xValid;
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
   void CopyFrom(const CXpExtreme &s)
   {
      m_len = s.m_len;
      ArrayResize(m_val, m_len);
      ArrayResize(m_ok, m_len);
      ArrayCopy(m_val, s.m_val);
      ArrayCopy(m_ok, s.m_ok);
      m_count = s.m_count;
      m_pos   = s.m_pos;
   }
};
bool XpMax(double a, bool aOk, double b, bool bOk, double &out)
{
   if(aOk && bOk) { out = (a >= b) ? a : b; return true; }
#ifdef XPW_NA_MAX_PROPAGATES
   out = 0.0; return false;
#else
   if(aOk) { out = a; return true; }
   if(bOk) { out = b; return true; }
   out = 0.0; return false;
#endif
}
bool XpMin(double a, bool aOk, double b, bool bOk, double &out)
{
   if(aOk && bOk) { out = (a <= b) ? a : b; return true; }
#ifdef XPW_NA_MAX_PROPAGATES
   out = 0.0; return false;
#else
   if(aOk) { out = a; return true; }
   if(bOk) { out = b; return true; }
   out = 0.0; return false;
#endif
}

CXpRsi     g_rsi;
CXpSma     g_fast;
CXpSma     g_slow;
CXpExtreme g_ext;
CXpAtr     g_atr;
//--- preview copies for the forming bar (Pine plots the realtime bar on every tick; the copies never touch confirmed state)
CXpRsi     g_rsiP;
CXpSma     g_fastP;
CXpSma     g_slowP;
CXpExtreme g_extP;

//+------------------------------------------------------------------+
//| Pine `var` state - reset only on full recalc                      |
//+------------------------------------------------------------------+
int    lastBotBar, lastTopBar, lastBotWedge, lastTopWedge;
int    nBotSq, nTopSq;
bool   botArmed, topArmed;
int    botArmBar, topArmBar;
int    nBotTurn, nTopTurn, lastBotGap, lastTopGap;
int    nBotTk, nTopTk;
bool   legOpen;
int    legDir;
double legP0;   bool legP0Ok;
int    legB0;
double legPath;
string leg1, leg2;

//--- history rings keyed by Pine bar_index (x[k] references)
int      g_ringCap = 64;
int      g_rIsRed[];
double   g_rFast[];
bool     g_rFastOk[];
double   g_rSlow[];
bool     g_rSlowOk[];
bool     g_rInLow[], g_rInHigh[];
datetime g_rTime[];

//--- bookkeeping
int      g_barIndex = -1;
double   g_prevClose = 0.0;  bool g_prevCloseOk = false;
datetime g_lastProcTime = 0;
int      g_lastProcIdx = -1, g_lastProcColour = -1, g_lastProcChartIdx = -1;
int      g_subwin = -1;
string   g_prefix = "";
string   g_boxNames[], g_labelNames[], g_tableNames[], g_dumpRows[];
string   g_dumpPath = "";
bool     g_initPrinted = false;
long     g_fullRecalcs = 0, g_measuredInterval = 0, g_expectedInterval = 1;
bool     g_axisOk = false;
int      g_digits = 2;
double   g_point = 0.01, g_tickSize = 0.01;
// last-bar values for the table
bool     g_tblIsRed = false, g_tblInLow = false, g_tblInHigh = false;
double   g_tblPosW = 0.5;

//+------------------------------------------------------------------+
//| helpers                                                           |
//+------------------------------------------------------------------+
string SanitizeFileName(string s)
{
   string bad = "\\/:*?\"<>|";
   string out = s;
   for(int i = 0; i < StringLen(bad); i++) { string ch = StringSubstr(bad, i, 1); StringReplace(out, ch, "_"); }
   return out;
}
string Fmt2(double x)          // str.tostring(x, "#.##")
{
   string s = DoubleToString(x, 2);
   int dot = StringFind(s, ".");
   if(dot >= 0)
   {
      int end = StringLen(s);
      while(end > dot && StringGetCharacter(s, end - 1) == '0') end--;
      if(end == dot + 1) end = dot;
      s = StringSubstr(s, 0, end);
   }
   if(s == "-0") s = "0";
   return s;
}
string Fmt00(double x) { return DoubleToString(x, 2); }   // str.tostring(x, "#.00")
string DumpNum(double x, bool ok) { return ok ? DoubleToString(x, 8) : "na"; }
int ClampInt(int v, int lo, string name)
{
   if(v < lo) { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", v, " below minval ", lo, " - clamped"); return lo; }
   return v;
}
double ClampDbl(double v, double lo, double hi, string name)
{
   if(v < lo) { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", DoubleToString(v, 4), " below minval ", DoubleToString(lo, 4), " - clamped"); return lo; }
   if(v > hi) { Print("XPW MAP v", XPW_VERSION, " WARNING: input ", name, "=", DoubleToString(v, 4), " above maxval ", DoubleToString(hi, 4), " - clamped"); return hi; }
   return v;
}
long ParseExpectedInterval(string sym)
{
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
//--- x[k] history access (NA8: before bar 0 -> na -> comparisons false)
int  HistIdx(int k)      { int idx = g_barIndex - k; return (idx < 0) ? -1 : (idx % g_ringCap); }
bool IsRedAt(int k)      { int i = HistIdx(k); return (i < 0) ? false : (g_rIsRed[i] == 1); }
bool IsLimeAt(int k)     { int i = HistIdx(k); return (i < 0) ? false : (g_rIsRed[i] == 0); }
bool FastAt(int k, double &v) { int i = HistIdx(k); if(i < 0) { v = 0.0; return false; } v = g_rFast[i]; return g_rFastOk[i]; }
bool SlowAt(int k, double &v) { int i = HistIdx(k); if(i < 0) { v = 0.0; return false; } v = g_rSlow[i]; return g_rSlowOk[i]; }
bool InLowAt(int k)      { int i = HistIdx(k); return (i < 0) ? false : g_rInLow[i]; }
bool InHighAt(int k)     { int i = HistIdx(k); return (i < 0) ? false : g_rInHigh[i]; }
datetime TimeAt(int barIndex) { return (barIndex < 0) ? 0 : g_rTime[barIndex % g_ringCap]; }
bool FastGtSlowAt(int k) { double f = 0.0, s = 0.0; bool fo = FastAt(k, f), so = SlowAt(k, s); return fo && so && f > s; }
bool FastLtSlowAt(int k) { double f = 0.0, s = 0.0; bool fo = FastAt(k, f), so = SlowAt(k, s); return fo && so && f < s; }
bool FastLeSlowAt(int k) { double f = 0.0, s = 0.0; bool fo = FastAt(k, f), so = SlowAt(k, s); return fo && so && f <= s; }
bool FastGeSlowAt(int k) { double f = 0.0, s = 0.0; bool fo = FastAt(k, f), so = SlowAt(k, s); return fo && so && f >= s; }

//+------------------------------------------------------------------+
//| detect(wantRedWedge, minW, maxW, ctx) - verbatim                  |
//+------------------------------------------------------------------+
bool Detect(bool wantRedWedge, int minW, int maxW, int ctx, int &wOut)
{
   int  wHi = MathMax(minW, maxW);
   bool fired = false;
   wOut = 0;
   for(int w = minW; w <= wHi; w++)
   {
      if(fired) continue;
      bool ok = true;
      for(int i = 0; i < ctx; i++)
      {
         bool v = wantRedWedge ? IsLimeAt(i) : IsRedAt(i);
         if(!v) ok = false;
      }
      if(ok)
         for(int i = 0; i < w; i++)
         {
            bool v = wantRedWedge ? IsRedAt(ctx + i) : IsLimeAt(ctx + i);
            if(!v) ok = false;
         }
      if(ok)
         for(int i = 0; i < ctx; i++)
         {
            bool v = wantRedWedge ? IsLimeAt(ctx + w + i) : IsRedAt(ctx + w + i);
            if(!v) ok = false;
         }
      if(ok) { fired = true; wOut = w; }
   }
   return fired;
}

//+------------------------------------------------------------------+
//| objects                                                           |
//+------------------------------------------------------------------+
void PushName(string &arr[], string name, int cap)
{
   int n = ArraySize(arr);
   while(n >= cap) { ObjectDelete(0, arr[0]); ArrayRemove(arr, 0, 1); n--; }
   ArrayResize(arr, n + 1);
   arr[n] = name;
}
void DrawText(int win, string name, datetime t, double y, string txt, color clr, int anchor, string font, int fontSize)
{
   if(win < 0) return;
   if(ObjectCreate(0, name, OBJ_TEXT, win, t, y))
   {
      ObjectSetString(0, name, OBJPROP_TEXT, txt);
      ObjectSetString(0, name, OBJPROP_FONT, font);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      PushName(g_labelNames, name, XPW_MAX_LABELS);
   }
}
void DrawBox(string name, int lft, int rgt, double top, double bottom, color clr)
{
   if(g_subwin < 0) return;
   if(ObjectCreate(0, name, OBJ_RECTANGLE, g_subwin, TimeAt(lft), top, TimeAt(rgt), bottom))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_FILL, false);     // no alpha in MQL5: border kept, translucent bg omitted
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      PushName(g_boxNames, name, XPW_MAX_BOXES);
   }
}

//+------------------------------------------------------------------+
//| table: 10 Pine rows as OBJ_LABELs, frame + header background      |
//+------------------------------------------------------------------+
void TableRect(string name, int xRight, int yTop, int w, int h, color bg, color border)
{
   if(ObjectFind(0, name) < 0)
   {
      if(!ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, g_subwin, 0, 0)) return;
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      int n = ArraySize(g_tableNames); ArrayResize(g_tableNames, n + 1); g_tableNames[n] = name;
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xRight);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yTop);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, bg);
   ObjectSetInteger(0, name, OBJPROP_COLOR, border);
}
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
      int n = ArraySize(g_tableNames); ArrayResize(g_tableNames, n + 1); g_tableNames[n] = name;
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
   if(!showTable || g_subwin < 0) return;
   string c0[11], c1[11];
   color  k0[11], k1[11];
   int    rows = 11, fs = 7, rowH = 13, pad = 4;
   for(int i = 0; i < rows; i++) { k0[i] = XPW_BLACK; k1[i] = XPW_BLACK; }   // Pine table.cell default text colour
   c0[0] = "XPW Shape Map v0.5";  k0[0] = XPW_WHITE;
   c1[0] = g_tblIsRed ? "RED" : "LIME";  k1[0] = XPW_WHITE;
   c0[1] = "Area pos";
   c1[1] = Fmt00(g_tblPosW) + (g_tblInLow ? " LOW" : g_tblInHigh ? " HIGH" : " MID");
   c0[2] = "BOT squares";  c1[2] = (string)nBotSq;
   c0[3] = "TOP squares";  c1[3] = (string)nTopSq;
   c0[4] = "BOT turns";    c1[4] = (string)nBotTurn + "  gap " + (string)lastBotGap + "b";
   c0[5] = "TOP turns";    c1[5] = (string)nTopTurn + "  gap " + (string)lastTopGap + "b";
   c0[6] = "BOT ticks";    c1[6] = (string)nBotTk;
   c0[7] = "TOP ticks";    c1[7] = (string)nTopTk;
   c0[8] = "Leg -1";       c1[8] = leg1;
   c0[9] = "Leg -2";       c1[9] = leg2;
   string period = (g_measuredInterval > 0) ? (string)g_measuredInterval + "s" : "?";
   c0[10] = "axis";                                                  // permitted 9th-row equivalent (R10)
   c1[10] = period + " measured, expected " + (string)g_expectedInterval + "s: " + (g_axisOk ? "OK" : "MISMATCH");
   k1[10] = g_axisOk ? XPW_GREEN : XPW_RED;
   int w0 = 0, w1 = 0;
   for(int i = 0; i < rows; i++)
   {
      int a = TextWidthPx(c0[i], fs), b = TextWidthPx(c1[i], fs);
      if(a > w0) w0 = a;
      if(b > w1) w1 = b;
   }
   int winH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, g_subwin);
   int totalH = rows * rowH + 2 * pad, totalW = w0 + w1 + 4 * pad;
   int yTop = winH / 2 - totalH / 2;
   if(yTop < 2) yTop = 2;
   TableRect(g_prefix + "TBL_FRAME", 4, yTop, totalW, totalH, clrNONE, XPW_GRAY);             // frame_color gray
   TableRect(g_prefix + "TBL_HEAD", 5, yTop + pad, totalW - 2, rowH, XPW_BLUE, XPW_BLUE);      // header bgcolor blue
   for(int i = 0; i < rows; i++)
   {
      TableCell(i, 1, c1[i], k1[i], fs, 4 + pad, yTop + pad + i * rowH);
      TableCell(i, 0, c0[i], k0[i], fs, 4 + pad + w1 + 2 * pad, yTop + pad + i * rowH);
   }
}

//+------------------------------------------------------------------+
//| dump (Gate C)                                                     |
//+------------------------------------------------------------------+
void DumpReset()
{
   if(!DumpCSV) return;
   FolderCreate(XPW_DUMP_DIR);
   g_dumpPath = XPW_DUMP_DIR + "\\mapdump05_" + SanitizeFileName(_Symbol) + ".csv";
   int h = FileOpen(g_dumpPath, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE) { Print("XPW MAP v", XPW_VERSION, " dump open failed: ", g_dumpPath, " err=", GetLastError()); return; }
   FileWrite(h, "time,open,high,low,close,tick_volume,bot_sq,bot_sq_top,bot_sq_bot,top_sq,top_sq_top,top_sq_bot,bot_turn,bot_turn_gap,top_turn,top_turn_gap,bot_tick,top_tick,state,posw,area,bot_armed,top_armed,leg_dir,leg_dist,leg_bars,leg_eff,rsi,fast,slow,atr,bar_index");
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
//| full reset                                                        |
//+------------------------------------------------------------------+
void ClearBar(int i)
{
   BufFast[i] = EMPTY_VALUE; BufSlow[i] = EMPTY_VALUE;
   BufFillRedA[i] = EMPTY_VALUE; BufFillRedB[i] = EMPTY_VALUE; BufFillLimeA[i] = EMPTY_VALUE; BufFillLimeB[i] = EMPTY_VALUE;
   BufBotSq[i] = EMPTY_VALUE; BufBotSqTop[i] = EMPTY_VALUE; BufBotSqBot[i] = EMPTY_VALUE;
   BufTopSq[i] = EMPTY_VALUE; BufTopSqTop[i] = EMPTY_VALUE; BufTopSqBot[i] = EMPTY_VALUE;
   BufBotTurn[i] = EMPTY_VALUE; BufBotTurnGap[i] = EMPTY_VALUE; BufTopTurn[i] = EMPTY_VALUE; BufTopTurnGap[i] = EMPTY_VALUE;
   BufBotTick[i] = EMPTY_VALUE; BufTopTick[i] = EMPTY_VALUE; BufState[i] = EMPTY_VALUE; BufPosW[i] = EMPTY_VALUE; BufArea[i] = EMPTY_VALUE;
   BufBotArmed[i] = EMPTY_VALUE; BufTopArmed[i] = EMPTY_VALUE;
   BufLegDir[i] = EMPTY_VALUE; BufLegDist[i] = EMPTY_VALUE; BufLegBars[i] = EMPTY_VALUE; BufLegEff[i] = EMPTY_VALUE;
   BufRSI[i] = EMPTY_VALUE; BufATR[i] = EMPTY_VALUE;
}
void ResetAll()
{
   g_rsi.Reset(); g_fast.Reset(); g_slow.Reset(); g_ext.Reset(); g_atr.Reset();
   lastBotBar = -10000; lastTopBar = -10000; lastBotWedge = -10000; lastTopWedge = -10000;
   nBotSq = 0; nTopSq = 0;
   botArmed = false; botArmBar = 0; topArmed = false; topArmBar = 0;
   nBotTurn = 0; nTopTurn = 0; lastBotGap = 0; lastTopGap = 0;
   nBotTk = 0; nTopTk = 0;
   legOpen = false; legDir = 0; legP0 = 0.0; legP0Ok = false; legB0 = 0; legPath = 0.0;
   leg1 = ShortToString(0x2014); leg2 = ShortToString(0x2014);          // "—"
   g_barIndex = -1; g_prevClose = 0.0; g_prevCloseOk = false;
   g_lastProcTime = 0; g_lastProcIdx = -1; g_lastProcColour = -1; g_lastProcChartIdx = -1;
   for(int k = 0; k < g_ringCap; k++)
   {
      g_rIsRed[k] = 0; g_rFast[k] = 0.0; g_rFastOk[k] = false; g_rSlow[k] = 0.0; g_rSlowOk[k] = false;
      g_rInLow[k] = false; g_rInHigh[k] = false; g_rTime[k] = 0;
   }
   g_tblIsRed = false; g_tblInLow = false; g_tblInHigh = false; g_tblPosW = 0.5;
   int n = ArraySize(BufFast);
   for(int i = 0; i < n; i++) ClearBar(i);
   ObjectsDeleteAll(0, g_prefix, -1, -1);
   ArrayResize(g_boxNames, 0); ArrayResize(g_labelNames, 0); ArrayResize(g_tableNames, 0);
   DumpReset();
   g_fullRecalcs++;
   if(g_fullRecalcs == 1 || g_fullRecalcs == 10 || g_fullRecalcs == 100 || g_fullRecalcs == 1000 || g_fullRecalcs % 10000 == 0)
      Print("XPW MAP v", XPW_VERSION, " full recalc #", g_fullRecalcs, " (prev_calculated==0): state reset, replay from bar 0");
}
void MeasureInterval(const datetime &time[], int rates_total)
{
   int n = MathMin(200, rates_total - 1);
   if(n < 1) { g_measuredInterval = 0; g_axisOk = false; return; }
   long d[];
   ArrayResize(d, n);
   for(int k = 0; k < n; k++) { int i = rates_total - 1 - k; d[k] = (long)time[i] - (long)time[i - 1]; }
   ArraySort(d);
   g_measuredInterval = (n % 2 == 1) ? d[n / 2] : (d[n / 2 - 1] + d[n / 2]) / 2;
   g_axisOk = (g_measuredInterval == g_expectedInterval);
}

//+------------------------------------------------------------------+
//| one confirmed bar                                                 |
//+------------------------------------------------------------------+
void ProcessBar(int i, const datetime &time[], const double &open[], const double &high[], const double &low[],
                const double &close[], const long &tick_volume[])
{
   double oo = open[i], hh = high[i], ll = low[i], cc = close[i];
   g_barIndex++;
   int bi = g_barIndex;
   int ri = bi % g_ringCap;

   // ---------------- TDI ----------------
   double r = 0.0, fast = 0.0, slow = 0.0;
   bool rOk    = g_rsi.Update(cc, r);
   bool fastOk = g_fast.Update(r, rOk, fast);
   bool slowOk = g_slow.Update(r, rOk, slow);
   bool both   = fastOk && slowOk;
   bool isRed  = invertFill ? (both && fast > slow) : (both && fast < slow);   // NA1

   // ---------------- AREAS ----------------
   double loW = 0.0, hiW = 0.0;
   bool   extOk = g_ext.Update(slow, slowOk, loW, hiW);
   double rngW = extOk ? (hiW - loW) : 0.0;
   double posW = 0.5;                                                          // NA9
   if(extOk && rngW > 0.0) posW = (slow - loW) / rngW;                         // slow is valid whenever the window is
   bool inLow  = (posW <= g_loFrac);
   bool inHigh = (posW >= g_hiFrac);
   g_rIsRed[ri] = isRed ? 1 : 0;
   g_rFast[ri] = fast; g_rFastOk[ri] = fastOk;
   g_rSlow[ri] = slow; g_rSlowOk[ri] = slowOk;
   g_rInLow[ri] = inLow; g_rInHigh[ri] = inHigh;
   g_rTime[ri] = time[i];

   // ---------------- WEDGES ----------------
   int  botWid = 0, topWid = 0;
   bool botRaw = Detect(true,  g_botMinW, g_botMaxW, g_botCtx, botWid);
   bool topRaw = Detect(false, g_topMinW, g_topMaxW, g_topCtx, topWid);
   bool botOK = botOn && botRaw && (!botNeedLow  || InLowAt(g_botCtx))  && (bi - lastBotBar >= g_botSep);
   bool topOK = topOn && topRaw && (!topNeedHigh || InHighAt(g_topCtx)) && (bi - lastTopBar >= g_topSep);
   double botSqTop = 0.0, botSqBot = 0.0, topSqTop = 0.0, topSqBot = 0.0;
   bool   botSqTopOk = false, botSqBotOk = false, topSqTopOk = false, topSqBotOk = false;
   if(botOK)
   {
      lastBotBar   = bi;
      lastBotWedge = bi - g_botCtx;
      nBotSq += 1;
      int lft = bi - g_botCtx - botWid + 1;
      int rgt = bi - g_botCtx;
      double h2 = -1e10, l2 = 1e10;
      bool hOk = true, lOk = true;
      for(int k = 0; k < botWid; k++)
      {
         double f = 0.0, s = 0.0, m = 0.0;
         bool fo = FastAt(g_botCtx + k, f), so = SlowAt(g_botCtx + k, s);
         bool mo = XpMax(f, fo, s, so, m);  hOk = XpMax(h2, hOk, m, mo, h2);
         mo = XpMin(f, fo, s, so, m);       lOk = XpMin(l2, lOk, m, mo, l2);
      }
      botSqTop = h2; botSqTopOk = hOk; botSqBot = l2; botSqBotOk = lOk;
      if(hOk && lOk)
      {
         string key = (string)(long)TimeAt(rgt);
         DrawBox(g_prefix + "SQB_" + key, lft, rgt, h2 + 1.5, l2 - 1.5, XPW_RED);
         // Pine: label bg red / white text; MQL5 text has no background -> text takes the label colour
         DrawText(g_subwin, g_prefix + "TGB_" + key, TimeAt(rgt), l2 - 2.0, "BOT " + (string)botWid, XPW_RED, ANCHOR_UPPER, "Arial", 7);
      }
   }
   if(topOK)
   {
      lastTopBar   = bi;
      lastTopWedge = bi - g_topCtx;
      nTopSq += 1;
      int lft = bi - g_topCtx - topWid + 1;
      int rgt = bi - g_topCtx;
      double h2 = -1e10, l2 = 1e10;
      bool hOk = true, lOk = true;
      for(int k = 0; k < topWid; k++)
      {
         double f = 0.0, s = 0.0, m = 0.0;
         bool fo = FastAt(g_topCtx + k, f), so = SlowAt(g_topCtx + k, s);
         bool mo = XpMax(f, fo, s, so, m);  hOk = XpMax(h2, hOk, m, mo, h2);
         mo = XpMin(f, fo, s, so, m);       lOk = XpMin(l2, lOk, m, mo, l2);
      }
      topSqTop = h2; topSqTopOk = hOk; topSqBot = l2; topSqBotOk = lOk;
      if(hOk && lOk)
      {
         string key = (string)(long)TimeAt(rgt);
         DrawBox(g_prefix + "SQT_" + key, lft, rgt, h2 + 1.5, l2 - 1.5, XPW_LIME);
         DrawText(g_subwin, g_prefix + "TGT_" + key, TimeAt(rgt), h2 + 2.0, "TOP " + (string)topWid, XPW_GREEN, ANCHOR_LOWER, "Arial", 7);
      }
   }

   // ---------------- TURN MARK ----------------
   if(botOK) { botArmed = true; botArmBar = bi; }
   if(topOK) { topArmed = true; topArmBar = bi; }
   if(botArmed && bi - botArmBar > g_turnMax) botArmed = false;
   if(topArmed && bi - topArmBar > g_turnMax) topArmed = false;
   bool holdUp = true, holdDn = true;
   for(int k = 0; k <= g_turnHold; k++)
   {
      if(!FastGtSlowAt(k)) holdUp = false;
      if(!FastLtSlowAt(k)) holdDn = false;
   }
   bool crossedUpAt = FastGtSlowAt(g_turnHold) && FastLeSlowAt(g_turnHold + 1);   // ta.crossover(fast, slow)[turnHold]
   bool crossedDnAt = FastLtSlowAt(g_turnHold) && FastGeSlowAt(g_turnHold + 1);   // ta.crossunder(fast, slow)[turnHold]
   bool botTurn = turnOn && botArmed && crossedUpAt && holdUp;
   bool topTurn = turnOn && topArmed && crossedDnAt && holdDn;
   int botGap = 0, topGap = 0;
   if(botTurn)
   {
      botArmed = false;
      nBotTurn += 1;
      int tb = bi - g_turnHold;
      lastBotGap = tb - lastBotWedge;
      botGap = lastBotGap;
      double f = 0.0, s = 0.0, y = 0.0;
      bool fo = FastAt(g_turnHold, f), so = SlowAt(g_turnHold, s);
      if(XpMin(f, fo, s, so, y))
         DrawText(g_subwin, g_prefix + "TNB_" + (string)(long)TimeAt(tb), TimeAt(tb), y - 3.0, ShortToString(0x25B2), XPW_YELLOW, ANCHOR_UPPER, "Arial", 8);
   }
   if(topTurn)
   {
      topArmed = false;
      nTopTurn += 1;
      int tb = bi - g_turnHold;
      lastTopGap = tb - lastTopWedge;
      topGap = lastTopGap;
      double f = 0.0, s = 0.0, y = 0.0;
      bool fo = FastAt(g_turnHold, f), so = SlowAt(g_turnHold, s);
      if(XpMax(f, fo, s, so, y))
         DrawText(g_subwin, g_prefix + "TNT_" + (string)(long)TimeAt(tb), TimeAt(tb), y + 3.0, ShortToString(0x25BC), XPW_ORANGE, ANCHOR_LOWER, "Arial", 8);
   }

   // ---------------- TICKS ----------------
   double atrV = 0.0;
   bool   atrOk = g_atr.Update(hh, ll, cc, atrV);
   double rngBar = hh - ll;
   double upWick = hh - MathMax(oo, cc);
   double dnWick = MathMin(oo, cc) - ll;
   bool atrPos = atrOk && atrV > 0.0;
   bool botTick = tickOn && rngBar > 0.0 && atrPos && dnWick / rngBar >= botWickRange && dnWick / atrV >= botWickAtr;
   bool topTick = tickOn && rngBar > 0.0 && atrPos && upWick / rngBar >= topWickRange && upWick / atrV >= topWickAtr;
   double botTickV = 0.0, topTickV = 0.0;
   if(botTick)
   {
      nBotTk += 1;
      botTickV = dnWick / atrV;
      DrawText(0, g_prefix + "TKB_" + (string)(long)time[i], time[i], ll, "BOT", XPW_YELLOW, ANCHOR_UPPER, "Arial", 7);
   }
   if(topTick)
   {
      nTopTk += 1;
      topTickV = upWick / atrV;
      DrawText(0, g_prefix + "TKT_" + (string)(long)time[i], time[i], hh, "TOP", XPW_ORANGE, ANCHOR_LOWER, "Arial", 7);
   }

   // ---------------- LEGS ----------------
   if(legOpen && g_prevCloseOk) legPath += MathAbs(cc - g_prevClose);
   int    legDirOut = 0, legBarsOut = 0;
   double legDistOut = 0.0, legEffOut = 0.0;
   bool   legClosed = false;
   if(botTurn || topTurn)
   {
      if(legOpen)
      {
         double dist = legP0Ok ? MathAbs(cc - legP0) : 0.0;
         int    bars = bi - legB0;
         double eff  = (legPath > 0.0) ? dist / legPath : 0.0;
         leg2 = leg1;
         leg1 = (legDir > 0 ? "UP " : "DN ") + Fmt2(dist) + " / " + (string)bars + "b / eff " + Fmt00(eff);
         legDirOut = legDir; legDistOut = dist; legBarsOut = bars; legEffOut = eff; legClosed = true;
      }
      legOpen = true;
      legDir  = botTurn ? 1 : -1;
      legP0   = cc; legP0Ok = true;
      legB0   = bi;
      legPath = 0.0;
   }
   g_prevClose = cc; g_prevCloseOk = true;

   // ---------------- buffers ----------------
   BufFast[i] = fastOk ? fast : EMPTY_VALUE;
   BufSlow[i] = slowOk ? slow : EMPTY_VALUE;
   BufRSI[i]  = rOk ? r : EMPTY_VALUE;
   BufATR[i]  = atrOk ? atrV : EMPTY_VALUE;
   if(both)
   {
      if(isRed) { BufFillRedA[i] = fast;  BufFillRedB[i] = slow; }
      else      { BufFillLimeA[i] = fast; BufFillLimeB[i] = slow; }
      int j = g_lastProcChartIdx;
      if(j >= 0 && g_lastProcColour >= 0 && g_lastProcColour != (isRed ? 1 : 0) && BufFast[j] != EMPTY_VALUE && BufSlow[j] != EMPTY_VALUE)
      {
         if(isRed) { BufFillRedA[j] = BufFast[j];  BufFillRedB[j] = BufSlow[j]; }
         else      { BufFillLimeA[j] = BufFast[j]; BufFillLimeB[j] = BufSlow[j]; }
      }
      g_lastProcColour = isRed ? 1 : 0;
   }
   else g_lastProcColour = -1;
   g_lastProcChartIdx = i;

   BufBotSq[i]      = botOK ? (double)botWid : 0.0;
   BufBotSqTop[i]   = (botOK && botSqTopOk) ? botSqTop : EMPTY_VALUE;
   BufBotSqBot[i]   = (botOK && botSqBotOk) ? botSqBot : EMPTY_VALUE;
   BufTopSq[i]      = topOK ? (double)topWid : 0.0;
   BufTopSqTop[i]   = (topOK && topSqTopOk) ? topSqTop : EMPTY_VALUE;
   BufTopSqBot[i]   = (topOK && topSqBotOk) ? topSqBot : EMPTY_VALUE;
   BufBotTurn[i]    = botTurn ? 1.0 : 0.0;
   BufBotTurnGap[i] = botTurn ? (double)botGap : EMPTY_VALUE;
   BufTopTurn[i]    = topTurn ? 1.0 : 0.0;
   BufTopTurnGap[i] = topTurn ? (double)topGap : EMPTY_VALUE;
   BufBotTick[i]    = botTick ? botTickV : 0.0;
   BufTopTick[i]    = topTick ? topTickV : 0.0;
   BufState[i]      = isRed ? 1.0 : 0.0;
   BufPosW[i]       = posW;
   BufArea[i]       = inLow ? -1.0 : (inHigh ? 1.0 : 0.0);
   BufBotArmed[i]   = botArmed ? 1.0 : 0.0;
   BufTopArmed[i]   = topArmed ? 1.0 : 0.0;
   BufLegDir[i]     = (double)legDirOut;
   BufLegDist[i]    = legClosed ? legDistOut : EMPTY_VALUE;
   BufLegBars[i]    = legClosed ? (double)legBarsOut : EMPTY_VALUE;
   BufLegEff[i]     = legClosed ? legEffOut : EMPTY_VALUE;

   g_tblIsRed = isRed; g_tblPosW = posW; g_tblInLow = inLow; g_tblInHigh = inHigh;

   if(DumpCSV)
   {
      string row = TimeToString(time[i], TIME_DATE | TIME_MINUTES | TIME_SECONDS) + "," +
                   DoubleToString(oo, 8) + "," + DoubleToString(hh, 8) + "," + DoubleToString(ll, 8) + "," + DoubleToString(cc, 8) + "," +
                   (string)tick_volume[i] + "," +
                   (string)(botOK ? botWid : 0) + "," + DumpNum(botSqTop, botOK && botSqTopOk) + "," + DumpNum(botSqBot, botOK && botSqBotOk) + "," +
                   (string)(topOK ? topWid : 0) + "," + DumpNum(topSqTop, topOK && topSqTopOk) + "," + DumpNum(topSqBot, topOK && topSqBotOk) + "," +
                   (string)(botTurn ? 1 : 0) + "," + (botTurn ? (string)botGap : "na") + "," +
                   (string)(topTurn ? 1 : 0) + "," + (topTurn ? (string)topGap : "na") + "," +
                   DumpNum(botTickV, botTick) + "," + DumpNum(topTickV, topTick) + "," +
                   (string)(isRed ? 1 : 0) + "," + DoubleToString(posW, 8) + "," + (string)(inLow ? -1 : (inHigh ? 1 : 0)) + "," +
                   (string)(botArmed ? 1 : 0) + "," + (string)(topArmed ? 1 : 0) + "," +
                   (string)legDirOut + "," + DumpNum(legDistOut, legClosed) + "," + (legClosed ? (string)legBarsOut : "na") + "," + DumpNum(legEffOut, legClosed) + "," +
                   DumpNum(r, rOk) + "," + DumpNum(fast, fastOk) + "," + DumpNum(slow, slowOk) + "," + DumpNum(atrV, atrOk) + "," + (string)bi;
      DumpRow(row);
   }
}

//+------------------------------------------------------------------+
//| forming-bar preview (fast/slow lines, fill, table header cells)   |
//| Recomputed from a COPY of the confirmed calculators on every tick,|
//| as TradingView redraws the realtime bar. Consumption buffers of   |
//| forming bars stay EMPTY_VALUE; confirmed bars are never touched   |
//| (the only write into the last closed bar is the fill bridge).     |
//+------------------------------------------------------------------+
void PreviewBars(int from, int to, const double &close[], const long &tick_volume[])
{
   g_rsiP.CopyFrom(g_rsi);
   g_fastP.CopyFrom(g_fast);
   g_slowP.CopyFrom(g_slow);
   g_extP.CopyFrom(g_ext);
   int j = g_lastProcChartIdx;
   int prevColour = g_lastProcColour;
   if(j >= 0)
   {
      bool jOk = (BufFast[j] != EMPTY_VALUE && BufSlow[j] != EMPTY_VALUE);
      BufFillRedA[j]  = (jOk && prevColour == 1) ? BufFast[j] : EMPTY_VALUE;
      BufFillRedB[j]  = (jOk && prevColour == 1) ? BufSlow[j] : EMPTY_VALUE;
      BufFillLimeA[j] = (jOk && prevColour == 0) ? BufFast[j] : EMPTY_VALUE;
      BufFillLimeB[j] = (jOk && prevColour == 0) ? BufSlow[j] : EMPTY_VALUE;
   }
   int prevIdx = j;
   for(int i = from; i <= to; i++)
   {
      if(SkipEmptyBars && tick_volume[i] == 0) continue;
      double r = 0.0, fast = 0.0, slow = 0.0, loW = 0.0, hiW = 0.0;
      bool rOk    = g_rsiP.Update(close[i], r);
      bool fastOk = g_fastP.Update(r, rOk, fast);
      bool slowOk = g_slowP.Update(r, rOk, slow);
      bool both   = fastOk && slowOk;
      bool isRed  = invertFill ? (both && fast > slow) : (both && fast < slow);
      bool extOk  = g_extP.Update(slow, slowOk, loW, hiW);
      double posW = 0.5;
      if(extOk && hiW - loW > 0.0) posW = (slow - loW) / (hiW - loW);
      BufRSI[i]  = rOk ? r : EMPTY_VALUE;
      BufFast[i] = fastOk ? fast : EMPTY_VALUE;
      BufSlow[i] = slowOk ? slow : EMPTY_VALUE;
      int colour = -1;
      if(both)
      {
         colour = isRed ? 1 : 0;
         if(isRed) { BufFillRedA[i] = fast;  BufFillRedB[i] = slow; }
         else      { BufFillLimeA[i] = fast; BufFillLimeB[i] = slow; }
         if(prevIdx >= 0 && prevColour >= 0 && prevColour != colour && BufFast[prevIdx] != EMPTY_VALUE && BufSlow[prevIdx] != EMPTY_VALUE)
         {
            if(isRed) { BufFillRedA[prevIdx] = BufFast[prevIdx];  BufFillRedB[prevIdx] = BufSlow[prevIdx]; }
            else      { BufFillLimeA[prevIdx] = BufFast[prevIdx]; BufFillLimeB[prevIdx] = BufSlow[prevIdx]; }
         }
      }
      prevColour = colour;
      prevIdx = i;
      // the Pine table reads isRed / posW / inLow / inHigh on the realtime bar
      g_tblIsRed = isRed; g_tblPosW = posW; g_tblInLow = (posW <= g_loFrac); g_tblInHigh = (posW >= g_hiFrac);
   }
}
//+------------------------------------------------------------------+
int OnInit()
{
   g_rsiLen   = ClampInt(rsiLen, 2, "rsiLen");
   g_fastLen  = ClampInt(fastLen, 1, "fastLen");
   g_slowLen  = ClampInt(slowLen, 1, "slowLen");
   g_areaLook = ClampInt(areaLook, 5, "areaLook");
   g_loFrac   = ClampDbl(loFrac, 0.0, 1.0, "loFrac");
   g_hiFrac   = ClampDbl(hiFrac, 0.0, 1.0, "hiFrac");
   g_botMinW  = ClampInt(botMinW, 1, "botMinW");
   g_botMaxW  = ClampInt(botMaxW, 1, "botMaxW");
   g_botCtx   = ClampInt(botCtx, 1, "botCtx");
   g_botSep   = ClampInt(botSep, 0, "botSep");
   g_topMinW  = ClampInt(topMinW, 1, "topMinW");
   g_topMaxW  = ClampInt(topMaxW, 1, "topMaxW");
   g_topCtx   = ClampInt(topCtx, 1, "topCtx");
   g_topSep   = ClampInt(topSep, 0, "topSep");
   g_turnMax  = ClampInt(turnMax, 1, "turnMax");
   g_turnHold = ClampInt(turnHold, 1, "turnHold");
   g_atrLen   = ClampInt(atrLen, 2, "atrLen");

   g_digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_point    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(g_tickSize <= 0.0) g_tickSize = g_point;
   g_expectedInterval = ParseExpectedInterval(_Symbol);

   SetIndexBuffer(0,  BufFast,       INDICATOR_DATA);
   SetIndexBuffer(1,  BufSlow,       INDICATOR_DATA);
   SetIndexBuffer(2,  BufFillRedA,   INDICATOR_DATA);
   SetIndexBuffer(3,  BufFillRedB,   INDICATOR_DATA);
   SetIndexBuffer(4,  BufFillLimeA,  INDICATOR_DATA);
   SetIndexBuffer(5,  BufFillLimeB,  INDICATOR_DATA);
   SetIndexBuffer(6,  BufBotSq,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(7,  BufBotSqTop,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(8,  BufBotSqBot,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(9,  BufTopSq,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(10, BufTopSqTop,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(11, BufTopSqBot,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(12, BufBotTurn,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(13, BufBotTurnGap, INDICATOR_CALCULATIONS);
   SetIndexBuffer(14, BufTopTurn,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(15, BufTopTurnGap, INDICATOR_CALCULATIONS);
   SetIndexBuffer(16, BufBotTick,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(17, BufTopTick,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(18, BufState,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(19, BufPosW,       INDICATOR_CALCULATIONS);
   SetIndexBuffer(20, BufArea,       INDICATOR_CALCULATIONS);
   SetIndexBuffer(21, BufBotArmed,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(22, BufTopArmed,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(23, BufLegDir,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(24, BufLegDist,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(25, BufLegBars,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(26, BufLegEff,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(27, BufRSI,        INDICATOR_CALCULATIONS);
   SetIndexBuffer(28, BufATR,        INDICATOR_CALCULATIONS);
   for(int p = 0; p < 4; p++) PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, 0, XPW_RED);
   PlotIndexSetInteger(2, PLOT_LINE_COLOR, 1, XPW_RED);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 0, XPW_LIME);
   PlotIndexSetInteger(3, PLOT_LINE_COLOR, 1, XPW_LIME);
   IndicatorSetString(INDICATOR_SHORTNAME, "XPW Shape Map v0.5");
   IndicatorSetInteger(INDICATOR_DIGITS, 2);
   IndicatorSetDouble(INDICATOR_MINIMUM, 0.0);
   IndicatorSetDouble(INDICATOR_MAXIMUM, 100.0);

   g_rsi.Init(g_rsiLen); g_fast.Init(g_fastLen); g_slow.Init(g_slowLen); g_ext.Init(g_areaLook); g_atr.Init(g_atrLen);

   int need = MathMax(2 * g_botCtx + MathMax(g_botMinW, g_botMaxW), 2 * g_topCtx + MathMax(g_topMinW, g_topMaxW));
   need = MathMax(need, g_turnHold + 2) + 8;
   g_ringCap = MathMax(64, need);
   ArrayResize(g_rIsRed, g_ringCap); ArrayResize(g_rFast, g_ringCap); ArrayResize(g_rFastOk, g_ringCap);
   ArrayResize(g_rSlow, g_ringCap);  ArrayResize(g_rSlowOk, g_ringCap);
   ArrayResize(g_rInLow, g_ringCap); ArrayResize(g_rInHigh, g_ringCap); ArrayResize(g_rTime, g_ringCap);

   g_prefix = "XPWMAP5_" + (string)ChartID() + "_";
   g_subwin = ChartWindowFind();
   g_initPrinted = false;
   g_fullRecalcs = 0;
   ResetAll();
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason)
{
   DumpFlush();
   ObjectsDeleteAll(0, g_prefix, -1, -1);
   ChartRedraw();
}
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
{
   if(rates_total < 1) return 0;
   if(g_subwin < 0) g_subwin = ChartWindowFind();
   if(prev_calculated == 0 && g_lastProcTime != 0) ResetAll();

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
   for(int i = i0; i < rates_total; i++) ClearBar(i);
   bool any = false;
   for(int i = i0; i <= lastClosed; i++)
   {
      if(time[i] <= g_lastProcTime) continue;
      if(!(SkipEmptyBars && tick_volume[i] == 0))
         ProcessBar(i, time, open, high, low, close, tick_volume);
      g_lastProcTime = time[i];
      g_lastProcIdx  = i;
      any = true;
   }
   if(any) DumpFlush();
   if(lastClosed + 1 <= rates_total - 1)
      PreviewBars(MathMax(lastClosed + 1, 0), rates_total - 1, close, tick_volume);   // realtime bar moves with every tick
   UpdateTable();
   ChartRedraw();
   return rates_total;
}
//+------------------------------------------------------------------+
