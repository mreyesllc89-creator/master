"""Resume stage 1: run only the indicator combinations missing from the saved CSV."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, sweep
from stage1_grid import ind_grid

out = os.path.join(sweep.DATA, "stage1_indicator_grid.csv")
done = pd.read_csv(out)
key = ["chart_tf", "er_period", "enter", "exit", "atr_period", "atr_mult", "min_dwell", "shock_mult"]
FLOATS = {"enter", "exit", "atr_mult", "shock_mult"}


def norm(vals):
    return tuple(f"{float(v):.4f}" if k in FLOATS else str(int(v)) if k != "chart_tf" else str(v) for k, v in zip(key, vals))


done_keys = set(norm(r) for r in done[key].values)
todo = [g for g in ind_grid if norm([g[k] for k in key]) not in done_keys]
print("already done:", len(done), "todo:", len(todo), flush=True)
jobs = sweep.make_jobs(todo, [dict()], sweep.DEFAULT_WINDOWS)
df = sweep.run_jobs(jobs, os.path.join(sweep.DATA, "stage1_rest.csv"), procs=4, chunk=5, tag="stage1rest")
pd.concat([done, df]).to_csv(out, index=False)
print("[stage1] done (resumed)", flush=True)
