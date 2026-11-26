"""GVLiveV2 | Crypto Polymarket Any-Chart Pre-Candle [Update 1] + FlashGold Direction Filter:
CANONICAL Python replica (key gvl; stage 3 of REPLICA_SPEC.md, brief SPEC_gvl.md).

Implementation A (gvl_a.py) after reconciliation with the independent implementation B (gvl_b.py): the two
agree on every trade and every summary field of every compared case (reconcile_gvl.md), plus the 1-minute
"Bar Magnifier" path. Ground truth: /home/user/master/GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine (HEAD,
Update 1); Lnnn below are its line numbers. Interpretations and limits: gvl_notes.md.

    prepare(pair, chart_tf, params=None) -> P     series, radar, arms, EMA-cross signals, clocks / gates,
                                                  filter permissions (nothing that depends on a position)
    simulate(P, x=None, full=False, sub=None) -> R  broker + the script's close run, in numba
    trades(P, R) -> DataFrame
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)

x: the ORDER / EXIT inputs by Pine name (SPEC_gvl 3.2) plus the replica controls
    path    'tv'  one intrabar path per chart bar (TradingView without Bar Magnifier; SPEC_AH rule 4)
            'mag' the bracket (stop, target, trailing stop) and the pending pre-candle price orders (buy / sell
                  stop; inverted: sell / buy limit) walk the 1-minute sub-bars of the chart bar in time order
                  (rows of data/<PAIR>_1.parquet with t_open in [t_open, t_close) of the chart bar), each
                  sub-bar with its own rule-4 path, the gap test at every sub-bar open, the trailing state and
                  the order slots carrying over. Market orders, strategy.close and the script's run stay on the
                  chart bar (open / close). Chart "1": mag == tv.
    cost    'tv' (the strategy() call: commission 0, slippage 0), 'ours', 'stress'
    inv     alias of gvInv (Update 1)
    tvMargin  0 = TradingView's margin rule not modelled (default); m > 0: an entry is refused when
              qty x fill price x m / 100 > cash

History only: one script run per chart bar at its close (assumption G1: the extra runs that
calc_on_order_fills adds after each fill change nothing; same-bar exit yes, same-bar re-entry never);
process_orders_on_close=false, so a market order of bar j fills at the open of j+1 and a price order is live
from j+1 on; the bracket of strategy.exit is in ticks from the fill and is live from the fill, on the fill
bar too. fgfOn defaults to False (L256).
"""
import math
import os
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402  (the verified direction filter; never reimplemented here)

DATA = os.path.join(W, 'data')
MINTICK = 0.01                 # syminfo.mintick, both pairs
POINTVALUE = 1.0               # syminfo.pointvalue, both pairs (P/L); the script's own pointValue is a sizing input
INITIAL_CAPITAL = 100000.0     # strategy(initial_capital=100000)
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

KINDS = ['', 'sl', 'tp', 'trail', 'reverse', 'time', 'maxbars', 'daily_lock', 'eod', 'end']
K_SL, K_TP, K_TRAIL, K_REV, K_TIME, K_MAXBARS, K_LOCK, K_EOD, K_END = 1, 2, 3, 4, 5, 6, 7, 8, 9

# per fill, per unit: (fixed $, fraction of the fill value)  [= hrd.COSTS; 'tv': commission 0, slippage 0]
COSTS = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}

# ----------------------------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------------------------
SIGNAL_DEFAULTS = dict(
    # Volatility Filter (DEVMA) L140-142
    devLen=30, fastVoVixLen=10, slowVoVixLen=30,
    # Directional Trend L148-150
    fastEmaLen=8, slowEmaLen=21, trendFilterLen=100,
    # Momentum Filter L156-159
    useRsiFilter=True, rsiLen=14, rsiOverbought=70, rsiOversold=30,
    # Polymarket Paper Router L206-213 (the part that gates entries)
    requiredSignalTimeframe='240', allowAnyChartTimeframe=True, maxSignalSecondsAfterWindowStart=90,
    allowWeekendEntries=True,
    # Pre-Candle Early Confirmation L216-231
    usePreCandleArm=True, radarTimeframeMode='Chart', preMinScore=60, preMinVolScore=35.0, preMinVolRise=1.0,
    preCloseLocation=0.65, preUseTrend=True, preUseEmaSlope=False, preUseRvol=False, preRvolLength=20,
    preMinRvol=1.10, preUseBodyAtr=False, preMinBodyAtr=0.20, preUseMicroBreak=False, preBreakoutLookback=2,
    # New York Session L244-248
    useSessionFilter=False, tradePreset='Balanced', entry_session='0945-1530',
    morning_entry_session='0945-1115', flat_session='0930-1545',
    # replica controls
    start=None, end=None, risingRule='any',
)
ORDER_DEFAULTS = dict(
    preCandleEntryMode='Market Next Candle', preStopAtrBuffer=0.03, preCancelAfterBars=2,
    oneSignalPerPolyWindow=True,
    # S2. Exits L169-180
    ExitMode='ATR', slPoints=16500.0, tpPoints=82500.0, atrLen=14, slAtrMult=1.0, tpR=5.0, useTrail=False,
    trailActPoints=99000.0, trailPoints=16500.0, trailActAtr=6.0, trailDstAtr=1.0, maxBarsHeld=0,
    # S3. Sizing L183-189, point value L165-166
    QtyMode='Risk %', fixedQty=10.0, riskPct=1.0, maxQty=50.0, qtyStep=0.001, capMargin=True, marginPct=1.0,
    brokerPreset='Manual / custom', manualPointValue=1.0,
    # Paper Safety Layer L193-199
    useMaxBarsExit=False, maxBarsInTrade=1, useDailyLossLock=True, maxDailyLossCurrency=0.0, maxDailyLosses=3,
    useMaxStopDistance=False, maxStopDistancePoints=8.0,
    # Update 1 L835 (alias inv)
    gvInv=False, inv=False,
    # replica controls
    path='tv', cost='tv', tvMargin=0.0,
)
FGF_DEFAULTS = dict(fgf.DEFAULTS)
FGF_DEFAULTS['fgfOn'] = False          # L256: the filter is OFF by default in this file
DEFAULTS = dict(SIGNAL_DEFAULTS)
DEFAULTS.update(FGF_DEFAULTS)
DEFAULTS.update(ORDER_DEFAULTS)

SIGNAL_KEYS = set(SIGNAL_DEFAULTS) | set(FGF_DEFAULTS)
ORDER_KEYS = set(ORDER_DEFAULTS)
# drawing / alerts / JSON only: accepted, no effect (SPEC 3.3, 3.4)
IGNORED_KEYS = {
    'riskPercent', 'maxLiveSpreadPoints', 'routerStrategyName', 'seriesSlug', 'routerTimeframe', 'paperStakeUsd',
    'sendEntryAlertsToWebhook', 'sendExitAlertsToWebhook', 'showPreDebug', 'collectTrainingData',
    'includeTrainingDataInAlerts', 'plotTrainingData', 'showTrainingLabels', 'trainingLabelHistory',
    'fgfShowBg', 'fgfShowLv', 'fgfSigMark', 'fgfShowTbl', 'fgfTblPos', 'fgsShow', 'fgsWin', 'fgsH',
    'FGF_FORCE_OVERLAY',
}
_OPTIONS = {
    'preCandleEntryMode': ('Signal Only', 'Market Next Candle', 'Stop Next Candle'),
    'radarTimeframeMode': ('Auto', 'Chart', '1', '3', '5', '15', '30', '60', '120', '240'),
    'ExitMode': ('Points', 'ATR'),
    'QtyMode': ('Fixed', 'Risk %'),
    'brokerPreset': ('Manual / custom', 'Crypto 1 USD per qty'),
    'tradePreset': ('Aggressive', 'Balanced', 'Conservative AM', 'Custom'),
    'risingRule': ('any', 'mono'),
    'path': ('tv', 'mag'),
    'cost': ('tv', 'ours', 'stress'),
}
_BOOLS = ('useRsiFilter', 'allowAnyChartTimeframe', 'allowWeekendEntries', 'usePreCandleArm', 'preUseTrend',
          'preUseEmaSlope', 'preUseRvol', 'preUseBodyAtr', 'preUseMicroBreak', 'useSessionFilter',
          'oneSignalPerPolyWindow', 'useTrail', 'capMargin', 'useMaxBarsExit', 'useDailyLossLock',
          'useMaxStopDistance', 'gvInv', 'inv', 'fgfOn')
_INTS = ('devLen', 'fastVoVixLen', 'slowVoVixLen', 'fastEmaLen', 'slowEmaLen', 'trendFilterLen', 'rsiLen',
         'rsiOverbought', 'rsiOversold', 'maxSignalSecondsAfterWindowStart', 'preMinScore', 'preRvolLength',
         'preBreakoutLookback', 'preCancelAfterBars', 'atrLen', 'maxBarsHeld', 'maxBarsInTrade', 'maxDailyLosses')
_FLOATS = ('preMinVolScore', 'preMinVolRise', 'preCloseLocation', 'preMinRvol', 'preMinBodyAtr',
           'preStopAtrBuffer', 'slPoints', 'tpPoints', 'slAtrMult', 'tpR', 'trailActPoints', 'trailPoints',
           'trailActAtr', 'trailDstAtr', 'fixedQty', 'riskPct', 'maxQty', 'qtyStep', 'marginPct',
           'manualPointValue', 'maxDailyLossCurrency', 'maxStopDistancePoints', 'tvMargin')
# lengths a Pine ta.* call needs >= 1 (ta.ema / ta.rsi / ta.atr / ta.sma / ta.stdev / ta.highest raise below 1)
_LENGTHS = ('devLen', 'fastVoVixLen', 'slowVoVixLen', 'fastEmaLen', 'slowEmaLen', 'trendFilterLen', 'rsiLen',
            'preRvolLength', 'preBreakoutLookback', 'atrLen')


