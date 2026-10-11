"""Calibration v2 for one chart timeframe: features -> entry-filter grid -> exit / re-entry grid on 1-minute
intrabar paths -> preset. Selection uses the in-sample period only (2023-01 .. 2025-06): the modal value of each
setting among the 60 best sets (a plateau, not a peak), drawn from the sets with every in-sample year positive when
at least 60 qualify, else from all sets with enough trades. The out-of-sample period (2025-07 .. 2026-10) is only
reported."""
import sys, json, time, itertools, os
import numpy as np
import pandas as pd
import fgengine as E
import fgrun as R
from calib import zones_for, IS_END
from features import build
from stage_b import grid as b_grid
from stage_c import apply_filters, FEE

OUT = os.environ.get("CAL_OUT", "results3")
NMIN_B = {1: 2000, 5: 800, 15: 400, 30: 300, 60: 200, 120: 150, 240: 120, 480: 80, 1440: 60}
NMIN_C = {1: 2000, 5: 800, 15: 300, 30: 250, 60: 120, 120: 100, 240: 60, 480: 50, 1440: 30}
KEYS_B = ['pm', 'ma', 'fm', 'parent', 'bmin', 'smax', 'smin', 'bmax', 'burst', 'hurst', 'areg', 'pbmin', 'psmax']
KEYS_C = ['sl', 'tpr', 'act', 'dst', 'rm', 'rmax', 'xopp', 'xbrk']
YEARS = (2023, 2024, 2025)


def year_of(ts):
    return pd.to_datetime(ts, unit="s", utc=True).year


def b_years(F, B):
    """min over the in-sample years of the mean forward move, per entry-filter set (recomputed from masks)."""
    return B


def stage_f(tf, S):
    out = []
    for pm in (1, 4, 8):
        for ma in (1, 2):
            for fm in (1, 4):
                df = build(tf, S, pm=pm, ma=ma, fd_mult=fm)
                df["pm"] = pm; df["ma"] = ma; df["fm"] = fm
                out.append(df)
    F = pd.concat(out, ignore_index=True)
    F.to_parquet(f"{OUT}/F_{tf}.parquet")
    return F


def stage_b(tf, F):
    F = F.copy()
    F["year"] = F.t.dt.year
    rows = []
    # grid() returns per-set IS/OOS stats; add per-year IS means by re-running the masks per year
    for y in YEARS:
        Fy = F[F["is"] & (F.year == y)].copy()
        By = b_grid(Fy.assign(**{"is": True}), min_is=8)
        By = By[KEYS_B + ["is_n", "is_f20"]].rename(columns={"is_n": f"n_{y}", "is_f20": f"f20_{y}"})
        rows.append(By)
    B = b_grid(F)
    for By in rows:
        B = B.merge(By, on=KEYS_B, how="left")
    yc = [f"f20_{y}" for y in YEARS]
    B["is_y_min"] = B[yc].min(axis=1, skipna=False)
    B["tf"] = tf
    B.to_parquet(f"{OUT}/B_{tf}.parquet")
    return B


def select_entry(tf, B, top_n=60):
    Bn = B[(B.is_n >= NMIN_B[tf]) & (B.is_y_min > 0)]
    if len(Bn) < top_n:
        Bn = B[B.is_n >= NMIN_B[tf]]
    top = Bn.sort_values("is_t", ascending=False).head(top_n)
    cfg = {k: top[k].mode().iloc[0] for k in KEYS_B}
    entry = dict(pm=int(cfg["pm"]), ma=int(cfg["ma"]), fm=int(cfg["fm"]), zk=0)
    filt = dict(parent=int(cfg["parent"]), bmin=float(cfg["bmin"]), smax=float(cfg["smax"]), smin=float(cfg["smin"]),
                bmax=float(cfg["bmax"]), burst=float(cfg["burst"]), hurst=int(cfg["hurst"]), areg=float(cfg["areg"]),
                pbmin=float(cfg["pbmin"]), psmax=float(cfg["psmax"]))
    m = np.ones(len(B), bool)
    for k in KEYS_B:
        m &= (B[k] == cfg[k]).to_numpy()
    row = B[m].iloc[0].to_dict() if m.any() else {}
    return entry, filt, row


