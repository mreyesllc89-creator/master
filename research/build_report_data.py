#!/usr/bin/env python3
"""Assemble research/results/report_data.json for report_template.html.
Usage (repo root): python3 research/build_report_data.py <data_dir>"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import fgf_backtest as FB   # noqa: E402
import xlzc_calibrate as C  # noqa: E402

R = "research/results/"


def curve(trades):
    eq = np.cumsum([r for _, r in trades])
    return [[str(t)[:10], round(float(e), 2)] for (t, _), e in zip(trades, eq)]


def main():
    data_dir = sys.argv[1]
    out = {}
    v = json.load(open(R + "m3_h1_verify.json"))
    out["stress"] = v["variants"]; out["monthly"] = v["monthly_r"]; out["worst_pf"] = v.get("worst_pf")
    out["boot"] = v["bootstrap_pf_5_95"]
    out["wf"] = json.load(open(R + "walkforward.json"))
    out["m2"] = json.load(open(R + "m2_h1_verify.json"))
    # equity curves: chosen setup with and without FlashGold defaults
    p = FB.prepare(data_dir, ["M3/H1"]); FB.init_worker(p)
    off = FB.run_with_mask(FB.CHOSEN, None)
    cfg = FB.cfg_from_label(FB.DEFAULT_LABEL)
    on = FB.run_with_mask(FB.CHOSEN, FB.fgf_mask(cfg, "M3/H1", {}))
    out["curves"] = [{"name": "Without filter", "pts": curve(off), "s": C.seg_stats(off)},
                     {"name": "With FlashGold defaults", "pts": curve(on), "s": C.seg_stats(on)}]
    # stage 1 baselines and default row; input effects on M3/H1
    s1 = pd.read_csv(R + "fgf_stage1_grid.csv.gz")
    base = pd.read_csv(R + "fgf_stage1_baselines.csv")
    d = s1.copy()
    for k, val in FB.DEFAULT_LABEL.items():
        d = d[d[k] == val]
    out["s1_default"] = d[["base", "all_trades", "all_pf", "all_net_r", "2025H1_pf", "2025H2_pf", "2026_pf"]].to_dict("records")
    out["s1_base"] = base[["base", "all_trades", "all_pf", "all_net_r", "2025H1_pf", "2025H2_pf", "2026_pf"]].to_dict("records")
    m = s1[s1.base == "M3/H1 chosen"]
    eff = []
    for col in ["window", "band_atr", "filter_tf", "zones", "against", "check", "level_mode", "hold_bars"]:
        for val, g in m.groupby(col):
            g20 = g[g.all_trades >= 20]
            eff.append(dict(input=col, value=str(val), share_ge20=float((g.all_trades >= 20).mean()),
                            med_trades=float(g.all_trades.median()),
                            pf_med=float(g20.all_pf.median()) if len(g20) else None))
    out["effects"] = eff
    s1["min25"] = s1[["2025H1_pf", "2025H2_pf"]].min(axis=1)
    wf = []
    for b, g in s1.groupby("base"):
        pool = g[(g["2025H1_trades"] >= 8) & (g["2025H2_trades"] >= 8)].sort_values("min25", ascending=False)
        bl = base.set_index("base").loc[b]
        for k in (1, 10, 50):
            t = pool.head(k)
            wf.append(dict(base=b, k=k, pf25=float(t.min25.median()), pf26=float(t["2026_pf"].median()),
                           base26=float(bl["2026_pf"]), beat=float((t["2026_pf"] > bl["2026_pf"]).mean())))
    out["fgf_wf"] = wf
    # stage 2 paired comparison
    s2 = pd.read_csv(R + "fgf_stage2_cross.csv.gz")
    keys = ["tf", "N", "S", "buffer", "NT", "min_rr", "session", "trail"]
    offd = s2[s2.fgf_id == "off"].set_index(keys)
    var = []
    for fid, g in s2[s2.fgf_id != "off"].groupby("fgf_id"):
        j = g.set_index(keys).join(offd, rsuffix="_off")
        ok = j[(j.all_trades_off >= 30) & (j.all_trades >= 15)]
        var.append(dict(id=fid, n=int(len(ok)), kept=float((j.all_trades / j.all_trades_off.replace(0, np.nan)).median()),
                        pf_off=float(ok.all_pf_off.median()), pf_on=float(ok.all_pf.median()),
                        pf_up=float((ok.all_pf > ok.all_pf_off).mean()),
                        net_up=float((ok.all_net_r > ok.all_net_r_off).mean())))
    out["s2_variants"] = sorted(var, key=lambda r: -r["pf_up"])
    j = s2[s2.fgf_id == "default"].set_index(keys).join(offd, rsuffix="_off")
    ok = j[(j.all_trades_off >= 30) & (j.all_trades >= 15)]
    pairs = []
    for tf, g in ok.groupby(level="tf"):
        pairs.append(dict(tf=tf, n=int(len(g)), pf_off=float(g.all_pf_off.median()), pf_on=float(g.all_pf.median()),
                          pf_up=float((g.all_pf > g.all_pf_off).mean()), net_off=float(g.all_net_r_off.median()),
                          net_on=float(g.all_net_r.median())))
    out["s2_pairs"] = pairs
    out["s2_labels"] = json.load(open(R + "fgf_stage2_select.json"))
    out["review"] = json.load(open(R + "review_status.json"))
    s = json.dumps(out, default=float).replace("NaN", "null").replace("Infinity", "null")
    json.loads(s)
    open(R + "report_data.json", "w").write(s)
    print("written", len(s))


if __name__ == "__main__":
    main()
