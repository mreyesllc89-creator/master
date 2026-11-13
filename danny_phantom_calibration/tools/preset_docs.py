"""Regenerate presets/*.set and presets/README.md (one section per timeframe) from the final configs."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pandas as pd
from params import TESTER_SET
from setfile import write_set

ROOT = os.path.join(os.path.dirname(__file__), "..")
PRESETS = os.path.join(ROOT, "presets")
RESULTS = os.path.join(ROOT, "results")

# Human labels from DPFXInputs.mqh comments.
LABELS = {
    "presetMode": "Preset Mode", "tradeOriginalDirection": "Trade Original (Un-Inverted) Signals",
    "atrLenS2": "ATR length", "slAtrMultS2": "Stop loss, ATR mult", "tpRS2": "Take profit, R multiple of SL (0 = off)",
    "useTrailS2": "Trailing stop", "trailActAtr": "Trail activation, ATR mult", "trailDstAtr": "Trail distance, ATR mult",
    "timeStopBars": "Time stop, bars (0 = off)", "useDeadExit": "(2) Scratch trades not in profit after N bars",
    "deadBarsIn": "Dead trade bars", "useBreakeven": "(4) Move stop to breakeven", "beTriggerAtr": "Breakeven trigger (ATR)",
    "useEntryBuffer": "(5) Block entries before blackout window", "entryBufferIn": "Buffer minutes before blackout",
    "useSundayBlock": "(6) Block all Sunday entries (NY)", "useEntryWindow": "(7) Use entry time window",
    "entryWindowIn": "Entry window (NY time)", "useOnePerZone": "(8) One entry per zone",
    "useCooldown": "(9) Re-entry cooldown after dead/time exit", "cooldownIn": "Cooldown bars",
    "manualZoneLength": "Zone lookback length", "manualDeltaThreshold": "Volume delta spike multiplier",
    "manualMinRetestBars": "Minimum bars before retest", "manualMaxZoneAge": "Max zone age in bars",
    "manualInvalidate": "Invalidate broken zones", "manualUseEmaFilter": "Use EMA trend filter",
    "manualEmaLength": "EMA length", "manualZoneTrend": "Only create zones with EMA trend", "manualEntryMode": "Entry mode",
    "useSessionFilter": "Use NY cash session filter", "nySession": "NY session",
    "useRobustHourFilter": "Block robustly losing NY hours", "useDirectionalMicroFilter": "Block directional 15-min windows",
    "useV105DirectionalFilter": "Block V10.5 directional windows", "useV1010PfFilter": "Block V10.10 profit-factor windows",
    "useV1011LossClusterPause": "Pause entries after consecutive loss cluster", "manualLossClusterCount": "Losses before pause",
    "manualLossClusterPauseBars": "Pause bars", "useV1013VolCostFilter": "Block entries when ATR stop is too small vs costs",
    "minStopToCostRatio": "Minimum stop distance / round-trip cost", "useWeekendBlackout": "Weekend close/block",
    "useDailyBlackout": "Daily intraday hold filter (Mon-Thu 16:55-18:00 NY)",
}
GROUPS = [
    ("Preset / direction", ["presetMode", "tradeOriginalDirection"]),
    ("S2. Exits", ["atrLenS2", "slAtrMultS2", "tpRS2", "useTrailS2", "trailActAtr", "trailDstAtr", "timeStopBars"]),
    ("V2 optimisations (Manual mode only)", ["useDeadExit", "deadBarsIn", "useBreakeven", "beTriggerAtr", "useEntryBuffer",
                                            "entryBufferIn", "useSundayBlock", "useEntryWindow", "entryWindowIn",
                                            "useOnePerZone", "useCooldown", "cooldownIn"]),
    ("Supply / demand zones", ["manualZoneLength", "manualDeltaThreshold", "manualMinRetestBars", "manualMaxZoneAge",
                               "manualInvalidate", "manualUseEmaFilter", "manualEmaLength", "manualZoneTrend", "manualEntryMode"]),
    ("Session & quality filters", ["useSessionFilter", "nySession", "useRobustHourFilter", "useDirectionalMicroFilter",
                                   "useV105DirectionalFilter", "useV1010PfFilter", "useV1011LossClusterPause",
                                   "manualLossClusterCount", "manualLossClusterPauseBars", "useV1013VolCostFilter",
                                   "minStopToCostRatio", "useWeekendBlackout", "useDailyBlackout"]),
]
# value inputs that only matter when their toggle is on
DEPENDS = {"trailActAtr": "useTrailS2", "trailDstAtr": "useTrailS2", "deadBarsIn": "useDeadExit",
           "beTriggerAtr": "useBreakeven", "entryBufferIn": "useEntryBuffer", "entryWindowIn": "useEntryWindow",
           "cooldownIn": "useCooldown", "manualEmaLength": "manualUseEmaFilter", "nySession": "useSessionFilter",
           "manualLossClusterCount": "useV1011LossClusterPause", "manualLossClusterPauseBars": "useV1011LossClusterPause",
           "minStopToCostRatio": "useV1013VolCostFilter"}
TF_NAME = {1: "M1", 2: "M2", 3: "M3", 5: "M5", 10: "M10", 15: "M15", 30: "M30", 60: "H1", 240: "H4"}
VERDICT = {
    "XAUUSD_M60": ("RECOMMENDED — rank 1", "Most trades of the robust gold sets, 7 of 8 years profitable, loses only a fifth of its edge under double slippage, flat-positive on the 2026 export."),
    "XAUUSD_M30": ("RECOMMENDED — rank 2", "Profitable in all 8 years and the best out-of-sample t-stat, but the thinnest margin per trade (+0.10 R): keep costs low, do not run it on a wide-spread account."),
    "XAUUSD_M15": ("RECOMMENDED — rank 3", "Best quality per trade on gold (PF 1.54, 61 % wins, 8 % drawdown) at the price of only ~70 trades a year."),
    "BTCUSD_M240": ("RECOMMENDED — rank 4", "The only bitcoin set that survives every test: profitable every year, cost-insensitive, positive on the 2026 export."),
    "XAUUSD_M5": ("USABLE — secondary", "Strong R per trade (+0.42) and 1.55 PF, but ~70 trades a year and an out-of-sample t-stat of only 1.8; no 2026 trades in the 28-day sample."),
    "XAUUSD_M10": ("USABLE — secondary", "Similar profile to M5; 2 losing years out of 8 and OOS t-stat 1.1."),
    "XAUUSD_M240": ("USABLE — secondary", "Highest profit factor on gold (1.76) and 7 % drawdown, but only ~30 trades a year, so the statistics are thin."),
    "BTCUSD_M60": ("PAPER-TRADE FIRST", "Good 2015-2019 history (PF 1.43, every year profitable) but slightly negative on the 37 trades of the 2026 export."),
    "XAUUSD_M1": ("NOT RECOMMENDED", "Edge halves with $0.05 extra slippage per fill; too cost-sensitive for live use."),
    "XAUUSD_M2": ("NOT RECOMMENDED", "Cost-sensitive and flat on the 2026 export (1 045 trades)."),
    "XAUUSD_M3": ("NOT RECOMMENDED", "Weakest gold set (PF 1.09, 37 % drawdown), negative on the 2026 export."),
}
for tf in (1, 2, 3, 5, 10, 15, 30):
    VERDICT[f"BTCUSD_M{tf}"] = ("DO NOT TRADE", "Spread artefact: the five-digit historical return vanishes with 0.5 bp of slippage and the real 2026 feed loses −0.2 to −0.4 R per trade over thousands of trades. Only a zero-spread (TradingView mid-price) backtest shows a profit.")


def describe(cfg, symbol, tf):
    c = dict(TESTER_SET); c.update(cfg)
    manual = c["presetMode"] == "Manual"
    s = []
    s.append(("un-inverted (original) signal direction" if c["tradeOriginalDirection"] else "inverted signals (as shipped)"))
    s.append(f"{'Manual' if manual else 'XAUUSD 5m auto'} profile")
    if manual:
        s.append(f"zones from a {c['manualZoneLength']}-bar volume-delta lookback with a {c['manualDeltaThreshold']}x spike threshold, "
                 f"entry on {'a close beyond the key zone' if c['manualEntryMode'] == 'Close Beyond Key Zone' else 'a retest touch'}")
    ema = c["manualUseEmaFilter"]
    s.append(f"EMA({100 if not manual else c['manualEmaLength']}) trend filter {'on' if ema else 'off'}")
    tp = "no fixed target" if c["tpRS2"] == 0 else f"{c['tpRS2']:g} R target"
    s.append(f"stop {c['slAtrMultS2']:g} x ATR({c['atrLenS2']}), {tp}")
    if c["useTrailS2"]:
        s.append(f"trailing stop armed at {c['trailActAtr']:g} ATR profit, trailing {c['trailDstAtr']:g} ATR behind")
    if c["timeStopBars"]:
        s.append(f"time stop after {c['timeStopBars']} bars")
    if manual and c["useDeadExit"]:
        s.append(f"dead-trade exit after {c['deadBarsIn']} bars without profit")
    if manual and c["useBreakeven"]:
        s.append(f"breakeven at {c['beTriggerAtr']:g} ATR")
    if manual and c["useEntryWindow"]:
        s.append(f"entries only {c['entryWindowIn'][:2]}:{c['entryWindowIn'][2:4]}-{c['entryWindowIn'][5:7]}:{c['entryWindowIn'][7:9]} NY")
    if c["useSessionFilter"]:
        s.append(f"NY session filter {c['nySession']}")
    filt = [n for n, k in (("robust-hour", "useRobustHourFilter"), ("directional", "useDirectionalMicroFilter"),
                            ("V10.5", "useV105DirectionalFilter"), ("V10.10", "useV1010PfFilter")) if c[k]]
    if not manual:
        s.append("gold NY-time window filters: " + (", ".join(filt) if filt else "all off"))
    s.append(f"weekend blackout {'on' if c['useWeekendBlackout'] else 'off'}, daily 16:55-18:00 blackout {'on' if c['useDailyBlackout'] else 'off'}")
    return "; ".join(s) + "."


def main():
    cfgs = json.load(open(os.path.join(RESULTS, "final_configs.json")))
    table = pd.read_csv(os.path.join(RESULTS, "final_table.csv"))
    out = ["# Calibrated presets, one per timeframe", "",
           "Load the `.set` file into MT5 Strategy Tester (Inputs → Load), on the chart timeframe named in the",
           "section, on a USD account, and give each independent run its own `RecoverySession`. The strategy's",
           "sizing (`Risk % = 1.0`, margin cap) and all inputs not listed are the shipped values. Statistics are",
           "from the Python replica described in `../REPORT.md`, with today's spread ($0.12 gold, 2.2 bp bitcoin),",
           "1 % risk per trade and a $10 000 start; 'OOS' = 2016-2018 (gold) / 2018-2019 (bitcoin), '2026' = your",
           "July-August 2026 Octa export. Verdicts: RECOMMENDED > USABLE > PAPER-TRADE > NOT RECOMMENDED > DO NOT TRADE.",
           ""]
    order = sorted(cfgs, key=lambda k: (k.split("_M")[0], int(k.split("_M")[1])))
    out.append("| Preset | Chart | Verdict | Trades/yr | PF | Win % | Return | Max DD | OOS t | 2026 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for key in order:
        symbol, tf = key.split("_M"); tf = int(tf)
        r = table[(table.key == key) & (table.model == "modern")].iloc[0]
        years = 8 if symbol == "XAUUSD" else 5
        x26 = f"{int(r.x26_n)} tr, {r.x26_avg_r:+.2f} R" if r.x26_n else "no trades"
        out.append(f"| `DPFX_{key}_calibrated.set` | {symbol} {TF_NAME[tf]} | {VERDICT[key][0]} | {r.all_n / years:.0f} | "
                   f"{r.all_pf:.2f} | {r.all_win:.0f} | {r.all_ret:,.0f} % | {r.all_dd:.1f} % | {r.oos_tstat:.1f} | {x26} |")
    out.append("")
    for key in order:
        symbol, tf = key.split("_M"); tf = int(tf)
        cfg = cfgs[key]
        write_set(os.path.join(PRESETS, f"DPFX_{key}_calibrated.set"), cfg, symbol)
        r = table[(table.key == key) & (table.model == "modern")].iloc[0]
        rec = table[(table.key == key) & (table.model == "recorded")].iloc[0]
        mid = table[(table.key == key) & (table.model == "mid")].iloc[0]
        years = 8 if symbol == "XAUUSD" else 5
        verdict, why = VERDICT[key]
        out += [f"## {symbol} {TF_NAME[tf]} — `DPFX_{key}_calibrated.set`", "",
                f"**Chart:** {symbol}, {TF_NAME[tf]} ({tf}-minute bars). **Verdict: {verdict}.** {why}", "",
                f"**Character:** {describe(cfg, symbol, tf)}", "",
                f"**History ({'2011-2018' if symbol == 'XAUUSD' else '2015-2019'}):** {int(r.all_n)} trades "
                f"({r.all_n / years:.0f}/yr), PF {r.all_pf:.2f}, {r.all_win:.0f} % wins, avg {r.all_avg_r:+.2f} R, "
                f"return {r.all_ret:,.0f} % with {r.all_dd:.1f} % max drawdown; in-sample t {r.is_tstat:.1f}, "
                f"out-of-sample t {r.oos_tstat:.1f} ({int(r.oos_n)} trades, {r.oos_avg_r:+.2f} R). "
                f"With the broker spread recorded at the time: {rec.all_ret:,.0f} %; with no spread (TradingView default): {mid.all_ret:,.0f} %. "
                f"2026 export: {int(r.x26_n)} trades, {r.x26_avg_r:+.2f} R." if r.x26_n else
                f"**History ({'2011-2018' if symbol == 'XAUUSD' else '2015-2019'}):** {int(r.all_n)} trades "
                f"({r.all_n / years:.0f}/yr), PF {r.all_pf:.2f}, {r.all_win:.0f} % wins, avg {r.all_avg_r:+.2f} R, "
                f"return {r.all_ret:,.0f} % with {r.all_dd:.1f} % max drawdown; in-sample t {r.is_tstat:.1f}, "
                f"out-of-sample t {r.oos_tstat:.1f} ({int(r.oos_n)} trades, {r.oos_avg_r:+.2f} R). "
                f"With the broker spread recorded at the time: {rec.all_ret:,.0f} %; with no spread (TradingView default): {mid.all_ret:,.0f} %. "
                f"2026 export: no trades in the short sample.",
                "", f"Exits: {r.exit_mix}.", "",
                "**Inputs that differ from the shipped Tester preset** (TradingView uses the same names):", ""]
        c = dict(TESTER_SET); c.update(cfg)
        manual = c["presetMode"] == "Manual"
        out.append("| Group | Input | Value | Shipped |")
        out.append("|---|---|---|---|")
        for group, keys in GROUPS:
            if not manual and group.startswith("V2") or not manual and group.startswith("Supply") and False:
                continue
            for k in keys:
                if k in cfg and cfg[k] != TESTER_SET.get(k) and (k not in DEPENDS or c.get(DEPENDS[k])):
                    if not manual and k in ("manualZoneLength", "manualDeltaThreshold", "manualEmaLength", "manualZoneTrend",
                                            "manualEntryMode", "manualLossClusterCount", "manualLossClusterPauseBars"):
                        continue  # ignored by the XAUUSD 5m profile
                    out.append(f"| {group} | `{k}` — {LABELS.get(k, k)} | **{cfg[k]}** | {TESTER_SET.get(k)} |")
        out.append("")
    out += ["## Mirroring a preset on TradingView", "",
            "The Pine strategy exposes the same inputs under the same names; `Preset Mode` is the dropdown at the top.",
            "Set `Trade Original (Un-Inverted) Signals` first (it changes the whole signal set), then the S2 exit group,",
            "then the filters. TradingView charges no spread by default: set *Properties → Commission* to about",
            "0.003 % per order on gold (≈ $0.06 each side at $4 300) or 0.11 % on bitcoin, or *Slippage* to 60 ticks on",
            "gold, or every result will be overstated — the M1-M30 bitcoin sets will look spectacular there and lose live.",
            ""]
    with open(os.path.join(PRESETS, "README.md"), "w") as fh:
        fh.write("\n".join(out))
    print(f"wrote {len(order)} presets and README.md")


if __name__ == "__main__":
    main()
