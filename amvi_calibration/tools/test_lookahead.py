"""Look-ahead test (written by an independent reviewer during the code review): perturb every
1-minute bar that OPENS at or after T and check that everything the engine shows for chart
bars that CLOSE at or before T is bit-identical.

usage: python test_lookahead.py      (three months of data, 12 timeframe combinations, 10 cut times)

Compared per chart bar: trigger, vol-collapse, hot count, zone, the AMVI value seen per
requested timeframe, and the filter arm seen (level, direction, band ATR, armed, on-signal-bar,
candle index relative to the arm).
"""
import sys
import numpy as np
import pandas as pd
import bars
import amvi_engine as E
from bars import MIN_MS, Bars


def ms(s):
    return int(pd.Timestamp(s, tz='UTC').value // 10 ** 6)


def perturbed(m1, T, seed):
    """Copy of the 1m bars with every bar opening at or after T on another price path."""
    rng = np.random.default_rng(seed)
    k = int(np.searchsorted(m1.t, T, side='left'))
    n = m1.t.size - k
    mult = np.exp(0.03 + np.cumsum(rng.normal(0, 0.004, n)))   # a jump at T, then another random walk
    wig = 1.0 + np.abs(rng.normal(0, 0.002, n))
    o, h, l, c = m1.o.copy(), m1.h.copy(), m1.l.copy(), m1.c.copy()
    o[k:] *= mult
    c[k:] *= mult * np.exp(rng.normal(0, 0.001, n))
    h[k:] = np.maximum(np.maximum(o[k:], c[k:]), h[k:] * mult * wig)
    l[k:] = np.minimum(np.minimum(o[k:], c[k:]), l[k:] * mult / wig)
    return Bars(1, m1.t.copy(), o, h, l, c, m1.v.copy(), m1.i0.copy(), m1.i1.copy())


def seen(m1, chart_tf, p):
    ft = E.Features(bars.Market(m1))
    ch = ft.mk.tf(chart_tf)
    out = {}
    trig, volc, hot = E.trigger_arrays(ft, chart_tf, p)
    out['trig'], out['volc'], out['hot'] = trig, volc, hot
    for tf in p['tfs']:
        out[f'amvi_seen_{tf}'] = E.gather(ft.amvi(tf, p), ft.idx('amvi', chart_tf, tf))
    F = p['f_tf']
    arms = E.filter_arms(ft, p)
    out['zone'] = E.zone_array(ft, chart_tf, p, arms)
    arm_idx, level, direction, atr_f = arms
    kc, at_clock = ft.idx('arm_open' if (p['check_open'] or F <= chart_tf) else 'arm', chart_tf, F)
    a = np.where(kc >= 0, arm_idx[np.maximum(kc, 0)], -1)
    ai = np.maximum(a, 0)
    out['arm_level'] = np.where(a >= 0, level[ai], np.nan)
    out['arm_dir'] = np.where(a >= 0, direction[ai], 0)
    out['arm_atr'] = np.where(a >= 0, atr_f[ai], np.nan)
    out['arm_candles_since'] = np.where(a >= 0, kc + (~at_clock) - a, -1)
    out['arm_on_sig'] = at_clock & (a == kc)
    out['exit_atr'] = ft.atr(chart_tf, p['exit_atr'])
    return ch.t, out


def same(x, y):
    if x.dtype.kind == 'f':
        return (x == y) | (np.isnan(x) & np.isnan(y))
    return x == y


SMALL = dict(fast=3, slow=10, sd=5, cr=5, norm=10)   # so that a daily AMVI exists inside 3 months
COMBOS = [
    # name, chart, overrides
    ('default 15m chart, filter 60 above', 15, dict(tfs=(15, 60, 240), f_tf=60, parent_tf=60, zones=(60, 120, 240), min_aligned=1)),
    ('5m chart, filter 1m BELOW, parent 60 above the filter, daily AMVI', 5, dict(tfs=(1, 5, 1440), f_tf=1, parent_tf=60, zones=(1, 2, 4), min_aligned=2, **SMALL)),
    ('15m chart, filter 240 above, parent 1D, zones below the filter, daily AMVI', 15, dict(tfs=(5, 60, 1440), f_tf=240, parent_tf=1440, zones=(60, 120, 240), min_aligned=1, **SMALL)),
    ('60m chart, filter 60 EQUAL, parent 240, daily AMVI', 60, dict(tfs=(1, 60, 1440), f_tf=60, parent_tf=240, zones=(60, 120, 240), min_aligned=2, **SMALL)),
    ('240m chart, filter 1D above, daily AMVI', 240, dict(tfs=(30, 240, 1440), f_tf=1440, parent_tf=1440, zones=(60, 120, 240), min_aligned=1, **SMALL)),
    ('240m chart, filter 15 BELOW, entry-price level, candles permission', 240, dict(tfs=(60, 240, 1440), f_tf=15, parent_tf=60, zones=(15, 30, 60), min_aligned=1, lv_mode='entry', perm_candles=3, use_burst=True, any_combo=False, **SMALL)),
    ('2m chart, filter 5 above (not a multiple), AMVI 1/5/15', 2, dict(tfs=(1, 5, 15), f_tf=5, parent_tf=60, zones=(5, 10, 20), min_aligned=1)),
    ('10m chart, filter 15 above (not a multiple), level at candle open', 10, dict(tfs=(5, 15, 60), f_tf=15, parent_tf=15, zones=(15, 30, 60), min_aligned=1, check_open=True)),
    ('1m chart, filter 1 EQUAL', 1, dict(tfs=(1, 5), f_tf=1, parent_tf=1, zones=(1, 2, 4), min_aligned=1, band=0.0)),
    ('30m chart, filter 5 BELOW, burst only, drift', 30, dict(tfs=(15, 30, 1440), f_tf=5, parent_tf=5, zones=(5, 10, 20), use_burst=True, any_combo=False, use_drift=True, drift_bars=30, band=0.25, **SMALL)),
    ('15m chart, filter 60 above, level at candle open, entry level, no band', 15, dict(tfs=(1, 15, 1440), f_tf=60, parent_tf=240, zones=(60, 120, 240), check_open=True, lv_mode='entry', band=0.0, **SMALL)),
    ('3m chart, filter 5 above (not a multiple), filter zones off', 3, dict(tfs=(1, 5, 60), f_tf=5, parent_tf=5, zones=(60, 120, 240), use_zones=False, band=0.5)),
]
TS = ['2025-03-10 00:00', '2025-03-10 13:37', '2025-03-11 14:00', '2025-03-12 14:45', '2025-03-13 16:00',
      '2025-03-14 09:05', '2025-03-15 08:00', '2025-03-16 00:01', '2025-03-17 23:59', '2025-03-18 12:10']

if __name__ == '__main__':
    m1 = bars.load_1m(start='2025-01-01', end='2025-04-01')
    print('1m bars', m1.t.size)
    total_bad = 0
    for name, ctf, ov in COMBOS:
        p = E.P(**ov)
        t0, base = seen(m1, ctf, p)
        worst = {}
        changed_after = {k: 0 for k in base}
        for j, Ts in enumerate(TS):
            T = ms(Ts)
            t1, pert = seen(perturbed(m1, T, 100 + j), ctf, p)
            assert np.array_equal(t0, t1)
            known = t0 + ctf * MIN_MS <= T            # chart bars closed at or before T
            for k in base:
                d = ~same(np.asarray(base[k]), np.asarray(pert[k]))
                nbad = int((d & known).sum())
                if nbad:
                    worst[k] = worst.get(k, 0) + nbad
                    i = int(np.nonzero(d & known)[0][0])
                    print(f'   LOOK-AHEAD {name}: {k} differs on {nbad} bars closed by T={Ts}; first bar opens '
                          f'{pd.Timestamp(t0[i], unit="ms")} base={base[k][i]} pert={pert[k][i]}')
                changed_after[k] += int((d & ~known).sum())
        total_bad += sum(worst.values())
        nontrivial = {k: int(np.isfinite(np.asarray(base[k], dtype=float)).sum()) for k in base if k.startswith('amvi_seen')}
        print(('FAIL ' if worst else 'ok   ') + name)
        print('      non-NaN AMVI bars per tf:', nontrivial, '| trig', int(base['trig'].sum()), 'zone+', int((base['zone'] == 1).sum()),
              'zone-', int((base['zone'] == -1).sum()))
        print('      values that changed AFTER T (power of the test):', {k: v for k, v in changed_after.items()})
    print('TOTAL look-ahead differences:', total_bad)
    sys.exit(1 if total_bad else 0)
