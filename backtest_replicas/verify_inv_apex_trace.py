"""verify_inv_apex_trace.py: hand traces of INVERTED trades (apxInv on) of the apex replica.

    python3 -I verify_inv_apex.py trace        (or: python3 -I verify_inv_apex_trace.py)

Each trace prints the chart bars that prove one trade and re-derives every number with plain
arithmetic written out here (the Pine's formulas on the printed bars), NOT with the walker of
verify_inv_apex.py or the replica's kernel; the result is then compared with the trade row of
the REPLICA (apex.simulate(..., inv=True)) and of the reference broker. Covered:
  1 a first entry (flat -> the BUY signal's SELL order / the SELL signal's BUY order)
  2 a reversal (the other kind of signal, allowed by the filter)
  3 a blocked-signal close (the other kind of signal, blocked: strategy.close on the mirror)
  4 a stop exit at the mirrored zone stop
  5 a target exit at the mirrored target
  6 a trailing exit (trailing take profit on, on the trade really open)
  7 a same-kind signal that re-sets the mirrored bracket (blocked by the filter or not)
All on the 'tv' path, cost 'tv' (0.04% per fill), so that the chart bars are the whole proof.
"""
import math
import os
import sys
import time

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import verify_inv_apex as V  # noqa: E402

TICK = 0.01
RATE = 0.0004
OK = [True]


def iso(t):
    return time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(t)))


def chk(cond, text):
    print(f'      [{"ok" if cond else "FAIL"}] {text}')
    if not cond:
        OK[0] = False


def near(a, b, rel=1e-9):
    return abs(a - b) <= rel * max(1.0, abs(b))


def setup(cell, fon, X):
    S = V.prep(cell, fon)
    ev = []
    trades, curve = V.ref_run(S, X, None, events=ev)
    E, es = V.eng_run(S, X)
    ok, msg, _ = V.compare_frames(V.ref_frame(S, trades), E)
    if not ok:
        print('   !! reference and replica differ on this run:', msg)
        OK[0] = False
    return S, trades, curve, E, ev


def show_bars(S, curve, a, b, marks=None):
    """Print window bars a..b (inclusive) with the script's inputs at each close."""
    d = S['diag']
    n = len(S['c'])
    a, b = max(a, 0), min(b, n - 1)
    print('      bar    t_open (UTC)         open       high        low      close  bull bear buyOk sellOk  '
          'pos@close  note')
    for i in range(a, b + 1):
        note = (marks or {}).get(i, '')
        print(f'      {i:5d}  {iso(S["t_open"][i])}  {S["o"][i]:10.2f} {S["h"][i]:10.2f} {S["l"][i]:10.2f} '
              f'{S["c"][i]:10.2f}  {int(d["bull"][i]):4d} {int(d["bear"][i]):4d} {int(S["buy_ok"][i]):5d} '
              f'{int(S["sell_ok"][i]):6d}  {curve["pos"][i]:+9d}  {note}')


