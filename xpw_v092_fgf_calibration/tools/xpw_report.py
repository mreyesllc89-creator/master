"""Turn results/*.json into .set presets, CSV tables and a markdown report."""
import csv, glob, json, os, sys, datetime as dt
import xpw_preset as P
import xpw_run as R

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
TOP_N = 3
MIN_WINNERS_IS = 15
MIN_WINNERS_OOS = 8
# modeled round-trip cost per 0.01 lot in USD (gold: 28 pts on 1 oz; BTC: ~0.04 % of ~100k on 0.01 BTC)
COST_RT_USD = {"XAUUSD": 0.28, "BTCUSD": 0.40}
TF_LABEL = {1: "M1", 5: "M5", 15: "M15", 30: "M30", 60: "H1", 240: "H4"}
LIVE_ADMITTED = {1, 5}  # XpwV92ClockPairAdmitted: live charts admit M1->1/5, M5->1/5 (and M10/M15->10); others tester-only
ENUM_TF = R.ENUM_TF


def d(ts): return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def tfname(v): return TF_LABEL.get(ENUM_TF.get(int(v), 0), f"{ENUM_TF.get(int(v), v)}min")


def describe(p):
    sig = {0: "BOT/TOP square", 1: "Turn", 2: "BOT/TOP tick", 3: "CONT"}[int(p["SigMode"])]
    if int(p["SigMode"]) == 1: sig += " / " + {0: "predict stop", 1: "at cross", 2: "after hold"}[int(p["TurnEntry"])]
    if int(p["SigMode"]) == 3: sig += " / " + {0: "at close", 1: "stop past candle"}[int(p["ContEntry"])]
    opp = {0: "reverse", 1: "close only", 2: "ignore"}[int(p["OppMode"])]
    if int(p["ExitUnit"]) == 0:
        ex = f"SL {p['SlPts']:.0f} / TP {p['TpPts']:.0f} pts" + (f", trail act {p['TrActPts']:.0f} dist {p['TrDisPts']:.0f}" if p["TrailOn"] else ", no trail")
    else:
        ex = f"SL {p['SlAtrM']}xATR / TP {p['TpR']}R" + (f", trail act {p['TrActAtr']}xATR dist {p['TrDisAtr']}xATR" if p["TrailOn"] else ", no trail")
    ts = f", time stop {p['TimeStop']} bars" if int(p["TimeStop"]) > 0 else ""
    lr = f"loss-rev x{p['LossRevMax']}" if p["LossRevOn"] else "no loss-rev"
    fgf = (f"FGF on: filter {tfname(p['fgfTf'])}, parent {tfname(p['fgfParentTf'])}, zones {tfname(p['fgfZTf1'])}/{tfname(p['fgfZTf2'])}/{tfname(p['fgfZTf3'])}, "
           f"band {p['fgfBandAtr']}xATR, burst {p['fgfBurstAtr']}xATR, minAligned {p['fgfMinAligned']}, against={p['fgfAgainst']}, window={['next signal','minutes','candles'][int(p['fgfLast'])]}")
    if not p["fgfOn"]: fgf = "FGF off"
    ind = f"RSI {p['RsiLen']} fast {p['FastLen']} slow {p['SlowLen']}, turnMax {p['TurnMax']} hold {p['TurnHold']}, allOn={p['AllOn']}"
    return f"{sig}; opp {opp}; {ex}{ts}; {lr}; {ind}; {fgf}"


