//+------------------------------------------------------------------+
//|                                   FlashGold_Direction_Filter.mq5 |
//+------------------------------------------------------------------+
// ============================================================================
//  FLASHGOLD DIRECTION FILTER  -  v1.0  (MetaTrader 5 port)
// ----------------------------------------------------------------------------
//  Port of the TradingView indicator "FlashGold Direction Filter" v1.0
//  (flashgold_direction_filter.pine). Same inputs, same defaults, same
//  FlashGold v5 signal math, same permission rule, same timing.
//
//  THE RULE
//    Each FlashGold v5 signal (BUY or SELL) sets the LEVEL = the signal price.
//      BUYS  are allowed only while price is ABOVE the level.
//      SELLS are allowed only while price is BELOW the level.
//    One level for both sides, whichever signal set it. The next signal
//    replaces it. Before the first signal nothing is allowed.
//    Level = Entry price (default): ask + entry distance for a BUY, bid -
//    entry distance for a SELL (where the strategy put its stop order).
//    Right after a BUY signal price is still below that level, so buys wait
//    for the break above it and sells are allowed below it (the mirror after
//    a SELL). "Signal close" uses the close of the signal candle instead.
//
//  FILTER TIMEFRAME (default H1)
//    The signal runs on H1 candles whatever the chart: on an M1 chart, or in
//    an M1 EA, you get what the H1 chart shows at that moment. A signal
//    counts when its H1 candle closes (only closed candles are read, so
//    nothing repaints); price is compared to the level at every chart bar.
//    "current" = the chart's own timeframe.
//
//  CHECK PRICE ON (when price is compared to the level)
//    Tick (default)  The live price, on every tick: a buy is allowed the
//                    moment price trades above the level. Closed candles keep
//                    the answer of their last tick (their close, at their
//                    close time).
//    Candle open     Each candle's OPEN, at its open time. Decided on the
//                    candle's first tick and fixed for the whole candle.
//    Candle close    Each candle's CLOSE, at its close time. While a candle
//                    is forming, the last closed candle's answer stays in
//                    force; the candle gets its own answer when it closes.
//    The signal in force is judged at the same moment: in Candle open, an H1
//    signal counts from the first candle that opens at or after its H1 close.
//    Candle open and Candle close never change inside a candle.
//
//  OUTPUT BUFFERS (Data Window, iCustom + CopyBuffer)
//    0  FGF buy allowed    1 when a buy may be taken on this bar, else 0
//    1  FGF sell allowed   1 when a sell may be taken on this bar, else 0
//    2  FGF active         1 while a signal's permission is in force
//    3  FGF level          the level in force
//    4  FGF signal         1 / -1 on the bar a BUY / SELL signal becomes known
//    5  FGF ended          1 on the bar a Minutes / Candles permission ends
//    6..8                  chart arrows (buy signal, sell signal, ended)
//
//  USE IT IN AN EA
//    Copy this file to MQL5\Indicators and compile it (F7). In the EA:
//        int fgf = iCustom(_Symbol, _Period, "FlashGold_Direction_Filter");
//    Read the bar that matches "Check price on":
//        Tick          shift 0, on every tick (the answer right now)
//        Candle open   shift 0 (fixed from the candle's first tick)
//        Candle close  shift 1 on each new bar (the candle that just closed);
//                      shift 0 gives the same answer until the candle closes
//        int shift = 0;   // 1 for Candle close on a new bar
//        double b[1], s[1];
//        if(CopyBuffer(fgf, 0, shift, 1, b) == 1 && CopyBuffer(fgf, 1, shift, 1, s) == 1)
//          {
//           if(myBuySignal  && b[0] == 1.0) { /* open the buy  */ }
//           if(mySellSignal && s[0] == 1.0) { /* open the sell */ }
//          }
//    Exits are never gated. iCustom with no extra parameters uses the
//    defaults below; to change them, edit the defaults and recompile, or pass
//    the inputs to iCustom in order.
//
//  WHAT CANNOT BE IDENTICAL TO TRADINGVIEW (the logic is; the data is not)
//    - Prices: your broker's MT5 candles vs TradingView's feed. Different
//      candles give different RSI / ATR, so signals can differ. The same
//      broker feed on both platforms gives the closest match.
//    - H2 / H4 / D1 candles: MT5 builds them on the broker's server clock,
//      TradingView on the exchange's, so the H2 / H4 zones can read
//      different candles.
//    - Point size: "Point size" (group "MT5") = TradingView's
//      syminfo.mintick; 0 = this symbol's _Point. It scales the spread model
//      (25 pts) and the Points-unit distances.
//    - History start: RSI / ATR warm up from the first loaded candle on both
//      platforms ("Warm-up candles"); after a few hundred candles they agree.
//    - Seconds timeframes do not exist in MT5 (the defaults use none).
//    - Visuals: MT5 has no transparency, so the shading colours are blended
//      with the chart background; labels are one line; the status box is
//      drawn with objects; signal marks are arrows; the "ended" cross sits
//      above the bar instead of at the top of the chart.
//    - Clock: TradingView's real clock is the trade server time here, and
//      the status box shows server time instead of the exchange time zone.
// ============================================================================
#property copyright   "FlashGold Direction Filter"
#property version     "1.00"
#property description "FlashGold v5 entry signal as a buy / sell permission:"
#property description "buys only above the signal level, sells only below it."
#property indicator_chart_window
#property indicator_buffers 9
#property indicator_plots   9

#property indicator_label1  "FGF buy allowed"
#property indicator_type1   DRAW_NONE
#property indicator_label2  "FGF sell allowed"
#property indicator_type2   DRAW_NONE
#property indicator_label3  "FGF active"
#property indicator_type3   DRAW_NONE
#property indicator_label4  "FGF level"
#property indicator_type4   DRAW_NONE
#property indicator_label5  "FGF signal (1 buy, -1 sell)"
#property indicator_type5   DRAW_NONE
#property indicator_label6  "FGF ended"
#property indicator_type6   DRAW_NONE
#property indicator_label7  "FGF buy signal"
#property indicator_type7   DRAW_ARROW
#property indicator_color7  C'0,230,118'
#property indicator_width7  1
#property indicator_label8  "FGF sell signal"
#property indicator_type8   DRAW_ARROW
#property indicator_color8  C'242,54,69'
#property indicator_width8  1
#property indicator_label9  "FGF permission ended"
#property indicator_type9   DRAW_ARROW
#property indicator_color9  C'255,152,0'
#property indicator_width9  1

//--- choices
enum ENUM_FGF_LEVEL
  {
   FGF_LEVEL_ENTRY = 0, // Entry price
   FGF_LEVEL_CLOSE = 1  // Signal close
  };
enum ENUM_FGF_LASTS
  {
   FGF_LASTS_NEXT    = 0, // Until next signal
   FGF_LASTS_MINUTES = 1, // Minutes
   FGF_LASTS_CANDLES = 2  // Candles
  };
enum ENUM_FGF_CHECK
  {
   FGF_CHECK_TICK  = 0, // Tick
   FGF_CHECK_OPEN  = 1, // Candle open
   FGF_CHECK_CLOSE = 2  // Candle close
  };
enum ENUM_FGF_UNIT
  {
   FGF_UNIT_ATR    = 0, // ATR
   FGF_UNIT_POINTS = 1  // Points
  };