def resonance(S, i):
    """Recompute bull / bear resonance of window bar i from the printed quantities (Pine lines
    FLOW PRESSURE DETECTION / RESONANCE CONFIRMATION)."""
    d = S['diag']
    P = S['P']
    o, h, l, c = float(S['o'][i]), float(S['h'][i]), float(S['l'][i]), float(S['c'][i])
    vol, vsma = float(d['volume'][i]), float(d['vol_sma'][i])
    body = abs(c - o) / (h - l) if h > l else float('nan')
    bull_flow = body >= P['minBodyStr'] and c > o and (c - l) / (h - l) > 0.65
    bear_flow = body >= P['minBodyStr'] and c < o and (h - c) / (h - l) > 0.65
    spike = vol > vsma * P['volMultiplier']
    dTop, dBot, sTop, sBot = (float(d[k][i]) for k in ('dTop', 'dBot', 'sTop', 'sBot'))
    htfL, htfH = float(d['htfLow'][i]), float(d['htfHigh'][i])
    bull = bull_flow and spike and not math.isnan(dBot) and l <= dTop and c > dBot and c > htfL
    bear = bear_flow and spike and not math.isnan(sTop) and h >= sBot and c < sTop and c < htfH
    print(f'      signal bar {i}: body strength {body:.4f} (min {P["minBodyStr"]}), close {"> " if c > o else "<= "}open, '
          f'(close-low)/(range) {(c - l) / (h - l):.4f}, (high-close)/(range) {(h - c) / (h - l):.4f}')
    print(f'        volume {vol:.4f} vs SMA20 x {P["volMultiplier"]} = {vsma * P["volMultiplier"]:.4f} -> spike {spike}')
    print(f'        demand box top {dTop:.4f} bottom {dBot:.4f} | supply box top {sTop:.4f} bottom {sBot:.4f} | '
          f'HTF low {htfL:.2f} high {htfH:.2f}')
    print(f'        -> bullResonance {bull}, bearResonance {bear}; fgfBuyOk {bool(S["buy_ok"][i])}, '
          f'fgfSellOk {bool(S["sell_ok"][i])}')
    chk(bull == bool(S['sig_l'][i]) and bear == bool(S['sig_s'][i]), 'recomputed resonance = the input signal arrays')
    return bull, bear


def bracket(S, i, kind):
    """The Pine's bracket of the signal on bar i (kind 'BUY' / 'SELL'), normal and mirrored."""
    d = S['diag']
    c = float(S['c'][i])
    rr = float(S['P']['rrRatio'])
    if kind == 'BUY':
        stopPrice = float(d['dBot'][i]) * 0.995
        targetPrice = c + (c - stopPrice) * rr
    else:
        stopPrice = float(d['sTop'][i]) * 1.005
        targetPrice = c - (stopPrice - c) * rr
    ms, mt = 2.0 * c - stopPrice, 2.0 * c - targetPrice
    print(f'        {kind} block on bar {i}: close {c}, normal stopPrice {stopPrice:.6f}, targetPrice {targetPrice:.6f} '
          f'(rr {rr})')
    print(f'        inverted: stop = 2 x close - stopPrice = {ms:.6f}, target = 2 x close - targetPrice = {mt:.6f} '
          f'(distances {abs(ms - c):.6f} / {abs(mt - c):.6f} = normal {abs(c - stopPrice):.6f} / {abs(targetPrice - c):.6f})')
    return stopPrice, targetPrice, ms, mt


def head(n, title, cell, fon, X):
    print()
    print(f'=== TRACE {n}: {title}')
    print(f'    {cell}, filter {"ON" if fon else "OFF"}, apxInv ON, path tv, cost tv, trailOn {X["trailOn"]}'
          + (f' (act {X["trailAct"]}% off {X["trailOff"]}%, keep target {X["useTarget"]})' if X['trailOn'] else '')
          + f', blkClose {X["blkClose"]}')


def row_check(t, e, w0):
    chk(int(e['dir']) == t['dir'] and int(e['entry_bar']) == t['entry_bar'] + w0
        and int(e['exit_bar']) == t['exit_bar'] + w0 and int(e['signal_bar']) == t['signal_bar'] + w0
        and str(e['exit_kind']) == t['exit_kind'] and float(e['entry_px']) == t['epx']
        and float(e['exit_px']) == t['exit_px'] and near(float(e['qty']), t['qty']) and near(float(e['pnl']), t['pnl']),
        f'replica row: dir {int(e["dir"]):+d}, entry bar {int(e["entry_bar"]) - w0} @ {float(e["entry_px"])}, '
        f'exit bar {int(e["exit_bar"]) - w0} @ {float(e["exit_px"])} kind {e["exit_kind"]}, qty {float(e["qty"]):.8f}, '
        f'pnl {float(e["pnl"]):.6f}  == reference row')


