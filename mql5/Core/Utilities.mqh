//+------------------------------------------------------------------+
//|                                                   Utilities.mqh   |
//|   TokioQuant - Tipos compartidos, enums, structs y helpers        |
//|   Este modulo NO depende de ningun otro. Es la base de todo.      |
//+------------------------------------------------------------------+
#ifndef TOKIO_UTILITIES_MQH
#define TOKIO_UTILITIES_MQH

//==================================================================//
//  ENUMERACIONES DE DOMINIO                                         //
//==================================================================//

// Regimen de mercado detectado por RegimeEngine.
enum ENUM_REGIME
{
   REGIME_RANGE = 0,     // Lateral: grid adaptativo permitido
   REGIME_TREND_UP,      // Tendencia alcista: trend following
   REGIME_TREND_DOWN,    // Tendencia bajista: trend following
   REGIME_MEAN_REVERT,   // Sobre-extension: reversion a la media
   REGIME_BREAKOUT,      // Ruptura con expansion de ATR
   REGIME_HIGH_VOL,      // Volatilidad alta: reducir exposicion
   REGIME_LOW_VOL,       // Volatilidad baja: grid fino
   REGIME_NEWS,          // Movimiento tipo noticia: pausa entradas
   REGIME_RECOVERY,      // DD elevado: modo recuperacion controlada
   REGIME_PANIC          // Riesgo extremo: solo administrar/salir
};

// Estructura de mercado (Higher High / Lower Low, etc.)
enum ENUM_MSTRUCT
{
   MS_NONE = 0,   // Sin estructura clara
   MS_BULL,       // HH + HL  (alcista)
   MS_BEAR,       // LH + LL  (bajista)
   MS_MIXED       // Mixto / indeciso
};

// Lado logico para decisiones de entrada.
enum ENUM_SIDE
{
   SIDE_NONE = 0,
   SIDE_BUY,
   SIDE_SELL,
   SIDE_BOTH
};

//==================================================================//
//  CONFIGURACION GLOBAL (mapea los inputs del .mq5)                 //
//  Se llena una vez en OnInit y se pasa por referencia const.       //
//==================================================================//
struct SConfig
{
   // --- Ejecucion / identidad ---
   ulong           magic;
   string          symbol;
   ENUM_TIMEFRAMES tf;
   ulong           slippage;

   // --- Lotaje / martingala ---
   double baseLot;        // Lote nivel 1
   double maxLotOrder;    // Tope por orden (airbag)
   int    maxLevels;      // Niveles maximos por direccion
   double maxTotalLots;   // Exposicion maxima total (airbag)
   double martLow;        // Multiplicador si ATR bajo
   double martMed;        // Multiplicador si ATR medio
   double martHigh;       // Multiplicador si ATR alto
   double martXHigh;      // Multiplicador si ATR muy alto (1.0 = off)

   // --- Grid adaptativo ---
   bool   useATRStep;
   double atrMult;        // Paso base = ATR * atrMult
   double fixedStep;      // Paso fijo en precio (si ATR off)
   double minStep;        // Paso minimo en precio (anti micro-spike)

   // --- Indicadores / periodos ---
   int atrPeriod;
   int atrAvgLookback;    // Ventana para ATR promedio (regimen de vol)
   double maxAtrRatioNew; // EDGE: bloquea CESTAS NUEVAS si atr/atrAvg supera esto (0=off)
   double ratchetArmPct;  // UPGRADE: % del objetivo de TP al que se arma el trinquete (0=off)
   double ratchetLock;    // UPGRADE: % del pico que queda protegido (suelo que nunca baja)
   int emaFast, emaMed, emaSlow, emaTrend;   // 20/50/100/200
   int adxPeriod;
   int rsiPeriod;
   int cciPeriod;
   int macdFast, macdSlow, macdSignal;
   int bbPeriod;  double bbDev;
   int momPeriod;
   int volLookback;       // Ventana volumen promedio
   int swingLookback;     // Ventana para swings/estructura
   int slopeLookback;     // Barras para pendiente EMA/precio
   int velLookback;       // Barras para velocidad de precio