enum ENUM_FGF_POS
  {
   FGF_POS_TOP_RIGHT     = 0, // top_right
   FGF_POS_MIDDLE_RIGHT  = 1, // middle_right
   FGF_POS_BOTTOM_RIGHT  = 2, // bottom_right
   FGF_POS_TOP_LEFT      = 3, // top_left
   FGF_POS_MIDDLE_LEFT   = 4, // middle_left
   FGF_POS_BOTTOM_LEFT   = 5, // bottom_left
   FGF_POS_TOP_CENTER    = 6, // top_center
   FGF_POS_BOTTOM_CENTER = 7  // bottom_center
  };

//--- inputs (same names, order and defaults as the TradingView script)
input group "Direction filter"
input bool               InpOn        = true;              // Enable filter
input ENUM_TIMEFRAMES    InpTf        = PERIOD_H1;         // Filter timeframe (current = chart)
input ENUM_FGF_LEVEL     InpLvMode    = FGF_LEVEL_ENTRY;   // Level
input ENUM_FGF_LASTS     InpLast      = FGF_LASTS_NEXT;    // Permission lasts
input int                InpMinutes   = 60;                // Minutes
input int                InpBars      = 1;                 // Candles
input ENUM_FGF_CHECK     InpCheck     = FGF_CHECK_TICK;    // Check price on
input bool               InpAllowBuy  = true;              // Allow buys
input bool               InpAllowSell = true;              // Allow sells
input bool               InpShowBg    = true;              // Shade
input bool               InpShowLv    = true;              // Level line
input bool               InpSigMark   = true;              // Signal marks
input bool               InpShowTbl   = true;              // Status box
input ENUM_FGF_POS       InpTblPos    = FGF_POS_TOP_RIGHT; // Status box position

input group "FlashGold signal: core"
input double InpSpreadPts    = 25.0; // Spread pts
input double InpEntryDistPts = 50.0; // Entry distance pts (Points unit)
input int    InpHoldBars     = 0;    // Entry hold bars
input double InpHoldFavPts   = 5.0;  // Hold min favorable pts (Points unit)
input bool   InpOnePerBar    = true; // One signal per bar

input group "FlashGold signal: burst / direction"
input ENUM_FGF_UNIT InpDistUnit     = FGF_UNIT_ATR; // Burst / entry distance / hold unit
input double        InpBurstAtr     = 0.5;          // Burst threshold, ATR mult (ATR unit)
input double        InpEntryDistAtr = 0.25;         // Entry distance, ATR mult (ATR unit)
input double        InpHoldFavAtr   = 0.1;          // Hold min favorable, ATR mult (ATR unit)
input double        InpBurstPts     = 172.0;        // Burst threshold pts (Points unit)
input bool          InpUseBurst     = true;         // Require burst gate
input bool          InpAnyCombo     = false;        // Allow any combo
input int           InpDriftBars    = 60;           // Prior drift bars
input bool          InpUseDrift     = false;        // Use prior drift filter

input group "FlashGold signal: TDI trade zone"
input bool            InpUseZones   = true;      // Use TDI trade-zone filter
input ENUM_TIMEFRAMES InpParentTf   = PERIOD_H1; // Parent obedience timeframe
input int             InpRsiLen     = 14;        // TDI RSI length
input int             InpFastLen    = 2;         // TDI white fast length
input int             InpMinAligned = 2;         // Minimum child zones aligned
input bool            InpFlatParent = false;     // Allow trade if parent is flat
input bool            InpIgnoreNa   = true;      // Ignore zones without data
input bool            InpHtfClosed  = true;      // Higher-TF zones use the last CLOSED bar
input bool            InpUseZ1      = true;      // Use child zone 1
input ENUM_TIMEFRAMES InpZTf1       = PERIOD_H1; // Zone 1 timeframe
input bool            InpUseZ2      = true;      // Use child zone 2
input ENUM_TIMEFRAMES InpZTf2       = PERIOD_H2; // Zone 2 timeframe
input bool            InpUseZ3      = true;      // Use child zone 3
input ENUM_TIMEFRAMES InpZTf3       = PERIOD_H4; // Zone 3 timeframe
input bool            InpUseZ4      = false;     // Use child zone 4
input ENUM_TIMEFRAMES InpZTf4       = PERIOD_H8; // Zone 4 timeframe
input bool            InpUseZ5      = false;     // Use child zone 5
input ENUM_TIMEFRAMES InpZTf5       = PERIOD_M1; // Zone 5 timeframe
input bool            InpUseZ6      = false;     // Use child zone 6
input ENUM_TIMEFRAMES InpZTf6       = PERIOD_M2; // Zone 6 timeframe

input group "MT5"
input double InpTickSize = 0.0;   // Point size (0 = symbol point) = TradingView syminfo.mintick
input int    InpMaxBars  = 20000; // Chart bars to calculate (0 = all)
input int    InpWarmup   = 500;   // Warm-up candles loaded before the first chart bar

//--- constants
#define FGF_NA        INT_MIN           // Pine na for int values
#define FGF_ROWS      7                 // status box rows
#define FGF_FONT      "Arial"
#define FGF_FONT_SIZE 9
#define FGF_WHITE     C'255,255,255'    // Pine color.white
#define FGF_LIME      C'0,230,118'      // Pine color.lime
#define FGF_RED       C'242,54,69'      // Pine color.red
#define FGF_GREEN     C'76,175,80'      // Pine color.green
#define FGF_GRAY      C'120,123,134'    // Pine color.gray
#define FGF_ORANGE    C'255,152,0'      // Pine color.orange
#define FGF_YELLOW    C'255,235,59'     // Pine color.yellow

int IMin(const int a, const int b) { return a < b ? a : b; }
int IMax(const int a, const int b) { return a > b ? a : b; }

// Close time of a candle (Pine time_close).
datetime BarClose(const ENUM_TIMEFRAMES tf, const datetime openTime)
  {
   if(tf == PERIOD_MN1)
     {
      MqlDateTime d;
      TimeToStruct(openTime, d);
      d.mon++;
      if(d.mon > 12)
        {
         d.mon = 1;
         d.year++;
        }
      d.day  = 1;
      d.hour = 0;
      d.min  = 0;
      d.sec  = 0;
      return StructToTime(d);
     }
   return openTime + PeriodSeconds(tf);
  }

//+------------------------------------------------------------------+
//| One timeframe: its candles and the TDI direction / ATR series,   |
//| computed exactly as Pine's ta.rsi, ta.sma and ta.atr.            |
//+------------------------------------------------------------------+
class CTf
  {
public:
   ENUM_TIMEFRAMES   tf;
   int               n;
   datetime          t[];    // open time
   datetime          tc[];   // close time
   double            h[];
   double            l[];
   double            c[];
   double            rUp[];  // RSI RMA of up moves   (EMPTY_VALUE = na)
   double            rDn[];  // RSI RMA of down moves (EMPTY_VALUE = na)
   double            rsi[];  // ta.rsi(close, InpRsiLen)
   double            fast[]; // ta.sma(rsi, InpFastLen)
   int               dir[];  // fast rising = 1, falling = -1, else 0
   double            atr[];  // ta.atr(14)

                     CTf(void) : tf(PERIOD_CURRENT), n(0) {}
   int               Load(const datetime from, const bool reset);
   void              Calc(const int from);
   int               LastClosedBy(const datetime x) const;
   int               LastOpenBy(const datetime x) const;

private:
   void              Resize(const int size);
  };

