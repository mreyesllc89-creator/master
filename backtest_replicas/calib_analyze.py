"""Rule C (CALIB_SPEC.md) on the calibration grids out/calib_<strategy>_<PAIR>_<TF>.parquet.

Usage: python3 -I calib_analyze.py <strategy> [PAIR [TF ...]]   -> out/calib_rule_<strategy>.json

Everything is scored on 1-minute fills with our costs, on the fair halves (h1r_pct / h2r_pct:
trades entered in each half of the window, each half compounded from a fresh start).

1. Pool: every grid setting; settings with identical results (trades, net, both halves) count
   once. Eligible = pool settings with at least MIN_TR trades entered in each half.
2. Candidates: eligible and positive in both halves.
3. Pick: among the TOPN best candidates by worst half, the best by
   0.5 x worst half + 0.5 x mean worst half of its grid neighbours. Neighbours = grid settings
   that differ in exactly one dimension (one step for an ordinal dimension, any other value for a
   categorical one; a dimension that is unused (None) on one side follows its switch). The
   direction (Normal / Inverted) is never a neighbour: its flip is the control of step 5.
   Neighbours with the candidate's own result, and repeated results, do not count. At least
   MIN_NB neighbours with a positive mean are required.
4. Hold-outs, both directions with the same bar: the TOPN best eligible settings by one half
   must, on the other half, beat 95% of random TOPN-draws from the eligible pool, be at least
   60% positive and have a positive mean.
5. Direction control: the pick beats the same setting with the direction flipped in both halves.
6. Stressed costs: the pick stays positive in both halves (re-run through calib_<s>.py --one).
7. Nested picks (rule C2, added after the audit of the ApexForge / HRD calibration, reported for
   every cell and required from the XPW calibration on): steps 2-3 applied to ONE half only
   (candidates = positive in that half with MIN_TR+ trades in it; the TOPN best by that half;
   plateau = neighbours' mean of that half), and the setting so chosen scored on the OTHER half:
   it must be positive there and beat its direction-flipped twin there. Both ways.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__)) + '/'
TFS = ['1', '5', '15', '30', '60', '120', '240']
MIN_TR, TOPN, MIN_NB, NRAND, SEED = 30, 40, 5, 5000, 20261124
DIR_NAMES = ('inv', 'apxinv', 'hrdinv', 'xpwinv', 'direction', 'inverted')
KEEP = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'h1r_pct', 'h2r_pct', 'h1_trades', 'h2_trades',
        'avg_bars_held', 'exposure', 'long', 'short', 'long_trades', 'short_trades')


def isna(v):
    return v is None or (isinstance(v, float) and np.isnan(v))


def native(v):
    if isna(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return float(v)
    return v


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if not np.isfinite(f) else round(f, 4)


def codes_of(df, D):
    """n x len(D) integer codes: index of the value in the dimension's list, -1 when unused."""
    C = np.full((len(df), len(D)), -1, dtype=np.int64)
    for j, d in enumerate(D):
        col = df['p_' + d['name']]
        na = col.isna().to_numpy()
        vals = col.to_numpy(dtype=object)
        for i, v in enumerate(d['values']):
            if isna(v):
                continue
            if isinstance(v, bool):
                m = np.array([(not isna(x)) and isinstance(x, (bool, np.bool_)) and bool(x) == v for x in vals])
            elif isinstance(v, (int, float)):
                m = np.array([(not isna(x)) and not isinstance(x, (bool, np.bool_, str)) and abs(float(x) - float(v)) < 1e-9 for x in vals])
            else:
                m = np.array([(not isna(x)) and x == v for x in vals])
            C[m, j] = i
        assert ((C[:, j] >= 0) | na).all(), f"dimension {d['name']}: a value is not in DIMS"
    return C


def label(D, row):
    parts = []
    for d in D:
        v = native(row['p_' + d['name']])
        if v is None:
            continue
        parts.append(f"{d['name']}={v:g}" if isinstance(v, float) else f"{d['name']}={v}")
    return ', '.join(parts)


def pvals(D, row):
    return {d['name']: native(row['p_' + d['name']]) for d in D}


def brief(D, row):
    if row is None:
        return None
    out = {'setting': label(D, row), 'p': pvals(D, row)}
    for k in KEEP:
        if k in row.index:
            out[k] = num(row[k])
    return out


