#!/usr/bin/env python3
"""
Year-by-year test of the Loma (hump) method on long history, with one extra entry condition at a time.

Question: does any version of the method keep a profit factor of 1.3 on years it was not fitted to?

Protocol (fixed before any result was looked at):
  data      XAUUSD: Dukascopy M1 2019-2024, FTMO M1 2025 - 15 May 2026, Dukascopy after (to 13 Nov 2026).
            BTCUSD: Binance BTCUSDT M1 2018 - 13 Nov 2026, read in UTC and converted to server time once.
            The clock of every series is checked (hump_tf_recal.clock_check).
  scale     Prices rose several-fold over these years, so every dollar distance of a setup (stop buffer, minimum
            and maximum stop) and every cost is multiplied by price / anchor price, where the anchor is the mean
            price of the last 180 days of the series. A setup therefore means the same thing in every year, and
            every year pays the same share of the price in costs as the broker charges today.
  costs     base   XAUUSD: VT Markets, 0.15 spread (with the usual widening by hour) + 0.60 commission per ounce.
                   BTCUSD: 10 USD spread, no commission.
            stress entry one minute late, pessimistic trailing, slippage 0.10 / 3 USD, extra commission 0.07 / 2 USD.
  rules     as hump_engine.simulate, with three corrections found by the audit of this module: the gold weekend
            close is the EA's (Friday from 23:00 server time, and at the next open when that moment fell in a closure;
            a mid-week holiday closure is not known in advance, so a trade stays open over it); no entry on the first
            bar after a break of 30 minutes or more (its spread is several times the normal one); a reward exactly
            equal to the minimum reward is accepted (it was decided by floating-point rounding).
  setups    N random setups per timeframe from the calibration space of hump_search (EA's own trailing), with
            two larger minimum-stop values added so that setups can avoid stops that are small next to the cost.
  condition each setup is simulated once for all its signals; every entry condition is then applied as a mask
            on the signals, followed by the one-position-at-a-time rule. "base" is the method without a condition.
  windows   for test year Y the setups are scored on the three years before it: the lowest of six profit factors
            (three years x base and stress costs), at least 20 trades in each. Setups whose average cost per trade
            is above 1/8 R (stop under 8 times the round-trip cost) are dropped. Picks: the 10 best scores, one per
            (direction, session, trend filter) family, score >= 1.3. The picks are run on year Y.
  pass      all unseen years together: profit factor >= 1.3 on >= 100 trades, >= 1.1 with stress costs, no unseen
            year with 50+ trades below 1.0, and at least two unseen years with 50+ trades.
  final     the last year (2026, to 13 Nov) is not used to decide what passes. It is run once, for what passed.

Usage (from research/):
  [HUMP_SYMBOL=BTCUSD] python3 hump_wf.py build <work_dir> <source dirs, comma separated>
  [HUMP_SYMBOL=BTCUSD] python3 hump_wf.py run   <work_dir> <TF> <N> [workers]
  [HUMP_SYMBOL=BTCUSD] python3 hump_wf.py wf    <work_dir> <out_json>
  python3 hump_wf.py selftest
"""
import glob, io, json, os, pickle, random, sys, time, zipfile
from multiprocessing import Pool
import numba as nb, numpy as np, pandas as pd

os.environ["HUMP_SPACE"] = "2"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, xlzc_backtest as B
import hump_trail2 as T2
import hump_tf_recal as R

SYM = H.SYMBOL
if SYM not in ("XAUUSD", "BTCUSD", "EURUSD", "US500"):
    raise SystemExit(f"hump_wf: unknown symbol {SYM}")
BTC = SYM == "BTCUSD"
NEW = SYM in X.SCALED                           # EURUSD and US500: protocol 2 (stored in meta.json by build)
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
MIN_N, TOPK, PASS_PF, PASS_STRESS, PASS_N = 20, 10, 1.30, 1.10, 100
YEAR_N = 50                                     # an unseen year counts for the "no losing year" rule from this many trades
MAX_COST_R = 1.0 / 8.0                          # average round-trip cost per trade, in R
ANCHOR_DAYS = 180
if BTC:
    SPREAD0 = 10.0
    COSTS = (dict(slip=0.0, comm=0.0, delay=0, trail_worst=0), dict(slip=3.0, comm=2.0, delay=1, trail_worst=1))
    EXTRA_MIN_RISK = [100, 150]
elif SYM == "EURUSD":                           # VT Markets RAW ECN: 0.3 pips, 6 USD per 100,000 EUR round trip
    SPREAD0 = 0.00003
    COSTS = (dict(slip=0.0, comm=0.00006, delay=0, trail_worst=0), dict(slip=0.00002, comm=0.000066, delay=1, trail_worst=1))
    EXTRA_MIN_RISK = None                       # gold's [4.0, 6.0] x k: set by apply_scale() from meta.json
elif SYM == "US500":                            # VT Markets RAW ECN: 0.5 index points, no commission
    SPREAD0 = 0.5
    COSTS = (dict(slip=0.0, comm=0.0, delay=0, trail_worst=0), dict(slip=0.3, comm=0.2, delay=1, trail_worst=1))
    EXTRA_MIN_RISK = None
else:
    SPREAD0 = 0.15                              # VT Markets: 1.5 pips
    COSTS = (dict(slip=0.0, comm=0.60, delay=0, trail_worst=0), dict(slip=0.10, comm=0.67, delay=1, trail_worst=1))
    EXTRA_MIN_RISK = [4.0, 6.0]
GOLD_EXTRA_MIN_RISK = [4.0, 6.0]
# protocol 2 (EURUSD, US500)
DUK_NAME = {"EURUSD": "EURUSD", "US500": "USA500IDXUSD"}           # Dukascopy instrument
DUK_DIVISOR = {"EURUSD": 1e5, "US500": 1e3}                         # price unit of its bi5 integers
ANCHOR_END = pd.Timestamp("2026-01-01")         # the anchor and k are measured on the 180 days that end on 2025-12-31
GOLD_M1 = os.environ.get("HUMP_GOLD_M1", "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad/wf/gold2/m1.pkl")
# The EA's Friday close (WeekendCloseTime, server time, minutes): gold and EURUSD 23:00; US500 15 minutes before its
# usual Friday close (build reports the close it finds and stops if this window would not start before it).
WEEKEND_MIN = {"US500": None}.get(SYM, 1380)
SEED_OFFSET = {"BTCUSD": 1000, "EURUSD": 2000, "US500": 3000}.get(SYM, 0)    # random controls: one stream per symbol
HTF_UP = {"M1": ("M5", "M15"), "M2": ("M10", "M30"), "M3": ("M15", "H1"), "M5": ("M15", "H1"), "M10": ("M30", "H1"),
          "M15": ("H1", "H4"), "M30": ("H1", "H4"), "H1": ("H4", "D1")}
# Years in which Dukascopy's gold had its own daily break on some days. The clock is still right: the other days
# reopen at 01:00 server time and the 08:30 New York data spike sits at 15:30, the stock open at 16:30.
GOLD_BREAK_EXCEPTIONS = {2014: "Dukascopy's daily break ran from 00:15 to 02:00 server time on 25 days in March and April 2014 "
                               "(87% of the year's reopens at 01:00-01:15 instead of 90%); the activity marks are where they belong"}
NICE = np.array([1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000], float)
# protocol 2: the same grid extended downward (EURUSD's 0.5% of a day's close is about 0.005). For a price above 200
# the choice is the same as with NICE (the new steps are all below 1), so gold and BTC would not change either.
NICE2 = np.r_[[0.0001, 0.0002, 0.00025, 0.0005, 0.001, 0.002, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5], NICE]


