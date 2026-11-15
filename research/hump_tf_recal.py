#!/usr/bin/env python3
"""
Re-calibration of the Loma (hump) method per trigger timeframe, with an honest out-of-sample test.

Question: on which timeframes does the method hold a profit factor of 1.3 or more on data the
calibration never saw?

Protocol (fixed before any out-of-sample result was looked at):
  data     XAUUSD: FTMO M1 (Jan 2025 - May 15 2026) followed by Dukascopy M1 (May 18 - Nov 13 2026), FTMO hourly
           spread table throughout. BTCUSD: Binance BTCUSDT M1 (Jan 2025 - Nov 13 2026) read from the raw UTC
           files and converted to broker server time once, 10 USD spread. build() checks the clock of both.
  IS       in-sample: entries before 2026-05-16 03:00 server time, in three blocks
           (2025 H1, 2025 H2, 2026 Jan - May 15).
  OOS      out-of-sample: entries from 2026-05-16 03:00 server time to the end of the data.
  space    hump_search.SPACE with HUMP_SPACE=2 (every calibrated input), one timeframe at a time,
           N random setups per timeframe; the trend-filter timeframe must be a multiple of the trigger timeframe.
  score    in-sample only: the lowest of the six profit factors (three blocks x base costs and harsh
           stress), with at least MIN_N trades in every block.
  pick     per timeframe: the 10 best scores, one per (direction, session, trend filter) family, score >= 1.3.
  test     the picked setups on OOS: pooled profit factor (all their trades together), base and stress.
  pass     pooled OOS PF >= 1.3 on >= 100 trades.
  trailing run 1 uses the EA's own trailing (multiples of the risk). Runs 2 and 3 add 22 more systems; those that
           trail by a fixed dollar, percent or ATR distance, the profit lock and the trail after a partial close
           move the stop once per closed one-minute bar, a rule that one-minute data resolves exactly
           (hump_trail2.py; trailing from inside the running minute is not testable on one-minute bars).

Usage:
  python3 hump_tf_recal.py build  <work_dir> <source>                 # once per symbol: combined M1 series
                                   (XAUUSD: Dukascopy bi5 directory; BTCUSD: Binance zip directories, comma-separated)
  python3 hump_tf_recal.py run    <work_dir> <TF> <N> [workers]       # candidates of one timeframe, base + stress
  python3 hump_tf_recal.py runx   <work_dir> <TF> <N> [workers]       # the same with every trailing family (hump_trail.py)
  python3 hump_tf_recal.py runy   <work_dir> <TF> <N> [workers]       # twelve more trailing systems (hump_trail2.py)
  python3 hump_tf_recal.py rerun  <work_dir> <prefix> <kind> [workers] # recompute one trailing kind in the stored files
  python3 hump_tf_recal.py fresh  <work_dir> <prefix> [per_kind] [workers]  # stored trades must equal the current code
  python3 hump_tf_recal.py select <work_dir> <out_json> [cand|candx]  # in-sample pick and out-of-sample test
  python3 hump_tf_recal.py sens   <work_dir> <out_json> [cand|candx]  # other selection rules (robustness)
  python3 hump_tf_recal.py kinds  <work_dir> <out_json> [prefix]      # the same test per trailing family
  (prefix: cand = run 1, candx = run 2, candx+candy = runs 2 and 3 together)
  python3 hump_tf_recal.py vt     <work_dir> <out_json> [cand|candx]  # gold: the picks at VT Markets' own costs
Environment: HUMP_SYMBOL=XAUUSD|BTCUSD, HUMP_BTC_DATA=<dir with BTCUSD_m1.csv> for BTC.
"""
import json, os, pickle, random, sys, time
from multiprocessing import Pool
import numpy as np, pandas as pd

os.environ["HUMP_SPACE"] = "2"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, xlzc_backtest as B
import hump_trail as T
import hump_trail2 as T2

SYM = H.SYMBOL
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
HTFS = ["M15", "M30", "H1", "H4", "D1"]
IS_END = np.datetime64("2026-05-16T03:00")
BLOCKS = [(np.datetime64("2025-01-01"), np.datetime64("2025-07-01")), (np.datetime64("2025-07-01"), np.datetime64("2026-01-01")),
          (np.datetime64("2026-01-01"), IS_END)]
MIN_N = 20
TOPK = 10
PASS_PF, PASS_N = 1.30, 100
STRESS = (dict(trail_worst=1, delay=1, slip=3.0, comm=2.0, max_spread=1e9) if SYM == "BTCUSD"
          else dict(trail_worst=1, delay=1, slip=0.10, comm=0.07, max_spread=5.0))
# VT Markets XAUUSD-ECNc as the account owner reported it: spread 1.5 pips (0.15 USD per ounce) and a
# commission of 0.60 USD per lot round trip, 1 lot = 1 ounce. About 0.75 USD per ounce in total.
VT_SPREAD, VT_COMM = 0.15, 0.60


# ----------------------------------------------------------------------------- data
def read_binance_zips(dirs):
    """Binance spot kline zips (monthly or daily) -> M1 bars indexed by UTC. Timestamps are milliseconds
    until 2024 and microseconds from 2025."""
    import glob, io, zipfile
    parts = []
    for d in dirs:
        for z in sorted(glob.glob(os.path.join(d, "BTCUSDT-1m-*.zip"))):
            with zipfile.ZipFile(z) as f:
                raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
            t = raw[0].astype("int64")
            parts.append(pd.DataFrame(dict(open=raw[1].values, high=raw[2].values, low=raw[3].values, close=raw[4].values),
                                      index=pd.to_datetime(t.values, unit="us" if t.iloc[0] > 1e14 else "ms")))
    m = pd.concat(parts)
    return m[~m.index.duplicated()].sort_index().astype(float)


