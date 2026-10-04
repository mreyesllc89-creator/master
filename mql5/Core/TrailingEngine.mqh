//+------------------------------------------------------------------+
//|                                                TrailingEngine.mqh |
//|   TokioQuant - Trailing dinamico del profit del basket            |
//|   Mas volatilidad -> retroceso permitido mayor (no cortar antes). |
//|   Menos volatilidad -> retroceso mas corto (asegurar ganancia).   |
//+------------------------------------------------------------------+
#ifndef TOKIO_TRAILINGENGINE_MQH
#define TOKIO_TRAILINGENGINE_MQH

#include "Utilities.mqh"

class CTrailingEngine
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Actualiza el pico y decide si hay que cosechar por trailing.
   // 'peak' se mantiene por referencia entre ticks (lo posee el Engine).
   bool Check(double profit, double &peak, const SMarket &m, const SRuntime &rt)
   {
      double activate = m_cfg.trailActUSD;
      if(profit < activate) return false;

      if(profit > peak) peak = profit;

      // Retroceso dinamico: escala con volatilidad y con el nivel de recovery.
      double volFactor = Clamp(m.atrRatio, 0.7, 2.0);
      double step = m_cfg.trailStepUSD * volFactor * rt.trailMult;
      step = MathMax(step, 0.01);

      return (peak - profit >= step);
   }
};

#endif // TOKIO_TRAILINGENGINE_MQH
