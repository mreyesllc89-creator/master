#!/usr/bin/env python3
"""
Tick data for the tick-by-tick replay of the Loma trailing systems (hump_tick.py, tick_replay.py).

Sources (downloaded by tick_download.py into $TICK_DIR, default <scratchpad>/ticks):
  gold  Dukascopy XAUUSD ticks, gold/XAUUSD_<YYYY-MM>.npz: t (int64, epoch ms UTC), bid, ask (int32, price x 1000)
  btc   Binance BTCUSDT one-second klines, btc/BTCUSDT_<YYYY-MM>.npz: t (int64, epoch s UTC), o, h, l, c (int32, x 100)

Everything is put on broker server time (New York + 7 hours, as hump_tf_recal.utc_to_server): GMT+3 while New York
is on summer time, GMT+2 otherwise. When New York leaves summer time the server clock repeats an hour: the second
pass of that hour is dropped, as the one-minute series of the study drop duplicated minutes (keep the first).

Ticks
  gold  one tick per record: (server time in ms, bid, ask).
  btc   four price points per second, at the second's own time: the open, then the extreme nearer to the open, then
        the other extreme, then the close (a tie, open exactly midway, takes the low first). These are trade prices
        and are used as the mid; bid and ask are mid -/+ half the cost model's spread (the expansion is done by
        hump_tick's stream, mode 1; order 1 there puts the farther extreme first, for tick_replay.py's order check).
        Binance writes a second without trades as a flat kline at the last price, while its one-minute kline opens at
        the minute's first trade: the empty seconds at the start of a minute are removed (empty_leading_seconds, which
        reads only whether the study's one-minute open differs from the previous close); later empty seconds repeat
        the last price and change nothing. Binance's one-second files of Jan - Mar 2023 lack 1,946 / 734 / 6,091 seconds.

One-minute bars (mid prices), built from the same ticks, one bar per server minute that has at least one tick:
  gold  mid = (bid + ask) / 2 of every tick: open = first, high = max, low = min, close = last.
  btc   open = first second's open, high = max of the highs, low = min of the lows, close = last second's close;
        equal to the Binance one-minute klines of the re-calibration in every minute from April 2023 on (check_btc).

Cost models (quotes around the same mid, so that every model has the same bars and the same signals)
  gold vt      half spread = 0.075 x (Dukascopy's own spread of the tick / its median in that calendar month):
               VT Markets' 0.15 spread, with Dukascopy's spikes (night, news, the daily reopen) kept (gold_vt_quotes;
               the replay, tick_replay.GoldSpan, also rounds these quotes to the cent as a broker quotes, with a
               spread of at least one cent: Dukascopy's rare spreads under a thirtieth of its median would round
               to 0, a quote VT never makes)
  gold duk_raw Dukascopy's own bid and ask
  btc  vt      mid -/+ 5 USD (the study's 10 USD spread)

Usage (from research/):
  python3 tick_data.py check_btc  [out_json] [months YYYY-MM,...]   # bars from the seconds against the study's Binance bars
  python3 tick_data.py check_gold [out_json] [months YYYY-MM,...]   # bars from Dukascopy's ticks against the Dukascopy and
                                                                    # FTMO one-minute bars of the study (downloaded months)
"""
import datetime as dt, glob, os, sys
import numpy as np, pandas as pd

SP = os.environ.get("LOMA_SCRATCH", "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad")   # LOMA_SCRATCH: the scratch folder of the data
TICK_DIR = os.environ.get("TICK_DIR", os.path.join(SP, "ticks"))
GOLD_DIV = 1000.0
BTC_DIV = 100.0
VT_HALF = 0.075               # VT Markets XAUUSD-ECNc spread 0.15 / 2
BTC_HALF = 5.0                # the study's BTC spread 10 / 2