# ----------------------------------------------------------------------------- data
def read_binance(dirs):
    """Binance spot kline zips -> M1 bars with volume, indexed by UTC (ms stamps until 2024, microseconds from 2025)."""
    parts = []
    for d in dirs:
        for z in sorted(glob.glob(os.path.join(d, "BTCUSDT-1m-*.zip"))):
            with zipfile.ZipFile(z) as f:
                raw = pd.read_csv(io.BytesIO(f.read(f.namelist()[0])), header=None)
            if isinstance(raw.iloc[0, 0], str):                     # a few files carry a header row
                raw = raw.iloc[1:]
            t = raw[0].astype("int64")
            parts.append(pd.DataFrame(dict(open=raw[1].values, high=raw[2].values, low=raw[3].values, close=raw[4].values,
                                           vol=raw[5].values), index=pd.to_datetime(t.values, unit="us" if t.iloc[0] > 1e14 else "ms")))
    m = pd.concat(parts).astype(float)
    return m[~m.index.duplicated()].sort_index()


def build(work, src):
    if NEW:
        return build2(work, src)
    os.makedirs(work, exist_ok=True)
    notes = []

    def check(part, label, fatal=True, min_reopen=0.9, jump_fatal=True):
        try:
            R.clock_check(part, label, min_reopen=min_reopen, jump_fatal=jump_fatal)
        except SystemExit as err:
            if fatal:
                raise
            notes.append(f"activity mark not found: {err}"); print("NOTE", err, flush=True)

    if BTC:
        raw = read_binance(src.split(","))
        m1 = raw.copy(); m1.index = R.utc_to_server(raw.index)
        # the conversion itself, year by year: server time is UTC + 2 h in the US winter and UTC + 3 h in the US summer,
        # changing on the second Sunday of March and the first Sunday of November (07:00 UTC)
        off = ((m1.index.values - raw.index.values) / np.timedelta64(1, "h")).astype(int)
        for y in sorted(set(raw.index.year)):
            mar = pd.Timestamp(year=y, month=3, day=8); mar += pd.Timedelta(days=(6 - mar.dayofweek) % 7, hours=7)
            nov = pd.Timestamp(year=y, month=11, day=1); nov += pd.Timedelta(days=(6 - nov.dayofweek) % 7, hours=6)
            yr = raw.index.year == y
            summer = (raw.index >= mar) & (raw.index < nov)
            assert (off[yr & summer] == 3).all() and (off[yr & ~summer] == 2).all(), f"{y}: UTC to server offsets are not 3 h in the US summer and 2 h in winter"
        m1 = m1[~m1.index.duplicated()].sort_index()
        notes.append(f"Binance UTC {raw.index[0]} .. {raw.index[-1]}; server = UTC + 2 h (US winter) / + 3 h (US summer) verified for every year")
    else:
        import duk_to_m1 as D
        old = [d for d in src.split(",") if d]                       # Dukascopy folders, oldest first; the last is the 2026 one
        f, _ = B.load(H.DATA)                                         # FTMO 2025 - May 2026 (server time), with tick volume
        f = f.rename(columns={"volume": "vol"})[["open", "high", "low", "close", "vol"]]
        parts = []
        for d in old[:-1]:
            a, _ = D.load(d)
            parts.append(a[a.index < f.index[0]])
            check(a, f"Dukascopy {os.path.basename(d)}")
        last, _ = D.load(old[-1])
        check(f, "FTMO")
        m1 = pd.concat(parts + [f, last[last.index > f.index[-1]]])
        assert m1.index.is_monotonic_increasing and not m1.index.duplicated().any()
        notes.append(f"Dukascopy to {parts[-1].index[-1]}, FTMO {f.index[0]} .. {f.index[-1]}, Dukascopy after")
    m1 = m1[["open", "high", "low", "close", "vol"]].astype(float)
    # gold reopens at 01:00 server time every day, in every year: fatal. BTC has no daily break; its only mark is the
    # US stock open, which it did not follow in its early years: fatal on 2023 and later, a note before
    check(m1[m1.index >= "2023-01-01"] if BTC else m1, f"{SYM} whole series")
    for y in sorted(set(m1.index.year)):                                # every year on its own
        part = m1[m1.index.year == y]
        if len(part) > 100000:
            if BTC:
                check(part, f"{SYM} {y}", fatal=False)
            else:                                                       # gold: the daily reopen at 01:00 decides
                if y in GOLD_BREAK_EXCEPTIONS:                          # a known break schedule of the data provider
                    notes.append(f"{y}: {GOLD_BREAK_EXCEPTIONS[y]}")
                check(part, f"{SYM} {y}", fatal=True, min_reopen=0.85 if y in GOLD_BREAK_EXCEPTIONS else 0.9, jump_fatal=False)
    gaps = pd.Series(m1.index).diff().dt.total_seconds().div(60)
    big = [(str(m1.index[i - 1]), str(m1.index[i]), int(g)) for i, g in gaps.items() if g > (60 * 24 * 4 if not BTC else 180)]
    anchor = float(m1["close"][m1.index >= m1.index[-1] - pd.Timedelta(days=ANCHOR_DAYS)].mean())
    m1.to_pickle(os.path.join(work, "m1.pkl"))
    meta = dict(symbol=SYM, first=str(m1.index[0]), last=str(m1.index[-1]), bars=int(len(m1)), anchor_price=anchor,
                bars_per_year={int(y): int(n) for y, n in m1.groupby(m1.index.year).size().items()}, long_gaps=big, notes=notes)
    json.dump(meta, open(os.path.join(work, "meta.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1)[:3000])


class Mk(H.Market):
    """hump_engine.Market on the long series, with the price scale and the scaled spread."""

    def __init__(self, work):
        m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))
        self.meta = json.load(open(os.path.join(work, "meta.json")))
        self.p0 = self.meta["anchor_price"]
        ps = m1["open"].values.astype(float) / self.p0                 # known at each bar's open
        if BTC:
            spread = np.full(len(m1), SPREAD0)
        else:
            _, hourly = B.load(H.DATA)                                 # FTMO spread by UTC hour: used as the shape of the day
            spread = SPREAD0 * (hourly / np.median(hourly))[B.server_to_utc_hour(m1.index)]
        super().__init__(m1=m1[["open", "high", "low", "close"]], half_spread=0.5 * spread * ps)
        self.ps = ps
        self.vol = m1["vol"]
        y = m1.index.year.values
        self.y0 = int(y.min()); self.years = list(range(self.y0, int(y.max()) + 1))
        self.year = (y - self.y0).astype(np.int64)
        # The EA closes from Friday 23:00 server time and, when that moment passed while the market was closed (an
        # early Friday close), on the first tick after it. It cannot know a mid-week holiday closure in advance, so a
        # trade stays open over it. (hump_engine uses the last bar before any closure of a day or more: look-ahead.)
        self.wk_gold = (self.dow == 4) & (self.tod >= 1380)
        tmin = self.t.astype("datetime64[m]").astype(np.int64)
        day = tmin // 1440; dw = (day + 3) % 7                       # 1970-01-01 was a Thursday: Monday = 0
        fri = (day - ((dw - 4) % 7)) * 1440 + 1380                    # the latest Friday 23:00 at or before each bar
        fri = np.where(tmin >= fri, fri, fri - 7 * 1440)
        prev = np.r_[-10 ** 12, tmin[:-1]]
        self.wko_gold = (prev < fri) & (tmin > fri) & ~self.wk_gold    # first bar after a Friday 23:00 that had no bar
        self.wko_gold[0] = False                                       # (the first bar of the data has no bar before it)
        self.after_break = (tmin - prev) >= 30
        self.wk_none = np.zeros(len(self.t), np.bool_)
        self._feat = {}

    def feat(self, name):
        if name not in self._feat:
            self.tf(name)
            self._feat[name] = Feat(self, name)
        return self._feat[name]


# ----------------------------------------------------------------------------- engine without the one-position rule
@nb.njit(cache=True)
def outcomes(sig, entry_row, o, h, l, c, hs, tod, s0, s1, buf, anticip, min_rr, tp_mode, tp_rr,
             trail_start, trail_dist, min_risk, max_risk, slip, comm, delay, trail_worst, wk, max_hold, eod, ps,
             wko, after_break, rr_tol):
    """hump_engine.simulate (hump stop, target at the previous hump or a multiple of the risk, the EA's own
    trailing) for EVERY signal on its own: no one-position rule and no spread limit. buf, min_risk, max_risk, slip
    and comm are multiplied by ps at the entry bar. Rows: signal index, entry row, exit row, side, R, risk,
    round-trip cost (spread + commission) in R.
    wk: no entry on these bars, and an open trade is closed at their close (the EA's Friday window).
    wko: an open trade is closed at the open of these bars (the EA's catch-up when the Friday close was missed).
    after_break: no entry on these bars (the first bar after a break of 30 minutes or more).
    rr_tol: relative tolerance of the reward test (a reward equal to min_rr x risk is accepted)."""
    n = len(o)
    out = np.empty((len(sig), 7))
    m = 0
    for k in range(len(sig)):
        e = entry_row[k]
        if e >= 0:
            e += delay
        if e < 0 or e >= n:
            continue
        if not (s0 <= tod[e] < s1) if s0 < s1 else not (tod[e] >= s0 or tod[e] < s1):
            continue
        if wk[e] or after_break[e]:
            continue
        sc = ps[e]
        bufk = buf * sc; slipk = slip * sc; commk = comm * sc
        side = int(sig[k, 1])
        if side < 0:
            entry = o[e] - hs[e] - slipk
            sl = sig[k, 2] + bufk + hs[e]
            risk = sl - entry
            if not (risk == risk):
                continue
            if risk < min_risk * sc or risk > max_risk * sc:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref + anticip * (entry - ref) + hs[e]
            else:
                tp = entry - tp_rr * risk
            if entry - tp < min_rr * risk * (1.0 - rr_tol):
                continue
            stop = sl; px = np.nan; j = e
            while j < n:
                ah = h[j] + hs[j]; al = l[j] + hs[j]; ao = o[j] + hs[j]
                if wko[j] and j > e:
                    px = ao + slipk; break
                if ao >= stop:
                    px = ao + slipk; break
                if ah >= stop:
                    px = stop + slipk; break
                if al <= tp:
                    px = min(tp, ao); break
                if trail_start > 0 and entry - al >= trail_start * risk:
                    cand = al + trail_dist * risk
                    if cand < stop:
                        stop = cand
                        if c[j] + hs[j] >= stop or (trail_worst == 1 and ah >= stop):
                            px = stop + slipk; break
                if wk[j]:
                    px = c[j] + hs[j] + slipk; break
                if (max_hold > 0 and j - e >= max_hold) or \
                        (eod >= 0 and j > e and tod[j] >= eod and (tod[j - 1] < eod or tod[j - 1] > tod[j])):
                    px = c[j] + hs[j] + slipk; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] + hs[j]
            r = (entry - px - commk) / risk
        else:
            entry = o[e] + hs[e] + slipk
            sl = sig[k, 2] - bufk - hs[e]
            risk = entry - sl
            if not (risk == risk):
                continue
            if risk < min_risk * sc or risk > max_risk * sc:
                continue
            if tp_mode == 0:
                ref = sig[k, 3]
                tp = ref - anticip * (ref - entry) - hs[e]
            else:
                tp = entry + tp_rr * risk
            if tp - entry < min_rr * risk * (1.0 - rr_tol):
                continue
            stop = sl; px = np.nan; j = e
            while j < n:
                bh = h[j] - hs[j]; bl = l[j] - hs[j]; bo = o[j] - hs[j]
                if wko[j] and j > e:
                    px = bo - slipk; break
                if bo <= stop:
                    px = bo - slipk; break
                if bl <= stop:
                    px = stop - slipk; break
                if bh >= tp:
                    px = max(tp, bo); break
                if trail_start > 0 and bh - entry >= trail_start * risk:
                    cand = bh - trail_dist * risk
                    if cand > stop:
                        stop = cand
                        if c[j] - hs[j] <= stop or (trail_worst == 1 and bl <= stop):
                            px = stop - slipk; break
                if wk[j]:
                    px = c[j] - hs[j] - slipk; break
                if (max_hold > 0 and j - e >= max_hold) or \
                        (eod >= 0 and j > e and tod[j] >= eod and (tod[j - 1] < eod or tod[j - 1] > tod[j])):
                    px = c[j] - hs[j] - slipk; break
                j += 1
            if px != px:
                j = n - 1; px = c[j] - hs[j]
            r = (px - entry - commk) / risk
        out[m, 0] = k; out[m, 1] = e; out[m, 2] = j; out[m, 3] = side; out[m, 4] = r; out[m, 5] = risk
        out[m, 6] = (2.0 * hs[e] + commk) / risk
        m += 1
    return out[:m]


