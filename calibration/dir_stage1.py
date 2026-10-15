"""Direction accuracy, stage 1: which signals are real. For every entry-logic / quality-gate set, the balanced hit
rate of the signal's direction (mean of the buy and sell hit rates, so BTC's drift does not count) after 5 and 20
candles, and the 'real' rate (+1 ATR in the direction before -1 ATR). In-sample years and out-of-sample reported."""
import sys, itertools, os
import numpy as np
import pandas as pd

OUT = "results_dir"
YEARS = (2023, 2024, 2025)
NMIN = {1: 3000, 5: 1500, 15: 600, 30: 400, 60: 250, 120: 150, 240: 100, 480: 60, 1440: 40}


def bal(hit, buy, m):
    """balanced hit rate over mask m: mean of the buy and sell hit rates (nan-safe), and counts"""
    hb = hit[m & buy]; hs = hit[m & ~buy]
    hb = hb[~np.isnan(hb)]; hs = hs[~np.isnan(hs)]
    if len(hb) < 5 or len(hs) < 5:
        return np.nan, len(hb), len(hs)
    return 0.5 * (hb.mean() + hs.mean()), len(hb), len(hs)


def grid(F, reduced=False):
    out = []
    yr = F.t.dt.year.to_numpy()
    for (pm, ma, fm), G in F.groupby(["pm", "ma", "fm"]):
        G = G.reset_index(drop=True)
        yr = G.t.dt.year.to_numpy()
        is_ = G["is"].to_numpy()
        buy = (G.dir == 1).to_numpy()
        h5 = np.where(np.isnan(G.f5), np.nan, (G.f5 > 0).astype(float)).astype(float)
        h20 = np.where(np.isnan(G.f20), np.nan, (G.f20 > 0).astype(float)).astype(float)
        lab = G.lab1.to_numpy().astype(float); lab[lab < 0] = np.nan
        fast = G.fast.to_numpy(); pfast = G.pfast.to_numpy(); burst = G.burst.to_numpy()
        hurst = G.hurst.to_numpy(); areg = G.atr_reg.to_numpy(); wp = G.with_parent.to_numpy()
        one = np.ones(len(G), bool)
        atoms = dict(
            parent={0: one, 1: wp == 1},
            bmin={v: (~buy) | (fast >= v) for v in (0, 50, 60)},
            bmax={v: (~buy) | (fast <= v) for v in ((100,) if reduced else (100, 80))},
            smax={v: buy | (fast <= v) for v in (100, 50, 40)},
            smin={v: buy | (fast >= v) for v in (0, 20, 30)},
            burst={v: burst >= v for v in (0.5, 0.75, 1.0, 1.5, 2.0)},
            hurst={0: one, 1: hurst >= 0.5, 2: hurst < 0.5},
            areg={v: areg >= v for v in (0.0, 0.8, 1.2)},
            pbmin={v: (~buy) | (pfast >= v) for v in ((0,) if reduced else (0, 50))},
            psmax={v: buy | (pfast <= v) for v in ((100,) if reduced else (100, 50))},
        )
        keys = list(atoms)
        for combo in itertools.product(*[list(atoms[k]) for k in keys]):
            m = one.copy()
            for k, v in zip(keys, combo):
                m &= atoms[k][v]
            mi = m & is_
            if mi.sum() < 40:
                continue
            r = dict(pm=pm, ma=ma, fm=fm); r.update(dict(zip(keys, combo)))
            for name, mm in (("is", mi), ("oos", m & ~is_)):
                b20, nb, ns = bal(h20, buy, mm)
                b5, _, _ = bal(h5, buy, mm)
                bl, _, _ = bal(lab, buy, mm)
                r.update({f"{name}_n": int(mm.sum()), f"{name}_nb": nb, f"{name}_ns": ns, f"{name}_bal20": b20,
                          f"{name}_bal5": b5, f"{name}_real": bl})
            ys = []
            for y in YEARS:
                v, _, _ = bal(h20, buy, mi & (yr == y))
                ys.append(v)
            r["is_y_min20"] = np.nanmin(ys) if not np.all(np.isnan(ys)) else np.nan
            r["is_y_nan"] = int(np.isnan(ys).sum())
            out.append(r)
    return pd.DataFrame(out)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    tf = int(sys.argv[1])
    F = pd.read_parquet(f"results3/F_{tf}.parquet")
    reduced = tf == 1
    if reduced:
        F = F[F.pm.isin([1, 4]) & (F.ma == 2)]
    D = grid(F, reduced)
    D["tf"] = tf
    D.to_parquet(f"{OUT}/D1_{tf}.parquet")
    print("D1 done", tf, len(D), flush=True)
