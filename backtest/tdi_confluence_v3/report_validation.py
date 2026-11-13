"""Markdown tables for RESULTS.md, generated from validation.json so no number is copied by hand.

    python3 report_validation.py [validation.json]
"""
import json, math, sys

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "validation.json"))


def f(v, fmt):
    return "–" if v is None or (isinstance(v, float) and not math.isfinite(v)) else format(v, fmt)


def row(name, s, extra=""):
    if s.get("n", 0) < 3:
        return f"| {name} | {s.get('n', 0)} | – | – | – | – | – | – |{extra}"
    return (f"| {name} | {s['n']} | {f(s['win_pct'], '.0f')} | {f(s['mean_bp'], '+.1f')} | {f(s['pf'], '.2f')} | "
            f"{f(s.get('crt_month'), '+.2f')} / {f(s.get('p_cr_month'), '.4f')} | {f(s.get('crt_6m'), '+.2f')} / {f(s.get('p_cr_6m'), '.4f')} | "
            f"{f(s.get('p_month'), '.4f')} |{extra}")


HEAD = ("| {} | Trades | Win % | Avg bp/trade | Profit factor | Month-clustered t / p | 6-month-clustered t / p | Bootstrap p (as first registered) |{}\n"
        "|---|---|---|---|---|---|---|---|{}")
v = R["verdict"]; b = R["btc_oos"]; T = v["tests"]
NAMES = dict(T1a_month_clustered="T1a: profit, month-clustered t-test", T1b_6month_clustered="T1b: profit, 6-month-block t-test",
             T2_random_timing="T2: beats random entry timing", T3_shuffled_sides="T3: long/short calls carry information")
print(f"**Verdict: {v['text']}**\n")
print("| Test | p | Pass mark | Result |\n|---|---|---|---|")
for k, p in T.items():
    print(f"| {NAMES.get(k, k)} | {f(p, '.6f')} | < {R['alpha']} | {'pass' if p is not None and p < R['alpha'] else 'fail'} |")
p4 = v["T4_worst_leave_one_year_out_p"]
t4 = v.get("T4_passed", p4 is not None and p4 < R["alpha_loyo"])
print(f"| T4: consistent without any single year (worst p{'' if v.get('T4_all_years_defined', True) else '; a year left too few trades'}) | {f(p4, '.4f')} | < {R['alpha_loyo']} | {'pass' if t4 else 'fail'} |")
rt = v["realistic_tests"]
print(f"| Realistic execution: T1a / T1b | {f(rt['T1a'], '.4f')} / {f(rt['T1b'], '.4f')} | < {R['alpha']} | {'pass' if v['realistic'] else 'fail'} |\n")
if b.get("lcb98_cr") is not None:
    print(f"98% one-sided bounds on the average: above {b['lcb98_cr']:+.1f} bp and below {b['ucb98_cr']:+.1f} bp per trade (month-clustered).\n")
if R.get("btc_excluded_months"):
    print(f"Months without trading (stale prices, Amendment 1): {', '.join(R['btc_excluded_months'])}.\n")
print("### Primary test: BTCUSDT, unseen history\n")
print(HEAD.format("Cost per side", "", ""))
for k, s in R["btc_oos_costs"].items():
    print(row(k, s))
print(row("Realistic execution", R["btc_oos_realistic"]))
print(row("Without the stale-price exclusion", R["btc_oos_no_exclusion"]))
print(row("Shorts dropped before 2019-09-13", R["btc_oos_long_only_before_2019_09_13"]))
sr = R["btc_oos_R"]
print(f"\nIn R (return ÷ stop distance): {sr['n']} trades, average {f(sr.get('mean_bp'), '+.3f')} R, month-clustered p {f(sr.get('p_cr_month'), '.4f')}, 6-month p {f(sr.get('p_cr_6m'), '.4f')}.")
ph = R["btc_oos_phase_shift"]
print(f"Month boundaries shifted by 0–29 days: month-clustered p between {ph['min']:.4f} and {ph['max']:.4f} (median {ph['median']:.4f}).")
nt, nd = R["btc_null_timing"], R["btc_null_direction"]
for lab, nn in (("Random timing (T2)", nt), ("Shuffled long/short labels (T3)", nd)):
    print(f"\n- **{lab}:** {nn['n']} runs with {f(nn['trades_avg'], '.0f')} trades each on average (real: {b['n']}); their average {f(nn['mean'], '+.1f')} bp "
          f"vs the rule's {f(b.get('mean_bp'), '+.1f')} bp. Verdict statistic: month-clustered t {f(nn.get('t_centered'), '+.2f')}, p = {f(nn.get('p_centered'), '.4f')}. "
          f"Permutation p-values, reported only (not the verdict, see Amendment 1): on the trade-level t {f(nn['p_t'], '.4f')} "
          f"({nn['count_t_ge_real']} runs reached it), on the raw average {f(nn['p_mean'], '.4f')} ({nn['count_mean_ge_real']} runs).", end="")
