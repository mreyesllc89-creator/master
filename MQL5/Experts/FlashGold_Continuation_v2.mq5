#define OnTester CPBT_OriginalOnTester
#property description "FlashGold_Continuation_v2 | active continuation entry filter | XPWF v1.1 direction/time gate"
// FlashGold_Continuation_v2.mq5
// Separate derivative of FlashGoldVirtual.mq5; Continuation v2.
//+------------------------------------------------------------------+
//|                                          FlashGold_Continuation_v2.mq5    |
//|                                  Copyright 2025, Senior Engineer |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Senior MQL5 Engineer"
#property link      "https://www.mql5.com"
#property version   "1.03" // Added Money Management
#property strict

#include <Trade\Trade.mqh>
#include <XPW_TradeWindowFilter.mqh>   // XPWF v1.1 direction/time gate

// BEGIN CONTINUATION V2
// Embedded separately in every Continuation_v2 EA. No shared runtime module.
// All measurements are frozen before the original CTrade::OrderSend call.
enum ENUM_CP_MODE { CP_OFF=0, CP_FILTER=2 };
input group "Continuation v2 - Active entry filter"
input ENUM_CP_MODE InpCPMode = CP_FILTER; // Continuation mode (Filter or Off)
input double InpCPPriceUnit = 0.01;       // Price per audit point (not broker _Point)
input double InpCPMinTickRate60 = 3.8;    // Minimum tick rate, last 60s (ticks/sec; 0=off)
input double InpCPMaxMedianGapMs = 215.0; // Maximum median quote gap, last 60s (ms; 0=off)
input double InpCPMinRange60 = 0.0;       // Minimum 1-minute range (audit points; 0=off)
input double InpCPMinRange300 = 0.0;      // Minimum 5-minute range (audit points; 0=off)
input bool InpCPWriteCsv = true;
input bool InpCPPrintDecisions = false;
input group "Original EA settings"

struct CP_Snapshot
{
   long cutoff_msc;
   long min_source_msc;
   long max_source_msc;
   int count60;
   int count300;
   bool complete60;
   bool complete300;
   double tick_rate60;
   double median_gap_ms;
   double range60_pts;
   double range300_pts;
   double spread_pts;
   string data_status;
};

CP_Snapshot g_cpCache;
long g_cpCacheSecond = -1;
long g_cpLastQuoteMsc = 0;
double g_cpLastBid = 0.0;
double g_cpLastAsk = 0.0;
ulong g_cpLastReceiptMs = 0;
bool g_cpReceiptKnown = false;
ulong g_cpSequence = 0;
ulong g_cpAllowed = 0;
ulong g_cpBlocked = 0;
int g_cpLog = INVALID_HANDLE;
int g_cpRowsSinceFlush = 0;
ulong g_cpRetryLogMs = 0;

void CP_Reset(CP_Snapshot &s, const long cutoff)
{
   s.cutoff_msc=cutoff;
   s.min_source_msc=0;
   s.max_source_msc=0;
   s.count60=0;
   s.count300=0;
   s.complete60=false;
   s.complete300=false;
   s.tick_rate60=-1.0;
   s.median_gap_ms=-1.0;
   s.range60_pts=-1.0;
   s.range300_pts=-1.0;
   s.spread_pts=-1.0;
   s.data_status="NO_TAPE";
}

// CP_CORE_BEGIN: also executed with synthetic ticks by the offline test harness.
void CP_Compute(MqlTick &ticks[], const int count, const long cutoff,
                const double unit, CP_Snapshot &s)
{
   CP_Reset(s,cutoff);
   if(unit<=0.0 || !MathIsValidNumber(unit) || count<=0) return;
   double lo60=DBL_MAX, hi60=-DBL_MAX, lo300=DBL_MAX, hi300=-DBL_MAX;
   double gaps[];
   ArrayResize(gaps,count);
   int ngaps=0;
   long previous60=0, previous_any=0;
   bool invalid=false;
   for(int i=0;i<count;i++)
   {
      long t=ticks[i].time_msc;
      // A half-open window excludes the snapshot boundary and every later tick.
      if(t>=cutoff) continue;
      if(t<=0 || !MathIsValidNumber(ticks[i].bid) || !MathIsValidNumber(ticks[i].ask) ||
         ticks[i].bid<=0.0 || ticks[i].ask<ticks[i].bid)
      { invalid=true; continue; }
      if(previous_any>t) { invalid=true; continue; }
      previous_any=t;
      if(s.min_source_msc==0) s.min_source_msc=t;
      s.max_source_msc=t;
      s.spread_pts=(ticks[i].ask-ticks[i].bid)/unit;
      if(t<cutoff-300000) continue;
      double mid=(ticks[i].bid+ticks[i].ask)*0.5;
      s.count300++;
      lo300=MathMin(lo300,mid);
      hi300=MathMax(hi300,mid);
      if(t<cutoff-60000) continue;
      s.count60++;
      lo60=MathMin(lo60,mid);
      hi60=MathMax(hi60,mid);
      if(previous60>0) gaps[ngaps++]=(double)(t-previous60);
      previous60=t;
   }
   s.complete60=(s.min_source_msc>0 && s.min_source_msc<=cutoff-60000);
   s.complete300=(s.min_source_msc>0 && s.min_source_msc<=cutoff-300000);
   if(s.complete60 || s.count60>0) s.tick_rate60=(double)s.count60/60.0;
   if(s.count60>0) s.range60_pts=(hi60-lo60)/unit;
   if(s.count300>0) s.range300_pts=(hi300-lo300)/unit;
   if(ngaps>0)
   {
      ArrayResize(gaps,ngaps);
      ArraySort(gaps);
      s.median_gap_ms=(ngaps%2==1) ? gaps[ngaps/2] :
                     (gaps[ngaps/2-1]+gaps[ngaps/2])*0.5;
   }
   if(invalid) { s.data_status="INVALID_TAPE"; s.complete60=false; s.complete300=false; }
   else if(!s.complete60) s.data_status="PARTIAL_60S";
   else if(s.count60<2) s.data_status="SPARSE_60S";
   else if(!s.complete300) s.data_status="PARTIAL_300S";
   else s.data_status="READY";
}

bool CP_HasRules()
{
   return InpCPMinTickRate60>0.0 || InpCPMaxMedianGapMs>0.0 ||
          InpCPMinRange60>0.0 || InpCPMinRange300>0.0;
}

string CP_RuleReason(const CP_Snapshot &s)
{
   if(!CP_HasRules()) return "NO_RULES_CONFIGURED";
   if(s.data_status=="INVALID_TAPE" || s.data_status=="COPY_ERROR" ||
      s.data_status=="SYMBOL_MISMATCH" || s.data_status=="NO_TAPE") return "MISSING_DATA";
   bool uses60=(InpCPMinTickRate60>0.0 || InpCPMaxMedianGapMs>0.0 || InpCPMinRange60>0.0);
   if(uses60 && !s.complete60) return "INCOMPLETE_60S";
   if(InpCPMinRange300>0.0 && !s.complete300) return "INCOMPLETE_300S";
   if(InpCPMinTickRate60>0.0 && s.tick_rate60<InpCPMinTickRate60) return "TICK_RATE_LOW";
   if(InpCPMaxMedianGapMs>0.0 && s.median_gap_ms<0.0) return "GAP_UNAVAILABLE";
   if(InpCPMaxMedianGapMs>0.0 && s.median_gap_ms>InpCPMaxMedianGapMs) return "QUOTE_GAP_HIGH";
   if(InpCPMinRange60>0.0 && s.range60_pts<InpCPMinRange60) return "RANGE_60S_LOW";
   if(InpCPMinRange300>0.0 && s.range300_pts<InpCPMinRange300) return "RANGE_300S_LOW";
   return "RULES_MET";
}
// CP_CORE_END

bool CP_Init()
{
   if(InpCPMode==CP_OFF) return true;
   if(InpCPMode!=CP_FILTER)
   { Print("Continuation v2: select CP_FILTER or CP_OFF; old Observe presets are not supported."); return false; }
   if(InpCPPriceUnit<=0.0 || !MathIsValidNumber(InpCPPriceUnit) ||
      InpCPMinTickRate60<0.0 || InpCPMaxMedianGapMs<0.0 ||
      InpCPMinRange60<0.0 || InpCPMinRange300<0.0 ||
      !MathIsValidNumber(InpCPMinTickRate60) || !MathIsValidNumber(InpCPMaxMedianGapMs) ||
      !MathIsValidNumber(InpCPMinRange60) || !MathIsValidNumber(InpCPMinRange300))
   { Print("Continuation: invalid price unit or threshold."); return false; }
   if(InpCPMode==CP_FILTER && !CP_HasRules())
   { Print("Continuation: FILTER requires at least one configured threshold."); return false; }
   PrintFormat("%s | Continuation v2 ACTIVE | %s | account=%s | min_rate=%.3f max_gap_ms=%.1f | experimental thresholds | point price=%.6f",
               MQLInfoString(MQL_PROGRAM_NAME),EnumToString(InpCPMode),CP_AccountMode(),
               InpCPMinTickRate60,InpCPMaxMedianGapMs,InpCPPriceUnit);
   return true;
}

void CP_OnTick()
{
   if(InpCPMode==CP_OFF) return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick)) return;
   if(!g_cpReceiptKnown || tick.time_msc!=g_cpLastQuoteMsc ||
      tick.bid!=g_cpLastBid || tick.ask!=g_cpLastAsk)
   {
      // Receipt silence is a local-clock observation, not network quote age.
      if(g_cpReceiptKnown && tick.time_msc<g_cpLastQuoteMsc) g_cpCacheSecond=-1;
      g_cpLastReceiptMs=GetTickCount64();
      g_cpReceiptKnown=true;
      g_cpLastQuoteMsc=tick.time_msc;
      g_cpLastBid=tick.bid;
      g_cpLastAsk=tick.ask;
   }
}

void CP_Capture(const string symbol, CP_Snapshot &s)
{
   CP_Reset(s,0);
   if(symbol!=_Symbol) { s.data_status="SYMBOL_MISMATCH"; return; }
   MqlTick anchor;
   if(!SymbolInfoTick(symbol,anchor) || anchor.time_msc<=360000) return;
   long cutoff=(anchor.time_msc/1000)*1000;
   if(g_cpCacheSecond==cutoff) { s=g_cpCache; return; }
   MqlTick ticks[];
   ResetLastError();
   int copied=CopyTicksRange(symbol,ticks,COPY_TICKS_ALL,
                            (ulong)(cutoff-360000),(ulong)(cutoff-1));
   int copy_error=GetLastError();
   CP_Compute(ticks,MathMax(copied,0),cutoff,InpCPPriceUnit,s);
   if(copy_error!=0 || copied<0)
   { s.data_status="COPY_ERROR"; s.complete60=false; s.complete300=false; }
   // Retry missing/partial history on the next request, even within this second.
   if(s.data_status=="READY") { g_cpCache=s; g_cpCacheSecond=cutoff; }
}

string CP_AccountMode()
{
   long mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode==ACCOUNT_TRADE_MODE_REAL) return "LIVE";
   if(mode==ACCOUNT_TRADE_MODE_DEMO) return "DEMO";
   return "CONTEST";
}

string CP_RunMode()
{
   return MQLInfoInteger(MQL_TESTER) ? "STRATEGY_TESTER" : "CHART";
}

string CP_FileToken(string text)
{
   StringReplace(text,"\\","_"); StringReplace(text,"/","_");
   StringReplace(text,":","_"); StringReplace(text,"*","_");
   StringReplace(text,"?","_"); StringReplace(text,"\"","_");
   StringReplace(text,"<","_"); StringReplace(text,">","_");
   StringReplace(text,"|","_");
   return text;
}

