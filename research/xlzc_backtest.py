#!/usr/bin/env python3
"""
Python replica of XAUUSD_M1_LiquidityZeroCross_Bearish.mq5 (v1.00) for
multi-timeframe calibration.

It is NOT the MT5 Strategy Tester. It reproduces the EA's rules on OHLC bars:
  R1 HTF bias   : HTF MACD(12,26,9) main < 0 and close < EMA(50), last CLOSED HTF bar
  R2 trigger    : trigger-TF MACD main crosses zero down on closed bars, entry at next bar open
  R3 Stochastic : (7, slowing 1, D 7) came from >= 80 within 5 bars and turned down (soft/hard)
  R4 liquidity  : sweep candle or swing high -> SL (+buffer +spread); nearest swing low with RR>=min -> TP
  R5 risk       : 1 position at a time, spread filter, trailing (server), optional partial close
  R6 session    : UTC window on the entry time (news filter NOT replicated - no calendar data)

Time base: the dataset's 'datetime' column is BROKER SERVER TIME (FTMO, New York + 7h,
i.e. GMT+2 winter / GMT+3 US summer), not UTC as its README says (weekly open is
Monday 01:05; the 08:30 ET payroll spike sits at 15:30 all year). Session windows
in this research are therefore server-time windows.

Fill model (data is mid-price M1 from an FTMO MT5 feed):
  bid = mid - spread/2, ask = mid + spread/2, spread = constant per-hour-of-day mean
  from spreads_summary.csv (that file is in UTC hours; bars are mapped server->UTC).
  Shorts enter at bid on the first tick of the bar after the signal bar.
  Exits walk M1 bars: SL is checked against the ask high BEFORE TP/trailing (pessimistic),
  gaps through a level fill at the bar open. Trailing step is ignored (continuous trailing).
  No commission and no swap (intraday holding; FTMO metals commission is not modelled).

Results are expressed in R (multiples of the initial risk). Because the EA sizes every trade
to risk the same % of equity, profit factor in R equals profit factor in money
(ignoring lot rounding).

Usage: python3 xlzc_backtest.py <data_dir> <out_dir>
"""
import itertools
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

# Instrument settings. Point distances in the research are written in gold points and
# multiplied by `scale` (ratio of typical M1 ranges) for other instruments.
#   spread_pts: constant spread in points when no spreads_summary.csv row exists
#   spread_cap: the EA's MaxSpread_Points used in the simulation (in that instrument's points)
INSTRUMENTS = {
    "XAUUSD": dict(scale=1.0, spread_cap=60, spread_pts=None),
    # BTC M1 median range $41.0 vs gold $1.26 (Jan 2025-May 2026) -> 32.6; CFD spread assumed $20
    "BTCUSD": dict(scale=32.6, spread_cap=3000, spread_pts=2000),
}
SYMBOL = os.environ.get("XLZC_SYMBOL", "XAUUSD")
INST = dict(INSTRUMENTS[SYMBOL])
if os.environ.get("XLZC_SPREAD_PTS"):          # override the assumed constant spread (points)
    INST["spread_pts"] = float(os.environ["XLZC_SPREAD_PTS"])
if os.environ.get("XLZC_SPREAD_CAP"):          # override the simulated MaxSpread_Points
    INST["spread_cap"] = float(os.environ["XLZC_SPREAD_CAP"])

TF_MIN = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
OOS_START = pd.Timestamp("2026-01-01")

# ----------------------------------------------------------------------------- data
def load(data_dir):
    m1 = pd.read_csv(os.path.join(data_dir, f"{SYMBOL}_m1.csv"), parse_dates=["datetime"])
    m1 = m1.set_index("datetime").sort_index()
    if INST["spread_pts"] is not None:
        return m1, np.full(24, INST["spread_pts"] * 0.01)
    sp = pd.read_csv(os.path.join(data_dir, "spreads_summary.csv"))
    sp = sp[sp.symbol == SYMBOL].set_index("hour_utc")["mean_spread"]
    hourly = sp.reindex(range(24))
    hourly[21] = 60.0  # rollover hour, not sampled: assume wide
    hourly = hourly.interpolate().bfill().ffill()
    return m1, hourly.values * 0.01  # points -> price (XAUUSD point = 0.01), indexed by UTC hour


