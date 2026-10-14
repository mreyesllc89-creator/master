//+------------------------------------------------------------------+
//| ExportBars_VT.mq5  - script: exports MN1, W1, D1, H4, H1 bars of the  |
//| chart symbol to MQL5\Files\<symbol>_<TF>.csv (server time, UTC ms)    |
//| Attach to any XAUUSD-ECNc / BTCUSD.c chart and run once.               |
//+------------------------------------------------------------------+
#property script_show_inputs
input int MaxBars = 100000;
void Export(ENUM_TIMEFRAMES tf, string tag)
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, tf, 0, MaxBars, r);
   if(n <= 0) { Print("no data for ", tag, " err ", GetLastError()); return; }
   string name = _Symbol + "_" + tag + ".csv";
   int h = FileOpen(name, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) { Print("cannot open ", name); return; }
   FileWrite(h, "time_server", "open", "high", "low", "close", "tick_volume", "spread");
   for(int i = 0; i < n; i++)
      FileWrite(h, TimeToString(r[i].time, TIME_DATE | TIME_SECONDS), DoubleToString(r[i].open, _Digits), DoubleToString(r[i].high, _Digits),
                DoubleToString(r[i].low, _Digits), DoubleToString(r[i].close, _Digits), r[i].tick_volume, r[i].spread);
   FileClose(h);
   Print("exported ", n, " bars -> MQL5\\Files\\", name, " (", TimeToString(r[0].time, TIME_DATE), " .. ", TimeToString(r[n-1].time, TIME_DATE), ")");
  }
void OnStart()
  {
   Export(PERIOD_MN1, "MN1"); Export(PERIOD_W1, "W1"); Export(PERIOD_D1, "D1"); Export(PERIOD_H4, "H4"); Export(PERIOD_H1, "H1");
   Print("Done. Also press Home on the chart / Tools>Options>Charts 'Max bars' = Unlimited and re-run if the ranges above are short.");
  }
