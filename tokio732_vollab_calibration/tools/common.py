"""Data loading, indicators, parameter handling and the run wrapper for the Tokio732_VolLab port."""
import glob
import os

import numpy as np
import pandas as pd

import engine as E

DATA = os.environ.get("TOKIO_DATA", "data")

# Symbol specification and the level every historical year is rescaled to (see REPORT.md):
# target = median H1 true range of the July-August 2026 export.
SPEC = {
    "XAUUSD": dict(pvl=100.0, lot_min=0.01, lot_step=0.01, leverage=500.0, target_tr=14.985,
                   spread=0.11, step=0.05),
    "BTCUSD": dict(pvl=1.0, lot_min=0.01, lot_step=0.01, leverage=400.0, target_tr=256.775,
                   spread=17.03, step=0.85),
}
K_BTC = SPEC["BTCUSD"]["target_tr"] / SPEC["XAUUSD"]["target_tr"]   # 17.1

# The shipped preset (TOKIO_3614_T50_PREDETERMINADO.set), reachable inputs only.
SHIPPED = dict(
    MainTimeframe=6, MainFastEMA=20, MainSlowEMA=50, MicroTimeframe=6, MicroFastEMA=9,
    MicroSlowEMA=21, TrendSource=3, UpdateTrendInsideBasket=1,
    LotsWithTrend=0.10, LotsAgainstTrend=0.01, LotMultiplier=1.0, ReferenceBalanceUSD=1000.0,
    CrossAboveCenter=220.0, CrossBelowCenter=110.0, MinMoveBetweenOrders=0.5,
    TrailingEnabled=1, TrailArmUSD=50.0, TrailGivebackUSD=2.0, TrailFloorUSD=1.0,
    VolLotEnabled=1, VolLotGamma=1.0, VolDistEnabled=1, VolATRRef=4.74, VolATRPeriod=14,
    VolATRTimeframe=60, VolFactorMin=0.25, VolFactorMax=8.0, MinVolFactor=2.0,
    CushionEnabled=1, CushionBaseUSD=3000.0, StopCooldownMinutes=240, EntryHourFrom=0.0,
    EntryHourTo=12.0, MaxBasketAgeMinutes=2880, CycleLossPctEnabled=1, CycleLossPct=8.0,
    NewZonesEnabled=1, NewZonePaddingPrice=4.0, ExitSlippageReservePrice=0.5,
)
PRICE_KEYS = ["CrossAboveCenter", "CrossBelowCenter", "MinMoveBetweenOrders", "VolATRRef",
              "NewZonePaddingPrice", "ExitSlippageReservePrice"]


def shipped_for(symbol):
    """Shipped preset; for BTCUSD the scale-equivalent transform: price inputs x K, lots x 100/K
    (1 BTC contract instead of 100 oz), money inputs unchanged."""
    p = dict(SHIPPED)
    if symbol == "BTCUSD":
        for k in PRICE_KEYS:
            p[k] *= K_BTC
        p["LotsWithTrend"] *= 100.0 / K_BTC
        p["LotsAgainstTrend"] *= 100.0 / K_BTC
    return p


def years(symbol):
    return sorted(int(os.path.basename(f).split("_")[-1][:4])
                  for f in glob.glob(os.path.join(DATA, f"{symbol.lower()}_m1_*.npz")))


_cache = {}


def load(symbol, year, spread_mult=1.0, rescale=True):
    """M1 bid/ask for one year. Historical years are multiplied by a constant so that their
    median H1 true range equals the 2026 level, and get the 2026 spread around the mid.
    2026 is used as recorded (real bid/ask, no rescale)."""
    key = (symbol, year, spread_mult, rescale)
    if key in _cache:
        return _cache[key]
    z = np.load(os.path.join(DATA, f"{symbol.lower()}_m1_{year}.npz"))
    d = {k: z[k].astype(np.float64) for k in ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]}
    d["t"] = z["t"].astype(np.int64)
    sp = SPEC[symbol]
    c = 1.0
    if year != 2026 and rescale:
        c = sp["target_tr"] / median_tr(d)
        half = 0.5 * sp["spread"] * spread_mult
        for x in "ohlc":
            m = 0.5 * (d["b" + x] + d["a" + x]) * c
            d["b" + x] = m - half; d["a" + x] = m + half
    elif spread_mult != 1.0:
        for x in "ohlc":
            m = 0.5 * (d["b" + x] + d["a" + x]); h = 0.5 * (d["a" + x] - d["b" + x]) * spread_mult
            d["b" + x] = m - h; d["a" + x] = m + h
    d["c"] = c; d["sym"] = symbol; d["year"] = year
    _cache[key] = d
    return d


