//+------------------------------------------------------------------+
//| TokioXAU_SinLimites_V3.mq5                                       |
//| XAU sin salidas de emergencia ni techo de niveles (peticion)     |
//| Generado por build_v3.py - editar la plantilla, no este archivo  |
//+------------------------------------------------------------------+
#property copyright "Tokio Corporation"
#property version   "3.00"
#property description "XAU sin salidas de emergencia ni techo de niveles (peticion)"

#include "Core/Engine.mqh"

input group "=== 1. Ejecucion e Identidad ==="
input ulong           InpMagic             = 88920;   // Magic exclusivo
input string          InpSymbol            = "";   // Simbolo ("" = grafico)
input ENUM_TIMEFRAMES InpTF                = PERIOD_CURRENT;   // Timeframe de calculo (CURRENT = el del grafico)
input ulong           InpSlippage          = 30;   // Slippage (puntos)
input group "=== 2. Lotaje / Martingala ==="
input double          InpBaseLot           = 0.01;   // Lote base (nivel 1)
input double          InpMaxLotOrder       = 0.3;   // Tope de lote por orden
input int             InpMaxLevels         = 999;   // Niveles maximos por lado
input double          InpMaxTotalLots      = 1000.0;   // Exposicion maxima total (lotes)
input double          InpMartLow           = 1.35;   // Mult. martingala ATR bajo
input double          InpMartMed           = 1.25;   // Mult. martingala ATR medio
input double          InpMartHigh          = 1.15;   // Mult. martingala ATR alto
input double          InpMartXHigh         = 1.0;   // Mult. martingala ATR extremo
input int             InpMartMaxLevels     = 8;   // V3: niveles con martingala; despues lote plano (0=siempre)
input group "=== 3. Grid / persecucion del precio ==="
input bool            InpUseATRStep        = true;   // Paso por ATR
input double          InpATRMult           = 0.3;   // Paso = ATR * mult
input double          InpFixedStep         = 1.5;   // Paso fijo (precio, si ATR off)
input double          InpMinStep           = 0.2;   // Paso minimo (precio)
input double          InpStepGrowth        = 0.1;   // V3: crecimiento del paso por nivel (0.10 = +10%)
input bool            InpChaseInTrend      = true;   // V3: seguir promediando aunque el regimen sea tendencia
input double          InpAdverseStepMult   = 1.0;   // V3: paso extra con tendencia fuerte en contra (1 = igual)
input bool            InpAddConfirmM1      = false;   // V3: promediar solo tras micro-rebote M1
input double          InpMaxSpreadAdd      = 0.0;   // V3: spread max para promediar (precio, 0=sin limite)
input group "=== 4. Indicadores / filtros de entrada ==="
input int             InpATRPeriod         = 7;   // ATR
input int             InpATRAvgLB          = 50;   // Ventana ATR promedio
input double          InpRatchetArmPct     = 0.7;   // Trinquete: se arma al % del TP
input double          InpRatchetLock       = 0.5;   // Trinquete: % del pico protegido (0=off)
input double          InpMaxAtrRatioNew    = 1.157;   // No sembrar si ATR/ATRavg > esto (0=off)
input int             InpNoNewFromHour     = -1;   // V3: no sembrar desde hora servidor (-1=off)
input int             InpNoNewToHour       = -1;   // V3: ... hasta hora servidor (inclusive)
input int             InpEmaFast           = 20;   // EMA rapida
input int             InpEmaMed            = 50;   // EMA media
input int             InpEmaSlow           = 100;   // EMA lenta
input int             InpEmaTrend          = 200;   // EMA tendencia
input int             InpAdxPeriod         = 14;   // ADX
input int             InpRsiPeriod         = 14;   // RSI
input int             InpCciPeriod         = 14;   // CCI
input int             InpMacdFast          = 12;   // MACD fast
input int             InpMacdSlow          = 26;   // MACD slow
input int             InpMacdSignal        = 9;   // MACD signal
input int             InpBbPeriod          = 20;   // Bollinger periodo
input double          InpBbDev             = 2.0;   // Bollinger desviacion
input int             InpMomPeriod         = 14;   // Momentum
input int             InpVolLookback       = 20;   // Ventana volumen
input int             InpSwingLB           = 50;   // Ventana swings
input int             InpSlopeLB           = 5;   // Barras pendiente
input int             InpVelLB             = 5;   // Barras velocidad
input group "=== 5. Salidas (moneda de la cuenta; x100 automatico en cent) ==="
input double          InpBaseTP            = 5.0;   // TP base de la cesta
input double          InpTpAtrMult         = 0.5;   // Componente ATR del TP
input double          InpTpMin             = 2.0;   // Piso del TP
input double          InpTrailAct          = 4.0;   // Activar trailing a este profit
input double          InpTrailStep         = 1.5;   // Retroceso del trailing
input double          InpBePad             = 0.2;   // Colchon breakeven
input group "=== 5b. V3: desarme de cestas profundas ==="
input int             InpScalpFromLevel    = 0;   // TP individual desde este nivel por lado (0=off)
input double          InpScalpStepFrac     = 0.8;   // TP individual = fraccion del paso
input bool            InpPayDown           = false;   // Lo cobrado paga la peor posicion
input double          InpPayDownBuffer     = 0.5;   // Colchon que debe quedar al pagar (moneda)
input int             InpDeepLevels        = 0;   // Cesta profunda desde N posiciones: sale al breakeven (0=off)
input double          InpDeepTP            = 1.0;   // Objetivo de la cesta profunda (moneda)
input double          InpSurvivalDDPct     = 0.0;   // Supervivencia: cesta pierde >= % balance -> paso ancho, lote plano (0=off)
input double          InpSurvivalStepMult  = 2.0;   // Supervivencia: multiplicador del paso
input double          InpWinBoostStep      = 0.0;   // Anti-martingala: +x lote por cesta limpia ganada seguida (0=off)
input double          InpWinBoostMax       = 1.5;   // Anti-martingala: tope del multiplicador
input int             InpCleanWinLevels    = 6;   // Anti-martingala: ganancia limpia = cesta con <= N posiciones
input double          InpLockPct           = 0.0;   // Candado: cubrir la cesta si pierde >= % balance (0=off, no cierra)
input int             InpLockMinLevels     = 10;   // Candado: solo con >= N posiciones
input double          InpUnlockATR         = 3.0;   // Candado: quitar al rebotar N x ATR desde el extremo
input double          InpRelockStepPct     = 5.0;   // Candado: volver a cubrir si empeora otro % balance
input int             InpDeepStopLevels    = 0;   // Stop catastrofe: solo cestas con >= N posiciones (0=off)
input double          InpDeepStopPct       = 20.0;   // Stop catastrofe: ...que pierden >= % balance
input double          InpStopCooldownH     = 24.0;   // Stop catastrofe: horas sin cestas nuevas despues
input double          InpTimeCutMin        = 0.0;   // Corte por tiempo: vida maxima de la cesta en minutos (0=off)
input bool            InpTimeCutOnlyLoss   = false;   // Corte por tiempo: solo si va en perdida
input double          InpTimeCutPauseMin   = 0.0;   // Corte por tiempo: minutos sin cestas nuevas despues
input string          InpBlockHours        = "";   // Horas servidor sin cestas nuevas, ej. 23,0,1,2,3
input string          InpBlockDays         = "";   // Dias sin cestas nuevas 0=Dom..6=Sab, ej. 6
input group "=== 5c. V3: lado operado y stop por monto ==="
input int             InpSideMode          = 0;   // Lado: 0=ambos 1=solo compras 2=solo ventas 3=a favor de tendencia 4=contra tendencia
input int             InpSideLookbackH     = 4;   // Lado: tendencia = precio vs cierre H1 de hace N horas
input double          InpStopPauseMin      = 0.0;   // Stop de cesta: minutos sin cestas nuevas despues
input double          InpStopBudgetFrac    = 0.0;   // Stop financiado: stop = max(stop, fraccion x ganado desde el ultimo stop) (0=off)
input double          InpStopBudgetCap     = 0.0;   // Stop financiado: tope del stop (moneda, 0=sin tope)
input double          InpStopFlipH         = 0.0;   // Tras stop/corte: horas operando solo el lado del movimiento que lo causo (0=off)
input group "=== 6. Riesgo (0 = desactivado) ==="
input double          InpEquityStop        = 0.0;   // Cierre total por DD% de equity (0=off)
input double          InpDailyLoss         = 0.0;   // Sin cestas nuevas si DD diario % (0=off)
input double          InpMaxSpread         = 0.6;   // Spread max para SEMBRAR (precio)
input int             InpMinSecs           = 1;   // Segundos minimos entre entradas
input int             InpRestartSecs       = 2;   // Pausa tras cosecha
input double          InpMarginMin         = 0.0;   // Nivel de margen % minimo para entrar/promediar (0=off, nunca cierra)
input group "=== 6b. Cortacircuitos (0 = desactivado) ==="
input double          InpBrkMarginFloor    = 0.0;   // Margen % que fuerza CIERRE TOTAL (0=off)
input double          InpBrkMaxBasketMin   = 0.0;   // Minutos antes de recortar la peor (0=off)
input double          InpBrkStopAddPct     = 0.0;   // Flotante % balance que corta adds (0=off)
input group "=== 6c. Stop de cesta (0 = desactivado) ==="
input double          InpBasketStop        = 0.0;   // Perdida maxima por cesta (moneda, 0=off)
input int             InpMaxTotalLvl       = 0;   // Tope global de posiciones (0=off)
input double          InpBlockAddsAdx      = 0.0;   // ADX que bloquea adds contra tendencia (0=off)
input group "=== 7. Tendencia ==="
input double          InpTrendBlock        = 85.0;   // Confianza de tendencia "fuerte"
input double          InpAdxTrend          = 25.0;   // ADX minimo de tendencia
input double          InpAdxRange          = 18.0;   // ADX de rango
input group "=== 8. Recovery por DD% (0 = desactivado) ==="
input double          InpDD1               = 0.0;
input double          InpDD2               = 0.0;
input double          InpDD3               = 0.0;
input double          InpDD4               = 0.0;
input double          InpDD5               = 0.0;
input double          InpDD6               = 0.0;
input group "=== 9. Hedge ==="
input bool            InpUseHedge          = true;   // Hedge en tendencia (solo con recovery >= 2)
input double          InpHedgeLot          = 0.02;   // Lote de cobertura
input double          InpHedgeConf         = 80.0;   // Confianza minima
input group "=== 9b. Interes compuesto ==="
input bool            InpUseCompound       = false;   // ON/OFF
input double          InpCmpAnchor         = 1000.0;   // Capital donde lote = lote base
input double          InpCmpReinvest       = 1.0;   // Reinversion
input double          InpCmpMaxMult        = 10.0;   // Tope de crecimiento
input double          InpCmpMinMult        = 1.0;   // Piso
input double          InpCmpDDFloor        = 0.4;   // Freno por DD
input double          InpCmpHysteresis     = 0.1;   // Histeresis
input bool            InpCmpSmooth         = true;   // Continuo
input group "=== 9c. Sesion / fin de semana ==="
input bool            InpAvoidWeekend      = false;   // Respetar horario
input bool            InpWeekendFlatten    = false;   // Cerrar todo antes del fin de semana
input int             InpFriStopHour       = 22;
input int             InpFriFlattenHour    = 23;
input int             InpMonStartHour      = 2;
input int             InpSunResumeHour     = 0;
input group "=== 10. Telegram ==="
input bool            InpTelegram          = false;
input string          InpTgToken           = "";
input string          InpTgChat            = "";
input group "=== 11. Base de datos / telemetria ==="
input bool            InpUseDB             = true;
input string          InpDBName            = "TokioXAU_SinLimites_V3.sqlite";   // BD en Common\Files (se separa sola por cuenta)
input int             InpSnapshotSec       = 10;   // Curva de equity (seg)
input int             InpTelemetrySec      = 2;   // Cockpit (seg)
input int             InpTelemetryKeep     = 300000;   // Filas de telemetria conservadas
input double          InpMoneyScale        = 1.0;   // Escala manual de importes (1 = normal; en cuenta cent tambien 1)
input bool            InpLogCSV            = true;
input group "=== 12. Dashboard ==="
input bool            InpShowDash          = true;

