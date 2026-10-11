"""Exit selection by in-sample TOTAL return (sum of ATR units per trade, after fees) instead of the t-statistic,
which favoured tight trails with many small wins. Same plateau rule: every in-sample year positive, modal value
of each setting among the 60 best sets. Keeps the t-ranked preset as preset_t_<tf>.json."""
import sys, json, os, shutil
import numpy as np
import pandas as pd
import fgrun as R
import pipe2 as P

OUT = P.OUT


def select_exits_sum(tf, C, top_n=60):
    Cn = C[(C.is_n >= P.NMIN_C[tf]) & (C.is_y_min > 0)]
    if len(Cn) < top_n:
        Cn = C[C.is_n >= P.NMIN_C[tf]]
    top = Cn.sort_values("is_sum", ascending=False).head(top_n)
    ex = {}
    for k in P.KEYS_C:
        v = top[k].mode().iloc[0]
        ex[k] = bool(v) if k in ("xopp", "xbrk") else (int(v) if k in ("rm", "rmax") else float(v))
    if ex["act"] == 0:
        ex["dst"] = 1.0
    if ex["act"] == 0 and ex["tpr"] == 0:
        ex["rm"] = 0          # nothing to re-enter after: no trailing stop, no target
    if ex["rm"] == 0:
        ex["rmax"] = 0
    return ex


if __name__ == "__main__":
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    for tf in [int(x) for x in sys.argv[1:]]:
        f = f"{OUT}/preset_{tf}.json"
        old = json.load(open(f))
        if not os.path.exists(f"{OUT}/preset_t_{tf}.json"):
            shutil.copy(f, f"{OUT}/preset_t_{tf}.json")
            old_t = old
        else:
            old_t = json.load(open(f"{OUT}/preset_t_{tf}.json"))
        C = pd.read_parquet(f"{OUT}/C_{tf}.parquet")
        ex = select_exits_sum(tf, C)
        B = pd.read_parquet(f"{OUT}/B_{tf}.parquet")
        entry, filt, brow = old_t["entry"], old_t["filter"], P.select_entry(tf, B)[2]
        res = P.finalize(tf, S, entry, filt, ex, brow, tf > 1)
        res["exits_t_ranked"] = old_t["exits"]
        res["results_t_ranked_preset"] = old_t["results"]["preset"]
        json.dump(res, open(f, "w"), indent=1, default=str)
        print(tf, "exits", ex, flush=True)
