//+------------------------------------------------------------------+
//|                                                MarketScanner.mqh  |
//|   TokioQuant - Escaner de mercado (el "sensor" del cerebro)       |
//|   Calcula continuamente indicadores y microestructura.            |
//|   OPTIMIZACION: lo barato se calcula por tick; lo caro (VWAP,     |
//|   estructura, volumen) se cachea y solo se recalcula por barra.   |
//+------------------------------------------------------------------+
#ifndef TOKIO_MARKETSCANNER_MQH
#define TOKIO_MARKETSCANNER_MQH

#include "Utilities.mqh"

class CMarketScanner
{
private:
   SConfig m_cfg;
   string  m_sym;
   ENUM_TIMEFRAMES m_tf;

   // Handles de indicadores
   int m_hAtr, m_hAdx, m_hRsi, m_hCci, m_hMacd, m_hBands, m_hMom;
   int m_hEma20, m_hEma50, m_hEma100, m_hEma200;

   // Cache por barra (calculo pesado)
   datetime m_lastBar;
   double   m_vwap, m_vwapPrev, m_vwapSlope;
   double   m_swingHigh, m_swingLow, m_fracUp, m_fracDn;
   bool     m_bosUp, m_bosDn, m_liqUp, m_liqDn, m_fvgUp, m_fvgDn;
   double   m_obBull, m_obBear;
   int      m_mstruct;
   double   m_volume, m_volAvg;

   //--- Lectura de un valor de buffer en un shift dado ---
   double Buf(int h, int b, int shift)
   {
      double a[];
      if(CopyBuffer(h, b, shift, 1, a) == 1) return a[0];
      return 0.0;
   }

   //--- Pendiente de un buffer de indicador sobre 'lb' barras ---
   double BufSlope(int h, int b, int lb)
   {
      double a[];
      ArraySetAsSeries(a, true);
      if(lb < 1) lb = 1;
      if(CopyBuffer(h, b, 0, lb + 1, a) == lb + 1)
         return (a[0] - a[lb]) / (double)lb;
      return 0.0;
   }

   //--- Recalculo pesado (una vez por barra) ---
   void UpdateHeavy(void)
   {
      ComputeVWAP();
      ComputeVolume();
      ComputeStructure();
   }

   //--- VWAP de la sesion diaria (desde medianoche del servidor) ---
   void ComputeVWAP(void)
   {
      m_vwapPrev = m_vwap;
      datetime now   = TimeCurrent();
      datetime start = now - (now % 86400); // inicio del dia (UTC servidor)

      MqlRates r[];
      int n = CopyRates(m_sym, m_tf, start, now, r);
      if(n <= 0) { m_vwapSlope = 0; return; }

      double pv = 0.0, vv = 0.0;
      for(int i = 0; i < n; i++)
      {
         double typical = (r[i].high + r[i].low + r[i].close) / 3.0;
         double v = (double)r[i].tick_volume;
         pv += typical * v;
         vv += v;
      }
      m_vwap      = (vv > 0) ? pv / vv : m_vwap;
      m_vwapSlope = (m_vwapPrev > 0) ? (m_vwap - m_vwapPrev) : 0.0;
   }

   //--- Volumen actual y promedio ---
   void ComputeVolume(void)
   {
      long v[];
      ArraySetAsSeries(v, true);
      int lb = m_cfg.volLookback;
      int copied = CopyTickVolume(m_sym, m_tf, 0, lb + 1, v);
      if(copied <= 1) return;
      m_volume = (double)v[1];      // ultima barra cerrada
      double s = 0; int c = 0;
      for(int i = 1; i <= lb && i < copied; i++) { s += (double)v[i]; c++; }
      m_volAvg = (c > 0) ? s / c : m_volume;
   }