def _check(Q):
    for k, opts in _OPTIONS.items():
        if Q[k] not in opts:
            raise ValueError('%s=%r is not one of %r' % (k, Q[k], opts))
    for k in _INTS:
        v = Q[k]
        if isinstance(v, bool) or int(v) != v:
            raise ValueError('%s=%r must be an integer' % (k, v))
        if v < 0:
            raise ValueError('%s=%r must be >= 0' % (k, v))
    for k in _FLOATS:
        v = float(Q[k])
        if not (v >= 0.0) or math.isinf(v):
            raise ValueError('%s=%r must be a finite number >= 0' % (k, Q[k]))
    for k in _LENGTHS:
        if Q[k] < 1:
            raise ValueError('%s=%r must be >= 1' % (k, Q[k]))
    if not (1 <= Q['preCancelAfterBars'] <= 10):
        raise ValueError('preCancelAfterBars must be 1..10')
    if Q['maxDailyLosses'] < 1:
        raise ValueError('maxDailyLosses must be >= 1')
    if Q['maxBarsInTrade'] < 1:
        raise ValueError('maxBarsInTrade must be >= 1')
    if float(Q['slAtrMult']) < 0.01:
        raise ValueError('slAtrMult must be >= 0.01')
    if not (0.50 <= float(Q['preCloseLocation']) <= 0.95):
        raise ValueError('preCloseLocation must be 0.50..0.95')
    if not (0 <= Q['maxSignalSecondsAfterWindowStart'] <= 299):
        raise ValueError('maxSignalSecondsAfterWindowStart must be 0..299')
    for k in ('entry_session', 'morning_entry_session', 'flat_session'):
        _parse_session(Q[k])


def _resolve_inv(given, cur):
    """gvInv with its alias inv: raise if both are given and disagree."""
    a = given.get('gvInv')
    b = given.get('inv')
    if a is not None and b is not None and bool(a) != bool(b):
        raise ValueError('gvInv and inv are both given and disagree')
    if a is not None:
        return bool(a)
    if b is not None:
        return bool(b)
    return bool(cur)


def _params(params):
    Q = dict(DEFAULTS)
    given = dict(params or {})
    for k, v in given.items():
        if k in IGNORED_KEYS:
            continue
        if k not in DEFAULTS:
            raise ValueError('unknown param %r' % (k,))
        Q[k] = v
    Q['gvInv'] = Q['inv'] = _resolve_inv(given, False)
    for k in _BOOLS:
        Q[k] = bool(Q[k])
    _check(Q)
    return Q


# ----------------------------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------------------------
_BARS = {}
_VOL = {}


def load_bars(pair, tf):
    """open high low close (float64), t_open t_close (int64 s) of data/<pair>_<tf>.parquet; a minute timeframe
    without a file (e.g. "3") is built from the 1-minute file as build_bars.py does (fgf._bars)."""
    tf = str(tf)
    key = (pair, tf)
    if key not in _BARS:
        f = os.path.join(DATA, '%s_%s.parquet' % (pair, tf))
        if os.path.exists(f):
            t = pq.read_table(f, columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
            d = {}
            for c in ('open', 'high', 'low', 'close'):
                d[c] = np.ascontiguousarray(t.column(c).to_numpy(), dtype=np.float64)
            for c in ('t_open', 't_close'):
                d[c] = np.ascontiguousarray(t.column(c).to_numpy(), dtype=np.int64)
        else:
            b = fgf._bars(pair, tf)
            if b is None:
                raise ValueError('no data for timeframe %r (seconds charts cannot be reproduced)' % (tf,))
            d = {c: np.ascontiguousarray(b[c]) for c in ('open', 'high', 'low', 'close', 't_open', 't_close')}
        _BARS[key] = d
    return _BARS[key]


def load_volume(pair, tf):
    """volume of the same rows (BTC: Bitstamp volume; XAU: tick count). Built timeframes: the sum of the
    1-minute volumes over the same groups."""
    tf = str(tf)
    key = (pair, tf)
    if key not in _VOL:
        f = os.path.join(DATA, '%s_%s_vol.parquet' % (pair, tf))
        b = load_bars(pair, tf)
        if os.path.exists(f):
            v = np.ascontiguousarray(pq.read_table(f, columns=['volume']).column('volume').to_numpy(),
                                     dtype=np.float64)
        else:
            m = load_bars(pair, '1')
            mv = load_volume(pair, '1')
            g = np.searchsorted(b['t_open'], m['t_open'], side='right') - 1
            if g.min() < 0:
                raise ValueError('1-minute bars before the first built bar')
            st = np.concatenate([[0], np.flatnonzero(np.diff(g) != 0) + 1])
            if len(st) != len(b['open']):
                raise ValueError('built bars and 1-minute groups do not match')
            v = np.add.reduceat(mv, st)
        if len(v) != len(b['open']):
            raise ValueError('volume rows do not match the bars of %s %s' % (pair, tf))
        _VOL[key] = v
    return _VOL[key]


# ----------------------------------------------------------------------------------------------
# Pine built-ins (formulas of SPEC_gvl section 4, to the letter)
# ----------------------------------------------------------------------------------------------
@njit(cache=True)
def _atr(high, low, close, length):
    """ta.atr(length) = ta.rma(ta.tr(true), length); na before row length-1."""
    n = close.shape[0]
    out = np.full(n, np.nan)
    tr = np.empty(n)
    for i in range(n):
        hl = high[i] - low[i]
        if i == 0:
            tr[i] = hl
        else:
            tr[i] = max(max(hl, abs(high[i] - close[i - 1])), abs(low[i] - close[i - 1]))
    if n >= length:
        s = 0.0
        for i in range(length):
            s += tr[i]
        v = s / length
        out[length - 1] = v
        alpha = 1.0 / length
        for i in range(length, n):
            v = alpha * tr[i] + (1.0 - alpha) * v
            out[i] = v
    return out


@njit(cache=True)
def _ema(x, length):
    """ta.ema: alpha = 2 / (n + 1), seeded with the first value."""
    n = x.shape[0]
    out = np.empty(n)
    if n == 0:
        return out
    alpha = 2.0 / (length + 1)
    out[0] = x[0]
    for i in range(1, n):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return out


@njit(cache=True)
def _rsi(close, length):
    """ta.rsi: Wilder RMA of the gains / losses, each seeded with the plain mean of rows 1..n."""
    n = close.shape[0]
    out = np.full(n, np.nan)
    if n <= length:
        return out
    su = 0.0
    sd = 0.0
    for i in range(1, length + 1):
        ch = close[i] - close[i - 1]
        su += max(ch, 0.0)
        sd += max(-ch, 0.0)
    u = su / length
    d = sd / length
    alpha = 1.0 / length
    for i in range(length, n):
        if i > length:
            ch = close[i] - close[i - 1]
            u = alpha * max(ch, 0.0) + (1.0 - alpha) * u
            d = alpha * max(-ch, 0.0) + (1.0 - alpha) * d
        if d == 0.0:
            out[i] = 100.0
        elif u == 0.0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + u / d)
    return out


