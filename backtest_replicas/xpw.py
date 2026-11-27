"""XPW v2.8 ladder and labels (Component 2): CANONICAL module.

Byte-for-byte the logic of xpw_a.py (implementation A), chosen by the
reconciler as the faster of the two implementations once both agreed on 100%
of rows on every reconciliation case (see reconcile_xpw.md). Only this
docstring differs from xpw_a.py.

Python replica of the fused script
/home/user/master/xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine from
"// PER-RUNG WINDOWS" through the end of the "SIGNAL RUNGS" section
(rungState on every rung timeframe, request.security mapping, the ladder
assembly, chart anchor, READ HERE, rungEvents / labelAction and the per-bar
signal-rung loop that fills longSrc / shortSrc / exitL / exitS), plus the
"both sides cancel" zeroing at the top of STRATEGY (nLong / nShort).

Public interface:

    xpw_signals(pair, chart_tf, start, end, params=None) -> pandas.DataFrame

Rows = chart bars of data/<pair>_<chart_tf>.parquet with start <= t_close <= end,
index = their row numbers in that file. Warm-up for prevPosA / prevReadAt: one
chart bar before the window (exact: the only bar-to-bar state is the previous
bar's posA and readAt). agreeOn = True raises NotImplementedError.
See xpw_a_notes.md for every place where the Pine had to be interpreted.
"""
from __future__ import annotations

import numpy as np
import numba as nb
import pandas as pd

W = '/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/'
DATA = W + 'data/'

# ---------------------------------------------------------------- constants
TF_NAME = ["1 Month", "1 Week", "1 Day", "4 Hour", "1 Hour", "30 Min", "15 Min",
           "5 Min", "1 Min", "30 Sec", "15 Sec", "5 Sec", "1 Sec"]
RUNG_TF = ["M", "W", "D", "240", "60", "30", "15", "5", "1", "30S", "15S", "5S", "1S"]
TF_SEC = np.array([2592000., 604800., 86400., 14400., 3600., 1800., 900., 300., 60.,
                   30., 15., 5., 1.])
N_RUNG = 13
N_DATA_RUNG = 9          # rungs 9..12 are seconds: no data -> na

# positions (posA); -1 = "" (the initial prevPosA value)
P_EMPTY, P_UNAVAIL, P_UNREAD, P_STAIR, P_END1, P_FIRST, P_SECOND, P_MID2, P_MID1 = -1, 0, 1, 2, 3, 4, 5, 6, 7
POS_NAMES = np.array(["UNAVAILABLE", "UNREADABLE", "STAIRCASE", "END FIRST LEG", "FIRST LEG",
                      "SECOND LEG", "MID SECOND LEG", "MID FIRST LEG"], dtype=object)
# shapes (shapeA)
SHAPE_NAMES = np.array(["-", "staircase", "refusal hi", "refusal lo", "area", "none"], dtype=object)
# label event codes (EV_*)
EV_NONE, EV_LEG1, EV_LEG2, EV_DIV, EV_END2, EV_LOOK, EV_STAIR = 0, 1, 2, 3, 4, 5, 6
# what the strategy does with an event (per row / rung)
K_NONE, K_LONG, K_SHORT, K_EXITL, K_EXITS = 0, 1, 2, 3, 4
# actions
ACTS = ["off", "enter", "enter opposite", "exit only"]
A_OFF, A_ENTER, A_OPP, A_EXIT = 0, 1, 2, 3
# rung-state flag bits (per rung timeframe bar); 255 = na (no rung bar / seconds rung)
F_RL, F_RH, F_C, F_SU, F_SD, F_OK = 1, 2, 4, 8, 16, 32
F_NA = 255
MARKS = ["", " *", " <<"]

SIG_RUNG_OPTS = ["chart rung (*)", "every rung (1 Sec to 1 Month)"] + TF_NAME

DEFAULTS = dict(
    rsiLen=13, fastLen=2, slowLen=7, bbLen=34, bbMult=1.6185,
    scaleWin=True, flatWin=20, areaLen=5, areaFrac=0.45, trendLen=20,
    sigRung="chart rung (*)", lblRead=True,
    actL1="enter", actL2="enter", actS1="enter", actS2="enter",
    actDL="enter", actDS="enter", actEnd="enter", actInf="enter",
    agreeOn=False, reverseAll=False, tradeAgree=True,
)

