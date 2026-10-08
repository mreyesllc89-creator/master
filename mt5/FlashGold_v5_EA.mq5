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
//      opens at market when the Bid reaches the stop (slippage applies), so
//      a buy fills at the Ask, one spread above the stop. SL / TP / trail are
//      measured from the real fill and hit on the real side (Bid for a buy,
//      Ask for a sell), so P&L distances match the strategy; on the chart, SL
//      comes one spread earlier and TP / trail activation one spread later
//      than on TradingView, for both buys and sells. The trailing stop moves
//      in steps of at least "Trail step" and respects the freeze level.
//    - Costs: commission and slippage are your broker's. The 25-pt spread
//      input only models the signal's bid/ask, as in the strategy.
//    - Lots: 1 lot = the symbol's contract size (100 oz on most XAUUSD), so
//      the strategy's 10 contracts = 0.10 lot.
//    - Pending stops live in the EA: they survive an input or chart change
//      but are lost when the EA or the terminal restarts.
//    - A failed order is not resent on every tick: it waits a few seconds,
//      or until the next candle when the server refuses it for good (money,
//      volume, stops, market closed). A failed exit is retried each second.
//    - One magic number per chart running the EA. On a netting account the
//      EA does not trade into a manual or other-EA position on the symbol.
//    - Backtest with "Every tick" modelling (real ticks if you can) and a
//      tester period at or below the trading timeframe: with "Open prices
//      only" stops, trailing and the Tick filter are seen only at bar opens.
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
input long            InpMagic        = 20261007;       // Magic number (one per chart running this EA)
input ENUM_FG_DIR     InpDirection    = FG_DIR_BOTH;    // Direction
input int             InpEntryValid   = 3;              // Cancel unfilled entry after N bars (0 = keep until filled)
input bool            InpAllowReverse = true;           // Opposite signal may reverse an open position
input bool            InpExitOnOpp    = false;          // Close at market on the opposite signal
input int             InpSlippage     = 10;             // Max slippage at market (points)

