# Calibration toolkit

Python replica of the RegimeTrend indicator + EA and the sweep scripts used
for `REPORT.md`. Needs Python 3.11+, numpy, pandas, numba, matplotlib,
tabulate.

```
tools/rt_model.py          indicator + EA replica, numba event loop, summary stats
tools/sweep.py             multiprocessing job runner (IS / OOS / all windows)
tools/stage1_grid.py       the 11,664-combination indicator grid
tools/stage1.py            stage 1 runner (stage1_resume.py resumes a partial run)
tools/stage2.py            one-factor EA variants on the stage 1 picks
tools/stage2b.py           factorial of the helpful EA factors
tools/stage3.py            joint random search over all inputs
tools/final_eval.py        per-window / per-year / cost-stress evaluation, chart, .set files
tools/setfile.py           MT5 .set writer (v1.50 input names)
tools/analyze.py           report tables
tools/baseline.py          defaults on every chart timeframe
tools/convert_ticks.py     Dukascopy tick CSV -> M1 bid/ask npz (FX-Data mirror layout)
tools/convert_mt5_ticks.py MT5 tick export (Ticks tab) -> M1 bid/ask npz
tools/fetch_years.sh       clones the FX-Data XAUUSD year branches and converts them
```

Data files are expected in `calibration/data/xauusd_m1_<year>.npz` (UTC
timestamps, bid and ask OHLC per minute). `fetch_years.sh` builds 2011-2018
from the public `FX-Data/FX-Data-XAUUSD-DS` repository; your own MT5 tick
export converts with:

```
python -I tools/convert_mt5_ticks.py 3 data/xauusd_m1_2026.npz "XAUUSD-ECNc_*.csv"
```

(`3` = your broker's UTC offset while the export was made; summer = 3,
winter = 2 for a GMT+2/+3 broker.) Then:

```
python -I tools/baseline.py
python -I tools/stage1.py && python -I tools/stage2.py && python -I tools/stage2b.py && python -I tools/stage3.py 6000
python -I tools/final_eval.py results/final_configs.json results/final
```

The scripts read `DATA` from `sweep.py`, which points at `../data` relative
to the tools folder.

Results of the run documented in the report are in `results/`:
`stage1_indicator_grid.csv`, `stage2_ea_variants.csv`, `stage2_effects.csv`,
`stage2b_factorial.csv`, `stage3_random_joint.csv.gz`, `baseline.csv`, and
`final/` (summary, per-year, trades per config, equity chart, `.set` files).