# Warm-up: the only state carried from bar to bar is prevPosA (= the previous
# chart bar's posA) and prevReadAt (= the previous bar's readAt); posA itself is
# rebuilt from the rung values on every bar. One chart bar before the window
# therefore reproduces a long chart exactly. WARMUP_BARS > 1 changes nothing
# (checked in xpw_a_check.py).
WARMUP_BARS = 1


def tf_in_seconds(tf: str) -> int:
    """Pine timeframe.in_seconds for the strings used here."""
    tf = str(tf)
    if tf.endswith('S'):
        return int(tf[:-1] or 1)
    if tf.endswith('D'):
        return int(tf[:-1] or 1) * 86400
    if tf.endswith('W'):
        return int(tf[:-1] or 1) * 604800
    if tf.endswith('M'):
        return int(tf[:-1] or 1) * 2628003     # Pine: 1M = 2628003 s
    return int(tf) * 60


def chart_index(chart_tf: str) -> int:
    """The Pine CHART ANCHOR loop: the last (smallest) rung with tfSec >= chartSec."""
    chart_sec = tf_in_seconds(chart_tf)
    idx = 0
    for i in range(N_RUNG):
        if TF_SEC[i] >= chart_sec:
            idx = i
    return idx


# ------------------------------------------------------------ TA primitives
@nb.njit(cache=True)
def _sma(x, n):
    """ta.sma: na until n values exist; na if the window holds an na."""
    N = x.shape[0]
    out = np.full(N, np.nan)
    for t in range(n - 1, N):
        s = 0.0
        bad = False
        for k in range(t - n + 1, t + 1):
            v = x[k]
            if np.isnan(v):
                bad = True
                break
            s += v
        if not bad:
            out[t] = s / n
    return out


@nb.njit(cache=True)
def _rsi(close, n):
    """ta.rsi: Wilder RMA of up / down changes, seeded with the SMA of the
    first n changes (first value on bar index n); 100 if down == 0, 0 if up == 0."""
    N = close.shape[0]
    out = np.full(N, np.nan)
    if N <= n:
        return out
    alpha = 1.0 / n
    su = 0.0
    sd = 0.0
    for k in range(1, n + 1):
        ch = close[k] - close[k - 1]
        su += ch if ch > 0.0 else 0.0
        sd += -ch if ch < 0.0 else 0.0
    up = su / n
    dn = sd / n
    for t in range(n, N):
        if t > n:
            ch = close[t] - close[t - 1]
            u = ch if ch > 0.0 else 0.0
            d = -ch if ch < 0.0 else 0.0
            up = alpha * u + (1.0 - alpha) * up
            dn = alpha * d + (1.0 - alpha) * dn
        if dn == 0.0:
            out[t] = 100.0
        elif up == 0.0:
            out[t] = 0.0
        else:
            out[t] = 100.0 - 100.0 / (1.0 + up / dn)
    return out


@nb.njit(cache=True)
def _rollext(x, n, is_max):
    """ta.highest / ta.lowest including the current bar; na before n bars or if
    the window holds an na."""
    N = x.shape[0]
    out = np.full(N, np.nan)
    for t in range(n - 1, N):
        m = x[t]
        if np.isnan(m):
            continue
        bad = False
        for k in range(t - n + 1, t):
            v = x[k]
            if np.isnan(v):
                bad = True
                break
            if is_max:
                if v > m:
                    m = v
            else:
                if v < m:
                    m = v
        if not bad:
            out[t] = m
    return out


def _shift(x, h):
    out = np.full(x.shape[0], np.nan)
    if h < x.shape[0]:
        out[h:] = x[:x.shape[0] - h]
    return out


