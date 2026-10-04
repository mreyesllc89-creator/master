//+------------------------------------------------------------------+
//|                                                    Dashboard.mqh  |
//|   TokioQuant - Panel de control en el grafico (Comment)           |
//|   Muestra regimen, scores, mercado, basket, equity y P/L.         |
//+------------------------------------------------------------------+
#ifndef TOKIO_DASHBOARD_MQH
#define TOKIO_DASHBOARD_MQH

#include "Utilities.mqh"

class CDashboard
{
private:
   SConfig m_cfg;

   string Bar(double v /*0..100*/)
   {
      int filled = (int)MathRound(Clamp(v, 0, 100) / 10.0);
      string s = "";
      for(int i = 0; i < 10; i++) s += (i < filled) ? "#" : ".";
      return s;
   }

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   void Render(const SMarket &m, const SScores &s, const SBasket &b, const SRuntime &rt,
               const string regimeName, double balance, double equity, double ddPct,
               double initialBankroll, double harvested, double dailyP, double weeklyP,
               int cycles, double step)
   {
      if(!m_cfg.showDash) return;

      double aboveInit = balance - initialBankroll;
      double pctGain   = (initialBankroll > 0) ? aboveInit / initialBankroll * 100.0 : 0.0;

      string d =
      "===== TOKIO QUANT  |  " + m_cfg.symbol + "  " + EnumToString(m_cfg.tf) + " =====\n" +
      TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES) + "\n" +
      "-------------------- REGIMEN --------------------\n" +
      "Regimen : " + regimeName + "   RecLvl: " + IntegerToString(rt.recoveryLevel) + "\n" +
      "-------------------- SCORES ---------------------\n" +
      "Trend  " + Bar(s.trend)      + " " + DoubleToString(s.trend,0)      + " (dir " + IntegerToString(s.trendDir) + ")\n" +
      "Mom    " + Bar(s.momentum)   + " " + DoubleToString(s.momentum,0)   + "\n" +
      "Vol    " + Bar(s.volatility) + " " + DoubleToString(s.volatility,0) + "\n" +
      "Liq    " + Bar(s.liquidity)  + " " + DoubleToString(s.liquidity,0)  + "\n" +
      "Risk   " + Bar(s.risk)       + " " + DoubleToString(s.risk,0)       + "\n" +
      "Recov  " + Bar(s.recovery)   + " " + DoubleToString(s.recovery,0)   + "\n" +
      "Qual   " + Bar(s.quality)    + " " + DoubleToString(s.quality,0)    + "\n" +
      "Conf   " + Bar(s.confidence) + " " + DoubleToString(s.confidence,0) + "\n" +
      "-------------------- MERCADO --------------------\n" +
      "ATR " + DoubleToString(m.atr,2) + " (x" + DoubleToString(m.atrRatio,2) + ")  " +
      "ADX " + DoubleToString(m.adx,1) + "  Spread " + DoubleToString(m.spread,2) + "\n" +
      "-------------------- BASKET ---------------------\n" +
      "Buys " + IntegerToString(b.buys) + "  Sells " + IntegerToString(b.sells) +
      "  Lots " + DoubleToString(b.lotsTotal,2) + "  Delta " + DoubleToString(b.delta,2) + "\n" +
      "Floating $" + DoubleToString(b.floating,2) + "   Step " + DoubleToString(step,2) + "\n" +
      "-------------------- CUENTA ---------------------\n" +
      "Balance $" + DoubleToString(balance,2) + "   Equity $" + DoubleToString(equity,2) + "\n" +
      "DD " + DoubleToString(ddPct,1) + "% / " + DoubleToString(m_cfg.equityStopPct,0) + "%\n" +
      "P/L dia $" + DoubleToString(dailyP,2) + "  semana $" + DoubleToString(weeklyP,2) +
      "  total $" + DoubleToString(harvested,2) + "\n" +
      "Sobre inicial $" + DoubleToString(aboveInit,2) + " (" + DoubleToString(pctGain,1) + "%)\n" +
      "Ciclos " + IntegerToString(cycles) + "\n" +
      "=================================================";

      Comment(d);
   }
};

#endif // TOKIO_DASHBOARD_MQH
