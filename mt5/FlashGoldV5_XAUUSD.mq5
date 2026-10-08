//+------------------------------------------------------------------+
//| FlashGoldV5_XAUUSD.mq5                                           |
//| MT5 Expert Advisor: FlashGold v5 strategy, XAUUSD calibration.   |
//| Same logic as flashgold_v5_strategy_xauusd.pine (see the core).  |
//| Defaults = presets/FlashGoldV5_XAUUSD_H1.set: run on XAUUSD H1.  |
//| Spread-aware simulation (spread $0.25, commission $0.035/oz,     |
//| slippage $0.03): SL 80 pips ($8, ~0.5 ATR), 30% at TP 5R, runner |
//| to breakeven + 315 pip trail, min aligned 3. Same result under   |
//| the 4-tick and the pessimistic fill model, and confirmed on the  |
//| real 15m path (Oct 5-8). Tight 10-20 pip stops lost on the real  |
//| path. 1 pip = $0.10 per oz (0.10 lot = 10 oz). M30: see presets. |
//| Put this file and FlashGoldV5_Core.mqh in MQL5/Experts/.         |
//+------------------------------------------------------------------+
#property copyright "FlashGold v5 port"
#property version   "1.00"
#property description "FlashGold v5 EA - XAUUSD calibration (Pips exits, partial + runner, spread aware)"

#define FG_NAME              "FlashGold v5 EA (XAUUSD)"
#define FG_MAGIC             50502
#define FG_LOTS              0.10
#define FG_MODEL_SPREAD      0.25
#define FG_MAX_SPREAD_PIPS   8.0
#define FG_MIN_ALIGNED       3
#define FG_PIP_SIZE          0.1
#define FG_SL_PIPS           80.0
#define FG_TPR_PIPS          5.0
#define FG_RUN_PIPS          315.0
#define FG_TRAIL_ACT_PIPS    400.0
#define FG_TRAIL_PIPS        315.0
#define FG_SL_ATR            0.5
#define FG_TPR_ATR           5.0
#define FG_RUN_ATR           2.0
#define FG_SL_POINTS         800.0
#define FG_TP_POINTS         4000.0
#define FG_RUN_POINTS        3150.0
#define FG_TRAIL_ACT_POINTS  4000.0
#define FG_TRAIL_POINTS      3150.0

#include "FlashGoldV5_Core.mqh"
