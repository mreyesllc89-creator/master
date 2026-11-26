"""Final step: evaluate the pick of every chart timeframe, give it a verdict, write the
calibrated .pine file, the trade list and REPORT_tables.md (the tables of REPORT.md).

usage: python report.py [results_dir]

The verdict rules were fixed before the final sweeps were run:

  RECOMMENDED      both transfer tests and the walk-forward pass; the pick sits on a plateau
                   (>= 60 % of its one-step neighbours positive in both halves); it is positive
                   on the untouched 2021-01..2023-10 period at base AND stressed costs with at
                   least 50 trades; weeks resampled positive >= 95 %
  USABLE           plateau, untouched period positive at base and stressed costs with at least
                   50 trades, weeks >= 95 %, and at least one of the three hold-out tests passes
  PAPER-TRADE      plateau and untouched period positive at base costs, but the hold-out tests
                   fail or the sample is thin: it may be luck, watch it before risking money
  NOT RECOMMENDED  positive in both halves of the search window, but negative on the untouched
                   period or not on a plateau
  DO NOT TRADE     no setting is positive in both halves at base and stressed costs
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

RISK_PCT = 0.5      # the owner's lab rule: at most 0.5 % of equity per trade
SYMBOL = "BTCUSDT.P"
ORDER = ["RECOMMENDED", "USABLE", "PAPER-TRADE", "NOT RECOMMENDED", "DO NOT TRADE"]


def verdict(hold, plat, ev):
    if plat is None:
        return "DO NOT TRADE", "no setting is positive in both halves of the search window at base and stressed costs"
    pre, pres = ev.get("pre", {}), ev.get("pre_stress", {})
    plateau = plat["share_both_positive"] >= 0.6
    u = pre.get("n", 0) > 0 and pre.get("total", 0) > 0
    u50 = u and pre.get("n", 0) >= 50
    us = pres.get("total", 0) > 0
    weeks = ev["base"].get("weeks_pos", 0) >= 0.95
    t1, t2, wf = hold["pass_h1_to_h2"], hold["pass_h2_to_h1"], hold["pass_walk_forward"]
    if t1 and t2 and wf and plateau and u50 and us and weeks:
        return "RECOMMENDED", "passes every hold-out test and the untouched period"
    if plateau and u50 and us and weeks and (t1 or t2 or wf):
        return "USABLE", "positive on the untouched period and on a plateau; only part of the hold-out tests pass"
    if plateau and u:
        why = []
        if not (t1 or t2 or wf):
            why.append("the best settings of one half did not carry to the other")
        if not u50:
            why.append(f"only {pre.get('n', 0)} trades on the untouched period")
        if not us:
            why.append("negative on the untouched period at stressed costs")
        if not weeks:
            why.append("result leans on few weeks")
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


def header_lines(tf, v, why, ev, hold, plat, changes, p):
    b, pre = ev["base"], ev.get("pre", {})
    name = make_pine.TF_NAME[tf]
    L = [f"AMVI Full MTF Strategy (direction filter, closed-candle engine): {SYMBOL} {name}",
         f"STATUS: {v} - {why}.",
         "-" * 85,
         "Same code as AMVI_FGF_Inverted_XAUUSD_15m.pine; only the title, the commission and the",
         "input defaults listed at the end of this record differ. Record date 2026-11-26.",
         "Numbers come from a Python copy of this script (amvi_calibration/tools), not from",
         "TradingView: check them against the Strategy Tester before relying on them.",
         "",
         f" - Data: Binance BTCUSDT perpetual, 1-minute bars; chart {name}. Search window 2023-11-01 to",
         "   2026-11-25. Costs: 0.05% per side + 1 tick slippage + funding. R = the amount risked",
         f"   per trade (Stop Loss x ATR{p['exit_atr']}); with the file's Risk {RISK_PCT}% sizing 1R = {RISK_PCT}% of equity.",
         f" - Search window: {b['n']} trades ({b['n_long']}L/{b['n_short']}S), {b['total']:+.1f}R, PF {b['pf']:.2f}, max DD {b['dd']:.1f}R,",
         f"   halves {b['h1']:+.1f}R/{b['h2']:+.1f}R, {b['win'] * 100:.0f}% winners, longest losing streak {b['streak']}, {b['months_pos']} of {b['months']}",
         f"   months positive, {b.get('avg_bars', 0):.0f} bars per trade on average.",
         f" - Costs: Bitget taker 0.06% {ev['bitget']['total']:+.1f}R; as TradingView shows it (0.06% commission, no",
         f"   funding) about {ev['bitget']['total'] + ev['bitget']['fund_r']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; stressed (0.10% + 3 ticks)",
         f"   {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side.",
         " - Untouched 2021-01 to 2023-10 (never used to choose anything): " + (f"{pre['n']} trades, {pre['total']:+.1f}R," if pre.get("n") else "no trades."),
         (f"   PF {pre['pf']:.2f}, max DD {pre['dd']:.1f}R, {pre['months_pos']} of {pre['months']} months positive; stressed costs {ev['pre_stress']['total']:+.1f}R." if pre.get("n") else "   -"),
         f" - Hold-outs (best 40 settings of one part, scored on the other): first half -> second",
         f"   {fmt_t(hold['h1_to_h2'])}; second -> first",
         f"   {fmt_t(hold['h2_to_h1'])}; walk-forward",
         f"   {fmt_t(hold['walk_forward'])}.",
         f" - Plateau: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} one-step neighbours are positive in both halves.",
         f" - Concentration: the 10 biggest trades give {b['top10']:+.1f}R, the rest {b['without_top10']:+.1f}R; weeks",
         f"   resampled: positive in {b['weeks_pos'] * 100:.1f}% of draws.",
         f" - The other trade direction with the same inputs: {ev['other_direction']['total']:+.1f}R.",
         " - Not simulated: seconds timeframes (all off), the filter's entry hold, liquidation,",
         "   partial fills; stops fill on 1-minute bars, not ticks.",
         "",
         "Inputs set in this file (shipped value in brackets):"]
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


def run(res_dir):
    out_root = os.path.join(res_dir, "..")
    presets = os.path.join(out_root, "presets")
    os.makedirs(presets, exist_ok=True)
    cs, cp = F.contexts()
    tpl = open(make_pine.TEMPLATE, encoding="utf-8").read()
    ttl = titles(tpl)
    rows, sections = [], []
    for tf in space.CHART_TFS:
        hp = os.path.join(res_dir, f"holdout_{tf}m.json")
        pp = os.path.join(res_dir, f"plateau_{tf}m.json")
        if not os.path.exists(hp):
            continue
        hold = json.load(open(hp))
        picks = json.load(open(pp))["picks"] if os.path.exists(pp) else []
        name = make_pine.TF_NAME[tf]
        if not picks:
            v, why = verdict(hold, None, None)
            rows.append(dict(tf=tf, name=name, verdict=v, why=why, hold=hold))
            sections.append(f"### {name}: {v}\n\n{why.capitalize()}. No file was written for this timeframe.\n")
            continue
        plat = picks[0]
        p = space.normalize(plat["setting"])
        ev = F.evaluate(cs, cp, tf, p)
        v, why = verdict(hold, plat, ev)
        # the calibrated file
        src0, changes = make_pine.build(p, tf, ["x"], "t", "s")
        hl = header_lines(tf, v, why, ev, hold, plat, changes, p)
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
                    w.writerow([period, pd.Timestamp(int(t["entry_t"][i]), unit="ms").strftime("%Y-%m-%d %H:%M"), pd.Timestamp(int(t["exit_t"][i]), unit="ms").strftime("%Y-%m-%d %H:%M"),
                                "long" if t["dir"][i] > 0 else "short", f"{t['entry_px'][i]:.1f}", f"{t['exit_px'][i]:.1f}", f"{t['risk'][i]:.1f}",
                                f"{t['gross'][i]:.3f}", f"{t['fee_r'][i]:.3f}", f"{t['fund_r'][i]:.3f}", f"{t['r'][i]:.3f}", reason[int(t["why"][i])]])
        json.dump(dict(tf=tf, verdict=v, why=why, setting=p, eval=ev, plateau={k: plat[k] for k in plat if k != "setting"}),
                  open(os.path.join(res_dir, f"final_{tf}m.json"), "w"), default=float)
        rows.append(dict(tf=tf, name=name, verdict=v, why=why, hold=hold, ev=ev, plat=plat, p=p, changes=changes, file=fn))
        sections.append(section(tf, name, v, why, ev, hold, plat, p, changes, ttl, fn))
        print(f"{name}: {v} - {why}", flush=True)
    md = tables(rows) + "\n\n## Settings per timeframe\n\n" + "\n".join(sections)
    open(os.path.join(out_root, "REPORT_tables.md"), "w", encoding="utf-8").write(md)
    json.dump([dict(tf=r["tf"], verdict=r["verdict"], why=r["why"]) for r in rows], open(os.path.join(res_dir, "verdicts.json"), "w"))


def tables(rows):
    L = ["## Results by timeframe", "",
         "Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade.", "",
         "| Chart | Verdict | Search window (2023-11 to 2026-11) | Halves | Stressed costs | Untouched 2021-01 to 2023-10 | Best 40 of one half on the other | Rows positive in both halves |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h = r["hold"]
        tr = f"{h['h1_to_h2']['top_mean']:+.1f}R / {h['h2_to_h1']['top_mean']:+.1f}R" if h.get("h1_to_h2") and h.get("h2_to_h1") else "n/a"
        share = f"{h['share_positive_both_halves'] * 100:.1f}%"
        if "ev" not in r:
            L.append(f"| {r['name']} | {r['verdict']} | none | - | - | - | {tr} | {share} |")
            continue
        b, pre, st = r["ev"]["base"], r["ev"].get("pre", {}), r["ev"]["stress"]
        L.append(f"| {r['name']} | {r['verdict']} | {b['total']:+.1f}R, {b['n']} trades, PF {b['pf']:.2f}, DD {b['dd']:.1f}R | {b['h1']:+.1f} / {b['h2']:+.1f}R | "
                 f"{st['total']:+.1f}R | {pre.get('total', 0):+.1f}R, {pre.get('n', 0)} trades, PF {pre.get('pf', 0):.2f} | {tr} | {share} |")
    L += ["", "## What the search itself says", "",
          "| Chart | Settings tried | Positive before costs | Positive after costs | Median after costs | First half -> second half (best 40) | Second -> first | Walk-forward |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h = r["hold"]

        def cell(t, ok):
            if not t:
                return "n/a"
            return f"{t['top_mean']:+.1f}R, {t['top_pos'] * 100:.0f}% positive, months {t['boot_pos'] * 100:.0f}% ({'pass' if ok else 'fail'})"
        L.append(f"| {r['name']} | {h['rows']} | {h['gross_share_positive'] * 100:.0f}% | {h['share_positive_total'] * 100:.0f}% | {h['median_total']:+.0f}R | "
                 f"{cell(h['h1_to_h2'], h['pass_h1_to_h2'])} | {cell(h['h2_to_h1'], h['pass_h2_to_h1'])} | {cell(h['walk_forward'], h['pass_walk_forward'])} |")
    return "\n".join(L)


def section(tf, name, v, why, ev, hold, plat, p, changes, ttl, fn):
    b, pre = ev["base"], ev.get("pre", {})
    lev = RISK_PCT / b["avg_risk_pct"] if b.get("avg_risk_pct") else 0
    L = [f"### {name}: {v}", "", f"{why.capitalize()}. File: `presets/{fn}`.", "",
         f"- Search window: {F.line('', b)[2:]}; halves {b['h1']:+.1f} / {b['h2']:+.1f}R; average trade lasts {b.get('avg_bars', 0):.0f} candles.",
         f"- At {RISK_PCT}% risk per trade that is about {pct(b['total']):+.1f}% in three years with a worst drawdown of about {pct(b['dd']):.1f}% (no compounding); "
         f"the stop is {b['avg_risk_pct']:.2f}% of price on average, so {RISK_PCT}% risk means about {lev:.1f}x leverage.",
         f"- Costs: Bitget 0.06% {ev['bitget']['total']:+.1f}R; TradingView's view at 0.05% without funding {ev['tv_file']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; "
         f"stressed {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side. Fees took {b['fee_r']:.1f}R and funding {b['fund_r']:+.1f}R.",
         f"- Untouched 2021-01 to 2023-10: {F.line('', pre)[2:] if pre.get('n') else 'no trades'}"
         + (f"; stressed {ev['pre_stress']['total']:+.1f}R; weeks resampled positive {pre.get('weeks_pos', 0) * 100:.0f}%." if pre.get("n") else "."),
         f"- Plateau: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} neighbouring settings positive in both halves"
         + (f"; fragile to: {', '.join(plat['fragile_inputs'])}." if plat["fragile_inputs"] else "."),
         f"- Concentration: 10 biggest trades {b['top10']:+.1f}R, all others {b['without_top10']:+.1f}R; weeks resampled positive {b['weeks_pos'] * 100:.1f}%.",
         f"- Same inputs, other trade direction: {ev['other_direction']['total']:+.1f}R.", "",
         "| Input | Shipped | This file |", "|---|---|---|"]
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
