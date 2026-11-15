#!/usr/bin/env python3
"""Independent check of hump_wf cells (protocol 2), walk-forward years only: nothing about the final year is read
or computed (the loop stops before it; the passing cell had no 2026 picks anyway).

For every window of a cell:
  picks       hump_wf.window_pick on the condition's slice of the stored array (read with mmap_mode='r'), compared
              with the picks of the stored evaluation (wf json);
  trades      hump_wf.trades_of for every pick at both cost levels, filtered to the test year by entry time (and, for
              the last test year, to the trades whose exit bar is in that year, by the exit bar's timestamp);
  test sums   count, gross win R, gross loss R, cost R of those trades against the stored columns 0-3 (4-7 for the last
              test year), every pick and both costs; the year totals against the stored evaluation;
  calibration the same four sums of every pick on its three calibration years (only trades that close in the year
              they open), against stored columns 4-7, and the score recomputed from the trades.
Then the trades collapsed to distinct (entry time, side) signals, once with hump_wf.distinct_signals and once with
an independent implementation (plain dict, mean R), and the share of the profit from the largest trades.
Usage (from research/, HUMP_SYMBOL set): python3 check_cell.py <work> <wf_json> <out_json> TF:key[:detail_json] ...
"""
import gc, json, os, pickle, sys, time
sys.path.insert(0, "/workspace/master/research")
import numpy as np, pandas as pd
import hump_wf as W

work, wf_json, out_json = sys.argv[1:4]
cells = [a.split(":", 2) for a in sys.argv[4:]]
ev = json.load(open(wf_json))
assert ev["symbol"] == W.SYM and ev.get("protocol") == 2
rows = {(r["tf"], r["condition"]): r for r in ev["rows"]}
t0 = time.time()
W.MK = W.Mk(work); W.MK._work = (work, None)
print(f"{W.SYM}: market ready in {time.time() - t0:.0f}s", flush=True)


def pf(r):
    r = np.asarray(r, float)
    w, l = r[r > 0].sum(), -r[r <= 0].sum()
    return float(w / l) if l > 0 else (float("inf") if w > 0 else float("nan"))


def year_of_rows(rows_):
    return pd.DatetimeIndex(W.MK.t[np.asarray(rows_, np.int64)]).year.values


def sums4(df):
    r = df.r.values.astype(float)
    return np.array([len(df), r[r > 0].sum(), -r[r <= 0].sum(), df.cost_r.values.astype(float).sum()])


def my_distinct(base, stress):
    """Independent: group by (entry time, side) in a dict, mean R per signal."""
    def coll(df):
        acc = {}
        for t, s, y, r in zip(df.entry_time.values.astype("datetime64[ns]"), df.side.values.astype(int),
                              df.year.values.astype(int), df.r.values.astype(float)):
            a = acc.setdefault((t, s), [y, 0.0, 0])
            assert a[0] == y
            a[1] += r; a[2] += 1
        return pd.DataFrame([(k[0], k[1], a[0], a[1] / a[2], a[2]) for k, a in acc.items()],
                            columns=["t", "side", "year", "r", "picks"]).sort_values(["t", "side"]).reset_index(drop=True)
    b, s = coll(base), coll(stress)
    yrs = {}
    for y in sorted(set(b.year)):
        g = b[b.year == y]; gs = s[s.year == y]
        yrs[int(y)] = dict(trades=int((base.year == y).sum()), signals=int(len(g)), pf=pf(g.r), net_r=float(g.r.sum()),
                           stress_signals=int(len(gs)), stress_pf=pf(gs.r))
    full = [y for y in yrs if yrs[y]["signals"] >= W.YEAR_N]
    p, sp = pf(b.r), pf(s.r)
    passes = bool(len(b) >= W.PASS_N and p >= W.PASS_PF and sp >= W.PASS_STRESS and len(full) >= 2
                  and all(yrs[y]["pf"] >= 1.0 for y in full))
    return dict(signals=int(len(b)), stress_signals=int(len(s)), pf=p, stress_pf=sp, net_r=float(b.r.sum()),
                years_with_50_signals=len(full), losing_years=[y for y in full if yrs[y]["pf"] < 1.0], passes=passes,
                by_year=yrs, picks_per_signal_mean=float(b.picks.mean()) if len(b) else None,
                signals_taken_by_2plus_picks=int((b.picks >= 2).sum())), b, s


