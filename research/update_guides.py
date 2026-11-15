#!/usr/bin/env python3
"""Keep the figures in the Loma guides equal to the result files.

1. Rewrites the lines that quote the per-timeframe re-calibration, from research/reports/recal_facts.json
   (written by make_recal_html.py) and presets/btc/BTC_RECAL_PRESETS_SUMMARY.csv:
     packages/loma_xauusd/START_HERE.md   the "Re-calibration per timeframe" bullet
     packages/loma_btcusd/START_HERE.md   the "With 23 trailing systems" bullet
     LOMA_START_HERE.md                   the BTC and re-calibration lines of the status box, the BTC preset table
     README.md                            the BTC and re-calibration lines of the status list
   Each is one line, found by its opening words.
2. Checks every other figure of the BTC guide against the data and stops on a mismatch.
Run from the repository root, after make_recal_html.py."""
import json, re, sys
import pandas as pd

F = json.load(open("research/reports/recal_facts.json"))
PS = pd.read_csv("presets/btc/BTC_RECAL_PRESETS_SUMMARY.csv")
DET = json.load(open("presets/btc/BTC_RECAL_PRESETS_DETAIL.json"))["M5"]
RUN1 = {x["tf"]: x for x in json.load(open("research/results/recal/btcusd_r_trailing.json"))["timeframes"]}
RULES = [x for x in json.load(open("research/results/recal/btcusd_r_trailing_other_rules.json")) if x["tf"] == "M5"]
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
m5 = F["btc_m5"]


def join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def set_line(path, start, new):
    lines = open(path, encoding="utf-8").read().split("\n")
    hits = [i for i, x in enumerate(lines) if x.startswith(start)]
    assert len(hits) == 1, (path, start, len(hits))
    lines[hits[0]] = new
    open(path, "w", encoding="utf-8").write("\n".join(lines))


# ---- sentences shared by the guides
WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}
best = {run: max((tf for tf in TFS if F["gold"][run][tf]), key=lambda tf: F["gold"][run][tf]["pf"]) for run in ("own", "all23")}
gold_best = (f"{best['own']} is the best in both runs ({F['gold']['own'][best['own']]['pf']:.2f} with the EA's own trailing, {F['gold']['all23'][best['all23']]['pf']:.2f} with the 23 systems)"
             if best["own"] == best["all23"] else
             f"the best are {best['own']} with the EA's own trailing ({F['gold']['own'][best['own']]['pf']:.2f}) and {best['all23']} with the 23 systems ({F['gold']['all23'][best['all23']]['pf']:.2f})")
gold_leads = {k: v for k, v in F["earlier"].items() if k.startswith("gold ")}
gold_lead_txt = ""
if gold_leads:
    gold_lead_txt = (f" {WORD[len(gold_leads)]} single combination{'s' if len(gold_leads) > 1 else ''} of timeframe and trailing system reached 1.3 on the unseen months "
                     f"({join(k[5:] for k in gold_leads)}); on July – December 2024, before the calibration data, "
                     f"{'they' if len(gold_leads) > 1 else 'it'} scored {join(f'{v[0]:.2f}' for v in gold_leads.values())}.")
p23 = F["btc_pass_23_systems"]
if p23:
    def early(tf):
        v = F["earlier"][f"BTC {tf}"]
        return f"{v[0]:.2f} in 2024 and {v[1]:.2f} in 2023"
    btc23 = ("with all 23 systems " + join(f"{tf} passes the 2026 months ({F['btc']['all23'][tf]['pf']:.2f} on {F['btc']['all23'][tf]['n']} trades)" for tf in p23)
             + "; the same setups scored " + join(f"{early(tf)}" + (f" ({tf})" if len(p23) > 1 else "") for tf in p23))
else:
    best = max((tf for tf in TFS if F["btc"]["all23"][tf]), key=lambda tf: F["btc"]["all23"][tf]["pf"])
    btc23 = f"with all 23 systems no BTC timeframe passes the 2026 months (the best is {best} at {F['btc']['all23'][best]['pf']:.2f})"
