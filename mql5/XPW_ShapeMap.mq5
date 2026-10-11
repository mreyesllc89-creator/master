//+------------------------------------------------------------------+
//|                                                 XPW_ShapeMap.mq5 |
//| XPW Shape Map v0.7 — MQL5 port. MAP LAYER ONLY, NO TRADES.       |
//|                                                                  |
//| Built bite by bite. Each bite is a block below, in this order:   |
//|   BITE 1  TDI: RSI(14) -> SMA(2) fast / SMA(7) slow + fill       |
//|   BITE 2  Areas: LOW / HIGH position of the slow line            |
//|   BITE 3  BOT / TOP squares (odd-colour wedge)                   |
//|   BITE 4  Turn ▲ / ▼ (the cross back that HOLDS)                 |
//|   BITE 5  Ticks (long wick = compressed cycle) on the price chart|
//|   BITE 6  CONT ▲ / ▼ (continuation WITHOUT a cross)              |
//|   BITE 7  Predict price (close where fast would cross slow next) |
//|   BITE 8  Panel + signal buffers for the EA                      |
//|                                                                  |
//| Signals are computed once per CLOSED bar and never repaint. With |
//| PreviewFormingBar = true the forming bar also gets a preview in  |
//| the signal buffers (not drawn) so an EA can "enter on tick".     |
//|                                                                  |
//| Buffer map (iCustom / CopyBuffer index):                         |
//|   0 fill A (fast)   1 fill B (slow)   2 Fast   3 Slow            |
//|   4 BOT sq arrow    5 TOP sq arrow    6 Turn▲ arrow 7 Turn▼ arrow|
//|   8 CONT▲ arrow     9 CONT▼ arrow                                |
//|  10 SigBotSq  11 SigTopSq  12 SigTurnUp  13 SigTurnDn            |
//|  14 SigBotTick 15 SigTopTick 16 SigContUp 17 SigContDn           |
//|  18 CrossUp   19 CrossDn   20 ArmL (BOT armed) 21 ArmS (TOP armed)|
//|  22 PredictPx 23 RSI       24 ATR   25 RmaUp  26 RmaDn  27 IsRed |
//| Signal buffers hold 1.0 on the bar the signal is CONFIRMED, else 0|
//+------------------------------------------------------------------+
#property copyright "XPW"
#property version   "0.70"
#property description "XPW Shape Map v0.7 - TDI shape map: squares, turns, ticks, CONT. No trades."
#property indicator_separate_window
#property indicator_buffers 28
#property indicator_plots   9

#property indicator_label1  "TDI fill"
#property indicator_type1   DRAW_FILLING
#property indicator_color1  clrRed,clrLime
#property indicator_label2  "Fast"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrGray
#property indicator_width2  1
#property indicator_label3  "Slow"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrSilver
#property indicator_width3  1
#property indicator_label4  "BOT square"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrRed
#property indicator_width4  2
#property indicator_label5  "TOP square"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrLime
#property indicator_width5  2
#property indicator_label6  "Turn up"
#property indicator_type6   DRAW_ARROW
#property indicator_color6  clrYellow
#property indicator_width6  2
#property indicator_label7  "Turn down"
#property indicator_type7   DRAW_ARROW
#property indicator_color7  clrOrange
#property indicator_width7  2
#property indicator_label8  "CONT up"
#property indicator_type8   DRAW_ARROW
#property indicator_color8  clrAqua
#property indicator_width8  2
#property indicator_label9  "CONT down"
#property indicator_type9   DRAW_ARROW
#property indicator_color9  clrMagenta
#property indicator_width9  2

