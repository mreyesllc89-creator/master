//+------------------------------------------------------------------+
//|                                                  RegimeGauge.mqh |
//|              Semicircular CCanvas gauge for the RegimeTrend state|
//+------------------------------------------------------------------+
//| Only functions that actually exist in Include/Canvas/Canvas.mqh  |
//| are used here: CreateBitmapLabel, Erase, FillRectangle,          |
//| FillTriangle, FillCircle, PolylineAA, LineAA, CircleAA,          |
//| LineThick, FontSet, TextOut, TextWidth, Update, Destroy. The     |
//| band is drawn as a triangle strip with anti-aliased rims, which  |
//| gives a clean arc without depending on Pie() angle conventions.  |
//|                                                                  |
//| Render() is cheap but it is still never called on every tick:    |
//| the host indicator calls it on a new bar, on a state change and  |
//| on CHARTEVENT_CHART_CHANGE only.                                 |
//+------------------------------------------------------------------+
#property copyright "MQL5-Foundry"
#property strict

#include <Canvas\Canvas.mqh>
#include "RegimeTypes.mqh"
#include "XPWorxLogo.mqh"

//+------------------------------------------------------------------+
//| Class CRegimeGauge                                               |
//+------------------------------------------------------------------+
class CRegimeGauge
  {
private:
   CCanvas           m_canvas;
   bool              m_created;
   long              m_chart_id;
   string            m_name;
   ENUM_BASE_CORNER  m_corner;
   int               m_x;
   int               m_y;
   int               m_width;
   int               m_height;
   int               m_brand_height;
   //--- geometry, recomputed whenever the size changes
   int               m_cx;
   int               m_cy;
   int               m_r_out;
   int               m_r_in;
   int               m_pad;          // padding above/below the text block
   int               m_gap;          // gap between text lines
   //--- fonts scale with the gauge width; sizes are in 1/10 pt
   int               m_font_scale;
   int               m_font_main;
   int               m_font_sub;
   //--- measured line heights, so DPI scaling cannot clip the text
   int               m_h_scale;
   int               m_h_main;
   int               m_h_sub;
   int               m_h_macro;
   //--- configuration
   double            m_exit;
   double            m_enter;
   uint              m_clr_choppy;
   uint              m_clr_neutral;
   uint              m_clr_trending;
   uint              m_clr_panel;
   uint              m_clr_text;
   uint              m_clr_dim;
   uint              m_clr_needle;
   uchar             m_opacity;
   bool              m_macro_confirm; // BUY/SELL ZONE only when the macro trend agrees

   void              CalcGeometry(void);
   void              FitHeight(void);
   void              ApplyPosition(void);
   void              DrawBand(const double a0,const double a1,const uint clr);
   void              DrawTick(const double value,const uint clr);
   void              DrawCentered(const int y,const string text,const uint clr);
   void              DrawBrand(void);
   double            AngleOf(const double er) const { return(M_PI * (1.0 - er)); }

public:
                     CRegimeGauge(void);
                    ~CRegimeGauge(void);

   bool              Create(const long chart_id,const string name,const ENUM_BASE_CORNER corner,
                            const int x,const int y,const int width);
   void              Destroy(void);
   bool              IsCreated(void) const { return(m_created); }

   void              SetThresholds(const double exit_level,const double enter_level);
   void              SetZoneColors(const color choppy,const color neutral,const color trending);
   void              SetOpacity(const uchar value) { m_opacity = value; }
   void              SetMacroConfirm(const bool value) { m_macro_confirm = value; }
   void              ApplyTheme(void);

   //--- re-reads the chart theme and keeps the gauge inside the chart
   void              OnChartResize(void);
   void              Render(const double er,const int state,const int dwell,const int macro_trend=REGIME_MACRO_UNSET);
  };

