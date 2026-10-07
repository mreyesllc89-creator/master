//+------------------------------------------------------------------+
//|                                              FlashGold_v5_EA.mq5 |
//+------------------------------------------------------------------+
// ============================================================================
//  FLASHGOLD v5 EA  -  v1.0  (MetaTrader 5)
// ----------------------------------------------------------------------------
//  The TradingView "FlashGold v5 Strategy (XAUUSD)" as an Expert Advisor,
//  with the FlashGold Direction Filter built in (one file, nothing else to
//  install).
//
//  TRADING (on "Trading timeframe", default the chart's)
//    At each candle close the FlashGold v5 signal is computed exactly as in
//    the strategy: bid/ask model from the spread input, TDI direction (fast
//    line rising = BUY), parent + six child zones, burst gate, prior drift,
//    entry hold, one entry per bar. A BUY signal places a buy STOP at ask +
//    entry distance, a SELL signal a sell STOP at bid - entry distance.
//    The stop is held by the EA (virtual, not sent to the server): it
//    triggers when the chart price (Bid, like TradingView's chart) reaches it
//    and the EA then opens at market. It is cancelled after N candles
//    unfilled; when one side opens, the other side's stop is cancelled (OCA).
//    Opposite signal: reverses (Allow reverse) and/or closes at market
//    (Close on the opposite signal). Stop loss and take profit (ATR or
//    points, locked at the signal), trailing stop, time stop, and fixed or
//    risk-% lots work as in the strategy.
//
//  DIRECTION FILTER (built in: the FlashGold Direction Filter indicator)
//    The FlashGold v5 signal also runs on "Filter timeframe" (default H1)
//    with its own inputs. Each filter signal sets ONE level: a buy may open
//    only while price is ABOVE it, a sell only while price is BELOW it, until
//    the next filter signal; nothing opens before the first one. Only closed
//    filter candles are used (no repaint). It is checked at the moment an
//    entry triggers, with "Check price on":
//      Tick          the price of that tick (Bid)
//      Candle open   the open of the current trading candle
//      Candle close  the close of the last closed trading candle
//    A blocked entry stays pending until it expires and opens as soon as the
//    filter allows it while price is still beyond the stop. Exits are never
//    filtered. "Enable filter" off = the plain strategy.
//
//  DIFFERENCES FROM THE TRADINGVIEW STRATEGY
//    - Fills: TradingView fills a stop at its price on the chart; here the EA
//      opens at market when the Bid reaches the stop (slippage applies).
//      SL / TP / trail are hit on the real side (Bid for a buy, Ask for a
//      sell), so a sell's exits come a spread earlier than on TradingView.
//    - Costs: commission and slippage are your broker's. The 25-pt spread
//      input only models the signal's bid/ask, as in the strategy.
//    - Lots: 1 lot = the symbol's contract size (100 oz on most XAUUSD), so
//      the strategy's 10 contracts = 0.10 lot.
//    - Pending stops live in the EA: they are lost when the EA restarts.
//    - Parent and zone timeframes above the signal timeframe are read from
//      their last closed candle (TradingView history), never a forming one.
//    - Data feed, server time (H2 / H4 candles) and point size: see the
//      notes in FlashGold_Direction_Filter.mq5. "Point size" = TradingView's
//      syminfo.mintick (0 = this symbol's point).
// ============================================================================
#property copyright   "FlashGold v5 EA"
#property version     "1.00"
#property description "FlashGold v5 strategy with the FlashGold direction filter built in:"
#property description "buys only above the filter level, sells only below it."

#include <Trade/Trade.mqh>

//--- choices
enum ENUM_FG_UNIT
  {
   FG_UNIT_ATR    = 0, // ATR
   FG_UNIT_POINTS = 1  // Points
  };
enum ENUM_FG_DIR
  {
   FG_DIR_BOTH  = 0, // Both
   FG_DIR_LONG  = 1, // Long
   FG_DIR_SHORT = 2  // Short
  };
enum ENUM_FG_QTY
  {
   FG_QTY_FIXED = 0, // Fixed
   FG_QTY_RISK  = 1  // Risk %
  };
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

//--- inputs: trading (the strategy's S1..S3 groups)
input group "S1. Entry order"
input ENUM_TIMEFRAMES InpTradeTf      = PERIOD_CURRENT; // Trading timeframe (current = chart)
input long            InpMagic        = 20261007;       // Magic number
input ENUM_FG_DIR     InpDirection    = FG_DIR_BOTH;    // Direction
input int             InpEntryValid   = 3;              // Cancel unfilled entry after N bars (0 = keep until filled)
input bool            InpAllowReverse = true;           // Opposite signal may reverse an open position
input bool            InpExitOnOpp    = false;          // Close at market on the opposite signal
input int             InpSlippage     = 10;             // Max slippage at market (points)

input group "S2. Exits"
input ENUM_FG_UNIT InpExitMode    = FG_UNIT_ATR; // SL / TP / trail unit
input double       InpSlPoints    = 150;         // Stop loss, pts (Points mode)
input double       InpTpPoints    = 300;         // Take profit, pts (Points mode)
input int          InpAtrLen      = 14;          // ATR length (ATR mode)
input double       InpSlAtrMult   = 2.0;         // Stop loss, ATR mult (ATR mode)
input double       InpTpR         = 2.0;         // Take profit, R multiple of SL (ATR mode)
input bool         InpUseTrail    = true;        // Trailing stop
input double       InpTrailActPts = 150;         // Trail activation, pts of profit (Points mode)
input double       InpTrailPts    = 100;         // Trail distance, pts (Points mode)
input double       InpTrailActAtr = 1.0;         // Trail activation, ATR mult (ATR mode)
input double       InpTrailDstAtr = 0.75;        // Trail distance, ATR mult (ATR mode)
input int          InpMaxBarsHeld = 0;           // Time stop, bars (0 = off)

input group "S3. Sizing"
input ENUM_FG_QTY InpQtyMode   = FG_QTY_FIXED; // Quantity
input double      InpFixedLots = 0.10;         // Fixed lots (0.10 lot = 10 oz on XAUUSD)
input double      InpRiskPct   = 1.0;          // Risk % of equity per trade (Risk mode)
input double      InpMaxLots   = 0.50;         // Max lots

//--- inputs: the strategy's FlashGold signal (on the trading timeframe)
input group "Strategy signal: core"
input double InpSSpreadPts    = 25.0; // Spread pts
input double InpSEntryDistPts = 50.0; // Entry distance pts (Points unit)
input int    InpSHoldBars     = 0;    // Entry hold bars
input double InpSHoldFavPts   = 5.0;  // Hold min favorable pts (Points unit)
input bool   InpSOnePerBar    = true; // One entry per bar

input group "Strategy signal: burst / direction"
input ENUM_FG_UNIT InpSDistUnit     = FG_UNIT_ATR; // Burst / entry distance / hold unit
input double       InpSBurstAtr     = 0.5;         // Burst threshold, ATR mult (ATR unit)
input double       InpSEntryDistAtr = 0.25;        // Entry distance, ATR mult (ATR unit)
input double       InpSHoldFavAtr   = 0.1;         // Hold min favorable, ATR mult (ATR unit)
input double       InpSBurstPts     = 172.0;       // Burst threshold pts (Points unit)
input bool         InpSUseBurst     = true;        // Require burst gate
input bool         InpSAnyCombo     = false;       // Allow any combo
input int          InpSDriftBars    = 60;          // Prior drift bars
input bool         InpSUseDrift     = false;       // Use prior drift filter

