"""What TradingView's Strategy Tester will show differently from a calibrated file's trade list,
without the file being wrong. Nothing here runs on TradingView: both effects are simulated
with the Python copy.

usage: python tester_view.py [results_dir]

1. Exits on chart candles. The tester (Bar detalization on its default) knows only each chart
   candle's open, high, low and close and assumes open -> nearer extreme -> other extreme ->
   close; the trade lists follow stops and targets second by second. Every trade of a
   calibrated file whose exit differs between the two walks is listed.

2. Limited history. A chart loads 5,000 to 40,000 candles depending on the plan, and a request
   for a lower timeframe about 100,000. A file whose AMVI reads the chart's own or a lower
   timeframe then starts without the history the trade list had: the AMVI has no value for
   its first 400 or so candles, and the entries around the start differ. Simulated: the AMVI
   trigger from the limited history; candles, exit ATR and the filter zone from the full
   history (the filter's daily candles have years of history on TradingView). Files whose
   AMVI reads higher timeframes are not simulated: how much history TradingView gives those
   requests was not checked.
"""
import csv
import json
import os
import sys

import numpy as np
import pandas as pd

import amvi_engine as E
import bars
import final_eval as F
import make_pine
import report
import space
import sweep

REASON = {E.X_STOP: "stop", E.X_TP: "target", E.X_TRAIL: "trail", E.X_REV: "reversal", E.X_VOL: "vol exit", E.X_TIME: "time stop", E.X_END: "open"}
CHART_CANDLES = (5000, 10000, 20000, 40000)      # what a chart holds, by plan
LOWER_TF_CANDLES = 100_000                       # what a request for a lower timeframe holds
LATER_DAYS = (0, 7, 14, 21)                      # a check made that many days after the record date


def when(ms_, fmt="%Y-%m-%d %H:%M"):
    return pd.Timestamp(int(ms_), unit="ms").strftime(fmt)


def exits_on_chart_candles(name, tf, ep, ctx, start, end, label):
    ft = ctx[0]
    a = E.run(ft, tf, ep, fee=0.0, slip_ticks=1, start_ms=sweep.ms(start), end_ms=sweep.ms(end), walk="fine")
    b = E.run(ft, tf, ep, fee=0.0, slip_ticks=1, start_ms=sweep.ms(start), end_ms=sweep.ms(end), walk="chart")
    keep_a, keep_b = a["entry_t"] >= sweep.ms(start), b["entry_t"] >= sweep.ms(start)
    A = {int(t): i for i, t in enumerate(a["entry_t"]) if keep_a[i]}
    B = {int(t): i for i, t in enumerate(b["entry_t"]) if keep_b[i]}
    tf_ms = tf * bars.MIN_MS
    diff = []
    for t in sorted(set(A) | set(B)):
        if t not in A:
            diff.append(f"      entry {when(t)}: only on chart candles")
        elif t not in B:
            diff.append(f"      entry {when(t)}: only second by second")
        else:
            i, j = A[t], B[t]
            same_candle = int(a["exit_t"][i]) // tf_ms == int(b["exit_t"][j]) // tf_ms
            if a["why"][i] != b["why"][j] or not same_candle or abs(a["exit_px"][i] - b["exit_px"][j]) > 0.11:
                side = "long" if a["dir"][i] > 0 else "short"
                diff.append(f"      {side} entered {when(t)}: second by second {REASON[int(a['why'][i])]} at {a['exit_px'][i]:.1f} "
                            f"({when(a['exit_t'][i], '%Y-%m-%d %H:%M:%S')}, {a['r'][i]:+.3f}R before costs); on chart candles "
                            f"{REASON[int(b['why'][j])]} at {b['exit_px'][j]:.1f} (candle {when(int(b['exit_t'][j]) // tf_ms * tf_ms)}, {b['r'][j]:+.3f}R)")
    print(f"   {label} ({start} to {end}): {len(A)} trades second by second ({a['r'][keep_a].sum():+.2f}R before costs), {len(B)} on chart candles "
          f"({b['r'][keep_b].sum():+.2f}R); trades that differ: {len(diff)}")
    for d in diff:
        print(d)


