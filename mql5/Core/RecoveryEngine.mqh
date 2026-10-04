//+------------------------------------------------------------------+
//|                                                RecoveryEngine.mqh |
//|   TokioQuant - Recuperacion escalonada por drawdown               |
//|   Cada nivel endurece el sistema: ensancha grid, baja lotes,      |
//|   acorta TP, activa hedge y recorta niveles/exposicion.           |
//+------------------------------------------------------------------+
#ifndef TOKIO_RECOVERYENGINE_MQH
#define TOKIO_RECOVERYENGINE_MQH

#include "Utilities.mqh"

class CRecoveryEngine
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Determina el nivel [0..6] y ajusta el runtime en consecuencia.
   int Apply(SRuntime &rt, double ddPct)
   {
      // Valores por defecto (nivel 0, operacion normal)
      rt.stepMult    = 1.0;
      rt.lotMult     = 1.0;
      rt.tpMult      = 1.0;
      rt.trailMult   = 1.0;
      rt.maxLevels   = m_cfg.maxLevels;
      rt.exposureCap = m_cfg.maxTotalLots;
      rt.allowMart   = true;
      rt.allowHedge  = false;

      int level = 0;
      // V3: un umbral <= 0 significa APAGADO (antes 0 activaba el nivel 6 siempre)
#define TQ_ON(x) ((x) > 0.0 && ddPct >= (x))
      if(TQ_ON(m_cfg.dd6))      level = 6;
      else if(TQ_ON(m_cfg.dd5)) level = 5;
      else if(TQ_ON(m_cfg.dd4)) level = 4;
      else if(TQ_ON(m_cfg.dd3)) level = 3;
      else if(TQ_ON(m_cfg.dd2)) level = 2;
      else if(TQ_ON(m_cfg.dd1)) level = 1;

      switch(level)
      {
         case 1:
            rt.stepMult=1.15; rt.lotMult=0.90; rt.tpMult=0.90; rt.trailMult=0.90;
            break;
         case 2:
            rt.stepMult=1.30; rt.lotMult=0.80; rt.tpMult=0.80; rt.trailMult=0.85;
            rt.allowHedge=true;
            break;
         case 3:
            rt.stepMult=1.50; rt.lotMult=0.65; rt.tpMult=0.70; rt.trailMult=0.75;
            rt.allowHedge=true;
            rt.exposureCap=m_cfg.maxTotalLots*0.85;
            break;
         case 4:
            rt.stepMult=1.70; rt.lotMult=0.50; rt.tpMult=0.60; rt.trailMult=0.65;
            rt.allowHedge=true;
            rt.maxLevels=MathMax(2, m_cfg.maxLevels-2);
            rt.exposureCap=m_cfg.maxTotalLots*0.70;
            break;
         case 5:
            rt.stepMult=2.00; rt.lotMult=0.35; rt.tpMult=0.50; rt.trailMult=0.55;
            rt.allowHedge=true;
            rt.maxLevels=MathMax(2, m_cfg.maxLevels-3);
            rt.exposureCap=m_cfg.maxTotalLots*0.55;
            break;
         case 6:
            // Modo panico: dejar de promediar, solo administrar salida
            rt.stepMult=2.50; rt.lotMult=0.25; rt.tpMult=0.40; rt.trailMult=0.45;
            rt.allowHedge=true;  rt.allowMart=false;
            rt.maxLevels=MathMax(1, m_cfg.maxLevels-4);
            rt.exposureCap=m_cfg.maxTotalLots*0.40;
            break;
         default: /* nivel 0: sin cambios */ break;
      }

      rt.recoveryLevel = level;
      return level;
   }
};

#endif // TOKIO_RECOVERYENGINE_MQH
