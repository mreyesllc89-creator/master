#!/usr/bin/env python3
"""Summary of the protocol-2 year reshuffles (nulls2.py raw files, one or more batches) -> nulls_<sym>.json (small).

Symbol-level count of run k = the passing cells of run k summed over the 8 timeframes (as audit_wf/summarize.py);
p05 / p95 = np.percentile (linear). Also with nested conditions counted as one (protocol2_decision.md, rule 3):
passing cells of one timeframe whose conditions are nested (one mask inside the other, NESTED below) form one group.
Usage: python3 summarize2.py <sym> <out_json> <raw_json> [<raw_json> ...]
"""
import json, math, sys
import numpy as np

TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
# (inner, outer): the inner condition's mask is inside the outer's by their definitions in hump_wf.conditions()
NESTED = [("adx_h1_30", "adx_h1_20"), ("adx_h4_30", "adx_h4_20"), ("atrp_ge70", "atrp_ge50"), ("pdr_ge120", "pdr_ge80"),
          ("tdr_ge70", "tdr_ge40"), ("pd_break", "pd_momentum"), ("htf_macd_both", "htf_macd_1"), ("htf_macd_both", "htf_macd_2"),
          ("vol_ge200", "vol_ge150"), ("xlzc_both", "xlzc_stoch"), ("xlzc_both", "xlzc_sweep"),
          ("hours_7_10", "not_us_open"), ("hours_10_13", "not_us_open"), ("hours_19_22", "not_us_open"),
          ("hours_7_10", "no_news_times"), ("hours_10_13", "no_news_times"), ("hours_19_22", "no_news_times"),
          ("tue_thu", "no_monday"), ("tue_thu", "no_friday")]


def log_binom_pmf(i, n, p):
    if p <= 0.0:
        return 0.0 if i == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if i == n else -math.inf
    return math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)


def tail_ge(k, n, p):
    return sum(math.exp(log_binom_pmf(i, n, p)) for i in range(k, n + 1))


def cp(k, n, a=0.05):
    """Clopper-Pearson interval of k successes in n."""
    def bis(f, target):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else bis(lambda p: tail_ge(k, n, p), a / 2)                    # P(X >= k) increases with p
    upper = 1.0 if k == n else bis(lambda p: -(1.0 - tail_ge(k + 1, n, p)), -a / 2)      # P(X <= k) decreases with p
    return [lower, upper]


def groups(idx, keys):
    """Number of groups of passing cells (one timeframe) when nested conditions count as one."""
    names = [keys[v] for v in idx]
    parent = {c: c for c in names}

    def find(c):
        while parent[c] != c:
            c = parent[c]
        return c
    for a, b in NESTED:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    return len({find(c) for c in names})


def stats(tot, real):
    tot = np.asarray(tot)
    k = int((tot >= real).sum())
    return dict(mean=float(tot.mean()), p05=float(np.percentile(tot, 5)), p95=float(np.percentile(tot, 95)),
                max=int(tot.max()), dist=np.bincount(tot).tolist(), runs_at_least_real=k,
                share_at_least_real=k / len(tot), share_at_least_real_ci95=cp(k, len(tot)))


