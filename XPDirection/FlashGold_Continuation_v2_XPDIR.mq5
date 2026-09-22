#define OnTester CPBT_OriginalOnTester
#property description "FlashGold_Continuation_v2 | active continuation entry filter"
// FlashGold_Continuation_v2.mq5
// Separate derivative of FlashGoldVirtual.mq5; Continuation v2.
//+------------------------------------------------------------------+
//|                                          FlashGold_Continuation_v2.mq5    |
//|                                  Copyright 2025, Senior Engineer |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Senior MQL5 Engineer"
#property link      "https://www.mql5.com"
#property version   "1.05-XPDIR" // 1.03 + XPW Direction Ladder v1 (DIR_OFF = 1.03)
#property strict

#include <Trade\Trade.mqh>

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
   input double   InpBurstThresholdFixed  = 172.0;   // Fixed burst threshold (Points); used when mode = FIXED
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

//+------------------------------------------------------------------+
//| XPW Direction Ladder v1 - the EA stops choosing its own side.     |
//| DIR_OFF reproduces 1.03 exactly (no handles, no reads, no writes).|
//+------------------------------------------------------------------+
enum ENUM_XPDIR      { XPDIR_NONE = 0, XPDIR_BUY = 1, XPDIR_SELL = -1 };
enum ENUM_XPDIR_MODE { DIR_OFF = 0, DIR_LOCK = 1, DIR_TRANSLATE = 2 };

input group "--- XPW Direction Ladder ---"
input ENUM_XPDIR_MODE InpDirMode                    = DIR_OFF;
input string          InpDirMapIndicator            = "XPW_ShapeMap_v0.4";
input ENUM_TIMEFRAMES InpDirParentTF                = PERIOD_M5;
input bool            InpDirUseS5                   = true;
input bool            InpDirUseS10                  = true;
input bool            InpDirUseS15                  = false;
input bool            InpDirUseS30                  = false;
input bool            InpDirUseS45                  = false;
input int             InpDirMinChildrenWithParent   = 2;
input int             InpDirMinChildrenAgainstParent= 3;
input bool            InpDirS1RequiredAgainstParent = true;
input int             InpDirMaxRungStaleBars        = 3;
input bool            InpDirWriteCsv                = true;  // XPDir decision CSV
//--- the cross is the signal (owner's correction 2026-09-22). A rung votes
//    the cross it just made; state is the floor it falls back to, never the signal.
input int             InpDirCrossMaxAgeBars         = 3;     // cross age window, in that rung's OWN bars (0 = off)
input double          InpDirEarlySepMult            = 2.0;   // EARLY band: |sepNow| <= |crossSep| * mult
input bool            InpDirRequireFreshS1          = false; // S1 must vote a cross, never STALE_STATE

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
// BURST_MIN_POINTS retired: the fixed-mode threshold is now the input
// InpBurstThresholdFixed, whose default is the 172.0 this constant held.
// One number, one place to edit - a dead constant beside a live input is a trap.
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
      thresholdPoints = InpBurstThresholdFixed;
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
   if(InpBurstPercentile < 0.0 || InpBurstPercentile > 100.0 ||
      InpBurstWindowSamples < 2 || InpBurstLookbackMs <= 0 ||
      InpEntryHoldMs < 0 || InpEntryHoldMinFavPoints < 0.0 ||
      InpBurstThresholdFixed <= 0.0)
   {
      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT invalid gate settings burst_percentile=%.4f burst_window_samples=%d burst_lookback_ms=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f burst_threshold_fixed_points=%.1f",
                  InpBurstPercentile, InpBurstWindowSamples,
                  InpBurstLookbackMs, InpEntryHoldMs,
                  InpEntryHoldMinFavPoints, InpBurstThresholdFixed);
      return(INIT_PARAMETERS_INCORRECT);
   }

   InitializeBurstPercentileWindow();
   g_MasterVwapTerminalId = MasterVwapTerminalIdFromDataPath();

   if(!ValidateAndLogBrokerProfile())
      return(INIT_FAILED);

   // XPDIR: the direction ladder. DIR_OFF creates no handle and reads nothing.
   if(!XPDir_Init())
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
               BurstThresholdModeName(), InpBurstThresholdFixed,
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
   XPDir_Deinit();          // XPDIR: IndicatorRelease on every rung handle
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
   XPDir_FunnelHeartbeat();   // XPDIR: says why the ladder is silent, unprompted
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
               burstThresholdPoints, InpBurstThresholdFixed,
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
   if(InpDirMode == DIR_TRANSLATE)
   {
      // XPDIR: in TRANSLATE the level that crossed is not necessarily the exec
      // side's level. Zero both, or the crossed level re-fires every tick.
      g_VirtualBuyStopPrice  = 0.0;
      g_VirtualSellStopPrice = 0.0;
   }
   else if(isBuy) g_VirtualBuyStopPrice = 0.0;
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
//| XPW Direction Ladder v1                                           |
//|                                                                   |
//| One decision, XPDir_Current(), fed by a fractal ladder of XPW     |
//| Shape Map instances: S1 (mandatory), the enabled optional         |
//| children S5/S10/S15/S30/S45, and one parent timeframe on _Symbol  |
//| (mandatory). Nothing in this block touches a gate, the hold, the  |
//| money management, the trailing, the CP wrapper or either          |
//| observer. With InpDirMode == DIR_OFF not a single line below runs |
//| past its first guard.                                             |
//|                                                                   |
//| Map semantics are taken from XPMap/XPW_ShapeMap_v0.4.mq5          |
//| (branch claude/cool-curie-89fhgg, commit 579cb33), never from a   |
//| description of it:                                                |
//|   buffer  1 FAST, 2 SLOW : EMPTY_VALUE is the map's own valid     |
//|                            flag (BufFast[i] = fastOk ? fast :     |
//|                            EMPTY_VALUE).                          |
//|   buffer 22 STATE        : isRedNow, NOT a validity flag - it is  |
//|                            0 both for "fast <= slow" and for an   |
//|                            invalid bar (stUp is forced false when |
//|                            !fastOk || !slowOk), and it is         |
//|                            inverted by the map's invertFill       |
//|                            input, which defaults to true. Logged  |
//|                            for cross-check only; never voted on.  |
//|   buffer 23 RUNLEN       : bars in the current colour run, 1 on   |
//|                            the flip bar.                          |
//| THE CROSS IS THE SIGNAL (owner's correction, 2026-09-22).         |
//| Direction is not the fill colour. It is the cross of the fast      |
//| (white) line through the slow line; the colour is what the cross   |
//| leaves behind. A cross has a moment and an age, a colour has       |
//| neither, and the early crosses - fast cutting through while the    |
//| fill is still the old colour - are the ones worth having. So every |
//| rung reports a cross event: crossDir, crossAge, crossSep, sepNow,  |
//| and state kept only as the floor the vote falls back to when no    |
//| cross is in the window. Reading state where a cross was available  |
//| is a defect, not a shortcut.                                       |
//|                                                                    |
//| Cross detection is on CLOSED bars only: a cross exists on bar i    |
//| when sign(fast-slow) at i differs from sign(fast-slow) at i+1.     |
//| Never on the forming bar - that is the repaint the map's           |
//| confirmed-bars rule exists to prevent, and an early cross read     |
//| from a forming bar is the easiest way to fake good results and     |
//| lose real money. Bar index 1 is the newest bar this code will      |
//| look at, on every rung, always.                                    |
//|                                                                    |
//| POLARITY, confirmed by the owner 2026-09-22: ignore the fill       |
//| entirely and read the two lines. Fast (white) is the shorter        |
//| average and moves first. fast > slow is momentum up = BUY,          |
//| fast < slow is momentum down = SELL, and the cross is the moment.   |
//| The owner's 20:56-20:57 frames show the fill painting RED on a      |
//| climb and GREEN on a drop - invertFill = true, colour running       |
//| opposite to price - which is why STATE is never read for direction. |
//+------------------------------------------------------------------+
#define XPDIR_RUNGS        7
#define XPDIR_IDX_S1       0
#define XPDIR_IDX_PARENT   6
#define XPDIR_BUF_FAST     1
#define XPDIR_BUF_SLOW     2
#define XPDIR_BUF_STATE   22
#define XPDIR_BUF_RUNLEN  23

//--- vote grades. Three labels, never multiplied into a score.
#define XPDIR_GRADE_NONE   0   // no vote
#define XPDIR_GRADE_EARLY  1   // just crossed, lines barely separated
#define XPDIR_GRADE_FRESH  2   // crossed inside the window, already widening
#define XPDIR_GRADE_STALE  3   // vote came from state, not from a cross

//--- how far back a rung read looks for its last cross. Bounded: past the age
//    window the vote falls back to state anyway, so there is nothing to find.
#define XPDIR_SCAN_MIN     4
#define XPDIR_SCAN_MAX   256