def explain_entry(S, t, curve, prev_closed):
    """The entry of trade t from its signal bar: order side, fill, quantity."""
    sb, eb = t['signal_bar'], t['entry_bar']
    bull, bear = resonance(S, sb)
    kind = 'BUY' if bull else 'SELL'
    ok_ = bool(S['buy_ok'][sb]) if bull else bool(S['sell_ok'][sb])
    chk(ok_, f'the filter allows the {kind} signal (apxGo{"Long" if bull else "Short"} true)')
    want = -1 if bull else 1
    print(f'        apxInv on: the {kind} signal places strategy.entry("{"Apex Short" if bull else "Apex Long"}", '
          f'{"strategy.short" if bull else "strategy.long"}) -> a real {"SHORT" if want < 0 else "LONG"}')
    chk(t['dir'] == want, f'trade side {t["dir"]:+d} is OPPOSITE to the {kind} signal')
    chk(eb == sb + 1 and t['epx'] == float(S['o'][eb]), f'filled at the next open: bar {eb} open {float(S["o"][eb])}')
    chk(t['signal_kind'] == kind, 'reference signal kind agrees')
    return kind


def pnl_check(t):
    ecost = RATE * t['epx'] * t['qty']
    xcost = RATE * t['exit_px'] * t['qty']
    pnl = t['dir'] * (t['exit_px'] - t['epx']) * t['qty'] - ecost - xcost
    print(f'        P/L = {t["dir"]:+d} x ({t["exit_px"]} - {t["epx"]}) x {t["qty"]:.8f} - {ecost:.6f} - {xcost:.6f} = {pnl:.6f}')
    chk(near(pnl, t['pnl']) and near(ecost, t['ecost']) and near(xcost, t['exit_cost']), 'P/L and both commissions (0.04% of each fill value)')


def resends(ev, t):
    """strategy.exit calls for this trade's entry id placed while it was open (after the signal bar)."""
    return [e for e in ev if e[1] == 'exit' and e[3] == t['id'] and t['signal_bar'] < e[0] < t['exit_bar']]


def level_walk(S, t, stop, limit):
    """Plain bar-by-bar check of a fixed bracket on the tv path. Returns (bar, price, kind)."""
    for i in range(t['entry_bar'], len(S['c'])):
        r = level_walk_one(t['dir'], float(S['o'][i]), float(S['h'][i]), float(S['l'][i]), stop, limit)
        if r is not None:
            return (i,) + r
    return None


def pick(trades, ev, cond):
    for j, t in enumerate(trades):
        if cond(j, t):
            return j
    return None


DEF = dict(inv=True, trailOn=False, trailAct=1.0, trailOff=0.5, useTarget=True, blkClose=True, cost='tv', path='tv')


def trace_first_entry(n, cell, fon):
    X = dict(DEF)
    head(n, 'a FIRST ENTRY (flat since the window start)', cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)
    t, e = trades[0], E.iloc[0]
    sb, eb = t['signal_bar'], t['entry_bar']
    chk(all(p == 0 for p in curve['pos'][:sb + 1]), f'flat on every bar up to the signal bar {sb} (apxPosN = 0)')
    first_sig = next(i for i in range(len(S['c'])) if (S['sig_l'][i] and S['buy_ok'][i]) or (S['sig_s'][i] and S['sell_ok'][i]))
    chk(first_sig == sb, f'bar {sb} is the first signal of the window that the filter allows')
    show_bars(S, curve, sb - 2, eb + 1, {sb: '<- signal', eb: '<- fill at the open'})
    kind = explain_entry(S, t, curve, 0.0)
    q = 0.01 * V.INIT / float(S['c'][sb])
    print(f'        quantity = 1% x equity 1,000,000 / close {float(S["c"][sb])} = {q:.8f}')
    chk(near(q, t['qty']) and near(q, float(e['qty'])), 'quantity of the replica and of the reference')
    stopPrice, targetPrice, ms, mt = bracket(S, sb, kind)
    x = ev_exit(ev, sb)
    chk(x is not None and x[4] == ms and x[5] == mt and x[3] == t['id'],
        f'strategy.exit("{x[2]}", "{x[3]}") sent on the signal bar with the mirrored stop / target')
    chk((ms > float(S['c'][sb]) > mt) if t['dir'] < 0 else (ms < float(S['c'][sb]) < mt),
        'the mirrored stop is on the losing side of the real trade, the mirrored target on the winning side')
    r = level_walk(S, t, ms, mt) if not resends(ev, t) else None
    print(f'        the trade ended: bar {t["exit_bar"]} at {t["exit_px"]} ({t["exit_kind"]})')
    if t['exit_kind'] in ('sl', 'tp') and r is not None:
        chk(r == (t['exit_bar'], t['exit_px'], t['exit_kind']),
            f'plain bar walk of that bracket: bar {r[0]} at {r[1]} ({r[2]})')
    elif r is not None:
        chk(r[0] >= t['exit_bar'], f'no level of that bracket is touched before bar {t["exit_bar"]} (first touch would be bar {r[0]})')
    pnl_check(t)
    row_check(t, e, S['w0'])


