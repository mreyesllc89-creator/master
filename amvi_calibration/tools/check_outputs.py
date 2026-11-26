"""Checks on what report.py wrote. Exit code 1 when one fails.

usage: python check_outputs.py [calibration_dir]

  trade lists   the numbers of final_<tf>m.json recomputed from results/trades_BTCUSDT_<tf>.csv
                (trade count, net R, profit factor, drawdown, the two halves, the years) for
                the search window and the untouched period;
  presets       every calibrated file compared line by line with the shipped script: only the
                header, the strategy title, the commission, the margin and input defaults (with
                their tooltips) may differ; every input default must be the pick's value; a
                string default must be one of the input's options;
  verdicts      a file exists exactly for the timeframes rated PAPER-TRADE or better.
"""
import csv
import json
import os
import re
import sys

import numpy as np
import pandas as pd

import final_eval as F
import make_pine
import space

SIZING = ("fixedQtyS3", "riskPctS3", "maxQtyS3", "marginPctS3")


def max_dd(r):
    if len(r) == 0:
        return 0.0
    eq = np.cumsum(r)
    return float((np.maximum.accumulate(np.maximum(eq, 0.0)) - eq).max())


def check_trades(root, tf, fin, problems):
    name = make_pine.TF_NAME[tf]
    path = os.path.join(root, "results", f"trades_BTCUSDT_{name}.csv")
    if not os.path.exists(path):
        problems.append(f"{name}: no trade list")
        return
    rows = list(csv.DictReader(open(path)))
    mid = pd.Timestamp(F.half_split(*F.SEARCH), unit="ms")
    for period, key in (("search", "base"), ("untouched", "pre")):
        st = fin["eval"].get(key)
        r = [x for x in rows if x["period"] == period]
        net = np.array([float(x["net_R"]) for x in r])
        if not st or st.get("n", 0) == 0:
            if net.size:
                problems.append(f"{name} {period}: {net.size} trades in the list, none in the record")
            continue
        tol = 0.0006 * net.size + 0.05        # the list is rounded to 0.001 R per trade
        if net.size != st["n"]:
            problems.append(f"{name} {period}: {net.size} trades in the list, {st['n']} in the record")
            continue
        if abs(net.sum() - st["total"]) > tol:
            problems.append(f"{name} {period}: net {net.sum():+.2f}R in the list, {st['total']:+.2f}R in the record")
        wins, losses = net[net > 0].sum(), -net[net <= 0].sum()
        pf = wins / losses if losses > 0 else 99.0
        if abs(pf - st["pf"]) > 0.02 + 0.02 * st["pf"]:
            problems.append(f"{name} {period}: profit factor {pf:.2f} in the list, {st['pf']:.2f} in the record")
        if abs(max_dd(net) - st["dd"]) > tol:
            problems.append(f"{name} {period}: drawdown {max_dd(net):.2f}R in the list, {st['dd']:.2f}R in the record")
        gross = np.array([float(x["gross_R"]) for x in r])
        fee = np.array([float(x["fee_R"]) for x in r])
        fund = np.array([float(x["funding_R"]) for x in r])
        if np.abs(gross - fee - fund - net).max() > 0.0021:
            problems.append(f"{name} {period}: gross - fee - funding is not net on some trade")
        t = pd.to_datetime([x["entry_utc"] for x in r])
        if period == "search":
            h1, h2 = net[t < mid].sum(), net[t >= mid].sum()
            if abs(h1 - st["h1"]) > tol or abs(h2 - st["h2"]) > tol:
                problems.append(f"{name}: halves {h1:+.2f} / {h2:+.2f}R in the list, {st['h1']:+.2f} / {st['h2']:+.2f}R in the record")
        years = fin["eval"].get("by_year" if period == "search" else "pre_by_year", [])
        for y in years:
            m = np.asarray(t.year == y["year"])
            if int(m.sum()) != y["n"] or abs(net[m].sum() - y["total"]) > tol:
                problems.append(f"{name} {period} {y['year']}: {int(m.sum())} trades {net[m].sum():+.2f}R in the list, {y['n']} trades {y['total']:+.2f}R in the record")
        side = {"long": 0, "short": 0}
        for x in r:
            side[x["side"]] += 1
        if side["long"] != st["n_long"] or side["short"] != st["n_short"]:
            problems.append(f"{name} {period}: long/short {side['long']}/{side['short']} in the list, {st['n_long']}/{st['n_short']} in the record")


