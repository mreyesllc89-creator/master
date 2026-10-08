//+------------------------------------------------------------------+
//| FlashGoldV5_BTCUSD.mq5                                           |
//| MT5 Expert Advisor: FlashGold v5 strategy, BTCUSD calibration.   |
//| Same logic as flashgold_v5_strategy_btcusd.pine (see the core).  |
//| Calibration (MEXC:BTCUSDT 60m, 2026-09-06 to 2026-10-08, 0.02%   |
//| fee, stop-first fills): SL 30 pips ($30), 30% at TP 5R, runner   |
//| to breakeven + 600 pip trail: +63k on 10 BTC, PF 3.5.            |
//| 1 pip = $1 per BTC. Check your broker's spread: the default max  |
//| spread for a new entry is 15 pips (half the stop).               |
//| Put this file and FlashGoldV5_Core.mqh in MQL5/Experts/ and run  |
//| it on a BTCUSD H1 chart (H2 / H4 also tested positive).          |
//+------------------------------------------------------------------+
#property copyright "FlashGold v5 port"
#property version   "1.00"
#property description "FlashGold v5 EA - BTCUSD calibration (Pips exits, partial + runner, spread aware)"

#define FG_NAME              "FlashGold v5 EA (BTCUSD)"
#define FG_MAGIC             50501
#define FG_LOTS              0.10
#define FG_MODEL_SPREAD      0.25
#define FG_MAX_SPREAD_PIPS   15.0
#define FG_PIP_SIZE          1.0
#define FG_SL_PIPS           30.0
#define FG_TPR_PIPS          5.0
#define FG_RUN_PIPS          600.0
#define FG_TRAIL_ACT_PIPS    150.0
#define FG_TRAIL_PIPS        600.0
#define FG_SL_ATR            0.1
#define FG_TPR_ATR           2.0
#define FG_RUN_ATR           1.5
#define FG_SL_POINTS         3000.0
#define FG_TP_POINTS         15000.0
#define FG_RUN_POINTS        60000.0
#define FG_TRAIL_ACT_POINTS  15000.0
#define FG_TRAIL_POINTS      60000.0

#include "FlashGoldV5_Core.mqh"