def ev_exit(ev, bar):
    for x in ev:
        if x[0] == bar and x[1] == 'exit':
            return x
    return None


def trace_reversal(n, cell, fon):
    X = dict(DEF)
    head(n, 'a REVERSAL (the other kind of signal, allowed)', cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)
    j = pick(trades, ev, lambda j, t: t['exit_kind'] == 'reverse' and j + 1 < len(trades) and j >= 1
             and t['exit_bar'] - t['entry_bar'] <= 30)
    t, e, t2, e2 = trades[j], E.iloc[j], trades[j + 1], E.iloc[j + 1]
    rb = t['exit_bar'] - 1
    print(f'    trade #{j}: real {"LONG" if t["dir"] > 0 else "SHORT"} opened by the {t["signal_kind"]} signal of bar '
          f'{t["signal_bar"]}, entry bar {t["entry_bar"]} @ {t["epx"]}')
    show_bars(S, curve, rb - 2, rb + 2, {rb: '<- the other signal', rb + 1: '<- reversal fill at the open'})
    bull, bear = resonance(S, rb)
    kind = 'BUY' if bull else 'SELL'
    chk(kind != t['signal_kind'], f'bar {rb} carries the OTHER kind of signal ({kind}) than the one that opened the trade')
    chk(bool(S['buy_ok'][rb]) if bull else bool(S['sell_ok'][rb]), f'the filter allows that {kind} signal')
    posN = -curve['pos'][rb]
    print(f'        real position at that close {curve["pos"][rb]:+d} -> apxPosN = {posN:+d} (the mirror)')
    print(f'        the {kind} signal places strategy.entry("{"Apex Short" if bull else "Apex Long"}", '
          f'{"short" if bull else "long"}): opposite to the open {"long" if t["dir"] > 0 else "short"} -> reversal')
    chk(t['exit_bar'] == rb + 1 and t['exit_px'] == float(S['o'][rb + 1]), f'old trade closed at bar {rb + 1} open {float(S["o"][rb + 1])}')
    chk(t2['entry_bar'] == rb + 1 and t2['epx'] == t['exit_px'] and t2['dir'] == -t['dir'] and t2['signal_bar'] == rb,
        f'new trade: real {"LONG" if t2["dir"] > 0 else "SHORT"} from the same fill')
    chk(t2['dir'] == (-1 if bull else 1), 'the new trade is opposite to its own signal')
    closed_before = sum(x['pnl'] for x in trades[:j])
    eq = V.INIT + closed_before + t['dir'] * (float(S['c'][rb]) - t['epx']) * t['qty'] - t['ecost']
    q = 0.01 * eq / float(S['c'][rb])
    print(f'        new quantity = 1% x equity at the signal close / close = 0.01 x {eq:.4f} / {float(S["c"][rb])} = {q:.8f}')
    print(f'          (equity = 1,000,000 + closed {closed_before:.4f} + open {t["dir"] * (float(S["c"][rb]) - t["epx"]) * t["qty"]:.4f}'
          f' - entry commission {t["ecost"]:.4f})')
    chk(near(q, t2['qty']) and near(q, float(e2['qty'])), 'quantity of the new trade (replica and reference)')
    stopPrice, targetPrice, ms, mt = bracket(S, rb, kind)
    x = ev_exit(ev, rb)
    chk(x is not None and x[4] == ms and x[5] == mt and x[3] == t2['id'], f'strategy.exit("{x[2]}", "{x[3]}") with the mirrored bracket')
    pnl_check(t)
    row_check(t, e, S['w0'])
    row_check(t2, e2, S['w0'])