//+------------------------------------------------------------------+
CRegimeGauge::CRegimeGauge(void) : m_created(false),
                                   m_chart_id(0),
                                   m_name(""),
                                   m_corner(CORNER_LEFT_UPPER),
                                   m_x(20),
                                   m_y(20),
                                   m_width(220),
                                   m_height(158),
                                   m_brand_height(40),
                                   m_cx(110),
                                   m_cy(110),
                                   m_r_out(99),
                                   m_r_in(77),
                                   m_pad(8),
                                   m_gap(4),
                                   m_font_scale(-80),
                                   m_font_main(-115),
                                   m_font_sub(-85),
                                   m_h_scale(12),
                                   m_h_main(18),
                                   m_h_sub(13),
                                   m_h_macro(12),
                                   m_exit(0.18),
                                   m_enter(0.30),
                                   m_clr_choppy(0xFFB04444),
                                   m_clr_neutral(0xFFC4963E),
                                   m_clr_trending(0xFF469664),
                                   m_clr_panel(0xD71C2026),
                                   m_clr_text(0xFFECEFF3),
                                   m_clr_dim(0xFF969EA8),
                                   m_clr_needle(0xFFF5F7FA),
                                   m_opacity(215),
                                   m_macro_confirm(false)
  {
  }
//+------------------------------------------------------------------+
CRegimeGauge::~CRegimeGauge(void)
  {
   Destroy();
  }
//+------------------------------------------------------------------+
void CRegimeGauge::SetThresholds(const double exit_level,const double enter_level)
  {
   m_exit  = exit_level;
   m_enter = enter_level;
  }
//+------------------------------------------------------------------+
void CRegimeGauge::SetZoneColors(const color choppy,const color neutral,const color trending)
  {
   m_clr_choppy   = COLOR2RGB(choppy);
   m_clr_neutral  = COLOR2RGB(neutral);
   m_clr_trending = COLOR2RGB(trending);
  }
//+------------------------------------------------------------------+
//| Derive panel / text colours from the chart background so the     |
//| gauge stays readable on both light and dark themes.              |
//+------------------------------------------------------------------+
void CRegimeGauge::ApplyTheme(void)
  {
   color bg = (color)ChartGetInteger(m_chart_id,CHART_COLOR_BACKGROUND);
   int r = (int)(bg & 0xFF);
   int g = (int)((bg >> 8) & 0xFF);
   int b = (int)((bg >> 16) & 0xFF);
   double luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0;

   if(luma < 0.5)
     {
      m_clr_panel  = ARGB(m_opacity,28,32,38);
      m_clr_text   = ARGB(255,236,239,243);
      m_clr_dim    = ARGB(255,150,158,168);
      m_clr_needle = ARGB(255,245,247,250);
     }
   else
     {
      m_clr_panel  = ARGB(m_opacity,246,247,249);
      m_clr_text   = ARGB(255,28,32,38);
      m_clr_dim    = ARGB(255,110,118,128);
      m_clr_needle = ARGB(255,32,36,42);
     }
  }
//+------------------------------------------------------------------+
//| The arc is sized from the width; the height then follows from    |
//| what the arc needs plus room for the three text rows. FitHeight() |
//| replaces the provisional reserve with the real measured heights.  |
//+------------------------------------------------------------------+
void CRegimeGauge::CalcGeometry(void)
  {
   m_cx    = m_width / 2;
   m_r_out = (int)MathRound(m_width * 0.46);
   if(m_r_out < 20)
      m_r_out = 20;
   m_r_in = m_r_out - (int)MathRound(m_r_out * 0.22);
   m_brand_height = (int)MathRound(m_width * 0.18);
   m_cy   = m_brand_height + (int)MathRound(m_width * 0.05) + m_r_out;
   m_pad  = (int)MathRound(m_width * 0.035);
   m_gap  = (int)MathRound(m_width * 0.020);
   if(m_pad < 4)
      m_pad = 4;
   if(m_gap < 2)
      m_gap = 2;

   m_font_scale = -(int)MathRound(m_width * 0.36);
   m_font_main  = -(int)MathRound(m_width * 0.50);
   m_font_sub   = -(int)MathRound(m_width * 0.36);

//--- provisional; FitHeight() corrects it once the canvas can measure
   m_h_scale = (int)MathRound(m_width * 0.055);
   m_h_main  = (int)MathRound(m_width * 0.080);
   m_h_sub   = (int)MathRound(m_width * 0.060);
   m_h_macro = (int)MathRound(m_width * 0.055);
   m_height  = m_cy + m_pad + m_h_scale + m_gap + m_h_main + m_gap + m_h_sub + m_gap + m_h_macro + m_pad;
  }
