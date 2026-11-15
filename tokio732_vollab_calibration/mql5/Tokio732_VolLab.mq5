#property strict
#property version "7.32"
#property description "7.32 r6 USD - lote y distancias por volatilidad. XAUUSD o BTCUSD. En vivo solo con LiveTradingEnabled=true."
#include <Trade/Trade.mqh>
enum TREND_SOURCE { TENDENCIA_PRINCIPAL=0,MICROTENDENCIA=1,AMBAS_DEBEN_COINCIDIR=2,PRINCIPAL_CON_RESPALDO_MICRO=3 };
input group "00 - Operativa real"
input bool LiveTradingEnabled=false;         // false = solo Probador; true = envia ordenes reales en el grafico
input bool RequireExnessBroker=false;        // true = solo cuentas Exness (comportamiento original)
enum ENTRY_CLOCK { HORA_SERVIDOR=0,UTC_DESDE_SERVIDOR_EET=1 };
input ENTRY_CLOCK EntryHourClock=HORA_SERVIDOR; // EntryHourFrom/To: hora del servidor, o UTC con servidor GMT+2/+3 (VT Markets)
input double ReferencePriceValueLotUSD=0;    // USD por 1.0 de precio y lote para el que se escribieron los lotes (0 = auto: oro 100, BTC 1)
input group "01 - Tendencia y microtendencia (barras cerradas)"
input TREND_SOURCE TrendSource=PRINCIPAL_CON_RESPALDO_MICRO;
input ENUM_TIMEFRAMES MainTimeframe=PERIOD_M6;
input int MainFastEMA=20;
input int MainSlowEMA=50;
input ENUM_TIMEFRAMES MicroTimeframe=PERIOD_M6;
input int MicroFastEMA=9;
input int MicroSlowEMA=21;
input bool UpdateTrendInsideBasket=true;
input group "02 - Lotes NETOS objetivo: compra menos venta"
input double LotsWithTrend=0.10;
input double LotsAgainstTrend=0.01;
input double PairedSeedLots=0.0;
input double LotMultiplier=1.0;
input bool ScaleLotsWithBalance=true;
input double ReferenceBalanceUSD=1000;
input group "03 - Separaciones en USD de PRECIO del simbolo (oro o bitcoin)"
input double CrossAboveCenter=220.0;
input double CrossBelowCenter=110.0;
input double MinMoveBetweenOrders=0.5;
input int MinSecondsBetweenOrders=1;
input double PyramidStep=0.0;
input double PyramidExtraLots=0.01;
input int MaxPyramidAdds=3;
input group "04 - Objetivo de beneficio y costes"
input double BasketProfitUSD=3.0;
input double ExtraCommissionRTperLot=0.0;
input double ExitSlippageReservePrice=0.50;
input group "05 - Topes opcionales: bloquean nuevas entradas, NO liquidan"
input double MaxGrossLots=0.0;
input double MaxNetLots=0.0;
input int MaxPositions=0;
input int RetrySecondsAfterRejection=5;
input group "06 - Laboratorio y registro"
input ulong MagicNumber=730202611;
input int DeviationPoints=1000;
input bool LogActions=true;


enum RESOLUTION_CLOCK { DESDE_PRIMERA_CESTA=0,ALINEADO_RELOJ_SERVIDOR=1 };
input group "07 - Resoluciones: reloj independiente del TP"
input bool ResolutionEnabled=false;
input int ResolutionMinutes=2;
input RESOLUTION_CLOCK ResolutionClock=DESDE_PRIMERA_CESTA;
input group "08 - Interruptores independientes: TP y stop monetario"
input bool ProfitTargetEnabled=false;
input bool CashStopEnabled=false;
input double CashStopUSD=5000.0;
input group "09 - Trailing sobre PnL neto TOTAL de la cesta"
input bool TrailingEnabled=true;
input double TrailArmUSD=50;
input double TrailGivebackUSD=2.0;
input double TrailFloorUSD=1.0;
input group "10 - Recuperacion: cortar la mala cesta durante el rebote"
input bool RecoveryEnabled=false;
input double RecoveryArmLossUSD=10.0;
input double RecoveryExitLossUSD=2.0;
input double RecoveryBounceUSD=5.0;
input group "11 - Identificador de informes"
input string RunTag="TOKIO_3614_T50";

// ---- LAB: ajuste por volatilidad. Apagado = identico al r6. Se mide al abrir la cesta y queda congelado en ella.
input group "40 - LAB volatilidad: lote y distancias segun ATR"
input bool VolLotEnabled=true;              // lote = lote normal / (ATR/ref)^gamma
input double VolLotGamma=1.0;
input bool VolDistEnabled=true;             // cruces, movimiento minimo, zona y trailing x (ATR/ref)
input double VolATRRef=4.74;                 // ATR14 H1 del simbolo para el que se diseno el SET (oro 4.74; bitcoin ver SET)
input int VolATRPeriod=14;
input ENUM_TIMEFRAMES VolATRTimeframe=PERIOD_H1;
input double VolFactorMin=0.25;
input double VolFactorMax=8.0;
double volFactorNow=1,volDist=1,volSum=0,volLo=0,volHi=0;
bool volReady=false;
datetime volBar=0;
int volBaskets=0;
double VolFactor732(){
 // ATR de Wilder sobre barras CERRADAS (sin mirar la barra en curso).
 if(!VolLotEnabled && !VolDistEnabled){volReady=true;return 1;}
 datetime b=iTime(_Symbol,VolATRTimeframe,0);
 if(b==volBar && volBar>0)return volFactorNow;
 MqlRates r[];int n=CopyRates(_Symbol,VolATRTimeframe,1,VolATRPeriod*20+2,r);
 if(n<VolATRPeriod+2){volReady=false;return 1;}   // historial insuficiente: EntryWindow732 no abre cestas (antes usaba factor 1)
 double a=0;int k=0;
 for(int i=1;i<n;i++){
  double trv=MathMax(r[i].high-r[i].low,MathMax(MathAbs(r[i].high-r[i-1].close),MathAbs(r[i].low-r[i-1].close)));
  if(k<VolATRPeriod){a+=trv;k++;if(k==VolATRPeriod)a/=VolATRPeriod;}else a=(a*(VolATRPeriod-1)+trv)/VolATRPeriod;
 }
 if(a<=0 || VolATRRef<=0){volReady=false;return 1;}
 volBar=b;volReady=true;volFactorNow=MathMin(VolFactorMax,MathMax(VolFactorMin,a/VolATRRef));return volFactorNow;
}
input group "41 - LAB colchon, trailing por lote, pausa y horario"
input bool CushionEnabled=true;             // lote fijo hasta Activate; por encima arriesga lo ganado sobre Base
input double CushionActivateUSD=1000000000;
input double CushionDeactivateUSD=3000;
input double CushionBaseUSD=3000;
input double CushionGain=1.0;
input bool TrailScaledWithLot=false;         // trailing en USD x (lote a favor / 0.10)
input int StopCooldownMinutes=240;             // pausa tras un stop de cesta
input double EntryHourFrom=0;                // hora servidor para ABRIR cestas
input double EntryHourTo=12.0;
input group "42 - LAB anti-atasco, interruptor y spread"
input bool RecenterAfterNewsClose=false;     // tras el cierre por noticias, centro y zonas = precio actual
input int FlatCloseMinutes=1440;               // >=0: cerrar la cesta N minutos despues de quedar solo con semillas
input int MaxBasketAgeMinutes=2880;             // cerrar la cesta al cumplir esta edad
input int IdleCloseMinutes=0;                // cerrar la cesta si no hay ordenes nuevas en este tiempo
input double MinVolFactor=2;                 // interruptor: no abrir cestas si ATR/ref es menor (oro tranquilo)
input double MaxEntrySpreadPrice=0;          // no abrir cesta con spread mayor
datetime flatSince=0;
bool cushionActive=false;
datetime cooldownUntil=0;
double trailMult=1;
int cushionSwitches=0;
double BaseScale732(){
 if(!CushionEnabled)return ConfiguredScale732();
 double bal=AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor-allExtra;
 if(!cushionActive && bal>=CushionActivateUSD){cushionActive=true;cushionSwitches++;}else if(cushionActive && bal<=CushionDeactivateUSD){cushionActive=false;cushionSwitches++;}
 double f=CushionBaseUSD/ReferenceBalanceUSD;if(cushionActive)f+=CushionGain*(bal-CushionBaseUSD)/ReferenceBalanceUSD;
 return LotMultiplier*MathMax(0,f);
}
datetime LastSundayUTC732(int year,int mon){
 // ultimo domingo del mes a las 01:00 UTC (cambio de horario europeo)
 MqlDateTime x;ZeroMemory(x);x.year=mon==12?year+1:year;x.mon=mon==12?1:mon+1;x.day=1;
 datetime t=StructToTime(x)-86400;MqlDateTime y;TimeToStruct(t,y);return t-y.day_of_week*86400+3600;
}
datetime EntryClockTime732(){
 datetime s=TimeCurrent();
 if(EntryHourClock==HORA_SERVIDOR)return s;
 datetime u=s-2*3600;MqlDateTime y;TimeToStruct(u,y);       // servidor EET: GMT+2 invierno, GMT+3 verano
 if(u>=LastSundayUTC732(y.year,3) && u<LastSundayUTC732(y.year,10))return s-3*3600;
 return u;
}
bool EntryWindow732(){
 if(TimeCurrent()<cooldownUntil)return false;
 double vfNow=VolFactor732();
 if(!volReady)return BlockDiag732("ESPERA_HISTORIAL_ATR","Historial insuficiente para el factor de volatilidad; no abre cestas");
 if(MinVolFactor>0 && vfNow<MinVolFactor)return false;
 if(MaxEntrySpreadPrice>0){MqlTick sq;if(SymbolInfoTick(_Symbol,sq) && sq.ask-sq.bid>MaxEntrySpreadPrice)return false;}
 if(EntryHourTo-EntryHourFrom>=24)return true;
 MqlDateTime d;TimeToStruct(EntryClockTime732(),d);double hr=d.hour+d.min/60.0+d.sec/3600.0;
 if(EntryHourFrom<=EntryHourTo)return hr>=EntryHourFrom && hr<EntryHourTo;
 return hr>=EntryHourFrom || hr<EntryHourTo;
}
double VolScale732(){double s=BaseScale732();if(VolLotEnabled && VolLotGamma>0)s*=MathPow(VolFactor732(),-VolLotGamma);return s;}

datetime resStart=0;
double resBalance=0,resExtra=0,allExtra=0,initialBalance=0,peakNet=0,maxGross=0,maxNet=0;
int cycleFile=INVALID_HANDLE,resFile=INVALID_HANDLE,cyclesClosed=0,resolutionsClosed=0,failedRequests=0;
long tickCount=0,skippedWindows=0;
bool pendingExit=false,hadPosition=false;
string exitReason="";

// Added modules are disabled by default. All decisions use current executable
// quotes or indicators from closed bars; no macro actual/revised values are read.
enum BIG_STOP_KIND { STOP_PRECIO=0,STOP_USD=1,STOP_ATR=2,STOP_PCT_EQUITY=3 };
input group "12 - Orden grande: identificacion y SL propio"
input double BigLegMinLots=0.01;
input bool ProtectOnlyWithTrend=false;
input bool BigStopEnabled=false;
input BIG_STOP_KIND BigStopKind=STOP_PRECIO;
input double BigStopPrice=2.0;
input double BigStopUSD=100.0;
input double BigStopATRMultiplier=1.0;
input double BigStopRiskPct=3.0;
input group "13 - Orden grande: BE, trailing y tiempo (independientes)"
input bool BigBEEnabled=false;
input double BigBETriggerPrice=2.0;
input double BigBEOffsetPrice=0.10;
input bool BigTrailEnabled=false;
input double BigTrailTriggerPrice=3.0;
input double BigTrailDistancePrice=1.0;
input double BigTrailStepPrice=0.10;
input int BigProtectionSeconds=1;
input bool BigAgeExitEnabled=false;
input int BigMaxAgeMinutes=15;
input int BigPauseAfterSLSeconds=60;
input double BigRearmMovePrice=0.0;
input group "14 - Noticias USD altas: fichero historico GMT+0"
input bool NewsFilterEnabled=false;
input int NewsBeforeMinutes=30;
input int NewsAfterMinutes=15;
input bool NewsOnlyBigOrders=true;
input bool NewsFailClosed=true;
input bool BigCloseBeforeNews=false;
input group "15 - Variante: solo nuevas zonas de entradas ejecutadas"
input bool NewZonesEnabled=true;
input double NewZonePaddingPrice=4.0;
input group "16 - Presupuesto de perdida de la cesta"
input bool CycleLossPctEnabled=true;
input double CycleLossPct=8;

double MoneyFactor=1,PriceValueLot=100;
double cycleRiskBaseUSD=0;
datetime newsFrom=0,newsTo=0,bigPauseUntil=0,lastProtection=0;
long newsTimes[];
bool newsReady=false,rearmPending=false;
double zoneHigh=0,zoneLow=0,bigExitMid=0;
int atrHandle=INVALID_HANDLE,bigOrders=0,bigSLHits=0,bigModifications=0,bigAgeCloses=0;
int blockedNews=0,blockedZones=0,blockedStop=0;
ulong bigPositionIDs[];
long lastBlockedTime=0;


input group "17 - SL grande y riesgo del libro residual"
input bool FlattenBasketAfterBigSL=false;
input group "18 - Lote por presupuesto restante de perdida (experimental)"
input bool RiskLotEnabled=false;
input double EntryRiskPct=2.0;
input double RiskExecutionReservePrice=0.50;
input group "19 - Reloj desde primera entrada direccional y ejecucion"
input bool BigClockEnabled=false;
input int BigClockSeconds=60;
input bool CloseLargestFirst=false;
input bool DirectionalClockOnlyWithTrend=true;
datetime firstDirectionalTime=0;
int riskCaps=0,riskBlocks=0,clockExits=0;
double riskSmallestLot=0;
double BudgetLotCap(double requested){
 if(!RiskLotEnabled)return requested;
 double dist=StopDistance(requested);
 if(dist<=0)return 0;
 double mark=(CycleRealizedNative732()+floating+swaps)/MoneyFactor-extraPaid;
 double budget=cycleRiskBaseUSD*EntryRiskPct/100+mark;
 double existing=MathAbs(buys-sells)*PriceValueLot*dist+(buys+sells)*(RiskExecutionReservePrice*PriceValueLot+ExtraCommissionRTperLot/2);
 double perLot=PriceValueLot*(dist+RiskExecutionReservePrice)+ExtraCommissionRTperLot;
 double cap=Quantize(MathMax(0,budget-existing)/perLot);
 if(cap<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8){riskBlocks++;return 0;}
 if(cap<requested-1e-8){riskCaps++;riskSmallestLot=riskSmallestLot==0?cap:MathMin(riskSmallestLot,cap);}
 return MathMin(requested,cap);
}