bool CP_OpenLog()
{
   if(g_cpLog!=INVALID_HANDLE) return true;
   if(GetTickCount64()<g_cpRetryLogMs) return false;
   string name=StringFormat("CP_%I64u.csv",GetTickCount64());
   g_cpLog=FileOpen(name,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
   if(g_cpLog==INVALID_HANDLE)
   {
      PrintFormat("Continuation: CSV open failed (%d); trading policy unchanged.",GetLastError());
      g_cpRetryLogMs=GetTickCount64()+60000;
      return false;
   }
   FileWrite(g_cpLog,"ea","account","account_mode","run_mode","server","symbol","timeframe","magic",
      "sequence","mode","observation_kind","request_type","snapshot_cutoff_msc",
      "min_source_msc","max_source_msc","complete60","complete300","data_status",
      "point_price","tick_count60","tick_count300","tick_rate60","median_gap_ms",
      "range60_pts","range300_pts","last_prequote_spread_pts","receipt_silence_ms",
      "capture_us","min_tick_rate60_rule","max_gap_ms_rule","min_range60_rule","min_range300_rule",
      "rule_reason","filter_exemption","blocked","meta_send_return","meta_order_ticket",
      "meta_deal_ticket","meta_retcode","meta_request_id");
   Print("Continuation CSV: MQL5/Files/",name);
   return true;
}

void CP_Record(const MqlTradeRequest &request, const CP_Snapshot &s, const ulong sequence,
               const ulong capture_us, const long receipt_silence, const string reason,
               const string exemption, const bool blocked, const bool sent, const MqlTradeResult &result)
{
   // Result identifiers are join metadata only. They never enter CP_Compute or CP_RuleReason.
   if(InpCPPrintDecisions)
      PrintFormat("Continuation %I64u %s %s rate=%.3f gap=%.1f range60=%.1f range300=%.1f blocked=%s",
         sequence,EnumToString(request.type),reason,s.tick_rate60,s.median_gap_ms,
         s.range60_pts,s.range300_pts,blocked ? "true" : "false");
   if(!InpCPWriteCsv || !CP_OpenLog()) return;
   string kind=(request.action==TRADE_ACTION_PENDING ? "PENDING_PLACEMENT" : "MARKET_SUBMISSION");
   uint written=FileWrite(g_cpLog,MQLInfoString(MQL_PROGRAM_NAME),AccountInfoInteger(ACCOUNT_LOGIN),
      CP_AccountMode(),CP_RunMode(),AccountInfoString(ACCOUNT_SERVER),request.symbol,EnumToString((ENUM_TIMEFRAMES)_Period),
      request.magic,sequence,EnumToString(InpCPMode),kind,EnumToString(request.type),s.cutoff_msc,
      s.min_source_msc,s.max_source_msc,s.complete60,s.complete300,s.data_status,
      InpCPPriceUnit,s.count60,s.count300,s.tick_rate60,s.median_gap_ms,s.range60_pts,
      s.range300_pts,s.spread_pts,receipt_silence,capture_us,InpCPMinTickRate60,InpCPMaxMedianGapMs,
      InpCPMinRange60,InpCPMinRange300,reason,exemption,blocked,sent,
      result.order,result.deal,result.retcode,result.request_id);
   if(written==0)
   {
      PrintFormat("Continuation: CSV write failed (%d).",GetLastError());
      FileClose(g_cpLog); g_cpLog=INVALID_HANDLE; g_cpRetryLogMs=GetTickCount64()+60000;
   }
   else if(++g_cpRowsSinceFlush>=64) { FileFlush(g_cpLog); g_cpRowsSinceFlush=0; }
}

void CP_Deinit()
{
   if(g_cpLog!=INVALID_HANDLE) { FileFlush(g_cpLog); FileClose(g_cpLog); g_cpLog=INVALID_HANDLE; }
   if(InpCPMode==CP_FILTER)
      PrintFormat("Continuation v2 SUMMARY | account=%s mode=%s | entry_requests=%I64u allowed=%I64u blocked=%I64u",
                  CP_AccountMode(),CP_RunMode(),g_cpSequence,g_cpAllowed,g_cpBlocked);
}

bool CP_IsEntryRequest(const MqlTradeRequest &request)
{
   if(request.position!=0 || request.position_by!=0) return false;
   return request.action==TRADE_ACTION_PENDING ||
          (request.action==TRADE_ACTION_DEAL &&
           (request.type==ORDER_TYPE_BUY || request.type==ORDER_TYPE_SELL));
}

string CP_FilterExemption(const MqlTradeRequest &request)
{
   // Netting reductions/reversals also close exposure. Never veto their exit component.
   if(request.action!=TRADE_ACTION_DEAL ||
      AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return "";
   if(!PositionSelect(request.symbol)) return "";
   long side=PositionGetInteger(POSITION_TYPE);
   if((side==POSITION_TYPE_BUY && request.type==ORDER_TYPE_SELL) ||
      (side==POSITION_TYPE_SELL && request.type==ORDER_TYPE_BUY)) return "NETTING_REDUCTION_OR_REVERSAL";
   return "";
}

// CTrade's virtual send hook covers Buy/Sell, pending entries and recovery entries.
// Closes, SL/TP changes, pending modifications and cancellations bypass it unchanged.
class CContinuationTrade : public CTrade
{
public:
   virtual bool OrderSend(const MqlTradeRequest &request, MqlTradeResult &result)
   {
      // XPWF fail-safe layer: entries only. Closes, SL/TP edits and netting reductions pass untouched.
      // Skipped entirely when both XPWF blocks are disabled so Gate 0 stays byte-for-byte original.
      if((XPWF_SellEnable || XPWF_BuyEnable) && CP_IsEntryRequest(request) && CP_FilterExemption(request)=="")
      {
         const bool xpwfIsBuy =(request.type==ORDER_TYPE_BUY  || request.type==ORDER_TYPE_BUY_STOP  ||
                               request.type==ORDER_TYPE_BUY_LIMIT  || request.type==ORDER_TYPE_BUY_STOP_LIMIT);
         const bool xpwfIsSell=(request.type==ORDER_TYPE_SELL || request.type==ORDER_TYPE_SELL_STOP ||
                               request.type==ORDER_TYPE_SELL_LIMIT || request.type==ORDER_TYPE_SELL_STOP_LIMIT);
         if((xpwfIsBuy && !XPWF_AllowBuy(false)) || (xpwfIsSell && !XPWF_AllowSell(false)))
         {
            XPWF_NoteFailsafeBlock(xpwfIsBuy ? "BUY" : "SELL");
            ZeroMemory(result);
            result.retcode=TRADE_RETCODE_REJECT;
            result.comment="XPWF: blocked";
            return false;
         }
      }
      if(InpCPMode==CP_OFF || !CP_IsEntryRequest(request)) return CTrade::OrderSend(request,result);
      ulong started=GetMicrosecondCount();
      CP_Snapshot snapshot;
      CP_Capture(request.symbol,snapshot);
      ulong capture_us=GetMicrosecondCount()-started;
      long silence=g_cpReceiptKnown ? (long)(GetTickCount64()-g_cpLastReceiptMs) : -1;
      string reason=CP_RuleReason(snapshot);
      string exemption=(InpCPMode==CP_FILTER ? CP_FilterExemption(request) : "");
      bool blocked=(InpCPMode==CP_FILTER && reason!="RULES_MET" && exemption=="");
      ulong sequence=++g_cpSequence;
      bool sent=false;
      if(blocked)
      {
         g_cpBlocked++;
         ZeroMemory(result);
         result.retcode=TRADE_RETCODE_REJECT;
         result.comment="Continuation: "+reason;
      }
      else { g_cpAllowed++; sent=CTrade::OrderSend(request,result); }
      CP_Record(request,snapshot,sequence,capture_us,silence,reason,exemption,blocked,sent,result);
      return sent;
   }
};

// END CONTINUATION V2

#include <Trade\PositionInfo.mqh>
// BEGIN INHERITED LegAsymmetryObserver_v1.mqh
#ifndef LEG_ASYMMETRY_OBSERVER_V1_MQH
#define LEG_ASYMMETRY_OBSERVER_V1_MQH

// Measurement-only observer. This file never sends, modifies, or deletes trades.
input int InpSweepWindowMs = 1000; // Pair-label sweep window; telemetry only

struct LA_LegState
{
   bool   assigned;
   bool   isBuy;
   ulong  orderTicket;
   bool   requestedAvailable;
   double requestedPrice;
   bool   filled;
   bool   terminal;
   string terminalOutcome;
   long   terminalUtcMsc;
   long   terminalTick;
   long   fillUtcMsc;
   long   fillTick;
   double actualPrice;
   bool   spreadAvailable;
   double spreadPoints;
   long   positionId;
};

struct LA_PairState
{
   bool        active;
   bool        explicitMembership;
   string      pairId;
   string      path;
   long        armUtcMsc;
   LA_LegState buy;
   LA_LegState sell;
   bool        mfeAvailable;
   double      mfePoints;
};

LA_PairState g_laPairs[];
string g_laEaName = "";
string g_laCsvName = "";
string g_laTerminalId = "";
long   g_laMagic = 0;
long   g_laTickSerial = 0;
int    g_laRowsWritten = 0;
bool   g_laCsvReady = false;
long   g_laLastCsvAttemptMsc = 0;
int    g_laLastCsvError = 0;
int    g_laLostRowsDegraded = 0;
const long LA_CSV_RETRY_INTERVAL_MSC = 60000;

void LA_ResetLeg(LA_LegState &leg, const bool isBuy)
{
   leg.assigned = false;
   leg.isBuy = isBuy;
   leg.orderTicket = 0;
   leg.requestedAvailable = false;
   leg.requestedPrice = 0.0;
   leg.filled = false;
   leg.terminal = false;
   leg.terminalOutcome = "";
   leg.terminalUtcMsc = 0;
   leg.terminalTick = 0;
   leg.fillUtcMsc = 0;
   leg.fillTick = 0;
   leg.actualPrice = 0.0;
   leg.spreadAvailable = false;
   leg.spreadPoints = 0.0;
   leg.positionId = 0;
}

string LA_SanitizeToken(string value)
{
   StringReplace(value, "\\", "_");
   StringReplace(value, "/", "_");
   StringReplace(value, ":", "_");
   StringReplace(value, " ", "_");
   StringReplace(value, ".", "_");
   return value;
}

string LA_TerminalId()
{
   string path = TerminalInfoString(TERMINAL_DATA_PATH);
   int last = -1;
   int pos = StringFind(path, "\\");
   while(pos >= 0)
   {
      last = pos;
      pos = StringFind(path, "\\", pos + 1);
   }
   string token = (last >= 0 ? StringSubstr(path, last + 1) : path);
   token = LA_SanitizeToken(token);
   if(StringLen(token) == 0)
      token = "TERMINAL_UNKNOWN";
   return token;
}

long LA_ToUtcMsc(const long serverMsc)
{
   if(serverMsc <= 0)
      return 0;
   datetime gmt = TimeGMT();
   datetime server = TimeTradeServer();
   if(gmt <= 0 || server <= 0)
      return serverMsc;
   long offsetMsc = ((long)server - (long)gmt) * 1000;
   return serverMsc - offsetMsc;
}

long LA_CurrentServerMsc()
{
   MqlTick tick;
   if(SymbolInfoTick(_Symbol, tick) && tick.time_msc > 0)
      return tick.time_msc;
   return (long)TimeCurrent() * 1000;
}

string LA_Double(const bool available, const double value, const int digits)
{
   return available ? DoubleToString(value, digits) : "UNAVAILABLE";
}

string LA_Long(const bool available, const long value)
{
   return available ? StringFormat("%I64d", value) : "UNAVAILABLE";
}

string LA_Position(const long value)
{
   return value > 0 ? StringFormat("%I64d", value) : "UNAVAILABLE";
}

string LA_NewPairId(const long armUtcMsc)
{
   string sequenceKey = StringFormat("LA1_%I64d_%I64d_%s",
                                     AccountInfoInteger(ACCOUNT_LOGIN),
                                     g_laMagic, LA_SanitizeToken(_Symbol));
   if(StringLen(sequenceKey) > 63)
      sequenceKey = StringSubstr(sequenceKey, 0, 63);
   long sequence = 1;
   if(GlobalVariableCheck(sequenceKey))
      sequence = (long)GlobalVariableGet(sequenceKey) + 1;
   GlobalVariableSet(sequenceKey, (double)sequence);
   return StringFormat("%s-%I64d-%I64d-%06d",
                       g_laTerminalId, g_laMagic, armUtcMsc, (int)sequence);
}

int LA_AddPair(const string path, const long armServerMsc,
               const bool explicitMembership)
{
   int index = ArraySize(g_laPairs);
   if(ArrayResize(g_laPairs, index + 1) != index + 1)
   {
      PrintFormat("LEG_ASYMMETRY RESOLUTION_ERROR ea=%s reason=pair_array_resize error=%d",
                  g_laEaName, GetLastError());
      return -1;
   }
   g_laPairs[index].active = true;
   g_laPairs[index].explicitMembership = explicitMembership;
   g_laPairs[index].path = path;
   g_laPairs[index].armUtcMsc = LA_ToUtcMsc(armServerMsc);
   g_laPairs[index].pairId = explicitMembership
                             ? LA_NewPairId(g_laPairs[index].armUtcMsc)
                             : StringFormat("PAIR_UNRESOLVED-MEMBERSHIP_NOT_ESTABLISHED-%s-%I64d",
                                            g_laTerminalId,
                                            g_laPairs[index].armUtcMsc);
   LA_ResetLeg(g_laPairs[index].buy, true);
   LA_ResetLeg(g_laPairs[index].sell, false);
   g_laPairs[index].mfeAvailable = false;
   g_laPairs[index].mfePoints = 0.0;
   return index;
}

void LA_RemovePair(const int index)
{
   int total = ArraySize(g_laPairs);
   if(index < 0 || index >= total)
      return;
   for(int i = index; i < total - 1; i++)
      g_laPairs[i] = g_laPairs[i + 1];
   ArrayResize(g_laPairs, total - 1);
}

bool LA_OpenCsv(int &handle, const bool forceAttempt = false)
{
   long nowMsc = LA_CurrentServerMsc();
   if(!forceAttempt && !g_laCsvReady && g_laLastCsvAttemptMsc > 0 &&
      nowMsc - g_laLastCsvAttemptMsc < LA_CSV_RETRY_INTERVAL_MSC)
   {
      handle = INVALID_HANDLE;
      return false;
   }
   g_laLastCsvAttemptMsc = nowMsc;
   ResetLastError();
   handle = FileOpen(g_laCsvName,
                     FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|
                     FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
   if(handle == INVALID_HANDLE)
   {
      g_laCsvReady = false;
      g_laLastCsvError = GetLastError();
      return false;
   }
   g_laCsvReady = true;
   g_laLastCsvError = 0;
   if(FileSize(handle) == 0)
   {
      uint headerWritten = FileWrite(handle,
         "schema_version", "terminal_id", "magic", "symbol", "pair_id", "path",
         "arm_utc_msc", "buy_trigger_price", "sell_trigger_price", "trigger_gap_points",
         "first_fill_leg", "first_fill_utc_msc", "first_fill_requested_price",
         "first_fill_actual_price", "first_fill_slip_points", "first_fill_spread_points",
         "second_leg_outcome", "second_fill_utc_msc", "second_fill_actual_price",
         "second_fill_slip_points", "second_fill_spread_points", "inter_leg_ms",
         "inter_leg_ticks", "traversal_points", "mfe_points_before_second_fill",
         "pair_label", "position_id_first", "position_id_second");
      if(headerWritten == 0)
      {
         g_laCsvReady = false;
         g_laLastCsvError = GetLastError();
         FileClose(handle);
         handle = INVALID_HANDLE;
         return false;
      }
      FileFlush(handle);
   }
   FileSeek(handle, 0, SEEK_END);
   return true;
}

double LA_SlipPoints(const LA_LegState &leg)
{
   if(_Point <= 0.0)
      return 0.0;
   return leg.isBuy
          ? (leg.actualPrice - leg.requestedPrice) / _Point
          : (leg.requestedPrice - leg.actualPrice) / _Point;
}

void LA_WritePair(const int index, const bool writeOpen)
{
   if(index < 0 || index >= ArraySize(g_laPairs))
      return;
   LA_PairState pair = g_laPairs[index];
   bool bothAssigned = pair.buy.assigned && pair.sell.assigned;
   int fills = (pair.buy.filled ? 1 : 0) + (pair.sell.filled ? 1 : 0);

   LA_LegState first;
   LA_LegState second;
   LA_ResetLeg(first, true);
   LA_ResetLeg(second, false);
   bool firstExists = false;
   bool secondExists = false;
   if(fills == 2)
   {
      if(pair.buy.fillUtcMsc <= pair.sell.fillUtcMsc)
      {
         first = pair.buy;
         second = pair.sell;
      }
      else
      {
         first = pair.sell;
         second = pair.buy;
      }
      firstExists = true;
      secondExists = true;
   }
   else if(fills == 1)
   {
      first = pair.buy.filled ? pair.buy : pair.sell;
      second = pair.buy.filled ? pair.sell : pair.buy;
      firstExists = true;
   }

   string firstLeg = "NO_FILL";
   if(fills == 2 && pair.buy.fillUtcMsc == pair.sell.fillUtcMsc)
      firstLeg = "BOTH_SAME_TICK";
   else if(firstExists)
      firstLeg = first.isBuy ? "BUY_STOP" : "SELL_STOP";

   string label = "PAIR_UNRESOLVED";
   if(pair.explicitMembership && bothAssigned && !writeOpen)
   {
      if(fills == 2)
      {
         long gap = second.fillUtcMsc - first.fillUtcMsc;
         if(gap == 0)
            label = "BOTH_SAME_TICK";
         else if(gap <= (long)InpSweepWindowMs)
            label = "SWEEP_BOTH";
         else
            label = "SEQUENTIAL_BOTH";
      }
      else if(fills == 1)
         label = "SINGLE_LEG";
      else
         label = "NO_FILL";
   }

   string secondOutcome = "UNAVAILABLE";
   if(fills == 2)
      secondOutcome = "FILLED";
   else if(fills == 1)
      secondOutcome = second.terminal ? second.terminalOutcome
                                      : "STILL_OPEN_AT_WRITE";
   else if(writeOpen && (!pair.buy.terminal || !pair.sell.terminal))
      secondOutcome = "STILL_OPEN_AT_WRITE";
   else if(pair.buy.terminal && pair.sell.terminal)
      secondOutcome = (pair.buy.terminalUtcMsc >= pair.sell.terminalUtcMsc)
                      ? pair.buy.terminalOutcome : pair.sell.terminalOutcome;

   bool gapAvailable = bothAssigned && pair.buy.requestedAvailable &&
                       pair.sell.requestedAvailable && _Point > 0.0;
   double triggerGap = gapAvailable
                       ? MathAbs(pair.buy.requestedPrice - pair.sell.requestedPrice) / _Point
                       : 0.0;
   bool bothFilled = (fills == 2);
   long interMs = bothFilled ? second.fillUtcMsc - first.fillUtcMsc : 0;
   long interTicks = bothFilled ? second.fillTick - first.fillTick : 0;
   bool traversalAvailable = bothFilled && first.requestedAvailable &&
                             second.requestedAvailable && _Point > 0.0;
   double traversal = traversalAvailable
                      ? MathAbs(second.requestedPrice - first.requestedPrice) / _Point
                      : 0.0;

   int handle = INVALID_HANDLE;
   if(!LA_OpenCsv(handle))
   {
      g_laLostRowsDegraded++;
      return;
   }
   uint written = FileWrite(handle,
      "1", g_laTerminalId, StringFormat("%I64d", g_laMagic), _Symbol,
      pair.pairId, pair.path,
      LA_Long(pair.armUtcMsc > 0, pair.armUtcMsc),
      LA_Double(pair.buy.assigned && pair.buy.requestedAvailable,
                pair.buy.requestedPrice, _Digits),
      LA_Double(pair.sell.assigned && pair.sell.requestedAvailable,
                pair.sell.requestedPrice, _Digits),
      LA_Double(gapAvailable, triggerGap, 1),
      firstLeg,
      LA_Long(firstExists, first.fillUtcMsc),
      LA_Double(firstExists && first.requestedAvailable,
                first.requestedPrice, _Digits),
      LA_Double(firstExists, first.actualPrice, _Digits),
      LA_Double(firstExists && first.requestedAvailable && _Point > 0.0,
                firstExists ? LA_SlipPoints(first) : 0.0, 1),
      LA_Double(firstExists && first.spreadAvailable, first.spreadPoints, 1),
      secondOutcome,
      LA_Long(secondExists, second.fillUtcMsc),
      LA_Double(secondExists, second.actualPrice, _Digits),
      LA_Double(secondExists && second.requestedAvailable && _Point > 0.0,
                secondExists ? LA_SlipPoints(second) : 0.0, 1),
      LA_Double(secondExists && second.spreadAvailable, second.spreadPoints, 1),
      LA_Long(bothFilled, interMs),
      LA_Long(bothFilled, interTicks),
      LA_Double(traversalAvailable, traversal, 1),
      LA_Double(firstExists && pair.mfeAvailable, pair.mfePoints, 1),
      label,
      firstExists ? LA_Position(first.positionId) : "UNAVAILABLE",
      secondExists ? LA_Position(second.positionId) : "UNAVAILABLE");
   if(written == 0)
   {
      g_laCsvReady = false;
      g_laLastCsvError = GetLastError();
      g_laLastCsvAttemptMsc = LA_CurrentServerMsc();
      g_laLostRowsDegraded++;
   }
   else
      g_laRowsWritten++;
   FileFlush(handle);
   FileClose(handle);
}

void LA_MaybeResolve(const int index)
{
   if(index < 0 || index >= ArraySize(g_laPairs) || !g_laPairs[index].active)
      return;
   bool bothAssigned = g_laPairs[index].buy.assigned && g_laPairs[index].sell.assigned;
   bool assignedTerminal = true;
   int assigned = 0;
   if(g_laPairs[index].buy.assigned)
   {
      assigned++;
      assignedTerminal = assignedTerminal && g_laPairs[index].buy.terminal;
   }
   if(g_laPairs[index].sell.assigned)
   {
      assigned++;
      assignedTerminal = assignedTerminal && g_laPairs[index].sell.terminal;
   }
   bool resolved = (bothAssigned && g_laPairs[index].buy.terminal &&
                     g_laPairs[index].sell.terminal) ||
                   (!bothAssigned && assigned > 0 && assignedTerminal);
   if(!resolved)
      return;
   LA_WritePair(index, false);
   LA_RemovePair(index);
}

int LA_FindByOrder(const ulong orderTicket, bool &isBuy)
{
   for(int i = 0; i < ArraySize(g_laPairs); i++)
   {
      if(g_laPairs[i].buy.assigned &&
         g_laPairs[i].buy.orderTicket == orderTicket)
      {
         isBuy = true;
         return i;
      }
      if(g_laPairs[i].sell.assigned &&
         g_laPairs[i].sell.orderTicket == orderTicket)
      {
         isBuy = false;
         return i;
      }
   }
   return -1;
}

void LA_AssignLeg(const int index, const bool isBuy,
                  const ulong orderTicket, const double requestedPrice,
                  const bool requestedAvailable = true)
{
   if(index < 0 || index >= ArraySize(g_laPairs))
      return;
   if(isBuy)
   {
      g_laPairs[index].buy.assigned = true;
      g_laPairs[index].buy.orderTicket = orderTicket;
      g_laPairs[index].buy.requestedAvailable = requestedAvailable;
      g_laPairs[index].buy.requestedPrice = requestedPrice;
   }
   else
   {
      g_laPairs[index].sell.assigned = true;
      g_laPairs[index].sell.orderTicket = orderTicket;
      g_laPairs[index].sell.requestedAvailable = requestedAvailable;
      g_laPairs[index].sell.requestedPrice = requestedPrice;
   }
}

void LA_ServerOrderPlaced(const bool isBuy, const ulong orderTicket,
                          const double requestedPrice, const long serverMsc)
{
   if(orderTicket == 0)
      return;
   for(int i = 0; i < ArraySize(g_laPairs); i++)
   {
      if(!g_laPairs[i].active || g_laPairs[i].path != "REAL")
         continue;
      LA_LegState same = isBuy ? g_laPairs[i].buy : g_laPairs[i].sell;
      LA_LegState opposite = isBuy ? g_laPairs[i].sell : g_laPairs[i].buy;
      if(!same.assigned && opposite.assigned && !opposite.terminal &&
         g_laPairs[i].explicitMembership)
      {
         LA_AssignLeg(i, isBuy, orderTicket, requestedPrice);
         return;
      }
   }
   int index = LA_AddPair("REAL", serverMsc, true);
   LA_AssignLeg(index, isBuy, orderTicket, requestedPrice);
}

void LA_ServerOrderModified(const ulong orderTicket, const double requestedPrice)
{
   bool isBuy = false;
   int index = LA_FindByOrder(orderTicket, isBuy);
   if(index < 0)
      return;
   if(isBuy)
   {
      g_laPairs[index].buy.requestedAvailable = true;
      g_laPairs[index].buy.requestedPrice = requestedPrice;
   }
   else
   {
      g_laPairs[index].sell.requestedAvailable = true;
      g_laPairs[index].sell.requestedPrice = requestedPrice;
   }
}

void LA_RecordFillAt(const int index, const bool isBuy, const double actualPrice,
                     const long fillServerMsc, const double spreadPoints,
                     const bool spreadAvailable, const long positionId)
{
   if(index < 0 || index >= ArraySize(g_laPairs))
      return;
   LA_LegState leg = isBuy ? g_laPairs[index].buy : g_laPairs[index].sell;
   if(leg.filled)
      return;
   leg.filled = true;
   leg.terminal = true;
   leg.terminalOutcome = "FILLED";
   leg.fillUtcMsc = LA_ToUtcMsc(fillServerMsc);
   leg.terminalUtcMsc = leg.fillUtcMsc;
   leg.fillTick = g_laTickSerial;
   leg.terminalTick = g_laTickSerial;
   leg.actualPrice = actualPrice;
   leg.spreadAvailable = spreadAvailable;
   leg.spreadPoints = spreadPoints;
   leg.positionId = positionId;
   if(isBuy)
      g_laPairs[index].buy = leg;
   else
      g_laPairs[index].sell = leg;
   int fills = (g_laPairs[index].buy.filled ? 1 : 0) +
               (g_laPairs[index].sell.filled ? 1 : 0);
   if(fills == 1)
   {
      g_laPairs[index].mfeAvailable = true;
      g_laPairs[index].mfePoints = 0.0;
   }
   LA_MaybeResolve(index);
}

void LA_ServerDeal(const ulong dealTicket)
{
   if(dealTicket == 0 || !HistoryDealSelect(dealTicket))
      return;
   ulong orderTicket = (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
   bool isBuy = false;
   int index = LA_FindByOrder(orderTicket, isBuy);
   if(index < 0)
      return;
   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
      return;
   MqlTick tick;
   bool spreadAvailable = SymbolInfoTick(_Symbol, tick) && _Point > 0.0;
   double spreadPoints = spreadAvailable ? (tick.ask - tick.bid) / _Point : 0.0;
   LA_RecordFillAt(index, isBuy,
                   HistoryDealGetDouble(dealTicket, DEAL_PRICE),
                   (long)HistoryDealGetInteger(dealTicket, DEAL_TIME_MSC),
                   spreadPoints, spreadAvailable,
                   (long)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID));
}

bool LA_FindAndRecordDeal(const ulong orderTicket)
{
   if(!HistorySelect(0, TimeCurrent()))
      return false;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 ||
         (ulong)HistoryDealGetInteger(deal, DEAL_ORDER) != orderTicket ||
         HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(deal, DEAL_MAGIC) != g_laMagic)
         continue;
      LA_ServerDeal(deal);
      return true;
   }
   return false;
}

void LA_MarkTerminal(const int index, const bool isBuy,
                     const string outcome, const long terminalServerMsc)
{
   if(index < 0 || index >= ArraySize(g_laPairs))
      return;
   LA_LegState leg = isBuy ? g_laPairs[index].buy : g_laPairs[index].sell;
   if(leg.terminal)
      return;
   leg.terminal = true;
   leg.terminalOutcome = outcome;
   leg.terminalUtcMsc = LA_ToUtcMsc(terminalServerMsc);
   leg.terminalTick = g_laTickSerial;
   if(isBuy)
      g_laPairs[index].buy = leg;
   else
      g_laPairs[index].sell = leg;
   LA_MaybeResolve(index);
}

void LA_PollServerLeg(const int index, const bool isBuy)
{
   if(index < 0 || index >= ArraySize(g_laPairs))
      return;
   LA_LegState leg = isBuy ? g_laPairs[index].buy : g_laPairs[index].sell;
   if(!leg.assigned || leg.terminal || leg.orderTicket == 0)
      return;
   if(OrderSelect(leg.orderTicket))
   {
      double currentPrice = OrderGetDouble(ORDER_PRICE_OPEN);
      if(currentPrice > 0.0)
         LA_ServerOrderModified(leg.orderTicket, currentPrice);
      return;
   }
   if(!HistoryOrderSelect(leg.orderTicket))
      return;
   ENUM_ORDER_STATE state = (ENUM_ORDER_STATE)HistoryOrderGetInteger(leg.orderTicket,
                                                                     ORDER_STATE);
   if(state == ORDER_STATE_FILLED && LA_FindAndRecordDeal(leg.orderTicket))
      return;
   long doneMsc = (long)HistoryOrderGetInteger(leg.orderTicket, ORDER_TIME_DONE_MSC);
   if(doneMsc <= 0)
      doneMsc = LA_CurrentServerMsc();
   if(state == ORDER_STATE_CANCELED || state == ORDER_STATE_REJECTED)
      LA_MarkTerminal(index, isBuy, "CANCELLED", doneMsc);
   else if(state == ORDER_STATE_EXPIRED)
      LA_MarkTerminal(index, isBuy, "EXPIRED", doneMsc);
}

void LA_ServerPoll()
{
   for(int i = ArraySize(g_laPairs) - 1; i >= 0; i--)
   {
      if(i >= ArraySize(g_laPairs) || g_laPairs[i].path != "REAL")
         continue;
      LA_PollServerLeg(i, true);
      if(i >= ArraySize(g_laPairs))
         continue;
      LA_PollServerLeg(i, false);
   }
}

void LA_ServerRecoverOpenOrders()
{
   int index = -1;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol ||
         OrderGetInteger(ORDER_MAGIC) != g_laMagic)
         continue;
      ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(type != ORDER_TYPE_BUY_STOP && type != ORDER_TYPE_SELL_STOP)
         continue;
      if(index < 0 ||
         (type == ORDER_TYPE_BUY_STOP && g_laPairs[index].buy.assigned) ||
         (type == ORDER_TYPE_SELL_STOP && g_laPairs[index].sell.assigned))
      {
         index = LA_AddPair("REAL", (long)OrderGetInteger(ORDER_TIME_SETUP_MSC), false);
         if(index >= 0)
            g_laPairs[index].pairId =
               StringFormat("PAIR_UNRESOLVED-PREINIT_MEMBERSHIP_NOT_PERSISTED-%s-%I64d",
                            g_laTerminalId, g_laPairs[index].armUtcMsc);
      }
      LA_AssignLeg(index, type == ORDER_TYPE_BUY_STOP, ticket,
                   OrderGetDouble(ORDER_PRICE_OPEN));
   }
}

int LA_FindVirtualPair()
{
   for(int i = 0; i < ArraySize(g_laPairs); i++)
      if(g_laPairs[i].active && g_laPairs[i].path == "VIRTUAL")
         return i;
   return -1;
}

void LA_VirtualSync(const double buyTrigger, const double sellTrigger,
                    const long serverMsc)
{
   int index = LA_FindVirtualPair();
   if(index < 0 && buyTrigger > 0.0 && sellTrigger > 0.0)
   {
      index = LA_AddPair("VIRTUAL", serverMsc, true);
      if(index >= 0)
      {
         LA_AssignLeg(index, true, 1, buyTrigger);
         LA_AssignLeg(index, false, 2, sellTrigger);
      }
      return;
   }
   if(index < 0)
      return;
   if(buyTrigger > 0.0 && !g_laPairs[index].buy.terminal)
   {
      g_laPairs[index].buy.requestedAvailable = true;
      g_laPairs[index].buy.requestedPrice = buyTrigger;
   }
   if(sellTrigger > 0.0 && !g_laPairs[index].sell.terminal)
   {
      g_laPairs[index].sell.requestedAvailable = true;
      g_laPairs[index].sell.requestedPrice = sellTrigger;
   }
   if(buyTrigger <= 0.0 && !g_laPairs[index].buy.terminal)
   {
      LA_MarkTerminal(index, true, "CANCELLED", serverMsc);
      index = LA_FindVirtualPair();
   }
   if(index >= 0 && sellTrigger <= 0.0 && !g_laPairs[index].sell.terminal)
      LA_MarkTerminal(index, false, "CANCELLED", serverMsc);
}

void LA_VirtualFill(const bool isBuy, const double actualPrice,
                    const long fillServerMsc, const double bid,
                    const double ask, const long positionId)
{
   int index = LA_FindVirtualPair();
   if(index < 0)
   {
      index = LA_AddPair("VIRTUAL", fillServerMsc, false);
      if(index < 0)
         return;
      g_laPairs[index].pairId =
         StringFormat("PAIR_UNRESOLVED-NO_ACTIVE_VIRTUAL_PAIR_AT_FILL-%s-%I64d",
                      g_laTerminalId, g_laPairs[index].armUtcMsc);
      LA_AssignLeg(index, isBuy, isBuy ? 1 : 2, 0.0, false);
   }
   bool spreadAvailable = (_Point > 0.0 && ask >= bid && bid > 0.0);
   double spreadPoints = spreadAvailable ? (ask - bid) / _Point : 0.0;
   LA_RecordFillAt(index, isBuy, actualPrice, fillServerMsc,
                   spreadPoints, spreadAvailable, positionId);
}

void LA_MarketTick(const long serverMsc, const double bid, const double ask)
{
   g_laTickSerial++;
   if(_Point <= 0.0)
      return;
   for(int i = 0; i < ArraySize(g_laPairs); i++)
   {
      int fills = (g_laPairs[i].buy.filled ? 1 : 0) +
                  (g_laPairs[i].sell.filled ? 1 : 0);
      if(fills != 1)
         continue;
      double excursion = g_laPairs[i].buy.filled
                         ? (bid - g_laPairs[i].buy.actualPrice) / _Point
                         : (g_laPairs[i].sell.actualPrice - ask) / _Point;
      if(excursion > g_laPairs[i].mfePoints)
         g_laPairs[i].mfePoints = excursion;
      g_laPairs[i].mfeAvailable = true;
   }
}

void LA_FlushOpenPairs()
{
   for(int i = ArraySize(g_laPairs) - 1; i >= 0; i--)
   {
      LA_WritePair(i, true);
      LA_RemovePair(i);
   }
}

