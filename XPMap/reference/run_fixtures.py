#!/usr/bin/env python3
"""
run_fixtures.py - GATE A. Replays every fixtures/*.csv through shapemap_ref.py and compares the
hand-derived exp_* columns. Blank cell = not asserted; "na" = must be na. Float tolerance 1e-5
(expectations were derived by hand to 6 decimals).

Exit code 0 = all fixtures pass.
"""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapemap_ref as ref

TOL = 1e-5
COLMAP = {  # exp_<name> -> reference output key
    "rsi": "rsi", "atr": "atr", "state": "isRedNow", "runLen": "runLen", "botHit": "botHit", "topHit": "topHit",
    "upTick": "upTick", "dnTick": "dnTick", "upTickAtr": "upTickAtr", "dnTickAtr": "dnTickAtr", "mBars": "mBars",
    "eff1": "eff1", "eff2": "eff2", "vel1": "vel1", "vel2": "vel2",
    "botSep": "botSep", "botTop": "botTop", "botBot": "botBot", "topSep": "topSep", "topTop": "topTop", "topBot": "topBot",
    "prevTop": "prevTop",
}


def parse_value(v):
    v = v.strip()
    if v == "":
        return None, False
    if v.lower() == "na":
        return ref.NA, True
    return float(v), True


def load(path):
    params, note = {}, ""
    rows = []
    with open(path, newline="") as fh:
        lines = fh.read().splitlines()
    body = []
    for ln in lines:
        if ln.startswith("# params:"):
            for kv in ln[len("# params:"):].split():
                k, v = kv.split("=")
                params[k] = (v == "True") if v in ("True", "False") else (float(v) if "." in v else int(v))
        elif ln.startswith("#"):
            note = ln[2:]
        else:
            body.append(ln)
    for r in csv.DictReader(body):
        rows.append(r)
    return params, note, rows


def check(path):
    params, note, rows = load(path)
    bars = [(float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])) for r in rows]
    outs, sm = ref.run(bars, params)
    fails = []
    asserted = 0
    for r, o in zip(rows, outs):
        for col, key in COLMAP.items():
            v, present = parse_value(r.get("exp_" + col, ""))
            if not present:
                continue
            asserted += 1
            got = o[key]
            if ref.na(v):
                ok = ref.na(got)
            elif ref.na(got):
                ok = False
            else:
                ok = abs(float(got) - v) <= TOL
            if not ok:
                fails.append("bar %s %s: expected %s got %s" % (r["bar"], col, "na" if ref.na(v) else v, "na" if ref.na(got) else got))
    funnel = dict(bars=len(outs), bot=sm.botCount, top=sm.topCount, up=sm.upTickN, dn=sm.dnTickN,
                  squares=len(sm.squares), labels=len(sm.labels))
    return fails, asserted, funnel, note


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, "fixtures", "*.csv")))
    total_fail = 0
    for f in files:
        fails, asserted, funnel, note = check(f)
        status = "PASS" if not fails else "FAIL"
        print("%s  %-18s asserts=%-3d bars=%d bot=%d top=%d up=%d dn=%d squares=%d labels=%d" %
              (status, os.path.basename(f), asserted, funnel["bars"], funnel["bot"], funnel["top"], funnel["up"], funnel["dn"], funnel["squares"], funnel["labels"]))
        for m in fails:
            print("      " + m)
        total_fail += len(fails)
    print("GATE A:", "PASS" if total_fail == 0 else "FAIL (%d mismatches)" % total_fail)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