def server_to_utc_hour(index):
    """Server time (New York + 7h) -> UTC hour of day, DST-aware."""
    ny = (index - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous="NaT",
                                                       nonexistent="shift_forward")
    utc = ny.tz_convert("UTC")
    h = np.asarray(utc.hour, dtype=float)
    fallback = (np.asarray(index.hour) - 2) % 24          # ambiguous hour: assume +2
    return np.where(np.isnan(h), fallback, h).astype(int)


def resample(m1, tf):
    if tf == "M1":
        return m1[["open", "high", "low", "close"]].copy()
    rule = f"{TF_MIN[tf]}min"
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return o.dropna()


def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def macd_main(close):
    return ema(close, 12) - ema(close, 26)


def stoch(df, k=7, slowing=1, d=7):
    ll = df["low"].rolling(k).min()
    hh = df["high"].rolling(k).max()
    num = (df["close"] - ll).rolling(slowing).sum()
    den = (hh - ll).rolling(slowing).sum()
    main = 100 * num / den.replace(0, np.nan)
    return main, main.rolling(d).mean()


def swing_flags(high, low, s):
    """MT5 EA fractal: newer side strict (>= blocks), older side (> blocks)."""
    n = len(high)
    sh = np.ones(n, bool)
    sl = np.ones(n, bool)
    for k in range(1, s + 1):
        newer_h = np.full(n, np.inf); newer_h[:-k] = high[k:]
        older_h = np.full(n, np.inf); older_h[k:] = high[:-k]
        sh &= (newer_h < high) & (older_h <= high)
        newer_l = np.full(n, -np.inf); newer_l[:-k] = low[k:]
        older_l = np.full(n, -np.inf); older_l[k:] = low[:-k]
        sl &= (newer_l > low) & (older_l >= low)
    return sh, sl


# ----------------------------------------------------------------------------- signals
def build_signals(m1, trig, htf):
    t = resample(m1, trig)
    h = resample(m1, htf)
    tm = macd_main(t["close"]).values
    st_main, st_sig = stoch(t)
    st_main = st_main.values; st_sig = st_sig.values

    h_macd = macd_main(h["close"])
    h_ema = ema(h["close"], 50)
    hb = pd.DataFrame({"close_time": h.index + pd.Timedelta(minutes=TF_MIN[htf]),
                       "bias": ((h_macd < 0) & (h["close"] < h_ema)).values})
    hb = hb.iloc[60:]  # warm-up

    idx = np.arange(1, len(t) - 1)
    cross = (tm[idx - 1] >= 0) & (tm[idx] < 0)
    sig_bar = idx[cross]
    sig_bar = sig_bar[sig_bar > 60]
    entry_bar = sig_bar + 1
    entry_time = t.index[entry_bar]

    st_ok = np.zeros(len(sig_bar), bool)
    for n, i in enumerate(sig_bar):
        was_ob = np.nanmax(st_main[i - 4:i + 1]) >= 80
        st_ok[n] = was_ob and (st_main[i] < st_sig[i] or st_main[i] < 80)

    sig = pd.DataFrame({"entry_bar": entry_bar, "entry_time": entry_time, "stoch_ok": st_ok})
    sig = pd.merge_asof(sig.sort_values("entry_time"), hb.sort_values("close_time"),
                        left_on="entry_time", right_on="close_time", direction="backward")
    sig["bias"] = sig["bias"].fillna(False).astype(bool)
    return t, sig


