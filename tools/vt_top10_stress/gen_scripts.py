"""Assemble the three Pine strategies from the verbatim parts and emit one script per top-10 config
with the config hard-coded as input defaults and VT cent-lot costs in strategy()."""
import re, json, csv, os, sys, difflib
P = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(P, "parts"); OUT = os.path.join(P, "out")
TOP = os.path.join(P, "..", "deliver", "top10_per_strategy.csv")

def rd(n): return open(os.path.join(PARTS, n), encoding="utf-8").read()
FGF = rd("fgf_block.pine")
BASE = {
    "FlashGold v5":      rd("fg5_A.pine") + FGF.replace("__FGF_OVERLAY__", "false") + rd("fg5_B.pine"),
    "ShapeMap v0.9.2":   rd("v92_A.pine") + FGF.replace("__FGF_OVERLAY__", "true")  + rd("v92_B.pine"),
    "Orientation v2.8 (partial ladder)": rd("v28_A.pine") + FGF.replace("__FGF_OVERLAY__", "true") + rd("v28_B.pine"),
}
SHORT = {"FlashGold v5": "FG5", "ShapeMap v0.9.2": "SM92", "Orientation v2.8 (partial ladder)": "OTDI28"}
DIR = {"FlashGold v5": "FlashGold_v5", "ShapeMap v0.9.2": "ShapeMap_v0.9.2", "Orientation v2.8 (partial ladder)": "Orientation_TDI_v2.8"}

SLIP_TICKS = 10      # per side on TV: ~half of the 13-tick VT gold spread + ~3 ticks execution
COMM = 0.30          # USD per contract (= per oz = per VT cent lot) per side -> 0.60 round trip
QTY = 0.1            # 0.10 cent lot = 0.1 oz = 0.1 TV contract
SPREAD_PTS = 13.0    # median VT XAUUSD-ECNc spread, July 2026

def fmt(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, str): return '"' + v + '"'
    if isinstance(v, float): return repr(v)
    return str(v)

def set_input(src, name, value):
    pat = re.compile(r'^(' + re.escape(name) + r'\s*=\s*input\.(float|int|bool|string|timeframe)\()("[^"]*"|[^,]+)(,)', re.M)
    ms = list(pat.finditer(src)); assert len(ms) == 1, (name, len(ms))
    m = ms[0]; kind = m.group(2); val = value
    if kind == "bool": assert isinstance(value, bool), name
    if kind == "string": assert isinstance(value, str), name
    if kind == "float" and isinstance(value, int) and not isinstance(value, bool): val = float(value)
    if kind == "int": assert isinstance(value, int) and not isinstance(value, bool), name
    return src[:m.start(3)] + fmt(val) + src[m.end(3):]

def replace_once(src, old, new):
    assert src.count(old) == 1, (old[:60], src.count(old)); return src.replace(old, new)

# ---------------- label parsers -> input maps ----------------
def fg5_inputs(label):
    m = re.fullmatch(r"ATR SL ([\d.]+) TP ([\d.]+)R (Fixed\+trail|Fixed|Partial), burst ([\d.]+), filter (off|on)", label); assert m, label
    sl, tp, style, bm, f = m.groups()
    d = {"ExitMode": "ATR", "slAtrMult": float(sl), "tpR": float(tp), "TpStyle": "Fixed" if style.startswith("Fixed") else "Partial + runner",
         "useTrail": style == "Fixed+trail", "trailActAtr": 1.0, "trailDstAtr": 0.25, "DistUnit": "ATR", "burstAtrMult": float(bm),
         "spreadPoints": SPREAD_PTS, "QtyMode": "Fixed", "fixedQty": QTY, "qtyStep": 0.01, "fgfOn": f == "on", "fgfSpreadPts": SPREAD_PTS}
    return d

