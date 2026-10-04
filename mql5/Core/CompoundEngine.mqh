//+------------------------------------------------------------------+
//|                                               CompoundEngine.mqh  |
//|   TokioQuant - INTERES COMPUESTO (la 8va maravilla)               |
//|                                                                   |
//|   OBJETIVO: que el lote base crezca con el capital para que el    |
//|   crecimiento sea EXPONENCIAL (geometrico) en vez de plano        |
//|   (aritmetico), pero SIN aumentar el riesgo relativo.             |
//|                                                                   |
//|   PRINCIPIO CENTRAL (medido con datos reales del EA):             |
//|   El drawdown NO depende del lote: depende de la RAZON            |
//|   lote/capital. Con 0.01 y 3900 USC el DD fue 1.4%; con el mismo  |
//|   0.01 y 1690 USC el DD fue 81%. Por eso el lote debe moverse     |
//|   SIEMPRE proporcional al capital: asi la razon de riesgo queda   |
//|   CONSTANTE mientras la cuenta crece de forma compuesta.          |
//|                                                                   |
//|   MATEMATICA:                                                     |
//|     P    = B - B0                    (ganancia sobre el anclaje)  |
//|     Beff = B0 + f * P     si P > 0   (reinvierte solo una parte)  |
//|     Beff = B              si P <= 0  (des-apalanca 1:1 al perder) |
//|     G    = Beff / B0                 (multiplicador de crecim.)   |
//|     lote = L0 * G * throttle(DD)                                  |
//|                                                                   |
//|   Como lote es proporcional al capital -> el beneficio por ciclo  |
//|   tambien lo es -> dB/dt = r*B -> B(t) = B0*e^(r t). Eso ES       |
//|   interes compuesto: crecimiento exponencial verdadero.           |
//|                                                                   |
//|   SEGURIDAD (por que "ni se nota" el riesgo):                     |
//|   1. Solo cuenta ganancia REALIZADA (balance), nunca flotante.    |
//|   2. f<1 deja un colchon permanente que nunca se arriesga.        |
//|   3. Al perder des-apalanca 1:1 (anti-martingala de capital).     |
//|   4. throttle(DD) reduce el lote en drawdown (habria evitado el   |
//|      81% del SEG 3).                                              |
//|   5. Solo recalcula con la cesta VACIA: jamas cambia el lote a    |
//|      mitad de un grid (romperia la matematica del basket).        |
//|   6. Histeresis: exige superar el umbral con margen para subir,   |
//|      evitando oscilar entre dos escalones.                        |
//+------------------------------------------------------------------+
#ifndef TOKIO_COMPOUNDENGINE_MQH
#define TOKIO_COMPOUNDENGINE_MQH

#include "Utilities.mqh"
#include "Database.mqh"

class CCompoundEngine
{
private:
   SConfig    m_cfg;
   CDatabase *m_db;

   double m_anchor;      // B0: capital de referencia donde lote = baseLot
   double m_growth;      // G: multiplicador vigente (1.0 = sin crecimiento)
   double m_effLot;      // Lote base efectivo ya normalizado al bróker
   double m_rawLot;      // Lote teorico antes de cuantizar (para el panel)
   double m_nextStepAt;  // Balance necesario para el proximo escalon
   bool   m_underCap;    // true si el bankroll obliga a operar sobre-apalancado
   bool   m_ready;

   // --- Banco de fraccion (redondeo estocastico / dithering) ---
   // El bróker solo acepta multiplos de m_vstep (0.01). Si el lote teorico
   // es 0.0136 no existe forma de operarlo: al truncar SIEMPRE a 0.01 el
   // interes compuesto quedaria CONGELADO hasta duplicar el capital.
   // Solucion: acumular la fraccion sobrante ciclo a ciclo y, cuando el
   // banco llega a un paso completo, operar un escalon mas.
   // Resultado: el lote MEDIO es exactamente el teorico -> compuesto real
   // y suave incluso con granularidad gruesa.
   double m_credit;
   double m_lastBalance;   // Balance de la ultima liquidacion contabilizada

   // Lote minimo/step del simbolo (cuantizacion del bróker)
   double m_vmin, m_vstep;

public:
   CCompoundEngine(void) : m_db(NULL), m_anchor(0), m_growth(1.0), m_effLot(0),
                           m_rawLot(0), m_nextStepAt(0), m_underCap(false),
                           m_ready(false), m_credit(0.0), m_lastBalance(-1.0),
                           m_vmin(0.01), m_vstep(0.01) {}

   //--- Getters para telemetria / dashboard ---
   double Growth(void)     const { return m_growth; }
   double EffLot(void)     const { return m_effLot; }
   double RawLot(void)     const { return m_rawLot; }
   double Anchor(void)     const { return m_anchor; }
   double NextStepAt(void) const { return m_nextStepAt; }
   bool   UnderCapital(void) const { return m_underCap; }

