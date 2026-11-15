#!/usr/bin/env python3
"""Write the parts of research/reports/loma_oos_review.html that quote the per-timeframe re-calibration: section 5
(between the recal:start / recal:end markers), the three re-calibration tiles, the BTC line of the verdict and the
re-calibration bullet of "What this means". Every number comes from the result files; the sentences are chosen from
the outcome, and the script stops when an outcome it has no sentence for appears. Run from the repository root.

Inputs (research/results/recal/):
  <sym>_r_trailing.json            the EA's own trailing stop, 12,000 setups per timeframe
  <sym>_23_trailing.json           23 trailing systems (runs 2 and 3 together), 69,000 setups per timeframe
  <sym>_23_trailing_by_family.json the same test inside each trailing system
  xauusd_*_vt_costs.json           the gold picks at VT Markets' costs
  btcusd_r_trailing_on_2023_2024.json, btcusd_23_trailing_on_2023_2024.json, xauusd_23_trailing_on_2024h2.json
                                   the picks on data from before the calibration period (pretest_picks.py)
presets/btc/BTC_RECAL_PRESETS_SUMMARY.csv and BTC_RECAL_PRESETS_DETAIL.json: the four BTC M5 presets.
Also writes research/reports/recal_facts.json, the figures the guides quote."""
import json, os, re
import pandas as pd

R = "research/results/recal"
PAGE = "research/reports/loma_oos_review.html"
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]
FAMILY = {
    "none": "No trailing", "R": "Multiples of the risk (the EA's own)", "points": "Fixed distance in dollars",
    "percent": "Percent of price", "atr": "ATR multiple, fixed at entry", "chandelier": "Chandelier (live ATR from the best price)",
    "breakeven": "Breakeven", "step": "Stepped ratchet", "profitlock": "Profit lock (keeps a share of the best profit)",
    "partial": "Half closed at a level, rest trailed", "timestop": "Time stop (stop slides to breakeven)",
    "candles": "Candle highs / lows", "pivots": "Swing pivots (fractals)", "donchian": "Donchian channel",
    "htfcandle": "Higher-timeframe candle", "hump": "Hump structure", "ema": "Moving average (EMA)",
    "sma": "Moving average (SMA)", "psar": "Parabolic SAR", "supertrend": "SuperTrend", "keltner": "Keltner channel",
    "bollinger": "Bollinger band", "kijun": "Ichimoku base line (Kijun)"}
SHORT = dict(none="no", R="the EA's own", points="fixed-dollar", percent="percent", atr="ATR-at-entry", chandelier="chandelier",
             breakeven="breakeven", step="stepped", profitlock="profit-lock", partial="partial-close", timestop="time-stop",
             candles="candle", pivots="swing-pivot", donchian="Donchian", htfcandle="higher-timeframe-candle", hump="hump-structure",
             ema="EMA", sma="SMA", psar="Parabolic SAR", supertrend="SuperTrend", keltner="Keltner", bollinger="Bollinger", kijun="Kijun")


def load(name):
    fn = f"{R}/{name}.json"
    return json.load(open(fn)) if os.path.exists(fn) else None


def tfrows(name):
    return {x["tf"]: x for x in load(name)["timeframes"]}


def passed(x):
    return bool(x and x.get("picked") and x["oos_pf"] >= 1.3 and x["oos_n"] >= 100)


def cell(x, vt=None):
    if not x.get("picked"):
        return '<td class="mut">none passed in-sample</td>'
    cls = ' class="gain"' if passed(x) else ""
    sub = [f'stressed {x["oos_stress_pf"]:.2f}']
    if vt and vt.get("picked"):
        sub.append(f'VT costs {vt["vt_oos_pf"]:.2f}')
    return f'<td{cls}>{x["oos_pf"]:.2f} ({int(x["oos_n"])}) <span class="sub">{" · ".join(sub)}</span></td>'


