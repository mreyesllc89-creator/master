"""What the search says about each input, one value at a time.

usage: python inputs_summary.py [results_dir]

For every chart timeframe and every input: the settings of the sweep grouped by that input's
value (all other inputs random), with the share of each group that is positive in BOTH halves
of the search window after costs and before costs, the share positive over the whole window,
the median net R and the median commission paid. Only settings with at least 30 trades in
each half are counted; an input that only some settings read is shown for those only.

After-cost shares alone mislead: a wide stop or a rare trigger pays less commission in R and
looks "better" without finding better trades, which is why the before-cost share and the fees
stand beside them. A difference of a few points between groups of a few hundred settings is
noise. Writes results/inputs_<tf>m.json and results/INPUTS.md.
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


def burst_only(s):
    return bool(s["use_burst"] and not s["any_combo"])


# (name, value of a setting or None when the setting does not read that input, tf = chart minutes)
INPUTS = [
    ("Trade direction", lambda s, tf: "inverted (against the filter)" if s["inverted"] else "with the filter"),
    ("Trailing stop", lambda s, tf: "on" if s["trail"] else "off"),
    ("Trail Activation (x ATR), trailing on", lambda s, tf: s["trail_act"] if s["trail"] else None),
    ("Trail Offset (x ATR), trailing on", lambda s, tf: s["trail_off"] if s["trail"] else None),
    ("Stop Loss (x ATR)", lambda s, tf: s["sl"]),
    ("Take Profit (x ATR, 0 = off)", lambda s, tf: s["tp"]),
    ("Time stop (bars, 0 = off)", lambda s, tf: s["max_bars"]),
    ("Candles to wait after an entry", lambda s, tf: s["wait"]),
    ("Volatility-collapse exit", lambda s, tf: "on" if s["vol_exit"] else "off"),
    ("Low Vol level, volatility exit on", lambda s, tf: s["low"] if s["vol_exit"] else None),
    ("Exit ATR length", lambda s, tf: s.get("exit_atr", 14)),
    ("Filter timeframe", lambda s, tf: tfname(s["f_tf"])),
    ("Band (x ATR)", lambda s, tf: s["band"]),
    ("Level", lambda s, tf: "entry price" if s["lv_mode"] == "entry" else "signal close"),
    ("Entry distance (x ATR), level = entry price", lambda s, tf: s["entry_dist_atr"] if s["lv_mode"] == "entry" else None),
    ("Trades against the signal's side", lambda s, tf: "allowed" if s["against"] else "not allowed"),
    ("Allowed side", lambda s, tf: "both" if (s["allow_buy"] and s["allow_sell"]) else ("buy only" if s["allow_buy"] else "sell only")),
    ("Signal", lambda s, tf: "burst only" if burst_only(s) else "zones (any)"),
    ("Burst size (x ATR), burst only", lambda s, tf: s["burst_atr"] if burst_only(s) else None),
    ("Permission lasts, burst only", lambda s, tf: ("until next signal" if not s.get("perm_candles") else f"{s['perm_candles']} candles") if burst_only(s) else None),
    ("Check price on, filter above the chart", lambda s, tf: ("level at candle open" if s.get("check_open") else "tick") if s["f_tf"] > tf else None),
    ("Zone filter", lambda s, tf: "off" if not s["use_zones"] else f"on, {s['min_aligned']} aligned"),
    ("Drift filter", lambda s, tf: f"on, {s['drift_bars']} bars" if s["use_drift"] else "off"),
    ("AMVI timeframes switched on", lambda s, tf: len(s["tfs"])),
    ("Lowest AMVI timeframe", lambda s, tf: tfname(min(s["tfs"]))),
    ("Highest AMVI timeframe", lambda s, tf: tfname(max(s["tfs"]))),
    ("Timeframes that must be hot", lambda s, tf: s["conf"]),
    ("High Vol level", lambda s, tf: s["high"]),
    ("Fast ATR", lambda s, tf: s["fast"]),
    ("Slow ATR", lambda s, tf: s["slow"]),
    ("Normalisation length", lambda s, tf: s["norm"]),
    ("Weights", lambda s, tf: s.get("weights", "default")),
]


def sort_key(v):
    return (0, float(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, str(v))


def summarise(d, settings, tf):
    nm = d["gross"].shape[1]
    M = holdout.split_masks(nm)
    net = holdout.net_months(d)
    gross = d["gross"].astype(np.float64)
    h1, h2 = net[:, M["h1"]].sum(1), net[:, M["h2"]].sum(1)
    g1, g2 = gross[:, M["h1"]].sum(1), gross[:, M["h2"]].sum(1)
    fee = holdout.BASE_FEE * d["feeu"].astype(np.float64).sum(1)
    tot = h1 + h2
    cnt = d["cnt"]
    ok = (cnt[:, M["h1"]].sum(1) >= 30) & (cnt[:, M["h2"]].sum(1) >= 30)
    both = (h1 > 0) & (h2 > 0)
    gboth = (g1 > 0) & (g2 > 0)
    out = dict(rows=int(ok.sum()), share_both=float(both[ok].mean()) if ok.any() else 0.0,
               share_both_gross=float(gboth[ok].mean()) if ok.any() else 0.0, inputs=[])
    for name, fn in INPUTS:
        vals = [fn(s, tf) for s in settings]
        groups = {}
        for i, v in enumerate(vals):
            if v is None or not ok[i]:
                continue
            groups.setdefault(v, []).append(i)
        rows = []
        for v in sorted(groups, key=sort_key):
            idx = np.array(groups[v])
            rows.append(dict(value=v, rows=int(idx.size), share_both=float(both[idx].mean()), share_both_gross=float(gboth[idx].mean()),
                             share_positive=float((tot[idx] > 0).mean()), median_total=float(np.median(tot[idx])),
                             median_fee=float(np.median(fee[idx])), median_trades=float(np.median(d["n"][idx]))))
        out["inputs"].append(dict(name=name, values=rows))
    return out


def run(res_dir):
    md = ["# What the search says about each input", "",
          "Settings of the random search grouped by one input's value, all other inputs random. Only settings with at least 30 trades in",
          "each half of the search window (2023-11 to 2026-10) are counted.", "",
          "- **Both halves, after costs**: share of the group positive in both halves net of 0.05% per side, 1 tick and funding.",
          "- **Both halves, before costs**: the same before commission and funding. Read the two together: a value that only looks good",
          "  after costs (a wide stop, a high trigger level) mostly saves commission; it does not find better trades.",
          "- **Median fees**: the commission the group's typical setting paid over the three years, in R.",
          "- An input that only some settings read (the trailing pair, the burst size, ...) is shown for those settings only.",
          "- Groups of a few hundred settings differ by a few points from noise alone.", ""]
    for tf in space.CHART_TFS:
        try:
            d, settings = holdout.load(os.path.join(res_dir, "sweeps"), tf)
        except SystemExit:
            continue
        r = summarise(d, settings, tf)
        json.dump(r, open(os.path.join(res_dir, f"inputs_{tf}m.json"), "w"))
        md += [f"## Chart {make_pine.TF_NAME[tf]}", "",
               f"{r['rows']:,} settings counted; {r['share_both'] * 100:.1f}% of them positive in both halves after costs, {r['share_both_gross'] * 100:.1f}% before costs.", "",
               "| Input | Value | Settings | Both halves, after costs | Both halves, before costs | Whole window positive | Median net R | Median fees | Median trades |",
               "|---|---|---|---|---|---|---|---|---|"]
        for inp in r["inputs"]:
            for k, v in enumerate(inp["values"]):
                md.append(f"| {inp['name'] if k == 0 else ''} | {v['value']} | {v['rows']} | {v['share_both'] * 100:.1f}% | {v['share_both_gross'] * 100:.1f}% | "
                          f"{v['share_positive'] * 100:.1f}% | {v['median_total']:+.1f} | {v['median_fee']:.1f}R | {v['median_trades']:.0f} |")
        md.append("")
        print(f"chart {tf}m: {r['rows']} settings", flush=True)
    open(os.path.join(res_dir, "INPUTS.md"), "w", encoding="utf-8").write("\n".join(md))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
