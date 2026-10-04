//+------------------------------------------------------------------+
//|                                                     TPManager.mqh |
//|   TokioQuant - Take Profit dinamico del basket                    |
//|   Depende de ATR, DD, exposicion, momentum y tiempo en mercado.   |
//|   En recuperacion el objetivo se acorta para escapar antes.       |
//+------------------------------------------------------------------+
#ifndef TOKIO_TPMANAGER_MQH
#define TOKIO_TPMANAGER_MQH

#include "Utilities.mqh"

class CTPManager
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Objetivo del basket en moneda de la cuenta.
   double BasketTP(const SMarket &m, const SBasket &b, const SRuntime &rt, double timeMin)
   {
      // Base escalada por numero de posiciones (basket mas grande, algo mas de meta)
      double lotsFactor = 1.0 + 0.10 * MathMax(b.total - 1, 0);
      // Componente de volatilidad (mercado mas rapido -> objetivo mayor)
      double atrComp = MathMax(m_cfg.tpAtrMult * m.atrRatio, 0.5);
      // Decaimiento por tiempo: cuanto mas dura el basket, menor la meta (escapar)
      double timeDecay = MapRange(timeMin, 0.0, 120.0, 1.0, 0.65);

      double tp = m_cfg.baseTP * lotsFactor * atrComp * rt.tpMult * timeDecay;
      tp = MathMax(tp, m_cfg.tpMinUSD);
      // V3: una cesta profunda no persigue MAS beneficio (antes el TP crecia
      // 10% por nivel): sale en cuanto vuelve a breakeven + deepTP.
      if(m_cfg.deepLevels > 0 && b.total >= m_cfg.deepLevels)
         tp = MathMin(tp, m_cfg.deepTP);
      return tp;
   }
};

#endif // TOKIO_TPMANAGER_MQH