def join(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def sym(s):
    return "gold" if s == "XAUUSD" else "BTC"


g1, g23, b1, b23 = tfrows("xauusd_r_trailing"), tfrows("xauusd_23_trailing"), tfrows("btcusd_r_trailing"), tfrows("btcusd_23_trailing")
v1 = {x["tf"]: x for x in load("xauusd_r_trailing_vt_costs")["timeframes"]}
v23 = {x["tf"]: x for x in load("xauusd_23_trailing_vt_costs")["timeframes"]}
rows = "\n".join(f"          <tr><td>{tf}</td>{cell(g1[tf], v1.get(tf))}{cell(g23[tf], v23.get(tf))}{cell(b1[tf])}{cell(b23[tf])}</tr>" for tf in TFS)
gp1, gp23 = [tf for tf in TFS if passed(g1[tf])], [tf for tf in TFS if passed(g23[tf])]
bp1, bp23 = [tf for tf in TFS if passed(b1[tf])], [tf for tf in TFS if passed(b23[tf])]
gvals = [d[tf]["oos_pf"] for d in (g1, g23) for tf in TFS if d[tf].get("picked")]
vvals = [x["vt_oos_pf"] for d in (v1, v23) for x in d.values() if x.get("picked")]
n1, n23 = g1["M5"]["setups"], g23["M5"]["setups"]
assert {d[tf]["setups"] for d in (g1, b1) for tf in TFS} == {n1} and {d[tf]["setups"] for d in (g23, b23) for tf in TFS} == {n23}
n_pass = len(gp1) + len(gp23) + len(bp1) + len(bp23)

# ---- by trailing system
gfam, bfam = load("xauusd_23_trailing_by_family"), load("btcusd_23_trailing_by_family")
kg = {x["kind"]: x for x in gfam["by_kind_all_timeframes"]}; kb = {x["kind"]: x for x in bfam["by_kind_all_timeframes"]}
assert set(kg) == set(kb) == set(FAMILY), (set(FAMILY) ^ set(kg), set(FAMILY) ^ set(kb))


def fcell(x):
    return f'<td>{x["oos_pf"]:.2f} ({int(x["oos_n"])})</td>' if x.get("oos_n") else '<td class="mut">no pick</td>'


order = sorted(FAMILY, key=lambda k: -(kg[k].get("oos_pf", 0) + kb[k].get("oos_pf", 0)))
best_g = max(kg.values(), key=lambda x: x.get("oos_pf", 0)); best_b = max(kb.values(), key=lambda x: x.get("oos_pf", 0))
cells = pd.concat([pd.DataFrame(gfam["cells"]), pd.DataFrame(bfam["cells"])])
big = cells[cells.oos_n >= 100]
lead = big[big.oos_pf >= 1.3]

# ---- second test: data from before the calibration period
def grp(name):
    d = load(name)
    return {x["group"]: x for x in d["groups"]} if d else {}


pre_b1, pre_b23, pre_g = grp("btcusd_r_trailing_on_2023_2024"), grp("btcusd_23_trailing_on_2023_2024"), grp("xauusd_23_trailing_on_2024h2")


def pcell(x, y):
    if not x.get(f"y{y}_n"):
        return '<td class="mut">no trades</td>'
    return f'<td{" class=\"loss\"" if round(x[f"y{y}_pf"], 2) < 1 else ""}>{x[f"y{y}_pf"]:.2f} ({x[f"y{y}_n"]})</td>'


def prerow(label, x, gold):
    a = pcell(x, "2024H2") if gold else pcell(x, "2024")
    b = '<td class="mut">not tested</td>' if gold else pcell(x, "2023")
    return f'          <tr><td>{label}</td><td>{x["oos2026_pf"]:.2f} ({x["oos2026_n"]})</td>{a}{b}</tr>'


pre_rows, early = [], []                       # early: (label, list of earlier-period PFs) of every group that passed 2026
for tf in bp23:
    x = pre_b23[f"timeframe {tf}"]
    pre_rows.append(prerow(f"BTC {tf}, best {x['setups']} of the 23 systems", x, False)); early.append((f"BTC {tf}", [x["y2024_pf"], x["y2023_pf"]]))
for tf in gp23:
    x = pre_g[f"timeframe {tf}"]
    pre_rows.append(prerow(f"Gold {tf}, best {x['setups']} of the 23 systems", x, True)); early.append((f"gold {tf}", [x["y2024H2_pf"]]))
for r in lead.itertuples():
    gold = r.symbol == "XAUUSD"
    x = (pre_g if gold else pre_b23)[f"{r.tf} + {r.kind}"]
    pre_rows.append(prerow(f"{'Gold' if gold else 'BTC'} {r.tf} with {SHORT[r.kind]} trailing: {x['setups']} setups", x, gold))
    early.append((f"{sym(r.symbol)} {r.tf} {SHORT[r.kind]}", [x["y2024H2_pf"]] if gold else [x["y2024_pf"], x["y2023_pf"]]))
pretab = "\n".join(pre_rows)


def ecell(x, y):
    if not x or not x.get(f"y{y}_n"):
        return '<td class="mut">–</td>'
    return f'<td{" class=\"loss\"" if round(x[f"y{y}_pf"], 2) < 1 else ""}>{x[f"y{y}_pf"]:.2f}</td>'


for k in FAMILY:                               # the earlier-data groups are the same picks as the by-system rows
    for kk, pre in ((kg[k], pre_g), (kb[k], pre_b23)):
        assert not kk.get("oos_n") or pre[f"trailing {k}"]["oos2026_n"] == kk["oos_n"], k
fam = "\n".join(f'          <tr><td>{FAMILY[k]}</td>{fcell(kg[k])}{ecell(pre_g.get(f"trailing {k}"), "2024H2")}'
                f'{fcell(kb[k])}{ecell(pre_b23.get(f"trailing {k}"), "2024")}{ecell(pre_b23.get(f"trailing {k}"), "2023")}</tr>' for k in order)
fam_early = {sym_: [pre[f"trailing {k}"][f"y{y}_pf"] for k in FAMILY if pre.get(f"trailing {k}", {}).get(f"y{y}_n")]
             for sym_, pre, y in (("gold 2024 H2", pre_g, "2024H2"), ("BTC 2024", pre_b23, "2024"), ("BTC 2023", pre_b23, "2023"))}
early = [(name, [round(p, 2) for p in v]) for name, v in early]             # compared as they are printed
held = [name for name, v in early if all(p >= 1.3 for p in v)]            # passed 2026 and every earlier period
mixed = [name for name, v in early if any(p >= 1.0 for p in v) and name not in held]

# ---- the four BTC M5 presets (the EA's own trailing)
assert bp1 == ["M5"], bp1                                                   # the BTC zip holds the M5 picks of run 1
ps = pd.read_csv("presets/btc/BTC_RECAL_PRESETS_SUMMARY.csv")
det = json.load(open("presets/btc/BTC_RECAL_PRESETS_DETAIL.json"))["M5"]
m5 = pre_b1["timeframe M5"]; b1m5 = b1["M5"]
assert len(ps) == b1m5["picked"] == det["picks"] and det["trades"] == b1m5["oos_n"] == m5["oos2026_n"] and abs(det["pf"] - b1m5["oos_pf"]) < 1e-6
assert m5["y2024_pf"] < 1 and m5["y2023_pf"] < 1


def hhmm(s):
    return f"{s[:2]}:{s[2:4]}–{s[5:7]}:{s[7:9]}"


prs = "\n".join(
    f'          <tr><td>R{int(r["rank"]):02d} · {r["direction"].lower()}, {hhmm(r["session"])}</td><td>{int(r["in_sample_trades"])} / {r["in_sample_pf"]:.2f}</td>'
    f'<td{" class=\"loss\"" if r["unseen_pf"] < 1 else ""}>{r["unseen_pf"]:.2f} ({int(r["unseen_trades"])})</td><td>{r["unseen_stress_pf"]:.2f}</td>'
    f'<td{" class=\"loss\"" if r["y2024_pf"] < 1 else ""}>{r["y2024_pf"]:.2f} ({int(r["y2024_trades"])})</td>'
    f'<td{" class=\"loss\"" if r["y2023_pf"] < 1 else ""}>{r["y2023_pf"]:.2f} ({int(r["y2023_trades"])})</td></tr>' for _, r in ps.iterrows())
prs += (f'\n          <tr class="total"><td>All four</td><td></td><td>{m5["oos2026_pf"]:.2f} ({m5["oos2026_n"]})</td><td>{m5["oos2026_stress_pf"]:.2f}</td>'
        f'<td class="loss">{m5["y2024_pf"]:.2f} ({m5["y2024_n"]})</td><td class="loss">{m5["y2023_pf"]:.2f} ({m5["y2023_n"]})</td></tr>')
pos_months = sum(1 for x in det["months"] if x["net_r"] > 0)
k0, k1 = round(det["unseen_first_close"], -3) / 1000, round(det["unseen_last_close"], -3) / 1000
assert k1 < k0 and det["sells"] > det["buys"]

# ---- sentences, chosen from the outcome
assert not gp1 and not gp23, "gold passes: the gold sentences need rewriting"
other = [tf for tf in bp23 if tf != "M5"]
if not bp23:
    btc23 = (f"With all 23 systems no BTC timeframe passes: the best is {max((b23[tf] for tf in TFS if b23[tf].get('picked')), key=lambda x: x['oos_pf'])['tf']} at "
             f"{max(b23[tf]['oos_pf'] for tf in TFS if b23[tf].get('picked')):.2f}.")
else:
    btc23 = ("With all 23 systems " + join(f"{tf} passes again ({b23[tf]['oos_pf']:.2f} on {int(b23[tf]['oos_n'])} trades, stressed {b23[tf]['oos_stress_pf']:.2f})" for tf in bp23)
             + "; those setups are in the last table of this section.")
assert not held, f"{held} held on every period: a real candidate, write it up by hand"
gold_rows = [v for name, v in early if name.startswith("gold")]; btc_rows = [(name, v) for name, v in early if name.startswith("BTC")]
assert all(p < 1 for v in gold_rows for p in v), "a gold lead did not lose on earlier data: rewrite the sentence"
btc_mixed = [name for name, v in btc_rows if any(p >= 1.0 for p in v)]
btc_2023_up = [name for name, v in btc_rows if v[1] >= 1.0]
repeat = ("On earlier data none of them reached 1.3. "
          + (f"The {len(gold_rows)} gold rows all lost. " if gold_rows else "")
          + (f"Of the {len(btc_rows)} BTC rows, {len(btc_mixed)} were between 1.0 and 1.3 in 2024 or 2023 and the other {len(btc_rows) - len(btc_mixed)} were below 1.0 in both years; "
             f"in 2023 {'only ' + str(len(btc_2023_up)) if btc_2023_up else 'none'} stayed above 1.0. " if btc_rows else "")
          + "In 2023 BTC traded at about a third of its 2025–26 price, so the fixed $10 spread and the dollar distances of the setups weigh more there; 2024 is the closer comparison.")
assert mixed == btc_mixed
heading = (f"Gold: no timeframe holds PF 1.3 on unseen data. BTC: {join(sorted(set(bp1 + bp23), key=TFS.index))} "
           f"pass{'es' if len(set(bp1 + bp23)) == 1 else ''} in 2026 and fail{'s' if len(set(bp1 + bp23)) == 1 else ''} on earlier years")
n_lead_g, n_lead_b = int((lead.symbol == "XAUUSD").sum()), int((lead.symbol == "BTCUSD").sum())
lead_txt = "; ".join(f"{sym(r.symbol)} {r.tf} with {SHORT[r.kind]} trailing, {r.oos_pf:.2f} on {int(r.oos_n)} trades (stressed {r.oos_stress_pf:.2f})"
                     for r in lead.itertuples())
family_text = (f"No trailing system rescues gold: the best, {SHORT[best_g['kind']]} trailing, scores {best_g['oos_pf']:.2f}. On BTC several score well on the unseen months "
               f"({SHORT[best_b['kind']]} trailing {best_b['oos_pf']:.2f}), but the same setups score {min(fam_early['BTC 2024']):.2f} to {max(fam_early['BTC 2024']):.2f} on 2024 "
               f"and {min(fam_early['BTC 2023']):.2f} to {max(fam_early['BTC 2023']):.2f} on 2023. Split by timeframe and trailing system there are {len(big)} combinations with at least 100 unseen "
               f"trades ({int((big.symbol == 'XAUUSD').sum())} on gold, {int((big.symbol == 'BTCUSD').sum())} on BTC). "
               + (f"{len(lead)} reach 1.3 on the unseen months, {n_lead_g} on gold and {n_lead_b} on BTC. With that many combinations some reach 1.3 by chance, "
                  f"so each was run on earlier data, which lies before the calibration period, together with the BTC M5 setups of the 23-system run:" if len(lead) else "None reaches 1.3."))

section = f"""<!-- recal:start (generated by research/make_recal_html.py from research/results/recal/*.json) -->
  <section>
    <span class="eyebrow">5 · Re-calibration per timeframe</span>
    <h2>{heading}</h2>
    <p>After the six presets failed, the calibration was redone for every timeframe from M1 to H1, on gold and on BTC, with part of the data held back. Each setup was scored on January 2025 – 15 May 2026 only: the lowest of six profit factors (three periods, each at normal and at stressed costs, at least 20 trades per period). The 10 best setups of each timeframe, one per direction, session and trend-filter combination and only with a score of 1.3 or more, were then run unchanged on 16 May – 13 November 2026. A timeframe passes with a profit factor of 1.3 or more on at least 100 of those unseen trades.</p>
    <p>The test was run twice per symbol: with the EA's own trailing stop ({n1:,} random setups per timeframe), and with 23 trailing systems, the EA's own among them ({n23:,} setups per timeframe).</p>
    <div class="tablebox">
      <table>
        <thead><tr><th>Timeframe</th><th>Gold, the EA's own trailing<span class="sub">unseen PF (trades)</span></th><th>Gold, 23 trailing systems<span class="sub">unseen PF (trades)</span></th>
          <th>BTC, the EA's own trailing<span class="sub">unseen PF (trades)</span></th><th>BTC, 23 trailing systems<span class="sub">unseen PF (trades)</span></th></tr></thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
    <p class="note">{n_pass} of 32 pass (green). Stressed = entry one minute late, pessimistic trailing, slippage and commission. VT costs = the same gold setups at VT Markets' own costs as the account owner reported them, a 1.5-pip spread ($0.15) and $0.60 commission per lot, $0.75 per ounce in all: {min(vvals):.2f} to {max(vvals):.2f}. Gold: FTMO prices to 15 May 2026, Dukascopy after. BTC: Binance prices from 1 January 2025, read in UTC and converted to broker time once.</p>
    <h3>BTC M5 with the EA's own trailing: one pass, then a second test</h3>
    <p>M5 is the only BTC timeframe that passes with the trailing stop the EA has: {b1m5["picked"]} setups, {int(b1m5["oos_n"])} unseen trades, PF {b1m5["oos_pf"]:.2f} ({b1m5["oos_stress_pf"]:.2f} stressed). Resampling the weeks gives {b1m5["oos_pf_p05"]:.2f} to {b1m5["oos_pf_p95"]:.2f}, and {100 * b1m5["random_pick_as_good"]:.1f}% of random sets of M5 setups did as well. These four setups are the presets of the BTC zip. They were also run on 2023 and 2024, which lie before the calibration data:</p>
    <div class="tablebox">
      <table>
        <thead><tr><th>BTC M5 preset</th><th>Picked on<span class="sub">trades / PF</span></th><th>Unseen 2026<span class="sub">PF (trades)</span></th><th>Stressed</th><th>2024<span class="sub">PF (trades)</span></th><th>2023<span class="sub">PF (trades)</span></th></tr></thead>
        <tbody>
{prs}
        </tbody>
      </table>
    </div>
    <p class="note">The 2026 result did not repeat: the four together lost in both earlier years. {det["sells"]} of the {det["trades"]} unseen trades were sells, in months when BTC fell from about ${k0:.0f},000 to ${k1:.0f},000; in 2023 and 2024 it rose. {pos_months} of the {len(det["months"])} unseen months were positive. At a $20 spread the unseen PF is {det["pf_at_double_spread"]:.2f}, and {det["pf_without_3_largest_wins"]:.2f} without the three largest wins. One good period out of three is not an edge: demo only. {btc23}</p>
    <h3>By trailing system, all timeframes together</h3>
    <div class="tablebox">
      <table>
        <thead><tr><th>Trailing system</th><th>Gold, unseen 2026<span class="sub">PF (trades)</span></th><th>Gold, Jul – Dec 2024<span class="sub">same setups</span></th><th>BTC, unseen 2026<span class="sub">PF (trades)</span></th><th>BTC, 2024<span class="sub">same setups</span></th><th>BTC, 2023<span class="sub">same setups</span></th></tr></thead>
        <tbody>
{fam}
        </tbody>
      </table>
    </div>
    <p>{family_text}</p>
""" + (f"""    <div class="tablebox">
      <table>
        <thead><tr><th>Setups picked on Jan 2025 – May 2026</th><th>Unseen 2026<span class="sub">PF (trades)</span></th><th>2024<span class="sub">PF (trades); gold: Jul – Dec only</span></th><th>2023<span class="sub">PF (trades)</span></th></tr></thead>
        <tbody>
{pretab}
        </tbody>
      </table>
    </div>
    <p>{repeat}</p>
""" if pre_rows else "") + """    <p class="note">Trailing by a fixed dollar, percent or ATR distance, the profit lock and the trail after a partial close move the stop once per closed one-minute bar: one-minute prices cannot test a stop that follows the price inside the minute. The EA's own trailing keeps a wider distance, which one-minute prices do resolve: its result did not change when the same trades were walked in coarser steps. Correction: an earlier version of this section showed BTC figures from a price file whose clock ran 2 to 3 hours ahead of broker time. Those figures are withdrawn. The BTC series was rebuilt from the raw files, and the calibration now checks the clock of every series before it runs.</p>
  </section>
<!-- recal:end -->
"""

tiles = f"""<!-- recal-tiles:start -->
      <div class="tile"><span class="v">23</span><span class="k">trailing systems tested on every timeframe from M1 to H1, {n23:,} setups per timeframe and symbol</span></div>
      <div class="tile"><span class="v">{len(set(gp1 + gp23))} of 8</span><span class="k">gold timeframes that hold PF ≥ 1.3 on unseen data after re-calibration, with any trailing system (best: {max(gvals):.2f})</span></div>
      <div class="tile"><span class="v">{len(set(bp1 + bp23))} of 8</span><span class="k">BTC timeframes that pass the 2026 test ({join(sorted(set(bp1 + bp23), key=TFS.index))}); the same setups did not reach 1.3 on 2024 or 2023 (M5 presets: {m5["y2024_pf"]:.2f} and {m5["y2023_pf"]:.2f})</span></div>
<!-- recal-tiles:end -->"""
verdict = (f"""<!-- recal-verdict:start --><p><strong>BTC: unproven, demo only.</strong> The four new BTC M5 presets passed the unseen months of 2026 (PF {b1m5["oos_pf"]:.2f} on {int(b1m5["oos_n"])} trades) """
           f"""and lost on 2024 and 2023 ({m5["y2024_pf"]:.2f} and {m5["y2023_pf"]:.2f}). The earlier BTC01–BTC04 presets are withdrawn: they were fitted on a price file with a wrong clock.</p><!-- recal-verdict:end -->""")
bullet = (f"""<!-- recal-bullet:start --><li><strong>No timeframe and no trailing stop changes that on gold.</strong> Re-calibrated from M1 to H1 with 23 trailing systems, gold stays between {min(gvals):.2f} and {max(gvals):.2f} on unseen data. """
          f"""On BTC, M5 passed the 2026 months with the EA's own trailing (PF {b1m5["oos_pf"]:.2f}) and lost on 2023 and 2024, so it is a lead, not an edge.</li><!-- recal-bullet:end -->""")

s = open(PAGE, encoding="utf-8").read()
for name, block in (("recal", section), ("recal-tiles", tiles), ("recal-verdict", verdict), ("recal-bullet", bullet)):
    pat = re.compile(r"<!-- %s:start.*?<!-- %s:end -->\n?" % (name, name), flags=re.S)
    assert len(pat.findall(s)) == 1, name
    s = pat.sub(lambda m: block if block.endswith("\n") else block + "\n", s)
open(PAGE, "w", encoding="utf-8").write(s)

facts = dict(
    gold_pass=sorted(set(gp1 + gp23)), btc_pass_own_trailing=bp1, btc_pass_23_systems=bp23, passes_of_32=n_pass,
    gold_min=round(min(gvals), 2), gold_max=round(max(gvals), 2), vt_min=round(min(vvals), 2), vt_max=round(max(vvals), 2),
    gold={run: {tf: (dict(pf=round(d[tf]["oos_pf"], 2), n=int(d[tf]["oos_n"]), stress=round(d[tf]["oos_stress_pf"], 2)) if d[tf].get("picked") else None) for tf in TFS}
          for run, d in (("own", g1), ("all23", g23))},
    btc={run: {tf: (dict(pf=round(d[tf]["oos_pf"], 2), n=int(d[tf]["oos_n"]), stress=round(d[tf]["oos_stress_pf"], 2)) if d[tf].get("picked") else None) for tf in TFS}
         for run, d in (("own", b1), ("all23", b23))},
    best_system=dict(gold=[best_g["kind"], round(best_g["oos_pf"], 2)], btc=[best_b["kind"], round(best_b["oos_pf"], 2)]),
    cells_100=int(len(big)), cells_1_3=int(len(lead)), leads=lead_txt, held_on_every_period=held, mixed_on_earlier=mixed,
    earlier={name: [round(p, 2) for p in v] for name, v in early},
    btc_m5=dict(n=int(b1m5["oos_n"]), pf=round(b1m5["oos_pf"], 2), stress=round(b1m5["oos_stress_pf"], 2), p05=round(b1m5["oos_pf_p05"], 2),
                p95=round(b1m5["oos_pf_p95"], 2), random=b1m5["random_pick_as_good"], y2024=round(m5["y2024_pf"], 2), y2024_n=m5["y2024_n"],
                y2023=round(m5["y2023_pf"], 2), y2023_n=m5["y2023_n"], positive_months=pos_months, months=len(det["months"]),
                sells=det["sells"], pf_double_spread=round(det["pf_at_double_spread"], 2), pf_no_top3=round(det["pf_without_3_largest_wins"], 2)),
    setups=dict(own=n1, all23=n23))
json.dump(facts, open("research/reports/recal_facts.json", "w"), indent=1)
print(json.dumps(facts, indent=1))
