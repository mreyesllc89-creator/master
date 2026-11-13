"""Top 20 run-2 presets across timeframes: 10 per symbol, at most 2 per timeframe, different ways of playing
within a timeframe. Ranked by a scale-free robustness score that never looks at the unseen days:
    min(in-sample PF, out-of-sample PF, 3) x neighbour stability x min(1, recovery factor / 3)."""
import csv, glob, json, os, sys, datetime as dt
import xpw_preset as P, xpw_run as R, xpw_report2 as X2, xpw_search2 as S

RES = os.environ.get("XPW_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "results2")
OUT = sys.argv[1]
PER_SYMBOL, PER_TF = 10, 2
d = X2.d


def score(r):
    return min(r["is_"]["pf"], r["oos"]["pf"], 3.0) * r["stability"]["stable_share"] * min(1.0, r["all"]["rf"] / 3.0)


def main():
    os.makedirs(os.path.join(OUT, "top20"), exist_ok=True)
    rows = []
    for f in glob.glob(os.path.join(RES, "*.json")):
        j = json.load(open(f))
        for r in j["top"]:
            rows.append((score(r), j, r))
    rows.sort(key=lambda x: -x[0])
    chosen = []
    for sym in ("XAUUSD", "BTCUSD"):
        per_tf = {}; ways = set(); n = 0
        for sc, j, r in rows:
            if j["symbol"] != sym: continue
            tf = j["tf_label"]; way = (tf, r["style_i"], r["direction"])
            if per_tf.get(tf, 0) >= PER_TF or way in ways: continue
            per_tf[tf] = per_tf.get(tf, 0) + 1; ways.add(way); chosen.append((sc, j, r)); n += 1
            if n == PER_SYMBOL: break
    chosen.sort(key=lambda x: -x[0])
    table = []
    for i, (sc, j, r) in enumerate(chosen, 1):
        sym = j["symbol"]; tf = int(j["tf"]); lab = j["tf_label"]; p = r["params"]; spec = R.SYMBOLS[sym]; nb = len(j["blocks"]) - 1
        slug = r["style"].replace("/", "").replace(",", "").replace(" ", "_") + "_" + X2.DIRN[int(p["TradeDir"])].replace(" ", "_")
        name = f"TOP{i:02d}_{sym}_{lab}_{slug}.set"
        fragile = r["all"]["avg"] < 2.0 * X2.COST_RT_USD[sym]
        notes = (["Cost-fragile"] if fragile else []) + ([X2.DIRN[int(p["TradeDir"])]] if int(p["TradeDir"]) != 0 else [])
        live = "live-admitted chart/signal clock" if tf in X2.LIVE else "TESTER-ONLY clock (EA refuses this SigTF on a live chart)"
        header = [
            f"XPW v0.9.2 + FlashGold fenced EA 9.23 - complete 157-input preset. Calibration run 2 top 20, rank {i}, 2026-11-13 (Python replica backtest, NOT MT5 Strategy Tester).",
            f"Required chart: {P.CHART_SYMBOL[sym]}, {lab}; a .set file does not change the chart period. SigTF={tf} selects the signal period ({live}).",
            f"Way of playing: {r['style']}, {X2.DIRN[int(p['TradeDir'])]}. Data: {spec['data']} 1-minute history, {spec['lot_desc']}; profit in USD per 0.01 lot after modeled costs.",
            f"In-sample {d(j['is_window'][0])}..{d(j['is_window'][1])}: {r['is_']['trades']} trades, net {r['is_']['net']:.0f}, PF {r['is_']['pf']:.2f}, maxDD {r['is_']['maxdd']:.0f}.",
            f"Out-of-sample {d(j['oos_window'][0])}..{d(j['oos_window'][1])}: {r['oos']['trades']} trades, net {r['oos']['net']:.0f}, PF {r['oos']['pf']:.2f}, maxDD {r['oos']['maxdd']:.0f}.",
            f"2x-cost stress: net {r['stress_all']['net']:.0f}, PF {r['stress_all']['pf']:.2f}. Profitable calendar blocks: {sum(1 for b in r['blocks'] if b > 0)} of {nb}. Neighbour stability: {r['stability']['stable_share']:.0%} of {r['stability']['neighbours']} variants.",
            f"Unseen days {X2.FWD_FROM}..{X2.FWD_TO} (not used for ranking): {r['fwd']['trades']} trades, net {r['fwd']['net']:.0f}.",
            "Live execution DISABLED (EnableTrading=false, FenceAllowExecution=false). Native MT5 performance NOT verified.",
        ] + (["WARNING: average profit per trade is below 2x the modeled round-trip cost; very sensitive to real spread/commission."] if fragile else []) \
          + (["NOTE: one-direction preset; part of its result is the market's own trend over the test period."] if int(p["TradeDir"]) != 0 else [])
        P.write_set(os.path.join(OUT, "top20", name), p, sym, tf, f"CAL20261113_TOP{i:02d}_{sym}_{lab}", header)
        table.append(dict(rank=i, preset=name, symbol=sym, tf=lab, clock="Live" if tf in X2.LIVE else "Tester only", style=r["style"], direction=X2.DIRN[int(p["TradeDir"])],
                          score=round(sc, 3), is_trades=r["is_"]["trades"], is_net_usd=round(r["is_"]["net"], 2), is_pf=round(r["is_"]["pf"], 3),
                          oos_trades=r["oos"]["trades"], oos_net_usd=round(r["oos"]["net"], 2), oos_pf=round(r["oos"]["pf"], 3), oos_maxdd_usd=round(r["oos"]["maxdd"], 2),
                          all_maxdd_usd=round(r["all"]["maxdd"], 2), stress2x_net_usd=round(r["stress_all"]["net"], 2),
                          profitable_blocks=f"{sum(1 for b in r['blocks'] if b > 0)}/{nb}", neighbour_stability=round(r["stability"]["stable_share"], 2),
                          fwd_trades=r["fwd"]["trades"], fwd_net_usd=round(r["fwd"]["net"], 2), note=", ".join(notes), description=X2.describe(p)))
    if table:
        with open(os.path.join(OUT, "data", "top20.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(table[0].keys())); w.writeheader(); w.writerows(table)
    L = ["# Run 2: top 20 presets\n",
         "Ten gold and ten BTC presets from calibration run 2, at most two per timeframe (so at least five of the six timeframes appear where they have survivors) and with different ways of playing inside a timeframe. "
         "Ranked by a robustness score that ignores the unseen days: the weaker of the in-sample and out-of-sample profit factor (capped at 3), times neighbour stability, times recovery factor (capped). "
         "USD per 0.01 lot after modeled costs. These are replica backtests, not MT5 Strategy Tester results; live gates stay disabled.\n",
         "| # | Preset | TF | Clock | Way of playing | IS net | IS PF | OOS trades | OOS net | OOS PF | Max DD | 2x-cost net | Blocks | Stability | Unseen-days net | Note |",
         "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|"]
    for a in table:
        L.append(f"| {a['rank']} | `{a['preset']}` | {a['tf']} | {a['clock']} | {a['style']}, {a['direction']} | {a['is_net_usd']:.0f} | {a['is_pf']:.2f} | {a['oos_trades']} | {a['oos_net_usd']:.0f} | {a['oos_pf']:.2f} | {a['all_maxdd_usd']:.0f} | {a['stress2x_net_usd']:.0f} | {a['profitable_blocks']} | {a['neighbour_stability']:.0%} | {a['fwd_net_usd']:.0f} ({a['fwd_trades']} trades) | {a['note']} |")
    L += ["", "## What each preset does\n"] + [f"- **{a['preset']}**: {a['description']}" for a in table]
    open(os.path.join(OUT, "TOP20.md"), "w").write("\n".join(L) + "\n")
    print("top20 presets", len(table), {s: sum(1 for a in table if a["symbol"] == s) for s in ("XAUUSD", "BTCUSD")})


if __name__ == "__main__":
    main()
