"""tests_danny.py: tests of the canonical replica danny.py (Danny Phantom FX V10.21.1 LiveSafe + FGF
[Update 1]); REPLICA_SPEC.md stage 3. Prints PASS / FAIL per test; exit code 1 on any failure.

Usage: python3 -I tests_danny.py [T1 T2 ...] [--quick]
  T1  A == B == canonical, every column of trades() and every field of summary(), on BTC and XAU
      charts 1, 5, 15, 60, 240, full windows: defaults, filter off, inv on (filter on / off), each
      cost mode, both varRollback, both signalDirection, 8 random calibration-grid settings per
      cell (80 in all), and 32 inputs outside the grid (one subprocess per cell:
      reconcile_danny_cmp.py). --quick: charts 60 and 240 only.
  T2  path 'mag' on chart "1" == path 'tv' (every column, bitwise), BTC and XAU.
  T3  path 'mag' with one fake sub-bar per chart candle == path 'tv'.
  T4  path 'mag' (and 'tv') against a slow pure-Python reference of the exits written for this
      test, on 30 + 10 random settings over 2-month windows. The reference takes ONLY the entry
      decisions (candle and side of each trade) from the module and recomputes the fill price, the
      quantity, the entry state (with the inherited one), the bracket of every candle, the exit along
      the 1-minute bars it reads itself, the forced closes, costs, P/L and cash.
  T5  fair halves, costs, slippage and net of each cost mode against a direct recomputation from
      the trade list.
  T6  the properties of Update 1 stated in the Pine header (P1: filter off and no directional
      window, inverted == the other "Signal direction"; not with the filter on, not on the preset
      cell; "Allow buys" off), the mirror property on whole reversal-only runs and on first
      decisions (P2), filter off == the unfused original (P3, against builder A's literal
      transliteration of the unfused file's entry block), varRollback independence (P4).
  T7  the kernel against builder A's literal several-runs reference (danny_a_ref.py) incl. the
      zero-quantity corner; the sub-bar table against hrd.sub_bars.
  T8  timing: simulate on BTC "1" ('tv' and 'mag') under 1 s, prepare under 2 minutes.
"""
import bisect
import math
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import danny as dc                      # noqa: E402
import reconcile_danny_cmp as rc        # noqa: E402

V10 = dc.SIG_INV
ORIG = dc.SIG_ORIG
RESULTS = []


def report(name, ok, detail=''):
    RESULTS.append((name, bool(ok)))
    print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, ('  ' + detail) if detail else ''), flush=True)


def run1(P, x, sub=None):
    R = dc.simulate(P, x, sub=sub)
    return dc.trades(P, R), dc.summary(P, R), R


# ----------------------------------------------------------------------------------------------
# T1
# ----------------------------------------------------------------------------------------------
def t1(quick):
    tfs = ('60', '240') if quick else ('60', '240', '15', '5', '1')
    for pair in ('BTC', 'XAU'):
        for tf in tfs:
            t0 = time.time()
            r = subprocess.run([sys.executable, '-I', os.path.join(W, 'reconcile_danny_cmp.py'), pair, tf,
                                '--mods', 'a,b,c', '--extra'], capture_output=True, text=True)
            last = [ln for ln in r.stdout.splitlines() if ln.startswith('TOTAL')]
            report('T1 A == B == canonical, %s %s' % (pair, tf), r.returncode == 0 and len(last) == 1,
                   (last[0][6:] if last else (r.stderr.strip().splitlines() or ['no output'])[-1])
                   + ' [%.0fs]' % (time.time() - t0))


# ----------------------------------------------------------------------------------------------
# T2 / T3
# ----------------------------------------------------------------------------------------------
SETTINGS_23 = [
    dict(), dict(inv=True), dict(cost='ours'), dict(cost='stress', inv=True),
    dict(varRollback=False), dict(signalDirection=ORIG, inv=True),
    dict(useTrailS2=True, trailActAtr=1.0, trailDstAtr=0.5),
    dict(useBreakeven=True, beTriggerAtr=0.5, tpRS2=0.0, inv=True),
    dict(ExitMode="Points", slPointsIn=20000.0, tpPointsIn=30000.0, QtyMode="Fixed", fixedQtyS3=0.01),
]


def t2():
    for pair in ('XAU', 'BTC'):
        ncase = nbad = ntr = 0
        for fo in (True, False):
            P = dc.prepare(pair, '1', dict(fgfOn=fo))
            for x in SETTINGS_23:
                ta, sa, _ = run1(P, dict(x, path='tv'))
                tb, sb, _ = run1(P, dict(x, path='mag'))
                e, txt, _ = rc.cmp_frames(ta, tb, exact=True)
                bad = rc.cmp_summ(sa, sb, exact=True)
                ncase += 1
                ntr += len(ta)
                if not e or bad:
                    nbad += 1
                    print('     %s 1 fgfOn=%s %s: %s %s' % (pair, fo, x, txt, bad[:4]))
            del P
        report('T2 mag on chart 1 == tv, %s' % pair, nbad == 0, '%d cases, %d trades, %d differ' % (ncase, ntr, nbad))
        dc._BARS.clear()
        dc._PERM.clear()


