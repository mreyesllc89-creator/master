"""Independent verifier of hrd.py's "Inverted direction" option (Pine UPDATE 1, input hrdInv).

A plain pure-Python reference for HRD v1.03 + FGF WITH the option, written from the Pine at HEAD
(/home/user/master/HRD_Full_Divergence_Strategy_v1_03_FGF.pine, lines 974-1106) and the broker
rules of SPEC_AH.md / SWEEP_AH_SPEC.md, WITHOUT reading the new code paths of hrd.py.

It is built differently from the replica and from the older verify_trail_hrd.py on purpose:
  * a small order-id broker (strategy.entry(id, direction, qty) / strategy.exit(id, from_entry,
    stop, limit, trail_points, trail_offset) / strategy.close(id) / strategy.close_all) that
    knows nothing about the option;
  * the script section transliterated line by line from the Pine, with the hrdInv conditionals
    exactly where the Pine has them (hrdPos, hrdDirOkL / hrdDirOkS, hrdIdL / hrdIdS, the two
    close calls, the two EXECUTION blocks, the hybrid exit on the real position);
  * one exit walker in "up space" (a short trade is walked on negated prices).
From hrd.py it takes only prepare()'s per-bar inputs: the window, chart OHLC / times, longSignal /
shortSignal (after "Reverse Trading") and the filter permissions buyOk / sellOk; the 1-minute
sub-bars are rebuilt here from data/<PAIR>_1.parquet.

Usage:
  python3 -I verify_inv_hrd.py check DATASET [NRANDOM] [SEED]   DATASET in BTC60, XAU60, BTC15, XAU240
  python3 -I verify_inv_hrd.py json PAIR TF                      reference vs out/inv_hrd_<PAIR>_<TF>.json
  python3 -I verify_inv_hrd.py trace                             hand-trace 8 inverted trades (bars printed)
  python3 -I verify_inv_hrd.py mutate [DATASET ...]              each wrong reading must be caught
  python3 -I verify_inv_hrd.py inputs                            checks of the inputs taken from prepare()
  python3 -I verify_inv_hrd.py api                               hrdInv / inv / prepare() / run() give the same run
  python3 -I verify_inv_hrd.py chart1                            chart "1": reference = replica tv = replica mag
"""
import os
import sys
import json
import time
import random
import datetime as _dt

import numpy as np
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402  inputs: prepare(); under test: simulate / trades_frame / summary_fast

MINTICK = 0.01           # syminfo.mintick (SPEC_AH.md: 0.01 for both symbols)
POINTVALUE = 1.0         # syminfo.pointvalue
INIT = 1_000_000.0       # Pine default initial_capital
# per fill: ($ per unit, fraction of the fill value) - SPEC_AH.md / SWEEP_AH_SPEC.md / INV_BT_SPEC.md
COST = {
    'tv': {'XAU': (0.0, 0.0), 'BTC': (0.0, 0.0)},
    'ours': {'XAU': (0.15, 0.0), 'BTC': (0.10, 0.0002)},
    'stress': {'XAU': (0.25 + 0.01, 0.0), 'BTC': (0.10 + 0.01, 0.00035)},
}
# the Pine's own input defaults (read from the input.* lines of the file at HEAD)
PINE = dict(InpTradeDirection='Both', InpRiskPct=1.0, InpFixedQty=0.01, InpSlPct=2.0, InpTpPct=4.0,
            InpExitCandles=5, useHybridExit=True, hybridSensitivity=1.0, minDecayUpdates=10,
            trailStepMult=1.0, minActivationPts=40, hrdBlkClose=True, hrdTrailOn=False,
            hrdTrailAct=1.0, hrdTrailOff=0.5, hrdInv=False)
DATASETS = {
    'BTC60': ('BTC', '60', None, None),
    'XAU60': ('XAU', '60', None, None),
    'BTC15': ('BTC', '15', 1767225600, 1775001600),     # 2026-01-01 .. 2026-04-01 (3 months)
    'XAU240': ('XAU', '240', None, None),
}
MUT = set()              # mutate mode only: wrong readings of the option that the check must catch


def module_id():
    import hashlib
    return f'{hrd.__file__} sha256 {hashlib.sha256(open(hrd.__file__, "rb").read()).hexdigest()}'


# ---------------------------------------------------------------------------------------------
# 1-minute sub-bars, rebuilt here
# ---------------------------------------------------------------------------------------------
_M1 = {}


def sub_bars(pair, t_open, t_close):
    """(lo, hi, O, H, L, C): the sub-bars of chart bar j are rows lo[j]..hi[j]-1 of the lists."""
    if pair not in _M1:
        _M1[pair] = pq.read_table(os.path.join(W, 'data', f'{pair}_1.parquet'),
                                  columns=['open', 'high', 'low', 'close', 't_open']).to_pandas()
    m = _M1[pair]
    mt = m['t_open'].to_numpy()
    lo = np.searchsorted(mt, t_open, side='left')
    hi = np.searchsorted(mt, t_close, side='left')
    a, b = int(lo[0]), int(hi[-1])
    return ((lo - a).tolist(), (hi - a).tolist(), m['open'].to_numpy()[a:b].tolist(),
            m['high'].to_numpy()[a:b].tolist(), m['low'].to_numpy()[a:b].tolist(),
            m['close'].to_numpy()[a:b].tolist(), mt[a:b].tolist())


# ---------------------------------------------------------------------------------------------
# the exit order of one trade along one path, in "up space" (u = dir x price)
# ---------------------------------------------------------------------------------------------
def rule4(o, h, l, c):
    """SPEC_AH.md rule 4: high first when (high - open) < (open - low), else low first."""
    return (o, h, l, c) if (h - o) < (o - l) else (o, l, h, c)


def _stop_level(t):
    """The protective level in up space and its kind: the higher of the stop loss and the armed
    trailing stop (trailing stop >= stop loss -> 'trail')."""
    ts = (t['ubest'] - t['off']) if (t['trail'] and t['armed']) else None
    if ts is None:
        return t['usl'], 'sl'
    if t['usl'] is None or ts >= t['usl']:
        return ts, 'trail'
    return t['usl'], 'sl'


def _trail_see(t, u):
    """A price the trade has traded at (in its favour or at an open): arm / ratchet the trail."""
    if not t['trail']:
        return
    if t['armed']:
        if u > t['ubest']:
            t['ubest'] = u
    elif u >= t['uA']:
        t['armed'] = True
        t['ubest'] = u


def walk(t, pts):
    """Exit order of trade t along the real-price path pts (4 points). Returns (kind, real price)
    or None; keeps the trailing state in t."""
    d = t['d']
    u0 = d * pts[0]
    lvl, kind = _stop_level(t)
    if lvl is not None and u0 <= lvl:            # already at / beyond the stop at this open
        return kind, pts[0]
    if t['utp'] is not None and u0 >= t['utp']:  # already at / beyond the limit at this open
        return 'tp', pts[0]
    _trail_see(t, u0)
    a = u0
    for p in pts[1:]:
        b = d * p
        if b > a:                                # favourable move: the limit, then the trail follows
            if t['utp'] is not None and b >= t['utp']:
                return 'tp', d * t['utp']
            _trail_see(t, b)
        elif b < a:                              # adverse move: the stop loss / trailing stop
            lvl, kind = _stop_level(t)
            if lvl is not None and b <= lvl:
                return kind, d * lvl
        a = b
    return None