def input_line(src, name):
    m = re.search(r"^" + re.escape(name) + r"\s*=\s*input\.(\w+)\((\"[^\"]*\"|[^,]+),(.*)$", src, re.M)
    return m


def check_preset(root, tf, fin, problems):
    name = make_pine.TF_NAME[tf]
    path = os.path.join(root, "presets", f"AMVI_FGF_BTCUSDT_{name}.pine")
    tpl = open(make_pine.TEMPLATE, encoding="utf-8").read()
    src = open(path, encoding="utf-8").read()
    p = space.normalize(fin["setting"])
    want = make_pine.pine_inputs(p, tf)
    # every input default is the pick's value, and a string default is one of the options
    for nm, val in want.items():
        m = input_line(src, nm)
        if not m:
            problems.append(f"{name}: input {nm} not found in the file")
            continue
        got = m.group(2).strip()
        if got != make_pine.lit(val) and not make_pine._same_number(got, make_pine.lit(val)):
            problems.append(f"{name}: {nm} is {got} in the file, the pick has {make_pine.lit(val)}")
        opt = re.search(r"options\s*=\s*\[([^\]]*)\]", m.group(3))
        if m.group(1) == "string" and opt:
            options = re.findall(r"\"([^\"]*)\"", opt.group(1))
            if got.strip('"') not in options:
                problems.append(f"{name}: {nm} = {got} is not among its options {options}")
    # nothing else differs from the shipped script
    body_t = tpl[tpl.index("strategy("):].split("\n")
    body_s = src[src.index("strategy("):].split("\n")
    if len(body_t) != len(body_s):
        problems.append(f"{name}: the file has {len(body_s)} code lines, the shipped script {len(body_t)}")
        return
    allowed = set(want) | set(SIZING)
    for k, (a, b) in enumerate(zip(body_t, body_s)):
        if a == b:
            continue
        lhs = b.split("=")[0].strip()
        if lhs in allowed and a.split("=")[0].strip() == lhs:
            continue
        if k < 4 and ("strategy(" in b or "commission_value" in b or "margin_long" in b):
            continue
        problems.append(f"{name}: line {k + 1} after strategy( differs from the shipped script and is not an input default: {b.strip()[:90]}")
    head = src[:src.index("strategy(")]
    if any(not ln.startswith("//") for ln in head.split("\n") if ln.strip()):
        problems.append(f"{name}: the header has a line that is not a comment")
    if any(len(ln) > 120 for ln in head.split("\n")):
        problems.append(f"{name}: a header line is longer than 120 characters")
    if fin["verdict"] not in head:
        problems.append(f"{name}: the header does not carry the verdict {fin['verdict']}")


def run(root):
    problems = []
    res = os.path.join(root, "results")
    verdicts = {v["tf"]: v["verdict"] for v in json.load(open(os.path.join(res, "verdicts.json")))}
    n_files = 0
    for tf in space.CHART_TFS:
        name = make_pine.TF_NAME[tf]
        fp = os.path.join(res, f"final_{tf}m.json")
        preset = os.path.join(root, "presets", f"AMVI_FGF_BTCUSDT_{name}.pine")
        should = verdicts.get(tf) in ("RECOMMENDED", "USABLE", "PAPER-TRADE")
        if os.path.exists(preset) != should:
            problems.append(f"{name}: verdict {verdicts.get(tf)} but the file {'exists' if os.path.exists(preset) else 'is missing'}")
        if not os.path.exists(fp):
            continue
        fin = json.load(open(fp))
        if fin["verdict"] != verdicts.get(tf):
            problems.append(f"{name}: verdict differs between final_{tf}m.json and verdicts.json")
        check_trades(root, tf, fin, problems)
        if os.path.exists(preset):
            n_files += 1
            check_preset(root, tf, fin, problems)
    for q in problems:
        print("PROBLEM:", q)
    print(f"checked {len(verdicts)} timeframes, {n_files} calibrated files: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
