//+------------------------------------------------------------------+
//|                                                LearningEngine.mqh |
//|   TokioQuant - Memoria persistente + optimizador adaptativo       |
//|   Guarda cada basket y snapshot en SQLite, y ajusta step/mart     |
//|   segun el desempeno historico por regimen.                       |
//+------------------------------------------------------------------+
#ifndef TOKIO_LEARNINGENGINE_MQH
#define TOKIO_LEARNINGENGINE_MQH

#include "Utilities.mqh"
#include "Database.mqh"

class CLearningEngine
{
private:
   SConfig    m_cfg;
   CDatabase *m_db;     // puntero a la BD que posee el Engine

public:
   double initialBankroll;

   CLearningEngine(void) : m_db(NULL), initialBankroll(0) {}

   // Crea tablas y recupera/inicializa el bankroll inicial persistente.
   void Init(CDatabase &db, const SConfig &cfg, double sessionBalance)
   {
      m_cfg = cfg;
      m_db  = GetPointer(db);
      initialBankroll = sessionBalance;

      if(m_db == NULL || !m_db.IsOpen()) return;

      m_db.Exec("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, dval REAL);");
      // baskets: incluye 'reason' y 'adx' para compatibilidad con el panel.
      m_db.Exec(
         "CREATE TABLE IF NOT EXISTS baskets("
         "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, symbol TEXT,"
         "regime INTEGER, atr REAL, adx REAL, momentum REAL, spread REAL,"
         "volume REAL, score REAL, profit REAL, dd REAL, recovery INTEGER,"
         "dur_min REAL, levels INTEGER, result INTEGER, reason TEXT, balance REAL);");
      // equity: incluye 'adx' (el panel lo lee junto con atr).
      m_db.Exec(
         "CREATE TABLE IF NOT EXISTS equity("
         "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER,"
         "equity REAL, balance REAL, floating REAL, open_pos INTEGER,"
         "adx REAL DEFAULT 0, atr REAL);");
      // Cuenta REAL (compartida): la escriben AMBOS EAs con AccountInfo.
      // La lee el panel COMBINADO para el total real y el nivel de margen.
      m_db.Exec(
         "CREATE TABLE IF NOT EXISTS account("
         "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER,"
         "balance REAL, equity REAL, floating REAL,"
         "margin REAL, margin_free REAL, margin_level REAL);");
      // telemetry: fila completa de estado del cerebro para el cockpit.
      m_db.Exec(
         "CREATE TABLE IF NOT EXISTS telemetry("
         "id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER,"
         "regime INTEGER, regime_name TEXT,"
         "trend REAL, trend_dir INTEGER, momentum REAL, volatility REAL,"
         "liquidity REAL, risk REAL, recovery REAL, quality REAL, confidence REAL,"
         "exp_score REAL, margin_score REAL, float_score REAL, vol_score REAL,"
         "corr_score REAL, dd_score REAL,"
         "adx REAL, atr REAL, atr_ratio REAL, spread REAL, rsi REAL, ddpct REAL,"
         "rec_level INTEGER, equity REAL, balance REAL, floating REAL,"
         "buys INTEGER, sells INTEGER, lots REAL, delta REAL, step REAL,"
         "cmp_growth REAL DEFAULT 1, cmp_lot REAL DEFAULT 0,"
         "cmp_anchor REAL DEFAULT 0, cmp_next REAL DEFAULT 0);");

      // Migracion para bases creadas por versiones anteriores.
      // Se ejecuta UNA sola vez: los ALTER sobre una columna existente hacen
      // que MT5 escriba "duplicate column name" en el log, y en una base
      // nueva (que ya nace con todas las columnas) ese ruido es puro estorbo.
      double _sv = 0.0;
      double _hasCols = 0.0;   // BD nueva: ya nace con todas las columnas, no hay nada que migrar
      m_db.QueryDouble("SELECT COUNT(*) FROM pragma_table_info('telemetry') WHERE name='cmp_next';", _hasCols);
      if(_hasCols > 0.5 && !m_db.QueryDouble("SELECT dval FROM meta WHERE key='schema_v';", _sv))
         m_db.Exec("INSERT OR REPLACE INTO meta(key,dval) VALUES('schema_v',2);");
      else if(!m_db.QueryDouble("SELECT dval FROM meta WHERE key='schema_v';", _sv) || _sv < 2.0)
      {
         m_db.ExecQuiet("ALTER TABLE equity  ADD COLUMN adx REAL DEFAULT 0;");
         m_db.ExecQuiet("ALTER TABLE baskets ADD COLUMN reason TEXT;");
         m_db.ExecQuiet("ALTER TABLE telemetry ADD COLUMN cmp_growth REAL DEFAULT 1;");
         m_db.ExecQuiet("ALTER TABLE telemetry ADD COLUMN cmp_lot REAL DEFAULT 0;");
         m_db.ExecQuiet("ALTER TABLE telemetry ADD COLUMN cmp_anchor REAL DEFAULT 0;");
         m_db.ExecQuiet("ALTER TABLE telemetry ADD COLUMN cmp_next REAL DEFAULT 0;");
         m_db.Exec("INSERT OR REPLACE INTO meta(key,dval) VALUES('schema_v',2);");
      }

      // V3: eventos (reinicios, fallos de cierre, trading desactivado...).
      m_db.Exec("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "ts INTEGER, login INTEGER, type TEXT, detail TEXT, balance REAL, equity REAL);");

      double stored = 0;
      if(m_db.QueryDouble("SELECT dval FROM meta WHERE key='initial_bankroll';", stored)
         && stored > 0)
         initialBankroll = stored;
      else
         m_db.Exec(StringFormat(
            "INSERT OR REPLACE INTO meta(key,dval) VALUES('initial_bankroll',%.2f);",
            initialBankroll));
   }

