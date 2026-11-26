#!/usr/bin/env python3
"""
ref_signals.py -- independent REFERENCE of the SIGNAL side of the TradingView
Pine Script v6 strategy AMVI_FGF_Inverted_XAUUSD_15m.pine, written for
differential testing against another implementation.

Source of truth: the Pine file only, plus the Pine v6 reference definitions of
the built-ins.  Python 3 standard library + numpy, nothing else.

PUBLIC FUNCTIONS
    reference_signals(m1, chart_tf, p) -> dict(chart_t, trig, volc, zone)
    reference_details(m1, chart_tf, p) -> the same plus every intermediate series
                                          and the `fragile` masks (decision 18)
    build_bars(m1, tf)                 -> bars of `tf` minutes built from 1m bars

For every chart bar N of timeframe chart_tf, as the script sees it at that
bar's close:
    trig[N] = `trigger`      (anyCross and hotCount >= minConfluence)
    volc[N] = `volCollapse`  (ta.crossunder(avgAmvi, lowVolThreshold))
    zone[N] = +1 if amviDirUp, -1 if amviDirDn, else 0

=========================================================================
RULES THIS FILE IMPLEMENTS (given, not chosen)
=========================================================================
MARKET / BARS
  * 24/7 crypto perpetual, syminfo.mintick = 0.1.
  * Input: ONE-MINUTE bars, dict of numpy arrays m1['t'] (int64, bar OPEN time
    in ms since the epoch, strictly increasing; gaps are tolerated), m1['o'],
    m1['h'], m1['l'], m1['c'] (float64).
  * A bar of T minutes opens at every multiple of T minutes since the epoch
    (every T used divides 1440; 1440 = Pine "D"), contains the 1m bars whose
    open time is in [open, open + T), has open = first, high = max, low = min,
    close = last, and does not exist when no 1m bar falls inside it.
    time_close of a bar = its open time + T minutes.
EXECUTION MODEL
  * Properties -> Script executions = "On bar close" only: one execution per
    chart bar, at its close, barstate.isconfirmed = true and
    barstate.ishistory = true (so fgfLiveBar = false, amviCcDups stays 0).
PINE BUILT-INS (reference definitions)
  * ta.sma(x, n)  = sum over the last n bars of x[i] / n; na until the window
    is full.
  * ta.rma(x, n)  : sum := na(sum[1]) ? ta.sma(x, n) : a * x + (1 - a) * sum[1],
    a = 1 / n (seeded with the SMA of the first full window).
  * ta.tr(true)   = max(high - low, |high - close[1]|, |low - close[1]|),
    and high - low on the first bar.
  * ta.atr(n)     = ta.rma(ta.tr(true), n).
  * ta.stdev(x,n) = population (biased) standard deviation around ta.sma(x, n).
  * ta.highest / ta.lowest(x, n) = rolling max / min of the last n bars, na
    until full.
  * ta.rsi(x, n)  = 100 - 100 / (1 + ta.rma(max(x - x[1], 0), n)
                                     / ta.rma(max(x[1] - x, 0), n)).
  * ta.crossover(a, b)  = a > b and a[1] <= b[1];
    ta.crossunder(a, b) = a < b and a[1] >= b[1].
  * Any comparison with na is false; arithmetic with na gives na; nz(na) = 0.
REQUEST.SECURITY ON HISTORICAL BARS (context bar: open time t, timeframe C;
requested timeframe R)
  * R > C, lookahead_on, expression offset [1]: the expression's value on the
    requested bar BEFORE the one that contains t (the last fully closed one).
  * R > C, lookahead_off, no offset: the last requested bar whose CLOSE time is
    <= the context bar's CLOSE time.
  * R == C: the context's own bar (so [1] gives the previous bar).
  * R < C, lookahead_off: the LAST requested bar inside the context bar (its
    last intrabar).
  * No such bar yet: na.

=========================================================================
PARAMETERS
=========================================================================
p maps to the Pine inputs:
  fast, slow, sd, cr, norm -> fastATRPeriod, slowATRPeriod, stdDevPeriod,
                              candleRangePeriod, normalizationPeriod
  wA, wV, wS, wC           -> aatrWeight, vrWeight, nsdWeight, acrWeight
  high, low, conf          -> highVolThreshold, lowVolThreshold, minConfluence
  tfs                      -> ENABLED AMVI timeframes in minutes, a subset of
                              (1, 5, 15, 30, 60, 240, 1440); all others (the
                              seconds ones too) are off
  f_tf                     -> fgfTf in minutes (below / equal / above chart_tf)
  lv_mode                  -> fgfLvMode: 'close' = "Signal close",
                              'entry' = "Entry price"
  band, against, allow_buy, allow_sell
                           -> fgfBandAtr, fgfAgainst, fgfAllowBuy, fgfAllowSell
  use_burst, any_combo, burst_atr, entry_dist_atr
                           -> fgfUseBurst, fgfAnyCombo, fgfBurstAtr,
                              fgfEntryDistAtr
  use_drift, drift_bars    -> fgfUseDrift, fgfDriftBars
  use_zones, parent_tf     -> fgfUseZones, fgfParentTf (minutes)
  rsi_len, fast_len, min_aligned
                           -> fgfRsiLen, fgfFastLen, fgfMinAligned
  zones                    -> timeframes (minutes) of the child zones that are
                              switched ON (order irrelevant, others are off)
  spread_pts               -> fgfSpreadPts
FIXED: noRepaint = true; fgfOn = true; fgfDistUnit = "ATR"; fgfHoldBars = 0;
fgfOnePerBar = true; fgfFlatParent = false; fgfIgnoreNa = true;
fgfHtfClosed = true; fgfLast = "Until next signal"; fgfCheckIn = "Tick".

=========================================================================
WHAT THE SCRIPT DOES, AS READ FROM THE PINE CODE
=========================================================================
A. AMVI (calc_amvi, evaluated on each requested timeframe's own bars)
     fATR = ta.atr(fast), sATR = ta.atr(slow)
     vr   = sATR > 0 ? min(2, max(0.5, fATR / sATR)) : 1.0   (sATR na -> 1.0)
     nVR  = (vr - 0.5) / 1.5
     sd   = ta.stdev(close, sd), cr = ta.sma(high - low, cr)
     normalize(x) = hi <= lo ? 0 : (x - lo) / (hi - lo), lo / hi = ta.lowest /
                    ta.highest(x, norm)  (na while lo / hi are na)
     amvi = (wA * nATR + wV * nVR + wS * nSD + wC * nCR) * 100
B. get_mtf(tf): below = tf < chart, lag = noRepaint and not below
     tf <  chart: request(tf, calc_amvi()[0], lookahead_off) -> the AMVI of
                  the LAST intrabar of the chart bar.
     tf == chart: request(tf, calc_amvi()[1], lookahead_on)  -> the AMVI of
                  the PREVIOUS chart bar.
     tf >  chart: request(tf, calc_amvi()[1], lookahead_on)  -> the AMVI of
                  the requested bar BEFORE the one containing the chart bar's
                  open (so the value changes on the first chart bar of each
                  requested bar and is constant inside it).
     A disabled timeframe is na: never crosses, never hot, not counted.
C. Chart context: x = ta.crossover(v, high) per timeframe (v[1] = the value
   on the previous CHART bar); hot = v > high; hotCount, enCount (non-na v),
   amviSum (na as 0), avgAmvi = enCount > 0 ? amviSum / enCount : na;
   trigger = anyCross and hotCount >= conf;
   volCollapse = ta.crossunder(avgAmvi, low).
D. FlashGold signal, evaluated on the FILTER timeframe's own candles
   (fgfRead() is the expression of request.security(fgfTfEff, ...)):
     * price model: bid / ask = close -/+ spread_pts * mintick / 2, mid.
     * fgfTdiDir on a timeframe: f = ta.sma(ta.rsi(close, rsi_len), fast_len);
       +1 if f > f[1], -1 if f < f[1], else 0 (so 0, not na, while f is na).
     * fgfZoneDir(Z), requested FROM THE FILTER CONTEXT (filter bar open tF):
         Z >  F: fgfTdiDir()[1] with lookahead_on = the direction of the Z bar
                 BEFORE the one containing tF (na while there is none);
         Z == F: the filter candle's own direction;
         Z <  F: the direction of the last Z bar inside the filter candle.
       The parent goes through the same function (the "AMVI fuse").
     * parentSide = sign(parentDir) (na -> 0).  A child zone is active when it
       is ON and its direction is not na (fgfIgnoreNa); aligned when active,
       parentSide != 0 and its direction == parentSide.
       zoneReady = active == 0 or aligned >= min(min_aligned, active).
       tradeZoneBuy / Sell = not use_zones or (parentSide == +1 / -1 and
       zoneReady)   (fgfFlatParent = false).
     * atrPts = ta.atr(14) / mintick; burst threshold = burst_atr * atrPts;
       burstPts = (mid - mid[1]) / mintick; drift = (mid - mid[drift_bars]) /
       mintick; burstBuy = burstPts >= thr, burstSell = burstPts <= -thr;
       priorBuyOk = not use_drift or drift > 0 (Sell: < 0).
       rawBuy = any_combo ? tradeZoneBuy and (not use_burst or burstBuy or
       parentSide == 1) : tradeZoneBuy and burstBuy   (Sell symmetrical).
     * fgfHoldBars = 0: every candle whose buy (sell) candidate is true gives a
       buy (sell) signal; signal price = ask + entry_dist_atr * atrPts *
       mintick (buy) or bid - the same (sell).
     * fgfArm: a signal candle sets aAt = its close time, aBar = its index,
       aPx = "Signal close" ? close : nz(signal price, close),
       aDir = buy ? +1 : -1, aAtr = ta.atr(14) of the filter timeframe on that
       candle.  The arm stays until the next signal ("Until next signal").
E. Chart context (fgfSelC / fgfSel / fgfAtOpen and the [1] close-time picks,
   on a confirmed bar with open t and close t + C):
     check in force: fgfCheckIn = "Tick" becomes "Level at candle open" when
     F <= C and stays "Tick" when F > C.
     * "Tick" (F > C): the request returns fp = the last filter candle whose
       close <= t + C; fgfSelC = fgfSel = 1; the arm in force is the arm as it
       stood after fp.  fgfIdx = fp's index when t + C == fp's close, else
       fp's index + 1.
     * "Level at candle open" (F <= C): fp is the last filter candle inside
       the chart bar; the clock is the bar's OPEN t.  fgfSel = 2 (the candle
       before fp) when that one closed by t (F == C), else 0 = the previous
       chart bar's close-time pick (F < C).  Either way the arm in force is the
       arm as it stood after the last filter candle that closed at or before
       t: a signal inside the chart bar counts from the next chart bar.
       fgfIdx = that candle's index when it closes exactly at t, else + 1.
     * The price compared is the chart bar's CLOSE in both cases (fgfValue).
     * armed = an arm exists (and clock >= aAt); fgfOpen = armed.
     * band = band * nz(aAtr).  band > 0:
           up = ceil((level + band) / mintick - 1e-9) * mintick
           dn = floor((level - band) / mintick + 1e-9) * mintick
           inUp = close > up + mintick / 2, inDn = close < dn - mintick / 2
       band == 0 (band input 0, or the signal candle's ATR na / 0):
           inUp = close > level or (on the signal candle and aDir > 0 and
                  close >= level);  inDn symmetrical with <=.
       "On the signal candle" = armed and fgfIdx == aBar: for "Tick" the
       chart bar that closes together with the signal candle; for "Level at
       candle open" the chart bar that opens exactly when it closes.
     * upNow = inUp and (against or aDir > 0); dnNow = inDn and (against or
       aDir < 0); fgfBuyOk = armed and allow_buy and upNow; fgfSellOk likewise.
     * zone = +1 if fgfBuyOk and not fgfSellOk, -1 if fgfSellOk and not
       fgfBuyOk, else 0.

=========================================================================
MODELLING DECISIONS (every choice I had to take)
=========================================================================
 1. na is NaN in float64 arrays.  Integer series that can be na (bar indices,
    times in ms, directions) are carried as float64 too: every value used is
    far below 2**53, so they stay exact, and NaN gives Pine's na behaviour for
    free (comparisons false, arithmetic na).  Part E is a line-by-line
    translation of the Pine statements with numpy.where, including the unused
    branches of fgfSelC / fgfSel, rather than a shortcut.
 2. "na until the window is full" for ta.sma / ta.stdev / ta.highest /
    ta.lowest is read as: the result is na unless the window holds n bars AND
    all n values are non-na (a source that is itself na during its warm-up
    delays the result by its own warm-up).  First non-na AMVI bar of a
    timeframe (0-based) = max(fast, sd, cr) - 1 + norm - 1.  The Pine manual
    remarks of ta.highest / ta.lowest that "na values in the source series
    are ignored"; if TradingView applies that to the warm-up of fATR / sd / cr
    inside normalize(), the first AMVI bar is max(fast, sd, cr, norm) - 1
    instead and nothing else changes.  The module switch
    HIGHEST_LOWEST_IGNORE_NA = True selects that reading.
 3. ta.sma follows the reference loop literally: sum := sum + x[i] / n for
    i = 0 .. n - 1 (most recent bar first), no running sums, so no drift.
 4. ta.rma follows the reference recursion literally (plain loop), seeded by
    the first non-na ta.sma value.
 5. ta.stdev follows the reference listing: deviations with |x - avg| <= 1e-10
    count as exactly 0, result = sqrt(sum(dev^2) / n).  The middle branch of
    the manual's SUM() helper (its stray "15" for deviations between 1e-10 and
    1e-4) is ignored: such deviations cannot occur with 0.1-tick prices.
 6. ta.rsi uses IEEE division like the reference formula: average loss 0 with
    average gain > 0 gives 100; both 0 gives na.  fgfTdiDir then returns 0.
 7. math.max / math.min with an na argument give na (numpy maximum / minimum).
    Immaterial for the result: when fATR is na, nATR is na and AMVI is na.
 8. Sums follow the Pine order: wA*nATR + wV*nVR + wS*nSD + wC*nCR, then * 100;
    amviSum adds the timeframes in the order 1, 5, 15, 30, 60, 240, D.
 9. request.security is implemented by its two merge rules, which reproduce
    the five given cases whenever one timeframe divides the other:
       lookahead_on : the last requested bar whose OPEN  <= the context OPEN
       lookahead_off: the last requested bar whose CLOSE <= the context CLOSE
    For a requested timeframe that is lower but does NOT divide the context
    timeframe (child zone "2" under a 5m filter) the lookahead_off rule is
    used as stated: the last requested bar that has closed by the context
    bar's close.
10. Nested requests (fgfZoneDir inside fgfRead) are evaluated relative to the
    FILTER timeframe's bars (ctxSec = fgfTfSec decides "higher"), whatever
    the chart timeframe is.
11. The filter context runs once on every filter candle (also when F < C:
    every intrabar), so `canFire` is always true and with fgfHoldBars = 0 the
    signals are exactly the candidates.  When both candidates are true on the
    same candle (possible with use_zones off) both fire: the signal price is
    the buy one and aDir = +1, as the Pine ternaries give.
12. Each entry of p['zones'] is one switched-on child zone with that
    timeframe (a repeated timeframe counts twice, as two Pine zones would).
13. syminfo.mintick is the float64 0.1; the band rounding and all price
    arithmetic use the same operation order as the Pine expressions.
14. ta.atr(14) in fgfSignal and in fgfRead is the same series (filter
    timeframe); it is na on the first 13 filter candles, where burst gates
    are false, the signal price is na (level falls back to the close) and a
    signal arms with aAtr = na (band 0).
15. Keys missing from p take the input defaults of the Pine file; unknown
    keys are ignored.  f_tf None / 0 / "" means "Chart" (= chart_tf).  A
    timeframe in tfs outside (1, 5, 15, 30, 60, 240, 1440), or any timeframe
    that does not divide 1440 minutes, raises ValueError instead of being
    modelled by guesswork.
16. Bars are built from the 1m bars as given, including a partial first or
    last bar; no history-depth limit of TradingView (intrabar history, max
    bars) is modelled, so every series warms up from the first bar supplied.
17. Not modelled, because fixed off / unused for these outputs: seconds
    timeframes, realtime bars, "Minutes" / "Candles" permission, entry hold
    bars, flat parent, the "Points" unit, drawings, the status box, the
    direction score, the strategy engine (orders, sizing, exits).
18. Float comparisons are taken literally, as Pine takes them.  One of them
    is numerically fragile: fgfTdiDir compares the fast line with its previous
    value, and when the closes of a timeframe do not change over consecutive
    bars (common on 1m, rare on 2m, absent from 5m up on BTC) the RSI is
    unchanged in exact arithmetic, so "rising / falling / flat" is decided by
    the last bit of the RMA / SMA arithmetic.  This file follows the reference
    listings' operation order; another faithful implementation (and
    TradingView itself) may round differently there.  reference_details()
    therefore returns `fragile` masks: a zone is flagged when the arm in force
    may come from a filter candle whose parent / child-zone direction compared
    two values closer than TIE_EPS = 1e-9 (the doubt lasts until a candle with
    firm directions fires); trig / volc are flagged when an AMVI value (the
    average) is within TIE_EPS of the threshold on the bar or the one before.

SELF-TEST
    python3 -I ref_signals.py            the checks below + the requested counts
    python3 -I ref_signals.py --deep     wide comparison with the scalar simulation
    python3 -I ref_signals.py --bench    timing on 130,000 one-minute bars
The self-test checks the vectorised built-ins against scalar loops, the bar
builder and the two merge rules against brute force (series with missing
minutes), hand-made filter gates whose zones were worked out from the Pine
rules, the fgfSel machinery against its direct statement, the `fragile` masks
against a re-run with rma / sma rounded another way, and the whole of
reference_signals against a bar-by-bar scalar simulation of the script (None =
na, one execution per bar, each request resolved by one of the five cases).
"""

