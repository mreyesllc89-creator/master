"""FlashGold v5 Strategy (BTCUSD) + FGF [Update 1]: Python replica, CANONICAL module (key fgv5, stage 3).

Ground truth: /home/user/master/FlashGold_v5_Strategy_BTCUSD_FGF.pine at HEAD (Pine //@version=5; Update 1 =
input `fgvInv`). Brief: SPEC_fgv5.md. Reconcile: reconcile_fgv5.md. Interpretations and limits: fgv5_notes.md.

This file is implementation B (fgv5_b.py, which agrees with implementation A trade by trade on every reconcile
case) plus the 1-minute Bar Magnifier path 'mag' (SWEEP_AH_SPEC.md section 2, REPLICA_SPEC.md stage 3):

    prepare(pair, chart_tf, params=None) -> P     signals, zones, filter permissions (SIGNAL inputs)
    simulate(P, x=None, full=False, log_cap=0, sub=None) -> R
                                                  orders, exits, money (ORDER / EXIT inputs by Pine name, plus
                                                  path 'tv' | 'mag', cost 'tv' | 'ours' | 'stress', inv / fgvInv)
    trades(P, R) -> DataFrame                     one row per entry fill (REAL side in `dir`)
    summary(P, R) -> dict
    run(pair, chart_tf, params=None) -> (trades, summary)
    prepare_arrays(...)                           a P from injected arrays (tests)
    sub_bars / get_sub / fake_sub_bars            the 1-minute sub-bars of the chart bars (path 'mag')

Path 'tv' = TradingView's one O-H-L-C path per chart bar (SPEC_AH rule 4). Path 'mag' = Bar Magnifier: every
price order (the pending stop / limit ENTRY orders and the open trade's exit orders XL1 / XL2 / XL: stop loss,
take profit, breakeven stop, runner and Fixed-style trailing stops) walks the 1-minute sub-bars of the chart bar
in time order (rows of data/<PAIR>_1.parquet with t_open in [chart t_open, chart t_close)), each sub-bar with
its own rule-4 path and its own open (a level crossed by a jump between minutes fills at the next minute's open);
pending orders, OCA, the trailing state and the partial state carry from one minute to the next. The market
closes (strategy.close 'opp', strategy.close_all 'time') stay at the chart bar's open, and the script run (the
decisions, the stale cancel, the breakeven flag from the CHART bar's high / low, the time stop) at its close.
Trade bars and times are chart bars. Chart "1": 'mag' == 'tv'.

What is written independently here (from the Pine, not from fgf.py): the TDI direction (RSI Wilder
-> SMA -> slope), the request.security mapping of the parent / six zones onto the chart, the zone
counts, burst / candidates / entry hold (the signal), ATR, the whole broker. Reused from fgf.py:
`fgf.fgf_permissions` (the filter gate, never reimplemented) and `fgf._bars` (bar data of the zone
timeframes; BTC minute timeframes that do not divide 1,440 minutes are built here with a daily
00:00 UTC reset, SPEC V17). The signal arrays equal fgf's own copy of the FlashGold signal (fgv5_b_check_sig.py,
tests_fgv5.py).

History only: one script run per chart bar at its close; orders of that run act from the next bar.
"""
import math
import os
import sys
import time as _time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(W, 'data')
if W not in sys.path:
    sys.path.insert(0, W)
import fgf  # noqa: E402  (filter permissions and zone-timeframe bars)

MINTICK = 0.01
POINTVALUE = 1.0
INITIAL_CAPITAL = 100000.0
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

KINDS = ['', 'sl', 'tp', 'tp_part', 'be', 'runner', 'trail', 'reverse', 'opp', 'time', 'end']
K_SL, K_TP, K_TPP, K_BE, K_RUN, K_TRAIL, K_REV, K_OPP, K_TIME, K_END = range(1, 11)

# per fill, per unit: (fixed $, fraction of the booked fill value); slippage in price on stop / market fills
COSTS = {
    'tv': {'XAU': (0.0, 0.0002), 'BTC': (0.0, 0.0002)},          # strategy(): 0.02 % commission per side
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}
SLIPPAGE = {'tv': 5 * MINTICK, 'ours': 0.0, 'stress': 0.0}    # strategy(): slippage = 5 ticks

# ----------------------------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------------------------
SIG_DEFAULTS = dict(
    # FlashGold Core
    spreadPoints=25.0, entryHoldBars=0, entryHoldMinFavPoints=5.0, oneEntryPerBar=True,
    # Burst / Direction
    DistUnit="ATR", burstAtrMult=0.5, holdFavAtrMult=0.1, burstPointsInput=172.0, useBurstGate=True,
    useAnyCombo=False, priorDriftBars=60, usePriorFilter=False,
    # TDI Trade Zone Filter
    useTdiTradeZone=True, tdiParentTf="60", tdiRsiLen=14, tdiFastLen=2, tdiSlowLen=7, minAlignedZones=2,
    allowNeutralParent=False, ignoreNaZones=True, htfNoRepaint=True,
    useZone1=True, zoneTf1="60", useZone2=True, zoneTf2="120", useZone3=True, zoneTf3="240",
    useZone4=False, zoneTf4="480", useZone5=False, zoneTf5="1", useZone6=False, zoneTf6="2",
    autoTf=True,
    # filter switch (the block's other inputs: fgf.DEFAULTS)
    fgfOn=True,
    # replica: window by t_close (None = the pair's window)
    start=None, end=None,
)
ORD_DEFAULTS = dict(
    entryDistAtrMult=0.25, entryDistPoints=50.0,
    # S1
    Direction="Both", entryValidBars=3, allowReverse=True, exitOnOpposite=False,
    # S2
    ExitMode="Pips", pipSize=1.0, slPips=30.0, tpRPips=5.0, runTrailPips=600.0, trailActPips=150.0,
    trailPips=600.0, slPoints=3900.0, tpPoints=19500.0, atrLen=14, slAtrMult=0.1, tpR=2.0, useTrail=False,
    trailActPoints=4500.0, trailPoints=1000.0, trailActAtr=1.0, trailDstAtr=0.25, maxBarsHeld=0,
    TpStyle="Partial + runner", partPct=30.0, runBE=True, runTrailAtr=1.5, runTrailPts=58000.0,
    # S3
    QtyMode="Fixed", fixedQty=10.0, riskPct=1.0, maxQty=50.0, qtyStep=1.0,
    # Update 1
    fgvInv=False,
    # replica controls
    path='tv', cost='tv',
)
FGF_KEYS = tuple(k for k in fgf.DEFAULTS if k != 'fgfOn')
DISPLAY_KEYS = {'showEntryLabels', 'showEntryLines', 'showSideTags', 'priceTagOffsetBars', 'entryLineBars',
                'labelTimeZone', 'showZoneTable', 'fgfShowBg', 'fgfShowLv', 'fgfSigMark', 'fgfShowTbl',
                'fgfTblPos', 'fgsShow', 'fgsWin', 'fgsH', 'FGF_FORCE_OVERLAY'}
ALIASES = {'inv': 'fgvInv'}
DEFAULTS = dict(SIG_DEFAULTS)
DEFAULTS.update({k: fgf.DEFAULTS[k] for k in FGF_KEYS})
DEFAULTS.update(ORD_DEFAULTS)

_OPTIONS = {'DistUnit': ("ATR", "Points"), 'Direction': ("Both", "Long", "Short"),
            'ExitMode': ("Pips", "ATR", "Points"), 'TpStyle': ("Fixed", "Partial + runner"),
            'QtyMode': ("Fixed", "Risk %"), 'path': ('tv', 'mag'), 'cost': ('tv', 'ours', 'stress')}
_INTS = {'entryHoldBars', 'priorDriftBars', 'tdiRsiLen', 'tdiFastLen', 'tdiSlowLen', 'minAlignedZones',
         'entryValidBars', 'atrLen', 'maxBarsHeld'}
_BOOLS = {'oneEntryPerBar', 'useBurstGate', 'useAnyCombo', 'usePriorFilter', 'useTdiTradeZone',
          'allowNeutralParent', 'ignoreNaZones', 'htfNoRepaint', 'useZone1', 'useZone2', 'useZone3', 'useZone4',
          'useZone5', 'useZone6', 'autoTf', 'fgfOn', 'allowReverse', 'exitOnOpposite', 'useTrail', 'runBE',
          'fgvInv'}
_MINVAL = {'priorDriftBars': 1, 'tdiRsiLen': 2, 'tdiFastLen': 1, 'tdiSlowLen': 1, 'pipSize': 0.000001,
           'slAtrMult': 0.01, 'runTrailPips': 1.0, 'trailPips': 1.0, 'trailPoints': 1.0, 'trailDstAtr': 0.005,
           'runTrailAtr': 0.05, 'runTrailPts': 1.0, 'atrLen': 1, 'qtyStep': 0.000001}
_STRINGS = {'tdiParentTf', 'zoneTf1', 'zoneTf2', 'zoneTf3', 'zoneTf4', 'zoneTf5', 'zoneTf6'}


def _norm_key(k):
    return ALIASES.get(k, k)


def _validate(Q):
    for k, opts in _OPTIONS.items():
        if Q[k] not in opts:
            raise ValueError(f'{k}={Q[k]!r} is not one of {opts}')
    for k in _INTS:
        v = Q[k]
        if isinstance(v, bool) or float(v) != int(v):
            raise ValueError(f'{k}={v!r} must be an integer')
        Q[k] = int(v)
    for k in _BOOLS:
        if not isinstance(Q[k], (bool, np.bool_)):
            raise ValueError(f'{k}={Q[k]!r} must be a bool')
        Q[k] = bool(Q[k])
    for k, v in Q.items():
        if k in _OPTIONS or k in _BOOLS or k in _STRINGS or k in ('start', 'end') or k in fgf.DEFAULTS:
            continue
        v = float(v)
        if math.isnan(v):
            raise ValueError(f'{k} is NaN')
        mv = _MINVAL.get(k, 0.0)
        if v < mv:
            raise ValueError(f'{k}={v!r} is below the Pine minval {mv}')
    if Q['minAlignedZones'] > 6:
        raise ValueError('minAlignedZones maxval is 6')
    if Q['partPct'] > 100:
        raise ValueError('partPct maxval is 100')
    if Q['priorDriftBars'] > 500:
        raise ValueError('priorDriftBars > max_bars_back = 500: TradingView would stop with a runtime error')
    return Q


