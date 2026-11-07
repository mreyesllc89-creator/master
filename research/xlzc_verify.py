#!/usr/bin/env python3
"""Stress-test a chosen configuration: buffer edges, spread +25%/+50%, session shifts,
trailing variants, monthly breakdown and bootstrap PF interval.
Usage: python3 xlzc_verify.py <data_dir> <out_json>"""
import json, sys
import numpy as np
import xlzc_backtest as B
import xlzc_calibrate as C

BASE = dict(tf="M3/H1", N=40, S=2, buffer=120, NT=120, min_rr=1.5, fb=0.0, stoch="soft",
            session="ny_12-1630", trail=True)


def setup(m1, hs, pair, spread_mult=1.0):
    path = B.M1Path(m1, hs * spread_mult)
    trig, htf = pair.split("/")
    t, sig = B.build_signals(m1, trig, htf)
    mi = np.searchsorted(path.t, sig["entry_time"].values)
    et = sig["entry_time"]
    s = dict(bias=sig["bias"].values, stoch_ok=sig["stoch_ok"].values, et=et.values,
             tod=(et.dt.hour * 60 + et.dt.minute).values, mi=mi)
    sls, pools = {}, {}
    for S in C.SS:
        shf, slf = B.swing_flags(t["high"].values, t["low"].values, S)
        pools[(pair, S)] = C.low_pools(t, sig, S, slf)
        for N in C.NS:
            sls[(pair, N, S)] = C.sl_structure(t, sig, N, S, shf)
    C.G.clear()
    C.G.update(sig={pair: s}, sls=sls, pools=pools, path=path)


def summarize(trades):
    rs = np.array([r for _, r in trades])
    st = C.seg_stats(trades)
    return {k: (None if isinstance(v, float) and not np.isfinite(v) else round(float(v), 3)) for k, v in st.items()}


def main():
    m1, hs = B.load(sys.argv[1])
    out = {"base": BASE, "variants": []}

    def run(label, **chg):
        cfg = dict(BASE); cfg.update(chg)
        _, tr = C.run_cfg(cfg)
        s = summarize(tr); s["label"] = label
        out["variants"].append(s)
        print(f"{label:38s} trades {s['all_trades']:>5} PF {s['all_pf']} net {s['all_net_r']}R dd {s['all_maxdd_r']}R "
              f"| H1 {s['2025H1_pf']} H2 {s['2025H2_pf']} 26 {s['2026_pf']}", flush=True)
        return tr

    setup(m1, hs, BASE["tf"])
    base_tr = run("chosen")
    for b in (80, 160, 200):
        run(f"buffer {b}", buffer=b)
    run("trailing off", trail=False)
    run("min RR 1.0", min_rr=1.0)
    run("min RR 2.0", min_rr=2.0)
    run("stochastic hard", stoch="hard")
    run("fallback 1.5R", fb=1.5)
    for name, win in [("ny_13-17", (780, 1020)), ("ny_11-16", (660, 960)), ("ny_12-15", (720, 900))]:
        C.SESSIONS[name] = win
        run(f"session {name}", session=name)
    run("session ldn_ny_07-20", session="ldn_ny_07-20")

    # monthly + bootstrap on chosen
    months = {}
    for t, r in base_tr:
        m = str(t)[:7]; months[m] = round(months.get(m, 0) + r, 2)
    out["monthly_r"] = months
    out["trades"] = [(str(t)[:16], round(r, 3)) for t, r in base_tr]
    rs = np.array([r for _, r in base_tr]); rng = np.random.default_rng(7); pf = []
    for _ in range(10000):
        s = rng.choice(rs, len(rs)); l = -s[s < 0].sum(); pf.append(s[s > 0].sum() / l if l > 0 else np.nan)
    out["bootstrap_pf_5_95"] = [round(float(x), 2) for x in np.nanpercentile(pf, [5, 95])]
    out["p_pf_below_1"] = round(float(np.nanmean(np.array(pf) < 1)), 3)
    print("bootstrap", out["bootstrap_pf_5_95"], "P(PF<1)", out["p_pf_below_1"])

    for mult in (1.25, 1.5):
        setup(m1, hs, BASE["tf"], mult)
        run(f"spread x{mult}")
    for pair in ("M2/H1", "M3/M30"):
        BASE_tf = BASE["tf"]; setup(m1, hs, pair)
        run(f"same inputs on {pair}", tf=pair)
    json.dump(out, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