@njit(cache=True)
def _sma(x, length):
    """ta.sma: a fresh sum per row, oldest to newest; na if any term is na."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        s = 0.0
        for k in range(i - length + 1, i + 1):
            s += x[k]
        out[i] = s / length
    return out


@njit(cache=True)
def _stdev(x, length):
    """ta.stdev (population): sqrt(sum((x - mean)^2) / n) over the same rows, oldest to newest."""
    n = x.shape[0]
    out = np.full(n, np.nan)
    for i in range(length - 1, n):
        s = 0.0
        for k in range(i - length + 1, i + 1):
            s += x[k]
        m = s / length
        q = 0.0
        for k in range(i - length + 1, i + 1):
            dv = x[k] - m
            q += dv * dv
        out[i] = math.sqrt(q / length)
    return out


@njit(cache=True)
def _prev_extremes(high, low, length):
    """ta.highest(high[1], n) and ta.lowest(low[1], n): max(high[i-n .. i-1]), min(low[i-n .. i-1])."""
    n = high.shape[0]
    hh = np.full(n, np.nan)
    ll = np.full(n, np.nan)
    for i in range(length, n):
        a = high[i - length]
        b = low[i - length]
        for k in range(i - length + 1, i):
            if high[k] > a:
                a = high[k]
            if low[k] < b:
                b = low[k]
        hh[i] = a
        ll[i] = b
    return hh, ll


@njit(cache=True)
def _vol_score(fa, sa):
    """f_vol_score (L848-852): clamp((fastAtr / slowAtr - 0.5) / 1.5 * 100, 0, 100); ratio 1.0 unless slowAtr > 0."""
    n = fa.shape[0]
    out = np.empty(n)
    for i in range(n):
        if sa[i] > 0:
            r = fa[i] / sa[i]
        else:
            r = 1.0
        v = (r - 0.50) / 1.50 * 100.0
        if v != v:
            out[i] = np.nan
        else:
            out[i] = max(0.0, min(100.0, v))
    return out


@njit(cache=True)
def _expansion(fd, sd, mono):
    """expansion_regime (L880) = fastDEVMA > slowDEVMA or ta.rising(fastDEVMA, 2).
    rising 'any' (G15): x > x[1] and x > x[2]; 'mono': x > x[1] and x[1] > x[2]."""
    n = fd.shape[0]
    out = np.zeros(n, np.bool_)
    for i in range(n):
        r = fd[i] > sd[i]
        if not r and i >= 2:
            if mono:
                r = fd[i] > fd[i - 1] and fd[i - 1] > fd[i - 2]
            else:
                r = fd[i] > fd[i - 1] and fd[i] > fd[i - 2]
        out[i] = r
    return out


# full-file series. Only the ATRs (shared by the vol score, the DEVMA chain, body / ATR and the exits) and the
# boolean expansion_regime (the slow one) are kept per (pair, tf, name, params); everything else is cached as
# window slices by prepare() (_WIN), which keeps a 1-minute chart well under the memory limit.
_SER = {}
_SER_KEEP = ('atr', 'expansion')


def _series(pair, tf, name, *a):
    key = (pair, str(tf), name) + a
    if key in _SER:
        return _SER[key]
    b = load_bars(pair, tf)
    if name == 'atr':
        v = _atr(b['high'], b['low'], b['close'], int(a[0]))
    elif name == 'ema':
        v = _ema(b['close'], int(a[0]))
    elif name == 'rsi':
        v = _rsi(b['close'], int(a[0]))
    elif name == 'volscore':                       # f_vol_score(), (fastVoVixLen, slowVoVixLen)
        v = _vol_score(_series(pair, tf, 'atr', a[0]), _series(pair, tf, 'atr', a[1]))
    elif name == 'expansion':                      # (devLen, fast, slow, risingRule)
        dev_len, fast, slow, rule = a
        fa = _series(pair, tf, 'atr', fast)
        sa = _series(pair, tf, 'atr', slow)
        vsrc = (fa - sa) / (_stdev(fa, dev_len) + 1e-6)          # f_vovix_source() L843
        dev = _stdev(vsrc, dev_len)                              # L877
        v = _expansion(_sma(dev, fast), _sma(dev, slow), rule == 'mono')   # L878-880
    elif name == 'slope':                          # f_ema_slope(n): e - nz(e[1], e)
        e = _series(pair, tf, 'ema', a[0])
        v = np.empty(len(e))
        v[0] = 0.0
        v[1:] = e[1:] - e[:-1]
    elif name == 'rvol':                           # f_rvol(n)
        vol = load_volume(pair, tf)
        avg = _sma(vol, int(a[0]))
        with np.errstate(invalid='ignore', divide='ignore'):
            v = np.where(np.isnan(vol) | np.isnan(avg) | ~(avg > 0), 1.0, vol / np.where(avg > 0, avg, 1.0))
    elif name == 'bodyatr':                        # f_body_atr()
        at = _series(pair, tf, 'atr', 14)
        with np.errstate(invalid='ignore', divide='ignore'):
            v = np.where(at > 0, np.abs(b['close'] - b['open']) / np.where(at > 0, at, 1.0), 0.0)
    elif name == 'break':                          # f_break_long / f_break_short (lookback) -> 2 x bool
        hh, ll = _prev_extremes(b['high'], b['low'], int(a[0]))
        with np.errstate(invalid='ignore'):
            v = (b['close'] > hh, b['close'] < ll)
    else:
        raise KeyError(name)
    if name in _SER_KEEP:
        _SER[key] = v
    return v


def clear_cache():
    for d in (_BARS, _VOL, _SER, _WIN, _PERM, _SUB):
        d.clear()


# ----------------------------------------------------------------------------------------------
# clocks
# ----------------------------------------------------------------------------------------------
def _parse_session(s):
    """'HHMM-HHMM' (optionally ':1234567', TradingView days 1 = Sunday) -> (start, end, days or None)."""
    s = str(s).strip()
    days = None
    if ':' in s:
        s, dd = s.split(':', 1)
        days = frozenset(int(ch) for ch in dd.strip())
        if not days or not days <= frozenset(range(1, 8)):
            raise ValueError('bad session days %r' % (dd,))
    parts = s.split('-')
    if len(parts) != 2 or any(len(p) != 4 or not p.isdigit() for p in parts):
        raise ValueError('bad session %r' % (s,))
    a, b = int(parts[0]), int(parts[1])
    for v in (a, b):
        if v // 100 > 24 or v % 100 > 59:
            raise ValueError('bad session %r' % (s,))
    return a, b, days


def _in_session(hhmm, tvday, sess):
    """G17: time(timeframe.period, session, "America/New_York") is not na iff the bar's OPEN (New York
    HHMM) is in [start, end); start > end wraps midnight; start == end is the whole day."""
    a, b, days = _parse_session(sess)
    if a < b:
        r = (hhmm >= a) & (hhmm < b)
    elif a > b:
        r = (hhmm >= a) | (hhmm < b)
    else:
        r = np.ones(len(hhmm), bool)
    if days is not None:
        r = r & np.isin(tvday, np.array(sorted(days)))
    return r


# ----------------------------------------------------------------------------------------------
# prepare
# ----------------------------------------------------------------------------------------------
_WIN = {}     # window-level derived arrays, keyed (pair, tf, w0, w1, tag, params...)
_PERM = {}    # filter permissions


def _win(pair, tf, w0, w1, tag, key, fn):
    k = (pair, tf, w0, w1, tag) + key
    v = _WIN.get(k)
    if v is None:
        v = fn()
        _WIN[k] = v
    return v


def tf_seconds(tf):
    return int(fgf.tf_seconds(tf))


def radar_timeframe(chart_tf, mode):
    """(radarTimeframe, useRadarTimeframe) of L854-856, L895-899."""
    chart_tf = str(chart_tf)
    cs = tf_seconds(chart_tf)
    if mode == 'Auto':
        rtf = ('60' if cs >= 86400 else '15' if cs >= 14400 else '5' if cs >= 3600 else '3' if cs >= 1800
               else '1' if cs >= 900 else chart_tf)
    elif mode == 'Chart':
        rtf = chart_tf
    else:
        rtf = str(mode)
    use = (rtf != chart_tf) and (tf_seconds(rtf) < cs)
    return rtf, use


def _radar(pair, chart_tf, rtf, use, w0, w1, name, *a):
    """A radar function on the window's chart bars: the chart's own series, or (use) the value of the last
    radar-timeframe bar with t_close <= the chart bar's t_close (G16), na / false if none."""
    if not use:
        v = _series(pair, chart_tf, name, *a)
        if name == 'break':
            return v[0][w0:w1], v[1][w0:w1]
        return v[w0:w1]
    rb = load_bars(pair, rtf)
    cb = load_bars(pair, chart_tf)
    j = np.searchsorted(rb['t_close'], cb['t_close'][w0:w1], side='right') - 1
    v = _series(pair, rtf, name, *a)
    jj = np.maximum(j, 0)
    if name == 'break':
        return (v[0][jj] & (j >= 0)), (v[1][jj] & (j >= 0))
    out = np.asarray(v, np.float64)[jj]
    out[j < 0] = np.nan
    return out


def _vol_pair(pair, chart_tf, rtf, use, w0, w1, fast, slow):
    """radarVolScore and radarVolRise (L908, L914) on the window bars; [1] = the previous CHART bar."""
    lo = max(w0 - 1, 0)
    sc = _radar(pair, chart_tf, rtf, use, lo, w1, 'volscore', fast, slow)
    prev = np.empty(len(sc))
    prev[0] = np.nan
    prev[1:] = sc[:-1]
    prev = np.where(np.isnan(prev), sc, prev)            # nz(radarVolScore[1], radarVolScore)
    rise = sc - prev
    k = w0 - lo
    return np.ascontiguousarray(sc[k:]), np.ascontiguousarray(rise[k:])


def _clock(pair, tf, w0, w1):
    b = load_bars(pair, tf)
    to = b['t_open'][w0:w1]
    idx = pd.to_datetime(to, unit='s', utc=True).tz_convert('America/New_York')
    hhmm = np.asarray(idx.hour, np.int64) * 100 + np.asarray(idx.minute, np.int64)
    dow = np.asarray(idx.dayofweek, np.int64)                    # Monday = 0
    tvday = (dow + 1) % 7 + 1                                    # TradingView: Sunday = 1 ... Saturday = 7
    day = (np.asarray(idx.year, np.int64) * 10000 + np.asarray(idx.month, np.int64) * 100
           + np.asarray(idx.day, np.int64))                      # ny_day_key L1176
    tms = to * 1000                                              # `time`, ms
    win = tms - (tms % 300000)                                   # polyWindowStartMs L973
    secs = (tms - win) // 1000                                   # secondsFromPolyWindowStart L974
    return dict(hhmm=hhmm, dow=dow, tvday=tvday, day=np.ascontiguousarray(day), win=np.ascontiguousarray(win),
                secs=secs)


def permissions(pair, chart_tf, start, end, fgfp):
    key = (pair, str(chart_tf), int(start), int(end), tuple(sorted((k, str(v)) for k, v in fgfp.items())))
    if key not in _PERM:
        df = fgf.fgf_permissions(pair, str(chart_tf), int(start), int(end), fgfp)
        _PERM[key] = (int(df.index[0]) if len(df) else -1, len(df),
                      np.ascontiguousarray(df['buyOk'].to_numpy(bool)),
                      np.ascontiguousarray(df['sellOk'].to_numpy(bool)))
    return _PERM[key]


