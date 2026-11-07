//+------------------------------------------------------------------+
//|                 XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5     |
//|                                                                  |
//|  Same EA as XAUUSD_M1_LiquidityZeroCross_Bearish.mq5, built with |
//|  the FlashGold Direction Filter v1.2 as a direction filter:      |
//|  a short is only opened while the filter's "sell allowed"        |
//|  buffer is 1 (price below the FlashGold level, outside the ATR   |
//|  no-trade band, permission window open).                         |
//|                                                                  |
//|  Install (keep the MQL5 folder layout):                          |
//|    MQL5/Experts/XAUUSD_M1_LiquidityZeroCross_Bearish.mq5         |
//|    MQL5/Experts/XAUUSD_M1_LiquidityZeroCross_Bearish_FGF.mq5     |
//|    MQL5/Indicators/FlashGold_Direction_Filter_v1_2.ex5 (+ .mq5)  |
//|    MQL5/Include/FlashGold/*.mqh                                  |
//|  Compile this file. All strategy logic lives in the base file,   |
//|  so both versions always share the same rules and fixes.         |
//+------------------------------------------------------------------+
#define XLZC_WITH_FGF
#include "XAUUSD_M1_LiquidityZeroCross_Bearish.mq5"
//+------------------------------------------------------------------+