bool pendingBigBookExit=false;
CTrade tr;
int hf=INVALID_HANDLE,hs=INVALID_HANDLE,mf=INVALID_HANDLE,ms=INVALID_HANDLE,logfile=INVALID_HANDLE;
datetime mainBar=0,microBar=0,started=0,lastOrder=0;
int cachedTrend=0,basketTrend=0,priceSide=0,cycle=0,positions=0;
long retryAfter=0;
double buys=0,sells=0,floating=0,swaps=0,cycleBalance=0,extraPaid=0,center=0,lastFillMid=0,scale=1,cycleLow=0;
bool active=false,closing=false,seedComplete=false;

void Book(){
 buys=0;sells=0;floating=0;swaps=0;positions=0;
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t)continue;
  if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber)continue;
  double v=PositionGetDouble(POSITION_VOLUME);if(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)buys+=v;else sells+=v;
  floating+=PositionGetDouble(POSITION_PROFIT);swaps+=PositionGetDouble(POSITION_SWAP);positions++;
 }
 maxGross=MathMax(maxGross,buys+sells);maxNet=MathMax(maxNet,MathAbs(buys-sells));
}
double Liquidatable(){
 return (CycleRealizedNative732()+floating+swaps)/MoneyFactor-extraPaid
 -(buys+sells)*(ExtraCommissionRTperLot/2+ExitSlippageReservePrice*PriceValueLot);
}
int Direction(int a,int b){
 double x[1],y[1];ResetLastError();int nx=CopyBuffer(a,0,1,1,x),ny=CopyBuffer(b,0,1,1,y);
 if(nx!=1 || ny!=1 || !MathIsValidNumber(x[0]) || !MathIsValidNumber(y[0]) || x[0]==EMPTY_VALUE || y[0]==EMPTY_VALUE){
  diagEMAError=GetLastError();diagEMAReady=false;SetDiag732("ESPERA_DATOS_EMA", "EMA sin datos: CopyBuffer="+(string)nx+"/"+(string)ny+" error="+(string)diagEMAError);return 0;
 }
 if(a==hf){diagMainFast=x[0];diagMainSlow=y[0];}else{diagMicroFast=x[0];diagMicroSlow=y[0];}
 return x[0]>y[0]?1:(x[0]<y[0]?-1:0);
}
int GetTrend(){
 datetime a=iTime(_Symbol,MainTimeframe,0),b=iTime(_Symbol,MicroTimeframe,0);
 if(a==mainBar && b==microBar && cachedTrend!=0)return cachedTrend;
 mainBar=a;microBar=b;diagEMAReady=true;diagEMAError=0;int main=Direction(hf,hs),micro=Direction(mf,ms),d=0;
 if(TrendSource==TENDENCIA_PRINCIPAL)d=main;
 else if(TrendSource==MICROTENDENCIA)d=micro;
 else if(TrendSource==AMBAS_DEBEN_COINCIDIR)d=(main==micro?main:0);
 else d=main!=0?main:micro;
 cachedTrend=d;return d;
}
void Log(string action,uint code=0){
 if(logfile==INVALID_HANDLE)return;
 FileWrite(logfile,cycle,(long)TimeCurrent(),action,basketTrend,priceSide,center,buys,sells,CycleRealizedNative732(),floating,swaps,extraPaid,Liquidatable(),cycleLow,code);
 FileFlush(logfile);
}
bool Confirmed(){liveLedgerDirty=true;liveStateDirty=true;uint r=tr.ResultRetcode();return r==TRADE_RETCODE_DONE || r==TRADE_RETCODE_DONE_PARTIAL;}
bool CanRequest(){MqlTick t;return SymbolInfoTick(_Symbol,t) && t.time_msc>=retryAfter;}
void Rejected(){diagRetcode=tr.ResultRetcode();SetDiag732("RECHAZO_BROKER",tr.ResultRetcodeDescription());Print("732 rechazo: ",diagRetcode," ",diagDetail);failedRequests++;MqlTick t;SymbolInfoTick(_Symbol,t);retryAfter=t.time_msc+1000*(long)MathMax(1,RetrySecondsAfterRejection);Log("RECHAZO",tr.ResultRetcode());}
double Quantize(double v){double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);return NormalizeDouble(MathFloor((v+1e-9)/step)*step,8);}
bool Send(int side,double volume,string why){
 if(!MQLInfoInteger(MQL_TESTER) && !LiveTradingEnabled)return false;
 if(!CanRequest())return false;Book();double v=Quantize(volume);
 if(StringFind(why,"SEMILLA_")!=0 && RecycleNetEnabled && TryRecycle732(side,v))return true;
 if(StringFind(why,"SEMILLA_")!=0)v=BudgetLotCap(v);
 if(v<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8)return BlockDiag732("LOTE_INFERIOR_MINIMO", "Lote calculado="+DoubleToString(v,8)+"; minimo="+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),8));
 if(MaxGrossLots>0 && buys+sells+v>MaxGrossLots+1e-8)return BlockDiag732("TOPE_BRUTO", "Se alcanzo MaxGrossLots");
 if(MaxNetLots>0 && MathAbs(buys-sells+side*v)>MaxNetLots+1e-8)return BlockDiag732("TOPE_NETO", "Se alcanzo MaxNetLots");
 if(MaxPositions>0 && positions>=MaxPositions)return BlockDiag732("TOPE_POSICIONES", "Se alcanzo MaxPositions");
 v=MathMin(v,SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX));
 double stop=0;string comment=why;if(!NewOrderGuard(side,v,why,stop,comment))return false;
 bool ok=side>0?tr.Buy(v,_Symbol,0,stop,0,comment):tr.Sell(v,_Symbol,0,stop,0,comment);
 if(!ok || !Confirmed()){Rejected();return false;}
 SetDiag732("ORDEN_CONFIRMADA",why+" volumen="+DoubleToString(tr.ResultVolume(),2));diagRetcode=tr.ResultRetcode();After730Entry(why,comment);ChargeExtra(tr.ResultVolume());hadPosition=true;lastOrder=TimeCurrent();
 MqlTick t;SymbolInfoTick(_Symbol,t);lastFillMid=(t.bid+t.ask)/2;Book();Log(why);return true;
}
void ChargeExtra(double volume){double c=volume*ExtraCommissionRTperLot/2;extraPaid+=c;resExtra+=c;allExtra+=c;}
void BeginResolution(){
 if(!ResolutionEnabled || resStart>0)return;
 int secs=ResolutionMinutes*60;datetime now=TimeCurrent();
 resStart=ResolutionClock==ALINEADO_RELOJ_SERVIDOR?(datetime)(((long)now/secs)*secs):now;
 resBalance=AccountInfoDouble(ACCOUNT_BALANCE);resExtra=0;
}
bool ResolutionDue(){return ResolutionEnabled && resStart>0 && TimeCurrent()>=resStart+ResolutionMinutes*60;}
void AdvanceResolution(){
 if(!ResolutionDue() || positions>0)return;
 int secs=ResolutionMinutes*60;long passed=MathMax(1,(long)(TimeCurrent()-resStart)/secs);
 resolutionsClosed++;skippedWindows+=passed-1;
 if(resFile!=INVALID_HANDLE){FileWrite(resFile,resolutionsClosed,(long)resStart,(long)(resStart+secs),(long)TimeCurrent(),(AccountInfoDouble(ACCOUNT_BALANCE)-resBalance)/MoneyFactor-resExtra,passed-1);FileFlush(resFile);}
 resStart+=(datetime)(passed*secs);resBalance=AccountInfoDouble(ACCOUNT_BALANCE);resExtra=0;
}
void FinishCycle(string why){
 double net=(CycleRealizedNative732())/MoneyFactor-extraPaid;
 LiveBasket732(why,net);cyclesClosed++;if((why=="STOP_PCT_CESTA" || why=="EDAD_MAXIMA" || why=="INACTIVA") && StopCooldownMinutes>0)cooldownUntil=TimeCurrent()+StopCooldownMinutes*60;
 if(cycleFile!=INVALID_HANDLE){FileWrite(cycleFile,cycle,(long)started,(long)TimeCurrent(),why,net,cycleLow,peakNet,(long)resStart,(long)(resStart+ResolutionMinutes*60));FileFlush(cycleFile);}
 ResetInventory732();firstDirectionalTime=0;pendingBigBookExit=false;Log("FIN_"+why);active=false;pendingExit=false;closing=false;seedComplete=false;hadPosition=false;exitReason="";
}
void RequestExit(string why){pendingExit=true;exitReason=why;Log("ORDEN_SALIDA_"+why);}
void FlattenPending(){
 // Latched exit; recompute the chosen ticket after every actual close.
 int remaining=PositionsTotal();
 for(int n=0;n<remaining;n++){
  if(!CanRequest())break;
  if(BasketExitCloseByEnabled){if(BasketExitNeutralizeNetFirst && (SymbolInfoInteger(_Symbol,SYMBOL_ORDER_MODE)&SYMBOL_ORDER_CLOSEBY)!=0){int reduced=NeutralizeExitNet732();if(reduced<0)break;if(reduced>0)continue;}int paired=ExitCloseByStep732();if(paired<0)break;if(paired>0)continue;}
  ulong chosen=0;double largest=-1;
  for(int i=PositionsTotal()-1;i>=0;i--){
   ulong t=PositionGetTicket(i);if(!t)continue;
   if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber)continue;
   double v=PositionGetDouble(POSITION_VOLUME);
   if(!CloseLargestFirst){chosen=t;break;}
   if(v>largest){largest=v;chosen=t;}
  }
  if(!chosen)break;
  if(!tr.PositionClose(chosen) || !Confirmed()){Rejected();break;}
  ChargeExtra(tr.ResultVolume());Book();Log("EJECUTA_"+exitReason);
 }
 Book();if(positions==0){FinishCycle(exitReason);AdvanceResolution();}
}
string ExitSignal(double net){
 if(ResolutionDue())return "RESOLUCION";
 if(hazardLatched)return "DETERIORO_INVENTARIO";
 if(BigClockEnabled && firstDirectionalTime>0 && TimeCurrent()-firstDirectionalTime>=BigClockSeconds){clockExits++;return "RELOJ_DIRECCIONAL";}
 bool cash=CashStopEnabled;
 bool trail=TrailingEnabled;
 bool recovery=RecoveryEnabled;
 if(CycleLossPctEnabled && net<=-cycleRiskBaseUSD*CycleLossPct/100)return "STOP_PCT_CESTA";
 if(MaxBasketAgeMinutes>0 && TimeCurrent()-started>=MaxBasketAgeMinutes*60)return "EDAD_MAXIMA";
 if(FlatCloseMinutes>=0 && flatSince>0 && TimeCurrent()-flatSince>=FlatCloseMinutes*60)return "SOLO_SEMILLAS";
 if(IdleCloseMinutes>0 && lastOrder>0 && TimeCurrent()-lastOrder>=IdleCloseMinutes*60)return "INACTIVA";
 if(cash && CashStopUSD>0 && net<=-CashStopUSD)return "STOP_USD";
 if(ProfitTargetEnabled && net>=BasketProfitUSD)return "TP";
 if(trail && peakNet>=TrailArmUSD*trailMult && net<=MathMax(TrailFloorUSD*trailMult,peakNet-TrailGivebackUSD*trailMult))return "TRAIL";
 if(recovery && cycleLow<=-RecoveryArmLossUSD && net>=-RecoveryExitLossUSD && net-cycleLow>=RecoveryBounceUSD)return "RECUPERACION";
 return "";
}
int EngineInit732(){
 NormalizeMoneyInputs732();bootstrapRetryable=false;diagInitError=0;
 if((BigClockEnabled && BigClockSeconds<1) || RiskExecutionReservePrice<0 || EntryRiskPct<=0)return InvalidParameters732();
 if(RiskLotEnabled && (!BigStopEnabled || (BigStopKind!=STOP_PRECIO && BigStopKind!=STOP_ATR)))return InvalidParameters732();
 if(BigLegMinLots<=0 || NewsBeforeMinutes<0 || NewsAfterMinutes<0 || NewZonePaddingPrice<0 || BigProtectionSeconds<0 || BigTrailStepPrice<0)return InvalidParameters732();
 if(BigStopEnabled && (BigStopPrice<=0 || BigStopUSD<=0 || BigStopATRMultiplier<=0 || BigStopRiskPct<=0))return InvalidParameters732();
 if((BigBEEnabled && (BigBETriggerPrice<=0 || BigBEOffsetPrice<0)) || (BigTrailEnabled && (BigTrailTriggerPrice<=0 || BigTrailDistancePrice<=0)) || (BigAgeExitEnabled && BigMaxAgeMinutes<=0))return InvalidParameters732();
 if(!CheckAccount732())return INIT_FAILED;
 if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING){SetDiag732("ERROR_CUENTA_NETTING","Se requiere cuenta hedging");return INIT_FAILED;}if(!Init730())return INIT_FAILED;
 if((ResolutionEnabled && (ResolutionMinutes<1 || ResolutionMinutes>525600))
 || (CashStopEnabled && CashStopUSD<=0)
 || (TrailingEnabled && (TrailArmUSD<=0 || TrailGivebackUSD<=0 || TrailFloorUSD<0 || TrailFloorUSD>TrailArmUSD))
 || (RecoveryEnabled && (RecoveryArmLossUSD<=0 || RecoveryExitLossUSD<0 || RecoveryExitLossUSD>=RecoveryArmLossUSD || RecoveryBounceUSD<0)))return InvalidParameters732();
 if(LotsWithTrend<=0 || LotsAgainstTrend<=0 || PairedSeedLots<0 || LotMultiplier<=0 || (ProfitTargetEnabled && BasketProfitUSD<=0) || ReferenceBalanceUSD<=0 || CrossAboveCenter<0 || CrossBelowCenter<0 || MainFastEMA<1 || MainSlowEMA<1 || MicroFastEMA<1 || MicroSlowEMA<1)return InvalidParameters732();
 hf=iMA(_Symbol,MainTimeframe,MainFastEMA,0,MODE_EMA,PRICE_CLOSE);hs=iMA(_Symbol,MainTimeframe,MainSlowEMA,0,MODE_EMA,PRICE_CLOSE);
 mf=iMA(_Symbol,MicroTimeframe,MicroFastEMA,0,MODE_EMA,PRICE_CLOSE);ms=iMA(_Symbol,MicroTimeframe,MicroSlowEMA,0,MODE_EMA,PRICE_CLOSE);
 if(hf==INVALID_HANDLE || hs==INVALID_HANDLE || mf==INVALID_HANDLE || ms==INVALID_HANDLE){FatalBootstrap732("ERROR_INDICADORES","No se pueden crear las EMA configuradas",GetLastError());return INIT_FAILED;}
 initialBalance=AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor;
 if(!InitInventory732())return InvalidParameters732();
 cycleFile=FileOpen(RunTag+"_cycles.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 resFile=FileOpen(RunTag+"_resolutions.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 if(cycleFile==INVALID_HANDLE || resFile==INVALID_HANDLE){FatalBootstrap732("ERROR_ARCHIVOS_LOCALES","No se puede abrir el registro de cestas/resoluciones",GetLastError());return INIT_FAILED;}
 FileWrite(cycleFile,"cycle","start","end","reason","net","MAE","MFE","resolution_start","scheduled_end");
 FileWrite(resFile,"resolution","start","scheduled_end","actual_end","net","skipped_windows");
 tr.SetExpertMagicNumber(MagicNumber);tr.SetAsyncMode(false);tr.SetTypeFillingBySymbol(_Symbol);tr.SetDeviationInPoints(DeviationPoints);
 if(LogActions){logfile=FileOpen(RunTag+"_actions.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(logfile!=INVALID_HANDLE)FileWrite(logfile,"cycle","time","action","trend","price_side","center","buy","sell","realized","floating","swap","extra_paid","liquidatable","MAE","retcode");}
 if(!LiveInit732())return INIT_FAILED;
 return INIT_SUCCEEDED;
}
void StrategyTick732(){

 MqlTick t;if(!SymbolInfoTick(_Symbol,t) || t.bid<=0 || t.ask<t.bid){SetDiag732("ESPERA_COTIZACION", "Todavia no hay bid/ask valido para este simbolo");return;}
 tickCount++;double mid=(t.bid+t.ask)/2;Book();UpdateInventoryHealth732();
 if(active){if(pendingBigBookExit && FlattenBasketAfterBigSL && !pendingExit)RequestExit("SL_GRANDE_CESTA");double net=Liquidatable();cycleLow=MathMin(cycleLow,net);peakNet=MathMax(peakNet,net);
  if(hadPosition && positions==0){FinishCycle("CIERRE_EXTERNO");AdvanceResolution();return;}
  if(!pendingExit){string signal=ExitSignal(net);if(signal!="")RequestExit(signal);}
  if(pendingExit){FlattenPending();return;}
 }
 if(active && ManageInventory732())return;
 if(!active){AdvanceResolution();}
 int trend=GetTrend();
 
 ManageBigPositions();Book();
 if(!CanRequest()){SetDiag732("ESPERA_REINTENTO", "Esperando cotizacion o pausa tras rechazo");return;}
 if(!active){
  if(trend==0){if(diagEMAReady)SetDiag732("SIN_SENAL", "EMA iguales o tendencias no coinciden; aun no se inicia cesta");return;}
  if(!EntryWindow732())return;
  if(!MigrationEntryReady732() || !CalendarEntryReady732() || !CheckStartingLots732(VolScale732()))return;
  SetDiag732("INICIA_CESTA", "Senal confirmada; preparando semillas");pendingBigBookExit=false;cycleRiskBaseUSD=AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor-allExtra;zoneHigh=mid;zoneLow=mid;BeginResolution();active=true;peakNet=0;hadPosition=false;cycle++;started=TimeCurrent();cycleBalance=AccountInfoDouble(ACCOUNT_BALANCE);BeginLedger732();extraPaid=0;cycleLow=0;ResetInventory732();center=mid;lastFillMid=mid;lastOrder=0;basketTrend=trend;priceSide=trend;seedComplete=false;scale=VolScale732();
  flatSince=0;double vf=VolFactor732();volDist=VolDistEnabled?vf:1;trailMult=volDist*(TrailScaledWithLot?TargetLots732(LotsWithTrend,scale)/0.10:1);volBaskets++;volSum+=vf;volLo=volLo==0?vf:MathMin(volLo,vf);volHi=MathMax(volHi,vf);
 }
 if(!seedComplete){
  // Complete each seed side from actual filled volume; never duplicate a filled leg.
  double seed=TargetLots732(PairedSeedLots,scale);
  if(seed>0){if(buys<seed-1e-8){if(!Send(1,seed-buys,"SEMILLA_BUY"))return;}Book();if(sells<seed-1e-8){if(!Send(-1,seed-sells,"SEMILLA_SELL"))return;}}
  Book();seedComplete=true;SetDiag732("CESTA_ACTIVA", "Semillas completadas; gestionando delta");Log("SEMILLA_CONFIRMADA");
 }
 if(UpdateTrendInsideBasket && trend!=0)basketTrend=trend;
 if(StrictNewZonesEnabled){if(mid>=zoneHigh+NewZonePaddingPrice)priceSide=1;else if(mid<=zoneLow-NewZonePaddingPrice)priceSide=-1;}
 else{if(mid>=center+CrossAboveCenter*volDist)priceSide=1;else if(mid<=center-CrossBelowCenter*volDist)priceSide=-1;}
 if(TimeCurrent()-lastOrder<MinSecondsBetweenOrders || (MinMoveBetweenOrders>0 && MathAbs(mid-lastFillMid)<MinMoveBetweenOrders*volDist)){SetDiag732("ESPERA_DISTANCIA", "Esperando tiempo minimo o movimiento entre ordenes");return;}
 bool withTrend=priceSide==basketTrend;
 double size=withTrend?LotsWithTrend:LotsAgainstTrend;
 if(withTrend && PyramidStep>0 && MaxPyramidAdds>0){double barrier=priceSide>0?CrossAboveCenter:CrossBelowCenter;int n=(int)MathFloor(MathMax(0,priceSide*(mid-center)-barrier)/PyramidStep);size+=MathMin(n,MaxPyramidAdds)*PyramidExtraLots;}
 double desired=priceSide*TargetLots732(size,scale),difference=desired-(buys-sells);
 if(MathAbs(difference)>=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8)Send(difference>0?1:-1,MathAbs(difference),withTrend?"DELTA_A_FAVOR":"DELTA_EN_CONTRA");else if(positions==0 && MathAbs(desired)<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8)SetDiag732("LOTES_REDONDEADOS_A_CERO", "Objetivo sin volumen ejecutable; revisar ScaleLotsWithBalance y LotMultiplier");else SetDiag732("DELTA_CUBIERTO", "Exposicion neta ya coincide con objetivo; no hace falta otra orden");
}
double OnTester(){Refresh730SyntheticCost();Book();return AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor-initialBalance-allExtra;}
void OnDeinit(const int reason){LiveDeinit732(reason);if(inventoryFile!=INVALID_HANDLE)FileClose(inventoryFile);Refresh730SyntheticCost();
 Book();if(active)Log("FIN_TEST_LIQUIDACION_PROBADOR");
 Print("732VOL cestas=",volBaskets," factor_medio=",DoubleToString(volBaskets>0?volSum/volBaskets:0,3)," min=",DoubleToString(volLo,3)," max=",DoubleToString(volHi,3)," cerradas=",cyclesClosed," max_bruto=",DoubleToString(maxGross,2)," lote=",VolLotEnabled," dist=",VolDistEnabled," colchon_cambios=",cushionSwitches);
 int f=FileOpen(RunTag+"_summary.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');
 if(f!=INVALID_HANDLE){FileWrite(f,"ticks","cycles","resolutions","broker_net","synthetic_paid","adjusted_net","open_positions","max_gross","max_net","failed_requests","skipped_windows");FileWrite(f,tickCount,cyclesClosed,resolutionsClosed,AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor-initialBalance,allExtra,AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor-initialBalance-allExtra,positions,maxGross,maxNet,failedRequests,skippedWindows);FileClose(f);}
 if(logfile!=INVALID_HANDLE)FileClose(logfile);if(cycleFile!=INVALID_HANDLE)FileClose(cycleFile);if(resFile!=INVALID_HANDLE)FileClose(resFile);
 if(hf!=INVALID_HANDLE)IndicatorRelease(hf);if(hs!=INVALID_HANDLE)IndicatorRelease(hs);if(mf!=INVALID_HANDLE)IndicatorRelease(mf);if(ms!=INVALID_HANDLE)IndicatorRelease(ms);
}

// Native tester receives an explicit historical calendar file.
#property tester_file "news_usd_high_2025_2026.bin"
#property tester_file "news_usd_high_2022_2026_LAB.bin"
input group "43 - LAB calendario de noticias 2022-2026"
input bool LabLongCalendar=true;            // LAB: calendario 2022-2026 para pruebas de anos anteriores
// Initialization may wait for broker data. Waiting never submits an order.
bool bootstrapPending=false,bootstrapRetryable=false,bootstrapStopped=false;
int bootstrapAttempts=0,diagInitError=0;
datetime bootstrapLastAttempt=0;
int InvalidParameters732(){bootstrapRetryable=false;SetDiag732("ERROR_PARAMETROS","Combinacion de Entradas invalida; revisar parametros de los metodos activados");return INIT_PARAMETERS_INCORRECT;}
bool WaitBootstrap732(string state,string detail,int error=0){
 bootstrapRetryable=true;diagInitError=error;SetDiag732(state,detail+"; error="+(string)error);return false;
}
bool FatalBootstrap732(string state,string detail,int error=0){
 bootstrapRetryable=false;diagInitError=error;SetDiag732(state,detail+"; error="+(string)error);Print("732 INIT ",state," | ",diagDetail);return false;
}
bool ReadCalendar732(string filename){
 newsReady=false;ArrayResize(newsTimes,0);ResetLastError();
 int f=FileOpen(filename,FILE_READ|FILE_BIN);
 if(f==INVALID_HANDLE)return FatalBootstrap732("ERROR_ARCHIVO_NOTICIAS","No se puede leer "+filename,GetLastError());
 if(FileSize(f)<24){FileClose(f);return FatalBootstrap732("ERROR_CALENDARIO","Archivo de noticias incompleto");}
 newsFrom=(datetime)FileReadLong(f);newsTo=(datetime)FileReadLong(f);int count=FileReadInteger(f);int offset=FileReadInteger(f);
 bool valid=count>0 && count<200000 && offset==0 && newsTo>newsFrom && FileSize(f)>=(ulong)(24+8*(long)count);
 if(valid)valid=FileReadArray(f,newsTimes,0,count)==(uint)count;
 FileClose(f);
 if(!valid)return FatalBootstrap732("ERROR_CALENDARIO","Formato o longitud de calendario invalida");
 newsReady=true;return true;
}
bool CalibrateUnits732(MqlTick &q){
 string currency=AccountInfoString(ACCOUNT_CURRENCY);
 if(currency!="USD" && currency!="USC")return FatalBootstrap732("ERROR_MONEDA","Solo USD o USC");
 MoneyFactor=currency=="USC"?100.0:1.0;
 if(q.bid<=0 || q.ask<=0 || q.ask<q.bid || q.time<=0)return WaitBootstrap732("ESPERA_COTIZACION","Esperando bid/ask valido del servidor");
 double minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),contract=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE),maximum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
 if(minimum<=0 || step<=0 || contract<=0 || maximum<minimum)return WaitBootstrap732("ESPERA_ESPECIFICACIONES","Esperando minimo, maximo, paso y contrato del simbolo");
 // Use a legal probe volume even when the broker's maximum is below one lot.
 double volume=MathMin(1.0,maximum);
 volume=MathMax(minimum,MathFloor((volume+1e-9)/step)*step);
 ResetLastError();double profit=0;
 if(!OrderCalcProfit(ORDER_TYPE_BUY,_Symbol,volume,q.ask,q.ask+1,profit))return WaitBootstrap732("ESPERA_VALOR_CONTRATO","OrderCalcProfit aun no disponible",GetLastError());
 if(!MathIsValidNumber(profit) || profit<=0)return WaitBootstrap732("ESPERA_VALOR_CONTRATO","El servidor aun no devuelve valor positivo del contrato");
 PriceValueLot=profit/(MoneyFactor*volume);
 if(currency=="USD" && SymbolInfoString(_Symbol,SYMBOL_CURRENCY_PROFIT)=="USD")PriceValueLot=contract;
 bootstrapRetryable=false;diagInitError=0;return true;
}
bool Init730(){
 bootstrapRetryable=false;diagInitError=0;
 if(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))return WaitBootstrap732("ESPERA_CONEXION","Esperando conexion con el broker");
 if(!SymbolSelect(_Symbol,true))return WaitBootstrap732("ESPERA_SIMBOLO","Esperando activacion del simbolo en Market Watch",GetLastError());
 ResetLastError();MqlTick q;if(!SymbolInfoTick(_Symbol,q))return WaitBootstrap732("ESPERA_COTIZACION","SymbolInfoTick aun no disponible",GetLastError());
 if(!CalibrateUnits732(q))return false;
 if(BigStopEnabled && BigStopKind==STOP_ATR && atrHandle==INVALID_HANDLE){atrHandle=iATR(_Symbol,MainTimeframe,14);if(atrHandle==INVALID_HANDLE)return WaitBootstrap732("ESPERA_ATR","ATR aun no disponible",GetLastError());}
 if(NewsFilterEnabled || BigCloseBeforeNews){
  if(!MQLInfoInteger(MQL_TESTER) && LiveEconomicCalendarEnabled){
   // Failure is a read-only wait state, not a reason to abandon open positions.
   RefreshLiveCalendar732(true);bootstrapRetryable=false;
  }else if(!ReadCalendar732(LabLongCalendar?"news_usd_high_2022_2026_LAB.bin":"news_usd_high_2025_2026.bin")){
   if(NewsFailClosed)return false;
   Print("732: calendario no disponible; NewsFailClosed=false fue elegido en Entradas.");bootstrapRetryable=false;
  }
 }
 Print("732_UNITS currency=",AccountInfoString(ACCOUNT_CURRENCY)," factor=",MoneyFactor," USD_price_value_per_lot=",PriceValueLot," lot_conversion=",LotConversion732()," news_ready=",newsReady);
 return true;
}
void CleanupPartialInit732(){
 if(logfile!=INVALID_HANDLE){FileClose(logfile);logfile=INVALID_HANDLE;}
 if(cycleFile!=INVALID_HANDLE){FileClose(cycleFile);cycleFile=INVALID_HANDLE;}
 if(resFile!=INVALID_HANDLE){FileClose(resFile);resFile=INVALID_HANDLE;}
 if(inventoryFile!=INVALID_HANDLE){FileClose(inventoryFile);inventoryFile=INVALID_HANDLE;}
 if(hf!=INVALID_HANDLE){IndicatorRelease(hf);hf=INVALID_HANDLE;}
 if(hs!=INVALID_HANDLE){IndicatorRelease(hs);hs=INVALID_HANDLE;}
 if(mf!=INVALID_HANDLE){IndicatorRelease(mf);mf=INVALID_HANDLE;}
 if(ms!=INVALID_HANDLE){IndicatorRelease(ms);ms=INVALID_HANDLE;}
 if(atrHandle!=INVALID_HANDLE){IndicatorRelease(atrHandle);atrHandle=INVALID_HANDLE;}
}
void RetryBootstrap732(){
 if(!bootstrapPending || TimeLocal()-bootstrapLastAttempt<2)return;
 bootstrapLastAttempt=TimeLocal();bootstrapAttempts++;
 int code=EngineInit732();
 if(code==INIT_SUCCEEDED){bootstrapPending=false;bootstrapStopped=false;SetDiag732("ESPERA_PRIMER_TICK","Datos de contrato listos; esperando tick y senal");Print("732: inicializacion completada tras reintento ",bootstrapAttempts);}
 else if(!bootstrapRetryable){bootstrapPending=false;bootstrapStopped=true;CleanupPartialInit732();if(diagState=="INICIALIZANDO")SetDiag732("ERROR_INICIALIZACION","Codigo="+(string)code+"; error="+(string)GetLastError());}
 Dashboard732();
}

