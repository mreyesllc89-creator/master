#!/usr/bin/env python3
"""
diff_harness.py (v0.5) - GATE C: replay the OHLC of an MQL5 dump (MQL5\\Files\\XPChart\\mapdump05_<symbol>.csv,
DumpCSV=true) through shapemap_ref.py and diff every buffer column; GATE B with --tv on a TradingView export of
XPW_ShapeMap_v0.5_export.pine; --s3 A B diffs two dumps (replay check). Pass = zero mismatches after warm-up.
Tolerance 1e-6 (relative) on floats, exact on flags/counters. Prints the gate-by-gate funnel (S2).
"""
import argparse, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapemap_ref as ref

MQL_COLS = [
    ("bot_sq", "botSq", True), ("bot_sq_top", "botSqTop", False), ("bot_sq_bot", "botSqBot", False),
    ("top_sq", "topSq", True), ("top_sq_top", "topSqTop", False), ("top_sq_bot", "topSqBot", False),
    ("bot_turn", "botTurn", True), ("bot_turn_gap", "botGap", True), ("top_turn", "topTurn", True), ("top_turn_gap", "topGap", True),
    ("bot_tick", "botTick", False), ("top_tick", "topTick", False), ("state", "isRed", True), ("posw", "posW", False),
    ("area", "area", True), ("bot_armed", "botArmed", True), ("top_armed", "topArmed", True),
    ("leg_dir", "legDir", True), ("leg_dist", "legDist", False), ("leg_bars", "legBars", True), ("leg_eff", "legEff", False),
    ("rsi", "rsi", False), ("fast", "fast", False), ("slow", "slow", False), ("atr", "atr", False),
]
TV_COLS = [
    ("r", "rsi", False), ("fast", "fast", False), ("slow", "slow", False), ("atrV", "atr", False),
    ("isRed", "isRed", True), ("posW", "posW", False), ("inLow", "inLow", True), ("inHigh", "inHigh", True),
    ("botRaw", "botRaw", True), ("botWid", "botWid", True), ("topRaw", "topRaw", True), ("topWid", "topWid", True),
    ("botOK", "botSq", True), ("topOK", "topSq", True), ("botArmed", "botArmed", True), ("topArmed", "topArmed", True),
    ("botTurn", "botTurn", True), ("topTurn", "topTurn", True), ("botTick", "botTickFlag", True), ("topTick", "topTickFlag", True),
    ("lastBotGap", "lastBotGap", True), ("lastTopGap", "lastTopGap", True), ("legPath", "legPath", False),
]
TOL = 1e-6


def parse_num(s):
    if s is None:
        return None
    s = s.strip()
    if s == "" or s.lower() in ("na", "nan", "∅"):
        return ref.NA
    return float(s)


def parse_params(items):
    p = {}
    for kv in items or []:
        k, v = kv.split("=", 1)
        p[k] = (v.lower() == "true") if v.lower() in ("true", "false") else (float(v) if "." in v else int(v))
    return p


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("no rows in " + path)
    cols = {c.lower(): c for c in rows[0].keys()}
    return rows, cols


def col(cols, *names):
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


def enrich(outs, sm_params):
    for x in outs:
        x["area"] = -1 if x["inLow"] else (1 if x["inHigh"] else 0)
        x["botTickFlag"] = 0 if ref.na(x["botTick"]) else 1
        x["topTickFlag"] = 0 if ref.na(x["topTick"]) else 1
        if "bot_tick" not in x:
            pass
    return outs


def replay(rows, cols, params):
    o, h, l, c = col(cols, "open"), col(cols, "high"), col(cols, "low"), col(cols, "close")
    if not all([o, h, l, c]):
        sys.exit("need open/high/low/close columns; have: " + ", ".join(cols.values()))
    bars = [(float(r[o]), float(r[h]), float(r[l]), float(r[c])) for r in rows]
    sm = ref.ShapeMap(params)
    outs = []
    for b in bars:
        x = sm.process(*b)
        x["lastBotGap"] = sm.lastBotGap
        x["lastTopGap"] = sm.lastTopGap
        x["legPath"] = sm.legPath
        outs.append(x)
    return enrich(outs, sm.p), sm


def first_valid(outs):
    for i, x in enumerate(outs):
        if not ref.na(x["rsi"]) and not ref.na(x["slow"]) and not ref.na(x["atr"]):
            return i
    return len(outs)


def compare(rows, cols, outs, spec, tcol, mql):
    warm = first_valid(outs)
    mism, warm_mism = [], []
    checked = 0
    for i, (r, x) in enumerate(zip(rows, outs)):
        for cname, key, exact in spec:
            cc = col(cols, cname)
            if cc is None:
                continue
            want = parse_num(r[cc])
            got = x[key]
            if mql and cname in ("bot_tick", "top_tick") and not ref.na(want) and want == 0.0 and ref.na(got):
                want = ref.NA          # MQL5 stamps 0 for "no tick", the reference stamps na
            if mql and cname == "leg_dir":
                pass
            checked += 1
            if ref.na(want) and ref.na(got):
                ok = True
            elif ref.na(want) or ref.na(got):
                ok = False
            elif exact:
                ok = abs(float(want) - float(got)) < 1e-9
            else:
                ok = abs(float(want) - float(got)) <= TOL * max(1.0, abs(float(got)))
            if not ok:
                line = "bar %d (%s) %s: file=%s ref=%s" % (i, r.get(tcol, "?") if tcol else "?", cname,
                                                          "na" if ref.na(want) else want, "na" if ref.na(got) else got)
                (mism if i >= warm else warm_mism).append(line)
    return mism, warm_mism, checked, warm


