"""Final step: evaluate the pick of every chart timeframe, give it a verdict, write the
calibrated .pine file (PAPER-TRADE and better only), the trade list and REPORT_tables.md
(the tables of REPORT.md).

usage: python report.py [results_dir]

The verdict rules. "Solid on the untouched period" = the pick is positive on 2021-01..2023-10
at base AND stressed costs with at least 50 trades, and is not fragile (at least 60 % of its
one-step neighbours are positive in both halves of the search window).

  RECOMMENDED      solid on the untouched period; that result stays positive in at least 95 %
                   of resamples of its weeks; all four hold-out tests pass (first half ->
                   second, second -> first, walk-forward, search window -> untouched period);
                   the search-window result does not lean on a few weeks either
  USABLE           solid on the untouched period; positive in at least 95 % of resamples of
                   its weeks; at least one of the four hold-out tests passes
  PAPER-TRADE      solid on the untouched period; positive in at least 90 % of resamples of
                   its weeks; the hold-out tests fail or the 95 % is missed: watch it, do not
                   fund it
  NOT RECOMMENDED  the search shows more than luck (a hold-out test passes, or it found more
                   candidates than 95 % of no-skill worlds), but the pick does not hold up on
                   the untouched period or is fragile
  DO NOT TRADE     the search found no more than luck would, and the best candidate does not
                   hold up on the untouched period

A pick that uses the trailing stop can only be RECOMMENDED or USABLE if it is also positive
on both periods when the trailing stop starts again at every candle close (how TradingView
treats a re-sent exit order could not be checked from here).

How often luck alone earns each verdict is measured by luck.py (no-skill worlds) and printed
in the report: with these rules PAPER-TRADE or better comes up a few times in a hundred per
timeframe, USABLE well under one in a hundred, RECOMMENDED never in the simulations. The
rules were tightened after the statistics review and before the final run: the first version
gave PAPER-TRADE to a no-edge pick about one time in three. The plateau share is a screen
against fragility, not evidence against luck (a lucky candidate passes it nine times in ten).
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

RISK_PCT = F.RISK_PCT   # the owner's lab rule: at most 0.5 % of equity per trade
SYMBOL = "BTCUSDT.P"
ORDER = ["RECOMMENDED", "USABLE", "PAPER-TRADE", "NOT RECOMMENDED", "DO NOT TRADE"]
WITH_FILE = ("RECOMMENDED", "USABLE", "PAPER-TRADE")
WINDOW_TXT = "2023-11 to 2026-10"


def replay_note(tf, p):
    """A setting that reads 15m candles from a higher chart can only be replayed on TradingView
    as far back as 100,000 of those candles reach (about 1,042 days)."""
    below = {t for t in list(p["tfs"]) + [p["f_tf"]] if t < tf}
    if 15 not in below:
        return None
    since = (pd.Timestamp("2026-11-26") - pd.Timedelta(minutes=15 * 100_000)).strftime("%Y-%m")
    return (f"This setting reads 15m candles from a {make_pine.TF_NAME[tf]} chart. TradingView keeps about 100,000 intrabars per request, "
            f"so its tester can replay it only back to about {since}; earlier trades of this record cannot be checked there.")


def trail_robust(p, ev):
    """A trailing pick must not depend on the trailing state surviving the candle close."""
    if not p.get("trail"):
        return True
    return ev.get("trail_restart", {}).get("total", 0) > 0 and ev.get("pre_trail_restart", {}).get("total", 0) > 0


def verdict(hold, plat, ev, unt=None, p=None, luck=None):
    t1, t2, wf = hold["pass_h1_to_h2"], hold["pass_h2_to_h1"], hold["pass_walk_forward"]
    tu = bool(unt and unt.get("passed"))
    any_test = t1 or t2 or wf or tu
    # is there anything in the search beyond luck?
    beyond = any_test or (luck is not None and luck["candidates"]["worlds_at_least"] <= 0.05)
    if plat is None:
        return "DO NOT TRADE", "no setting is positive in both halves of the search window at base and stressed costs"
    pre, pres = ev.get("pre", {}), ev.get("pre_stress", {})
    sturdy = plat["share_both_positive"] >= 0.6
    u = pre.get("n", 0) > 0 and pre.get("total", 0) > 0
    u50 = u and pre.get("n", 0) >= 50
    us = pres.get("total", 0) > 0
    weeks = ev["base"].get("weeks_pos", 0) >= 0.95
    uw = pre.get("weeks_pos", 0) if u else 0.0
    tr = trail_robust(p or {}, ev)
    solid = sturdy and u50 and us
    if solid and uw >= 0.95 and t1 and t2 and wf and tu and weeks and tr:
        return "RECOMMENDED", "passes every hold-out test and holds up on the untouched period"
    if solid and uw >= 0.95 and any_test and tr:
        return "USABLE", "holds up on the untouched period beyond what luck gives, and part of the hold-out tests pass"
    if solid and uw >= 0.90:
        why = []
        if not any_test:
            why.append("no hold-out test passes")
        if uw < 0.95:
            why.append(f"its untouched result is positive in only {uw * 100:.0f}% of resamples of the weeks")
        if not tr:
            why.append("it depends on how TradingView handles the trailing stop at candle closes")
        return "PAPER-TRADE", "positive on the untouched period at base and stressed costs, but " + "; ".join(why)
    why = []
    if not sturdy:
        why.append("neighbouring settings lose")
    if not u:
        why.append("it loses on the untouched 2021-2023 period" if pre.get("n", 0) > 0 else "it does not trade on the untouched 2021-2023 period")
    elif not u50:
        why.append(f"it has only {pre.get('n', 0)} trades on the untouched period")
    elif not us:
        why.append("it loses on the untouched period at stressed costs")
    elif uw < 0.90:
        why.append(f"its untouched result is positive in only {uw * 100:.0f}% of resamples of the weeks, so it rests on a few good weeks")
    if beyond:
        return "NOT RECOMMENDED", "the search shows more than luck would, but the pick does not hold up: " + "; ".join(why)
    return "DO NOT TRADE", "the search found no more winners than luck would, no hold-out test passes, and the best candidate does not hold up: " + "; ".join(why)


def titles(src):
    """input variable -> the label TradingView shows."""
    out = {}
    for m in re.finditer(r"^(\w+)\s*=\s*input\.\w+\((?:\"[^\"]*\"|[^,]+),\s*\"([^\"]*)\"", src, re.M):
        out[m.group(1)] = m.group(2)
    return out


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


def luck_line(luck):
    if not luck or "pick" not in luck:
        return ""
    k = luck["pick"]
    return (f"In shuffled worlds where no setting has an edge, the same choice still shows about {k['search_median']:+.0f}R here "
            f"(95th percentile {k['search_p95']:+.0f}R) and {k['untouched_median']:+.0f}R on fresh months.")


def header_lines(tf, v, why, ev, hold, plat, unt, changes, p, luck=None, n_rows=0):
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
              f"second-by-second trade prices. Costs: 0.05% per side + 1 tick slippage + funding. R = the amount "
              f"risked per trade (Stop Loss x ATR{p['exit_atr']}); with the file's Risk {RISK_PCT}% sizing 1R = {RISK_PCT}% of equity.")
    if pre.get("n"):
        L += wrap(f"On data it was NOT chosen on (untouched {ev.get('pre_from', '2021-01-01')[:7]} to 2023-10): {pre['n']} trades, {pre['total']:+.1f}R, "
                  f"PF {pre['pf']:.2f}, max DD {pre['dd']:.1f}R, {pre['months_pos']} of {pre['months']} months positive; stressed costs "
                  f"{ev['pre_stress']['total']:+.1f}R; positive in {pre.get('weeks_pos', 0) * 100:.0f}% of resamples of its weeks.")
    else:
        L += wrap("On data it was NOT chosen on (untouched 2021-01 to 2023-10): no trades.")
    L += wrap(f"Where it was chosen (search window 2023-11-01 to 2026-10-31, the best of {n_rows:,} settings, so flattered): "
              f"{b['n']} trades ({b['n_long']}L/{b['n_short']}S), {b['total']:+.1f}R, PF {b['pf']:.2f}, max DD {b['dd']:.1f}R, "
              f"halves {b['h1']:+.1f}R/{b['h2']:+.1f}R, {b['win'] * 100:.0f}% winners, longest losing streak {b['streak']}, "
              f"{b['months_pos']} of {b['months']} months positive, {b.get('avg_bars', 0):.0f} bars per trade on average. " + luck_line(luck))
    L += wrap(f"Costs on the search window: Bitget taker 0.06% {ev['bitget']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; stressed "
              f"(0.10% + 3 ticks) {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side.")
    same_costs = ev["bitget"]["total"] + ev["bitget"]["fund_r"]
    L += wrap(f"TradingView's Strategy Tester walks stops on the chart's candles (no Bar Magnifier) and charges no funding: "
              f"on the same bars it would show about {ev['tv_view']['total']:+.1f}R ({ev['tv_view']['n']} trades) for the search window. The same "
              f"costs on second-by-second prices give {same_costs:+.1f}R; any difference is the tester's price path, not profit.")
    if p.get("trail"):
        L += wrap(f"Trailing stop: if TradingView starts it again at every candle close (not checked), the search window "
                  f"gives {ev['trail_restart']['total']:+.1f}R instead of {b['total']:+.1f}R and the untouched period "
                  f"{ev.get('pre_trail_restart', {}).get('total', 0):+.1f}R instead of {pre.get('total', 0):+.1f}R.")
    L += wrap(f"Hold-outs (best 40 settings of one part, scored on the other): first half -> second {fmt_t(hold['h1_to_h2'])}; "
              f"second -> first {fmt_t(hold['h2_to_h1'])}; walk-forward {fmt_t(hold['walk_forward'])}. "
              f"Search window -> untouched period: {fmt_u(unt)}.")
    L += wrap(f"Not fragile: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} one-step neighbours are positive in both halves "
              f"(a screen against fragility, not against luck). Concentration: the 10 biggest trades of the search window give "
              f"{b['top10']:+.1f}R, the rest {b['without_top10']:+.1f}R. The other trade direction with the same inputs: {ev['other_direction']['total']:+.1f}R.")
    if replay_note(tf, p):
        L += wrap(replay_note(tf, p))
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
    t = (f"the {u['n_candidates']} candidates made {u['cand_mean']:+.1f}R on average ({u['cand_share_positive'] * 100:.0f}% positive, "
         f"months resampled {u['boot_pos'] * 100:.0f}%): {'pass' if u['passed'] else 'fail'}")
    if "matched_null_mean" in u:
        t += (f"; random settings of the same trade direction made {u['matched_null_mean']:+.1f}R, so the choice "
              f"{'adds something' if u['passed_matched'] else 'adds nothing measurable'} beyond the direction")
    return t


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


def fee_in_r(ft, tf, start=None):
    """Median ATR(14) of the chart timeframe as % of price from `start` on (default: the
    search window), and the commission of one round trip at 0.05 % per side in R for a
    1 x ATR stop."""
    ch = ft.mk.tf(tf)
    a = ft.atr(tf, 14)
    m = (ch.t >= sweep.ms(start or F.SEARCH[0])) & ~np.isnan(a)
    atr_pct = float(np.median(a[m] / ch.c[m]) * 100)
    return atr_pct, 2 * F.BASE_FEE * 100 / atr_pct


def run(res_dir):
    out_root = os.path.join(res_dir, "..")
    presets = os.path.join(out_root, "presets")
    os.makedirs(presets, exist_ok=True)
    for old in os.listdir(presets):
        if old.endswith(".pine"):
            os.remove(os.path.join(presets, old))
    for old in os.listdir(res_dir):
        if old.startswith("trades_BTCUSDT_") and old.endswith(".csv"):
            os.remove(os.path.join(res_dir, old))
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
        luck = load_json(os.path.join(res_dir, f"luck_{tf}m.json"))
        name = make_pine.TF_NAME[tf]
        base_ev = F.evaluate(cs, cp, tf, shipped, light=True)
        for k in ("_trades", "_pre_trades"):
            base_ev.pop(k, None)
        atr_pct, fee_r = fee_in_r(cs[0], tf)
        atr_pre, fee_pre = fee_in_r(cp[0], tf, F.PRESAMPLE[0])
        row = dict(tf=tf, name=name, hold=hold, unt=unt, shipped=base_ev, atr_pct=atr_pct, fee_r=fee_r, atr_pre=atr_pre, fee_pre=fee_pre, luck=luck,
                   trailing=load_json(os.path.join(res_dir, f"trailing_{tf}m.json")),
                   inputs=load_json(os.path.join(res_dir, f"inputs_{tf}m.json")))
        if not picks:
            v, why = verdict(hold, None, None, unt, None, luck)
            row.update(verdict=v, why=why)
            rows.append(row)
            sections.append(f"### {name}: {v}\n\n{why.capitalize()}. No file was written for this timeframe.\n")
            print(f"{name}: {v} - {why}", flush=True)
            continue
        plat = picks[0]
        p = space.normalize(plat["setting"])
        ev = F.evaluate(cs, cp, tf, p)
        v, why = verdict(hold, plat, ev, unt, p, luck)
        src0, changes = make_pine.build(p, tf, ["x"], "t", "s")
        fn = None
        if v in WITH_FILE:
            # the calibrated file: only for a pick that holds up on the untouched period
            hl = header_lines(tf, v, why, ev, hold, plat, unt, changes, p, luck, hold["rows"])
            tag = {"RECOMMENDED": "recommended", "USABLE": "usable", "PAPER-TRADE": "paper-trade only"}[v]
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
        sections.append(section(tf, name, v, why, ev, hold, plat, unt, p, changes, ttl, fn, luck))
        print(f"{name}: {v} - {why}", flush=True)
    md = tables(rows) + "\n\n## Settings per timeframe\n\n" + "\n".join(sections)
    open(os.path.join(out_root, "REPORT_tables.md"), "w", encoding="utf-8").write(md)
    json.dump([dict(tf=r["tf"], verdict=r["verdict"], why=r["why"]) for r in rows], open(os.path.join(res_dir, "verdicts.json"), "w"))
    # one small file with the headline numbers of every timeframe (charts.py reads it)
    summ = []
    for r in rows:
        h = r["hold"]
        d = direction(r)
        summ.append(dict(tf=r["tf"], name=r["name"], verdict=r["verdict"], atr_pct=r["atr_pct"], fee_r=r["fee_r"],
                         rows=h["rows"], share_positive=h["share_positive_total"], share_both=h["share_positive_both_halves"],
                         with_filter_both=d.get("with", {}).get("share_both"), inverted_both=d.get("inv", {}).get("share_both"),
                         shipped_total=r["shipped"]["base"].get("total"), shipped_n=r["shipped"]["base"].get("n"),
                         shipped_pre_total=r["shipped"].get("pre", {}).get("total"),
                         pick_total=r["ev"]["base"]["total"] if "ev" in r else None, pick_n=r["ev"]["base"]["n"] if "ev" in r else None,
                         pick_pre_total=r["ev"].get("pre", {}).get("total") if "ev" in r else None,
                         pick_pre_n=r["ev"].get("pre", {}).get("n") if "ev" in r else None, file=r.get("file")))
    json.dump(summ, open(os.path.join(res_dir, "summary.json"), "w"), default=float)


def direction(r):
    """The 'Trade direction' rows of a timeframe's input summary: {'with': row, 'inv': row}."""
    out = {}
    if r.get("inputs"):
        for inp in r["inputs"]["inputs"]:
            if inp["name"] == "Trade direction":
                for v in inp["values"]:
                    out["with" if str(v["value"]).startswith("with") else "inv"] = v
    return out


