"""Danny Phantom FX V10.21.1 LiveSafe + FlashGold Direction Filter [Update 1]: the CANONICAL
Python replica (stage 3 of REPLICA_SPEC.md). Ground truth:
/home/user/master/DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine at HEAD; brief SPEC_danny.md. It is
build A (danny_a.py) after the reconciliation with build B (reconcile_danny.md), plus the
1-minute "Bar Magnifier" path. Interpretations and limits: danny_notes.md. Tests: tests_danny.py.

    prepare(pair, chart_tf, params=None) -> P     series, gates, zone seed, filter permissions
    simulate(P, x=None, full=False, sub=None) -> R   the zone machine, orders and exits (one numba kernel)
    trades(P, R)                         -> DataFrame, one row per trade, in exit order
    summary(P, R)                        -> dict
    run(pair, chart_tf, params=None)     -> (trades, summary)

Paths: 'tv' (TradingView's bar path, SPEC_AH.md rule 4) and 'mag' (the exit bracket walks the
1-minute sub-bars of the chart candle in time order, each with its own rule-4 path; entries,
reversals, dead / time / blackout closes and the script's bar-close logic stay on the chart
candle). Chart "1": mag == tv. Cost modes 'tv' / 'ours' / 'stress'.
Two SEPARATE direction inputs: signalDirection (the older "Signal direction": flips the zone
signals BEFORE the directional windows and the filter) and dpInv / inv (Update 1: flips the order
AFTER the gate).
Line numbers Lnnn below are those of the fused Pine file. The filter block (L249-829) is NOT
reimplemented: prepare() takes fgfBuyOk / fgfSellOk from fgf.fgf_permissions.

How one candle runs (SPEC_danny.md sections 5 and 6, assumptions E1-E14):
  A  the open trade's bracket (the strategy.exit levels sent at the previous candle's close) is
     walked along the candle's path; never on the entry candle;
  B  the bar-close run: loss cluster, cooldown, distances, cost filter, forced exits, zones and
     signals, Update 1 decisions, ONE market order (entry / reversal, or a forced close) filled at
     this close;
  C  the run after that fill: closed-trade accounting, the new trade's entry state and its first
     bracket, active from the next candle's open.
varRollback (default True) = TradingView's rollback of `var` variables between the runs on one
bar: the one-entry-per-zone reset and the cooldown assignment are lost, and a same-side re-entry
on the candle where the bracket closed the previous trade keeps that trade's entry state.
A decision sized to zero places no order: on a candle without a bracket fill nothing rolls back
what that run wrote (the zone reset and the pending* variables persist, as the Pine does).
limitOneDecisionPerBar (default True) has one effect on history, added by the stage-4 audit: off,
the same holds on a candle WITH a bracket fill, because the bar-close run decides again. It can
only matter once a quantity has floored to zero (zero_qty > 0). limitOneFlatExitPerBar has none.
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
MINTICK = 0.01                 # syminfo.mintick (both pairs)
POINTVALUE = 1.0               # syminfo.pointvalue
INITIAL_CAPITAL = 2000.0       # strategy(initial_capital=2000)
SLIPPAGE_TICKS = 75            # strategy(slippage=75): 75 x 0.01 = 0.75 in price per market / stop fill
COMMISSION_PCT = 0.001         # strategy(commission_type=percent, commission_value=0.001): 0.001 % per fill
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}
TICKER = {'BTC': 'BTCUSD', 'XAU': 'XAUUSD'}          # syminfo.ticker (E11)
EXCH_TZ = {'BTC': 'UTC', 'XAU': 'America/New_York'}  # syminfo.timezone (E12)

KINDS = ['', 'sl', 'tp', 'trail', 'be', 'reverse', 'dead', 'time', 'blackout', 'end']
K_SL, K_TP, K_TRAIL, K_BE, K_REV, K_DEAD, K_TIME, K_BLK, K_END = 1, 2, 3, 4, 5, 6, 7, 8, 9

# per fill, per unit: (fixed $, fraction of the fill value), and the slippage in price per
# market / stop fill
COSTS = {
    'tv': {'XAU': (0.0, COMMISSION_PCT / 100.0), 'BTC': (0.0, COMMISSION_PCT / 100.0)},
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}
SLIP = {'tv': SLIPPAGE_TICKS * MINTICK, 'ours': 0.0, 'stress': 0.0}

SIG_INV = "Inverted (V10 design)"
SIG_ORIG = "Original (un-inverted)"

DEFAULTS = dict(
    # ---- replica controls
    fgfOn=True,                # the filter's own "Enable filter" (prepare)
    start=None, end=None,      # window override by t_close (prepare)
    path='tv', cost='tv', varRollback=True,
    # ---- Preset (L83-95)
    presetMode="Auto", signalDirection=SIG_INV, v2Source="Auto Optimized Profile", lockAutoProfile=True,
    useV106GrowthSlTp=True, useV1021NasAdaptiveDead=True, nasAdaptiveRunupAtr=2.0,
    # ---- LiveSafe (L103-109)
    limitOneDecisionPerBar=True, limitOneFlatExitPerBar=True,
    # ---- V2 toggles (L117-134)
    useDeadExit=True, deadBarsIn=15, useBreakeven=False, beTriggerAtr=1.0,
    useEntryBuffer=True, entryBufferIn=60, useSundayBlock=True,
    useEntryWindow=False, entryWindowIn="0800-1200",
    useOnePerZone=True, useCooldown=True, cooldownIn=10,
    # ---- zones / trend / entry (L141-154)
    manualZoneLength=50, manualDeltaThreshold=1.5, manualMinRetestBars=1, manualMaxZoneAge=200,
    manualInvalidate=True, manualUseEmaFilter=True, manualEmaLength=100, manualZoneTrend=False,
    manualEntryMode="Normal Retest Touch",
    # ---- S2 exits (L157-168)
    ExitMode="ATR", slPointsIn=5000.0, tpPointsIn=50000.0, atrLenS2=14, slAtrMultS2=1.2, tpRS2=4.1667,
    useTrailS2=False, trailActPts=1000.0, trailPts=100.0, trailActAtr=4.0, trailDstAtr=0.2, timeStopBars=50,
    # ---- S3 sizing (L171-177)
    QtyMode="Risk %", fixedQtyS3=10.0, riskPctS3=1.0, maxQtyS3=50.0, qtyStepS3=0.001,
    capMarginS3=True, marginPctS3=1.0,
    # ---- session (L180-181)
    useSessionFilter=False, nySession="0930-1600",
    # ---- quality filters (L189-201)
    useRobustHourFilter=True, useDirectionalMicroFilter=True, useV105DirectionalFilter=True,
    useV1010PfFilter=True, useV1011LossClusterPause=True, manualLossClusterCount=5,
    manualLossClusterPauseBars=12, useV1013VolCostFilter=True, minStopToCostRatio=4.0,
    modeledSlippageTicksOverride=0,
    # ---- blackout (L208-210)
    useWeekendBlackout=True, useDailyBlackout=True, closeLeadMin=10,
    # ---- Update 1 (L832)
    dpInv=False,
)
_ALIASES = {'inv': 'dpInv'}
# SIGNAL inputs: fixed by prepare(); simulate() may not change them (SPEC_danny 3.1)
_PREP_KEYS = {
    'fgfOn', 'start', 'end', 'presetMode', 'v2Source', 'lockAutoProfile',
    'manualZoneLength', 'manualDeltaThreshold', 'manualUseEmaFilter', 'manualEmaLength', 'manualZoneTrend',
    'manualMinRetestBars', 'manualMaxZoneAge', 'manualInvalidate', 'manualEntryMode',
    'useEntryBuffer', 'entryBufferIn', 'useSundayBlock', 'useEntryWindow', 'entryWindowIn',
    'useSessionFilter', 'nySession',
    'useRobustHourFilter', 'useDirectionalMicroFilter', 'useV105DirectionalFilter', 'useV1010PfFilter',
    'useWeekendBlackout', 'useDailyBlackout', 'closeLeadMin',
}
# accepted, no effect in the replica (SPEC_danny 3.3): limitOneFlatExitPerBar never binds on history
# under E1 / E3 (the flat-exit time stamp is a varip whatever the switch says), useV106GrowthSlTp is
# never read by the Pine, the NAS100 inputs belong to another preset. limitOneDecisionPerBar has ONE
# effect on history (stage-4 audit): off, a decision sized to zero on a candle where the bracket
# filled is repeated by the bar-close run, so its zone reset and pending* writes stay (kernel B12)
_NO_EFFECT = {'limitOneFlatExitPerBar', 'useV106GrowthSlTp',
              'useV1021NasAdaptiveDead', 'nasAdaptiveRunupAtr'}
# drawing / alerts only (SPEC_danny 3.4): accepted and ignored
_DISPLAY = {'manualShowZones', 'appendLiveSafeId', 'appendExitReason', 'webhookPointSizeInput', 'useLotInAlert',
            'mt4Balance', 'mt4RiskPct', 'lotStep', 'minLot', 'maxLot', 'contractOverride', 'quoteUsd',
            'demandColor', 'demandKeyColor', 'supplyColor', 'supplyKeyColor', 'buySignalColor', 'sellSignalColor',
            'showOriginalSignals', 'showRawActiveSignals'}
_PRESETS_OTHER = ("AUDJPY 2m", "EURGBP 3m", "USDCAD 5m", "XAGUSD 5m", "NAS100 5m")


def _check(Q):
    if Q['cost'] not in COSTS:
        raise ValueError("cost must be 'tv', 'ours' or 'stress'")
    if Q['path'] not in ('tv', 'mag'):
        raise ValueError("path must be 'tv' or 'mag'")
    if Q['presetMode'] in _PRESETS_OTHER:
        raise NotImplementedError('preset %r is another market: not implemented' % Q['presetMode'])
    if Q['presetMode'] not in ("Auto", "XAUUSD 5m", "Manual"):
        raise ValueError('presetMode %r' % (Q['presetMode'],))
    if Q['signalDirection'] not in (SIG_INV, SIG_ORIG):
        raise ValueError('signalDirection must be %r or %r' % (SIG_INV, SIG_ORIG))
    if Q['v2Source'] not in ("Auto Optimized Profile", "Manual V2 Toggles"):
        raise ValueError('v2Source %r' % (Q['v2Source'],))
    if Q['manualEntryMode'] not in ("Normal Retest Touch", "Close Beyond Key Zone"):
        raise ValueError('manualEntryMode %r' % (Q['manualEntryMode'],))
    if Q['ExitMode'] not in ("Points", "ATR"):
        raise ValueError('ExitMode must be Points or ATR')
    if Q['QtyMode'] not in ("Fixed", "Risk %"):
        raise ValueError('QtyMode must be Fixed or Risk %')
    mins = dict(deadBarsIn=1, beTriggerAtr=0.1, entryBufferIn=5, cooldownIn=1, manualZoneLength=2,
                manualMinRetestBars=1, manualMaxZoneAge=5, manualEmaLength=1, slPointsIn=0.0, tpPointsIn=0.0,
                atrLenS2=1, slAtrMultS2=0.01, tpRS2=0.0, trailActPts=0.0, trailPts=1.0, trailActAtr=0.0,
                trailDstAtr=0.005, timeStopBars=0, fixedQtyS3=0.0, riskPctS3=0.0, maxQtyS3=0.0,
                qtyStepS3=0.000001, marginPctS3=0.0, manualLossClusterCount=2, manualLossClusterPauseBars=1,
                minStopToCostRatio=1.0, modeledSlippageTicksOverride=0, closeLeadMin=5)
    for k, mv in mins.items():
        if Q[k] < mv:
            raise ValueError('%s=%r is below the Pine minval %r' % (k, Q[k], mv))
    for k in ('nySession', 'entryWindowIn'):
        _parse_session(Q[k])


def _params(params, base=None):
    Q = dict(DEFAULTS if base is None else base)
    fgfp = {}
    for k, v in (params or {}).items():
        k = _ALIASES.get(k, k)
        if k in DEFAULTS:
            Q[k] = v
        elif k.startswith('fgf') or k.startswith('fgs') or k == 'FGF_FORCE_OVERLAY':
            fgfp[k] = v
        elif k in _DISPLAY:
            pass
        else:
            raise ValueError('unknown param %r' % (k,))
    _check(Q)
    fgfp['fgfOn'] = bool(Q['fgfOn'])
    return Q, fgfp


def _parse_session(s):
    """'HHMM-HHMM' or 'HHMM-HHMM:days' -> (start minute, end minute of the day, days). days is None
    (every day of the week) or a set of Pine day numbers (1 = Sunday ... 7 = Saturday)."""
    s = str(s)
    days = None
    if ':' in s:
        s, dd = s.split(':', 1)
        days = set(int(ch) for ch in dd)
        if not days or not days <= set(range(1, 8)):
            raise ValueError('session days %r' % (dd,))
    a, b = s.split('-')
    if len(a) != 4 or len(b) != 4:
        raise ValueError('session %r' % (s,))
    return int(a[:2]) * 60 + int(a[2:]), int(b[:2]) * 60 + int(b[2:]), days


# ----------------------------------------------------------------------------
# data and series
# ----------------------------------------------------------------------------
_BARS = {}


def load_bars(pair, tf):
    key = (pair, str(tf))
    if key not in _BARS:
        t = pq.read_table(os.path.join(DATA, '%s_%s.parquet' % key),
                          columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
        d = {}
        for cn in t.column_names:
            a = t.column(cn).to_numpy()
            d[cn] = np.ascontiguousarray(a, dtype=np.float64 if cn in ('open', 'high', 'low', 'close') else np.int64)
        v = pq.read_table(os.path.join(DATA, '%s_%s_vol.parquet' % key), columns=['volume']).column('volume').to_numpy()
        if len(v) != len(d['close']):
            raise RuntimeError('volume rows do not match the bars')
        d['volume'] = np.ascontiguousarray(v, dtype=np.float64)
        _BARS[key] = d
    return _BARS[key]


@njit(cache=True)
def _volume_delta(o, h, l, c, v):
    """L1065-1077. volumeDelta = buyVolume - sellVolume with the candle-position split."""
    n = c.shape[0]
    vd = np.empty(n)
    for i in range(n):
        pr = h[i] - l[i]
        up = 0.5
        if pr != 0.0:
            up = (c[i] - l[i]) / pr
        else:
            pcl = c[i - 1] if i > 0 else c[i]          # nz(close[1], close)
            if c[i] > pcl:
                up = 1.0
            elif c[i] < pcl:
                up = 0.0
        sv = v[i]
        if np.isnan(sv):                                # nz(volume, 1.0)
            sv = 1.0
        vd[i] = sv * up - sv * (1.0 - up)
    return vd


@njit(cache=True)
def _sma_abs(x, n):
    """ta.sma(math.abs(x), n): mean of the last n values incl. the current bar, na for the first
    n-1 rows. Each window is summed afresh (oldest first): no drift of a running sum."""
    m = x.shape[0]
    out = np.full(m, np.nan)
    for i in range(n - 1, m):
        s = 0.0
        for j in range(i - n + 1, i + 1):
            s += abs(x[j])
        out[i] = s / n
    return out


@njit(cache=True)
def _ema(x, n):
    """ta.ema: alpha = 2 / (n + 1), seeded with the first value."""
    m = x.shape[0]
    out = np.empty(m)
    a = 2.0 / (n + 1.0)
    for i in range(m):
        if i == 0:
            out[i] = x[i]
        else:
            out[i] = a * x[i] + (1.0 - a) * out[i - 1]
    return out


@njit(cache=True)
def _atr(high, low, close, length):
    """ta.atr(length) = ta.rma(ta.tr(true), length): TR[0] = high - low, RMA seeded with the SMA of
    the first `length` true ranges (first value on row length - 1)."""
    n = close.shape[0]
    out = np.full(n, np.nan)
    if n < length:
        return out
    s = 0.0
    v = 0.0
    alpha = 1.0 / length
    for i in range(n):
        tr = high[i] - low[i]
        if i > 0:
            tr = max(max(tr, abs(high[i] - close[i - 1])), abs(low[i] - close[i - 1]))
        if i < length:
            s += tr
            if i == length - 1:
                v = s / length
                out[i] = v
        else:
            v = alpha * tr + (1.0 - alpha) * v
            out[i] = v
    return out


@njit(cache=True)
def _zone_seed(o, h, l, c, d_spike, s_spike, invalidate, w0):
    """State of the ten zone variables after row w0 - 1: only the invalidation (L1145-1157) and
    the new-zone assignment (L1178-1190) run before the window (no trade exists there, so the
    one-entry-per-zone reset cannot fire). Run from the first row of the file."""
    z = np.full(10, np.nan)        # dTop dBot dKeyTop dKeyBot dBar | sTop sBot sKeyTop sKeyBot sBar
    for i in range(w0):
        if invalidate:
            if not np.isnan(z[1]) and c[i] < z[1]:
                z[0] = np.nan; z[1] = np.nan; z[2] = np.nan; z[3] = np.nan; z[4] = np.nan
            if not np.isnan(z[5]) and c[i] > z[5]:
                z[5] = np.nan; z[6] = np.nan; z[7] = np.nan; z[8] = np.nan; z[9] = np.nan
        if d_spike[i]:
            z[0] = h[i]; z[1] = l[i]; z[2] = c[i]; z[3] = o[i]; z[4] = i
        if s_spike[i]:
            z[5] = h[i]; z[6] = l[i]; z[7] = o[i]; z[8] = c[i]; z[9] = i
    return z


def _ny_clock(t_open):
    """dayofweek / hour / minute of the bar OPEN in America/New_York (L942-945), Pine numbering:
    Sunday = 1 ... Saturday = 7."""
    idx = pd.DatetimeIndex(pd.to_datetime(np.asarray(t_open, dtype=np.int64), unit='s', utc=True)).tz_convert('America/New_York')
    dow = (np.asarray(idx.dayofweek, dtype=np.int64) + 1) % 7 + 1
    return dow, np.asarray(idx.hour, dtype=np.int64), np.asarray(idx.minute, dtype=np.int64)


def _in_session(pair, t_open, sess, ny_min, ny_dow):
    """E12: time(timeframe.period, sess) is not na iff the bar's OPEN, in the exchange time zone
    (XAU: New York, BTC: UTC), has HHMM in [start, end), wrapping over midnight when start > end;
    every day of the week unless the string carries ':days' (the day of the bar's open in that
    time zone, Pine numbering). start == end is read as the whole day."""
    a, b, days = _parse_session(sess)
    t = np.asarray(t_open, dtype=np.int64)
    if EXCH_TZ[pair] == 'UTC':
        m = (t % 86400) // 60
        dow = ((t // 86400 + 4) % 7) + 1                # 1970-01-01 was a Thursday (Pine: 5)
    else:
        m = ny_min
        dow = ny_dow
    if a == b:
        out = np.ones(len(m), np.bool_)
    elif a < b:
        out = (m >= a) & (m < b)
    else:
        out = (m >= a) | (m < b)
    if days is not None:
        out = out & np.isin(dow, list(days))
    return out


# ----------------------------------------------------------------------------
# the kernel
# ----------------------------------------------------------------------------
@njit(cache=True)
def _fq(stop_dist, equity, close, risk_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct, pv):
    """f_qty (L1196-1205), same operation order. Returns (quantity, a cap reduced it)."""
    q = fixed_qty
    if risk_mode:
        stop_cash = stop_dist * pv
        if stop_cash > 0.0:                      # na -> false -> 0
            q = equity * risk_pct / 100.0 / stop_cash
        else:
            q = 0.0
    capped = False
    if max_qty < q:                              # math.min(q, maxQtyS3)
        q = max_qty
        capped = True
    if cap_margin and margin_pct > 0.0:
        m = equity / (close * pv * margin_pct / 100.0)
        if m < q:
            q = m
            capped = True
    return math.floor(q / qty_step + 1e-9) * qty_step, capped


@njit(cache=True)
def _protect(pos, close, avg, atr_e, sl_e, tp_e, tr_armed, tr_stop, be_armed,
             use_trail, tr_act, tr_dst, be_on, be_trig):
    """L1414-1429 (long) / L1433-1448 (short): the stop and the target of strategy.exit, with the
    hand-made trailing and breakeven. math.max / math.min with na give na (E6).
    Returns (stop, target, stop kind, trailArmed, trailStop, beArmed)."""
    kind = 1                                         # K_SL
    if pos > 0:
        stop = np.nan
        if sl_e > 0.0:
            stop = avg - sl_e
        tgt = np.nan
        if not np.isnan(tp_e):
            tgt = avg + tp_e
        if use_trail:
            if close - avg >= tr_act:
                tr_armed = True
            if tr_armed:
                new_tr = close - tr_dst
                if np.isnan(tr_stop):
                    tr_stop = new_tr
                elif np.isnan(new_tr):
                    tr_stop = np.nan
                elif new_tr > tr_stop:
                    tr_stop = new_tr
                if np.isnan(stop) or tr_stop > stop:
                    kind = 3                         # K_TRAIL
                if np.isnan(stop):
                    stop = tr_stop
                elif np.isnan(tr_stop):
                    stop = np.nan
                elif tr_stop > stop:
                    stop = tr_stop
        if be_on:
            if close >= avg + atr_e * be_trig:
                be_armed = True
            if be_armed:
                if not np.isnan(stop) and avg > stop:
                    kind = 4                         # K_BE
                    stop = avg
        return stop, tgt, kind, tr_armed, tr_stop, be_armed
    stop = np.nan
    if sl_e > 0.0:
        stop = avg + sl_e
    tgt = np.nan
    if not np.isnan(tp_e):
        tgt = avg - tp_e
    if use_trail:
        if avg - close >= tr_act:
            tr_armed = True
        if tr_armed:
            new_tr = close + tr_dst
            if np.isnan(tr_stop):
                tr_stop = new_tr
            elif np.isnan(new_tr):
                tr_stop = np.nan
            elif new_tr < tr_stop:
                tr_stop = new_tr
            if np.isnan(stop) or tr_stop < stop:
                kind = 3
            if np.isnan(stop):
                stop = tr_stop
            elif np.isnan(tr_stop):
                stop = np.nan
            elif tr_stop < stop:
                stop = tr_stop
    if be_on:
        if close <= avg - atr_e * be_trig:
            be_armed = True
        if be_armed:
            if not np.isnan(stop) and avg < stop:
                kind = 4
                stop = avg
    return stop, tgt, kind, tr_armed, tr_stop, be_armed


@njit(cache=True)
def _walk(pos, ok, hk, lk, ck, stop, tgt):
    """SPEC_danny 5.3 (SPEC_AH rule 4) on ONE bar (a chart candle, or a 1-minute sub-bar on the 'mag'
    path) for the bracket stop / tgt (na = that order does not exist) of a trade on side pos.
    Open test first (stop before limit: a gap fills at the open), then the path
    open -> high -> low -> close if (high - open) < (open - low), else open -> low -> high -> close;
    the first level reached wins; inclusive comparisons, no rounding.
    Returns (hit, raw price, where): hit 0 none / 1 stop / 2 limit; where 1 = at the open or on the
    first leg, 2 = second leg, 3 = third leg."""
    has_s = not np.isnan(stop)
    has_t = not np.isnan(tgt)
    if pos > 0:
        if has_s and ok <= stop:
            return 1, ok, 1
        if has_t and ok >= tgt:
            return 2, ok, 1
        if (hk - ok) < (ok - lk):                    # open -> high -> low -> close
            if has_t and hk >= tgt:
                return 2, tgt, 1
            if has_s and lk <= stop:
                return 1, stop, 2
            if has_t and ck >= tgt:
                return 2, tgt, 3
        else:                                        # open -> low -> high -> close
            if has_s and lk <= stop:
                return 1, stop, 1
            if has_t and hk >= tgt:
                return 2, tgt, 2
            if has_s and ck <= stop:
                return 1, stop, 3
    else:
        if has_s and ok >= stop:
            return 1, ok, 1
        if has_t and ok <= tgt:
            return 2, ok, 1
        if (hk - ok) < (ok - lk):                    # open -> high -> low -> close
            if has_s and hk >= stop:
                return 1, stop, 1
            if has_t and lk <= tgt:
                return 2, tgt, 2
            if has_s and ck >= stop:
                return 1, stop, 3
        else:                                        # open -> low -> high -> close
            if has_t and lk <= tgt:
                return 2, tgt, 1
            if has_s and hk >= stop:
                return 1, stop, 2
            if has_t and ck <= tgt:
                return 2, tgt, 3
    return 0, 0.0, 0


@njit(cache=True)
def _kernel(o, h, l, c, pc, atr, d_spike, s_spike, trend_l, trend_s, gate, bclose, pre, lblock, sblock,
            buy_ok, sell_ok, w0, seed, mag, ptr, sb_o, sb_h, sb_l, sb_c,
            invalidate, min_retest, max_age, close_beyond,
            orig_dir, inv, points_mode, sl_mult, tp_r, sl_pts, tp_pts,
            use_trail, tr_act_atr, tr_dst_atr, tr_act_pts, tr_pts,
            max_bars, dead_on, dead_bars, be_on, be_trig, one_zone, cd_on, cd_bars,
            lc_on, lc_trig, lc_bars, vc_on, min_ratio, model_ticks,
            risk_mode, fixed_qty, risk_pct, max_qty, qty_step, cap_margin, margin_pct,
            slip, c_fix, c_pct, rollback, lock_entry, init_cap, mintick, pv, mid_j, full):
    n = c.shape[0]
    cap = n + 2
    t_dir = np.empty(cap, np.int8)
    t_ek = np.empty(cap, np.int64)
    t_xk = np.empty(cap, np.int64)
    t_epx = np.empty(cap)
    t_qty = np.empty(cap)
    t_xpx = np.empty(cap)
    t_kind = np.empty(cap, np.int8)
    t_gross = np.empty(cap)
    t_cost = np.empty(cap)
    t_eqb = np.empty(cap)
    t_sig = np.empty(cap, np.int8)
    t_zone = np.empty(cap, np.int8)          # 1 = demand zone, 0 = supply zone
    t_sld = np.empty(cap)
    t_slpx = np.empty(cap)
    t_tppx = np.empty(cap)
    t_re = np.empty(cap, np.int8)
    t_inh = np.empty(cap, np.bool_)
    t_xs = np.full(cap, -1, np.int64)        # 'mag': the sub-bar (row of the sub-bar arrays) of a bracket exit
    nt = 0

    m = n if full else 0
    b_eq = np.empty(m)
    b_pos = np.empty(m, np.int8)
    b_stop = np.empty(m)                     # bracket in force for the NEXT candle
    b_tgt = np.empty(m)
    b_flags = np.empty(m, np.int32)
    b_cons = np.empty(m, np.int32)
    b_pause = np.empty(m, np.int64)
    b_cd = np.empty(m, np.int64)
    b_dkt = np.empty(m)                      # zone keys as the signal test saw them
    b_dkb = np.empty(m)
    b_dbar = np.empty(m)
    b_skt = np.empty(m)
    b_skb = np.empty(m)
    b_sbar = np.empty(m)

    # zones (the seed); *_set stands for "not na" of the five variables of a zone
    d_set = not np.isnan(seed[4])
    d_bot = seed[1]; d_kt = seed[2]; d_kb = seed[3]
    d_bar = np.int64(seed[4]) if d_set else np.int64(-1)
    s_set = not np.isnan(seed[9])
    s_top = seed[5]; s_kt = seed[7]; s_kb = seed[8]
    s_bar = np.int64(seed[9]) if s_set else np.int64(-1)

    # position and per-trade state
    pos = 0
    qty = 0.0
    avg = np.nan
    ebar = np.int64(-1)                      # bar_index of the entry candle
    e_k = np.int64(-1)
    e_cost = 0.0
    e_eqb = 0.0
    e_sig = 0
    e_zone = 0
    e_re = 0
    e_inh = False
    e_sld = np.nan
    e_slpx = np.nan
    e_tppx = np.nan
    stop = np.nan                            # the bracket: strategy.exit stop / limit
    tgt = np.nan
    skind = K_SL
    atr_e = np.nan                           # longAtrAtEntry / shortAtrAtEntry
    sl_e = np.nan                            # slDistAtEntry
    tp_e = np.nan                            # tpDistAtEntry
    tr_armed = False
    tr_stop = np.nan
    be_armed = False
    # pendingLongAtr / pendingShortAtr / pendingSlDist / pendingTpDist (L1047-1050). With rollback
    # they are na at every initialisation EXCEPT after an entry decision sized to zero, whose
    # writes are not rolled back (no fill follows that run): see B12 and C2
    p_la = np.nan
    p_sa = np.nan
    p_sl = np.nan
    p_tp = np.nan

    cons = 0                                 # consecutiveClosedLosses
    pause_until = np.int64(-1)               # lossClusterPauseUntilBar (-1 = na)
    cd_until = np.int64(-1)                  # cooldownUntilBar (-1 = na)
    cash = init_cap

    dd_pk = init_cap
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init_cap
    eq_last = init_cap
    n_pos = 0
    n_rl = 0
    n_rs = 0
    n_bl = 0
    n_bs = 0
    slip_paid = 0.0
    n_zero = 0
    n_capped = 0
    n_margin = 0

    for k in range(n):
        bi = w0 + k
        ok = o[k]
        hk = h[k]
        lk = l[k]
        ck = c[k]
        pha = 0                              # where the bracket filled: 1 open / leg 0, 2 leg 1, 3 leg 2
        xs = -1
        inh_side = 0
        inh_atr = np.nan
        inh_sl = np.nan
        inh_tp = np.nan
        inh_ta = False
        inh_ts = np.nan
        inh_be = False
        flags = 0

        # ---------------- A. the bracket of the open trade (5.3) ----------------
        if pos != 0 and bi > ebar and (not np.isnan(stop) or not np.isnan(tgt)):
            hit = 0                          # 1 stop, 2 limit
            raw = 0.0
            if mag:
                # the 1-minute sub-bars of this candle in time order; the levels are constant
                # during the candle and the open test runs at every sub-bar open
                j1 = ptr[k + 1]
                for j in range(ptr[k], j1):
                    hit, raw, leg = _walk(pos, sb_o[j], sb_h[j], sb_l[j], sb_c[j], stop, tgt)
                    if hit != 0:
                        xs = j
                        # 2 / 3 only when TradingView's own next tick would be this candle's close
                        pha = leg if j == j1 - 1 else 1
                        break
            else:
                hit, raw, pha = _walk(pos, ok, hk, lk, ck, stop, tgt)
            if hit != 0:
                if hit == 1:
                    xpx = raw - pos * slip                   # stop fill: slippage against the trade
                    xkind = skind
                    slip_paid += slip * qty
                else:
                    xpx = raw                                # limit fill: no slippage
                    xkind = K_TP
                xc = qty * (c_fix + c_pct * xpx)
                gross = pos * qty * (xpx - avg) * pv
                cash += gross - xc
                pnl = gross - (e_cost + xc)
                t_dir[nt] = pos; t_ek[nt] = e_k; t_xk[nt] = k; t_epx[nt] = avg; t_qty[nt] = qty
                t_xpx[nt] = xpx; t_kind[nt] = xkind; t_gross[nt] = gross; t_cost[nt] = e_cost + xc
                t_eqb[nt] = e_eqb; t_sig[nt] = e_sig; t_zone[nt] = e_zone; t_sld[nt] = e_sld
                t_slpx[nt] = e_slpx; t_tppx[nt] = e_tppx; t_re[nt] = e_re; t_inh[nt] = e_inh
                t_xs[nt] = xs
                nt += 1
                # the closed trade's entry state as it was at the end of the previous candle (E2 iii)
                inh_side = pos; inh_atr = atr_e; inh_sl = sl_e; inh_tp = tp_e
                inh_ta = tr_armed; inh_ts = tr_stop; inh_be = be_armed
                pos = 0; qty = 0.0; avg = np.nan
                stop = np.nan; tgt = np.nan; skind = K_SL
                atr_e = np.nan; sl_e = np.nan; tp_e = np.nan
                tr_armed = False; tr_stop = np.nan; be_armed = False
                # B1. loss cluster (L1020-1032)
                if pnl < 0.0:
                    cons += 1
                else:
                    cons = 0
                if lc_on and cons >= lc_trig:
                    pause_until = bi + lc_bars
                    cons = 0

        # ---------------- B. the bar-close run ----------------
        # B2 (L1034-1036): the flag is computed before the clear
        in_pause = lc_on and pause_until >= 0 and bi < pause_until
        if lc_on and pause_until >= 0 and bi >= pause_until:
            pause_until = -1
        # B3 (L1039)
        in_cd = cd_on and cd_until >= 0 and bi < cd_until
        # B5 (L1084-1087)
        a = atr[k]
        if points_mode:
            sl_now = sl_pts * mintick
            tp_now = tp_pts * mintick if tp_pts > 0.0 else np.nan
            tr_act_now = tr_act_pts * mintick
            tr_dst_now = tr_pts * mintick
        else:
            sl_now = a * sl_mult
            tp_now = sl_now * tp_r if tp_r > 0.0 else np.nan
            tr_act_now = a * tr_act_atr
            tr_dst_now = a * tr_dst_atr
            if tr_dst_now < mintick:                         # math.max(atr * trailDstAtr, mintick); na stays na
                tr_dst_now = mintick
        # B6 (L1089-1097)
        vol_block = False
        if vc_on:
            est = 2.0 * model_ticks * mintick + ck * 0.00002
            if est > 0.0:
                ratio = sl_now / est
                vol_block = (not np.isnan(ratio)) and ratio < min_ratio
        # B4 + B7 (L1058-1059, L1105-1118), on the position after phase A
        dead_x = False
        time_x = False
        blk_x = False
        if pos != 0:
            bars_in = bi - ebar
            if dead_on and bars_in >= dead_bars:
                if pos > 0:
                    dead_x = ck <= avg
                else:
                    dead_x = ck >= avg
            time_x = max_bars > 0 and bars_in >= max_bars
            blk_x = bclose[k]
        forced = dead_x or time_x or blk_x
        # B8 (L1120)
        allowed = gate[k] and (not in_cd) and (not in_pause) and (not forced)
        # B9 (L1145-1175)
        if invalidate:
            if d_set and ck < d_bot:
                d_set = False
            if s_set and ck > s_top:
                s_set = False
        if full:
            b_dkt[k] = d_kt if d_set else np.nan
            b_dkb[k] = d_kb if d_set else np.nan
            b_dbar[k] = d_bar if d_set else np.nan
            b_skt[k] = s_kt if s_set else np.nan
            b_skb[k] = s_kb if s_set else np.nan
            b_sbar[k] = s_bar if s_set else np.nan
        in_d = False
        if d_set:
            age = bi - d_bar
            if age >= min_retest and age <= max_age and lk <= d_kt and ck >= d_kb:
                in_d = (ck > d_kt) if close_beyond else True
        in_s = False
        if s_set:
            age = bi - s_bar
            if age >= min_retest and age <= max_age and hk >= s_kb and ck <= s_kt:
                in_s = (ck < s_kb) if close_beyond else True
        tradable = allowed and not vol_block
        orig_buy = in_d and ck > ok and ck > pc[k] and trend_l[k] and tradable
        orig_sell = in_s and ck < ok and ck < pc[k] and trend_s[k] and tradable
        if orig_dir:
            n_buy = orig_buy and not lblock[k]
            n_sell = orig_sell and not sblock[k]
        else:
            n_buy = orig_sell and not lblock[k]
            n_sell = orig_buy and not sblock[k]
        # B10 (L1178-1190): new zones AFTER the signals
        if d_spike[k]:
            d_bot = lk; d_kt = ck; d_kb = ok; d_bar = bi; d_set = True
        if s_spike[k]:
            s_top = hk; s_kt = ok; s_kb = ck; s_bar = bi; s_set = True
        # B11 (L1291-1296, L1354-1357)
        pos_n = -pos if inv else pos
        raw_l = n_buy and pos_n <= 0
        raw_s = n_sell and pos_n >= 0
        buy_go = raw_l and buy_ok[k]
        sell_go = (not buy_go) and raw_s and sell_ok[k]
        if raw_l:
            n_rl += 1
            if not buy_ok[k]:
                n_bl += 1
        if raw_s:
            n_rs += 1
            if not sell_ok[k]:
                n_bs += 1
        if inv:
            place_long = sell_go
            place_short = buy_go
            lfd = not orig_dir
        else:
            place_long = buy_go
            place_short = sell_go
            lfd = orig_dir
        # B12 (L1302-1351): entry / atomic reversal at this close
        entered = False
        closed_now = False
        closed_pnl = 0.0
        if place_long or place_short:
            nd = 1 if place_long else -1
            equity = cash
            if pos != 0:
                equity = cash + pos * qty * (ck - avg) * pv
            q, capped = _fq(sl_now, equity, ck, risk_mode, fixed_qty, risk_pct, max_qty, qty_step,
                            cap_margin, margin_pct, pv)
            if q > 0.0:
                px = ck + nd * slip
                if pos == -nd:
                    xc = qty * (c_fix + c_pct * px)
                    gross = pos * qty * (px - avg) * pv
                    cash += gross - xc
                    closed_pnl = gross - (e_cost + xc)
                    closed_now = True
                    slip_paid += slip * qty
                    t_dir[nt] = pos; t_ek[nt] = e_k; t_xk[nt] = k; t_epx[nt] = avg; t_qty[nt] = qty
                    t_xpx[nt] = px; t_kind[nt] = K_REV; t_gross[nt] = gross; t_cost[nt] = e_cost + xc
                    t_eqb[nt] = e_eqb; t_sig[nt] = e_sig; t_zone[nt] = e_zone; t_sld[nt] = e_sld
                    t_slpx[nt] = e_slpx; t_tppx[nt] = e_tppx; t_re[nt] = e_re; t_inh[nt] = e_inh
                    nt += 1
                e_eqb = cash
                e_cost = q * (c_fix + c_pct * px)
                cash -= e_cost
                slip_paid += slip * q
                pos = nd; qty = q; avg = px; ebar = bi; e_k = k
                e_sig = 1 if buy_go else -1
                e_zone = 1 if (buy_go == orig_dir) else 0     # the zone whose retest gave the signal
                e_re = pha
                e_inh = False
                entered = True
                if capped:
                    n_capped += 1
            else:
                n_zero += 1
                flags |= 32768
                # a decision sized to zero places no order, so no fill follows and (on a candle
                # without a bracket fill, where this IS the bar-close run) nothing rolls back
                # the pending* variables it wrote (L1304-1307 / L1329-1332). On a candle WITH a
                # bracket fill the decision belongs to the run after that fill and is rolled back,
                # unless limitOneDecisionPerBar is off (L1243): the bar-close run then decides
                # again, and its writes stay
                if rollback and (pha == 0 or not lock_entry):
                    if place_long:
                        p_la = a; p_sa = np.nan
                    else:
                        p_sa = a; p_la = np.nan
                    p_sl = sl_now
                    p_tp = tp_now
            # L1314-1326 / L1339-1351. With rollback the reset only survives when no fill follows
            # the run that made it: a decision sized to zero (no order) on a candle WITHOUT a
            # bracket fill. After a bracket fill the decision belongs to the run that follows that
            # intrabar fill, and the bar-close run that comes after it rolls the reset back.
            if one_zone and ((not rollback) or (q <= 0.0 and pha == 0)):
                if place_long == lfd:
                    d_set = False
                else:
                    s_set = False
            elif one_zone and q <= 0.0 and not lock_entry:
                # limitOneDecisionPerBar off (L103, L1243): after a bracket fill the bar-close run
                # is not locked out, decides again (quantity 0 again: same equity, same close),
                # and nothing follows it: its reset stays
                if place_long == lfd:
                    d_set = False
                else:
                    s_set = False
        if pos != 0 and not entered:
            if forced:
                # B14 (L1457-1486): blackout > dead > time
                if blk_x:
                    xkind = K_BLK
                elif dead_x:
                    xkind = K_DEAD
                else:
                    xkind = K_TIME
                if xkind != K_BLK and not rollback:
                    cd_until = bi + cd_bars
                xpx = ck - pos * slip
                xc = qty * (c_fix + c_pct * xpx)
                gross = pos * qty * (xpx - avg) * pv
                cash += gross - xc
                closed_pnl = gross - (e_cost + xc)
                closed_now = True
                slip_paid += slip * qty
                t_dir[nt] = pos; t_ek[nt] = e_k; t_xk[nt] = k; t_epx[nt] = avg; t_qty[nt] = qty
                t_xpx[nt] = xpx; t_kind[nt] = xkind; t_gross[nt] = gross; t_cost[nt] = e_cost + xc
                t_eqb[nt] = e_eqb; t_sig[nt] = e_sig; t_zone[nt] = e_zone; t_sld[nt] = e_sld
                t_slpx[nt] = e_slpx; t_tppx[nt] = e_tppx; t_re[nt] = e_re; t_inh[nt] = e_inh
                nt += 1
                pos = 0; qty = 0.0; avg = np.nan
                stop = np.nan; tgt = np.nan; skind = K_SL
                atr_e = np.nan; sl_e = np.nan; tp_e = np.nan
                tr_armed = False; tr_stop = np.nan; be_armed = False
            else:
                # B13 (L1411-1450): the bracket for the next candle
                stop, tgt, skind, tr_armed, tr_stop, be_armed = _protect(
                    pos, ck, avg, atr_e, sl_e, tp_e, tr_armed, tr_stop, be_armed,
                    use_trail, tr_act_now, tr_dst_now, be_on, be_trig)

        # ---------------- C. after the fills at this close ----------------
        if closed_now:                       # C1
            if closed_pnl < 0.0:
                cons += 1
            else:
                cons = 0
            if lc_on and cons >= lc_trig:
                pause_until = bi + lc_bars
                cons = 0
        if entered:                          # C2 (L1371-1393, then the protective block)
            if rollback and inh_side == pos:
                atr_e = inh_atr; sl_e = inh_sl; tp_e = inh_tp
                tr_armed = inh_ta; tr_stop = inh_ts; be_armed = inh_be
                e_inh = True
            else:
                atr_e = a; sl_e = sl_now; tp_e = tp_now
                tr_armed = False; tr_stop = np.nan; be_armed = False
                if rollback:
                    # L1372-1374 / L1384-1386 in the post-fill run: the pending* values are those of
                    # the END OF THE PREVIOUS CANDLE (this candle's own writes were rolled back):
                    # na, unless an earlier decision sized to zero left them
                    p_a = p_la if pos > 0 else p_sa
                    if not np.isnan(p_a):
                        atr_e = p_a
                    if not np.isnan(p_sl):
                        sl_e = p_sl
                        tp_e = p_tp
                    p_la = np.nan
                    p_sa = np.nan
            stop, tgt, skind, tr_armed, tr_stop, be_armed = _protect(
                pos, ck, avg, atr_e, sl_e, tp_e, tr_armed, tr_stop, be_armed,
                use_trail, tr_act_now, tr_dst_now, be_on, be_trig)
            e_sld = sl_e
            e_slpx = stop
            e_tppx = tgt
            if pre[k]:                       # C3: close_all in the post-fill run, at this same close (E8)
                xpx = ck - pos * slip
                xc = qty * (c_fix + c_pct * xpx)
                gross = pos * qty * (xpx - avg) * pv
                cash += gross - xc
                pnl = gross - (e_cost + xc)
                slip_paid += slip * qty
                t_dir[nt] = pos; t_ek[nt] = e_k; t_xk[nt] = k; t_epx[nt] = avg; t_qty[nt] = qty
                t_xpx[nt] = xpx; t_kind[nt] = K_BLK; t_gross[nt] = gross; t_cost[nt] = e_cost + xc
                t_eqb[nt] = e_eqb; t_sig[nt] = e_sig; t_zone[nt] = e_zone; t_sld[nt] = e_sld
                t_slpx[nt] = e_slpx; t_tppx[nt] = e_tppx; t_re[nt] = e_re; t_inh[nt] = e_inh
                nt += 1
                pos = 0; qty = 0.0; avg = np.nan
                stop = np.nan; tgt = np.nan; skind = K_SL
                atr_e = np.nan; sl_e = np.nan; tp_e = np.nan
                tr_armed = False; tr_stop = np.nan; be_armed = False
                if pnl < 0.0:
                    cons += 1
                else:
                    cons = 0
                if lc_on and cons >= lc_trig:
                    pause_until = bi + lc_bars
                    cons = 0

        if pos == 0:                         # L1395-1401 in the last run of the candle
            p_sl = np.nan
            p_tp = np.nan

        # ---------------- D. bar-close equity ----------------
        equity = cash
        if pos != 0:
            equity = cash + pos * qty * (ck - avg) * pv
            n_pos += 1
            if equity < qty * ck * 0.002:
                n_margin += 1
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
            if orig_buy:
                flags |= 1
            if orig_sell:
                flags |= 2
            if n_buy:
                flags |= 4
            if n_sell:
                flags |= 8
            if raw_l:
                flags |= 16
            if raw_s:
                flags |= 32
            if raw_l and not buy_ok[k]:
                flags |= 64
            if raw_s and not sell_ok[k]:
                flags |= 128
            if buy_go:
                flags |= 256
            if sell_go:
                flags |= 512
            if allowed:
                flags |= 1024
            if in_pause:
                flags |= 2048
            if in_cd:
                flags |= 4096
            if forced:
                flags |= 8192
            if vol_block:
                flags |= 16384
            if pha != 0:
                flags |= 65536
            b_eq[k] = equity
            b_pos[k] = pos
            b_stop[k] = stop
            b_tgt[k] = tgt
            b_flags[k] = flags
            b_cons[k] = cons
            b_pause[k] = pause_until
            b_cd[k] = cd_until

    # window end (E10): a trade still open is closed at the last close as a market fill
    if pos != 0:
        k = n - 1
        xpx = c[k] - pos * slip
        xc = qty * (c_fix + c_pct * xpx)
        gross = pos * qty * (xpx - avg) * pv
        cash += gross - xc
        slip_paid += slip * qty
        t_dir[nt] = pos; t_ek[nt] = e_k; t_xk[nt] = k; t_epx[nt] = avg; t_qty[nt] = qty
        t_xpx[nt] = xpx; t_kind[nt] = K_END; t_gross[nt] = gross; t_cost[nt] = e_cost + xc
        t_eqb[nt] = e_eqb; t_sig[nt] = e_sig; t_zone[nt] = e_zone; t_sld[nt] = e_sld
        t_slpx[nt] = e_slpx; t_tppx[nt] = e_tppx; t_re[nt] = e_re; t_inh[nt] = e_inh
        nt += 1
        eq_last = cash
        if full:
            b_eq[k] = cash
    if n > 0:
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
    stats = np.array([eq_last, eq_mid, dd_rel, dd_abs, float(n_pos), float(n_rl), float(n_rs), float(n_bl),
                      float(n_bs), slip_paid, float(n_zero), float(n_capped), float(n_margin), cash])
    return (t_dir[:nt].copy(), t_ek[:nt].copy(), t_xk[:nt].copy(), t_epx[:nt].copy(), t_qty[:nt].copy(),
            t_xpx[:nt].copy(), t_kind[:nt].copy(), t_gross[:nt].copy(), t_cost[:nt].copy(), t_eqb[:nt].copy(),
            t_sig[:nt].copy(), t_zone[:nt].copy(), t_sld[:nt].copy(), t_slpx[:nt].copy(), t_tppx[:nt].copy(),
            t_re[:nt].copy(), t_inh[:nt].copy(), t_xs[:nt].copy(), stats,
            b_eq, b_pos, b_stop, b_tgt, b_flags, b_cons, b_pause, b_cd,
            b_dkt, b_dkb, b_dbar, b_skt, b_skb, b_sbar)


_R_KEYS = ('dir', 'ek', 'xk', 'epx', 'qty', 'xpx', 'kind', 'gross', 'cost', 'eqb', 'sig', 'zone', 'sld', 'slpx',
           'tppx', 're', 'inh', 'xs', 'stats',
           'eq', 'pos', 'stop', 'tgt', 'flags', 'cons', 'pause', 'cd', 'dkt', 'dkb', 'dbar', 'skt', 'skb', 'sbar')
FLAG_BITS = dict(orig_buy=1, orig_sell=2, n_buy=4, n_sell=8, raw_l=16, raw_s=32, blk_l=64, blk_s=128,
                 buy_go=256, sell_go=512, allowed=1024, in_pause=2048, in_cd=4096, forced=8192, vol_block=16384,
                 zero_qty=32768, bracket_fill=65536)


# ----------------------------------------------------------------------------
# public interface
# ----------------------------------------------------------------------------
def _window(pair, chart_tf, Q):
    b = load_bars(pair, chart_tf)
    s0, e0 = WINDOWS[pair]
    start = int(Q['start']) if Q['start'] is not None else s0
    end = int(Q['end']) if Q['end'] is not None else e0
    w0 = int(np.searchsorted(b['t_close'], start, side='left'))
    w1 = int(np.searchsorted(b['t_close'], end, side='right'))
    return start, end, w0, w1


_PERM = {}


def permissions(pair, chart_tf, start, end, fgfp):
    key = (pair, str(chart_tf), start, end, tuple(sorted((k, str(v)) for k, v in fgfp.items())))
    if key not in _PERM:
        if W not in sys.path:
            sys.path.insert(0, W)
        import fgf
        _PERM[key] = fgf.fgf_permissions(pair, chart_tf, start, end, fgfp)
    return _PERM[key]


def _fgf_default(k, fallback):
    if W not in sys.path:
        sys.path.insert(0, W)
    import fgf
    return fgf.DEFAULTS.get(k, fallback)          # display-only filter inputs: any value is accepted


def resolve_preset(pair, chart_tf, Q):
    """L849-933: the preset flags and the active SIGNAL settings."""
    mode = Q['presetMode']
    tf = str(chart_tf)
    tf_min = int(tf) if tf.isdigit() else 0                      # timeframe.isminutes ? multiplier : 0
    is_xau = ('XAUUSD' in TICKER[pair]) or ('GOLD' in TICKER[pair])
    preset_xau = mode == "XAUUSD 5m" or (mode == "Auto" and is_xau and tf_min == 5)
    using = preset_xau                                           # the other presets are not implemented
    use_profile = using and (bool(Q['lockAutoProfile']) or Q['v2Source'] == "Auto Optimized Profile")
    return dict(
        presetXAUUSD=preset_xau, usingFxPreset=using, useProfile=use_profile,
        zoneLengthInput=50 if using else int(Q['manualZoneLength']),
        deltaThresholdInput=1.5 if using else float(Q['manualDeltaThreshold']),
        emaLength=100 if using else int(Q['manualEmaLength']),
        entryMode="Normal Retest Touch" if using else Q['manualEntryMode'],
        entryBufferActive=True if use_profile else bool(Q['useEntryBuffer']),
        entryBufferMin=60 if use_profile else int(Q['entryBufferIn']),
        sundayBlockActive=preset_xau if use_profile else bool(Q['useSundayBlock']),     # profSundayBlock
        entryWindowActive=False if use_profile else bool(Q['useEntryWindow']),
        entryWindow="0800-1200" if use_profile else Q['entryWindowIn'],
        useEmaFilter=bool(Q['manualUseEmaFilter']),
        zoneTrendFilter=bool(Q['manualZoneTrend']) if mode == "Manual" else False,
        invalidateZones=bool(Q['manualInvalidate']),
        minRetestBars=int(Q['manualMinRetestBars']),
        maxZoneAge=int(Q['manualMaxZoneAge']),
    )


def prepare(pair, chart_tf, params=None):
    """Everything that does not depend on the ORDER / EXIT inputs: the window, the chart OHLC, the
    spikes, the EMA trend flags, the New York clock gates, the preset windows, the zone seed, the
    filter permissions, the ATR cache. params may also carry ORDER / EXIT inputs: they become the
    defaults of simulate(P, x)."""
    Q, fgfp = _params(params)
    chart_tf = str(chart_tf)
    b = load_bars(pair, chart_tf)
    start, end, w0, w1 = _window(pair, chart_tf, Q)
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    A = resolve_preset(pair, chart_tf, Q)
    o, h, l, c = b['open'], b['high'], b['low'], b['close']
    sl = slice(w0, w1)

    # ---- series from the start of the data file (section 4)
    vd = _volume_delta(o, h, l, c, b['volume'])
    avg_delta = _sma_abs(vd, A['zoneLengthInput'])
    ema = _ema(c, A['emaLength'])
    thr = avg_delta * A['deltaThresholdInput']
    with np.errstate(invalid='ignore'):
        ok_avg = ~np.isnan(avg_delta)
        d_spike = ok_avg & (vd > thr) & (c > o)                   # rawDemandSpike (L1129)
        s_spike = ok_avg & (vd < -thr) & (c < o)                  # rawSupplySpike (L1130)
    if A['zoneTrendFilter']:
        d_spike = d_spike & (c > ema)
        s_spike = s_spike & (c < ema)
    if A['useEmaFilter']:
        trend_l = c > ema                                         # L1122-1123
        trend_s = c < ema
    else:
        trend_l = np.ones(len(c), np.bool_)
        trend_s = np.ones(len(c), np.bool_)
    seed = _zone_seed(o, h, l, c, d_spike, s_spike, bool(A['invalidateZones']), w0)

    # ---- New York clock of the bar open and the gates (window rows)
    to = b['t_open'][sl]
    dow, hour, minute = _ny_clock(to)
    mins = hour * 60 + minute
    FRI, SAT, SUN, MON, THU = 6, 7, 1, 2, 5
    d_start = 16 * 60 + 55
    d_end = 18 * 60
    lead = int(Q['closeLeadMin'])
    use_we = bool(Q['useWeekendBlackout'])
    use_da = bool(Q['useDailyBlackout'])
    weekend = use_we & (((dow == FRI) & (mins >= d_start)) | (dow == SAT) | ((dow == SUN) & (mins < d_end)))
    mon_thu = (dow >= MON) & (dow <= THU)
    daily = use_da & mon_thu & (mins >= d_start) & (mins < d_end)
    blackout = weekend | daily
    pre_window = (mins >= d_start - lead) & (mins < d_start)
    pre = (use_we & (dow == FRI) & pre_window) | (use_da & mon_thu & pre_window)
    near = (bool(A['entryBufferActive']) & (dow >= MON) & (dow <= FRI)
            & (mins >= d_start - int(A['entryBufferMin'])) & (mins < d_end))
    sunday = bool(A['sundayBlockActive']) & (dow == SUN)
    in_sess = (np.ones(n, np.bool_) if not Q['useSessionFilter']
               else _in_session(pair, to, Q['nySession'], mins, dow))
    in_win = (np.ones(n, np.bool_) if not A['entryWindowActive']
              else _in_session(pair, to, A['entryWindow'], mins, dow))
    px = bool(A['presetXAUUSD'])
    false = np.zeros(n, np.bool_)
    if px:
        robust = bool(Q['useRobustHourFilter']) & ((hour == 3) | (hour == 14) | (hour == 18))
        long_dir = bool(Q['useDirectionalMicroFilter']) & (hour == 4) & (minute >= 0) & (minute < 15)
        short_dir = bool(Q['useDirectionalMicroFilter']) & (hour == 9) & (minute >= 0) & (minute < 15)
        v105_l = bool(Q['useV105DirectionalFilter']) & (((hour == 10) & (minute >= 15) & (minute < 30))
                                                        | ((hour == 11) & (minute >= 30)))
        v1010_l = bool(Q['useV1010PfFilter']) & (((hour == 1) & (minute >= 15) & (minute < 30))
                                                 | ((hour == 4) & (minute >= 15) & (minute < 30)))
        v1010_s = bool(Q['useV1010PfFilter']) & (hour == 4) & (minute >= 45)
        lblock = long_dir | v105_l | v1010_l
        sblock = short_dir | v1010_s                              # v105ShortBlock: NAS100 / XAGUSD only
    else:
        robust = false
        lblock = false
        sblock = false
    gate = in_sess & in_win & ~blackout & ~near & ~sunday & ~robust
    bclose = blackout | pre

    # ---- the filter
    if Q['fgfOn']:
        perm = permissions(pair, chart_tf, start, end, fgfp)
        if perm.index[0] != w0 or len(perm) != n:
            raise RuntimeError('filter rows do not match the window')
        buy_ok = np.ascontiguousarray(perm['buyOk'].to_numpy(bool))
        sell_ok = np.ascontiguousarray(perm['sellOk'].to_numpy(bool))
    else:
        buy_ok = np.ones(n, np.bool_)
        sell_ok = np.ones(n, np.bool_)

    tc = b['t_close'][sl]
    mid = start + (end - start) // 2
    pc = np.empty(n)
    if w0 > 0:
        pc[:] = c[w0 - 1:w1 - 1]
    else:
        pc[0] = np.nan                                            # close[1] is na on the first bar
        pc[1:] = c[0:w1 - 1]
    ca = np.ascontiguousarray
    return dict(
        pair=pair, tf=chart_tf, start=start, end=end, w0=w0, w1=w1, n=n, mid=mid,
        mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
        o=ca(o[sl]), h=ca(h[sl]), l=ca(l[sl]), c=ca(c[sl]), pc=pc, t_open=ca(to), t_close=ca(tc),
        d_spike=ca(d_spike[sl]), s_spike=ca(s_spike[sl]), trend_l=ca(trend_l[sl]), trend_s=ca(trend_s[sl]),
        gate=ca(gate), bclose=ca(bclose), pre=ca(pre), lblock=ca(lblock), sblock=ca(sblock),
        buy_ok=buy_ok, sell_ok=sell_ok, seed=seed, active=A, params=Q, fgfp=fgfp, atr={}, sub=None,
        # diagnostics (window rows)
        diag=dict(vd=ca(vd[sl]), avg_delta=ca(avg_delta[sl]), ema=ca(ema[sl]), dow=dow, hour=hour, minute=minute,
                  blackout=blackout, pre=pre, near=near, sunday=sunday, weekend=weekend, daily=daily, robust=robust),
    )


def get_atr(P, length):
    """ta.atr(length) on the window rows, computed from the start of the data file; cached."""
    length = int(length)
    if length not in P['atr']:
        b = load_bars(P['pair'], P['tf'])
        P['atr'][length] = np.ascontiguousarray(_atr(b['high'], b['low'], b['close'], length)[P['w0']:P['w1']])
    return P['atr'][length]


def sub_bars(pair, chart_tf, w0, w1, check=True):
    """The 1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows
    of data/<pair>_1.parquet with t_open in [chart t_open, chart t_close). Returns
    (ptr, o, h, l, c, t_open): ptr int64 (n + 1); the sub-bars of window candle k are the rows
    [ptr[k], ptr[k+1]) of the five contiguous arrays. With check, every chart candle has at least
    one sub-bar and its OHLC equals the sub-bars' first open / highest high / lowest low / last
    close (build_bars.py built the chart bars from them)."""
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


def get_sub(P):
    """The sub-bar table of P's window, built once and kept in P['sub']."""
    if P.get('sub') is None:
        P['sub'] = sub_bars(P['pair'], P['tf'], P['w0'], P['w1'])
    return P['sub']


