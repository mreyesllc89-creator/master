# XP ChartEngine source census - 2026-09-22 09:37:19

Prompt base (LF-normalised sha256): `ddad0226f8d85be1010a452c6b1cb0d943cc70ddd5d63b695b1cee88c55fd9e0`

Newest source (P0.1 base candidate): `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\86ADC2D106E3946A8F8D9E6D2FD89531\MQL5\Services\XP ChartEngine.mq5` (2026-08-24 12:12:02, norm=d7d776d4246fab0a100e5d5b4734be267982ad9f49ec4307f117d0fff870117d)

| norm sha256 | copies | newest write | matches prompt base |
|---|---|---|---|
| 92723dd92a9b5ccd67ba3b2900b8ed41a719109ea00c13d2e127a4c62dcbfa41 | 1 | 2026-08-24 11:54:08 | no |
| fc322fd2217401b00282b419b86fe70840f0ab1648923d8423484a3720b1a21f | 2 | 2026-03-20 06:36:14 | no |
| d7d776d4246fab0a100e5d5b4734be267982ad9f49ec4307f117d0fff870117d | 1 | 2026-08-24 12:12:02 | no |

## Copies
- `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\5FFA568149E88FCD5B44D926DCFEAA79\MQL5\Services\XP ChartEngine.mq5` 2026-08-24 11:54:08 norm=92723dd92a9b5ccd67ba3b2900b8ed41a719109ea00c13d2e127a4c62dcbfa41
- `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\73B7A2420D6397DFF9014A20F1201F97\MQL5\Services\XP ChartEngine.mq5` 2026-03-20 06:36:14 norm=fc322fd2217401b00282b419b86fe70840f0ab1648923d8423484a3720b1a21f
- `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\86ADC2D106E3946A8F8D9E6D2FD89531\MQL5\Services\XP ChartEngine.mq5` 2026-08-24 12:12:02 norm=d7d776d4246fab0a100e5d5b4734be267982ad9f49ec4307f117d0fff870117d
- `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\9BB124B7D418C7FB69DF2865535BA9BF\MQL5\Services\XP ChartEngine.mq5` 2026-03-20 06:36:14 norm=fc322fd2217401b00282b419b86fe70840f0ab1648923d8423484a3720b1a21f

## Diffs against newest

### `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\5FFA568149E88FCD5B44D926DCFEAA79\MQL5\Services\XP ChartEngine.mq5` vs newest
```diff
git.exe : warning: in the working copy of 'C:\Users\maynor\AppData\Local\Temp\xp_census_a.mq5', LF will be replaced by 
CRLF the next time Git touches it
At C:\Users\maynor\Downloads\xpchartv2\XP_Census.ps1:128 char:15
+       $md += (& git --no-pager diff --no-index -- $a $b 2>&1 | Out-St ...
+               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (warning: in the... Git touches it:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
warning: in the working copy of 'C:\Users\maynor\AppData\Local\Temp\xp_census_b.mq5', LF will be replaced by CRLF the 
next time Git touches it
diff --git "a/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_a.mq5" "b/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_b.mq5"
index 598cfbf..93def81 100644
--- "a/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_a.mq5"
+++ "b/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_b.mq5"
@@ -203,7 +203,7 @@ void OnStart()
 
              // B. FIX: Push a Virtual Tick using an ARRAY (Fixes error 113)
              MqlTick tick_to_push[1]; 
-            tick_to_push[0] = last_tick;
+             tick_to_push[0] = last_tick;
             tick_to_push[0].time = current_time;
             
             // This function expects: (symbol, array, count)

```

