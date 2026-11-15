#!/usr/bin/env python3
"""audit_wf/nulls.py (SETUP and ORDER year reshuffles) adapted to protocol 2 (EURUSD, US500): 8-column arrays.

Arrays wf_<TF>.npy: A[setup, condition, cost (0 base, 1 stress), year 2013..2026, 8]; columns 0-3 trades / gross win R /
gross loss R / cost R by entry year, columns 4-7 the same over the trades that close in the year they open in.
Protocol-2 rules (hump_wf docstring "windows"/"final", hump_wf.wf_tf and window_pick), re-implemented here:
  calibration years  columns 4-7: score = lowest of the six profit factors (3 years x 2 costs) on columns 5/6, at least
                     20 trades (column 4) in each of the six; base cost per trade = sum col 7 / sum col 4 over the three
                     years <= 1/8 R; picks = 10 best scores >= 1.3, one per (sides, session, htf) family (wfcore.picks_of).
  test year          columns 0-3 (every trade by entry year), except calendar year 2025 (the last test year before the
                     final one): columns 4-7.
  pass               unseen years 2016-2025 together (wfcore.verdict): PF >= 1.3 on >= 100 trades, stress PF >= 1.1,
                     >= 2 unseen years with 50+ trades, none of them below 1.0. The final year 2026 is never computed.
Reshuffles (as audit_wf/nulls.py):
  SETUP  for every condition and every year, setups sorted by their base trade count of that year (column 0, cost 0;
         random among equals) and permuted inside consecutive blocks of 40 sorted positions; setup i takes ALL 8 columns
         (both costs) of that year from setup src[i], so its calibration (cols 4-7) and test (cols 0-3 / 4-7) figures
         of that year move together.
  ORDER  the 13 non-final years in a random order, 2026 stays last (and out of the pass rule); every setup keeps all its
         results; a calendar year is read as in the real run: columns 4-7 as a calibration year, columns 0-3 as a test
         year except 2025 (columns 4-7; the column choice follows the calendar year, not the position).
Usage: python3 nulls2.py <eurusd|us500> <n_setup> <n_order> <out_json> [TF,TF,...] [--verify-only] [--batch=K]
"""
import json, math, os, pickle, resource, sys, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, "/workspace/master/research/audit_wf")
import wfcore as M                                       # picks_of, verdict, pf1 and the constants of the rule

S = "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad"
WORK = {"eurusd": f"{S}/wfx/eurusd", "us500": f"{S}/wfx/us500"}
EVAL = {"eurusd": f"{S}/wf/eurusd_wf.json", "us500": f"{S}/wf/us500_wf.json"}
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
BLOCK = 40
SEED = {"eurusd": 4242 + 20, "us500": 4242 + 30}
CHUNK = 400
assert M.MIN_N == 20 and M.TOPK == 10 and M.SEL_PF == 1.30 and M.MAX_COST == 1.0 / 8.0
assert (M.PASS_PF, M.PASS_STRESS, M.PASS_N, M.YEAR_N, M.MIN_FULL) == (1.30, 1.10, 100, 50, 2)


def load_tf(work, tf):
    A = np.load(os.path.join(work, f"wf_{tf}.npy"), mmap_mode="r")
    with open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb") as f:
        d = pickle.load(f)
    N, V, C, Y, K = A.shape
    years = [int(y) for y in d["years"]]
    assert K == 8 and C == 2 and int(d.get("protocol", 1)) == 2 and len(years) == Y and V == len(d["keys"]) == 59
    y25 = years.index(2025)
    assert years[-1] == 2026 and y25 == Y - 2
    elig_y = np.empty((V, Y, N), bool)                   # >= 20 same-year trades with both costs
    bad_y = np.empty((V, Y, N), bool)                    # a profit factor undefined (no win and no loss) with a cost
    minpf_y = np.empty((V, Y, N), np.float64)            # lower of the two profit factors (undefined -> inf, then bad)
    ccal = np.empty((V, Y, N), np.float64)               # base cost R of the same-year trades (col 7)
    nbcal = np.empty((V, Y, N), np.float64)              # base same-year trade count (col 4)
    nact = np.empty((V, Y, N), np.float32)               # base trade count by entry year (col 0): activity for SETUP
    T = np.empty((V, Y, N, 2, 4), np.float32)            # what a test year sums: cols 0-3, 2025 cols 4-7
    for i0 in range(0, N, CHUNK):
        i1 = min(N, i0 + CHUNK)
        a = np.array(A[i0:i1]).transpose(1, 3, 0, 2, 4)  # [V, Y, n, 2, 8]
        w = a[..., 5].astype(np.float64); l = a[..., 6].astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            pf = np.where(l > 0, w / l, np.where(w > 0, np.inf, np.nan))     # as hump_wf.pf_of on float64
        nan = np.isnan(pf)
        elig_y[:, :, i0:i1] = (a[..., 4] >= M.MIN_N).all(axis=-1)
        bad_y[:, :, i0:i1] = nan.any(axis=-1)
        minpf_y[:, :, i0:i1] = np.where(nan, np.inf, pf).min(axis=-1)
        ccal[:, :, i0:i1] = a[:, :, :, 0, 7]
        nbcal[:, :, i0:i1] = a[:, :, :, 0, 4]
        nact[:, :, i0:i1] = a[:, :, :, 0, 0]
        T[:, :, i0:i1] = a[..., 0:4]
        T[:, y25, i0:i1] = a[:, y25, :, :, 4:8]
        del a, w, l, pf, nan
    del A
    fam = M.fam_codes(d["params"])
    return dict(cal=(elig_y, bad_y, minpf_y, ccal, nbcal), nact=nact, T=T, years=years, keys=list(d["keys"]), fam=fam,
                N=N, V=V, Y=Y)


