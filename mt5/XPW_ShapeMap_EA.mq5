//+------------------------------------------------------------------+
//| XPW Shape Map v0.6 — MT5 Expert Advisor                          |
//| Port of xpw_shape_map_v0.6_strategy.pine (Turn ▲/▼, Predict).    |
//| Presets calibrated on VT Markets MT5 ticks (real bid/ask,        |
//| ECN commission). See mt5/README.md for the numbers.              |
//+------------------------------------------------------------------+
#property copyright "XPW"
#property version   "1.20"
#property description "XPW Shape Map v0.6 Turn-Predict EA. 9 presets for XAUUSD / BTCUSD, swept on 9 weeks of VT Markets ticks."

#include <Trade/Trade.mqh>

//--- how it trades (same as the Pine strategy, Turn ▲/▼ + Predict entry)
// 1. TDI: RSI(rsiLen) -> fast = SMA(RSI, fastLen), slow = SMA(RSI, slowLen).
// 2. A BOT square (odd red wedge: fast > slow for 1..3 bars inside fast < slow)
//    arms a LONG for turnMax bars; a TOP square (odd lime wedge) arms a SHORT.
// 3. At every bar close, while armed and the lines have not crossed yet, the
//    EA calculates the exact price at which fast and slow would cross on the
//    next bar, and holds a virtual stop there. The first tick that reaches it
//    (Ask for buys, Bid for sells) sends a market order. An open opposite
//    position is closed first (reverse).
// 4. Exits: broker-side SL = slAtr x distance unit of the signal bar, or
//    (swing mode) just beyond the lowest low / highest high of the last N
//    bars. Units: ATR(14), ATR(50), average high-low range(14) or Donchian(20)
//    width, rescaled to the median ATR(14) so multipliers stay comparable.
//    Trailing stop starts when price has moved actAtr x unit in favour and
//    then follows the best price at disAtr x unit (server SL is moved).
//    Optional TP = tpR x SL. Optional time stop: close after N bars.
//    "Cross failed" (optional): if within turnHold bars of entry the bar
//    closes with the lines back on the wrong side, close at market.
// Virtual stops (not broker pending orders) are used so behaviour is the same
// on hedging and netting accounts and identical to the tick calibration.

enum EPreset
  {
   // PF = profit factor on 9 weeks of VT Markets ticks (Jul-Oct 2026), blocks = 4 time blocks
   PRESET_GOLD_M30 = 0,   // Gold M30 - PF 1.37, lost one block (not recommended)
   PRESET_GOLD_M15 = 1,   // * Gold M15 - PF 1.35, all 4 blocks 1.25-1.44 (recommended)
   PRESET_BTC_M30  = 2,   // BTC M30 - PF 1.24, lost one block (not recommended)
   PRESET_CUSTOM   = 3,   // Custom (inputs below)
   PRESET_GOLD_M30_SWING = 4, // * Gold M30 swing stop - PF 1.71, all blocks > 1.2
   PRESET_GOLD_M15_TIME  = 5, // * Gold M15 time stop 24 - PF 1.29, all blocks 1.25-1.31
   PRESET_BTC_M15        = 6, // BTC M15 time stop 24 - PF 1.46, one block 0.98 (experimental)
   PRESET_BTC_M30_ATR50  = 7, // * BTC M30 ATR(50) - PF 1.38, all blocks > 1.07
   PRESET_GOLD_H1_SWING  = 8, // Gold H1 swing-20 stop - PF 3.31, 33 trades (experimental)
   PRESET_BTC_H1_RANGE   = 9  // * BTC H1 average-range - PF 2.28, all blocks > 1.45, 50 trades
  };

enum EUnit
  {
   UNIT_ATR14    = 0,   // ATR(14)
   UNIT_ATR50    = 1,   // ATR(50) - slow
   UNIT_RANGE14  = 2,   // Average high-low range (14)
   UNIT_DONCH20  = 3    // Donchian(20) width
  };

enum ESlMode
  {
   SL_UNIT  = 0,   // SL = multiple of the distance unit
   SL_SWING = 1    // SL behind the swing low / high of the last N bars
  };

