"""Trailing sweep: pick and hold-out test per (pair, TF, filter).  Rule T (trailing).

Data: out/sweep_<PAIR>_<TF>.parquet (sweep.py, SWEEP_SPEC.md + SWEEP_SPEC_2.md).
Scored on the realistic path ('mag', Bar Magnifier with 1-minute data), normal labels, with
costs ('cost_'), on the leak-free halves (h1r / h2r: trades entered in each half, each half
from a fresh 10,000).

Pool: the 1379 grid settings minus trail offsets below the pair's 1-minute noise floor (the
first grid offset >= twice the median 1-minute candle range in the window: BTC 0.1%, XAU
0.05%; below it even the 1-minute path decides the exit), minus settings whose open entries
ever exceed 1.0x equity (TradingView's default 100% margin would liquidate them). Settings with
identical results are clones: one is kept.

Pick: among pool settings positive in both halves with >= MIN_TR trades in each, the 40 best
by worst half are scored by 0.5 x worst half + 0.5 x the mean worst half of their clone-free
grid neighbours (same stop loss, activation and offset one grid step away; at least 5
neighbours in the pool with a positive mean). The best score is the pick.

Hold-out, both directions: the 40 best settings by half 1 must beat 95% of random 40-setting
draws from the pool on half 2, and be >= 60% positive with a positive mean there (forward);
the 40 best by half 2 must beat 95% of random draws on half 1 (reverse).

Signal control: the pick must make more than the same setting with every label reversed, in
both halves. Otherwise the profit comes from the exit, not the signals.
Stressed costs: the pick must stay positive (stress_).

FILE = pick exists and forward, reverse, control and stress all pass.
Writes out/sweep_rule.json and prints a summary.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__)) + '/'
TFS = ['1', '5', '15', '30', '60', '120', '240']
ACTS = [0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
OFFS = [0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
NOISE = {'BTC': 0.1, 'XAU': 0.05}
MAX_EXPO = 1.0
MIN_TR = 30
TOPN = 40
NRAND = 5000
PRE = 'cost_'
RNG_SEED = 20261118


def key_of(r):
    sl = round(float(r['slDist']), 6) if bool(r['slOn']) else -1.0
    if not bool(r['trailOn']):
        return ('off', sl)
    return (round(float(r['trailAct']), 6), round(float(r['trailOff']), 6), sl)


def setting_label(r):
    if r is None:
        return 'none'
    if r['trailUnit'] == 'price':
        t = f"script default (${r['trailAct']:g} / ${r['trailOff']:g})"
    elif not bool(r['trailOn']):
        t = 'no trailing TP'
    else:
        t = f"activation {r['trailAct']:g}%, offset {r['trailOff']:g}%"
    t += f", stop loss {r['slDist']:g}%" if bool(r['slOn']) else ', no stop loss'
    return t


def num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if not np.isfinite(f) else round(f, 4)


def brief(r, pre=PRE):
    if r is None:
        return None
    out = {'setting': setting_label(r)}
    for k in ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
              'max_expo', 'avg_bars_held', 'exit_trail', 'exit_sl', 'exit_close_all', 'exit_reverse'):
        if pre + k in r.index:
            out[k] = num(r[pre + k])
    return out


def pool_of(g, pair):
    grid = g[g.tag == 'grid'].copy()
    ok = ((~grid.trailOn) | (grid.trailOff >= NOISE[pair] - 1e-12)) & (grid[PRE + 'max_expo'] <= MAX_EXPO + 1e-9)
    pool = grid[ok].copy()
    if not len(pool):
        return pool
    sig = pool[[PRE + 'trades', PRE + 'net_pct', PRE + 'h1r_pct', PRE + 'h2r_pct']].round(6).astype(str).agg('|'.join, axis=1)
    pool['clone_of'] = sig
    pool = pool[~sig.duplicated(keep='first')]
    return pool


def neighbours(pool):
    idx = {key_of(r): i for i, r in pool.iterrows()}
    nb = {}
    for i, r in pool.iterrows():
        k = key_of(r)
        if k[0] == 'off':
            nb[i] = []
            continue
        a, o, s = k
        ai, oi = ACTS.index(min(ACTS, key=lambda x: abs(x - a))), OFFS.index(min(OFFS, key=lambda x: abs(x - o)))
        out = []
        for da in (-1, 0, 1):
            for do in (-1, 0, 1):
                if da == 0 and do == 0:
                    continue
                aa, oo = ai + da, oi + do
                if 0 <= aa < len(ACTS) and 0 <= oo < len(OFFS):
                    j = idx.get((round(ACTS[aa], 6), round(OFFS[oo], 6), s))
                    if j is not None:
                        out.append(j)
        nb[i] = out
    return nb


def pick(pool):
    p = pool.copy()
    p['worst'] = np.minimum(p[PRE + 'h1r_pct'], p[PRE + 'h2r_pct'])
    cand = p[(p[PRE + 'h1r_pct'] > 0) & (p[PRE + 'h2r_pct'] > 0) & (p[PRE + 'h1_trades'] >= MIN_TR) & (p[PRE + 'h2_trades'] >= MIN_TR)]
    if not len(cand):
        return None, 'no setting is positive in both halves'
    top = cand.sort_values('worst', ascending=False).head(TOPN)
    nb = neighbours(p)
    best, best_score, why = None, -np.inf, 'no candidate sits on a plateau (>= 5 neighbours with a positive mean worst half)'
    for i, r in top.iterrows():
        ns = nb.get(i, [])
        if len(ns) < 5:
            continue
        m = float(p.loc[ns, 'worst'].mean())
        if m <= 0:
            continue
        sc = 0.5 * r['worst'] + 0.5 * m
        if sc > best_score:
            best, best_score = r.copy(), sc
            best['nb_mean_worst'] = m
            best['score'] = sc
            best['n_nb'] = len(ns)
    return best, (None if best is not None else why)


def holdout(pool, rng, fwd=True):
    a, b = (PRE + 'h1r_pct', PRE + 'h2r_pct') if fwd else (PRE + 'h2r_pct', PRE + 'h1r_pct')
    ta = PRE + ('h1_trades' if fwd else 'h2_trades')
    p = pool[pool[ta] >= MIN_TR]
    if len(p) < TOPN * 2:
        return {'pass': False, 'why': f'pool too small ({len(p)})'}
    top = p.sort_values(a, ascending=False).head(TOPN)
    m = float(top[b].mean())
    share = float((top[b] > 0).mean())
    vals = p[b].to_numpy()
    draws = np.array([vals[rng.choice(len(vals), TOPN, replace=False)].mean() for _ in range(NRAND)])
    q95 = float(np.quantile(draws, 0.95))
    ok = m > q95
    why = []
    if not ok:
        why.append(f'mean {m:+.2f}% not above the random 95th percentile {q95:+.2f}%')
    if fwd:
        if share < 0.6:
            ok = False
            why.append(f'only {share:.0%} positive (60% needed)')
        if m <= 0:
            ok = False
            why.append('mean not positive')
    return {'pass': bool(ok), 'mean': round(m, 3), 'q95_random': round(q95, 3), 'share_pos': round(share, 3),
            'median_random': round(float(np.median(draws)), 3), 'why': '; '.join(why)}


def analyze(df, pair, tf, filt):
    rng = np.random.default_rng(RNG_SEED)
    cell = df[(df['filter'] == filt)]
    g = cell[(cell.path == 'mag') & (cell.labels == 'normal')]
    grev = cell[(cell.path == 'mag') & (cell.labels == 'rev')]
    gtv = cell[(cell.path == 'tv') & (cell.labels == 'normal')]
    res = {'pair': pair, 'tf': tf, 'filter': filt}
    pool = pool_of(g, pair)
    res['pool'] = int(len(pool))
    gg = g[g.tag == 'grid']
    res['grid_share_pos'] = round(float((gg[PRE + 'net_pct'] > 0).mean()), 3)
    res['grid_best'] = brief(gg.loc[gg[PRE + 'net_pct'].idxmax()])
    res['grid_share_expo_ok'] = round(float((gg[PRE + 'max_expo'] <= MAX_EXPO + 1e-9).mean()), 3)
    if not len(pool):
        res.update({'share_pos_full': 0.0, 'share_pos_both_halves': 0.0, 'median_net': None, 'best_full': None, 'pick': None,
                    'why_no_pick': 'no setting left after the noise floor and the 1x margin limit',
                    'forward': {'pass': False, 'why': 'empty pool'}, 'reverse': {'pass': False, 'why': 'empty pool'},
                    'file': False, 'reasons': ['no setting left after the noise floor and the 1x margin limit']})
        tvgrid = gtv[gtv.tag == 'grid']
        tvbest = tvgrid.loc[tvgrid[PRE + 'net_pct'].idxmax()]
        k = key_of(tvbest)
        mag_same = gg[[key_of(r) == k for _, r in gg.iterrows()]]
        res['tv_best'] = {'tv': brief(tvbest), 'tv0_net_pct': num(tvbest['tv0_net_pct']),
                          'on_1m_data': brief(mag_same.iloc[0]) if len(mag_same) else None}
        d_mag, d_tv, d_rev = g[g.tag == 'default'], gtv[gtv.tag == 'default'], grev[grev.tag == 'default']
        res['default'] = {'mag': brief(d_mag.iloc[0]), 'tv': brief(d_tv.iloc[0]), 'tv_tv0_net_pct': num(d_tv.iloc[0]['tv0_net_pct']),
                          'rev_mag': brief(d_rev.iloc[0])}
        return res
    res['share_pos_full'] = round(float((pool[PRE + 'net_pct'] > 0).mean()), 3)
    res['share_pos_both_halves'] = round(float(((pool[PRE + 'h1r_pct'] > 0) & (pool[PRE + 'h2r_pct'] > 0)).mean()), 3)
    res['median_net'] = round(float(pool[PRE + 'net_pct'].median()), 2)
    bestfull = pool.loc[pool[PRE + 'net_pct'].idxmax()]
    res['best_full'] = brief(bestfull)
    # what TradingView (no Bar Magnifier) would rank first, and how it does on 1-minute data
    tvgrid = gtv[gtv.tag == 'grid']
    tvbest = tvgrid.loc[tvgrid[PRE + 'net_pct'].idxmax()]
    k = key_of(tvbest)
    mag_same = g[g.tag == 'grid'][[key_of(r) == k for _, r in g[g.tag == 'grid'].iterrows()]]
    res['tv_best'] = {'tv': brief(tvbest), 'tv0_net_pct': num(tvbest['tv0_net_pct']),
                      'on_1m_data': brief(mag_same.iloc[0]) if len(mag_same) else None}
    # the script's default
    d_mag = g[g.tag == 'default']
    d_tv = gtv[gtv.tag == 'default']
    d_rev = grev[grev.tag == 'default']
    res['default'] = {'mag': brief(d_mag.iloc[0]) if len(d_mag) else None,
                      'tv': brief(d_tv.iloc[0]) if len(d_tv) else None,
                      'tv_tv0_net_pct': num(d_tv.iloc[0]['tv0_net_pct']) if len(d_tv) else None,
                      'rev_mag': brief(d_rev.iloc[0]) if len(d_rev) else None}
    pk, why = pick(pool)
    res['pick'] = None
    res['why_no_pick'] = why
    if pk is not None:
        kk = key_of(pk)
        rv = grev[grev.tag == 'grid']
        rv = rv[[key_of(r) == kk for _, r in rv.iterrows()]]
        tv = gtv[gtv.tag == 'grid']
        tv = tv[[key_of(r) == kk for _, r in tv.iterrows()]]
        rvr = rv.iloc[0] if len(rv) else None
        tvr = tv.iloc[0] if len(tv) else None
        ctrl = rvr is not None and pk[PRE + 'h1r_pct'] > rvr[PRE + 'h1r_pct'] and pk[PRE + 'h2r_pct'] > rvr[PRE + 'h2r_pct']
        stress_ok = float(pk['stress_net_pct']) > 0
        res['pick'] = brief(pk)
        res['pick'].update({'key': list(kk), 'trailAct': num(pk['trailAct']), 'trailOff': num(pk['trailOff']),
                            'trailOn': bool(pk['trailOn']), 'slOn': bool(pk['slOn']), 'slDist': num(pk['slDist']),
                            'score': round(float(pk['score']), 3), 'nb_mean_worst': round(float(pk['nb_mean_worst']), 3),
                            'n_nb': int(pk['n_nb']), 'tv0_net_pct': num(pk['tv0_net_pct']),
                            'stress_net_pct': num(pk['stress_net_pct'])})
        res['pick_rev'] = brief(rvr)
        res['pick_tv'] = brief(tvr)
        res['pick_tv_tv0_net_pct'] = num(tvr['tv0_net_pct']) if tvr is not None else None
        res['control_pass'] = bool(ctrl)
        res['stress_pass'] = bool(stress_ok)
    res['forward'] = holdout(pool, rng, True)
    res['reverse'] = holdout(pool, rng, False)
    reasons = []
    if pk is None:
        reasons.append('no pick: ' + why)
    else:
        if not res['control_pass']:
            reasons.append('signal control failed: the same exit with every label reversed makes as much or more in a half '
                           f"(normal {pk[PRE + 'h1r_pct']:+.2f} / {pk[PRE + 'h2r_pct']:+.2f}, reversed "
                           f"{(rvr[PRE + 'h1r_pct'] if rvr is not None else float('nan')):+.2f} / {(rvr[PRE + 'h2r_pct'] if rvr is not None else float('nan')):+.2f})")
        if not res['stress_pass']:
            reasons.append(f"stressed costs {float(pk['stress_net_pct']):+.2f}%")
    if not res['forward']['pass']:
        reasons.append('forward hold-out failed: ' + res['forward']['why'])
    if not res['reverse']['pass']:
        reasons.append('reverse hold-out failed: ' + res['reverse']['why'])
    res['file'] = not reasons
    res['reasons'] = reasons
    return res


def main(argv):
    pairs = argv or ['BTC', 'XAU']
    out = {}
    for pair in pairs:
        for tf in TFS:
            f = W + f'out/sweep_{pair}_{tf}.parquet'
            if not os.path.exists(f):
                continue
            df = pd.read_parquet(f)
            if 'labels' not in df.columns:
                print('skip (no labels column):', f)
                continue
            for filt in ('off', 'on'):
                r = analyze(df, pair, tf, filt)
                out[f'{pair}|{tf}|{filt}'] = r
                p = r['pick']
                print(f"{pair} {tf:>3} {filt:3}: grid pos {r['grid_share_pos']:.0%} best {r['grid_best']['setting']} {r['grid_best']['net_pct']} | pool {r['pool']} pos {r['share_pos_full']:.0%} both {r['share_pos_both_halves']:.0%} "
                      f"| pick {p['setting'] if p else '-'} net {p['net_pct'] if p else '-'} "
                      f"rev {r.get('pick_rev', {}) and r['pick_rev']['net_pct']} stress {p['stress_net_pct'] if p else '-'} "
                      f"| fwd {r['forward'].get('pass')} rev {r['reverse'].get('pass')} ctrl {r.get('control_pass')} -> {'FILE' if r['file'] else 'no file'}",
                      flush=True)
    json.dump(out, open(W + 'out/sweep_rule.json', 'w'), indent=1, default=str)


if __name__ == '__main__':
    main(sys.argv[1:])
