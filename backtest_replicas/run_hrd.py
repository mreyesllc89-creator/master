"""HRD Full Divergence v1.03 + FGF by time frame, with the canonical replica hrd.py.

For PAIR in BTC, XAU and TF in 1, 5, 15, 30, 60, 120, 240 (full windows), runs the variants
    off      fgfOn False                       (= the original script)
    on       default (filter on, hrdBlkClose on)
    on_noblk blkClose False
    rev_off  reverse True, fgfOn False         (InpReverseTrading: the reversed-label control)
    rev_on   reverse True
each with cost 'tv' (the script's own properties: no commission) and 'ours', plus the pivot tie
control (pivotTies 'left_strict', off / on, cost 'tv'), and writes out/hrd_<PAIR>_<TF>.json with
every summary field. Trades go to out/hrd_trades/hrd_<PAIR>_<TF>_<variant>_<cost>.parquet.

Usage: python3 -I run_hrd.py PAIR [TF ...]
"""
import json
import math
import os
import sys
import time

import numpy as np

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
import hrd  # noqa: E402

OUT = os.path.join(W, 'out')
TRD = os.path.join(OUT, 'hrd_trades')
TFS = ['1', '5', '15', '30', '60', '120', '240']
VARIANTS = [
    ('off', {'fgfOn': False}),
    ('on', {}),
    ('on_noblk', {'blkClose': False}),
    ('rev_off', {'reverse': True, 'fgfOn': False}),
    ('rev_on', {'reverse': True}),
]
TIES = [('off_left_strict', {'fgfOn': False, 'pivotTies': 'left_strict'}),
        ('on_left_strict', {'pivotTies': 'left_strict'})]


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        v = float(v)
        if math.isnan(v):
            return None
        if math.isinf(v):
            return 'inf' if v > 0 else '-inf'
        return v
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def extras(tr, s):
    """Fields derived from the trade list on top of hrd.summarize()."""
    init = hrd.INITIAL_CAPITAL
    n = len(tr)
    end_pnl = float(tr.loc[tr['exit_kind'] == 'end', 'pnl'].sum()) if n else 0.0
    # TradingView's Net Profit counts closed trades only; a trade still open at the window end
    # is its Open P/L. net_pct here includes that trade closed at the last close.
    closed_pct = s['net_pct'] - end_pnl / init * 100.0
    # entries that fill at the same open as a time close_all of the previous trade (the new
    # trade then has no time exit): the reversal-sizing question in reconcile_hrd.md
    tt = 0
    inh = 0
    if n > 1:
        kind = tr['exit_kind'].to_numpy().astype(str)
        xb = tr['exit_bar'].to_numpy()
        eb = tr['entry_bar'].to_numpy()
        same = eb[1:] == xb[:-1]
        tt = int((same & (kind[:-1] == 'time')).sum())
        inh = int((same & (kind[:-1] == 'reverse')).sum())
    held = (tr['exit_bar'] - tr['entry_bar']).to_numpy() if n else np.zeros(0)
    return dict(net_closed_pct=closed_pct, end_trade_pnl_pct=end_pnl / init * 100.0,
                entries_after_time_exit_same_open=tt, reversal_entries=inh,
                avg_bars_held=float(held.mean()) if n else None,
                gross_costs=float(tr['costs'].sum()) if n else 0.0,
                avg_trade_pct=float(tr['pnl'].sum() / init * 100.0 / n) if n else None)


def run_cell(pair, tf, save_trades=True):
    res = dict(pair=pair, tf=tf, window=list(hrd.WINDOWS[pair]), runs={})
    t0 = time.time()
    for name, p in VARIANTS:
        for cost in ('tv', 'ours'):
            q = dict(p)
            q['cost'] = cost
            tr, s = hrd.run(pair, tf, q)
            s = dict(s)
            s.update(extras(tr, s))
            s['params'] = q
            res['runs'][f'{name}_{cost}'] = s
            if save_trades:
                tr.to_parquet(os.path.join(TRD, f'hrd_{pair}_{tf}_{name}_{cost}.parquet'))
    for name, p in TIES:
        q = dict(p)
        q['cost'] = 'tv'
        tr, s = hrd.run(pair, tf, q)
        s = dict(s)
        s.update(extras(tr, s))
        s['params'] = q
        res['runs'][f'{name}_tv'] = s
    res['seconds'] = round(time.time() - t0, 2)
    with open(os.path.join(OUT, f'hrd_{pair}_{tf}.json'), 'w') as f:
        json.dump(clean(res), f, indent=1)
    return res


def line(pair, tf, res):
    r = res['runs']
    a, b = r['off_tv'], r['on_tv']
    return (f"{pair} {tf:>3}: off {a['trades']:5d} {a['net_pct']:+8.3f}% pf {a['pf']:.3f} dd {a['max_dd_pct']:.2f} | "
            f"on {b['trades']:5d} {b['net_pct']:+8.3f}% pf {b['pf']:.3f} dd {b['max_dd_pct']:.2f} | "
            f"ours off/on {r['off_ours']['net_pct']:+.2f}/{r['on_ours']['net_pct']:+.2f} | "
            f"rev off/on {r['rev_off_tv']['net_pct']:+.2f}/{r['rev_on_tv']['net_pct']:+.2f} ({res['seconds']}s)")


def main():
    pair = sys.argv[1]
    tfs = sys.argv[2:] or TFS
    os.makedirs(TRD, exist_ok=True)
    for tf in tfs:
        res = run_cell(pair, tf)
        print(line(pair, tf, res), flush=True)


if __name__ == '__main__':
    main()