void CTf::Resize(const int size)
  {
   ArrayResize(t, size, 1000);
   ArrayResize(tc, size, 1000);
   ArrayResize(h, size, 1000);
   ArrayResize(l, size, 1000);
   ArrayResize(c, size, 1000);
   ArrayResize(rUp, size, 1000);
   ArrayResize(rDn, size, 1000);
   ArrayResize(rsi, size, 1000);
   ArrayResize(fast, size, 1000);
   ArrayResize(dir, size, 1000);
   ArrayResize(atr, size, 1000);
  }

// Loads the candles from 'from' (reset) or refreshes the last one and adds
// the new ones. Returns the first index that changed, -1 when the data is not
// ready yet, -2 when the history changed (start over).
int CTf::Load(const datetime from, const bool reset)
  {
   MqlRates r[];
   int first = 0;
   int got   = 0;
   if(reset || n == 0)
     {
      got = CopyRates(_Symbol, tf, from, TimeCurrent(), r);
      if(got <= 0)
         return -1;
      first = 0;
     }
   else
     {
      got = CopyRates(_Symbol, tf, t[n - 1], TimeCurrent(), r);
      if(got <= 0)
         return -1;
      if(r[0].time != t[n - 1])
         return -2;
      first = n - 1;
     }
   Resize(first + got);
   for(int i = 0; i < got; i++)
     {
      t[first + i]  = r[i].time;
      tc[first + i] = BarClose(tf, r[i].time);
      h[first + i]  = r[i].high;
      l[first + i]  = r[i].low;
      c[first + i]  = r[i].close;
     }
   n = first + got;
   return first;
  }

void CTf::Calc(const int from)
  {
   double ra = 1.0 / InpRsiLen;
   double aa = 1.0 / 14.0;
   for(int i = from; i < n; i++)
     {
      // ta.rsi: the change is na on the first candle, so the RMA starts on
      // candle InpRsiLen with the SMA of the first InpRsiLen changes.
      rUp[i] = EMPTY_VALUE;
      rDn[i] = EMPTY_VALUE;
      rsi[i] = EMPTY_VALUE;
      if(i >= InpRsiLen)
        {
         if(rUp[i - 1] == EMPTY_VALUE)
           {
            double su = 0.0, sd = 0.0;
            for(int j = i - InpRsiLen + 1; j <= i; j++)
              {
               su += MathMax(c[j] - c[j - 1], 0.0);
               sd += MathMax(c[j - 1] - c[j], 0.0);
              }
            rUp[i] = su / InpRsiLen;
            rDn[i] = sd / InpRsiLen;
           }
         else
           {
            rUp[i] = ra * MathMax(c[i] - c[i - 1], 0.0) + (1.0 - ra) * rUp[i - 1];
            rDn[i] = ra * MathMax(c[i - 1] - c[i], 0.0) + (1.0 - ra) * rDn[i - 1];
           }
         rsi[i] = rDn[i] == 0.0 ? 100.0 : (rUp[i] == 0.0 ? 0.0 : 100.0 - 100.0 / (1.0 + rUp[i] / rDn[i]));
        }
      // fast line = ta.sma(rsi, InpFastLen)
      fast[i] = EMPTY_VALUE;
      if(i - InpFastLen + 1 >= 0)
        {
         double s  = 0.0;
         bool   ok = true;
         for(int j = i - InpFastLen + 1; j <= i; j++)
           {
            if(rsi[j] == EMPTY_VALUE)
              {
               ok = false;
               break;
              }
            s += rsi[j];
           }
         if(ok)
            fast[i] = s / InpFastLen;
        }
      // direction: f > f[1] ? 1 : f < f[1] ? -1 : 0 (na compares false -> 0)
      dir[i] = 0;
      if(i >= 1 && fast[i] != EMPTY_VALUE && fast[i - 1] != EMPTY_VALUE)
         dir[i] = fast[i] > fast[i - 1] ? 1 : (fast[i] < fast[i - 1] ? -1 : 0);
      // ta.atr(14) = RMA of the true range (first candle: high - low)
      atr[i] = EMPTY_VALUE;
      if(i >= 13)
        {
         if(atr[i - 1] == EMPTY_VALUE)
           {
            double st = 0.0;
            for(int j = i - 13; j <= i; j++)
               st += j == 0 ? h[j] - l[j] : MathMax(MathMax(h[j] - l[j], MathAbs(h[j] - c[j - 1])), MathAbs(l[j] - c[j - 1]));
            atr[i] = st / 14.0;
           }
         else
           {
            double tr = MathMax(MathMax(h[i] - l[i], MathAbs(h[i] - c[i - 1])), MathAbs(l[i] - c[i - 1]));
            atr[i] = aa * tr + (1.0 - aa) * atr[i - 1];
           }
        }
     }
  }

// Latest candle whose close time is <= x (-1 if none).
int CTf::LastClosedBy(const datetime x) const
  {
   int lo = 0, hi = n - 1, res = -1;
   while(lo <= hi)
     {
      int mid = (lo + hi) / 2;
      if(tc[mid] <= x)
        {
         res = mid;
         lo  = mid + 1;
        }
      else
         hi = mid - 1;
     }
   return res;
  }

// Latest candle whose open time is <= x (-1 if none).
int CTf::LastOpenBy(const datetime x) const
  {
   int lo = 0, hi = n - 1, res = -1;
   while(lo <= hi)
     {
      int mid = (lo + hi) / 2;
      if(t[mid] <= x)
        {
         res = mid;
         lo  = mid + 1;
        }
      else
         hi = mid - 1;
     }
   return res;
  }

// request.security(tf, tdiDir(), lookahead_off) seen from a candle closing at
// ctxClose: the latest candle of tf closed by then (on the same timeframe,
// the candle itself; on a lower one, the last one inside the candle).
int DirOff(const CTf &T, const datetime ctxClose)
  {
   int j = T.LastClosedBy(ctxClose);
   return j >= 0 ? T.dir[j] : FGF_NA;
  }

// request.security(tf, tdiDir()[1], lookahead_on) seen from a candle opening
// at ctxOpen: the candle of tf before the one that contains ctxOpen (its last
// closed candle).
int DirPrevOn(const CTf &T, const datetime ctxOpen)
  {
   int j = T.LastOpenBy(ctxOpen);
   return j >= 1 ? T.dir[j - 1] : FGF_NA;
  }

//--- state of the FlashGold signal and of the arming after a filter candle
//    (the Pine 'var' variables)
struct FgState
  {
   bool              holdActive;
   bool              holdIsBuy;
   int               holdSignalBar;
   double            holdSignalMid;
   int               lastEntryBar;
   datetime          aAt;   // signal candle close (0 = na)
   int               aBar;  // signal candle index
   double            aPx;   // level (EMPTY_VALUE = na)
   int               aDir;  // 1 buy, -1 sell
   int               aId;   // signal count
   int               par;   // parent side of this candle
   int               al;    // aligned zones of this candle
   int               ac;    // active zones of this candle
  };

//--- last chart bar, for the status box
struct FgBar
  {
   bool              armed;
   bool              isOpen;
   datetime          endT;
   int               endBar;
   int               idx;
   double            value;
   double            level;
   int               sigDir;
   datetime          sigAt;
   bool              onSigBar;
   bool              atBuy;
   bool              atSell;
   int               par;
   int               al;
   int               ac;
  };

//--- buffers
double BufBuyOk[];
double BufSellOk[];
double BufActive[];
double BufLevel[];
double BufSignal[];
double BufEnded[];
double BufBuyArr[];
double BufSellArr[];
double BufEndArr[];