def t3():
    ncase = nbad = ntr = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15'), ('BTC', '240'), ('XAU', '240')):
        for fo in (True, False):
            P = dc.prepare(pair, tf, dict(fgfOn=fo))
            fake = dc.fake_sub_bars(P)
            for x in SETTINGS_23:
                ta, sa, _ = run1(P, dict(x, path='tv'))
                tb, sb, _ = run1(P, dict(x, path='mag'), sub=fake)
                e, txt, _ = rc.cmp_frames(ta, tb, exact=True)
                bad = rc.cmp_summ(sa, sb, exact=True)
                ncase += 1
                ntr += len(ta)
                if not e or bad:
                    nbad += 1
                    print('     %s %s fgfOn=%s %s: %s %s' % (pair, tf, fo, x, txt, bad[:4]))
    report('T3 mag with one fake sub-bar per candle == tv', nbad == 0, '%d cases, %d trades, %d differ' % (ncase, ntr, nbad))


# ----------------------------------------------------------------------------------------------
# T4: the slow reference of the exits (pure Python; None = na)
# ----------------------------------------------------------------------------------------------
REF_COST = {'tv': {'XAU': (0.0, 0.001 / 100.0), 'BTC': (0.0, 0.001 / 100.0)},
            'ours': {'XAU': (0.30 / 2, 0.0), 'BTC': (0.20 / 2, 0.02 / 100.0)},
            'stress': {'XAU': (0.50 / 2 + 0.01, 0.0), 'BTC': (0.20 / 2 + 0.01, 0.035 / 100.0)}}
_M1 = {}


def m1_bars(pair):
    if pair not in _M1:
        t = pq.read_table(os.path.join(W, 'data', '%s_1.parquet' % pair),
                          columns=['open', 'high', 'low', 'close', 't_open']).to_pandas()
        _M1[pair] = (t['t_open'].tolist(), t['open'].tolist(), t['high'].tolist(), t['low'].tolist(),
                     t['close'].tolist())
    return _M1[pair]


def ref_walk(pos, o, h, l, c, S, T):
    """One bar, TradingView's assumed path: the open, the extreme nearer to the open, the other
    extreme, the close. -> None or (is_stop, raw price, where 1 / 2 / 3)."""
    if pos > 0:
        if S is not None and o <= S:
            return True, o, 1
        if T is not None and o >= T:
            return False, o, 1
    else:
        if S is not None and o >= S:
            return True, o, 1
        if T is not None and o <= T:
            return False, o, 1
    pts = [h, l, c] if (h - o) < (o - l) else [l, h, c]
    prev = o
    for j, p in enumerate(pts):
        if p > prev:
            if pos > 0 and T is not None and p >= T:
                return False, T, j + 1
            if pos < 0 and S is not None and p >= S:
                return True, S, j + 1
        elif p < prev:
            if pos > 0 and S is not None and p <= S:
                return True, S, j + 1
            if pos < 0 and T is not None and p <= T:
                return False, T, j + 1
        prev = p
    return None


def ref_protect(pos, close, avg, st, I, trailActNow, trailDstNow):
    """L1414-1448 with the current close; st = dict(atrE, slE, tpE, trArmed, trStop, beArmed).
    -> (stop, target, label)."""
    label = 'sl'
    slE, tpE = st['slE'], st['tpE']
    if pos > 0:
        stop = avg - slE if (slE is not None and slE > 0) else None
        tgt = None if tpE is None else avg + tpE
        if I['useTrailS2']:
            if close - avg >= trailActNow:
                st['trArmed'] = True
            if st['trArmed']:
                newTrail = close - trailDstNow
                st['trStop'] = newTrail if st['trStop'] is None else max(st['trStop'], newTrail)
                if stop is None or st['trStop'] > stop:
                    label = 'trail'
                stop = st['trStop'] if stop is None else max(stop, st['trStop'])
        if I['breakevenActive']:
            if close >= avg + st['atrE'] * I['beTrigger']:
                st['beArmed'] = True
            if st['beArmed'] and stop is not None:
                if avg > stop:
                    label = 'be'
                stop = max(stop, avg)
    else:
        stop = avg + slE if (slE is not None and slE > 0) else None
        tgt = None if tpE is None else avg - tpE
        if I['useTrailS2']:
            if avg - close >= trailActNow:
                st['trArmed'] = True
            if st['trArmed']:
                newTrail = close + trailDstNow
                st['trStop'] = newTrail if st['trStop'] is None else min(st['trStop'], newTrail)
                if stop is None or st['trStop'] < stop:
                    label = 'trail'
                stop = st['trStop'] if stop is None else min(stop, st['trStop'])
        if I['breakevenActive']:
            if close <= avg - st['atrE'] * I['beTrigger']:
                st['beArmed'] = True
            if st['beArmed'] and stop is not None:
                if avg < stop:
                    label = 'be'
                stop = min(stop, avg)
    return stop, tgt, label