def fake_sub_bars(P):
    """One sub-bar per chart candle, equal to the candle (tests: mag on it == tv)."""
    n = P['n']
    return (np.arange(n + 1, dtype=np.int64), P['o'], P['h'], P['l'], P['c'], P['t_open'])


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, np.int64))


def resolve_exit(P, Q):
    """L904-933 and L1089-1097: the active ORDER / EXIT settings."""
    A = P['active']
    up = A['useProfile']
    px = A['presetXAUUSD']
    return dict(
        deadExitActive=(not px) if up else bool(Q['useDeadExit']),          # profDeadOn = not presetXAUUSD
        deadBars=15 if up else int(Q['deadBarsIn']),                        # profDeadBars (NAS100: 10)
        breakevenActive=False if up else bool(Q['useBreakeven']),
        beTrigger=1.0 if up else float(Q['beTriggerAtr']),
        onePerZoneActive=True if up else bool(Q['useOnePerZone']),
        cooldownActive=True if up else bool(Q['useCooldown']),
        cooldownBars=10 if up else int(Q['cooldownIn']),
        lossClusterProfileActive=bool(Q['useV1011LossClusterPause']),
        lossClusterTrigger=5 if px else int(Q['manualLossClusterCount']),
        lossClusterPauseBars=12 if px else int(Q['manualLossClusterPauseBars']),
        costFilterActive=bool(Q['useV1013VolCostFilter']) and px,           # topThreeCostProfile
        modeledSlippageTicks=(int(Q['modeledSlippageTicksOverride']) if int(Q['modeledSlippageTicksOverride']) > 0
                              else 75),
    )