assert not F["held_on_every_period"]

gold_recal = (f"every timeframe from M1 to H1 was re-calibrated on January 2025 – 15 May 2026, once with the EA's own trailing stop and once with "
              f"23 trailing systems ({F['setups']['all23']:,} setups per timeframe), and the best 10 setups of each were run on 16 May – 13 November 2026. "
              f"No gold timeframe holds a profit factor of 1.3 there: the range is {F['gold_min']:.2f} to {F['gold_max']:.2f} "
              f"({F['vt_min']:.2f} to {F['vt_max']:.2f} at VT's costs), and {gold_best}.{gold_lead_txt}")
btc_status = (f"the four new M5 presets passed the unseen months of 2026 (profit factor {m5['pf']:.2f} on {m5['n']} trades, 16 May – 13 November) and lost on the "
              f"two years before the calibration data ({m5['y2024']:.2f} in 2024, {m5['y2023']:.2f} in 2023): unproven, demo only. "
              f"The earlier `Loma_BTC01`–`BTC04` presets are withdrawn; they were fitted on a price file with a wrong clock.")
if p23 == ["M5"]:
    e23 = F["earlier"]["BTC M5"]; a23 = F["btc"]["all23"]["M5"]
    btc_line = (f"BTC: M5 passes the 2026 months, with the EA's own trailing ({m5['pf']:.2f} on {m5['n']} trades) and with all 23 systems ({a23['pf']:.2f} on {a23['n']} trades), "
                f"but the same setups scored {m5['y2024']:.2f} and {e23[0]:.2f} in 2024 and {m5['y2023']:.2f} and {e23[1]:.2f} in 2023: it did not hold on earlier data. No other BTC timeframe passes.")
    btc_bullet = (f"- **With 23 trailing systems** instead of the EA's one, M5 again passes the 2026 months ({a23['pf']:.2f} on {a23['n']} trades), and the same setups scored "
                  f"{e23[0]:.2f} in 2024 and {e23[1]:.2f} in 2023. No other BTC timeframe passes. The EA cannot trade the other 22 systems, and nothing in these results is a reason to add them.")
else:
    btc_line = f"BTC: M5 passes with the EA's own trailing ({m5['pf']:.2f}), and {btc23}. None of it held on earlier data."
    btc_bullet = f"- **With 23 trailing systems** instead of the EA's one: {btc23}. The EA cannot trade the other 22 systems, and nothing in these results is a reason to add them."
recal_status = (f"every timeframe from M1 to H1 was re-calibrated on the same period with 23 trailing systems and tested on the months after it. "
                f"Gold: no timeframe holds a profit factor of 1.3 on unseen data ({F['gold_min']:.2f}–{F['gold_max']:.2f}, or {F['vt_min']:.2f}–{F['vt_max']:.2f} at VT's costs). {btc_line}")

set_line("packages/loma_xauusd/START_HERE.md", "- **Re-calibration per timeframe",
         f"- **Re-calibration per timeframe (15 November 2026):** {gold_recal} The tables are in `Loma_OOS_Review.html`, section 5.")
set_line("packages/loma_btcusd/START_HERE.md", "<!--BTC23-->" if "<!--BTC23-->" in open("packages/loma_btcusd/START_HERE.md").read() else "- **With 23 trailing systems",
         btc_bullet)
set_line("LOMA_START_HERE.md", "> - **BTC:**", f"> - **BTC:** {btc_status}")
set_line("LOMA_START_HERE.md", "> - **Re-calibration", f"> - **Re-calibration (15 November 2026):** {recal_status}")
set_line("README.md", "- **BTC:**", f"- **BTC:** {btc_status}")
set_line("README.md", "- **Re-calibration per timeframe", f"- **Re-calibration per timeframe:** {recal_status} See `research/reports/loma_oos_review.html`, section 5.")


