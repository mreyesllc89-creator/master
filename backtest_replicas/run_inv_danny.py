"""run_inv_danny.py: Danny Phantom FX V10.21.1 LiveSafe + FGF [Update 1], by time frame, with the
canonical replica danny.py (REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3).

Usage: python3 -I run_inv_danny.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close)
and the script's default inputs (Preset Mode Auto, Signal direction "Inverted (V10 design)", zone
length 50, delta 1.5, EMA 100 filter on, ATR exits: stop 1.2 ATR(14), target 4.1667 R, no trail,
time stop 50 bars, dead-trade exit 15 bars, Risk 1 % sizing, max 50 units, step 0.001, capital
2,000) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = dpInv off; inverted = dpInv on (Pine input "Inverted direction: opposite side
             at the same entries", Update 1). The OLDER option "Signal direction" stays at its
             default in both; it is a separate input (see reference below).
  filter     off = "Enable filter" off (fgfOn False); on = the FlashGold Direction Filter defaults
  path       tv = one intrabar path per chart candle (TradingView without Bar Magnifier);
             mag = the exit bracket walked along the 1-minute sub-bars. Chart "1": mag == tv
  cost       script = the script's own Properties as TradingView applies them (danny cost 'tv'):
             slippage 75 ticks = 0.75 in price on every market and stop fill, against the order
             (none on the limit fill of the target), inside the fill price; commission 0.001 % of
             the fill value per fill.  ours = XAU $0.30 per ounce per round trip, BTC 0.02 % of the
             fill value per fill + $0.20 per unit per round trip, no slippage (danny cost 'ours')

and writes out/inv_danny_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>']     the full summary of danny.summary with varRollback
      True (the default: TradingView's documented rollback of `var` variables between the runs on
      one bar), plus trades_per_year, net_r_per_trade, reentry_share.
  runs_aw[...]        the same 16 keys with varRollback False ("as written, once per candle").
  reference['original/<filter>/<path>/<cost>']   the older option: Signal direction "Original
      (un-inverted)" with dpInv off (varRollback True).
  XAU "5" only (Auto = the XAUUSD 5m preset, which takes no trade on a 0.01-tick gold symbol):
  runs_manual[...], runs_manual_aw[...], reference_manual[...] = the same with presetMode "Manual".
  checks: chart "1": every mag run equals its tv run; filter off and no directional window in
      force: inverted == the other Signal direction, trade for trade (the Pine header); filter on:
      they differ.
long / short = the REAL side of each trade; raw_* / blocked_* = the normal (signal) side.
Every 'tv' result carries reentry_same_bar / reentry_leg1 / inherited (assumptions E2, E3) and
zero_qty (> 0 = the account could no longer size a trade: the result is flagged `ruined`).
--trades also saves the trade lists to out/inv_danny_trades/inv_danny_<PAIR>_<TF>_<key>.parquet.
"""
import json
import math
import os
import resource
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import danny as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_danny_trades')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = ('off', 'on')
PATHS = ('tv', 'mag')
COSTS = (('script', 'tv'), ('ours', 'ours'))
YEAR = 365.25 * 86400


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        if math.isnan(v):
            return None
        if math.isinf(v):
            return 'inf' if v > 0 else '-inf'
        return v
    return v


def same_trades(ta, tb, mirror_sig=False):
    """Two runs have the same real trades, every column (sig mirrored when asked)."""
    if len(ta) != len(tb) or list(ta.columns) != list(tb.columns):
        return False
    for c in ta.columns:
        x, y = ta[c].to_numpy(), tb[c].to_numpy()
        if c == 'sig' and mirror_sig:
            x = -x
        if x.dtype.kind == 'f':
            if not ((x == y) | (np.isnan(x) & np.isnan(y))).all():
                return False
        elif not (x == y).all():
            return False
    return True


def same_summary(a, b, skip=('path', 'direction', 'filter', 'cost', 'params', 'signalDirection')):
    for k, v in a.items():
        if k in skip:
            continue
        w = b[k]
        if isinstance(v, float) and isinstance(w, float) and math.isnan(v) and math.isnan(w):
            continue
        if v != w:
            return False
    return True


