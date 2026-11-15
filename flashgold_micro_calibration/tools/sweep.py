"""Helpers to evaluate many input sets against a feed."""
import time

import numpy as np
import pandas as pd

import params
import sim

# calibrated to the author's real fills (see REPORT.md, "Execution model"): 74% of real stop fills are
# exact, limits and targets fill at the market, market orders reach the server after about 150 ms
REAL_FILLS = {"X_FillSnapPts": 10.0, "X_LimitAtMarket": 1.0, "X_LatencyMs": 150.0}
# what the Strategy Tester does without an execution delay: orders fill on the tick that sent them
TESTER_FILLS = {"X_FillSnapPts": 10.0, "X_LimitAtMarket": 1.0, "X_LatencyMs": 0.0}
# strict: every stop fills at the next quote, limits and targets get no price improvement, slow orders
STRICT_FILLS = {"X_FillSnapPts": 0.0, "X_LimitAtMarket": 0.0, "X_LatencyMs": 250.0}


def base(preset="FlashGold_NativeReference", fills=REAL_FILLS, **over):
    p = params.from_set(f"../shipped_presets/{preset}_DISABLED.set")
    p.update(fills)
    p.update(over)
    return p


def evaluate(S, p0, variants, extra_cols=None, verbose=False):
    """variants = list of dicts of overrides. Returns one metrics row per variant."""
    rows = []
    t0 = time.time()
    for k, v in enumerate(variants):
        p = dict(p0)
        p.update(v)
        df = S.run(p)
        m = sim.metrics(df)
        m.update({kk: vv for kk, vv in v.items()})
        if extra_cols:
            m.update(extra_cols(df))
        rows.append(m)
        if verbose and (k + 1) % 50 == 0:
            print(f"{k + 1}/{len(variants)} {time.time() - t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


def split_metrics(df, cut_ms):
    """Metrics before / after a cut time (in-sample / out-of-sample)."""
    a = sim.metrics(df[df.entry_ms < cut_ms])
    b = sim.metrics(df[df.entry_ms >= cut_ms])
    return {**{f"is_{k}": v for k, v in a.items()}, **{f"oos_{k}": v for k, v in b.items()}}
