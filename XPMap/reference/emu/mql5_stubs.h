// Minimal MQL5 -> C++ stub layer for syntax/type linting only (no compiler in the box).
#include <string>
#include <vector>
#include <deque>
#include <cstdio>
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <sstream>
#include <iostream>
typedef long long datetime; typedef unsigned int color; typedef unsigned short ushort; typedef unsigned int uint; typedef unsigned char uchar;
#define EMPTY_VALUE 1.7976931348623157e308
struct string {
  std::string s;
  string() {}
  string(const char* c) : s(c) {}
  string(const std::string& c) : s(c) {}
  explicit string(int v) { s = std::to_string(v); }
  explicit string(long long v) { s = std::to_string(v); }
  explicit string(long v) { s = std::to_string(v); }
  explicit string(double v) { s = std::to_string(v); }
  explicit string(bool v) { s = v ? "true" : "false"; }
  explicit string(unsigned int v) { s = std::to_string(v); }
  string operator+(const string& o) const { return string(s + o.s); }
  string& operator+=(const string& o) { s += o.s; return *this; }
  bool operator==(const string& o) const { return s == o.s; }
  bool operator!=(const string& o) const { return s != o.s; }
};
inline string operator+(const char* a, const string& b) { return string(std::string(a) + b.s); }
template<class T> struct Arr {
  std::deque<T> v;
  Arr() {}
  Arr(int n) : v(n) {}
  T& operator[](int i) { return v[i]; }
  const T& operator[](int i) const { return v[i]; }
};
template<class T> int ArraySize(const Arr<T>& a) { return (int)a.v.size(); }
template<class T> int ArrayResize(Arr<T>& a, int n, int reserve = 0) { a.v.resize(n); return n; }
template<class T, class V> int ArrayInitialize(Arr<T>& a, V val) { for (auto& x : a.v) x = (T)val; return (int)a.v.size(); }
template<class T> bool ArrayRemove(Arr<T>& a, int start, int count) { a.v.erase(a.v.begin() + start, a.v.begin() + start + count); return true; }
template<class T> bool ArraySort(Arr<T>& a) { std::sort(a.v.begin(), a.v.end()); return true; }
inline int MathMax(int a, int b) { return a > b ? a : b; }
inline double MathMax(double a, double b) { return a > b ? a : b; }
inline int MathMin(int a, int b) { return a < b ? a : b; }
inline double MathMin(double a, double b) { return a < b ? a : b; }
inline double MathAbs(double a) { return std::fabs(a); }
inline double MathRound(double a) { return std::round(a); }
inline int StringLen(const string& s) { return (int)s.s.size(); }
inline string StringSubstr(const string& s, int start, int len = -1) { return string(s.s.substr(start, len < 0 ? std::string::npos : len)); }
inline int StringFind(const string& s, const string& f, int start = 0) { auto p = s.s.find(f.s, start); return p == std::string::npos ? -1 : (int)p; }
inline int StringReplace(string& s, const string& a, const string& b) { return 0; }
inline ushort StringGetCharacter(const string& s, int i) { return (ushort)s.s[i]; }
inline string DoubleToString(double v, int d = 8) { return string(std::to_string(v)); }
inline string TimeToString(datetime t, int flags = 0) { return string("t"); }
template<class... A> string StringFormat(const string& f, A... a) { return f; }
template<class... A> void Print(A... a) {}
inline bool TextSetFont(const string& n, int s, unsigned int f = 0, int o = 0) { return true; }
inline bool TextGetSize(const string& t, uint& w, uint& h) { w = 1; h = 1; return true; }
enum { TIME_DATE = 1, TIME_MINUTES = 2, TIME_SECONDS = 4 };
enum { FILE_READ = 1, FILE_WRITE = 2, FILE_TXT = 4, FILE_ANSI = 8, FILE_SHARE_READ = 16, FILE_SHARE_WRITE = 32, SEEK_END_ = 2 };
#undef SEEK_END
#define SEEK_END SEEK_END_
#define INVALID_HANDLE -1
inline int FileOpen(const string& p, int flags, int delim = 0) { return 1; }
inline bool FileSeek(int h, long long off, int origin) { return true; }
template<class... A> uint FileWrite(int h, A... a) { return 0; }
inline void FileClose(int h) {}
inline bool FolderCreate(const string& p, int common = 0) { return true; }
inline int GetLastError() { return 0; }
enum ENUM_OBJECT { OBJ_RECTANGLE, OBJ_TEXT, OBJ_LABEL };
enum ENUM_OBJECT_PROPERTY_INTEGER { OBJPROP_COLOR, OBJPROP_WIDTH, OBJPROP_STYLE, OBJPROP_FILL, OBJPROP_BACK, OBJPROP_SELECTABLE, OBJPROP_HIDDEN, OBJPROP_FONTSIZE, OBJPROP_ANCHOR, OBJPROP_CORNER, OBJPROP_XDISTANCE, OBJPROP_YDISTANCE };
enum ENUM_OBJECT_PROPERTY_STRING { OBJPROP_TEXT, OBJPROP_FONT, OBJPROP_TOOLTIP };
enum { STYLE_SOLID, ANCHOR_UPPER, ANCHOR_LOWER, ANCHOR_RIGHT_UPPER, CORNER_RIGHT_UPPER };
inline bool ObjectCreate(long long c, const string& n, ENUM_OBJECT t, int w, datetime t1, double p1, datetime t2 = 0, double p2 = 0) { return true; }
inline bool ObjectSetInteger(long long c, const string& n, ENUM_OBJECT_PROPERTY_INTEGER p, long long v) { return true; }
inline bool ObjectSetString(long long c, const string& n, ENUM_OBJECT_PROPERTY_STRING p, const string& v) { return true; }
inline int ObjectFind(long long c, const string& n) { return -1; }
inline bool ObjectDelete(long long c, const string& n) { return true; }
inline int ObjectsDeleteAll(long long c, const string& prefix, int w = -1, int t = -1) { return 0; }
enum ENUM_CHART_PROPERTY_INTEGER { CHART_HEIGHT_IN_PIXELS };
inline long long ChartGetInteger(long long c, ENUM_CHART_PROPERTY_INTEGER p, int w = 0) { return 400; }
inline long long ChartID() { return 1; }
inline int ChartWindowFind() { return 1; }
inline void ChartRedraw(long long c = 0) {}
enum ENUM_SYMBOL_INFO_INTEGER { SYMBOL_DIGITS }; enum ENUM_SYMBOL_INFO_DOUBLE { SYMBOL_POINT, SYMBOL_TRADE_TICK_SIZE };
inline long long SymbolInfoInteger(const string& s, ENUM_SYMBOL_INFO_INTEGER p) { return 2; }
inline double SymbolInfoDouble(const string& s, ENUM_SYMBOL_INFO_DOUBLE p) { return 0.01; }
static string _Symbol("XAUUSD-ECNc_S1");
enum ENUM_INDEXBUFFER_TYPE { INDICATOR_DATA, INDICATOR_CALCULATIONS };
inline bool SetIndexBuffer(int i, Arr<double>& b, ENUM_INDEXBUFFER_TYPE t) { return true; }
enum ENUM_PLOT_PROPERTY_DOUBLE { PLOT_EMPTY_VALUE }; enum ENUM_PLOT_PROPERTY_INTEGER { PLOT_LINE_COLOR };
inline bool PlotIndexSetDouble(int i, ENUM_PLOT_PROPERTY_DOUBLE p, double v) { return true; }
inline bool PlotIndexSetInteger(int i, ENUM_PLOT_PROPERTY_INTEGER p, int m, long long v) { return true; }
enum ENUM_CUSTOMIND_PROPERTY_STRING { INDICATOR_SHORTNAME }; enum ENUM_CUSTOMIND_PROPERTY_INTEGER { INDICATOR_DIGITS }; enum ENUM_CUSTOMIND_PROPERTY_DOUBLE { INDICATOR_MINIMUM, INDICATOR_MAXIMUM };
inline bool IndicatorSetString(ENUM_CUSTOMIND_PROPERTY_STRING p, const string& v) { return true; }
inline bool IndicatorSetInteger(ENUM_CUSTOMIND_PROPERTY_INTEGER p, long long v) { return true; }
inline bool IndicatorSetDouble(ENUM_CUSTOMIND_PROPERTY_DOUBLE p, double v) { return true; }
#define INIT_SUCCEEDED 0
#define clrWhite 0xFFFFFFu
inline color RGBc(int r, int g, int b) { return (color)((b << 16) | (g << 8) | r); }
