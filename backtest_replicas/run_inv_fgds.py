"""run_inv_fgds.py: FlashGold Direction Strategy [Update 1], by time frame, with the canonical replica fgds.py
(REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3; SPEC_fgds.md section 13).

Usage: python3 -I run_inv_fgds.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close) and the
script's default inputs (filter on with its defaults; entry trigger "Zone start", Sides Both, close when the
entry zone ends on, reverse on an opposite entry on; ATR exits: stop 1 x ATR(14), target 3 R, no trail, no time
stop; Risk 0.5 % of equity, max 50 units, step 0.001, margin cap 1 %; capital 10,000) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = "Trade direction: Follow the filter"; inverted = "Trade direction: Inverted" (dsDirection,
             the script's own input, older than Update 1, which numbered the file and changed no code: a buy
             trigger opens "DS Short", a sell trigger opens "DS Long"; the stop / target / trail keep their tick
             distances from the fill of the trade really open)
  filter     off = "Enable filter" off (fgfOn False): every trigger needs the filter, so NOTHING trades (the 8
             filter-off rows are zero-trade rows by construction; kept, not dropped); on = the filter's defaults
             (fgfOn True is the file's default)
  path       tv = one intrabar path per chart bar (TradingView without Bar Magnifier); mag = the bracket walks
             the 1-minute sub-bars (Bar Magnifier). Chart "1": mag == tv
  cost       script = the script's own Properties (commission 0 %, slippage 0: NO cost; fgds cost 'tv');
             ours = XAU $0.30 per ounce per round trip, BTC 0.02 % of the fill value per fill + $0.20 per unit
             per round trip (fgds cost 'ours')

and writes out/inv_fgds_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>']       the full summary of fgds.summary (entry trigger "Zone start",
      the default), plus trades_per_year, net_r_per_trade, ruined
  runs_conf[...]   the same 16 keys with entry trigger "Signal confirmed"
  runs_new[...]    the same 16 keys with entry trigger "New signal"
  checks: chart "1": every mag run equals its tv run; filter off: no trade; the sub-bars rebuild the chart bars.
long / short = the REAL side of each trade; raw_* = the trigger bars of the chosen trigger (normal frame).
Every row prints zero_qty (decisions with a trigger that could not be sized: the account is too small; the run is
then "ruined"), qty_capped_max (entries whose quantity dsMaxQty = 50 set) and qty_capped_margin (entries whose
quantity the script's margin cap set: TradingView's own 1 % margin rule could bite there; not modelled).
--trades also saves the trade lists to out/inv_fgds_trades/inv_fgds_<PAIR>_<TF>_<group>_<key>.parquet.
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
import fgds as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_fgds_trades')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = ('off', 'on')
PATHS = ('tv', 'mag')
COSTS = (('script', 'tv'), ('ours', 'ours'))
GROUPS = (('runs', {}), ('runs_conf', {'dsTrigger': "Signal confirmed"}), ('runs_new', {'dsTrigger': "New signal"}))
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


def same_trades(ta, tb):
    if len(ta) != len(tb) or list(ta.columns) != list(tb.columns):
        return False
    for c in ta.columns:
        x, y = ta[c].to_numpy(), tb[c].to_numpy()
        if x.dtype.kind == 'f':
            if not ((x == y) | (np.isnan(x) & np.isnan(y))).all():
                return False
        elif not (x == y).all():
            return False
    return True


def same_summary(a, b, skip=('path', 'direction', 'filter', 'cost', 'params', 'trigger')):
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
    p0 = P['on']
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    res = dict(strategy='fgds', pine='FlashGold_Direction_Strategy.pine [Update 1]', pair=pair, tf=tf,
               window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               years=years,
               inputs='script defaults: filter on with its defaults (filter timeframe 60, parent 60, zones '
                      '60 / 120 / 240, burst 0.5 ATR, band 0.25 ATR, level = entry price, until the next signal, '
                      'trade against the signal on); Zone start (runs), Sides Both, close when the entry zone '
                      'ends, reverse on an opposite entry; ATR exits: stop 1 x ATR(14), target 3 R, no trail, no '
                      'time stop; Risk 0.5 % of equity, max 50 units, step 0.001, margin cap 1 %; capital 10,000',
               cost_modes={'script': "fgds cost 'tv': the strategy() call has commission 0 and slippage 0: no cost",
                           'ours': "fgds cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value "
                                   "per fill + $0.20 / unit per round trip"},
               sides='long / short = the REAL side of each trade; raw_* = trigger bars of the chosen trigger '
                     '(normal frame); blocked_* are always 0 (the filter is the signal)',
               direction='inverted = the script input "Trade direction: Inverted" (dsDirection, older than Update '
                         '1): a buy trigger opens "DS Short", a sell trigger "DS Long"; stop / target / trail keep '
                         'their tick distances from the fill of the trade really open',
               groups={'runs': 'entry trigger "Zone start" (the default)',
                       'runs_conf': 'entry trigger "Signal confirmed"',
                       'runs_new': 'entry trigger "New signal"'},
               filter_off='fgfOn False: every trigger is false, no trade in any filter-off row (by construction)',
               triggers=dict(p0['counts']),
               runs={}, runs_conf={}, runs_new={}, checks={})
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
                        s['ruined'] = bool(s['zero_qty'] > 0)
                        s.update(direction=dname, filter=flt, path=path, cost=cname,
                                 trigger=extra.get('dsTrigger', "Zone start"),
                                 params=dict(extra, fgfOn=flt == 'on', dsDirection="Inverted" if inv else
                                             "Follow the filter", path=path, cost=cmode))
                        res[group][key] = s
                        keep[(group, key)] = M.trades(P[flt], R)
                        if save_trades:
                            os.makedirs(TRD, exist_ok=True)
                            keep[(group, key)].to_parquet(os.path.join(TRD, 'inv_fgds_%s_%s_%s_%s.parquet' % (
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
    off_zero = all(res[g][k]['trades'] == 0 for g, _ in GROUPS for k in res[g] if '/off/' in k)
    res['checks'] = dict(mag_equals_tv_on_chart_1=mag_tv, filter_off_no_trade=off_zero,
                         sub_bars_equal_chart_bars=True)
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_fgds_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not mag_tv:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    if not off_zero:
        raise RuntimeError('%s %s: a filter-off run has trades' % (pair, tf))
    return res


def line(key, s):
    def g(v, fm):
        return fm % v if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else '   n/a'
    return ('  %-26s trades %6d (L %5d / S %5d)  net %+12.3f%%  R %+8.1f  pf %6s  win %5s%%  maxDD %6.2f%%  '
            'h1r %+9.2f h2r %+9.2f  sl/tp/rev/opp/zone/end %d/%d/%d/%d/%d/%d  zero_qty %d  capped max %d '
            'margin %d' % (key, s['trades'], s['long'], s['short'], s['net_pct'], s['net_r'], g(s['pf'], '%.3f'),
                           g(s['win_pct'], '%.1f'), s['max_dd_pct'], s['h1r_pct'], s['h2r_pct'], s['exit_sl'],
                           s['exit_tp'], s['exit_reverse'], s['exit_opp'], s['exit_zone'], s['exit_end'],
                           s['zero_qty'], s['qty_capped_max'], s['qty_capped_margin']))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    save_trades = '--trades' in sys.argv
    if len(args) < 2 or args[0] not in M.WINDOWS or any(t not in TFS for t in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if len(args) > 2:
        # one fresh process per cell, one at a time: the peak memory of a 1-minute chart is that of one cell
        import subprocess
        rc = 0
        for tf in args[1:]:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), pair, tf]
                               + (['--trades'] if save_trades else []))
            rc = rc or r.returncode
        return rc
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        tc = res['triggers']
        print('%s %s: %d bars, %d 1-minute sub-bars, triggers zone %d / %d, conf %d / %d, new %d / %d, %.1fs, '
              'peak RSS %.2f GB -> out/inv_fgds_%s_%s.json' % (
                  pair, tf, res['bars'], res['sub_bars_1m'], tc['trig_zone_buy'], tc['trig_zone_sell'],
                  tc['trig_conf_buy'], tc['trig_conf_sell'], tc['trig_new_buy'], tc['trig_new_sell'],
                  res['seconds'], res['peak_rss_gb'], pair, tf))
        for g, _ in GROUPS:
            print(' %s' % g)
            for k, s in res[g].items():
                print(line(k, s))
        print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
