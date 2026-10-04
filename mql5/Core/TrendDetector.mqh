//+------------------------------------------------------------------+
//|                                                 TrendDetector.mqh |
//|   TokioQuant - Confianza de tendencia 0-100 + direccion          |
//|   Combina: alineacion EMA, ADX/DI, pendiente, momentum,          |
//|   expansion de ATR y velocidad de precio, penalizando desacuerdo.|
//+------------------------------------------------------------------+
#ifndef TOKIO_TRENDDETECTOR_MQH
#define TOKIO_TRENDDETECTOR_MQH

#include "Utilities.mqh"

class CTrendDetector
{
private:
   SConfig m_cfg;

public:
   void Init(const SConfig &cfg) { m_cfg = cfg; }

   // Devuelve confianza [0..100] y direccion (+1/-1/0) por referencia.
   void Compute(const SMarket &m, double &conf, int &dir)
   {
      // --- 1. Alineacion de EMAs ---
      double align = 0; int adir = 0;
      if(m.ema20 > m.ema50 && m.ema50 > m.ema100 && m.ema100 > m.ema200)      { align = 100; adir = 1; }
      else if(m.ema20 < m.ema50 && m.ema50 < m.ema100 && m.ema100 < m.ema200) { align = 100; adir = -1; }
      else
      {
         int up = 0, dn = 0;
         if(m.ema20  > m.ema50)  up++; else dn++;
         if(m.ema50  > m.ema100) up++; else dn++;
         if(m.ema100 > m.ema200) up++; else dn++;
         align = MathAbs(up - dn) / 3.0 * 100.0;
         adir  = (up > dn) ? 1 : ((dn > up) ? -1 : 0);
      }

      // --- 2. ADX + direccion por DI ---
      double adxScore = MapRange(m.adx, m_cfg.adxRange, 40.0, 0.0, 100.0);
      int    didir    = (m.plusDI > m.minusDI) ? 1 : ((m.minusDI > m.plusDI) ? -1 : 0);

      // --- 3. Pendiente de EMA ---
      int sdir; double slopeScore = SlopeToScore(m.emaSlope, m.atr, sdir);

      // --- 4. Momentum ---
      int    mdir     = (m.momentum > 0) ? 1 : ((m.momentum < 0) ? -1 : 0);
      double momScore = Clamp(MathAbs(m.momentum) * 20.0, 0.0, 100.0);

      // --- 5. Velocidad de precio ---
      int vdir; double velScore = SlopeToScore(m.priceVelocity, m.atr, vdir);

      // --- 6. Expansion de ATR (apoya la tendencia, no la direccion) ---
      double atrExp = MapRange(m.atrRatio, 1.0, 2.0, 0.0, 100.0);

      // --- Resolucion de direccion (voto ponderado por magnitud) ---
      double vote = adir*align + didir*adxScore + sdir*slopeScore +
                    mdir*momScore + vdir*velScore;
      dir = (vote > 0) ? 1 : ((vote < 0) ? -1 : 0);

      // --- Confianza base (media ponderada) ---
      double base = 0.30*align + 0.25*adxScore + 0.20*slopeScore +
                    0.15*momScore + 0.10*velScore;

      // --- Factor de acuerdo: cuantos componentes apuntan a 'dir' ---
      int agree = 0, tot = 5;
      if(adir  == dir && dir != 0) agree++;
      if(didir == dir && dir != 0) agree++;
      if(sdir  == dir && dir != 0) agree++;
      if(mdir  == dir && dir != 0) agree++;
      if(vdir  == dir && dir != 0) agree++;
      double agreeFactor = (double)agree / tot;

      // Escalamos: sin acuerdo baja a ~50%, pleno acuerdo mantiene 100%.
      base *= (0.5 + 0.5 * agreeFactor);
      // Pequeno impulso por expansion de volatilidad
      base *= (0.85 + 0.15 * atrExp / 100.0);

      conf = Clamp(base, 0.0, 100.0);
      if(dir == 0) conf = 0.0;
   }
};

#endif // TOKIO_TRENDDETECTOR_MQH