# ------------------------------------------------------------- rung measure
def rung_state_arrays(high, low, close, h, rsiLen, fastLen, bbLen, areaLen, areaFrac, trendLen):
    """rungState(h) on one timeframe's own series. Returns (flags uint8, dir int8)
    per bar: bits F_RL refuseLow, F_RH refuseHigh, F_C compressed, F_SU stairUp,
    F_SD stairDown, F_OK dirOk; dir in {1, -1, 0}. All 7 Pine outputs are
    never na on the timeframe's bars (v6 bools), so na only arises from the
    request.security mapping."""
    high = np.ascontiguousarray(high, dtype=np.float64)
    low = np.ascontiguousarray(low, dtype=np.float64)
    close = np.ascontiguousarray(close, dtype=np.float64)
    r = _rsi(close, rsiLen)
    fast = _sma(r, fastLen)
    basis = _sma(r, bbLen)
    # (slow line and bands are computed by tdiCore but never used by rungState)

    recentLow = _rollext(low, h, False)
    priorLow = _shift(recentLow, h)
    recentHigh = _rollext(high, h, True)
    priorHigh = _shift(recentHigh, h)
    fastLowR = _rollext(fast, h, False)
    fastLowP = _shift(fastLowR, h)
    fastHighR = _rollext(fast, h, True)
    fastHighP = _shift(fastHighR, h)

    brokeLow = recentLow < priorLow
    brokeHigh = recentHigh > priorHigh
    tdiBrokeLow = fastLowR < fastLowP
    tdiBrokeHigh = fastHighR > fastHighP

    refuseLow = brokeLow & ~tdiBrokeLow
    refuseHigh = brokeHigh & ~tdiBrokeHigh

    rngShort = _rollext(fast, areaLen, True) - _rollext(fast, areaLen, False)
    rngLong = fastHighR - fastLowR          # ta.highest(fast, h) - ta.lowest(fast, h)
    with np.errstate(divide='ignore', invalid='ignore'):
        compressed = (rngLong > 0) & ((rngShort / rngLong) <= areaFrac)

    stairUp = brokeHigh & tdiBrokeHigh & ~refuseHigh
    stairDown = brokeLow & tdiBrokeLow & ~refuseLow

    smaC = _sma(close, trendLen)
    basisP = _shift(basis, trendLen)
    dirUp = (basis > basisP) & (close > smaC)
    dirDown = (basis < basisP) & (close < smaC)
    d = np.where(dirUp, 1, np.where(dirDown, -1, 0)).astype(np.int8)
    dirOk = ~np.isnan(basisP) & ~np.isnan(smaC)

    flags = (refuseLow.astype(np.uint8) * F_RL | refuseHigh.astype(np.uint8) * F_RH
             | compressed.astype(np.uint8) * F_C | stairUp.astype(np.uint8) * F_SU
             | stairDown.astype(np.uint8) * F_SD | dirOk.astype(np.uint8) * F_OK).astype(np.uint8)
    return flags, d


_TC_CACHE = {}
_RUNG_CACHE = {}


def _load(pair, tf, cols):
    return pd.read_parquet(DATA + f'{pair}_{tf}.parquet', columns=cols)


def _t_close(pair, tf):
    key = (pair, tf)
    if key not in _TC_CACHE:
        _TC_CACHE[key] = np.ascontiguousarray(_load(pair, tf, ['t_close'])['t_close'].to_numpy(np.int64))
    return _TC_CACHE[key]


def rung_state(pair, tf, h, p):
    """(t_close, flags, dir) of rungState(h) on <pair>_<tf>, all of its history. Cached."""
    key = (pair, tf, int(h), int(p['rsiLen']), int(p['fastLen']), int(p['bbLen']),
           int(p['areaLen']), float(p['areaFrac']), int(p['trendLen']))
    if key not in _RUNG_CACHE:
        df = _load(pair, tf, ['high', 'low', 'close', 't_close'])
        tc = np.ascontiguousarray(df['t_close'].to_numpy(np.int64))
        _TC_CACHE.setdefault((pair, tf), tc)
        flags, d = rung_state_arrays(df['high'].to_numpy(), df['low'].to_numpy(), df['close'].to_numpy(),
                                     int(h), int(p['rsiLen']), int(p['fastLen']), int(p['bbLen']),
                                     int(p['areaLen']), float(p['areaFrac']), int(p['trendLen']))
        _RUNG_CACHE[key] = (tc, flags, d)
    return _RUNG_CACHE[key]


def map_to_chart(tf_tclose, chart_tclose):
    """request.security(..., lookahead_off) on history: the last TF bar with
    t_close <= the chart bar's t_close; -1 = none (na)."""
    return np.searchsorted(tf_tclose, chart_tclose, side='right') - 1