def neighbours(C, D, jdir, i):
    c = C[i]
    both = (C >= 0) & (c >= 0)
    diff = both & (C != c)
    bad = np.zeros(len(C), dtype=bool)
    for j, d in enumerate(D):
        if d.get('kind') == 'ordinal':
            bad |= diff[:, j] & (np.abs(C[:, j] - c[j]) != 1)
    ok = (diff.sum(axis=1) == 1) & ~bad & ~diff[:, jdir]
    return np.flatnonzero(ok)


def holdout(el, rng, fwd):
    a, b = ('h1r_pct', 'h2r_pct') if fwd else ('h2r_pct', 'h1r_pct')
    if len(el) < 2 * TOPN:
        return {'pass': False, 'why': f'eligible pool too small ({len(el)})'}
    top = el.sort_values(a, ascending=False, kind='mergesort').head(TOPN)
    m, share = float(top[b].mean()), float((top[b] > 0).mean())
    vals = el[b].to_numpy()
    draws = np.array([vals[rng.choice(len(vals), TOPN, replace=False)].mean() for _ in range(NRAND)])
    q95 = float(np.quantile(draws, 0.95))
    why = []
    if not m > q95:
        why.append(f'mean {m:+.2f}% not above the random 95th percentile {q95:+.2f}%')
    if share < 0.6:
        why.append(f'only {share:.0%} positive')
    if m <= 0:
        why.append(f'mean {m:+.2f}% not positive')
    return {'pass': not why, 'mean': round(m, 3), 'q95': round(q95, 3), 'share_pos': round(share, 3),
            'median_random': round(float(np.median(draws)), 3), 'why': '; '.join(why)}


def nested(df, pool, C, D, jdir, a, b, ta):
    """Steps 2-3 on half `a` only; the setting chosen is scored on half `b`."""
    cand = pool[(pool[a] > 0) & (pool[ta] >= MIN_TR)]
    if not len(cand):
        return {'pass': False, 'why': 'no setting is positive in the selection half with 30+ trades in it'}
    best, bs = None, -np.inf
    for i, r in cand.sort_values(a, ascending=False, kind='mergesort').head(TOPN).iterrows():
        nbd = df.loc[neighbours(C, D, jdir, i)]
        nbd = nbd[nbd.in_floor & (nbd.sig != r['sig'])]
        nbd = nbd[~nbd.sig.duplicated(keep='first')]
        if len(nbd) < MIN_NB:
            continue
        m = float(nbd[a].mean())
        if m <= 0:
            continue
        sc = 0.5 * r[a] + 0.5 * m
        if sc > bs:
            best, bs = i, sc
    if best is None:
        return {'pass': False, 'why': 'no plateau in the selection half'}
    r = df.loc[best]
    tw = C[best].copy()
    tw[jdir] = 1 - tw[jdir]
    tm = (C == tw).all(axis=1)
    twin = df[tm].iloc[0] if tm.any() else None
    ok = bool(r[b] > 0 and twin is not None and r[b] > twin[b])
    why = '' if ok else (f'the setting chosen on one half makes {r[b]:+.2f}% on the other' if not r[b] > 0 else 'its direction-flipped twin does as well on the other half')
    return {'pass': ok, 'setting': label(D, r), 'selection_half': num(r[a]), 'other_half': num(r[b]),
            'twin_other_half': num(twin[b]) if twin is not None else None, 'why': why}


def one(strat, pair, tf, p, path, cost):
    r = subprocess.run([sys.executable, '-I', W + f'calib_{strat}.py', '--one', pair, tf, json.dumps(p), '--path', path, '--cost', cost],
                       capture_output=True, text=True, cwd=W)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    txt = r.stdout
    return json.loads(txt[txt.index('{'):])