def ref_exits(P, tr, Q, path):
    """The slow reference. From the module's trade list `tr` it takes ONLY entry_bar and dir."""
    pair = P['pair']
    o = P['o'].tolist(); h = P['h'].tolist(); l = P['l'].tolist(); c = P['c'].tolist()
    to = P['t_open'].tolist(); tc = P['t_close'].tolist()
    atr = dc.get_atr(P, Q['atrLenS2']).tolist()
    bclose = P['bclose'].tolist(); pre = P['pre'].tolist()
    w0 = P['w0']
    n = len(c)
    entries = {int(b) - w0: int(d) for b, d in zip(tr['entry_bar'], tr['dir'])}
    if len(entries) != len(tr):
        raise RuntimeError('two entries on one candle')
    fix, pct = REF_COST[Q['cost']][pair]
    slip = 0.75 if Q['cost'] == 'tv' else 0.0
    points = Q['ExitMode'] == "Points"
    I = dict(useTrailS2=bool(Q['useTrailS2']), breakevenActive=bool(Q['useBreakeven']),
             beTrigger=float(Q['beTriggerAtr']))
    rollback = bool(Q['varRollback'])
    if path == 'mag':
        mt, mo, mh, ml, mc = m1_bars(pair)
    out = []
    cash = 2000.0
    pos = 0
    cur = None
    S = T = None
    label = 'sl'
    st = None

    def fee(px, q):
        return q * fix + q * px * pct

    def close(k, px, kind, xtime):
        nonlocal cash, pos, cur, S, T, st
        xc = fee(px, cur['qty'])
        gross = pos * cur['qty'] * (px - cur['avg'])
        cash += gross - xc
        cur.update(exit_bar=k + w0, exit_px=px, exit_kind=kind, exit_time=xtime, pnl_gross=gross,
                   costs=cur['ecost'] + xc, pnl=gross - cur['ecost'] - xc)
        out.append(cur)
        pos = 0
        cur = None
        S = T = None
        st = None

    for k in range(n):
        ck = c[k]
        inh = None
        code = 0
        # the bracket sent at the previous close, inside this candle
        if pos != 0 and k > cur['k'] and (S is not None or T is not None):
            hit = None
            if path == 'mag':
                i0 = bisect.bisect_left(mt, to[k])
                i1 = bisect.bisect_left(mt, tc[k])
                for j in range(i0, i1):
                    hit = ref_walk(pos, mo[j], mh[j], ml[j], mc[j], S, T)
                    if hit is not None:
                        xt = mt[j]
                        code = hit[2] if j == i1 - 1 else 1
                        break
            else:
                hit = ref_walk(pos, o[k], h[k], l[k], ck, S, T)
                if hit is not None:
                    xt = to[k]
                    code = hit[2]
            if hit is not None:
                inh = (pos, dict(st))
                if hit[0]:
                    close(k, hit[1] - pos * slip, label, xt)
                else:
                    close(k, hit[1], 'tp', xt)
        # distances of this candle (L1084-1087)
        a = atr[k]
        if points:
            slDistNow = Q['slPointsIn'] * 0.01
            tpDistNow = Q['tpPointsIn'] * 0.01 if Q['tpPointsIn'] > 0 else None
            trailActNow = Q['trailActPts'] * 0.01
            trailDstNow = Q['trailPts'] * 0.01
        else:
            slDistNow = a * Q['slAtrMultS2']
            tpDistNow = slDistNow * Q['tpRS2'] if Q['tpRS2'] > 0 else None
            trailActNow = a * Q['trailActAtr']
            trailDstNow = max(a * Q['trailDstAtr'], 0.01)
        # forced exits on the position left by the bracket (L1105-1118)
        forced = None
        if pos != 0:
            bars_in = k - cur['k']
            dead = (Q['useDeadExit'] and bars_in >= Q['deadBarsIn']
                    and ((pos > 0 and ck <= cur['avg']) or (pos < 0 and ck >= cur['avg'])))
            timex = Q['timeStopBars'] > 0 and bars_in >= Q['timeStopBars']
            forced = 'blackout' if bclose[k] else ('dead' if dead else ('time' if timex else None))
        if k in entries:
            nd = entries[k]
            if forced is not None:
                raise RuntimeError('entry on a forced-exit candle %d' % k)
            if pos == nd:
                raise RuntimeError('same-side entry with a trade open at candle %d' % k)
            equity = cash + (pos * cur['qty'] * (ck - cur['avg']) if pos != 0 else 0.0)
            q = Q['fixedQtyS3']
            if Q['QtyMode'] == "Risk %":
                q = equity * Q['riskPctS3'] / 100.0 / slDistNow if slDistNow > 0 else 0.0
            q = min(q, Q['maxQtyS3'])
            if Q['capMarginS3'] and Q['marginPctS3'] > 0:
                q = min(q, equity / (ck * Q['marginPctS3'] / 100.0))
            q = math.floor(q / Q['qtyStepS3'] + 1e-9) * Q['qtyStepS3']
            if not q > 0:
                raise RuntimeError('entry with quantity 0 at candle %d' % k)
            px = ck + nd * slip
            if pos == -nd:
                close(k, px, 'reverse', tc[k])
            cur = dict(dir=nd, k=k, entry_bar=k + w0, entry_time=tc[k], entry_px=px, avg=px, qty=q, eq_before=cash,
                       ecost=fee(px, q), reentry=code, inherit=False)
            cash -= cur['ecost']
            pos = nd
            if rollback and inh is not None and inh[0] == nd:
                st = inh[1]
                cur['inherit'] = True
            else:
                st = dict(atrE=a, slE=slDistNow, tpE=tpDistNow, trArmed=False, trStop=None, beArmed=False)
            S, T, label = ref_protect(pos, ck, cur['avg'], st, I, trailActNow, trailDstNow)
            cur.update(sl_dist=st['slE'], sl_px=S, tp_px=T)
            if pre[k]:
                close(k, ck - pos * slip, 'blackout', tc[k])
        elif pos != 0:
            if forced is not None:
                close(k, ck - pos * slip, forced, tc[k])
            else:
                S, T, label = ref_protect(pos, ck, cur['avg'], st, I, trailActNow, trailDstNow)
    if pos != 0:
        close(n - 1, c[n - 1] - pos * slip, 'end', tc[n - 1])
    cols = ['dir', 'entry_time', 'entry_px', 'qty', 'exit_time', 'exit_px', 'exit_kind', 'pnl', 'entry_bar',
            'exit_bar', 'eq_before', 'pnl_gross', 'costs', 'sl_dist', 'sl_px', 'tp_px', 'reentry', 'inherit']
    df = pd.DataFrame(out, columns=cols)
    for cn in ('sl_dist', 'sl_px', 'tp_px', 'entry_px', 'exit_px', 'qty', 'pnl', 'eq_before', 'pnl_gross', 'costs'):
        df[cn] = df[cn].astype(float)
    for cn in ('dir', 'entry_time', 'exit_time', 'entry_bar', 'exit_bar', 'reentry'):
        df[cn] = df[cn].astype(np.int64)
    df['inherit'] = df['inherit'].astype(bool)
    return df, cash