print()
print(f"- **Risk:** worst drawdown {R['btc_oos_maxdd_bp']:.0f} bp of one position's notional, worst trade {R['btc_oos_worst_trade_bp']:.0f} bp.")
if "power" in R:
    pw = R["power"]
    print(f"- **Power, each test alone:** an edge of about {f(pw.get('mde80_T1a_alone_bp'), '.0f')} bp would pass T1a, and about {f(pw.get('mde80_T1b_alone_bp'), '.0f')} bp T1b, "
          f"80% of the time on this data ({f(pw.get('mde80_iid_bp'), '.0f')} bp if trades were independent). The full verdict needs all five tests and has lower power (Amendment 1, 8.5).")
print("\n| Year | Trades | Win % | Avg bp/trade | Total bp | Without this year: avg bp / month-clustered p (T4) |\n|---|---|---|---|---|---|")
for y, s in R["btc_oos_years"].items():
    lo = R["btc_oos_leave_one_year_out"][y]
    print(f"| {y} | {s['n']} | {s['win_pct']:.0f} | {s['mean_bp']:+.1f} | {s['total_bp']:+.0f} | {f(lo['mean_bp'], '+.1f')} / {f(lo['p_cr_month'], '.3f')} |")
print("\n" + HEAD.format("Side", "", ""))
print(row("Long", R["btc_oos_long"])); print(row("Short", R["btc_oos_short"]))
print("\n### Neighbours on the same unseen BTC data (descriptive)\n")
print(HEAD.format("Change from the frozen rule", "", ""))
print(row("none (frozen rule)", b))
for k, s in R["btc_oos_neighbours"].items():
    print(row(k, s))
nr = R["neighbours_reading"]
print(f"\n{nr['positive']} of {nr['of']} neighbours have a positive average. Pre-set reading: **{nr['label']}** (a plateau needs at least 9).")
print("\n### Other coins (surviving large caps; supporting only, same calendar period as the BTC test)\n")
print(HEAD.format("Coin, before 2024-11", " Random timing p |", "---|"))
A = R["alts"]
for sym in [k for k in A if not k.startswith("pooled")]:
    print(row(sym, A[sym]["clean"], f" {f(A[sym]['clean'].get('p_random_timing'), '.4f')} |"))
pc = A["pooled_clean"]
nco = len([k for k in A if not k.startswith("pooled")])
print(row(f"**All {nco} pooled**", pc, " – |"))
oc = R["other_coins"]
print(f"\nPooled: {pc.get('coins_positive', '–')} of {nco} coins positive, equal-weight average {f(pc.get('equal_weight_by_coin_bp'), '+.1f')} bp, "
      f"in R {f(pc.get('R_mean'), '+.3f')} (p {f(pc.get('R_p_cr_month'), '.4f')}). Pre-set reading: **{oc['reading']}** "
      f"(pooled month-clustered p = {f(oc['p_cr_month'], '.4f')}, 6-month p = {f(oc['p_cr_6m'], '.4f')}). "
      f"Correlation of monthly results with BTC: {f(oc.get('monthly_corr_with_btc'), '.2f')}.\n")
print(HEAD.format("Coin, 2024-11 → 2026-11 (descriptive)", "", ""))
for sym in [k for k in A if not k.startswith("pooled")]:
    print(row(sym, A[sym]["after"]))
print(row(f"**All {nco} pooled**", A["pooled_after"]))
pv = R.get("provenance", {})
print(f"\n*Run: commit `{pv.get('git_head', '?')[:12]}`, started {pv.get('started_utc', '?')}, finished {R.get('finished_utc', '?')}; "
      f"python {pv.get('versions', {}).get('python', '?')}, numpy {pv.get('versions', {}).get('numpy', '?')}, pandas {pv.get('versions', {}).get('pandas', '?')}, numba {pv.get('versions', {}).get('numba', '?')}.*")