bool InNewsWindow(){return KnownNewsAt732(CalendarNow732());}

bool IsBigRequest(double v,string why){return v>=BigLegMinLots-1e-8 && (!ProtectOnlyWithTrend || why=="DELTA_A_FAVOR");}
bool IsProtectedPosition(){return StringFind(PositionGetString(POSITION_COMMENT),"730B_")==0;}
double StopDistance(double volume){
 if(BigStopKind==STOP_PRECIO)return BigStopPrice;
 if(BigStopKind==STOP_USD)return BigStopUSD/(volume*PriceValueLot);
 if(BigStopKind==STOP_PCT_EQUITY)return MathMax(0,AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor-allExtra)*BigStopRiskPct/100/(volume*PriceValueLot);
 double a[1];if(atrHandle==INVALID_HANDLE || CopyBuffer(atrHandle,0,1,1,a)!=1)return 0;
 return a[0]*BigStopATRMultiplier;
}
bool NewOrderGuard(int side,double v,string why,double &stop,string &comment){
 stop=0;comment=why;if(!MigrationEntryReady732() || !CalendarEntryReady732())return false;MqlTick q;SymbolInfoTick(_Symbol,q);double mid=(q.bid+q.ask)/2;
 bool seed=StringFind(why,"SEMILLA_")==0,big=!seed && (RiskLotEnabled || IsBigRequest(v,why));
 if(!EntryAllowed732(side,v))return false;
 if(RecenterAfterNewsClose && !seed && InNewsWindow())return false;
 if(!seed && (NewZonesEnabled || StrictNewZonesEnabled) && ((side>0 && mid<zoneHigh+NewZonePaddingPrice*volDist) || (side<0 && mid>zoneLow-NewZonePaddingPrice*volDist))){blockedZones++;return BlockDiag732("ZONA_YA_EXPLORADA","Espera precio fuera de la frontera de entradas y su separacion configurada");}
 if(((NewsFilterEnabled && (!NewsOnlyBigOrders || big)) || (BlockReentryDuringNews && BigCloseBeforeNews && big)) && InNewsWindow()){blockedNews++;return BlockDiag732("VENTANA_NOTICIAS","Entrada bloqueada dentro de una ventana USD de alta importancia");}
 if(big){
  if(TimeCurrent()<bigPauseUntil)return BlockDiag732("PAUSA_TRAS_SL","Esperando pausa posterior al stop de una orden");
  if(rearmPending && BigRearmMovePrice>0 && MathAbs(mid-bigExitMid)<BigRearmMovePrice)return false;
  if(BigStopEnabled){
   double dist=StopDistance(v),tick=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double minDist=SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*SymbolInfoDouble(_Symbol,SYMBOL_POINT)+tick;
   if(dist<=0 || dist<q.ask-q.bid+minDist){blockedStop++;return false;}
   stop=side>0?MathFloor((q.ask-dist)/tick)*tick:MathCeil((q.bid+dist)/tick)*tick;
  }
  comment="730B_"+why;
 }
 return true;
}
void After730Entry(string why,string comment){
 AfterEntry732(why);
 MqlTick q;SymbolInfoTick(_Symbol,q);double mid=(q.bid+q.ask)/2;
 if(StringFind(why,"SEMILLA_")!=0){if(firstDirectionalTime==0 && (!DirectionalClockOnlyWithTrend || why=="DELTA_A_FAVOR"))firstDirectionalTime=TimeCurrent();double filled=StrictNewZonesEnabled && tr.ResultPrice()>0?tr.ResultPrice():mid;zoneHigh=MathMax(zoneHigh,filled);zoneLow=MathMin(zoneLow,filled);flatSince=0;}
 if(StringFind(comment,"730B_")==0){
  bigOrders++;rearmPending=false;
  ulong d=tr.ResultDeal();if(HistoryDealSelect(d)){ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);int n=ArraySize(bigPositionIDs);ArrayResize(bigPositionIDs,n+1);bigPositionIDs[n]=id;}
 }
}
void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result){liveLedgerDirty=true;liveStateDirty=true;
 if(trans.type!=TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))return;
 if(HistoryDealGetInteger(trans.deal,DEAL_MAGIC)!=(long)MagicNumber || HistoryDealGetString(trans.deal,DEAL_SYMBOL)!=_Symbol)return;
 if(HistoryDealGetInteger(trans.deal,DEAL_REASON)!=DEAL_REASON_SL)return;
 ChargeExtra(HistoryDealGetDouble(trans.deal,DEAL_VOLUME));
 ulong id=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);bool ours=false;
 for(int i=0;i<ArraySize(bigPositionIDs);i++)if(bigPositionIDs[i]==id){ours=true;break;}
 if(!ours)return;
 bigSLHits++;if(FlattenBasketAfterBigSL)pendingBigBookExit=true;bigPauseUntil=TimeCurrent()+BigPauseAfterSLSeconds;MqlTick q;SymbolInfoTick(_Symbol,q);bigExitMid=(q.bid+q.ask)/2;rearmPending=true;
}
void ManageBigPositions(){
 if(!BigBEEnabled && !BigTrailEnabled && !BigAgeExitEnabled && !BigCloseBeforeNews)return;
 MqlTick q;SymbolInfoTick(_Symbol,q);double tick=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
 for(int i=PositionsTotal()-1;i>=0;i--){
  ulong ticket=PositionGetTicket(i);if(!ticket)continue;
  if(PositionGetString(POSITION_SYMBOL)!=_Symbol || PositionGetInteger(POSITION_MAGIC)!=(long)MagicNumber || !IsProtectedPosition())continue;
  int side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;
  double entry=PositionGetDouble(POSITION_PRICE_OPEN),old=PositionGetDouble(POSITION_SL),volume=PositionGetDouble(POSITION_VOLUME);
  double close=side>0?q.bid:q.ask,gain=side*(close-entry),desired=old;
  bool age=BigAgeExitEnabled && TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME)>=BigMaxAgeMinutes*60;
  if(age || (BigCloseBeforeNews && InNewsWindow())){
   if(!CanRequest())return;
   if(tr.PositionClose(ticket) && Confirmed()){ChargeExtra(tr.ResultVolume());bigAgeCloses++;Book();Log(age?"BIG_TIEMPO":"BIG_PRE_NOTICIA");if(!age){flatSince=TimeCurrent();if(RecenterAfterNewsClose){double rm=(q.bid+q.ask)/2;center=rm;zoneHigh=rm;zoneLow=rm;lastFillMid=rm;}}}
   else Rejected();
   continue;
  }
  if(TimeCurrent()-lastProtection<BigProtectionSeconds)continue;
  if(BigBEEnabled && gain>=BigBETriggerPrice){double target=entry+side*BigBEOffsetPrice;if(old==0 || side*(target-desired)>0)desired=target;}
  if(BigTrailEnabled && gain>=BigTrailTriggerPrice){double target=close-side*BigTrailDistancePrice;if(desired==0 || side*(target-desired)>0)desired=target;}
  if(desired==0 || (old>0 && side*(desired-old)<MathMax(tick,BigTrailStepPrice)))continue;
  desired=side>0?MathFloor(desired/tick)*tick:MathCeil(desired/tick)*tick;
  double minDist=MathMax(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL),SymbolInfoInteger(_Symbol,SYMBOL_TRADE_FREEZE_LEVEL))*SymbolInfoDouble(_Symbol,SYMBOL_POINT)+tick;
  if(side*(close-desired)<=minDist || !CanRequest())continue;
  if(tr.PositionModify(ticket,desired,0) && Confirmed()){bigModifications++;lastProtection=TimeCurrent();}else Rejected();
 }
}
void Refresh730SyntheticCost(){
 if(!MQLInfoInteger(MQL_TESTER))return;
 if(ExtraCommissionRTperLot<=0){allExtra=0;return;}
 if(!HistorySelect(0,TimeCurrent()+86400))return;
 double volume=0;
 for(int i=0;i<HistoryDealsTotal();i++){ulong d=HistoryDealGetTicket(i);long type=HistoryDealGetInteger(d,DEAL_TYPE);if((type==DEAL_TYPE_BUY || type==DEAL_TYPE_SELL) && HistoryDealGetString(d,DEAL_SYMBOL)==_Symbol)volume+=HistoryDealGetDouble(d,DEAL_VOLUME);}
 allExtra=volume*ExtraCommissionRTperLot/2;
}

