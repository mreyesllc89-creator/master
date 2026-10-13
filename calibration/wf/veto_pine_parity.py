"""Parity export for the Pine filter's score veto (flashgold_direction_filter.pine, group "Score veto").
For each model timeframe (M5, M15, M30, H1): the last N closed filter candles of Bitstamp BTC/USD on UTC bars as
TradingView builds them, with the score's 17 inputs in the Pine order, the frozen H = 3 score (log-odds), its answer
(1 UP / -1 DOWN / 0 undecided) and the veto's permission (the zone where the answer agrees, else 0). Plus, as an
aggregate check, the frozen 2026 model's raw accuracy and coverage on 2026 UTC candles (labels ending inside the
window), zone alone (P0) against zone + veto (R2s), at 1 / 3 / 10 candles. No fitting, no selection.
Usage: python veto_pine_parity.py <veto_model_2026.json> <out_dir> [n=3000] [start=2026-01-01] [end=2026-10-11]
(run from the data directory: Bitstamp 1-minute candles from 2014 in btc_1m_2014.parquet)"""
import sys, os, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
# the frozen G2 definitions (features, labels) of wf_g2_broker.py, without its main part
_src = open(os.path.join(HERE, "wf_g2_broker.py")).read()
_src = _src[:_src.index('if run == "check":')]
_argv = sys.argv; sys.argv = ["wf_g2_broker.py", "none", "dry"]
G = {"__file__": os.path.join(HERE, "wf_g2_broker.py"), "__name__": "g2_defs"}
exec(compile(_src, "wf_g2_broker.py", "exec"), G)
sys.argv = _argv
W = G["W"]; features, label = G["features"], G["label"]

mpath, out = sys.argv[1], sys.argv[2]
n_keep = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
a = sys.argv[4] if len(sys.argv) > 4 else "2026-01-01"
b = sys.argv[5] if len(sys.argv) > 5 else "2026-10-11"
os.makedirs(out, exist_ok=True)
spec = json.load(open(mpath))
PINE = ["zone", "dist", "side", "r1", "r5", "r20", "vol", "age", "zone_vol", "dist_vol", "fdir",
        "f_level_tf", "f_slope_tf", "f_level_2tf", "f_slope_2tf", "f_level_4tf", "f_slope_4tf"]
S = W.load("utc", "btc_1m_2014.parquet")
ta, tb = int(pd.Timestamp(a, tz="UTC").timestamp()), int(pd.Timestamp(b, tz="UTC").timestamp())
agg = []
for tf in (5, 15, 30, 60):
    name = W.NAMES[tf]
    fe = features(S, tf)
    m = spec["models"][name]["3"]
    assert m["features"][1:] == fe["cols"] and len(fe["cols"]) == 17
    X = fe["X"]
    good = ~np.isnan(X).any(axis=1)
    s = np.full(fe["N"], np.nan)
    s[good] = m["w"][0] + ((X[good] - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"][1:])
    ans = np.where(good, np.where(s > m["q_hi"], 1, np.where(s < m["q_lo"], -1, 0)), 0)
    z = fe["z"].astype(int)
    veto = np.where((z != 0) & (ans == z), z, 0)
    idx = np.arange(fe["N"])[-n_keep:]
    df = pd.DataFrame(X[idx], columns=PINE)
    df.insert(0, "close", fe["c"][idx])
    df.insert(0, "time_open_utc", pd.to_datetime(fe["t"][idx], unit="s", utc=True).strftime("%Y-%m-%d %H:%M"))
    df.insert(0, "time_open", fe["t"][idx])
    df.insert(0, "tf", name)
    df["inputs_ready"] = good[idx].astype(int)
    df["score"] = s[idx]
    df["answer"] = ans[idx]
    df["zone_P0"] = z[idx]
    df["veto_permission"] = veto[idx]
    df.to_csv(os.path.join(out, f"parity_{name}.csv"), index=False, float_format="%.10g")
    # aggregate: the frozen model on 2026 UTC candles, labels ending inside [a, b)
    for H in W.HS:
        ok, y, tH = label(fe, H)
        ev = ok & good & (fe["t"] >= ta) & (tH < tb)
        for rule, p in (("P0", z[ev]), ("R2s", veto[ev])):
            calls = p != 0
            yy = y[ev]
            agg.append(dict(tf=name, window=f"{a}..{b} UTC", H=H, rule=rule, n=int(ev.sum()), calls=int(calls.sum()),
                            coverage=float(calls.mean()),
                            acc=float(((p > 0) & (yy == 1)).sum() + ((p < 0) & (yy == 0)).sum()) / max(calls.sum(), 1)))
    print(name, "rows", len(df), df.time_open_utc.iloc[0], "..", df.time_open_utc.iloc[-1], "ready", int(good[idx].sum()), flush=True)
A = pd.DataFrame(agg)
A.to_csv(os.path.join(out, "aggregates_2026_utc.csv"), index=False, float_format="%.5f")
print(A.to_string())
print("done parity")
