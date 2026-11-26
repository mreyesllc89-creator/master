"""How completely the one-second bars cover the 1-minute bars.

usage: python seconds_coverage.py [symbol]

Per period: the minutes with a trade; the empty rows of the 1-minute file, which are not bars
here, and in how many of them the trade-by-trade files do show a trade; the minutes that have
their seconds; the minutes whose seconds contradict the minute's bar (refused: the 1-minute bar
is used there); the minutes whose bar opens at the previous close instead of the first trade;
and the number of one-second bars.
"""
import sys

import numpy as np

import bars

PERIODS = (("2021-01-01", "2022-01-01"), ("2022-01-01", "2023-01-01"), ("2023-01-01", "2023-11-01"),
           ("2023-11-01", "2025-01-01"), ("2025-01-01", "2026-01-01"), ("2026-01-01", "2026-11-01"))


def one(symbol, start, end):
    every = bars.load_1m(symbol, start=start, end=end, drop_empty=False)
    m1 = bars.load_1m(symbol, start=start, end=end)
    sec = bars.load_1s(symbol, start=start, end=end)
    if sec is None:
        raise SystemExit(f"no one-second files for {start} to {end}: run fetch_1s.py first")
    bars.attach_seconds(m1, sec)
    t0 = every.t[every.v <= 0] // 1000                 # the empty rows, epoch seconds
    a = np.searchsorted(sec.sec, t0, side="left")
    b = np.searchsorted(sec.sec, t0 + 60, side="left")
    return dict(minutes=len(m1), empty=int(t0.size), empty_traded=int((b > a).sum()), covered=int(sec.covered),
                refused=int(sec.refused), open_differs=int(sec.open_differs), seconds=len(sec))


def line(name, d):
    return (f"{name}: {d['minutes']:,} minutes with a trade ({d['empty']:,} empty rows of the 1-minute file left out; "
            f"the trade files show a trade in {d['empty_traded']:,} of them), {d['covered']:,} with their seconds "
            f"({d['covered'] / d['minutes'] * 100:.3f}%), {d['refused']:,} refused, {d['open_differs']:,} open at the previous close "
            f"({d['open_differs'] / d['minutes'] * 100:.1f}%), {d['seconds']:,} seconds")


def main():
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    print("One-second bars built from Binance aggTrades, attached to the 1-minute bars (bars.attach_seconds)")
    total = {}
    for start, end in PERIODS:
        d = one(symbol, start, end)
        print(line(f"{start} to {end}", d), flush=True)
        for k, v in d.items():
            total[k] = total.get(k, 0) + v
    print(line("total", total))


if __name__ == "__main__":
    main()
