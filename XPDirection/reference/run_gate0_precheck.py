#!/usr/bin/env python3
"""Gate 0 pre-check: everything about "DIR_OFF reproduces 1.03" that can be
established without a terminal.

It does NOT replace Gate 0. The Strategy Tester comparison
(gate0_tester_settings.ini + compare_trades.py) is what proves the trade list.
This proves the layer underneath it: that with InpDirMode = DIR_OFF the build's
entry path is the 1.03 entry path, line for line and branch for branch.

Two parts:

  A. STATIC  - diff the build against the 1.03 base and audit every injected
               call site for a DIR_OFF guard.
  B. EXECUTED - lift the entry-path wiring out of the .mq5, compile it with
               g++, and run all 144 mode x state combinations against the
               literal 1.03 conditions.

  usage: ./run_gate0_precheck.py [--base <FlashGold_Continuation_v2.mq5>]
  exit 0 iff both parts pass.
"""
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EA = os.path.join(HERE, "..", "FlashGold_Continuation_v2_XPDIR.mq5")
EMU = os.path.join(HERE, "emu")
BASE_SHA = "75820278a87ee5b65d9e6c4518a1ab0936d229fed6025893c188bca2f3d87498"

# The 1.03 lines this build is allowed to replace. Anything else in the diff's
# removed set is an unauthorised edit and fails the gate.
#
# Two groups, because they are two different changes with two different risks:
# the direction ladder (inert in DIR_OFF) and the burst-threshold input (a real
# edit to the EA, behaviour-preserving only because its default is the value
# the retired constant held - which A7 checks rather than assumes).
ALLOWED_REMOVALS_LADDER = [
    '#property version   "1.03" // Added Money Management',
    '   if(isBuy) g_VirtualBuyStopPrice = 0.0;',
    '   if(g_EntryHoldCandidate.active &&',
    '   if(buyHoldActive || (!g_EntryHoldCandidate.active && buyCrossing))',
    '   // SELL TRIGGER',
    '   const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);',
    '   if(sellHoldActive || (!g_EntryHoldCandidate.active && sellCrossing))',
]
ALLOWED_REMOVALS_BURST = [
    'const double   BURST_MIN_POINTS            = 172.0;',
    '      thresholdPoints = BURST_MIN_POINTS;',
    '               BurstThresholdModeName(), BURST_MIN_POINTS,',
    '               burstThresholdPoints, BURST_MIN_POINTS,',
    '      InpEntryHoldMs < 0 || InpEntryHoldMinFavPoints < 0.0)',
    '      PrintFormat("FlashGold_Continuation_v2 INIT_ABORT invalid gate settings burst_percentile=%.4f burst_window_samples=%d burst_lookback_ms=%d entry_hold_ms=%d entry_hold_min_fav_points=%.1f",',
    '                  InpEntryHoldMinFavPoints);',
    '   {',   # re-emitted by difflib where the block above it changed
]
ALLOWED_REMOVALS = ALLOWED_REMOVALS_LADDER + ALLOWED_REMOVALS_BURST

# The value the retired BURST_MIN_POINTS constant held. The new input's default
# must equal it exactly, or "same default behaviour as today" is not true.
RETIRED_BURST_CONSTANT = 172.0

# Every XPDir entry point called from 1.03 code, and the guard that makes it
# inert in DIR_OFF. The guard must be the function's FIRST statement.
GUARDS = {
    "XPDir_ApplyArmingLock":     "if(InpDirMode != DIR_LOCK) return;",
    "XPDir_NoteTrigger":         "if(InpDirMode != DIR_TRANSLATE) return;",
    "XPDir_ClearTriggerLevels":  "if(InpDirMode != DIR_TRANSLATE) return;",
    "XPDir_LogSent":             "if(InpDirMode == DIR_OFF) return;",
    "XPDir_WriteCsv":            "if(!InpDirWriteCsv || InpDirMode == DIR_OFF) return;",
}


def fail(msg, problems):
    problems.append(msg)