//--- inputs. ORDER MATTERS: the EA passes them to iCustom in this order.
input group "TDI"
input int    RsiLen      = 14;     // RSI length
input int    FastLen     = 2;      // Fast MA length
input int    SlowLen     = 7;      // Slow MA length
input bool   InvertFill  = true;   // My panel paints fast>slow as RED
input group "Areas"
input int    AreaLook    = 20;     // Area lookback
input double LoFrac      = 0.20;   // LOW area: below this fraction
input double HiFrac      = 0.67;   // HIGH area: above this fraction
input group "Label ALL opportunities"
input bool   AllOn       = true;   // Label ALL opportunities (ignore area + spacing)
input int    AllCtx      = 1;      // Context bars in ALL mode
input group "BOTTOM square (odd RED wedge, LOW area)"
input bool   BotOn       = true;   // Enable
input int    BotMinW     = 1;      // Min width
input int    BotMaxW     = 3;      // Max width
input int    BotCtxIn    = 2;      // Context bars
input bool   BotNeedLow  = true;   // Require LOW area
input int    BotSepIn    = 5;      // Min bars between squares
input group "TOP square (odd LIME wedge, HIGH area)"
input bool   TopOn       = true;   // Enable
input int    TopMinW     = 1;      // Min width
input int    TopMaxW     = 2;      // Max width
input int    TopCtxIn    = 3;      // Context bars
input bool   TopNeedHigh = true;   // Require HIGH area
input int    TopSepIn    = 5;      // Min bars between squares
input group "Turn mark"
input bool   TurnOn      = true;   // Enable
input int    TurnMax     = 12;     // Max bars to wait after a square
input int    TurnHold    = 2;      // Bars the cross must hold
input group "Ticks"
input bool   TickOn      = true;   // Enable
input int    AtrLen      = 14;     // ATR length
input double BotWickRange= 0.55;   // BOTTOM: min lower wick / range
input double BotWickAtr  = 0.8;    // BOTTOM: min lower wick / ATR
input double TopWickRange= 0.70;   // TOP: min upper wick / range
input double TopWickAtr  = 1.20;   // TOP: min upper wick / ATR
input group "CONT (continuation, no cross)"
input bool   ContOn      = true;   // Enable
input double ContBigAtr  = 1.0;    // Big candle: min body / ATR
input int    ContLook    = 30;     // Max bars from big candle to CONT
input bool   ContNeedRed = true;   // Require the little RED area after the big candle
input int    ContRedMax  = 12;     // Max bars of that little RED area
input double ContPinch   = 1.0;    // Pinch: max |fast-slow| where red flips to green (RSI pts)
input int    ContAfter   = 6;      // Max bars after the flip for the green candle
input int    ContSep     = 5;      // Min bars between CONT marks
input bool   ContMirror  = true;   // Also detect the mirror (short) version: CONT ▼
input group "Engine / display"
input bool   PreviewFormingBar = true;  // Signal buffers also preview the forming bar (for EA "enter on tick")
input bool   ShowBoxes   = true;   // Draw BOT / TOP square boxes + labels
input bool   ShowTurns   = true;   // Draw Turn ▲ / ▼
input bool   ShowTicks   = true;   // Draw BOT / TOP ticks on the price chart
input bool   ShowCont    = true;   // Draw CONT marks (panel + price chart)
input bool   ShowPanel   = true;   // Show the counters panel (Comment)

//--- buffers
double FillA[], FillB[], FastBuf[], SlowBuf[];
double BotSqArr[], TopSqArr[], TurnUpArr[], TurnDnArr[], ContUpArr[], ContDnArr[];
double SigBotSq[], SigTopSq[], SigTurnUp[], SigTurnDn[], SigBotTick[], SigTopTick[], SigContUp[], SigContDn[];
double CrossUpBuf[], CrossDnBuf[], ArmLBuf[], ArmSBuf[], PredictPx[], RsiBuf[], AtrBuf[], UpBuf[], DnBuf[], IsRedBuf[];

//--- persistent state (Pine "var" variables). Only mutated on CLOSED bars.
struct XpwState
  {
   int  lastBotBar, lastTopBar, lastBotWedge, lastTopWedge;
   bool botArmed, topArmed;
   int  botArmBar, topArmBar;
   int  nBotSq, nTopSq, nBotTurn, nTopTurn, nBotTk, nTopTk, nContUp, nContDn;
   int  lastBotGap, lastTopGap, lastContUpAge, lastContDnAge;
   int  cSt[2], cBigAt[2], cFlipAt[2], cOddCnt[2], cLastSig[2];   // CONT state, [0]=long [1]=short
  };
//--- what one bar produced
struct XpwSig
  {
   bool   botSq, topSq, turnUp, turnDn, botTick, topTick, contUp, contDn, crossUp, crossDn, armL, armS;
   int    botWid, topWid, botLft, botRgt, topLft, topRgt, turnUpBar, turnDnBar, contUpAge, contDnAge;
   double botHH, botLL, topHH, topLL;
  };

XpwState g_state;
int      g_lastDone = -1;      // last CLOSED bar index that was committed
string   g_prefix   = "XPWSM_";
int      g_win      = -1;