input group "S2. Exits"
input ENUM_FG_UNIT InpExitMode    = FG_UNIT_POINTS; // SL / TP / trail unit
input double       InpSlPoints    = 5000;        // Stop loss, pts (Points mode)
input double       InpTpPoints    = 50000;       // Take profit, pts (Points mode)
input int          InpAtrLen      = 14;          // ATR length (ATR mode)
input double       InpSlAtrMult   = 2.0;         // Stop loss, ATR mult (ATR mode)
input double       InpTpR         = 2.0;         // Take profit, R multiple of SL (ATR mode)
input bool         InpUseTrail    = true;        // Trailing stop
input double       InpTrailActPts = 4500;        // Trail activation, pts of profit (Points mode)
input double       InpTrailPts    = 1000;        // Trail distance, pts (Points mode)
input double       InpTrailActAtr = 4.0;         // Trail activation, ATR mult (ATR mode)
input double       InpTrailDstAtr = 0.2;         // Trail distance, ATR mult (ATR mode)
input double       InpTrailStepPts = 5;          // Trail step, pts (min stop move per modify; MT5 only)
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
input int             InpFBars       = 1;                 // Candles (with Tick: N = N-1 candles after the signal candle)
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
input ENUM_TIMEFRAMES InpFParentTf   = PERIOD_H1; // Parent obedience timeframe (current = filter timeframe)
input int             InpFRsiLen     = 14;        // TDI RSI length
input int             InpFFastLen    = 2;         // TDI white fast length
input int             InpFMinAligned = 2;         // Minimum child zones aligned
input bool            InpFFlatParent = false;     // Allow trade if parent is flat
input bool            InpFIgnoreNa   = true;      // Ignore zones without data
input bool            InpFHtfClosed  = true;      // Higher-TF zones use the last CLOSED bar
input bool            InpFUseZ1      = true;      // Use child zone 1
input ENUM_TIMEFRAMES InpFZTf1       = PERIOD_H1; // Zone 1 timeframe (current = filter timeframe)
input bool            InpFUseZ2      = true;      // Use child zone 2
input ENUM_TIMEFRAMES InpFZTf2       = PERIOD_H2; // Zone 2 timeframe (current = filter timeframe)
input bool            InpFUseZ3      = true;      // Use child zone 3
input ENUM_TIMEFRAMES InpFZTf3       = PERIOD_H4; // Zone 3 timeframe (current = filter timeframe)
input bool            InpFUseZ4      = false;     // Use child zone 4
input ENUM_TIMEFRAMES InpFZTf4       = PERIOD_H8; // Zone 4 timeframe (current = filter timeframe)
input bool            InpFUseZ5      = false;     // Use child zone 5
input ENUM_TIMEFRAMES InpFZTf5       = PERIOD_M1; // Zone 5 timeframe (current = filter timeframe)
input bool            InpFUseZ6      = false;     // Use child zone 6
input ENUM_TIMEFRAMES InpFZTf6       = PERIOD_M2; // Zone 6 timeframe (current = filter timeframe)

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
   datetime          waitFrom; // first load: waiting for the history since
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

                     CTf(void) : tf(PERIOD_CURRENT), n(0), rsiLen(14), fastLen(2), xLen(0), waitFrom(0) {}
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
      // accept the first load once the series is synchronized and starts
      // near 'from' (or the broker has nothing older); stop waiting after 30 s
      bool     synced   = SeriesInfoInteger(_Symbol, tf, SERIES_SYNCHRONIZED) != 0;
      datetime srvFirst = (datetime)SeriesInfoInteger(_Symbol, tf, SERIES_SERVER_FIRSTDATE);
      long     gap      = PeriodSeconds(tf) > 7 * 86400 ? (long)PeriodSeconds(tf) : (long)7 * 86400;
      bool     starts   = (long)r[0].time <= (long)from + gap || (srvFirst > 0 && srvFirst >= r[0].time);
      if(!synced || !starts)
        {
         if(waitFrom == 0)
            waitFrom = TimeLocal();
         if(TimeLocal() - waitFrom < 30)
            return -1;
        }
      waitFrom = 0;
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
   datetime          nextTry; // no new attempt before this time (after a failure)
   bool              triggered; // the stop was hit and the filter allowed it: retries
                                // no longer need the price or the filter again
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
CFlashGold      g_sig;               // the strategy's signal (trading timeframe)
CFlashGold      g_flt;               // the direction filter (filter timeframe)
ENUM_TIMEFRAMES g_tradeTf;
double          g_pt = 0.0;
datetime        g_base = 0;          // history is counted back from here
bool            g_sigReset = true;
bool            g_fltReset = true;
datetime        g_fltBar = 0;        // filter candle the filter was last refreshed on
datetime        g_lastBar = 0;
FgPending       g_pL;
FgPending       g_pS;
bool            g_hedging = true;
bool            g_closeL = false;    // an exit of the longs is still owed (retried)
bool            g_closeS = false;
bool            g_snapOk = false;    // positions at the end of the last tick
bool            g_snapL = false;
bool            g_snapS = false;
datetime        g_trailNextTry = 0;
bool            g_foreignWarned = false;
string          g_lvlName = "";
bool            g_lvlDrawn = false;
double          g_lvlPx = 0.0;
color           g_lvlCol = clrNONE;
int             g_lvlStyle = -1;
string          g_lastComment = "";

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
   q.active  = false;
   q.price   = 0.0;
   q.lots    = 0.0;
   q.sl      = EMPTY_VALUE;
   q.tp      = EMPTY_VALUE;
   q.act     = EMPTY_VALUE;
   q.dst     = EMPTY_VALUE;
   q.placed  = 0;
   q.nextTry = 0;
   q.triggered = false;
  }

double TickSize(void)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return ts > 0.0 ? ts : _Point;
  }

// Prices on the symbol's tick grid, rounded away from the market.
double RoundDn(const double price)
  {
   double ts = TickSize();
   return NormalizeDouble(MathFloor(price / ts + 1e-9) * ts, _Digits);
  }