### `C:\Users\maynor\AppData\Roaming\MetaQuotes\Terminal\73B7A2420D6397DFF9014A20F1201F97\MQL5\Services\XP ChartEngine.mq5` vs newest
```diff
git.exe : warning: in the working copy of 'C:\Users\maynor\AppData\Local\Temp\xp_census_a.mq5', LF will be replaced by 
CRLF the next time Git touches it
At C:\Users\maynor\Downloads\xpchartv2\XP_Census.ps1:128 char:15
+       $md += (& git --no-pager diff --no-index -- $a $b 2>&1 | Out-St ...
+               ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (warning: in the... Git touches it:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
warning: in the working copy of 'C:\Users\maynor\AppData\Local\Temp\xp_census_b.mq5', LF will be replaced by CRLF the 
next time Git touches it
diff --git "a/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_a.mq5" "b/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_b.mq5"
index 598cfbf..b55d54a 100644
--- "a/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_a.mq5"
+++ "b/C:\\Users\\maynor\\AppData\\Local\\Temp\\xp_census_b.mq5"
@@ -25,76 +25,9 @@ enum ENUM_CUSTOM_SECONDS
 input string               BaseSymbol    = "BTCUSD";      
 input ENUM_CUSTOM_SECONDS  Timeframe     = S1;            
 input int                  ManualSeconds = 15;           
-input bool                 UpdateRatesEveryTick = false;
 
 string actual_symbol; 
 string custom_name;  
-string lock_key;
-string heartbeat_key;
-double lock_owner = 0.0;
-bool lock_acquired = false;
-
-bool AcquireCustomSymbolLock()
-{
-   lock_key = "XPChartEngine.Lock." + custom_name;
-   heartbeat_key = lock_key + ".Heartbeat";
-   lock_owner = (double)TimeLocal() * 100000.0 + (double)(GetTickCount() % 100000);
-
-   if(!GlobalVariableCheck(lock_key))
-      GlobalVariableSet(lock_key, 0.0);
-
-   double current_owner = GlobalVariableGet(lock_key);
-   if(current_owner != 0.0)
-   {
-      if(GlobalVariableCheck(heartbeat_key))
-      {
-         datetime last_seen = (datetime)GlobalVariableGet(heartbeat_key);
-         if(TimeLocal() - last_seen > 30)
-            GlobalVariableSet(lock_key, 0.0);
-      }
-   }
-
-   ResetLastError();
-   if(!GlobalVariableSetOnCondition(lock_key, lock_owner, 0.0))
-   {
-      Print("XP ChartEngine stopped: ", custom_name, " is already being generated by another service instance.");
-      return false;
-   }
-
-   lock_acquired = true;
-   GlobalVariableSet(heartbeat_key, (double)TimeLocal());
-   return true;
-}
-
-void TouchCustomSymbolLock()
-{
-   if(lock_acquired)
-      GlobalVariableSet(heartbeat_key, (double)TimeLocal());
-}
-
-void ReleaseCustomSymbolLock()
-{
-   if(!lock_acquired)
-      return;
-
-   if(GlobalVariableCheck(lock_key) && GlobalVariableGet(lock_key) == lock_owner)
-   {
-      GlobalVariableSet(lock_key, 0.0);
-      GlobalVariableDel(heartbeat_key);
-   }
-}
-
-void FillRateBar(MqlRates &rates[], datetime bar_time, double open, double high, double low, double close, long volume, int spread)
-{
-   rates[0].time = bar_time;
-   rates[0].open = open;
-   rates[0].high = high;
-   rates[0].low = low;
-   rates[0].close = close;
-   rates[0].tick_volume = volume;
-   rates[0].spread = spread;
-   rates[0].real_volume = 0;
-}
 
 //+------------------------------------------------------------------+
 //| Service program start function                                   |
@@ -122,14 +55,10 @@ void OnStart()
    // 2. AUTO-GENERATE CUSTOM NAME
    custom_name = actual_symbol + "_S" + (string)interval_s;
 
-   if(!AcquireCustomSymbolLock())
-      return;
-
    // 3. CREATE OR SELECT SYMBOL
    if(!SymbolSelect(custom_name, true)) {
       if(!CustomSymbolCreate(custom_name, "Custom\\XPChart", actual_symbol)) {
          Print("Failed to create custom symbol. Error: ", GetLastError());
-         ReleaseCustomSymbolLock();
          return;
       }
       SymbolSelect(custom_name, true);
@@ -140,69 +69,43 @@ void OnStart()
 
    MqlTick last_tick;
    MqlRates s_bar[1];
-   double bar_open=0, bar_high=0, bar_low=0, bar_close=0;
-   long bar_tick_volume=0;
-   int bar_spread=0;
+   double bar_open=0, bar_high=0, bar_low=0;
    datetime last_bar_time=0;
-   datetime last_heartbeat_time=0;
-   bool bar_ready=false;
    long last_tick_time_msc = 0; // Filter to avoid redundant updates
 
 //--- Main Loop
    while(!IsStopped()) 
    {
-      datetime now = TimeLocal();
-      if(now != last_heartbeat_time)
-      {
-         TouchCustomSymbolLock();
-         last_heartbeat_time = now;
-      }
-
       if(SymbolInfoTick(actual_symbol, last_tick)) 
       {
          if(last_tick.time_msc != last_tick_time_msc)
          {
-             datetime current_time = TimeCurrent();
-             datetime bar_time = (current_time / interval_s) * interval_s;
-             int current_spread = (int)((last_tick.ask - last_tick.bid) / SymbolInfoDouble(actual_symbol, SYMBOL_POINT));
-             
-             if(!bar_ready) {
-                bar_open = last_tick.bid;
-                bar_high = last_tick.bid;
-                bar_low  = last_tick.bid;
-                bar_close = last_tick.bid;
-                bar_tick_volume = 0;
-                bar_spread = current_spread;
-                last_bar_time = bar_time;
-                bar_ready = true;
-             }
-             else if(bar_time != last_bar_time) {
-                FillRateBar(s_bar, last_bar_time, bar_open, bar_high, bar_low, bar_close, bar_tick_volume, bar_spread);
-                CustomRatesUpdate(custom_name, s_bar, 1);
-
-                bar_open = last_tick.bid;
-                bar_high = last_tick.bid;
-                bar_low  = last_tick.bid;
-                bar_close = last_tick.bid;
-                bar_tick_volume = 0;
-                bar_spread = current_spread;
-                last_bar_time = bar_time;
-             }
-             
-             bar_high = MathMax(bar_high, last_tick.bid);
-             bar_low  = MathMin(bar_low, last_tick.bid);
-             bar_close = last_tick.bid;
-             bar_tick_volume++;
-             bar_spread = current_spread;
-
-             if(UpdateRatesEveryTick)
-             {
-                FillRateBar(s_bar, last_bar_time, bar_open, bar_high, bar_low, bar_close, bar_tick_volume, bar_spread);
-                CustomRatesUpdate(custom_name, s_bar, 1);
-             }
-
-             // B. FIX: Push a Virtual Tick using an ARRAY (Fixes error 113)
-             MqlTick tick_to_push[1]; 
+            datetime current_time = TimeCurrent();
+            datetime bar_time = (current_time / interval_s) * interval_s;
+            
+            if(bar_time != last_bar_time) {
+               bar_open = last_tick.bid;
+               bar_high = last_tick.bid;
+               bar_low  = last_tick.bid;
+               last_bar_time = bar_time;
+            }
+            
+            bar_high = MathMax(bar_high, last_tick.bid);
+            bar_low  = MathMin(bar_low, last_tick.bid);
+
+            s_bar[0].time = bar_time;
+            s_bar[0].open = bar_open;
+            s_bar[0].high = bar_high;
+            s_bar[0].low  = bar_low;
+            s_bar[0].close = last_tick.bid;
+            s_bar[0].tick_volume = 1;
+            s_bar[0].spread = (int)((last_tick.ask - last_tick.bid) / SymbolInfoDouble(actual_symbol, SYMBOL_POINT));
+
+            // A. Update the Visual Chart
+            CustomRatesUpdate(custom_name, s_bar);
+
+            // B. FIX: Push a Virtual Tick using an ARRAY (Fixes error 113)
+            MqlTick tick_to_push[1]; 
             tick_to_push[0] = last_tick;
             tick_to_push[0].time = current_time;
             
@@ -214,12 +117,4 @@ void OnStart()
       }
       Sleep(100); 
    }
-
-   if(bar_ready)
-   {
-      FillRateBar(s_bar, last_bar_time, bar_open, bar_high, bar_low, bar_close, bar_tick_volume, bar_spread);
-      CustomRatesUpdate(custom_name, s_bar, 1);
-   }
-
-   ReleaseCustomSymbolLock();
-}
+}
\ No newline at end of file

```