def main():
    os.makedirs(os.path.join(OUT, "presets"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "data", "all_candidates"), exist_ok=True)
    summary = []; accepted_rows = []
    files = sorted(glob.glob(os.path.join(RESULTS, "*.json")))
    for f in files:
        j = json.load(open(f))
        sym, tf = j["symbol"], int(j["tf"])
        lab = TF_LABEL[tf]
        spec = R.SYMBOLS[sym]
        base = j["baseline"]
        summary.append(dict(symbol=sym, tf=lab, bars=j["bars"], window=j["window"], evaluated=j["evaluated"],
                            candidates_is_oos=j.get("candidates_before_stress", ""), accepted=j["accepted"],
                            baseline_net_usd=round(base["all"]["net"], 2), baseline_trades=base["all"]["trades"], baseline_pf=round(base["all"]["pf"], 3),
                            best_net_usd=round(j["top"][0]["all"]["net"], 2) if j["top"] else "", elapsed_min=round(j["elapsed_s"] / 60, 1)))
        with open(os.path.join(OUT, "data", "all_candidates", f"{sym}_{lab}.csv"), "w", newline="") as cf:
            w = csv.writer(cf)
            w.writerow(["gen", "score", "is_trades", "is_net_usd", "is_pf", "is_maxdd_usd", "oos_trades", "oos_net_usd", "oos_pf", "oos_maxdd_usd", "all_trades", "all_net_usd", "all_pf", "all_maxdd_usd"])
            for r in j["all_rows"]:
                w.writerow([r["gen"], round(r["score"], 2), r["is_"]["trades"], round(r["is_"]["net"], 2), round(r["is_"]["pf"], 3), round(r["is_"]["maxdd"], 2),
                            r["oos"]["trades"], round(r["oos"]["net"], 2), round(r["oos"]["pf"], 3), round(r["oos"]["maxdd"], 2),
                            r["all"]["trades"], round(r["all"]["net"], 2), round(r["all"]["pf"], 3), round(r["all"]["maxdd"], 2)])
        # statistical sanity: enough winning trades in both windows (no lottery-ticket presets)
        sane = [r for r in j["top"] if r["is_"]["win"] * r["is_"]["trades"] >= MIN_WINNERS_IS and r["oos"]["win"] * r["oos"]["trades"] >= MIN_WINNERS_OOS]
        summary[-1]["dropped_too_few_winners"] = len(j["top"]) - len(sane)
        for rank, r in enumerate(sane[:TOP_N], 1):
            p = r["params"]
            cost_rt = COST_RT_USD[sym]
            fragile = r["all"]["avg"] < 2.0 * cost_rt
            tag = f"CAL20261106_{sym}_{lab}_r{rank}"
            name = f"{sym}_{lab}_rank{rank}.set"
            live = "live-admitted chart/signal clock" if tf in LIVE_ADMITTED else "TESTER-ONLY clock (EA refuses this SigTF on a live chart)"
            header = [
                f"XPW v0.9.2 + FlashGold fenced EA 9.23 - complete 157-input preset. Calibrated 2026-11-06 (Python replica backtest, NOT MT5 Strategy Tester).",
                f"Required chart: {P.CHART_SYMBOL[sym]}, {lab}; a .set file does not change the chart period. SigTF={tf} selects the signal period ({live}).",
                f"Data: {spec['data']} 1-minute history ({j['window']}), {spec['lot_desc']}; costs modeled: see CALIBRATION_REPORT.md.",
                f"In-sample {d(j['is_window'][0])}..{d(j['is_window'][1])}: {r['is_']['trades']} trades, net {r['is_']['net']:.0f} USD, PF {r['is_']['pf']:.2f}, maxDD {r['is_']['maxdd']:.0f} USD.",
                f"Out-of-sample {d(j['oos_window'][0])}..{d(j['oos_window'][1])}: {r['oos']['trades']} trades, net {r['oos']['net']:.0f} USD, PF {r['oos']['pf']:.2f}, maxDD {r['oos']['maxdd']:.0f} USD.",
                f"2x-cost stress (full period): net {r['stress_all']['net']:.0f} USD, PF {r['stress_all']['pf']:.2f}.",
                f"Live execution DISABLED (EnableTrading=false, FenceAllowExecution=false). Native MT5 performance NOT verified. Profit per 0.01 lot.",
            ] + ([f"WARNING: average profit per trade ({r['all']['avg']:.2f} USD) is below 2x the modeled round-trip cost; very sensitive to real spread/commission."] if fragile else [])
            P.write_set(os.path.join(OUT, "presets", name), p, sym, tf, tag, header)
            accepted_rows.append(dict(symbol=sym, tf=lab, rank=rank, preset=name, live_clock=tf in LIVE_ADMITTED, cost_fragile=fragile,
                                      is_trades=r["is_"]["trades"], is_net_usd=round(r["is_"]["net"], 2), is_pf=round(r["is_"]["pf"], 3), is_win=round(r["is_"]["win"], 3), is_maxdd_usd=round(r["is_"]["maxdd"], 2),
                                      oos_trades=r["oos"]["trades"], oos_net_usd=round(r["oos"]["net"], 2), oos_pf=round(r["oos"]["pf"], 3), oos_win=round(r["oos"]["win"], 3), oos_maxdd_usd=round(r["oos"]["maxdd"], 2),
                                      all_trades=r["all"]["trades"], all_net_usd=round(r["all"]["net"], 2), all_pf=round(r["all"]["pf"], 3), all_maxdd_usd=round(r["all"]["maxdd"], 2), all_avg_usd=round(r["all"]["avg"], 3),
                                      stress2x_net_usd=round(r["stress_all"]["net"], 2), stress2x_pf=round(r["stress_all"]["pf"], 3),
                                      description=describe(p)))
    with open(os.path.join(OUT, "data", "search_summary.csv"), "w", newline="") as cf:
        w = csv.DictWriter(cf, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)
    if accepted_rows:
        with open(os.path.join(OUT, "data", "accepted_presets.csv"), "w", newline="") as cf:
            w = csv.DictWriter(cf, fieldnames=list(accepted_rows[0].keys())); w.writeheader(); w.writerows(accepted_rows)
    # markdown report
    L = []
    L.append("# XPW v0.9.2 + FlashGold EA: input calibration (XAUUSD, BTCUSD), 2026-11-06\n")
    L.append("Presets in `presets/` are the input combinations that stayed profitable in-sample, out-of-sample and under doubled trading costs in a Python replica of the EA's decision logic. "
             "This is **not** an MT5 Strategy Tester result and **not** live-broker evidence; all live gates in the presets remain disabled (`EnableTrading=false`, `FenceAllowExecution=false`).\n")
    L.append("## Search summary\n")
    L.append("| Symbol | TF | Bars | Data window | Combos evaluated | Pass IS+OOS | Pass 2x-cost stress | Saved presets | Reference-preset net (USD/0.01 lot) |")
    L.append("|---|---|---:|---|---:|---:|---:|---:|---:|")
    for s in summary:
        saved = sum(1 for a in accepted_rows if a["symbol"] == s["symbol"] and a["tf"] == s["tf"])
        L.append(f"| {s['symbol']} | {s['tf']} | {s['bars']} | {s['window']} | {s['evaluated']} | {s['candidates_is_oos']} | {s['accepted']} | {saved} | {s['baseline_net_usd']} ({s['baseline_trades']} trades, PF {s['baseline_pf']}) |")
    L.append("")
    L.append("## Accepted presets\n")
    L.append("Profit figures are USD per 0.01 lot (gold: 1 oz; BTC: 0.01 BTC) after modeled spread and commission. IS = in-sample selection window, OOS = out-of-sample validation window, 2x = full period with spread and commission doubled.\n")
    L.append("| Preset | Clock | IS trades | IS net | IS PF | IS win | IS maxDD | OOS trades | OOS net | OOS PF | OOS win | OOS maxDD | 2x-cost net | 2x PF | Avg/trade | Note |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for a in accepted_rows:
        L.append(f"| `{a['preset']}` | {'live' if a['live_clock'] else 'tester-only'} | {a['is_trades']} | {a['is_net_usd']:.0f} | {a['is_pf']:.2f} | {a['is_win']:.2f} | {a['is_maxdd_usd']:.0f} | {a['oos_trades']} | {a['oos_net_usd']:.0f} | {a['oos_pf']:.2f} | {a['oos_win']:.2f} | {a['oos_maxdd_usd']:.0f} | {a['stress2x_net_usd']:.0f} | {a['stress2x_pf']:.2f} | {a['all_avg_usd']:.2f} | {'cost-fragile' if a['cost_fragile'] else ''} |")
    L.append("")
    L.append("### What each preset does\n")
    for a in accepted_rows:
        L.append(f"- **{a['preset']}**: {a['description']}")
    L.append("")
    L.append("""## Method

1. **Logic port.** The EA's pure decision code was ported line by line to Python/numba (`tools/xpw_engine.py`): RSI/SMA/ATR and square detection (`ShapeMapV7Core`), crosses, turns, wick ticks and the inverse-Wilder prediction (`ShapeMapV8Core`), the CONT state machine (`ShapeMapV92Core`), the ordered command planner incl. loss/tiny reversal (`ShapeMapV92Execution`), exit distances and trailing (`ShapeMapV8Execution`), and the FlashGold direction filter with TDI zones, burst signal and permission gate (`FlashGold/DirectionFilterCore` + the Filter indicator's bar mapping). Chart period = signal period for every run.
2. **Data.** Binance Vision 1-minute klines: `BTCUSDT` for BTCUSD and `PAXGUSDT` (PAX Gold, a tokenised ounce) as the XAUUSD proxy, 2023-01 to 2026-10. Gold bars outside a typical XAUUSD quote session (weekends, 00:00-00:59 server time) were removed; timestamps shifted to UTC+2 so H1/H4 bars align like an EET MT5 server. PAXG traded in whole dollars before 2025-05, so gold M1/M5/M15 use 2025-05..2026-10 only; gold M30/H1/H4 and all BTC runs use the full span.
3. **Fills.** Signals are evaluated on closed bars (`EnterTick=false` in every preset, matching the backtest). Market orders fill at the next bar open, virtual stop entries at max(stop, open) inside the 1-minute sub-bar that reaches them, SL/TP/trailing are resolved on 1-minute sub-bars with the stop loss assumed first when both are reachable and the pessimistic high-then-low order for trailing. One position at a time, fixed 0.01 lot (the cent gate rejects any other volume).
4. **Costs.** XAUUSD: 25-point spread + 3-point commission per trade (0.28 USD per oz round trip). BTCUSD: 0.03 % spread + 0.01 % commission of price. Acceptance additionally requires profit with both doubled.
5. **Search.** Per symbol and timeframe: the reference preset, then random sampling over the input grid in `tools/xpw_search.py` (signal mode, turn/CONT entry style, opposite-signal mode, exits in points or ATR, trailing, time stop, loss reversal, RSI/MA lengths, square geometry, wick and CONT thresholds, FlashGold filter on/off and its timeframes, band, burst, zones), followed by 3-5 rounds of mutating the best in-sample candidates.
6. **Acceptance.** In-sample net > 0 and PF >= 1.15 with a minimum trade count, out-of-sample net > 0 and PF >= 1.15, net > 0 in both windows with 2x costs, and at least 15 (IS) / 8 (OOS) winning trades so a handful of outliers cannot carry a preset. Ranked by the weaker of the annualised IS and OOS profits, weighted by the weaker profit factor and the recovery factor. Up to 3 distinct presets per symbol/timeframe are saved. "cost-fragile" marks presets whose average profit per trade is below twice the modeled round-trip cost.

## Caveats (read before using)

- **Proxy data.** PAXG is not the broker's XAUUSD-ECNc feed (different spreads, no session gaps, coarse ticks before 2025-05); BTCUSDT spot is not BTCUSD.c. Expect lower performance on the broker feed; re-test every preset in the MT5 Strategy Tester with real tick data before any consideration of live use.
- **Replica, not the EA.** The port follows the MQL5 sources but was not cross-checked against native tester output in this environment (no MetaTrader here). Timing differences remain: the EA re-plans on every tick, the replica once per closed bar; loss-reversal entries fill at the next bar open instead of the next tick.
- **Overfitting risk.** Thousands of combinations were tried per symbol/timeframe; even with an out-of-sample window and cost stress, the accepted presets are the survivors of a search and will degrade. Treat the OOS and 2x-cost columns as the realistic expectation, not the IS column.
- **Clocks.** The EA admits only M1/M5 charts with SigTF 1 or 5 (and M10/M15 with 10) outside the Strategy Tester (`XpwV92ClockPairAdmitted`). M15/M30/H1/H4 presets here are tester-only and were produced because the calibration brief covered six timeframes.
- **Sizing fix.** The reference presets carried `QtyFixed=0.01` (gold, oz) and `0.0001` (BTC), which the EA floors to 0 lots, and the cent gate requires exactly 0.01 lots. All calibrated presets use `QtyFixed=1.0` (gold, 100 oz contract) and `0.01` (BTC, 1 BTC contract) so the source quantity maps to 0.01 lots; verify the broker contract sizes.
- **Risk gates untouched.** `EnableTrading`, `FenceAllowExecution`, the fence capital and the cent-gate limits are exactly as in the handoff package. Nothing here is approval to trade.

## Reproduce

```bash
pip install numpy numba
python3 tools/xpw_data.py        # expects Binance Vision monthly 1m zips under ../data/<SYMBOL>/
python3 tools/xpw_search.py      # writes results/*.json (about 30-60 min on 4 cores)
python3 tools/xpw_report.py out  # presets + CSV + this report
```
""")
    with open(os.path.join(OUT, "CALIBRATION_REPORT.md"), "w") as f:
        f.write("\n".join(L))
    print("presets:", len(accepted_rows), "jobs:", len(summary))


if __name__ == "__main__":
    main()