def group(r, name, test):
    """Settings of one input pooled over the values that pass `test`: (after-cost share,
    before-cost share, typical fees in R, number of settings)."""
    vals = [v for inp in r["inputs"]["inputs"] if inp["name"] == name for v in inp["values"] if test(v["value"])]
    n = sum(v["rows"] for v in vals)
    if not n:
        return None
    return (sum(v["share_both"] * v["rows"] for v in vals) / n, sum(v["share_both_gross"] * v["rows"] for v in vals) / n,
            sum(v["median_fee"] * v["rows"] for v in vals) / n, n)


def glance(rows):
    """The compact verdict table of the report's short version, highest timeframe first."""
    L = ["## Verdicts at a glance", "",
         "| Chart | Verdict | On 2021-2023, which it was not chosen on | Last three years, where it was chosen | File |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: -x["tf"]):
        if "ev" not in r:
            L.append(f"| {r['name']} | {r['verdict']} | no candidate | - | none |")
            continue
        b, pre, ev = r["ev"]["base"], r["ev"].get("pre", {}), r["ev"]
        if not pre.get("n"):
            pc = "no trades"
        else:
            pc = f"{pre['total']:+.1f}R in {pre['n']} trades"
            if pre["total"] > 0 and ev.get("pre_stress", {}).get("total", 0) <= 0:
                pc += f" ({ev['pre_stress']['total']:+.1f}R at stressed costs)"
            elif pre["total"] > 0 and pre.get("weeks_pos", 0) < 0.95:
                pc += f", positive in {pre['weeks_pos'] * 100:.0f}% of resamples"
        L.append(f"| {r['name']} | {r['verdict']} | {pc} | {b['total']:+.1f}R in {b['n']} trades | "
                 + (f"`{r['file']}`" if r.get("file") else "none") + " |")
    return L


def tables(rows):
    L = glance(rows) + ["", "## Results by timeframe", "",
         "The pick of each timeframe. Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade. The untouched period comes",
         "first because the pick was not chosen on it; the search-window figure is the best of thousands of settings and is flattered by that choice.", "",
         f"| Chart | Verdict | Untouched 2021-01 to 2023-10 (not chosen on it) | Stressed costs | Positive in resamples of its weeks | Search window {WINDOW_TXT} (chosen here) | Halves | File |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "ev" not in r:
            L.append(f"| {r['name']} | {r['verdict']} | no candidate | - | - | - | - | none |")
            continue
        b, pre = r["ev"]["base"], r["ev"].get("pre", {})
        pc = (f"{pre['total']:+.1f}R, {pre['n']} trades, PF {pre['pf']:.2f}, DD {pre['dd']:.1f}R" if pre.get("n") else "no trades")
        L.append(f"| {r['name']} | {r['verdict']} | {pc} | {r['ev'].get('pre_stress', {}).get('total', 0):+.1f}R | {pre.get('weeks_pos', 0) * 100:.0f}% | "
                 f"{b['total']:+.1f}R, {b['n']} trades, PF {b['pf']:.2f}, DD {b['dd']:.1f}R | {b['h1']:+.1f} / {b['h2']:+.1f}R | "
                 + (f"`presets/{r['file']}`" if r.get("file") else "none") + " |")

    L += ["", "## What the search itself says", "",
          "Best 40 = the 40 steadiest settings of one part of the data, scored on another part. A test passes when their mean is positive,",
          "above 95% of random groups of 40, and stays positive in 95% of resamples of the months. Being positive is the hard part: random",
          "settings mostly bleed commission, so beating them is easy.", "",
          "| Chart | Settings tried | Positive before costs | Positive after costs | Positive in both halves | First half -> second (best 40) | Second -> first | Walk-forward | Search window -> untouched period (candidates) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h, u = r["hold"], r.get("unt")

        def cell(t, ok):
            if not t:
                return "n/a"
            return f"{t['top_mean']:+.1f}R, {t['top_pos'] * 100:.0f}% positive, months {t['boot_pos'] * 100:.0f}% ({'pass' if ok else 'fail'})"
        uc = "n/a"
        if u and "cand_mean" in u:
            uc = f"{u['cand_mean']:+.1f}R, {u['cand_share_positive'] * 100:.0f}% positive, months {u['boot_pos'] * 100:.0f}% ({'pass' if u['passed'] else 'fail'})"
            if "matched_null_mean" in u:
                uc += f"; random settings of the same direction {u['matched_null_mean']:+.1f}R ({'beaten' if u['passed_matched'] else 'not beaten'})"
        elif u:
            uc = "no candidates"
        L.append(f"| {r['name']} | {h['rows']:,} | {h['gross_share_positive'] * 100:.0f}% | {h['share_positive_total'] * 100:.0f}% | {h['share_positive_both_halves'] * 100:.1f}% | "
                 f"{cell(h['h1_to_h2'], h['pass_h1_to_h2'])} | {cell(h['h2_to_h1'], h['pass_h2_to_h1'])} | {cell(h['walk_forward'], h['pass_walk_forward'])} | {uc} |")

    if any(r.get("unt") and "random_with_filter" in r["unt"] for r in rows):
        L += ["", "## The two trade directions on data the search never saw", "",
              "400 random settings of the search per timeframe (at least 30 trades in each half of the search window), run over the untouched",
              "period 2021-01 to 2023-10 and split by trade direction; then the same split on the search window for all settings of the search.",
              "\"Positive\" = net result above zero over the whole period after 0.05% per side, 1 tick and funding. The last two columns:",
              "positive in both halves of the search window, after costs / before costs.", "",
              "| Chart | Untouched: with the filter positive | Median | Untouched: inverted positive | Median | Search window: with the filter positive | Median | Inverted positive | Median | Both halves, with the filter | Both halves, inverted |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            u = r.get("unt")
            if not u or "random_with_filter" not in u:
                continue
            w, iv = u["random_with_filter"], u["random_inverted"]
            d = direction(r)
            dw, di = d.get("with", {}), d.get("inv", {})
            L.append(f"| {r['name']} | {w['share_positive'] * 100:.0f}% of {w['n']} | {w['median']:+.1f}R | {iv['share_positive'] * 100:.0f}% of {iv['n']} | {iv['median']:+.1f}R | "
                     f"{dw.get('share_positive', 0) * 100:.0f}% | {dw.get('median_total', 0):+.1f}R | {di.get('share_positive', 0) * 100:.0f}% | {di.get('median_total', 0):+.1f}R | "
                     f"{dw.get('share_both', 0) * 100:.1f}% / {dw.get('share_both_gross', 0) * 100:.1f}% | {di.get('share_both', 0) * 100:.1f}% / {di.get('share_both_gross', 0) * 100:.1f}% |")

    if any(r.get("luck") for r in rows):
        L += ["", "## Is there more here than luck?", "",
              "The same counts in 1,000 no-skill worlds per timeframe: the months of the real search drawn at random, each month's result of all",
              "settings flipped by one coin toss, so that no setting has an edge before costs while fees, trade counts and the likeness between",
              "settings stay real. A real count inside the luck-only range is no evidence of an edge.", "",
              "| Chart | Positive in both halves: real | Luck alone (5% to 95% of worlds) | Worlds with at least as many | Candidates: real | Luck alone | Worlds with at least as many | With the filter minus inverted: real | Luck alone | Worlds with a gap this large |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            k = r.get("luck")
            if not k:
                continue
            sb, c, g = k["share_both"], k["candidates"], k["gap"]
            L.append(f"| {r['name']} | {sb['real'] * 100:.1f}% | {sb['median'] * 100:.1f}% ({sb['p05'] * 100:.1f} to {sb['p95'] * 100:.1f}%) | {sb['worlds_at_least'] * 100:.0f}% | "
                     f"{c['real']} | {c['median']:.0f} ({c['p05']:.0f} to {c['p95']:.0f}) | {c['worlds_at_least'] * 100:.0f}% | {g['real'] * 100:+.1f} points | "
                     f"{g['p05'] * 100:+.1f} to {g['p95'] * 100:+.1f} | {k['gap_abs_at_least'] * 100:.0f}% |")
        L += ["", "What a pick is worth when nothing is there: the steadiest candidate of each no-skill world, and how often luck alone meets the",
              "conditions of each verdict (plateau leg taken as passed, months standing in for weeks).", "",
              "| Chart | Luck's pick on the search window (median, 95th percentile) | Luck's pick on fresh months | Positive on fresh months | At base and stressed costs with 50+ trades | Luck passes at least one hold-out test | Luck earns PAPER-TRADE or better | USABLE or better | RECOMMENDED |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            k = r.get("luck")
            if not k or "pick" not in k:
                continue
            pk, lp = k["pick"], k["luck_pass"]
            L.append(f"| {r['name']} | {pk['search_median']:+.1f}R, {pk['search_p95']:+.1f}R | {pk['untouched_median']:+.1f}R | {lp['pick_pos'] * 100:.0f}% | {lp['pick_ok'] * 100:.0f}% | "
                     f"{lp['any'] * 100:.1f}% | {lp['paper'] * 100:.1f}% | {lp['usable'] * 100:.1f}% | {lp['recommended'] * 100:.1f}% |")

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
          "Commission of a round trip at 0.05% per side, in R, when the stop is 1 x ATR(14) of the chart (a 2 x ATR stop halves it). The market",
          "moved more per candle in 2021-2023, so the same commission was a smaller share of the risk then.", "",
          "| Chart | Search window: median ATR(14) as % of price | Round-trip commission in R | Untouched 2021-2023: median ATR(14) | Round-trip commission in R |",
          "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['atr_pct']:.3f}% | {r['fee_r']:.2f}R | {r['atr_pre']:.3f}% | {r['fee_pre']:.2f}R |")

    if any(r.get("trailing") for r in rows):
        L += ["", "## Trailing stop", "",
              "The same settings (a random sample of the search: 300 per timeframe, 200 on 5m and below) with the trailing stop off and with",
              "each of the 42 Trail Activation x Trail Offset pairs, nothing else changed, on the second-by-second price path. \"Both halves\" =",
              "share of the settings positive after costs in both halves of the search window. The best of 42 pairs is partly the luckiest of",
              "42, so it was chosen on one random half of the settings and is read on the other half.", "",
              "| Chart | Trailing off: both halves | With trailing: median of the 42 pairs | Pairs above \"off\" | Best pair chosen on half the settings (activation / offset) | On the other half: with it vs trailing off | Shipped pair 1.5 / 1.0 | It makes a setting better / leaves it unchanged / worse | Chart-candle testing claims for 0.5 / 0.5 | Second by second it is |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            t = r.get("trailing")
            if not t:
                continue
            bp = t["best_pair"]
            sh = next(x for x in t["grid"] if x["act"] == 1.5 and x["off"] == 1.0)
            tight = next(x for x in t["grid"] if x["act"] == 0.5 and x["off"] == 0.5)
            L.append(f"| {r['name']} | {t['base_share_both'] * 100:.1f}% | {t['grid_median_share_both'] * 100:.1f}% | {t['pairs_above_base']} of {t['pairs']} | "
                     f"{bp['act']:g} / {bp['off']:g} | {bp['share_other_half'] * 100:.1f}% vs {bp['base_other_half'] * 100:.1f}% | {sh['share_both'] * 100:.1f}% | "
                     f"{sh['share_better'] * 100:.0f}% / {sh['share_unchanged'] * 100:.0f}% / {sh['share_worse'] * 100:.0f}% | "
                     f"{tight['share_both_chart'] * 100:.1f}% ({tight['flatter_chart']:+.2f}R per trade too good) | {tight['share_both'] * 100:.1f}% |")
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
        def cell3(g):
            return f"{g[0] * 100:.1f}% / {g[1] * 100:.1f}% / {g[2]:.0f}R" if g else "-"
        L += ["", "## Direction and exits across timeframes", "",
              "Share of the search's settings positive in both halves, by one input's value (all other inputs random). Each cell: after costs /",
              "before costs / the commission a typical setting of the group paid in three years. Where two values differ after costs but not",
              "before, the difference is commission, not better trades.", "",
              "| Chart | With the filter | Inverted | Trailing off | Trailing on | Stop up to 1 ATR | Stop 4 ATR and more | No target | Target on | No time stop | Time stop on |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if not r.get("inputs"):
                continue
            L.append(f"| {r['name']} | {cell3(group(r, 'Trade direction', lambda v: str(v).startswith('with')))} | {cell3(group(r, 'Trade direction', lambda v: str(v).startswith('inv')))} | "
                     f"{cell3(group(r, 'Trailing stop', lambda v: v == 'off'))} | {cell3(group(r, 'Trailing stop', lambda v: v == 'on'))} | "
                     f"{cell3(group(r, 'Stop Loss (x ATR)', lambda v: v <= 1))} | {cell3(group(r, 'Stop Loss (x ATR)', lambda v: v >= 4))} | "
                     f"{cell3(group(r, 'Take Profit (x ATR, 0 = off)', lambda v: v == 0))} | {cell3(group(r, 'Take Profit (x ATR, 0 = off)', lambda v: v > 0))} | "
                     f"{cell3(group(r, 'Time stop (bars, 0 = off)', lambda v: v == 0))} | {cell3(group(r, 'Time stop (bars, 0 = off)', lambda v: v > 0))} |")
        L += ["", "Every input, value by value, for every timeframe: `results/INPUTS.md`."]
    return "\n".join(L)


def section(tf, name, v, why, ev, hold, plat, unt, p, changes, ttl, fn, luck=None):
    b, pre = ev["base"], ev.get("pre", {})
    lev = RISK_PCT / b["avg_risk_pct"] if b.get("avg_risk_pct") else 0
    file_txt = (f"File: `presets/{fn}`." if fn else
                "No file was written: a file is an invitation to trade, and this pick did not earn one. Its inputs are listed below for the record.")
    L = [f"### {name}: {v}", "", f"{why[0].upper() + why[1:]}. {file_txt}", "",
         f"- On data it was not chosen on (untouched {ev.get('pre_from', '2021-01-01')[:7]} to 2023-10): {F.line('', pre)[2:] if pre.get('n') else 'no trades'}"
         + (f"; stressed costs {ev['pre_stress']['total']:+.1f}R; positive in {pre.get('weeks_pos', 0) * 100:.0f}% of resamples of its weeks." if pre.get("n") else "."),
         f"- Where it was chosen (search window): {F.line('', b)[2:]}; halves {b['h1']:+.1f} / {b['h2']:+.1f}R; average trade lasts {b.get('avg_bars', 0):.0f} candles. "
         + luck_line(luck),
         f"- With {RISK_PCT}% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about {b['pct_total']:+.1f}% in three years "
         f"with a worst drawdown of about {b['pct_dd']:.1f}% (no compounding)"
         + (f", and the untouched period about {pre['pct_total']:+.1f}% with a worst drawdown of {pre['pct_dd']:.1f}%" if pre.get("n") else "")
         + f". The stop is {b['avg_risk_pct']:.2f}% of price on average, so {RISK_PCT}% risk asks for about {lev:.1f}x leverage"
         + (f"; the 5x cap cuts the position on {b['cap_share'] * 100:.0f}% of the trades, which then risk less than {RISK_PCT}%." if b.get("cap_share", 0) > 0.005 else "."),
         f"- Costs (search window): Bitget 0.06% {ev['bitget']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; "
         f"stressed {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side. Fees took {b['fee_r']:.1f}R and funding {b['fund_r']:+.1f}R.",
         f"- Price path (search window): second by second {b['total']:+.1f}R; on 1-minute bars {ev['walk_1m']['total']:+.1f}R; on the chart's candles {ev['walk_chart']['total']:+.1f}R. "
         f"TradingView's tester (chart candles, the file's 0.06%, no funding) would show about {ev['tv_view']['total']:+.1f}R with {ev['tv_view']['n']} trades; "
         f"the same costs second by second give {ev['bitget']['total'] + ev['bitget']['fund_r']:+.1f}R.",
         f"- The selection method on this timeframe, search window -> untouched period: {fmt_u(unt)}.",
         f"- Not fragile: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} neighbouring settings positive in both halves"
         + (f"; sensitive to: {', '.join(plat['fragile_inputs'])}." if plat["fragile_inputs"] else "."),
         f"- Concentration (search window): 10 biggest trades {b['top10']:+.1f}R, all others {b['without_top10']:+.1f}R; positive in {b['weeks_pos'] * 100:.1f}% of resamples of its weeks.",
         f"- Same inputs, other trade direction: {ev['other_direction']['total']:+.1f}R."]
    if p.get("trail"):
        L.append(f"- Trailing stop restarted at every candle close (if TradingView does that): search window {ev['trail_restart']['total']:+.1f}R, "
                 f"untouched {ev.get('pre_trail_restart', {}).get('total', 0):+.1f}R.")
    if replay_note(tf, p):
        L.append(f"- {replay_note(tf, p)}")
    L += ["", "| Input | Shipped | " + ("This file" if fn else "This pick") + " |", "|---|---|---|"]
    for nm, old, new in changes:
        L.append(f"| {ttl.get(nm, nm)} (`{nm}`) | {old} | {new} |")
    L += ["", "| Year | Trades | Net R | Winners | Max DD |", "|---|---|---|---|---|"]
    for y in ev.get("pre_by_year", []):
        L.append(f"| {y['year']} (untouched) | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    for y in ev["by_year"]:
        L.append(f"| {y['year']} | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    L += ["", "| Exit (search window) | Trades | Net R | Average |", "|---|---|---|---|"]
    for x in ev["by_reason"]:
        L.append(f"| {x['reason']} | {x['n']} | {x['total']:+.1f} | {x['avg']:+.2f} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(rd)