def trace_blocked(n, cell, fon):
    X = dict(DEF)
    head(n, 'a BLOCKED-SIGNAL CLOSE (the other kind of signal, blocked by the filter)', cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)
    j = pick(trades, ev, lambda j, t: t['exit_kind'] == 'blocked_close' and t['exit_bar'] - t['entry_bar'] <= 40)
    t, e = trades[j], E.iloc[j]
    bb = t['exit_bar'] - 1
    print(f'    trade #{j}: real {"LONG" if t["dir"] > 0 else "SHORT"} opened by the {t["signal_kind"]} signal of bar '
          f'{t["signal_bar"]}, entry bar {t["entry_bar"]} @ {t["epx"]}')
    show_bars(S, curve, bb - 2, bb + 2, {bb: '<- blocked signal', bb + 1: '<- close fills at the open'})
    bull, bear = resonance(S, bb)
    kind = 'BUY' if bull else 'SELL'
    chk(kind != t['signal_kind'], f'bar {bb} carries the OTHER kind of signal ({kind})')
    blocked = (bull and not S['buy_ok'][bb]) or (bear and not S['sell_ok'][bb])
    chk(bool(blocked), f'the filter blocks it (apxBlk{"Long" if bull else "Short"} true): no entry')
    posN = -curve['pos'][bb]
    print(f'        real position {curve["pos"][bb]:+d} -> apxPosN = {posN:+d}; rule: apxBlkClose and '
          + ('apxBlkShort and apxPosN > 0 -> strategy.close(apxIdBuy)' if bear else 'apxBlkLong and apxPosN < 0 -> strategy.close(apxIdSell)'))
    chk((bear and posN > 0) or (bull and posN < 0), 'the rule fires on the MIRRORED position')
    x = [z for z in ev if z[0] == bb and z[1] == 'close']
    chk(len(x) == 1 and x[0][2] == t['id'], f'strategy.close("{t["id"]}") = the trade really open')
    chk(t['exit_bar'] == bb + 1 and t['exit_px'] == float(S['o'][bb + 1]), f'closed at bar {bb + 1} open {float(S["o"][bb + 1])}')
    chk(curve['pos'][bb + 1] == 0 or (j + 1 < len(trades) and trades[j + 1]['entry_bar'] > bb + 1),
        'nothing is opened by the blocked signal (flat after the close fill)')
    chk(not any(z[0] == bb and z[1] == 'exit' for z in ev), 'no strategy.exit is sent for the blocked other-kind signal')
    pnl_check(t)
    row_check(t, e, S['w0'])