def _bars(d, minutes):
    off = 3 * 86400 if minutes == 10080 else 0       # weekly bars start on Monday
    k = (d["t"] + off) // (minutes * 60)
    brk = np.flatnonzero(np.diff(k)) + 1
    st = np.concatenate([[0], brk]); en = np.concatenate([brk, [len(k)]]) - 1
    return k, st, en


def median_tr(d):
    _, st, en = _bars(d, 60)
    h = np.maximum.reduceat(d["bh"], st); l = np.minimum.reduceat(d["bl"], st); c = d["bc"][en]
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return float(np.median(tr))


def atr_closed(d, minutes, period):
    """Wilder ATR of the last CLOSED bar of the ATR timeframe, per M1 bar (VolFactor732)."""
    key = ("atr", id(d), minutes, period)
    if key in _cache:
        return _cache[key]
    _, st, en = _bars(d, minutes)
    h = np.maximum.reduceat(d["bh"], st); l = np.minimum.reduceat(d["bl"], st); c = d["bc"][en]
    tr = np.empty(len(h)); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    a = np.zeros(len(h))
    if len(h) > period + 1:
        a[period] = tr[1:period + 1].mean()
        for i in range(period + 1, len(h)):
            a[i] = (a[i - 1] * (period - 1) + tr[i]) / period
    prev = np.concatenate([[0.0], a[:-1]])           # value of the previous (closed) bar
    out = np.repeat(prev, en - st + 1)
    _cache[key] = out
    return out


def _history(symbol, year):
    """Raw bid closes of the run of consecutive years that contains `year`."""
    ys = years(symbol)
    run = [y for y in ys if all(z in ys for z in range(min(y, year), max(y, year) + 1))]
    key = ("hist", symbol, run[0])
    if key not in _cache:
        parts = [np.load(os.path.join(DATA, f"{symbol.lower()}_m1_{y}.npz")) for y in run]
        _cache[key] = dict(t=np.concatenate([z["t"].astype(np.int64) for z in parts]),
                           bc=np.concatenate([z["bc"].astype(np.float64) for z in parts]))
    return _cache[key]


def trend_closed(d, p):
    """EMA direction on closed bars (GetTrend/Direction), per M1 bar."""
    key = ("tr", id(d), p["MainTimeframe"], p["MainFastEMA"], p["MainSlowEMA"], p["MicroTimeframe"],
           p["MicroFastEMA"], p["MicroSlowEMA"], p["TrendSource"])
    if key in _cache:
        return _cache[key]

    def direction(minutes, fast, slow):
        # EMAs run on the raw, continuous history of the symbol (all consecutive years), so slow
        # timeframes are warmed up; a constant price rescale does not change the sign of a cross.
        full = _history(d["sym"], d["year"])
        _, st, en = _bars(full, int(minutes))
        c = pd.Series(full["bc"][en])
        f = c.ewm(span=int(fast), adjust=False).mean().values
        s = c.ewm(span=int(slow), adjust=False).mean().values
        x = np.sign(f - s).astype(np.int8)
        x[:int(max(fast, slow))] = 0                 # warm-up
        prev = np.concatenate([[0], x[:-1]]).astype(np.int8)
        m1 = np.repeat(prev, en - st + 1)
        i = int(np.searchsorted(full["t"], d["t"][0]))
        return m1[i:i + len(d["t"])]

    main = direction(p["MainTimeframe"], p["MainFastEMA"], p["MainSlowEMA"])
    micro = direction(p["MicroTimeframe"], p["MicroFastEMA"], p["MicroSlowEMA"])
    src = int(p["TrendSource"])
    if src == 0:
        out = main
    elif src == 1:
        out = micro
    elif src == 2:
        out = np.where(main == micro, main, 0).astype(np.int8)
    else:
        out = np.where(main != 0, main, micro).astype(np.int8)
    if len(_cache) > 400:
        for k in [k for k in _cache if k[0] == "tr"]:
            del _cache[k]
    _cache[key] = out
    return out


