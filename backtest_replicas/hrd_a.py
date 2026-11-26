"""HRD Full Divergence Strategy v1.03 + FlashGold Direction Filter: Python replica,
implementation A.

Ground truth: /home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine
(with "Enable filter" off it is /home/user/master/HRD_Full_Divergence_Strategy_v1_03.pine).
Spec: SPEC_AH.md. Interpretations: hrd_a_notes.md.

    run(pair, chart_tf, params=None) -> (trades: DataFrame, summary: dict)

History only (TradingView Strategy Tester, no Bar Magnifier): the script runs once
per chart bar at its close; market orders fill at the next bar's open in the
order they were placed; the SL / TP bracket is checked along the intrabar path.
The direction filter permissions come from fgf.py (fgf_permissions).

Pipeline
  1. signals over ALL bars of the chart file (warm-up from the start of data):
     D / W / M horizons (request.security lookahead_on, [1]), breakouts, RSI /
     MACD / stoch oscillator, pivots and the divergence state machine (numba).
  2. broker + strategy logic over the window bars only (numba): time exit,
     filter gate, blocked-opposite close, entries with SL / TP, hybrid
     decay-slip exit, fills, intrabar bracket, equity, FGD counts.

Run as a script for a quick summary:  python3 -I hrd_a.py
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

KINDS = ['', 'sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end']
K_SL, K_TP, K_REV, K_BLK, K_TIME, K_HYB, K_END = 1, 2, 3, 4, 5, 6, 7

DEFAULTS = dict(
    # replica controls
    fgfOn=True, blkClose=True, cost='tv', reverse=False, pivotTies='strict',
    smaNa='skip',            # ta.sma on na stoch values: 'skip' (Pine docs) or 'propagate'
    start=None, end=None,    # window override (t_close, epoch s)
    # Divergence Engine
    pivotStrength=5, maxDivLookback=60,
    showBullReg=True, showBearReg=True, showBullHid=True, showBearHid=True,
    # Strategy Rules & Risk
    InpTradeDirection='Both', InpRiskPct=1.0, InpFixedQty=0.01, InpSlPct=2.0, InpTpPct=4.0,
    InpExitCandles=5,
    # Hybrid decay-slip exit
    useHybridExit=True, hybridSensitivity=1.0, minDecayUpdates=10, trailStepMult=1.0,
    minActivationPts=40,
)
_ALIASES = {'InpReverseTrading': 'reverse', 'hrdBlkClose': 'blkClose'}
# display-only inputs: accepted and ignored
_DISPLAY = {'dailyColor', 'weeklyColor', 'monthlyColor', 'showDivLines', 'showLabels', 'alertsOn',
            'scoreThreshold', 'scoreBullReg', 'scoreBearReg', 'scoreBullHid', 'scoreBearHid', 'showBreaks'}


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
    if P['cost'] not in ('tv', 'ours'):
        raise ValueError("cost must be 'tv' or 'ours'")
    if P['pivotTies'] not in ('strict', 'left_strict'):
        raise ValueError("pivotTies must be 'strict' or 'left_strict'")
    if P['smaNa'] not in ('skip', 'propagate'):
        raise ValueError("smaNa must be 'skip' or 'propagate'")
    if P['InpTradeDirection'] not in ('Both', 'Buy Only', 'Sell Only'):
        raise ValueError('InpTradeDirection must be Both / Buy Only / Sell Only')
    if int(P['pivotStrength']) < 1 or int(P['maxDivLookback']) < 10 or int(P['InpExitCandles']) < 1:
        raise ValueError('below a Pine minval')
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
def _simulate(o, h, l, c, long_sig, short_sig, buy_ok, sell_ok,
              long_allowed, short_allowed, blk_close,
              sl_pct, tp_pct, risk_pct, fixed_qty, exit_candles,
              use_hybrid, hyb_sens, min_updates, trail_mult, min_act_pts,
              mintick, pointvalue, init_cap, c_fix, c_pct):
    n = o.shape[0]
    maxt = 2 * n + 4
    t_dir = np.zeros(maxt, np.int64)
    t_ek = np.zeros(maxt, np.int64)        # entry fill bar (window-relative)
    t_sk = np.zeros(maxt, np.int64)        # bar where the entry order was placed
    t_epx = np.zeros(maxt)
    t_qty = np.zeros(maxt)
    t_xk = np.zeros(maxt, np.int64)        # exit bar
    t_xsk = np.zeros(maxt, np.int64)       # bar where the exit order was placed (-1: bracket / end)
    t_xpx = np.zeros(maxt)
    t_kind = np.zeros(maxt, np.int64)
    t_gross = np.zeros(maxt)
    t_cost = np.zeros(maxt)
    t_sl = np.zeros(maxt)
    t_tp = np.zeros(maxt)
    nt = 0

    eq_close = np.zeros(n)
    pos_close = np.zeros(n)
    ebi_arr = np.full(n, -1, np.int64)
    peak_arr = np.zeros(n)
    cnt_arr = np.zeros(n, np.int64)
    want_l = np.zeros(n, np.bool_)
    want_s = np.zeros(n, np.bool_)
    blk_l = np.zeros(n, np.bool_)
    blk_s = np.zeros(n, np.bool_)

    # pending orders (placed on bar k, filled at the open of bar k+1)
    # type: 1 close_all, 2 close(entry id = dir), 3 entry(dir)
    MAXO = 8
    p_type = np.zeros(MAXO, np.int64)
    p_dir = np.zeros(MAXO, np.int64)
    p_qty = np.zeros(MAXO)
    p_sl = np.zeros(MAXO)
    p_tp = np.zeros(MAXO)
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

    prev_pos = 0.0
    ebi = -1                  # entryBarIndex (-1 = na)
    g_peak = 0.0
    g_cnt = 0
    act_level = min_act_pts * mintick
    decay_thr = trail_mult * 8 * mintick * hyb_sens

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
                    t_sl[nt] = psl; t_tp[nt] = ptp
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
                    t_sl[nt] = psl; t_tp[nt] = ptp
                    nt += 1
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
        np_ = 0
        # ---- 2. the open trade's SL / TP bracket along the intrabar path
        if pdir != 0 and (not np.isnan(psl) or not np.isnan(ptp)):
            xpx = np.nan
            kind = 0
            has_s = not np.isnan(psl)
            has_t = not np.isnan(ptp)
            high_first = (hk - ok_) < (ok_ - lk)     # True: O->H->L->C ; False: O->L->H->C
            if pdir > 0:
                if has_s and ok_ <= psl:
                    xpx = ok_; kind = K_SL
                elif has_t and ok_ >= ptp:
                    xpx = ok_; kind = K_TP
                elif high_first:
                    if has_t and hk >= ptp:
                        xpx = ptp; kind = K_TP
                    elif has_s and lk <= psl:
                        xpx = psl; kind = K_SL
                else:                    # low first (O->L->H->C)
                    if has_s and lk <= psl:
                        xpx = psl; kind = K_SL
                    elif has_t and hk >= ptp:
                        xpx = ptp; kind = K_TP
            else:
                if has_s and ok_ >= psl:
                    xpx = ok_; kind = K_SL
                elif has_t and ok_ <= ptp:
                    xpx = ok_; kind = K_TP
                elif high_first:
                    if has_s and hk >= psl:
                        xpx = psl; kind = K_SL
                    elif has_t and lk <= ptp:
                        xpx = ptp; kind = K_TP
                else:                    # low first (O->L->H->C)
                    if has_t and lk <= ptp:
                        xpx = ptp; kind = K_TP
                    elif has_s and hk >= psl:
                        xpx = psl; kind = K_SL
            if kind != 0:
                xc = _cost(xpx, pqty, c_fix, c_pct)
                cash += pdir * pqty * (xpx - ppx) * pointvalue - xc
                t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
                t_xk[nt] = k; t_xsk[nt] = -1; t_xpx[nt] = xpx; t_kind[nt] = kind
                t_gross[nt] = pdir * pqty * (xpx - ppx) * pointvalue; t_cost[nt] = pcost + xc
                t_sl[nt] = psl; t_tp[nt] = ptp
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
        # direction filter gate
        wl = long_sig[k] and long_allowed and pos <= 0
        ws = short_sig[k] and short_allowed and pos >= 0
        bl = wl and not buy_ok[k]
        bs = ws and not sell_ok[k]
        want_l[k] = wl
        want_s[k] = ws
        blk_l[k] = bl
        blk_s[k] = bs
        if blk_close and bl and pos < 0:
            p_type[np_] = 2; p_dir[np_] = -1; p_kind[np_] = K_BLK; np_ += 1
        if blk_close and bs and pos > 0:
            p_type[np_] = 2; p_dir[np_] = 1; p_kind[np_] = K_BLK; np_ += 1
        # 4. LONG / 5. SHORT execution
        for side in (1, -1):
            go = (wl and buy_ok[k]) if side == 1 else (ws and sell_ok[k])
            if not go:
                continue
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
            p_type[np_] = 3; p_dir[np_] = side; p_qty[np_] = qty; p_sl[np_] = slp; p_tp[np_] = tpp
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
        eq_close[k] = equity
        pos_close[k] = pos
        ebi_arr[k] = ebi
        peak_arr[k] = g_peak
        cnt_arr[k] = g_cnt

    # orders placed on the last bar do not fill; an open trade is closed at the last close
    if pdir != 0:
        k = n - 1
        xc = _cost(c[k], pqty, c_fix, c_pct)
        cash += pdir * pqty * (c[k] - ppx) * pointvalue - xc
        t_dir[nt] = pdir; t_ek[nt] = pek; t_sk[nt] = psk; t_epx[nt] = ppx; t_qty[nt] = pqty
        t_xk[nt] = k; t_xsk[nt] = -1; t_xpx[nt] = c[k]; t_kind[nt] = K_END
        t_gross[nt] = pdir * pqty * (c[k] - ppx) * pointvalue; t_cost[nt] = pcost + xc
        t_sl[nt] = psl; t_tp[nt] = ptp
        nt += 1
        eq_close[k] = cash
    return (t_dir[:nt], t_ek[:nt], t_sk[:nt], t_epx[:nt], t_qty[:nt], t_xk[:nt], t_xsk[:nt], t_xpx[:nt],
            t_kind[:nt], t_gross[:nt], t_cost[:nt], t_sl[:nt], t_tp[:nt],
            eq_close, pos_close, ebi_arr, peak_arr, cnt_arr, want_l, want_s, blk_l, blk_s, cash)


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


def run(pair, chart_tf, params=None, return_state=False):
    P, fgfp = _params(params)
    chart_tf = str(chart_tf)
    b = load_bars(pair, chart_tf)
    start, end, w0, w1 = _window(pair, chart_tf, P)
    n = w1 - w0
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
    td = P['InpTradeDirection']
    long_allowed = td in ('Both', 'Buy Only')
    short_allowed = td in ('Both', 'Sell Only')
    if P['cost'] == 'ours':
        c_fix, c_pct = (0.15, 0.0) if pair == 'XAU' else (0.10, 0.0002)
    else:
        c_fix, c_pct = 0.0, 0.0          # HRD's strategy() sets no commission
    sl = slice(w0, w1)
    R = _simulate(b['open'][sl], b['high'][sl], b['low'][sl], b['close'][sl],
                  long_sig, short_sig, buy_ok, sell_ok, long_allowed, short_allowed, bool(P['blkClose']),
                  float(P['InpSlPct']), float(P['InpTpPct']), float(P['InpRiskPct']), float(P['InpFixedQty']),
                  int(P['InpExitCandles']), bool(P['useHybridExit']), float(P['hybridSensitivity']),
                  int(P['minDecayUpdates']), float(P['trailStepMult']), int(P['minActivationPts']),
                  MINTICK, POINTVALUE, INITIAL_CAPITAL, c_fix, c_pct)
    (t_dir, t_ek, t_sk, t_epx, t_qty, t_xk, t_xsk, t_xpx, t_kind, t_gross, t_cost, t_sl, t_tp,
     eq, pos, ebi, peak, cnt, want_l, want_s, blk_l, blk_s, cash) = R
    to = b['t_open'][sl]
    tc = b['t_close'][sl]
    trades = pd.DataFrame({
        'dir': t_dir.astype(np.int64),
        'entry_time': to[t_ek],
        'entry_px': t_epx,
        'qty': t_qty,
        'exit_time': np.where(t_kind == K_END, tc[t_xk], to[t_xk]),
        'exit_px': t_xpx,
        'exit_kind': [KINDS[k] for k in t_kind],
        'pnl': t_gross - t_cost,
        'entry_bar': t_ek + w0,
        'exit_bar': t_xk + w0,
        'signal_bar': t_sk + w0,
        'exit_order_bar': np.where(t_xsk >= 0, t_xsk + w0, -1),
        'sl_px': t_sl,
        'tp_px': t_tp,
        'pnl_gross': t_gross,
        'costs': t_cost,
    })
    summ = summarize(trades, eq, pos, tc, start, end, want_l, want_s, blk_l, blk_s)
    summ.update(pair=pair, tf=chart_tf, bars=int(n), w0=w0, w1=w1)
    if return_state:
        st = dict(eq=eq, pos=pos, ebi=ebi, peak=peak, cnt=cnt, want_l=want_l, want_s=want_s,
                  blk_l=blk_l, blk_s=blk_s, buy_ok=buy_ok, sell_ok=sell_ok,
                  long_sig=long_sig, short_sig=short_sig, w0=w0, w1=w1, S=S, P=P)
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