# ---------------------------------------------------------------------------------------------
# the strategy (Pine, transliterated) on a small order-id broker
# ---------------------------------------------------------------------------------------------
def reference(Pp, X=None, sub=None, log=None):
    """Pp: hrd.prepare() output (inputs only). X: Pine inputs by their Pine names + cost, path.
    Returns dict(trades=[...], cash, eq=[...], npos, cnt={...}).  log: dict bar -> list of lines."""
    q = dict(PINE)
    q.update(cost='tv', path='tv')
    for k, v in (X or {}).items():
        if k not in q:
            raise KeyError(k)
        q[k] = v
    o = Pp['o'].tolist()
    h = Pp['h'].tolist()
    l = Pp['l'].tolist()
    c = Pp['c'].tolist()
    LS = Pp['long_sig'].tolist()
    SS = Pp['short_sig'].tolist()
    BOK = Pp['buy_ok'].tolist()
    SOK = Pp['sell_ok'].tolist()
    n = Pp['n']
    c_fix, c_pct = COST[q['cost']][Pp['pair']]
    mag = q['path'] == 'mag'
    if mag:
        slo, shi, MO, MH, ML, MC, MT = sub

    InpTradeDirection = q['InpTradeDirection']
    InpRiskPct = float(q['InpRiskPct'])
    InpFixedQty = float(q['InpFixedQty'])
    InpSlPct = float(q['InpSlPct'])
    InpTpPct = float(q['InpTpPct'])
    InpExitCandles = int(q['InpExitCandles'])
    useHybridExit = bool(q['useHybridExit'])
    hybridSensitivity = float(q['hybridSensitivity'])
    minDecayUpdates = int(q['minDecayUpdates'])
    trailStepMult = float(q['trailStepMult'])
    minActivationPts = int(q['minActivationPts'])
    hrdBlkClose = bool(q['hrdBlkClose'])
    hrdTrailOn = bool(q['hrdTrailOn'])
    hrdTrailAct = float(q['hrdTrailAct'])
    hrdTrailOff = float(q['hrdTrailOff'])
    hrdInv = bool(q['hrdInv'])

    def fee(px, qty):
        return qty * c_fix + qty * px * c_pct

    # ---- broker state ----
    cash = INIT                 # initial capital + closed P/L - every commission paid so far
    T = None                    # the open trade (pyramiding 0: at most one)
    exit_orders = {}            # from_entry id -> exit order placed by strategy.exit
    pending = []                # market orders placed at the last close, in placement order
    trades = []
    eq = []
    npos = 0

    def close_trade(i, px, kind, order_bar):
        nonlocal cash, T
        t = T
        t['xk'] = i
        t['xpx'] = px
        t['kind'] = kind
        t['xob'] = order_bar
        t['gross'] = t['d'] * (px - t['epx']) * t['qty']
        t['xcost'] = fee(px, t['qty'])
        cash += t['gross'] - t['xcost']
        exit_orders.pop(t['id'], None)          # an exit whose entry trade has closed is cancelled
        trades.append(t)
        T = None

    # ---- script state (var) ----
    entryBarIndex = None
    prev_position_size = 0.0
    g_PeakProfit = 0.0
    g_UpdateCounter = 0
    cnt = dict(raw_long=0, raw_short=0, blocked_long=0, blocked_short=0)

    def calculatePositionSize(slDistancePrice, strategy_equity):
        positionSize = 0.0
        if InpSlPct <= 0.0 or slDistancePrice <= 0.0:
            positionSize = InpFixedQty
        else:
            riskAmount = strategy_equity * (InpRiskPct / 100.0)
            if POINTVALUE > 0.0:
                positionSize = riskAmount / (slDistancePrice * POINTVALUE)
            else:
                positionSize = InpFixedQty
            if positionSize < InpFixedQty:
                positionSize = InpFixedQty
        return positionSize

    longDirectionAllowed = (InpTradeDirection == "Both") or (InpTradeDirection == "Buy Only")
    shortDirectionAllowed = (InpTradeDirection == "Both") or (InpTradeDirection == "Sell Only")

    for i in range(n):
        lg = None
        if log is not None:
            lg = log.setdefault(i, [])
        # ============ broker: market orders of the previous close fill at this open ============
        for od in pending:
            if od[0] == 'close_all':
                if T is not None:
                    if lg is not None:
                        lg.append(f'open {o[i]}: close_all ("{od[1]}") closes the {T["id"]} trade')
                    close_trade(i, o[i], od[1], i - 1)
            elif od[0] == 'close':
                if T is not None and T['id'] == od[1]:
                    if lg is not None:
                        lg.append(f'open {o[i]}: strategy.close("{od[1]}") closes the {T["id"]} trade')
                    close_trade(i, o[i], 'blocked_close', i - 1)
            else:
                _, eid, d, qty, sbar = od
                if T is not None and T['d'] == d:
                    if MUT:
                        continue                  # pyramiding 0 (reachable only under a mutation)
                    raise RuntimeError('entry in the direction of the open position (never placed by this script)')
                if T is not None:                 # opposite entry: reversal in the same fill
                    if lg is not None:
                        lg.append(f'open {o[i]}: entry "{eid}" reverses: closes the {T["id"]} trade')
                    close_trade(i, o[i], 'reverse', i - 1)
                T = dict(id=eid, d=d, qty=qty, epx=o[i], ek=i, sk=sbar, eqb=cash, ecost=fee(o[i], qty),
                         usl=None, utp=None, sl=None, tp=None, trail=False, armed=False, uA=None, off=None,
                         ubest=None)
                cash -= T['ecost']
                ex = exit_orders.get(eid)
                if ex is not None:                # strategy.exit(from_entry = eid) now works this trade
                    T['sl'] = ex['stop']
                    T['tp'] = ex['limit']
                    T['usl'] = None if ex['stop'] is None else d * ex['stop']
                    T['utp'] = None if ex['limit'] is None else d * ex['limit']
                    if ex['trail_points'] is not None:
                        T['trail'] = True
                        T['uA'] = d * T['epx'] + ex['trail_points'] * MINTICK   # fill +/- trail_points ticks
                        T['off'] = ex['trail_offset'] * MINTICK
                        T['armed'] = ex['trail_points'] == 0.0
                        T['ubest'] = d * T['epx']
                if lg is not None:
                    lg.append(f'open {o[i]}: entry "{eid}" fills: {"BUY" if d > 0 else "SELL"} {qty:.6f} at {o[i]}'
                              f' (stop {T["sl"]}, limit {T["tp"]}'
                              + (f', trail activation {d * T["uA"]:.6f} offset {T["off"]:.6f}' if T['trail'] else '')
                              + ')')
        pending = []
        # ============ broker: the open trade's exit order along this bar ============
        if T is not None:
            res = None
            def _tstate(t):
                if not t['trail']:
                    return ''
                if not t['armed']:
                    return f'trail not armed (activation {t["d"] * t["uA"]:.6f})'
                return (f'trail armed, best {t["d"] * t["ubest"]}, trailing stop '
                        f'{t["d"] * (t["ubest"] - t["off"]):.6f}')
            if mag:
                for k in range(slo[i], shi[i]):
                    st0 = (T['armed'], T['ubest'])
                    res = walk(T, rule4(MO[k], MH[k], ML[k], MC[k]))
                    if lg is not None and (res is not None or st0 != (T['armed'], T['ubest'])):
                        lg.append(f'1-minute bar {ts(MT[k])} O {MO[k]} H {MH[k]} L {ML[k]} C {MC[k]} path '
                                  f'{rule4(MO[k], MH[k], ML[k], MC[k])}: {_tstate(T)}'
                                  + (f' -> exit {res[0]} at {res[1]}' if res is not None else ''))
                    if res is not None:
                        break
            else:
                res = walk(T, rule4(o[i], h[i], l[i], c[i]))
                if lg is not None and (res is not None or T['trail']):
                    lg.append(f'path {rule4(o[i], h[i], l[i], c[i])}: {_tstate(T)}'
                              + (f' -> exit {res[0]} at {res[1]}' if res is not None else ''))
            if res is not None:
                close_trade(i, res[1], res[0], -1)
        # ============ the script at the close of bar i (Pine 974-1106) ============
        position_size = 0.0 if T is None else T['d'] * T['qty']        # strategy.position_size
        close = c[i]
        open_profit = 0.0 if T is None else T['d'] * (close - T['epx']) * T['qty']
        equity = cash + open_profit                                    # strategy.equity
        eq.append(equity)
        if position_size != 0:
            npos += 1
        longSignal = bool(LS[i])           # after "Reverse Trading" (prepare)
        shortSignal = bool(SS[i])
        fgfBuyOk = bool(BOK[i])
        fgfSellOk = bool(SOK[i])
        orders = []

        # 3. Time-based exit
        if position_size != 0 and prev_position_size == 0:
            entryBarIndex = i
        if position_size != 0 and entryBarIndex is not None and (i - entryBarIndex >= InpExitCandles):
            orders.append(('close_all', 'time'))
            entryBarIndex = None

        hrdPos = -position_size if hrdInv else position_size
        hrdDirOkL = shortDirectionAllowed if hrdInv else longDirectionAllowed
        hrdDirOkS = longDirectionAllowed if hrdInv else shortDirectionAllowed
        hrdIdL = "Short" if hrdInv else "Long"
        hrdIdS = "Long" if hrdInv else "Short"
        if 'pos_real' in MUT:
            hrdPos = position_size
        if 'dir_not_swapped' in MUT:
            hrdDirOkL, hrdDirOkS = longDirectionAllowed, shortDirectionAllowed
        hrdWantLong = longSignal and hrdDirOkL and hrdPos <= 0
        hrdWantShort = shortSignal and hrdDirOkS and hrdPos >= 0
        okL, okS = fgfBuyOk, fgfSellOk
        if 'gate_swapped' in MUT and hrdInv:      # the flip BEFORE the gate (= "Reverse Trading")
            okL, okS = fgfSellOk, fgfBuyOk
        hrdBlkLong = hrdWantLong and not okL
        hrdBlkShort = hrdWantShort and not okS
        cnt['raw_long'] += hrdWantLong
        cnt['raw_short'] += hrdWantShort
        cnt['blocked_long'] += hrdBlkLong
        cnt['blocked_short'] += hrdBlkShort

        if hrdBlkClose and hrdBlkLong and hrdPos < 0:
            orders.append(('close', hrdIdL if 'blk_wrong_id' in MUT else hrdIdS))
        if hrdBlkClose and hrdBlkShort and hrdPos > 0:
            orders.append(('close', hrdIdS if 'blk_wrong_id' in MUT else hrdIdL))

        mirror_px = hrdInv and 'px_not_mirrored' not in MUT
        blocks = [('L', hrdWantLong and okL), ('S', hrdWantShort and okS)]
        if 'block_order' in MUT and hrdInv:
            blocks.reverse()
        for side, go in blocks:
            if not go:
                continue
            estimatedEntryPrice = close
            if side == 'L':
                # 4. LONG EXECUTION
                stopLossDistanceLong = estimatedEntryPrice * (InpSlPct / 100.0) if InpSlPct > 0.0 else 0.0
                stopLossPriceLong = (estimatedEntryPrice * ((1.0 + InpSlPct / 100.0) if mirror_px
                                                            else (1.0 - InpSlPct / 100.0))
                                     if InpSlPct > 0.0 else None)
                takeProfitPriceLong = (estimatedEntryPrice * ((1.0 - InpTpPct / 100.0) if mirror_px
                                                              else (1.0 + InpTpPct / 100.0))
                                       if InpTpPct > 0.0 else None)
                longQuantity = calculatePositionSize(stopLossDistanceLong, equity)
                orders.append(('entry', hrdIdL, (-1 if hrdInv else 1), longQuantity, i))
                hrdTrPts = max(estimatedEntryPrice * hrdTrailAct / 100.0 / MINTICK, 0.0) if hrdTrailOn else None
                hrdTrOfs = max(estimatedEntryPrice * hrdTrailOff / 100.0 / MINTICK, 1.0) if hrdTrailOn else None
                exit_orders[hrdIdL] = dict(stop=stopLossPriceLong, limit=takeProfitPriceLong,
                                           trail_points=hrdTrPts, trail_offset=hrdTrOfs)
            else:
                # 5. SHORT EXECUTION
                stopLossDistanceShort = estimatedEntryPrice * (InpSlPct / 100.0) if InpSlPct > 0.0 else 0.0
                stopLossPriceShort = (estimatedEntryPrice * ((1.0 - InpSlPct / 100.0) if mirror_px
                                                             else (1.0 + InpSlPct / 100.0))
                                      if InpSlPct > 0.0 else None)
                takeProfitPriceShort = (estimatedEntryPrice * ((1.0 + InpTpPct / 100.0) if mirror_px
                                                               else (1.0 - InpTpPct / 100.0))
                                        if InpTpPct > 0.0 else None)
                shortQuantity = calculatePositionSize(stopLossDistanceShort, equity)
                orders.append(('entry', hrdIdS, (1 if hrdInv else -1), shortQuantity, i))
                hrdTrPts = max(estimatedEntryPrice * hrdTrailAct / 100.0 / MINTICK, 0.0) if hrdTrailOn else None
                hrdTrOfs = max(estimatedEntryPrice * hrdTrailOff / 100.0 / MINTICK, 1.0) if hrdTrailOn else None
                exit_orders[hrdIdS] = dict(stop=stopLossPriceShort, limit=takeProfitPriceShort,
                                           trail_points=hrdTrPts, trail_offset=hrdTrOfs)

        # HYBRID DECAY-SLIP EXIT ENGINE (the trade really open)
        inTrade = position_size != 0
        isLong = position_size > 0
        if 'hybrid_frame' in MUT and hrdInv:
            isLong = not isLong
        currentProfit = 0.0
        if inTrade:
            if isLong:
                currentProfit = close - T['epx']        # strategy.position_avg_price = the fill price
            else:
                currentProfit = T['epx'] - close
        if not inTrade:
            g_PeakProfit = 0.0
            g_UpdateCounter = 0
        hyb = ''
        if useHybridExit and inTrade:
            activationLevel = minActivationPts * MINTICK
            if (currentProfit >= activationLevel) or (g_PeakProfit >= activationLevel):
                g_UpdateCounter += 1
                if currentProfit > g_PeakProfit:
                    g_PeakProfit = currentProfit
                speedDrop = g_PeakProfit - currentProfit
                decayTriggered = speedDrop > (trailStepMult * 8 * MINTICK * hybridSensitivity)
                slipTriggered = currentProfit < (g_PeakProfit * 0.85)
                hyb = f' hybrid: profit {currentProfit:.2f} peak {g_PeakProfit:.2f} updates {g_UpdateCounter}'
                if decayTriggered and slipTriggered and g_UpdateCounter >= minDecayUpdates and g_PeakProfit > 0:
                    orders.append(('close_all', 'hybrid'))
                    g_PeakProfit = 0.0
                    g_UpdateCounter = 0
        if lg is not None:
            lg.append(f'close {close}: position_size {position_size:+.6f} hrdPos {hrdPos:+.6f} | longSignal '
                      f'{int(longSignal)} shortSignal {int(shortSignal)} fgfBuyOk {int(fgfBuyOk)} fgfSellOk '
                      f'{int(fgfSellOk)} | hrdWantLong {int(hrdWantLong)} hrdWantShort {int(hrdWantShort)} '
                      f'hrdBlkLong {int(hrdBlkLong)} hrdBlkShort {int(hrdBlkShort)} | entryBarIndex '
                      f'{None if entryBarIndex is None else entryBarIndex + Pp["w0"]} equity {equity:.2f}{hyb}')
            for od in orders:
                if od[0] == 'entry':
                    ex = exit_orders[od[1]]
                    lg.append(f'   order: strategy.entry("{od[1]}", {"long" if od[2] > 0 else "short"}, qty '
                              f'{od[3]:.6f}) + strategy.exit(stop {ex["stop"]}, limit {ex["limit"]}, trail_points '
                              f'{ex["trail_points"]}, trail_offset {ex["trail_offset"]})')
                elif od[0] == 'close':
                    lg.append(f'   order: strategy.close("{od[1]}")  [blocked signal]')
                else:
                    lg.append(f'   order: strategy.close_all  [{od[1]}]')
        prev_position_size = position_size
        if i < n - 1:
            pending = orders                  # rule 5: orders placed on the last bar do not fill
        else:
            pending = []
    if T is not None:                         # rule 5: open at the end -> closed at the last close
        close_trade(n - 1, c[n - 1], 'end', -1)
        eq[-1] = cash
    return dict(trades=trades, cash=cash, eq=eq, npos=npos, cnt=cnt)


