"""run_inv_hrd.py: HRD Full Divergence v1.03 + FGF, Update 1 "Inverted direction", by time frame,
with the canonical replica hrd.py (INV_BT_SPEC.md task 3, strategy "hrd").

Usage: python3 -I run_inv_hrd.py PAIR TF [TF ...] [--trades]
  PAIR in BTC, XAU; TF in 1, 5, 15, 30, 60, 120, 240.

For the full window of PAIR (BTC 1731801600..1794873600, XAU 1483315200..1529366400, by t_close)
and the script's default inputs (SL 2 %, TP 4 %, close after 5 candles, hybrid exit on, trailing
take profit off, Trade Direction Both, Reverse Trading off, hrdBlkClose on) it runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

  direction  normal = hrdInv off; inverted = hrdInv on (Pine input "Inverted direction: opposite
             side at the same entries")
  filter     off = "Enable filter" off (fgfOn False); on = the FlashGold Direction Filter defaults
  path       tv = one intrabar path per chart bar (TradingView without Bar Magnifier);
             mag = exits walked along the 1-minute sub-bars (Bar Magnifier). Chart "1": mag == tv
  cost       script = what TradingView shows with the script's own Properties: HRD's strategy()
             sets no commission, so no costs (hrd cost 'tv'); ours = XAU $0.30 per ounce per
             round trip, BTC 0.02 % per side + $0.20 per coin per round trip (hrd cost 'ours')

and writes out/inv_hrd_<PAIR>_<TF>.json:
  runs[<direction>_<filter>_<path>_<cost>] = the full summary: trades, net_pct, pf, win_pct,
    max_dd_pct, max_dd_init_pct, h1r_pct / h2r_pct (fair halves) with h1_trades / h2_trades, long /
    short (REAL sides of the trades), exits {sl, tp, reverse, blocked_close, time, hybrid, end,
    trail}, avg_bars_held, exposure, zero_length, costs, final_equity, half1_pct / half2_pct,
    net_closed_pct, and raw_long / raw_short / blocked_long / blocked_short (the Pine's FGD counts:
    the SIGNAL's side, before the inversion, for an inverted run too).
  reference[rev_<filter>_<path>_<cost>] = the existing reversed-labels runs (Reverse Trading on,
    hrdInv off), filter off and on, same summary.
  checks = the normal / reversed tv runs against the saved out/hrd_<PAIR>_<TF>.json (every common
    field must be equal), and summary_fast against the full summary.
--trades also saves the trade lists to out/inv_hrd_trades/inv_hrd_<PAIR>_<TF>_<key>.parquet.
"""
import json
import math
import os
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import hrd  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'inv_hrd_trades')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = ('off', 'on')
PATHS = ('tv', 'mag')
COSTS = (('script', 'tv'), ('ours', 'ours'))
# saved out/hrd_<PAIR>_<TF>.json run names (run_hrd.py) of the tv-path runs that exist there
SAVED = {('normal', 'off', 'script'): 'off_tv', ('normal', 'off', 'ours'): 'off_ours',
         ('normal', 'on', 'script'): 'on_tv', ('normal', 'on', 'ours'): 'on_ours',
         ('rev', 'off', 'script'): 'rev_off_tv', ('rev', 'off', 'ours'): 'rev_off_ours',
         ('rev', 'on', 'script'): 'rev_on_tv', ('rev', 'on', 'ours'): 'rev_on_ours'}


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