# ------------------------------------------------------------ ladder kernel
@nb.njit(cache=True)
def _ladder(flags, dirs, chartIdx, everyRung, pickIdx, lblRead, reverseAll,
            act_tab, d_tab, prev0, prevReadAt0):
    """Per chart bar: ASSEMBLY, CHART ANCHOR (given), READ HERE, and the SIGNAL
    RUNGS loop (rungEvents + labelAction with agreeOn = false)."""
    n = flags.shape[0]
    pos = np.empty((n, 13), np.int8)
    shape = np.empty((n, 13), np.int8)
    orient = np.empty((n, 13), np.int8)
    inh = np.zeros((n, 13), np.bool_)
    readAt = np.empty(n, np.int8)
    base_out = np.empty(n, np.int8)
    code = np.zeros((n, 13), np.int8)
    kind = np.zeros((n, 13), np.int8)
    upf = np.zeros((n, 13), np.bool_)
    was2 = np.zeros((n, 13), np.bool_)
    mark = np.zeros((n, 13), np.int8)
    prev = prev0.copy()
    prevReadAt = prevReadAt0
    for t in range(n):
        # D2. baseDir from the highest rung whose direction is computed.
        base = 0
        for i in range(13):
            f = flags[t, i]
            if base == 0 and f != 255 and (f & 32) != 0:
                base = 1 if dirs[t, i] >= 0 else -1
        if base == 0:
            base = 1
        base_out[t] = base
        flip = False
        for i in range(13):
            f = flags[t, i]
            avail = f != 255
            o = -base if flip else base
            orient[t, i] = o
            refStart = False
            refEnd = False
            stair = False
            area = False
            if avail:
                rl = (f & 1) != 0
                rh = (f & 2) != 0
                area = (f & 4) != 0
                su = (f & 8) != 0
                sd = (f & 16) != 0
                refStart = rl if o > 0 else rh
                refEnd = rh if o > 0 else rl
                stair = sd if o > 0 else su
            if not avail:
                shape[t, i] = 0
            elif stair:
                shape[t, i] = 1
            elif refEnd:
                shape[t, i] = 2
            elif refStart and area:
                shape[t, i] = 3
            elif area:
                shape[t, i] = 4
            else:
                shape[t, i] = 5
            pp = pos[t, i - 1] if i > 0 else -1
            ih = False
            p = 0  # UNAVAILABLE
            if avail:
                if stair:
                    p = 2
                elif refEnd:
                    p = 3
                elif refStart and area:
                    p = 5 if (pp == 3 or pp == 4 or pp == 7) else 4
                elif area:
                    p = 6 if (pp == 5 or pp == 6) else (2 if pp == 2 else 7)
                else:
                    ih = True
                    p = 1 if (i == 0 or pp == 0 or pp == 1) else pp
            pos[t, i] = p
            inh[t, i] = ih
            # D1. Only a rung's OWN shape hands a new side down.
            if p == 3 and not ih:
                flip = not flip
            if p == 4 and not ih:
                flip = False
        # D3. READ HERE
        ra = -1
        for i in range(chartIdx, 13):
            if ra == -1:
                pi = pos[t, i]
                if (pi == 4 or pi == 5) and not inh[t, i]:
                    ra = i
        readAt[t] = ra
        # SIGNAL RUNGS
        for i in range(13):
            pv = prev[i]
            isChart = i == chartIdx
            if everyRung:
                active = True
            elif pickIdx == -1:
                active = isChart
            else:
                active = i == pickIdx
            isRead = lblRead and i == ra and not active
            if isRead and ra != prevReadAt:
                pv = -1
            if active or isRead:
                mark[t, i] = 1 if isChart else (2 if isRead else 0)
                p = pos[t, i]
                ih = inh[t, i]
                up = orient[t, i] > 0
                ws = pv == 5 or pv == 6
                c = 0
                if p != pv and not ih:
                    if p == 3:
                        c = 3          # EV_DIV
                    elif p == 4:
                        c = 1          # EV_LEG1
                    elif p == 5:
                        c = 2          # EV_LEG2
                    elif ws and (p == 2 or p == 7):
                        c = 4          # EV_END2
                    elif p == 7:
                        c = 5          # EV_LOOK
                    elif p == 2:
                        c = 6          # EV_STAIR
                code[t, i] = c
                upf[t, i] = up
                was2[t, i] = ws
                if c != 0:
                    ui = 1 if up else 0
                    d = d_tab[c, ui]
                    a = act_tab[c, ui]
                    if d != 0 and a != 0:
                        if a == 3:
                            kind[t, i] = 4 if d > 0 else 3     # exitS / exitL
                        else:
                            dd = -d if a == 2 else d
                            if reverseAll:
                                dd = -dd
                            kind[t, i] = 1 if dd > 0 else 2
            prev[i] = pos[t, i]
        prevReadAt = ra
    return pos, shape, orient, inh, readAt, base_out, code, kind, upf, was2, mark