# ---------------------------------------------------------------------------------------------
# summary of the reference run, recomputed here from its own trade list and equity curve
# ---------------------------------------------------------------------------------------------
def ref_summary(Pp, rr):
    tr = rr['trades']
    pnl = np.array([t['gross'] - t['ecost'] - t['xcost'] for t in tr], float)
    gp = float(pnl[pnl > 0].sum()) if len(tr) else 0.0
    gl = float(-pnl[pnl < 0].sum()) if len(tr) else 0.0
    curve = np.concatenate([[INIT], np.array(rr['eq'], float)])
    peak = np.maximum.accumulate(curve)
    tc = Pp['t_close']
    to = Pp['t_open']
    mid = Pp['start'] + (Pp['end'] - Pp['start']) // 2
    j = int(np.searchsorted(tc, mid, side='right')) - 1
    eq_mid = rr['eq'][j] if j >= 0 else INIT
    g1 = g2 = 1.0
    n1 = 0
    for t, p in zip(tr, pnl):
        if int(to[t['ek']]) <= mid:
            g1 *= 1.0 + p / t['eqb']
            n1 += 1
        else:
            g2 *= 1.0 + p / t['eqb']
    kinds = {}
    for t in tr:
        kinds[t['kind']] = kinds.get(t['kind'], 0) + 1
    s = dict(
        trades=len(tr), net_pct=(rr['cash'] - INIT) / INIT * 100,
        pf=(gp / gl) if gl > 0 else (np.inf if gp > 0 else np.nan),
        win_pct=float((pnl > 0).mean() * 100) if len(tr) else np.nan,
        max_dd_pct=float(np.max((peak - curve) / peak) * 100),
        max_dd_init_pct=float(np.max(peak - curve) / INIT * 100),
        long=sum(1 for t in tr if t['d'] > 0), short=sum(1 for t in tr if t['d'] < 0),
        raw_long=rr['cnt']['raw_long'], raw_short=rr['cnt']['raw_short'],
        blocked_long=rr['cnt']['blocked_long'], blocked_short=rr['cnt']['blocked_short'],
        half1_pct=(eq_mid - INIT) / INIT * 100, half2_pct=(rr['cash'] - eq_mid) / INIT * 100,
        exposure=rr['npos'] / Pp['n'], final_equity=rr['cash'],
        zero_length=sum(1 for t in tr if t['ek'] == t['xk']),
        h1r_pct=(g1 - 1.0) * 100, h2r_pct=(g2 - 1.0) * 100, h1_trades=n1, h2_trades=len(tr) - n1,
        avg_bars_held=float(np.mean([t['xk'] - t['ek'] for t in tr])) if tr else np.nan,
        costs=float(sum(t['ecost'] + t['xcost'] for t in tr)),
    )
    for k in ('sl', 'tp', 'reverse', 'blocked_close', 'time', 'hybrid', 'end', 'trail'):
        s['exit_' + k] = kinds.get(k, 0)
    return s


