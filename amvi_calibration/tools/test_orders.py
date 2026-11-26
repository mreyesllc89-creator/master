"""Hand-computed scenarios for the order simulation (amvi_engine.simulate).

Chart timeframe = 1 minute, so every chart bar is one 1-minute bar and the intrabar walk
(open -> nearer extreme -> other extreme -> close) can be followed by hand.
Run: python test_orders.py
"""
import numpy as np

import amvi_engine as E

TICK = 0.1


def sim(bars_ohlc, trig, zone, atr=2.0, volc=None, **kw):
    b = np.array(bars_ohlc, dtype=np.float64)
    n = b.shape[0]
    t = np.arange(n, dtype=np.int64) * 60_000
    o, h, l, c = (np.ascontiguousarray(b[:, k]) for k in range(4))
    i0 = np.arange(n, dtype=np.int64)
    tr = np.zeros(n, np.bool_)
    zn = np.zeros(n, np.int8)
    for k in trig:
        tr[k] = True
    for k, v in zone.items():
        zn[k] = v
    vc = np.zeros(n, np.bool_)
    for k in (volc or []):
        vc[k] = True
    a = np.full(n, float(atr))
    p = dict(inverted=False, sl=1.0, tp=0.0, use_trail=False, trail_act=1.5, trail_off=1.0, use_vol_exit=False,
             max_bars=0, wait=0, fee=0.0, slip_ticks=1.0)
    p.update(kw)
    out = E.simulate(t, o, c, i0, i0 + 1, a, t, o, h, l, c, tr, zn, vc,
                     p["inverted"], p["sl"], p["tp"], p["use_trail"], p["trail_act"], p["trail_off"], p["use_vol_exit"],
                     p["max_bars"], p["wait"], p["fee"], p["slip_ticks"], TICK, 0, n, 60_000,
                     *E.NO_SECONDS, False)
    keys = ("entry_t", "exit_t", "dir", "entry_px", "exit_px", "risk", "r", "why", "sig_bar")
    return dict(zip(keys, out))


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_long_then_stop():
    # signal at the close of bar 1 (close 100, ATR 2, stop 1 ATR): entry at bar 2's open + 1 tick
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (100.5, 101, 99, 100),      # fill bar: stop from the signal close = 98, not reached
            (100, 100.2, 98.5, 99),     # stop re-based on the entry price 100.6 -> 98.6, reached on the way down
            (99, 99.5, 98, 98.5)]
    t = sim(bars, trig=[1], zone={1: 1})
    assert t["r"].size == 1 and t["why"][0] == E.X_STOP
    assert close(t["entry_px"][0], 100.6) and close(t["exit_px"][0], 98.5)   # 98.6 less one tick of slippage
    assert t["entry_t"][0] == 2 * 60_000 and t["exit_t"][0] == 3 * 60_000
    assert close(t["r"][0], (98.5 - 100.6) / 2.0)


def test_fill_bar_uses_signal_close():
    # entry 1 above the signal close: on the fill bar the stop is 100 - 2 = 98 (not 101.1 - 2 = 99.1)
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (101, 101.2, 98.6, 99.5),   # low 98.6: above 98 -> the position survives the fill bar
            (99.5, 99.6, 99.0, 99.05)]  # next bar opens at 99.5 with the stop now 101.1 - 2 = 99.1: reached at 99.1
    t = sim(bars, trig=[1], zone={1: 1})
    assert t["r"].size == 1 and t["why"][0] == E.X_STOP
    assert close(t["entry_px"][0], 101.1) and close(t["exit_px"][0], 99.0) and t["exit_t"][0] == 3 * 60_000


def test_gap_through_stop_fills_at_open():
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (100, 100.4, 99.6, 100),
            (97, 97.5, 96.5, 97)]       # opens below the stop (98.1): fills at the open less a tick
    t = sim(bars, trig=[1], zone={1: 1})
    assert t["why"][0] == E.X_STOP and close(t["exit_px"][0], 96.9)


