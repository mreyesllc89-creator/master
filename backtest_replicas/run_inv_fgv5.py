"""run_inv_fgv5.py: FlashGold v5 Strategy (BTCUSD) + FGF [Update 1], by time frame, with the canonical replica fgv5.py
(REPLICA_SPEC.md stage 3; the runner of INV_BT_SPEC.md item 3; SPEC_fgv5.md section 13).

Usage: python3 -I run_inv_fgv5.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close) and the script's
default inputs (Pine //@version=5; signal: spread 25 pts, burst 0.5 ATR, entry distance 0.25 ATR, Auto timeframes
= chart / 2x / 4x, minimum 2 zones aligned; S1: Direction Both, entry valid 3 bars, reverse on, no close on the
opposite signal; S2: Pips exits (1 pip = $1): SL 30, target 5 R, 30 % partial + runner trailed 600 pips with the
stop to breakeven after the target, no time stop; S3: Fixed 10 units, capital 100,000; filter on with its
defaults) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = Update 1 off; inverted = "Inverted direction: opposite side at the same entries" (fgvInv on: a
             BUY signal the filter allows places a SELL LIMIT at the buy stop's price, a SELL signal a BUY LIMIT;
             decisions in the normal frame on the mirrored position; exits keep their distances on the real trade).
             The script has no older reverse option, so there is no reversed-label run to store
  filter     off = fgfOn false (every gate true); on = the filter block's defaults (fgfOn true is the default)
  path       tv = one intrabar path per chart bar (TradingView without Bar Magnifier); mag = the stop / limit entry
             orders and every exit order walk the 1-minute sub-bars (Bar Magnifier); market closes at the chart
             open, the script (and the breakeven flag) at the chart close. Chart "1": mag == tv
  cost       script = the strategy() Properties: commission 0.02 % of every fill + slippage 5 ticks (0.05) on every
             stop / market fill (fgv5 cost 'tv'); ours = XAU $0.30 per ounce per round trip, BTC 0.02 % of the fill
             value per fill + $0.20 per unit per round trip, no slippage (fgv5 cost 'ours')

and writes out/inv_fgv5_<PAIR>_<TF>.json:
  runs['<direction>/<filter>/<path>/<cost>']   the full summary of fgv5.summary, plus trades_per_year,
                                                net_r_per_trade, neg_equity (equity <= 0 at some bar close)
  signals: signal bars per side and of them allowed by the filter; checks: chart "1": every mag run equals its tv
  run; chart "60": no filter-on trade (the strategy's signal is the filter's own 60-minute signal); the 1-minute
  sub-bars rebuild the chart bars.
Every printed row carries neg_equity_bars, min_equity, be_no_tp, tv_rows and zero_length. long / short = the REAL
side; raw_* / blocked_* = the FGD funnel in the normal frame. Fixed 10 units: 10 BTC is about 9 accounts (v5 has no
margin rule: equity may go below 0 and trading continues; the fair halves h1r / h2r are then NaN), 10 oz of gold
0.13 of the account; on gold the Pips exits ($30 stop, $150 target, $600 runner) are BTC-sized (see fgv5_notes.md).
--trades also saves the trade lists to out/inv_fgv5_trades/inv_fgv5_<PAIR>_<TF>_<key>.parquet.
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
import fgv5 as M  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_fgv5_trades')
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
    P = {flt: M.prepare(pair, tf, {'fgfOn': flt == 'on'}) for flt in FILTERS}
    p0 = P['on']
    sub = M.get_sub(p0)            # the 1-minute sub-bars, built once and checked against the chart bars
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    years = (p0['end'] - p0['start']) / YEAR
    sig = dict(buy=int(p0['sig_buy']), sell=int(p0['sig_sell']),
               buy_allowed=int((p0['buySig'] & p0['buyOk']).sum()),
               sell_allowed=int((p0['sellSig'] & p0['sellOk']).sum()))
    res = dict(strategy='fgv5', pine='FlashGold_v5_Strategy_BTCUSD_FGF.pine [Update 1] (//@version=5)', pair=pair,
               tf=tf, window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               years=years,
               inputs='script defaults: spread 25 pts, burst 0.5 ATR, entry distance 0.25 ATR, Auto timeframes '
                      '(chart / 2x / 4x), minimum 2 zones aligned; Direction Both, entry valid 3 bars, reverse on, '
                      'close on the opposite signal off; Pips exits (1 pip = $1): SL 30, TP 5 R, Partial + runner '
                      '30 %, runner trail 600 pips, breakeven after the TP, no time stop; Fixed 10 units, capital '
                      '100,000; filter on with its defaults (timeframe 60, level = entry price)',
               cost_modes={'script': "fgv5 cost 'tv': strategy() commission 0.02 % of every fill + slippage 5 "
                                     "ticks (0.05) on stop and market fills (none on limit fills)",
                           'ours': "fgv5 cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % of the fill value "
                                   "per fill + $0.20 / unit per round trip; no slippage"},
               sides='long / short = the REAL side of each trade; raw_* / blocked_* = the FGD funnel (normal frame)',
               direction='inverted = fgvInv on (Update 1); the script has no older reverse option',
               signals=sig, runs={}, checks={})
    keep = {}
    for dname, inv in DIRECTIONS:
        for flt in FILTERS:
            for path in PATHS:
                for cname, cmode in COSTS:
                    key = '%s/%s/%s/%s' % (dname, flt, path, cname)
                    x = dict(inv=inv, path=path, cost=cmode)
                    R = M.simulate(P[flt], x)
                    s = dict(M.summary(P[flt], R))
                    nt = s['trades']
                    s['trades_per_year'] = nt / years
                    s['net_r_per_trade'] = (s['net_r'] / nt) if nt else None
                    s['neg_equity'] = bool(s['neg_equity_bars'] > 0)
                    s.update(direction=dname, filter=flt, path=path, cost=cname,
                             params=dict(fgfOn=flt == 'on', fgvInv=inv, path=path, cost=cmode))
                    res['runs'][key] = s
                    keep[key] = M.trades(P[flt], R)
                    if save_trades:
                        os.makedirs(TRD, exist_ok=True)
                        keep[key].to_parquet(os.path.join(TRD, 'inv_fgv5_%s_%s_%s.parquet' % (
                            pair, tf, key.replace('/', '_'))))
    mag_tv = None
    if tf == '1':
        mag_tv = all(same_summary(res['runs'][k], res['runs'][k.replace('/mag/', '/tv/')])
                     and same_trades(keep[k], keep[k.replace('/mag/', '/tv/')])
                     for k in res['runs'] if '/mag/' in k)
    on60_zero = None
    if tf == '60':
        on60_zero = all(res['runs'][k]['trades'] == 0 for k in res['runs'] if '/on/' in k)
    res['checks'] = dict(mag_equals_tv_on_chart_1=mag_tv, no_filter_on_trade_on_chart_60=on60_zero,
                         sub_bars_equal_chart_bars=True)
    res['seconds'] = round(time.time() - t0, 2)
    res['peak_rss_gb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576.0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_fgv5_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if tf == '1' and not mag_tv:
        raise RuntimeError('%s 1: a mag run differs from its tv run' % pair)
    if tf == '60' and not on60_zero:
        raise RuntimeError('%s 60: a filter-on run has trades' % pair)
    return res


def line(key, s):
    def g(v, fm):
        ok = v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
        return fm % v if ok else '   n/a'
    return ('  %-26s trades %6d (L %6d / S %6d)  net %+12.2f%%  pf %6s  win %5s%%  maxDD %8.2f%%  h1r %9s h2r %9s  '
            'sl/tp_part/be/runner/rev/end %d/%d/%d/%d/%d/%d  neg_eq_bars %d  min_eq %.0f  be_no_tp %d  tv_rows %d  '
            'zero_len %d' % (key, s['trades'], s['long'], s['short'], s['net_pct'], g(s['pf'], '%.3f'),
                             g(s['win_pct'], '%.1f'), s['max_dd_pct'], g(s['h1r_pct'], '%+.2f'),
                             g(s['h2r_pct'], '%+.2f'), s['exit_sl'], s['part_tp_part'], s['exit_be'],
                             s['exit_runner'], s['exit_reverse'], s['exit_end'], s['neg_equity_bars'], s['min_equity'],
                             s['be_no_tp'], s['tv_rows'], s['zero_length']))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    save_trades = '--trades' in sys.argv
    if len(args) < 2 or args[0] not in M.WINDOWS or any(t not in TFS for t in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if len(args) > 2:
        # one fresh process per cell, one at a time: the peak memory is that of one cell
        import subprocess
        rc = 0
        for tf in args[1:]:
            r = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), pair, tf]
                               + (['--trades'] if save_trades else []))
            rc = rc or r.returncode
        return rc
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        sg = res['signals']
        print('%s %s: %d bars, %d 1-minute sub-bars, signals %d / %d (filter allows %d / %d), %.1fs, peak RSS %.2f GB '
              '-> out/inv_fgv5_%s_%s.json' % (pair, tf, res['bars'], res['sub_bars_1m'], sg['buy'], sg['sell'],
                                              sg['buy_allowed'], sg['sell_allowed'], res['seconds'],
                                              res['peak_rss_gb'], pair, tf))
        for k, s in res['runs'].items():
            print(line(k, s))
        print('  checks: %r' % (res['checks'],), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