def v92_inputs(label):
    m = re.fullmatch(r"(Turn_AfterHold|Turn_AtCross|Turn_Predict_Squares|Square|Tick|CONT_Stop|CONT_Close), (Points_default|ATR_[\w.]+), lossrev (any\+tiny|any_notiny|SLtrail\+tiny|off), filter (off|on)", label); assert m, label
    sig, ex, rev, f = m.groups(); d = {}
    d["sigMode"] = {"Square": "BOT/TOP square", "Tick": "BOT/TOP tick"}.get(sig, "CONT ▲/▼" if sig.startswith("CONT") else "Turn ▲/▼")
    if sig.startswith("Turn"): d["turnEntry"] = {"Turn_AfterHold": "After hold (when ▲/▼ confirms)", "Turn_AtCross": "At the cross", "Turn_Predict_Squares": "Predict (stop at cross price)"}[sig]
    if sig.startswith("CONT"): d["contEntry"] = "Stop past signal candle" if sig == "CONT_Stop" else "At signal close"
    if ex == "Points_default":
        d.update(exitUnit="Points", slPts=7000.0, tpPts=50000.0, trailOn=True, trActPts=1000.0, trDisPts=100.0)
    else:
        if ex == "ATR_default_2.0_2R_4.0_0.2": d.update(exitUnit="ATR", slAtrM=2.0, tpR=2.0, trailOn=True, trActAtr=4.0, trDisAtr=0.2)
        elif ex == "ATR_1.5_2R_1.0_0.5": d.update(exitUnit="ATR", slAtrM=1.5, tpR=2.0, trailOn=True, trActAtr=1.0, trDisAtr=0.5)
        elif ex == "ATR_2.5_2R_1.0_0.5": d.update(exitUnit="ATR", slAtrM=2.5, tpR=2.0, trailOn=True, trActAtr=1.0, trDisAtr=0.5)
        elif ex == "ATR_1.0_3R_notrail": d.update(exitUnit="ATR", slAtrM=1.0, tpR=3.0, trailOn=False)
        else: raise ValueError(ex)
    if rev == "off": d.update(lossRevOn=False)
    else:
        d.update(lossRevOn=True, lossRevWhat="Stop loss / trail only" if rev.startswith("SL") else "Any losing exit", lossRevTiny=rev.endswith("+tiny"), lossRevMax=1, lossRevTinyPts=1500.0)
    d.update(enterTick=False, qtyMode="Fixed", qtyFixed=QTY, fgfOn=f == "on", fgfSpreadPts=SPREAD_PTS)
    return d

def v28_inputs(label):
    m = re.fullmatch(r"(chart\+READ|chart only|every rung), info (enter|off), reverse (off|on), (Points_default|ATR_[\w.]+), maxOpen (\d+), filter (off|on)", label); assert m, label
    rung, inf, rev, ex, mo, f = m.groups(); d = {}
    d["sigRung"] = "every rung (1 Sec to 1 Month)" if rung == "every rung" else "chart rung (*)"
    d["lblRead"] = rung == "chart+READ"
    d["actInf"] = inf; d["reverseAll"] = rev == "on"
    if ex == "Points_default": d.update(exitUnit="Points", slPtsIn=10000.0, tpPtsIn=30000.0, trailOn=True, trActPts=15000.0, trDistPts=10000.0)
    elif ex == "ATR_2.0_2R_notrail": d.update(exitUnit="ATR", slAtrMult=2.0, tpRMult=2.0, trailOn=False)
    elif ex == "ATR_1.0_3R_notrail": d.update(exitUnit="ATR", slAtrMult=1.0, tpRMult=3.0, trailOn=False)
    elif ex == "ATR_1.5_2R_trail1.0_0.5": d.update(exitUnit="ATR", slAtrMult=1.5, tpRMult=2.0, trailOn=True, trActAtr=1.0, trDistAtr=0.5)
    elif ex == "ATR_default_3.0_1R_trail1.0_0.75": d.update(exitUnit="ATR", slAtrMult=3.0, tpRMult=1.0, trailOn=True, trActAtr=1.0, trDistAtr=0.75)
    else: raise ValueError(ex)
    d.update(maxOpen=int(mo), qtyMode="Fixed", qtyFixed=QTY, qtyStep=0.01, fgfOn=f == "on", fgfSpreadPts=SPREAD_PTS)
    return d

PARSE = {"FlashGold v5": fg5_inputs, "ShapeMap v0.9.2": v92_inputs, "Orientation v2.8 (partial ladder)": v28_inputs}

