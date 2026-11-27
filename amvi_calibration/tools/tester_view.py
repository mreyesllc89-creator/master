"""What TradingView's Strategy Tester will show differently from a calibrated file's trade list,
without the file being wrong. Nothing here runs on TradingView: every effect is simulated with
the Python copy.

usage: python tester_view.py [results_dir]

1. Exits on chart candles. The tester (Bar detalization on its default) knows only each chart
   candle's open, high, low and close and assumes open -> nearer extreme -> other extreme ->
   close; the trade lists follow stops and targets second by second. Every trade of a
   calibrated file whose exit differs between the two walks is listed.

2. Deep Backtesting. The tester computes the script over the period chosen in the Strategy
   Tester; the script's "Limit Backtest Date Range" only blocks entries outside its dates.
   Simulated: every request starts on the period's first day (the cautious case), entries from
   the range's start, against the list: with the period starting six months before the range,
   and with both starting on the same day.

3. An ordinary chart. A chart loads 5,000 to 40,000 candles depending on the plan, and a
   request for a lower timeframe about 100,000 candles (200,000 on Ultimate; not simulated).
   The script then starts without the history the trade list had. How far back TradingView
   loads a request for a higher timeframe (the filter; an AMVI above the chart) was not
   checked, so two models are simulated (simulate()): B1, those requests have their full
   history; B2, they start on the chart's first day. In both, an AMVI on the chart's own
   timeframe starts at the chart's first candle, one below the chart not before the oldest
   lower-timeframe candle TradingView keeps, and the strategy is flat at the chart's first
   candle. Checks are scanned every SCAN_STEP_H hours over SCAN_DAYS days from the record
   date, for every plan size that holds at least 3 list trades. A difference is counted from
   the later of the chart's first candle, the start of the search window and the AMVI's first
   candle.
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
CHART_CANDLES = {5000: "Basic", 10000: "Essential, Plus", 20000: "Premium", 25000: "Expert", 40000: "Ultimate"}   # what a chart holds, by plan
LOWER_TF_CANDLES = 100_000                       # what a request for a lower timeframe holds (plans up to Premium)
SCAN_DAYS, SCAN_STEP_H = 35, 12                  # checks made over the five weeks after the record date
DEEP = {"search": ("2023-05-01", F.SEARCH), "untouched": ("2020-07-01", F.PRESAMPLE)}   # Deep Backtesting period start, date range
_M1 = {}


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


def m1_all():
    if "m1" not in _M1:
        _M1["m1"] = bars.load_1m("BTCUSDT", start=F.PRE_LOAD, end=F.SEARCH[1])
    return _M1["m1"]


def features_from(start_ms):
    """Features over the 1-minute bars from start_ms to the end of the search window (no seconds)."""
    m = m1_all()
    k = int(np.searchsorted(m.t, int(start_ms)))
    idx = np.arange(m.t.size - k, dtype=np.int64)
    return E.Features(bars.Market(bars.Bars(1, m.t[k:], m.o[k:], m.h[k:], m.l[k:], m.c[k:], m.v[k:], idx, idx + 1)))


def aligned(ch, ch_part, arr_part):
    """Arrays of a shorter history put into the positions of the longer one (False before)."""
    j0 = int(np.searchsorted(ch.t, ch_part.t[0]))
    if j0 + len(ch_part) != len(ch) or not np.array_equal(ch.t[j0:], ch_part.t):
        raise ValueError("candles do not line up")
    out = np.zeros(len(ch), np.bool_)
    out[j0:] = arr_part
    return out


def simulate(tf, ep, listed, first_ms, now_ms, model, full=None, run_from=None, end_ms=None):
    """The entries the tester takes when its data starts at first_ms, against the list.

    model "B1": the filter and an AMVI above the chart have the trade list's own history
                (full = (features, zone) of the list's context);
    model "B2": every request starts on the first day of the tester's data.
    An AMVI on the chart's own timeframe starts at first_ms, one below the chart not before
    now_ms minus LOWER_TF_CANDLES of its candles. Entries from run_from (the date range's start;
    default first_ms), flat there, up to end_ms. Returns a dict, or a string saying why the
    case was not simulated."""
    date_range = run_from is not None
    amvi_tf = sorted(ep["tfs"])
    end_ms = end_ms or sweep.ms(F.SEARCH[1])
    run_from = run_from or first_ms
    if any(t > tf for t in amvi_tf) and any(t <= tf for t in amvi_tf):
        return "AMVI timeframes on both sides of the chart: not simulated"
    low = min(amvi_tf)
    limit = now_ms - low * LOWER_TF_CANDLES * bars.MIN_MS if low < tf else None
    amvi_start = None if low > tf else max(first_ms, limit or first_ms)
    if max(run_from, amvi_start or run_from) >= max(listed, default=0):
        return "no list trade after the start: nothing to compare"
    if model == "B1":
        ft_run, zone = full
        if first_ms < int(ft_run.mk.m1.t[0]):
            return "starts before the list's own history: not simulated"
    else:
        day0 = floor_day(first_ms)
        if day0 < sweep.ms(F.PRE_LOAD):
            return "starts before the data: not simulated"
        ft_run = features_from(day0)
        zone = E.zone_array(ft_run, tf, ep)
    ch = ft_run.mk.tf(tf)
    if amvi_start is None:
        trig, volc, _ = E.trigger_arrays(ft_run, tf, ep)
    else:
        ft_a = features_from(amvi_start)
        t2, v2, _ = E.trigger_arrays(ft_a, tf, ep)
        ch_a = ft_a.mk.tf(tf)
        trig, volc = aligned(ch, ch_a, t2), aligned(ch, ch_a, v2)
    j0 = int(np.searchsorted(ch.t, run_from))
    tv = E.run(ft_run, tf, ep, fee=0.0, slip_ticks=1, start_ms=int(ch.t[j0]), end_ms=end_ms, signals=(trig, volc, zone), walk="1m")
    cmp_from = max(run_from, amvi_start or run_from)
    if not date_range:
        cmp_from = max(cmp_from, sweep.ms(F.SEARCH[0]))    # an ordinary chart: the list starts with the search window
    te = {int(t): int(x) for t, x in zip(tv["entry_t"], tv["dir"]) if cmp_from <= t < end_ms}
    le = {t: x for t, x in listed.items() if cmp_from <= t < end_ms}
    only_list = sorted(set(le) - set(te))
    only_tv = sorted(set(te) - set(le))
    other_side = sorted(t for t in set(le) & set(te) if le[t] != te[t])
    bad = only_list + only_tv + other_side
    last = max(bad) if bad else None
    return dict(cmp_from=cmp_from, n_list=len(le), only_list=only_list, only_tv=only_tv, other_side=other_side,
                last_days=(last - cmp_from) / 86_400_000 if last else None, after=sum(1 for t in le if last is None or t > last))


def line(r):
    return (f"list trades {r['n_list']}; missing in the tester {len(r['only_list'])} ({', '.join(when(t) for t in r['only_list'][:6]) or '-'}"
            + (", ..." if len(r["only_list"]) > 6 else "") + f"); in the tester only {len(r['only_tv'])} ({', '.join(when(t) for t in r['only_tv'][:6]) or '-'}); "
            f"other side {len(r['other_side'])}; last difference "
            + (f"{r['last_days']:.1f} days after {when(r['cmp_from'])}" if r["last_days"] is not None else "none") + f"; list trades after it {r['after']}")


def deep_backtesting(name, tf, ep, listed_by_period):
    """The Deep Backtesting check: the period starting six months before the date range, and
    starting on the range's first day; every request from the period's start (model B2)."""
    now_ms = sweep.ms(report.RECORD_DATE)
    print(f"   Deep Backtesting, every request from the start of the tester's period, entries from the date range's start, checked {report.RECORD_DATE}:")
    for period, (lead, (r0, r1)) in DEEP.items():
        listed = listed_by_period.get(period)
        if not listed:
            continue
        lead_ms, r0_ms, r1_ms = sweep.ms(lead), sweep.ms(r0), sweep.ms(r1)
        if lead_ms < now_ms - 2_000_000 * tf * bars.MIN_MS:
            print(f"      {period} list: two million {name} candles do not reach back to {lead}: not possible")
            continue
        low = min(ep["tfs"])
        if low < tf and now_ms - low * LOWER_TF_CANDLES * bars.MIN_MS >= r1_ms:
            print(f"      {period} list: the tester keeps no {make_pine.TF_NAME[low]} candles from before {r1}: not possible")
            continue
        for first in (lead_ms, r0_ms):
            r = simulate(tf, ep, listed, first, now_ms, "B2", run_from=r0_ms, end_ms=r1_ms)
            what = f"period from {when(first)[:10]}, date range {r0} to {r1}"
            print(f"      {period} list, {what}: " + (r if isinstance(r, str) else line(r)), flush=True)


def ordinary_chart(name, tf, ep, listed, full):
    """Ordinary charts of every plan size, checks every SCAN_STEP_H hours over SCAN_DAYS days."""
    now0 = sweep.ms(report.RECORD_DATE)
    steps = range(0, SCAN_DAYS * 24 // SCAN_STEP_H + 1)
    print(f"   ordinary chart, strategy flat at the chart's first candle, checks every {SCAN_STEP_H} hours from {report.RECORD_DATE} for {SCAN_DAYS} days:")
    summary = {}
    for n, plan in CHART_CANDLES.items():
        s0 = now0 - n * tf * bars.MIN_MS
        in_range = sum(1 for t in listed if t >= s0)
        print(f"      {n:,} {name} candles ({plan}) reach back to {when(s0)} on {report.RECORD_DATE}: {in_range} list trades after that", flush=True)
        if in_range < 3:
            continue
        if s0 < int(full[0].mk.m1.t[0]):
            print("         further back than the list's own history: as with Deep Backtesting above")
            continue
        for model in ("B1", "B2"):
            res, empty, why = [], 0, ""
            for k in steps:
                now_ms = now0 + k * SCAN_STEP_H * 3_600_000
                r = simulate(tf, ep, listed, now_ms - n * tf * bars.MIN_MS, now_ms, model, full=full)
                if isinstance(r, str):
                    empty, why = empty + 1, r
                    continue
                res.append((now_ms, r))
            if not res:
                print(f"         {model}: {why}")
                continue
            lasts = [r["last_days"] or 0.0 for _, r in res]
            worst = sorted(res, key=lambda x: -(x[1]["last_days"] or 0.0))[:3]
            summary[(n, model)] = max(lasts)
            print(f"         {model}: {len(res)} checks" + (f" ({empty} more with no list trade left)" if empty else "") + "; last difference later than 7 / 14 / 21 / 28 / 42 days: "
                  f"{sum(x > 7 for x in lasts)} / {sum(x > 14 for x in lasts)} / {sum(x > 21 for x in lasts)} / {sum(x > 28 for x in lasts)} / "
                  f"{sum(x > 42 for x in lasts)}; latest {max(lasts):.1f} days; checks with a trade only in the tester "
                  f"{sum(1 for _, r in res if r['only_tv'])}, with a trade on the other side {sum(1 for _, r in res if r['other_side'])}")
            for now_ms, r in worst:
                if r["last_days"]:
                    print(f"            checked {when(now_ms)}: {line(r)}")
    return summary


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
        listed = {per: {sweep.ms(r["entry_utc"]): (1 if r["side"] == "long" else -1) for r in rows if r["period"] == per} for per in ("search", "untouched")}
        hold = max((sweep.ms(r["exit_utc"]) - sweep.ms(r["entry_utc"])) / 86_400_000 for r in rows)
        print(f"   longest trade of the list: {hold:.1f} days")
        deep_backtesting(name, tf, ep, listed)
        ft_full = cs[0]
        ordinary_chart(name, tf, ep, listed["search"], (ft_full, E.zone_array(ft_full, tf, ep)))
        print(flush=True)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
