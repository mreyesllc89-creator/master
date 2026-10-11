"""BTC stage 2: EA-side variants (incl. proposed v1.11 improvements) one at a time
on the best stage-1 configs per timeframe and method."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_sweep as sw, btc_model as bm

SIG_COLS = ["chart_tf", "method", "length", "exit_bars", "efficiency", "pullback_ema", "clearance"]
EA_COLS = ["ea_stop_atr", "ea_trail_atr", "ea_tp_r"]
MIN_IS = {"M15": 150, "M30": 100, "H1": 60, "H4": 30}


def top_configs(csv, per_tf=8):
    df = pd.read_csv(csv)
    picks = []
    for tf, g in df.groupby("chart_tf"):
        g = g[g["is_trades"] >= MIN_IS[tf]].sort_values("is_sqn", ascending=False)
        # at most 3 per method so the picks are not all one method
        g = g.groupby("method").head(3).head(per_tf)
        for _, r in g.iterrows():
            sig = {k: r[k] for k in SIG_COLS}
            for k in ("method", "length", "exit_bars", "pullback_ema"):
                sig[k] = int(sig[k])
            ea = {k[3:]: float(r[k]) for k in EA_COLS}
            picks.append((sig, ea))
    return picks


def variants():
    v = [("baseline", {})]
    v += [("risk", dict(risk_pct=r)) for r in (1.0, 2.0)]
    v += [("no_signal_exit", dict(exit_rule=1))]
    v += [("be", dict(use_be=1, be_r=r)) for r in (0.5, 1.0, 1.5, 2.0)]
    v += [("lock", dict(lock_trigger_r=t, lock_r=l)) for t, l in ((1.5, 0.5), (2.0, 1.0), (3.0, 1.5))]
    v += [("trail_activate", dict(trail_activate_r=r)) for r in (0.5, 1.0, 2.0)]
    v += [("chandelier", dict(trail_mode=2))]
    v += [("partial", dict(partial_r=r, partial_pct=50)) for r in (1.0, 2.0, 3.0)]
    v += [("er_exit", dict(er_exit=e)) for e in (0.10, 0.15, 0.20)]
    v += [("max_hold", dict(max_hold_bars=b)) for b in (24, 48, 96, 200)]
    v += [("long_only", dict(long_only=1)), ("short_only", dict(short_only=1))]
    v += [("max_spread", dict(max_spread_atr=s)) for s in (0.0, 0.10, 0.50)]
    v += [("trail_step", dict(trail_step_pts=s)) for s in (0, 1000, 5000)]
    v += [("costs_crypto", dict(commission_pct=0.05, swap_pct_day=-0.03)),
          ("costs_heavy", dict(spread_add_pct=0.03, commission_pct=0.05, swap_pct_day=-0.06))]
    return v


if __name__ == "__main__":
    picks = top_configs(os.path.join(sw.DATA, "btc_stage1.csv"))
    jobs = []
    for sig, ea_base in picks:
        s = dict(bm.SIG_DEFAULTS); s.update(sig)
        for name, over in variants():
            ea = dict(ea_base); ea.update(over); ea["variant"] = name
            jobs.append((s, ea, sw.DEFAULT_WINDOWS))
    print("picks:", len(picks), "variants:", len(variants()), "jobs:", len(jobs), flush=True)
    sw.run_jobs(jobs, os.path.join(sw.DATA, "btc_stage2.csv"), procs=4, chunk=6, tag="btc2")
