"""Run 2: results2/*.json -> presets, CSV tables and a markdown report."""
import csv, glob, json, os, sys, datetime as dt
import xpw_preset as P, xpw_run as R, xpw_report as X1, xpw_search2 as S

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("XPW_OUT") or os.path.join(HERE, "results2")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out2")
TOP_N = 3
LIVE = {1, 5}
COST_RT_USD = {"XAUUSD": 0.28, "BTCUSD": 0.40}
DIRN = {0: "Both", 1: "Long only", 2: "Short only"}
d = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")
FWD_FROM, FWD_TO = "2026-11-01", "2026-11-12"


def pick(top):
    """Up to TOP_N presets, preferring different entry style / direction combinations."""
    chosen = []; used = set()
    for r in top:
        k = (r["style_i"], r["direction"])
        if k in used: continue
        used.add(k); chosen.append(r)
        if len(chosen) == TOP_N: return chosen
    for r in top:
        if r not in chosen: chosen.append(r)
        if len(chosen) == TOP_N: break
    return sorted(chosen, key=lambda r: r["balanced"], reverse=True)


def describe(p):
    s = X1.describe(p).replace("loss-rev x0;", "loss-rev unlimited;")
    return f"{DIRN[int(p['TradeDir'])]}; " + s


def main():
    os.makedirs(os.path.join(OUT, "presets"), exist_ok=True); os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    summary = []; accepted = []; strata = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "*.json")), key=lambda f: (os.path.basename(f).split("_")[0], S.MIN_IS and {v: k for k, v in S.TF_LABEL.items()}[os.path.basename(f).split("_")[1][:-5]])):
        j = json.load(open(f)); sym = j["symbol"]; tf = int(j["tf"]); lab = j["tf_label"]; spec = R.SYMBOLS[sym]
        chosen = pick(j["top"])
        summary.append(dict(symbol=sym, tf=lab, clock="Live" if tf in LIVE else "Tester only", window=j["window"], bars=j["bars"], evaluated=j["evaluated"],
                            pass_is_oos=j["pass_is_oos"], pass_rules=j["pass_rules"], checked_for_stability=j["checked_for_stability"], stable=j["final"], saved=len(chosen),
                            ref_trades=j["baseline"]["trades"], ref_net_usd=round(j["baseline"]["net"], 2), ref_pf=round(j["baseline"]["pf"], 3)))
        for s in j["strata"]:
            strata.append(dict(symbol=sym, tf=lab, style=s["style"], direction=DIRN[s["direction"]], evaluated=s["evaluated"], is_profitable=s["is_profitable"],
                               pass_is_oos=s["pass_is_oos_distinct"], pass_rules=s["pass_rules"], in_final=sum(1 for r in j["top"] if r["style_i"] == s["style_i"] and r["direction"] == s["direction"]),
                               best_final_oos_net_usd=max([round(r["oos"]["net"], 2) for r in j["top"] if r["style_i"] == s["style_i"] and r["direction"] == s["direction"]], default="")))
        nb = len(j["blocks"]) - 1
        for rank, r in enumerate(chosen, 1):
            p = r["params"]; name = f"{sym}_{lab}_run2_rank{rank}.set"
            fragile = r["all"]["avg"] < 2.0 * COST_RT_USD[sym]
            notes = []
            if fragile: notes.append("Cost-fragile")
            if int(p["TradeDir"]) != 0: notes.append(DIRN[int(p["TradeDir"])])
            live = "live-admitted chart/signal clock" if tf in LIVE else "TESTER-ONLY clock (EA refuses this SigTF on a live chart)"
            header = [
                "XPW v0.9.2 + FlashGold fenced EA 9.23 - complete 157-input preset. Calibration run 2, 2026-11-13 (Python replica backtest, NOT MT5 Strategy Tester).",
                f"Required chart: {P.CHART_SYMBOL[sym]}, {lab}; a .set file does not change the chart period. SigTF={tf} selects the signal period ({live}).",
                f"Way of playing: {r['style']}, {DIRN[int(p['TradeDir'])]}. Data: {spec['data']} 1-minute history, {spec['lot_desc']}; profit in USD per 0.01 lot after modeled costs.",
                f"In-sample {d(j['is_window'][0])}..{d(j['is_window'][1])}: {r['is_']['trades']} trades, net {r['is_']['net']:.0f}, PF {r['is_']['pf']:.2f}, maxDD {r['is_']['maxdd']:.0f}.",
                f"Out-of-sample {d(j['oos_window'][0])}..{d(j['oos_window'][1])}: {r['oos']['trades']} trades, net {r['oos']['net']:.0f}, PF {r['oos']['pf']:.2f}, maxDD {r['oos']['maxdd']:.0f}.",
                f"2x-cost stress: net {r['stress_all']['net']:.0f}, PF {r['stress_all']['pf']:.2f}. Profitable calendar blocks: {sum(1 for b in r['blocks'] if b > 0)} of {nb}. Neighbour stability: {r['stability']['stable_share']:.0%} of {r['stability']['neighbours']} variants.",
                f"Unseen days {FWD_FROM}..{FWD_TO} (open positions valued at the last price): {r['fwd']['trades']} trades, net {r['fwd']['net']:.0f}.",
                "Live execution DISABLED (EnableTrading=false, FenceAllowExecution=false). Native MT5 performance NOT verified.",
            ] + (["WARNING: average profit per trade is below 2x the modeled round-trip cost; very sensitive to real spread/commission."] if fragile else []) \
              + (["NOTE: one-direction preset; part of its result is the market's own trend over the test period."] if int(p["TradeDir"]) != 0 else [])
            P.write_set(os.path.join(OUT, "presets", name), p, sym, tf, f"CAL20261113_{sym}_{lab}_r{rank}", header)
            accepted.append(dict(preset=name, symbol=sym, tf=lab, rank=rank, clock="Live" if tf in LIVE else "Tester only", style=r["style"], direction=DIRN[int(p["TradeDir"])],
                                 is_trades=r["is_"]["trades"], is_net_usd=round(r["is_"]["net"], 2), is_pf=round(r["is_"]["pf"], 3), is_win=round(r["is_"]["win"], 3), is_maxdd_usd=round(r["is_"]["maxdd"], 2),
                                 oos_trades=r["oos"]["trades"], oos_net_usd=round(r["oos"]["net"], 2), oos_pf=round(r["oos"]["pf"], 3), oos_win=round(r["oos"]["win"], 3), oos_maxdd_usd=round(r["oos"]["maxdd"], 2),
                                 all_net_usd=round(r["all"]["net"], 2), all_maxdd_usd=round(r["all"]["maxdd"], 2), avg_trade_usd=round(r["all"]["avg"], 3),
                                 stress2x_net_usd=round(r["stress_all"]["net"], 2), stress2x_pf=round(r["stress_all"]["pf"], 3),
                                 profitable_blocks=f"{sum(1 for b in r['blocks'] if b > 0)}/{nb}", neighbour_stability=round(r["stability"]["stable_share"], 2),
                                 fwd_trades=r["fwd"]["trades"], fwd_net_usd=round(r["fwd"]["net"], 2), note=", ".join(notes), description=describe(p)))

    def wcsv(name, rows):
        with open(os.path.join(OUT, "data", name), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    wcsv("search_summary.csv", summary); wcsv("strata_summary.csv", strata)
    if accepted: wcsv("accepted_presets.csv", accepted)
    fwd1 = list(csv.DictReader(open(os.path.join(HERE, "fwd_run1.csv"))))
    wcsv("run1_forward_test.csv", [{k: r[k] for k in ("preset", "symbol", "tf", "fwd_trades", "fwd_net_usd", "fwd_pf", "fwd_win")} for r in fwd1])

    L = ["# XPW v0.9.2 + FlashGold EA: calibration run 2 (XAUUSD, BTCUSD), 2026-11-13\n",
         "Run 2 searches every way the EA can be played as its own problem: 7 entry styles x 3 trade directions, per symbol and timeframe, over a wider input grid than run 1 and with stricter acceptance. "
         "Results are replica backtests on Binance 1-minute data (PAX Gold as the XAUUSD proxy), **not** MT5 Strategy Tester or broker results. Live gates stay disabled in every preset.\n",
         "## How run 1 did on data it never saw\n",
         f"Before recalibrating, the 33 run-1 presets were run on {FWD_FROM} to {FWD_TO}, published after run 1. Positions still open at the end are valued at the last price.\n",
         "| Symbol | Presets | Made money | Lost money | Did not trade | Combined net (USD per 0.01 lot) |", "|---|---:|---:|---:|---:|---:|"]
    for sym in ("XAUUSD", "BTCUSD"):
        rs = [r for r in fwd1 if r["symbol"] == sym]
        L.append(f"| {sym} | {len(rs)} | {sum(float(r['fwd_net_usd']) > 0 for r in rs)} | {sum(float(r['fwd_net_usd']) < 0 for r in rs)} | {sum(int(r['fwd_trades']) == 0 for r in rs)} | {sum(float(r['fwd_net_usd']) for r in rs):.0f} |")
    L += ["", "Twelve days is a short test. It is the only fully independent evidence available, and it is mixed: fewer than half the presets made money. Per-preset figures are in `data/run1_forward_test.csv`.\n",
          "## Search summary\n",
          "| Symbol | TF | Clock | Window | Combos tested | Pass in and out of sample | Pass cost, block and winner rules | Stability-checked | Stable | Saved | Reference preset net |",
          "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        L.append(f"| {s['symbol']} | {s['tf']} | {s['clock']} | {s['window']} | {s['evaluated']} | {s['pass_is_oos']} | {s['pass_rules']} | {s['checked_for_stability']} | {s['stable']} | {s['saved']} | {s['ref_net_usd']:.0f} ({s['ref_trades']} trades) |")
    L += ["", f"Total combinations tested: **{sum(s['evaluated'] for s in summary):,}**.\n", "## Which ways of playing survive\n",
          "Count of timeframes (out of 6) where at least one stable preset exists for that entry style and direction.\n"]
    for sym in ("XAUUSD", "BTCUSD"):
        L += [f"**{sym}**\n", "| Entry style | Both | Long only | Short only |", "|---|---:|---:|---:|"]
        for st in S.STYLES:
            cells = [str(sum(1 for r in strata if r["symbol"] == sym and r["style"] == st[3] and r["direction"] == dn and r["in_final"] > 0)) for dn in ("Both", "Long only", "Short only")]
            L.append(f"| {st[3]} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["Per-timeframe detail is in `data/strata_summary.csv`.\n", "## Saved presets\n",
          "USD per 0.01 lot (gold: 1 oz; BTC: 0.01 BTC) after modeled spread and commission. Forward = the untouched 2026-11-01 to 2026-11-12 window, never used to pick or accept a preset.\n",
          "| Preset | Clock | Way of playing | IS trades | IS net | IS PF | OOS trades | OOS net | OOS PF | OOS maxDD | 2x-cost net | Blocks | Stability | Fwd trades | Fwd net | Note |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|"]
    for a in accepted:
        L.append(f"| `{a['preset']}` | {a['clock']} | {a['style']}, {a['direction']} | {a['is_trades']} | {a['is_net_usd']:.0f} | {a['is_pf']:.2f} | {a['oos_trades']} | {a['oos_net_usd']:.0f} | {a['oos_pf']:.2f} | {a['oos_maxdd_usd']:.0f} | {a['stress2x_net_usd']:.0f} | {a['profitable_blocks']} | {a['neighbour_stability']:.0%} | {a['fwd_trades']} | {a['fwd_net_usd']:.0f} | {a['note']} |")
    L += ["", "### What each preset does\n"] + [f"- **{a['preset']}**: {a['description']}" for a in accepted]
    if accepted:
        L += ["", "### Forward window, run-2 presets together\n", "| Symbol | Presets | Made money | Lost money | Did not trade | Combined net |", "|---|---:|---:|---:|---:|---:|"]
        for sym in ("XAUUSD", "BTCUSD"):
            rs = [a for a in accepted if a["symbol"] == sym]
            L.append(f"| {sym} | {len(rs)} | {sum(a['fwd_net_usd'] > 0 for a in rs)} | {sum(a['fwd_net_usd'] < 0 for a in rs)} | {sum(a['fwd_trades'] == 0 for a in rs)} | {sum(a['fwd_net_usd'] for a in rs):.0f} |")
    L.append("""
## What changed from run 1

- **Every way of playing gets its own search.** 7 entry styles (BOT/TOP square; Turn with predict stop, at cross, after hold; BOT/TOP tick; CONT at close, CONT stop entry) x 3 directions (both, long only, short only) = 21 searches per symbol and timeframe, half of each starting with the FlashGold filter on.
- **Wider grid.** New or widened inputs: TradeDir, InvertFill, AtrLen, ExAtrLen, MaxChase, ContStopBars, BotMinW/TopMinW, BotNeedLow/TopNeedHigh, FlashGold hold bars, drift bars, TDI lengths, D1 filter/parent/zone timeframes, and more values for stops, targets, trailing, time stop, RSI/MA lengths, squares, wicks and CONT thresholds.
- **Stricter acceptance.** On top of run 1's rules (in-sample and out-of-sample net > 0 with PF >= 1.15, minimum trades and winners, profitable at 2x costs): at most one losing calendar block (yearly blocks, or half-year blocks for the short gold window), and neighbour stability of at least 50 %.
- **Neighbour stability.** For each leading candidate, 24 variants are built by changing one input one step. Only variants whose trades actually differ from the candidate and from each other count. The share that stays profitable overall and out of sample is the stability score. The overall top 30 and the top 5 of every way of playing are checked, so no way of playing is skipped.
- **Drawdown is mark-to-market.** Maximum drawdown includes the paper loss of open positions at each bar close, not only closed trades. Run 1 used closed trades only, so run-2 drawdowns read higher for the same behaviour.
- **Warm-up.** Indicators and the FlashGold filter get 120 days of history before the in-sample window; no trade may open in the warm-up. Run 1 started cold.
- **Unseen days.** 2026-11-01 to 2026-11-12 is reported for every preset and used for nothing else. Positions still open at the end are valued at the last price.
- **Diverse picks.** Up to 3 presets per symbol and timeframe, preferring different entry style / direction combinations.

## Checks on the tooling

- **No look-ahead.** 168 configurations across all styles and directions produce identical trades with and without later data (`tools/causality_test.py`).
- **Search-space bookkeeping is sound.** Inputs that cannot matter for a given way of playing are reset to defaults so duplicates are not re-tested; 1,890 cases confirm that resetting them never changes a single trade (`tools/canon_test.py`).
- **Independent review.** The run-2 search code was reviewed by three reviewers with two adversarial verifiers per finding. Thirteen findings were confirmed and all were fixed before this run, including an inflated stability score, stability checks limited to the overall leaders, closed-trade-only drawdown, a forward window that dropped the final hours, and BTC point inputs re-entering the search at gold scale.

## Caveats

- **Search size cuts both ways.** Testing this many combinations finds more candidates and also more lucky ones. The block, stability and unseen-days columns are there to tell them apart; no rule removes the risk.
- **One-direction presets ride the trend.** Gold rose strongly over 2023-2026, so a long-only gold preset profits partly from that rise, and would lose it in a falling market. They are marked in the Note column.
- **Proxy data, replica engine, clocks, sizing.** As in run 1: PAXG is not the broker's XAUUSD feed, the Python port is not the MT5 tester, only M1/M5 presets run on a live chart, and `QtyFixed` assumes 100 oz (gold) and 1 BTC contracts. See `../CALIBRATION_REPORT.md`.
- **BTC points.** Stops and targets in points assume a 0.01 tick on BTCUSD.c; scale `SlPts`, `TpPts` and the other point inputs if your broker's tick differs.

## Reproduce

```bash
python3 tools/xpw_search2.py          # writes results2/strata/*.json, then results2/*.json (resumable)
python3 tools/xpw_search2.py merge    # re-run acceptance and stability from the saved strata
python3 tools/xpw_report2.py out2     # presets, CSV and this report
python3 tools/causality_test.py       # look-ahead check
python3 tools/canon_test.py 30        # inert-input check
python3 tools/warmup_test.py          # warm-up and drawdown check
python3 tools/fwd_run1.py             # run-1 presets on the unseen days
```
""")
    open(os.path.join(OUT, "CALIBRATION_REPORT.md"), "w").write("\n".join(L))
    print("presets", len(accepted), "jobs", len(summary), "evaluated", sum(s["evaluated"] for s in summary))


if __name__ == "__main__":
    main()
