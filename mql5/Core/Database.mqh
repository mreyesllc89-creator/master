//+------------------------------------------------------------------+
//|                                                    Database.mqh   |
//|   TokioQuant - Wrapper SQLite nativo (sin DLL)                    |
//|   Responsabilidad unica: abrir/cerrar la BD y ejecutar SQL de     |
//|   forma segura. LearningEngine construye la logica encima.        |
//+------------------------------------------------------------------+
#ifndef TOKIO_DATABASE_MQH
#define TOKIO_DATABASE_MQH

#include "Utilities.mqh"

class CDatabase
{
private:
   int    m_handle;
   bool   m_enabled;
   string m_name;

public:
   CDatabase(void) : m_handle(INVALID_HANDLE), m_enabled(false), m_name("") {}

   bool IsOpen(void) const { return m_handle != INVALID_HANDLE; }
   int  Handle(void)  const { return m_handle; }

   // Abre (o crea) la BD en la carpeta Common\Files.
   bool Open(const SConfig &cfg)
   {
      m_enabled = cfg.useDB;
      m_name    = cfg.dbName;
      // GUARDA DE PROBADOR: si esto corre en el Probador de Estrategias, NO
      // debe tocar la base de la cuenta real (Common\Files es compartida por
      // todos los terminales de la maquina). Redirige a un fichero _TESTER.
      // Es la causa de que en agosto se colaran 5284 operaciones simuladas.
      if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION) ||
         MQLInfoInteger(MQL_VISUAL_MODE))
      {
         int dot = StringLen(m_name) - 8;   // ".sqlite"
         string base = (StringFind(m_name, ".sqlite") >= 0)
                       ? StringSubstr(m_name, 0, StringFind(m_name, ".sqlite")) : m_name;
         m_name = base + "_TESTER.sqlite";
      }
      if(!m_enabled) return false;

      m_handle = DatabaseOpen(m_name,
                    DATABASE_OPEN_READWRITE | DATABASE_OPEN_CREATE | DATABASE_OPEN_COMMON);
      if(m_handle == INVALID_HANDLE)
      {
         Print("CDatabase: no se pudo abrir '", m_name, "' err=", GetLastError());
         return false;
      }
      return true;
   }

   void Close(void)
   {
      if(m_handle != INVALID_HANDLE)
      {
         DatabaseClose(m_handle);
         m_handle = INVALID_HANDLE;
      }
   }

   // Ejecuta una sentencia sin resultado (CREATE/INSERT/UPDATE).
   bool Exec(const string sql)
   {
      if(m_handle == INVALID_HANDLE) return false;
      if(!DatabaseExecute(m_handle, sql))
      {
         Print("CDatabase.Exec err=", GetLastError(), " SQL=", sql);
         return false;
      }
      return true;
   }

   // Igual que Exec pero sin imprimir en fallo (para ALTER TABLE idempotentes:
   // fallan si la columna ya existe y eso es esperado).
   bool ExecQuiet(const string sql)
   {
      if(m_handle == INVALID_HANDLE) return false;
      return DatabaseExecute(m_handle, sql);
   }

   // Lee un unico valor REAL de una consulta de una sola columna.
   // Devuelve true si obtuvo fila.
   bool QueryDouble(const string sql, double &out)
   {
      if(m_handle == INVALID_HANDLE) return false;
      int req = DatabasePrepare(m_handle, sql);
      if(req == INVALID_HANDLE) return false;
      bool got = false;
      if(DatabaseRead(req))
      {
         DatabaseColumnDouble(req, 0, out);
         got = true;
      }
      DatabaseFinalize(req);
      return got;
   }
};

#endif // TOKIO_DATABASE_MQH
