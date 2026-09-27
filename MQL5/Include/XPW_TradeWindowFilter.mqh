//+------------------------------------------------------------------+
//| XPW_TradeWindowFilter.mqh   v1.1                                  |
//| Decision gate only. Never sends, modifies or closes an order.     |
//|                                                                    |
//| SELL block : active-below a ceiling, window starts at attach.     |
//| BUY  block : cross-up a trigger,   window starts at the CROSS.    |
//|                                                                    |
//| Two layers, two jobs:                                              |
//|   XPWF_AllowSellSide / XPWF_AllowBuySide                            |
//|       "is this side live right now" (direction + window only).    |
//|       Use at ARMING so the suppressed side never exists.          |
//|   XPWF_AllowSell / XPWF_AllowBuy                                    |
//|       "may I fire this instant" (side + price test).              |
//|       Use immediately before the order call.                      |
//|                                                                    |
//| Both blocks disabled = host EA untouched (Gate 0).                |
//+------------------------------------------------------------------+
#ifndef XPW_TRADEWINDOWFILTER_MQH
#define XPW_TRADEWINDOWFILTER_MQH

input group "XPW Trade Window Filter"
input bool   XPWF_SellEnable       = false;  // Sell block: enable
input double XPWF_SellCeiling      = 0.0;    // Sell block: open sells only BELOW this price
input int    XPWF_SellWindowMin    = 30;     // Sell block: minutes, counted from attach
input bool   XPWF_BuyEnable        = false;  // Buy block: enable
input double XPWF_BuyTrigger       = 0.0;    // Buy block: price must cross UP through this
input int    XPWF_BuyWindowMin     = 30;     // Buy block: minutes, counted from the CROSS
input bool   XPWF_BuyRequireAbove  = true;   // Buy block: price must stay above trigger

//--- symbol calibration (read at init, never hardcoded)
int      g_xpwf_digits   = 0;
double   g_xpwf_tick     = 0.0;
double   g_xpwf_eps      = 0.0;
double   g_xpwf_ceilN    = 0.0;
double   g_xpwf_trigN    = 0.0;
datetime g_xpwf_armTime  = 0;
bool     g_xpwf_ready    = false;

//--- buy cross state
bool     g_xpwf_crossed  = false;
datetime g_xpwf_crossAt  = 0;
double   g_xpwf_prevAsk  = 0.0;
bool     g_xpwf_havePrev = false;

//--- side-live edge detection (window opened or closed since last tick)
bool     g_xpwf_edgeInit     = false;
bool     g_xpwf_prevSellLive = false;
bool     g_xpwf_prevBuyLive  = false;
bool     g_xpwf_edgeFlag     = false;

//--- funnel counters
long     g_xpwf_sellOK   = 0;
long     g_xpwf_sellNo   = 0;
long     g_xpwf_buyOK    = 0;
long     g_xpwf_buyNo    = 0;
long     g_xpwf_failsafe = 0;
string   g_xpwf_lastBlock = "";

//+------------------------------------------------------------------+
//| Snap a price to the symbol's own tick grid                        |
//+------------------------------------------------------------------+
double XPWF_Norm(const double p)
  {
   if(g_xpwf_tick <= 0.0)
      return(p);
   return(NormalizeDouble(MathRound(p / g_xpwf_tick) * g_xpwf_tick, g_xpwf_digits));
  }

bool XPWF_Expired(const datetime start, const int minutes)
  {
   if(minutes <= 0)
      return(true);
   return(TimeCurrent() >= start + (datetime)(minutes * 60));
  }

string XPWF_P(const double p)
  {
   return(DoubleToString(p, g_xpwf_digits));
  }

