"""HRD Full Divergence Strategy v1.03 + FlashGold Direction Filter: CANONICAL Python replica.

A copy of implementation A (hrd_a.py), chosen after reconciliation against the independent
implementation B (hrd_b.py): after fixing B the two agree on 100% of trades, every column,
and on every summary field (BTC / XAU, charts 1, 5, 60, 240, full windows; default, fgfOn False,
blkClose False, cost 'ours', reverse True, pivotTies 'left_strict'). See reconcile_hrd.md.

Ground truth: /home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine
(with "Enable filter" off it is /home/user/master/HRD_Full_Divergence_Strategy_v1_03.pine).
Spec: SPEC_AH.md, SWEEP_AH_SPEC.md (trailing exit, mag path, stress cost, fair halves). Interpretations:
hrd_a_notes.md; the pre-trail version is sweep_ah_backup/hrd.py.pre_trail.

    run(pair, chart_tf, params=None) -> (trades: DataFrame, summary: dict)
    prepare(pair, chart_tf, params=None) -> P          signals, permissions, window arrays (once)
    simulate(P, X=None, full=False) -> R                strategy + broker with exit params X
    summary_fast(P, R) -> dict                           run()'s summary without the DataFrame
    trades_frame(P, R) -> DataFrame                      run()'s trade list
run() = prepare + simulate(full=True) + trades_frame + summarize. The sweep (sweep_hrd.py) calls
prepare once per (filter, labels) and simulate + summary_fast per exit setting.

History (TradingView Strategy Tester): the script runs once per chart bar at its close; market
orders fill at the next bar's open in the order they were placed; the exit order (SL / TP
bracket, optional trailing stop) is checked along the intrabar path. The direction filter
permissions come from fgf.py (fgf_permissions).

Trailing take profit (SWEEP_AH_SPEC.md, Pine hrdTrailOn / hrdTrailAct / hrdTrailOff, off by default):
params trailOn, trailAct, trailOff (% of the signal close; aliases hrdTrail*). On the signal bar
trail_points = max(close x act / 100 / mintick, 0), trail_offset = max(close x off / 100 /
mintick, 1) (fractional ticks, not rounded), sent with the entry's own strategy.exit next to the
SL / TP (InpTpPct 0 = no target). Activation price = entry FILL price +/- trail_points x mintick;
once reached the stop = best price since activation -/+ trail_offset x mintick, moving only in the
trade's favour; trail_points 0 = armed at the fill with best = the fill price. Active from the
entry fill on, along the rest of the fill bar's path. Along the path (_walk): the gap test at the
open (open at / beyond the stop -> fill at the open; at / beyond the limit -> limit at the open),
then the open can arm / ratchet the trail; rising (favourable) segments can reach the limit and
arm / ratchet the trail; falling (adverse) segments can reach the higher of the SL and the trailing
stop (fixed along the segment), filled at that level. Trailing stop >= SL -> exit kind 'trail'.
No touch tolerance (as the original bracket). HRD sends the exit only with its entry (an entry
needs position_size <= 0 for a long, >= 0 for a short), so an open trade's exit is never re-sent.
With the trail off the kernel equals the original one exactly (sweep_ah_tests.py R1, R1b).

path 'mag' (Bar Magnifier): every exit order is evaluated along the 1-minute sub-bars of the
chart bar (rows of data/<PAIR>_1.parquet with t_open in [t_open, t_close) of the chart bar), in
time order, each with its own rule-4 path, the trailing state carrying over; the gap test runs at
every sub-bar open. Entries, close / close_all and reversals still fill at the chart bar open and
the script still runs at the chart bar close. Chart "1": mag == tv.

cost 'tv' (none), 'ours' (XAU $0.15 / unit per fill; BTC 0.02% of the fill value + $0.10 / unit per
fill), 'stress' (XAU $0.25 + 0.01 / unit per fill; BTC 0.035% + $0.10 + 0.01 / unit per fill): the
tick is charged as a cost, fill prices stay unchanged. Costs reduce equity, so they change sizing.

Inverted direction (Pine UPDATE 1, input hrdInv "Inverted direction: opposite side at the same
entries", off by default): param hrdInv (alias inv), a broker param (simulate() may set it). On, the
script keeps deciding in the NORMAL frame, as if it held the mirror of its real position (Pine
hrdPos = -strategy.position_size): hrdWantLong / hrdWantShort read hrdPos and are gated by fgfBuyOk /
fgfSellOk as before; "Trade Direction" applies to the order really placed (hrdDirOkL =
shortDirectionAllowed, hrdDirOkS = longDirectionAllowed); a blocked LONG signal closes an open real
long (id hrdIdS = "Long"), a blocked SHORT an open real short; the LONG execution block sends a SELL
with stop = close x (1 + SL %) and limit = close x (1 - TP %), the SHORT block a BUY with stop =
close x (1 - SL %) and limit = close x (1 + TP %), same quantity (same stop distance, the account's
equity) and the same trail ticks; the two blocks keep their order (LONG block first). The time exit
and the hybrid exit read the real position and are unchanged. Trades report the REAL side (dir);
raw_long / raw_short / blocked_long / blocked_short and want_l / want_s / blk_l / blk_s stay in the
normal frame (the signal's side, the Pine's FGD values). Off = the previous kernel exactly
(inv_tests_hrd.py R1; the pre-change module is pre_inv_backup/hrd.py). See inv_hrd_notes.md.

Added summary fields: h1r_pct / h2r_pct (fair halves: for the trades ENTERED in each half, entry
t_open <= mid / > mid, mid = start + (end - start) // 2, prod(1 + pnl / eq_before) - 1 in %; 0 when
the half has no trade), h1_trades / h2_trades, avg_bars_held, exits['trail']. Trades get eq_before
(cash just before the entry fill = equity then, the position being flat).

Pipeline
  1. signals over ALL bars of the chart file (warm-up from the start of data):
     D / W / M horizons (request.security lookahead_on, [1]), breakouts, RSI /
     MACD / stoch oscillator, pivots and the divergence state machine (numba).
  2. broker + strategy logic over the window bars only (numba): time exit,
     filter gate, blocked-opposite close, entries with SL / TP / trail, hybrid
     decay-slip exit, fills, intrabar exit order, equity, FGD counts.

Run as a script for a quick summary:  python3 -I hrd.py
"""
import os
import sys
import time as _time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numba import njit

W = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(W, 'data')
MINTICK = 0.01
POINTVALUE = 1.0
INITIAL_CAPITAL = 1_000_000.0
WINDOWS = {'BTC': (1731801600, 1794873600), 'XAU': (1483315200, 1529366400)}