# ---- the BTC preset table (same rows in the BTC guide and in LOMA_START_HERE.md)
def trow(r, name):
    sess = r["session"]; sess = f"{sess[:2]}:{sess[2:4]}-{sess[5:7]}:{sess[7:9]}"
    filt = "none" if r["trend_filter"] == "none" else f"{r['trend_filter']} EMA {int(r['htf_ema'])}"
    net = f"{'+' if r['unseen_net_r'] >= 0 else '−'}{abs(r['unseen_net_r']):.1f}R"
    return (f"| `{name}` | {r['direction'].lower()} | {sess} | {filt} | {r['target']} | {r['trailing']} | {int(r['in_sample_trades'])} / {r['in_sample_pf']:.2f} | "
            f"{int(r['unseen_trades'])}, {r['unseen_pf']:.2f}, {net} | {r['unseen_stress_pf']:.2f} | {r['y2024_pf']:.2f} ({int(r['y2024_trades'])}) | {r['y2023_pf']:.2f} ({int(r['y2023_trades'])}) |")


head = ("| Preset | Direction | Session (server time) | Trend filter | Target | Trailing | Picked on: trades / PF | Unseen 2026: trades, PF, net | Stress PF | 2024: PF (trades) | 2023: PF (trades) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|")
total = (f"| **All four** | | | | | | | **{m5['n']}, {m5['pf']:.2f}, +{DET['net_r']:.1f}R** | **{m5['stress']:.2f}** | **{m5['y2024']:.2f} ({m5['y2024_n']})** | **{m5['y2023']:.2f} ({m5['y2023_n']})** |")
table_short = "\n".join([head] + [trow(r, f"R{int(r['rank']):02d}") for _, r in PS.iterrows()] + [total])
table_long = "\n".join([head] + [trow(r, f"Loma_BTC_M5_R{int(r['rank']):02d}") for _, r in PS.iterrows()] + [total])

g = open("packages/loma_btcusd/START_HERE.md", encoding="utf-8").read()
i = g.index("| Preset | Direction |"); j = g.index("\n\n", i)
g = g[:i] + table_short + g[j:]
open("packages/loma_btcusd/START_HERE.md", "w", encoding="utf-8").write(g)

a = open("LOMA_START_HERE.md", encoding="utf-8").read()
i = a.index("**BTC** (`dist/Loma_BTCUSD"); j = a.index("\n## ", i)
a = a[:i] + ("**BTC** (`dist/Loma_BTCUSD_v1_34.zip`). Four M5 presets from the re-calibration. Binance BTCUSDT one-minute data in broker server time with an assumed $10 spread. "
             "Picked on January 2025 – 15 May 2026; unseen: 16 May – 13 November 2026; 2024 and 2023 lie before the calibration data. "
             "Stress = entry one minute late, pessimistic trailing, $3 slippage and $2 commission per BTC.\n\n" + table_long + "\n") + a[j:]
open("LOMA_START_HERE.md", "w", encoding="utf-8").write(a)

# ---- every other figure of the BTC guide, checked against the data
g = open("packages/loma_btcusd/START_HERE.md", encoding="utf-8").read()
sept = next(x for x in DET["months"] if x["month"].endswith("-09"))
neg = [x for x in DET["months"] if x["net_r"] <= 0]
words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
others = ", ".join((f"{tf} {RUN1[tf]['oos_pf']:.2f}" + (f" ({int(RUN1[tf]['oos_n'])} trades)" if RUN1[tf]["oos_n"] < 100 and tf == "M2" else ""))
                   for tf in TFS if tf != "M5" and RUN1[tf].get("picked"))
