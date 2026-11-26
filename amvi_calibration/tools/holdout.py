"""Hold-out tests on a sweep: is there anything in the search that carries from one part of
the window to another, or is the best row just the luckiest of thousands?

usage: python holdout.py <chart_tf_minutes> [sweeps_dir]

All scores are net R (gross - fee x fee units - funding) of calendar months inside the search
window. Rules (the same idea as rule v3.1 of the earlier AMVI record):

  transfer H1 -> H2   take the 40 best rows by first-half net R (distinct entry sets, enough
                      trades in the first half); their mean second-half net R must be positive,
                      above the 95th percentile of the mean of 40 random eligible rows, and
                      stay positive in 95% of resamples of the second half's months (the 40
                      as one equal-weight basket), so that it is not the work of a few months;
  transfer H2 -> H1   the same the other way round;
  walk-forward        the 40 best of the first two thirds, scored on the last third, with the
                      same three conditions;
  candidates          rows positive in both halves at the base fee AND at the stressed fee,
                      ranked by the steadiness of their worse half (plateau.py picks among them).

Rows are ranked by steadiness (the t-statistic of their monthly net R) rather than by raw
net R, which favours rows that live on a few huge trades; the raw-R ranking is shown too.
"""
import glob
import json
import os
import sys

import numpy as np

BASE_FEE = 0.0005
STRESS_FEE = 0.0010
TOP_K = 40
N_DRAWS = 20000


def load(sweeps_dir, chart_tf):
    files = sorted(glob.glob(os.path.join(sweeps_dir, f"sweep_{chart_tf}m_seed*.npz")))
    if not files:
        raise SystemExit(f"no sweep files for {chart_tf}m in {sweeps_dir}")
    parts, settings = [], []
    for f in files:
        z = np.load(f)
        parts.append({k: z[k] for k in z.files})
        settings += json.load(open(f[:-4] + ".json"))["settings"]
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    return out, settings


def net_months(d, fee=BASE_FEE, funding=True):
    x = d["gross"].astype(np.float64) - fee * d["feeu"]
    return x - d["fund"] if funding else x


def split_masks(n_months):
    h = n_months // 2
    t = n_months // 3
    m = np.arange(n_months)
    return dict(h1=m < h, h2=m >= h, t1=m < t, t2=(m >= t) & (m < 2 * t), t3=m >= 2 * t, t12=m < 2 * t)


def distinct_top(order, hashes, k):
    """First k rows of `order` with distinct entry sets."""
    seen, out = set(), []
    for i in order:
        h = int(hashes[i])
        if h in seen:
            continue
        seen.add(h)
        out.append(int(i))
        if len(out) == k:
            break
    return np.array(out, dtype=np.int64)


def transfer(train, test, eligible, hashes, rng, test_months=None, k=TOP_K, draws=N_DRAWS):
    """Best-k by `train` scored on `test`, against random k-row draws from the eligible rows.
    test_months (rows x months of the scored part): the best-k as an equal-weight basket, its
    months resampled with replacement -> share of resamples with a positive total."""
    idx = np.nonzero(eligible)[0]
    if idx.size < 4 * k:
        return None
    order = idx[np.argsort(-train[idx], kind="stable")]
    top = distinct_top(order, hashes, k)
    # one representative per entry set for the random draws
    _, first = np.unique(hashes[idx], return_index=True)
    pool = idx[np.sort(first)]
    if pool.size < 2 * k or top.size < k:
        return None
    null = np.empty(draws)
    vals = test[pool]
    for j in range(draws):
        null[j] = vals[rng.choice(pool.size, k, replace=False)].mean()
    top_mean = float(test[top].mean())
    boot = None
    if test_months is not None:
        basket = test_months[top].mean(0)
        m = basket.size
        sums = basket[rng.integers(0, m, size=(draws, m))].sum(1)
        boot = float((sums > 0).mean())
    return dict(top_mean=top_mean, top_pos=float((test[top] > 0).mean()), top_train_mean=float(train[top].mean()),
                null_mean=float(null.mean()), null_p95=float(np.percentile(null, 95)), p=float((null >= top_mean).mean()),
                boot_pos=boot, pool=int(pool.size), top=top.tolist())


