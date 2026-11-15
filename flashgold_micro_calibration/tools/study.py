"""Named studies: grids of input sets replayed on the whole feed, with per-split results.

usage: python -I study.py <study> <preset> <out csv> [spread_pts] [center.json]
studies: trailing, exits (around the preset), trailing_cal (around a calibrated centre)
"""
import itertools
import json
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


def _layer(dist):
    """Trail layer `dist` points behind the best price: distance = 3.3333 x max(spread, reference), capped."""
    return dict(distance=dist, InpUseTrailLayer=1, InpReferenceSpreadPts=dist * 0.3, InpTrailOuterCapPts=max(200.0, float(dist)))


def trailing_cal():
    """Every trailing mechanism on the entries of a calibrated centre (same entries, only the trailing differs)."""
    simple_off, layer_off = dict(UseTrailing=0), dict(InpUseTrailLayer=0)
    v = [dict(tag="none", **simple_off, **layer_off, **SETTLE_OFF)]
    # A. trail layer alone, by distance
    for dist in (30, 50, 75, 100, 125, 150, 200, 300, 400):
        v.append(dict(tag="layer", **_layer(dist), **simple_off, **SETTLE_OFF))
    # B. simple trailing alone: start x behind
    for start, behind in itertools.product([69, 100, 160, 270, 400], [30, 60, 110, 160, 200]):
        v.append(dict(tag="simple", UseTrailing=1, TrailStartPoints=start, TrailBehindPoints=behind, TrailStepPoints=10, **layer_off, **SETTLE_OFF))
    for step in (1, 5, 20, 40):
        v.append(dict(tag="simple step", UseTrailing=1, TrailStartPoints=160, TrailBehindPoints=110, TrailStepPoints=step, **layer_off, **SETTLE_OFF))
    # C. the burst-settle permission on top of one of each
    for quiet, frac, cap, pull in [(1500, 0.35, 2.0, 2.0), (500, 0.35, 2.0, 2.0), (1500, 0.6, 5.0, 1.0), (500, 0.6, 5.0, 0.5), (250, 1.0, 20.0, 0.5),
                                   (7000, 0.35, 100.0, 100.0)]:
        st = dict(InpWaitForBurstSettle=1, InpBurstSettleQuietMs=quiet, InpBurstSettleSpeedFraction=frac, InpBurstSettleMaxSpeedPipsSec=cap,
                  InpBurstSettlePullbackPips=pull)
        v.append(dict(tag="layer+settle", **_layer(100), **simple_off, **st))
        v.append(dict(tag="simple+settle", UseTrailing=1, TrailStartPoints=160, TrailBehindPoints=110, TrailStepPoints=10, **layer_off, **st))
    # D. both mechanisms together
    for start, behind in ((160, 110), (270, 60), (400, 200)):
        v.append(dict(tag="layer+simple", **_layer(100), UseTrailing=1, TrailStartPoints=start, TrailBehindPoints=behind, TrailStepPoints=10, **SETTLE_OFF))
    # E. trail layer with the stop and the target moved
    for dist, sl, tp in itertools.product((100, 200), (60, 90, 130), (300, 600, 1000, 1500)):
        v.append(dict(tag="layer x stop x target", **_layer(dist), **simple_off, StopSLPoints=sl, StopTPPoints=tp, **SETTLE_OFF))
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


def run(variants, preset, out, spread, center=None):
    feed = ticks.Feed("../data", spread)
    S = sim.Sim(feed)
    p0 = sweep.base(preset)
    if center:
        p0.update(json.load(open(center))["set"])
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
        m["sl_moved"] = float((df["sl_moved"] > 0).mean()) if len(df) else 0.0
        rows.append(m)
        if (k + 1) % 20 == 0:
            print(k + 1, len(variants), flush=True)
            pd.DataFrame(rows).to_csv(out, index=False)
    pd.DataFrame(rows).to_csv(out, index=False)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    name, preset, out = sys.argv[1], sys.argv[2], sys.argv[3]
    spread = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    center = sys.argv[5] if len(sys.argv) > 5 else None
    res = run({"trailing": trailing, "exits": exits, "trailing_cal": trailing_cal}[name](), preset, out, spread, center)
    cols = [c for c in ("tag", "n", "pf", "pf_is", "pf_val", "pf_test", "net", "win", "avg", "avg_win", "avg_loss", "dd") if c in res.columns]
    print(res.sort_values("pf", ascending=False)[cols].head(25).round(3).to_string())
