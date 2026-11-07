"""Validation analyses on an EVK run.

All choices of a "best" pass use only the training data of each test, so the
out-of-sample numbers are honest: the pass was chosen before its test period.
"""
import numpy as np
import pandas as pd

from .metrics import pf, score, stats, max_drawdown


def _split_edges(start, end, k):
    return [start + (end - start) * i / k for i in range(k)] + [end + pd.Timedelta(seconds=1)]


def pass_table(run, value, split, is_periods=2):
    """Per-pass statistics: whole run, in-sample (before split), out-of-sample, IS sub-periods."""
    t = run.trades
    v = run.value_col(value)
    if t.empty:
        empty = {f"all_{k}": val for k, val in stats([]).items()}
        if split is not None:
            empty.update({f"is_{k}": val for k, val in stats([]).items()})
            empty.update({f"oos_{k}": val for k, val in stats([]).items()})
        empty.update(is_period_trades_min=0, is_period_pf_min=np.nan)
        return pd.DataFrame([dict(empty, **{"pass": p}) for p in run.passes.index]).set_index("pass").join(run.passes)
    start, end = t.close_time.min(), t.close_time.max()
    split = pd.Timestamp(split) if split is not None else None
    is_end = split if split is not None else end + pd.Timedelta(seconds=1)
    edges = _split_edges(start, is_end - pd.Timedelta(seconds=1), is_periods)
    rows = []
    groups = dict(tuple(t.groupby("pass")))
    for p in run.passes.index:
        g = groups.get(p)
        x = g[v].to_numpy(float) if g is not None else np.array([])
        ct = g.close_time.to_numpy() if g is not None else np.array([], "datetime64[ns]")
        row = {"pass": p}
        for k, val in stats(x).items():
            row[f"all_{k}"] = val
        if split is not None:
            m = ct < np.datetime64(split)
            for k, val in stats(x[m]).items():
                row[f"is_{k}"] = val
            for k, val in stats(x[~m]).items():
                row[f"oos_{k}"] = val
        ism = ct < np.datetime64(is_end)
        per = []
        for a, b in zip(edges[:-1], edges[1:]):
            mm = ism & (ct >= np.datetime64(a)) & (ct < np.datetime64(b))
            per.append((int(mm.sum()), pf(x[mm]) if mm.any() else np.nan))
        row["is_period_trades_min"] = min(n for n, _ in per)
        row["is_period_pf_min"] = min((q for _, q in per), default=np.nan) if all(n > 0 for n, _ in per) else np.nan
        rows.append(row)
    tab = pd.DataFrame(rows).set_index("pass")
    return tab.join(run.passes)


def neighbours(run, tab, metric):
    """For each pass: median of `metric` over itself and its grid neighbours (one optimized
    input moved one step), and the share of that neighbourhood above 1. Inputs that are not
    numeric are matched exactly."""
    params = run.varying
    if not params:
        return pd.DataFrame({"nb_median": tab[metric], "nb_share_gt1": (tab[metric] > 1).astype(float), "nb_n": 1},
                            index=tab.index)
    strtab = tab[params].astype(str)
    numtab = tab[params].apply(pd.to_numeric, errors="coerce")
    numeric = {c: bool(numtab[c].notna().all()) for c in params}
    # sorted grid of each numeric input, with the original string form of each value
    grid = {}
    for c in params:
        if numeric[c]:
            pairs = sorted({(float(v), sv) for v, sv in zip(numtab[c], strtab[c])})
            grid[c] = [sv for _, sv in pairs]
    keys = list(strtab.itertuples(index=False, name=None))
    lookup = dict(zip(keys, tab.index))
    med, share, cnt = [], [], []
    for p, key in zip(tab.index, keys):
        vals = [tab.at[p, metric]]
        for ci, c in enumerate(params):
            if not numeric[c]:
                continue
            g = grid[c]
            i = g.index(key[ci])
            for j in (i - 1, i + 1):
                if 0 <= j < len(g):
                    nb = list(key)
                    nb[ci] = g[j]
                    q = lookup.get(tuple(nb))
                    if q is not None:
                        vals.append(tab.at[q, metric])
        arr = np.array(vals, float)
        arr = arr[np.isfinite(arr)]
        med.append(np.median(arr) if len(arr) else np.nan)
        share.append((arr > 1).mean() if len(arr) else np.nan)
        cnt.append(len(vals))
    return pd.DataFrame({"nb_median": med, "nb_share_gt1": share, "nb_n": cnt}, index=tab.index)