def analyze(strat, pair, tf, D, default_p=None, verify=True):
    df = pd.read_parquet(W + f'out/calib_{strat}_{pair}_{tf}.parquet').reset_index(drop=True)
    jdir = next(j for j, d in enumerate(D) if d['name'].lower() in DIR_NAMES)
    dname = 'p_' + D[jdir]['name']
    C = codes_of(df, D)
    df['worst'] = np.minimum(df.h1r_pct, df.h2r_pct)
    sig = (df.trades.astype(str) + '|' + df.net_pct.round(6).astype(str) + '|' + df.h1r_pct.round(6).astype(str) + '|' + df.h2r_pct.round(6).astype(str))
    df['sig'] = sig
    # rows a runner marks floor_ok False (a trailing offset below the 1-minute noise floor of this
    # cell) are computed but are not in the pool and are not neighbours
    fl = df['floor_ok'].astype(bool) if 'floor_ok' in df.columns else pd.Series(True, index=df.index)
    df['in_floor'] = fl
    pool = df[fl]
    pool = pool[~pool.sig.duplicated(keep='first')]
    el = pool[(pool.h1_trades >= MIN_TR) & (pool.h2_trades >= MIN_TR)]
    cand = el[(el.h1r_pct > 0) & (el.h2r_pct > 0)]
    res = {'strategy': strat, 'pair': pair, 'tf': tf, 'settings': int(len(df)), 'pool': int(len(pool)), 'eligible': int(len(el)),
           'below_floor': int((~fl).sum()), 'candidates': int(len(cand)), 'share_net_pos': round(float((pool.net_pct > 0).mean()), 4),
           'share_both_pos_eligible': round(float(len(cand)) / max(1, len(el)), 4)}
    # by direction
    res['by_direction'] = {}
    for v, nm in ((False, 'normal'), (True, 'inverted')):
        g, ge, gc = pool[pool[dname] == v], el[el[dname] == v], cand[cand[dname] == v]
        best = ge.loc[ge.net_pct.idxmax()] if len(ge) else None
        bw = ge.loc[ge.worst.idxmax()] if len(ge) else None
        res['by_direction'][nm] = {'pool': int(len(g)), 'eligible': int(len(ge)), 'candidates': int(len(gc)),
                                   'share_net_pos': round(float((g.net_pct > 0).mean()), 4) if len(g) else None,
                                   'median_net': num(g.net_pct.median()) if len(g) else None,
                                   'median_net_eligible': num(ge.net_pct.median()) if len(ge) else None,
                                   'best_net': brief(D, best), 'best_worst_half': brief(D, bw)}
    # marginals of every dimension on the eligible pool
    res['marginals'] = {}
    for d in D:
        col, m = 'p_' + d['name'], {}
        for v in d['values']:
            if isna(v):
                continue
            ge = el[el[col] == v]
            m[str(v)] = {'eligible': int(len(ge)), 'candidates': int(((ge.h1r_pct > 0) & (ge.h2r_pct > 0)).sum()),
                         'median_net': num(ge.net_pct.median()) if len(ge) else None,
                         'median_worst': num(ge.worst.median()) if len(ge) else None}
        res['marginals'][d['name']] = m
    # the script's default setting, both directions
    res['default'] = None
    if default_p:
        dp = {k[2:] if k.startswith('p_') else k: v for k, v in default_p.items()}
        out = {}
        for v, nm in ((False, 'normal'), (True, 'inverted')):
            m = np.ones(len(df), dtype=bool)
            for d in D:
                want = v if d['name'] == D[jdir]['name'] else dp.get(d['name'])
                col = df['p_' + d['name']]
                m &= col.isna().to_numpy() if isna(want) else np.array([(not isna(x)) and x == want for x in col.to_numpy(dtype=object)])
            out[nm] = brief(D, df[m].iloc[0]) if m.any() else None
        res['default'] = out
    # pick
    pk, why, tried = None, None, 0
    if not len(cand):
        why = 'no setting is positive in both halves with 30+ trades in each'
    else:
        best_sc = -np.inf
        for i, r in cand.sort_values('worst', ascending=False, kind='mergesort').head(TOPN).iterrows():
            nb = neighbours(C, D, jdir, i)
            nbd = df.loc[nb]
            nbd = nbd[nbd.in_floor & (nbd.sig != r['sig'])]
            nbd = nbd[~nbd.sig.duplicated(keep='first')]
            tried += 1
            if len(nbd) < MIN_NB:
                continue
            m = float(nbd.worst.mean())
            if m <= 0:
                continue
            sc = 0.5 * r['worst'] + 0.5 * m
            if sc > best_sc:
                best_sc, pk = sc, r.copy()
                pk['score'], pk['nb_mean'], pk['n_nb'], pk['nb_pos'], pk['row'] = sc, m, len(nbd), float((nbd.worst > 0).mean()), i
        if pk is None:
            why = f'none of the {tried} best candidates sits on a plateau ({MIN_NB}+ different neighbours with a positive mean worst half)'
    res['pick'], res['why_no_pick'] = None, why
    reasons = []
    rng = np.random.default_rng(SEED)
    res['forward'], res['reverse'] = holdout(el, rng, True), holdout(el, rng, False)
    res['nested_fwd'] = nested(df, pool, C, D, jdir, 'h1r_pct', 'h2r_pct', 'h1_trades')
    res['nested_rev'] = nested(df, pool, C, D, jdir, 'h2r_pct', 'h1r_pct', 'h2_trades')
    if pk is not None:
        b = brief(D, pk)
        b.update({'score': round(float(pk['score']), 3), 'nb_mean': round(float(pk['nb_mean']), 3), 'n_nb': int(pk['n_nb']),
                  'nb_share_pos': round(float(pk['nb_pos']), 3)})
        res['pick'] = b
        i = int(pk['row'])
        tw = C[i].copy()
        tw[jdir] = 1 - tw[jdir]
        tm = (C == tw).all(axis=1)
        twin = df[tm].iloc[0] if tm.any() else None
        res['pick_twin'] = brief(D, twin)
        res['control_pass'] = bool(twin is not None and pk.h1r_pct > twin.h1r_pct and pk.h2r_pct > twin.h2r_pct)
        if not res['control_pass']:
            reasons.append('the direction-flipped twin does as well in a half')
        if verify:
            p = pvals(D, pk)
            st = one(strat, pair, tf, p, 'mag', 'stress')
            tv = one(strat, pair, tf, p, 'tv', 'tv')
            chk = one(strat, pair, tf, p, 'mag', 'ours')
            res['pick_recheck_ok'] = bool(abs(chk['net_pct'] - pk.net_pct) < 1e-6 and int(chk['trades']) == int(pk.trades))
            res['pick_stress'] = {k: num(st[k]) for k in ('net_pct', 'h1r_pct', 'h2r_pct', 'trades', 'pf')}
            res['pick_tv'] = {k: num(tv[k]) for k in ('net_pct', 'h1r_pct', 'h2r_pct', 'trades', 'pf', 'win_pct', 'max_dd_pct')}
            res['stress_pass'] = bool(st['h1r_pct'] > 0 and st['h2r_pct'] > 0)
            if not res['stress_pass']:
                reasons.append(f"stressed costs: halves {st['h1r_pct']:+.2f}% / {st['h2r_pct']:+.2f}%")
            if not res['pick_recheck_ok']:
                reasons.append('the pick does not reproduce through --one')
    else:
        reasons.append('no pick: ' + why)
    if not res['forward']['pass']:
        reasons.append('forward hold-out failed: ' + res['forward']['why'])
    if not res['reverse']['pass']:
        reasons.append('reverse hold-out failed: ' + res['reverse']['why'])
    res['passes'], res['reasons'] = not reasons, reasons
    # rule C2 = rule C + the nested picks, both ways
    r2 = list(reasons)
    for nm, k in (('forward', 'nested_fwd'), ('reverse', 'nested_rev')):
        if not res[k]['pass']:
            r2.append(f'nested {nm} pick failed: ' + res[k]['why'])
    res['passes_c2'], res['reasons_c2'] = not r2, r2
    return res