@nb.njit(cache=True)
def take(e, j, keep):
    """One position at a time: indices of the outcomes that are taken when only those with keep are allowed."""
    out = np.empty(len(e), np.int64)
    m = 0; busy = -1
    for i in range(len(e)):
        if not keep[i] or e[i] <= busy:
            continue
        out[m] = i; m += 1; busy = j[i]
    return out[:m]


@nb.njit(cache=True)
def aggregate(masks, kidx, e, j, r, costr, yr, ny):
    """For every condition (row of masks, over the signals): the trades taken under the one-position rule, summed
    per entry year: count, gross profit in R, gross loss in R, cost in R."""
    nv = masks.shape[0]
    out = np.zeros((nv, ny, 4))
    for v in range(nv):
        busy = -1
        for i in range(len(e)):
            if not masks[v, kidx[i]] or e[i] <= busy:
                continue
            busy = j[i]
            y = yr[e[i]]
            out[v, y, 0] += 1.0
            if r[i] > 0:
                out[v, y, 1] += r[i]
            else:
                out[v, y, 2] -= r[i]
            out[v, y, 3] += costr[i]
    return out


# ----------------------------------------------------------------------------- features of the signal bar
def adx(df, n=14):
    up = df["high"].diff(); dn = -df["low"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


@nb.njit(cache=True)
def sweep_flags(hi, lo, cl, sh, sl, N, S):
    """XLZC liquidity sweep seen from signal bar i (entry bar i + 1): within the last N bars a bar went through an
    older confirmed swing high and closed back below it (dn, for sells); mirrored for buys (up)."""
    n = len(hi)
    dn = np.zeros(n, np.bool_); up = np.zeros(n, np.bool_)
    for i in range(n):
        e = i + 1
        if e - N - S < 0:
            continue
        fd = False; fu = False
        for j in range(1, N + 1):
            aj = e - j
            for k in range(j + S + 1, N + 1):
                ai = e - k
                if (not fd) and sh[ai] and hi[aj] > hi[ai] and cl[aj] < hi[ai]:
                    fd = True
                if (not fu) and sl[ai] and lo[aj] < lo[ai] and cl[aj] > lo[ai]:
                    fu = True
            if fd and fu:
                break
        dn[i] = fd; up[i] = fu
    return dn, up


class Feat:
    """What is known at the close of each trigger bar (the signal bar), for the entry conditions. Every value
    uses only bars that have closed by then: higher-timeframe values come from the last CLOSED higher bar, daily
    values from the days before, and running values of the day from the bars up to this one."""

    def __init__(self, mk, name):
        d = mk._tf[name]; t = d["t"]; tfm = B.TF_MIN[name]
        idx = t.index; tclose = idx + pd.Timedelta(minutes=tfm)
        o = t["open"].values.astype(float); h = d["hi"]; l = d["lo"]; c = t["close"].values.astype(float)
        m1 = mk.m1

        def asof(s, htf):                                  # a value of a higher-timeframe bar, known from that bar's close
            s = s.copy(); s.index = s.index + pd.Timedelta(minutes=B.TF_MIN[htf])
            return s.reindex(tclose, method="ffill").values

        for htf, key in (("H4", "h4"), ("D1", "d1")):
            hb = B.resample(m1, htf)
            n_ema, lag = (50, 5) if htf == "H4" else (20, 3)
            e50 = B.ema(hb["close"], 50); e50.iloc[:50] = np.nan
            es = B.ema(hb["close"], n_ema); es.iloc[:n_ema] = np.nan
            setattr(self, "tr_" + key, np.nan_to_num(asof(np.sign(hb["close"] - e50), htf)).astype(np.int8))
            setattr(self, "sl_" + key, np.nan_to_num(asof(np.sign(es - es.shift(lag)), htf)).astype(np.int8))
        self.adx_h1 = asof(adx(B.resample(m1, "H1")), "H1")
        self.adx_h4 = asof(adx(B.resample(m1, "H4")), "H4")
        w = int(20 * 1440 / tfm)
        self.atrp = pd.Series(d["atr"]).rolling(w, min_periods=w // 2).rank(pct=True).values

        # days (server calendar days), from the one-minute bars
        day = m1.index.normalize(); tod = mk.tod
        g = m1.groupby(day)
        dhi, dlo, dop, dcl = g["high"].max(), g["low"].min(), g["open"].first(), g["close"].last()
        rng = dhi - dlo
        adr = rng.rolling(20).mean().shift(1)              # the 20 days before the day
        bar_day = idx.normalize()
        pick = lambda s: s.reindex(bar_day).values
        pdh, pdl, pdc = pick(dhi.shift(1)), pick(dlo.shift(1)), pick(dcl.shift(1))
        adr_b = pick(adr)
        self.pdr = pick(rng.shift(1) / adr.shift(1))
        hi_s = pd.Series(h, index=idx); lo_s = pd.Series(l, index=idx)
        self.tdr = (hi_s.groupby(bar_day).cummax().values - lo_s.groupby(bar_day).cummin().values) / adr_b
        with np.errstate(divide="ignore", invalid="ignore"):
            self.pdpos = (c - pdl) / (pdh - pdl)
        self.dopen = np.sign(c - pick(dop)).astype(np.int8)
        open_tod = (idx.hour * 60 + idx.minute).values
        for key, a, b in (("asia", 60, 540), ("nyor", 990, 1050)):     # ranges 01:00-09:00 and 16:30-17:30 server time
            sel = (tod >= a) & (tod < b)
            gg = m1[sel].groupby(day[sel])
            rh, rl = pick(gg["high"].max()), pick(gg["low"].min())
            ok = (open_tod >= a) & (open_tod + tfm >= b)              # the bar closes at or after the end of the range
            with np.errstate(divide="ignore", invalid="ignore"):
                setattr(self, key + "_pos", np.where(ok, (c - rl) / (rh - rl), np.nan))
        grid = NICE[np.abs(np.log(NICE)[None, :] - np.log(np.where(pdc > 0, 0.005 * pdc, 1.0))[:, None]).argmin(axis=1)]
        self.rn = np.where(pdc > 0, np.abs(c - np.round(c / grid) * grid) / (grid / 2.0), np.nan)
        ph, pl = T2.pivot_levels(h, l, 3)                  # last confirmed swing high / low, known 3 bars after it
        self.bos_up = c > ph; self.bos_dn = c < pl

        # confirmation
        for k, htf in enumerate(HTF_UP[name]):
            hb = B.resample(m1, htf)
            mac = B.ema(hb["close"], 12) - B.ema(hb["close"], 26); mac.iloc[:60] = np.nan
            setattr(self, f"hm{k + 1}", np.nan_to_num(asof(np.sign(mac), htf)).astype(np.int8))
        vol = mk.vol if name == "M1" else mk.vol.resample(f"{tfm}min", label="left", closed="left").sum()
        vol = vol.reindex(idx)
        self.volr = (vol / vol.rolling(20).mean().shift(1)).values
        self.body_dir = np.sign(c - o).astype(np.int8)
        with np.errstate(divide="ignore", invalid="ignore"):
            self.body_frac = np.where(h > l, np.abs(c - o) / (h - l), np.nan)
            self.rng_atr = (h - l) / d["atr"]

        # XLZC rules on the trigger bars: Stochastic (7, 1, 7) from the extreme, and a liquidity sweep (30 bars, swing 2)
        sm, ss = B.stoch(t, 7, 1, 7)
        hi5 = sm.rolling(5).max().values; lo5 = sm.rolling(5).min().values
        sm = sm.values; ss = ss.values
        self.xs_dn = (hi5 >= 80) & ((sm < ss) | (sm < 80))
        self.xs_up = (lo5 <= 20) & ((sm > ss) | (sm > 20))
        sh, sl = B.swing_flags(h, l, 2)
        self.sw_dn, self.sw_up = sweep_flags(h, l, c, sh, sl, 30, 2)

        self.rnd = np.random.default_rng(B.TF_MIN[name] + (1000 if BTC else 0)).random((3, len(idx)))   # controls


def conditions():
    """(key, group, plain description, function(F, i, s, te, de) -> keep) for signal bars i, sides s (+1 buy, -1 sell),
    entry minute of the day te and entry weekday de (server time, Monday = 0)."""
    C = []

    def add(key, group, text, fn):
        C.append((key, group, text, fn))

    adv = lambda F, i, s: np.where(s < 0, F.pdpos[i], 1.0 - F.pdpos[i])           # 1 = at the far (adverse) end of yesterday's range
    aadv = lambda F, i, s: np.where(s < 0, F.asia_pos[i], 1.0 - F.asia_pos[i])
    nadv = lambda F, i, s: np.where(s < 0, F.nyor_pos[i], 1.0 - F.nyor_pos[i])
    add("base", "base", "no extra condition", lambda F, i, s, te, de: np.ones(len(i), np.bool_))
    # market regime
    add("trend_h4", "regime", "with the H4 trend (H4 close on the trade's side of its EMA 50)", lambda F, i, s, te, de: F.tr_h4[i] == s)
    add("trend_d1", "regime", "with the daily trend (D1 close on the trade's side of its EMA 50)", lambda F, i, s, te, de: F.tr_d1[i] == s)
    add("slope_h4", "regime", "H4 EMA 50 sloping with the trade", lambda F, i, s, te, de: F.sl_h4[i] == s)
    add("slope_d1", "regime", "D1 EMA 20 sloping with the trade", lambda F, i, s, te, de: F.sl_d1[i] == s)
    add("adx_h1_20", "regime", "trend strength: ADX(14) of H1 at least 20", lambda F, i, s, te, de: F.adx_h1[i] >= 20)
    add("adx_h1_30", "regime", "trend strength: ADX(14) of H1 at least 30", lambda F, i, s, te, de: F.adx_h1[i] >= 30)
    add("adx_h4_20", "regime", "trend strength: ADX(14) of H4 at least 20", lambda F, i, s, te, de: F.adx_h4[i] >= 20)
    add("adx_h4_30", "regime", "trend strength: ADX(14) of H4 at least 30", lambda F, i, s, te, de: F.adx_h4[i] >= 30)
    add("adx_h1_lt20", "regime", "quiet market: ADX(14) of H1 under 20", lambda F, i, s, te, de: F.adx_h1[i] < 20)
    add("atrp_ge50", "regime", "volatility in its upper half (ATR percentile of 20 days at least 50)", lambda F, i, s, te, de: F.atrp[i] >= 0.5)
    add("atrp_ge70", "regime", "volatility high (ATR percentile at least 70)", lambda F, i, s, te, de: F.atrp[i] >= 0.7)
    add("atrp_le50", "regime", "volatility in its lower half (ATR percentile at most 50)", lambda F, i, s, te, de: F.atrp[i] <= 0.5)
    add("atrp_30_70", "regime", "volatility in the middle (ATR percentile 30 to 70)", lambda F, i, s, te, de: (F.atrp[i] >= 0.3) & (F.atrp[i] <= 0.7))
    add("pdr_ge80", "regime", "no flat day before: previous day's range at least 80% of the 20-day average", lambda F, i, s, te, de: F.pdr[i] >= 0.8)
    add("pdr_ge120", "regime", "wide day before: previous day's range at least 120% of the average", lambda F, i, s, te, de: F.pdr[i] >= 1.2)
    add("tdr_ge40", "regime", "the day is moving: today's range so far at least 40% of the average day", lambda F, i, s, te, de: F.tdr[i] >= 0.4)
    add("tdr_ge70", "regime", "the day is moving: today's range so far at least 70% of the average day", lambda F, i, s, te, de: F.tdr[i] >= 0.7)
    # location
    add("pd_premium", "location", "sell in the upper half, buy in the lower half of the previous day's range", lambda F, i, s, te, de: adv(F, i, s) >= 0.5)
    add("pd_momentum", "location", "sell in the lower half, buy in the upper half of the previous day's range", lambda F, i, s, te, de: adv(F, i, s) <= 0.5)
    add("pd_break", "location", "sell below the previous day's low, buy above its high", lambda F, i, s, te, de: adv(F, i, s) < 0)
    add("pd_inside", "location", "inside the previous day's range", lambda F, i, s, te, de: (F.pdpos[i] >= 0) & (F.pdpos[i] <= 1))
    add("asia_break", "location", "beyond the 01:00-09:00 range in the trade's direction", lambda F, i, s, te, de: aadv(F, i, s) < 0)
    add("asia_inside", "location", "inside the 01:00-09:00 range", lambda F, i, s, te, de: (F.asia_pos[i] >= 0) & (F.asia_pos[i] <= 1))
    add("nyor_break", "location", "beyond the 16:30-17:30 opening range in the trade's direction", lambda F, i, s, te, de: nadv(F, i, s) < 0)
    add("nyor_inside", "location", "inside the 16:30-17:30 opening range", lambda F, i, s, te, de: (F.nyor_pos[i] >= 0) & (F.nyor_pos[i] <= 1))
    add("day_with", "location", "price on the trade's side of the day's open", lambda F, i, s, te, de: F.dopen[i] == s)
    add("day_against", "location", "price on the other side of the day's open", lambda F, i, s, te, de: F.dopen[i] == -s)
    add("round_near", "location", "close to a round number (within 30% of the way)", lambda F, i, s, te, de: F.rn[i] <= 0.3)
    add("round_far", "location", "away from round numbers (at least half way)", lambda F, i, s, te, de: F.rn[i] >= 0.5)
    add("bos", "location", "last swing already broken in the trade's direction", lambda F, i, s, te, de: np.where(s < 0, F.bos_dn[i], F.bos_up[i]))
    add("no_bos", "location", "last swing not yet broken", lambda F, i, s, te, de: ~np.where(s < 0, F.bos_dn[i], F.bos_up[i]))
    # confirmation
    add("htf_macd_1", "confirmation", "MACD of the next timeframe up on the trade's side (same hump there)", lambda F, i, s, te, de: F.hm1[i] == s)
    add("htf_macd_2", "confirmation", "MACD two timeframes up on the trade's side", lambda F, i, s, te, de: F.hm2[i] == s)
    add("htf_macd_both", "confirmation", "MACD of both higher timeframes on the trade's side", lambda F, i, s, te, de: (F.hm1[i] == s) & (F.hm2[i] == s))
    add("vol_ge150", "confirmation", "tick volume of the signal bar at least 1.5 times its 20-bar average", lambda F, i, s, te, de: F.volr[i] >= 1.5)
    add("vol_ge200", "confirmation", "tick volume of the signal bar at least twice its average", lambda F, i, s, te, de: F.volr[i] >= 2.0)
    add("vol_le100", "confirmation", "tick volume of the signal bar at or below its average", lambda F, i, s, te, de: F.volr[i] <= 1.0)
    add("candle_with", "confirmation", "signal candle closes in the trade's direction", lambda F, i, s, te, de: F.body_dir[i] == s)
    add("candle_against", "confirmation", "signal candle closes against the trade", lambda F, i, s, te, de: F.body_dir[i] == -s)
    add("candle_body50", "confirmation", "signal candle body at least half its range", lambda F, i, s, te, de: F.body_frac[i] >= 0.5)
    add("candle_big", "confirmation", "signal candle range at least 1 ATR", lambda F, i, s, te, de: F.rng_atr[i] >= 1.0)
    add("candle_small", "confirmation", "signal candle range under 1 ATR", lambda F, i, s, te, de: F.rng_atr[i] < 1.0)
    # timing (entry time, server clock)
    for a, b in ((7, 10), (10, 13), (13, 16), (16, 19), (19, 22)):
        add(f"hours_{a}_{b}", "timing", f"entries from {a:02d}:00 to {b:02d}:00 only", lambda F, i, s, te, de, a=a, b=b: (te >= a * 60) & (te < b * 60))
    add("not_us_open", "timing", "no entries from 15:00 to 17:30", lambda F, i, s, te, de: ~((te >= 900) & (te < 1050)))
    add("no_monday", "timing", "no entries on Monday", lambda F, i, s, te, de: de != 0)
    add("no_friday", "timing", "no entries on Friday", lambda F, i, s, te, de: de != 4)
    add("tue_thu", "timing", "entries from Tuesday to Thursday only", lambda F, i, s, te, de: (de >= 1) & (de <= 3))
    add("no_news_times", "timing", "no entries within 30 minutes of 15:30 or 17:00 (the usual US release times)",
        lambda F, i, s, te, de: ~((np.abs(te - 930) <= 30) | (np.abs(te - 1020) <= 30)))
    # the XLZC signal's own rules, mirrored for buys
    add("xlzc_stoch", "xlzc", "XLZC Stochastic rule: came from 80 / 20 within 5 bars and turned", lambda F, i, s, te, de: np.where(s < 0, F.xs_dn[i], F.xs_up[i]))
    add("xlzc_sweep", "xlzc", "XLZC liquidity sweep in the last 30 bars", lambda F, i, s, te, de: np.where(s < 0, F.sw_dn[i], F.sw_up[i]))
    add("xlzc_both", "xlzc", "XLZC Stochastic rule and liquidity sweep", lambda F, i, s, te, de: np.where(s < 0, F.xs_dn[i] & F.sw_dn[i], F.xs_up[i] & F.sw_up[i]))
    # controls: a random half of the signals (what chance alone does to the test)
    for k, nm in enumerate("abc"):
        add(f"random_{nm}", "control", "control: a random half of the signals", lambda F, i, s, te, de, k=k: F.rnd[k][i] < 0.5)
    return C


CONDS = conditions()
KEYS = [c[0] for c in CONDS]


# ----------------------------------------------------------------------------- candidates and the per-setup run
def space():
    sp = dict(X.SPACE)
    sp["min_risk"] = list(sp["min_risk"]) + EXTRA_MIN_RISK
    return sp


def candidates(tf, n):
    rng = random.Random(f"{SYM}-{tf}-wf-2026-11")
    sp = space()
    keys = [k for k in sp if k not in ("tf", "htf")]
    seen, out = set(), []
    hl = R.valid_htfs(tf)
    while len(out) < n:
        p = {k: rng.choice(sp[k]) for k in keys}
        p["tf"] = tf; p["htf"] = rng.choice(hl)
        key = json.dumps(p, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(p)
    return out


MK = None


def prepare(p):
    """Signals of a setup (after its own trend filter) and what the engine needs to run them."""
    c = dict(H.DEFAULT); c.update(X.engine_cfg(dict(X.BASE, **p)))
    fast, slow = int(c["macd_fast"]), int(c["macd_slow"])
    hi, lo, macd, stk, row, bias, atr = MK.tf(c["tf"], fast, slow, int(c["stoch_k"]))
    sg = H.signals(hi, lo, macd, stk, c["big_mult"], int(c["hist"]), int(c["big_min_bars"]), int(c["stoch_req"]),
                   int(c["pb_min_bars"]), c["pb_max_ratio"], c["break_ratio"], int(c["max_signals"]),
                   int(c["trend_max_bars"]), int(c["sides"]), int(c["classic"]), int(c["skip_big_pb"]),
                   c["stoch_lo"], c["stoch_hi"])
    if c.get("htf", "none") != "none" and len(sg):
        sg = sg[bias[(c["htf"], int(c["htf_ema"]))][sg[:, 0].astype(np.int64)] == sg[:, 1]]
    ix = sg[:, 0].astype(np.int64) if len(sg) else np.zeros(0, np.int64)
    sg = np.column_stack([sg, atr[ix]]) if len(sg) else np.zeros((0, 6))
    return c, sg, ix, row[ix]


def run_outcomes(c, sg, er, cost, parity=False):
    """parity=True: the rules of hump_engine.simulate (weekend array with closures known in advance, no break rule,
    strict reward test), for the parity self-test only."""
    s0, s1 = H.SESSIONS[c["session"]]
    if parity:
        wk = (((MK.dow == 4) & (MK.tod >= 1380)) | MK.pre_gap) if c["weekend_close"] else MK.wk_none
        wko = MK.wk_none; brk = MK.wk_none; tol = 0.0
    else:
        wk = MK.wk_gold if c["weekend_close"] else MK.wk_none
        wko = MK.wko_gold if c["weekend_close"] else MK.wk_none
        brk = MK.after_break; tol = 1e-9
    return outcomes(sg, er, MK.o, MK.h, MK.l, MK.c, MK.hs, MK.tod, s0, s1, float(c["buf"]), float(c["anticip"]), float(c["min_rr"]),
                    int(c["tp_mode"]), float(c["tp_rr"]), float(c["trail_start"]), float(c["trail_dist"]), float(c["min_risk"]),
                    float(c["max_risk"]), float(cost["slip"]), float(cost["comm"]), int(cost["delay"]), int(cost["trail_worst"]),
                    wk, int(c["max_hold"]), int(c["eod"]), MK.ps, wko, brk, tol)


def masks_of(tf, ix, s, er):
    F = MK.feat(tf)
    ok = er >= 0
    te = np.where(ok, MK.tod[np.clip(er, 0, None)], -10000); de = np.where(ok, MK.dow[np.clip(er, 0, None)], -1)
    M = np.empty((len(CONDS), len(ix)), np.bool_)
    for v, (_, _, _, fn) in enumerate(CONDS):
        M[v] = fn(F, ix, s, te, de)
    return M


def one(p):
    """Per condition, cost level and entry year: trades, gross profit, gross loss, cost (all in R)."""
    c, sg, ix, er = prepare(p)
    ny = len(MK.years)
    res = np.zeros((len(CONDS), 2, ny, 4), np.float32)
    if not len(sg):
        return res
    M = masks_of(c["tf"], ix, sg[:, 1].astype(np.int8), er)
    for ci, cost in enumerate(COSTS):
        out = run_outcomes(c, sg, er, cost)
        if len(out):
            res[:, ci] = aggregate(M, out[:, 0].astype(np.int64), out[:, 1].astype(np.int64), out[:, 2].astype(np.int64),
                                   out[:, 4], out[:, 6], MK.year, ny)
    return res


def trades_of(p, key, cost):
    """The trades of one setup under one condition (for the detail of a result): DataFrame entry_time, side, r, risk, cost_r."""
    c, sg, ix, er = prepare(p)
    if not len(sg):
        return pd.DataFrame(columns=["entry_time", "side", "r", "risk", "cost_r"])
    M = masks_of(c["tf"], ix, sg[:, 1].astype(np.int8), er)[KEYS.index(key)]
    out = run_outcomes(c, sg, er, cost)
    idx = take(out[:, 1].astype(np.int64), out[:, 2].astype(np.int64), M[out[:, 0].astype(np.int64)])
    o = out[idx]
    return pd.DataFrame(dict(entry_time=MK.t[o[:, 1].astype(np.int64)], side=o[:, 3].astype(int), r=o[:, 4], risk=o[:, 5], cost_r=o[:, 6],
                             exit_row=o[:, 2].astype(np.int64), entry_row=o[:, 1].astype(np.int64)))


def run(work, tf, n, workers=3):
    global MK
    t0 = time.time()
    MK = Mk(work)
    MK.feat(tf)                                         # built once here, shared with the workers (fork)
    cand = candidates(tf, n)
    one(cand[0])                                        # compile before the workers start
    print(f"{SYM} {tf}: market and features ready in {time.time() - t0:.0f}s; {len(MK.t)} bars, years {MK.years[0]}-{MK.years[-1]}", flush=True)
    with Pool(workers) as pool:
        res = pool.map(one, cand, chunksize=8)
    A = np.stack(res)
    np.save(os.path.join(work, f"wf_{tf}.npy.tmp.npy"), A)
    os.replace(os.path.join(work, f"wf_{tf}.npy.tmp.npy"), os.path.join(work, f"wf_{tf}.npy"))
    with open(os.path.join(work, f"wf_{tf}_params.pkl"), "wb") as f:
        pickle.dump(dict(tf=tf, params=cand, keys=KEYS, years=MK.years, costs=COSTS, anchor=MK.p0), f, protocol=4)
    print(f"{SYM} {tf}: {n} setups x {len(CONDS)} conditions x 2 cost levels in {time.time() - t0:.0f}s", flush=True)


# ----------------------------------------------------------------------------- year-by-year selection and test
def pf_of(win, loss):
    win = np.asarray(win, float); loss = np.asarray(loss, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(loss > 0, win / loss, np.where(win > 0, np.inf, np.nan))


def window_pick(A, P, v, cal):
    """Picks of condition v on the calibration years cal (indices): the protocol's rule. A: [setups, conditions, cost, year, 4]."""
    n = A[:, v][:, :, cal, 0]; win = A[:, v][:, :, cal, 1]; loss = A[:, v][:, :, cal, 2]       # [N, 2, 3]
    ok = (n >= MIN_N).all(axis=(1, 2))
    score = np.where(ok, pf_of(win, loss).min(axis=(1, 2)), 0.0)
    nb_ = A[:, v][:, 0][:, cal, 0].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cost = np.where(nb_ > 0, A[:, v][:, 0][:, cal, 3].sum(axis=1) / nb_, np.inf)
    score = np.where(cost <= MAX_COST_R, score, 0.0)
    order = np.argsort(-score, kind="stable")
    out, fams = [], set()
    for i in order:
        if not (score[i] >= PASS_PF) or len(out) >= TOPK:
            break
        fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
        if fam in fams:
            continue
        fams.add(fam); out.append(int(i))
    return out, score, cost, int((ok).sum()), int((ok & (cost <= MAX_COST_R)).sum())


def wf_tf(work, tf):
    """Every condition of one timeframe through all windows. The last year of the data is the final check."""
    fn = os.path.join(work, f"wf_{tf}.npy")
    if not os.path.exists(fn):
        return None
    A = np.load(fn).astype(np.float64)
    d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
    P, years = d["params"], d["years"]
    final = len(years) - 1
    tests = list(range(3, len(years)))                   # index of every year that has three years before it
    rows = []
    for v, key in enumerate(d["keys"]):
        yrs = []
        for ty in tests:
            cal = [ty - 3, ty - 2, ty - 1]
            picks, score, cost, n_ok, n_cost = window_pick(A, P, v, cal)
            s = A[picks][:, v][:, :, ty, :].sum(axis=0) if picks else np.zeros((2, 4))
            yrs.append(dict(year=years[ty], picks=picks, eligible=n_ok, eligible_after_cost_rule=n_cost,
                            n=int(s[0, 0]), win=float(s[0, 1]), loss=float(s[0, 2]), cost_r=float(s[0, 3]),
                            stress_n=int(s[1, 0]), stress_win=float(s[1, 1]), stress_loss=float(s[1, 2]),
                            pf=float(pf_of(s[0, 1], s[0, 2])), stress_pf=float(pf_of(s[1, 1], s[1, 2])),
                            scores=[round(float(score[i]), 3) for i in picks]))
        wfy = [y for y in yrs if y["year"] != years[final]]
        n = sum(y["n"] for y in wfy); win = sum(y["win"] for y in wfy); loss = sum(y["loss"] for y in wfy)
        sw = sum(y["stress_win"] for y in wfy); sl = sum(y["stress_loss"] for y in wfy)
        pf = float(pf_of(win, loss)); spf = float(pf_of(sw, sl))
        full = [y for y in wfy if y["n"] >= YEAR_N]
        passes = bool(n >= PASS_N and pf >= PASS_PF and spf >= PASS_STRESS and len(full) >= 2 and all(y["pf"] >= 1.0 for y in full))
        rows.append(dict(symbol=SYM, tf=tf, condition=key, group=CONDS[v][1], text=CONDS[v][2],
                         unseen_years=[y["year"] for y in wfy], n=int(n), pf=pf, stress_pf=spf, net_r=float(win - loss),
                         cost_r_per_trade=(sum(y["cost_r"] for y in wfy) / n if n else None),
                         years_with_50_trades=len(full), losing_years=[y["year"] for y in full if y["pf"] < 1.0],
                         passes=passes, by_year=wfy, final=yrs[-1]))
    return rows


def wf(work, out_json):
    rows = []
    for tf in TFS:
        r = wf_tf(work, tf)
        if r:
            rows += r
    meta = json.load(open(os.path.join(work, "meta.json")))
    json.dump(dict(symbol=SYM, anchor_price=meta["anchor_price"], spread_at_anchor=SPREAD0, costs=list(COSTS), min_n=MIN_N, topk=TOPK,
                   pass_pf=PASS_PF, pass_stress_pf=PASS_STRESS, pass_n=PASS_N, year_n=YEAR_N, max_cost_r=MAX_COST_R,
                   conditions=[dict(key=c[0], group=c[1], text=c[2]) for c in CONDS], rows=rows), open(out_json, "w"), indent=1)
    t = pd.DataFrame([{k: v for k, v in r.items() if k not in ("by_year", "final", "text")} for r in rows])
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    for r in rows:                                       # per-year profit factors (trades) next to the pooled figure
        r["_years"] = "  ".join(f"{y['year']}: {y['pf']:.2f} ({y['n']})" if y["n"] else f"{y['year']}: -" for y in r["by_year"])
    t["by_year"] = [r["_years"] for r in rows]
    print(f"{SYM}: {len(t)} timeframe-and-condition cells; {int(t.passes.sum())} pass the year-by-year test")
    show = t.sort_values(["passes", "pf"], ascending=False)
    print(show[["tf", "condition", "n", "pf", "stress_pf", "cost_r_per_trade", "passes", "by_year"]].head(40).round(2).to_string(index=False))
    print("\nwithout a condition (base):")
    print(t[t.condition == "base"][["tf", "n", "pf", "stress_pf", "cost_r_per_trade", "passes", "by_year"]].round(2).to_string(index=False))
    print("\ncontrols (a random half of the signals):")
    print(t[t.group == "control"][["tf", "condition", "n", "pf", "stress_pf", "passes", "by_year"]].round(2).to_string(index=False))


def unseen_trades(work, tf, key, flat_spread=None):
    """Trade lists behind one cell: for every window the picks of condition `key`, run on their test year.
    Returns a DataFrame (year, pick, entry_time, side, r, risk, cost_r) for base costs and the same for stress.
    flat_spread: the same spread in dollars in every year instead of the price-scaled one (no slippage or commission
    scaling is changed; meant for BTC, whose base cost is the spread alone)."""
    global MK
    if MK is None or getattr(MK, "_work", None) != (work, flat_spread):
        MK = Mk(work); MK._work = (work, flat_spread)
        if flat_spread is not None:
            MK.hs = np.full(len(MK.t), flat_spread / 2.0)
    A = np.load(os.path.join(work, f"wf_{tf}.npy")).astype(np.float64)
    d = pickle.load(open(os.path.join(work, f"wf_{tf}_params.pkl"), "rb"))
    P, years = d["params"], d["years"]; v = d["keys"].index(key)
    out = [[], []]
    for ty in range(3, len(years)):
        picks, score, cost, _, _ = window_pick(A, P, v, [ty - 3, ty - 2, ty - 1])
        for i in picks:
            for ci in (0, 1):
                df = trades_of(P[i], key, COSTS[ci])
                df = df[df.entry_time.dt.year == years[ty]]
                if flat_spread is None:                  # the stored sums must be these trades
                    assert len(df) == A[i, v, ci, ty, 0] and abs(df.r[df.r > 0].sum() - A[i, v, ci, ty, 1]) < 1e-3 * max(1.0, A[i, v, ci, ty, 1]), (tf, key, i, years[ty])
                out[ci].append(df.assign(year=years[ty], pick=i, score=float(score[i])))
    cols = ["year", "pick", "score", "entry_time", "side", "r", "risk", "cost_r", "entry_row", "exit_row"]
    return [pd.concat(x)[cols].sort_values("entry_time").reset_index(drop=True) if x else pd.DataFrame(columns=cols) for x in out], P


def boot(times, r, reps=2000, seed=7):
    """Weekly resampling of a trade list: 5th and 95th percentile of the profit factor, share of resamples under 1.0 and 1.3."""
    wk = times.astype("datetime64[W]").astype(np.int64)
    groups = [r[wk == w] for w in np.unique(wk)]
    rng = np.random.default_rng(seed); out = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        out.append(float(pf_of(*(lambda x: (x[x > 0].sum(), -x[x <= 0].sum()))(np.concatenate([groups[i] for i in pick])))))
    out = np.asarray(out); out = out[np.isfinite(out)]
    return dict(p05=float(np.percentile(out, 5)), p95=float(np.percentile(out, 95)), below_1_0=float((out < 1.0).mean()), below_1_3=float((out < 1.3).mean()))


def describe(r):
    r = np.asarray(r, float)
    if not len(r):
        return dict(n=0)
    eq = np.cumsum(r)
    return dict(n=int(len(r)), pf=float(pf_of(r[r > 0].sum(), -r[r <= 0].sum())), net_r=float(r.sum()), win_rate=float((r > 0).mean()),
                max_drawdown_r=float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()),
                pf_without_3_largest_wins=float(pf_of(np.sort(r[r > 0])[:-3].sum(), -r[r <= 0].sum())) if (r > 0).sum() > 3 else None)


def detail(work, tf, key, out_json):
    """Everything behind one cell, from its trade lists: per year, per side, per pick, months, resampling, and for
    BTC the same picks at a flat spread in dollars."""
    (base, stress), P = unseen_trades(work, tf, key)
    last = int(base.year.max())
    res = dict(symbol=SYM, tf=tf, condition=key, text=CONDS[KEYS.index(key)][2], final_year_number=last)
    for name, df in (("walk_forward", base[base.year < last]), ("final_year", base[base.year == last]), ("all_unseen_years", base)):
        r = df.r.values.astype(float)
        res[name] = dict(describe(r), stress=describe(stress[stress.year.isin(df.year.unique())].r.values),
                         buys=describe(df.r[df.side > 0].values), sells=describe(df.r[df.side < 0].values),
                         cost_r_per_trade=float(df.cost_r.mean()) if len(df) else None,
                         resampling=boot(df.entry_time.values, r) if len(df) > 30 else None,
                         by_year={int(y): describe(g.r.values) for y, g in df.groupby("year")},
                         positive_months=int((df.groupby(df.entry_time.dt.strftime("%Y-%m")).r.sum() > 0).sum()) if len(df) else 0,
                         months=int(df.entry_time.dt.strftime("%Y-%m").nunique()) if len(df) else 0)
    res["picks"] = [dict(year=int(y), pick=int(i), score=round(float(g.score.iloc[0]), 3), **describe(g.r.values),
                         setup={k: P[i][k] for k in ("sides", "session", "htf", "htf_ema", "macd", "tp_mode", "tp_rr", "trail_start", "trail_dist", "max_hold", "eod", "buf", "min_risk")})
                    for (y, i), g in base.groupby(["year", "pick"])]
    if BTC:
        (flat, _), _ = unseen_trades(work, tf, key, flat_spread=SPREAD0)
        res["flat_spread_in_dollars"] = dict(spread=SPREAD0, all_unseen_years=describe(flat.r.values),
                                             by_year={int(y): describe(g.r.values) for y, g in flat.groupby("year")})
    json.dump(res, open(out_json, "w"), indent=1, default=float)
    show = {k: res[k] for k in ("walk_forward", "final_year", "all_unseen_years")}
    for k, v in show.items():
        print(f"{SYM} {tf} {key} | {k}: n {v['n']}, PF {v['pf']:.3f}, stress {v['stress'].get('pf', float('nan')):.3f}, net {v['net_r']:+.1f}R, win {v['win_rate']:.0%}, "
              f"maxDD {v['max_drawdown_r']:.1f}R, w/o 3 best {v['pf_without_3_largest_wins']}, buys {v['buys'].get('pf')} ({v['buys']['n']}), sells {v['sells'].get('pf')} ({v['sells']['n']}), "
              f"resampling {v['resampling']}, months {v['positive_months']}/{v['months']}, cost/trade {v['cost_r_per_trade']:.3f}R")
    print("by year:", {y: (round(v["pf"], 2), v["n"]) for y, v in res["all_unseen_years"]["by_year"].items()})
    if BTC:
        print("flat $ spread:", {y: (round(v["pf"], 2), v["n"]) for y, v in res["flat_spread_in_dollars"]["by_year"].items()}, "all", round(res["flat_spread_in_dollars"]["all_unseen_years"]["pf"], 3))
    for q in res["picks"]:
        print("  pick", q["year"], q["pick"], "score", q["score"], "n", q["n"], "PF", round(q["pf"], 2), "net", round(q["net_r"], 1), q["setup"])


# ----------------------------------------------------------------------------- self-test
def selftest(work):
    """1. With the price scale switched off, the outcomes of all signals followed by the one-position rule are
    exactly hump_engine.simulate. 2. aggregate() equals take() + sums. 3. Features do not look ahead: computed on
    the series cut at a row, the values at the last closed trigger bar are the same as on the whole series."""
    global MK
    MK = Mk(work)
    rng = random.Random(5)
    ps = MK.ps; hs = MK.hs
    try:
        MK.ps = np.ones(len(ps))
        n_tr = 0
        for q in range(120):
            tf = rng.choice(["M3", "M5", "M10", "M15", "M30", "H1"])
            p = candidates(tf, 400)[rng.randrange(400)]
            c, sg, ix, er = prepare(p)
            for cost in COSTS + (dict(slip=0.05, comm=0.03, delay=2, trail_worst=1),):
                out = run_outcomes(c, sg, er, cost, parity=True)
                idx = take(out[:, 1].astype(np.int64), out[:, 2].astype(np.int64), np.ones(len(out), np.bool_))
                mine = out[idx][:, 1:6]
                s0, s1 = H.SESSIONS[c["session"]]
                wk = (((MK.dow == 4) & (MK.tod >= 1380)) | MK.pre_gap) if c["weekend_close"] else MK.wk_none
                ref = H.simulate(sg, er, MK.o, MK.h, MK.l, MK.c, MK.hs, MK.tod, s0, s1, c["buf"], c["anticip"], c["min_rr"], int(c["tp_mode"]),
                                 c["tp_rr"], c["trail_start"], c["trail_dist"], 1e18, c["min_risk"], c["max_risk"], cost["slip"], cost["comm"],
                                 int(cost["delay"]), int(cost["trail_worst"]), wk, 0, 0.0, 0.0, 0, int(c["max_hold"]), int(c["eod"]))
                assert mine.shape == ref.shape and np.array_equal(mine[:, :3], ref[:, :3]) and np.allclose(mine[:, 3:], ref[:, 3:], rtol=0, atol=1e-12), (tf, p)
                n_tr += len(ref)
        print(f"engine parity: 360 runs, {n_tr} trades identical to hump_engine.simulate")
    finally:
        MK.ps = ps
    # the production rules: the weekend arrays are what the EA can know
    if not BTC:
        fri = MK.wk_gold; wko = MK.wko_gold
        assert not (fri & ~((MK.dow == 4) & (MK.tod >= 1380))).any()
        t = pd.DatetimeIndex(MK.t)
        for j in np.where(wko)[0][:400]:
            prev = t[j - 1]; cur = t[j]
            last_fri = cur.normalize() - pd.Timedelta(days=(cur.dayofweek - 4) % 7) + pd.Timedelta(hours=23)
            if cur < last_fri:
                last_fri -= pd.Timedelta(days=7)
            assert prev < last_fri < cur, (prev, cur, last_fri)
        print(f"weekend rule: {int(fri.sum())} Friday-window bars; {int(wko.sum())} catch-up closes after a missed Friday close, all checked")
    gaps = np.diff(MK.t.astype("datetime64[m]").astype(np.int64))
    assert int(MK.after_break[1:].sum()) == int((gaps >= 30).sum())
    print(f"break rule: no entry on {int(MK.after_break.sum())} bars that follow a break of 30 minutes or more")
    n_cmp = 0
    for q in range(40):
        tf = rng.choice(["M5", "M15", "H1"])
        p = candidates(tf, 400)[rng.randrange(400)]
        c, sg, ix, er = prepare(p)
        if not len(sg):
            continue
        M = masks_of(tf, ix, sg[:, 1].astype(np.int8), er)
        out = run_outcomes(c, sg, er, COSTS[0])
        k = out[:, 0].astype(np.int64); e = out[:, 1].astype(np.int64); j = out[:, 2].astype(np.int64)
        A = aggregate(M, k, e, j, out[:, 4], out[:, 6], MK.year, len(MK.years))
        for v in rng.sample(range(len(CONDS)), 8):
            idx = take(e, j, M[v][k]); r = out[idx, 4]; y = MK.year[e[idx]]
            for yy in range(len(MK.years)):
                rr = r[y == yy]
                assert A[v, yy, 0] == len(rr) and abs(A[v, yy, 1] - rr[rr > 0].sum()) < 1e-9 and abs(A[v, yy, 2] + rr[rr <= 0].sum()) < 1e-9
                n_cmp += 1
    print(f"aggregate: {n_cmp} condition-year sums equal the trade lists")
    # look-ahead: features on a cut series
    names = ["tr_h4", "tr_d1", "sl_h4", "sl_d1", "adx_h1", "adx_h4", "atrp", "pdr", "tdr", "pdpos", "dopen", "asia_pos", "nyor_pos", "rn",
             "bos_up", "bos_dn", "hm1", "hm2", "volr", "body_dir", "body_frac", "rng_atr", "xs_dn", "xs_up", "sw_dn", "sw_up"]
    full_m1 = pd.read_pickle(os.path.join(work, "m1.pkl"))
    rs = np.random.default_rng(3); n_feat = 0; n_diff_next = 0
    for tf in ("M5", "H1"):
        F = MK.feat(tf)
        tt = MK._tf[tf]["t"].index.values
        for cut in sorted(rs.integers(len(full_m1) // 3, len(full_m1) - 5, 5)):
            part = full_m1.iloc[:cut + 1]
            tmp = os.path.join(work, "_selftest"); os.makedirs(tmp, exist_ok=True)
            part.to_pickle(os.path.join(tmp, "m1.pkl")); json.dump(MK.meta, open(os.path.join(tmp, "meta.json"), "w"))
            mk2 = Mk(tmp); F2 = mk2.feat(tf)
            closed = mk2._tf[tf]["t"].index.values + np.timedelta64(B.TF_MIN[tf], "m")
            i2 = int(np.searchsorted(closed, part.index.values[-1], side="right") - 1) - 1      # last bar surely complete in the cut
            i1 = int(np.searchsorted(tt, mk2._tf[tf]["t"].index.values[i2]))
            assert tt[i1] == mk2._tf[tf]["t"].index.values[i2]
            for nm in names:
                a, b = getattr(F, nm)[i1], getattr(F2, nm)[i2]
                assert (a == b) or (a != a and b != b) or (isinstance(a, float) and abs(a - b) < 1e-9 * max(1.0, abs(a))), (tf, cut, nm, a, b)
                z = getattr(F, nm)[i1 + 1]
                n_feat += 1; n_diff_next += not ((z == b) or (z != z and b != b))
    assert n_diff_next > 0.2 * n_feat
    print(f"features: {n_feat} values identical when the series is cut after the bar; the next bar's value would differ in {n_diff_next}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build(sys.argv[2], sys.argv[3])
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else 3)
    elif cmd == "wf":
        wf(sys.argv[2], sys.argv[3])
    elif cmd == "detail":
        detail(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "selftest":
        selftest(sys.argv[2])