def scores(cal_arrays, cal):
    """[V, N] score, eligible, cost per trade for the calibration years cal (three year indices, in window order)."""
    elig_y, bad_y, minpf_y, ccal, nbcal = cal_arrays
    a, b, c = cal
    elig = elig_y[:, a] & elig_y[:, b] & elig_y[:, c]
    bad = bad_y[:, a] | bad_y[:, b] | bad_y[:, c]
    worst = np.minimum(np.minimum(minpf_y[:, a], minpf_y[:, b]), minpf_y[:, c])
    cs = (ccal[:, a] + ccal[:, b]) + ccal[:, c]          # the association order of hump_wf's sum (checked bit for bit)
    nb = (nbcal[:, a] + nbcal[:, b]) + nbcal[:, c]
    with np.errstate(divide="ignore", invalid="ignore"):
        cpt = np.where(nb > 0, cs / nb, np.inf)
    ok = elig & ~bad & (cpt <= M.MAX_COST)
    return np.where(ok, worst, 0.0), elig, cpt


def walk(D, seq, cal_arrays=None, src=None, detail=False):
    """Unseen windows (every test position but the final year's) of all conditions. src: [V, Y, N] SETUP mapping."""
    cal_arrays = D["cal"] if cal_arrays is None else cal_arrays
    T, years, V, fam = D["T"], D["years"], D["V"], D["fam"]
    out = [[] for _ in range(V)]
    for pos in range(3, len(seq) - 1):
        ty = seq[pos]
        sc, elig, cpt = scores(cal_arrays, [seq[pos - 3], seq[pos - 2], seq[pos - 1]])
        if detail:
            ecount = elig.sum(axis=1); ecost = (elig & (cpt <= M.MAX_COST)).sum(axis=1)
        for v in range(V):
            pk = M.picks_of(sc[v], fam)
            if pk:
                rows = np.asarray(pk, np.int64) if src is None else src[v, ty][pk]
                s = T[v, ty][rows].astype(np.float64).sum(axis=0)
            else:
                s = np.zeros((2, 4))
            w = dict(year=years[ty], picks=pk, n=int(s[0, 0]), win=float(s[0, 1]), loss=float(s[0, 2]),
                     stress_n=int(s[1, 0]), stress_win=float(s[1, 1]), stress_loss=float(s[1, 2]),
                     pf=M.pf1(float(s[0, 1]), float(s[0, 2])), stress_pf=M.pf1(float(s[1, 1]), float(s[1, 2])))
            if detail:
                w.update(eligible=int(ecount[v]), eligible_after_cost_rule=int(ecost[v]))
            out[v].append(w)
    return out


def flags(wins_by_v):
    return [bool(M.verdict(w)["passes"]) for w in wins_by_v]


def same(a, b):
    if a is None or b is None:
        return a is None and b is None
    a = float(a); b = float(b)
    return (math.isnan(a) and math.isnan(b)) or a == b


