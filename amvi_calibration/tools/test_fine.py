"""The second-by-second order walk, computed two ways that must give the same trades:

  shortcut    the engine's normal mode: 1-minute bars, and the seconds only inside the minutes
              in which an order could fill;
  every second  each second of every minute handed to the same bar walk, one after the other.

Also prints how many minutes have their seconds (and how many were refused because the
seconds do not rebuild the minute's open, high, low and close).

usage: python test_fine.py [n_settings_per_timeframe] [seed] [start] [end]
"""
import sys

import numpy as np
from numba import njit

import amvi_engine as E
import bars
import space


@njit(cache=True)
def _flatten(mt, mo, mh, ml, mc, s0, s1, sec, so, sh, sl, sc, mult):
    n = mt.size
    total = 0
    for j in range(n):
        total += max(1, s1[j] - s0[j])
    T = np.empty(total, np.int64)
    O = np.empty(total)
    H = np.empty(total)
    L = np.empty(total)
    C = np.empty(total)
    a = np.empty(n, np.int64)
    b = np.empty(n, np.int64)
    k = 0
    for j in range(n):
        a[j] = k
        if s1[j] > s0[j]:
            for q in range(s0[j], s1[j]):
                T[k] = np.int64(sec[q]) * 1000
                O[k] = so[q] / mult
                H[k] = sh[q] / mult
                L[k] = sl[q] / mult
                C[k] = sc[q] / mult
                k += 1
        else:
            T[k], O[k], H[k], L[k], C[k] = mt[j], mo[j], mh[j], ml[j], mc[j]
            k += 1
        b[j] = k
    return T, O, H, L, C, a, b


def every_second(ft, chart_tf, p, signals, fee, slip):
    mk = ft.mk
    m1, s, ch = mk.m1, mk.sec, mk.tf(chart_tf)
    T, O, H, L, C, a, b = _flatten(m1.t, m1.o, m1.h, m1.l, m1.c, s.s0, s.s1, s.sec, s.o, s.h, s.l, s.c, s.mult)
    ci0, ci1 = a[ch.i0], b[ch.i1 - 1]
    trig, volc, zone = signals
    out = E.simulate(ch.t, ch.o, ch.c, ci0, ci1, ft.atr(chart_tf, p["exit_atr"]), T, O, H, L, C, trig, zone, volc,
                     bool(p["inverted"]), float(p["sl"]), float(p["tp"]), bool(p["trail"]), float(p["trail_act"]), float(p["trail_off"]),
                     bool(p["vol_exit"]), int(p["max_bars"]), int(p["wait"]), float(fee), float(slip), E.MINTICK, 0, len(ch), chart_tf * bars.MIN_MS,
                     *E.NO_SECONDS, False)
    keys = ("entry_t", "exit_t", "dir", "entry_px", "exit_px", "risk", "r", "why", "sig_bar")
    return dict(zip(keys, out))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    start = sys.argv[3] if len(sys.argv) > 3 else "2026-07-01"
    end = sys.argv[4] if len(sys.argv) > 4 else "2026-10-01"
    m1 = bars.load_1m(start=start, end=end)
    sec = bars.load_1s(start=start, end=end)
    if sec is None:
        raise SystemExit("no one-second files for this period: run fetch_1s.py first")
    mk = bars.Market(m1, sec)
    ft = E.Features(mk)
    print(f"{start} to {end}: {len(m1):,} minutes, {sec.covered:,} with their seconds ({sec.covered / len(m1) * 100:.2f}%), "
          f"{sec.refused:,} refused, {sec.open_differs:,} open at the previous close instead of the first trade; {len(sec):,} seconds")
    rng = np.random.default_rng(seed)
    bad = total = diff_1m = 0
    for ctf in (1, 3, 5, 15, 60, 240):
        ch = mk.tf(ctf)
        for k in range(n):
            p = space.draw(rng, ctf)
            if max(p["tfs"]) >= 240:
                p["slow"], p["norm"] = 50, 100
            if k % 2 == 0:               # half of the cases: tight trailing stops, the hard case
                p["trail"], p["trail_act"], p["trail_off"] = True, float(rng.choice([0.5, 1.0])), float(rng.choice([0.5, 1.0]))
            ep = E.P(**space.engine_params(p))
            trig, volc, _ = E.trigger_arrays(ft, ctf, ep)
            zone = E.zone_array(ft, ctf, ep)
            if k % 3 != 0:               # dense random signals so that every case has many trades
                trig = rng.random(len(ch)) < (0.04 if ctf <= 5 else 0.15)
                zone = rng.choice(np.array([-1, 0, 1], np.int8), size=len(ch))
                volc = rng.random(len(ch)) < 0.02
            sig = (np.asarray(trig), np.asarray(volc), np.asarray(zone))
            fee, slip = float(rng.choice([0.0, 0.0005])), int(rng.choice([0, 1, 3]))
            a = E.run(ft, ctf, ep, fee=fee, slip_ticks=slip, signals=sig, walk="fine")
            b = every_second(ft, ctf, ep, sig, fee, slip)
            c = E.run(ft, ctf, ep, fee=fee, slip_ticks=slip, signals=sig, walk="1m")
            total += 1
            same = a["r"].size == b["r"].size and all(np.array_equal(a[key], b[key]) for key in a)
            if a["r"].size == c["r"].size:
                diff_1m += int((np.abs(a["exit_px"] - c["exit_px"]) > 1e-9).sum())
            else:
                diff_1m += abs(a["r"].size - c["r"].size)
            tag = (f"chart {ctf}m #{k} sl={ep['sl']} tp={ep['tp']} trail={ep['trail']}({ep['trail_act']},{ep['trail_off']}) "
                   f"maxbars={ep['max_bars']} trades={a['r'].size} sum {a['r'].sum():+.2f}R (1-minute walk {c['r'].sum():+.2f}R)")
            if same:
                print("ok      ", tag)
            else:
                bad += 1
                print("MISMATCH", tag, f"every-second trades={b['r'].size} sum {b['r'].sum():+.2f}R")
                for i in range(min(a["r"].size, b["r"].size)):
                    if any(a[key][i] != b[key][i] for key in a):
                        print("     first difference at trade", i, {key: (a[key][i], b[key][i]) for key in a if a[key][i] != b[key][i]})
                        break
    print(f"second-by-second walk: {total - bad} of {total} cases identical to walking every second; "
          f"{diff_1m} exits differ from the 1-minute walk")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
