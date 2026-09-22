//+------------------------------------------------------------------+
//|                                          XPW_DirectionVeto.mqh   |
//|                                                                  |
//|  Drop-in veto for any EA that trades through CTrade.             |
//|                                                                  |
//|      #include <XPW_DirectionVeto.mqh>                            |
//|      CXPDirTrade trade;        // instead of  CTrade trade;      |
//|                                                                  |
//|  That is the whole integration on the trading side. The EA keeps  |
//|  its own trigger, its own direction, its own sizing and its own   |
//|  exits; the ladder only refuses an ENTRY whose side it disagrees  |
//|  with, and only when InpDirMode = DIR_VETO.                       |
//|                                                                  |
//|  Still required in the EA's lifecycle:                            |
//|      OnInit   : if(!XPDir_Init(InpMagic)) return INIT_FAILED;    |
//|      OnDeinit : XPDir_Deinit();                                  |
//|      OnTimer  : XPDir_FunnelHeartbeat();                         |
//|                                                                  |
//|  SAFETY: a veto never blocks a close. XPDir_IsEntryRequest lets   |
//|  through every SLTP/MODIFY/REMOVE, anything naming a position or  |
//|  position_by, and any netting-account order that reduces an open  |
//|  position. Blocking a close would strand a live position with no  |
//|  stop management, which is worse than any entry it might prevent. |
//+------------------------------------------------------------------+
#property strict

#include <Trade\Trade.mqh>
#include "XPW_DirectionLadder.mqh"

class CXPDirTrade : public CTrade
{
public:
   virtual bool OrderSend(const MqlTradeRequest &request, MqlTradeResult &result)
   {
      if(XPDir_AllowsRequest(request))
         return CTrade::OrderSend(request, result);

      // Refused. Nothing was sent, so there is no position and no state to
      // unwind - which is exactly why a veto is safe where a side swap is not.
      ZeroMemory(result);
      result.retcode = TRADE_RETCODE_REJECT;
      result.comment = "XPDIR_VETO";
      return false;
   }
};
