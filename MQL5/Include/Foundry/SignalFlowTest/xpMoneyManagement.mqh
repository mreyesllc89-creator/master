// XPWorx Money Management 1.01 -- portable MQL5 include, no custom dependencies.
// The EA owns signals and event handlers. See docs/xpMoneyManagement.md.
#ifndef XPWORX_MONEY_MANAGEMENT_MQH
#define XPWORX_MONEY_MANAGEMENT_MQH

#define XPMM_VERSION "1.01"
// Tunables: define any of these before the include to override.
#ifndef XPMM_RECONNECT_GRACE_MS
#define XPMM_RECONNECT_GRACE_MS 10000   // connected time seen before an ambiguous wait is reconciled
#endif
#ifndef XPMM_MIN_RECONCILE_SECONDS
#define XPMM_MIN_RECONCILE_SECONDS 30
#endif
#ifndef XPMM_CLEANUP_BATCH
#define XPMM_CLEANUP_BATCH 20           // closed-position history checks per Refresh
#endif
#ifndef XPMM_CLEANUP_TRIES
#define XPMM_CLEANUP_TRIES 50           // Refresh attempts before an unconfirmed id is left to expire
#endif

enum XPMM_LOT_MODE
  { XPMM_FIXED_LOTS, XPMM_FIXED_CASH, XPMM_PERCENT_BALANCE,
    XPMM_PERCENT_EQUITY, XPMM_PERCENT_FREE_MARGIN, XPMM_CAPITAL_UNITS,
    XPMM_EQUITY_STEPS, XPMM_PROFIT_REINVEST };
enum XPMM_UNIT { XPMM_POINTS, XPMM_R, XPMM_ATR, XPMM_CASH };
enum XPMM_TRAIL_MODE
  { XPMM_TRAIL_OFF, XPMM_TRAIL_FIXED, XPMM_TRAIL_ATR,
    XPMM_TRAIL_CHANDELIER, XPMM_TRAIL_EXTERNAL, XPMM_TRAIL_GIVEBACK };
enum XPMM_STOP_MODE { XPMM_STOP_EXTERNAL, XPMM_STOP_POINTS, XPMM_STOP_ATR, XPMM_STOP_PERCENT };
enum XPMM_TP_MODE { XPMM_TP_OFF, XPMM_TP_EXTERNAL, XPMM_TP_POINTS, XPMM_TP_ATR, XPMM_TP_PERCENT, XPMM_TP_R };

struct XPMM_BE_STAGE
  { XPMM_UNIT unit; double trigger; double lock_points; double lock_r; bool cover_costs; };
struct XPMM_PARTIAL_STAGE
  { XPMM_UNIT unit; double trigger; double percent_original; };
struct XPMM_R_STAGE { double trigger_r; double lock_r; };
struct XPMM_COMPLETED { datetime at; ulong id; double pnl; };
struct XPMM_CONFIG
  {
   string symbol; ulong magic; string instance;
   XPMM_LOT_MODE lot_mode;
   double value;                      // lots, cash, or risk percent according to mode
   double capital_unit;               // capital denominator / equity step
   double base_capital;               // zero = capital captured at Configure
   double lots_per_step;
   double reinvest_percent;
   double max_lots; double max_risk_cash; double max_risk_percent;
   double max_total_risk_percent; double max_margin_percent; double max_spread_points;
   int max_positions; int max_entries_day; int max_losses;
   int loss_cooldown_seconds;
   double daily_loss_percent; double weekly_loss_percent; double max_drawdown_percent;
   double daily_profit_cash; double basket_profit_cash; double basket_loss_cash;
   double reduce_risk_at_dd; double reduced_risk_factor;
   bool guard_close; bool require_sl; bool require_tp; bool persist;
   bool exclusive_netting;             // explicit exclusive symbol ownership
   int reset_hour; int deviation_points; int retry_seconds;
   int max_hold_seconds; double estimated_exit_commission_per_lot;
   XPMM_STOP_MODE stop_mode; double stop_value;
   XPMM_TP_MODE tp_mode; double tp_value;
   XPMM_TRAIL_MODE trail_mode; XPMM_UNIT trail_trigger_unit;
   double trail_trigger; double trail_distance; double trail_step_points;
   double giveback_percent;
   int reconcile_seconds;              // ambiguous broker outcome wait; 0 = ConfirmBrokerReconciled only
  };
struct XPMM_ENTRY
  { ENUM_ORDER_TYPE type; double entry; double sl; double tp; double atr; string comment; };
struct XPMM_PLAN
  { ENUM_ORDER_TYPE type; string symbol; double entry; double sl; double tp;
    double volume; double risk_cash; double margin; string comment; };
struct XPMM_POSITION_STATE
  {
   ulong id; ulong ticket; long side; double entry; double risk; double original_volume;
   double favorable; double atr; double external_stop; double costs_cash;
   uint partial_mask; datetime opened; datetime last_try;
   ulong pending_order; bool uncertain; double pending_before; double pending_target;
   int pending_stage; bool closing;
   datetime since; ulong eligible; bool risk_known; // wait start, connected grace start, history conclusive
  };

void XPMM_Defaults(XPMM_CONFIG &c)
  {
   ZeroMemory(c);
   c.symbol=_Symbol; c.magic=20261001; c.instance="default";
   c.lot_mode=XPMM_PERCENT_EQUITY; c.value=1.0;
   c.capital_unit=10000; c.lots_per_step=0.01; c.reinvest_percent=100;
   c.max_margin_percent=25; c.reduced_risk_factor=0.5;
   c.require_sl=true; c.persist=true; c.exclusive_netting=false;
   c.retry_seconds=5; c.deviation_points=20; c.reconcile_seconds=60;
   c.stop_mode=XPMM_STOP_EXTERNAL; c.tp_mode=XPMM_TP_OFF;
   c.trail_mode=XPMM_TRAIL_OFF; c.trail_trigger_unit=XPMM_POINTS;
   c.giveback_percent=30;
  }

// Quantization uses the actual step; decimal-place inference is insufficient.
double XPMM_VolumeDown(const double raw,const double step,const double maximum)
  {
   if(!MathIsValidNumber(raw) || !MathIsValidNumber(step) || step<=0 || raw<=0 || maximum<=0) return 0;
   return NormalizeDouble(MathFloor(MathMin(raw,maximum)/step+1e-9)*step,8);
  }
// Largest partial close <= requested whose remainder stays tradable; zero when none exists.
double XPMM_CloseVolume(const double position,const double requested,const double step,
                        const double minimum,const double maximum)
  {
   if(!MathIsValidNumber(position) || !MathIsValidNumber(requested) || position<=0 || requested<=0) return 0;
   double volume=XPMM_VolumeDown(MathMin(position,requested),step,maximum);
   double rest=position-volume;
   if(rest>1e-9 && rest<minimum-1e-9) volume=XPMM_VolumeDown(position-minimum,step,maximum);
   return volume>0 && volume>=minimum-1e-9 ? volume : 0;
  }
double XPMM_StopRound(const double price,const double tick,const bool buy)
  {
   if(tick<=0 || !MathIsValidNumber(price) || price<=0) return 0;
   return (buy ? MathFloor(price/tick+1e-9) : MathCeil(price/tick-1e-9))*tick;
  }
bool XPMM_Tighter(const bool buy,const double candidate,const double old_sl,const double step)
  {
   if(candidate<=0 || !MathIsValidNumber(candidate)) return false;
   if(old_sl<=0) return true;
   return buy ? candidate>old_sl+1e-9 && candidate-old_sl+1e-9>=step
              : candidate<old_sl-1e-9 && old_sl-candidate+1e-9>=step;
  }
double XPMM_ProfitDistance(const bool buy,const double entry,const double bid,const double ask)
  { return buy ? bid-entry : entry-ask; }
double XPMM_BaseLots(const XPMM_CONFIG &c,const double equity,const double balance,
                    const double free_margin,const double base,const double loss_per_lot)
  {
   if(c.lot_mode==XPMM_FIXED_LOTS) return c.value;
   if(c.lot_mode==XPMM_CAPITAL_UNITS) return c.capital_unit>0 ? c.value*equity/c.capital_unit : 0;
   if(c.lot_mode==XPMM_EQUITY_STEPS)
      return c.capital_unit>0 ? MathMax(0,c.value+MathFloor((equity-base)/c.capital_unit)*c.lots_per_step) : 0;
   if(loss_per_lot<=0) return 0;
   if(c.lot_mode==XPMM_FIXED_CASH) return c.value/loss_per_lot;
   if(c.lot_mode==XPMM_PERCENT_BALANCE) return balance*c.value/100/loss_per_lot;
   if(c.lot_mode==XPMM_PERCENT_EQUITY) return equity*c.value/100/loss_per_lot;
   if(c.lot_mode==XPMM_PERCENT_FREE_MARGIN) return free_margin*c.value/100/loss_per_lot;
   if(c.lot_mode==XPMM_PROFIT_REINVEST)
      return MathMax(0,MathMin(equity,base+MathMax(0,balance-base)*c.reinvest_percent/100))*c.value/100/loss_per_lot;
   return 0;
  }
// 32-bit FNV-1a. Persisted key prefixes depend on it: never change the algorithm.
uint XPMM_Hash(const string text)
  {
   uint hash=2166136261;
   for(int x=0;x<StringLen(text);x++) hash=(hash^(uint)StringGetCharacter(text,x))*16777619;
   return hash;
  }
void XPMM_Unique(ulong &values[])
  {
   ArraySort(values); int count=0;
   for(int i=0;i<ArraySize(values);i++)
      if(count==0 || values[i]!=values[count-1]) values[count++]=values[i];
   ArrayResize(values,count);
  }
bool XPMM_ClosedBefore(const XPMM_COMPLETED &a,const XPMM_COMPLETED &b)
  { return a.at<b.at || (a.at==b.at && a.id<b.id); }
void XPMM_SortCompleted(XPMM_COMPLETED &items[],const int left,const int right)
  {
   if(left>=right) return;
   int i=left,j=right; XPMM_COMPLETED pivot=items[(left+right)/2];
   while(i<=j)
     {
      while(XPMM_ClosedBefore(items[i],pivot)) i++;
      while(XPMM_ClosedBefore(pivot,items[j])) j--;
      if(i<=j) { XPMM_COMPLETED swap=items[i]; items[i]=items[j]; items[j]=swap; i++; j--; }
     }
   if(left<j) XPMM_SortCompleted(items,left,j);
   if(i<right) XPMM_SortCompleted(items,i,right);
  }