def prepare(pair, chart_tf, params=None, _perm=None):
    """Everything that does not depend on the ORDER / EXIT inputs. ORDER / EXIT keys given here are kept as
    the defaults of simulate(P). _perm = (buyOk, sellOk) injects permissions instead of the filter's (tests)."""
    Q = _params(params)
    tf = str(chart_tf)
    b = load_bars(pair, tf)
    s0, e0 = WINDOWS[pair]
    start = int(Q['start']) if Q['start'] is not None else s0
    end = int(Q['end']) if Q['end'] is not None else e0
    w0 = int(np.searchsorted(b['t_close'], start, side='left'))
    w1 = int(np.searchsorted(b['t_close'], end, side='right'))
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    sl = slice(w0, w1)
    close = b['close']

    # --- chart series (L840-893, 916-917, 938-939)
    def _cloc():
        rng = b['high'][sl] - b['low'][sl]
        with np.errstate(invalid='ignore', divide='ignore'):
            return np.where(rng > 0, (b['close'][sl] - b['low'][sl]) / np.where(rng > 0, rng, 1.0), 0.50)
    cloc = _win(pair, tf, w0, w1, 'cloc', (), _cloc)

    tlen = int(Q['trendFilterLen'])

    def _trend():
        te = _series(pair, tf, 'ema', tlen)[sl]
        c = close[sl]
        return np.ascontiguousarray(c > te), np.ascontiguousarray(c < te)
    up_trend, down_trend = _win(pair, tf, w0, w1, 'trend', (tlen,), _trend)

    fe, se = int(Q['fastEmaLen']), int(Q['slowEmaLen'])
    dev_len, fast, slow = int(Q['devLen']), int(Q['fastVoVixLen']), int(Q['slowVoVixLen'])
    use_rsi, rsi_len = Q['useRsiFilter'], int(Q['rsiLen'])
    ob, osd = Q['rsiOverbought'], Q['rsiOversold']
    rule = Q['risingRule']

    def _cross():
        f = _series(pair, tf, 'ema', fe)
        s = _series(pair, tf, 'ema', se)
        lo = max(w0 - 1, 0)
        fa, sa = f[lo:w1], s[lo:w1]
        bull = np.zeros(len(fa), bool)
        bear = np.zeros(len(fa), bool)
        bull[1:] = (fa[1:] > sa[1:]) & (fa[:-1] <= sa[:-1])     # ta.crossover
        bear[1:] = (fa[1:] < sa[1:]) & (fa[:-1] >= sa[:-1])     # ta.crossunder
        k = w0 - lo
        return bull[k:], bear[k:]

    def _signals():
        bull, bear = _win(pair, tf, w0, w1, 'cross', (fe, se), _cross)
        ex = _win(pair, tf, w0, w1, 'exp', (dev_len, fast, slow, rule),
                  lambda: _series(pair, tf, 'expansion', dev_len, fast, slow, rule)[sl].copy())
        if use_rsi:
            r = _win(pair, tf, w0, w1, 'rsi', (rsi_len,), lambda: _series(pair, tf, 'rsi', rsi_len)[sl].copy())
            with np.errstate(invalid='ignore'):
                rl = r < ob                                      # rsiLongCondition (na -> false)
                rs = r > osd
        else:
            rl = rs = True
        return (np.ascontiguousarray(bull & up_trend & ex & rl),          # longCondition L938
                np.ascontiguousarray(bear & down_trend & ex & rs))        # shortCondition L939
    sigL, sigS = _win(pair, tf, w0, w1, 'sig', (fe, se, tlen, dev_len, fast, slow, rule, use_rsi, rsi_len, ob, osd),
                      _signals)

    # --- radar (L895-914) and arms (L919-934, L1228-1229)
    rtf, use_radar = radar_timeframe(tf, Q['radarTimeframeMode'])
    rkey = (rtf, use_radar)
    vsc, vrise = _win(pair, tf, w0, w1, 'vol', rkey + (fast, slow),
                      lambda: _vol_pair(pair, tf, rtf, use_radar, w0, w1, fast, slow))
    with np.errstate(invalid='ignore'):
        pre_vol_ok = (vsc >= float(Q['preMinVolScore'])) & (vrise >= float(Q['preMinVolRise']))
    T = True
    if Q['preUseRvol']:
        rv = _win(pair, tf, w0, w1, 'rvol', rkey + (int(Q['preRvolLength']),),
                  lambda: _radar(pair, tf, rtf, use_radar, w0, w1, 'rvol', int(Q['preRvolLength'])))
        with np.errstate(invalid='ignore'):
            pre_rvol_ok = rv >= float(Q['preMinRvol'])
    else:
        pre_rvol_ok = T
    if Q['preUseBodyAtr']:
        ba = _win(pair, tf, w0, w1, 'bodyatr', rkey, lambda: _radar(pair, tf, rtf, use_radar, w0, w1, 'bodyatr'))
        with np.errstate(invalid='ignore'):
            pre_body_ok = ba >= float(Q['preMinBodyAtr'])
    else:
        pre_body_ok = T
    l_trend = up_trend if Q['preUseTrend'] else T
    s_trend = down_trend if Q['preUseTrend'] else T
    if Q['preUseEmaSlope']:
        slp = _win(pair, tf, w0, w1, 'slope', rkey + (fe,),
                   lambda: _radar(pair, tf, rtf, use_radar, w0, w1, 'slope', fe))
        with np.errstate(invalid='ignore'):
            l_slope = slp > 0
            s_slope = slp < 0
    else:
        l_slope = s_slope = T
    pcl = float(Q['preCloseLocation'])
    l_press = cloc >= pcl
    s_press = cloc <= 1.0 - pcl
    if Q['preUseMicroBreak']:
        l_break, s_break = _win(pair, tf, w0, w1, 'break', rkey + (int(Q['preBreakoutLookback']),),
                                lambda: _radar(pair, tf, rtf, use_radar, w0, w1, 'break',
                                               int(Q['preBreakoutLookback'])))
    else:
        l_break = s_break = T

    def _i(x):
        return x.astype(np.int64) if isinstance(x, np.ndarray) else int(bool(x))
    pre_long_score = (25 * _i(pre_vol_ok) + 20 * _i(l_trend) + 15 * _i(l_slope) + 10 * _i(pre_rvol_ok)
                      + 10 * _i(pre_body_ok) + 10 * _i(l_press) + 10 * _i(l_break))            # L931
    pre_short_score = (25 * _i(pre_vol_ok) + 20 * _i(s_trend) + 15 * _i(s_slope) + 10 * _i(pre_rvol_ok)
                       + 10 * _i(pre_body_ok) + 10 * _i(s_press) + 10 * _i(s_break))           # L932
    ms = int(Q['preMinScore'])
    use_arm = Q['usePreCandleArm']                      # barstate.isconfirmed is true in the close run
    pre_long_arm = (use_arm & pre_vol_ok & l_trend & l_slope & pre_rvol_ok & pre_body_ok & l_press & l_break
                    & (pre_long_score >= ms))                                                  # L933
    pre_short_arm = (use_arm & pre_vol_ok & s_trend & s_slope & pre_rvol_ok & pre_body_ok & s_press & s_break
                     & (pre_short_score >= ms))                                                # L934
    armL = np.ascontiguousarray(pre_long_arm & (pre_long_score >= pre_short_score))            # L1228
    armS = np.ascontiguousarray(pre_short_arm & (pre_short_score > pre_long_score))            # L1229

    # --- clocks and gates (L961-986)
    ck = _win(pair, tf, w0, w1, 'clock', (), lambda: _clock(pair, tf, w0, w1))
    timeframe_ok = Q['allowAnyChartTimeframe'] or tf == str(Q['requiredSignalTimeframe'])
    poly_ok = ck['secs'] <= int(Q['maxSignalSecondsAfterWindowStart'])
    weekday_ok = np.ones(n, bool) if Q['allowWeekendEntries'] else (ck['dow'] < 5)
    if Q['useSessionFilter']:
        sess = Q['morning_entry_session'] if Q['tradePreset'] == 'Conservative AM' else Q['entry_session']
        entry_ok = _in_session(ck['hhmm'], ck['tvday'], sess)
        flat_ok = _in_session(ck['hhmm'], ck['tvday'], Q['flat_session'])
        if Q['tradePreset'] == 'Balanced':
            weak = np.isin(ck['hhmm'], (1245, 1345, 1400, 1500))
        else:
            weak = np.zeros(n, bool)
    else:
        entry_ok = np.ones(n, bool)
        flat_ok = np.ones(n, bool)
        weak = np.zeros(n, bool)
    gate = np.ascontiguousarray(poly_ok & entry_ok & weekday_ok & ~weak & bool(timeframe_ok))

    # --- filter permissions
    fgfp = {k: Q[k] for k in FGF_DEFAULTS}
    if _perm is not None:
        buy_ok = np.ascontiguousarray(np.asarray(_perm[0], dtype=np.bool_))
        sell_ok = np.ascontiguousarray(np.asarray(_perm[1], dtype=np.bool_))
        if len(buy_ok) != n or len(sell_ok) != n:
            raise ValueError('injected permissions do not match the window')
    elif Q['fgfOn']:
        p0, pn, buy_ok, sell_ok = permissions(pair, tf, start, end, fgfp)
        if p0 != w0 or pn != n:
            raise RuntimeError('filter rows do not match the window')
    else:
        buy_ok = np.ones(n, np.bool_)
        sell_ok = np.ones(n, np.bool_)

    tc = b['t_close'][sl]
    mid = start + (end - start) // 2
    atr14 = _win(pair, tf, w0, w1, 'atr', (14,), lambda: np.ascontiguousarray(_series(pair, tf, 'atr', 14)[sl]))
    P = dict(pair=pair, tf=tf, start=start, end=end, mid=mid, w0=w0, w1=w1, n=n,
             mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
             rows=np.arange(w0, w1, dtype=np.int64),
             open=b['open'][sl], high=b['high'][sl], low=b['low'][sl], close=b['close'][sl],
             t_open=b['t_open'][sl], t_close=tc,
             armL=armL, armS=armS, sigL=sigL, sigS=sigS, buyOk=buy_ok, sellOk=sell_ok,
             gate=gate, flatOk=np.ascontiguousarray(flat_ok), win=ck['win'], day=ck['day'],
             atr14=atr14, atr_cache={14: atr14},
             arms_long=int(np.count_nonzero(armL)), arms_short=int(np.count_nonzero(armS)),
             sig_long=int(np.count_nonzero(sigL)), sig_short=int(np.count_nonzero(sigS)),
             gate_bars=int(np.count_nonzero(gate)),
             radar_tf=rtf, use_radar=bool(use_radar), params=Q, fgfp=fgfp, sub=None)
    return P


def exit_atr(P, length):
    """ta.atr(atrLen) on the window bars (computed on the whole file, cached per length)."""
    length = int(length)
    a = P['atr_cache'].get(length)
    if a is None:
        a = _win(P['pair'], P['tf'], P['w0'], P['w1'], 'atr', (length,),
                 lambda: np.ascontiguousarray(_series(P['pair'], P['tf'], 'atr', length)[P['w0']:P['w1']]))
        P['atr_cache'][length] = a
    return a


# ----------------------------------------------------------------------------------------------
# the 1-minute sub-bars of the chart bars (path 'mag')
# ----------------------------------------------------------------------------------------------
def sub_bars(pair, chart_tf, w0, w1, check=True):
    """The 1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close). Returns (ptr, o, h, l, c, t_open): ptr
    int64 (n + 1); the sub-bars of window bar k are the rows [ptr[k], ptr[k+1]) of the five arrays. With check,
    every chart bar has at least one sub-bar and its OHLC equals the sub-bars' first open / highest high /
    lowest low / last close (build_bars.py built the chart bars from them)."""
    b = load_bars(pair, str(chart_tf))
    m = load_bars(pair, '1')
    bo = b['t_open'][w0:w1]
    bc = b['t_close'][w0:w1]
    s = np.searchsorted(m['t_open'], bo, side='left')
    e = np.searchsorted(m['t_open'], bc, side='left')
    ln = (e - s).astype(np.int64)
    ptr = np.zeros(len(bo) + 1, np.int64)
    np.cumsum(ln, out=ptr[1:])
    if len(bo) and (ln <= 0).any():
        raise ValueError('%s %s: %d chart bars without 1-minute sub-bars' % (pair, chart_tf, int((ln <= 0).sum())))
    if len(bo) > 1 and (s[1:] < e[:-1]).any():
        raise ValueError('%s %s: chart bars share 1-minute sub-bars' % (pair, chart_tf))
    idx = np.repeat(s - ptr[:-1], ln) + np.arange(int(ptr[-1]), dtype=np.int64)
    ca = np.ascontiguousarray
    so = ca(m['open'][idx])
    sh = ca(m['high'][idx])
    sl = ca(m['low'][idx])
    sc = ca(m['close'][idx])
    st = ca(m['t_open'][idx])
    if check and len(bo):
        a = ptr[:-1]
        ok = ((so[a] == b['open'][w0:w1]) & (sc[ptr[1:] - 1] == b['close'][w0:w1])
              & (np.maximum.reduceat(sh, a) == b['high'][w0:w1])
              & (np.minimum.reduceat(sl, a) == b['low'][w0:w1]))
        if not ok.all():
            raise ValueError('%s %s: %d chart bars differ from their sub-bars' % (pair, chart_tf, int((~ok).sum())))
    return ptr, so, sh, sl, sc, st


