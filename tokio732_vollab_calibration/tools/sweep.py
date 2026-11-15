"""Stage 1: random search on the in-sample years. usage: python sweep.py SYMBOL N SEED"""
import json, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd
import space as S, score as SC

sym, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])


def work(g):
    r = SC.evaluate(g, sym, SC.SPLIT[sym]["IS"])
    r["gene"] = json.dumps(g)
    return r


if __name__ == "__main__":
    rng = np.random.default_rng(seed)
    genes = [S.shipped_gene()] + [S.draw(rng) for _ in range(n)]
    t = time.time()
    with Pool(4) as pool:
        rows = pool.map(work, genes, chunksize=8)
    df = pd.DataFrame(rows).sort_values("score", ascending=False)
    df.to_csv(f"../results/stage1_{sym}.csv", index=False)
    print(sym, len(df), "configs", round(time.time() - t), "s")
    print(df.drop(columns="gene").head(12).round(2).to_string())
    print("shipped:", {k: round(v, 2) for k, v in rows[0].items() if k != "gene"})