rules = [f"{x['oos_pf']:.2f}" for x in RULES if not x["rule"].startswith("main rule")]
ws = DET["stop_usd_whole_series"]; ex = DET["exposure_unseen"]
expect = [
    f"profit factor {m5['y2024']:.2f} in 2024 ({m5['y2024_n']} trades) and {m5['y2023']:.2f} in 2023 ({m5['y2023_n']} trades)",
    f"{DET['sells']} of the {DET['trades']} unseen trades were sells",
    f"(about ${round(DET['unseen_first_close'], -3) / 1000:.0f},000 to ${round(DET['unseen_last_close'], -3) / 1000:.0f},000)",
    f"{words[m5['positive_months']]} of the {words[m5['months']]} months were positive (September −{abs(sept['net_r']):.1f}R)",
    f"The largest drawdown was {DET['max_drawdown_r']:.1f}R",
    f"It falls to {m5['pf_no_top3']:.2f} without the three largest wins and to {m5['pf_double_spread']:.2f} at a $20 spread",
    f"Resampling the weeks gives {m5['p05']:.2f} to {m5['p95']:.2f} in nine cases out of ten, and about a third of the resamples are below 1.3",
    f"the result is {', '.join(rules[:-1])} and {rules[-1]}",
    others,
    f"the {DET['trades']} trades start on {DET['distinct_entry_minutes']} different minutes",
    f"median ${round(ws['median'] / 5) * 5:.0f}, 90% under ${round(ws['p90'], -1):.0f}, widest ${round(ws['max'], -1):,.0f}",
    f"about ${round(2 * ws['p90'], -2):,.0f} covers 90% of trades",
    f"{m5['n']} trades, profit factor {m5['pf']:.2f} ({m5['stress']:.2f} in the stress test)",
    f"after falling to ${round(DET['unseen_low_close'], -3) / 1000:.0f},000 by July and rising to ${round(DET['unseen_high_close'], -3) / 1000:.0f},000 in September",
    f"Sells in the {words[len(DET['falling_months'])]} falling months made +{DET['sells_in_falling_months']['net_r']:.1f}R of the +{DET['net_r']:.1f}R, "
    f"sells in the {words[len(DET['rising_months'])]} rising months +{DET['sells_in_rising_months']['net_r']:.1f}R and the {DET['buys_all']['trades']} buys +{DET['buys_all']['net_r']:.1f}R",
    f"with no spread at all they score {DET['earlier_years_no_spread']['2024']:.2f} in 2024 and {DET['earlier_years_no_spread']['2023']:.2f} in 2023",
    f"Extra round-trip costs of $20 per BTC lower it to {DET['pf_by_extra_cost_per_btc']['20']:.2f}, and $45 per BTC removes the gain ({DET['pf_by_extra_cost_per_btc']['45']:.2f})",
    f"with the extra costs alone it is {DET['pf_extra_costs_without_late_entry']:.2f}",
    f"R02 shares entry minutes with R03 ({DET['shared_entry_minutes']['R02+R03']}) and R01 ({DET['shared_entry_minutes']['R01+R02']}), and R03 with R04 ({DET['shared_entry_minutes']['R03+R04']})",
    f"open together {ex['pairs_open_together']} times, {ex['pairs_same_direction']} of them in the same direction, and up to {words[ex['max_positions_open']]} at once: {0.5 * ex['max_positions_open']:.0f}% at risk",
    f"typically {ex['per_trade_median']:.1f} times the balance (up to {ex['per_trade_max']:.1f} times in the unseen months), and the four presets together held up to {ex['all_presets_max']:.1f} times",
]
assert 0.30 <= DET["weekly_resampling"]["share_below_1_3"] <= 0.37, "the guide says about a third"
assert set(DET["shared_entry_minutes"]) == {"R02+R03", "R01+R02", "R03+R04"} and DET["unseen_low_date"][5:7] == "07" and DET["unseen_high_date"][5:7] == "09"
assert ex["all_presets_max"] < 10 and DET["exposure_whole_series"]["all_presets_max"] < 10, "the leverage sentence says about 1:10"
assert len(neg) == 1 and neg[0] is sept, neg
bad = [x for x in expect if x not in g]
for x in bad:
    print("NOT IN THE BTC GUIDE:", x)
if bad:
    sys.exit(1)
assert "<!--" not in g, "marker left in the BTC guide"
print(f"guides updated; {len(expect)} BTC guide figures match the data")
