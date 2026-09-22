// MQL5 -> C++ stub layer for the Gate 0 entry-path check.
//
// Unlike the Gate 1 core, the entry-path wiring READS GLOBALS - the mode, the
// two virtual stop levels, the hold candidate. Those are supplied here so the
// driver can set them, run the EA's own source text, and read back what it did.
// Nothing here models trading: the point is to observe writes and return values.
#include <string>
#include <vector>
#include <cstdio>
#include <cmath>

typedef long long datetime;

struct string {
  std::string s;
  string() {}
  string(const char* c) : s(c) {}
  string(const std::string& c) : s(c) {}
  string operator+(const string& o) const { return string(s + o.s); }
  bool operator==(const string& o) const { return s == o.s; }
  bool operator!=(const string& o) const { return s != o.s; }
};
inline string operator+(const char* a, const string& b) { return string(std::string(a) + b.s); }

// --- the EA's enums, copied from the build ---------------------------------
enum ENUM_XPDIR      { XPDIR_NONE = 0, XPDIR_BUY = 1, XPDIR_SELL = -1 };
enum ENUM_XPDIR_MODE { DIR_OFF = 0, DIR_LOCK = 1, DIR_TRANSLATE = 2, DIR_VETO = 3 };
enum ENUM_XPDIR_ON_NONE { XPDIR_NONE_BLOCK = 0, XPDIR_NONE_ALLOW = 1 };
ENUM_XPDIR_ON_NONE InpDirOnNone = XPDIR_NONE_BLOCK;

// --- the globals the wiring touches ----------------------------------------
ENUM_XPDIR_MODE InpDirMode = DIR_OFF;
double g_VirtualBuyStopPrice = 0.0;
double g_VirtualSellStopPrice = 0.0;
bool   g_XPDirHoldTriggerIsBuy = false;
datetime g_XPDirLastBlockedSec = 0;
int    g_XPDirLastArmed = -2;
bool   g_XPDirCachedConflict = false;

struct EntryHoldCandidateStub { bool active; bool isBuy; };
EntryHoldCandidateStub g_EntryHoldCandidate = { false, false };

// --- observable side effects ------------------------------------------------
int g_stubResetCalls = 0;
int g_stubCsvCalls = 0;
int g_stubPrintCalls = 0;
datetime g_stubNow = 1000;

void ResetEntryHoldCandidate() { g_EntryHoldCandidate.active = false;
                                 g_EntryHoldCandidate.isBuy = false;
                                 g_stubResetCalls++; }
void XPDir_WriteCsv(const string&, const string&, const string&, const string&) { g_stubCsvCalls++; }
template <class... A> void PrintFormat(A...) { g_stubPrintCalls++; }
inline datetime TimeCurrent() { return g_stubNow; }
inline string XPDir_DirName(ENUM_XPDIR d) {
  return d == XPDIR_BUY ? string("BUY") : (d == XPDIR_SELL ? string("SELL") : string("NONE"));
}

// --- the direction the ladder would return, set by the driver ---------------
ENUM_XPDIR g_stubDir = XPDIR_NONE;
int g_stubVetoCalls = 0;
// XPDir_Allows lives in the LADDER block, not the wiring block, so the Gate 0
// driver stubs it with the same logic to keep the two honest.
bool XPDir_Allows(const bool isBuy);
int g_stubDirCalls = 0;
ENUM_XPDIR XPDir_Current() { g_stubDirCalls++; return g_stubDir; }

bool XPDir_Allows(const bool isBuy) {
  g_stubVetoCalls++;
  if (InpDirMode == DIR_OFF) return true;
  if (g_stubDir == XPDIR_NONE) return InpDirOnNone == XPDIR_NONE_ALLOW;
  return isBuy ? (g_stubDir == XPDIR_BUY) : (g_stubDir == XPDIR_SELL);
}

inline void StubReset() {
  g_stubResetCalls = g_stubCsvCalls = g_stubPrintCalls = g_stubDirCalls = g_stubVetoCalls = 0;
  g_XPDirLastArmed = -2;
  g_XPDirLastBlockedSec = 0;
  g_XPDirHoldTriggerIsBuy = false;
  g_XPDirCachedConflict = false;
}