def verify(D, rows):
    """The adapted evaluation against hump_wf's own output (rows of <sym>_wf.json for this timeframe)."""
    real = walk(D, list(range(D["Y"])), detail=True)
    rep = dict(cells=0, flag_mismatch=[], pass_cells=[], cells_exact=0, window_checks=0, window_mismatch=[])
    for v, key in enumerate(D["keys"]):
        r = rows[key]
        vd = M.verdict(real[v])
        rep["cells"] += 1
        if vd["passes"] != r["passes"]:
            rep["flag_mismatch"].append(key)
        if vd["passes"]:
            rep["pass_cells"].append(key)
        cell_ok = (vd["n"] == r["n"] and same(vd["pf"], r["pf"]) and same(vd["stress_pf"], r["stress_pf"])
                   and vd["years_with_50_trades"] == r["years_with_50_trades"] and vd["losing_years"] == r["losing_years"]
                   and len(real[v]) == len(r["by_year"]))
        for w, ry in zip(real[v], r["by_year"]):
            rep["window_checks"] += 1
            ok = (w["year"] == ry["year"] and w["picks"] == ry["picks"] and w["n"] == ry["n"] and w["stress_n"] == ry["stress_n"]
                  and same(w["win"], ry["win"]) and same(w["loss"], ry["loss"]) and same(w["stress_win"], ry["stress_win"])
                  and same(w["stress_loss"], ry["stress_loss"]) and same(w["pf"], ry["pf"]) and same(w["stress_pf"], ry["stress_pf"])
                  and w["eligible"] == ry["eligible"] and w["eligible_after_cost_rule"] == ry["eligible_after_cost_rule"])
            if not ok:
                rep["window_mismatch"].append([key, w["year"]])
                cell_ok = False
        rep["cells_exact"] += int(cell_ok)
    return rep, real


