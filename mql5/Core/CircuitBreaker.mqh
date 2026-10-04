//+------------------------------------------------------------------+
//|                                               CircuitBreaker.mqh  |
//|   TokioQuant - CORTACIRCUITOS INTELIGENTE                          |
//|                                                                    |
//|   POR QUE EXISTE (medido con datos reales del propio bot):         |
//|   Las cestas sanas se recuperan en ~3 min desde su peor momento    |
//|   (mediana 9.5 min de vida, maximo historico 62 min). Un stop por  |
//|   % de equity dispara JUSTO en ese peor momento y convierte una    |
//|   excursion normal en perdida realizada. Por eso el kill switch    |
//|   "tonto" se siente injusto: casi siempre corta algo que iba a     |
//|   recuperarse.                                                     |
//|                                                                    |
//|   Pero quitarlo del todo deja la cola de riesgo sin limite, que    |
//|   es como mueren las cuentas con martingala.                       |
//|                                                                    |
//|   SOLUCION: distinguir EXCURSION NORMAL de CESTA ROTA, y actuar    |
//|   de forma graduada en vez de liquidar todo de golpe:              |
//|                                                                    |
//|     1. STOP_ADD  -> deja de echar lena al fuego (no cierra nada).  |
//|        La perdida flotante ya supera un umbral: mantener, no       |
//|        promediar mas. Es la accion mas rentable segun los datos    |
//|        (el edge se acaba a partir del nivel 4-5).                  |
//|                                                                    |
//|     2. DERISK    -> la cesta lleva MUCHO mas de lo normal viva.    |
//|        Ya no es ruido: es estructura. Recorta la PEOR posicion     |
//|        poco a poco para bajar exposicion sin liquidar el conjunto. |
//|                                                                    |
//|     3. CLOSE_ALL -> solo por FISICA: el nivel de margen se acerca  |
//|        al stop-out del broker. Aqui no hay opinion posible; si no  |
//|        cierras tu, cierra el broker y peor.                        |
//|                                                                    |
//|   El stop por % de equity queda como ultimo recurso, pensado para  |
//|   ponerse MUY lejos: con la exposicion bien limitada casi nunca    |
//|   deberia llegar a dispararse.                                     |
//+------------------------------------------------------------------+
#ifndef TOKIO_CIRCUITBREAKER_MQH
#define TOKIO_CIRCUITBREAKER_MQH

#include "Utilities.mqh"

// Accion recomendada por el cortacircuitos, de menor a mayor severidad.
enum ENUM_BREAKER
{
   BRK_NONE = 0,    // todo normal
   BRK_STOP_ADD,    // no abrir/promediar mas; mantener lo abierto
   BRK_DERISK,      // recortar la peor posicion progresivamente
   BRK_CLOSE_ALL    // cerrar todo (solo margen o ultimo recurso)
};

class CCircuitBreaker
{
private:
   SConfig m_cfg;
   ENUM_BREAKER m_last;

public:
   CCircuitBreaker(void) : m_last(BRK_NONE) {}

   void Init(const SConfig &cfg) { m_cfg = cfg; m_last = BRK_NONE; }

   ENUM_BREAKER Last(void) const { return m_last; }

   //+---------------------------------------------------------------+
   //| Evalua el estado. basketAgeMin = minutos de vida de la cesta.  |
   //+---------------------------------------------------------------+
   ENUM_BREAKER Check(double floating, double balance, double ddPct,
                      double basketAgeMin, int openPos)
   {
      ENUM_BREAKER act = BRK_NONE;

      if(openPos > 0)
      {
         // --- 1. FISICA: nivel de margen. Innegociable. ---
         double mUsed  = AccountInfoDouble(ACCOUNT_MARGIN);
         double mLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
         if(m_cfg.brkMarginFloor > 0.0 && mUsed > 0.0 &&
            mLevel > 0.0 && mLevel < m_cfg.brkMarginFloor)
         {
            m_last = BRK_CLOSE_ALL;
            return BRK_CLOSE_ALL;
         }

         // --- 2. TIEMPO: cesta muy por encima de su vida normal ---
         // Si ademas esta en perdida, no es ruido: es estructura rota.
         if(m_cfg.brkMaxBasketMin > 0 && basketAgeMin > m_cfg.brkMaxBasketMin
            && floating < 0.0)
            act = BRK_DERISK;

         // --- 3. FLOTANTE: dejar de promediar (sin cerrar nada) ---
         // Umbral en % del balance para que sea comparable entre cuentas.
         if(m_cfg.brkStopAddPct > 0.0 && balance > 0.0)
         {
            double floatPct = -floating / balance * 100.0;   // positivo si perdemos
            if(floatPct >= m_cfg.brkStopAddPct && act == BRK_NONE)
               act = BRK_STOP_ADD;
         }
      }

      // --- 4. ULTIMO RECURSO: stop por % de equity (ponerlo MUY lejos) ---
      if(m_cfg.equityStopPct > 0.0 && ddPct >= m_cfg.equityStopPct)
         act = BRK_CLOSE_ALL;

      m_last = act;
      return act;
   }

   // Etiqueta legible para el log / dashboard.
   string Name(ENUM_BREAKER a)
   {
      switch(a)
      {
         case BRK_STOP_ADD:  return "STOP-ADD (no promediar)";
         case BRK_DERISK:    return "DERISK (recortando peor)";
         case BRK_CLOSE_ALL: return "CIERRE TOTAL";
      }
      return "OK";
   }
};

#endif // TOKIO_CIRCUITBREAKER_MQH
