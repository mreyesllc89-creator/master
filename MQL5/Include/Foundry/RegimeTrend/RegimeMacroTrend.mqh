//+------------------------------------------------------------------+
//|                                              RegimeMacroTrend.mqh |
//|      Macro trend axis - HTF EMA slope, independent of the regime |
//+------------------------------------------------------------------+
//| This answers a DIFFERENT question from the state machine: not     |
//| "is the market moving efficiently right now" but "which way is    |
//| the slow structural trend pointing". It is deliberately NOT fed   |
//| into CRegimeStateMachine and is never forced to Flat when the     |
//| regime turns choppy - the whole point is that it keeps reporting  |
//| the macro direction while the regime layer is warning you not to  |
//| trust the current bar-to-bar noise.                                |
//|                                                                    |
//| Method: an EMA on its own (usually slower) higher timeframe, its   |
//| slope measured over InpMacroSlopeBars HTF bars, classified Up /    |
//| Down / Flat with a percentage deadband so a nearly-flat EMA does   |
//| not flicker sign on noise alone. The classification is then run   |
//| through a minimum-dwell debounce, in HTF-bar units.                |
//|                                                                    |
//| CalculateRaw() is a pure, stateless mapping, exactly like          |
//| RegimeER.mqh: it always recomputes the classification of the      |
//| currently closed HTF bar from scratch and never repaints, because  |
//| a closed HTF bar's own classification cannot change.               |
//|                                                                    |
//| The min-dwell debounce is a DIFFERENT matter: it is a genuine      |
//| recursion (today's answer depends on yesterday's), so - exactly    |
//| like the core state machine - it MUST live in a real indicator     |
//| buffer that bar i reads from bar i-1, never in a value recomputed  |
//| fresh from an arbitrary truncated window. (An earlier version of   |
//| this file tried to get away with a "bounded automaton always      |
//| re-syncs within min_dwell steps" argument and recompute it fresh   |
//| every call; that argument is false in general - it only holds if  |
//| the fetched window happens to contain min_dwell identical raw      |
//| readings, which a truncation point is not guaranteed to catch, so  |
//| two differently-sized windows could disagree forever at the same   |
//| bar. Real persistence removes the question entirely.)              |
//|                                                                    |
//| The debounce must also only take a step once per HTF bar close,    |
//| not once per chart bar - otherwise "InpMacroMinDwell" would        |
//| silently mean chart bars instead of the HTF bars its name and      |
//| its input description promise. CalculateRaw() therefore also       |
//| reports, per chart bar, whether a new HTF bar has just closed      |
//| (boundary_out[]); the host only steps the debounce on that bar.    |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

#include "RegimeTypes.mqh"

//+------------------------------------------------------------------+
//| Class CMacroTrendEngine                                          |
//+------------------------------------------------------------------+
class CMacroTrendEngine
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_ema_period;
   int               m_slope_bars;
   double            m_deadband_pct;
   int               m_min_dwell;
   //--- scratch buffers, reused between calls
   double            m_htf_close[];
   datetime          m_htf_time[];
   double            m_htf_ema[];
   int               m_htf_raw[];

   int               ClassifyOf(const double ema_now,const double ema_prev) const;
   datetime          ClosedHtfTimeAt(const datetime bar_time) const;

public:
                     CMacroTrendEngine(void);
                    ~CMacroTrendEngine(void);

   bool              Init(const string symbol,const ENUM_TIMEFRAMES tf,
                          const int ema_period,const int slope_bars,
                          const double deadband_pct,const int min_dwell);
   int               MinDwell(void) const { return(m_min_dwell); }

   //--- One step of the min-dwell debounce, applied by the host to its
   //--- own persistent buffers - see the file header for why this
   //--- cannot be folded into a stateless recompute.
   void              Step(const int prev_trend,const int prev_dwell,const int raw,
                          int &out_trend,int &out_dwell) const;

   //--- Fills, for chart bars [first .. rates_total-1]:
   //---   raw_out[i]      REGIME_MACRO_UP/DOWN/FLAT/UNSET, the closed
   //---                   HTF bar's classification (pure function of
   //---                   history, never repaints)
   //---   boundary_out[i] 1 if a NEW HTF bar closed between chart bar
   //---                   i-1 and i (or i has no prior bar), else 0
   //--- Returns false when the higher timeframe is not ready yet;
   //--- both arrays are left untouched then.
   bool              CalculateRaw(const int rates_total,const int first,
                                  const datetime &time[],
                                  double &raw_out[],int &boundary_out[]);
  };

