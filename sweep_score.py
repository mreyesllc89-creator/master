#!/usr/bin/env python3
"""FGF sweep scorer (MODE = REAL).

Every number comes from a real Strategy Tester run that a person logged in a
run-log CSV. This script never applies costs: commission and slippage are set
in Strategy Tester Properties and are already inside every logged number.

Subcommands
  plan stage2   append the Stage 2 cells for one chart timeframe (28 cells)
  plan stage2b  append the Stage 2b cells (the strategy's own inputs) for one build
  plan stage3   append the Stage 3 grid (3 values per LIVE input, H1 and H2)
  score         score a run log: one row per cell per window, verdicts, report
  verify-trade  recompute one trade's net by hand to check the cost model once

Run-log columns
  run_id, stage, chart_tf, filter_tf, input, value, gate, window,
  net_profit, profit_factor, max_dd, trades, net_per_trade, notes

Conventions
  gate        on | off
  window      full | H1 | H2
  input       "defaults" for a baseline row; one input name for Stage 2 / 2b;
              "a=x;b=y" pairs for a Stage 3 grid cell (value left blank)
  Lines starting with '#' are comments and are skipped.
  A row whose net_profit is blank has not been run yet.
"""
import argparse
import csv
import io
import math
import sys
from collections import OrderedDict

COLUMNS = ["run_id", "stage", "chart_tf", "filter_tf", "input", "value", "gate", "window",
           "net_profit", "profit_factor", "max_dd", "trades", "net_per_trade", "notes"]

MIN_TRADES = {"full": 300, "H1": 150, "H2": 150}
BAND_FRACTION = 0.10       # Stage 2: a value must beat the default by > 10 % of |gate-off net|
STAGE1_KEEP = 2            # chart timeframes that go on to Stage 2
STAGE2_KEEP = 3            # LIVE inputs per chart timeframe that go to Stage 3
RUN_CAP = 40               # real runs per chart timeframe per stage

# Stage 2 ladders: (default, ordered ladder). Order matters for neighbours.
STAGE2 = OrderedDict([
    ("fgfTf",           ("60",                ["15", "30", "60", "120", "240"])),
    ("fgfBandAtr",      ("0.25",              ["0", "0.10", "0.25", "0.50", "1.00"])),
    ("fgfAgainst",      ("on",                ["on", "off"])),
    ("fgfBurstAtr",     ("0.50",              ["0.25", "0.50", "0.75", "1.00", "burst off"])),
    ("fgfMinAligned",   ("2",                 ["0", "1", "2", "3"])),
    ("zoneSet",         ("Z1+Z2+Z3",          ["Z1", "Z1+Z2", "Z1+Z2+Z3", "Z1..Z4 (480)"])),
    ("fgfLast",         ("Until next signal", ["Until next signal", "Candles 1", "Candles 3", "Minutes 60", "Minutes 240"])),
    ("fgfCheck",        ("Tick",              ["Tick", "Candle open", "Candle close"])),
    ("fgfLvMode",       ("Entry price",       ["Entry price", "Signal close"])),
    ("fgfEntryDistAtr", ("0.25",              ["0.10", "0.25", "0.50"])),
])

# Stage 2b ladders, accepted 2026-10-13 (maxOpen and lblRead dropped).
STAGE2B = {
    "v28": OrderedDict([
        ("slAtrMult",  ("3.0",         ["1.5", "2", "3", "4", "5"])),
        ("tpRMult",    ("1.0",         ["0.5", "1", "1.5", "2", "3"])),
        ("trailOn",    ("on",          ["on", "off"])),
        ("trActAtr",   ("1.0",         ["0.5", "1", "1.5", "2"])),
        ("trDistAtr",  ("0.75",        ["0.5", "0.75", "1", "1.5"])),
        ("timeStop",   ("0",           ["0", "20", "50", "100"])),
        ("entryFill",  ("Signal tick", ["Signal tick", "Limit at label price"])),
        ("sigRung",    ("chart rung",  ["chart rung", "every rung"])),
    ]),
    "fg5": OrderedDict([
        ("slPips",            ("30",   ["20", "30", "40"])),
        ("tpRPips",           ("5",    ["3", "5", "8"])),
        ("partPct",           ("30",   ["0", "30", "50", "100"])),
        ("runTrailPips",      ("600",  ["450", "600", "800"])),
        ("runBE",             ("on",   ["on", "off"])),
        ("entryValidBars",    ("3",    ["1", "3", "5", "0"])),
        ("allowReverse",      ("on",   ["on", "off"])),
        ("burstAtrMult",      ("0.5",  ["0.25", "0.5", "0.75", "1.0"])),
        ("entryDistAtrMult",  ("0.25", ["0.1", "0.25", "0.5"])),
        ("minAlignedZones",   ("2",    ["0", "1", "2", "3"])),
    ]),
}