# ---------------------------------------------------------------------------------------------
# comparison with the replica
# ---------------------------------------------------------------------------------------------
def feq(a, b, rtol=1e-9, atol=1e-9):
    an = a is None or (isinstance(a, float) and np.isnan(a))
    bn = b is None or (isinstance(b, float) and np.isnan(b))
    if an or bn:
        return an and bn
    if a == b:
        return True
    return abs(a - b) <= atol + rtol * max(abs(a), abs(b))


INT_SUMMARY = ('trades', 'long', 'short', 'raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'zero_length',
               'h1_trades', 'h2_trades', 'exit_sl', 'exit_tp', 'exit_reverse', 'exit_blocked_close', 'exit_time',
               'exit_hybrid', 'exit_end', 'exit_trail')
FLT_SUMMARY = ('net_pct', 'pf', 'win_pct', 'max_dd_pct', 'max_dd_init_pct', 'half1_pct', 'half2_pct', 'exposure',
               'final_equity', 'h1r_pct', 'h2r_pct', 'avg_bars_held', 'costs')
STAT = dict(px_exact=0, px_tol=0)


def replica_run(Pp, X):
    """The replica with the same settings, addressed by the Pine input names."""
    R = hrd.simulate(Pp, X)
    return hrd.trades_frame(Pp, R), hrd.summary_fast(Pp, R)


def compare(Pp, X, sub=None):
    tf, s = replica_run(Pp, X)
    rr = reference(Pp, X, sub)
    mine = rr['trades']
    w0 = Pp['w0']
    to = Pp['t_open']
    tc = Pp['t_close']
    msgs = []
    if len(tf) != len(mine):
        msgs.append(f'trade count replica {len(tf)} reference {len(mine)}')
    m = min(len(tf), len(mine))
    col = {k: tf[k].to_numpy() for k in ('dir', 'entry_bar', 'exit_bar', 'signal_bar', 'exit_order_bar', 'entry_px',
                                         'exit_px', 'qty', 'pnl', 'pnl_gross', 'costs', 'eq_before', 'sl_px',
                                         'tp_px', 'entry_time', 'exit_time')}
    kinds = tf['exit_kind'].tolist()
    for j in range(m):
        t = mine[j]
        xt = int(tc[t['xk']]) if t['kind'] == 'end' else int(to[t['xk']])
        xob = -1 if t['xob'] < 0 else t['xob'] + w0
        bad = []
        if int(col['dir'][j]) != t['d']:
            bad.append('dir')
        if int(col['entry_bar'][j]) - w0 != t['ek']:
            bad.append('entry_bar')
        if int(col['exit_bar'][j]) - w0 != t['xk']:
            bad.append('exit_bar')
        if int(col['signal_bar'][j]) - w0 != t['sk']:
            bad.append('signal_bar')
        if int(col['exit_order_bar'][j]) != xob:
            bad.append('exit_order_bar')
        if kinds[j] != t['kind']:
            bad.append('exit_kind')
        if int(col['entry_time'][j]) != int(to[t['ek']]) or int(col['exit_time'][j]) != xt:
            bad.append('times')
        if float(col['entry_px'][j]) != t['epx']:
            bad.append('entry_px')
        ex = float(col['exit_px'][j])
        if ex == t['xpx']:
            STAT['px_exact'] += 1
        elif feq(ex, t['xpx'], rtol=1e-12, atol=0.0):
            STAT['px_tol'] += 1
        else:
            bad.append('exit_px')
        for nm, v in (('sl_px', t['sl']), ('tp_px', t['tp'])):
            e = float(col[nm][j])
            if not ((v is None and np.isnan(e)) or (v is not None and e == v)):
                bad.append(nm)
        pnl = t['gross'] - t['ecost'] - t['xcost']
        if not feq(float(col['qty'][j]), t['qty']):
            bad.append('qty')
        if not feq(float(col['pnl'][j]), pnl, atol=1e-7):
            bad.append('pnl')
        if not feq(float(col['pnl_gross'][j]), t['gross'], atol=1e-7):
            bad.append('pnl_gross')
        if not feq(float(col['costs'][j]), t['ecost'] + t['xcost'], atol=1e-7):
            bad.append('costs')
        if not feq(float(col['eq_before'][j]), t['eqb']):
            bad.append('eq_before')
        if bad:
            msgs.append(f'first mismatch at trade {j} in {bad}: replica {tf.iloc[j].to_dict()} | reference dir '
                        f'{t["d"]} id {t["id"]} signal {t["sk"] + w0} entry {t["ek"] + w0} at {t["epx"]} exit '
                        f'{t["xk"] + w0} at {t["xpx"]} kind {t["kind"]} qty {t["qty"]} pnl {pnl} sl {t["sl"]} '
                        f'tp {t["tp"]} eq_before {t["eqb"]} exit_order_bar {xob}')
            break
    rs = ref_summary(Pp, rr)
    for k in INT_SUMMARY:
        if int(s[k]) != int(rs[k]):
            msgs.append(f'summary {k}: replica {s[k]} reference {rs[k]}')
    for k in FLT_SUMMARY:
        if not feq(float(s[k]), float(rs[k]), rtol=1e-9, atol=1e-7):
            msgs.append(f'summary {k}: replica {s[k]} reference {rs[k]}')
    return msgs, mine, rs


