#!/usr/bin/env python3
"""
Test the v1.20 options from the refined spec (Nov 2026) on the calibrated presets.

  python3 v120_options.py <data_dir> <out.json>                                  (gold)
  XLZC_SYMBOL=BTCUSD XLZC_SPREAD_PTS=500 XLZC_SPREAD_CAP=1000 \
  python3 v120_options.py <btc_data_dir> <out.json>                              (BTC)

Options (EA inputs in brackets):
  * trend condition [HTF_Condition]: MACD<0 AND close<EMA50 (default) / OR / MACD only / EMA only
  * second trend timeframe [UseHTF2, HTF2_Timeframe, HTF_Combine]: D1 or M15, both / either
  * liquidity zones [TP_Mode=TP_ZONE, Zone_Tolerance_Points, Zone_MinTouches, TP_Buffer_Points]
  * the spec's literal setup: M1 trigger with an M15 and/or D1 trend filter
Every option is chosen on 2025 only; 2026 is out of sample.
"""
import itertools
import json
import sys

import numpy as np
import pandas as pd

import fgf_backtest as FB
import xlzc_backtest as B
import xlzc_calibrate as C

PRESETS = {
    "XAUUSD": {
        "Gold M3/H1": dict(tf="M3/H1", N=40, S=2, buffer=120, NT=120, min_rr=1.5, fb=0.0, stoch="soft",
                           session="ny_12-1630", trail=True),
        "Gold M2/H1": dict(tf="M2/H1", N=15, S=4, buffer=40, NT=120, min_rr=1.5, fb=1.5, stoch="soft",
                           session="ny_12-1630", trail=True),
        "Spec M1/M15": dict(tf="M1/M15", N=25, S=2, buffer=40, NT=0, min_rr=1.0, fb=0.0, stoch="soft",
                            session="ny_12-1630", trail=True),
    },
    "BTCUSD": {
        "BTC M3/H1": dict(tf="M3/H1", N=40, S=2, buffer=40, NT=60, min_rr=2.0, fb=0.0, stoch="soft",
                          session="ny_12-1630", trail=True, trail_start=150, trail_dist=25),
        "Spec M1/M15": dict(tf="M1/M15", N=25, S=2, buffer=40, NT=0, min_rr=1.0, fb=0.0, stoch="soft",
                            session="ny_12-1630", trail=True),
    },
}


def htf_components(m1, tf):
    """Per HTF bar close time: MACD<0 and close<EMA50 (last closed bar rule)."""
    h = B.resample(m1, tf)
    m = B.macd_main(h["close"])
    e = B.ema(h["close"], 50)
    df = pd.DataFrame({"close_time": h.index + pd.Timedelta(minutes=B.TF_MIN[tf]),
                       "macd_neg": (m < 0).values, "below": (h["close"] < e).values}).iloc[60:]
    return df


def components_at(entry_times, comp):
    s = pd.DataFrame({"t": pd.to_datetime(entry_times)}).reset_index()
    j = pd.merge_asof(s.sort_values("t"), comp.sort_values("close_time"), left_on="t", right_on="close_time",
                      direction="backward").sort_values("index")
    return j["macd_neg"].fillna(False).to_numpy(bool), j["below"].fillna(False).to_numpy(bool)


def cond(mn, be, mode):
    return {"and": mn & be, "or": mn | be, "macd": mn, "ema": be}[mode]


def stats(tr):
    s = C.seg_stats(tr)
    out = {k: (None if not np.isfinite(v) else round(float(v), 4)) for k, v in s.items()}
    r = np.array([x[1] for x in tr])
    out["win"] = round(float((r > 0).mean()), 3) if len(r) else None
    h1, h2 = out["2025H1_pf"], out["2025H2_pf"]
    out["min25"] = min(h1, h2) if h1 is not None and h2 is not None else None
    return out


def main():
    data_dir, out_path = sys.argv[1], sys.argv[2]
    presets = PRESETS[B.SYMBOL]
    m1, _ = B.load(data_dir)
    comps = {tf: htf_components(m1, tf) for tf in ("M15", "M30", "H1", "D1")}
    p = FB.prepare(data_dir, sorted({c["tf"] for c in presets.values()}))
    FB.init_worker(p)
    res = {"symbol": B.SYMBOL, "presets": {}}
    for name, base in presets.items():
        pair = base["tf"]; htf1 = pair.split("/")[1]
        sig = FB.W["sig"][pair]
        et = sig["et"]
        comp1 = components_at(et, comps[htf1])
        rows = []

        def run(label, group, cfg=base, bias=None):
            orig = C.G["sig"][pair]
            if bias is not None:
                C.G["sig"][pair] = dict(orig, bias=bias)
            tr = C.run_cfg(cfg)[1]
            C.G["sig"][pair] = orig
            s = stats(tr); s.update(label=label, group=group); rows.append(s)
            return s
        base_s = run("baseline (v1.10)", "baseline")
        # --- trend condition on the preset's own filter timeframe
        for mode in ("or", "macd", "ema"):
            run(f"condition {mode}", "condition", bias=cond(*comp1, mode))
        # --- second trend timeframe
        for tf2 in ("D1", "M15"):
            if tf2 == htf1:
                continue
            comp2 = components_at(et, comps[tf2])
            for mode in ("and", "or"):
                for comb in ("both", "either"):
                    b1, b2 = cond(*comp1, mode), cond(*comp2, mode)
                    run(f"+{tf2} {comb}, condition {mode}", "second TF", bias=(b1 & b2) if comb == "both" else (b1 | b2))
        # --- liquidity zones
        for tol, mn, buf in itertools.product([50, 100, 200], [1, 2], [0, 20, 50]):
            run(f"zones tol {tol} min {mn} buf {buf}", "zones", cfg=dict(base, zone_tol=tol, zone_min=mn, tp_buf=buf))
        for buf in (20, 50):
            run(f"swing TP + buffer {buf}", "tp buffer", cfg=dict(base, tp_buf=buf))
        # --- choose per group on 2025 only (worst half-year PF, >= 20 trades per half)
        picks = {}
        for g in ("condition", "second TF", "zones", "tp buffer"):
            cand = [r for r in rows if r["group"] == g and r["min25"] is not None
                    and min(r["2025H1_trades"], r["2025H2_trades"]) >= 20]
            if cand:
                best = max(cand, key=lambda r: r["min25"])
                picks[g] = dict(label=best["label"], min25=best["min25"], pf26=best["2026_pf"], pf=best["all_pf"],
                                trades=best["all_trades"], beats_baseline_2025=best["min25"] > (base_s["min25"] or 0),
                                beats_baseline_2026=(best["2026_pf"] or 0) > (base_s["2026_pf"] or 0))
        res["presets"][name] = dict(base=base, rows=rows, picks=picks)
        print(f"\n{name}  baseline: {base_s['all_trades']:.0f} tr PF {base_s['all_pf']} | 2025 halves "
              f"{base_s['2025H1_pf']} / {base_s['2025H2_pf']} | 2026 {base_s['2026_pf']} | win {base_s['win']}")
        for g, pk in picks.items():
            print(f"  best {g:10s} on 2025: {pk['label']:32s} 2025 min {pk['min25']}  PF {pk['pf']} ({pk['trades']:.0f} tr)"
                  f"  2026 {pk['pf26']}  better than baseline: 2025 {pk['beats_baseline_2025']}, 2026 {pk['beats_baseline_2026']}")
    json.dump(res, open(out_path, "w"), indent=1, default=float)
    print("written", out_path)


if __name__ == "__main__":
    main()