def _split(params):
    """One dict of Pine inputs -> resolved full dict (DEFAULTS overridden)."""
    Q = dict(DEFAULTS)
    seen = {}
    for k, v in (params or {}).items():
        kk = _norm_key(k)
        if kk in DISPLAY_KEYS:
            continue
        if kk not in DEFAULTS:
            raise ValueError(f'unknown input {k!r}')
        if kk in seen and seen[kk] != v:
            raise ValueError(f'{k!r} given twice with different values (alias of {kk!r})')
        seen[kk] = v
        Q[kk] = v
    return Q


# ----------------------------------------------------------------------------------------------
# timeframes and bars
# ----------------------------------------------------------------------------------------------
def tf_parse(tf):
    """Pine timeframe string -> (unit, n), unit in 'S', 'm', 'D', 'W', 'M'."""
    s = str(tf).strip().upper()
    if s == '':
        raise ValueError('empty timeframe')
    if s.isdigit():
        return 'm', int(s)
    unit, num = s[-1], s[:-1]
    if unit not in 'SDWMH':
        raise ValueError(f'bad timeframe {tf!r}')
    n = int(num) if num else 1
    if unit == 'H':
        return 'm', 60 * n
    return unit, n


def tf_seconds(tf):
    """timeframe.in_seconds(); a month = 2,628,003 s (Pine)."""
    u, n = tf_parse(tf)
    return n * {'S': 1, 'm': 60, 'D': 86400, 'W': 604800, 'M': 2628003}[u]


