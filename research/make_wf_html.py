#!/usr/bin/env python3
"""
Section 6 of research/reports/loma_oos_review.html: the year-by-year test on long history (hump_wf.py), written
between the <!-- wf:start --> and <!-- wf:end --> markers (inserted before "What this means" on the first run).
Also writes research/results/wf/<sym>_wf_summary.json, the compact per-cell results the section is built from.

Usage (repository root):
  python3 research/make_wf_html.py <xauusd wf json> <btcusd wf json> [<detail json of a passing cell> ...]
The wf jsons are written by "hump_wf.py wf"; the detail jsons by "hump_wf.py detail".
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
                         final=dict(year=r["final"]["year"], picks=len(r["final"]["picks"]), n=r["final"]["n"], pf=r["final"]["pf"],
                                    stress_pf=r["final"]["stress_pf"], net_r=r["final"]["win"] - r["final"]["loss"])))
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
    for fn in sys.argv[1:3]:
        d = compact(json.load(open(fn)))
        sym = d["symbol"].lower()
        json.dump(d, open(os.path.join(OUT, f"{sym}_wf_summary.json"), "w"), indent=1, default=float)
        sums[d["symbol"]] = d
    details = [json.load(open(f)) for f in sys.argv[3:]]

    def table(d, rows, title):
        years = [y["year"] for y in rows[0]["by_year"]] if rows else []
        head = "".join(f"<th>{y}</th>" for y in years)
        body = []
        for r in rows:
            fin = r["final"]
            fcls = ' class="loss"' if fin["n"] and fin["pf"] < 1 else (' class="gain"' if fin["n"] and fin["pf"] >= 1.3 else "")
            body.append(f'          <tr><td>{r["tf"]} · {r["text"]}</td>{"".join(ycell(y) for y in r["by_year"])}'
                        f'<td{" class=\"gain\"" if r["passes"] else ""}>{f2(r["pf"])} <span class="sub">{r["n"]} · stressed {f2(r["stress_pf"])}</span></td>'
                        f'<td{fcls}>{f2(fin["pf"]) if fin["n"] else "no picks"} <span class="sub">{fin["n"]}</span></td></tr>')
        return (f'    <h3>{title}</h3>\n    <div class="tablebox">\n      <table>\n        <thead><tr><th>Timeframe · condition</th>{head}'
                f'<th>Unseen years together<span class="sub">PF · trades</span></th><th>Final check {rows[0]["final"]["year"] if rows else ""}<span class="sub">never used to decide</span></th></tr></thead>\n'
                f'        <tbody>\n' + "\n".join(body) + '\n        </tbody>\n      </table>\n    </div>')

    parts = []
    counts = {}
    for sym, d in sums.items():
        rows = d["rows"]
        passed = [r for r in rows if r["passes"]]
        base = [r for r in rows if r["condition"] == "base"]
        ctrl = [r for r in rows if r["group"] == "control"]
        counts[sym] = dict(cells=len(rows), cells_100=sum(1 for r in rows if r["n"] >= 100), passed=len(passed),
                           confirmed=[r for r in passed if r["final"]["n"] and r["final"]["pf"] >= 1.3],
                           flat=[r for r in passed if r["final"]["n"] and 1.0 <= r["final"]["pf"] < 1.3],
                           failed=[r for r in passed if r["final"]["n"] and r["final"]["pf"] < 1.0],
                           nopick=[r for r in passed if not r["final"]["n"]], controls_passed=sum(1 for r in ctrl if r["passes"]), controls=len(ctrl))
        name = "Gold" if sym == "XAUUSD" else "BTC"
        if passed:
            parts.append(table(d, sorted(passed, key=lambda r: -r["pf"]), f"{name}: the timeframe-and-condition cells that passed"))
        else:
            parts.append(f"    <h3>{name}: no cell passed</h3>")
        parts.append(table(d, base, f"{name}: the method without an extra condition"))
    c_g, c_b = counts.get("XAUUSD"), counts.get("BTCUSD")

    def names(lst):
        return ", ".join(f'{r["tf"]} {r["condition"]} ({f2(r["final"]["pf"]) if r["final"]["n"] else "no picks"})' for r in lst) or "none"

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
    <p class="note">Costs: gold at VT Markets' own, a 1.5-pip spread (shaped by hour) and $0.60 commission per ounce; BTC a $10 spread. Both, and every dollar distance of a setup, are scaled with the price, so a setup means the same in 2016 as today. Swap is not charged. {total_cells:,} cells were tested; with that many, a few pass by chance. The random controls passed {sum(c["controls_passed"] for c in counts.values())} of {sum(c["controls"] for c in counts.values())} times.</p>
{chr(10).join(parts)}
{det}{chance_html}    <p>The 2026 months of the cells that passed: gold {names(c_g["confirmed"] + c_g["flat"] + c_g["failed"] + c_g["nopick"]) if c_g else "–"}; BTC {names(c_b["confirmed"] + c_b["flat"] + c_b["failed"] + c_b["nopick"]) if c_b else "–"}.</p>
  </section>
<!-- wf:end -->
"""
    s = open(PAGE, encoding="utf-8").read()
    # the verdict line and the "What this means" bullet
    b = counts["BTCUSD"]; gld = counts["XAUUSD"]
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
                   f'presets: demo only.</p>')
        bullet = (f'<li><strong>Nothing held year by year.</strong> With {total_cells:,} timeframe-and-condition cells tested on long history, '
                  f'{"no gold cell" if not gld["passed"] else str(gld["passed"]) + " gold cells"} and {b["passed"]} BTC cells (one result) met the pass rule. '
                  f'The BTC one, M30 with the Stochastic turn rule, made {f2(best["final"]["pf"])} in the 2026 months it had not seen, under 1.3, and chance '
                  f'explains a pass like it: a candidate for a demo, not an edge.</li>')
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
