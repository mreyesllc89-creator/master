"""run_inv_gvl.py: GVLiveV2 Polymarket Pre-Candle + FGF [Update 1], by time frame, with the canonical replica
gvl.py (REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3; SPEC_gvl.md section 13).

Usage: python3 -I run_inv_gvl.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close) and the
script's default inputs (EMA 8 / 21, trend EMA 100, RSI filter on, pre-candle arm on, "Market Next Candle",
radar = Chart, min vol score 35, vol rise 1, close location 0.65, trend direction on, ATR exits: stop
1 x ATR(14), target 5 R, no trail, no time stop, Risk 1 % of equity, max 50 units, step 0.001, margin cap 1 %,
daily lock: 3 losing trades per New York day, no $ lock; capital 100,000) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = gvInv off; inverted = gvInv on (Pine input "Inverted direction: opposite side at the
             same entries", Update 1). The script has no other reverse or Long / Short-only option.
  filter     off = "Enable filter" off (fgfOn False, the DEFAULT of this file); on = the FlashGold Direction
             Filter with its defaults
  path       tv = one intrabar path per chart bar (TradingView without Bar Magnifier); mag = the bracket and
             the pending price orders walk the 1-minute sub-bars. Chart "1": mag == tv
  cost       script = the script's own Properties (commission 0, slippage 0: NO cost at all; gvl cost 'tv');
             ours = XAU $0.30 per ounce per round trip, BTC 0.02 % of the fill value per fill + $0.20 per unit
             per round trip (gvl cost 'ours')

and writes out/inv_gvl_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>']       the full summary of gvl.summary (default inputs, tvMargin 0),
      plus trades_per_year, net_r_per_trade, reentry_share, ruined
  runs_stop[...]   the same 16 keys with preCandleEntryMode "Stop Next Candle" (the default mode never places
      a pending order)
  runs_m100[...]   the same 16 keys with tvMargin 100: an entry whose notional exceeds the cash is refused,
      i.e. what the file most likely shows in TradingView with its untouched Properties (Margin 100 %; the
      strategy() call sets no margin). Indicative (SPEC_gvl G14).
  checks: chart "1": every mag run equals its tv run; the sub-bars rebuild the chart bars.
long / short = the REAL side of each trade; raw_* / blocked_* = the normal (signal) side.
Every 'tv' row prints reentry_same_bar / reentry_gap_r (assumption G1: trades entered by an order decided on
an exit bar, and the estimate in R of what TradingView's same-bar fill would have changed) and margin_over
(entry fills larger than the account). --trades also saves the trade lists to
out/inv_gvl_trades/inv_gvl_<PAIR>_<TF>_<group>_<key>.parquet.
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
import gvl as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_gvl_trades')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = ('off', 'on')
PATHS = ('tv', 'mag')
COSTS = (('script', 'tv'), ('ours', 'ours'))
GROUPS = (('runs', {}), ('runs_stop', {'preCandleEntryMode': "Stop Next Candle"}), ('runs_m100', {'tvMargin': 100.0}))
YEAR = 365.25 * 86400
PATH_FIELDS = ('reentry_extreme', 'reentry_gap_r')        # defined per path (SPEC_gvl 6.3, 12)


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


def same_trades(ta, tb):
    """Two runs have the same trades, every column; the exleg code in `reentry` only as zero / non-zero (it
    is 1 / 2 / 3 on 'tv' and 1 / 2 on 'mag' by definition)."""
    if len(ta) != len(tb) or list(ta.columns) != list(tb.columns):
        return False
    for c in ta.columns:
        x, y = ta[c].to_numpy(), tb[c].to_numpy()
        if c == 'reentry':
            x, y = x > 0, y > 0
        if x.dtype.kind == 'f':
            if not ((x == y) | (np.isnan(x) & np.isnan(y))).all():
                return False
        elif not (x == y).all():
            return False
    return True


def same_summary(a, b, skip=('path', 'direction', 'filter', 'cost', 'params') + PATH_FIELDS):
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
    P = {flt: M.prepare(pair, tf, {'fgfOn': flt == 'on'}) for flt in FILTERS}
    p0 = P['off']
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    res = dict(strategy='gvl', pine='GVLiveV2_Polymarket_PreCandle_Strategy_FGF.pine [Update 1]', pair=pair, tf=tf,
               window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               years=years,
               inputs='script defaults: EMA 8 / 21, trend EMA 100, RSI filter 14 / 70 / 30, pre-candle arm on, '
                      'Market Next Candle, radar Chart, min vol score 35, vol rise 1, close location 0.65, trend '
                      'direction on, ATR exits (stop 1 x ATR(14), target 5 R, no trail, no time stop), Risk 1 % of '
                      'equity, max 50 units, step 0.001, margin cap 1 %, daily lock 3 losing trades per New York '
                      'day, no $ lock; capital 100,000; filter OFF by default, filter defaults when on',
               cost_modes={'script': "gvl cost 'tv': the strategy() call has commission 0 and slippage 0: no cost",
                           'ours': "gvl cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value "
                                   "per fill + $0.20 / unit per round trip"},
               sides='long / short = the REAL side of each trade; raw_* / blocked_* = the normal (signal) side',
               groups={'runs': 'default inputs, tvMargin 0 (TradingView margin rule not modelled)',
                       'runs_stop': 'preCandleEntryMode "Stop Next Candle"',
                       'runs_m100': 'tvMargin 100: entries larger than the cash are refused (indicative)'},
               assumptions='G1: one decision run per bar at its close; reentry_same_bar counts the trades entered '
                           'by an order decided on a bar with an exit (TradingView would probably fill a market '
                           'order of that run inside the bar), reentry_gap_r the estimated effect on the tv path. '
                           'zero_qty > 0: the account could no longer size a trade (ruined = True)',
               arms_long=int(p0['arms_long']), arms_short=int(p0['arms_short']),
               sig_long=int(p0['sig_long']), sig_short=int(p0['sig_short']), gate_bars=int(p0['gate_bars']),
               runs={}, runs_stop={}, runs_m100={}, checks={})
    keep = {}
    for group, extra in GROUPS:
        for dname, inv in DIRECTIONS:
            for flt in FILTERS:
                for path in PATHS:
                    for cname, cmode in COSTS:
                        key = '%s/%s/%s/%s' % (dname, flt, path, cname)
                        x = dict(extra, inv=inv, path=path, cost=cmode)
                        R = M.simulate(P[flt], x)
                        s = dict(M.summary(P[flt], R))
                        nt = s['trades']
                        s['trades_per_year'] = nt / years
                        s['net_r_per_trade'] = (s['net_r'] / nt) if nt else None
                        s['reentry_share'] = (s['reentry_same_bar'] / nt) if nt else None
                        s['ruined'] = bool(s['zero_qty'] > 0)
                        s.update(direction=dname, filter=flt, path=path, cost=cname,
                                 params=dict(extra, fgfOn=flt == 'on', gvInv=inv, path=path, cost=cmode))
                        res[group][key] = s
                        keep[(group, key)] = M.trades(P[flt], R)
                        if save_trades:
                            os.makedirs(TRD, exist_ok=True)
                            keep[(group, key)].to_parquet(os.path.join(TRD, 'inv_gvl_%s_%s_%s_%s.parquet' % (
                                pair, tf, group, key.replace('/', '_'))))
    mag_tv = None
    if tf == '1':
        mag_tv = True
        for g, _ in GROUPS:
            for k in res[g]:
                if '/mag/' in k:
                    k2 = k.replace('/mag/', '/tv/')
                    if not (same_summary(res[g][k], res[g][k2]) and same_trades(keep[(g, k)], keep[(g, k2)])):
                        mag_tv = False
    res['checks'] = dict(mag_equals_tv_on_chart_1=mag_tv, sub_bars_equal_chart_bars=True)
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_gvl_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not mag_tv:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    return res


def line(key, s):
    def g(v, fm):
        return fm % v if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else '   n/a'
    tail = ''
    if s['path'] == 'tv':
        tail = '  re %5d gapR %+7.1f over %5d' % (s['reentry_same_bar'], s['reentry_gap_r'], s['margin_over'])
    else:
        tail = '  re %5d' % s['reentry_same_bar']
    return ('  %-26s trades %6d (L %5d / S %5d)  net %+12.3f%%  R %+8.1f  pf %6s  win %5s%%  maxDD %6.2f%%  '
            'h1r %+9.2f h2r %+9.2f  sl/tp/rev/lock/end %d/%d/%d/%d/%d  zq %d ref %d%s' % (
                key, s['trades'], s['long'], s['short'], s['net_pct'], s['net_r'], g(s['pf'], '%.3f'),
                g(s['win_pct'], '%.1f'), s['max_dd_pct'], s['h1r_pct'], s['h2r_pct'], s['exit_sl'], s['exit_tp'],
                s['exit_reverse'], s['exit_daily_lock'], s['exit_end'], s['zero_qty'], s['margin_refused'], tail))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    save_trades = '--trades' in sys.argv
    if len(args) < 2 or args[0] not in M.WINDOWS or any(t not in TFS for t in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if len(args) > 2:
        # one fresh process per cell, one at a time: the peak memory of a 1-minute chart is then that of a
        # single cell, whatever ran before
        import subprocess
        rc = 0
        for tf in args[1:]:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), pair, tf]
                               + (['--trades'] if save_trades else []))
            rc = rc or r.returncode
        return rc
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        print('%s %s: %d bars, %d 1-minute sub-bars, arms %d / %d, signals %d / %d, %.1fs, peak RSS %.2f GB -> '
              'out/inv_gvl_%s_%s.json' % (pair, tf, res['bars'], res['sub_bars_1m'], res['arms_long'],
                                          res['arms_short'], res['sig_long'], res['sig_short'], res['seconds'],
                                          res['peak_rss_gb'], pair, tf))
        for g, _ in GROUPS:
            print(' %s' % g)
            for k, s in res[g].items():
                print(line(k, s))
        print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