enum EDir
  {
   DIR_BOTH  = 0,   // Both
   DIR_LONG  = 1,   // Long only
   DIR_SHORT = 2    // Short only
  };

input group "Preset & risk"
input EPreset InpPreset      = PRESET_GOLD_M15; // Preset
input double  InpRiskPct     = 0.5;             // Risk % of equity per trade (distance to SL)
input double  InpFixedLots   = 0.0;             // Fixed lots (>0 overrides risk %)
input double  InpMaxLots     = 5.0;             // Max lots per trade
input EDir    InpDirection   = DIR_BOTH;        // Trade direction
input bool    InpEnforceTF   = true;            // Only trade on the preset's timeframe
input double  InpMaxSpread   = 0.0;             // Max spread in price (0 = preset default)
input long    InpMagic       = 20260601;        // Magic number
input string  InpComment     = "XPW-SM6";       // Order comment

input group "Custom preset (used only when Preset = Custom)"
input ENUM_TIMEFRAMES InpCTF = PERIOD_M30;      // Timeframe
input int    InpCRsiLen      = 14;              // RSI length
input int    InpCFastLen     = 2;               // Fast MA length
input int    InpCSlowLen     = 7;               // Slow MA length
input int    InpCTurnMax     = 12;              // Max bars to wait after a square
input int    InpCTurnHold    = 2;               // Bars the cross must hold
input bool   InpCFailExit    = true;            // Exit if the cross fails to hold
input EUnit  InpCUnit        = UNIT_ATR14;      // Distance unit for SL / trail
input ESlMode InpCSlMode     = SL_UNIT;         // Stop-loss placement
input int    InpCSwingN      = 5;               // Swing SL: bars to look back
input int    InpCTimeStop    = 0;               // Time stop, bars (0 = off)
input double InpCSlAtr       = 3.0;             // Stop loss, unit multiple
input double InpCTpR         = 0.0;             // Take profit, R multiple of SL (0 = off)
input double InpCActAtr      = 1.0;             // Trail activation, unit multiple
input double InpCDisAtr      = 1.5;             // Trail distance, unit multiple (0 = no trail)
input double InpCMaxSpread   = 0.30;            // Max spread in price

input group "Detection (same defaults as the Pine script)"
input int    InpAtrLen       = 14;              // ATR length (exits)
input int    InpBotMaxW      = 3;               // BOT square max width
input int    InpTopMaxW      = 2;               // TOP square max width
input int    InpCtx          = 1;               // Context bars (ALL mode)

//--- effective parameters
struct SParams
  {
   ENUM_TIMEFRAMES tf;
   int    rsiLen, fastLen, slowLen, turnMax, turnHold;
   bool   failExit;
   double slAtr, tpR, actAtr, disAtr, maxSpread;
   EUnit  unit;
   ESlMode slMode;
   int    swingN, timeStop;
   string name;
  };
SParams P;

CTrade  trade;
datetime g_lastBar   = 0;
int      g_pendDir   = 0;      // virtual stop: +1 buy, -1 sell, 0 none
double   g_pendPx    = 0.0;
double   g_pendAtr   = 0.0;      // trail unit of the signal bar
double   g_pendSl    = 0.0;      // SL distance of the signal bar
double   g_lastFast  = 0.0, g_lastSlow = 0.0;
bool     g_botArmed  = false, g_topArmed = false;
bool     g_tfOK      = true;