input group "Strategy signal: TDI trade zone"
input bool            InpSUseZones   = true;      // Use TDI trade-zone filter
input ENUM_TIMEFRAMES InpSParentTf   = PERIOD_H1; // Parent obedience timeframe
input int             InpSRsiLen     = 14;        // TDI RSI length
input int             InpSFastLen    = 2;         // TDI white fast length
input int             InpSMinAligned = 2;         // Minimum child zones aligned
input bool            InpSFlatParent = false;     // Allow trade if parent is flat
input bool            InpSIgnoreNa   = true;      // Ignore zones without data
input bool            InpSHtfClosed  = true;      // Higher-TF zones use the last CLOSED bar
input bool            InpSUseZ1      = true;      // Use child zone 1
input ENUM_TIMEFRAMES InpSZTf1       = PERIOD_H1; // Zone 1 timeframe
input bool            InpSUseZ2      = true;      // Use child zone 2
input ENUM_TIMEFRAMES InpSZTf2       = PERIOD_H2; // Zone 2 timeframe
input bool            InpSUseZ3      = true;      // Use child zone 3
input ENUM_TIMEFRAMES InpSZTf3       = PERIOD_H4; // Zone 3 timeframe
input bool            InpSUseZ4      = false;     // Use child zone 4
input ENUM_TIMEFRAMES InpSZTf4       = PERIOD_H8; // Zone 4 timeframe
input bool            InpSUseZ5      = false;     // Use child zone 5
input ENUM_TIMEFRAMES InpSZTf5       = PERIOD_M1; // Zone 5 timeframe
input bool            InpSUseZ6      = false;     // Use child zone 6
input ENUM_TIMEFRAMES InpSZTf6       = PERIOD_M2; // Zone 6 timeframe

//--- inputs: the direction filter (the indicator's)
input group "Direction filter"
input bool            InpFOn         = true;              // Enable filter
input ENUM_TIMEFRAMES InpFTf         = PERIOD_H1;         // Filter timeframe (current = trading timeframe)
input ENUM_FGF_LEVEL  InpFLvMode     = FGF_LEVEL_ENTRY;   // Level
input ENUM_FGF_LASTS  InpFLast       = FGF_LASTS_NEXT;    // Permission lasts
input int             InpFMinutes    = 60;                // Minutes
input int             InpFBars       = 1;                 // Candles
input ENUM_FGF_CHECK  InpFCheck      = FGF_CHECK_TICK;    // Check price on
input bool            InpFAllowBuy   = true;              // Allow buys
input bool            InpFAllowSell  = true;              // Allow sells
input bool            InpFDrawLevel  = true;              // Draw the filter level
input bool            InpShowStatus  = true;              // Status text on the chart

input group "Filter signal: core"
input double InpFSpreadPts    = 25.0; // Spread pts
input double InpFEntryDistPts = 50.0; // Entry distance pts (Points unit)
input int    InpFHoldBars     = 0;    // Entry hold bars
input double InpFHoldFavPts   = 5.0;  // Hold min favorable pts (Points unit)
input bool   InpFOnePerBar    = true; // One signal per bar

input group "Filter signal: burst / direction"
input ENUM_FG_UNIT InpFDistUnit     = FG_UNIT_ATR; // Burst / entry distance / hold unit
input double       InpFBurstAtr     = 0.5;         // Burst threshold, ATR mult (ATR unit)
input double       InpFEntryDistAtr = 0.25;        // Entry distance, ATR mult (ATR unit)
input double       InpFHoldFavAtr   = 0.1;         // Hold min favorable, ATR mult (ATR unit)
input double       InpFBurstPts     = 172.0;       // Burst threshold pts (Points unit)
input bool         InpFUseBurst     = true;        // Require burst gate
input bool         InpFAnyCombo     = false;       // Allow any combo
input int          InpFDriftBars    = 60;          // Prior drift bars
input bool         InpFUseDrift     = false;       // Use prior drift filter

input group "Filter signal: TDI trade zone"
input bool            InpFUseZones   = true;      // Use TDI trade-zone filter
input ENUM_TIMEFRAMES InpFParentTf   = PERIOD_H1; // Parent obedience timeframe
input int             InpFRsiLen     = 14;        // TDI RSI length
input int             InpFFastLen    = 2;         // TDI white fast length
input int             InpFMinAligned = 2;         // Minimum child zones aligned
input bool            InpFFlatParent = false;     // Allow trade if parent is flat
input bool            InpFIgnoreNa   = true;      // Ignore zones without data
input bool            InpFHtfClosed  = true;      // Higher-TF zones use the last CLOSED bar
input bool            InpFUseZ1      = true;      // Use child zone 1
input ENUM_TIMEFRAMES InpFZTf1       = PERIOD_H1; // Zone 1 timeframe
input bool            InpFUseZ2      = true;      // Use child zone 2
input ENUM_TIMEFRAMES InpFZTf2       = PERIOD_H2; // Zone 2 timeframe
input bool            InpFUseZ3      = true;      // Use child zone 3
input ENUM_TIMEFRAMES InpFZTf3       = PERIOD_H4; // Zone 3 timeframe
input bool            InpFUseZ4      = false;     // Use child zone 4
input ENUM_TIMEFRAMES InpFZTf4       = PERIOD_H8; // Zone 4 timeframe
input bool            InpFUseZ5      = false;     // Use child zone 5
input ENUM_TIMEFRAMES InpFZTf5       = PERIOD_M1; // Zone 5 timeframe
input bool            InpFUseZ6      = false;     // Use child zone 6
input ENUM_TIMEFRAMES InpFZTf6       = PERIOD_M2; // Zone 6 timeframe

input group "MT5"
input double InpTickSize = 0.0;  // Point size (0 = symbol point) = TradingView syminfo.mintick
input int    InpWarmup   = 1000; // Warm-up candles loaded before the EA starts

//--- constants
#define FG_NA      INT_MIN            // Pine na for int values
#define FG_LIME    C'0,230,118'       // Pine color.lime
#define FG_RED     C'242,54,69'       // Pine color.red

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
   int               rsiLen;
   int               fastLen;
   int               xLen;   // second ATR length (exits), 0 = none
   datetime          t[];    // open time
   datetime          tc[];   // close time
   double            h[];
   double            l[];
   double            c[];
   double            rUp[];  // RSI RMA of up moves   (EMPTY_VALUE = na)
   double            rDn[];  // RSI RMA of down moves (EMPTY_VALUE = na)
   double            rsi[];  // ta.rsi(close, rsiLen)
   double            fast[]; // ta.sma(rsi, fastLen)
   int               dir[];  // fast rising = 1, falling = -1, else 0
   double            atr[];  // ta.atr(14)
   double            xatr[]; // ta.atr(xLen)

                     CTf(void) : tf(PERIOD_CURRENT), n(0), rsiLen(14), fastLen(2), xLen(0) {}
   int               Load(const datetime from, const bool reset);
   void              Calc(const int from);
   int               LastClosedBy(const datetime x) const;
   int               LastOpenBy(const datetime x) const;

private:
   void              Resize(const int size);
   double            Tr(const int j) const;
   void              AtrAt(double &a[], const int len, const int i);
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
   ArrayResize(xatr, size, 1000);
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

// True range (Pine ta.tr(true): high - low on the first candle).
double CTf::Tr(const int j) const
  {
   return j == 0 ? h[j] - l[j] : MathMax(MathMax(h[j] - l[j], MathAbs(h[j] - c[j - 1])), MathAbs(l[j] - c[j - 1]));
  }