def t4():
    rng = np.random.default_rng(424242)
    cells = [('BTC', '5'), ('BTC', '15'), ('BTC', '60'), ('BTC', '240'), ('XAU', '5'), ('XAU', '15'), ('XAU', '60'),
             ('XAU', '240')]
    nbad = ntr = 0
    kinds = {}
    nre = ninh = 0
    plan = [('mag', i) for i in range(30)] + [('tv', i) for i in range(10)]
    for path, i in plan:
        pair, tf = cells[int(rng.integers(len(cells)))]
        sig, x = rc.grid_draw(rng, pair, tf)
        # outside the grid as well: tighter trailing, breakeven, Points mode, sizing
        u = int(rng.integers(6))
        if u == 0:
            x.update(useTrailS2=True, trailActAtr=float(rng.choice([0.5, 1.0])), trailDstAtr=float(rng.choice([0.3, 0.6])))
        elif u == 1:
            x.update(useBreakeven=True, beTriggerAtr=float(rng.choice([0.4, 0.8])))
        elif u == 2:
            big = pair == 'BTC'
            x.update(ExitMode="Points", slPointsIn=40000.0 if big else 250.0, tpPointsIn=float(rng.choice([0.0, 2.0])) * (40000.0 if big else 250.0),
                     useTrailS2=True, trailActPts=30000.0 if big else 200.0, trailPts=15000.0 if big else 100.0)
        elif u == 3:
            x.update(QtyMode="Fixed", fixedQtyS3=0.01 if pair == 'BTC' else 1.0)
        s0, e0 = dc.WINDOWS[pair]
        start = int(s0 + rng.integers(0, (e0 - s0) // 86400 - 61) * 86400)
        sig.update(start=start, end=start + 61 * 86400)
        P = dc.prepare(pair, tf, sig)
        R = dc.simulate(P, dict(x, path=path))
        tr = dc.trades(P, R)
        sm = dc.summary(P, R)
        Q = R['x']
        cols = ['dir', 'entry_time', 'entry_px', 'qty', 'exit_time', 'exit_px', 'exit_kind', 'pnl', 'entry_bar',
                'exit_bar', 'eq_before', 'pnl_gross', 'costs', 'sl_dist', 'sl_px', 'tp_px', 'reentry', 'inherit']
        try:
            rf, cash = ref_exits(P, tr, Q, path)
            e, txt, _ = rc.cmp_frames(tr[cols], rf[cols])
            if e and abs(cash - sm['final_equity']) > 1e-7 * max(1.0, abs(cash)):
                e, txt = False, 'final cash %r vs %r' % (cash, sm['final_equity'])
        except RuntimeError as ex:
            e, txt = False, 'reference refused the entries: %s' % ex
        ntr += len(tr)
        nre += int((tr['reentry'] > 0).sum())
        ninh += int(tr['inherit'].sum())
        for kd, cnt in tr['exit_kind'].value_counts().items():
            kinds[kd] = kinds.get(kd, 0) + int(cnt)
        if not e:
            nbad += 1
        print('     %s %s %s %s %s: %d trades, zero_qty %d  %s' % (path, pair, tf, {k: v for k, v in sig.items() if k not in ('start', 'end')},
                                                               x, len(tr), sm['zero_qty'], 'equal' if e else 'DIFF ' + txt), flush=True)
    report('T4 mag (30) and tv (10) random settings on 2-month windows == the slow exit reference', nbad == 0,
           '%d trades, %d settings differ; exit kinds %s; same-candle re-entries %d, inherited %d'
           % (ntr, nbad, dict(sorted(kinds.items())), nre, ninh))


# ----------------------------------------------------------------------------------------------
# T5
# ----------------------------------------------------------------------------------------------
def t5():
    nbad = ncase = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '15'), ('XAU', '240')):
        for fo in (True, False):
            P = dc.prepare(pair, tf, dict(fgfOn=fo))
            cl = P['c']; op = P['o']; w0 = P['w0']
            for cost in ('tv', 'ours', 'stress'):
                for path in ('tv', 'mag'):
                    for x in (dict(), dict(inv=True), dict(useTrailS2=True, trailActAtr=1.0, trailDstAtr=0.5)):
                        tr, sm, R = run1(P, dict(x, cost=cost, path=path))
                        msg = []
                        fix, pct = REF_COST[cost][pair]
                        slip = 0.75 if cost == 'tv' else 0.0
                        d = tr['dir'].to_numpy(float); q = tr['qty'].to_numpy(); ep = tr['entry_px'].to_numpy()
                        xp = tr['exit_px'].to_numpy()
                        costs = q * fix + q * ep * pct + q * fix + q * xp * pct
                        pnl = d * q * (xp - ep) - costs
                        if not np.allclose(costs, tr['costs'], rtol=1e-10, atol=1e-12):
                            msg.append('costs')
                        if not np.allclose(pnl, tr['pnl'], rtol=1e-9, atol=1e-9):
                            msg.append('pnl')
                        net = pnl.sum() / 2000.0 * 100.0
                        if abs(net - sm['net_pct']) > 1e-8 * max(1.0, abs(net)):
                            msg.append('net_pct %r vs %r' % (net, sm['net_pct']))
                        if abs(costs.sum() - sm['costs']) > 1e-8 * max(1.0, costs.sum()):
                            msg.append('costs total')
                        # the slippage is inside the fill prices: entries and market closes at the candle
                        # close -/+ slip, a stop at its level (or a bar open) -/+ slip, a target without
                        eb = tr['entry_bar'].to_numpy() - w0; xb = tr['exit_bar'].to_numpy() - w0
                        if not np.allclose(ep, cl[eb] + d * slip, rtol=0, atol=1e-9):
                            msg.append('entry price')
                        kd = tr['exit_kind'].to_numpy()
                        mk = np.isin(kd, ['reverse', 'dead', 'time', 'blackout', 'end'])
                        if not np.allclose(xp[mk], cl[xb[mk]] - d[mk] * slip, rtol=0, atol=1e-9):
                            msg.append('market exit price')
                        tp = kd == 'tp'
                        if path == 'tv' and not np.all(np.isclose(xp[tp], tr['tp_px'].to_numpy()[tp], rtol=0, atol=1e-9)
                                                       | np.isclose(xp[tp], op[xb[tp]], rtol=0, atol=1e-9)):
                            msg.append('target price')
                        sl = kd == 'sl'
                        if path == 'tv' and not np.all(np.isclose(xp[sl] + d[sl] * slip, tr['sl_px'].to_numpy()[sl], rtol=0, atol=1e-9)
                                                       | np.isclose(xp[sl] + d[sl] * slip, op[xb[sl]], rtol=0, atol=1e-9)):
                            msg.append('stop price')
                        paid = slip * (q.sum() + q[~tp].sum())
                        if abs(paid - sm['slippage_paid']) > 1e-8 * max(1.0, paid):
                            msg.append('slippage_paid %r vs %r' % (paid, sm['slippage_paid']))
                        # fair halves
                        first = tr['entry_time'].to_numpy() <= P['mid']
                        r = 1.0 + tr['pnl'].to_numpy() / tr['eq_before'].to_numpy()
                        h1 = (np.prod(r[first]) - 1.0) * 100.0
                        h2 = (np.prod(r[~first]) - 1.0) * 100.0
                        if abs(h1 - sm['h1r_pct']) > 1e-9 * max(1.0, abs(h1)) or abs(h2 - sm['h2r_pct']) > 1e-9 * max(1.0, abs(h2)):
                            msg.append('fair halves')
                        if int(first.sum()) != sm['h1_trades'] or int((~first).sum()) != sm['h2_trades']:
                            msg.append('half counts')
                        # eq_before = the cash just before the entry fill
                        cash_before = 2000.0 + np.concatenate(([0.0], np.cumsum(tr['pnl'].to_numpy())[:-1]))
                        if not np.allclose(cash_before, tr['eq_before'].to_numpy(), rtol=1e-9, atol=1e-7):
                            msg.append('eq_before')
                        for kk in dc.KINDS[1:]:
                            if int((kd == kk).sum()) != sm['exit_' + kk]:
                                msg.append('exit_' + kk)
                        if sm['long'] != int((d > 0).sum()) or sm['short'] != int((d < 0).sum()) or sm['trades'] != len(tr):
                            msg.append('counts')
                        ncase += 1
                        if msg:
                            nbad += 1
                            print('     %s %s fgfOn=%s cost=%s path=%s %s: %s' % (pair, tf, fo, cost, path, x, msg))
    report('T5 fair halves, costs, slippage, net against a recomputation from the trade list', nbad == 0,
           '%d runs (3 cost modes x 2 paths), %d differ' % (ncase, nbad))