//--- funnel heartbeat: how many dumps before it stops repeating itself
#define XPDIR_FUNNEL_MAX_DUMPS 30

//--- the map's own defaults, in the map's declaration order. iCustom binds
//    positionally, so this list is the contract. Detector inputs are never
//    retuned; only the five marked OVERRIDE differ from the map's default.
#define XPDIR_MAP_rsiLen          14
#define XPDIR_MAP_fastLen          2
#define XPDIR_MAP_slowLen          7
#define XPDIR_MAP_invertFill    true
#define XPDIR_MAP_extLook         20
#define XPDIR_MAP_loFrac        0.33
#define XPDIR_MAP_hiFrac        0.67
#define XPDIR_MAP_sqBotOn      false   // OVERRIDE (visual; buffers unaffected)
#define XPDIR_MAP_sqBotMin         1
#define XPDIR_MAP_sqBotMax         3
#define XPDIR_MAP_sqBotCtx         2
#define XPDIR_MAP_sqBotSep       0.0
#define XPDIR_MAP_sqBotArea     true
#define XPDIR_MAP_sqTopOn      false   // OVERRIDE (visual; buffers unaffected)
#define XPDIR_MAP_sqTopMin         1
#define XPDIR_MAP_sqTopMax         2
#define XPDIR_MAP_sqTopCtx         3
#define XPDIR_MAP_sqTopSep       0.0
#define XPDIR_MAP_sqTopArea     true
#define XPDIR_MAP_tickOn        true   // detector: left at the map default
#define XPDIR_MAP_atrLen          14
#define XPDIR_MAP_dnWickFrac    0.55
#define XPDIR_MAP_dnWickAtr      0.8
#define XPDIR_MAP_upWickFrac    0.70
#define XPDIR_MAP_upWickAtr      1.2
#define XPDIR_MAP_tickPrice    false   // OVERRIDE: true routes tick labels to
                                       // window 0 - the EA's chart - even from
                                       // an iCustom instance (DrawTickLabel).
#define XPDIR_MAP_showTbl      false   // OVERRIDE (visual)
#define XPDIR_MAP_LastBarIsClosed false // OVERRIDE per spec (= map default)
#define XPDIR_MAP_SkipEmptyBars   false // OVERRIDE per spec (= map default)
#define XPDIR_MAP_DumpCSV         false // OVERRIDE per spec (= map default)

//--- rung state
int      g_XPDirHandle[XPDIR_RUNGS];
string   g_XPDirSymbol[XPDIR_RUNGS];
string   g_XPDirTag[XPDIR_RUNGS]      = {"S1","S5","S10","S15","S30","S45","P"};
int      g_XPDirDeclSecs[XPDIR_RUNGS] = {1,5,10,15,30,45,0};   // [PARENT] filled in OnInit
int      g_XPDirIntervalS[XPDIR_RUNGS];
bool     g_XPDirEnabled[XPDIR_RUNGS];
bool     g_XPDirReadyLogged[XPDIR_RUNGS];
int      g_XPDirVote[XPDIR_RUNGS];        // +1 BUY, -1 SELL, 0 NO_VOTE
int      g_XPDirGrade[XPDIR_RUNGS];       // EARLY / FRESH / STALE_STATE / NONE
int      g_XPDirCrossDir[XPDIR_RUNGS];    // +1 crossed up, -1 crossed down, 0 none
int      g_XPDirCrossAge[XPDIR_RUNGS];    // closed bars since that cross; 0 = last bar
double   g_XPDirCrossSep[XPDIR_RUNGS];    // fast-slow at the cross bar, map units
double   g_XPDirSepNow[XPDIR_RUNGS];      // fast-slow on the bar being read
int      g_XPDirSign[XPDIR_RUNGS];        // the CARRIED sign: the state fallback
bool     g_XPDirBufProbed[XPDIR_RUNGS];   // buffer-contract probe done for this rung
datetime g_XPDirLastBarTime[XPDIR_RUNGS]; // newest closed bar seen, for the scan width
int      g_XPDirRunLen[XPDIR_RUNGS];
double   g_XPDirState[XPDIR_RUNGS];       // the map's STATE buffer, logged only
string   g_XPDirWhy[XPDIR_RUNGS];         // last NO_VOTE reason (funnel)

//--- clamped copies
int      g_XPDirMinWith          = 2;
int      g_XPDirMinAgainst       = 3;
int      g_XPDirMaxStaleBars     = 3;
int      g_XPDirCrossMaxAge      = 3;
double   g_XPDirEarlySepMult     = 2.0;

//--- decision cache and state
bool     g_XPDirReady            = false;
ENUM_XPDIR g_XPDirCached         = XPDIR_NONE;
int      g_XPDirCachedRule       = 0;
bool     g_XPDirCachedConflict   = false;
datetime g_XPDirCacheKey         = 0;
datetime g_XPDirCacheSecond      = 0;
bool     g_XPDirCacheFilled      = false;
string   g_XPDirLastStateLine    = "";
bool     g_XPDirHoldTriggerIsBuy = false;
datetime g_XPDirLastBlockedSec   = 0;
int      g_XPDirLastArmed        = -2;    // -2 = never logged
ulong    g_XPDirEvals            = 0;
ulong    g_XPDirStateLines       = 0;
datetime g_XPDirFunnelLastSec    = 0;   // funnel heartbeat (zero-result contingency)
int      g_XPDirFunnelDumps      = 0;

const string XPDIR_CSV_NAME = "XPChart\\FlashGold_Continuation_v2_XPDir_v1.csv";

//+------------------------------------------------------------------+
//| XPDIR_RULE_CORE_BEGIN                                             |
//| Pure rule evaluation. No MQL5 runtime call, no global read: this  |
//| block is lifted verbatim by XPDirection/reference/vote_ref.py     |
//| (Gate 1) and compiled and executed unchanged by the emu harness.  |
//| Votes are +1 BUY, -1 SELL, 0 NO_VOTE. NO_VOTE is never counted as |
//| disagreement: it simply fails to be counted for either direction. |
//+------------------------------------------------------------------+
// EMPTY_VALUE in FAST or SLOW is the map's own valid flag
// (XPW_ShapeMap_v0.4.mq5: BufFast[i] = fastOk ? fast : EMPTY_VALUE).
bool XPDir_CoreIsEmpty(const double v)
{
   return (!MathIsValidNumber(v) || MathAbs(v) >= EMPTY_VALUE);
}

int XPDir_Sign(const double v)
{
   if(v > 0.0) return  1;     // fast above slow -> BUY side
   if(v < 0.0) return -1;
   return 0;
}

// Walk the newly CLOSED bars oldest -> newest and carry the sign forward.
//
//   fast[]/slow[] are newest-first: index 0 is the bar that just closed, and
//   the forming bar is never in them. The newCount newest entries are the
//   bars not yet processed; older entries are context only.
//
//   Equality is not a sign. A bar where fast == slow INHERITS the previous
//   closed bar's carried sign, so a touch is not a cross and a touch that
//   resumes the same side is not a cross either. Only a strict flip of the
//   carried sign is a cross, and it is stamped on the bar where the new
//   non-zero sign appears. (This deliberately differs from Pine's
//   ta.crossover, which treats the touch bar as the event.)
//
//   crossDir PERSISTS: it is the direction of the most recent cross since
//   warm-up, held until the next one. It is 0 only while no cross has been
//   seen at all. "Crossed on this bar" is crossAge == 0 - there is no
//   separate flag.
//
// carriedSign / crossDir / crossAge / crossSep are in-out: the caller keeps
// them per rung between reads, which is what makes crossAge exact across
// missing bars and stalls instead of a division of timestamps.
void XPDir_AdvanceCross(const double &fast[], const double &slow[], const int newCount,
                        int &carriedSign, int &crossDir, int &crossAge, double &crossSep)
{
   for(int b = newCount - 1; b >= 0; b--)
   {
      if(XPDir_CoreIsEmpty(fast[b]) || XPDir_CoreIsEmpty(slow[b]))
         continue;                       // the map has not processed this bar
      const double sep = fast[b] - slow[b];
      const int    s   = XPDir_Sign(sep);
      bool crossed = false;
      if(s != 0)
      {
         if(carriedSign == 0)
            carriedSign = s;             // the first sign of all is not a cross
         else if(s != carriedSign)
         {
            carriedSign = s;
            crossDir    = s;
            crossSep    = sep;
            crossAge    = 0;
            crossed     = true;
         }
      }
      if(!crossed && crossAge >= 0) crossAge++;
   }
}

