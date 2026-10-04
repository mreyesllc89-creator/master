//+------------------------------------------------------------------+
//|                                                       Engine.mqh  |
//|   TokioQuant V3 - Orquestador central                              |
//|                                                                    |
//|   Cambios V3 (medidos sobre la telemetria real ago-oct 2026):      |
//|   - 51 cestas cortadas por stop: 50 habrian vuelto a breakeven     |
//|     con el precio M1 real (31 en <30 min). Las cestas ya NO se     |
//|     congelan en tendencia: siguen persiguiendo el precio.          |
//|   - Paso geometrico + martingala que se aplana: el grid puede      |
//|     seguir al precio 80+ USD sin que el lote explote.              |
//|   - Desarme: las posiciones profundas cobran su propio TP y ese    |
//|     dinero paga la peor posicion (baja exposicion sin realizar     |
//|     perdida neta).                                                 |
//|   - CloseAll transaccional: nunca registra una cesta que no se     |
//|     cerro (4.521 cestas fantasma el 01/10/2026).                   |
//|   - Resultado leido de los deals de las posiciones de la cesta     |
//|     (sin doble conteo), edad de cesta recuperada tras reinicio,    |
//|     guarda de permiso de trading, BD separada por cuenta.          |
//+------------------------------------------------------------------+
#ifndef TOKIO_ENGINE_MQH
#define TOKIO_ENGINE_MQH

#include <Trade\Trade.mqh>
#include "Utilities.mqh"
#include "MarketScanner.mqh"
#include "TrendDetector.mqh"
#include "RegimeEngine.mqh"
#include "SignalEngine.mqh"
#include "GridEngine.mqh"
#include "RiskManager.mqh"
#include "RecoveryEngine.mqh"
#include "BasketManager.mqh"
#include "PartialCloseEngine.mqh"
#include "HedgeEngine.mqh"
#include "TrailingEngine.mqh"
#include "TPManager.mqh"
#include "LearningEngine.mqh"
#include "CompoundEngine.mqh"
#include "DataRecorder.mqh"
#include "SessionEngine.mqh"
#include "CircuitBreaker.mqh"
#include "Database.mqh"
#include "Dashboard.mqh"
#include "Telegram.mqh"

class CEngine
{
private:
   //--- Configuracion e infraestructura ---
   SConfig  m_cfg;
   CTrade   m_trade;
   CTrade   m_lockTrade;      // posiciones del candado: magic + 1 (fuera del grid)

   //--- Modulos ---
   CMarketScanner      m_scanner;
   CTrendDetector      m_trend;
   CRegimeEngine       m_regime;
   CSignalEngine       m_signal;
   CGridEngine         m_grid;
   CRiskManager        m_risk;
   CRecoveryEngine     m_recovery;
   CBasketManager      m_basketMgr;
   CPartialCloseEngine m_partial;
   CHedgeEngine        m_hedge;
   CTrailingEngine     m_trailing;
   CTPManager          m_tp;
   CLearningEngine     m_learn;
   CCompoundEngine     m_compound;
   CDataRecorder       m_recorder;
   CCircuitBreaker     m_breaker;
   CSessionEngine      m_session;
   CDatabase           m_db;
   CDashboard          m_dash;
   CTelegram           m_tg;

   //--- Estado por tick ---
   SMarket  m_mkt;
   SScores  m_scr;
   SBasket  m_bkt;
   SRuntime m_rt;
   ENUM_REGIME m_curRegime;
   double   m_ddPct;

   //--- Estado de sesion ---
   double   m_peakEquity;
   double   m_basketPeak;
   double   m_harvested;
   int      m_cycles;
   double   m_optStepFactor, m_optMartFactor;
   double   m_effBaseLot;
   double   m_cmpGrowth;
   int      m_winStreak;      // cestas limpias ganadas seguidas (anti-martingala)
   bool     m_locked;         // candado puesto
   int      m_lockDir;        // +1 = cesta neta larga (candado vendido), -1 = cesta neta corta
   double   m_lockNet;        // neto de la cesta cuando se puso el ultimo candado
   double   m_lockExtreme;    // precio mas adverso visto con el candado puesto
   int      m_locks;          // candados puestos en esta cesta
   datetime m_noNewUntil;     // pausa de siembra tras un stop de catastrofe
   double   m_sinceStop;      // realizado desde el ultimo stop de cesta (financia el siguiente stop)
   int      m_flipDir;        // lado unico tras un stop: +1 compras, -1 ventas
   datetime m_flipUntil;
   double   m_closeDelta;     // exposicion neta de la cesta al pedir el cierre

   //--- P/L virtual por robot (solo display) ---
   double   m_netRealized;
   double   m_lastResetSeen;
   double   m_robotPeakEq;

   //--- V3: cesta en curso ---
   ulong    m_posIds[];       // POSITION_IDENTIFIER de TODAS las posiciones de la cesta
   double   m_bank;           // realizado dentro de la cesta (scalps + pagos)
   int      m_scalps, m_paydowns;
   int      m_paidBuy, m_paidSell;   // posiciones pagadas por lado: la profundidad REAL no baja
   bool     m_closePending;   // se pidio cerrar; aun no esta todo cerrado/contabilizado
   string   m_closeReason;
   double   m_closeEstimate;
   datetime m_lastCloseTry;
   int      m_finalizeTries;
   int      m_closeLevels;
   double   m_closeDurMin;

   //--- V3: permisos / eventos ---
   bool     m_tradeOK;
   datetime m_lastOpenErrLog;
   datetime m_lastScalp;

   //--- Timers ---
   datetime m_lastAdd, m_lastHarvest, m_lastSnapshot, m_basketOpen;
   datetime m_lastPartial, m_lastOptimize, m_lastTel;
   int      m_telCount;

   //--- P/L diario / semanal ---
   double   m_dayStartBal, m_weekStartBal;
   int      m_curDay, m_curWeek;

   //--- CSV ---
   int      m_csv;

