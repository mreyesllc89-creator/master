//+------------------------------------------------------------------+
//|                                                  SignalEngine.mqh |
//|   TokioQuant - Scores de IA y generacion de senales               |
//|   Completa los scores (momentum/vol/liquidez/quality/confidence)  |
//|   y expone senales de entrada especificas por regimen.            |
//+------------------------------------------------------------------+
#ifndef TOKIO_SIGNALENGINE_MQH
#define TOKIO_SIGNALENGINE_MQH

#include "Utilities.mqh"

class CSignalEngine
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Completa los scores. Requiere s.trend, s.trendDir y s.risk ya seteados.
   void ComputeScores(SScores &s, const SMarket &m, ENUM_REGIME regime, double ddPct)
   {
      // --- Momentum score (magnitud) ---
      double momA = Clamp(MathAbs(m.momentum) * 20.0, 0.0, 100.0);
      double macdA = Clamp(MathAbs(m.macdHist) / (m.atr > 0 ? m.atr : 1.0) * 100.0, 0.0, 100.0);
      double rsiA = MathAbs(m.rsi - 50.0) * 2.0; // 0..100
      s.momentum = Clamp(0.45*momA + 0.35*macdA + 0.20*rsiA, 0.0, 100.0);

      // --- Volatilidad score ---
      s.volatility = Clamp(MapRange(m.atrRatio, 0.6, 2.5, 0.0, 100.0), 0.0, 100.0);

      // --- Liquidez score (spread bajo + volumen sano = buena liquidez) ---
      double spreadScore = MapRange(m.spread, m_cfg.maxSpreadUSD, 0.0, 0.0, 100.0);
      double volFlow      = SafeDiv(m.volume, m.volAvg, 1.0);
      double volScore     = MapRange(volFlow, 0.5, 1.5, 0.0, 100.0);
      s.liquidity = Clamp(0.6*spreadScore + 0.4*volScore, 0.0, 100.0);

      // --- Presion de recuperacion ---
      s.recovery = Clamp(MapRange(ddPct, 0.0, m_cfg.equityStopPct, 0.0, 100.0), 0.0, 100.0);

      // --- Calidad de mercado ---
      // Penaliza volatilidad excesiva; premia liquidez y claridad direccional.
      double excessVol = Clamp(MapRange(m.atrRatio, 1.8, 3.0, 0.0, 100.0), 0.0, 100.0);
      double clarity   = MathMax(s.trend, 100.0 - s.trend); // clara si muy tendencial o muy rango
      s.quality = Clamp(0.45*s.liquidity + 0.30*clarity + 0.25*(100.0 - excessVol), 0.0, 100.0);

      // --- Confianza compuesta para actuar ---
      double dirStrength = (regime == REGIME_TREND_UP || regime == REGIME_TREND_DOWN ||
                            regime == REGIME_BREAKOUT)
                           ? s.trend : (100.0 - s.trend);
      s.confidence = Clamp(0.40*s.quality + 0.30*dirStrength + 0.30*(100.0 - s.risk),
                           0.0, 100.0);
   }

   // Senal de entrada por pullback en tendencia. Devuelve lado o SIDE_NONE.
   ENUM_SIDE PullbackEntry(const SMarket &m, int trendDir)
   {
      double near = 0.5 * m.atr; // "cerca" de la EMA
      if(trendDir > 0)
      {
         // Alcista: compramos retroceso hacia EMA rapida/media sin sobrecompra
         bool pull = (m.bid <= m.ema20 + near) || (m.bid <= m.ema50 + near);
         if(pull && m.rsi < 60.0) return SIDE_BUY;
      }
      else if(trendDir < 0)
      {
         // Bajista: vendemos rebote hacia EMA rapida/media sin sobreventa
         bool pull = (m.ask >= m.ema20 - near) || (m.ask >= m.ema50 - near);
         if(pull && m.rsi > 40.0) return SIDE_SELL;
      }
      return SIDE_NONE;
   }

   // Senal de reversion a la media. Devuelve lado o SIDE_NONE.
   ENUM_SIDE MeanRevertEntry(const SMarket &m)
   {
      bool overbought = (m.rsi > 70.0 || m.cci > 150.0 || m.bid > m.bbUpper);
      bool oversold   = (m.rsi < 30.0 || m.cci < -150.0 || m.ask < m.bbLower);
      if(overbought) return SIDE_SELL;
      if(oversold)   return SIDE_BUY;
      return SIDE_NONE;
   }
};

#endif // TOKIO_SIGNALENGINE_MQH