def trade_metrics(tr, atr_e, t_e):
    split = int(IS_END.timestamp())
    x = tr.pnl.to_numpy() / atr_e
    yr = pd.to_datetime(t_e, unit="s", utc=True).year.to_numpy()
    is_ = t_e < split
    r = {}
    for name, m in (("is", is_), ("oos", ~is_)):
        v = x[m]
        n = len(v)
        r[name + "_n"] = n
        r[name + "_mean"] = v.mean() if n else np.nan
        r[name + "_t"] = v.mean() / v.std() * np.sqrt(n) if n > 2 and v.std() > 0 else np.nan
        g = v[v > 0].sum(); l = -v[v <= 0].sum()
        r[name + "_pf"] = g / l if l > 0 else np.nan
        eq = np.cumsum(v) if n else np.zeros(1)
        r[name + "_dd"] = float((np.maximum.accumulate(eq) - eq).max()) if n else np.nan
        r[name + "_win"] = (v > 0).mean() if n else np.nan
        r[name + "_sum"] = v.sum()
    ys = []
    for y in YEARS:
        v = x[is_ & (yr == y)]
        r[f"sum_{y}"] = v.sum()
        ys.append(v.sum() if len(v) else np.nan)
    r["is_y_min"] = np.nanmin(ys) if not all(np.isnan(ys)) else np.nan
    return r


def base_params(tf, entry, filt):
    return R.params(parent_tf=tf * entry["pm"], zones=zones_for(tf, entry.get("zk", 0)), min_aligned=entry["ma"],
                    burst_atr=max(0.5, float(filt.get("burst", 0.5))), fd_tf=tf * entry.get("fm", 1), fd_trade=bool(filt.get("parent", 0)),
                    fd_div_on=False, fd_pull_on=False, fd_hurst_on=False, exit_mode="ATR", fee_pct=FEE, slip_ticks=0.0)


def stage_c(tf, S, entry, filt, mag_on):
    p0 = base_params(tf, entry, filt)
    ctx = apply_filters(R.context(S, tf, p0), S, tf, p0, filt)
    mag = S.bars(1) if mag_on else None
    rows = []
    G = list(itertools.product((1.0, 1.5, 2.0, 3.0), (0.0, 4.0, 8.0), (1.0, 2.0, 4.0, 0.0), (0.5, 1.0, 2.0),
                               ((0, 0), (1, 2), (1, 5), (2, 2), (2, 5)), (False, True), (False, True)))
    t0 = time.time()
    for i, (sl, tpr, act, dst, (rm, rmax), xopp, xbrk) in enumerate(G):
        if act == 0.0 and dst != 1.0:
            continue
        p = dict(p0)
        p.update(sl_atr=sl, tp_r=tpr, trail_act_atr=act, trail_dst_atr=dst, use_trail=act > 0, re_mode=rm, re_max=rmax,
                 exit_opp=xopp, fd_exit_break=xbrk, fd_on=True, re_dist_atr=0.25, use_mag=mag_on)
        tr = R.run(S, tf, p, ctx, mag=mag)
        if len(tr) < 3:
            continue
        eb = tr.ebar.to_numpy()
        r = dict(sl=sl, tpr=tpr, act=act, dst=dst, rm=rm, rmax=rmax, xopp=xopp, xbrk=xbrk)
        r.update(trade_metrics(tr, ctx["atr14"][eb], ctx["ch"]["t_open"][eb]))
        r["n_re"] = int(tr.reentry.sum())
        rows.append(r)
        if i % 500 == 0:
            print(f"[C tf={tf}] {i}/{len(G)} {time.time()-t0:.0f}s", flush=True)
    C = pd.DataFrame(rows)
    C["tf"] = tf
    C.to_parquet(f"{OUT}/C_{tf}.parquet")
    return C


def select_exits(tf, C, top_n=60):
    Cn = C[(C.is_n >= NMIN_C[tf]) & (C.is_y_min > 0)]
    if len(Cn) < top_n:
        Cn = C[C.is_n >= NMIN_C[tf]]
    top = Cn.sort_values("is_t", ascending=False).head(top_n)
    ex = pick_exits(top)
    if ex["rm"] == 0:
        ex["rmax"] = 0
    return ex


def pick_exits(top):
    """Modal value of each exit setting among the top sets; the re-entry limit is voted among the sets that use
    the chosen re-entry mode (rm = 0 rows carry rmax = 0 = 'no limit', which must not win for rm > 0)."""
    ex = {}
    for k in KEYS_C:
        if k in ("rm", "rmax"):
            continue
        v = top[k].mode().iloc[0]
        ex[k] = bool(v) if k in ("xopp", "xbrk") else float(v)
    ex["rm"] = int(top["rm"].mode().iloc[0])
    ex["rmax"] = int(top.loc[top["rm"] == ex["rm"], "rmax"].mode().iloc[0]) if ex["rm"] else 0
    if ex["act"] == 0:
        ex["dst"] = 1.0
    return ex