_SUB = {}     # sub-bar tables, keyed (pair, tf, w0, w1): one per cell and window, shared by every prepare() of it


def get_sub(P):
    """The sub-bar table of P's window: built and checked once per (pair, tf, window), kept in P['sub']."""
    if P.get('sub') is None:
        key = (P['pair'], P['tf'], int(P['w0']), int(P['w1']))
        if key not in _SUB:
            _SUB[key] = sub_bars(P['pair'], P['tf'], P['w0'], P['w1'])
        P['sub'] = _SUB[key]
    return P['sub']


def fake_sub_bars(P):
    """One sub-bar per chart bar, equal to the bar (tests: 'mag' on it == 'tv' but for the exleg codes)."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), P['open'], P['high'], P['low'], P['close'], P['t_open'])


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, np.int64))


# ----------------------------------------------------------------------------------------------
# broker + script (numba)
# ----------------------------------------------------------------------------------------------
NEG = -1.0e300
POSI = 1.0e300
NA = -(1 << 62)          # na for the script's int variables

# float state
F_CASH, F_QTY, F_E, F_SL, F_TP, F_A, F_OFF, F_BEST, F_EQB, F_ECOST, F_SLD, F_LASTPNL, F_MAXNOT = range(13)
NF = 13
# int state
(I_POS, I_HSL, I_HTP, I_ARMED, I_EBAR, I_SBAR, I_EKIND, I_SIG, I_OTYPE, I_REENT, I_INH, I_AFTER, I_CAP, I_NT,
 I_NCLOSED, I_EXLEG, I_ERR, I_PFILL, I_MREF, I_MOVER) = range(20)
NI = 20
# slot ints / floats (slot 0 = id "Long", a real buy; slot 1 = id "Short", a real sell)
SI_ACT, SI_SIG, SI_TYPE, SI_TRIG, SI_KIND, SI_BAR, SI_SEQ, SI_REENT, SI_CAP = range(9)
SF_P, SF_QTY, SF_SLT, SF_TPT, SF_TRA, SF_TRD, SF_SLD = range(7)
# trade columns
(TI_DIR, TI_SIG, TI_EKIND, TI_OTYPE, TI_SBAR, TI_EBAR, TI_XBAR, TI_XKIND, TI_REENT, TI_INH, TI_AFTER,
 TI_CAP) = range(12)
TF_EPX, TF_QTY, TF_XPX, TF_GROSS, TF_COST, TF_EQB, TF_SLD, TF_SLPX, TF_TPPX = range(9)


@njit(cache=True)
def _stop_level(F, I, use_trail):
    """The stop in force of the open trade (SPEC 6.2): (exists, level, is the trailing stop)."""
    if I[I_POS] > 0:
        sv = F[F_SL] if I[I_HSL] != 0 else NEG
        ts = (F[F_BEST] - F[F_OFF]) if (use_trail and I[I_ARMED] != 0) else NEG
        if ts >= sv:
            return ts > NEG, ts, True
        return True, sv, False
    sv = F[F_SL] if I[I_HSL] != 0 else POSI
    ts = (F[F_BEST] + F[F_OFF]) if (use_trail and I[I_ARMED] != 0) else POSI
    if ts <= sv:
        return ts < POSI, ts, True
    return True, sv, False


@njit(cache=True)
def _close(F, I, TF, TI, k, px, kind, c_fix, c_pct):
    """Close the open trade at px on bar k."""
    d = I[I_POS]
    qty = F[F_QTY]
    xc = qty * (c_fix + c_pct * px)
    gross = d * qty * (px - F[F_E])
    cost = F[F_ECOST] + xc
    F[F_CASH] += gross - xc
    nt = I[I_NT]
    TI[nt, TI_DIR] = d
    TI[nt, TI_SIG] = I[I_SIG]
    TI[nt, TI_EKIND] = I[I_EKIND]
    TI[nt, TI_OTYPE] = I[I_OTYPE]
    TI[nt, TI_SBAR] = I[I_SBAR]
    TI[nt, TI_EBAR] = I[I_EBAR]
    TI[nt, TI_XBAR] = k
    TI[nt, TI_XKIND] = kind
    TI[nt, TI_REENT] = I[I_REENT]
    TI[nt, TI_INH] = I[I_INH]
    TI[nt, TI_AFTER] = I[I_AFTER]
    TI[nt, TI_CAP] = I[I_CAP]
    TF[nt, TF_EPX] = F[F_E]
    TF[nt, TF_QTY] = qty
    TF[nt, TF_XPX] = px
    TF[nt, TF_GROSS] = gross
    TF[nt, TF_COST] = cost
    TF[nt, TF_EQB] = F[F_EQB]
    TF[nt, TF_SLD] = F[F_SLD]
    TF[nt, TF_SLPX] = F[F_SL] if I[I_HSL] != 0 else np.nan
    TF[nt, TF_TPPX] = F[F_TP] if I[I_HTP] != 0 else np.nan
    I[I_NT] = nt + 1
    I[I_NCLOSED] += 1
    F[F_LASTPNL] = gross - cost
    I[I_POS] = 0


@njit(cache=True)
def _fill(F, I, SF, SI, TF, TI, s, k, px, use_trail, mintick, tv_margin, c_fix, c_pct):
    """Entry fill of the order in slot s at px on bar k: a reversal if a position is open (G8), else a fresh
    trade; the bracket of the order's own ticks from this fill (6.2). False = refused by tvMargin (G14)."""
    qty = SF[s, SF_QTY]
    if tv_margin > 0.0 and qty * px * tv_margin / 100.0 > F[F_CASH]:
        SI[s, SI_ACT] = 0
        I[I_MREF] += 1
        return False
    d = 1 if s == 0 else -1
    after = 0
    if I[I_POS] != 0:
        if I[I_POS] == d:
            I[I_ERR] += 1                    # a pending order is never on the side of the open position
        _close(F, I, TF, TI, k, px, K_REV, c_fix, c_pct)
    elif SI[s, SI_TYPE] == 1 and I[I_EXLEG] > 0:
        after = 1
    eqb = F[F_CASH]
    ec = qty * (c_fix + c_pct * px)
    F[F_CASH] = eqb - ec
    I[I_POS] = d
    F[F_QTY] = qty
    F[F_E] = px
    F[F_EQB] = eqb
    F[F_ECOST] = ec
    F[F_SLD] = SF[s, SF_SLD]
    slt = SF[s, SF_SLT]
    tpt = SF[s, SF_TPT]
    if slt > 0:
        I[I_HSL] = 1
        F[F_SL] = px - d * (slt * mintick)
    else:
        I[I_HSL] = 0
        F[F_SL] = np.nan
    if tpt > 0:
        I[I_HTP] = 1
        F[F_TP] = px + d * (tpt * mintick)
    else:
        I[I_HTP] = 0
        F[F_TP] = np.nan
    if use_trail:
        tra = SF[s, SF_TRA]
        F[F_A] = px + d * (tra * mintick)
        F[F_OFF] = SF[s, SF_TRD] * mintick
        I[I_ARMED] = 1 if tra <= 0 else 0
        F[F_BEST] = px
    else:
        I[I_ARMED] = 0
    I[I_EBAR] = k
    I[I_SBAR] = SI[s, SI_BAR]
    I[I_EKIND] = SI[s, SI_KIND]
    I[I_SIG] = SI[s, SI_SIG]
    I[I_OTYPE] = SI[s, SI_TYPE]
    I[I_REENT] = SI[s, SI_REENT]
    I[I_INH] = 0
    I[I_AFTER] = after
    I[I_CAP] = SI[s, SI_CAP]
    if SI[s, SI_KIND] == 2:
        I[I_PFILL] += 1
    notional = qty * px
    if notional > eqb:
        I[I_MOVER] += 1
    x = notional / eqb
    if x > F[F_MAXNOT]:
        F[F_MAXNOT] = x
    SI[s, SI_ACT] = 0
    return True


