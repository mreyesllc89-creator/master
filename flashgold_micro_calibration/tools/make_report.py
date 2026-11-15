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
RES = os.environ.get("REPORT_RES") or os.path.join(ROOT, "results")      # REPORT_RES: read the tables from another folder (drafts)


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


def pct(x, q):
    return float(np.percentile(np.asarray(x, float), q))


def exact(x):
    return float((np.abs(np.asarray(x, float)) < 0.5).mean())


def sgn(v):
    return f"{v:+.0f}" if abs(v) >= 0.5 else "0"


SPLIT_NAMES = {"pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026"}
SPLIT_DEC = {"profit factor": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026": 2, "points per trade": 1}


PARTIAL = bool(os.environ.get("REPORT_PARTIAL"))        # draft mode: a study that has not finished leaves "(pending)"


class maybe:
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is not None and PARTIAL:
            print("pending:", et.__name__, ev)
            return True
        return False


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
    ref_all = read("trades_reference_preset.csv")
    late_all = ref_all[pd.to_datetime(ref_all.entry_time) >= pd.Timestamp("2026-10-01")]
    rows = []
    for route_ in f.route.unique():
        a = f[(f.route == route_) & (f.source == "real")].iloc[0]
        b = f[(f.route == route_) & (f.source == "replay")].iloc[0]
        lt = late_all[late_all.route == route_]
        rows.append({"route": route_, "real trades": int(a.n), "real profit factor": a.pf, "replay, Oct-Nov 2026": stats(lt.pts)["pf"],
                     "replay, all months": b.pf, "real win %": 100 * a.win, "replay win %": 100 * b.win,
                     "real avg win / loss": f"{a.avg_win:.0f} / {a.avg_loss:.0f}", "replay avg win / loss": f"{b.avg_win:.0f} / {b.avg_loss:.0f}"})
    V["T_fidelity_routes"] = md(pd.DataFrame(rows), {"real profit factor": 2, "replay, Oct-Nov 2026": 2, "replay, all months": 2})
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
    ag = json.load(open(os.path.join(RES, "real", "real_replay_agreement.json")))
    V["rr_corr"], V["rr_sign"], V["rr_close"] = f"{ag['corr']:.2f}", f"{100 * ag['same_sign']:.0f}%", f"{100 * ag['within_15']:.0f}%"
    V["rr_days"], V["rr_stretches"] = str(ag["days"]), str(ag["stretches"])
    V["rr_gap"] = f"{b0.sim_avg - b0.real_avg:+.1f}"

    # ------------------------------------------------------------------ fills: real account against the replay
    sl = real[(real.exit_kind == "SL") & real.exit_level.notna()].copy()
    sl["slip"] = sl.side * (sl.exit_level - sl.exit) / 0.01
    sl = sl[sl.slip > -50]                                         # a handful of stops moved by hand
    st_ = sl[sl.action.isin(["BS", "SS"])]
    est = (st_.side * (st_.entry - st_.exit_level) / 0.01 - 90.0)
    est = est[est.abs() <= 100]
    mk_ = sl[sl.action.isin(["BM", "SM"])]
    emk = (mk_.side * (mk_.entry - mk_.exit_level) / 0.01 - 80.0)
    emk = emk[emk.abs() <= 100]
    ref_tr = read("trades_reference_preset.csv")
    late = ref_tr[pd.to_datetime(ref_tr.entry_time) >= pd.Timestamp("2026-10-01")]
    r_e = late[late.route.str.startswith("FLXQ")]
    r_est = r_e.side * (r_e.entry - r_e.requested) / 0.01
    r_s = late[late.exit_reason == "SL"]
    r_sl = -r_s.side * (r_s.exit - (r_s.requested - r_s.side * 0.90)) / 0.01
    lat_ = read("latency.csv")
    lv = lat_[lat_.name.str.startswith("shipped preset with the market route") & (lat_.latency_ms == 150)].iloc[0]
    rows = [
        {"fill": "stop-loss fills exactly at the stop level", "real account, 7 Sep to 8 Oct 2026": f"{100 * exact(sl.slip):.0f}% of {len(sl):,}",
         "replay, Oct-Nov 2026": f"{100 * exact(r_sl):.0f}% of {len(r_sl):,}"},
        {"fill": "slip of a stop-loss fill, points: mean / 90th / 95th / 99th percentile",
         "real account, 7 Sep to 8 Oct 2026": f"{sl.slip.mean():.1f} / {pct(sl.slip, 90):.0f} / {pct(sl.slip, 95):.0f} / {pct(sl.slip, 99):.0f}",
         "replay, Oct-Nov 2026": f"{r_sl.mean():.1f} / {pct(r_sl, 90):.0f} / {pct(r_sl, 95):.0f} / {pct(r_sl, 99):.0f}"},
        {"fill": "stop-order entries exactly at the order price", "real account, 7 Sep to 8 Oct 2026": f"{100 * exact(est):.0f}% of {len(est):,}",
         "replay, Oct-Nov 2026": f"{100 * exact(r_est):.0f}% of {len(r_est):,}"},
        {"fill": "slip of a stop-order entry, points: mean / 90th percentile",
         "real account, 7 Sep to 8 Oct 2026": f"{est.mean():.1f} / {pct(est, 90):.0f}", "replay, Oct-Nov 2026": f"{r_est.mean():.1f} / {pct(r_est, 90):.0f}"},
        {"fill": "market entry against the price when the EA decided, points: 5th / 25th / 50th / 75th / 90th percentile",
         "real account, 7 Sep to 8 Oct 2026": " / ".join(sgn(pct(emk, q)) for q in (5, 25, 50, 75, 90)) + f" ({len(emk):,} entries)",
         "replay, Oct-Nov 2026": " / ".join(sgn(lv[f"mk_p{q:02d}"]) for q in (5, 25, 50, 75, 90)) + f" with an order delay of 150 ms ({int(lv.mk_n):,} entries)"},
        {"fill": "limit orders and take profits", "real account, 7 Sep to 8 Oct 2026": "filled at the market, with price improvement",
         "replay, Oct-Nov 2026": "same"},
    ]
    V["T_fills"] = md(pd.DataFrame(rows))
    V["sl_real_mean"], V["sl_sim_mean"] = f"{sl.slip.mean():.1f}", f"{r_sl.mean():.1f}"
    V["sl_sim_quoted"] = f"{r_sl.mean() / 1.5:.1f}"                # every slip beyond the level is scaled by 1.5
    V["sl_real_n"] = f"{len(sl):,}"
    bt = read("real/real_replay_baseline_trades.csv")
    pr = bt[(bt.exit_kind == "SL") & (bt.sim_kind == "SL") & bt.exit_level.notna()]
    V["sl_pair_n"] = str(len(pr))
    V["sl_pair_real"] = f"{(pr.side * (pr.exit_level - pr.exit) / 0.01).mean():.1f}"
    V["sl_pair_sim"] = f"{(pr.side * (pr.exit_level - pr.exit_sim) / 0.01).mean():.1f}"

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
    V["ref_test"] = f"{ref.pf_test:.2f}"
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

    # ------------------------------------------------------------------ order delay, searches without it
    lat = read("latency.csv")
    piv = lat.pivot_table(index="name", columns="latency_ms", values="pf")
    piv = piv.loc[list(dict.fromkeys(lat.name))]
    piv.columns = [f"{int(c)} ms" for c in piv.columns]
    V["T_latency"] = md(piv.reset_index().rename(columns={"name": "input set"}), {c: 2 for c in piv.columns})
    mk = lat[lat.name.str.startswith("best set found")]
    V["mk_pf0"] = f"{mk[mk.latency_ms == 0].pf.iloc[0]:.2f}"
    V["mk_pf150"] = f"{mk[mk.latency_ms == 150].pf.iloc[0]:.2f}"
    V["mk_slip150"] = f"{mk[mk.latency_ms == 150].mk_mean.iloc[0]:.0f}"
    V["mk_avg0"] = f"{mk[mk.latency_ms == 0].avg.iloc[0]:.0f}"
    live = lat[lat.name.str.startswith("shipped preset with the market route")]
    V["live_pf0"], V["live_pf150"] = f"{live[live.latency_ms == 0].pf.iloc[0]:.2f}", f"{live[live.latency_ms == 150].pf.iloc[0]:.2f}"
    z1 = pd.read_csv(os.path.join(RES, "zero_latency", "joint_native_seed1.csv"))
    z2 = pd.read_csv(os.path.join(RES, "zero_latency", "joint_native_focus.csv"))
    V["z_wide_n"], V["z_wide_max"], V["z_wide_med"] = str(len(z1)), f"{z1.pf.max():.2f}", f"{z1.pf.median():.2f}"
    V["z_focus_n"], V["z_focus_max"] = str(len(z2)), f"{z2.pf.max():.2f}"
    zg = pd.read_csv(os.path.join(RES, "zero_latency", "grid_spread_mult.csv"))
    V["z_grid_max"] = f"{zg.pf.max():.2f}"

    # ------------------------------------------------------------------ joint grid around the calibrated preset
    jg = read("grid_joint.csv")
    axes = [c for c in ("MaxTrailingMultiplier", "MaxSpreadPoints", "trailing", "InpEntryHoldMs", "StopSLPoints") if c in jg.columns]
    V["jg_n"] = str(len(jg))
    V["jg_pf_med"], V["jg_pf_min"], V["jg_pf_max"] = f"{jg.pf.median():.2f}", f"{jg.pf.min():.2f}", f"{jg.pf.max():.2f}"
    V["jg_pf_mean"] = f"{jg.pf.mean():.2f}"
    V["jg_share1"] = f"{100 * (jg.pf >= 1).mean():.0f}%"
    V["jg_early_med"], V["jg_early_share1"] = f"{jg.pf_early.median():.2f}", f"{100 * (jg.pf_early >= 1).mean():.0f}%"
    V["jg_test_med"], V["jg_test_share1"] = f"{jg.pf_test.median():.2f}", f"{100 * (jg.pf_test >= 1).mean():.0f}%"
    V["jg_rank_early_test"] = f"{jg.pf_early.rank().corr(jg.pf_test.rank()):.2f}"
    V["jg_rank_is_val"] = f"{jg.pf_is.rank().corr(jg.pf_val.rank()):.2f}"
    rows = []
    label = {"MaxTrailingMultiplier": "`MaxTrailingMultiplier`", "MaxSpreadPoints": "`MaxSpreadPoints`", "trailing": "trailing",
             "InpEntryHoldMs": "`InpEntryHoldMs`", "StopSLPoints": "`StopSLPoints`"}
    for ax in axes:
        for lev, g_ in jg.groupby(ax, sort=False):
            rows.append({"input": label[ax], "value": f"{lev:g}" if not isinstance(lev, str) else lev, "sets": len(g_), "average profit factor": g_.pf.mean(),
                         "Nov-May": g_.pf_early.mean(), "Oct-Nov 2026": g_.pf_test.mean(), "sets at or above 1, %": 100 * (g_.pf >= 1).mean(),
                         "average drawdown, points": g_.dd.mean()})
    V["T_jg_levels"] = md(pd.DataFrame(rows), {"average profit factor": 2, "Nov-May": 2, "Oct-Nov 2026": 2})
    ok = jg[(jg.n_early >= 400) & (jg.pf_is >= 1.0) & (jg.pf_val >= 1.0)].sort_values("pf_early", ascending=False)
    V["jg_ok_n"] = str(len(ok))
    t = ok.head(8)[axes + ["n", "pf_early", "pf_is", "pf_val", "pf_test", "pf", "dd"]].rename(columns={
        "MaxTrailingMultiplier": "multiplier", "MaxSpreadPoints": "spread cap", "InpEntryHoldMs": "entry hold ms", "StopSLPoints": "stop",
        "n": "trades", "pf_early": "Nov-May", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026 (not used for ranking)",
        "pf": "all months", "dd": "max drawdown, points"})
    V["T_jg_top"] = md(t, {"Nov-May": 2, "Nov-Feb": 2, "Mar-May": 2, "Oct-Nov 2026 (not used for ranking)": 2, "all months": 2, "multiplier": 0, "spread cap": 0})
    top = ok.head(max(10, len(jg) // 10))
    V["jg_top_n"] = str(len(top))
    V["jg_top_test_med"] = f"{top.pf_test.median():.2f}"

    # ------------------------------------------------------------------ calibrated preset
    cf = read("center_final.csv")
    c0 = cf[cf.kind == "center"].iloc[0]
    V["fin_pf"], V["fin_is"], V["fin_val"], V["fin_test"] = f"{c0.pf:.2f}", f"{c0.pf_is:.2f}", f"{c0.pf_val:.2f}", f"{c0.pf_test:.2f}"
    V["fin_n"], V["fin_avg"], V["fin_dd"] = f"{int(c0.n):,}", f"{c0.avg:.0f}", f"{c0.dd:,.0f}"
    V["fin_avg1"] = f"{c0.avg:.1f}"
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
    V["fin_boot_below"] = f"{100 * (np.array(bpf) < 1).mean():.0f}%"
    V["fin_boot_sd"] = f"{np.std(bpf):.2f}"
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
    top3 = fm_.sort_values("net points", ascending=False).head(3)["net points"].sum()
    V["fin_top3_net"] = f"{top3:,.0f}"
    V["fin_rest_net"] = f"{fm_['net points'].sum() - top3:+,.0f}"
    V["fin_rest_n"] = str(len(fm_) - 3)
    rows = []
    for side_, name_ in ((1, "buy stops"), (-1, "sell stops")):
        st = stats(tr_.pts[tr_.side == side_])
        rows.append({"side": name_, "trades": st["trades"], "profit factor": st["pf"], "win %": st["win"], "points per trade": st["avg"], "net points": st["net"]})
    V["T_final_side"] = md(pd.DataFrame(rows), {"profit factor": 2, "points per trade": 1})
    V["fin_buy_pf"], V["fin_sell_pf"] = f"{rows[0]['profit factor']:.2f}", f"{rows[1]['profit factor']:.2f}"
    rows = []
    kind_ = tr_.exit_reason.map(lambda x: {"SL": "stop loss (original)", "LAYER_SL": "trailing stop (trail layer)", "TRAIL_SL": "trailing stop (simple trailing)",
                                           "TP": "take profit"}.get(x, "EA-side close"))
    for k_ in ["stop loss (original)", "trailing stop (trail layer)", "take profit", "EA-side close"]:
        g_ = tr_[kind_ == k_]
        if len(g_):
            rows.append({"closed by": k_, "trades": len(g_), "share %": 100 * len(g_) / len(tr_), "points per trade": g_.pts.mean(), "net points": g_.pts.sum(),
                         "median seconds held": g_.hold_s.median()})
    V["T_final_exits"] = md(pd.DataFrame(rows), {"points per trade": 1, "median seconds held": 1})
    V["fin_stop_share"] = f"{100 * kind_.isin(['stop loss (original)', 'trailing stop (trail layer)']).mean():.0f}%"
    V["fin_hold_med"] = f"{tr_.hold_s.median():.0f}"
    V["fin_entry_slip"] = f"{(tr_.side * (tr_.entry - tr_.requested) / 0.01).mean():.0f}"
    V["fin_entry_spread"] = f"{tr_.spread_pts.mean():.0f}"
    V["fin_alert"] = f"{tr_.alert_pts.mean():.0f}"
    st_ = cf[cf.kind == "stress"][["name", "n", "pf", "pf_is", "pf_val", "pf_test", "avg", "dd"]].rename(columns={
        "name": "change to the calibrated preset", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026",
        "avg": "points per trade", "dd": "max drawdown, points"})
    V["T_final_stress"] = md(st_, SPLIT_DEC)

    def stress(prefix):
        return cf[cf.name.str.startswith(prefix)].iloc[0]

    V["fin_worst_pf"] = f"{stress('strict fills + commission 7').pf:.2f}"
    V["fin_comm3_pf"] = f"{stress('commission 3').pf:.2f}"
    V["fin_comm7_pf"] = f"{stress('commission 7').pf:.2f}"
    V["fin_strict_pf"] = f"{stress('strict fills (').pf:.2f}"
    V["fin_slip10_pf"] = f"{stress('stop-loss slip as quoted').pf:.2f}"
    V["fin_slip20_pf"] = f"{stress('stop-loss slip factor 2.0').pf:.2f}"
    V["fin_notrail_pf"], V["fin_notrail_dd"] = f"{stress('no trailing at all').pf:.2f}", f"{stress('no trailing at all').dd:,.0f}"
    V["fin_layer100_pf"] = f"{stress('trail layer 100 points').pf:.2f}"
    V["fin_nofg_pf"] = f"{stress('FlashGold filter off').pf:.2f}"
    V["fin_micro_pf"] = f"{stress('FlashGold micro 1 s (capacity restart)').pf:.2f}"

    # ---- spread cap x multiplier around the calibrated preset
    gc = read("grid_calibrated.csv")
    piv = gc.pivot_table(index="MaxSpreadPoints", columns="MaxTrailingMultiplier", values="pf").sort_index(ascending=False)
    piv.index = [f"spread cap {int(i)}" for i in piv.index]
    piv.columns = [f"x{c:g}" for c in piv.columns]
    V["T_grid"] = md(piv.reset_index().rename(columns={"index": "MaxSpreadPoints / MaxTrailingMultiplier"}), {c: 2 for c in piv.columns})
    V["gc_n"] = str(len(gc))
    V["gc_max"], V["gc_min"] = f"{gc.pf.max():.2f}", f"{gc.pf.min():.2f}"
    V["gc_share1"] = f"{int((gc.pf >= 1).sum())} of {len(gc)}"
    low = gc[gc.MaxTrailingMultiplier <= 13]
    V["gc_low_max"] = f"{low.pf.max():.2f}"
    gs = read("grid_stops.csv")
    V["gs_min"], V["gs_max"] = f"{gs.pf.min():.2f}", f"{gs.pf.max():.2f}"

    # ---- trailing on the calibrated entries
    tc = read("study_trailing_calibrated.csv")
    none = tc[tc.tag == "none"].iloc[0]
    V["tc_n"] = str(len(tc))
    V["tc_none_pf"], V["tc_none_dd"] = f"{none.pf:.2f}", f"{none.dd:,.0f}"
    cols_ = {"n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb", "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026", "win": "win %", "avg": "points per trade",
             "dd": "max drawdown, points", "moved": "trades whose stop was moved, %"}

    def tc_table(d_, first):
        d_ = d_.assign(win=100 * d_.win, moved=100 * d_.sl_moved)
        return md(d_[[first] + list(cols_)].rename(columns=cols_), SPLIT_DEC)

    lay = tc[tc.tag == "layer"].copy()
    lay["what"] = lay.distance.map(lambda x: f"trail layer {int(x)} points behind (`InpReferenceSpreadPts` {x * 0.3:g})")
    V["T_tc_layer"] = tc_table(pd.concat([pd.DataFrame([dict(none, what="no trailing")]), lay]), "what").replace("| what |", "| trail layer |")
    simp = tc[tc.tag == "simple"]
    for col, key, dec in (("pf", "T_tc_simple", 2), ("dd", "T_tc_simple_dd", 0)):
        piv = simp.pivot_table(index="TrailStartPoints", columns="TrailBehindPoints", values=col)
        piv.index = [f"start {int(i)}" for i in piv.index]
        piv.columns = [f"behind {int(c)}" for c in piv.columns]
        V[key] = md(piv.reset_index().rename(columns={"index": "`TrailStartPoints` / `TrailBehindPoints`"}), {c: dec for c in piv.columns})
    V["tc_simple_lo"], V["tc_simple_hi"] = f"{simp.pf.min():.2f}", f"{simp.pf.max():.2f}"
    wide = tc[((tc.tag == "layer") & (tc.distance >= 125) & (tc.distance <= 200)) | ((tc.tag == "simple") & (tc.TrailBehindPoints >= 110))]
    tight = tc[((tc.tag == "layer") & (tc.distance <= 75)) | ((tc.tag == "simple") & (tc.TrailBehindPoints <= 60) & (tc.TrailStartPoints <= 160))]
    V["tc_wide_lo"], V["tc_wide_hi"] = f"{wide.pf.min():.2f}", f"{wide.pf.max():.2f}"
    V["tc_wide_dd_lo"], V["tc_wide_dd_hi"] = f"{wide.dd.min():,.0f}", f"{wide.dd.max():,.0f}"
    V["tc_tight_lo"], V["tc_tight_hi"] = f"{tight.pf.min():.2f}", f"{tight.pf.max():.2f}"
    stp = tc[tc.tag == "simple step"].sort_values("TrailStepPoints")
    V["tc_step"] = ", ".join(f"step {int(r.TrailStepPoints)}: {r.pf:.2f}" for r in stp.itertuples())
    sett = tc[tc.tag.isin(["layer+settle", "simple+settle"])].copy()
    sett["what"] = np.where(sett.tag == "layer+settle", "trail layer 100", "simple 160/110")
    sett["settle rule"] = [f"quiet {int(r.InpBurstSettleQuietMs)} ms, pullback {r.InpBurstSettlePullbackPips:g} pips, speed {r.InpBurstSettleSpeedFraction:g} / {r.InpBurstSettleMaxSpeedPipsSec:g}"
                           for r in sett.itertuples()]
    sett = sett.assign(moved=100 * sett.sl_moved)
    V["T_tc_settle"] = md(sett.sort_values(["what", "InpBurstSettleQuietMs"])[["what", "settle rule", "pf", "dd", "moved"]].rename(columns={
        "what": "trailing", "pf": "profit factor", "dd": "max drawdown, points", "moved": "trades whose stop was moved, %"}), {"profit factor": 2})
    both = tc[tc.tag == "layer+simple"]
    V["tc_both"] = ", ".join(f"{int(r.TrailStartPoints)}/{int(r.TrailBehindPoints)}: {r.pf:.2f}" for r in both.itertuples())
    lst = tc[tc.tag == "layer x stop x target"]
    for dist in (100, 200):
        piv = lst[lst.distance == dist].pivot_table(index="StopSLPoints", columns="StopTPPoints", values="pf")
        piv.index = [f"stop {int(i)}" for i in piv.index]
        piv.columns = [f"target {int(c)}" for c in piv.columns]
        V[f"T_tc_sltp{dist}"] = md(piv.reset_index().rename(columns={"index": f"trail layer {dist}: stop / target"}), {c: 2 for c in piv.columns})

    # ---- one setting at a time put back, neighbours (on the variant without trailing)
    nt = read("center_no_trailing_variant.csv")
    n0 = nt[nt.kind == "center"].iloc[0]
    V["nt_pf"], V["nt_dd"] = f"{n0.pf:.2f}", f"{n0.dd:,.0f}"
    order_ = ([n_ for n_ in nt.name if n_.startswith("back to shipped")]
              + ["entry hold off", "60 minute drift filter off", "FlashGold filter off", "post-entry validation off", "continuation filter off",
                 "buys only", "sells only"])
    rev = nt.set_index("name").loc[order_].reset_index()
    V["T_final_revert"] = md(rev[["name", "n", "pf", "pf_is", "pf_val", "pf_test", "avg"]].rename(columns={
        "name": "one setting changed (variant without trailing, profit factor " + f"{n0.pf:.2f}" + ")", "n": "trades", "pf": "profit factor", "pf_is": "Nov-Feb",
        "pf_val": "Mar-May", "pf_test": "Oct-Nov 2026", "avg": "points per trade"}), SPLIT_DEC)

    def ntrow(name_):
        return nt[nt.name == name_].iloc[0]

    V["fin_mult75_pf"] = f"{ntrow('back to shipped: multiplier 7.5').pf:.2f}"
    V["rev_fade_pf"] = f"{ntrow('back to shipped: fade route on (EntryRouterMode 2)').pf:.2f}"
    V["rev_cp_pf"] = f"{ntrow('continuation filter off').pf:.2f}"
    V["rev_buy_pf"], V["rev_buy_n"] = f"{ntrow('buys only').pf:.2f}", f"{int(ntrow('buys only').n)}"
    V["rev_sell_pf"], V["rev_sell_n"] = f"{ntrow('sells only').pf:.2f}", f"{int(ntrow('sells only').n)}"
    nb = nt[nt.kind == "neighbour"].copy()
    nb["input"] = nb.name.str.split("=").str[0]
    nb["value"] = nb.name.str.split("=").str[1]
    rows = []
    for name, g_ in nb.groupby("input", sort=False):
        rows.append({"input": name, "calibrated": {"MaxSpreadPoints": "14", "MaxTrailingMultiplier": "30", "StopEntryDistancePoints": "50", "StopSLPoints": "90",
                                                   "StopTPPoints": "600", "PendingExpirySeconds": "5", "SpeedLookbackSeconds": "10", "InpEntryHoldMs": "1100"}.get(name, ""),
                     "neighbouring values: profit factor": ", ".join(f"{v} -> {pf:.2f}" for v, pf in zip(g_.value, g_.pf)),
                     "lowest": g_.pf.min(), "highest": g_.pf.max()})
    V["T_final_neighbours"] = md(pd.DataFrame(rows), {"lowest": 2, "highest": 2})
    V["nb_min"], V["nb_max"] = f"{nb.pf.min():.2f}", f"{nb.pf.max():.2f}"
    V["nb_n"] = str(len(nb))

    # ---- every input, one at a time, around the calibrated preset
    oc = read("oat_calibrated.csv")
    ocb = oc[oc.is_base].iloc[0]
    V["oc_n_inputs"], V["oc_n_runs"] = str(oc.input.nunique()), f"{len(oc):,}"
    V["oc_base_pf"] = f"{ocb.pf:.2f}"
    ok_ = oc[(oc.n >= 400) & ~oc.input.str.startswith("X_")]
    g = ok_.groupby("input").agg(lo=("pf", "min"), hi=("pf", "max"))
    g["span"] = g.hi - g.lo
    rows = []
    for name, r in g.sort_values("span", ascending=False).head(16).iterrows():
        k = ok_[ok_.input == name]
        best = k.loc[k.pf.idxmax()]
        base_ = oc[(oc.input == name) & oc.is_base]
        rows.append({"input": name, "calibrated": f"{float(base_.value.iloc[0]):g}" if len(base_) else "",
                     "values tested": ", ".join(f"{v:g}" for v in k.value), "lowest": r.lo, "highest": r.hi, "best value": f"{best.value:g}",
                     "best: Nov-Feb / Mar-May / Oct-Nov": f"{best.pf_is:.2f} / {best.pf_val:.2f} / {best.pf_test:.2f}"})
    V["T_oc_top"] = md(pd.DataFrame(rows), {"lowest": 2, "highest": 2})
    span_c = oc.groupby("input").pf.agg(lambda x: x.max() - x.min())
    V["oc_dead_n"] = str(int((span_c < 0.0005).sum()))
    V["oc_dead"] = ", ".join(f"`{k}`" for k in span_c[span_c < 0.0005].index)
    cand = ok_[(ok_.pf >= ocb.pf + 0.03) & (ok_.pf_is >= ocb.pf_is) & (ok_.pf_val >= ocb.pf_val) & (ok_.pf_test >= ocb.pf_test) & ~ok_.is_base]
    rows = [{"input": r.input, "value": f"{r.value:g}", "trades": int(r.n), "profit factor": r.pf, "Nov-Feb": r.pf_is, "Mar-May": r.pf_val,
             "Oct-Nov 2026": r.pf_test, "max drawdown, points": r.dd} for r in cand.sort_values("pf", ascending=False).itertuples()]
    V["oc_cand_n"] = str(len(rows))
    V["T_oc_cand"] = md(pd.DataFrame(rows), SPLIT_DEC) if rows else "(none)"

    # ---- the FlashGold gate candidates, checked on a grid
    with maybe():
        fg = read("grid_flashgold.csv")
        rows = []
        for ax, lab in (("FG_InpBandAtr", "`FG_InpBandAtr`"), ("FG_InpEntryDistAtr", "`FG_InpEntryDistAtr`")):
            for lev, g_ in fg.groupby(ax, sort=False):
                rows.append({"input": lab, "value": f"{lev:g}", "sets": len(g_), "average trades": g_.n.mean(), "average profit factor": g_.pf.mean(),
                             "Nov-May": g_.pf_early.mean(), "Oct-Nov 2026": g_.pf_test.mean(), "sets at or above 1, %": 100 * (g_.pf >= 1).mean()})
        t_fg = md(pd.DataFrame(rows), {"average profit factor": 2, "Nov-May": 2, "Oct-Nov 2026": 2})
        band = fg.groupby("FG_InpBandAtr").agg(pf=("pf", "mean"), early=("pf_early", "mean"), test=("pf_test", "mean"), n=("n", "mean"))
        b_lo, b_hi = band.loc[band.index.min()], band.loc[band.pf.idxmax()]
        best_band = float(band.pf.idxmax())
        holds = (b_hi.pf - b_lo.pf >= 0.04) and (b_hi.early > b_lo.early) and (b_hi.test > b_lo.test) and best_band > band.index.min()
        dist = fg.groupby("FG_InpEntryDistAtr").agg(pf=("pf", "mean"), early=("pf_early", "mean"), test=("pf_test", "mean"))
        d_lo, d_hi = dist.loc[dist.index.min()], dist.loc[dist.pf.idxmax()]
        best_dist = float(dist.pf.idxmax())
        dist_holds = (d_hi.pf - d_lo.pf >= 0.04) and (d_hi.early > d_lo.early) and (d_hi.test > d_lo.test) and best_dist > dist.index.min()
        text = ("Two of them are FlashGold gate inputs: a wider band around the armed level (`FG_InpBandAtr`) and a larger entry distance "
                "(`FG_InpEntryDistAtr`). Both make the gate stricter and cut the number of trades. Because single replays are noisy, they were "
                f"put through a grid of {len(fg)} sets (four bands, three entry distances, four multipliers, two spread caps), "
                "`results/grid_flashgold.csv`:\n\n" + t_fg + "\n\n")
        if holds:
            text += (f"The band holds up on average: {b_lo.pf:.2f} at the shipped {band.index.min():g} against {b_hi.pf:.2f} at {best_band:g}, higher in the months "
                     f"to May ({b_lo.early:.2f} to {b_hi.early:.2f}) and in October-November ({b_lo.test:.2f} to {b_hi.test:.2f}), on about "
                     f"{b_hi.n:,.0f} trades instead of {b_lo.n:,.0f}. ")
        else:
            text += (f"The band does not hold up on average: {b_lo.pf:.2f} at the shipped {band.index.min():g} against {b_hi.pf:.2f} at the best value "
                     f"({best_band:g}). ")
        if dist_holds:
            text += f"The entry distance holds up too ({d_lo.pf:.2f} at {dist.index.min():g}, {d_hi.pf:.2f} at {best_dist:g}). "
        else:
            text += f"The entry distance does not ({d_lo.pf:.2f} at the shipped {dist.index.min():g}, {d_hi.pf:.2f} at {best_dist:g}). "
        text += ("Neither is in the calibrated preset: fewer trades make the result harder to verify, and a gain that appears after the preset was "
                 "fixed is the kind that most often disappears. `FlashGold_NativeReference_Calibrated_flashgold_TESTER_OPT.set` is the range file "
                 "to test them in MetaTrader.")
        V["FG_GATE_TEXT"] = text
        V["fg_n"] = str(len(fg))

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
    with maybe():
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
    V = {k: v for k, v in V.items()}
    tpl = open(os.path.join(ROOT, "REPORT.template.md")).read()
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", tpl)) - set(V))
    if missing and not PARTIAL:
        raise SystemExit("unknown placeholders: " + ", ".join(missing))
    for k in missing:
        print("pending placeholder:", k)
        V[k] = "(pending)"
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: V[m.group(1)], tpl)
    open(os.path.join(ROOT, "REPORT.md"), "w").write(out)
    print("REPORT.md written,", len(out.splitlines()), "lines;", len(V), "values")


if __name__ == "__main__":
    main()