   //--- Estructura de mercado / smart money (simplificado pero real) ---
   void ComputeStructure(void)
   {
      int need = MathMax(m_cfg.swingLookback, 60);
      MqlRates r[];
      ArraySetAsSeries(r, true);
      int n = CopyRates(m_sym, m_tf, 0, need, r);
      if(n < 12) return;

      // --- Fractales de 5 barras: buscamos los 2 mas recientes por lado ---
      double sh1 = 0, sh2 = 0, sl1 = 0, sl2 = 0;
      int foundH = 0, foundL = 0;
      // i = centro; arrancamos en 3 para que los vecinos derechos (1,2) esten cerrados
      for(int i = 3; i < n - 2 && (foundH < 2 || foundL < 2); i++)
      {
         bool isHigh = (r[i].high > r[i-1].high && r[i].high > r[i-2].high &&
                        r[i].high > r[i+1].high && r[i].high > r[i+2].high);
         bool isLow  = (r[i].low  < r[i-1].low  && r[i].low  < r[i-2].low  &&
                        r[i].low  < r[i+1].low  && r[i].low  < r[i+2].low);
         if(isHigh) { if(foundH == 0) sh1 = r[i].high; else if(foundH == 1) sh2 = r[i].high; foundH++; }
         if(isLow)  { if(foundL == 0) sl1 = r[i].low;  else if(foundL == 1) sl2 = r[i].low;  foundL++; }
      }

      m_swingHigh = (sh1 > 0) ? sh1 : r[1].high;
      m_swingLow  = (sl1 > 0) ? sl1 : r[1].low;
      m_fracUp    = m_swingHigh;
      m_fracDn    = m_swingLow;

      // --- Estructura HH/HL vs LH/LL ---
      if(foundH >= 2 && foundL >= 2)
      {
         if(sh1 > sh2 && sl1 > sl2)      m_mstruct = MS_BULL;
         else if(sh1 < sh2 && sl1 < sl2) m_mstruct = MS_BEAR;
         else                            m_mstruct = MS_MIXED;
      }
      else m_mstruct = MS_NONE;

      // --- Break of Structure (usando la ultima barra cerrada) ---
      double c1 = r[1].close, h1 = r[1].high, l1 = r[1].low;
      m_bosUp = (m_swingHigh > 0 && c1 > m_swingHigh);
      m_bosDn = (m_swingLow  > 0 && c1 < m_swingLow);

      // --- Barrida de liquidez (wick rompe swing pero cierra de regreso) ---
      m_liqUp = (m_swingHigh > 0 && h1 > m_swingHigh && c1 < m_swingHigh);
      m_liqDn = (m_swingLow  > 0 && l1 < m_swingLow  && c1 > m_swingLow);

      // --- Fair Value Gap / imbalance (3 velas) ---
      m_fvgUp = (r[1].low  > r[3].high); // hueco alcista
      m_fvgDn = (r[1].high < r[3].low);  // hueco bajista

      // --- Order block simplificado: ultima vela opuesta antes del impulso ---
      m_obBull = 0; m_obBear = 0;
      if(m_bosUp)
         for(int k = 1; k <= 5 && k < n; k++)
            if(r[k].close < r[k].open) { m_obBull = r[k].low; break; }
      if(m_bosDn)
         for(int k = 1; k <= 5 && k < n; k++)
            if(r[k].close > r[k].open) { m_obBear = r[k].high; break; }
   }

public:
   CMarketScanner(void) : m_hAtr(INVALID_HANDLE), m_hAdx(INVALID_HANDLE),
      m_hRsi(INVALID_HANDLE), m_hCci(INVALID_HANDLE), m_hMacd(INVALID_HANDLE),
      m_hBands(INVALID_HANDLE), m_hMom(INVALID_HANDLE), m_hEma20(INVALID_HANDLE),
      m_hEma50(INVALID_HANDLE), m_hEma100(INVALID_HANDLE), m_hEma200(INVALID_HANDLE),
      m_lastBar(0), m_vwap(0), m_vwapPrev(0), m_vwapSlope(0),
      m_swingHigh(0), m_swingLow(0), m_fracUp(0), m_fracDn(0),
      m_bosUp(false), m_bosDn(false), m_liqUp(false), m_liqDn(false),
      m_fvgUp(false), m_fvgDn(false), m_obBull(0), m_obBear(0),
      m_mstruct(MS_NONE), m_volume(0), m_volAvg(0) {}

