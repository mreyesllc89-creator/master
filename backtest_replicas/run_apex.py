"""ApexForge Flow Resonance + FGF by timeframe, with the canonical module apex.py.

    python3 -I run_apex.py PAIR [TF ...]     (default TFs: 1 5 15 30 60 120 240)

For each cell (PAIR, TF) runs the variants
    off      fgfOn False                 (= the original script)
    on       defaults (filter on, blocked-opposite close on)
    on_noblk blkClose False
    rev_off  reverse True, fgfOn False   (reversed-label control, literal brackets)
    rev_on   reverse True
each with cost 'tv' (the script's 0.04% per side, what TradingView shows) and
'ours', plus three extras with cost 'tv' only:
    on_left      pivotTies 'left_strict' (tie-rule sensitivity)
    rev_off_mir / rev_on_mir   reverse with reverseStops 'mirror' (bracket sensitivity)
and writes out/apex_<PAIR>_<TF>.json: {variant: {cost: summary}} with every summary field
of apex.run, plus 'stopped_at_fill_open' (trades opened and stopped at the same open).
Trades of the cost-'tv' runs go to out/apex_trades/<PAIR>_<TF>_<variant>.parquet.
"""
import json
import math
import os
import sys
import time

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
import apex  # noqa: E402

OUT = os.path.join(W, 'out')
TFS = ['1', '5', '15', '30', '60', '120', '240']
VARIANTS = {
    'off': {'fgfOn': False},
    'on': {},
    'on_noblk': {'blkClose': False},
    'rev_off': {'reverse': True, 'fgfOn': False},
    'rev_on': {'reverse': True},
}
EXTRAS = {
    'on_left': {'pivotTies': 'left_strict'},
    'rev_off_mir': {'reverse': True, 'fgfOn': False, 'reverseStops': 'mirror'},
    'rev_on_mir': {'reverse': True, 'reverseStops': 'mirror'},
}


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


def one(pair, tf, name, p, cost, save):
    q = dict(p)
    q['cost'] = cost
    tr, s = apex.run(pair, tf, q)
    s = dict(s)
    s['variant'] = name
    s['stopped_at_fill_open'] = int(((tr.entry_bar == tr.exit_bar) & (tr.exit_kind == 'sl')
                                     & (tr.exit_px == tr.entry_px)).sum())
    if save:
        d = os.path.join(OUT, 'apex_trades')
        os.makedirs(d, exist_ok=True)
        tr.to_parquet(os.path.join(d, f'{pair}_{tf}_{name}.parquet'))
    return clean(s)


def cell(pair, tf):
    t0 = time.time()
    res = {}
    for name, p in VARIANTS.items():
        res[name] = {c: one(pair, tf, name, p, c, c == 'tv') for c in ('tv', 'ours')}
    for name, p in EXTRAS.items():
        res[name] = {'tv': one(pair, tf, name, p, 'tv', False)}
    res['_meta'] = {'pair': pair, 'tf': tf, 'module': 'apex.py', 'seconds': round(time.time() - t0, 1),
                    'window': list(apex.WINDOWS[pair])}
    f = os.path.join(OUT, f'apex_{pair}_{tf}.json')
    with open(f, 'w') as fh:
        json.dump(res, fh, indent=1)
    on, off = res['on']['tv'], res['off']['tv']
    print(f"{pair} {tf:>4}: off {off['trades']:6d} tr {off['net_pct']:+8.3f}%  on {on['trades']:6d} tr "
          f"{on['net_pct']:+8.3f}%  ({res['_meta']['seconds']}s) -> {f}", flush=True)


if __name__ == '__main__':
    pair = sys.argv[1]
    for tf in (sys.argv[2:] or TFS):
        cell(pair, tf)
