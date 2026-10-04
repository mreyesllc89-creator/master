//+------------------------------------------------------------------+
//|                                                   RiskManager.mqh |
//|   TokioQuant - Cerebro de riesgo institucional                    |
//|   No solo un equity-stop: compone Risk / Exposure / Margin /      |
//|   Floating / Volatility / Correlation en un unico Risk Score.     |
//|   Cuando el riesgo sube, reduce lotes, frecuencia y bloquea.      |
//+------------------------------------------------------------------+
#ifndef TOKIO_RISKMANAGER_MQH
#define TOKIO_RISKMANAGER_MQH

#include "Utilities.mqh"

class CRiskManager
{
private:
   SConfig m_cfg;

public:
   // Sub-scores expuestos para el dashboard/telemetria
   double exposureScore, marginScore, floatingScore, volScore, corrScore, ddScore;

   CRiskManager(void) : exposureScore(0), marginScore(0), floatingScore(0),
                        volScore(0), corrScore(0), ddScore(0) {}

   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Calcula el Risk Score global [0..100] y lo guarda en s.risk.
   void Compute(SScores &s, const SMarket &m, const SBasket &b,
                double ddPct, double balance)
   {
      // Exposicion: lotes totales vs tope
      exposureScore = MapRange(b.lotsTotal, 0.0, MathMax(m_cfg.maxTotalLots, 0.01), 0.0, 100.0);

      // Margen: cuanto mas bajo el nivel de margen, mas peligro
      double marginUsed  = AccountInfoDouble(ACCOUNT_MARGIN);
      double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
      if(marginUsed > 0 && marginLevel > 0)
         marginScore = MapRange(marginLevel, m_cfg.marginMinLevel, 1000.0, 100.0, 0.0);
      else
         marginScore = 0.0;

      // Flotante negativo respecto al balance
      double floatPct = (balance > 0) ? (-b.floating / balance * 100.0) : 0.0;
      floatingScore   = MapRange(floatPct, 0.0, m_cfg.equityStopPct, 0.0, 100.0);

      // Volatilidad
      volScore = Clamp(MapRange(m.atrRatio, 1.0, 2.5, 0.0, 100.0), 0.0, 100.0);

      // Correlacion/desbalance: exposicion neta (delta) concentrada
      corrScore = MapRange(MathAbs(b.delta), 0.0, MathMax(m_cfg.maxTotalLots, 0.01), 0.0, 100.0);

      // Drawdown
      ddScore = MapRange(ddPct, 0.0, m_cfg.equityStopPct, 0.0, 100.0);

      // Score global: media ponderada mezclada con el peor sub-score
      double avg = 0.28*floatingScore + 0.20*ddScore + 0.18*exposureScore +
                   0.16*marginScore   + 0.10*volScore + 0.08*corrScore;
      double worst = MathMax(floatingScore, MathMax(ddScore, MathMax(marginScore, exposureScore)));
      s.risk = Clamp(0.6*avg + 0.4*worst, 0.0, 100.0);
   }

   // Escala de lotaje [0.25..1.0]: reduce tamano cuando el riesgo sube.
   double LotScale(double riskScore)
   {
      if(riskScore < 40.0) return 1.0;
      return Clamp(MapRange(riskScore, 40.0, 90.0, 1.0, 0.25), 0.25, 1.0);
   }

   // Kill switch por drawdown.
   bool KillSwitch(double ddPct) { return m_cfg.equityStopPct > 0 && ddPct >= m_cfg.equityStopPct; }

   // Permiso para abrir nuevas operaciones (compuerta dura).
   bool AllowNew(double riskScore, ENUM_REGIME regime, const SMarket &m)
   {
      if(regime == REGIME_PANIC || regime == REGIME_NEWS) return false;
      if(riskScore >= 88.0)                                return false;
      if(m.spread > m_cfg.maxSpreadUSD)                    return false;

      double marginUsed  = AccountInfoDouble(ACCOUNT_MARGIN);
      double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
      if(m_cfg.marginMinLevel > 0 && marginUsed > 0 && marginLevel > 0 && marginLevel < m_cfg.marginMinLevel)
         return false;

      return true;
   }
};

#endif // TOKIO_RISKMANAGER_MQH
