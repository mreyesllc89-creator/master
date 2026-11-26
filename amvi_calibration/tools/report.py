"""Final step: evaluate the pick of every chart timeframe, give it a verdict, write the
calibrated .pine file (PAPER-TRADE and better only), the trade list, REPORT_tables.md (the
tables of REPORT.md) and results/TRAILING.md.

usage: python report.py [results_dir]

The verdict rules. "Holds up on the untouched period" = the pick is positive on
2021-01..2023-10 at base AND stressed costs with at least 50 trades, that result stays positive
in at least 90 % of resamples of its weeks, and the pick is not fragile (at least 60 % of its
one-step neighbours are positive in both halves of the search window). "The four tests" = the
three hold-out tests inside the search window (first half -> second, second -> first,
walk-forward) and the group test of the 25 steadiest candidates on the untouched period.

  RECOMMENDED      holds up, positive in at least 95 % of resamples of its weeks, all four
                   tests pass, and the search-window result does not lean on a few weeks either
  USABLE           holds up, positive in at least 95 % of resamples, and at least one of the
                   four tests passes
  PAPER-TRADE      holds up, but is positive in fewer than 95 % of resamples or passes none of
                   the four tests: watch it, do not fund it
  NOT RECOMMENDED  the pick does not hold up, although one of the four tests passes or the
                   search found more candidates than 95 % of luck-only worlds
  DO NOT TRADE     the pick does not hold up and none of that is true

A pick that uses the trailing stop can only be RECOMMENDED or USABLE if it is also positive
on both periods when the trailing stop starts again at every candle close (how TradingView
treats a re-sent exit order could not be checked from here).

How often luck alone earns each verdict is measured by luck.py (luck-only worlds) and printed
in the report: with these rules PAPER-TRADE or better comes up a few times in a hundred per
timeframe, USABLE about one time in a hundred or less, RECOMMENDED never in the simulations.
The rules were tightened after the statistics review and before the final run: the first
version gave PAPER-TRADE to a no-edge pick about one time in three. The neighbour share is a
screen against fragility, not evidence against luck (a lucky candidate passes it nine times in
ten).
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
ACTION = {"RECOMMENDED": "test with alerts, then trade small", "USABLE": "test with alerts first; small size at most",
          "PAPER-TRADE": "watch with alerts only; no money", "NOT RECOMMENDED": "nothing to load", "DO NOT TRADE": "nothing to load"}
WINDOW_TXT = "2023-11 to 2026-10"
RECORD_DATE = "2026-11-26"
# engine parameter -> Pine input variable (for readable names of fragile inputs)
ENGINE_TO_PINE = dict(fast="fastATRPeriod", slow="slowATRPeriod", sd="stdDevPeriod", cr="candleRangePeriod", norm="normalizationPeriod",
                      high="highVolThreshold", low="lowVolThreshold", conf="minConfluence", band="fgfBandAtr", sl="slMult", tp="tpMult",
                      max_bars="maxBars", wait="amviWait", exit_atr="exitAtrLen", trail_act="trailActMul", trail_off="trailOffMul",
                      burst_atr="fgfBurstAtr", min_aligned="fgfMinAligned", perm_candles="fgfBars", drift_bars="fgfDriftBars",
                      entry_dist_atr="fgfEntryDistAtr")


def replay_since(tf, p):
    """A setting that reads 15m candles from a higher chart can only be replayed on TradingView
    as far back as 100,000 of those candles reach (about 1,042 days). The date, or None."""
    below = {t for t in list(p["tfs"]) + [p["f_tf"]] if t < tf}
    if 15 not in below:
        return None
    return (pd.Timestamp(RECORD_DATE) - pd.Timedelta(minutes=15 * 100_000)).strftime("%Y-%m-%d")


def replay_note(tf, p):
    since = replay_since(tf, p)
    if not since:
        return None
    return (f"This setting reads 15m candles from a {make_pine.TF_NAME[tf]} chart. TradingView keeps about 100,000 candles of a lower timeframe "
            f"per request, so its tester can replay it only back to about {since}; earlier trades of this record cannot be checked there.")


def trail_robust(p, ev):
    """A trailing pick must not depend on the trailing state surviving the candle close."""
    if not p.get("trail"):
        return True
    return ev.get("trail_restart", {}).get("total", 0) > 0 and ev.get("pre_trail_restart", {}).get("total", 0) > 0


def verdict(hold, plat, ev, unt=None, p=None, luck=None):
    t1, t2, wf = hold["pass_h1_to_h2"], hold["pass_h2_to_h1"], hold["pass_walk_forward"]
    tu = bool(unt and unt.get("passed"))
    any_test = t1 or t2 or wf or tu
    many = luck is not None and luck["candidates"]["worlds_at_least"] <= 0.05
    if plat is None:
        return "DO NOT TRADE", "has no setting that made money in both halves of the last three years at base and stressed costs"
    pre, pres = ev.get("pre", {}), ev.get("pre_stress", {})
    sturdy = plat["share_both_positive"] >= 0.6
    u = pre.get("n", 0) > 0 and pre.get("total", 0) > 0
    u50 = u and pre.get("n", 0) >= 50
    us = pres.get("total", 0) > 0
    weeks = ev["base"].get("weeks_pos", 0) >= 0.95
    uw = pre.get("weeks_pos", 0) if u else 0.0
    tr = trail_robust(p or {}, ev)
    solid = sturdy and u50 and us
    inside = [nm for nm, ok in (("first half -> second", t1), ("second half -> first", t2), ("walk-forward", wf)) if ok]
    inside_txt = ("the three hold-out tests inside the last three years fail" if not inside
                  else "of the three hold-out tests inside the last three years, " + " and ".join(inside) + (" passes" if len(inside) == 1 else " pass"))
    group_txt = ("the 25 steadiest candidates did too as a group" if tu else "the candidates as a group did not pass the test there")
    made = f"made money on 2021-2023, which it was not chosen on, at base and stressed costs and in {uw * 100:.0f}% of resamples of its weeks"
    if solid and uw >= 0.95 and t1 and t2 and wf and tu and weeks and tr:
        return "RECOMMENDED", f"{made}, and all four tests pass"
    if solid and uw >= 0.95 and any_test and tr:
        return "USABLE", f"{made}; {group_txt}; {inside_txt}"
    if solid and uw >= 0.90:
        why = []
        if uw < 0.95:
            why.append(f"only in {uw * 100:.0f}% of resamples of its weeks (95% needed)")
        if not any_test:
            why.append("none of the four tests passes")
        if not tr:
            why.append("it depends on how TradingView handles the trailing stop at candle closes")
        return "PAPER-TRADE", "made money on 2021-2023, which it was not chosen on, at base and stressed costs, but " + "; ".join(why)
    why = []
    if not sturdy:
        why.append("neighbouring settings lose")
    if not u:
        why.append("it lost there" if pre.get("n", 0) > 0 else "it did not trade there")
    elif not u50:
        why.append(f"it has only {pre.get('n', 0)} trades there")
    elif not us:
        why.append("it loses there at stressed costs")
    elif uw < 0.90:
        why.append(f"its gain there stays positive in only {uw * 100:.0f}% of resamples of its weeks, so a few good weeks carry it")
    base_txt = "does not hold up on 2021-2023 (" + "; ".join(why) + ")"
    if any_test:
        return "NOT RECOMMENDED", base_txt + ", although " + ("the 25 steadiest candidates passed the test there as a group" if tu else inside_txt)
    if many:
        return "NOT RECOMMENDED", base_txt + ", although the search found more candidates than 95% of luck-only worlds"
    return "DO NOT TRADE", base_txt + ", and none of the four tests passes"


def titles(src):
    """input variable -> the label TradingView shows."""
    out = {}
    for m in re.finditer(r"^(\w+)\s*=\s*input\.\w+\((?:\"[^\"]*\"|[^,]+),\s*\"([^\"]*)\"", src, re.M):
        out[m.group(1)] = m.group(2)
    return out


def input_label(name, ttl):
    if name == "weights":
        return "the four weights"
    if name == "tdi":
        return "TDI lengths"
    return re.sub(r"\s*\(.*\)$", "", ttl.get(ENGINE_TO_PINE.get(name, name), name))


def wrap(text, width=84, indent="        ", first="STATUS:"):
    """Wrap a header paragraph: the first line starts with its tag, the others are indented."""
    words, lines, cur = text.split(), [], first
    for w in words:
        if len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = indent + w
        else:
            cur += " " + w
    lines.append(cur)
    return lines


def hours_txt(h):
    return f"{h:.0f} hours" if h < 48 else f"{h / 24:.1f} days"


def year_share(ev):
    """(share, year) of the untouched result's best year when the result is positive."""
    pre = ev.get("pre", {})
    ys = ev.get("pre_by_year", [])
    if not ys or pre.get("total", 0) <= 0:
        return None
    best = max(ys, key=lambda y: y["total"])
    return best["total"] / pre["total"], best["year"]


