"""The search space of the calibration: every input of the strategy that changes a trade.

Values are the grid points the random search draws from. A setting is a parameter dict for
amvi_engine.P(). Timeframes are minutes (1440 = 1D). Seconds timeframes are not in the space:
there is no long seconds history to test them on (see README).
"""
import numpy as np

AMVI_TFS = (1, 5, 15, 30, 60, 240, 1440)
FILTER_TFS = (1, 5, 15, 30, 60, 240, 1440)
CHART_TFS = (1, 2, 3, 5, 10, 15, 30, 60, 240)

GRID = dict(
    fast=(5, 7, 10, 14),
    slow=(50, 100, 200),
    sd=(10, 20, 30),
    cr=(10, 20, 30),
    norm=(100, 200, 400),
    weights=("default", "atr", "equal", "ratio", "stdev"),
    high=(50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0),
    low=(20.0, 30.0, 40.0),
    band=(0.0, 0.25, 0.5, 1.0, 1.5, 2.0),
    burst_atr=(0.25, 0.5, 1.0, 1.5),
    min_aligned=(0, 1, 2, 3),
    sl=(0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0),
    tp=(0.0, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0),
    trail_act=(0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0),
    trail_off=(0.5, 1.0, 1.5, 2.0, 3.0, 4.0),
    max_bars=(0, 6, 12, 24, 48, 96, 192),
    wait=(0, 1, 2, 3, 5, 10, 20),
    exit_atr=(7, 14, 21, 30),
    perm_candles=(1, 2, 3, 6, 12),
    drift_bars=(30, 60, 120),
    entry_dist_atr=(0.1, 0.25, 0.5),
    tdi=((14, 2), (7, 2), (21, 2), (14, 3)),
)

WEIGHTS = dict(
    default=(0.35, 0.25, 0.25, 0.15),   # the script's defaults: ATR, ratio, stdev, candle range
    atr=(0.55, 0.15, 0.15, 0.15),
    equal=(0.25, 0.25, 0.25, 0.25),
    ratio=(0.20, 0.50, 0.15, 0.15),
    stdev=(0.20, 0.15, 0.50, 0.15),
)


def tf_allowed(chart_tf, t):
    """Timeframes the calibration may switch on for a chart timeframe:
      at or above the chart   whole multiples of it only. On a chart that straddles the other
                              timeframe's boundaries (5m on a 2m or 3m chart, 15m on a 10m chart)
                              the script reads a different bar live than after a reload;
      below the chart         divisors of at least 15 minutes only. TradingView keeps about
                              100,000 intrabars per request: 69 days of 1m, 347 days of 5m,
                              2.9 years of 15m. A setting built on 1m or 5m intrabars could not
                              be replayed in the Strategy Tester for more than that."""
    if t >= chart_tf:
        return t % chart_tf == 0
    return chart_tf % t == 0 and t >= 15


def parent_options(f_tf):
    """Parent timeframe: the filter timeframe itself (as calibrated before) or the next of
    1h / 4h / 1D above it."""
    higher = [t for t in (60, 240, 1440) if t > f_tf]
    return (f_tf, higher[0]) if higher else (f_tf,)


def zone_options(f_tf):
    """Child zones: the file's 1h / 2h / 4h, or the filter timeframe x1 / x2 / x4 when those
    are day-aligned timeframes."""
    opts = [(60, 120, 240)]
    if f_tf <= 60 and f_tf != 60:
        opts.append((f_tf, 2 * f_tf, 4 * f_tf))
    return opts


def draw(rng, chart_tf):
    """One random setting for a chart timeframe (dict of engine parameters plus 'weights')."""
    g = GRID
    c = lambda name: g[name][rng.integers(len(g[name]))]
    amvi_opts = [t for t in AMVI_TFS if tf_allowed(chart_tf, t)]
    k = min(int(rng.choice((1, 2, 3, 4), p=(0.35, 0.35, 0.25, 0.05))), len(amvi_opts))
    tfs = tuple(sorted(int(x) for x in rng.choice(amvi_opts, size=k, replace=False)))
    conf = int(rng.choice(np.arange(1, k + 1), p=_conf_p(k)))
    f_opts = sorted({t for t in FILTER_TFS if tf_allowed(chart_tf, t)} | {chart_tf})
    f_tf = int(f_opts[rng.integers(len(f_opts))])
    par = parent_options(f_tf)
    parent_tf = int(par[rng.integers(len(par))])
    min_aligned = int(rng.choice(g["min_aligned"], p=(0.6, 0.15, 0.15, 0.10)))
    zo = zone_options(f_tf)
    zones = zo[rng.integers(len(zo))] if min_aligned > 0 else zo[0]
    burst_only = rng.random() < 0.4
    w = c("weights")
    wA, wV, wS, wC = WEIGHTS[w]
    trail = rng.random() < 0.4
    vol_exit = rng.random() < 0.15
    lv_entry = rng.random() >= 0.7
    use_drift = rng.random() < 0.2
    side = rng.choice(("both", "buy", "sell"), p=(0.7, 0.15, 0.15))
    rsi_len, fast_len = g["tdi"][0] if rng.random() < 0.8 else g["tdi"][1 + rng.integers(len(g["tdi"]) - 1)]
    p = dict(
        fast=c("fast"), slow=c("slow"), sd=c("sd"), cr=c("cr"), norm=c("norm"),
        weights=w, wA=wA, wV=wV, wS=wS, wC=wC,
        high=c("high"), low=c("low") if vol_exit else 30.0, conf=conf, tfs=tfs,
        f_tf=f_tf, lv_mode="entry" if lv_entry else "close", band=c("band"),
        entry_dist_atr=c("entry_dist_atr") if lv_entry else 0.25,
        against=bool(rng.random() < 0.75), allow_buy=bool(side != "sell"), allow_sell=bool(side != "buy"),
        perm_candles=int(c("perm_candles")) if (burst_only and rng.random() < 0.3) else 0,
        check_open=bool(f_tf > chart_tf and rng.random() < 0.3),
        rsi_len=int(rsi_len), fast_len=int(fast_len),
        use_burst=bool(burst_only), any_combo=not burst_only,
        burst_atr=c("burst_atr") if burst_only else 0.5,
        use_drift=bool(use_drift), drift_bars=int(c("drift_bars")) if use_drift else 60,
        use_zones=bool(rng.random() < 0.85),
        parent_tf=parent_tf, min_aligned=min_aligned, zones=tuple(int(z) for z in zones),
        inverted=bool(rng.random() < 0.5),
        sl=c("sl"), tp=float(rng.choice(g["tp"], p=_tp_p())),
        trail=bool(trail), trail_act=c("trail_act") if trail else 1.5, trail_off=c("trail_off") if trail else 1.0,
        vol_exit=bool(vol_exit), max_bars=int(rng.choice(g["max_bars"], p=_mb_p())),
        wait=int(rng.choice(g["wait"], p=_wait_p())),
        exit_atr=int(g["exit_atr"][1] if rng.random() < 0.6 else c("exit_atr")),
    )
    return p