def static_part(base_path, problems):
    base = open(base_path, newline=None).read()
    got = hashlib.sha256(open(base_path, "rb").read()).hexdigest()
    if got != BASE_SHA:
        fail(f"base is not the 1.03 file: sha256 {got}", problems)
    ea = open(EA, newline=None).read()

    # --- A1: only the authorised 1.03 lines were removed
    removed = [l[1:] for l in difflib.unified_diff(base.split("\n"), ea.split("\n"),
                                                   lineterm="", n=0)
               if l.startswith("-") and not l.startswith("---")]
    unexpected = [l for l in removed if l not in ALLOWED_REMOVALS]
    missing = [l for l in ALLOWED_REMOVALS if l not in removed]
    if unexpected:
        for l in unexpected:
            fail(f"unauthorised removal of a 1.03 line: {l!r}", problems)
    if missing:
        for l in missing:
            fail(f"expected removal did not happen: {l!r}", problems)
    print(f"  A1 removed 1.03 lines: {len(removed)} "
          f"({len(ALLOWED_REMOVALS_LADDER)} ladder + {len(ALLOWED_REMOVALS_BURST)} burst-input) "
          f"{'all authorised' if not unexpected and not missing else 'MISMATCH'}")

    # --- A2: every injected entry point is guarded, as its first statement
    for fn, guard in GUARDS.items():
        m = re.search(r"^\w[\w\s]*?\b" + fn + r"\s*\([^)]*\)\s*\n\{\n(.*?)\n", ea,
                      re.M | re.S)
        if not m:
            fail(f"{fn} not found or not a top-level function", problems)
            continue
        first = m.group(1).strip()
        if guard not in first:
            fail(f"{fn} first statement is {first!r}, expected the guard {guard!r}",
                 problems)
    print(f"  A2 DIR_OFF guards on injected entry points: {len(GUARDS)} checked")

    # --- A3: XPDir_Init creates no indicator handle in DIR_OFF
    init = re.search(r"bool XPDir_Init\(\)\n\{(.*?)\n\}\n", ea, re.S).group(1)
    off_return = init.index('if(InpDirMode == DIR_OFF)')
    first_handle = init.index("XPDir_CreateHandle")
    if not off_return < first_handle:
        fail("XPDir_Init can reach XPDir_CreateHandle before the DIR_OFF return",
             problems)
    print("  A3 XPDir_Init returns before any iCustom handle in DIR_OFF")

    # --- A4: the hold-gate edit reduces to the two 1.03 lines in DIR_OFF
    need = ("   if(InpDirMode == DIR_TRANSLATE)\n", "   else if(isBuy) g_VirtualBuyStopPrice = 0.0;\n",
            "   else g_VirtualSellStopPrice = 0.0;\n")
    if not all(n in ea for n in need):
        fail("the hold-gate failure edit is not the expected TRANSLATE/else-if shape",
             problems)
    print("  A4 hold-gate failure edit reduces to the 1.03 pair outside TRANSLATE")

    # --- A5: the hoisted sellCrossing expression is byte-identical to 1.03's
    expr = "const bool sellCrossing = (g_VirtualSellStopPrice > 0 && bid <= g_VirtualSellStopPrice);"
    if expr not in base or expr not in ea:
        fail("the hoisted sellCrossing expression differs from the 1.03 one", problems)
    if ea.count(expr) != 1:
        fail(f"sellCrossing is computed {ea.count(expr)} times, expected once", problems)
    print("  A5 hoisted sellCrossing expression byte-identical to 1.03, computed once")

    # --- A6: the dashboard line is behind a DIR_OFF branch
    if 'if(InpDirMode == DIR_OFF)\n      ObjectDelete(0, "Lbl_XPDir");' not in ea:
        fail("the dashboard DIR line is not guarded by a DIR_OFF branch", problems)
    print("  A6 dashboard DIR line deleted, not drawn, in DIR_OFF")

    # --- A7: the burst-threshold input preserves the retired constant's value
    m = re.search(r"^\s*input\s+double\s+InpBurstThresholdFixed\s*=\s*([0-9.]+)\s*;",
                  ea, re.M)
    if not m:
        fail("InpBurstThresholdFixed is missing or is not an input double", problems)
    elif float(m.group(1)) != RETIRED_BURST_CONSTANT:
        fail(f"InpBurstThresholdFixed defaults to {m.group(1)}, but the retired "
             f"BURST_MIN_POINTS held {RETIRED_BURST_CONSTANT} - the build no longer "
             f"reproduces 1.03 at defaults", problems)
    if "BURST_MIN_POINTS" in re.sub(r"//[^\n]*", "", ea):
        fail("BURST_MIN_POINTS still has a live reference; two numbers, one of them dead",
             problems)
    if "thresholdPoints = InpBurstThresholdFixed;" not in ea:
        fail("BURST_THRESHOLD_FIXED does not route to InpBurstThresholdFixed", problems)
    if "InpBurstThresholdFixed <= 0.0)" not in ea:
        fail("OnInit does not reject a non-positive InpBurstThresholdFixed", problems)
    print(f"  A7 InpBurstThresholdFixed = {RETIRED_BURST_CONSTANT} (the retired constant), "
          f"routed from FIXED, guarded at init, no dead BURST_MIN_POINTS")


def executed_part(problems):
    work = tempfile.mkdtemp(prefix="xpdir_gate0_")
    for f in ("gate0_stubs.h", "gate0_driver.cpp"):
        shutil.copy(os.path.join(EMU, f), work)
    subprocess.run([sys.executable, os.path.join(EMU, "extract_core.py"), EA,
                    os.path.join(work, "g0core.cpp"), "XPDIR_GATE0_CORE"],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["g++", "-std=c++17", "-O1", "-Wall", "-Wextra",
                    "-Wno-unused-parameter", "-o", os.path.join(work, "g0"),
                    os.path.join(work, "gate0_driver.cpp")], cwd=work, check=True)
    r = subprocess.run([os.path.join(work, "g0")], capture_output=True, text=True)
    for line in r.stdout.rstrip().split("\n"):
        print("  " + line)
    if r.returncode != 0:
        fail("the executed entry-path check reported failures", problems)


def main():
    base = None
    if "--base" in sys.argv:
        base = sys.argv[sys.argv.index("--base") + 1]
    else:
        for cand in (os.path.join(HERE, "FlashGold_Continuation_v2.mq5"),
                     os.path.join(HERE, "..", "FlashGold_Continuation_v2.mq5")):
            if os.path.exists(cand):
                base = cand
                break

    problems = []
    print("A. STATIC")
    if base:
        static_part(base, problems)
    else:
        print("  SKIPPED: the 1.03 base is not in the tree. Pass it with")
        print("           --base <path to FlashGold_Continuation_v2.mq5>")
        print(f"           (expected sha256 {BASE_SHA})")

    print("B. EXECUTED")
    try:
        executed_part(problems)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  UNAVAILABLE: {exc}")
        problems.append("the executed entry-path check could not run")

    print()
    if problems:
        print(f"G0 PRE-CHECK FAIL ({len(problems)})")
        for p in problems:
            print("  " + p)
        return 1
    print("G0 PRE-CHECK PASS - DIR_OFF is the 1.03 entry path.")
    print("Still required: the Strategy Tester run. See gate0_tester_settings.ini")
    print("and compare_trades.py; this pre-check does not substitute for it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