def structure(t, sig, N, S):
    """Per signal: SL reference (bid-chart high) and candidate swing lows (mid)."""
    hi = t["high"].values; lo = t["low"].values; cl = t["close"].values; op = t["open"].values
    sh, sl = swing_flags(hi, lo, S)
    out = []
    for e in sig["entry_bar"].values:
        if e - N - S < 0:
            out.append(None); continue
        mid_open = op[e]  # r[0] at first tick: high = low = open
        # shifts 1..N  -> absolute e-1 .. e-N ; swing valid at shift >= 1+S
        sweep = -1
        for j in range(1, N + 1):
            aj = e - j
            for i in range(j + S + 1, N + 1):
                ai = e - i
                if sh[ai] and hi[aj] > hi[ai] and cl[aj] < hi[ai]:
                    sweep = j; break
            if sweep > 0:
                break
        struct_bar, src = -1, ""
        if sweep > 0 and hi[e - sweep] > mid_open:
            struct_bar, src = sweep, "sweep"
        else:
            for i in range(1 + S, N + 1):
                if sh[e - i] and hi[e - i] > mid_open:
                    struct_bar, src = i, "swing"; break
        if struct_bar < 0:
            out.append(None); continue
        ref = max(hi[e - struct_bar:e].max(), mid_open)
        lows = sorted({lo[e - i] for i in range(1 + S, N + 1) if sl[e - i] and lo[e - i] < mid_open},
                      reverse=True)
        out.append((ref, src == "sweep", lows))
    return out


# ----------------------------------------------------------------------------- exits
class M1Path:
    # How a trailing level set from bar k's low is treated inside bar k:
    #   "next"  - only tested from bar k+1 (original model; optimistic)
    #   "close" - also stop at bar k if its close is at/above the new level (certain hit)
    #   "worst" - also stop at bar k if its high reached the new level
    #   "random"- the low comes first in a seeded half of the bars: there the later high can hit
    #             the new level; on high-first bars only a close beyond it counts (as "close")
    #   With a trailing distance below a typical M1 range, "worst" exits near the bar's low (a
    #   good price) and "next" is the pessimistic case: no mode is a bound on its own.
    TRAIL_MODE = "close"  # default: count certain same-bar hits; "worst" is the pessimistic bound

    def __init__(self, m1, hs_by_hour):
        self.t = m1.index.values
        self.o = m1["open"].values; self.h = m1["high"].values; self.l = m1["low"].values
        self.c = m1["close"].values
        self.low_first = np.random.default_rng(20261107).random(len(m1)) < 0.5   # for TRAIL_MODE "random"
        self.hs = hs_by_hour[server_to_utc_hour(m1.index)] / 2.0  # half spread per bar

    def simulate(self, start, entry, sl0, tp, trail, partial):
        """Return (exit_idx, R). trail=(start,dist) price units or None; partial=(atR,pct,be) or None."""
        risk = sl0 - entry
        n = len(self.o)
        pos = start
        win = 1500
        realized = 0.0
        remaining = 1.0
        sl_floor = np.inf  # extra SL cap (break-even after partial)
        partial_done = partial is None
        best_trail = np.inf
        while pos < n:
            end = min(n, pos + win)
            ah = self.h[pos:end] + self.hs[pos:end]
            al = self.l[pos:end] + self.hs[pos:end]
            ao = self.o[pos:end] + self.hs[pos:end]
            if trail is not None:
                cand = np.where(entry - al >= trail[0], al + trail[1], np.inf)
                cm = np.minimum.accumulate(np.concatenate(([best_trail], cand)))[:-1]  # effective before bar
                eff = np.minimum(np.minimum(sl0, cm), sl_floor)
            else:
                eff = np.full(end - pos, min(sl0, sl_floor))
            stop_hit = ah >= eff
            tp_hit = al <= tp
            same_hit = np.zeros(end - pos, bool)
            if trail is not None and self.TRAIL_MODE != "next":
                if self.TRAIL_MODE == "random":
                    # low before high in a seeded half of the bars: there the later high can hit
                    # the level set at the low; on high-first bars only a close beyond it is certain
                    trig = np.where(self.low_first[pos:end], ah, self.c[pos:end] + self.hs[pos:end])
                else:
                    trig = ah if self.TRAIL_MODE == "worst" else self.c[pos:end] + self.hs[pos:end]
                same_hit = np.isfinite(cand) & (cand < eff) & (trig >= cand) & ~tp_hit
            part_k = None
            if not partial_done:
                lvl = entry - partial[0] * risk
                ph = al <= lvl
                if ph.any():
                    part_k = int(np.argmax(ph))
            ev = stop_hit | tp_hit | same_hit
            k = int(np.argmax(ev)) if ev.any() else None
            if part_k is not None and (k is None or part_k < k or (part_k == k and not stop_hit[k])):
                if k is not None and part_k == k and tp_hit[k]:
                    pass  # TP and partial same bar: TP closes all anyway
                else:
                    pct = partial[1]
                    realized += pct * partial[0]
                    remaining -= pct
                    partial_done = True
                    if partial[2]:
                        sl_floor = entry
                    if trail is not None:
                        best_trail = min(best_trail, cm[part_k + 1] if part_k + 1 < len(cm) else cand[part_k])
                        best_trail = min(best_trail, cand[part_k])
                    if k is not None and part_k == k and same_hit[k]:
                        # partial and a same-bar trailing hit in one bar: close the rest at the level
                        return pos + k, realized + remaining * (entry - cand[k]) / risk
                    pos = pos + part_k + 1
                    continue
            if k is not None:
                if stop_hit[k]:
                    px = max(eff[k], ao[k])
                    # random mode, low-first bar: rising from the low, the price meets the newer
                    # (lower) level set at the low before the older one
                    if (trail is not None and self.TRAIL_MODE == "random" and self.low_first[pos + k]
                            and np.isfinite(cand[k]) and cand[k] < eff[k] and ao[k] < eff[k] and ah[k] >= cand[k]):
                        px = cand[k]
                elif tp_hit[k]:
                    px = min(tp, ao[k])
                else:                      # trailing level set and hit inside the same bar
                    px = cand[k]
                r = realized + remaining * (entry - px) / risk
                return pos + k, r
            if trail is not None:
                best_trail = min(best_trail, np.min(cand))
            pos = end
        return n - 1, realized + remaining * (entry - (self.o[-1] + self.hs[-1])) / risk


