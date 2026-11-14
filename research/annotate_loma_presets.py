#!/usr/bin/env python3
"""Update the comment header of the Loma presets (version, out-of-sample results) without touching any input line,
and add the out-of-sample columns to the two summary CSVs.
Gold: results/loma_report_data.json (VT Markets MT5 + Dukascopy, Jun 1 - Nov 6 2026, six tested presets).
BTC:  results/btc_oos/btc_oos_2026.json and btc_oos_2026_spread20.json (Binance, May 16 - Nov 13 2026).
Usage (repository root): python3 research/annotate_loma_presets.py 1.34"""
import glob, json, os, re, sys
import pandas as pd

VER = sys.argv[1]
R = "research/results"
gold = {p["preset"]: p for p in json.load(open(f"{R}/loma_report_data.json"))["presets"]}
b10 = json.load(open(f"{R}/btc_oos/btc_oos_2026.json")); b20 = json.load(open(f"{R}/btc_oos/btc_oos_2026_spread20.json"))


def btc(d, preset, variant):
    return next(x for x in d["presets"] if x["preset"] == preset and x["variant"] == variant)


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
               f"PF {g['oos_vt_gross_pf']:.2f} before commission ({g['oos_vt_net_pf']:.2f} after); Dukascopy prices {g['oos_duk_n']} trades, "
               f"PF {g['oos_duk_pf']:.2f}. The edge did not hold: NOT RECOMMENDED FOR LIVE TRADING.")
    else:
        oos = "; Not tested out of sample on broker data (only Top01-05 and Top07 were); the six that were all failed from June 2026."
    head.insert(i + 1, oos)
    head = [h.replace("UNPROVEN: Strategy Tester (real ticks) and demo only.", "Strategy Tester and demo only.") for h in head]
    rewrite(path, head)

for path in sorted(glob.glob("presets/btc/Loma_BTC*.set")):
    key = re.search(r"(BTC\d\d)", path).group(1)
    head = [l for l in open(path).read().splitlines() if l.startswith(";")]
    head[0] = re.sub(r"v1\.\d\d", f"v{VER}", head[0])
    head = [h for h in head if not h.startswith("; OUT OF SAMPLE")]
    i = next(k for k, h in enumerate(head) if h.startswith("; Chosen with ALL the data"))
    a, s, t = btc(b10, key, "base"), btc(b10, key, "stress"), btc(b20, key, "base")
    head[i] = "; Chosen with ALL the data from Jan 2025 to May 15 2026: the figures above are in-sample."
    head.insert(i + 1, f"; OUT OF SAMPLE May 16 - Nov 13 2026 (Binance BTCUSDT M1, never used for calibration): {a['oos_n']} trades, "
                       f"PF {a['oos_pf']:.2f} ({a['oos_netR']:+.1f}R); harsh stress PF {s['oos_pf']:.2f}; 20 USD spread PF {t['oos_pf']:.2f}. "
                       f"All four together PF {b10['all_four_base']['pf']:.2f}: no reliable edge, demo only.")
    head = [h.replace("UNPROVEN: Strategy Tester (real ticks) and demo only.", "Strategy Tester and demo only.") for h in head]
    rewrite(path, head)

# summary CSVs: add out-of-sample columns
s = pd.read_csv("presets/top10/TOP10_SUMMARY.csv")
for c in ["oos_vt_trades", "oos_vt_pf_before_comm", "oos_vt_pf_after_comm", "oos_dukascopy_trades", "oos_dukascopy_pf"]:
    s[c] = pd.NA
for k, g in gold.items():
    m = s["rank"] == int(k[3:])
    s.loc[m, ["oos_vt_trades", "oos_vt_pf_before_comm", "oos_vt_pf_after_comm", "oos_dukascopy_trades", "oos_dukascopy_pf"]] = \
        [g["oos_vt_n"], round(g["oos_vt_gross_pf"], 2), round(g["oos_vt_net_pf"], 2), g["oos_duk_n"], round(g["oos_duk_pf"], 2)]
s.to_csv("presets/top10/TOP10_SUMMARY.csv", index=False)
s = pd.read_csv("presets/btc/BTC_PRESETS_SUMMARY.csv")
for c in ["oos_trades", "oos_pf", "oos_net_r", "oos_stress_pf", "oos_pf_spread20"]:
    s[c] = pd.NA
for i, r in s.iterrows():
    key = f"BTC{int(r['rank']):02d}"; a, st, t = btc(b10, key, "base"), btc(b10, key, "stress"), btc(b20, key, "base")
    s.loc[i, ["oos_trades", "oos_pf", "oos_net_r", "oos_stress_pf", "oos_pf_spread20"]] = \
        [a["oos_n"], round(a["oos_pf"], 2), round(a["oos_netR"], 1), round(st["oos_pf"], 2), round(t["oos_pf"], 2)]
s.to_csv("presets/btc/BTC_PRESETS_SUMMARY.csv", index=False)
print("done")
