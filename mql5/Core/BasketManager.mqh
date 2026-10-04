//+------------------------------------------------------------------+
//|                                                 BasketManager.mqh |
//|   TokioQuant - Radiografia del basket abierto                     |
//|   Precio medio ponderado, exposicion, delta, breakeven, distancia |
//|   de recuperacion y localizacion de la peor posicion.             |
//+------------------------------------------------------------------+
#ifndef TOKIO_BASKETMANAGER_MQH
#define TOKIO_BASKETMANAGER_MQH

#include "Utilities.mqh"

class CBasketManager
{
private:
   string m_sym;
   ulong  m_magic;

   // Cache de la comision de las posiciones abiertas. POSITION_COMMISSION esta
   // OBSOLETO en MQL5 (devuelve 0): la comision vive en los DEALS. Sin ella el
   // flotante miente a favor del bot y el TP cerraria antes de cubrir costes.
   // Se recalcula solo cuando cambia el numero de posiciones, no en cada tick.
   int    m_lastCount;
   double m_commCache;

   // Suma la comision real de los deals que abrieron las posiciones vivas.
   double OpenCommission(void)
   {
      double total = 0.0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong tkt = PositionGetTicket(i);
         if(tkt == 0 || !PositionSelectByTicket(tkt)) continue;
         if(!Mine()) continue;
         ulong pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
         if(!HistorySelectByPosition(pid)) continue;
         for(int k = HistoryDealsTotal() - 1; k >= 0; k--)
         {
            ulong d = HistoryDealGetTicket(k);
            if(d == 0) continue;
            total += HistoryDealGetDouble(d, DEAL_COMMISSION);
         }
      }
      return total;   // normalmente negativo (es un coste)
   }

   bool Mine(void)
   {
      return (PositionGetString(POSITION_SYMBOL) == m_sym &&
              (ulong)PositionGetInteger(POSITION_MAGIC) == m_magic);
   }

public:
   CBasketManager(void) : m_lastCount(-1), m_commCache(0.0) {}

   void Init(const SConfig &cfg) { m_sym = cfg.symbol; m_magic = cfg.magic; }

   // Recalcula todas las metricas del basket a partir de las posiciones.
   void Update(SBasket &b, const SMarket &m)
   {
      b.buys = 0; b.sells = 0; b.total = 0;
      b.lotsBuy = 0; b.lotsSell = 0; b.lotsTotal = 0;
      b.floating = 0; b.delta = 0;
      b.avgBuy = 0; b.avgSell = 0;
      b.worstProfit = 0; b.worstTicket = 0; b.oldestTime = 0;

      double pvBuy = 0, pvSell = 0;   // sum(precio*lote) por lado
      double worst = DBL_MAX;
      bool   first = true;

      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong tkt = PositionGetTicket(i);
         if(tkt == 0) continue;
         if(!PositionSelectByTicket(tkt)) continue;
         if(!Mine()) continue;

         double lot   = PositionGetDouble(POSITION_VOLUME);
         double open  = PositionGetDouble(POSITION_PRICE_OPEN);
         double prof  = PositionGetDouble(POSITION_PROFIT) +
                        PositionGetDouble(POSITION_SWAP);
         long   type  = PositionGetInteger(POSITION_TYPE);

         b.floating += prof;
         b.total++;
         datetime pt = (datetime)PositionGetInteger(POSITION_TIME);
         if(b.oldestTime == 0 || pt < b.oldestTime) b.oldestTime = pt;

         if(type == POSITION_TYPE_BUY)
         {
            b.buys++; b.lotsBuy += lot; pvBuy += open * lot;
         }
         else
         {
            b.sells++; b.lotsSell += lot; pvSell += open * lot;
         }

         if(first || prof < worst) { worst = prof; b.worstTicket = tkt; first = false; }
      }

      // Comision de las posiciones vivas (recalculada solo si cambio el numero
      // de posiciones). Asi el flotante, el MAE y el TP trabajan con el coste
      // real y no con una cifra inflada.
      if(b.total != m_lastCount)
      {
         m_commCache = OpenCommission();
         m_lastCount = b.total;
      }
      b.floating += m_commCache;

      b.lotsTotal = b.lotsBuy + b.lotsSell;
      b.delta     = b.lotsBuy - b.lotsSell;
      b.avgBuy    = (b.lotsBuy  > 0) ? pvBuy  / b.lotsBuy  : 0.0;
      b.avgSell   = (b.lotsSell > 0) ? pvSell / b.lotsSell : 0.0;
      b.worstProfit = (b.total > 0) ? worst : 0.0;

      // Breakeven aproximado (ignora comision) = precio medio ponderado.
      b.breakevenBuy  = b.avgBuy;
      b.breakevenSell = b.avgSell;

      // Distancia de recuperacion en precio (positiva = bajo el agua).
      b.recDistBuy  = (b.buys  > 0) ? (b.avgBuy  - m.bid) : 0.0;
      b.recDistSell = (b.sells > 0) ? (m.ask - b.avgSell) : 0.0;
   }
};

#endif // TOKIO_BASKETMANAGER_MQH
