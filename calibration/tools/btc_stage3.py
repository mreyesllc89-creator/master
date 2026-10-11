"""BTC stage 3: joint random search over signal + EA inputs, per timeframe."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_sweep as sw, btc_model as bm

N_PER_TF = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
rng = np.random.default_rng(20261011)
L = dict(method=[0, 1, 2, 2, 4, 5], length=[7, 10, 14, 20, 30, 50, 100], exit_bars=[5, 10, 20],
         efficiency=[0.10, 0.15, 0.20, 0.30, 0.40], pullback_ema=[10, 20, 50], clearance=[0.0, 0.1, 0.2, 0.5],
         stop_atr=[1.0, 1.5, 2.0, 2.5, 3.5, 5.0], trail_atr=[0.0, 1.5, 2.0, 3.5, 5.0, 7.0], tp_r=[0.0, 0.0, 2.0, 4.0, 8.0],
         use_be=[0, 0, 1], be_r=[0.5, 1.0, 2.0], trail_activate_r=[0.0, 0.0, 1.0, 2.0],
         lock=[0, 0, 1, 2], trail_mode=[1, 1, 2], partial=[0, 0, 1], er_exit=[0.0, 0.0, 0.10, 0.15],
         max_hold_bars=[0, 0, 0, 48, 200], direction=[0, 0, 0, 1, 2], exit_rule=[0, 0, 1])
pick = lambda k: L[k][rng.integers(len(L[k]))]
jobs = []
for tf in ["M15", "M30", "H1", "H4"]:
    for _ in range(N_PER_TF):
        sig = dict(bm.SIG_DEFAULTS); sig["chart_tf"] = tf
        for k in ("method", "length", "exit_bars", "efficiency", "pullback_ema", "clearance"):
            sig[k] = pick(k)
        ea = {k: pick(k) for k in ("stop_atr", "trail_atr", "tp_r", "use_be", "be_r", "trail_activate_r", "trail_mode", "er_exit", "max_hold_bars", "exit_rule")}
        lk = pick("lock"); ea.update({0: dict(lock_trigger_r=0.0, lock_r=0.0), 1: dict(lock_trigger_r=1.5, lock_r=0.5), 2: dict(lock_trigger_r=2.0, lock_r=1.0)}[lk])
        ea.update({0: dict(partial_r=0.0), 1: dict(partial_r=1.5, partial_pct=50)}[pick("partial")])
        ea.update({0: {}, 1: dict(long_only=1), 2: dict(short_only=1)}[pick("direction")])
        jobs.append((sig, ea, sw.DEFAULT_WINDOWS))
print("jobs:", len(jobs), flush=True)
sw.run_jobs(jobs, os.path.join(sw.DATA, "btc_stage3.csv"), procs=4, chunk=4, tag="btc3")