double RoundUp(const double price)
  {
   double ts = TickSize();
   return NormalizeDouble(MathCeil(price / ts - 1e-9) * ts, _Digits);
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

// Open time of the newest position of this EA on that side, or of any side
// (0 if none).
datetime NewestPosTime(const ENUM_POSITION_TYPE type, const bool anySide)
  {
   datetime latest = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      if(!anySide && (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
         continue;
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(ot > latest)
         latest = ot;
     }
   return latest;
  }

// Closes this EA's positions on one side. True when all of them were closed
// (or there was none).
bool ClosePos(const ENUM_POSITION_TYPE type)
  {
   bool ok = true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
         continue;
      bool sent = g_trade.PositionClose(tk);
      uint rc   = g_trade.ResultRetcode();
      if(!sent || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
        {
         ok = false;
         PrintFormat("FlashGold EA: close failed, retcode %u (%s)", rc, g_trade.ResultRetcodeDescription());
        }
     }
   return ok;
  }

// On a netting account one position holds every trade of the symbol: a
// manual or other-EA position there must not be traded into.
bool ForeignPosition(void)
  {
   if(g_hedging || !PositionSelect(_Symbol))
      return false;
   bool foreign = PositionGetInteger(POSITION_MAGIC) != InpMagic;
   if(foreign && !g_foreignWarned)
     {
      Print("FlashGold EA: netting account with a position of another magic number on ", _Symbol, ": entries wait until it is closed.");
      g_foreignWarned = true;
     }
   if(!foreign)
      g_foreignWarned = false;
   return foreign;
  }

// Trailing parameters of a position, kept in terminal global variables so
// they survive an EA restart. Keyed by POSITION_IDENTIFIER (the ticket of the
// order that opened the position).
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

// Deletes the trail records of closed positions: a record unread for a day
// whose position is no longer open (on any symbol or chart).
void TrailCleanup(void)
  {
   string pre = "FGEA_" + IntegerToString(InpMagic) + "_";
   for(int i = GlobalVariablesTotal() - 1; i >= 0; i--)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, pre) != 0 || TimeLocal() - GlobalVariableTime(name) <= 86400)
         continue;
      long id   = StringToInteger(StringSubstr(name, StringLen(pre)));   // stops at the '_'
      bool open = false;
      for(int j = PositionsTotal() - 1; j >= 0 && !open; j--)
         if(PositionGetTicket(j) > 0 && PositionGetInteger(POSITION_IDENTIFIER) == id)
            open = true;
      if(!open)
         GlobalVariableDel(name);
     }
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
// SL / TP of a position entered at 'ref': the locked distances from the
// entry, pushed out where needed to clear the stops level from the price the
// server checks them against (Bid for a buy, Ask for a sell), on the tick grid.
void Levels(const bool buy, const double ref, const FgPending &q, double &sl, double &tp)
  {
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double ts   = TickSize();
   double minD = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   sl = 0.0;
   tp = 0.0;
   if(q.sl != EMPTY_VALUE && q.sl > 0.0)
      sl = buy ? RoundDn(MathMin(ref - q.sl * g_pt, bid - minD - ts)) : RoundUp(MathMax(ref + q.sl * g_pt, ask + minD + ts));
   if(q.tp != EMPTY_VALUE && q.tp > 0.0)
      tp = buy ? RoundUp(MathMax(ref + q.tp * g_pt, bid + minD + ts)) : RoundDn(MathMin(ref - q.tp * g_pt, ask - minD - ts));
  }

// Opens at market with the pending's locked SL / TP. Returns the trade
// server's return code (TRADE_RETCODE_DONE when the position is open).
uint OpenPos(const bool buy, const FgPending &q)
  {
   double px = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0.0, tp = 0.0;
   Levels(buy, px, q, sl, tp);
   bool sent = buy ? g_trade.Buy(q.lots, _Symbol, 0.0, sl, tp, "FG buy stop")
               : g_trade.Sell(q.lots, _Symbol, 0.0, sl, tp, "FG sell stop");
   uint rc = g_trade.ResultRetcode();
   if(!sent || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
     {
      PrintFormat("FlashGold EA: %s failed, retcode %u (%s)", buy ? "buy" : "sell", rc, g_trade.ResultRetcodeDescription());
      return rc == 0 ? (uint)TRADE_RETCODE_ERROR : rc;
     }
   // the position's identifier is the ticket of the order that opened it
   // (no need to find it in the position list, which can lag)
   long id = (long)g_trade.ResultOrder();
   if(id <= 0)
     {
      ulong deal = g_trade.ResultDeal();
      if(deal > 0 && HistoryDealSelect(deal))
         id = HistoryDealGetInteger(deal, DEAL_POSITION_ID);
     }
   if(id <= 0)
     {
      Print("FlashGold EA: the new position's id is unknown; its trailing stop is not stored.");
      return (uint)TRADE_RETCODE_DONE;
     }
   if(InpUseTrail && q.act != EMPTY_VALUE && q.dst != EMPTY_VALUE)
      TrailSave(id, q.act, q.dst);
   // SL / TP from the actual fill, as the strategy measures them from the
   // entry price (the order carried them from the quote, so it is never
   // left unprotected)
   if(PositionSelectByTicket((ulong)id))
     {
      double fill = PositionGetDouble(POSITION_PRICE_OPEN);
      if(MathAbs(fill - px) >= _Point * 0.5)
        {
         double sl2 = 0.0, tp2 = 0.0;
         Levels(buy, fill, q, sl2, tp2);
         if(sl2 != sl || tp2 != tp)
            g_trade.PositionModify((ulong)id, sl2, tp2);
        }
     }
   return (uint)TRADE_RETCODE_DONE;
  }

// After a failed attempt: try again in a few seconds, or at the next candle
// when the server's answer will not change by itself.
void Backoff(FgPending &q, const uint rc)
  {
   bool hard = rc == TRADE_RETCODE_NO_MONEY || rc == TRADE_RETCODE_INVALID_VOLUME || rc == TRADE_RETCODE_TRADE_DISABLED ||
               rc == TRADE_RETCODE_MARKET_CLOSED || rc == TRADE_RETCODE_INVALID_STOPS || rc == TRADE_RETCODE_LIMIT_POSITIONS ||
               rc == TRADE_RETCODE_LIMIT_VOLUME;
   q.nextTry = hard ? iTime(_Symbol, g_tradeTf, 0) + PeriodSeconds(g_tradeTf) : TimeCurrent() + 5;
  }

// Trailing stop (strategy.exit trail_points / trail_offset): once the profit
// reaches 'act' ticks, the stop follows 'dst' ticks behind the best price. It
// moves in steps of at least "Trail step" and respects the freeze level.
void ManageTrailing(void)
  {
   if(!InpUseTrail || TimeCurrent() < g_trailNextTry)
      return;
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double minD = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double frz  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL) * _Point;
   double gap  = MathMax(minD, frz);
   double ts   = TickSize();
   double step = MathMax(_Point, InpTrailStepPts * g_pt);
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
      bool   send = false;
      double nsl  = 0.0;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
        {
         if((bid - open) / g_pt >= act)
           {
            // at the trail distance, or the closest the server allows
            nsl  = RoundDn(MathMin(bid - dst * g_pt, bid - gap - ts));
            send = (sl == 0.0 || nsl >= sl + step) && (sl == 0.0 || frz == 0.0 || bid - sl > frz) && (tp == 0.0 || tp - bid > gap);
           }
        }
      else
        {
         if((open - ask) / g_pt >= act)
           {
            nsl  = RoundUp(MathMax(ask + dst * g_pt, ask + gap + ts));
            send = (sl == 0.0 || nsl <= sl - step) && (sl == 0.0 || frz == 0.0 || sl - ask > frz) && (tp == 0.0 || ask - tp > gap);
           }
        }
      if(send && !g_trade.PositionModify(tk, nsl, tp))
         g_trailNextTry = TimeCurrent() + 2;
     }
  }