# ----------------------------------------------------------------------------- run one config
SESSIONS = {"overlap_12-1630": (720, 990), "ldn_ny_07-20": (420, 1200), "all_day": (0, 1440)}

G = {}


def init_worker(payload):
    G.update(payload)


def run_cfg(cfg):
    sig = G["sig"][cfg["tf"]]
    struct = G["struct"][(cfg["tf"], cfg["N"], cfg["S"])]
    path = G["path"]
    t_index = G["tidx"][cfg["tf"]]
    m1_times = path.t
    s0, s1 = SESSIONS[cfg["session"]]
    pt = 0.01
    trades = []
    busy_until = np.datetime64("1970-01-01")
    for n, row in enumerate(sig.itertuples(index=False)):
        if cfg["use_htf"] and not row.bias:
            continue
        if cfg["stoch"] == "hard" and not row.stoch_ok:
            continue
        et = np.datetime64(row.entry_time)
        if et <= busy_until:
            continue
        tod = row.entry_time.hour * 60 + row.entry_time.minute
        if not (s0 <= tod < s1):
            continue
        st = struct[n]
        if st is None:
            continue
        ref, is_sweep, lows = st
        mi = int(np.searchsorted(m1_times, et))
        if mi >= len(m1_times) or m1_times[mi] - et > np.timedelta64(TF_MIN[cfg["tf"].split("/")[0]], "m"):
            continue
        hs = path.hs[mi]
        if 2 * hs / pt > cfg["max_spread"]:
            continue
        entry = path.o[mi] - hs                     # bid
        sl = (ref - hs) + cfg["buffer"] * pt + 2 * hs  # bid-chart high + buffer + spread
        risk = sl - entry
        risk_pts = risk / pt
        if risk_pts < cfg["min_sl"] or (cfg["max_sl"] and risk_pts > cfg["max_sl"]):
            continue
        tp = None
        for low in lows:
            cand = low - hs                          # bid-chart low, TP buffer 0
            if entry - cand > 0 and entry - cand >= cfg["min_rr"] * risk:
                tp = cand; break
        if tp is None:
            continue
        trail = None
        if cfg["trail"]:
            trail = (cfg["trail"][0] * pt, cfg["trail"][1] * pt)
        partial = (1.0, 0.5, True) if cfg["partial"] else None
        xi, r = path.simulate(mi, entry, sl, tp, trail, partial)
        busy_until = m1_times[xi]
        trades.append((row.entry_time, r, is_sweep))
    return cfg, trades


