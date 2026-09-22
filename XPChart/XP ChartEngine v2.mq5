//+------------------------------------------------------------------+
//|                                            XP ChartEngine v2.mq5 |
//|  Lossless CopyTicks cursor, tick.time_msc bar anchoring, spec     |
//|  sync, restart-safe, heartbeat.  v1 stays untouched.              |
//+------------------------------------------------------------------+
#property service
#property copyright   "xpworx"
#property link        "ghostmaster"
#property description "XP ChartEngine v2: lossless CopyTicks cursor, tick-anchored bars, spec sync, restart-safe, heartbeat"
#define  Version      "2.00"
#property version     Version
#property strict

//--- F14: enum unchanged from v1
enum ENUM_CUSTOM_SECONDS
{
   S1=1,       // 1 Second
   S2=2,       // 2 Seconds
   S5=5,       // 5 Seconds
   S10=10,     // 10 Seconds
   S30=30,     // 30 Seconds
   S_Custom=0  // Manual Input
};
enum ENUM_XP_SPREAD_MODE
{
   XP_SPREAD_LAST=0,   // LAST  (spread of the last tick in the bar)
   XP_SPREAD_MAX=1,    // MAX   (max spread over every tick in the bar)
   XP_SPREAD_MIN=2     // MIN   (min spread over every tick in the bar)
};
enum ENUM_XP_PRICE_BASIS
{
   XP_BASIS_BID=0,     // BID   (matches MT5 native bars and the parent chart)
   XP_BASIS_ASK=1,     // ASK
   XP_BASIS_MID=2      // MID   ((bid+ask)/2, not rounded to digits)
};
enum ENUM_XP_TIME_AXIS
{
   XP_AXIS_REAL=0,     // REAL      (bar time = real second, v1 behaviour)
   XP_AXIS_SYNTHETIC=1 // SYNTHETIC (one interval -> one chart minute, mapping CSV)
};

//--- inputs ---------------------------------------------------------
input string               BaseSymbol           = "XAUUSD";        // F14 default
input ENUM_CUSTOM_SECONDS  Timeframe            = S1;
input int                  ManualSeconds        = 15;
input string               BaseSymbolOverride   = "";              // F6: "" = auto-detect (deterministic)
input string               CustomNameSuffix     = "";              // "" = <parent>_S<n> (F14). Use when changing TimeAxis on an existing name
input ENUM_XP_PRICE_BASIS  PriceBasis           = XP_BASIS_BID;    // F5
input ENUM_XP_SPREAD_MODE  SpreadMode           = XP_SPREAD_MAX;   // F4 (points of the PARENT's SYMBOL_POINT)
input ENUM_XP_TIME_AXIS    TimeAxis             = XP_AXIS_REAL;    // F10 GATE1_DEFAULT: re-pin after XP_AxisCheck receipt
input datetime             AxisBase             = 0;               // F10 SYNTHETIC chart-time origin (0 = auto, persisted)
input datetime             AxisOrigin           = 0;               // F10 SYNTHETIC real-time origin  (0 = auto, persisted)
input bool                 WriteEmptyBars       = false;           // F10 flat bars for interval slots with no tick
input int                  MaxEmptyBarsPerGap   = 600;             // cap per gap (weekend protection)
input bool                 PushTicks            = true;            // F11 (diagnostic off-switch for the funnel)
input int                  ConsecutiveFailLimit = 20;              // F8
input int                  PollSleepMs          = 50;              // F1 keep 50; floor 10
input int                  CopyTicksCount       = 0;               // F1 count arg: 0 = all ticks since cursor (verify in reference); >0 = bounded
input int                  HeartbeatSeconds     = 60;              // F12
input string               OutputDir            = "XPChart";       // R6: under MQL5\Files
input int                  LockStaleSeconds     = 180;             // F13 stale-lock takeover
input int                  FunnelPolls          = 20;              // verbose CopyTicks prints for the first N polls

//--- resolved at start ----------------------------------------------
string   actual_symbol = "";
string   custom_name   = "";
int      interval_s    = 1;
long     interval_ms   = 1000;
double   parent_point  = 0.0;
int      parent_digits = 0;
bool     symbol_created = false;

//--- tick cursor (F1) -------------------------------------------------
long     cursor_msc  = 0;
int      cursor_seen = 0;

//--- current bar (F2/F3/F4/F5) -----------------------------------------
bool     bar_active = false;
long     bar_slot   = 0;
double   b_open = 0.0, b_high = 0.0, b_low = 0.0, b_close = 0.0;
long     b_ticks = 0, b_realvol = 0;
int      b_spread = 0;
double   last_close  = 0.0;
int      last_spread = 0;

//--- synthetic axis (F10) ---------------------------------------------
long     axis_base   = 0;   // chart-time origin, seconds
long     origin_slot = 0;   // real slot index mapped to axis_base
string   gv_axis_base = "", gv_axis_origin = "", gv_lock = "";
int      map_handle = INVALID_HANDLE;

//--- pending output (F8 retry buffers) --------------------------------
MqlRates pend_rates[];
long     pend_slots[];
MqlTick  pend_ticks[];
#define  MAX_PEND_RATES 5000
#define  MAX_PEND_TICKS 20000

//--- counters (F12) ---------------------------------------------------
long     ticks_captured = 0, ticks_pushed = 0, bars_written = 0, bars_opened = 0, empty_slots = 0, empty_bars_written = 0;
long     copyticks_errors = 0, write_errors = 0, anomalies = 0, bad_ticks = 0, dropped_ticks = 0, dropped_bars = 0;
long     rates_updates = 0, polls = 0, blocked_events = 0, suppressed_prints = 0, file_errors = 0, partial_tick_adds = 0;
long     bars_tickvol_gt1 = 0, written_slot_max = -1, seeded_bars = 0;
int      max_tps = 0, tps_count = 0, max_ticks_per_poll = 0, consecutive_fail = 0;
long     tps_second = -1;
int      spread_min_seen = -1, spread_max_seen = -1;
bool     volume_seen = false;
ulong    last_tick_local_ms = 0, last_err_print_ms = 0, last_hb_ms = 0, start_local_ms = 0;
int      spec_pass = 0, spec_fail = 0, spec_not_settable = 0;