// One rung's vote.
//
//   crossAge inside the window          -> vote = crossDir   (EARLY | FRESH)
//   crossAge outside it, or -1, or
//   ageing disabled                     -> vote = carriedSign (STALE_STATE)
//   map warm-up, stale feed, sign still
//   zero                                -> NO_VOTE
//
// An unknown age (-1, no cross seen yet) is treated as OLD, not as absent: the
// rung still votes its carried sign, marked STALE_STATE, exactly like a cross
// that has aged out. NO_VOTE is only for "the map has not produced this bar",
// "the feed is stale" and "the sign is still zero".
//
// crossMaxAgeBars counts the RUNG'S OWN bars: 3 is three seconds on S1 and
// 135 seconds on S45. "Early" is fractal, like everything else here. 0 makes
// every vote the carried sign and every grade STALE_STATE - the pure-colour
// baseline, for comparison only. The cross fields are still logged there.
int XPDir_VoteFromCross(const double sepNow, const bool bar0Valid,
                        const int carriedSign, const int crossDir,
                        const int crossAge, const double crossSep,
                        const long ageSeconds, const int intervalSeconds,
                        const int maxStaleBars, const int crossMaxAgeBars,
                        const double earlySepMult,
                        int &gradeOut, string &whyOut)
{
   gradeOut = XPDIR_GRADE_NONE;
   if(!bar0Valid)                                            { whyOut = "map_invalid"; return 0; }
   if(ageSeconds > (long)maxStaleBars * (long)intervalSeconds){ whyOut = "stale";       return 0; }
   if(carriedSign == 0)                                      { whyOut = "sign_zero";   return 0; }

   if(crossMaxAgeBars > 0 && crossAge >= 0 && crossAge <= crossMaxAgeBars)
   {
      // EARLY: it just crossed, or the lines have barely separated and the
      // move has not been paid out yet. That is the "it crossed early and
      // it's even better" case.
      gradeOut = (crossAge == 0 ||
                  MathAbs(sepNow) <= MathAbs(crossSep) * earlySepMult)
                 ? XPDIR_GRADE_EARLY : XPDIR_GRADE_FRESH;
      whyOut = "cross";
      return crossDir;
   }

   // state is the floor, never the signal
   gradeOut = XPDIR_GRADE_STALE;
   whyOut   = (crossAge < 0) ? "state_no_cross_seen" : "state_cross_aged_out";
   return carriedSign;
}

int XPDir_RulePassesFor(const int x,
                        const int parentVote,
                        const int s1Vote,
                        const bool s1Fresh,
                        const int &optionalVotes[],
                        const int minWithParent,
                        const int minAgainstParent,
                        const bool s1RequiredAgainstParent,
                        const bool requireFreshS1)
{
   int nOptional = 0;
   for(int i = 0; i < ArraySize(optionalVotes); i++)
      if(optionalVotes[i] == x) nOptional++;

   // requireFreshS1 applies to every rule that NEEDS C1 == X, and to no other.
   // R2 is untouched by it, and no other rung's grade is ever enforced.
   const bool s1Counts = (s1Vote == x) && (!requireFreshS1 || s1Fresh);

   if(parentVote == x)
   {
      if(s1Counts) return 1;                                 // R1 aligned
      if(s1Vote != x && nOptional >= minWithParent) return 2; // R2 parent carries
      return 0;
   }
   // P != X. A NO_VOTE parent lands here too: it cannot satisfy R1 or R2,
   // and the prompt states R3 as "P != X" literally (report: AMBIGUITY-R3-P-NV).
   const int nAgainst = nOptional + ((s1Vote == x) ? 1 : 0); // S1 counts as a child
   if(nAgainst >= minAgainstParent &&
      (!s1RequiredAgainstParent || s1Counts))
      return 3;                                              // R3 children overrule
   return 0;
}

int XPDir_DecideFromVotes(const int parentVote,
                          const int s1Vote,
                          const bool s1Fresh,
                          const int &optionalVotes[],
                          const int minWithParent,
                          const int minAgainstParent,
                          const bool s1RequiredAgainstParent,
                          const bool requireFreshS1,
                          int &ruleOut,
                          bool &conflictOut)
{
   ruleOut = 0;
   conflictOut = false;
   const int rBuy  = XPDir_RulePassesFor(1, parentVote, s1Vote, s1Fresh, optionalVotes,
                                         minWithParent, minAgainstParent,
                                         s1RequiredAgainstParent, requireFreshS1);
   const int rSell = XPDir_RulePassesFor(-1, parentVote, s1Vote, s1Fresh, optionalVotes,
                                         minWithParent, minAgainstParent,
                                         s1RequiredAgainstParent, requireFreshS1);
   if(rBuy > 0 && rSell > 0) { conflictOut = true; return 0; }
   if(rBuy  > 0) { ruleOut = rBuy;  return  1; }
   if(rSell > 0) { ruleOut = rSell; return -1; }
   return 0;
}
//| XPDIR_RULE_CORE_END                                               |
//+------------------------------------------------------------------+

string XPDir_VoteTag(const int rungIndex)
{
   if(!g_XPDirEnabled[rungIndex]) return "-";
   if(g_XPDirVote[rungIndex] > 0)  return "BUY";
   if(g_XPDirVote[rungIndex] < 0)  return "SELL";
   return "NV";
}

string XPDir_GradeName(const int grade)
{
   if(grade == XPDIR_GRADE_EARLY) return "EARLY";
   if(grade == XPDIR_GRADE_FRESH) return "FRESH";
   if(grade == XPDIR_GRADE_STALE) return "STALE_STATE";
   return "-";
}

string XPDir_GradeLetter(const int grade)
{
   if(grade == XPDIR_GRADE_EARLY) return "E";
   if(grade == XPDIR_GRADE_FRESH) return "F";
   if(grade == XPDIR_GRADE_STALE) return "S";
   return "-";
}

// "BUY:EARLY@0" / "SELL:STALE_STATE@37" / "NV" / "-"
string XPDir_RungTag(const int rungIndex)
{
   if(!g_XPDirEnabled[rungIndex]) return "-";
   if(g_XPDirVote[rungIndex] == 0) return "NV";
   return XPDir_VoteTag(rungIndex) + ":" + XPDir_GradeName(g_XPDirGrade[rungIndex]) +
          "@" + IntegerToString(g_XPDirCrossAge[rungIndex] < 0 ? -1 : g_XPDirCrossAge[rungIndex]);
}

// the CSV's per-rung grade column: "EARLY@0", "STALE_STATE@37", "-"
string XPDir_GradeCell(const int rungIndex)
{
   if(!g_XPDirEnabled[rungIndex] || g_XPDirGrade[rungIndex] == XPDIR_GRADE_NONE) return "-";
   return XPDir_GradeName(g_XPDirGrade[rungIndex]) + "@" +
          IntegerToString(g_XPDirCrossAge[rungIndex] < 0 ? -1 : g_XPDirCrossAge[rungIndex]);
}

string XPDir_DirName(const ENUM_XPDIR d)
{
   if(d == XPDIR_BUY)  return "BUY";
   if(d == XPDIR_SELL) return "SELL";
   return "NONE";
}

string XPDir_ModeName()
{
   if(InpDirMode == DIR_LOCK)      return "DIR_LOCK";
   if(InpDirMode == DIR_TRANSLATE) return "DIR_TRANSLATE";
   return "DIR_OFF";
}

//+------------------------------------------------------------------+
//| CSV                                                               |
//+------------------------------------------------------------------+
void XPDir_WriteCsv(const string eventName, const string triggerSide,
                    const string execSide, const string action)
{
   if(!InpDirWriteCsv || InpDirMode == DIR_OFF) return;

   // The section-5 columns come first and in their original order, so anything
   // already parsing this file keeps working. The cross columns are appended:
   // one grade@age cell per rung, plus S1's cross detail.
   const string header = "server_msc,event,mode,dir,rule,P,C1,C5,C10,C15,C30,C45,"
                         "runlen1,trigger_side,exec_side,action,"
                         "P_g,C1_g,C5_g,C10_g,C15_g,C30_g,C45_g,"
                         "c1_cross_dir,c1_cross_age,c1_cross_sep,c1_sep_now,c1_state";
   const string row = StringFormat("%I64d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%d,%s,%s,%s,"
                                   "%s,%s,%s,%s,%s,%s,%s,%d,%d,%.6f,%.6f,%d",
                                   (long)TimeCurrent() * 1000 + (long)(GetTickCount64() % 1000),
                                   eventName, XPDir_ModeName(),
                                   XPDir_DirName(g_XPDirCached),
                                   g_XPDirCachedRule > 0 ? "R" + IntegerToString(g_XPDirCachedRule) : "-",
                                   XPDir_VoteTag(XPDIR_IDX_PARENT),
                                   XPDir_VoteTag(0), XPDir_VoteTag(1), XPDir_VoteTag(2),
                                   XPDir_VoteTag(3), XPDir_VoteTag(4), XPDir_VoteTag(5),
                                   g_XPDirRunLen[XPDIR_IDX_S1],
                                   triggerSide, execSide, action,
                                   XPDir_GradeCell(XPDIR_IDX_PARENT),
                                   XPDir_GradeCell(0), XPDir_GradeCell(1), XPDir_GradeCell(2),
                                   XPDir_GradeCell(3), XPDir_GradeCell(4), XPDir_GradeCell(5),
                                   g_XPDirCrossDir[XPDIR_IDX_S1], g_XPDirCrossAge[XPDIR_IDX_S1],
                                   g_XPDirCrossSep[XPDIR_IDX_S1], g_XPDirSepNow[XPDIR_IDX_S1],
                                   g_XPDirSign[XPDIR_IDX_S1]);

   const int h = FileOpen(XPDIR_CSV_NAME,
                          FILE_READ | FILE_WRITE | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE, ",");
   if(h == INVALID_HANDLE)
   {
      PrintFormat("XPDIR CSV_OPEN_FAILED file=%s error=%d", XPDIR_CSV_NAME, GetLastError());
      return;
   }
   FileSeek(h, 0, SEEK_END);
   if(FileSize(h) == 0) FileWriteString(h, header + "\r\n");
   FileWriteString(h, row + "\r\n");
   FileClose(h);
}