def holdout(run, value, split, criterion="min_period_pf", min_trades=30, is_periods=2, smooth=True):
    """Choose on data before `split`, measure after it. Reports the top-k picks' out-of-sample
    results against the base rate (all passes)."""
    tab = pass_table(run, value, split, is_periods)
    v = run.value_col(value)
    t = run.trades
    groups = dict(tuple(t[t.close_time < pd.Timestamp(split)].groupby("pass")))
    start = t.close_time.min()
    edges = _split_edges(start, pd.Timestamp(split) - pd.Timedelta(seconds=1), is_periods)
    sc = {}
    for p in tab.index:
        g = groups.get(p)
        if g is None:
            sc[p] = -np.inf
            continue
        sc[p] = score(g.close_time.to_numpy(), g[v].to_numpy(float), criterion, min_trades,
                      np.array(edges, "datetime64[ns]"))
    tab["is_score"] = pd.Series(sc)
    tab["is_score_finite"] = tab.is_score.replace(-np.inf, np.nan)
    if smooth:
        nb = neighbours(run, tab, "is_score_finite")
        tab = tab.join(nb)
        tab["rank_score"] = tab.nb_median.where(np.isfinite(tab.is_score), -np.inf)
    else:
        tab["rank_score"] = tab.is_score
    ranked = tab[np.isfinite(tab.rank_score)].sort_values("rank_score", ascending=False)
    # same rules for the picks and the base rate: every rankable pass counts, a pass with
    # no out-of-sample trade counts as "not profitable", medians ignore passes without trades
    base = ranked
    topk = []
    for k in (1, 5, 10, 25, 50):
        top = ranked.head(k)
        if len(top) < k and k > 1:
            break
        topk.append(dict(k=k, oos_pf_median=float(top.oos_pf.dropna().median()) if top.oos_pf.notna().any() else np.nan,
                         oos_profitable=float((top.oos_pf.fillna(0) > 1).mean()),
                         oos_trades_median=float(top.oos_trades.median()), is_score_median=float(top.is_score.median())))
    return dict(table=tab, ranked=ranked, topk=topk,
                base_rate=float((base.oos_pf.fillna(0) > 1).mean()) if len(base) else np.nan,
                base_median=float(base.oos_pf.dropna().median()) if base.oos_pf.notna().any() else np.nan,
                chosen=ranked.index[0] if len(ranked) else None, criterion=criterion, smooth=smooth,
                split=str(pd.Timestamp(split).date()), min_trades=min_trades)


def walkforward(run, value, train_months=6, test_months=2, criterion="min_period_pf", min_trades=20,
                is_periods=2, smooth=True, anchored=False):
    """Rolling (or anchored) walk-forward: choose on each training window, trade the next test
    window, stitch all test windows into one out-of-sample record."""
    t = run.trades
    v = run.value_col(value)
    start = t.close_time.min().normalize().replace(day=1)
    end = t.close_time.max()
    windows = []
    test_start = start + pd.DateOffset(months=train_months)
    while test_start < end:
        test_end = test_start + pd.DateOffset(months=test_months)
        train_start = start if anchored else test_start - pd.DateOffset(months=train_months)
        windows.append((train_start, test_start, test_end))
        test_start = test_end
    if not windows:
        return dict(windows=[], oos=stats([]), oos_trades=pd.DataFrame())
    rows, oos_parts = [], []
    for a, b, c in windows:
        sub_t = t[(t.close_time >= a) & (t.close_time < b)]
        groups = dict(tuple(sub_t.groupby("pass")))
        edges = np.array(_split_edges(a, b - pd.Timedelta(seconds=1), is_periods), "datetime64[ns]")
        sc = pd.Series({p: (score(g.close_time.to_numpy(), g[v].to_numpy(float), criterion, min_trades, edges)
                            if (g := groups.get(p)) is not None else -np.inf) for p in run.passes.index})
        if smooth:
            tab = run.passes.copy()
            tab["s"] = sc.replace(-np.inf, np.nan)
            nb = neighbours(run, tab, "s")
            rank = nb.nb_median.where(np.isfinite(sc), -np.inf)
        else:
            rank = sc
        rank = rank[np.isfinite(rank)]
        if rank.empty:
            rows.append(dict(train=f"{a.date()}..{b.date()}", test=f"{b.date()}..{c.date()}", chosen=None))
            continue
        p = rank.idxmax()
        tr = t[(t["pass"] == p) & (t.close_time >= a) & (t.close_time < b)]
        te = t[(t["pass"] == p) & (t.close_time >= b) & (t.close_time < c)]
        oos_parts.append(te)
        si, so = stats(tr[v]), stats(te[v])
        rows.append(dict(train=f"{a.date()}..{(b - pd.Timedelta(days=1)).date()}",
                         test=f"{b.date()}..{(c - pd.Timedelta(days=1)).date()}", chosen=run.label(p), pass_id=p,
                         is_trades=si["trades"], is_pf=si["pf"], oos_trades=so["trades"], oos_pf=so["pf"],
                         oos_net=so["net"]))
    oos = pd.concat(oos_parts) if oos_parts else t.iloc[0:0]
    return dict(windows=rows, oos=stats(oos[v]), oos_trades=oos, train_months=train_months,
                test_months=test_months, anchored=anchored, criterion=criterion, smooth=smooth,
                distinct_picks=len({r.get("pass_id") for r in rows if r.get("chosen")}))