def trace_level(n, cell, fon, kind_wanted, title):
    X = dict(DEF)
    head(n, title, cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)
    j = pick(trades, ev, lambda j, t: t['exit_kind'] == kind_wanted and not resends(ev, t)
             and 2 <= t['exit_bar'] - t['entry_bar'] <= 14 and t['exit_px'] != float(S['o'][t['exit_bar']]))
    t, e = trades[j], E.iloc[j]
    sb, eb, xb = t['signal_bar'], t['entry_bar'], t['exit_bar']
    print(f'    trade #{j}')
    show_bars(S, curve, sb - 1, xb + 1, {sb: '<- signal', eb: '<- fill at the open', xb: f'<- exit ({kind_wanted})'})
    kind = explain_entry(S, t, curve, 0.0)
    stopPrice, targetPrice, ms, mt = bracket(S, sb, kind)
    chk(not resends(ev, t), 'no same-kind signal re-sets the bracket while the trade is open')
    d = t['dir']
    for i in range(eb, xb):
        h, l = float(S['h'][i]), float(S['l'][i])
        if d < 0:
            good = h < ms and l > mt
            print(f'        bar {i}: high {h} < stop {ms:.6f} and low {l} > target {mt:.6f}: {good}')
        else:
            good = l > ms and h < mt
            print(f'        bar {i}: low {l} > stop {ms:.6f} and high {h} < target {mt:.6f}: {good}')
        chk(good, f'bar {i} touches neither level')
    o, h, l, c = (float(S[k][xb]) for k in ('o', 'h', 'l', 'c'))
    path = 'open -> high -> low -> close' if (h - o) < (o - l) else 'open -> low -> high -> close'
    print(f'        exit bar {xb}: O {o} H {h} L {l} C {c}; (high-open) {h - o:.2f} {"<" if (h - o) < (o - l) else ">="} '
          f'(open-low) {o - l:.2f} -> path {path}')
    r = level_walk(S, t, ms, mt)
    lvl = ms if kind_wanted == 'sl' else mt
    print(f'        plain bar walk: first level touched = {r[2]} at {r[1]:.6f} on bar {r[0]}')
    chk(r is not None and r[0] == xb and r[2] == kind_wanted and r[1] == t['exit_px'] and t['exit_px'] == lvl,
        f'exit at the mirrored {"stop" if kind_wanted == "sl" else "target"} {lvl:.6f} on bar {xb}')
    if kind_wanted == 'sl':
        print(f'        (the NORMAL trade of this signal would have had its stop at {stopPrice:.6f} and target at {targetPrice:.6f})')
    pnl_check(t)
    row_check(t, e, S['w0'])


