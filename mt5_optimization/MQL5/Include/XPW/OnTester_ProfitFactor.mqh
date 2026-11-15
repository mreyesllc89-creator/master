// Profit-factor optimization score for XPW_ShapeMap_v092_FGF_EA.mq5.
// Included by the patched EA after its EnableTrading input; OnTester() returns
// XpwPfTesterScore(). In the Strategy Tester choose Optimization criterion = "Custom max".
//
// Score = min(PF, PfCap) x trade-count weight x drawdown damping.
//  - Passes with fewer than PfMinTrades trades or non-positive net profit score 0,
//    so the optimizer cannot "win" with 3 lucky trades (PF = infinity).
//  - Weight ramps 0..1 until 3 x PfMinTrades trades, then is flat.
//  - PF is capped so one outlier trade cannot dominate.
//  - Relative equity drawdown damps the score: 100/(100+DD%).
#ifndef XPW_ONTESTER_PROFIT_FACTOR_MQH
#define XPW_ONTESTER_PROFIT_FACTOR_MQH
#ifndef XPW_V92_INPUT
#define XPW_V92_INPUT input
#endif

input group "Optimization score (PF)"
XPW_V92_INPUT int    PfMinTrades = 60;    // Minimum trades for a non-zero score
XPW_V92_INPUT double PfCap       = 8.0;   // Profit-factor cap

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