//+------------------------------------------------------------------+
//| Measure the text rows with the real fonts and grow the bitmap to  |
//| fit them.                                                        |
//+------------------------------------------------------------------+
void CRegimeGauge::FitHeight(void)
  {
   m_canvas.FontSet("Segoe UI",m_font_scale,FW_NORMAL);
   m_h_scale = m_canvas.TextHeight("0.0");
   m_canvas.FontSet("Segoe UI",m_font_main,FW_BOLD);
   m_h_main = m_canvas.TextHeight("BUY ZONE");
   m_canvas.FontSet("Segoe UI",m_font_sub,FW_NORMAL);
   m_h_sub = m_canvas.TextHeight("ER 0.00");
   m_h_macro = m_canvas.TextHeight("Macro: BULLISH");

   int needed = m_cy + m_pad + m_h_scale + m_gap + m_h_main + m_gap + m_h_sub + m_gap + m_h_macro + m_pad;
   if(needed == m_height || needed <= 0)
      return;
   if(!m_canvas.Resize(m_width,needed))
      return;
   m_height = needed;
//--- Resize() rebuilds the resource but does not touch the object,
//--- so the visible bitmap area has to be updated by hand.
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_XSIZE,m_width);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_YSIZE,m_height);
  }
//+------------------------------------------------------------------+
bool CRegimeGauge::Create(const long chart_id,const string name,const ENUM_BASE_CORNER corner,
                          const int x,const int y,const int width)
  {
   Destroy();
   m_chart_id = chart_id;
   m_name     = name;
   m_corner   = corner;
   m_x        = x;
   m_y        = y;
   m_width    = (width < 120) ? 120 : width;
   CalcGeometry();

   if(!m_canvas.CreateBitmapLabel(m_chart_id,0,m_name,m_x,m_y,m_width,m_height,COLOR_FORMAT_ARGB_NORMALIZE))
      return(false);

   FitHeight();
   ApplyPosition();
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_SELECTED,false);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_HIDDEN,true);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_ZORDER,0);

   m_created = true;
   ApplyTheme();
   return(true);
  }
//+------------------------------------------------------------------+
void CRegimeGauge::Destroy(void)
  {
   if(m_created)
     {
      m_canvas.Destroy();
      m_created = false;
     }
   if(m_name != "" && ObjectFind(m_chart_id,m_name) >= 0)
      ObjectDelete(m_chart_id,m_name);
  }