def share_words(ys, of="it"):
    """'77% of it in 2023'; above 100% the other years lost, and a percentage reads badly."""
    if ys[0] > 1.0:
        return f"all of {of} in {ys[1]} (the other years together lost)"
    return f"{ys[0] * 100:.0f}% of {of} in {ys[1]}"


def open_txt(st):
    """A sentence about a position still open at the end of a period, when it matters."""
    if not st.get("open_at_end") or abs(st.get("open_at_end_r", 0)) < 1.0:
        return ""
    return (f" {st['open_at_end_r']:+.1f}R of it is a trade still open at the end of the period, marked at the last close "
            f"(without it {st['total'] - st['open_at_end_r']:+.1f}R).")


def luck_line(luck):
    if not luck or "pick" not in luck:
        return ""
    k = luck["pick"]
    return (f"In luck-only worlds, where no setting has an edge, a pick chosen the same way still shows about {k['search_median']:+.0f}R here "
            f"(95th percentile {k['search_p95']:+.0f}R) and {k['untouched_median']:+.0f}R on months it was not chosen on.")


def tester_txt(ev):
    """What TradingView's Strategy Tester should roughly show for the search window."""
    tv = ev["tv_view"]
    t = (f"about {tv['n']} trades, {tv['win'] * 100:.0f}% profitable, profit factor about {tv['pf']:.1f}, net profit about {tv['pct_total']:+.0f}% "
         f"for 2023-11-01 to 2026-10-31")
    s = ev.get("tv_view_since")
    if s and s.get("n"):
        t += (f"; TradingView can replay this file only from about {s['since']}: from then about {s['n']} trades, {s['win'] * 100:.0f}% profitable, "
              f"net profit about {s['pct_total']:+.0f}%")
    return t