import math
import sys
import time as _time

import numpy as np

__all__ = ["reference_signals", "reference_details", "build_bars"]

MS_PER_MIN = 60000
MINTICK = 0.1                                  # syminfo.mintick
AMVI_TFS = (1, 5, 15, 30, 60, 240, 1440)       # en1 en5 en15 en30 en60 en240 enD (order of the Pine sums)

# ta.highest / ta.lowest over a window that holds na values (decision 2).  False: the result is na
# (the reading used here).  True: the na values are skipped, as the Pine manual's remark "na values
# in the source series are ignored" suggests; the result is still na before n bars exist.  It only
# moves the first non-na AMVI bar of each timeframe from max(fast, sd, cr) - 1 + norm - 1 to
# max(fast, sd, cr, norm) - 1.  Set the module attribute to try the other reading.
HIGHEST_LOWEST_IGNORE_NA = False

# reference_details()['fragile'] marks the bars whose answer hinges on a comparison of two floats
# that are equal in exact arithmetic or closer than this (see decision 18 in the module docstring)
TIE_EPS = 1e-9

# ---- FIXED inputs (not part of p) -------------------------------------------
NO_REPAINT = True                # noRepaint
FGF_ON = True                    # fgfOn
FGF_CHECK_IN = "Tick"            # fgfCheckIn
FGF_FLAT_PARENT = False          # fgfFlatParent
FGF_IGNORE_NA = True             # fgfIgnoreNa
FGF_HTF_CLOSED = True            # fgfHtfClosed
# fgfDistUnit = "ATR", fgfHoldBars = 0, fgfOnePerBar = true, fgfLast = "Until next signal"

# ---- input defaults of the Pine file (used for keys missing from p) ---------
PINE_DEFAULTS = {
    "fast": 7, "slow": 100, "sd": 20, "cr": 20, "norm": 200,
    "wA": 0.35, "wV": 0.25, "wS": 0.25, "wC": 0.15,
    "high": 60.0, "low": 30.0, "conf": 1,
    "tfs": (15, 60, 240),
    "f_tf": 60, "lv_mode": "close", "band": 0.5, "against": True,
    "allow_buy": True, "allow_sell": True,
    "use_burst": False, "any_combo": True, "burst_atr": 0.5, "entry_dist_atr": 0.25,
    "use_drift": False, "drift_bars": 60,
    "use_zones": True, "parent_tf": 60, "rsi_len": 14, "fast_len": 2, "min_aligned": 0,
    "zones": (60, 120, 240),
    "spread_pts": 25.0,
}


# =============================================================================
# parameters
# =============================================================================
def _tf_minutes(tf):
    """A timeframe as integer minutes (accepts ints and Pine strings such as "60", "D")."""
    if isinstance(tf, str):
        s = tf.strip().upper()
        minutes = 1440 if s in ("D", "1D") else int(s)
    else:
        minutes = int(tf)
        if minutes != tf:
            raise ValueError("timeframe must be a whole number of minutes: %r" % (tf,))
    if minutes < 1 or 1440 % minutes != 0:
        raise ValueError("only timeframes that divide 1440 minutes are modelled: %r" % (tf,))
    return minutes


def _normalise_params(p, chart_tf):
    q = dict(PINE_DEFAULTS)
    if p:
        q.update(p)
    P = {}
    for key in ("fast", "slow", "sd", "cr", "norm", "conf", "drift_bars", "rsi_len", "fast_len", "min_aligned"):
        P[key] = int(q[key])
        if P[key] != q[key]:
            raise ValueError("%s must be an integer: %r" % (key, q[key]))
    for key in ("fast", "slow", "sd", "cr", "norm", "conf", "drift_bars", "rsi_len", "fast_len"):
        if P[key] < 1:
            raise ValueError("%s must be >= 1: %r" % (key, q[key]))
    if P["min_aligned"] < 0:
        raise ValueError("min_aligned must be >= 0")
    for key in ("wA", "wV", "wS", "wC", "high", "low", "band", "burst_atr", "entry_dist_atr", "spread_pts"):
        P[key] = float(q[key])
    for key in ("against", "allow_buy", "allow_sell", "use_burst", "any_combo", "use_drift", "use_zones"):
        P[key] = bool(q[key])

    tfs = sorted(set(_tf_minutes(x) for x in ([] if q["tfs"] is None else list(q["tfs"]))))
    for tf in tfs:
        if tf not in AMVI_TFS:
            raise ValueError("tfs must be a subset of %r, got %r" % (AMVI_TFS, tf))
    P["tfs"] = tuple(tfs)

    f_tf = q["f_tf"]
    if f_tf is None or (isinstance(f_tf, str) and f_tf.strip() == "") or (not isinstance(f_tf, str) and f_tf == 0):
        P["f_tf"] = chart_tf                                              # fgfTf == "" : "Chart"
    else:
        P["f_tf"] = _tf_minutes(f_tf)
    P["parent_tf"] = _tf_minutes(q["parent_tf"])
    P["zones"] = tuple(_tf_minutes(z) for z in ([] if q["zones"] is None else list(q["zones"])))

    lv = str(q["lv_mode"]).strip().lower()
    if lv in ("close", "signal close"):
        P["lv_entry"] = False
    elif lv in ("entry", "entry price"):
        P["lv_entry"] = True
    else:
        raise ValueError("lv_mode must be 'close' or 'entry': %r" % (q["lv_mode"],))
    return P


# =============================================================================
# bars
# =============================================================================
def build_bars(m1, tf):
    """Bars of `tf` minutes built from the 1-minute bars.

    A bar opens at every multiple of tf minutes since the epoch, contains the
    1m bars whose open time is in [open, open + tf), open = first, high = max,
    low = min, close = last; it does not exist when it holds no 1m bar.
    Returns dict(t=int64 open times in ms, o, h, l, c float64).
    """
    tf = _tf_minutes(tf)
    t = np.asarray(m1["t"], dtype=np.int64)
    o = np.asarray(m1["o"], dtype=np.float64)
    h = np.asarray(m1["h"], dtype=np.float64)
    l = np.asarray(m1["l"], dtype=np.float64)
    c = np.asarray(m1["c"], dtype=np.float64)
    n = t.shape[0]
    if not (o.shape[0] == h.shape[0] == l.shape[0] == c.shape[0] == n):
        raise ValueError("m1 arrays must have the same length")
    if n == 0:
        e = np.zeros(0, dtype=np.float64)
        return {"t": np.zeros(0, dtype=np.int64), "o": e, "h": e.copy(), "l": e.copy(), "c": e.copy()}
    if n > 1 and not np.all(t[1:] > t[:-1]):
        raise ValueError("m1['t'] must be strictly increasing")
    ms = tf * MS_PER_MIN
    bucket = t // ms                                           # the bar each 1m bar falls in
    first = np.flatnonzero(np.concatenate(([True], bucket[1:] != bucket[:-1])))
    last = np.concatenate((first[1:], [n])) - 1
    return {
        "t": bucket[first] * ms,
        "o": o[first].copy(),
        "h": np.maximum.reduceat(h, first),
        "l": np.minimum.reduceat(l, first),
        "c": c[last].copy(),
    }