// 7.32: inventory controls. All activation switches default to false.
input group "20 - Rebalancear cerrando: evita sumar otra cobertura"
input bool RecycleNetEnabled=false;
input bool RecycleFarthestFirst=true;
input bool RecyclePreserveSeeds=true;
input group "21 - Entradas solo fuera de fronteras ejecutadas"
input bool StrictNewZonesEnabled=false;
input group "22 - Recortar N posiciones PERDEDORAS mas lejanas"
input bool TimedLosingTrimEnabled=false;
input double LosingTrimMinutes=5.0;
input int TimedTrimCount=1;
input bool OnEntryLosingTrimEnabled=false;
input int OnEntryTrimCount=1;
input double TrimMaxLotsPerPosition=0.0;
input int TrimMinAgeSeconds=60;
input double TrimMinLossUSD=1.0;
input bool TrimOnlyNegativeBasket=true;
input bool TrimNetExposureGuard=true;
input double TrimMaxAbsNetLots=0.0;
input int TrimPauseSeconds=60;
input double TrimRearmDistancePrice=2.0;
input group "23 - Pareado financiado: ganadora + perdedora con CloseBy"
input bool FundedPairTrimEnabled=false;
input double FundedPairMinutes=5.0;
input int FundedPairCount=1;
input double FundedPairMinNetUSD=0.50;
input double FundedPairCostBufferUSD=0.50;
input group "24 - Saturacion de inventario: pausa o liquidacion explicita"
input bool InventoryGuardEnabled=false;
input int InventoryMaxPositions=20;
input double InventoryMaxGrossLots=1.0;
input double InventoryMaxHedgeRatio=20.0;
input double InventoryDebtUSD=100.0;
input bool InventoryGuardFlatten=false;
input group "25 - Salida por deterioro observado: NO predice el futuro"
input bool HazardExitEnabled=false;
input int HazardWindowSeconds=300;
input int HazardMinEntries=6;
input double HazardGrossGrowthLots=0.30;
input double HazardWorsenUSD=50.0;
input double HazardMinLossUSD=100.0;
input group "26 - Auditoria de equity, deuda y recortes"
input bool InventoryLogEnabled=false;
int inventoryFile=INVALID_HANDLE,recycleCloses=0,loserTrims=0,fundedPairs=0;
int inventoryBlocks=0,exposureBlocks=0,pairUnsupported=0,hazardExits=0;
int maxInventoryPositions=0,trimPending=0,pairPending=0,windowEntries=0;
datetime inventoryPauseUntil=0,lastTimedTrim=0,lastPairTrim=0,windowStart=0;
double trimRearmMid=0,windowGross=0,windowNet=0;
bool trimRearm=false,onEntryTrimPending=false,hazardLatched=false;
ulong lastInventoryEntryID=0,trimVisited[];
string trimCause="";