KINDS = ['', 'sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end', 'trail']
K_SL, K_TP, K_REV, K_BLK, K_TIME, K_HYB, K_END, K_TRAIL = 1, 2, 3, 4, 5, 6, 7, 8
NEG = -1.0e300

# per fill, per unit: (fixed $, fraction of the fill value)
COSTS = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},                  # HRD's strategy() sets no commission
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},           # $0.30 / oz RT; 0.02% + $0.20 / coin RT
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},   # $0.50 / oz RT; 0.035% + $0.20 / coin RT; + 1 tick per fill
}

DEFAULTS = dict(
    # replica controls
    fgfOn=True, blkClose=True, cost='tv', reverse=False, pivotTies='strict',
    smaNa='skip',            # ta.sma on na stoch values: 'skip' (Pine docs) or 'propagate'
    start=None, end=None,    # window override (t_close, epoch s)
    path='tv',               # 'tv': one rule-4 path per chart bar; 'mag': Bar Magnifier, 1-minute sub-bars
    # Divergence Engine
    pivotStrength=5, maxDivLookback=60,
    showBullReg=True, showBearReg=True, showBullHid=True, showBearHid=True,
    # Strategy Rules & Risk
    InpTradeDirection='Both', InpRiskPct=1.0, InpFixedQty=0.01, InpSlPct=2.0, InpTpPct=4.0,
    InpExitCandles=5,
    # Hybrid decay-slip exit
    useHybridExit=True, hybridSensitivity=1.0, minDecayUpdates=10, trailStepMult=1.0,
    minActivationPts=40,
    # Trailing take profit (hrdTrailOn / hrdTrailAct / hrdTrailOff, % of the signal close)
    trailOn=False, trailAct=1.0, trailOff=0.5,
    # Inverted direction (Pine UPDATE 1, hrdInv): every entry on the opposite side, after the gate
    hrdInv=False,
)
_ALIASES = {'InpReverseTrading': 'reverse', 'hrdBlkClose': 'blkClose',
            'hrdTrailOn': 'trailOn', 'hrdTrailAct': 'trailAct', 'hrdTrailOff': 'trailOff',
            'inv': 'hrdInv'}
# params that prepare() fixes (signals, permissions, window); simulate() may not change them
_PREP_KEYS = {'fgfOn', 'reverse', 'pivotTies', 'smaNa', 'start', 'end', 'pivotStrength', 'maxDivLookback',
              'showBullReg', 'showBearReg', 'showBullHid', 'showBearHid'}
# display-only inputs: accepted and ignored
_DISPLAY = {'dailyColor', 'weeklyColor', 'monthlyColor', 'showDivLines', 'showLabels', 'alertsOn',
            'scoreThreshold', 'scoreBullReg', 'scoreBearReg', 'scoreBullHid', 'scoreBearHid', 'showBreaks'}


def _check(P):
    if P['cost'] not in COSTS:
        raise ValueError("cost must be 'tv', 'ours' or 'stress'")
    if P['path'] not in ('tv', 'mag'):
        raise ValueError("path must be 'tv' or 'mag'")
    if P['pivotTies'] not in ('strict', 'left_strict'):
        raise ValueError("pivotTies must be 'strict' or 'left_strict'")
    if P['smaNa'] not in ('skip', 'propagate'):
        raise ValueError("smaNa must be 'skip' or 'propagate'")
    if P['InpTradeDirection'] not in ('Both', 'Buy Only', 'Sell Only'):
        raise ValueError('InpTradeDirection must be Both / Buy Only / Sell Only')
    if int(P['pivotStrength']) < 1 or int(P['maxDivLookback']) < 10 or int(P['InpExitCandles']) < 1:
        raise ValueError('below a Pine minval')
    if bool(P['trailOn']) and not (float(P['trailAct']) >= 0.0 and float(P['trailOff']) >= 0.0):
        raise ValueError('trailAct / trailOff below the Pine minval 0')


def _params(params):
    P = dict(DEFAULTS)
    fgfp = {}
    for k, v in (params or {}).items():
        k = _ALIASES.get(k, k)
        if k in DEFAULTS:
            P[k] = v
        elif k.startswith('fgf') or k.startswith('fgs') or k == 'FGF_FORCE_OVERLAY':
            fgfp[k] = v
        elif k in _DISPLAY:
            pass
        else:
            raise ValueError(f'unknown param {k!r}')
    _check(P)
    fgfp['fgfOn'] = bool(P['fgfOn'])
    return P, fgfp


# ----------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------
_CACHE = {}


def load_bars(pair, tf):
    key = (pair, str(tf))
    if key not in _CACHE:
        t = pq.read_table(os.path.join(DATA, f'{pair}_{tf}.parquet'),
                          columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
        d = {}
        for c in t.column_names:
            a = t.column(c).to_numpy()
            d[c] = np.ascontiguousarray(a, dtype=np.float64 if c in ('open', 'high', 'low', 'close') else np.int64)
        _CACHE[key] = d
    return _CACHE[key]


def _map_on_prev(src_topen, src_tclose, dst_topen):
    """request.security(..., expr[1], lookahead_on): the source bar that contains
    the chart bar (t_open <= chart t_open < t_close), then its previous bar.
    Returns (index or -1, number of chart bars not contained in their source bar)."""
    k = np.searchsorted(src_topen, dst_topen, side='right') - 1
    ok = k >= 0
    bad = int(np.sum(ok & (dst_topen >= src_tclose[np.maximum(k, 0)])))
    return np.where(ok, k - 1, -1), bad


def _take(a, idx):
    out = a[np.maximum(idx, 0)].astype(np.float64)
    out[idx < 0] = np.nan
    return out


# ----------------------------------------------------------------------------
# indicators (numba)
# ----------------------------------------------------------------------------
@njit(cache=True)
def _rsi(x, n):
    """ta.rsi: Wilder RMA of the up / down changes, seeded with the SMA of the
    first n changes; down == 0 -> 100, up == 0 -> 0."""
    N = x.shape[0]
    out = np.full(N, np.nan)
    alpha = 1.0 / n
    su = 0.0
    sd = 0.0
    up = np.nan
    dn = np.nan
    cnt = 0
    for i in range(1, N):
        ch = x[i] - x[i - 1]
        u = ch if ch > 0.0 else 0.0
        d = -ch if ch < 0.0 else 0.0
        if cnt < n:
            su += u
            sd += d
            cnt += 1
            if cnt < n:
                continue
            up = su / n
            dn = sd / n
        else:
            up = alpha * u + (1.0 - alpha) * up
            dn = alpha * d + (1.0 - alpha) * dn
        if dn == 0.0:
            out[i] = 100.0
        elif up == 0.0:
            out[i] = 0.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + up / dn)
    return out