datetime XPMM_Day(const datetime now,const int hour)
  {
   MqlDateTime d; TimeToStruct(now-hour*3600,d); d.hour=0; d.min=0; d.sec=0;
   return StructToTime(d)+hour*3600;
  }
// `second` of the server day inside one SymbolInfoSessionTrade() window. The window's date
// part is dropped but 24:00 (86400) stays the exclusive end; a window ending before it
// starts wraps past midnight.
bool XPMM_InSession(const long second,const datetime from,const datetime to)
  {
   long begin=(long)from%86400,end=(long)to-((long)from-begin);
   if(end<begin) end+=86400;
   return second>=begin && second<end;
  }
// Quotes can resume before orders are accepted (XM GOLD quotes from 01:00 but trades from
// 01:02 server time). True while the symbol's trade session is open at `when`; a day that
// publishes no session is left for the server to decide.
bool XPMM_TradeSessionOpen(const string symbol,const datetime when)
  {
   MqlDateTime t; TimeToStruct(when,t);
   long second=t.hour*3600+t.min*60+t.sec;
   datetime from,to; bool listed=false;
   for(uint i=0;SymbolInfoSessionTrade(symbol,(ENUM_DAY_OF_WEEK)t.day_of_week,i,from,to);i++)
     { listed=true; if(XPMM_InSession(second,from,to)) return true; }
   return !listed;
  }

