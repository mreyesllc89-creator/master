#!/usr/bin/env python3
"""Mechanical checks of the two Loma zips against the repository. Stops with a message on the first set of problems.
Usage (repository root): python3 research/check_package.py <version e.g. 1.34> <dist_dir>"""
import hashlib, io, os, re, sys, zipfile
import pandas as pd

VER, DIST = sys.argv[1], sys.argv[2]
TAG = VER.replace(".", "_")
EA = "XAUUSD_Loma_TrendPullback.mq5"
problems = []


def need(cond, msg):
    if not cond:
        problems.append(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


ea_src = open(EA, "rb").read()
inputs = re.findall(r"^input\s+\w+\s+(\w+)\s*=", ea_src.decode("utf-8"), re.M)
need(len(inputs) == len(set(inputs)) and len(inputs) >= 50, f"EA inputs: {len(inputs)} found, {len(set(inputs))} distinct")

def count_sets(*folders):
    return sum(len([f for f in os.listdir(d) if f.endswith(".set")]) for d in folders if os.path.isdir(d))


for sym, n_sets, guide, name_pat, other in (
        ("XAUUSD", 6 + count_sets("presets/trailing15/gold"), "packages/loma_xauusd/START_HERE.md", r"Loma_(Top\d\d_Gold_|T15_Gold_)", "BTC"),
        ("BTCUSD", count_sets("presets/btc", "presets/btc_wf", "presets/trailing15/btc"), "packages/loma_btcusd/START_HERE.md",
         r"Loma_(BTC_M5_R\d\d_|WF_BTC_M30_|T15_BTC_)", "Gold")):
    zname = os.path.join(DIST, f"Loma_{sym}_v{TAG}.zip")
    z = zipfile.ZipFile(zname)
    names = z.namelist(); root = f"Loma_{sym}_v{TAG}/"
    need(all(n.startswith(root) for n in names), f"{zname}: entries outside {root}")
    rel = {n[len(root):]: n for n in names}
    need(sha(z.read(rel.get("MQL5/Experts/" + EA, names[0]))) == sha(ea_src), f"{zname}: EA differs from the repository file")
    need(sha(z.read(rel["MQL5/Include/EVK/EVK.mqh"])) == sha(open("EVK/MQL5/Include/EVK/EVK.mqh", "rb").read()), f"{zname}: EVK.mqh differs")
    sets = sorted(n for n in rel if n.startswith("MQL5/Presets/") and n.endswith(".set"))
    need(len(sets) == n_sets, f"{zname}: {len(sets)} presets, expected {n_sets}")
    magics = []
    for s in sets:
        base = os.path.basename(s)
        need(re.match(name_pat, base) is not None, f"{zname}: unexpected preset name {base}")
        text = z.read(rel[s]).decode("utf-8")
        need(text.isascii(), f"{base}: non-ASCII characters (MT5 reads presets as ANSI)")
        head = [x for x in text.splitlines() if x.startswith(";")]
        keys = [x.split("=", 1)[0] for x in text.splitlines() if x and not x.startswith(";")]
        need(keys == inputs, f"{base}: inputs differ from the EA's ({len(keys)} against {len(inputs)})")
        need(f"v{VER}" in head[0], f"{base}: header does not name v{VER}")
        need(f"DO NOT LOAD ON {other.upper()}" in head[0].upper() or sym == "XAUUSD", f"{base}: no warning against loading on {other}")
        need("WITHDRAWN" not in text.upper(), f"{base}: a withdrawn preset is in the zip")
        vals = dict(x.split("=", 1) for x in text.splitlines() if x and not x.startswith(";"))
        magics.append(vals["MagicNumber"])
        if sym == "BTCUSD":
            need(vals["CloseBeforeWeekend"] == "false" and int(vals["MaxSpread_Points"]) >= 1000, f"{base}: BTC settings (weekend close, spread limit)")
            if base.startswith("Loma_WF_"):
                need(vals["UseStochTurnFilter"] == "true" and vals["ScaleWithPrice"] == "true" and float(vals["ReferencePrice"]) > 0
                     and vals["TriggerTimeframe"] == "30", f"{base}: year-by-year preset settings (M30, turn filter, price scaling)")
        else:
            need(vals["CloseBeforeWeekend"] == "true" and int(vals["MaxSpread_Points"]) <= 200, f"{base}: gold settings (weekend close, spread limit)")
    need(len(set(magics)) == len(magics), f"{zname}: magic numbers repeat")
    g = z.read(rel["START_HERE.md"]).decode("utf-8")
    need(g == open(guide, encoding="utf-8").read(), f"{zname}: START_HERE.md differs from {guide}")
    need("<!--" not in g and "being recomputed" not in g and "TODO" not in g, f"{guide}: a placeholder is left")
    for fn in re.findall(r"`((?:MQL5/|[A-Z][A-Za-z_]+\.(?:csv|html))[^`…*]*)`", g):          # files the guide's table names
        if fn.endswith((".mq5", ".mqh", ".csv", ".html")):
            need(fn in rel, f"{guide}: names {fn}, which is not in the zip")
    page = z.read(rel["Loma_OOS_Review.html"]).decode("utf-8")
    need(page.lower().startswith("<!doctype html>") and '<meta charset="utf-8">' in page, f"{zname}: report without doctype or charset")
    body = open("research/reports/loma_oos_review.html", encoding="utf-8").read()
    need(body in page, f"{zname}: the report differs from research/reports/loma_oos_review.html")
    need("being recomputed" not in page and "recal-tiles:start -->\n<!-- recal-tiles:end" not in page, f"{zname}: the report has an unfilled part")
    csvs = [n for n in rel if n.endswith(".csv")]
    stems = {os.path.basename(s)[:-4] for s in sets}
    listed = []
    for c in csvs:
        table = pd.read_csv(io.BytesIO(z.read(rel[c])))
        files = list(table["file"].astype(str).str.replace(".set", "", regex=False))
        need(set(files) <= stems, f"{zname}: {c} names presets that are not in the zip: {sorted(set(files) - stems)[:3]}")
        listed += files
    need(sorted(listed) == sorted(stems), f"{zname}: the csv files do not list every preset exactly once")
    extra = set(rel) - set(sets) - set(csvs) - {"START_HERE.md", "Loma_OOS_Review.html", "MQL5/Experts/" + EA, "MQL5/Include/EVK/EVK.mqh"}
    need(not extra, f"{zname}: unexpected files {sorted(extra)}")
    print(f"{zname}: {len(names)} files, {len(sets)} presets, guide and report as in the repository")

if problems:
    print("\n".join("PROBLEM: " + p for p in problems))
    sys.exit(1)
print("package check passed")