@njit(cache=True)
def _ema(x, n):
    """ta.ema seeded with the first value."""
    N = x.shape[0]
    out = np.empty(N)
    alpha = 2.0 / (n + 1)
    v = x[0]
    out[0] = v
    for i in range(1, N):
        v = alpha * x[i] + (1.0 - alpha) * v
        out[i] = v
    return out


@njit(cache=True)
def _stoch_sma(close, high, low, n, m, skip_na):
    """ta.sma(ta.stoch(close, high, low, n), m). stoch = na when the n-bar range
    is 0 (float division by zero). skip_na: ta.sma ignores na values and averages
    the last m non-na values; else any na in the m bars gives na."""
    N = close.shape[0]
    st = np.full(N, np.nan)
    for i in range(n - 1, N):
        hh = high[i]
        ll = low[i]
        for j in range(i - n + 1, i):
            if high[j] > hh:
                hh = high[j]
            if low[j] < ll:
                ll = low[j]
        rng = hh - ll
        if rng != 0.0:
            st[i] = 100.0 * (close[i] - ll) / rng
    out = np.full(N, np.nan)
    if skip_na:
        buf = np.zeros(m)
        cnt = 0
        for i in range(N):
            if not np.isnan(st[i]):
                buf[cnt % m] = st[i]
                cnt += 1
            if cnt >= m:
                s = 0.0
                for j in range(m):
                    s += buf[j]
                out[i] = s / m
    else:
        for i in range(m - 1, N):
            s = 0.0
            for j in range(i - m + 1, i + 1):
                s += st[j]
            out[i] = s / m
    return out


@njit(cache=True)
def _pivots(high, low, L, R, left_strict):
    """ta.pivothigh(high, L, R) / ta.pivotlow(low, L, R) on bar i: the value of
    bar i-R when it is a pivot over bars i-L-R .. i, else na. strict: strictly
    above (below) every other bar; left_strict: strictly against the left bars,
    >= (<=) against the right bars."""
    N = high.shape[0]
    ph = np.full(N, np.nan)
    pl = np.full(N, np.nan)
    for i in range(L + R, N):
        c = i - R
        vh = high[c]
        vl = low[c]
        okh = True
        okl = True
        for j in range(c - L, c):
            if not (vh > high[j]):
                okh = False
            if not (vl < low[j]):
                okl = False
        for j in range(c + 1, i + 1):
            if left_strict:
                if not (vh >= high[j]):
                    okh = False
                if not (vl <= low[j]):
                    okl = False
            else:
                if not (vh > high[j]):
                    okh = False
                if not (vl < low[j]):
                    okl = False
        if okh:
            ph[i] = vh
        if okl:
            pl[i] = vl
    return ph, pl


@njit(cache=True)
def _divergence(ph, pl, osc, ps, max_lb, bull_reg, bull_hid, bear_reg, bear_hid):
    """The two divergence blocks. Returns per bar: bull type (0 none, 1 regular,
    2 hidden), bear type, and the previous pivot bar used (for traces)."""
    N = ph.shape[0]
    bull = np.zeros(N, np.int8)
    bear = np.zeros(N, np.int8)
    prev_l_bar_used = np.full(N, -1, np.int64)
    prev_h_bar_used = np.full(N, -1, np.int64)
    pl_price = np.nan
    pl_osc = np.nan
    pl_bar = -1
    ph_price = np.nan
    ph_osc = np.nan
    ph_bar = -1
    for i in range(N):
        if not np.isnan(pl[i]):
            cb = i - ps
            cp = pl[i]
            co = osc[i - ps] if i - ps >= 0 else np.nan
            if pl_bar >= 0 and (cb - pl_bar) <= max_lb:
                if bull_reg and cp < pl_price and co > pl_osc:
                    bull[i] = 1
                    prev_l_bar_used[i] = pl_bar
                elif bull_hid and cp > pl_price and co < pl_osc:
                    bull[i] = 2
                    prev_l_bar_used[i] = pl_bar
            pl_price = cp
            pl_osc = co
            pl_bar = cb
        if not np.isnan(ph[i]):
            cb = i - ps
            cp = ph[i]
            co = osc[i - ps] if i - ps >= 0 else np.nan
            if ph_bar >= 0 and (cb - ph_bar) <= max_lb:
                if bear_reg and cp > ph_price and co < ph_osc:
                    bear[i] = 1
                    prev_h_bar_used[i] = ph_bar
                elif bear_hid and cp < ph_price and co > ph_osc:
                    bear[i] = 2
                    prev_h_bar_used[i] = ph_bar
            ph_price = cp
            ph_osc = co
            ph_bar = cb
    return bull, bear, prev_l_bar_used, prev_h_bar_used


_SIG = {}


def signals(pair, chart_tf, P=None):
    """All bars of the chart file: horizons, breakouts, oscillator, pivots,
    divergences, longCondition / shortCondition (before Reverse / Direction)."""
    if P is None:
        P, _ = _params(None)
    key = (pair, str(chart_tf), int(P['pivotStrength']), int(P['maxDivLookback']), P['pivotTies'], P['smaNa'],
           bool(P['showBullReg']), bool(P['showBullHid']), bool(P['showBearReg']), bool(P['showBearHid']))
    if key in _SIG:
        return _SIG[key]
    b = load_bars(pair, chart_tf)
    o, h, l, c = b['open'], b['high'], b['low'], b['close']
    to = b['t_open']
    N = c.shape[0]
    S = {'n': N}
    bad = {}
    for tf, hk, lk in (('D', 'pdh', 'pdl'), ('W', 'pwh', 'pwl'), ('M', 'pmh', 'pml')):
        hb = load_bars(pair, tf)
        k, nb = _map_on_prev(hb['t_open'], hb['t_close'], to)
        S[hk] = _take(hb['high'], k)
        S[lk] = _take(hb['low'], k)
        bad[tf] = nb
    S['not_contained'] = bad
    # math.max / math.min with an na argument give na
    with np.errstate(invalid='ignore'):
        maxl = np.maximum(S['pdh'], np.maximum(S['pwh'], S['pmh']))
        minl = np.minimum(S['pdl'], np.minimum(S['pwl'], S['pml']))
        c1 = np.concatenate([[np.nan], c[:-1]])
        bull_break = (c > maxl) & (c1 <= maxl)
        bear_break = (c < minl) & (c1 >= minl)
    S['maxLevel'] = maxl
    S['minLevel'] = minl
    S['bullBreak'] = bull_break
    S['bearBreak'] = bear_break
    rsi = _rsi(c, 14)
    macd = _ema(c, 12) - _ema(c, 26)
    stoch = _stoch_sma(c, h, l, 5, 3, P['smaNa'] == 'skip')
    osc = rsi * 0.4 + macd * 0.3 + stoch * 0.3
    S['rsi'], S['macd'], S['stoch'], S['osc'] = rsi, macd, stoch, osc
    ps = int(P['pivotStrength'])
    ph, pl = _pivots(h, l, ps, ps, P['pivotTies'] == 'left_strict')
    S['ph'], S['pl'] = ph, pl
    bull, bear, pbl, pbh = _divergence(ph, pl, osc, ps, int(P['maxDivLookback']),
                                       bool(P['showBullReg']), bool(P['showBullHid']),
                                       bool(P['showBearReg']), bool(P['showBearHid']))
    S['bullDiv'], S['bearDiv'], S['prevPlBarUsed'], S['prevPhBarUsed'] = bull, bear, pbl, pbh
    S['longCondition'] = bull_break | (bull > 0)
    S['shortCondition'] = bear_break | (bear > 0)
    _SIG[key] = S
    return S


