//+------------------------------------------------------------------+
//|                                                  RegimeEngine.mqh |
//|   TokioQuant - Clasificador de regimen de mercado                 |
//|   Cada regimen habilita una estrategia distinta. La cascada esta  |
//|   ordenada por prioridad de riesgo (primero lo peligroso).        |
//+------------------------------------------------------------------+
#ifndef TOKIO_REGIMEENGINE_MQH
#define TOKIO_REGIMEENGINE_MQH

#include "Utilities.mqh"

class CRegimeEngine
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   ENUM_REGIME Classify(const SMarket &m, double trendConf, int trendDir, double ddPct)
   {
      // --- 1. PANICO: DD extremo -> solo administrar/salir ---
      if(m_cfg.dd6 > 0 && ddPct >= m_cfg.dd6) return REGIME_PANIC;

      // --- 2. NOTICIA: expansion violenta de ATR ---
      if(m.atrRatio >= 2.5) return REGIME_NEWS;

      // --- 3. RECOVERY: en DD relevante pero controlable ---
      if(m_cfg.dd2 > 0 && ddPct >= m_cfg.dd2) return REGIME_RECOVERY;

      // --- 4. ALTA VOLATILIDAD: reducir exposicion / ampliar step ---
      if(m.atrRatio >= 1.8) return REGIME_HIGH_VOL;

      // --- 5. BREAKOUT: ruptura de estructura con expansion de ATR ---
      if((m.bosUp || m.bosDn) && m.atrRatio >= 1.3 && m.adx >= m_cfg.adxTrend)
         return REGIME_BREAKOUT;

      // --- 6. TENDENCIA confirmada ---
      if(m.adx >= m_cfg.adxTrend && trendConf >= 60.0 && trendDir != 0)
         return (trendDir > 0) ? REGIME_TREND_UP : REGIME_TREND_DOWN;

      // --- 7. BAJA VOLATILIDAD: rango muy comprimido -> grid fino ---
      if(m.adx < m_cfg.adxRange && m.atrRatio < 0.8)
         return REGIME_LOW_VOL;

      // --- 8. REVERSION A LA MEDIA: sobre-extension sin tendencia ---
      if(m.adx < m_cfg.adxTrend &&
         (m.rsi > 70.0 || m.rsi < 30.0 || MathAbs(m.cci) > 150.0))
         return REGIME_MEAN_REVERT;

      // --- 9. RANGO por defecto ---
      return REGIME_RANGE;
   }

   // Etiqueta legible para el dashboard.
   string Name(ENUM_REGIME r)
   {
      switch(r)
      {
         case REGIME_RANGE:       return "RANGO";
         case REGIME_TREND_UP:    return "TENDENCIA ALCISTA";
         case REGIME_TREND_DOWN:  return "TENDENCIA BAJISTA";
         case REGIME_MEAN_REVERT: return "REVERSION MEDIA";
         case REGIME_BREAKOUT:    return "BREAKOUT";
         case REGIME_HIGH_VOL:    return "ALTA VOLATILIDAD";
         case REGIME_LOW_VOL:     return "BAJA VOLATILIDAD";
         case REGIME_NEWS:        return "NOTICIA";
         case REGIME_RECOVERY:    return "RECOVERY";
         case REGIME_PANIC:       return "PANICO";
      }
      return "?";
   }
};

#endif // TOKIO_REGIMEENGINE_MQH
