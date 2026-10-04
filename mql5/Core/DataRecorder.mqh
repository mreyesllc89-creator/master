//+------------------------------------------------------------------+
//|                                                 DataRecorder.mqh  |
//|   TokioQuant - CAJA NEGRA (el cerebro que guarda TODO)             |
//|                                                                    |
//|   POR QUE EXISTE:                                                  |
//|   La tabla 'baskets' guardaba el RESULTADO (profit) pero no el     |
//|   RIESGO. En un grid/martingala el profit no dice nada: ganar      |
//|   +1.50 arriesgando -5 no es lo mismo que ganar +1.50 arriesgando  |
//|   -300. Sin esa variable es IMPOSIBLE medir edge o calibrar nada.  |
//|                                                                    |
//|   QUE REGISTRA (por cada cesta, de principio a fin):               |
//|   - MAE : Maximum Adverse Excursion = lo mas hundida que estuvo.   |
//|           ES LA METRICA DE RIESGO. Sin ella no hay analisis.       |
//|   - MFE : Maximum Favorable Excursion = lo mas arriba que estuvo   |
//|           (dice si el TP deja dinero sobre la mesa).               |
//|   - Eficiencia = profit / |MAE| -> cuanto gano por unidad de       |
//|           riesgo REALMENTE asumido. Este es el "edge" de verdad.   |
//|   - Excursion de precio en contra, niveles y lotes maximos.        |
//|   - Contexto de ENTRADA y de SALIDA (regimen, ADX, ATR, RSI,       |
//|     spread, hora, dia) -> permite responder "¿en que condiciones   |
//|     este sistema gana y en cuales sufre?".                         |
//|   - Banderas: si se uso hedge, cierre parcial, nivel de recovery.  |
//|                                                                    |
//|   COSTE: unas pocas comparaciones por tick. Nada de I/O salvo un   |
//|   INSERT al cerrar la cesta. No afecta la velocidad de ejecucion.  |
//+------------------------------------------------------------------+
#ifndef TOKIO_DATARECORDER_MQH
#define TOKIO_DATARECORDER_MQH

#include "Utilities.mqh"
#include "Database.mqh"

class CDataRecorder
{
private:
   SConfig    m_cfg;
   CDatabase *m_db;
   bool       m_active;       // hay una cesta viva siendo grabada

   //--- Estado de la cesta en curso ---
   datetime m_openTime;
   double   m_openPrice;      // precio de referencia al abrir
   double   m_openBalance;

   double   m_mae;            // peor flotante (<=0)
   double   m_mfe;            // mejor flotante (>=0)
   datetime m_maeTime;        // cuando ocurrio el peor momento
   double   m_maeExcursion;   // distancia de precio en contra (peor)
   double   m_maeLots;        // lotes desplegados en el peor momento

   int      m_maxLevels;      // maximo de posiciones simultaneas
   double   m_maxLots;        // maximo de lotes acumulados
   int      m_maxRecLevel;    // nivel de recovery mas alto alcanzado
   bool     m_usedHedge;
   bool     m_usedPartial;

   //--- Contexto de entrada ---
   int    m_eRegime; double m_eAdx, m_eAtr, m_eAtrRatio, m_eRsi, m_eSpread, m_eConf;
   int    m_eHour, m_eDow;

public:
   CDataRecorder(void) : m_db(NULL), m_active(false), m_openTime(0), m_openPrice(0),
      m_openBalance(0), m_mae(0), m_mfe(0), m_maeTime(0), m_maeExcursion(0),
      m_maeLots(0), m_maxLevels(0), m_maxLots(0), m_maxRecLevel(0),
      m_usedHedge(false), m_usedPartial(false), m_eRegime(0), m_eAdx(0), m_eAtr(0),
      m_eAtrRatio(0), m_eRsi(0), m_eSpread(0), m_eConf(0), m_eHour(0), m_eDow(0) {}

   bool IsActive(void) const { return m_active; }