# ----------------------------------------------------------------------------------------------
# T6
# ----------------------------------------------------------------------------------------------
def flip_sig(t):
    t = t.copy()
    t['sig'] = -t['sig']
    return t


def t6():
    # ---- P1: the header's property
    nbad = n = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '15'), ('XAU', '15'), ('BTC', '240'), ('XAU', '240'), ('BTC', '5')):
        P = dc.prepare(pair, tf, dict(fgfOn=False))
        for path in ('tv', 'mag'):
            for cost in ('tv', 'ours'):
                for rb in (True, False):
                    for X, Y in ((V10, ORIG), (ORIG, V10)):
                        ti, si, _ = run1(P, dict(inv=True, signalDirection=X, path=path, cost=cost, varRollback=rb))
                        tn, sn, _ = run1(P, dict(inv=False, signalDirection=Y, path=path, cost=cost, varRollback=rb))
                        e, txt, _ = rc.cmp_frames(flip_sig(ti), tn, exact=True)
                        s2 = dict(si)
                        s2['raw_long'], s2['raw_short'] = si['raw_short'], si['raw_long']
                        s2['blocked_long'], s2['blocked_short'] = si['blocked_short'], si['blocked_long']
                        bad = rc.cmp_summ(s2, sn, exact=True)
                        n += 1
                        if not e or bad:
                            nbad += 1
                            print('     P1 %s %s %s %s rb=%s %s: %s %s' % (pair, tf, path, cost, rb, X, txt, bad[:4]))
    report('T6 P1 filter off, no directional window: inverted == the other Signal direction (sig mirrored, raw counts swapped)',
           nbad == 0, '%d pairs of runs, %d differ' % (n, nbad))
    # ---- P1 does not hold with the filter on, nor on the preset cell
    P = dc.prepare('BTC', '60', dict(fgfOn=True))
    ti, si, _ = run1(P, dict(inv=True, signalDirection=V10))
    tn, sn, _ = run1(P, dict(inv=False, signalDirection=ORIG))
    report('T6 P1 counter-example: with the filter on the two are different runs', len(ti) != len(tn),
           'BTC 60 inverted + V10: %d trades; normal + Original: %d trades' % (len(ti), len(tn)))
    P = dc.prepare('XAU', '5', dict(fgfOn=False))
    ti, si, _ = run1(P, dict(inv=True, signalDirection=V10, useV1013VolCostFilter=False))
    tn, sn, _ = run1(P, dict(inv=False, signalDirection=ORIG, useV1013VolCostFilter=False))
    e, txt, _ = rc.cmp_frames(flip_sig(ti), tn, exact=True)
    report('T6 P1 counter-example: XAU 5 preset cell (directional windows in force) differs', (not e) and len(ti) > 100,
           '%d vs %d trades; %s' % (len(ti), len(tn), txt))
    t0, s0, _ = run1(P, dict())
    report('T6 XAU 5 default (Auto = XAUUSD 5m preset): the cost filter leaves no trade', len(t0) == 0 and s0['raw_long'] + s0['raw_short'] == 0,
           '%d trades' % len(t0))
    # ---- header: "Allow buys off removes the SELL orders this option places (only BUY orders are left)"
    P = dc.prepare('BTC', '60', dict(fgfAllowBuy=False))
    tn, sn, _ = run1(P, dict())
    ti, si, _ = run1(P, dict(inv=True))
    P2 = dc.prepare('BTC', '60', dict(fgfAllowSell=False))
    tn2, sn2, _ = run1(P2, dict())
    ti2, si2, _ = run1(P2, dict(inv=True))
    report('T6 Allow buys / Allow sells keep meaning the normal direction',
           sn['long'] == 0 and sn['short'] > 0 and si['short'] == 0 and si['long'] > 0
           and sn2['short'] == 0 and sn2['long'] > 0 and si2['long'] == 0 and si2['short'] > 0,
           'Allow buys off: normal %d L / %d S, inverted %d L / %d S; Allow sells off: normal %d L / %d S, inverted %d L / %d S'
           % (sn['long'], sn['short'], si['long'], si['short'], sn2['long'], sn2['short'], si2['long'], si2['short']))
    # ---- P2: mirror. Runs closed only by reversals: the inverted run is the normal run mirrored
    nbad = n = ntr = 0
    rev_only = dict(ExitMode="Points", slPointsIn=0.0, tpPointsIn=0.0, QtyMode="Fixed", capMarginS3=False,
                    timeStopBars=0, useDeadExit=False, useV1011LossClusterPause=False)
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '15'), ('XAU', '240')):
        for fo in (True, False):
            P = dc.prepare(pair, tf, dict(fgfOn=fo, useWeekendBlackout=False, useDailyBlackout=False))
            for sd in (V10, ORIG):
                for cost in ('tv', 'ours'):
                    x = dict(rev_only, fixedQtyS3=0.01 if pair == 'BTC' else 1.0, signalDirection=sd, cost=cost)
                    tn, sn, _ = run1(P, dict(x, inv=False))
                    ti, si, _ = run1(P, dict(x, inv=True))
                    cl = P['c']; w0 = P['w0']
                    ok = len(tn) == len(ti) and len(tn) > 20 and set(tn['exit_kind']) <= {'reverse', 'end'}
                    if ok:
                        ok = bool((tn['dir'].to_numpy() == -ti['dir'].to_numpy()).all()
                                  and (tn['entry_bar'].to_numpy() == ti['entry_bar'].to_numpy()).all()
                                  and (tn['exit_bar'].to_numpy() == ti['exit_bar'].to_numpy()).all()
                                  and (tn['sig'].to_numpy() == ti['sig'].to_numpy()).all()
                                  and (tn['zone'].to_numpy() == ti['zone'].to_numpy()).all()
                                  and (tn['qty'].to_numpy() == ti['qty'].to_numpy()).all()
                                  and np.allclose(tn['entry_px'].to_numpy() + ti['entry_px'].to_numpy(),
                                                  2 * cl[tn['entry_bar'].to_numpy() - w0], rtol=0, atol=1e-9)
                                  and np.allclose(tn['exit_px'].to_numpy() + ti['exit_px'].to_numpy(),
                                                  2 * cl[tn['exit_bar'].to_numpy() - w0], rtol=0, atol=1e-9)
                                  and all(sn[kk] == si[kk] for kk in ('raw_long', 'raw_short', 'blocked_long', 'blocked_short')))
                    n += 1
                    ntr += len(tn)
                    if not ok:
                        nbad += 1
                        print('     P2 %s %s fgfOn=%s %s %s: %d vs %d trades' % (pair, tf, fo, sd, cost, len(tn), len(ti)))
    report('T6 P2 mirror: reversal-only runs, inverted == normal mirrored (same candles, opposite sides, prices mirrored about the close)',
           nbad == 0, '%d pairs of runs, %d trades, %d differ' % (n, ntr, nbad))
    # ---- P2 on first decisions (from flat), default exits
    nbad = n = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '5'), ('XAU', '15'), ('BTC', '240')):
        s0, e0 = dc.WINDOWS[pair]
        for j in range(4):
            st = s0 + (37 + 131 * j) * 86400
            P = dc.prepare(pair, tf, dict(start=st, end=st + 45 * 86400))
            tn, sn, Rn = run1(P, dict(cost='ours'))
            ti, si, Ri = run1(P, dict(cost='ours', inv=True))
            if not len(tn) or not len(ti):
                continue
            a = tn.iloc[0]; b = ti.iloc[0]
            cl = P['c'][int(a['entry_bar']) - P['w0']]
            ok = (a['entry_bar'] == b['entry_bar'] and a['dir'] == -b['dir'] and a['qty'] == b['qty'] and a['sig'] == b['sig']
                  and a['zone'] == b['zone'] and a['entry_px'] == b['entry_px'] == cl and a['sl_dist'] == b['sl_dist']
                  and abs((a['sl_px'] - cl) + (b['sl_px'] - cl)) < 1e-9 and abs((a['tp_px'] - cl) + (b['tp_px'] - cl)) < 1e-9)
            n += 1
            if not ok:
                nbad += 1
                print('     P2 first decision %s %s window %d:\n%s\n%s' % (pair, tf, j, a.to_dict(), b.to_dict()))
    report('T6 P2 first decision of a window: same candle, opposite side, same quantity, stop and target mirrored',
           nbad == 0 and n >= 15, '%d windows, %d differ' % (n, nbad))
    # ---- P3: filter off and inv off == the unfused original (builder A's literal transliteration of
    #      the unfused file's own entry conditions and reset test)
    import danny_a_ref as ref
    import danny_a_cmp as ac
    nbad = n = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('XAU', '240')):
        for p in (dict(), dict(varRollback=False), dict(signalDirection=ORIG), dict(cost='ours')):
            tr, sm = dc.run(pair, tf, dict(p, fgfOn=False))
            rt, cnt = ref.ref_run(pair, tf, {k: v for k, v in dict(p, fgfOn=False).items() if k != 'varRollback'},
                                  rollback=bool(p.get('varRollback', True)), original=True)
            cols = ac.COLS_EXACT + ac.COLS_NUM
            e, txt, _ = rc.cmp_frames(tr[cols], rt[cols])
            n += 1
            if not e:
                nbad += 1
                print('     P3 %s %s %s: %s' % (pair, tf, p, txt))
    report('T6 P3 filter off, inv off == the unfused original script', nbad == 0, '%d runs, %d differ' % (n, nbad))
    # ---- P4
    nbad = n = 0
    for pair, tf in (('BTC', '60'), ('XAU', '60'), ('BTC', '240')):
        for fo in (True, False):
            P = dc.prepare(pair, tf, dict(fgfOn=fo))
            for path in ('tv', 'mag'):
                t0, s0, _ = run1(P, dict(cost='ours', path=path))
                for x in (dict(useOnePerZone=False), dict(useCooldown=False), dict(cooldownIn=40),
                          dict(useOnePerZone=False, useCooldown=False, cooldownIn=1)):
                    t1_, s1, _ = run1(P, dict(x, cost='ours', path=path))
                    e, txt, _ = rc.cmp_frames(t0, t1_, exact=True)
                    n += 1
                    if not e or s0['zero_qty'] != 0:
                        nbad += 1
                        print('     P4 %s %s fgfOn=%s %s %s: %s zero_qty %d' % (pair, tf, fo, path, x, txt, s0['zero_qty']))
            # no bracket -> no inherited trade: rollback True == rollback False with both switches off
            x = dict(ExitMode="Points", slPointsIn=0.0, tpPointsIn=0.0, QtyMode="Fixed",
                     fixedQtyS3=0.01 if pair == 'BTC' else 1.0, cost='ours')
            ta, sa, _ = run1(P, dict(x, varRollback=True))
            tb, sb, _ = run1(P, dict(x, varRollback=False, useOnePerZone=False, useCooldown=False))
            tc_, sc_, _ = run1(P, dict(x, varRollback=False))
            e, txt, _ = rc.cmp_frames(ta, tb, exact=True)
            n += 1
            if not e or sa['inherited'] != 0 or len(tc_) == len(ta):
                nbad += 1
                print('     P4b %s %s fgfOn=%s: %s (with the switches on: %d vs %d trades)' % (pair, tf, fo, txt, len(tc_), len(ta)))
    report('T6 P4 varRollback True ignores useOnePerZone / useCooldown / cooldownIn; without inherited trades it equals '
           'varRollback False with both off', nbad == 0, '%d comparisons, %d differ' % (n, nbad))