bool LA_Initialize(const string eaName, const string csvName,
                   const string path, const long magic)
{
   g_laEaName = eaName;
   g_laCsvName = csvName;
   g_laMagic = magic;
   g_laTerminalId = LA_TerminalId();
   g_laTickSerial = 0;
   g_laRowsWritten = 0;
   g_laCsvReady = false;
   g_laLastCsvAttemptMsc = 0;
   g_laLastCsvError = 0;
   g_laLostRowsDegraded = 0;
   ArrayResize(g_laPairs, 0);

   int csvHandle = INVALID_HANDLE;
   if(LA_OpenCsv(csvHandle, true))
      FileClose(csvHandle);

   long digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   long fillingMode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   PrintFormat("LEG_ASYMMETRY INIT ea=%s schema=1 csv=%s terminal_id=%s magic=%I64d symbol=%s path=%s sweep_window_ms=%d csv_ready=%d csv_error=%d lost_rows_degraded=%d digits=%I64d point=%.10f tick_size=%.10f tick_value=%.10f stops_level_points=%I64d freeze_level_points=%I64d contract_size=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f filling_mode=%I64d account_currency=%s observer_only=1",
                eaName, csvName, g_laTerminalId, magic, _Symbol, path,
                InpSweepWindowMs, g_laCsvReady ? 1 : 0, g_laLastCsvError,
                g_laLostRowsDegraded, digits, point, tickSize, tickValue,
                stopsLevel, freezeLevel, contractSize, volumeMin,
                volumeMax, volumeStep, fillingMode, currency);
   return (InpSweepWindowMs >= 0 && point > 0.0 && tickSize > 0.0 &&
           volumeMin > 0.0 && volumeMax >= volumeMin && volumeStep > 0.0);
}

void LA_Poll()
{
   if(g_laCsvReady)
      return;
   int handle = INVALID_HANDLE;
   if(LA_OpenCsv(handle, false))
      FileClose(handle);
}

void LA_MarkCsvUnavailable(const int errorCode)
{
   g_laCsvReady = false;
   g_laLastCsvError = errorCode;
   g_laLastCsvAttemptMsc = LA_CurrentServerMsc();
}

bool LA_CsvReady() { return g_laCsvReady; }
int LA_LastCsvError() { return g_laLastCsvError; }
int LA_LostRowsDegraded() { return g_laLostRowsDegraded; }

#endif

// END INHERITED LegAsymmetryObserver_v1.mqh
// BEGIN INHERITED ExitAttribution_v1.mqh
#ifndef EXIT_ATTRIBUTION_V1_MQH
#define EXIT_ATTRIBUTION_V1_MQH

// Logging-only, position-keyed exit attribution shared by GM3 and
// FlashGoldVirtual. This observer never sends, modifies, or deletes trades.

struct XA_OpenMetric
{
   long   positionId;
   bool   isBuy;
   double entryPrice;
   double mfePoints;
   double maePoints;
};

string g_xaEaName = "";
string g_xaCsvName = "";
string g_xaLegCsvName = "";
string g_xaTerminalId = "";
string g_xaNamespace = "";
string g_xaSchema = "";
long   g_xaMagic = 0;
long   g_xaHistoryStartMsc = 0;
int    g_xaRowsThisRun = 0;
int    g_xaUnknownTagsThisRun = 0;
int    g_xaHistoryCloseEvents = 0;
int    g_xaLostRowsDegraded = 0;
bool   g_xaInitialized = false;
bool   g_xaExitCsvReady = false;
bool   g_xaExitStateKnown = false;
bool   g_xaLegCsvReady = false;
bool   g_xaLegStateKnown = false;
long   g_xaExitLastAttemptMsc = 0;
int    g_xaExitLastError = 0;
int    g_xaLegLastError = 0;
const long XA_RETRY_INTERVAL_MSC = 60000;
ulong  g_xaLostDealTickets[];
XA_OpenMetric g_xaOpenMetrics[];

string XA_SanitizeToken(string value)
{
   StringReplace(value, "\\", "_");
   StringReplace(value, "/", "_");
   StringReplace(value, ":", "_");
   StringReplace(value, " ", "_");
   StringReplace(value, ".", "_");
   return value;
}

string XA_TerminalId()
{
   string path = TerminalInfoString(TERMINAL_DATA_PATH);
   int last = -1;
   int pos = StringFind(path, "\\");
   while(pos >= 0)
   {
      last = pos;
      pos = StringFind(path, "\\", pos + 1);
   }
   string token = (last >= 0 ? StringSubstr(path, last + 1) : path);
   token = XA_SanitizeToken(token);
   return StringLen(token) > 0 ? token : "TERMINAL_UNKNOWN";
}

long XA_ToUtcMsc(const long serverMsc)
{
   if(serverMsc <= 0)
      return 0;
   datetime gmt = TimeGMT();
   datetime server = TimeTradeServer();
   if(gmt <= 0 || server <= 0)
      return serverMsc;
   return serverMsc - ((long)server - (long)gmt) * 1000;
}

string XA_Long(const bool available, const long value)
{
   return available ? StringFormat("%I64d", value) : "UNAVAILABLE";
}

string XA_ULong(const bool available, const ulong value)
{
   return available ? StringFormat("%llu", value) : "UNAVAILABLE";
}

string XA_Double(const bool available, const double value, const int digits)
{
   return available && MathIsValidNumber(value)
          ? DoubleToString(value, digits) : "UNAVAILABLE";
}

string XA_Bool(const bool value)
{
   return value ? "true" : "false";
}

int XA_TagCode(const string tag)
{
   if(tag == "EXIT_VIRTUAL_INITIAL_STOP") return 1;
   if(tag == "EXIT_PROFILE_ATR_INITIAL_STOP") return 2;
   if(tag == "EXIT_VIRTUAL_BREAKEVEN_STOP") return 3;
   if(tag == "EXIT_PROFILE_ATR_BREAKEVEN_STOP") return 4;
   if(tag == "EXIT_VIRTUAL_TRAILING_STOP") return 5;
   if(tag == "EXIT_PROFILE_ATR_TRAILING_STOP") return 6;
   if(tag == "EXIT_PROFILE_ATR_TIME_58") return 7;
   if(tag == "EXIT_SERVER_INITIAL_SL") return 8;
   if(tag == "EXIT_SERVER_PROFILE_INITIAL_SL") return 9;
   if(tag == "EXIT_SERVER_PROFILE_BREAKEVEN_SL") return 10;
   if(tag == "EXIT_SERVER_PROFILE_TRAILING_SL") return 11;
   if(tag == "EXIT_SERVER_DYNAMIC_TRAILING_SL") return 12;
   if(tag == "EXIT_VIRTUAL_STOP") return 13;
   if(tag == "EXIT_BREAKEVEN_STOP") return 14;
   if(tag == "EXIT_TRAILING_STOP") return 15;
   if(tag == "EXIT_TIME") return 16;
   if(tag == "EXIT_PROFIT") return 17;
   if(tag == "EXIT_DEFENSIVE") return 18;
   return 0;
}

string XA_TagFromCode(const int code)
{
   if(code == 1) return "EXIT_VIRTUAL_INITIAL_STOP";
   if(code == 2) return "EXIT_PROFILE_ATR_INITIAL_STOP";
   if(code == 3) return "EXIT_VIRTUAL_BREAKEVEN_STOP";
   if(code == 4) return "EXIT_PROFILE_ATR_BREAKEVEN_STOP";
   if(code == 5) return "EXIT_VIRTUAL_TRAILING_STOP";
   if(code == 6) return "EXIT_PROFILE_ATR_TRAILING_STOP";
   if(code == 7) return "EXIT_PROFILE_ATR_TIME_58";
   if(code == 8) return "EXIT_SERVER_INITIAL_SL";
   if(code == 9) return "EXIT_SERVER_PROFILE_INITIAL_SL";
   if(code == 10) return "EXIT_SERVER_PROFILE_BREAKEVEN_SL";
   if(code == 11) return "EXIT_SERVER_PROFILE_TRAILING_SL";
   if(code == 12) return "EXIT_SERVER_DYNAMIC_TRAILING_SL";
   if(code == 13) return "EXIT_VIRTUAL_STOP";
   if(code == 14) return "EXIT_BREAKEVEN_STOP";
   if(code == 15) return "EXIT_TRAILING_STOP";
   if(code == 16) return "EXIT_TIME";
   if(code == 17) return "EXIT_PROFIT";
   if(code == 18) return "EXIT_DEFENSIVE";
   return "";
}

string XA_StateKey(const long positionId, const string field)
{
   string key = StringFormat("XA1_%s_%I64d_%I64d_%I64d_%s",
                             g_xaNamespace,
                             AccountInfoInteger(ACCOUNT_LOGIN),
                             g_xaMagic, positionId, field);
   return StringLen(key) <= 63 ? key : StringSubstr(key, 0, 63);
}

void XA_StateDelete(const long positionId)
{
   string fields[] = {"T", "L", "TV", "TA", "HV", "HA", "RV", "RA"};
   for(int i = 0; i < ArraySize(fields); i++)
   {
      string key = XA_StateKey(positionId, fields[i]);
      if(GlobalVariableCheck(key))
         GlobalVariableDel(key);
   }
}

void XA_StampDecision(const long positionId,
                      const string exitTag,
                      const int branchLine,
                      const bool triggerAvailable,
                      const double triggerValue,
                      const bool thresholdAvailable,
                      const double thresholdValue,
                      const bool requestedPriceAvailable,
                      const double requestedPrice)
{
   if(!g_xaInitialized || positionId <= 0)
      return;
   int tagCode = XA_TagCode(exitTag);
   GlobalVariableSet(XA_StateKey(positionId, "T"), (double)tagCode);
   GlobalVariableSet(XA_StateKey(positionId, "L"), (double)branchLine);
   GlobalVariableSet(XA_StateKey(positionId, "TA"), triggerAvailable ? 1.0 : 0.0);
   GlobalVariableSet(XA_StateKey(positionId, "HA"), thresholdAvailable ? 1.0 : 0.0);
   GlobalVariableSet(XA_StateKey(positionId, "RA"), requestedPriceAvailable ? 1.0 : 0.0);
   if(triggerAvailable)
      GlobalVariableSet(XA_StateKey(positionId, "TV"), triggerValue);
   else if(GlobalVariableCheck(XA_StateKey(positionId, "TV")))
      GlobalVariableDel(XA_StateKey(positionId, "TV"));
   if(thresholdAvailable)
      GlobalVariableSet(XA_StateKey(positionId, "HV"), thresholdValue);
   else if(GlobalVariableCheck(XA_StateKey(positionId, "HV")))
      GlobalVariableDel(XA_StateKey(positionId, "HV"));
   if(requestedPriceAvailable)
      GlobalVariableSet(XA_StateKey(positionId, "RV"), requestedPrice);
   else if(GlobalVariableCheck(XA_StateKey(positionId, "RV")))
      GlobalVariableDel(XA_StateKey(positionId, "RV"));
}

void XA_UpdateRequestedPrice(const long positionId, const double requestedPrice)
{
   if(!g_xaInitialized || positionId <= 0 || requestedPrice <= 0.0)
      return;
   GlobalVariableSet(XA_StateKey(positionId, "RA"), 1.0);
   GlobalVariableSet(XA_StateKey(positionId, "RV"), requestedPrice);
}

bool XA_ReadDecision(const long positionId,
                     string &tag,
                     int &branchLine,
                     bool &triggerAvailable,
                     double &triggerValue,
                     bool &thresholdAvailable,
                     double &thresholdValue,
                     bool &requestedAvailable,
                     double &requestedPrice)
{
   tag = "";
   branchLine = 0;
   triggerAvailable = false;
   triggerValue = 0.0;
   thresholdAvailable = false;
   thresholdValue = 0.0;
   requestedAvailable = false;
   requestedPrice = 0.0;
   string tagKey = XA_StateKey(positionId, "T");
   if(!GlobalVariableCheck(tagKey))
      return false;
   tag = XA_TagFromCode((int)GlobalVariableGet(tagKey));
   string lineKey = XA_StateKey(positionId, "L");
   if(GlobalVariableCheck(lineKey))
      branchLine = (int)GlobalVariableGet(lineKey);
   string triggerFlag = XA_StateKey(positionId, "TA");
   triggerAvailable = GlobalVariableCheck(triggerFlag) &&
                      GlobalVariableGet(triggerFlag) > 0.5;
   string triggerKey = XA_StateKey(positionId, "TV");
   if(triggerAvailable && GlobalVariableCheck(triggerKey))
      triggerValue = GlobalVariableGet(triggerKey);
   else
      triggerAvailable = false;
   string thresholdFlag = XA_StateKey(positionId, "HA");
   thresholdAvailable = GlobalVariableCheck(thresholdFlag) &&
                        GlobalVariableGet(thresholdFlag) > 0.5;
   string thresholdKey = XA_StateKey(positionId, "HV");
   if(thresholdAvailable && GlobalVariableCheck(thresholdKey))
      thresholdValue = GlobalVariableGet(thresholdKey);
   else
      thresholdAvailable = false;
   string requestedFlag = XA_StateKey(positionId, "RA");
   requestedAvailable = GlobalVariableCheck(requestedFlag) &&
                        GlobalVariableGet(requestedFlag) > 0.5;
   string requestedKey = XA_StateKey(positionId, "RV");
   if(requestedAvailable && GlobalVariableCheck(requestedKey))
      requestedPrice = GlobalVariableGet(requestedKey);
   else
      requestedAvailable = false;
   return StringLen(tag) > 0;
}

int XA_FindMetric(const long positionId)
{
   for(int i = 0; i < ArraySize(g_xaOpenMetrics); i++)
      if(g_xaOpenMetrics[i].positionId == positionId)
         return i;
   return -1;
}

void XA_RemoveMetric(const int index)
{
   int total = ArraySize(g_xaOpenMetrics);
   if(index < 0 || index >= total)
      return;
   for(int i = index; i < total - 1; i++)
      g_xaOpenMetrics[i] = g_xaOpenMetrics[i + 1];
   ArrayResize(g_xaOpenMetrics, total - 1);
}

void XA_RegisterMetric(const long positionId, const bool isBuy,
                       const double entryPrice)
{
   if(positionId <= 0 || entryPrice <= 0.0)
      return;
   int index = XA_FindMetric(positionId);
   if(index < 0)
   {
      index = ArraySize(g_xaOpenMetrics);
      if(ArrayResize(g_xaOpenMetrics, index + 1) != index + 1)
         return;
      g_xaOpenMetrics[index].mfePoints = 0.0;
      g_xaOpenMetrics[index].maePoints = 0.0;
   }
   g_xaOpenMetrics[index].positionId = positionId;
   g_xaOpenMetrics[index].isBuy = isBuy;
   g_xaOpenMetrics[index].entryPrice = entryPrice;
}

bool XA_SelectPositionByIdentifier(const long positionId, ulong &ticket)
{
   ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong candidate = PositionGetTicket(i);
      if(candidate == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != g_xaMagic)
         continue;
      if(PositionGetInteger(POSITION_IDENTIFIER) == positionId)
      {
         ticket = candidate;
         return true;
      }
   }
   return false;
}

void XA_UpdateOpenMetrics()
{
   if(!g_xaInitialized || _Point <= 0.0)
      return;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
      return;
   double mid = (tick.bid + tick.ask) * 0.5;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != g_xaMagic)
         continue;
      long positionId = PositionGetInteger(POSITION_IDENTIFIER);
      bool isBuy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      XA_RegisterMetric(positionId, isBuy, entryPrice);
      int index = XA_FindMetric(positionId);
      if(index < 0)
         continue;
      double excursion = isBuy ? (mid - entryPrice) / _Point
                               : (entryPrice - mid) / _Point;
      if(excursion > g_xaOpenMetrics[index].mfePoints)
         g_xaOpenMetrics[index].mfePoints = excursion;
      if(-excursion > g_xaOpenMetrics[index].maePoints)
         g_xaOpenMetrics[index].maePoints = -excursion;
   }
}

long XA_ClockMsc()
{
   MqlTick tick;
   if(SymbolInfoTick(_Symbol, tick) && tick.time_msc > 0)
      return tick.time_msc;
   return (long)TimeCurrent() * 1000;
}

void XA_UpdateResourceState(const bool exitResource, const bool ready,
                            const int errorCode)
{
   bool known = exitResource ? g_xaExitStateKnown : g_xaLegStateKnown;
   bool previous = exitResource ? g_xaExitCsvReady : g_xaLegCsvReady;
   string resource = exitResource ? "EXIT_CSV" : "LEG_CSV";
   string fileName = exitResource ? g_xaCsvName : g_xaLegCsvName;
   if((known && previous != ready) || (!known && !ready))
   {
      if(ready)
         PrintFormat("%s EXIT_ATTRIBUTION RECOVERED resource=%s file=%s lost_rows_degraded=%d leg_lost_rows_degraded=%d",
                     g_xaEaName, resource, fileName, g_xaLostRowsDegraded,
                     LA_LostRowsDegraded());
      else
         PrintFormat("%s EXIT_ATTRIBUTION DEGRADED resource=%s file=%s error_code=%d trading_continues=1",
                     g_xaEaName, resource, fileName, errorCode);
   }
   if(exitResource)
   {
      g_xaExitStateKnown = true;
      g_xaExitCsvReady = ready;
      g_xaExitLastError = ready ? 0 : errorCode;
   }
   else
   {
      g_xaLegStateKnown = true;
      g_xaLegCsvReady = ready;
      g_xaLegLastError = ready ? 0 : errorCode;
   }
}

void XA_RecordDegradedRow(const ulong dealTicket)
{
   for(int i = 0; i < ArraySize(g_xaLostDealTickets); i++)
      if(g_xaLostDealTickets[i] == dealTicket)
         return;
   int index = ArraySize(g_xaLostDealTickets);
   if(ArrayResize(g_xaLostDealTickets, index + 1) == index + 1)
   {
      g_xaLostDealTickets[index] = dealTicket;
      g_xaLostRowsDegraded++;
   }
}

bool XA_OpenCsv(int &handle, bool &wasEmpty, const bool forceAttempt = false)
{
   wasEmpty = false;
   long nowMsc = XA_ClockMsc();
   if(!forceAttempt && !g_xaExitCsvReady && g_xaExitLastAttemptMsc > 0 &&
      nowMsc - g_xaExitLastAttemptMsc < XA_RETRY_INTERVAL_MSC)
   {
      handle = INVALID_HANDLE;
      return false;
   }
   g_xaExitLastAttemptMsc = nowMsc;
   ResetLastError();
   handle = FileOpen(g_xaCsvName,
                     FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|
                     FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
   if(handle == INVALID_HANDLE)
   {
      XA_UpdateResourceState(true, false, GetLastError());
      return false;
   }
   XA_UpdateResourceState(true, true, 0);
   wasEmpty = FileSize(handle) == 0;
   if(wasEmpty)
   {
      uint headerWritten = FileWrite(handle,
         "schema_version", "terminal_id", "magic", "symbol", "position_id",
         "order_ticket", "deal_ticket", "direction", "volume_closed",
         "is_partial_close", "remaining_volume", "open_utc_msc",
         "close_utc_msc", "duration_ms", "entry_actual_price",
         "exit_requested_price", "exit_actual_price", "exit_slip_points",
         "bid_at_close", "ask_at_close", "close_spread_points", "exit_tag",
         "exit_branch_line", "exit_trigger_value", "exit_threshold_value",
         "mfe_points", "mae_points", "profit_points", "close_initiator",
         "pair_id");
      if(headerWritten == 0)
      {
         int errorCode = GetLastError();
         XA_UpdateResourceState(true, false, errorCode);
         FileClose(handle);
         handle = INVALID_HANDLE;
         return false;
      }
      FileFlush(handle);
   }
   FileSeek(handle, 0, SEEK_END);
   return true;
}

bool XA_CheckLegCsv()
{
   // The leg observer owns this file.  It performs the single rate-limited
   // open attempt; attribution consumes its state without a second attempt.
   bool ready = LA_CsvReady();
   XA_UpdateResourceState(false, ready,
                          ready ? 0 : LA_LastCsvError());
   return ready;
}

bool XA_DealAlreadyWritten(const ulong dealTicket)
{
   if(!g_xaExitCsvReady)
      return false;
   ResetLastError();
   int handle = FileOpen(g_xaCsvName,
                         FILE_READ|FILE_CSV|FILE_ANSI|
                         FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
   if(handle == INVALID_HANDLE)
   {
      XA_UpdateResourceState(true, false, GetLastError());
      return false;
   }
   bool first = true;
   while(!FileIsEnding(handle))
   {
      string dealCell = "";
      for(int column = 0; column < 30 && !FileIsEnding(handle); column++)
      {
         string cell = FileReadString(handle);
         if(column == 6)
            dealCell = cell;
      }
      if(first)
      {
         first = false;
         continue;
      }
      if((ulong)StringToInteger(dealCell) == dealTicket)
      {
         FileClose(handle);
         return true;
      }
   }
   FileClose(handle);
   return false;
}

string XA_PairIdForPosition(const long positionId)
{
   if(positionId <= 0)
      return "UNAVAILABLE";
   // The pair can still be active when its first leg closes.  Read the
   // observer's in-memory identity before falling back to its completed CSV.
   for(int i = 0; i < ArraySize(g_laPairs); i++)
   {
      if((g_laPairs[i].buy.positionId == positionId ||
          g_laPairs[i].sell.positionId == positionId) &&
         StringLen(g_laPairs[i].pairId) > 0)
         return g_laPairs[i].pairId;
   }
   if(StringLen(g_xaLegCsvName) == 0 || !g_xaLegCsvReady)
      return "UNAVAILABLE";
   ResetLastError();
   int handle = FileOpen(g_xaLegCsvName,
                         FILE_READ|FILE_CSV|FILE_ANSI|
                         FILE_SHARE_READ|FILE_SHARE_WRITE, ',');
   if(handle == INVALID_HANDLE)
   {
      int errorCode = GetLastError();
      LA_MarkCsvUnavailable(errorCode);
      XA_UpdateResourceState(false, false, errorCode);
      return "UNAVAILABLE";
   }
   bool first = true;
   while(!FileIsEnding(handle))
   {
      string pairId = "";
      string firstPosition = "";
      string secondPosition = "";
      for(int column = 0; column < 27 && !FileIsEnding(handle); column++)
      {
         string cell = FileReadString(handle);
         if(column == 4) pairId = cell;
         if(column == 25) firstPosition = cell;
         if(column == 26) secondPosition = cell;
      }
      if(first)
      {
         first = false;
         continue;
      }
      string wanted = StringFormat("%I64d", positionId);
      if(firstPosition == wanted || secondPosition == wanted)
      {
         FileClose(handle);
         return StringLen(pairId) > 0 ? pairId : "UNAVAILABLE";
      }
   }
   FileClose(handle);
   return "UNAVAILABLE";
}

bool XA_EntryFacts(const long positionId,
                   bool &isBuy,
                   long &openServerMsc,
                   double &entryPrice,
                   ulong &entryDeal)
{
   isBuy = false;
   openServerMsc = 0;
   entryPrice = 0.0;
   entryDeal = 0;
   if(positionId <= 0 || !HistorySelectByPosition((ulong)positionId))
      return false;
   double weighted = 0.0;
   double volume = 0.0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0)
         continue;
      ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_IN && entry != DEAL_ENTRY_INOUT)
         continue;
      long dealMsc = (long)HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      if(openServerMsc == 0 || dealMsc < openServerMsc)
      {
         openServerMsc = dealMsc;
         entryDeal = deal;
         ENUM_DEAL_TYPE type =
            (ENUM_DEAL_TYPE)HistoryDealGetInteger(deal, DEAL_TYPE);
         isBuy = type == DEAL_TYPE_BUY;
      }
      double dealVolume = HistoryDealGetDouble(deal, DEAL_VOLUME);
      weighted += HistoryDealGetDouble(deal, DEAL_PRICE) * dealVolume;
      volume += dealVolume;
   }
   if(volume > 0.0)
      entryPrice = weighted / volume;
   return entryDeal > 0 && entryPrice > 0.0;
}

