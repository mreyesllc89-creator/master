"""
STEP 4 - final_report.py

Assembles outputs/final_report.md:
  line 1: VERDICT WORD | deciding number | decision yes/no
  then the three step reports, verbatim. Nothing else.

Deciding number: the tick-replay profit factor after costs (step3).
Decision rule (stated, not tuned):
  yes  <=> no defect in any step AND profit factor > 1.0
           AND parity match rate >= --min-parity (default 0.90)
  verdict word: PASS / FAIL / BLOCKED (BLOCKED when any step named a defect)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--min-parity", type=float, default=0.90)
    a = ap.parse_args()
    out = Path(a.project) / "outputs"

    def load(n):
        p = out / n
        return json.loads(p.read_text()) if p.exists() else None

    s1, s2, s3 = load("step1_report.json"), load("step2_report.json"), load("step3_report.json")
    defects = []
    for tag, s in (("step1", s1), ("step2", s2), ("step3", s3)):
        if s is None:
            defects.append(f"{tag}: MISSING_REPORT")
        else:
            defects += [f"{tag}: {d['name']}" for d in s.get("defects", [])]
    pf = (s3 or {}).get("metrics", {}).get("profit_factor")
    parity = ((s2 or {}).get("diff") or {}).get("match_rate")

    if defects:
        word, decision = "BLOCKED", "no"
    elif pf is not None and pf > 1.0 and parity is not None and parity >= a.min_parity:
        word, decision = "PASS", "yes"
    else:
        word, decision = "FAIL", "no"
    pf_s = "n/a" if pf is None else f"{pf:.3f}"
    first = f"{word} | profit factor {pf_s} | decision {decision}"
    if defects:
        first += f"  ({'; '.join(defects)})"

    parts = [first, ""]
    for n in ("step1_report.md", "step2_report.md", "step3_report.md"):
        p = out / n
        parts.append(p.read_text(encoding="utf-8") if p.exists() else f"# {n} MISSING\n")
    (out / "final_report.md").write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts))


if __name__ == "__main__":
    main()
