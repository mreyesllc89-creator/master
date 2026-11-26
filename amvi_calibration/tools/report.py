"""Final step: evaluate the pick of every chart timeframe, give it a verdict, write the
calibrated .pine file, the trade list and REPORT_tables.md (the tables of REPORT.md).

usage: python report.py [results_dir]

The verdict rules (fixed before the final sweeps were run; the last two conditions of
RECOMMENDED and the trailing-stop condition were added after the code review, also before
the final run):

  RECOMMENDED      all four hold-out tests pass (first half -> second, second -> first,
                   walk-forward, search window -> untouched period); the pick sits on a plateau
                   (>= 60 % of its one-step neighbours positive in both halves); it is positive
                   on the untouched 2021-01..2023-10 period at base AND stressed costs with at
                   least 50 trades; weeks resampled positive >= 95 % on the search window AND
                   on the untouched period
  USABLE           plateau, untouched period positive at base and stressed costs with at least
                   50 trades, weeks >= 95 % on the search window, and at least one of the four
                   hold-out tests passes
  PAPER-TRADE      plateau and untouched period positive at base costs, but the hold-out tests
                   fail or the sample is thin: it may be luck, watch it before risking money
  NOT RECOMMENDED  positive in both halves of the search window, but negative on the untouched
                   period or not on a plateau
  DO NOT TRADE     no setting is positive in both halves at base and stressed costs

A pick that uses the trailing stop can only be RECOMMENDED or USABLE if it is also positive
on both periods when the trailing stop starts again at every candle close (how TradingView
treats a re-sent exit order could not be checked from here).
"""
import csv
import json
import os
import re
import sys

import numpy as np
import pandas as pd

import amvi_engine as E
import final_eval as F
import make_pine
import space
import sweep

RISK_PCT = 0.5      # the owner's lab rule: at most 0.5 % of equity per trade
SYMBOL = "BTCUSDT.P"
ORDER = ["RECOMMENDED", "USABLE", "PAPER-TRADE", "NOT RECOMMENDED", "DO NOT TRADE"]
WINDOW_TXT = "2023-11 to 2026-10"


def trail_robust(p, ev):
    """A trailing pick must not depend on the trailing state surviving the candle close."""
    if not p.get("trail"):
        return True
    return ev.get("trail_restart", {}).get("total", 0) > 0 and ev.get("pre_trail_restart", {}).get("total", 0) > 0


def verdict(hold, plat, ev, unt=None, p=None):
    if plat is None:
        return "DO NOT TRADE", "no setting is positive in both halves of the search window at base and stressed costs"
    pre, pres = ev.get("pre", {}), ev.get("pre_stress", {})
    plateau = plat["share_both_positive"] >= 0.6
    u = pre.get("n", 0) > 0 and pre.get("total", 0) > 0
    u50 = u and pre.get("n", 0) >= 50
    us = pres.get("total", 0) > 0
    weeks = ev["base"].get("weeks_pos", 0) >= 0.95
    uweeks = pre.get("weeks_pos", 0) >= 0.95
    t1, t2, wf = hold["pass_h1_to_h2"], hold["pass_h2_to_h1"], hold["pass_walk_forward"]
    tu = bool(unt and unt.get("passed"))
    tr = trail_robust(p or {}, ev)
    if t1 and t2 and wf and tu and plateau and u50 and us and weeks and uweeks and tr:
        return "RECOMMENDED", "passes every hold-out test and the untouched period"
    if plateau and u50 and us and weeks and (t1 or t2 or wf or tu) and tr:
        return "USABLE", "positive on the untouched period and on a plateau; only part of the hold-out tests pass"
    if plateau and u:
        why = []
        if not (t1 or t2 or wf or tu):
            why.append("the best settings of one period did not carry to another")
        if not u50:
            why.append(f"only {pre.get('n', 0)} trades on the untouched period")
        if not us:
            why.append("negative on the untouched period at stressed costs")
        if not weeks:
            why.append("the result leans on few weeks")
        if not tr:
            why.append("it depends on how TradingView handles the trailing stop at candle closes")
        return "PAPER-TRADE", "positive on the untouched period, but " + "; ".join(why)
    if not u:
        return "NOT RECOMMENDED", "positive in both halves of the search window but not on the untouched 2021-2023 period"
    return "NOT RECOMMENDED", "positive in both halves but not on a plateau: neighbouring settings lose"