//+------------------------------------------------------------------+
void ResetState()
  {
   ZeroMemory(g_state);
   g_state.lastBotBar = -10000; g_state.lastTopBar = -10000;
   g_state.lastBotWedge = -10000; g_state.lastTopWedge = -10000;
   for(int d = 0; d < 2; d++) { g_state.cBigAt[d] = -10000; g_state.cFlipAt[d] = -10000; g_state.cLastSig[d] = -10000; }
   g_lastDone = -1;
   ObjectsDeleteAll(0, g_prefix);
  }
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0,  FillA,      INDICATOR_DATA);
   SetIndexBuffer(1,  FillB,      INDICATOR_DATA);
   SetIndexBuffer(2,  FastBuf,    INDICATOR_DATA);
   SetIndexBuffer(3,  SlowBuf,    INDICATOR_DATA);
   SetIndexBuffer(4,  BotSqArr,   INDICATOR_DATA);
   SetIndexBuffer(5,  TopSqArr,   INDICATOR_DATA);
   SetIndexBuffer(6,  TurnUpArr,  INDICATOR_DATA);
   SetIndexBuffer(7,  TurnDnArr,  INDICATOR_DATA);
   SetIndexBuffer(8,  ContUpArr,  INDICATOR_DATA);
   SetIndexBuffer(9,  ContDnArr,  INDICATOR_DATA);
   SetIndexBuffer(10, SigBotSq,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(11, SigTopSq,   INDICATOR_CALCULATIONS);
   SetIndexBuffer(12, SigTurnUp,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(13, SigTurnDn,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(14, SigBotTick, INDICATOR_CALCULATIONS);
   SetIndexBuffer(15, SigTopTick, INDICATOR_CALCULATIONS);
   SetIndexBuffer(16, SigContUp,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(17, SigContDn,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(18, CrossUpBuf, INDICATOR_CALCULATIONS);
   SetIndexBuffer(19, CrossDnBuf, INDICATOR_CALCULATIONS);
   SetIndexBuffer(20, ArmLBuf,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(21, ArmSBuf,    INDICATOR_CALCULATIONS);
   SetIndexBuffer(22, PredictPx,  INDICATOR_CALCULATIONS);
   SetIndexBuffer(23, RsiBuf,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(24, AtrBuf,     INDICATOR_CALCULATIONS);
   SetIndexBuffer(25, UpBuf,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(26, DnBuf,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(27, IsRedBuf,   INDICATOR_CALCULATIONS);

   for(int p = 0; p < 9; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   // Fill colours: colour 0 is used where buffer A (fast) is above buffer B (slow).
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, InvertFill ? clrRed  : clrLime);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 1, InvertFill ? clrLime : clrRed);
   PlotIndexSetInteger(3, PLOT_ARROW, 110);   // small square
   PlotIndexSetInteger(4, PLOT_ARROW, 110);
   PlotIndexSetInteger(5, PLOT_ARROW, 233);   // up arrow
   PlotIndexSetInteger(6, PLOT_ARROW, 234);   // down arrow
   PlotIndexSetInteger(7, PLOT_ARROW, 241);   // up arrow (thin)
   PlotIndexSetInteger(8, PLOT_ARROW, 242);   // down arrow (thin)
   int wb = WarmUp();
   for(int p = 0; p < 9; p++)
      PlotIndexSetInteger(p, PLOT_DRAW_BEGIN, wb);

   IndicatorSetString(INDICATOR_SHORTNAME, "XPW Shape Map v0.7" + (AllOn ? " ALL" : ""));
   IndicatorSetInteger(INDICATOR_DIGITS, 2);
   ResetState();
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, g_prefix);
   Comment("");
  }
//+------------------------------------------------------------------+
int WarmUp()
  {
   int ctx = MathMax(MathMax(BotCtxIn, TopCtxIn), AllCtx);
   int w   = MathMax(BotMaxW, TopMaxW);
   int need = RsiLen + SlowLen + MathMax(AreaLook, AtrLen) + 2 * ctx + w + TurnHold + 3;
   return MathMax(need, ContLook + 2);
  }
//+------------------------------------------------------------------+
//| BITE 2 helpers: area position of the slow line at bar j          |
//+------------------------------------------------------------------+
double PosWAt(const int j)
  {
   if(j < AreaLook) return 0.5;
   double hi = -1e10, lo = 1e10;
   for(int k = j - AreaLook + 1; k <= j; k++) { hi = MathMax(hi, SlowBuf[k]); lo = MathMin(lo, SlowBuf[k]); }
   double rng = hi - lo;
   return rng > 0 ? (SlowBuf[j] - lo) / rng : 0.5;
  }
bool InLowAt(const int j)  { return PosWAt(j) <= LoFrac; }
bool InHighAt(const int j) { return PosWAt(j) >= HiFrac; }
bool IsRedAt(const int j)  { return IsRedBuf[j] > 0.5; }
//+------------------------------------------------------------------+
//| BITE 3 helper: odd-colour wedge detector (same loops as Pine)    |
//+------------------------------------------------------------------+
bool Detect(const int i, const bool wantRedWedge, const int minW, const int maxW, const int ctx, int &wOut)
  {
   int wHi = MathMax(minW, maxW);
   wOut = 0;
   if(i - (2 * ctx + wHi) < 0) return false;
   for(int w = minW; w <= wHi; w++)
     {
      bool ok = true;
      for(int k = 0; k < ctx && ok; k++)
         if(!(wantRedWedge ? !IsRedAt(i - k) : IsRedAt(i - k))) ok = false;
      for(int k = 0; k < w && ok; k++)
         if(!(wantRedWedge ? IsRedAt(i - ctx - k) : !IsRedAt(i - ctx - k))) ok = false;
      for(int k = 0; k < ctx && ok; k++)
         if(!(wantRedWedge ? !IsRedAt(i - ctx - w - k) : IsRedAt(i - ctx - w - k))) ok = false;
      if(ok) { wOut = w; return true; }
     }
   return false;
  }
//+------------------------------------------------------------------+
//| BITE 6: CONT state machine for one direction (d: 0 long, 1 short)|
//+------------------------------------------------------------------+
bool ContStep(const int i, const int d, const bool bull, XpwState &s, int &ageOut,
              const double &open[], const double &high[], const double &low[], const double &close[])
  {
   double atr  = AtrBuf[i];
   double body = MathAbs(close[i] - open[i]);
   bool bigBar = atr > 0 && (bull ? close[i] > open[i] : close[i] < open[i]) && body >= ContBigAtr * atr;
   bool isRed  = IsRedAt(i);
   bool inZone = bull ? !isRed : isRed;      // "green zone" (mirror: red zone)
   bool oddClr = bull ? isRed : !isRed;      // the little area of the other colour
   bool dirBar = bull ? close[i] > open[i] : close[i] < open[i];
   double gapNow = MathAbs(FastBuf[i] - SlowBuf[i]);
   double gapPrv = MathAbs(FastBuf[i - 1] - SlowBuf[i - 1]);

   bool ready = s.cSt[d] == 3 && inZone && dirBar && (i - s.cFlipAt[d] <= ContAfter) && (i - s.cLastSig[d] >= ContSep);
   if(ready)
     {
      // the candle we were waiting for. Checked FIRST so a big candle can be the signal itself.
      s.cLastSig[d] = i;
      s.cSt[d] = 0;
     }
   else if(bigBar)
     {
      s.cSt[d] = 1; s.cBigAt[d] = i; s.cOddCnt[d] = 0;       // a new big candle restarts the sequence
     }
   else if(s.cSt[d] > 0 && i - s.cBigAt[d] > ContLook)
      s.cSt[d] = 0;
   else if(s.cSt[d] == 1)
     {
      if(oddClr) { s.cSt[d] = 2; s.cOddCnt[d] = 1; }
      else if(inZone && !ContNeedRed) { s.cSt[d] = 3; s.cFlipAt[d] = i; }
     }
   else if(s.cSt[d] == 2)
     {
      if(oddClr)
        {
         s.cOddCnt[d]++;
         if(s.cOddCnt[d] > ContRedMax) s.cSt[d] = 0;          // not "little" any more
        }
      else if(inZone)
        {
         // the flip bar: the gap on the last odd bar or on this bar must be tiny
         if(MathMin(gapPrv, gapNow) <= ContPinch) { s.cSt[d] = 3; s.cFlipAt[d] = i; }
         else s.cSt[d] = 0;
        }
     }
   else if(s.cSt[d] == 3)
     {
      if(oddClr) { s.cSt[d] = 2; s.cOddCnt[d] = 1; }          // crossed back: turn territory, re-arm
      else if(i - s.cFlipAt[d] > ContAfter) s.cSt[d] = 0;
     }
   ageOut = i - s.cBigAt[d];
   return ContOn && ready;
  }
//+------------------------------------------------------------------+
//| One bar of detection. Mutates s (pass a copy for a preview).     |
//+------------------------------------------------------------------+
void Step(const int i, XpwState &s, XpwSig &o,
          const double &open[], const double &high[], const double &low[], const double &close[])
  {
   ZeroMemory(o);
   //--- BITE 3: squares
   int botCtx = AllOn ? AllCtx : BotCtxIn;
   int topCtx = AllOn ? AllCtx : TopCtxIn;
   int botSep = AllOn ? 0 : BotSepIn;
   int topSep = AllOn ? 0 : TopSepIn;
   bool botArea = AllOn || !BotNeedLow  || InLowAt(i - botCtx);
   bool topArea = AllOn || !TopNeedHigh || InHighAt(i - topCtx);
   int botWid = 0, topWid = 0;
   bool botRaw = Detect(i, true,  BotMinW, BotMaxW, botCtx, botWid);
   bool topRaw = Detect(i, false, TopMinW, TopMaxW, topCtx, topWid);
   bool botOK = BotOn && botRaw && botArea && (i - s.lastBotBar >= botSep);
   bool topOK = TopOn && topRaw && topArea && (i - s.lastTopBar >= topSep);
   if(botOK)
     {
      s.lastBotBar = i; s.lastBotWedge = i - botCtx; s.nBotSq++;
      o.botSq = true; o.botWid = botWid; o.botLft = i - botCtx - botWid + 1; o.botRgt = i - botCtx;
      o.botHH = -1e10; o.botLL = 1e10;
      for(int k = 0; k < botWid; k++)
        {
         o.botHH = MathMax(o.botHH, MathMax(FastBuf[i - botCtx - k], SlowBuf[i - botCtx - k]));
         o.botLL = MathMin(o.botLL, MathMin(FastBuf[i - botCtx - k], SlowBuf[i - botCtx - k]));
        }
     }
   if(topOK)
     {
      s.lastTopBar = i; s.lastTopWedge = i - topCtx; s.nTopSq++;
      o.topSq = true; o.topWid = topWid; o.topLft = i - topCtx - topWid + 1; o.topRgt = i - topCtx;
      o.topHH = -1e10; o.topLL = 1e10;
      for(int k = 0; k < topWid; k++)
        {
         o.topHH = MathMax(o.topHH, MathMax(FastBuf[i - topCtx - k], SlowBuf[i - topCtx - k]));
         o.topLL = MathMin(o.topLL, MathMin(FastBuf[i - topCtx - k], SlowBuf[i - topCtx - k]));
        }
     }
   //--- BITE 4: turns
   if(botOK) { s.botArmed = true; s.botArmBar = i; }
   if(topOK) { s.topArmed = true; s.topArmBar = i; }
   if(s.botArmed && i - s.botArmBar > TurnMax) s.botArmed = false;
   if(s.topArmed && i - s.topArmBar > TurnMax) s.topArmed = false;
   bool holdUp = true, holdDn = true;
   for(int k = 0; k <= TurnHold; k++)
     {
      if(!(FastBuf[i - k] > SlowBuf[i - k])) holdUp = false;
      if(!(FastBuf[i - k] < SlowBuf[i - k])) holdDn = false;
     }
   int j = i - TurnHold;
   bool crossedUpAt = FastBuf[j] > SlowBuf[j] && FastBuf[j - 1] <= SlowBuf[j - 1];
   bool crossedDnAt = FastBuf[j] < SlowBuf[j] && FastBuf[j - 1] >= SlowBuf[j - 1];
   o.crossUp = FastBuf[i] > SlowBuf[i] && FastBuf[i - 1] <= SlowBuf[i - 1];
   o.crossDn = FastBuf[i] < SlowBuf[i] && FastBuf[i - 1] >= SlowBuf[i - 1];
   // arming captured BEFORE the turn confirmation clears it (Pine armL / armS)
   o.armL = TurnOn && s.botArmed;
   o.armS = TurnOn && s.topArmed;
   bool botTurn = TurnOn && s.botArmed && crossedUpAt && holdUp;
   bool topTurn = TurnOn && s.topArmed && crossedDnAt && holdDn;
   if(botTurn) { s.botArmed = false; s.nBotTurn++; s.lastBotGap = j - s.lastBotWedge; o.turnUp = true; o.turnUpBar = j; }
   if(topTurn) { s.topArmed = false; s.nTopTurn++; s.lastTopGap = j - s.lastTopWedge; o.turnDn = true; o.turnDnBar = j; }
   //--- BITE 5: ticks
   double rng = high[i] - low[i];
   double upW = high[i] - MathMax(open[i], close[i]);
   double dnW = MathMin(open[i], close[i]) - low[i];
   double atr = AtrBuf[i];
   o.botTick = TickOn && rng > 0 && atr > 0 && dnW / rng >= BotWickRange && dnW / atr >= BotWickAtr;
   o.topTick = TickOn && rng > 0 && atr > 0 && upW / rng >= TopWickRange && upW / atr >= TopWickAtr;
   if(o.botTick) s.nBotTk++;
   if(o.topTick) s.nTopTk++;
   //--- BITE 6: CONT
   o.contUp = ContStep(i, 0, true,  s, o.contUpAge, open, high, low, close);
   bool dn  = ContStep(i, 1, false, s, o.contDnAge, open, high, low, close);
   o.contDn = ContMirror && dn;
   if(o.contUp) { s.nContUp++; s.lastContUpAge = o.contUpAge; }
   if(o.contDn) { s.nContDn++; s.lastContDnAge = o.contDnAge; }
  }
//+------------------------------------------------------------------+
//| BITE 7: close where fast would cross slow on the NEXT bar        |
//+------------------------------------------------------------------+
double CrossPriceAt(const int i, const double &close[])
  {
   if(!(SlowLen > FastLen)) return EMPTY_VALUE;
   int nF = MathMax(FastLen - 1, 1), nS = MathMax(SlowLen - 1, 1);
   if(i - nS < 0) return EMPTY_VALUE;
   double sumF = 0, sumS = 0;
   if(FastLen > 1) for(int k = 0; k < nF; k++) sumF += RsiBuf[i - k];
   for(int k = 0; k < nS; k++) sumS += RsiBuf[i - k];
   double rStar = (sumS / SlowLen - sumF / FastLen) / (1.0 / FastLen - 1.0 / SlowLen);
   if(!(rStar > 0.01 && rStar < 99.99)) return EMPTY_VALUE;
   double a   = RsiLen;
   double up1 = UpBuf[i] * (a - 1) / a;
   double dn1 = DnBuf[i] * (a - 1) / a;
   double rs  = rStar / (100 - rStar);
   double r0  = up1 + dn1 > 0 ? 100 * up1 / (up1 + dn1) : 50;
   if(rStar >= r0) return close[i] + a * (rs * dn1 - up1);
   return close[i] - a * (up1 / rs - dn1);
  }
//+------------------------------------------------------------------+
//| drawing helpers                                                  |
//+------------------------------------------------------------------+
void DrawBox(const string nm, const datetime t1, const double p1, const datetime t2, const double p2, const color clr)
  {
   if(g_win < 0) g_win = ChartWindowFind();
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_RECTANGLE, g_win, t1, p1, t2, p2);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FILL, true);
   ObjectSetInteger(0, nm, OBJPROP_BACK, true);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawText(const string nm, const int win, const datetime t, const double p, const string txt, const color clr, const int anchor)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, OBJ_TEXT, win, t, p);
   ObjectSetString(0, nm, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
void DrawPriceArrow(const string nm, const datetime t, const double p, const bool up, const color clr)
  {
   if(ObjectFind(0, nm) < 0) ObjectCreate(0, nm, up ? OBJ_ARROW_UP : OBJ_ARROW_DOWN, 0, t, p);
   ObjectSetInteger(0, nm, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, nm, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, nm, OBJPROP_ANCHOR, up ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetInteger(0, nm, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nm, OBJPROP_HIDDEN, true);
  }
//+------------------------------------------------------------------+
void WriteSig(const int i, const XpwSig &o)
  {
   SigBotSq[i]   = o.botSq   ? 1 : 0;
   SigTopSq[i]   = o.topSq   ? 1 : 0;
   SigTurnUp[i]  = o.turnUp  ? 1 : 0;
   SigTurnDn[i]  = o.turnDn  ? 1 : 0;
   SigBotTick[i] = o.botTick ? 1 : 0;
   SigTopTick[i] = o.topTick ? 1 : 0;
   SigContUp[i]  = o.contUp  ? 1 : 0;
   SigContDn[i]  = o.contDn  ? 1 : 0;
   CrossUpBuf[i] = o.crossUp ? 1 : 0;
   CrossDnBuf[i] = o.crossDn ? 1 : 0;
   ArmLBuf[i]    = o.armL    ? 1 : 0;
   ArmSBuf[i]    = o.armS    ? 1 : 0;
  }
void ClearSig(const int i)
  {
   SigBotSq[i] = 0; SigTopSq[i] = 0; SigTurnUp[i] = 0; SigTurnDn[i] = 0;
   SigBotTick[i] = 0; SigTopTick[i] = 0; SigContUp[i] = 0; SigContDn[i] = 0;
   CrossUpBuf[i] = 0; CrossDnBuf[i] = 0; ArmLBuf[i] = 0; ArmSBuf[i] = 0;
  }
//+------------------------------------------------------------------+
void CommitDraw(const int i, const XpwSig &o, const datetime &time[], const double &high[], const double &low[])
  {
   if(g_win < 0) g_win = ChartWindowFind();
   if(o.botSq)
     {
      BotSqArr[o.botRgt] = o.botLL - 2.0;
      if(ShowBoxes)
        {
         DrawBox(g_prefix + "bbox_" + (string)(long)time[i], time[o.botLft], o.botHH + 1.5, time[o.botRgt], o.botLL - 1.5, clrFireBrick);
         DrawText(g_prefix + "blbl_" + (string)(long)time[i], g_win, time[o.botRgt], o.botLL - 2.0, "BOT " + (string)o.botWid, clrRed, ANCHOR_UPPER);
        }
     }
   if(o.topSq)
     {
      TopSqArr[o.topRgt] = o.topHH + 2.0;
      if(ShowBoxes)
        {
         DrawBox(g_prefix + "tbox_" + (string)(long)time[i], time[o.topLft], o.topHH + 1.5, time[o.topRgt], o.topLL - 1.5, clrSeaGreen);
         DrawText(g_prefix + "tlbl_" + (string)(long)time[i], g_win, time[o.topRgt], o.topHH + 2.0, "TOP " + (string)o.topWid, clrLime, ANCHOR_LOWER);
        }
     }
   if(o.turnUp && ShowTurns) TurnUpArr[o.turnUpBar] = MathMin(FastBuf[o.turnUpBar], SlowBuf[o.turnUpBar]) - 3.0;
   if(o.turnDn && ShowTurns) TurnDnArr[o.turnDnBar] = MathMax(FastBuf[o.turnDnBar], SlowBuf[o.turnDnBar]) + 3.0;
   if(o.botTick && ShowTicks) DrawPriceArrow(g_prefix + "btk_" + (string)(long)time[i], time[i], low[i],  true,  clrYellow);
   if(o.topTick && ShowTicks) DrawPriceArrow(g_prefix + "ttk_" + (string)(long)time[i], time[i], high[i], false, clrOrange);
   if(o.contUp && ShowCont)
     {
      ContUpArr[i] = MathMin(FastBuf[i], SlowBuf[i]) - 3.0;
      DrawText(g_prefix + "cu_" + (string)(long)time[i], g_win, time[i], ContUpArr[i] - 2.0, "CONT " + (string)o.contUpAge + "b", clrAqua, ANCHOR_UPPER);
      DrawPriceArrow(g_prefix + "cup_" + (string)(long)time[i], time[i], low[i], true, clrAqua);
     }
   if(o.contDn && ShowCont)
     {
      ContDnArr[i] = MathMax(FastBuf[i], SlowBuf[i]) + 3.0;
      DrawText(g_prefix + "cd_" + (string)(long)time[i], g_win, time[i], ContDnArr[i] + 2.0, "CONT " + (string)o.contDnAge + "b", clrMagenta, ANCHOR_LOWER);
      DrawPriceArrow(g_prefix + "cdn_" + (string)(long)time[i], time[i], high[i], false, clrMagenta);
     }
  }
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   ArraySetAsSeries(time, false); ArraySetAsSeries(open, false); ArraySetAsSeries(high, false);
   ArraySetAsSeries(low, false);  ArraySetAsSeries(close, false);
   int wb = WarmUp();
   if(rates_total < wb + 2) return 0;

   int start;
   if(prev_calculated <= 0 || prev_calculated > rates_total)
     {
      ResetState();
      start = 0;
     }
   else start = prev_calculated - 1;

   //--- BITE 1 (+ ATR, predict): per-bar values, recomputed for the forming bar on every tick
   for(int i = start; i < rates_total; i++)
     {
      if(i > g_lastDone)
        {
         BotSqArr[i] = EMPTY_VALUE; TopSqArr[i] = EMPTY_VALUE; TurnUpArr[i] = EMPTY_VALUE;
         TurnDnArr[i] = EMPTY_VALUE; ContUpArr[i] = EMPTY_VALUE; ContDnArr[i] = EMPTY_VALUE;
        }
      // Wilder RSI (= Pine ta.rsi: rma of gains / rma of losses, SMA seed)
      if(i < RsiLen) { UpBuf[i] = 0; DnBuf[i] = 0; RsiBuf[i] = 50; }
      else
        {
         double up = MathMax(close[i] - close[i - 1], 0.0), dn = MathMax(close[i - 1] - close[i], 0.0);
         if(i == RsiLen)
           {
            double su = 0, sd = 0;
            for(int k = i - RsiLen + 1; k <= i; k++) { su += MathMax(close[k] - close[k - 1], 0.0); sd += MathMax(close[k - 1] - close[k], 0.0); }
            UpBuf[i] = su / RsiLen; DnBuf[i] = sd / RsiLen;
           }
         else
           {
            UpBuf[i] = (UpBuf[i - 1] * (RsiLen - 1) + up) / RsiLen;
            DnBuf[i] = (DnBuf[i - 1] * (RsiLen - 1) + dn) / RsiLen;
           }
         RsiBuf[i] = DnBuf[i] == 0 ? 100 : (UpBuf[i] == 0 ? 0 : 100 - 100 / (1 + UpBuf[i] / DnBuf[i]));
        }
      // SMA fast / slow of RSI
      if(i < RsiLen + SlowLen) { FastBuf[i] = EMPTY_VALUE; SlowBuf[i] = EMPTY_VALUE; FillA[i] = EMPTY_VALUE; FillB[i] = EMPTY_VALUE; IsRedBuf[i] = 0; }
      else
        {
         double sf = 0, ss = 0;
         for(int k = 0; k < FastLen; k++) sf += RsiBuf[i - k];
         for(int k = 0; k < SlowLen; k++) ss += RsiBuf[i - k];
         FastBuf[i] = sf / FastLen; SlowBuf[i] = ss / SlowLen;
         FillA[i] = FastBuf[i]; FillB[i] = SlowBuf[i];
         bool red = InvertFill ? FastBuf[i] > SlowBuf[i] : FastBuf[i] < SlowBuf[i];
         IsRedBuf[i] = red ? 1 : 0;
        }
      // Wilder ATR (= Pine ta.atr)
      if(i < AtrLen) AtrBuf[i] = 0;
      else
        {
         double tr = MathMax(high[i] - low[i], MathMax(MathAbs(high[i] - close[i - 1]), MathAbs(low[i] - close[i - 1])));
         if(i == AtrLen)
           {
            double s = 0;
            for(int k = i - AtrLen + 1; k <= i; k++) s += MathMax(high[k] - low[k], MathMax(MathAbs(high[k] - close[k - 1]), MathAbs(low[k] - close[k - 1])));
            AtrBuf[i] = s / AtrLen;
           }
         else AtrBuf[i] = (AtrBuf[i - 1] * (AtrLen - 1) + tr) / AtrLen;
        }
      PredictPx[i] = (i >= RsiLen + SlowLen) ? CrossPriceAt(i, close) : EMPTY_VALUE;
     }

   //--- BITES 3-6: detection. Closed bars commit state once; the forming bar only previews.
   for(int i = start; i < rates_total; i++)
     {
      if(i < wb) { ClearSig(i); continue; }
      bool closed = (i <= rates_total - 2);
      XpwSig o;
      if(closed)
        {
         if(i <= g_lastDone) continue;
         Step(i, g_state, o, open, high, low, close);
         WriteSig(i, o);
         CommitDraw(i, o, time, high, low);
         g_lastDone = i;
        }
      else if(PreviewFormingBar)
        {
         XpwState tmp = g_state;
         Step(i, tmp, o, open, high, low, close);
         WriteSig(i, o);
        }
      else ClearSig(i);
     }

   //--- BITE 8: panel
   if(ShowPanel)
     {
      int i = rates_total - 1;
      string txt = "XPW Shape Map v0.7" + (AllOn ? " ALL" : "") + "   " + (IsRedAt(i) ? "RED" : "LIME") + "\n";
      double pw = PosWAt(i);
      txt += "Area pos " + DoubleToString(pw, 2) + (pw <= LoFrac ? " LOW" : (pw >= HiFrac ? " HIGH" : " MID")) + "\n";
      txt += "BOT squares " + (string)g_state.nBotSq + "   TOP squares " + (string)g_state.nTopSq + "\n";
      txt += "BOT turns " + (string)g_state.nBotTurn + " (gap " + (string)g_state.lastBotGap + "b)   TOP turns " + (string)g_state.nTopTurn + " (gap " + (string)g_state.lastTopGap + "b)\n";
      txt += "BOT ticks " + (string)g_state.nBotTk + "   TOP ticks " + (string)g_state.nTopTk + "\n";
      txt += "CONT up " + (string)g_state.nContUp + " (big " + (string)g_state.lastContUpAge + "b ago)   CONT down " + (ContMirror ? (string)g_state.nContDn : "off") + "\n";
      Comment(txt);
     }
   return rates_total;
  }
//+------------------------------------------------------------------+