# ----------------------------------------------------------------------------
# broker + strategy logic (numba)
# ----------------------------------------------------------------------------
@njit(cache=True)
def _cost(px, qty, c_fix, c_pct):
    return qty * (c_fix + c_pct * px)


@njit(cache=True)
def _walk(v0, v1, v2, v3, act, best, A, off, sl, tp, has_tr, has_sl, has_tp):
    """One intrabar path of the open trade's exit order (stop loss, limit, trailing stop) in
    'long space' (a short's prices are negated: its stops are below, its limit above).
    v0..v3: open, first extreme, second extreme, close (rule 4). act / best: trailing state
    (armed, best price since arming); A: activation price; off: trail offset (price).
    Returns (kind, fill price in long space, act, best); kind 0 = no exit.
      - gap at the open: open at / beyond the stop (the higher of the stop loss and the
        trailing stop) -> stop at the open; open at / beyond the limit -> limit at the open;
      - the open itself can arm / ratchet the trail;
      - rising segment: reaches the limit -> limit at its price; else arms / ratchets the trail;
      - falling segment: the stop is fixed along it; reached -> fill at the stop.
    Trailing stop >= stop loss -> kind 'trail', else 'sl'. No tolerance (as the bracket)."""
    sv = sl if has_sl else NEG
    ts = (best - off) if (has_tr and act) else NEG
    lvl = ts if ts > sv else sv
    if v0 <= lvl:
        return (K_TRAIL if ts >= sv else K_SL), v0, act, best
    if has_tp and v0 >= tp:
        return K_TP, v0, act, best
    if has_tr:
        if act:
            if v0 > best:
                best = v0
        elif v0 >= A:
            act = True
            best = v0
    a = v0
    for s in range(3):
        if s == 0:
            b = v1
        elif s == 1:
            b = v2
        else:
            b = v3
        if b > a:
            if has_tp and b >= tp:
                return K_TP, (tp if tp > a else a), act, best
            if has_tr:
                if act:
                    if b > best:
                        best = b
                elif b >= A:
                    act = True
                    best = b
        elif b < a:
            ts = (best - off) if (has_tr and act) else NEG
            lvl = ts if ts > sv else sv
            if b <= lvl:
                return (K_TRAIL if ts >= sv else K_SL), (lvl if lvl < a else a), act, best
        a = b
    return 0, 0.0, act, best