def run_cell(pair, tf, save_trades=False):
    t0 = time.time()
    tf = str(tf)
    preset_cell = pair == 'XAU' and tf == '5'
    P = {}
    for mode in (('Auto', 'Manual') if preset_cell else ('Auto',)):
        for flt in FILTERS:
            P[(mode, flt)] = M.prepare(pair, tf, {'fgfOn': flt == 'on', 'presetMode': mode})
    p0 = P[('Auto', 'off')]
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    res = dict(strategy='danny', pine='DannyPhantomFX_V10_21_1_LiveSafe_FGF.pine [Update 1]', pair=pair, tf=tf,
               window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               years=years,
               preset=('XAUUSD 5m (Preset Mode Auto matches this cell)' if p0['active']['presetXAUUSD']
                       else 'none (Preset Mode Auto matches no preset here)'),
               inputs='script defaults: Preset Mode Auto, Signal direction "Inverted (V10 design)", zone length 50, '
                      'delta 1.5, EMA 100 filter, Normal Retest Touch, ATR(14) exits (stop 1.2 ATR, target 4.1667 R, '
                      'no trail), time stop 50 bars, dead-trade exit 15 bars, loss-cluster pause 5 / 12, blackouts '
                      'on, Risk 1 % of equity, max 50 units, step 0.001, margin cap 1 %; capital 2,000; filter defaults',
               cost_modes={'script': "danny cost 'tv': the strategy() Properties as TradingView applies them: "
                                     "slippage 75 ticks = 0.75 in price per market / stop fill against the order "
                                     "(none on limit fills), inside the fill price; commission 0.001 % of the fill "
                                     "value per fill",
                           'ours': "danny cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value "
                                   "per fill + $0.20 / unit per round trip; no slippage"},
               sides='long / short = the REAL side of each trade; raw_* / blocked_* = the normal (signal) side, '
                     'the Pine FGD counts',
               assumptions='runs = varRollback True (E2); runs_aw = varRollback False. reentry_same_bar / '
                           'reentry_leg1 / inherited count the trades that rest on E3 / E2 (iii). zero_qty > 0: '
                           'the account could no longer size a trade (ruined = True)',
               runs={}, runs_aw={}, reference={}, checks={})
    if preset_cell:
        res.update(runs_manual={}, runs_manual_aw={}, reference_manual={})
    keep = {}

    def do(group, key, mode, flt, inv, path, cname, cmode, rb=True, sigdir=M.SIG_INV):
        Pk = P[(mode, flt)]
        x = {'dpInv': inv, 'path': path, 'cost': cmode, 'varRollback': rb, 'signalDirection': sigdir}
        R = M.simulate(Pk, x)
        s = dict(M.summary(Pk, R))
        nt = s['trades']
        s['trades_per_year'] = nt / years
        s['net_r_per_trade'] = (s['net_r'] / nt) if nt else None
        s['reentry_share'] = (s['reentry_same_bar'] / nt) if nt else None
        s['ruined'] = bool(s['zero_qty'] > 0)
        s.update(direction=('inverted' if inv else 'normal'), filter=flt, path=path, cost=cname,
                 signalDirection=sigdir,
                 params={'fgfOn': flt == 'on', 'presetMode': mode, 'dpInv': inv, 'signalDirection': sigdir,
                         'path': path, 'cost': cmode, 'varRollback': rb})
        res[group][key] = s
        keep[(group, key)] = M.trades(Pk, R)
        if save_trades:
            os.makedirs(TRD, exist_ok=True)
            keep[(group, key)].to_parquet(os.path.join(TRD, 'inv_danny_%s_%s_%s_%s.parquet' % (
                pair, tf, group, key.replace('/', '_'))))

    def block(mode, g_runs, g_aw, g_ref):
        for dname, inv in DIRECTIONS:
            for flt in FILTERS:
                for path in PATHS:
                    for cname, cmode in COSTS:
                        key = '%s/%s/%s/%s' % (dname, flt, path, cname)
                        do(g_runs, key, mode, flt, inv, path, cname, cmode, True)
                        do(g_aw, key, mode, flt, inv, path, cname, cmode, False)
        for flt in FILTERS:
            for path in PATHS:
                for cname, cmode in COSTS:
                    do(g_ref, 'original/%s/%s/%s' % (flt, path, cname), mode, flt, False, path, cname, cmode, True,
                       M.SIG_ORIG)

    block('Auto', 'runs', 'runs_aw', 'reference')
    if preset_cell:
        block('Manual', 'runs_manual', 'runs_manual_aw', 'reference_manual')

    # ---- checks
    def p1(g_runs, g_ref):
        out = {}
        for path in PATHS:
            for cname, _ in COSTS:
                a = keep[(g_runs, 'inverted/off/%s/%s' % (path, cname))]
                b = keep[(g_ref, 'original/off/%s/%s' % (path, cname))]
                out['%s/%s' % (path, cname)] = bool(same_trades(a, b, mirror_sig=True))
        return out

    def on_differs(g_runs, g_ref):
        out = {}
        for path in PATHS:
            a = res[g_runs]['inverted/on/%s/script' % path]
            b = res[g_ref]['original/on/%s/script' % path]
            out[path] = bool(a['trades'] != b['trades'] or a['net_pct'] != b['net_pct'])
        return out

    mag_tv = None
    if tf == '1':
        mag_tv = True
        for g in ('runs', 'runs_aw', 'reference'):
            for k in res[g]:
                if '/mag/' in k:
                    k2 = k.replace('/mag/', '/tv/')
                    if not (same_summary(res[g][k], res[g][k2]) and same_trades(keep[(g, k)], keep[(g, k2)])):
                        mag_tv = False
    res['checks'] = dict(
        mag_equals_tv_on_chart_1=mag_tv,
        filter_off_inverted_equals_original_direction=p1('runs', 'reference'),
        filter_on_inverted_differs_from_original_direction=on_differs('runs', 'reference'),
        sub_bars_equal_chart_bars=True)
    if preset_cell:
        res['checks']['manual_filter_off_inverted_equals_original_direction'] = p1('runs_manual', 'reference_manual')
        res['checks']['manual_filter_on_inverted_differs_from_original_direction'] = on_differs('runs_manual',
                                                                                              'reference_manual')
        res['checks']['auto_preset_takes_no_trade'] = bool(all(s['trades'] == 0 for s in res['runs'].values()))
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_danny_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not mag_tv:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    c = res['checks']
    if not all(c['filter_off_inverted_equals_original_direction'].values()):
        raise RuntimeError('%s %s: filter off, inverted != the other Signal direction: %r'
                           % (pair, tf, c['filter_off_inverted_equals_original_direction']))
    if preset_cell and not all(c['manual_filter_off_inverted_equals_original_direction'].values()):
        raise RuntimeError('%s %s Manual: filter off, inverted != the other Signal direction' % (pair, tf))
    return res