@njit(cache=True)
def _walk_bar(F, I, SF, SI, TF, TI, k, o, h, l, cl, skip_a3, xl_open, xl_leg,
              use_trail, mintick, tv_margin, c_fix, c_pct):
    """Steps A3, A4 and B of SPEC 6.3 for one bar: a chart bar (path 'tv') or one 1-minute sub-bar of chart
    bar k (path 'mag'). The open, then the rule-4 path.
    skip_a3: the open trade was filled at this very open (a market order, A2): its bracket is not tested
    against the open. xl_open: the exleg code of an exit at this open (1 at a chart open; 2 at the open of a
    later sub-bar). xl_leg: 0 = an exit on leg n gets code n + 1 ('tv'); else that code ('mag': 2)."""
    # ---- A3: the trade that was open before this (sub-)bar, at the open
    d = I[I_POS]
    if d != 0 and not skip_a3:
        ex, lvl, istr = _stop_level(F, I, use_trail)
        if d > 0:
            if ex and o <= lvl:
                _close(F, I, TF, TI, k, o, K_TRAIL if istr else K_SL, c_fix, c_pct)
                I[I_EXLEG] = xl_open
            elif I[I_HTP] != 0 and o >= F[F_TP]:
                _close(F, I, TF, TI, k, o, K_TP, c_fix, c_pct)
                I[I_EXLEG] = xl_open
            elif use_trail:
                if I[I_ARMED] != 0:
                    if o > F[F_BEST]:
                        F[F_BEST] = o
                elif o >= F[F_A]:
                    I[I_ARMED] = 1
                    F[F_BEST] = o
        else:
            if ex and o >= lvl:
                _close(F, I, TF, TI, k, o, K_TRAIL if istr else K_SL, c_fix, c_pct)
                I[I_EXLEG] = xl_open
            elif I[I_HTP] != 0 and o <= F[F_TP]:
                _close(F, I, TF, TI, k, o, K_TP, c_fix, c_pct)
                I[I_EXLEG] = xl_open
            elif use_trail:
                if I[I_ARMED] != 0:
                    if o < F[F_BEST]:
                        F[F_BEST] = o
                elif o <= F[F_A]:
                    I[I_ARMED] = 1
                    F[F_BEST] = o
    # ---- A4: price orders already passed at the open, the older placement first
    s0 = 0
    s1 = 1
    if SI[1, SI_SEQ] < SI[0, SI_SEQ]:
        s0 = 1
        s1 = 0
    for t in range(2):
        s = s0 if t == 0 else s1
        if SI[s, SI_ACT] != 0 and SI[s, SI_TYPE] == 1:
            pp = SF[s, SF_P]
            if (SI[s, SI_TRIG] > 0 and o >= pp) or (SI[s, SI_TRIG] < 0 and o <= pp):
                _fill(F, I, SF, SI, TF, TI, s, k, o, use_trail, mintick, tv_margin, c_fix, c_pct)
    # ---- B: the path (rule 4; a tie goes low first)
    if (h - o) < (o - l):
        v1 = h
        v2 = l
    else:
        v1 = l
        v2 = h
    cur = o
    for leg in range(3):
        if leg == 0:
            b = v1
        elif leg == 1:
            b = v2
        else:
            b = cl
        if b == cur:
            continue
        up = b > cur
        while True:
            d = I[I_POS]
            xk = 0
            xpx = 0.0
            if d != 0:
                if up:
                    if d > 0:
                        if I[I_HTP] != 0 and b >= F[F_TP]:
                            xk = K_TP
                            xpx = F[F_TP] if F[F_TP] > cur else cur
                    else:
                        ex, lvl, istr = _stop_level(F, I, use_trail)
                        if ex and b >= lvl:
                            xk = K_TRAIL if istr else K_SL
                            xpx = lvl if lvl > cur else cur
                else:
                    if d < 0:
                        if I[I_HTP] != 0 and b <= F[F_TP]:
                            xk = K_TP
                            xpx = F[F_TP] if F[F_TP] < cur else cur
                    else:
                        ex, lvl, istr = _stop_level(F, I, use_trail)
                        if ex and b <= lvl:
                            xk = K_TRAIL if istr else K_SL
                            xpx = lvl if lvl < cur else cur
            os_ = -1
            opx = 0.0
            for t in range(2):
                s = s0 if t == 0 else s1
                if SI[s, SI_ACT] != 0 and SI[s, SI_TYPE] == 1:
                    pp = SF[s, SF_P]
                    if up:
                        if SI[s, SI_TRIG] > 0 and b >= pp:
                            q = pp if pp > cur else cur
                            if os_ < 0 or q < opx:
                                os_ = s
                                opx = q
                    else:
                        if SI[s, SI_TRIG] < 0 and b <= pp:
                            q = pp if pp < cur else cur
                            if os_ < 0 or q > opx:
                                os_ = s
                                opx = q
            if xk == 0 and os_ < 0:
                # nothing reached on the rest of this leg: the trail arms / ratchets on a favourable leg
                if d != 0 and use_trail and ((d > 0) == up):
                    if d > 0:
                        if I[I_ARMED] != 0:
                            if b > F[F_BEST]:
                                F[F_BEST] = b
                        elif b >= F[F_A]:
                            I[I_ARMED] = 1
                            F[F_BEST] = b
                    else:
                        if I[I_ARMED] != 0:
                            if b < F[F_BEST]:
                                F[F_BEST] = b
                        elif b <= F[F_A]:
                            I[I_ARMED] = 1
                            F[F_BEST] = b
                break
            if xk != 0 and (os_ < 0 or (up and xpx <= opx) or ((not up) and xpx >= opx)):
                _close(F, I, TF, TI, k, xpx, xk, c_fix, c_pct)         # a tie: the exit before the order
                I[I_EXLEG] = (leg + 1) if xl_leg == 0 else xl_leg
                cur = xpx
            else:
                if _fill(F, I, SF, SI, TF, TI, os_, k, opx, use_trail, mintick, tv_margin, c_fix, c_pct):
                    cur = opx
        cur = b