def pvec(p, symbol, start_balance=1000.0, slip=0.0, coarse=False, step=None):
    sp = SPEC[symbol]
    P = np.zeros(E.NP)
    P[E.LOTS_WITH] = p["LotsWithTrend"]; P[E.LOTS_AGAINST] = p["LotsAgainstTrend"]
    P[E.CROSS_ABOVE] = p["CrossAboveCenter"]; P[E.CROSS_BELOW] = p["CrossBelowCenter"]
    P[E.MIN_MOVE] = p["MinMoveBetweenOrders"]; P[E.TRAIL_ON] = p["TrailingEnabled"]
    P[E.TRAIL_ARM] = p["TrailArmUSD"]; P[E.TRAIL_GIVE] = p["TrailGivebackUSD"]
    P[E.TRAIL_FLOOR] = p["TrailFloorUSD"]; P[E.VOL_LOT_ON] = p["VolLotEnabled"]
    P[E.VOL_GAMMA] = p["VolLotGamma"]; P[E.VOL_DIST_ON] = p["VolDistEnabled"]
    P[E.VOL_REF] = p["VolATRRef"]; P[E.VF_MIN] = p["VolFactorMin"]; P[E.VF_MAX] = p["VolFactorMax"]
    P[E.MIN_VF] = p["MinVolFactor"]; P[E.CUSHION_ON] = p["CushionEnabled"]
    P[E.CUSHION_BASE] = p["CushionBaseUSD"]; P[E.REF_BAL] = p["ReferenceBalanceUSD"]
    P[E.LOT_MULT] = p["LotMultiplier"]; P[E.COOLDOWN_MIN] = p["StopCooldownMinutes"]
    P[E.HOUR_FROM] = p["EntryHourFrom"]; P[E.HOUR_TO] = p["EntryHourTo"]
    P[E.MAX_AGE_MIN] = p["MaxBasketAgeMinutes"]; P[E.LOSS_ON] = p["CycleLossPctEnabled"]
    P[E.LOSS_PCT] = p["CycleLossPct"]; P[E.ZONES_ON] = p["NewZonesEnabled"]
    P[E.ZONE_PAD] = p["NewZonePaddingPrice"]; P[E.RESERVE] = p["ExitSlippageReservePrice"]
    P[E.UPDATE_TREND] = p["UpdateTrendInsideBasket"]
    P[E.PVL] = sp["pvl"]; P[E.LOT_MIN] = sp["lot_min"]; P[E.LOT_STEP] = sp["lot_step"]
    P[E.START_BAL] = start_balance; P[E.LEVERAGE] = sp["leverage"]; P[E.STEP] = sp["step"]
    P[E.SLIP] = slip
    if step is not None:
        P[E.STEP] = step
    if coarse:
        P[E.STEP] = -1.0          # one evaluation per M1 bar, at the recorded close          # decisions only at the four OHLC points of each M1 bar
    return P


_out = np.zeros((20000, 8))


def backtest(p, symbol, year, start_balance=1000.0, slip=0.0, spread_mult=1.0, t_from=None,
             baskets=False, coarse=False, step=None):
    d = load(symbol, year, spread_mult)
    tr = trend_closed(d, p)
    atr = atr_closed(d, int(p["VolATRTimeframe"]), int(p["VolATRPeriod"]))
    sl = slice(None)
    if t_from is not None:
        sl = slice(int(np.searchsorted(d["t"], t_from)), None)
    nb, bal, dd, mineq, orders = E.run(d["t"][sl], d["bo"][sl], d["bh"][sl], d["bl"][sl], d["bc"][sl],
                                       d["ao"][sl], d["ah"][sl], d["al"][sl], d["ac"][sl],
                                       tr[sl], atr[sl], pvec(p, symbol, start_balance, slip, coarse, step), _out)
    res = dict(n=nb, final=bal, net=bal - start_balance, dd=dd, min_eq=mineq, orders=orders)
    b = _out[:min(nb, len(_out))]
    res["r"] = (b[:, 3] / np.maximum(b[:, 7], 1e-9)).copy()   # basket net / balance at open
    res["reason"] = b[:, 2].astype(int).copy()
    if baskets:
        res["baskets"] = pd.DataFrame(b.copy(), columns=["start", "end", "reason", "net", "mae", "mfe",
                                                         "vf", "balance_before"])
        res["baskets"]["reason"] = [E.REASONS[int(x)] for x in res["baskets"]["reason"]]
    return res
