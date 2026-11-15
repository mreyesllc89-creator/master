"""Expected chance passes (controls, placebo cells, year reshuffles) and stricter readings of the pass rule.
Usage: python3 summarize.py <sym> <mine_json> <placebo_dir> <nulls_json> <out_json>"""
import glob, json, math, os, sys
import numpy as np

sym, mine_json, pl_dir, nulls_json, out_json = sys.argv[1:6]
mine = json.load(open(mine_json))["rows"]
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]


def pf1(w, l):
    return w / l if l > 0 else (math.inf if w > 0 else math.nan)


def rule(wins, year_n=50, min_full=2, pass_n=100, pass_pf=1.3, pass_stress=1.1, floor=1.0, every_year=False, thin_floor_n=None, min_full_frac=None):
    n = sum(w["n"] for w in wins); win = sum(w["win"] for w in wins); loss = sum(w["loss"] for w in wins)
    sw = sum(w["stress_win"] for w in wins); sl = sum(w["stress_loss"] for w in wins)
    full = [w for w in wins if w["n"] >= year_n]
    need = max(min_full, math.ceil(min_full_frac * len(wins))) if min_full_frac else min_full
    ok = n >= pass_n and pf1(win, loss) >= pass_pf and pf1(sw, sl) >= pass_stress and len(full) >= need and all(w["pf"] >= floor for w in full)
    if every_year:
        ok = ok and all(w["n"] > 0 for w in wins)
    if thin_floor_n is not None:
        ok = ok and all(w["pf"] >= floor for w in wins if w["n"] >= thin_floor_n)
    return bool(ok)


RULES = {
    "as written": {},
    "3+ unseen years with 50+ trades": dict(min_full=3),
    "half of the unseen years with 50+ trades": dict(min_full_frac=0.5),
    "trades in every unseen year": dict(every_year=True),
    "no unseen year with 20+ trades below PF 1.0": dict(thin_floor_n=20),
    "stress PF >= 1.3": dict(pass_stress=1.3),
    "300+ trades": dict(pass_n=300),
    "combined: trades every year, half the years 50+, no 20+ year below 1.0": dict(every_year=True, min_full_frac=0.5, thin_floor_n=20),
}


def _tail_ge(k, n, p):                       # P(X >= k), X ~ Binomial(n, p), terms in log space
    if p <= 0.0:
        return 1.0 if k <= 0 else 0.0
    if p >= 1.0:
        return 1.0
    lp, lq = math.log(p), math.log1p(-p)
    lg = math.lgamma(n + 1)
    return sum(math.exp(lg - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq) for i in range(max(k, 0), n + 1))


def _bisect(f, target, lo=0.0, hi=1.0):
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp(k, n, a=0.05):
    """Clopper-Pearson interval of a binomial proportion (exact, by bisection on the tails)."""
    lo = 0.0 if k == 0 else _bisect(lambda p: _tail_ge(k, n, p), a / 2)                  # P(X >= k | lo) = a/2
    hi = 1.0 if k == n else _bisect(lambda p: -(1 - _tail_ge(k + 1, n, p)), -a / 2)    # P(X <= k | hi) = a/2
    return float(lo), float(hi)


out = dict(sym=sym)
real = [r for r in mine]
ctrl = [r for r in real if r["condition"].startswith("random_")]
noctl = [r for r in real if not r["condition"].startswith("random_")]
out["cells"] = len(real); out["tfs"] = sorted({r["tf"] for r in real}, key=TFS.index)
out["real_passes"] = [(r["tf"], r["condition"], round(r["pf"], 3), r["n"]) for r in real if r["passes"]]
out["control_cells"] = len(ctrl); out["control_passes"] = [(r["tf"], r["condition"]) for r in ctrl if r["passes"]]
k = len(out["control_passes"]); n = len(ctrl)
out["controls_rate"] = (k / n if n else None, cp(k, n) if n else None)
out["expected_false_from_controls"] = dict(point=k / n * len(real) if n else None, ci95=[x * len(real) for x in cp(k, n)] if n else None)

# placebo cells
pl = []; realx = {}; nob = {}
for f in sorted(glob.glob(os.path.join(pl_dir, f"eval_{sym}_*_placebo.json"))):
    e = json.load(open(f))
    for r in e["placebo"]:
        pl.append(dict(tf=e["tf"], **r))
    nob[e["tf"]] = {k: v for k, v in e["noboundary"].items() if k != "changed"}
    nob[e["tf"]]["changed_sample"] = e["noboundary"]["changed"][:10]