//+------------------------------------------------------------------+
//| Init: read symbol specs, validate inputs, stamp the arm time      |
//+------------------------------------------------------------------+
bool XPWF_Init()
  {
   g_xpwf_ready    = false;
   g_xpwf_crossed  = false;
   g_xpwf_crossAt  = 0;
   g_xpwf_havePrev = false;
   g_xpwf_edgeInit = false;
   g_xpwf_edgeFlag = false;

   g_xpwf_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_xpwf_tick   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(g_xpwf_tick <= 0.0)
      g_xpwf_tick = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(g_xpwf_tick <= 0.0)
     {
      Print("XPWF INIT_ABORT cannot read tick size or point for ", _Symbol);
      return(false);
     }
   g_xpwf_eps = g_xpwf_tick * 0.5;

   if(XPWF_SellEnable && XPWF_SellCeiling <= 0.0)
     {
      Print("XPWF INIT_ABORT sell block enabled but XPWF_SellCeiling is not set");
      return(false);
     }
   if(XPWF_BuyEnable && XPWF_BuyTrigger <= 0.0)
     {
      Print("XPWF INIT_ABORT buy block enabled but XPWF_BuyTrigger is not set");
      return(false);
     }

   g_xpwf_ceilN   = XPWF_Norm(XPWF_SellCeiling);
   g_xpwf_trigN   = XPWF_Norm(XPWF_BuyTrigger);
   g_xpwf_armTime = TimeCurrent();
   g_xpwf_ready   = true;

   PrintFormat("XPWF ARMED symbol=%s digits=%d tick=%s | SELL=%s below=%s window_min=%d | BUY=%s cross=%s window_min=%d require_above=%d",
               _Symbol, g_xpwf_digits, XPWF_P(g_xpwf_tick),
               (XPWF_SellEnable ? "ON" : "OFF"), XPWF_P(g_xpwf_ceilN), XPWF_SellWindowMin,
               (XPWF_BuyEnable  ? "ON" : "OFF"), XPWF_P(g_xpwf_trigN), XPWF_BuyWindowMin,
               (XPWF_BuyRequireAbove ? 1 : 0));
   return(true);
  }

//+------------------------------------------------------------------+
//| Side-live checks: direction + window only, no price test.         |
//| Disabled block = no opinion = true (host EA untouched).           |
//+------------------------------------------------------------------+
bool XPWF_AllowSellSide()
  {
   if(!XPWF_SellEnable)
      return(true);
   if(!g_xpwf_ready)
      return(false);
   return(!XPWF_Expired(g_xpwf_armTime, XPWF_SellWindowMin));
  }

bool XPWF_AllowBuySide()
  {
   if(!XPWF_BuyEnable)
      return(true);
   if(!g_xpwf_ready)
      return(false);
   if(!g_xpwf_crossed)
      return(false);
   return(!XPWF_Expired(g_xpwf_crossAt, XPWF_BuyWindowMin));
  }

//+------------------------------------------------------------------+
//| OnTick: buy cross detection, then window-edge detection.          |
//| Call as the first statement of the host OnTick.                   |
//+------------------------------------------------------------------+
void XPWF_OnTick()
  {
   if(!g_xpwf_ready)
      return;

   if(XPWF_BuyEnable)
     {
      MqlTick t;
      if(SymbolInfoTick(_Symbol, t))
        {
         double ask = XPWF_Norm(t.ask);
         if(!g_xpwf_crossed && g_xpwf_havePrev)
           {
            bool wasAtOrBelow = (g_xpwf_prevAsk <= g_xpwf_trigN + g_xpwf_eps);
            bool isAbove      = (ask            >  g_xpwf_trigN + g_xpwf_eps);
            if(wasAtOrBelow && isAbove)
              {
               g_xpwf_crossed = true;
               g_xpwf_crossAt = TimeCurrent();
               PrintFormat("XPWF BUY_CROSS ask=%s trigger=%s window_min=%d",
                           XPWF_P(ask), XPWF_P(g_xpwf_trigN), XPWF_BuyWindowMin);
              }
           }
         g_xpwf_prevAsk  = ask;
         g_xpwf_havePrev = true;
        }
     }

   bool sellLive = XPWF_AllowSellSide();
   bool buyLive  = XPWF_AllowBuySide();
   if(g_xpwf_edgeInit && (sellLive != g_xpwf_prevSellLive || buyLive != g_xpwf_prevBuyLive))
     {
      g_xpwf_edgeFlag = true;
      PrintFormat("XPWF SIDE_EDGE sell_live=%d buy_live=%d", (sellLive ? 1 : 0), (buyLive ? 1 : 0));
     }
   g_xpwf_prevSellLive = sellLive;
   g_xpwf_prevBuyLive  = buyLive;
   g_xpwf_edgeInit     = true;
  }