def simulate(P, x=None, full=False, sub=None):
    """Orders and exits on prepare()'s arrays. x: ORDER / EXIT inputs by Pine name (signalDirection,
    dpInv or its alias inv, ExitMode, atrLenS2, slAtrMultS2, tpRS2, ..., QtyMode, ...), path
    ('tv' | 'mag'), cost ('tv' | 'ours' | 'stress'), varRollback. A SIGNAL input in x that differs
    from prepare()'s raises. full=True adds the per-candle state arrays (traces). sub: a sub-bar
    table to use on the 'mag' path instead of the 1-minute data (tests: fake_sub_bars)."""
    Q = P['params']
    if x:
        Q = dict(Q)
        for k, v in x.items():
            k = _ALIASES.get(k, k)
            if k in _DISPLAY:
                continue
            if k == 'fgfOn':
                if bool(v) != bool(Q['fgfOn']):
                    raise ValueError("'fgfOn' is fixed by prepare()")
                continue
            if k.startswith('fgf') or k.startswith('fgs') or k == 'FGF_FORCE_OVERLAY':
                if k in P['fgfp'] and P['fgfp'][k] != v:
                    raise ValueError('%r is fixed by prepare()' % (k,))
                if k not in P['fgfp'] and _fgf_default(k, v) != v:
                    raise ValueError('%r is fixed by prepare()' % (k,))
                continue
            if k not in DEFAULTS:
                raise ValueError('unknown param %r' % (k,))
            if k in _PREP_KEYS and v != Q[k]:
                raise ValueError('%r is fixed by prepare()' % (k,))
            Q[k] = v
        _check(Q)
    E = resolve_exit(P, Q)
    A = P['active']
    # ta.atr is na on the first atrLenS2 - 1 rows of the data file; if the window reaches them the
    # kernel follows the Pine: every distance is na, f_qty returns 0 in Risk mode (no order), a
    # Fixed-quantity trade gets no bracket (L1415-1416)
    atr = get_atr(P, Q['atrLenS2'])
    c_fix, c_pct = COSTS[Q['cost']][P['pair']]
    mag = Q['path'] == 'mag'
    if mag:
        S = sub if sub is not None else get_sub(P)
    else:
        S = _NO_SUB
    out = _kernel(
        P['o'], P['h'], P['l'], P['c'], P['pc'], atr, P['d_spike'], P['s_spike'], P['trend_l'], P['trend_s'],
        P['gate'], P['bclose'], P['pre'], P['lblock'], P['sblock'], P['buy_ok'], P['sell_ok'],
        int(P['w0']), P['seed'], mag, S[0], S[1], S[2], S[3], S[4],
        bool(A['invalidateZones']), int(A['minRetestBars']), int(A['maxZoneAge']),
        A['entryMode'] == "Close Beyond Key Zone",
        Q['signalDirection'] == SIG_ORIG, bool(Q['dpInv']), Q['ExitMode'] == "Points",
        float(Q['slAtrMultS2']), float(Q['tpRS2']), float(Q['slPointsIn']), float(Q['tpPointsIn']),
        bool(Q['useTrailS2']), float(Q['trailActAtr']), float(Q['trailDstAtr']), float(Q['trailActPts']),
        float(Q['trailPts']),
        int(Q['timeStopBars']), bool(E['deadExitActive']), int(E['deadBars']), bool(E['breakevenActive']),
        float(E['beTrigger']), bool(E['onePerZoneActive']), bool(E['cooldownActive']), int(E['cooldownBars']),
        bool(E['lossClusterProfileActive']), int(E['lossClusterTrigger']), int(E['lossClusterPauseBars']),
        bool(E['costFilterActive']), float(Q['minStopToCostRatio']), float(E['modeledSlippageTicks']),
        Q['QtyMode'] == "Risk %", float(Q['fixedQtyS3']), float(Q['riskPctS3']), float(Q['maxQtyS3']),
        float(Q['qtyStepS3']), bool(Q['capMarginS3']), float(Q['marginPctS3']),
        float(SLIP[Q['cost']]), float(c_fix), float(c_pct), bool(Q['varRollback']),
        bool(Q['limitOneDecisionPerBar']),
        INITIAL_CAPITAL, MINTICK, POINTVALUE, int(P['mid_j']), bool(full))
    R = dict(zip(_R_KEYS, out))
    R['x'] = Q
    R['exit'] = E
    R['sub_t_open'] = S[5] if mag else None
    return R