//+------------------------------------------------------------------+
void LoadPreset()
  {
   P.unit = UNIT_ATR14; P.slMode = SL_UNIT; P.swingN = 5; P.timeStop = 0;
   switch(InpPreset)
     {
      case PRESET_GOLD_M30:
         P.tf = PERIOD_M30; P.rsiLen = 14; P.fastLen = 2; P.slowLen = 7; P.turnMax = 12; P.turnHold = 2;
         P.failExit = true;  P.slAtr = 3.0; P.tpR = 0.0; P.actAtr = 1.0; P.disAtr = 1.5; P.maxSpread = 0.30;
         P.name = "Gold M30"; break;
      case PRESET_GOLD_M15:
         P.tf = PERIOD_M15; P.rsiLen = 21; P.fastLen = 2; P.slowLen = 5; P.turnMax = 6; P.turnHold = 2;
         P.failExit = false; P.slAtr = 2.0; P.tpR = 0.0; P.actAtr = 1.0; P.disAtr = 0.5; P.maxSpread = 0.30;
         P.name = "Gold M15"; break;
      case PRESET_BTC_M30:
         P.tf = PERIOD_M30; P.rsiLen = 21; P.fastLen = 2; P.slowLen = 5; P.turnMax = 6; P.turnHold = 2;
         P.failExit = false; P.slAtr = 3.0; P.tpR = 0.0; P.actAtr = 1.5; P.disAtr = 0.75; P.maxSpread = 25.0;
         P.name = "BTC M30"; break;
      case PRESET_GOLD_M30_SWING:
         P.tf = PERIOD_M30; P.rsiLen = 10; P.fastLen = 2; P.slowLen = 10; P.turnMax = 12; P.turnHold = 2;
         P.failExit = true;  P.slMode = SL_SWING; P.swingN = 5; P.slAtr = 0; P.tpR = 0.0;
         P.actAtr = 2.0; P.disAtr = 2.0; P.maxSpread = 0.30;
         P.name = "Gold M30 swing"; break;
      case PRESET_GOLD_M15_TIME:
         P.tf = PERIOD_M15; P.rsiLen = 21; P.fastLen = 2; P.slowLen = 5; P.turnMax = 6; P.turnHold = 1;
         P.failExit = false; P.slAtr = 1.5; P.tpR = 0.0; P.actAtr = 1.0; P.disAtr = 0.75; P.timeStop = 24;
         P.maxSpread = 0.30; P.name = "Gold M15 time"; break;
      case PRESET_BTC_M15:   // swept on Jul-Oct ticks (replaces the M15 range preset, which failed out of sample)
         P.tf = PERIOD_M15; P.rsiLen = 21; P.fastLen = 2; P.slowLen = 10; P.turnMax = 6; P.turnHold = 1;
         P.failExit = false; P.slAtr = 4.0; P.tpR = 0.0; P.actAtr = 0.0; P.disAtr = 0.0; P.timeStop = 24;
         P.maxSpread = 25.0; P.name = "BTC M15 time"; break;
      case PRESET_GOLD_H1_SWING:
         P.tf = PERIOD_H1; P.rsiLen = 14; P.fastLen = 3; P.slowLen = 7; P.turnMax = 24; P.turnHold = 2;
         P.failExit = true;  P.slMode = SL_SWING; P.swingN = 20; P.slAtr = 0; P.tpR = 0.0;
         P.actAtr = 0.0; P.disAtr = 1.5; P.maxSpread = 0.30;
         P.name = "Gold H1 swing"; break;
      case PRESET_BTC_H1_RANGE:
         P.tf = PERIOD_H1; P.rsiLen = 14; P.fastLen = 2; P.slowLen = 10; P.turnMax = 6; P.turnHold = 1;
         P.failExit = false; P.unit = UNIT_RANGE14; P.slAtr = 1.0; P.tpR = 0.0; P.actAtr = 1.0; P.disAtr = 2.0;
         P.maxSpread = 25.0; P.name = "BTC H1 range"; break;
      case PRESET_BTC_M30_ATR50:
         P.tf = PERIOD_M30; P.rsiLen = 21; P.fastLen = 2; P.slowLen = 5; P.turnMax = 6; P.turnHold = 1;
         P.failExit = false; P.unit = UNIT_ATR50; P.slAtr = 4.0; P.tpR = 0.0; P.actAtr = 2.0; P.disAtr = 0.5;
         P.maxSpread = 25.0; P.name = "BTC M30 ATR50"; break;
      default:
         P.tf = InpCTF; P.rsiLen = InpCRsiLen; P.fastLen = InpCFastLen; P.slowLen = InpCSlowLen;
         P.turnMax = InpCTurnMax; P.turnHold = InpCTurnHold; P.failExit = InpCFailExit;
         P.slAtr = InpCSlAtr; P.tpR = InpCTpR; P.actAtr = InpCActAtr; P.disAtr = InpCDisAtr;
         P.maxSpread = InpCMaxSpread; P.unit = InpCUnit; P.slMode = InpCSlMode;
         P.swingN = MathMax(InpCSwingN, 1); P.timeStop = InpCTimeStop; P.name = "Custom"; break;
     }
   if(InpMaxSpread > 0) P.maxSpread = InpMaxSpread;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   LoadPreset();
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);
   g_tfOK = !InpEnforceTF || _Period == P.tf;
   if(!g_tfOK)
      PrintFormat("XPW: preset %s is calibrated for %s, chart is %s. No trades (set 'Only trade on the preset's timeframe' = false to override).",
                  P.name, EnumToString(P.tf), EnumToString((ENUM_TIMEFRAMES)_Period));
   string sym = _Symbol;
   StringToUpper(sym);
   bool goldPreset = InpPreset == PRESET_GOLD_M30 || InpPreset == PRESET_GOLD_M15 || InpPreset == PRESET_GOLD_M30_SWING || InpPreset == PRESET_GOLD_M15_TIME || InpPreset == PRESET_GOLD_H1_SWING;
   bool btcPreset  = InpPreset == PRESET_BTC_M30 || InpPreset == PRESET_BTC_M15 || InpPreset == PRESET_BTC_M30_ATR50 || InpPreset == PRESET_BTC_H1_RANGE;
   if(goldPreset && StringFind(sym, "XAU") < 0)
      PrintFormat("XPW: warning - gold preset on %s", _Symbol);
   if(btcPreset && StringFind(sym, "BTC") < 0)
      PrintFormat("XPW: warning - BTC preset on %s", _Symbol);
   g_lastBar = 0;
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { Comment(""); }

