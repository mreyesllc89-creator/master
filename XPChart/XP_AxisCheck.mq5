//+------------------------------------------------------------------+
//|                                                 XP_AxisCheck.mq5 |
//|  GATE 1 receipt: which time axis does a custom *_S<n> symbol hold |
//|  READ-ONLY: no SymbolSelect, no Custom* writes, no deletes.       |
//+------------------------------------------------------------------+
#property copyright   "xpworx"
#property link        "ghostmaster"
#property description "XP AxisCheck - read-only bar-time-axis receipt for a custom symbol (Gate 1)"
#define  Version      "1.00"
#property version     Version
#property strict
#property script_show_inputs

input string CheckSymbol             = "";        // symbol to check ("" = chart symbol)
input int    ExpectedIntervalSeconds = 1;         // interval_s the engine was run with
input int    BarsToRead              = 500;       // CopyRates(sym, PERIOD_M1, 0, N)
input int    TicksToRead             = 200;       // last N ticks of the custom tick DB (0 = skip)
input string OutputDir               = "XPChart"; // under MQL5\Files (R6)

string g_lines[];
int    g_nlines = 0;

//+------------------------------------------------------------------+
void Add(string line)
{
   Print("XP_AxisCheck ", line);
   ArrayResize(g_lines, g_nlines + 1);
   g_lines[g_nlines] = line;
   g_nlines++;
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
string Ts(datetime t)
{
   return TimeToString(t, TIME_DATE | TIME_MINUTES | TIME_SECONDS);
}
//+------------------------------------------------------------------+
void WriteReceipt(string sym)
{
   FolderCreate(OutputDir);
   string path = OutputDir + "\\axischeck_" + SanitizeFileName(sym) + ".csv";
   int h = FileOpen(path, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      Print("XP_AxisCheck could not open ", path, " err=", GetLastError());
      return;
   }
   FileSeek(h, 0, SEEK_END);
   string hdr = "# XP_AxisCheck v";
   hdr += Version;
   hdr += " run_local=" + Ts(TimeLocal()) + " run_server=" + Ts(TimeCurrent());
   FileWrite(h, hdr);
   for(int i = 0; i < g_nlines; i++)
      FileWrite(h, g_lines[i]);
   FileClose(h);
   Print("XP_AxisCheck receipt appended to MQL5\\Files\\", path);
}
//+------------------------------------------------------------------+
void OnStart()
{
   string sym = (CheckSymbol == "") ? _Symbol : CheckSymbol;
   bool is_custom = false;
   bool exists = SymbolExist(sym, is_custom);

   Add("symbol;" + sym);
   Add("exists;" + (string)exists);
   Add("is_custom;" + (string)is_custom);
   Add("selected_in_market_watch;" + (string)SymbolInfoInteger(sym, SYMBOL_SELECT));
   Add("path;" + SymbolInfoString(sym, SYMBOL_PATH));
   Add("digits;" + (string)SymbolInfoInteger(sym, SYMBOL_DIGITS));
   Add("expected_interval_s;" + (string)ExpectedIntervalSeconds);

   if(!exists)
   {
      Add("VERDICT: EMPTY | symbol=" + sym + " | reason=symbol_not_found");
      WriteReceipt(sym);
      return;
   }

   Add("bars_total_M1;" + (string)Bars(sym, PERIOD_M1));

   MqlRates r[];
   ArraySetAsSeries(r, false);
   ResetLastError();
   int n = CopyRates(sym, PERIOD_M1, 0, BarsToRead, r);
   int err = GetLastError();
   Add("copyrates_returned;" + (string)n + ";err;" + (string)err);

   string verdict = "";
   if(n <= 0)
   {
      verdict = "EMPTY";
      Add("note;CopyRates returned nothing. If selected_in_market_watch=0 add the symbol to Market Watch by hand and re-run (this script stays read-only).");
   }
   else
   {
      datetime first = r[0].time;
      datetime last  = r[n - 1].time;
      int non_minute = 0;
      for(int i = 0; i < n; i++)
         if(((long)r[i].time) % 60 != 0) non_minute++;

      long dvals[];
      int  dcnt[];
      int  nd = 0;
      long dmin = 0, dmax = 0;
      for(int i = 1; i < n; i++)
      {
         long d = (long)r[i].time - (long)r[i - 1].time;
         if(i == 1 || d < dmin) dmin = d;
         if(i == 1 || d > dmax) dmax = d;
         int idx = -1;
         for(int k = 0; k < nd; k++)
            if(dvals[k] == d) { idx = k; break; }
         if(idx < 0)
         {
            ArrayResize(dvals, nd + 1);
            ArrayResize(dcnt, nd + 1);
            dvals[nd] = d;
            dcnt[nd] = 0;
            idx = nd;
            nd++;
         }
         dcnt[idx]++;
      }
      // selection sort by count desc
      for(int a = 0; a < nd; a++)
         for(int b = a + 1; b < nd; b++)
            if(dcnt[b] > dcnt[a])
            {
               long tv = dvals[a]; dvals[a] = dvals[b]; dvals[b] = tv;
               int  tc = dcnt[a];  dcnt[a]  = dcnt[b];  dcnt[b]  = tc;
            }
      long modal = (nd > 0) ? dvals[0] : 0;
      int  modal_cnt = (nd > 0) ? dcnt[0] : 0;

      Add("bars_read;" + (string)n);
      Add("first_bar;" + Ts(first) + ";" + (string)(long)first);
      Add("last_bar;" + Ts(last) + ";" + (string)(long)last);
      Add("non_minute_aligned_bars;" + (string)non_minute);
      Add("delta_min_s;" + (string)dmin + ";delta_max_s;" + (string)dmax);
      for(int k = 0; k < nd; k++)
         Add("delta_s;" + (string)dvals[k] + ";count;" + (string)dcnt[k]);
      Add("last_bar_ohlc;" + DoubleToString(r[n-1].open, 8) + ";" + DoubleToString(r[n-1].high, 8) + ";" +
          DoubleToString(r[n-1].low, 8) + ";" + DoubleToString(r[n-1].close, 8) +
          ";tick_volume;" + (string)r[n-1].tick_volume + ";spread;" + (string)r[n-1].spread);

      if(n == 1)
         verdict = "OTHER_AXIS(single_bar)";
      else if(non_minute > 0 || modal == ExpectedIntervalSeconds)
         verdict = "SECONDS_AXIS_REAL";
      else if(modal == 60)
         verdict = "M1_AXIS";
      else
         verdict = "OTHER_AXIS(" + (string)modal + ")";

      Add("VERDICT: " + verdict + " | symbol=" + sym + " | bars=" + (string)n +
          " | modal_delta_s=" + (string)modal + " (" + (string)modal_cnt + "/" + (string)(n - 1) + ")" +
          " | non_minute_bars=" + (string)non_minute + " | first=" + Ts(first) + " | last=" + Ts(last));
   }

   if(TicksToRead > 0)
   {
      MqlTick t[];
      ResetLastError();
      int nt = CopyTicks(sym, t, COPY_TICKS_ALL, 0, (uint)TicksToRead);   // from=0 + count => last N ticks, read-only
      int terr = GetLastError();
      Add("copyticks_returned;" + (string)nt + ";err;" + (string)terr);
      if(nt > 0)
      {
         long distinct_sec = 0, prev_sec = -1, mismatch = 0;
         for(int i = 0; i < nt; i++)
         {
            long sec = t[i].time_msc / 1000;
            if(sec != prev_sec) { distinct_sec++; prev_sec = sec; }
            if((long)t[i].time != sec) mismatch++;                       // D9 receipt: time vs time_msc
         }
         Add("ticks_first_msc;" + (string)t[0].time_msc + ";" + Ts(t[0].time));
         Add("ticks_last_msc;" + (string)t[nt - 1].time_msc + ";" + Ts(t[nt - 1].time));
         Add("ticks_distinct_seconds;" + (string)distinct_sec + ";ticks_per_second_avg;" +
             DoubleToString((distinct_sec > 0) ? (double)nt / (double)distinct_sec : 0.0, 2));
         Add("ticks_time_vs_time_msc_mismatch;" + (string)mismatch);
      }
   }

   if(verdict == "EMPTY")
      Add("VERDICT: EMPTY | symbol=" + sym + " | bars=0");

   WriteReceipt(sym);
}
//+------------------------------------------------------------------+