// Retries an exit that failed (close on the opposite signal, time stop), at
// most once a second, until that side is flat.
void RetryCloses(void)
  {
   static datetime lastTry = 0;
   if(!g_closeL && !g_closeS)
      return;
   datetime now = TimeCurrent();
   if(now == lastTry)
      return;
   lastTry = now;
   if(g_closeL)
      g_closeL = CountPos(POSITION_TYPE_BUY) > 0 && !ClosePos(POSITION_TYPE_BUY);
   if(g_closeS)
      g_closeS = CountPos(POSITION_TYPE_SELL) > 0 && !ClosePos(POSITION_TYPE_SELL);
  }

// A position opened from a pending whose order answer was lost: give it the
// pending's trail record and SL / TP from its fill, as OpenPos would have.
void AdoptFill(const ENUM_POSITION_TYPE type, const FgPending &q)
  {
   bool buy = type == POSITION_TYPE_BUY;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine() || (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
         continue;
      if((datetime)PositionGetInteger(POSITION_TIME) < q.placed)
         continue;
      long   id = PositionGetInteger(POSITION_IDENTIFIER);
      double a  = 0.0, d = 0.0;
      if(TrailLoad(id, a, d))
         continue;   // already recorded by OpenPos
      if(InpUseTrail && q.act != EMPTY_VALUE && q.dst != EMPTY_VALUE)
         TrailSave(id, q.act, q.dst);
      double sl  = PositionGetDouble(POSITION_SL);
      double tp  = PositionGetDouble(POSITION_TP);
      double sl2 = 0.0, tp2 = 0.0;
      Levels(buy, PositionGetDouble(POSITION_PRICE_OPEN), q, sl2, tp2);
      if(sl2 != sl || tp2 != tp)
         g_trade.PositionModify(tk, sl2, tp2);
     }
  }

// An entry stop whose side is already in a position opened since the stop
// was placed has filled (even if the order's answer was lost): adopt that
// position and cancel both stops (OCA).
void ReconcilePendings(void)
  {
   if(g_pL.active && CountPos(POSITION_TYPE_BUY) > 0 && NewestPosTime(POSITION_TYPE_BUY, false) >= g_pL.placed)
     {
      AdoptFill(POSITION_TYPE_BUY, g_pL);
      PendingClear(g_pL);
      PendingClear(g_pS);
     }
   if(g_pS.active && CountPos(POSITION_TYPE_SELL) > 0 && NewestPosTime(POSITION_TYPE_SELL, false) >= g_pS.placed)
     {
      AdoptFill(POSITION_TYPE_SELL, g_pS);
      PendingClear(g_pS);
      PendingClear(g_pL);
     }
  }