def funnel(sm, outs, rows, cols):
    from collections import Counter
    p = sm.p
    flips = sum(1 for i in range(1, len(outs)) if outs[i]["isRed"] != outs[i - 1]["isRed"])
    cb, ct = Counter(), Counter()
    b_area = b_sep = t_area = t_sep = 0
    for x in outs:
        if x["botRaw"]:
            cb[x["botWid"]] += 1
            if (not p["botNeedLow"]) or x["inLowAt"] is True:
                b_area += 1
                if x["botOK"]:
                    b_sep += 1
        if x["topRaw"]:
            ct[x["topWid"]] += 1
            if (not p["topNeedHigh"]) or x["inHighAt"] is True:
                t_area += 1
                if x["topOK"]:
                    t_sep += 1
    armed_b = sum(1 for x in outs if x["botArmed"])
    armed_t = sum(1 for x in outs if x["topArmed"])
    xu = sum(1 for x in outs if x["crossedUpAt"])
    xd = sum(1 for x in outs if x["crossedDnAt"])
    hu = sum(1 for x in outs if x["crossedUpAt"] and x["holdUp"])
    hd = sum(1 for x in outs if x["crossedDnAt"] and x["holdDn"])
    print("FUNNEL bars_processed=%d state_flips=%d" % (len(outs), flips))
    print("  BOTTOM wedges raw by width %s | area pass=%d | sep pass (=squares)=%d" % (dict(sorted(cb.items())), b_area, b_sep))
    print("  TOP    wedges raw by width %s | area pass=%d | sep pass (=squares)=%d" % (dict(sorted(ct.items())), t_area, t_sep))
    print("  TURNS  armed bars bot=%d top=%d | crossover-at bars up=%d dn=%d | with hold up=%d dn=%d | turns bot=%d top=%d" %
          (armed_b, armed_t, xu, xd, hu, hd, sm.nBotTurn, sm.nTopTurn))
    o, h, l, c = col(cols, "open"), col(cols, "high"), col(cols, "low"), col(cols, "close")
    atr = ref.Atr(p["atrLen"])
    b_rng = b_frac = b_atr = t_rng = t_frac = t_atr = 0
    for r in rows:
        oo, hh, ll, cc = float(r[o]), float(r[h]), float(r[l]), float(r[c])
        a = atr.update(hh, ll, cc)
        rng = hh - ll
        if rng > 0 and ref.gt(a, 0.0):
            b_rng += 1
            t_rng += 1
            dn = min(oo, cc) - ll
            up = hh - max(oo, cc)
            if dn / rng >= p["botWickRange"]:
                b_frac += 1
                if dn / a >= p["botWickAtr"]:
                    b_atr += 1
            if up / rng >= p["topWickRange"]:
                t_frac += 1
                if up / a >= p["topWickAtr"]:
                    t_atr += 1
    print("  BOTTOM ticks: rng>0&atr>0=%d | wick/range pass=%d | wick/ATR pass=%d | hits=%d" % (b_rng, b_frac, b_atr, sm.nBotTk))
    print("  TOP    ticks: rng>0&atr>0=%d | wick/range pass=%d | wick/ATR pass=%d | hits=%d" % (t_rng, t_frac, t_atr, sm.nTopTk))
    print("  TABLE  " + " | ".join("%s: %s" % rw for rw in sm.table()))


def s3(a, b):
    ra, ca = read_csv(a)
    rb, cb = read_csv(b)
    n = min(len(ra), len(rb))
    diffs = []
    keys = [k for k in ra[0].keys()]
    for i in range(n):
        for k in keys:
            if ra[i].get(k) != rb[i].get(k):
                diffs.append("row %d %s: A=%s B=%s" % (i, k, ra[i].get(k), rb[i].get(k)))
    if len(ra) != len(rb):
        diffs.append("row count A=%d B=%d" % (len(ra), len(rb)))
    for d in diffs[:200]:
        print(d)
    print("S3 replay diff rows:", len(diffs), "->", "PASS" if not diffs else "FAIL")
    return 0 if not diffs else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="*")
    ap.add_argument("--tv", action="store_true")
    ap.add_argument("--params", nargs="*")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--s3", nargs=2, metavar=("A", "B"))
    a = ap.parse_args()
    if a.s3:
        return s3(*a.s3)
    if not a.csv:
        ap.error("csv path required")
    rows, cols = read_csv(a.csv[0])
    outs, sm = replay(rows, cols, parse_params(a.params))
    tcol = col(cols, "time")
    spec = TV_COLS if a.tv else MQL_COLS
    present = [c for c, _, _ in spec if col(cols, c)]
    print("GATE %s: %s rows=%d compared_columns=%d (%s)" % ("B" if a.tv else "C", a.csv[0], len(rows), len(present), ", ".join(present)))
    mism, warm_mism, checked, warm = compare(rows, cols, outs, spec, tcol, not a.tv)
    print("warm-up ends at bar %d; cells checked=%d" % (warm, checked))
    for m in mism[:500]:
        print("MISMATCH " + m)
    if a.full:
        for m in warm_mism[:200]:
            print("warm-up " + m)
    funnel(sm, outs, rows, cols)
    print("GATE %s RESULT: %s (mismatches after warm-up: %d; inside warm-up: %d)" %
          ("B" if a.tv else "C", "PASS" if not mism else "FAIL", len(mism), len(warm_mism)))
    return 0 if not mism else 1


if __name__ == "__main__":
    sys.exit(main())