def _conf_p(k):
    return {1: (1.0,), 2: (0.7, 0.3), 3: (0.6, 0.3, 0.1), 4: (0.55, 0.3, 0.1, 0.05)}[k]


def _tp_p():
    n = len(GRID["tp"])
    return np.array([0.35] + [0.65 / (n - 1)] * (n - 1))


def _mb_p():
    n = len(GRID["max_bars"])
    return np.array([0.55] + [0.45 / (n - 1)] * (n - 1))


def _wait_p():
    n = len(GRID["wait"])
    return np.array([0.5] + [0.5 / (n - 1)] * (n - 1))


def normalize(p):
    """A setting as read back from JSON: tuples again, and inputs added to the space later
    filled with the script's defaults."""
    import amvi_engine
    q = dict(amvi_engine.DEFAULTS)
    q.update(p)
    q["tfs"] = tuple(int(x) for x in q["tfs"])
    q["zones"] = tuple(int(x) for x in q["zones"])
    return q


def engine_params(p):
    """Strip the bookkeeping keys so the dict can go to amvi_engine.P()."""
    return {k: v for k, v in normalize(p).items() if k != "weights"}


def filter_key(p):
    """Everything filter_arms() depends on (settings with the same key share one computation)."""
    p = normalize(p)
    return (p["f_tf"], p["lv_mode"], p["use_burst"], p["any_combo"], p["burst_atr"], p["use_drift"], p["drift_bars"],
            p["entry_dist_atr"], p["use_zones"], p["parent_tf"], p["min_aligned"], p["zones"], p["rsi_len"], p["fast_len"])


def neighbours(p, chart_tf):
    """Every setting one grid step away from p in one numeric input (for the plateau test):
    the AMVI periods and level, band, exits, wait, the filter's numeric inputs that are in use
    (minimum aligned zones, Candles, drift bars, entry distance), the number of timeframes
    that must be hot, plus the other weight presets and the other TDI lengths."""
    p = normalize(p)
    out = []
    for name in ("fast", "slow", "sd", "cr", "norm", "high", "band", "sl", "tp", "max_bars", "wait", "exit_atr"):
        vals = GRID[name]
        if name not in p or p[name] not in vals:
            continue
        i = vals.index(p[name])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = dict(p)
                q[name] = vals[j]
                out.append((name, q))
    if p["trail"]:
        for name in ("trail_act", "trail_off"):
            vals = GRID[name]
            i = vals.index(p[name])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vals):
                    q = dict(p)
                    q[name] = vals[j]
                    out.append((name, q))
    if p["use_burst"] and not p["any_combo"]:
        vals = GRID["burst_atr"]
        i = vals.index(p["burst_atr"])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = dict(p)
                q["burst_atr"] = vals[j]
                out.append(("burst_atr", q))
    if p["vol_exit"]:
        vals = GRID["low"]
        i = vals.index(p["low"])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = dict(p)
                q["low"] = vals[j]
                out.append(("low", q))
    # the filter's own numeric inputs, where they are in use (minimum aligned zones and the
    # TDI lengths are only read when the zone filter is on)
    steps = [("min_aligned", True)] if p["use_zones"] else []
    if p["perm_candles"] > 0:
        steps.append(("perm_candles", True))
    if p["use_drift"]:
        steps.append(("drift_bars", True))
    if p["lv_mode"] == "entry":
        steps.append(("entry_dist_atr", True))
    for name, _ in steps:
        vals = GRID[name]
        if p[name] not in vals:
            continue
        i = vals.index(p[name])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                q = dict(p)
                q[name] = vals[j]
                out.append((name, q))
    for c in (p["conf"] - 1, p["conf"] + 1):
        if 1 <= c <= len(p["tfs"]):
            q = dict(p)
            q["conf"] = c
            out.append(("conf", q))
    if p["use_zones"]:
        pair = (p["rsi_len"], p["fast_len"])
        for other in (GRID["tdi"][1:] if pair == GRID["tdi"][0] else GRID["tdi"][:1]):
            q = dict(p)
            q["rsi_len"], q["fast_len"] = other
            out.append(("tdi", q))
    names = list(WEIGHTS)
    for wname in names:
        if wname != p.get("weights"):
            q = dict(p)
            q["weights"] = wname
            q["wA"], q["wV"], q["wS"], q["wC"] = WEIGHTS[wname]
            out.append(("weights", q))
    return out
