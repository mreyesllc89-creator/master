"""Search space of the calibration: what is sampled, and the split of the data."""
import numpy as np
import pandas as pd

IS_START = int(pd.Timestamp("2023-11-01", tz="UTC").timestamp())
IS_MID = int(pd.Timestamp("2024-11-01", tz="UTC").timestamp())
IS_END = int(pd.Timestamp("2025-11-01", tz="UTC").timestamp())     # in-sample: 2023-11 .. 2025-10
OOS_END = int(pd.Timestamp("2026-11-12", tz="UTC").timestamp())    # out-of-sample: 2025-11 .. 2026-11-11
TIMEFRAMES = (30, 60, 120, 240)
BASE_SPREAD = 15.0     # dollars; a typical retail BTCUSD CFD quote. Stressed later at 5 and 30.


def sample_signal(rng):
    return dict(rsi_len=int(rng.choice([7, 10, 14, 21])), fast_len=int(rng.choice([1, 2, 3, 5])),
                min_aligned=int(rng.choice([0, 1, 2, 3])), burst_atr=float(np.round(rng.uniform(0.2, 2.0), 2)),
                entry_dist_atr=float(np.round(rng.uniform(0.0, 0.6), 2)), atr_len=14,
                use_zone_filter=bool(rng.random() < 0.85))


def sample_exit(rng):
    runner = bool(rng.random() < 0.5)
    use_trail = (not runner) and bool(rng.random() < 0.35)
    return dict(sl_atr=float(np.round(np.exp(rng.uniform(np.log(0.3), np.log(4.0))), 2)), sl_abs=0.0,
                tp_r=float(rng.choice([1, 1.5, 2, 3, 4, 5, 6, 8])), runner=runner,
                part_pct=float(rng.choice([0.0, 0.3, 0.5])) if runner else 0.3, run_be=bool(rng.random() < 0.5),
                run_atr=float(np.round(rng.uniform(1.0, 6.0), 1)), run_abs=0.0, use_trail=use_trail,
                act_atr=float(np.round(rng.uniform(0.5, 3.0), 1)), act_abs=0.0,
                dst_atr=float(np.round(rng.uniform(0.5, 4.0), 1)), dst_abs=0.0,
                valid_bars=int(rng.choice([1, 2, 3, 5, 8])), allow_rev=bool(rng.random() < 0.5),
                exit_opp=bool(rng.random() < 0.25), direction=int(rng.choice([0, 0, 0, 1, -1])),
                max_held=int(rng.choice([0, 0, 12, 24, 48, 96])))