@njit(cache=True)
def _simulate(o, h, l, c, long_sig, short_sig, buy_ok, sell_ok,
              long_allowed, short_allowed, blk_close,
              sl_pct, tp_pct, risk_pct, fixed_qty, exit_candles,
              use_hybrid, hyb_sens, min_updates, trail_mult, min_act_pts,
              trail_on, trail_act, trail_off,
              mag, ptr, so, sh, sl_, sc,
              mintick, pointvalue, init_cap, c_fix, c_pct,
              cap, full, mid_j, inv):
    """The strategy + broker over the window bars. cap: trade capacity (>= the number of entry
    fills: 2 x the bars with a long or short signal suffices). full: also return the per-bar
    state arrays (else they have length 1). mid_j: the bar of the half split (half1_pct).
    mag: exits walk the 1-minute sub-bars [ptr[k], ptr[k+1]) of so / sh / sl_ / sc.
    inv: Pine hrdInv (UPDATE 1). long_allowed / short_allowed are the Pine's longDirectionAllowed /
    shortDirectionAllowed (the orders really placed); every trade array holds the REAL side."""
    n = o.shape[0]
    maxt = cap
    t_dir = np.zeros(maxt, np.int64)
    t_ek = np.zeros(maxt, np.int64)        # entry fill bar (window-relative)
    t_sk = np.zeros(maxt, np.int64)        # bar where the entry order was placed
    t_epx = np.zeros(maxt)
    t_qty = np.zeros(maxt)
    t_xk = np.zeros(maxt, np.int64)        # exit bar
    t_xsk = np.zeros(maxt, np.int64)       # bar where the exit order was placed (-1: exit order / end)
    t_xpx = np.zeros(maxt)
    t_kind = np.zeros(maxt, np.int64)
    t_gross = np.zeros(maxt)
    t_cost = np.zeros(maxt)
    t_sl = np.zeros(maxt)
    t_tp = np.zeros(maxt)
    t_eqb = np.zeros(maxt)                 # equity (= cash, flat) just before the entry fill
    nt = 0
    n_fill = 0

    nb_ = n if full else 1
    eq_close = np.zeros(nb_)
    pos_close = np.zeros(nb_)
    ebi_arr = np.full(nb_, -1, np.int64)
    peak_arr = np.zeros(nb_)
    cnt_arr = np.zeros(nb_, np.int64)
    want_l = np.zeros(nb_, np.bool_)
    want_s = np.zeros(nb_, np.bool_)
    blk_l = np.zeros(nb_, np.bool_)
    blk_s = np.zeros(nb_, np.bool_)
    n_wl = 0
    n_ws = 0
    n_bl = 0
    n_bs = 0
    n_pos = 0
    dd_pk = init_cap
    dd_rel = 0.0
    dd_abs = 0.0
    eq_mid = init_cap
    eq_last = init_cap

    # pending orders (placed on bar k, filled at the open of bar k+1)
    # type: 1 close_all, 2 close(entry id = dir), 3 entry(dir)
    MAXO = 8
    p_type = np.zeros(MAXO, np.int64)
    p_dir = np.zeros(MAXO, np.int64)
    p_qty = np.zeros(MAXO)
    p_sl = np.zeros(MAXO)
    p_tp = np.zeros(MAXO)
    p_trp = np.zeros(MAXO)        # trail_points (ticks), NaN = no trailing stop
    p_tro = np.zeros(MAXO)        # trail_offset (ticks)
    p_kind = np.zeros(MAXO, np.int64)
    np_ = 0
    p_k = -1

    cash = init_cap          # initial capital + closed gross P/L - every cost paid
    pdir = 0
    pqty = 0.0
    ppx = 0.0
    pek = -1
    psk = -1
    pcost = 0.0
    psl = np.nan
    ptp = np.nan
    peqb = 0.0
    # trailing state of the open trade, long space
    ptr_on = False
    pA = 0.0
    poff = 0.0
    pact = False
    pbest = 0.0

    prev_pos = 0.0
    ebi = -1                  # entryBarIndex (-1 = na)
    g_peak = 0.0
    g_cnt = 0
    act_level = min_act_pts * mintick
    decay_thr = trail_mult * 8 * mintick * hyb_sens
    # UPDATE 1 (hrdInv): hrdDirOkL / hrdDirOkS = "Trade Direction" for the order really placed;
    # real_l / real_s = the real side of the order a normal-frame LONG / SHORT entry places
    # (ids hrdIdL / hrdIdS: "Long" is always a buy, "Short" always a sell)
    dir_ok_l = short_allowed if inv else long_allowed
    dir_ok_s = long_allowed if inv else short_allowed
    real_l = -1 if inv else 1
    real_s = 1 if inv else -1

    for k in range(n):
        ok_ = o[k]
        hk = h[k]
        lk = l[k]
        ck = c[k]
        # ---- 1. market orders from bar k-1, at this bar's open, in placement order
        for q in range(np_):
            ty = p_type[q]
            if ty == 1 or (ty == 2 and pdir == p_dir[q]):
                if pdir != 0:
                    xc = _cost(ok_, pqty, c_fix, c_pct)
                    cash += pdir * pqty * (ok_ - ppx) * pointvalue - xc
                    t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
                    t_xk[nt] = k; t_xsk[nt] = p_k; t_xpx[nt] = ok_; t_kind[nt] = p_kind[q]
                    t_gross[nt] = pdir * pqty * (ok_ - ppx) * pointvalue; t_cost[nt] = pcost + xc
                    t_sl[nt] = psl; t_tp[nt] = ptp; t_eqb[nt] = peqb
                    nt += 1
                    pdir = 0
                    pqty = 0.0
            elif ty == 3:
                d = p_dir[q]
                if pdir == d:
                    continue            # pyramiding = 0: same-direction entry ignored
                if pdir == -d:          # reversal: close the open trade in the same fill
                    xc = _cost(ok_, pqty, c_fix, c_pct)
                    cash += pdir * pqty * (ok_ - ppx) * pointvalue - xc
                    t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
                    t_xk[nt] = k; t_xsk[nt] = p_k; t_xpx[nt] = ok_; t_kind[nt] = K_REV
                    t_gross[nt] = pdir * pqty * (ok_ - ppx) * pointvalue; t_cost[nt] = pcost + xc
                    t_sl[nt] = psl; t_tp[nt] = ptp; t_eqb[nt] = peqb
                    nt += 1
                n_fill += 1
                if n_fill > maxt:
                    raise ValueError('trade capacity exceeded')
                peqb = cash
                ec = _cost(ok_, p_qty[q], c_fix, c_pct)
                cash -= ec
                pdir = d
                pqty = p_qty[q]
                ppx = ok_
                pek = k
                psk = p_k
                pcost = ec
                psl = p_sl[q]
                ptp = p_tp[q]
                # trailing stop of this entry's exit order: armed at the fill when trail_points is 0
                ptr_on = not np.isnan(p_trp[q])
                pbest = d * ok_
                if ptr_on:
                    pA = d * ok_ + p_trp[q] * mintick
                    poff = p_tro[q] * mintick
                    pact = pbest >= pA
                else:
                    pA = 0.0
                    poff = 0.0
                    pact = False
        np_ = 0
        # ---- 2. the open trade's exit order (SL / TP bracket, trailing stop) along the intrabar
        #         path (tv), or along the 1-minute sub-bars of this bar in time order (mag)
        if pdir != 0 and (not np.isnan(psl) or not np.isnan(ptp) or ptr_on):
            has_s = not np.isnan(psl)
            has_t = not np.isnan(ptp)
            sg = 1.0 if pdir > 0 else -1.0
            slv = sg * psl
            tpv = sg * ptp
            kind = 0
            xl = 0.0
            if mag:
                for s in range(ptr[k], ptr[k + 1]):
                    s_o = so[s]
                    s_h = sh[s]
                    s_l = sl_[s]
                    if (s_h - s_o) < (s_o - s_l):    # O->H->L->C
                        p1 = s_h
                        p2 = s_l
                    else:                            # O->L->H->C
                        p1 = s_l
                        p2 = s_h
                    kind, xl, pact, pbest = _walk(sg * s_o, sg * p1, sg * p2, sg * sc[s], pact, pbest,
                                                  pA, poff, slv, tpv, ptr_on, has_s, has_t)
                    if kind != 0:
                        break
            else:
                if (hk - ok_) < (ok_ - lk):          # O->H->L->C
                    p1 = hk
                    p2 = lk
                else:                                # O->L->H->C
                    p1 = lk
                    p2 = hk
                kind, xl, pact, pbest = _walk(sg * ok_, sg * p1, sg * p2, sg * ck, pact, pbest,
                                              pA, poff, slv, tpv, ptr_on, has_s, has_t)
            if kind != 0:
                xpx = sg * xl
                xc = _cost(xpx, pqty, c_fix, c_pct)
                cash += pdir * pqty * (xpx - ppx) * pointvalue - xc
                t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
                t_xk[nt] = k; t_xsk[nt] = -1; t_xpx[nt] = xpx; t_kind[nt] = kind
                t_gross[nt] = pdir * pqty * (xpx - ppx) * pointvalue; t_cost[nt] = pcost + xc
                t_sl[nt] = psl; t_tp[nt] = ptp; t_eqb[nt] = peqb
                nt += 1
                pdir = 0
                pqty = 0.0
        # ---- 3. the script at this bar's close
        pos = pdir * pqty
        equity = cash + (pdir * pqty * (ck - ppx) * pointvalue if pdir != 0 else 0.0)
        # 3. Time-based exit
        if pos != 0 and prev_pos == 0:
            ebi = k
        if pos != 0 and ebi >= 0 and (k - ebi >= exit_candles):
            p_type[np_] = 1; p_kind[np_] = K_TIME; np_ += 1
            ebi = -1
        # direction filter gate, in the normal frame: hrdPos = the real position, sign flipped
        # when inverted (UPDATE 1)
        hpos = -pos if inv else pos
        wl = long_sig[k] and dir_ok_l and hpos <= 0
        ws = short_sig[k] and dir_ok_s and hpos >= 0
        bl = wl and not buy_ok[k]
        bs = ws and not sell_ok[k]
        if wl:
            n_wl += 1
        if ws:
            n_ws += 1
        if bl:
            n_bl += 1
        if bs:
            n_bs += 1
        # strategy.close(hrdIdS) / strategy.close(hrdIdL): the trade really open, the one a
        # normal SHORT / LONG entry opened
        if blk_close and bl and hpos < 0:
            p_type[np_] = 2; p_dir[np_] = real_s; p_kind[np_] = K_BLK; np_ += 1
        if blk_close and bs and hpos > 0:
            p_type[np_] = 2; p_dir[np_] = real_l; p_kind[np_] = K_BLK; np_ += 1
        # 4. LONG / 5. SHORT execution (normal-frame blocks, in the Pine's order); side = the
        # order really placed: a buy has its stop below and its target above the signal close,
        # a sell the other way round (hrdInv: the normal bracket mirrored, same distances)
        for blk in (1, -1):
            go = (wl and buy_ok[k]) if blk == 1 else (ws and sell_ok[k])
            if not go:
                continue
            side = real_l if blk == 1 else real_s
            est = ck
            sl_dist = est * (sl_pct / 100.0) if sl_pct > 0.0 else 0.0
            if side == 1:
                slp = est * (1.0 - sl_pct / 100.0) if sl_pct > 0.0 else np.nan
                tpp = est * (1.0 + tp_pct / 100.0) if tp_pct > 0.0 else np.nan
            else:
                slp = est * (1.0 + sl_pct / 100.0) if sl_pct > 0.0 else np.nan
                tpp = est * (1.0 - tp_pct / 100.0) if tp_pct > 0.0 else np.nan
            # calculatePositionSize
            if sl_pct <= 0.0 or sl_dist <= 0.0:
                qty = fixed_qty
            else:
                risk = equity * (risk_pct / 100.0)
                if pointvalue > 0.0:
                    qty = risk / (sl_dist * pointvalue)
                else:
                    qty = fixed_qty
                if qty < fixed_qty:
                    qty = fixed_qty
            # trailing take profit: trail_points / trail_offset in ticks from the signal close
            if trail_on:
                trp = est * trail_act / 100.0 / mintick
                if trp < 0.0:
                    trp = 0.0
                tro = est * trail_off / 100.0 / mintick
                if tro < 1.0:
                    tro = 1.0
            else:
                trp = np.nan
                tro = np.nan
            p_type[np_] = 3; p_dir[np_] = side; p_qty[np_] = qty; p_sl[np_] = slp; p_tp[np_] = tpp
            p_trp[np_] = trp; p_tro[np_] = tro
            p_kind[np_] = K_REV; np_ += 1
        # HYBRID DECAY-SLIP EXIT ENGINE
        in_trade = pos != 0
        cur = 0.0
        if in_trade:
            cur = (ck - ppx) if pos > 0 else (ppx - ck)
        if not in_trade:
            g_peak = 0.0
            g_cnt = 0
        if use_hybrid and in_trade:
            if cur >= act_level or g_peak >= act_level:
                g_cnt += 1
                if cur > g_peak:
                    g_peak = cur
                drop = g_peak - cur
                decay = drop > decay_thr
                slip = cur < g_peak * 0.85
                if decay and slip and g_cnt >= min_updates and g_peak > 0:
                    p_type[np_] = 1; p_kind[np_] = K_HYB; np_ += 1
                    g_peak = 0.0
                    g_cnt = 0
        p_k = k
        prev_pos = pos
        if pos != 0:
            n_pos += 1
        if k < n - 1:
            # bar-close equity curve (the last bar's value is final below)
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
            eq_close[k] = equity
            pos_close[k] = pos
            ebi_arr[k] = ebi
            peak_arr[k] = g_peak
            cnt_arr[k] = g_cnt
            want_l[k] = wl
            want_s[k] = ws
            blk_l[k] = bl
            blk_s[k] = bs

    # orders placed on the last bar do not fill; an open trade is closed at the last close
    if pdir != 0:
        k = n - 1
        xc = _cost(c[k], pqty, c_fix, c_pct)
        cash += pdir * pqty * (c[k] - ppx) * pointvalue - xc
        t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
        t_xk[nt] = k; t_xsk[nt] = -1; t_xpx[nt] = c[k]; t_kind[nt] = K_END
        t_gross[nt] = pdir * pqty * (c[k] - ppx) * pointvalue; t_cost[nt] = pcost + xc
        t_sl[nt] = psl; t_tp[nt] = ptp; t_eqb[nt] = peqb
        nt += 1
        eq_last = cash
        if full:
            eq_close[k] = cash
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
    stats = np.array([eq_last, eq_mid, dd_rel, dd_abs, float(n_pos),
                      float(n_wl), float(n_ws), float(n_bl), float(n_bs), cash])
    return (t_dir[:nt], t_ek[:nt], t_sk[:nt], t_epx[:nt], t_qty[:nt], t_xk[:nt], t_xsk[:nt], t_xpx[:nt],
            t_kind[:nt], t_gross[:nt], t_cost[:nt], t_sl[:nt], t_tp[:nt], t_eqb[:nt],
            eq_close, pos_close, ebi_arr, peak_arr, cnt_arr, want_l, want_s, blk_l, blk_s, stats)