class _Cache(object):
    """The bars and the TDI directions of each timeframe, built once per call."""

    def __init__(self, m1, rsi_len, fast_len):
        self._m1 = m1
        self._rsi_len = rsi_len
        self._fast_len = fast_len
        self._bars = {}
        self._tdi = {}

    def bars(self, tf):
        if tf not in self._bars:
            self._bars[tf] = build_bars(self._m1, tf)
        return self._bars[tf]

    def tdi(self, tf):
        """(fgfTdiDir() on the bars of tf, the bars where it hinges on a floating-point tie)"""
        if tf not in self._tdi:
            self._tdi[tf] = _tdi(self.bars(tf)["c"], self._rsi_len, self._fast_len)
        return self._tdi[tf]


# =============================================================================
# Pine built-ins (na = NaN)
# =============================================================================
def _prev(x, n=1):
    """x[n]: the value n bars back in the same series, na while that bar does not exist."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full(x.shape[0], np.nan)
    if 0 <= n < x.shape[0]:
        out[n:] = x[:x.shape[0] - n]
    return out


def _sma(x, n):
    """ta.sma: sum of x[i] / n over the last n bars (i = 0 first); na unless all n are non-na."""
    x = np.asarray(x, dtype=np.float64)
    N = x.shape[0]
    out = np.full(N, np.nan)
    if n <= N:
        acc = np.zeros(N - n + 1)
        for k in range(n):                       # k bars back, for the bars n-1 .. N-1
            acc += x[n - 1 - k:N - k] / n
        out[n - 1:] = acc
    return out


def _rma(x, n):
    """ta.rma: sum := na(sum[1]) ? ta.sma(x, n) : alpha * x + (1 - alpha) * sum[1], alpha = 1 / n."""
    x = np.asarray(x, dtype=np.float64)
    seed = _sma(x, n).tolist()
    xs = x.tolist()
    alpha = 1.0 / n
    out = [np.nan] * len(xs)
    prev = np.nan
    for i in range(len(xs)):
        if prev != prev:                         # na(sum[1])
            prev = seed[i]
        else:
            prev = alpha * xs[i] + (1.0 - alpha) * prev
        out[i] = prev
    return np.array(out, dtype=np.float64)


def _true_range(h, l, c):
    """ta.tr(true): high - low on the first bar."""
    pc = _prev(c)
    tr = np.maximum(np.maximum(h - l, np.abs(h - pc)), np.abs(l - pc))
    if tr.shape[0]:
        tr[0] = h[0] - l[0]
    return tr


def _atr(h, l, c, n):
    """ta.atr(n) = ta.rma(ta.tr(true), n)."""
    return _rma(_true_range(h, l, c), n)


def _stdev(x, n):
    """ta.stdev: population standard deviation around ta.sma (deviations <= 1e-10 count as 0)."""
    x = np.asarray(x, dtype=np.float64)
    N = x.shape[0]
    out = np.full(N, np.nan)
    if n <= N:
        avg = _sma(x, n)[n - 1:]
        acc = np.zeros(N - n + 1)
        for k in range(n):
            dev = x[n - 1 - k:N - k] - avg
            dev = np.where(np.abs(dev) <= 1e-10, 0.0, dev)
            acc += dev * dev
        out[n - 1:] = np.sqrt(acc / n)
    return out


def _rolling(x, n, fn, skipped):
    x = np.asarray(x, dtype=np.float64)
    N = x.shape[0]
    out = np.full(N, np.nan)
    if n <= N:
        if HIGHEST_LOWEST_IGNORE_NA:
            # the other reading: na values do not take part (all na -> na)
            res = fn(np.lib.stride_tricks.sliding_window_view(np.where(np.isnan(x), skipped, x), n), axis=1)
            out[n - 1:] = np.where(res == skipped, np.nan, res)
        else:
            out[n - 1:] = fn(np.lib.stride_tricks.sliding_window_view(x, n), axis=1)   # NaN in the window -> NaN
    return out


def _highest(x, n):
    """ta.highest: max of the last n bars, na unless all n are non-na (see HIGHEST_LOWEST_IGNORE_NA)."""
    return _rolling(x, n, np.max, -np.inf)


def _lowest(x, n):
    """ta.lowest: min of the last n bars, na unless all n are non-na (see HIGHEST_LOWEST_IGNORE_NA)."""
    return _rolling(x, n, np.min, np.inf)


def _rsi(x, n):
    """ta.rsi: 100 - 100 / (1 + rma(up, n) / rma(down, n))."""
    x = np.asarray(x, dtype=np.float64)
    px = _prev(x)
    up = np.maximum(x - px, 0.0)
    down = np.maximum(px - x, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = _rma(up, n) / _rma(down, n)          # x / 0 = inf, 0 / 0 = na
        return 100.0 - 100.0 / (1.0 + rs)


def _tdi(close, rsi_len, fast_len):
    """fgfTdiDir(): +1 / -1 / 0 as the fast line (SMA of RSI) rises / falls / else (never na).

    Also returns the bars where that answer is numerically fragile: past the warm-up, the two
    values compared are within TIE_EPS of each other (the RSI did not really move: unchanged
    closes) or one of them is na (RSI 0 / 0).
    """
    f = _sma(_rsi(close, rsi_len), fast_len)
    f1 = _prev(f)
    direction = np.where(f > f1, 1.0, np.where(f < f1, -1.0, 0.0))
    with np.errstate(invalid="ignore"):
        fragile = (np.arange(f.shape[0]) >= rsi_len + fast_len) & ~(np.abs(f - f1) > TIE_EPS)
    return direction, fragile


def _tdi_dir(close, rsi_len, fast_len):
    return _tdi(close, rsi_len, fast_len)[0]


# =============================================================================
# request.security merge rules (historical bars)
# =============================================================================
def _idx_lookahead_on(req_t, ctx_t):
    """lookahead_on: index of the last requested bar whose OPEN <= the context bar's OPEN (-1: none).

    For a requested timeframe >= the context's this is the requested bar that
    contains the context bar's open time.
    """
    return np.searchsorted(req_t, ctx_t, side="right") - 1


def _idx_lookahead_off(req_t, req_tf, ctx_t, ctx_tf):
    """lookahead_off: index of the last requested bar whose CLOSE <= the context bar's CLOSE (-1: none).

    Higher timeframe: the last requested bar closed by the context bar's close;
    same timeframe: the context's own bar; lower timeframe: the last intrabar.
    """
    return np.searchsorted(req_t + req_tf * MS_PER_MIN, ctx_t + ctx_tf * MS_PER_MIN, side="right") - 1


def _take(values, idx):
    """values[idx] as a Pine series: a negative index means 'no such bar' -> na."""
    out = np.full(idx.shape[0], np.nan)
    ok = idx >= 0
    out[ok] = values[idx[ok]]
    return out


# =============================================================================
# A / B / C : AMVI, get_mtf, trigger, volCollapse
# =============================================================================
def _normalize(val, n):
    """normalize(val, len) => hi <= lo ? 0.0 : (val - lo) / (hi - lo)   (na while lo / hi are na)."""
    lo = _lowest(val, n)
    hi = _highest(val, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(hi <= lo, 0.0, (val - lo) / (hi - lo))


def _calc_amvi(bars, P):
    """calc_amvi() on one timeframe's bars."""
    h, l, c = bars["h"], bars["l"], bars["c"]
    f_atr = _atr(h, l, c, P["fast"])
    s_atr = _atr(h, l, c, P["slow"])
    with np.errstate(divide="ignore", invalid="ignore"):
        vr = np.where(s_atr > 0, np.minimum(2.0, np.maximum(0.5, f_atr / s_atr)), 1.0)
    n_vr = (vr - 0.5) / 1.5
    sd = _stdev(c, P["sd"])
    cr = _sma(h - l, P["cr"])
    n_atr = _normalize(f_atr, P["norm"])
    n_sd = _normalize(sd, P["norm"])
    n_cr = _normalize(cr, P["norm"])
    return (P["wA"] * n_atr + P["wV"] * n_vr + P["wS"] * n_sd + P["wC"] * n_cr) * 100.0


def _get_mtf(cache, tf, chart_tf, chart_t, P):
    """get_mtf(tf, true) on every chart bar."""
    req = cache.bars(tf)
    amvi = _calc_amvi(req, P)
    below = tf < chart_tf                      # bool below = on and in_seconds(tf) < in_seconds(timeframe.period)
    lag = NO_REPAINT and not below             # bool lag   = noRepaint and not below
    if lag:
        # request.security(tf, calc_amvi()[1], lookahead_on): the bar before the requested bar
        # that contains the chart bar's open (tf == chart: the previous chart bar)
        return _take(amvi, _idx_lookahead_on(req["t"], chart_t) - 1)
    # request.security(tf, calc_amvi()[0], lookahead_off): the last intrabar of the chart bar
    return _take(amvi, _idx_lookahead_off(req["t"], tf, chart_t, chart_tf))


def _amvi_side(cache, chart_t, chart_tf, P):
    n = chart_t.shape[0]
    hot_count = np.zeros(n, dtype=np.int64)
    en_count = np.zeros(n, dtype=np.int64)
    amvi_sum = np.zeros(n, dtype=np.float64)
    any_cross = np.zeros(n, dtype=bool)
    v_by_tf = {}
    near_high = np.zeros(n, dtype=bool)        # diagnostics only: a v within TIE_EPS of the threshold
    for tf in AMVI_TFS:                        # the order of the Pine sums
        if tf not in P["tfs"]:
            continue                           # disabled: v = na
        v = _get_mtf(cache, tf, chart_tf, chart_t, P)
        v_by_tf[tf] = v
        is_na = np.isnan(v)
        near_high |= np.abs(v - P["high"]) <= TIE_EPS
        any_cross |= (v > P["high"]) & (_prev(v) <= P["high"])      # ta.crossover(v, highVolThreshold)
        hot_count += (~is_na) & (v > P["high"])                     # hot(v)
        en_count += ~is_na                                          # cnt(v)
        amvi_sum = amvi_sum + np.where(is_na, 0.0, v)               # val(v)
    with np.errstate(divide="ignore", invalid="ignore"):
        avg = np.where(en_count > 0, amvi_sum / en_count, np.nan)   # avgAmvi
    trig = any_cross & (hot_count >= P["conf"])                     # trigger
    volc = (avg < P["low"]) & (_prev(avg) >= P["low"])              # ta.crossunder(avgAmvi, lowVolThreshold)
    near_low = np.abs(avg - P["low"]) <= TIE_EPS

    def or_prev(flag):                                              # the flag on this bar or the one before
        return flag | np.concatenate((np.zeros(min(1, n), dtype=bool), flag[:-1]))

    return {"v": v_by_tf, "hot_count": hot_count, "en_count": en_count, "avg_amvi": avg,
            "any_cross": any_cross, "trig": trig, "volc": volc,
            "trig_fragile": or_prev(near_high), "volc_fragile": or_prev(near_low)}


# =============================================================================
# D : the FlashGold signal and the arm, on the filter timeframe's candles
# =============================================================================
def _zone_dir(cache, tf, f_tf, f_t):
    """fgfZoneDir(tf, ctxSec) on every filter candle (and whether that direction is a fragile tie)."""
    req = cache.bars(tf)
    d, d_fragile = cache.tdi(tf)
    if FGF_HTF_CLOSED and tf > f_tf:
        # dPrev = request.security(tf, fgfTdiDirPrev(), lookahead_on): the direction of the
        # zone bar before the one that contains the filter candle's open
        j = _idx_lookahead_on(req["t"], f_t) - 1
    else:
        # dNow = request.security(tf, fgfTdiDir(), lookahead_off): the filter candle's own bar
        # (tf == filter) or the last zone bar inside the filter candle (tf < filter)
        j = _idx_lookahead_off(req["t"], tf, f_t, f_tf)
    return _take(d, j), _take(d_fragile.astype(np.float64), j) > 0