ACTS = [0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5]
OFFS = [0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5]

# (name, reverse, exit settings by Pine input name); the first is the script's defaults
NAMED = [
    ('default', False, {}),
    ('trail on (defaults 1.0 / 0.5)', False, dict(hrdTrailOn=True)),
    ('trail 0.1 / 0.05, target off', False, dict(hrdTrailOn=True, hrdTrailAct=0.1, hrdTrailOff=0.05, InpTpPct=0.0)),
    ('trail 0 / 0.2, 100 candles, hybrid off', False, dict(hrdTrailOn=True, hrdTrailAct=0.0, hrdTrailOff=0.2,
                                                         InpExitCandles=100, useHybridExit=False)),
    ('time exit 20, hybrid off', False, dict(InpExitCandles=20, useHybridExit=False)),
    ('SL 1 = TP 1, 100 candles', False, dict(InpSlPct=1.0, InpTpPct=1.0, InpExitCandles=100)),
    ('SL 0.5, TP 1.5, 100 candles, hybrid off', False, dict(InpSlPct=0.5, InpTpPct=1.5, InpExitCandles=100,
                                                          useHybridExit=False)),
    ('SL 0 (fixed qty 5), TP 1, 50 candles', False, dict(InpSlPct=0.0, InpFixedQty=5.0, InpTpPct=1.0,
                                                       InpExitCandles=50)),
    ('Buy Only', False, dict(InpTradeDirection='Buy Only')),
    ('Sell Only, 20 candles', False, dict(InpTradeDirection='Sell Only', InpExitCandles=20)),
    ('blocked close off, 20 candles', False, dict(hrdBlkClose=False, InpExitCandles=20)),
    ('Reverse Trading on', True, {}),
    ('Reverse Trading on, trail 0.3 / 0.1, 20 candles', True, dict(hrdTrailOn=True, hrdTrailAct=0.3,
                                                                  hrdTrailOff=0.1, InpExitCandles=20)),
]


def rand_setting(rng):
    X = {}
    X['hrdBlkClose'] = rng.random() < 0.7
    X['InpTradeDirection'] = rng.choice(['Both', 'Both', 'Both', 'Buy Only', 'Sell Only'])
    X['InpSlPct'] = rng.choice([2.0, 2.0, 1.0, 0.5, 0.3, 3.0, 0.0])
    X['InpTpPct'] = rng.choice([4.0, 4.0, 0.0, 0.5, 1.0, 2.0])
    X['InpExitCandles'] = rng.choice([5, 5, 20, 100, 1, 3, 40])
    X['useHybridExit'] = rng.random() < 0.6
    if rng.random() < 0.5:
        X['hybridSensitivity'] = rng.choice([0.5, 3.0, 20.0])
        X['minDecayUpdates'] = rng.choice([1, 3, 10])
        X['minActivationPts'] = rng.choice([10, 200, 1000])
        X['trailStepMult'] = rng.choice([1.0, 2.0, 10.0])
    if rng.random() < 0.3:
        X['InpRiskPct'] = rng.choice([0.5, 2.0])
        X['InpFixedQty'] = rng.choice([0.01, 1.0, 50.0])
    if rng.random() < 0.7:
        X.update(hrdTrailOn=True, hrdTrailAct=rng.choice(ACTS), hrdTrailOff=rng.choice(OFFS))
    return X


def run_check(ds, nrand=12, seed=1, quiet=False):
    pair, tf, st, en = DATASETS[ds]
    rng = random.Random(seed)
    settings = list(NAMED)
    for k in range(nrand):
        settings.append((f'random {k}', rng.random() < 0.25, rand_setting(rng)))
    t0 = time.time()
    preps = {}
    subs = {}
    for fon in (False, True):
        for rev in (False, True):
            prm = dict(fgfOn=fon, reverse=rev)
            if st is not None:
                prm.update(start=st, end=en)
            preps[(fon, rev)] = hrd.prepare(pair, tf, prm)
        Pp = preps[(fon, False)]
        subs[fon] = sub_bars(pair, Pp['t_open'], Pp['t_close'])
    Pa, Pb = preps[(True, False)], preps[(True, True)]
    if not quiet:
        Pp = preps[(False, False)]
        print(f'{ds}: {Pp["n"]} chart bars, {len(subs[False][2])} 1-minute sub-bars; filter on: buyOk on '
              f'{int(Pa["buy_ok"].sum())} bars, sellOk on {int(Pa["sell_ok"].sum())}, both on '
              f'{int((Pa["buy_ok"] & Pa["sell_ok"]).sum())}; LONG signals {int(Pp["long_sig"].sum())}, SHORT '
              f'{int(Pp["short_sig"].sum())}, both on one candle {int((Pp["long_sig"] & Pp["short_sig"]).sum())}; '
              f'prepared in {time.time() - t0:.1f}s', flush=True)
    costs = ('tv', 'ours', 'stress')
    tot = dict(runs=0, fail=0, trades=0, kinds={}, runs_inv=0, runs_off=0, fail_inv=0, fail_off=0, cov={})
    mid0 = module_id()
    if not quiet:
        print(f'{ds}: replica under test: {mid0}', flush=True)
    for si, (name, rev, X0) in enumerate(settings):
        cost_list = costs if si == 0 else (costs[si % 3],)
        for cost in cost_list:
            for fon in (False, True):
                for path in ('tv', 'mag'):
                    for inv in (True, False):
                        X = dict(X0, cost=cost, path=path, hrdInv=inv)
                        Pp = preps[(fon, rev)]
                        t1 = time.time()
                        msgs, mine, rs = compare(Pp, X, subs[fon] if path == 'mag' else None)
                        tot['runs'] += 1
                        tot['runs_inv' if inv else 'runs_off'] += 1
                        tot['trades'] += len(mine)
                        if inv:
                            for t in mine:
                                key = ('long ' if t['d'] > 0 else 'short ') + t['kind']
                                tot['kinds'][key] = tot['kinds'].get(key, 0) + 1
                        tag = (f'{ds} s{si:02d} [{name}] rev {int(rev)} filter {"on " if fon else "off"} {path:3s} '
                               f'{cost:6s} inv {"ON " if inv else "off"} {X0}')
                        if msgs:
                            tot['fail'] += 1
                            tot['fail_inv' if inv else 'fail_off'] += 1
                            print('FAIL', tag, flush=True)
                            for mm in msgs:
                                print('     ', mm, flush=True)
                        elif not quiet:
                            print(f'ok   {tag}: {len(mine)} trades (L {rs["long"]} / S {rs["short"]}), net '
                                  f'{rs["net_pct"]:.4f}% ({time.time() - t1:.2f}s)', flush=True)
    if module_id() != mid0:
        tot['fail'] += 1
        print('FAIL the replica file changed during the run', flush=True)
    if not quiet:
        print(f'{ds} TOTAL: {tot["runs"]} runs ({tot["runs_inv"]} option ON, {tot["runs_off"]} option off), failed '
              f'{tot["fail"]} (ON {tot["fail_inv"]}, off {tot["fail_off"]}), {tot["trades"]} trades compared, '
              f'{time.time() - t0:.1f}s', flush=True)
        print(f'{ds} inverted trades by real side and exit kind: {dict(sorted(tot["kinds"].items()))}', flush=True)
        print(f'{ds} exit prices: {STAT["px_exact"]} bit-equal, {STAT["px_tol"]} within 1e-12 relative', flush=True)
    return tot