TF_MINUTES = {"1": 1, "5": 5, "15": 15, "30": 30, "60": 60, "120": 120, "240": 240, "D": 1440, "1D": 1440}


# ----------------------------------------------------------------- I/O ----
def read_log(path):
    rows, comments = [], []
    with open(path, newline="") as f:
        for line in f:
            if line.startswith("#"):
                comments.append(line.rstrip("\n"))
                continue
            if line.strip():
                rows.append(line)
    reader = csv.DictReader(io.StringIO("".join(rows)))
    missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        sys.exit("run log is missing columns: %s" % ", ".join(missing))
    return comments, [dict(r) for r in reader]


def write_log(path, comments, rows):
    with open(path, "w", newline="") as f:
        for c in comments:
            f.write(c + "\n")
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def done(r):
    return num(r.get("net_profit")) is not None and num(r.get("trades")) is not None


def next_run_id(rows):
    ids = [int(r["run_id"]) for r in rows if str(r.get("run_id", "")).strip().isdigit()]
    return (max(ids) + 1) if ids else 1


def tf_minutes(tf):
    tf = str(tf).strip()
    return TF_MINUTES.get(tf, num(tf))


# ---------------------------------------------------------------- plans ----
def plan_stage2(rows, chart_tf):
    """28 cells: every non-default ladder value, one input changed at a time.
    Timeframe inputs never go below the chart timeframe."""
    new, rid = [], next_run_id(rows)
    ctf = tf_minutes(chart_tf)
    for name, (default, ladder) in STAGE2.items():
        for v in ladder:
            if v == default:
                continue
            note = ""
            if name == "fgfTf" and tf_minutes(v) is not None and ctf and tf_minutes(v) < ctf:
                note = "skipped: filter timeframe below chart timeframe"
            new.append({"run_id": rid, "stage": "2", "chart_tf": chart_tf,
                        "filter_tf": v if name == "fgfTf" else "60",
                        "input": name, "value": v, "gate": "on", "window": "full", "notes": note})
            rid += 1
    return new


def plan_stage2b(rows, chart_tf, build):
    new, rid = [], next_run_id(rows)
    for name, (default, ladder) in STAGE2B[build].items():
        for v in ladder:
            if v == default:
                continue
            new.append({"run_id": rid, "stage": "2b", "chart_tf": chart_tf, "filter_tf": "60",
                        "input": name, "value": v, "gate": "on", "window": "full", "notes": ""})
            rid += 1
    return new


def neighbours_of(ladder, value):
    i = ladder.index(value)
    out = []
    if i > 0:
        out.append(ladder[i - 1])
    if i < len(ladder) - 1:
        out.append(ladder[i + 1])
    return out


def plan_stage3(rows, chart_tf, live):
    """live: list of 'input=value' (the LIVE value). Grid = that value and its two
    ladder neighbours per input, every cell on H1 and H2, plus the four
    baseline rows (gate off / gate on defaults, H1 and H2)."""
    dims = []
    for item in live:
        name, value = item.split("=", 1)
        if name not in STAGE2:
            sys.exit("unknown Stage 2 input: %s" % name)
        ladder = STAGE2[name][1]
        if value not in ladder:
            sys.exit("%s is not on the %s ladder %s" % (value, name, ladder))
        dims.append((name, [x for x in [*neighbours_of(ladder, value)[:1], value, *neighbours_of(ladder, value)[1:]]]))
    if not 2 <= len(dims) <= 3:
        sys.exit("Stage 3 takes two or three LIVE inputs")
    cells = [[]]
    for name, vals in dims:
        cells = [c + ["%s=%s" % (name, v)] for c in cells for v in vals]
    new, rid = [], next_run_id(rows)
    for window in ("H1", "H2"):
        for gate in ("off", "on"):
            new.append({"run_id": rid, "stage": "3", "chart_tf": chart_tf, "filter_tf": "60",
                        "input": "defaults", "value": "", "gate": gate, "window": window, "notes": "baseline"})
            rid += 1
    for c in cells:
        for window in ("H1", "H2"):
            new.append({"run_id": rid, "stage": "3", "chart_tf": chart_tf, "filter_tf": "60",
                        "input": ";".join(c), "value": "", "gate": "on", "window": window, "notes": ""})
            rid += 1
    return new