//+------------------------------------------------------------------+
//| True once when a side went live or dead since the last call.      |
//| Host EA uses it to force an immediate entry-level refresh.        |
//+------------------------------------------------------------------+
bool XPWF_SideStateChanged()
  {
   if(!g_xpwf_edgeFlag)
      return(false);
   g_xpwf_edgeFlag = false;
   return(true);
  }

//+------------------------------------------------------------------+
//| Fire checks: side + price. Sell tests Bid, buy tests Ask.         |
//| count=false for fail-safe layers so the funnel is not doubled.    |
//+------------------------------------------------------------------+
bool XPWF_AllowSell(const bool count = true)
  {
   if(!XPWF_SellEnable)
     {
      if(count) g_xpwf_sellOK++;
      return(true);
     }
   if(!XPWF_AllowSellSide())
     {
      if(count) { g_xpwf_sellNo++; g_xpwf_lastBlock = (g_xpwf_ready ? "SELL:window_over" : "SELL:not_ready"); }
      return(false);
     }
   MqlTick t;
   if(!SymbolInfoTick(_Symbol, t))
     {
      if(count) { g_xpwf_sellNo++; g_xpwf_lastBlock = "SELL:no_tick"; }
      return(false);
     }
   double bid = XPWF_Norm(t.bid);
   if(bid >= g_xpwf_ceilN - g_xpwf_eps)
     {
      if(count) { g_xpwf_sellNo++; g_xpwf_lastBlock = "SELL:at_or_above_ceiling"; }
      return(false);
     }
   if(count) g_xpwf_sellOK++;
   return(true);
  }

bool XPWF_AllowBuy(const bool count = true)
  {
   if(!XPWF_BuyEnable)
     {
      if(count) g_xpwf_buyOK++;
      return(true);
     }
   if(!XPWF_AllowBuySide())
     {
      if(count)
        {
         g_xpwf_buyNo++;
         if(!g_xpwf_ready)          g_xpwf_lastBlock = "BUY:not_ready";
         else if(!g_xpwf_crossed)   g_xpwf_lastBlock = "BUY:no_cross_yet";
         else                       g_xpwf_lastBlock = "BUY:window_over";
        }
      return(false);
     }
   if(XPWF_BuyRequireAbove)
     {
      MqlTick t;
      if(!SymbolInfoTick(_Symbol, t))
        {
         if(count) { g_xpwf_buyNo++; g_xpwf_lastBlock = "BUY:no_tick"; }
         return(false);
        }
      if(XPWF_Norm(t.ask) <= g_xpwf_trigN + g_xpwf_eps)
        {
         if(count) { g_xpwf_buyNo++; g_xpwf_lastBlock = "BUY:back_below_trigger"; }
         return(false);
        }
     }
   if(count) g_xpwf_buyOK++;
   return(true);
  }

//+------------------------------------------------------------------+
//| Fail-safe accounting (called by a CTrade::OrderSend override)     |
//+------------------------------------------------------------------+
void XPWF_NoteFailsafeBlock(const string side)
  {
   g_xpwf_failsafe++;
   g_xpwf_lastBlock = "FAILSAFE:" + side;
   PrintFormat("XPWF FAILSAFE_BLOCK side=%s (an entry reached OrderSend past the arming and call-site layers)", side);
  }

//+------------------------------------------------------------------+
//| Funnel report — call from OnDeinit                                |
//+------------------------------------------------------------------+
void XPWF_Report()
  {
   PrintFormat("XPWF FUNNEL sell_allow=%d sell_block=%d buy_allow=%d buy_block=%d failsafe_blocks=%d buy_crossed=%d last_block=%s",
               (int)g_xpwf_sellOK, (int)g_xpwf_sellNo,
               (int)g_xpwf_buyOK,  (int)g_xpwf_buyNo,
               (int)g_xpwf_failsafe, (g_xpwf_crossed ? 1 : 0),
               (g_xpwf_lastBlock == "" ? "none" : g_xpwf_lastBlock));
  }

#endif // XPW_TRADEWINDOWFILTER_MQH