# ---------------------------------------------------------------------------------------------
# saved runner output: out/inv_hrd_<PAIR>_<TF>.json against the reference
# ---------------------------------------------------------------------------------------------
def check_json(pair, tf):
    path = os.path.join(W, 'out', f'inv_hrd_{pair}_{tf}.json')
    d = json.load(open(path))
    preps = {}
    subs = {}
    bad = 0
    nrun = 0
    nval = 0
    for sec in ('runs', 'reference'):
        for name, v in d[sec].items():
            p = v['params']
            key = (bool(p['fgfOn']), bool(p['reverse']))
            if key not in preps:
                preps[key] = hrd.prepare(pair, tf, dict(fgfOn=key[0], reverse=key[1]))
            Pp = preps[key]
            if p['path'] == 'mag' and key[0] not in subs:
                subs[key[0]] = sub_bars(pair, Pp['t_open'], Pp['t_close'])
            X = dict(hrdInv=bool(p['hrdInv']), path=p['path'], cost=p['cost'])
            rr = reference(Pp, X, subs.get(key[0]) if p['path'] == 'mag' else None)
            rs = ref_summary(Pp, rr)
            nrun += 1
            diffs = []
            for k in INT_SUMMARY:
                jv = v['exits'][k[5:]] if k.startswith('exit_') else v[k]
                nval += 1
                if int(jv) != int(rs[k]):
                    diffs.append(f'{k}: file {jv} reference {rs[k]}')
            for k in FLT_SUMMARY:
                nval += 1
                if not feq(float(v[k]), float(rs[k]), rtol=1e-9, atol=1e-7):
                    diffs.append(f'{k}: file {v[k]} reference {rs[k]}')
            # the runner's derived fields, from the reference's trade list
            end_pct = sum(t['gross'] - t['ecost'] - t['xcost'] for t in rr['trades'] if t['kind'] == 'end') / INIT * 100
            for k, val in (('end_trade_pnl_pct', end_pct), ('net_closed_pct', rs['net_pct'] - end_pct),
                           ('avg_trade_pct', rs['net_pct'] / rs['trades'] if rs['trades'] else float('nan'))):
                nval += 1
                if not feq(float(v[k]), float(val), rtol=1e-9, atol=1e-9):
                    diffs.append(f'{k}: file {v[k]} reference {val}')
            want_dir = 'inverted' if p['hrdInv'] else 'normal'
            if v['direction'] != want_dir or v['filter'] != ('on' if p['fgfOn'] else 'off') or v['path'] != p['path']:
                diffs.append(f'labels {v["direction"]} / {v["filter"]} / {v["path"]} do not match params {p}')
            want_name = '_'.join(['inverted' if p['hrdInv'] else ('rev' if p['reverse'] else 'normal'),
                                  'on' if p['fgfOn'] else 'off', p['path'], {'tv': 'script', 'ours': 'ours'}[p['cost']]])
            if name != want_name or (p['hrdInv'] and p['reverse']):
                diffs.append(f'run name {name} does not match params {p} ({want_name})')
            if diffs:
                bad += 1
                print(f'FAIL {pair} {tf} {sec}.{name}:', '; '.join(diffs), flush=True)
            else:
                print(f'ok   {pair} {tf} {sec}.{name}: trades {rs["trades"]} (L {rs["long"]} / S {rs["short"]}) net '
                      f'{rs["net_pct"]:.6f}% pf {rs["pf"]:.4f} win {rs["win_pct"]:.2f}% maxDD '
                      f'{rs["max_dd_pct"]:.4f}%', flush=True)
    P0 = preps[(False, False)]
    nsub = len(sub_bars(pair, P0['t_open'], P0['t_close'])[2])
    if (d['window'] != [int(P0['start']), int(P0['end'])] or d['window'] != list(hrd.WINDOWS[pair])
            or d['bars'] != P0['n'] or d['sub_bars_1m'] != nsub or d['pair'] != pair or str(d['tf']) != str(tf)):
        bad += 1
        print('FAIL header', d['window'], d['bars'], d['sub_bars_1m'], 'reference', P0['start'], P0['end'], P0['n'], nsub)
    print(f'{pair} {tf} JSON: replica under test {module_id()}')
    print(f'{pair} {tf} JSON: {nrun} runs, {nval} values compared with the reference, {bad} runs differ', flush=True)
    return bad


# ---------------------------------------------------------------------------------------------
# hand traces
# ---------------------------------------------------------------------------------------------
def ts(x):
    return _dt.datetime.fromtimestamp(int(x), _dt.timezone.utc).strftime('%Y-%m-%d %H:%M')


def print_bars(Pp, a, b, log, mark=None):
    w0 = Pp['w0']
    for i in range(max(a, 0), min(b, Pp['n'] - 1) + 1):
        print(f'  bar {i + w0} {ts(Pp["t_open"][i])} UTC  O {Pp["o"][i]} H {Pp["h"][i]} L {Pp["l"][i]} C {Pp["c"][i]}'
              + (f'   <- {mark[i]}' if mark and i in mark else ''))
        for line in log.get(i, []):
            print('        ' + line)


