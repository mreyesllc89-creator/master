"""Private parity fixture for the MQL5 port of option 2 (NOT for the repository: it holds broker candles).
For each filter timeframe, a slice of broker candles with every feature, the standardised logit of each horizon's
model and of the H = 3 model, P0, G2P (H = 3 model) and the veto permission R2, plus aggregate per-horizon metrics of
the same slice. Usage: python veto_fixture.py <broker_csv> <veto_model_2026.json> <out_dir> [n_candles_per_tf=2000]"""
import sys, os, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
_src = open(os.path.join(HERE, "wf_g2_broker.py")).read()
_src = _src[:_src.index('if run == "check":')]
_argv = sys.argv; sys.argv = ["wf_g2_broker.py", "none", "dry"]
G = {"__file__": os.path.join(HERE, "wf_g2_broker.py"), "__name__": "g2_defs"}
exec(compile(_src, "wf_g2_broker.py", "exec"), G)
sys.argv = _argv
W = G["W"]; features, label = G["features"], G["label"]

path, mpath, out = sys.argv[1], sys.argv[2], sys.argv[3]
n_keep = int(sys.argv[4]) if len(sys.argv) > 4 else 2000
os.makedirs(out, exist_ok=True)
spec = json.load(open(mpath))
BS = W.load("server", "btc_1m_2014.parquet")
BK, BK_START = G["load_broker_warm"](path, BS)
agg = []
for tf in (5, 15, 30, 60):
    name = W.NAMES[tf]
    fe = features(BK, tf)
    good = ~np.isnan(fe["X"]).any(axis=1) & (fe["t"] >= BK_START)
    idx = np.where(good)[0][-n_keep:]
    cols = fe["cols"]
    df = pd.DataFrame(fe["X"][idx], columns=cols)
    df.insert(0, "close", fe["c"][idx])
    df.insert(0, "time_server", fe["t"][idx])
    df.insert(0, "tf", name)
    df["P0_zone"] = fe["z"][idx].astype(int)
    ms = spec["models"][name]
    for H in ("1", "3", "10"):
        m = ms[H]
        assert m["features"][1:] == cols
        s = m["w"][0] + ((fe["X"][idx] - np.array(m["mu"])) / np.array(m["sd"])) @ np.array(m["w"][1:])
        df[f"logit_H{H}"] = s
        df[f"G2P_H{H}"] = np.where(s > m["q_hi"], 1, np.where(s < m["q_lo"], -1, 0))
    df["G2P_used"] = df["G2P_H3"]                                  # the port uses the H = 3 model (R2s)
    df["veto_R2s"] = np.where((df.P0_zone != 0) & (df.G2P_used == df.P0_zone), df.P0_zone, 0)
    df["DV_baseline"] = np.where((df.P0_zone != 0) & (np.abs(df["dist"]) >= ms["3"]["k_dist"]), df.P0_zone, 0)
    df.to_csv(os.path.join(out, f"fixture_{name}.csv"), index=False, float_format="%.10g")
    # aggregate metrics on the slice, per horizon (labels must end inside the slice)
    for H in W.HS:
        ok, y, tH = label(fe, H)
        m = np.zeros(fe["N"], bool); m[idx] = True
        ev = m & ok & (tH <= fe["t"][idx[-1]])
        z = fe["z"][ev]
        r2 = np.where((fe["z"] != 0) & (df.set_index(pd.Index(idx)).reindex(np.arange(fe["N"]))["G2P_used"].to_numpy() == fe["z"]), fe["z"], 0)[ev]
        for rule, p in (("P0", z), ("R2s", r2)):
            calls = p != 0
            agg.append(dict(tf=name, H=H, rule=rule, n=int(ev.sum()), calls=int(calls.sum()), coverage=float(calls.mean()),
                            acc=float(((p > 0) & (y[ev] == 1)).sum() + ((p < 0) & (y[ev] == 0)).sum()) / max(calls.sum(), 1)))
    print(name, "rows", len(df), "first", pd.to_datetime(df.time_server.iloc[0], unit="s"), "last", pd.to_datetime(df.time_server.iloc[-1], unit="s"))
pd.DataFrame(agg).to_csv(os.path.join(out, "fixture_aggregates.csv"), index=False, float_format="%.5f")
print("done fixture")