def titles(src):
    """input variable -> the label TradingView shows."""
    out = {}
    for m in re.finditer(r"^(\w+)\s*=\s*input\.\w+\((?:\"[^\"]*\"|[^,]+),\s*\"([^\"]*)\"", src, re.M):
        out[m.group(1)] = m.group(2)
    return out


def pct(r):
    return r * RISK_PCT


def wrap(text, width=84, indent="   ", first=" -"):
    """Wrap a header paragraph: first line starts with ' - ', the others with the indent."""
    words, lines, cur = text.split(), [], first
    for w in words:
        if len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = indent + w
        else:
            cur += " " + w
    lines.append(cur)
    return lines


def header_lines(tf, v, why, ev, hold, plat, unt, changes, p):
    b, pre = ev["base"], ev.get("pre", {})
    name = make_pine.TF_NAME[tf]
    L = [f"AMVI Full MTF Strategy (direction filter, closed-candle engine): {SYMBOL} {name}"]
    L += wrap(f"{v} - {why}.", indent="        ", first="STATUS:")
    L += ["-" * 85,
         "Same code as AMVI_FGF_Inverted_XAUUSD_15m.pine; only the title, the commission and the",
         "input defaults listed at the end of this record differ. Record date 2026-11-26.",
         "Numbers come from a Python copy of this script (amvi_calibration/tools), not from",
         "TradingView: check them against the Strategy Tester before relying on them.",
         ""]
    L += wrap(f"Data: Binance BTCUSDT perpetual; chart {name}; stops, targets and trailing stops filled on the "
              f"second-by-second trade prices. Search window 2023-11-01 to 2026-10-31. Costs: 0.05% per side + 1 tick "
              f"slippage + funding. R = the amount risked per trade (Stop Loss x ATR{p['exit_atr']}); with the file's "
              f"Risk {RISK_PCT}% sizing 1R = {RISK_PCT}% of equity.")
    L += wrap(f"Search window: {b['n']} trades ({b['n_long']}L/{b['n_short']}S), {b['total']:+.1f}R, PF {b['pf']:.2f}, max DD {b['dd']:.1f}R, "
              f"halves {b['h1']:+.1f}R/{b['h2']:+.1f}R, {b['win'] * 100:.0f}% winners, longest losing streak {b['streak']}, "
              f"{b['months_pos']} of {b['months']} months positive, {b.get('avg_bars', 0):.0f} bars per trade on average.")
    L += wrap(f"Costs: Bitget taker 0.06% {ev['bitget']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; stressed (0.10% + 3 ticks) "
              f"{ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side.")
    same_costs = ev["bitget"]["total"] + ev["bitget"]["fund_r"]
    L += wrap(f"TradingView's Strategy Tester walks stops on the chart's candles (no Bar Magnifier) and charges no funding: "
              f"on the same bars it would show about {ev['tv_view']['total']:+.1f}R ({ev['tv_view']['n']} trades) for this file. The same "
              f"costs on second-by-second prices give {same_costs:+.1f}R; any difference is the tester's price path, not profit.")
    if p.get("trail"):
        L += wrap(f"Trailing stop: if TradingView starts it again at every candle close (not checked), the search window "
                  f"gives {ev['trail_restart']['total']:+.1f}R instead of {b['total']:+.1f}R.")
    if pre.get("n"):
        L += wrap(f"Untouched {ev.get('pre_from', '2021-01-01')[:7]} to 2023-10 (never used to choose anything): {pre['n']} trades, {pre['total']:+.1f}R, "
                  f"PF {pre['pf']:.2f}, max DD {pre['dd']:.1f}R, {pre['months_pos']} of {pre['months']} months positive; stressed costs "
                  f"{ev['pre_stress']['total']:+.1f}R.")
    else:
        L += wrap("Untouched 2021-01 to 2023-10 (never used to choose anything): no trades.")
    L += wrap(f"Hold-outs (best 40 settings of one part, scored on the other): first half -> second {fmt_t(hold['h1_to_h2'])}; "
              f"second -> first {fmt_t(hold['h2_to_h1'])}; walk-forward {fmt_t(hold['walk_forward'])}. "
              f"Search window -> untouched period: {fmt_u(unt)}.")
    L += wrap(f"Plateau: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} one-step neighbours are positive in both halves. "
              f"Concentration: the 10 biggest trades give {b['top10']:+.1f}R, the rest {b['without_top10']:+.1f}R; weeks resampled: "
              f"positive in {b['weeks_pos'] * 100:.1f}% of draws. The other trade direction with the same inputs: {ev['other_direction']['total']:+.1f}R.")
    L += wrap("Not simulated: seconds timeframes (all off), the filter's entry hold, liquidation, partial fills, your "
              "exchange's own prices (Binance trades were used).")
    L += ["", "Inputs set in this file (shipped value in brackets):"]
    line = ""
    for nm, old, new in changes:
        item = f"{nm} = {new} [{old}]"
        if len(line) + len(item) + 2 > 84:
            L.append(line.rstrip(", ") + ",")
            line = ""
        line += item + ", "
    if line:
        L.append(line.rstrip(", ") + ".")
    L += ["Seconds timeframes (1s-45s) are off: they cannot be tested on history.",
          "",
          "SIZING (S3): Risk % of equity per trade; this file ships 0.5% and a 20% margin (5x",
          "leverage cap), the limits of your crypto lab. Results in R do not depend on size.",
          "",
          "CLOSED-CANDLE ENGINE: every decision is taken once per candle, at its close, and filled",
          "at the next open; keep Properties -> Script executions on \"On bar close\" only."]
    return L


