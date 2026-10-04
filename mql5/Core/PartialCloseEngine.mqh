//+------------------------------------------------------------------+
//|                                            PartialCloseEngine.mqh |
//|   TokioQuant - Optimizacion del basket sin cerrar todo            |
//|   Cierra selectivamente: primero las peores, luego por lado.      |
//|   Libera margen y reduce la peor exposicion manteniendo control.  |
//+------------------------------------------------------------------+
#ifndef TOKIO_PARTIALCLOSEENGINE_MQH
#define TOKIO_PARTIALCLOSEENGINE_MQH

#include "Utilities.mqh"
#include <Trade\Trade.mqh>

class CPartialCloseEngine
{
private:
   string m_sym;
   ulong  m_magic;

   bool Mine(void)
   {
      return (PositionGetString(POSITION_SYMBOL) == m_sym &&
              (ulong)PositionGetInteger(POSITION_MAGIC) == m_magic);
   }

public:
   void Init(const SConfig &cfg) { m_sym = cfg.symbol; m_magic = cfg.magic; }

   // Cierra las 'n' peores posiciones (menor profit) del lado indicado.
   // side = SIDE_BOTH considera ambos lados. Devuelve cuantas cerro.
   int CloseWorst(CTrade &tr, int n, ENUM_SIDE side)
   {
      if(n <= 0) return 0;

      ulong  tk[]; double pf[];
      int c = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0) continue;
         if(!PositionSelectByTicket(t)) continue;
         if(!Mine()) continue;

         long type = PositionGetInteger(POSITION_TYPE);
         if(side == SIDE_BUY  && type != POSITION_TYPE_BUY)  continue;
         if(side == SIDE_SELL && type != POSITION_TYPE_SELL) continue;

         ArrayResize(tk, c + 1); ArrayResize(pf, c + 1);
         tk[c] = t;
         pf[c] = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         c++;
      }

      int closed = 0;
      for(int k = 0; k < n; k++)
      {
         int idx = -1; double worst = DBL_MAX;
         for(int j = 0; j < c; j++)
            if(tk[j] != 0 && pf[j] < worst) { worst = pf[j]; idx = j; }
         if(idx < 0) break;
         if(tr.PositionClose(tk[idx])) closed++;
         tk[idx] = 0;
      }
      return closed;
   }

   // Cierra una posicion concreta por ticket.
   bool CloseTicket(CTrade &tr, ulong ticket)
   {
      if(ticket == 0) return false;
      return tr.PositionClose(ticket);
   }
};

#endif // TOKIO_PARTIALCLOSEENGINE_MQH
