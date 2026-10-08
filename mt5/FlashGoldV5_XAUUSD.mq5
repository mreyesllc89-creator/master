//+------------------------------------------------------------------+
//| FlashGoldV5_XAUUSD.mq5                                           |
//| MT5 Expert Advisor: FlashGold v5 strategy, XAUUSD calibration.   |
//| Same logic as flashgold_v5_strategy_xauusd.pine (see the core).  |
//| Calibration (OANDA:XAUUSD 60m, 2026-09-21 to 2026-10-08,         |
//| $0.13/oz/side, stop-first fills): SL 15 pips ($1.50), 30% at TP  |
//| 3R, runner to breakeven + 160 pip trail: +1,220 on 10 oz, PF 5.6.|
//| 1 pip = $0.10 per oz (0.10 lot = 10 oz). A 15 pip stop is tight: |
//| new entries are skipped when the spread is above 5 pips ($0.50). |
//| Put this file and FlashGoldV5_Core.mqh in MQL5/Experts/ and run  |
//| it on an XAUUSD H1 chart (M15 also tested positive).             |
//+------------------------------------------------------------------+
#property copyright "FlashGold v5 port"
#property version   "1.00"
#property description "FlashGold v5 EA - XAUUSD calibration (Pips exits, partial + runner, spread aware)"

#define FG_NAME              "FlashGold v5 EA (XAUUSD)"
#define FG_MAGIC             50502
#define FG_LOTS              0.10
#define FG_MODEL_SPREAD      0.25
#define FG_MAX_SPREAD_PIPS   5.0
#define FG_PIP_SIZE          0.1
#define FG_SL_PIPS           15.0
#define FG_TPR_PIPS          3.0
#define FG_RUN_PIPS          160.0
#define FG_TRAIL_ACT_PIPS    45.0
#define FG_TRAIL_PIPS        160.0
#define FG_SL_ATR            0.1
#define FG_TPR_ATR           1.5
#define FG_RUN_ATR           1.5
#define FG_SL_POINTS         150.0
#define FG_TP_POINTS         450.0
#define FG_RUN_POINTS        1600.0
#define FG_TRAIL_ACT_POINTS  450.0
#define FG_TRAIL_POINTS      1600.0

#include "FlashGoldV5_Core.mqh"
