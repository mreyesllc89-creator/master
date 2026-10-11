"""Stage 2b: full factorial of the EA factors that helped in stage 2, on the stage-1 picks."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sweep, rt_model as rt
from stage2 import top_indicators
picks = top_indicators(os.path.join(sweep.DATA, "stage1_indicator_grid.csv"), per_tf=6)
ea_grid = []
for sess in [dict(use_session=0), dict(use_session=1, start_hour=7, end_hour=18), dict(use_session=1, start_hour=7, end_hour=20)]:
    for be in [dict(use_be=0), dict(use_be=1, be_r=1.5)]:
        for lock in [dict(lock_trigger_r=0.0), dict(lock_trigger_r=2.0, lock_r=1.0)]:
            for step in [0, 50]:
                for ss in [1, 0]:
                    for msa in [1.0, 1.5]:
                        d = dict(trail_step_pts=step, strict_shorts=ss, min_stop_atr=msa); d.update(sess); d.update(be); d.update(lock)
                        ea_grid.append(d)
jobs = sweep.make_jobs(picks, ea_grid, sweep.DEFAULT_WINDOWS)
print("jobs:", len(jobs), flush=True)
sweep.run_jobs(jobs, os.path.join(sweep.DATA, "stage2b_factorial.csv"), procs=2, chunk=8, tag="stage2b")
