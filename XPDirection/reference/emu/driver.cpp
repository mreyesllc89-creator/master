// Gate 1 driver: feeds fixtures through the EA's OWN rule-core source text
// (lifted by extract_core.py, compiled by g++ against mql5_stubs.h).
//
//   usage: ./driver <fixtures.csv>
//   out  : name,dir,rule,conflict,p_grade,c1_grade,P,C1,C5,C10,C15,C30,C45
//
// Rung field grammar, per fixture column P/S1/S5/S10/S15/S30/S45:
//   "-"    rung absent or disabled
//   "nv"   rung present, NO_VOTE
//   "f:s/f:s/...|age|interval|carried|crossdir|crossage|crosssep"
//          the CLOSED-bar series newest-first (index 0 = the bar that just
//          closed; the forming bar is never in it), EMPTY = EMPTY_VALUE, then
//          the rung's PERSISTED state going into the read. 'x' = first read.
#include "mql5_stubs.h"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>
#include "core.cpp"

static std::vector<std::string> split(const std::string& line, char sep) {
  std::vector<std::string> out; std::string cur; std::istringstream is(line);
  while (std::getline(is, cur, sep)) out.push_back(cur);
  return out;
}
static std::string trim(std::string s) {
  while (!s.empty() && (s.back() == ' ' || s.back() == '\r' || s.back() == '\t')) s.pop_back();
  size_t i = 0; while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) i++;
  return s.substr(i);
}
static double num(const std::string& s) {
  if (s == "EMPTY") return EMPTY_VALUE;
  return atof(s.c_str());
}
static const char* vote_tag(int present, int vote) {
  if (!present) return "-";
  if (vote > 0) return "BUY";
  if (vote < 0) return "SELL";
  return "NV";
}
static const char* grade_name(int g) {
  if (g == XPDIR_GRADE_EARLY) return "EARLY";
  if (g == XPDIR_GRADE_FRESH) return "FRESH";
  if (g == XPDIR_GRADE_STALE) return "STALE_STATE";
  return "-";
}

int main(int argc, char** argv) {
  if (argc < 2) { fprintf(stderr, "usage: driver <fixtures.csv>\n"); return 2; }
  std::ifstream f(argv[1]);
  if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
  std::string line;
  bool have_head = false;
  printf("name,dir,rule,conflict,p_grade,c1_grade,P,C1,C5,C10,C15,C30,C45\n");
  while (std::getline(f, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') continue;
    auto c = split(line, ',');
    for (auto& x : c) x = trim(x);
    if (!have_head) { have_head = true; continue; }
    if (c.size() < 18) { fprintf(stderr, "short row: %s\n", line.c_str()); return 2; }

    const std::string name = c[0];
    const int minWith = atoi(c[1].c_str());
    const int minAgainst = atoi(c[2].c_str());
    const bool s1Req = (c[3] == "1" || c[3] == "true");
    const int maxStale = atoi(c[4].c_str());
    const int crossMaxAge = atoi(c[5].c_str());
    const double earlyMult = atof(c[6].c_str());
    const bool requireFreshS1 = (c[7] == "1" || c[7] == "true");

    int present[7] = {0}, vote[7] = {0}, grade[7] = {0};
    for (int r = 0; r < 7; r++) {           // order: P,S1,S5,S10,S15,S30,S45
      const std::string& spec = c[8 + r];
      if (spec == "-") continue;
      present[r] = 1;
      if (spec == "nv") continue;
      auto p = split(spec, '|');
      if (p.size() != 7) { fprintf(stderr, "bad rung spec '%s' in %s\n", spec.c_str(), name.c_str()); return 2; }
      auto bars = split(p[0], '/');
      Arr<double> fast((int)bars.size()), slow((int)bars.size());
      for (size_t b = 0; b < bars.size(); b++) {
        auto fs = split(bars[b], ':');
        if (fs.size() != 2) { fprintf(stderr, "bad bar '%s' in %s\n", bars[b].c_str(), name.c_str()); return 2; }
        fast[(int)b] = num(fs[0]);
        slow[(int)b] = num(fs[1]);
      }
      int carried = (p[3] == "x") ? 0 : atoi(p[3].c_str());
      int cdir    = (p[4] == "x") ? 0 : atoi(p[4].c_str());
      int cage    = (p[5] == "x") ? -1 : atoi(p[5].c_str());
      double csep = (p[6] == "x") ? 0.0 : atof(p[6].c_str());

      XPDir_AdvanceCross(fast, slow, (int)bars.size(), carried, cdir, cage, csep);

      const bool bar0Valid = !XPDir_CoreIsEmpty(fast[0]) && !XPDir_CoreIsEmpty(slow[0]);
      const double sepNow = bar0Valid ? (fast[0] - slow[0]) : 0.0;
      int g = 0;
      string why;
      vote[r] = XPDir_VoteFromCross(sepNow, bar0Valid, carried, cdir, cage, csep,
                                    atol(p[1].c_str()), atoi(p[2].c_str()),
                                    maxStale, crossMaxAge, earlyMult, g, why);
      grade[r] = g;
    }

    Arr<int> optional;
    for (int r = 2; r < 7; r++) {           // S5..S45, present ones only
      if (!present[r]) continue;
      int n = ArraySize(optional);
      ArrayResize(optional, n + 1);
      optional[n] = vote[r];
    }

    const bool s1Fresh = (grade[1] == XPDIR_GRADE_EARLY || grade[1] == XPDIR_GRADE_FRESH);
    int rule = 0; bool conflict = false;
    const int decided = XPDir_DecideFromVotes(vote[0], vote[1], s1Fresh, optional,
                                              minWith, minAgainst, s1Req,
                                              requireFreshS1, rule, conflict);
    printf("%s,%s,%s,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s\n", name.c_str(),
           decided > 0 ? "BUY" : (decided < 0 ? "SELL" : "NONE"),
           rule > 0 ? (rule == 1 ? "R1" : rule == 2 ? "R2" : "R3") : "-",
           conflict ? 1 : 0,
           grade_name(grade[0]), grade_name(grade[1]),
           vote_tag(present[0], vote[0]), vote_tag(present[1], vote[1]),
           vote_tag(present[2], vote[2]), vote_tag(present[3], vote[3]),
           vote_tag(present[4], vote[4]), vote_tag(present[5], vote[5]),
           vote_tag(present[6], vote[6]));
  }
  return 0;
}
