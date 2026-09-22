#!/usr/bin/env python3
"""run_fixtures.py (v0.5) - GATE A: replay fixtures/*.csv through shapemap_ref.py and compare the hand-derived
exp_* columns (blank = not asserted, "na" = must be na, tolerance 1e-5)."""
import csv, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapemap_ref as ref

TOL = 1e-5
COLMAP = {"rsi": "rsi", "slow": "slow", "atr": "atr", "state": "isRed", "posW": "posW", "inLow": "inLow", "inHigh": "inHigh",
          "botRaw": "botRaw", "botWid": "botWid", "topRaw": "topRaw", "topWid": "topWid",
          "botSq": "botSq", "botSqTop": "botSqTop", "botSqBot": "botSqBot", "topSq": "topSq", "topSqTop": "topSqTop", "topSqBot": "topSqBot",
          "botArmed": "botArmed", "topArmed": "topArmed", "botTurn": "botTurn", "botGap": "botGap", "topTurn": "topTurn", "topGap": "topGap",
          "botTick": "botTick", "topTick": "topTick", "legDir": "legDir", "legDist": "legDist", "legBars": "legBars", "legEff": "legEff"}
STRMAP = {"leg1": "leg1", "leg2": "leg2"}


def parse_value(v):
    v = v.strip()
    if v == "":
        return None, False
    if v.lower() == "na":
        return ref.NA, True
    return float(v), True


def load(path):
    params, note, body = {}, "", []
    with open(path, encoding="utf-8") as fh:
        for ln in fh.read().splitlines():
            if ln.startswith("# params:"):
                for kv in ln[len("# params:"):].split():
                    k, v = kv.split("=")
                    params[k] = (v == "True") if v in ("True", "False") else (float(v) if "." in v else int(v))
            elif ln.startswith("#"):
                note = ln[2:]
            else:
                body.append(ln)
    return params, note, list(csv.DictReader(body))


def check(path):
    params, note, rows = load(path)
    bars = [(float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])) for r in rows]
    outs, sm = ref.run(bars, params)
    fails, asserted = [], 0
    for r, o in zip(rows, outs):
        for c, key in COLMAP.items():
            v, present = parse_value(r.get("exp_" + c, ""))
            if not present:
                continue
            asserted += 1
            got = o[key]
            ok = (ref.na(got)) if ref.na(v) else ((not ref.na(got)) and abs(float(got) - v) <= TOL)
            if not ok:
                fails.append("bar %s %s: expected %s got %s" % (r["bar"], c, "na" if ref.na(v) else v, "na" if ref.na(got) else got))
        for c, key in STRMAP.items():
            v = r.get("exp_" + c, "")
            if v == "":
                continue
            asserted += 1
            if o[key] != v:
                fails.append("bar %s %s: expected %r got %r" % (r["bar"], c, v, o[key]))
    return fails, asserted, sm


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    total = 0
    for f in sorted(glob.glob(os.path.join(here, "fixtures", "*.csv"))):
        fails, asserted, sm = check(f)
        print("%s  %-22s asserts=%-3d sq=%d/%d turns=%d/%d ticks=%d/%d" % ("PASS" if not fails else "FAIL", os.path.basename(f), asserted,
              sm.nBotSq, sm.nTopSq, sm.nBotTurn, sm.nTopTurn, sm.nBotTk, sm.nTopTk))
        for m in fails:
            print("      " + m)
        total += len(fails)
    print("GATE A:", "PASS" if total == 0 else "FAIL (%d mismatches)" % total)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