   //+---------------------------------------------------------------+
   //| Init: fija el anclaje B0 y lo persiste para que sobreviva a    |
   //| reinicios del terminal (si no, el compuesto se reiniciaria).   |
   //+---------------------------------------------------------------+
   void Init(CDatabase &db, const SConfig &cfg, double balance)
   {
      m_cfg = cfg;
      m_db  = GetPointer(db);

      m_vmin  = SymbolInfoDouble(cfg.symbol, SYMBOL_VOLUME_MIN);
      m_vstep = SymbolInfoDouble(cfg.symbol, SYMBOL_VOLUME_STEP);
      if(m_vmin  <= 0) m_vmin  = 0.01;
      if(m_vstep <= 0) m_vstep = 0.01;

      m_effLot = cfg.baseLot;
      m_growth = 1.0;

      if(!cfg.useCompound) { m_ready = false; return; }

      // 1) Anclaje manual (recomendado: el capital donde ya validaste el riesgo)
      if(cfg.compoundAnchor > 0.0)
      {
         m_anchor = cfg.compoundAnchor;
      }
      else
      {
         // 2) Anclaje automatico persistido: la primera vez usa el balance actual
         double stored = 0.0;
         if(m_db != NULL && m_db.IsOpen() &&
            m_db.QueryDouble("SELECT dval FROM meta WHERE key='compound_anchor';", stored)
            && stored > 0)
            m_anchor = stored;
         else
         {
            m_anchor = balance;
            if(m_db != NULL && m_db.IsOpen())
               m_db.Exec(StringFormat(
                  "INSERT OR REPLACE INTO meta(key,dval) VALUES('compound_anchor',%.2f);",
                  m_anchor));
         }
      }

      if(m_anchor <= 0) { m_ready = false; return; }
      m_ready = true;

      // Aviso duro: operar por debajo del anclaje = riesgo relativo mayor al
      // validado. El lote no puede bajar del minimo del bróker.
      double proportional = cfg.baseLot * (balance / m_anchor);
      if(proportional < m_vmin - 1e-9)
      {
         m_underCap = true;
         Print("### AVISO COMPOUND: balance ", DoubleToString(balance,2),
               " esta por DEBAJO del anclaje ", DoubleToString(m_anchor,2),
               ". El lote proporcional seria ", DoubleToString(proportional,4),
               " pero el minimo del broker es ", DoubleToString(m_vmin,2),
               " -> operaras con riesgo relativo x",
               DoubleToString(m_vmin/MathMax(proportional,0.0001),2), " ###");
      }

      Print("=== INTERES COMPUESTO ON | anclaje=", DoubleToString(m_anchor,2),
            " | lote base=", DoubleToString(cfg.baseLot,2),
            " | reinversion=", DoubleToString(cfg.compoundReinvest*100,0), "%",
            " | modo=", (cfg.compoundSmooth ? "CONTINUO" : "ESCALON"), " ===");

      // La razon lote/capital es la que define el drawdown (medido en real).
      // Con f=1.0 esa razon queda CONSTANTE: mismo riesgo que el validado.
      // Con f>1.0 el lote crece mas rapido que el capital -> el riesgo sube
      // en cada ciclo y el drawdown historico deja de ser representativo.
      if(cfg.compoundReinvest > 1.0)
         Print("### PELIGRO COMPOUND: reinversion ",
               DoubleToString(cfg.compoundReinvest*100,0),
               "% > 100% APALANCA la cuenta: el lote crecera mas rapido que el",
               " capital y el riesgo superara al que validaste. Usa 1.00 o menos. ###");
   }