# ----------------------------------------------------------------------------------------------
# T7
# ----------------------------------------------------------------------------------------------
def t7():
    import danny_a_ref as ref
    import danny_a_cmp as ac
    cases = [('BTC', '60', dict()), ('BTC', '60', dict(inv=True)), ('XAU', '60', dict(fgfOn=False)),
             ('XAU', '60', dict(fgfOn=False, inv=True, signalDirection=ORIG, varRollback=False)),
             ('BTC', '240', dict(useTrailS2=True, trailActAtr=1.0, trailDstAtr=0.5, cost='ours')),
             ('XAU', '240', dict(useBreakeven=True, beTriggerAtr=0.5, cost='stress')),
             # zero-quantity corners (ruined accounts): the reset and the pending* variables of a decision
             # sized to zero, with and without a bracket fill on the candle
             ('XAU', '15', dict(fgfOn=False, inv=True)), ('XAU', '15', dict()),
             ('BTC', '15', dict(cost='ours', fgfOn=False, useTrailS2=True, trailActAtr=1.0, trailDstAtr=0.5)),
             ('XAU', '60', dict(riskPctS3=25.0, useBreakeven=True)),
             ('XAU', '5', dict(presetMode='Manual', fgfOn=False, inv=True, useBreakeven=True, timeStopBars=25)),
             # the run where a stale pendingShortAtr changes a breakeven (danny_s3_trace_zero.log, trade 3225)
             ('BTC', '5', dict(fgfOn=False, cost='ours', useBreakeven=True))]
    nbad = ntr = nz = 0
    for pair, tf, p in cases:
        tr, sm = dc.run(pair, tf, dict(p))
        rt, cnt = ref.ref_run(pair, tf, {k: v for k, v in p.items() if k != 'varRollback'},
                              rollback=bool(p.get('varRollback', True)), original=False, x1=True, keep_pending_on_zero=True)
        cols = ac.COLS_EXACT + ac.COLS_NUM
        e, txt, _ = rc.cmp_frames(tr[cols], rt[cols])
        cnt_ok = all(sm[k] == cnt[k] for k in ('raw_long', 'raw_short', 'blocked_long', 'blocked_short', 'zero_qty'))
        ntr += len(tr)
        nz += sm['zero_qty']
        if not e or not cnt_ok:
            nbad += 1
            print('     T7 %s %s %s: %s counts %s' % (pair, tf, p, txt, cnt_ok))
    report("T7 kernel == builder A's literal several-runs reference (Pine transliterated, `var` rollback)", nbad == 0,
           '%d runs, %d trades, %d zero-quantity decisions, %d differ' % (len(cases), ntr, nz, nbad))
    import hrd
    nbad = 0
    late = 0
    for pair, tf in (('BTC', '60'), ('XAU', '240'), ('XAU', '15'), ('BTC', '5')):
        P = dc.prepare(pair, tf, dict(fgfOn=False))
        a = dc.get_sub(P)
        b = hrd.sub_bars(pair, tf, P['w0'], P['w1'])
        if not all(np.array_equal(a[i], b[i]) for i in range(5)):
            nbad += 1
        # every sub-bar lies inside its candle, in time order; the candle's OHLC is its sub-bars' (the
        # candle's t_open is its grid time: where the 1-minute data has a hole at the start of a candle
        # the first sub-bar opens later, at the same price as the candle)
        cnt = np.diff(a[0])
        kk = np.repeat(np.arange(P['n']), cnt)
        if not (((a[5] >= P['t_open'][kk]) & (a[5] < P['t_close'][kk])).all() and (np.diff(a[5]) > 0).all()):
            nbad += 1
        if not (np.array_equal(a[1][a[0][:-1]], P['o']) and np.array_equal(a[4][a[0][1:] - 1], P['c'])
                and np.array_equal(np.maximum.reduceat(a[2], a[0][:-1]), P['h'])
                and np.array_equal(np.minimum.reduceat(a[3], a[0][:-1]), P['l'])):
            nbad += 1
        late += int((a[5][a[0][:-1]] != P['t_open']).sum())
    report('T7 sub-bar table == hrd.sub_bars; sub-bars inside their candle, in time order, same OHLC', nbad == 0,
           '%d candles start with a hole in the 1-minute data (first sub-bar later than the candle open)' % late)