def header_lines(tf, v, why, ev, changes, p):
    b, pre = ev["base"], ev.get("pre", {})
    name = make_pine.TF_NAME[tf]
    grade = ORDER.index(v) + 1
    L = [f"AMVI Full MTF Strategy (direction filter, closed-candle engine): {SYMBOL} {name}"]
    after = (". After that still alerts only, no money." if v == "PAPER-TRADE"
             else ", then alerts only for about 20 trades before any money (REPORT.md, What I would do).")
    L += wrap(f"{v} (grade {grade} of 5): {ACTION[v]}. For the {name} chart of {SYMBOL} only. Not yet run on TradingView: "
              f"first check that its trade list matches (see CHECK){after}")
    L += ["-" * 85]
    ys = year_share(ev)
    conc = f" ({share_words(ys)})" if ys and ys[0] >= 0.6 else ""
    if pre.get("n"):
        L += wrap(f"{ev.get('pre_from', '2021-01-01')[:7]} to 2023-10, NOT used for choosing: {pre['total']:+.1f}R{conc}, {pre['n']} trades, "
                  f"largest drawdown {pre['dd']:.1f}R; {ev['pre_stress']['total']:+.1f}R at double commission.{open_txt(pre)}", first="RESULT:")
    else:
        L += wrap("2021-01 to 2023-10, NOT used for choosing: no trades.", first="RESULT:")
    month = (f"; {b['best_month_total'] / b['total'] * 100:.0f}% of it in one month ({b['best_month']})"
             if b["total"] > 0 and b["best_month_total"] / b["total"] >= 0.5 else "")
    L += wrap(f"2023-11 to 2026-10, used for choosing (so flattered): {b['total']:+.1f}R, {b['n']} trades, largest drawdown {b['dd']:.1f}R{month}.",
              first="       ")
    L += wrap(f"1R = the amount risked per trade = {RISK_PCT}% of the account with this file's sizing. After 0.05% commission per side, 1 tick "
              f"slippage and funding, on Binance prices. Trades are held {hours_txt(b['hold_mean_h'])} on average, {hours_txt(b['hold_max_h'])} at most.",
              first="       ")
    L += wrap(f"{v} because it {why}.", first="WHY:   ")
    reach = ("for this file not before that date, whatever the plan: the 100,000 15m candles TradingView keeps are the limit"
             if ev.get("tv_view_since") else "Deep Backtesting covers the whole period")
    L += wrap(f"TradingView's Strategy Tester (Bar detalization on its default, the former Bar Magnifier off) should show {tester_txt(ev)}. "
              f"It shows money, not R, and only the candles your plan loads ({reach}).", first="TESTER:")
    if p.get("trail"):
        L += wrap(f"this file uses the trailing stop. If TradingView starts it again at every candle close (not checked), the results are "
                  f"{ev['trail_restart']['total']:+.1f}R and {ev.get('pre_trail_restart', {}).get('total', 0):+.1f}R instead of {b['total']:+.1f}R and {pre.get('total', 0):+.1f}R.",
                  first="NOTE:  ")
    if abs(ev["walk_chart"]["total"] - b["total"]) >= 0.05:
        exits = (f" An exit differs on chart candles where stop and target lie inside one candle: walked that way this record would be "
                 f"{ev['walk_chart']['total']:+.1f}R instead of {b['total']:+.1f}R.")
    else:
        exits = " The exits should be on the same candles too."
    start = ("the date in TESTER (the first 15m candle TradingView still holds; it moves on by a day every day)" if ev.get("tv_view_since")
             else "the first candle the chart loads")
    L += wrap(f"amvi_calibration/results/trades_BTCUSDT_{name}.csv (UTC times, Binance prices): on BINANCE:BTCUSDT.P the entries must be on "
              f"the same candles and sides. Change no input. Start one week after {start}: the script needs a few hundred candles of "
              f"history before its first signal, so earlier list trades are missing in the tester.{exits} "
              f"Details: REPORT.md, section 9.", first="CHECK: ")
    L += wrap(f"amvi_calibration/REPORT.md, section 7, {name}. Record date {RECORD_DATE}. Numbers come from a Python copy of this script, "
              f"not from TradingView.", first="RECORD:")
    L += ["",
          "Same code as AMVI_FGF_Inverted_XAUUSD_15m.pine; only the title, the commission (0.06%), the",
          "sizing defaults (risk 0.5%, max 5 BTC, margin 20%, fixed quantity 0.01 BTC), the wording of",
          "tooltips and of the two quantity labels, and these inputs differ (shipped value in brackets):"]
    line = ""
    for nm, old, new in changes:
        item = f"{nm} = {new} [{old}]"
        if len(line) + len(item) + 2 > 84:
            L.append(line.rstrip(", ") + ",")
            line = ""
        line += item + ", "
    if line:
        L.append(line.rstrip(", ") + ".")
    L += ["Seconds timeframes (1s-45s) are off: they were not tested.",
          "",
          "CLOSED-CANDLE ENGINE: every decision is taken once per candle, at its close, and filled",
          "at the next open; keep Properties -> Script executions on \"On bar close\" only."]
    return L


