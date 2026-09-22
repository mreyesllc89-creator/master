#!/usr/bin/env bash
# Emulated compile + run of XPW_ShapeMap_v0.4.mq5 (no MetaEditor in the box).
#  1. stub lint      : g++ -fsyntax-only on a mechanical MQL5->C++ translation (syntax/type check only)
#  2. runtime emu    : the same translation linked against mql5_rt.h and driven by driver.cpp, which feeds
#                      synthetic seconds bars the way MT5 does (history load, growing rates_total, a mutating
#                      forming bar, 3-bar jumps, a prev_calculated==0 replay), then diff_harness on the dump.
# usage: ./run_emu.sh [N_bars] [seed] [empty_bars 0/1] [no_partial 0/1] [Input=value ...]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../../XPW_ShapeMap_v0.4.mq5"
N=${1:-1200}; SEED=${2:-7}; EMPTY=${3:-0}; NOPART=${4:-0}; shift 4 2>/dev/null || shift $#
WORK="$(mktemp -d)"; cd "$WORK"
cp "$HERE"/mql5_rt.h "$HERE"/mql5_stubs.h "$HERE"/driver.cpp .
python3 "$HERE/mql2cpp.py" "$SRC" lint.cpp
g++ -std=c++17 -fsyntax-only -Wall -Wextra -Wno-unused-parameter -Wno-unused-variable lint.cpp && echo "stub lint: 0 errors 0 warnings"
python3 "$HERE/mql2cpp_rt.py" "$SRC" lint_rt.cpp DumpCSV=true "$@"
g++ -std=c++17 -O1 -Wno-format-security -Wno-unused-result -o driver driver.cpp
./driver "$N" "$SEED" "$EMPTY" "$NOPART"
python3 "$HERE/../diff_harness.py" Files/XPChart/dump_A.csv
python3 "$HERE/../diff_harness.py" --s3 Files/XPChart/dump_A.csv Files/XPChart/dump_B.csv | tail -1
echo "work dir: $WORK"