def _filter_context(cache, P):
    """fgfRead(): fgfSignal + fgfArm on every candle of the filter timeframe."""
    f_tf = P["f_tf"]
    fb = cache.bars(f_tf)
    f_t = fb["t"]
    nF = f_t.shape[0]
    close = fb["c"]

    # price model
    pt = MINTICK
    half_spread = P["spread_pts"] * pt * 0.5
    bid = close - half_spread
    ask = close + half_spread
    mid = (bid + ask) * 0.5

    # TDI trade zone
    parent_dir, fragile = _zone_dir(cache, P["parent_tf"], f_tf, f_t)
    parent_side = np.where(parent_dir > 0, 1.0, np.where(parent_dir < 0, -1.0, 0.0))
    active = np.zeros(nF, dtype=np.int64)
    aligned = np.zeros(nF, dtype=np.int64)
    zone_dirs = []
    for z_tf in P["zones"]:                                   # the child zones that are ON
        z_dir, z_fragile = _zone_dir(cache, z_tf, f_tf, f_t)
        fragile = fragile | z_fragile
        zone_dirs.append(z_dir)
        on = np.ones(nF, dtype=bool) if not FGF_IGNORE_NA else ~np.isnan(z_dir)   # fgfZoneOn
        active += on
        aligned += on & (parent_side != 0) & (z_dir == parent_side)               # fgfAlign
    required = np.minimum(P["min_aligned"], active)
    parent_flat_allowed = FGF_FLAT_PARENT & (parent_side == 0)
    zone_ready = (active == 0) | (aligned >= required)
    if P["use_zones"]:
        tz_buy = ((parent_side == 1) | parent_flat_allowed) & zone_ready
        tz_sell = ((parent_side == -1) | parent_flat_allowed) & zone_ready
    else:
        tz_buy = np.ones(nF, dtype=bool)
        tz_sell = np.ones(nF, dtype=bool)

    # burst / prior drift (fgfDistUnit = "ATR")
    atr14 = _atr(fb["h"], fb["l"], close, 14)
    atr_pts = atr14 / pt
    burst_thr = P["burst_atr"] * atr_pts
    entry_dist = P["entry_dist_atr"] * atr_pts
    burst_pts = (mid - _prev(mid)) / pt
    drift_pts = (mid - _prev(mid, P["drift_bars"])) / pt
    burst_buy = burst_pts >= burst_thr
    burst_sell = burst_pts <= -burst_thr
    if P["use_drift"]:
        prior_buy_ok = drift_pts > 0
        prior_sell_ok = drift_pts < 0
    else:
        prior_buy_ok = np.ones(nF, dtype=bool)
        prior_sell_ok = np.ones(nF, dtype=bool)
    if P["any_combo"]:
        if P["use_burst"]:
            raw_buy = tz_buy & (burst_buy | (parent_side == 1))
            raw_sell = tz_sell & (burst_sell | (parent_side == -1))
        else:
            raw_buy = tz_buy.copy()
            raw_sell = tz_sell.copy()
    else:
        raw_buy = tz_buy & burst_buy
        raw_sell = tz_sell & burst_sell
    buy_candidate = raw_buy & prior_buy_ok
    sell_candidate = raw_sell & prior_sell_ok

    # fgfHoldBars = 0 and canFire always true (one execution per filter candle):
    # the signals are the candidates
    s_buy = buy_candidate
    s_sell = sell_candidate
    buy_px = ask + entry_dist * pt
    sell_px = bid - entry_dist * pt
    s_px = np.where(s_buy, buy_px, np.where(s_sell, sell_px, np.nan))          # signalPx
    # aPx := fgfLvMode == "Entry price" ? nz(sPx, close) : close
    arm_px = np.where(np.isnan(s_px), close, s_px) if P["lv_entry"] else close

    # fgfArm: committed state carried from candle to candle
    f_close_time = f_t + f_tf * MS_PER_MIN                    # nz(time_close, time)
    fire = (s_buy | s_sell).tolist()
    is_buy = s_buy.tolist()
    close_time_l = f_close_time.tolist()
    arm_px_l = arm_px.tolist()
    atr_l = atr14.tolist()
    a_at = [np.nan] * nF
    a_bar = [np.nan] * nF
    a_px = [np.nan] * nF
    a_dir = [0.0] * nF
    a_atr = [np.nan] * nF
    cur_at = np.nan       # var int   aAt  = na
    cur_bar = np.nan      # var int   aBar = na
    cur_px = np.nan       # var float aPx  = na
    cur_dir = 0.0         # var int   aDir = 0
    cur_atr = np.nan      # var float aAtr = na
    for k in range(nF):
        if fire[k]:
            cur_at = float(close_time_l[k])
            cur_bar = float(k)
            cur_px = arm_px_l[k]
            cur_dir = 1.0 if is_buy[k] else -1.0
            cur_atr = atr_l[k]
        a_at[k] = cur_at
        a_bar[k] = cur_bar
        a_px[k] = cur_px
        a_dir[k] = cur_dir
        a_atr[k] = cur_atr

    # Diagnostics only: is the arm after each candle numerically fragile?  A candle whose TDI
    # directions hinge on a tie may or may not fire in another implementation; the doubt lasts
    # until a candle with firm directions fires and replaces the whole arm.
    fired = s_buy | s_sell
    last_decisive = np.maximum.accumulate(np.where(fragile | fired, np.arange(nF), -1)) if nF else np.zeros(0, int)
    arm_fragile = np.where(last_decisive >= 0, fragile[np.maximum(last_decisive, 0)], False)

    return {
        "f_tf": f_tf, "f_t": f_t,
        "aAt": np.array(a_at, dtype=np.float64), "aBar": np.array(a_bar, dtype=np.float64),
        "aPx": np.array(a_px, dtype=np.float64), "aDir": np.array(a_dir, dtype=np.float64),
        "aAtr": np.array(a_atr, dtype=np.float64),
        "aFragile": arm_fragile.astype(np.float64), "fragile_candle": fragile,
        "s_buy": s_buy, "s_sell": s_sell, "s_px": s_px, "atr14": atr14,
        "parent_dir": parent_dir, "parent_side": parent_side, "zone_dirs": zone_dirs,
        "active_zones": active, "aligned_zones": aligned,
        "burst_pts": burst_pts, "drift_pts": drift_pts,
    }


# =============================================================================
# E : the gates on the chart bars (line-by-line translation, confirmed bar)
# =============================================================================
def _filter_gate(chart_t, chart_close, chart_tf, f_tf, f_t, arm, P):
    """fgfBuyOk / fgfSellOk / the zone on every chart bar.

    arm: dict of the filter-context series aAt, aBar, aPx, aDir, aAtr (one value
    per filter candle, the committed state after that candle).
    """
    n = chart_t.shape[0]
    nF = f_t.shape[0]
    time_ = chart_t.astype(np.float64)                        # time
    time_close = time_ + chart_tf * MS_PER_MIN                # time_close
    close = np.asarray(chart_close, dtype=np.float64)
    f_close = f_t.astype(np.float64) + f_tf * MS_PER_MIN      # nz(time_close, time) in the filter context
    f_index = np.arange(nF, dtype=np.float64)                 # bar_index in the filter context

    # [fp.., fq..] = request.security(syminfo.tickerid, fgfTfEff, fgfRead(), gaps_off, lookahead_off)
    k = _idx_lookahead_off(f_t, f_tf, chart_t, chart_tf)      # the filter candle returned on each chart bar
    fpAt, fpBar, fpPx = _take(arm["aAt"], k), _take(arm["aBar"], k), _take(arm["aPx"], k)
    fpDir, fpAtr = _take(arm["aDir"], k), _take(arm["aAtr"], k)
    fpIdx, fpClose = _take(f_index, k), _take(f_close, k)
    # the [1] members of the tuple: the candle before it (na when there is none)
    fqAt, fqBar, fqPx = _take(arm["aAt"], k - 1), _take(arm["aBar"], k - 1), _take(arm["aPx"], k - 1)
    fqDir, fqAtr = _take(arm["aDir"], k - 1), _take(arm["aAtr"], k - 1)
    fqClose = _take(f_close, k - 1)

    # string fgfCheck = fgfCheckIn != "Candle open" and fgfTfSec <= in_seconds(timeframe.period)
    #                   ? "Level at candle open" : fgfCheckIn
    check = "Level at candle open" if (FGF_CHECK_IN != "Candle open" and f_tf <= chart_tf) else FGF_CHECK_IN
    live_bar = False                                          # fgfLiveBar = not barstate.isconfirmed
    at_open = check == "Candle open" or check == "Level at candle open" or (check == "Candle close" and live_bar)
    clock_c = time_close                                      # fgfClockC on a confirmed bar
    clock = time_ if at_open else clock_c                     # fgfClock

    # int fgfSelC = fgfClockC >= fpClose ? 1 : 2
    sel_c = np.where(clock_c >= fpClose, 1, 2)
    # int fgfSel  = fgfAtOpen ? (fpClose <= time ? 1 : fqClose <= time ? 2 : 0) : fgfSelC
    if at_open:
        sel = np.where(fpClose <= time_, 1, np.where(fqClose <= time_, 2, 0))
    else:
        sel = sel_c

    # the close-time pick of every bar, kept for the next bar's open (fgfSel 0)
    cAt = np.where(sel_c == 1, fpAt, fqAt)
    cBar = np.where(sel_c == 1, fpBar, fqBar)
    cPx = np.where(sel_c == 1, fpPx, fqPx)
    cDir = np.where(sel_c == 1, fpDir, fqDir)
    cAtr = np.where(sel_c == 1, fpAtr, fqAtr)
    cIdx = np.where(sel_c == 1,
                    np.where(clock_c == fpClose, fpIdx, fpIdx + 1),
                    np.where(clock_c == fqClose, fpIdx - 1, fpIdx))
    cK = np.where(sel_c == 1, fpIdx, fpIdx - 1)
    cKClose = np.where(sel_c == 1, fpClose, fqClose)

    def pick(p_, q_, c_series):
        return np.where(sel == 1, p_, np.where(sel == 2, q_, _prev(c_series)))

    sig_at = pick(fpAt, fqAt, cAt)                            # fgfSigAt
    sig_bar = pick(fpBar, fqBar, cBar)                        # fgfSigBar
    level = pick(fpPx, fqPx, cPx)                             # fgfLevel
    sig_dir = np.nan_to_num(pick(fpDir, fqDir, cDir), nan=0.0)    # fgfSigDir = nz(...)
    sig_atr = pick(fpAtr, fqAtr, cAtr)                        # fgfSigAtr
    # diagnostics only: the same pick applied to the "this arm hinges on a tie" flag
    a_fragile = arm["aFragile"] if "aFragile" in arm else np.zeros(nF, dtype=np.float64)
    fpFr, fqFr = _take(a_fragile, k), _take(a_fragile, k - 1)
    sig_fragile = np.nan_to_num(pick(fpFr, fqFr, np.where(sel_c == 1, fpFr, fqFr)), nan=0.0) > 0
    if not at_open:
        idx = cIdx                                            # fgfIdx
    else:
        idx = np.where(sel == 1,
                       np.where(time_ == fpClose, fpIdx, fpIdx + 1),
                       np.where(sel == 2,
                                np.where(time_ == fqClose, fpIdx - 1, fpIdx),
                                np.where(time_ == _prev(cKClose), _prev(cK), _prev(cK) + 1)))

    # fgfValue = fgfCheck == "Candle open" ? open : fgfCheck == "Candle close" and fgfLiveBar ? close[1] : close
    value = close

    armed = (~np.isnan(sig_at)) & (clock >= sig_at)           # fgfArmed
    open_ = armed                                             # fgfOpen, fgfLast = "Until next signal"

    on_sig_bar = armed & (idx == sig_bar)                     # fgfOnSigBar
    at_buy_lv = on_sig_bar & (sig_dir > 0) & (value >= level)     # fgfAtBuyLv
    at_sell_lv = on_sig_bar & (sig_dir < 0) & (value <= level)    # fgfAtSellLv

    mt = MINTICK                                              # fgfMt
    band = P["band"] * np.nan_to_num(sig_atr, nan=0.0)        # fgfBand = fgfBandAtr * nz(fgfSigAtr)
    has_band = band > 0
    up_lv = np.where(has_band, np.ceil((level + band) / mt - 1e-9) * mt, level)     # fgfUpLv
    dn_lv = np.where(has_band, np.floor((level - band) / mt + 1e-9) * mt, level)    # fgfDnLv
    in_up = np.where(has_band, value > up_lv + mt / 2, (value > level) | at_buy_lv)     # fgfInUp
    in_dn = np.where(has_band, value < dn_lv - mt / 2, (value < level) | at_sell_lv)    # fgfInDn
    up_now = in_up & (P["against"] | (sig_dir > 0))           # fgfUpNow
    dn_now = in_dn & (P["against"] | (sig_dir < 0))           # fgfDnNow

    buy_ok = (not FGF_ON) | (open_ & P["allow_buy"] & up_now)     # fgfBuyOk
    sell_ok = (not FGF_ON) | (open_ & P["allow_sell"] & dn_now)   # fgfSellOk
    dir_up = FGF_ON & buy_ok & ~sell_ok                       # amviDirUp
    dir_dn = FGF_ON & sell_ok & ~buy_ok                       # amviDirDn
    zone = dir_up.astype(np.int8) - dir_dn.astype(np.int8)
    assert zone.shape[0] == n
    return {
        "check": check, "at_open": at_open, "fp_index": k, "sel": sel, "sel_c": sel_c,
        "sig_at": sig_at, "sig_bar": sig_bar, "level": level, "sig_dir": sig_dir, "sig_atr": sig_atr,
        "idx": idx, "armed": armed, "on_sig_bar": on_sig_bar, "band": band, "up_lv": up_lv, "dn_lv": dn_lv,
        "in_up": in_up, "in_dn": in_dn, "buy_ok": buy_ok, "sell_ok": sell_ok, "zone": zone,
        "fragile": sig_fragile,
    }