   // --- Salidas ---
   double baseTP;         // TP base del basket (moneda cuenta)
   double tpAtrMult;      // Componente dinamico del TP por ATR
   double tpMinUSD;       // Piso del TP dinamico
   double trailActUSD;    // Activar trailing a este profit
   double trailStepUSD;   // Retroceso base desde pico
   double bePad;          // Colchon breakeven

   // --- Riesgo ---
   double equityStopPct;  // Kill switch DD%
   double dailyLossPct;   // Freno perdida diaria
   double maxSpreadUSD;   // Spread maximo para abrir
   int    minSecs;        // Segundos minimos entre adds
   int    restartSecs;    // Pausa tras cosecha
   double marginMinLevel; // Nivel de margen minimo (%) para abrir

   // --- Tendencia ---
   double trendBlock;     // Trend Confidence que bloquea contra-tendencia
   double adxTrend;       // ADX minimo para considerar tendencia
   double adxRange;       // ADX por debajo del cual es rango

   // --- Recovery (umbrales DD%) ---
   double dd1, dd2, dd3, dd4, dd5, dd6;

   // --- Hedge inteligente ---
   bool   useHedge;
   double hedgeLot;
   double hedgeConf;      // Trend Confidence minima para hedge

   // --- Interes compuesto (lote base dinamico) ---
   bool   useCompound;        // Encender/apagar desde el panel de MT5
   double compoundAnchor;     // Capital de referencia (0 = usar balance inicial)
   double compoundReinvest;   // Fraccion de la ganancia reinvertida (0.5 = 50%)
   double compoundMaxMult;    // Tope de crecimiento del lote (x veces)
   double compoundMinMult;    // Piso de des-apalancamiento
   double compoundDDFloor;    // Freno maximo por drawdown (0.4 = -60% lote)
   double compoundHysteresis; // Margen extra para subir de escalon (0.10 = 10%)
   bool   compoundSmooth;     // true = redondeo estocastico (compuesto continuo)

   // --- Telegram ---
   bool   tg;
   string tgToken;
   string tgChat;

   // --- Base de datos / cerebro ---
   bool   useDB;
   string dbName;
   int    snapSec;
   int    telSec;         // Intervalo de escritura de telemetria (cockpit)
   bool   logCSV;

   // --- Cortacircuitos inteligente ---
   double brkMarginFloor;   // Nivel de margen % que fuerza cierre total (fisica)
   double brkMaxBasketMin;  // Minutos de vida antes de recortar (0=off)
   double brkStopAddPct;    // Perdida flotante % del balance que corta los adds

   // --- STOP DE CESTA (calibrado 2026-08-20 sobre 1083 cestas reales) ---
   // Sin tope, la perdida media de una cesta perdedora era -85.68 contra una
   // ganancia media de +4.05: relacion 21:1, que exige 95.5% de aciertos para
   // empatar. El sistema acertaba 91.0% -> -4408.61 netos.
   // Con tope -50 la perdida media baja a -29.79, el breakeven cae a 88.0%
   // y los mismos 1083 trades dan +1068.93. Es el cambio que mas dinero mueve.
   double basketStopMoney;  // Perdida flotante maxima por cesta (0=off)
   int    maxTotalLevels;   // Tope GLOBAL de posiciones (los 2 lados juntos)
   double blockAddsAdverseAdx; // ADX que bloquea ADDS a favor de la tendencia contraria (0=off)

   // --- Dashboard ---
   bool   showDash;

   // --- Sesion (especifico XAUUSD: horario + proteccion de fin de semana) ---
   bool   avoidWeekend;    // true = respeta horario de mercado (oro)
   bool   weekendFlatten;  // true = cierra todo antes del fin de semana
   int    friStopHour;     // Viernes: hora servidor para dejar de abrir nuevas
   int    friFlattenHour;  // Viernes: hora servidor para aplanar todo
   int    monStartHour;    // Lunes: hora servidor para reanudar
   int    sunResumeHour;   // Domingo: hora servidor de reapertura (0 = no domingo)