class CXPMoneyManager
  {
private:
   XPMM_CONFIG m_c;
   XPMM_BE_STAGE m_be[]; XPMM_PARTIAL_STAGE m_partial[]; XPMM_R_STAGE m_rtrail[];
   XPMM_POSITION_STATE m_state[];
   string m_prefix; string m_reason; bool m_ready; bool m_tester;
   double m_base; double m_peak; double m_day_equity; double m_week_equity;
   datetime m_day; datetime m_week; datetime m_loss_until;
   int m_entries; int m_losses; double m_daily_realized;
   ulong m_entry_order; datetime m_last_entry_try; bool m_entry_uncertain;
   datetime m_entry_since; ulong m_entry_eligible;
   bool m_history_ok; bool m_dirty;
   bool m_day_locked; bool m_week_locked; bool m_dd_locked;
   bool m_sent; string m_owner_key; double m_owner_token; bool m_owned;
   datetime m_last_cancel;
   double m_cash_total; bool m_cash_known;
   double m_credit_total; bool m_credit_known;
   ulong m_cleanup[]; int m_cleanup_tries[]; bool m_swept;

   string Key(const ulong id,const string field) { return m_prefix+"."+(string)id+"."+field; }
   double Read(const string k,const double fallback)
     { return m_c.persist && !m_tester && GlobalVariableCheck(k) ? GlobalVariableGet(k) : fallback; }
   void Write(const string k,const double v)
     { if(m_c.persist && !m_tester) GlobalVariableSet(k,v); }
   void WriteTicket(const string k,const ulong v)
     { Write(k+"h",(double)(v>>32)); Write(k+"l",(double)(v&0xFFFFFFFF)); }
   ulong ReadTicket(const string k)
     { return ((ulong)Read(k+"h",0)<<32)|(ulong)Read(k+"l",0); }
   bool BrokerUncertain(const MqlTradeResult &r)
     { return r.retcode==0 || r.retcode==TRADE_RETCODE_TIMEOUT || r.retcode==TRADE_RETCODE_CONNECTION; }
   bool Uncertain(const MqlTradeResult &r) { return m_sent && BrokerUncertain(r); }
   double OwnerRead(const string field)
     { string k=m_owner_key+field; return GlobalVariableCheck(k) ? GlobalVariableGet(k) : 0; }
   void OwnerWrite(const string field,const double value)
     { string k=m_owner_key+field; if(!GlobalVariableCheck(k)) GlobalVariableTemp(k); GlobalVariableSet(k,value); }
   // A lock is stale only when its expert cannot still be running: its chart was closed,
   // the chart no longer runs an expert, or this expert replaced it on the same chart.
   bool OwnerStale(const double token)
     {
      if(token==0) return true;
      long chart=(long)(((ulong)OwnerRead(".ch")<<32)|(ulong)OwnerRead(".cl"));
      if(chart==0 || OwnerRead(".ea")!=1 ||
         (ENUM_PROGRAM_TYPE)MQLInfoInteger(MQL_PROGRAM_TYPE)!=PROGRAM_EXPERT) return false;
      if(chart==ChartID()) return true;
      return ChartSymbol(chart)=="" || ChartGetString(chart,CHART_EXPERT_NAME)=="";
     }
   bool AcquireOwner()
     {
      if(!GlobalVariableCheck(m_owner_key)) GlobalVariableTemp(m_owner_key);
      ulong seed=((ulong)ChartID()*(ulong)2654435761)^(GetMicrosecondCount()<<12)^(ulong)TimeLocal();
      m_owner_token=(double)((seed&0x1FFFFFFFFFFFFF)|1); // non-zero and exact in a double
      double current=GlobalVariableGet(m_owner_key);
      if(!GlobalVariableSetOnCondition(m_owner_key,m_owner_token,0))
        {
         if(!OwnerStale(current) || !GlobalVariableSetOnCondition(m_owner_key,m_owner_token,current)) return false;
         PrintFormat("XPMM: replaced a stale management lock for %s magic %I64u.",m_c.symbol,m_c.magic);
        }
      ulong chart=(ulong)ChartID();
      OwnerWrite(".ch",(double)(chart>>32)); OwnerWrite(".cl",(double)(chart&0xFFFFFFFF));
      OwnerWrite(".ea",(ENUM_PROGRAM_TYPE)MQLInfoInteger(MQL_PROGRAM_TYPE)==PROGRAM_EXPERT ? 1 : 0);
      m_owned=true; return true;
     }
   void ReleaseOwner()
     { if(m_owned) GlobalVariableSetOnCondition(m_owner_key,0,m_owner_token); m_owned=false; }
   bool Fail(const string reason) { m_reason=reason; return false; }
   bool FiniteNonNegative(const double v) { return MathIsValidNumber(v) && v>=0; }
   double PointSize() { return SymbolInfoDouble(m_c.symbol,SYMBOL_POINT); }
   double TickSize() { return SymbolInfoDouble(m_c.symbol,SYMBOL_TRADE_TICK_SIZE); }
   bool Buy(const int i) { return m_state[i].side==POSITION_TYPE_BUY; }
   void Calendar()
     {
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      datetime day=XPMM_Day(TimeCurrent(),m_c.reset_hour);
      MqlDateTime d; TimeToStruct(day-m_c.reset_hour*3600,d);
      datetime week=day-((d.day_of_week+6)%7)*86400;
      bool changed=false;
      if(day!=m_day) { m_day=day; m_day_equity=equity; m_day_locked=false; m_dirty=true; changed=true; }
      if(week!=m_week) { m_week=week; m_week_equity=equity; m_week_locked=false; changed=true; }
      if(changed) SaveAccount();
     }
   bool Scope(const string symbol,const long magic)
     { return symbol==m_c.symbol && (ulong)magic==m_c.magic; }
   int Index(const ulong id)
     { for(int i=0;i<ArraySize(m_state);i++) if(m_state[i].id==id) return i; return -1; }
   void Save(const int i)
     {
      ulong id=m_state[i].id;
      Write(Key(id,"e"),m_state[i].entry); Write(Key(id,"r"),m_state[i].risk);
      Write(Key(id,"v"),m_state[i].original_volume); Write(Key(id,"f"),m_state[i].favorable);
      Write(Key(id,"p"),(double)m_state[i].partial_mask);
      Write(Key(id,"s"),m_state[i].side); Write(Key(id,"close"),m_state[i].closing ? 1 : 0);
      // Split ulong tickets into exact 32-bit halves for terminal global variables.
      WriteTicket(Key(id,"order"),m_state[i].pending_order);
      Write(Key(id,"before"),m_state[i].pending_before);
      Write(Key(id,"target"),m_state[i].pending_target);
      Write(Key(id,"stage"),m_state[i].pending_stage);
      Write(Key(id,"uncertain"),m_state[i].uncertain ? 1 : 0);
      Write(Key(id,"since"),(double)m_state[i].since);
     }
   void SaveAccount()
     {
      Write(Key(0,"base"),m_base); Write(Key(0,"peak"),m_peak);
      Write(Key(0,"day"),(double)m_day); Write(Key(0,"week"),(double)m_week);
      Write(Key(0,"de"),m_day_equity); Write(Key(0,"we"),m_week_equity);
      Write(Key(0,"cool"),(double)m_loss_until);
      Write(Key(0,"dl"),m_day_locked ? 1 : 0); Write(Key(0,"wl"),m_week_locked ? 1 : 0);
      Write(Key(0,"ddl"),m_dd_locked ? 1 : 0); Write(Key(0,"eu"),m_entry_uncertain ? 1 : 0);
      WriteTicket(Key(0,"entry"),m_entry_order); Write(Key(0,"es"),(double)m_entry_since);
      Write(Key(0,"cash"),m_cash_total); Write(Key(0,"cashknown"),m_cash_known ? 1 : 0);
      Write(Key(0,"credit"),m_credit_total); Write(Key(0,"creditknown"),m_credit_known ? 1 : 0);
     }
   // Returns false while broker history is not yet conclusive, so Track(true) retries later.
   bool RecoverRisk(const int i)
     {
      // Only initialization/explicit Refresh/event forwarding calls this history path.
      if(!HistorySelectByPosition(m_state[i].id)) return false;
      double first_price=0,first_sl=0,total_in=0,commission=0;
      ulong first_order=0; bool multiple_orders=false;
      long first_side=-1;
      for(int d=0;d<HistoryDealsTotal();d++)
        {
         ulong deal=HistoryDealGetTicket(d);
         if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_INOUT)
           { m_state[i].risk=0; return true; } // reversal cannot inherit original R
         if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY)!=DEAL_ENTRY_IN) continue;
         if(first_price==0)
           {
            first_price=HistoryDealGetDouble(deal,DEAL_PRICE);
            first_side=HistoryDealGetInteger(deal,DEAL_TYPE)==DEAL_TYPE_BUY ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
            first_order=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
            // The fill can be reported before its order reaches history.
            if(!HistoryOrderGetDouble(first_order,ORDER_SL,first_sl)) return false;
           }
         if((ulong)HistoryDealGetInteger(deal,DEAL_ORDER)!=first_order) multiple_orders=true;
         total_in+=HistoryDealGetDouble(deal,DEAL_VOLUME);
         commission+=HistoryDealGetDouble(deal,DEAL_COMMISSION)+HistoryDealGetDouble(deal,DEAL_FEE);
        }
      if(first_price==0) return false; // entry deal not synchronized yet
      m_state[i].costs_cash=MathMax(0,-commission);
      if(first_side!=m_state[i].side) { m_state[i].risk=0; return true; }
      if(total_in>0) m_state[i].original_volume=total_in;
      // Position-average entry is used after additions; original R remains unavailable
      // for merged netting additions, whose risk is not a single initial stop.
      if(multiple_orders) { m_state[i].risk=0; return true; }
      if(first_sl>0 && (Buy(i) ? first_sl<m_state[i].entry : first_sl>m_state[i].entry))
         m_state[i].risk=MathAbs(m_state[i].entry-first_sl);
      return true;
     }
   // Active library order for a position (an in-flight close), or zero.
   ulong PositionOrder(const ulong id)
     {
      for(int o=0;o<OrdersTotal();o++)
        {
         ulong order=OrderGetTicket(o);
         if((ulong)OrderGetInteger(ORDER_POSITION_ID)==id &&
            Scope(OrderGetString(ORDER_SYMBOL),OrderGetInteger(ORDER_MAGIC))) return order;
        }
      return 0;
     }
   // Active market order in scope that is not closing a tracked position, or zero.
   ulong EntryOrder()
     {
      for(int o=OrdersTotal()-1;o>=0;o--)
        {
         ulong order=OrderGetTicket(o);
         if(!Scope(OrderGetString(ORDER_SYMBOL),OrderGetInteger(ORDER_MAGIC))) continue;
         long type=OrderGetInteger(ORDER_TYPE);
         if(type!=ORDER_TYPE_BUY && type!=ORDER_TYPE_SELL) continue;
         ulong position=(ulong)OrderGetInteger(ORDER_POSITION_ID);
         if(position==0 || Index(position)<0) return order;
        }
      return 0;
     }
   void Track(const bool recover)
     {
      for(int p=0;p<PositionsTotal();p++)
        {
         ulong ticket=PositionGetTicket(p);
         if(!Scope(PositionGetString(POSITION_SYMBOL),PositionGetInteger(POSITION_MAGIC))) continue;
         ulong id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
         int i=Index(id);
         if(i>=0)
           {
            m_state[i].ticket=ticket;
            if(m_state[i].side!=PositionGetInteger(POSITION_TYPE) ||
               MathAbs(m_state[i].entry-PositionGetDouble(POSITION_PRICE_OPEN))>TickSize()/2)
              {
               bool reversal=m_state[i].side!=PositionGetInteger(POSITION_TYPE);
               m_state[i].entry=PositionGetDouble(POSITION_PRICE_OPEN);
               m_state[i].side=PositionGetInteger(POSITION_TYPE);
               m_state[i].risk=0; m_state[i].external_stop=0; m_state[i].risk_known=false;
               if(reversal) { m_state[i].favorable=m_state[i].entry; m_state[i].partial_mask=0; }
               if(recover) m_state[i].risk_known=RecoverRisk(i);
               Save(i);
              }
            else if(recover && !m_state[i].risk_known)
              { // history was not conclusive earlier; retry until it is
               if(RecoverRisk(i)) { m_state[i].risk_known=true; Save(i); }
              }
            continue;
           }
         i=ArraySize(m_state); ArrayResize(m_state,i+1,16); ZeroMemory(m_state[i]);
         m_state[i].id=id; m_state[i].ticket=ticket;
         m_state[i].side=PositionGetInteger(POSITION_TYPE);
         m_state[i].entry=PositionGetDouble(POSITION_PRICE_OPEN);
         m_state[i].opened=(datetime)PositionGetInteger(POSITION_TIME);
         m_state[i].original_volume=Read(Key(id,"v"),PositionGetDouble(POSITION_VOLUME));
         m_state[i].risk=Read(Key(id,"r"),0);
         if(Read(Key(id,"s"),m_state[i].side)!=m_state[i].side ||
            MathAbs(Read(Key(id,"e"),m_state[i].entry)-m_state[i].entry)>TickSize()/2) m_state[i].risk=0;
         m_state[i].favorable=Read(Key(id,"f"),m_state[i].entry);
         m_state[i].partial_mask=(uint)Read(Key(id,"p"),0);
         m_state[i].closing=Read(Key(id,"close"),0)!=0;
         m_state[i].uncertain=Read(Key(id,"uncertain"),0)!=0;
         m_state[i].pending_stage=(int)Read(Key(id,"stage"),-1);
         m_state[i].pending_before=Read(Key(id,"before"),0);
         m_state[i].pending_target=Read(Key(id,"target"),0);
         m_state[i].pending_order=ReadTicket(Key(id,"order"));
         m_state[i].since=(datetime)Read(Key(id,"since"),0);
         // Recover any active library close order by position identifier.
         ulong order=PositionOrder(id);
         if(order!=0) { m_state[i].pending_order=order; m_state[i].uncertain=false; m_state[i].since=TimeCurrent(); }
         if(recover) m_state[i].risk_known=RecoverRisk(i);
         Save(i);
        }
      // Remove disappeared positions; their persisted state is deleted once history proves closure.
      for(int i=ArraySize(m_state)-1;i>=0;i--)
        {
         if(PositionSelectByTicket(m_state[i].ticket)) continue;
         QueueCleanup(m_state[i].id);
         for(int j=i;j<ArraySize(m_state)-1;j++) m_state[j]=m_state[j+1];
         ArrayResize(m_state,ArraySize(m_state)-1);
        }
     }
   void QueueCleanup(const ulong id)
     {
      if(id==0 || !m_c.persist || m_tester) return;
      for(int k=0;k<ArraySize(m_cleanup);k++) if(m_cleanup[k]==id) return;
      int n=ArraySize(m_cleanup); ArrayResize(m_cleanup,n+1,64); ArrayResize(m_cleanup_tries,n+1,64);
      m_cleanup[n]=id; m_cleanup_tries[n]=0;
     }
   void DropCleanup(const int k)
     {
      int last=ArraySize(m_cleanup)-1;
      m_cleanup[k]=m_cleanup[last]; m_cleanup_tries[k]=m_cleanup_tries[last];
      ArrayResize(m_cleanup,last); ArrayResize(m_cleanup_tries,last);
     }
   // History proves closure when the position's buy and sell deal volumes net to zero.
   bool PositionClosed(const ulong id)
     {
      if(!HistorySelectByPosition(id)) return false;
      double net=0; int deals=0;
      for(int d=0;d<HistoryDealsTotal();d++)
        {
         ulong deal=HistoryDealGetTicket(d);
         long type=HistoryDealGetInteger(deal,DEAL_TYPE);
         if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
         double volume=HistoryDealGetDouble(deal,DEAL_VOLUME);
         net+=type==DEAL_TYPE_BUY ? volume : -volume; deals++;
        }
      return deals>=2 && MathAbs(net)<1e-8;
     }
   // Once per Configure: queue persisted positions closed while this EA was not running.
   void Sweep()
     {
      m_swept=true;
      string head=m_prefix+".";
      int length=StringLen(head);
      for(int g=GlobalVariablesTotal()-1;g>=0;g--)
        {
         string name=GlobalVariableName(g);
         if(StringFind(name,head)!=0) continue;
         int dot=StringFind(name,".",length);
         if(dot<=length || StringSubstr(name,dot)!=".e") continue; // one marker key per position
         ulong id=(ulong)StringToInteger(StringSubstr(name,length,dot-length));
         if(id!=0 && Index(id)<0) QueueCleanup(id);
        }
     }
   void Cleanup()
     {
      if(!m_c.persist || m_tester) return;
      if(!m_swept) Sweep();
      int checked=0;
      for(int k=ArraySize(m_cleanup)-1;k>=0 && checked<XPMM_CLEANUP_BATCH;k--)
        {
         ulong id=m_cleanup[k];
         if(Index(id)>=0) { DropCleanup(k); continue; }
         checked++;
         if(PositionClosed(id)) { GlobalVariablesDeleteAll(m_prefix+"."+(string)id+"."); DropCleanup(k); }
         else if(++m_cleanup_tries[k]>=XPMM_CLEANUP_TRIES) DropCleanup(k); // left to the 4-week expiry
        }
     }
   bool NettingSafe()
     {
      if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING) return true;
      if(!m_c.exclusive_netting) return Fail("NETTING_REQUIRES_EXCLUSIVE_SYMBOL");
      if(PositionSelect(m_c.symbol) && (ulong)PositionGetInteger(POSITION_MAGIC)!=m_c.magic)
         return Fail("FOREIGN_NETTING_POSITION");
      for(int o=0;o<OrdersTotal();o++)
        {
         OrderGetTicket(o);
         if(OrderGetString(ORDER_SYMBOL)==m_c.symbol && (ulong)OrderGetInteger(ORDER_MAGIC)!=m_c.magic)
            return Fail("FOREIGN_NETTING_ORDER");
        }
      return true;
     }
   // 1 = active, 0 = final (in history, whatever its state), -1 = unknown: not yet
   // synchronized or never created. Unknown waits are bounded by reconcile_seconds.
   int OrderStatus(const ulong order)
     {
      if(order==0) return 0;
      if(OrderSelect(order)) return 1;
      if(HistoryOrderSelect(order)) return 0;
      return -1;
     }
   // Bounded wait for an ambiguous outcome: reconcile_seconds of server time, then, outside
   // the tester, a connected grace seen on two calls so a reconnect can resynchronize first.
   bool WaitOver(datetime &since,ulong &eligible)
     {
      if(m_c.reconcile_seconds<=0) return false;
      datetime now=TimeCurrent();
      if(since<=0 || since>now) { since=now; eligible=0; return false; }
      if(now-since<m_c.reconcile_seconds) return false;
      if(m_tester) return true;
      if(!TerminalInfoInteger(TERMINAL_CONNECTED)) { eligible=0; return false; }
      ulong clock=GetTickCount64();
      if(eligible==0) { eligible=clock; return false; }
      return clock-eligible>=XPMM_RECONNECT_GRACE_MS;
     }
   bool PositionWaitOver(const int i)
     {
      datetime since=m_state[i].since; ulong eligible=m_state[i].eligible;
      bool over=WaitOver(since,eligible);
      if(since!=m_state[i].since) { m_state[i].since=since; Write(Key(m_state[i].id,"since"),(double)since); }
      m_state[i].eligible=eligible;
      return over;
     }
   // True while an earlier library entry may still be executing; sets the reason.
   bool EntryWaiting()
     {
      if(m_entry_uncertain)
        {
         datetime since=m_entry_since;
         bool over=WaitOver(m_entry_since,m_entry_eligible);
         if(since!=m_entry_since) Write(Key(0,"es"),(double)m_entry_since);
         if(!over) { m_reason="ENTRY_OUTCOME_UNCERTAIN"; return true; }
         // No broker reply arrived: adopt any in-flight entry order, else trust the terminal.
         m_entry_uncertain=false;
         m_entry_order=EntryOrder();
         if(m_entry_order!=0) { m_entry_since=TimeCurrent(); m_entry_eligible=0; }
         SaveAccount();
         Track(true);
         PrintFormat("XPMM: entry had no broker reply for %ds; %s.",m_c.reconcile_seconds,
                     m_entry_order!=0 ? "tracking its active order" : "positions re-read from the terminal");
        }
      if(m_entry_order!=0)
        {
         int status=OrderStatus(m_entry_order);
         if(status>0 || (status<0 && !WaitOver(m_entry_since,m_entry_eligible)))
           { m_reason="ENTRY_PENDING"; return true; }
         m_entry_order=0; m_entry_since=0; m_entry_eligible=0;
         WriteTicket(Key(0,"entry"),0); Write(Key(0,"es"),0);
        }
      return false;
     }
   // Explicit reasons for live permission problems that OrderCheck reports less clearly.
   bool TradePermitted(const ENUM_ORDER_TYPE type)
     {
      if(!m_tester)
        {
         if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return Fail("TERMINAL_DISCONNECTED");
         if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)) return Fail("TERMINAL_ALGO_TRADING_DISABLED");
         if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return Fail("PROGRAM_ALGO_TRADING_DISABLED");
         if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) return Fail("ACCOUNT_TRADING_DISABLED");
         if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT)) return Fail("ACCOUNT_EXPERT_TRADING_DISABLED");
        }
      ENUM_SYMBOL_TRADE_MODE mode=(ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(m_c.symbol,SYMBOL_TRADE_MODE);
      if(mode==SYMBOL_TRADE_MODE_DISABLED || mode==SYMBOL_TRADE_MODE_CLOSEONLY) return Fail("SYMBOL_TRADE_DISABLED");
      if((mode==SYMBOL_TRADE_MODE_LONGONLY && type==ORDER_TYPE_SELL) ||
         (mode==SYMBOL_TRADE_MODE_SHORTONLY && type==ORDER_TYPE_BUY)) return Fail("SYMBOL_DIRECTION_DISABLED");
      return true;
     }
   ENUM_ORDER_TYPE_FILLING Filling()
     {
      long flags=SymbolInfoInteger(m_c.symbol,SYMBOL_FILLING_MODE);
      if((flags&SYMBOL_FILLING_FOK)!=0) return ORDER_FILLING_FOK;
      if((flags&SYMBOL_FILLING_IOC)!=0) return ORDER_FILLING_IOC;
      // Request/Instant execution fills market orders FOK; RETURN suits exchange execution.
      ENUM_SYMBOL_TRADE_EXECUTION exec=(ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(m_c.symbol,SYMBOL_TRADE_EXEMODE);
      if(exec==SYMBOL_TRADE_EXECUTION_REQUEST || exec==SYMBOL_TRADE_EXECUTION_INSTANT) return ORDER_FILLING_FOK;
      return ORDER_FILLING_RETURN;
     }
   bool Send(MqlTradeRequest &q,MqlTradeResult &r)
     {
      m_sent=false;
      MqlTradeCheckResult check; ZeroMemory(check); ZeroMemory(r);
      if(!OrderCheck(q,check)) return Fail("ORDER_CHECK: "+check.comment);
      m_sent=true;
      if(!OrderSend(q,r)) return Fail("ORDER_SEND: "+r.comment);
      if(r.retcode!=TRADE_RETCODE_DONE && r.retcode!=TRADE_RETCODE_DONE_PARTIAL && r.retcode!=TRADE_RETCODE_PLACED)
         return Fail("SERVER: "+(string)r.retcode+" "+r.comment);
      m_reason=r.retcode==TRADE_RETCODE_PLACED ? "ACCEPTED_PENDING" : "EXECUTED";
      return true;
     }
   bool CancelPending()
     {
      bool found=false,attempted=false;
      for(int o=OrdersTotal()-1;o>=0;o--)
        {
         ulong ticket=OrderGetTicket(o);
         if(!Scope(OrderGetString(ORDER_SYMBOL),OrderGetInteger(ORDER_MAGIC)) ||
            OrderGetInteger(ORDER_TYPE)<ORDER_TYPE_BUY_LIMIT) continue;
         found=true;
         if(TimeCurrent()<m_last_cancel+m_c.retry_seconds) continue;
         MqlTradeRequest q; MqlTradeResult r; ZeroMemory(q);
         q.action=TRADE_ACTION_REMOVE; q.order=ticket; q.symbol=m_c.symbol; q.magic=m_c.magic;
         attempted=true;
         Send(q,r);
        }
      if(attempted) m_last_cancel=TimeCurrent();
      return found;
     }
   double UnitValue(const int i,const XPMM_UNIT unit,const double distance,const double cash)
     {
      if(unit==XPMM_POINTS) return distance/PointSize();
      if(unit==XPMM_R) return m_state[i].risk>0 ? distance/m_state[i].risk : -DBL_MAX;
      if(unit==XPMM_ATR) return m_state[i].atr>0 ? distance/m_state[i].atr : -DBL_MAX;
      return cash;
     }
   bool ValidMove(const int i,const double sl,const MqlTick &tick)
     {
      double point=PointSize();
      double stops=SymbolInfoInteger(m_c.symbol,SYMBOL_TRADE_STOPS_LEVEL)*point;
      double freeze=SymbolInfoInteger(m_c.symbol,SYMBOL_TRADE_FREEZE_LEVEL)*point;
      double distance=Buy(i) ? tick.bid-sl : sl-tick.ask;
      if(distance<MathMax(stops,TickSize())-1e-9 || (freeze>0 && distance<=freeze+1e-9)) return false;
      double old=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
      if(freeze>0 && ((old>0 && (Buy(i) ? tick.bid-old : old-tick.ask)<=freeze) ||
         (tp>0 && (Buy(i) ? tp-tick.bid : tick.ask-tp)<=freeze))) return false;
      return true;
     }
   void Candidate(const int i,const double price,const double min_step,const MqlTick &tick,double &best)
     {
      double sl=XPMM_StopRound(price,TickSize(),Buy(i));
      double old=PositionGetDouble(POSITION_SL);
      if(!XPMM_Tighter(Buy(i),sl,old,min_step) || !ValidMove(i,sl,tick)) return;
      if(best==0 || (Buy(i) ? sl>best : sl<best)) best=sl;
     }
   bool Pending(const int i)
     {
      if(m_state[i].uncertain)
        {
         if(!PositionWaitOver(i)) return true;
         // No broker reply arrived: adopt any in-flight close order, else let volumes decide.
         m_state[i].uncertain=false;
         ulong order=PositionOrder(m_state[i].id);
         if(order!=0) { m_state[i].pending_order=order; m_state[i].since=TimeCurrent(); m_state[i].eligible=0; }
         PrintFormat("XPMM: position %I64u had no broker reply for %ds; %s.",m_state[i].id,m_c.reconcile_seconds,
                     order!=0 ? "tracking its active close order" : "resuming from the terminal's volume");
         Save(i);
        }
      if(m_state[i].pending_order!=0)
        {
         int status=OrderStatus(m_state[i].pending_order);
         if(status>0) return true;
         if(status<0 && !PositionWaitOver(i)) return true;
         if(status==0 && m_state[i].pending_before>0)
           {
            double filled=HistoryOrderGetDouble(m_state[i].pending_order,ORDER_VOLUME_INITIAL)-
                          HistoryOrderGetDouble(m_state[i].pending_order,ORDER_VOLUME_CURRENT);
            double observed=m_state[i].pending_before-PositionGetDouble(POSITION_VOLUME);
            // Final order history can arrive before the corresponding position update.
            // Wait (bounded) for the filled volume to appear in the position cache before retrying.
            if(filled>0 && observed+1e-9<MathMin(filled,m_state[i].pending_target) && !PositionWaitOver(i))
               return true;
           }
        }
      m_state[i].pending_order=0;
      bool waited=m_state[i].since!=0;
      m_state[i].since=0; m_state[i].eligible=0;
      if(m_state[i].pending_before>0)
        {
         double now=PositionGetDouble(POSITION_VOLUME);
         if(m_state[i].pending_before-now+1e-9>=m_state[i].pending_target)
           {
            if(m_state[i].pending_stage>=0)
               m_state[i].partial_mask|=((uint)1<<m_state[i].pending_stage);
            m_state[i].pending_target=0;
           }
         else
           { // partial fill: retry only the unfilled remainder
            m_state[i].pending_target=MathMax(0,m_state[i].pending_target-(m_state[i].pending_before-now));
           }
         m_state[i].pending_before=0;
         Save(i);
        }
      else if(waited) Write(Key(m_state[i].id,"since"),0);
      return false;
     }
   bool CloseVolume(const int i,const double requested,const int stage)
     {
      if(TimeCurrent()<m_state[i].last_try+m_c.retry_seconds) return false;
      if(!PositionSelectByTicket(m_state[i].ticket)) return false;
      double before=PositionGetDouble(POSITION_VOLUME);
      double step=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_STEP);
      double minimum=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_MIN);
      double maximum=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_MAX);
      // Full exits send the position volume (chunked by the broker maximum); partial
      // stages must leave a tradable remainder or they are skipped instead of retried forever.
      double volume=stage<0 ? (maximum>0 && before>maximum ? maximum : before)
                            : XPMM_CloseVolume(before,requested,step,minimum,maximum);
      if(volume<=0)
        {
         if(stage<0) { m_state[i].last_try=TimeCurrent(); return Fail("INVALID_CLOSE_VOLUME"); }
         m_state[i].partial_mask|=((uint)1<<stage);
         m_state[i].pending_target=0; m_state[i].pending_before=0;
         Save(i);
         PrintFormat("XPMM: partial stage %d skipped for position %I64u: %.2f lots cannot be split above the %.2f lot minimum.",
                     stage,m_state[i].id,before,minimum);
         return Fail("PARTIAL_SKIPPED_MIN_VOLUME");
        }
      MqlTick tick; if(!SymbolInfoTick(m_c.symbol,tick)) return false;
      MqlTradeRequest q; MqlTradeResult r; ZeroMemory(q);
      q.action=TRADE_ACTION_DEAL; q.position=m_state[i].ticket; q.symbol=m_c.symbol; q.magic=m_c.magic;
      q.type=Buy(i) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY; q.price=Buy(i) ? tick.bid : tick.ask;
      q.volume=volume; q.deviation=m_c.deviation_points; q.type_filling=Filling(); q.comment="XPMM exit";
      m_state[i].last_try=TimeCurrent();
      double previous_target=m_state[i].pending_target; int previous_stage=m_state[i].pending_stage;
      // Persist intention before sending: a crash between send and response fails closed.
      m_state[i].uncertain=true; m_state[i].since=TimeCurrent(); m_state[i].eligible=0;
      m_state[i].pending_before=before; m_state[i].pending_target=volume; m_state[i].pending_stage=stage;
      Save(i);
      if(!m_tester && m_c.persist) GlobalVariablesFlush();
      if(!Send(q,r))
        {
         if(!Uncertain(r))
           { // definitive rejection: keep any committed remainder for the next attempt
            m_state[i].uncertain=false; m_state[i].since=0; m_state[i].pending_before=0;
            m_state[i].pending_target=previous_target; m_state[i].pending_stage=previous_stage;
            Save(i);
           }
         return false;
        }
      m_state[i].uncertain=(r.retcode==TRADE_RETCODE_PLACED && r.order==0);
      m_state[i].pending_order=r.order;
      Save(i); return true;
     }

