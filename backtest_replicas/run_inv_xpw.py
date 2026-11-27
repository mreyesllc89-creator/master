"""run_inv_xpw.py: XPW v2.8 trailing-TP + FlashGold Direction Filter, Update 1 "Inverted direction:
opposite side at the same entries", by timeframe (INV_BT_SPEC.md, task 3).

Usage: python3 -I run_inv_xpw.py PAIR TF [TF ...]      -> out/inv_xpw_<PAIR>_<TF>.json

Full window run_tf.WINDOWS[PAIR] (BTC 1731801600..1794873600, XAU 1483315200..1529366400), the
script's default inputs (trail activation 2.0 / offset 1.0 in price units, no stop loss, Trade
direction Both, Max open entries 20, Signal tick, "Blocked entry still closes the other side"
on). Runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

    direction  normal = the option off; inverted = xpwInv on (the Pine at HEAD, Update 1)
    filter     "Enable filter" off / on
    path       tv  = TradingView without Bar Magnifier (one O-H-L-C / O-L-H-C path per chart bar)
               mag = Bar Magnifier on 1-minute data (exit orders walked along the 1-minute bars)
    cost       script = what TradingView shows with the script's own Properties (no commission,
                        no slippage)
               ours   = XAU $0.30 per ounce per round trip; BTC 0.02% of price per side + $0.20
                        per coin per round trip

Money model = run_tf.metrics / sweep_core.metrics_fast: 10,000 initial capital, every entry 10%
of the closed equity at its entry (the script's default quantity), compounding.

json: runs[direction][filter][path][cost] = the full summary (trades, net_pct, pf, win_pct,
max_dd_pct, half1_pct / half2_pct, the fair halves h1r_pct / h2r_pct with h1_trades / h2_trades
and h1r_pf / h2r_pf, long_trades / short_trades = the REAL sides, exit_trail / exit_sl /
exit_close_all / exit_reverse / exit_end, avg_bars_held, max_expo = the largest open notional
over closed equity, max_concurrent, avg_trade_ret_pct, entries_skipped_room,
entries_ignored_pyramiding, close_all_bars). rev_labels[filter][path][cost] = the same for the
existing reversed-label run ("Reverse every label" on, the option off), for reference.
funnel[...] = the engine's entry funnel (FGD counts on the filter's side, entries on the real
side). checks = what the runner verified while running (see _checks).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import sweep_core as sc   # noqa: E402
import engine             # noqa: E402
import run_tf             # noqa: E402

OUT = os.path.join(W, 'out')
COSTS = (('script', 'tv0'), ('ours', 'cost'))      # our cost name -> sweep_core cost mode
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = (('off', False), ('on', True))
PATHS = ('tv', 'mag')
ARR = ('dir', 'erow', 'k', 'epx', 'xrow', 'xpx', 'xkind')
REF_KEYS = ('trades', 'net_pct', 'pf', 'win_pct', 'max_dd_pct', 'half1_pct', 'half2_pct', 'avg_trade_ret_pct',
            'max_concurrent')


def _clean(v):
    """JSON-safe scalar: numpy -> Python, NaN -> None."""
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return None if math.isnan(v) else v
    return v


def _same(a, b):
    an = a is None or (isinstance(a, float) and math.isnan(a))
    bn = b is None or (isinstance(b, float) and math.isnan(b))
    if an or bn:
        return an and bn
    return float(a) == float(b)


def summarize(pair, P, R, start, end):
    """{cost: summary} for one run (R = sweep_core.run_cfg output)."""
    m = sc.metrics_fast(pair, R, P['t_close'], start, end)
    nl = int((R['dir'] > 0).sum())
    out = {}
    for name, mode in COSTS:
        d = {k: _clean(v) for k, v in m[mode].items()}
        d['long_trades'] = nl
        d['short_trades'] = int(R['n']) - nl
        for k in ('entries_skipped_room', 'entries_ignored_pyramiding', 'close_all_bars', 'max_open'):
            d[k] = int(R[k])
        out[name] = d
    return out


def _same_arrays(Ra, Rb):
    return Ra['n'] == Rb['n'] and all(np.array_equal(Ra[k], Rb[k]) for k in ARR)


def _check_tv(pair, tf, sig, perm, flt, inv, summ, start, end, R, P):
    """The tv numbers against the slow path: engine.backtest's trade list (real sides) through
    run_tf.metrics, both costs, and its trade arrays against run_cfg's. Returns the engine summary."""
    tr, es = engine.backtest(pair, tf, sig, perm if flt else None, {'fgfOn': flt, 'xpwInv': inv})
    bad = []
    if len(tr) != R['n'] or (R['n'] and not (
            np.array_equal(tr['dir'].to_numpy(np.int64), R['dir'].astype(np.int64))
            and np.array_equal(tr['entry_row'].to_numpy(np.int64), P['rows'][R['erow']])
            and np.array_equal(tr['exit_row'].to_numpy(np.int64), P['rows'][R['xrow']])
            and np.array_equal(tr['entry_px'].to_numpy(), R['epx']) and np.array_equal(tr['exit_px'].to_numpy(), R['xpx']))):
        bad.append('engine.backtest trades != run_cfg trades')
    for (name, mode), with_cost in zip(COSTS, (False, True)):
        ref = run_tf.metrics(pair, tr, start, end, with_cost)
        for k in REF_KEYS:
            if k in ref and not _same(ref[k], summ[name][k]):
                bad.append('%s %s: run_tf.metrics %r vs %r' % (name, k, ref[k], summ[name][k]))
        kinds = ref.get('exit_kinds', {})
        for kn in ('trail', 'sl', 'close_all', 'reverse', 'end'):
            if int(kinds.get(kn, 0)) != summ[name]['exit_' + kn]:
                bad.append('%s exit_%s' % (name, kn))
    if bad:
        raise AssertionError('%s %s filter %s inverted %s: %s' % (pair, tf, flt, inv, '; '.join(bad[:5])))
    keep = ('sig_bars_long', 'sig_bars_short', 'sig_bars_cancelled', 'raw_long', 'raw_short', 'blocked_long',
            'blocked_short', 'go_long_bars', 'go_short_bars', 'entries', 'long_entries', 'short_entries', 'entry_bars',
            'buyOk_bars', 'sellOk_bars', 'gross_pl', 'gross_pl_long', 'gross_pl_short')
    return {k: _clean(es[k]) for k in keep}


