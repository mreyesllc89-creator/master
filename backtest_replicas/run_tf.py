"""By-timeframe backtest of XPW v2.8 (trailing-TP variant) with and without the
FlashGold Direction Filter, using the reconciled replicas xpw.py, fgf.py and
engine.py.

Usage: python3 -I run_tf.py PAIR TF [TF ...]   -> out/run_<PAIR>_<TF>.json

Variants per timeframe:
  off       filter off (the pasted v2.8)
  on        filter on, defaults ("Blocked entry still closes the other side" on)
  on_noblk  filter on, blocked entries do nothing
  rev_off   filter off, Reverse every label on
  rev_on    filter on,  Reverse every label on

Money: initial capital 10,000, 10% of equity per entry (the script's default
quantity). Two figures per variant:
  tv0   no costs (TradingView with the script's own Properties: commission 0,
        slippage 0), compounding: each entry's quantity = 10% of the equity
        (initial + closed P/L) when it is placed, as strategy.percent_of_equity
        does without open profit.
  cost  same with costs: XAU $0.30 per round trip per ounce; BTC 0.02% of price
        per side + $0.20 per round trip per coin.
"""
import json
import sys
import time

import numpy as np
import pandas as pd

W = '/tmp/claude-0/-home-user-master/945e8df4-8527-5484-84f3-50cef64e8e3c/scratchpad/xpwbt/'
sys.path.insert(0, W)
import xpw      # noqa: E402
import fgf      # noqa: E402
import engine   # noqa: E402

WINDOWS = {
    'BTC': (1731801600, 1794873600),   # 2024-11-17 .. 2026-11-17 UTC
    'XAU': (1483315200, 1529366400),   # 2017-01-02 .. 2018-06-19 UTC
}
CAP = 10000.0
FRAC = 0.10


def cost_per_unit(pair, entry, exitp):
    if pair == 'XAU':
        return 0.30
    return 0.0002 * (entry + exitp) + 0.20


def metrics(pair, trades, start, end, with_cost):
    if trades is None or len(trades) == 0:
        return {'trades': 0}
    t = trades.sort_values(['exit_time', 'entry_time']).reset_index(drop=True)
    gross = t['dir'].astype(float) * (t['exit_px'] - t['entry_px'])
    cst = np.array([cost_per_unit(pair, a, b) for a, b in zip(t['entry_px'], t['exit_px'])]) if with_cost else np.zeros(len(t))
    pnl_u = gross.values - cst                       # P/L per unit
    # compounding on closed equity at entry time
    order = np.argsort(t['entry_time'].values, kind='stable')
    exit_t = t['exit_time'].values
    eq_closed = CAP
    realized = np.zeros(len(t))
    qty = np.zeros(len(t))
    # process events in time order: exits before entries at the same timestamp
    ev = [(exit_t[i], 0, i) for i in range(len(t))] + [(t['entry_time'].values[i], 1, i) for i in range(len(t))]
    ev.sort()
    for ts, kind, i in ev:
        if kind == 1:
            qty[i] = FRAC * max(eq_closed, 0.0) / t['entry_px'].values[i]
        else:
            realized[i] = qty[i] * pnl_u[i]
            eq_closed += realized[i]
    curve = CAP + np.cumsum(realized)                 # by exit order (t is sorted by exit)
    peak = np.maximum.accumulate(np.concatenate([[CAP], curve]))[1:]
    dd = np.max((peak - curve) / peak) if len(curve) else 0.0
    wins = realized[realized > 0].sum()
    losses = -realized[realized < 0].sum()
    mid = start + (end - start) // 2
    h1 = realized[exit_t <= mid].sum()
    h2 = realized[exit_t > mid].sum()
    ret = pnl_u / t['entry_px'].values
    return {
        'trades': int(len(t)),
        'net_pct': round(100 * (curve[-1] - CAP) / CAP, 2),
        'pf': round(wins / losses, 2) if losses > 0 else None,
        'win_pct': round(100 * float((realized > 0).mean()), 1),
        'max_dd_pct': round(100 * dd, 2),
        'half1_pct': round(100 * h1 / CAP, 2),
        'half2_pct': round(100 * h2 / CAP, 2),
        'avg_trade_ret_pct': round(100 * float(ret.mean()), 4),
        'max_concurrent': int(max_concurrent(t)),
        'exit_kinds': t['exit_kind'].value_counts().to_dict(),
    }


def max_concurrent(t):
    ev = sorted([(a, 1) for a in t['entry_time']] + [(b, -1) for b in t['exit_time']], key=lambda x: (x[0], x[1]))
    c = m = 0
    for _, d in ev:
        c += d
        m = max(m, c)
    return m


def run(pair, tf):
    start, end = WINDOWS[pair]
    t0 = time.time()
    sig = xpw.xpw_signals(pair, tf, start, end, {})
    t1 = time.time()
    perm = fgf.fgf_permissions(pair, tf, start, end, {})
    t2 = time.time()
    sig_rev = xpw.xpw_signals(pair, tf, start, end, {'reverseAll': True})
    out = {'pair': pair, 'tf': tf, 'start': start, 'end': end, 'bars': int(len(sig)),
           'timing_s': {'xpw': round(t1 - t0, 1), 'fgf': round(t2 - t1, 1)},
           'perm_share': {'buyOk': round(float(perm['buyOk'].mean()), 3), 'sellOk': round(float(perm['sellOk'].mean()), 3)},
           'variants': {}}
    variants = {
        'off': (sig, None, {'fgfOn': False}),
        'on': (sig, perm, {'fgfOn': True, 'fgfBlkClose': True}),
        'on_noblk': (sig, perm, {'fgfOn': True, 'fgfBlkClose': False}),
        'rev_off': (sig_rev, None, {'fgfOn': False}),
        'rev_on': (sig_rev, perm, {'fgfOn': True, 'fgfBlkClose': True}),
    }
    for name, (s, p, prm) in variants.items():
        tr, summ = engine.backtest(pair, tf, s, p, prm)
        tr.to_parquet(W + f'out/trades_{pair}_{tf}_{name}.parquet')
        out['variants'][name] = {
            'tv0': metrics(pair, tr, start, end, False),
            'cost': metrics(pair, tr, start, end, True),
            'summary': {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v)) for k, v in (summ or {}).items()},
        }
    out['timing_s']['total'] = round(time.time() - t0, 1)
    json.dump(out, open(W + f'out/run_{pair}_{tf}.json', 'w'), indent=1, default=str)
    return out


if __name__ == '__main__':
    pair = sys.argv[1]
    for tf in sys.argv[2:]:
        o = run(pair, tf)
        v = o['variants']
        print(pair, tf, o['bars'], 'bars', o['timing_s'],
              {k: (v[k]['tv0'].get('trades'), v[k]['tv0'].get('net_pct'), v[k]['cost'].get('net_pct')) for k in v}, flush=True)
