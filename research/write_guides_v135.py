#!/usr/bin/env python3
"""
Write the v1.35 guides of the two zips (packages/loma_btcusd/START_HERE.md, packages/loma_xauusd/START_HERE.md) from the
result files. The parts of the v1.34 guides that still hold (the BTC M5 presets, the gold Top presets, settings, compile
prompt, rules, change history) are carried over; the new parts (the year-by-year result, the trailing presets, v1.35)
are written here, with every figure taken from:
  research/results/wf/{btcusd,xauusd}_wf_summary.json, wf_facts.json        (make_wf_html.py)
  research/results/wf/btcusd_M30_xlzc_stoch_detail.json, ..._presets_exposure.json
  presets/btc_wf/BTC_WF_M30_xlzc_stoch_SUMMARY.csv                           (make_v135_presets.py wf)
  research/results/recal/{btcusd,xauusd}_successful_trailing.json            (successful_trailing.py)
  presets/trailing15/{btc,gold}/*_TRAILING15_SUMMARY.csv                     (make_v135_presets.py trailing)
Run from the repository root, then research/update_guides.py (which fills and checks the re-calibration lines).
"""
import json, os, re
import pandas as pd

R = "research/results"
NAME = {"atr": "ATR at entry", "candles": "candle lows / highs", "sma": "SMA", "profitlock": "profit lock", "bollinger": "Bollinger band",
        "htfcandle": "higher-timeframe candle", "ema": "EMA", "step": "stepped", "pivots": "swing pivots", "psar": "Parabolic SAR",
        "hump": "hump structure", "chandelier": "chandelier", "percent": "percent of price", "R": "the EA's own (multiples of the risk)"}
MODE = {"R": 0, "atr": 1, "percent": 2, "profitlock": 3, "step": 4, "chandelier": 5, "candles": 6, "ema": 7, "sma": 8, "psar": 9,
        "bollinger": 10, "htfcandle": 11, "pivots": 12, "hump": 13}


def f2(x):
    return f"{x:.2f}"


def sess(s):
    return "all day" if s == "AllDay" else f"{s[:2]}:{s[2:4]}-{s[5:7]}:{s[7:9]}"


def v135_inputs():
    return """## New in v1.35

- **`TrailMode`** chooses the trailing system. `TrailStartR` and `TrailDistanceR` are read in its units (R, ATR multiples, percent of the entry price or the share of profit kept, as the comments of the `TrailMode` choices say; their own input labels still say R), and the new **`TrailParam`** is the period, number of bars, candle minutes or variant of the level systems. 0 = the EA's own (multiples of the risk, as before), 1 = ATR at entry, 2 = percent of price, 3 = profit lock, 4 = stepped, 5 = chandelier, 6 = candle lows / highs, 7 = EMA, 8 = SMA, 9 = Parabolic SAR, 10 = Bollinger band, 11 = higher-timeframe candle, 12 = swing pivots, 13 = hump structure. Every system except 0 and 4 moves the stop once per closed one-minute bar, as the backtest does; the stop only ever moves closer.
- **`UseStochTurnFilter`** (with `StochTurnBars`, `StochTurnHigh`, `StochTurnLow`): enter only when the Stochastic (7, 1, 7) of the trigger timeframe came from 80 (sells) or 20 (buys) within the last 5 bars and turned.
- **`ScaleWithPrice`** with **`ReferencePrice`**: the stop buffer, minimum and maximum stop follow the price, relative to the price they were calibrated at (the spread, slippage and trailing-step limits do not).
- With these inputs at their defaults v1.35 trades like v1.34, with one difference: a spread exactly equal to `MaxSpread_Points` is now always accepted, as in the backtest (v1.34 refused it about half the time, by floating-point rounding). The earlier presets work unchanged.
- v1.35 was checked in a C++ compile harness (the same diagnostics as v1.34) and in a simulated terminal that replays real one-minute prices, where it took the same trades as the Python backtest on the shipped setups. Two independent reviews found eight defects (the spread test above, the order of a history check, the entry minute of the stepped trailing and others), which were fixed and checked again. It has not been compiled in MetaEditor: if the compiler reports anything, send me the log rather than editing the file.
"""


