//+------------------------------------------------------------------+
//|                                                  RegimeTypes.mqh |
//|                    RegimeTrend - shared types and small helpers  |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

//--- Regime state codes. These values are the public contract exposed
//--- through indicator buffer 3 and consumed by EAs via iCustom().
#define REGIME_RANGE        0   // choppy / low efficiency
#define REGIME_TREND_UP     1   // efficient move, SuperTrend bullish
#define REGIME_TREND_DOWN  -1   // efficient move, SuperTrend bearish
#define REGIME_NEUTRAL      2   // between exit and enter thresholds
#define REGIME_UNSET     -999   // not yet computed (warm-up bars)

//--- Macro trend levels, written to buffer 7. This is a SEPARATE axis
//--- from the state machine's REGIME/DIRECTION split: it is computed
//--- from a slow HTF EMA slope, has its own (small, bounded) smoothing,
//--- and is NOT reset when the state machine forces REGIME_RANGE. The
//--- whole point is that it keeps reporting the structural trend while
//--- the regime layer is calling the market choppy underneath it.
#define REGIME_MACRO_UNSET  (-2)  // warm-up, HTF EMA/slope not ready
#define REGIME_MACRO_DOWN   (-1)  // HTF EMA sloping down
#define REGIME_MACRO_FLAT     0   // slope inside the deadband
#define REGIME_MACRO_UP        1  // HTF EMA sloping up

//--- EA-facing split of the state, written to buffers 5 and 6.
//--- Buffer 5 answers "how directional is the market?" and buffer 6
//--- answers "which way?", so neither question needs the sign of the
//--- other. An EA filter reads:
//---    regime >= REGIME_LEVEL_TRENDING && direction > 0
#define REGIME_LEVEL_UNSET    (-1)  // warm-up, no reading yet
#define REGIME_LEVEL_CHOPPY     0
#define REGIME_LEVEL_NEUTRAL    1
#define REGIME_LEVEL_TRENDING   2

//--- Colour indices written to buffer 1 (DRAW_COLOR_LINE palette).
#define REGIME_CLRIDX_RANGE    0
#define REGIME_CLRIDX_UP       1
#define REGIME_CLRIDX_DOWN     2
#define REGIME_CLRIDX_NEUTRAL  3

//+------------------------------------------------------------------+
//| Map a state code to the plot colour index.                       |
//+------------------------------------------------------------------+
int RegimeColorIndex(const int state)
  {
   switch(state)
     {
      case REGIME_TREND_UP:   return(REGIME_CLRIDX_UP);
      case REGIME_TREND_DOWN: return(REGIME_CLRIDX_DOWN);
      case REGIME_NEUTRAL:    return(REGIME_CLRIDX_NEUTRAL);
      default:                return(REGIME_CLRIDX_RANGE);
     }
  }

//+------------------------------------------------------------------+
//| Regime level for buffer 5: how directional the market is, with   |
//| the direction factored out.                                      |
//+------------------------------------------------------------------+
int RegimeLevel(const int state)
  {
   switch(state)
     {
      case REGIME_TREND_UP:
      case REGIME_TREND_DOWN: return(REGIME_LEVEL_TRENDING);
      case REGIME_NEUTRAL:    return(REGIME_LEVEL_NEUTRAL);
      case REGIME_RANGE:      return(REGIME_LEVEL_CHOPPY);
      default:                return(REGIME_LEVEL_UNSET);
     }
  }

//+------------------------------------------------------------------+
//| Direction for buffer 6: +1 up, -1 down, 0 when not trending.    |
//| This is the direction the STATE MACHINE has committed to, which  |
//| is not the same as the raw SuperTrend direction in buffer 10:     |
//| the dwell lock can hold a state while SuperTrend has flipped.    |
//+------------------------------------------------------------------+
int RegimeDirection(const int state)
  {
   switch(state)
     {
      case REGIME_TREND_UP:   return(1);
      case REGIME_TREND_DOWN: return(-1);
      default:                return(0);
     }
  }

//+------------------------------------------------------------------+
//| Human readable macro trend name (logs / self-check messages).    |
//+------------------------------------------------------------------+
string RegimeMacroTrendName(const int macro_trend)
  {
   switch(macro_trend)
     {
      case REGIME_MACRO_UP:   return("Up");
      case REGIME_MACRO_DOWN: return("Down");
      case REGIME_MACRO_FLAT: return("Flat");
      default:                return("Warm-up");
     }
  }

//+------------------------------------------------------------------+
//| Human readable state name (used by the gauge and the logs).      |
//+------------------------------------------------------------------+
string RegimeStateName(const int state)
  {
   switch(state)
     {
      case REGIME_TREND_UP:   return("TRENDING");
      case REGIME_TREND_DOWN: return("TRENDING");
      case REGIME_NEUTRAL:    return("NEUTRAL");
      case REGIME_RANGE:      return("CHOPPY");
      default:                return("WARM-UP");
     }
  }

//+------------------------------------------------------------------+
//| Short tag without direction arrow (CSV / logging).               |
//+------------------------------------------------------------------+
string RegimeStateTag(const int state)
  {
   switch(state)
     {
      case REGIME_TREND_UP:   return("TrendUp");
      case REGIME_TREND_DOWN: return("TrendDown");
      case REGIME_NEUTRAL:    return("Neutral");
      case REGIME_RANGE:      return("Range");
      default:                return("Unset");
     }
  }