def tf_from_seconds(s):
    """timeframe.from_seconds() for the values this script can produce (2x / 4x a chart)."""
    s = int(s)
    if s < 60:
        return f'{s}S'
    if s % 86400 == 0 and s < 7 * 86400:
        return 'D' if s == 86400 else f'{s // 86400}D'
    if s % 60 == 0 and s // 60 < 1440:
        return str(s // 60)
    raise ValueError(f'timeframe.from_seconds({s}) not supported by this replica')


def tf_name(tf):
    u, n = tf_parse(tf)
    if u == 'm':
        return str(n)
    if u == 'S':
        return f'{n}S'
    return u if n == 1 else f'{n}{u}'


_CHART = {}


def load_chart(pair, tf):
    key = (pair, tf_name(tf))
    if key not in _CHART:
        f = os.path.join(DATA, f'{pair}_{tf_name(tf)}.parquet')
        t = pq.read_table(f, columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
        d = {}
        for c in t.column_names:
            d[c] = np.ascontiguousarray(t.column(c).to_numpy(),
                                        dtype=np.int64 if c.startswith('t_') else np.float64)
        _CHART[key] = d
    return _CHART[key]


_TFBARS = {}


def _daily_reset_minutes(pair, m):
    """Minute bars of m minutes from the 1-minute file, restarting at 00:00 UTC every day (TradingView
    builds intraday bars from the session start; BTC's session is the UTC day). The last bar of a
    day is truncated at 24:00 (t_close = next midnight)."""
    b = load_chart(pair, '1')
    to = b['t_open']
    day = (to // 86400) * 86400
    s = m * 60
    o = day + ((to - day) // s) * s
    c = np.minimum(o + s, day + 86400)
    brk = np.flatnonzero(np.diff(o) != 0) + 1
    st = np.concatenate([[0], brk])
    en = np.concatenate([brk, [len(o)]]) - 1
    return {'open': b['open'][st].copy(), 'high': np.maximum.reduceat(b['high'], st),
            'low': np.minimum.reduceat(b['low'], st), 'close': b['close'][en].copy(),
            't_open': o[st].copy(), 't_close': c[st].copy()}


def tf_bars(pair, tf):
    """Bars of a zone / parent timeframe; None for seconds (no data)."""
    u, n = tf_parse(tf)
    if u == 'S':
        return None
    key = (pair, tf_name(tf))
    if key in _TFBARS:
        return _TFBARS[key]
    fpath = os.path.join(DATA, f'{pair}_{tf_name(tf)}.parquet')
    if os.path.exists(fpath):
        b = load_chart(pair, tf)
    elif u == 'm' and pair == 'BTC' and 1440 % n != 0:
        b = _daily_reset_minutes(pair, n)            # V17
    else:
        fb = fgf._bars(pair, tf)
        b = {k: fb[k] for k in ('open', 'high', 'low', 'close', 't_open', 't_close')}
    _TFBARS[key] = b
    return b


# ----------------------------------------------------------------------------------------------
# indicators (numba)
# ----------------------------------------------------------------------------------------------
@njit(cache=True)
def _atr_k(high, low, close, length):
    """ta.atr(length): RMA of the true range (bar 0: high - low), seeded with the plain mean of the
    first `length` true ranges."""
    n = close.shape[0]
    out = np.full(n, np.nan)
    if n < length:
        return out
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        a = high[i] - low[i]
        b = abs(high[i] - close[i - 1])
        c = abs(low[i] - close[i - 1])
        m = a if a > b else b
        tr[i] = m if m > c else c
    s = 0.0
    for i in range(length):
        s += tr[i]
    v = s / length
    out[length - 1] = v
    al = 1.0 / length
    for i in range(length, n):
        v = al * tr[i] + (1.0 - al) * v
        out[i] = v
    return out


@njit(cache=True)
def _tdi_dir_k(close, rsi_len, fast_len):
    """tdiDir()'s d: r = ta.rsi(close, rsiLen) (Wilder: up / down RMA of the changes, seeded with the
    mean of the first rsiLen changes; down == 0 -> 100, up == 0 -> 0); f = ta.sma(r, fastLen) (na while
    the window holds an na); d = f > f[1] ? 1 : f < f[1] ? -1 : 0 (a comparison with na is false)."""
    n = close.shape[0]
    r = np.full(n, np.nan)
    if n > rsi_len:
        up = 0.0
        dn = 0.0
        for i in range(1, rsi_len + 1):
            ch = close[i] - close[i - 1]
            if ch > 0:
                up += ch
            elif ch < 0:
                dn -= ch
        up /= rsi_len
        dn /= rsi_len
        al = 1.0 / rsi_len
        for i in range(rsi_len, n):
            if i > rsi_len:
                ch = close[i] - close[i - 1]
                u = ch if ch > 0 else 0.0
                dd = -ch if ch < 0 else 0.0
                up = al * u + (1.0 - al) * up
                dn = al * dd + (1.0 - al) * dn
            if dn == 0.0:
                r[i] = 100.0
            elif up == 0.0:
                r[i] = 0.0
            else:
                r[i] = 100.0 - 100.0 / (1.0 + up / dn)
    f = np.full(n, np.nan)
    for i in range(fast_len - 1, n):
        s = 0.0
        bad = False
        for j in range(i - fast_len + 1, i + 1):
            if np.isnan(r[j]):
                bad = True
                break
            s += r[j]
        if not bad:
            f[i] = s / fast_len
    d = np.zeros(n, np.int8)
    for i in range(1, n):
        if f[i] > f[i - 1]:
            d[i] = 1
        elif f[i] < f[i - 1]:
            d[i] = -1
    return d


@njit(cache=True)
def _signal_k(close, atr14, tz_buy, tz_sell, pside, pt, spread_pts, unit_atr, burst_atr, holdfav_atr,
              burst_pts_in, holdfav_pts_in, use_burst, any_combo, drift_bars, use_drift, hold_bars,
              one_per_bar):
    """L1003-1165 bar by bar from the first bar of the chart data: burst, prior drift, candidates, the
    entry hold (var state) and buySignal / sellSignal. The entry PRICE is computed in simulate()."""
    n = close.shape[0]
    bs = np.zeros(n, np.bool_)
    ss = np.zeros(n, np.bool_)
    half = spread_pts * pt * 0.5
    hold_active = False
    hold_is_buy = False
    hold_bar = -1
    hold_mid = np.nan
    last_entry = -1                        # na
    prev_mid = np.nan
    for i in range(n):
        bid = close[i] - half
        ask = close[i] + half
        mid = (bid + ask) * 0.5
        atr_pts = atr14[i] / pt
        if unit_atr:
            burst_thr = burst_atr * atr_pts
            hold_fav = holdfav_atr * atr_pts
        else:
            burst_thr = burst_pts_in
            hold_fav = holdfav_pts_in
        burst = (mid - prev_mid) / pt                      # na on the first bar
        if i >= drift_bars:
            mid_d = ((close[i - drift_bars] - half) + (close[i - drift_bars] + half)) * 0.5
            drift = (mid - mid_d) / pt
        else:
            drift = np.nan
        prev_mid = mid
        burst_buy = burst >= burst_thr
        burst_sell = burst <= -burst_thr
        prior_buy = (not use_drift) or drift > 0
        prior_sell = (not use_drift) or drift < 0
        if any_combo:
            raw_b = tz_buy[i] and ((not use_burst) or burst_buy or pside[i] == 1)
            raw_s = tz_sell[i] and ((not use_burst) or burst_sell or pside[i] == -1)
        else:
            raw_b = tz_buy[i] and burst_buy
            raw_s = tz_sell[i] and burst_sell
        buy_c = raw_b and prior_buy
        sell_c = raw_s and prior_sell
        can_fire = (not one_per_bar) or last_entry < 0 or last_entry != i
        if buy_c and can_fire:
            if hold_bars == 0:
                bs[i] = True
                last_entry = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = True
                hold_bar = i
                hold_mid = mid
            elif hold_is_buy:
                el = i - hold_bar
                mv = (mid - hold_mid) / pt
                if el >= hold_bars and mv >= hold_fav:
                    bs[i] = True
                    last_entry = i
                    hold_active = False
        if sell_c and can_fire:
            if hold_bars == 0:
                ss[i] = True
                last_entry = i
            elif not hold_active:
                hold_active = True
                hold_is_buy = False
                hold_bar = i
                hold_mid = mid
            elif not hold_is_buy:
                el = i - hold_bar
                mv = (hold_mid - mid) / pt
                if el >= hold_bars and mv >= hold_fav:
                    ss[i] = True
                    last_entry = i
                    hold_active = False
        if hold_active and ((hold_is_buy and not tz_buy[i]) or ((not hold_is_buy) and not tz_sell[i])):
            hold_active = False
            hold_bar = -1
            hold_mid = np.nan
    return bs, ss


# ----------------------------------------------------------------------------------------------
# zones (request.security on history)
# ----------------------------------------------------------------------------------------------
_DIRS = {}


def tdi_dir_series(pair, tf, rsi_len, fast_len):
    """(t_open, t_close, d) of timeframe tf, d from its own first bar; None for seconds."""
    key = (pair, tf_name(tf), int(rsi_len), int(fast_len))
    if key not in _DIRS:
        b = tf_bars(pair, tf)
        _DIRS[key] = None if b is None else (b['t_open'], b['t_close'],
                                             _tdi_dir_k(b['close'], int(rsi_len), int(fast_len)))
    return _DIRS[key]


def _gather(d, idx):
    out = np.full(len(idx), np.nan)
    ok = idx >= 0
    out[ok] = d[idx[ok]]
    return out


def map_lookahead_off(src_tc, dst_tc):
    """request.security(..., lookahead_off): the last source bar whose close time <= the chart bar's
    close time (index, -1 = none)."""
    return np.searchsorted(src_tc, dst_tc, side='right') - 1


def map_lookahead_on_prev(src_to, dst_to):
    """request.security(..., expr[1], lookahead_on): the source bar that contains the chart bar's open,
    then the bar before it (index, -1 = none)."""
    k = np.searchsorted(src_to, dst_to, side='right') - 1
    return np.where(k >= 1, k - 1, -1)


def zone_inputs(Q, chart_tf):
    """Effective parent / zone timeframes (L354-358)."""
    csec = tf_seconds(chart_tf)
    if Q['autoTf']:
        par = tf_name(chart_tf)
        z = [tf_name(chart_tf), tf_from_seconds(2 * csec), tf_from_seconds(4 * csec)]
    else:
        par = Q['tdiParentTf']
        z = [Q['zoneTf1'], Q['zoneTf2'], Q['zoneTf3']]
    z += [Q['zoneTf4'], Q['zoneTf5'], Q['zoneTf6']]
    return par, z


def trade_zone(pair, chart_tf, cb, Q):
    """tradeZoneBuyAllowed / tradeZoneSellAllowed / parentSide on every bar of the chart file."""
    n = len(cb['t_close'])
    csec = tf_seconds(chart_tf)
    par_tf, ztf = zone_inputs(Q, chart_tf)
    rl, fl = Q['tdiRsiLen'], Q['tdiFastLen']
    ds = tdi_dir_series(pair, par_tf, rl, fl)
    if ds is None:
        parent = np.full(n, np.nan)
    else:
        parent = _gather(ds[2], map_lookahead_off(ds[1], cb['t_close']))
    pside = np.where(parent > 0, 1, np.where(parent < 0, -1, 0)).astype(np.int64)   # na -> 0
    active = np.zeros(n, np.int64)
    aligned = np.zeros(n, np.int64)
    zdirs = []
    for zi in range(6):
        use = Q[f'useZone{zi + 1}']
        tf = ztf[zi]
        ds = tdi_dir_series(pair, tf, rl, fl)
        if ds is None:
            zd = np.full(n, np.nan)
        elif Q['htfNoRepaint'] and tf_seconds(tf) > csec:
            zd = _gather(ds[2], map_lookahead_on_prev(ds[0], cb['t_open']))      # z?DirP
        else:
            zd = _gather(ds[2], map_lookahead_off(ds[1], cb['t_close']))         # z?Dir0
        zdirs.append(zd)
        if not use:
            continue
        on = np.ones(n, bool) if not Q['ignoreNaZones'] else ~np.isnan(zd)
        active += on
        aligned += on & (pside != 0) & (zd == pside)
    required = np.minimum(Q['minAlignedZones'], active)
    flat_ok = Q['allowNeutralParent'] & (pside == 0)
    ready = (active == 0) | (aligned >= required)
    if Q['useTdiTradeZone']:
        tzb = ((pside == 1) | flat_ok) & ready
        tzs = ((pside == -1) | flat_ok) & ready
    else:
        tzb = np.ones(n, bool)
        tzs = np.ones(n, bool)
    return dict(tz_buy=np.ascontiguousarray(tzb), tz_sell=np.ascontiguousarray(tzs), pside=pside,
                active=active, aligned=aligned, parent_tf=par_tf, zone_tfs=ztf)


_ATR = {}


def chart_atr(pair, tf, length):
    key = (pair, tf_name(tf), int(length))
    if key not in _ATR:
        b = load_chart(pair, tf)
        _ATR[key] = _atr_k(b['high'], b['low'], b['close'], int(length))
    return _ATR[key]


_SIG = {}
_SIG_KEYS = ('spreadPoints', 'entryHoldBars', 'entryHoldMinFavPoints', 'oneEntryPerBar', 'DistUnit',
             'burstAtrMult', 'holdFavAtrMult', 'burstPointsInput', 'useBurstGate', 'useAnyCombo', 'priorDriftBars',
             'usePriorFilter', 'useTdiTradeZone', 'tdiParentTf', 'tdiRsiLen', 'tdiFastLen', 'minAlignedZones',
             'allowNeutralParent', 'ignoreNaZones', 'htfNoRepaint', 'useZone1', 'zoneTf1', 'useZone2', 'zoneTf2',
             'useZone3', 'zoneTf3', 'useZone4', 'zoneTf4', 'useZone5', 'zoneTf5', 'useZone6', 'zoneTf6', 'autoTf')


def chart_signals(pair, chart_tf, Q):
    """buySignal / sellSignal on every bar of the chart file (from its first bar)."""
    key = (pair, tf_name(chart_tf)) + tuple(Q[k] for k in _SIG_KEYS)
    if key in _SIG:
        return _SIG[key]
    cb = load_chart(pair, chart_tf)
    Z = trade_zone(pair, chart_tf, cb, Q)
    atr14 = chart_atr(pair, chart_tf, 14)
    bs, ss = _signal_k(cb['close'], atr14, Z['tz_buy'], Z['tz_sell'], Z['pside'], MINTICK,
                       float(Q['spreadPoints']), Q['DistUnit'] == 'ATR', float(Q['burstAtrMult']),
                       float(Q['holdFavAtrMult']), float(Q['burstPointsInput']), float(Q['entryHoldMinFavPoints']),
                       bool(Q['useBurstGate']), bool(Q['useAnyCombo']), int(Q['priorDriftBars']),
                       bool(Q['usePriorFilter']), int(Q['entryHoldBars']), bool(Q['oneEntryPerBar']))
    out = dict(buy=bs, sell=ss, Z=Z)
    if len(_SIG) > 24:
        _SIG.clear()
    _SIG[key] = out
    return out


_PERM = {}


def permissions(pair, chart_tf, start, end, fgfp):
    key = (pair, tf_name(chart_tf), start, end, tuple(sorted((k, repr(v)) for k, v in fgfp.items())))
    if key not in _PERM:
        _PERM[key] = fgf.fgf_permissions(pair, tf_name(chart_tf), start, end, fgfp)
    return _PERM[key]


# ----------------------------------------------------------------------------------------------
# the 1-minute sub-bars of the chart bars (path 'mag')
# ----------------------------------------------------------------------------------------------
def sub_bars(pair, chart_tf, w0, w1, check=True):
    """The 1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close). Returns (ptr, o, h, l, c, t_open): ptr
    int64 (n + 1); the sub-bars of window bar k are the rows [ptr[k], ptr[k+1]) of the five arrays. With check,
    every chart bar has at least one sub-bar, no two chart bars share one, and the chart bar's OHLC equals its
    sub-bars' first open / highest high / lowest low / last close (build_bars.py built the chart bars from them)."""
    b = load_chart(pair, chart_tf)
    m = load_chart(pair, '1')
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
        if P['pair'] == 'TEST':
            raise ValueError("injected arrays have no 1-minute data: pass sub= to simulate()")
        key = (P['pair'], P['tf'], int(P['w0']), int(P['w1']))
        if key not in _SUB:
            _SUB[key] = sub_bars(P['pair'], P['tf'], P['w0'], P['w1'])
        P['sub'] = _SUB[key]
    return P['sub']


def fake_sub_bars(P):
    """One sub-bar per chart bar, equal to the bar (tests: 'mag' on it == 'tv')."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), P['o'], P['h'], P['l'], P['c'], P['t_open'])


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, np.int64))


def clear_cache(bars=False):
    """Drop the signal / filter / sub-bar caches (and the bar caches with bars=True)."""
    _SIG.clear()
    _PERM.clear()
    _SUB.clear()
    _ATR.clear()
    if bars:
        _CHART.clear()
        _TFBARS.clear()
        _DIRS.clear()


# ----------------------------------------------------------------------------------------------
# broker + strategy run (numba). State lives in small arrays so that helpers can mutate it.
# ----------------------------------------------------------------------------------------------
# open trade, floats
T_E, T_Q, T_R1, T_R2, T_SL, T_TP, T_A, T_OFF, T_BEST, T_EQB, T_COST, T_GROSS, T_XVAL, T_PPX, T_PQTY, \
    T_SLD = range(16)
NT_F = 16
# open trade, ints
I_POS, I_EBAR, I_HSL, I_HTP, I_HTR, I_ARM, I_BEM, I_SIG, I_SBAR, I_ETYP, I_GAP, I_REV, I_PKIND, I_PBAR, \
    I_BEF, I_BENT, I_ROWS, I_TID, I_SLLT, I_X1 = range(20)
NT_I = 20
# globals (floats)
G_CASH, G_SLIP, G_CFIX, G_CPCT, G_SLPAID, G_PT, G_PV, G_MAXNX = range(8)
NG = 8
# counters (ints)
C_NT, C_PLACED, C_REPL, C_FILLED, C_CANC, C_OCA, C_BOTH, C_GAP, C_ZQ, C_SLLT, C_NEG, C_RAWL, C_RAWS, \
    C_BLKL, C_BLKS, C_NPOS, C_SEQ, C_TID, C_LOG, C_ASSERT, C_BEN = range(21)
NC = 21
# trade output columns
OF_EPX, OF_QTY, OF_XPX, OF_GROSS, OF_COST, OF_EQB, OF_SLD, OF_SLPX, OF_TPPX, OF_PPX, OF_PQTY = range(11)
NOF = 11
OI_DIR, OI_SIG, OI_SBAR, OI_EBAR, OI_XBAR, OI_ETYP, OI_KIND, OI_PKIND, OI_PBAR, OI_REV, OI_GAP, OI_BE, \
    OI_BENT, OI_ROWS, OI_SLLT = range(15)
NOI = 15
# config ints / floats
CI_MODE, CI_PARTIAL, CI_TRAIL, CI_RUNBE, CI_INV, CI_ALLOWL, CI_ALLOWS, CI_EXOPP, CI_ALLOWREV, CI_EVB, \
    CI_MAXBARS, CI_RISK, CI_FULL = range(13)
NCI = 13
CF_PT, CF_PIP, CF_SLPIPS, CF_TPRPIPS, CF_RUNPIPS, CF_ACTPIPS, CF_TRPIPS, CF_SLPTS, CF_TPPTS, CF_SLATR, CF_TPR, \
    CF_ACTPTS, CF_TRPTS, CF_ACTATR, CF_DSTATR, CF_RUNATR, CF_RUNPTS, CF_PART, CF_FIXQ, CF_RISK, CF_MAXQ, \
    CF_STEP, CF_PV = range(23)
NCF = 23
MODE_PIPS, MODE_ATR, MODE_POINTS = 0, 1, 2
TYP_STOP, TYP_LIMIT = 0, 1
NLOG = 13      # order log: bar, slot, typ, P, qty, sig, lsl, ltp, lact, ldst, lrun, replaced, seq


@njit(cache=True)
def _rem(T):
    """The open quantity (strategy.position_size): the entry quantity Q while both exit orders are open (not
    q1 + q2, which can differ from Q by one ulp), else the quantity of the one left (reconcile r0)."""
    if T[T_R1] > 0.0 and T[T_R2] > 0.0:
        return T[T_Q]
    return T[T_R1] + T[T_R2]


@njit(cache=True)
def _finish(T, TI, CNT, OF, OI, kind, k):
    i = CNT[C_NT]
    if i >= OF.shape[0]:
        raise RuntimeError('trade capacity exceeded')
    OF[i, OF_EPX] = T[T_E]
    OF[i, OF_QTY] = T[T_Q]
    OF[i, OF_XPX] = T[T_XVAL] / T[T_Q]
    OF[i, OF_GROSS] = T[T_GROSS]
    OF[i, OF_COST] = T[T_COST]
    OF[i, OF_EQB] = T[T_EQB]
    OF[i, OF_SLD] = T[T_SLD]
    OF[i, OF_SLPX] = T[T_SL] if TI[I_HSL] == 1 else np.nan
    OF[i, OF_TPPX] = T[T_TP] if TI[I_HTP] == 1 else np.nan
    OF[i, OF_PPX] = T[T_PPX]
    OF[i, OF_PQTY] = T[T_PQTY]
    OI[i, OI_DIR] = TI[I_POS]
    OI[i, OI_SIG] = TI[I_SIG]
    OI[i, OI_SBAR] = TI[I_SBAR]
    OI[i, OI_EBAR] = TI[I_EBAR]
    OI[i, OI_XBAR] = k
    OI[i, OI_ETYP] = TI[I_ETYP]
    OI[i, OI_KIND] = kind
    OI[i, OI_PKIND] = TI[I_PKIND]
    OI[i, OI_PBAR] = TI[I_PBAR]
    OI[i, OI_REV] = TI[I_REV]
    OI[i, OI_GAP] = TI[I_GAP]
    OI[i, OI_BE] = TI[I_BEF]
    OI[i, OI_BENT] = TI[I_BENT]
    OI[i, OI_ROWS] = TI[I_ROWS]
    OI[i, OI_SLLT] = TI[I_SLLT]
    CNT[C_NT] = i + 1
    TI[I_POS] = 0
    T[T_R1] = 0.0
    T[T_R2] = 0.0


@njit(cache=True)
def _exit_fill(T, TI, G, CNT, OF, OI, which, raw, is_stop, kind, k):
    """Exit order fill of the open trade: which 1 = XL1 (its remaining quantity), 2 = XL2 / XL,
    3 = both at one price. Stop fills are booked raw - d x slippage, limit fills at raw."""
    d = TI[I_POS]
    if which == 1:
        q = T[T_R1]
    elif which == 2:
        q = T[T_R2]
    else:
        q = _rem(T)
    if is_stop:
        px = raw - d * G[G_SLIP]
        G[G_SLPAID] += G[G_SLIP] * q
    else:
        px = raw
    gross = d * q * (px - T[T_E]) * G[G_PV]
    cost = q * (G[G_CFIX] + G[G_CPCT] * px)
    G[G_CASH] += gross - cost
    T[T_GROSS] += gross
    T[T_COST] += cost
    T[T_XVAL] += q * px
    TI[I_ROWS] += 2 if which == 3 else 1
    if which == 1 or which == 3:
        T[T_R1] = 0.0
    if which == 2 or which == 3:
        T[T_R2] = 0.0
    if T[T_R1] == 0.0 and T[T_R2] == 0.0:
        _finish(T, TI, CNT, OF, OI, kind, k)
    elif TI[I_PKIND] == 0:
        TI[I_PKIND] = kind
        TI[I_PBAR] = k
        T[T_PPX] = px
        T[T_PQTY] = q


@njit(cache=True)
def _close_rem(T, TI, G, CNT, OF, OI, px, slipped, kind, k):
    """Close the whole remaining position at the booked price px (market close, reversal, end)."""
    d = TI[I_POS]
    q = _rem(T)
    if slipped:
        G[G_SLPAID] += G[G_SLIP] * q
    gross = d * q * (px - T[T_E]) * G[G_PV]
    cost = q * (G[G_CFIX] + G[G_CPCT] * px)
    G[G_CASH] += gross - cost
    T[T_GROSS] += gross
    T[T_COST] += cost
    T[T_XVAL] += q * px
    TI[I_ROWS] += 1
    T[T_R1] = 0.0
    T[T_R2] = 0.0
    _finish(T, TI, CNT, OF, OI, kind, k)


@njit(cache=True)
def _stop2(T, TI, partial):
    """XL2 (Partial style) / XL (Fixed style): the stop price in force and its kind; exists flag.
    Own stop = the breakeven price in breakeven mode, else SL; the trailing stop best -/+ offset once
    armed; the one nearer the market is in force (a tie is labelled as the trailing stop)."""
    d = TI[I_POS]
    bem = TI[I_BEM] == 1
    own_ex = bem or TI[I_HSL] == 1
    own = T[T_E] if bem else T[T_SL]
    own_kind = K_BE if bem else K_SL
    tk = K_RUN if partial else K_TRAIL
    if TI[I_HTR] == 1 and TI[I_ARM] == 1:
        trl = T[T_BEST] - d * T[T_OFF]
        if own_ex and d * own > d * trl:
            return own, own_kind, True
        return trl, tk, True
    if own_ex:
        return own, own_kind, True
    return 0.0, 0, False


@njit(cache=True)
def _trail(T, TI, x):
    """Trailing part of XL2 / XL with a price reached on a move in the trade's favour."""
    if TI[I_POS] != 0 and TI[I_HTR] == 1 and T[T_R2] > 0.0:
        d = TI[I_POS]
        if TI[I_ARM] == 1:
            if d * x > d * T[T_BEST]:
                T[T_BEST] = x
        elif d * x >= d * T[T_A]:
            TI[I_ARM] = 1
            T[T_BEST] = x


@njit(cache=True)
def _gap(T, TI, G, CNT, OF, OI, x, k, partial):
    """The open trade's exit orders at a single price x (a bar open, or the raw price of an entry
    fill, V11): stops at / beyond x fill at x (slipped), then the limit, then the trailing update."""
    if TI[I_POS] == 0:
        return False
    d = TI[I_POS]
    fired = False
    hit1 = partial and T[T_R1] > 0.0 and TI[I_HSL] == 1 and d * x <= d * T[T_SL]
    lv2, k2, ex2 = _stop2(T, TI, partial)
    hit2 = T[T_R2] > 0.0 and ex2 and d * x <= d * lv2
    if hit1 and hit2:
        _exit_fill(T, TI, G, CNT, OF, OI, 3, x, True, k2, k)
        return True
    if hit1:
        _exit_fill(T, TI, G, CNT, OF, OI, 1, x, True, K_SL, k)
        fired = True
    elif hit2:
        _exit_fill(T, TI, G, CNT, OF, OI, 2, x, True, k2, k)
        fired = True
    if TI[I_POS] == 0:
        return fired
    if TI[I_HTP] == 1 and d * x >= d * T[T_TP]:
        if partial:
            if T[T_R1] > 0.0:
                _exit_fill(T, TI, G, CNT, OF, OI, 1, x, False, K_TPP, k)
                fired = True
        elif T[T_R2] > 0.0:
            _exit_fill(T, TI, G, CNT, OF, OI, 2, x, False, K_TP, k)
            return True
    if TI[I_POS] != 0:
        _trail(T, TI, x)
    return fired


@njit(cache=True)
def _open(T, TI, SF, SI, G, CNT, OF, OI, s, raw, gap, k, partial, part_pct, use_trail):
    """Fill of the pending entry order of slot s (0 = id "Long", a buy; 1 = id "Short", a sell) at the
    raw price `raw`: reversal of an open opposite position at the booked price, the new trade's exit
    orders from its locks, OCA cancel of the other slot, then the V11 test at the raw price."""
    d = 1 if s == 0 else -1
    typ = SI[s, 1]
    slip = G[G_SLIP]
    e = raw + d * slip if typ == TYP_STOP else raw
    q = SF[s, 1]
    rev = 0
    if TI[I_POS] != 0:
        if TI[I_POS] == d:
            CNT[C_ASSERT] += 1                     # an entry on the side already held: impossible
        _close_rem(T, TI, G, CNT, OF, OI, e, typ == TYP_STOP, K_REV, k)
        rev = 1
    eqb = G[G_CASH]
    cost = q * (G[G_CFIX] + G[G_CPCT] * e)
    G[G_CASH] -= cost
    if typ == TYP_STOP:
        G[G_SLPAID] += slip * q
    if eqb > 0.0:
        nx = q * e / eqb
        if nx > G[G_MAXNX]:
            G[G_MAXNX] = nx
    pt = G[G_PT]
    lsl = SF[s, 2]
    ltp = SF[s, 3]
    lact = SF[s, 4]
    ldst = SF[s, 5]
    lrun = SF[s, 6]
    T[:] = 0.0
    TI[:] = 0
    TI[I_POS] = d
    T[T_E] = e
    T[T_Q] = q
    TI[I_EBAR] = k
    TI[I_SIG] = SI[s, 3]
    TI[I_SBAR] = SI[s, 4]
    TI[I_ETYP] = typ
    TI[I_GAP] = gap
    TI[I_REV] = rev
    T[T_EQB] = eqb
    T[T_COST] = cost
    has_sl = lsl > 0.0
    has_tp = ltp > 0.0
    TI[I_HSL] = 1 if has_sl else 0
    TI[I_HTP] = 1 if has_tp else 0
    T[T_SL] = e - d * lsl * pt if has_sl else np.nan
    T[T_TP] = e + d * ltp * pt if has_tp else np.nan
    T[T_SLD] = lsl * pt if has_sl else np.nan
    if partial:
        x1 = part_pct > 0.0 and (has_sl or has_tp)
        TI[I_X1] = 1 if x1 else 0
        T[T_R1] = q * part_pct / 100.0 if x1 else 0.0
        T[T_R2] = q - T[T_R1]
        htr = has_tp and not np.isnan(lrun)
        T[T_A] = T[T_TP]
        T[T_OFF] = lrun * pt
        armed = False
    else:
        T[T_R1] = 0.0
        T[T_R2] = q
        htr = use_trail and (not np.isnan(lact)) and (not np.isnan(ldst))
        T[T_A] = e + d * lact * pt
        T[T_OFF] = ldst * pt
        armed = htr and lact <= 0.0
    TI[I_HTR] = 1 if htr else 0
    TI[I_ARM] = 1 if armed else 0
    T[T_BEST] = e
    TI[I_PKIND] = 0
    TI[I_PBAR] = -1
    T[T_PPX] = np.nan
    T[T_PQTY] = 0.0
    CNT[C_TID] += 1
    TI[I_TID] = CNT[C_TID]
    o_ = 1 - s
    if SI[o_, 0] == 1:
        SI[o_, 0] = 0
        CNT[C_OCA] += 1
    SI[s, 0] = 0
    CNT[C_FILLED] += 1
    if gap:
        CNT[C_GAP] += 1
    # V11: the new trade's exits at the raw fill price (a stop inside the slippage fills at once)
    TI[I_SLLT] = 1
    fired = _gap(T, TI, G, CNT, OF, OI, raw, k, partial)
    if fired:
        CNT[C_SLLT] += 1
    elif TI[I_POS] != 0:
        TI[I_SLLT] = 0


@njit(cache=True)
def _leg(T, TI, SF, SI, G, CNT, OF, OI, cur, b, k, partial, part_pct, use_trail):
    """One straight move of price from cur to b: the open trade's exit orders and the pending entry
    orders in the order price reaches them (exits before entries at one price)."""
    if b == cur:
        return
    up = b > cur
    while True:
        pos = TI[I_POS]
        fav = False
        x_ev = 0
        x_px = 0.0
        x_kind = 0
        x_stop = False
        if pos != 0:
            d = pos
            fav = (up and d > 0) or ((not up) and d < 0)
            if fav:
                if partial:
                    has = T[T_R1] > 0.0 and TI[I_HTP] == 1
                    w = 1
                    kk = K_TPP
                else:
                    has = T[T_R2] > 0.0 and TI[I_HTP] == 1
                    w = 2
                    kk = K_TP
                if has:
                    lv = T[T_TP]
                    if (up and b >= lv) or ((not up) and b <= lv):
                        x_ev = w
                        x_px = (lv if lv > cur else cur) if up else (lv if lv < cur else cur)
                        x_kind = kk
            else:
                x_stop = True
                r1 = False
                p1 = 0.0
                if partial and T[T_R1] > 0.0 and TI[I_HSL] == 1:
                    lv = T[T_SL]
                    if (up and b >= lv) or ((not up) and b <= lv):
                        r1 = True
                        p1 = (lv if lv > cur else cur) if up else (lv if lv < cur else cur)
                r2 = False
                p2 = 0.0
                lv2, k2, ex2 = _stop2(T, TI, partial)
                if T[T_R2] > 0.0 and ex2:
                    if (up and b >= lv2) or ((not up) and b <= lv2):
                        r2 = True
                        p2 = (lv2 if lv2 > cur else cur) if up else (lv2 if lv2 < cur else cur)
                if r1 and r2:
                    if p1 == p2:
                        x_ev = 3
                        x_px = p1
                        x_kind = k2
                    elif (up and p1 < p2) or ((not up) and p1 > p2):
                        x_ev = 1
                        x_px = p1
                        x_kind = K_SL
                    else:
                        x_ev = 2
                        x_px = p2
                        x_kind = k2
                elif r1:
                    x_ev = 1
                    x_px = p1
                    x_kind = K_SL
                elif r2:
                    x_ev = 2
                    x_px = p2
                    x_kind = k2
        e_slot = -1
        e_px = 0.0
        for s in range(2):
            if SI[s, 0] != 1:
                continue
            t = SI[s, 3]
            P = SF[s, 0]
            if up and t == 1 and b >= P:
                p = P if P > cur else cur
            elif (not up) and t == -1 and b <= P:
                p = P if P < cur else cur
            else:
                continue
            if e_slot < 0 or (up and p < e_px) or ((not up) and p > e_px) or (p == e_px and SI[s, 2] < SI[e_slot, 2]):
                e_slot = s
                e_px = p
        if x_ev == 0 and e_slot < 0:
            if pos != 0 and fav:
                _trail(T, TI, b)
            return
        take_exit = x_ev != 0 and (e_slot < 0 or (up and x_px <= e_px) or ((not up) and x_px >= e_px))
        px = x_px if take_exit else e_px
        if pos != 0 and fav:
            _trail(T, TI, px)
        if take_exit:
            _exit_fill(T, TI, G, CNT, OF, OI, x_ev, px, x_stop, x_kind, k)
        else:
            _open(T, TI, SF, SI, G, CNT, OF, OI, e_slot, px, 0, k, partial, part_pct, use_trail)
        cur = px


@njit(cache=True)
def _walk(T, TI, SF, SI, G, CNT, OF, OI, o, h, l, c, k, partial, part_pct, use_trail):
    """A3 + A4 + B on one price bar (the chart bar on path 'tv')."""
    if TI[I_POS] != 0:
        _gap(T, TI, G, CNT, OF, OI, o, k, partial)
    sel = -1
    for s in range(2):
        if SI[s, 0] == 1:
            t = SI[s, 3]
            P = SF[s, 0]
            if (t == 1 and o >= P) or (t == -1 and o <= P):
                if sel < 0 or SI[s, 2] < SI[sel, 2]:
                    sel = s
    if sel >= 0:
        _open(T, TI, SF, SI, G, CNT, OF, OI, sel, o, 1, k, partial, part_pct, use_trail)
    if (h - o) < (o - l):
        v1 = h
        v2 = l
    else:
        v1 = l
        v2 = h
    for j in range(3):
        if j == 0:
            a = o
            b = v1
        elif j == 1:
            a = v1
            b = v2
        else:
            a = v2
            b = c
        if TI[I_POS] == 0 and SI[0, 0] == 0 and SI[1, 0] == 0:
            return                                    # nothing left that this bar can fill
        _leg(T, TI, SF, SI, G, CNT, OF, OI, a, b, k, partial, part_pct, use_trail)


@njit(cache=True)
def _idle(T, TI, SF, SI, h, l, partial):
    """True when nothing can happen on a bar (a pure shortcut, same results): no pending entry within the
    bar's range and, if a trade is open, no exit level, target, trail activation or new trail extreme
    inside it (the open lies inside the range, so its gap tests are covered)."""
    pos = TI[I_POS]
    if pos != 0:
        d = pos
        lo = l if d > 0 else -h          # adverse extreme in long space
        hi = h if d > 0 else -l          # favourable extreme in long space
        if partial and T[T_R1] > 0.0 and TI[I_HSL] == 1 and lo <= d * T[T_SL]:
            return False
        if T[T_R2] > 0.0:
            lv2, k2, ex2 = _stop2(T, TI, partial)
            if ex2 and lo <= d * lv2:
                return False
            if TI[I_HTR] == 1:
                if TI[I_ARM] == 1:
                    if hi > d * T[T_BEST]:
                        return False
                elif hi >= d * T[T_A]:
                    return False
        if TI[I_HTP] == 1 and ((partial and T[T_R1] > 0.0) or ((not partial) and T[T_R2] > 0.0)) and hi >= d * T[T_TP]:
            return False
    for s in range(2):
        if SI[s, 0] == 1:
            if SI[s, 3] == 1:
                if h >= SF[s, 0]:
                    return False
            elif l <= SF[s, 0]:
                return False
    return True


@njit(cache=True)
def _calc_qty(sl_ticks, equity, CI, CF):
    """calcQty() L1188-1196."""
    q = CF[CF_FIXQ]
    if CI[CI_RISK] == 1:
        risk_cash = equity * CF[CF_RISK] / 100.0
        stop_cash = sl_ticks * CF[CF_PT] * CF[CF_PV]
        if stop_cash > 0.0:
            q = risk_cash / stop_cash
        else:
            q = 0.0
    if CF[CF_MAXQ] < q:
        q = CF[CF_MAXQ]
    q = math.floor(q / CF[CF_STEP] + 1e-9) * CF[CF_STEP]
    return q


@njit(cache=True)
def _geometry(atr14k, atrlk, CI, CF):
    """slTicksNow, tpTicksNow, trailActNow, trailDstNow, runDstNow (L1168-1184) on one bar."""
    pt = CF[CF_PT]
    mode = CI[CI_MODE]
    atr_pts = atr14k / pt
    pip_ticks = CF[CF_PIP] / pt
    if mode == MODE_POINTS:
        sl = CF[CF_SLPTS]
        tp = CF[CF_TPPTS]
        act = CF[CF_ACTPTS]
        dst = CF[CF_TRPTS]
        run = CF[CF_RUNPTS]
    elif mode == MODE_PIPS:
        sl = CF[CF_SLPIPS] * pip_ticks
        tp = np.nan if np.isnan(sl) else sl * CF[CF_TPRPIPS]
        act = CF[CF_ACTPIPS] * pip_ticks
        x = CF[CF_TRPIPS] * pip_ticks
        dst = np.nan if np.isnan(x) else (x if x > 1.0 else 1.0)
        x = CF[CF_RUNPIPS] * pip_ticks
        run = np.nan if np.isnan(x) else (x if x > 1.0 else 1.0)
    else:
        sl = np.nan if np.isnan(atrlk) else CF[CF_SLATR] * atrlk / pt
        tp = np.nan if np.isnan(sl) else sl * CF[CF_TPR]
        act = CF[CF_ACTATR] * atr_pts
        x = CF[CF_DSTATR] * atr_pts
        dst = np.nan if np.isnan(x) else (x if x > 1.0 else 1.0)
        x = CF[CF_RUNATR] * atrlk / pt
        run = np.nan if np.isnan(x) else (x if x > 1.0 else 1.0)
    return sl, tp, act, dst, run


@njit(cache=True)
def _decide(pos, equity, bsig, ssig, bok, sok, bpx, spx, atr14k, atrlk, CI, CF, out):
    """C1-C4 of one script run: the opposite-signal close and the two entry blocks, in the Pine's order.
    out[2, 11] receives the orders placed (valid, slot, typ, price, qty, sig, lsl, ltp, lact, ldst, lrun).
    Returns (close_req, n_orders, rawL, rawS, blockedL, blockedS, zero_qty)."""
    inv = CI[CI_INV] == 1
    in_long = pos > 0
    in_short = pos < 0
    flat = pos == 0
    nl = in_short if inv else in_long
    ns = in_long if inv else in_short
    allow_l = CI[CI_ALLOWL] == 1
    allow_s = CI[CI_ALLOWS] == 1
    eo = CI[CI_EXOPP] == 1
    close_req = 0
    if eo and ssig and nl:
        close_req = K_OPP
    if eo and bsig and ns:
        close_req = K_OPP
    gate = flat or CI[CI_ALLOWREV] == 1 or eo
    raw_l = bsig and allow_l and (not nl) and gate
    raw_s = ssig and allow_s and (not ns) and gate
    nord = 0
    zq = 0
    if (raw_l and bok) or (raw_s and sok):
        sl, tp, act, dst, run = _geometry(atr14k, atrlk, CI, CF)
        if raw_l and bok:
            q = _calc_qty(sl, equity, CI, CF)
            if q > 0.0 and not np.isnan(bpx):
                out[nord, 0] = 1.0
                out[nord, 1] = 1.0 if inv else 0.0
                out[nord, 2] = TYP_LIMIT if inv else TYP_STOP
                out[nord, 3] = bpx
                out[nord, 4] = q
                out[nord, 5] = 1.0
                out[nord, 6] = sl
                out[nord, 7] = tp
                out[nord, 8] = act
                out[nord, 9] = dst
                out[nord, 10] = run
                nord += 1
            else:
                zq += 1
        if raw_s and sok:
            q = _calc_qty(sl, equity, CI, CF)
            if q > 0.0 and not np.isnan(spx):
                out[nord, 0] = 1.0
                out[nord, 1] = 0.0 if inv else 1.0
                out[nord, 2] = TYP_LIMIT if inv else TYP_STOP
                out[nord, 3] = spx
                out[nord, 4] = q
                out[nord, 5] = -1.0
                out[nord, 6] = sl
                out[nord, 7] = tp
                out[nord, 8] = act
                out[nord, 9] = dst
                out[nord, 10] = run
                nord += 1
            else:
                zq += 1
    return (close_req, nord, 1 if raw_l else 0, 1 if raw_s else 0, 1 if (raw_l and not bok) else 0,
            1 if (raw_s and not sok) else 0, zq)


@njit(cache=True)
def _kernel(o, h, l, c, bsig, ssig, bok, sok, bpx, spx, atr14, atrl, CI, CF, G, mid_j, cap, log_cap,
            mag, ptr, sb_o, sb_h, sb_l, sb_c):
    """A, B, C, D of every window bar. mag: the price orders (A3, A4, B) walk the sub-bars [ptr[k], ptr[k+1])
    of chart bar k (sb_o / sb_h / sb_l / sb_c), each with its own open and rule-4 path; A1 (market closes)
    stays at the chart bar's open and C (the script run, the breakeven flag from h[k] / l[k]) at its close."""
    n = o.shape[0]
    partial = CI[CI_PARTIAL] == 1
    use_trail = CI[CI_TRAIL] == 1
    part_pct = CF[CF_PART]
    pt = CF[CF_PT]
    full = CI[CI_FULL] == 1
    T = np.zeros(NT_F)
    TI = np.zeros(NT_I, np.int64)
    SF = np.zeros((2, 7))
    SI = np.zeros((2, 5), np.int64)
    CNT = np.zeros(NC, np.int64)
    OF = np.zeros((cap, NOF))
    OI = np.zeros((cap, NOI), np.int64)
    LG = np.zeros((log_cap, NLOG))
    lock = np.full((2, 5), np.nan)         # lockSl/Tp/Act/Dst/Run per id (0 = L, 1 = S)
    placed = np.full(2, -1, np.int64)      # placedBarL / S (-1 = na)
    trade_id = np.full(2, -1, np.int64)    # tradeIdL / S
    tp_hit = np.zeros(2, np.bool_)         # tpHitL / S
    buf = np.zeros((2, 11))
    eq_close = np.zeros(n if full else 1)
    pos_close = np.zeros(n if full else 1, np.int64)
    close_req = 0
    init = G[G_CASH]
    dd_pk = init
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init
    min_eq = init
    evb = CI[CI_EVB]
    maxb = CI[CI_MAXBARS]
    run_be = CI[CI_RUNBE] == 1
    for k in range(n):
        # A1: market close sent by the previous run
        if close_req != 0:
            if TI[I_POS] != 0:
                _close_rem(T, TI, G, CNT, OF, OI, o[k] - TI[I_POS] * G[G_SLIP], True, close_req, k)
            close_req = 0
        # A3, A4, B (skipped when nothing inside the bar's range can fill or move a trail; the same test holds
        # for every sub-bar, whose range lies inside the chart bar's)
        if not _idle(T, TI, SF, SI, h[k], l[k], partial):
            if mag:
                for m in range(ptr[k], ptr[k + 1]):
                    if TI[I_POS] == 0 and SI[0, 0] == 0 and SI[1, 0] == 0:
                        break                      # flat, nothing pending: nothing can happen before the close
                    if not _idle(T, TI, SF, SI, sb_h[m], sb_l[m], partial):
                        _walk(T, TI, SF, SI, G, CNT, OF, OI, sb_o[m], sb_h[m], sb_l[m], sb_c[m], k, partial,
                              part_pct, use_trail)
            else:
                _walk(T, TI, SF, SI, G, CNT, OF, OI, o[k], h[k], l[k], c[k], k, partial, part_pct, use_trail)
        # C: the script run at the close
        pos = TI[I_POS]
        rem = _rem(T)
        equity = G[G_CASH] + (pos * rem * (c[k] - T[T_E]) * G[G_PV] if pos != 0 else 0.0)
        if bsig[k] or ssig[k]:
            cr, nord, rl, rs, bl, bs_, zq = _decide(pos, equity, bsig[k], ssig[k], bok[k], sok[k], bpx[k], spx[k],
                                                   atr14[k], atrl[k], CI, CF, buf)
            close_req = cr
            CNT[C_RAWL] += rl
            CNT[C_RAWS] += rs
            CNT[C_BLKL] += bl
            CNT[C_BLKS] += bs_
            CNT[C_ZQ] += zq
            for i in range(nord):
                s = int(buf[i, 1])
                if (s == 0 and pos > 0) or (s == 1 and pos < 0):
                    CNT[C_ASSERT] += 1             # an order on the side held: impossible
                rep = SI[s, 0] == 1
                if rep:
                    CNT[C_REPL] += 1
                SI[s, 0] = 1
                SI[s, 1] = int(buf[i, 2])
                SI[s, 2] = CNT[C_SEQ]
                CNT[C_SEQ] += 1
                SI[s, 3] = int(buf[i, 5])
                SI[s, 4] = k
                SF[s, 0] = buf[i, 3]
                SF[s, 1] = buf[i, 4]
                for j in range(5):
                    SF[s, 2 + j] = buf[i, 6 + j]
                    lock[s, j] = buf[i, 6 + j]
                placed[s] = k
                CNT[C_PLACED] += 1
                if CNT[C_LOG] < log_cap:
                    r = CNT[C_LOG]
                    LG[r, 0] = k
                    LG[r, 1] = s
                    LG[r, 2] = buf[i, 2]
                    LG[r, 3] = buf[i, 3]
                    LG[r, 4] = buf[i, 4]
                    LG[r, 5] = buf[i, 5]
                    for j in range(5):
                        LG[r, 6 + j] = buf[i, 6 + j]
                    LG[r, 11] = 1.0 if rep else 0.0
                    LG[r, 12] = SI[s, 2]
                CNT[C_LOG] += 1
        in_long = pos > 0
        in_short = pos < 0
        # C5: stale-order cancel
        if evb > 0:
            if placed[0] >= 0 and (not in_long) and k - placed[0] >= evb:
                if SI[0, 0] == 1:
                    SI[0, 0] = 0
                    CNT[C_CANC] += 1
                placed[0] = -1
            if placed[1] >= 0 and (not in_short) and k - placed[1] >= evb:
                if SI[1, 0] == 1:
                    SI[1, 0] = 0
                    CNT[C_CANC] += 1
                placed[1] = -1
        # breakeven flag (whole bar's high / low, V18), reset on each new trade
        cur = TI[I_TID] if pos != 0 else -1
        if (not in_long) or trade_id[0] < 0 or cur != trade_id[0]:
            tp_hit[0] = False
            trade_id[0] = cur if in_long else -1
        if (not in_short) or trade_id[1] < 0 or cur != trade_id[1]:
            tp_hit[1] = False
            trade_id[1] = cur if in_short else -1
        if in_long and lock[0, 1] > 0.0 and h[k] >= T[T_E] + lock[0, 1] * pt:
            tp_hit[0] = True
        if in_short and lock[1, 1] > 0.0 and l[k] <= T[T_E] - lock[1, 1] * pt:
            tp_hit[1] = True
        # C6: XL2 / XS2 in breakeven mode from the next bar
        if partial and run_be and pos != 0 and TI[I_BEM] == 0:
            if (in_long and tp_hit[0]) or (in_short and tp_hit[1]):
                TI[I_BEM] = 1
                TI[I_BEF] = 1
                if T[T_R2] > 0.0 and (T[T_R1] > 0.0 or (TI[I_X1] == 0 and TI[I_ARM] == 0)):
                    TI[I_BENT] = 1
                    CNT[C_BEN] += 1
        # C7: time stop
        if maxb > 0 and pos != 0 and k - TI[I_EBAR] >= maxb:
            if close_req == 0:
                close_req = K_TIME
        # D: bar-close equity
        if pos != 0:
            CNT[C_NPOS] += 1
        if SI[0, 0] == 1 and SI[1, 0] == 1:
            CNT[C_BOTH] += 1
        if equity <= 0.0:
            CNT[C_NEG] += 1
        if equity < min_eq:
            min_eq = equity
        if full:
            eq_close[k] = equity
            pos_close[k] = pos
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
    # end of the window: pending orders and a close sent by the last run are dropped; an open trade
    # is closed at the last close as a market fill
    unfilled = 1 if (SI[0, 0] == 1 or SI[1, 0] == 1) else 0
    if n > 0:
        if TI[I_POS] != 0:
            k = n - 1
            _close_rem(T, TI, G, CNT, OF, OI, c[k] - TI[I_POS] * G[G_SLIP], True, K_END, k)
        final = G[G_CASH]
        if full:
            eq_close[n - 1] = final
        if final > dd_pk:
            dd_pk = final
        x = (dd_pk - final) / dd_pk
        if x > dd_rel:
            dd_rel = x
        x = dd_pk - final
        if x > dd_abs:
            dd_abs = x
        if mid_j == n - 1:
            eq_mid = final
        if final < min_eq:
            min_eq = final
    else:
        final = init
    nt = CNT[C_NT]
    stats = np.array([final, eq_mid, dd_rel, dd_abs, min_eq, G[G_SLPAID], G[G_MAXNX], float(unfilled)])
    nlog = min(CNT[C_LOG], log_cap)
    return OF[:nt].copy(), OI[:nt].copy(), CNT, stats, eq_close, pos_close, LG[:nlog].copy()


# ----------------------------------------------------------------------------------------------
# public interface
# ----------------------------------------------------------------------------------------------
def prepare(pair, chart_tf, params=None, _perm=None):
    """Signals, zones, filter permissions and the window: everything the SIGNAL inputs decide.
    ORDER / EXIT inputs given here become simulate()'s defaults. _perm: (buyOk, sellOk) arrays to
    inject in place of the filter (tests)."""
    Q = _validate(_split(params))
    chart_tf = tf_name(chart_tf)
    cb = load_chart(pair, chart_tf)
    s0, e0 = WINDOWS[pair]
    start = int(Q['start']) if Q['start'] is not None else s0
    end = int(Q['end']) if Q['end'] is not None else e0
    tc_all = cb['t_close']
    w0 = int(np.searchsorted(tc_all, start, side='left'))
    w1 = int(np.searchsorted(tc_all, end, side='right'))
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    S = chart_signals(pair, chart_tf, Q)
    sl = slice(w0, w1)
    buy = np.ascontiguousarray(S['buy'][sl])
    sell = np.ascontiguousarray(S['sell'][sl])
    if _perm is not None:
        bok = np.ascontiguousarray(np.asarray(_perm[0], bool))
        sok = np.ascontiguousarray(np.asarray(_perm[1], bool))
        if len(bok) != n or len(sok) != n:
            raise ValueError('injected permissions do not match the window')
    elif Q['fgfOn']:
        fgfp = {k: Q[k] for k in FGF_KEYS}
        F = permissions(pair, chart_tf, start, end, fgfp)
        if F.index[0] != w0 or len(F) != n:
            raise RuntimeError('filter rows do not match the window')
        bok = np.ascontiguousarray(F['buyOk'].to_numpy(bool))
        sok = np.ascontiguousarray(F['sellOk'].to_numpy(bool))
    else:
        bok = np.ones(n, np.bool_)
        sok = np.ones(n, np.bool_)
    tc = tc_all[sl]
    mid = start + (end - start) // 2
    sigQ = {k: Q[k] for k in SIG_DEFAULTS}
    sigQ.update({k: Q[k] for k in FGF_KEYS})
    ordQ = {k: Q[k] for k in ORD_DEFAULTS}
    return dict(pair=pair, tf=chart_tf, start=start, end=end, w0=w0, w1=w1, n=n, mid=mid,
                mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
                o=cb['open'][sl], h=cb['high'][sl], l=cb['low'][sl], c=cb['close'][sl],
                t_open=cb['t_open'][sl], t_close=tc,
                buySig=buy, sellSig=sell, buyOk=bok, sellOk=sok,
                atr14=np.ascontiguousarray(chart_atr(pair, chart_tf, 14)[sl]),
                sigQ=sigQ, ordQ=ordQ, injected=_perm is not None,
                parent_tf=S['Z']['parent_tf'], zone_tfs=S['Z']['zone_tfs'],
                sig_buy=int(buy.sum()), sig_sell=int(sell.sum()))


def prepare_arrays(o, h, l, c, atr14, buySig, sellSig, buyOk=None, sellOk=None, t_open=None, t_close=None,
                   params=None, atr_len=None):
    """A P built from injected arrays (kernel tests): no data file, no filter. atr_len: dict
    {length: array} for ATR(atrLen) other than 14 (default: atr14 for every length)."""
    Q = _validate(_split(params))
    n = len(o)
    t_open = np.arange(n, dtype=np.int64) * 60 if t_open is None else np.asarray(t_open, np.int64)
    t_close = t_open + 60 if t_close is None else np.asarray(t_close, np.int64)
    f = lambda a: np.ascontiguousarray(np.asarray(a, np.float64))
    b = lambda a, dflt: np.ascontiguousarray(np.full(n, dflt, bool) if a is None else np.asarray(a, bool))
    sigQ = {k: Q[k] for k in SIG_DEFAULTS}
    sigQ.update({k: Q[k] for k in FGF_KEYS})
    P = dict(pair='TEST', tf='1', start=int(t_close[0]), end=int(t_close[-1]), w0=0, w1=n, n=n,
             mid=int(t_close[n // 2]), mid_j=n // 2, o=f(o), h=f(h), l=f(l), c=f(c), t_open=t_open,
             t_close=t_close, buySig=b(buySig, False), sellSig=b(sellSig, False), buyOk=b(buyOk, True),
             sellOk=b(sellOk, True), atr14=f(atr14), sigQ=sigQ, ordQ={k: Q[k] for k in ORD_DEFAULTS},
             injected=True, atr_other={int(k): f(v) for k, v in (atr_len or {}).items()},
             sig_buy=int(np.sum(buySig)), sig_sell=int(np.sum(sellSig)))
    return P


def _atr_len(P, length):
    if length == 14:
        return P['atr14']
    if P['pair'] == 'TEST':
        return P['atr_other'].get(int(length), P['atr14'])
    return np.ascontiguousarray(chart_atr(P['pair'], P['tf'], length)[P['w0']:P['w1']])


def _resolve_x(P, x):
    Q = dict(P['ordQ'])
    seen = {}
    for k, v in (x or {}).items():
        kk = _norm_key(k)
        if kk in DISPLAY_KEYS:
            continue
        if kk in seen and seen[kk] != v:
            raise ValueError(f'{k!r} given twice with different values (alias of {kk!r})')
        seen[kk] = v
        if kk in P['sigQ']:
            if v != P['sigQ'][kk]:
                raise ValueError(f'{kk!r} is a SIGNAL input fixed by prepare() ({P["sigQ"][kk]!r}), got {v!r}')
            continue
        if kk not in ORD_DEFAULTS:
            raise ValueError(f'unknown input {k!r}')
        Q[kk] = v
    full = dict(DEFAULTS)
    full.update(P['sigQ'])
    full.update(Q)
    _validate(full)
    return {k: full[k] for k in ORD_DEFAULTS}


def _config(P, Q):
    """The kernel configuration of the resolved ORDER / EXIT inputs Q on P: (CI, CF, G, entry prices bpx / spx,
    ATR(atrLen), partial, inv, slip). simulate() and the single-decision test (tests_fgv5 P2) use it."""
    pair = P['pair']
    cost = Q['cost']
    c_fix, c_pct = COSTS[cost]['BTC' if pair == 'TEST' else pair]
    slip = SLIPPAGE[cost]
    pt = MINTICK
    inv = bool(Q['fgvInv'])
    dirn = Q['Direction']
    allow_l = (dirn != 'Long') if inv else (dirn != 'Short')
    allow_s = (dirn != 'Short') if inv else (dirn != 'Long')
    # entry prices (L1005-1008, L1092, L1126 / L1145), only on signal bars
    half = P['sigQ']['spreadPoints'] * pt * 0.5
    ask = P['c'] + half
    bid = P['c'] - half
    if P['sigQ']['DistUnit'] == 'ATR':
        edp = Q['entryDistAtrMult'] * (P['atr14'] / pt)
    else:
        edp = np.full(P['n'], float(Q['entryDistPoints']))
    bpx = np.where(P['buySig'], ask + edp * pt, np.nan)
    spx = np.where(P['sellSig'], bid - edp * pt, np.nan)
    atrl = _atr_len(P, int(Q['atrLen']))
    partial = Q['TpStyle'] == 'Partial + runner' and Q['partPct'] < 100
    CI = np.zeros(NCI, np.int64)
    CI[CI_MODE] = {'Pips': MODE_PIPS, 'ATR': MODE_ATR, 'Points': MODE_POINTS}[Q['ExitMode']]
    CI[CI_PARTIAL] = 1 if partial else 0
    CI[CI_TRAIL] = 1 if Q['useTrail'] else 0
    CI[CI_RUNBE] = 1 if Q['runBE'] else 0
    CI[CI_INV] = 1 if inv else 0
    CI[CI_ALLOWL] = 1 if allow_l else 0
    CI[CI_ALLOWS] = 1 if allow_s else 0
    CI[CI_EXOPP] = 1 if Q['exitOnOpposite'] else 0
    CI[CI_ALLOWREV] = 1 if Q['allowReverse'] else 0
    CI[CI_EVB] = int(Q['entryValidBars'])
    CI[CI_MAXBARS] = int(Q['maxBarsHeld'])
    CI[CI_RISK] = 1 if Q['QtyMode'] == 'Risk %' else 0
    CI[CI_FULL] = 0                              # simulate() sets it
    CF = np.zeros(NCF)
    CF[CF_PT] = pt
    CF[CF_PIP] = Q['pipSize']
    CF[CF_SLPIPS] = Q['slPips']
    CF[CF_TPRPIPS] = Q['tpRPips']
    CF[CF_RUNPIPS] = Q['runTrailPips']
    CF[CF_ACTPIPS] = Q['trailActPips']
    CF[CF_TRPIPS] = Q['trailPips']
    CF[CF_SLPTS] = Q['slPoints']
    CF[CF_TPPTS] = Q['tpPoints']
    CF[CF_SLATR] = Q['slAtrMult']
    CF[CF_TPR] = Q['tpR']
    CF[CF_ACTPTS] = Q['trailActPoints']
    CF[CF_TRPTS] = Q['trailPoints']
    CF[CF_ACTATR] = Q['trailActAtr']
    CF[CF_DSTATR] = Q['trailDstAtr']
    CF[CF_RUNATR] = Q['runTrailAtr']
    CF[CF_RUNPTS] = Q['runTrailPts']
    CF[CF_PART] = Q['partPct']
    CF[CF_FIXQ] = Q['fixedQty']
    CF[CF_RISK] = Q['riskPct']
    CF[CF_MAXQ] = Q['maxQty']
    CF[CF_STEP] = Q['qtyStep']
    CF[CF_PV] = POINTVALUE
    G = np.zeros(NG)
    G[G_CASH] = INITIAL_CAPITAL
    G[G_SLIP] = slip
    G[G_CFIX] = c_fix
    G[G_CPCT] = c_pct
    G[G_PT] = pt
    G[G_PV] = POINTVALUE
    return CI, CF, G, bpx, spx, atrl, partial, inv, slip


def simulate(P, x=None, full=False, log_cap=0, sub=None):
    """Orders, exits and money on prepare()'s arrays with the ORDER / EXIT inputs x (Pine names, plus
    path, cost, inv). full=True also returns the bar-close equity / position arrays; log_cap > 0 keeps
    that many entries of the order log. sub: a sub-bar table (ptr, o, h, l, c[, t_open]) for path 'mag' in
    place of the 1-minute data (tests: fake_sub_bars, synthetic bars)."""
    Q = _resolve_x(P, x)
    mag = Q['path'] == 'mag'
    if mag:
        S = sub if sub is not None else get_sub(P)
        if len(S[0]) != P['n'] + 1:
            raise ValueError('the sub-bar table does not match the window')
    else:
        S = _NO_SUB
    CI, CF, G, bpx, spx, atrl, partial, inv, slip = _config(P, Q)
    CI[CI_FULL] = 1 if full else 0
    cap = int(P['sig_buy'] + P['sig_sell']) + 8
    OF, OI, CNT, stats, eq, posc, LG = _kernel(P['o'], P['h'], P['l'], P['c'], P['buySig'], P['sellSig'],
                                               P['buyOk'], P['sellOk'], bpx, spx, P['atr14'], atrl,
                                               CI, CF, G, int(P['mid_j']), cap, int(log_cap),
                                               bool(mag), S[0], S[1], S[2], S[3], S[4])
    if CNT[C_ASSERT] != 0:
        raise AssertionError(f'{CNT[C_ASSERT]} broker invariant violations')
    R = dict(OF=OF, OI=OI, CNT=CNT, stats=stats, Q=Q, partial=partial, inv=inv, slip=slip, path=Q['path'])
    if full:
        R['eq'] = eq
        R['pos'] = posc
    if log_cap:
        R['log'] = LG
    return R


def trades(P, R):
    OF, OI = R['OF'], R['OI']
    w0 = P['w0']
    to, tc = P['t_open'], P['t_close']
    kind = OI[:, OI_KIND]
    xb = OI[:, OI_XBAR]
    pk = OI[:, OI_PKIND]
    qty = OF[:, OF_QTY]
    pnl = OF[:, OF_GROSS] - OF[:, OF_COST]
    sld = OF[:, OF_SLD]
    with np.errstate(invalid='ignore', divide='ignore'):
        r_mult = pnl / (sld * qty)
    return pd.DataFrame({
        'dir': OI[:, OI_DIR].astype(np.int64),
        'sig': OI[:, OI_SIG].astype(np.int64),
        'sig_bar': OI[:, OI_SBAR] + w0,
        'entry_bar': OI[:, OI_EBAR] + w0,
        'exit_bar': xb + w0,
        'entry_time': to[OI[:, OI_EBAR]],
        'exit_time': np.where(kind == K_END, tc[xb], to[xb]),
        'entry_px': OF[:, OF_EPX],
        'entry_type': np.where(OI[:, OI_ETYP] == TYP_STOP, 'stop', 'limit'),
        'qty': qty,
        'exit_px': OF[:, OF_XPX],
        'exit_kind': [KINDS[k] for k in kind],
        'part_kind': [KINDS[k] for k in pk],
        'part_bar': np.where(pk > 0, OI[:, OI_PBAR] + w0, -1),
        'part_px': OF[:, OF_PPX],
        'part_qty': OF[:, OF_PQTY],
        'pnl': pnl,
        'pnl_gross': OF[:, OF_GROSS],
        'costs': OF[:, OF_COST],
        'eq_before': OF[:, OF_EQB],
        'sl_dist': sld,
        'sl_px': OF[:, OF_SLPX],
        'tp_px': OF[:, OF_TPPX],
        'r_mult': r_mult,
        'rev': OI[:, OI_REV].astype(bool),
        'gap': OI[:, OI_GAP].astype(bool),
        'be': OI[:, OI_BE].astype(bool),
        'be_no_tp': OI[:, OI_BENT].astype(bool),
        'tv_rows': OI[:, OI_ROWS].astype(np.int64),
        'sl_lt_slip': OI[:, OI_SLLT].astype(bool),
    })


def _fair(r, eqb, sel):
    if not sel.any():
        return 0.0
    if (eqb[sel] <= 0).any():
        return np.nan
    return (float(np.prod(r[sel])) - 1.0) * 100.0


def summary(P, R):
    OF, OI, CNT, st = R['OF'], R['OI'], R['CNT'], R['stats']
    init = INITIAL_CAPITAL
    pnl = OF[:, OF_GROSS] - OF[:, OF_COST]
    eqb = OF[:, OF_EQB]
    nt = len(pnl)
    final = float(st[0])
    eq_mid = float(st[1])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    d = OI[:, OI_DIR]
    kind = OI[:, OI_KIND]
    kc = np.bincount(kind, minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    pc = np.bincount(OI[:, OI_PKIND], minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    out = dict(
        start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100.0,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100.0) if nt else np.nan,
        max_dd_pct=float(st[2] * 100.0),
        max_dd_init_pct=float(st[3] / init * 100.0),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(CNT[C_RAWL]), raw_short=int(CNT[C_RAWS]),
        blocked_long=int(CNT[C_BLKL]), blocked_short=int(CNT[C_BLKS]),
        half1_pct=(eq_mid - init) / init * 100.0,
        half2_pct=(final - eq_mid) / init * 100.0,
        exposure=float(CNT[C_NPOS] / P['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((OI[:, OI_EBAR] == OI[:, OI_XBAR]).sum())
    first = P['t_open'][OI[:, OI_EBAR]] <= P['mid']
    with np.errstate(invalid='ignore', divide='ignore'):
        r = 1.0 + pnl / eqb
    out['h1r_pct'] = _fair(r, eqb, first)
    out['h2r_pct'] = _fair(r, eqb, ~first)
    out['h1_trades'] = int(first.sum())
    out['h2_trades'] = int(nt - first.sum())
    out['avg_bars_held'] = float((OI[:, OI_XBAR] - OI[:, OI_EBAR]).mean()) if nt else np.nan
    out['costs'] = float(OF[:, OF_COST].sum())
    # fields of this strategy
    for i, nm in enumerate(KINDS[1:], 1):
        out['part_' + nm] = int(pc[i])
    out['tv_rows'] = int(OI[:, OI_ROWS].sum())
    out['be_trades'] = int(OI[:, OI_BE].sum())
    out['be_no_tp'] = int(OI[:, OI_BENT].sum())
    sld = OF[:, OF_SLD]
    with np.errstate(invalid='ignore', divide='ignore'):
        rm = pnl / (sld * OF[:, OF_QTY])
    out['net_r'] = float(np.nansum(rm)) if nt else 0.0
    out['h1_r'] = float(np.nansum(rm[first])) if nt else 0.0
    out['h2_r'] = float(np.nansum(rm[~first])) if nt else 0.0
    out['orders_placed'] = int(CNT[C_PLACED])
    out['orders_replaced'] = int(CNT[C_REPL])
    out['orders_filled'] = int(CNT[C_FILLED])
    out['orders_cancelled'] = int(CNT[C_CANC])
    out['oca_cancelled'] = int(CNT[C_OCA])
    out['orders_unfilled_end'] = int(st[7])
    out['both_pending_bars'] = int(CNT[C_BOTH])
    out['gap_entries'] = int(CNT[C_GAP])
    out['zero_qty'] = int(CNT[C_ZQ])
    out['sl_lt_slip'] = int(CNT[C_SLLT])
    out['slippage_paid'] = float(st[5])
    out['neg_equity_bars'] = int(CNT[C_NEG])
    out['min_equity'] = float(st[4])
    out['max_notional_x'] = float(st[6]) if (eqb > 0).any() else np.nan     # max over an empty set: NaN
    out['sig_buy'] = int(P['sig_buy'])
    out['sig_sell'] = int(P['sig_sell'])
    return out


def run(pair, chart_tf, params=None):
    """prepare + simulate with one dict of inputs (signal and order inputs split automatically)."""
    params = dict(params or {})
    P = prepare(pair, chart_tf, params)
    R = simulate(P, None)
    return trades(P, R), summary(P, R)


def fmt(s):
    return (f"trades={s['trades']} (L {s['long']} / S {s['short']}) net={s['net_pct']:.2f}% pf={s['pf']:.3f} "
            f"win={s['win_pct']:.1f}% dd={s['max_dd_pct']:.2f}% h1r={s['h1r_pct']:.2f}% h2r={s['h2r_pct']:.2f}% "
            f"raw L/S={s['raw_long']}/{s['raw_short']} blk L/S={s['blocked_long']}/{s['blocked_short']} "
            f"exits sl/tp/be/run/trail/rev/opp/time/end={s['exit_sl']}/{s['exit_tp']}/{s['exit_be']}/"
            f"{s['exit_runner']}/{s['exit_trail']}/{s['exit_reverse']}/{s['exit_opp']}/{s['exit_time']}/"
            f"{s['exit_end']} part_tp={s['part_tp_part']} be_no_tp={s['be_no_tp']} tv_rows={s['tv_rows']}")


if __name__ == '__main__':
    for pair in ('BTC', 'XAU'):
        for fo in (False, True):
            for inv in (False, True):
                t0 = _time.time()
                P = prepare(pair, '60', {'fgfOn': fo})
                t1 = _time.time()
                R = simulate(P, {'inv': inv})
                t2 = _time.time()
                print(pair, '60', 'filter', fo, 'inv', inv, fmt(summary(P, R)),
                      f'prep {t1 - t0:.1f}s sim {t2 - t1:.3f}s', flush=True)