kp = sum(r["passes"] for r in pl); npl = len(pl)
out["placebo_cells"] = npl
out["placebo_tfs"] = sorted({r["tf"] for r in pl}, key=TFS.index)
out["placebo_passes"] = [(r["tf"], r["name"], round(r["pf"], 3), r["n"]) for r in pl if r["passes"]]
out["placebo_rate"] = (kp / npl if npl else None, cp(kp, npl) if npl else None)
by_kind = {}
for r in pl:
    kind = r["name"].split(":")[0].rstrip("01")
    a = by_kind.setdefault(kind, [0, 0]); a[0] += r["passes"]; a[1] += 1
out["placebo_by_kind"] = by_kind
by_tf = {}
for r in pl:
    a = by_tf.setdefault(r["tf"], [0, 0]); a[0] += r["passes"]; a[1] += 1
out["placebo_by_tf"] = by_tf
if npl:
    out["expected_false_from_placebo"] = dict(point=kp / npl * len(real), ci95=[x * len(real) for x in cp(kp, npl)])
    # the same, timeframe by timeframe where a placebo exists (real cells of that timeframe x its placebo rate)
    e_tf = 0.0; cover = 0
    for tf, (a, b) in by_tf.items():
        m = sum(1 for r in real if r["tf"] == tf); e_tf += a / b * m; cover += m
    out["expected_false_from_placebo_tf_matched"] = dict(point_on_covered_cells=e_tf, covered_cells=cover)
out["noboundary"] = nob

# year reshuffles
nfiles = [f for f in nulls_json.split(",") if os.path.exists(f)]
if nfiles:
    nu = dict(tfs={})
    for f in nfiles:                                   # several files: their timeframes are merged
        for tf, r in json.load(open(f))["tfs"].items():
            assert tf not in nu["tfs"], f"timeframe {tf} twice"
            nu["tfs"][tf] = r
    for kind in ("setup", "order"):
        tot = None; cells = 0; tfs = []
        for tf, r in nu["tfs"].items():
            a = np.array(r[kind], bool)
            if not len(a):
                continue
            assert tot is None or len(a) == len(tot), "every timeframe must have the same number of permutations"
            tot = a.sum(axis=1) if tot is None else tot + a.sum(axis=1)
            cells += a.shape[1]; tfs.append(tf)
        if tot is not None:
            out[f"reshuffle_{kind}"] = dict(perms=int(len(tot)), cells=cells, tfs=tfs, mean_passes=float(tot.mean()), p05=float(np.percentile(tot, 5)),
                                            p95=float(np.percentile(tot, 95)), max=int(tot.max()), dist=np.bincount(tot).tolist())
        # how often each real passing cell passes again
        freq = {}
        for tf, r in nu["tfs"].items():
            a = np.array(r[kind], bool)
            for v, key in enumerate(r["keys"]):
                if r["real_pass"][v] and len(a):
                    freq[f"{tf}:{key}"] = float(a[:, v].mean())
        out[f"reshuffle_{kind}_pass_rate_of_real_passes"] = freq

# stricter readings, real and placebo
sr = {}
for name, kw in RULES.items():
    rp = [(r["tf"], r["condition"]) for r in real if rule(r["by_year"], **kw)]
    pp = sum(rule(r["by_year"], **kw) for r in pl)
    cpp = sum(rule(r["by_year"], **kw) for r in ctrl)
    sr[name] = dict(real=len(rp), real_cells=rp, controls=cpp, placebo=pp, placebo_cells=npl,
                    expected_false_placebo=(pp / npl * len(real)) if npl else None)
out["stricter"] = sr
# thin evidence of the real passes
th = []
for r in real:
    if r["passes"]:
        wins = r["by_year"]
        th.append(dict(tf=r["tf"], condition=r["condition"], n=r["n"], pf=r["pf"], stress_pf=r["stress_pf"],
                       years=[(w["year"], len(w["picks"]), w["n"], round(w["pf"], 3) if w["n"] else None) for w in wins],
                       years_with_picks=sum(1 for w in wins if w["picks"]), full_years=r["years_with_50_trades"],
                       final=dict(n=r["final"]["n"], pf=r["final"]["pf"], stress_pf=r["final"]["stress_pf"], picks=r["final"]["picks"])))
out["passes_detail"] = th
# distribution of thin passes in the placebo: years with trades among placebo passes
out["placebo_pass_years_with_trades"] = [sum(1 for w in r["by_year"] if w["n"] > 0) for r in pl if r["passes"]]
out["placebo_pass_full_years"] = [r["years_with_50_trades"] for r in pl if r["passes"]]
json.dump(out, open(out_json, "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in out.items() if k not in ("noboundary",)}, indent=1, default=float)[:6000])