   //+---------------------------------------------------------------+
   //| Crea la tabla de la caja negra.                                |
   //+---------------------------------------------------------------+
   void Init(CDatabase &db, const SConfig &cfg)
   {
      m_cfg = cfg;
      m_db  = GetPointer(db);
      if(m_db == NULL || !m_db.IsOpen()) return;

      m_db.Exec(
         "CREATE TABLE IF NOT EXISTS trades("
         "id INTEGER PRIMARY KEY AUTOINCREMENT,"
         "symbol TEXT, open_ts INTEGER, close_ts INTEGER, dur_min REAL,"
         // --- resultado ---
         "profit REAL, reason TEXT, result INTEGER,"
         // --- RIESGO (lo que faltaba) ---
         "mae REAL, mfe REAL, mae_pct REAL, efficiency REAL,"
         "mae_ts INTEGER, mae_excursion REAL, mae_lots REAL, recovery_min REAL,"
         // --- despliegue del grid ---
         "max_levels INTEGER, max_lots REAL, max_rec_level INTEGER,"
         "used_hedge INTEGER, used_partial INTEGER,"
         // --- contexto de ENTRADA ---
         "e_regime INTEGER, e_adx REAL, e_atr REAL, e_atr_ratio REAL, e_rsi REAL,"
         "e_spread REAL, e_conf REAL, e_hour INTEGER, e_dow INTEGER, e_price REAL,"
         // --- contexto de SALIDA ---
         "x_regime INTEGER, x_adx REAL, x_atr REAL, x_atr_ratio REAL, x_rsi REAL,"
         "x_spread REAL, x_conf REAL, x_hour INTEGER, x_price REAL,"
         // --- cuenta ---
         "balance_open REAL, balance_close REAL, base_lot REAL, cmp_growth REAL,"
         // --- V3: desarme y trazabilidad ---
         "bank REAL DEFAULT 0, scalps INTEGER DEFAULT 0, paydowns INTEGER DEFAULT 0,"
         "positions INTEGER DEFAULT 0, estimated INTEGER DEFAULT 0, login INTEGER DEFAULT 0,"
         "ea TEXT, mfe_raw REAL DEFAULT 0);");
   }

   //+---------------------------------------------------------------+
   //| Arranca la grabacion de una cesta nueva (primera posicion).    |
   //+---------------------------------------------------------------+
   void OnBasketOpen(const SMarket &m, const SScores &s, ENUM_REGIME regime, double balance)
   {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      m_active      = true;
      m_openTime    = TimeCurrent();
      m_openPrice   = m.mid;
      m_openBalance = balance;

      m_mae = 0; m_mfe = 0; m_maeTime = 0; m_maeExcursion = 0; m_maeLots = 0;
      m_maxLevels = 0; m_maxLots = 0; m_maxRecLevel = 0;
      m_usedHedge = false; m_usedPartial = false;

      m_eRegime = (int)regime; m_eAdx = m.adx; m_eAtr = m.atr;
      m_eAtrRatio = m.atrRatio; m_eRsi = m.rsi; m_eSpread = m.spread;
      m_eConf = s.confidence; m_eHour = dt.hour; m_eDow = dt.day_of_week;
   }

   //+---------------------------------------------------------------+
   //| Se llama CADA TICK con la cesta viva. Solo comparaciones.      |
   //+---------------------------------------------------------------+
   void OnTick(const SMarket &m, const SBasket &b, int recLevel)
   {
      if(!m_active) return;

      // MAE: el momento mas doloroso (lo que de verdad arriesgaste)
      if(b.floating < m_mae)
      {
         m_mae          = b.floating;
         m_maeTime      = TimeCurrent();
         m_maeExcursion = MathAbs(m.mid - m_openPrice);
         m_maeLots      = b.lotsTotal;
      }
      // MFE: el mejor momento (dice si el TP se queda corto o largo)
      if(b.floating > m_mfe) m_mfe = b.floating;

      if(b.total     > m_maxLevels)   m_maxLevels   = b.total;
      if(b.lotsTotal > m_maxLots)     m_maxLots     = b.lotsTotal;
      if(recLevel    > m_maxRecLevel) m_maxRecLevel = recLevel;
   }

   void MarkHedge(void)   { if(m_active) m_usedHedge   = true; }
   void MarkPartial(void) { if(m_active) m_usedPartial = true; }

