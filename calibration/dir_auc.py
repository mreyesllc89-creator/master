"""AUC of the direction filter's zones for every parent / child-zone / alignment choice, per filter timeframe.
Score at a filter candle's close: the zone the filter shows (v1.2 defaults: BUY ZONE +1 above level + 0.25 ATR,
SELL ZONE -1 below level - 0.25 ATR, NO TRADE 0; also the bare level (band 0) and 'signal only' (against off)).
Label: the close H filter candles later higher (1) or lower (0), ties dropped. AUC = P(score of an up case >
score of a down case) + half the ties: 0.5 = no information, independent of the market's drift."""
import sys, itertools, time
import numpy as np
import pandas as pd
import fgrun as R
from calib import IS_END

import os
OUT = os.environ.get("AUC_OUT", "results_dir")
HS = (1, 3, 10)
YEARS = (2023, 2024, 2025)
ZSETS = [(1,), (2,), (4,), (1, 2), (1, 4), (2, 4), (1, 2, 4), (2, 4, 8), (1, 4, 16), (4, 8, 16), (1, 2, 4, 8)]
PMS = (1, 2, 4, 8, 16)
BAND = 0.25


def zones(tf, mults):
    z = [(True, tf * m) for m in mults]
    while len(z) < 6:
        z.append((False, tf))
    return tuple(z)


def held(c, atr, buy, sell, bpx, spx):
    """level, band unit (ATR at the signal) and side of the last signal, per candle"""
    N = len(c)
    L = np.full(N, np.nan); A = np.full(N, np.nan); D = np.zeros(N, np.int8)
    idx = np.where(buy | sell)[0]
    if len(idx) == 0:
        return L, A, D
    lv = np.where(buy[idx], bpx[idx], spx[idx])
    lv = np.where(np.isnan(lv), c[idx], lv)
    pos = np.searchsorted(idx, np.arange(N), side="right") - 1
    ok = pos >= 0
    L[ok] = lv[pos[ok]]; A[ok] = atr[idx][pos[ok]]; D[ok] = np.where(buy[idx], 1, -1)[pos[ok]]
    return L, A, D


def auc_counts(s, y):
    """AUC of an integer score s in {-1, 0, 1} for binary y (1 up, 0 down)"""
    nu = np.array([np.sum((s == v) & (y == 1)) for v in (-1, 0, 1)], float)
    nd = np.array([np.sum((s == v) & (y == 0)) for v in (-1, 0, 1)], float)
    NU, ND = nu.sum(), nd.sum()
    if NU == 0 or ND == 0:
        return np.nan
    gt = nu[1] * nd[0] + nu[2] * (nd[0] + nd[1])
    tie = (nu * nd).sum()
    return (gt + 0.5 * tie) / (NU * ND)


def evaluate(c, t_open, scores, split, warm=300):
    yr = pd.to_datetime(t_open, unit="s", utc=True).year.to_numpy()
    N = len(c)
    base = np.arange(N) >= warm
    out = {}
    for H in HS:
        fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
        ok = base & ~np.isnan(fwd) & (fwd != 0)
        y = (fwd > 0).astype(int)
        for name, s in scores.items():
            for per, m in (("is", t_open < split), ("oos", t_open >= split)):
                mm = ok & m
                out[f"{name}_{per}_auc{H}"] = auc_counts(s[mm], y[mm])
            if H == 10:
                ys = [auc_counts(s[ok & (t_open < split) & (yr == yy)], y[ok & (t_open < split) & (yr == yy)]) for yy in YEARS]
                out[f"{name}_is_ymin10"] = np.nanmin(ys)
            # in-sample halves for a selection check that never looks at the out-of-sample period:
            # A = 2023, B = 2024-01 .. 2025-06
            for half, hm in (("A", ok & (yr == 2023)), ("B", ok & (t_open < split) & (yr >= 2024))):
                out[f"{name}_{half}_auc{H}"] = auc_counts(s[hm], y[hm])
    for name, s in scores.items():
        for per, m in (("is", t_open < split), ("oos", t_open >= split)):
            out[f"{name}_{per}_auc"] = np.nanmean([out[f"{name}_{per}_auc{H}"] for H in HS])
        for half in ("A", "B"):
            out[f"{name}_{half}_auc"] = np.nanmean([out[f"{name}_{half}_auc{H}"] for H in HS])
            out[f"{name}_{per}_cov"] = float((s[base & m] != 0).mean())
    return out


def run(tf, S):
    split = int(IS_END.timestamp())
    ch = S.bars(tf)
    c = ch["c"]
    rows = []
    t0 = time.time()
    combos = [(pm, zs, ma) for pm in PMS for zs in ZSETS for ma in range(1, len(zs) + 1)] + [(pm, (), 0) for pm in (1,)]
    for i, (pm, zs, ma) in enumerate(combos):
        p = R.params(parent_tf=tf * pm, zones=zones(tf, zs) if zs else zones(tf, (1,)), min_aligned=ma,
                     use_zones=bool(zs), burst_atr=0.5, fd_tf=tf)
        ctx = R.context(S, tf, p)
        L, A, D = held(c, ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
        b = BAND * np.nan_to_num(A)
        z_band = np.where(c > L + b, 1, np.where(c < L - b, -1, 0)).astype(np.int8)
        z_band[np.isnan(L)] = 0
        z_bare = np.where(c > L, 1, np.where(c < L, -1, 0)).astype(np.int8)
        z_bare[np.isnan(L)] = 0
        z_sig = np.where(((D == 1) & (z_band == 1)) | ((D == -1) & (z_band == -1)), z_band, 0).astype(np.int8)
        r = dict(tf=tf, pm=pm, zones="/".join(f"x{m}" for m in zs) if zs else "none", ma=ma,
                 n_sig_is=int((ctx["buy"] | ctx["sell"])[ch["t_open"] < split].sum()))
        r.update(evaluate(c, ch["t_open"], {"zone": z_band, "bare": z_bare, "sigonly": z_sig}, split))
        rows.append(r)
        if i % 20 == 0:
            print(f"[AUC tf={tf}] {i}/{len(combos)} {time.time()-t0:.0f}s", flush=True)
    D = pd.DataFrame(rows)
    D.to_parquet(f"{OUT}/AUC_{tf}.parquet")
    return D


if __name__ == "__main__":
    tf = int(sys.argv[1])
    S = R.Source(pd.read_parquet("btc_1m.parquet"), 1)
    run(tf, S)
    print("AUC done", tf)