//--- globals
CTf             g_tf[8];
int             g_tfCount = 0;
int             g_fi = -1;          // filter timeframe
int             g_pi = -1;          // parent timeframe
int             g_zi[6];            // zone timeframes (-1 = zone off)
bool            g_zUse[6];
ENUM_TIMEFRAMES g_zTf[6];
ENUM_TIMEFRAMES g_fTf;
int             g_fSec = 0;
double          g_pt = 0.0;
int             g_digits = 0;
string          g_pfx = "";
string          g_tfTag = "";
bool            g_reset = false;
bool            g_waiting = false;  // data of a timeframe still loading
int             g_first = 0;
FgState         g_st[];
int             g_stN = 0;
int             g_sigId[];
bool            g_ended[];
int             g_from[];
int             g_shade[];
int             g_runStart[];
FgBar           g_last;
color           g_bgBuy, g_bgSell, g_bgNone, g_tblBg;
bool            g_tblOn = false;
string          g_tblTxt[FGF_ROWS][2];
color           g_tblClr[FGF_ROWS][2];

ENUM_TIMEFRAMES Resolve(const ENUM_TIMEFRAMES tf) { return tf == PERIOD_CURRENT ? Period() : tf; }

int AddTf(const ENUM_TIMEFRAMES tf)
  {
   for(int i = 0; i < g_tfCount; i++)
      if(g_tf[i].tf == tf)
         return i;
   g_tf[g_tfCount].tf = tf;
   g_tf[g_tfCount].n  = 0;
   return g_tfCount++;
  }

string TfText(const ENUM_TIMEFRAMES tf)
  {
   if(tf == PERIOD_MN1)
      return "M";
   if(tf == PERIOD_W1)
      return "W";
   if(tf == PERIOD_D1)
      return "D";
   int sec = PeriodSeconds(tf);
   if(sec < 3600)
      return IntegerToString(sec / 60) + "m";
   return IntegerToString(sec / 3600) + "H";
  }

int DigitsOf(const double v)
  {
   int d = 0;
   while(d < 8 && MathAbs(v * MathPow(10.0, d) - MathRound(v * MathPow(10.0, d))) > 1e-9)
      d++;
   return d;
  }

color Blend(const color bg, const color fg, const double a)
  {
   int b0 = (int)bg, f0 = (int)fg;
   int r  = (int)MathRound((b0 & 0xFF) * (1.0 - a) + (f0 & 0xFF) * a);
   int g  = (int)MathRound(((b0 >> 8) & 0xFF) * (1.0 - a) + ((f0 >> 8) & 0xFF) * a);
   int b  = (int)MathRound(((b0 >> 16) & 0xFF) * (1.0 - a) + ((f0 >> 16) & 0xFF) * a);
   return (color)(r | (g << 8) | (b << 16));
  }

// Pine colors with transparency, blended with the chart background.
void SetColors()
  {
   color bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   g_bgBuy  = Blend(bg, FGF_GREEN, 0.15); // color.new(color.green, 85)
   g_bgSell = Blend(bg, FGF_RED, 0.15);   // color.new(color.red, 85)
   g_bgNone = Blend(bg, FGF_GRAY, 0.12);  // color.new(color.gray, 88)
   g_tblBg  = Blend(bg, clrBlack, 0.80);  // color.new(color.black, 20)
  }

string FormatTime(const datetime x)
  {
   static const string mon[12] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
   MqlDateTime d;
   TimeToStruct(x, d);
   return mon[d.mon - 1] + " " + StringFormat("%02d %02d:%02d", d.day, d.hour, d.min);
  }

//+------------------------------------------------------------------+
//| FLASHGOLD SIGNAL (the strategy's logic, unchanged) and arming,    |
//| on filter candle k.                                               |
//+------------------------------------------------------------------+
double MidAt(const int j)
  {
   double halfSpread = InpSpreadPts * g_pt * 0.5;
   double bid = g_tf[g_fi].c[j] - halfSpread;
   double ask = g_tf[g_fi].c[j] + halfSpread;
   return (bid + ask) * 0.5;
  }

// Direction of a child zone. A zone on a timeframe HIGHER than the filter
// timeframe is read from its last closed candle (InpHtfClosed).
int ZoneDir(const int z, const int k)
  {
   int ti = g_zi[z];
   if(ti < 0)
      return FGF_NA;
   if(InpHtfClosed && PeriodSeconds(g_zTf[z]) > g_fSec)
      return DirPrevOn(g_tf[ti], g_tf[g_fi].t[k]);
   return DirOff(g_tf[ti], g_tf[g_fi].tc[k]);
  }

void StateInit(FgState &s)
  {
   s.holdActive    = false;
   s.holdIsBuy     = false;
   s.holdSignalBar = FGF_NA;
   s.holdSignalMid = EMPTY_VALUE;
   s.lastEntryBar  = FGF_NA;
   s.aAt           = 0;
   s.aBar          = FGF_NA;
   s.aPx           = EMPTY_VALUE;
   s.aDir          = 0;
   s.aId           = 0;
   s.par           = 0;
   s.al            = 0;
   s.ac            = 0;
  }