def _saved_checks(pair, tf, out, G):
    """The option-off numbers against the files saved before Update 1 (None when a file is absent)."""
    res = {'normal_tv_equals_saved_run_json': None, 'rev_tv_equals_saved_run_json': None,
           'option_off_equals_saved_sweep_default_rows': None}
    pj = os.path.join(OUT, 'run_%s_%s.json' % (pair, tf))
    if os.path.exists(pj):
        with open(pj) as fh:
            sv = json.load(fh)['variants']
        def eq(mine, name):
            return all(_same(mine[cn][k], sv[name][mode].get(k)) for cn, mode in COSTS for k in REF_KEYS)
        res['normal_tv_equals_saved_run_json'] = bool(eq(out['runs']['normal']['off']['tv'], 'off')
                                                      and eq(out['runs']['normal']['on']['tv'], 'on'))
        res['rev_tv_equals_saved_run_json'] = bool(eq(out['rev_labels']['off']['tv'], 'rev_off')
                                                   and eq(out['rev_labels']['on']['tv'], 'rev_on'))
    pp = os.path.join(OUT, 'sweep_%s_%s.parquet' % (pair, tf))
    if os.path.exists(pp):
        df = pd.read_parquet(pp)
        df = df[df['tag'] == 'default']
        ok = len(df) == 8
        for _, row in df.iterrows():
            mine = (out['runs']['normal'] if row['labels'] == 'normal' else out['rev_labels'])[row['filter']][row['path']]
            for cn, mode in COSTS:
                for k in sc.METRIC_COLS:
                    ok = ok and _same(mine[cn][k], row[mode + '_' + k])
        res['option_off_equals_saved_sweep_default_rows'] = bool(ok)
    return res