def utc_to_server(index):
    """Broker server time = New York time + 7 hours (GMT+2 in the US winter, GMT+3 in the US summer)."""
    return index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)


def clock_check(m1, label, min_reopen=0.9, jump_fatal=True, top=None):
    """Stops when a price series is not on broker server time (New York + 7 h). Two physical marks are used.

    1. The US stock open (09:30 New York = 16:30 server time) lifts activity on gold and on BTC every weekday, at
       that exact minute. For each half-past mark from 13:30 to 19:30 the median one-minute range of the five
       minutes after it is compared with the five minutes before it, quarter by quarter.
    2. A market with a daily break (gold) reopens at 18:00 New York = 01:00 server time (01:05 at FTMO).

    A series without a daily break (BTC) must have its largest jump at 16:30 in at least two thirds of the
    quarters; a quarter full of 08:30 New York data releases can put 15:30 first. A series with a daily break must
    reopen between 01:00 and 01:15 on at least 90% of the days, and 16:30 must be one of its two largest jumps in
    at least two thirds of the quarters (gold reacts to the 08:30 releases as much as to the stock open).
    top: how high the 16:30 jump must rank (default: 2 with a daily break, 1 without). US500 has the daily break
    and must have its largest jump at 16:30 (top=1): the stock index follows the stock open first.
    A BTC file that was already in server time was once converted a second time, which put a calibration 2-3
    hours off: such a series fails here. Returns the line it prints."""
    rng = (m1["high"] - m1["low"]).values
    mod = (m1.index.hour * 60 + m1.index.minute).values
    q = m1.index.to_period("Q")
    wd = (m1.index.dayofweek < 5)
    gap = np.diff(m1.index.values).astype("timedelta64[m]").astype(np.int64)
    reopen = mod[np.where((gap >= 45) & (gap <= 150))[0] + 1]            # first bar after a daily break
    daily_break = len(reopen) >= 20
    note = ""
    if daily_break:
        share = float(((reopen >= 60) & (reopen <= 75)).mean())
        if share < min_reopen:
            raise SystemExit(f"{label}: the market reopens between 01:00 and 01:15 server time on only {share:.0%} of {len(reopen)} days: wrong clock")
        note = f"daily reopen at 01:00-01:15 server time on {share:.0%} of {len(reopen)} days; "
    top = (2 if daily_break else 1) if top is None else int(top)
    tested, bad = _open_jumps(rng, mod, q, wd, top)
    if tested == 0 or len(bad) > 0.34 * tested:
        msg = f"{label}: the US-open jump is not at 16:30 server time in {bad} ({len(bad)} of {tested} quarters)"
        if jump_fatal or not daily_break:
            raise SystemExit(msg + ": wrong clock")
        # a market with a daily break whose reopen is already at 01:00 server time: the reopen decides the clock
        # (a series one hour off has 0-1% of its reopens there); the weaker activity mark is only recorded
        line = f"{label}: clock check passed on the daily reopen ({note.strip('; ')}); NOTE {msg}"
        print(line, flush=True)
        return line
    line = (f"{label}: clock check passed ({note}US-open jump at 16:30 server time "
            + ("among the two largest " if top == 2 else "") + f"in {tested - len(bad)} of {tested} quarters"
            + (f"; elsewhere in {bad}" if bad else "") + ")")
    print(line, flush=True)
    return line


def _open_jumps(rng, mod, q, wd, top):
    """The US-open mark of clock_check: per quarter (20000 weekday bars or more) the jump of the median one-minute
    range at each half-past mark from 13:30 to 19:30; returns (quarters tested, [(quarter, largest mark)] of the
    quarters where 16:30 is not among the `top` largest)."""
    bad = []; tested = 0
    for quarter in sorted(set(q)):
        mask = np.asarray(q == quarter) & np.asarray(wd)
        if mask.sum() < 20000:
            continue
        r, t = rng[mask], mod[mask]
        jumps = []
        for mark in range(13 * 60 + 30, 19 * 60 + 31, 60):          # 13:30 ... 19:30: three hours either side
            after = r[(t >= mark) & (t < mark + 5)]; before = r[(t >= mark - 5) & (t < mark)]
            if len(after) < 50 or len(before) < 50 or np.median(before) <= 0:
                continue
            jumps.append((np.median(after) / np.median(before), mark))
        jumps.sort(reverse=True)
        tested += 1
        if 16 * 60 + 30 not in [m for _, m in jumps[:top]]:
            bad.append((str(quarter), f"{jumps[0][1] // 60:02d}:{jumps[0][1] % 60:02d}" if jumps else "none"))
    return tested, bad