void CalcCandle(const int k)
  {
   FgState s;
   if(k > 0)
      s = g_st[k - 1];
   else
      StateInit(s);

   // price model
   double pt         = g_pt;
   double halfSpread = InpSpreadPts * pt * 0.5;
   double bid        = g_tf[g_fi].c[k] - halfSpread;
   double ask        = g_tf[g_fi].c[k] + halfSpread;
   double midPrice   = (bid + ask) * 0.5;

   // TDI trade zone
   int  parentDir = DirOff(g_tf[g_pi], g_tf[g_fi].tc[k]);
   int  zDir[6];
   bool zOn[6];
   int  activeZones = 0;
   for(int z = 0; z < 6; z++)
     {
      zDir[z] = ZoneDir(z, k);
      zOn[z]  = g_zUse[z] && (!InpIgnoreNa || zDir[z] != FGF_NA);
      if(zOn[z])
         activeZones++;
     }
   int parentSide = parentDir == FGF_NA ? 0 : (parentDir > 0 ? 1 : (parentDir < 0 ? -1 : 0));
   int alignedZones = 0;
   for(int z = 0; z < 6; z++)
      if(zOn[z] && parentSide != 0 && zDir[z] == parentSide)
         alignedZones++;

   int  requiredAligned   = IMin(InpMinAligned, activeZones);
   bool parentFlatAllowed = InpFlatParent && parentSide == 0;
   bool zoneReady         = activeZones == 0 || alignedZones >= requiredAligned;

   bool tradeZoneBuyAllowed  = !InpUseZones || ((parentSide == 1 || parentFlatAllowed) && zoneReady);
   bool tradeZoneSellAllowed = !InpUseZones || ((parentSide == -1 || parentFlatAllowed) && zoneReady);

   // burst / prior drift (Pine na = the *Ok flags false: every compare fails)
   bool   atrUnit      = InpDistUnit == FGF_UNIT_ATR;
   bool   thrOk        = !atrUnit || g_tf[g_fi].atr[k] != EMPTY_VALUE;
   double atrPts       = (atrUnit && thrOk) ? g_tf[g_fi].atr[k] / pt : 0.0;
   double burstThrPts  = atrUnit ? InpBurstAtr * atrPts : InpBurstPts;
   double entryDistPts = atrUnit ? InpEntryDistAtr * atrPts : InpEntryDistPts;
   double holdFavPts   = atrUnit ? InpHoldFavAtr * atrPts : InpHoldFavPts;

   bool   burstOk       = k >= 1;
   double burstPts      = burstOk ? (midPrice - MidAt(k - 1)) / pt : 0.0;
   bool   driftOk       = k >= InpDriftBars;
   double priorDriftPts = driftOk ? (midPrice - MidAt(k - InpDriftBars)) / pt : 0.0;

   bool burstBuy  = burstOk && thrOk && burstPts >= burstThrPts;
   bool burstSell = burstOk && thrOk && burstPts <= -burstThrPts;

   bool priorBuyOk  = !InpUseDrift || (driftOk && priorDriftPts > 0);
   bool priorSellOk = !InpUseDrift || (driftOk && priorDriftPts < 0);

   bool rawBuyCandidate  = InpAnyCombo ? (tradeZoneBuyAllowed && (!InpUseBurst || burstBuy || parentSide == 1)) : (tradeZoneBuyAllowed && burstBuy);
   bool rawSellCandidate = InpAnyCombo ? (tradeZoneSellAllowed && (!InpUseBurst || burstSell || parentSide == -1)) : (tradeZoneSellAllowed && burstSell);

   bool buyCandidate  = rawBuyCandidate && priorBuyOk;
   bool sellCandidate = rawSellCandidate && priorSellOk;

   // entry hold / virtual stop
   double buyEntryPrice  = EMPTY_VALUE;
   double sellEntryPrice = EMPTY_VALUE;
   bool   buySignal      = false;
   bool   sellSignal     = false;

   bool canFire = !InpOnePerBar || s.lastEntryBar == FGF_NA || s.lastEntryBar != k;

   if(buyCandidate && canFire)
     {
      if(InpHoldBars == 0)
        {
         buyEntryPrice  = thrOk ? ask + entryDistPts * pt : EMPTY_VALUE;
         buySignal      = true;
         s.lastEntryBar = k;
        }
      else if(!s.holdActive)
        {
         s.holdActive    = true;
         s.holdIsBuy     = true;
         s.holdSignalBar = k;
         s.holdSignalMid = midPrice;
        }
      else if(s.holdIsBuy)
        {
         int    elapsedBars    = k - s.holdSignalBar;
         double holdMovePoints = (midPrice - s.holdSignalMid) / pt;
         if(elapsedBars >= InpHoldBars && thrOk && holdMovePoints >= holdFavPts)
           {
            buyEntryPrice  = thrOk ? ask + entryDistPts * pt : EMPTY_VALUE;
            buySignal      = true;
            s.lastEntryBar = k;
            s.holdActive   = false;
           }
        }
     }

   if(sellCandidate && canFire)
     {
      if(InpHoldBars == 0)
        {
         sellEntryPrice = thrOk ? bid - entryDistPts * pt : EMPTY_VALUE;
         sellSignal     = true;
         s.lastEntryBar = k;
        }
      else if(!s.holdActive)
        {
         s.holdActive    = true;
         s.holdIsBuy     = false;
         s.holdSignalBar = k;
         s.holdSignalMid = midPrice;
        }
      else if(!s.holdIsBuy)
        {
         int    elapsedBars    = k - s.holdSignalBar;
         double holdMovePoints = (s.holdSignalMid - midPrice) / pt;
         if(elapsedBars >= InpHoldBars && thrOk && holdMovePoints >= holdFavPts)
           {
            sellEntryPrice = thrOk ? bid - entryDistPts * pt : EMPTY_VALUE;
            sellSignal     = true;
            s.lastEntryBar = k;
            s.holdActive   = false;
           }
        }
     }

   if(s.holdActive && ((s.holdIsBuy && !tradeZoneBuyAllowed) || (!s.holdIsBuy && !tradeZoneSellAllowed)))
     {
      s.holdActive    = false;
      s.holdSignalBar = FGF_NA;
      s.holdSignalMid = EMPTY_VALUE;
     }

   double signalPx = buySignal ? buyEntryPrice : (sellSignal ? sellEntryPrice : EMPTY_VALUE);

   // arming: a signal candle sets the level at its close; aId counts signals
   if(buySignal || sellSignal)
     {
      s.aAt  = g_tf[g_fi].tc[k];
      s.aBar = k;
      s.aPx  = InpLvMode == FGF_LEVEL_ENTRY ? (signalPx != EMPTY_VALUE ? signalPx : g_tf[g_fi].c[k]) : g_tf[g_fi].c[k];
      s.aDir = buySignal ? 1 : -1;
      s.aId++;
     }
   s.par = parentSide;
   s.al  = alignedZones;
   s.ac  = activeZones;
   g_st[k] = s;
  }

//+------------------------------------------------------------------+
//| Drawings                                                          |
//+------------------------------------------------------------------+
// Background shading (Pine bgcolor): one rectangle per run of bars with the
// same colour. s: 0 none, 1 buys allowed, 2 sells allowed, 3 neither.
void ShadeBar(const int i, const int s, const datetime &time[])
  {
   int    per = PeriodSeconds();
   int    sp  = i > g_first ? g_shade[i - 1] : 0;
   string own = g_pfx + "BG" + IntegerToString((long)time[i]);
   g_shade[i] = s;
   if(s != 0 && s == sp)
     {
      // same colour as the previous bar: extend its run
      ObjectDelete(0, own);
      g_runStart[i] = g_runStart[i - 1];
      string run = g_pfx + "BG" + IntegerToString((long)time[g_runStart[i]]);
      ObjectSetInteger(0, run, OBJPROP_TIME, 1, (long)(time[i] + per));
      return;
     }
   if(sp != 0)
     {
      // the previous run ends at the previous bar
      string prev = g_pfx + "BG" + IntegerToString((long)time[g_runStart[i - 1]]);
      ObjectSetInteger(0, prev, OBJPROP_TIME, 1, (long)(time[i - 1] + per));
     }
   g_runStart[i] = i;
   if(s == 0)
     {
      ObjectDelete(0, own);
      return;
     }
   if(ObjectFind(0, own) < 0)
     {
      ObjectCreate(0, own, OBJ_RECTANGLE, 0, time[i], 0.0, time[i] + per, 1.0e8);
      ObjectSetInteger(0, own, OBJPROP_FILL, true);
      ObjectSetInteger(0, own, OBJPROP_BACK, true);
      ObjectSetInteger(0, own, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, own, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, own, OBJPROP_WIDTH, 1);
     }
   else
      ObjectSetInteger(0, own, OBJPROP_TIME, 1, (long)(time[i] + per));
   ObjectSetInteger(0, own, OBJPROP_COLOR, s == 1 ? g_bgBuy : (s == 2 ? g_bgSell : g_bgNone));
  }