# ----------------------------------------------------------------------------------------------
# T8
# ----------------------------------------------------------------------------------------------
def t8():
    t0 = time.time()
    P = dc.prepare('BTC', '1', dict(fgfOn=True))
    tp = time.time() - t0
    dc.simulate(P, dict())
    dc.simulate(P, dict(path='mag'))
    tt = []
    for path in ('tv', 'mag'):
        best = 1e9
        for _ in range(3):
            t0 = time.time()
            R = dc.simulate(P, dict(path=path))
            best = min(best, time.time() - t0)
        tt.append(best)
    t0 = time.time()
    s = dc.summary(P, R)
    ts = time.time() - t0
    report('T8 timing BTC "1" (%d candles): simulate under 1 s, prepare under 2 minutes' % P['n'],
           tt[0] < 1.0 and tt[1] < 1.0 and tp < 120.0,
           'prepare (filter on) %.1f s; simulate tv %.3f s, mag %.3f s; summary %.3f s; %d trades' % (tp, tt[0], tt[1], ts, s['trades']))
    del P
    dc._BARS.clear()
    dc._PERM.clear()
    P = dc.prepare('BTC', '60', dict())
    dc.simulate(P, dict(path='mag'))
    t0 = time.time()
    for _ in range(20):
        dc.simulate(P, dict(path='mag'))
    tm = (time.time() - t0) / 20
    t0 = time.time()
    for _ in range(20):
        dc.simulate(P, dict(path='tv'))
    tv = (time.time() - t0) / 20
    report('T8 timing BTC 60: one mag setting', tm < 0.5, 'mag %.4f s, tv %.4f s per simulate' % (tm, tv))


def main(argv):
    quick = '--quick' in argv
    want = [a for a in argv if not a.startswith('--')]
    tests = [('T3', t3), ('T4', t4), ('T5', t5), ('T6', t6), ('T7', t7), ('T1', lambda: t1(quick)), ('T2', t2), ('T8', t8)]
    t00 = time.time()
    for name, fn in tests:
        if want and name not in want:
            continue
        t0 = time.time()
        fn()
        print('     [%s %.0f s]' % (name, time.time() - t0), flush=True)
    nfail = sum(1 for _, ok in RESULTS if not ok)
    print('%d tests, %d PASS, %d FAIL, %.0f s' % (len(RESULTS), len(RESULTS) - nfail, nfail, time.time() - t00))
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