   bool Init(const SConfig &cfg)
   {
      m_cfg = cfg;
      m_sym = cfg.symbol;
      m_tf  = cfg.tf;

      m_hAtr   = iATR(m_sym, m_tf, cfg.atrPeriod);
      m_hAdx   = iADX(m_sym, m_tf, cfg.adxPeriod);
      m_hRsi   = iRSI(m_sym, m_tf, cfg.rsiPeriod, PRICE_CLOSE);
      m_hCci   = iCCI(m_sym, m_tf, cfg.cciPeriod, PRICE_TYPICAL);
      m_hMacd  = iMACD(m_sym, m_tf, cfg.macdFast, cfg.macdSlow, cfg.macdSignal, PRICE_CLOSE);
      m_hBands = iBands(m_sym, m_tf, cfg.bbPeriod, 0, cfg.bbDev, PRICE_CLOSE);
      m_hMom   = iMomentum(m_sym, m_tf, cfg.momPeriod, PRICE_CLOSE);
      m_hEma20  = iMA(m_sym, m_tf, cfg.emaFast,  0, MODE_EMA, PRICE_CLOSE);
      m_hEma50  = iMA(m_sym, m_tf, cfg.emaMed,   0, MODE_EMA, PRICE_CLOSE);
      m_hEma100 = iMA(m_sym, m_tf, cfg.emaSlow,  0, MODE_EMA, PRICE_CLOSE);
      m_hEma200 = iMA(m_sym, m_tf, cfg.emaTrend, 0, MODE_EMA, PRICE_CLOSE);

      if(m_hAtr==INVALID_HANDLE  || m_hAdx==INVALID_HANDLE  || m_hRsi==INVALID_HANDLE ||
         m_hCci==INVALID_HANDLE  || m_hMacd==INVALID_HANDLE || m_hBands==INVALID_HANDLE ||
         m_hMom==INVALID_HANDLE  || m_hEma20==INVALID_HANDLE|| m_hEma50==INVALID_HANDLE||
         m_hEma100==INVALID_HANDLE || m_hEma200==INVALID_HANDLE)
      {
         Print("CMarketScanner: fallo al crear indicadores err=", GetLastError());
         return false;
      }
      return true;
   }

   void Deinit(void)
   {
      IndicatorRelease(m_hAtr);   IndicatorRelease(m_hAdx);   IndicatorRelease(m_hRsi);
      IndicatorRelease(m_hCci);   IndicatorRelease(m_hMacd);  IndicatorRelease(m_hBands);
      IndicatorRelease(m_hMom);   IndicatorRelease(m_hEma20); IndicatorRelease(m_hEma50);
      IndicatorRelease(m_hEma100);IndicatorRelease(m_hEma200);
   }

