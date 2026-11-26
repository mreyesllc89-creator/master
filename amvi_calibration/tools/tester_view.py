"""What TradingView's Strategy Tester will show differently from a calibrated file's trade list,
without the file being wrong. Nothing here runs on TradingView: both effects are simulated
with the Python copy.

usage: python tester_view.py [results_dir]

1. Exits on chart candles. The tester (Bar detalization on its default) knows only each chart
   candle's open, high, low and close and assumes open -> nearer extreme -> other extreme ->
   close; the trade lists follow stops and targets second by second. Every trade of a
   calibrated file whose exit differs between the two walks is listed.

2. Limited history. A chart loads 5,000 to 40,000 candles depending on the plan, and a request
   for a lower timeframe about 100,000. The script then starts without the history the trade
   list had, and the entries around the start differ. How far back TradingView loads a
   request for a higher timeframe (the filter; an AMVI above the chart) was not checked, so
   two models are simulated (scenario()): B1, those requests have their full history; B2,
   they start on the chart's first day. In both, an AMVI on the chart's own timeframe starts
   at the chart's first candle, one below the chart not before the oldest lower-timeframe
   candle TradingView keeps, and the strategy is flat at the chart's first candle. The
   differences are counted from the later of the chart's first candle, the start of the
   search window and the AMVI's first candle.
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


def floor_day(ms_):
    return ms_ // 86_400_000 * 86_400_000


def features_from(start_ms):
    """Features over 1-minute bars from start_ms to the end of the search window (no seconds)."""
    sub = bars.load_1m("BTCUSDT", start=pd.Timestamp(int(start_ms), unit="ms").strftime("%Y-%m-%d %H:%M"), end=F.SEARCH[1])
    return E.Features(bars.Market(sub))


def aligned(ch, ch_part, arr_part):
    """Arrays of a shorter history put into the positions of the longer one (False before)."""
    j0 = int(np.searchsorted(ch.t, ch_part.t[0]))
    if j0 + len(ch_part) != len(ch) or not np.array_equal(ch.t[j0:], ch_part.t):
        raise ValueError("candles do not line up")
    out = np.zeros(len(ch), np.bool_)
    out[j0:] = arr_part
    return out


def scenario(tf, ep, ft_full, listed, s_ms, now_ms, model):
    """The entries the tester takes on a chart whose first candle opens at s_ms, against the list.

    model "B1": the filter and an AMVI above the chart have their full history (as with Deep
                Backtesting, or if TradingView loads those requests further back than the chart);
    model "B2": every request starts on the chart's first day (nothing before the chart).
    An AMVI on the chart's own timeframe starts at the chart's first candle in both models, one
    below the chart not before the oldest of the LOWER_TF_CANDLES candles TradingView keeps.
    The strategy is flat at the chart's first candle. Returns a dict, or a string saying why
    the case was not simulated."""
    amvi_tf = sorted(ep["tfs"])
    end = sweep.ms(F.SEARCH[1])
    data0 = int(ft_full.mk.m1.t[0])
    if any(t > tf for t in amvi_tf) and any(t <= tf for t in amvi_tf):
        return "AMVI timeframes on both sides of the chart: not simulated"
    low = min(amvi_tf)
    limit = now_ms - low * LOWER_TF_CANDLES * bars.MIN_MS if low < tf else None
    amvi_start = None if low > tf else max(s_ms, limit or s_ms)
    if model == "B1":
        # the full history is the trade list's own (loaded from sweep.LOAD_START)
        if s_ms < data0:
            return "chart starts before the loaded data: not simulated"
        ft_run = ft_full
        zone = E.zone_array(ft_full, tf, ep)
    else:
        day0 = floor_day(s_ms)
        if day0 < sweep.ms(F.PRE_LOAD):
            return "chart starts before the data: not simulated"
        ft_run = features_from(day0)
        zone = E.zone_array(ft_run, tf, ep)
    ch = ft_run.mk.tf(tf)
    if amvi_start is None and model == "B1":
        trig, volc, _ = E.trigger_arrays(ft_full, tf, ep)
    elif amvi_start is None:
        trig, volc, _ = E.trigger_arrays(ft_run, tf, ep)
    else:
        ft_a = features_from(amvi_start)
        t2, v2, _ = E.trigger_arrays(ft_a, tf, ep)
        ch_a = ft_a.mk.tf(tf)
        trig, volc = aligned(ch, ch_a, t2), aligned(ch, ch_a, v2)
    j0 = int(np.searchsorted(ch.t, s_ms))
    tv = E.run(ft_run, tf, ep, fee=0.0, slip_ticks=1, start_ms=int(ch.t[j0]), end_ms=end, signals=(trig, volc, zone), walk="1m")
    cmp_from = max(s_ms, sweep.ms(F.SEARCH[0]), amvi_start or s_ms)
    te = {int(t): int(x) for t, x in zip(tv["entry_t"], tv["dir"]) if t >= cmp_from}
    le = {t: x for t, x in listed.items() if t >= cmp_from}
    only_list = sorted(set(le) - set(te))
    only_tv = sorted(set(te) - set(le))
    other_side = sorted(t for t in set(le) & set(te) if le[t] != te[t])
    bad = only_list + only_tv + other_side
    last = max(bad) if bad else None
    return dict(cmp_from=cmp_from, n_list=len(le), only_list=only_list, only_tv=only_tv, other_side=other_side,
                last_days=(last - cmp_from) / 86_400_000 if last else None, after=sum(1 for t in le if last is None or t > last))


def limited_history(name, tf, ep, ft_full, listed, hold_max_days):
    """An ordinary chart holds 5,000 to 40,000 candles depending on the plan: the script then
    starts without the history the trade list had. Both models of scenario(), for every chart
    size whose first candle lies inside the search window, checked on the record date and up
    to three weeks later."""
    now0 = pd.Timestamp(report.RECORD_DATE)
    print(f"   limited history (an ordinary chart, strategy flat at its first candle; longest trade of the list {hold_max_days:.1f} days):")
    worst = {"B1": 0.0, "B2": 0.0}
    for n in CHART_CANDLES:
        s0 = now0 - pd.Timedelta(minutes=tf * n)
        in_range = sum(1 for t in listed if t >= int(s0.value // 10 ** 6))
        print(f"      {n:,} {name} candles reach back to {s0.strftime('%Y-%m-%d %H:%M')} on {report.RECORD_DATE}: {in_range} list entries after that")
        if in_range < 3:
            print("         too few to compare: not simulated")
            continue
        for d in LATER_DAYS:
            now = now0 + pd.Timedelta(days=d)
            s_ms = int((now - pd.Timedelta(minutes=tf * n)).value // 10 ** 6)
            for model in ("B1", "B2"):
                r = scenario(tf, ep, ft_full, listed, s_ms, int(now.value // 10 ** 6), model)
                if isinstance(r, str):
                    print(f"         {model}, checked {now.strftime('%Y-%m-%d')}: {r}")
                    continue
                if r["last_days"] is not None:
                    worst[model] = max(worst[model], r["last_days"])
                print(f"         {model}, checked {now.strftime('%Y-%m-%d')}, first candle {when(s_ms)}, compared from {when(r['cmp_from'])}: list entries {r['n_list']}; "
                      f"missing in the tester {len(r['only_list'])} ({', '.join(when(t) for t in r['only_list']) or '-'}); in the tester only "
                      f"{len(r['only_tv'])} ({', '.join(when(t) for t in r['only_tv']) or '-'}); other side {len(r['other_side'])}; last difference "
                      + (f"{r['last_days']:.1f} days after the comparison start" if r["last_days"] is not None else "none")
                      + f"; list entries after it {r['after']}", flush=True)
    print(f"   latest difference after the comparison start: B1 {worst['B1']:.1f} days, B2 {worst['B2']:.1f} days")
    return worst


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
        hold = max((sweep.ms(r["exit_utc"]) - sweep.ms(r["entry_utc"])) / 86_400_000 for r in rows)
        limited_history(name, tf, ep, cs[0], listed, hold)
        print(flush=True)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