//+------------------------------------------------------------------+
//| Indicator maths on closed bars (chronological arrays, last = the |
//| bar that just closed).                                           |
//+------------------------------------------------------------------+
struct SSignal
  {
   bool   ok;
   bool   wantL, wantS;
   double xPx, fast, slow, atr;
   double unit;          // trail unit (price) of this bar
   double slL, slS;      // SL distance for a long / short placed now
  };

double Median(const double &src[], int from, int n)
  {
   double v[]; int m = 0;
   ArrayResize(v, n);
   for(int i = from; i < n; i++) if(src[i] != EMPTY_VALUE && src[i] > 0) v[m++] = src[i];
   if(m == 0) return 0;
   ArrayResize(v, m);
   ArraySort(v);
   return m % 2 == 1 ? v[m / 2] : 0.5 * (v[m / 2 - 1] + v[m / 2]);
  }

void Rma(const double &src[], double &dst[], int len, int n)
  {
   ArrayResize(dst, n);
   ArrayInitialize(dst, EMPTY_VALUE);
   double s = 0; int cnt = 0; bool seeded = false; double prev = 0;
   for(int i = 0; i < n; i++)
     {
      if(src[i] == EMPTY_VALUE) continue;
      if(!seeded)
        {
         s += src[i]; cnt++;
         if(cnt == len) { prev = s / len; dst[i] = prev; seeded = true; }
        }
      else
        {
         prev = (prev * (len - 1) + src[i]) / len;
         dst[i] = prev;
        }
     }
  }

void Sma(const double &src[], double &dst[], int len, int n)
  {
   ArrayResize(dst, n);
   ArrayInitialize(dst, EMPTY_VALUE);
   for(int i = len - 1; i < n; i++)
     {
      double s = 0; bool ok = true;
      for(int k = 0; k < len; k++) { if(src[i - k] == EMPTY_VALUE) { ok = false; break; } s += src[i - k]; }
      if(ok) dst[i] = s / len;
     }
  }

