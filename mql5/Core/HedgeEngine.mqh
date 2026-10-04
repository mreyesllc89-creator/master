//+------------------------------------------------------------------+
//|                                                   HedgeEngine.mqh |
//|   TokioQuant - Hedge inteligente (NO hedge permanente)            |
//|   Solo en tendencia fuerte: abre a favor de la tendencia para     |
//|   financiar la recuperacion del lado contrario en perdida.        |
//|   Nunca abre hedge si el mercado esta lateral.                    |
//+------------------------------------------------------------------+
#ifndef TOKIO_HEDGEENGINE_MQH
#define TOKIO_HEDGEENGINE_MQH

#include "Utilities.mqh"
#include <Trade\Trade.mqh>

class CHedgeEngine
{
private:
   SConfig  m_cfg;
   datetime m_lastHedge;

public:
   CHedgeEngine(void) : m_lastHedge(0) {}

   void Init(const SConfig &cfg) { m_cfg = cfg; m_lastHedge = 0; }

   // Intenta abrir una cobertura a favor de la tendencia. Devuelve true si abrio.
   bool TryHedge(CTrade &tr, const SMarket &m, int trendDir, double trendConf,
                 const SBasket &b, const SRuntime &rt)
   {
      if(!m_cfg.useHedge || !rt.allowHedge)   return false;
      if(trendDir == 0)                       return false;
      if(trendConf < m_cfg.hedgeConf)         return false;

      // Espaciado temporal para no sobre-cubrir
      if((TimeCurrent() - m_lastHedge) < (m_cfg.minSecs * 3)) return false;

      // Solo cubrir si el lado CONTRARIO a la tendencia esta bajo el agua
      bool counterUnderwater = false;
      if(trendDir > 0 && b.sells > 0 && b.recDistSell > 0) counterUnderwater = true;
      if(trendDir < 0 && b.buys  > 0 && b.recDistBuy  > 0) counterUnderwater = true;
      if(!counterUnderwater) return false;

      // Respeto del tope de exposicion
      double lot = NormalizeVolume(m_cfg.symbol, m_cfg.hedgeLot * rt.lotMult, m_cfg.maxLotOrder);
      if(lot <= 0) return false;
      if(b.lotsTotal + lot > rt.exposureCap) return false;

      bool ok;
      if(trendDir > 0) ok = tr.Buy(lot, m_cfg.symbol, m.ask, 0, 0, "TQ-Hedge");
      else             ok = tr.Sell(lot, m_cfg.symbol, m.bid, 0, 0, "TQ-Hedge");

      if(ok) m_lastHedge = TimeCurrent();
      return ok;
   }
};

#endif // TOKIO_HEDGEENGINE_MQH