def clock_check_fx(m1, spread, label, min_monday=0.9, min_rollover=0.8):
    """Stops when a currency series without a daily break (EURUSD) is not on broker server time (New York + 7 h).
    Two marks of the FX market itself are used.

    1. The FX week opens on Sunday at 17:00 New York, which is Monday 00:00 server time in the US summer and in the
       US winter. The first bar after every closure of 24 hours or more (the weekends, and the odd holiday) must be on
       a Monday between 00:00 and 00:05 server time after at least 90% of those closures.
    2. The daily rollover at 17:00 New York (00:00 server time) widens the spread every day. Quarter by quarter
       (quarters with 20000 bars or more), the minute of the day with the largest median spread (ask close - bid
       close, `spread`, one value per bar) must lie between 23:50 and 00:10 server time in at least 80% of them.

    The US-open jump of clock_check (16:30 the largest of the half-past marks in two thirds of the quarters) is only
    recorded: a currency reacts to the 08:30 New York releases (15:30 server time) more than to the stock open.
    Returns (line, note): the line it prints and the US-open note."""
    t = m1.index
    spread = np.asarray(spread, float)
    assert len(spread) == len(t)
    mod = (t.hour * 60 + t.minute).values
    tmin = t.values.astype("datetime64[m]").astype(np.int64)
    first = np.where(np.diff(tmin) >= 24 * 60)[0] + 1                   # first bar after a closure of 24 h or more
    if len(first) == 0:
        raise SystemExit(f"{label}: no closure of 24 hours or more (no weekend) in the series: the weekly open cannot be checked")
    monday = (t.dayofweek.values[first] == 0) & (mod[first] <= 5)
    share = float(monday.mean())
    if share < min_monday:
        other = pd.Series([f"{t[i].day_name()[:3]} {mod[i] // 60:02d}:{mod[i] % 60:02d}" for i in first[~monday]]).value_counts()
        raise SystemExit(f"{label}: the week opens on Monday 00:00-00:05 server time after only {share:.0%} of {len(first)} "
                         f"closures of 24 h or more (others: {dict(other.head(5))}): wrong clock")
    q = t.to_period("Q")
    bad = []; tested = 0
    for quarter in sorted(set(q)):
        mask = np.asarray(q == quarter)
        if mask.sum() < 20000:
            continue
        med = pd.Series(spread[mask]).groupby(mod[mask]).median()
        widest = int(med.idxmax())
        tested += 1
        if not (widest >= 23 * 60 + 50 or widest <= 10):
            bad.append((str(quarter), f"{widest // 60:02d}:{widest % 60:02d}"))
    if tested == 0 or tested - len(bad) < min_rollover * tested:
        raise SystemExit(f"{label}: the widest median spread (the daily rollover) is not at 23:50-00:10 server time in {bad} "
                         f"({len(bad)} of {tested} quarters): wrong clock")
    wd = (t.dayofweek < 5)
    jt, jbad = _open_jumps((m1["high"] - m1["low"]).values, mod, q, wd, 1)
    note = (f"{label}: US-open jump (recorded only) at 16:30 server time the largest of the half-past marks in "
            f"{jt - len(jbad)} of {jt} quarters" + (f"; elsewhere in {jbad}" if jbad else ""))
    line = (f"{label}: clock check passed (weekly open on Monday 00:00-00:05 server time after {int(monday.sum())} of {len(first)} "
            f"closures of 24 h or more; widest median spread at 23:50-00:10 server time in {tested - len(bad)} of {tested} quarters"
            + (f"; elsewhere in {bad}" if bad else "") + ")")
    print(line, flush=True)
    print("NOTE", note, flush=True)
    return line, note


def schedule(m1):
    """Where a series' closures fall in server time (for the record, and for the weekend rule of a new symbol):
    the reopen minute after breaks of 45-150 minutes (a daily break), the minute after the last bar of each Friday
    (the Friday close; a Friday without bars is skipped) and the first bar after closures of 24 hours or more
    (the weekly open). Each as {"HH:MM": share} of the five most frequent values, with the count."""
    t = m1.index
    mod = (t.hour * 60 + t.minute).values
    tmin = t.values.astype("datetime64[m]").astype(np.int64)
    gap = np.diff(tmin)

    def top5(minutes, days=None):
        if len(minutes) == 0:
            return dict(n=0)
        s = pd.Series([f"{m // 60:02d}:{m % 60:02d}" if days is None else f"{d} {m // 60:02d}:{m % 60:02d}"
                       for m, d in zip(minutes, days if days is not None else [None] * len(minutes))])
        vc = s.value_counts(normalize=True).head(5)
        return dict(n=int(len(s)), top={k: round(float(v), 3) for k, v in vc.items()})

    i = np.where((gap >= 45) & (gap <= 150))[0]
    brk = top5(mod[i + 1])
    brk_start = top5((mod[i] + 1) % 1440)
    fri = (t.dayofweek.values == 4)
    day = tmin // 1440
    last_fri = np.where(fri & np.r_[day[1:] != day[:-1], True])[0]       # last bar of each Friday
    close = top5((mod[last_fri] + 1) % 1440)
    j = np.where(gap >= 24 * 60)[0] + 1
    wopen = top5(mod[j], [x.day_name()[:3] for x in t[j]])
    return dict(daily_break_reopen=brk, daily_break_start=brk_start, friday_close=close, weekly_open=wopen)


def build(work, src=None):
    """XAUUSD: src = Dukascopy bi5 directory for the months after the FTMO data.
    BTCUSD: src = comma-separated directories of raw Binance kline zips (UTC), converted to server time once."""
    os.makedirs(work, exist_ok=True)
    duk_dir = src
    if SYM == "BTCUSD":
        raw = read_binance_zips(src.split(","))
        m1 = raw.copy(); m1.index = utc_to_server(raw.index)
        m1 = m1[~m1.index.duplicated()].sort_index()
        gaps = pd.Series(m1.index).diff().dt.total_seconds().div(60)
        print(f"Binance UTC {raw.index[0]} .. {raw.index[-1]}; largest gap {gaps.max():.0f} min; gaps over 10 min: {int((gaps > 10).sum())}")
        hs = np.full(len(m1), H.BTC_SPREAD / 2.0)
        hs_real = hs
    else:
        import duk_to_m1 as D
        f, hourly = B.load(H.DATA)
        d, dh = D.load(duk_dir)
        cut = f.index[-1]
        keep = d.index > cut
        d, dh = d[keep], dh[keep]
        m1 = pd.concat([f[["open", "high", "low", "close"]], d[["open", "high", "low", "close"]]])
        assert m1.index.is_monotonic_increasing and not m1.index.duplicated().any()
        hs = hourly[B.server_to_utc_hour(m1.index)] / 2.0                 # FTMO spread table for the whole series
        hs_real = np.r_[hourly[B.server_to_utc_hour(f.index)] / 2.0, dh]  # Dukascopy's own spread after the seam
        print(f"FTMO to {cut}, Dukascopy {d.index[0]} .. {d.index[-1]} ({len(d)} bars)")
    m1 = m1[["open", "high", "low", "close"]].astype(float)
    clock_check(m1, SYM)
    m1.to_pickle(os.path.join(work, "m1.pkl"))
    np.save(os.path.join(work, "hs.npy"), np.asarray(hs, float)); np.save(os.path.join(work, "hs_real.npy"), np.asarray(hs_real, float))
    print(SYM, m1.index[0], m1.index[-1], len(m1), "bars; IS bars", int((m1.index.values < IS_END).sum()),
          "OOS bars", int((m1.index.values >= IS_END).sum()))


