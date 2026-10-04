//+------------------------------------------------------------------+
//|                                                 SessionEngine.mqh |
//|   TokioQuant XAU - Guardian de sesion (especifico de oro)         |
//|                                                                   |
//|   BTC opera 24/7; XAUUSD NO: cierra el viernes por la noche y      |
//|   reabre el domingo/lunes. Dos peligros de un grid/martingala en   |
//|   un mercado con horario:                                          |
//|                                                                   |
//|   1. GAP DEL LUNES: el precio puede reabrir muy lejos del cierre   |
//|      del viernes. Una cesta martingala mantenida durante el fin de |
//|      semana puede saltarse todos los niveles del grid de golpe.    |
//|      -> Por eso, opcionalmente, APLANAMOS todo antes del cierre.   |
//|                                                                   |
//|   2. LIQUIDEZ POBRE en la apertura: spreads enormes y mechas.      |
//|      -> Esperamos unos minutos tras la apertura antes de sembrar.  |
//|                                                                   |
//|   Todo se mide en HORA DEL SERVIDOR (TimeCurrent). El usuario debe |
//|   ajustar las horas a su bróker (reloj del Market Watch de MT5).   |
//|   Ademas, sabado y domingo se consideran SIEMPRE cerrados como     |
//|   red de seguridad, sin depender de la configuracion de horas.     |
//+------------------------------------------------------------------+
#ifndef TOKIO_SESSIONENGINE_MQH
#define TOKIO_SESSIONENGINE_MQH

#include "Utilities.mqh"

class CSessionEngine
{
private:
   SConfig m_cfg;

   // Descompone la hora del servidor en dia de semana y hora.
   void Now(int &dow, int &hour, int &minute)
   {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      dow    = dt.day_of_week;   // 0=Dom 1=Lun ... 5=Vie 6=Sab
      hour   = dt.hour;
      minute = dt.min;
   }

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Fin de semana duro: sabado o domingo (red de seguridad absoluta).
   bool IsWeekend(void)
   {
      int dow, h, m; Now(dow, h, m);
      return (dow == 6 || dow == 0);
   }

   // Pregunta al BROKER si el simbolo tiene sesion de negociacion AHORA.
   // Es mucho mas fiable que adivinar horas a mano: cada simbolo (forex,
   // indices, metales) tiene su propio calendario y el broker ya lo conoce.
   // Si el broker no informa sesiones, devolvemos true (no bloquear).
   bool BrokerOpenNow(void)
   {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      ENUM_DAY_OF_WEEK d = (ENUM_DAY_OF_WEEK)dt.day_of_week;
      long nowSec = dt.hour * 3600 + dt.min * 60 + dt.sec;

      datetime from = 0, to = 0;
      bool anySession = false;
      for(uint i = 0; i < 8; i++)
      {
         if(!SymbolInfoSessionTrade(m_cfg.symbol, d, i, from, to)) break;
         anySession = true;
         if(nowSec >= (long)from && nowSec <= (long)to) return true;
      }
      // Sin informacion de sesiones -> no bloqueamos por horario
      if(!anySession) return true;
      return false;
   }

   // ¿Podemos ABRIR nuevas cestas ahora?
   bool CanOpenNew(void)
   {
      if(!m_cfg.avoidWeekend) return true;

      // 1) El broker manda: si el simbolo no cotiza ahora, no se abre nada.
      if(!BrokerOpenNow()) return false;

      int dow, h, m; Now(dow, h, m);

      // 2) Red de seguridad: sabado nunca.
      if(dow == 6) return false;

      // 3) Viernes tarde: dejar de abrir para no cargar cestas hacia el cierre.
      if(dow == 5 && h >= m_cfg.friStopHour) return false;

      // 4) Colchon tras la reapertura (liquidez pobre y spreads anchos).
      //    Domingo: espera a sunResumeHour SOLO si se configuro (>0).
      if(dow == 0 && m_cfg.sunResumeHour > 0 && h < m_cfg.sunResumeHour) return false;
      if(dow == 1 && h < m_cfg.monStartHour) return false;

      return true;
   }

   // ¿Debemos APLANAR todo ya (proteccion de gap de fin de semana)?
   bool ShouldFlatten(void)
   {
      if(!m_cfg.weekendFlatten) return false;

      int dow, h, m; Now(dow, h, m);

      // Sabado: fuera. Domingo NO se aplana: el mercado ya reabrio y una
      // cesta viva debe poder gestionarse con normalidad.
      if(dow == 6) return true;

      // Viernes a partir de la hora de aplanado
      if(dow == 5 && h >= m_cfg.friFlattenHour) return true;

      return false;
   }

   // Etiqueta para el log / dashboard.
   string Status(void)
   {
      if(!m_cfg.avoidWeekend) return "24/7";
      if(!BrokerOpenNow())    return "CERRADO (horario del broker)";
      if(IsWeekend())         return "FIN DE SEMANA";
      if(ShouldFlatten())     return "PRE-CIERRE (aplanando)";
      if(!CanOpenNew())       return "SIN NUEVAS (ventana horaria)";
      return "ABIERTO";
   }
};

#endif // TOKIO_SESSIONENGINE_MQH