//+------------------------------------------------------------------+
//| Place the bitmap so that m_x / m_y always mean "margin from the  |
//| chosen corner", for every corner.                                |
//|                                                                  |
//| OBJ_BITMAP_LABEL binds its LEFT-UPPER pixel to the anchor point, |
//| while OBJPROP_XDISTANCE / OBJPROP_YDISTANCE grow INWARDS from    |
//| the chosen corner. On a right or lower corner the bitmap would   |
//| therefore hang off the edge by its own width or height, so the   |
//| size has to be added to the distance.                            |
//+------------------------------------------------------------------+
void CRegimeGauge::ApplyPosition(void)
  {
   int cw = (int)ChartGetInteger(m_chart_id,CHART_WIDTH_IN_PIXELS);
   int ch = (int)ChartGetInteger(m_chart_id,CHART_HEIGHT_IN_PIXELS);

//--- clamp the margin so the gauge always stays fully visible
   int mx = (m_x < 0) ? 0 : m_x;
   int my = (m_y < 0) ? 0 : m_y;
   if(cw > 0 && mx + m_width > cw)
      mx = (cw - m_width > 0) ? cw - m_width : 0;
   if(ch > 0 && my + m_height > ch)
      my = (ch - m_height > 0) ? ch - m_height : 0;

   bool right = (m_corner == CORNER_RIGHT_UPPER || m_corner == CORNER_RIGHT_LOWER);
   bool lower = (m_corner == CORNER_LEFT_LOWER  || m_corner == CORNER_RIGHT_LOWER);

   ObjectSetInteger(m_chart_id,m_name,OBJPROP_CORNER,m_corner);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_XDISTANCE,right ? mx + m_width  : mx);
   ObjectSetInteger(m_chart_id,m_name,OBJPROP_YDISTANCE,lower ? my + m_height : my);
  }
//+------------------------------------------------------------------+
//| Keep the gauge on screen after a resize and refresh the theme.   |
//+------------------------------------------------------------------+
void CRegimeGauge::OnChartResize(void)
  {
   if(!m_created)
      return;
   ApplyPosition();
   ApplyTheme();
  }
//+------------------------------------------------------------------+
//| Filled arc band between m_r_in and m_r_out, anti-aliased rims.   |
//+------------------------------------------------------------------+
void CRegimeGauge::DrawBand(const double a0,const double a1,const uint clr)
  {
   double span = MathAbs(a1 - a0);
   if(span < 1e-6)
      return;
   int steps = (int)MathCeil(span / 0.02);
   if(steps < 4)
      steps = 4;

   int ox[], oy[], ix[], iy[];
   ArrayResize(ox,steps+1);
   ArrayResize(oy,steps+1);
   ArrayResize(ix,steps+1);
   ArrayResize(iy,steps+1);

   for(int k = 0; k <= steps; k++)
     {
      double a  = a0 + (a1 - a0) * ((double)k / (double)steps);
      double ca = MathCos(a);
      double sa = MathSin(a);
      ox[k] = m_cx + (int)MathRound(m_r_out * ca);
      oy[k] = m_cy - (int)MathRound(m_r_out * sa);
      ix[k] = m_cx + (int)MathRound(m_r_in  * ca);
      iy[k] = m_cy - (int)MathRound(m_r_in  * sa);
     }
   for(int k = 0; k < steps; k++)
     {
      m_canvas.FillTriangle(ox[k],oy[k],ox[k+1],oy[k+1],ix[k],iy[k],clr);
      m_canvas.FillTriangle(ix[k],iy[k],ix[k+1],iy[k+1],ox[k+1],oy[k+1],clr);
     }
   m_canvas.PolylineAA(ox,oy,clr);
   m_canvas.PolylineAA(ix,iy,clr);
   m_canvas.LineAA(ox[0],oy[0],ix[0],iy[0],clr);
   m_canvas.LineAA(ox[steps],oy[steps],ix[steps],iy[steps],clr);
  }
//+------------------------------------------------------------------+
void CRegimeGauge::DrawTick(const double value,const uint clr)
  {
   double a  = AngleOf(value);
   double ca = MathCos(a);
   double sa = MathSin(a);
   int r1 = m_r_out + 2;
   int r2 = m_r_out + 7;
   m_canvas.LineAA(m_cx + (int)MathRound(r1 * ca),m_cy - (int)MathRound(r1 * sa),
                   m_cx + (int)MathRound(r2 * ca),m_cy - (int)MathRound(r2 * sa),clr);
  }
//+------------------------------------------------------------------+
void CRegimeGauge::DrawCentered(const int y,const string text,const uint clr)
  {
   int w = m_canvas.TextWidth(text);
   m_canvas.TextOut(m_cx - w / 2,y,text,clr);
  }