def market(work, real_spread=False, flat_spread=None):
    m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))
    hs = np.load(os.path.join(work, "hs_real.npy" if real_spread else "hs.npy"))
    if flat_spread is not None:
        hs = np.full(len(m1), flat_spread / 2.0)
    return T2.MarketY(m1=m1, half_spread=hs)


# ----------------------------------------------------------------------------- candidates
def valid_htfs(tf):
    m = B.TF_MIN[tf]
    return ["none"] + [h for h in HTFS if B.TF_MIN[h] > m and B.TF_MIN[h] % m == 0]


def candidates(tf, n):
    rng = random.Random(f"{SYM}-{tf}-2026-11")
    keys = [k for k in X.SPACE if k not in ("tf", "htf")]
    seen, out = set(), []
    hl = valid_htfs(tf)
    while len(out) < n:
        p = {k: rng.choice(X.SPACE[k]) for k in keys}
        p["tf"] = tf; p["htf"] = rng.choice(hl)
        key = json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def trail_space():
    """Every trailing family with its parameter grid (distances in R unless the family says otherwise)."""
    ps, pd_ = ((50, 100, 200, 400), (25, 50, 100, 200)) if SYM == "BTCUSD" else ((1, 2, 4, 8), (0.5, 1, 2, 4))
    return {
        "none": [dict()],
        "R": [dict(trail_start=a, trail_dist=b) for a in (0.5, 1.0, 1.5, 2.0) for b in (0.3, 0.5, 1.0, 1.5)],
        "points": [dict(trail_start=a, trail_dist=b) for a in ps for b in pd_],                       # USD
        "percent": [dict(trail_start=a, trail_dist=b) for a in (0.05, 0.1, 0.2, 0.4) for b in (0.03, 0.05, 0.1, 0.2)],
        "atr": [dict(trail_start=a, trail_dist=b) for a in (0.5, 1.0, 2.0, 3.0) for b in (0.5, 1.0, 1.5, 2.5)],
        "breakeven": [dict(trail_start=a, trail_dist=b) for a in (0.5, 1.0, 1.5) for b in (0.0, 0.1, 0.3)],
        "step": [dict(trail_start=a) for a in (0.5, 1.0, 1.5)],
        "candles": [dict(trail_p=n, trail_start=a) for n in (1, 2, 3, 5, 8, 13) for a in (0.0, 0.5, 1.0)],
        "ema": [dict(trail_p=n, trail_start=a) for n in (8, 13, 21, 34, 50) for a in (0.0, 0.5, 1.0)],
        "psar": [dict(trail_p=v, trail_start=a) for v in (0, 1, 2) for a in (0.0, 0.5, 1.0)],
        "hump": [dict(trail_start=a) for a in (0.0, 0.5, 1.0)],
    }


def candidates_x(tf, n):
    rng = random.Random(f"{SYM}-{tf}-trail-2026-11")
    keys = [k for k in X.SPACE if k not in ("tf", "htf", "trail_start", "trail_dist")]
    ts = trail_space(); kinds = list(ts)
    seen, out = set(), []
    hl = valid_htfs(tf)
    while len(out) < n:
        p = {k: rng.choice(X.SPACE[k]) for k in keys}
        p["tf"] = tf; p["htf"] = rng.choice(hl)
        kind = rng.choice(kinds)
        p.update(trail_kind=kind, trail_start=0.0, trail_dist=0.5, trail_p=0)
        p.update(rng.choice(ts[kind]))
        key = json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def trail_space_y(tf):
    """The twelve further trailing systems of hump_trail2.py (run 3)."""
    starts = (0.0, 0.5, 1.0)
    htf = [m for m in (15, 30, 60, 240) if m > B.TF_MIN[tf] and m % B.TF_MIN[tf] == 0]
    return {
        "chandelier": [dict(trail_start=a, trail_dist=k) for a in starts for k in (1.5, 2.0, 3.0)],
        "profitlock": [dict(trail_start=a, trail_dist=k) for a in (0.5, 1.0, 1.5) for k in (0.3, 0.5, 0.7)],
        "timestop": [dict(trail_dist=float(m)) for m in (30, 60, 120, 240, 480)],
        "partial": [dict(trail_start=a, trail_dist=k) for a in (0.5, 1.0, 1.5) for k in (0.0, 0.5, 1.0)],
        "supertrend": [dict(trail_p=v, trail_start=a) for v in (0, 1, 2) for a in starts],
        "keltner": [dict(trail_p=v, trail_start=a) for v in (0, 1, 2) for a in starts],
        "bollinger": [dict(trail_p=v, trail_start=a) for v in (0, 1) for a in starts],
        "kijun": [dict(trail_p=n, trail_start=a) for n in (13, 26, 52) for a in starts],
        "pivots": [dict(trail_p=n, trail_start=a) for n in (2, 3, 5) for a in starts],
        "sma": [dict(trail_p=n, trail_start=a) for n in (10, 20, 50) for a in starts],
        "donchian": [dict(trail_p=n, trail_start=a) for n in (20, 55) for a in starts],
        "htfcandle": [dict(trail_p=m, trail_start=a) for m in htf for a in starts],
    }


