#!/usr/bin/env python3
"""Update the comment header of the Loma presets (version, out-of-sample results) without touching any input line,
and add the out-of-sample columns to the two summary CSVs.
Gold: results/loma_report_data.json (VT Markets MT5 + Dukascopy, Jun 1 - Nov 6 2026, six tested presets).
BTC:  nothing to do here. The BTC presets in presets/btc are written complete by make_recal_presets.py; the four
      earlier ones (presets/btc_withdrawn) were calibrated on a wrong clock and are withdrawn.
Usage (repository root): python3 research/annotate_loma_presets.py 1.34"""
import glob, json, os, re, sys
import pandas as pd

VER = sys.argv[1]
R = "research/results"
gold = {p["preset"]: p for p in json.load(open(f"{R}/loma_report_data.json"))["presets"]}

def rewrite(path, new_head):
    lines = open(path).read().splitlines()
    body = [l for l in lines if not l.startswith(";")]
    old_body = list(body)
    open(path, "w").write("\n".join(new_head + body) + "\n")
    assert [l for l in open(path).read().splitlines() if not l.startswith(";")] == old_body


for path in sorted(glob.glob("presets/top10/Loma_Top*.set")):
    rank = re.search(r"Top(\d\d)", path).group(1); key = f"Top{rank}"
    head = [l for l in open(path).read().splitlines() if l.startswith(";")]
    head[0] = re.sub(r"v1\.\d\d", f"v{VER}", head[0])
    head = [h for h in head if not h.startswith("; OUT OF SAMPLE") and not h.startswith("; Not tested out of sample")]
    i = next(k for k, h in enumerate(head) if h.startswith("; Chosen with ALL the data"))
    head[i] = "; Chosen with ALL the data from Jan 2025 to May 15 2026: the figures above are in-sample."
    if key in gold:
        g = gold[key]
        oos = (f"; OUT OF SAMPLE Jun 1 - Nov 6 2026 (never used for calibration): VT Markets MT5 real ticks {g['oos_vt_n']} trades, "
               f"PF {g['oos_vt_gross_pf']:.2f} before commission, {g['oos_vt_pf_real_comm']:.2f} at VT's 0.60 USD per lot; "
               f"Dukascopy prices {g['oos_duk_n']} trades, PF {g['oos_duk_pf']:.2f}. The edge did not hold: NOT RECOMMENDED FOR LIVE TRADING.")
    else:
        oos = "; Not tested out of sample on broker data (only Top01-05 and Top07 were); the six that were all failed from June 2026."
    head.insert(i + 1, oos)
    head = [h.replace("UNPROVEN: Strategy Tester (real ticks) and demo only.", "Strategy Tester and demo only.") for h in head]
    rewrite(path, head)

# the five original presets (repository only): no promise of live results, and no claim of an out-of-sample 2026
for path in sorted(glob.glob("presets/Loma_Gold_*.set")):
    head = [l for l in open(path).read().splitlines() if l.startswith(";")]
    head[0] = re.sub(r"v1\.\d\d", f"v{VER}", head[0])
    head = [h.replace("2026 (out of sample) PF", "2026 PF")
             .replace("were added after seeing all the data: expect roughly PF 1.1-1.5 live. Stress verdicts are in LOMA_START_HERE.md.",
                      "were added after seeing all the data. Not tested on data after May 2026; the six top-10 presets that were tested "
                      "all lost from June 2026: NOT RECOMMENDED FOR LIVE TRADING.") for h in head]
    rewrite(path, head)

# summary CSVs: add out-of-sample columns
s = pd.read_csv("presets/top10/TOP10_SUMMARY.csv")
OOS_COLS = ["oos_vt_trades", "oos_vt_pf_before_comm", "oos_vt_pf_comm_0_60_per_lot", "oos_vt_pf_comm_6_per_lot_tester",
            "oos_dukascopy_trades", "oos_dukascopy_pf"]
s = s[[c for c in s.columns if not c.startswith("oos_")]]
for c in OOS_COLS:
    s[c] = pd.NA
for k, g in gold.items():
    m = s["rank"] == int(k[3:])
    s.loc[m, OOS_COLS] = [g["oos_vt_n"], round(g["oos_vt_gross_pf"], 2), round(g["oos_vt_pf_real_comm"], 2),
                          round(g["oos_vt_net_pf"], 2), g["oos_duk_n"], round(g["oos_duk_pf"], 2)]
for c in ("oos_vt_trades", "oos_dukascopy_trades"):
    s[c] = pd.to_numeric(s[c]).astype("Int64")                      # whole numbers, blank where not tested
s.to_csv("presets/top10/TOP10_SUMMARY.csv", index=False)
print("done")
