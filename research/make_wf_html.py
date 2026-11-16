#!/usr/bin/env python3
"""
Section 6 of research/reports/loma_oos_review.html: the year-by-year test on long history (hump_wf.py), written
between the <!-- wf:start --> and <!-- wf:end --> markers (inserted before "What this means" on the first run).
Also writes research/results/wf/<sym>_wf_summary.json, the compact per-cell results the section is built from.

Usage (repository root):
  python3 research/make_wf_html.py <wf json> ... [<detail json of a passing cell> ...]
The wf jsons (written by "hump_wf.py wf": XAUUSD, BTCUSD, and EURUSD and US500 of protocol 2) and the detail jsons
("hump_wf.py detail") can come in any order; they are told apart by their contents. Protocol 2 writes the final
year only for the cells that pass.
"""
import json, os, re, sys

PAGE = "research/reports/loma_oos_review.html"
OUT = "research/results/wf"
TFS = ["M1", "M2", "M3", "M5", "M10", "M15", "M30", "H1"]


def compact(d):
    rows = []
    for r in d["rows"]:
        rows.append(dict(tf=r["tf"], condition=r["condition"], group=r["group"], text=r["text"], n=r["n"], pf=r["pf"], stress_pf=r["stress_pf"],
                         net_r=r["net_r"], cost_r_per_trade=r["cost_r_per_trade"], passes=r["passes"], losing_years=r["losing_years"],
                         years_with_50_trades=r["years_with_50_trades"],
                         by_year=[dict(year=y["year"], picks=len(y["picks"]), n=y["n"], pf=y["pf"], stress_pf=y["stress_pf"]) for y in r["by_year"]],
                         final=(dict(year=r["final"]["year"], picks=len(r["final"]["picks"]), n=r["final"]["n"], pf=r["final"]["pf"],
                                     stress_pf=r["final"]["stress_pf"], net_r=r["final"]["win"] - r["final"]["loss"]) if r.get("final") else None)))
    return dict({k: v for k, v in d.items() if k != "rows"}, rows=rows)


def f2(x):
    return "–" if x is None or x != x else ("∞" if x == float("inf") else f"{x:.2f}")


def ycell(y):
    if not y["n"]:
        return '<td class="mut">–</td>'
    cls = ' class="loss"' if y["pf"] < 1 else (' class="gain"' if y["pf"] >= 1.3 else "")
    return f'<td{cls}>{f2(y["pf"])} <span class="sub">{y["n"]}</span></td>'