# ----------------------------------------------------------------------------
# public interface
# ----------------------------------------------------------------------------
def _window(pair, chart_tf, P):
    b = load_bars(pair, chart_tf)
    s0, e0 = WINDOWS[pair]
    start = int(P['start']) if P['start'] is not None else s0
    end = int(P['end']) if P['end'] is not None else e0
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


def sub_bars(pair, chart_tf, w0, w1, check=True):
    """1-minute sub-bars of the chart rows w0..w1-1 of data/<pair>_<chart_tf>.parquet: the rows of
    data/<pair>_1.parquet with t_open in [chart t_open, chart t_close). Returns (ptr, o, h, l, c):
    ptr int64 (n+1); the sub-bars of window bar k are [ptr[k], ptr[k+1]) of the contiguous
    arrays. With check, every chart bar has >= 1 sub-bar and its OHLC equals the sub-bars' first
    open / max high / min low / last close (build_bars.py built it from them)."""
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
    so = np.ascontiguousarray(m['open'][idx])
    sh = np.ascontiguousarray(m['high'][idx])
    sl = np.ascontiguousarray(m['low'][idx])
    sc = np.ascontiguousarray(m['close'][idx])
    if check and len(bo):
        st = ptr[:-1]
        ok = ((so[st] == b['open'][w0:w1]) & (sc[ptr[1:] - 1] == b['close'][w0:w1])
              & (np.maximum.reduceat(sh, st) == b['high'][w0:w1])
              & (np.minimum.reduceat(sl, st) == b['low'][w0:w1]))
        if not ok.all():
            raise ValueError('%s %s: %d chart bars differ from their sub-bars' % (pair, chart_tf, int((~ok).sum())))
    return ptr, so, sh, sl, sc