string XA_CloseInitiator(const long reasonCode)
{
   if(reasonCode == DEAL_REASON_EXPERT) return "EA";
   if(reasonCode == DEAL_REASON_SL) return "BROKER_SL";
   if(reasonCode == DEAL_REASON_TP) return "BROKER_TP";
   if(reasonCode == DEAL_REASON_SO) return "MARGIN";
   if(reasonCode == DEAL_REASON_CLIENT || reasonCode == DEAL_REASON_MOBILE ||
      reasonCode == DEAL_REASON_WEB) return "MANUAL";
   return "UNKNOWN";
}

bool XA_IsExternalInitiator(const string initiator)
{
   return initiator == "BROKER_SL" || initiator == "BROKER_TP" ||
          initiator == "MARGIN" || initiator == "MANUAL";
}

bool XA_LogCloseDeal(const ulong dealTicket, const bool liveEvent)
{
   if(!g_xaInitialized || dealTicket == 0 ||
      !HistoryDealSelect(dealTicket) || XA_DealAlreadyWritten(dealTicket))
      return false;
   if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol ||
      HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != g_xaMagic)
      return false;
   ENUM_DEAL_ENTRY entryType =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entryType != DEAL_ENTRY_OUT && entryType != DEAL_ENTRY_OUT_BY &&
      entryType != DEAL_ENTRY_INOUT)
      return false;

   long positionId = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
   ulong orderTicket =
      (ulong)HistoryDealGetInteger(dealTicket, DEAL_ORDER);
   long reasonCode = HistoryDealGetInteger(dealTicket, DEAL_REASON);
   string initiator = XA_CloseInitiator(reasonCode);
   long closeServerMsc =
      (long)HistoryDealGetInteger(dealTicket, DEAL_TIME_MSC);
   long closeUtcMsc = XA_ToUtcMsc(closeServerMsc);
   double actualPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
   double volumeClosed = HistoryDealGetDouble(dealTicket, DEAL_VOLUME);

   bool isBuy = false;
   long openServerMsc = 0;
   double entryPrice = 0.0;
   ulong entryDeal = 0;
   bool entryAvailable = XA_EntryFacts(positionId, isBuy, openServerMsc,
                                       entryPrice, entryDeal);
   if(!entryAvailable)
   {
      ENUM_DEAL_TYPE closeType =
         (ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE);
      isBuy = closeType == DEAL_TYPE_SELL;
   }
   long openUtcMsc = XA_ToUtcMsc(openServerMsc);

   ulong remainingTicket = 0;
   bool stillOpen = XA_SelectPositionByIdentifier(positionId, remainingTicket);
   double remainingVolume = stillOpen ? PositionGetDouble(POSITION_VOLUME) : 0.0;
   bool isPartial = stillOpen && remainingVolume > 0.0;

   string tag = "";
   int branchLine = 0;
   bool triggerAvailable = false;
   double triggerValue = 0.0;
   bool thresholdAvailable = false;
   double thresholdValue = 0.0;
   bool requestedAvailable = false;
   double requestedPrice = 0.0;
   bool decisionAvailable = XA_ReadDecision(positionId, tag, branchLine,
                                             triggerAvailable, triggerValue,
                                             thresholdAvailable, thresholdValue,
                                             requestedAvailable, requestedPrice);
   if(XA_IsExternalInitiator(initiator))
   {
      tag = "UNAVAILABLE";
      branchLine = 0;
      triggerAvailable = false;
      thresholdAvailable = false;
      if(reasonCode == DEAL_REASON_SL)
      {
         requestedPrice = HistoryDealGetDouble(dealTicket, DEAL_SL);
         requestedAvailable = requestedPrice > 0.0;
      }
      else if(reasonCode == DEAL_REASON_TP)
      {
         requestedPrice = HistoryDealGetDouble(dealTicket, DEAL_TP);
         requestedAvailable = requestedPrice > 0.0;
      }
   }
   else if(initiator == "EA" && (!decisionAvailable || StringLen(tag) == 0))
   {
      tag = "UNKNOWN";
      branchLine = 0;
      triggerAvailable = false;
      thresholdAvailable = false;
      g_xaUnknownTagsThisRun++;
      PrintFormat("%s EXIT_ATTRIBUTION UNKNOWN_TAG position_id=%I64d deal=%llu",
                  g_xaEaName, positionId, dealTicket);
   }
   else if(StringLen(tag) == 0)
      tag = "UNAVAILABLE";

   if(!requestedAvailable && orderTicket > 0 && HistoryOrderSelect(orderTicket))
   {
      requestedPrice = HistoryOrderGetDouble(orderTicket, ORDER_PRICE_OPEN);
      requestedAvailable = requestedPrice > 0.0;
   }

   MqlTick tick;
   bool quoteAvailable = liveEvent && SymbolInfoTick(_Symbol, tick) &&
                         tick.bid > 0.0 && tick.ask > 0.0;
   double slipPoints = 0.0;
   bool slipAvailable = requestedAvailable && actualPrice > 0.0 && _Point > 0.0;
   if(slipAvailable)
      slipPoints = isBuy ? (requestedPrice - actualPrice) / _Point
                         : (actualPrice - requestedPrice) / _Point;
   double profitPoints = 0.0;
   bool profitAvailable = entryAvailable && actualPrice > 0.0 && _Point > 0.0;
   if(profitAvailable)
      profitPoints = isBuy ? (actualPrice - entryPrice) / _Point
                           : (entryPrice - actualPrice) / _Point;

   int metricIndex = XA_FindMetric(positionId);
   bool metricAvailable = metricIndex >= 0;
   double mfe = metricAvailable ? g_xaOpenMetrics[metricIndex].mfePoints : 0.0;
   double mae = metricAvailable ? g_xaOpenMetrics[metricIndex].maePoints : 0.0;

   int handle = INVALID_HANDLE;
   bool wasEmpty = false;
   if(!XA_OpenCsv(handle, wasEmpty))
   {
      XA_RecordDegradedRow(dealTicket);
      return false;
   }
   uint written = FileWrite(handle,
      g_xaSchema, g_xaTerminalId,
      StringFormat("%I64d", g_xaMagic), _Symbol,
      XA_Long(positionId > 0, positionId),
      XA_ULong(orderTicket > 0, orderTicket),
      XA_ULong(true, dealTicket),
      isBuy ? "BUY" : "SELL",
      XA_Double(volumeClosed > 0.0, volumeClosed, 8),
      XA_Bool(isPartial),
      XA_Double(true, remainingVolume, 8),
      XA_Long(openUtcMsc > 0, openUtcMsc),
      XA_Long(closeUtcMsc > 0, closeUtcMsc),
      XA_Long(openUtcMsc > 0 && closeUtcMsc >= openUtcMsc,
              closeUtcMsc - openUtcMsc),
      XA_Double(entryAvailable, entryPrice, _Digits),
      XA_Double(requestedAvailable, requestedPrice, _Digits),
      XA_Double(actualPrice > 0.0, actualPrice, _Digits),
      XA_Double(slipAvailable, slipPoints, 1),
      XA_Double(quoteAvailable, quoteAvailable ? tick.bid : 0.0, _Digits),
      XA_Double(quoteAvailable, quoteAvailable ? tick.ask : 0.0, _Digits),
      XA_Double(quoteAvailable && _Point > 0.0,
                quoteAvailable ? (tick.ask - tick.bid) / _Point : 0.0, 1),
      tag,
      XA_Long(branchLine > 0, branchLine),
      XA_Double(triggerAvailable, triggerValue, 6),
      XA_Double(thresholdAvailable, thresholdValue, 6),
      XA_Double(metricAvailable, mfe, 1),
      XA_Double(metricAvailable, mae, 1),
      XA_Double(profitAvailable, profitPoints, 1),
      initiator,
      XA_PairIdForPosition(positionId));
   if(written > 0)
   {
      g_xaRowsThisRun++;
      FileFlush(handle);
   }
   else
   {
      int errorCode = GetLastError();
      XA_UpdateResourceState(true, false, errorCode);
      g_xaExitLastAttemptMsc = XA_ClockMsc();
      XA_RecordDegradedRow(dealTicket);
   }
   FileClose(handle);

   if(!isPartial)
   {
      XA_StateDelete(positionId);
      if(metricIndex >= 0)
         XA_RemoveMetric(metricIndex);
   }
   return written > 0;
}

void XA_OnTradeDeal(const ulong dealTicket)
{
   if(!g_xaInitialized || dealTicket == 0 || !HistoryDealSelect(dealTicket) ||
      HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol ||
      HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != g_xaMagic)
      return;
   ENUM_DEAL_ENTRY entry =
      (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY ||
      entry == DEAL_ENTRY_INOUT)
      XA_LogCloseDeal(dealTicket, true);
   if(entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
   {
      long positionId = HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
      ENUM_DEAL_TYPE type =
         (ENUM_DEAL_TYPE)HistoryDealGetInteger(dealTicket, DEAL_TYPE);
      XA_RegisterMetric(positionId, type == DEAL_TYPE_BUY,
                        HistoryDealGetDouble(dealTicket, DEAL_PRICE));
   }
}

void XA_ReconcileHistory()
{
   g_xaHistoryCloseEvents = 0;
   datetime from = (datetime)MathMax(0, g_xaHistoryStartMsc / 1000 - 1);
   if(!HistorySelect(from, TimeCurrent()))
      return;
   int total = HistoryDealsTotal();
   ulong closeDeals[];
   ArrayResize(closeDeals, 0);
   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(deal, DEAL_MAGIC) != g_xaMagic)
         continue;
      long dealMsc = (long)HistoryDealGetInteger(deal, DEAL_TIME_MSC);
      if(dealMsc < g_xaHistoryStartMsc)
         continue;
      ENUM_DEAL_ENTRY entry =
         (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY &&
         entry != DEAL_ENTRY_INOUT)
         continue;
      g_xaHistoryCloseEvents++;
      int index = ArraySize(closeDeals);
      if(ArrayResize(closeDeals, index + 1) == index + 1)
         closeDeals[index] = deal;
   }
   for(int i = 0; i < ArraySize(closeDeals); i++)
      XA_LogCloseDeal(closeDeals[i], false);
}

bool XA_Initialize(const string eaName,
                   const string csvName,
                   const string legCsvName,
                   const long magic)
{
   g_xaEaName = eaName;
   g_xaCsvName = csvName;
   g_xaLegCsvName = legCsvName;
   g_xaMagic = magic;
   g_xaTerminalId = XA_TerminalId();
   g_xaNamespace = XA_SanitizeToken(eaName);
   g_xaSchema = (eaName == "GM3"
                 ? "gm3.exitattribution.v1"
                 : "flashgoldvirtual.exitattribution.v1");
   if(StringLen(g_xaNamespace) > 8)
      g_xaNamespace = StringSubstr(g_xaNamespace, 0, 8);
   g_xaRowsThisRun = 0;
   g_xaUnknownTagsThisRun = 0;
   g_xaHistoryCloseEvents = 0;
   g_xaLostRowsDegraded = 0;
   g_xaExitCsvReady = false;
   g_xaExitStateKnown = false;
   g_xaLegCsvReady = false;
   g_xaLegStateKnown = false;
   g_xaExitLastAttemptMsc = 0;
   g_xaExitLastError = 0;
   g_xaLegLastError = 0;
   ArrayResize(g_xaLostDealTickets, 0);
   ArrayResize(g_xaOpenMetrics, 0);
   g_xaInitialized = true;

   int handle = INVALID_HANDLE;
   bool freshFile = false;
   if(XA_OpenCsv(handle, freshFile, true))
      FileClose(handle);
   LA_Poll();
   XA_CheckLegCsv();
   string startKey = StringFormat("XA1S_%s_%I64d_%I64d",
                                  g_xaNamespace,
                                  AccountInfoInteger(ACCOUNT_LOGIN), g_xaMagic);
   if(StringLen(startKey) > 63)
      startKey = StringSubstr(startKey, 0, 63);
   if(freshFile || !GlobalVariableCheck(startKey))
   {
      g_xaHistoryStartMsc = (long)TimeCurrent() * 1000;
      GlobalVariableSet(startKey, (double)g_xaHistoryStartMsc);
   }
   else
      g_xaHistoryStartMsc = (long)GlobalVariableGet(startKey);

   XA_UpdateOpenMetrics();
   if(g_xaExitCsvReady)
      XA_ReconcileHistory();

   long digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   long fillingMode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);
   PrintFormat("%s EXIT_ATTRIBUTION INIT schema=%s csv=%s terminal_id=%s magic=%I64d symbol=%s history_start_msc=%I64d history_close_events=%d rows_this_run=%d unknown_tags=%d lost_rows_degraded=%d degraded=%d exit_csv_ready=%d exit_csv_error=%d leg_csv_ready=%d leg_csv_error=%d leg_rows_this_run=%d leg_lost_rows_degraded=%d digits=%I64d point=%.10f tick_size=%.10f tick_value=%.10f stops_level_points=%I64d freeze_level_points=%I64d contract_size=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f filling_mode=%I64d account_currency=%s logging_only=1",
                eaName, g_xaSchema, csvName, g_xaTerminalId, magic, _Symbol,
                g_xaHistoryStartMsc, g_xaHistoryCloseEvents,
                g_xaRowsThisRun, g_xaUnknownTagsThisRun,
                g_xaLostRowsDegraded,
                (!g_xaExitCsvReady || !g_xaLegCsvReady) ? 1 : 0,
                g_xaExitCsvReady ? 1 : 0, g_xaExitLastError,
                g_xaLegCsvReady ? 1 : 0, g_xaLegLastError,
                g_laRowsWritten, LA_LostRowsDegraded(),
                digits, point, tickSize, tickValue, stopsLevel, freezeLevel,
                contractSize, volumeMin, volumeMax, volumeStep,
                fillingMode, currency);
   return true;
}

void XA_Poll()
{
   if(!g_xaInitialized)
      return;
   bool wasExitReady = g_xaExitCsvReady;
   if(!g_xaExitCsvReady)
   {
      int handle = INVALID_HANDLE;
      bool wasEmpty = false;
      if(XA_OpenCsv(handle, wasEmpty, false))
         FileClose(handle);
   }
   LA_Poll();
   if(!LA_CsvReady() && g_xaLegCsvReady)
      XA_UpdateResourceState(false, false, LA_LastCsvError());
   if(!g_xaLegCsvReady)
      XA_CheckLegCsv();
   if(!wasExitReady && g_xaExitCsvReady)
      XA_ReconcileHistory();
}

void XA_Deinitialize()
{
   if(!g_xaInitialized)
      return;
   PrintFormat("%s EXIT_ATTRIBUTION DEINIT history_close_events=%d rows_this_run=%d unknown_tags=%d lost_rows_degraded=%d degraded=%d exit_csv_ready=%d exit_csv_error=%d leg_csv_ready=%d leg_csv_error=%d leg_rows_this_run=%d leg_lost_rows_degraded=%d",
               g_xaEaName, XA_HistoryCloseEvents(), XA_RowsThisRun(),
               XA_UnknownTagsThisRun(), g_xaLostRowsDegraded,
               (!g_xaExitCsvReady || !g_xaLegCsvReady) ? 1 : 0,
               g_xaExitCsvReady ? 1 : 0, g_xaExitLastError,
               g_xaLegCsvReady ? 1 : 0, g_xaLegLastError,
               g_laRowsWritten, LA_LostRowsDegraded());
}

int XA_RowsThisRun() { return g_xaRowsThisRun; }
int XA_UnknownTagsThisRun() { return g_xaUnknownTagsThisRun; }
int XA_HistoryCloseEvents() { return g_xaHistoryCloseEvents; }
int XA_LostRowsDegraded() { return g_xaLostRowsDegraded; }
bool XA_Degraded() { return !g_xaExitCsvReady || !g_xaLegCsvReady; }

#endif

// END INHERITED ExitAttribution_v1.mqh

//--- Enums
enum ENUM_MM_TYPE
{
   MM_FIXED_LOTS,    // Fixed Lots (Old Way)
   MM_RISK_PERCENT   // Risk % of Equity (New Way)
};

enum ENUM_BURST_THRESHOLD_MODE
{
   BURST_THRESHOLD_FIXED = 0,
   BURST_THRESHOLD_PERCENTILE = 1
};

//--- Input Parameters
input group "--- Money Management ---"
input int      InpMagic          = 26090555;
input ENUM_MM_TYPE InpMMType     = MM_RISK_PERCENT; // Money Management Method
input double   InpRiskPercent    = 1.0;      // Risk % (if Risk Percent selected)
input double   InpFixedLots      = 0.1;      // Fixed Lots (if Fixed selected)
input double   InpMaxLots        = 5.0;      // Maximum Safety Lot Cap

input group "--- Cost & Spread Logic ---"
input double   InpMinSpreadPips  = 1.0;      // Minimum Spread Floor (Pips) used for calcs
input double   InpMaxEntrySpreadPoints = 50.0; // Maximum spread allowed for entry (Points)

input group "--- Virtual Entry Logic ---"
input double   InpEntryDistMult  = 2.0;      // Entry Distance = Spread * Multiplier
input int      InpModInterval    = 15;       // Seconds between entry modifications (Noise reduction)
   input bool     InpUseEntryHold        = true;   // Delayed favourable-move gate
   input int      InpEntryHoldMs          = 3000;   // Hold after signal (ms)
   input double   InpEntryHoldMinFavPoints = 5.0;   // Required favourable midpoint move (Points)
   input bool     InpUsePrior60Filter     = false;  // Friendly-60m direction gate
   input int      InpPrior60LookbackMin   = 60;     // Drift lookback (minutes)
   input int      InpBurstLookbackMs      = 1000;   // Burst midpoint displacement window (ms)
   input bool     InpUseBurstGate         = false;  // Burst bundle gate (magnitude/direction/continuation)
   input ENUM_BURST_THRESHOLD_MODE InpBurstThresholdMode = BURST_THRESHOLD_FIXED;
   input double   InpBurstPercentile      = 99.0;   // Rolling absolute-burst percentile
   input int      InpBurstWindowSamples   = 2000;   // Prior observations; current sample excluded

// --- PROPRIETARY TICK FRICTION ENGINE ---
input group "Tick Friction Coefficient (MKE)"
input bool             InpUseFriction      = true;          // Use Tick Friction Filter?
input double           InpMaxFriction      = 50.0;          // Max Volume per Point Allowed (Ice vs Mud)

input group "--- Virtual Stop & Trail ---"
input double   InpInitStopMult   = 3.0;      // Initial Virtual SL = Spread * Multiplier
input double   InpTrailStartMult = 2.0;      // Start Trailing when profit > Spread * Multiplier
input double   InpTrailStepMult  = 0.5;      // Trailing Step = Spread * Multiplier
input double   InpMinTrailingFloorPoints = 100.0; // Absolute inner trailing floor (Points)
input double   InpMaxTrailingFloorPoints = 200.0; // Absolute outer trailing floor (Points)
input double   InpTrailingLockInPoints = 8.0;     // Net points locked when trailing first arms

input group "--- Dashboard Settings ---"
input color    InpDashColor1     = clrWhite;      // Label Color
input color    InpDashColor2     = clrLime;       // Value Color (Good)
input color    InpDashColor3     = clrRed;        // Value Color (Bad/Risk)
input int      InpDashX          = 20;            // X Offset
input int      InpDashY          = 40;            // Y Offset
input int      InpFontSize       = 9;             // Font Size

input group "--- Master Order-Flow Telemetry Only ---"
input string   InpMasterGVPrefix    = "XPW_XAU_"; // Existing master GlobalVariable prefix
input int      InpMasterMaxStaleMs  = 4000;       // Existing master age limit in milliseconds

//--- Global Objects
CContinuationTrade         trade;
CPositionInfo  posInfo;

//--- Global Variables for Virtual Logic
double         g_VirtualBuyStopPrice  = 0.0;
double         g_VirtualSellStopPrice = 0.0;
datetime       g_LastModTime          = 0;

//--- Performance Optimization
uint           g_LastDashUpdate       = 0;    
const uint     InpDashUpdateRate      = 250; 

//--- Arrays to store Virtual SLs
struct VirtualPosition {
   ulong ticket;
   double virtualSL;
};
VirtualPosition g_VirtualPositions[];

struct StopFloorLogState
{
   ulong  ticket;
   double calculatedPoints;
   double floorPoints;
   double appliedPoints;
   string winningTerm;
};
StopFloorLogState g_StopFloorLogStates[];

//--- PROVISIONAL COST FLOOR (internal points; edit together after validation)
const double   PROVISIONAL_ENTRY_SPREAD_POINTS          = 25.0;
const double   PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS = 12.0;
const double   PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS    = 10.0;
const double   PROVISIONAL_ROUND_TRIP_COST_POINTS       =
                  PROVISIONAL_ENTRY_SPREAD_POINTS +
                  PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS +
                  PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS; // 47 points total
const double   COST_FLOOR_POINTS = PROVISIONAL_ROUND_TRIP_COST_POINTS; // 47-point hidden-stop floor
const double   LEGACY_COMPARISON_COST_POINTS            = 21.0; // reporting only

//--- Explicitly requested virtual-entry distance ceiling
const double   MAX_ENTRY_DISTANCE_POINTS = 60.0;

//--- Broker constraint safety margin applied above the live stops level
const double   BROKER_DISTANCE_BUFFER_POINTS = 3.0;

//--- Hard pre-entry signal gates and conflict-resolution limits
#define BURST_BUFFER_CAPACITY 20000
const double   BURST_MIN_POINTS            = 172.0;
const int      CONTINUATION_TICKS          = 5;

double         internalOrderDistance = 0.0;
double         internalMinTrailing   = 0.0;
double         internalMaxTrailing   = 0.0;
double         internalMultiplier    = 1.0;

long           g_BurstTimesMsc[BURST_BUFFER_CAPACITY];
double         g_BurstMidPrices[BURST_BUFFER_CAPACITY];
int            g_BurstHead             = 0;
int            g_BurstCount            = 0;
double         g_PreviousMidPrice       = 0.0;
int            g_UpTickStreak          = 0;
int            g_DownTickStreak        = 0;
datetime       g_LastEntryBar          = 0;

//--- Exact rolling Type-7 percentile state. Heap slots point into the ring.
double         g_BurstPercentileValues[];
int            g_BurstPercentileHeapType[]; // -1 none, 0 lower/max, 1 upper/min
int            g_BurstPercentileHeapPos[];
int            g_BurstLowerHeap[];
int            g_BurstUpperHeap[];
int            g_BurstPercentileCount    = 0;
int            g_BurstPercentileNextSlot = 0;
int            g_BurstLowerSize           = 0;
int            g_BurstUpperSize           = 0;