def main(argv):
    strat = argv[0]
    pairs = [argv[1]] if len(argv) > 1 else ['BTC', 'XAU']
    tfs = argv[2:] if len(argv) > 2 else TFS
    D = json.load(open(W + f'out/calib_{strat}_dims.json'))
    sys.path.insert(0, W)
    try:
        mod = __import__(f'calib_{strat}')
        default_p = getattr(mod, 'DEFAULT_P', None) or getattr(mod, 'DEFAULT', None)
    except Exception as e:  # the default rows are informative only
        print('no default setting:', e)
        default_p = None
    fn = W + f'out/calib_rule_{strat}.json'
    out = json.load(open(fn)) if os.path.exists(fn) else {}
    for pair in pairs:
        for tf in tfs:
            if not os.path.exists(W + f'out/calib_{strat}_{pair}_{tf}.parquet'):
                continue
            r = analyze(strat, pair, tf, D, default_p)
            out[f'{pair}|{tf}'] = r
            bd, p = r['by_direction'], r['pick']
            print(f"{strat} {pair} {tf:>3} | pool {r['pool']:>6} eligible {r['eligible']:>6} cand {r['candidates']:>5} "
                  f"(normal {bd['normal']['candidates']}, inverted {bd['inverted']['candidates']}) | fwd {'ok' if r['forward']['pass'] else 'no'} "
                  f"rev {'ok' if r['reverse']['pass'] else 'no'} | pick {(p['setting'] + ' net ' + str(p['net_pct'])) if p else '-'} "
                  f"| nested {'ok' if r['nested_fwd']['pass'] else 'no'}/{'ok' if r['nested_rev']['pass'] else 'no'} "
                  f"| C {'PASS' if r['passes'] else 'no'} C2 {'PASS' if r['passes_c2'] else 'no'}: {'; '.join(x.split(':')[0] for x in r['reasons'])}", flush=True)
            json.dump(out, open(fn, 'w'), indent=1, default=str)


if __name__ == '__main__':
    main(sys.argv[1:])
