// Profit-factor optimization score for XPW_ShapeMap_v092_FGF_EA.mq5.
//
// HOW TO APPLY (2 edits in MQL5/Experts/XPW_ShapeMap_v092_FGF_EA.mq5):
//   1. Add after the EnableTrading input line:
//        #include <XPW/OnTester_ProfitFactor.mqh>
//      (copy this file to MQL5/Include/XPW/ first)
//   2. Replace the existing two-line OnTester() at the bottom of the EA with:
//        double OnTester() { return XpwPfTesterScore(g_v92_runtime.ExportTesterLedger()); }
//   Then in the Strategy Tester choose Optimization criterion = "Custom max".
//
// Score = min(PF, PfCap) x trade-count weight x drawdown damping.
//  - Passes with fewer than PfMinTrades trades or non-positive net profit score 0,
//    so the optimizer cannot "win" with 3 lucky trades (PF = infinity).
//  - Weight ramps 0..1 until 3 x PfMinTrades trades, then is flat.
//  - PF is capped so one outlier trade cannot dominate.
//  - Relative equity drawdown damps the score: 100/(100+DD%).
#ifndef XPW_ONTESTER_PROFIT_FACTOR_MQH
#define XPW_ONTESTER_PROFIT_FACTOR_MQH

input group "Optimization score (PF)"
input int    PfMinTrades = 60;    // Minimum trades for a non-zero score
input double PfCap       = 8.0;   // Profit-factor cap

double XpwPfTesterScore(const bool ledgerExported)
  {
   if(!ledgerExported) return -DBL_MAX;
   const double trades = TesterStatistics(STAT_TRADES);
   const double profit = TesterStatistics(STAT_PROFIT);
   if(trades < PfMinTrades || profit <= 0.0) return 0.0;
   const double gross = TesterStatistics(STAT_GROSS_PROFIT);
   const double loss  = MathAbs(TesterStatistics(STAT_GROSS_LOSS));
   const double pf    = loss > 0.0 ? gross / loss : PfCap;
   const double pfC   = MathMin(pf, PfCap);
   const double w     = MathMin(1.0, trades / (3.0 * PfMinTrades));
   const double dd    = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   return pfC * w * (100.0 / (100.0 + dd));
  }
#endif
