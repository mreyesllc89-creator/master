"""run_inv_amvi.py: AMVI Full MTF Strategy + FGF [Update 1], by time frame, with the canonical replica amvi.py
(REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3; SPEC_amvi.md section 13).

Usage: python3 -I run_inv_amvi.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240. Several TFs: one fresh process per TF, one at a time.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close) and the script's
default inputs (AMVI 14 / 50 / 20 / 10 / 200, weights 0.35 / 0.25 / 0.25 / 0.15, Non-Repainting on, High Vol 70,
Low Vol 30, confluence 3, the seven minute / day timeframes on (the five seconds timeframes have no data: off),
no date range; exits: ATR(14) stop 1.5, target 3.0, no trail, collapse exit on, no time stop; 10 % of equity per
trade, capital 10,000) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = "Trade direction: Follow the filter"; inverted = "Trade direction: Inverted" (amviTradeDir,
             the replica's inv: the script's own input, older than Update 1, which only numbered the file)
  filter     on  = the fused file (AMVI_Full_MTF_Strategy_FGF.pine) with the FlashGold Direction Filter at its
                   defaults: the filter's zone IS the direction
             off = the unfused original (AMVI_Full_MTF_Strategy.pine) at its defaults: direction "Trend (EMA)" 50,
                   "Both", reverse on (replica dirSource 'orig'). The fused file with fgfOn False places no order
                   at all (it has no direction): stored once as fgf_off_literal
  path       tv  = one intrabar path per chart bar (TradingView without Bar Magnifier); mag = the bracket walks the
                   1-minute sub-bars. Chart "1": mag == tv
  cost       script = the script's Properties: commission 0.04 % per fill, slippage 1 tick (cost 'tv');
             ours = XAU $0.30 per ounce per round trip, BTC 0.02 % of the fill value per fill + $0.20 per unit per
                   round trip, no slippage (cost 'ours')

and writes out/inv_amvi_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>']   the full summary of amvi.summary, plus trades_per_year,
      net_r_per_trade
  runs_ltf_last['<direction>/on/<path>/<cost>']  the 'on' runs with ltfRule 'last' (lower-timeframe requests read
      as on a live bar, assumption A2): the weight of A2
  fgf_off_literal['<direction>/tv/script']    the fused file with fgfOn False (zero trades)
  checks: chart "1": every mag run equals its tv run; the sub-bars rebuild the chart bars; fgf_off_literal has no
      trade; the five seconds toggles are reported in seconds_ignored (5: TradingView must have them off)
long / short = the REAL side of each trade; raw_long / raw_short = triggers in the BUY / SELL zone (filter on) or
with an up / down bias (filter off), triggers / trig_none: all triggers / those with no direction.
--trades also saves the trade lists to out/inv_amvi_trades/inv_amvi_<PAIR>_<TF>_<group>_<key>.parquet.
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
import amvi as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_amvi_trades')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = (('off', {'dirSource': 'orig'}), ('on', {}))
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


def same_summary(a, b, skip=('path', 'direction', 'filter', 'cost', 'params')):
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
    P = {flt: M.prepare(pair, tf, dict(pp)) for flt, pp in FILTERS}
    P['on_last'] = M.prepare(pair, tf, {'ltfRule': 'last'})
    P['fgf_off'] = M.prepare(pair, tf, {'fgfOn': False})
    p0 = P['on']
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    res = dict(strategy='amvi', pine='AMVI_Full_MTF_Strategy_FGF.pine [Update 1]',
               filter_off_is='AMVI_Full_MTF_Strategy.pine',
               filter_on_is='AMVI_Full_MTF_Strategy_FGF.pine (fgfOn true, filter defaults)',
               pair=pair, tf=tf, window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']),
               sub_bars_1m=int(len(sub[1])), years=years,
               inputs='script defaults: AMVI periods 14 / 50 / 20 / 10 / 200, weights 0.35 / 0.25 / 0.25 / 0.15, '
                      'Non-Repainting on, High Vol 70, Low Vol 30, confluence 3, timeframes 1m 5m 15m 30m 1h 4h 1D '
                      '(1s-45s: no data, = off), no date range; ATR(14) stop 1.5, target 3.0, no trail, collapse '
                      'exit on, no time stop; 10 % of equity, capital 10,000. Filter off = the unfused original: '
                      '"Trend (EMA)" 50, "Both", reverse on',
               cost_modes={'script': "amvi cost 'tv': the strategy() call's commission 0.04 % per fill and slippage "
                                     "1 tick on market and stop fills",
                           'ours': "amvi cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value per "
                                   "fill + $0.20 / unit per round trip; no slippage"},
               sides='long / short = the REAL side of each trade; raw_long / raw_short / trig_none = the triggers '
                     'by normal-frame direction',
               groups={'runs': 'default inputs',
                       'runs_ltf_last': "filter on, ltfRule 'last' (A2: lower timeframes read as on a live bar)",
                       'fgf_off_literal': 'the fused file with fgfOn False: no direction, no order'},
               reversed_label_runs='none: the fused file has no other reverse / direction option ("Trade direction: '
                                   'Inverted" IS the option; the original\'s tradeDir / allowReverse are a side '
                                   'restriction and a reverse switch, removed by the fusion); with fgfOn false nothing '
                                   'trades in either direction (fgf_off_literal)',
               seconds_timeframes='1S 5S 15S 30S 45S: no data, na on every bar = the Pine with en1s en5s en15s en30s '
                                  'en45s off (seconds_ignored = 5 with the defaults)',
               triggers=int(p0['triggers']),
               trig_on=dict(up=int(p0['trig_up']), dn=int(p0['trig_dn']), none=int(p0['trig_none'])),
               trig_off=dict(up=int(P['off']['trig_up']), dn=int(P['off']['trig_dn']),
                             none=int(P['off']['trig_none'])),
               triggers_ltf_last=int(P['on_last']['triggers']),
               runs={}, runs_ltf_last={}, fgf_off_literal={}, checks={})
    keep = {}

    def one(group, key, Pk, x, dname, flt, path, cname):
        R = M.simulate(Pk, x)
        s = dict(M.summary(Pk, R))
        nt = s['trades']
        s['trades_per_year'] = nt / years
        s['net_r_per_trade'] = (s['net_r'] / nt) if nt else None
        s.update(direction=dname, filter=flt, path=path, cost=cname, params=dict(x))
        res[group][key] = s
        T = M.trades(Pk, R)
        keep[(group, key)] = T
        if save_trades:
            os.makedirs(TRD, exist_ok=True)
            T.to_parquet(os.path.join(TRD, 'inv_amvi_%s_%s_%s_%s.parquet' % (pair, tf, group, key.replace('/', '_'))))

    for dname, inv in DIRECTIONS:
        for flt, _ in FILTERS:
            for path in PATHS:
                for cname, cmode in COSTS:
                    one('runs', '%s/%s/%s/%s' % (dname, flt, path, cname), P[flt],
                        dict(inv=inv, path=path, cost=cmode), dname, flt, path, cname)
        for path in PATHS:
            for cname, cmode in COSTS:
                one('runs_ltf_last', '%s/on/%s/%s' % (dname, path, cname), P['on_last'],
                    dict(inv=inv, path=path, cost=cmode), dname, 'on', path, cname)
        one('fgf_off_literal', '%s/tv/script' % dname, P['fgf_off'], dict(inv=inv, path='tv', cost='tv'),
            dname, 'fgfOn False', 'tv', 'script')
    mag_tv = None
    if tf == '1':
        mag_tv = True
        for g in ('runs', 'runs_ltf_last'):
            for k in res[g]:
                if '/mag/' in k:
                    k2 = k.replace('/mag/', '/tv/')
                    if not (same_summary(res[g][k], res[g][k2]) and same_trades(keep[(g, k)], keep[(g, k2)])):
                        mag_tv = False
    lit0 = all(s['trades'] == 0 for s in res['fgf_off_literal'].values())
    res['checks'] = dict(mag_equals_tv_on_chart_1=mag_tv, sub_bars_equal_chart_bars=True,
                         fgf_off_literal_no_trade=lit0,
                         ltf_last_differs=(None if tf == '1' else
                                           any(res['runs_ltf_last'][k]['trades'] != res['runs'][k]['trades'] or
                                               res['runs_ltf_last'][k]['net_pct'] != res['runs'][k]['net_pct']
                                               for k in res['runs_ltf_last'])))
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_amvi_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not mag_tv:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    if not lit0:
        raise RuntimeError('%s %s: the fused file with fgfOn False traded' % (pair, tf))
    return res


def line(key, s):
    def g(v, fm):
        return fm % v if v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else '   n/a'
    return ('  %-26s trades %5d (L %4d / S %4d)  net %+8.3f%%  netR %+8.2f  pf %6s  win %5s%%  maxDD %6.3f%%  '
            'h1r %+7.3f h2r %+7.3f (%d / %d)  sl/tp/tr/rev/vol/time/end %d/%d/%d/%d/%d/%d/%d  zl %d  rcs %d  zq %d' % (
                key, s['trades'], s['long'], s['short'], s['net_pct'], s['net_r'], g(s['pf'], '%.3f'),
                g(s['win_pct'], '%.1f'), s['max_dd_pct'], s['h1r_pct'], s['h2r_pct'], s['h1_trades'], s['h2_trades'],
                s['exit_sl'], s['exit_tp'], s['exit_trail'], s['exit_reverse'], s['exit_vol'], s['exit_time'],
                s['exit_end'], s['zero_length'], s['rev_close_same_run'], s['zero_qty']))


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
    tf = args[1]
    res = run_cell(pair, tf, save_trades)
    print('%s %s: %d bars, %d 1-minute sub-bars, triggers %d (filter on: BUY %d / SELL %d / none %d; filter off: up %d '
          '/ down %d), ltfRule last: %d triggers, %.1fs, peak RSS %.2f GB -> out/inv_amvi_%s_%s.json' % (
              pair, tf, res['bars'], res['sub_bars_1m'], res['triggers'], res['trig_on']['up'], res['trig_on']['dn'],
              res['trig_on']['none'], res['trig_off']['up'], res['trig_off']['dn'], res['triggers_ltf_last'],
              res['seconds'], res['peak_rss_gb'], pair, tf))
    for g in ('runs', 'runs_ltf_last', 'fgf_off_literal'):
        print(' %s' % g)
        for k, s in res[g].items():
            print(line(k, s))
    print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
