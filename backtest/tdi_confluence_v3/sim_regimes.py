"""False-positive rate of the Amendment 1 verdict (T1a + T1b + T4) next to the registered T1, in histories with NO edge,
including persistent dependence (carry-over and multi-month regimes in the rule's own results). PREREGISTRATION.md 8.4.

    python3 sim_regimes.py [histories=40000] [seed=20261113] [bootstrap B=20000]

Setup (as sim_final.py): 83 calendar months 2017-12 .. 2024-10, Poisson(9.2) trades a month drawn from the 232 tuning-data
trades of the frozen rule with their mean removed (so the true edge is exactly 0), plus
  - a common month effect (sd 60 bp per trade) with optional AR(1) carry-over between months,
  - or a two-state regime of +-a bp per trade that switches with probability q each month (average length 1/q months),
  - optionally the volatility profile by year of sim_final.py.
Tests exactly as validate.py: T1a month-clustered t (G-1 df), T1b 6-month blocks counted from 2017-12 (14 blocks),
T4 = the T1a p below 0.05 with each calendar year removed in turn; the registered T1 = month-block bootstrap p < 0.02.
For regime rows it also reports how many verdict passes came from histories whose realised regime average over the
83 months was positive (the rule then really did earn in that period, but has no long-run edge), and the pass rate among
histories whose realised regime average was <= 0 (the false-positive rate for the claim "the rule earned in this period").
Uses the tuning data only. Needs scipy (validate.py itself does not). Written by an adversarial verifier of Amendment 1
(cross-checked against validate.cluster_t and validate.block_boot), then made self-contained."""
import os, sys, time
import numpy as np, pandas as pd
from scipy.stats import t as tdist

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import validate as V

C_ALL = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
seed = int(sys.argv[2]) if len(sys.argv) > 2 else V.SEED
B = int(sys.argv[3]) if len(sys.argv) > 3 else V.N_BOOT
base = V.Ctx(V.load("BTCUSDT_insample")).run()[0]; assert len(base) == 232
base = base - base.mean()
months = pd.period_range("2017-12", "2024-10", freq="M"); M = len(months); years = months.year.to_numpy()
VOL = {2017: 2.0, 2018: 1.8, 2019: 1.4, 2020: 1.5, 2021: 1.8, 2022: 1.3, 2023: 0.9, 2024: 1.0}
rng = np.random.default_rng(seed)
Wb = np.zeros((B, M)); ii = rng.integers(0, M, size=(B, M)); np.add.at(Wb, (np.repeat(np.arange(B), M), ii.ravel()), 1.0)


def ctest(S, N, alpha):
    """cluster t on the columns of S / N (clusters); one-sided p; G = clusters with trades"""
    G = (N > 0).sum(1); Nt = N.sum(1); m = S.sum(1) / Nt; E = S - m[:, None] * N
    se = np.sqrt(G / (G - 1.0) * (E * E).sum(1)) / Nt
    p = tdist.sf(m / se, G - 1)
    return p < alpha, p


def gen(C, shock=60.0, ar=0.0, vol=False, regime=None):
    n = rng.poisson(9.2, size=(C, M))
    vals = base[rng.integers(0, len(base), int(n.sum()))]
    cell = np.repeat(np.arange(C * M), n.ravel())
    sums = np.bincount(cell, weights=vals, minlength=C * M).reshape(C, M)
    z = rng.normal(0, shock, size=(C, M)); e = np.empty((C, M))
    e[:, 0] = z[:, 0] * np.sqrt(1 - ar * ar)
    for i in range(1, M):
        e[:, i] = ar * e[:, i - 1] + z[:, i] * np.sqrt(1 - ar * ar)
    reg = np.zeros((C, M))
    if regime is not None:
        a, q = regime; s = np.where(rng.random(C) < 0.5, 1.0, -1.0)
        for i in range(M):
            if i:
                s = np.where(rng.random(C) < q, -s, s)
            reg[:, i] = s * a
    sc = np.array([VOL[y] for y in years]) if vol else np.ones(M)
    return sc * (sums + n * (e + reg)), n.astype(float), reg


def evaluate(S, N):
    a, _ = ctest(S, N, V.ALPHA)
    C = S.shape[0]; pad = (-M) % V.LONG_BLOCK
    S6 = np.pad(S, ((0, 0), (0, pad))).reshape(C, -1, V.LONG_BLOCK).sum(2); N6 = np.pad(N, ((0, 0), (0, pad))).reshape(C, -1, V.LONG_BLOCK).sum(2)
    b, _ = ctest(S6, N6, V.ALPHA)
    pmax = np.zeros(C)
    for y in np.unique(years):
        k = years != y
        pmax = np.maximum(pmax, ctest(S[:, k], N[:, k], V.ALPHA_LOYO)[1])
    p1 = np.empty(C)
    for c0 in range(0, C, 2000):
        D = (Wb @ S[c0:c0 + 2000].T) / (Wb @ N[c0:c0 + 2000].T); p1[c0:c0 + 2000] = (D <= 0).mean(0)
    return a, b, pmax < V.ALPHA_LOYO, p1 < V.ALPHA


def row(lab, **kw):
    t0 = time.time(); acc = []; regm = []
    for c0 in range(0, C_ALL, 5000):
        S, N, reg = gen(min(5000, C_ALL - c0), **kw); acc.append(np.column_stack(evaluate(S, N)))
        regm.append((reg * N).sum(1) / N.sum(1))
    A = np.concatenate(acc); regm = np.concatenate(regm)
    a, b, c, o = A.T; v = a & b & c; W = len(A)
    se = lambda x: 100 * np.sqrt(max(x.mean() * (1 - x.mean()), 1e-12) / W)
    extra = ""
    if kw.get("regime") is not None:
        extra = (f" | verdict passes with a positive realised regime average: {100 * np.mean(regm[v] > 0):.0f}%;"
                 f" pass rate when the realised regime average is <= 0: {100 * v[regm <= 0].mean():.2f}%")
    print(f"  {lab:44s} verdict T1a&T1b&T4 {100 * v.mean():5.2f}% (+-{se(v):.2f}) | registered T1 {100 * o.mean():5.2f}% (+-{se(o):.2f}) "
          f"| T1a {100 * a.mean():5.2f}%  T1b {100 * b.mean():5.2f}%  T4 {100 * c.mean():5.2f}%{extra}  [{time.time() - t0:.0f}s]", flush=True)


SCEN = [
    ("common month effect 60 bp", dict()),
    ("month effect carried over, autocorrelation 0.5", dict(ar=0.5)),
    ("volatility profile by year", dict(vol=True)),
    ("month effect carried over, autocorrelation 0.7", dict(ar=0.7)),
    ("regimes +-30 bp, about 6 months", dict(shock=0.0, regime=(30.0, 1 / 6))),
    ("regimes +-50 bp, about 6 months", dict(shock=0.0, regime=(50.0, 1 / 6))),
    ("regimes +-30 bp, about 12 months", dict(shock=0.0, regime=(30.0, 1 / 12))),
    ("regimes +-50 bp, about 12 months", dict(shock=0.0, regime=(50.0, 1 / 12))),
    ("regimes +-50 bp, about 24 months", dict(shock=0.0, regime=(50.0, 1 / 24))),
]
if __name__ == "__main__":
    print(f"{C_ALL} no-edge histories per row, seed {seed}, bootstrap B={B} for the registered T1")
    for lab, kw in SCEN:
        row(lab, **kw)