bool Valid(const double &f[], const double &s[], int i) { return i >= 0 && f[i] != EMPTY_VALUE && s[i] != EMPTY_VALUE; }
bool IsRed(const double &f[], const double &s[], int i)  { return Valid(f, s, i) && f[i] > s[i]; }   // fast > slow
bool IsLime(const double &f[], const double &s[], int i) { return !IsRed(f, s, i); }

// Wedge detector, same as Pine detect(): pattern ending at bar i.
bool Detect(const double &f[], const double &s[], int i, bool redWedge, int maxW, int ctx)
  {
   for(int w = 1; w <= maxW; w++)
     {
      if(i - (ctx + w + ctx - 1) < 0) return false;
      bool ok = true;
      for(int k = 0; k < ctx && ok; k++)      ok = redWedge ? IsLime(f, s, i - k) : IsRed(f, s, i - k);
      for(int k = 0; k < w && ok; k++)        ok = redWedge ? IsRed(f, s, i - ctx - k) : IsLime(f, s, i - ctx - k);
      for(int k = 0; k < ctx && ok; k++)      ok = redWedge ? IsLime(f, s, i - ctx - w - k) : IsRed(f, s, i - ctx - w - k);
      if(ok) return true;
     }
   return false;
  }

bool CrossUp(const double &f[], const double &s[], int i)   { return i >= 1 && Valid(f, s, i) && Valid(f, s, i - 1) && f[i] > s[i] && f[i - 1] <= s[i - 1]; }
bool CrossDn(const double &f[], const double &s[], int i)   { return i >= 1 && Valid(f, s, i) && Valid(f, s, i - 1) && f[i] < s[i] && f[i - 1] >= s[i - 1]; }