# ----------------------------------------------------------------------------- clock
def _dst_utc(years):
    """US summer time [start, end) in UTC seconds per year: second Sunday of March 07:00 UTC (02:00 EST) to the first
    Sunday of November 06:00 UTC (02:00 EDT)."""
    out = []
    for y in years:
        d = dt.date(y, 3, 1); d += dt.timedelta(days=(6 - d.weekday()) % 7 + 7)          # second Sunday of March
        e = dt.date(y, 11, 1); e += dt.timedelta(days=(6 - e.weekday()) % 7)             # first Sunday of November
        a = int(dt.datetime(d.year, d.month, d.day, 7, tzinfo=dt.timezone.utc).timestamp())
        b = int(dt.datetime(e.year, e.month, e.day, 6, tzinfo=dt.timezone.utc).timestamp())
        out.append((a, b))
    return out


_DST = np.array(_dst_utc(range(2015, 2035)), dtype=np.int64)


def utc_to_server_s(t):
    """Epoch seconds UTC -> epoch seconds of broker server time (New York + 7 h)."""
    t = np.asarray(t, dtype=np.int64)
    k = np.searchsorted(_DST[:, 0], t, side="right") - 1
    summer = (k >= 0) & (t < _DST[np.clip(k, 0, None), 1])
    return t + np.where(summer, 3 * 3600, 2 * 3600)


def _keep_first(ts):
    """Mask that drops the second pass of a repeated server hour: keep a record only when its server time is later
    than every earlier record's (the series are sorted by UTC)."""
    if len(ts) == 0:
        return np.zeros(0, bool)
    prev = np.maximum.accumulate(ts)
    keep = np.ones(len(ts), bool)
    keep[1:] = ts[1:] > prev[:-1]
    return keep


def _months(a, b):
    """Calendar months (UTC) that cover server-time [a, b) with a few hours of margin."""
    a = pd.Timestamp(a) - pd.Timedelta(hours=4); b = pd.Timestamp(b) + pd.Timedelta(hours=4)
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append((y, m)); y, m = (y + (m == 12), m % 12 + 1)
    return out