   //================= Permiso de trading =======================//
   bool TradeAllowed(void)
   {
      if(MQLInfoInteger(MQL_TESTER)) return true;
      return TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) &&
             MQLInfoInteger(MQL_TRADE_ALLOWED) &&
             AccountInfoInteger(ACCOUNT_TRADE_EXPERT) &&
             AccountInfoInteger(ACCOUNT_TRADE_ALLOWED);
   }

   bool Mine(void)
   {
      return PositionGetString(POSITION_SYMBOL) == m_cfg.symbol &&
             (ulong)PositionGetInteger(POSITION_MAGIC) == m_cfg.magic;
   }
   bool LockMine(void)
   {
      return PositionGetString(POSITION_SYMBOL) == m_cfg.symbol &&
             (ulong)PositionGetInteger(POSITION_MAGIC) == m_cfg.magic + 1;
   }
   bool AnyMine(void) { return Mine() || LockMine(); }

   //================= CANDADO DE COBERTURA ======================//
   double LockFloating(void)
   {
      double s = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !LockMine()) continue;
         s += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      }
      return s;
   }

   // Abre la cobertura igual a la exposicion neta de la cesta (en trozos <= maxLotOrder).
   void DoLock(double net)
   {
      double delta = m_bkt.delta;                     // lotes compra - lotes venta
      double rest  = NormalizeDouble(MathAbs(delta), 2);
      if(rest < SymbolInfoDouble(m_cfg.symbol, SYMBOL_VOLUME_MIN)) return;
      double maxOrd = MathMax(m_cfg.maxLotOrder * m_cmpGrowth, SymbolInfoDouble(m_cfg.symbol, SYMBOL_VOLUME_MIN));
      int guard = 0;
      while(rest >= 0.01 && guard++ < 50)
      {
         double lot = NormalizeVolume(m_cfg.symbol, MathMin(rest, maxOrd), maxOrd);
         bool ok = (delta > 0) ? m_lockTrade.Sell(lot, m_cfg.symbol, m_mkt.bid, 0, 0, "TQ-Lock")
                               : m_lockTrade.Buy(lot, m_cfg.symbol, m_mkt.ask, 0, 0, "TQ-Lock");
         if(!ok || m_lockTrade.ResultRetcode() != TRADE_RETCODE_DONE) break;
         ulong deal = m_lockTrade.ResultDeal();
         if(deal > 0 && HistoryDealSelect(deal))
         {
            int n = ArraySize(m_posIds); ArrayResize(m_posIds, n + 1);
            m_posIds[n] = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
         }
         rest = NormalizeDouble(rest - lot, 2);
      }
      m_locked = true; m_lockDir = (delta > 0) ? 1 : -1;
      m_lockNet = net; m_lockExtreme = m_mkt.mid; m_locks++;
      m_learn.Event("lock", "neto " + DoubleToString(net, 2) + " delta " + DoubleToString(delta, 2));
   }

   void Unlock(void)
   {
      double got = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !LockMine()) continue;
         double pf = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         if(m_lockTrade.PositionClose(t) && m_lockTrade.ResultRetcode() == TRADE_RETCODE_DONE) got += pf;
      }
      m_bank += got;            // lo ganado por la cobertura cuenta para cerrar la cesta
      m_locked = false;
      m_learn.Event("unlock", "cobertura " + DoubleToString(got, 2));
   }

   // Pone/quita el candado. Devuelve true si la cesta esta bloqueada (no promediar).
   bool ManageLock(double balance)
   {
      if(m_cfg.lockPct <= 0) return false;
      double net = m_bkt.floating + m_bank + LockFloating();
      if(m_locked)
      {
         // extremo adverso: cesta larga sufre cuando baja; corta cuando sube
         if(m_lockDir > 0) m_lockExtreme = MathMin(m_lockExtreme, m_mkt.mid);
         else              m_lockExtreme = MathMax(m_lockExtreme, m_mkt.mid);
         double reb = (m_lockDir > 0) ? (m_mkt.mid - m_lockExtreme) : (m_lockExtreme - m_mkt.mid);
         if(m_mkt.atr > 0 && reb >= m_cfg.unlockATR * m_mkt.atr) Unlock();
         return m_locked;
      }
      if(m_bkt.total < m_cfg.lockMinLevels) return false;
      double thr = (m_locks == 0) ? -balance * m_cfg.lockPct / 100.0
                                  : m_lockNet - balance * m_cfg.relockStepPct / 100.0;
      if(net <= thr) DoLock(net);
      return m_locked;
   }

   //================= Helpers de posiciones =====================//
   bool Open(ENUM_ORDER_TYPE type, double lot, const string tag)
   {
      if(!m_tradeOK) return false;
      lot = m_compound.Quantize(lot, m_cfg.maxLotOrder * m_cmpGrowth);
      if(lot <= 0) return false;
      if(m_bkt.lotsTotal + lot > m_rt.exposureCap + 1e-9) return false;

      bool sent = (type == ORDER_TYPE_BUY)
                  ? m_trade.Buy(lot, m_cfg.symbol, m_mkt.ask, 0, 0, tag)
                  : m_trade.Sell(lot, m_cfg.symbol, m_mkt.bid, 0, 0, tag);
      uint rc = m_trade.ResultRetcode();
      bool ok = sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED ||
                         rc == TRADE_RETCODE_DONE_PARTIAL);
      if(!ok && TimeCurrent() - m_lastOpenErrLog >= 30)
      {
         Print("Open ", EnumToString(type), " fallo: ", rc, " ", m_trade.ResultRetcodeDescription());
         m_lastOpenErrLog = TimeCurrent();
      }
      return ok;
   }

   // Registra los identificadores de las posiciones vivas de la cesta.
   void TrackPositions(void)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !Mine()) continue;
         ulong pid = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
         bool known = false;
         for(int k = ArraySize(m_posIds) - 1; k >= 0; k--)
            if(m_posIds[k] == pid) { known = true; break; }
         if(!known)
         {
            int n = ArraySize(m_posIds);
            ArrayResize(m_posIds, n + 1);
            m_posIds[n] = pid;
         }
      }
   }

   bool IsBasketId(ulong pid)
   {
      for(int k = ArraySize(m_posIds) - 1; k >= 0; k--)
         if(m_posIds[k] == pid) return true;
      return false;
   }

   // Suma TODOS los deals (entrada y salida) de las posiciones de la cesta.
   // exitsOK = cada posicion tiene ya su deal de salida en el historial.
   double BasketRealized(bool &exitsOK)
   {
      exitsOK = false;
      int nIds = ArraySize(m_posIds);
      if(nIds == 0) { exitsOK = true; return 0.0; }
      datetime from = (m_basketOpen > 0 ? m_basketOpen : TimeCurrent() - 86400 * 7) - 600;
      if(!HistorySelect(from, TimeCurrent() + 60)) return 0.0;

      int exits[]; ArrayResize(exits, nIds); ArrayInitialize(exits, 0);
      double sum = 0.0;
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
      {
         ulong d = HistoryDealGetTicket(i);
         if(d == 0) continue;
         if(HistoryDealGetString(d, DEAL_SYMBOL) != m_cfg.symbol) continue;
         if((ulong)HistoryDealGetInteger(d, DEAL_MAGIC) != m_cfg.magic &&
            HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) continue;
         ulong pid = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
         int idx = -1;
         for(int k = 0; k < nIds; k++) if(m_posIds[k] == pid) { idx = k; break; }
         if(idx < 0) continue;
         sum += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) +
                HistoryDealGetDouble(d, DEAL_SWAP)   + HistoryDealGetDouble(d, DEAL_FEE);
         long entry = HistoryDealGetInteger(d, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY || entry == DEAL_ENTRY_INOUT)
            exits[idx]++;
      }
      exitsOK = true;
      for(int k = 0; k < nIds; k++) if(exits[k] == 0) { exitsOK = false; break; }
      return sum;
   }

   //================= Cierre total transaccional =================//
   // Pide el cierre. La cesta SOLO se contabiliza cuando no queda ninguna
   // posicion y el historial tiene todas las salidas (FinalizeClose).
   void CloseAll(const string reason)
   {
      if(!m_closePending)
      {
         m_closePending  = true;
         m_closeReason   = reason;
         m_closeEstimate = m_bkt.floating + m_bank;
         m_closeLevels   = m_bkt.total;
         m_closeDelta    = m_bkt.delta;
         m_closeDurMin   = (m_basketOpen > 0) ? (TimeCurrent() - m_basketOpen) / 60.0 : 0.0;
         m_finalizeTries = 0;
      }
      TryCloseRemaining();
   }

   void TryCloseRemaining(void)
   {
      if(!m_tradeOK) return;
      m_lastCloseTry = TimeCurrent();
      int failed = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !AnyMine()) continue;
         CTrade *tr = LockMine() ? GetPointer(m_lockTrade) : GetPointer(m_trade);
         if(!tr.PositionClose(t) || tr.ResultRetcode() != TRADE_RETCODE_DONE)
            failed++;
      }
      if(failed > 0)
      {
         Print("CIERRE INCOMPLETO [", m_closeReason, "] quedan ", failed,
               " posiciones: ", m_trade.ResultRetcodeDescription(), " -> reintento");
         m_learn.Event("close_failed", m_closeReason + " quedan " + IntegerToString(failed) +
                       " rc=" + IntegerToString((int)m_trade.ResultRetcode()));
      }
   }

   int CountMine(void)
   {
      int n = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t != 0 && PositionSelectByTicket(t) && AnyMine()) n++;
      }
      return n;
   }

   // Devuelve true si la cesta quedo contabilizada y el estado reiniciado.
   bool FinalizeClose(void)
   {
      if(CountMine() > 0) return false;
      bool exitsOK = false;
      double realized = BasketRealized(exitsOK);
      m_finalizeTries++;
      if(!exitsOK && m_finalizeTries < 20) return false;   // el historial aun no tiene las salidas
      bool estimated = !exitsOK;
      if(estimated && realized == 0.0) realized = m_closeEstimate;

      string reason = m_closeReason;
      if(reason == "deep_stop" && m_cfg.stopCooldownH > 0)
         m_noNewUntil = TimeCurrent() + (datetime)(m_cfg.stopCooldownH * 3600);
      if(reason == "time_cut" && m_cfg.timeCutPauseMin > 0)
         m_noNewUntil = TimeCurrent() + (datetime)(m_cfg.timeCutPauseMin * 60);
      if(reason == "basket_stop_hard" && m_cfg.stopPauseMin > 0)
         m_noNewUntil = TimeCurrent() + (datetime)(m_cfg.stopPauseMin * 60);
      // Giro tras el stop: la cesta neta vendida murio por una subida -> un rato solo compras (y al reves).
      if((reason == "basket_stop_hard" || reason == "time_cut") && m_cfg.stopFlipH > 0 && m_closeDelta != 0.0)
      {
         m_flipDir   = (m_closeDelta < 0.0) ? 1 : -1;
         m_flipUntil = TimeCurrent() + (datetime)(m_cfg.stopFlipH * 3600);
      }
      if(reason == "basket_stop_hard") m_sinceStop = 0.0; else m_sinceStop += realized;
      int    levels = m_closeLevels;
      double durMin = m_closeDurMin;

      if(realized > 0) m_harvested += realized;
      m_netRealized += realized;
      // Anti-martingala: solo las victorias rapidas (pocas posiciones) suben la racha;
      // una cesta profunda o perdedora la devuelve a cero (el lote vuelve al base).
      if(realized > 0 && (m_cfg.cleanWinLevels <= 0 || levels <= m_cfg.cleanWinLevels)) m_winStreak++;
      else m_winStreak = 0;
      double newBal = AccountInfoDouble(ACCOUNT_BALANCE);

      Print("COSECHA [", reason, "] $", DoubleToString(realized, 2),
            " | ", levels, " pos | ", DoubleToString(durMin, 1), "m | scalps ", m_scalps,
            " pagos ", m_paydowns, " | acum $", DoubleToString(m_harvested, 2),
            (estimated ? " (ESTIMADO)" : ""));

      m_recorder.OnBasketClose(m_mkt, m_scr, m_curRegime, realized, reason, newBal,
                               m_effBaseLot, m_cmpGrowth, m_bank, m_scalps, m_paydowns,
                               ArraySize(m_posIds), estimated);
      m_learn.RecordBasket(m_mkt, m_curRegime, m_scr.confidence, realized,
                           m_ddPct, m_rt.recoveryLevel, durMin, levels, reason, newBal);

      if(m_cfg.logCSV && m_csv != INVALID_HANDLE)
         FileWrite(m_csv, TimeToString(TimeCurrent()), DoubleToString(realized, 2),
                   levels, DoubleToString(durMin, 1), reason, DoubleToString(newBal, 2));

      if(realized > 0)
      {
         double aboveInit = newBal - m_learn.initialBankroll;
         double pct = (m_learn.initialBankroll > 0) ? aboveInit / m_learn.initialBankroll * 100.0 : 0.0;
         m_tg.Send("<b>" + m_cfg.eaName + "</b> +$" + DoubleToString(realized, 2) + "\n" +
                   "Regimen: " + m_regime.Name(m_curRegime) + "\n" +
                   "Balance: <b>" + DoubleToString(newBal, 2) + "</b>\n" +
                   "Sobre inicial: " + DoubleToString(aboveInit, 2) + " (" + DoubleToString(pct, 1) + "%)\n" +
                   IntegerToString(levels) + " pos | " + reason + " | scalps " + IntegerToString(m_scalps) + "\n" +
                   "Ciclos: " + IntegerToString(m_cycles) + " | Acum $" + DoubleToString(m_harvested, 2));
      }

      ResetBasketState();
      m_lastHarvest = TimeCurrent();
      m_lastAdd     = TimeCurrent();
      return true;
   }

   void ResetBasketState(void)
   {
      ArrayResize(m_posIds, 0);
      m_bank = 0.0; m_scalps = 0; m_paydowns = 0; m_paidBuy = 0; m_paidSell = 0;
      m_basketPeak = 0; m_basketOpen = 0;
      m_closePending = false; m_closeReason = ""; m_closeEstimate = 0;
      m_finalizeTries = 0;
      m_locked = false; m_lockDir = 0; m_lockNet = 0; m_lockExtreme = 0; m_locks = 0;
   }

   //================= Grid: paso y lote por nivel ==============//
   double LevelStep(double step, int sameSide, bool adverse)
   {
      double s = step;
      if(m_cfg.stepGrowth > 0.0 && sameSide > 1)
         s *= MathPow(1.0 + m_cfg.stepGrowth, sameSide - 1);
      if(adverse && m_cfg.adverseStepMult > 1.0) s *= m_cfg.adverseStepMult;
      return s;
   }

   double LevelLot(double martMult, int sameSide, double lotScale)
   {
      int n = sameSide;
      if(m_cfg.martMaxLevels > 0 && n > m_cfg.martMaxLevels) n = m_cfg.martMaxLevels;
      return m_effBaseLot * MathPow(martMult, n) * lotScale;
   }

   // El precio ya no esta haciendo nuevo extremo adverso en la vela M1 actual.
   bool M1Confirms(bool buySide, double stepN)
   {
      if(!m_cfg.addConfirmM1) return true;
      if(buySide)
      {
         double lo = iLow(m_cfg.symbol, PERIOD_M1, 0);
         return (lo <= 0) || (m_mkt.bid - lo >= 0.20 * stepN);
      }
      double hi = iHigh(m_cfg.symbol, PERIOD_M1, 0);
      return (hi <= 0) || (hi - m_mkt.ask >= 0.20 * stepN);
   }

   //================= Lado permitido para sembrar ==============//
   // 0 = ambos, +1 = solo compras, -1 = solo ventas. Las posiciones ya abiertas se siguen gestionando.
   int SideAllowed(void)
   {
      if(m_cfg.stopFlipH > 0 && m_flipDir != 0 && TimeCurrent() < m_flipUntil) return m_flipDir;
      if(m_cfg.sideMode == 1) return 1;
      if(m_cfg.sideMode == 2) return -1;
      if(m_cfg.sideMode == 3 || m_cfg.sideMode == 4)
      {
         double past = iClose(m_cfg.symbol, PERIOD_H1, MathMax(m_cfg.sideLookbackH, 1));
         if(past <= 0.0) return 0;
         int d = (m_mkt.bid > past) ? 1 : -1;
         return (m_cfg.sideMode == 3) ? d : -d;
      }
      return 0;
   }

   //================= Logica de ENTRADAS ========================//
   void ManageTrend(int dir, double step)
   {
      int sdT = SideAllowed();
      if(sdT != 0 && sdT != ((dir > 0) ? 1 : -1)) return;
      if(m_bkt.total == 0)
      {
         if(VolExpansionBlocksNew()) return;
         SeedSingle((dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
         return;
      }
      ENUM_SIDE side = m_signal.PullbackEntry(m_mkt, dir);
      int sameSide = (dir > 0) ? m_bkt.buys : m_bkt.sells;
      if(sameSide >= m_rt.maxLevels) return;
      if(dir > 0 && side == SIDE_BUY)
      {
         if(m_mkt.bid <= LowestOpen(POSITION_TYPE_BUY) - step)
            { if(Open(ORDER_TYPE_BUY, m_effBaseLot * m_rt.lotMult, "TQ-TrendAdd")) m_lastAdd = TimeCurrent(); }
      }
      else if(dir < 0 && side == SIDE_SELL)
      {
         if(m_mkt.ask >= HighestOpen(POSITION_TYPE_SELL) + step)
            { if(Open(ORDER_TYPE_SELL, m_effBaseLot * m_rt.lotMult, "TQ-TrendAdd")) m_lastAdd = TimeCurrent(); }
      }
   }

   // Siembra de una cesta nueva en modo grid (rango).
   void SeedGrid(double lotScale)
   {
      bool blockSell = (m_scr.trend >= m_cfg.trendBlock && m_scr.trendDir > 0);
      bool blockBuy  = (m_scr.trend >= m_cfg.trendBlock && m_scr.trendDir < 0);
      if(VolExpansionBlocksNew()) return;
      int sd = SideAllowed();
      if(sd > 0) blockSell = true;
      if(sd < 0) blockBuy  = true;
      if(blockBuy && blockSell) return;
      m_basketPeak = 0;
      m_basketOpen = TimeCurrent();
      m_cycles++;
      if(!blockBuy)  Open(ORDER_TYPE_BUY,  m_effBaseLot * lotScale, "TQ-Seed");
      if(!blockSell) Open(ORDER_TYPE_SELL, m_effBaseLot * lotScale, "TQ-Seed");
      m_lastAdd = TimeCurrent();
   }

   // Promedia la cesta abierta persiguiendo el precio (ambos lados).
   void GridAdds(double step, double martMult, double lotScale)
   {
      double ask = m_mkt.ask, bid = m_mkt.bid;
      double highestBuy = 0, lowestBuy = DBL_MAX, highestSell = 0, lowestSell = DBL_MAX;
      GetExtremes(highestBuy, lowestBuy, highestSell, lowestSell);

      if(m_cfg.maxTotalLevels > 0 && m_bkt.total >= m_cfg.maxTotalLevels) return;

      // MODO SUPERVIVENCIA (backtest mensual 2026, 100k): en marzo una cesta de
      // 5 dias y 30 posiciones llevo la cuenta al stop-out. Con la cesta muy
      // hundida se sigue persiguiendo, pero el paso se ensancha y el lote deja
      // de crecer: la exposicion sube mucho mas despacio. No cierra nada.
      bool survival = m_cfg.survivalDDPct > 0.0 &&
                      -(m_bkt.floating + m_bank) >= AccountInfoDouble(ACCOUNT_BALANCE) * m_cfg.survivalDDPct / 100.0;
      if(survival)
      {
         step    *= MathMax(m_cfg.survivalStepMult, 1.0);
         martMult = 1.0;
      }

      bool strong = (m_scr.trend >= m_cfg.trendBlock);
      bool advBuy  = strong && m_scr.trendDir < 0;   // tendencia fuerte bajista contra las compras
      bool advSell = strong && m_scr.trendDir > 0;

      bool trendBlockBuy = false, trendBlockSell = false;
      if(m_cfg.blockAddsAdverseAdx > 0.0 && m_mkt.adx >= m_cfg.blockAddsAdverseAdx)
      {
         if(m_mkt.minusDI > m_mkt.plusDI) trendBlockBuy  = true;
         if(m_mkt.plusDI  > m_mkt.minusDI) trendBlockSell = true;
      }

      if(!trendBlockBuy && m_rt.allowMart && m_bkt.buys > 0 && m_bkt.buys < m_rt.maxLevels)
      {
         int dB = m_bkt.buys + m_paidBuy;   // profundidad real (las pagadas cuentan)
         double sN = LevelStep(step, dB, advBuy);
         if(lowestBuy - ask >= sN && M1Confirms(true, sN))
            if(Open(ORDER_TYPE_BUY, LevelLot(martMult, dB, lotScale), "TQ-GridBuy"))
               { m_lastAdd = TimeCurrent(); return; }
      }
      if(!trendBlockSell && m_rt.allowMart && m_bkt.sells > 0 && m_bkt.sells < m_rt.maxLevels)
      {
         int dS = m_bkt.sells + m_paidSell;
         double sN = LevelStep(step, dS, advSell);
         if(bid - highestSell >= sN && M1Confirms(false, sN))
            if(Open(ORDER_TYPE_SELL, LevelLot(martMult, dS, lotScale), "TQ-GridSell"))
               { m_lastAdd = TimeCurrent(); return; }
      }
      // Reponer el lado faltante (mantener bidireccional)
      int sd = SideAllowed();
      if(m_bkt.sells == 0 && m_bkt.buys > 0 && (lowestBuy - bid) >= step * 0.5 && !advSell && sd <= 0)
         { if(Open(ORDER_TYPE_SELL, m_effBaseLot * lotScale, "TQ-Refill")) m_lastAdd = TimeCurrent(); }
      else if(m_bkt.buys == 0 && m_bkt.sells > 0 && (ask - highestSell) >= step * 0.5 && !advBuy && sd >= 0)
         { if(Open(ORDER_TYPE_BUY, m_effBaseLot * lotScale, "TQ-Refill")) m_lastAdd = TimeCurrent(); }
   }

   //================= V3: desarme de cestas profundas ===========//
   // 1) La posicion mas profunda de cada lado (nivel >= scalpFromLevel) se
   //    cierra sola al rebotar una fraccion del paso: cobra la oscilacion.
   //    El grid la vuelve a abrir si el precio regresa a ese nivel.
   // 2) Lo cobrado (m_bank) paga la PEOR posicion cuando alcanza para
   //    cerrarla con colchon: la cesta se desarma sin perdida neta.
   void ScalpAndPayDown(double step)
   {
      if(m_cfg.scalpFromLevel <= 0) return;
      if(TimeCurrent() - m_lastScalp < MathMax(m_cfg.minSecs, 1)) return;

      for(int pass = 0; pass < 2; pass++)
      {
         long want = (pass == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
         int  cnt  = (pass == 0) ? m_bkt.buys : m_bkt.sells;
         if(cnt < m_cfg.scalpFromLevel) continue;

         ulong newest = 0; long newestT = 0; double op = 0, pf = 0;
         for(int i = PositionsTotal() - 1; i >= 0; i--)
         {
            ulong t = PositionGetTicket(i);
            if(t == 0 || !PositionSelectByTicket(t) || !Mine()) continue;
            if(PositionGetInteger(POSITION_TYPE) != want) continue;
            long pt = PositionGetInteger(POSITION_TIME_MSC);
            if(newest == 0 || pt > newestT)
            {
               newest = t; newestT = pt;
               op = PositionGetDouble(POSITION_PRICE_OPEN);
               pf = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
            }
         }
         if(newest == 0 || pf <= 0) continue;
         double gain = (want == POSITION_TYPE_BUY) ? (m_mkt.bid - op) : (op - m_mkt.ask);
         if(gain >= m_cfg.scalpStepFrac * step)
         {
            if(m_trade.PositionClose(newest) && m_trade.ResultRetcode() == TRADE_RETCODE_DONE)
            {
               m_bank += pf; m_scalps++; m_lastScalp = TimeCurrent();
               m_recorder.MarkPartial();
               return;
            }
         }
      }

      if(m_cfg.payDown && m_bank > 0.0 && m_bkt.total >= 2 && m_bkt.worstTicket != 0 &&
         m_bkt.worstProfit < 0.0 && m_bank + m_bkt.worstProfit >= m_cfg.payDownBuffer)
      {
         bool worstIsBuy = PositionSelectByTicket(m_bkt.worstTicket) &&
                           PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
         if(m_trade.PositionClose(m_bkt.worstTicket) && m_trade.ResultRetcode() == TRADE_RETCODE_DONE)
         {
            if(worstIsBuy) m_paidBuy++; else m_paidSell++;
            m_bank += m_bkt.worstProfit; m_paydowns++; m_lastScalp = TimeCurrent();
            m_recorder.MarkPartial();
         }
      }
   }

   bool VolExpansionBlocksNew()
   {
      if(m_cfg.maxAtrRatioNew <= 0) return false;
      if(m_mkt.atrRatio <= 0)       return false;
      return (m_mkt.atrRatio > m_cfg.maxAtrRatioNew);
   }

   static bool InList(const string csv, int v)
   {
      if(StringLen(csv) == 0) return false;
      string parts[]; int n = StringSplit(csv, ',', parts);
      for(int i = 0; i < n; i++) { string p = parts[i]; StringTrimLeft(p); StringTrimRight(p); if(StringLen(p) > 0 && (int)StringToInteger(p) == v) return true; }
      return false;
   }

   bool MaskBlocksNew(void)
   {
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      return InList(m_cfg.blockHours, dt.hour) || InList(m_cfg.blockDays, dt.day_of_week);
   }

   bool HourBlocksNew(void)
   {
      if(m_cfg.noNewFromHour < 0 || m_cfg.noNewToHour < 0) return false;
      MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
      int h = dt.hour, a = m_cfg.noNewFromHour, b = m_cfg.noNewToHour;
      return (a <= b) ? (h >= a && h <= b) : (h >= a || h <= b);
   }

   void SeedSingle(ENUM_ORDER_TYPE type)
   {
      m_basketPeak = 0;
      m_basketOpen = TimeCurrent();
      m_cycles++;
      Open(type, m_effBaseLot * m_rt.lotMult, "TQ-TrendSeed");
      m_lastAdd = TimeCurrent();
   }

   double LowestOpen(long type)
   {
      double lo = DBL_MAX;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !Mine()) continue;
         if(PositionGetInteger(POSITION_TYPE) != type) continue;
         double op = PositionGetDouble(POSITION_PRICE_OPEN);
         if(op < lo) lo = op;
      }
      return (lo == DBL_MAX) ? m_mkt.bid : lo;
   }

   double HighestOpen(long type)
   {
      double hi = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !Mine()) continue;
         if(PositionGetInteger(POSITION_TYPE) != type) continue;
         double op = PositionGetDouble(POSITION_PRICE_OPEN);
         if(op > hi) hi = op;
      }
      return (hi == 0) ? m_mkt.ask : hi;
   }

   void GetExtremes(double &hiBuy, double &loBuy, double &hiSell, double &loSell)
   {
      hiBuy = 0; loBuy = DBL_MAX; hiSell = 0; loSell = DBL_MAX;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong t = PositionGetTicket(i);
         if(t == 0 || !PositionSelectByTicket(t) || !Mine()) continue;
         double op = PositionGetDouble(POSITION_PRICE_OPEN);
         if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
            { if(op > hiBuy) hiBuy = op; if(op < loBuy) loBuy = op; }
         else
            { if(op > hiSell) hiSell = op; if(op < loSell) loSell = op; }
      }
      if(loBuy  == DBL_MAX) loBuy  = m_mkt.bid;
      if(loSell == DBL_MAX) loSell = m_mkt.ask;
   }

   void UpdatePnLAnchors(double balance)
   {
      int day  = (int)(TimeCurrent() / 86400);
      int week = (int)(TimeCurrent() / 604800);
      if(day  != m_curDay)  { m_curDay  = day;  m_dayStartBal  = balance; }
      if(week != m_curWeek) { m_curWeek = week; m_weekStartBal = balance; }
   }

   //================= RESET EN CALIENTE ==========================//
   void CheckHotReset(double balance)
   {
      if(!m_cfg.useDB || !m_db.IsOpen()) return;
      double req = 0.0;
      if(!m_db.QueryDouble("SELECT dval FROM meta WHERE key='reset_request';", req)) return;
      if(req <= m_lastResetSeen) return;
      m_lastResetSeen = req;
      m_db.ExecQuiet("DELETE FROM equity;");
      m_db.ExecQuiet("DELETE FROM baskets;");
      m_db.ExecQuiet("DELETE FROM trades;");
      m_db.ExecQuiet("DELETE FROM telemetry;");
      m_db.ExecQuiet("DELETE FROM account;");
      m_netRealized  = 0.0;
      m_harvested    = 0.0;
      m_cycles       = 0;
      m_peakEquity   = AccountInfoDouble(ACCOUNT_EQUITY);
      m_robotPeakEq  = balance;
      m_dayStartBal  = balance;
      m_weekStartBal = balance;
      m_learn.Reseed(balance);
      m_db.ExecQuiet(StringFormat("INSERT OR REPLACE INTO meta(key,dval) VALUES('reset_done',%.0f);", req));
      m_learn.Event("hot_reset", "bankroll " + DoubleToString(balance, 2));
      Print("### RESET EN CALIENTE aplicado | nuevo bankroll: ", DoubleToString(balance, 2), " ###");
   }

   double RobotBalance(void) { return m_learn.initialBankroll + m_netRealized; }
   double RobotEquity(void)  { return RobotBalance() + m_bank + m_bkt.floating + (m_locked ? LockFloating() : 0.0); }
   double RobotDDpct(void)
   {
      double e = RobotEquity();
      if(e > m_robotPeakEq) m_robotPeakEq = e;
      return (m_robotPeakEq > 0.0) ? (m_robotPeakEq - e) / m_robotPeakEq * 100.0 : 0.0;
   }

   void WriteTelemetry(double equity, double balance)
   {
      STelemetry t;
      t.ts         = (long)TimeCurrent();
      t.regime     = (int)m_curRegime;
      t.regimeName = m_regime.Name(m_curRegime);
      t.trend      = m_scr.trend;      t.trendDir  = m_scr.trendDir;
      t.momentum   = m_scr.momentum;   t.volatility= m_scr.volatility;
      t.liquidity  = m_scr.liquidity;  t.risk      = m_scr.risk;
      t.recovery   = m_scr.recovery;   t.quality   = m_scr.quality;
      t.confidence = m_scr.confidence;
      t.expScore   = m_risk.exposureScore; t.marginScore = m_risk.marginScore;
      t.floatScore = m_risk.floatingScore; t.volScore    = m_risk.volScore;
      t.corrScore  = m_risk.corrScore;     t.ddScore     = m_risk.ddScore;
      t.adx        = m_mkt.adx;   t.atr = m_mkt.atr;   t.atrRatio = m_mkt.atrRatio;
      t.spread     = m_mkt.spread;t.rsi = m_mkt.rsi;
      // ddpct = DD REAL de la cuenta (equity vs pico): es lo que se vigila en el panel
      t.ddpct      = m_ddPct;
      t.recLevel   = m_rt.recoveryLevel;
      t.equity     = RobotEquity(); t.balance = RobotBalance(); t.floating = m_bkt.floating + m_bank;
      t.buys       = m_bkt.buys;  t.sells   = m_bkt.sells;
      t.lots       = m_bkt.lotsTotal; t.delta = m_bkt.delta;
      t.step       = m_grid.Step(m_mkt, m_rt.stepMult);
      t.cmpGrowth  = m_cmpGrowth;
      t.cmpLot     = m_effBaseLot;
      t.cmpAnchor  = m_compound.Anchor();
      t.cmpNext    = m_compound.NextStepAt();
      m_learn.WriteTelemetry(t);
   }

   // Una BD por cuenta: si la BD ya pertenece a otro login, usa <nombre>_<login>.
   void OpenDatabaseForAccount(void)
   {
      m_db.Open(m_cfg);
      if(!m_db.IsOpen()) return;
      long login = AccountInfoInteger(ACCOUNT_LOGIN);
      double stored = 0;
      m_db.Exec("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, dval REAL);");
      if(m_db.QueryDouble("SELECT dval FROM meta WHERE key='login';", stored) &&
         (long)stored != login && login > 0)
      {
         m_db.Close();
         string base = m_cfg.dbName;
         int p = StringFind(base, ".sqlite");
         if(p >= 0) base = StringSubstr(base, 0, p);
         m_cfg.dbName = base + "_" + IntegerToString(login) + ".sqlite";
         Print("BD de otra cuenta (", (long)stored, ") -> uso ", m_cfg.dbName);
         m_db.Open(m_cfg);
         if(!m_db.IsOpen()) return;
         m_db.Exec("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, dval REAL);");
      }
      m_db.Exec(StringFormat("INSERT OR REPLACE INTO meta(key,dval) VALUES('login',%I64d);", login));
      m_db.Exec(StringFormat("INSERT OR REPLACE INTO meta(key,dval) VALUES('money_scale',%.0f);", m_cfg.moneyScale));
   }

