//+------------------------------------------------------------------+
//|                                                    GridEngine.mqh |
//|   TokioQuant - Grid adaptativo + martingala dinamica              |
//|   El paso se ensancha con volatilidad, ADX, momentum y DD.        |
//|   El multiplicador baja (o se apaga) cuando el riesgo sube.       |
//+------------------------------------------------------------------+
#ifndef TOKIO_GRIDENGINE_MQH
#define TOKIO_GRIDENGINE_MQH

#include "Utilities.mqh"

class CGridEngine
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Paso del grid en unidades de PRECIO. extraMult viene de recovery/riesgo.
   double Step(const SMarket &m, double extraMult)
   {
      double base = m_cfg.useATRStep ? (m.atr * m_cfg.atrMult) : m_cfg.fixedStep;
      if(base <= 0) base = m_cfg.fixedStep;

      // Factor volatilidad: mas volatil -> niveles mas separados
      double fVol = Clamp(m.atrRatio, 0.7, 2.5);
      // Factor tendencia: ADX alto -> ensanchar (no sobre-promediar en tendencia)
      double fAdx = MapRange(m.adx, 15.0, 40.0, 1.0, 1.6);
      // Factor momentum: momentum fuerte -> ensanchar
      double fMom = MapRange(MathAbs(m.momentum), 0.0, 2.0, 1.0, 1.4);

      double step = base * fVol * fAdx * fMom * MathMax(extraMult, 0.1);
      return MathMax(step, m_cfg.minStep);
   }

   // Multiplicador de martingala segun el regimen de volatilidad (ATR).
   double Multiplier(const SMarket &m)
   {
      if(m.atrRatio < 0.8)      return m_cfg.martLow;   // vol baja -> mas agresivo ok
      else if(m.atrRatio < 1.2) return m_cfg.martMed;
      else if(m.atrRatio < 1.8) return m_cfg.martHigh;
      else                      return m_cfg.martXHigh; // vol extrema -> 1.0 apaga
   }
};

#endif // TOKIO_GRIDENGINE_MQH
