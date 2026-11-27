"""run_inv_apex.py: ApexForge Flow Resonance + FGF, "Inverted direction" (Update 1) by
timeframe, with the canonical module apex.py (INV_BT_SPEC.md, task 3).

    python3 -I run_inv_apex.py PAIR TF [TF ...] [--trades]

For each cell (PAIR, TF), full window (BTC 1731801600..1794873600, XAU
1483315200..1529366400 by t_close), default inputs of the Pine, runs

    direction {normal, inverted} x filter {off, on} x path {tv, mag} x cost {script, ours}

and writes out/inv_apex_<PAIR>_<TF>.json:

    runs["<direction>/<filter>/<path>/<cost>"] = the full summary of apex.simulate
        (trades, net_pct, pf, win_pct, max_dd_pct, long / short = REAL sides, raw / blocked
        signal counts = the SIGNAL's side, half1_pct / half2_pct, the fair halves h1r_pct /
        h2r_pct with h1_trades / h2_trades, exit_kinds and every exit_<kind> count,
        avg_bars_held, exposure, costs, final_equity, stopped_at_fill_open, params,
        exit_params, inv) plus the four key fields direction / filter / path / cost.
    reference["<labels>/<filter>/<path>/<cost>"] = the existing reversed-label runs, for
        comparison: labels rev_literal (apex param reverse=True: the signals swapped BEFORE the
        gate, each side keeps its own bracket; = the saved rev_off / rev_on of run_apex.py)
        and rev_mirror (reverse=True, reverseStops='mirror'; = the saved rev_off_mir /
        rev_on_mir). With the filter off, inverted == rev_mirror (same trades).
    _meta: pair, tf, window, what each key value means, seconds.

direction: normal = the script as before (apxInv off); inverted = apxInv on.
filter:    off = "Enable filter" off (fgfOn False); on = the FlashGold Direction Filter.
path:      tv = TradingView's bar path (no Bar Magnifier); mag = exits along the 1-minute
           sub-bars (Bar Magnifier). Chart "1": mag is run with the real sub-bar table (every
           chart bar is its own sub-bar) and equals tv.
cost:      script = the script's own Properties, what TradingView shows (apex cost 'tv':
           commission 0.04% of the order value per side); ours = XAU $0.30 per ounce per
           round trip, BTC 0.02% per side + $0.20 per round trip (apex cost 'ours').
--trades also writes the trade lists of the cost-script runs to
out/inv_apex_trades/<PAIR>_<TF>_<direction>_<filter>_<path>.parquet.
"""
import json
import math
import os
import sys
import time

W = os.path.dirname(os.path.abspath(__file__))
if W not in sys.path:
    sys.path.insert(0, W)
import apex  # noqa: E402

OUT = os.path.join(W, 'out')
TFS = ('1', '5', '15', '30', '60', '120', '240')
DIRECTIONS = (('normal', False), ('inverted', True))
FILTERS = (('off', False), ('on', True))
PATHS = ('tv', 'mag')
COSTS = (('script', 'tv'), ('ours', 'ours'))
REFERENCE = (('rev_literal', {'reverse': True, 'reverseStops': 'literal'}),
             ('rev_mirror', {'reverse': True, 'reverseStops': 'mirror'}))


def clean(x):
    if isinstance(x, float):
        if math.isnan(x):
            return None
        if math.isinf(x):
            return 'inf' if x > 0 else '-inf'
        return x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if hasattr(x, 'item'):
        return clean(x.item())
    return x


def one(S, inv, path, cost, tags):
    out, s = apex.simulate(S, {'inv': inv, 'path': path, 'cost': cost})
    s = dict(s)
    s.update(tags)
    return out, clean(s)


