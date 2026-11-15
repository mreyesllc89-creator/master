"""One calibration per trend timeframe (MainTimeframe = MicroTimeframe fixed), 20 MT5 timeframes.
Same protocol as sweep.py / refine.py: random search and hill climbing on the in-sample years,
pick by out-of-sample score, July-August 2026 untouched. usage: python tfsweep.py SYMBOL N TEMPLATE.set"""
import json, sys
from multiprocessing import Pool
import numpy as np, pandas as pd
import common as C, space as S, score as SC, setfile

sym, N, template = sys.argv[1], int(sys.argv[2]), sys.argv[3]
TFS = [("M1", 1), ("M2", 2), ("M3", 3), ("M4", 4), ("M5", 5), ("M6", 6), ("M10", 10), ("M12", 12), ("M15", 15),
       ("M20", 20), ("M30", 30), ("H1", 60), ("H2", 120), ("H3", 180), ("H4", 240), ("H6", 360), ("H8", 480),
       ("H12", 720), ("D1", 1440), ("W1", 10080)]
IS, OOS, Y26 = (SC.SPLIT[sym][k] for k in ("IS", "OOS", "Y26"))


def fix(g, tf):
    g = dict(g); g["MainTimeframe"] = tf
    if tf >= 720:                                    # few bars: keep the EMAs short
        g["MainFastEMA"] = max(3, int(round(g["MainFastEMA"] / 3)))
        g["SlowRatio"] = min(g["SlowRatio"], 4.0)
    return g


def ev_is(g):
    r = SC.evaluate(g, sym, IS); r["gene"] = json.dumps(g); return r


def ev_all(g):
    out = {"gene": json.dumps(g)}
    for name, yrs in (("is", IS), ("oos", OOS), ("y26", Y26)):
        for k, v in SC.evaluate(g, sym, yrs).items():
            out[f"{name}_{k}"] = v
    p = SC.to_symbol(S.to_params(g, C.SHIPPED), sym)
    fin = [C.backtest(p, sym, y)["final"] for y in OOS]
    out["oos_interp_median_final"] = float(np.median(fin))
    return out


if __name__ == "__main__":
    rows = []
    with Pool(4) as pool:
        for name, tf in TFS:
            rng = np.random.default_rng(1000 + tf)
            genes = [fix(S.draw(rng), tf) for _ in range(N)]
            s1 = pd.DataFrame(pool.map(ev_is, genes, chunksize=8))
            s1 = s1[s1.baskets >= 8 * s1.runs].sort_values("score", ascending=False)
            if len(s1) == 0:
                rows.append(dict(timeframe=name, note="no setting traded enough")); print(name, "none", flush=True); continue
            full = pd.DataFrame(pool.map(ev_all, [json.loads(x) for x in s1.head(24).gene]))
            seeds = full[full.oos_growth > 0].head(4)
            if len(seeds) < 2:
                seeds = full.head(4)
            cand = []
            for _, row in seeds.iterrows():
                g = json.loads(row.gene); best = row.is_score
                for _ in range(4):
                    nb = [n for n in S.neighbours(g) if n["MainTimeframe"] == tf]
                    res = pool.map(ev_is, nb, chunksize=4)
                    i = max(range(len(nb)), key=lambda j: res[j]["score"] if res[j]["baskets"] >= 8 * res[j]["runs"] else -99)
                    if res[i]["score"] <= best + 0.01:
                        break
                    g, best = nb[i], res[i]["score"]
                cand.append(g)
            ref = pd.DataFrame(pool.map(ev_all, cand))
            ok = ref[ref.is_growth > 0]
            best = (ok if len(ok) else ref).sort_values("oos_score", ascending=False).iloc[0]
            g = json.loads(best.gene)
            p = SC.to_symbol(S.to_params(g, C.SHIPPED), sym)
            setfile.write(template, f"../presets/by_timeframe/TOKIO_VolLab_{sym}_{name}.set", p,
                          [f"Tokio732_VolLab - {sym}, trend timeframe {name}, calibrated (see REPORT_TIMEFRAMES.md)."])
            r = dict(timeframe=name, searched=N, **{k: best[k] for k in best.index if k != "gene"}, inputs=json.dumps(p))
            rows.append(r)
            print(name, {k: round(float(best[k]), 2) for k in ("is_growth", "is_worst_dd", "oos_score", "oos_growth", "oos_worst_dd",
                                                               "oos_ruined", "oos_baskets", "y26_growth")}, flush=True)
            pd.DataFrame(rows).to_csv(f"../results/timeframes_{sym}.csv", index=False)