// Pine ta.atr(len) at candle i: RMA of the true range, seeded with the SMA of
// the first len values.
void CTf::AtrAt(double &a[], const int len, const int i)
  {
   a[i] = EMPTY_VALUE;
   if(i < len - 1)
      return;
   if(i == 0 || a[i - 1] == EMPTY_VALUE)
     {
      double st = 0.0;
      for(int j = i - len + 1; j <= i; j++)
         st += Tr(j);
      a[i] = st / len;
     }
   else
     {
      double aa = 1.0 / len;
      a[i] = aa * Tr(i) + (1.0 - aa) * a[i - 1];
     }
  }

void CTf::Calc(const int from)
  {
   double ra = 1.0 / rsiLen;
   for(int i = from; i < n; i++)
     {
      // ta.rsi: the change is na on the first candle, so the RMA starts on
      // candle rsiLen with the SMA of the first rsiLen changes.
      rUp[i] = EMPTY_VALUE;
      rDn[i] = EMPTY_VALUE;
      rsi[i] = EMPTY_VALUE;
      if(i >= rsiLen)
        {
         if(rUp[i - 1] == EMPTY_VALUE)
           {
            double su = 0.0, sd = 0.0;
            for(int j = i - rsiLen + 1; j <= i; j++)
              {
               su += MathMax(c[j] - c[j - 1], 0.0);
               sd += MathMax(c[j - 1] - c[j], 0.0);
              }
            rUp[i] = su / rsiLen;
            rDn[i] = sd / rsiLen;
           }
         else
           {
            rUp[i] = ra * MathMax(c[i] - c[i - 1], 0.0) + (1.0 - ra) * rUp[i - 1];
            rDn[i] = ra * MathMax(c[i - 1] - c[i], 0.0) + (1.0 - ra) * rDn[i - 1];
           }
         rsi[i] = rDn[i] == 0.0 ? 100.0 : (rUp[i] == 0.0 ? 0.0 : 100.0 - 100.0 / (1.0 + rUp[i] / rDn[i]));
        }
      // fast line = ta.sma(rsi, fastLen)
      fast[i] = EMPTY_VALUE;
      if(i - fastLen + 1 >= 0)
        {
         double s  = 0.0;
         bool   ok = true;
         for(int j = i - fastLen + 1; j <= i; j++)
           {
            if(rsi[j] == EMPTY_VALUE)
              {
               ok = false;
               break;
              }
            s += rsi[j];
           }
         if(ok)
            fast[i] = s / fastLen;
        }
      // direction: f > f[1] ? 1 : f < f[1] ? -1 : 0 (na compares false -> 0)
      dir[i] = 0;
      if(i >= 1 && fast[i] != EMPTY_VALUE && fast[i - 1] != EMPTY_VALUE)
         dir[i] = fast[i] > fast[i - 1] ? 1 : (fast[i] < fast[i - 1] ? -1 : 0);
      AtrAt(atr, 14, i);
      if(xLen > 0)
         AtrAt(xatr, xLen, i);
      else
         xatr[i] = EMPTY_VALUE;
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
// ctxClose: the latest candle of tf closed by then.
int DirOff(const CTf &T, const datetime ctxClose)
  {
   int j = T.LastClosedBy(ctxClose);
   return j >= 0 ? T.dir[j] : FG_NA;
  }

// request.security(tf, tdiDir()[1], lookahead_on) seen from a candle opening
// at ctxOpen: the candle of tf before the one that contains ctxOpen.
int DirPrevOn(const CTf &T, const datetime ctxOpen)
  {
   int j = T.LastOpenBy(ctxOpen);
   return j >= 1 ? T.dir[j - 1] : FG_NA;
  }

//--- inputs of one FlashGold signal
struct FgParams
  {
   ENUM_TIMEFRAMES   tf;          // the timeframe the signal runs on
   double            spreadPts;
   double            entryDistPts;
   int               holdBars;
   double            holdFavPts;
   bool              onePerBar;
   int               distUnit;    // FG_UNIT_ATR / FG_UNIT_POINTS
   double            burstAtr;
   double            entryDistAtr;
   double            holdFavAtr;
   double            burstPts;
   bool              useBurst;
   bool              anyCombo;
   int               driftBars;
   bool              useDrift;
   bool              useZones;
   ENUM_TIMEFRAMES   parentTf;
   int               rsiLen;
   int               fastLen;
   int               minAligned;
   bool              flatParent;
   bool              ignoreNa;
   bool              htfClosed;
   bool              useZ[6];
   ENUM_TIMEFRAMES   zTf[6];
   int               levelMode;   // filter: FGF_LEVEL_ENTRY / FGF_LEVEL_CLOSE
  };

//--- state after a candle (the Pine 'var' variables)
struct FgState
  {
   bool              holdActive;
   bool              holdIsBuy;
   int               holdSignalBar;
   double            holdSignalMid;
   int               lastEntryBar;
   datetime          aAt;   // filter: signal candle close (0 = na)
   int               aBar;  // filter: signal candle index
   double            aPx;   // filter: level (EMPTY_VALUE = na)
   int               aDir;  // filter: 1 buy, -1 sell
   int               aId;   // filter: signal count
   int               par;   // parent side of this candle
   int               al;    // aligned zones of this candle
   int               ac;    // active zones of this candle
  };

//+------------------------------------------------------------------+
//| The FlashGold v5 signal on one timeframe (the strategy's logic,  |
//| unchanged), with the filter's arming on top.                      |
//+------------------------------------------------------------------+
class CFlashGold
  {
public:
   FgParams          p;
   double            pt;
   CTf               tfs[8];
   int               tfCount;
   int               fi;       // the signal timeframe (loaded first)
   int               pi;       // the parent timeframe
   int               zi[6];    // the zone timeframes (-1 = zone off)
   int               fSec;
   FgState           st[];     // state after each candle
   int               stN;
   int               pend;     // first candle still to recompute
   bool              buySig[]; // signal of each candle
   bool              sellSig[];
   double            buyPx[];  // entry price of each candle's signal
   double            sellPx[];

                     CFlashGold(void) : pt(0.0), tfCount(0), fi(-1), pi(-1), fSec(0), stN(0), pend(INT_MAX) {}
   void              Init(const FgParams &prm, const double point, const int exitAtrLen);
   int               Update(const datetime base, const int warm, const bool reset);

private:
   int               AddTf(const ENUM_TIMEFRAMES tf);
   double            MidAt(const int j);
   int               ZoneDir(const int z, const int k);
   void              StateInit(FgState &s);
   void              CalcCandle(const int k);
  };

int CFlashGold::AddTf(const ENUM_TIMEFRAMES tf)
  {
   for(int i = 0; i < tfCount; i++)
      if(tfs[i].tf == tf)
         return i;
   tfs[tfCount].tf = tf;
   tfs[tfCount].n  = 0;
   return tfCount++;
  }

void CFlashGold::Init(const FgParams &prm, const double point, const int exitAtrLen)
  {
   p       = prm;
   pt      = point;
   tfCount = 0;
   fSec    = PeriodSeconds(p.tf);
   fi      = AddTf(p.tf);
   pi      = AddTf(p.parentTf);
   for(int z = 0; z < 6; z++)
      zi[z] = p.useZ[z] ? AddTf(p.zTf[z]) : -1;
   for(int t = 0; t < tfCount; t++)
     {
      tfs[t].rsiLen  = p.rsiLen;
      tfs[t].fastLen = p.fastLen;
      tfs[t].xLen    = 0;
      tfs[t].n       = 0;
     }
   tfs[fi].xLen = exitAtrLen;
   stN  = 0;
   pend = INT_MAX;
  }

// Loads / refreshes every timeframe and recomputes the candles that changed.
// base: the moment the history is counted back from; warm: warm-up candles.
// Returns 0, -1 (data not ready yet) or -2 (history changed: reset).
int CFlashGold::Update(const datetime base, const int warm, const bool reset)
  {
   if(reset)
     {
      stN  = 0;
      pend = INT_MAX;
      for(int t = 0; t < tfCount; t++)
         tfs[t].n = 0;
     }
   for(int t = 0; t < tfCount; t++)
     {
      // every timeframe covers the signal warm-up, plus its own warm-up
      long back  = (long)warm * fSec + (t == fi ? 0 : (long)warm * PeriodSeconds(tfs[t].tf));
      long fromL = (long)base - back;
      if(fromL < 0)
         fromL = 0;
      int ch = tfs[t].Load((datetime)fromL, reset);
      if(ch < 0)
         return ch;
      tfs[t].Calc(ch);
      // the signal timeframe is loaded first: remember its changed candles
      // even if a later timeframe is not ready and this pass stops early
      if(t == fi)
         pend = IMin(pend, ch);
     }
   int fn = tfs[fi].n;
   if(ArraySize(st) < fn)
     {
      ArrayResize(st, fn, 1000);
      ArrayResize(buySig, fn, 1000);
      ArrayResize(sellSig, fn, 1000);
      ArrayResize(buyPx, fn, 1000);
      ArrayResize(sellPx, fn, 1000);
     }
   for(int k = IMin(pend, stN); k < fn; k++)
      CalcCandle(k);
   stN  = fn;
   pend = INT_MAX;
   return 0;
  }

double CFlashGold::MidAt(const int j)
  {
   double halfSpread = p.spreadPts * pt * 0.5;
   double bid = tfs[fi].c[j] - halfSpread;
   double ask = tfs[fi].c[j] + halfSpread;
   return (bid + ask) * 0.5;
  }

// Direction of a child zone. A zone on a timeframe HIGHER than the signal
// timeframe is read from its last closed candle (htfClosed).
int CFlashGold::ZoneDir(const int z, const int k)
  {
   int ti = zi[z];
   if(ti < 0)
      return FG_NA;
   if(p.htfClosed && PeriodSeconds(p.zTf[z]) > fSec)
      return DirPrevOn(tfs[ti], tfs[fi].t[k]);
   return DirOff(tfs[ti], tfs[fi].tc[k]);
  }

void CFlashGold::StateInit(FgState &s)
  {
   s.holdActive    = false;
   s.holdIsBuy     = false;
   s.holdSignalBar = FG_NA;
   s.holdSignalMid = EMPTY_VALUE;
   s.lastEntryBar  = FG_NA;
   s.aAt           = 0;
   s.aBar          = FG_NA;
   s.aPx           = EMPTY_VALUE;
   s.aDir          = 0;
   s.aId           = 0;
   s.par           = 0;
   s.al            = 0;
   s.ac            = 0;
  }

void CFlashGold::CalcCandle(const int k)
  {
   FgState s;
   if(k > 0)
      s = st[k - 1];
   else
      StateInit(s);

   // price model
   double halfSpread = p.spreadPts * pt * 0.5;
   double bid        = tfs[fi].c[k] - halfSpread;
   double ask        = tfs[fi].c[k] + halfSpread;
   double midPrice   = (bid + ask) * 0.5;

   // TDI trade zone
   int  parentDir = DirOff(tfs[pi], tfs[fi].tc[k]);
   int  zDir[6];
   bool zOn[6];
   int  activeZones = 0;
   for(int z = 0; z < 6; z++)
     {
      zDir[z] = ZoneDir(z, k);
      zOn[z]  = p.useZ[z] && (!p.ignoreNa || zDir[z] != FG_NA);
      if(zOn[z])
         activeZones++;
     }
   int parentSide = parentDir == FG_NA ? 0 : (parentDir > 0 ? 1 : (parentDir < 0 ? -1 : 0));
   int alignedZones = 0;
   for(int z = 0; z < 6; z++)
      if(zOn[z] && parentSide != 0 && zDir[z] == parentSide)
         alignedZones++;

   int  requiredAligned   = IMin(p.minAligned, activeZones);
   bool parentFlatAllowed = p.flatParent && parentSide == 0;
   bool zoneReady         = activeZones == 0 || alignedZones >= requiredAligned;

   bool tradeZoneBuyAllowed  = !p.useZones || ((parentSide == 1 || parentFlatAllowed) && zoneReady);
   bool tradeZoneSellAllowed = !p.useZones || ((parentSide == -1 || parentFlatAllowed) && zoneReady);

   // burst / prior drift (Pine na = the *Ok flags false: every compare fails)
   bool   atrUnit      = p.distUnit == FG_UNIT_ATR;
   bool   thrOk        = !atrUnit || tfs[fi].atr[k] != EMPTY_VALUE;
   double atrPts       = (atrUnit && thrOk) ? tfs[fi].atr[k] / pt : 0.0;
   double burstThrPts  = atrUnit ? p.burstAtr * atrPts : p.burstPts;
   double entryDistPts = atrUnit ? p.entryDistAtr * atrPts : p.entryDistPts;
   double holdFavPts   = atrUnit ? p.holdFavAtr * atrPts : p.holdFavPts;

   bool   burstOk       = k >= 1;
   double burstPts      = burstOk ? (midPrice - MidAt(k - 1)) / pt : 0.0;
   bool   driftOk       = k >= p.driftBars;
   double priorDriftPts = driftOk ? (midPrice - MidAt(k - p.driftBars)) / pt : 0.0;

   bool burstBuy  = burstOk && thrOk && burstPts >= burstThrPts;
   bool burstSell = burstOk && thrOk && burstPts <= -burstThrPts;

   bool priorBuyOk  = !p.useDrift || (driftOk && priorDriftPts > 0);
   bool priorSellOk = !p.useDrift || (driftOk && priorDriftPts < 0);

   bool rawBuyCandidate  = p.anyCombo ? (tradeZoneBuyAllowed && (!p.useBurst || burstBuy || parentSide == 1)) : (tradeZoneBuyAllowed && burstBuy);
   bool rawSellCandidate = p.anyCombo ? (tradeZoneSellAllowed && (!p.useBurst || burstSell || parentSide == -1)) : (tradeZoneSellAllowed && burstSell);

   bool buyCandidate  = rawBuyCandidate && priorBuyOk;
   bool sellCandidate = rawSellCandidate && priorSellOk;

   // entry hold / virtual stop
   double buyEntryPrice  = EMPTY_VALUE;
   double sellEntryPrice = EMPTY_VALUE;
   bool   buySignal      = false;
   bool   sellSignal     = false;

   // computed once, before both branches (as in the strategy)
   bool canFire = !p.onePerBar || s.lastEntryBar == FG_NA || s.lastEntryBar != k;

   if(buyCandidate && canFire)
     {
      if(p.holdBars == 0)
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
         if(elapsedBars >= p.holdBars && thrOk && holdMovePoints >= holdFavPts)
           {
            buyEntryPrice  = ask + entryDistPts * pt;
            buySignal      = true;
            s.lastEntryBar = k;
            s.holdActive   = false;
           }
        }
     }

   if(sellCandidate && canFire)
     {
      if(p.holdBars == 0)
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
         if(elapsedBars >= p.holdBars && thrOk && holdMovePoints >= holdFavPts)
           {
            sellEntryPrice = bid - entryDistPts * pt;
            sellSignal     = true;
            s.lastEntryBar = k;
            s.holdActive   = false;
           }
        }
     }

   if(s.holdActive && ((s.holdIsBuy && !tradeZoneBuyAllowed) || (!s.holdIsBuy && !tradeZoneSellAllowed)))
     {
      s.holdActive    = false;
      s.holdSignalBar = FG_NA;
      s.holdSignalMid = EMPTY_VALUE;
     }

   buySig[k]  = buySignal;
   sellSig[k] = sellSignal;
   buyPx[k]   = buyEntryPrice;
   sellPx[k]  = sellEntryPrice;

   // filter arming: a signal candle sets the level at its close
   double signalPx = buySignal ? buyEntryPrice : (sellSignal ? sellEntryPrice : EMPTY_VALUE);
   if(buySignal || sellSignal)
     {
      s.aAt  = tfs[fi].tc[k];
      s.aBar = k;
      s.aPx  = p.levelMode == FGF_LEVEL_ENTRY ? (signalPx != EMPTY_VALUE ? signalPx : tfs[fi].c[k]) : tfs[fi].c[k];
      s.aDir = buySignal ? 1 : -1;
      s.aId++;
     }
   s.par = parentSide;
   s.al  = alignedZones;
   s.ac  = activeZones;
   st[k] = s;
  }