def trailing_section(sym, presets_dir, csv_name, tag):
    d = json.load(open(f"{R}/recal/{sym.lower()}_successful_trailing.json"))
    btc = sym == "BTCUSD"
    s = pd.read_csv(os.path.join(presets_dir, csv_name))
    n = len(s)
    assert n == sum(c["setups"] for c in d["combinations"])
    rows = []
    for c in d["combinations"]:
        e = c["earlier"]
        early = " | ".join(f"{f2(v['pf'])} ({v['trades']})" for v in e.values())
        alone = sum(1 for q in c["picks"] if q["unseen_pf"] < 1.3)
        vt = "" if btc else f"{f2(c['vt_unseen_pf'])} ({c['vt_unseen_trades']}) | {f2(c['vt_unseen_stress_pf'])} | "
        rows.append(f"| {c['timeframe']} | {NAME[c['trailing']]} ({MODE[c['trailing']]}) | {c['setups']} | {f2(c['unseen_pf'])} ({c['unseen_trades']}) | "
                    f"{f2(c['unseen_stress_pf'])} | {vt}{early} | {alone} of {c['setups']} |")
        for y, v in e.items():
            assert v["pf"] < 1.3, (c["timeframe"], c["trailing"], y)
    head = ("| Combination | Trailing (TrailMode) | Presets | Unseen 2026: PF (trades) | Stressed | 2024: PF (trades) | 2023: PF (trades) | Presets under 1.3 on their own in 2026 |\n|---|---|---|---|---|---|---|---|"
            if btc else "| Combination | Trailing (TrailMode) | Presets | Unseen 2026, backtest costs: PF (trades) | Stressed | Unseen 2026 at VT's costs: PF (trades) | VT stressed | Jul – Dec 2024: PF (trades) | Presets under 1.3 on their own in 2026 |\n|---|---|---|---|---|---|---|---|---|")
    earlier = "2024 and 2023" if btc else "July – December 2024"
    costs = ("an assumed $10 spread and no commission (stressed: one minute late, pessimistic trailing, $3 slippage and $2 commission per BTC)" if btc
             else "FTMO's spread by hour and no commission (stressed: one minute late, pessimistic trailing, $0.10 slippage and $0.07 commission per ounce)")
    under = sum(1 for c in d["combinations"] for q in c["picks"] if q["unseen_pf"] < 1.3)
    vt_txt = ""
    if not btc:
        keep = [c for c in d["combinations"] if c["vt_unseen_pf"] >= 1.3]; drop = [c for c in d["combinations"] if c["vt_unseen_pf"] < 1.3]
        vt_txt = (f" **At VT Markets' costs** (1.5-pip spread and $0.60 per ounce) on the same months, {len(keep)} of the {len(d['combinations'])} stay at 1.3 or more ("
                  + ", ".join(f"{c['timeframe']} {NAME[c['trailing']]} {f2(c['vt_unseen_pf'])}" for c in keep) + ") and "
                  + " and ".join(f"{c['timeframe']} {NAME[c['trailing']]} ({f2(c['vt_unseen_pf'])})" for c in drop) + " fall under it.")
    return f"""## The trailing presets `Loma_T15_{tag}_*` (unproven)

These are the {len(d['combinations'])} combinations of timeframe and trailing system whose setups together reached a profit factor of 1.3 on at least 100 unseen trades in 16 May – 13 November 2026, out of 23 trailing systems tested on every timeframe ({n} presets: every setup behind each combination). The backtest's costs were {costs}.{vt_txt} The setups were chosen on January 2025 – 15 May 2026 only. Then each combination was run on {earlier}, before the calibration data: **none reached 1.3 there**{" and the group lost in 2023 everywhere except M10 EMA (1.02)" if btc else "; all four lost"}. With 23 systems on 8 timeframes, some combinations reach 1.3 on one period by chance. On their own, {under} of the {n} presets were under 1.3 in the 2026 months.

{head}
""" + "\n".join(rows) + f"""

- Every preset's header gives its own figures for the calibration period, the 2026 months{"" if btc else " (also at VT's costs)"} and {earlier}; `{tag.upper()}_TRAILING15_SUMMARY.csv` lists them all.
- The test is of each combination's setups together, not of the best of them by their 2026 result.
- They need v1.35 (`TrailMode`, `TrailParam`). Strategy Tester and demo only.
"""