//+------------------------------------------------------------------+
//| Init / deinit                                                     |
//+------------------------------------------------------------------+
string XPDir_ParamList()
{
   return StringFormat("rsiLen=%d,fastLen=%d,slowLen=%d,invertFill=%s,extLook=%d,"
                       "loFrac=%.2f,hiFrac=%.2f,sqBotOn=%s,sqBotMin=%d,sqBotMax=%d,"
                       "sqBotCtx=%d,sqBotSep=%.1f,sqBotArea=%s,sqTopOn=%s,sqTopMin=%d,"
                       "sqTopMax=%d,sqTopCtx=%d,sqTopSep=%.1f,sqTopArea=%s,tickOn=%s,"
                       "atrLen=%d,dnWickFrac=%.2f,dnWickAtr=%.2f,upWickFrac=%.2f,"
                       "upWickAtr=%.2f,tickPrice=%s,showTbl=%s,LastBarIsClosed=%s,"
                       "SkipEmptyBars=%s,DumpCSV=%s",
                       XPDIR_MAP_rsiLen, XPDIR_MAP_fastLen, XPDIR_MAP_slowLen,
                       XPDIR_MAP_invertFill ? "true" : "false", XPDIR_MAP_extLook,
                       XPDIR_MAP_loFrac, XPDIR_MAP_hiFrac,
                       XPDIR_MAP_sqBotOn ? "true" : "false",
                       XPDIR_MAP_sqBotMin, XPDIR_MAP_sqBotMax, XPDIR_MAP_sqBotCtx,
                       XPDIR_MAP_sqBotSep, XPDIR_MAP_sqBotArea ? "true" : "false",
                       XPDIR_MAP_sqTopOn ? "true" : "false",
                       XPDIR_MAP_sqTopMin, XPDIR_MAP_sqTopMax, XPDIR_MAP_sqTopCtx,
                       XPDIR_MAP_sqTopSep, XPDIR_MAP_sqTopArea ? "true" : "false",
                       XPDIR_MAP_tickOn ? "true" : "false", XPDIR_MAP_atrLen,
                       XPDIR_MAP_dnWickFrac, XPDIR_MAP_dnWickAtr,
                       XPDIR_MAP_upWickFrac, XPDIR_MAP_upWickAtr,
                       XPDIR_MAP_tickPrice ? "true" : "false",
                       XPDIR_MAP_showTbl ? "true" : "false",
                       XPDIR_MAP_LastBarIsClosed ? "true" : "false",
                       XPDIR_MAP_SkipEmptyBars ? "true" : "false",
                       XPDIR_MAP_DumpCSV ? "true" : "false");
}

int XPDir_CreateHandle(const string sym, const ENUM_TIMEFRAMES tf)
{
   // Positional binding, map declaration order, 30 inputs. Do not reorder.
   return iCustom(sym, tf, InpDirMapIndicator,
                  XPDIR_MAP_rsiLen,
                  XPDIR_MAP_fastLen,
                  XPDIR_MAP_slowLen,
                  XPDIR_MAP_invertFill,
                  XPDIR_MAP_extLook,
                  XPDIR_MAP_loFrac,
                  XPDIR_MAP_hiFrac,
                  XPDIR_MAP_sqBotOn,
                  XPDIR_MAP_sqBotMin,
                  XPDIR_MAP_sqBotMax,
                  XPDIR_MAP_sqBotCtx,
                  XPDIR_MAP_sqBotSep,
                  XPDIR_MAP_sqBotArea,
                  XPDIR_MAP_sqTopOn,
                  XPDIR_MAP_sqTopMin,
                  XPDIR_MAP_sqTopMax,
                  XPDIR_MAP_sqTopCtx,
                  XPDIR_MAP_sqTopSep,
                  XPDIR_MAP_sqTopArea,
                  XPDIR_MAP_tickOn,
                  XPDIR_MAP_atrLen,
                  XPDIR_MAP_dnWickFrac,
                  XPDIR_MAP_dnWickAtr,
                  XPDIR_MAP_upWickFrac,
                  XPDIR_MAP_upWickAtr,
                  XPDIR_MAP_tickPrice,
                  XPDIR_MAP_showTbl,
                  XPDIR_MAP_LastBarIsClosed,
                  XPDIR_MAP_SkipEmptyBars,
                  XPDIR_MAP_DumpCSV);
}

// When a rung symbol is missing, say what IS there instead of just what is not.
// The usual cause is the EA sitting on a _S<n> chart: the ladder derives every
// rung from _Symbol, so an EA on XAUUSD-ECNc_S1 goes looking for
// XAUUSD-ECNc_S1_S1, which nothing will ever create.
void XPDir_DiagnoseSymbols(const string wanted)
{
   const int p = StringFind(_Symbol, "_S");
   if(p >= 0)
   {
      bool allDigits = false;
      for(int i = p + 2; i < StringLen(_Symbol); i++)
      {
         const ushort ch = StringGetCharacter(_Symbol, i);
         if(ch < '0' || ch > '9') { allDigits = false; break; }
         allDigits = true;
      }
      if(allDigits)
         PrintFormat("XPDIR HINT _Symbol=%s is itself a seconds symbol. Attach this EA to the "
                     "PARENT (%s), not to a _S<n> chart. Custom symbols do not trade, and the "
                     "ladder derives every rung from _Symbol.",
                     _Symbol, StringSubstr(_Symbol, 0, p));
   }

   const string prefix = _Symbol + "_S";
   const int total = SymbolsTotal(false);
   string found = "";
   int n = 0;
   for(int i = 0; i < total; i++)
   {
      const string name = SymbolName(i, false);
      if(StringFind(name, prefix) != 0) continue;
      if(n > 0) found += ",";
      found += name;
      n++;
   }
   PrintFormat("XPDIR DIAG wanted=%s found_rung_symbols=[%s] count=%d symbols_known_to_terminal=%d",
               wanted, found, n, total);
   if(n == 0)
      PrintFormat("XPDIR HINT nothing named %s* exists. Start the XP ChartEngine service for "
                  "this parent and let it create the custom symbol before attaching the EA.",
                  prefix);
}