def fmt_t(t):
    if not t:
        return "not enough rows"
    return f"{t['top_mean']:+.1f}R ({t['top_pos'] * 100:.0f}% positive, months resampled {t['boot_pos'] * 100:.0f}%)"


def fmt_u(u):
    if not u or "cand_mean" not in u:
        return "not tested"
    return (f"the {u['n_candidates']} candidates made {u['cand_mean']:+.1f}R on average ({u['cand_share_positive'] * 100:.0f}% positive), "
            f"random settings {u['random_mean']:+.1f}R ({u['random_share_positive'] * 100:.0f}% positive): {'pass' if u['passed'] else 'fail'}")


def sizing_defaults(src):
    """BTC sizing defaults: the owner's lab limits (0.5 % risk, 5x leverage) and BTC units."""
    rep = [('fixedQtyS3  = input.float(10, "Fixed quantity (contracts = oz, 100 = 1 lot)"', 'fixedQtyS3  = input.float(0.01, "Fixed quantity (BTC)"'),
           ('riskPctS3   = input.float(1.0, "Risk % of equity per trade (Risk mode)"', 'riskPctS3   = input.float(0.5, "Risk % of equity per trade (Risk mode)"'),
           ('maxQtyS3    = input.float(50, "Max quantity"', 'maxQtyS3    = input.float(5, "Max quantity (BTC)"'),
           ('marginPctS3 = input.float(1.0, "Margin % (match Properties -> Margin)"', 'marginPctS3 = input.float(20.0, "Margin % (match Properties -> Margin)"'),
           ("margin_long=1, margin_short=1)", "margin_long=20, margin_short=20)")]
    for a, b in rep:
        assert a in src, a
        src = src.replace(a, b)
    return src


