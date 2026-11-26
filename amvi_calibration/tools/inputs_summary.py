"""What the search says about each input, one value at a time.

usage: python inputs_summary.py [results_dir]

For every chart timeframe and every input: the settings of the sweep grouped by that input's
value (all other inputs random), with the share of each group that is positive after costs in
BOTH halves of the search window, the share positive over the whole window, and the median
net R. Only settings with at least 30 trades in each half are counted.

A value that helps shows up as a larger share; a difference of a few points between groups of
a few hundred settings is noise. Writes results/inputs_<tf>m.json and results/INPUTS.md.
"""
import json
import os
import sys

import numpy as np

import holdout
import make_pine
import space


def tfname(m):
    return make_pine.TF_NAME.get(int(m), f"{int(m)}m") if int(m) != 1440 else "1D"


INPUTS = [
    ("Trade direction", lambda s: "inverted (against the filter)" if s["inverted"] else "with the filter"),
    ("Trailing stop", lambda s: "on" if s["trail"] else "off"),
    ("Trail Activation (x ATR), trailing on", lambda s: s["trail_act"] if s["trail"] else None),
    ("Trail Offset (x ATR), trailing on", lambda s: s["trail_off"] if s["trail"] else None),
    ("Stop Loss (x ATR)", lambda s: s["sl"]),
    ("Take Profit (x ATR, 0 = off)", lambda s: s["tp"]),
    ("Time stop (bars, 0 = off)", lambda s: s["max_bars"]),
    ("Candles to wait after an entry", lambda s: s["wait"]),
    ("Volatility-collapse exit", lambda s: "on" if s["vol_exit"] else "off"),
    ("Exit ATR length", lambda s: s.get("exit_atr", 14)),
    ("Filter timeframe", lambda s: tfname(s["f_tf"])),
    ("Band (x ATR)", lambda s: s["band"]),
    ("Level", lambda s: "entry price" if s["lv_mode"] == "entry" else "signal close"),
    ("Trades against the signal's side", lambda s: "allowed" if s["against"] else "not allowed"),
    ("Allowed side", lambda s: "both" if (s["allow_buy"] and s["allow_sell"]) else ("buy only" if s["allow_buy"] else "sell only")),
    ("Signal", lambda s: "burst only" if (s["use_burst"] and not s["any_combo"]) else "zones (any)"),
    ("Permission lasts", lambda s: "until next signal" if not s.get("perm_candles") else f"{s['perm_candles']} candles"),
    ("Check price on", lambda s: "level at candle open" if s.get("check_open") else "tick / automatic"),
    ("Zone filter", lambda s: "off" if not s["use_zones"] else f"on, {s['min_aligned']} aligned"),
    ("Drift filter", lambda s: f"on, {s['drift_bars']} bars" if s["use_drift"] else "off"),
    ("AMVI timeframes switched on", lambda s: len(s["tfs"])),
    ("Lowest AMVI timeframe", lambda s: tfname(min(s["tfs"]))),
    ("Highest AMVI timeframe", lambda s: tfname(max(s["tfs"]))),
    ("Timeframes that must be hot", lambda s: s["conf"]),
    ("High Vol level", lambda s: s["high"]),
    ("Fast ATR", lambda s: s["fast"]),
    ("Slow ATR", lambda s: s["slow"]),
    ("Normalisation length", lambda s: s["norm"]),
    ("Weights", lambda s: s.get("weights", "default")),
]


def sort_key(v):
    return (0, float(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, str(v))


def summarise(d, settings):
    nm = d["gross"].shape[1]
    M = holdout.split_masks(nm)
    net = holdout.net_months(d)
    h1, h2 = net[:, M["h1"]].sum(1), net[:, M["h2"]].sum(1)
    tot = h1 + h2
    cnt = d["cnt"]
    ok = (cnt[:, M["h1"]].sum(1) >= 30) & (cnt[:, M["h2"]].sum(1) >= 30)
    both = (h1 > 0) & (h2 > 0)
    out = dict(rows=int(ok.sum()), share_both=float(both[ok].mean()) if ok.any() else 0.0, inputs=[])
    for name, fn in INPUTS:
        vals = [fn(s) for s in settings]
        groups = {}
        for i, v in enumerate(vals):
            if v is None or not ok[i]:
                continue
            groups.setdefault(v, []).append(i)
        rows = []
        for v in sorted(groups, key=sort_key):
            idx = np.array(groups[v])
            rows.append(dict(value=v, rows=int(idx.size), share_both=float(both[idx].mean()), share_positive=float((tot[idx] > 0).mean()),
                             median_total=float(np.median(tot[idx])), median_trades=float(np.median(d["n"][idx]))))
        out["inputs"].append(dict(name=name, values=rows))
    return out


def run(res_dir):
    md = ["# What the search says about each input", "",
          "Settings of the random search grouped by one input's value, all other inputs random. \"Both halves\" = share of the group",
          "that is positive after 0.05% per side, 1 tick and funding in both halves of the search window (2023-11 to 2026-10).",
          "Only settings with at least 30 trades in each half are counted. Groups of a few hundred settings differ by a few points",
          "from noise alone.", ""]
    for tf in space.CHART_TFS:
        try:
            d, settings = holdout.load(os.path.join(res_dir, "sweeps"), tf)
        except SystemExit:
            continue
        r = summarise(d, settings)
        json.dump(r, open(os.path.join(res_dir, f"inputs_{tf}m.json"), "w"))
        md += [f"## Chart {make_pine.TF_NAME[tf]}", "", f"{r['rows']} settings counted; {r['share_both'] * 100:.1f}% of them positive in both halves.", "",
               "| Input | Value | Settings | Both halves positive | Whole window positive | Median net R | Median trades |", "|---|---|---|---|---|---|---|"]
        for inp in r["inputs"]:
            for k, v in enumerate(inp["values"]):
                md.append(f"| {inp['name'] if k == 0 else ''} | {v['value']} | {v['rows']} | {v['share_both'] * 100:.1f}% | {v['share_positive'] * 100:.1f}% | "
                          f"{v['median_total']:+.1f} | {v['median_trades']:.0f} |")
        md.append("")
        print(f"chart {tf}m: {r['rows']} settings", flush=True)
    open(os.path.join(res_dir, "INPUTS.md"), "w", encoding="utf-8").write("\n".join(md))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