   //+---------------------------------------------------------------+
   //| Recalcula el lote base efectivo. LLAMAR SOLO CON CESTA VACIA.  |
   //| balance = capital realizado; ddPct = drawdown actual.          |
   //+---------------------------------------------------------------+
   double Recompute(double balance, double ddPct)
   {
      if(!m_cfg.useCompound || !m_ready || m_anchor <= 0)
      {
         m_growth = 1.0;
         m_rawLot = m_cfg.baseLot;
         m_effLot = NormalizeVolume(m_cfg.symbol, m_cfg.baseLot, m_cfg.maxLotOrder);
         return m_effLot;
      }

      m_lastBalance = balance;

      // --- 1. Capital efectivo (SOLO ganancia REALIZADA sobre el anclaje) ---
      double P    = balance - m_anchor;
      double Beff;
      if(P > 0.0)
         Beff = m_anchor + m_cfg.compoundReinvest * P;  // reinvierte una fraccion
      else
         Beff = balance;                                 // por debajo: se encoge

      // --- 2. Multiplicador de crecimiento ---
      // Con compoundMinMult = 1.0 (recomendado) el sistema NUNCA baja del
      // comportamiento base: por debajo del anclaje G queda fijo en 1.0, o sea
      // lote = InpBaseLot y topes de exposicion originales. Solo crece con lo
      // GANADO por encima del anclaje. Esto garantiza que en drawdown el EA
      // opere exactamente igual que en la configuracion ya validada, sin
      // estrechar los topes (lo que podria estorbar a la recuperacion).
      double G = SafeDiv(Beff, m_anchor, 1.0);
      G = Clamp(G, m_cfg.compoundMinMult, m_cfg.compoundMaxMult);

      // Aviso vivo: operar muy por debajo del anclaje implica riesgo relativo
      // mayor al validado y el minimo del bróker impide reducir el lote.
      m_underCap = (balance < m_anchor * 0.95);

      // --- 3. Freno por drawdown: arriesga menos cuando vas perdiendo.
      //     Curva convexa (exp 1.5): casi no penaliza al principio y
      //     recorta fuerte cerca del kill switch.
      double throttle = 1.0;
      if(m_cfg.equityStopPct > 0.0 && ddPct > 0.0)
      {
         double x = Clamp(ddPct / m_cfg.equityStopPct, 0.0, 1.0);
         throttle = Clamp(1.0 - MathPow(x, 1.5), m_cfg.compoundDDFloor, 1.0);
      }

      // --- 4. Lote teorico ---
      m_growth = G;
      m_rawLot = m_cfg.baseLot * G * throttle;

      // --- 5. El lote base queda FRACCIONARIO a proposito ---
      // La cuantizacion al paso del bróker NO se hace aqui: se hace orden por
      // orden en Quantize(). Como cada cesta despliega entre 5 y 18 niveles,
      // repartir la fraccion por ORDEN da una granularidad 5-18 veces mas fina
      // que hacerlo una vez por ciclo -> el crecimiento se nota en cada cesta
      // en lugar de esperar a duplicar el capital.
      m_effLot = m_rawLot;

      if(!m_cfg.compoundSmooth)
      {
         // MODO ESCALON (clasico): cuantiza ya, con histeresis. Mas predecible
         // pero el crecimiento se congela entre escalon y escalon.
         double quantized = MathFloor(m_rawLot / m_vstep) * m_vstep;
         if(quantized < m_vmin) quantized = m_vmin;

         // Subir exige margen extra; bajar es inmediato (protege rapido).
         if(quantized > m_effLot + 1e-9)
         {
            double needed = (m_effLot + m_vstep) * (1.0 + m_cfg.compoundHysteresis);
            if(m_rawLot < needed) quantized = m_effLot;
         }
         m_effLot = NormalizeVolume(m_cfg.symbol, quantized, m_cfg.maxLotOrder * G);
      }

      // --- 6. Balance necesario para el proximo escalon (informativo) ---
      double nextLot = m_effLot + m_vstep;
      double needG   = SafeDiv(nextLot * (1.0 + m_cfg.compoundHysteresis),
                               m_cfg.baseLot, 0.0);
      m_nextStepAt   = (m_cfg.compoundReinvest > 0.0)
                       ? m_anchor + m_anchor * (needG - 1.0) / m_cfg.compoundReinvest
                       : 0.0;

      return m_effLot;
   }

   //+---------------------------------------------------------------+
   //| Cuantiza un lote deseado al paso del bróker. SE LLAMA UNA VEZ  |
   //| POR ORDEN.                                                     |
   //|                                                                |
   //| El bróker solo acepta multiplos de m_vstep (0.01). Si el lote  |
   //| teorico de un nivel es 0.0115, truncar siempre a 0.01 tiraria  |
   //| la fraccion y congelaria el compuesto. Aqui la fraccion se     |
   //| guarda en un banco: cuando acumula un paso completo, esa orden |
   //| sale con un escalon mas.                                       |
   //|                                                                |
   //| Con 5-18 niveles por cesta el promedio converge DENTRO de la   |
   //| propia cesta -> el beneficio por ciclo crece de forma continua |
   //| y visible, no a saltos.                                        |
   //+---------------------------------------------------------------+
   double Quantize(double desired, double maxOrder)
   {
      // Compuesto apagado o modo escalon -> comportamiento clasico intacto.
      if(!m_cfg.useCompound || !m_ready || !m_cfg.compoundSmooth)
         return NormalizeVolume(m_cfg.symbol, desired, maxOrder);

      double target = MathMax(desired, m_vmin);
      double q      = MathFloor(target / m_vstep) * m_vstep;

      m_credit += (target - q);
      if(m_credit >= m_vstep - 1e-9)
      {
         q        += m_vstep;
         m_credit -= m_vstep;
      }
      // El banco nunca guarda mas de un paso (evita saltos acumulados).
      m_credit = Clamp(m_credit, 0.0, m_vstep);

      if(q < m_vmin) q = m_vmin;
      return NormalizeVolume(m_cfg.symbol, q, maxOrder);
   }
};

#endif // TOKIO_COMPOUNDENGINE_MQH
