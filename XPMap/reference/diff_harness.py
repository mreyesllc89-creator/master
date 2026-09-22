#!/usr/bin/env python3
"""
diff_harness.py - GATE C (and GATE B with --tv).

GATE C: replay the OHLC columns of an MQL5 dump (MQL5\\Files\\XPChart\\mapdump_<symbol>.csv, written by
XPW_ShapeMap_v0.4.mq5 with DumpCSV=true) through shapemap_ref.py and diff every R8 buffer column.
   python3 diff_harness.py mapdump_XAUUSD-ECNc_S1.csv [--params k=v ...]
GATE B: same for a TradingView "Export chart data" CSV of XPW_ShapeMap_v0.4_export.pine (--tv).
   python3 diff_harness.py tv_export.csv --tv [--params k=v ...]

Pass = zero mismatches after warm-up. Every mismatch is listed bar by bar with both values.
Tolerances: 1e-6 on rsi/fast/slow/atr and the derived ratios; exact on flags and counters.
Warm-up = bars before rsi, slow and atr are all valid in the reference (their first-valid bars).
--full lists mismatches inside warm-up too (informational, they do not fail the gate).
--s3 A.csv B.csv : replay check, diff two MQL5 dumps row by row (S3 receipt = zero rows).
"""
import argparse, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapemap_ref as ref