//+------------------------------------------------------------------+
CMacroTrendEngine::CMacroTrendEngine(void) : m_symbol(""),
                                             m_tf(PERIOD_H4),
                                             m_ema_period(50),
                                             m_slope_bars(3),
                                             m_deadband_pct(0.05),
                                             m_min_dwell(2)
  {
  }
//+------------------------------------------------------------------+
CMacroTrendEngine::~CMacroTrendEngine(void)
  {
  }
//+------------------------------------------------------------------+
bool CMacroTrendEngine::Init(const string symbol,const ENUM_TIMEFRAMES tf,
                             const int ema_period,const int slope_bars,
                             const double deadband_pct,const int min_dwell)
  {
   if(ema_period < 2 || slope_bars < 1 || deadband_pct < 0.0 || min_dwell < 1)
      return(false);
   m_symbol       = symbol;
   m_tf           = tf;
   m_ema_period   = ema_period;
   m_slope_bars   = slope_bars;
   m_deadband_pct = deadband_pct;
   m_min_dwell    = min_dwell;
   ArraySetAsSeries(m_htf_close,false);
   ArraySetAsSeries(m_htf_time,false);
   ArraySetAsSeries(m_htf_ema,false);
   ArraySetAsSeries(m_htf_raw,false);
   return(true);
  }
//+------------------------------------------------------------------+
//| Up / Down / Flat from the relative EMA slope, or UNSET if either  |
//| endpoint is not defined yet (still inside the EMA's own warm-up). |
//+------------------------------------------------------------------+
int CMacroTrendEngine::ClassifyOf(const double ema_now,const double ema_prev) const
  {
   if(ema_now == EMPTY_VALUE || ema_prev == EMPTY_VALUE || ema_prev == 0.0)
      return(REGIME_MACRO_UNSET);
   double rel_pct = (ema_now - ema_prev) / ema_prev * 100.0;
   if(rel_pct > m_deadband_pct)
      return(REGIME_MACRO_UP);
   if(rel_pct < -m_deadband_pct)
      return(REGIME_MACRO_DOWN);
   return(REGIME_MACRO_FLAT);
  }
//+------------------------------------------------------------------+
//| The closed HTF bar's own open time as of `bar_time`, found        |
//| independently of the batch window below (iBarShift/iTime give the |
//| same absolute answer regardless of when they are called, so this  |
//| is safe to compare against a value computed on a different tick). |
//| iBarShift returns 0 = most recent bar, growing into the past; the |
//| bar AT that shift is the one still forming as of bar_time, so the |
//| previous (closed) one is one shift further back.                  |
//+------------------------------------------------------------------+
datetime CMacroTrendEngine::ClosedHtfTimeAt(const datetime bar_time) const
  {
   int shift = iBarShift(m_symbol,m_tf,bar_time,false);
   if(shift < 0)
      return(0);
   int closed_shift = shift + 1;
   if(closed_shift >= Bars(m_symbol,m_tf))
      return(0);
   return(iTime(m_symbol,m_tf,closed_shift));
  }
//+------------------------------------------------------------------+
void CMacroTrendEngine::Step(const int prev_trend,const int prev_dwell,const int raw,
                             int &out_trend,int &out_dwell) const
  {
   if(raw == REGIME_MACRO_UNSET)
     {
      out_trend = REGIME_MACRO_UNSET;
      out_dwell = 0;
      return;
     }
   if(prev_trend == REGIME_MACRO_UNSET)
     {
      out_trend = raw;
      out_dwell = 1;
      return;
     }
   //--- same dwell-lock idea as CRegimeStateMachine::Step: a state is
   //--- protected from flipping again for its first min_dwell bars;
   //--- the deadband above already absorbs noise in the raw reading.
   if(raw == prev_trend || prev_dwell < m_min_dwell)
     {
      out_trend = prev_trend;
      out_dwell = prev_dwell + 1;
     }
   else
     {
      out_trend = raw;
      out_dwell = 1;
     }
  }