//--- an EA-held entry stop (the strategy's strategy.entry(..., stop = ...))
struct FgPending
  {
   bool              active;
   double            price;   // trigger
   double            lots;
   double            sl;      // ticks, EMPTY_VALUE / <= 0 = none (locked at the signal)
   double            tp;
   double            act;     // trail activation, ticks
   double            dst;     // trail distance, ticks
   datetime          placed;  // open time of the signal candle
  };

//--- the filter's answer at a moment
struct FgPerm
  {
   bool              armed;
   bool              isOpen;
   bool              buyOk;
   bool              sellOk;
   bool              onSigBar;
   datetime          sigAt;
   datetime          endT;
   int               endBar;
   int               idx;
   int               sigDir;
   double            level;
   double            value;
   int               par;
   int               al;
   int               ac;
  };

//--- globals
CTrade          g_trade;
CFlashGold      g_sig;              // the strategy's signal (trading timeframe)
CFlashGold      g_flt;              // the direction filter (filter timeframe)
ENUM_TIMEFRAMES g_tradeTf;
double          g_pt = 0.0;
datetime        g_base = 0;         // history is counted back from here
bool            g_sigReset = true;
bool            g_fltReset = true;
datetime        g_lastBar = 0;
FgPending       g_pL;
FgPending       g_pS;
string          g_lvlName = "";

