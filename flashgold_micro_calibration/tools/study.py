"""Named studies: grids of input sets replayed on the whole feed, with per-split results.

usage: python -I study.py <study> <preset> <out csv> [spread_pts]
studies: trailing, exits, joint
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import numpy as np
import pandas as pd

import engine
import oat
import sim
import sweep
import ticks

SETTLE_OFF = {"InpWaitForBurstSettle": 0}
SETTLE_SRC = {"InpWaitForBurstSettle": 1, "InpBurstSettleQuietMs": 1500, "InpBurstSettleSpeedFraction": 0.35,
              "InpBurstSettleMaxSpeedPipsSec": 2.0, "InpBurstSettlePullbackPips": 2.0}


def trailing():
    """The three trailing mechanisms on unchanged entries."""
    v = [dict(tag="preset (trailing cannot act: start 270 > TP, settle needs a 100 pip pullback)")]
    # A. simple trailing, burst-settle off
    for start, behind, step in itertools.product([69, 80, 100, 130, 160], [20, 30, 40, 60, 80, 110], [10]):
        if behind >= start + 90:
            continue
        v.append(dict(tag="simple", UseTrailing=1, TrailStartPoints=start, TrailBehindPoints=behind, TrailStepPoints=step, **SETTLE_OFF))
    for step in (1, 5, 20, 40):
        v.append(dict(tag="simple", UseTrailing=1, TrailStartPoints=80, TrailBehindPoints=40, TrailStepPoints=step, **SETTLE_OFF))
    # B. simple trailing with the burst-settle permission (source defaults and variants)
    for start, behind in itertools.product([69, 100], [30, 60]):
        for quiet, frac, cap, pull in [(1500, 0.35, 2.0, 2.0), (500, 0.35, 2.0, 2.0), (1500, 0.6, 5.0, 1.0), (500, 0.6, 5.0, 0.5),
                                       (250, 1.0, 20.0, 0.5), (7000, 0.35, 100.0, 2.0)]:
            v.append(dict(tag="simple+settle", UseTrailing=1, TrailStartPoints=start, TrailBehindPoints=behind, TrailStepPoints=10,
                          InpWaitForBurstSettle=1, InpBurstSettleQuietMs=quiet, InpBurstSettleSpeedFraction=frac,
                          InpBurstSettleMaxSpeedPipsSec=cap, InpBurstSettlePullbackPips=pull))
    # C. spread-scaled trail layer (distance = clamp(orderDistance, min, max) * max(spread, reference), capped)
    for ref, mn in itertools.product([15, 30], [1.0, 2.0, 3.3333333, 5.0]):
        v.append(dict(tag="layer", InpUseTrailLayer=1, InpReferenceSpreadPts=ref, internalMinTrailing=mn,
                      internalMaxTrailing=mn * 2.0, internalMultiplier=2.0, internalOrderDistance=mn, **SETTLE_OFF))
    for ref, mn in itertools.product([30], [2.0, 3.3333333]):
        v.append(dict(tag="layer+settle", InpUseTrailLayer=1, InpReferenceSpreadPts=ref, internalMinTrailing=mn,
                      internalMaxTrailing=mn * 2.0, internalMultiplier=2.0, internalOrderDistance=mn, **SETTLE_SRC))
    # D. the same trailing ideas with the fixed 100 point speed exit switched off and a far target
    for start, behind in itertools.product([69, 100, 160], [30, 60, 110]):
        for tp in (180, 600):
            v.append(dict(tag="simple, no speed exit", UseTrailing=1, TrailStartPoints=start, TrailBehindPoints=behind,
                          TrailStepPoints=10, UseSpeedProfitExit=0, StopTPPoints=tp, LimitTPPoints=tp, MarketTPPoints=tp, **SETTLE_OFF))
    return v


def exits():
    """Stop / target / profit-exit geometry on unchanged entries."""
    v = [dict(tag="preset")]
    for sl in (40, 60, 90, 130, 200, 300, 450):
        for tp in (120, 180, 300, 600, 1500):
            for se in (0, 100, 200):
                d = dict(tag="geometry", StopSLPoints=sl, LimitSLPoints=sl, MarketSLPoints=sl, StopTPPoints=tp, LimitTPPoints=tp,
                         MarketTPPoints=tp, UseSpeedProfitExit=1 if se else 0)
                if se:
                    d["SpeedProfitExitPoints"] = se
                v.append(d)
    return v


def run(variants, preset, out, spread):
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    p0 = sweep.base(preset)
    rows = []
    for k, v in enumerate(variants):
        p = dict(p0)
        p.update({a: b for a, b in v.items() if a != "tag"})
        df = S.run(p)
        m = sim.metrics(df)
        m.update(oat.split_row(df))
        m.update(v)
        L = df["reason"].map(engine.REASON).value_counts()
        m["exits"] = " ".join(f"{a}:{b}" for a, b in L.items())
        rows.append(m)
        if (k + 1) % 20 == 0:
            print(k + 1, len(variants), flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)
    pd.DataFrame(rows).to_csv(out, index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    name, preset, out = sys.argv[1], sys.argv[2], sys.argv[3]
    spread = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    res = run({"trailing": trailing, "exits": exits}[name](), preset, out, spread)
    cols = [c for c in ("tag", "n", "pf", "pf_is", "pf_val", "pf_test", "net", "win", "avg", "avg_win", "avg_loss") if c in res.columns]
    print(res.sort_values("pf", ascending=False)[cols].head(25).round(3).to_string())