def fmt_u(u):
    if not u or "cand_mean" not in u:
        return "not tested"
    t = (f"the {u['n_candidates']} steadiest candidates made {u['cand_mean']:+.1f}R on average ({u['cand_share_positive'] * 100:.0f}% of them made money; "
         f"positive in {u['boot_pos'] * 100:.1f}% of resamples of the months): {'pass' if u['passed'] else 'fail'}")
    if "matched_null_mean" in u:
        inv = u.get("candidates_inverted", 0)
        who = (f"Random groups with the candidates' trade directions ({inv} of {u['n_candidates']} inverted)" if inv
               else "Random groups of with-the-filter settings")
        t += f". {who} made {u['matched_null_mean']:+.1f}R on average; " + (
            "the candidates beat 95% of such groups, so the choice adds something beyond the direction" if beats_matched(u)
            else "the candidates do not beat 95% of such groups, so the choice adds nothing measurable beyond the direction")
    return t


def beats_matched(u):
    """The candidates' mean is above 95 % of random groups with their own trade directions.
    (untouched_check's passed_matched also asks for 95 % of resamples, which the main test
    already reports.)"""
    return u["cand_mean"] > u["matched_null_p95"]


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
            sections.append(f"### {name}: {v}\n\n{v} because it {why}. No file was written for this timeframe.\n")
            print(f"{name}: {v} - {why}", flush=True)
            continue
        plat = picks[0]
        p = space.normalize(plat["setting"])
        ev = F.evaluate(cs, cp, tf, p, tv_since=replay_since(tf, p))
        v, why = verdict(hold, plat, ev, unt, p, luck)
        src0, changes = make_pine.build(p, tf, ["x"], "t", "s")
        fn = None
        if v in WITH_FILE:
            # the calibrated file: only for a pick that holds up on the untouched period
            hl = header_lines(tf, v, why, ev, changes, p)
            tag = {"RECOMMENDED": "recommended", "USABLE": "usable", "PAPER-TRADE": "paper-trade only"}[v]
            short = {"RECOMMENDED": "REC", "USABLE": "USABLE", "PAPER-TRADE": "PAPER ONLY"}[v]
            src, changes = make_pine.build(p, tf, hl, f"AMVI FGF | {SYMBOL} {name} ({tag}, closed-candle)", f"AMVI BTC {name} {short}", commission_pct=0.06, symbol=SYMBOL)
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
        sections.append(section(tf, name, v, why, ev, plat, unt, p, changes, ttl, fn, luck))
        print(f"{name}: {v} - {why}", flush=True)
    md = tables(rows) + "\n\n## Settings per timeframe\n\n" + "\n".join(sections)
    open(os.path.join(out_root, "REPORT_tables.md"), "w", encoding="utf-8").write(md)
    open(os.path.join(res_dir, "TRAILING.md"), "w", encoding="utf-8").write(trailing_grids(rows))
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


