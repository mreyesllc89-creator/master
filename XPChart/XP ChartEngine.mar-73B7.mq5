//+------------------------------------------------------------------+
//|                                                   XP ChartEngine |
//|                                         Developed by Coders Guru |
//|                                          Copyrighted for XPWORX |
//|                                          https://www.xpworx.com |
//+------------------------------------------------------------------+
#property service
#property copyright   "xpworx"
#property link        "https://www.xpworx.com"
#property description "XP ChartEngine"
#define  Version      "1.2"
#property version     Version
#property strict

enum ENUM_CUSTOM_SECONDS 
{ 
   S1=1,       // 1 Second
   S2=2,       // 2 Seconds
   S5=5,       // 5 Seconds 
   S10=10,     // 10 Seconds
   S30=30,     // 30 Seconds
   S_Custom=0  // Manual Input
};

input string               BaseSymbol    = "BTCUSD";      
input ENUM_CUSTOM_SECONDS  Timeframe     = S1;            
input int                  ManualSeconds = 15;           

string actual_symbol; 
string custom_name;  

//+------------------------------------------------------------------+
//| Service program start function                                   |
//+------------------------------------------------------------------+
void OnStart()
{
   int interval_s = (Timeframe == S_Custom) ? ManualSeconds : (int)Timeframe;
   if(interval_s <= 0) interval_s = 1;

   // 1. AUTO-DETECT BROKER SUFFIX
   actual_symbol = "";
   for(int i=0; i<SymbolsTotal(false); i++) {
      string sym = SymbolName(i, false);
      if(StringFind(sym, BaseSymbol) >= 0) {
         actual_symbol = sym;
         break;
      }
   }

   if(actual_symbol == "") {
      Print("ERROR: Could not find any broker symbol containing: ", BaseSymbol);
      return;
   }

   // 2. AUTO-GENERATE CUSTOM NAME
   custom_name = actual_symbol + "_S" + (string)interval_s;

   // 3. CREATE OR SELECT SYMBOL
   if(!SymbolSelect(custom_name, true)) {
      if(!CustomSymbolCreate(custom_name, "Custom\\XPChart", actual_symbol)) {
         Print("Failed to create custom symbol. Error: ", GetLastError());
         return;
      }
      SymbolSelect(custom_name, true);
      CustomSymbolSetInteger(custom_name, SYMBOL_DIGITS, (int)SymbolInfoInteger(actual_symbol, SYMBOL_DIGITS));
   }

   Print("XP ChartEngine Active: ", actual_symbol, " -> ", custom_name);

   MqlTick last_tick;
   MqlRates s_bar[1];
   double bar_open=0, bar_high=0, bar_low=0;
   datetime last_bar_time=0;
   long last_tick_time_msc = 0; // Filter to avoid redundant updates

//--- Main Loop
   while(!IsStopped()) 
   {
      if(SymbolInfoTick(actual_symbol, last_tick)) 
      {
         if(last_tick.time_msc != last_tick_time_msc)
         {
            datetime current_time = TimeCurrent();
            datetime bar_time = (current_time / interval_s) * interval_s;
            
            if(bar_time != last_bar_time) {
               bar_open = last_tick.bid;
               bar_high = last_tick.bid;
               bar_low  = last_tick.bid;
               last_bar_time = bar_time;
            }
            
            bar_high = MathMax(bar_high, last_tick.bid);
            bar_low  = MathMin(bar_low, last_tick.bid);

            s_bar[0].time = bar_time;
            s_bar[0].open = bar_open;
            s_bar[0].high = bar_high;
            s_bar[0].low  = bar_low;
            s_bar[0].close = last_tick.bid;
            s_bar[0].tick_volume = 1;
            s_bar[0].spread = (int)((last_tick.ask - last_tick.bid) / SymbolInfoDouble(actual_symbol, SYMBOL_POINT));

            // A. Update the Visual Chart
            CustomRatesUpdate(custom_name, s_bar);

            // B. FIX: Push a Virtual Tick using an ARRAY (Fixes error 113)
            MqlTick tick_to_push[1]; 
            tick_to_push[0] = last_tick;
            tick_to_push[0].time = current_time;
            
            // This function expects: (symbol, array, count)
            CustomTicksAdd(custom_name, tick_to_push, 1);

            last_tick_time_msc = last_tick.time_msc;
         }
      }
      Sleep(100); 
   }
}