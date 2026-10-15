"""Independent broker comparison (secondary; no setting is chosen here). Broker candles stay outside the repository;
only aggregate numbers are written.
1. Clock check: which offset maps the broker's server clock to UTC (5-minute return correlation with Bitstamp, per month).
2. Same frozen settings, same periods (2024H2, 2025H1, 2025H2; 2024-01-08 .. 2024-06 = warm-up), same horizons, on
   (a) broker candles and (b) Bitstamp re-stamped to the New-York-close server clock; labels purged at each period end;
   paired 48-hour block bootstrap of the AUC difference vs the native default (500 repeats, blocks shared across H).
3. Zone agreement between the two data sources for the same setting.
Usage: python wf_broker.py <broker_csv> <run real|dry>"""
import sys, os, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import wf_common as W

path, run = sys.argv[1], sys.argv[2]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
READ = "mt5"
B = 500
SEED = 20261012
if run == "dry":
    PERIODS = [("2024-01-08..2024-06 (dry)", "2024-03-01", "2024-07-01")]
else:
    PERIODS = [("2024H2", "2024-07-01", "2025-01-01"), ("2025H1", "2025-01-01", "2025-07-01"), ("2025H2", "2025-07-01", "2026-01-01")]

BK = W.load_broker(path)
BS = W.load("server")
BU = pd.read_parquet("btc_1m_long.parquet")

# ---- 1. clock check
bk5 = BK.bars(5)
b = pd.Series(bk5["c"], index=pd.to_datetime(bk5["t_open"], unit="s", utc=True))
u5 = BU["close"].resample("5min", label="left", closed="left").last()
rows = []
rb = np.log(b).diff()
for name, off in [("UTC+0", 0), ("UTC+1", 1), ("UTC+2", 2), ("UTC+3", 3), ("UTC+4", 4)]:
    s = u5.copy(); s.index = s.index + pd.Timedelta(hours=off)
    ru = np.log(s).diff()
    j = pd.concat([rb.rename("b"), ru.rename("u"), b.rename("pb"), s.rename("pu")], axis=1).dropna()
    for mth, gdf in j.groupby(j.index.strftime("%Y-%m")):
        rows.append(dict(offset=name, month=mth, n=len(gdf), ret_corr=gdf.b.corr(gdf.u),
                         med_abs_pct_diff=float((gdf.pb / gdf.pu - 1).abs().median() * 100)))
# the New-York-close rule (UTC+2 / UTC+3 with US DST)
bs5 = BS.bars(5)
s = pd.Series(bs5["c"], index=pd.to_datetime(bs5["t_open"], unit="s", utc=True))
ru = np.log(s).diff()
j = pd.concat([rb.rename("b"), ru.rename("u"), b.rename("pb"), s.rename("pu")], axis=1).dropna()
for mth, gdf in j.groupby(j.index.strftime("%Y-%m")):
    rows.append(dict(offset="NY+7 (UTC+2/+3, US DST)", month=mth, n=len(gdf), ret_corr=gdf.b.corr(gdf.u),
                     med_abs_pct_diff=float((gdf.pb / gdf.pu - 1).abs().median() * 100)))
clock = pd.DataFrame(rows)
best = clock.loc[clock[~clock.offset.str.startswith("NY")].groupby("month").ret_corr.idxmax()][["month", "offset", "ret_corr"]]
clock.to_csv(f"{OUT}/broker_clock_{run}.csv", index=False, float_format="%.5f")
best.to_csv(f"{OUT}/broker_clock_best_{run}.csv", index=False, float_format="%.5f")
print(best.to_string())

# ---- 2. settings to compare (frozen picks come from the primary walk-forward run, written before this script runs)
def parse(tf, d, kind):
    return dict(parent=int(d["parent"]), zones=tuple(int(x) for x in str(d["zones"]).split("/")), ma=int(d["min_aligned"]),
                use_zones=bool(d["use_zones"]), kind=kind)