//+------------------------------------------------------------------+
void CRegimeGauge::DrawBrand(void)
  {
   int size = (int)MathRound(m_width * 0.13);
   m_canvas.FontSet("Segoe UI",m_font_sub,FW_BOLD);
   int text_width = m_canvas.TextWidth("XPWorx");
   int left = (m_width - size - m_gap - text_width) / 2;
   int top = (m_brand_height - size) / 2;
   for(int y = 0; y < size; y++)
      for(int x = 0; x < size; x++)
        {
         uint pixel = XPWORX_LOGO_PIXELS[(y * 32 / size) * 32 + x * 32 / size];
         uint alpha = pixel >> 24;
         if(alpha == 0)
            continue;
         uint r = (((pixel >> 16) & 255) * alpha + ((m_clr_panel >> 16) & 255) * (255-alpha)) / 255;
         uint g = (((pixel >> 8) & 255) * alpha + ((m_clr_panel >> 8) & 255) * (255-alpha)) / 255;
         uint b = ((pixel & 255) * alpha + (m_clr_panel & 255) * (255-alpha)) / 255;
         m_canvas.PixelSet(left+x,top+y,ARGB(255,r,g,b));
        }
   m_canvas.TextOut(left+size+m_gap,(m_brand_height-m_canvas.TextHeight("XPWorx"))/2,"XPWorx",m_clr_text);
  }
