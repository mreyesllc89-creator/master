//+------------------------------------------------------------------+
//|                                              RegimeDirection.mqh |
//|                    Layer 2 - SuperTrend direction on the chart TF|
//+------------------------------------------------------------------+
//| Classic SuperTrend built on Wilder ATR. Every recursive term     |
//| (final upper band, final lower band, direction) is written into  |
//| an INDICATOR_CALCULATIONS buffer owned by the host indicator, so |
//| bar i only ever reads bar i-1 from that buffer. Nothing lives in |
//| a static or global variable and a full recalculation reproduces  |
//| the incremental result bit for bit.                              |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

//+------------------------------------------------------------------+
//| Class CSuperTrendEngine                                          |
//+------------------------------------------------------------------+
class CSuperTrendEngine
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_atr_period;
   double            m_multiplier;
   int               m_atr_handle;
   double            m_atr[];             // ATR window, oldest first
   int               m_atr_offset;        // chart index of m_atr[0]

public:
                     CSuperTrendEngine(void);
                    ~CSuperTrendEngine(void);

   bool              Init(const string symbol,const ENUM_TIMEFRAMES tf,
                          const int atr_period,const double multiplier);
   void              Deinit(void);

   int               WarmupBars(void) const { return(m_atr_period + 1); }
   double            Atr(const int i) const;

   //--- Loads the ATR window covering [first .. rates_total-1].
   bool              LoadAtr(const int rates_total,const int first);

   //--- Fills st/fu/fl/dir for [first .. rates_total-1]. Requires a
   //--- prior successful LoadAtr() for the same range.
   bool              Calculate(const int rates_total,const int first,
                               const double &high[],const double &low[],const double &close[],
                               double &st[],double &fu[],double &fl[],double &dir[]);
  };

//+------------------------------------------------------------------+
CSuperTrendEngine::CSuperTrendEngine(void) : m_symbol(""),
                                             m_tf(PERIOD_CURRENT),
                                             m_atr_period(10),
                                             m_multiplier(3.0),
                                             m_atr_handle(INVALID_HANDLE),
                                             m_atr_offset(0)
  {
  }
//+------------------------------------------------------------------+
CSuperTrendEngine::~CSuperTrendEngine(void)
  {
   Deinit();
  }
//+------------------------------------------------------------------+
bool CSuperTrendEngine::Init(const string symbol,const ENUM_TIMEFRAMES tf,
                             const int atr_period,const double multiplier)
  {
   if(atr_period < 1 || multiplier <= 0.0)
      return(false);
   m_symbol     = symbol;
   m_tf         = tf;
   m_atr_period = atr_period;
   m_multiplier = multiplier;
   ArraySetAsSeries(m_atr,false);
   m_atr_handle = iATR(m_symbol,m_tf,m_atr_period);
   return(m_atr_handle != INVALID_HANDLE);
  }
//+------------------------------------------------------------------+
void CSuperTrendEngine::Deinit(void)
  {
   if(m_atr_handle != INVALID_HANDLE)
     {
      IndicatorRelease(m_atr_handle);
      m_atr_handle = INVALID_HANDLE;
     }
  }
//+------------------------------------------------------------------+
double CSuperTrendEngine::Atr(const int i) const
  {
   int idx = i - m_atr_offset;
   if(idx < 0 || idx >= ArraySize(m_atr))
      return(0.0);
   return(m_atr[idx]);
  }
//+------------------------------------------------------------------+
bool CSuperTrendEngine::LoadAtr(const int rates_total,const int first)
  {
   if(m_atr_handle == INVALID_HANDLE || rates_total <= 0)
      return(false);
   if(BarsCalculated(m_atr_handle) < rates_total)
      return(false);                       // ATR not fully built yet

   int need = rates_total - first + 2;
   if(need > rates_total)
      need = rates_total;
   if(need < 1)
      return(false);
   if(CopyBuffer(m_atr_handle,0,0,need,m_atr) != need)
      return(false);
   m_atr_offset = rates_total - need;
   return(true);
  }
//+------------------------------------------------------------------+
bool CSuperTrendEngine::Calculate(const int rates_total,const int first,
                                  const double &high[],const double &low[],const double &close[],
                                  double &st[],double &fu[],double &fl[],double &dir[])
  {
   int seed = WarmupBars();
   if(rates_total <= seed || first < seed || first >= rates_total)
      return(false);

//--- on a full recalculation clear the warm-up region explicitly
   if(first == seed)
     {
      for(int i = 0; i < seed; i++)
        {
         st[i]  = EMPTY_VALUE;
         fu[i]  = 0.0;
         fl[i]  = 0.0;
         dir[i] = 0.0;
        }
     }

   for(int i = first; i < rates_total; i++)
     {
      double atr   = Atr(i);
      double hl2   = (high[i] + low[i]) * 0.5;
      double upper = hl2 + m_multiplier * atr;
      double lower = hl2 - m_multiplier * atr;

      if(i == seed)
        {
         fu[i]  = upper;
         fl[i]  = lower;
         dir[i] = (close[i] > hl2) ? 1.0 : -1.0;
         st[i]  = (dir[i] > 0.0) ? fl[i] : fu[i];
         continue;
        }

      double prev_fu  = fu[i-1];
      double prev_fl  = fl[i-1];
      double prev_dir = dir[i-1];

      fu[i] = (upper < prev_fu || close[i-1] > prev_fu) ? upper : prev_fu;
      fl[i] = (lower > prev_fl || close[i-1] < prev_fl) ? lower : prev_fl;

      if(prev_dir > 0.0)
         dir[i] = (close[i] < fl[i]) ? -1.0 : 1.0;
      else
         dir[i] = (close[i] > fu[i]) ?  1.0 : -1.0;

      st[i] = (dir[i] > 0.0) ? fl[i] : fu[i];
     }
   return(true);
  }