def candidates_y(tf, n):
    rng = random.Random(f"{SYM}-{tf}-trail2-2026-11")
    keys = [k for k in X.SPACE if k not in ("tf", "htf", "trail_start", "trail_dist")]
    ts = trail_space_y(tf); kinds = [k for k in ts if ts[k]]
    seen, out = set(), []
    hl = valid_htfs(tf)
    while len(out) < n:
        p = {k: rng.choice(X.SPACE[k]) for k in keys}
        p["tf"] = tf; p["htf"] = rng.choice(hl)
        kind = rng.choice(kinds)
        p.update(trail_kind=kind, trail_start=0.0, trail_dist=0.5, trail_p=0)
        p.update(rng.choice(ts[kind]))
        key = json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def load_cands(work, prefix, tf):
    """Stored candidates of one timeframe; prefix may join several runs with '+', e.g. candx+candy."""
    P, Bs, Ss = [], [], []
    for pre in prefix.split("+"):
        fn = os.path.join(work, f"{pre}_{tf}.pkl")
        if not os.path.exists(fn):
            return None
        d = pickle.load(open(fn, "rb"))
        P += d["params"]; Bs += d["base"]; Ss += d["stress"]
    return P, Bs, Ss


MK = None


def _dump(obj, fn):
    """Write a candidate file in one step, so that a reader never meets a half-written pickle."""
    tmp = fn + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=4)
    os.replace(tmp, fn)


def _init(work):
    global MK
    MK = market(work)


def _trades(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = MK.run(X.engine_cfg(c))
    return (df.entry_time.values.astype("datetime64[m]").astype(np.int64).astype(np.int32),   # minutes since epoch
            df.r.values.astype(np.float32))


def _one(p):
    return _trades(p), _trades(p, STRESS)


def _trades_x(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = MK.run_y(X.engine_cfg(c))          # run_y: dollar, percent and ATR trailing move the stop per closed minute
    return (df.entry_time.values.astype("datetime64[m]").astype(np.int64).astype(np.int32), df.r.values.astype(np.float32))


def _one_x(p):
    return _trades_x(p), _trades_x(p, STRESS)


def _trades_y(p, extra=None):
    c = dict(X.BASE); c.update(p)
    if extra:
        c.update(extra)
    df = MK.run_y(X.engine_cfg(c))
    return (df.entry_time.values.astype("datetime64[m]").astype(np.int64).astype(np.int32), df.r.values.astype(np.float32))


def _one_y(p):
    return _trades_y(p), _trades_y(p, STRESS)


def run_y(work, tf, n, workers=3):
    cand = candidates_y(tf, n)
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(work,)) as pool:
        res = pool.map(_one_y, cand, chunksize=16)
    _dump(dict(tf=tf, params=cand, base=[r[0] for r in res], stress=[r[1] for r in res]), os.path.join(work, f"candy_{tf}.pkl"))
    print(f"{SYM} {tf}: {n} setups x 2 (twelve more trailing systems) in {time.time() - t0:.0f}s", flush=True)


def rerun_kind(work, prefix, kind, workers=3):
    """Recompute the stored trades of one trailing kind in <prefix>_<TF>.pkl (after a fix to that kind)."""
    for tf in TFS:
        fn = os.path.join(work, f"{prefix}_{tf}.pkl")
        if not os.path.exists(fn):
            continue
        d = pickle.load(open(fn, "rb"))
        idx = [i for i, p in enumerate(d["params"]) if p.get("trail_kind") == kind]
        with Pool(workers, initializer=_init, initargs=(work,)) as pool:
            res = pool.map(_one_y, [d["params"][i] for i in idx], chunksize=16)
        changed = 0
        for i, r in zip(idx, res):
            if len(r[0][1]) != len(d["base"][i][1]) or not np.allclose(r[0][1], d["base"][i][1]):
                changed += 1
            d["base"][i], d["stress"][i] = r
        _dump(d, fn)
        print(f"{SYM} {tf}: {len(idx)} '{kind}' setups recomputed, {changed} changed", flush=True)


def fresh(work, prefix, per_kind=25, workers=3):
    """Stored trades against the current code: per timeframe, a random sample of every trailing kind is recomputed
    and must equal the stored arrays (entry minutes exactly, R to 1e-6). Stops on the first stale kind, so that a
    result table is never built from trades that an older version of a simulator produced."""
    rng = random.Random(20261115)
    bad = {}; total = 0
    for tf in TFS:
        for pre in prefix.split("+"):
            fn = os.path.join(work, f"{pre}_{tf}.pkl")
            if not os.path.exists(fn):
                continue
            d = pickle.load(open(fn, "rb"))
            groups = {}
            for i, p in enumerate(d["params"]):
                groups.setdefault(p.get("trail_kind", "R (run 1)"), []).append(i)
            idx = [i for k in groups for i in rng.sample(groups[k], min(per_kind, len(groups[k])))]
            one = _one if pre == "cand" else _one_y
            with Pool(workers, initializer=_init, initargs=(work,)) as pool:
                res = pool.map(one, [d["params"][i] for i in idx], chunksize=8)
            for i, r in zip(idx, res):
                for new, old in ((r[0], d["base"][i]), (r[1], d["stress"][i])):
                    if len(new[1]) != len(old[1]) or not np.array_equal(new[0], old[0]) or not np.allclose(new[1], old[1], rtol=0, atol=1e-6):
                        key = (pre, tf, d["params"][i].get("trail_kind", "R (run 1)"))
                        bad[key] = bad.get(key, 0) + 1
            total += len(idx)
            print(f"{SYM} {pre} {tf}: {len(idx)} setups of {len(groups)} kinds recomputed", flush=True)
    if bad:
        raise SystemExit(f"{SYM}: STALE stored results (file, timeframe, kind: runs that differ): {bad}")
    print(f"{SYM} {prefix}: {total} stored setups equal the current code, base and stress")


def run_x(work, tf, n, workers=3):
    cand = candidates_x(tf, n)
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(work,)) as pool:
        res = pool.map(_one_x, cand, chunksize=16)
    _dump(dict(tf=tf, params=cand, base=[r[0] for r in res], stress=[r[1] for r in res]), os.path.join(work, f"candx_{tf}.pkl"))
    print(f"{SYM} {tf}: {n} setups x 2 (all trailing families) in {time.time() - t0:.0f}s", flush=True)


