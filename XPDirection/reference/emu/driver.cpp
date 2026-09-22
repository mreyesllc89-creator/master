// Gate 1 driver: feeds fixtures through the EA's OWN rule-core source text
// (lifted by extract_core.py, compiled by g++ against mql5_stubs.h).
//
//   usage: ./driver <fixtures.csv>
//   out  : name,dir,rule,conflict,P,C1,C5,C10,C15,C30,C45   (one line per case)
//
// Rung field grammar, per fixture column P/S1/S5/S10/S15/S30/S45:
//   "-"                                   rung absent or disabled (no vote,
//                                         and excluded from the optional set)
//   "nv"                                  rung present, NO_VOTE
//   "<fast>|<slow>|<runlen>|<age>|<interval>"
//                                         raw map outputs; "EMPTY" for
//                                         EMPTY_VALUE (the map's valid flag)
#include "mql5_stubs.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
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
  if (s == "NAN") return std::nan("");
  return atof(s.c_str());
}
static const char* tag(int present, int vote) {
  if (!present) return "-";
  if (vote > 0) return "BUY";
  if (vote < 0) return "SELL";
  return "NV";
}

int main(int argc, char** argv) {
  if (argc < 2) { fprintf(stderr, "usage: driver <fixtures.csv>\n"); return 2; }
  std::ifstream f(argv[1]);
  if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
  std::string line;
  std::vector<std::string> head;
  printf("name,dir,rule,conflict,P,C1,C5,C10,C15,C30,C45\n");
  while (std::getline(f, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') continue;
    auto c = split(line, ',');
    for (auto& x : c) x = trim(x);
    if (head.empty()) { head = c; continue; }
    if (c.size() < 16) { fprintf(stderr, "short row: %s\n", line.c_str()); return 2; }

    const std::string name = c[0];
    const int minWith = atoi(c[1].c_str());
    const int minAgainst = atoi(c[2].c_str());
    const bool s1Req = (c[3] == "1" || c[3] == "true");
    const int maxStale = atoi(c[4].c_str());
    const int maxRunLen = atoi(c[5].c_str());

    int present[7] = {0}, vote[7] = {0};
    for (int r = 0; r < 7; r++) {           // order: P,S1,S5,S10,S15,S30,S45
      const std::string& spec = c[6 + r];
      if (spec == "-") { present[r] = 0; vote[r] = 0; continue; }
      present[r] = 1;
      if (spec == "nv") { vote[r] = 0; continue; }
      auto p = split(spec, '|');
      if (p.size() != 5) { fprintf(stderr, "bad rung spec '%s' in %s\n", spec.c_str(), name.c_str()); return 2; }
      string why;
      vote[r] = XPDir_RungVote(num(p[0]), num(p[1]), atoi(p[2].c_str()),
                               atol(p[3].c_str()), atoi(p[4].c_str()),
                               maxStale, maxRunLen, why);
    }

    Arr<int> optional;
    for (int r = 2; r < 7; r++) {           // S5..S45, present ones only
      if (!present[r]) continue;
      int n = ArraySize(optional);
      ArrayResize(optional, n + 1);
      optional[n] = vote[r];
    }

    int rule = 0; bool conflict = false;
    const int decided = XPDir_DecideFromVotes(vote[0], vote[1], optional,
                                              minWith, minAgainst, s1Req,
                                              rule, conflict);
    const char* dir = decided > 0 ? "BUY" : (decided < 0 ? "SELL" : "NONE");
    printf("%s,%s,%s,%d,%s,%s,%s,%s,%s,%s,%s\n", name.c_str(), dir,
           rule > 0 ? (rule == 1 ? "R1" : rule == 2 ? "R2" : "R3") : "-",
           conflict ? 1 : 0,
           tag(present[0], vote[0]), tag(present[1], vote[1]),
           tag(present[2], vote[2]), tag(present[3], vote[3]),
           tag(present[4], vote[4]), tag(present[5], vote[5]),
           tag(present[6], vote[6]));
  }
  return 0;
}