   // Re-ancla el bankroll inicial (reset en caliente, sin reiniciar MT5).
   void Reseed(double balance)
   {
      initialBankroll = balance;
      if(m_db != NULL && m_db.IsOpen())
         m_db.Exec(StringFormat(
            "INSERT OR REPLACE INTO meta(key,dval) VALUES('initial_bankroll',%.2f);",
            balance));
   }

   // Evento de auditoria (texto libre, sin comillas simples).
   void Event(const string type, const string detail)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      string d = detail; StringReplace(d, "'", "");
      m_db.Exec(StringFormat(
         "INSERT INTO events(ts,login,type,detail,balance,equity) VALUES(%I64d,%I64d,'%s','%s',%.2f,%.2f);",
         (long)TimeCurrent(), AccountInfoInteger(ACCOUNT_LOGIN), type, d,
         AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)));
   }

   // Registra el resultado de un basket cerrado.
   void RecordBasket(const SMarket &m, ENUM_REGIME regime, double score, double profit,
                     double ddPct, int recoveryLevel, double durMin, int levels,
                     const string reason, double balance)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      int result = (profit > 0) ? 1 : 0;
      string sql = StringFormat(
         "INSERT INTO baskets(ts,symbol,regime,atr,adx,momentum,spread,volume,"
         "score,profit,dd,recovery,dur_min,levels,result,reason,balance) VALUES("
         "%I64d,'%s',%d,%.3f,%.2f,%.3f,%.3f,%.1f,%.1f,%.2f,%.2f,%d,%.2f,%d,%d,'%s',%.2f);",
         (long)TimeCurrent(), m_cfg.symbol, (int)regime, m.atr, m.adx, m.momentum,
         m.spread, m.volume, score, profit, ddPct, recoveryLevel, durMin, levels,
         result, reason, balance);
      m_db.Exec(sql);
   }

   // Snapshot periodico de equity (curva).
   void Snapshot(double equity, double balance, double floating, int openPos,
                 double adx, double atr)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      string sql = StringFormat(
         "INSERT INTO equity(ts,equity,balance,floating,open_pos,adx,atr) "
         "VALUES(%I64d,%.2f,%.2f,%.2f,%d,%.2f,%.3f);",
         (long)TimeCurrent(), equity, balance, floating, openPos, adx, atr);
      m_db.Exec(sql);
   }

   // Escribe una fila de telemetria completa (alimenta el cockpit en vivo).
   // Snapshot de la CUENTA REAL (valores AccountInfo, compartidos).
   void SnapshotAccount(double bal, double eq, double flt,
                        double margin, double mfree, double mlevel)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      string sql = StringFormat(
         "INSERT INTO account(ts,balance,equity,floating,margin,margin_free,margin_level) "
         "VALUES(%I64d,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f);",
         (long)TimeCurrent(), bal, eq, flt, margin, mfree, mlevel);
      m_db.Exec(sql);
   }

   // Acota la tabla account (evita crecimiento infinito).
   void TrimAccount(int keep)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      m_db.ExecQuiet(StringFormat(
         "DELETE FROM account WHERE id < (SELECT MAX(id)-%d FROM account);", keep));
   }

   void WriteTelemetry(const STelemetry &t)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      // Escapamos comillas simples del nombre de regimen por seguridad.
      string rn = t.regimeName;
      StringReplace(rn, "'", "");
      string sql = StringFormat(
         "INSERT INTO telemetry(ts,regime,regime_name,trend,trend_dir,momentum,"
         "volatility,liquidity,risk,recovery,quality,confidence,exp_score,"
         "margin_score,float_score,vol_score,corr_score,dd_score,adx,atr,atr_ratio,"
         "spread,rsi,ddpct,rec_level,equity,balance,floating,buys,sells,lots,delta,step,"
         "cmp_growth,cmp_lot,cmp_anchor,cmp_next) "
         "VALUES(%I64d,%d,'%s',%.1f,%d,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,%.1f,"
         "%.1f,%.1f,%.1f,%.1f,%.2f,%.3f,%.3f,%.3f,%.1f,%.2f,%d,%.2f,%.2f,%.2f,%d,%d,"
         "%.2f,%.2f,%.3f,%.4f,%.2f,%.2f,%.2f);",
         t.ts, t.regime, rn, t.trend, t.trendDir, t.momentum, t.volatility,
         t.liquidity, t.risk, t.recovery, t.quality, t.confidence, t.expScore,
         t.marginScore, t.floatScore, t.volScore, t.corrScore, t.ddScore, t.adx,
         t.atr, t.atrRatio, t.spread, t.rsi, t.ddpct, t.recLevel, t.equity,
         t.balance, t.floating, t.buys, t.sells, t.lots, t.delta, t.step,
         t.cmpGrowth, t.cmpLot, t.cmpAnchor, t.cmpNext);
      m_db.Exec(sql);
   }

   // Mantiene la tabla telemetry acotada (evita crecimiento infinito).
   void TrimTelemetry(int keep)
   {
      if(m_db == NULL || !m_db.IsOpen()) return;
      m_db.ExecQuiet(StringFormat(
         "DELETE FROM telemetry WHERE id < (SELECT MAX(id)-%d FROM telemetry);", keep));
   }

   // --- OPTIMIZADOR: factor de step segun desempeno historico del regimen ---
   // Si el regimen suele perder, ensancha; si suele ganar, ajusta ligeramente.
   double OptimizeStepMult(ENUM_REGIME regime)
   {
      if(m_db == NULL || !m_db.IsOpen()) return 1.0;
      double cnt = 0;
      if(!m_db.QueryDouble(StringFormat(
            "SELECT COUNT(*) FROM baskets WHERE regime=%d AND dur_min>0.05;", (int)regime), cnt) || cnt < 20)
         return 1.0; // muestra insuficiente -> sin cambios

      double avg = 0;
      if(!m_db.QueryDouble(StringFormat(
            "SELECT AVG(profit) FROM baskets WHERE regime=%d AND dur_min>0.05;", (int)regime), avg))
         return 1.0;

      if(avg < 0) return 1.20; // historicamente perdedor -> mas prudente (grid amplio)
      if(avg > 0) return 0.95; // historicamente ganador -> algo mas agresivo
      return 1.0;
   }

   // --- OPTIMIZADOR: factor de martingala segun desempeno historico ---
   double OptimizeMartMult(ENUM_REGIME regime)
   {
      if(m_db == NULL || !m_db.IsOpen()) return 1.0;
      double winRate = 0;
      if(!m_db.QueryDouble(StringFormat(
            "SELECT AVG(result) FROM baskets WHERE regime=%d AND dur_min>0.05;", (int)regime), winRate))
         return 1.0;
      // winRate 0..1. Bajo win rate -> reducir agresividad de martingala.
      return Clamp(MapRange(winRate, 0.3, 0.8, 0.85, 1.05), 0.85, 1.05);
   }
};

#endif // TOKIO_LEARNINGENGINE_MQH