# MQL5 dump column -> reference key (flag columns compared exactly, the rest with tolerance)
MQL_COLS = [
    ("bot_hit", "botHit", True), ("bot_sep", "botSep", False), ("bot_top", "botTop", False), ("bot_bot", "botBot", False),
    ("top_hit", "topHit", True), ("top_sep", "topSep", False), ("top_top", "topTop", False), ("top_bot", "topBot", False),
    ("up_tick", "upTickAtr", False), ("dn_tick", "dnTickAtr", False),
    ("eff1", "eff1", False), ("eff2", "eff2", False), ("vel1", "vel1", False), ("vel2", "vel2", False),
    ("mbars", "mBars", True), ("state", "isRedNow", True), ("runlen", "runLen", True),
    ("rsi", "rsi", False), ("fast", "fast", False), ("slow", "slow", False), ("atr", "atr", False),
]
# TradingView export column (plot title from the export .pine) -> reference key
TV_COLS = [
    ("rsiv", "rsi", False), ("fast", "fast", False), ("slow", "slow", False), ("atrv", "atr", False),
    ("isRedNow", "isRedNow", True), ("runLen", "runLen", True), ("runTop", "runTop", False), ("runBot", "runBot", False),
    ("runSep", "runSep", False), ("prevTop", "prevTop", False), ("prevBot", "prevBot", False), ("prevSep", "prevSep", False),
    ("botHit", "botHit", True), ("topHit", "topHit", True), ("upTick", "upTick", True), ("dnTick", "dnTick", True),
    ("mBars", "mBars", True), ("eff1", "eff1", False), ("eff2", "eff2", False), ("vel1", "vel1", False), ("vel2", "vel2", False),
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


def replay(rows, cols, params):
    o, h, l, c = col(cols, "open"), col(cols, "high"), col(cols, "low"), col(cols, "close")
    if not all([o, h, l, c]):
        sys.exit("need open/high/low/close columns; have: " + ", ".join(cols.values()))
    bars = [(float(r[o]), float(r[h]), float(r[l]), float(r[c])) for r in rows]
    outs, sm = ref.run(bars, params)
    return outs, sm


def first_valid(outs):
    for i, x in enumerate(outs):
        if not ref.na(x["rsi"]) and not ref.na(x["slow"]) and not ref.na(x["atr"]):
            return i
    return len(outs)


def compare(rows, cols, outs, spec, full, tcol):
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
            if want is not None and not ref.na(want) and want >= 1e300:   # EMPTY_VALUE never appears in the dump, but be safe
                want = ref.NA
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


def funnel(sm, outs):
    from collections import Counter
    flips = sum(1 for i in range(1, len(outs)) if outs[i]["isRedNow"] != outs[i - 1]["isRedNow"])
    p = sm.p
    cand_bot, area_bot, sep_bot, width_bot, ctx_bot, p2_bot = Counter(), 0, 0, 0, 0, 0
    for x in outs:
        # a candidate is a bar where wasRed and runLen == ctx (the confirmation bar of a RED prev run)
        if x["wasRed"] and x["runLen"] == p["sqBotCtx"]:
            cand_bot[x["prevLen"]] += 1
            if p["sqBotMin"] <= x["prevLen"] <= p["sqBotMax"]:
                width_bot += 1
                if x["prev2Len"] >= p["sqBotCtx"]:
                    p2_bot += 1
                    if (not p["sqBotArea"]) or x["isLow"]:
                        area_bot += 1
                        if p["sqBotSep"] == 0.0 or ref.ge(x["prevSep"], p["sqBotSep"]):
                            sep_bot += 1
    cand_top, area_top, sep_top, width_top, p2_top = Counter(), 0, 0, 0, 0
    for x in outs:
        if (not x["wasRed"]) and x["runLen"] == p["sqTopCtx"]:
            cand_top[x["prevLen"]] += 1
            if p["sqTopMin"] <= x["prevLen"] <= p["sqTopMax"]:
                width_top += 1
                if x["prev2Len"] >= p["sqTopCtx"]:
                    p2_top += 1
                    if (not p["sqTopArea"]) or x["isHigh"]:
                        area_top += 1
                        if p["sqTopSep"] == 0.0 or ref.ge(x["prevSep"], p["sqTopSep"]):
                            sep_top += 1
    print("FUNNEL bars_processed=%d state_flips=%d" % (len(outs), flips))
    print("  BOTTOM candidates by prev width: %s | width pass=%d | prev2Len pass=%d | area pass=%d | sep pass=%d | hits=%d" %
          (dict(sorted(cand_bot.items())), width_bot, p2_bot, area_bot, sep_bot, sm.botCount))
    print("  TOP    candidates by prev width: %s | width pass=%d | prev2Len pass=%d | area pass=%d | sep pass=%d | hits=%d" %
          (dict(sorted(cand_top.items())), width_top, p2_top, area_top, sep_top, sm.topCount))


def tick_funnel(rows, cols, sm):
    p = sm.p
    o, h, l, c = col(cols, "open"), col(cols, "high"), col(cols, "low"), col(cols, "close")
    up_rng = up_frac = up_atr = dn_rng = dn_frac = dn_atr = 0
    atr = ref.Atr(p["atrLen"])
    for r in rows:
        oo, hh, ll, cc = float(r[o]), float(r[h]), float(r[l]), float(r[c])
        a = atr.update(hh, ll, cc)
        rng = hh - ll
        upW = hh - max(oo, cc)
        dnW = min(oo, cc) - ll
        if rng > 0:
            up_rng += 1
            dn_rng += 1
            if upW >= p["upWickFrac"] * rng:
                up_frac += 1
                if ref.ge(upW, ref.mul(p["upWickAtr"], a)):
                    up_atr += 1
            if dnW >= p["dnWickFrac"] * rng:
                dn_frac += 1
                if ref.ge(dnW, ref.mul(p["dnWickAtr"], a)):
                    dn_atr += 1
    print("  TOP    ticks: rng>0=%d | wick/range pass=%d | wick/ATR pass=%d | hits=%d" % (up_rng, up_frac, up_atr, sm.upTickN))
    print("  BOTTOM ticks: rng>0=%d | wick/range pass=%d | wick/ATR pass=%d | hits=%d" % (dn_rng, dn_frac, dn_atr, sm.dnTickN))


def s3(a, b):
    ra, ca = read_csv(a)
    rb, cb = read_csv(b)
    n = min(len(ra), len(rb))
    diffs = []
    keys = [k for k in ra[0].keys() if k != "bar_index"]
    for i in range(n):
        for k in keys:
            if ra[i].get(k) != rb[i].get(k):
                diffs.append("row %d %s: A=%s B=%s" % (i, k, ra[i].get(k), rb[i].get(k)))
    if len(ra) != len(rb):
        diffs.append("row count A=%d B=%d (compared the first %d rows)" % (len(ra), len(rb), n))
    for d in diffs[:200]:
        print(d)
    print("S3 replay diff rows:", len(diffs), "->", "PASS" if not diffs else "FAIL")
    return 0 if not diffs else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="*")
    ap.add_argument("--tv", action="store_true", help="input is a TradingView export of the export .pine (Gate B)")
    ap.add_argument("--params", nargs="*", help="k=v overrides matching the settings used on the chart")
    ap.add_argument("--full", action="store_true", help="also list warm-up mismatches")
    ap.add_argument("--s3", nargs=2, metavar=("A", "B"), help="replay check: diff two MQL5 dumps")
    a = ap.parse_args()
    if a.s3:
        return s3(*a.s3)
    if not a.csv:
        ap.error("csv path required")
    rows, cols = read_csv(a.csv[0])
    params = parse_params(a.params)
    outs, sm = replay(rows, cols, params)
    tcol = col(cols, "time")
    spec = TV_COLS if a.tv else MQL_COLS
    present = [c for c, _, _ in spec if col(cols, c)]
    print("GATE %s: %s rows=%d compared_columns=%d (%s)" % ("B" if a.tv else "C", a.csv[0], len(rows), len(present), ", ".join(present)))
    mism, warm_mism, checked, warm = compare(rows, cols, outs, spec, a.full, tcol)
    print("warm-up ends at bar %d (first bar with rsi, slow and atr all valid); cells checked=%d" % (warm, checked))
    for m in mism[:500]:
        print("MISMATCH " + m)
    if a.full:
        for m in warm_mism[:200]:
            print("warm-up " + m)
    funnel(sm, outs)
    tick_funnel(rows, cols, sm)
    print("GATE %s RESULT: %s (mismatches after warm-up: %d; inside warm-up: %d)" %
          ("B" if a.tv else "C", "PASS" if not mism else "FAIL", len(mism), len(warm_mism)))
    return 0 if not mism else 1


if __name__ == "__main__":
    sys.exit(main())