def test_trailing():
    # trail activation 1 ATR = 20 ticks above the entry (100.1 + 2 = 102.1), offset 0.5 ATR = 1.0
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (100, 100.4, 99.8, 100),
            (100, 103, 100, 102.5),     # low first (it equals the open), then 103: active, stop 102; close 102.5 stays above
            (102.4, 102.6, 101.5, 101.8)]  # high first, then down through 102
    t = sim(bars, trig=[1], zone={1: 1}, use_trail=True, trail_act=1.0, trail_off=0.5)
    assert t["r"].size == 1 and t["why"][0] == E.X_TRAIL
    assert close(t["entry_px"][0], 100.1) and close(t["exit_px"][0], 101.9) and t["exit_t"][0] == 4 * 60_000


def test_target_and_gap_target():
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (100, 100.4, 99.8, 100),
            (100, 104.5, 99.9, 104)]    # target 100.1 + 2 x 2 = 104.1 reached inside the bar: fills at 104.1
    t = sim(bars, trig=[1], zone={1: 1}, tp=2.0)
    assert t["why"][0] == E.X_TP and close(t["exit_px"][0], 104.1)
    bars[3] = (105, 105.5, 104.8, 105)  # opens beyond the target: fills at the open, no slippage
    t = sim(bars, trig=[1], zone={1: 1}, tp=2.0)
    assert t["why"][0] == E.X_TP and close(t["exit_px"][0], 105.0)


def test_reversal_and_inverted():
    bars = [(100, 100.5, 99.5, 100), (100, 100.5, 99.5, 100),
            (100, 100.4, 99.8, 100), (100, 100.4, 99.8, 100.2),
            (100.3, 100.6, 100.0, 100.4), (100.4, 100.5, 100.2, 100.3)]
    t = sim(bars, trig=[1, 3], zone={1: 1, 3: -1})
    # long at bar 2 open (100.1); short signal at bar 3's close -> reversal at bar 4's open 100.3: sell at 100.2
    assert t["r"].size == 2 and t["why"][0] == E.X_REV and t["dir"][0] == 1 and t["dir"][1] == -1
    assert close(t["exit_px"][0], 100.2) and close(t["entry_px"][1], 100.2) and t["why"][1] == E.X_END
    ti = sim(bars, trig=[1, 3], zone={1: 1, 3: -1}, inverted=True)
    assert ti["dir"][0] == -1 and ti["dir"][1] == 1 and close(ti["entry_px"][0], 99.9)


def test_time_stop_wait_and_vol_exit():
    flat = [(100, 100.4, 99.8, 100)] * 12
    t = sim(flat, trig=[1], zone={1: 1}, max_bars=3)
    # filled at bar 2; at the close of bar 5 (5 - 2 >= 3) the close is ordered; it fills at bar 6's open
    assert t["why"][0] == E.X_TIME and t["exit_t"][0] == 6 * 60_000 and close(t["exit_px"][0], 99.9)
    t = sim(flat, trig=[1, 2, 3, 6], zone={1: 1, 2: -1, 3: -1, 6: -1}, wait=3)
    # signals at bars 2 and 3 are inside the wait (bar - 1 <= 3); the one at bar 6 reverses
    assert t["r"].size == 2 and t["why"][0] == E.X_REV and t["exit_t"][0] == 7 * 60_000
    t = sim(flat, trig=[1], zone={1: 1}, volc=[4], use_vol_exit=True)
    assert t["why"][0] == E.X_VOL and t["exit_t"][0] == 5 * 60_000


def test_same_side_signal_is_ignored_and_fee():
    flat = [(100, 100.4, 99.8, 100)] * 8
    t = sim(flat, trig=[1, 3], zone={1: 1, 3: 1}, fee=0.001)
    assert t["r"].size == 1 and t["why"][0] == E.X_END
    # entry 100.1, marked at the last close 100: -0.1 less 0.1 % of (100.1 + 100)
    assert close(t["r"][0], (100 - 100.1 - 0.001 * 200.1) / 2.0)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("all order scenarios pass")
