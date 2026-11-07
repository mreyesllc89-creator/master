//+------------------------------------------------------------------+
//|                                                      EVK.mqh     |
//|                     EA Validation Kit  v1.0                      |
//|                                                                  |
//|  Add ONE line to any Expert Advisor:                             |
//|        #include <EVK/EVK.mqh>                                    |
//|                                                                  |
//|  In the MT5 Strategy Tester it then:                             |
//|   * rebuilds every closed trade of each test pass from the deal  |
//|     history (open/close time, side, volume, prices, initial SL,  |
//|     net profit incl. commission and swap, initial risk -> R)     |
//|   * returns a custom optimization criterion (OnTester)           |
//|   * during an optimization, sends each pass's trades to the      |
//|     terminal (frames) and writes ONE CSV with the inputs of      |
//|     every pass and all its trades:                               |
//|        <Common Data Folder>/Files/EVK/<EA>_<symbol>_<time>.csv   |
//|   * in a single test, writes that pass's trades the same way.    |
//|                                                                  |
//|  The CSV is read by the Python tool  python -m evk  (hold-out,   |
//|  walk-forward, robustness, stress tests, A/B comparison, report).|
//|                                                                  |
//|  If your EA already defines OnTester / OnTesterInit /            |
//|  OnTesterPass / OnTesterDeinit, put                              |
//|        #define EVK_NO_HANDLERS                                   |
//|  before the #include and call EVK_OnTester(), EVK_OnTesterInit(),|
//|  EVK_OnTesterPass(), EVK_OnTesterDeinit() from your handlers.    |
//|  If the EA sends frames of its own, call EVK_HandleFrame() for   |
//|  each frame inside your FrameNext loop instead of                |
//|  EVK_OnTesterPass() (which would consume your frames too).       |
//|                                                                  |
//|  The EA itself is not changed: EVK only reads the deal history.  |
//+------------------------------------------------------------------+
#ifndef EVK_MQH
#define EVK_MQH

#define EVK_VERSION     "1.0"
#define EVK_FIELDS      11      // doubles per trade in a frame
#define EVK_FRAME_NAME  "evk"
#define EVK_FRAME_ID    20261107

enum ENUM_EVK_CRITERION
  {
   EVK_CRIT_MIN_PERIOD_PF = 0, // Worst sub-period profit factor (robust)
   EVK_CRIT_PF            = 1, // Profit factor
   EVK_CRIT_NET           = 2, // Net profit (money)
   EVK_CRIT_EXPECTANCY_R  = 3, // Average R per trade
   EVK_CRIT_NET_OVER_DD   = 4  // Net profit / max drawdown (money)
  };

input group "=== EA Validation Kit (tester only) ==="
input bool               EVK_Enable    = true;                   // Record trades and export (tester only)
input long               EVK_Magic     = -1;                     // Only this magic number (-1 = all)
input ENUM_EVK_CRITERION EVK_Criterion = EVK_CRIT_MIN_PERIOD_PF; // Custom optimization criterion
input int                EVK_MinTrades = 30;                     // Passes with fewer trades score 0
input int                EVK_Periods   = 3;                      // Sub-periods for the worst-period criterion
input string             EVK_RunName   = "";                     // CSV name prefix ("" = EA name)

struct EVKTrade
  {
   long     position;
   datetime openTime;
   datetime closeTime;
   int      type;       // 0 buy, 1 sell
   double   volume;     // opened volume
   double   entry;      // volume-weighted entry price
   double   exitValue;  // sum(price*volume) of closing deals
   double   exitVolume; // closed volume
   double   sl;         // stop loss at entry (0 = none)
   double   profit;     // net: profit + commission + swap (+ fee)
   double   risk;       // money lost if the initial SL had been hit (0 = unknown)
   long     magic;
   string   symbol;
   bool     closed;     // fully closed (a netting reversal starts a new record)
  };

int    g_evkFile        = INVALID_HANDLE;
bool   g_evkHeader      = false;
string g_evkParamNames[];
string g_evkPath        = "";
long   g_evkPasses      = 0;