_NO_SUB = (np.zeros(1, np.int64), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0))


def prepare(pair, chart_tf, params=None):
    """Everything that does not depend on the exit settings, computed once: the window, the
    chart OHLC, longSignal / shortSignal (after Reverse Trading), the filter permissions, the
    half split. simulate(P, X) then runs the strategy + broker with the params given here,
    overridden by X (broker / exit params only: see _PREP_KEYS for those X may not change).
    P['sub'] holds the 1-minute sub-bars for path 'mag' once built (get_sub)."""
    P, fgfp = _params(params)
    chart_tf = str(chart_tf)
    b = load_bars(pair, chart_tf)
    start, end, w0, w1 = _window(pair, chart_tf, P)
    n = w1 - w0
    if n <= 0:
        raise ValueError('empty window')
    S = signals(pair, chart_tf, P)
    rev = bool(P['reverse'])
    lc = S['longCondition'][w0:w1]
    sc = S['shortCondition'][w0:w1]
    long_sig = np.ascontiguousarray(sc if rev else lc)
    short_sig = np.ascontiguousarray(lc if rev else sc)
    if P['fgfOn']:
        perm = permissions(pair, chart_tf, start, end, fgfp)
        if perm.index[0] != w0 or len(perm) != n:
            raise RuntimeError('filter rows do not match the window')
        buy_ok = np.ascontiguousarray(perm['buyOk'].to_numpy(bool))
        sell_ok = np.ascontiguousarray(perm['sellOk'].to_numpy(bool))
    else:
        buy_ok = np.ones(n, np.bool_)
        sell_ok = np.ones(n, np.bool_)
    sl = slice(w0, w1)
    tc = b['t_close'][sl]
    mid = start + (end - start) // 2
    return dict(pair=pair, tf=chart_tf, start=start, end=end, w0=w0, w1=w1, n=n, mid=mid,
                mid_j=int(np.searchsorted(tc, mid, side='right')) - 1,
                cap=2 * int(np.count_nonzero(long_sig | short_sig)) + 4,
                o=b['open'][sl], h=b['high'][sl], l=b['low'][sl], c=b['close'][sl],
                t_open=b['t_open'][sl], t_close=tc,
                long_sig=long_sig, short_sig=short_sig, buy_ok=buy_ok, sell_ok=sell_ok,
                S=S, params=P, fgfp=fgfp, sub=None)


def get_sub(Pp):
    if Pp.get('sub') is None:
        Pp['sub'] = sub_bars(Pp['pair'], Pp['tf'], Pp['w0'], Pp['w1'])
    return Pp['sub']


_R_KEYS = ('dir', 'ek', 'sk', 'epx', 'qty', 'xk', 'xsk', 'xpx', 'kind', 'gross', 'cost', 'sl', 'tp', 'eqb',
           'eq', 'pos', 'ebi', 'peak', 'cnt', 'want_l', 'want_s', 'blk_l', 'blk_s', 'stats')


def simulate(Pp, X=None, full=False):
    """Run the strategy + broker on prepare()'s arrays with the exit / broker params X (e.g.
    trailOn, trailAct, trailOff, InpTpPct, InpSlPct, InpExitCandles, cost, path, blkClose,
    hybrid inputs, hrdInv / inv) over the params given to prepare(). Returns a dict of the kernel outputs
    (window-relative bars); full=True adds the per-bar state arrays (run(), traces)."""
    Q = Pp['params']
    if X:
        Q = dict(Q)
        for k, v in X.items():
            k = _ALIASES.get(k, k)
            if k not in DEFAULTS:
                raise ValueError(f'unknown param {k!r}')
            if k in _PREP_KEYS and v != Q[k]:
                raise ValueError(f'{k!r} is fixed by prepare()')
            Q[k] = v
        _check(Q)
    c_fix, c_pct = COSTS[Q['cost']][Pp['pair']]
    td = Q['InpTradeDirection']
    mag = Q['path'] == 'mag'
    ptr, so, sh, sl_, sc = get_sub(Pp) if mag else _NO_SUB
    R = _simulate(Pp['o'], Pp['h'], Pp['l'], Pp['c'], Pp['long_sig'], Pp['short_sig'], Pp['buy_ok'], Pp['sell_ok'],
                  td in ('Both', 'Buy Only'), td in ('Both', 'Sell Only'), bool(Q['blkClose']),
                  float(Q['InpSlPct']), float(Q['InpTpPct']), float(Q['InpRiskPct']), float(Q['InpFixedQty']),
                  int(Q['InpExitCandles']), bool(Q['useHybridExit']), float(Q['hybridSensitivity']),
                  int(Q['minDecayUpdates']), float(Q['trailStepMult']), int(Q['minActivationPts']),
                  bool(Q['trailOn']), float(Q['trailAct']), float(Q['trailOff']),
                  mag, ptr, so, sh, sl_, sc,
                  MINTICK, POINTVALUE, INITIAL_CAPITAL, c_fix, c_pct,
                  int(Pp['cap']), bool(full), int(Pp['mid_j']), bool(Q['hrdInv']))
    return dict(zip(_R_KEYS, R))


def trades_frame(Pp, R):
    w0 = Pp['w0']
    to = Pp['t_open']
    tc = Pp['t_close']
    t_kind = R['kind']
    t_xk = R['xk']
    return pd.DataFrame({
        'dir': R['dir'].astype(np.int64),
        'entry_time': to[R['ek']],
        'entry_px': R['epx'],
        'qty': R['qty'],
        'exit_time': np.where(t_kind == K_END, tc[t_xk], to[t_xk]),
        'exit_px': R['xpx'],
        'exit_kind': [KINDS[k] for k in t_kind],
        'pnl': R['gross'] - R['cost'],
        'entry_bar': R['ek'] + w0,
        'exit_bar': t_xk + w0,
        'signal_bar': R['sk'] + w0,
        'exit_order_bar': np.where(R['xsk'] >= 0, R['xsk'] + w0, -1),
        'sl_px': R['sl'],
        'tp_px': R['tp'],
        'pnl_gross': R['gross'],
        'costs': R['cost'],
        'eq_before': R['eqb'],
    })


