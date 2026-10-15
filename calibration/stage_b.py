"""Stage B: entry filters as masks over the per-signal feature tables (forward-move objective)."""
import sys, itertools
import numpy as np
import pandas as pd

import os
MIN_IS = 120
REDUCED = os.environ.get("REDUCED") == "1"


def set_reduced(v):
    global REDUCED
    REDUCED = v


def grid(F, min_is=None):
    min_is = MIN_IS if min_is is None else min_is
    out = []
    for (pm, ma, fm), G in F.groupby(["pm", "ma", "fm"]):
        G = G.reset_index(drop=True)
        is_ = G["is"].to_numpy()
        buy = (G.dir == 1).to_numpy()
        f20 = G.f20.to_numpy(); f50 = G.f50.to_numpy(); lab1 = G.lab1.to_numpy(); lab2 = G.lab2.to_numpy()
        fast = G.fast.to_numpy(); pfast = G.pfast.to_numpy(); burst = G.burst.to_numpy()
        hurst = G.hurst.to_numpy(); areg = G.atr_reg.to_numpy(); wp = G.with_parent.to_numpy()
        atoms = dict(
            parent={0: np.ones(len(G), bool), 1: wp == 1},
            bmin={v: (~buy) | (fast >= v) for v in (0, 50, 60)},
            smax={v: buy | (fast <= v) for v in (100, 50, 40)},
            smin={v: buy | (fast >= v) for v in (0, 30)},
            bmax={v: (~buy) | (fast <= v) for v in ((100,) if REDUCED else (100, 80))},
            burst={v: burst >= v for v in (0.5, 0.75, 1.0, 1.5, 2.0)},
            hurst={0: np.ones(len(G), bool), 1: hurst >= 0.5, 2: hurst < 0.5},
            areg={v: areg >= v for v in (0.0, 0.8, 1.2)},
            pbmin={v: (~buy) | (pfast >= v) for v in ((0,) if REDUCED else (0, 50))},
            psmax={v: buy | (pfast <= v) for v in ((100,) if REDUCED else (100, 50))},
        )
        keys = list(atoms)
        for combo in itertools.product(*[list(atoms[k]) for k in keys]):
            m = np.ones(len(G), bool)
            for k, v in zip(keys, combo):
                m &= atoms[k][v]
            mi = m & is_
            n = int(mi.sum())
            if n < min_is:
                continue
            mo = m & ~is_
            x = f20[mi]; x = x[~np.isnan(x)]
            xo = f20[mo]; xo = xo[~np.isnan(xo)]
            l1 = lab1[mi]; l1 = l1[l1 >= 0]
            l1o = lab1[mo]; l1o = l1o[l1o >= 0]
            l2 = lab2[mi]; l2 = l2[l2 >= 0]
            r = dict(pm=pm, ma=ma, fm=fm)
            r.update(dict(zip(keys, combo)))
            r.update(is_n=n, is_f20=x.mean(), is_t=x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan,
                     is_f50=np.nanmean(f50[mi]), is_p1=l1.mean() if len(l1) else np.nan, is_p2=l2.mean() if len(l2) else np.nan,
                     oos_n=int(mo.sum()), oos_f20=xo.mean() if len(xo) else np.nan,
                     oos_t=xo.mean() / xo.std() * np.sqrt(len(xo)) if len(xo) > 2 else np.nan,
                     oos_p1=l1o.mean() if len(l1o) else np.nan)
            out.append(r)
    return pd.DataFrame(out)


if __name__ == "__main__":
    tf = int(sys.argv[1])
    F = pd.read_parquet(f"results/F_{tf}.parquet")
    df = grid(F)
    df["tf"] = tf
    df.to_parquet(f"results/B_{tf}.parquet")
    print("B done", tf, len(df))