def main():
    sums = {}
    os.makedirs(OUT, exist_ok=True)
    loaded = [json.load(open(f)) for f in sys.argv[1:]]
    order = {"XAUUSD": 0, "BTCUSD": 1, "EURUSD": 2, "US500": 3}
    for raw in sorted((x for x in loaded if "rows" in x), key=lambda x: order.get(x["symbol"], 9)):
        d = compact(raw)
        sym = d["symbol"].lower()
        json.dump(d, open(os.path.join(OUT, f"{sym}_wf_summary.json"), "w"), indent=1, default=float)
        sums[d["symbol"]] = d
    details = [x for x in loaded if "walk_forward" in x]
    NAME = {"XAUUSD": "Gold", "BTCUSD": "BTC", "EURUSD": "EURUSD", "US500": "US500"}

    def table(d, rows, title):
        years = [y["year"] for y in rows[0]["by_year"]] if rows else []
        head = "".join(f"<th>{y}</th>" for y in years)
        body = []
        for r in rows:
            fin = r["final"]
            if fin is None:
                fcell = '<td class="mut">not run <span class="sub">did not pass</span></td>'
            else:
                fcls = ' class="loss"' if fin["n"] and fin["pf"] < 1 else (' class="gain"' if fin["n"] and fin["pf"] >= 1.3 else "")
                fcell = f'<td{fcls}>{f2(fin["pf"]) if fin["n"] else "no picks"} <span class="sub">{fin["n"]}</span></td>'
            body.append(f'          <tr><td>{r["tf"]} · {r["text"]}</td>{"".join(ycell(y) for y in r["by_year"])}'
                        f'<td{" class=\"gain\"" if r["passes"] else ""}>{f2(r["pf"])} <span class="sub">{r["n"]} · stressed {f2(r["stress_pf"])}</span></td>'
                        f'{fcell}</tr>')
        fy = next((r["final"]["year"] for r in rows if r["final"]), 2026)
        return (f'    <h3>{title}</h3>\n    <div class="tablebox">\n      <table>\n        <thead><tr><th>Timeframe · condition</th>{head}'
                f'<th>Unseen years together<span class="sub">PF · trades</span></th><th>Final check {fy}<span class="sub">never used to decide</span></th></tr></thead>\n'
                f'        <tbody>\n' + "\n".join(body) + '\n        </tbody>\n      </table>\n    </div>')

    parts, parts2 = [], []
    counts = {}
    p2 = [d for d in sums.values() if d.get("protocol", 1) == 2]
    P2_INTRO = ""
    P2_DECISION = ""
    fxd_path = os.path.join(OUT, "fx_decision.json")
    if p2 and os.path.exists(fxd_path):
        fxd = json.load(open(fxd_path))
        lines = []
        for sym, v in fxd.items():
            ns = v["no_skill"]
            head = (f'<strong>{sym}:</strong> {v["passes"]} of {v["cells"]} cells met the pass rule; in the no-skill reshuffle '
                    f'({ns["runs"]} runs per timeframe) {ns["mean_passes_per_run"]:.2f} cells pass per run, 95th percentile {ns["p95"]:.0f}.')
            for c in v["passing_cells"]:
                r1, r2, r3, r4 = c["rule1"], c["rule2"], c["rule3"], c["rule4"]
                yrs = ", ".join(f'{y} {f2(x["pf"])} on {x["trades"]}' for y, x in r1["by_year"].items())
                head += (f' {c["tf"]} {c["text"]}: rule 1 met, PF {r1["pf"]:.2f} on {r1["trades"]} trades ({yrs}), stressed {r1["stress_pf"]:.2f}, '
                         f'and the pass rests on one setup chosen in 2023 with a score of 1.30, just above the selection cut: without it the cell has 91 trades, under the 100 the rule needs; rule 2 {"met" if r2["met"] else "not met"}, '
                         f'{r2["pf"]:.2f} on {r2["signals"]} signals; rule 3 not met: the cell itself passes in {r3["cell_share_of_no_skill_runs"] * 100:.0f}% of the reshuffles, '
                         f'but one pass is what they give: {r3["share_runs_with_as_many"] * 100:.0f}% of the runs have one or more; rule 4: {r4["outcome"]} '
                         f'(and none for the year ahead), so there is nothing to test or to trade.') if not r3["met"] else ''
            lines.append(head)
        verdict_all = "No result." if not any(v["results"] for v in fxd.values()) else "Results: " + "; ".join(f"{k} {', '.join(v['results'])}" for k, v in fxd.items() if v["results"])
        P2_DECISION = (f'    <p><strong>The decision fixed in advance, applied.</strong> {" ".join(lines)} {verdict_all} '
                       f'Sources: <code>research/results/wf/fx_decision.json</code>, <code>research/results/wf/fx_eval/</code>, '
                       f'<code>research/audit_wf/protocol2/</code> (an independent recomputation reproduced all 944 cells exactly).</p>\n')
    if p2:
        cells2 = sum(len(d["rows"]) for d in p2)
        P2_INTRO = (f'    <h3>EURUSD and US500: the same test, because gold and BTC did not hold up</h3>\n'
                    f'    <p>The research brief said: if gold and BTC both fail, run the same test on EURUSD and US500. It was run with the same setups, '
                    f'entry conditions, selection and pass rule ({cells2:,} cells), on Dukascopy one-minute prices from 2013 to 13 November 2026 in broker server '
                    f'time (each year\'s clock checked), so the unseen years are 2016 to 2025. What counts as a result was written down before any of their '
                    f'figures existed (<code>research/results/wf/protocol2_decision.md</code>): the pass rule, then the same rule counted once per signal, then a '
                    f'chance check, then the 2026 months, which are run only for cells that get that far. For EURUSD and US500, three details of the gold and BTC runs were tightened (gold and BTC were not re-run): '
                    f'the anchor price comes from the last 180 days of 2025, calibration years leave out trades that close in the next year, and the 2025 test '
                    f'year counts only trades that close in 2025.</p>\n'
                    f'    <p class="note">Costs at VT Markets\' RAW ECN account (the account type of the gold costs above): EURUSD a 0.3-pip spread shaped by the '
                    f'hour (wider at the daily rollover) and $6 commission per 100,000; US500 a 0.5-point spread shaped by the hour, no commission. Stressed: '
                    f'one minute late, pessimistic trailing, and 0.2 pip slippage with 10% more commission (EURUSD) or 0.3 points slippage and 0.2 points '
                    f'commission (US500). All scaled with the price as for gold. US500\'s early data is uneven: a three-month hole in 2013, the cash session only '
                    f'on some 2013 days, and 09:00 – 23:00 server time only from 2015 to April 2018, so the night conditions have fewer years there.</p>')
    for sym, d in sums.items():
        rows = d["rows"]
        passed = [r for r in rows if r["passes"]]
        base = [r for r in rows if r["condition"] == "base"]
        ctrl = [r for r in rows if r["group"] == "control"]
        counts[sym] = dict(cells=len(rows), cells_100=sum(1 for r in rows if r["n"] >= 100), passed=len(passed),
                           confirmed=[r for r in passed if r["final"] and r["final"]["n"] and r["final"]["pf"] >= 1.3],
                           flat=[r for r in passed if r["final"] and r["final"]["n"] and 1.0 <= r["final"]["pf"] < 1.3],
                           failed=[r for r in passed if r["final"] and r["final"]["n"] and r["final"]["pf"] < 1.0],
                           nopick=[r for r in passed if not (r["final"] and r["final"]["n"])], controls_passed=sum(1 for r in ctrl if r["passes"]), controls=len(ctrl),
                           protocol=d.get("protocol", 1))
        name = NAME.get(sym, sym)
        dst = parts2 if d.get("protocol", 1) == 2 else parts
        if passed:
            dst.append(table(d, sorted(passed, key=lambda r: -r["pf"]), f"{name}: the timeframe-and-condition cells that passed"))
        else:
            dst.append(f"    <h3>{name}: no cell passed</h3>")
        dst.append(table(d, base, f"{name}: the method without an extra condition"))
    c_g, c_b = counts.get("XAUUSD"), counts.get("BTCUSD")

    def names(lst):
        return ", ".join(f'{r["tf"]} {r["condition"]} ({f2(r["final"]["pf"]) if r["final"] and r["final"]["n"] else "no picks"})' for r in lst) or "none"

    det = ""
    for x in details:
        a = x["all_unseen_years"]; w = x["walk_forward"]; f = x["final_year"]
        flat = x.get("flat_spread_in_dollars", {}).get("all_unseen_years", {})
        yrs_traded = sorted(int(y) for y in a["by_year"])
        det += (f'    <p class="note">{x["symbol"]} {x["tf"]} · {x["text"]}: {yrs_traded[0]} – {yrs_traded[-1]} together {a["n"]} trades, PF {a["pf"]:.2f} '
                f'(stressed {a["stress"]["pf"]:.2f}), {a["positive_months"]} of {a["months"]} months positive, largest drawdown {a["max_drawdown_r"]:.1f}R, '
                f'PF {a["pf_without_3_largest_wins"]:.2f} without the three largest wins; resampling the weeks gives {a["resampling"]["p05"]:.2f} to '
                f'{a["resampling"]["p95"]:.2f} in nine cases out of ten. Buys {a["buys"]["pf"]:.2f} ({a["buys"]["n"]}), sells {a["sells"]["pf"]:.2f} ({a["sells"]["n"]}). '
                f'Average cost {a["cost_r_per_trade"]:.3f}R per trade.'
                + (f' With the spread fixed at ${x["flat_spread_in_dollars"]["spread"]:.0f} in every year instead of following the price: {flat["pf"]:.2f}.' if flat else "")
                + "</p>\n")
    total_cells = sum(c["cells"] for c in counts.values())
    ch = json.load(open(os.path.join(OUT, "chance_check.json")))
    cb, cg = ch["BTCUSD"], ch["XAUUSD"]; th = cb["thin_M30_xlzc_stoch"]

    def rc(c):
        return f'{c["walk_forward_vs_2026"]["rank_correlation"]:.2f}'.replace("-", "−")
    chance_html = (f'    <h3>Can chance explain the BTC pass? Yes</h3>\n'
                   f'    <p>An independent audit of the test (<code>research/results/wf/chance_check.json</code>) counted how many passes chance produces with the same setups, '
                   f'selection and pass rule. <strong>Placebo cells</strong>, built like the real ones but cut loose from the signals (a condition\'s mask moved in time, '
                   f'random masks with a condition\'s share), passed {cb["placebo"]["passed"]} times in {cb["placebo"]["cells"]:,} on BTC: about '
                   f'{cb["placebo"]["expected_passes"]:.1f} chance passes expected among its {cb["cells"]} cells (95% range {cb["placebo"]["ci95"][0]:.2f} to '
                   f'{cb["placebo"]["ci95"][1]:.1f}), against {len(cb["real_passes"])} real passes that are one result (the liquidity sweep holds on about '
                   f'{cb["sweep_share_of_signals_M30"] * 100:.0f}% of the signals, so xlzc_both is xlzc_stoch less a few signals). With each year\'s results '
                   f'<strong>swapped among setups</strong>, which removes any skill in choosing them, {cb["no_skill"]["mean"]:.1f} cells pass per run and two or '
                   f'more in {cb["no_skill"]["at_least_2"] * 100:.0f}% of the runs; M30 xlzc_stoch itself passes in '
                   f'{cb["real_passes_in_nulls"]["M30 xlzc_stoch"]["no_skill_share"] * 100:.0f}% of them: what passed is the rule\'s good years, not the choice of '
                   f'setups. <strong>Counted once per signal</strong> (several picks often take the same one) its {th["walk_forward"]["trades"]} trades of '
                   f'2021 – 2025 are {th["walk_forward"]["signals"]} signals with PF {th["walk_forward"]["pf_signals"]:.2f} instead of {th["walk_forward"]["pf"]:.2f}; '
                   f'in 2026 the 10 largest trades made {th["final"]["net_share_of_10_largest"] * 100:.0f}% of the profit. Across cells, the walk-forward result '
                   f'does not predict the 2026 result (rank correlation {rc(cb)} over {cb["walk_forward_vs_2026"]["cells"]} '
                   f'BTC cells, {rc(cg)} over {cg["walk_forward_vs_2026"]["cells"]} gold cells). On gold the placebo '
                   f'expects {cg["placebo"]["expected_passes"]:.1f} chance passes; none occurred.</p>\n')
    section = f"""<!-- wf:start (generated by research/make_wf_html.py from research/results/wf/*.json) -->
  <section>
    <span class="eyebrow">6 · Year by year on long history</span>
    <h2>{"One BTC result passes; gold has none" if c_b and c_b["confirmed"] and not (c_g and c_g["confirmed"]) else "Nothing holds up year by year"}</h2>
    <p>The method was then tested the way it would be traded: set up on three years, traded on the next year without changes, and rolled forward one year at a time. Gold: Dukascopy prices from 2013 (FTMO for 2025 to mid-May 2026), so ten unseen years, 2016 to 2025. BTC: Binance from 2018, so five unseen years, 2021 to 2025. The last months, 2026 to 13 November, were kept back: they were not used to decide what passes (the tables show them for every cell, as a check). Each year 12,000 setups per timeframe (M1 to H1) were scored on the three years before it with 58 entry conditions added one at a time (market regime, location, confirmation, timing, the XLZC rules, and three random halves of the signals as controls) and the method without one: 59 cells per timeframe. Picks: the best of them, up to 10, one per direction, session and trend-filter family, each holding PF 1.3 in all three years at normal and stressed costs, and with an average cost under 1/8 of the risk. A cell passes with PF 1.3 or more over all its unseen years together, 1.1 or more stressed, at least two unseen years with 50 trades, and no such year below 1.0.</p>
    <p class="note">Costs: gold at VT Markets' own, a 1.5-pip spread (shaped by hour) and $0.60 commission per ounce; BTC a $10 spread. Both, and every dollar distance of a setup, are scaled with the price, so a setup means the same in 2016 as today. Swap is not charged. {sum(c["cells"] for k, c in counts.items() if c["protocol"] == 1):,} cells were tested on gold and BTC; with that many, a few pass by chance. The random controls passed {sum(c["controls_passed"] for k, c in counts.items() if c["protocol"] == 1)} of {sum(c["controls"] for k, c in counts.items() if c["protocol"] == 1)} times.</p>
{chr(10).join(parts)}
{det}{chance_html}{P2_INTRO}
{chr(10).join(parts2)}
{P2_DECISION}
    <p>The 2026 months of the cells that passed: {"; ".join(f'{NAME.get(k, k)} {names(v["confirmed"] + v["flat"] + v["failed"] + v["nopick"])}' for k, v in counts.items())}.</p>
  </section>
<!-- wf:end -->
"""
    s = open(PAGE, encoding="utf-8").read()
    # the verdict line and the "What this means" bullet
    b = counts["BTCUSD"]; gld = counts["XAUUSD"]
    p2c = {k: v for k, v in counts.items() if v["protocol"] == 2}
    p2_txt = ""
    if p2c:
        conf = [(k, r) for k, v in p2c.items() for r in v["confirmed"]]
        fxd = json.load(open(os.path.join(OUT, "fx_decision.json"))) if os.path.exists(os.path.join(OUT, "fx_decision.json")) else {}
        res2 = [f"{k} {c}" for k, v in fxd.items() for c in v.get("results", [])]
        p2_txt = (f' The same test on {" and ".join(NAME.get(k, k) for k in p2c)}, run because gold and BTC did not hold up: '
                  + ("; ".join(f'{NAME.get(k, k)} {v["passed"]} of {v["cells"]} cells met the pass rule' for k, v in p2c.items())
                     if any(v["passed"] for v in p2c.values()) else f'none of their {sum(v["cells"] for v in p2c.values()):,} cells passed')
                  + (f'; under the decision fixed in advance (once per signal, a chance check, the 2026 months) ' + (f'the results are {", ".join(res2)}.' if res2 else 'nothing is a result.')
                     if fxd and any(v["passed"] for v in p2c.values()) else '.'))
    btc_pass = [r for r in sums["BTCUSD"]["rows"] if r["passes"]]
    best = max(btc_pass, key=lambda r: r["final"]["pf"] if r["final"]["n"] else 0) if btc_pass else None
    if best is not None:
        det = next((x for x in details if x["tf"] == best["tf"] and x["condition"] == best["condition"]), None)
        a = det["all_unseen_years"] if det else None
        yrs = ", ".join(f"{f2(y['pf'])} in {y['year']}" for y in best["by_year"] if y["n"])
        th = json.load(open(os.path.join(OUT, "chance_check.json")))["BTCUSD"]
        verdict = (f'<p><strong>Year by year: nothing that holds up.</strong> No gold cell passed. On BTC, M30 with the Stochastic turn rule met the pass rule '
                   f'(set up on three years and traded on the next: {yrs}), but the 2026 months that were kept back gave {f2(best["final"]["pf"])} on '
                   f'{best["final"]["n"]} trades, under 1.3, and an independent audit found that chance alone produces one or two such passes among the '
                   f'{b["cells"]} BTC cells (about {th["placebo"]["expected_passes"]:.1f} expected). Its setups for the year ahead are in the BTC zip as unproven '
                   f'presets: demo only.' + p2_txt + '</p>')
        bullet = (f'<li><strong>Nothing held year by year.</strong> With {sum(c["cells"] for c in counts.values() if c["protocol"] == 1):,} timeframe-and-condition cells tested on gold and BTC, '
                  f'{"no gold cell" if not gld["passed"] else str(gld["passed"]) + " gold cells"} and {b["passed"]} BTC cells (one result) met the pass rule. '
                  f'The BTC one, M30 with the Stochastic turn rule, made {f2(best["final"]["pf"])} in the 2026 months it had not seen, under 1.3, and chance '
                  f'explains a pass like it: a candidate for a demo, not an edge.' + p2_txt + '</li>')
    else:
        verdict = "<p><strong>Year by year: nothing passed</strong> on gold or BTC (section 6).</p>"
        bullet = "<li><strong>Nothing held year by year</strong> on long history, on gold or BTC, with 58 entry conditions tried one at a time.</li>"
    for name, block in (("wf-verdict", verdict), ("wf-bullet", bullet)):
        pat = re.compile(r"<!-- %s:start -->.*?<!-- %s:end -->" % (name, name), flags=re.S)
        assert len(pat.findall(s)) == 1, name
        s = pat.sub(lambda m: f"<!-- {name}:start -->{block}<!-- {name}:end -->", s)
    if "<!-- wf:start" in s:
        s = re.sub(r"<!-- wf:start.*?<!-- wf:end -->\n", lambda m: section, s, flags=re.S)
    else:
        anchor = '  <section>\n    <span class="eyebrow">6 · What this means</span>'
        assert s.count(anchor) == 1
        s = s.replace(anchor, section + "\n" + anchor.replace("6 · What this means", "7 · What this means"))
    open(PAGE, "w", encoding="utf-8").write(s)
    json.dump({k: dict(cells=v["cells"], cells_100=v["cells_100"], passed=v["passed"], controls_passed=v["controls_passed"], controls=v["controls"],
                       confirmed=[(r["tf"], r["condition"]) for r in v["confirmed"]], flat=[(r["tf"], r["condition"]) for r in v["flat"]],
                       failed=[(r["tf"], r["condition"]) for r in v["failed"]], no_final_picks=[(r["tf"], r["condition"]) for r in v["nopick"]])
               for k, v in counts.items()}, open(os.path.join(OUT, "wf_facts.json"), "w"), indent=1)
    print(json.dumps(json.load(open(os.path.join(OUT, "wf_facts.json"))), indent=1))


if __name__ == "__main__":
    main()