bool OurPosition732(){return PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==(long)MagicNumber;}
bool IsSeed732(){return StringFind(PositionGetString(POSITION_COMMENT),"SEMILLA_")>=0;}
double PositionNet732(){return (PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP))/MoneyFactor;}
void Audit732(string why,double equityBefore,double netBefore){
 if(inventoryFile==INVALID_HANDLE)return;
 Book();FileWrite(inventoryFile,(long)TimeCurrent(),cycle,why,positions,buys,sells,(CycleRealizedNative732())/MoneyFactor,floating/MoneyFactor,swaps/MoneyFactor,Liquidatable(),equityBefore,AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor,netBefore,buys-sells);FileFlush(inventoryFile);
}
void ResetInventory732(){
 trimPending=0;pairPending=0;onEntryTrimPending=false;hazardLatched=false;
 lastTimedTrim=TimeCurrent();lastPairTrim=TimeCurrent();windowStart=TimeCurrent();
 windowGross=buys+sells;windowNet=0;windowEntries=0;ArrayResize(trimVisited,0);lastInventoryEntryID=0;
 // Cooldown and rearm survive basket reset, so emptying inventory cannot bypass them.
}
bool InitInventory732(){
 if(LosingTrimMinutes<=0 || FundedPairMinutes<=0 || TimedTrimCount<1 || OnEntryTrimCount<1 || FundedPairCount<1 || TimedTrimCount>1000 || OnEntryTrimCount>1000 || FundedPairCount>1000 || TrimMaxLotsPerPosition<0 || TrimMinAgeSeconds<0 || TrimMinLossUSD<0 || TrimMaxAbsNetLots<0 || TrimPauseSeconds<0 || TrimRearmDistancePrice<0 || FundedPairMinNetUSD<0 || FundedPairCostBufferUSD<0 || HazardWindowSeconds<1 || HazardMinEntries<1 || HazardGrossGrowthLots<0 || HazardWorsenUSD<0 || HazardMinLossUSD<0)return false;
 if(InventoryMaxPositions<0 || InventoryMaxGrossLots<0 || InventoryMaxHedgeRatio<0 || InventoryDebtUSD<0)return false;
 if(InventoryLogEnabled){inventoryFile=FileOpen(RunTag+"_inventory.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,',');if(inventoryFile==INVALID_HANDLE)return false;
 FileWrite(inventoryFile,"time","cycle","action","positions","buy","sell","realized","floating","swap","liquidatable","equity_before","equity_after","net_before","net_after");}
 return true;
}
bool InventoryBreach732(){
 if(!InventoryGuardEnabled)return false;
 double gross=buys+sells,step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
 if(InventoryMaxPositions>0 && positions>=InventoryMaxPositions)return true;
 if(InventoryMaxGrossLots>0 && gross>=InventoryMaxGrossLots-1e-8)return true;
 return InventoryMaxHedgeRatio>0 && gross/MathMax(MathAbs(buys-sells),step)>=InventoryMaxHedgeRatio && Liquidatable()<=-InventoryDebtUSD;
}
bool EntryAllowed732(int side,double volume){
 MqlTick q;SymbolInfoTick(_Symbol,q);double mid=(q.bid+q.ask)/2;
 if(TimeCurrent()<inventoryPauseUntil){inventoryBlocks++;return BlockDiag732("PAUSA_INVENTARIO","Esperando pausa despues de recortar posiciones");}
 if(trimRearm && TrimRearmDistancePrice>0){if(MathAbs(mid-trimRearmMid)<TrimRearmDistancePrice){inventoryBlocks++;return BlockDiag732("ESPERA_REARME","Falta desplazamiento despues del recorte");}trimRearm=false;}
 if(InventoryBreach732()){inventoryBlocks++;return BlockDiag732("TOPE_INVENTARIO","Se alcanzo un limite de posiciones, lotes o cobertura");}
 return true;
}
void AfterInventoryClose732(){
 inventoryPauseUntil=TimeCurrent()+TrimPauseSeconds;MqlTick q;SymbolInfoTick(_Symbol,q);
 trimRearmMid=(q.bid+q.ask)/2;trimRearm=TrimRearmDistancePrice>0;
}
bool CloseVolume732(ulong ticket,double requested){
 if(!CanRequest() || !PositionSelectByTicket(ticket) || !OurPosition732())return false;
 double volume=PositionGetDouble(POSITION_VOLUME),v=Quantize(MathMin(volume,requested));
 if(v<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8)return false;
 double eq=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor,delta=buys-sells;
 bool ok=v>=volume-1e-8?tr.PositionClose(ticket):tr.PositionClosePartial(ticket,v);
 if(!ok || !Confirmed()){Rejected();return false;}
 ChargeExtra(tr.ResultVolume());Book();Audit732("CIERRE_PARCIAL_O_TOTAL",eq,delta);return true;
}
bool TryRecycle732(int side,double requested){
 if(!RecycleNetEnabled)return false;
 ulong chosen=0;double metric=-1;MqlTick q;SymbolInfoTick(_Symbol,q);
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || !OurPosition732())continue;
  int s=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;
  if(s==side || (RecyclePreserveSeeds && IsSeed732()))continue;
  double value=RecycleFarthestFirst?MathAbs((s>0?q.bid:q.ask)-PositionGetDouble(POSITION_PRICE_OPEN)):(double)(TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME));
  if(value>metric){metric=value;chosen=t;}
 }
 if(!chosen)return false;
 // A failed recycle must NEVER fall through into opening another hedge.
 if(CloseVolume732(chosen,requested)){recycleCloses++;lastOrder=TimeCurrent();SymbolInfoTick(_Symbol,q);lastFillMid=(q.bid+q.ask)/2;Log("RECICLA_EN_VEZ_DE_ABRIR");}
 return true;
}
void AfterEntry732(string why){
 if(StringFind(why,"SEMILLA_")==0)return;
 windowEntries++;
 ulong d=tr.ResultDeal();if(HistoryDealSelect(d))lastInventoryEntryID=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);
 if(OnEntryLosingTrimEnabled)onEntryTrimPending=true;
}
void UpdateInventoryHealth732(){
 maxInventoryPositions=MathMax(maxInventoryPositions,positions);
 if(!HazardExitEnabled || !active)return;
 if(windowStart==0){windowStart=TimeCurrent();windowGross=buys+sells;windowNet=Liquidatable();windowEntries=0;return;}
 if(TimeCurrent()-windowStart<HazardWindowSeconds)return;
 double now=Liquidatable();
 if(windowEntries>=HazardMinEntries && buys+sells-windowGross>=HazardGrossGrowthLots && now-windowNet<=-HazardWorsenUSD && now<=-HazardMinLossUSD){hazardLatched=true;hazardExits++;Audit732("DETERIORO_OBSERVADO",AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor,buys-sells);}
 windowStart=TimeCurrent();windowGross=buys+sells;windowNet=now;windowEntries=0;
}
bool VisitedTrim732(ulong id){for(int i=0;i<ArraySize(trimVisited);i++)if(trimVisited[i]==id)return true;return false;}
bool TrimOneLoser732(){
 if(TrimOnlyNegativeBasket && Liquidatable()>=0)return false;
 ulong chosen=0,idChosen=0;double far=-1,vChosen=0;MqlTick q;SymbolInfoTick(_Symbol,q);
 double bound=TrimMaxAbsNetLots>0?TrimMaxAbsNetLots:MathMax(LotsWithTrend,LotsAgainstTrend)*scale;
 bound=MathMax(bound,MathAbs(buys-sells));
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || !OurPosition732())continue;
  ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
  if(VisitedTrim732(id) || (id==lastInventoryEntryID && TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME)<MathMax(1,TrimMinAgeSeconds)) || TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME)<TrimMinAgeSeconds || PositionNet732()>=-TrimMinLossUSD)continue;
  int s=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;double v=PositionGetDouble(POSITION_VOLUME);
  if(TrimMaxLotsPerPosition>0)v=Quantize(MathMin(v,TrimMaxLotsPerPosition));
  if(v<SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)-1e-8)continue;
  if(TrimNetExposureGuard && MathAbs(buys-sells-s*v)>bound+1e-8){exposureBlocks++;continue;}
  double distance=MathAbs((s>0?q.bid:q.ask)-PositionGetDouble(POSITION_PRICE_OPEN));
  if(distance>far){far=distance;chosen=t;idChosen=id;vChosen=v;}
 }
 if(!chosen)return false;
 if(!CloseVolume732(chosen,vChosen))return false;
 int n=ArraySize(trimVisited);ArrayResize(trimVisited,n+1);trimVisited[n]=idChosen;
 loserTrims++;AfterInventoryClose732();Log(trimCause);return true;
}
bool TryFundedPair732(){
 if((SymbolInfoInteger(_Symbol,SYMBOL_ORDER_MODE)&SYMBOL_ORDER_CLOSEBY)==0){pairUnsupported++;return false;}
 MqlTick q;SymbolInfoTick(_Symbol,q);ulong loser=0,winner=0;double bestFar=-1;
 for(int i=PositionsTotal()-1;i>=0;i--){ulong a=PositionGetTicket(i);if(!a || !OurPosition732())continue;
  if(((ulong)PositionGetInteger(POSITION_IDENTIFIER)==lastInventoryEntryID && TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME)<MathMax(1,TrimMinAgeSeconds)) || PositionNet732()>=-TrimMinLossUSD || TimeCurrent()-(datetime)PositionGetInteger(POSITION_TIME)<TrimMinAgeSeconds)continue;
  int sa=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;double va=PositionGetDouble(POSITION_VOLUME),pa=PositionNet732();
  double distance=MathAbs((sa>0?q.bid:q.ask)-PositionGetDouble(POSITION_PRICE_OPEN));
  if(distance<=bestFar)continue;
  for(int j=PositionsTotal()-1;j>=0;j--){ulong b=PositionGetTicket(j);if(!b || b==a || !OurPosition732())continue;
   int sb=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;
   if(sa==sb || PositionNet732()<=0)continue;
   double vb=PositionGetDouble(POSITION_VOLUME),v=MathMin(va,vb);
   double estimated=pa*v/va+PositionNet732()*v/vb-v*ExtraCommissionRTperLot-FundedPairCostBufferUSD;
   if(estimated<FundedPairMinNetUSD)continue;
   loser=a;winner=b;bestFar=distance;break;
  }
 }
 if(!loser || !winner || !CanRequest())return false;
 double gross=buys+sells,delta=buys-sells,eq=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor;
 if(!tr.PositionCloseBy(loser,winner) || !Confirmed()){Rejected();return false;}
 Book();ChargeExtra(MathMax(0,gross-buys-sells));fundedPairs++;AfterInventoryClose732();Audit732("PAREADO_FINANCIADO_CLOSEBY",eq,delta);Log("PAREADO_FINANCIADO");return true;
}
bool ManageInventory732(){
 if(!active || positions==0)return false;
 if(InventoryBreach732() && InventoryGuardFlatten){RequestExit("SATURACION_INVENTARIO");FlattenPending();return true;}
 if(trimPending>0){
  if(!CanRequest())return true;
  if(TrimOneLoser732())trimPending--;else trimPending=0;
  return true;
 }
 if(pairPending>0){
  if(!CanRequest())return true;
  if(TryFundedPair732())pairPending--;else pairPending=0;
  return true;
 }
 if(OnEntryLosingTrimEnabled && onEntryTrimPending){onEntryTrimPending=false;trimPending=OnEntryTrimCount;trimCause="RECORTE_TRAS_ENTRADA";ArrayResize(trimVisited,0);return true;}
 if(TimedLosingTrimEnabled && TimeCurrent()-lastTimedTrim>=LosingTrimMinutes*60){lastTimedTrim=TimeCurrent();trimPending=TimedTrimCount;trimCause="RECORTE_PERIODICO";ArrayResize(trimVisited,0);return true;}
 if(FundedPairTrimEnabled && TimeCurrent()-lastPairTrim>=FundedPairMinutes*60){lastPairTrim=TimeCurrent();pairPending=FundedPairCount;return true;}
 return false;
}

input group "27 - Cierre TOTAL coordinado: CloseBy antes del neto residual"
input bool BasketExitCloseByEnabled=false;
int exitCloseByPairs=0;
int ExitCloseByStep732(){
 if((SymbolInfoInteger(_Symbol,SYMBOL_ORDER_MODE)&SYMBOL_ORDER_CLOSEBY)==0)return 0;
 ulong buy=0,sell=0;double bv=0,sv=0;
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || !OurPosition732())continue;
  double v=PositionGetDouble(POSITION_VOLUME);
  if(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY){if(v>bv){bv=v;buy=t;}}
  else if(v>sv){sv=v;sell=t;}
 }
 if(!buy || !sell)return 0;
 double gross=buys+sells,delta=buys-sells,eq=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor;
 if(!tr.PositionCloseBy(buy,sell) || !Confirmed()){Rejected();return -1;}
 Book();ChargeExtra(MathMax(0,gross-buys-sells));exitCloseByPairs++;Audit732("SALIDA_TOTAL_CLOSEBY",eq,delta);return 1;
}

input group "28 - Salida total: neutralizar neto antes de desmontar pares"
input bool BasketExitNeutralizeNetFirst=false;
int NeutralizeExitNet732(){
 double delta=buys-sells,step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
 if(MathAbs(delta)<step/2)return 0;
 ulong chosen=0;double largest=0;
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || !OurPosition732())continue;
  int side=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?1:-1;
  double v=PositionGetDouble(POSITION_VOLUME);
  if(side*delta>0 && v>largest){largest=v;chosen=t;}
 }
 if(!chosen)return 0;
 double eq=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor;
 if(!CloseVolume732(chosen,MathMin(largest,MathAbs(delta))))return -1;
 Audit732("NEUTRALIZA_NETO_SALIDA_TOTAL",eq,delta);return 1;
}

