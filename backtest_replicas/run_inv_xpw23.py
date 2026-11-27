"""run_inv_xpw23.py: XPW Orientation TDI v2.8 (S2 / S3 exits) + FGF [Update 1], by time frame, with the
canonical replica xpw23.py (REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3).

Usage: python3 -I run_inv_xpw23.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close)
and the script's default inputs (Signal tick, chart rung + READ HERE, every label row "enter",
ATR exits: stop 3.0 ATR(14), target 1.0 R, trailing stop 1.0 / 0.75 ATR, no time stop, Fixed 0.1
unit per entry, Max open entries 20, Trade direction Both) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = xpwInv off; inverted = xpwInv on (Pine input "Inverted direction: opposite
             side at the same entries")
  filter     off = "Enable filter" off (fgfOn False); on = the FlashGold Direction Filter defaults
  path       tv = one intrabar path per chart bar (TradingView without Bar Magnifier);
             mag = exits (and pending entries) walked along the 1-minute sub-bars. Chart "1": mag == tv
  cost       script = what TradingView shows with the script's own Properties: this strategy()
             sets no commission and no slippage, so no costs (xpw23 cost 'tv'); ours = XAU $0.30 per
             ounce per round trip, BTC 0.02 % of the fill value per fill + $0.20 per unit per round
             trip (xpw23 cost 'ours')

and writes out/inv_xpw23_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>'] = the full summary of xpw23.summary (trades, net_pct,
    pf, win_pct, max_dd_pct, the fair halves h1r_pct / h2r_pct with h1_trades / h2_trades, long /
    short = the REAL sides, raw_* / blocked_* = the label's side before the inversion, exit_<kind>
    counts, avg_bars_held, exposure, ...) plus net_R_per_trade and trades_per_year.
  reference['reversed/<filter>/<path>/<cost>'] = the older option "Reverse every label" on
    (reverseAll, xpwInv off), same summary.
  checks: chart "1": every mag run equals its tv run; filter off: inverted == reversed (the Pine
    header: either option alone places the same orders), trade for trade.
Money: 10,000 account, 0.1 unit per entry, so net_pct is the money earned by 0.1 BTC / 0.1 ounce
per entry in % of 10,000; no margin model (see xpw23_notes.md).
--trades also saves the trade lists to out/inv_xpw23_trades/inv_xpw23_<PAIR>_<TF>_<key>.parquet.
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
import xpw23 as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_xpw23_trades')
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


def same_trades(P1, R1, P2, R2):
    """Two runs have the same real trades: ids, sides, bars, prices, quantities, exit kinds, P/L."""
    a, b = M.trades(P1, R1, comments=False), M.trades(P2, R2, comments=False)
    if len(a) != len(b):
        return False
    for c in ('id', 'dir', 'sig_bar', 'k', 'entry_bar', 'exit_bar', 'exit_kind'):
        if not (a[c].to_numpy() == b[c].to_numpy()).all():
            return False
    for c in ('entry_px', 'qty', 'exit_px', 'pnl', 'eq_before'):
        x, y = a[c].to_numpy(), b[c].to_numpy()
        if not (np.abs(x - y) <= 1e-9 * np.maximum(1.0, np.maximum(np.abs(x), np.abs(y)))).all():
            return False
    return True


def same_summary(a, b, skip=('path', 'direction', 'filter', 'cost', 'params', 'labels')):
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
    P = {}
    for lab, rev in (('normal', False), ('reversed', True)):
        if rev and tf == '1':
            # chart "1": one xpw.xpw_signals call peaks near 2.4 GB by itself, so the memo caches of the
            # first two prepares are dropped before the reversed labels are computed (results unchanged)
            M.free_caches()
        for flt in FILTERS:
            pp = {'fgfOn': flt == 'on'}
            if rev:
                pp['reverseAll'] = True
            P[(lab, flt)] = M.prepare(pair, tf, pp)
    p0 = P[('normal', 'off')]
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    res = dict(strategy='xpw23', pine='xpw_orientation_tdi_v2.8_strategy_FGF.pine [Update 1]', pair=pair, tf=tf,
               window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               years=years,
               inputs='script defaults: Signal tick, chart rung + READ HERE, every label row "enter", ATR(14) exits '
                      '(stop 3.0 ATR, target 1.0 R, trail 1.0 / 0.75 ATR), no time stop, Fixed 0.1 unit per entry, '
                      'Max open entries 20, Trade direction Both; filter defaults',
               cost_modes={'script': "xpw23 cost 'tv': none (strategy() sets no commission and no slippage)",
                           'ours': "xpw23 cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value "
                                   "per fill + $0.20 / unit per round trip"},
               sides='long / short = the REAL side of each trade; raw_* / blocked_* = the label side before the '
                     'inversion (the Pine FGD counts)',
               money='10,000 account, 0.1 unit per entry (strategy.fixed), no margin model: net_pct = money '
                     'earned in % of 10,000',
               runs={}, reference={}, checks={})
    keep = {}

    def do(group, key, lab, flt, inv, path, cname, cmode):
        Pk = P[(lab, flt)]
        R = M.simulate(Pk, {'xpwInv': inv, 'path': path, 'cost': cmode})
        s = dict(M.summary(Pk, R))
        s['net_R_per_trade'] = (s['net_R'] / s['n_R']) if s['n_R'] else None
        s['trades_per_year'] = s['trades'] / years
        s.update(direction=('inverted' if inv else 'normal'), labels=lab, filter=flt, path=path, cost=cname,
                 params={'fgfOn': flt == 'on', 'reverseAll': lab == 'reversed', 'xpwInv': inv, 'path': path,
                         'cost': cmode})
        res[group][key] = s
        keep[(group, key)] = (Pk, R)
        if save_trades:
            os.makedirs(TRD, exist_ok=True)
            M.trades(Pk, R).to_parquet(os.path.join(TRD, 'inv_xpw23_%s_%s_%s.parquet' % (
                pair, tf, key.replace('/', '_'))))

    for dname, inv in DIRECTIONS:
        for flt in FILTERS:
            for path in PATHS:
                for cname, cmode in COSTS:
                    do('runs', '%s/%s/%s/%s' % (dname, flt, path, cname), 'normal', flt, inv, path, cname, cmode)
    for flt in FILTERS:
        for path in PATHS:
            for cname, cmode in COSTS:
                do('reference', 'reversed/%s/%s/%s' % (flt, path, cname), 'reversed', flt, False, path, cname, cmode)
    # checks
    inv_eq_rev = {}
    for path in PATHS:
        for cname, _ in COSTS:
            a = keep[('runs', 'inverted/off/%s/%s' % (path, cname))]
            b = keep[('reference', 'reversed/off/%s/%s' % (path, cname))]
            inv_eq_rev['%s/%s' % (path, cname)] = bool(same_trades(a[0], a[1], b[0], b[1]))
    on_differs = {}
    for path in PATHS:
        a = res['runs']['inverted/on/%s/script' % path]
        b = res['reference']['reversed/on/%s/script' % path]
        on_differs[path] = bool(a['trades'] != b['trades'] or a['net_pct'] != b['net_pct'])
    res['checks'] = dict(
        mag_equals_tv_on_chart_1=(all(same_summary(res['runs'][k], res['runs'][k.replace('/mag/', '/tv/')])
                                      for k in res['runs'] if '/mag/' in k) if tf == '1' else None),
        filter_off_inverted_equals_reversed=inv_eq_rev,
        filter_on_inverted_differs_from_reversed=on_differs,
        sub_bars_equal_chart_bars=True)
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_xpw23_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not res['checks']['mag_equals_tv_on_chart_1']:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    if not all(inv_eq_rev.values()):
        raise RuntimeError('%s %s: filter off, inverted != reversed: %r' % (pair, tf, inv_eq_rev))
    return res


def line(key, s):
    return ('  %-28s trades %6d (L %5d / S %5d)  net %+9.3f%%  pf %6.3f  win %5.1f%%  maxDD %7.2f%%  h1r %+8.3f '
            'h2r %+8.3f  R/trade %+7.4f  sl/tp/trail/rev/end %d/%d/%d/%d/%d' % (
                key, s['trades'], s['long'], s['short'], s['net_pct'], s['pf'], s['win_pct'], s['max_dd_pct'],
                s['h1r_pct'], s['h2r_pct'], s['net_R_per_trade'] if s['net_R_per_trade'] is not None else float('nan'),
                s['exit_sl'], s['exit_tp'], s['exit_trail'], s['exit_reverse'], s['exit_end']))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    save_trades = '--trades' in sys.argv
    if len(args) < 2 or args[0] not in M.WINDOWS or any(t not in TFS for t in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if len(args) > 2:
        # one fresh process per cell, one at a time: the peak memory of a 1-minute chart then is that of a
        # single prepare (inside xpw.xpw_signals), whatever ran before
        import subprocess
        rc = 0
        for tf in args[1:]:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), pair, tf]
                               + (['--trades'] if save_trades else []))
            rc = rc or r.returncode
        return rc
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        print('%s %s: %d bars, %d 1-minute sub-bars, %.1fs, peak RSS %.2f GB -> out/inv_xpw23_%s_%s.json' % (
            pair, tf, res['bars'], res['sub_bars_1m'], res['seconds'], res['peak_rss_gb'], pair, tf))
        for k, s in res['runs'].items():
            print(line(k, s))
        for k, s in res['reference'].items():
            print(line(k, s))
        print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