# -------------------------------------------------------------- scoring ----
def key(r):
    return (str(r["chart_tf"]).strip(), r["window"].strip() or "full")


def baseline(rows, chart_tf, window, gate):
    for r in rows:
        if (str(r["chart_tf"]).strip() == str(chart_tf).strip() and (r["window"].strip() or "full") == window
                and r["gate"].strip() == gate and r["input"].strip() == "defaults" and done(r)):
            return r
    return None


def metrics(r, base):
    n, t = num(r["net_profit"]), num(r["trades"])
    npt = num(r["net_per_trade"])
    if npt is None and n is not None and t:
        npt = n / t
    out = {"net_profit": n, "profit_factor": num(r["profit_factor"]), "max_dd": num(r["max_dd"]),
           "trades": t, "net_per_trade": npt, "delta_net": None, "delta_npt": None,
           "eligible": t is not None and t >= MIN_TRADES.get(r["window"].strip() or "full", 300)}
    if base is not None and n is not None:
        bn, bt = num(base["net_profit"]), num(base["trades"])
        bnpt = num(base["net_per_trade"])
        if bnpt is None and bn is not None and bt:
            bnpt = bn / bt
        out["delta_net"] = n - bn
        out["delta_npt"] = (npt - bnpt) if (npt is not None and bnpt is not None) else None
    return out


def fmt(v, d=2):
    if v is None:
        return "-"
    if isinstance(v, float) and math.isnan(v):
        return "-"
    return ("%%.%df" % d) % v if isinstance(v, float) else str(v)


