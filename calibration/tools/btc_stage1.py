"""BTC stage 1: per-method signal grid x core EA risk grid, all timeframes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import btc_sweep as sw
sig = sw.signal_grid()
ea = list(sw.grid(stop_atr=[1.5, 2.5, 3.5], trail_atr=[0.0, 2.0, 3.5, 5.0], tp_r=[0.0, 2.0, 4.0, 8.0]))
jobs = sw.make_jobs(sig, ea)
print("signal configs:", len(sig), "ea combos:", len(ea), "jobs:", len(jobs), flush=True)
sw.run_jobs(jobs, os.path.join(sw.DATA, "btc_stage1.csv"), procs=4, chunk=12, tag="btc1")