// The strategy's order block, at the close of candle k (run on the first
// tick of the next candle, where TradingView would fill these orders).
void OnCandleClose(const int k)
  {
   ReconcilePendings();
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

   // the position at the candle's close: as seen on its last tick (a stop
   // hit on the first tick of this candle happened after that close)
   bool allowL  = InpDirection != FG_DIR_SHORT;
   bool allowS  = InpDirection != FG_DIR_LONG;
   bool inLong  = g_snapOk ? g_snapL : CountPos(POSITION_TYPE_BUY) > 0;
   bool inShort = g_snapOk ? g_snapS : CountPos(POSITION_TYPE_SELL) > 0;
   bool flat    = !inLong && !inShort;

   // opposite-signal handling on an open position (retried if it fails)
   if(InpExitOnOpp && sellSignal && inLong && !ClosePos(POSITION_TYPE_BUY))
      g_closeL = true;
   if(InpExitOnOpp && buySignal && inShort && !ClosePos(POSITION_TYPE_SELL))
      g_closeS = true;

   // long entry: stop at the signal's entry price
   if(buySignal && allowL && !inLong && (flat || InpAllowReverse || InpExitOnOpp))
     {
      double qL = CalcLots(slTicksNow);
      if(qL > 0.0 && buyEntryPrice != EMPTY_VALUE)
        {
         g_pL.active  = true;
         g_pL.price   = buyEntryPrice;
         g_pL.lots    = qL;
         g_pL.sl      = slTicksNow;
         g_pL.tp      = tpTicksNow;
         g_pL.act     = trailActNow;
         g_pL.dst     = trailDstNow;
         g_pL.placed  = g_sig.tfs[g_sig.fi].t[k];
         g_pL.nextTry = 0;
         g_pL.triggered = false;
        }
     }

   // short entry
   if(sellSignal && allowS && !inShort && (flat || InpAllowReverse || InpExitOnOpp))
     {
      double qS = CalcLots(slTicksNow);
      if(qS > 0.0 && sellEntryPrice != EMPTY_VALUE)
        {
         g_pS.active  = true;
         g_pS.price   = sellEntryPrice;
         g_pS.lots    = qS;
         g_pS.sl      = slTicksNow;
         g_pS.tp      = tpTicksNow;
         g_pS.act     = trailActNow;
         g_pS.dst     = trailDstNow;
         g_pS.placed  = g_sig.tfs[g_sig.fi].t[k];
         g_pS.nextTry = 0;
         g_pS.triggered = false;
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

   // time stop (entry candle of the newest open position; retried if a
   // close fails)
   if(InpMaxBarsHeld > 0 && !flat)
     {
      datetime ot = NewestPosTime(POSITION_TYPE_BUY, true);
      int      eb = ot > 0 ? g_sig.tfs[g_sig.fi].LastOpenBy(ot) : -1;
      if(eb >= 0 && k - eb >= InpMaxBarsHeld)
        {
         if(!ClosePos(POSITION_TYPE_BUY))
            g_closeL = true;
         if(!ClosePos(POSITION_TYPE_SELL))
            g_closeS = true;
        }
     }
   TrailCleanup();
  }

// Triggers the EA-held stops when the chart price (Bid) reaches them and the
// direction filter allows that side at this moment. A blocked stop stays
// pending; when one side opens, the other side's stop is cancelled (OCA). A
// failed attempt waits (Backoff) instead of resending on every tick.
void CheckPendings(void)
  {
   ReconcilePendings();
   if(!g_pL.active && !g_pS.active)
      return;
   double   bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   datetime now = TimeCurrent();
   if(g_pL.active && (g_pL.triggered || bid >= g_pL.price) && now >= g_pL.nextTry && CountPos(POSITION_TYPE_BUY) == 0 && !ForeignPosition())
     {
      bool ok = g_pL.triggered;
      if(!ok)
        {
         FgPerm r;
         FilterPermission(r);
         ok = r.buyOk;
        }
      if(ok)
        {
         // hit and allowed: like a filled stop, retries (after a failure) no
         // longer wait for the price or the filter, so a reversal is completed
         g_pL.triggered = true;
         // the long reverses an open short
         if(CountPos(POSITION_TYPE_SELL) > 0 && !ClosePos(POSITION_TYPE_SELL))
           {
            g_pL.nextTry = now + 5;
            return;
           }
         uint rc = OpenPos(true, g_pL);
         if(rc == TRADE_RETCODE_DONE || CountPos(POSITION_TYPE_BUY) > 0)
           {
            if(rc != TRADE_RETCODE_DONE)
               AdoptFill(POSITION_TYPE_BUY, g_pL);
            PendingClear(g_pL);
            PendingClear(g_pS);
            return;
           }
         Backoff(g_pL, rc);
        }
     }
   if(g_pS.active && (g_pS.triggered || bid <= g_pS.price) && now >= g_pS.nextTry && CountPos(POSITION_TYPE_SELL) == 0 && !ForeignPosition())
     {
      bool ok = g_pS.triggered;
      if(!ok)
        {
         FgPerm r;
         FilterPermission(r);
         ok = r.sellOk;
        }
      if(ok)
        {
         g_pS.triggered = true;
         if(CountPos(POSITION_TYPE_BUY) > 0 && !ClosePos(POSITION_TYPE_BUY))
           {
            g_pS.nextTry = now + 5;
            return;
           }
         uint rc = OpenPos(false, g_pS);
         if(rc == TRADE_RETCODE_DONE || CountPos(POSITION_TYPE_SELL) > 0)
           {
            if(rc != TRADE_RETCODE_DONE)
               AdoptFill(POSITION_TYPE_SELL, g_pS);
            PendingClear(g_pS);
            PendingClear(g_pL);
            return;
           }
         Backoff(g_pS, rc);
        }
     }
  }

//+------------------------------------------------------------------+
//| Status text and the filter level on the chart (skipped in         |
//| non-visual tests; objects only touched when something changes)    |
//+------------------------------------------------------------------+
void LevelLineHide(void)
  {
   if(g_lvlDrawn)
      ObjectDelete(0, g_lvlName);
   g_lvlDrawn = false;
  }

void ShowStatus(const bool fltReady)
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   FgPerm r;
   FilterPermission(r);
   if(InpFDrawLevel && InpFOn && fltReady && r.level != EMPTY_VALUE && r.armed)
     {
      color col   = r.sigDir > 0 ? FG_LIME : FG_RED;
      int   style = r.isOpen ? STYLE_SOLID : STYLE_DOT;
      if(!g_lvlDrawn || ObjectFind(0, g_lvlName) < 0)
        {
         ObjectCreate(0, g_lvlName, OBJ_HLINE, 0, 0, r.level);
         ObjectSetInteger(0, g_lvlName, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, g_lvlName, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, g_lvlName, OBJPROP_HIDDEN, true);
         g_lvlDrawn = true;
         g_lvlPx    = 0.0;
         g_lvlCol   = clrNONE;
         g_lvlStyle = -1;
        }
      if(r.level != g_lvlPx)
         ObjectSetDouble(0, g_lvlName, OBJPROP_PRICE, 0, r.level);
      if(col != g_lvlCol)
         ObjectSetInteger(0, g_lvlName, OBJPROP_COLOR, col);
      if(style != g_lvlStyle)
         ObjectSetInteger(0, g_lvlName, OBJPROP_STYLE, style);
      g_lvlPx    = r.level;
      g_lvlCol   = col;
      g_lvlStyle = style;
     }
   else
      LevelLineHide();
   if(!InpShowStatus)
      return;

   string tag = TfText(g_flt.p.tf);
   string txt = "FlashGold v5 EA  (" + TfText(g_tradeTf) + ", magic " + IntegerToString(InpMagic) + ")\n";
   if(!InpFOn)
      txt += "Direction filter: OFF (every entry allowed)\n";
   else
      if(!fltReady)
         txt += "Filter " + tag + ": loading its history... (entries wait)\n";
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
         txt += "  " + (r.onSigBar && r.sigDir > 0 ? "Buy >= " : "Buy  > ") + lv + "  " + (r.buyOk ? "ALLOWED" : "BLOCKED") +
                "   |   " + (r.onSigBar && r.sigDir < 0 ? "Sell <= " : "Sell < ") + lv + "  " + (r.sellOk ? "ALLOWED" : "BLOCKED") +
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
   if(txt != g_lastComment)
     {
      Comment(txt);
      g_lastComment = txt;
     }
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
   p.parentTf     = Resolve(InpSParentTf, p.tf);
   p.rsiLen       = InpSRsiLen;
   p.fastLen      = InpSFastLen;
   p.minAligned   = InpSMinAligned;
   p.flatParent   = InpSFlatParent;
   p.ignoreNa     = InpSIgnoreNa;
   p.htfClosed    = InpSHtfClosed;
   p.useZ[0] = InpSUseZ1;
   p.zTf[0]  = Resolve(InpSZTf1, p.tf);
   p.useZ[1] = InpSUseZ2;
   p.zTf[1]  = Resolve(InpSZTf2, p.tf);
   p.useZ[2] = InpSUseZ3;
   p.zTf[2]  = Resolve(InpSZTf3, p.tf);
   p.useZ[3] = InpSUseZ4;
   p.zTf[3]  = Resolve(InpSZTf4, p.tf);
   p.useZ[4] = InpSUseZ5;
   p.zTf[4]  = Resolve(InpSZTf5, p.tf);
   p.useZ[5] = InpSUseZ6;
   p.zTf[5]  = Resolve(InpSZTf6, p.tf);
   p.levelMode = FGF_LEVEL_ENTRY;
  }

// "current" parent / zone timeframes of the filter = the filter timeframe
// (every filter input works as on that timeframe's own chart).
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
   p.parentTf     = Resolve(InpFParentTf, p.tf);
   p.rsiLen       = InpFRsiLen;
   p.fastLen      = InpFFastLen;
   p.minAligned   = InpFMinAligned;
   p.flatParent   = InpFFlatParent;
   p.ignoreNa     = InpFIgnoreNa;
   p.htfClosed    = InpFHtfClosed;
   p.useZ[0] = InpFUseZ1;
   p.zTf[0]  = Resolve(InpFZTf1, p.tf);
   p.useZ[1] = InpFUseZ2;
   p.zTf[1]  = Resolve(InpFZTf2, p.tf);
   p.useZ[2] = InpFUseZ3;
   p.zTf[2]  = Resolve(InpFZTf3, p.tf);
   p.useZ[3] = InpFUseZ4;
   p.zTf[3]  = Resolve(InpFZTf4, p.tf);
   p.useZ[4] = InpFUseZ5;
   p.zTf[4]  = Resolve(InpFZTf5, p.tf);
   p.useZ[5] = InpFUseZ6;
   p.zTf[5]  = Resolve(InpFZTf6, p.tf);
   p.levelMode = InpFLvMode;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpEntryValid < 0 || InpMaxBarsHeld < 0 || InpAtrLen < 1 || InpSlAtrMult < 0.1 || InpTpR < 0.0 || InpTrailDstAtr < 0.05 ||
      InpTrailPts < 1.0 || InpSlPoints < 0.0 || InpTpPoints < 0.0 || InpTrailActPts < 0.0 || InpTrailActAtr < 0.0 || InpTrailStepPts < 0.0 ||
      InpFixedLots < 0.0 || InpRiskPct < 0.0 || InpMaxLots < 0.0 || InpSlippage < 0 ||
      InpSRsiLen < 2 || InpSFastLen < 1 || InpSMinAligned < 0 || InpSMinAligned > 6 || InpSDriftBars < 1 || InpSHoldBars < 0 ||
      InpSSpreadPts < 0.0 || InpSEntryDistPts < 0.0 || InpSHoldFavPts < 0.0 || InpSBurstAtr < 0.0 || InpSEntryDistAtr < 0.0 ||
      InpSHoldFavAtr < 0.0 || InpSBurstPts < 0.0 ||
      InpFRsiLen < 2 || InpFFastLen < 1 || InpFMinAligned < 0 || InpFMinAligned > 6 || InpFDriftBars < 1 || InpFHoldBars < 0 ||
      InpFSpreadPts < 0.0 || InpFEntryDistPts < 0.0 || InpFHoldFavPts < 0.0 || InpFBurstAtr < 0.0 || InpFEntryDistAtr < 0.0 ||
      InpFHoldFavAtr < 0.0 || InpFBurstPts < 0.0 ||
      InpFMinutes < 1 || InpFBars < 1 || InpTickSize < 0.0 || InpWarmup < 1)
     {
      Print("FlashGold EA: an input is out of range (see the TradingView minimums).");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_tradeTf = Resolve(InpTradeTf, Period());
   g_pt      = InpTickSize > 0.0 ? InpTickSize : _Point;
   g_hedging = AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING;

   if(InpFOn && InpFCheck == FGF_CHECK_TICK && InpFLast == FGF_LASTS_CANDLES && InpFBars == 1)
      Print("FlashGold EA: warning - Check price on = Tick with Permission lasts = Candles 1 never allows an entry ",
            "(the signal candle has closed when its signal is known). Use Candles >= 2, or Candle open / Candle close.");
   if(MQLInfoInteger(MQL_TESTER) && PeriodSeconds(Period()) > PeriodSeconds(g_tradeTf))
      Print("FlashGold EA: warning - the tester's period is above the trading timeframe; use 'Every tick' modelling ",
            "with a period at or below ", TfText(g_tradeTf), " so every trading candle and stop is seen.");

   FgParams sp;
   StrategyParams(sp);
   g_sig.Init(sp, g_pt, InpAtrLen);
   FgParams fp;
   FilterParams(fp);
   g_flt.Init(fp, g_pt, 0);

   g_trade.SetExpertMagicNumber((ulong)InpMagic);
   g_trade.SetDeviationInPoints((ulong)InpSlippage);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   // an input edit or a chart change re-initialises the EA without unloading
   // it: keep the entry stops for the same symbol, magic and trading
   // timeframe, minus a side the new Direction no longer allows
   static ENUM_TIMEFRAMES s_prevTf    = PERIOD_CURRENT;
   static string          s_prevSym   = "";
   static long            s_prevMagic = 0;
   int  ur   = UninitializeReason();
   bool keep = (ur == REASON_PARAMETERS || ur == REASON_CHARTCHANGE) && s_prevTf == g_tradeTf &&
               s_prevSym == _Symbol && s_prevMagic == InpMagic;
   if(!keep)
     {
      PendingClear(g_pL);
      PendingClear(g_pS);
      g_lastBar = 0;
      g_closeL  = false;
      g_closeS  = false;
     }
   else
     {
      if(InpDirection == FG_DIR_SHORT)
         PendingClear(g_pL);
      if(InpDirection == FG_DIR_LONG)
         PendingClear(g_pS);
     }
   s_prevTf    = g_tradeTf;
   s_prevSym   = _Symbol;
   s_prevMagic = InpMagic;

   g_base       = TimeCurrent();
   g_sigReset   = true;
   g_fltReset   = true;
   g_fltBar     = 0;
   g_snapOk     = false;
   g_lvlName    = "FGEA_" + IntegerToString(InpMagic) + "_level";
   g_lvlDrawn   = false;
   g_lastComment = "";
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Comment("");
   ObjectDelete(0, g_lvlName);
   g_lvlDrawn = false;
  }