def setup_src(nact, rng, check=False):
    """nulls.py's SETUP permutation for every (condition, year) at once: [V, Y, N], setup i takes setup src[i]."""
    V, Y, N = nact.shape
    assert N % BLOCK == 0
    key = nact.reshape(V * Y, N).astype(np.float64)
    # nulls.py: o = lexsort((random, activity)); the counts are whole numbers, so activity + 0.5 * uniform sorts the
    # same way (by activity, a random order among equals; checked equal to the lexsort on the same numbers), faster
    o = np.argsort(key + 0.5 * rng.random((V * Y, N)), axis=-1)
    # nulls.py: pp = lexsort((random, position // 40)): a uniform random order inside every block of 40 positions
    pp = rng.permuted(np.broadcast_to(np.arange(BLOCK), (V * Y, N // BLOCK, BLOCK)), axis=-1)
    pp = (pp + (np.arange(N // BLOCK) * BLOCK)[:, None]).reshape(V * Y, N)
    perm = np.take_along_axis(o, pp, axis=-1)
    src = np.empty_like(o)
    np.put_along_axis(src, o, perm, axis=-1)                                  # setup o[j] takes the results of perm[j]
    if check:                                  # a setup takes the results of a setup in its own block of 40 by activity
        pos = np.empty_like(o)
        np.put_along_axis(pos, o, np.broadcast_to(np.arange(N), (V * Y, N)), axis=-1)
        assert np.array_equal(np.take_along_axis(pos, src, axis=-1) // BLOCK, pos // BLOCK)
        assert np.array_equal(np.sort(src, axis=-1), np.broadcast_to(np.arange(N), (V * Y, N)))
        assert (np.diff(np.take_along_axis(key, o, axis=-1), axis=-1) >= 0).all()
        del pos
    return src.reshape(V, Y, N)


def main():
    sym, ns, no, out_json = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    only = sys.argv[5].split(",") if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else None
    verify_only = "--verify-only" in sys.argv
    batch = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--batch=")), 0))
    J = json.load(open(EVAL[sym]))
    rows_all = {}
    for r in J["rows"]:
        rows_all.setdefault(r["tf"], {})[r["condition"]] = r
    res = dict(symbol=sym, work=WORK[sym], evaluation=EVAL[sym], script=os.path.abspath(__file__), block=BLOCK,
               seed=SEED[sym], batch=batch, seed_note="rng = default_rng([seed, timeframe index in TFS, batch]) per timeframe; SETUP runs first",
               runs_setup=ns, runs_order=no, rules=__doc__.split("Usage:")[0].strip().splitlines(), tfs={})
    if os.path.exists(out_json) and only:                                   # several invocations add their timeframes
        old = json.load(open(out_json))
        assert old.get("symbol") == sym
        res["tfs"] = old.get("tfs", {})
    for ti, tf in enumerate(TFS):
        if only and tf not in only:
            continue
        t0 = time.time()
        D = load_tf(WORK[sym], tf)
        t_load = time.time() - t0
        rep, real = verify(D, rows_all[tf])
        real_pass = flags(real)
        V = D["V"]
        r_tf = dict(keys=D["keys"], verify=dict(cells=rep["cells"], flag_mismatches=len(rep["flag_mismatch"]),
                                                cells_exact=rep["cells_exact"], window_checks=rep["window_checks"],
                                                window_mismatches=len(rep["window_mismatch"]),
                                                examples=rep["flag_mismatch"][:5] + rep["window_mismatch"][:5]),
                    real_pass_idx=[v for v in range(V) if real_pass[v]], setup_pass_idx=[], order_pass_idx=[], orders=[])
        print(f"{sym} {tf}: load {t_load:.0f}s; verify: {rep['cells']} cells, flag mismatches {len(rep['flag_mismatch'])}, "
              f"cells exact {rep['cells_exact']}, window mismatches {len(rep['window_mismatch'])}/{rep['window_checks']}; "
              f"real passes {[D['keys'][v] for v in r_tf['real_pass_idx']]}", flush=True)
        if rep["flag_mismatch"] or rep["window_mismatch"]:
            res["tfs"][tf] = r_tf
            json.dump(res, open(out_json, "w"))
            raise SystemExit(f"{sym} {tf}: the adapted evaluation does not reproduce hump_wf; nulls not run")
        if not verify_only:
            rng = np.random.default_rng([SEED[sym], ti, batch])
            elig_y, bad_y, minpf_y, ccal, nbcal = D["cal"]
            Yn, Nn = D["Y"], D["N"]
            base = (np.arange(V * Yn) * Nn)[:, None]
            ident = np.broadcast_to(np.arange(Nn), (V, Yn, Nn))           # the SETUP code path, no reshuffle: real flags
            Pi = tuple(np.take(a.reshape(-1), (base + ident.reshape(V * Yn, Nn)).ravel()).reshape(V, Yn, Nn) for a in D["cal"])
            assert flags(walk(D, list(range(Yn)), cal_arrays=Pi, src=ident)) == real_pass
            del Pi
            t1 = time.time()
            for k in range(ns):
                src = setup_src(D["nact"], rng, check=(k == 0))
                flat = (base + src.reshape(V * Yn, Nn)).ravel()          # [v, y, i] <- [v, y, src[v, y, i]]
                P = tuple(np.take(a.reshape(-1), flat).reshape(V, Yn, Nn) for a in D["cal"])
                if k == 0:
                    vi = np.arange(V)[:, None, None]; yi = np.arange(Yn)[None, :, None]
                    assert all(np.array_equal(p, a[vi, yi, src]) for p, a in zip(P, D["cal"]))
                if k == 0:                     # every year keeps its results (the multiset over setups is unchanged)
                    assert np.array_equal(np.sort(P[4], axis=2), np.sort(nbcal, axis=2))
                    assert np.array_equal(np.sort(P[2], axis=2), np.sort(minpf_y, axis=2))
                    assert np.array_equal(np.sort(P[3], axis=2), np.sort(ccal, axis=2))
                f = flags(walk(D, list(range(D["Y"])), cal_arrays=P, src=src))
                r_tf["setup_pass_idx"].append([v for v in range(V) if f[v]])
                del P, src
            t2 = time.time()
            for k in range(no):
                order = [int(x) for x in rng.permutation(D["Y"] - 1)] + [D["Y"] - 1]
                f = flags(walk(D, order))
                r_tf["order_pass_idx"].append([v for v in range(V) if f[v]])
                r_tf["orders"].append(order)
            t3 = time.time()
            s = [len(x) for x in r_tf["setup_pass_idx"]]; o = [len(x) for x in r_tf["order_pass_idx"]]
            r_tf["seconds"] = dict(load=round(t_load), setup=round(t2 - t1), order=round(t3 - t2))
            print(f"{sym} {tf}: SETUP mean passes/run {np.mean(s) if s else float('nan'):.2f} ({t2 - t1:.0f}s); "
                  f"ORDER mean passes/run {np.mean(o) if o else float('nan'):.2f} ({t3 - t2:.0f}s); "
                  f"maxrss {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB", flush=True)
        res["tfs"][tf] = r_tf
        json.dump(res, open(out_json, "w"))
        del D
    print("NULLS2_DONE", sym, flush=True)


if __name__ == "__main__":
    main()