// Level line and label. Each signal keeps its own line and label, so past
// levels stay readable; the line grows while the permission is in force.
void LevelLine(const int i, const bool newSig, const bool armed, const bool isOpen, const double level, const int sigDir, const datetime &time[])
  {
   int from = i > g_first ? g_from[i - 1] : -1;
   if(newSig || (from < 0 && armed))
      from = i;
   g_from[i] = from;
   if(from < 0)
      return;
   string ln = g_pfx + "LN" + IntegerToString((long)time[from]);
   string lb = g_pfx + "LB" + IntegerToString((long)time[from]);
   if(InpShowLv && InpOn && isOpen && level != EMPTY_VALUE)
     {
      color clr = sigDir > 0 ? FGF_LIME : FGF_RED;
      if(ObjectFind(0, ln) < 0)
        {
         ObjectCreate(0, ln, OBJ_TREND, 0, time[from], level, time[i], level);
         ObjectSetInteger(0, ln, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, ln, OBJPROP_RAY_RIGHT, false);
         ObjectSetInteger(0, ln, OBJPROP_RAY_LEFT, false);
         ObjectSetInteger(0, ln, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, ln, OBJPROP_HIDDEN, true);
        }
      else
        {
         ObjectSetInteger(0, ln, OBJPROP_TIME, 1, (long)time[i]);
         ObjectSetDouble(0, ln, OBJPROP_PRICE, 0, level);
         ObjectSetDouble(0, ln, OBJPROP_PRICE, 1, level);
        }
      ObjectSetInteger(0, ln, OBJPROP_COLOR, clr);
      if(ObjectFind(0, lb) < 0)
        {
         string lasts = InpLast == FGF_LASTS_MINUTES ? IntegerToString(InpMinutes) + " min" :
                        (InpLast == FGF_LASTS_CANDLES ? IntegerToString(InpBars) + (InpBars == 1 ? " candle " : " candles ") + g_tfTag : "until next signal");
         string txt = (sigDir > 0 ? "BUY" : "SELL") + " signal " + g_tfTag + " @ " + DoubleToString(level, g_digits) + " | " + lasts;
         ObjectCreate(0, lb, OBJ_TEXT, 0, time[from], level);
         ObjectSetString(0, lb, OBJPROP_TEXT, txt);
         ObjectSetString(0, lb, OBJPROP_FONT, FGF_FONT);
         ObjectSetInteger(0, lb, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, lb, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lb, OBJPROP_ANCHOR, ANCHOR_RIGHT);
         ObjectSetInteger(0, lb, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, lb, OBJPROP_HIDDEN, true);
        }
     }
   else
      if(ObjectFind(0, ln) >= 0 && (datetime)ObjectGetInteger(0, ln, OBJPROP_TIME, 1) >= time[i])
        {
         // drawn on an earlier tick of this forming bar and no longer in
         // force: back to the previous bar, as Pine rolls the bar back
         if(from == i)
           {
            ObjectDelete(0, ln);
            ObjectDelete(0, lb);
           }
         else
            ObjectSetInteger(0, ln, OBJPROP_TIME, 1, (long)time[i - 1]);
        }
  }

void SetText(const string name, const int x, const int y, const string text, const color clr)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetString(0, name, OBJPROP_FONT, FGF_FONT);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, FGF_FONT_SIZE);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
  }

// Status box (Pine table): 2 columns x 7 rows at the chosen position.
void RenderTable()
  {
   string bg = g_pfx + "TBG";
   if(!g_tblOn)
     {
      ObjectDelete(0, bg);
      for(int r = 0; r < FGF_ROWS; r++)
         for(int c = 0; c < 2; c++)
            ObjectDelete(0, g_pfx + "TC" + IntegerToString(r) + "_" + IntegerToString(c));
      return;
     }
   TextSetFont(FGF_FONT, -FGF_FONT_SIZE * 10);
   uint w0 = 0, w1 = 0, th = 0, w = 0, hgt = 0;
   for(int r = 0; r < FGF_ROWS; r++)
     {
      TextGetSize(g_tblTxt[r][0], w, hgt);
      if(w > w0)
         w0 = w;
      if(hgt > th)
         th = hgt;
      TextGetSize(g_tblTxt[r][1], w, hgt);
      if(w > w1)
         w1 = w;
      if(hgt > th)
         th = hgt;
     }
   int pad  = 4;
   int c0   = (int)w0 + 2 * pad;
   int c1   = (int)w1 + 2 * pad;
   int rowH = (int)th + 4;
   int tw   = c0 + c1;
   int tht  = FGF_ROWS * rowH + 2;
   int cw   = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int ch   = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);
   int m    = 6;
   int x    = m, y = m;
   switch(InpTblPos)
     {
      case FGF_POS_TOP_RIGHT:
         x = cw - tw - m;
         y = m;
         break;
      case FGF_POS_MIDDLE_RIGHT:
         x = cw - tw - m;
         y = (ch - tht) / 2;
         break;
      case FGF_POS_BOTTOM_RIGHT:
         x = cw - tw - m;
         y = ch - tht - m;
         break;
      case FGF_POS_TOP_LEFT:
         x = m;
         y = m;
         break;
      case FGF_POS_MIDDLE_LEFT:
         x = m;
         y = (ch - tht) / 2;
         break;
      case FGF_POS_BOTTOM_LEFT:
         x = m;
         y = ch - tht - m;
         break;
      case FGF_POS_TOP_CENTER:
         x = (cw - tw) / 2;
         y = m;
         break;
      default:
         x = (cw - tw) / 2;
         y = ch - tht - m;
         break;
     }
   x = IMax(0, x);
   y = IMax(0, y);
   if(ObjectFind(0, bg) < 0)
     {
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE, tw);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE, tht);
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, g_tblBg);
   ObjectSetInteger(0, bg, OBJPROP_COLOR, g_tblBg);
   for(int r = 0; r < FGF_ROWS; r++)
     {
      SetText(g_pfx + "TC" + IntegerToString(r) + "_0", x + pad, y + 1 + r * rowH + 2, g_tblTxt[r][0], g_tblClr[r][0]);
      SetText(g_pfx + "TC" + IntegerToString(r) + "_1", x + c0 + pad, y + 1 + r * rowH + 2, g_tblTxt[r][1], g_tblClr[r][1]);
     }
  }