def one_run(Pp, X):
    """One full-window run: (trades DataFrame, summary). The summary is hrd.run()'s (summarize +
    extra_fields) plus costs, net_closed_pct and the open trade's P/L; it is cross-checked against
    hrd.summary_fast (the sweep's summary)."""
    R = hrd.simulate(Pp, X, full=True)
    tr = hrd.trades_frame(Pp, R)
    s = hrd.summarize(tr, R['eq'], R['pos'], Pp['t_close'], Pp['start'], Pp['end'],
                      R['want_l'], R['want_s'], R['blk_l'], R['blk_s'])
    s.update(hrd.extra_fields(Pp, R))
    f = hrd.summary_fast(Pp, R)
    for k, v in f.items():
        if k.startswith('exit_'):
            same = s['exits'][k[5:]] == v
        elif k in s:
            same = (s[k] == v) or (isinstance(v, float) and math.isnan(v) and math.isnan(s[k]))
        else:
            continue
        if not same:
            raise RuntimeError('summary_fast differs from the full summary on %s: %r vs %r' % (k, v, s.get(k)))
    init = hrd.INITIAL_CAPITAL
    end_pnl = float(tr.loc[tr['exit_kind'] == 'end', 'pnl'].sum()) if len(tr) else 0.0
    s['costs'] = float(tr['costs'].sum()) if len(tr) else 0.0
    # TradingView's Net Profit counts closed trades only; net_pct includes the trade still open at
    # the window end, closed at the last close (exit kind 'end')
    s['net_closed_pct'] = s['net_pct'] - end_pnl / init * 100.0
    s['end_trade_pnl_pct'] = end_pnl / init * 100.0
    s['avg_trade_pct'] = float(tr['pnl'].sum() / init * 100.0 / len(tr)) if len(tr) else None
    return tr, s


def check_saved(saved, name, s):
    """Every scalar field the saved run and this summary share must be equal (and the exits)."""
    if saved is None or name not in saved['runs']:
        return None
    sv = saved['runs'][name]
    cl = clean(s)
    bad = []
    for k, v in sv.items():
        if k == 'exits':
            if any(cl['exits'].get(e) != x for e, x in v.items()):
                bad.append(k)
        elif k in cl and k not in ('params',) and cl[k] != v:
            bad.append(k)
    return bad


def run_cell(pair, tf, save_trades=False):
    t0 = time.time()
    tf = str(tf)
    saved = None
    fn = os.path.join(OUT, 'hrd_%s_%s.json' % (pair, tf))
    if os.path.exists(fn):
        saved = json.load(open(fn))
    P = {(lab, flt): hrd.prepare(pair, tf, {'fgfOn': flt == 'on', 'reverse': lab == 'rev'})
         for lab in ('normal', 'rev') for flt in FILTERS}
    p0 = P[('normal', 'off')]
    sub = hrd.get_sub(p0)                      # the 1-minute sub-bars, built once (checked against the chart bars)
    for Pk in P.values():
        if Pk['w0'] != p0['w0'] or Pk['w1'] != p0['w1']:
            raise RuntimeError('window rows differ')
        Pk['sub'] = sub
    res = dict(strategy='hrd', pine='HRD_Full_Divergence_Strategy_v1_03_FGF.pine [Update 1]', pair=pair, tf=tf,
               window=[int(p0['start']), int(p0['end'])], bars=int(p0['n']), sub_bars_1m=int(len(sub[1])),
               inputs='script defaults: SL 2 %, TP 4 %, 5 candles, hybrid exit on, trail off, Trade Direction Both, '
                      'Reverse Trading off, hrdBlkClose on; filter defaults',
               cost_modes={'script': "hrd cost 'tv': none (strategy() sets no commission)",
                           'ours': "hrd cost 'ours': XAU $0.30 / oz per round trip; BTC 0.02 % per side + $0.20 / coin "
                                   "per round trip"},
               sides='long / short = the REAL side of each trade; raw_* / blocked_* = the signal side before the '
                     'inversion (the Pine FGD counts)',
               runs={}, reference={}, checks={})
    saved_bad = {}
    n_saved = 0

    def do(group, key, lab, flt, inv, path, cname, cmode):
        nonlocal n_saved
        X = {'hrdInv': inv, 'path': path, 'cost': cmode}
        tr, s = one_run(P[(lab, flt)], X)
        s = dict(s)
        s.update(direction=('inverted' if inv else 'normal'), labels=lab, filter=flt, path=path, cost=cname,
                 params={'fgfOn': flt == 'on', 'reverse': lab == 'rev', 'hrdInv': inv, 'path': path, 'cost': cmode})
        res[group][key] = s
        if path == 'tv' and not inv:
            bad = check_saved(saved, SAVED.get((lab, flt, cname)), s)
            if bad is not None:
                n_saved += 1
                if bad:
                    saved_bad[key] = bad
        if save_trades:
            tr.to_parquet(os.path.join(TRD, 'inv_hrd_%s_%s_%s.parquet' % (pair, tf, key)))

    for dname, inv in DIRECTIONS:
        for flt in FILTERS:
            for path in PATHS:
                for cname, cmode in COSTS:
                    do('runs', '%s_%s_%s_%s' % (dname, flt, path, cname), 'normal', flt, inv, path, cname, cmode)
    for flt in FILTERS:
        for path in PATHS:
            for cname, cmode in COSTS:
                do('reference', 'rev_%s_%s_%s' % (flt, path, cname), 'rev', flt, False, path, cname, cmode)
    res['checks'] = dict(saved_file=os.path.basename(fn) if saved is not None else None,
                         saved_runs_compared=n_saved, saved_runs_equal=n_saved - len(saved_bad),
                         saved_differences=saved_bad,
                         summary_fast_equal=True,
                         mag_equals_tv_on_chart_1=(all(_same(res['runs'][k], res['runs'][k.replace('_mag_', '_tv_')])
                                                       for k in res['runs'] if '_mag_' in k) if tf == '1' else None))
    res['seconds'] = round(time.time() - t0, 2)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, 'inv_hrd_%s_%s.json' % (pair, tf))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(clean(res), f, indent=1)
    os.replace(tmp, out)
    if saved_bad:
        raise RuntimeError('%s %s: runs differ from the saved %s: %r' % (pair, tf, os.path.basename(fn), saved_bad))
    return res