# ---------------- strategy() header edits ----------------
def patch_header(strat, src, title, short):
    if strat == "FlashGold v5":
        src = replace_once(src, 'strategy("FlashGold v5 Strategy (BTCUSD)", "FlashGold v5 S (BTCUSD)",', f'strategy("{title}", "{short}",')
        src = replace_once(src, "default_qty_type = strategy.fixed, default_qty_value = 10,", f"default_qty_type = strategy.fixed, default_qty_value = {QTY},")
        src = replace_once(src, "commission_type = strategy.commission.percent, commission_value = 0.02,  // % of notional per side (typical crypto futures taker fee)",
                           f"commission_type = strategy.commission.cash_per_contract, commission_value = {COMM:.2f},  // USD per contract (oz) per side = VT Markets 0.60 round trip per cent lot")
        src = replace_once(src, "slippage = 5,                                                            // ticks per side. mintick 0.01 -> $0.05/BTC",
                           f"slippage = {SLIP_TICKS},                                                           // ticks per side: ~half of the 13-tick VT spread + 3 ticks execution")
    elif strat == "ShapeMap v0.9.2":
        src = replace_once(src, 'strategy("XPW Shape Map v0.9.2 Strategy", shorttitle = "XPW-SM9.2 S",', f'strategy("{title}", shorttitle = "{short}",')
        src = replace_once(src, "default_qty_type = strategy.fixed, default_qty_value = 10,", f"default_qty_type = strategy.fixed, default_qty_value = {QTY},")
        src = replace_once(src, "commission_type = strategy.commission.percent, commission_value = 0.05)",
                           f"commission_type = strategy.commission.cash_per_contract, commission_value = {COMM:.2f}, slippage = {SLIP_TICKS})")
    else:
        src = replace_once(src, 'strategy("XPW Orientation TDI v2.8 Strategy", shorttitle="XPW-OTDI8 S",', f'strategy("{title}", shorttitle="{short}",')
        src = replace_once(src, "default_qty_type=strategy.fixed, default_qty_value=0.1, process_orders_on_close=true,",
                           f"default_qty_type=strategy.fixed, default_qty_value={QTY}, commission_type=strategy.commission.cash_per_contract, commission_value={COMM:.2f}, slippage={SLIP_TICKS}, margin_long=1, margin_short=1, process_orders_on_close=true,")
    return src

NOTES = {
    "FlashGold v5": "FlashGold v5 strategy source as supplied (BTCUSD build), unchanged except the input defaults and strategy() costs listed above.",
    "ShapeMap v0.9.2": "XPW Shape Map v0.9.2 strategy source as supplied, unchanged except the input defaults and strategy() costs listed above.\n"
        "// enterTick is set to false: the replay decided every signal on the CLOSED candle (ticks were used only for fills and stops), so live entries wait for the close too. The historical tester is unaffected.",
    "Orientation v2.8 (partial ladder)": "XPW Orientation TDI v2.8 strategy source as supplied, unchanged except the input defaults and strategy() costs listed above.\n"
        "// CAUTION: the VT replay had NO 1 Day / 1 Week / 1 Month bars (July 2026 ticks only), the seconds rungs were off, and every rung started cold on 1 July.\n"
        "// On TradingView all 13 rungs are live and the 1 Month rung orients the ladder, so the screened result is NOT reproducible here: treat the numbers above as the VT partial-ladder result only.\n"
        "// margin_long = margin_short = 1 was added so TradingView's default 100% margin never silently caps the 20-entry stack (the replay had no equity cap).",
}

STRESS = {(w["strategy"], int(w["rank"])): w for w in csv.DictReader(open(os.path.join(P, "..", "deliver", "top30_stress_results_wide.csv"), encoding="utf-8"))}