CEngine g_engine;

SConfig BuildConfig()
{
   SConfig c;
   c.symbol = (InpSymbol == "") ? _Symbol : InpSymbol;
   c.tf     = (InpTF == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : InpTF;
   c.eaName = "TokioXAU_SinLimites_V3";
   c.magic = InpMagic;
   c.slippage = InpSlippage;
   c.baseLot = InpBaseLot;
   c.maxLotOrder = InpMaxLotOrder;
   c.maxLevels = InpMaxLevels;
   c.maxTotalLots = InpMaxTotalLots;
   c.martLow = InpMartLow;
   c.martMed = InpMartMed;
   c.martHigh = InpMartHigh;
   c.martXHigh = InpMartXHigh;
   c.martMaxLevels = InpMartMaxLevels;
   c.useATRStep = InpUseATRStep;
   c.atrMult = InpATRMult;
   c.fixedStep = InpFixedStep;
   c.minStep = InpMinStep;
   c.stepGrowth = InpStepGrowth;
   c.chaseInTrend = InpChaseInTrend;
   c.adverseStepMult = InpAdverseStepMult;
   c.addConfirmM1 = InpAddConfirmM1;
   c.maxSpreadAdd = InpMaxSpreadAdd;
   c.atrPeriod = InpATRPeriod;
   c.atrAvgLookback = InpATRAvgLB;
   c.ratchetArmPct = InpRatchetArmPct;
   c.ratchetLock = InpRatchetLock;
   c.maxAtrRatioNew = InpMaxAtrRatioNew;
   c.noNewFromHour = InpNoNewFromHour;
   c.noNewToHour = InpNoNewToHour;
   c.emaFast = InpEmaFast;
   c.emaMed = InpEmaMed;
   c.emaSlow = InpEmaSlow;
   c.emaTrend = InpEmaTrend;
   c.adxPeriod = InpAdxPeriod;
   c.rsiPeriod = InpRsiPeriod;
   c.cciPeriod = InpCciPeriod;
   c.macdFast = InpMacdFast;
   c.macdSlow = InpMacdSlow;
   c.macdSignal = InpMacdSignal;
   c.bbPeriod = InpBbPeriod;
   c.bbDev = InpBbDev;
   c.momPeriod = InpMomPeriod;
   c.volLookback = InpVolLookback;
   c.swingLookback = InpSwingLB;
   c.slopeLookback = InpSlopeLB;
   c.velLookback = InpVelLB;
   c.baseTP = InpBaseTP;
   c.tpAtrMult = InpTpAtrMult;
   c.tpMinUSD = InpTpMin;
   c.trailActUSD = InpTrailAct;
   c.trailStepUSD = InpTrailStep;
   c.bePad = InpBePad;
   c.scalpFromLevel = InpScalpFromLevel;
   c.scalpStepFrac = InpScalpStepFrac;
   c.payDown = InpPayDown;
   c.payDownBuffer = InpPayDownBuffer;
   c.deepLevels = InpDeepLevels;
   c.deepTP = InpDeepTP;
   c.survivalDDPct = InpSurvivalDDPct;
   c.survivalStepMult = InpSurvivalStepMult;
   c.winBoostStep = InpWinBoostStep;
   c.winBoostMax = InpWinBoostMax;
   c.cleanWinLevels = InpCleanWinLevels;
   c.lockPct = InpLockPct;
   c.lockMinLevels = InpLockMinLevels;
   c.unlockATR = InpUnlockATR;
   c.relockStepPct = InpRelockStepPct;
   c.deepStopLevels = InpDeepStopLevels;
   c.deepStopPct = InpDeepStopPct;
   c.stopCooldownH = InpStopCooldownH;
   c.timeCutMin = InpTimeCutMin;
   c.timeCutOnlyLoss = InpTimeCutOnlyLoss;
   c.timeCutPauseMin = InpTimeCutPauseMin;
   c.blockHours = InpBlockHours;
   c.blockDays = InpBlockDays;
   c.sideMode = InpSideMode;
   c.sideLookbackH = InpSideLookbackH;
   c.stopPauseMin = InpStopPauseMin;
   c.stopBudgetFrac = InpStopBudgetFrac;
   c.stopBudgetCap = InpStopBudgetCap;
   c.stopFlipH = InpStopFlipH;
   c.equityStopPct = InpEquityStop;
   c.dailyLossPct = InpDailyLoss;
   c.maxSpreadUSD = InpMaxSpread;
   c.minSecs = InpMinSecs;
   c.restartSecs = InpRestartSecs;
   c.marginMinLevel = InpMarginMin;
   c.brkMarginFloor = InpBrkMarginFloor;
   c.brkMaxBasketMin = InpBrkMaxBasketMin;
   c.brkStopAddPct = InpBrkStopAddPct;
   c.basketStopMoney = InpBasketStop;
   c.maxTotalLevels = InpMaxTotalLvl;
   c.blockAddsAdverseAdx = InpBlockAddsAdx;
   c.trendBlock = InpTrendBlock;
   c.adxTrend = InpAdxTrend;
   c.adxRange = InpAdxRange;
   c.dd1 = InpDD1;
   c.dd2 = InpDD2;
   c.dd3 = InpDD3;
   c.dd4 = InpDD4;
   c.dd5 = InpDD5;
   c.dd6 = InpDD6;
   c.useHedge = InpUseHedge;
   c.hedgeLot = InpHedgeLot;
   c.hedgeConf = InpHedgeConf;
   c.useCompound = InpUseCompound;
   c.compoundAnchor = InpCmpAnchor;
   c.compoundReinvest = InpCmpReinvest;
   c.compoundMaxMult = InpCmpMaxMult;
   c.compoundMinMult = InpCmpMinMult;
   c.compoundDDFloor = InpCmpDDFloor;
   c.compoundHysteresis = InpCmpHysteresis;
   c.compoundSmooth = InpCmpSmooth;
   c.avoidWeekend = InpAvoidWeekend;
   c.weekendFlatten = InpWeekendFlatten;
   c.friStopHour = InpFriStopHour;
   c.friFlattenHour = InpFriFlattenHour;
   c.monStartHour = InpMonStartHour;
   c.sunResumeHour = InpSunResumeHour;
   c.tg = InpTelegram;
   c.tgToken = InpTgToken;
   c.tgChat = InpTgChat;
   c.useDB = InpUseDB;
   c.dbName = InpDBName;
   c.snapSec = InpSnapshotSec;
   c.telSec = InpTelemetrySec;
   c.telemetryKeep = InpTelemetryKeep;
   c.moneyScale = InpMoneyScale;
   c.logCSV = InpLogCSV;
   c.showDash = InpShowDash;
   return c;
}

int OnInit()
{
   SConfig cfg = BuildConfig();
   if(!g_engine.Init(cfg)) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { g_engine.Deinit(reason); }

void OnTick() { g_engine.OnTick(); }