def _same(a, b):
    skip = ('path', 'params')
    ca, cb = clean(a), clean(b)
    return all(ca[k] == cb[k] for k in ca if k not in skip)


def table(res):
    """The cell as text: one line per run."""
    lines = ['%s %s: %d bars, window %d..%d (%.1fs)' % (res['pair'], res['tf'], res['bars'], res['window'][0],
                                                       res['window'][1], res['seconds']),
             '  %-28s %6s %9s %7s %6s %7s %8s %8s %11s %s' % ('run', 'trades', 'net %', 'pf', 'win %', 'maxDD %',
                                                             'h1r %', 'h2r %', 'L / S', 'exits sl/tp/rev/blk/time/hyb/end')]
    for group in ('runs', 'reference'):
        for key, s in res[group].items():
            e = s['exits']
            pf = s['pf']
            lines.append('  %-28s %6d %+9.3f %7s %6.1f %7.2f %+8.3f %+8.3f %5d/%-5d %d/%d/%d/%d/%d/%d/%d'
                         % (key, s['trades'], s['net_pct'], ('%.3f' % pf) if isinstance(pf, float) and math.isfinite(pf) else str(pf),
                            s['win_pct'] if s['trades'] else float('nan'), s['max_dd_pct'], s['h1r_pct'], s['h2r_pct'],
                            s['long'], s['short'], e['sl'], e['tp'], e['reverse'], e['blocked_close'], e['time'],
                            e['hybrid'], e['end']))
    c = res['checks']
    lines.append('  checks: %s tv runs equal to %s: %s of %s; summary_fast == full summary: %s%s'
                 % ('normal / reversed', c['saved_file'], c['saved_runs_equal'], c['saved_runs_compared'],
                    c['summary_fast_equal'],
                    '' if c['mag_equals_tv_on_chart_1'] is None else '; chart 1 mag == tv: %s' % c['mag_equals_tv_on_chart_1']))
    return '\n'.join(lines)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    save_trades = '--trades' in argv
    if len(args) < 2 or args[0] not in hrd.WINDOWS or any(tf not in TFS for tf in args[1:]):
        print(__doc__)
        return 2
    pair = args[0]
    if save_trades:
        os.makedirs(TRD, exist_ok=True)
    for tf in args[1:]:
        res = run_cell(pair, tf, save_trades)
        print(table(res), flush=True)
        hrd._SIG.clear()
        hrd._PERM.clear()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
