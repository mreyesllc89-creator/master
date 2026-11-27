"""Hand traces of 5 trailing exits of apex.py (engine trades), re-derived from the raw
parquet rows (chart bars and 1-minute sub-bars read here with pandas) with a deliberately
simple step-by-step walk that prints every (sub-)bar it uses.

    python3 -I verify_trail_apex.py trace      (or python3 -I verify_trail_apex_trace.py)

Each trace prints: the signal bar (raw OHLC, the Pine tick formulas on its close), the
entry fill (next open), activation price and offset, every exit (re-)send with its zone
stop / target, one line per chart bar of the trade, and the 1-minute sub-bars of the arming
bar and of the exit bar (mag) with the trailing state after each, then checks the engine's
exit bar / price / kind / pnl against the trace.
"""
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402
import verify_trail_apex as V  # noqa: E402

TICK = 0.01
_RAW = {}


def raw(pair, tf):
    if (pair, tf) not in _RAW:
        _RAW[(pair, tf)] = pd.read_parquet(os.path.join(W, 'data', f'{pair}_{tf}.parquet'),
                                           columns=['open', 'high', 'low', 'close', 't_open', 't_close'])
    return _RAW[(pair, tf)]


def ts(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime('%Y-%m-%d %H:%M')


def subbars(pair, t_open, t_close):
    m = raw(pair, '1')
    a = np.searchsorted(m['t_open'].to_numpy(), t_open, 'left')
    b = np.searchsorted(m['t_open'].to_numpy(), t_close, 'left')
    return m.iloc[a:b]


def path_of(o, h, l, c):
    return ('O-H-L-C', (o, h, l, c)) if (h - o) < (o - l) else ('O-L-H-C', (o, l, h, c))


def trace(title, cell, S, X, row, out_lines, show_all_sub=False):
    """Re-derive the engine trade `row` (a trades_frame row) by hand. Returns True if equal."""
    P = print
    pair, tf = S['pair'], S['tf']
    cb = raw(pair, tf)
    d = int(row['dir'])
    sb, eb, xb = int(row['signal_bar']), int(row['entry_bar']), int(row['exit_bar'])
    w0 = S['w0']
    sig = cb.iloc[sb]
    act, off = X['trailAct'], X['trailOff']
    pts = max(sig.close * act / 100.0 / TICK, 0.0)
    ofs = max(sig.close * off / 100.0 / TICK, 1.0)
    fill = cb.iloc[eb].open
    act_px = fill + d * pts * TICK
    ofs_px = ofs * TICK
    P(f'\n=== {title}')
    P(f'cell {cell} path {X["path"]} filter {"on" if S["P"]["fgfOn"] else "off"} labels '
      f'{"rev" if S["P"]["reverse"] else "normal"} cost {X["cost"]} | trailAct {act}% trailOff {off}% '
      f'useTarget {X["useTarget"]}')
    side = 'long' if d > 0 else 'short'
    sigarr = S['sig_l'] if d > 0 else S['sig_s']
    okarr = S['buy_ok'] if d > 0 else S['sell_ok']
    P(f'signal bar row {sb} [{ts(sig.t_open)}] O {sig.open} H {sig.high} L {sig.low} C {sig.close}: '
      f'{side} signal {bool(sigarr[sb - w0])}, filter ok {bool(okarr[sb - w0])}')
    P(f'  trail_points = max(C x {act}/100 / 0.01, 0) = {pts:.6f} ticks; trail_offset = max(C x {off}/100 / 0.01, 1) '
      f'= {ofs:.6f} ticks = {ofs_px:.6f}')
    P(f'entry row {eb} [{ts(cb.iloc[eb].t_open)}] fill at the open {fill}; activation = {fill} {"+" if d > 0 else "-"} '
      f'{pts * TICK:.6f} = {act_px:.6f}; engine qty {row["qty"]:.8f}')
    # exit (re-)sends: the signal bar's, then same-side signals while in the trade (bars eb..xb-1)
    stp = S['stp_l'] if d > 0 else S['stp_s']
    lim = S['lim_l'] if d > 0 else S['lim_s']
    drop = X['trailOn'] and not X['useTarget']
    sends = [sb] + [j for j in range(eb, xb) if sigarr[j - w0]]
    eff = {}
    for j in sends:
        lv = float('nan') if drop else lim[j - w0]
        P(f'  Exit {side} sent on row {j}: stop {stp[j - w0]:.6f} limit {lv:.6f}  (effective from row {j + 1})')
        eff[j + 1] = (stp[j - w0], lv)
    armed, best, res = False, float('nan'), None
    cur = None
    for r in range(eb, xb + 1):
        if r in eff:
            cur = eff[r]
        sv, lv = cur
        bar = cb.iloc[r]
        if X['path'] == 'mag':
            sub = subbars(pair, bar.t_open, bar.t_close)
        else:
            sub = cb.iloc[r:r + 1]
        lines = []
        was_armed = armed
        for k, sbar in enumerate(sub.itertuples(index=False)):
            pname, pt = path_of(sbar.open, sbar.high, sbar.low, sbar.close)
            note = ''
            # the open: trail state update, then any level already beyond fills at the open
            for j, p in enumerate(pt):
                if not armed and (p - act_px) * d >= -1e-9:
                    armed, best = True, p
                    note += f' armed@{p}'
                elif armed and (p - best) * d > 0:
                    best = p
                stop_t = best - d * ofs_px if armed else float('nan')
                if j == 0:
                    if armed and (p - stop_t) * d <= 1e-9:
                        res = (r, k, p, 'trail', 'open beyond the trailing stop ' + f'{stop_t:.6f}')
                    elif (p - sv) * d <= 0:
                        res = (r, k, p, 'sl', 'open beyond the zone stop')
                    elif (p - lv) * d >= 0:
                        res = (r, k, p, 'tp', 'open beyond the target')
                else:
                    q = pt[j - 1]
                    if (p - q) * d > 0:          # moving in the trade's favour: only the target
                        if (p - lv) * d >= 0:
                            res = (r, k, lv, 'tp', 'target touched')
                    elif (p - q) * d < 0:        # moving against: trailing / zone stop
                        hit_t = armed and (p - stop_t) * d <= 1e-9
                        hit_s = (p - sv) * d <= 0
                        if hit_t and (not hit_s or (stop_t - sv) * d >= 0):
                            res = (r, k, stop_t, 'trail', f'price {p} ({"falling" if d > 0 else "rising"} leg) reaches the '
                                                          f'trailing stop {stop_t:.6f} = best {best} '
                                                          f'{"-" if d > 0 else "+"} {ofs_px:.6f}')
                        elif hit_s:
                            res = (r, k, sv, 'sl', 'zone stop touched')
                if res is not None:
                    break
            lines.append(f'      sub {k:3d} [{ts(sbar.t_open)}] O {sbar.open} H {sbar.high} L {sbar.low} C {sbar.close} '
                         f'{pname}  armed={armed} best={best} trail_stop='
                         f'{(best - d * ofs_px) if armed else float("nan"):.6f}{note}'
                         + (f'  -> EXIT {res[3]} at {res[2]}: {res[4]}' if res is not None else ''))
            if res is not None:
                break
        stop_now = (best - d * ofs_px) if armed else float('nan')
        P(f'  row {r} [{ts(bar.t_open)}] O {bar.open} H {bar.high} L {bar.low} C {bar.close} | zone stop {sv:.6f} '
          f'limit {lv:.6f} | end: armed={armed} best={best} trail_stop={stop_now:.6f}'
          + (f'  EXIT on sub-bar {res[1]}' if res is not None and X['path'] == 'mag' else '')
          + ('  EXIT' if res is not None and X['path'] != 'mag' else ''))
        if X['path'] == 'mag' and (res is not None or (armed and not was_armed) or show_all_sub):
            for ln in lines:
                P(ln)
        elif X['path'] != 'mag' and res is not None:
            for ln in lines:
                P(ln)
        if res is not None:
            break
    if res is None:
        P('  trace: no exit found')
        return False
    r, k, px, kind, why = res
    rate, fee = V.ref_rates(pair, X['cost'])
    q = row['qty']
    pnl = d * (px - fill) * q - (rate * fill * q + fee * q) - (rate * px * q + fee * q)
    ok = (r == xb and px == row['exit_px'] and kind == row['exit_kind'] and fill == row['entry_px']
          and abs(pnl - row['pnl']) <= 1e-9 * max(1, abs(pnl)))
    P(f'  trace exit: row {r} sub-bar {k} {kind} at {px} ({why}); pnl = {d} x ({px} - {fill}) x {q:.8f} - costs '
      f'= {pnl:.6f}')
    P(f'  engine   : row {xb} {row["exit_kind"]} at {row["exit_px"]} pnl {row["pnl"]:.6f}  -> '
      f'{"MATCH" if ok else "MISMATCH"}')
    out_lines.append((title, ok))
    return ok


def engine_trades(S, X):
    out, _ = apex.simulate(S, {k: X[k] for k in ('trailOn', 'trailAct', 'trailOff', 'useTarget', 'blkClose',
                                                 'cost', 'path')})
    return apex.trades_frame(S, out)


def first_sub_gap(S, X, row):
    """True when the engine's trail exit price is the open of a later sub-bar of the exit bar."""
    pair = S['pair']
    bar = raw(pair, S['tf']).iloc[int(row['exit_bar'])]
    sub = subbars(pair, bar.t_open, bar.t_close)
    opens = sub['open'].to_numpy()[1:]
    return bool((opens == row['exit_px']).any())


def main():
    res = []
    base = dict(trailOn=True, blkClose=True, cost='tv')
    # T1: BTC 60 mag, filter on: armed in one chart bar, trailed out in a later one
    S = V.prep('BTC_60', True, False)
    X = dict(base, trailAct=0.5, trailOff=0.3, useTarget=True, path='mag')
    E = engine_trades(S, X)
    c = E[(E.exit_kind == 'trail') & (E.exit_bar - E.entry_bar == 1)]
    trace('T1 BTC 60 mag: a short not armed on its fill bar, armed and trailed out on the next bar (sub-bars 4-5)', 'BTC_60', S, X, c.iloc[0], res)
    # T2: a level crossed by a jump between two sub-bars: fills at the later sub-bar's open
    found = False
    for cell in ('XAU_60', 'BTC_60', 'XAU_240'):
        for fon in (False, True):
            S = V.prep(cell, fon, False)
            for a, o in ((0.0, 0.01), (0.05, 0.02), (0.1, 0.05), (0.0, 0.05), (0.2, 0.1)):
                X = dict(base, trailAct=a, trailOff=o, useTarget=False, path='mag')
                E = engine_trades(S, X)
                c = E[(E.exit_kind == 'trail') & (E.exit_bar - E.entry_bar <= 1)]
                for _, row in c.iterrows():
                    if first_sub_gap(S, X, row):
                        trace(f'T2 {cell} mag: trailing stop crossed by a jump between sub-bars -> fill at the '
                              f'next sub-bar open', cell, S, X, row, res)
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if found:
            break
    # T3: XAU 240 mag, a short trailed out
    S = V.prep('XAU_240', False, False)
    X = dict(base, trailAct=0.2, trailOff=0.15, useTarget=True, path='mag')
    E = engine_trades(S, X)
    c = E[(E.exit_kind == 'trail') & (E.dir < 0)]
    c = c.assign(n=c.exit_bar - c.entry_bar).sort_values('n')
    trace('T3 XAU 240 mag: a short trailed out', 'XAU_240', S, X, c.iloc[0], res)
    # T4: BTC 15 (3-month window), tv path: armed and stopped inside the fill bar
    S = V.prep('BTC_15', True, False)
    X = dict(base, trailAct=0.1, trailOff=0.1, useTarget=True, path='tv')
    E = engine_trades(S, X)
    c = E[(E.exit_kind == 'trail') & (E.exit_bar == E.entry_bar)]
    trace('T4 BTC 15 tv: activation and trailing exit on the fill bar (one O-H-L-C / O-L-H-C path)',
          'BTC_15', S, X, c.iloc[0], res)
    # T5: mag, a same-side re-send while the trail is armed (stop / limit change, trail state kept)
    S = V.prep('BTC_60', False, False)
    X = dict(base, trailAct=0.3, trailOff=1.0, useTarget=True, path='mag')
    E = engine_trades(S, X)
    w0 = S['w0']
    done = False
    for _, row in E[E.exit_kind == 'trail'].iterrows():
        sig = S['sig_l'] if row['dir'] > 0 else S['sig_s']
        js = [j for j in range(int(row['entry_bar']), int(row['exit_bar'])) if sig[j - w0]]
        if js and int(row['exit_bar']) - int(row['entry_bar']) <= 6:
            trace('T5 BTC 60 mag: same-side signal re-sends the exit while trailing; distances and best kept',
                  'BTC_60', S, X, row, res)
            done = True
            break
    if not done:
        print('T5: no candidate')
    print('\nTRACES:', ', '.join(f'{t.split()[0]} {"MATCH" if ok else "MISMATCH"}' for t, ok in res))
    print('TRACE', 'PASS' if res and all(ok for _, ok in res) and len(res) >= 5 else 'FAIL')


main()