SETS = {}
for tf in W.FILTER_TFS:
    SETS[tf] = list(W.baselines(tf))
    fj = f"{OUT}/wf_final_{tf}_utc_{READ}_real.json"
    if run != "dry" and os.path.exists(fj):
        fin = json.load(open(fj))
        for k in ("R1_greedy", "R2_conservative"):
            SETS[tf].append(parse(tf, fin[k], f"frozen_{k}"))
SETS[120].append(dict(parent=120, zones=(480, 720, 1440), ma=1, use_zones=True, kind="codex_candidate_H2"))
SETS[60].append(dict(parent=120, zones=(30, 60, 1440), ma=2, use_zones=True, kind="codex_candidate_H1"))


# added after the review: the walk-forward fold pick whose test block is the period (chosen on 2020-01 .. the month
# before it, purged), i.e. the out-of-sample comparison for that period; the final picks saw 2024H2 and 2025H1
def fold_sets(tf, pname):
    out = []
    ff, fc = f"{OUT}/wf_folds_{tf}_utc_{READ}_real.csv", f"{OUT}/cands_{tf}_utc_{READ}_real_all.csv"
    if run == "dry" or not os.path.exists(ff):
        return out
    folds, cands = pd.read_csv(ff), pd.read_csv(fc)
    for k in ("R1_greedy", "R2_conservative"):
        x = folds[(folds.fold == pname) & (folds.method == k)]
        if len(x):
            c = cands.iloc[int(x.cid.iloc[0])]
            out.append(dict(parent=int(c.parent), zones=tuple(int(v) for v in str(c.zones).split("/")), ma=int(c.ma),
                            use_zones=bool(c.use_zones), kind=f"wf_fold_{k}"))
    return out


def sample_status(kind, pname):
    if kind.startswith("wf_fold_"):
        return "out-of-sample (fold pick)"
    if kind.startswith("frozen_") or kind.startswith("codex_"):
        return "out-of-sample" if pname == "2025H2" else "in selection window"
    return "baseline"


def evaluate(S, tf, r, p0, p1):
    z, g, ctx = W.zone_of(S, tf, r, READ)
    ch = S.bars(tf)
    t = ch["t_open"]; c = ch["c"]; N = len(c)
    out = {}
    blocks = None
    for H in W.HS:
        fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
        tH = np.full(N, np.iinfo(np.int64).max); tH[:-H] = t[H:]
        m = (t >= p0) & (t < p1) & (tH < p1) & ~np.isnan(fwd) & (fwd != 0)
        y = (fwd[m] > 0).astype(int); zz = z[m].astype(int) + 1
        blk = (t[m] - p0) // 172800
        out[H] = (zz, y, blk, t[m])
    return out, z, t


def acc_of(T):
    """raw accuracy from (..., zone, label) counts: share right among BUY / SELL zone candles"""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (T[..., 2, 1] + T[..., 0, 0]) / (T[..., 2, :].sum(-1) + T[..., 0, :].sum(-1))


def cov_of(T):
    return (T[..., 2, :].sum(-1) + T[..., 0, :].sum(-1)) / T.sum((-1, -2))


def table(zz, y, blk, nb):
    key = (blk * 3 + zz) * 2 + y
    return np.bincount(key, minlength=nb * 6).reshape(nb, 3, 2).astype(float)