def trace():
    """Hand traces of inverted trades: every bar from the signal candle to the exit, with what the
    script saw at each close, the orders it placed and the fills; the replica's row next to it."""
    def pick(kind, d=None, nth=0, held=True):
        def f(tr):
            cand = [k for k, t in enumerate(tr) if t['kind'] == kind and (d is None or t['d'] == d)
                    and (t['xk'] > t['ek'] if held else True)]
            cand.sort(key=lambda k: (tr[k]['xk'] - tr[k]['ek'], k))      # the shortest first
            return cand[nth] if len(cand) > nth else None
        return f

    def double_flat(tr):
        # the first entry of a candle that sent both entries while flat: closed at once by the second
        for k, t in enumerate(tr[:-1]):
            if t['kind'] == 'reverse' and t['xk'] == t['ek'] and tr[k + 1]['sk'] == t['sk']:
                return k
        return None

    cases = [
        ('1. FIRST ENTRY of the run (flat, a signal the filter allows, sent on the other side)', 'BTC', '60', True,
         {}, lambda tr: 0, 0),
        ('2. REVERSAL (an allowed LONG signal is a sell order: it reverses the open LONG)', 'BTC', '60', False,
         {}, pick('reverse', d=1), 1),
        ('3. BLOCKED-SIGNAL CLOSE (a LONG signal the filter blocks closes the open LONG)', 'XAU', '60', True,
         {}, pick('blocked_close', d=1), 1),
        ('4. STOP EXIT (a SELL placed for a LONG signal: its stop is ABOVE the signal close)', 'BTC', '60', True,
         {}, pick('sl', d=-1), 0),
        ('5a. TARGET EXIT (a SELL placed for a LONG signal: its target is BELOW the signal close)', 'BTC', '60',
         True, dict(InpExitCandles=20), pick('tp', d=-1), 0),
        ('5b. TRAILING EXIT, chart path (a SELL: the trail arms below the fill and follows the lows)', 'XAU', '240',
         True, dict(hrdTrailOn=True, hrdTrailAct=0.3, hrdTrailOff=0.15), pick('trail', d=-1, nth=1), 0),
        ('5c. TRAILING EXIT, 1-minute path (a BUY placed for a SHORT signal)', 'XAU', '60', True,
         dict(hrdTrailOn=True, hrdTrailAct=0.2, hrdTrailOff=0.1, path='mag'), pick('trail', d=1, nth=2), 0),
        ('6. BOTH SIGNALS ON ONE CANDLE WHILE FLAT (the header exception: both entries are sent, the BUY stays)',
         'BTC', '60', False, {}, double_flat, 1),
    ]
    n_equal = 0
    for title, pair, tf, fon, X0, picker, after in cases:
        Pp = hrd.prepare(pair, tf, dict(fgfOn=fon))
        X = dict(X0, hrdInv=True)
        sub = sub_bars(pair, Pp['t_open'], Pp['t_close']) if X.get('path') == 'mag' else None
        log = {}
        rr = reference(Pp, X, sub, log)
        tr = rr['trades']
        w0 = Pp['w0']
        j = picker(tr)
        print('=' * 118)
        print(title)
        if j is None:
            print('  no such trade in this run')
            continue
        t = tr[j]
        tfr, _ = replica_run(Pp, X)
        print(f'{pair} {tf}, filter {"on" if fon else "off"}, Inverted direction ON, settings '
              f'{X0 or "script defaults"}; trade #{j} of the run')
        sc = float(Pp['c'][t['sk']])
        side = 'SELL (short)' if t['d'] < 0 else 'BUY (long)'
        sig = 'LONG' if t['d'] < 0 else 'SHORT'
        print(f'  signal candle {t["sk"] + w0}: {sig} signal, close {sc}; placed as a {side}, id "{t["id"]}"')
        slp, tpp = PINE['InpSlPct'], PINE['InpTpPct']
        if t['d'] < 0:
            print(f'  by hand: stop = close x (1 + {slp}/100) = {sc * (1.0 + slp / 100.0)!r} (above), '
                  f'limit = close x (1 - {tpp}/100) = {sc * (1.0 - tpp / 100.0)!r} (below)')
        else:
            print(f'  by hand: stop = close x (1 - {slp}/100) = {sc * (1.0 - slp / 100.0)!r} (below), '
                  f'limit = close x (1 + {tpp}/100) = {sc * (1.0 + tpp / 100.0)!r} (above)')
        eqs = rr['eq'][t['sk']]
        print(f'  by hand: qty = strategy.equity at the signal close x 1% / (close x {slp}%) = {eqs:.4f} x 0.01 / '
              f'{sc * (slp / 100.0):.6f} = {eqs * 0.01 / (sc * (slp / 100.0)):.6f}')
        if X.get('hrdTrailOn'):
            pts = max(sc * X['hrdTrailAct'] / 100.0 / MINTICK, 0.0)
            ofs = max(sc * X['hrdTrailOff'] / 100.0 / MINTICK, 1.0)
            print(f'  by hand: trail_points = close x {X["hrdTrailAct"]}% / mintick = {pts:.4f} ticks -> activation = '
                  f'fill {"-" if t["d"] < 0 else "+"} {pts * MINTICK:.6f} = {t["epx"] + t["d"] * pts * MINTICK:.6f}; '
                  f'trail_offset = close x {X["hrdTrailOff"]}% / mintick = {ofs:.4f} ticks = {ofs * MINTICK:.6f}')
        mark = {t['sk']: 'signal candle', t['ek']: 'entry fills at this open', t['xk']: f'exit ({t["kind"]})'}
        if t['ek'] == t['xk']:
            mark[t['ek']] = f'entry fills at this open; exit ({t["kind"]})'
        print_bars(Pp, t['sk'] - 1, t['xk'] + after, log, mark)
        rows = [j] + ([j + 1] if title.startswith('6.') else [])
        same = True
        for jj in rows:
            u = tr[jj]
            pnl = u['gross'] - u['ecost'] - u['xcost']
            print(f'  REFERENCE trade #{jj}: dir {u["d"]:+d} entry bar {u["ek"] + w0} at {u["epx"]} qty {u["qty"]:.6f} '
                  f'-> exit bar {u["xk"] + w0} at {u["xpx"]} kind {u["kind"]}; P/L = {u["d"]:+d} x ({u["xpx"]} - '
                  f'{u["epx"]}) x qty = {pnl:.4f}')
            row = tfr.iloc[jj]
            print(f'  REPLICA   trade #{jj}: dir {int(row["dir"]):+d} entry bar {int(row["entry_bar"])} at '
                  f'{row["entry_px"]} qty {row["qty"]:.6f} -> exit bar {int(row["exit_bar"])} at {row["exit_px"]} kind '
                  f'{row["exit_kind"]}; P/L {row["pnl"]:.4f}; sl {row["sl_px"]} tp {row["tp_px"]}')
            same = same and (int(row['dir']) == u['d'] and int(row['entry_bar']) == u['ek'] + w0
                             and int(row['exit_bar']) == u['xk'] + w0 and row['exit_kind'] == u['kind']
                             and row['entry_px'] == u['epx'] and float(row['exit_px']) == u['xpx']
                             and feq(float(row['qty']), u['qty']) and feq(float(row['pnl']), pnl, atol=1e-7)
                             and (u['sl'] is None or float(row['sl_px']) == u['sl'])
                             and (u['tp'] is None or float(row['tp_px']) == u['tp']))
        print(f'  -> {"EQUAL" if same else "DIFFERENT"}')
        n_equal += same
    print('=' * 118)
    print(f'traces: {n_equal} of {len(cases)} equal to the replica')
    return n_equal == len(cases)