def score(rows):
    scored, lines = [], []
    pending = [r for r in rows if not done(r)]
    chart_tfs = []
    for r in rows:
        c = str(r["chart_tf"]).strip()
        if c and c not in chart_tfs:
            chart_tfs.append(c)

    # ---- Stage 1
    s1 = {}
    for c in chart_tfs:
        off, on = baseline(rows, c, "full", "off"), baseline(rows, c, "full", "on")
        if off is None or on is None:
            continue
        m = metrics(on, off)
        survive = (m["delta_net"] is not None and m["delta_net"] > 0 and m["eligible"]
                   and m["net_per_trade"] is not None and m["net_per_trade"] > 0)
        s1[c] = (m, survive)
        for g, r in (("off", off), ("on", on)):
            mm = metrics(r, off)
            scored.append(dict(stage="1", chart_tf=c, input="defaults", value="", gate=g, window="full", **mm))
    survivors = sorted([c for c in s1 if s1[c][1]], key=lambda c: -s1[c][0]["delta_net"])[:STAGE1_KEEP]
    if s1:
        best = max((s1[c][0]["delta_net"] for c in s1 if s1[c][0]["delta_net"] is not None), default=None)
        verdict = "TF_SURVIVOR" if survivors else "GATE_DEAD"
        lines.append("Stage 1: %s. Deciding number: %s. Decision needed: %s." % (
            verdict, fmt(best), "yes" if survivors else "no"))
        lines.append("")
        lines.append("| chart_tf | gate | net_profit | profit_factor | max_dd | trades | net_per_trade | delta_net | >=300 | verdict |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for c in chart_tfs:
            if c not in s1:
                continue
            for g in ("off", "on"):
                r = baseline(rows, c, "full", g)
                m = metrics(r, baseline(rows, c, "full", "off"))
                v = ("SURVIVE" if c in survivors else "dead") if g == "on" else ""
                lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    c, g, fmt(m["net_profit"]), fmt(m["profit_factor"]), fmt(m["max_dd"]), fmt(m["trades"], 0),
                    fmt(m["net_per_trade"]), fmt(m["delta_net"]), "yes" if m["eligible"] else "no", v))
        lines.append("")

    # ---- Stage 2 and 2b
    live_by_tf = {}
    for stage_name, ladders_by in (("2", {c: STAGE2 for c in chart_tfs}), ("2b", None)):
        for c in chart_tfs:
            off, on = baseline(rows, c, "full", "off"), baseline(rows, c, "full", "on")
            if off is None or on is None:
                continue
            B, D = num(off["net_profit"]), num(on["net_profit"])
            band = BAND_FRACTION * abs(B)
            cells = [r for r in rows if r["stage"].strip() == stage_name and str(r["chart_tf"]).strip() == c]
            if not cells:
                continue
            inputs = []
            for r in cells:
                if r["input"].strip() not in inputs:
                    inputs.append(r["input"].strip())
            ladders = STAGE2 if stage_name == "2" else {**STAGE2B["v28"], **STAGE2B["fg5"]}
            table, verdicts = [], []
            for name in inputs:
                if name not in ladders:
                    continue
                default, ladder = ladders[name]
                vals = {}
                for v in ladder:
                    if v == default:
                        vals[v] = on
                    else:
                        hit = [r for r in cells if r["input"].strip() == name and r["value"].strip() == v and done(r)]
                        vals[v] = hit[0] if hit else None
                ms = {v: (metrics(r, off) if r is not None else None) for v, r in vals.items()}
                for v in ladder:
                    m = ms[v]
                    if m is None:
                        table.append((name, v, None))
                        continue
                    scored.append(dict(stage=stage_name, chart_tf=c, input=name, value=v, gate="on", window="full", **m))
                    table.append((name, v, m))
                nets = [ms[v]["net_profit"] for v in ladder if ms[v] is not None and ms[v]["eligible"]]
                beats = lambda v: ms[v] is not None and ms[v]["eligible"] and ms[v]["net_profit"] > B
                best_v, best_gain = None, 0.0
                for v in ladder:
                    m = ms[v]
                    if m is None or v == default or not m["eligible"] or D is None:
                        continue
                    gain = m["net_profit"] - D
                    if gain > band and all(beats(n) for n in neighbours_of(ladder, v)) and gain > best_gain:
                        best_v, best_gain = v, gain
                flat = len(nets) >= 2 and (max(nets) - min(nets)) <= band
                pending_vals = [v for v in ladder if ms[v] is None]
                if pending_vals:
                    verdicts.append((name, "PENDING", None, None, pending_vals))
                elif best_v is not None and not flat:
                    verdicts.append((name, "INPUT_LIVE", best_v, best_gain, []))
                else:
                    verdicts.append((name, "INPUT_DEAD", None, None, []))
            live = sorted([v for v in verdicts if v[1] == "INPUT_LIVE"], key=lambda v: -v[3])[:STAGE2_KEEP]
            if stage_name == "2":
                live_by_tf[c] = live
            best = max((v[3] for v in verdicts if v[3] is not None), default=None)
            lines.append("Stage %s, chart %s: %s. Deciding number: %s. Decision needed: %s." % (
                stage_name, c, "INPUT_LIVE" if live else ("PENDING" if any(v[1] == "PENDING" for v in verdicts) else "INPUT_DEAD"),
                fmt(best), "yes" if live else "no"))
            lines.append("")
            lines.append("| input | value | net_profit | profit_factor | max_dd | trades | net_per_trade | delta_net vs off | >=300 |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for name, v, m in table:
                if m is None:
                    lines.append("| %s | %s | pending | | | | | | |" % (name, v))
                else:
                    lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                        name, v, fmt(m["net_profit"]), fmt(m["profit_factor"]), fmt(m["max_dd"]),
                        fmt(m["trades"], 0), fmt(m["net_per_trade"]), fmt(m["delta_net"]), "yes" if m["eligible"] else "no"))
            lines.append("")
            lines.append("| input | verdict | value | gain vs default | band (10 %% of |gate off|) = %s |" % fmt(band))
            lines.append("|---|---|---|---|---|")
            for name, verdict, v, gain, pend in verdicts:
                lines.append("| %s | %s | %s | %s | %s |" % (
                    name, verdict, v or "-", fmt(gain), ("pending: " + ", ".join(pend)) if pend else ""))
            if live:
                lines.append("")
                lines.append("To Stage 3: " + ", ".join("%s=%s" % (v[0], v[2]) for v in live))
            lines.append("")

    # ---- Stage 3
    for c in chart_tfs:
        cells = [r for r in rows if r["stage"].strip() == "3" and str(r["chart_tf"]).strip() == c and r["input"].strip() != "defaults"]
        if not cells:
            continue
        offs = {w: baseline(rows, c, w, "off") for w in ("H1", "H2")}
        ons = {w: baseline(rows, c, w, "on") for w in ("H1", "H2")}
        if any(v is None for v in list(offs.values()) + list(ons.values())):
            lines.append("Stage 3, chart %s: PENDING. Deciding number: -. Decision needed: no. Baseline H1/H2 rows missing." % c)
            lines.append("")
            continue
        grid = {}
        for r in cells:
            if not done(r):
                continue
            pairs = tuple(sorted(p.split("=", 1)[0] for p in r["input"].split(";")))
            vals = dict(p.split("=", 1) for p in r["input"].split(";"))
            grid.setdefault(tuple(sorted(vals.items())), {})[r["window"].strip()] = metrics(r, offs[r["window"].strip()])
        names = sorted({n for cell in grid for n, _ in cell})
        ladders = {n: STAGE2[n][1] for n in names}

        def idx(cell):
            d = dict(cell)
            return tuple(ladders[n].index(d[n]) for n in names)

        def is_neighbour(a, b):
            return a != b and max(abs(x - y) for x, y in zip(idx(a), idx(b))) <= 1

        pick, pick_net = None, None
        for cell, w in grid.items():
            m1 = w.get("H1")
            if m1 is None or not m1["eligible"] or m1["net_profit"] <= num(offs["H1"]["net_profit"]):
                continue
            nb = [o for o in grid if is_neighbour(cell, o)]
            # The pick needs its whole neighbourhood (8 cells in a 3x3, 26 in a
            # 3x3x3): only the plateau centre qualifies, never an edge or corner.
            if len(nb) < 3 ** len(names) - 1:
                continue
            if any(grid[o].get("H1") is None or not grid[o]["H1"]["eligible"]
                             or grid[o]["H1"]["net_profit"] <= num(offs["H1"]["net_profit"]) for o in nb):
                continue
            if pick_net is None or m1["net_profit"] > pick_net:
                pick, pick_net = cell, m1["net_profit"]
        lines.append("| cell | window | net_profit | profit_factor | max_dd | trades | net_per_trade | delta_net vs off | >=150 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for cell, w in grid.items():
            label = ";".join("%s=%s" % kv for kv in cell)
            for win in ("H1", "H2"):
                m = w.get(win)
                if m is None:
                    lines.append("| %s | %s | pending | | | | | | |" % (label, win))
                    continue
                scored.append(dict(stage="3", chart_tf=c, input=label, value="", gate="on", window=win, **m))
                lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                    label, win, fmt(m["net_profit"]), fmt(m["profit_factor"]), fmt(m["max_dd"]), fmt(m["trades"], 0),
                    fmt(m["net_per_trade"]), fmt(m["delta_net"]), "yes" if m["eligible"] else "no"))
        if pick is None:
            verdict, number, setting = "CONFIRM_FAIL", None, "defaults (no plateau on H1)"
        else:
            m2 = grid[pick].get("H2")
            on2 = num(ons["H2"]["net_profit"])
            if m2 is not None and m2["eligible"] and m2["net_profit"] > on2:
                verdict, number = "CONFIRM_PASS", m2["net_profit"] - num(offs["H2"]["net_profit"])
                setting = ";".join("%s=%s" % kv for kv in pick)
            else:
                verdict, number = "CONFIRM_FAIL", (m2["net_profit"] - on2) if m2 else None
                setting = "defaults (pick %s failed H2)" % ";".join("%s=%s" % kv for kv in pick)
        lines.insert(len(lines) - len(grid) * 2 - 2, "Stage 3, chart %s: %s. Deciding number: %s. Decision needed: %s. Setting: %s" % (
            c, verdict, fmt(number), "yes" if verdict == "CONFIRM_PASS" else "no", setting))
        lines.insert(len(lines) - len(grid) * 2 - 2, "")
        lines.append("")

    if pending:
        lines.append("Pending rows (not run): %d" % len(pending))
    return scored, lines