@njit(cache=True)
def _kernel(o, h, l, c, armL, armS, sigL, sigS, buyOk, sellOk, gate, flatOk, win, day, atr14, atrx,
            mode, stop_buf, cancel_after, one_sig,
            points_mode, sl_points, tp_points, sl_atr_mult, tp_r, use_trail,
            trail_act_points, trail_points, trail_act_atr, trail_dst_atr, max_bars_held,
            risk_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct, point_value,
            use_max_bars_exit, max_bars_in_trade, use_daily_lock, max_daily_loss, max_daily_losses,
            use_max_stop, max_stop_points, inv, tv_margin, c_fix, c_pct, mintick, init_cap,
            cap, mid_j, full, mag, ptr, sb_o, sb_h, sb_l, sb_c):
    """mode: 0 "Signal Only", 1 "Market Next Candle", 2 "Stop Next Candle".
    mag: walk the sub-bars [ptr[k], ptr[k+1]) of chart bar k (sb_o / sb_h / sb_l / sb_c) instead of the bar."""
    n = o.shape[0]
    F = np.zeros(NF)
    I = np.zeros(NI, np.int64)
    SF = np.zeros((2, 7))
    SI = np.zeros((2, 9), np.int64)
    TF = np.zeros((cap, 9))
    TI = np.zeros((cap, 12), np.int64)
    F[F_CASH] = init_cap
    nb_ = n if full else 1
    eq_arr = np.zeros(nb_)
    pos_arr = np.zeros(nb_, np.int8)
    lock_arr = np.zeros(nb_, np.bool_)
    dlc_arr = np.zeros(nb_, np.int64)
    can_arr = np.zeros(nb_, np.bool_)
    plc_arr = np.zeros(nb_, np.int8)       # order placed in the run of this bar: sig * kind (0 none)
    cnl_arr = np.zeros(nb_, np.bool_)      # the cancel block removed at least one order on this bar
    qty_arr = np.full(nb_, np.nan)         # entry_qty of the run (when it was computed)

    pre_can_order = mode != 0
    stop_mode = mode == 2
    # the script's var state
    active_day = NA
    day_start_eq = np.nan
    day_loss_count = 0
    last_closed = 0
    daily_locked = False
    last_win = NA
    last_pre = NA
    ebi = NA
    prev_pos = 0
    close_req = 0
    seq = 0

    n_raw_l = 0
    n_raw_s = 0
    n_blk_l = 0
    n_blk_s = 0
    n_placed = 0
    n_pplaced = 0
    n_prepl = 0
    n_pcancel = 0
    n_locked = 0
    n_lockdays = 0
    n_zero = 0
    n_inh = 0
    n_pos = 0
    dd_pk = init_cap
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init_cap
    eq_last = init_cap

    for k in range(n):
        ok_ = o[k]
        ck_ = c[k]
        I[I_EXLEG] = 0
        # ---- A1: strategy.close of the previous run
        if close_req != 0:
            if I[I_POS] != 0:
                _close(F, I, TF, TI, k, ok_, close_req, c_fix, c_pct)
                I[I_EXLEG] = 1
            close_req = 0
        # ---- A2: market orders fill at the open
        for s in range(2):
            if SI[s, SI_ACT] != 0 and SI[s, SI_TYPE] == 0:
                if I[I_POS] != 0:
                    I[I_ERR] += 1
                _fill(F, I, SF, SI, TF, TI, s, k, ok_, use_trail, mintick, tv_margin, c_fix, c_pct)
                SI[s, SI_ACT] = 0
        # ---- A3, A4, B (nothing can happen on the path of a bar with no position and no pending order)
        if I[I_POS] != 0 or SI[0, SI_ACT] != 0 or SI[1, SI_ACT] != 0:
            # a trade filled by a market order at this open: its bracket is not tested against this open
            skip = I[I_POS] != 0 and I[I_EBAR] == k
            if mag:
                m0 = ptr[k]
                m1 = ptr[k + 1]
                for m in range(m0, m1):
                    if I[I_POS] == 0 and SI[0, SI_ACT] == 0 and SI[1, SI_ACT] == 0:
                        break                  # flat and no pending order: nothing can happen before the close
                    if m == m0:
                        _walk_bar(F, I, SF, SI, TF, TI, k, sb_o[m], sb_h[m], sb_l[m], sb_c[m], skip, 1, 2,
                                  use_trail, mintick, tv_margin, c_fix, c_pct)
                    else:
                        _walk_bar(F, I, SF, SI, TF, TI, k, sb_o[m], sb_h[m], sb_l[m], sb_c[m], False, 2, 2,
                                  use_trail, mintick, tv_margin, c_fix, c_pct)
            else:
                _walk_bar(F, I, SF, SI, TF, TI, k, ok_, h[k], l[k], ck_, skip, 1, 0,
                          use_trail, mintick, tv_margin, c_fix, c_pct)

        # ---- C: the script run at the close
        pos = I[I_POS]
        equity = F[F_CASH]
        if pos != 0:
            equity = F[F_CASH] + pos * F[F_QTY] * (ck_ - F[F_E])
        # C1 daily lock (L1178-1203)
        if active_day == NA or day[k] != active_day:
            active_day = day[k]
            day_start_eq = equity
            day_loss_count = 0
            daily_locked = False
        if I[I_NCLOSED] > last_closed:
            if F[F_LASTPNL] < 0:
                day_loss_count += 1
            last_closed = I[I_NCLOSED]
        day_pnl = equity - day_start_eq
        loss_hit = use_daily_lock and max_daily_loss > 0 and day_pnl <= -max_daily_loss
        count_hit = use_daily_lock and day_loss_count >= max_daily_losses
        if (loss_hit or count_hit) and not daily_locked:
            daily_locked = True
            n_lockdays += 1
        if daily_locked:
            n_locked += 1

        pre_this = False
        raw_l = False
        raw_s = False
        placed = 0
        cancelled = False
        can = False
        if pos == 0:
            # C2 / C3: exit geometry, quantity, can_enter (L1210-1223); only needed where an arm or a
            # signal could use it
            if ((armL[k] or armS[k] or sigL[k] or sigS[k]) and gate[k] and not daily_locked
                    and ((not one_sig) or last_win == NA or win[k] != last_win)):
                if points_mode:
                    slt = sl_points
                    tpt = tp_points
                    tra = trail_act_points
                    trd = trail_points
                else:
                    ea = atrx[k]
                    slt = sl_atr_mult * ea / mintick
                    if slt != slt:
                        slt = 0.0
                    tpt = slt * tp_r
                    tra = trail_act_atr * ea / mintick
                    if tra != tra:
                        tra = 0.0
                    trd = trail_dst_atr * ea / mintick
                    if trd != trd:
                        trd = 0.0
                if trd < 1.0:
                    trd = 1.0
                stop_distance = slt * mintick
                # f_get_qty (L1163-1171)
                capf = 0
                q = fixed_qty
                if risk_mode:
                    stop_cash = stop_distance * point_value
                    if stop_cash > 0:
                        q = equity * risk_pct / 100.0 / stop_cash
                    else:
                        q = 0.0
                if max_qty < q:
                    q = max_qty
                    capf = 1
                if cap_margin and margin_pct > 0:
                    mq = equity / (ck_ * point_value * margin_pct / 100.0)
                    if mq < q:
                        q = mq
                        capf = 2
                q = q + 1e-9 * qty_step
                if qty_step > 0:
                    q = math.floor(q / qty_step) * qty_step
                if full:
                    qty_arr[k] = q
                if (not use_max_stop) or stop_distance <= max_stop_points:
                    if q > 0:
                        can = True
                    else:
                        n_zero += 1
            if can:
                # C4 blocks 1 and 2: the pre-candle arms (L1238, L1261)
                for blk in range(2):
                    if blk == 0:
                        hit = pre_can_order and armL[k]
                        sg = 1
                        okf = buyOk[k]
                    else:
                        hit = pre_can_order and armS[k] and not pre_this
                        sg = -1
                        okf = sellOk[k]
                    if hit:
                        if sg > 0:
                            raw_l = True
                        else:
                            raw_s = True
                        if okf:
                            dd_ = -sg if inv else sg
                            s = 0 if dd_ > 0 else 1
                            if SI[s, SI_ACT] != 0 and SI[s, SI_KIND] == 2:
                                n_prepl += 1
                            seq += 1
                            SI[s, SI_ACT] = 1
                            SI[s, SI_SIG] = sg
                            SI[s, SI_TRIG] = sg
                            SI[s, SI_BAR] = k
                            SI[s, SI_SEQ] = seq
                            SI[s, SI_REENT] = I[I_EXLEG]
                            SI[s, SI_CAP] = capf
                            SF[s, SF_QTY] = q
                            SF[s, SF_SLT] = slt
                            SF[s, SF_TPT] = tpt
                            SF[s, SF_TRA] = tra
                            SF[s, SF_TRD] = trd
                            SF[s, SF_SLD] = stop_distance
                            if stop_mode:
                                SI[s, SI_TYPE] = 1
                                SI[s, SI_KIND] = 2
                                if sg > 0:
                                    SF[s, SF_P] = h[k] + atr14[k] * stop_buf      # preLongStopPrice L1225
                                else:
                                    SF[s, SF_P] = l[k] - atr14[k] * stop_buf      # preShortStopPrice L1226
                                last_pre = k
                                n_pplaced += 1
                            else:
                                SI[s, SI_TYPE] = 0
                                SI[s, SI_KIND] = 1
                                SF[s, SF_P] = np.nan
                                last_pre = NA
                            last_win = win[k]
                            pre_this = True
                            n_placed += 1
                            placed = sg * SI[s, SI_KIND]
            # C4 block 3: cancel unfilled pre-stops (L1284-1287); the position is flat here
            if stop_mode and last_pre != NA and k - last_pre > cancel_after:
                for s in range(2):
                    if SI[s, SI_ACT] != 0:
                        if SI[s, SI_KIND] == 2:
                            n_pcancel += 1
                        SI[s, SI_ACT] = 0
                        cancelled = True
                last_pre = NA
            if can and not pre_this:
                # C4 blocks 4 and 5: the EMA-cross signals, market (L1289, L1305)
                for blk in range(2):
                    if blk == 0:
                        hit = sigL[k]
                        sg = 1
                        okf = buyOk[k]
                    else:
                        hit = sigS[k]
                        sg = -1
                        okf = sellOk[k]
                    if hit:
                        if sg > 0:
                            raw_l = True
                        else:
                            raw_s = True
                        if okf:
                            dd_ = -sg if inv else sg
                            s = 0 if dd_ > 0 else 1
                            if SI[s, SI_ACT] != 0 and SI[s, SI_KIND] == 2:
                                n_prepl += 1
                            seq += 1
                            SI[s, SI_ACT] = 1
                            SI[s, SI_SIG] = sg
                            SI[s, SI_TRIG] = sg
                            SI[s, SI_BAR] = k
                            SI[s, SI_SEQ] = seq
                            SI[s, SI_REENT] = I[I_EXLEG]
                            SI[s, SI_CAP] = capf
                            SI[s, SI_TYPE] = 0
                            SI[s, SI_KIND] = 3
                            SF[s, SF_P] = np.nan
                            SF[s, SF_QTY] = q
                            SF[s, SF_SLT] = slt
                            SF[s, SF_TPT] = tpt
                            SF[s, SF_TRA] = tra
                            SF[s, SF_TRD] = trd
                            SF[s, SF_SLD] = stop_distance
                            last_win = win[k]
                            n_placed += 1
                            placed = sg * 3
        if raw_l:
            n_raw_l += 1
            if not buyOk[k]:
                n_blk_l += 1
        if raw_s:
            n_raw_s += 1
            if not sellOk[k]:
                n_blk_s += 1

        # C5 bars in trade and the closes (L1322-1354)
        if pos != 0 and prev_pos == 0:
            ebi = k
        if pos == 0:
            ebi = NA
        if pos != 0:
            if prev_pos != 0 and I[I_EBAR] == k and I[I_INH] == 0:
                I[I_INH] = 1                       # the trade opened in this bar inherits entryBarIndex
                n_inh += 1
            bars_in = k - ebi                      # ebi is never na while a position is open
            max_bars_hit = use_max_bars_exit and bars_in >= max_bars_in_trade
            time_hit = max_bars_held > 0 and bars_in >= max_bars_held and not max_bars_hit
            if max_bars_hit:
                close_req = K_MAXBARS
            elif time_hit:
                close_req = K_TIME
            elif daily_locked:
                close_req = K_LOCK
            elif not flatOk[k]:
                close_req = K_EOD
            n_pos += 1
        prev_pos = pos

        # C6 bar-close equity
        if k < n - 1:
            if equity > dd_pk:
                dd_pk = equity
            x = (dd_pk - equity) / dd_pk
            if x > dd_rel:
                dd_rel = x
            x = dd_pk - equity
            if x > dd_abs:
                dd_abs = x
            if k == mid_j:
                eq_mid = equity
        else:
            eq_last = equity
        if full:
            eq_arr[k] = equity
            pos_arr[k] = pos
            lock_arr[k] = daily_locked
            dlc_arr[k] = day_loss_count
            can_arr[k] = can
            plc_arr[k] = placed
            cnl_arr[k] = cancelled

    # the end of the window: an open trade is closed at the last close; orders are dropped
    n_pend_end = 0
    for s in range(2):
        if SI[s, SI_ACT] != 0 and SI[s, SI_KIND] == 2:
            n_pend_end += 1
    if n > 0:
        if I[I_POS] != 0:
            _close(F, I, TF, TI, n - 1, c[n - 1], K_END, c_fix, c_pct)
            eq_last = F[F_CASH]
            if full:
                eq_arr[n - 1] = eq_last
        if eq_last > dd_pk:
            dd_pk = eq_last
        x = (dd_pk - eq_last) / dd_pk
        if x > dd_rel:
            dd_rel = x
        x = dd_pk - eq_last
        if x > dd_abs:
            dd_abs = x
        if mid_j == n - 1:
            eq_mid = eq_last
    nt = I[I_NT]
    stats = np.array([eq_last, eq_mid, dd_rel, dd_abs, float(n_pos), float(n_raw_l), float(n_raw_s),
                      float(n_blk_l), float(n_blk_s), float(n_placed), float(n_pplaced), float(I[I_PFILL]),
                      float(n_prepl), float(n_pcancel), float(n_pend_end), float(n_locked), float(n_lockdays),
                      float(n_zero), float(n_inh), float(I[I_MOVER]), float(I[I_MREF]), F[F_MAXNOT],
                      float(I[I_ERR]), F[F_CASH]])
    return TI[:nt], TF[:nt], stats, eq_arr, pos_arr, lock_arr, dlc_arr, can_arr, plc_arr, cnl_arr, qty_arr


_STATS = ('eq_last', 'eq_mid', 'dd_rel', 'dd_abs', 'n_pos', 'raw_long', 'raw_short', 'blocked_long',
          'blocked_short', 'orders_placed', 'pend_placed', 'pend_filled', 'pend_replaced', 'pend_cancelled',
          'pend_open_end', 'locked_bars', 'lock_days', 'zero_qty', 'inherit_ebi', 'margin_over',
          'margin_refused', 'max_notional_x', 'errors', 'cash')
_MODES = {'Signal Only': 0, 'Market Next Candle': 1, 'Stop Next Candle': 2}