def month_t(x):
    """t-statistic of the monthly net R (mean / standard deviation x sqrt(months)): high for
    rows that earn steadily, low for rows that live on one lucky month."""
    m = x.shape[1]
    sd = x.std(1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(sd > 0, x.mean(1) / sd * np.sqrt(m), 0.0)
    return t


def analyse(d, settings, min_trades_half=30, seed=12345):
    rng = np.random.default_rng(seed)
    nm = d["gross"].shape[1]
    M = split_masks(nm)
    net = net_months(d)
    net_s = net_months(d, STRESS_FEE)
    cnt = d["cnt"]
    seg = {k: net[:, m].sum(1) for k, m in M.items()}
    seg_s = {k: net_s[:, m].sum(1) for k, m in M.items()}
    n_seg = {k: cnt[:, m].sum(1) for k, m in M.items()}
    tst = {k: month_t(net[:, m]) for k, m in M.items()}
    active = {k: (cnt[:, m] > 0).mean(1) for k, m in M.items()}   # share of months with a trade
    h = d["h"]
    res = dict(rows=int(net.shape[0]), months=int(nm))

    def elig(train, test):
        return (n_seg[train] >= min_trades_half) & (active[train] >= 0.6) & (n_seg[test] >= 1)

    # primary ranking: steadiness (monthly t-statistic); secondary: plain net R
    for tag, rank in (("", tst), ("_byR", seg)):
        res["h1_to_h2" + tag] = transfer(rank["h1"], seg["h2"], elig("h1", "h2"), h, rng, net[:, M["h2"]])
        res["h2_to_h1" + tag] = transfer(rank["h2"], seg["h1"], elig("h2", "h1"), h, rng, net[:, M["h1"]])
        res["walk_forward" + tag] = transfer(rank["t12"], seg["t3"], elig("t12", "t3"), h, rng, net[:, M["t3"]])
    both = elig("h1", "h2") & elig("h2", "h1")
    total = net.sum(1)
    res["eligible_rows"] = int(both.sum())
    res["share_positive_total"] = float((total[both] > 0).mean()) if both.any() else 0.0
    res["share_positive_both_halves"] = float(((seg["h1"] > 0) & (seg["h2"] > 0))[both].mean()) if both.any() else 0.0
    res["median_total"] = float(np.median(total[both])) if both.any() else 0.0
    res["gross_share_positive"] = float((d["gross"].sum(1)[both] > 0).mean()) if both.any() else 0.0
    cand = both & (seg["h1"] > 0) & (seg["h2"] > 0) & (seg_s["h1"] > 0) & (seg_s["h2"] > 0)
    worst_t = np.minimum(tst["h1"], tst["h2"])
    order = np.nonzero(cand)[0]
    order = order[np.argsort(-worst_t[order], kind="stable")]
    top = distinct_top(order, h, 25)
    res["n_candidates"] = int(cand.sum())
    res["candidates"] = [dict(row=int(i), h1=float(seg["h1"][i]), h2=float(seg["h2"][i]), total=float(total[i]),
                              t_h1=float(tst["h1"][i]), t_h2=float(tst["h2"][i]),
                              stress_total=float(net_s[i].sum()), n=int(d["n"][i]), dd=float(d["dd"][i]),
                              t3=float(seg["t3"][i]), months_pos=float((net[i][cnt[i] > 0] > 0).mean()) if (cnt[i] > 0).any() else 0.0,
                              setting=settings[i]) for i in top]

    def ok(t):
        # positive, above the random draws, and not carried by a few months
        return bool(t and t["top_mean"] > 0 and t["top_mean"] > t["null_p95"] and t["boot_pos"] is not None and t["boot_pos"] >= 0.95)
    for tag in ("", "_byR"):
        res["pass_h1_to_h2" + tag] = ok(res["h1_to_h2" + tag])
        res["pass_h2_to_h1" + tag] = ok(res["h2_to_h1" + tag])
        res["pass_walk_forward" + tag] = ok(res["walk_forward" + tag])
    res["pass_transfer"] = res["pass_h1_to_h2"] and res["pass_h2_to_h1"]
    return res


def fmt_transfer(name, t, by_r=False):
    if not t:
        return f"  {name}: not enough rows"
    b = "" if t.get("boot_pos") is None else f"; months resampled: positive in {t['boot_pos'] * 100:.0f}% of draws"
    had = f"they had {t['top_train_mean']:+.1f}R where chosen" if by_r else f"their steadiness t was {t['top_train_mean']:.1f} where chosen"
    return (f"  {name}: best-40 mean on the scored part {t['top_mean']:+.1f}R ({t['top_pos'] * 100:.0f}% positive; {had}); "
            f"random 40: mean {t['null_mean']:+.1f}R, p95 {t['null_p95']:+.1f}R{b}")


if __name__ == "__main__":
    ctf = int(sys.argv[1])
    sdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "sweeps")
    d, settings = load(sdir, ctf)
    r = analyse(d, settings)
    print(f"chart {ctf}m: {r['rows']} rows, {r['eligible_rows']} with enough trades in both halves, {r['months']} months")
    print(f"  before costs {r['gross_share_positive'] * 100:.0f}% of rows are positive; after fees and funding {r['share_positive_total'] * 100:.0f}% "
          f"(median {r['median_total']:+.1f}R); positive in both halves {r['share_positive_both_halves'] * 100:.1f}%")
    for tag, name in (("", "ranked by steadiness"), ("_byR", "ranked by net R")):
        print(f" {name}:")
        by_r = tag == "_byR"
        print(fmt_transfer("first half -> second half", r["h1_to_h2" + tag], by_r), "PASS" if r["pass_h1_to_h2" + tag] else "fail")
        print(fmt_transfer("second half -> first half", r["h2_to_h1" + tag], by_r), "PASS" if r["pass_h2_to_h1" + tag] else "fail")
        print(fmt_transfer("walk-forward (2/3 -> last 1/3)", r["walk_forward" + tag], by_r), "PASS" if r["pass_walk_forward" + tag] else "fail")
    print(f"  candidates positive in both halves at base and stressed fee: {r['n_candidates']}")
    for c in r["candidates"][:8]:
        s = c["setting"]
        print(f"    row {c['row']}: halves {c['h1']:+.1f} / {c['h2']:+.1f}R (t {c['t_h1']:.1f} / {c['t_h2']:.1f}), total {c['total']:+.1f}R (stress {c['stress_total']:+.1f}R), {c['n']} trades, DD {c['dd']:.1f}R | "
              f"tfs {s['tfs']} conf {s['conf']} high {s['high']} f_tf {s['f_tf']} band {s['band']} inv {s['inverted']} sl {s['sl']} tp {s['tp']} trail {s['trail']} max_bars {s['max_bars']} wait {s['wait']}")
    out = os.path.join(sdir, "..", f"holdout_{ctf}m.json")
    json.dump(r, open(out, "w"))
