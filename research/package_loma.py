#!/usr/bin/env python3
"""Build the two Loma zips (XAUUSD and BTCUSD) from the repository files.
Usage (repository root): python3 research/package_loma.py <version e.g. 1.34> <output_dir>"""
import os, re, shutil, sys, zipfile
import pandas as pd

VER, OUT = sys.argv[1], sys.argv[2]
TAG = VER.replace(".", "_")
EA = "XAUUSD_Loma_TrendPullback.mq5"
EVK = "EVK/MQL5/Include/EVK/EVK.mqh"
GOLD = ["Top01", "Top02", "Top03", "Top04", "Top05", "Top07"]

src = open(EA).read()
assert f'#property version     "{VER}"' in src and f"Loma TrendPullback v{VER}" in src and f"Version  : {VER}" in src, "EA version strings"


def build(name, presets, docs, extra):
    root = os.path.join(BUILD, name)                     # staging folder, removed after zipping
    shutil.rmtree(root, ignore_errors=True)
    for d in ("MQL5/Experts", "MQL5/Include/EVK", "MQL5/Presets"):
        os.makedirs(os.path.join(root, d))
    shutil.copy(EA, os.path.join(root, "MQL5/Experts", EA))
    shutil.copy(EVK, os.path.join(root, "MQL5/Include/EVK/EVK.mqh"))
    for p in presets:
        head = open(p).readline()
        assert f"v{VER}" in head, (p, head)
        shutil.copy(p, os.path.join(root, "MQL5/Presets", os.path.basename(p)))
    guide = open(docs).read()
    assert f"v{VER}" in guide.splitlines()[0], docs
    shutil.copy(docs, os.path.join(root, "START_HERE.md"))
    for dst, s in extra.items():
        if isinstance(s, pd.DataFrame):
            s.to_csv(os.path.join(root, dst), index=False)
        elif s.endswith(".html"):
            # the page was written for the artifact viewer, which supplies the document head:
            # add it so the file opens correctly from disk (UTF-8, phone width, margins)
            body = open(s, encoding="utf-8").read()
            assert "<!doctype" not in body.lower()
            with open(os.path.join(root, dst), "w", encoding="utf-8") as f:
                # no explicit </head><body>: the page's own <title>, <link> and <style> stay in the
                # head and the parser opens the body at <main>
                f.write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
                        '<style>body{margin:0}</style>\n' + body + '\n</html>\n')
        else:
            shutil.copy(s, os.path.join(root, dst))
    z = os.path.join(OUT, name + ".zip")
    if os.path.exists(z):
        os.remove(z)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for dp, _, fs in sorted(os.walk(root)):
            for fn in sorted(fs):
                full = os.path.join(dp, fn)
                f.write(full, os.path.relpath(full, BUILD))
    return z


os.makedirs(OUT, exist_ok=True)
BUILD = os.path.join(OUT, "_build")
gold_sets = sorted(p for p in (os.path.join("presets/top10", f) for f in os.listdir("presets/top10"))
                   if p.endswith(".set") and re.search(r"Loma_(Top\d\d)_", p).group(1) in GOLD)
assert len(gold_sets) == 6
s = pd.read_csv("presets/top10/TOP10_SUMMARY.csv")
s = s[s["rank"].isin([int(g[3:]) for g in GOLD])].copy()
for c in ("oos_vt_trades", "oos_dukascopy_trades"):
    s[c] = s[c].astype("Int64")                                   # whole numbers (blank rows made them float)
z1 = build(f"Loma_XAUUSD_v{TAG}", gold_sets, "packages/loma_xauusd/START_HERE.md",
           {"GOLD_PRESETS_SUMMARY.csv": s, "Loma_OOS_Review.html": "research/reports/loma_oos_review.html"})
btc_sets = sorted(os.path.join("presets/btc", f) for f in os.listdir("presets/btc") if f.endswith(".set"))
assert len(btc_sets) == 4
z2 = build(f"Loma_BTCUSD_v{TAG}", btc_sets, "packages/loma_btcusd/START_HERE.md",
           {"BTC_PRESETS_SUMMARY.csv": "presets/btc/BTC_PRESETS_SUMMARY.csv",
            "Loma_OOS_Review.html": "research/reports/loma_oos_review.html"})
shutil.rmtree(BUILD)
for z in (z1, z2):
    print(z)
    for i in zipfile.ZipFile(z).infolist():
        print(f"  {i.file_size:8d}  {i.filename}")
