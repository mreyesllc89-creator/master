"""Markdown tables for RESULTS.md, generated from validation.json so no number is copied by hand.

    python3 report_validation.py [validation.json]
"""
import json, sys

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "validation.json"))


def row(name, s, extra=""):
    if s.get("n", 0) < 3:
        return f"| {name} | {s.get('n', 0)} | – | – | – | – | – | – |{extra}"
    return (f"| {name} | {s['n']} | {s['win_pct']:.0f} | {s['mean_bp']:+.1f} | {s['t']:+.2f} | {s['pf']:.2f} | "
            f"{s['p_month']:.4f} | {s['lcb98_month']:+.1f} |{extra}")


HEAD = "| {} | Trades | Win % | Avg bp/trade | t | Profit factor | p (month blocks) | 98% lower bound, bp |{}\n|---|---|---|---|---|---|---|---|{}"
v = R["verdict"]; b = R["btc_oos"]
print(f"**Verdict: {v['text']}**  (p1 = {v['p1_profit']:.4f}, p2 = {v['p2_random_timing']:.4f}; both must be below {v['alpha']})\n")
print("### Primary test: BTCUSDT, unseen history\n")
print(HEAD.format("Cost per side", "", ""))
for k, s in R["btc_oos_costs"].items():
    print(row(k, s))
nt, nd = R["btc_null_timing"], R["btc_null_direction"]
print(f"\n- **T1, profit:** p1 = {b['p_month']:.4f} (week blocks {b['p_week']:.4f}, plain t-test {b['p_t']:.4f}); 95% interval for the average {b['ci95_month'][0]:+.1f} to {b['ci95_month'][1]:+.1f} bp over {b['months']} months.")
print(f"- **T2, random timing:** {nt['n']} random-entry runs averaged {nt['mean']:+.1f} bp (98th percentile {nt['q98']:+.1f}, best {nt['max']:+.1f}); p2 = {nt['p']:.4f}.")
print(f"- **T3, shuffled long/short labels:** {nd['n']} runs averaged {nd['mean']:+.1f} bp (98th percentile {nd['q98']:+.1f}, best {nd['max']:+.1f}); p3 = {nd['p']:.4f}.")
print(f"- **Risk:** worst drawdown {R['btc_oos_maxdd_bp']:.0f} bp of one position's notional, worst trade {R['btc_oos_worst_trade_bp']:.0f} bp.")
pw = R["power"]
print(f"- **Power:** with {b['n']} trades the test detects a true edge of {pw['mde80_bp']:.0f} bp or more 80% of the time." +
      (f" At the observed average it would take about {pw['trades_needed_for_observed']:.0f} trades to prove." if pw.get("trades_needed_for_observed") else ""))
print("\n| Year | Trades | Win % | Avg bp/trade | Total bp |\n|---|---|---|---|---|")
for y, s in R["btc_oos_years"].items():
    print(f"| {y} | {s['n']} | {s['win_pct']:.0f} | {s['mean_bp']:+.1f} | {s['total_bp']:+.0f} |")
print("\n" + HEAD.format("Side", "", ""))
print(row("Long", R["btc_oos_long"])); print(row("Short", R["btc_oos_short"]))
print("\n### Neighbours on the same unseen BTC data (descriptive)\n")
print(HEAD.format("Change from the frozen rule", "", ""))
print(row("none (frozen rule)", b))
for k, s in R["btc_oos_neighbours"].items():
    print(row(k, s))
print("\n### Replication on six other coins\n")
print(HEAD.format("Coin, before 2024-11", " vs random timing, p |", "---|"))
A = R["alts"]
for sym in [k for k in A if not k.startswith("pooled")]:
    print(row(sym, A[sym]["clean"], f" {A[sym]['clean'].get('p_random_timing', float('nan')):.4f} |"))
pc = A["pooled_clean"]
print(row("**All six pooled**", pc, " – |"))
print(f"\nPooled: {pc['coins_positive']} of 6 coins positive, equal-weight average {pc['equal_weight_by_coin_bp']:+.1f} bp. "
      f"Replication rule (pooled p < {v['alpha']}): **{'replicates' if R['replication']['replicates'] else 'does not replicate'}** (p = {R['replication']['p_pooled_clean']:.4f}).\n")
print(HEAD.format("Coin, 2024-11 → 2026-11 (descriptive)", "", ""))
for sym in [k for k in A if not k.startswith("pooled")]:
    print(row(sym, A[sym]["after"]))
print(row("**All six pooled**", A["pooled_after"]))