//+------------------------------------------------------------------+
//| helpers                                                          |
//+------------------------------------------------------------------+
string Ts(datetime t)
{
   return TimeToString(t, TIME_DATE | TIME_MINUTES | TIME_SECONDS);
}
//+------------------------------------------------------------------+
string ErrName(int code)
{
   switch(code)
   {
      case 0:    return "OK";
      case 32:   return "NOT_AN_MQL5_CODE(Windows ERROR_SHARING_VIOLATION=32? custom history file held by another process - unverified)";
      case 4301: return "ERR_MARKET_UNKNOWN_SYMBOL";
      case 4302: return "ERR_MARKET_NOT_SELECTED";
      case 4303: return "ERR_MARKET_WRONG_PROPERTY";
      case 4401: return "ERR_HISTORY_NOT_FOUND";
      case 4403: return "ERR_HISTORY_TIMEOUT";
      case 5004: return "ERR_CANNOT_OPEN_FILE";
      case 5300: return "ERR_CUSTOM_SYMBOL_WRONG_NAME";
      case 5301: return "ERR_CUSTOM_SYMBOL_NAME_LONG";
      case 5302: return "ERR_CUSTOM_SYMBOL_PATH_LONG";
      case 5303: return "ERR_CUSTOM_SYMBOL_EXIST";
      case 5304: return "ERR_CUSTOM_SYMBOL_ERROR";
      case 5305: return "ERR_CUSTOM_SYMBOL_SELECTED";
      case 5306: return "ERR_CUSTOM_SYMBOL_PROPERTY_WRONG";
      case 5307: return "ERR_CUSTOM_SYMBOL_PARAMETER_ERROR";
      case 5308: return "ERR_CUSTOM_SYMBOL_PARAMETER_LONG";
      case 5309: return "ERR_CUSTOM_TICKS_WRONG_ORDER";
   }
   return "code_" + (string)code;
}
//+------------------------------------------------------------------+
void ErrPrint(string msg)   // F8: rate-limited, <= 1 print per second
{
   ulong now = GetTickCount64();
   if(last_err_print_ms == 0 || now - last_err_print_ms >= 1000)
   {
      Print("XP ChartEngine v2 ERROR: ", msg, (suppressed_prints > 0) ? " (+" + (string)suppressed_prints + " suppressed)" : "");
      last_err_print_ms = now;
      suppressed_prints = 0;
   }
   else
      suppressed_prints++;
}
//+------------------------------------------------------------------+
void SleepInterruptible(int ms)
{
   int waited = 0;
   while(waited < ms && !IsStopped())
   {
      Sleep(100);
      waited += 100;
   }
}
//+------------------------------------------------------------------+
string SanitizeFileName(string s)
{
   string bad = "\\/:*?\"<>|";
   string out = s;
   for(int i = 0; i < StringLen(bad); i++)
   {
      string ch = StringSubstr(bad, i, 1);
      StringReplace(out, ch, "_");
   }
   return out;
}
//+------------------------------------------------------------------+
void AppendLine(string fname, string header, string line)
{
   string path = OutputDir + "\\" + fname;
   bool is_new = !FileIsExist(path);
   int h = FileOpen(path, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      file_errors++;
      ErrPrint("FileOpen failed: " + path + " err=" + (string)GetLastError());
      return;
   }
   FileSeek(h, 0, SEEK_END);
   if(is_new && header != "") FileWrite(h, header);
   FileWrite(h, line);
   FileClose(h);
}
//+------------------------------------------------------------------+
string HeartbeatFile()
{
   return "heartbeat_" + SanitizeFileName(custom_name) + ".csv";
}
string MapFile()
{
   return "axismap_" + SanitizeFileName(custom_name) + ".csv";
}
//+------------------------------------------------------------------+
//| F6 deterministic base-symbol resolution                          |
//+------------------------------------------------------------------+
bool ResolveBaseSymbol()
{
   if(BaseSymbolOverride != "")
   {
      bool is_custom = false;
      bool exists = SymbolExist(BaseSymbolOverride, is_custom);
      Print("F6 BaseSymbolOverride='", BaseSymbolOverride, "' exists=", exists, " is_custom=", is_custom);
      if(!exists || is_custom)
      {
         Print("BLOCKED_NO_BASE_SYMBOL: override '", BaseSymbolOverride, "' is ", (exists ? "a custom symbol" : "unknown"));
         return false;
      }
      actual_symbol = BaseSymbolOverride;
      return true;
   }

   string names[];
   int    exact[];
   int    selected[];
   long   lastms[];
   int    n = 0;
   int total = SymbolsTotal(false);
   for(int i = 0; i < total; i++)
   {
      string sym = SymbolName(i, false);
      if(SymbolInfoInteger(sym, SYMBOL_CUSTOM) != 0) continue;                 // never a custom symbol (D6 self-match)
      bool is_exact = (sym == BaseSymbol);
      if(!is_exact && StringFind(sym, BaseSymbol) != 0) continue;              // must START with BaseSymbol
      MqlTick t;
      long ms = 0;
      if(SymbolInfoTick(sym, t)) ms = t.time_msc;
      ArrayResize(names, n + 1);
      ArrayResize(exact, n + 1);
      ArrayResize(selected, n + 1);
      ArrayResize(lastms, n + 1);
      names[n]    = sym;
      exact[n]    = is_exact ? 1 : 0;
      selected[n] = (SymbolInfoInteger(sym, SYMBOL_SELECT) != 0) ? 1 : 0;
      lastms[n]   = ms;
      n++;
   }
   Print("F6 base resolution for '", BaseSymbol, "': ", n, " candidate(s) among ", total, " symbols");
   if(n == 0)
   {
      Print("BLOCKED_NO_BASE_SYMBOL: no non-custom symbol equals or starts with '", BaseSymbol, "'");
      return false;
   }
   // rank: exact > selected > most recent tick > name (stable, deterministic)
   for(int a = 0; a < n; a++)
      for(int b = a + 1; b < n; b++)
      {
         bool swap = false;
         if(exact[b] != exact[a])            swap = (exact[b] > exact[a]);
         else if(selected[b] != selected[a]) swap = (selected[b] > selected[a]);
         else if(lastms[b] != lastms[a])     swap = (lastms[b] > lastms[a]);
         else                                swap = (StringCompare(names[b], names[a]) < 0);
         if(swap)
         {
            string ts = names[a]; names[a] = names[b]; names[b] = ts;
            int ti = exact[a]; exact[a] = exact[b]; exact[b] = ti;
            ti = selected[a]; selected[a] = selected[b]; selected[b] = ti;
            long tl = lastms[a]; lastms[a] = lastms[b]; lastms[b] = tl;
         }
      }
   for(int i = 0; i < n; i++)
      Print("F6 candidate rank=", i + 1, " name=", names[i], " exact=", exact[i], " selected=", selected[i],
            " last_tick_msc=", lastms[i], (lastms[i] > 0) ? " (" + Ts((datetime)(lastms[i] / 1000)) + ")" : "");
   actual_symbol = names[0];
   return true;
}
//+------------------------------------------------------------------+
//| F13 one instance per custom_name (GlobalVariable lock)           |
//+------------------------------------------------------------------+
bool AcquireLock()
{
   double now = (double)(long)TimeLocal();
   if(!GlobalVariableCheck(gv_lock))
   {
      if(!GlobalVariableTemp(gv_lock))
      {
         Print("F13 GlobalVariableTemp failed err=", GetLastError(), " - falling back to a persistent variable");
         if(GlobalVariableSet(gv_lock, 0.0) == 0)
         {
            Print("BLOCKED_DUPLICATE_INSTANCE: cannot create lock variable '", gv_lock, "' err=", GetLastError());
            return false;
         }
      }
      if(GlobalVariableSetOnCondition(gv_lock, now, 0.0)) return true;
   }
   double v = GlobalVariableGet(gv_lock);
   if(now - v > (double)LockStaleSeconds)
   {
      if(GlobalVariableSetOnCondition(gv_lock, now, v))
      {
         Print("F13 stale lock (age ", (long)(now - v), " s) taken over: ", gv_lock);
         return true;
      }
   }
   Print("BLOCKED_DUPLICATE_INSTANCE: lock '", gv_lock, "' held, last heartbeat ", (long)(now - v), " s ago (stale after ", LockStaleSeconds, " s)");
   return false;
}
void RefreshLock()
{
   if(GlobalVariableSet(gv_lock, (double)(long)TimeLocal()) == 0)
      ErrPrint("F13 lock refresh failed err=" + (string)GetLastError());
}
void ReleaseLock()
{
   if(!GlobalVariableDel(gv_lock))
      Print("F13 lock release failed err=", GetLastError());
}
//+------------------------------------------------------------------+
//| custom symbol create / reuse                                     |
//+------------------------------------------------------------------+
bool EnsureCustomSymbol()
{
   bool is_custom = false;
   bool exists = SymbolExist(custom_name, is_custom);
   if(exists && !is_custom)
   {
      Print("BLOCKED_CUSTOM_CREATE: '", custom_name, "' exists as a BROKER symbol - refusing to write into it");
      return false;
   }
   if(!exists)
   {
      ResetLastError();
      if(!CustomSymbolCreate(custom_name, "Custom\\XPChart", actual_symbol))
      {
         int err = GetLastError();
         if(err != 5303)
         {
            Print("BLOCKED_CUSTOM_CREATE: CustomSymbolCreate('", custom_name, "','Custom\\XPChart','", actual_symbol, "') failed err=", err, " ", ErrName(err));
            return false;
         }
         Print("custom symbol reported as existing during create (err 5303) - reusing");
      }
      else
      {
         symbol_created = true;
         Print("custom symbol CREATED: ", custom_name, " path=Custom\\XPChart origin=", actual_symbol);
      }
   }
   else
      Print("custom symbol REUSED: ", custom_name, " path=", SymbolInfoString(custom_name, SYMBOL_PATH));

   ResetLastError();
   if(!SymbolSelect(custom_name, true))
   {
      int err = GetLastError();
      Print("BLOCKED_CUSTOM_SELECT: SymbolSelect('", custom_name, "') failed err=", err, " ", ErrName(err), " (CustomTicksAdd needs the symbol in Market Watch)");
      return false;
   }
   if(SymbolInfoInteger(custom_name, SYMBOL_CUSTOM) == 0)
   {
      Print("BLOCKED_CUSTOM_CREATE: '", custom_name, "' is not flagged SYMBOL_CUSTOM after select");
      return false;
   }
   return true;
}
//+------------------------------------------------------------------+
//| F7 spec sync: set from parent, read both back, PASS/FAIL table   |
//+------------------------------------------------------------------+
void SpecRow(string name, string pv, string cv, string verdict)
{
   Print(StringFormat("F7 SPEC %-30s parent=%-22s custom=%-22s %s", name, pv, cv, verdict));
   if(StringFind(verdict, "PASS") == 0) spec_pass++;
   else if(StringFind(verdict, "NOT_SETTABLE") == 0) spec_not_settable++;
   else spec_fail++;
}
void SyncInt(ENUM_SYMBOL_INFO_INTEGER prop, string name)
{
   long pv = SymbolInfoInteger(actual_symbol, prop);
   ResetLastError();
   bool ok = CustomSymbolSetInteger(custom_name, prop, pv);
   int err = GetLastError();
   long cv = SymbolInfoInteger(custom_name, prop);
   string v;
   if(ok && cv == pv)          v = "PASS";
   else if(!ok && err == 5306) v = "NOT_SETTABLE(err 5306)";
   else                        v = "FAIL(set=" + (string)ok + " err=" + (string)err + " " + ErrName(err) + ")";
   SpecRow(name, (string)pv, (string)cv, v);
}
void SyncDbl(ENUM_SYMBOL_INFO_DOUBLE prop, string name)
{
   double pv = SymbolInfoDouble(actual_symbol, prop);
   ResetLastError();
   bool ok = CustomSymbolSetDouble(custom_name, prop, pv);
   int err = GetLastError();
   double cv = SymbolInfoDouble(custom_name, prop);
   string v;
   if(ok && DoubleToString(cv, 8) == DoubleToString(pv, 8)) v = "PASS";
   else if(!ok && err == 5306)                              v = "NOT_SETTABLE(err 5306)";
   else                                                     v = "FAIL(set=" + (string)ok + " err=" + (string)err + " " + ErrName(err) + ")";
   SpecRow(name, DoubleToString(pv, 8), DoubleToString(cv, 8), v);
}
void SyncStr(ENUM_SYMBOL_INFO_STRING prop, string name)
{
   string pv = SymbolInfoString(actual_symbol, prop);
   ResetLastError();
   bool ok = CustomSymbolSetString(custom_name, prop, pv);
   int err = GetLastError();
   string cv = SymbolInfoString(custom_name, prop);
   string v;
   if(ok && cv == pv)          v = "PASS";
   else if(!ok && err == 5306) v = "NOT_SETTABLE(err 5306)";
   else                        v = "FAIL(set=" + (string)ok + " err=" + (string)err + " " + ErrName(err) + ")";
   SpecRow(name, "'" + pv + "'", "'" + cv + "'", v);
}
void InfoInt(ENUM_SYMBOL_INFO_INTEGER prop, string name)   // read-only / derived: shown, never set
{
   SpecRow(name, (string)SymbolInfoInteger(actual_symbol, prop), (string)SymbolInfoInteger(custom_name, prop), "NOT_SETTABLE(derived/dynamic, parent shown)");
}
void InfoDbl(ENUM_SYMBOL_INFO_DOUBLE prop, string name)
{
   SpecRow(name, DoubleToString(SymbolInfoDouble(actual_symbol, prop), 8), DoubleToString(SymbolInfoDouble(custom_name, prop), 8), "NOT_SETTABLE(derived/dynamic, parent shown)");
}
void SyncSpecs()
{
   Print("F7 SPEC SYNC start: ", custom_name, " <- ", actual_symbol, " (", symbol_created ? "create path" : "reuse path", ")");
   SyncInt(SYMBOL_DIGITS,              "SYMBOL_DIGITS");
   InfoDbl(SYMBOL_POINT,               "SYMBOL_POINT");
   SyncDbl(SYMBOL_TRADE_TICK_SIZE,     "SYMBOL_TRADE_TICK_SIZE");
   SyncDbl(SYMBOL_TRADE_TICK_VALUE,    "SYMBOL_TRADE_TICK_VALUE");
   SyncDbl(SYMBOL_TRADE_TICK_VALUE_PROFIT, "SYMBOL_TRADE_TICK_VALUE_PROFIT");
   SyncDbl(SYMBOL_TRADE_TICK_VALUE_LOSS,   "SYMBOL_TRADE_TICK_VALUE_LOSS");
   SyncDbl(SYMBOL_TRADE_CONTRACT_SIZE, "SYMBOL_TRADE_CONTRACT_SIZE");
   SyncDbl(SYMBOL_VOLUME_MIN,          "SYMBOL_VOLUME_MIN");
   SyncDbl(SYMBOL_VOLUME_MAX,          "SYMBOL_VOLUME_MAX");
   SyncDbl(SYMBOL_VOLUME_STEP,         "SYMBOL_VOLUME_STEP");
   SyncDbl(SYMBOL_VOLUME_LIMIT,        "SYMBOL_VOLUME_LIMIT");
   SyncInt(SYMBOL_TRADE_STOPS_LEVEL,   "SYMBOL_TRADE_STOPS_LEVEL");
   SyncInt(SYMBOL_TRADE_FREEZE_LEVEL,  "SYMBOL_TRADE_FREEZE_LEVEL");
   SyncStr(SYMBOL_CURRENCY_BASE,       "SYMBOL_CURRENCY_BASE");
   SyncStr(SYMBOL_CURRENCY_PROFIT,     "SYMBOL_CURRENCY_PROFIT");
   SyncStr(SYMBOL_CURRENCY_MARGIN,     "SYMBOL_CURRENCY_MARGIN");
   SyncInt(SYMBOL_TRADE_MODE,          "SYMBOL_TRADE_MODE");
   SyncInt(SYMBOL_TRADE_CALC_MODE,     "SYMBOL_TRADE_CALC_MODE");
   SyncInt(SYMBOL_TRADE_EXEMODE,       "SYMBOL_TRADE_EXEMODE");
   SyncInt(SYMBOL_FILLING_MODE,        "SYMBOL_FILLING_MODE");
   SyncInt(SYMBOL_ORDER_MODE,          "SYMBOL_ORDER_MODE");
   SyncInt(SYMBOL_ORDER_GTC_MODE,      "SYMBOL_ORDER_GTC_MODE");
   SyncInt(SYMBOL_EXPIRATION_MODE,     "SYMBOL_EXPIRATION_MODE");
   SyncInt(SYMBOL_CHART_MODE,          "SYMBOL_CHART_MODE");
   SyncInt(SYMBOL_SPREAD_FLOAT,        "SYMBOL_SPREAD_FLOAT");
   SyncInt(SYMBOL_SWAP_MODE,           "SYMBOL_SWAP_MODE");
   SyncDbl(SYMBOL_SWAP_LONG,           "SYMBOL_SWAP_LONG");
   SyncDbl(SYMBOL_SWAP_SHORT,          "SYMBOL_SWAP_SHORT");
   SyncInt(SYMBOL_SWAP_ROLLOVER3DAYS,  "SYMBOL_SWAP_ROLLOVER3DAYS");
   SyncDbl(SYMBOL_MARGIN_INITIAL,      "SYMBOL_MARGIN_INITIAL");
   SyncDbl(SYMBOL_MARGIN_MAINTENANCE,  "SYMBOL_MARGIN_MAINTENANCE");
   SyncStr(SYMBOL_DESCRIPTION,         "SYMBOL_DESCRIPTION");
   SyncStr(SYMBOL_ISIN,                "SYMBOL_ISIN");
   InfoInt(SYMBOL_SPREAD,              "SYMBOL_SPREAD");
   InfoInt(SYMBOL_CUSTOM,              "SYMBOL_CUSTOM");
   InfoInt(SYMBOL_SELECT,              "SYMBOL_SELECT");
   Print("F7 SPEC SYNC done: PASS=", spec_pass, " FAIL=", spec_fail, " NOT_SETTABLE=", spec_not_settable,
         " (verdicts come from the runtime set+readback; a 5306 means the terminal refuses the property on custom symbols)");
}
//+------------------------------------------------------------------+
//| F10 synthetic axis mapping                                       |
//+------------------------------------------------------------------+
datetime SlotChartTime(long slot)
{
   if(TimeAxis == XP_AXIS_SYNTHETIC) return (datetime)(axis_base + (slot - origin_slot) * 60);
   return (datetime)(slot * interval_s);
}
long TickChartMsc(long real_msc, long slot)
{
   if(TimeAxis == XP_AXIS_SYNTHETIC)
   {
      long off = real_msc - slot * interval_ms;                          // 0 .. interval_ms-1, order preserved
      return (axis_base + (slot - origin_slot) * 60) * 1000 + (off * 60000) / interval_ms;
   }
   return real_msc;
}
bool ReadAxisFromMap(long &ab, long &ao)
{
   string path = OutputDir + "\\" + MapFile();
   if(!FileIsExist(path)) return false;
   int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE) return false;
   long fab = 0, fao = 0;
   bool found = false;
   while(!FileIsEnding(h))
   {
      string line = FileReadString(h);
      if(StringFind(line, "# xp_axis_base=") != 0) continue;
      string parts[];
      int np = StringSplit(line, ';', parts);
      long tab = 0, tao = 0;
      for(int i = 0; i < np; i++)
      {
         string kv[];
         if(StringSplit(parts[i], '=', kv) != 2) continue;
         string k = kv[0];
         StringReplace(k, "# ", "");
         if(k == "xp_axis_base")   tab = StringToInteger(kv[1]);
         if(k == "xp_axis_origin") tao = StringToInteger(kv[1]);
      }
      if(tab > 0 && tao > 0) { fab = tab; fao = tao; found = true; }   // keep the LAST header (latest session)
   }
   FileClose(h);
   if(found) { ab = fab; ao = fao; }
   return found;
}
void WriteMapRow(long slot, bool empty)
{
   if(TimeAxis != XP_AXIS_SYNTHETIC || map_handle == INVALID_HANDLE) return;
   datetime ct = SlotChartTime(slot);
   FileWrite(map_handle, (string)(slot * interval_ms) + ";" + (string)(long)ct + ";" + Ts(ct) + ";" + (empty ? "1" : "0"));
   FileFlush(map_handle);
}
bool LoadAxis(long start_msc)
{
   if(TimeAxis != XP_AXIS_SYNTHETIC)
   {
      Print("F10 axis=REAL (bar time = real second; identity mapping, no mapping CSV)");
      return true;
   }
   long ab = (long)AxisBase, ao = (long)AxisOrigin;
   string src = "input";
   if((ab == 0) != (ao == 0))
      Print("F10 WARNING: only one of AxisBase/AxisOrigin given - both are needed, falling back to persisted/auto values");
   if(ab == 0 || ao == 0)
   {
      if(GlobalVariableCheck(gv_axis_base) && GlobalVariableCheck(gv_axis_origin))
      {
         ab = (long)GlobalVariableGet(gv_axis_base);
         ao = (long)GlobalVariableGet(gv_axis_origin);
         src = "globalvariable";
      }
      else if(ReadAxisFromMap(ab, ao))
         src = "mapping_csv";
      else
      {
         ao = (start_msc / interval_ms) * interval_s;                  // real slot start of the first tick
         ab = (((long)TimeCurrent()) / 60 + 2) * 60;                  // chart origin strictly after all real-time data
         src = "fresh";
      }
   }
   if(ab % 60 != 0 || ao % interval_s != 0 || ab <= 0 || ao <= 0)
   {
      Print("BLOCKED_AXIS: invalid axis values axis_base=", ab, " (must be minute-aligned) axis_origin=", ao, " (must be a multiple of ", interval_s, ")");
      return false;
   }
   axis_base   = ab;
   origin_slot = ao / interval_s;
   if(GlobalVariableSet(gv_axis_base, (double)ab) == 0 || GlobalVariableSet(gv_axis_origin, (double)ao) == 0)
      Print("F10 WARNING: could not persist axis GlobalVariables err=", GetLastError());
   Print("F10 axis=SYNTHETIC source=", src, " axis_base=", Ts((datetime)ab), " (", ab, ") axis_origin=", Ts((datetime)ao),
         " (", ao, ") origin_slot=", origin_slot, " chart_minutes_per_real_second=", 60.0 / interval_s);
   if(src == "fresh")
   {
      MqlRates lastbar[];
      if(CopyRates(custom_name, PERIOD_M1, 0, 1, lastbar) == 1 && (long)lastbar[0].time > ab)
         Print("F10 WARNING: existing history of ", custom_name, " ends at ", Ts(lastbar[0].time), " which is AFTER the fresh axis_base ",
               Ts((datetime)ab), " - CustomTicksAdd will reject out-of-order ticks. Use CustomNameSuffix or supply AxisBase/AxisOrigin from the mapping CSV.");
   }
   FolderCreate(OutputDir);
   string path = OutputDir + "\\" + MapFile();
   map_handle = FileOpen(path, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(map_handle == INVALID_HANDLE)
   {
      file_errors++;
      Print("F10 WARNING: mapping CSV not writable: ", path, " err=", GetLastError(), " (engine continues; back-conversion needs the GlobalVariables)");
   }
   else
   {
      FileSeek(map_handle, 0, SEEK_END);
      FileWrite(map_handle, "# xp_axis_base=" + (string)ab + ";xp_axis_origin=" + (string)ao + ";interval_s=" + (string)interval_s +
                            ";custom=" + custom_name + ";parent=" + actual_symbol + ";session_local=" + Ts(TimeLocal()));
      FileWrite(map_handle, "real_start_msc;chart_time;chart_time_str;empty");
      FileFlush(map_handle);
   }
   return true;
}
//+------------------------------------------------------------------+
//| bar building (F2..F5)                                            |
//+------------------------------------------------------------------+
double TickPrice(const MqlTick &t)
{
   switch(PriceBasis)
   {
      case XP_BASIS_ASK: return t.ask;
      case XP_BASIS_MID: return (t.bid + t.ask) * 0.5;
      default:           break;
   }
   return t.bid;
}
int SpreadPoints(const MqlTick &t)
{
   if(parent_point <= 0.0 || t.bid <= 0.0 || t.ask <= 0.0) return 0;
   return (int)MathRound((t.ask - t.bid) / parent_point);
}
void AppendRate(const MqlRates &r, long slot)
{
   int n = ArraySize(pend_rates);
   if(n >= MAX_PEND_RATES)
   {
      int drop = n / 2;
      ArrayRemove(pend_rates, 0, drop);
      ArrayRemove(pend_slots, 0, drop);
      dropped_bars += drop;
      ErrPrint("pending bar buffer full - dropped oldest " + (string)drop + " bars");
      n = ArraySize(pend_rates);
   }
   ArrayResize(pend_rates, n + 1);
   ArrayResize(pend_slots, n + 1);
   pend_rates[n] = r;
   pend_slots[n] = slot;
}
void AppendTick(const MqlTick &t)
{
   int n = ArraySize(pend_ticks);
   if(n >= MAX_PEND_TICKS)
   {
      int drop = n / 2;
      ArrayRemove(pend_ticks, 0, drop);
      dropped_ticks += drop;
      ErrPrint("pending tick buffer full - dropped oldest " + (string)drop + " ticks");
      n = ArraySize(pend_ticks);
   }
   ArrayResize(pend_ticks, n + 1);
   pend_ticks[n] = t;
}
void CurrentBar(MqlRates &r)
{
   r.time        = SlotChartTime(bar_slot);
   r.open        = b_open;
   r.high        = b_high;
   r.low         = b_low;
   r.close       = b_close;
   r.tick_volume = b_ticks;
   r.spread      = b_spread;
   r.real_volume = b_realvol;
}
void OpenBar(long slot, double p, const MqlTick &t)
{
   bar_active = true;
   bar_slot   = slot;
   b_open = p; b_high = p; b_low = p; b_close = p;
   b_ticks = 0; b_realvol = 0;
   b_spread = SpreadPoints(t);
   bars_opened++;
   WriteMapRow(slot, false);
}
void CloseBar()
{
   if(!bar_active) return;
   MqlRates r;
   CurrentBar(r);
   AppendRate(r, bar_slot);
   if(b_ticks > 1) bars_tickvol_gt1++;
   last_close  = b_close;
   last_spread = b_spread;
   bar_active  = false;
}
void WriteGap(long prev_slot, long gap)
{
   long n = (gap < (long)MaxEmptyBarsPerGap) ? gap : (long)MaxEmptyBarsPerGap;
   if(n < gap) ErrPrint("empty-bar gap of " + (string)gap + " slots truncated to " + (string)n + " (MaxEmptyBarsPerGap)");
   for(long k = 1; k <= n; k++)
   {
      MqlRates r;
      r.time        = SlotChartTime(prev_slot + k);
      r.open        = last_close;
      r.high        = last_close;
      r.low         = last_close;
      r.close       = last_close;
      r.tick_volume = 0;
      r.spread      = last_spread;
      r.real_volume = 0;
      AppendRate(r, prev_slot + k);
      empty_bars_written++;
      WriteMapRow(prev_slot + k, true);
   }
}
void ProcessTick(const MqlTick &t)
{
   double p = TickPrice(t);
   if(p <= 0.0)
   {
      bad_ticks++;
      return;
   }
   long slot = t.time_msc / interval_ms;                                 // F2: anchored on tick.time_msc
   if(bar_active && slot < bar_slot)
   {
      anomalies++;
      return;
   }
   if(!bar_active)
      OpenBar(slot, p, t);
   else if(slot != bar_slot)
   {
      long prev = bar_slot;
      CloseBar();                                                        // F2: close old ...
      long gap = slot - prev - 1;
      if(gap > 0)
      {
         empty_slots += gap;
         if(WriteEmptyBars) WriteGap(prev, gap);
      }
      OpenBar(slot, p, t);                                               // ... open new; both written by FlushPending
   }
   if(p > b_high) b_high = p;
   if(p < b_low)  b_low  = p;
   b_close = p;
   b_ticks++;                                                            // F3 tick_volume = ticks counted
   if(t.volume_real > 0.0)      { b_realvol += (long)t.volume_real; volume_seen = true; }
   else if(t.volume > 0)        { b_realvol += (long)t.volume;      volume_seen = true; }
   int sp = SpreadPoints(t);                                             // F4 in parent points
   switch(SpreadMode)
   {
      case XP_SPREAD_MAX: if(sp > b_spread) b_spread = sp; break;
      case XP_SPREAD_MIN: if(sp < b_spread) b_spread = sp; break;
      default:            b_spread = sp; break;
   }
   if(spread_min_seen < 0 || sp < spread_min_seen) spread_min_seen = sp;
   if(sp > spread_max_seen) spread_max_seen = sp;

   ticks_captured++;
   long sec = t.time_msc / 1000;
   if(sec == tps_second) tps_count++;
   else { tps_second = sec; tps_count = 1; }
   if(tps_count > max_tps) max_tps = tps_count;
   last_tick_local_ms = GetTickCount64();

   if(PushTicks)                                                         // F11: time and time_msc always consistent
   {
      MqlTick o = t;
      long cm = TickChartMsc(t.time_msc, slot);
      o.time_msc = cm;
      o.time     = (datetime)(cm / 1000);
      AppendTick(o);
   }
}
//+------------------------------------------------------------------+
//| F8 checked writes                                                |
//+------------------------------------------------------------------+
bool FlushPending()
{
   bool ok = true;
   int nt = ArraySize(pend_ticks);
   if(nt > 0)
   {
      ResetLastError();
      int r = CustomTicksAdd(custom_name, pend_ticks);
      int err = GetLastError();
      if(r < 0)
      {
         write_errors++;
         consecutive_fail++;
         ok = false;
         ErrPrint("CustomTicksAdd returned " + (string)r + " err=" + (string)err + " " + ErrName(err) + " ticks=" + (string)nt +
                  " first_msc=" + (string)pend_ticks[0].time_msc + " last_msc=" + (string)pend_ticks[nt - 1].time_msc);
      }
      else
      {
         if(r != nt) { partial_tick_adds++; ErrPrint("CustomTicksAdd added " + (string)r + " of " + (string)nt + " ticks err=" + (string)err); }
         ticks_pushed += r;
         ArrayResize(pend_ticks, 0);
         if(polls <= (long)FunnelPolls) Print("FUNNEL CustomTicksAdd ok=", r, "/", nt);
      }
   }
   int nb = ArraySize(pend_rates) + (bar_active ? 1 : 0);
   if(nb > 0)
   {
      MqlRates wr[];
      ArrayResize(wr, nb);
      int np = ArraySize(pend_rates);
      for(int i = 0; i < np; i++) wr[i] = pend_rates[i];
      if(bar_active) CurrentBar(wr[nb - 1]);
      ResetLastError();
      int r = CustomRatesUpdate(custom_name, wr);
      int err = GetLastError();
      if(r < 0)
      {
         write_errors++;
         consecutive_fail++;
         ok = false;
         ErrPrint("CustomRatesUpdate returned " + (string)r + " err=" + (string)err + " " + ErrName(err) + " bars=" + (string)nb +
                  " first=" + Ts(wr[0].time) + " last=" + Ts(wr[nb - 1].time));
      }
      else
      {
         rates_updates += r;
         for(int i = 0; i < np; i++)
            if(pend_slots[i] > written_slot_max) { bars_written++; written_slot_max = pend_slots[i]; }
         if(bar_active && bar_slot > written_slot_max) { bars_written++; written_slot_max = bar_slot; }
         ArrayResize(pend_rates, 0);
         ArrayResize(pend_slots, 0);
         if(polls <= (long)FunnelPolls) Print("FUNNEL CustomRatesUpdate ok=", r, " bars=", nb, " last_bar=", Ts(wr[nb - 1].time),
                                              " O=", DoubleToString(wr[nb-1].open, parent_digits), " H=", DoubleToString(wr[nb-1].high, parent_digits),
                                              " L=", DoubleToString(wr[nb-1].low, parent_digits), " C=", DoubleToString(wr[nb-1].close, parent_digits),
                                              " tv=", wr[nb-1].tick_volume, " spread=", wr[nb-1].spread);
      }
   }
   if(ok) consecutive_fail = 0;
   return ok;
}
//+------------------------------------------------------------------+
//| F9 restart-safe seed                                             |
//+------------------------------------------------------------------+
void SeedFromStoredBar(long current_slot)
{
   MqlRates last[];
   ResetLastError();
   int n = CopyRates(custom_name, PERIOD_M1, 0, 1, last);
   if(n < 1)
   {
      Print("F9 no stored bar in ", custom_name, " (CopyRates=", n, " err=", GetLastError(), ") - starting fresh");
      return;
   }
   last_close  = last[0].close;
   last_spread = last[0].spread;
   long stored_slot = 0;
   if(TimeAxis == XP_AXIS_SYNTHETIC)
   {
      long diff = (long)last[0].time - axis_base;
      if(diff < 0 || diff % 60 != 0)
      {
         Print("F9 stored bar ", Ts(last[0].time), " is not on the synthetic axis (axis_base ", Ts((datetime)axis_base), ") - starting fresh");
         return;
      }
      stored_slot = origin_slot + diff / 60;
   }
   else
      stored_slot = (long)last[0].time / interval_s;

   if(stored_slot != current_slot)
   {
      Print("F9 no seed: stored bar ", Ts(last[0].time), " slot=", stored_slot, " != current slot ", current_slot, " - starting fresh");
      return;
   }
   bar_active = true;
   bar_slot   = stored_slot;
   b_open  = last[0].open;
   b_high  = last[0].high;
   b_low   = last[0].low;
   b_close = last[0].close;
   b_ticks = last[0].tick_volume;
   b_spread = last[0].spread;
   b_realvol = last[0].real_volume;
   written_slot_max = stored_slot;
   seeded_bars = 1;
   Print("F9 SEEDED from stored bar ", Ts(last[0].time), " O=", DoubleToString(b_open, parent_digits), " H=", DoubleToString(b_high, parent_digits),
         " L=", DoubleToString(b_low, parent_digits), " tv=", b_ticks, " spread=", b_spread);
}
//+------------------------------------------------------------------+
//| F12 heartbeat                                                    |
//+------------------------------------------------------------------+
void Heartbeat(string tag)
{
   long age = (last_tick_local_ms == 0) ? -1 : (long)(GetTickCount64() - last_tick_local_ms);
   string axis   = (TimeAxis == XP_AXIS_SYNTHETIC) ? "SYNTHETIC" : "REAL";
   string basis  = (PriceBasis == XP_BASIS_ASK) ? "ASK" : (PriceBasis == XP_BASIS_MID) ? "MID" : "BID";
   string smode  = (SpreadMode == XP_SPREAD_MAX) ? "MAX" : (SpreadMode == XP_SPREAD_MIN) ? "MIN" : "LAST";
   string header = "time_server;time_local;actual_symbol;custom_name;interval_s;ticks_captured;bars_written;max_ticks_per_second;empty_slots;";
   header += "copyticks_errors;write_errors;last_tick_age_ms;real_volume_seen;bars_tickvol_gt1;spread_min_seen;spread_max_seen;";
   header += "cur_bar_tick_volume;cur_bar_spread;ticks_pushed;rates_updates;bars_opened;empty_bars_written;seeded_bars;";
   header += "consecutive_fail;blocked_events;anomalies;bad_ticks;dropped_ticks;dropped_bars;partial_tick_adds;file_errors;";
   header += "max_ticks_per_poll;polls;cursor_msc;price_basis;spread_mode;time_axis;axis_base;origin_slot;spec_pass;spec_fail;spec_not_settable;tag";
   string line = Ts(TimeCurrent()) + ";" + Ts(TimeLocal()) + ";" + actual_symbol + ";" + custom_name + ";" + (string)interval_s + ";" +
                 (string)ticks_captured + ";" + (string)bars_written + ";" + (string)max_tps + ";" + (string)empty_slots + ";" +
                 (string)copyticks_errors + ";" + (string)write_errors + ";" + (string)age + ";" + (string)volume_seen + ";" +
                 (string)bars_tickvol_gt1 + ";" + (string)spread_min_seen + ";" + (string)spread_max_seen + ";" +
                 (string)b_ticks + ";" + (string)b_spread + ";" + (string)ticks_pushed + ";" + (string)rates_updates + ";" + (string)bars_opened + ";" +
                 (string)empty_bars_written + ";" + (string)seeded_bars + ";" + (string)consecutive_fail + ";" + (string)blocked_events + ";" +
                 (string)anomalies + ";" + (string)bad_ticks + ";" + (string)dropped_ticks + ";" + (string)dropped_bars + ";" + (string)partial_tick_adds + ";" +
                 (string)file_errors + ";" + (string)max_ticks_per_poll + ";" + (string)polls + ";" + (string)cursor_msc + ";" + basis + ";" + smode + ";" + axis + ";" +
                 (string)axis_base + ";" + (string)origin_slot + ";" + (string)spec_pass + ";" + (string)spec_fail + ";" + (string)spec_not_settable + ";" + tag;
   Print("XP ChartEngine v2 HEARTBEAT ", tag, " ", actual_symbol, "->", custom_name, " S", interval_s, " ticks=", ticks_captured, " bars=", bars_written,
         " max_tps=", max_tps, " empty_slots=", empty_slots, " copyticks_err=", copyticks_errors, " write_err=", write_errors,
         " tick_age_ms=", age, " spread[", spread_min_seen, "..", spread_max_seen, "] cur_tv=", b_ticks, " real_vol=", volume_seen);
   AppendLine(HeartbeatFile(), header, line);
}
//+------------------------------------------------------------------+
//| Service program start function                                   |
//+------------------------------------------------------------------+
void OnStart()
{
   start_local_ms = GetTickCount64();
   interval_s = (Timeframe == S_Custom) ? ManualSeconds : (int)Timeframe;
   if(interval_s <= 0) interval_s = 1;
   interval_ms = (long)interval_s * 1000;
   int poll_ms = (PollSleepMs < 10) ? 10 : PollSleepMs;

   Print("XP ChartEngine v", Version, " starting: BaseSymbol=", BaseSymbol, " interval_s=", interval_s, " basis=", EnumToString(PriceBasis),
         " spread=", EnumToString(SpreadMode), " axis=", EnumToString(TimeAxis), " push_ticks=", PushTicks, " poll_ms=", poll_ms);

   // 1. F6 base symbol
   if(!ResolveBaseSymbol()) return;
   ResetLastError();
   bool sel = SymbolSelect(actual_symbol, true);
   Print("F6 base chosen: ", actual_symbol, " SymbolSelect=", sel, " err=", GetLastError());
   if(!sel)
   {
      Print("BLOCKED_NO_BASE_SYMBOL: cannot select '", actual_symbol, "' in Market Watch");
      return;
   }
   parent_point  = SymbolInfoDouble(actual_symbol, SYMBOL_POINT);
   parent_digits = (int)SymbolInfoInteger(actual_symbol, SYMBOL_DIGITS);
   if(parent_point <= 0.0)
   {
      Print("BLOCKED_NO_BASE_SYMBOL: '", actual_symbol, "' has SYMBOL_POINT=0");
      return;
   }

   // 2. F14 naming
   custom_name = actual_symbol + "_S" + (string)interval_s + CustomNameSuffix;
   gv_lock        = "XPC2.lock." + custom_name;
   gv_axis_base   = "XPC2.axis." + custom_name;
   gv_axis_origin = "XPC2.orig." + custom_name;

   // 3. F13 lock
   if(!AcquireLock()) return;

   // 4. create / reuse + F7 spec sync (both paths)
   if(!EnsureCustomSymbol()) { ReleaseLock(); return; }
   SyncSpecs();

   // 5. output folder (R6)
   FolderCreate(OutputDir);

   // 6. F1 cursor = current tick at start (R3: no backfill)
   MqlTick t0;
   long start_msc = 0;
   for(int w = 0; w < 100 && !IsStopped(); w++)               // up to ~10 s for a first tick
   {
      if(SymbolInfoTick(actual_symbol, t0) && t0.time_msc > 0) { start_msc = t0.time_msc; break; }
      Sleep(100);
   }
   if(start_msc == 0)
   {
      start_msc = (long)TimeCurrent() * 1000;
      Print("F1 no tick available at start (market closed?) - cursor from TimeCurrent ", Ts(TimeCurrent()));
   }
   cursor_msc  = start_msc;
   cursor_seen = 0;

   // 7. F10 axis, then F9 seed
   if(!LoadAxis(start_msc)) { ReleaseLock(); return; }
   SeedFromStoredBar(start_msc / interval_ms);

   Print("XP ChartEngine Active: ", actual_symbol, " -> ", custom_name, " | v", Version, " | interval_s=", interval_s,
         " | axis=", EnumToString(TimeAxis), " | basis=", EnumToString(PriceBasis), " | spread=", EnumToString(SpreadMode),
         " | cursor_from_msc=", cursor_msc, " (", Ts((datetime)(cursor_msc / 1000)), ") | point=", DoubleToString(parent_point, parent_digits),
         " digits=", parent_digits, " | output=MQL5\\Files\\", OutputDir, "\\");
   Heartbeat("start");
   last_hb_ms = GetTickCount64();

   //--- Main loop (F1): CopyTicks cursor, every tick, in order
   MqlTick ticks[];
   while(!IsStopped())
   {
      polls++;
      ResetLastError();
      int n = CopyTicks(actual_symbol, ticks, COPY_TICKS_ALL, (ulong)cursor_msc, (uint)((CopyTicksCount < 0) ? 0 : CopyTicksCount));   // from=cursor (inclusive left border)
      int err = GetLastError();
      if(polls <= (long)FunnelPolls)
         Print("FUNNEL poll=", polls, " CopyTicks=", n, " err=", err, " cursor_msc=", cursor_msc, " seen_at_cursor=", cursor_seen);
      if(n < 0)
      {
         copyticks_errors++;
         ErrPrint("CopyTicks(" + actual_symbol + ", from=" + (string)cursor_msc + ") returned " + (string)n + " err=" + (string)err + " " + ErrName(err));
      }
      else
      {
         int processed = 0, same = 0;
         for(int i = 0; i < n; i++)
         {
            long ms = ticks[i].time_msc;
            if(ms < cursor_msc) { anomalies++; continue; }
            if(ms == cursor_msc)
            {
               same++;
               if(same <= cursor_seen) continue;                          // boundary-millisecond dedupe (no +1 ms skip)
               cursor_seen = same;
            }
            else
            {
               cursor_msc  = ms;
               cursor_seen = 1;
               same = 1;
            }
            ProcessTick(ticks[i]);
            processed++;
         }
         if(processed > max_ticks_per_poll) max_ticks_per_poll = processed;
         if(processed > 0 || ArraySize(pend_ticks) > 0 || ArraySize(pend_rates) > 0)
            FlushPending();
      }

      if(consecutive_fail >= ConsecutiveFailLimit)                        // F8: never spin
      {
         blocked_events++;
         Print("BLOCKED_CUSTOM_WRITE: ", consecutive_fail, " consecutive failed writes to ", custom_name,
               " (write_errors=", write_errors, ") - sleeping 5 s then retrying; pending ticks=", ArraySize(pend_ticks), " bars=", ArraySize(pend_rates));
         consecutive_fail = 0;
         SleepInterruptible(5000);
      }

      ulong now = GetTickCount64();
      if(now - last_hb_ms >= (ulong)HeartbeatSeconds * 1000)
      {
         Heartbeat("run");
         RefreshLock();
         last_hb_ms = now;
      }
      Sleep(poll_ms);
   }

   //--- shutdown
   if(bar_active || ArraySize(pend_rates) > 0 || ArraySize(pend_ticks) > 0) FlushPending();
   Heartbeat("stop");
   if(map_handle != INVALID_HANDLE) FileClose(map_handle);
   ReleaseLock();
   Print("XP ChartEngine v", Version, " stopped: ", actual_symbol, " -> ", custom_name, " ticks=", ticks_captured, " bars=", bars_written,
         " write_errors=", write_errors, " uptime_s=", (long)((GetTickCount64() - start_local_ms) / 1000));
}
//+------------------------------------------------------------------+