//+------------------------------------------------------------------+
//| helpers                                                          |
//+------------------------------------------------------------------+
string EVK_Clean(const string s)
  {
   string r = s;
   StringReplace(r, ",", " ");
   StringReplace(r, "\"", "'");
   StringReplace(r, "\r", " ");
   StringReplace(r, "\n", " ");
   StringReplace(r, "#", " ");        // '#' starts a comment line in the CSV
   return r;
  }

string EVK_Name()
  {
   string n = EVK_RunName;
   if(n == "")
      n = MQLInfoString(MQL_PROGRAM_NAME);
   return EVK_Clean(n);
  }

//--- the still-open record of a position (closed records are skipped)
int EVK_FindPosition(const EVKTrade &t[], const int count, const long position)
  {
   for(int i = count - 1; i >= 0; i--)   // recent positions first
      if(t[i].position == position && !t[i].closed)
         return i;
   return -1;
  }

int EVK_NewTrade(EVKTrade &t[], int &count, const ulong deal, const long pos, const datetime when,
                 const long dtype, const long magic)
  {
   int i = count++;
   ArrayResize(t, count, 256);
   t[i].position   = pos;
   t[i].openTime   = when;
   t[i].closeTime  = 0;
   t[i].type       = (dtype == DEAL_TYPE_BUY) ? 0 : 1;
   t[i].volume     = 0.0;
   t[i].entry      = 0.0;
   t[i].exitValue  = 0.0;
   t[i].exitVolume = 0.0;
   t[i].sl         = HistoryDealGetDouble(deal, DEAL_SL);
   if(t[i].sl <= 0.0)
     {
      ulong order = (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
      if(order > 0 && HistoryOrderSelect(order))
         t[i].sl = HistoryOrderGetDouble(order, ORDER_SL);
     }
   t[i].profit = 0.0;
   t[i].risk   = 0.0;
   t[i].magic  = magic;
   t[i].symbol = HistoryDealGetString(deal, DEAL_SYMBOL);
   t[i].closed = false;
   return i;
  }

//+------------------------------------------------------------------+
//| Rebuild closed trades from the deal history                      |
//+------------------------------------------------------------------+
int EVK_CollectTrades(EVKTrade &out[])
  {
   ArrayResize(out, 0);
   if(!HistorySelect(0, TimeCurrent() + 1))
      return 0;
   EVKTrade t[];
   int count = 0;
   int deals = HistoryDealsTotal();
   for(int k = 0; k < deals; k++)
     {
      ulong deal = HistoryDealGetTicket(k);
      if(deal == 0)
         continue;
      long dtype = HistoryDealGetInteger(deal, DEAL_TYPE);
      if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL)
         continue;                                   // balance, credit, charges ...
      long magic = HistoryDealGetInteger(deal, DEAL_MAGIC);
      if(EVK_Magic >= 0 && magic != EVK_Magic)
         continue;
      long   entry  = HistoryDealGetInteger(deal, DEAL_ENTRY);
      long   pos    = HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      double vol    = HistoryDealGetDouble(deal, DEAL_VOLUME);
      double price  = HistoryDealGetDouble(deal, DEAL_PRICE);
      double pnl    = HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP);
      double costs  = HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_FEE);
      datetime when = (datetime)HistoryDealGetInteger(deal, DEAL_TIME);
      int i = EVK_FindPosition(t, count, pos);

      if(entry == DEAL_ENTRY_IN || (entry == DEAL_ENTRY_INOUT && i < 0))
        {
         if(i < 0)
            i = EVK_NewTrade(t, count, deal, pos, when, dtype, magic);
         //--- scale-in: volume-weighted average entry
         double nv = t[i].volume + vol;
         if(nv > 0.0)
            t[i].entry = (t[i].entry * t[i].volume + price * vol) / nv;
         t[i].volume  = nv;
         t[i].profit += pnl + costs;                 // entry commission / fee
        }
      else if(i >= 0)                                // OUT, OUT_BY, or INOUT (netting reversal)
        {
         double openVol  = t[i].volume - t[i].exitVolume;
         double closeVol = (entry == DEAL_ENTRY_INOUT) ? MathMin(vol, openVol) : vol;
         double share    = (vol > 0.0) ? closeVol / vol : 1.0;
         t[i].exitValue  += price * closeVol;
         t[i].exitVolume += closeVol;
         t[i].profit     += pnl + costs * share;      // realised P/L belongs to the closed part
         t[i].closeTime   = when;
         if(t[i].exitVolume >= t[i].volume * 0.999)
            t[i].closed = true;
         //--- netting reversal: the rest of the deal opens a new trade on the other side
         double rest = vol - closeVol;
         if(entry == DEAL_ENTRY_INOUT && rest > 1e-9)
           {
            int j = EVK_NewTrade(t, count, deal, pos, when, dtype, magic);
            t[j].volume = rest;
            t[j].entry  = price;
            t[j].profit = costs * (1.0 - share);
           }
        }
     }
   //--- keep fully closed trades, compute initial risk
   int n = 0;
   for(int i = 0; i < count; i++)
     {
      if(!t[i].closed)
         continue;                                   // still open at the end of the test
      if(t[i].sl > 0.0)
        {
         double loss = 0.0;
         ENUM_ORDER_TYPE ot = (t[i].type == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         if(OrderCalcProfit(ot, t[i].symbol, t[i].volume, t[i].entry, t[i].sl, loss))
            t[i].risk = MathAbs(loss);
        }
      ArrayResize(out, n + 1, 256);
      out[n++] = t[i];
     }
   //--- order by close time (insertion sort; trades are almost sorted already)
   for(int i = 1; i < n; i++)
     {
      EVKTrade cur = out[i];
      int j = i - 1;
      while(j >= 0 && out[j].closeTime > cur.closeTime)
        {
         out[j + 1] = out[j];
         j--;
        }
      out[j + 1] = cur;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| Criterion                                                        |
//+------------------------------------------------------------------+
double EVK_PF(const double &p[], const int from, const int to)
  {
   double gw = 0.0, gl = 0.0;
   for(int i = from; i < to; i++)
     {
      if(p[i] > 0.0) gw += p[i];
      else           gl -= p[i];
     }
   if(gl <= 0.0)
      return (gw > 0.0) ? 100.0 : 0.0;   // capped instead of infinity
   return gw / gl;
  }

double EVK_Score(const EVKTrade &t[], const int n)
  {
   if(n < MathMax(1, EVK_MinTrades))
      return 0.0;
   double p[];
   ArrayResize(p, n);
   double net = 0.0, peak = 0.0, eq = 0.0, dd = 0.0, rsum = 0.0;
   int rn = 0;
   for(int i = 0; i < n; i++)
     {
      p[i] = t[i].profit;
      net += p[i];
      eq  += p[i];
      peak = MathMax(peak, eq);
      dd   = MathMax(dd, peak - eq);
      if(t[i].risk > 0.0) { rsum += t[i].profit / t[i].risk; rn++; }
     }
   switch(EVK_Criterion)
     {
      case EVK_CRIT_PF:           return EVK_PF(p, 0, n);
      case EVK_CRIT_NET:          return net;
      case EVK_CRIT_EXPECTANCY_R: return (rn > 0) ? rsum / rn : 0.0;
      case EVK_CRIT_NET_OVER_DD:  return (dd > 0.0) ? net / dd : (net > 0.0 ? 100.0 : 0.0);
      default:
        {
         //--- worst profit factor over EVK_Periods equal time slices (by close time)
         int periods = MathMax(1, EVK_Periods);
         datetime t0 = t[0].closeTime, t1 = t[n - 1].closeTime;
         double span = (double)(t1 - t0) + 1.0;
         double worst = 1e9;
         int start = 0;
         for(int k = 0; k < periods; k++)
           {
            int end = start;
            double limit = (double)t0 + span * (k + 1) / periods;
            while(end < n && (double)t[end].closeTime < limit) end++;
            if(k == periods - 1) end = n;
            if(end - start < 1)
               return 0.0;                           // a period without trades fails
            worst = MathMin(worst, EVK_PF(p, start, end));
            start = end;
           }
         return worst;
        }
     }
  }

//+------------------------------------------------------------------+
//| CSV writing                                                      |
//+------------------------------------------------------------------+
string EVK_TradeColumns()
  {
   return "open_time,close_time,side,volume,entry,exit,sl,profit,risk,r,magic";
  }

string EVK_TradeLine(const double &d[], const int k)
  {
   int b = k * EVK_FIELDS;
   double risk = d[b + 8];
   string r = (risk > 0.0) ? DoubleToString(d[b + 7] / risk, 4) : "";
   return StringFormat("%I64d,%I64d,%s,%.2f,%s,%s,%s,%.2f,%.2f,%s,%I64d",
                       (long)d[b + 0], (long)d[b + 1], (d[b + 2] < 0.5) ? "buy" : "sell", d[b + 3],
                       DoubleToString(d[b + 4], 8), DoubleToString(d[b + 5], 8), DoubleToString(d[b + 6], 8),
                       d[b + 7], d[b + 8], r, (long)d[b + 9]);
  }

void EVK_Pack(const EVKTrade &t[], const int n, double &d[])
  {
   ArrayResize(d, n * EVK_FIELDS);
   for(int i = 0; i < n; i++)
     {
      int b = i * EVK_FIELDS;
      d[b + 0]  = (double)t[i].openTime;
      d[b + 1]  = (double)t[i].closeTime;
      d[b + 2]  = t[i].type;
      d[b + 3]  = t[i].volume;
      d[b + 4]  = t[i].entry;
      d[b + 5]  = (t[i].exitVolume > 0.0) ? t[i].exitValue / t[i].exitVolume : 0.0;
      d[b + 6]  = t[i].sl;
      d[b + 7]  = t[i].profit;
      d[b + 8]  = t[i].risk;
      d[b + 9]  = (double)t[i].magic;
      d[b + 10] = 0.0;                                // reserved
     }
  }

bool EVK_Open()
  {
   if(g_evkFile != INVALID_HANDLE)
      return true;
   //--- in the tester TimeLocal() is the simulated time, so two single tests over the
   //    same period would get the same name: add _2, _3 ... until the name is free
   MqlDateTime s;
   TimeToStruct(TimeLocal(), s);
   string base = StringFormat("EVK\\%s_%s_%04d%02d%02d_%02d%02d%02d", EVK_Name(), EVK_Clean(_Symbol),
                              s.year, s.mon, s.day, s.hour, s.min, s.sec);
   if(!MQLInfoInteger(MQL_OPTIMIZATION) && MQLInfoInteger(MQL_TESTER))
      base += "_single";
   g_evkPath = base + ".csv";
   for(int k = 2; FileIsExist(g_evkPath, FILE_COMMON) && k < 10000; k++)
      g_evkPath = base + "_" + IntegerToString(k) + ".csv";
   g_evkFile = FileOpen(g_evkPath, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(g_evkFile == INVALID_HANDLE)
     {
      Print("[EVK] cannot create Common\\Files\\", g_evkPath, " error ", GetLastError());
      return false;
     }
   g_evkHeader = false;
   g_evkPasses = 0;
   return true;
  }

//--- write all rows of one pass (one row per trade, or one empty row if no trades)
void EVK_WritePass(const long pass, const double crit, string &params[], const int nparams,
                   const double &d[], const int ntrades)
  {
   if(!EVK_Open())
      return;
   string names[], values[];
   ArrayResize(names, nparams);
   ArrayResize(values, nparams);
   for(int i = 0; i < nparams; i++)
     {
      int eq = StringFind(params[i], "=");
      names[i]  = EVK_Clean(eq > 0 ? StringSubstr(params[i], 0, eq) : params[i]);
      values[i] = EVK_Clean(eq > 0 ? StringSubstr(params[i], eq + 1) : "");
     }
   if(!g_evkHeader)
     {
      ArrayResize(g_evkParamNames, nparams);
      string head = "pass,criterion";
      for(int i = 0; i < nparams; i++)
        {
         g_evkParamNames[i] = names[i];
         head += ",p." + names[i];
        }
      head += "," + EVK_TradeColumns();
      //--- in an optimization this runs in the terminal, whose account is not the tester's
      string ccy = (MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
                   ? AccountInfoString(ACCOUNT_CURRENCY) : "tester deposit currency";
      FileWriteString(g_evkFile, "# EVK " + EVK_VERSION + " | " + EVK_Name() + " | " + _Symbol +
                      " | " + ccy + " | times are broker server time\n");
      FileWriteString(g_evkFile, head + "\n");
      g_evkHeader = true;
     }
   //--- values in header order (inputs are identical across passes of one run)
   string prefix = StringFormat("%I64d,%.6f", pass, crit);
   for(int c = 0; c < ArraySize(g_evkParamNames); c++)
     {
      string v = "";
      for(int i = 0; i < nparams; i++)
         if(names[i] == g_evkParamNames[c]) { v = values[i]; break; }
      prefix += "," + v;
     }
   if(ntrades == 0)
      FileWriteString(g_evkFile, prefix + ",,,,,,,,,,,\n");
   for(int k = 0; k < ntrades; k++)
      FileWriteString(g_evkFile, prefix + "," + EVK_TradeLine(d, k) + "\n");
   g_evkPasses++;
  }

void EVK_Close()
  {
   if(g_evkFile == INVALID_HANDLE)
      return;
   FileClose(g_evkFile);
   g_evkFile = INVALID_HANDLE;
   Print("[EVK] ", g_evkPasses, " pass(es) written to <Common Data Folder>\\Files\\", g_evkPath,
         "  ->  python -m evk analyze <that file>");
  }

//+------------------------------------------------------------------+
//| Tester handlers                                                  |
//+------------------------------------------------------------------+
double EVK_OnTester()
  {
   //--- the criterion is always computed (also with EVK_Enable=false); only the export is optional
   EVKTrade t[];
   int n = EVK_CollectTrades(t);
   double crit = EVK_Score(t, n);
   if(!EVK_Enable)
      return crit;
   double d[];
   EVK_Pack(t, n, d);
   if(MQLInfoInteger(MQL_OPTIMIZATION))
     {
      //--- an empty pass still sends one frame, so it is counted in the CSV
      if(!FrameAdd(EVK_FRAME_NAME, EVK_FRAME_ID, crit, d))
         Print("[EVK] FrameAdd failed, error ", GetLastError());
     }
   else if(MQLInfoInteger(MQL_TESTER))
     {
      //--- single test: write the trades directly (pass 0, no input list available)
      string none[];
      EVK_WritePass(0, crit, none, 0, d, n);
      EVK_Close();
     }
   return crit;
  }

void EVK_OnTesterInit()
  {
   //--- the CSV is created when the first pass arrives, so an optimization that
   //    sends nothing leaves no empty file behind
   g_evkPasses = 0;
  }

//--- Handle ONE frame. Returns true if it was an EVK frame (and was written).
//    An EA that sends frames of its own calls this inside its own FrameNext loop
//    (with EVK_NO_HANDLERS) and handles the frames for which it returns false.
bool EVK_HandleFrame(const ulong pass, const string name, const long id, const double value, const double &d[])
  {
   if(!EVK_Enable || name != EVK_FRAME_NAME || id != EVK_FRAME_ID)
      return false;
   string params[];
   uint   np = 0;
   if(!FrameInputs(pass, params, np))
      np = 0;
   EVK_WritePass((long)pass, value, params, (int)np, d, ArraySize(d) / EVK_FIELDS);
   return true;
  }

//--- Default pass handler: reads every queued frame. Use it only when the EA sends
//    no frames of its own; otherwise use EVK_HandleFrame (see above).
void EVK_OnTesterPass()
  {
   ulong  pass;
   string name;
   long   id;
   double value;
   double d[];
   while(FrameNext(pass, name, id, value, d))
      EVK_HandleFrame(pass, name, id, value, d);
  }

void EVK_OnTesterDeinit()
  {
   EVK_OnTesterPass();   // collect any frames still queued
   if(EVK_Enable && g_evkPasses == 0)
      Print("[EVK] No passes were received, so no CSV was written. Passes served from the tester "
            "cache send nothing: delete the files in <terminal data folder>\\Tester\\cache or change "
            "EVK_RunName, then run the optimization again.");
   EVK_Close();
  }

#ifndef EVK_NO_HANDLERS
double OnTester()       { return EVK_OnTester(); }
void   OnTesterInit()   { EVK_OnTesterInit(); }
void   OnTesterPass()   { EVK_OnTesterPass(); }
void   OnTesterDeinit() { EVK_OnTesterDeinit(); }
#endif

#endif // EVK_MQH
//+------------------------------------------------------------------+