   //+---------------------------------------------------------------+
   //| Cierra y escribe la fila completa en la caja negra.            |
   //+---------------------------------------------------------------+
   void OnBasketClose(const SMarket &m, const SScores &s, ENUM_REGIME regime,
                      double profit, const string reason, double balanceClose,
                      double baseLot, double cmpGrowth,
                      double bank = 0.0, int scalps = 0, int paydowns = 0,
                      int positions = 0, bool estimated = false)
   {
      if(!m_active) return;
      m_active = false;
      if(m_db == NULL || !m_db.IsOpen()) return;

      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      double durMin = (TimeCurrent() - m_openTime) / 60.0;

      // INVARIANTE DE CONTABILIDAD (V3): el MFE muestreado se guarda TAL CUAL
      // en mfe_raw. La version anterior lo sobrescribia con el profit y el
      // aviso de abajo no podia saltar nunca: ocultaba el doble conteo.
      double mfeRaw = m_mfe;
      // (el deslizamiento al cerrar 10+ posiciones una a una mueve el neto unos USD:
      //  solo se avisa de diferencias que no puede explicar la ejecucion)
      if(profit > 2.0 * MathMax(m_mfe, 0.0) + 5.0 * m_cfg.moneyScale && !estimated && scalps == 0)
         Print("### AVISO CONTABILIDAD ", m_cfg.symbol, ": profit ",
               DoubleToString(profit,2), " > MFE ", DoubleToString(m_mfe,2),
               " -> revisar el calculo del realizado ###");
      if(profit > m_mfe) m_mfe = profit;   // columna mfe: compatible con el panel

      // % del capital que llego a estar en riesgo (comparable entre cuentas)
      double maePct = (m_openBalance > 0) ? (m_mae / m_openBalance * 100.0) : 0.0;

      // EFICIENCIA = ganancia por unidad de riesgo realmente asumido.
      // Es la metrica que dice si hay edge o solo suerte con martingala.
      double eff = (MathAbs(m_mae) > 0.0001) ? (profit / MathAbs(m_mae)) : 0.0;

      // Minutos que tardo en recuperarse desde el peor momento
      double recMin = (m_maeTime > 0) ? (TimeCurrent() - m_maeTime) / 60.0 : 0.0;

      string rs = reason; StringReplace(rs, "'", "");

      string sql = StringFormat(
         "INSERT INTO trades(symbol,open_ts,close_ts,dur_min,profit,reason,result,"
         "mae,mfe,mae_pct,efficiency,mae_ts,mae_excursion,mae_lots,recovery_min,"
         "max_levels,max_lots,max_rec_level,used_hedge,used_partial,"
         "e_regime,e_adx,e_atr,e_atr_ratio,e_rsi,e_spread,e_conf,e_hour,e_dow,e_price,"
         "x_regime,x_adx,x_atr,x_atr_ratio,x_rsi,x_spread,x_conf,x_hour,x_price,"
         "balance_open,balance_close,base_lot,cmp_growth,"
         "bank,scalps,paydowns,positions,estimated,login,ea,mfe_raw) VALUES("
         "'%s',%I64d,%I64d,%.2f,%.2f,'%s',%d,"
         "%.2f,%.2f,%.3f,%.3f,%I64d,%.2f,%.2f,%.2f,"
         "%d,%.2f,%d,%d,%d,"
         "%d,%.2f,%.3f,%.3f,%.1f,%.3f,%.1f,%d,%d,%.2f,"
         "%d,%.2f,%.3f,%.3f,%.1f,%.3f,%.1f,%d,%.2f,"
         "%.2f,%.2f,%.4f,%.4f,"
         "%.2f,%d,%d,%d,%d,%I64d,'%s',%.2f);",
         m_cfg.symbol, (long)m_openTime, (long)TimeCurrent(), durMin, profit, rs,
         (profit > 0 ? 1 : 0),
         m_mae, m_mfe, maePct, eff, (long)m_maeTime, m_maeExcursion, m_maeLots, recMin,
         m_maxLevels, m_maxLots, m_maxRecLevel, (m_usedHedge?1:0), (m_usedPartial?1:0),
         m_eRegime, m_eAdx, m_eAtr, m_eAtrRatio, m_eRsi, m_eSpread, m_eConf, m_eHour,
         m_eDow, m_openPrice,
         (int)regime, m.adx, m.atr, m.atrRatio, m.rsi, m.spread, s.confidence,
         dt.hour, m.mid,
         m_openBalance, balanceClose, baseLot, cmpGrowth,
         bank, scalps, paydowns, positions, (estimated ? 1 : 0),
         AccountInfoInteger(ACCOUNT_LOGIN), m_cfg.eaName, mfeRaw);

      m_db.Exec(sql);
   }
};

#endif // TOKIO_DATARECORDER_MQH