def anchor(r):
    return f"#{r['name']}-" + r["verdict"].lower().replace(" ", "-")


def glance(rows):
    """The compact verdict table of the report's short version."""
    L = ["## Verdicts at a glance", "",
         "| Chart | Verdict | What it means for you | On 2021-2023, which it was not chosen on | Last three years, where it was chosen | File |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        if "ev" not in r:
            L.append(f"| {r['name']} | {r['verdict']} | nothing to load | no candidate | - | none |")
            continue
        b, pre, ev = r["ev"]["base"], r["ev"].get("pre", {}), r["ev"]
        if not pre.get("n"):
            pc = "no trades"
        else:
            pc = f"{pre['total']:+.1f}R in {pre['n']} trades"
            ys = year_share(ev)
            if pre["total"] > 0 and ev.get("pre_stress", {}).get("total", 0) <= 0:
                pc += f" ({ev['pre_stress']['total']:+.1f}R at stressed costs)"
            elif pre["total"] > 0 and pre.get("weeks_pos", 0) < 0.95:
                pc += f", positive in {pre['weeks_pos'] * 100:.0f}% of resamples"
            if ys and ys[0] >= 0.6:
                pc += f"; {share_words(ys)}"
        L.append(f"| [{r['name']}]({anchor(r)}) | {r['verdict']} | {ACTION[r['verdict']]} | {pc} | {b['total']:+.1f}R in {b['n']} trades | "
                 + (f"`{r['file']}`" if r.get("file") else "none") + " |")
    return L


def trailing_grids(rows):
    L = ["# Trailing stop: every activation and offset, per chart timeframe", "",
         "The same settings (a random sample of the search: 300 per timeframe, 200 on 5m and below) with each Trail Activation x Trail Offset",
         "pair, nothing else changed, on the second-by-second price path. Each cell: share of the settings positive after costs in both halves",
         "of the search window (2023-11 to 2026-10). Rows = Trail Activation, columns = Trail Offset, both in multiples of the exit ATR.",
         "Cells differ by a few points from noise alone (a cell is 200 or 300 settings). Summary and reading: REPORT.md, section 5.", ""]
    for r in rows:
        t = r.get("trailing")
        if not t:
            continue
        offs = sorted({x["off"] for x in t["grid"]})
        acts = sorted({x["act"] for x in t["grid"]})
        L += [f"## {r['name']} (trailing off: {t['base_share_both'] * 100:.1f}%)", "",
              "| Activation \\ Offset | " + " | ".join(f"{o:g}" for o in offs) + " |", "|---|" + "---|" * len(offs)]
        for a in acts:
            cells = []
            for o in offs:
                x = next(y for y in t["grid"] if y["act"] == a and y["off"] == o)
                cells.append(f"{x['share_both'] * 100:.1f}%")
            L.append(f"| {a:g} | " + " | ".join(cells) + " |")
        L.append("")
    return "\n".join(L)


def tables(rows):
    L = glance(rows) + ["", "## Results by timeframe", "",
         "Net of 0.05% per side, 1 tick slippage and funding. R = amount risked per trade; PF = profit factor (gross profit / gross loss);",
         "DD = largest drawdown. The untouched period comes first because the pick was not chosen on it; the search-window figure is the best",
         "of thousands of settings and is flattered by that choice.", "",
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

    elig = sum(r["hold"]["eligible_rows"] for r in rows)
    tried = sum(r["hold"]["rows"] for r in rows)
    L += ["", "## What the search itself says", "",
          "Best 40 = the 40 steadiest settings of one part of the search window, scored on another part. A test passes when their mean is",
          "positive, above 95% of random groups of 40, and stays positive in 95% of resamples of the months. The last column is the same test",
          "for the 25 steadiest candidates (12 on 1m), chosen on the whole search window and scored on the untouched period.",
          f"The three \"Positive\" columns are shares of the settings with at least 30 trades in each half and a trade in at least 60% of its",
          f"months: {elig:,} of the {tried:,} tried. \"Beaten\" in the last column: the candidates' mean is above 95% of random groups with",
          "their own trade directions.", "",
          "| Chart | Settings tried | Positive before costs | Positive after costs | Positive in both halves | First half -> second (best 40) | Second -> first | Walk-forward (two years -> the third) | Search window -> untouched period (25 steadiest candidates) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        h, u = r["hold"], r.get("unt")

        def cell(t, ok):
            if not t:
                return "n/a"
            return f"{t['top_mean']:+.1f}R, {t['top_pos'] * 100:.0f}% positive, {t['boot_pos'] * 100:.0f}% of resamples ({'pass' if ok else 'fail'})"
        uc = "n/a"
        if u and "cand_mean" in u:
            uc = f"{u['cand_mean']:+.1f}R, {u['cand_share_positive'] * 100:.0f}% positive, {u['boot_pos'] * 100:.1f}% of resamples ({'pass' if u['passed'] else 'fail'})"
            if "matched_null_mean" in u:
                uc += f"; random settings of the same directions {u['matched_null_mean']:+.1f}R ({'beaten' if beats_matched(u) else 'not beaten'})"
        elif u:
            uc = "no candidates"
        L.append(f"| {r['name']} | {h['rows']:,} | {h['gross_share_positive'] * 100:.0f}% | {h['share_positive_total'] * 100:.0f}% | {h['share_positive_both_halves'] * 100:.1f}% | "
                 f"{cell(h['h1_to_h2'], h['pass_h1_to_h2'])} | {cell(h['h2_to_h1'], h['pass_h2_to_h1'])} | {cell(h['walk_forward'], h['pass_walk_forward'])} | {uc} |")

    if any(r.get("unt") and "random_with_filter" in r["unt"] for r in rows):
        L += ["", "## The two trade directions on data the search never saw", "",
              "400 random settings of the search per timeframe (at least 30 trades in each half of the search window), run over the untouched",
              "period and split by trade direction; then the same split on the search window for all settings of the search with at least 30",
              f"trades in each half ({sum(sum(v['rows'] for v in direction(r).values()) for r in rows):,} of the {tried:,}).",
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
              "To see what luck alone produces, the search results were scrambled 1,000 times per chart: months were drawn at random and, in",
              "each month, the before-cost results of all settings were flipped together by one coin toss. No setting has an edge after that,",
              "but fees, trade counts and the similarity between settings stay as they are. These are the luck-only worlds. A real count inside",
              "the luck-only range is no evidence of an edge.", "",
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
        L += ["", "What a pick is worth when nothing is there: the steadiest candidate of each luck-only world, on the months it was chosen on and",
              "on further months it was not chosen on, and how often luck alone meets the conditions of each verdict (the neighbour test of",
              "section 3 taken as passed, months standing in for weeks).", "",
              "| Chart | Luck's pick where it was chosen (median, 95th percentile) | Luck's pick on months it was not chosen on | Positive there | Positive there at base and stressed costs with 50+ trades | Luck passes at least one of the four tests | Luck earns PAPER-TRADE or better | USABLE or better | RECOMMENDED |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            k = r.get("luck")
            if not k or "pick" not in k:
                continue
            pk, lp = k["pick"], k["luck_pass"]
            L.append(f"| {r['name']} | {pk['search_median']:+.1f}R, {pk['search_p95']:+.1f}R | {pk['untouched_median']:+.1f}R | {lp['pick_pos'] * 100:.0f}% | {lp['pick_ok'] * 100:.0f}% | "
                     f"{lp['any'] * 100:.1f}% | {lp['paper'] * 100:.1f}% | {lp['usable'] * 100:.1f}% | {lp['recommended'] * 100:.1f}% |")

    L += ["", "## The shipped inputs on BTCUSDT", "",
          "The inputs of AMVI_FGF_Inverted_XAUUSD_15m.pine unchanged (calibrated for gold on 15m: 60m filter, trade direction Inverted), run on",
          "each BTC chart timeframe. On the 2m and 10m charts the 15m AMVI does not line up with the chart's candles; the numbers there are what",
          "a reloaded chart shows.", "",
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
          "moved more per candle on the untouched period, so the same commission was a smaller share of the risk then.", "",
          "| Chart | Search window: median ATR(14) as % of price | Round-trip commission in R | Untouched period: median ATR(14) | Round-trip commission in R |",
          "|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {r['atr_pct']:.3f}% | {r['fee_r']:.2f}R | {r['atr_pre']:.3f}% | {r['fee_pre']:.2f}R |")

    if any(r.get("trailing") for r in rows):
        L += ["", "## Trailing stop", "",
              "The same settings (a random sample of the search: 300 per timeframe, 200 on 5m and below) with the trailing stop off and with",
              "each of the 42 Trail Activation x Trail Offset pairs, nothing else changed, on the second-by-second price path. \"Both halves\" =",
              "share of the settings positive after costs in both halves of the search window. The best of 42 pairs is partly the luckiest of",
              "42, so it was chosen on one random half of the settings and is read on the other half. The last three columns are for a tight",
              "pair (0.5 / 0.5 ATR): what a walk on the chart's candles shows, how much profit per trade that invents, and the real figure.", "",
              "| Chart | Trailing off: both halves | With trailing: median of the 42 pairs | Pairs above \"off\" | Best pair chosen on half the settings (activation / offset) | On the other half: with it vs trailing off | Shipped pair 1.5 / 1.0 | It makes a setting better / leaves it unchanged / worse | Tight pair on chart candles | Profit it invents per trade | Tight pair second by second |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
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
                     f"{tight['share_both_chart'] * 100:.1f}% | {tight['flatter_chart']:+.2f}R | {tight['share_both'] * 100:.1f}% |")
        L += ["", "All 42 pairs for every timeframe: `results/TRAILING.md`."]

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


def section(tf, name, v, why, ev, plat, unt, p, changes, ttl, fn, luck=None):
    b, pre = ev["base"], ev.get("pre", {})
    lev = RISK_PCT / b["avg_risk_pct"] if b.get("avg_risk_pct") else 0
    file_txt = (f"File: `presets/{fn}` ({ACTION[v]})." if fn else
                "No file was written. The inputs below are listed only so that the result can be reproduced; they are not a setup to trade.")
    ys = year_share(ev)
    conc = ""
    if ys and ys[0] > 1.0:
        conc = f" All of that result came in {ys[1]}; the other years together lost."
    elif ys and ys[0] >= 0.6:
        conc = f" {ys[0] * 100:.0f}% of that result came in {ys[1]}."
    inside_day = max(b["hold_max_h"], pre.get("hold_max_h", 0)) <= 24.5
    L = [f"### {name}: {v}", "", f"{v} because it {why}. {file_txt}", "",
         f"- On data it was not chosen on (untouched {ev.get('pre_from', '2021-01-01')[:7]} to 2023-10): {F.line('', pre)[2:] if pre.get('n') else 'no trades'}"
         + (f"; stressed costs {ev['pre_stress']['total']:+.1f}R; positive in {pre.get('weeks_pos', 0) * 100:.0f}% of resamples of its weeks.{conc}{open_txt(pre)}" if pre.get("n") else "."),
         f"- Where it was chosen (search window): {F.line('', b)[2:]}; halves {b['h1']:+.1f} / {b['h2']:+.1f}R. "
         f"The best month ({b['best_month']}) made {b['best_month_total']:+.1f}R of it.{open_txt(b)} " + luck_line(luck),
         f"- Holding time: {hours_txt(b['hold_mean_h'])} on average and {hours_txt(b['hold_max_h'])} at most in the search window"
         + (f" ({hours_txt(pre['hold_mean_h'])} and {hours_txt(pre['hold_max_h'])} on the untouched period)" if pre.get("n") else "")
         + (": inside your lab's holding limit (hours to one day)." if inside_day else ": longer than your lab's holding limit (hours to one day)."),
         f"- With {RISK_PCT}% of equity at risk per trade and the position capped at 5x equity (the calibrated files' sizing), the search-window result is about {b['pct_total']:+.1f}% in three years "
         f"with a worst drawdown of about {b['pct_dd']:.1f}% (no compounding)"
         + (f", and the untouched period about {pre['pct_total']:+.1f}% with a worst drawdown of {pre['pct_dd']:.1f}%" if pre.get("n") else "")
         + f". The stop is {b['avg_risk_pct']:.2f}% of price on average, so {RISK_PCT}% risk asks for about {lev:.1f}x leverage"
         + (f"; the 5x cap cuts the position on {b['cap_share'] * 100:.0f}% of the trades, which then risk less than {RISK_PCT}%." if b.get("cap_share", 0) > 0.005 else "."),
         f"- Costs (search window): Bitget 0.06% {ev['bitget']['total']:+.1f}R; no costs {ev['no_cost']['total']:+.1f}R; "
         f"stressed {ev['stress']['total']:+.1f}R; break-even commission {ev['breakeven_fee_pct']:.3f}% per side. Fees took {b['fee_r']:.1f}R and funding {b['fund_r']:+.1f}R.",
         f"- Price path (search window): second by second {b['total']:+.1f}R; on 1-minute bars {ev['walk_1m']['total']:+.1f}R; on the chart's candles {ev['walk_chart']['total']:+.1f}R.",
         f"- On TradingView (chart candles, 0.06% commission, no funding) the Strategy Tester should show {tester_txt(ev)}.",
         f"- The selection method on this timeframe, search window -> untouched period: {fmt_u(unt)}.",
         f"- Not fragile: {plat['share_both_positive'] * 100:.0f}% of {plat['neighbours']} neighbouring settings positive in both halves"
         + (f"; sensitive to: {'; '.join(input_label(x, ttl) for x in plat['fragile_inputs'])}." if plat["fragile_inputs"] else "."),
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
        lab = "2023 (Jan-Oct, untouched)" if y["year"] == 2023 else f"{y['year']} (untouched)"
        L.append(f"| {lab} | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    for y in ev["by_year"]:
        lab = {2023: "2023 (Nov-Dec)", 2026: "2026 (Jan-Oct)"}.get(y["year"], str(y["year"]))
        L.append(f"| {lab} | {y['n']} | {y['total']:+.1f} | {y['win'] * 100:.0f}% | {y['dd']:.1f} |")
    L += ["", "| Exit (search window) | Trades | Net R | Average |", "|---|---|---|---|"]
    for x in ev["by_reason"]:
        L.append(f"| {x['reason']} | {x['n']} | {x['total']:+.1f} | {x['avg']:+.2f} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    rd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    run(rd)