// Status box contents, judged by the real clock (display only; the gates
// never use it).
void UpdateTable(const datetime now)
  {
   g_tblOn = InpShowTbl && InpOn;
   if(!g_tblOn)
     {
      RenderTable();
      return;
     }
   FgBar  L      = g_last;
   bool   dOpen  = L.isOpen && !(InpCheck == FGF_CHECK_TICK && InpLast == FGF_LASTS_MINUTES && L.endT > 0 && now >= L.endT);
   bool   lvOk   = L.level != EMPTY_VALUE;
   bool   dBuy   = dOpen && InpAllowBuy && ((lvOk && L.value > L.level) || L.atBuy);
   bool   dSell  = dOpen && InpAllowSell && ((lvOk && L.value < L.level) || L.atSell);
   string dSide  = L.sigDir > 0 ? "BUY" : "SELL";
   string dState = !L.armed ? "WAITING FOR SIGNAL" : (dOpen ? "ACTIVE - " : "ENDED - ") + dSide + " signal";
   color  dCol   = !L.armed ? FGF_YELLOW : (dOpen ? FGF_LIME : FGF_ORANGE);
   int    dSecs  = (dOpen && L.endT > 0) ? IMax(0, (int)(L.endT - now)) : 0;
   string dLeft  = "-";
   if(dOpen)
     {
      if(InpLast == FGF_LASTS_MINUTES)
         dLeft = StringFormat("%02d:%02d", dSecs / 60, dSecs % 60);
      else
         if(InpLast == FGF_LASTS_CANDLES)
            dLeft = IntegerToString(L.endBar - L.idx) + (L.endBar - L.idx == 1 ? " candle " : " candles ") + g_tfTag;
         else
            dLeft = "until next signal";
     }
   string dLv    = lvOk ? DoubleToString(L.level, g_digits) : "-";
   string dSig   = L.sigAt == 0 ? "-" : dSide + " " + FormatTime(L.sigAt);
   string dPar   = L.par == FGF_NA ? "-" : (L.par > 0 ? "BUY" : (L.par < 0 ? "SELL" : "FLAT"));
   string dZones = L.ac == FGF_NA ? "-" : IntegerToString(L.al) + "/" + IntegerToString(L.ac);

   g_tblTxt[0][0] = "FG filter " + g_tfTag;
   g_tblClr[0][0] = FGF_WHITE;
   g_tblTxt[0][1] = dState;
   g_tblClr[0][1] = dCol;
   g_tblTxt[1][0] = "Signal (server)";
   g_tblClr[1][0] = FGF_WHITE;
   g_tblTxt[1][1] = dSig;
   g_tblClr[1][1] = L.sigDir > 0 ? FGF_LIME : (L.sigDir < 0 ? FGF_RED : FGF_WHITE);
   g_tblTxt[2][0] = "Left";
   g_tblClr[2][0] = FGF_WHITE;
   g_tblTxt[2][1] = dLeft;
   g_tblClr[2][1] = FGF_WHITE;
   g_tblTxt[3][0] = InpCheck == FGF_CHECK_OPEN ? "Candle open" : (InpCheck == FGF_CHECK_CLOSE ? "Last close" : "Price now");
   g_tblClr[3][0] = FGF_WHITE;
   g_tblTxt[3][1] = DoubleToString(L.value, g_digits);
   g_tblClr[3][1] = FGF_WHITE;
   g_tblTxt[4][0] = (L.onSigBar && L.sigDir > 0 ? "Buy >= " : "Buy  > ") + dLv;
   g_tblClr[4][0] = FGF_WHITE;
   g_tblTxt[4][1] = dBuy ? "ALLOWED" : "BLOCKED";
   g_tblClr[4][1] = dBuy ? FGF_LIME : FGF_RED;
   g_tblTxt[5][0] = (L.onSigBar && L.sigDir < 0 ? "Sell <= " : "Sell < ") + dLv;
   g_tblClr[5][0] = FGF_WHITE;
   g_tblTxt[5][1] = dSell ? "ALLOWED" : "BLOCKED";
   g_tblClr[5][1] = dSell ? FGF_LIME : FGF_RED;
   g_tblTxt[6][0] = "Last " + g_tfTag + " parent / zones";
   g_tblClr[6][0] = FGF_WHITE;
   g_tblTxt[6][1] = dPar + " / " + dZones + " aligned";
   g_tblClr[6][1] = dPar == "BUY" ? FGF_LIME : (dPar == "SELL" ? FGF_RED : FGF_WHITE);
   RenderTable();
  }

//+------------------------------------------------------------------+
//| One chart bar: the permission in force at the bar's clock.        |
//+------------------------------------------------------------------+
void CalcBar(const int i, const int total, const datetime now, const datetime &time[],
             const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   // Clock and price: the moment a bar is judged ("Check price on").
   //   Tick          a closed bar at its close time with its close; the
   //                 forming bar at the real clock with the live price.
   //   Candle open   every bar at its open time with its open.
   //   Candle close  a closed bar at its close time with its close; the
   //                 forming bar at its open time with the last close.
   // Closed bars never repaint in any mode. The last bar counts as closed
   // once its close time has passed (no new tick yet).
   bool     last  = i == total - 1;
   datetime close_t = BarClose(Period(), time[i]);
   bool     live  = last && now < close_t;
   datetime clock = close_t;
   double   value = cl[i];
   if(InpCheck == FGF_CHECK_OPEN)
     {
      clock = time[i];
      value = op[i];
     }
   else
      if(InpCheck == FGF_CHECK_CLOSE)
        {
         if(live)
           {
            clock = time[i];
            value = cl[i - 1];
           }
        }
      else
         if(live)
            clock = now > time[i] ? now : time[i];

   // The arm in force: the latest filter candle closed by this clock.
   int k = g_tf[g_fi].LastClosedBy(clock);
   if(k >= g_stN)
      k = g_stN - 1;
   datetime sigAt  = 0;
   int      sigBar = FGF_NA;
   double   level  = EMPTY_VALUE;
   int      sigDir = 0;
   int      sigId  = 0;
   int      par    = FGF_NA, al = FGF_NA, ac = FGF_NA;
   int      idx    = FGF_NA;
   if(k >= 0)
     {
      sigAt  = g_st[k].aAt;
      sigBar = g_st[k].aBar;
      level  = g_st[k].aPx;
      sigDir = g_st[k].aDir;
      sigId  = g_st[k].aId;
      par    = g_st[k].par;
      al     = g_st[k].al;
      ac     = g_st[k].ac;
      // the filter candle this clock falls in; one closing exactly at the
      // clock is the one judged, as on its own chart
      idx    = g_tf[g_fi].tc[k] == clock ? k : k + 1;
     }

   bool   lvOk  = level != EMPTY_VALUE;

   // permission window: from the signal candle's close until the next signal
   // (or the minutes / candles run out)
   bool     armed  = sigAt > 0 && clock >= sigAt;
   datetime endT   = (InpLast == FGF_LASTS_MINUTES && armed) ? sigAt + InpMinutes * 60 : 0;
   int      endBar = (InpLast == FGF_LASTS_CANDLES && armed) ? sigBar + InpBars : FGF_NA;
   bool     isOpen = armed && (InpLast == FGF_LASTS_MINUTES ? clock < endT : (InpLast == FGF_LASTS_CANDLES ? idx < endBar : true));

   // on the signal candle itself price can sit exactly at the level
   // ("Signal close"): there the signal's own side counts as allowed AT it
   bool onSigBar = armed && idx == sigBar;
   bool atBuy    = onSigBar && sigDir > 0 && lvOk && value >= level;
   bool atSell   = onSigBar && sigDir < 0 && lvOk && value <= level;

   // final gates: is a buy / a sell ALLOWED on this bar? (permission only)
   bool buyOk  = !InpOn || (isOpen && InpAllowBuy && ((lvOk && value > level) || atBuy));
   bool sellOk = !InpOn || (isOpen && InpAllowSell && ((lvOk && value < level) || atSell));

   // a new signal became known on this bar; a Minutes / Candles permission ended
   bool newSig  = i > g_first && sigId > g_sigId[i - 1];
   bool ended   = armed && !isOpen;
   bool expired = InpOn && ended && i > g_first && !g_ended[i - 1];
   g_sigId[i] = sigId;
   g_ended[i] = ended;

   BufBuyOk[i]   = buyOk ? 1.0 : 0.0;
   BufSellOk[i]  = sellOk ? 1.0 : 0.0;
   BufActive[i]  = (InpOn && isOpen) ? 1.0 : 0.0;
   BufLevel[i]   = lvOk ? level : EMPTY_VALUE;
   BufSignal[i]  = newSig ? (double)sigDir : 0.0;
   BufEnded[i]   = expired ? 1.0 : 0.0;
   BufBuyArr[i]  = (InpSigMark && InpOn && newSig && sigDir > 0) ? lo[i] : EMPTY_VALUE;
   BufSellArr[i] = (InpSigMark && InpOn && newSig && sigDir < 0) ? hi[i] : EMPTY_VALUE;
   BufEndArr[i]  = expired ? hi[i] : EMPTY_VALUE;

   int shade = (InpShowBg && InpOn && isOpen) ? (buyOk ? 1 : (sellOk ? 2 : 3)) : 0;
   ShadeBar(i, shade, time);
   LevelLine(i, newSig, armed, isOpen, level, sigDir, time);

   if(last)
     {
      g_last.armed    = armed;
      g_last.isOpen   = isOpen;
      g_last.endT     = endT;
      g_last.endBar   = endBar;
      g_last.idx      = idx;
      g_last.value    = value;
      g_last.level    = level;
      g_last.sigDir   = sigDir;
      g_last.sigAt    = sigAt;
      g_last.onSigBar = onSigBar;
      g_last.atBuy    = atBuy;
      g_last.atSell   = atSell;
      g_last.par      = par;
      g_last.al       = al;
      g_last.ac       = ac;
     }
  }

