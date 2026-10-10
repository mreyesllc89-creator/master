"""
STEP 3a - cost_audit.py  (READ-ONLY, run before backtest_ticks.py)

Confirms, without changing anything:
  1. the engine's commission type and value   (required: percent, 0.02 per side)
  2. slippage value                            (required: 5 USD per side)
  3. quantity                                  (required: fixed contracts, no risk-percent sizing)
  4. the quantity is actually used by entries and not overridden by a calcQty path
  5. no spread input double-charges on top of bid/ask fills

Then the SIBLING CHECK: the same tokens in backtest.py and shadow.py (and
shadow_report.py, mexc_data.py for completeness), so a defect found in the
engine's cost path is reported wherever else it appears. Report only.

Output: outputs/cost_audit.md (+ .json). Items 4 and 5 are printed with every
matching source line so the reader (Codex) fills the verdict by reading them;
the script does not pretend to parse control flow.

Usage: python cost_audit.py --require-commission-pct 0.02 --require-slippage-usd 5 --require-leverage 10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TOKENS = {
    "commission": re.compile(r"commission", re.I),
    "slippage": re.compile(r"slip", re.I),
    "qty": re.compile(r"\bqty\b|quantity|contracts?\b|position_size|lot", re.I),
    "calcQty": re.compile(r"calc_?qty|size_?position|position_?sizing|risk_?pct|risk_?percent|percent_of_equity|equity\s*\*", re.I),
    "spread": re.compile(r"spread", re.I),
    "leverage": re.compile(r"leverage|margin", re.I),
}
FILES = ["xpw_engine.py", "backtest.py", "shadow.py", "shadow_report.py", "mexc_data.py"]


def scan(path: Path) -> dict:
    hits = {k: [] for k in TOKENS}
    if not path.exists():
        return {"missing": True, "hits": hits}
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = line.strip()
        if s.startswith("#"):
            continue
        for k, rx in TOKENS.items():
            if rx.search(line):
                hits[k].append((i, line.rstrip()))
    return {"missing": False, "hits": hits}


def runtime_values() -> dict:
    try:
        import engine_adapter as ea
        return {"strategy_params": ea.get_strategy_params(), "engine_costs": ea.get_engine_costs()}
    except SystemExit as e:
        return {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def verdict(found, required, label) -> str:
    if found is None:
        return f"UNKNOWN - {label} not found by name in xpw_engine (read the source lines below)"
    try:
        ok = abs(float(found) - float(required)) < 1e-12
    except (TypeError, ValueError):
        return f"UNKNOWN - {label} = {found!r} is not numeric"
    return f"{'CONFIRMED' if ok else 'MISMATCH'} - {label} = {found!r}, required {required!r}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--require-commission-pct", type=float, default=0.02)
    ap.add_argument("--require-slippage-usd", type=float, default=5.0)
    ap.add_argument("--require-leverage", type=float, default=10.0)
    a = ap.parse_args()
    project = Path(a.project)
    out_dir = project / "outputs"
    out_dir.mkdir(exist_ok=True)

    scans = {f: scan(project / f) for f in FILES}
    rt = runtime_values()
    costs = rt.get("engine_costs", {})

    # commission: 0.02% could be stored as 0.02 (percent) or 0.0002 (fraction)
    cv = costs.get("commission_value")
    comm_line = verdict(cv, a.require_commission_pct, "commission value")
    if cv is not None and abs(float(cv) - a.require_commission_pct / 100.0) < 1e-12:
        comm_line = f"CONFIRMED (as fraction) - commission value = {cv!r} == {a.require_commission_pct}% / 100"
    checks = {
        "1_commission_type": f"{costs.get('commission_type')!r} (required: percent of notional, per side)" if costs.get("commission_type") is not None else "UNKNOWN - no commission_type name found; read lines below",
        "1_commission_value": comm_line,
        "2_slippage": verdict(costs.get("slippage"), a.require_slippage_usd, "slippage"),
        "3_qty": f"{costs.get('qty')!r} qty_type={costs.get('qty_type')!r} risk_pct={costs.get('risk_pct')!r} (required: fixed contracts, risk_pct unused)",
        "3_leverage": verdict(costs.get("leverage"), a.require_leverage, "leverage"),
        "4_qty_used_by_entries_not_calcQty": "MANUAL - read the calcQty/qty lines below; fill verdict in the report",
        "5_no_spread_double_charge": "MANUAL - read the spread lines below; with bid/ask tick fills any spread cost input must be zero or unused",
    }

    report = {"runtime": rt, "checks": checks, "scans": {f: {"missing": s["missing"], "hits": {k: [[i, l] for i, l in v] for k, v in s["hits"].items()}} for f, s in scans.items()}}
    (out_dir / "cost_audit.json").write_text(json.dumps(report, indent=2, default=str))

    L = ["# STEP 3 - COST AUDIT (read-only, before the first tick run)", ""]
    L.append("## Runtime values (engine_adapter.get_engine_costs / get_strategy_params)")
    L.append("```")
    L.append(json.dumps(rt, indent=2, default=str))
    L.append("```")
    L.append("")
    L.append("## Checklist")
    for k, v in checks.items():
        L.append(f"- {k}: {v}")
    L.append("")
    L.append("## Source lines - xpw_engine.py")
    L += _lines(scans["xpw_engine.py"])
    L.append("")
    L.append("## SIBLING CHECK - same tokens in backtest.py and shadow.py (report only)")
    for f in ("backtest.py", "shadow.py", "shadow_report.py", "mexc_data.py"):
        L.append(f"### {f}")
        L += _lines(scans[f])
        L.append("")
    md = "\n".join(L) + "\n"
    (out_dir / "cost_audit.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def _lines(s: dict) -> list[str]:
    if s["missing"]:
        return ["- file missing"]
    out = []
    for k, hits in s["hits"].items():
        out.append(f"- **{k}**: {len(hits)} line(s)")
        for i, line in hits[:40]:
            out.append(f"    - L{i}: `{line.strip()[:160]}`")
        if len(hits) > 40:
            out.append(f"    - ... {len(hits) - 40} more in cost_audit.json")
    return out


if __name__ == "__main__":
    sys.exit(main())