   // --- V3: persecucion del precio (grid sin techo) ---
   // Medido sobre 51 stops reales (ago-oct 2026) contra el precio M1 real:
   // 50 se habrian recuperado (31 en <30 min, 45 en <4 h). El grid se
   // congelaba en tendencia y el stop de -30 cerraba en el peor momento.
   bool   chaseInTrend;     // seguir promediando la cesta abierta aunque el regimen sea tendencia
   double stepGrowth;       // crecimiento geometrico del paso por nivel (0.10 = +10% por nivel)
   int    martMaxLevels;    // niveles con martingala; a partir de aqui el lote queda plano (0 = siempre)
   double maxSpreadAdd;     // spread maximo para PROMEDIAR una cesta abierta (precio, 0 = sin limite)
   double adverseStepMult;  // paso extra cuando la tendencia fuerte va contra el lado que se promedia
   bool   addConfirmM1;     // promediar solo si la vela M1 actual no esta haciendo nuevo extremo adverso
   int    noNewFromHour;    // no sembrar cestas desde esta hora servidor (-1 = off)
   int    noNewToHour;      // ... hasta esta hora servidor (inclusive)

   // --- V3: desarme inteligente de cestas profundas ---
   int    scalpFromLevel;   // a partir de este nivel, cada posicion lleva su propio TP (0 = off)
   double scalpStepFrac;    // TP individual = fraccion del paso del grid (precio)
   bool   payDown;          // usar lo cobrado por los scalps para cerrar la peor posicion
   double payDownBuffer;    // colchon minimo (moneda) que debe quedar tras pagar la peor
   int    deepLevels;       // desde este numero de posiciones la cesta sale al breakeven (0 = off)
   double deepTP;           // objetivo (moneda) de una cesta profunda: pequeno y fijo
   double survivalDDPct;    // MODO SUPERVIVENCIA: si la cesta pierde >= este % del balance... (0 = off)
   double survivalStepMult; // ...sigue persiguiendo con paso x esto y lote plano (sin martingala). Nunca cierra.
   // --- ANTI-MARTINGALA INTELIGENTE (martingala tras ganancias, minima) ---
   double winBoostStep;     // +x del lote base por cada cesta "limpia" ganada seguida (0 = off)
   double winBoostMax;      // tope del multiplicador (p.ej. 1.5)
   int    cleanWinLevels;   // una ganancia cuenta si la cesta no paso de N posiciones; si pasa, racha a 0
   // --- CANDADO DE COBERTURA (congela el DD de una cesta en tendencia, sin cerrar nada) ---
   double lockPct;          // bloquear cuando la cesta pierde >= este % del balance (0 = off)
   int    lockMinLevels;    // ...y tiene al menos N posiciones
   double unlockATR;        // desbloquear cuando el precio rebota N x ATR desde el extremo
   double relockStepPct;    // re-bloquear si el neto empeora otro X % del balance tras desbloquear
   // --- STOP DE CATASTROFE (solo cestas profundas: el 0,16% que se vuelve tendencia) ---
   int    deepStopLevels;   // solo actua si la cesta tiene >= N posiciones (0 = off)
   double deepStopPct;      // ...y pierde >= este % del balance
   double stopCooldownH;    // horas sin sembrar cestas nuevas tras un stop de catastrofe (la tendencia sigue)
   // --- CORTE POR TIEMPO: la cesta que dura mas que T se da por fallida y se cierra ---
   double timeCutMin;       // minutos de vida maxima de una cesta (0 = off)
   bool   timeCutOnlyLoss;  // cortar solo si el neto es negativo
   double timeCutPauseMin;  // minutos sin sembrar tras un corte por tiempo
   // --- HORAS / DIAS SIN SEMBRAR (las cestas abiertas se siguen gestionando) ---
   string blockHours;       // horas servidor separadas por coma, p.ej. "23,0,1,2,3"
   string blockDays;        // dias 0=Dom..6=Sab separados por coma, p.ej. "6"
   // --- LADO OPERADO: el 71% del dano de 2026 vino de las ventas contra subidas ---
   int    sideMode;         // 0 ambos, 1 solo compras, 2 solo ventas, 3 a favor de tendencia, 4 contra tendencia
   int    sideLookbackH;    // tendencia = precio actual vs cierre H1 de hace N horas
   // --- STOP DE CESTA: pausa, stop financiado por lo ganado y giro tras el stop ---
   double stopPauseMin;     // minutos sin sembrar tras un stop de cesta
   double stopBudgetFrac;   // stop = max(basketStopMoney, frac x ganado desde el ultimo stop)
   double stopBudgetCap;    // tope del stop financiado (0 = sin tope)
   double stopFlipH;        // horas operando solo el lado del movimiento que causo el stop/corte