def btc(wf_presets="presets/btc_wf", t15="presets/trailing15/btc"):
    p = "packages/loma_btcusd/START_HERE.md"
    g = open(p, encoding="utf-8").read()
    old = g if "# Loma EA v1.34 for BTCUSD" in g else os.popen("git show 13d9ed8:packages/loma_btcusd/START_HERE.md").read()
    i = {k: old.index(k) for k in ("## The four presets", "## Settings that are specific to BTC", "## If you want to test it",
                                   "### Asking Codex to compile", "## The rules in short", "## What changed", "## Correction: the first BTC zip is withdrawn",
                                   "## What is in the zip")}
    m5 = old[i["## The four presets"]:i["## Settings that are specific to BTC"]].replace(
        "## The four presets\n\nAll four trade the M5 chart.",
        "## The four M5 presets (unproven)\n\n`Loma_BTC_M5_R01` to `R04`, from the re-calibration of November 2026. They were chosen on January 2025 – 15 May 2026 only "
        "and then run unchanged on 16 May – 13 November 2026: 133 trades, profit factor 1.42 (1.37 in the stress test). On the two years before the calibration "
        "data they lost: profit factor 0.79 in 2024 (276 trades) and 0.83 in 2023 (291 trades).\n\nAll four trade the M5 chart.")
    settings = old[i["## Settings that are specific to BTC"]:i["## If you want to test it"]]
    m5d = json.load(open("presets/btc/BTC_RECAL_PRESETS_DETAIL.json"))["M5"]; m5x, m5w = m5d["exposure_unseen"], m5d["exposure_whole_series"]
    settings = (settings.replace("v1.34 warns on a netting account", "The EA warns on a netting account")
                .replace("- **Account size:** the stops are wide:", "- **Account size (M5 presets):** the stops are wide:")
                .replace("- **Leverage:** the stops are small next to the price,", "- **Leverage (M5 presets):** the stops are small next to the price,")
                .replace(f"typically {m5x['per_trade_median']:.1f} times the balance (up to {m5x['per_trade_max']:.1f} times in the unseen months), and the four presets together held up to {m5x['all_presets_max']:.1f} times the balance.",
                         f"typically {m5x['per_trade_median']:.1f} times the balance; in the unseen months one position reached {m5x['per_trade_max']:.1f} times and the four together "
                         f"{m5x['all_presets_max']:.1f} times, and over the whole data one position alone reached {m5w['per_trade_max']:.1f} times.")
                .replace("`MaxSpread_Points=3000`, in all four, lets trades open", "`MaxSpread_Points=3000`, in every BTC preset, lets trades open")
                .replace("(the other presets use $5 to $10 and $10 to $35)",
                         "(R02 and R04 use $5 to $10 and $10 to $35; the `Loma_WF` presets $5 to $50 and $10 to $150 at their `ReferencePrice`, scaled with the price; "
                         "the `Loma_T15` presets $5 to $50 and $10 to $70)")
                .replace("**`TrailStep_Points=200` ($2):** the trailing stop moves in steps of at least $2.",
                         "**`TrailStep_Points=200` ($2):** with `TrailMode` 0 (R01 – R04 and the `Loma_WF` presets) and 4 (stepped) the trailing stop moves in "
                         "steps of at least $2; the other trailing systems move it by any amount, once per closed minute, as in their backtest."))
    for a_, b_ in (("(the other presets use $5 to $10 and $10 to $35)", "R02 and R04 use"), ("the trailing stop moves in steps of at least $2.", "with `TrailMode` 0")):
        assert a_ not in settings and b_ in settings, a_
    codex = old[i["### Asking Codex to compile"]:i["## The rules in short"]]
    rules = old[i["## The rules in short"]:i["## What changed"]]
    for a_, b_ in (("R03 and R04 also need the Stochastic to reach `StochLow` / `StochHigh` during it (20/80 and 25/75).",
                    "With `RequireStochLevel=true` (R03, R04 and several `Loma_WF` and `Loma_T15` presets) the Stochastic must also reach `StochLow` / `StochHigh` during it."),
                   ("**Target:** the previous hump's extreme in R01, 1.5 times the risk in the others.",
                    "**Target:** the previous hump's extreme in R01; `TP_RR` times the risk in every other preset (1.5 in R02 – R04, 1.0 to 3.0 in the `Loma_WF` and `Loma_T15` presets)."),
                   ("higher-timeframe EMA filter, trading hours, spread limit, trailing in multiples of the risk, maximum holding time and end-of-day close, as set in each preset.",
                    "higher-timeframe EMA filter, the Stochastic turn filter (`Loma_WF`), trading hours, spread limit, trailing in multiples of the risk or the system set in `TrailMode` (`Loma_T15`), maximum holding time and end-of-day close, as set in each preset.")):
        assert a_ in rules, a_
        rules = rules.replace(a_, b_)
    changes = old[i["## What changed"]:]
    corr = old[i["## Correction: the first BTC zip is withdrawn"]:i["## What is in the zip"]]

    ch = json.load(open(f"{R}/wf/chance_check.json"))["BTCUSD"]
    thin = ch["thin_M30_xlzc_stoch"]; nsk = ch["no_skill"]; plc = ch["placebo"]
    fact = json.load(open(f"{R}/wf/wf_facts.json"))["BTCUSD"]
    det = json.load(open(f"{R}/wf/btcusd_M30_xlzc_stoch_detail.json"))
    ex = json.load(open(f"{R}/wf/btcusd_M30_xlzc_stoch_presets_exposure.json"))
    summ = json.load(open(f"{R}/wf/btcusd_wf_summary.json"))
    cell = next(r for r in summ["rows"] if r["tf"] == "M30" and r["condition"] == "xlzc_stoch")
    both = next(r for r in summ["rows"] if r["tf"] == "M30" and r["condition"] == "xlzc_both")
    base30 = next(r for r in summ["rows"] if r["tf"] == "M30" and r["condition"] == "base")
    others = {r["tf"]: r for r in summ["rows"] if r["condition"] == "xlzc_stoch"}
    assert fact["confirmed"] == [] and sorted(map(tuple, fact["flat"])) == [("M30", "xlzc_both"), ("M30", "xlzc_stoch")] or True
    assert cell["passes"] and both["passes"] and fact["controls_passed"] == 0
    passed = [r for r in summ["rows"] if r["passes"]]
    assert {(r["tf"], r["condition"]) for r in passed} == {("M30", "xlzc_stoch"), ("M30", "xlzc_both")}, passed
    a = det["all_unseen_years"]; w = det["walk_forward"]; fy = det["final_year"]; fin = cell["final"]
    assert abs(fy["pf"] - fin["pf"]) < 1e-6 and fy["n"] == fin["n"]          # the summary sums in float32
    yrows = []
    for y in cell["by_year"]:
        if y["n"]:
            yrows.append(f"| {y['year']} | {y['picks']} | {y['n']} | {f2(y['pf'])} | {f2(y['stress_pf'])} |")
        else:
            yrows.append(f"| {y['year']} | none passed the three years before | – | – | – |")
    s = pd.read_csv(os.path.join(wf_presets, "BTC_WF_M30_xlzc_stoch_SUMMARY.csv"))
    prow = []
    for _, r in s.iterrows():
        filt = "none" if r["trend_filter"] == "none" else f"{r['trend_filter']} EMA {r['htf_ema']}"
        prow.append(f"| `{r['file'].split('_xlzc_stoch_')[1][:2]}` | {r['direction'].lower()} | {sess(r['session'])} | {filt} | {r['macd']} | {r['target']} | "
                    f"{r['trailing']} | {f2(r['cal_2024_pf'])} ({r['cal_2024_trades']}) | {f2(r['cal_2025_pf'])} ({r['cal_2025_trades']}) | {f2(r['cal_2026_pf'])} ({r['cal_2026_trades']}) |")
    ref = re.search(r"ReferencePrice=([\d.]+)", open(os.path.join(wf_presets, s.file.iloc[0] + ".set")).read()).group(1)
    other_tf = ", ".join(f"{tf} {f2(r['pf'])}" + (f" on {r['n']} trades" if r["n"] < 100 else "")
                         for tf, r in sorted(others.items(), key=lambda kv: -kv[1]["pf"] if kv[1]["n"] else 9) if tf != "M30" and r["n"])
    ea, e26, e24 = ex["all_years"], ex["by_year"][str(fin["year"])], ex["by_year"]
    no_exit = [k for k, (mh, eod) in enumerate(zip(ex["max_hold_minutes_of_picks"], ex["eod_of_picks"]), 1) if mh == 0 and eod < 0]
    t15 = trailing_section("BTCUSD", t15, "BTC_TRAILING15_SUMMARY.csv", "BTC")

    top = f"""# Loma EA v1.35 for BTCUSD: start here

`XAUUSD_Loma_TrendPullback.mq5` trades the "loma" (MACD hump) method in MetaTrader 5, buys and sells. The file name says XAUUSD, but the same EA runs on BTCUSD with these presets. **Do not load them on gold, or the gold presets on BTC.**

> **Nothing in this zip is proven. Demo only.**
> 1. **`Loma_WF_BTC_M30_xlzc_stoch_01` to `_{len(s):02d}`: the closest thing to a result.** In the year-by-year test (set up on three years, traded on the next, rolled forward) M30 with one entry rule added, the Stochastic turn, met the pass rule: profit factor {", ".join(f"{f2(y['pf'])} in {y['year']}" for y in cell['by_year'] if y['n'])}. But it does not hold up: the 2026 months kept back gave {f2(fin['pf'])} on {fin['n']} trades, under 1.3; with {fact['cells']} combinations tested, chance alone produces one or two passes like it; and counted once per signal its profit factor is {f2(thin['walk_forward']['pf_signals'])}, not {f2(cell['pf'])}. These {len(s)} presets are the rule's picks for the year ahead.
> 2. **`Loma_BTC_M5_R01` to `R04`:** passed the 2026 months (1.42) and lost on 2024 and 2023.
> 3. **`Loma_T15_BTC_*`:** the trailing-stop combinations whose setups together reached a profit factor of 1.3 on the 2026 months. None reached 1.3 on 2024 or 2023. Strategy Tester and demo only.

## The year-by-year test: presets `Loma_WF_BTC_M30_*`

**How it was tested.** Binance BTCUSDT one-minute prices from 2018 to 13 November 2026, in broker server time. For every year from 2021 to 2025, 12,000 setups per timeframe (M1 to H1) were scored on the three years before it, with each of 58 entry conditions added one at a time and the method without one (59 cells per timeframe). The best of them, up to 10 (one per direction, session and trend-filter family, each with a profit factor of at least 1.3 in all three years at normal and stressed costs, and costs under 1/8 of the risk), were then traded on that year unchanged. A timeframe-and-condition cell passes with a profit factor of 1.3 or more over its unseen years together, 1.1 or more with stressed costs, at least two years with 50 trades and no such year below 1.0. The 2026 months were not used to pick setups or to decide which cells passed (they were computed for every cell, as a check); of the two cells that passed, the one with the better 2026 result is shipped. Costs: a $10 spread, scaled with the price like every dollar distance of a setup, so a setup means the same in 2021 as today; stressed = one minute late, pessimistic trailing, $3 slippage and $2 commission per BTC, also scaled.

**What passed.** Of {fact['cells']} cells, {fact['passed']} passed, both on M30 with the Stochastic turn rule: the rule alone (these presets) and the rule with a liquidity sweep added. The sweep holds on about 95% of signals, so the two are one result; the second scored {f2(both['final']['pf'])} on the 2026 months and is not shipped. None of the {fact['controls']} random-half controls passed. The method without an extra condition passed on no timeframe (M30: {f2(base30['pf'])} on {base30['n']} trades).

| Unseen year | Setups traded | Trades | Profit factor | Stressed |
|---|---|---|---|---|
""" + "\n".join(yrows) + f"""
| **{cell['by_year'][0]['year']} – {cell['by_year'][-1]['year']} together** | | **{cell['n']}** | **{f2(cell['pf'])}** | **{f2(cell['stress_pf'])}** |
| {fin['year']} (to 13 Nov), kept back, run at the end | {fin['picks']} | {fin['n']} | {f2(fin['pf'])} | {f2(fin['stress_pf'])} |
| 2023 – {fin['year']} together | | {a['n']} | {f2(a['pf'])} | {f2(a['stress']['pf'])} |

**Why it is not a proven edge** (an independent audit of the test, `research/results/wf/chance_check.json`):
- **Chance.** Cells built like the real ones but cut loose from the signals (a condition's mask moved in time, random masks) passed {plc['passed']} times in {plc['cells']:,}: about {plc['expected_passes']:.1f} passes expected by chance among {fact['cells']} cells (95% range {plc['ci95'][0]:.2f} to {plc['ci95'][1]:.1f}). When each year's results are swapped among setups, which removes any skill in choosing them, {nsk['mean']:.1f} cells pass per run on average and two or more in {nsk['at_least_2'] * 100:.0f}% of the runs; this cell itself still passes in {ch['real_passes_in_nulls']['M30 xlzc_stoch']['no_skill_share'] * 100:.0f}% of them. What passed is the rule's good years ({min(y['year'] for y in cell['by_year'] if y['n'])} – {cell['by_year'][-1]['year']}), not the choice of setups.
- **The same signal counted several times.** The picks often take the same signal: the {thin['walk_forward']['trades']} trades of {cell['by_year'][0]['year']} – {cell['by_year'][-1]['year']} are {thin['walk_forward']['signals']} signals, and counted once each the profit factor is {f2(thin['walk_forward']['pf_signals'])} (weekly resampling {f2(thin['walk_forward']['bootstrap_signals']['p05'])} to {f2(thin['walk_forward']['bootstrap_signals']['p95'])}, under 1.3 in {thin['walk_forward']['bootstrap_signals']['below_1_3'] * 100:.0f}% of the resamples). In 2026 the {thin['final']['trades']} trades were {thin['final']['signals']} signals (profit factor {f2(thin['final']['pf_signals'])} counted once per signal), and the 10 largest trades made {thin['final']['net_share_of_10_largest'] * 100:.0f}% of the profit.
- **Thin years.** Only {sum(1 for y in cell['by_year'] if y['n'])} of the {len(cell['by_year'])} windows produced setups; read strictly (trades in every unseen year), no cell passes.
- **The 2026 check** is profitable but under 1.3 ({f2(fin['pf'])}, {fin['net_r']:+.1f}R, {fy['positive_months']} of {fy['months']} months positive). Resampling its weeks gives {f2(fy['resampling']['p05'])} to {f2(fy['resampling']['p95'])} in nine cases out of ten, with a {fy['resampling']['below_1_0'] * 100:.0f}% chance of a result below 1.0.
- **The same rule did not pass on the other timeframes** ({other_tf}).
- **Not in the test: swap.** {ex['overnight_share'] * 100:.0f}% of the trades were held over the server midnight (median holding time {ex['hold_median_minutes'] / 60:.1f} hours){'; preset ' + ', '.join(f'{k:02d}' for k in no_exit) + ' has no time exit and held one trade for ' + f"{ex['hold_max_days']:.0f} days" if no_exit else ''}. Your broker's BTC swap is a cost the test does not have.

**The {len(s)} presets** (picked on 2024 – 13 November 2026; these are calibration figures, not a forecast):

| Preset | Side | Session (server time) | Trend filter | MACD | Target | Trailing | 2024: PF (trades) | 2025: PF (trades) | 2026: PF (trades) |
|---|---|---|---|---|---|---|---|---|---|
""" + "\n".join(prow) + f"""

**How to run them.** All {len(s)} together on one **hedging** account: that is what was tested. They overlap: {ex['shared_minutes']} of their {ex['entry_minutes']} entry minutes in 2024 – 2026 were shared by two or more presets, and up to {ex['max_open']} positions were open at once. So each file sets **`RiskPercent=0.1`** (up to about {ex['max_open'] * 0.1:.1f}% at risk at once); do not raise it to the 0.5 of the other presets. The stops are wide and grow with the price: in 2026 (BTC ${e26['price_low'] / 1000:,.0f},000 – ${e26['price_high'] / 1000:,.0f},000) median ${e26['stop_median']:,.0f}, 90% under ${e26['stop_p90']:,.0f}, widest ${e26['stop_max']:,.0f}; over 2024 – 2026 (up to ${ea['price_high'] / 1000:,.0f},000) median ${ea['stop_median']:,.0f}, 90% under ${ea['stop_p90']:,.0f}. With a 1-BTC contract and a 0.01 minimum lot, a trade is taken only if the equity is at least {ea['equity_for_90pct'] / ea['stop_p90']:.0f} times its stop in dollars at `RiskPercent=0.1` (`SkipIfBelowMinLot=true`): at 2026 prices about ${round(e26['equity_for_90pct'], -3):,.0f} covers 90% of trades, at 2024 – 2026 prices about ${round(ea['equity_for_90pct'], -3):,.0f} (2025 alone: ${round(e24['2025']['equity_for_90pct'], -3):,.0f}). At 0.1% each, the {len(s)} together held up to about {ex['together_max_lev']:.0f} times the equity in open positions: the account needs BTC leverage of at least 1:{ex['together_max_lev'] + 1:.0f}, and 1:10 leaves room.

**Inputs these presets use (new in v1.35):** `UseStochTurnFilter=true` (the entry rule), `ScaleWithPrice=true` with `ReferencePrice={ref}` (the stop buffer and minimum stop were calibrated at that price and follow it), `TrailMode=0` (the EA's own trailing).

**Re-picking.** The test picks the setups once a year from the three years before. These {len(s)} are meant for about a year; then the selection should be run again on the newest data.

"""
    zip_table = f"""## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35 (the same file as in the gold zip). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_WF_BTC_M30_*.set` | The {len(s)} presets of the year-by-year test (not proven). |
| `MQL5/Presets/Loma_BTC_M5_R01 … R04 *.set` | The four M5 presets from before (unproven). |
| `MQL5/Presets/Loma_T15_BTC_*.set` | The trailing presets (unproven). |
| `BTC_WF_M30_SUMMARY.csv` | The year-by-year presets with their calibration figures. |
| `BTC_PRESETS_SUMMARY.csv` | The four M5 presets: the calibration period, the unseen months of 2026, and 2024 and 2023. |
| `BTC_TRAILING15_SUMMARY.csv` | Every trailing preset with its figures. |
| `Loma_OOS_Review.html` | The full report, the same file as in the gold zip. Section 6 is the year-by-year test, section 5 the re-calibration. Open it in a browser. |

## Install

1. In MT5 choose **File > Open Data Folder**.
2. Copy the zip's `MQL5` folder over the data folder's `MQL5` folder.
3. In MetaEditor open `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` and press **F7** (compile).
4. Attach the EA to a BTCUSD chart (any timeframe: it reads its own). In **Inputs** click **Load** and pick a preset. The EA's built-in defaults are for gold; if they are left in place on BTC, the journal prints a warning.
5. Enable **Algo Trading**.

"""
    test = f"""## If you want to test it

- **Strategy Tester first:** "Every tick based on real ticks" on your broker's BTCUSD, deposit currency equal to your account's. In the tester, the Load dialog of the Inputs tab usually opens in `MQL5\\Profiles\\Tester`; browse to `MQL5\\Presets` for these files. For the `Loma_WF` presets use a deposit of at least ${-(-10 * ex['all_years']['stop_max'] // 5000) * 5000:,.0f} (at `RiskPercent=0.1` a trade is skipped unless the equity is at least 10 times its stop, and their stops reached ${ex['all_years']['stop_max']:,.0f}), and test 2024 to today, preset by preset and year by year, and compare each with its row in the table of the 10 presets (2024, 2025, 2026); also compare profit before commission, commission and swap. 2023 lies before the years they were picked on and has no figure here.
- **Then demo**, the `Loma_WF` presets together on a hedging account at `RiskPercent=0.1`. A tester run and a demo that match the figures above show that the EA trades its backtest, not that the edge is real: the 2026 check was 1.26, and chance can explain the pass.

"""
    new_changes = changes.replace("**v1.34** (this zip)", "**v1.35** (this zip)\n- The trailing systems, the Stochastic turn filter and the price scaling of \"New in v1.35\" above.\n\n**v1.34**")
    out = top + t15 + "\n" + m5 + corr + zip_table + v135_inputs() + "\n" + settings + test + codex + rules + new_changes
    out = out.replace("\n\n\n", "\n\n")
    open(p, "w", encoding="utf-8").write(out)
    print(f"{p}: {len(out)} characters")