# =============================================================================
# public
# =============================================================================
def reference_details(m1, chart_tf, p):
    """reference_signals plus the intermediate series (for diagnosing a difference).

    Keys: chart_t, trig, volc, zone, chart (the chart bars), params (normalised),
    amvi (per-timeframe v, hot_count, en_count, avg_amvi, any_cross),
    filter (the filter-timeframe context: f_tf, f_t, signals, arm series ...),
    gate (the chart-context filter series: level, sig_dir, sig_atr, idx, ...),
    fragile (dict of bool arrays trig / volc / zone, one entry per chart bar: True
    where that output hinges on a floating-point tie, see decision 18; another
    faithful implementation may legitimately differ there and nowhere else).
    """
    chart_tf = _tf_minutes(chart_tf)
    P = _normalise_params(p, chart_tf)
    cache = _Cache(m1, P["rsi_len"], P["fast_len"])
    chart = cache.bars(chart_tf)
    with np.errstate(divide="ignore", invalid="ignore"):
        amvi = _amvi_side(cache, chart["t"], chart_tf, P)
        fctx = _filter_context(cache, P)
        gate = _filter_gate(chart["t"], chart["c"], chart_tf, fctx["f_tf"], fctx["f_t"], fctx, P)
    return {
        "chart_t": chart["t"].astype(np.int64),
        "trig": amvi["trig"].astype(bool),
        "volc": amvi["volc"].astype(bool),
        "zone": gate["zone"].astype(np.int8),
        "chart": chart, "params": P, "amvi": amvi, "filter": fctx, "gate": gate,
        "fragile": {"trig": amvi["trig_fragile"], "volc": amvi["volc_fragile"], "zone": gate["fragile"]},
    }


def reference_signals(m1, chart_tf, p):
    """returns dict(chart_t=int64 array of chart bar open times,
                    trig=bool array, volc=bool array, zone=int8 array)  -- one entry per chart bar"""
    d = reference_details(m1, chart_tf, p)
    return {"chart_t": d["chart_t"], "trig": d["trig"], "volc": d["volc"], "zone": d["zone"]}


# =============================================================================
# self-test
# =============================================================================
def _synthetic_m1(n, seed, gaps=False):
    """A seeded random-walk 1-minute series on the 0.1 tick grid (optionally with missing bars)."""
    rng = np.random.default_rng(seed)
    vol = 12.0 * np.exp(0.8 * np.sin(np.arange(n) / 900.0) + 0.5 * np.sin(np.arange(n) / 137.0))
    close = np.round((30000.0 + np.cumsum(rng.standard_normal(n) * vol)) * 10.0) / 10.0
    open_ = np.concatenate(([30000.0], close[:-1]))
    high = np.round((np.maximum(open_, close) + np.abs(rng.standard_normal(n)) * vol * 0.4) * 10.0) / 10.0
    low = np.round((np.minimum(open_, close) - np.abs(rng.standard_normal(n)) * vol * 0.4) * 10.0) / 10.0
    t0 = 1767225600000 + 7 * MS_PER_MIN            # 2026-01-01 00:07 UTC: the first 5m / 60m bars are partial
    t = t0 + np.arange(n, dtype=np.int64) * MS_PER_MIN
    m1 = {"t": t, "o": open_, "h": high, "l": low, "c": close}
    if gaps:
        keep = rng.random(n) > 0.02                # 2 % of the minutes missing ...
        keep[5000:5400] = False                    # ... and a hole of several hours
        keep[12000:12007] = False
        m1 = {k_: v_[keep] for k_, v_ in m1.items()}
    return m1


def _same(a, b):
    return np.array_equal(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64), equal_nan=True)


def _check_builtins():
    """The vectorised built-ins against bar-by-bar scalar loops written from the definitions."""
    rng = np.random.default_rng(7)
    N = 700
    x = np.round(100.0 + np.cumsum(rng.standard_normal(N)), 1)
    x_na = x.copy()
    x_na[:23] = np.nan                               # a source with its own warm-up
    nan = float("nan")
    for src in (x, x_na):
        xs = src.tolist()
        for n in (1, 2, 7, 20, 100):
            sma, sd, hi, lo = [nan] * N, [nan] * N, [nan] * N, [nan] * N
            for i in range(n - 1, N):
                w = [xs[i - k] for k in range(n)]
                s = 0.0
                for v in w:
                    s = s + v / n
                sma[i] = s
                acc = 0.0
                for v in w:
                    d = v - s
                    if abs(d) <= 1e-10:
                        d = 0.0
                    acc = acc + d * d
                sd[i] = math.sqrt(acc / n) if acc == acc else nan
                if all(v == v for v in w):
                    hi[i], lo[i] = max(w), min(w)
            assert _same(_sma(src, n), sma), "sma %d" % n
            assert _same(_stdev(src, n), sd), "stdev %d" % n
            assert _same(_highest(src, n), hi), "highest %d" % n
            assert _same(_lowest(src, n), lo), "lowest %d" % n
            first = int(np.flatnonzero(~np.isnan(_sma(src, n)))[0])
            assert first == int(np.flatnonzero(~np.isnan(src))[0]) + n - 1
    # rma: seeded with the SMA of the first full window, then alpha = 1 / n
    r = _rma(x, 5)
    assert np.all(np.isnan(r[:4])) and r[4] == _sma(x, 5)[4]
    assert r[5] == (1.0 / 5) * x[5] + (1.0 - 1.0 / 5) * r[4]
    # true range / atr / rsi warm-ups
    h, l = x + 0.5, x - 0.7
    tr = _true_range(h, l, x)
    assert tr[0] == h[0] - l[0] and tr[1] == max(h[1] - l[1], abs(h[1] - x[0]), abs(l[1] - x[0]))
    a = _atr(h, l, x, 14)
    assert np.all(np.isnan(a[:13])) and not np.isnan(a[13])
    rs = _rsi(x, 14)
    assert np.all(np.isnan(rs[:14])) and not np.isnan(rs[14])
    assert np.nanmin(rs) >= 0.0 and np.nanmax(rs) <= 100.0
    assert _rsi(np.arange(40.0), 14)[20] == 100.0            # no losses -> 100
    d = _tdi_dir(x, 14, 2)
    assert np.all(d[:16] == 0.0) and set(np.unique(d).tolist()) <= {-1.0, 0.0, 1.0}
    # AMVI warm-up: first value at max(fast, sd, cr) - 1 + norm - 1, values within 0..100
    P = _normalise_params({"fast": 7, "slow": 100, "sd": 20, "cr": 20, "norm": 200}, 5)
    bars = {"h": h, "l": l, "c": x}
    amvi = _calc_amvi(bars, P)
    assert int(np.flatnonzero(~np.isnan(amvi))[0]) == 20 - 1 + 200 - 1
    assert np.nanmin(amvi) >= 0.0 and np.nanmax(amvi) <= 100.0 + 1e-9
    P2 = _normalise_params({"fast": 30, "slow": 400, "sd": 5, "cr": 3, "norm": 50}, 5)    # slow ATR still na: vr = 1
    amvi2 = _calc_amvi(bars, P2)
    assert int(np.flatnonzero(~np.isnan(amvi2))[0]) == 30 - 1 + 50 - 1


def _check_other_na_reading():
    """HIGHEST_LOWEST_IGNORE_NA = True: only the warm-up of the AMVI moves, the rest is identical."""
    global HIGHEST_LOWEST_IGNORE_NA
    rng = np.random.default_rng(8)
    x = np.round(100.0 + np.cumsum(rng.standard_normal(900)), 1)
    bars = {"h": x + 0.5, "l": x - 0.7, "c": x}
    P = _normalise_params({"fast": 7, "slow": 100, "sd": 20, "cr": 20, "norm": 200}, 5)
    strict = _calc_amvi(bars, P)
    src = x.copy()
    src[:30] = np.nan
    HIGHEST_LOWEST_IGNORE_NA = True
    try:
        loose = _calc_amvi(bars, P)
        hi, lo = _highest(src, 50), _lowest(src, 50)
        m1 = _synthetic_m1(2500, 4)
        p = dict(fast=3, slow=30, sd=8, cr=6, norm=40, tfs=(1, 5, 15), f_tf=5, parent_tf=5, zones=(5, 15))
        slow_out = _scalar_simulation(m1, 5, p)
        fast_out = reference_signals(m1, 5, p)
    finally:
        HIGHEST_LOWEST_IGNORE_NA = False
    assert int(np.flatnonzero(~np.isnan(strict))[0]) == 20 - 1 + 200 - 1
    assert int(np.flatnonzero(~np.isnan(loose))[0]) == 200 - 1
    assert _same(strict[218:], loose[218:])
    assert np.all(np.isnan(hi[:49])) and hi[49] == np.max(x[30:50]) and lo[49] == np.min(x[30:50])
    assert hi[400] == np.max(x[351:401]) and lo[400] == np.min(x[351:401])
    assert all(np.array_equal(np.array(slow_out[key], dtype=np.int64), fast_out[key].astype(np.int64))
               for key in ("chart_t", "trig", "volc", "zone"))