//+------------------------------------------------------------------+
bool CMacroTrendEngine::CalculateRaw(const int rates_total,const int first,
                                     const datetime &time[],
                                     double &raw_out[],int &boundary_out[])
  {
   if(rates_total <= 0 || first < 0 || first >= rates_total)
      return(false);

   int shift = iBarShift(m_symbol,m_tf,time[first],false);
   if(shift < 0)
      return(false);                       // series not built yet, retry next tick

   int warmup = m_ema_period + m_slope_bars;
   int available = Bars(m_symbol,m_tf);
   if(available <= warmup + 2)
      return(false);                       // not enough higher timeframe history yet

//--- The EMA is recursive, so its value depends on where the copied
//--- window starts. Without a burn-in, an incremental call (shift ~ 0,
//--- window ~ warmup bars) seeds from an SMA a few bars back while a
//--- full recalculation seeds thousands of bars back: the same closed
//--- HTF bar got different slopes. 20 x period extra bars makes the
//--- seed's residual weight (1-k)^(20*period) ~ 5e-18 for period 50,
//--- below double precision. Runs seeded at different points then agree
//--- to within a few ULPs (usually exactly, but rounding can keep a
//--- 1-ULP difference alive), so a classification can only differ if
//--- the slope sits within ~1e-16 of the deadband - negligible, not a
//--- formal guarantee. InpSelfCheck verifies it at runtime.
   int burn_in = 20 * m_ema_period;
   int need = shift + warmup + 3 + burn_in;
   if(need > available)
      need = available;

   if(CopyClose(m_symbol,m_tf,0,need,m_htf_close) != need)
      return(false);
   if(CopyTime(m_symbol,m_tf,0,need,m_htf_time) != need)
      return(false);

   if(ArraySize(m_htf_ema) != need && ArrayResize(m_htf_ema,need) != need)
      return(false);
   if(ArraySize(m_htf_raw) != need && ArrayResize(m_htf_raw,need) != need)
      return(false);

//--- EMA over the higher timeframe closes
   double k = 2.0 / (m_ema_period + 1.0);
   double running = 0.0;
   for(int j = 0; j < need; j++)
     {
      if(j < m_ema_period - 1)
        {
         m_htf_ema[j] = EMPTY_VALUE;
         running += m_htf_close[j];
         continue;
        }
      if(j == m_ema_period - 1)
        {
         running += m_htf_close[j];
         m_htf_ema[j] = running / m_ema_period;    // seed = simple average
         continue;
        }
      m_htf_ema[j] = m_htf_close[j] * k + m_htf_ema[j-1] * (1.0 - k);
     }

//--- pure per-HTF-bar classification; identical every time it is
//--- computed for the same closed bar, hence never repaints
   for(int j = 0; j < need; j++)
     {
      if(j < m_slope_bars)
         m_htf_raw[j] = REGIME_MACRO_UNSET;
      else
         m_htf_raw[j] = ClassifyOf(m_htf_ema[j],m_htf_ema[j - m_slope_bars]);
     }

//--- map the higher timeframe onto the chart, exactly like RegimeER,
//--- and flag every chart bar where the mapped closed HTF bar changed
   int j_cur = 0;
   int prev_closed = -1;
   for(int i = first; i < rates_total; i++)
     {
      if(time[i] < m_htf_time[0])
        {
         raw_out[i]      = (double)REGIME_MACRO_UNSET;
         boundary_out[i] = 1;
         prev_closed     = -1;
         continue;
        }
      while(j_cur + 1 < need && m_htf_time[j_cur+1] <= time[i])
         j_cur++;
      int closed = j_cur - 1;
      raw_out[i] = (closed >= 0) ? (double)m_htf_raw[closed] : (double)REGIME_MACRO_UNSET;

      if(i == first)
        {
         //--- the previous chart bar was outside this call's range (or
         //--- does not exist); find its closed HTF time independently
         //--- so the very first boundary flag is still correct.
         datetime this_time = (closed >= 0) ? m_htf_time[closed] : 0;
         datetime prev_time = (i > 0) ? ClosedHtfTimeAt(time[i-1]) : 0;
         boundary_out[i] = (this_time != prev_time) ? 1 : 0;
        }
      else
         boundary_out[i] = (closed != prev_closed) ? 1 : 0;

      prev_closed = closed;
     }
   return(true);
  }