ENUM_TIMEFRAMES Resolve(const ENUM_TIMEFRAMES tf, const ENUM_TIMEFRAMES current) { return tf == PERIOD_CURRENT ? current : tf; }

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

string FormatTime(const datetime x)
  {
   static const string mon[12] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
   MqlDateTime d;
   TimeToStruct(x, d);
   return mon[d.mon - 1] + " " + StringFormat("%02d %02d:%02d", d.day, d.hour, d.min);
  }

void PendingClear(FgPending &q)
  {
   q.active = false;
   q.price  = 0.0;
   q.lots   = 0.0;
   q.sl     = EMPTY_VALUE;
   q.tp     = EMPTY_VALUE;
   q.act    = EMPTY_VALUE;
   q.dst    = EMPTY_VALUE;
   q.placed = 0;
  }

//+------------------------------------------------------------------+
//| Positions of this EA                                              |
//+------------------------------------------------------------------+
bool IsMine(void)
  {
   return PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic;
  }

int CountPos(const ENUM_POSITION_TYPE type)
  {
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
         cnt++;
     }
   return cnt;
  }

void ClosePos(const ENUM_POSITION_TYPE type)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type)
         g_trade.PositionClose(tk);
     }
  }

// Open time of the latest open position of this EA (0 if none).
datetime LatestOpenTime(void)
  {
   datetime latest = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(ot > latest)
         latest = ot;
     }
   return latest;
  }

// Trailing parameters of a position, kept in terminal global variables so
// they survive an EA restart.
string TrailKey(const long id, const string what) { return "FGEA_" + IntegerToString(InpMagic) + "_" + IntegerToString(id) + "_" + what; }

void TrailSave(const long id, const double act, const double dst)
  {
   GlobalVariableSet(TrailKey(id, "a"), act);
   GlobalVariableSet(TrailKey(id, "d"), dst);
  }

bool TrailLoad(const long id, double &act, double &dst)
  {
   if(!GlobalVariableCheck(TrailKey(id, "a")) || !GlobalVariableCheck(TrailKey(id, "d")))
      return false;
   act = GlobalVariableGet(TrailKey(id, "a"));
   dst = GlobalVariableGet(TrailKey(id, "d"));
   return true;
  }

//+------------------------------------------------------------------+
//| Sizing (the strategy's calcQty, in lots)                          |
//+------------------------------------------------------------------+
double CalcLots(const double slTicks)
  {
   double q = InpFixedLots;
   if(InpQtyMode == FG_QTY_RISK)
     {
      double riskCash = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
      double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tickVal <= 0.0)
         tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double stopCash = (slTicks == EMPTY_VALUE || tickSize <= 0.0) ? 0.0 : slTicks * g_pt / tickSize * tickVal;
      q = stopCash > 0.0 ? riskCash / stopCash : 0.0;
     }
   q = MathMin(q, InpMaxLots);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0.0)
      q = MathFloor(q / step + 1e-9) * step;
   if(q < vmin || q <= 0.0)
      return 0.0;
   if(q > vmax)
      q = vmax;
   return NormalizeDouble(q, 8);
  }

