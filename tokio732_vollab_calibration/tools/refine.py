"""Stage 2: out-of-sample check of the stage-1 leaders, then one-input-at-a-time hill climbing of
the best survivors on the in-sample score only. usage: python refine.py SYMBOL"""
import json, sys
from multiprocessing import Pool
import pandas as pd
import space as S, score as SC

sym = sys.argv[1]
IS, OOS, Y26 = (SC.SPLIT[sym][k] for k in ("IS", "OOS", "Y26"))


def ev_is(g):
    return SC.evaluate(g, sym, IS)


def ev_all(g):
    out = {"gene": json.dumps(g)}
    for name, yrs in (("is", IS), ("oos", OOS), ("y26", Y26)):
        for k, v in SC.evaluate(g, sym, yrs).items():
            out[f"{name}_{k}"] = v
    return out


if __name__ == "__main__":
    s1 = pd.read_csv(f"../results/stage1_{sym}.csv")
    s1 = s1[s1.baskets >= 20 * s1.runs]
    lead = [json.loads(x) for x in s1.head(40).gene]
    with Pool(4) as pool:
        full = pd.DataFrame(pool.map(ev_all, lead))
        full.to_csv(f"../results/stage2_leaders_{sym}.csv", index=False)
        print(full.drop(columns="gene")[["is_score", "is_growth", "is_worst_dd", "oos_score", "oos_growth", "oos_worst_dd",
                                         "oos_ruined", "y26_growth"]].round(2).to_string())
        seeds = full[full.oos_growth > 0].head(6)
        if len(seeds) < 3:
            seeds = full.head(6)
        rows = []
        for _, row in seeds.iterrows():
            g = json.loads(row.gene); best = row.is_score
            for rnd in range(5):
                nb = S.neighbours(g)
                res = pool.map(ev_is, nb, chunksize=4)
                i = max(range(len(nb)), key=lambda j: res[j]["score"] if res[j]["baskets"] >= 20 * res[j]["runs"] else -99)
                if res[i]["score"] <= best + 0.01:
                    break
                g, best = nb[i], res[i]["score"]
                print("climb", rnd, round(best, 3), flush=True)
            rows.append(g)
        ref = pd.DataFrame(pool.map(ev_all, rows))
    ref.to_csv(f"../results/stage2_refined_{sym}.csv", index=False)
    print(ref.drop(columns="gene")[["is_score", "is_growth", "is_worst_dd", "is_ruined", "oos_score", "oos_growth",
                                    "oos_worst_dd", "oos_ruined", "oos_baskets", "y26_growth", "y26_worst_dd"]].round(2).to_string())