def evaluate(S, tf, p, filt, mag_on):
    ctx0 = R.context(S, tf, p)
    ctx = apply_filters(ctx0, S, tf, p, filt) if filt is not None else ctx0
    p = dict(p); p["use_mag"] = mag_on
    tr = R.run(S, tf, p, ctx, mag=S.bars(1) if mag_on else None)
    eb = tr.ebar.to_numpy()
    m = trade_metrics(tr, ctx["atr14"][eb], ctx["ch"]["t_open"][eb]) if len(tr) else {}
    m["n_re"] = int(tr.reentry.sum()) if len(tr) else 0
    m["reasons"] = {int(k): int(v) for k, v in tr.reason.value_counts().items()} if len(tr) else {}
    return m, tr


def finalize(tf, S, entry, filt, ex, brow, mag_on):
    p = base_params(tf, entry, filt)
    p.update(sl_atr=ex["sl"], tp_r=ex["tpr"], trail_act_atr=ex["act"], trail_dst_atr=ex["dst"], use_trail=ex["act"] > 0,
             re_mode=ex["rm"], re_max=ex["rmax"], re_dist_atr=0.25, exit_opp=ex["xopp"], fd_exit_break=ex["xbrk"], fd_on=True)
    variants = {}
    variants["preset"] = (p, filt)
    variants["preset, no re-entry"] = (dict(p, re_mode=0, re_max=0), filt)
    variants["preset + divergence gate"] = (dict(p, fd_div_on=True), filt)
    variants["preset + pullback gate 0.5"] = (dict(p, fd_pull_on=True, fd_pull_atr=0.5), filt)
    variants["preset + quality filter off"] = (p, dict(parent=filt["parent"], burst=filt["burst"]))
    pu = R.params(parent_tf=tf * 4, zones=zones_for(tf, 0), min_aligned=2, burst_atr=0.5, fd_tf=tf, fee_pct=FEE, exit_mode="Points")
    variants["your settings (FDF PDF gates, Points 5000/50000/4500/1000)"] = (pu, None)
    variants["your settings, ATR exits 2/2R/4/0.2"] = (dict(pu, exit_mode="ATR"), None)
    res = {}
    for name, (pp, ff) in variants.items():
        m, _ = evaluate(S, tf, pp, ff, mag_on)
        res[name] = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in m.items()}
    sig = {k: (float(brow[k]) if k in brow and pd.notna(brow[k]) else None)
           for k in ("is_n", "is_p1", "is_p2", "is_f20", "is_t", "is_y_min", "oos_n", "oos_p1", "oos_f20", "oos_t")}
    return dict(entry=entry, filter=filt, exits=ex, signal=sig, results=res, mag=mag_on)


if __name__ == "__main__":
    tf = int(sys.argv[1])
    t0 = time.time()
    base = pd.read_parquet("btc_1m.parquet")
    S = R.Source(base, 1)
    mag_on = tf > 1
    F = pd.read_parquet(f"{OUT}/F_{tf}.parquet") if os.path.exists(f"{OUT}/F_{tf}.parquet") else stage_f(tf, S)
    print(f"[{tf}] F {len(F)} rows {time.time()-t0:.0f}s", flush=True)
    if tf == 1:
        import stage_b as SB
        SB.set_reduced(True)
        F = F[F.pm.isin([1, 4]) & (F.ma == 2)]
    B = pd.read_parquet(f"{OUT}/B_{tf}.parquet") if os.path.exists(f"{OUT}/B_{tf}.parquet") else stage_b(tf, F)
    print(f"[{tf}] B {len(B)} rows {time.time()-t0:.0f}s", flush=True)
    entry, filt, brow = select_entry(tf, B)
    print(f"[{tf}] entry {entry} {filt}", flush=True)
    C = stage_c(tf, S, entry, filt, mag_on)
    print(f"[{tf}] C {len(C)} rows {time.time()-t0:.0f}s", flush=True)
    ex = select_exits(tf, C)
    print(f"[{tf}] exits {ex}", flush=True)
    res = finalize(tf, S, entry, filt, ex, brow, mag_on)
    json.dump(res, open(f"{OUT}/preset_{tf}.json", "w"), indent=1, default=str)
    print(f"[{tf}] done {time.time()-t0:.0f}s", flush=True)