void EmptyBar(const int i)
  {
   BufBuyOk[i]   = EMPTY_VALUE;
   BufSellOk[i]  = EMPTY_VALUE;
   BufActive[i]  = EMPTY_VALUE;
   BufLevel[i]   = EMPTY_VALUE;
   BufSignal[i]  = EMPTY_VALUE;
   BufEnded[i]   = EMPTY_VALUE;
   BufBuyArr[i]  = EMPTY_VALUE;
   BufSellArr[i] = EMPTY_VALUE;
   BufEndArr[i]  = EMPTY_VALUE;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpMinutes < 1 || InpBars < 1 || InpRsiLen < 2 || InpFastLen < 1 || InpMinAligned < 0 || InpMinAligned > 6 ||
      InpDriftBars < 1 || InpHoldBars < 0 || InpMaxBars < 0 || InpWarmup < 0 || InpTickSize < 0.0 ||
      InpSpreadPts < 0.0 || InpEntryDistPts < 0.0 || InpHoldFavPts < 0.0 || InpBurstAtr < 0.0 ||
      InpEntryDistAtr < 0.0 || InpHoldFavAtr < 0.0 || InpBurstPts < 0.0)
     {
      Print("FlashGold Direction Filter: an input is out of range (see the TradingView minimums).");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_pt     = InpTickSize > 0.0 ? InpTickSize : _Point;
   g_digits = InpTickSize > 0.0 ? DigitsOf(InpTickSize) : _Digits;

   g_tfCount = 0;
   g_fTf     = Resolve(InpTf);
   g_fSec    = PeriodSeconds(g_fTf);
   g_fi      = AddTf(g_fTf);
   g_pi      = AddTf(Resolve(InpParentTf));
   g_zUse[0] = InpUseZ1;
   g_zTf[0]  = Resolve(InpZTf1);
   g_zUse[1] = InpUseZ2;
   g_zTf[1]  = Resolve(InpZTf2);
   g_zUse[2] = InpUseZ3;
   g_zTf[2]  = Resolve(InpZTf3);
   g_zUse[3] = InpUseZ4;
   g_zTf[3]  = Resolve(InpZTf4);
   g_zUse[4] = InpUseZ5;
   g_zTf[4]  = Resolve(InpZTf5);
   g_zUse[5] = InpUseZ6;
   g_zTf[5]  = Resolve(InpZTf6);
   for(int z = 0; z < 6; z++)
      g_zi[z] = g_zUse[z] ? AddTf(g_zTf[z]) : -1;
   g_tfTag = TfText(g_fTf);

   MathSrand((uint)GetTickCount());
   g_pfx = "FGF" + IntegerToString(MathRand()) + "_";

   SetIndexBuffer(0, BufBuyOk, INDICATOR_DATA);
   SetIndexBuffer(1, BufSellOk, INDICATOR_DATA);
   SetIndexBuffer(2, BufActive, INDICATOR_DATA);
   SetIndexBuffer(3, BufLevel, INDICATOR_DATA);
   SetIndexBuffer(4, BufSignal, INDICATOR_DATA);
   SetIndexBuffer(5, BufEnded, INDICATOR_DATA);
   SetIndexBuffer(6, BufBuyArr, INDICATOR_DATA);
   SetIndexBuffer(7, BufSellArr, INDICATOR_DATA);
   SetIndexBuffer(8, BufEndArr, INDICATOR_DATA);
   for(int p = 0; p < 9; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetInteger(6, PLOT_ARROW, 233);
   PlotIndexSetInteger(6, PLOT_ARROW_SHIFT, 12);
   PlotIndexSetInteger(7, PLOT_ARROW, 234);
   PlotIndexSetInteger(7, PLOT_ARROW_SHIFT, -12);
   PlotIndexSetInteger(8, PLOT_ARROW, 251);
   PlotIndexSetInteger(8, PLOT_ARROW_SHIFT, -28);

   IndicatorSetString(INDICATOR_SHORTNAME, "FG-DF " + g_tfTag);
   IndicatorSetInteger(INDICATOR_DIGITS, g_digits);
   SetColors();
   g_reset = true;
   EventSetTimer(1);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, g_pfx);
   ChartRedraw(0);
  }

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
   if(rates_total < 2)
      return 0;
   bool full = prev_calculated <= 0 || g_reset;
   if(full)
     {
      g_reset = false;
      ObjectsDeleteAll(0, g_pfx);
      SetColors();
      g_first = InpMaxBars > 0 ? IMax(0, rates_total - InpMaxBars) : 0;
      g_stN   = 0;
      for(int t = 0; t < g_tfCount; t++)
         g_tf[t].n = 0;
     }

   // 1. candles of every timeframe used (filter, parent, zones)
   int fChanged = 0;
   for(int t = 0; t < g_tfCount; t++)
     {
      long fromL = (long)time[g_first] - (long)InpWarmup * PeriodSeconds(g_tf[t].tf);
      if(fromL < 0)
         fromL = 0;
      int ch = g_tf[t].Load((datetime)fromL, full);
      if(ch == -2)
        {
         g_reset = true;   // history changed: start over on the next tick
         return 0;
        }
      if(ch == -1)
        {
         // data still loading: try again on the next tick (or the timer)
         if(full)
           {
            g_reset   = true;
            g_waiting = true;
           }
         return full ? 0 : prev_calculated;
        }
      g_tf[t].Calc(ch);
      if(t == g_fi)
         fChanged = ch;
     }

   g_waiting = false;

   // 2. FlashGold signal and arming on the filter candles that changed
   int fn = g_tf[g_fi].n;
   if(ArraySize(g_st) < fn)
      ArrayResize(g_st, fn, 1000);
   int fFrom = full ? 0 : IMin(fChanged, g_stN);
   for(int k = fFrom; k < fn; k++)
      CalcCandle(k);
   g_stN = fn;

   // 3. chart bars
   ArrayResize(g_sigId, rates_total, 1000);
   ArrayResize(g_ended, rates_total, 1000);
   ArrayResize(g_from, rates_total, 1000);
   ArrayResize(g_shade, rates_total, 1000);
   ArrayResize(g_runStart, rates_total, 1000);
   if(full)
      for(int i = 0; i < g_first; i++)
         EmptyBar(i);
   datetime now = TimeTradeServer();
   if(now < TimeCurrent())
      now = TimeCurrent();
   int start = full ? g_first : IMax(g_first, prev_calculated - 1);
   for(int i = start; i < rates_total; i++)
      CalcBar(i, rates_total, now, time, open, high, low, close);

   UpdateTable(now);
   ChartRedraw(0);
   return rates_total;
  }

// Other timeframes load in the background; without new ticks (market
// closed) OnCalculate would not run again, so refresh the chart once they
// may be ready.
void OnTimer()
  {
   if(g_waiting && !MQLInfoInteger(MQL_TESTER))
      ChartSetSymbolPeriod(0, _Symbol, _Period);
  }

void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_CHART_CHANGE)
     {
      RenderTable();
      ChartRedraw(0);
     }
  }
//+------------------------------------------------------------------+