def _check_bars_and_merge():
    """build_bars and the two request.security merge rules against brute-force definitions."""
    m1 = _synthetic_m1(3000, 3, gaps=True)
    t = m1["t"].tolist()
    for tf in (1, 5, 15, 60, 240):
        b = build_bars(m1, tf)
        ms = tf * MS_PER_MIN
        groups = {}
        for i, ti in enumerate(t):
            groups.setdefault(ti // ms * ms, []).append(i)
        keys = sorted(groups)
        assert b["t"].tolist() == keys
        for j, key in enumerate(keys):
            g = groups[key]
            assert b["o"][j] == m1["o"][g[0]] and b["c"][j] == m1["c"][g[-1]]
            assert b["h"][j] == max(m1["h"][g]) and b["l"][j] == min(m1["l"][g])
    for req_tf, ctx_tf in ((1, 5), (5, 5), (60, 5), (15, 60), (240, 15), (5, 60), (1440, 60)):
        req_t = build_bars(m1, req_tf)["t"]
        ctx_t = build_bars(m1, ctx_tf)["t"]
        on = _idx_lookahead_on(req_t, ctx_t)
        off = _idx_lookahead_off(req_t, req_tf, ctx_t, ctx_tf)
        rl = req_t.tolist()
        r_ms, c_ms = req_tf * MS_PER_MIN, ctx_tf * MS_PER_MIN
        for i, ct in enumerate(ctx_t.tolist()):
            b_on = max([j for j, rt in enumerate(rl) if rt <= ct], default=-1)
            b_off = max([j for j, rt in enumerate(rl) if rt + r_ms <= ct + c_ms], default=-1)
            assert on[i] == b_on and off[i] == b_off
            if req_tf >= ctx_tf:      # lookahead_on: the requested bar that contains the context open
                assert b_on >= 0 and rl[b_on] <= ct < rl[b_on] + r_ms
            if req_tf == ctx_tf:      # same timeframe: the context's own bar, both ways
                assert b_on == i and b_off == i
            if req_tf < ctx_tf:       # lookahead_off: the last requested bar inside the context bar
                inside = [j for j, rt in enumerate(rl) if ct <= rt < ct + c_ms]
                assert inside and b_off == inside[-1]


def _check_gate_by_hand():
    """Hand-made arms: the zone a chart bar must get, worked out from the Pine rules."""
    M = MS_PER_MIN
    nan = float("nan")
    base = _normalise_params({}, 15)

    def run(chart_tf, f_tf, f_minutes, arms, chart_minutes, closes, **over):
        P = dict(base)
        P.update(over)
        arm = {key: np.array([a[i] for a in arms], dtype=np.float64)
               for i, key in enumerate(("aAt", "aBar", "aPx", "aDir", "aAtr"))}
        g = _filter_gate(np.array(chart_minutes, dtype=np.int64) * M, np.array(closes, dtype=np.float64),
                         chart_tf, f_tf, np.array(f_minutes, dtype=np.int64) * M, arm, P)
        return g["zone"].tolist()

    # --- "Tick": 15m chart, 60m filter ---------------------------------------
    # buy signal on filter candle 0 (level 100, ATR 2), nothing on candle 1,
    # sell signal on candle 2 (level 105, ATR 4)
    arms = [(60 * M, 0, 100.0, 1, 2.0), (60 * M, 0, 100.0, 1, 2.0), (180 * M, 2, 105.0, -1, 4.0)]
    f_min = [0, 60, 120]
    ch_min = list(range(0, 210, 15))                # opens 0 .. 195
    #          0    15   30   45     60     75     90    105   120    135    150    165    180    195
    closes = [100, 100, 100, 100.0, 101.1, 101.0, 98.9, 99.0, 101.1, 101.0, 98.9, 105.0, 102.9, 107.1]
    assert run(15, 60, f_min, arms, ch_min, closes, band=0.5) == [0, 0, 0, 0, 1, 0, -1, 0, 1, 0, -1, 0, -1, 1]
    assert run(15, 60, f_min, arms, ch_min, closes, band=0.5, against=False) == \
        [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, -1, 0]
    assert run(15, 60, f_min, arms, ch_min, closes, band=0.5, allow_buy=False) == \
        [0, 0, 0, 0, 0, 0, -1, 0, 0, 0, -1, 0, -1, 0]
    # no band: the level splits; AT the level only the signal's side, only on the chart bar
    # that closes with the signal candle (opens 45 and 165)
    closes0 = [100, 100, 100, 100.0, 100.0, 100.1, 99.9, 100.0, 100.0, 100.0, 100.0, 105.0, 105.0, 105.1]
    assert run(15, 60, f_min, arms, ch_min, closes0, band=0.0) == [0, 0, 0, 1, 0, 1, -1, 0, 0, 0, 0, -1, 0, 1]
    # --- "Level at candle open": 5m chart, 1m filter --------------------------
    # buy at 1m candle 4 (level 50, ATR na -> no band), sell at candle 5 (level 60, ATR 1),
    # buy at candle 9 (level 55, ATR 1)
    arms = []
    cur = (nan, nan, nan, 0, nan)
    for i in range(15):
        if i == 4:
            cur = (5 * M, 4, 50.0, 1, nan)
        elif i == 5:
            cur = (6 * M, 5, 60.0, -1, 1.0)
        elif i == 9:
            cur = (10 * M, 9, 55.0, 1, 1.0)
        arms.append(cur)
    f_min = list(range(15))
    # chart bar 0: nothing closed by its open; bar 5: the arm of candle 4 (not candle 5's, which
    # fired inside the bar), judged at the bar's close; bar 10: the arm of candle 9
    assert run(5, 1, f_min, arms, [0, 5, 10], [50.0, 50.0, 55.6], band=0.5) == [0, 1, 1]
    assert run(5, 1, f_min, arms, [0, 5, 10], [50.0, 49.9, 55.5], band=0.5) == [0, -1, 0]
    assert run(5, 1, f_min, arms, [0, 5, 10], [50.0, 50.1, 54.4], band=0.5) == [0, 1, -1]
    assert run(5, 1, f_min, arms, [0, 5, 10], [50.0, 50.0, 54.5], band=0.5) == [0, 1, 0]
    # AT the level: the chart bar that opens exactly when the signal candle (9) closes is "on the
    # signal candle"; when the minutes 10..14 are missing the next chart bar opens at 15, inside a
    # later filter candle, and a close AT the level is NO TRADE
    assert run(5, 1, f_min, arms, [0, 5, 10], [50.0, 50.0, 55.0], band=0.0) == [0, 1, 1]
    f_gap = list(range(10)) + list(range(15, 20))
    assert run(5, 1, f_gap, arms, [0, 5, 15], [50.0, 50.0, 55.0], band=0.0) == [0, 1, 0]
    assert run(5, 1, f_gap, arms, [0, 5, 15], [50.0, 50.0, 55.1], band=0.0) == [0, 1, 1]
    # --- "Level at candle open": 5m chart, 5m filter --------------------------
    # buy on candle 0 (level 10), nothing on candle 1, sell on candle 2 (level 12), no ATR -> no band
    arms = [(5 * M, 0, 10.0, 1, nan), (5 * M, 0, 10.0, 1, nan), (15 * M, 2, 12.0, -1, nan), (15 * M, 2, 12.0, -1, nan)]
    f_min = [0, 5, 10, 15]
    assert run(5, 5, f_min, arms, f_min, [10.0, 10.0, 10.0, 12.0], band=0.5) == [0, 1, 0, -1]
    assert run(5, 5, f_min, arms, f_min, [10.0, 9.9, 10.1, 12.1], band=0.5) == [0, -1, 1, 1]
    assert run(5, 5, f_min, arms, f_min, [10.0, 9.9, 10.1, 12.1], band=0.5, against=False) == [0, 0, 1, 0]


def _check_arm_in_force(d, chart_tf):
    """The translated fgfSel machinery against the direct statement of what it selects:
    the arm as it stood after the last filter candle closed by the clock (the bar's close
    for "Tick", the bar's open for "Level at candle open")."""
    g, f = d["gate"], d["filter"]
    C = chart_tf
    F = f["f_tf"]
    t = d["chart_t"]
    clock = t if g["at_open"] else t + C * MS_PER_MIN
    f_close = f["f_t"] + F * MS_PER_MIN
    m = np.searchsorted(f_close, clock, side="right") - 1
    assert g["at_open"] == (F <= C)
    assert _same(g["sig_at"], _take(f["aAt"], m))
    assert _same(g["sig_bar"], _take(f["aBar"], m))
    assert _same(g["level"], _take(f["aPx"], m))
    assert _same(g["sig_dir"], np.nan_to_num(_take(f["aDir"], m), nan=0.0))
    assert _same(g["sig_atr"], _take(f["aAtr"], m))
    armed = ~np.isnan(_take(f["aAt"], m))
    assert np.array_equal(g["armed"], armed)
    exact = _take(f_close.astype(np.float64), m) == clock
    idx = np.where(m >= 0, np.where(exact, m, m + 1), np.nan)
    assert _same(g["idx"][armed], idx[armed])


# -----------------------------------------------------------------------------
# self-test only: the script executed bar by bar with plain Python scalars
# (None = na, lists for history), each request.security resolved by one of the
# five stated cases.  Slow, but as close to "read the Pine code aloud" as it
# gets; the vectorised functions above must give the same answers.
# -----------------------------------------------------------------------------
def _s_bars(m1, tf):
    out, order = {}, []
    for t, o, h, l, c in zip(m1["t"].tolist(), m1["o"].tolist(), m1["h"].tolist(), m1["l"].tolist(),
                             m1["c"].tolist()):
        key = (t // (tf * MS_PER_MIN)) * (tf * MS_PER_MIN)
        if key not in out:
            out[key] = [o, h, l, c]
            order.append(key)
        else:
            bar = out[key]
            bar[1] = max(bar[1], h)
            bar[2] = min(bar[2], l)
            bar[3] = c
    return {"t": order, "o": [out[k][0] for k in order], "h": [out[k][1] for k in order],
            "l": [out[k][2] for k in order], "c": [out[k][3] for k in order]}


def _s_sma(x, n):
    res = []
    for i in range(len(x)):
        s = 0.0
        if i - n + 1 < 0:
            s = None
        else:
            for k in range(n):
                if x[i - k] is None:
                    s = None
                    break
                s = s + x[i - k] / n
        res.append(s)
    return res


def _s_rma(x, n):
    sma = _s_sma(x, n)
    alpha = 1.0 / n
    res, prev = [], None
    for i in range(len(x)):
        if prev is None:
            cur = sma[i]
        else:
            cur = None if x[i] is None else alpha * x[i] + (1 - alpha) * prev
        res.append(cur)
        prev = cur
    return res


def _s_tr(h, l, c):
    return [h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
            for i in range(len(h))]


def _s_stdev(x, n):
    sma = _s_sma(x, n)
    res = []
    for i in range(len(x)):
        if sma[i] is None:
            res.append(None)
            continue
        acc = 0.0
        for k in range(n):
            dev = x[i - k] - sma[i]
            if abs(dev) <= 1e-10:
                dev = 0.0
            acc = acc + dev * dev
        res.append(math.sqrt(acc / n))
    return res


def _s_extreme(x, n, fn):
    res = []
    for i in range(len(x)):
        w = x[i - n + 1:i + 1] if i - n + 1 >= 0 else [None]
        if HIGHEST_LOWEST_IGNORE_NA and i - n + 1 >= 0:
            w = [v for v in w if v is not None] or [None]
        res.append(None if any(v is None for v in w) else fn(w))
    return res


def _s_rsi(x, n):
    up, down = [None], [None]
    for i in range(1, len(x)):
        up.append(max(x[i] - x[i - 1], 0.0))
        down.append(max(x[i - 1] - x[i], 0.0))
    res = []
    for a, b in zip(_s_rma(up, n), _s_rma(down, n)):
        if a is None or b is None:
            res.append(None)
        elif b == 0.0:
            res.append(None if a == 0.0 else 100.0)
        else:
            res.append(100.0 - 100.0 / (1.0 + a / b))
    return res


def _s_tdi(c, rsi_len, fast_len):
    f = _s_sma(_s_rsi(c, rsi_len), fast_len)
    res = []
    for i in range(len(c)):
        cur, prev = f[i], (f[i - 1] if i > 0 else None)
        res.append(1 if _s_gt(cur, prev) else -1 if _s_lt(cur, prev) else 0)
    return res


def _s_amvi(bars, P):
    h, l, c = bars["h"], bars["l"], bars["c"]
    tr = _s_tr(h, l, c)
    f_atr, s_atr = _s_rma(tr, P["fast"]), _s_rma(tr, P["slow"])
    sd = _s_stdev(c, P["sd"])
    cr = _s_sma([a - b for a, b in zip(h, l)], P["cr"])

    def normalize(x):
        lo, hi = _s_extreme(x, P["norm"], min), _s_extreme(x, P["norm"], max)
        return [None if (a is None or b is None) else 0.0 if b <= a else (v - a) / (b - a)
                for v, a, b in zip(x, lo, hi)]

    n_atr, n_sd, n_cr = normalize(f_atr), normalize(sd), normalize(cr)
    res = []
    for i in range(len(c)):
        if s_atr[i] is not None and s_atr[i] > 0:
            vr = None if f_atr[i] is None else min(2.0, max(0.5, f_atr[i] / s_atr[i]))
        else:
            vr = 1.0
        n_vr = None if vr is None else (vr - 0.5) / 1.5
        if n_atr[i] is None or n_vr is None or n_sd[i] is None or n_cr[i] is None:
            res.append(None)
        else:
            res.append((P["wA"] * n_atr[i] + P["wV"] * n_vr + P["wS"] * n_sd[i] + P["wC"] * n_cr[i]) * 100.0)
    return res


def _s_request(req_t, req_tf, t, ctx_tf, lookahead_on):
    """The index of the requested bar a request reads on the context bar that opens at t
    (None: no such bar yet); with lookahead_on the caller applies the [1] offset."""
    r_ms, c_ms = req_tf * MS_PER_MIN, ctx_tf * MS_PER_MIN
    if req_tf > ctx_tf and lookahead_on:            # the requested bar that contains t
        for j in range(len(req_t) - 1, -1, -1):
            if req_t[j] <= t:
                assert t < req_t[j] + r_ms
                return j
        return None
    if req_tf > ctx_tf:                             # the last requested bar closed by the context bar's close
        for j in range(len(req_t) - 1, -1, -1):
            if req_t[j] + r_ms <= t + c_ms:
                return j
        return None
    if req_tf == ctx_tf:                            # the context's own bar
        return req_t.index(t)
    assert not lookahead_on and ctx_tf % req_tf == 0
    for j in range(len(req_t) - 1, -1, -1):         # the last requested bar inside the context bar
        if req_t[j] < t + c_ms:
            assert req_t[j] >= t
            return j
    return None


class _SRequest(object):
    """_s_request with the backward scans replaced by a moving pointer (contexts come in time order)."""

    def __init__(self):
        self._hint = {}

    def __call__(self, key, req_t, req_tf, t, ctx_tf, lookahead_on):
        r_ms, c_ms = req_tf * MS_PER_MIN, ctx_tf * MS_PER_MIN
        if req_tf == ctx_tf:
            limit = t                               # own bar: the bar that opens at t
        elif req_tf > ctx_tf and lookahead_on:
            limit = t                               # last bar with open <= t
        elif req_tf > ctx_tf:
            limit = t + c_ms - r_ms                 # last bar with open + R <= t + C
        else:
            assert not lookahead_on and ctx_tf % req_tf == 0
            limit = t + c_ms - 1                    # last bar with open < t + C
        j = self._hint.get(key, -1)
        while j + 1 < len(req_t) and req_t[j + 1] <= limit:
            j += 1
        self._hint[key] = j
        if j < 0:
            return None
        if req_tf == ctx_tf:
            assert req_t[j] == t
        elif req_tf > ctx_tf and lookahead_on:
            assert req_t[j] <= t < req_t[j] + r_ms
        elif req_tf < ctx_tf:
            assert t <= req_t[j] < t + c_ms
        return j


def _s_gt(a, b):
    return a is not None and b is not None and a > b


def _s_lt(a, b):
    return a is not None and b is not None and a < b


def _s_ge(a, b):
    return a is not None and b is not None and a >= b


def _s_le(a, b):
    return a is not None and b is not None and a <= b


def _s_eq(a, b):
    return a is not None and b is not None and a == b


def _s_add(a, b):
    return None if a is None else a + b


def _scalar_simulation(m1, chart_tf, p):
    P = _normalise_params(p, chart_tf)
    C, F = chart_tf, P["f_tf"]
    cache = {}
    request = _SRequest()

    def bars(tf):
        if tf not in cache:
            cache[tf] = _s_bars(m1, tf)
        return cache[tf]

    chart = bars(C)
    n = len(chart["t"])

    # ---- AMVI, trigger, volCollapse: one execution per chart bar --------------------------
    amvi = dict((tf, _s_amvi(bars(tf), P)) for tf in P["tfs"])
    trig, volc = [], []
    v_prev = dict((tf, None) for tf in P["tfs"])
    avg_prev = None
    for i in range(n):
        t = chart["t"][i]
        hot_count, en_count, amvi_sum, any_cross = 0, 0, 0.0, False
        for tf in AMVI_TFS:
            if tf not in P["tfs"]:
                continue
            below = tf < C
            lag = NO_REPAINT and not below
            j = request(("amvi", tf), bars(tf)["t"], tf, t, C, lag)
            if lag:
                v = None if (j is None or j - 1 < 0) else amvi[tf][j - 1]      # calc_amvi()[1]
            else:
                v = None if j is None else amvi[tf][j]                         # calc_amvi()[0]
            if _s_gt(v, P["high"]) and _s_le(v_prev[tf], P["high"]):
                any_cross = True
            if v is not None and v > P["high"]:
                hot_count += 1
            if v is not None:
                en_count += 1
            amvi_sum = amvi_sum + (0.0 if v is None else v)
            v_prev[tf] = v
        avg = amvi_sum / en_count if en_count > 0 else None
        trig.append(any_cross and hot_count >= P["conf"])
        volc.append(_s_lt(avg, P["low"]) and _s_ge(avg_prev, P["low"]))
        avg_prev = avg

    # ---- fgfRead(): one execution per filter candle ------------------------------------------
    fb = bars(F)
    tdi = dict((z, _s_tdi(bars(z)["c"], P["rsi_len"], P["fast_len"])) for z in set((P["parent_tf"],) + P["zones"]))
    atr14 = _s_rma(_s_tr(fb["h"], fb["l"], fb["c"]), 14)
    pt = MINTICK
    half_spread = P["spread_pts"] * pt * 0.5
    mids, read = [], []
    aAt = aBar = aPx = aAtr = None
    aDir = 0
    for k in range(len(fb["t"])):
        t_f = fb["t"][k]
        close = fb["c"][k]
        bid = close - half_spread
        ask = close + half_spread
        mid = (bid + ask) * 0.5
        mids.append(mid)

        def zone_dir(slot, z):
            if FGF_HTF_CLOSED and z > F:            # dPrev: lookahead_on, fgfTdiDir()[1]
                j = request((slot, z, "prev"), bars(z)["t"], z, t_f, F, True)
                return None if (j is None or j - 1 < 0) else tdi[z][j - 1]
            j = request((slot, z, "now"), bars(z)["t"], z, t_f, F, False)      # dNow: lookahead_off
            return None if j is None else tdi[z][j]

        parent_dir = zone_dir("parent", P["parent_tf"])
        parent_side = 1 if _s_gt(parent_dir, 0) else -1 if _s_lt(parent_dir, 0) else 0
        active = aligned = 0
        for slot, z in enumerate(P["zones"]):
            z_dir = zone_dir(slot, z)
            on = (not FGF_IGNORE_NA) or z_dir is not None
            active += 1 if on else 0
            aligned += 1 if (on and parent_side != 0 and z_dir == parent_side) else 0
        required = min(P["min_aligned"], active)
        flat_ok = FGF_FLAT_PARENT and parent_side == 0
        zone_ready = active == 0 or aligned >= required
        tz_buy = (not P["use_zones"]) or ((parent_side == 1 or flat_ok) and zone_ready)
        tz_sell = (not P["use_zones"]) or ((parent_side == -1 or flat_ok) and zone_ready)

        atr_pts = None if atr14[k] is None else atr14[k] / pt
        burst_thr = None if atr_pts is None else P["burst_atr"] * atr_pts
        entry_dist = None if atr_pts is None else P["entry_dist_atr"] * atr_pts
        burst_pts = None if k < 1 else (mid - mids[k - 1]) / pt
        drift_pts = None if k < P["drift_bars"] else (mid - mids[k - P["drift_bars"]]) / pt
        burst_buy = _s_ge(burst_pts, burst_thr)
        burst_sell = _s_le(burst_pts, None if burst_thr is None else -burst_thr)
        prior_buy_ok = (not P["use_drift"]) or _s_gt(drift_pts, 0)
        prior_sell_ok = (not P["use_drift"]) or _s_lt(drift_pts, 0)
        if P["any_combo"]:
            raw_buy = tz_buy and ((not P["use_burst"]) or burst_buy or parent_side == 1)
            raw_sell = tz_sell and ((not P["use_burst"]) or burst_sell or parent_side == -1)
        else:
            raw_buy = tz_buy and burst_buy
            raw_sell = tz_sell and burst_sell
        buy_candidate = raw_buy and prior_buy_ok
        sell_candidate = raw_sell and prior_sell_ok

        can_fire = True                             # lastEntryBar != bar_index: one execution per candle
        buy_px = sell_px = None
        buy_signal = sell_signal = False
        if buy_candidate and can_fire:              # fgfHoldBars == 0
            buy_px = None if entry_dist is None else ask + entry_dist * pt
            buy_signal = True
        if sell_candidate and can_fire:
            sell_px = None if entry_dist is None else bid - entry_dist * pt
            sell_signal = True
        signal_px = buy_px if buy_signal else sell_px if sell_signal else None

        before = (aAt, aBar, aPx, aDir, aAtr) if k > 0 else (None, None, None, None, None)     # the [1] values
        if buy_signal or sell_signal:               # fgfArm
            aAt = t_f + F * MS_PER_MIN
            aBar = k
            aPx = (close if signal_px is None else signal_px) if P["lv_entry"] else close
            aDir = 1 if buy_signal else -1
            aAtr = atr14[k]
        read.append({"p": (aAt, aBar, aPx, aDir, aAtr), "q": before, "idx": k, "close": t_f + F * MS_PER_MIN,
                     "q_close": (fb["t"][k - 1] + F * MS_PER_MIN) if k > 0 else None})

    # ---- the gates: one execution per chart bar ------------------------------------------------
    check = "Level at candle open" if (FGF_CHECK_IN != "Candle open" and F <= C) else FGF_CHECK_IN
    at_open = check in ("Candle open", "Level at candle open")
    na5 = (None, None, None, None, None)
    zone = []
    c_pick_prev, c_k_prev, c_kclose_prev = na5, None, None          # fgfC..[1], fgfCK[1], fgfCKClose[1]
    for i in range(n):
        time_ = chart["t"][i]
        time_close = time_ + C * MS_PER_MIN
        value = chart["c"][i]
        j = request("read", fb["t"], F, time_, C, False)
        if j is None:
            fp, fq, fp_idx, fp_close, fq_close = na5, na5, None, None, None
        else:
            fp, fq = read[j]["p"], read[j]["q"]
            fp_idx, fp_close, fq_close = read[j]["idx"], read[j]["close"], read[j]["q_close"]
        clock_c = time_close
        clock = time_ if at_open else clock_c
        sel_c = 1 if _s_ge(clock_c, fp_close) else 2
        if at_open:
            sel = 1 if _s_le(fp_close, time_) else 2 if _s_le(fq_close, time_) else 0
        else:
            sel = sel_c
        c_pick = fp if sel_c == 1 else fq
        if sel_c == 1:
            c_idx = fp_idx if _s_eq(clock_c, fp_close) else _s_add(fp_idx, 1)
            c_k, c_kclose = fp_idx, fp_close
        else:
            c_idx = _s_add(fp_idx, -1) if _s_eq(clock_c, fq_close) else fp_idx
            c_k, c_kclose = _s_add(fp_idx, -1), fq_close
        sig_at, sig_bar, level, sig_dir, sig_atr = fp if sel == 1 else fq if sel == 2 else c_pick_prev
        sig_dir = 0 if sig_dir is None else sig_dir
        if not at_open:
            idx = c_idx
        elif sel == 1:
            idx = fp_idx if _s_eq(time_, fp_close) else _s_add(fp_idx, 1)
        elif sel == 2:
            idx = _s_add(fp_idx, -1) if _s_eq(time_, fq_close) else fp_idx
        else:
            idx = c_k_prev if _s_eq(time_, c_kclose_prev) else _s_add(c_k_prev, 1)
        armed = sig_at is not None and clock >= sig_at
        is_open = armed
        on_sig_bar = armed and _s_eq(idx, sig_bar)
        at_buy_lv = on_sig_bar and sig_dir > 0 and _s_ge(value, level)
        at_sell_lv = on_sig_bar and sig_dir < 0 and _s_le(value, level)
        band = P["band"] * (0.0 if sig_atr is None else sig_atr)
        mt = MINTICK
        if band > 0:
            up_lv = None if level is None else math.ceil((level + band) / mt - 1e-9) * mt
            dn_lv = None if level is None else math.floor((level - band) / mt + 1e-9) * mt
            in_up = _s_gt(value, _s_add(up_lv, mt / 2))
            in_dn = _s_lt(value, _s_add(dn_lv, -(mt / 2)))
        else:
            in_up = _s_gt(value, level) or at_buy_lv
            in_dn = _s_lt(value, level) or at_sell_lv
        up_now = in_up and (P["against"] or sig_dir > 0)
        dn_now = in_dn and (P["against"] or sig_dir < 0)
        buy_ok = (not FGF_ON) or (is_open and P["allow_buy"] and up_now)
        sell_ok = (not FGF_ON) or (is_open and P["allow_sell"] and dn_now)
        dir_up = FGF_ON and buy_ok and not sell_ok
        dir_dn = FGF_ON and sell_ok and not buy_ok
        zone.append(1 if dir_up else -1 if dir_dn else 0)
        c_pick_prev, c_k_prev, c_kclose_prev = c_pick, c_k, c_kclose
    return {"chart_t": chart["t"], "trig": trig, "volc": volc, "zone": zone}


def _check_against_scalar(n_bars, chart_tfs, f_tfs, verbose):
    """reference_signals against the bar-by-bar scalar simulation; returns the number of comparisons."""
    # the pointer-based request must agree with the plain backward scans
    m1 = _synthetic_m1(1500, 5, gaps=True)
    for req_tf, ctx_tf, on in ((60, 5, True), (60, 5, False), (5, 5, False), (1, 5, False), (15, 60, False)):
        req_t, ctx_t = _s_bars(m1, req_tf)["t"], _s_bars(m1, ctx_tf)["t"]
        fast = _SRequest()
        for t in ctx_t:
            assert fast("k", req_t, req_tf, t, ctx_tf, on) == _s_request(req_t, req_tf, t, ctx_tf, on)
    short = dict(fast=3, slow=30, sd=8, cr=6, norm=40, high=55.0, low=35.0)
    configs = (
        ("file filter defaults", dict(short, tfs=(1, 5, 15, 60))),
        ("entry level, band 0, burst gate, drift, against off",
         dict(short, tfs=(1, 5, 15, 30, 60, 240), lv_mode="entry", band=0.0, use_burst=True, burst_atr=0.3,
              zones=(1, 5, 60), min_aligned=1, use_drift=True, drift_bars=7, against=False, conf=2, parent_tf=5)),
        ("zones off, burst only", dict(short, tfs=(5, 15), use_zones=False, any_combo=False, burst_atr=0.8,
                                       band=0.25, parent_tf=240, zones=())),
        ("zones off, no burst gate (both candidates fire)", dict(short, tfs=(1, 15), use_zones=False, band=0.1,
                                                                 allow_sell=False)),
        ("band 0, signal close, min aligned 2", dict(short, tfs=(1, 5, 15, 60), band=0.0, zones=(15, 30, 60, 120),
                                                     min_aligned=2, parent_tf=15, rsi_len=5, fast_len=3)),
        ("entry level, wide band", dict(short, tfs=(5, 60), lv_mode="entry", band=1.5, entry_dist_atr=0.6,
                                        zones=(1, 2), parent_tf=60, spread_pts=40.0)),
    )
    done = 0
    for gaps in (False, True):
        m1 = _synthetic_m1(n_bars, 11 + int(gaps), gaps=gaps)
        for chart_tf in chart_tfs:
            for f_tf in f_tfs:
                for label, cfg in configs:
                    p = dict(cfg, f_tf=f_tf)
                    # the stated lower-timeframe case needs the zone timeframe to divide the filter's
                    p["zones"] = tuple(z for z in p.get("zones", PINE_DEFAULTS["zones"]) if z >= f_tf or f_tf % z == 0)
                    parent_tf = p.get("parent_tf", PINE_DEFAULTS["parent_tf"])
                    if parent_tf < f_tf and f_tf % parent_tf != 0:
                        p["parent_tf"] = f_tf
                    slow = _scalar_simulation(m1, chart_tf, p)
                    fast = reference_signals(m1, chart_tf, p)
                    for key in ("chart_t", "trig", "volc", "zone"):
                        a = np.array(slow[key], dtype=np.int64)
                        b = fast[key].astype(np.int64)
                        if a.shape != b.shape or not np.array_equal(a, b):
                            bad = np.flatnonzero(a != b)[:5].tolist() if a.shape == b.shape else "shape"
                            raise AssertionError("scalar simulation differs: %s gaps=%s chart_tf=%d f_tf=%d %s bars %s"
                                                 % (key, gaps, chart_tf, f_tf, label, bad))
                    done += 1
                    if verbose:
                        print("   scalar == vectorised: gaps=%d chart_tf=%-3d f_tf=%-3d %-48s %s" % (
                            gaps, chart_tf, f_tf, label, _counts(fast)))
    return done


def _rma_wilder(x, n):
    """ta.rma with another rounding: Wilder's (prev * (n - 1) + x) / n, seeded by a plain mean."""
    x = np.asarray(x, dtype=np.float64)
    out = [np.nan] * x.shape[0]
    prev = np.nan
    window = []
    for i, v in enumerate(x.tolist()):
        if prev != prev:
            window = (window + [v])[-n:]
            if len(window) == n and all(w == w for w in window):
                prev = sum(window) / n
        else:
            prev = (prev * (n - 1) + v) / n
        out[i] = prev
    return np.array(out, dtype=np.float64)


def _sma_pairwise(x, n):
    """ta.sma with another rounding: numpy's pairwise sum of the window, divided once."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full(x.shape[0], np.nan)
    if n <= x.shape[0]:
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).sum(axis=1) / n
    return out


def _check_fragile_mask():
    """The same formulas rounded another way may change an output only on bars flagged `fragile`.

    Returns (zone bars that changed, zone bars flagged)."""
    global _rma, _sma
    rng = np.random.default_rng(99)
    n = 20000
    close = np.round((500.0 + np.cumsum(rng.standard_normal(n) * 0.11)) * 10.0) / 10.0     # many unchanged closes
    open_ = np.concatenate(([500.0], close[:-1]))
    high = np.round((np.maximum(open_, close) + np.abs(rng.standard_normal(n)) * 0.05) * 10.0) / 10.0
    low = np.round((np.minimum(open_, close) - np.abs(rng.standard_normal(n)) * 0.05) * 10.0) / 10.0
    m1 = {"t": 1767225600000 + np.arange(n, dtype=np.int64) * MS_PER_MIN, "o": open_, "h": high, "l": low, "c": close}
    keep = (_rma, _sma)
    changed = flagged = 0
    for chart_tf, f_tf, parent_tf, zones in ((1, 1, 1, (1, 2, 4)), (5, 1, 1, (1, 5)), (5, 5, 5, (5, 15)),
                                             (15, 5, 1, (1, 2)), (5, 60, 60, (60, 120)), (1, 5, 15, (1, 30))):
        for extra in ({}, {"band": 0.0}, {"lv_mode": "entry", "min_aligned": 1, "use_burst": True, "against": False}):
            p = dict(extra, tfs=(1, 5, 15, 60), f_tf=f_tf, parent_tf=parent_tf, zones=zones, norm=60, slow=40)
            ref = reference_details(m1, chart_tf, p)
            _rma, _sma = _rma_wilder, _sma_pairwise
            try:
                other = reference_signals(m1, chart_tf, p)
            finally:
                _rma, _sma = keep
            for key in ("trig", "volc", "zone"):
                diff = ref[key] != other[key]
                assert not (diff & ~ref["fragile"][key]).any(), "a difference outside the fragile mask: " + key
            changed += int((ref["zone"] != other["zone"]).sum())
            flagged += int(ref["fragile"]["zone"].sum())
    assert changed > 0 and flagged >= changed
    return changed, flagged


def _counts(out):
    z = out["zone"]
    return "bars=%d trig=%d volc=%d zone[-1]=%d zone[0]=%d zone[+1]=%d trig&zone[+1]=%d trig&zone[-1]=%d" % (
        z.shape[0], int(out["trig"].sum()), int(out["volc"].sum()),
        int((z == -1).sum()), int((z == 0).sum()), int((z == 1).sum()),
        int((out["trig"] & (z == 1)).sum()), int((out["trig"] & (z == -1)).sum()))


def _check_output(out, m1, chart_tf):
    n = build_bars(m1, chart_tf)["t"].shape[0]
    assert out["chart_t"].dtype == np.int64 and out["chart_t"].shape == (n,)
    assert out["trig"].dtype == np.bool_ and out["trig"].shape == (n,)
    assert out["volc"].dtype == np.bool_ and out["volc"].shape == (n,)
    assert out["zone"].dtype == np.int8 and out["zone"].shape == (n,)
    assert set(np.unique(out["zone"]).tolist()) <= {-1, 0, 1}
    assert np.all(out["chart_t"] % (chart_tf * MS_PER_MIN) == 0) and np.all(np.diff(out["chart_t"]) > 0)


def _self_test(argv):
    t_start = _time.time()
    _check_builtins()
    _check_other_na_reading()
    _check_bars_and_merge()
    _check_gate_by_hand()
    print("unit checks passed (built-ins, bars, request.security merge rules, hand-made gates)")

    m1 = _synthetic_m1(30000, 20261126)
    m1_gaps = _synthetic_m1(30000, 20261126, gaps=True)
    variants = (
        ("file defaults, tfs=(1,5,15,60)",
         dict(tfs=(1, 5, 15, 60))),
        ("entry level, band 0, burst gate, zones (1,5,60), min aligned 1, drift, against off",
         dict(tfs=(1, 5, 15, 60), lv_mode="entry", band=0.0, use_burst=True, burst_atr=0.3, zones=(1, 5, 60),
              min_aligned=1, use_drift=True, drift_bars=30, against=False, conf=2, parent_tf=5)),
        ("zones off, any combo off (burst only), band 0.25, parent 240",
         dict(tfs=(5, 15), use_zones=False, any_combo=False, burst_atr=1.0, band=0.25, parent_tf=240,
              zones=(), high=55.0, low=35.0)),
    )
    print("synthetic random walk: %d one-minute bars, chart_tf = 5" % m1["t"].shape[0])
    for label, over in variants:
        print("-- %s" % label)
        for f_tf in (1, 5, 60):
            p = dict(over, f_tf=f_tf)
            out = reference_signals(m1, 5, p)
            _check_output(out, m1, 5)
            d = reference_details(m1, 5, p)
            _check_arm_in_force(d, 5)
            assert all(np.array_equal(out[key], d[key]) for key in ("chart_t", "trig", "volc", "zone"))
            assert all(d["fragile"][key].dtype == np.bool_ and d["fragile"][key].shape == out[key].shape
                       for key in ("trig", "volc", "zone"))
            print("   f_tf=%-3d %s" % (f_tf, _counts(out)))
    # other chart timeframes and a series with missing minutes: shapes and the arm cross-check
    for chart_tf in (1, 15, 60, 240):
        for f_tf in (1, 15, 60, 240):
            for series in (m1, m1_gaps):
                p = dict(tfs=(1, 5, 15, 30, 60, 240, 1440), f_tf=f_tf, parent_tf=f_tf,
                         zones=(f_tf, min(2 * f_tf, 1440)), norm=50, slow=30)
                d = reference_details(series, chart_tf, p)
                _check_output(d, series, chart_tf)
                _check_arm_in_force(d, chart_tf)
    # a lower zone timeframe that does not divide the filter timeframe, "Chart" filter, no AMVI timeframe
    out = reference_signals(m1_gaps, 5, dict(f_tf=None, parent_tf=2, zones=(2, 1, 3), tfs=()))
    _check_output(out, m1_gaps, 5)
    assert not out["trig"].any() and not out["volc"].any()
    print("cross-checks passed (chart_tf 1/15/60/240 x f_tf 1/15/60/240, with and without missing minutes)")
    changed, flagged = _check_fragile_mask()
    print("fragile mask: another rounding of rma / sma changed %d zone bars on a flat-ish series, "
          "all among the %d flagged" % (changed, flagged))
    deep = "--deep" in argv
    done = _check_against_scalar(9000 if deep else 2500, (1, 5, 15, 60) if deep else (5,),
                                 (1, 5, 15, 60, 240) if deep else (1, 5, 60), deep)
    print("bar-by-bar scalar simulation == vectorised reference on %d runs%s" % (
        done, "" if deep else " (--deep for the wide set)"))
    print("self-test OK in %.1f s" % (_time.time() - t_start))

    if "--bench" in argv:
        big = _synthetic_m1(130000, 1)
        for chart_tf, f_tf in ((1, 1), (5, 1), (15, 60), (60, 240)):
            t0 = _time.time()
            out = reference_signals(big, chart_tf, dict(tfs=AMVI_TFS, f_tf=f_tf, zones=(1, 2, 60, 120, 240, 480)))
            print("bench 130000 bars chart_tf=%-3d f_tf=%-3d %.2f s  %s" % (
                chart_tf, f_tf, _time.time() - t0, _counts(out)))


if __name__ == "__main__":
    _self_test(sys.argv[1:])
