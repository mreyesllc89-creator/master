// Terminal emulator: feeds synthetic seconds bars to OnCalculate the way MT5 does (growing rates_total,
// a mutating forming bar, occasional multi-bar jumps, a prev_calculated==0 replay).
#include "lint_rt.cpp"
#include <random>
struct Bar { datetime t; double o, h, l, c; long long tv; };
static std::vector<Bar> g_bars;
static Arr<datetime> A_time; static Arr<double> A_open, A_high, A_low, A_close; static Arr<long> A_tv, A_vol; static Arr<int> A_spread;
static int g_prev = 0;
static void feed(int n, bool partialLast) {
  A_time.v.resize(n); A_open.v.resize(n); A_high.v.resize(n); A_low.v.resize(n); A_close.v.resize(n); A_tv.v.resize(n); A_vol.v.resize(n); A_spread.v.resize(n);
  for (int i = 0; i < n; i++) { const Bar& b = g_bars[i]; A_time[i] = b.t; A_open[i] = b.o; A_high[i] = b.h; A_low[i] = b.l; A_close[i] = b.c; A_tv[i] = b.tv; A_vol[i] = 0; A_spread[i] = 0; }
  if (partialLast) { A_high[n - 1] = A_open[n - 1]; A_low[n - 1] = A_open[n - 1]; A_close[n - 1] = A_open[n - 1]; A_tv[n - 1] = 1; }  // forming bar, first tick only
  for (auto* b : g_buffers) { size_t old = b->v.size(); b->v.resize(n); for (size_t k = old; k < (size_t)n; k++) b->v[k] = EMPTY_VALUE; }
}
static void call(int n, int prev) {
  g_prev = OnCalculate(n, prev, A_time, A_open, A_high, A_low, A_close, A_tv, A_vol, A_spread);
}
int main(int argc, char** argv) {
  int N = argc > 1 ? atoi(argv[1]) : 1200; int seed = argc > 2 ? atoi(argv[2]) : 7; bool emptyBars = argc > 3 && atoi(argv[3]) == 1; bool noPartial = argc > 4 && atoi(argv[4]) == 1;
  std::mt19937 rng(seed); std::uniform_real_distribution<double> u(-0.6, 0.6), w(0.0, 0.5), z(0.0, 1.0);
  double p = 2400.0; datetime t0 = 10 * 3600;
  for (int i = 0; i < N; i++) {
    double o = p, c = p + u(rng); double hh = std::max(o, c) + w(rng), ll = std::min(o, c) - w(rng);
    if (z(rng) < 0.08) { hh += 1.5 * w(rng); }   // occasional long upper wick
    if (z(rng) < 0.08) { ll -= 1.5 * w(rng); }
    long long tv = 3; if (emptyBars && z(rng) < 0.15) { tv = 0; o = hh = ll = c = p; }   // engine WriteEmptyBars marker
    g_bars.push_back({t0 + i, o, hh, ll, c, tv}); p = c;
  }
  OnInit();
  int n = 300; feed(n, false); call(n, 0);                                // history load
  std::mt19937 r2(seed + 1);
  long previewChecks = 0, previewFails = 0, previewEmpty = 0;
  double pvR = EMPTY_VALUE, pvF = EMPTY_VALUE, pvS = EMPTY_VALUE; int pvIdx = -1;
  while (n < N) {
    if (pvIdx >= 0 && n + 1 <= N) {   // bar pvIdx is about to close: compare its last preview with the confirmed value
      // (comparison happens after the next feed/call below)
    }
    int jump = (z(r2) < 0.05) ? std::min(3, N - n) : 1;                    // rates_total jumps by more than one
    n += jump;
    feed(n, !noPartial);  call(n, g_prev);                                 // new forming bar, first tick (or closed when noPartial)
    feed(n, false); call(n, g_prev);                                        // forming bar mutated (more ticks)
    call(n, g_prev);                                                        // tick with no bar change
    if (pvIdx >= 0 && jump == 1) {                                          // previous forming bar is now closed
      previewChecks++;
      if (pvR == EMPTY_VALUE && BufRSI[pvIdx] != EMPTY_VALUE) previewEmpty++;
      else if (pvR != BufRSI[pvIdx] || pvF != BufFast[pvIdx] || pvS != BufSlow[pvIdx]) previewFails++;
    }
    pvIdx = n - 1; pvR = BufRSI[pvIdx]; pvF = BufFast[pvIdx]; pvS = BufSlow[pvIdx];   // preview of the complete forming bar
    if (n > 330 && BufRSI[n - 1] == EMPTY_VALUE && BufFast[n - 1] == EMPTY_VALUE) previewEmpty++;
  }
  std::cout << "preview: checks=" << previewChecks << " mismatches_vs_confirmed=" << previewFails << " empty_forming_bars=" << previewEmpty << std::endl;
  std::cout << "objects=" << g_objects.size() << " creates=" << g_objCreates << std::endl;
  int boxes = 0, labels = 0, tbl = 0; for (auto& kv : g_objects) { if (kv.second.type == OBJ_RECTANGLE) boxes++; else if (kv.second.type == OBJ_TEXT) labels++; else tbl++; }
  std::cout << "boxes=" << boxes << " text_labels=" << labels << " table_labels=" << tbl << std::endl;
  // S3 emulation: copy dump, force a replay, compare
  system("cp Files/XPChart/mapdump05_XAUUSD-ECNc_S1.csv Files/XPChart/dump_A.csv");
  feed(n, false); call(n, 0);
  system("cp Files/XPChart/mapdump05_XAUUSD-ECNc_S1.csv Files/XPChart/dump_B.csv");
  std::cout << "after replay objects=" << g_objects.size() << std::endl;
  OnDeinit(0);
  std::cout << "after deinit objects=" << g_objects.size() << std::endl;
  return 0;
}
