"""Stage 2: one-factor-at-a-time EA input sweeps (incl. the v1.50 improvements)
on the best indicator configurations per chart timeframe from stage 1."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep, rt_model as rt

IND_COLS = ["chart_tf", "er_period", "enter", "exit", "atr_period", "atr_mult", "min_dwell", "shock_mult"]
MIN_IS_TRADES = {"M5": 120, "M15": 90, "M30": 70, "H1": 50}


def top_indicators(stage1_csv, per_tf=6):
    df = pd.read_csv(stage1_csv)
    picks = []
    for tf, g in df.groupby("chart_tf"):
        g = g[g["is_trades"] >= MIN_IS_TRADES[tf]]
        g = g.sort_values("is_sqn", ascending=False).head(per_tf)
        picks += [dict(r[IND_COLS]) for _, r in g.iterrows()]
    for p in picks:
        for k in ["er_period", "atr_period", "min_dwell"]:
            p[k] = int(p[k])
    return picks


def ea_variants():
    v = [("baseline", {})]
    v += [("exit_mode", dict(exit_mode=0))]
    v += [("be", dict(use_be=1, be_r=r)) for r in (0.5, 1.0, 1.5, 2.0)]
    v += [("trail_off", dict(trail_mode=0))]
    v += [("trail_step", dict(trail_step_pts=s)) for s in (0, 20, 100, 200, 400)]
    v += [("trail_tight", dict(trail_mode=2, _ind=dict(trail_atr_mult=m))) for m in (1.5, 2.0, 2.5, 3.0)]
    v += [("trail_chand", dict(trail_mode=3, trail_atr_k=k)) for k in (2.0, 3.0, 4.0, 5.0)]
    v += [("trail_atrclose", dict(trail_mode=4, trail_atr_k=k)) for k in (2.0, 3.0, 4.0, 5.0)]
    v += [("trail_activate", dict(trail_activate_r=r)) for r in (0.5, 1.0, 1.5, 2.0)]
    v += [("tp_r", dict(tp_r=r)) for r in (1.5, 2.0, 3.0, 4.0, 6.0)]
    v += [("macro_nonstrict", dict(strict_longs=0, strict_shorts=0)),
          ("macro_off", dict(use_macro_filter=0, strict_longs=0, strict_shorts=0)),
          ("macro_strict_longs_only", dict(strict_shorts=0)),
          ("macro_strict_shorts_only", dict(strict_longs=0))]
    v += [("direction", dict(trade_direction=d)) for d in (1, 2)]
    v += [("min_stop_atr", dict(min_stop_atr=a)) for a in (0.0, 0.5, 1.5, 2.0)]
    v += [("max_stop_atr", dict(max_stop_atr=a)) for a in (1.5, 2.0, 3.0, 4.0)]
    v += [("sl_atr", dict(sl_atr_mult=a)) for a in (1.0, 1.5, 2.0, 3.0)]
    v += [("st_flip_exit", dict(exit_on_st_flip=1))]
    v += [("er_exit", dict(er_exit=e)) for e in (0.15, 0.25, 0.35)]
    v += [("max_bars", dict(max_bars_in_trade=b)) for b in (24, 48, 96, 192)]
    v += [("friday", dict(close_friday_hour=h)) for h in (14, 18, 20)]
    v += [("session", dict(use_session=1, start_hour=a, end_hour=b)) for a, b in ((7, 18), (7, 20), (8, 16), (12, 21), (0, 12), (13, 22))]
    v += [("late_entry", dict(late_entry_bars=n, reentry_after_stop=r)) for n in (2, 4, 8) for r in (0, 1)]
    v += [("prev_state", dict(entry_prev_state=s)) for s in (1, 2)]
    v += [("min_er", dict(min_er_entry=e)) for e in (0.45, 0.50, 0.60)]
    v += [("max_spread", dict(max_spread_pts=s)) for s in (30, 40, 50)]
    v += [("lock", dict(lock_trigger_r=t, lock_r=l)) for t, l in ((1.5, 0.5), (2.0, 1.0), (3.0, 1.5), (1.0, 0.2))]
    v += [("partial", dict(partial_r=r, partial_pct=p)) for r, p in ((1.0, 50), (1.5, 50), (2.0, 50), (1.0, 30), (3.0, 50))]
    v += [("costs_xm", dict(spread_add_pts=10, swap_usd_lot_night=-8.0))]
    return v


if __name__ == "__main__":
    picks = top_indicators(os.path.join(sweep.DATA, "stage1_indicator_grid.csv"))
    jobs = []
    for ind_over in picks:
        for name, over in ea_variants():
            ind = dict(rt.IND_DEFAULTS); ind.update(ind_over)
            ea = {k: v for k, v in over.items() if k != "_ind"}
            if "_ind" in over:
                ind.update(over["_ind"])
            ea["variant"] = name
            jobs.append((ind, ea, sweep.DEFAULT_WINDOWS))
    print("indicator picks:", len(picks), "variants:", len(ea_variants()), "jobs:", len(jobs), flush=True)
    sweep.run_jobs_custom(jobs, os.path.join(sweep.DATA, "stage2_ea_variants.csv"), sweep.evaluate_labeled, procs=4, chunk=5, tag="stage2")