def main():
    sym, out_json = sys.argv[1], sys.argv[2]
    raws = [a for a in sys.argv[3:] if not a.startswith("--")]
    diag = next((a.split("=", 1)[1] for a in sys.argv[3:] if a.startswith("--diag=")), None)
    R = [json.load(open(f)) for f in raws]
    assert all(r["symbol"] == sym for r in R) and len({r["batch"] for r in R}) == len(R), "one file per batch"
    for r in R:
        assert sorted(r["tfs"]) == sorted(TFS), (r["batch"], sorted(r["tfs"]))
    keys = R[0]["tfs"]["M1"]["keys"]
    ver = dict(cells=0, flag_mismatches=0, cells_exact=0, window_checks=0, window_mismatches=0, by_tf={})
    real_cells, real_nested = [], 0
    for tf in TFS:
        t = R[0]["tfs"][tf]
        assert t["keys"] == keys and all(r["tfs"][tf]["real_pass_idx"] == t["real_pass_idx"] for r in R)
        v = t["verify"]
        for k in ("cells", "flag_mismatches", "cells_exact", "window_checks", "window_mismatches"):
            ver[k] += v[k]
        ver["by_tf"][tf] = dict(cells=v["cells"], flag_mismatches=v["flag_mismatches"], cells_exact=v["cells_exact"],
                                window_mismatches=v["window_mismatches"])
        real_cells += [f"{tf} {keys[i]}" for i in t["real_pass_idx"]]
        real_nested += groups(t["real_pass_idx"], keys)
    real = len(real_cells)
    ref = json.load(open(R[0]["evaluation"]))
    ref_cells = [f"{r['tf']} {r['condition']}" for r in ref["rows"] if r["passes"]]
    assert sorted(ref_cells) == sorted(real_cells) and len(ref["rows"]) == ver["cells"]
    out = dict(symbol=sym.upper(), evaluation=R[0]["evaluation"], work=R[0]["work"], script=R[0]["script"],
               raw_files=raws, batches=[r["batch"] for r in R], block=R[0]["block"], seed=R[0]["seed"], seed_note=R[0]["seed_note"],
               rules=R[0]["rules"], nested_as_one_pairs=NESTED,
               verification=ver, real=dict(passes=real, cells=real_cells, passes_nested_as_one=real_nested,
                                           evaluation_json_passes=len(ref_cells)))
    for kind in ("setup", "order"):
        per_tf = {tf: [x for r in R for x in r["tfs"][tf][f"{kind}_pass_idx"]] for tf in TFS}
        n = {len(v) for v in per_tf.values()}
        assert len(n) == 1, f"{kind}: every timeframe must have the same number of runs"
        runs = n.pop()
        if not runs:
            continue
        tot = [sum(len(per_tf[tf][k]) for tf in TFS) for k in range(runs)]
        tot_n = [sum(groups(per_tf[tf][k], keys) for tf in TFS) for k in range(runs)]
        freq = {}
        for tf in TFS:
            for k in range(runs):
                for i in per_tf[tf][k]:
                    freq[f"{tf} {keys[i]}"] = freq.get(f"{tf} {keys[i]}", 0) + 1
        cellshare = {}
        for c in real_cells:
            m = freq.get(c, 0)
            cellshare[c] = dict(runs_passing=m, share=m / runs, ci95=cp(m, runs))
        top = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:12]
        out[kind] = dict(runs=runs, **stats(tot, real), nested_as_one=stats(tot_n, real_nested),
                         mean_passes_by_tf={tf: float(np.mean([len(x) for x in per_tf[tf]])) for tf in TFS},
                         real_cells_pass_share=cellshare, most_frequent_cells=[[c, m / runs] for c, m in top],
                         distinct_cells_ever_passing=len(freq),
                         pass_idx_by_tf={tf: [[int(i) for i in x] for x in per_tf[tf]] for tf in TFS})
    if diag:                                   # diag2.py: trade volume of each reshuffle; supplementary TESTONLY reshuffle
        G = json.load(open(diag))
        assert G["symbol"] == sym and sorted(G["tfs"]) == sorted(TFS)
        vol = {}
        for kind in ("real", "setup", "order", "testonly"):
            rows = [G["tfs"][tf][kind] for tf in TFS]
            vol[kind] = dict(runs=rows[0]["runs"], cells_with_100_trades=sum(r["cells_with_100_trades"] for r in rows),
                             cells_with_2_full_years=sum(r["cells_with_2_full_years"] for r in rows),
                             mean_trades_per_cell=float(np.mean([r["mean_trades_per_cell"] for r in rows])),
                             windows_with_picks_per_cell=float(np.mean([r["windows_with_picks_per_cell"] for r in rows])),
                             passes_per_run=sum(r["passes_per_run"] for r in rows),
                             by_tf={tf: dict(trades_per_cell=round(G["tfs"][tf][kind]["mean_trades_per_cell"], 1),
                                             cells_with_100_trades=G["tfs"][tf][kind]["cells_with_100_trades"]) for tf in TFS})
        out["volume_by_reshuffle"] = dict(note="per run, summed over the 8 timeframes (472 cells); a pass needs >= 100 trades "
                                               "and two unseen years with 50+", file=diag, seed=G["seed"], **vol)
        per_tf = {tf: G["tfs"][tf]["testonly"]["pass_idx"] for tf in TFS}
        runs = len(per_tf["M1"])
        assert all(len(x) == runs for x in per_tf.values())
        tot = [sum(len(per_tf[tf][k]) for tf in TFS) for k in range(runs)]
        tot_n = [sum(groups(per_tf[tf][k], keys) for tf in TFS) for k in range(runs)]
        freq = {}
        for tf in TFS:
            for x in per_tf[tf]:
                for i in x:
                    freq[f"{tf} {keys[i]}"] = freq.get(f"{tf} {keys[i]}", 0) + 1
        out["testonly_supplementary"] = dict(
            what="not the pre-registered null: the real picks of every window kept; only the test-year results of each pick "
                 "replaced by those of a random setup in its activity block of 40 (same condition and test year)",
            runs=runs, **stats(tot, real), nested_as_one=stats(tot_n, real_nested),
            real_cells_pass_share={c: dict(runs_passing=freq.get(c, 0), share=freq.get(c, 0) / runs, ci95=cp(freq.get(c, 0), runs))
                                   for c in real_cells},
            most_frequent_cells=[[c, m / runs] for c, m in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:12]],
            pass_idx_by_tf=per_tf)
    s = out.get("setup")
    if s:
        cell_ok = {c: v["share"] < 0.05 for c, v in s["real_cells_pass_share"].items()}
        out["decision_rule_3_setup"] = dict(
            cell_share_below_5pct=cell_ok, real_count=real, setup_p95=s["p95"], real_count_above_p95=bool(real > s["p95"]),
            real_count_nested_as_one=real_nested, setup_p95_nested_as_one=s["nested_as_one"]["p95"],
            real_count_above_p95_nested_as_one=bool(real_nested > s["nested_as_one"]["p95"]),
            met={c: bool(ok and real > s["p95"]) for c, ok in cell_ok.items()})
    hl = dict(real_passes=real, real_cells=real_cells,
              reproduction=f"{ver['cells'] - ver['flag_mismatches']}/{ver['cells']} pass flags; {ver['cells_exact']}/{ver['cells']} cells and "
                           f"{ver['window_checks'] - ver['window_mismatches']}/{ver['window_checks']} windows identical to {R[0]['evaluation']}")
    for kind in ("setup", "order", "testonly_supplementary"):
        if kind in out:
            x = out[kind]
            hl[kind] = dict(runs=x["runs"], mean_passes_per_run=x["mean"], p05=x["p05"], p95=x["p95"],
                            share_runs_at_least_real=x["share_at_least_real"], share_ci95=[round(a, 4) for a in x["share_at_least_real_ci95"]],
                            real_cells_pass_share={c: v["share"] for c, v in x["real_cells_pass_share"].items()})
    if "decision_rule_3_setup" in out:
        hl["decision_rule_3_setup"] = out["decision_rule_3_setup"]["met"]
    out = dict(headline=hl, **out)
    json.dump(out, open(out_json, "w"), indent=None, separators=(",", ":"))
    show = {k: v for k, v in out.items() if k not in ("rules", "nested_as_one_pairs")}
    for kind in ("setup", "order", "testonly_supplementary"):
        if kind in show:
            show[kind] = {k: v for k, v in show[kind].items() if k != "pass_idx_by_tf"}
    print(json.dumps(show, indent=1)[:7000])


if __name__ == "__main__":
    main()