# ---------------------------------------------------------------------------------------------
# inputs taken from prepare(): what the reference relies on
# ---------------------------------------------------------------------------------------------
def check_inputs():
    bad = 0
    for ds, (pair, tf, st, en) in DATASETS.items():
        prm = {} if st is None else dict(start=st, end=en)
        a = hrd.prepare(pair, tf, dict(prm, fgfOn=True))
        b = hrd.prepare(pair, tf, dict(prm, fgfOn=True, reverse=True))
        f = hrd.prepare(pair, tf, dict(prm, fgfOn=False))
        g = hrd.prepare(pair, tf, dict(prm, fgfOn=True, hrdInv=True))
        raw = pq.read_table(os.path.join(W, 'data', f'{pair}_{tf}.parquet')).to_pandas()
        sl = slice(a['w0'], a['w1'])
        ok = dict(
            reverse_swaps_signals=bool((a['long_sig'] == b['short_sig']).all() and (a['short_sig'] == b['long_sig']).all()),
            reverse_keeps_permissions=bool((a['buy_ok'] == b['buy_ok']).all() and (a['sell_ok'] == b['sell_ok']).all()),
            filter_off_all_true=bool(f['buy_ok'].all() and f['sell_ok'].all()),
            filter_keeps_signals=bool((a['long_sig'] == f['long_sig']).all() and (a['short_sig'] == f['short_sig']).all()),
            inv_does_not_touch_inputs=bool((a['long_sig'] == g['long_sig']).all() and (a['short_sig'] == g['short_sig']).all()
                                           and (a['buy_ok'] == g['buy_ok']).all() and (a['sell_ok'] == g['sell_ok']).all()),
            ohlc_from_file=bool((raw['open'].to_numpy()[sl] == a['o']).all() and (raw['high'].to_numpy()[sl] == a['h']).all()
                                and (raw['low'].to_numpy()[sl] == a['l']).all() and (raw['close'].to_numpy()[sl] == a['c']).all()
                                and (raw['t_open'].to_numpy()[sl] == a['t_open']).all()),
            window=bool(raw['t_close'].to_numpy()[a['w0']] >= a['start'] and raw['t_close'].to_numpy()[a['w1'] - 1] <= a['end']
                        and (a['w0'] == 0 or raw['t_close'].to_numpy()[a['w0'] - 1] < a['start'])
                        and (a['w1'] == len(raw) or raw['t_close'].to_numpy()[a['w1']] > a['end'])),
        )
        sub = sub_bars(pair, a['t_open'], a['t_close'])
        lo, hi, O, H, L, C, _ = sub
        agg = 0
        for j in range(a['n']):
            if hi[j] <= lo[j] or O[lo[j]] != a['o'][j] or C[hi[j] - 1] != a['c'][j] \
                    or max(H[lo[j]:hi[j]]) != a['h'][j] or min(L[lo[j]:hi[j]]) != a['l'][j]:
                agg += 1
        ok['sub_bars_aggregate_to_chart_bars'] = agg == 0
        both = int((a['buy_ok'] & a['sell_ok']).sum())
        bad += sum(1 for v in ok.values() if not v)
        print(f'{ds}: window {a["start"]}..{a["end"]} bars {a["n"]}; buyOk and sellOk both true on {both} bars; '
              + ', '.join(f'{k} {"ok" if v else "FAIL"}' for k, v in ok.items()), flush=True)
    # the defaults the reference took from the Pine against the replica's
    alias = dict(hrdBlkClose='blkClose', hrdTrailOn='trailOn', hrdTrailAct='trailAct', hrdTrailOff='trailOff')
    dd = [k for k, v in PINE.items() if hrd.DEFAULTS.get(alias.get(k, k), hrd.DEFAULTS.get(k)) != v]
    print('Pine input defaults vs hrd.DEFAULTS:', 'equal' if not dd else f'DIFFERENT {dd}')
    return bad + len(dd)


def check_api():
    """The option addressed by its Pine name, by the alias, through prepare() and through run()
    gives the same replica trades (all equal to the reference); no key = option off."""
    bad = 0
    for pair, tf in (('BTC', '60'), ('XAU', '240')):
        for fon in (False, True):
            Pp = hrd.prepare(pair, tf, dict(fgfOn=fon))
            Pg = hrd.prepare(pair, tf, dict(fgfOn=fon, inv=True))
            Ph = hrd.prepare(pair, tf, dict(fgfOn=fon, hrdInv=True))
            a, sa = replica_run(Pp, dict(hrdInv=True))
            b, _ = replica_run(Pp, dict(inv=True))
            c, _ = replica_run(Pg, None)
            d, _ = replica_run(Ph, {})
            e, se = hrd.run(pair, tf, dict(fgfOn=fon, hrdInv=True))
            f, _ = replica_run(Pg, dict(inv=False))          # simulate() may switch it off again
            g, _ = replica_run(Pp, None)
            h, _ = replica_run(Pp, dict(hrdInv=False))
            msgs, mine, rs = compare(Pp, dict(hrdInv=True))
            ok = dict(alias=a.equals(b), prepare_alias=a.equals(c), prepare_name=a.equals(d), run=a.equals(e),
                      run_summary=(se['trades'] == rs['trades'] and se['long'] == rs['long']
                                   and se['short'] == rs['short'] and feq(se['net_pct'], rs['net_pct'])
                                   and se['raw_long'] == rs['raw_long'] and se['blocked_short'] == rs['blocked_short']
                                   and all(se['exits'][k[5:]] == rs[k] for k in rs if k.startswith('exit_'))),
                      off_again=f.equals(g), no_key_is_off=g.equals(h), on_differs_from_off=not a.equals(g),
                      reference=not msgs)
            bad += sum(1 for v in ok.values() if not v)
            print(f'{pair} {tf} filter {"on" if fon else "off"}: '
                  + ', '.join(f'{k} {"ok" if v else "FAIL"}' for k, v in ok.items()), flush=True)
    return bad


def check_chart1():
    """Chart "1": the 1-minute path is the chart path. Reference (tv) = replica tv = replica mag,
    option on and off, on a 3-week window per pair."""
    bad = 0
    for pair, st, en in (('BTC', 1772323200, 1774137600), ('XAU', 1519862400, 1521676800)):
        for fon in (False, True):
            Pp = hrd.prepare(pair, '1', dict(fgfOn=fon, start=st, end=en))
            sub = sub_bars(pair, Pp['t_open'], Pp['t_close'])
            for X0 in ({}, dict(hrdTrailOn=True, hrdTrailAct=0.1, hrdTrailOff=0.05, InpExitCandles=100),
                       dict(InpSlPct=0.2, InpTpPct=0.3, InpExitCandles=100, useHybridExit=False)):
                for inv in (True, False):
                    X = dict(X0, hrdInv=inv)
                    m1, mine, rs = compare(Pp, dict(X, path='tv'))
                    m2, _, _ = compare(Pp, dict(X, path='mag'), sub)
                    a, _ = replica_run(Pp, dict(X, path='tv'))
                    b, _ = replica_run(Pp, dict(X, path='mag'))
                    ok = (not m1) and (not m2) and a.equals(b)
                    bad += not ok
                    kinds = {}
                    for t in mine:
                        kinds[t['kind']] = kinds.get(t['kind'], 0) + 1
                    print(f'{"ok  " if ok else "FAIL"} {pair} 1 ({Pp["n"]} bars) filter {"on " if fon else "off"} inv '
                          f'{"ON " if inv else "off"} {X0}: {len(mine)} trades {dict(sorted(kinds.items()))}; '
                          f'reference = replica tv: {not m1}, reference(mag) = replica mag: {not m2}, replica mag = '
                          f'replica tv: {a.equals(b)}', flush=True)
                    for mm in m1 + m2:
                        print('     ', mm)
    return bad


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'check':
        tot = run_check(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12,
                        int(sys.argv[4]) if len(sys.argv) > 4 else 1)
        sys.exit(1 if tot['fail'] else 0)
    elif mode == 'json':
        sys.exit(1 if check_json(sys.argv[2], sys.argv[3]) else 0)
    elif mode == 'trace':
        sys.exit(0 if trace() else 1)
    elif mode == 'inputs':
        sys.exit(1 if check_inputs() else 0)
    elif mode == 'api':
        sys.exit(1 if check_api() else 0)
    elif mode == 'chart1':
        sys.exit(1 if check_chart1() else 0)
    elif mode == 'mutate':
        import io
        import contextlib
        for mut in ('pos_real', 'dir_not_swapped', 'gate_swapped', 'blk_wrong_id', 'px_not_mirrored', 'block_order',
                    'hybrid_frame'):
            MUT.clear()
            MUT.add(mut)
            res = []
            for ds in sys.argv[2:] or ['XAU240', 'BTC15']:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    tot = run_check(ds, 6, 3, quiet=True)
                res.append(f'{ds}: option ON {tot["fail_inv"]}/{tot["runs_inv"]} runs differ, option off '
                           f'{tot["fail_off"]}/{tot["runs_off"]}')
            print(f'mutation {mut:16s}: ' + '; '.join(res), flush=True)
        MUT.clear()
    else:
        print(__doc__)