def trace_trail(n, cell, fon):
    X = dict(DEF, trailOn=True, trailAct=0.5, trailOff=0.2, useTarget=True)
    head(n, 'a TRAILING exit (the trail follows the trade really open)', cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)
    j = pick(trades, ev, lambda j, t: t['exit_kind'] == 'trail' and not resends(ev, t)
             and 3 <= t['exit_bar'] - t['entry_bar'] <= 10 and t['exit_px'] != float(S['o'][t['exit_bar']]))
    t, e = trades[j], E.iloc[j]
    sb, eb, xb = t['signal_bar'], t['entry_bar'], t['exit_bar']
    print(f'    trade #{j}')
    show_bars(S, curve, sb - 1, xb + 1, {sb: '<- signal', eb: '<- fill at the open', xb: '<- exit (trail)'})
    kind = explain_entry(S, t, curve, 0.0)
    stopPrice, targetPrice, ms, mt = bracket(S, sb, kind)
    c = float(S['c'][sb])
    pts = max(c * X['trailAct'] / 100.0 / TICK, 0.0)
    ofs = max(c * X['trailOff'] / 100.0 / TICK, 1.0)
    d = t['dir']
    act = t['epx'] + d * pts * TICK
    print(f'        apxPosN <= 0 on the signal bar (new trade): apxTrPts{"L" if kind == "BUY" else "S"} = close x {X["trailAct"]} / 100 / 0.01 '
          f'= {pts:.4f} ticks, apxTrOfs = close x {X["trailOff"]} / 100 / 0.01 = {ofs:.4f} ticks')
    print(f'        real {"SHORT" if d < 0 else "LONG"}: activation = entry {t["epx"]} {"-" if d < 0 else "+"} {pts * TICK:.6f} = {act:.6f}; '
          f'trailing stop = best {"low + " if d < 0 else "high - "}{ofs * TICK:.6f}')
    chk(near(pts, t['pts_ticks']) and near(ofs, t['ofs_ticks']) and near(act, t['act_px']), 'distances and activation of the reference trade')
    # plain walk of the trailing stop along the tv path, written out for this one trade
    armed, best, res = False, float('nan'), None

    def beyond_stop(p, lvl):          # price p at / beyond a stop level of the real trade
        return p >= lvl if d < 0 else p <= lvl

    def beyond_limit(p, lvl):
        return p <= lvl if d < 0 else p >= lvl

    def state(i, p):
        nonlocal armed, best
        if not armed:
            if (p <= act + 1e-9) if d < 0 else (p >= act - 1e-9):
                armed, best = True, p
                print(f'        bar {i}: price reaches {p} -> ARMED (activation {act:.6f}); best {best}, '
                      f'trail stop {best - d * ofs * TICK:.6f}')
        elif (p < best) if d < 0 else (p > best):
            best = p
            print(f'        bar {i}: new best {best} -> trail stop {best - d * ofs * TICK:.6f}')

    for i in range(eb, xb + 1):
        o, h, l, cc = (float(S[k][i]) for k in ('o', 'h', 'l', 'c'))
        pts4 = (o, h, l, cc) if (h - o) < (o - l) else (o, l, h, cc)
        print(f'        bar {i}: path {pts4}')
        for k, p in enumerate(pts4):
            if k == 0:                                   # the open: state, then levels already beyond
                state(i, p)
                ts = best - d * ofs * TICK if armed else float('nan')
                if armed and beyond_stop(p, ts - d * 1e-9):
                    res = (i, p, 'trail')
                elif beyond_stop(p, ms):
                    res = (i, p, 'sl')
                elif beyond_limit(p, mt):
                    res = (i, p, 'tp')
            else:
                prev = pts4[k - 1]
                if p == prev:
                    continue
                favourable = (p < prev) if d < 0 else (p > prev)
                if favourable:                           # towards the target: the limit, then the state
                    if beyond_limit(p, mt):
                        res = (i, mt, 'tp')
                    else:
                        state(i, p)
                else:                                    # against the trade: the nearer stop fills first
                    ts = best - d * ofs * TICK if armed else float('nan')
                    hit_t = armed and beyond_stop(p, ts - d * 1e-9)
                    hit_z = beyond_stop(p, ms)
                    if hit_t and (not hit_z or (ts <= ms if d < 0 else ts >= ms)):
                        res = (i, ts, 'trail')
                    elif hit_z:
                        res = (i, ms, 'sl')
            if res is not None:
                break
        if res is not None:
            break
    print(f'        plain walk result: {res}')
    chk(res is not None and res[0] == xb and res[2] == 'trail' and near(res[1], t['exit_px']),
        f'trailing stop filled on bar {xb} at best {best} {"+" if d < 0 else "-"} {ofs * TICK:.6f} = {best - d * ofs * TICK:.6f}')
    chk((t['exit_px'] < ms and t['exit_px'] > mt) if d < 0 else (t['exit_px'] > ms and t['exit_px'] < mt),
        f'between the mirrored target {mt:.6f} and the mirrored zone stop {ms:.6f} (neither was reached first)')
    pnl_check(t)
    row_check(t, e, S['w0'])