def trades(P, R):
    """One row per trade, in exit order (SPEC_danny section 11)."""
    w0 = P['w0']
    to = P['t_open']
    tc = P['t_close']
    kind = R['kind'].astype(np.int64)
    ek = R['ek']
    xk = R['xk']
    bracket = (kind == K_SL) | (kind == K_TP) | (kind == K_TRAIL) | (kind == K_BE)
    pnl = R['gross'] - R['cost']
    sld = R['sld']
    with np.errstate(invalid='ignore', divide='ignore'):
        r_mult = np.where(sld > 0, pnl / (sld * R['qty'] * POINTVALUE), np.nan)
    # a bracket exit happens inside the candle: its time is the candle's open ('tv') or the open of
    # the 1-minute sub-bar in which it filled ('mag'); every other exit is a fill at a close
    x_open = to[xk]
    if R.get('sub_t_open') is not None and len(xk):
        xs = R['xs']
        x_open = np.where(xs >= 0, R['sub_t_open'][np.maximum(xs, 0)], x_open)
    return pd.DataFrame({
        'dir': R['dir'].astype(np.int64),
        'entry_time': tc[ek],                                   # the fill is at the entry candle's close
        'entry_px': R['epx'],
        'qty': R['qty'],
        'exit_time': np.where(bracket, x_open, tc[xk]),
        'exit_px': R['xpx'],
        'exit_kind': [KINDS[i] for i in kind],
        'pnl': pnl,
        'entry_bar': ek + w0,
        'exit_bar': xk + w0,
        'eq_before': R['eqb'],
        'pnl_gross': R['gross'],
        'costs': R['cost'],
        'sig': R['sig'].astype(np.int64),
        'zone': np.where(R['zone'] == 1, 'D', 'S'),
        'sl_dist': sld,
        'sl_px': R['slpx'],
        'tp_px': R['tppx'],
        'r_mult': r_mult,
        'reentry': R['re'].astype(np.int64),
        'inherit': R['inh'].astype(bool),
    })


