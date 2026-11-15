"""Independent re-implementation of hump_wf protocol 2's walk-forward selection and pass rule, written from the
hump_wf.py docstring only (no import of hump_wf), for the 8-column arrays.

Array A[setup, condition, cost (0 base, 1 stress), year (2013..2026), col]:
  col 0-3  trades, gross win R, gross loss R, cost R, by entry year
  col 4-7  the same over the trades that close in the calendar year they open in ("same-year")

Docstring rules implemented here:
  window   for test year Y: every setup is scored on Y-3, Y-2, Y-1: the lowest of six profit factors (3 years x base
           and stress costs), at least 20 trades in each of the six; setups whose average base cost per trade over
           those years is above 1/8 R are dropped. Protocol 2: every calibration sum leaves out the trades that close in
           a later calendar year than they open -> same-year columns 4-7 for counts, PFs and the cost rule.
  picks    the 10 best scores, one per (direction, session, trend filter) = (sides, session, htf) family, score >= 1.3;
           ties to the lower setup index (the docstring does not say).
  test     the picks' sums on year Y by entry year (columns 0-3), except the last test year before the final one
           (2025), which counts only the trades that close in it (columns 4-7).
  pass     the unseen years 2016-2025 together: PF >= 1.3 on >= 100 trades, stress PF >= 1.1, at least two unseen
           years with 50+ trades, none of those below PF 1.0.
  final    2026 (calibrated on 2023-2025, entry-year columns) only for cells that pass.
"""
import math, os, pickle
import numpy as np

MIN_N, TOPK, SEL_PF = 20, 10, 1.30
PASS_PF, PASS_STRESS, PASS_N, YEAR_N, MIN_FULL = 1.30, 1.10, 100, 50, 2
MAX_COST = 1.0 / 8.0
ENTRY, SAME = slice(0, 4), slice(4, 8)
LAST_WF_YEAR, FINAL_YEAR = 2025, 2026


def load(work, tf):
    A = np.load(os.path.join(work, f"wf_{tf}.npy"), mmap_mode="r")
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


def cond_stats(Av):
    """Av: [N, 2, Y, 8] float32 of one condition. Calibration quantities from the same-year columns, float64."""
    S = Av[:, :, :, SAME]
    n = S[..., 0].astype(np.float64)                       # [N, 2, Y]
    w = S[..., 1].astype(np.float64)
    l = S[..., 2].astype(np.float64)
    c = S[:, 0, :, 3].astype(np.float64)                   # [N, Y] base cost R
    with np.errstate(divide="ignore", invalid="ignore"):
        pf = np.where(l > 0, w / l, np.where(w > 0, np.inf, np.nan))
    return n, pf, c


def score_window(n, pf, c, cal):
    nc = n[:, :, cal]
    elig = (nc >= MIN_N).all(axis=(1, 2))
    pc = pf[:, :, cal]
    bad = np.isnan(pc).any(axis=(1, 2))
    worst = np.where(np.isnan(pc), np.inf, pc).min(axis=(1, 2))
    nb = n[:, 0, cal].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cpt = np.where(nb > 0, c[:, cal].sum(axis=1) / nb, np.inf)
    ok = elig & ~bad & (cpt <= MAX_COST)
    return np.where(ok, worst, 0.0), elig, cpt, ok, worst


def picks_of(score, fam, topk=TOPK, sel=SEL_PF):
    cand = np.flatnonzero(score >= sel)
    if not len(cand):
        return []
    order = cand[np.lexsort((cand, -score[cand]))]         # best score first, ties to the lower index
    seen, out = set(), []
    for i in order:
        f = int(fam[i])
        if f in seen:
            continue
        seen.add(f); out.append(int(i))
        if len(out) == topk:
            break
    return out


def tie_info(score, fam, picks, sel=SEL_PF):
    """Ties that the (unstated) tie rule decides: a pick whose family holds another setup with the same score,
    or a non-picked family whose best score equals the 10th pick's."""
    t = 0
    for i in picks:
        same = np.flatnonzero((fam == fam[i]) & (score == score[i]))
        if len(same) > 1:
            t += 1
    if len(picks) == TOPK:
        last = score[picks[-1]]
        picked_f = set(int(fam[i]) for i in picks)
        others = np.flatnonzero((score == last) & (score >= sel))
        if any(int(fam[j]) not in picked_f for j in others):
            t += 1
    return t


def test_sums(Av, picks, t, years):
    cols = SAME if years[t] == LAST_WF_YEAR else ENTRY
    if not picks:
        return np.zeros((2, 4)), ("same" if cols == SAME else "entry")
    s = Av[picks][:, :, t, cols].astype(np.float64).sum(axis=0)
    return s, ("same" if cols == SAME else "entry")


def window_dict(year, picks, s, score, elig, cpt, cols):
    return dict(year=year, picks=picks, cols=cols, n=int(round(s[0, 0])), win=float(s[0, 1]), loss=float(s[0, 2]),
                cost_r=float(s[0, 3]), stress_n=int(round(s[1, 0])), stress_win=float(s[1, 1]), stress_loss=float(s[1, 2]),
                pf=pf1(s[0, 1], s[0, 2]), stress_pf=pf1(s[1, 1], s[1, 2]), eligible=int(elig.sum()),
                eligible_after_cost_rule=int((elig & (cpt <= MAX_COST)).sum()), scores=[float(score[i]) for i in picks])


def verdict(wins):
    n = sum(w["n"] for w in wins); win = sum(w["win"] for w in wins); loss = sum(w["loss"] for w in wins)
    sw = sum(w["stress_win"] for w in wins); sl = sum(w["stress_loss"] for w in wins)
    cost = sum(w["cost_r"] for w in wins)
    p = pf1(win, loss); sp = pf1(sw, sl)
    full = [w for w in wins if w["n"] >= YEAR_N]
    losing = [w["year"] for w in full if not (w["pf"] >= 1.0)]
    ok = (n >= PASS_N) and (p >= PASS_PF) and (sp >= PASS_STRESS) and (len(full) >= MIN_FULL) and not losing
    return dict(n=n, win=win, loss=loss, pf=p, stress_pf=sp, net_r=win - loss, cost_r_per_trade=(cost / n if n else None),
                years_with_50_trades=len(full), losing_years=losing, passes=bool(ok))