def write_scores(path, scored):
    cols = ["stage", "chart_tf", "input", "value", "gate", "window", "net_profit", "profit_factor",
            "max_dd", "trades", "net_per_trade", "delta_net", "delta_npt", "eligible"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for s in scored:
            w.writerow({k: s.get(k, "") for k in cols})


# ------------------------------------------------------- verify one trade ----
def verify_trade(a):
    sign = 1 if a.side == "long" else -1
    slip = a.slippage_ticks * a.tick_size
    entry = a.entry + sign * slip
    exit_ = a.exit - sign * slip
    gross = (exit_ - entry) * sign * a.qty
    commission = (entry + exit_) * a.qty * a.commission_pct / 100.0
    net = gross - commission
    print("entry filled %.4f, exit filled %.4f (slippage %d ticks x %.4f per side)" % (entry, exit_, a.slippage_ticks, a.tick_size))
    print("gross %.4f, commission %.4f (%.3f %% per side on notional), net %.4f" % (gross, commission, a.commission_pct, net))
    if a.expected is not None:
        diff = net - a.expected
        print("Strategy Tester net %.4f, difference %.4f (%s)" % (a.expected, diff, "match" if abs(diff) < 0.01 * max(1.0, abs(a.expected)) else "MISMATCH: check Properties"))


# ----------------------------------------------------------------- main ----
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("plan", help="append planned cells to a run log")
    pl.add_argument("what", choices=["stage2", "stage2b", "stage3"])
    pl.add_argument("--log", required=True)
    pl.add_argument("--chart-tf", required=True, help="e.g. 30")
    pl.add_argument("--build", choices=["v28", "fg5"], help="stage2b only")
    pl.add_argument("--live", nargs="*", default=[], help="stage3 only: input=LIVEvalue, two or three of them")

    sc = sub.add_parser("score", help="score a run log")
    sc.add_argument("--log", required=True)
    sc.add_argument("--out", help="scores CSV")
    sc.add_argument("--report", help="markdown report path (first lines = verdicts)")

    vt = sub.add_parser("verify-trade", help="recompute one trade's net by hand")
    vt.add_argument("--side", choices=["long", "short"], required=True)
    vt.add_argument("--entry", type=float, required=True, help="order price before slippage")
    vt.add_argument("--exit", type=float, required=True, help="order price before slippage")
    vt.add_argument("--qty", type=float, default=0.1)
    vt.add_argument("--commission-pct", type=float, default=0.02, help="percent per side, default 0.02")
    vt.add_argument("--slippage-ticks", type=int, default=50)
    vt.add_argument("--tick-size", type=float, default=0.1, help="MEXC:BTCUSDT.P tick 0.1 USDT")
    vt.add_argument("--expected", type=float, help="net shown by the Strategy Tester for this trade")

    a = p.parse_args()
    if a.cmd == "plan":
        comments, rows = read_log(a.log)
        if a.what == "stage2":
            new = plan_stage2(rows, a.chart_tf)
        elif a.what == "stage2b":
            if not a.build:
                sys.exit("--build v28|fg5 is required for stage2b")
            new = plan_stage2b(rows, a.chart_tf, a.build)
        else:
            new = plan_stage3(rows, a.chart_tf, a.live)
        real = [r for r in new if not r.get("notes", "").startswith("skipped")]
        if len(real) > RUN_CAP:
            sys.exit("plan would need %d runs, cap is %d" % (len(real), RUN_CAP))
        write_log(a.log, comments, rows + new)
        print("appended %d rows (%d real runs) to %s" % (len(new), len(real), a.log))
    elif a.cmd == "score":
        _, rows = read_log(a.log)
        scored, lines = score(rows)
        text = "\n".join(lines)
        print(text)
        if a.out:
            write_scores(a.out, scored)
        if a.report:
            with open(a.report, "w") as f:
                f.write(text + "\n")
    else:
        verify_trade(a)


if __name__ == "__main__":
    main()