void Compute(SSignal &out)
  {
   out.ok = false; out.wantL = false; out.wantS = false; out.xPx = 0; out.fast = 0; out.slow = 0; out.atr = 0;
   out.unit = 0; out.slL = 0; out.slS = 0;
   int n = MathMin(Bars(_Symbol, _Period) - 1, 1500);
   if(n < 100) return;
   MqlRates rt[];
   ArraySetAsSeries(rt, false);
   if(CopyRates(_Symbol, _Period, 1, n, rt) != n) return;   // shift 1 = last closed bar, oldest first

   double c[], up[], dn[], upR[], dnR[], r[], fast[], slow[], tr[], atr[];
   ArrayResize(c, n); ArrayResize(up, n); ArrayResize(dn, n); ArrayResize(r, n); ArrayResize(tr, n);
   for(int i = 0; i < n; i++)
     {
      c[i] = rt[i].close;
      if(i == 0) { up[i] = EMPTY_VALUE; dn[i] = EMPTY_VALUE; tr[i] = rt[i].high - rt[i].low; continue; }
      double ch = c[i] - c[i - 1];
      up[i] = MathMax(ch, 0); dn[i] = MathMax(-ch, 0);
      tr[i] = MathMax(rt[i].high - rt[i].low, MathMax(MathAbs(rt[i].high - c[i - 1]), MathAbs(rt[i].low - c[i - 1])));
     }
   Rma(up, upR, P.rsiLen, n);
   Rma(dn, dnR, P.rsiLen, n);
   Rma(tr, atr, InpAtrLen, n);
   for(int i = 0; i < n; i++)
     {
      if(upR[i] == EMPTY_VALUE || dnR[i] == EMPTY_VALUE) { r[i] = EMPTY_VALUE; continue; }
      r[i] = dnR[i] == 0 ? 100.0 : (upR[i] == 0 ? 0.0 : 100.0 - 100.0 / (1.0 + upR[i] / dnR[i]));
     }
   Sma(r, fast, P.fastLen, n);
   Sma(r, slow, P.slowLen, n);

   // replay arming state over the window (arming only lasts turnMax bars)
   bool bA = false, tA = false; int bBar = 0, tBar = 0;
   for(int i = 0; i < n; i++)
     {
      if(Detect(fast, slow, i, true,  InpBotMaxW, InpCtx)) { bA = true; bBar = i; }
      if(Detect(fast, slow, i, false, InpTopMaxW, InpCtx)) { tA = true; tBar = i; }
      if(bA && i - bBar > P.turnMax) bA = false;
      if(tA && i - tBar > P.turnMax) tA = false;
      if(i >= P.turnHold)
        {
         bool holdUp = true, holdDn = true;
         for(int k = 0; k <= P.turnHold; k++)
           {
            if(!(Valid(fast, slow, i - k) && fast[i - k] > slow[i - k])) holdUp = false;
            if(!(Valid(fast, slow, i - k) && fast[i - k] < slow[i - k])) holdDn = false;
           }
         if(bA && CrossUp(fast, slow, i - P.turnHold) && holdUp) bA = false;
         if(tA && CrossDn(fast, slow, i - P.turnHold) && holdDn) tA = false;
        }
     }
   int L = n - 1;
   if(!Valid(fast, slow, L) || atr[L] == EMPTY_VALUE) return;
   g_botArmed = bA; g_topArmed = tA;

   // predicted cross price for the next bar
   double px = 0; bool havePx = false;
   if(P.slowLen > P.fastLen && upR[L] != EMPTY_VALUE && dnR[L] != EMPTY_VALUE)
     {
      double sumF = 0, sumS = 0; bool ok = true;
      for(int k = 0; k < P.fastLen - 1; k++) { if(r[L - k] == EMPTY_VALUE) ok = false; else sumF += r[L - k]; }
      for(int k = 0; k < MathMax(P.slowLen - 1, 1); k++) { if(r[L - k] == EMPTY_VALUE) ok = false; else sumS += r[L - k]; }
      if(ok)
        {
         double rStar = (sumS / P.slowLen - sumF / P.fastLen) / (1.0 / P.fastLen - 1.0 / P.slowLen);
         if(rStar > 0.01 && rStar < 99.99)
           {
            double a = P.rsiLen;
            double up1 = upR[L] * (a - 1) / a, dn1 = dnR[L] * (a - 1) / a;
            double rs = rStar / (100 - rStar);
            double r0 = up1 + dn1 > 0 ? 100 * up1 / (up1 + dn1) : 50;
            px = rStar >= r0 ? c[L] + a * (rs * dn1 - up1) : c[L] - a * (up1 / rs - dn1);
            havePx = px > 0;
           }
        }
     }
   out.ok    = true;
   out.fast  = fast[L];
   out.slow  = slow[L];
   out.atr   = atr[L];
   out.xPx   = px;
   out.wantL = havePx && bA && fast[L] < slow[L];
   out.wantS = havePx && tA && fast[L] > slow[L];

   // distance unit, rescaled to the same median as ATR(14) over the window,
   // so multipliers mean "x typical ATR" (as in the calibration)
   double u[];
   ArrayResize(u, n);
   ArrayInitialize(u, EMPTY_VALUE);
   if(P.unit == UNIT_ATR50)
      Rma(tr, u, 50, n);
   else if(P.unit == UNIT_RANGE14)
     {
      double hl[]; ArrayResize(hl, n);
      for(int i = 0; i < n; i++) hl[i] = rt[i].high - rt[i].low;
      Sma(hl, u, 14, n);
     }
   else if(P.unit == UNIT_DONCH20)
     {
      for(int i = 19; i < n; i++)
        {
         double hh = rt[i].high, ll = rt[i].low;
         for(int k = 1; k < 20; k++) { hh = MathMax(hh, rt[i - k].high); ll = MathMin(ll, rt[i - k].low); }
         u[i] = hh - ll;
        }
     }
   double unitVal = atr[L];
   if(P.unit != UNIT_ATR14 && u[L] != EMPTY_VALUE)
     {
      double mA = Median(atr, 0, n), mU = Median(u, 0, n);
      if(mA > 0 && mU > 0) unitVal = u[L] * mA / mU;
     }
   if(P.slMode == SL_SWING)
     {
      double ll = rt[L].low, hh = rt[L].high;
      for(int k = 1; k < P.swingN && L - k >= 0; k++) { ll = MathMin(ll, rt[L - k].low); hh = MathMax(hh, rt[L - k].high); }
      double x = havePx ? px : c[L];
      out.slL  = MathMax(x - ll + 0.1 * atr[L], 0.3 * atr[L]);
      out.slS  = MathMax(hh - x + 0.1 * atr[L], 0.3 * atr[L]);
      out.unit = atr[L];
     }
   else
     {
      out.slL  = P.slAtr * unitVal;
      out.slS  = out.slL;
      out.unit = unitVal;
     }
  }