def run(work, tf, n, workers=3):
    cand = candidates(tf, n)
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(work,)) as pool:
        res = pool.map(_one, cand, chunksize=16)
    _dump(dict(tf=tf, params=cand, base=[r[0] for r in res], stress=[r[1] for r in res]), os.path.join(work, f"cand_{tf}.pkl"))
    print(f"{SYM} {tf}: {n} setups x 2 in {time.time() - t0:.0f}s", flush=True)


# ----------------------------------------------------------------------------- selection and test
def pf(r):
    r = np.asarray(r, float)
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    return float(w / l) if l > 0 else (float("inf") if w > 0 else float("nan"))


def is_score(tb, ts):
    """Lowest of the six in-sample profit factors; 0 when a block has fewer than MIN_N trades."""
    vals = []
    for (t, r) in (tb, ts):
        tt = t.astype("int64").astype("datetime64[m]")
        for a, b in BLOCKS:
            m = (tt >= a) & (tt < b)
            if m.sum() < MIN_N:
                return 0.0
            v = pf(r[m])
            if not np.isfinite(v):
                v = 99.0
            vals.append(v)
    return float(min(vals))


def split(t, r):
    tt = t.astype("int64").astype("datetime64[m]")
    return r[tt < IS_END], tt[tt >= IS_END], r[tt >= IS_END]


def weekly_boot(times, r, reps=2000, seed=7):
    """Profit-factor percentiles from resampling calendar weeks (keeps same-week trades together)."""
    if len(r) == 0:
        return [float("nan")] * 3
    wk = times.astype("datetime64[W]").astype(np.int64)
    groups = [r[wk == w] for w in np.unique(wk)]
    rng = np.random.default_rng(seed); out = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        out.append(pf(np.concatenate([groups[i] for i in pick])))
    out = np.asarray(out); out = out[np.isfinite(out)]
    return [float(np.percentile(out, q)) for q in (5, 50, 95)]


OOS_MID = np.datetime64("2026-08-15T00:00")