   // --- V3: infraestructura ---
   int    telemetryKeep;    // filas de telemetria que se conservan en la BD viva
   double moneyScale;       // 100 en cuentas cent (USC), 1 en USD: escala los importes en moneda
   string eaName;           // nombre del experto (va a meta/eventos)
};

//==================================================================//
//  SNAPSHOT DE MERCADO (salida de MarketScanner, POD: sin strings)  //
//==================================================================//
struct SMarket
{
   // Precio / basicos
   double bid, ask, mid, spread, point;
   double tickValue, tickSize;

   // Tendencia / medias
   double ema20, ema50, ema100, ema200;
   double emaSlope;       // Pendiente EMA rapida (precio/barra)
   double priceSlope;     // Pendiente del precio (precio/barra)
   double priceVelocity;  // Velocidad de precio (precio/barra)

   // Fuerza / momentum
   double adx, plusDI, minusDI;
   double rsi, cci;
   double momentum;       // iMomentum - 100 (pct)
   double macdMain, macdSignal, macdHist;

   // Volatilidad
   double atr, atrAvg, atrRatio;   // atrRatio = atr / atrAvg
   double volatility;              // Desviacion de retornos (pct)
   double bbUpper, bbLower, bbMid, bbWidth;

   // Volumen
   double volume, volAvg;

   // VWAP (sesion diaria, calculado a mano)
   double vwap, vwapSlope, vwapDist;

   // Estructura de mercado (smart money simplificado)
   double swingHigh, swingLow;
   double fractalUp, fractalDn;
   bool   bosUp, bosDn;        // Break of Structure
   bool   liqSweepUp, liqSweepDn;
   bool   fvgUp, fvgDn;        // Fair Value Gap / imbalance
   double obBull, obBear;      // Order block (nivel, 0 si no hay)
   int    mstruct;             // ENUM_MSTRUCT

   bool   valid;               // true si el update fue exitoso
};

//==================================================================//
//  SCORES DE IA (todos 0-100)                                       //
//==================================================================//
struct SScores
{
   double trend;       // Confianza de tendencia
   int    trendDir;    // +1 alcista, -1 bajista, 0 neutral
   double momentum;
   double volatility;  // 0 = calmo, 100 = extremo
   double liquidity;   // Calidad de liquidez (spread/volumen)
   double risk;        // 0 = seguro, 100 = peligro
   double recovery;    // Presion de recuperacion (por DD)
   double quality;     // Calidad general del mercado para operar
   double confidence;  // Confianza compuesta para actuar
};

//==================================================================//
//  METRICAS DEL BASKET (salida de BasketManager, POD)               //
//==================================================================//
struct SBasket
{
   int    buys, sells, total;
   double lotsBuy, lotsSell, lotsTotal;
   double avgBuy, avgSell;         // Precio medio ponderado por lado
   double floating;                // PnL flotante total (moneda cuenta)
   double delta;                   // lotsBuy - lotsSell (exposicion neta)
   double breakevenBuy, breakevenSell;
   double recDistBuy, recDistSell; // Distancia a recuperacion (precio)
   double worstProfit;             // Peor PnL individual del basket
   ulong  worstTicket;             // Ticket de la peor posicion
   datetime oldestTime;            // apertura de la posicion mas antigua (edad real de la cesta)
};