//+------------------------------------------------------------------+
//| Position helpers (one position per symbol + magic)               |
//+------------------------------------------------------------------+
int  PosDir(ulong &ticket)
  {
   ticket = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ticket = t;
      return PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? 1 : -1;
     }
   return 0;
  }

void CloseAll()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      trade.PositionClose(t);
     }
  }

string GvAtr(ulong t)  { return "XPW_ATR_"  + (string)t; }
string GvBest(ulong t) { return "XPW_BEST_" + (string)t; }

double NormPx(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

double CalcLots(double slDist)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = MathMin(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), InpMaxLots);
   double lots = InpFixedLots;
   if(lots <= 0)
     {
      double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tv <= 0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tv <= 0 || ts <= 0 || slDist <= 0) return 0;
      double lossPerLot = slDist / ts * tv;
      lots = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0 / lossPerLot;
     }
   lots = MathFloor(lots / step) * step;          // round DOWN: never risk more than asked
   if(lots < vmin) return 0;                      // too small for the account -> skip
   return NormalizeDouble(MathMin(lots, vmax), 8);
  }

//+------------------------------------------------------------------+
void Enter(int dir, double slDist, double atrSig)
  {
   ulong t; int pos = PosDir(t);
   if(pos == dir) return;
   if(pos != 0) CloseAll();                       // reverse
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return;
   double px = dir == 1 ? tk.ask : tk.bid;
   double minDist = (SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) + 1) * _Point;
   slDist = MathMax(slDist, minDist);
   double lots = CalcLots(slDist);
   if(lots <= 0) { PrintFormat("XPW: lot size below minimum for %.2f%% risk, entry skipped", InpRiskPct); return; }
   double sl = NormPx(px - dir * slDist);
   double tp = P.tpR > 0 ? NormPx(px + dir * P.tpR * slDist) : 0.0;
   bool ok = dir == 1 ? trade.Buy(lots, _Symbol, 0, sl, tp, InpComment + " L")
                      : trade.Sell(lots, _Symbol, 0, sl, tp, InpComment + " S");
   if(!ok) { PrintFormat("XPW: order failed %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()); return; }
   ulong nt; if(PosDir(nt) == dir && nt > 0)
     {
      GlobalVariableSet(GvAtr(nt), atrSig);
      GlobalVariableSet(GvBest(nt), dir == 1 ? tk.bid : tk.ask);
     }
  }

void ManageTrail()
  {
   if(P.disAtr <= 0) return;
   ulong t; int pos = PosDir(t);
   if(pos == 0 || !PositionSelectByTicket(t)) return;
   if(!GlobalVariableCheck(GvAtr(t))) return;
   double atrE = GlobalVariableGet(GvAtr(t));
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double cur  = PositionGetDouble(POSITION_SL);
   double tp   = PositionGetDouble(POSITION_TP);
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return;
   double best = GlobalVariableCheck(GvBest(t)) ? GlobalVariableGet(GvBest(t)) : (pos == 1 ? tk.bid : tk.ask);
   double stops = (SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) + 1) * _Point;
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(pos == 1)
     {
      if(tk.bid > best) { best = tk.bid; GlobalVariableSet(GvBest(t), best); }
      if(best >= open + P.actAtr * atrE)
        {
         double nsl = NormPx(best - P.disAtr * atrE);
         if(nsl > cur + ts && nsl <= tk.bid - stops) trade.PositionModify(t, nsl, tp);
        }
     }
   else
     {
      if(tk.ask < best) { best = tk.ask; GlobalVariableSet(GvBest(t), best); }
      if(best <= open - P.actAtr * atrE)
        {
         double nsl = NormPx(best + P.disAtr * atrE);
         if((cur == 0 || nsl < cur - ts) && nsl >= tk.ask + stops) trade.PositionModify(t, nsl, tp);
        }
     }
  }