bool XPDir_Init()
{
   for(int r = 0; r < XPDIR_RUNGS; r++)
   {
      g_XPDirHandle[r]      = INVALID_HANDLE;
      g_XPDirSymbol[r]      = "";
      g_XPDirEnabled[r]     = false;
      g_XPDirReadyLogged[r] = false;
      g_XPDirVote[r]        = 0;
      g_XPDirGrade[r]       = XPDIR_GRADE_NONE;
      g_XPDirCrossDir[r]    = 0;
      g_XPDirCrossAge[r]    = -1;
      g_XPDirCrossSep[r]    = 0.0;
      g_XPDirSepNow[r]      = 0.0;
      g_XPDirSign[r]        = 0;
      g_XPDirBufProbed[r]   = false;
      g_XPDirLastBarTime[r] = 0;
      g_XPDirRunLen[r]      = 0;
      g_XPDirState[r]       = EMPTY_VALUE;
      g_XPDirWhy[r]         = "init";
      g_XPDirIntervalS[r]   = 1;
   }
   g_XPDirReady = false;

   if(InpDirMode == DIR_OFF)
   {
      PrintFormat("XPDIR MODE mode=DIR_OFF - direction ladder inert, 1.03 behaviour");
      return true;
   }

   g_XPDirMinWith       = (InpDirMinChildrenWithParent    < 1) ? 1 : InpDirMinChildrenWithParent;
   g_XPDirMinAgainst    = (InpDirMinChildrenAgainstParent < 2) ? 2 : InpDirMinChildrenAgainstParent;
   g_XPDirMaxStaleBars  = (InpDirMaxRungStaleBars         < 1) ? 1 : InpDirMaxRungStaleBars;
   g_XPDirCrossMaxAge   = (InpDirCrossMaxAgeBars         < 0) ? 0 : InpDirCrossMaxAgeBars;
   g_XPDirEarlySepMult  = (InpDirEarlySepMult          < 0.0) ? 0.0 : InpDirEarlySepMult;
   if(g_XPDirMinWith != InpDirMinChildrenWithParent ||
      g_XPDirMinAgainst != InpDirMinChildrenAgainstParent ||
      g_XPDirMaxStaleBars != InpDirMaxRungStaleBars ||
      g_XPDirCrossMaxAge != InpDirCrossMaxAgeBars ||
      g_XPDirEarlySepMult != InpDirEarlySepMult)
      PrintFormat("XPDIR CLAMP min_with_parent=%d min_against_parent=%d max_stale_bars=%d cross_max_age_bars=%d early_sep_mult=%.3f",
                  g_XPDirMinWith, g_XPDirMinAgainst, g_XPDirMaxStaleBars,
                  g_XPDirCrossMaxAge, g_XPDirEarlySepMult);
   if(g_XPDirCrossMaxAge == 0)
      PrintFormat("XPDIR WARN cross ageing disabled (InpDirCrossMaxAgeBars=0) - every rung "
                  "votes its state fallback and no vote can ever grade EARLY or FRESH. "
                  "The cross is the signal; this setting throws it away.");

   bool useOptional[5];
   useOptional[0] = InpDirUseS5;
   useOptional[1] = InpDirUseS10;
   useOptional[2] = InpDirUseS15;
   useOptional[3] = InpDirUseS30;
   useOptional[4] = InpDirUseS45;

   // --- children S1..S45: symbol names derive from _Symbol, never a literal
   for(int r = 0; r <= 5; r++)
   {
      const bool wanted = (r == XPDIR_IDX_S1) ? true : useOptional[r - 1];
      g_XPDirSymbol[r]    = _Symbol + "_S" + IntegerToString(g_XPDirDeclSecs[r]);
      g_XPDirIntervalS[r] = g_XPDirDeclSecs[r];
      if(!wanted) { g_XPDirWhy[r] = "disabled"; continue; }

      if(!SymbolSelect(g_XPDirSymbol[r], true))
      {
         if(r == XPDIR_IDX_S1)
         {
            PrintFormat("XPDIR_INIT_ABORT rung=S1 reason=symbol_missing symbol=%s error=%d",
                        g_XPDirSymbol[r], GetLastError());
            XPDir_DiagnoseSymbols(g_XPDirSymbol[r]);
            return false;
         }
         PrintFormat("XPDIR RUNG_ABSENT rung=%s reason=symbol_missing symbol=%s error=%d",
                     g_XPDirTag[r], g_XPDirSymbol[r], GetLastError());
         g_XPDirWhy[r] = "symbol_missing";
         continue;
      }

      g_XPDirHandle[r] = XPDir_CreateHandle(g_XPDirSymbol[r], PERIOD_M1);
      if(g_XPDirHandle[r] == INVALID_HANDLE)
      {
         if(r == XPDIR_IDX_S1)
         {
            PrintFormat("XPDIR_INIT_ABORT rung=S1 reason=handle_invalid symbol=%s indicator=%s error=%d",
                        g_XPDirSymbol[r], InpDirMapIndicator, GetLastError());
            PrintFormat("XPDIR HINT iCustom could not load '%s'. It resolves relative to "
                        "MQL5\\Indicators: the compiled .ex5 must sit there, the input carries "
                        "no .ex5 extension, and a subfolder must be part of the name "
                        "(e.g. Subfolder\\\\XPW_ShapeMap_v0.4).", InpDirMapIndicator);
            return false;
         }
         PrintFormat("XPDIR RUNG_ABSENT rung=%s reason=handle_invalid symbol=%s error=%d",
                     g_XPDirTag[r], g_XPDirSymbol[r], GetLastError());
         g_XPDirWhy[r] = "handle_invalid";
         continue;
      }
      g_XPDirEnabled[r] = true;
      g_XPDirWhy[r]     = "warmup";
      PrintFormat("XPDIR RUNG_INIT rung=%s symbol=%s tf=PERIOD_M1 interval_s=%d handle=%d params=[%s]",
                  g_XPDirTag[r], g_XPDirSymbol[r], g_XPDirIntervalS[r],
                  g_XPDirHandle[r], XPDir_ParamList());
   }

   // --- parent: iCustom on _Symbol at InpDirParentTF, mandatory
   const int p = XPDIR_IDX_PARENT;
   g_XPDirSymbol[p]    = _Symbol;
   g_XPDirDeclSecs[p]  = (int)PeriodSeconds(InpDirParentTF);
   g_XPDirIntervalS[p] = g_XPDirDeclSecs[p];
   if(g_XPDirIntervalS[p] <= 0)
   {
      PrintFormat("XPDIR_INIT_ABORT rung=P reason=bad_parent_timeframe tf=%s",
                  EnumToString(InpDirParentTF));
      return false;
   }
   g_XPDirHandle[p] = XPDir_CreateHandle(g_XPDirSymbol[p], InpDirParentTF);
   if(g_XPDirHandle[p] == INVALID_HANDLE)
   {
      PrintFormat("XPDIR_INIT_ABORT rung=P reason=handle_invalid symbol=%s tf=%s indicator=%s error=%d",
                  g_XPDirSymbol[p], EnumToString(InpDirParentTF), InpDirMapIndicator, GetLastError());
      PrintFormat("XPDIR HINT iCustom could not load '%s'. It resolves relative to "
                  "MQL5\\Indicators: the compiled .ex5 must sit there, the input carries no "
                  ".ex5 extension, and a subfolder must be part of the name.", InpDirMapIndicator);
      return false;
   }
   g_XPDirEnabled[p] = true;
   g_XPDirWhy[p]     = "warmup";
   PrintFormat("XPDIR RUNG_INIT rung=P symbol=%s tf=%s interval_s=%d handle=%d params=[%s]",
               g_XPDirSymbol[p], EnumToString(InpDirParentTF), g_XPDirIntervalS[p],
               g_XPDirHandle[p], XPDir_ParamList());
   PrintFormat("XPDIR NOTE rung=P the map derives its expected interval from the symbol name "
               "(ParseExpectedInterval); '%s' has no _S<n> suffix so its axis row reads MISMATCH. "
               "That flag is cosmetic - it gates nothing in the map.", g_XPDirSymbol[p]);

   PrintFormat("XPDIR INIT mode=%s indicator=%s parent_tf=%s children=[S1%s%s%s%s%s] "
               "min_with_parent=%d min_against_parent=%d s1_required_against_parent=%d "
               "max_stale_bars=%d cross_max_age_bars=%d early_sep_mult=%.2f "
               "require_fresh_s1=%d csv=%d",
               XPDir_ModeName(), InpDirMapIndicator, EnumToString(InpDirParentTF),
               g_XPDirEnabled[1] ? ",S5" : "", g_XPDirEnabled[2] ? ",S10" : "",
               g_XPDirEnabled[3] ? ",S15" : "", g_XPDirEnabled[4] ? ",S30" : "",
               g_XPDirEnabled[5] ? ",S45" : "",
               g_XPDirMinWith, g_XPDirMinAgainst,
               InpDirS1RequiredAgainstParent ? 1 : 0,
               g_XPDirMaxStaleBars, g_XPDirCrossMaxAge,
               g_XPDirEarlySepMult, InpDirRequireFreshS1 ? 1 : 0, InpDirWriteCsv ? 1 : 0);
   g_XPDirReady = true;
   return true;
}

void XPDir_Deinit()
{
   for(int r = 0; r < XPDIR_RUNGS; r++)
   {
      if(g_XPDirHandle[r] != INVALID_HANDLE)
      {
         IndicatorRelease(g_XPDirHandle[r]);
         g_XPDirHandle[r] = INVALID_HANDLE;
      }
      g_XPDirEnabled[r] = false;
   }
   g_XPDirReady      = false;
   g_XPDirCacheFilled = false;
   if(InpDirMode != DIR_OFF)
      PrintFormat("XPDIR DEINIT handles_released evaluations=%I64u state_lines=%I64u",
                  g_XPDirEvals, g_XPDirStateLines);
}