enum ENUM_ENTRY_HOLD_RESULT
{
   ENTRY_HOLD_WAIT = 0,
   ENTRY_HOLD_PASS = 1,
   ENTRY_HOLD_FAIL = 2
};

struct EntryHoldCandidate
{
   bool     active;
   bool     isBuy;
   long     signalTimeMsc;
   double   signalMidPrice;
   datetime signalBar;
};

EntryHoldCandidate g_EntryHoldCandidate;
datetime           g_LastEntryHoldFailureBar = 0;
string             g_MasterVwapTerminalId = "UNAVAILABLE";

//--- Tick Analytics Variables (Velocity & Friction)
const bool     InpUseTickVelocity       = false;
int            InpVelocityTicks         = 0;
double         currentTickVelocity      = 0.0;
double         currentTickFriction      = 0.0;

bool BurstLowerBefore(const int slotA, const int slotB)
{
   const double valueA = g_BurstPercentileValues[slotA];
   const double valueB = g_BurstPercentileValues[slotB];
   if(valueA > valueB) return true;
   if(valueA < valueB) return false;
   return slotA > slotB;
}

bool BurstUpperBefore(const int slotA, const int slotB)
{
   const double valueA = g_BurstPercentileValues[slotA];
   const double valueB = g_BurstPercentileValues[slotB];
   if(valueA < valueB) return true;
   if(valueA > valueB) return false;
   return slotA < slotB;
}

void SwapBurstLower(const int indexA, const int indexB)
{
   const int slotA = g_BurstLowerHeap[indexA];
   const int slotB = g_BurstLowerHeap[indexB];
   g_BurstLowerHeap[indexA] = slotB;
   g_BurstLowerHeap[indexB] = slotA;
   g_BurstPercentileHeapPos[slotA] = indexB;
   g_BurstPercentileHeapPos[slotB] = indexA;
}

void SwapBurstUpper(const int indexA, const int indexB)
{
   const int slotA = g_BurstUpperHeap[indexA];
   const int slotB = g_BurstUpperHeap[indexB];
   g_BurstUpperHeap[indexA] = slotB;
   g_BurstUpperHeap[indexB] = slotA;
   g_BurstPercentileHeapPos[slotA] = indexB;
   g_BurstPercentileHeapPos[slotB] = indexA;
}

void SiftBurstLowerUp(int index)
{
   while(index > 0)
   {
      const int parent = (index - 1) / 2;
      if(!BurstLowerBefore(g_BurstLowerHeap[index], g_BurstLowerHeap[parent])) break;
      SwapBurstLower(index, parent);
      index = parent;
   }
}

void SiftBurstLowerDown(int index)
{
   while(true)
   {
      const int left = index * 2 + 1;
      if(left >= g_BurstLowerSize) break;
      const int right = left + 1;
      int best = left;
      if(right < g_BurstLowerSize &&
         BurstLowerBefore(g_BurstLowerHeap[right], g_BurstLowerHeap[left]))
         best = right;
      if(!BurstLowerBefore(g_BurstLowerHeap[best], g_BurstLowerHeap[index])) break;
      SwapBurstLower(index, best);
      index = best;
   }
}

void SiftBurstUpperUp(int index)
{
   while(index > 0)
   {
      const int parent = (index - 1) / 2;
      if(!BurstUpperBefore(g_BurstUpperHeap[index], g_BurstUpperHeap[parent])) break;
      SwapBurstUpper(index, parent);
      index = parent;
   }
}

void SiftBurstUpperDown(int index)
{
   while(true)
   {
      const int left = index * 2 + 1;
      if(left >= g_BurstUpperSize) break;
      const int right = left + 1;
      int best = left;
      if(right < g_BurstUpperSize &&
         BurstUpperBefore(g_BurstUpperHeap[right], g_BurstUpperHeap[left]))
         best = right;
      if(!BurstUpperBefore(g_BurstUpperHeap[best], g_BurstUpperHeap[index])) break;
      SwapBurstUpper(index, best);
      index = best;
   }
}

void InsertBurstLower(const int slot)
{
   const int index = g_BurstLowerSize++;
   g_BurstLowerHeap[index] = slot;
   g_BurstPercentileHeapType[slot] = 0;
   g_BurstPercentileHeapPos[slot] = index;
   SiftBurstLowerUp(index);
}

void InsertBurstUpper(const int slot)
{
   const int index = g_BurstUpperSize++;
   g_BurstUpperHeap[index] = slot;
   g_BurstPercentileHeapType[slot] = 1;
   g_BurstPercentileHeapPos[slot] = index;
   SiftBurstUpperUp(index);
}

void RemoveBurstLowerAt(const int index)
{
   if(index < 0 || index >= g_BurstLowerSize) return;
   const int removedSlot = g_BurstLowerHeap[index];
   const int lastSlot = g_BurstLowerHeap[g_BurstLowerSize - 1];
   g_BurstLowerSize--;
   if(index < g_BurstLowerSize)
   {
      g_BurstLowerHeap[index] = lastSlot;
      g_BurstPercentileHeapPos[lastSlot] = index;
      const int parent = (index - 1) / 2;
      if(index > 0 && BurstLowerBefore(lastSlot, g_BurstLowerHeap[parent]))
         SiftBurstLowerUp(index);
      else
         SiftBurstLowerDown(index);
   }
   g_BurstPercentileHeapType[removedSlot] = -1;
   g_BurstPercentileHeapPos[removedSlot] = -1;
}

void RemoveBurstUpperAt(const int index)
{
   if(index < 0 || index >= g_BurstUpperSize) return;
   const int removedSlot = g_BurstUpperHeap[index];
   const int lastSlot = g_BurstUpperHeap[g_BurstUpperSize - 1];
   g_BurstUpperSize--;
   if(index < g_BurstUpperSize)
   {
      g_BurstUpperHeap[index] = lastSlot;
      g_BurstPercentileHeapPos[lastSlot] = index;
      const int parent = (index - 1) / 2;
      if(index > 0 && BurstUpperBefore(lastSlot, g_BurstUpperHeap[parent]))
         SiftBurstUpperUp(index);
      else
         SiftBurstUpperDown(index);
   }
   g_BurstPercentileHeapType[removedSlot] = -1;
   g_BurstPercentileHeapPos[removedSlot] = -1;
}

void RemoveBurstPercentileSlot(const int slot)
{
   const int heapType = g_BurstPercentileHeapType[slot];
   const int heapPosition = g_BurstPercentileHeapPos[slot];
   if(heapType == 0) RemoveBurstLowerAt(heapPosition);
   else if(heapType == 1) RemoveBurstUpperAt(heapPosition);
}

int BurstPercentileLowerTarget(const int sampleCount)
{
   if(sampleCount <= 0) return 0;
   const double rank = (sampleCount - 1) * (InpBurstPercentile / 100.0);
   return (int)MathFloor(rank) + 1;
}

void RebalanceBurstPercentileHeaps()
{
   const int target = BurstPercentileLowerTarget(g_BurstPercentileCount);
   while(g_BurstLowerSize > target)
   {
      const int slot = g_BurstLowerHeap[0];
      RemoveBurstLowerAt(0);
      InsertBurstUpper(slot);
   }
   while(g_BurstLowerSize < target && g_BurstUpperSize > 0)
   {
      const int slot = g_BurstUpperHeap[0];
      RemoveBurstUpperAt(0);
      InsertBurstLower(slot);
   }

   while(g_BurstLowerSize > 0 && g_BurstUpperSize > 0 &&
         g_BurstPercentileValues[g_BurstLowerHeap[0]] >
         g_BurstPercentileValues[g_BurstUpperHeap[0]])
   {
      const int lowerSlot = g_BurstLowerHeap[0];
      const int upperSlot = g_BurstUpperHeap[0];
      RemoveBurstLowerAt(0);
      RemoveBurstUpperAt(0);
      InsertBurstLower(upperSlot);
      InsertBurstUpper(lowerSlot);
   }
}

void InitializeBurstPercentileWindow()
{
   ArrayResize(g_BurstPercentileValues, InpBurstWindowSamples);
   ArrayResize(g_BurstPercentileHeapType, InpBurstWindowSamples);
   ArrayResize(g_BurstPercentileHeapPos, InpBurstWindowSamples);
   ArrayResize(g_BurstLowerHeap, InpBurstWindowSamples);
   ArrayResize(g_BurstUpperHeap, InpBurstWindowSamples);
   ArrayInitialize(g_BurstPercentileValues, 0.0);
   ArrayInitialize(g_BurstPercentileHeapType, -1);
   ArrayInitialize(g_BurstPercentileHeapPos, -1);
   g_BurstPercentileCount = 0;
   g_BurstPercentileNextSlot = 0;
   g_BurstLowerSize = 0;
   g_BurstUpperSize = 0;
}

void AddBurstPercentileSample(const double absoluteBurstPoints)
{
   if(!MathIsValidNumber(absoluteBurstPoints)) return;

   const int slot = g_BurstPercentileNextSlot;
   if(g_BurstPercentileCount == InpBurstWindowSamples)
      RemoveBurstPercentileSlot(slot);
   else
      g_BurstPercentileCount++;

   g_BurstPercentileValues[slot] = MathAbs(absoluteBurstPoints);
   if(g_BurstLowerSize == 0 ||
      g_BurstPercentileValues[slot] <=
      g_BurstPercentileValues[g_BurstLowerHeap[0]])
      InsertBurstLower(slot);
   else
      InsertBurstUpper(slot);

   RebalanceBurstPercentileHeaps();
   g_BurstPercentileNextSlot = (slot + 1) % InpBurstWindowSamples;
}

bool GetBurstPercentileThreshold(double &thresholdPoints, int &sampleCount)
{
   thresholdPoints = 0.0;
   sampleCount = g_BurstPercentileCount;
   if(sampleCount < InpBurstWindowSamples || g_BurstLowerSize <= 0)
      return false;

   RebalanceBurstPercentileHeaps();
   const double rank = (sampleCount - 1) * (InpBurstPercentile / 100.0);
   const double fraction = rank - MathFloor(rank);
   const double lowerValue = g_BurstPercentileValues[g_BurstLowerHeap[0]];
   thresholdPoints = lowerValue;
   if(fraction > 0.0 && g_BurstUpperSize > 0)
   {
      const double upperValue = g_BurstPercentileValues[g_BurstUpperHeap[0]];
      thresholdPoints = lowerValue + fraction * (upperValue - lowerValue);
   }
   return MathIsValidNumber(thresholdPoints);
}

string BurstThresholdModeName()
{
   return InpBurstThresholdMode == BURST_THRESHOLD_PERCENTILE
          ? "PERCENTILE" : "FIXED";
}

bool GetActiveBurstThreshold(double &thresholdPoints, int &sampleCount)
{
   if(InpBurstThresholdMode == BURST_THRESHOLD_FIXED)
   {
      thresholdPoints = BURST_MIN_POINTS;
      sampleCount = g_BurstPercentileCount;
      return true;
   }
   return GetBurstPercentileThreshold(thresholdPoints, sampleCount);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!CP_Init()) return INIT_PARAMETERS_INCORRECT;
   if(!XPWF_Init()) return INIT_PARAMETERS_INCORRECT;
   if(InpBurstPercentile < 0.0 || InpBurstPercentile > 100.0 ||
      InpBurstWindowSamples < 2 || InpBurstLookbackMs <= 0 ||
      InpEntryHoldMs < 0 || InpEntryHoldMinFavPoints < 0.0)
   {
      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT invalid gate settings burst_percentile=%.4f burst_window_samples=%d burst_lookback_ms=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f",
                  InpBurstPercentile, InpBurstWindowSamples,
                  InpBurstLookbackMs, InpEntryHoldMs,
                  InpEntryHoldMinFavPoints);
      return(INIT_PARAMETERS_INCORRECT);
   }

   InitializeBurstPercentileWindow();
   g_MasterVwapTerminalId = MasterVwapTerminalIdFromDataPath();

   if(!ValidateAndLogBrokerProfile())
      return(INIT_FAILED);

   // Set the Magic Number properly using the input we just defined
   trade.SetExpertMagicNumber(InpMagic); 

   // Measurement only. The return value is intentionally not used as a gate.
   LA_Initialize("FlashGold_Continuation_v2", "FlashGold_Continuation_v2_LegAsymmetry_v1.csv",
                 "VIRTUAL", InpMagic);
   // Logging is observational: file contention must never gate trading.
   XA_Initialize("FlashGold_Continuation_v2",
                 "FlashGold_Continuation_v2_ExitAttribution_v1.csv",
                 "FlashGold_Continuation_v2_LegAsymmetry_v1.csv", InpMagic);
   EventSetTimer(1);
   
   trade.SetMarginMode();
   trade.SetTypeFillingBySymbol(Symbol());

   LoadVirtualSLs();
   RestoreLastEntryBar();

   PrintFormat("PROVISIONAL COST FLOOR REPORT_HEADER entry_spread_assumption_points=%.1f commission_round_trip_points=%.1f slippage_allowance_points=%.1f combined_round_trip_points=%.1f maximum_entry_distance_points=%.1f burst_gate_active=%d burst_threshold_mode=%s burst_fixed_threshold_points=%.1f burst_percentile=%.4f burst_window_samples=%d current_sample_excluded=1 entry_hold_active=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f",
               PROVISIONAL_ENTRY_SPREAD_POINTS,
               PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS,
               PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS,
               PROVISIONAL_ROUND_TRIP_COST_POINTS,
               MAX_ENTRY_DISTANCE_POINTS,
               InpUseBurstGate ? 1 : 0,
               BurstThresholdModeName(), BURST_MIN_POINTS,
               InpBurstPercentile, InpBurstWindowSamples,
               InpUseEntryHold ? 1 : 0, InpEntryHoldMs,
               InpEntryHoldMinFavPoints);
   PrintFormat("FlashGold_Continuation_v2 MASTER_VWAP_TELEMETRY_INIT prefix=%s max_stale_ms=%d terminal_id=%s mode=OBSERVE_ONLY",
               InpMasterGVPrefix, InpMasterMaxStaleMs,
               g_MasterVwapTerminalId);
   
   // Clean up any old visual objects
   ObjectsDeleteAll(0, "V_Entry_");
   ObjectsDeleteAll(0, "V_SL_");
   ObjectsDeleteAll(0, "Lbl_"); 
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   XPWF_Report();
   CP_Deinit();
   LA_FlushOpenPairs();
   XA_ReconcileHistory();
   XA_Deinitialize();
   EventKillTimer();
   SaveVirtualSLs();
   ObjectsDeleteAll(0, "V_Entry_");
   ObjectsDeleteAll(0, "V_SL_");
   ObjectsDeleteAll(0, "Lbl_"); 
}

void OnTimer()
{
   XA_Poll();
}

bool FindTesterEntryDeal(const ulong positionId, double &entryPrice,
                         ENUM_DEAL_TYPE &entryDealType)
{
   const int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
   {
      const ulong deal=HistoryDealGetTicket(i);
      if(deal==0) continue;
      if((ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID)!=positionId) continue;
      if(HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) continue;
      if(HistoryDealGetInteger(deal,DEAL_MAGIC)!=InpMagic) continue;

      const ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;

      entryPrice=HistoryDealGetDouble(deal,DEAL_PRICE);
      entryDealType=(ENUM_DEAL_TYPE)HistoryDealGetInteger(deal,DEAL_TYPE);
      return (entryPrice>0.0 &&
              (entryDealType==DEAL_TYPE_BUY || entryDealType==DEAL_TYPE_SELL));
   }
   return false;
}

double OnTester()
{
   PrintFormat("PROVISIONAL COST FLOOR REPORT_HEADER entry_spread_assumption_points=%.1f commission_round_trip_points=%.1f slippage_allowance_points=%.1f combined_round_trip_points=%.1f legacy_comparison_points=%.1f maximum_entry_distance_points=%.1f",
               PROVISIONAL_ENTRY_SPREAD_POINTS,
               PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS,
               PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS,
               PROVISIONAL_ROUND_TRIP_COST_POINTS,
               LEGACY_COMPARISON_COST_POINTS,
               MAX_ENTRY_DISTANCE_POINTS);

   if(!HistorySelect(0,TimeCurrent()))
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 REPORT_FAILED reason=history_select error=%d",
                  GetLastError());
      return 0.0;
   }

   const double point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   int trades=0;
   int provisionalWins=0;
   int legacyWins=0;
   double provisionalNetSum=0.0;
   double legacyNetSum=0.0;
   double provisionalGrossProfit=0.0;
   double provisionalGrossLoss=0.0;
   double legacyGrossProfit=0.0;
   double legacyGrossLoss=0.0;

   const int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
   {
      const ulong exitDeal=HistoryDealGetTicket(i);
      if(exitDeal==0) continue;
      if(HistoryDealGetString(exitDeal,DEAL_SYMBOL)!=_Symbol) continue;
      if(HistoryDealGetInteger(exitDeal,DEAL_MAGIC)!=InpMagic) continue;

      const ENUM_DEAL_ENTRY exitEntry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(exitDeal,DEAL_ENTRY);
      if(exitEntry!=DEAL_ENTRY_OUT && exitEntry!=DEAL_ENTRY_OUT_BY) continue;

      const ulong positionId=(ulong)HistoryDealGetInteger(exitDeal,DEAL_POSITION_ID);
      double entryPrice=0.0;
      ENUM_DEAL_TYPE entryDealType=DEAL_TYPE_BUY;
      if(positionId==0 || !FindTesterEntryDeal(positionId,entryPrice,entryDealType)) continue;

      const double exitPrice=HistoryDealGetDouble(exitDeal,DEAL_PRICE);
      if(exitPrice<=0.0 || point<=0.0) continue;

      const double grossPoints=(entryDealType==DEAL_TYPE_BUY)
                               ? (exitPrice-entryPrice)/point
                               : (entryPrice-exitPrice)/point;
      const double provisionalNetPoints=grossPoints-PROVISIONAL_ROUND_TRIP_COST_POINTS;
      const double legacyNetPoints=grossPoints-LEGACY_COMPARISON_COST_POINTS;

      trades++;
      provisionalNetSum+=provisionalNetPoints;
      legacyNetSum+=legacyNetPoints;

      if(provisionalNetPoints>0.0)
      {
         provisionalWins++;
         provisionalGrossProfit+=provisionalNetPoints;
      }
      else
         provisionalGrossLoss+=MathAbs(provisionalNetPoints);

      if(legacyNetPoints>0.0)
      {
         legacyWins++;
         legacyGrossProfit+=legacyNetPoints;
      }
      else
         legacyGrossLoss+=MathAbs(legacyNetPoints);
   }

   const double provisionalWinRate=(trades>0) ? 100.0*provisionalWins/trades : 0.0;
   const double legacyWinRate=(trades>0) ? 100.0*legacyWins/trades : 0.0;
   const double provisionalNetPerTrade=(trades>0) ? provisionalNetSum/trades : 0.0;
   const double legacyNetPerTrade=(trades>0) ? legacyNetSum/trades : 0.0;
   const double provisionalProfitFactor=(provisionalGrossLoss>0.0)
                                          ? provisionalGrossProfit/provisionalGrossLoss
                                          : (provisionalGrossProfit>0.0 ? 999999.0 : 0.0);
   const double legacyProfitFactor=(legacyGrossLoss>0.0)
                                     ? legacyGrossProfit/legacyGrossLoss
                                     : (legacyGrossProfit>0.0 ? 999999.0 : 0.0);

   PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 REPORT_SUMMARY trades=%d provisional_cost_points=%.1f provisional_win_rate=%.4f provisional_net_points_per_trade=%.6f provisional_profit_factor=%.6f legacy_cost_points=%.1f legacy_win_rate=%.4f legacy_net_points_per_trade=%.6f legacy_profit_factor=%.6f",
               trades,
               PROVISIONAL_ROUND_TRIP_COST_POINTS,
               provisionalWinRate,
               provisionalNetPerTrade,
               provisionalProfitFactor,
               LEGACY_COMPARISON_COST_POINTS,
               legacyWinRate,
               legacyNetPerTrade,
               legacyProfitFactor);
   return provisionalProfitFactor;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   XPWF_OnTick();
   if(XPWF_SideStateChanged()) g_LastModTime = 0;   // window edge: refresh entry levels now, not in <=InpModInterval s
   CP_OnTick();
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double ask = tick.ask;
   double bid = tick.bid;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double midPrice = (ask + bid) * 0.5;
   long tickTimeMsc = tick.time_msc;
   if(tickTimeMsc <= 0) tickTimeMsc = (long)TimeCurrent() * 1000;

   LA_MarketTick(tickTimeMsc, bid, ask);
   XA_UpdateOpenMetrics();

   UpdateTickSignals(tickTimeMsc, midPrice);
   InpVelocityTicks = g_BurstCount;
   UpdateTickPhysics();
   
   double realSpread = (ask - bid);
   double calcSpread = MathMax(realSpread, InpMinSpreadPips * 10 * point);

   // --- CRITICAL TRADING LOGIC ---
   ManageOpenPositions(ask, bid, calcSpread, point);

   if(realSpread <= EffectiveMaxEntrySpread(point))
   {
      ManageVirtualPendings(ask, bid, calcSpread, point, tickTimeMsc, midPrice);
   }
   else
   {
      g_VirtualBuyStopPrice = 0;
      g_VirtualSellStopPrice = 0;
      ObjectDelete(0, "V_Entry_Buy");
      ObjectDelete(0, "V_Entry_Sell");
   }

   LA_VirtualSync(g_VirtualBuyStopPrice, g_VirtualSellStopPrice,
                  tickTimeMsc);

   // The decision above sees only prior observations. Add this tick afterward.
   CaptureBurstPercentileSample(tickTimeMsc, midPrice, point);
   
   // --- DASHBOARD ---
   if((!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE)) &&
      GetTickCount() - g_LastDashUpdate > InpDashUpdateRate)
   {
      DrawVirtualLevels();  
      UpdateDashboard();    
      g_LastDashUpdate = GetTickCount(); 
      ChartRedraw();        
   }
}

//+------------------------------------------------------------------+
//| MONEY MANAGEMENT LOGIC                                           |
//+------------------------------------------------------------------+
double FloorVolumeToStep(double volume, double step)
{
   if(volume <= 0.0 || step <= 0.0) return 0.0;
   return NormalizeDouble(MathFloor((volume / step) + 1e-9) * step, 8);
}

bool AccountCurrencyLossForMove(ENUM_ORDER_TYPE orderType,
                                double entryPrice,
                                double exitPrice,
                                double &lossMoney)
{
   lossMoney = 0.0;
   double profit = 0.0;
   ResetLastError();
   if(!OrderCalcProfit(orderType, _Symbol, 1.0, entryPrice, exitPrice, profit))
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ORDER_CALC_PROFIT_FAILED symbol=%s order_type=%d entry=%.10f exit=%.10f error=%d",
                  _Symbol, (int)orderType, entryPrice, exitPrice, GetLastError());
      return false;
   }

   lossMoney = MathAbs(profit);
   return true;
}

