//+------------------------------------------------------------------+
//|                                           RegimeStateMachine.mqh |
//|        The core - hysteresis + dwell time + shock circuit breaker|
//+------------------------------------------------------------------+
//| Transition rules, in priority order:                             |
//|                                                                  |
//| 1. SHOCK   bar range > ShockMult * ATR  ->  force Range and reset |
//|            the dwell counter to 1. A shock overrides the dwell    |
//|            lock; it is a circuit breaker, not a suggestion.       |
//| 2. TARGET  already trending : ER < Exit  -> Range,                |
//|                               otherwise  -> trend, direction from |
//|                                             SuperTrend           |
//|            not trending    : ER > Enter  -> trend (SuperTrend),   |
//|                               ER < Exit  -> Range,                |
//|                               otherwise  -> Neutral              |
//| 3. DWELL   a target different from the current state is only      |
//|            accepted once the state has lasted MinDwell bars;      |
//|            otherwise the current state is held and dwell grows.   |
//|                                                                  |
//| Every input and every piece of state is read from, and written    |
//| to, an indicator buffer. Bar i reads bar i-1. No static or global |
//| variable participates, so recomputing from bar 0 yields exactly   |
//| the same series as an incremental update.                         |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

#include "RegimeTypes.mqh"
#include "RegimeER.mqh"

//+------------------------------------------------------------------+
//| Class CRegimeStateMachine                                        |
//+------------------------------------------------------------------+
class CRegimeStateMachine
  {
private:
   double            m_enter;        // ER level that opens a trend state
   double            m_exit;         // ER level that closes a trend state
   int               m_min_dwell;    // minimum bars in a state
   double            m_shock_mult;   // bar range / ATR that forces Range

public:
                     CRegimeStateMachine(void);
                    ~CRegimeStateMachine(void);

   bool              Init(const double enter_level,const double exit_level,
                          const int min_dwell,const double shock_mult);

   double            EnterLevel(void) const { return(m_enter);      }
   double            ExitLevel(void)  const { return(m_exit);       }
   int               MinDwell(void)   const { return(m_min_dwell);  }

   //--- Single transition. Pure: identical arguments always give an
   //--- identical result. This is the only place a state is decided.
   void              Step(const int prev_state,const int prev_dwell,
                          const double er,const double st_dir,
                          const double bar_range,const double atr,
                          int &out_state,int &out_dwell) const;

   //--- Runs Step() across [first .. last] inclusive, reading inputs
   //--- from the calculation buffers and writing state/dwell back.
   void              Calculate(const int first,const int last,
                               const double &high[],const double &low[],
                               const double &er[],const double &st_dir[],const double &atr[],
                               double &state[],double &dwell[]) const;
  };

//+------------------------------------------------------------------+
CRegimeStateMachine::CRegimeStateMachine(void) : m_enter(0.30),
                                                 m_exit(0.18),
                                                 m_min_dwell(4),
                                                 m_shock_mult(3.0)
  {
  }
//+------------------------------------------------------------------+
CRegimeStateMachine::~CRegimeStateMachine(void)
  {
  }
//+------------------------------------------------------------------+
bool CRegimeStateMachine::Init(const double enter_level,const double exit_level,
                               const int min_dwell,const double shock_mult)
  {
   if(enter_level <= exit_level || exit_level < 0.0 || enter_level > 1.0)
      return(false);
   if(min_dwell < 1 || shock_mult <= 0.0)
      return(false);
   m_enter      = enter_level;
   m_exit       = exit_level;
   m_min_dwell  = min_dwell;
   m_shock_mult = shock_mult;
   return(true);
  }
//+------------------------------------------------------------------+
void CRegimeStateMachine::Step(const int prev_state,const int prev_dwell,
                               const double er,const double st_dir,
                               const double bar_range,const double atr,
                               int &out_state,int &out_dwell) const
  {
//--- 1. shock: overrides everything, including the dwell lock
   if(atr > 0.0 && bar_range > m_shock_mult * atr)
     {
      out_state = REGIME_RANGE;
      out_dwell = 1;
      return;
     }

//--- 2. where would we like to be?
   int trend_state = (st_dir > 0.0) ? REGIME_TREND_UP : REGIME_TREND_DOWN;
   int target;
   bool in_trend = (prev_state == REGIME_TREND_UP || prev_state == REGIME_TREND_DOWN);

   if(in_trend)
     {
      //--- hysteresis: only ER below the exit level ends a trend
      target = (er < m_exit) ? REGIME_RANGE : trend_state;
     }
   else
     {
      if(er > m_enter)
         target = trend_state;
      else
         if(er < m_exit)
            target = REGIME_RANGE;
         else
            target = REGIME_NEUTRAL;
     }

//--- 3. dwell lock
   if(target == prev_state || prev_dwell < m_min_dwell)
     {
      out_state = prev_state;
      out_dwell = prev_dwell + 1;
     }
   else
     {
      out_state = target;
      out_dwell = 1;
     }
  }
//+------------------------------------------------------------------+
void CRegimeStateMachine::Calculate(const int first,const int last,
                                    const double &high[],const double &low[],
                                    const double &er[],const double &st_dir[],const double &atr[],
                                    double &state[],double &dwell[]) const
  {
   for(int i = first; i <= last; i++)
     {
      //--- warm-up: no higher timeframe reading or no ATR yet
      if(er[i] < 0.0 || atr[i] <= 0.0)
        {
         state[i] = (double)REGIME_UNSET;
         dwell[i] = 0.0;
         continue;
        }

      int prev_state = (i > 0) ? (int)state[i-1] : REGIME_UNSET;
      int prev_dwell = (i > 0) ? (int)dwell[i-1] : 0;

      //--- first bar the machine can run on: seed it as Range
      if(prev_state == REGIME_UNSET)
        {
         state[i] = (double)REGIME_RANGE;
         dwell[i] = 1.0;
         continue;
        }

      int new_state, new_dwell;
      Step(prev_state,prev_dwell,er[i],st_dir[i],high[i]-low[i],atr[i],new_state,new_dwell);
      state[i] = (double)new_state;
      dwell[i] = (double)new_dwell;
     }
  }