public:
   CXPMoneyManager() { m_ready=false; m_entry_order=0; m_last_entry_try=0; m_entry_uncertain=false; m_entry_since=0; m_entry_eligible=0; m_history_ok=false; m_dirty=true; m_owned=false; m_sent=false; m_last_cancel=0; m_swept=false; }
   ~CXPMoneyManager() { ReleaseOwner(); }
   string Reason() { return m_reason; }
   bool Configure(const XPMM_CONFIG &config)
     {
      ReleaseOwner(); m_ready=false; m_c=config; m_tester=(bool)MQLInfoInteger(MQL_TESTER);
      if(m_c.symbol=="" || m_c.instance=="" || !SymbolSelect(m_c.symbol,true)) return Fail("INVALID_IDENTITY");
      double values[]={m_c.value,m_c.capital_unit,m_c.base_capital,m_c.lots_per_step,m_c.reinvest_percent,
         m_c.max_lots,m_c.max_risk_cash,m_c.max_risk_percent,m_c.max_total_risk_percent,m_c.max_margin_percent,
         m_c.max_spread_points,m_c.daily_loss_percent,m_c.weekly_loss_percent,m_c.max_drawdown_percent,
         m_c.daily_profit_cash,m_c.basket_profit_cash,m_c.basket_loss_cash,m_c.reduce_risk_at_dd,
         m_c.reduced_risk_factor,m_c.estimated_exit_commission_per_lot,m_c.stop_value,m_c.tp_value,
         m_c.trail_trigger,m_c.trail_distance,m_c.trail_step_points,m_c.giveback_percent};
      for(int i=0;i<ArraySize(values);i++) if(!FiniteNonNegative(values[i])) return Fail("INVALID_NUMERIC_SETTING");
      if(m_c.value<=0 || m_c.reset_hour<0 || m_c.reset_hour>23 || m_c.retry_seconds<1 ||
         m_c.deviation_points<0 || m_c.max_positions<0 || m_c.max_entries_day<0 || m_c.max_losses<0 ||
         m_c.loss_cooldown_seconds<0 || m_c.max_hold_seconds<0 || m_c.reconcile_seconds<0 || m_c.reinvest_percent>100 ||
         m_c.giveback_percent>=100 || m_c.reduced_risk_factor>1 ||
         m_c.max_risk_percent>100 || m_c.max_total_risk_percent>100 ||
         m_c.daily_loss_percent>100 || m_c.weekly_loss_percent>100 || m_c.max_drawdown_percent>100 ||
         m_c.lot_mode<XPMM_FIXED_LOTS || m_c.lot_mode>XPMM_PROFIT_REINVEST ||
         m_c.stop_mode<XPMM_STOP_EXTERNAL || m_c.stop_mode>XPMM_STOP_PERCENT ||
         m_c.tp_mode<XPMM_TP_OFF || m_c.tp_mode>XPMM_TP_R ||
         m_c.trail_mode<XPMM_TRAIL_OFF || m_c.trail_mode>XPMM_TRAIL_GIVEBACK ||
         m_c.trail_trigger_unit<XPMM_POINTS || m_c.trail_trigger_unit>XPMM_CASH)
         return Fail("INVALID_CONFIGURATION");
      if((m_c.lot_mode==XPMM_CAPITAL_UNITS || m_c.lot_mode==XPMM_EQUITY_STEPS) && m_c.capital_unit<=0)
         return Fail("CAPITAL_UNIT_REQUIRED");
      if(m_c.lot_mode==XPMM_PROFIT_REINVEST && m_c.value>100) return Fail("RISK_PERCENT_OUT_OF_RANGE");
      if(m_c.max_losses>0 && m_c.loss_cooldown_seconds==0) return Fail("LOSS_COOLDOWN_REQUIRED");
      if(m_c.stop_mode!=XPMM_STOP_EXTERNAL && m_c.stop_value<=0) return Fail("STOP_DISTANCE_REQUIRED");
      if(m_c.tp_mode>=XPMM_TP_POINTS && m_c.tp_value<=0) return Fail("TP_DISTANCE_REQUIRED");
      if(m_c.require_tp && m_c.tp_mode==XPMM_TP_OFF) return Fail("TP_REQUIRED");
      if((m_c.trail_mode==XPMM_TRAIL_FIXED || m_c.trail_mode==XPMM_TRAIL_ATR ||
          m_c.trail_mode==XPMM_TRAIL_CHANDELIER) && m_c.trail_distance<=0) return Fail("TRAIL_DISTANCE_REQUIRED");
      if(m_c.reconcile_seconds>0 && m_c.reconcile_seconds<XPMM_MIN_RECONCILE_SECONDS) return Fail("RECONCILE_TOO_SHORT");
      if(PointSize()<=0 || TickSize()<=0 || SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_STEP)<=0) return Fail("SYMBOL_DATA_UNAVAILABLE");
      string identity=(string)AccountInfoInteger(ACCOUNT_LOGIN)+"|"+AccountInfoString(ACCOUNT_SERVER)+"|"+
         m_c.symbol+"|"+(string)m_c.magic+"|"+m_c.instance;
      m_prefix="XPMM1."+(string)XPMM_Hash(identity);
      // One active manager for each symbol+magic in this terminal. Shared budgets
      // across different magic numbers/terminals require an account coordinator.
      string scope=(string)AccountInfoInteger(ACCOUNT_LOGIN)+"|"+AccountInfoString(ACCOUNT_SERVER)+"|"+m_c.symbol+"|"+(string)m_c.magic;
      m_owner_key="XPMMowner."+(string)XPMM_Hash(scope);
      if(!m_tester && !AcquireOwner()) return Fail("MANAGEMENT_SCOPE_ALREADY_OWNED");
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      m_base=Read(Key(0,"base"),m_c.base_capital>0 ? m_c.base_capital : equity);
      m_peak=Read(Key(0,"peak"),equity);
      m_day=(datetime)Read(Key(0,"day"),0); m_week=(datetime)Read(Key(0,"week"),0);
      m_day_equity=Read(Key(0,"de"),equity); m_week_equity=Read(Key(0,"we"),equity);
      m_loss_until=(datetime)Read(Key(0,"cool"),0);
      m_cash_total=Read(Key(0,"cash"),0); m_cash_known=Read(Key(0,"cashknown"),0)!=0;
      m_credit_total=Read(Key(0,"credit"),0); m_credit_known=Read(Key(0,"creditknown"),0)!=0;
      m_day_locked=Read(Key(0,"dl"),0)!=0; m_week_locked=Read(Key(0,"wl"),0)!=0;
      m_dd_locked=Read(Key(0,"ddl"),0)!=0; m_entry_uncertain=Read(Key(0,"eu"),0)!=0;
      m_entries=0; m_losses=0; m_daily_realized=0; m_entry_order=ReadTicket(Key(0,"entry"));
      m_entry_since=(datetime)Read(Key(0,"es"),0); m_entry_eligible=0;
      m_dirty=true; m_history_ok=false;
      ArrayResize(m_state,0); ArrayResize(m_be,0); ArrayResize(m_partial,0); ArrayResize(m_rtrail,0);
      ArrayResize(m_cleanup,0); ArrayResize(m_cleanup_tries,0); m_swept=false;
      if(!NettingSafe()) { ReleaseOwner(); return false; }
      m_ready=true; Refresh(); m_reason="OK"; return true;
     }
   bool AddBreakEven(const XPMM_BE_STAGE &s)
     {
      if(s.unit<XPMM_POINTS || s.unit>XPMM_CASH || !FiniteNonNegative(s.trigger) ||
         !FiniteNonNegative(s.lock_points) || !FiniteNonNegative(s.lock_r)) return Fail("INVALID_BE_STAGE");
      int n=ArraySize(m_be); ArrayResize(m_be,n+1); m_be[n]=s; return true;
     }
   bool AddPartial(const XPMM_PARTIAL_STAGE &s)
     {
      if(ArraySize(m_partial)>=24 || s.unit<XPMM_POINTS || s.unit>XPMM_CASH ||
         !FiniteNonNegative(s.trigger) || !MathIsValidNumber(s.percent_original) || s.percent_original<=0 || s.percent_original>=100)
         return Fail("INVALID_PARTIAL_STAGE");
      double sum=s.percent_original; for(int i=0;i<ArraySize(m_partial);i++) sum+=m_partial[i].percent_original;
      if(sum>=100) return Fail("PARTIAL_STAGES_MUST_LEAVE_REMAINDER");
      int n=ArraySize(m_partial); ArrayResize(m_partial,n+1); m_partial[n]=s; return true;
     }
   bool AddRTrail(const XPMM_R_STAGE &s)
     {
      if(!FiniteNonNegative(s.trigger_r) || !FiniteNonNegative(s.lock_r) || s.lock_r>=s.trigger_r)
         return Fail("INVALID_R_TRAIL_STAGE");
      int n=ArraySize(m_rtrail); ArrayResize(m_rtrail,n+1); m_rtrail[n]=s; return true;
     }
   // Heavy recovery/history work: call on initialization and closed bars, never every tick.
   void Refresh()
     {
      if(!m_ready) return;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      datetime previous_day=m_day,previous_week=m_week;
      Calendar();
      Track(true);
      Cleanup();
      if(!m_dirty && m_history_ok)
        { if(equity>m_peak) { m_peak=equity; Write(Key(0,"peak"),m_peak); } return; }
      m_entries=0; m_daily_realized=0; m_losses=0;
      // The day of margin keeps deals stamped after the last quote inside the selection.
      m_history_ok=HistorySelect(0,TimeCurrent()+86400);
      if(!m_history_ok) { m_reason="HISTORY_UNAVAILABLE"; return; }
      // Closed-trade statistics feed only the daily-entry, loss-streak and daily-profit locks.
      bool statistics=m_c.max_entries_day>0 || m_c.max_losses>0 || m_c.daily_profit_cash>0;
      int total=HistoryDealsTotal();
      ulong entry_orders[]; ulong ids[]; double pnl[]; double remaining[]; datetime ends[];
      if(statistics)
         for(int k=0;k<total;k++)
           {
            ulong deal=HistoryDealGetTicket(k);
            if(!Scope(HistoryDealGetString(deal,DEAL_SYMBOL),HistoryDealGetInteger(deal,DEAL_MAGIC))) continue;
            long type=HistoryDealGetInteger(deal,DEAL_TYPE);
            if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
            int n=ArraySize(ids); ArrayResize(ids,n+1,1024);
            ids[n]=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
            if(HistoryDealGetInteger(deal,DEAL_ENTRY)==DEAL_ENTRY_IN)
              {
               n=ArraySize(entry_orders); ArrayResize(entry_orders,n+1,1024);
               entry_orders[n]=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
              }
           }
      XPMM_Unique(ids); XPMM_Unique(entry_orders);
      datetime first_fills[]; ArrayResize(first_fills,ArraySize(entry_orders)); ArrayInitialize(first_fills,0);
      ArrayResize(pnl,ArraySize(ids)); ArrayInitialize(pnl,0);
      ArrayResize(remaining,ArraySize(ids)); ArrayInitialize(remaining,0);
      ArrayResize(ends,ArraySize(ids)); ArrayInitialize(ends,0);
      double cash_total=0,credit_total=0;
      // Aggregate full position lifecycles so partial exits do not count as separate losses.
      for(int k=0;k<total;k++)
        {
         ulong deal=HistoryDealGetTicket(k);
         long type=HistoryDealGetInteger(deal,DEAL_TYPE);
         if(type==DEAL_TYPE_BALANCE) { cash_total+=HistoryDealGetDouble(deal,DEAL_PROFIT); continue; }
         if(type==DEAL_TYPE_CREDIT || type==DEAL_TYPE_BONUS) { credit_total+=HistoryDealGetDouble(deal,DEAL_PROFIT); continue; }
         if(!statistics || (type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL)) continue;
         if(!Scope(HistoryDealGetString(deal,DEAL_SYMBOL),HistoryDealGetInteger(deal,DEAL_MAGIC))) continue;
         ulong id=(ulong)HistoryDealGetInteger(deal,DEAL_POSITION_ID);
         int index=ArrayBsearch(ids,id);
         if(index<0 || ids[index]!=id) continue;
         double net=HistoryDealGetDouble(deal,DEAL_PROFIT)+HistoryDealGetDouble(deal,DEAL_SWAP)+
            HistoryDealGetDouble(deal,DEAL_COMMISSION)+HistoryDealGetDouble(deal,DEAL_FEE);
         pnl[index]+=net;
         datetime at=(datetime)HistoryDealGetInteger(deal,DEAL_TIME);
         if(at>=m_day) m_daily_realized+=net;
         ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY);
         if(entry==DEAL_ENTRY_IN)
           {
            remaining[index]+=HistoryDealGetDouble(deal,DEAL_VOLUME);
            ulong order=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
            int oi=ArrayBsearch(entry_orders,order);
            if(oi>=0 && entry_orders[oi]==order && (first_fills[oi]==0 || at<first_fills[oi])) first_fills[oi]=at;
           }
         else if(entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY)
           { remaining[index]-=HistoryDealGetDouble(deal,DEAL_VOLUME); ends[index]=at; }
         else remaining[index]=DBL_MAX; // reversal lifecycle unsupported for streak accounting
        }
      for(int i=0;i<ArraySize(first_fills);i++) if(first_fills[i]>=m_day && first_fills[i]>0) m_entries++;
      XPMM_COMPLETED completed[];
      for(int i=0;i<ArraySize(ids);i++)
         if(ends[i]>0 && remaining[i]<1e-8)
           {
            int n=ArraySize(completed); ArrayResize(completed,n+1,256);
            completed[n].at=ends[i]; completed[n].id=ids[i]; completed[n].pnl=pnl[i];
           }
      XPMM_SortCompleted(completed,0,ArraySize(completed)-1);
      for(int i=0;i<ArraySize(completed);i++)
         if(completed[i].at>m_loss_until)
           {
            if(completed[i].pnl<0) m_losses++; else m_losses=0;
            if(m_c.max_losses>0 && m_losses>=m_c.max_losses)
              { m_loss_until=completed[i].at+m_c.loss_cooldown_seconds; m_losses=0; }
           }
      // Funding is not performance. Balance operations move every anchor; credit and
      // bonus move only the equity guard anchors, never the base capital used for scaling.
      if(m_cash_known)
        {
         double adjustment=cash_total-m_cash_total;
         m_base+=adjustment; m_peak+=adjustment;
         if(previous_day==m_day) m_day_equity+=adjustment;
         if(previous_week==m_week) m_week_equity+=adjustment;
        }
      if(m_credit_known)
        {
         double adjustment=credit_total-m_credit_total;
         m_peak+=adjustment;
         if(previous_day==m_day) m_day_equity+=adjustment;
         if(previous_week==m_week) m_week_equity+=adjustment;
        }
      m_cash_total=cash_total; m_cash_known=true;
      m_credit_total=credit_total; m_credit_known=true;
      m_peak=MathMax(m_peak,equity);
      SaveAccount();
      m_dirty=false;
     }
   // Reconciliation runs on transaction events. Deposit/withdrawal offsets guards.
   void OnTradeTransaction(const MqlTradeTransaction &tx,const MqlTradeRequest &request,const MqlTradeResult &result)
     {
      if(!m_ready) return;
      if(tx.type==TRADE_TRANSACTION_DEAL_ADD && HistoryDealSelect(tx.deal))
        {
         long type=HistoryDealGetInteger(tx.deal,DEAL_TYPE);
         if(type==DEAL_TYPE_BALANCE || type==DEAL_TYPE_CREDIT || type==DEAL_TYPE_BONUS)
           {
            double cash=HistoryDealGetDouble(tx.deal,DEAL_PROFIT);
            if(type==DEAL_TYPE_BALANCE) { m_base+=cash; m_cash_total+=cash; }
            else m_credit_total+=cash;
            m_peak+=cash; m_day_equity+=cash; m_week_equity+=cash;
            SaveAccount();
           }
        }
      // Position-level recovery only. Full account history is deferred to Refresh().
      if(tx.symbol==m_c.symbol) Track(true);
      if(tx.type==TRADE_TRANSACTION_REQUEST && request.symbol==m_c.symbol && request.magic==m_c.magic)
        {
         // Only explicit successful/rejected server responses resolve ambiguity.
         if(request.position!=0)
           {
            for(int i=0;i<ArraySize(m_state);i++) if(m_state[i].ticket==request.position && m_state[i].uncertain)
              {
               if(!BrokerUncertain(result))
                 {
                  m_state[i].uncertain=false;
                  if(result.retcode==TRADE_RETCODE_PLACED && result.order==0) m_state[i].uncertain=true;
                  else if(result.order!=0) m_state[i].pending_order=result.order;
                  Save(i);
                 }
              }
           }
         else if(m_entry_uncertain && request.action==TRADE_ACTION_DEAL && !BrokerUncertain(result))
           {
            m_entry_uncertain=result.retcode==TRADE_RETCODE_PLACED && result.order==0;
            m_entry_order=result.order; SaveAccount();
           }
        }
      if(tx.type==TRADE_TRANSACTION_DEAL_ADD) m_dirty=true;
     }
   void SetContext(const ulong identifier,const double atr,const double external_stop)
     {
      int i=Index(identifier); if(i<0) return;
      m_state[i].atr=FiniteNonNegative(atr) ? atr : 0;
      m_state[i].external_stop=FiniteNonNegative(external_stop) && external_stop!=EMPTY_VALUE ? external_stop : 0;
     }
   bool RegisterPosition(const ulong identifier,const double original_sl)
     {
      Track(false); int i=Index(identifier);
      if(i<0 || !MathIsValidNumber(original_sl) || original_sl<=0 ||
         (Buy(i) ? original_sl>=m_state[i].entry : original_sl<=m_state[i].entry)) return Fail("INVALID_ORIGINAL_STOP");
      m_state[i].risk=MathAbs(m_state[i].entry-original_sl); m_state[i].risk_known=true; Save(i); return true;
     }
   bool EntryAllowed()
     {
      if(!m_ready) return Fail("NOT_CONFIGURED");
      Calendar();
      if(!NettingSafe()) return false;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY);
      if(equity<=0) return Fail("NO_EQUITY");
      bool changed=false;
      if(equity>m_peak) { m_peak=equity; Write(Key(0,"peak"),m_peak); }
      if(m_c.daily_loss_percent>0 && !m_day_locked && equity<=m_day_equity*(1-m_c.daily_loss_percent/100)) { m_day_locked=true; changed=true; }
      if(m_c.weekly_loss_percent>0 && !m_week_locked && equity<=m_week_equity*(1-m_c.weekly_loss_percent/100)) { m_week_locked=true; changed=true; }
      if(m_c.max_drawdown_percent>0 && !m_dd_locked && equity<=m_peak*(1-m_c.max_drawdown_percent/100)) { m_dd_locked=true; changed=true; }
      if(changed) SaveAccount();
      if(m_day_locked && m_c.daily_loss_percent>0) return Fail("DAILY_EQUITY_LIMIT");
      if(m_week_locked && m_c.weekly_loss_percent>0) return Fail("WEEKLY_EQUITY_LIMIT");
      if(m_dd_locked && m_c.max_drawdown_percent>0) return Fail("DRAWDOWN_LIMIT");
      if(!m_history_ok) return Fail("HISTORY_UNAVAILABLE");
      // Limits which depend on closed-trade statistics wait for an explicit Refresh.
      if(m_dirty && (m_c.max_entries_day>0 || m_c.max_losses>0 || m_c.daily_profit_cash>0))
         return Fail("REFRESH_REQUIRED");
      if(m_c.daily_profit_cash>0 && m_daily_realized>=m_c.daily_profit_cash) return Fail("DAILY_PROFIT_LOCK");
      if(TimeCurrent()<m_loss_until) return Fail("LOSS_COOLDOWN");
      if(m_c.max_entries_day>0 && m_entries>=m_c.max_entries_day) return Fail("DAILY_ENTRY_LIMIT");
      return true;
     }
   bool PrepareEntry(const XPMM_ENTRY &e,XPMM_PLAN &plan)
     {
      ZeroMemory(plan);
      if(!EntryAllowed()) return false;
      if(EntryWaiting()) return false;
      if(AccountInfoInteger(ACCOUNT_MARGIN_MODE)!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING && PositionSelect(m_c.symbol))
         return Fail("NETTING_ADDITIONS_UNSUPPORTED");
      if(e.type!=ORDER_TYPE_BUY && e.type!=ORDER_TYPE_SELL) return Fail("MARKET_ENTRY_ONLY");
      bool buy=e.type==ORDER_TYPE_BUY; MqlTick tick;
      if(!SymbolInfoTick(m_c.symbol,tick) || tick.bid<=0 || tick.ask<=0) return Fail("QUOTE_UNAVAILABLE");
      if(m_c.max_spread_points>0 && (tick.ask-tick.bid)/PointSize()>m_c.max_spread_points) return Fail("SPREAD_LIMIT");
      double price=e.entry>0 ? e.entry : (buy ? tick.ask : tick.bid);
      if(!MathIsValidNumber(price) || MathAbs(price-(buy ? tick.ask : tick.bid))>MathMax(m_c.deviation_points*PointSize(),TickSize()))
         return Fail("STALE_ENTRY_PRICE");
      double sl=e.sl,tp=e.tp,dist=0;
      if(m_c.stop_mode==XPMM_STOP_POINTS) dist=m_c.stop_value*PointSize();
      if(m_c.stop_mode==XPMM_STOP_ATR) { if(e.atr<=0 || !MathIsValidNumber(e.atr)) return Fail("ATR_REQUIRED"); dist=m_c.stop_value*e.atr; }
      if(m_c.stop_mode==XPMM_STOP_PERCENT) dist=price*m_c.stop_value/100;
      if(dist>0) sl=buy ? price-dist : price+dist;
      if(!FiniteNonNegative(sl) || sl==EMPTY_VALUE) return Fail("INVALID_SL");
      if(sl>0) sl=XPMM_StopRound(sl,TickSize(),buy);
      double minimum=MathMax(SymbolInfoInteger(m_c.symbol,SYMBOL_TRADE_STOPS_LEVEL)*PointSize(),TickSize());
      if(sl>0 && (buy ? tick.bid-sl : sl-tick.ask)<minimum-1e-9) return Fail("INVALID_SL_DISTANCE");
      if(m_c.require_sl && sl<=0) return Fail("SL_REQUIRED");
      dist=0;
      if(m_c.tp_mode==XPMM_TP_OFF) tp=0;
      if(m_c.tp_mode==XPMM_TP_POINTS) dist=m_c.tp_value*PointSize();
      if(m_c.tp_mode==XPMM_TP_ATR) { if(e.atr<=0 || !MathIsValidNumber(e.atr)) return Fail("ATR_REQUIRED"); dist=m_c.tp_value*e.atr; }
      if(m_c.tp_mode==XPMM_TP_PERCENT) dist=price*m_c.tp_value/100;
      if(m_c.tp_mode==XPMM_TP_R) { if(sl<=0) return Fail("R_REQUIRES_SL"); dist=MathAbs(price-sl)*m_c.tp_value; }
      if(dist>0) tp=buy ? price+dist : price-dist;
      if(!FiniteNonNegative(tp) || tp==EMPTY_VALUE) return Fail("INVALID_TP");
      if(tp>0) tp=XPMM_StopRound(tp,TickSize(),!buy);
      if(tp>0 && ((buy ? tp<=price : tp>=price) || (buy ? tp-tick.bid : tick.ask-tp)<minimum-1e-9)) return Fail("INVALID_TP_DISTANCE");
      if(m_c.require_tp && tp<=0) return Fail("TP_REQUIRED");
      if(!TradePermitted(e.type)) return false;
      double equity=AccountInfoDouble(ACCOUNT_EQUITY),balance=AccountInfoDouble(ACCOUNT_BALANCE);
      double free=AccountInfoDouble(ACCOUNT_MARGIN_FREE),loss=0,lots=0;
      if(sl>0 && (!OrderCalcProfit(e.type,m_c.symbol,1,price,sl,loss) || loss>=0)) return Fail("RISK_CALC_FAILED");
      loss=-loss;
      if(m_c.lot_mode!=XPMM_FIXED_LOTS && m_c.lot_mode!=XPMM_CAPITAL_UNITS && m_c.lot_mode!=XPMM_EQUITY_STEPS && loss<=0)
         return Fail("RISK_MODE_REQUIRES_SL");
      lots=XPMM_BaseLots(m_c,equity,balance,free,m_base,loss);
      if(m_c.reduce_risk_at_dd>0 && m_peak>0 && (m_peak-equity)/m_peak*100>=m_c.reduce_risk_at_dd)
         lots*=m_c.reduced_risk_factor;
      if((m_c.max_risk_cash>0 || m_c.max_risk_percent>0 || m_c.max_total_risk_percent>0) && loss<=0)
         return Fail("RISK_CAP_REQUIRES_SL");
      if(m_c.max_risk_cash>0) lots=MathMin(lots,m_c.max_risk_cash/loss);
      if(m_c.max_risk_percent>0) lots=MathMin(lots,equity*m_c.max_risk_percent/100/loss);
      int count=0; double exposure=0;
      for(int p=0;p<PositionsTotal();p++)
        {
         PositionGetTicket(p);
         if(!Scope(PositionGetString(POSITION_SYMBOL),PositionGetInteger(POSITION_MAGIC))) continue;
         count++;
         if(m_c.max_total_risk_percent<=0) continue;
         double stop=PositionGetDouble(POSITION_SL),pnl=0;
         if(stop<=0) return Fail("UNBOUNDED_OPEN_RISK");
         ENUM_ORDER_TYPE type=PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         // Additional loss from current liquidation quote to SL, not entry-to-SL.
         double current=type==ORDER_TYPE_BUY ? tick.bid : tick.ask;
         if(!OrderCalcProfit(type,m_c.symbol,PositionGetDouble(POSITION_VOLUME),current,stop,pnl)) return Fail("EXPOSURE_CALC_FAILED");
         exposure+=MathMax(0,-pnl);
        }
      for(int o=0;o<OrdersTotal();o++)
        {
         OrderGetTicket(o);
         if(!Scope(OrderGetString(ORDER_SYMBOL),OrderGetInteger(ORDER_MAGIC))) continue;
         count++;
         if(m_c.max_total_risk_percent<=0) continue;
         double stop=OrderGetDouble(ORDER_SL),pnl=0;
         if(stop<=0) return Fail("UNBOUNDED_PENDING_RISK");
         long type=OrderGetInteger(ORDER_TYPE);
         ENUM_ORDER_TYPE side=(type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT || type==ORDER_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
         double entry=OrderGetDouble(ORDER_PRICE_OPEN);
         if(!OrderCalcProfit(side,m_c.symbol,OrderGetDouble(ORDER_VOLUME_CURRENT),entry,stop,pnl)) return Fail("EXPOSURE_CALC_FAILED");
         exposure+=MathMax(0,-pnl);
        }
      if(m_c.max_positions>0 && count>=m_c.max_positions) return Fail("POSITION_LIMIT");
      if(m_c.max_total_risk_percent>0) lots=MathMin(lots,MathMax(0,equity*m_c.max_total_risk_percent/100-exposure)/loss);
      double maximum=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_MAX),step=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_STEP);
      double direction_limit=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_LIMIT);
      if(direction_limit>0)
        {
         double used=0;
         for(int p=0;p<PositionsTotal();p++)
           {
            PositionGetTicket(p);
            if(PositionGetString(POSITION_SYMBOL)==m_c.symbol &&
               (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)==buy) used+=PositionGetDouble(POSITION_VOLUME);
           }
         for(int o=0;o<OrdersTotal();o++)
           {
            OrderGetTicket(o); if(OrderGetString(ORDER_SYMBOL)!=m_c.symbol) continue;
            long type=OrderGetInteger(ORDER_TYPE);
            bool order_buy=type==ORDER_TYPE_BUY || type==ORDER_TYPE_BUY_LIMIT || type==ORDER_TYPE_BUY_STOP || type==ORDER_TYPE_BUY_STOP_LIMIT;
            if(order_buy==buy) used+=OrderGetDouble(ORDER_VOLUME_CURRENT);
           }
         maximum=MathMin(maximum,MathMax(0,direction_limit-used));
        }
      if(m_c.max_lots>0) maximum=MathMin(maximum,m_c.max_lots);
      lots=XPMM_VolumeDown(lots,step,maximum);
      double minimum_lots=SymbolInfoDouble(m_c.symbol,SYMBOL_VOLUME_MIN);
      double margin=0,budget=free*(m_c.max_margin_percent>0 ? m_c.max_margin_percent/100 : 1);
      if(lots<minimum_lots) return Fail("MIN_VOLUME_EXCEEDS_BUDGET");
      if(!OrderCalcMargin(e.type,m_c.symbol,lots,price,margin)) return Fail("MARGIN_CALC_FAILED");
      // Binary search in broker volume units; no assumption of linear margin tiers.
      if(margin>budget)
        {
         long low=0,high=(long)MathFloor(lots/step+1e-9);
         while(low<high)
           {
            long mid=(low+high+1)/2; double cost=0;
            if(!OrderCalcMargin(e.type,m_c.symbol,mid*step,price,cost)) return Fail("MARGIN_CALC_FAILED");
            if(cost<=budget) low=mid; else high=mid-1;
           }
         lots=XPMM_VolumeDown(low*step,step,maximum);
         if(lots<minimum_lots) return Fail("INSUFFICIENT_MARGIN");
         if(!OrderCalcMargin(e.type,m_c.symbol,lots,price,margin)) return Fail("MARGIN_CALC_FAILED");
        }
      plan.type=e.type; plan.symbol=m_c.symbol; plan.entry=price; plan.sl=sl; plan.tp=tp;
      plan.volume=lots; plan.risk_cash=lots*loss; plan.margin=margin; plan.comment=e.comment;
      MqlTradeRequest check_request; MqlTradeCheckResult check; ZeroMemory(check_request); ZeroMemory(check);
      check_request.action=TRADE_ACTION_DEAL; check_request.magic=m_c.magic; check_request.symbol=m_c.symbol;
      check_request.type=plan.type; check_request.price=plan.entry; check_request.volume=plan.volume;
      check_request.sl=plan.sl; check_request.tp=plan.tp; check_request.type_filling=Filling();
      check_request.deviation=m_c.deviation_points;
      if(!OrderCheck(check_request,check)) return Fail("ENTRY_CHECK: "+check.comment);
      m_reason="OK"; return true;
     }
   // Recompute the plan against the current quote and limits before submitting.
   bool SubmitEntry(const XPMM_ENTRY &e,XPMM_PLAN &plan)
     {
      if(TimeCurrent()<m_last_entry_try+m_c.retry_seconds) return Fail("ENTRY_THROTTLED");
      if(!PrepareEntry(e,plan)) return false;
      MqlTradeRequest q; MqlTradeResult r; ZeroMemory(q);
      q.action=TRADE_ACTION_DEAL; q.magic=m_c.magic; q.symbol=m_c.symbol;
      q.type=plan.type; q.price=plan.entry; q.volume=plan.volume; q.sl=plan.sl; q.tp=plan.tp;
      q.deviation=m_c.deviation_points; q.type_filling=Filling(); q.comment=plan.comment;
      m_last_entry_try=TimeCurrent();
      m_entry_uncertain=true; m_entry_since=TimeCurrent(); m_entry_eligible=0; SaveAccount();
      if(!m_tester && m_c.persist) GlobalVariablesFlush();
      if(!Send(q,r))
        { if(!Uncertain(r)) { m_entry_uncertain=false; m_entry_since=0; SaveAccount(); } return false; }
      m_entry_uncertain=r.retcode==TRADE_RETCODE_PLACED && r.order==0;
      m_entry_order=r.order;
      SaveAccount();
      Track(false);
      if(r.deal!=0 && plan.sl>0 && HistoryDealSelect(r.deal))
        {
         ulong id=(ulong)HistoryDealGetInteger(r.deal,DEAL_POSITION_ID);
         int i=Index(id);
         if(i>=0 && m_state[i].risk<=0) RegisterPosition(id,plan.sl);
        }
      return true;
     }
   bool RequestClose(const ulong identifier)
     {
      int i=Index(identifier); if(i<0) return Fail("POSITION_NOT_TRACKED");
      m_state[i].closing=true; Save(i); return true;
     }
   // Manual recovery after checking broker history and active orders. Waits also
   // resolve automatically after reconcile_seconds unless that setting is zero.
   bool ConfirmBrokerReconciled()
     {
      if(!m_ready || OrderStatus(m_entry_order)>0) return Fail("ENTRY_STILL_PENDING");
      for(int i=0;i<ArraySize(m_state);i++)
         if(OrderStatus(m_state[i].pending_order)>0) return Fail("POSITION_STILL_PENDING");
      m_entry_uncertain=false; m_entry_order=0; m_entry_since=0; m_entry_eligible=0;
      for(int i=0;i<ArraySize(m_state);i++)
        {
         m_state[i].uncertain=false; m_state[i].pending_order=0;
         m_state[i].since=0; m_state[i].eligible=0; Save(i);
        }
      SaveAccount(); Refresh(); return true;
     }
   void ResetDrawdownAnchor()
     { if(!m_ready) return; m_peak=AccountInfoDouble(ACCOUNT_EQUITY); m_dd_locked=false; SaveAccount(); }
   // Lightweight quote/position work only. Refresh separately on closed bars/events.
   void Manage()
     {
      if(!m_ready || !NettingSafe()) return;
      MqlTick tick; if(!SymbolInfoTick(m_c.symbol,tick)) return;
      double basket=0;
      for(int i=0;i<ArraySize(m_state);i++)
         if(PositionSelectByTicket(m_state[i].ticket)) basket+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
      bool liquidate=(m_c.basket_profit_cash>0 && basket>=m_c.basket_profit_cash) ||
         (m_c.basket_loss_cash>0 && basket<=-m_c.basket_loss_cash);
      bool allowed=EntryAllowed();
      if(!allowed && m_c.guard_close && (m_reason=="DAILY_EQUITY_LIMIT" || m_reason=="WEEKLY_EQUITY_LIMIT" || m_reason=="DRAWDOWN_LIMIT")) liquidate=true;
      if(liquidate) CancelPending();
      for(int i=0;i<ArraySize(m_state);i++)
        {
         if(!PositionSelectByTicket(m_state[i].ticket)) continue;
         if(Pending(i)) continue;
         double volume=PositionGetDouble(POSITION_VOLUME);
         if(!m_state[i].closing && (liquidate || (m_c.max_hold_seconds>0 && TimeCurrent()-m_state[i].opened>=m_c.max_hold_seconds)))
           { m_state[i].closing=true; Write(Key(m_state[i].id,"close"),1); }
         if(m_state[i].closing) { CloseVolume(i,volume,-1); continue; }
         double current=Buy(i) ? tick.bid : tick.ask;
         double favorable=Buy(i) ? MathMax(m_state[i].favorable,current) : MathMin(m_state[i].favorable,current);
         if(favorable!=m_state[i].favorable) { m_state[i].favorable=favorable; Write(Key(m_state[i].id,"f"),favorable); }
         double distance=XPMM_ProfitDistance(Buy(i),m_state[i].entry,tick.bid,tick.ask);
         double cash=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
         bool partial_sent=false;
         for(int s=0;s<ArraySize(m_partial);s++)
           {
            if((m_state[i].partial_mask&((uint)1<<s))!=0) continue;
            bool committed=m_state[i].pending_stage==s && m_state[i].pending_target>0;
            if(!committed && UnitValue(i,m_partial[s].unit,distance,cash)<m_partial[s].trigger) continue;
            double amount=committed ? m_state[i].pending_target : m_state[i].original_volume*m_partial[s].percent_original/100;
            partial_sent=CloseVolume(i,amount,s); break;
           }
         if(partial_sent || m_state[i].pending_order!=0 || TimeCurrent()<m_state[i].last_try+m_c.retry_seconds) continue;
         double best=0,point=PointSize();
         for(int b=0;b<ArraySize(m_be);b++)
           {
            if(UnitValue(i,m_be[b].unit,distance,cash)<m_be[b].trigger) continue;
            if(m_be[b].lock_r>0 && m_state[i].risk<=0) continue;
            double offset=m_be[b].lock_points*point+m_be[b].lock_r*m_state[i].risk;
            if(m_be[b].cover_costs)
              {
               double one=0; ENUM_ORDER_TYPE type=Buy(i) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
               if(!OrderCalcProfit(type,m_c.symbol,volume,m_state[i].entry,
                    m_state[i].entry+(Buy(i) ? TickSize() : -TickSize()),one) || one<=0) continue;
               double share=m_state[i].original_volume>0 ? volume/m_state[i].original_volume : 1;
               double costs=m_state[i].costs_cash*share+
                  m_c.estimated_exit_commission_per_lot*volume-PositionGetDouble(POSITION_SWAP);
               offset+=MathMax(0,costs)*TickSize()/one;
              }
            Candidate(i,m_state[i].entry+(Buy(i) ? offset : -offset),0,tick,best);
           }
         for(int s=0;s<ArraySize(m_rtrail);s++)
           if(m_state[i].risk>0 && distance/m_state[i].risk>=m_rtrail[s].trigger_r)
              Candidate(i,m_state[i].entry+(Buy(i) ? 1 : -1)*m_rtrail[s].lock_r*m_state[i].risk,
                        m_c.trail_step_points*point,tick,best);
         if(m_c.trail_trigger==0 || UnitValue(i,m_c.trail_trigger_unit,distance,cash)>=m_c.trail_trigger)
           {
            double sl=0,dist=0;
            if(m_c.trail_mode==XPMM_TRAIL_FIXED) dist=m_c.trail_distance*point;
            if(m_c.trail_mode==XPMM_TRAIL_ATR || m_c.trail_mode==XPMM_TRAIL_CHANDELIER) dist=m_c.trail_distance*m_state[i].atr;
            if(dist>0)
              { double anchor=m_c.trail_mode==XPMM_TRAIL_CHANDELIER ? m_state[i].favorable : current;
                sl=anchor+(Buy(i) ? -dist : dist); }
            if(m_c.trail_mode==XPMM_TRAIL_EXTERNAL) sl=m_state[i].external_stop;
            if(m_c.trail_mode==XPMM_TRAIL_GIVEBACK)
              { double excursion=(Buy(i) ? 1 : -1)*(m_state[i].favorable-m_state[i].entry);
                if(excursion>0) sl=m_state[i].entry+(Buy(i) ? 1 : -1)*excursion*(1-m_c.giveback_percent/100); }
            Candidate(i,sl,m_c.trail_step_points*point,tick,best);
           }
         if(best>0)
           {
            MqlTradeRequest q; MqlTradeResult r; ZeroMemory(q);
            q.action=TRADE_ACTION_SLTP; q.symbol=m_c.symbol; q.magic=m_c.magic;
            q.position=m_state[i].ticket; q.sl=best; q.tp=PositionGetDouble(POSITION_TP);
            // A stop change is idempotent and never loosens: an unanswered request is simply
            // re-evaluated after retry_seconds, so it needs no fail-closed persistence.
            m_state[i].last_try=TimeCurrent();
            Send(q,r);
           }
        }
     }
   void Shutdown()
     { if(m_ready) { for(int i=0;i<ArraySize(m_state);i++) Save(i); SaveAccount(); if(!m_tester && m_c.persist) GlobalVariablesFlush(); }
       m_ready=false; ReleaseOwner(); }
  };
#endif
