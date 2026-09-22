// Minimal MQL5 -> C++ stub layer for the XPDir rule core (Gate 1).
// Same approach as XPMap/reference/emu/mql5_stubs.h, cut down to what the
// extracted core touches: string, dynamic arrays, MathAbs/MathIsValidNumber,
// EMPTY_VALUE. Nothing here models trading, charts or indicator buffers - the
// core is pure by construction, which is the point of extracting it.
#include <string>
#include <deque>
#include <cmath>
#include <algorithm>
#define EMPTY_VALUE 1.7976931348623157e308
typedef long long datetime;
struct string {
  std::string s;
  string() {}
  string(const char* c) : s(c) {}
  string(const std::string& c) : s(c) {}
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
inline double MathAbs(double a) { return std::fabs(a); }
inline bool MathIsValidNumber(double a) { return std::isfinite(a); }