def _sec(x):
    return int(pd.Timestamp(x).value // 10 ** 9)


# the UTC months the downloads cover (tick_download.py: Dukascopy XAUUSD 2024-07-01 .. 2026-11-13, Binance BTCUSDT
# 2023-01-01 .. 2026-11-13); inside them every month a span touches must be on disk (require_months)
DATA_MONTHS = {"gold": ("2024-07", "2026-11"), "btc": ("2023-01", "2026-11")}
_FILE = {"gold": ("gold", "XAUUSD"), "btc": ("btc", "BTCUSDT")}


def month_file(kind, y, m, tick_dir=TICK_DIR):
    sub, pre = _FILE[kind]
    return os.path.join(tick_dir, sub, f"{pre}_{y}-{m:02d}.npz")


def require_months(kind, a, b, tick_dir=TICK_DIR):
    """Raise when a month file that holds part of server time [a, b) is missing: the UTC months of [a - 3 h, b - 2 h)
    (server time is UTC + 2 or 3 h) that lie inside the downloaded range DATA_MONTHS[kind]. A span is never built on
    part of its data (a download not finished, a file lost) without notice."""
    lo, hi = DATA_MONTHS[kind]
    x = pd.Timestamp(a) - pd.Timedelta(hours=3); z = pd.Timestamp(b) - pd.Timedelta(hours=2) - pd.Timedelta(seconds=1)
    missing = []
    y, m = x.year, x.month
    while (y, m) <= (z.year, z.month):
        if lo <= f"{y}-{m:02d}" <= hi and not os.path.exists(month_file(kind, y, m, tick_dir)):
            missing.append(f"{y}-{m:02d}")
        y, m = (y + (m == 12), m % 12 + 1)
    if missing:
        raise FileNotFoundError(f"{kind} {a} .. {b}: month files missing {missing} (download not finished?)")


# ----------------------------------------------------------------------------- loaders
class BtcSeconds:
    """Binance one-second klines on server time: t (int64 server s), o, h, l, c (int32 x 100). Read month by month (the
    memory peak is the result plus one month). Every month file of the span must exist (require_months)."""

    def __init__(self, a, b, tick_dir=TICK_DIR):
        require_months("btc", a, b, tick_dir)
        ts, cols = [], {k: [] for k in "ohlc"}
        a_s, b_s = _sec(a), _sec(b)
        run_max = None
        self.dropped_repeat = 0
        for (y, m) in _months(a, b):
            fn = os.path.join(tick_dir, "btc", f"BTCUSDT_{y}-{m:02d}.npz")
            if not os.path.exists(fn):
                continue
            d = np.load(fn)
            srv = utc_to_server_s(d["t"])
            keep = _keep_first(srv)
            if run_max is not None and len(srv):
                keep &= srv > run_max
            self.dropped_repeat += int((~keep).sum())
            if len(srv):
                run_max = max(run_max if run_max is not None else srv[0], int(srv.max()))
            keep &= (srv >= a_s) & (srv < b_s)
            if keep.any():
                ts.append(srv[keep])
                for k in "ohlc":
                    cols[k].append(d[k][keep])
            del d, srv, keep
        self.t = np.concatenate(ts) if ts else np.zeros(0, np.int64)
        del ts
        for k in "ohlc":
            setattr(self, k, np.concatenate(cols[k]) if cols[k] else np.zeros(0, np.int32))
            cols[k] = None
        self.empty_dropped = 0
        assert np.all(np.diff(self.t) > 0)

    def subset(self, keep):
        """Keep only the records of the mask, in place, one array at a time (small memory peak)."""
        for k in ("t", "o", "h", "l", "c"):
            setattr(self, k, getattr(self, k)[keep])
        self.empty_dropped += int((~keep).sum())
        return self


def empty_leading_seconds(sec, ref_open):
    """Seconds without a trade at the start of a minute. Binance writes a second without trades as a flat kline at the
    last price (o = h = l = c = the previous close), while its one-minute kline opens at the minute's first trade. A
    leading flat second at the previous close can only be a trade when that price is the minute's first trade, so
    when the minute's first trade (ref_open, x 100, one value per minute of btc_m1(sec)) differs from the previous
    close, every leading flat second at the previous close is empty. When it equals the previous close the leading
    flat seconds are at the minute's open either way and are kept. Seconds without trades later in a minute repeat
    the last trade price and change nothing. Returns a mask of the empty leading seconds."""
    _, st, en = btc_m1(sec)
    flat = (sec.o == sec.h) & (sec.h == sec.l) & (sec.l == sec.c)
    pc = np.r_[-1, sec.c[st[1:] - 1]].astype(np.int64)
    drop = np.zeros(len(sec.t), bool)
    for k in np.where((np.asarray(ref_open, np.int64) != pc) & (np.arange(len(st)) > 0))[0]:
        q = st[k]
        while q < en[k] and flat[q] and sec.o[q] == pc[k]:
            drop[q] = True; q += 1
    return drop


def btc_reference_m1(a, b):
    """The study's Binance BTCUSDT one-minute bars (server time) for [a, b): the pretest series (btc_raw_pre zips)
    before 2025, the re-calibration series (recal/btc/m1.pkl) from 2025."""
    out = []
    if pd.Timestamp(a) < pd.Timestamp("2025-01-01 02:00"):
        pre = btc_minutes_from_zips(os.path.join(SP, "btc_raw_pre"))
        out.append(pre[(pre.index >= pd.Timestamp(a)) & (pre.index < min(pd.Timestamp(b), pd.Timestamp("2025-01-01 02:00")))])
    if pd.Timestamp(b) > pd.Timestamp("2025-01-01 02:00"):
        rec = _recal_m1("btc")
        out.append(rec[(rec.index >= max(pd.Timestamp(a), pd.Timestamp("2025-01-01 02:00"))) & (rec.index < pd.Timestamp(b))])
    return pd.concat(out)


def load_btc(a, b, ref=None):
    """Seconds of [a, b) (server time) with the empty leading seconds removed, their one-minute bars (x 100, int) and
    the study's reference bars of the same minutes (float)."""
    sec = BtcSeconds(a, b)
    if ref is None:
        ref = btc_reference_m1(a, b)
    bars, _, _ = btc_m1(sec)
    ro = (ref["open"].reindex(bars.index) * BTC_DIV).round()
    assert not ro.isna().any(), "minutes without a reference bar"
    sec = sec.subset(~empty_leading_seconds(sec, ro.values.astype(np.int64)))
    return sec


class GoldTicks:
    """Dukascopy XAUUSD ticks on server time: t (int64 server ms), bid, ask (int32 x 1000). Every month file of the
    span must exist (require_months)."""

    def __init__(self, a, b, tick_dir=TICK_DIR):
        require_months("gold", a, b, tick_dir)
        ts, bs, as_ = [], [], []
        self.months = []
        for (y, m) in _months(a, b):
            fn = os.path.join(tick_dir, "gold", f"XAUUSD_{y}-{m:02d}.npz")
            if not os.path.exists(fn):
                continue
            d = np.load(fn)
            ts.append(d["t"]); bs.append(d["bid"]); as_.append(d["ask"]); self.months.append(f"{y}-{m:02d}")
        t = np.concatenate(ts) if ts else np.zeros(0, np.int64)
        srv = (utc_to_server_s(t // 1000) - t // 1000) * 1000 + t      # same offset at the millisecond level
        keep = _keep_first_ms(srv) & (srv >= _sec(a) * 1000) & (srv < _sec(b) * 1000)
        self.t = srv[keep]
        self.bid = np.concatenate(bs)[keep] if ts else np.zeros(0, np.int32)
        self.ask = np.concatenate(as_)[keep] if ts else np.zeros(0, np.int32)
        self.crossed = int((self.ask < self.bid).sum())


def _keep_first_ms(ts):
    """As _keep_first, for millisecond times where several ticks may share one millisecond (>= instead of >)."""
    if len(ts) == 0:
        return np.zeros(0, bool)
    prev = np.maximum.accumulate(ts)
    keep = np.ones(len(ts), bool)
    keep[1:] = ts[1:] >= prev[:-1]
    return keep


def gold_months_available(tick_dir=TICK_DIR):
    return sorted(os.path.basename(f)[7:14] for f in glob.glob(os.path.join(tick_dir, "gold", "XAUUSD_????-??.npz")))


# ----------------------------------------------------------------------------- one-minute bars
def _groups(minute):
    """Start index of every run of equal values in a sorted array, and the run values."""
    if len(minute) == 0:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    st = np.r_[0, np.where(np.diff(minute) != 0)[0] + 1].astype(np.int64)
    return st, minute[st]


def btc_m1(sec):
    """One-minute mid bars from the seconds (prices x 100 as int64, exact) and the second range of every bar."""
    st, mins = _groups(sec.t // 60)
    end = np.r_[st[1:], len(sec.t)]
    o = sec.o[st].astype(np.int64); c = sec.c[end - 1].astype(np.int64)
    h = np.maximum.reduceat(sec.h, st).astype(np.int64); l = np.minimum.reduceat(sec.l, st).astype(np.int64)
    idx = pd.to_datetime(mins * 60, unit="s")
    return pd.DataFrame(dict(open=o, high=h, low=l, close=c), index=idx), st, end


def gold_m1(tk, bid=None, ask=None):
    """One-minute mid bars from ticks (bid / ask in price units; default Dukascopy's own), with the tick range of
    every bar and per-bar quote facts: first tick's spread, highest bid, lowest ask, lowest bid + smallest spread."""
    if bid is None:
        bid = tk.bid / GOLD_DIV; ask = tk.ask / GOLD_DIV
    st, mins = _groups(tk.t // 60000)
    end = np.r_[st[1:], len(tk.t)]
    mid = 0.5 * (bid + ask)
    bars = pd.DataFrame(dict(open=mid[st], high=np.maximum.reduceat(mid, st), low=np.minimum.reduceat(mid, st),
                             close=mid[end - 1]), index=pd.to_datetime(mins * 60, unit="s"))
    spr = ask - bid
    facts = pd.DataFrame(dict(spread_first=spr[st], bid_high=np.maximum.reduceat(bid, st), ask_low=np.minimum.reduceat(ask, st),
                              bid_low_min_spread=np.minimum.reduceat(bid, st) + np.minimum.reduceat(spr, st),
                              ticks=end - st), index=bars.index)
    return bars, facts, st, end


# ----------------------------------------------------------------------------- cost models
def gold_vt_quotes(tk, half=VT_HALF):
    """VT model: mid of Dukascopy's ticks -/+ half x (Dukascopy's spread / its median in the tick's calendar month,
    server time). Returns bid, ask (float64) and the monthly medians used."""
    mid2 = tk.bid.astype(np.int64) + tk.ask.astype(np.int64)                   # 2 x mid x 1000, exact
    spr = (tk.ask.astype(np.int64) - tk.bid.astype(np.int64)).astype(np.float64)
    month = pd.to_datetime(tk.t, unit="ms").to_period("M").asi8 if len(tk.t) else np.zeros(0, np.int64)
    meds = {}
    hs = np.empty(len(spr))
    for mo in np.unique(month):
        sel = month == mo
        med = float(np.median(spr[sel]))
        meds[str(pd.Period(ordinal=int(mo), freq="M"))] = med / GOLD_DIV
        hs[sel] = half * spr[sel] / med
    mid = mid2 / (2 * GOLD_DIV)
    return mid - hs, mid + hs, meds


def gold_raw_quotes(tk):
    return tk.bid / GOLD_DIV, tk.ask / GOLD_DIV


# ----------------------------------------------------------------------------- checks
def _recal_m1(sym):
    return pd.read_pickle(os.path.join(SP, "recal", sym, "m1.pkl"))


def btc_minutes_from_zips(folder):
    """The one-minute series of pretest_picks.py (Binance BTCUSDT 1m zips, UTC, converted to server time once)."""
    import io, zipfile
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hump_tf_recal as R
    parts = []
    for z in sorted(glob.glob(os.path.join(folder, "BTCUSDT-1m-*.zip"))):
        with zipfile.ZipFile(z) as f:
            raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
        t = raw[0].astype("int64")
        parts.append(pd.DataFrame(dict(datetime=pd.to_datetime(t, unit="us" if t.iloc[0] > 1e14 else "ms"),
                                       open=raw[1], high=raw[2], low=raw[3], close=raw[4])))
    m1 = pd.concat(parts).drop_duplicates("datetime").sort_values("datetime")
    m1.index = R.utc_to_server(pd.DatetimeIndex(m1["datetime"]))
    return m1[~m1.index.duplicated()].sort_index()[["open", "high", "low", "close"]].astype(float)


def compare_btc(ref, a, b, label, drop_empty=True):
    """Minute-by-minute equality of the bars built from the seconds with a reference one-minute series (server time).
    drop_empty: without the empty leading seconds (empty_leading_seconds), as the replay uses them."""
    sec = BtcSeconds(pd.Timestamp(a) - pd.Timedelta(minutes=1), b)       # one minute before: the previous close is known
    raw_bars, _, _ = btc_m1(sec)
    raw = raw_bars.reindex(ref.index[(ref.index >= pd.Timestamp(a)) & (ref.index < pd.Timestamp(b))])
    rr = (ref.reindex(raw.index) * BTC_DIV).round()
    raw_same = int((raw.values == rr.values).all(axis=1).sum())
    if drop_empty:
        ro = (ref["open"].reindex(raw_bars.index) * BTC_DIV).round()
        sec = sec.subset(~empty_leading_seconds(sec, ro.fillna(-1).values.astype(np.int64)))
    bars, st, en = btc_m1(sec)
    bars = bars[bars.index >= pd.Timestamp(a)]
    ref = ref[(ref.index >= pd.Timestamp(a)) & (ref.index < pd.Timestamp(b))]
    r = (ref * BTC_DIV).round().astype(np.int64)
    only_ref = r.index.difference(bars.index); only_sec = bars.index.difference(r.index)
    both = r.index.intersection(bars.index)
    x, y = bars.loc[both], r.loc[both]
    neq = {c: int((x[c].values != y[c].values).sum()) for c in ("open", "high", "low", "close")}
    line = (f"{label}: {len(bars):,} minutes from the seconds, {len(r):,} reference minutes; identical in all four prices: "
            f"{int(((x.values == y.values).all(axis=1)).sum()):,} of {len(both):,}; differing {neq}; "
            f"minutes only in the reference {len(only_ref)}, only in the seconds {len(only_sec)}; "
            f"seconds dropped in a repeated server hour {sec.dropped_repeat}; empty leading seconds dropped {sec.empty_dropped} "
            f"(with them: {raw_same:,} identical minutes)")
    print(line, flush=True)
    bad = x.index[(x.values != y.values).any(axis=1)]
    return dict(label=label, minutes_seconds=int(len(bars)), minutes_ref=int(len(r)), compared=int(len(both)),
                identical=int(((x.values == y.values).all(axis=1)).sum()), differ=neq, only_ref=[str(v) for v in only_ref[:20]],
                n_only_ref=int(len(only_ref)), n_only_seconds=int(len(only_sec)), only_seconds=[str(v) for v in only_sec[:20]],
                first_differences=[dict(t=str(i), sec=x.loc[i].tolist(), ref=y.loc[i].tolist()) for i in bad[:10]],
                dropped_repeat_seconds=sec.dropped_repeat, empty_leading_seconds=sec.empty_dropped,
                identical_with_empty_seconds=raw_same, line=line)


def check_btc(out_json=None, months=None):
    """The one-minute bars from Binance's seconds against the bars of the re-calibration: 2023-2024 (pretest_picks.py,
    Binance 1m zips in btc_raw_pre) and Jan 2025 - Nov 13 2026 (hump_tf_recal build, recal/btc/m1.pkl)."""
    import json
    res = []
    pre = btc_minutes_from_zips(os.path.join(SP, "btc_raw_pre"))
    rec = _recal_m1("btc")
    spans = [("2023-2024 (pretest series)", pre, "2023-01-01 02:00", "2025-01-01 02:00"),
             ("Jan 2025 - Nov 2026 (re-calibration series)", rec, str(rec.index[0]), str(rec.index[-1] + pd.Timedelta(minutes=1)))]
    for label, ref, a, b in spans:
        # month by month to keep the memory small
        for lo, hi in _month_slices(a, b, months):
            res.append(compare_btc(ref, lo, hi, f"{label} {lo[:7]}"))
    tot = dict(compared=sum(r["compared"] for r in res), identical=sum(r["identical"] for r in res),
               only_ref=sum(r["n_only_ref"] for r in res), only_seconds=sum(r["n_only_seconds"] for r in res),
               empty_leading_seconds=sum(r["empty_leading_seconds"] for r in res),
               identical_with_empty_seconds=sum(r["identical_with_empty_seconds"] for r in res))
    print("BTC TOTAL", tot, flush=True)
    if out_json:
        json.dump(dict(total=tot, months=res), open(out_json, "w"), indent=1)
    return tot, res


def _month_slices(a, b, months=None):
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    out = []
    cur = a
    while cur < b:
        nxt = min(b, (cur + pd.offsets.MonthBegin(1)).normalize())
        if months is None or cur.strftime("%Y-%m") in months:
            out.append((str(cur), str(nxt)))
        cur = nxt
    return out


def gold_reference_m1():
    """The study's gold one-minute bars: Dukascopy M1 of Jul-Dec 2024 (pretest_picks.py, duk_pre), FTMO to 15 May
    2026 and Dukascopy M1 after it (hump_tf_recal build, recal/gold/m1.pkl). Returns {name: (bars, half_spread)}."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import duk_to_m1 as D
    pre, pre_hs = D.load(os.path.join(SP, "duk_pre"))
    rec = _recal_m1("gold")
    cut = pd.Timestamp("2026-05-16")
    return {"dukascopy_m1_2024": (pre[["open", "high", "low", "close"]].astype(float), pre_hs),
            "ftmo_m1": (rec[rec.index < cut], None), "dukascopy_m1_2026": (rec[rec.index >= cut], None)}


def compare_gold(ref, a, b, label, tk=None):
    """Bars from Dukascopy's ticks (mid) against a reference one-minute series: missing minutes on either side, the
    clock offset that best lines the two up (correlation of one-minute returns at shifts of -3..+3 minutes), and
    price differences of open / high / low / close at the best offset."""
    if tk is None:
        tk = GoldTicks(a, b)
    bars, facts, st, en = gold_m1(tk)
    ref = ref[(ref.index >= pd.Timestamp(a)) & (ref.index < pd.Timestamp(b))]
    if len(bars) == 0 or len(ref) == 0:
        return None
    both = bars.index.intersection(ref.index)
    rt = bars["close"].diff(); rr = ref["close"].diff()
    corr = {}
    for sh in range(-3, 4):
        s = rr.copy(); s.index = s.index + pd.Timedelta(minutes=sh)
        j = rt.index.intersection(s.index)
        corr[sh] = float(np.corrcoef(rt.loc[j].fillna(0), s.loc[j].fillna(0))[0, 1]) if len(j) > 100 else float("nan")
    best = max(corr, key=lambda k: -1 if np.isnan(corr[k]) else corr[k])
    x, y = bars.loc[both], ref.loc[both]
    d = (x - y)
    q = lambda v: [round(float(np.percentile(np.abs(v), p)), 4) for p in (50, 90, 99)]
    row = dict(label=label, minutes_ticks=int(len(bars)), minutes_ref=int(len(ref)), both=int(len(both)),
               only_ref=int(len(ref.index.difference(bars.index))), only_ticks=int(len(bars.index.difference(ref.index))),
               best_offset_min=int(best), return_corr_by_offset={str(k): round(v, 4) for k, v in corr.items()},
               mean_diff={c: round(float(d[c].mean()), 4) for c in d}, abs_diff_p50_p90_p99={c: q(d[c].values) for c in d},
               high_above_ref_share=round(float((d["high"] > 1e-9).mean()), 3), low_below_ref_share=round(float((d["low"] < -1e-9).mean()), 3),
               range_ratio_median=round(float(np.median(((x.high - x.low) / (y.high - y.low).replace(0, np.nan)).dropna())), 3),
               tick_spread_median=round(float(np.median(tk.ask - tk.bid) / GOLD_DIV), 4), ticks=int(len(tk.t)))
    print(f"{label}: ticks {len(tk.t):,}, minutes ticks {len(bars):,} / ref {len(ref):,} (only ref {row['only_ref']}, only ticks {row['only_ticks']}), "
          f"best offset {best} min (corr {corr[best]:.3f}, at 0: {corr[0]:.3f}); |diff| p50/p90/p99 open {row['abs_diff_p50_p90_p99']['open']} "
          f"high {row['abs_diff_p50_p90_p99']['high']} low {row['abs_diff_p50_p90_p99']['low']} close {row['abs_diff_p50_p90_p99']['close']}; "
          f"mean diff {row['mean_diff']}; tick high above ref {row['high_above_ref_share']:.0%}, tick low below ref {row['low_below_ref_share']:.0%}; "
          f"range ratio {row['range_ratio_median']}", flush=True)
    return row


def check_gold(out_json=None, months=None):
    import json
    refs = gold_reference_m1()
    avail = gold_months_available()
    res = []
    for ym in avail:
        if months and ym not in months:
            continue
        a = pd.Timestamp(ym + "-01"); b = a + pd.offsets.MonthBegin(1)
        try:
            tk = GoldTicks(a, b)
        except FileNotFoundError as ex:          # the month before is not downloaded yet: its first hours are missing
            print(f"{ym}: skipped, {ex}", flush=True)
            continue
        for name, (ref, _) in refs.items():
            r = compare_gold(ref, a, b, f"{name} {ym}", tk)
            if r:
                res.append(r)
    if out_json:
        json.dump(res, open(out_json, "w"), indent=1)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "check_btc":
        check_btc(sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3].split(",") if len(sys.argv) > 3 else None)
    elif cmd == "check_gold":
        check_gold(sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3].split(",") if len(sys.argv) > 3 else None)