public:
   CEngine(void) : m_curRegime(REGIME_RANGE), m_ddPct(0), m_peakEquity(0),
      m_basketPeak(0), m_harvested(0), m_cycles(0),
      m_optStepFactor(1.0), m_optMartFactor(1.0),
      m_effBaseLot(0.01), m_cmpGrowth(1.0), m_winStreak(0),
      m_locked(false), m_lockDir(0), m_lockNet(0), m_lockExtreme(0), m_locks(0), m_noNewUntil(0), m_sinceStop(0), m_flipDir(0), m_flipUntil(0), m_closeDelta(0),
      m_netRealized(0.0), m_lastResetSeen(0.0), m_robotPeakEq(0.0),
      m_bank(0), m_scalps(0), m_paydowns(0), m_paidBuy(0), m_paidSell(0), m_closePending(false), m_closeReason(""),
      m_closeEstimate(0), m_lastCloseTry(0), m_finalizeTries(0), m_closeLevels(0), m_closeDurMin(0),
      m_tradeOK(true), m_lastOpenErrLog(0), m_lastScalp(0),
      m_lastAdd(0), m_lastHarvest(0), m_lastSnapshot(0), m_basketOpen(0),
      m_lastPartial(0), m_lastOptimize(0), m_lastTel(0), m_telCount(0),
      m_dayStartBal(0), m_weekStartBal(0), m_curDay(0), m_curWeek(0),
      m_csv(INVALID_HANDLE) {}

   //================= INICIALIZACION ============================//
   bool Init(const SConfig &cfg)
   {
      m_cfg = cfg;
      if(!SymbolSelect(m_cfg.symbol, true))
         { Print("Symbol invalido: ", m_cfg.symbol); return false; }

      // Cuenta cent (USC): 0,01 lote cent gana en USC el MISMO numero que 0,01 lote
      // estandar en USD (1 USC por 1 USD de movimiento del oro). Por eso los importes
      // del .set valen 1:1 y NO se escalan. InpMoneyScale queda solo como ajuste manual.
      if(m_cfg.moneyScale <= 0) m_cfg.moneyScale = 1.0;
      double k = m_cfg.moneyScale;
      m_cfg.baseTP *= k; m_cfg.tpMinUSD *= k; m_cfg.trailActUSD *= k; m_cfg.trailStepUSD *= k;
      m_cfg.bePad *= k; m_cfg.basketStopMoney *= k; m_cfg.payDownBuffer *= k; m_cfg.deepTP *= k;
      if(m_cfg.compoundAnchor > 0) m_cfg.compoundAnchor *= k;

      m_trade.SetExpertMagicNumber(m_cfg.magic);
      m_trade.SetDeviationInPoints(m_cfg.slippage);
      m_trade.SetTypeFillingBySymbol(m_cfg.symbol);
      m_trade.SetAsyncMode(false);
      m_trade.LogLevel(LOG_LEVEL_ERRORS);
      m_lockTrade.SetExpertMagicNumber(m_cfg.magic + 1);
      m_lockTrade.SetDeviationInPoints(m_cfg.slippage);
      m_lockTrade.SetTypeFillingBySymbol(m_cfg.symbol);
      m_lockTrade.SetAsyncMode(false);
      m_lockTrade.LogLevel(LOG_LEVEL_ERRORS);

      if(!m_scanner.Init(m_cfg)) return false;
      m_trend.Init(m_cfg);
      m_regime.Init(m_cfg);
      m_signal.Init(m_cfg);
      m_grid.Init(m_cfg);
      m_risk.Init(m_cfg);
      m_recovery.Init(m_cfg);
      m_basketMgr.Init(m_cfg);
      m_partial.Init(m_cfg);
      m_hedge.Init(m_cfg);
      m_trailing.Init(m_cfg);
      m_tp.Init(m_cfg);
      m_session.Init(m_cfg);
      m_dash.Init(m_cfg);
      m_tg.Init(m_cfg);

      double bal = AccountInfoDouble(ACCOUNT_BALANCE);
      m_peakEquity   = AccountInfoDouble(ACCOUNT_EQUITY);
      m_dayStartBal  = bal;
      m_weekStartBal = bal;
      m_curDay  = (int)(TimeCurrent() / 86400);
      m_curWeek = (int)(TimeCurrent() / 604800);

      OpenDatabaseForAccount();
      m_learn.Init(m_db, m_cfg, bal);

      // Balance virtual: solo cestas reales (las fantasma duraban 0 min).
      double _sp = 0.0;
      if(m_db.QueryDouble("SELECT COALESCE(SUM(profit),0) FROM baskets WHERE dur_min>0.05 OR reason NOT LIKE 'breaker%';", _sp))
         m_netRealized = _sp;
      m_robotPeakEq = m_learn.initialBankroll + m_netRealized;
      m_db.QueryDouble("SELECT dval FROM meta WHERE key='reset_request';", m_lastResetSeen);
      double _mig = 0.0;
      if(!m_db.QueryDouble("SELECT dval FROM meta WHERE key='virtual_pl_v1';", _mig))
         m_db.Exec("INSERT OR REPLACE INTO meta(key,dval) VALUES('virtual_pl_v1',1);");

      m_compound.Init(m_db, m_cfg, bal);
      m_recorder.Init(m_db, m_cfg);
      m_breaker.Init(m_cfg);
      m_effBaseLot = m_compound.Recompute(bal, 0.0);
      m_cmpGrowth  = m_compound.Growth();

      // Cesta viva tras un reinicio: recupera edad e identificadores.
      m_basketMgr.Update(m_bkt, m_mkt);
      if(m_bkt.total > 0) { m_basketOpen = m_bkt.oldestTime; TrackPositions(); }
      if(LockFloating() != 0.0 || CountMine() > m_bkt.total) { m_locked = true; m_lockDir = (m_bkt.delta > 0) ? 1 : -1; m_lockExtreme = m_mkt.mid; m_locks = 1; }

      if(m_cfg.logCSV)
      {
         string fname = m_cfg.eaName + "_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + "_" +
                        TimeToString(TimeCurrent(), TIME_DATE) + ".csv";
         StringReplace(fname, ".", "-");
         StringReplace(fname, "-csv", ".csv");
         if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION) || MQLInfoInteger(MQL_VISUAL_MODE))
            StringReplace(fname, ".csv", "_TESTER.csv");
         m_csv = FileOpen(fname, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON, ',');
         if(m_csv != INVALID_HANDLE)
         {
            if(FileSize(m_csv) == 0)
               FileWrite(m_csv, "timestamp", "profit", "levels", "dur_min", "reason", "balance");
            FileSeek(m_csv, 0, SEEK_END);
         }
      }

      m_tradeOK = TradeAllowed();
      m_learn.Event("init", m_cfg.eaName + " " + m_cfg.symbol + " tf=" + EnumToString(m_cfg.tf) +
                    " cesta_viva=" + IntegerToString(m_bkt.total) +
                    " trading=" + (m_tradeOK ? "ON" : "OFF"));
      Print("=== ", m_cfg.eaName, " ON | ", m_cfg.symbol, " | Balance ", bal,
            " | Bankroll inicial ", m_learn.initialBankroll, " | BD ", m_cfg.dbName,
            " | escala moneda x", DoubleToString(m_cfg.moneyScale, 0), " ===");
      return true;
   }

   void Deinit(const int reason = 0)
   {
      m_learn.Event("deinit", "reason=" + IntegerToString(reason) + " cesta=" + IntegerToString(m_bkt.total));
      m_scanner.Deinit();
      m_db.Close();
      if(m_csv != INVALID_HANDLE) FileClose(m_csv);
      Comment("");
   }

   //================= TICK PRINCIPAL ============================//
   void OnTick(void)
   {
      double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      if(equity > m_peakEquity) m_peakEquity = equity;
      m_ddPct = (m_peakEquity > 0) ? (m_peakEquity - equity) / m_peakEquity * 100.0 : 0.0;
      UpdatePnLAnchors(balance);

      // 0) Permiso de trading: sin el, NADA de OrderSend (antes: 37k rechazos/dia).
      bool ok = TradeAllowed();
      if(ok != m_tradeOK)
      {
         m_learn.Event(ok ? "trade_on" : "trade_off", "");
         Print(ok ? "Trading automatico HABILITADO" : "Trading automatico DESHABILITADO: solo telemetria");
         m_tradeOK = ok;
      }

      // 1) Sensor de mercado
      if(!m_scanner.Update(m_mkt)) return;

      // 2) Radiografia del basket
      m_basketMgr.Update(m_bkt, m_mkt);
      if(m_bkt.total > 0)
      {
         if(m_basketOpen == 0) m_basketOpen = m_bkt.oldestTime;
         TrackPositions();
      }

      // 2b) Caja negra
      if(m_bkt.total > 0 && !m_recorder.IsActive() && !m_closePending)
         m_recorder.OnBasketOpen(m_mkt, m_scr, m_curRegime, balance);
      if(m_bkt.total > 0)
         m_recorder.OnTick(m_mkt, m_bkt, m_rt.recoveryLevel);

      // 2c) Cierre pendiente: no se opera nada hasta contabilizarlo.
      if(m_closePending)
      {
         if(m_bkt.total > 0)
         {
            if(TimeCurrent() - m_lastCloseTry >= 5) TryCloseRemaining();
         }
         else FinalizeClose();
         DrawDash(balance, equity);
         return;
      }
      // Posiciones cerradas desde fuera (manual/SL/stop-out): contabilizar.
      if(m_bkt.total == 0 && ArraySize(m_posIds) > 0)
      {
         m_closePending = true; m_closeReason = "external_close";
         m_closeEstimate = 0; m_closeLevels = ArraySize(m_posIds);
         m_closeDurMin = (m_basketOpen > 0) ? (TimeCurrent() - m_basketOpen) / 60.0 : 0.0;
         FinalizeClose();
         DrawDash(balance, equity);
         return;
      }

      // 3-7) Cerebro
      m_trend.Compute(m_mkt, m_scr.trend, m_scr.trendDir);
      m_curRegime = m_regime.Classify(m_mkt, m_scr.trend, m_scr.trendDir, m_ddPct);
      m_risk.Compute(m_scr, m_mkt, m_bkt, m_ddPct, balance);
      m_recovery.Apply(m_rt, m_ddPct);
      m_rt.exposureCap *= m_cmpGrowth;
      m_signal.ComputeScores(m_scr, m_mkt, m_curRegime, m_ddPct);

      if((TimeCurrent() - m_lastOptimize) >= 300)
      {
         m_optStepFactor = m_learn.OptimizeStepMult(m_curRegime);
         m_optMartFactor = m_learn.OptimizeMartMult(m_curRegime);
         m_lastOptimize  = TimeCurrent();
      }

      if(m_bkt.total == 0)
      {
         m_effBaseLot = m_compound.Recompute(balance, m_ddPct);
         m_cmpGrowth  = m_compound.Growth();
         if(m_cfg.winBoostStep > 0.0)
            m_effBaseLot *= MathMin(MathMax(m_cfg.winBoostMax, 1.0), 1.0 + m_cfg.winBoostStep * m_winStreak);
      }

      // 9) Compuertas: allowNew = sembrar cestas nuevas; allowAdd = promediar la abierta.
      m_rt.allowNew = m_risk.AllowNew(m_scr.risk, m_curRegime, m_mkt);
      double riskLotScale = m_risk.LotScale(m_scr.risk);
      m_rt.lotMult  *= riskLotScale;
      m_rt.stepMult *= m_optStepFactor;
      m_rt.martMult  = m_grid.Multiplier(m_mkt) * m_optMartFactor;

      double dayDD = (m_dayStartBal > 0) ? (m_dayStartBal - equity) / m_dayStartBal * 100.0 : 0.0;
      if(m_cfg.dailyLossPct > 0 && dayDD >= m_cfg.dailyLossPct) m_rt.allowNew = false;
      if(!m_session.CanOpenNew()) m_rt.allowNew = false;
      if(HourBlocksNew())         m_rt.allowNew = false;
      if(TimeCurrent() < m_noNewUntil) m_rt.allowNew = false;   // pausa tras stop de catastrofe / corte por tiempo
      if(MaskBlocksNew())              m_rt.allowNew = false;   // horas/dias sin sembrar

      bool allowAdd = m_tradeOK;
      if(m_cfg.maxSpreadAdd > 0 && m_mkt.spread > m_cfg.maxSpreadAdd) allowAdd = false;
      if(m_cfg.marginMinLevel > 0)
      {
         double mU = AccountInfoDouble(ACCOUNT_MARGIN), mL = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
         if(mU > 0 && mL > 0 && mL < m_cfg.marginMinLevel) allowAdd = false;
      }

      // 10) Cortacircuitos (todo input > 0; con 0 no hace nada)
      double _ageMin = (m_basketOpen > 0) ? (TimeCurrent() - m_basketOpen) / 60.0 : 0.0;
      ENUM_BREAKER _brk = m_breaker.Check(m_bkt.floating, balance, m_ddPct, _ageMin, m_bkt.total);
      if(_brk == BRK_CLOSE_ALL && m_bkt.total > 0)
      {
         m_learn.Event("breaker_close", "margen/equity");
         CloseAll("breaker_close");
         DrawDash(balance, equity);
         return;
      }
      if(_brk == BRK_DERISK && m_tradeOK)
      {
         if(m_bkt.total > 1 && (TimeCurrent() - m_lastPartial) >= (m_cfg.minSecs * 10))
            if(m_partial.CloseWorst(m_trade, 1, SIDE_BOTH) > 0)
               { m_lastPartial = TimeCurrent(); m_recorder.MarkPartial(); }
      }
      if(_brk != BRK_NONE) { m_rt.allowNew = false; allowAdd = false; }

      // 11) Snapshots / telemetria
      if(m_cfg.useDB && (TimeCurrent() - m_lastSnapshot) >= m_cfg.snapSec)
      {
         CheckHotReset(balance);
         double _rbal = m_learn.initialBankroll + m_netRealized;
         m_learn.Snapshot(_rbal + m_bank + m_bkt.floating, _rbal, m_bkt.floating + m_bank,
                          m_bkt.total, m_mkt.adx, m_mkt.atr);
         m_learn.SnapshotAccount(balance, equity, equity - balance,
            AccountInfoDouble(ACCOUNT_MARGIN), AccountInfoDouble(ACCOUNT_MARGIN_FREE),
            AccountInfoDouble(ACCOUNT_MARGIN_LEVEL));
         m_lastSnapshot = TimeCurrent();
      }
      if(m_cfg.useDB && (TimeCurrent() - m_lastTel) >= m_cfg.telSec)
      {
         WriteTelemetry(equity, balance);
         m_lastTel = TimeCurrent();
         if((++m_telCount % 500) == 0)
         {
            m_learn.TrimTelemetry(MathMax(m_cfg.telemetryKeep, 5000));
            m_learn.TrimAccount(MathMax(m_cfg.telemetryKeep, 20000));
         }
      }

      if(!m_tradeOK) { DrawDash(balance, equity); return; }

      // 11c) Fin de semana
      if(m_session.ShouldFlatten())
      {
         if(m_bkt.total > 0) CloseAll("weekend_flat");
         DrawDash(balance, equity);
         return;
      }

      double step = m_grid.Step(m_mkt, m_rt.stepMult);

      // 12) SALIDAS
      if(m_bkt.total > 0)
      {
         double timeMin = (m_basketOpen > 0) ? (TimeCurrent() - m_basketOpen) / 60.0 : 0.0;
         double target  = m_tp.BasketTP(m_mkt, m_bkt, m_rt, timeMin);
         double net     = m_bkt.floating + m_bank + LockFloating();   // lo cobrado y la cobertura cuentan

         // CORTE POR TIEMPO: una cesta normal cierra en minutos (mediana 6 min oro, 10 min BTC);
         // si sigue viva tras T minutos se da por fallida, se cierra y se vuelve a grindear.
         if(m_cfg.timeCutMin > 0 && timeMin >= m_cfg.timeCutMin && (!m_cfg.timeCutOnlyLoss || net < 0))
         {
            PrintFormat("[TQ] CORTE POR TIEMPO: %.0f min, neto %.2f, %d posiciones", timeMin, net, m_bkt.total);
            CloseAll("time_cut"); DrawDash(balance, equity); return;
         }

         // STOP DE CATASTROFE: solo cestas profundas (>= N posiciones) que ya perdieron X% del balance.
         if(m_cfg.deepStopLevels > 0 && m_bkt.total >= m_cfg.deepStopLevels &&
            net <= -balance * m_cfg.deepStopPct / 100.0)
         {
            PrintFormat("[TQ] STOP CATASTROFE: neto %.2f, %d posiciones", net, m_bkt.total);
            CloseAll("deep_stop"); DrawDash(balance, equity); return;
         }

         // STOP DE CESTA por monto. Con stopBudgetFrac el stop crece con lo ganado desde el ultimo stop.
         double stopMoney = m_cfg.basketStopMoney;
         if(stopMoney > 0.0 && m_cfg.stopBudgetFrac > 0.0)
         {
            stopMoney = MathMax(stopMoney, m_cfg.stopBudgetFrac * m_sinceStop);
            if(m_cfg.stopBudgetCap > 0.0) stopMoney = MathMin(stopMoney, m_cfg.stopBudgetCap);
         }
         if(stopMoney > 0.0 && net <= -stopMoney)
         {
            PrintFormat("[TQ] STOP DE CESTA: neto %.2f <= -%.2f (niveles=%d lotes=%.2f)",
                        net, stopMoney, m_bkt.total, m_bkt.lotsTotal);
            CloseAll("basket_stop_hard"); DrawDash(balance, equity); return;
         }
         if(net >= target) { CloseAll("basket_tp"); DrawDash(balance, equity); return; }

         if(m_cfg.ratchetLock > 0.0 && target > 0.0 && m_basketPeak >= target * m_cfg.ratchetArmPct)
         {
            double suelo = m_basketPeak * m_cfg.ratchetLock;
            if(net <= suelo && net > 0)
               { CloseAll("ratchet_tp"); DrawDash(balance, equity); return; }
         }
         if(net > m_basketPeak && net >= target * m_cfg.ratchetArmPct) m_basketPeak = net;
         if(net >= m_cfg.bePad && m_trailing.Check(net, m_basketPeak, m_mkt, m_rt))
            { CloseAll("trail_tp"); DrawDash(balance, equity); return; }

         // V3: desarme de cestas profundas
         if(!m_locked) ScalpAndPayDown(step);

         if(m_rt.recoveryLevel >= 2 && m_bkt.total >= 5 &&
            (TimeCurrent() - m_lastPartial) >= (m_cfg.minSecs * 5))
         {
            if(m_partial.CloseWorst(m_trade, 1, SIDE_BOTH) > 0)
               { m_lastPartial = TimeCurrent(); m_recorder.MarkPartial(); }
         }
         if(m_curRegime == REGIME_TREND_UP || m_curRegime == REGIME_TREND_DOWN ||
            m_curRegime == REGIME_BREAKOUT)
            if(m_hedge.TryHedge(m_trade, m_mkt, m_scr.trendDir, m_scr.trend, m_bkt, m_rt))
               m_recorder.MarkHedge();
      }

      // 14) Anti-spike temporal
      if((TimeCurrent() - m_lastAdd)     < m_cfg.minSecs)     { DrawDash(balance, equity); return; }
      if((TimeCurrent() - m_lastHarvest) < m_cfg.restartSecs) { DrawDash(balance, equity); return; }

      bool trendRegime = (m_curRegime == REGIME_TREND_UP || m_curRegime == REGIME_TREND_DOWN ||
                          m_curRegime == REGIME_BREAKOUT);
      double gStep = step, gMart = m_rt.martMult, gScale = m_rt.lotMult;
      if(m_curRegime == REGIME_HIGH_VOL) { gStep = step * 1.5; gMart = MathMax(m_rt.martMult, 1.0); gScale = m_rt.lotMult * 0.6; }

      // 15a) CESTA ABIERTA: perseguir el precio (salvo con candado puesto)
      if(m_bkt.total > 0)
      {
         if(ManageLock(balance)) { DrawDash(balance, equity); return; }
         if(allowAdd)
         {
            if(trendRegime && !m_cfg.chaseInTrend) ManageTrend(m_scr.trendDir, step);
            else
            {
               GridAdds(gStep, gMart, gScale);
               if(trendRegime) ManageTrend(m_scr.trendDir, step);   // piramide a favor
            }
         }
         DrawDash(balance, equity);
         return;
      }

      // 15b) SIN CESTA: sembrar segun regimen
      if(!m_rt.allowNew) { DrawDash(balance, equity); return; }
      if(trendRegime) ManageTrend(m_scr.trendDir, step);
      else            SeedGrid(gScale);

      DrawDash(balance, equity);
   }

   void DrawDash(double balance, double equity)
   {
      double dailyP  = balance - m_dayStartBal;
      double weeklyP = balance - m_weekStartBal;
      double step    = m_grid.Step(m_mkt, m_rt.stepMult);
      m_dash.Render(m_mkt, m_scr, m_bkt, m_rt, m_regime.Name(m_curRegime),
                    balance, equity, m_ddPct, m_learn.initialBankroll,
                    m_harvested, dailyP, weeklyP, m_cycles, step);
   }
};

#endif // TOKIO_ENGINE_MQH