def summary(P, R):
    """The common fields as hrd.summary_fast computes them (initial capital 2,000) plus this
    strategy's own (SPEC_danny section 11)."""
    init = INITIAL_CAPITAL
    pnl = R['gross'] - R['cost']
    st = R['stats']
    final = float(st[0])
    eq_mid = float(st[1])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    nt = len(pnl)
    d = R['dir']
    kind = R['kind'].astype(np.int64)
    kc = np.bincount(kind, minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    out = dict(
        start=int(P['start']), end=int(P['end']), bars=int(P['n']),
        trades=nt,
        net_pct=(final - init) / init * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if nt else np.nan,
        max_dd_pct=float(st[2] * 100),
        max_dd_init_pct=float(st[3] / init * 100),
        long=int((d > 0).sum()), short=int((d < 0).sum()),
        raw_long=int(st[5]), raw_short=int(st[6]), blocked_long=int(st[7]), blocked_short=int(st[8]),
        half1_pct=(eq_mid - init) / init * 100,
        half2_pct=(final - eq_mid) / init * 100,
        exposure=float(st[4] / P['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((R['ek'] == R['xk']).sum())
    # fair halves: trades ENTERED in each half (entry_time = t_close of the entry candle)
    first = P['t_close'][R['ek']] <= P['mid']
    r = 1.0 + pnl / R['eqb']
    n1 = int(first.sum())
    out['h1r_pct'] = (float(np.prod(r[first])) - 1.0) * 100.0
    out['h2r_pct'] = (float(np.prod(r[~first])) - 1.0) * 100.0
    out['h1_trades'] = n1
    out['h2_trades'] = nt - n1
    out['avg_bars_held'] = float((R['xk'] - R['ek']).mean()) if nt else np.nan
    out['costs'] = float(R['cost'].sum())
    sld = R['sld']
    with np.errstate(invalid='ignore', divide='ignore'):
        r_mult = np.where(sld > 0, pnl / (sld * R['qty'] * POINTVALUE), np.nan)
    out['slippage_paid'] = float(st[9])
    out['net_r'] = float(np.nansum(r_mult)) if nt else 0.0
    out['reentry_same_bar'] = int((R['re'] > 0).sum())
    out['reentry_leg1'] = int((R['re'] == 1).sum())
    out['inherited'] = int(R['inh'].sum())
    out['zero_qty'] = int(st[10])
    out['qty_capped'] = int(st[11])
    out['margin_breach'] = int(st[12])
    return out


def run(pair, chart_tf, params=None):
    """prepare + simulate with one dict -> (trades, summary)."""
    P = prepare(pair, chart_tf, params)
    R = simulate(P)
    s = summary(P, R)
    s.update(pair=pair, tf=P['tf'], w0=P['w0'], w1=P['w1'])
    return trades(P, R), s


def fmt(s):
    ex = ' '.join('%s=%d' % (k, s['exit_' + k]) for k in KINDS[1:] if s['exit_' + k])
    return ('trades=%d (L %d / S %d) net=%.3f%% pf=%.3f win=%.1f%% maxDD=%.2f%% h1r=%.2f%% h2r=%.2f%% '
            'raw L/S=%d/%d blocked L/S=%d/%d reentry=%d (leg1 %d) inherited=%d zero_qty=%d capped=%d '
            'slip=%.2f costs=%.2f exits: %s'
            % (s['trades'], s['long'], s['short'], s['net_pct'], s['pf'], s['win_pct'], s['max_dd_pct'],
               s['h1r_pct'], s['h2r_pct'], s['raw_long'], s['raw_short'], s['blocked_long'], s['blocked_short'],
               s['reentry_same_bar'], s['reentry_leg1'], s['inherited'], s['zero_qty'], s['qty_capped'],
               s['slippage_paid'], s['costs'], ex))


if __name__ == '__main__':
    for pair_ in ('BTC', 'XAU'):
        for fo in (True, False):
            t0 = _time.time()
            P_ = prepare(pair_, '60', {'fgfOn': fo})
            t1 = _time.time()
            for iv in (False, True):
                R_ = simulate(P_, {'inv': iv})
                print(pair_, '60', 'filter', 'on ' if fo else 'off', 'inv', iv, fmt(summary(P_, R_)))
            print('   prepare %.2fs' % (t1 - t0))