def run(pair, tf):
    tf = str(tf)
    t0 = time.time()
    start, end = run_tf.WINDOWS[pair]
    sc.check_mag_sync()
    sig, perm = sc.load_inputs(pair, tf, verbose=False)
    sig_rev = sc.load_sig(pair, tf, 'rev', verbose=False)
    t_in = time.time() - t0
    G = sc.grid()
    cfg = G[-1]                                         # the script's own exit defaults
    assert cfg['tag'] == 'default'
    d = engine.DEFAULTS
    out = {'strategy': 'xpw', 'pair': pair, 'tf': tf, 'start': int(start), 'end': int(end), 'bars': int(len(sig)),
           'pine': 'xpw_orientation_tdi_v2.8_strategy_trailtp_FGF.pine at HEAD d28ba97 (Update 1)',
           'inputs': {k: (bool(v) if isinstance(v, bool) else v) for k, v in d.items() if k not in ('xpwInv', 'fgfOn')},
           'costs': {'script': 'none (the script declares no commission or slippage)',
                     'ours': 'XAU $0.30 per ounce per round trip; BTC 0.02% of price per side + $0.20 per coin per round trip'},
           'money': '10,000 initial capital, every entry 10% of the closed equity at its entry, compounding '
                    '(run_tf.metrics / sweep_core.metrics_fast)',
           'perm_share': {'buyOk': round(float(perm['buyOk'].mean()), 3), 'sellOk': round(float(perm['sellOk'].mean()), 3)},
           'runs': {}, 'rev_labels': {},
           'funnel_note': 'engine.backtest summary of the tv run: sig / raw / blocked / go counts are candles on the '
                          "filter's side (a raw_long of the inverted run is placed as a sell); long_entries / "
                          'short_entries and gross_pl_* (price units per 1 unit, no cost) are the REAL sides',
           'funnel': {'normal': {}, 'inverted': {}, 'rev_labels': {}}}
    sub = None
    Rs = {}
    for dname, inv in DIRECTIONS:
        out['runs'][dname] = {}
        for fname, flt in FILTERS:
            P = sc.prep(pair, tf, sig, perm, flt, inv=inv)
            if sub is None:
                sub = sc.sub_bars(pair, tf, P['rows'])
                sc.warmup()
                sc.check_mag_equiv(P)
            out['runs'][dname][fname] = {}
            for path in PATHS:
                R = sc.run_cfg(P, cfg, path, sub=sub)
                Rs[(dname, fname, path)] = R
                out['runs'][dname][fname][path] = summarize(pair, P, R, start, end)
            out['funnel'][dname][fname] = _check_tv(pair, tf, sig, perm, flt, inv, out['runs'][dname][fname]['tv'],
                                                    start, end, Rs[(dname, fname, 'tv')], P)
    for fname, flt in FILTERS:                           # the existing reversed-label runs, option off
        P = sc.prep(pair, tf, sig_rev, perm, flt)
        out['rev_labels'][fname] = {}
        for path in PATHS:
            R = sc.run_cfg(P, cfg, path, sub=sub)
            Rs[('rev', fname, path)] = R
            out['rev_labels'][fname][path] = summarize(pair, P, R, start, end)
        out['funnel']['rev_labels'][fname] = _check_tv(pair, tf, sig_rev, perm, flt, False, out['rev_labels'][fname]['tv'],
                                                       start, end, Rs[('rev', fname, 'tv')], P)
    # the header's statement, on this very run: filter off, inverted places the trades of "Reverse every label"
    checks = {'inverted_filter_off_equals_rev_labels_filter_off':
              {p: bool(_same_arrays(Rs[('inverted', 'off', p)], Rs[('rev', 'off', p)])) for p in PATHS},
              # expected True: with the filter on the two are judged in opposite zones
              'inverted_filter_on_differs_from_rev_labels_filter_on':
              {p: bool(not _same_arrays(Rs[('inverted', 'on', p)], Rs[('rev', 'on', p)])) for p in PATHS},
              'tv_numbers_equal_engine_backtest_plus_run_tf_metrics': True}
    if not all(checks['inverted_filter_off_equals_rev_labels_filter_off'].values()):
        raise AssertionError('%s %s: filter off, inverted != reversed labels' % (pair, tf))
    checks.update(_saved_checks(pair, tf, out, G))
    for k in ('normal_tv_equals_saved_run_json', 'rev_tv_equals_saved_run_json', 'option_off_equals_saved_sweep_default_rows'):
        if checks[k] is False:
            raise AssertionError('%s %s: %s is False' % (pair, tf, k))
    out['checks'] = checks
    out['timing_s'] = {'inputs': round(t_in, 1), 'total': round(time.time() - t0, 1)}
    os.makedirs(OUT, exist_ok=True)
    path_out = os.path.join(OUT, 'inv_xpw_%s_%s.json' % (pair, tf))
    tmp = path_out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as fh:
        json.dump(out, fh, indent=1, allow_nan=False)
    os.replace(tmp, path_out)
    return out, path_out


