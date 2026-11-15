"""Search space over the EA's own inputs (so every result loads as a .set). Values are in gold
units; C.to_symbol() applies the BTCUSD transform. `L0` is the with-trend lot at factor 1 and
1000 USD: fixed lot (CushionEnabled=true) -> LotsWithTrend = L0/3 with CushionBaseUSD 3000 /
ReferenceBalanceUSD 1000 as shipped; balance-scaled lot (CushionEnabled=false) -> LotsWithTrend = L0."""
import numpy as np

CHOICES = dict(
    MainTimeframe=[3, 5, 6, 10, 15, 30],
    UpdateTrendInsideBasket=[0, 1],
    Against=[0.0, 0.1, 0.3, 0.5],                 # LotsAgainstTrend as a fraction of LotsWithTrend
    Cross=[(220.0, 110.0), (40.0, 40.0), (20.0, 20.0), (10.0, 10.0)],
    StopCooldownMinutes=[0, 60, 240, 720, 1440],
    Hours=[(0.0, 12.0), (0.0, 24.0), (6.0, 18.0), (12.0, 24.0), (0.0, 8.0), (7.0, 20.0)],
    MaxBasketAgeMinutes=[360, 720, 1440, 2880, 5760],
    MinVolFactor=[0.0, 1.5, 2.0, 2.5, 3.0, 3.5],
    VolLotGamma=[0.5, 1.0, 1.5],
    CushionEnabled=[0, 1],
    NewZonesEnabled=[1, 1, 1, 0],
)
RANGES = dict(   # (low, high, log-uniform?)
    MainFastEMA=(8, 40, True), SlowRatio=(1.8, 5.0, True), L0=(0.08, 0.6, True),
    MinMoveBetweenOrders=(0.2, 2.0, True), NewZonePaddingPrice=(1.0, 10.0, True),
    TrailArmUSD=(15.0, 150.0, True), GiveFrac=(0.02, 0.6, True), FloorFrac=(0.0, 0.5, False),
    CycleLossPct=(2.0, 15.0, True),
)
INT = {"MainFastEMA"}


def draw(rng):
    g = {k: v[rng.integers(len(v))] for k, v in CHOICES.items()}
    for k, (lo, hi, lg) in RANGES.items():
        x = np.exp(rng.uniform(np.log(lo), np.log(hi))) if lg else rng.uniform(lo, hi)
        g[k] = int(round(x)) if k in INT else float(x)
    return g


def shipped_gene():
    return dict(MainTimeframe=6, UpdateTrendInsideBasket=1, Against=0.1, Cross=(220.0, 110.0),
                StopCooldownMinutes=240, Hours=(0.0, 12.0), MaxBasketAgeMinutes=2880, MinVolFactor=2.0,
                VolLotGamma=1.0, CushionEnabled=1, NewZonesEnabled=1, MainFastEMA=20, SlowRatio=2.5,
                L0=0.30, MinMoveBetweenOrders=0.5, NewZonePaddingPrice=4.0, TrailArmUSD=50.0,
                GiveFrac=0.04, FloorFrac=0.02, CycleLossPct=8.0)


def neighbours(g):
    """One-input-at-a-time moves for hill climbing."""
    out = []
    for k, v in CHOICES.items():
        for c in v:
            if c != g[k]:
                n = dict(g); n[k] = c; out.append(n)
    for k, (lo, hi, lg) in RANGES.items():
        for f in (0.7, 0.85, 1.18, 1.43):
            x = g[k] * f if (lg or g[k] != 0) else (hi - lo) * 0.1 * f
            x = min(hi, max(lo, x))
            if k in INT:
                x = int(round(x))
            if x != g[k]:
                n = dict(g); n[k] = x; out.append(n)
    return out


def to_params(g, shipped):
    """gene -> EA inputs in gold units."""
    p = dict(shipped)
    p["MainTimeframe"] = p["MicroTimeframe"] = g["MainTimeframe"]
    p["MainFastEMA"] = int(g["MainFastEMA"])
    p["MainSlowEMA"] = int(round(g["MainFastEMA"] * g["SlowRatio"]))
    p["UpdateTrendInsideBasket"] = g["UpdateTrendInsideBasket"]
    p["CushionEnabled"] = g["CushionEnabled"]
    p["LotsWithTrend"] = round(g["L0"] / 3.0 if g["CushionEnabled"] else g["L0"], 4)
    p["LotsAgainstTrend"] = max(0.0001, round(p["LotsWithTrend"] * g["Against"], 4))
    p["CrossAboveCenter"], p["CrossBelowCenter"] = g["Cross"]
    p["MinMoveBetweenOrders"] = round(g["MinMoveBetweenOrders"], 2)
    p["NewZonesEnabled"] = g["NewZonesEnabled"]
    p["NewZonePaddingPrice"] = round(g["NewZonePaddingPrice"], 2)
    p["TrailArmUSD"] = round(g["TrailArmUSD"], 1)
    p["TrailGivebackUSD"] = round(max(0.5, g["TrailArmUSD"] * g["GiveFrac"]), 1)
    p["TrailFloorUSD"] = round(g["TrailArmUSD"] * g["FloorFrac"], 1)
    p["CycleLossPct"] = round(g["CycleLossPct"], 1)
    p["StopCooldownMinutes"] = g["StopCooldownMinutes"]
    p["EntryHourFrom"], p["EntryHourTo"] = g["Hours"]
    p["MaxBasketAgeMinutes"] = g["MaxBasketAgeMinutes"]
    p["MinVolFactor"] = g["MinVolFactor"]
    p["VolLotGamma"] = g["VolLotGamma"]
    return p
