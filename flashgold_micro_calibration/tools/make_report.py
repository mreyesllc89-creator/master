"""Fill REPORT.template.md with tables and figures computed from results/*.csv -> REPORT.md.

usage: python -I make_report.py

Every number in the report comes from a result file, so the report can be regenerated after a rerun.
Placeholders in the template are {{name}}; unknown names stop the build.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RES = os.path.join(ROOT, "results")


def md(df, floats=None, align=None):
    """DataFrame -> markdown table. floats = {col: decimals}; other numbers are printed as integers."""
    floats = floats or {}
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |"]
    out.append("|" + "|".join((" ---: " if (pd.api.types.is_numeric_dtype(df[c]) or (align or {}).get(c) == "r") else " --- ") for c in cols) + "|")
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                if np.isnan(v):
                    cells.append("n/a")
                elif np.isinf(v):
                    cells.append("no losses")
                elif c in floats:
                    cells.append(f"{v:,.{floats[c]}f}")
                else:
                    cells.append(f"{v:,.0f}")
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{v:,}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def stats(pts):
    pts = np.asarray(pts, float)
    w, l = pts[pts > 0].sum(), -pts[pts < 0].sum()
    return dict(trades=len(pts), pf=w / l if l > 0 else np.inf, win=100 * (pts > 0).mean(), avg=pts.mean(), net=pts.sum())


def read(name):
    return pd.read_csv(os.path.join(RES, name))


def build():
    V = {}
    PF = {"profit factor": 2}

    # ------------------------------------------------------------------ real trades
    real = read("real/real_trades_sar.csv")
    s = stats(real.pts)
    V["real_n"] = f"{len(real):,}"
    V["real_pf"] = f"{s['pf']:.2f}"
    V["real_win"] = f"{s['win']:.0f}%"
    V["real_avg"] = f"{s['avg']:.1f}"
    V["real_net"] = f"{s['net']:,.0f}"
    V["real_usd"] = f"{-s['net'] / 100:,.2f}"
    V["real_avg_win"] = f"{real.pts[real.pts > 0].mean():.0f}"
    V["real_avg_loss"] = f"{real.pts[real.pts < 0].mean():.0f}"
    V["real_days"] = str(pd.to_datetime(real.open_time).dt.date.nunique())
    V["real_per_day"] = f"{len(real) / pd.to_datetime(real.open_time).dt.date.nunique():.0f}"
    route = np.where(real.scenario == "FOLM", "market order after follow-through (FOLM)",
                     np.where(real.scenario == "FLXQ", "stop order with the burst (FLXQ)",
                              np.where(real.scenario == "EXHL", "limit order against the burst (EXHL)", "other stop orders (CONT, BNO)")))
    rows = []
    for k in ["market order after follow-through (FOLM)", "stop order with the burst (FLXQ)", "limit order against the burst (EXHL)", "other stop orders (CONT, BNO)"]:
        g = real[route == k]
        st = stats(g.pts)
        rows.append({"entry route": k, "trades": st["trades"], "share %": 100 * len(g) / len(real), "profit factor": st["pf"], "win %": st["win"],
                     "points per trade": st["avg"], "net points": st["net"]})
    V["T_real_routes"] = md(pd.DataFrame(rows), {"profit factor": 2, "points per trade": 1})
    kind = real.exit_kind.map(lambda x: {"SL": "stop loss", "TP": "take profit", "SA_PROFIT_EXIT": "speed profit exit (SA_PROFIT_EXIT)", "other": "other"}.get(x, "defensive close (SA_...)"))
    rows = []
    for k in ["stop loss", "speed profit exit (SA_PROFIT_EXIT)", "defensive close (SA_...)", "take profit", "other"]:
        g = real[kind == k]
        rows.append({"closed by": k, "trades": len(g), "share %": 100 * len(g) / len(real), "points per trade": g.pts.mean(), "net points": g.pts.sum(),
                     "median seconds held": g.hold_s.median()})
    V["T_real_exits"] = md(pd.DataFrame(rows), {"points per trade": 1})
    rows = []
    for k, name in (("agrees", "feed agreed with the trade (FA)"), ("disagrees", "feed disagreed (FD)"), ("none", "no label")):
        st = stats(real.pts[real.flow == k])
        rows.append({"order-flow label on the entry": name, "trades": st["trades"], "profit factor": st["pf"], "win %": st["win"], "points per trade": st["avg"]})
    V["T_real_flow"] = md(pd.DataFrame(rows), {"profit factor": 2, "points per trade": 1})
    hb = pd.cut(real.hold_s, [-1, 10, 40, 1e9], labels=["closed within 10 s", "10 to 40 s", "longer than 40 s"])
    rows = []
    for k in hb.cat.categories:
        st = stats(real.pts[hb == k])
        rows.append({"time in the trade": k, "trades": st["trades"], "profit factor": st["pf"], "net points": st["net"]})
    V["T_real_hold"] = md(pd.DataFrame(rows), PF)

    # ------------------------------------------------------------------ fidelity
    f = read("fidelity_routes.csv")
    rows = []
    for route_ in f.route.unique():
        a = f[(f.route == route_) & (f.source == "real")].iloc[0]
        b = f[(f.route == route_) & (f.source == "replay")].iloc[0]
        rows.append({"route": route_, "real trades": int(a.n), "real profit factor": a.pf, "replay profit factor": b.pf, "real win %": 100 * a.win,
                     "replay win %": 100 * b.win, "real avg win / loss": f"{a.avg_win:.0f} / {a.avg_loss:.0f}",
                     "replay avg win / loss": f"{b.avg_win:.0f} / {b.avg_loss:.0f}"})
    V["T_fidelity_routes"] = md(pd.DataFrame(rows), {"real profit factor": 2, "replay profit factor": 2})
    fm = read("fidelity_exit_mix.csv")
    V["T_fidelity_mix"] = md(fm[["kind", "real", "replay"]].rename(columns={"kind": "closed by", "real": "real trades %", "replay": "replay %"}))
    rr = read("real/real_replay_variants.csv")
    b0 = rr.iloc[0]
    V["rr_n"] = f"{int(b0.sim_n)}"
    V["rr_sim_avg"] = f"{b0.sim_avg:.1f}"
    V["rr_real_avg"] = f"{b0.real_avg:.1f}"
    V["rr_sim_pf"] = f"{b0.sim_pf:.2f}"
    V["rr_real_pf"] = f"{b0.real_pf:.2f}"
    V["T_real_replay"] = md(rr[["name", "sim_pf", "sim_avg"]].rename(columns={"name": "exit inputs applied to the real entries", "sim_pf": "profit factor",
                                                                             "sim_avg": "points per trade"}), {"profit factor": 2, "points per trade": 1})
    log = open(os.path.join(RES, "real", "real_replay.log")).read()
    m = re.search(r"points correlation ([\d.]+), same sign ([\d.]+), \|difference\| <= 15 points ([\d.]+)", log)
    V["rr_corr"], V["rr_sign"], V["rr_close"] = m.group(1), f"{100 * float(m.group(2)):.0f}%", f"{100 * float(m.group(3)):.0f}%"

    # ------------------------------------------------------------------ baseline
    bs = read("baseline_summary.csv")
    bs["preset"] = bs.preset.str.replace("FlashGold_", "")
    t = bs[["preset", "case", "n", "pf", "pf_is", "pf_val", "pf_test", "avg"]].rename(columns={
        "case": "execution", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026", "avg": "points per trade"})
    V["T_baseline"] = md(t, {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1})
    ref = bs[(bs.preset == "NativeReference") & (bs.case == "real fills")].iloc[0]
    V["ref_pf"] = f"{ref.pf:.2f}"
    V["ref_n"] = f"{int(ref.n):,}"
    V["ref_avg"] = f"{ref.avg:.1f}"
    bm = read("baseline_by_month.csv")
    g = bm[(bm.preset == "FlashGold_NativeReference") & (bm.case == "real fills")]
    V["T_baseline_month"] = md(g[["month", "n", "pf", "win", "avg", "net"]].assign(win=lambda d: 100 * d.win).rename(columns={
        "n": "trades", "pf": "profit factor", "win": "win %", "avg": "points per trade", "net": "net points"}), {"profit factor": 2, "points per trade": 1})
    gm = g[g.month != "ALL"]
    V["ref_month_min"] = f"{gm.pf.min():.2f}"
    V["ref_month_max"] = f"{gm.pf.max():.2f}"
    for name, key in (("FlashGold_Micro1s", "micro1s"), ("FlashGold_Micro250ms", "micro250"), ("FlashGold_1s_Expiry5seconds", "exp5s"), ("FlashGold_1s_Expiry250ms", "exp250")):
        a = bs[(bs.preset == name.replace("FlashGold_", "")) & (bs.case == "real fills")].iloc[0]
        b = bs[(bs.preset == name.replace("FlashGold_", "")) & (bs.case.str.contains("capacity block"))].iloc[0]
        V[f"{key}_pf"] = f"{a.pf:.2f}"
        V[f"{key}_n"] = f"{int(a.n):,}"
        V[f"{key}_literal_n"] = f"{int(b.n):,}"
    sd = bs[bs.preset == "source code defaults"].iloc[0]
    V["src_pf"], V["src_n"] = f"{sd.pf:.2f}", f"{int(sd.n):,}"
    st_ = bs[(bs.preset == "NativeReference") & (bs.case == "strict fills")].iloc[0]
    V["ref_strict_pf"] = f"{st_.pf:.2f}"
    nf = bs[(bs.preset == "NativeReference") & (bs.case.str.contains("filter off"))].iloc[0]
    V["ref_nofg_pf"], V["ref_nofg_n"] = f"{nf.pf:.2f}", f"{int(nf.n):,}"

    # ------------------------------------------------------------------ forward path
    fd = read("forward_drift.csv")
    t = fd[fd.h_s <= 600][["h_s", "mid_drift_FLXQ", "net_if_closed_FLXQ", "mid_drift_EXHL", "net_if_closed_EXHL"]].rename(columns={
        "h_s": "seconds after the fill", "mid_drift_FLXQ": "stop entries: mid-price move", "net_if_closed_FLXQ": "stop entries: result if closed then",
        "mid_drift_EXHL": "limit fades: mid-price move", "net_if_closed_EXHL": "limit fades: result if closed then"})
    V["T_forward"] = md(t, {c: 1 for c in t.columns if c != "seconds after the fill"})
    V["fwd_best"] = f"{fd[fd.h_s <= 300].mid_drift_FLXQ.max():.0f}"
    V["fwd_cost"] = f"{fd.cost.iloc[0]:.0f}"
    V["fwd_spread"] = f"{fd.spread_paid.iloc[0]:.0f}"
    V["fwd_slip"] = f"{fd.entry_slip.iloc[0]:.0f}"

    # ------------------------------------------------------------------ one input at a time
    o = read("oat_native_all.csv")
    base = o[o.is_base].iloc[0]
    V["oat_n_inputs"] = str(o.input.nunique())
    V["oat_n_runs"] = f"{len(o):,}"
    ob = o[(o.n >= 2000) & ~o.input.str.startswith("X_")]
    g = ob.groupby("input").agg(lo=("pf", "min"), hi=("pf", "max"))
    g["span"] = g.hi - g.lo
    V["oat_max"] = f"{g.hi.max():.2f}"
    V["oat_min"] = f"{g.lo.min():.2f}"
    top = g.sort_values("span", ascending=False).head(14)
    rows = []
    for name, r in top.iterrows():
        k = ob[ob.input == name]
        best = k.loc[k.pf.idxmax()]
        rows.append({"input": name, "shipped": f"{float(o[(o.input == name) & o.is_base].value.iloc[0]):g}" if ((o.input == name) & o.is_base).any() else "",
                     "values tested": ", ".join(f"{v:g}" for v in k.value), "lowest": r.lo, "highest": r.hi, "best value": f"{best.value:g}",
                     "best: Nov-Feb / Mar-May / Oct-Nov": f"{best.pf_is:.2f} / {best.pf_val:.2f} / {best.pf_test:.2f}"})
    V["T_oat_top"] = md(pd.DataFrame(rows), {"lowest": 2, "highest": 2})
    span_all = o.groupby("input").pf.agg(lambda x: x.max() - x.min())
    V["oat_dead"] = ", ".join(f"`{k}`" for k in span_all[span_all < 0.0005].index)
    gate = o[o.input == "X_ExitGatePips"]
    V["gate0_pf"] = f"{gate[gate.value == 0].pf.iloc[0]:.2f}"

    # ------------------------------------------------------------------ trailing on the shipped entries
    tr = read("study_trailing.csv")
    V["trail_base_pf"] = f"{tr.iloc[0].pf:.2f}"
    a = tr[(tr.tag == "simple") & (tr.TrailStepPoints == 10)]
    piv = a.pivot_table(index="TrailStartPoints", columns="TrailBehindPoints", values="pf")
    piv.index = [f"start {int(i)}" for i in piv.index]
    piv.columns = [f"behind {int(c)}" for c in piv.columns]
    V["T_trail_simple"] = md(piv.reset_index().rename(columns={"index": "TrailStartPoints / TrailBehindPoints"}), {c: 2 for c in piv.columns})
    V["trail_simple_best"] = f"{a.pf.max():.2f}"
    V["trail_simple_worst"] = f"{a.pf.min():.2f}"
    b = tr[tr.tag == "simple+settle"]
    V["trail_settle_lo"], V["trail_settle_hi"] = f"{b.pf.min():.2f}", f"{b.pf.max():.2f}"
    c = tr[tr.tag == "layer"].copy()
    c["distance"] = (c.internalMinTrailing * np.maximum(c.InpReferenceSpreadPts, 12)).round(0)
    V["T_trail_layer"] = md(c.sort_values("distance")[["InpReferenceSpreadPts", "internalMinTrailing", "distance", "pf", "win", "avg"]].assign(win=lambda d: 100 * d.win).rename(columns={
        "InpReferenceSpreadPts": "reference spread", "internalMinTrailing": "min / order distance factor", "distance": "about points behind the peak",
        "pf": "profit factor", "win": "win %", "avg": "points per trade"}), {"min / order distance factor": 2, "profit factor": 2, "points per trade": 1})
    d = tr[tr.tag == "simple, no speed exit"]
    V["T_trail_runner"] = md(d.sort_values("pf", ascending=False).head(8)[["TrailStartPoints", "TrailBehindPoints", "StopTPPoints", "pf", "pf_is", "pf_val", "pf_test", "win", "avg"]].assign(
        win=lambda x: 100 * x.win).rename(columns={"TrailStartPoints": "trail start", "TrailBehindPoints": "trail behind", "StopTPPoints": "target", "pf": "profit factor",
                                                   "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026", "win": "win %", "avg": "points per trade"}),
        {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1})
    V["trail_runner_best"] = f"{d.pf.max():.2f}"

    # ------------------------------------------------------------------ stops and targets
    ex = read("study_exits.csv")
    g = ex[(ex.tag == "geometry") & (ex.UseSpeedProfitExit == 0)]
    for col, key, dec in (("pf", "T_exit_pf", 2), ("avg", "T_exit_avg", 1)):
        piv = g.pivot_table(index="StopSLPoints", columns="StopTPPoints", values=col)
        piv.index = [f"stop {int(i)}" for i in piv.index]
        piv.columns = [f"target {int(c)}" for c in piv.columns]
        V[key] = md(piv.reset_index().rename(columns={"index": "stop loss / take profit"}), {c: dec for c in piv.columns})
    ge = ex[ex.tag == "geometry"]
    V["exit_pf_max"] = f"{ge.pf.max():.2f}"
    V["exit_avg_best"] = f"{ge.avg.max():.0f}"
    V["exit_avg_worst"] = f"{ge.avg.min():.0f}"
    V["exit_n"] = str(len(ge))

    # ------------------------------------------------------------------ spread cap x multiplier, order delay
    gs = read("grid_stops.csv")
    piv = gs.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="pf").sort_index(ascending=False)
    piv.index = [f"spread cap {int(i)}" for i in piv.index]
    piv.columns = [f"x{c:g}" for c in piv.columns]
    V["T_grid"] = md(piv.reset_index().rename(columns={"index": "MaxSpreadPoints / MaxTrailingMultiplier"}), {c: 2 for c in piv.columns})
    lat = read("latency.csv")
    piv = lat.pivot_table(index="name", columns="latency_ms", values="pf")
    piv = piv.loc[list(dict.fromkeys(lat.name))]
    piv.columns = [f"{int(c)} ms" for c in piv.columns]
    V["T_latency"] = md(piv.reset_index().rename(columns={"name": "input set"}), {c: 2 for c in piv.columns})
    mk = lat[lat.name.str.startswith("best set found")]
    V["mk_pf0"] = f"{mk[mk.latency_ms == 0].pf.iloc[0]:.2f}"
    V["mk_pf150"] = f"{mk[mk.latency_ms == 150].pf.iloc[0]:.2f}"
    V["mk_slip150"] = f"{mk[mk.latency_ms == 150].entry_slip.iloc[0]:.0f}"
    V["mk_avg0"] = f"{mk[mk.latency_ms == 0].avg.iloc[0]:.0f}"
    z1 = pd.read_csv(os.path.join(RES, "zero_latency", "joint_native_seed1.csv"))
    z2 = pd.read_csv(os.path.join(RES, "zero_latency", "joint_native_focus.csv"))
    V["z_wide_n"], V["z_wide_max"], V["z_wide_med"] = str(len(z1)), f"{z1.pf.max():.2f}", f"{z1.pf.median():.2f}"
    V["z_focus_n"], V["z_focus_max"] = str(len(z2)), f"{z2.pf.max():.2f}"
    V["z_focus_share"] = f"{100 * ((z2.pf_is >= 1) & (z2.pf_val >= 1)).mean():.1f}%"
    zg = pd.read_csv(os.path.join(RES, "zero_latency", "grid_spread_mult.csv"))
    V["z_grid_max"] = f"{zg.pf.max():.2f}"

    # ------------------------------------------------------------------ calibrated preset
    cf = read("center_final.csv")
    c0 = cf[cf.kind == "center"].iloc[0]
    V["fin_pf"], V["fin_is"], V["fin_val"], V["fin_test"] = f"{c0.pf:.2f}", f"{c0.pf_is:.2f}", f"{c0.pf_val:.2f}", f"{c0.pf_test:.2f}"
    V["fin_n"], V["fin_avg"], V["fin_dd"] = f"{int(c0.n):,}", f"{c0.avg:.0f}", f"{c0.dd:,.0f}"
    V["fin_win"] = f"{100 * c0.win:.0f}%"
    V["fin_avg_win"], V["fin_avg_loss"] = f"{c0.avg_win:.0f}", f"{c0.avg_loss:.0f}"
    tr_ = pd.read_csv(os.path.join(RES, "center_final_center_trades.csv"))
    p = tr_.pts.to_numpy()
    V["fin_t"] = f"{p.mean() / (p.std(ddof=1) / np.sqrt(len(p))):.1f}"
    rng = np.random.default_rng(1)
    bpf = []
    for _ in range(4000):
        s_ = rng.choice(p, len(p))
        bpf.append(s_[s_ > 0].sum() / -s_[s_ < 0].sum())
    V["fin_boot_lo"], V["fin_boot_hi"] = f"{np.percentile(bpf, 5):.2f}", f"{np.percentile(bpf, 95):.2f}"
    V["fin_boot_below"] = f"{100 * (np.array(bpf) < 1).mean():.1f}%"
    days = pd.to_datetime(tr_.entry_time).dt.date.nunique()
    V["fin_per_day"] = f"{len(p) / days:.0f}"
    tr_["month"] = pd.to_datetime(tr_.entry_time).dt.to_period("M").astype(str)
    rows = []
    for m_, g_ in tr_.groupby("month"):
        st = stats(g_.pts)
        rows.append({"month": m_, "trades": st["trades"], "profit factor": st["pf"], "points per trade": st["avg"], "net points": st["net"]})
    fm_ = pd.DataFrame(rows)
    V["T_final_month"] = md(fm_, {"profit factor": 2, "points per trade": 1})
    V["fin_months_pos"] = f"{int((fm_['net points'] > 0).sum())} of {len(fm_)}"
    V["fin_months_top"] = ", ".join(fm_.sort_values("net points", ascending=False).head(3).month)
    V["fin_top3_share"] = f"{100 * fm_.sort_values('net points', ascending=False).head(3)['net points'].sum() / fm_['net points'].sum():.0f}%"
    st_ = cf[cf.kind == "stress"][["name", "n", "pf", "pf_is", "pf_val", "pf_test", "avg", "dd"]].rename(columns={
        "name": "change to the calibrated preset", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026",
        "avg": "points per trade", "dd": "max drawdown, points"})
    V["T_final_stress"] = md(st_, {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1})
    worst = cf[cf.name == "strict fills + commission 7"].iloc[0]
    V["fin_worst_pf"] = f"{worst.pf:.2f}"
    V["fin_comm7_pf"] = f"{cf[cf.name == 'commission 7 points per round trip'].pf.iloc[0]:.2f}"
    V["fin_strict_pf"] = f"{cf[cf.name.str.startswith('strict fills (')].pf.iloc[0]:.2f}"
    nt = read("center_no_trailing_variant.csv")
    n0 = nt[nt.kind == "center"].iloc[0]
    tv = nt[nt.name.str.startswith("trailing:")].copy()
    tv["name"] = tv.name.str.replace("trailing: ", "")
    tv = pd.concat([pd.DataFrame([dict(name="no trailing (shipped behaviour: both mechanisms inert)", n=n0.n, pf=n0.pf, pf_is=n0.pf_is, pf_val=n0.pf_val, pf_test=n0.pf_test,
                                       avg=n0.avg, win=n0.win, dd=n0.dd)]), tv])
    V["T_final_trailing"] = md(tv[["name", "n", "pf", "pf_is", "pf_val", "pf_test", "win", "avg", "dd"]].assign(win=lambda d: 100 * d.win).rename(columns={
        "name": "trailing on the calibrated entries", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026",
        "win": "win %", "avg": "points per trade", "dd": "max drawdown, points"}), {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1})
    V["nt_pf"], V["nt_dd"] = f"{n0.pf:.2f}", f"{n0.dd:,.0f}"
    rev = nt[nt.name.str.startswith("back to shipped") | nt.name.isin(["entry hold off", "60 minute drift filter off", "post-entry validation off",
                                                                       "continuation filter off", "FlashGold filter off"])]
    V["T_final_revert"] = md(rev[["name", "n", "pf", "pf_is", "pf_val", "pf_test", "avg"]].rename(columns={
        "name": "one setting changed (no-trailing variant, profit factor " + f"{n0.pf:.2f}" + ")", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb",
        "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026", "avg": "points per trade"}), {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1})
    nb = nt[nt.kind == "neighbour"].copy()
    nb["input"] = nb.name.str.split("=").str[0]
    nb["value"] = nb.name.str.split("=").str[1]
    rows = []
    for name, g_ in nb.groupby("input", sort=False):
        rows.append({"input": name, "calibrated": {"MaxSpreadPoints": "14", "MaxTrailingMultiplier": "30", "StopEntryDistancePoints": "50", "StopSLPoints": "90",
                                                   "StopTPPoints": "600", "PendingExpirySeconds": "5", "SpeedLookbackSeconds": "10", "InpEntryHoldMs": "1100"}.get(name, ""),
                     "neighbouring values: profit factor": ", ".join(f"{v} -> {pf:.2f}" for v, pf in zip(g_.value, g_.pf)),
                     "lowest": g_.pf.min()})
    V["T_final_neighbours"] = md(pd.DataFrame(rows), {"lowest": 2})
    V["nb_min"] = f"{nb.pf.min():.2f}"
    V["nb_n"] = str(len(nb))
    mult75 = nt[nt.name == "back to shipped: multiplier 7.5"].iloc[0]
    V["fin_mult75_pf"] = f"{mult75.pf:.2f}"

    # ------------------------------------------------------------------ spread
    sp = read("study_spread.csv")
    piv = sp.pivot_table(index="name", columns="spread_median", values="pf")
    piv = piv.loc[list(dict.fromkeys(sp.name))]
    piv.columns = [f"{c:.0f} points" for c in piv.columns]
    V["T_spread"] = md(piv.reset_index().rename(columns={"name": "median spread of the feed"}), {c: 2 for c in piv.columns})
    pn = sp.pivot_table(index="name", columns="spread_median", values="n").loc[list(dict.fromkeys(sp.name))]
    pn.columns = [f"{c:.0f} points" for c in pn.columns]
    V["T_spread_n"] = md(pn.reset_index().rename(columns={"name": "trades"}))

    # ------------------------------------------------------------------ FlashGold inputs
    om = read("oat_micro1s_fg.csv")
    omb = om[om.n >= 2000]
    g = omb.groupby("input").agg(lo=("pf", "min"), hi=("pf", "max"))
    V["micro_lo"], V["micro_hi"] = f"{g.lo.min():.2f}", f"{g.hi.max():.2f}"
    V["micro_n_inputs"] = str(om.input.nunique())
    lit = om[(om.input == "X_MicroRestart") & (om.value == 0)].iloc[0]
    V["micro_literal_n"] = f"{int(lit.n)}"

    # ------------------------------------------------------------------ inputs classification
    ic = read("inputs_classification.csv")
    cls = ic.tester_effect.str.split(":").str[0]
    V["n_inputs"] = str(len(ic))
    V["n_replayed"] = str(int((cls == "replayed").sum()))
    V["n_telemetry"] = str(int(cls.str.startswith("telemetry").sum()))
    V["n_labels"] = str(int(cls.str.startswith("label").sum()))
    V["n_flow"] = str(int(cls.str.startswith("order-flow").sum()))
    V["n_sizing"] = str(int(cls.str.startswith("position sizing").sum()))
    V["n_notreplayed"] = str(int(cls.str.startswith("not replayed").sum()))
    return V


def main():
    V = build()
    tpl = open(os.path.join(ROOT, "REPORT.template.md")).read()
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", tpl)) - set(V))
    if missing:
        raise SystemExit("unknown placeholders: " + ", ".join(missing))
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: V[m.group(1)], tpl)
    open(os.path.join(ROOT, "REPORT.md"), "w").write(out)
    print("REPORT.md written,", len(out.splitlines()), "lines;", len(V), "values")


if __name__ == "__main__":
    main()