def trace_resend(n, cell, fon, blocked):
    X = dict(DEF)
    head(n, 'a same-kind signal RE-SETS the mirrored bracket' + (' although the filter blocks it' if blocked else ''), cell, fon, X)
    S, trades, curve, E, ev = setup(cell, fon, X)

    def cond(j, t):
        rs = resends(ev, t)
        if len(rs) != 1 or t['exit_kind'] not in ('sl', 'tp') or t['exit_bar'] - t['entry_bar'] > 40:
            return False
        rb = rs[0][0]
        isblk = not (S['buy_ok'][rb] if t['signal_kind'] == 'BUY' else S['sell_ok'][rb])
        return bool(isblk) == blocked and t['exit_px'] != float(S['o'][t['exit_bar']])
    j = pick(trades, ev, cond)
    if j is None:
        print('    (no such trade in this run)')
        return
    t, e = trades[j], E.iloc[j]
    sb, eb, xb = t['signal_bar'], t['entry_bar'], t['exit_bar']
    x = resends(ev, t)[0]
    rb = x[0]
    print(f'    trade #{j}: real {"LONG" if t["dir"] > 0 else "SHORT"} opened by the {t["signal_kind"]} signal of bar {sb}')
    show_bars(S, curve, sb - 1, xb + 1, {sb: '<- signal', eb: '<- fill at the open', rb: '<- same-kind signal again',
                                         xb: f'<- exit ({t["exit_kind"]})'})
    kind = t['signal_kind']
    s0 = bracket(S, sb, kind)
    bull, bear = resonance(S, rb)
    chk(('BUY' if bull else 'SELL') == kind, f'bar {rb}: the same kind of signal ({kind}) while holding its trade')
    gate = bool(S['buy_ok'][rb]) if bull else bool(S['sell_ok'][rb])
    posN = -curve['pos'][rb]
    print(f'        filter allows it: {gate}; real position {curve["pos"][rb]:+d} -> apxPosN {posN:+d}; rule: '
          + ('apxGoLong or (bullResonance and apxPosN > 0)' if bull else 'apxGoShort or (bearResonance and apxPosN < 0)'))
    chk((posN > 0) if bull else (posN < 0), 'the re-send fires on the mirrored position')
    s1 = bracket(S, rb, kind)
    chk(x[4] == s1[2] and x[5] == s1[3] and x[3] == t['id'], f'strategy.exit("{x[2]}", "{x[3]}") re-sent with the mirrored bracket of bar {rb}')
    # plain walk: old bracket up to and including bar rb, the new one from bar rb+1
    d = t['dir']
    res = None
    for i in range(eb, len(S['c'])):
        ms, mt = (s0[2], s0[3]) if i <= rb else (s1[2], s1[3])
        o, h, l, c = (float(S[k][i]) for k in ('o', 'h', 'l', 'c'))
        r = level_walk_one(d, o, h, l, ms, mt)
        if r is not None:
            res = (i,) + r
            break
    print(f'        plain bar walk (bracket of bar {sb} through bar {rb}, of bar {rb} from bar {rb + 1}): {res}')
    chk(res is not None and res[0] == xb and res[1] == t['exit_px'] and res[2] == t['exit_kind'],
        f'exit on bar {xb} at {t["exit_px"]} ({t["exit_kind"]}) = the bracket in force')
    chk(xb <= rb or t['exit_px'] in (s1[2], s1[3]), 'after the re-send the level hit is the NEW mirrored one' if xb > rb else 'exit before the re-send')
    pnl_check(t)
    row_check(t, e, S['w0'])


def level_walk_one(d, o, h, l, stop, limit):
    if d < 0:
        if o >= stop:
            return o, 'sl'
        if o <= limit:
            return o, 'tp'
        up_first = (h - o) < (o - l)
        hs, hl = h >= stop, l <= limit
        if hs and hl:
            return (stop, 'sl') if up_first else (limit, 'tp')
        if hs:
            return stop, 'sl'
        if hl:
            return limit, 'tp'
    else:
        if o <= stop:
            return o, 'sl'
        if o >= limit:
            return o, 'tp'
        up_first = (h - o) < (o - l)
        hs, hl = l <= stop, h >= limit
        if hs and hl:
            return (limit, 'tp') if up_first else (stop, 'sl')
        if hs:
            return stop, 'sl'
        if hl:
            return limit, 'tp'
    return None


def main():
    trace_first_entry(1, 'BTC_60', True)
    trace_first_entry('1b', 'XAU_240', False)
    trace_reversal(2, 'BTC_60', False)
    trace_reversal('2b', 'XAU_60', True)
    trace_blocked(3, 'BTC_60', True)
    trace_blocked('3b', 'XAU_60', True)
    trace_level(4, 'BTC_60', False, 'sl', 'a STOP exit at the mirrored zone stop')
    trace_level('4b', 'BTC_15', True, 'sl', 'a STOP exit at the mirrored zone stop')
    trace_level(5, 'BTC_60', False, 'tp', 'a TARGET exit at the mirrored target')
    trace_trail(6, 'BTC_60', True)
    trace_trail('6b', 'XAU_60', False)
    trace_resend(7, 'BTC_60', False, False)
    trace_resend('7b', 'BTC_15', True, True)
    print()
    print('TRACE ' + ('PASS: every check ok' if OK[0] else 'FAIL'))
    return OK[0]


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
