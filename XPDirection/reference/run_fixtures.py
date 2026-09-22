#!/usr/bin/env python3
"""Gate 1 runner.

Three sources must agree on every fixture:
  1. the hand-derived expectation in the fixture CSV;
  2. vote_ref.py, an independent transliteration of the prompt's section 4;
  3. the EA's OWN rule core, lifted verbatim out of
     FlashGold_Continuation_v2_XPDIR.mq5 by reference/emu/extract_core.py and
     compiled and executed by g++ (the XPMap emu approach).

  usage: ./run_fixtures.py [--no-emu]
  exit 0 iff asserts > 0 and mismatches == 0.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vote_ref  # noqa: E402

EA = os.path.join(HERE, "..", "FlashGold_Continuation_v2_XPDIR.mq5")
FIXTURES = os.path.join(HERE, "fixtures", "vote_rules.csv")
EMU = os.path.join(HERE, "emu")
COLS = ("dir", "rule", "conflict", "p_grade", "c1_grade")


def build_and_run_emu():
    """Extract the MQL5 rule core, compile it, run the fixtures through it."""
    work = tempfile.mkdtemp(prefix="xpdir_emu_")
    core = os.path.join(work, "core.cpp")
    subprocess.run([sys.executable, os.path.join(EMU, "extract_core.py"), EA, core],
                   check=True)
    for f in ("mql5_stubs.h", "driver.cpp"):
        with open(os.path.join(EMU, f)) as src, open(os.path.join(work, f), "w") as dst:
            dst.write(src.read())
    # stub lint first (syntax/type check only), then the real build
    subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "-Wall", "-Wextra",
                    "-Wno-unused-parameter", os.path.join(work, "driver.cpp")],
                   cwd=work, check=True)
    print("stub lint: 0 errors 0 warnings")
    subprocess.run(["g++", "-std=c++17", "-O1", "-o", os.path.join(work, "driver"),
                    os.path.join(work, "driver.cpp")], cwd=work, check=True)
    out = subprocess.run([os.path.join(work, "driver"), FIXTURES],
                         capture_output=True, text=True, check=True).stdout
    rows, head = {}, None
    for line in out.strip().split("\n"):
        cells = line.split(",")
        if head is None:
            head = cells
            continue
        rows[cells[0]] = dict(zip(head, cells))
    return rows


def main():
    use_emu = "--no-emu" not in sys.argv
    fixtures = vote_ref.load_fixtures(FIXTURES)
    emu_rows = {}
    if use_emu:
        try:
            emu_rows = build_and_run_emu()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"EMU UNAVAILABLE: {exc}")
            use_emu = False

    asserts = 0
    mismatches = []
    for row in fixtures:
        got = vote_ref.evaluate_row(row)
        name = row["name"]
        want = {"dir": row["expect_dir"], "rule": row["expect_rule"],
                "conflict": int(row["expect_conflict"]),
                "p_grade": row["expect_p_grade"],
                "c1_grade": row["expect_c1_grade"]}

        for col in COLS:
            asserts += 1
            if str(got[col]) != str(want[col]):
                mismatches.append(f"{name}: expected {col}={want[col]} got {got[col]}")

        if use_emu:
            emu = emu_rows.get(name)
            if emu is None:
                mismatches.append(f"{name}: missing from the compiled MQL5 core run")
                continue
            for col in list(COLS) + ["P", "C1", "C5", "C10", "C15", "C30", "C45"]:
                asserts += 1
                if str(emu[col]) != str(got[col]):
                    mismatches.append(
                        f"{name}: MQL5 core {col}={emu[col]} != vote_ref {col}={got[col]}")

    print(f"fixtures={len(fixtures)} asserts={asserts} mismatches={len(mismatches)} "
          f"emu={'on' if use_emu else 'OFF'}")
    for m in mismatches:
        print("  MISMATCH " + m)
    if not fixtures or not asserts:
        print("G1 FAIL: no asserts ran")
        return 1
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