res, agree = [], []
for tf in W.FILTER_TFS:
    for pname, a, bnd in PERIODS:
        p0 = int(pd.Timestamp(a, tz="UTC").timestamp()); p1 = int(pd.Timestamp(bnd, tz="UTC").timestamp())
        nb = int((p1 - p0) // 172800) + 1
        rng = np.random.default_rng(SEED + tf)
        pick = rng.integers(0, nb, size=(B, nb))
        Wb = np.stack([np.bincount(pk, minlength=nb) for pk in pick]).astype(float)
        for src_name, S in (("broker", BK), ("bitstamp_server_clock", BS)):
            tabs = {}
            zones_by = {}
            sets_here = SETS[tf] + fold_sets(tf, pname)
            for r in sets_here:
                ev, z, t = evaluate(S, tf, r, p0, p1)
                tabs[r["kind"]] = {H: table(*ev[H][:3], nb) for H in W.HS}
                zones_by[r["kind"]] = (z, t)
            ref = tabs["native_default"]
            ref_boot = np.nanmean([W.auc_table(*(lambda T: (T[..., 1], T[..., 0]))(np.einsum("bk,kzy->bzy", Wb, ref[H]))) for H in W.HS], axis=0)
            ref_acc = np.nanmean([acc_of(np.einsum("bk,kzy->bzy", Wb, ref[H])) for H in W.HS], axis=0)
            ref_acc_pt = float(np.nanmean([acc_of(ref[H].sum(0)) for H in W.HS]))
            ref_cov_pt = float(np.nanmean([cov_of(ref[H].sum(0)) for H in W.HS]))
            for r in sets_here:
                T = tabs[r["kind"]]
                row = dict(tf=W.NAMES[tf], period=pname, source=src_name, kind=r["kind"], setting=W.label(r),
                           sample=sample_status(r["kind"], pname))
                for H in W.HS:
                    pm = W.perm_metrics(T[H].sum(0)[:, 1], T[H].sum(0)[:, 0])
                    for k2, v in pm.items():
                        row[f"{k2}_H{H}"] = v
                for k2 in ("auc", "acc", "bal_acc", "coverage"):
                    row[f"{k2}_mean"] = float(np.nanmean([row[f"{k2}_H{H}"] for H in W.HS]))
                bo = np.nanmean([W.auc_table(*(lambda TT: (TT[..., 1], TT[..., 0]))(np.einsum("bk,kzy->bzy", Wb, T[H]))) for H in W.HS], axis=0)
                d = bo - ref_boot
                row["auc_mean_ci_lo"], row["auc_mean_ci_hi"] = np.nanpercentile(bo, [2.5, 97.5])
                row["diff_vs_native_default"] = row["auc_mean"] - float(np.nanmean([W.auc_table(ref[H].sum(0)[:, 1], ref[H].sum(0)[:, 0]) for H in W.HS]))
                row["diff_ci_lo"], row["diff_ci_hi"] = np.nanpercentile(d, [2.5, 97.5])
                row["bal_recall_mean"] = float(np.nanmean([row[f"bal_recall_H{H}"] for H in W.HS]))
                ab = np.nanmean([acc_of(np.einsum("bk,kzy->bzy", Wb, T[H])) for H in W.HS], axis=0)
                row["acc_diff_vs_native_default"] = row["acc_mean"] - ref_acc_pt
                row["acc_diff_ci_lo"], row["acc_diff_ci_hi"] = np.nanpercentile(ab - ref_acc, [2.5, 97.5])
                row["coverage_diff_vs_native_default"] = row["coverage_mean"] - ref_cov_pt
                res.append(row)
            if src_name == "broker":
                zb = zones_by
            else:
                for k in zb:
                    z1, t1 = zb[k]; z2, t2 = zones_by[k]
                    m1 = (t1 >= p0) & (t1 < p1); m2 = (t2 >= p0) & (t2 < p1)
                    s1 = pd.Series(z1[m1], index=t1[m1]); s2 = pd.Series(z2[m2], index=t2[m2])
                    jj = pd.concat([s1.rename("b"), s2.rename("s")], axis=1).dropna()
                    agree.append(dict(tf=W.NAMES[tf], period=pname, kind=k, n_common=len(jj), n_broker=int(m1.sum()), n_bitstamp=int(m2.sum()),
                                      same_zone_share=float((jj.b == jj.s).mean()) if len(jj) else np.nan,
                                      opposite_zone_share=float((jj.b * jj.s == -1).mean()) if len(jj) else np.nan))
    print("broker done", tf, flush=True)
pd.DataFrame(res).to_csv(f"{OUT}/broker_eval_{run}.csv", index=False, float_format="%.5f")
pd.DataFrame(agree).to_csv(f"{OUT}/broker_zone_agreement_{run}.csv", index=False, float_format="%.5f")
print("done broker", run)
