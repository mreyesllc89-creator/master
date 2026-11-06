# Custom indicators

## Skeleton (separate window, two lines: TDI fast and slow)
```mql5
#property indicator_separate_window
#property indicator_buffers 3            // all buffers incl. calculation-only ones
#property indicator_plots   2
#property indicator_minimum 0
#property indicator_maximum 100
#property indicator_level1  32
#property indicator_level2  68
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrWhite
#property indicator_width1  2
#property indicator_label1  "TDI fast"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrOrange
#property indicator_label2  "TDI slow"

input int InpRsiLen = 14, InpFastLen = 2, InpSlowLen = 7;

double bufFast[], bufSlow[], bufRsi[];
int hRsi = INVALID_HANDLE;

int OnInit()
{
   SetIndexBuffer(0, bufFast, INDICATOR_DATA);
   SetIndexBuffer(1, bufSlow, INDICATOR_DATA);
   SetIndexBuffer(2, bufRsi,  INDICATOR_CALCULATIONS);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, InpRsiLen + InpFastLen);
   PlotIndexSetInteger(1, PLOT_DRAW_BEGIN, InpRsiLen + InpSlowLen);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   IndicatorSetInteger(INDICATOR_DIGITS, 2);
   IndicatorSetString(INDICATOR_SHORTNAME, StringFormat("TDI(%d,%d,%d)", InpRsiLen, InpFastLen, InpSlowLen));
   hRsi = iRSI(_Symbol, _Period, InpRsiLen, PRICE_CLOSE);
   return hRsi == INVALID_HANDLE ? INIT_FAILED : INIT_SUCCEEDED;
}

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
{
   if(rates_total < InpRsiLen + InpSlowLen) return 0;
   if(BarsCalculated(hRsi) < rates_total) return 0;                 // wait for the RSI
   int toCopy = (prev_calculated == 0) ? rates_total : rates_total - prev_calculated + 1;
   if(CopyBuffer(hRsi, 0, 0, toCopy, bufRsi) <= 0) return 0;       // buffers here are NOT series: index 0 = oldest

   int start = (prev_calculated == 0) ? InpRsiLen + InpSlowLen : prev_calculated - 1;
   for(int i = start; i < rates_total; i++)
   {
      bufFast[i] = Sma(bufRsi, i, InpFastLen);
      bufSlow[i] = Sma(bufRsi, i, InpSlowLen);
   }
   return rates_total;                                               // becomes prev_calculated next call
}

double Sma(const double &src[], int i, int n)
{
   double s = 0; for(int k = 0; k < n; k++) s += src[i - k]; return s / n;
}
void OnDeinit(const int reason) { IndicatorRelease(hRsi); }
```

## Rules of the game
- Indicator buffers bound with `SetIndexBuffer` are managed by the terminal: do not
  `ArrayResize` them. Their default indexing is oldest-first (`i = 0` is the first bar in
  history) unless you call `ArraySetAsSeries(buf, true)` — be consistent and comment it.
- `prev_calculated` is what you returned last time. `0` means recompute everything (first
  run, history reload). Recalculate from `prev_calculated - 1` so the forming bar updates
  on every tick.
- Returning `0` forces a full recalculation next tick; use it when data is not ready.
- `INDICATOR_CALCULATIONS` buffers are hidden helpers; they still count in
  `indicator_buffers`.
- Plot types: `DRAW_LINE, DRAW_HISTOGRAM, DRAW_ARROW (PLOT_ARROW + PLOT_ARROW_SHIFT),
  DRAW_SECTION, DRAW_ZIGZAG, DRAW_FILLING, DRAW_CANDLES, DRAW_BARS, DRAW_COLOR_LINE
  (needs a color-index buffer with INDICATOR_COLOR_INDEX), DRAW_NONE`.
- Arrow codes come from Wingdings (`233` up arrow, `234` down arrow, `159` dot).
- `indicator_chart_window` for overlays; `indicator_separate_window` for oscillators.
- Short form `OnCalculate(rates_total, prev_calculated, begin, price[])` exists for
  single-input indicators (lets the user apply it to another indicator's data).

## Signals for an EA
Expose signals as a buffer (e.g. `+1 / -1 / 0` or `EMPTY_VALUE`) and read it from the EA
with `iCustom` + `CopyBuffer`. Keep the indicator free of trading logic.

## Drawing objects (labels, lines, like Pine `label.new`, `line.new`)
```mql5
string name = "FG_entry_" + TimeToString(time);
ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
ObjectSetInteger(0, name, OBJPROP_COLOR, clrLime);
ObjectCreate(0, name + "_txt", OBJ_TEXT, 0, time, price);
ObjectSetString(0, name + "_txt", OBJPROP_TEXT, "BUY " + DoubleToString(price, _Digits));
ObjectsDeleteAll(0, "FG_");    // cleanup by prefix in OnDeinit
```
`OBJ_TREND` for segments (two anchors), `OBJ_ARROW_UP/DOWN`, `OBJ_RECTANGLE`,
`OBJ_LABEL` for screen-anchored text (`OBJPROP_XDISTANCE/YDISTANCE/CORNER`). Objects are
slow in the tester; guard with `MQLInfoInteger(MQL_VISUAL_MODE)`.

## Testing an indicator
Attach in a chart, compare values in the Data Window against a reference (TradingView
export or Python `indicators.py`). In the Strategy Tester, indicators run in visual mode
with "Open prices only" for speed.
