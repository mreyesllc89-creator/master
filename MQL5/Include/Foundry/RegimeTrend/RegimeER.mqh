//+------------------------------------------------------------------+
//|                                                     RegimeER.mqh |
//|          Layer 1 - Kaufman Efficiency Ratio on a higher timeframe|
//+------------------------------------------------------------------+
//| ER[j] = |c[j] - c[j-N]| / SUM(|c[k] - c[k-1]|), k = j-N+1..j     |
//|                                                                  |
//| The ratio is computed on its own timeframe (default H1) and then |
//| mapped down to the chart timeframe. A chart bar opening at time  |
//| T is given the ER of the LAST FULLY CLOSED higher-timeframe bar  |
//| at T, so no value can ever be revised once the chart bar exists. |
//| That mapping depends only on bar open times, therefore a full    |
//| recalculation reproduces the incremental result exactly.         |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

#define REGIME_ER_INVALID  (-1.0)   // marker for bars without HTF coverage

//+------------------------------------------------------------------+
//| Class CRegimeEfficiencyRatio                                     |
//+------------------------------------------------------------------+
class CRegimeEfficiencyRatio
  {
private:
   string            m_symbol;
   ENUM_TIMEFRAMES   m_tf;
   int               m_period;
   //--- scratch buffers, reused between calls to avoid reallocation
   double            m_htf_close[];
   datetime          m_htf_time[];
   double            m_htf_er[];

public:
                     CRegimeEfficiencyRatio(void);
                    ~CRegimeEfficiencyRatio(void);

   bool              Init(const string symbol,const ENUM_TIMEFRAMES tf,const int period);
   ENUM_TIMEFRAMES   Timeframe(void) const { return(m_tf);     }
   int               Period(void)    const { return(m_period); }

   //--- Fills er[] for chart bars [first .. rates_total-1].
   //--- Returns false when the higher timeframe is not ready yet; in
   //--- that case er[] is left completely untouched.
   bool              Calculate(const int rates_total,const int first,
                               const datetime &time[],double &er[]);
  };

//+------------------------------------------------------------------+
CRegimeEfficiencyRatio::CRegimeEfficiencyRatio(void) : m_symbol(""),
                                                       m_tf(PERIOD_H1),
                                                       m_period(20)
  {
  }
//+------------------------------------------------------------------+
CRegimeEfficiencyRatio::~CRegimeEfficiencyRatio(void)
  {
  }
//+------------------------------------------------------------------+
bool CRegimeEfficiencyRatio::Init(const string symbol,const ENUM_TIMEFRAMES tf,const int period)
  {
   if(period < 2)
      return(false);
   m_symbol = symbol;
   m_tf     = tf;
   m_period = period;
   ArraySetAsSeries(m_htf_close,false);
   ArraySetAsSeries(m_htf_time,false);
   ArraySetAsSeries(m_htf_er,false);
   return(true);
  }
//+------------------------------------------------------------------+
bool CRegimeEfficiencyRatio::Calculate(const int rates_total,const int first,
                                       const datetime &time[],double &er[])
  {
   if(rates_total <= 0 || first < 0 || first >= rates_total)
      return(false);
//--- how far back on the higher timeframe do we have to reach?
   int shift = iBarShift(m_symbol,m_tf,time[first],false);
   if(shift < 0)
      return(false);                       // series not built yet, retry next tick

   int available = Bars(m_symbol,m_tf);
   if(available <= m_period + 2)
      return(false);                       // no usable higher timeframe history yet

   int need = shift + m_period + 3;
   if(need > available)
      need = available;

   if(CopyClose(m_symbol,m_tf,0,need,m_htf_close) != need)
      return(false);
   if(CopyTime(m_symbol,m_tf,0,need,m_htf_time) != need)
      return(false);

//--- efficiency ratio per higher timeframe bar
   if(ArraySize(m_htf_er) != need && ArrayResize(m_htf_er,need) != need)
      return(false);
   for(int j = 0; j < need; j++)
     {
      if(j < m_period)
        {
         m_htf_er[j] = REGIME_ER_INVALID;
         continue;
        }
      double volatility = 0.0;
      for(int k = j - m_period + 1; k <= j; k++)
         volatility += MathAbs(m_htf_close[k] - m_htf_close[k-1]);
      double direction = MathAbs(m_htf_close[j] - m_htf_close[j-m_period]);
      m_htf_er[j] = (volatility > 0.0) ? direction / volatility : 0.0;
     }

//--- map the higher timeframe onto the chart, walking both series forward
   int j_cur = 0;
   for(int i = first; i < rates_total; i++)
     {
      if(time[i] < m_htf_time[0])
        {
         er[i] = REGIME_ER_INVALID;        // chart bar predates the copied window
         continue;
        }
      while(j_cur + 1 < need && m_htf_time[j_cur+1] <= time[i])
         j_cur++;
      //--- j_cur is the bar still forming at time[i]; use the one before it
      int closed = j_cur - 1;
      er[i] = (closed >= m_period) ? m_htf_er[closed] : REGIME_ER_INVALID;
     }
   return(true);
  }