void OnTick()
  {
   // exits first: they never wait for history or the filter
   ManageTrailing();
   RetryCloses();

   // the direction filter: refreshed on each new filter candle (its closed
   // candles do not change in between); entries wait while it is not ready
   bool fltReady = !InpFOn;
   if(InpFOn)
     {
      datetime fb = iTime(_Symbol, g_flt.p.tf, 0);
      if(fb != 0 && (g_fltReset || fb != g_fltBar))
        {
         int rf = g_flt.Update(g_base, InpWarmup, g_fltReset);
         if(rf == 0)
           {
            g_fltReset = false;
            g_fltBar   = fb;
           }
         else
            if(rf == -2)
              {
               g_fltReset = true;
               g_fltBar   = 0;
              }
        }
      fltReady = fb != 0 && !g_fltReset && fb == g_fltBar && g_flt.stN > 0;
     }

   // the strategy: once per trading candle, at its close
   datetime bar0 = iTime(_Symbol, g_tradeTf, 0);
   if(bar0 != 0 && bar0 != g_lastBar)
     {
      int rs = g_sig.Update(g_base, InpWarmup, g_sigReset);
      if(rs == -2)
         g_sigReset = true;
      else
         if(rs == 0)
           {
            g_sigReset = false;
            // the candle that just closed; not on the first tick after start
            // (its signal is history, the EA was not running when it closed)
            int k = g_sig.tfs[g_sig.fi].LastOpenBy(bar0 - 1);
            if(g_lastBar != 0 && k >= 0 && k < g_sig.stN)
              {
               int kPrev = g_sig.tfs[g_sig.fi].LastOpenBy(g_lastBar);
               if(kPrev >= 0 && k - kPrev > 0)
                  PrintFormat("FlashGold EA: %d trading candle(s) closed without being processed (no ticks or no data)", k - kPrev);
               OnCandleClose(k);
              }
            g_lastBar = bar0;
           }
     }

   // entries wait until the candle that closed has been processed (its
   // order block can cancel or replace the stops)
   bool closeDone = bar0 != 0 && bar0 == g_lastBar;
   if(fltReady && closeDone)
      CheckPendings();
   ShowStatus(fltReady);

   // the positions at the end of this tick (the state at a candle's close),
   // kept from the last tick of a candle whose close is not processed yet
   if(closeDone)
     {
      g_snapL  = CountPos(POSITION_TYPE_BUY) > 0;
      g_snapS  = CountPos(POSITION_TYPE_SELL) > 0;
      g_snapOk = true;
     }
  }
//+------------------------------------------------------------------+
