"""Rule T for the ApexForge / HRD trailing sweeps (out/swah_<strat>_<PAIR>_<TF>.parquet).

Scored on 1-minute fills ('mag'), normal labels, our costs ('ours'), fair halves (h1r / h2r:
trades entered in each half, compounded from a fresh start).

Pool: trail-on settings with an offset >= the 1-minute noise floor (BTC 0.1%, XAU 0.05%), plus
the trail-off settings (the strategy's own exits). Apex trail-off rows with useTarget False are
clones of the default (the Pine ignores 'Keep the target' with the trailing off) and are dropped.
Identical results count once.

Pick: among pool settings positive in both halves with >= MIN_TR trades in each, the 40 best by
worst half, scored 0.5 x worst half + 0.5 x the mean worst half of their grid neighbours
(activation / offset one step away, same other inputs; >= 5 in the pool, positive mean).
Trail-off settings have no neighbours, so they are reported as the baseline, not picked.
Hold-outs (forward: pick on half 1 -> half 2, 95% of random 40-draws beaten, >= 60% positive,
positive mean; reverse: half 2 -> half 1, 95% beaten). Control: the pick beats the same setting
with labels reversed in both halves. Stress: the pick stays positive with stressed costs (engine
re-run). Also: does the pick beat the best trail-off setting (no trailing) in both halves?
"""
import json
import os
import sys

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, W)
TFS = ['1', '5', '15', '30', '60', '120', '240']
ACTS = [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
OFFS = [0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
NOISE = {'BTC': 0.1, 'XAU': 0.05}
MIN_TR = 30
TOPN = 40
NRAND = 5000
SEED = 20261118
OTHER = {'apex': ['useTarget'], 'hrd': ['InpTpPct', 'InpExitCandles']}


def ai(x):
    return int(np.argmin([abs(a - x) for a in ACTS]))


def oi(x):
    return int(np.argmin([abs(o - x) for o in OFFS]))


def label(strat, r):
    if r is None:
        return 'none'
    t = f"trail {r['trailAct']:g}% / {r['trailOff']:g}%" if r['trailOn'] else 'no trail'
    if strat == 'apex':
        if r['trailOn']:
            t += ', target kept' if r['useTarget'] else ', no target'
    else:
        t += f", TP {r['InpTpPct']:g}%" if r['InpTpPct'] > 0 else ', no TP'
        t += f", time exit {int(r['InpExitCandles'])}"
    return t


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if not np.isfinite(f) else round(f, 4)


def brief(strat, r):
    if r is None:
        return None
    d = {'setting': label(strat, r)}
    for k in ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
              'exit_trail', 'exit_sl', 'exit_tp', 'exit_time', 'exit_reverse', 'exit_blocked_close', 'avg_bars_held', 'exposure'):
        if k in r.index:
            d[k] = num(r[k])
    return d


def key(strat, r):
    k = [bool(r['trailOn'])]
    if r['trailOn']:
        k += [ai(r['trailAct']), oi(r['trailOff'])]
    for c in OTHER[strat]:
        k.append(float(r[c]) if not isinstance(r[c], (bool, np.bool_)) else bool(r[c]))
    return tuple(k)


def pool_of(strat, g, pair):
    on = g.trailOn.astype(bool)
    keep = (~on) | (g.trailOff >= NOISE[pair] - 1e-12)
    if strat == 'apex':
        keep &= on | g.useTarget.astype(bool)
    p = g[keep].copy()
    sig = p[['trades', 'net_pct', 'h1r_pct', 'h2r_pct']].round(6).astype(str).agg('|'.join, axis=1)
    return p[~sig.duplicated(keep='first')]


def neighbours(strat, pool):
    idx = {key(strat, r): i for i, r in pool.iterrows()}
    nb = {}
    for i, r in pool.iterrows():
        if not r['trailOn']:
            nb[i] = []
            continue
        k = key(strat, r)
        a, o, rest = k[1], k[2], k[3:]
        out = []
        for da in (-1, 0, 1):
            for do in (-1, 0, 1):
                if (da or do) and 0 <= a + da < len(ACTS) and 0 <= o + do < len(OFFS):
                    j = idx.get((True, a + da, o + do) + rest)
                    if j is not None:
                        out.append(j)
        nb[i] = out
    return nb


def pick(strat, pool):
    p = pool.copy()
    p['worst'] = np.minimum(p['h1r_pct'], p['h2r_pct'])
    cand = p[p.trailOn.astype(bool) & (p.h1r_pct > 0) & (p.h2r_pct > 0) & (p.h1_trades >= MIN_TR) & (p.h2_trades >= MIN_TR)]
    if not len(cand):
        return None, 'no trailing setting is positive in both halves with 30+ trades in each'
    nb = neighbours(strat, p)
    best, bs = None, -np.inf
    for i, r in cand.sort_values('worst', ascending=False).head(TOPN).iterrows():
        ns = nb.get(i, [])
        if len(ns) < 5:
            continue
        m = float(p.loc[ns, 'worst'].mean())
        if m <= 0:
            continue
        sc = 0.5 * r['worst'] + 0.5 * m
        if sc > bs:
            best, bs = r.copy(), sc
            best['score'], best['nb_mean'], best['n_nb'] = sc, m, len(ns)
    return best, (None if best is not None else 'no candidate on a plateau (5+ neighbours with a positive mean worst half)')


def holdout(pool, rng, fwd):
    a, b = ('h1r_pct', 'h2r_pct') if fwd else ('h2r_pct', 'h1r_pct')
    ta = 'h1_trades' if fwd else 'h2_trades'
    p = pool[pool[ta] >= MIN_TR]
    if len(p) < 2 * TOPN:
        return {'pass': False, 'why': f'pool too small ({len(p)})'}
    top = p.sort_values(a, ascending=False).head(TOPN)
    m, share = float(top[b].mean()), float((top[b] > 0).mean())
    vals = p[b].to_numpy()
    draws = np.array([vals[rng.choice(len(vals), TOPN, replace=False)].mean() for _ in range(NRAND)])
    q95 = float(np.quantile(draws, 0.95))
    ok, why = m > q95, []
    if not ok:
        why.append(f'mean {m:+.2f}% not above the random 95th percentile {q95:+.2f}%')
    if fwd and share < 0.6:
        ok = False
        why.append(f'only {share:.0%} positive')
    if fwd and m <= 0:
        ok = False
        why.append('mean not positive')
    return {'pass': bool(ok), 'mean': round(m, 3), 'q95': round(q95, 3), 'share_pos': round(share, 3),
            'median_random': round(float(np.median(draws)), 3), 'why': '; '.join(why)}


def same(strat, g, r):
    k = key(strat, r)
    m = g[[key(strat, x) == k for _, x in g.iterrows()]]
    return m.iloc[0] if len(m) else None


def stress_net(strat, pair, tf, filt, r):
    if strat == 'apex':
        import apex
        S = apex.prepare(pair, tf, {'fgfOn': filt == 'on', 'reverse': False})
        X = {'trailOn': bool(r['trailOn']), 'useTarget': bool(r['useTarget']), 'path': 'mag', 'cost': 'stress'}
        if r['trailOn']:
            X['trailAct'], X['trailOff'] = float(r['trailAct']), float(r['trailOff'])
        _, s = apex.simulate(S, X)
        return float(s['net_pct']), float(s['h1r_pct']), float(s['h2r_pct'])
    import hrd
    P = hrd.prepare(pair, tf, {'fgfOn': filt == 'on', 'reverse': False})
    X = {'trailOn': bool(r['trailOn']), 'InpTpPct': float(r['InpTpPct']), 'InpExitCandles': int(r['InpExitCandles']),
         'path': 'mag', 'cost': 'stress'}
    if r['trailOn']:
        X['trailAct'], X['trailOff'] = float(r['trailAct']), float(r['trailOff'])
    s = hrd.summary_fast(P, hrd.simulate(P, X))
    return float(s['net_pct']), float(s['h1r_pct']), float(s['h2r_pct'])


def analyze(strat, df, pair, tf, filt):
    rng = np.random.default_rng(SEED)
    sel = lambda path, lab, cost: df[(df['filter'] == filt) & (df.path == path) & (df.labels == lab) & (df.cost == cost)]
    g, grev, gtv = sel('mag', 'normal', 'ours'), sel('mag', 'rev', 'ours'), sel('tv', 'normal', 'tv')
    res = {'strat': strat, 'pair': pair, 'tf': tf, 'filter': filt}
    pool = pool_of(strat, g, pair)
    on = pool[pool.trailOn.astype(bool)]
    off = pool[~pool.trailOn.astype(bool)]
    res['pool'] = int(len(pool))
    res['share_pos'] = round(float((on.net_pct > 0).mean()), 3) if len(on) else 0.0
    res['best_trail'] = brief(strat, on.loc[on.net_pct.idxmax()]) if len(on) else None
    res['best_notrail'] = brief(strat, off.loc[off.net_pct.idxmax()]) if len(off) else None
    d = g[(~g.trailOn.astype(bool))]
    if strat == 'apex':
        d = d[d.useTarget.astype(bool)]
    else:
        d = d[(d.InpTpPct == 4.0) & (d.InpExitCandles == 5)]
    res['default'] = brief(strat, d.iloc[0]) if len(d) else None
    dtv = gtv[(~gtv.trailOn.astype(bool))]
    dtv = dtv[dtv.useTarget.astype(bool)] if strat == 'apex' else dtv[(dtv.InpTpPct == 4.0) & (dtv.InpExitCandles == 5)]
    res['default_tv'] = num(dtv.iloc[0]['net_pct']) if len(dtv) else None
    tvon = gtv[gtv.trailOn.astype(bool)]
    tvb = tvon.loc[tvon.net_pct.idxmax()]
    res['tv_best'] = {'setting': label(strat, tvb), 'tv_net': num(tvb['net_pct'])}
    m1 = same(strat, g, tvb)
    res['tv_best']['real_net'] = num(m1['net_pct']) if m1 is not None else None
    pk, why = pick(strat, pool)
    res['pick'], res['why_no_pick'] = None, why
    reasons = []
    if pk is not None:
        rv, tv = same(strat, grev, pk), same(strat, gtv, pk)
        res['pick'] = brief(strat, pk)
        res['pick'].update({'score': round(float(pk['score']), 3), 'nb_mean': round(float(pk['nb_mean']), 3),
                            'trailAct': float(pk['trailAct']), 'trailOff': float(pk['trailOff'])})
        for c in OTHER[strat]:
            res['pick'][c] = num(pk[c]) if not isinstance(pk[c], (bool, np.bool_)) else bool(pk[c])
        res['pick_rev'] = brief(strat, rv)
        res['pick_tv_net'] = num(tv['net_pct']) if tv is not None else None
        sn = stress_net(strat, pair, tf, filt, pk)
        res['pick_stress'] = {'net': round(sn[0], 3), 'h1r': round(sn[1], 3), 'h2r': round(sn[2], 3)}
        res['control_pass'] = bool(rv is not None and pk.h1r_pct > rv.h1r_pct and pk.h2r_pct > rv.h2r_pct)
        res['stress_pass'] = sn[0] > 0
        bo = off.loc[off.net_pct.idxmax()] if len(off) else None
        res['beats_notrail'] = bool(bo is None or (pk.h1r_pct > bo.h1r_pct and pk.h2r_pct > bo.h2r_pct))
        if not res['control_pass']:
            reasons.append('reversed labels do as well in a half')
        if not res['stress_pass']:
            reasons.append(f'stressed costs {sn[0]:+.2f}%')
    else:
        reasons.append('no pick: ' + why)
    res['forward'], res['reverse'] = holdout(pool, rng, True), holdout(pool, rng, False)
    if not res['forward']['pass']:
        reasons.append('forward hold-out failed: ' + res['forward']['why'])
    if not res['reverse']['pass']:
        reasons.append('reverse hold-out failed: ' + res['reverse']['why'])
    res['passes'] = not reasons
    res['reasons'] = reasons
    return res


def main(argv):
    strats = argv or ['apex', 'hrd']
    out = json.load(open(W + 'out/swah_rule.json')) if os.path.exists(W + 'out/swah_rule.json') else {}
    for strat in strats:
        for pair in ('BTC', 'XAU'):
            for tf in TFS:
                f = W + f'out/swah_{strat}_{pair}_{tf}.parquet'
                if not os.path.exists(f):
                    continue
                df = pd.read_parquet(f)
                for filt in ('off', 'on'):
                    r = analyze(strat, df, pair, tf, filt)
                    out[f'{strat}|{pair}|{tf}|{filt}'] = r
                    p = r['pick']
                    print(f"{strat} {pair} {tf:>3} {filt:3} | trail>0 {r['share_pos']:.0%} best {r['best_trail']['setting'] if r['best_trail'] else '-'} "
                          f"{r['best_trail']['net_pct'] if r['best_trail'] else ''} | notrail {r['best_notrail']['setting'] if r['best_notrail'] else '-'} "
                          f"{r['best_notrail']['net_pct'] if r['best_notrail'] else ''} | pick {p['setting'] + ' ' + str(p['net_pct']) if p else '-'} "
                          f"| {'PASS' if r['passes'] else 'no'}: {'; '.join(x.split(':')[0] for x in r['reasons'])}", flush=True)
    json.dump(out, open(W + 'out/swah_rule.json', 'w'), indent=1, default=str)


if __name__ == '__main__':
    main(sys.argv[1:])