def concentration(r):
    """Share of the profit from the largest trades (or signals)."""
    r = np.sort(np.asarray(r, float))[::-1]
    net, gw = float(r.sum()), float(r[r > 0].sum())
    out = dict(n=int(len(r)), wins=int((r > 0).sum()), net_r=net, gross_win_r=gw, largest=[round(float(x), 3) for x in r[:10]])
    for k in (1, 3, 5, 10, 20):
        if k < len(r):
            out[f"top{k}"] = dict(sum_r=float(r[:k].sum()), share_of_net=float(r[:k].sum() / net) if net else None,
                                  share_of_gross_win=float(r[:k].sum() / gw) if gw else None,
                                  pf_without=pf(r[k:]), net_without=float(r[k:].sum()))
    cum = net - np.cumsum(r)
    out["remove_to_net_le_0"] = int(np.argmax(cum <= 0) + 1) if (cum <= 0).any() else None
    pfs = [pf(r[k:]) for k in range(0, min(len(r), 60))]
    out["remove_to_pf_lt_1_3"] = next((k for k, x in enumerate(pfs) if x < 1.3), None)
    out["remove_to_pf_lt_1_0"] = next((k for k, x in enumerate(pfs) if x < 1.0), None)
    return out


def check(tf, key, detail_json=None):
    t1 = time.time()
    A = np.load(os.path.join(work, f"wf_{tf}.npy"), mmap_mode="r")
    with open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb") as f:
        d = pickle.load(f)
    P, years, keys = d["params"], d["years"], d["keys"]
    assert list(keys) == W.KEYS and int(d.get("protocol", 1)) == 2
    v = keys.index(key)
    Av = np.asarray(A[:, v:v + 1], dtype=np.float64)          # [N, 1, 2, Y, 8]: this condition only
    del A
    final = len(years) - 1
    row = rows[(tf, key)]
    wf_years = {y["year"]: y for y in row["by_year"]}
    res = dict(tf=tf, condition=key, stored=dict(n=row["n"], pf=row["pf"], stress_pf=row["stress_pf"], passes=row["passes"]),
               windows=[], max_abs_diff_test=[0.0] * 4, max_abs_diff_cal=[0.0] * 4, max_score_diff=0.0, count_mismatches=0)
    base_l, stress_l = [], []
    for ty in range(3, final):                                  # the walk-forward years: never the final one
        cal = [ty - 3, ty - 2, ty - 1]
        picks, score, cost, n_ok, n_cost = W.window_pick(Av, P, 0, cal, 4)
        ref = wf_years[years[ty]]
        assert picks == ref["picks"], (tf, key, years[ty], picks, ref["picks"])
        assert (n_ok, n_cost) == (ref["eligible"], ref["eligible_after_cost_rule"])
        tc = 4 if ty == final - 1 else 0
        tot = np.zeros((2, 4)); win = []
        for i in picks:
            calc = np.zeros((2, 3, 4))
            for ci in (0, 1):
                df = W.trades_of(P[i], key, W.COSTS[ci])
                ey, xy = df.entry_time.dt.year.values, year_of_rows(df.exit_row.values)
                for k, cy in enumerate(cal):                    # calibration: trades that open and close in the year
                    calc[ci, k] = sums4(df[(ey == years[cy]) & (xy == years[cy])])
                dt = df[ey == years[ty]]
                if tc:
                    dt = dt[year_of_rows(dt.exit_row.values) == years[ty]]
                got = sums4(dt); st = Av[i, 0, ci, ty, tc:tc + 4]
                res["count_mismatches"] += int(got[0] != st[0])
                res["max_abs_diff_test"] = [max(a, float(abs(g - s))) for a, g, s in zip(res["max_abs_diff_test"], got, st)]
                tot[ci] += got
                (base_l if ci == 0 else stress_l).append(dt.assign(year=years[ty], pick=i, score=float(score[i])))
                if ci == 0:
                    win.append(dict(pick=i, score=float(score[i]), n=int(got[0]), win=float(got[1]), loss=float(got[2]), pf=pf(dt.r)))
            stc = Av[i, 0, :, cal, 4:8].transpose(1, 0, 2)       # [2 costs, 3 years, 4]
            res["count_mismatches"] += int((calc[..., 0] != stc[..., 0]).sum())
            res["max_abs_diff_cal"] = [max(a, float(np.abs(calc[..., c] - stc[..., c]).max())) for c, a in enumerate(res["max_abs_diff_cal"])]
            sc = min(pf_from(calc[ci, k]) for ci in (0, 1) for k in range(3))     # the score: lowest of six PFs
            res["max_score_diff"] = max(res["max_score_diff"], abs(sc - float(score[i])))
        diffs = dict(n=tot[0, 0] - ref["n"], win=tot[0, 1] - ref["win"], loss=tot[0, 2] - ref["loss"], cost=tot[0, 3] - ref["cost_r"],
                     stress_n=tot[1, 0] - ref["stress_n"], stress_win=tot[1, 1] - ref["stress_win"], stress_loss=tot[1, 2] - ref["stress_loss"])
        res["windows"].append(dict(year=years[ty], picks=picks, scores=[float(score[i]) for i in picks], n=int(tot[0, 0]),
                                   pf=pf_from(tot[0]), stress_n=int(tot[1, 0]), stress_pf=pf_from(tot[1]),
                                   diff_vs_stored_eval={k: float(x) for k, x in diffs.items()}, picks_detail=win))
    cols = ["year", "pick", "score", "entry_time", "side", "r", "risk", "cost_r", "entry_row", "exit_row"]
    base = pd.concat(base_l)[cols].sort_values("entry_time").reset_index(drop=True) if base_l else pd.DataFrame(columns=cols)
    stress = pd.concat(stress_l)[cols].sort_values("entry_time").reset_index(drop=True) if stress_l else pd.DataFrame(columns=cols)
    res["trades"] = dict(n=int(len(base)), pf=pf(base.r), net_r=float(base.r.sum()), stress_n=int(len(stress)), stress_pf=pf(stress.r),
                         buys=dict(n=int((base.side > 0).sum()), pf=pf(base.r[base.side > 0])),
                         sells=dict(n=int((base.side < 0).sum()), pf=pf(base.r[base.side < 0])),
                         cost_r_per_trade=float(base.cost_r.mean()) if len(base) else None)
    official = W.distinct_signals(base, stress)
    mine, b, s = my_distinct(base, stress)
    res["distinct_official"] = official
    res["distinct_independent"] = mine
    agree = (official["signals"] == mine["signals"] and official["stress_signals"] == mine["stress_signals"]
             and abs(official["pf"] - mine["pf"]) < 1e-9 and abs(official["stress_pf"] - mine["stress_pf"]) < 1e-9
             and official["years_with_50_signals"] == mine["years_with_50_signals"] and official["passes"] == mine["passes"]
             and all(official["by_year"][y]["signals"] == mine["by_year"][y]["signals"]
                     and abs(official["by_year"][y]["pf"] - mine["by_year"][y]["pf"]) < 1e-9 for y in mine["by_year"]))
    res["distinct_agree"] = bool(agree)
    res["concentration_trades"] = concentration(base.r.values)
    res["concentration_signals"] = concentration(b.r.values)
    res["resampling_trades"] = W.boot(base.entry_time.values, base.r.values.astype(float)) if len(base) > 30 else None
    res["resampling_signals"] = W.boot(b.t.values, b.r.values.astype(float)) if len(b) > 30 else None
    # hump_wf.boot bins by numpy datetime64[W], whose weeks start on Thursday (1970-01-01); +3 days gives Monday weeks
    mon = np.timedelta64(3, "D")
    res["resampling_trades_monday_weeks"] = W.boot(base.entry_time.values + mon, base.r.values.astype(float)) if len(base) > 30 else None
    res["resampling_signals_monday_weeks"] = W.boot(b.t.values + mon, b.r.values.astype(float)) if len(b) > 30 else None
    res["weeks"] = dict(thursday_bins=int(len(np.unique(base.entry_time.values.astype("datetime64[W]")))),
                        monday_bins=int(len(np.unique((base.entry_time.values + mon).astype("datetime64[W]")))))
    if row["passes"]:                                           # the passing cell: its trade lists, for the record
        res["trade_list"] = dict(base=[dict(t=str(x.entry_time), side=int(x.side), r=round(float(x.r), 6), year=int(x.year), pick=int(x.pick))
                                       for x in base.itertuples()],
                                 stress=[dict(t=str(x.entry_time), side=int(x.side), r=round(float(x.r), 6), year=int(x.year), pick=int(x.pick))
                                         for x in stress.itertuples()])
    if detail_json:                                             # the detail run's figures against these trade lists
        dj = json.load(open(detail_json))
        wfd = dj["walk_forward"]
        res["vs_detail"] = dict(
            n=wfd["n"] - len(base), pf=wfd.get("pf", np.nan) - pf(base.r), net=wfd.get("net_r", 0.0) - float(base.r.sum()),
            stress_n=wfd["stress"]["n"] - len(stress), stress_pf=wfd["stress"].get("pf", np.nan) - pf(stress.r),
            resampling_same=wfd["resampling"] == res["resampling_trades"],
            distinct_same=all(dj["distinct_signals"]["walk_forward"][k] == official[k] for k in ("signals", "stress_signals", "years_with_50_signals", "passes"))
            and abs(dj["distinct_signals"]["walk_forward"]["pf"] - official["pf"]) < 1e-12)
        # every (year, pick) of the detail: win and loss from its n, PF and net, against the stored base columns
        pk = []
        for q in dj["picks"]:
            ty = years.index(q["year"]); tc = 4 if ty == final - 1 else 0
            loss = q["net_r"] / (q["pf"] - 1.0); wn = q["pf"] * loss
            st = Av[q["pick"], 0, 0, ty, tc:tc + 3]
            pk.append(dict(year=q["year"], pick=q["pick"], n=q["n"], stored_n=float(st[0]), win=wn, stored_win=float(st[1]),
                           loss=loss, stored_loss=float(st[2])))
        res["detail_picks_vs_array"] = pk
    for k in ("distinct_official", "distinct_independent"):
        res[k]["by_year"] = {str(y): x for y, x in res[k]["by_year"].items()}
    print(f"{W.SYM} {tf} {key}: {len(base)} trades, PF {pf(base.r):.4f}, stress {pf(stress.r):.4f}; distinct {mine['signals']} "
          f"PF {mine['pf']:.4f} stress {mine['stress_pf']:.4f} y50 {mine['years_with_50_signals']} losing {mine['losing_years']} "
          f"passes {mine['passes']} (agree with hump_wf: {agree}); count mismatches {res['count_mismatches']}, max diff test "
          f"{[round(x, 6) for x in res['max_abs_diff_test']]}, cal {[round(x, 6) for x in res['max_abs_diff_cal']]}, score "
          f"{res['max_score_diff']:.2e}; {time.time() - t1:.0f}s", flush=True)
    W.MK._feat.pop(tf, None); W.MK._tf.pop(tf, None); gc.collect()
    return res


def pf_from(s):
    return float(s[1] / s[2]) if s[2] > 0 else (float("inf") if s[1] > 0 else float("nan"))


out = dict(symbol=W.SYM, work=work, wf_json=wf_json, cells=[])
for c in cells:
    out["cells"].append(check(c[0], c[1], c[2] if len(c) > 2 else None))
    json.dump(out, open(out_json, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
print("CHECK_DONE", flush=True)