def header_comment(strat, r, rank, inputs):
    w = STRESS[(strat, rank)]
    lines = ["// ============================================================================",
             f"// {strat.replace(' (partial ladder)', '')}  |  TOP-{rank:02d} of the VT Markets screen  |  {r['symbol']} {r['tf']}",
             f"// Settings: {r['settings']}",
             f"// Screen (VT XAUUSD-ECNc real bid/ask ticks, July 2026, 0.10 cent lot, 0.60 USD round trip per lot):",
             f"//   trades {r['trades']}  net {float(r['net']):.2f} USD  PF {float(r['pf']):.2f}  win {float(r['win'])*100:.0f}%  maxDD {float(r['maxdd']):.2f} USD  positive weeks {float(r['pos_weeks'])*100:.0f}%  halves {r['halves']}",
             "// Costs in strategy(): commission 0.30 USD per contract per side (= VT 0.60 round trip per cent lot of 1 oz),",
             "//   slippage 10 ticks per side (~half of the 13-tick VT spread + ~3 ticks execution), quantity 0.1 contracts = 0.10 cent lot.",
             "// Chart: XAUUSD, timeframe " + r['tf'] + ". TradingView's feed is not VT's tick feed and its tester fills on bar OHLC, not ticks: expect different signals and fills.",
             "// This is a 4-week screen, not a calibration: 15-275 trades, one month, no out-of-sample test. Treat as a candidate only.",
             f"// Stress re-run on the same VT ticks (stress/ folder): +10 ticks/side net {float(w['net@c0.30_s10']):.2f} PF {float(w['pf@c0.30_s10']):.2f}; 2x commission + 10 ticks/side net {float(w['net@c0.60_s10']):.2f} PF {float(w['pf@c0.60_s10']):.2f}" + (" (trade count changed across levels: tick-timing sensitive)" if w['trade_count_changed'] == 'True' else ""),
             "// TICK SIZE: every point input (spread 13 pts, slippage 10 ticks, Points-mode SL/TP/trail) assumes mintick 0.01 as on VT. On a 3-decimal gold symbol (mintick 0.001)",
             "//   multiply them by 10, or the exits are 10x too tight. Confirm 1 contract = 1 oz and that the List of Trades shows qty 0.1 on the first fill.",
             "// Hard-coded input defaults (everything else is the author's default):"]
    for k, v in inputs.items(): lines.append(f"//   {k} = {fmt(v)}")
    if inputs.get("exitUnit") == "Points": lines.append("// THIS SCRIPT USES POINTS-MODE EXITS (SL / TP / trail in ticks): check the tick size note above before running it.")
    lines.append("// " + NOTES[strat].replace("\n", "\n// ") if False else "// " + NOTES[strat])
    lines.append("// ============================================================================")
    return "\n".join(lines) + "\n"

def main():
    rows = list(csv.DictReader(open(TOP, encoding="utf-8")))
    manifest = []; counters = {}
    for r in rows:
        strat = r["strategy"]; counters[strat] = counters.get(strat, 0) + 1; rank = counters[strat]
        inputs = PARSE[strat](r["settings"])
        base = BASE[strat]
        src = base
        for k, v in inputs.items(): src = set_input(src, k, v)
        title = f"{strat.replace(' (partial ladder)', '')} S | VT XAUUSD {r['tf']} #{rank:02d}"
        short = f"{SHORT[strat]} {rank:02d} {r['tf']}"
        src = patch_header(strat, src, title, short)
        mv = re.search(r"^//@version=\d+\n", src, re.M); assert mv, strat
        hdr = header_comment(strat, r, rank, inputs)
        src = src[:mv.end()] + hdr + src[mv.end():]
        assert "__FGF_OVERLAY__" not in src
        slug = re.sub(r"[^A-Za-z0-9.+]+", "_", r["settings"]).strip("_")[:110]
        fn = f"{SHORT[strat]}_{rank:02d}_{r['tf']}_{slug}.pine"
        d = os.path.join(OUT, DIR[strat]); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, fn), "w", encoding="utf-8").write(src)
        diff = "".join(difflib.unified_diff(base.splitlines(True), src.splitlines(True), "base_assembled.pine", fn, n=0))
        os.makedirs(os.path.join(OUT, "_diffs"), exist_ok=True)
        open(os.path.join(OUT, "_diffs", fn + ".diff"), "w", encoding="utf-8").write(diff)
        manifest.append(dict(strategy=strat, rank=rank, file=os.path.join(DIR[strat], fn), symbol=r["symbol"], tf=r["tf"], settings=r["settings"],
                             inputs=inputs, title=title, shorttitle=short, screen=dict(trades=int(r["trades"]), net=float(r["net"]), pf=float(r["pf"]), win=float(r["win"]), maxdd=float(r["maxdd"]), pos_weeks=float(r["pos_weeks"]), halves=r["halves"])))
    for strat, base in BASE.items():
        open(os.path.join(OUT, "_diffs", f"base_{SHORT[strat]}.pine"), "w", encoding="utf-8").write(base)
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(len(manifest), "scripts written")

if __name__ == "__main__": main()
