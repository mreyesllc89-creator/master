"""Stage 3: joint random search over indicator AND EA inputs (all improvements
switchable), per chart timeframe, seeded by the stage 1/2 findings. Each
sample draws every input independently from its level list, so interactions
between inputs are explored, not just one factor at a time."""
import sys, os, json
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep, rt_model as rt

N_PER_TF = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
SEED = 20261011

IND_LEVELS = dict(
    er_period=[7, 10, 14, 20, 30],
    enter=[0.30, 0.36, 0.42, 0.50, 0.55, 0.62, 0.70],
    exit=[0.10, 0.18, 0.28],
    atr_period=[10, 14, 20],
    atr_mult=[2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
    min_dwell=[2, 4, 6, 10],
    shock_mult=[2.5, 3.0, 5.0, 8.0],
    macro_ema=[20, 50, 100],
    macro_slope=[2, 3, 5],
    macro_deadband=[0.02, 0.05, 0.10],
)
EA_LEVELS = dict(
    exit_mode=[0, 1],
    use_be=[0, 0, 1], be_r=[0.5, 1.0, 1.5, 2.0],
    trail_mode=[0, 1, 1, 2, 3, 4], trail_step_pts=[0, 20, 50, 100, 200], trail_atr_k=[2.0, 3.0, 4.0, 5.0],
    trail_activate_r=[0.0, 0.0, 0.5, 1.0, 1.5],
    tp_r=[0.0, 0.0, 2.0, 3.0, 4.0, 6.0],
    macro=[0, 1, 2, 3],   # 0 strict both (default), 1 non-strict, 2 off, 3 strict longs only
    trade_direction=[0, 0, 0, 1, 2],
    min_stop_atr=[0.0, 0.5, 1.0, 1.5, 2.0],
    max_stop_atr=[0.0, 0.0, 2.0, 3.0, 4.0],
    sl_atr_mult=[0.0, 0.0, 0.0, 1.5, 2.0, 3.0],
    exit_on_st_flip=[0, 0, 1],
    er_exit=[0.0, 0.0, 0.15, 0.25, 0.35],
    max_bars_in_trade=[0, 0, 0, 48, 96, 192],
    close_friday_hour=[0, 0, 0, 18, 20],
    session=[0, 0, 0, 1, 2, 3],   # 0 off, 1 7-18, 2 7-20, 3 12-21
    late_entry_bars=[0, 0, 2, 4, 8], reentry_after_stop=[0, 1],
    entry_prev_state=[0, 0, 1, 2],
    min_er_entry=[0.0, 0.0, 0.45, 0.50, 0.60],
    lock=[0, 0, 1, 2, 3],         # 0 off, 1 (1.5,0.5), 2 (2,1), 3 (3,1.5)
    partial=[0, 0, 0, 1, 2],      # 0 off, 1 (1R,50%), 2 (2R,50%)
)
TRAIL_TIGHT = [1.5, 2.0, 2.5, 3.0]


def sample(rng, tf):
    ind = dict(rt.IND_DEFAULTS); ind["chart_tf"] = tf
    for k, lv in IND_LEVELS.items():
        ind[k] = lv[rng.integers(len(lv))]
    ea = {}
    for k, lv in EA_LEVELS.items():
        ea[k] = lv[rng.integers(len(lv))]
    macro = ea.pop("macro")
    ea.update({0: dict(use_macro_filter=1, strict_longs=1, strict_shorts=1),
               1: dict(use_macro_filter=1, strict_longs=0, strict_shorts=0),
               2: dict(use_macro_filter=0, strict_longs=0, strict_shorts=0),
               3: dict(use_macro_filter=1, strict_longs=1, strict_shorts=0)}[macro])
    sess = ea.pop("session")
    ea.update({0: dict(use_session=0), 1: dict(use_session=1, start_hour=7, end_hour=18),
               2: dict(use_session=1, start_hour=7, end_hour=20), 3: dict(use_session=1, start_hour=12, end_hour=21)}[sess])
    lock = ea.pop("lock")
    ea.update({0: dict(lock_trigger_r=0.0, lock_r=0.0), 1: dict(lock_trigger_r=1.5, lock_r=0.5),
               2: dict(lock_trigger_r=2.0, lock_r=1.0), 3: dict(lock_trigger_r=3.0, lock_r=1.5)}[lock])
    part = ea.pop("partial")
    ea.update({0: dict(partial_r=0.0), 1: dict(partial_r=1.0, partial_pct=50), 2: dict(partial_r=2.0, partial_pct=50)}[part])
    if ea["trail_mode"] == 2:
        ind["trail_atr_mult"] = TRAIL_TIGHT[rng.integers(len(TRAIL_TIGHT))]
        if ind["trail_atr_mult"] >= ind["atr_mult"]:
            ea["trail_mode"] = 1
            ind["trail_atr_mult"] = 0.0
    for k in ("er_period", "atr_period", "min_dwell", "macro_ema", "macro_slope"):
        ind[k] = int(ind[k])
    return ind, ea


if __name__ == "__main__":
    rng = np.random.default_rng(SEED)
    jobs = []
    for tf in ["M5", "M15", "M30", "H1"]:
        for _ in range(N_PER_TF):
            ind, ea = sample(rng, tf)
            jobs.append((ind, ea, sweep.DEFAULT_WINDOWS))
    print("jobs:", len(jobs), flush=True)
    sweep.run_jobs(jobs, os.path.join(sweep.DATA, "stage3_random_joint.csv"), procs=4, chunk=5, tag="stage3")