def extra_fields(Pp, R):
    """Fair halves and holding time from the kernel's trade arrays: h1r_pct / h2r_pct = for the
    trades ENTERED in each half (entry t_open <= mid / > mid), prod(1 + pnl / eq_before) - 1, in %
    (0 when the half has no trade); h1_trades / h2_trades; avg_bars_held = mean(exit bar - entry
    bar) (NaN without trades)."""
    pnl = R['gross'] - R['cost']
    eqb = R['eqb']
    first = Pp['t_open'][R['ek']] <= Pp['mid']
    r = 1.0 + pnl / eqb
    g1 = float(np.prod(r[first]))
    g2 = float(np.prod(r[~first]))
    nt = len(pnl)
    n1 = int(first.sum())
    return dict(h1r_pct=(g1 - 1.0) * 100.0, h2r_pct=(g2 - 1.0) * 100.0, h1_trades=n1, h2_trades=nt - n1,
                avg_bars_held=float((R['xk'] - R['ek']).mean()) if nt else np.nan)


def summary_fast(Pp, R):
    """summarize() + extra_fields() without the DataFrame and the per-bar arrays (the sweep):
    the same numbers (the kernel's running drawdown / half / exposure equal summarize()'s array
    operations exactly; the trade reductions are the same numpy calls). exits flattened to
    exit_<kind>; plus start / end / bars of the window and costs (the sum of the trades' costs)."""
    init = INITIAL_CAPITAL
    pnl = R['gross'] - R['cost']
    st = R['stats']
    final = float(st[0])
    eq_mid = float(st[1])
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    nt = len(pnl)
    d = R['dir']
    kc = np.bincount(R['kind'], minlength=len(KINDS)) if nt else np.zeros(len(KINDS), np.int64)
    out = dict(
        start=int(Pp['start']), end=int(Pp['end']), bars=int(Pp['n']),
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
        exposure=float(st[4] / Pp['n']),
        final_equity=final,
    )
    for i, nm in enumerate(KINDS[1:], 1):
        out['exit_' + nm] = int(kc[i])
    out['zero_length'] = int((R['ek'] == R['xk']).sum())
    out.update(extra_fields(Pp, R))
    out['costs'] = float(R['cost'].sum())
    return out


def run(pair, chart_tf, params=None, return_state=False):
    Pp = prepare(pair, chart_tf, params)
    R = simulate(Pp, None, full=True)
    trades = trades_frame(Pp, R)
    summ = summarize(trades, R['eq'], R['pos'], Pp['t_close'], Pp['start'], Pp['end'],
                     R['want_l'], R['want_s'], R['blk_l'], R['blk_s'])
    summ.update(extra_fields(Pp, R))
    summ.update(pair=pair, tf=Pp['tf'], bars=int(Pp['n']), w0=Pp['w0'], w1=Pp['w1'])
    if return_state:
        st = dict(eq=R['eq'], pos=R['pos'], ebi=R['ebi'], peak=R['peak'], cnt=R['cnt'],
                  want_l=R['want_l'], want_s=R['want_s'], blk_l=R['blk_l'], blk_s=R['blk_s'],
                  buy_ok=Pp['buy_ok'], sell_ok=Pp['sell_ok'], long_sig=Pp['long_sig'], short_sig=Pp['short_sig'],
                  w0=Pp['w0'], w1=Pp['w1'], S=Pp['S'], P=Pp['params'])
        return trades, summ, st
    return trades, summ


def summarize(trades, eq, pos, tc, start, end, want_l, want_s, blk_l, blk_s):
    init = INITIAL_CAPITAL
    pnl = trades['pnl'].to_numpy() if len(trades) else np.zeros(0)
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    final = float(eq[-1]) if len(eq) else init
    curve = np.concatenate([[init], eq])
    peak = np.maximum.accumulate(curve)
    dd = float(np.max((peak - curve) / peak) * 100) if len(curve) else 0.0
    dd_init = float(np.max(peak - curve) / init * 100) if len(curve) else 0.0
    mid = start + (end - start) // 2
    j = int(np.searchsorted(tc, mid, side='right')) - 1
    eq_mid = float(eq[j]) if j >= 0 else init
    kinds = trades['exit_kind'].value_counts().to_dict() if len(trades) else {}
    return dict(
        trades=int(len(trades)),
        net_pct=(final - init) / init * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if len(pnl) else np.nan,
        max_dd_pct=dd,                 # peak-to-trough % of the running peak, bar-close equity incl. open P/L
        max_dd_init_pct=dd_init,       # the same drawdown amount as % of the initial capital
        long=int((trades['dir'] > 0).sum()) if len(trades) else 0,
        short=int((trades['dir'] < 0).sum()) if len(trades) else 0,
        raw_long=int(want_l.sum()), raw_short=int(want_s.sum()),
        blocked_long=int(blk_l.sum()), blocked_short=int(blk_s.sum()),
        half1_pct=(eq_mid - init) / init * 100,
        half2_pct=(final - eq_mid) / init * 100,
        exposure=float((pos != 0).mean()) if len(pos) else 0.0,
        final_equity=final,
        exits={k: int(kinds.get(k, 0)) for k in KINDS[1:]},
        zero_length=int((trades['entry_bar'] == trades['exit_bar']).sum()) if len(trades) else 0,
    )


def fmt(s):
    return (f"{s['pair']} {s['tf']}: bars={s['bars']} trades={s['trades']} (L {s['long']} / S {s['short']}) "
            f"net={s['net_pct']:.3f}% pf={s['pf']:.3f} win={s['win_pct']:.1f}% maxDD={s['max_dd_pct']:.3f}% "
            f"h1={s['half1_pct']:.3f}% h2={s['half2_pct']:.3f}% exp={s['exposure']:.3f} "
            f"raw L/S={s['raw_long']}/{s['raw_short']} blocked L/S={s['blocked_long']}/{s['blocked_short']} "
            f"exits={s['exits']}")


if __name__ == '__main__':
    for pair in ('BTC', 'XAU'):
        t0 = _time.time()
        tr, s = run(pair, '60')
        print(fmt(s), f'time {_time.time() - t0:.1f}s')