bool CalculateLossPerLot(ENUM_ORDER_TYPE orderType,
                         double entryPrice,
                         double intendedStopPrice,
                         double &stopLossMoney,
                         double &commissionMoney,
                         double &slippageMoney,
                         double &totalLossMoney)
{
   stopLossMoney = 0.0;
   commissionMoney = 0.0;
   slippageMoney = 0.0;
   totalLossMoney = 0.0;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0.0 || entryPrice <= 0.0 || intendedStopPrice <= 0.0)
      return false;

   if((orderType == ORDER_TYPE_BUY && intendedStopPrice >= entryPrice) ||
      (orderType == ORDER_TYPE_SELL && intendedStopPrice <= entryPrice))
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 INVALID_RISK_GEOMETRY symbol=%s order_type=%d entry=%.10f intended_stop=%.10f",
                  _Symbol, (int)orderType, entryPrice, intendedStopPrice);
      return false;
   }

   double commissionExit = (orderType == ORDER_TYPE_BUY)
                           ? entryPrice - PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS * point
                           : entryPrice + PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS * point;
   double slippageExit = (orderType == ORDER_TYPE_BUY)
                         ? entryPrice - PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS * point
                         : entryPrice + PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS * point;

   if(!AccountCurrencyLossForMove(orderType, entryPrice, intendedStopPrice, stopLossMoney) ||
      !AccountCurrencyLossForMove(orderType, entryPrice, commissionExit, commissionMoney) ||
      !AccountCurrencyLossForMove(orderType, entryPrice, slippageExit, slippageMoney))
      return false;

   totalLossMoney = stopLossMoney + commissionMoney + slippageMoney;
   return (totalLossMoney > 0.0);
}

double CalculateLotSize(ENUM_ORDER_TYPE orderType,
                        double entryPrice,
                        double intendedStopPrice,
                        bool logDetails = true)
{
   double minLots = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLots = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLots = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minLots <= 0.0 || maxLots <= 0.0 || stepLots <= 0.0)
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 INVALID_VOLUME_PROFILE symbol=%s min=%.8f max=%.8f step=%.8f",
                  _Symbol, minLots, maxLots, stepLots);
      return 0.0;
   }

   double effectiveMaxLots = MathMin(maxLots, InpMaxLots);
   effectiveMaxLots = FloorVolumeToStep(effectiveMaxLots, stepLots);
   if(effectiveMaxLots < minLots)
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 INVALID_VOLUME_CAP symbol=%s broker_min=%.8f effective_max=%.8f",
                  _Symbol, minLots, effectiveMaxLots);
      return 0.0;
   }

   double rawLots = InpFixedLots;
   double riskMoney = 0.0;
   double stopLossMoney = 0.0;
   double commissionMoney = 0.0;
   double slippageMoney = 0.0;
   double totalLossPerLot = 0.0;

   if(InpMMType == MM_RISK_PERCENT)
   {
      double equity = AccountInfoDouble(ACCOUNT_EQUITY);
      riskMoney = equity * (InpRiskPercent / 100.0);
      if(equity <= 0.0 || riskMoney <= 0.0 ||
         !CalculateLossPerLot(orderType, entryPrice, intendedStopPrice,
                              stopLossMoney, commissionMoney,
                              slippageMoney, totalLossPerLot))
         return 0.0;

      rawLots = riskMoney / totalLossPerLot;
   }

   double roundedLots = FloorVolumeToStep(rawLots, stepLots);
   double lots = MathMax(minLots, MathMin(roundedLots, effectiveMaxLots));
   lots = NormalizeDouble(lots, 8);

   if(logDetails)
   {
      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 LOT_SIZING symbol=%s account_currency=%s order_type=%d mode=%d risk_money=%.2f entry=%.10f intended_stop=%.10f stop_loss_per_lot=%.2f commission_per_lot=%.2f slippage_per_lot=%.2f total_loss_per_lot=%.2f raw_lots=%.8f rounded_down_lots=%.8f final_lots=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f",
                  _Symbol, AccountInfoString(ACCOUNT_CURRENCY), (int)orderType,
                  (int)InpMMType, riskMoney, entryPrice, intendedStopPrice,
                  stopLossMoney, commissionMoney, slippageMoney, totalLossPerLot,
                  rawLots, roundedLots, lots, minLots, effectiveMaxLots, stepLots); }
   }

   return lots;
}

//+------------------------------------------------------------------+
//| Ownership, account-mode and risk helpers                         |
//+------------------------------------------------------------------+
bool ValidateAndLogBrokerProfile()
{
   bool selected = (bool)SymbolInfoInteger(_Symbol, SYMBOL_SELECT);
   bool synchronized = SymbolIsSynchronized(_Symbol);
   if(!selected || !synchronized)
   {
      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT symbol=%s selected=%d synchronized=%d message=Symbol must be selected in Market Watch and fully synchronized before initialization",
                  _Symbol, selected ? 1 : 0, synchronized ? 1 : 0);
      return false;
   }

   long digits = SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freezeLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double volumeMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volumeMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volumeStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   long fillingMode = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   string accountCurrency = AccountInfoString(ACCOUNT_CURRENCY);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);

   const double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   const double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   const double calibratedSpreadPoints = (point > 0.0)
                                         ? MathMax((ask - bid) / point, 1.0)
                                         : 1.0;
   internalOrderDistance = MathMax(InpTrailStartMult, 0.0);
   internalMinTrailing = MathMax(InpMinTrailingFloorPoints, 0.0) /
                         calibratedSpreadPoints;
   internalMaxTrailing = MathMax(InpMaxTrailingFloorPoints, 0.0) /
                         calibratedSpreadPoints;
   internalMaxTrailing = MathMax(internalMaxTrailing,
                                  internalMinTrailing);
   internalMultiplier = (internalMinTrailing > 0.0)
                        ? MathMax(internalMaxTrailing /
                                  internalMinTrailing, 1.0)
                        : 1.0;

   PrintFormat("FlashGold_Continuation_v2 BROKER_PROFILE symbol=%s digits=%I64d point=%.10f tick_size=%.10f trade_stops_level_points=%I64d freeze_level_points=%I64d contract_size=%.8f volume_min=%.8f volume_max=%.8f volume_step=%.8f filling_mode=%I64d account_currency=%s leverage=1:%I64d calibration_spread_points=%.1f internal_order_distance=%.8f internal_min_trailing=%.8f internal_max_trailing=%.8f internal_multiplier=%.8f internal_feed=SYMBOL_SPREAD_PLUS_INPUTS",
               _Symbol, digits, point, tickSize, stopsLevel, freezeLevel,
               contractSize, volumeMin, volumeMax, volumeStep, fillingMode,
               accountCurrency, leverage, calibratedSpreadPoints,
               internalOrderDistance, internalMinTrailing,
               internalMaxTrailing, internalMultiplier);
   return true;
}

string StopFloorWinningTerm(const double calculatedPoints,
                            const double floorPoints,
                            const string floorTerm)
{
   const double loggedCalculated = NormalizeDouble(calculatedPoints, 1);
   const double loggedFloor = NormalizeDouble(floorPoints, 1);
   if(loggedCalculated == loggedFloor) return "TIE";
   return (loggedCalculated > loggedFloor) ? "CALCULATED" : floorTerm;
}

bool ShouldEmitStopFloor(const ulong ticket,
                         const double calculatedPoints,
                         const double floorPoints,
                         const double appliedPoints,
                         const string winningTerm)
{
   const double loggedCalculated = NormalizeDouble(calculatedPoints, 1);
   const double loggedFloor = NormalizeDouble(floorPoints, 1);
   const double loggedApplied = NormalizeDouble(appliedPoints, 1);
   const int count = ArraySize(g_StopFloorLogStates);
   for(int i = 0; i < count; i++)
   {
      if(g_StopFloorLogStates[i].ticket != ticket) continue;
      if(g_StopFloorLogStates[i].calculatedPoints == loggedCalculated &&
         g_StopFloorLogStates[i].floorPoints == loggedFloor &&
         g_StopFloorLogStates[i].appliedPoints == loggedApplied &&
         g_StopFloorLogStates[i].winningTerm == winningTerm)
         return false;

      g_StopFloorLogStates[i].calculatedPoints = loggedCalculated;
      g_StopFloorLogStates[i].floorPoints = loggedFloor;
      g_StopFloorLogStates[i].appliedPoints = loggedApplied;
      g_StopFloorLogStates[i].winningTerm = winningTerm;
      return true;
   }

   const int index = ArraySize(g_StopFloorLogStates);
   ArrayResize(g_StopFloorLogStates, index + 1);
   g_StopFloorLogStates[index].ticket = ticket;
   g_StopFloorLogStates[index].calculatedPoints = loggedCalculated;
   g_StopFloorLogStates[index].floorPoints = loggedFloor;
   g_StopFloorLogStates[index].appliedPoints = loggedApplied;
   g_StopFloorLogStates[index].winningTerm = winningTerm;
   return true;
}

bool BrokerFloorDistance(double calculatedDistancePrice,
                         double point,
                         string context,
                         double &appliedDistancePrice,
                         long &stopsLevel,
                         ulong ticket = 0)
{
   appliedDistancePrice = 0.0;
   stopsLevel = 0;
   if(point <= 0.0)
      return false;

   ResetLastError();
   if(!SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL, stopsLevel) || stopsLevel < 0)
   {
      PrintFormat("FlashGold_Continuation_v2 STOPS_LEVEL_READ_FAILED symbol=%s error=%d",
                  _Symbol, GetLastError());
      return false;
   }

   double brokerFloorPrice = ((double)stopsLevel + BROKER_DISTANCE_BUFFER_POINTS) * point;
   appliedDistancePrice = MathMax(calculatedDistancePrice, brokerFloorPrice);
   const double calculatedPoints = calculatedDistancePrice / point;
   const double floorPoints = brokerFloorPrice / point;
   const double appliedPoints = appliedDistancePrice / point;
   const string winningTerm = StopFloorWinningTerm(calculatedPoints,
                                                   floorPoints,
                                                   "SYMBOL_STOPS_LEVEL");
   if(ShouldEmitStopFloor(ticket, calculatedPoints, floorPoints,
                          appliedPoints, winningTerm))
      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("STOP_FLOOR ticket=%I64u context=%s path=BROKER calculated_distance_points=%.1f floor_value_points=%.1f applied_distance_points=%.1f winning_term=%s",
                  ticket, context, calculatedPoints, floorPoints,
                  appliedPoints, winningTerm); }
   return true;
}

bool VirtualFloorDistance(double calculatedDistancePrice,
                           double point,
                           string context,
                           double &appliedDistancePrice,
                           bool writeLog = true,
                           ulong ticket = 0)
{
   appliedDistancePrice = 0.0;
   if(point <= 0.0)
      return false;

   double virtualFloorPrice = COST_FLOOR_POINTS * point;
   appliedDistancePrice = MathMax(calculatedDistancePrice, virtualFloorPrice);
   const double calculatedPoints = calculatedDistancePrice / point;
   const double floorPoints = virtualFloorPrice / point;
   const double appliedPoints = appliedDistancePrice / point;
   const string winningTerm = StopFloorWinningTerm(calculatedPoints,
                                                   floorPoints,
                                                   "ABS_FLOOR");

   if(writeLog && ShouldEmitStopFloor(ticket, calculatedPoints, floorPoints,
                                      appliedPoints, winningTerm))
   {
      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("STOP_FLOOR ticket=%I64u context=%s path=VIRTUAL calculated_distance_points=%.1f floor_value_points=%.1f applied_distance_points=%.1f winning_term=%s",
                  ticket, context, calculatedPoints, floorPoints,
                  appliedPoints, winningTerm); }
   }
   return true;
}

bool IsOwnSelectedPosition()
{
   return (posInfo.Symbol() == _Symbol && posInfo.Magic() == InpMagic);
}

bool IsNettingAccount()
{
   ENUM_ACCOUNT_MARGIN_MODE mode = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   return (mode == ACCOUNT_MARGIN_MODE_RETAIL_NETTING || mode == ACCOUNT_MARGIN_MODE_EXCHANGE);
}

double EffectiveMaxEntrySpread(double point)
{
   return MathMax(InpMaxEntrySpreadPoints, 0.0) * point;
}

string MasterVwapTerminalIdFromDataPath()
{
   string dataPath = TerminalInfoString(TERMINAL_DATA_PATH);
   StringReplace(dataPath, "/", "\\");
   for(int i = StringLen(dataPath) - 1; i >= 0; --i)
   {
      if(StringGetCharacter(dataPath, i) == 92)
         return StringSubstr(dataPath, i + 1);
   }
   return (StringLen(dataPath) > 0 ? dataPath : "UNAVAILABLE");
}

string MasterVwapBoolText(const bool value)
{
   return value ? "true" : "false";
}

string MasterVwapCsvEscape(string value)
{
   StringReplace(value, "\"", "\"\"");
   return "\"" + value + "\"";
}

void MasterVwapCsvAdd(string &row, const string value)
{
   if(StringLen(row) > 0)
      row += ",";
   row += MasterVwapCsvEscape(value);
}

bool MasterVwapReadScalar(const string suffix, double &value)
{
   if(StringLen(InpMasterGVPrefix) <= 0)
      return false;
   string name = InpMasterGVPrefix + suffix;
   if(!GlobalVariableCheck(name))
      return false;
   value = GlobalVariableGet(name);
   return true;
}

void CaptureMasterVwapTelemetry(string &vwapValue,
                                string &vwapValid,
                                string &vwapAgeMs,
                                string &vwapContributors,
                                string &vwapDegraded)
{
   vwapValue = "";
   vwapValid = "false";
   vwapAgeMs = "";
   vwapContributors = "";
   vwapDegraded = "true";

   if(MQLInfoInteger(MQL_TESTER) || StringLen(InpMasterGVPrefix) <= 0)
      return;

   if(!GlobalVariableCheck(InpMasterGVPrefix + "OK") ||
      !GlobalVariableCheck(InpMasterGVPrefix + "HEARTBEAT"))
      return;

   double heartbeat = GlobalVariableGet(InpMasterGVPrefix + "HEARTBEAT");
   double ageMs = (double)GetTickCount64() - heartbeat;
   vwapAgeMs = StringFormat("%I64d", (long)MathRound(ageMs));

   if(GlobalVariableGet(InpMasterGVPrefix + "OK") < 0.5 ||
      ageMs < 0.0 || ageMs > (double)InpMasterMaxStaleMs)
      return;

   double validRaw = 0.0;
   if(!MasterVwapReadScalar("VWAP_VALID", validRaw))
      return;

   bool valid = (validRaw > 0.5);
   vwapValid = MasterVwapBoolText(valid);
   if(!valid)
      return;

   double contributors = 0.0;
   double vwapPrice = 0.0;
   if(!MasterVwapReadScalar("LIVE_FEEDS", contributors) ||
      !MasterVwapReadScalar("VWAP_PRICE", vwapPrice))
      return;

   vwapContributors = IntegerToString((int)MathRound(contributors));
   vwapValue = DoubleToString(vwapPrice, _Digits);
   vwapDegraded = "false";
}

void WriteMasterVwapDecision(const bool isBuy,
                             const long decisionMsc,
                             const double brokerMid,
                             const string decisionStage)
{
   // Legacy telemetry only; continuation and deal exports stay enabled.
   if(MQLInfoInteger(MQL_TESTER)) return;
   string vwapValue = "";
   string vwapValid = "false";
   string vwapAgeMs = "";
   string vwapContributors = "";
   string vwapDegraded = "true";
   CaptureMasterVwapTelemetry(vwapValue,
                              vwapValid,
                              vwapAgeMs,
                              vwapContributors,
                              vwapDegraded);

   string header = "";
   MasterVwapCsvAdd(header, "schema_version");
   MasterVwapCsvAdd(header, "terminal_id");
   MasterVwapCsvAdd(header, "magic");
   MasterVwapCsvAdd(header, "decision_utc_msc");
   MasterVwapCsvAdd(header, "symbol");
   MasterVwapCsvAdd(header, "direction");
   MasterVwapCsvAdd(header, "decision_stage");
   MasterVwapCsvAdd(header, "master_vwap_value");
   MasterVwapCsvAdd(header, "master_vwap_valid");
   MasterVwapCsvAdd(header, "master_vwap_age_ms");
   MasterVwapCsvAdd(header, "master_vwap_contributors");
   MasterVwapCsvAdd(header, "broker_mid");
   MasterVwapCsvAdd(header, "master_vwap_degraded");

   string row = "";
   MasterVwapCsvAdd(row, "1");
   MasterVwapCsvAdd(row, g_MasterVwapTerminalId);
   MasterVwapCsvAdd(row, IntegerToString(InpMagic));
   MasterVwapCsvAdd(row, StringFormat("%I64d", decisionMsc));
   MasterVwapCsvAdd(row, _Symbol);
   MasterVwapCsvAdd(row, isBuy ? "BUY" : "SELL");
   MasterVwapCsvAdd(row, decisionStage);
   MasterVwapCsvAdd(row, vwapValue);
   MasterVwapCsvAdd(row, vwapValid);
   MasterVwapCsvAdd(row, vwapAgeMs);
   MasterVwapCsvAdd(row, vwapContributors);
   MasterVwapCsvAdd(row, brokerMid > 0.0 ? DoubleToString(brokerMid, _Digits) : "");
   MasterVwapCsvAdd(row, vwapDegraded);

   int h = FileOpen("FlashGold_Continuation_v2_MasterVwapDecision_v1.csv",
                    FILE_READ | FILE_WRITE | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      Print("FlashGold_Continuation_v2 MASTER_VWAP_DECISION_FILE_OPEN_FAILED error=", GetLastError());
      return;
   }
   FileSeek(h, 0, SEEK_END);
   if(FileSize(h) == 0)
      FileWriteString(h, header + "\r\n");
   FileWriteString(h, row + "\r\n");
   FileClose(h);
}
void CalculateTrailingGeometry(double liveSpread, double point,
                               double &innerEdgePoints, double &outerEdgePoints,
                               double &trailingBufferPoints)
{
   double spreadPoints = (point > 0) ? liveSpread / point : 0.0;
   innerEdgePoints = MathMax(spreadPoints * internalMinTrailing,
                             InpMinTrailingFloorPoints);

   double scaledOuterPoints = spreadPoints * internalMaxTrailing;
   double geometricOuterPoints = innerEdgePoints * internalMultiplier;
   outerEdgePoints = MathMax(MathMax(scaledOuterPoints,
                                     InpMaxTrailingFloorPoints),
                             geometricOuterPoints);

   double requestedBufferPoints = spreadPoints * InpTrailStepMult;
   trailingBufferPoints = MathMin(MathMax(requestedBufferPoints, innerEdgePoints),
                                  outerEdgePoints);
}

void LogTrailingArm(string side, ulong ticket,
                    double requestedActivationPoints,
                    double costSafeActivationPoints,
                    double finalActivationPoints,
                    double actualActivationPoints,
                    double currentSpreadPoints,
                    double trailingBufferPoints,
                    double innerEdgePoints,
                    double outerEdgePoints)
{
   PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 TRAILING_ARM side=%s ticket=%I64u requested_activation_points=%.1f cost_safe_activation_points=%.1f final_activation_points=%.1f actual_activation_points=%.1f current_spread_points=%.1f trailing_buffer_points=%.1f lock_in_points=%.1f inner_edge_points=%.1f outer_edge_points=%.1f combined_round_trip_points=%.1f",
               side, ticket, requestedActivationPoints, costSafeActivationPoints,
               finalActivationPoints, actualActivationPoints, currentSpreadPoints,
               trailingBufferPoints, InpTrailingLockInPoints, innerEdgePoints,
               outerEdgePoints, PROVISIONAL_ROUND_TRIP_COST_POINTS);
}

void UpdateTickSignals(long tickTimeMsc, double midPrice)
{
   if(g_PreviousMidPrice > 0)
   {
      if(midPrice > g_PreviousMidPrice)
      {
         g_UpTickStreak++;
         g_DownTickStreak = 0;
      }
      else if(midPrice < g_PreviousMidPrice)
      {
         g_DownTickStreak++;
         g_UpTickStreak = 0;
      }
      else
      {
         g_UpTickStreak = 0;
         g_DownTickStreak = 0;
      }
   }
   g_PreviousMidPrice = midPrice;

   if(g_BurstCount == BURST_BUFFER_CAPACITY)
   {
      g_BurstHead = (g_BurstHead + 1) % BURST_BUFFER_CAPACITY;
      g_BurstCount--;
   }

   int insertIndex = (g_BurstHead + g_BurstCount) % BURST_BUFFER_CAPACITY;
   g_BurstTimesMsc[insertIndex] = tickTimeMsc;
   g_BurstMidPrices[insertIndex] = midPrice;
   g_BurstCount++;

   long cutoff = tickTimeMsc - InpBurstLookbackMs;
   while(g_BurstCount > 1)
   {
      int nextIndex = (g_BurstHead + 1) % BURST_BUFFER_CAPACITY;
      if(g_BurstTimesMsc[nextIndex] > cutoff) break;
      g_BurstHead = nextIndex;
      g_BurstCount--;
   }
}

//+------------------------------------------------------------------+
//| The Physics Engine: Tick Velocity & Friction Coefficient         |
//+------------------------------------------------------------------+
void UpdateTickPhysics() {
    if(!InpUseTickVelocity && !InpUseFriction) return;
    
    MqlTick ticks[];
    int copied = CopyTicks(_Symbol, ticks, COPY_TICKS_ALL, 0, InpVelocityTicks);
    
    if(copied > 1) {
        double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
        
        // 1. Calculate Velocity (Net Distance Traveled)
        double netDistancePts = (ticks[copied-1].bid - ticks[0].bid) / point;
        currentTickVelocity = netDistancePts;
        
        // 2. Calculate Friction (Effort vs Result)
        if(InpUseFriction) {
            double totalVolume = 0;
            for(int i = 0; i < copied; i++) {
                totalVolume += (ticks[i].volume_real > 0) ? (double)ticks[i].volume_real : 1.0;
            }
            
            double absoluteDistance = MathAbs(netDistancePts);
            if(absoluteDistance < 1.0) absoluteDistance = 1.0; 
            
            currentTickFriction = totalVolume / absoluteDistance;
        }
    }
}

bool GetBurstSpeed(long tickTimeMsc, double midPrice, double point, double &burstPoints)
{
   burstPoints = 0.0;
   if(point <= 0 || g_BurstCount < 2) return false;

   long cutoff = tickTimeMsc - InpBurstLookbackMs;
   if(g_BurstTimesMsc[g_BurstHead] > cutoff) return false;

   burstPoints = (midPrice - g_BurstMidPrices[g_BurstHead]) / point;
   return true;
}

void CaptureBurstPercentileSample(long tickTimeMsc, double midPrice, double point)
{
   double burstPoints = 0.0;
   if(GetBurstSpeed(tickTimeMsc, midPrice, point, burstPoints))
      AddBurstPercentileSample(MathAbs(burstPoints));
}

datetime CurrentEntryBar()
{
   return iTime(_Symbol, PERIOD_M1, 0);
}

bool HasEnteredCurrentBar()
{
   datetime currentBar = CurrentEntryBar();
   return (currentBar > 0 && g_LastEntryBar == currentBar);
}

bool HasEntryHoldFailureCurrentBar()
{
   datetime currentBar = CurrentEntryBar();
   return (currentBar > 0 && g_LastEntryHoldFailureBar == currentBar);
}

void MarkCurrentBarEntered()
{
   g_LastEntryBar = CurrentEntryBar();
}