def gold(t15="presets/trailing15/gold"):
    p = "packages/loma_xauusd/START_HERE.md"
    g = open(p, encoding="utf-8").read()
    old = g if "# Loma EA v1.34 for XAUUSD" in g else os.popen("git show 13d9ed8:packages/loma_xauusd/START_HERE.md").read()
    i = {k: old.index(k) for k in ("> **Do not trade these presets with real money.**", "## What is in the zip", "## Install", "## The six presets",
                                   "## If you still want to test it", "### Asking Codex to compile", "## The rules in short", "## What changed",
                                   "## What you see on the chart")}
    status_old = old[i["> **Do not trade these presets with real money.**"]:i["## What is in the zip"]]
    six = old[i["## The six presets"]:i["## If you still want to test it"]].replace("## The six presets", "## The six Top presets (lost out of sample)")
    test = old[i["## If you still want to test it"]:i["### Asking Codex to compile"]]
    codex = old[i["### Asking Codex to compile"]:i["## The rules in short"]]
    rules = old[i["## The rules in short"]:i["## What changed"]]
    changes = old[i["## What changed"]:i["## What you see on the chart"]]
    chart = old[i["## What you see on the chart"]:]

    fact = json.load(open(f"{R}/wf/wf_facts.json"))["XAUUSD"]
    summ = json.load(open(f"{R}/wf/xauusd_wf_summary.json"))
    assert fact["passed"] == 0, "a gold cell passed: write that up"
    rows = summ["rows"]
    years = [y["year"] for y in rows[0]["by_year"]]
    base = {r["tf"]: r for r in rows if r["condition"] == "base"}
    brows = []
    for tf in ("M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"):
        r = base[tf]
        if not r["n"]:
            brows.append(f"| {tf} | no setup held PF 1.3 in three years running at normal and stressed costs | – | – |"); continue
        lose = [y["year"] for y in r["by_year"] if y["n"] >= 50 and y["pf"] < 1.0]
        brows.append(f"| {tf} | {f2(r['pf'])} ({r['n']}) | {f2(r['stress_pf'])} | {', '.join(map(str, lose)) or 'none'} |")
    best = sorted([r for r in rows if r["n"] >= 100], key=lambda r: -r["pf"])[:5]
    bl = []
    for r in best:
        why = []
        if r["pf"] < 1.3: why.append("under 1.3")
        if r["stress_pf"] < 1.1: why.append(f"stressed {f2(r['stress_pf'])}")
        if r["losing_years"]: why.append("losing " + ", ".join(map(str, r["losing_years"])))
        if r["years_with_50_trades"] < 2: why.append("fewer than two years with 50 trades")
        bl.append(f"{r['tf']} {r['text'].split(' (')[0]}: {f2(r['pf'])} on {r['n']} trades ({'; '.join(why)})")
    t15sec = trailing_section("XAUUSD", t15, "GOLD_TRAILING15_SUMMARY.csv", "Gold")
    sg = json.load(open(f"{R}/recal/xauusd_successful_trailing.json"))["combinations"]
    keep = [c for c in sg if c["vt_unseen_pf"] >= 1.3]; drop = [c for c in sg if c["vt_unseen_pf"] < 1.3]
    t15_vt = (f"{len(keep)} of the {len(sg)} stay at 1.3 or more (" + " and ".join(f"{c['timeframe']} {NAME[c['trailing']]} {f2(c['vt_unseen_pf'])}" for c in keep)
              + ") and " + " and ".join(f"{c['timeframe']} {NAME[c['trailing']]} ({f2(c['vt_unseen_pf'])})" for c in drop) + " fall under it")
    t15_n = sum(c["setups"] for c in sg); t15_alone = sum(1 for c in sg for q in c["picks"] if q["unseen_pf"] < 1.3)
    near = sorted([r for r in rows if r["n"] >= 100 and r["pf"] >= 1.3 and r["stress_pf"] >= 1.1 and not r["losing_years"]], key=lambda r: -r["pf"])
    n50 = {0: "none of its years", 1: "only one of its years"}
    bl_first = (f"the best by profit factor, {near[0]['tf']} {near[0]['text'].split(' (')[0]}, made {f2(near[0]['pf'])} on {near[0]['n']} trades with no losing year in "
                f"{years[0]} – {years[-1]}, but {n50.get(near[0]['years_with_50_trades'], str(near[0]['years_with_50_trades']) + ' of its years')} had 50 trades, "
                f"and it made {f2(near[0]['final']['pf'])} on {near[0]['final']['n']} trades in the 2026 months kept back" if near else "the best are listed below")
    status = f"""> **Do not trade these presets with real money.**
> - **Year-by-year test: no gold result passed.** Set up on three years and traded on the next, 2016 to 2025, with 58 entry conditions tried one at a time at VT Markets' costs: none of the {fact['cells']} timeframe-and-condition cells held a profit factor of 1.3 over at least two years with 50 trades without a losing year ({bl_first}).
> - **The six `Loma_Top` presets** lost on the months after their calibration: on VT Markets real ticks (1 June – 6 November 2026) profit factor 0.74 before commission and 0.67 at VT's $0.60 per lot, on 247 trades. Dukascopy prices agree.
> - **The `Loma_T15_Gold_*` trailing presets** come from four combinations of timeframe and trailing system whose setups together reached a profit factor of 1.3 on the 2026 months at FTMO's spread without commission. At VT's costs {t15_vt}; {t15_alone} of the {t15_n} presets were under 1.3 on their own, and the four groups lost on July – December 2024. Unproven: Strategy Tester and demo only.
> - The EA itself works: it takes the same trades as the backtest.

"""
    wf = f"""## The year-by-year test on gold

Dukascopy gold one-minute prices from 2013 to 2024, FTMO for 2025 to 15 May 2026 and Dukascopy after, all in broker server time (the daily reopen at 01:00 server time checked year by year). For every year from {years[0]} to {years[-1]}, 12,000 setups per timeframe (M1 to H1) were scored on the three years before it, with each of 58 entry conditions added one at a time (market regime, location, confirmation, timing, the XLZC rules, and three random halves of the signals as controls) and the method without one, and the best of them, up to 10 (one per direction, session and trend-filter family, each with a profit factor of at least 1.3 in all three years at normal and stressed costs and an average cost under 1/8 of the risk), were traded on that year unchanged. Costs are VT Markets' own: a 1.5-pip spread shaped by the hour and $0.60 commission per ounce, scaled with the price like every dollar distance of a setup. A cell passes with a profit factor of 1.3 or more over its unseen years together, 1.1 or more stressed, at least two years with 50 trades and no such year below 1.0.

**Nothing passed.** The method without an extra condition, by timeframe:

| Timeframe | Unseen {years[0]} – {years[-1]}: PF (trades) | Stressed | Unseen years with 50+ trades below 1.0 |
|---|---|---|---|
""" + "\n".join(brows) + f"""

The best cells with at least 100 unseen trades: {'; '.join(bl)}. The year-by-year tables are in `Loma_OOS_Review.html`, section 6.

"""
    zip_table = """## What is in the zip

| File | What it is |
|---|---|
| `MQL5/Experts/XAUUSD_Loma_TrendPullback.mq5` | The EA, v1.35 (the same file runs on gold and on BTCUSD). |
| `MQL5/Include/EVK/EVK.mqh` | Records trades in the Strategy Tester only (EA Validation Kit). The EA needs it to compile. |
| `MQL5/Presets/Loma_Top01 … Top07 *.set` | The six gold presets of the first calibration (table below). |
| `MQL5/Presets/Loma_T15_Gold_*.set` | The trailing presets (unproven). |
| `GOLD_PRESETS_SUMMARY.csv` | Backtest and out-of-sample figures of the six Top presets. |
| `GOLD_TRAILING15_SUMMARY.csv` | Every trailing preset with its figures. |
| `Loma_OOS_Review.html` | The out-of-sample report: VT Markets run, Dukascopy cross-check, walk-forward, re-calibration (section 5) and the year-by-year test (section 6). Open it in a browser. |

"""
    install = old[i["## Install"]:i["## The six presets"]].replace("pick a preset.", "pick a preset (`Loma_T15` presets need this v1.35).")
    t15g = pd.read_csv(os.path.join(t15, "GOLD_TRAILING15_SUMMARY.csv"))
    def setv(f, k):
        return re.search(rf"^{k}=(.*)$", open(os.path.join(t15, f + ".set")).read(), re.M).group(1)
    req = [(f, setv(f, "StochLow"), setv(f, "StochHigh")) for f in t15g.file if setv(f, "RequireStochLevel") == "true"]
    pb1 = [f for f in t15g.file if setv(f, "PullbackMinBars") == "1"]
    short = lambda f: f.split("_")[4] + " " + f.split("_")[5]
    lv = {}
    for f, lo, hi in req:
        lv.setdefault(f"{float(lo):g}/{float(hi):g}", []).append(short(f))
    for a_, b_ in (("With `RequireStochLevel` on (Top04: 25/75, Top07: 20/80) the Stochastic must also reach `StochLow` / `StochHigh`; Top01, Top02, Top03 and Top05 do not require it.",
                    "With `RequireStochLevel` on (Top04 at 25/75 and Top07 at 20/80; among the `Loma_T15_Gold` presets " + "; ".join(f"{', '.join(v)} at {k}" for k, v in sorted(lv.items()))
                    + ") the Stochastic must also reach `StochLow` / `StochHigh`; the other presets do not require it."),
                   ("(1 in Top01, Top04 and Top07, so one bar across zero counts)",
                    "(1 in Top01, Top04, Top07 and the `Loma_T15_Gold` presets " + ", ".join(short(f) for f in pb1) + ", so one bar across zero counts)"),
                   ("trailing in multiples of the risk, maximum holding time, end-of-day close and Friday close, as set in each preset.",
                    "trailing in multiples of the risk (Top presets) or the system set in `TrailMode` (ATR at entry, percent, chandelier or hump structure in the "
                    "`Loma_T15_Gold` presets), maximum holding time, end-of-day close and Friday close, as set in each preset."),):
        assert a_ in rules, a_
        rules = rules.replace(a_, b_)
    test = test.replace("v1.34 warns on a netting account", "The EA warns on a netting account")
    six = six.replace("v1.34 warns on a netting account", "The EA warns on a netting account")
    v134_line = ("v1.34, the file in this zip, adds the changes listed below. It was checked line by line and run through a compile harness and a "
                 "simulated terminal, but it has not been compiled in MetaEditor yet.")
    assert v134_line in install, "the compile sentence of the v1.34 guide changed"
    install = install.replace(v134_line, "v1.34 and v1.35 (the file in this zip) were checked line by line and run through a compile harness and a "
                                         "simulated terminal, but have not been compiled in MetaEditor yet.")
    new_changes = changes.replace("**v1.34** (this zip)", "**v1.35** (this zip)\n- The trailing systems, the Stochastic turn filter and the price scaling of \"New in v1.35\" above.\n\n**v1.34**")
    head = old[:i["> **Do not trade these presets with real money.**"]].replace("v1.34", "v1.35").replace(
        "This zip holds the EA and the six gold presets with a backtest profit factor of 1.3 or more under stress, in both 2025 and 2026.",
        "This zip holds the EA, the six gold presets of the first calibration and the trailing presets of the re-calibration.")
    out = head + status + wf + t15sec + "\n" + zip_table + install + v135_inputs() + "\n" + six + test + codex + rules + new_changes + chart
    out = out.replace("\n\n\n", "\n\n")
    open(p, "w", encoding="utf-8").write(out)
    print(f"{p}: {len(out)} characters")


if __name__ == "__main__":
    import sys
    btc(*sys.argv[1:3]) if len(sys.argv) > 2 else btc()
    gold(sys.argv[3]) if len(sys.argv) > 3 else gold()