def _what(c, up, ws):
    side = "LONGS" if up else "SHORTS"
    if c == EV_DIV:
        zone = "DIV SHORT ZONE" if up else "DIV LONG ZONE"
        leg = "END 2nd LEG" if ws else "END 1st LEG"
        return zone + " " + leg
    if c == EV_LEG1:
        return "1st LEG " + side
    if c == EV_LEG2:
        return "2nd LEG " + side
    if c == EV_END2:
        return "END 2nd LEG " + side
    if c == EV_LOOK:
        return "look for " + side
    if c == EV_STAIR:
        return "staircase"
    return ""


# src string table [rung, mark, code, up, wasSecond]
_SRC = np.empty((13, 3, 7, 2, 2), dtype=object)
for _i in range(13):
    for _m in range(3):
        for _c in range(7):
            for _u in range(2):
                for _w in range(2):
                    _SRC[_i, _m, _c, _u, _w] = TF_NAME[_i] + MARKS[_m] + " " + _what(_c, bool(_u), bool(_w))


def _params(params):
    p = dict(DEFAULTS)
    if params:
        for k, v in params.items():
            if k in p:
                p[k] = v
    if bool(p['agreeOn']):
        raise NotImplementedError("agreeOn = True is not supported (spec: only False)")
    if p['sigRung'] not in SIG_RUNG_OPTS:
        raise ValueError(f"sigRung {p['sigRung']!r} not one of {SIG_RUNG_OPTS}")
    for k in ('actL1', 'actL2', 'actS1', 'actS2', 'actDL', 'actDS', 'actEnd', 'actInf'):
        if p[k] not in ACTS:
            raise ValueError(f"{k} {p[k]!r} not one of {ACTS}")
    for k in ('rsiLen', 'fastLen', 'bbLen', 'areaLen', 'trendLen', 'flatWin'):
        if int(p[k]) < 1:
            raise ValueError(f"{k} must be >= 1")
    return p


def _windows(p):
    if bool(p['scaleWin']):
        return [20, 17, 28, 24, 16, 12, 12, 12, 20, 12, 12, 12, 20]
    return [int(p['flatWin'])] * 13


def _tables(p):
    A = {k: ACTS.index(p[k]) for k in ('actL1', 'actL2', 'actS1', 'actS2', 'actDL', 'actDS', 'actEnd', 'actInf')}
    act = np.zeros((7, 2), np.int8)   # [code, up]
    dtab = np.zeros((7, 2), np.int8)
    act[EV_LEG1] = (A['actS1'], A['actL1'])
    act[EV_LEG2] = (A['actS2'], A['actL2'])
    act[EV_DIV] = (A['actDL'], A['actDS'])
    act[EV_END2] = (A['actEnd'], A['actEnd'])
    act[EV_LOOK] = (A['actInf'], A['actInf'])
    act[EV_STAIR] = (A['actInf'], A['actInf'])
    dtab[EV_LEG1] = (-1, 1)
    dtab[EV_LEG2] = (-1, 1)
    dtab[EV_DIV] = (1, -1)
    dtab[EV_END2] = (1, -1)
    dtab[EV_LOOK] = (-1, 1)
    dtab[EV_STAIR] = (1, -1)
    return act, dtab


def ladder_inputs(pair, chart_tf, chart_tc, p):
    """flags / dirs [n, 13] of every rung mapped onto the chart bars chart_tc."""
    n = chart_tc.shape[0]
    flags = np.full((n, 13), F_NA, np.uint8)
    dirs = np.zeros((n, 13), np.int8)
    hs = _windows(p)
    for i in range(N_DATA_RUNG):
        tc, fl, d = rung_state(pair, RUNG_TF[i], hs[i], p)
        idx = map_to_chart(tc, chart_tc)
        ok = idx >= 0
        ii = np.where(ok, idx, 0)
        flags[:, i] = np.where(ok, fl[ii], F_NA)
        dirs[:, i] = np.where(ok, d[ii], 0)
    return flags, dirs