#define RELEASE_CURRENCY "USD"
#define RELEASE_MODE "USD"
#define MINIMUM_SCALED_DEFAULT false
void NormalizeMoneyInputs732(){}
// Core accounting stays in real USD. Public CENT money inputs/display are USC.
input group "30 - Minimo de lotes escalados (regla explicita)"
input bool UseMinimumForScaledLots=false;
double DisplayFactor732(){return MoneyFactor;}
string DisplayCurrency732(){return MoneyFactor==100.0?"USC":"USD";}
double DisplayMoney732(double usd){return usd*DisplayFactor732();}
double ScaleFactorMath732(double balance_native,double money_factor,double costs_usd,double reference_usd,double multiplier,bool enabled){
 if(!enabled)return multiplier;
 if(reference_usd<=0 || money_factor<=0 || !MathIsValidNumber(reference_usd) || !MathIsValidNumber(balance_native))return 0;
 return multiplier*(MathMax(0,balance_native/money_factor-costs_usd)/reference_usd);
}
double QuantizeScaledMath732(double raw,double minimum,double step,bool use_minimum){
 if(!MathIsValidNumber(raw) || raw<=0 || minimum<=0 || step<=0)return 0;
 double v=NormalizeDouble(MathFloor((raw+1e-9)/step)*step,8);
 if(v<minimum-1e-8)return use_minimum?minimum:0;
 return v;
}
double LotConversion732(){
 double ref=ReferencePriceValueLotUSD>0?ReferencePriceValueLotUSD:(StringFind(_Symbol,"BTCUSD")==0?1.0:100.0);
 return PriceValueLot>0?ref/PriceValueLot:1.0;
}
double TargetLots732(double base,double factor){
 return QuantizeScaledMath732(base*factor*LotConversion732(),SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),ScaleLotsWithBalance && UseMinimumForScaledLots);
}
int MinimumLegs732(double factor){
 if(!ScaleLotsWithBalance || !UseMinimumForScaledLots)return 0;
 double min=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);int n=0;
 if(LotsWithTrend*factor>0 && Quantize(LotsWithTrend*factor)<min-1e-8)n++;
 if(LotsAgainstTrend*factor>0 && Quantize(LotsAgainstTrend*factor)<min-1e-8)n++;
 if(PairedSeedLots*factor>0 && Quantize(PairedSeedLots*factor)<min-1e-8)n++;
 return n;
}

// Live calendar uses MT5 trade-server timestamps. Tester retains frozen events.
input group "31 - Noticias: calendario y comprobaciones de cuenta"
input bool LiveEconomicCalendarEnabled=true;
input bool BlockNewEntriesWithOtherTokioMagic=true;
input bool BlockReentryDuringNews=true;
datetime lastLiveCalendarAttempt=0,lastLiveCalendarSuccess=0;
int liveCalendarError=0;
string calendarSource732="HISTORICO";
datetime CalendarNow732(){
 if(MQLInfoInteger(MQL_TESTER))return TimeCurrent();
 datetime t=TimeTradeServer();return t>0?t:TimeCurrent();
}
bool CalendarCoveredAt732(datetime when){return newsReady && when>=newsFrom && when<newsTo;}
bool KnownNewsAt732(datetime when){
 if(!CalendarCoveredAt732(when))return false;
 long low=(long)when-(long)NewsAfterMinutes*60,high=(long)when+(long)NewsBeforeMinutes*60;
 int a=0,b=ArraySize(newsTimes);while(a<b){int k=(a+b)/2;if(newsTimes[k]<low)a=k+1;else b=k;}
 return a<ArraySize(newsTimes) && newsTimes[a]<=high;
}
bool RefreshLiveCalendar732(bool force=false){
 if(MQLInfoInteger(MQL_TESTER) || !LiveEconomicCalendarEnabled || (!NewsFilterEnabled && !BigCloseBeforeNews))return true;
 calendarSource732="MT5_EN_VIVO";datetime now=CalendarNow732();
 if(!force && now-lastLiveCalendarAttempt<(liveCalendarError==0?60:30))return CalendarCoveredAt732(now);
 lastLiveCalendarAttempt=now;
 if(!TerminalInfoInteger(TERMINAL_CONNECTED)){liveCalendarError=1;return false;}
 MqlCalendarValue values[];datetime from=now-86400,to=now+7*86400;ResetLastError();
 int n=CalendarValueHistory(values,from,to,NULL,"USD");
 if(n<0){liveCalendarError=GetLastError();SetDiag732("ESPERA_CALENDARIO_VIVO","Calendario no disponible; aperturas bloqueadas, sin cierres por datos ausentes");return false;}
 long upcoming[];int count=0;
 for(int i=0;i<n;i++){
  MqlCalendarEvent event;ResetLastError();
  if(!CalendarEventById(values[i].event_id,event)){liveCalendarError=GetLastError();return false;}
  if(event.importance!=CALENDAR_IMPORTANCE_HIGH || values[i].time<=0)continue;
  ArrayResize(upcoming,count+1);upcoming[count++]=(long)values[i].time;
 }
 ArraySort(upcoming);ArrayCopy(newsTimes,upcoming);ArrayResize(newsTimes,count);
 newsFrom=from;newsTo=to;newsReady=true;liveCalendarError=0;lastLiveCalendarSuccess=now;
 Print("732 calendario vivo: eventos USD alta=",count," cobertura hasta ",TimeToString(newsTo));return true;
}
bool CalendarEntryReady732(){
 if(!NewsFilterEnabled && !BigCloseBeforeNews)return true;
 datetime now=CalendarNow732();
 if(!MQLInfoInteger(MQL_TESTER) && LiveEconomicCalendarEnabled){
  if(NewsFailClosed && (!CalendarCoveredAt732(now) || lastLiveCalendarSuccess<=0 || now-lastLiveCalendarSuccess>300))
   return BlockDiag732("ESPERA_CALENDARIO_VIVO","Sin calendario vivo reciente: no abre; gestion de posiciones sigue activa");
 }
 if(!CalendarCoveredAt732(now) && NewsFailClosed)return BlockDiag732("CALENDARIO_FUERA_COBERTURA","Calendario vencido/ausente: no abre y no fuerza cierres por noticias");
 return true;
}
int OtherTokioPositions732(){
 if(MQLInfoInteger(MQL_TESTER))return 0;
 int count=0;
 for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || PositionGetString(POSITION_SYMBOL)!=_Symbol)continue;
  long m=PositionGetInteger(POSITION_MAGIC);
  if(m!=(long)MagicNumber && (m==730202611 || m==732120002 || m==732120001))count++;
 }
 return count;
}
bool MigrationEntryReady732(){
 int count=OtherTokioPositions732();
 if(BlockNewEntriesWithOtherTokioMagic && count>0)return BlockDiag732("OTRA_CESTA_ANTERIOR","Hay "+(string)count+" posiciones con otro Magic: revisar antes de nuevas aperturas");
 return true;
}