//+------------------------------------------------------------------+
//| Direction filter: the permission at this moment (the indicator's  |
//| CalcBar on the forming trading candle)                            |
//+------------------------------------------------------------------+
void FilterPermission(FgPerm &r)
  {
   r.armed    = false;
   r.isOpen   = false;
   r.onSigBar = false;
   r.sigAt    = 0;
   r.endT     = 0;
   r.endBar   = FG_NA;
   r.idx      = FG_NA;
   r.sigDir   = 0;
   r.level    = EMPTY_VALUE;
   r.value    = EMPTY_VALUE;
   r.par      = FG_NA;
   r.al       = FG_NA;
   r.ac       = FG_NA;
   r.buyOk    = !InpFOn;
   r.sellOk   = !InpFOn;
   if(!InpFOn || g_flt.stN <= 0)
      return;

   // clock and price ("Check price on") on the forming trading candle
   datetime bar0   = iTime(_Symbol, g_tradeTf, 0);
   datetime close0 = BarClose(g_tradeTf, bar0);
   datetime now    = TimeTradeServer();
   if(now < TimeCurrent())
      now = TimeCurrent();
   datetime clock  = bar0;
   double   value  = 0.0;
   bool     rtTick = false;   // the clock comes from the real clock (Tick)
   if(InpFCheck == FGF_CHECK_OPEN)
      value = iOpen(_Symbol, g_tradeTf, 0);
   else
      if(InpFCheck == FGF_CHECK_CLOSE)
         value = iClose(_Symbol, g_tradeTf, 1);
      else
        {
         // the real clock, kept inside the candle
         rtTick = now >= bar0;
         clock  = now > bar0 ? now : bar0;
         if(clock >= close0)
            clock = close0 - 1;
         // nor past the newest filter candle while it can still get ticks
         // (the tick being handled is stamped before its close)
         int      fl       = g_flt.tfs[g_flt.fi].n - 1;
         datetime fEnd     = fl >= 0 ? g_flt.tfs[g_flt.fi].tc[fl] : 0;
         datetime lastTick = (datetime)SymbolInfoInteger(_Symbol, SYMBOL_TIME);
         if(fl >= 0 && clock >= fEnd && lastTick < fEnd)
            clock = fEnd - 1;
         value = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        }
   r.value = value;

   // the arm in force: the latest filter candle closed by this clock
   int k = g_flt.tfs[g_flt.fi].LastClosedBy(clock);
   if(k >= g_flt.stN)
      k = g_flt.stN - 1;
   if(k < 0)
      return;
   r.sigAt  = g_flt.st[k].aAt;
   r.level  = g_flt.st[k].aPx;
   r.sigDir = g_flt.st[k].aDir;
   r.par    = g_flt.st[k].par;
   r.al     = g_flt.st[k].al;
   r.ac     = g_flt.st[k].ac;
   int sigBar = g_flt.st[k].aBar;
   // the filter candle this clock falls in; one closing exactly at the
   // clock is the one judged, as on its own chart (a real-clock tick in the
   // second a filter candle closes is already after it, as on TradingView)
   r.idx = g_flt.tfs[g_flt.fi].tc[k] == clock && !rtTick ? k : k + 1;

   bool lvOk = r.level != EMPTY_VALUE;
   r.armed   = r.sigAt > 0 && clock >= r.sigAt;
   r.endT    = (InpFLast == FGF_LASTS_MINUTES && r.armed) ? r.sigAt + InpFMinutes * 60 : 0;
   r.endBar  = (InpFLast == FGF_LASTS_CANDLES && r.armed) ? sigBar + InpFBars : FG_NA;
   r.isOpen  = r.armed && (InpFLast == FGF_LASTS_MINUTES ? clock < r.endT : (InpFLast == FGF_LASTS_CANDLES ? r.idx < r.endBar : true));

   // on the signal candle itself price can sit exactly at the level
   r.onSigBar  = r.armed && r.idx == sigBar;
   bool atBuy  = r.onSigBar && r.sigDir > 0 && lvOk && value >= r.level;
   bool atSell = r.onSigBar && r.sigDir < 0 && lvOk && value <= r.level;

   r.buyOk  = r.isOpen && InpFAllowBuy && ((lvOk && value > r.level) || atBuy);
   r.sellOk = r.isOpen && InpFAllowSell && ((lvOk && value < r.level) || atSell);
  }

//+------------------------------------------------------------------+
//| Orders                                                            |
//+------------------------------------------------------------------+
// Opens at market with the pending's locked SL / TP (ticks from the fill).
bool OpenPos(const bool buy, const FgPending &q)
  {
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px   = buy ? ask : bid;
   double minD = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double sl   = 0.0;
   double tp   = 0.0;
   if(q.sl != EMPTY_VALUE && q.sl > 0.0)
     {
      double d = MathMax(q.sl * g_pt, minD);
      sl = NormalizeDouble(buy ? px - d : px + d, _Digits);
     }
   if(q.tp != EMPTY_VALUE && q.tp > 0.0)
     {
      double d = MathMax(q.tp * g_pt, minD);
      tp = NormalizeDouble(buy ? px + d : px - d, _Digits);
     }
   bool ok = buy ? g_trade.Buy(q.lots, _Symbol, 0.0, sl, tp, "FG buy stop")
             : g_trade.Sell(q.lots, _Symbol, 0.0, sl, tp, "FG sell stop");
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
     {
      PrintFormat("FlashGold EA: %s failed, retcode %u (%s)", buy ? "buy" : "sell", rc, g_trade.ResultRetcodeDescription());
      return false;
     }
   // keep the trail parameters with the new position
   if(InpUseTrail && q.act != EMPTY_VALUE && q.dst != EMPTY_VALUE)
     {
      long     id     = 0;
      datetime latest = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong tk = PositionGetTicket(i);
         if(tk == 0 || !IsMine())
            continue;
         if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != (buy ? POSITION_TYPE_BUY : POSITION_TYPE_SELL))
            continue;
         datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
         if(ot >= latest)
           {
            latest = ot;
            id     = PositionGetInteger(POSITION_IDENTIFIER);
           }
        }
      if(id != 0)
         TrailSave(id, q.act, q.dst);
     }
   return true;
  }

// Trailing stop (strategy.exit trail_points / trail_offset): once the profit
// reaches 'act' ticks, the stop follows 'dst' ticks behind the best price.
void ManageTrailing(void)
  {
   if(!InpUseTrail)
      return;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minD = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      double act = 0.0, dst = 0.0;
      if(!TrailLoad(PositionGetInteger(POSITION_IDENTIFIER), act, dst))
         continue;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         if((bid - open) / g_pt >= act)
           {
            double nsl = NormalizeDouble(bid - dst * g_pt, _Digits);
            if((sl == 0.0 || nsl > sl + _Point * 0.5) && bid - nsl >= minD)
               g_trade.PositionModify(tk, nsl, tp);
           }
        }
      else
        {
         if((open - ask) / g_pt >= act)
           {
            double nsl = NormalizeDouble(ask + dst * g_pt, _Digits);
            if((sl == 0.0 || nsl < sl - _Point * 0.5) && nsl - ask >= minD)
               g_trade.PositionModify(tk, nsl, tp);
           }
        }
     }
  }