//+------------------------------------------------------------------+
//| Buffer-contract probe.                                            |
//|                                                                    |
//| The map's FAST and SLOW buffers are SMAs of RSI, so a valid value  |
//| is inside [0, 100] - the map itself declares INDICATOR_MINIMUM 0   |
//| and INDICATOR_MAXIMUM 100. If the configured indices were pointing |
//| at VEL2, EFF2 or MBARS instead, the values would not sit in that   |
//| band. This runs once per rung, on its first valid read, and says   |
//| so out loud rather than letting the ladder vote on the wrong       |
//| buffer. See the report, DISCREPANCY-1 (two different buffer maps   |
//| exist for "XPW_ShapeMap_v0.4").                                    |
//+------------------------------------------------------------------+
bool XPDir_ProbeBufferContract(const int r, const double fast, const double slow)
{
   if(g_XPDirBufProbed[r]) return true;
   const bool ok = (fast >= -0.0001 && fast <= 100.0001 &&
                    slow >= -0.0001 && slow <= 100.0001);
   g_XPDirBufProbed[r] = true;
   if(ok)
   {
      PrintFormat("XPDIR BUF_CONTRACT rung=%s verdict=OK fast_idx=%d slow_idx=%d fast=%.4f slow=%.4f",
                  g_XPDirTag[r], XPDIR_BUF_FAST, XPDIR_BUF_SLOW, fast, slow);
      return true;
   }
   PrintFormat("XPDIR BLOCKED_MAP_CONTRACT_MISMATCH rung=%s fast_idx=%d slow_idx=%d fast=%.4f slow=%.4f "
               "- these are not SMAs of RSI. The indicator answering '%s' does not have the "
               "buffer map this build was compiled against. Fix XPDIR_BUF_FAST/SLOW or the "
               "indicator, do not guess: this rung is silenced.",
               g_XPDirTag[r], XPDIR_BUF_FAST, XPDIR_BUF_SLOW, fast, slow, InpDirMapIndicator);
   return false;
}

string XPDir_CarriedName(const int r)
{
   if(g_XPDirSign[r] > 0) return "BUY";
   if(g_XPDirSign[r] < 0) return "SELL";
   return "-";
}

//+------------------------------------------------------------------+
//| One rung read: a window of CLOSED bars ending at index 1.         |
//| Index 0 of the chart - the forming bar - is never copied. Only    |
//| the bars newer than the last one seen are walked, so the carried  |
//| sign, crossDir and crossAge advance exactly across gaps, missing  |
//| bars and stalls.                                                   |
//+------------------------------------------------------------------+
void XPDir_ReadRung(const int r)
{
   g_XPDirVote[r]     = 0;
   g_XPDirGrade[r]    = XPDIR_GRADE_NONE;
   g_XPDirRunLen[r]   = 0;
   g_XPDirState[r]    = EMPTY_VALUE;
   // g_XPDirSign / CrossDir / CrossAge / CrossSep persist across reads.

   if(!g_XPDirEnabled[r])                { g_XPDirWhy[r] = "disabled";       return; }
   if(g_XPDirHandle[r] == INVALID_HANDLE){ g_XPDirWhy[r] = "handle_invalid"; return; }

   const ENUM_TIMEFRAMES tf = (r == XPDIR_IDX_PARENT) ? InpDirParentTF : PERIOD_M1;

   const datetime barTime = iTime(g_XPDirSymbol[r], tf, 1);
   if(barTime <= 0) { g_XPDirWhy[r] = "no_bar_time"; return; }

   // how many closed bars are new since the last read
   int newBars = 1;
   bool firstRead = (g_XPDirLastBarTime[r] <= 0);
   if(!firstRead && g_XPDirIntervalS[r] > 0)
   {
      const long gone = ((long)barTime - (long)g_XPDirLastBarTime[r]) / (long)g_XPDirIntervalS[r];
      newBars = (int)((gone <= 0) ? 0 : ((gone > XPDIR_SCAN_MAX) ? XPDIR_SCAN_MAX : gone));
   }
   int want = firstRead ? XPDIR_SCAN_MAX : (newBars + 2);
   if(want < XPDIR_SCAN_MIN) want = XPDIR_SCAN_MIN;
   if(want > XPDIR_SCAN_MAX) want = XPDIR_SCAN_MAX;

   double fastArr[], slowArr[], runArr[], stateArr[];
   ArraySetAsSeries(fastArr, true);      // [0] = the bar that just closed
   ArraySetAsSeries(slowArr, true);
   const int gotFast = CopyBuffer(g_XPDirHandle[r], XPDIR_BUF_FAST, 1, want, fastArr);
   const int gotSlow = CopyBuffer(g_XPDirHandle[r], XPDIR_BUF_SLOW, 1, want, slowArr);
   if(gotFast < 1 || gotSlow < 1) { g_XPDirWhy[r] = "no_data"; return; }
   const int count = (gotFast < gotSlow) ? gotFast : gotSlow;

   if(CopyBuffer(g_XPDirHandle[r], XPDIR_BUF_RUNLEN, 1, 1, runArr) != 1) ArrayResize(runArr, 0);
   if(CopyBuffer(g_XPDirHandle[r], XPDIR_BUF_STATE,  1, 1, stateArr) != 1) ArrayResize(stateArr, 0);
   if(ArraySize(runArr) == 1 && !XPDir_CoreIsEmpty(runArr[0]))
      g_XPDirRunLen[r] = (int)MathRound(runArr[0]);   // logged, never voted on
   if(ArraySize(stateArr) == 1) g_XPDirState[r] = stateArr[0];

   const bool bar0Valid = !XPDir_CoreIsEmpty(fastArr[0]) && !XPDir_CoreIsEmpty(slowArr[0]);
   if(bar0Valid && !XPDir_ProbeBufferContract(r, fastArr[0], slowArr[0]))
   {
      g_XPDirWhy[r] = "buffer_contract";
      g_XPDirEnabled[r] = false;          // silenced: never vote on the wrong buffer
      return;
   }

   int advance = firstRead ? count : newBars;
   if(advance > count) advance = count;
   if(advance > 0)
      XPDir_AdvanceCross(fastArr, slowArr, advance,
                         g_XPDirSign[r], g_XPDirCrossDir[r],
                         g_XPDirCrossAge[r], g_XPDirCrossSep[r]);
   g_XPDirLastBarTime[r] = barTime;

   g_XPDirSepNow[r] = bar0Valid ? (fastArr[0] - slowArr[0]) : 0.0;
   const long age = (long)TimeCurrent() - (long)barTime;

   string why = "";
   int grade = XPDIR_GRADE_NONE;
   const int vote = XPDir_VoteFromCross(g_XPDirSepNow[r], bar0Valid,
                                        g_XPDirSign[r], g_XPDirCrossDir[r],
                                        g_XPDirCrossAge[r], g_XPDirCrossSep[r],
                                        age, g_XPDirIntervalS[r], g_XPDirMaxStaleBars,
                                        g_XPDirCrossMaxAge, g_XPDirEarlySepMult,
                                        grade, why);
   g_XPDirVote[r]  = vote;
   g_XPDirGrade[r] = grade;
   if(why == "stale") why = StringFormat("stale_%I64ds", age);
   g_XPDirWhy[r] = why;

   if(vote == 0) return;

   if(!g_XPDirReadyLogged[r])
   {
      g_XPDirReadyLogged[r] = true;
      PrintFormat("XPDIR RUNG_READY rung=%s symbol=%s bars=%d scan=%d vote=%s grade=%s "
                  "cross_dir=%d cross_age=%d cross_sep=%.6f sep_now=%.6f carried=%s runlen=%d",
                  g_XPDirTag[r], g_XPDirSymbol[r], Bars(g_XPDirSymbol[r], tf), count,
                  XPDir_VoteTag(r), XPDir_GradeName(grade), g_XPDirCrossDir[r],
                  g_XPDirCrossAge[r], g_XPDirCrossSep[r], g_XPDirSepNow[r],
                  XPDir_CarriedName(r), g_XPDirRunLen[r]);
   }
}