# ----------------------------------------------------------------------------------------------
# public interface
# ----------------------------------------------------------------------------------------------
def simulate(P, x=None, full=False, sub=None):
    """Orders and exits on prepare()'s arrays. x: ORDER / EXIT inputs by Pine name (SPEC 3.2), plus path
    ('tv' | 'mag'), cost ('tv' | 'ours' | 'stress'), tvMargin, inv; a SIGNAL key in x raises unless it repeats
    the prepared value. full=True adds the per-bar state arrays (traces). sub: a sub-bar table to use on the
    'mag' path instead of the 1-minute data (tests: fake_sub_bars, synthetic bars)."""
    Q = P['params']
    if x:
        Q = dict(Q)
        given = {}
        for k, v in x.items():
            if k in IGNORED_KEYS:
                continue
            if k not in DEFAULTS:
                raise ValueError('unknown param %r' % (k,))
            if k in SIGNAL_KEYS:
                if v != Q[k]:
                    raise ValueError('%r is fixed by prepare()' % (k,))
                continue
            given[k] = v
            Q[k] = v
        Q['gvInv'] = Q['inv'] = _resolve_inv(given, P['params']['gvInv'])
        for k in _BOOLS:
            Q[k] = bool(Q[k])
        _check(Q)
    mag = Q['path'] == 'mag'
    if mag:
        S = sub if sub is not None else get_sub(P)
        if len(S[0]) != P['n'] + 1:
            raise ValueError('the sub-bar table does not match the window')
    else:
        S = _NO_SUB
    c_fix, c_pct = COSTS[Q['cost']][P['pair']]
    point_value = 1.0 if Q['brokerPreset'] == 'Crypto 1 USD per qty' else float(Q['manualPointValue'])   # L988
    atrx = exit_atr(P, Q['atrLen'])
    cand = (P['armL'] | P['armS'] | P['sigL'] | P['sigS']) & P['gate']
    cap = int(np.count_nonzero(cand)) + 4
    out = _kernel(P['open'], P['high'], P['low'], P['close'], P['armL'], P['armS'], P['sigL'], P['sigS'],
                  P['buyOk'], P['sellOk'], P['gate'], P['flatOk'], P['win'], P['day'], P['atr14'], atrx,
                  _MODES[Q['preCandleEntryMode']], float(Q['preStopAtrBuffer']), int(Q['preCancelAfterBars']),
                  bool(Q['oneSignalPerPolyWindow']),
                  Q['ExitMode'] == 'Points', float(Q['slPoints']), float(Q['tpPoints']), float(Q['slAtrMult']),
                  float(Q['tpR']), bool(Q['useTrail']), float(Q['trailActPoints']), float(Q['trailPoints']),
                  float(Q['trailActAtr']), float(Q['trailDstAtr']), int(Q['maxBarsHeld']),
                  Q['QtyMode'] == 'Risk %', float(Q['fixedQty']), float(Q['riskPct']), float(Q['maxQty']),
                  float(Q['qtyStep']), bool(Q['capMargin']), float(Q['marginPct']), point_value,
                  bool(Q['useMaxBarsExit']), int(Q['maxBarsInTrade']), bool(Q['useDailyLossLock']),
                  float(Q['maxDailyLossCurrency']), int(Q['maxDailyLosses']),
                  bool(Q['useMaxStopDistance']), float(Q['maxStopDistancePoints']),
                  bool(Q['gvInv']), float(Q['tvMargin']), float(c_fix), float(c_pct), MINTICK, INITIAL_CAPITAL,
                  cap, int(P['mid_j']), bool(full), mag, S[0], S[1], S[2], S[3], S[4])
    TI, TF, stats = out[0], out[1], out[2]
    st = dict(zip(_STATS, stats))
    if st['errors'] != 0:
        raise RuntimeError('broker assertion failed %d time(s) (an order on the side of the open position)'
                           % int(st['errors']))
    R = dict(TI=TI, TF=TF, stats=st, x=Q, inv=bool(Q['gvInv']), path=Q['path'],
             dir=TI[:, TI_DIR], sig=TI[:, TI_SIG], entry_kind=TI[:, TI_EKIND], otype=TI[:, TI_OTYPE],
             sk=TI[:, TI_SBAR], ek=TI[:, TI_EBAR], xk=TI[:, TI_XBAR], kind=TI[:, TI_XKIND],
             reentry=TI[:, TI_REENT], inherit=TI[:, TI_INH], after=TI[:, TI_AFTER], capf=TI[:, TI_CAP],
             epx=TF[:, TF_EPX], qty=TF[:, TF_QTY], xpx=TF[:, TF_XPX], gross=TF[:, TF_GROSS], cost=TF[:, TF_COST],
             eqb=TF[:, TF_EQB], sld=TF[:, TF_SLD], slpx=TF[:, TF_SLPX], tppx=TF[:, TF_TPPX])
    if full:
        R.update(eq=out[3], pos=out[4], locked=out[5], day_loss_count=out[6], can_enter=out[7], placed=out[8],
                 cancelled=out[9], entry_qty=out[10])
    return R


def _r_mult(R):
    pnl = R['gross'] - R['cost']
    den = R['sld'] * R['qty']
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(R['sld'] > 0, pnl / np.where(den != 0, den, np.nan), np.nan)


def trades(P, R):
    """One row per entry fill, in fill order = closing order (one trade open at a time) (SPEC 12).
    entry_time / exit_time are chart-bar opens on both paths ('end': the last t_close)."""
    w0 = P['w0']
    to = P['t_open']
    tc = P['t_close']
    kind = R['kind']
    xk = R['xk']
    ot = np.where(R['otype'] == 0, 'market', 'limit' if R['inv'] else 'stop')
    return pd.DataFrame({
        'dir': R['dir'].astype(np.int64),
        'sig': R['sig'].astype(np.int64),
        'entry_kind': R['entry_kind'].astype(np.int64),
        'order_type': ot,
        'sig_bar': R['sk'] + w0,
        'entry_bar': R['ek'] + w0,
        'exit_bar': xk + w0,
        'entry_time': to[R['ek']],
        'exit_time': np.where(kind == K_END, tc[xk], to[xk]),
        'entry_px': R['epx'],
        'qty': R['qty'],
        'exit_px': R['xpx'],
        'exit_kind': [KINDS[i] for i in kind],
        'pnl': R['gross'] - R['cost'],
        'pnl_gross': R['gross'],
        'costs': R['cost'],
        'eq_before': R['eqb'],
        'sl_dist': R['sld'],
        'sl_px': R['slpx'],
        'tp_px': R['tppx'],
        'r_mult': _r_mult(R),
        'reentry': R['reentry'].astype(np.int64),
        'inherit_ebi': R['inherit'].astype(bool),
        'after_exit': R['after'].astype(bool),
    })


def summary(P, R):
    """The common fields as hrd.summary_fast + hrd.extra_fields (INITIAL_CAPITAL 100,000) and the fields of
    this strategy (SPEC 12)."""
    init = INITIAL_CAPITAL
    st = R['stats']
    pnl = R['gross'] - R['cost']
    final = float(st['eq_last'])
    eq_mid = float(st['eq_mid'])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    nt = len(pnl)
    d = R['dir']
    kc = np.bincount(R['kind'], minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    out = dict(
        start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if nt else np.nan,
        max_dd_pct=float(st['dd_rel'] * 100),
        max_dd_init_pct=float(st['dd_abs'] / init * 100),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(st['raw_long']), raw_short=int(st['raw_short']),
        blocked_long=int(st['blocked_long']), blocked_short=int(st['blocked_short']),
        half1_pct=(eq_mid - init) / init * 100,
        half2_pct=(final - eq_mid) / init * 100,
        exposure=float(st['n_pos'] / P['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((R['ek'] == R['xk']).sum())
    # fair halves (trades ENTERED in each half by the fill bar's t_open <= mid / > mid)
    first = P['t_open'][R['ek']] <= P['mid']
    r = 1.0 + pnl / R['eqb']
    n1 = int(first.sum())
    out.update(h1r_pct=(float(np.prod(r[first])) - 1.0) * 100.0, h2r_pct=(float(np.prod(r[~first])) - 1.0) * 100.0,
               h1_trades=n1, h2_trades=nt - n1,
               avg_bars_held=float((R['xk'] - R['ek']).mean()) if nt else np.nan)
    out['costs'] = float(R['cost'].sum())
    # fields of this strategy
    rm = _r_mult(R)
    out['net_r'] = float(rm.sum())
    out['h1_r'] = float(rm[first].sum())
    out['h2_r'] = float(rm[~first].sum())
    out.update(arms_long=int(P['arms_long']), arms_short=int(P['arms_short']),
               sig_long=int(P['sig_long']), sig_short=int(P['sig_short']))
    for k in ('orders_placed', 'pend_placed', 'pend_filled', 'pend_replaced', 'pend_cancelled', 'pend_open_end'):
        out[k] = int(st[k])
    re_ = R['reentry']
    mk = R['otype'] == 0
    out['reentry_same_bar'] = int((re_ > 0).sum())
    out['reentry_extreme'] = int((((re_ == 1) | (re_ == 2)) & mk).sum())
    gap = 0.0
    sel = np.flatnonzero((re_ > 0) & mk & (R['sld'] > 0))
    if R.get('path', 'tv') != 'tv':
        sel = sel[:0]                # path 'mag': no "next path point of the chart bar"; 0 by definition
    if len(sel):
        sk = R['sk'][sel]
        po, ph, pl_, pc = P['open'][sk], P['high'][sk], P['low'][sk], P['close'][sk]
        hi_first = (ph - po) < (po - pl_)
        v1 = np.where(hi_first, ph, pl_)
        v2 = np.where(hi_first, pl_, ph)
        code = re_[sel]
        tv_px = np.where(code == 1, v1, np.where(code == 2, v2, pc))
        gap = float((R['dir'][sel] * (R['epx'][sel] - tv_px) / R['sld'][sel]).sum())
    out['reentry_gap_r'] = gap
    out['pend_fill_after_exit'] = int(R['after'].sum())
    out['inherit_ebi'] = int(R['inherit'].sum())
    out['locked_bars'] = int(st['locked_bars'])
    out['lock_days'] = int(st['lock_days'])
    out['zero_qty'] = int(st['zero_qty'])
    out['qty_capped_max'] = int((R['capf'] == 1).sum())
    out['qty_capped_margin'] = int((R['capf'] == 2).sum())
    out['margin_over'] = int(st['margin_over'])
    out['margin_refused'] = int(st['margin_refused'])
    out['max_notional_x'] = float(st['max_notional_x'])
    return out


def split_params(params):
    """One dict -> (SIGNAL params for prepare, ORDER / EXIT params for simulate)."""
    pp, sp = {}, {}
    for k, v in (params or {}).items():
        (sp if k in ORDER_KEYS else pp)[k] = v
    return pp, sp


def run(pair, chart_tf, params=None):
    """prepare + simulate with one dict (SIGNAL and ORDER / EXIT keys together)."""
    P = prepare(pair, chart_tf, params)
    R = simulate(P)
    return trades(P, R), summary(P, R)


def fmt(s):
    return ('trades=%d (L %d / S %d) net=%.3f%% netR=%.1f pf=%.3f win=%.1f%% maxDD=%.2f%% sl/tp/other=%d/%d/%d '
            'zero=%d reentry=%d gapR=%.1f lockbars=%d over=%d'
            % (s['trades'], s['long'], s['short'], s['net_pct'], s['net_r'], s['pf'], s['win_pct'],
               s['max_dd_pct'], s['exit_sl'], s['exit_tp'], s['trades'] - s['exit_sl'] - s['exit_tp'],
               s['zero_length'], s['reentry_same_bar'], s['reentry_gap_r'], s['locked_bars'], s['margin_over']))


if __name__ == '__main__':
    import time as _time
    for pair_, tf_ in (('BTC', '60'), ('XAU', '60')):
        t0 = _time.time()
        P_ = prepare(pair_, tf_)
        t1 = _time.time()
        R_ = simulate(P_)
        t2 = _time.time()
        print(pair_, tf_, 'prepare %.2fs simulate %.3fs' % (t1 - t0, t2 - t1), fmt(summary(P_, R_)))