def show(out):
    def line(tag, x):
        s, o = x['script'], x['ours']
        f = lambda v, w, p: ('%*.*f' % (w, p, v)) if v is not None else ' ' * (w - 1) + '-'
        return ('  %-22s %5d %5d/%-5d | script net %s%% pf %s win %s%% dd %s%% h1r %s h2r %s | ours net %s%% pf %s win %s%% dd %s%% '
                'h1r %s h2r %s | exits tr %d sl %d ca %d rev %d end %d | bars %.2f expo %s'
                % (tag, s['trades'], s['long_trades'], s['short_trades'],
                   f(s['net_pct'], 8, 2), f(s['pf'], 6, 2), f(s['win_pct'], 5, 1), f(s['max_dd_pct'], 6, 2), f(s['h1r_pct'], 7, 2), f(s['h2r_pct'], 7, 2),
                   f(o['net_pct'], 8, 2), f(o['pf'], 6, 2), f(o['win_pct'], 5, 1), f(o['max_dd_pct'], 6, 2), f(o['h1r_pct'], 7, 2), f(o['h2r_pct'], 7, 2),
                   s['exit_trail'], s['exit_sl'], s['exit_close_all'], s['exit_reverse'], s['exit_end'],
                   s['avg_bars_held'] if s['avg_bars_held'] is not None else float('nan'), f(s['max_expo'], 5, 2)))
    print('%s %s: %d bars, window %d..%d, default inputs; columns: trades long/short | cost script | cost ours | exit kinds | '
          'avg bars held, max exposure' % (out['pair'], out['tf'], out['bars'], out['start'], out['end']))
    for path in PATHS:
        for fname, _ in FILTERS:
            for dname, _ in DIRECTIONS:
                print(line('%s filter %-3s %s' % (path, fname, dname), out['runs'][dname][fname][path]))
            print(line('%s filter %-3s %s' % (path, fname, 'rev-lbl'), out['rev_labels'][fname][path]))
    print('  checks: %s' % json.dumps(out['checks']))
    print('  timing: %s' % json.dumps(out['timing_s']), flush=True)


def main(argv):
    if len(argv) < 2 or argv[0] not in sc.PAIRS:
        print(__doc__)
        return 2
    pair = argv[0]
    for tf in argv[1:]:
        if tf not in sc.TFS:
            print('unknown timeframe %r (one of %s)' % (tf, ', '.join(sc.TFS)))
            return 2
    for tf in argv[1:]:
        out, path_out = run(pair, tf)
        show(out)
        print('  -> %s' % path_out, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