// The strategy's order block, at the close of candle k (run on the first
// tick of the next candle, where TradingView would fill these orders).
void OnCandleClose(const int k)
  {
   bool   buySignal      = g_sig.buySig[k];
   bool   sellSignal     = g_sig.sellSig[k];
   double buyEntryPrice  = g_sig.buyPx[k];
   double sellEntryPrice = g_sig.sellPx[k];

   // exit geometry, locked at the signal
   bool   pointsMode  = InpExitMode == FG_UNIT_POINTS;
   double atrV        = g_sig.tfs[g_sig.fi].xatr[k];
   double atr14       = g_sig.tfs[g_sig.fi].atr[k];
   double atrPts      = atr14 != EMPTY_VALUE ? atr14 / g_pt : EMPTY_VALUE;
   double slTicksNow  = pointsMode ? InpSlPoints : (atrV != EMPTY_VALUE ? InpSlAtrMult * atrV / g_pt : EMPTY_VALUE);
   double tpTicksNow  = pointsMode ? InpTpPoints : (slTicksNow != EMPTY_VALUE ? slTicksNow * InpTpR : EMPTY_VALUE);
   double trailActNow = pointsMode ? InpTrailActPts : (atrPts != EMPTY_VALUE ? InpTrailActAtr * atrPts : EMPTY_VALUE);
   double trailDstNow = pointsMode ? InpTrailPts : (atrPts != EMPTY_VALUE ? MathMax(InpTrailDstAtr * atrPts, 1.0) : EMPTY_VALUE);

   bool allowL  = InpDirection != FG_DIR_SHORT;
   bool allowS  = InpDirection != FG_DIR_LONG;
   bool inLong  = CountPos(POSITION_TYPE_BUY) > 0;
   bool inShort = CountPos(POSITION_TYPE_SELL) > 0;
   bool flat    = !inLong && !inShort;

   // opposite-signal handling on an open position
   if(InpExitOnOpp && sellSignal && inLong)
      ClosePos(POSITION_TYPE_BUY);
   if(InpExitOnOpp && buySignal && inShort)
      ClosePos(POSITION_TYPE_SELL);

   // long entry: stop at the signal's entry price
   if(buySignal && allowL && !inLong && (flat || InpAllowReverse || InpExitOnOpp))
     {
      double qL = CalcLots(slTicksNow);
      if(qL > 0.0 && buyEntryPrice != EMPTY_VALUE)
        {
         g_pL.active = true;
         g_pL.price  = buyEntryPrice;
         g_pL.lots   = qL;
         g_pL.sl     = slTicksNow;
         g_pL.tp     = tpTicksNow;
         g_pL.act    = trailActNow;
         g_pL.dst    = trailDstNow;
         g_pL.placed = g_sig.tfs[g_sig.fi].t[k];
        }
     }

   // short entry
   if(sellSignal && allowS && !inShort && (flat || InpAllowReverse || InpExitOnOpp))
     {
      double qS = CalcLots(slTicksNow);
      if(qS > 0.0 && sellEntryPrice != EMPTY_VALUE)
        {
         g_pS.active = true;
         g_pS.price  = sellEntryPrice;
         g_pS.lots   = qS;
         g_pS.sl     = slTicksNow;
         g_pS.tp     = tpTicksNow;
         g_pS.act    = trailActNow;
         g_pS.dst    = trailDstNow;
         g_pS.placed = g_sig.tfs[g_sig.fi].t[k];
        }
     }

   // cancel a stale unfilled entry
   if(InpEntryValid > 0)
     {
      if(g_pL.active && !inLong && k - g_sig.tfs[g_sig.fi].LastOpenBy(g_pL.placed) >= InpEntryValid)
         PendingClear(g_pL);
      if(g_pS.active && !inShort && k - g_sig.tfs[g_sig.fi].LastOpenBy(g_pS.placed) >= InpEntryValid)
         PendingClear(g_pS);
     }

   // time stop
   if(InpMaxBarsHeld > 0 && !flat)
     {
      int eb = g_sig.tfs[g_sig.fi].LastOpenBy(LatestOpenTime());
      if(eb >= 0 && k - eb >= InpMaxBarsHeld)
        {
         ClosePos(POSITION_TYPE_BUY);
         ClosePos(POSITION_TYPE_SELL);
        }
     }
  }