// Live adapter. Strategy rules above retain their original defaults.
bool liveReady=false,liveLedgerDirty=true;
bool liveStateDirty=true;
ulong lastStateSave=0;
int liveLock=INVALID_HANDLE;
string liveBase="";
double liveRealized=0,liveInitial=0,livePeak=0,liveMaxDD=0,liveMaxDDPct=0;
ulong cycleBoundary=0;
datetime lastPanel=0,lastCurve=0;
struct LiveState732 {
 int signature;
 long login;
 ulong magic;
 datetime started;
datetime lastOrder;
datetime resStart;
datetime firstDirectionalTime;
datetime bigPauseUntil;
datetime lastProtection;
datetime inventoryPauseUntil;
datetime lastTimedTrim;
datetime lastPairTrim;
datetime windowStart;
double resBalance;
double resExtra;
double allExtra;
double initialBalance;
double peakNet;
double maxGross;
double maxNet;
double cycleRiskBaseUSD;
double zoneHigh;
double zoneLow;
double bigExitMid;
double cycleBalance;
double extraPaid;
double center;
double lastFillMid;
double scale;
double cycleLow;
double trimRearmMid;
double windowGross;
double windowNet;
double liveInitial;
double livePeak;
double liveMaxDD;
double liveMaxDDPct;
int basketTrend;
int priceSide;
int cycle;
int cyclesClosed;
int resolutionsClosed;
int trimPending;
int pairPending;
int windowEntries;
bool pendingExit;
bool hadPosition;
bool pendingBigBookExit;
bool rearmPending;
bool active;
bool closing;
bool seedComplete;
bool trimRearm;
bool onEntryTrimPending;
bool hazardLatched;
ulong cycleBoundary;
ulong lastInventoryEntryID;
long retryAfter;
 double volDist;
 double trailMult;
 datetime cooldownUntil;
 datetime flatSince;
 bool cushionActive;
};
uint Hash732(string s){uint h=2166136261;for(int i=0;i<StringLen(s);i++){h^=(uint)StringGetCharacter(s,i);h*=16777619;}return h;}
bool CheckAccount732(){
 if(!MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_CONNECTED))return WaitBootstrap732("ESPERA_CONEXION","Esperando conexion y datos de cuenta");
 string c=AccountInfoString(ACCOUNT_CURRENCY);
 if(c=="")return WaitBootstrap732("ESPERA_CUENTA","La moneda de cuenta aun no esta disponible");
 if(c!="USD" && c!="USC"){Print("732: requiere cuenta USD o USC (cent); cuenta actual ",c);return BlockDiag732("ERROR_MONEDA","Requiere cuenta USD o USC; cuenta="+c);}
 if(StringFind(_Symbol,"XAUUSD")!=0 && StringFind(_Symbol,"BTCUSD")!=0){Print("732: requiere XAUUSD o BTCUSD del broker, incluido su sufijo.");return BlockDiag732("ERROR_SIMBOLO","Este experto requiere XAUUSD o BTCUSD y el sufijo correcto del broker");}
 if(!MQLInfoInteger(MQL_TESTER) && RequireExnessBroker){
  string company=AccountInfoString(ACCOUNT_COMPANY);StringToLower(company);
  string server=AccountInfoString(ACCOUNT_SERVER);StringToLower(server);
  if(StringFind(company,"exness")<0 && StringFind(server,"exness")<0){Print("732: edicion Exness.");return BlockDiag732("ERROR_BROKER","Edicion exclusiva para cuentas Exness");}
 }
 return true;
}
void BeginLedger732(){
 if(MQLInfoInteger(MQL_TESTER))return;
 cycleBoundary=0;HistorySelect(0,TimeCurrent()+86400);
 for(int i=HistoryDealsTotal()-1;i>=0;i--){ulong d=HistoryDealGetTicket(i);cycleBoundary=MathMax(cycleBoundary,d);}
 liveRealized=0;liveLedgerDirty=true;
}
double CycleRealizedNative732(){
 if(MQLInfoInteger(MQL_TESTER))return AccountInfoDouble(ACCOUNT_BALANCE)-cycleBalance;
 if(!active || started==0)return 0;
 if(!liveLedgerDirty)return liveRealized;
 if(!HistorySelect(started-1,TimeCurrent()+86400)){Print("732: historial no disponible; se conserva ultimo PnL conocido.");return liveRealized;}
 ulong ids[];int n=HistoryDealsTotal();
 for(int i=0;i<n;i++){ulong d=HistoryDealGetTicket(i);
  if(d<=cycleBoundary || HistoryDealGetString(d,DEAL_SYMBOL)!=_Symbol || HistoryDealGetInteger(d,DEAL_MAGIC)!=(long)MagicNumber)continue;
  long t=HistoryDealGetInteger(d,DEAL_TYPE);if(t!=DEAL_TYPE_BUY && t!=DEAL_TYPE_SELL)continue;
  ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);bool found=false;for(int k=0;k<ArraySize(ids);k++)if(ids[k]==id)found=true;
  if(!found){int k=ArraySize(ids);ArrayResize(ids,k+1);ids[k]=id;}
 }
 double sum=0;
 for(int i=0;i<n;i++){ulong d=HistoryDealGetTicket(i);if(d<=cycleBoundary)continue;
  ulong id=(ulong)HistoryDealGetInteger(d,DEAL_POSITION_ID);bool ours=false;for(int k=0;k<ArraySize(ids);k++)if(ids[k]==id)ours=true;
  if(ours)sum+=HistoryDealGetDouble(d,DEAL_PROFIT)+HistoryDealGetDouble(d,DEAL_SWAP)+HistoryDealGetDouble(d,DEAL_COMMISSION)+HistoryDealGetDouble(d,DEAL_FEE);
 }
 liveRealized=sum;liveLedgerDirty=false;return sum;
}
bool SaveLive732(bool force=false){
 if(!liveReady)return false;
 if(!force && !liveStateDirty && GetTickCount64()-lastStateSave<1000)return true;
 LiveState732 s;ZeroMemory(s);s.signature=7321202;s.login=AccountInfoInteger(ACCOUNT_LOGIN);s.magic=MagicNumber;
 s.started=started;
s.lastOrder=lastOrder;
s.resStart=resStart;
s.firstDirectionalTime=firstDirectionalTime;
s.bigPauseUntil=bigPauseUntil;
s.lastProtection=lastProtection;
s.inventoryPauseUntil=inventoryPauseUntil;
s.lastTimedTrim=lastTimedTrim;
s.lastPairTrim=lastPairTrim;
s.windowStart=windowStart;
s.resBalance=resBalance;
s.resExtra=resExtra;
s.allExtra=allExtra;
s.initialBalance=initialBalance;
s.peakNet=peakNet;
s.maxGross=maxGross;
s.maxNet=maxNet;
s.cycleRiskBaseUSD=cycleRiskBaseUSD;
s.zoneHigh=zoneHigh;
s.zoneLow=zoneLow;
s.bigExitMid=bigExitMid;
s.cycleBalance=cycleBalance;
s.extraPaid=extraPaid;
s.center=center;
s.lastFillMid=lastFillMid;
s.scale=scale;
s.cycleLow=cycleLow;
s.trimRearmMid=trimRearmMid;
s.windowGross=windowGross;
s.windowNet=windowNet;
s.liveInitial=liveInitial;
s.livePeak=livePeak;
s.liveMaxDD=liveMaxDD;
s.liveMaxDDPct=liveMaxDDPct;
s.basketTrend=basketTrend;
s.priceSide=priceSide;
s.cycle=cycle;
s.cyclesClosed=cyclesClosed;
s.resolutionsClosed=resolutionsClosed;
s.trimPending=trimPending;
s.pairPending=pairPending;
s.windowEntries=windowEntries;
s.pendingExit=pendingExit;
s.hadPosition=hadPosition;
s.pendingBigBookExit=pendingBigBookExit;
s.rearmPending=rearmPending;
s.active=active;
s.closing=closing;
s.seedComplete=seedComplete;
s.trimRearm=trimRearm;
s.onEntryTrimPending=onEntryTrimPending;
s.hazardLatched=hazardLatched;
s.cycleBoundary=cycleBoundary;
s.lastInventoryEntryID=lastInventoryEntryID;
s.retryAfter=retryAfter;
s.volDist=volDist;
s.trailMult=trailMult;
s.cooldownUntil=cooldownUntil;
s.flatSince=flatSince;
s.cushionActive=cushionActive;
 string p=liveBase+".state.tmp";
 ResetLastError();int f=FileOpen(p,FILE_WRITE|FILE_BIN|FILE_COMMON);if(f==INVALID_HANDLE){Print("732 estado: FileOpen error=",GetLastError()," ruta=",TerminalInfoString(TERMINAL_COMMONDATA_PATH),"\\Files\\",p);return false;}
 uint bytes=FileWriteStruct(f,s);FileFlush(f);FileClose(f);
 if(bytes!=sizeof(s)){Print("732 estado: bytes=",bytes," esperado=",sizeof(s));return false;}
 bool ok=FileMove(p,FILE_COMMON,liveBase+".state",FILE_COMMON|FILE_REWRITE);
 if(ok){lastStateSave=GetTickCount64();liveStateDirty=false;}else Print("732 estado: FileMove error=",GetLastError());return ok;
}
bool LoadLive732(){
 int f=FileOpen(liveBase+".state",FILE_READ|FILE_BIN|FILE_COMMON);if(f==INVALID_HANDLE)return false;
 LiveState732 s;uint bytes=FileReadStruct(f,s);FileClose(f);
 if(bytes!=sizeof(s) || s.signature!=7321202 || s.login!=AccountInfoInteger(ACCOUNT_LOGIN) || s.magic!=MagicNumber)return false;
 started=s.started;
lastOrder=s.lastOrder;
resStart=s.resStart;
firstDirectionalTime=s.firstDirectionalTime;
bigPauseUntil=s.bigPauseUntil;
lastProtection=s.lastProtection;
inventoryPauseUntil=s.inventoryPauseUntil;
lastTimedTrim=s.lastTimedTrim;
lastPairTrim=s.lastPairTrim;
windowStart=s.windowStart;
resBalance=s.resBalance;
resExtra=s.resExtra;
allExtra=s.allExtra;
initialBalance=s.initialBalance;
peakNet=s.peakNet;
maxGross=s.maxGross;
maxNet=s.maxNet;
cycleRiskBaseUSD=s.cycleRiskBaseUSD;
zoneHigh=s.zoneHigh;
zoneLow=s.zoneLow;
bigExitMid=s.bigExitMid;
cycleBalance=s.cycleBalance;
extraPaid=s.extraPaid;
center=s.center;
lastFillMid=s.lastFillMid;
scale=s.scale;
cycleLow=s.cycleLow;
trimRearmMid=s.trimRearmMid;
windowGross=s.windowGross;
windowNet=s.windowNet;
liveInitial=s.liveInitial;
livePeak=s.livePeak;
liveMaxDD=s.liveMaxDD;
liveMaxDDPct=s.liveMaxDDPct;
basketTrend=s.basketTrend;
priceSide=s.priceSide;
cycle=s.cycle;
cyclesClosed=s.cyclesClosed;
resolutionsClosed=s.resolutionsClosed;
trimPending=s.trimPending;
pairPending=s.pairPending;
windowEntries=s.windowEntries;
pendingExit=s.pendingExit;
hadPosition=s.hadPosition;
pendingBigBookExit=s.pendingBigBookExit;
rearmPending=s.rearmPending;
active=s.active;
closing=s.closing;
seedComplete=s.seedComplete;
trimRearm=s.trimRearm;
onEntryTrimPending=s.onEntryTrimPending;
hazardLatched=s.hazardLatched;
cycleBoundary=s.cycleBoundary;
lastInventoryEntryID=s.lastInventoryEntryID;
retryAfter=s.retryAfter;
volDist=s.volDist>0?s.volDist:1;
trailMult=s.trailMult>0?s.trailMult:1;
cooldownUntil=s.cooldownUntil;
flatSince=s.flatSince;
cushionActive=s.cushionActive;
 if(pendingExit)exitReason="SALIDA_REANUDADA";
 trimCause="RECORTE_REANUDADO";liveLedgerDirty=true;
 return true;
}
bool LiveInit732(){
 if(MQLInfoInteger(MQL_TESTER))return true;
 liveBase="Tokio732_"+RELEASE_MODE+"_"+(string)AccountInfoInteger(ACCOUNT_LOGIN)+"_"+(string)Hash732(AccountInfoString(ACCOUNT_SERVER)+_Symbol)+"_"+(string)MagicNumber;
 // Exclusive common-file handle also prevents duplicates in different terminals.
 liveLock=FileOpen(liveBase+".lock",FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
 if(liveLock==INVALID_HANDLE){Print("732: otra instancia usa esta cuenta/simbolo/magic, o no se puede crear el bloqueo.");return BlockDiag732("ERROR_INSTANCIA_O_ARCHIVO","Otra copia usa este magic/simbolo o no puede abrirse Common/Files; error="+(string)GetLastError());}
 Book();bool restored=LoadLive732();
 if(restored)ResetUntradedBasket732();
 if(positions>0 && (!restored || !active)){
  Print("732: hay posiciones propias sin estado recuperable. No se abriran mas. Revisalas manualmente; no borres el estado de una cesta abierta.");FileClose(liveLock);liveLock=INVALID_HANDLE;return BlockDiag732("ERROR_ESTADO_CESTA","Hay posiciones propias sin estado recuperable; revisar manualmente");
 }
 if(restored && active && positions>0){
  // Rebuild SL tracking from the surviving position comments.
  for(int i=PositionsTotal()-1;i>=0;i--){ulong t=PositionGetTicket(i);if(!t || !OurPosition732() || !IsProtectedPosition())continue;int n=ArraySize(bigPositionIDs);ArrayResize(bigPositionIDs,n+1);bigPositionIDs[n]=(ulong)PositionGetInteger(POSITION_IDENTIFIER);}
 }
 if(!restored){liveInitial=AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor;livePeak=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor;}
 liveReady=true;
 if(!SaveLive732(true)){Print("732: no se puede persistir el estado. No se inicia trading.");liveReady=false;FileClose(liveLock);liveLock=INVALID_HANDLE;return BlockDiag732("ERROR_GUARDADO","No se puede guardar estado en Common/Files; error="+(string)GetLastError());}
 EventSetTimer(2);WritePanel732(true);
 Print("732 ",RELEASE_MODE," lista. Importes publicos=",DisplayCurrency732(),"; contabilidad interna normalizada USD; lotes del broker. Panel: ",TerminalInfoString(TERMINAL_COMMONDATA_PATH),"\\Files.");
 return true;
}
string Esc732(string s){StringReplace(s,"\\","\\\\");StringReplace(s,"\"","\\\"");StringReplace(s,"\r"," ");StringReplace(s,"\n"," ");return s;}
string Num732(double x){return MathIsValidNumber(x)?DoubleToString(x,8):"0";}
void WritePanel732(bool force=false){
 if(!liveReady || (!force && TimeGMT()-lastPanel<2))return;
 Book();datetime now=TimeGMT();lastPanel=now;
 double eq=AccountInfoDouble(ACCOUNT_EQUITY)/MoneyFactor,bal=AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor;
 livePeak=MathMax(livePeak,eq);liveMaxDD=MathMax(liveMaxDD,livePeak-eq);if(livePeak>0)liveMaxDDPct=MathMax(liveMaxDDPct,100*(livePeak-eq)/livePeak);
 string j="{\"version\":732,\"mode\":\""+RELEASE_MODE+"\",\"currency\":\""+AccountInfoString(ACCOUNT_CURRENCY)+"\",\"symbol\":\""+Esc732(_Symbol)+"\",\"server\":\""+Esc732(AccountInfoString(ACCOUNT_SERVER))+"\",\"t\":"+(string)(long)now+",\"server_time\":"+(string)(long)TimeCurrent()+",\"connected\":"+(TerminalInfoInteger(TERMINAL_CONNECTED)?"true":"false")+",\"trade_allowed\":"+((TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED) && AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))?"true":"false")+",\"initial\":"+Num732(liveInitial)+",\"balance\":"+Num732(bal)+",\"equity\":"+Num732(eq)+",\"floating\":"+Num732((floating+swaps)/MoneyFactor)+",\"basket_net\":"+Num732(active?Liquidatable():0)+",\"positions\":"+(string)positions+",\"buys\":"+Num732(buys)+",\"sells\":"+Num732(sells)+",\"gross\":"+Num732(buys+sells)+",\"price_value_lot_usd\":"+Num732(PriceValueLot)+",\"contract\":"+Num732(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE))+",\"margin\":"+Num732(AccountInfoDouble(ACCOUNT_MARGIN)/MoneyFactor)+",\"free_margin\":"+Num732(AccountInfoDouble(ACCOUNT_MARGIN_FREE)/MoneyFactor)+",\"max_dd\":"+Num732(liveMaxDD)+",\"max_dd_pct\":"+Num732(liveMaxDDPct)+",\"mae\":"+Num732(cycleLow)+",\"recycles\":"+(string)recycleCloses+",\"pairs\":"+(string)fundedPairs+"}";
 j=StringSubstr(j,0,StringLen(j)-1)+",\"status\":\""+Esc732(diagState)+"\",\"status_detail\":\""+Esc732(diagDetail)+"\",\"tick_count\":"+(string)tickCount+",\"last_retcode\":"+(string)diagRetcode+"}";
 j=StringSubstr(j,0,StringLen(j)-1)+",\"ema_error\":"+(string)diagEMAError+",\"ema_ready\":"+(diagEMAReady?"true":"false")+",\"ema_bars_min\":"+(string)MathMin(MathMin(BarsCalculated(hf),BarsCalculated(hs)),MathMin(BarsCalculated(mf),BarsCalculated(ms)))+",\"calendar_source\":\""+calendarSource732+"\",\"calendar_covered\":"+(CalendarCoveredAt732(CalendarNow732())?"true":"false")+",\"calendar_error\":"+(string)liveCalendarError+",\"magic\":"+(string)MagicNumber+",\"other_tokio_positions\":"+(string)OtherTokioPositions732()+"}";
 double factor=active?scale:ConfiguredScale732();
 j=StringSubstr(j,0,StringLen(j)-1)+",\"display_currency\":\""+DisplayCurrency732()+"\",\"display_factor\":"+Num732(DisplayFactor732())+",\"reference_balance_native\":"+Num732(DisplayMoney732(ReferenceBalanceUSD))+",\"next_scale\":"+Num732(ConfiguredScale732())+",\"minimum_scaled_lots\":"+(UseMinimumForScaledLots?"true":"false")+",\"minimum_legs\":"+(string)MinimumLegs732(factor)+"}";
 j=StringSubstr(j,0,StringLen(j)-1)+",\"scale_with_balance\":"+(ScaleLotsWithBalance?"true":"false")+",\"effective_scale\":"+Num732(factor)+",\"reference_balance_usd\":"+Num732(ReferenceBalanceUSD)+",\"lot_multiplier\":"+Num732(LotMultiplier)+",\"effective_with_lots\":"+Num732(TargetLots732(LotsWithTrend,factor))+",\"raw_with_lots\":"+Num732(LotsWithTrend*factor)+",\"min_lots\":"+Num732(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN))+"}";
 string temp=liveBase+".json.tmp";int f=FileOpen(temp,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
 if(f!=INVALID_HANDLE){FileWriteString(f,j);FileFlush(f);FileClose(f);FileMove(temp,FILE_COMMON,liveBase+".json",FILE_COMMON|FILE_REWRITE);}
 if(force || now-lastCurve>=15){lastCurve=now;f=FileOpen(liveBase+".curve.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
  if(f!=INVALID_HANDLE){FileSeek(f,0,SEEK_END);FileWrite(f,(long)now,eq,bal,(floating+swaps)/MoneyFactor,positions,buys+sells,active?Liquidatable():0);FileFlush(f);FileClose(f);}
 }
}
void LiveBasket732(string why,double net){
 if(!liveReady)return;
 int f=FileOpen(liveBase+".baskets.csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON|FILE_SHARE_READ,',');
 if(f!=INVALID_HANDLE){FileSeek(f,0,SEEK_END);FileWrite(f,(long)TimeGMT(),net,maxInventoryPositions,(TimeCurrent()-started)/60.0,why,AccountInfoDouble(ACCOUNT_BALANCE)/MoneyFactor,cycleLow);FileFlush(f);FileClose(f);}
}
void OnTick(){
 if(!MQLInfoInteger(MQL_TESTER) && !liveReady)return;
 if(!Gate732()){Dashboard732();return;}
 bool wasActive=active;
 StrategyTick732();
 if(wasActive!=active)liveStateDirty=true;
 if(liveReady){if(!SaveLive732())Print("732: no se pudo guardar estado; comprueba disco/permisos.");WritePanel732();}
 Dashboard732();
}
void OnTimer(){if(bootstrapPending){RetryBootstrap732();return;}if(bootstrapStopped){Dashboard732();return;}if(liveReady){RefreshLiveCalendar732();Warmup732();Gate732();WritePanel732();SaveLive732();Dashboard732();}}
void LiveDeinit732(int reason=0){
 EventKillTimer();if(liveReady){SaveLive732(true);WritePanel732(true);liveReady=false;}
 if(liveLock!=INVALID_HANDLE){FileClose(liveLock);liveLock=INVALID_HANDLE;}
 if(atrHandle!=INVALID_HANDLE){IndicatorRelease(atrHandle);atrHandle=INVALID_HANDLE;}
 if(dashboardPrefix!="" && reason!=REASON_INITFAILED)ObjectsDeleteAll(0,dashboardPrefix);
}

// Read-only on-chart dashboard. It never sends, modifies or closes trades.
input group "29 - Dashboard de diagnostico (solo lectura)"
input bool DashboardEnabled=true;
input int DashboardX=12;
input int DashboardY=28;
string diagState="INICIALIZANDO",diagDetail="Preparando indicadores y estado";
double diagMainFast=0,diagMainSlow=0,diagMicroFast=0,diagMicroSlow=0;
bool diagEMAReady=false;
int diagEMAError=0;
uint diagRetcode=0;
string dashboardPrefix="";
datetime diagLastPrint=0;
string diagLastPrinted="";
ulong diagLastDraw=0;
string diagLastDrawState="";
void SetDiag732(string state,string detail){diagState=state;diagDetail=detail;}
bool BlockDiag732(string state,string detail){SetDiag732(state,detail);return false;}
double ConfiguredScale732(){return ScaleFactorMath732(AccountInfoDouble(ACCOUNT_BALANCE),MoneyFactor,allExtra,ReferenceBalanceUSD,LotMultiplier,ScaleLotsWithBalance);}
bool CheckStartingLots732(double factor){
 double raw=LotsWithTrend*factor,effective=TargetLots732(LotsWithTrend,factor),minimum=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
 if(effective<minimum-1e-8)return BlockDiag732("LOTES_REDONDEADOS_A_CERO","Favor="+DoubleToString(raw,6)+" < minimo="+DoubleToString(minimum,2)+"; revisar escala de saldo y multiplicador");
 return true;
}
bool ResetUntradedBasket732(){
 // Only discard a never-executed cycle. A real trade or uncertain history keeps it.
 if(!active || positions>0 || hadPosition || started<=0)return false;
 if(!HistorySelect(started-1,TimeCurrent()+86400))return false;
 for(int i=0;i<HistoryDealsTotal();i++){ulong d=HistoryDealGetTicket(i);
  if(d>cycleBoundary && HistoryDealGetString(d,DEAL_SYMBOL)==_Symbol && HistoryDealGetInteger(d,DEAL_MAGIC)==(long)MagicNumber){long kind=HistoryDealGetInteger(d,DEAL_TYPE);if(kind==DEAL_TYPE_BUY || kind==DEAL_TYPE_SELL)return false;}
 }
 active=false;seedComplete=false;pendingExit=false;closing=false;pendingBigBookExit=false;firstDirectionalTime=0;
 started=0;center=0;zoneHigh=0;zoneLow=0;extraPaid=0;peakNet=0;cycleLow=0;liveRealized=0;liveLedgerDirty=true;liveStateDirty=true;
 Print("732: se descarta solo el ciclo vacio sin posiciones ni deals propios; se recalculara la escala configurada.");return true;
}
bool Gate732(){
 if(MQLInfoInteger(MQL_TESTER))return true;
 if(!TerminalInfoInteger(TERMINAL_CONNECTED))return BlockDiag732("DESCONECTADO","MT5 no esta conectado al servidor");
 if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))return BlockDiag732("ALGO_DESACTIVADO","Boton Algo Trading desactivado en MT5");
 if(!MQLInfoInteger(MQL_TRADE_ALLOWED))return BlockDiag732("PERMISO_EA_DESACTIVADO","Permitir trading algoritmico no esta habilitado para este experto");
 if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED) || !AccountInfoInteger(ACCOUNT_TRADE_EXPERT))return BlockDiag732("CUENTA_NO_AUTORIZA","El servidor no permite operaciones del experto en esta cuenta");
 if(SymbolInfoInteger(_Symbol,SYMBOL_TRADE_MODE)==SYMBOL_TRADE_MODE_DISABLED || SymbolInfoInteger(_Symbol,SYMBOL_TRADE_MODE)==SYMBOL_TRADE_MODE_CLOSEONLY)return BlockDiag732("SIMBOLO_NO_ABRE","El simbolo esta deshabilitado o solo permite cerrar");
 return true;
}
void Warmup732(){
 // Ask for the actual configured history; never substitute another timeframe.
 if(BarsCalculated(hf)>MathMax(MainFastEMA,MainSlowEMA) && BarsCalculated(hs)>MathMax(MainFastEMA,MainSlowEMA) && BarsCalculated(mf)>MathMax(MicroFastEMA,MicroSlowEMA) && BarsCalculated(ms)>MathMax(MicroFastEMA,MicroSlowEMA))return;
 MqlRates rates[];CopyRates(_Symbol,MainTimeframe,0,MathMax(MainFastEMA,MainSlowEMA)+10,rates);CopyRates(_Symbol,MicroTimeframe,0,MathMax(MicroFastEMA,MicroSlowEMA)+10,rates);
}
string Dir732(int d){return d>0?"ALCISTA":d<0?"BAJISTA":"SIN SENAL";}
void DashboardRow732(int row,string text,color ink=clrGainsboro){
 string name=dashboardPrefix+"row"+(string)row;
 if(ObjectFind(0,name)<0){ObjectCreate(0,name,OBJ_LABEL,0,0,0);ObjectSetInteger(0,name,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,name,OBJPROP_FONTSIZE,10);ObjectSetString(0,name,OBJPROP_FONT,"Consolas");ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);ObjectSetInteger(0,name,OBJPROP_HIDDEN,true);}
 ObjectSetInteger(0,name,OBJPROP_XDISTANCE,DashboardX+12);ObjectSetInteger(0,name,OBJPROP_YDISTANCE,DashboardY+10+row*22);ObjectSetInteger(0,name,OBJPROP_COLOR,ink);ObjectSetString(0,name,OBJPROP_TEXT,text);
}
void Dashboard732(){
 if(MQLInfoInteger(MQL_TESTER))return;
 string signature=diagState+"|"+diagDetail;
 if(signature!=diagLastPrinted && TimeLocal()-diagLastPrint>=10){Print("732 ESTADO ",diagState," | ",diagDetail);diagLastPrinted=signature;diagLastPrint=TimeLocal();}
 if(!DashboardEnabled)return;
 if(signature==diagLastDrawState && GetTickCount64()-diagLastDraw<500)return;
 diagLastDraw=GetTickCount64();diagLastDrawState=signature;
 if(dashboardPrefix=="")dashboardPrefix="TOKIO732_DASH_"+(string)ChartID()+"_";
 string bg=dashboardPrefix+"bg";
 if(ObjectFind(0,bg)<0){ObjectCreate(0,bg,OBJ_RECTANGLE_LABEL,0,0,0);ObjectSetInteger(0,bg,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,bg,OBJPROP_BGCOLOR,C'13,21,32');ObjectSetInteger(0,bg,OBJPROP_BORDER_TYPE,BORDER_FLAT);ObjectSetInteger(0,bg,OBJPROP_COLOR,C'57,77,99');ObjectSetInteger(0,bg,OBJPROP_SELECTABLE,false);ObjectSetInteger(0,bg,OBJPROP_HIDDEN,true);ObjectSetInteger(0,bg,OBJPROP_BACK,false);}
 ObjectSetInteger(0,bg,OBJPROP_XDISTANCE,DashboardX);ObjectSetInteger(0,bg,OBJPROP_YDISTANCE,DashboardY);ObjectSetInteger(0,bg,OBJPROP_XSIZE,715);ObjectSetInteger(0,bg,OBJPROP_YSIZE,436);
 bool waiting=StringFind(diagState,"ESPERA")>=0 || StringFind(diagState,"ZONA")>=0 || StringFind(diagState,"CALENDARIO")>=0 || StringFind(diagState,"OTRA_CESTA")>=0;
 color status=StringFind(diagState,"RECHAZO")>=0 || StringFind(diagState,"ERROR")>=0 || StringFind(diagState,"DESACTIVADO")>=0?clrTomato:waiting?clrGold:positions>0?clrLimeGreen:clrGold;
 MqlTick q;SymbolInfoTick(_Symbol,q);Book();
 DashboardRow732(0,"TOKIO 7.32 VolLab - "+AccountInfoString(ACCOUNT_COMPANY)+" "+DisplayCurrency732()+" | "+_Symbol+" | factor vol "+DoubleToString(active?volDist:VolFactor732(),2)+(volReady?"":" (sin historial)"),clrDeepSkyBlue);
 DashboardRow732(1,"ESTADO: "+diagState,status);
 DashboardRow732(2,StringSubstr(diagDetail,0,85),status);
 DashboardRow732(3,"Ticks: "+(string)tickCount+" | Senal: "+Dir732(cachedTrend)+" | Ciclo: "+(string)cycle);
 DashboardRow732(4,"EMA principal "+EnumToString(MainTimeframe)+": "+DoubleToString(diagMainFast,3)+" / "+DoubleToString(diagMainSlow,3));
 DashboardRow732(5,"EMA micro "+EnumToString(MicroTimeframe)+": "+DoubleToString(diagMicroFast,3)+" / "+DoubleToString(diagMicroSlow,3));
 int bars=MathMin(MathMin(BarsCalculated(hf),BarsCalculated(hs)),MathMin(BarsCalculated(mf),BarsCalculated(ms)));
 DashboardRow732(6,"Error EMA: "+(string)diagEMAError+" | Barras listas (min): "+(string)bars+" | "+(diagEMAReady?"DATOS OK":"ESPERANDO DATOS"),diagEMAError==0&&diagEMAReady?clrLimeGreen:clrGold);
 DashboardRow732(7,"Pos: "+(string)positions+" | BUY: "+DoubleToString(buys,2)+" SELL: "+DoubleToString(sells,2)+" | Neto: "+DoubleToString(buys-sells,2));
 DashboardRow732(8,"Cesta neta: "+DoubleToString(DisplayMoney732(active?Liquidatable():0),2)+" "+DisplayCurrency732()+" | Margen libre: "+DoubleToString(DisplayMoney732(AccountInfoDouble(ACCOUNT_MARGIN_FREE)/MoneyFactor),2)+" "+DisplayCurrency732());
 DashboardRow732(9,"Cotizacion: "+DoubleToString(q.bid,_Digits)+" / "+DoubleToString(q.ask,_Digits)+" | Ultimo tick: "+TimeToString(q.time,TIME_SECONDS));
 DashboardRow732(10,"Rechazos: "+(string)failedRequests+" | Retcode: "+(string)diagRetcode+" | InitError: "+(string)diagInitError+" | Intentos init: "+(string)bootstrapAttempts);
 DashboardRow732(11,"TP:"+(ProfitTargetEnabled?"ON":"OFF")+" SL:"+(CashStopEnabled?"ON":"OFF")+" Trail:"+(TrailingEnabled?"ON":"OFF")+" Recovery:"+(RecoveryEnabled?"ON":"OFF")+" | Lotes: "+DoubleToString(LotsWithTrend,2)+" / "+DoubleToString(LotsAgainstTrend,2));
 double factor=active?scale:ConfiguredScale732();
 DashboardRow732(12,"Escalar: "+(ScaleLotsWithBalance?"TRUE":"FALSE")+" | Cesta: "+DoubleToString(factor,6)+" | Proxima: "+DoubleToString(ConfiguredScale732(),6));
 DashboardRow732(13,"Ref: "+DoubleToString(DisplayMoney732(ReferenceBalanceUSD),2)+" "+DisplayCurrency732()+" | Lotes favor/contra/semilla: "+DoubleToString(TargetLots732(LotsWithTrend,factor),2)+"/"+DoubleToString(TargetLots732(LotsAgainstTrend,factor),2)+"/"+DoubleToString(TargetLots732(PairedSeedLots,factor),2));
 DashboardRow732(14,"Minimo autorizado: "+(UseMinimumForScaledLots?"TRUE":"FALSE")+" | Patas ajustadas: "+(string)MinimumLegs732(factor)+" | Broker: "+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),2),MinimumLegs732(factor)>0?clrGold:clrSilver);
 DashboardRow732(15,"Heartbeat: "+TimeToString(TimeLocal(),TIME_SECONDS)+" | Escala congelada durante la cesta.",clrSilver);
 DashboardRow732(16,"Calendario: "+calendarSource732+" | Cobertura: "+(CalendarCoveredAt732(CalendarNow732())?"OK":"NO")+" | Error: "+(string)liveCalendarError,CalendarCoveredAt732(CalendarNow732())?clrSilver:clrGold);
 DashboardRow732(17,"Magic propio: "+(string)MagicNumber+" | Posiciones de otro Tokio: "+(string)OtherTokioPositions732(),OtherTokioPositions732()>0?clrTomato:clrSilver);
 ChartRedraw();
}
int OnInit(){
 if(!MQLInfoInteger(MQL_TESTER) && !LiveTradingEnabled){Print("Tokio732_VolLab: LiveTradingEnabled=false, solo Probador de estrategias. No opera en graficos.");return INIT_FAILED;}
 if(CushionEnabled && (CushionBaseUSD<=0 || CushionActivateUSD<CushionDeactivateUSD || CushionGain<0))return INIT_PARAMETERS_INCORRECT;
 if(VolLotGamma<0 || VolATRRef<=0 || VolATRPeriod<2 || VolFactorMin<=0 || VolFactorMax<VolFactorMin)return INIT_PARAMETERS_INCORRECT;
 string unit=AccountInfoString(ACCOUNT_CURRENCY);MoneyFactor=unit=="USC" || (unit=="" && RELEASE_CURRENCY=="USC")?100.0:1.0;
 ResetLastError();bootstrapAttempts=1;int code=EngineInit732();
 if(code!=INIT_SUCCEEDED && bootstrapRetryable && !MQLInfoInteger(MQL_TESTER)){
  CleanupPartialInit732();bootstrapPending=true;bootstrapLastAttempt=TimeLocal();
  if(!EventSetTimer(2)){bootstrapPending=false;SetDiag732("ERROR_TIMER","No se puede iniciar reloj de reintento; error="+(string)GetLastError());Dashboard732();return INIT_FAILED;}
  Dashboard732();return INIT_SUCCEEDED;
 }
 if(code!=INIT_SUCCEEDED){if(diagState=="INICIALIZANDO")SetDiag732("ERROR_INICIALIZACION","Codigo="+(string)code+"; error="+(string)GetLastError()+". Revisar pestaÃ±a Expertos.");Dashboard732();return code;}
 SetDiag732("ESPERA_PRIMER_TICK","Inicializado; esperando primer tick e indicadores cerrados");Dashboard732();return code;
}