def load_json(path):
    return json.load(open(path)) if os.path.exists(path) else None


def fee_in_r(ft, tf):
    """Median ATR(14) of the chart timeframe as % of price over the search window, and the
    commission of one round trip at 0.05 % per side in R for a 1 x ATR stop."""
    ch = ft.mk.tf(tf)
    a = ft.atr(tf, 14)
    m = (ch.t >= sweep.ms(F.SEARCH[0])) & ~np.isnan(a)
    atr_pct = float(np.median(a[m] / ch.c[m]) * 100)
    return atr_pct, 2 * F.BASE_FEE * 100 / atr_pct


def run(res_dir):
    out_root = os.path.join(res_dir, "..")
    presets = os.path.join(out_root, "presets")
    os.makedirs(presets, exist_ok=True)
    for old in os.listdir(presets):
        if old.endswith(".pine"):
            os.remove(os.path.join(presets, old))
    cs, cp = F.contexts()
    tpl = open(make_pine.TEMPLATE, encoding="utf-8").read()
    ttl = titles(tpl)
    shipped = space.normalize({})
    rows, sections = [], []
    for tf in space.CHART_TFS:
        hold = load_json(os.path.join(res_dir, f"holdout_{tf}m.json"))
        if hold is None:
            continue
        pj = load_json(os.path.join(res_dir, f"plateau_{tf}m.json"))
        picks = pj["picks"] if pj else []
        unt = load_json(os.path.join(res_dir, f"untouched_{tf}m.json"))
        name = make_pine.TF_NAME[tf]
        base_ev = F.evaluate(cs, cp, tf, shipped, light=True)
        for k in ("_trades", "_pre_trades"):
            base_ev.pop(k, None)
        atr_pct, fee_r = fee_in_r(cs[0], tf)
        row = dict(tf=tf, name=name, hold=hold, unt=unt, shipped=base_ev, atr_pct=atr_pct, fee_r=fee_r,
                   trailing=load_json(os.path.join(res_dir, f"trailing_{tf}m.json")),
                   inputs=load_json(os.path.join(res_dir, f"inputs_{tf}m.json")))
        if not picks:
            v, why = verdict(hold, None, None)
            row.update(verdict=v, why=why)
            rows.append(row)
            sections.append(f"### {name}: {v}\n\n{why.capitalize()}. No file was written for this timeframe.\n")
            print(f"{name}: {v} - {why}", flush=True)
            continue
        plat = picks[0]
        p = space.normalize(plat["setting"])
        ev = F.evaluate(cs, cp, tf, p)
        v, why = verdict(hold, plat, ev, unt, p)
        # the calibrated file
        src0, changes = make_pine.build(p, tf, ["x"], "t", "s")
        hl = header_lines(tf, v, why, ev, hold, plat, unt, changes, p)
        tag = "calibrated" if v in ("RECOMMENDED", "USABLE") else ("paper-trade only" if v == "PAPER-TRADE" else "not recommended")
        src, changes = make_pine.build(p, tf, hl, f"AMVI FGF | {SYMBOL} {name} ({tag}, closed-candle)", f"AMVI BTC {name}", commission_pct=0.06, symbol=SYMBOL)
        src = sizing_defaults(src)
        fn = f"AMVI_FGF_BTCUSDT_{name}.pine"
        open(os.path.join(presets, fn), "w", encoding="utf-8").write(src)
        # the trade list
        tr = ev.pop("_trades")
        pre_tr = ev.pop("_pre_trades", None)
        with open(os.path.join(res_dir, f"trades_BTCUSDT_{name}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["period", "entry_utc", "exit_utc", "side", "entry_price", "exit_price", "risk_distance", "gross_R", "fee_R", "funding_R", "net_R", "exit"])
            reason = {E.X_STOP: "stop", E.X_TP: "target", E.X_TRAIL: "trail", E.X_REV: "reversal", E.X_VOL: "vol exit", E.X_TIME: "time stop", E.X_END: "open"}
            for period, t in (("untouched", pre_tr), ("search", tr)):
                if t is None:
                    continue
                for i in range(t["r"].size):
                    w.writerow([period, pd.Timestamp(int(t["entry_t"][i]), unit="ms").strftime("%Y-%m-%d %H:%M:%S"), pd.Timestamp(int(t["exit_t"][i]), unit="ms").strftime("%Y-%m-%d %H:%M:%S"),
                                "long" if t["dir"][i] > 0 else "short", f"{t['entry_px'][i]:.1f}", f"{t['exit_px'][i]:.1f}", f"{t['risk'][i]:.1f}",
                                f"{t['gross'][i]:.3f}", f"{t['fee_r'][i]:.3f}", f"{t['fund_r'][i]:.3f}", f"{t['r'][i]:.3f}", reason[int(t["why"][i])]])
        json.dump(dict(tf=tf, verdict=v, why=why, setting=p, eval=ev, plateau={k: plat[k] for k in plat if k != "setting"}, untouched_check=unt, shipped=base_ev),
                  open(os.path.join(res_dir, f"final_{tf}m.json"), "w"), default=float)
        row.update(verdict=v, why=why, ev=ev, plat=plat, p=p, changes=changes, file=fn)
        rows.append(row)
        sections.append(section(tf, name, v, why, ev, hold, plat, unt, p, changes, ttl, fn))
        print(f"{name}: {v} - {why}", flush=True)
    md = tables(rows) + "\n\n## Settings per timeframe\n\n" + "\n".join(sections)
    open(os.path.join(out_root, "REPORT_tables.md"), "w", encoding="utf-8").write(md)
    json.dump([dict(tf=r["tf"], verdict=r["verdict"], why=r["why"]) for r in rows], open(os.path.join(res_dir, "verdicts.json"), "w"))
    # one small file with the headline numbers of every timeframe (charts.py reads it)
    summ = []
    for r in rows:
        h = r["hold"]
        d = {}
        if r.get("inputs"):
            for inp in r["inputs"]["inputs"]:
                if inp["name"] == "Trade direction":
                    d = {str(v["value"]): v["share_both"] for v in inp["values"]}
        summ.append(dict(tf=r["tf"], name=r["name"], verdict=r["verdict"], atr_pct=r["atr_pct"], fee_r=r["fee_r"],
                         rows=h["rows"], share_positive=h["share_positive_total"], share_both=h["share_positive_both_halves"],
                         with_filter_both=d.get("with the filter"), inverted_both=d.get("inverted (against the filter)"),
                         shipped_total=r["shipped"]["base"].get("total"), shipped_n=r["shipped"]["base"].get("n"),
                         shipped_pre_total=r["shipped"].get("pre", {}).get("total"),
                         pick_total=r["ev"]["base"]["total"] if "ev" in r else None, pick_n=r["ev"]["base"]["n"] if "ev" in r else None,
                         pick_pre_total=r["ev"].get("pre", {}).get("total") if "ev" in r else None,
                         pick_pre_n=r["ev"].get("pre", {}).get("n") if "ev" in r else None))
    json.dump(summ, open(os.path.join(res_dir, "summary.json"), "w"), default=float)


def tables(rows):
    L = ["## Results by timeframe", "",
         "The pick of each timeframe. Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade.", "",
         f"| Chart | Verdict | Search window ({WINDOW_TXT}) | Halves | Stressed costs | Untouched 2021-01 to 2023-10 | TradingView's tester would show |",
         "|---|---|---|---|---|---|---|"]
    for r in rows:
        if "ev" not in r:
            L.append(f"| {r['name']} | {r['verdict']} | none | - | - | - | - |")
            continue
        b, pre, st = r["ev"]["base"], r["ev"].get("pre", {}), r["ev"]["stress"]
        L.append(f"| {r['name']} | {r['verdict']} | {b['total']:+.1f}R, {b['n']} trades, PF {b['pf']:.2f}, DD {b['dd']:.1f}R | {b['h1']:+.1f} / {b['h2']:+.1f}R | "
                 f"{st['total']:+.1f}R | {pre.get('total', 0):+.1f}R, {pre.get('n', 0)} trades, PF {pre.get('pf', 0):.2f} (stressed {r['ev'].get('pre_stress', {}).get('total', 0):+.1f}R) | "
                 f"{r['ev']['tv_view']['total']:+.1f}R |")

    L += ["", "## What the search itself says", "",
          "Best 40 = the 40 steadiest settings of one part of the data, scored on another part. A test passes when their mean is positive,",
          "above 95% of random groups of 40, and stays positive when the months are resampled.", "",
          "| Chart | Settings tried | Positive before costs | Positive after costs | Positive in both halves | First half -> second (best 40) | Second -> first | Walk-forward | Search window -> untouched (candidates vs random) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h, u = r["hold"], r.get("unt")

        def cell(t, ok):
            if not t:
                return "n/a"
            return f"{t['top_mean']:+.1f}R, {t['top_pos'] * 100:.0f}% positive, months {t['boot_pos'] * 100:.0f}% ({'pass' if ok else 'fail'})"
        uc = "n/a"
        if u and "cand_mean" in u:
            uc = (f"{u['cand_mean']:+.1f}R, {u['cand_share_positive'] * 100:.0f}% positive vs {u['random_mean']:+.1f}R, {u['random_share_positive'] * 100:.0f}% "
                  f"({'pass' if u['passed'] else 'fail'})")
        elif u:
            uc = f"no candidates; random {u['random_mean']:+.1f}R, {u['random_share_positive'] * 100:.0f}% positive"
        L.append(f"| {r['name']} | {h['rows']} | {h['gross_share_positive'] * 100:.0f}% | {h['share_positive_total'] * 100:.0f}% | {h['share_positive_both_halves'] * 100:.1f}% | "
                 f"{cell(h['h1_to_h2'], h['pass_h1_to_h2'])} | {cell(h['h2_to_h1'], h['pass_h2_to_h1'])} | {cell(h['walk_forward'], h['pass_walk_forward'])} | {uc} |")

    L += ["", "## The file as shipped (your current inputs) on BTCUSDT", "",
          "The inputs of AMVI_FGF_Inverted_XAUUSD_15m.pine unchanged (calibrated for gold on 15m), run on each BTC chart timeframe.",
          "On the 2m and 10m charts the 15m AMVI does not line up with the chart's candles; the numbers there are what a reloaded chart shows.", "",
          f"| Chart | Search window ({WINDOW_TXT}) | Stressed costs | Untouched 2021-01 to 2023-10 |", "|---|---|---|---|"]
    for r in rows:
        s = r["shipped"]
        b, pre = s["base"], s.get("pre", {})
        if not b.get("n"):
            L.append(f"| {r['name']} | no trades | - | - |")
            continue
        L.append(f"| {r['name']} | {b['total']:+.1f}R, {b['n']} trades, PF {b['pf']:.2f}, DD {b['dd']:.1f}R | {s['stress']['total']:+.1f}R | "
                 + (f"{pre['total']:+.1f}R, {pre['n']} trades, PF {pre['pf']:.2f} |" if pre.get("n") else "no trades |"))

    L += ["", "## What one trade costs", "",
          "Commission of a round trip at 0.05% per side, in R, when the stop is 1 x ATR(14) of the chart (a 2 x ATR stop halves it).", "",
          "| Chart | Median ATR(14) as % of price | Round-trip commission in R |", "|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['atr_pct']:.3f}% | {r['fee_r']:.2f}R |")

    if any(r.get("trailing") for r in rows):
        L += ["", "## Trailing stop", "",
              "The same settings (a random sample of the search, 300 per timeframe) with the trailing stop off and with every Trail Activation x",
              "Trail Offset pair, nothing else changed, on the second-by-second price path. \"Both halves\" = share of the settings positive after",
              "costs in both halves of the search window.", "",
              "| Chart | Trailing off: both halves | Best pair (activation / offset, x ATR) | Its share | Improves how many settings | Median change | Shipped pair 1.5 / 1.0 | What chart-candle testing claims for 0.5 / 0.5 vs second-by-second |",
              "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            t = r.get("trailing")
            if not t:
                continue
            g = sorted(t["grid"], key=lambda x: (-x["share_both"], -x["median_change"]))[0]
            sh = next(x for x in t["grid"] if x["act"] == 1.5 and x["off"] == 1.0)
            tight = next(x for x in t["grid"] if x["act"] == 0.5 and x["off"] == 0.5)
            L.append(f"| {r['name']} | {t['base_share_both'] * 100:.1f}% | {g['act']:g} / {g['off']:g} | {g['share_both'] * 100:.1f}% | {g['share_improved'] * 100:.0f}% | {g['median_change']:+.1f}R | "
                     f"{sh['share_both'] * 100:.1f}% (improves {sh['share_improved'] * 100:.0f}%, median {sh['median_change']:+.1f}R) | "
                     f"{tight['share_both_chart'] * 100:.1f}% vs {tight['share_both'] * 100:.1f}% ({tight['flatter_chart']:+.2f}R per trade too good) |")
        L += ["", "Full grids per timeframe (share of settings positive in both halves; rows = Trail Activation, columns = Trail Offset, x ATR):", ""]
        for r in rows:
            t = r.get("trailing")
            if not t:
                continue
            offs = sorted({x["off"] for x in t["grid"]})
            acts = sorted({x["act"] for x in t["grid"]})
            L += [f"**{r['name']}** (trailing off: {t['base_share_both'] * 100:.1f}%)", "",
                  "| Activation \\ Offset | " + " | ".join(f"{o:g}" for o in offs) + " |", "|---|" + "---|" * len(offs)]
            for a in acts:
                cells = []
                for o in offs:
                    x = next(y for y in t["grid"] if y["act"] == a and y["off"] == o)
                    cells.append(f"{x['share_both'] * 100:.1f}%")
                L.append(f"| {a:g} | " + " | ".join(cells) + " |")
            L.append("")

    if any(r.get("inputs") for r in rows):
        def pick_input(r, name):
            for inp in r["inputs"]["inputs"]:
                if inp["name"] == name:
                    return {str(v["value"]): v for v in inp["values"]}
            return {}
        L += ["", "## Direction and exits across timeframes", "",
              "Share of the search's settings positive after costs in both halves, by one input's value (all other inputs random).", "",
              "| Chart | With the filter | Inverted | No time stop | Time stop on | No target | Target on | Stop <= 1 ATR | Stop >= 4 ATR |", "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if not r.get("inputs"):
                continue
            d = pick_input(r, "Trade direction")

            def grp(name, test):
                vals = [v for inp in r["inputs"]["inputs"] if inp["name"] == name for v in inp["values"] if test(v["value"])]
                n = sum(v["rows"] for v in vals)
                return f"{sum(v['share_both'] * v['rows'] for v in vals) / n * 100:.1f}%" if n else "-"
            L.append(f"| {r['name']} | {d.get('with the filter', {}).get('share_both', 0) * 100:.1f}% | {d.get('inverted (against the filter)', {}).get('share_both', 0) * 100:.1f}% | "
                     f"{grp('Time stop (bars, 0 = off)', lambda v: v == 0)} | {grp('Time stop (bars, 0 = off)', lambda v: v > 0)} | "
                     f"{grp('Take Profit (x ATR, 0 = off)', lambda v: v == 0)} | {grp('Take Profit (x ATR, 0 = off)', lambda v: v > 0)} | "
                     f"{grp('Stop Loss (x ATR)', lambda v: v <= 1)} | {grp('Stop Loss (x ATR)', lambda v: v >= 4)} |")
        L += ["", "Every input, value by value, for every timeframe: `results/INPUTS.md`."]
    return "\n".join(L)


def section(tf, name, v, why, ev, hold, plat, unt, p, changes, ttl, fn):
    b, pre = ev["base"], ev.get("pre", {})
    lev = RISK_PCT / b["avg_risk_pct"] if b.get("avg_risk_pct") else 0
    L = [f"### {name}: {v}", "", f"{why.capitalize()}. File: `presets/{fn}`.", "",
         f"- Search window: {F.line('', b)[2:]}; halves {b['h1']:+.1f} / {b['h2']:+.1f}R; average trade lasts {b.get('avg_bars', 0):.0f} candles.",
         f"- At {RISK_PCT}% risk per trade that is about {pct(b['total']):+.1f}% in three years with a worst drawdown of about {pct(b['dd']):.1f}% (no compounding); "
         f"the stop is {b['avg_risk_pct']:.2f}% of price on average, so {RISK_PCT}% risk means about {lev:.1f}x leverage.",
         f"- Costs: Bitget 0.06% {ev['bitget']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; "
         f"stressed {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side. Fees took {b['fee_r']:.1f}R and funding {b['fund_r']:+.1f}R.",
         f"- Price path: second by second {b['total']:+.1f}R; on 1-minute bars {ev['walk_1m']['total']:+.1f}R; on the chart's candles {ev['walk_chart']['total']:+.1f}R. "
         f"TradingView's tester (chart candles, the file's 0.06%, no funding) would show about {ev['tv_view']['total']:+.1f}R with {ev['tv_view']['n']} trades; "
         f"the same costs second by second give {ev['bitget']['total'] + ev['bitget']['fund_r']:+.1f}R.",
         f"- Untouched {ev.get('pre_from', '2021-01-01')[:7]} to 2023-10: {F.line('', pre)[2:] if pre.get('n') else 'no trades'}"
         + (f"; stressed {ev['pre_stress']['total']:+.1f}R; weeks resampled positive {pre.get('weeks_pos', 0) * 100:.0f}%." if pre.get("n") else "."),
         f"- The selection method on this timeframe, search window -> untouched period: {fmt_u(unt)}.",
         f"- Plateau: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} neighbouring settings positive in both halves"
         + (f"; fragile to: {', '.join(plat['fragile_inputs'])}." if plat["fragile_inputs"] else "."),
         f"- Concentration: 10 biggest trades {b['top10']:+.1f}R, all others {b['without_top10']:+.1f}R; weeks resampled positive {b['weeks_pos'] * 100:.1f}%.",
         f"- Same inputs, other trade direction: {ev['other_direction']['total']:+.1f}R."]
    if p.get("trail"):
        L.append(f"- Trailing stop restarted at every candle close (if TradingView does that): search window {ev['trail_restart']['total']:+.1f}R, "
                 f"untouched {ev.get('pre_trail_restart', {}).get('total', 0):+.1f}R.")
    L += ["", "| Input | Shipped | This file |", "|---|---|---|"]
    for nm, old, new in changes:
        L.append(f"| {ttl.get(nm, nm)} (`{nm}`) | {old} | {new} |")
    L += ["", "| Year | Trades | Net R | Winners | Max DD |", "|---|---|---|---|---|"]
    for y in ev.get("pre_by_year", []):
        L.append(f"| {y['year']} (untouched) | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    for y in ev["by_year"]:
        L.append(f"| {y['year']} | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    L += ["", "| Exit | Trades | Net R | Average |", "|---|---|---|---|"]
    for x in ev["by_reason"]:
        L.append(f"| {x['reason']} | {x['n']} | {x['total']:+.1f} | {x['avg']:+.2f} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(rd)