void RestoreLastEntryBar()
{
   datetime currentBar = CurrentEntryBar();
   if(currentBar <= 0 || !HistorySelect(currentBar, TimeCurrent())) return;

   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong dealTicket = HistoryDealGetTicket(i);
      if(dealTicket == 0) continue;
      if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != InpMagic) continue;

      ENUM_DEAL_ENTRY entryType = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
      if(entryType != DEAL_ENTRY_IN && entryType != DEAL_ENTRY_INOUT) continue;

      g_LastEntryBar = currentBar;
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_BAR_RESTORED symbol=%s magic=%d bar=%s deal=%I64u",
                  _Symbol, InpMagic, TimeToString(currentBar, TIME_DATE | TIME_MINUTES), dealTicket);
      return;
   }
}

bool EntryCandidateApproved(bool isBuy, long tickTimeMsc, double midPrice, double point)
{
   double burstPoints = 0.0;
   const bool burstAvailable = GetBurstSpeed(tickTimeMsc, midPrice, point,
                                             burstPoints);
   double burstThresholdPoints = 0.0;
   int burstThresholdSampleCount = 0;
   const bool burstThresholdAvailable =
      GetActiveBurstThreshold(burstThresholdPoints,
                              burstThresholdSampleCount);

   // InpUseBurstGate controls the complete legacy burst bundle. When OFF,
   // magnitude, sign and five-tick continuation are diagnostic only.
   const bool burstSpeedPassed = !InpUseBurstGate ||
                                 (burstAvailable &&
                                  burstThresholdAvailable &&
                                  MathAbs(burstPoints) >= burstThresholdPoints);
   const bool burstDirectionPassed = !InpUseBurstGate ||
                                     (burstAvailable &&
                                      ((isBuy && burstPoints > 0.0) ||
                                       (!isBuy && burstPoints < 0.0)));
   const bool continuationPassed = !InpUseBurstGate ||
                                   (isBuy
                                    ? (g_UpTickStreak >= CONTINUATION_TICKS)
                                    : (g_DownTickStreak >= CONTINUATION_TICKS));
   const bool burstGateSurvived = burstSpeedPassed &&
                                  burstDirectionPassed &&
                                  continuationPassed;
   const bool frictionPassed = !InpUseFriction ||
                               currentTickFriction <= InpMaxFriction;
   const bool oneEntryPerBarPassed = !HasEnteredCurrentBar() &&
                                     !HasEntryHoldFailureCurrentBar();

   { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_CANDIDATE side=%s crossing=1 burst_gate_active=%d burst_threshold_mode=%s burst_available=%d burst_points=%.1f burst_threshold_available=%d burst_threshold_points=%.1f burst_fixed_threshold_points=%.1f burst_percentile=%.4f burst_window_samples=%d burst_window_target=%d current_sample_excluded=1 burst_magnitude_pass=%d burst_direction_pass=%d continuation_pass=%d burst_gate_survived=%d friction_pass=%d one_entry_per_bar_pass=%d",
               isBuy ? "BUY" : "SELL",
               InpUseBurstGate ? 1 : 0,
               BurstThresholdModeName(),
               burstAvailable ? 1 : 0, burstPoints,
               burstThresholdAvailable ? 1 : 0,
               burstThresholdPoints, BURST_MIN_POINTS,
               InpBurstPercentile, burstThresholdSampleCount,
               InpBurstWindowSamples,
               burstSpeedPassed ? 1 : 0,
               burstDirectionPassed ? 1 : 0,
               continuationPassed ? 1 : 0,
               burstGateSurvived ? 1 : 0,
               frictionPassed ? 1 : 0,
               oneEntryPerBarPassed ? 1 : 0); }

   const bool candidatePassed = burstGateSurvived &&
                                oneEntryPerBarPassed &&
                                frictionPassed;
   WriteMasterVwapDecision(isBuy, tickTimeMsc, midPrice,
                           candidatePassed
                           ? "ENTRY_CANDIDATE_PASS"
                           : "ENTRY_CANDIDATE_REJECT");

   if(candidatePassed)
      return true;

   { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=%s crossing=1 burst_gate_active=%d burst_threshold_mode=%s burst_speed_failed=%d burst_direction_failed=%d continuation_failed=%d one_entry_per_bar_failed=%d friction_failed=%d entry_hold_failed=0 prior60_failed=0 burst_available=%d burst_points=%.1f burst_threshold_available=%d burst_threshold_points=%.1f burst_percentile=%.4f burst_window_samples=%d burst_window_target=%d current_sample_excluded=1 friction=%.6f up_streak=%d down_streak=%d hold_move_points=0.0 prior60_drift_points=0.0",
               isBuy ? "BUY" : "SELL",
               InpUseBurstGate ? 1 : 0,
               BurstThresholdModeName(),
               burstSpeedPassed ? 0 : 1,
               burstDirectionPassed ? 0 : 1,
               continuationPassed ? 0 : 1,
               oneEntryPerBarPassed ? 0 : 1,
               frictionPassed ? 0 : 1,
               burstAvailable ? 1 : 0,
               burstPoints,
               burstThresholdAvailable ? 1 : 0,
               burstThresholdPoints, InpBurstPercentile,
               burstThresholdSampleCount, InpBurstWindowSamples,
               currentTickFriction, g_UpTickStreak, g_DownTickStreak); }
   return false;
}

void ResetEntryHoldCandidate()
{
   g_EntryHoldCandidate.active = false;
   g_EntryHoldCandidate.isBuy = false;
   g_EntryHoldCandidate.signalTimeMsc = 0;
   g_EntryHoldCandidate.signalMidPrice = 0.0;
   g_EntryHoldCandidate.signalBar = 0;
}

ENUM_ENTRY_HOLD_RESULT EvaluateEntryHoldGate(bool isBuy, long tickTimeMsc,
                                              double midPrice, double point,
                                              double &holdMovePoints)
{
   holdMovePoints = 0.0;
   const string side = isBuy ? "BUY" : "SELL";

   if(!InpUseEntryHold)
   {
      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_GATE_EVAL gate=ENTRY_HOLD side=%s enabled=0 status=BYPASS elapsed_ms=0 required_ms=%d signal_mid=%.10f current_mid=%.10f hold_move_points=0.0 required_move_points=%.1f pass=1",
                  side, InpEntryHoldMs, midPrice, midPrice,
                  InpEntryHoldMinFavPoints); }
      return ENTRY_HOLD_PASS;
   }

   if(!g_EntryHoldCandidate.active)
   {
      g_EntryHoldCandidate.active = true;
      g_EntryHoldCandidate.isBuy = isBuy;
      g_EntryHoldCandidate.signalTimeMsc = tickTimeMsc;
      g_EntryHoldCandidate.signalMidPrice = midPrice;
      g_EntryHoldCandidate.signalBar = CurrentEntryBar();

      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_GATE_EVAL gate=ENTRY_HOLD side=%s enabled=1 status=ARMED elapsed_ms=0 required_ms=%d signal_mid=%.10f current_mid=%.10f hold_move_points=0.0 required_move_points=%.1f pass=0",
                  side, InpEntryHoldMs, midPrice, midPrice,
                  InpEntryHoldMinFavPoints); }
   }

   if(g_EntryHoldCandidate.isBuy != isBuy)
      return ENTRY_HOLD_WAIT;

   long elapsedMsc = tickTimeMsc - g_EntryHoldCandidate.signalTimeMsc;
   if(elapsedMsc < 0) elapsedMsc = 0;
   long requiredMsc = (long)MathMax(0, InpEntryHoldMs);
   holdMovePoints = (point > 0.0)
                    ? (isBuy
                       ? (midPrice - g_EntryHoldCandidate.signalMidPrice) / point
                       : (g_EntryHoldCandidate.signalMidPrice - midPrice) / point)
                    : 0.0;
   if(elapsedMsc < requiredMsc)
      return ENTRY_HOLD_WAIT;

   const bool passed = (point > 0.0 &&
                        holdMovePoints >= InpEntryHoldMinFavPoints);
   const datetime signalBar = g_EntryHoldCandidate.signalBar;
   const double signalMidPrice = g_EntryHoldCandidate.signalMidPrice;

   { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_GATE_EVAL gate=ENTRY_HOLD side=%s enabled=1 status=%s elapsed_ms=%I64d required_ms=%d signal_mid=%.10f current_mid=%.10f hold_move_points=%.1f required_move_points=%.1f pass=%d",
               side, passed ? "PASS" : "FAIL", elapsedMsc,
               InpEntryHoldMs, signalMidPrice, midPrice, holdMovePoints,
               InpEntryHoldMinFavPoints, passed ? 1 : 0); }

   ResetEntryHoldCandidate();
   if(passed)
      return ENTRY_HOLD_PASS;

   g_LastEntryHoldFailureBar = signalBar;
   if(isBuy) g_VirtualBuyStopPrice = 0.0;
   else g_VirtualSellStopPrice = 0.0;

   { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=%s crossing=1 burst_speed_failed=0 burst_direction_failed=0 continuation_failed=0 friction_failed=0 one_entry_per_bar_failed=0 entry_hold_failed=1 prior60_failed=0 hold_move_points=%.1f prior60_drift_points=0.0",
               side, holdMovePoints); }
   return ENTRY_HOLD_FAIL;
}

bool MeasurePrior60Drift(long tickTimeMsc, double midPrice, double point,
                         double &driftPoints, long &sampleTimeMsc)
{
   driftPoints = 0.0;
   sampleTimeMsc = 0;
   if(point <= 0.0 || InpPrior60LookbackMin <= 0) return false;

   const long lookbackMsc = (long)InpPrior60LookbackMin * 60 * 1000;
   if(tickTimeMsc <= lookbackMsc) return false;

   MqlTick priorTicks[];
   const ulong targetTimeMsc = (ulong)(tickTimeMsc - lookbackMsc);
   const int copied = CopyTicks(_Symbol, priorTicks, COPY_TICKS_ALL,
                                targetTimeMsc, 1);
   if(copied != 1 || priorTicks[0].bid <= 0.0 || priorTicks[0].ask <= 0.0 ||
      priorTicks[0].time_msc <= 0 || priorTicks[0].time_msc > tickTimeMsc)
      return false;

   const double priorMidPrice = (priorTicks[0].bid + priorTicks[0].ask) * 0.5;
   driftPoints = (midPrice - priorMidPrice) / point;
   sampleTimeMsc = priorTicks[0].time_msc;
   return true;
}

bool EntryPrior60Approved(bool isBuy, long tickTimeMsc, double midPrice,
                          double point, double holdMovePoints)
{
   double driftPoints = 0.0;
   long sampleTimeMsc = 0;
   const bool driftAvailable = MeasurePrior60Drift(tickTimeMsc, midPrice,
                                                   point, driftPoints,
                                                   sampleTimeMsc);
   const bool directionPassed = driftAvailable &&
                                ((isBuy && driftPoints > 0.0) ||
                                 (!isBuy && driftPoints < 0.0));
   const bool passed = !InpUsePrior60Filter || directionPassed;
   const long sampledLookbackMsc = (sampleTimeMsc > 0)
                                   ? tickTimeMsc - sampleTimeMsc : 0;

   { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_GATE_EVAL gate=PRIOR60 side=%s enabled=%d lookback_min=%d drift_available=%d prior60_drift_points=%.1f sampled_lookback_ms=%I64d hold_move_points=%.1f pass=%d",
               isBuy ? "BUY" : "SELL", InpUsePrior60Filter ? 1 : 0,
               InpPrior60LookbackMin, driftAvailable ? 1 : 0,
               driftPoints, sampledLookbackMsc, holdMovePoints,
               passed ? 1 : 0); }

   if(!passed)
   {
      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=%s crossing=1 burst_speed_failed=0 burst_direction_failed=0 continuation_failed=0 friction_failed=0 one_entry_per_bar_failed=0 entry_hold_failed=0 prior60_failed=1 hold_move_points=%.1f prior60_drift_points=%.1f drift_available=%d",
                  isBuy ? "BUY" : "SELL", holdMovePoints, driftPoints,
                  driftAvailable ? 1 : 0); }
   }
   return passed;
}

int OwnPositionsTotal()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(!IsOwnSelectedPosition()) continue;
      count++;
   }
   return count;
}

ulong ResolveOwnPositionTicket(ENUM_POSITION_TYPE positionType, ulong resultOrderTicket)
{
   if(resultOrderTicket > 0 && posInfo.SelectByTicket(resultOrderTicket) &&
      IsOwnSelectedPosition() && posInfo.PositionType() == positionType)
      return posInfo.Ticket();

   ulong newestTicket = 0;
   long newestTimeMsc = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(!IsOwnSelectedPosition()) continue;
      if(posInfo.PositionType() != positionType) continue;

      long positionTimeMsc = PositionGetInteger(POSITION_TIME_MSC);
      if(positionTimeMsc >= newestTimeMsc)
      {
         newestTimeMsc = positionTimeMsc;
         newestTicket = posInfo.Ticket();
      }
   }
   return newestTicket;
}

double RiskPercentForTrade(ENUM_ORDER_TYPE orderType, double lots,
                           double entryPrice, double stopPrice)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity <= 0.0 || lots <= 0.0) return 0.0;

   double stopLossMoney = 0.0;
   double commissionMoney = 0.0;
   double slippageMoney = 0.0;
   double totalLossPerLot = 0.0;
   if(!CalculateLossPerLot(orderType, entryPrice, stopPrice,
                           stopLossMoney, commissionMoney,
                           slippageMoney, totalLossPerLot))
      return 0.0;

   return ((lots * totalLossPerLot) / equity) * 100.0;
}

void LogEntryRisk(string side, ulong ticket, double lots,
                  ENUM_ORDER_TYPE orderType,
                  double requestedEntryPrice, double requestedStopPrice,
                  double fillPrice, double virtualSL)
{
   double requestedRiskPercent = RiskPercentForTrade(orderType, lots,
                                                      requestedEntryPrice,
                                                      requestedStopPrice);
   double realisedRiskPercent = RiskPercentForTrade(orderType, lots,
                                                     fillPrice, virtualSL);

   PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_RISK side=%s ticket=%I64u configured_risk_percent=%.4f requested_risk_percent=%.4f realised_risk_percent=%.4f lots=%.8f requested_entry=%.10f requested_stop=%.10f fill=%.10f actual_virtual_stop=%.10f commission_points=%.1f slippage_points=%.1f",
               side, ticket, InpRiskPercent, requestedRiskPercent,
               realisedRiskPercent, lots, requestedEntryPrice,
               requestedStopPrice, fillPrice, virtualSL,
               PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS,
               PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS);
}