def limited_history(name, tf, ep, ctx, listed):
    """listed: {entry time in ms: side} of the file's trade list (search window)."""
    ft = ctx[0]
    amvi_tf = sorted(ep["tfs"])
    if any(t > tf for t in amvi_tf):
        print(f"   limited history: the AMVI of this file reads {', '.join(make_pine.TF_NAME[t] for t in amvi_tf)} candles from a {name} chart "
              f"(higher timeframes); not simulated.")
        return
    low = min(amvi_tf)
    ch = ft.mk.tf(tf)
    trig, volc, _ = E.trigger_arrays(ft, tf, ep)
    zone = E.zone_array(ft, tf, ep)
    end = sweep.ms(F.SEARCH[1])
    full = E.run(ft, tf, ep, fee=0.0, slip_ticks=1, start_ms=sweep.ms(F.SEARCH[0]), end_ms=end, signals=(trig, volc, zone), walk="fine")
    fe = {int(t) for t in full["entry_t"] if t >= sweep.ms(F.SEARCH[0])}
    print(f"   limited history: the full-history run gives the list's {len(listed)} search-window entries: {fe == set(listed)}")
    sizes = CHART_CANDLES if low == tf else (LOWER_TF_CANDLES,)
    now0 = pd.Timestamp(report.RECORD_DATE)
    for n in sizes:
        for d in LATER_DAYS:
            now = now0 + pd.Timedelta(days=d)
            s = now - pd.Timedelta(minutes=low * n)
            s_ms = int(s.value // 10 ** 6)
            sub = bars.load_1m("BTCUSDT", start=s.strftime("%Y-%m-%d %H:%M"), end=F.SEARCH[1])
            ft2 = E.Features(bars.Market(sub))
            ch2 = ft2.mk.tf(tf)
            t2, v2, _ = E.trigger_arrays(ft2, tf, ep)
            j0 = int(np.searchsorted(ch.t, ch2.t[0]))
            assert np.array_equal(ch.t[j0:], ch2.t)
            tt = np.zeros(len(ch), np.bool_)
            vv = np.zeros(len(ch), np.bool_)
            tt[j0:], vv[j0:] = t2, v2
            first_value = np.nonzero(~np.isnan(ft2.amvi(low, ep)))[0]
            tv = E.run(ft, tf, ep, fee=0.0, slip_ticks=1, start_ms=int(ch.t[j0]), end_ms=end, signals=(tt, vv, zone), walk="fine")
            te = {int(t): int(x) for t, x in zip(tv["entry_t"], tv["dir"]) if t >= ch.t[j0]}
            le = {t: x for t, x in listed.items() if t >= s_ms}
            only_list = sorted(set(le) - set(te))
            only_tv = sorted(set(te) - set(le))
            other_side = sorted(t for t in set(le) & set(te) if le[t] != te[t])
            bad = only_list + only_tv + other_side
            last = max(bad) if bad else None
            comparable = sum(1 for t in le if last is None or t > last)
            what = f"{n:,} {make_pine.TF_NAME[low]} candles"
            print(f"      {what}, checked {(now).strftime('%Y-%m-%d')}: history from {when(s_ms)}; the AMVI has its first value "
                  f"{int(first_value[0]) if first_value.size else -1} candles later; list entries from there {len(le)}; missing in the tester "
                  f"{len(only_list)} ({', '.join(when(t) for t in only_list) or '-'}); in the tester only {len(only_tv)} "
                  f"({', '.join(when(t) for t in only_tv) or '-'}); other side {len(other_side)}; last difference "
                  + (f"{(last - s_ms) / 86_400_000:.1f} days after the start" if last else "none")
                  + f"; list entries after it {comparable}")


def run(res_dir):
    cs, cp = F.contexts()
    for tf in space.CHART_TFS:
        path = os.path.join(res_dir, f"final_{tf}m.json")
        if not os.path.exists(path):
            continue
        fin = json.load(open(path))
        if fin["verdict"] not in report.WITH_FILE:
            continue
        name = make_pine.TF_NAME[tf]
        p = fin["setting"]
        ep = E.P(**space.engine_params(p))
        print(f"{name} file ({fin['verdict']})")
        exits_on_chart_candles(name, tf, ep, cs, F.SEARCH[0], F.SEARCH[1], "exits, search window")
        exits_on_chart_candles(name, tf, ep, cp, fin["eval"].get("pre_from", F.PRESAMPLE[0]), F.PRESAMPLE[1], "exits, untouched period")
        rows = list(csv.DictReader(open(os.path.join(res_dir, f"trades_BTCUSDT_{name}.csv"))))
        listed = {sweep.ms(r["entry_utc"]): (1 if r["side"] == "long" else -1) for r in rows if r["period"] == "search"}
        limited_history(name, tf, ep, cs, listed)
        print(flush=True)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