//+------------------------------------------------------------------+
//| The one decision                                                  |
//+------------------------------------------------------------------+
ENUM_XPDIR XPDir_Current()
{
   if(InpDirMode == DIR_OFF || !g_XPDirReady) return XPDIR_NONE;

   // cached per S1 closed-bar time; re-read once per server second as well,
   // because staleness is the one thing that changes between S1 bars.
   const datetime key = iTime(g_XPDirSymbol[XPDIR_IDX_S1], PERIOD_M1, 1);
   const datetime nowSec = TimeCurrent();
   if(g_XPDirCacheFilled && key == g_XPDirCacheKey && nowSec == g_XPDirCacheSecond)
      return g_XPDirCached;

   for(int r = 0; r < XPDIR_RUNGS; r++) XPDir_ReadRung(r);
   g_XPDirEvals++;

   int optional[];
   ArrayResize(optional, 0);
   for(int r = 1; r <= 5; r++)
   {
      if(!g_XPDirEnabled[r]) continue;            // absent/disabled is not a vote
      const int n = ArraySize(optional);
      ArrayResize(optional, n + 1);
      optional[n] = g_XPDirVote[r];
   }

   // S1 freshness does not delete S1's vote: it is a condition on the rules
   // that NEED C1 == X (R1, and R3 when S1RequiredAgainstParent). R2 is
   // untouched, and S1 still counts toward R3's child total either way.
   const bool s1Fresh = (g_XPDirGrade[XPDIR_IDX_S1] == XPDIR_GRADE_EARLY ||
                         g_XPDirGrade[XPDIR_IDX_S1] == XPDIR_GRADE_FRESH);

   int rule = 0;
   bool conflict = false;
   const int decided = XPDir_DecideFromVotes(g_XPDirVote[XPDIR_IDX_PARENT],
                                             g_XPDirVote[XPDIR_IDX_S1],
                                             s1Fresh,
                                             optional,
                                             g_XPDirMinWith,
                                             g_XPDirMinAgainst,
                                             InpDirS1RequiredAgainstParent,
                                             InpDirRequireFreshS1,
                                             rule, conflict);

   g_XPDirCached         = (decided > 0) ? XPDIR_BUY : ((decided < 0) ? XPDIR_SELL : XPDIR_NONE);
   g_XPDirCachedRule     = rule;
   g_XPDirCachedConflict = conflict;
   g_XPDirCacheKey       = key;
   g_XPDirCacheSecond    = nowSec;
   g_XPDirCacheFilled    = true;

   // The change key holds votes and GRADES but not the cross ages: an age ticks
   // up every bar and would print a DIR_STATE line every bar. A grade change
   // (EARLY -> FRESH -> STALE_STATE) is the part worth a line, and the line
   // itself carries the ages as of that moment.
   const string key = StringFormat("%s|%s|%s|%s|%s|%s|%s|%s|%s",
                                   XPDir_DirName(g_XPDirCached),
                                   rule > 0 ? "R" + IntegerToString(rule) : "-",
                                   XPDir_VoteTag(XPDIR_IDX_PARENT) + XPDir_GradeLetter(g_XPDirGrade[XPDIR_IDX_PARENT]),
                                   XPDir_VoteTag(0) + XPDir_GradeLetter(g_XPDirGrade[0]),
                                   XPDir_VoteTag(1) + XPDir_GradeLetter(g_XPDirGrade[1]),
                                   XPDir_VoteTag(2) + XPDir_GradeLetter(g_XPDirGrade[2]),
                                   XPDir_VoteTag(3) + XPDir_GradeLetter(g_XPDirGrade[3]),
                                   XPDir_VoteTag(4) + XPDir_GradeLetter(g_XPDirGrade[4]),
                                   XPDir_VoteTag(5) + XPDir_GradeLetter(g_XPDirGrade[5]));
   const string line = StringFormat("dir=%s rule=%s P=%s C1=%s C5=%s C10=%s C15=%s C30=%s C45=%s runlen1=%d",
                                    XPDir_DirName(g_XPDirCached),
                                    rule > 0 ? "R" + IntegerToString(rule) : "-",
                                    XPDir_RungTag(XPDIR_IDX_PARENT),
                                    XPDir_RungTag(0), XPDir_RungTag(1), XPDir_RungTag(2),
                                    XPDir_RungTag(3), XPDir_RungTag(4), XPDir_RungTag(5),
                                    g_XPDirRunLen[XPDIR_IDX_S1]);
   if(key != g_XPDirLastStateLine)
   {
      g_XPDirLastStateLine = key;
      g_XPDirStateLines++;
      PrintFormat("XPDIR DIR_STATE %s", line);
      if(conflict)
         PrintFormat("XPDIR DIR_CONFLICT both directions pass a rule - direction forced NONE. %s", line);
      XPDir_WriteCsv("DIR_STATE", "-", "-",
                     conflict ? "BLOCKED_CONFLICT"
                              : (g_XPDirCached == XPDIR_BUY ? "ARMED_BUY"
                                 : (g_XPDirCached == XPDIR_SELL ? "ARMED_SELL" : "ARMED_NONE")));
   }
   return g_XPDirCached;
}

//+------------------------------------------------------------------+
//| Funnel dump - the zero-result contingency instrument              |
//+------------------------------------------------------------------+
void XPDir_PrintFunnel()
{
   if(InpDirMode == DIR_OFF) return;
   g_XPDirFunnelDumps++;
   PrintFormat("XPDIR FUNNEL_DUMP #%d mode=%s ready=%d evaluations=%I64u state_lines=%I64u "
               "dir=%s indicator=%s parent=%s",
               g_XPDirFunnelDumps, XPDir_ModeName(), g_XPDirReady ? 1 : 0,
               g_XPDirEvals, g_XPDirStateLines, XPDir_DirName(g_XPDirCached),
               InpDirMapIndicator, _Symbol);
   for(int r = 0; r < XPDIR_RUNGS; r++)
   {
      const ENUM_TIMEFRAMES tf = (r == XPDIR_IDX_PARENT) ? InpDirParentTF : PERIOD_M1;
      PrintFormat("XPDIR FUNNEL rung=%s symbol=%s enabled=%d handle=%d bars=%d bar1_time=%s "
                  "vote=%s grade=%s cross_dir=%d cross_age=%d cross_sep=%.6f sep_now=%.6f "
                  "carried_sign=%d carried=%s map_state=%s runlen=%d why=%s",
                  g_XPDirTag[r], g_XPDirSymbol[r], g_XPDirEnabled[r] ? 1 : 0,
                  g_XPDirHandle[r], g_XPDirSymbol[r] == "" ? 0 : Bars(g_XPDirSymbol[r], tf),
                  TimeToString(iTime(g_XPDirSymbol[r], tf, 1), TIME_DATE | TIME_MINUTES | TIME_SECONDS),
                  XPDir_VoteTag(r), XPDir_GradeName(g_XPDirGrade[r]),
                  g_XPDirCrossDir[r], g_XPDirCrossAge[r], g_XPDirCrossSep[r], g_XPDirSepNow[r],
                  g_XPDirSign[r], XPDir_CarriedName(r),
                  XPDir_CoreIsEmpty(g_XPDirState[r]) ? "-" : DoubleToString(g_XPDirState[r], 0),
                  g_XPDirRunLen[r], g_XPDirWhy[r]);
   }
}

// Zero-result contingency, wired rather than merely available. A ladder that
// has produced no DIR_STATE line at all is a broken run until proven otherwise,
// so it says why - per rung, with the reason - instead of sitting silent. It
// stops on its own the moment the ladder starts deciding.
void XPDir_FunnelHeartbeat()
{
   if(InpDirMode == DIR_OFF) return;
   if(g_XPDirFunnelDumps >= XPDIR_FUNNEL_MAX_DUMPS)
   {
      if(g_XPDirFunnelDumps == XPDIR_FUNNEL_MAX_DUMPS)
      {
         g_XPDirFunnelDumps++;            // print this once, then go quiet
         PrintFormat("XPDIR FUNNEL_STOP after %d dumps - still nothing to report. "
                     "Read the last dump: it names the blocked rung and the reason.",
                     XPDIR_FUNNEL_MAX_DUMPS);
      }
      return;
   }

   const datetime now = TimeCurrent();
   // nothing decided yet -> every 30 s, starting immediately
   // deciding, but stuck on NONE -> every 300 s
   const int period = (g_XPDirStateLines == 0) ? 30 : 300;
   if(g_XPDirStateLines > 0 && g_XPDirCached != XPDIR_NONE) return;
   if(g_XPDirFunnelLastSec != 0 && (long)now - (long)g_XPDirFunnelLastSec < period) return;
   g_XPDirFunnelLastSec = now;

   XPDir_Current();                       // refresh the rungs before reporting them
   XPDir_PrintFunnel();
}

//+------------------------------------------------------------------+
//| Wiring helpers used inside ManageVirtualPendings                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| XPDIR_GATE0_CORE_BEGIN                                            |
//| The entry-path wiring. Gate 0's executed pre-check lifts this out |
//| and runs every mode x state combination against the literal 1.03  |
//| conditions, so "DIR_OFF is inert" is a result, not a claim.       |
//+------------------------------------------------------------------+
// DIR_LOCK: the ladder decides which virtual stop stays armed. Enforced on
// every tick and not only inside the InpModInterval refresh, so a direction
// change between refreshes cannot leave a live level on the wrong side.
void XPDir_ApplyArmingLock()
{
   if(InpDirMode != DIR_LOCK) return;
   const ENUM_XPDIR d = XPDir_Current();
   if(d == XPDIR_BUY)       g_VirtualSellStopPrice = 0.0;
   else if(d == XPDIR_SELL) g_VirtualBuyStopPrice  = 0.0;
   else { g_VirtualBuyStopPrice = 0.0; g_VirtualSellStopPrice = 0.0; }

   const int armed = (int)d;
   if(armed != g_XPDirLastArmed)
   {
      g_XPDirLastArmed = armed;
      XPDir_WriteCsv("DECISION", "-", "-",
                     d == XPDIR_BUY ? "ARMED_BUY" : (d == XPDIR_SELL ? "ARMED_SELL" : "ARMED_NONE"));
   }
}