def select(work, out_json, prefix="cand"):
    rows, picks_all = [], []
    for tf in TFS:
        loaded = load_cands(work, prefix, tf)
        if loaded is None:
            continue
        P, Bs, Ss = loaded
        sc = np.array([is_score(Bs[i], Ss[i]) for i in range(len(P))])
        elig = np.where(sc > 0)[0]
        order = elig[np.argsort(-sc[elig], kind="stable")]
        picked, fams = [], set()
        for i in order:
            if sc[i] < PASS_PF or len(picked) >= TOPK:
                break
            fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
            if fam in fams:
                continue
            fams.add(fam); picked.append(int(i))
        row = dict(symbol=SYM, tf=tf, setups=len(P), eligible=int(len(elig)), is_ge_1_3=int((sc >= PASS_PF).sum()), picked=len(picked))
        # baseline of the timeframe: every eligible setup, unselected
        if len(elig):
            ob = [split(*Bs[i]) for i in elig]
            allr = np.concatenate([x[2] for x in ob]) if ob else np.zeros(0)
            row["all_eligible_oos_pf"] = pf(allr)
            row["all_eligible_share_oos_ge_1_3"] = float(np.mean([pf(x[2]) >= PASS_PF for x in ob if len(x[2]) >= 15] or [np.nan]))
        if picked:
            isr = [split(*Bs[i])[0] for i in picked]
            ot = np.concatenate([split(*Bs[i])[1] for i in picked]); orr = np.concatenate([split(*Bs[i])[2] for i in picked])
            st = np.concatenate([split(*Ss[i])[1] for i in picked]); sr = np.concatenate([split(*Ss[i])[2] for i in picked])
            ind = [pf(split(*Bs[i])[2]) for i in picked]; ind_n = [len(split(*Bs[i])[2]) for i in picked]
            lo, med, hi = weekly_boot(ot, orr)
            row.update(oos_pf_first_half=pf(orr[ot < OOS_MID]), oos_pf_second_half=pf(orr[ot >= OOS_MID]),
                       is_score_median=float(np.median(sc[picked])), is_pf_pooled=pf(np.concatenate(isr)),
                       oos_n=int(len(orr)), oos_pf=pf(orr), oos_net_r=float(orr.sum()),
                       oos_stress_n=int(len(sr)), oos_stress_pf=pf(sr), oos_stress_net_r=float(sr.sum()),
                       oos_pf_p05=lo, oos_pf_p95=hi,
                       oos_individual_ge_1_3=int(sum(1 for v, n in zip(ind, ind_n) if n >= 15 and v >= PASS_PF)),
                       oos_individual_median_pf=float(np.nanmedian(ind)),
                       top1_is_score=float(sc[picked[0]]), top1_oos_n=int(ind_n[0]), top1_oos_pf=ind[0])
            # luck check: how often do 10 random eligible setups of this timeframe do as well out of sample?
            rng = np.random.default_rng(11); better = 0; reps = 1000
            oos_cache = {int(i): split(*Bs[i])[2] for i in elig}
            for _ in range(reps):
                ch = rng.choice(elig, size=min(len(picked), len(elig)), replace=False)
                if pf(np.concatenate([oos_cache[int(i)] for i in ch])) >= row["oos_pf"]:
                    better += 1
            row["random_pick_as_good"] = better / reps
            row["passes"] = bool(row["oos_pf"] >= PASS_PF and row["oos_n"] >= PASS_N)
            row["passes_robust"] = bool(row["passes"] and row["oos_stress_pf"] >= 1.1 and
                                        row["oos_pf_first_half"] >= 1.0 and row["oos_pf_second_half"] >= 1.0)
            for rank, i in enumerate(picked, 1):
                picks_all.append(dict(P[i], symbol=SYM, rank=rank, is_score=float(sc[i]), oos_n=int(ind_n[rank - 1]),
                                      oos_pf=ind[rank - 1], oos_stress_pf=pf(split(*Ss[i])[2])))
        else:
            row["passes"] = False
        rows.append(row)
    out = dict(symbol=SYM, is_end=str(IS_END), min_n=MIN_N, topk=TOPK, pass_pf=PASS_PF, pass_n=PASS_N, stress=STRESS,
               timeframes=rows, picks=picks_all)
    json.dump(out, open(out_json, "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    cols = ["tf", "setups", "eligible", "is_ge_1_3", "picked", "is_score_median", "oos_n", "oos_pf", "oos_stress_pf",
            "oos_pf_p05", "oos_pf_p95", "oos_individual_ge_1_3", "all_eligible_oos_pf", "random_pick_as_good", "passes"]
    df = pd.DataFrame(rows)
    print(df[[c for c in cols if c in df]].round(2).to_string(index=False))


def vt_costs(work, out_json, prefix="candx"):
    """Gold only: the protocol's picks of every timeframe, re-run at VT Markets' own costs (VT_SPREAD, VT_COMM),
    and the same with a one-minute delay, pessimistic trailing and 0.10 slippage on top."""
    assert SYM == "XAUUSD"
    mk = market(work, flat_spread=VT_SPREAD)
    vt = dict(comm=VT_COMM, max_spread=5.0)
    vt_hard = dict(vt, trail_worst=1, delay=1, slip=0.10)
    runner = mk.run if prefix == "cand" else mk.run_y
    rows = []
    for tf in TFS:
        loaded = load_cands(work, prefix, tf)
        if loaded is None:
            continue
        P, Bs, Ss = loaded
        sc = np.array([is_score(Bs[i], Ss[i]) for i in range(len(P))])
        elig = np.where(sc > 0)[0]
        order = elig[np.argsort(-sc[elig], kind="stable")]
        picked, fams = [], set()
        for i in order:
            if sc[i] < PASS_PF or len(picked) >= TOPK:
                break
            fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
            if fam in fams:
                continue
            fams.add(fam); picked.append(int(i))
        row = dict(symbol=SYM, tf=tf, picked=len(picked))
        if picked:
            for name, extra in (("vt", vt), ("vt_hard", vt_hard)):
                isr, oor = [], []
                for i in picked:
                    c = dict(X.BASE); c.update(P[i]); c.update(extra)
                    df = runner(X.engine_cfg(c))
                    tt = df.entry_time.values.astype("datetime64[m]"); r = df.r.values.astype(float)
                    isr.append(r[tt < IS_END]); oor.append(r[tt >= IS_END])
                isr, oor = np.concatenate(isr), np.concatenate(oor)
                row.update({f"{name}_is_pf": pf(isr), f"{name}_oos_n": int(len(oor)), f"{name}_oos_pf": pf(oor),
                            f"{name}_oos_net_r": float(oor.sum())})
            row["base_oos_pf"] = pf(np.concatenate([split(*Bs[i])[2] for i in picked]))
        rows.append(row)
    json.dump(dict(vt_spread=VT_SPREAD, vt_comm=VT_COMM, timeframes=rows), open(out_json, "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).round(2).to_string(index=False))


def block_pfs(t, r):
    tt = t.astype("int64").astype("datetime64[m]")
    out = []
    for a, b in BLOCKS:
        m = (tt >= a) & (tt < b)
        if m.sum() < MIN_N:
            return None
        v = pf(r[m]); out.append(v if np.isfinite(v) else 99.0)
    return out


def sensitivity(work, out_json, prefix="cand"):
    """Other in-sample selection rules, to see whether the answer depends on the rule (robustness only:
    the protocol's own rule is select())."""
    rows = []
    for tf in TFS:
        loaded = load_cands(work, prefix, tf)
        if loaded is None:
            continue
        P, Bs, Ss = loaded
        n = len(P)
        main = np.array([is_score(Bs[i], Ss[i]) for i in range(n)])
        base3 = np.array([min(b) if (b := block_pfs(*Bs[i])) else 0.0 for i in range(n)])
        whole = np.array([pf(split(*Bs[i])[0]) if len(split(*Bs[i])[0]) >= 3 * MIN_N else 0.0 for i in range(n)])
        whole = np.where(np.isfinite(whole), whole, 0.0)

        def pick(score, k, families, thresh):
            order = np.argsort(-score, kind="stable"); out, fams = [], set()
            for i in order:
                if score[i] <= 0 or score[i] < thresh or len(out) >= k:
                    break
                fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
                if families and fam in fams:
                    continue
                fams.add(fam); out.append(int(i))
            return out

        rules = {"main rule (top 10, score >= 1.3)": pick(main, TOPK, True, PASS_PF),
                 "top 10 by score, no threshold": pick(main, TOPK, True, 0.0),
                 "top 50 by score": pick(main, 50, False, 0.0),
                 "top 10, base costs only": pick(base3, TOPK, True, PASS_PF),
                 "top 10 by whole in-sample PF": pick(whole, TOPK, True, 0.0)}
        for name, idx in rules.items():
            if not idx:
                rows.append(dict(symbol=SYM, tf=tf, rule=name, picked=0)); continue
            orr = np.concatenate([split(*Bs[i])[2] for i in idx]); sr = np.concatenate([split(*Ss[i])[2] for i in idx])
            rows.append(dict(symbol=SYM, tf=tf, rule=name, picked=len(idx), oos_n=int(len(orr)), oos_pf=pf(orr),
                             oos_stress_pf=pf(sr), passes=bool(pf(orr) >= PASS_PF and len(orr) >= PASS_N)))
    json.dump(rows, open(out_json, "w"), indent=1, default=float)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(df.pivot_table(index="tf", columns="rule", values="oos_pf", sort=False).reindex(TFS).round(2).to_string())
    print("passing cells:", df[df.get("passes", False) == True][["tf", "rule", "oos_n", "oos_pf", "oos_stress_pf"]].round(2).to_dict("records"))


def by_kind(work, out_json, prefix="candx"):
    """candx only: the protocol's pick-and-test for each trailing family, per timeframe and over all timeframes
    (information on whether any family helps; 11 families x 8 timeframes are many cells, so single passes
    can be luck)."""
    rows = []
    pooled = {}
    for tf in TFS:
        loaded = load_cands(work, prefix, tf)
        if loaded is None:
            continue
        P, Bs, Ss = loaded
        sc = np.array([is_score(Bs[i], Ss[i]) for i in range(len(P))])
        kinds_here = list(dict.fromkeys(P[i]["trail_kind"] for i in range(len(P))))
        for kind in kinds_here:
            idx = np.array([i for i in range(len(P)) if P[i]["trail_kind"] == kind])
            elig = idx[sc[idx] > 0]
            order = elig[np.argsort(-sc[elig], kind="stable")]
            picked, fams = [], set()
            for i in order:
                if sc[i] < PASS_PF or len(picked) >= TOPK:
                    break
                fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
                if fam in fams:
                    continue
                fams.add(fam); picked.append(int(i))
            allr = np.concatenate([split(*Bs[i])[2] for i in elig]) if len(elig) else np.zeros(0)
            row = dict(symbol=SYM, tf=tf, kind=kind, setups=int(len(idx)), eligible=int(len(elig)),
                       is_ge_1_3=int((sc[idx] >= PASS_PF).sum()), picked=len(picked), all_eligible_oos_pf=pf(allr))
            if picked:
                orr = np.concatenate([split(*Bs[i])[2] for i in picked]); sr = np.concatenate([split(*Ss[i])[2] for i in picked])
                row.update(oos_n=int(len(orr)), oos_pf=pf(orr), oos_stress_pf=pf(sr),
                           passes=bool(pf(orr) >= PASS_PF and len(orr) >= PASS_N))
                pooled.setdefault(kind, [[], []]); pooled[kind][0].append(orr); pooled[kind][1].append(sr)
            rows.append(row)
    tot = [dict(symbol=SYM, tf="ALL", kind=k, oos_n=int(sum(len(x) for x in v[0])), oos_pf=pf(np.concatenate(v[0])),
                oos_stress_pf=pf(np.concatenate(v[1]))) for k, v in pooled.items()]
    json.dump(dict(cells=rows, by_kind_all_timeframes=tot), open(out_json, "w"), indent=1, default=float)
    df = pd.DataFrame(rows)
    for col in ("oos_pf", "oos_n", "oos_stress_pf", "passes"):
        if col not in df:
            df[col] = np.nan
    pd.set_option("display.width", 250)
    print("OOS pooled PF of the in-sample picks, by timeframe and trailing family (blank: nothing passed in-sample)")
    if df["oos_pf"].notna().any():
        print(df.pivot_table(index="tf", columns="kind", values="oos_pf", sort=False).reindex(TFS).round(2).to_string())
    print("unselected baseline (all eligible setups) OOS PF")
    print(df.pivot_table(index="tf", columns="kind", values="all_eligible_oos_pf", sort=False).reindex(TFS).round(2).to_string())
    if tot:
        print(pd.DataFrame(tot).round(2).to_string(index=False))
    if df["passes"].notna().any():
        print("passing cells:", df[df["passes"] == True][["tf", "kind", "picked", "oos_n", "oos_pf", "oos_stress_pf"]].round(2).to_dict("records"))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "runx":
        run_x(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "select":
        select(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "cand")
    elif cmd == "sens":
        sensitivity(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "cand")
    elif cmd == "rerun":
        rerun_kind(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "fresh":
        fresh(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 25, int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "runy":
        run_y(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "kinds":
        by_kind(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "candx")
    elif cmd == "vt":
        vt_costs(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "candx")
