"""Independent re-implementation of the walk-forward selection and pass rule of hump_wf, written from its docstring
only (no import of hump_wf).

Docstring rules implemented here:
  windows  for test year Y: score each setup on the three years before it = lowest of six profit factors
           (3 years x base/stress costs), at least 20 trades in each of the six; drop setups whose average base
           cost per trade over those years is above 1/8 R; picks = the 10 best scores, one per (sides, session, htf)
           family, score >= 1.3; the picks' sums on year Y.
  pass     all unseen years (every test year except the last year of the data) together: PF >= 1.3 on >= 100
           trades, stress PF >= 1.1, no unseen year with 50+ trades below PF 1.0, at least two unseen years with 50+.
Array layout: A[setup, condition, cost(0 base, 1 stress), year, (trades, gross win R, gross loss R, cost R)].
"""
import math, os, pickle
import numpy as np

MIN_N, TOPK, SEL_PF = 20, 10, 1.30
PASS_PF, PASS_STRESS, PASS_N, YEAR_N, MIN_FULL = 1.30, 1.10, 100, 50, 2
MAX_COST = 1.0 / 8.0


def load(work, tf, mmap=True):
    A = np.load(os.path.join(work, f"wf_{tf}.npy"), mmap_mode="r" if mmap else None)
    with open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb") as f:
        d = pickle.load(f)
    return A, d


def fam_codes(P):
    keys = {}
    return np.array([keys.setdefault((p["sides"], p["session"], p["htf"]), len(keys)) for p in P], np.int64)


def pf1(w, l):
    if l > 0:
        return w / l
    return math.inf if w > 0 else math.nan


def per_year(A):
    """Per setup, condition, cost and year: trades, PF (nan when no win and no loss), base cost sum. float64."""
    n = np.asarray(A[..., 0], dtype=np.float64)
    w = np.asarray(A[..., 1], dtype=np.float64)
    l = np.asarray(A[..., 2], dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        pf = np.where(l > 0, w / l, np.where(w > 0, np.inf, np.nan))
    c = np.asarray(A[:, :, 0, :, 3], dtype=np.float64)
    return n, pf, c


def scores(n, pf, c, cal):
    """n, pf: [N, V, 2, Y]; c: [N, V, Y] (base cost R). Returns score [N, V], eligible [N, V], cost per trade [N, V]."""
    nc = n[:, :, :, cal]
    elig = (nc >= MIN_N).all(axis=(2, 3))
    pc = pf[:, :, :, cal]
    bad = np.isnan(pc).any(axis=(2, 3))                      # no win and no loss in a year: no profit factor
    worst = np.where(np.isnan(pc), np.inf, pc).min(axis=(2, 3))
    nb = n[:, :, 0, cal].sum(axis=2)
    with np.errstate(divide="ignore", invalid="ignore"):
        cpt = np.where(nb > 0, c[:, :, cal].sum(axis=2) / nb, np.inf)
    ok = elig & ~bad & (cpt <= MAX_COST)
    return np.where(ok, worst, 0.0), elig, cpt


def picks_of(score_v, fam, topk=TOPK, sel=SEL_PF):
    """score_v: [N]. The topk best scores >= sel, one per family; ties to the lower setup index."""
    cand = np.flatnonzero(score_v >= sel)
    if not len(cand):
        return []
    order = cand[np.lexsort((cand, -score_v[cand]))]
    f = fam[order]
    _, first = np.unique(f, return_index=True)               # first (best) setup of every family in that order
    first = np.sort(first)[:topk]
    return [int(i) for i in order[first]]


def walk(A, fam, years, conds=None, order=None, setup_perm=None, keep_scores=False, pre=None):
    """All windows for the conditions `conds` (default all). order: year indices in the order the walk-forward
    runs over (default chronological; the last entry is the final year). setup_perm: optional [Y, N] permutation of
    setups per year (the results of year y of setup i are those of setup setup_perm[y, i]).
    Returns {v: [window dicts in order]}."""
    Y = len(years)
    seq = list(range(Y)) if order is None else list(order)
    n, pf, c = per_year(A) if pre is None else pre
    if setup_perm is not None:
        n = n.copy(); pf = pf.copy(); c = c.copy()
        for y in range(Y):
            n[:, :, :, y] = n[setup_perm[y], :, :, y]; pf[:, :, :, y] = pf[setup_perm[y], :, :, y]; c[:, :, y] = c[setup_perm[y], :, y]
    V = A.shape[1]
    conds = range(V) if conds is None else conds
    out = {v: [] for v in conds}
    for pos in range(3, len(seq)):
        ty = seq[pos]; cal = [seq[pos - 3], seq[pos - 2], seq[pos - 1]]
        sc, elig, cpt = scores(n, pf, c, cal)
        for v in conds:
            pk = picks_of(sc[:, v], fam)
            if setup_perm is None:
                s = np.asarray(A[pk, v][:, :, ty, :], dtype=np.float64).sum(axis=0) if pk else np.zeros((2, 4))
            else:
                rows = setup_perm[ty][pk]
                s = np.asarray(A[rows, v][:, :, ty, :], dtype=np.float64).sum(axis=0) if pk else np.zeros((2, 4))
            d = dict(year=years[ty], picks=pk, n=int(s[0, 0]), win=float(s[0, 1]), loss=float(s[0, 2]), cost_r=float(s[0, 3]),
                     stress_n=int(s[1, 0]), stress_win=float(s[1, 1]), stress_loss=float(s[1, 2]),
                     pf=pf1(s[0, 1], s[0, 2]), stress_pf=pf1(s[1, 1], s[1, 2]),
                     eligible=int(elig[:, v].sum()), eligible_after_cost_rule=int((elig[:, v] & (cpt[:, v] <= MAX_COST)).sum()))
            if keep_scores:
                d["scores"] = [float(sc[i, v]) for i in pk]
            out[v].append(d)
    return out


def verdict(wins, pass_pf=PASS_PF, pass_stress=PASS_STRESS, pass_n=PASS_N, year_n=YEAR_N, min_full=MIN_FULL, floor=1.0):
    """wins: the unseen-year window dicts (final year excluded)."""
    n = sum(w["n"] for w in wins); win = sum(w["win"] for w in wins); loss = sum(w["loss"] for w in wins)
    sw = sum(w["stress_win"] for w in wins); sl = sum(w["stress_loss"] for w in wins)
    p = pf1(win, loss); sp = pf1(sw, sl)
    full = [w for w in wins if w["n"] >= year_n]
    losing = [w["year"] for w in full if not (w["pf"] >= floor)]
    ok = (n >= pass_n) and (p >= pass_pf) and (sp >= pass_stress) and (len(full) >= min_full) and not losing
    return dict(n=n, win=win, loss=loss, pf=p, stress_pf=sp, years_with_50_trades=len(full), losing_years=losing, passes=bool(ok))


def cells(A, fam, years, **kw):
    """Per condition: unseen windows, final window and the verdict (final = last window of the walk)."""
    res = {}
    for v, wins in walk(A, fam, years, **kw).items():
        res[v] = dict(by_year=wins[:-1], final=wins[-1], **verdict(wins[:-1]))
    return res