//==================================================================//
//  PARAMETROS EN TIEMPO DE EJECUCION (los ajusta Risk/Recovery)     //
//==================================================================//
struct SRuntime
{
   double stepMult;      // Multiplicador del paso de grid
   double lotMult;       // Escala de lotaje (<=1 reduce)
   double martMult;      // Multiplicador martingala vigente
   double tpMult;        // Escala del TP del basket
   double trailMult;     // Escala del retroceso de trailing
   int    maxLevels;     // Tope de niveles vigente
   double exposureCap;   // Tope de lotes total vigente
   bool   allowNew;      // Permitir sembrar nuevos baskets
   bool   allowMart;     // Permitir promediar (adds martingala)
   bool   allowHedge;    // Permitir hedge inteligente
   int    recoveryLevel; // 0..6
};

//==================================================================//
//  TELEMETRIA COMPLETA (fila que alimenta el cockpit del panel)     //
//  Contiene un string (regimeName) -> NO usar ZeroMemory con ella.  //
//==================================================================//
struct STelemetry
{
   long   ts;
   int    regime;
   string regimeName;
   // Scores 0-100
   double trend;   int trendDir;
   double momentum, volatility, liquidity, risk, recovery, quality, confidence;
   // Sub-scores de riesgo 0-100
   double expScore, marginScore, floatScore, volScore, corrScore, ddScore;
   // Mercado
   double adx, atr, atrRatio, spread, rsi, ddpct;
   int    recLevel;
   // Cuenta / basket
   double equity, balance, floating;
   int    buys, sells;
   double lots, delta, step;
   // Interes compuesto
   double cmpGrowth;   // multiplicador vigente (1.0 = sin crecimiento)
   double cmpLot;      // lote base efectivo
   double cmpAnchor;   // capital de referencia
   double cmpNext;     // balance necesario para el proximo escalon
};

//==================================================================//
//  HELPERS MATEMATICOS / UTILES                                     //
//==================================================================//

// Restringe v al rango [lo, hi].
double Clamp(double v, double lo, double hi)
{
   if(v < lo) return lo;
   if(v > hi) return hi;
   return v;
}

// Mapea x del rango [inLo,inHi] a [outLo,outHi] con recorte.
double MapRange(double x, double inLo, double inHi, double outLo, double outHi)
{
   if(inHi - inLo == 0.0) return outLo;
   double t = (x - inLo) / (inHi - inLo);
   t = Clamp(t, 0.0, 1.0);
   return outLo + t * (outHi - outLo);
}

// Division segura (evita /0).
double SafeDiv(double a, double b, double fallback = 0.0)
{
   if(b == 0.0) return fallback;
   return a / b;
}

// Convierte una pendiente (precio/barra) a un score 0-100 usando ATR
// como escala natural del instrumento. dir devuelve el signo.
double SlopeToScore(double slope, double atr, int &dir)
{
   dir = (slope > 0) ? 1 : ((slope < 0) ? -1 : 0);
   double norm = SafeDiv(MathAbs(slope), (atr > 0 ? atr : 1.0)); // ~0..1+
   return Clamp(norm * 100.0, 0.0, 100.0);
}

// Normaliza un volumen al step/min/max del simbolo y al tope por orden.
double NormalizeVolume(const string sym, double lot, double maxOrder)
{
   double vmin  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   if(maxOrder > 0) lot = MathMin(lot, maxOrder);
   lot = MathMax(lot, vmin);
   if(vstep > 0) lot = MathFloor(lot / vstep) * vstep;
   lot = MathMin(lot, vmax);
   return NormalizeDouble(lot, 2);
}

#endif // TOKIO_UTILITIES_MQH