// Triggers the EA-held stops when the chart price (Bid) reaches them and the
// direction filter allows that side at this moment. A blocked stop stays
// pending; when one side opens, the other side's stop is cancelled (OCA).
void CheckPendings(void)
  {
   if(!g_pL.active && !g_pS.active)
      return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(g_pL.active && bid >= g_pL.price && CountPos(POSITION_TYPE_BUY) == 0)
     {
      FgPerm r;
      FilterPermission(r);
      if(r.buyOk)
        {
         // the long reverses an open short
         if(CountPos(POSITION_TYPE_SELL) > 0)
            ClosePos(POSITION_TYPE_SELL);
         if(CountPos(POSITION_TYPE_SELL) == 0 && OpenPos(true, g_pL))
           {
            PendingClear(g_pL);
            PendingClear(g_pS);
            return;
           }
        }
     }
   if(g_pS.active && bid <= g_pS.price && CountPos(POSITION_TYPE_SELL) == 0)
     {
      FgPerm r;
      FilterPermission(r);
      if(r.sellOk)
        {
         if(CountPos(POSITION_TYPE_BUY) > 0)
            ClosePos(POSITION_TYPE_BUY);
         if(CountPos(POSITION_TYPE_BUY) == 0 && OpenPos(false, g_pS))
           {
            PendingClear(g_pS);
            PendingClear(g_pL);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Status text and the filter level on the chart                     |
//+------------------------------------------------------------------+
void ShowStatus(void)
  {
   FgPerm r;
   FilterPermission(r);
   if(InpFDrawLevel && InpFOn && r.level != EMPTY_VALUE && r.armed)
     {
      if(ObjectFind(0, g_lvlName) < 0)
        {
         ObjectCreate(0, g_lvlName, OBJ_HLINE, 0, 0, r.level);
         ObjectSetInteger(0, g_lvlName, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, g_lvlName, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, g_lvlName, OBJPROP_HIDDEN, true);
        }
      ObjectSetDouble(0, g_lvlName, OBJPROP_PRICE, 0, r.level);
      ObjectSetInteger(0, g_lvlName, OBJPROP_COLOR, r.sigDir > 0 ? FG_LIME : FG_RED);
      ObjectSetInteger(0, g_lvlName, OBJPROP_STYLE, r.isOpen ? STYLE_SOLID : STYLE_DOT);
     }
   else
      ObjectDelete(0, g_lvlName);
   if(!InpShowStatus)
      return;

   string tag = TfText(g_flt.p.tf);
   string txt = "FlashGold v5 EA  (" + TfText(g_tradeTf) + ", magic " + IntegerToString(InpMagic) + ")\n";
   if(!InpFOn)
      txt += "Direction filter: OFF (every entry allowed)\n";
   else
     {
      string side  = r.sigDir > 0 ? "BUY" : "SELL";
      string state = !r.armed ? "WAITING FOR SIGNAL" : (r.isOpen ? "ACTIVE - " : "ENDED - ") + side + " signal";
      string lv    = r.level != EMPTY_VALUE ? DoubleToString(r.level, _Digits) : "-";
      string chk   = InpFCheck == FGF_CHECK_OPEN ? "candle open" : (InpFCheck == FGF_CHECK_CLOSE ? "last close" : "tick");
      txt += "Filter " + tag + ": " + state;
      if(r.sigAt > 0)
         txt += "  (" + FormatTime(r.sigAt) + " server)";
      txt += "\n";
      txt += "  Buy  > " + lv + "  " + (r.buyOk ? "ALLOWED" : "BLOCKED") + "   |   Sell < " + lv + "  " + (r.sellOk ? "ALLOWED" : "BLOCKED") +
             "   (" + chk + " " + (r.value != EMPTY_VALUE ? DoubleToString(r.value, _Digits) : "-") + ")\n";
      string dPar = r.par == FG_NA ? "-" : (r.par > 0 ? "BUY" : (r.par < 0 ? "SELL" : "FLAT"));
      string dZn  = r.ac == FG_NA ? "-" : IntegerToString(r.al) + "/" + IntegerToString(r.ac);
      txt += "  Last " + tag + " parent / zones: " + dPar + " / " + dZn + " aligned\n";
     }
   txt += "Pending: BUY STOP " + (g_pL.active ? DoubleToString(g_pL.price, _Digits) + " (" + DoubleToString(g_pL.lots, 2) + " lot)" : "-") +
          "   SELL STOP " + (g_pS.active ? DoubleToString(g_pS.price, _Digits) + " (" + DoubleToString(g_pS.lots, 2) + " lot)" : "-") + "\n";
   int nL = CountPos(POSITION_TYPE_BUY);
   int nS = CountPos(POSITION_TYPE_SELL);
   txt += "Position: " + (nL > 0 ? "LONG" : (nS > 0 ? "SHORT" : "flat"));
   Comment(txt);
  }

//+------------------------------------------------------------------+
//| Parameters of the two FlashGold signals                           |
//+------------------------------------------------------------------+
void StrategyParams(FgParams &p)
  {
   p.tf           = g_tradeTf;
   p.spreadPts    = InpSSpreadPts;
   p.entryDistPts = InpSEntryDistPts;
   p.holdBars     = InpSHoldBars;
   p.holdFavPts   = InpSHoldFavPts;
   p.onePerBar    = InpSOnePerBar;
   p.distUnit     = InpSDistUnit;
   p.burstAtr     = InpSBurstAtr;
   p.entryDistAtr = InpSEntryDistAtr;
   p.holdFavAtr   = InpSHoldFavAtr;
   p.burstPts     = InpSBurstPts;
   p.useBurst     = InpSUseBurst;
   p.anyCombo     = InpSAnyCombo;
   p.driftBars    = InpSDriftBars;
   p.useDrift     = InpSUseDrift;
   p.useZones     = InpSUseZones;
   p.parentTf     = Resolve(InpSParentTf, g_tradeTf);
   p.rsiLen       = InpSRsiLen;
   p.fastLen      = InpSFastLen;
   p.minAligned   = InpSMinAligned;
   p.flatParent   = InpSFlatParent;
   p.ignoreNa     = InpSIgnoreNa;
   p.htfClosed    = InpSHtfClosed;
   p.useZ[0] = InpSUseZ1;
   p.zTf[0]  = Resolve(InpSZTf1, g_tradeTf);
   p.useZ[1] = InpSUseZ2;
   p.zTf[1]  = Resolve(InpSZTf2, g_tradeTf);
   p.useZ[2] = InpSUseZ3;
   p.zTf[2]  = Resolve(InpSZTf3, g_tradeTf);
   p.useZ[3] = InpSUseZ4;
   p.zTf[3]  = Resolve(InpSZTf4, g_tradeTf);
   p.useZ[4] = InpSUseZ5;
   p.zTf[4]  = Resolve(InpSZTf5, g_tradeTf);
   p.useZ[5] = InpSUseZ6;
   p.zTf[5]  = Resolve(InpSZTf6, g_tradeTf);
   p.levelMode = FGF_LEVEL_ENTRY;
  }

void FilterParams(FgParams &p)
  {
   p.tf           = Resolve(InpFTf, g_tradeTf);
   p.spreadPts    = InpFSpreadPts;
   p.entryDistPts = InpFEntryDistPts;
   p.holdBars     = InpFHoldBars;
   p.holdFavPts   = InpFHoldFavPts;
   p.onePerBar    = InpFOnePerBar;
   p.distUnit     = InpFDistUnit;
   p.burstAtr     = InpFBurstAtr;
   p.entryDistAtr = InpFEntryDistAtr;
   p.holdFavAtr   = InpFHoldFavAtr;
   p.burstPts     = InpFBurstPts;
   p.useBurst     = InpFUseBurst;
   p.anyCombo     = InpFAnyCombo;
   p.driftBars    = InpFDriftBars;
   p.useDrift     = InpFUseDrift;
   p.useZones     = InpFUseZones;
   p.parentTf     = Resolve(InpFParentTf, g_tradeTf);
   p.rsiLen       = InpFRsiLen;
   p.fastLen      = InpFFastLen;
   p.minAligned   = InpFMinAligned;
   p.flatParent   = InpFFlatParent;
   p.ignoreNa     = InpFIgnoreNa;
   p.htfClosed    = InpFHtfClosed;
   p.useZ[0] = InpFUseZ1;
   p.zTf[0]  = Resolve(InpFZTf1, g_tradeTf);
   p.useZ[1] = InpFUseZ2;
   p.zTf[1]  = Resolve(InpFZTf2, g_tradeTf);
   p.useZ[2] = InpFUseZ3;
   p.zTf[2]  = Resolve(InpFZTf3, g_tradeTf);
   p.useZ[3] = InpFUseZ4;
   p.zTf[3]  = Resolve(InpFZTf4, g_tradeTf);
   p.useZ[4] = InpFUseZ5;
   p.zTf[4]  = Resolve(InpFZTf5, g_tradeTf);
   p.useZ[5] = InpFUseZ6;
   p.zTf[5]  = Resolve(InpFZTf6, g_tradeTf);
   p.levelMode = InpFLvMode;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpEntryValid < 0 || InpMaxBarsHeld < 0 || InpAtrLen < 1 || InpSlAtrMult < 0.1 || InpTpR < 0.0 || InpTrailDstAtr < 0.05 ||
      InpTrailPts < 1.0 || InpSlPoints < 0.0 || InpTpPoints < 0.0 || InpTrailActPts < 0.0 || InpTrailActAtr < 0.0 ||
      InpFixedLots < 0.0 || InpRiskPct < 0.0 || InpMaxLots < 0.0 || InpSlippage < 0 ||
      InpSRsiLen < 2 || InpSFastLen < 1 || InpSMinAligned < 0 || InpSMinAligned > 6 || InpSDriftBars < 1 || InpSHoldBars < 0 ||
      InpFRsiLen < 2 || InpFFastLen < 1 || InpFMinAligned < 0 || InpFMinAligned > 6 || InpFDriftBars < 1 || InpFHoldBars < 0 ||
      InpFMinutes < 1 || InpFBars < 1 || InpTickSize < 0.0 || InpWarmup < 1)
     {
      Print("FlashGold EA: an input is out of range (see the TradingView minimums).");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_tradeTf = Resolve(InpTradeTf, Period());
   g_pt      = InpTickSize > 0.0 ? InpTickSize : _Point;

   FgParams sp;
   StrategyParams(sp);
   g_sig.Init(sp, g_pt, InpAtrLen);
   FgParams fp;
   FilterParams(fp);
   g_flt.Init(fp, g_pt, 0);

   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippage);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   PendingClear(g_pL);
   PendingClear(g_pS);
   g_base     = TimeCurrent();
   g_sigReset = true;
   g_fltReset = true;
   g_lastBar  = 0;
   g_lvlName  = "FGEA_" + IntegerToString(InpMagic) + "_level";
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Comment("");
   ObjectDelete(0, g_lvlName);
  }

void OnTick()
  {
   // the direction filter follows every tick (its last closed candle)
   if(InpFOn)
     {
      int rf = g_flt.Update(g_base, InpWarmup, g_fltReset);
      if(rf == -2)
        {
         g_fltReset = true;
         return;
        }
      if(rf == -1)
        {
         if(InpShowStatus)
            Comment("FlashGold v5 EA: loading the filter's history...");
         return;
        }
      g_fltReset = false;
     }

   // the strategy acts once per trading candle, at its close
   datetime bar0 = iTime(_Symbol, g_tradeTf, 0);
   if(bar0 == 0)
      return;
   if(bar0 != g_lastBar)
     {
      int rs = g_sig.Update(g_base, InpWarmup, g_sigReset);
      if(rs == -2)
        {
         g_sigReset = true;
         return;
        }
      if(rs == -1)
        {
         if(InpShowStatus)
            Comment("FlashGold v5 EA: loading the strategy's history...");
         return;
        }
      g_sigReset = false;
      // the candle that just closed; not on the first tick after start (its
      // signal is history, the EA was not running when it closed)
      int k = g_sig.tfs[g_sig.fi].LastOpenBy(bar0 - 1);
      if(g_lastBar != 0 && k >= 0 && k < g_sig.stN)
         OnCandleClose(k);
      g_lastBar = bar0;
     }

   ManageTrailing();
   CheckPendings();
   ShowStatus();
  }
//+------------------------------------------------------------------+