void LogPositionExitAttempt(const string reason, const ulong ticket,
                            const ENUM_POSITION_TYPE positionType,
                            const double entryPrice, const double bid,
                            const double ask, const double point,
                            const double activeVirtualSL,
                            const bool trailArmed,
                            const datetime entryTime)
{
   const string direction = (positionType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   const double spreadPoints = (point > 0.0) ? (ask - bid) / point : 0.0;
   const double pnlPoints = (point > 0.0)
                            ? ((positionType == POSITION_TYPE_BUY)
                               ? (bid - entryPrice) / point
                               : (entryPrice - ask) / point)
                            : 0.0;
   long secondsSinceEntry = (long)(TimeCurrent() - entryTime);
   if(secondsSinceEntry < 0) secondsSinceEntry = 0;

   PrintFormat("EXIT_REASON=%s phase=ATTEMPT ticket=%I64u direction=%s entry_price=%.10f bid=%.10f ask=%.10f spread_points=%.1f active_virtual_stop=%.10f trail_armed=%d pnl_points=%.1f seconds_since_entry=%I64d",
               reason, ticket, direction, entryPrice, bid, ask,
               spreadPoints, activeVirtualSL, trailArmed ? 1 : 0,
               pnlPoints, secondsSinceEntry);
}

void LogPositionExitResult(const string reason, const ulong ticket,
                           const ENUM_POSITION_TYPE positionType,
                           const bool closeCallReturned,
                           const uint retcode,
                           const string retcodeDescription,
                           const bool positionStillOpen)
{
   const string direction = (positionType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   const bool closeSucceeded = closeCallReturned && !positionStillOpen;
   PrintFormat("EXIT_REASON=%s phase=RESULT ticket=%I64u direction=%s success=%d call_return=%d retcode=%u retcode_description=%s position_still_open=%d",
               reason, ticket, direction, closeSucceeded ? 1 : 0,
               closeCallReturned ? 1 : 0, retcode, retcodeDescription,
               positionStillOpen ? 1 : 0);
}

//+------------------------------------------------------------------+
//| Logic: Manage Virtual Pending Orders                             |
//+------------------------------------------------------------------+
void ManageVirtualPendings(double ask, double bid, double spread, double point,
                           long tickTimeMsc, double midPrice)
{
   bool buyOpen = false;
   bool sellOpen = false;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(posInfo.SelectByIndex(i)) // Filter by magic needed if used in prod
      {
         if(!IsOwnSelectedPosition()) continue;
         if(posInfo.PositionType() == POSITION_TYPE_BUY) buyOpen = true;
         if(posInfo.PositionType() == POSITION_TYPE_SELL) sellOpen = true;
      }
   }

   bool nettingAccount = IsNettingAccount();
   if(nettingAccount && buyOpen) g_VirtualSellStopPrice = 0;
   if(nettingAccount && sellOpen) g_VirtualBuyStopPrice = 0;

   // --- Recalculate Entry Levels ---
   if(TimeCurrent() > g_LastModTime + InpModInterval)
   {
      double calculatedSpreadPoints = (point > 0.0) ? spread / point : 0.0;
      double multipliedDistancePoints = calculatedSpreadPoints * InpEntryDistMult;
      double cappedDistancePoints = MathMin(multipliedDistancePoints,
                                            MAX_ENTRY_DISTANCE_POINTS);
      double entryDist = cappedDistancePoints * point;
      double appliedDistancePoints = entryDist / point;

      { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_DISTANCE_REFRESH calculated_spread_points=%.1f multiplier=%.2f multiplied_distance_points=%.1f cap_points=%.1f capped_distance_points=%.1f applied_distance_points=%.1f cap_bound=%d",
                   calculatedSpreadPoints, InpEntryDistMult,
                   multipliedDistancePoints, MAX_ENTRY_DISTANCE_POINTS,
                   cappedDistancePoints, appliedDistancePoints,
                   multipliedDistancePoints > MAX_ENTRY_DISTANCE_POINTS ? 1 : 0); }
      
      // XPWF arming layer: a side that is not live never gets a level, so its bursts cannot fire.
      if(!buyOpen && !(nettingAccount && sellOpen) && XPWF_AllowBuySide()) g_VirtualBuyStopPrice = ask + entryDist; 
      else g_VirtualBuyStopPrice = 0; 

      if(!sellOpen && !(nettingAccount && buyOpen) && XPWF_AllowSellSide()) g_VirtualSellStopPrice = bid - entryDist;
      else g_VirtualSellStopPrice = 0; 
      
      g_LastModTime = TimeCurrent();
   }

   if(g_EntryHoldCandidate.active &&
      ((g_EntryHoldCandidate.isBuy && g_VirtualBuyStopPrice <= 0.0) ||
       (!g_EntryHoldCandidate.isBuy && g_VirtualSellStopPrice <= 0.0)))
      ResetEntryHoldCandidate();

   // BUY TRIGGER
   const bool buyCrossing = (g_VirtualBuyStopPrice > 0 && ask >= g_VirtualBuyStopPrice);
   const bool buyHoldActive = g_EntryHoldCandidate.active && g_EntryHoldCandidate.isBuy;
   if(buyHoldActive || (!g_EntryHoldCandidate.active && buyCrossing))
   {
      const bool cheapGatesPassed = buyHoldActive ||
                                    EntryCandidateApproved(true, tickTimeMsc,
                                                           midPrice, point);
      if(cheapGatesPassed)
      {
         double holdMovePoints = 0.0;
         const ENUM_ENTRY_HOLD_RESULT holdResult =
            EvaluateEntryHoldGate(true, tickTimeMsc, midPrice, point,
                                  holdMovePoints);
         if(holdResult == ENTRY_HOLD_PASS &&
            EntryPrior60Approved(true, tickTimeMsc, midPrice, point,
                                 holdMovePoints))
         {
            double virtualSLDist = 0.0;
            if(!VirtualFloorDistance(spread * InpInitStopMult, point,
                                     "INITIAL_BUY", virtualSLDist,
                                     true, 0))
            {
               { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=BUY crossing=1 reason=virtual_floor_unavailable"); }
            }
            else
            {
               double requestedEntryPrice = ask;
               double requestedStopPrice = bid - virtualSLDist;
               double tradeLots = CalculateLotSize(ORDER_TYPE_BUY,
                                                   requestedEntryPrice,
                                                   requestedStopPrice);

               PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 PRE_ORDER_DISTANCE side=BUY virtual_cost_floor_points=%.1f calculated_stop_distance_points=%.1f applied_stop_distance_points=%.1f entry_to_stop_points=%.1f",
                           COST_FLOOR_POINTS,
                           (spread * InpInitStopMult) / point,
                           virtualSLDist / point,
                           (requestedEntryPrice - requestedStopPrice) / point);

               if(tradeLots > 0 && XPWF_AllowBuy() && trade.Buy(tradeLots, _Symbol, 0, 0, 0, "V_Breakout"))
               {
                  MarkCurrentBarEntered();
                  g_VirtualBuyStopPrice = 0;
                  ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_BUY, trade.ResultOrder());
                  double virtualSL = bid - virtualSLDist;
                  if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
                  double fillPrice = trade.ResultPrice();
                  if(fillPrice <= 0) fillPrice = ask;
                  long positionId = (long)ticket;
                  ulong dealTicket = trade.ResultDeal();
                  if(dealTicket > 0 && HistoryDealSelect(dealTicket))
                  {
                     long dealPositionId =
                        (long)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
                     if(dealPositionId > 0) positionId = dealPositionId;
                  }
                  LA_VirtualFill(true, fillPrice, tickTimeMsc,
                                 bid, ask, positionId);
                  LogEntryRisk("BUY", ticket, tradeLots, ORDER_TYPE_BUY,
                               requestedEntryPrice, requestedStopPrice,
                               fillPrice, virtualSL);
               }
            }
         }
      }
   }

   // SELL TRIGGER
   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
   const bool sellHoldActive = g_EntryHoldCandidate.active && !g_EntryHoldCandidate.isBuy;
   if(sellHoldActive || (!g_EntryHoldCandidate.active && sellCrossing))
   {
      const bool cheapGatesPassed = sellHoldActive ||
                                    EntryCandidateApproved(false, tickTimeMsc,
                                                           midPrice, point);
      if(cheapGatesPassed)
      {
         double holdMovePoints = 0.0;
         const ENUM_ENTRY_HOLD_RESULT holdResult =
            EvaluateEntryHoldGate(false, tickTimeMsc, midPrice, point,
                                  holdMovePoints);
         if(holdResult == ENTRY_HOLD_PASS &&
            EntryPrior60Approved(false, tickTimeMsc, midPrice, point,
                                 holdMovePoints))
         {
            double virtualSLDist = 0.0;
            if(!VirtualFloorDistance(spread * InpInitStopMult, point,
                                     "INITIAL_SELL", virtualSLDist,
                                     true, 0))
            {
               { if(!MQLInfoInteger(MQL_TESTER)) PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 ENTRY_REJECT side=SELL crossing=1 reason=virtual_floor_unavailable"); }
            }
            else
            {
               double requestedEntryPrice = bid;
               double requestedStopPrice = ask + virtualSLDist;
               double tradeLots = CalculateLotSize(ORDER_TYPE_SELL,
                                                   requestedEntryPrice,
                                                   requestedStopPrice);

               PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 PRE_ORDER_DISTANCE side=SELL virtual_cost_floor_points=%.1f calculated_stop_distance_points=%.1f applied_stop_distance_points=%.1f entry_to_stop_points=%.1f",
                           COST_FLOOR_POINTS,
                           (spread * InpInitStopMult) / point,
                           virtualSLDist / point,
                           (requestedStopPrice - requestedEntryPrice) / point);

               if(tradeLots > 0 && XPWF_AllowSell() && trade.Sell(tradeLots, _Symbol, 0, 0, 0, "V_Breakout"))
               {
                  MarkCurrentBarEntered();
                  g_VirtualSellStopPrice = 0;
                  ulong ticket = ResolveOwnPositionTicket(POSITION_TYPE_SELL, trade.ResultOrder());
                  double virtualSL = ask + virtualSLDist;
                  if(ticket > 0) RegisterVirtualSL(ticket, virtualSL);
                  double fillPrice = trade.ResultPrice();
                  if(fillPrice <= 0) fillPrice = bid;
                  long positionId = (long)ticket;
                  ulong dealTicket = trade.ResultDeal();
                  if(dealTicket > 0 && HistoryDealSelect(dealTicket))
                  {
                     long dealPositionId =
                        (long)HistoryDealGetInteger(dealTicket, DEAL_POSITION_ID);
                     if(dealPositionId > 0) positionId = dealPositionId;
                  }
                  LA_VirtualFill(false, fillPrice, tickTimeMsc,
                                 bid, ask, positionId);
                  LogEntryRisk("SELL", ticket, tradeLots, ORDER_TYPE_SELL,
                               requestedEntryPrice, requestedStopPrice,
                               fillPrice, virtualSL);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Logic: Manage Open Positions (Virtual SL + Trailing)             |
//+------------------------------------------------------------------+
void ManageOpenPositions(double ask, double bid, double spread, double point)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(posInfo.SelectByIndex(i)) 
      {
         if(!IsOwnSelectedPosition()) continue;
         ulong ticket = posInfo.Ticket();
         double openPrice = posInfo.PriceOpen();
         double currentVSL = GetVirtualSL(ticket);
         
          if(currentVSL == 0)
          {
             double initDist = 0.0;
             string fallbackContext = (posInfo.PositionType() == POSITION_TYPE_BUY)
                                      ? "FALLBACK_BUY" : "FALLBACK_SELL";
             if(!VirtualFloorDistance(spread * InpInitStopMult, point,
                                      fallbackContext, initDist,
                                      true, ticket))
             {
                PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_FALLBACK_DEFERRED ticket=%I64u symbol=%s reason=virtual_floor_unavailable",
                            ticket, _Symbol);
                continue;
             }
             if(posInfo.PositionType() == POSITION_TYPE_BUY) currentVSL = openPrice - initDist;
             else currentVSL = openPrice + initDist;
             PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_FALLBACK_RECONSTRUCTION ticket=%I64u symbol=%s magic=%d open_price=%.10f reconstructed_sl=%.10f virtual_cost_floor_points=%.1f applied_stop_distance_points=%.1f",
                         ticket, _Symbol, InpMagic, openPrice, currentVSL,
                         COST_FLOOR_POINTS,
                         initDist / point);
             UpdateVirtualSL(ticket, currentVSL);
          }

          double liveSpread = ask - bid;
          double currentSpreadPoints = (point > 0) ? liveSpread / point : 0.0;
          double innerEdgePoints = 0.0;
          double outerEdgePoints = 0.0;
          double trailingBufferPoints = 0.0;
          CalculateTrailingGeometry(liveSpread, point, innerEdgePoints,
                                    outerEdgePoints, trailingBufferPoints);

          double formulaTrailingBufferPoints = trailingBufferPoints;
          string trailingContext = (posInfo.PositionType() == POSITION_TYPE_BUY)
                                   ? "TRAILING_BUY" : "TRAILING_SELL";
          double virtualFlooredTrailingPrice = 0.0;
          if(!VirtualFloorDistance(formulaTrailingBufferPoints * point, point,
                                   trailingContext,
                                   virtualFlooredTrailingPrice,
                                   true, ticket))
          {
             PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 TRAILING_DEFERRED ticket=%I64u symbol=%s reason=virtual_floor_unavailable",
                         ticket, _Symbol);
             continue;
          }
          trailingBufferPoints = virtualFlooredTrailingPrice / point;

          double requestedActivationPoints = currentSpreadPoints * internalOrderDistance;
          double costSafeActivationPoints = PROVISIONAL_ROUND_TRIP_COST_POINTS +
                                            trailingBufferPoints;
          double finalActivationPoints = MathMax(requestedActivationPoints,
                                                 costSafeActivationPoints +
                                                 InpTrailingLockInPoints);

          if(posInfo.PositionType() == POSITION_TYPE_BUY)
          {
            if(bid <= currentVSL)
            {
               const bool exitTrailArmed = (currentVSL >= openPrice);
               const string exitReason = exitTrailArmed
                                         ? "TRAILED_STOP_HIT"
                                         : "INITIAL_VIRTUAL_STOP_HIT";
               const datetime entryTime = (datetime)PositionGetInteger(POSITION_TIME);
               const long positionId =
                  (long)PositionGetInteger(POSITION_IDENTIFIER);
               XA_StampDecision(positionId,
                                exitTrailArmed
                                ? "EXIT_VIRTUAL_TRAILING_STOP"
                                : "EXIT_VIRTUAL_INITIAL_STOP",
                                __LINE__, true, bid, true, currentVSL,
                                true, bid);
               LogPositionExitAttempt(exitReason, ticket, POSITION_TYPE_BUY,
                                      openPrice, bid, ask, point, currentVSL,
                                      exitTrailArmed, entryTime);

               const bool closeCallReturned = trade.PositionClose(ticket);
               const uint closeRetcode = trade.ResultRetcode();
               const string closeRetcodeDescription = trade.ResultRetcodeDescription();
               const bool positionStillOpen = PositionSelectByTicket(ticket);
               LogPositionExitResult(exitReason, ticket, POSITION_TYPE_BUY,
                                     closeCallReturned, closeRetcode,
                                     closeRetcodeDescription, positionStillOpen);

               if(closeCallReturned)
               {
                  RemoveVirtualSL(ticket);
               }
               else
               {
                  PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_CLOSE_FAILED ticket=%I64u retained_sl=%.10f retcode=%u description=%s",
                              ticket, currentVSL, trade.ResultRetcode(), trade.ResultRetcodeDescription());
               }
               continue; 
            }
            
            double profitPoints = (bid - openPrice) / point;
            bool trailingWasArmed = (currentVSL >= openPrice);

            if(profitPoints >= finalActivationPoints)
            {
               double newSL = bid - (trailingBufferPoints * point);
               double minimumAdvance = MathMax(spread, point);
               if(newSL >= openPrice && newSL > currentVSL &&
                  newSL - currentVSL >= minimumAdvance)
               {
                  if(!trailingWasArmed)
                     LogTrailingArm("BUY", ticket, requestedActivationPoints,
                                    costSafeActivationPoints, finalActivationPoints,
                                    profitPoints,
                                    currentSpreadPoints, trailingBufferPoints,
                                    innerEdgePoints, outerEdgePoints);
                  UpdateVirtualSL(ticket, newSL);
               }
            }
         }
         else // SELL
         {
            if(ask >= currentVSL)
            {
               const bool exitTrailArmed = (currentVSL <= openPrice);
               const string exitReason = exitTrailArmed
                                         ? "TRAILED_STOP_HIT"
                                         : "INITIAL_VIRTUAL_STOP_HIT";
               const datetime entryTime = (datetime)PositionGetInteger(POSITION_TIME);
               const long positionId =
                  (long)PositionGetInteger(POSITION_IDENTIFIER);
               XA_StampDecision(positionId,
                                exitTrailArmed
                                ? "EXIT_VIRTUAL_TRAILING_STOP"
                                : "EXIT_VIRTUAL_INITIAL_STOP",
                                __LINE__, true, ask, true, currentVSL,
                                true, ask);
               LogPositionExitAttempt(exitReason, ticket, POSITION_TYPE_SELL,
                                      openPrice, bid, ask, point, currentVSL,
                                      exitTrailArmed, entryTime);

               const bool closeCallReturned = trade.PositionClose(ticket);
               const uint closeRetcode = trade.ResultRetcode();
               const string closeRetcodeDescription = trade.ResultRetcodeDescription();
               const bool positionStillOpen = PositionSelectByTicket(ticket);
               LogPositionExitResult(exitReason, ticket, POSITION_TYPE_SELL,
                                     closeCallReturned, closeRetcode,
                                     closeRetcodeDescription, positionStillOpen);

               if(closeCallReturned)
               {
                  RemoveVirtualSL(ticket);
               }
               else
               {
                  PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_CLOSE_FAILED ticket=%I64u retained_sl=%.10f retcode=%u description=%s",
                              ticket, currentVSL, trade.ResultRetcode(), trade.ResultRetcodeDescription());
               }
               continue;
            }
            
            double profitPoints = (openPrice - ask) / point;
            bool trailingWasArmed = (currentVSL <= openPrice);

            if(profitPoints >= finalActivationPoints)
            {
               double newSL = ask + (trailingBufferPoints * point);
               double minimumAdvance = MathMax(spread, point);
               if(newSL <= openPrice && newSL < currentVSL &&
                  currentVSL - newSL >= minimumAdvance)
               {
                  if(!trailingWasArmed)
                     LogTrailingArm("SELL", ticket, requestedActivationPoints,
                                    costSafeActivationPoints, finalActivationPoints,
                                    profitPoints,
                                    currentSpreadPoints, trailingBufferPoints,
                                    innerEdgePoints, outerEdgePoints);
                  UpdateVirtualSL(ticket, newSL);
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Helpers: Virtual SL Memory Management                            |
//+------------------------------------------------------------------+
string VirtualSLFileName()
{
   string symbolToken = _Symbol;
   StringReplace(symbolToken, "\\", "_");
   StringReplace(symbolToken, "/", "_");
   StringReplace(symbolToken, ":", "_");
   StringReplace(symbolToken, "*", "_");
   StringReplace(symbolToken, "?", "_");
   StringReplace(symbolToken, "\"", "_");
   StringReplace(symbolToken, "<", "_");
   StringReplace(symbolToken, ">", "_");
   StringReplace(symbolToken, "|", "_");
   return StringFormat("FlashGold_Continuation_v2_VSL_%I64d_%s_%d.csv",
                       AccountInfoInteger(ACCOUNT_LOGIN), symbolToken, InpMagic);
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || trans.deal == 0)
      return;
   XA_OnTradeDeal(trans.deal);
}

bool SaveVirtualSLs()
{
   // Tester runs start cold and use the in-memory stop array.
   if(MQLInfoInteger(MQL_TESTER)) return true;
   string fileName = VirtualSLFileName();
   int handle = FileOpen(fileName, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_SAVE_FAILED file=%s error=%d", fileName, GetLastError());
      return false;
   }

   for(int i = 0; i < ArraySize(g_VirtualPositions); i++)
      FileWrite(handle, (string)g_VirtualPositions[i].ticket,
                DoubleToString(g_VirtualPositions[i].virtualSL, _Digits));

   FileFlush(handle);
   FileClose(handle);
   return true;
}

bool LoadVirtualSLs()
{
   ArrayResize(g_VirtualPositions, 0);
   string fileName = VirtualSLFileName();
   if(!FileIsExist(fileName))
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_FILE_NOT_FOUND file=%s", fileName);
      return true;
   }

   int handle = FileOpen(fileName, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_LOAD_FAILED file=%s error=%d", fileName, GetLastError());
      return false;
   }

   int loaded = 0;
   while(!FileIsEnding(handle))
   {
      string ticketText = FileReadString(handle);
      if(StringLen(ticketText) == 0) break;
      double virtualSL = FileReadNumber(handle);
      ulong ticket = (ulong)StringToInteger(ticketText);
      if(ticket == 0 || virtualSL <= 0) continue;

      int size = ArraySize(g_VirtualPositions);
      ArrayResize(g_VirtualPositions, size + 1);
      g_VirtualPositions[size].ticket = ticket;
      g_VirtualPositions[size].virtualSL = virtualSL;
      loaded++;
   }

   FileClose(handle);
   PrintFormat("PROVISIONAL COST FLOOR FlashGold_Continuation_v2 VSL_LOAD_COMPLETE file=%s count=%d", fileName, loaded);
   return true;
}

void RegisterVirtualSL(ulong ticket, double sl)
{
   if(ticket == 0 || sl <= 0) return;

   for(int i = 0; i < ArraySize(g_VirtualPositions); i++)
   {
      if(g_VirtualPositions[i].ticket == ticket)
      {
         g_VirtualPositions[i].virtualSL = sl;
         SaveVirtualSLs();
         return;
      }
   }

   int size = ArraySize(g_VirtualPositions);
   ArrayResize(g_VirtualPositions, size + 1);
   g_VirtualPositions[size].ticket = ticket;
   g_VirtualPositions[size].virtualSL = sl;
   SaveVirtualSLs();
}

double GetVirtualSL(ulong ticket)
{
   for(int i=ArraySize(g_VirtualPositions) - 1; i>=0; i--)
   {
      if(g_VirtualPositions[i].ticket == ticket) return g_VirtualPositions[i].virtualSL;
   }
   return 0;
}

void UpdateVirtualSL(ulong ticket, double newSL)
{
   for(int i=0; i<ArraySize(g_VirtualPositions); i++)
   {
      if(g_VirtualPositions[i].ticket == ticket)
      {
         g_VirtualPositions[i].virtualSL = newSL;
         SaveVirtualSLs();
         return;
      }
   }
   RegisterVirtualSL(ticket, newSL); 
}

void RemoveVirtualSL(ulong ticket)
{
   int index = -1;
   for(int i=0; i<ArraySize(g_VirtualPositions); i++)
   {
      if(g_VirtualPositions[i].ticket == ticket)
      {
         index = i;
         break;
      }
   }
   
   if(index != -1)
   {
      int last = ArraySize(g_VirtualPositions) - 1;
      g_VirtualPositions[index] = g_VirtualPositions[last];
      ArrayResize(g_VirtualPositions, last);
      SaveVirtualSLs();
   }
}

//+------------------------------------------------------------------+
//| Visuals                                                          |
//+------------------------------------------------------------------+
void DrawVirtualLevels()
{
   if(g_VirtualBuyStopPrice > 0) DrawLine("V_Entry_Buy", g_VirtualBuyStopPrice, clrBlue);
   if(g_VirtualSellStopPrice > 0) DrawLine("V_Entry_Sell", g_VirtualSellStopPrice, clrRed);
   
   for(int i=ArraySize(g_VirtualPositions) - 1; i>=0; i--)
   {
      if(!posInfo.SelectByTicket(g_VirtualPositions[i].ticket)) 
      {
         RemoveVirtualSL(g_VirtualPositions[i].ticket);
         continue;
      }
      if(!IsOwnSelectedPosition())
      {
         RemoveVirtualSL(g_VirtualPositions[i].ticket);
         continue;
      }
      string name = "V_SL_" + IntegerToString(g_VirtualPositions[i].ticket);
      DrawLine(name, g_VirtualPositions[i].virtualSL, clrOrange);
   }
}

void DrawLine(string name, double price, color clr)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
}

void UpdateDashboard()
{
   int y = InpDashY;
   int lineHeight = 18;
   
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double spread = (ask - bid) / _Point;
   
   // Calculate the next BUY size through the same account-currency risk path
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double calcSpread = MathMax((ask-bid), InpMinSpreadPips * 10 * point);
   double nextStopDistance = 0.0;
   double nextLots = 0.0;
   if(VirtualFloorDistance(calcSpread * InpInitStopMult, point,
                           "DASHBOARD_PREVIEW", nextStopDistance,
                           false, 0))
   {
      double nextIntendedStop = bid - nextStopDistance;
      nextLots = CalculateLotSize(ORDER_TYPE_BUY, ask,
                                  nextIntendedStop, false);
   }
   
   string status = "Scanning";
   if(OwnPositionsTotal() > 0) status = "Managing Position";
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) status = "AutoTrading Disabled";
   
   CreateLabel("Lbl_Status", InpDashX, y, "Status: " + status, clrGray);
   y += lineHeight;

   string costTxt = StringFormat("PROVISIONAL COST FLOOR: %.0f + %.0f + %.0f = %.0f pts",
                                 PROVISIONAL_ENTRY_SPREAD_POINTS,
                                 PROVISIONAL_COMMISSION_ROUND_TRIP_POINTS,
                                 PROVISIONAL_SLIPPAGE_ALLOWANCE_POINTS,
                                 PROVISIONAL_ROUND_TRIP_COST_POINTS);
   CreateLabel("Lbl_CostFloor", InpDashX, y, costTxt, clrOrange);
   y += lineHeight;

   // Next Trade Lot Prediction
   string riskType = (InpMMType == MM_RISK_PERCENT) ? StringFormat("Risk %.1f%%", InpRiskPercent) : "Fixed Lots";
   string lotTxt = StringFormat("Next Trade: %.2f Lots (%s)", nextLots, riskType);
   CreateLabel("Lbl_Lots", InpDashX, y, lotTxt, clrWhite);
   y += lineHeight;

   double maxEntrySpreadPoints = EffectiveMaxEntrySpread(_Point) / _Point;
   color spreadClr = (spread <= maxEntrySpreadPoints) ? InpDashColor2 : InpDashColor3;
   string spreadTxt = StringFormat("Spread: %.1f (Max: %.1f points)", spread, maxEntrySpreadPoints);
   CreateLabel("Lbl_Spread", InpDashX, y, spreadTxt, spreadClr);
   y += lineHeight + 5; 

   if(g_VirtualBuyStopPrice > 0) {
      double dist = (g_VirtualBuyStopPrice - ask) / _Point;
      string txt = StringFormat("V-BuyStop: %.5f | Dist: %.1f", g_VirtualBuyStopPrice, dist/10);
      CreateLabel("Lbl_VBuy", InpDashX, y, txt, InpDashColor1);
   } else {
      CreateLabel("Lbl_VBuy", InpDashX, y, "V-BuyStop: [Inactive]", clrGray);
   }
   y += lineHeight;

   if(g_VirtualSellStopPrice > 0) {
      double dist = (bid - g_VirtualSellStopPrice) / _Point;
      string txt = StringFormat("V-SellStop: %.5f | Dist: %.1f", g_VirtualSellStopPrice, dist/10);
      CreateLabel("Lbl_VSell", InpDashX, y, txt, InpDashColor1);
   } else {
      CreateLabel("Lbl_VSell", InpDashX, y, "V-SellStop: [Inactive]", clrGray);
   }
   y += lineHeight + 5;

   int openPositions = PositionsTotal();
   int ownPositionIndex = 0;
   if(openPositions > 0) {
      for(int i = 0; i < openPositions; i++) {
         if(posInfo.SelectByIndex(i)) {
            if(!IsOwnSelectedPosition()) continue;
            ulong ticket = posInfo.Ticket();
            double vSL = GetVirtualSL(ticket);
            double currentPrice = (posInfo.PositionType() == POSITION_TYPE_BUY) ? bid : ask;
            double profit = posInfo.Profit();
            double distToSL = MathAbs(currentPrice - vSL) / _Point;
            
            string pType = (posInfo.PositionType() == POSITION_TYPE_BUY) ? "BUY" : "SELL";
            color pColor = (profit >= 0) ? InpDashColor2 : InpDashColor3;
            
            string pTxt = StringFormat("%s #%d | PnL: %.2f", pType, ticket, profit);
            CreateLabel("Lbl_Pos_"+(string)ownPositionIndex, InpDashX, y, pTxt, pColor);
            y += lineHeight;
            
            string slTxt = StringFormat("  > Stealth SL: %.5f (Gap: %.1f)", vSL, distToSL/10);
            CreateLabel("Lbl_PosSL_"+(string)ownPositionIndex, InpDashX, y, slTxt, clrOrange);
            y += lineHeight + 5;
            ownPositionIndex++;
         }
      }
   }
   if(ownPositionIndex == 0) {
      ObjectDelete(0, "Lbl_Pos_0");
      ObjectDelete(0, "Lbl_PosSL_0"); 
   }
}

void CreateLabel(string name, int x, int y, string text, color clr)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
}

#undef OnTester
// Post-test export only. None of these fields is a predictive feature.
void CPBT_ExportDeals()
{
   if(!MQLInfoInteger(MQL_TESTER)) return;
   string fn=StringFormat("D_%I64u.csv",GetTickCount64());
   int h=FileOpen(fn,FILE_WRITE|FILE_CSV|FILE_ANSI,',');
   if(h==INVALID_HANDLE) { Print("CPBT_EXPORT FAIL file_error=",GetLastError()); return; }
   FileWrite(h,"deal","time_msc","symbol","type","entry","position_id","order","magic","volume","price","profit","commission","swap","fee","reason");
   if(!HistorySelect(0,TimeCurrent())) { FileClose(h); Print("CPBT_EXPORT FAIL history_error=",GetLastError()); return; }
   int n=HistoryDealsTotal(),written=0;
   for(int i=0;i<n;i++)
   {
      ulong d=HistoryDealGetTicket(i);
      if(d==0) continue;
      FileWrite(h,d,HistoryDealGetInteger(d,DEAL_TIME_MSC),HistoryDealGetString(d,DEAL_SYMBOL),
         HistoryDealGetInteger(d,DEAL_TYPE),HistoryDealGetInteger(d,DEAL_ENTRY),
         HistoryDealGetInteger(d,DEAL_POSITION_ID),HistoryDealGetInteger(d,DEAL_ORDER),
         HistoryDealGetInteger(d,DEAL_MAGIC),DoubleToString(HistoryDealGetDouble(d,DEAL_VOLUME),8),
         DoubleToString(HistoryDealGetDouble(d,DEAL_PRICE),8),DoubleToString(HistoryDealGetDouble(d,DEAL_PROFIT),8),
         DoubleToString(HistoryDealGetDouble(d,DEAL_COMMISSION),8),DoubleToString(HistoryDealGetDouble(d,DEAL_SWAP),8),
         DoubleToString(HistoryDealGetDouble(d,DEAL_FEE),8),HistoryDealGetInteger(d,DEAL_REASON));
      written++;
   }
   FileClose(h);
   PrintFormat("CPBT_EXPORT PASS file=%s rows=%d",fn,written);
   datetime first=D'2026.08.24 00:00:00';
   for(int day=0;day<5;day++)
   {
      MqlTick tape[];
      ulong a=(ulong)(first+day*86400)*1000;
      ResetLastError();
      int count=CopyTicksRange(_Symbol,tape,COPY_TICKS_ALL,a,a+86400000-1);
      long time_sum=0,bid_sum=0,ask_sum=0;
      for(int k=0;k<count;k++)
      {
         time_sum+=tape[k].time_msc-(long)a;
         bid_sum+=(long)MathRound(tape[k].bid*100.0);
         ask_sum+=(long)MathRound(tape[k].ask*100.0);
      }
      PrintFormat("CPBT_TAPE day=%d count=%d time_sum=%I64d bid_sum=%I64d ask_sum=%I64d error=%d",
         day,count,time_sum,bid_sum,ask_sum,GetLastError());
   }
}

double OnTester()
{
   double score=CPBT_OriginalOnTester();
   CPBT_ExportDeals();
   return score;
}