def stress(x, times=None, n_sims=2000, seed=7):
    """Stress tests on one trade list (R or money)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    rng = np.random.default_rng(seed)
    out = {}
    if len(x) == 0:
        return out
    avg_loss = -x[x < 0].mean() if (x < 0).any() else (np.abs(x).mean() or 1.0)
    # extra cost per trade, as a fraction of the average loss (spread/slippage/commission)
    out["cost"] = [dict(cost=f"{int(c * 100)}% of avg loss", pf=pf(x - c * avg_loss), net=float((x - c * avg_loss).sum()))
                   for c in (0.0, 0.05, 0.10, 0.20)]
    # remove the best trades (luck concentration)
    srt = np.sort(x)[::-1]
    out["drop_best"] = [dict(removed=k, pf=pf(srt[k:]), net=float(srt[k:].sum())) for k in (0, 1, 3, 5) if k < len(x)]
    # Monte Carlo: reshuffle trade order -> drawdown distribution
    dds = [max_drawdown(rng.permutation(x)) for _ in range(n_sims)]
    out["mc_drawdown"] = dict(p50=float(np.percentile(dds, 50)), p95=float(np.percentile(dds, 95)),
                              p99=float(np.percentile(dds, 99)), actual=max_drawdown(x))
    # bootstrap PF (iid trades) - conditional on this pass, ignores how it was chosen
    pfs = []
    for _ in range(n_sims):
        s = rng.choice(x, len(x))
        pfs.append(pf(s))
    pfs = np.array(pfs, float)
    out["bootstrap_pf"] = dict(p5=float(np.nanpercentile(pfs, 5)), p50=float(np.nanpercentile(pfs, 50)),
                               p95=float(np.nanpercentile(pfs, 95)), p_below_1=float(np.nanmean(pfs < 1)))
    return out


def compare(run_a, run_b, value, label_a="A", label_b="B", min_trades=15):
    """Pair passes of two runs with identical optimized inputs (e.g. a filter off vs on) and
    report how often B beats A."""
    va, vb = run_a.value_col(value), run_b.value_col(value)
    if set(run_a.varying) != set(run_b.varying):
        raise ValueError("the two runs optimized different inputs: "
                         f"{sorted(c[2:] for c in run_a.varying)} vs {sorted(c[2:] for c in run_b.varying)}")
    ta = pass_table(run_a, value, None)
    tb = pass_table(run_b, value, None)

    def keys(tab):
        cols = []
        for c in run_a.varying:          # optimized inputs identify the twin pass
            num = pd.to_numeric(tab[c], errors="coerce")
            cols.append(num.round(10).astype(str) if num.notna().all() else tab[c].astype(str))
        return list(zip(*cols)) if cols else [()] * len(tab)
    a = ta.assign(key=keys(ta)).set_index("key")
    b = tb.assign(key=keys(tb)).set_index("key")
    if not (a.index.is_unique and b.index.is_unique):
        raise ValueError("passes are not unique by their optimized inputs; cannot pair them")
    j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
    ok = j[(j.all_trades_a >= min_trades) & (j.all_trades_b >= min_trades)]
    res = dict(label_a=label_a, label_b=label_b, matched=int(len(j)), used=int(len(ok)),
               inputs=[c[2:] for c in run_a.varying])
    if len(ok):
        res.update(pf_a=float(ok.all_pf_a.median()), pf_b=float(ok.all_pf_b.median()),
                   share_pf_up=float((ok.all_pf_b > ok.all_pf_a).mean()),
                   share_net_up=float((ok.all_net_b > ok.all_net_a).mean()),
                   trades_kept=float((ok.all_trades_b / ok.all_trades_a).median()),
                   net_a=float(ok.all_net_a.median()), net_b=float(ok.all_net_b.median()))
    res["pairs"] = ok
    res["unit"] = "R" if va == "r" and vb == "r" else "money"
    return res