//+------------------------------------------------------------------+
//| Full repaint of the gauge for one (ER, state, dwell) triple.     |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Full repaint of the gauge for one (ER, state, dwell) triple.     |
//+------------------------------------------------------------------+
void CRegimeGauge::Render(const double er,const int state,const int dwell,const int macro_trend=REGIME_MACRO_UNSET)
  {
   if(!m_created)
      return;

   m_canvas.Erase(0x00000000);
   m_canvas.FillRectangle(0,0,m_width-1,m_height-1,m_clr_panel);
   DrawBrand();

   double shown = er;
   if(shown < 0.0)
      shown = 0.0;
   if(shown > 1.0)
      shown = 1.0;

//--- three zones, sized in proportion to the thresholds
   double gap = 0.012;
   DrawBand(AngleOf(0.0),           AngleOf(m_exit)  + gap, m_clr_choppy);
   DrawBand(AngleOf(m_exit)  - gap, AngleOf(m_enter) + gap, m_clr_neutral);
   DrawBand(AngleOf(m_enter) - gap, AngleOf(1.0),           m_clr_trending);

//--- threshold ticks
   DrawTick(m_exit,m_clr_dim);
   DrawTick(m_enter,m_clr_dim);

//--- needle at the current (closed bar) efficiency ratio
   double a = AngleOf(shown);
   int needle_r = m_r_in - 6;
   if(needle_r < 10)
      needle_r = 10;
   int nx = m_cx + (int)MathRound(needle_r * MathCos(a));
   int ny = m_cy - (int)MathRound(needle_r * MathSin(a));
   m_canvas.LineThick(m_cx,m_cy,nx,ny,m_clr_needle,3,STYLE_SOLID,LINE_END_ROUND);
   m_canvas.FillCircle(m_cx,m_cy,5,m_clr_needle);
   m_canvas.CircleAA(m_cx,m_cy,5.0,m_clr_needle);

//--- text rows are stacked from measured heights, never from guesses
   int row = m_cy + m_pad;

//--- scale end labels, sitting under the two arc tips
   m_canvas.FontSet("Segoe UI",m_font_scale,FW_NORMAL);
   m_canvas.TextOut(m_cx - m_r_out - 2,row,"0.0",m_clr_dim);
   int w10 = m_canvas.TextWidth("1.0");
   m_canvas.TextOut(m_cx + m_r_out + 2 - w10,row,"1.0",m_clr_dim);
   row += m_h_scale + m_gap;

//--- centre label: institutional zone name
   string label     = "";
   uint   label_clr = m_clr_text;
//--- with macro confirmation on, a trend against the H4 macro trend is
//--- shown as COUNTER-TREND and one with a flat macro in amber, because
//--- the EA takes neither - the gauge must never invite a trade it skips.
   if(state == REGIME_TREND_UP && m_macro_confirm && macro_trend == REGIME_MACRO_DOWN)
     {
      label     = "COUNTER-TREND " + ShortToString(0x25B2);
      label_clr = m_clr_neutral;
     }
   else if(state == REGIME_TREND_DOWN && m_macro_confirm && macro_trend == REGIME_MACRO_UP)
     {
      label     = "COUNTER-TREND " + ShortToString(0x25BC);
      label_clr = m_clr_neutral;
     }
   else if(state == REGIME_TREND_UP)
     {
      label     = "BUY ZONE " + ShortToString(0x25B2);
      label_clr = (m_macro_confirm && macro_trend != REGIME_MACRO_UP) ? m_clr_neutral : m_clr_trending;
     }
   else if(state == REGIME_TREND_DOWN)
     {
      label     = "SELL ZONE " + ShortToString(0x25BC);
      label_clr = (m_macro_confirm && macro_trend != REGIME_MACRO_DOWN) ? m_clr_neutral : m_clr_choppy;
     }
   else if(state == REGIME_RANGE)
     {
      label     = "CHOPPY ZONE";
      label_clr = m_clr_dim;
     }
   else if(state == REGIME_NEUTRAL)
     {
      label     = "NEUTRAL ZONE";
      label_clr = m_clr_neutral;
     }
   else
     {
      label     = "WARMING UP";
      label_clr = m_clr_dim;
     }

//--- shrink the font until the label fits (COUNTER-TREND is the longest)
   int font = m_font_main;
   m_canvas.FontSet("Segoe UI",font,FW_BOLD);
   while(m_canvas.TextWidth(label) > m_width - 2 * m_pad && font < -40)
     {
      font += 5;
      m_canvas.FontSet("Segoe UI",font,FW_BOLD);
     }
   DrawCentered(row + (m_h_main - m_canvas.TextHeight(label)) / 2,label,label_clr);
   row += m_h_main + m_gap;

//--- small line underneath: efficiency ratio and bars in state
   string dot = ShortToString(0x00B7);
   string sub;
   if(er < 0.0)
      sub = "ER --   " + dot + "   waiting for data";
   else
      sub = "ER " + DoubleToString(er,2) + "   " + dot + "   " +
            IntegerToString(dwell) + ((dwell == 1) ? " bar" : " bars");
   m_canvas.FontSet("Segoe UI",m_font_sub,FW_NORMAL);
   DrawCentered(row,sub,m_clr_dim);
   row += m_h_sub + m_gap;

//--- fourth row: H4 Macro Trend status
   string macro_txt = "Macro: ";
   uint macro_clr = m_clr_dim;
   if(macro_trend == REGIME_MACRO_UP)
     {
      macro_txt += "BULLISH " + ShortToString(0x25B2);
      macro_clr = m_clr_trending;
     }
   else if(macro_trend == REGIME_MACRO_DOWN)
     {
      macro_txt += "BEARISH " + ShortToString(0x25BC);
      macro_clr = m_clr_choppy;
     }
   else if(macro_trend == REGIME_MACRO_FLAT)
     {
      macro_txt += "FLAT " + ShortToString(0x25AC);
      macro_clr = m_clr_neutral;
     }
   else
     {
      macro_txt += "CALCULATING";
      macro_clr = m_clr_dim;
     }
   m_canvas.FontSet("Segoe UI",m_font_sub,FW_NORMAL);
   DrawCentered(row,macro_txt,macro_clr);

   m_canvas.Update(true);
  }