// TRANSLATE: remember which level crossed, and log a blocked trigger.
void XPDir_NoteTrigger(const bool buyCrossing, const bool sellCrossing)
{
   if(InpDirMode != DIR_TRANSLATE) return;
   if(g_EntryHoldCandidate.active) return;   // the live candidate keeps its trigger side
   if(!buyCrossing && !sellCrossing) return;
   g_XPDirHoldTriggerIsBuy = buyCrossing;    // a simultaneous cross counts as BUY

   const ENUM_XPDIR d = XPDir_Current();
   if(d != XPDIR_NONE) return;
   const datetime nowSec = TimeCurrent();
   if(nowSec == g_XPDirLastBlockedSec) return;   // a still-crossed level fires every tick
   g_XPDirLastBlockedSec = nowSec;
   XPDir_WriteCsv("DECISION", buyCrossing ? "BUY" : "SELL", "NONE",
                  g_XPDirCachedConflict ? "BLOCKED_CONFLICT" : "BLOCKED_NONE");
}

// TRANSLATE: the candidate is keyed on the exec side, the trigger on the level
// that crossed. Drop it when that level is gone or the direction moved away.
void XPDir_ReviewHoldCandidate()
{
   if(!g_EntryHoldCandidate.active) return;
   const bool triggerGone = g_XPDirHoldTriggerIsBuy ? (g_VirtualBuyStopPrice  <= 0.0)
                                                    : (g_VirtualSellStopPrice <= 0.0);
   const ENUM_XPDIR want = XPDir_Current();
   const ENUM_XPDIR have = g_EntryHoldCandidate.isBuy ? XPDIR_BUY : XPDIR_SELL;
   if(!triggerGone && want == have) return;

   const string reason = triggerGone ? "trigger_level_gone" : "direction_changed";
   PrintFormat("XPDIR HOLD_DROPPED reason=%s trigger_side=%s exec_side=%s dir=%s",
               reason, g_XPDirHoldTriggerIsBuy ? "BUY" : "SELL",
               g_EntryHoldCandidate.isBuy ? "BUY" : "SELL", XPDir_DirName(want));
   XPDir_WriteCsv("HOLD_DROPPED", g_XPDirHoldTriggerIsBuy ? "BUY" : "SELL",
                  g_EntryHoldCandidate.isBuy ? "BUY" : "SELL",
                  reason == "direction_changed" ? "BLOCKED_NONE" : "ARMED_NONE");
   ResetEntryHoldCandidate();
}

// Does the native BUY (SELL) block run this tick?
//   DIR_OFF / DIR_LOCK : exactly the 1.03 condition.
//   DIR_TRANSLATE      : either crossing fires the trigger, the ladder picks
//                        the side that executes.
bool XPDir_BuyBlockRuns(const bool buyHoldActive, const bool buyCrossing, const bool sellCrossing)
{
   if(g_EntryHoldCandidate.active) return buyHoldActive;
   if(InpDirMode == DIR_TRANSLATE)
      return (buyCrossing || sellCrossing) && (XPDir_Current() == XPDIR_BUY);
   return buyCrossing;
}

bool XPDir_SellBlockRuns(const bool sellHoldActive, const bool buyCrossing, const bool sellCrossing)
{
   if(g_EntryHoldCandidate.active) return sellHoldActive;
   if(InpDirMode == DIR_TRANSLATE)
      return (buyCrossing || sellCrossing) && (XPDir_Current() == XPDIR_SELL);
   return sellCrossing;
}

// In TRANSLATE the level that crossed is not necessarily the exec side's
// level, so after a fill both levels go. Otherwise the crossed level stays
// crossed and re-fires on the next tick.
void XPDir_ClearTriggerLevels()
{
   if(InpDirMode != DIR_TRANSLATE) return;
   g_VirtualBuyStopPrice  = 0.0;
   g_VirtualSellStopPrice = 0.0;
}
//+------------------------------------------------------------------+
//| XPDIR_GATE0_CORE_END                                              |
//+------------------------------------------------------------------+

void XPDir_LogSent(const bool execIsBuy)
{
   if(InpDirMode == DIR_OFF) return;
   const string triggerSide = (InpDirMode == DIR_TRANSLATE)
                              ? (g_XPDirHoldTriggerIsBuy ? "BUY" : "SELL")
                              : (execIsBuy ? "BUY" : "SELL");
   const string execSide = execIsBuy ? "BUY" : "SELL";
   PrintFormat("XPDIR DECISION mode=%s dir=%s rule=%s trigger_side=%s exec_side=%s action=SENT "
               "translated=%d C1=%s P=%s",
               XPDir_ModeName(), XPDir_DirName(g_XPDirCached),
               g_XPDirCachedRule > 0 ? "R" + IntegerToString(g_XPDirCachedRule) : "-",
               triggerSide, execSide, (triggerSide != execSide) ? 1 : 0,
               XPDir_RungTag(XPDIR_IDX_S1), XPDir_RungTag(XPDIR_IDX_PARENT));
   XPDir_WriteCsv("DECISION", triggerSide, execSide, "SENT");
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
      
      if(!buyOpen && !(nettingAccount && sellOpen)) g_VirtualBuyStopPrice = ask + entryDist; 
      else g_VirtualBuyStopPrice = 0; 

      if(!sellOpen && !(nettingAccount && buyOpen)) g_VirtualSellStopPrice = bid - entryDist;
      else g_VirtualSellStopPrice = 0; 
      
      g_LastModTime = TimeCurrent();
   }

   // XPDIR (DIR_LOCK): the ladder disarms the side it does not want.
   XPDir_ApplyArmingLock();

   if(InpDirMode == DIR_TRANSLATE)
      XPDir_ReviewHoldCandidate();
   else if(g_EntryHoldCandidate.active &&
      ((g_EntryHoldCandidate.isBuy && g_VirtualBuyStopPrice <= 0.0) ||
       (!g_EntryHoldCandidate.isBuy && g_VirtualSellStopPrice <= 0.0)))
      ResetEntryHoldCandidate();

   // BUY TRIGGER
   const bool buyCrossing = (g_VirtualBuyStopPrice > 0 && ask >= g_VirtualBuyStopPrice);
   // XPDIR: sellCrossing hoisted out of the SELL TRIGGER block so DIR_TRANSLATE
   // sees both crossings before either side-specific block runs. In DIR_OFF and
   // DIR_LOCK neither block writes g_VirtualSellStopPrice or bid, so this is the
   // same value the SELL block computed in 1.03 (report: HOIST-1).
   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);
   XPDir_NoteTrigger(buyCrossing, sellCrossing);

   const bool buyHoldActive = g_EntryHoldCandidate.active && g_EntryHoldCandidate.isBuy;
   if(XPDir_BuyBlockRuns(buyHoldActive, buyCrossing, sellCrossing))
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

               if(tradeLots > 0 && trade.Buy(tradeLots, _Symbol, 0, 0, 0, "V_Breakout"))
               {
                  MarkCurrentBarEntered();
                  g_VirtualBuyStopPrice = 0;
                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
                  XPDir_LogSent(true);
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

   // SELL TRIGGER  (sellCrossing is computed above, with buyCrossing)
   const bool sellHoldActive = g_EntryHoldCandidate.active && !g_EntryHoldCandidate.isBuy;
   if(XPDir_SellBlockRuns(sellHoldActive, buyCrossing, sellCrossing))
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

               if(tradeLots > 0 && trade.Sell(tradeLots, _Symbol, 0, 0, 0, "V_Breakout"))
               {
                  MarkCurrentBarEntered();
                  g_VirtualSellStopPrice = 0;
                  XPDir_ClearTriggerLevels();   // XPDIR: TRANSLATE zeroes both
                  XPDir_LogSent(false);
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

   // XPDIR: one added line, last, so no existing dashboard line moves.
   if(InpDirMode == DIR_OFF)
      ObjectDelete(0, "Lbl_XPDir");
   else
   {
      const ENUM_XPDIR d = XPDir_Current();
      string dirTxt = StringFormat("DIR: %-4s %-2s P=%s/%s 1:%s/%s 5:%s/%s 10:%s/%s 15:%s 30:%s 45:%s",
                                   XPDir_DirName(d),
                                   g_XPDirCachedRule > 0 ? "R" + IntegerToString(g_XPDirCachedRule) : "- ",
                                   XPDir_VoteTag(XPDIR_IDX_PARENT), XPDir_GradeLetter(g_XPDirGrade[XPDIR_IDX_PARENT]),
                                   XPDir_VoteTag(0), XPDir_GradeLetter(g_XPDirGrade[0]),
                                   XPDir_VoteTag(1), XPDir_GradeLetter(g_XPDirGrade[1]),
                                   XPDir_VoteTag(2), XPDir_GradeLetter(g_XPDirGrade[2]),
                                   XPDir_VoteTag(3), XPDir_VoteTag(4), XPDir_VoteTag(5));
      color dirClr = (d == XPDIR_BUY) ? InpDashColor2
                     : ((d == XPDIR_SELL) ? InpDashColor3 : clrGray);
      CreateLabel("Lbl_XPDir", InpDashX, y, dirTxt, dirClr);
      y += lineHeight;
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