def xpw_signals(pair: str, chart_tf: str, start: int, end: int, params: dict | None = None,
                warmup_bars: int = WARMUP_BARS) -> pd.DataFrame:
    p = _params(params)
    chart_tf = str(chart_tf)
    tc_all = _t_close(pair, chart_tf)
    r0 = int(np.searchsorted(tc_all, start, side='left'))
    r1 = max(int(np.searchsorted(tc_all, end, side='right')), r0)     # empty window -> 0 rows
    w0 = max(r0 - int(warmup_bars), 0)
    chart_tc = tc_all[w0:r1]

    chartIdx = chart_index(chart_tf)
    sig = p['sigRung']
    everyRung = sig == "every rung (1 Sec to 1 Month)"
    pickIdx = TF_NAME.index(sig) if sig in TF_NAME else -1
    act_tab, d_tab = _tables(p)

    flags, dirs = ladder_inputs(pair, chart_tf, chart_tc, p)
    prev0 = np.full(13, -1, np.int8)
    (pos, shape, orient, inh, readAt, base, code, kind, upf, was2, mark) = _ladder(
        flags, dirs, chartIdx, everyRung, pickIdx, bool(p['lblRead']), bool(p['reverseAll']),
        act_tab, d_tab, prev0, -1)

    k = r0 - w0                       # drop the warm-up rows
    pos, shape, orient, inh = pos[k:], shape[k:], orient[k:], inh[k:]
    readAt, base, code, kind, upf, was2, mark = readAt[k:], base[k:], code[k:], kind[k:], upf[k:], was2[k:], mark[k:]
    n = r1 - r0

    nLongRaw = (kind == K_LONG).sum(axis=1).astype(np.int64)
    nShortRaw = (kind == K_SHORT).sum(axis=1).astype(np.int64)
    both = (nLongRaw > 0) & (nShortRaw > 0)
    nLong = np.where(both, 0, nLongRaw)
    nShort = np.where(both, 0, nShortRaw)
    exitL = (kind == K_EXITL).any(axis=1)
    exitS = (kind == K_EXITS).any(axis=1)

    longSrc = [[] for _ in range(n)]
    shortSrc = [[] for _ in range(n)]
    events = [[] for _ in range(n)]
    exitLSrc = np.full(n, "", dtype=object)
    exitSSrc = np.full(n, "", dtype=object)
    rr, ii = np.nonzero(code)                  # row-major: bar, then rung 0..12
    for r, i in zip(rr.tolist(), ii.tolist()):
        s = _SRC[i, mark[r, i], code[r, i], int(upf[r, i]), int(was2[r, i])]
        events[r].append(s)
        kd = kind[r, i]
        if kd == K_LONG:
            longSrc[r].append(s)
        elif kd == K_SHORT:
            shortSrc[r].append(s)
        elif kd == K_EXITL:
            exitLSrc[r] = s                    # last one wins, as exitLSrc := src
        elif kd == K_EXITS:
            exitSSrc[r] = s

    cols = {
        't_close': tc_all[r0:r1],
        'chartIdx': np.full(n, chartIdx, np.int64),
        'readAt': readAt.astype(np.int64),
        'baseDir': base.astype(np.int64),
        'nLongRaw': nLongRaw, 'nShortRaw': nShortRaw,
        'nLong': nLong.astype(np.int64), 'nShort': nShort.astype(np.int64),
        'longSrc': longSrc, 'shortSrc': shortSrc,
        'exitL': exitL, 'exitS': exitS,
        'exitLSrc': exitLSrc, 'exitSSrc': exitSSrc,
        'events': events,
    }
    for i in range(13):
        cols[f'pos_{i}'] = POS_NAMES[pos[:, i]]
    for i in range(13):
        cols[f'orient_{i}'] = orient[:, i].astype(np.int64)
    for i in range(13):
        cols[f'inh_{i}'] = inh[:, i].copy()
    for i in range(13):
        cols[f'shape_{i}'] = SHAPE_NAMES[shape[:, i]]
    return pd.DataFrame(cols, index=pd.RangeIndex(r0, r1))


def clear_cache():
    _TC_CACHE.clear()
    _RUNG_CACHE.clear()