def cell(pair, tf, save_trades=False, out_dir=None):
    """One (PAIR, TF): runs everything and writes the JSON (to out/, or to out_dir)."""
    t0 = time.time()
    out_dir = out_dir or OUT
    start, end = apex.WINDOWS[pair]
    runs = {}
    ref = {}
    S = {fname: apex.prepare(pair, tf, {'fgfOn': fon}) for fname, fon in FILTERS}
    for dname, inv in DIRECTIONS:
        for fname, _ in FILTERS:
            for path in PATHS:
                for cname, cost in COSTS:
                    out, s = one(S[fname], inv, path, cost,
                                 {'direction': dname, 'filter': fname, 'path': path, 'cost': cname})
                    runs['%s/%s/%s/%s' % (dname, fname, path, cname)] = s
                    if save_trades and cname == 'script':
                        d = os.path.join(out_dir, 'inv_apex_trades')
                        os.makedirs(d, exist_ok=True)
                        apex.trades_frame(S[fname], out).to_parquet(
                            os.path.join(d, '%s_%s_%s_%s_%s.parquet' % (pair, tf, dname, fname, path)))
    for lname, lp in REFERENCE:
        for fname, fon in FILTERS:
            Sr = apex.prepare(pair, tf, dict(lp, fgfOn=fon))
            for path in PATHS:
                for cname, cost in COSTS:
                    _, s = one(Sr, False, path, cost,
                               {'direction': lname, 'filter': fname, 'path': path, 'cost': cname})
                    ref['%s/%s/%s/%s' % (lname, fname, path, cname)] = s
    meta = {
        'strategy': 'apex', 'pair': pair, 'tf': tf, 'window': [int(start), int(end)],
        'module': 'apex.py', 'pine': 'ApexForge_Flow_Resonance_Strategy_FGF.pine (HEAD d28ba97, Update 1)',
        'inputs': 'Pine defaults (blocked-opposite close on, trailing take profit off, rrRatio 3, ...)',
        'key': 'direction/filter/path/cost',
        'direction': {'normal': 'apxInv off', 'inverted': 'apxInv on (Update 1)'},
        'filter': {'off': 'fgfOn False', 'on': 'fgfOn True'},
        'path': {'tv': "TradingView bar path", 'mag': 'Bar Magnifier: exits along the 1-minute sub-bars'},
        'cost': {'script': "apex cost 'tv': 0.04% of the order value per side (the script's Properties)",
                 'ours': "apex cost 'ours': XAU $0.30 per ounce per round trip; BTC 0.02% per side + $0.20 per round trip"},
        'reference': {'rev_literal': "reverse=True (signals swapped before the gate), each side's own bracket",
                      'rev_mirror': "reverse=True, reverseStops='mirror'; filter off: the same trades as inverted"},
        'sizing': '1% of equity per entry (default_qty_value 1), initial capital 1,000,000: net_pct is % of the initial capital',
        'bars': int(len(S['off']['c'])),
        'seconds': round(time.time() - t0, 1),
    }
    res = {'_meta': meta, 'runs': runs, 'reference': ref}
    os.makedirs(out_dir, exist_ok=True)
    f = os.path.join(out_dir, 'inv_apex_%s_%s.json' % (pair, tf))
    tmp = f + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as fh:
        json.dump(res, fh, indent=1)
    os.replace(tmp, f)
    return res, f


def _row(s):
    pf = s['pf']
    pf = '   nan' if pf is None else ('   inf' if pf == 'inf' else '%6.3f' % pf)
    wp = s['win_pct']
    wp = '  nan' if wp is None else '%5.1f' % wp
    ab = s['avg_bars_held']
    ab = '   nan' if ab is None else '%6.1f' % ab
    ek = ' '.join('%s %d' % (k, v) for k, v in s['exit_kinds'].items())
    return ('%5d tr %+9.4f%% pf %s win %s%% dd %7.4f%% | L %4d S %4d | h1r %+8.4f%% (%d) h2r %+8.4f%% (%d) | '
            'bars %s expo %.3f | %s'
            % (s['trades'], s['net_pct'], pf, wp, s['max_dd_pct'], s['long'], s['short'], s['h1r_pct'],
               s['h1_trades'], s['h2r_pct'], s['h2_trades'], ab, s['exposure'], ek))


def show(res, f):
    m = res['_meta']
    print('== apex %s %s: %d bars, window %d..%d (%.1fs) -> %s' % (m['pair'], m['tf'], m['bars'], m['window'][0],
                                                                 m['window'][1], m['seconds'], f), flush=True)
    for cname, _ in COSTS:
        for path in PATHS:
            for fname, _ in FILTERS:
                for dname in ('normal', 'inverted', 'rev_literal', 'rev_mirror'):
                    src = res['runs'] if dname in ('normal', 'inverted') else res['reference']
                    s = src['%s/%s/%s/%s' % (dname, fname, path, cname)]
                    print('  cost %-6s path %-3s filter %-3s %-11s %s' % (cname, path, fname, dname, _row(s)), flush=True)


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    flags = [a for a in argv if a.startswith('--')]
    if len(args) < 2 or args[0] not in apex.WINDOWS or any(a not in ('--trades',) for a in flags):
        print(__doc__)
        return 2
    pair = args[0]
    for tf in args[1:]:
        if tf not in TFS:
            print('unknown TF %r (one of %s)' % (tf, ', '.join(TFS)))
            return 2
    t0 = time.time()
    for tf in args[1:]:
        res, f = cell(pair, tf, '--trades' in flags)
        show(res, f)
    print('all done in %.1fs' % (time.time() - t0), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
