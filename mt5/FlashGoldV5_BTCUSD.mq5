//+------------------------------------------------------------------+
//| FlashGoldV5_BTCUSD.mq5                                           |
//| MT5 Expert Advisor: FlashGold v5 strategy, BTCUSD calibration.   |
//| Same logic as flashgold_v5_strategy_btcusd.pine (see the core).  |
//| Defaults = presets/FlashGoldV5_BTCUSD_H4.set: run on BTCUSD H4.  |
//| Spread-aware simulation (spread $12, slippage $3): H4 was the    |
//| only BTC timeframe profitable under both the TradingView 4-tick  |
//| fill model and a pessimistic one. SL 400 pips (~0.5 ATR), 30% at |
//| TP 3R, runner to breakeven + 1200 pip trail, min aligned 0.      |
//| Tight stops (20-40 pips) only win under the 4-tick model: on a   |
//| real intrabar path they lose (checked on gold 15m data).         |
//| 1 pip = $1 per BTC. Max spread for a new entry: 40 pips.         |
//| Put this file and FlashGoldV5_Core.mqh in MQL5/Experts/.         |
//+------------------------------------------------------------------+
#property copyright "FlashGold v5 port"
#property version   "1.00"
#property description "FlashGold v5 EA - BTCUSD calibration (Pips exits, partial + runner, spread aware)"

#define FG_NAME              "FlashGold v5 EA (BTCUSD)"
#define FG_MAGIC             50501
#define FG_LOTS              0.10
#define FG_MODEL_SPREAD      0.25
#define FG_MAX_SPREAD_PIPS   40.0
#define FG_MIN_ALIGNED       0
#define FG_PIP_SIZE          1.0
#define FG_SL_PIPS           400.0
#define FG_TPR_PIPS          3.0
#define FG_RUN_PIPS          1200.0
#define FG_TRAIL_ACT_PIPS    1200.0
#define FG_TRAIL_PIPS        1200.0
#define FG_SL_ATR            0.5
#define FG_TPR_ATR           3.0
#define FG_RUN_ATR           1.5
#define FG_SL_POINTS         40000.0
#define FG_TP_POINTS         120000.0
#define FG_RUN_POINTS        120000.0
#define FG_TRAIL_ACT_POINTS  120000.0
#define FG_TRAIL_POINTS      120000.0

#include "FlashGoldV5_Core.mqh"