def line(key, s):
    def g(v, fm):
        return fm % v if v is not None and not (isinstance(v, float) and math.isnan(v)) else '   n/a'
    return ('  %-26s trades %6d (L %5d / S %5d)  net %+12.3f%%  pf %6s  win %5s%%  maxDD %7.2f%%  h1r %+9.2f h2r %+9.2f'
            '  re %5d (leg1 %4d) inh %5d zq %5d  sl/tp/rev/dead/time/blk/end %d/%d/%d/%d/%d/%d/%d' % (
                key, s['trades'], s['long'], s['short'], s['net_pct'], g(s['pf'], '%.3f'), g(s['win_pct'], '%.1f'),
                s['max_dd_pct'], s['h1r_pct'], s['h2r_pct'], s['reentry_same_bar'], s['reentry_leg1'], s['inherited'],
                s['zero_qty'], s['exit_sl'], s['exit_tp'], s['exit_reverse'], s['exit_dead'], s['exit_time'],
                s['exit_blackout'], s['exit_end']))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    save_trades = '--trades' in sys.argv
    if len(args) < 2 or args[0] not in M.WINDOWS or any(t not in TFS for t in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if len(args) > 2:
        # one fresh process per cell, one at a time: the peak memory of a 1-minute chart is then that of
        # a single cell, whatever ran before
        import subprocess
        rc = 0
        for tf in args[1:]:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), pair, tf]
                               + (['--trades'] if save_trades else []))
            rc = rc or r.returncode
        return rc
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        print('%s %s: %d bars, %d 1-minute sub-bars, preset %s, %.1fs, peak RSS %.2f GB -> out/inv_danny_%s_%s.json' % (
            pair, tf, res['bars'], res['sub_bars_1m'], res['preset'].split(' ')[0], res['seconds'],
            res['peak_rss_gb'], pair, tf))
        for g in ('runs', 'runs_aw', 'reference', 'runs_manual', 'runs_manual_aw', 'reference_manual'):
            if g in res:
                print(' %s' % g)
                for k, s in res[g].items():
                    print(line(k, s))
        print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