   //--- Llena SMarket. Devuelve false si faltan datos (mercado no listo). ---
   bool Update(SMarket &m)
   {
      m.valid = false;

      // Basicos de precio
      m.bid   = SymbolInfoDouble(m_sym, SYMBOL_BID);
      m.ask   = SymbolInfoDouble(m_sym, SYMBOL_ASK);
      if(m.bid <= 0 || m.ask <= 0) return false;
      m.mid    = (m.bid + m.ask) / 2.0;
      m.point  = SymbolInfoDouble(m_sym, SYMBOL_POINT);
      m.spread = m.ask - m.bid;
      m.tickValue = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_VALUE);
      m.tickSize  = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_SIZE);

      // Medias
      m.ema20  = Buf(m_hEma20, 0, 0);
      m.ema50  = Buf(m_hEma50, 0, 0);
      m.ema100 = Buf(m_hEma100, 0, 0);
      m.ema200 = Buf(m_hEma200, 0, 0);
      m.emaSlope = BufSlope(m_hEma20, 0, m_cfg.slopeLookback);

      // ATR + regimen de volatilidad
      m.atr = Buf(m_hAtr, 0, 0);
      double atrArr[];
      ArraySetAsSeries(atrArr, true);
      int lb = m_cfg.atrAvgLookback;
      if(CopyBuffer(m_hAtr, 0, 0, lb, atrArr) == lb)
      {
         double s = 0; for(int i = 0; i < lb; i++) s += atrArr[i];
         m.atrAvg = s / lb;
      }
      else m.atrAvg = m.atr;
      m.atrRatio = SafeDiv(m.atr, m.atrAvg, 1.0);

      // ADX / DI
      m.adx    = Buf(m_hAdx, 0, 0);
      m.plusDI = Buf(m_hAdx, 1, 0);
      m.minusDI= Buf(m_hAdx, 2, 0);

      // Osciladores
      m.rsi = Buf(m_hRsi, 0, 0);
      m.cci = Buf(m_hCci, 0, 0);
      m.momentum = Buf(m_hMom, 0, 0) - 100.0;

      // MACD
      m.macdMain   = Buf(m_hMacd, 0, 0);
      m.macdSignal = Buf(m_hMacd, 1, 0);
      m.macdHist   = m.macdMain - m.macdSignal;

      // Bollinger
      m.bbMid   = Buf(m_hBands, 0, 0);
      m.bbUpper = Buf(m_hBands, 1, 0);
      m.bbLower = Buf(m_hBands, 2, 0);
      m.bbWidth = SafeDiv(m.bbUpper - m.bbLower, m.bbMid, 0.0);

      // Pendiente y velocidad de precio + volatilidad (retornos)
      double c[];
      ArraySetAsSeries(c, true);
      int need = MathMax(m_cfg.slopeLookback, MathMax(m_cfg.velLookback, m_cfg.volLookback)) + 2;
      if(CopyClose(m_sym, m_tf, 0, need, c) == need)
      {
         m.priceSlope    = (c[0] - c[m_cfg.slopeLookback]) / (double)m_cfg.slopeLookback;
         m.priceVelocity = (c[0] - c[m_cfg.velLookback])   / (double)m_cfg.velLookback;
         // volatilidad = desviacion estandar de retornos * 100
         int vn = m_cfg.volLookback;
         double mean = 0.0;
         double ret[];
         ArrayResize(ret, vn);
         for(int i = 0; i < vn; i++) { ret[i] = SafeDiv(c[i]-c[i+1], c[i+1], 0.0); mean += ret[i]; }
         mean /= vn;
         double var = 0.0;
         for(int i = 0; i < vn; i++) var += MathPow(ret[i]-mean, 2);
         m.volatility = MathSqrt(var / vn) * 100.0;
      }

      // --- Calculo pesado cacheado por barra ---
      datetime bt = (datetime)SeriesInfoInteger(m_sym, m_tf, SERIES_LASTBAR_DATE);
      if(bt != m_lastBar)
      {
         UpdateHeavy();
         m_lastBar = bt;
      }
      // Volcado del cache (VWAP, estructura, volumen)
      m.vwap      = m_vwap;
      m.vwapSlope = m_vwapSlope;
      m.vwapDist  = m.mid - m_vwap;
      m.volume    = m_volume;
      m.volAvg    = m_volAvg;
      m.swingHigh = m_swingHigh;  m.swingLow = m_swingLow;
      m.fractalUp = m_fracUp;     m.fractalDn = m_fracDn;
      m.bosUp = m_bosUp;          m.bosDn = m_bosDn;
      m.liqSweepUp = m_liqUp;     m.liqSweepDn = m_liqDn;
      m.fvgUp = m_fvgUp;          m.fvgDn = m_fvgDn;
      m.obBull = m_obBull;        m.obBear = m_obBear;
      m.mstruct = m_mstruct;

      m.valid = true;
      return true;
   }
};

#endif // TOKIO_MARKETSCANNER_MQH