def stats(rs):
    rs = np.asarray(rs, float)
    if len(rs) == 0:
        return dict(trades=0, pf=np.nan, win=np.nan, exp_r=np.nan, net_r=0.0, maxdd_r=0.0)
    gw = rs[rs > 0].sum(); gl = -rs[rs < 0].sum()
    eq = np.cumsum(rs)
    dd = np.max(np.maximum.accumulate(np.concatenate(([0], eq))) - np.concatenate(([0], eq)))
    return dict(trades=len(rs), pf=gw / gl if gl > 0 else np.inf, win=(rs > 0).mean(),
                exp_r=rs.mean(), net_r=rs.sum(), maxdd_r=dd)


# ----------------------------------------------------------------------------- main
def main():
    data_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    m1, hs = load(data_dir)
    path = M1Path(m1, hs)

    tf_pairs = ["M1/M5", "M1/M15", "M5/M15", "M5/H1", "M15/H1", "M15/H4"]
    NS = [(15, 2), (25, 2), (25, 3), (40, 3)]
    sigs, structs, tidx = {}, {}, {}
    for pair in tf_pairs:
        trig, htf = pair.split("/")
        t, sig = build_signals(m1, trig, htf)
        sigs[pair] = sig; tidx[pair] = t.index
        for N, S in NS:
            structs[(pair, N, S)] = structure(t, sig, N, S)
        print(f"{pair}: {len(sig)} zero-cross signals, {int(sig.bias.sum())} with HTF bias", flush=True)

    # SL bounds scale with the trigger timeframe (swing size grows ~ sqrt(TF))
    sl_bounds = {"M1": (50, 1000), "M5": (100, 2000), "M15": (150, 3500)}
    grid = []
    for pair in tf_pairs:
        trig = pair.split("/")[0]
        for (N, S), buf, rr, stoch_mode, session, trail, partial, mx_spread, use_htf in itertools.product(
                NS, [20, 40, 80], [1.0, 1.5, 2.0], ["soft", "hard"], list(SESSIONS),
                [None, "on"], [False, True], [30, 60], [True, False]):
            if mx_spread == 30 and not (N == 25 and S == 2 and buf == 40 and rr == 1.0 and use_htf
                                        and stoch_mode == "soft" and session == "overlap_12-1630"
                                        and trail is None and not partial):
                continue  # only probe the shipped spread default once per TF
            if not use_htf and not (stoch_mode == "soft" and trail is None and not partial):
                continue  # HTF-off ablation kept small
            k = TF_MIN[trig] ** 0.5
            trail_pts = (round(150 * k), round(100 * k)) if trail else None
            grid.append(dict(tf=pair, N=N, S=S, buffer=round(buf * k), buf_base=buf, min_rr=rr,
                             stoch=stoch_mode, session=session, trail=trail_pts, partial=partial,
                             max_spread=mx_spread, use_htf=use_htf,
                             min_sl=sl_bounds[trig][0], max_sl=sl_bounds[trig][1]))
    print(f"{len(grid)} configurations", flush=True)

    payload = dict(sig=sigs, struct=structs, path=path, tidx=tidx)
    rows, trade_log = [], {}
    with Pool(4, initializer=init_worker, initargs=(payload,)) as pool:
        for cfg, trades in pool.imap_unordered(run_cfg, grid, chunksize=8):
            times = [x[0] for x in trades]; rs = [x[1] for x in trades]
            is_ = [r for t_, r in zip(times, rs) if t_ < OOS_START]
            oos = [r for t_, r in zip(times, rs) if t_ >= OOS_START]
            a, b, c = stats(rs), stats(is_), stats(oos)
            row = {k: (json.dumps(v) if isinstance(v, (tuple, list)) else v) for k, v in cfg.items()}
            row.update({f"all_{k}": v for k, v in a.items()})
            row.update({f"is_{k}": v for k, v in b.items()})
            row.update({f"oos_{k}": v for k, v in c.items()})
            row["sweep_share"] = np.mean([x[2] for x in trades]) if trades else np.nan
            rows.append(row)
            key = json.dumps({k: cfg[k] for k in sorted(cfg)}, default=str)
            trade_log[key] = [(str(t_), round(r, 4)) for t_, r in zip(times, rs)]
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "grid_results.csv"), index=False)
    with open(os.path.join(out_dir, "trades.json"), "w") as f:
        json.dump(trade_log, f)
    print("done", len(df))


if __name__ == "__main__":
    main()