//+------------------------------------------------------------------+
void OnNewBar()
  {
   SSignal s;
   Compute(s);
   g_pendDir = 0;
   if(!s.ok) return;
   g_lastFast = s.fast; g_lastSlow = s.slow;
   ulong t; int pos = PosDir(t);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   bool canL = g_tfOK && InpDirection != DIR_SHORT;
   bool canS = g_tfOK && InpDirection != DIR_LONG;
   // Pine order: set the stop with the position as of the close, then "cross failed".
   if(s.wantL && canL && pos <= 0)      { g_pendDir = 1;  g_pendPx = MathCeil(s.xPx / ts) * ts;  g_pendAtr = s.unit; g_pendSl = s.slL; }
   else if(s.wantS && canS && pos >= 0) { g_pendDir = -1; g_pendPx = MathFloor(s.xPx / ts) * ts; g_pendAtr = s.unit; g_pendSl = s.slS; }
   if(pos != 0 && PositionSelectByTicket(t))
     {
      int entryShift = iBarShift(_Symbol, _Period, (datetime)PositionGetInteger(POSITION_TIME));
      int held = entryShift - 1;               // bars from the entry bar to the bar that just closed
      bool closeIt = false;
      if(P.failExit && held >= 0 && held <= P.turnHold)
         if((pos == 1 && s.fast <= s.slow) || (pos == -1 && s.fast >= s.slow)) closeIt = true;
      if(!closeIt && P.timeStop > 0 && held >= 0 && held + 1 >= P.timeStop) closeIt = true;
      if(closeIt) trade.PositionClose(t);
     }
  }

void OnTick()
  {
   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt != g_lastBar)
     {
      g_lastBar = bt;
      OnNewBar();
     }
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;
   double spread = tk.ask - tk.bid;
   if(g_pendDir != 0 && spread <= P.maxSpread)
     {
      if(g_pendDir == 1 && tk.ask >= g_pendPx)       { int d = g_pendDir; g_pendDir = 0; Enter(d, g_pendSl, g_pendAtr); }
      else if(g_pendDir == -1 && tk.bid <= g_pendPx) { int d = g_pendDir; g_pendDir = 0; Enter(d, g_pendSl, g_pendAtr); }
     }
   ManageTrail();
   string unitName = P.unit == UNIT_ATR50 ? "ATR50" : P.unit == UNIT_RANGE14 ? "Range14" : P.unit == UNIT_DONCH20 ? "Donch20" : "ATR14";
   string slTxt = P.slMode == SL_SWING ? StringFormat("swing %d bars", P.swingN) : StringFormat("%.1f x %s", P.slAtr, unitName);
   Comment(StringFormat("XPW Shape Map EA  |  %s %s\nTF %s   spread %.2f (max %.2f)\nArmed  BOT %s  TOP %s\nStop  %s %.2f\nRisk %.2f%%  SL %s  trail %.1f / %.2f x %s  cross-failed %s  time stop %d",
                        P.name, g_tfOK ? "" : "(WRONG TIMEFRAME - not trading)",
                        EnumToString((ENUM_TIMEFRAMES)_Period), spread, P.maxSpread,
                        g_botArmed ? "yes" : "no", g_topArmed ? "yes" : "no",
                        g_pendDir == 1 ? "BUY at" : g_pendDir == -1 ? "SELL at" : "none", g_pendDir != 0 ? g_pendPx : 0.0,
                        InpRiskPct, slTxt, P.actAtr, P.disAtr, P.slMode == SL_SWING ? "ATR14" : unitName, P.failExit ? "on" : "off", P.timeStop));
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)
  {
   // tidy up global variables of closed positions
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD && trans.position > 0 && !PositionSelectByTicket(trans.position))
     {
      GlobalVariableDel(GvAtr(trans.position));
      GlobalVariableDel(GvBest(trans.position));
     }
  }
//+------------------------------------------------------------------+
