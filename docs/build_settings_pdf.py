from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "XPW_Settings_by_Timeframe.pdf")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=16, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=8, spaceAfter=3)
B  = ParagraphStyle("b", parent=ss["Normal"], fontSize=8.6, leading=11)
S  = ParagraphStyle("s", parent=ss["Normal"], fontSize=7.4, leading=9)
SB = ParagraphStyle("sb", parent=S, fontName="Helvetica-Bold")
NOTE = ParagraphStyle("n", parent=B, textColor=colors.HexColor("#444444"), fontSize=8.2, leading=10.5)

# ---------------------------------------------------------------- inputs, in script order, with the defaults of each build
GROUPS = [
 ("1. Execution", [
  ("Execution", "Tick", "Tick", "BarClose = v2.01 bar-close behaviour. Historical bars are identical either way."),
  ("Trading System (1 = enabled)", "1", "1", "0 disables new entries."),
  ("Direction", "Both", "Both", ""),
  ("Arm latch (buffer arms only, stop then rests)", "on", "on", "Keep on. Off = v2.01 arming, which cancels the stop on every tick inside the buffer."),
  ("Latched stop when the level moves", "Follow", "Follow", "Follow = the resting stop is re-priced to a new level at once (calibrated policy). Recheck = new level must pass the buffer again."),
  ("Max level distance, ATR mult (0 = off)", "0", "0", "Must be larger than the buffer if used."),
 ]),
 ("2. Costs (model, mirrors the header)", [
  ("Commission % per side", "0", "0", "Exchange feeds: 0.05. Then set the header commission type to percent."),
  ("Commission USD per contract per side", "10.5", "0.13", "VT Markets: BTC half of the $21 spread; gold half of the $0.25 spread + $0.006/oz commission."),
  ("Slippage USD per side", "5.0", "0.05", "Header slippage (ticks) must equal this / mintick: 500 for BTC, 5 for gold. The table prints it."),
  ("Cost gate (skip when RT cost > x% of net TP)", "on", "on", ""),
  ("   max round-trip cost, % of net TP", "20", "20", ""),
  ("Widen TP by both commissions (net target = input)", "on", "on", ""),
  ("Reserve round-trip cost in risk sizing", "on", "on", ""),
 ]),
 ("3. Sizing", [
  ("Risk percent of equity per trade", "1.0", "1.0", "Risk sizing was spot-checked, not swept; the sweep used 1 BTC / 1 oz fixed."),
  ("Risk-based sizing (off = FixedQty)", "on", "on", ""),
  ("FixedQty fallback", "0.1 BTC", "10 oz", "Gold: 100 oz = 1 MT5 lot."),
  ("HARD qty cap", "2.0 BTC", "50 oz", "The cap binding means the risk inputs are wrong for the account, not a feature."),
  ("Qty step (rounds down)", "0.01", "1", ""),
 ]),
 ("4. Geometry", [
  ("Geometry", "ATR", "ATR", "Pct = percent-of-entry SL and TP (v2.01 style)."),
  ("SL, ATR mult (ATR mode)", "3.0", "1.5", ""),
  ("TP, R multiple of SL (ATR mode)", "3.0", "2.5", ""),
  ("TP as percent of entry (Pct mode)", "0.25", "0.25", "Only read in Pct mode."),
  ("SL as percent of entry (Pct mode)", "0.1", "0.1", "Only read in Pct mode. 0.1% on BTC sits inside one bar: do not use it there."),
  ("ATR length", "14", "14", ""),
 ]),
 ("5. Levels", [
  ("Pivot levels (v2.01)", "on", "on", ""),
  ("   pivot bars each side", "3", "3", "BarsN."),
  ("Donchian levels (prior N bars)", "off", "off", "A rolling level that moves every bar."),
  ("   Donchian length", "20", "20", "Only read when Donchian is on."),
  ("Previous-day high/low", "off", "off", ""),
  ("Entry buffer anchor", "ATR", "ATR", ""),
  ("Buffer, ATR mult", "0.5", "1.0", "Price must be this far from the level to ARM the stop."),
  ("Buffer, percent of the Pct-mode TP (parity mode)", "50", "50", "Only for the v2.01 acceptance test."),
 ]),
 ("6. Entry trigger", [
  ("Trigger", "Stop", "Stop", "Stop = pending stop straddle (the calibrated one). CloseConfirm / Retest were not swept."),
  ("CloseConfirm: max close beyond level, ATR mult", "0.5", "0.5", ""),
  ("Retest: bars the limit stays valid", "5", "5", ""),
  ("Retest: limit offset inside the level, ATR mult", "0", "0", ""),
 ]),
 ("7. Filters", [
  ("Chart EMA trend filter, length (0 = off)", "0", "0", "Not swept; the calibration ran without filters."),
  ("Cooldown bars after an exit (0 = off)", "0", "0", ""),
  ("Max trades per day (0 = off)", "0", "0", ""),
  ("Max consecutive losses per level (0 = off)", "0", "0", ""),
  ("   same-level tolerance, ATR mult", "0.25", "0.25", ""),
  ("Compression gate (arm only when coiled)", "off", "off", ""),
  ("   compression lookback", "200", "200", ""),
  ("   arm below width percentile", "30", "30", ""),
 ]),
 ("8. Time", [
  ("Start hour (0 = off)", "0", "0", "Chart / broker server time."),
  ("End hour (0 = off)", "0", "0", ""),
  ("Trade days (1=Sun .. 7=Sat)", "1234567", "1234567", "Gold: the daily maintenance break and weekend gap are not modelled."),
 ]),
 ("9. Exits", [
  ("Ratchet trail", "on", "on", ""),
  ("Trail execution", "Emulator", "Emulator", "Emulator = broker-emulator trail (intrabar on history, per tick live) = engine 'tick'. Script = v2.01 close-anchored ratchet = engine 'bar'."),
  ("Trail anchor", "ATR", "ATR", ""),
  ("Trail trigger, ATR mult", "1.0", "1.0", ""),
  ("Trail distance, ATR mult", "1.5", "1.5", ""),
  ("Trail trigger, percent of TP (parity mode)", "7", "7", "v2.01 parity only."),
  ("Trail distance, percent of TP (parity mode)", "5", "5", "v2.01 parity only."),
  ("Breakeven step (stop to fill +/- costs)", "off", "off", "Not swept."),
  ("   BE trigger, R multiple of SL", "1.0", "1.0", ""),
  ("Time stop, bars (0 = off)", "0", "0", "Not swept."),
 ]),
 ("10. Display", [
  ("Cost / state table", "on", "on", "Check the 'Header slippage should be' row after any cost change."),
  ("Plot levels, TP and trail", "on", "on", ""),
  ("Plot trend EMA", "off", "off", ""),
  ("Mark realtime bars (Tick mode)", "on", "on", ""),
 ]),
]
SPX_DEFAULTS = {
 "Commission USD per contract per side": "0.25 pt", "Slippage USD per side": "0.1 pt",
 "FixedQty fallback": "1 contract", "HARD qty cap": "10 contracts", "Qty step (rounds down)": "1",
 "Geometry": "Pct", "TP as percent of entry (Pct mode)": "1.0", "SL as percent of entry (Pct mode)": "0.5",
 "Buffer, ATR mult": "2.0",
}
HEADER = {
 "BTC": [("Properties > Commission", "cash per contract, 10.5 USD", "Header default. Properties > Defaults > Reset settings restores it."),
         ("Properties > Slippage", "500 ticks", "= 5 USD at mintick 0.01.")],
 "XAU": [("Properties > Commission", "cash per contract, 0.13 USD", "Header default. Properties > Defaults > Reset settings restores it."),
         ("Properties > Slippage", "5 ticks", "= 0.05 USD/oz at mintick 0.01.")],
 "SPX": [("Properties > Commission", "cash per contract, 0.25 (index points)", "Half of a 0.5 point spread; placeholder until the VT Markets SPX500 spec is confirmed."),
         ("Properties > Slippage", "10 ticks", "= 0.10 index points at mintick 0.01.")],
}

# ---------------------------------------------------------------- per-timeframe sheets
# overrides: {input label: value}; stats: text; notes: list of paragraphs
SHEETS = {
 "BTC": dict(
  symbol="BTCUSD", script="pine/XPW_Breakout_v2.10_BTCUSD.pine", unit="per 1 BTC, VT Markets costs ($31 round trip)",
  tfs=[
   dict(tf="5m and below", verdict="DO NOT TRADE", overrides={}, stats="Defaults on the MEXC 5m export: 109 trades, -6,519, PF 0.49, in a week where 15m/30m/60m were positive.",
        notes=["No settings sheet. If a 5m chart must be used, the only band with evidence (one week) is Geometry Pct, SL 1.0%, TP 1.0% to 3.0%, pivot bars 8. Treat it as untested."]),
   dict(tf="15m", verdict="Trade with the 15m block", overrides={"Geometry": "Pct", "SL as percent of entry (Pct mode)": "1.0", "TP as percent of entry (Pct mode)": "2.5", "Trail execution": "Script"},
        stats="29 trades, +5,957, PF 2.30, max DD 2,387 (sweep, CFD costs within $4 of VT). Every grid neighbour positive.",
        notes=["Percent geometry wins on 15m: SL 1.0% is about 4 ATR there; the ATR 3.0 band is positive but thinner (36 trades, +4,509).",
               "Alternative, same script defaults with a rolling level: Pivot levels OFF, Donchian ON, length 20, Geometry ATR 3.0 / 3R, buffer 0.5, Emulator trail, Follow: 37 trades, +5,877, PF 2.56, max DD 1,141; first half +1,801 / second half +3,661. The pivot at the ATR defaults loses the first half (-594 / +4,908)."]),
   dict(tf="30m", verdict="Trade, prefer the Donchian 50 variant", overrides={"Trail execution": "Script"},
        stats="Pivot, ATR 3.0 / 3R, BarsN 3, buffer 0.5, Script trail: 24 trades, +5,660, PF 1.91, max DD 4,625.",
        notes=["Do not use pivot bars 5 on 30m (30 trades, +1,411 CFD / -486 exchange). 3 or 8 only.",
               "Better variant: Pivot levels OFF, Donchian ON, length 50, Geometry ATR 3.0 / 3R, buffer 0.5, Emulator trail: 24 trades, +7,585, PF 3.90, max DD 1,277; first half +651 / second half +3,979, but only 11 trades per half. Follow and Recheck give the same result here."]),
   dict(tf="60m", verdict="SHIPPED DEFAULTS - change nothing", overrides={},
        stats="30 trades, +10,004, PF 2.35, max DD 2,956; first half +397 / second half +8,883. Recheck: 31 trades, +9,937, PF 2.29.",
        notes=["Sensitive to pivot bars: 5 and 8 drop to about +2,400. Keep 3.",
               "Donchian does not help here at the defaults (Donchian 10: +7,387 with a negative first half; Donchian 20: +4,023). The pivot is the only level source positive in both halves on 60m."]),
   dict(tf="240m", verdict="Low confidence - context timeframe", overrides={"Pivot levels (v2.01)": "off", "Donchian levels (prior N bars)": "on", "   Donchian length": "20"},
        stats="Donchian 20, ATR 3.0 / 3R, buffer 0.5, Emulator trail, Follow: 27 trades, +5,850, PF 1.50, max DD 5,683; first half +885 / second half +5,591.",
        notes=["99 days of 240m bars give 20 to 46 trades per cell and the sign flips between neighbours; the pivot defaults are +1,528 (Recheck) or -2,708 (Follow). Donchian 20 is the only level source positive in both halves. Every other Donchian length loses on 240m (length 5: -13,624).",
               "Use this sheet only with a larger position cap than you would regret; more history is needed before 240m counts as calibrated."]),
  ]),
 "SPX": dict(
  symbol="SPX500 (SPCFD:SPX)", script="pine/XPW_Breakout_v2.10_SPX500.pine", unit="per 1 contract at $1 per index point, cash session, placeholder costs (0.5 pt spread, 0.1 pt slip)",
  tfs=[
   dict(tf="5m and below", verdict="NOT TESTED - do not trade", overrides={}, stats="The 1m export covers 2.5 months and the 15s / 1s exports one day: not enough to calibrate, and every lower timeframe tested on BTC and gold lost.",
        notes=["No settings sheet."]),
   dict(tf="15m", verdict="Borderline - verify with Bar Magnifier first", overrides={"SL as percent of entry (Pct mode)": "0.1", "TP as percent of entry (Pct mode)": "0.25", "   pivot bars each side": "5", "Buffer, ATR mult": "0.5"},
        stats="Pct SL 0.1% / TP 0.25%, pivot bars 5, buffer 0.5, Emulator trail, Follow: 173 trades, +400, PF 1.49, max DD 102; first half +282 / second half +118. Donchian 10 instead of pivots: 272 trades, +717, PF 1.55 (+239 / +476).",
        notes=["One trade in four resolves inside the fill bar (the stop is 0.8 ATR on 15m), so part of this result is the emulator's path assumption. Run it in the Strategy Tester with Bar Magnifier ON before trusting it; if the PF holds there, it is real.",
               "Every wider geometry was negative in the second half of the 15m export (5 months). 15m SPX is the weakest timeframe here."]),
   dict(tf="30m", verdict="Trade with the ATR block", overrides={"Geometry": "ATR", "   pivot bars each side": "8", "Trail execution": "Emulator"},
        stats="ATR 3.0 / 3R, pivot bars 8, buffer 2.0, Emulator trail, Follow: 78 trades, +764, PF 1.67, max DD 296; first half +573 / second half +171; 1% fill-bar exits. 9 months of data.",
        notes=["The SL/TP ATR inputs stay at their defaults (3.0 / 3R); only Geometry switches to ATR and pivot bars to 8.",
               "Alternative with more trades: Pct SL 0.25% / TP 0.5%, Donchian 10 instead of pivots, buffer 0.5, Recheck: 237 trades, +809, PF 1.34, max DD 385 (+563 / +227), 15% fill-bar exits."]),
   dict(tf="60m", verdict="SHIPPED DEFAULTS - change nothing", overrides={},
        stats="143 trades, +1,320, PF 1.59, max DD 333; first half +917 / second half +437; 10% fill-bar exits. 18 months of data.",
        notes=["Recheck instead of Follow halves the trade count (80 trades, +750, PF 1.55) and loses the second half (+10): keep Follow on SPX.",
               "Alternative: Pct SL 0.25% / TP 0.5%, pivot bars 5, buffer 0.5, Recheck: 194 trades, +1,065, PF 1.54, max DD 179 (+733 / +298), but 26% of exits are inside the fill bar."]),
   dict(tf="120m", verdict="SHIPPED DEFAULTS - change nothing", overrides={},
        stats="151 trades, +1,329, PF 1.57, max DD 225; first half +594 / second half +676; 15% fill-bar exits. 2.7 years of data.",
        notes=["Alternative: Geometry ATR, SL 1.5 ATR, TP 3R, pivot bars 3, buffer 1.0, Emulator trail: 183 trades, +1,696, PF 1.48, max DD 455 (+1,218 / +460), 6% fill-bar exits."]),
   dict(tf="180m", verdict="Trade with the ATR block", overrides={"Geometry": "ATR", "   pivot bars each side": "8"},
        stats="ATR 3.0 / 3R, pivot bars 8, buffer 2.0, Emulator trail, Follow: 82 trades, +1,838, PF 2.03, max DD 416; first half +1,239 / second half +577; no fill-bar exits. 3.6 years of data.",
        notes=["Recheck: 70 trades, +1,898, PF 2.22, max DD 457 (+1,294 / +581). Either policy.",
               "The shipped percent block fails here (-30 over the file); use the ATR block."]),
   dict(tf="240m", verdict="Trade with the ATR block, few trades", overrides={"Geometry": "ATR", "   pivot bars each side": "8", "Buffer, ATR mult": "1.0", "Ratchet trail": "off"},
        stats="ATR 3.0 / 3R, pivot bars 8, buffer 1.0, trail OFF, Follow: 34 trades, +3,450, PF 2.42, max DD 803; first half +1,719 / second half +1,538. 5.4 years of data, so about 6 trades a year.",
        notes=["Alternative with more trades: Geometry ATR, SL 1.5 ATR, TP 3R, pivot bars 3, buffer 1.0, Emulator trail: 189 trades, +2,028, PF 1.40, max DD 1,031 (+1,369 / +612).",
               "Every percent stop below 0.5% is a fill-bar artefact on 240m and above (46 to 96% same-bar exits) and is excluded."]),
   dict(tf="Daily", verdict="Trade with the daily ATR block", overrides={"Geometry": "ATR", "SL, ATR mult (ATR mode)": "2.0", "TP, R multiple of SL (ATR mode)": "2.5", "   pivot bars each side": "8", "Buffer, ATR mult": "0.5", "Ratchet trail": "off"},
        stats="ATR 2.0 / 2.5R, pivot bars 8, buffer 0.5, trail OFF, Follow: 56 trades, +4,767, PF 2.66, max DD 451; first half +1,602 / second half +3,090; no fill-bar exits. 10.8 years of data, about 5 trades a year.",
        notes=["Alternative: ATR 3.0 / 3R, pivot bars 8, buffer 2.0, Emulator trail: 55 trades, +3,039, PF 4.29, max DD 296 (+938 / +2,024).",
               "Positions hold for days: overnight financing on an index CFD is not modelled and will matter at this timeframe."]),
   dict(tf="Weekly", verdict="Context only", overrides={"Geometry": "ATR", "SL, ATR mult (ATR mode)": "2.0", "TP, R multiple of SL (ATR mode)": "2.5", "   pivot bars each side": "8", "Buffer, ATR mult": "0.5", "Ratchet trail": "off"},
        stats="Same block as daily: 66 trades, +2,093, PF 1.53, max DD 1,027 over 52 years (about one trade a year); first half +359 / second half +1,839.",
        notes=["Not a trading timeframe for this system. Monthly and quarterly exports were stored but not swept: a 3-bar pivot needs 7 months to confirm."]),
  ]),
 "XAU": dict(
  symbol="XAUUSD", script="pine/XPW_Breakout_v2.10_XAUUSD.pine", unit="per 1 oz, VT Markets raw costs; multiply by 100 for one MT5 lot",
  tfs=[
   dict(tf="5m", verdict="DO NOT TRADE", overrides={}, stats="Defaults: 48 trades, -59 per oz. Every geometry that survives costs elsewhere is negative on 5m.",
        notes=["No settings sheet."]),
   dict(tf="10m", verdict="Trade with Donchian 20", overrides={"Pivot levels (v2.01)": "off", "Donchian levels (prior N bars)": "on", "   Donchian length": "20"},
        stats="Donchian 20, ATR 1.5 / 2.5R, buffer 1.0, Emulator trail, Follow: 124 trades, +141 per oz, PF 1.27, max DD 85; first half +109 / second half +37. Most robust level source on 10m (94% of the grid positive).",
        notes=["Pivot defaults on 10m: 134 trades, +99, PF 1.16, second half +8 (a coin flip). Donchian 10 with Recheck is the higher net (+182, PF 1.36, 111 trades, +148 / +33).",
               "Single-cell alternative on pivots: Geometry Pct, SL 0.5%, TP 1.25%, pivot bars 8, buffer 0.5, trail OFF: 23 trades, +452, PF 3.06, max DD 44. Thin: the walk-forward's first-half pick on 10m made +80 out of sample."]),
   dict(tf="15m", verdict="SHIPPED DEFAULTS - change nothing", overrides={},
        stats="101 trades, +213 per oz, PF 1.49, max DD 94; first half +31 / second half +177; walk-forward out of sample +177. Recheck: 81 trades, +216, PF 1.65.",
        notes=["The pivot is the best and most robust level source on 15m (90 to 96% of the grid positive); every Donchian length is behind it.",
               "Single-cell alternative: ATR 3.0 / 2.5R, pivot bars 3, buffer 2.0, trail OFF: 18 trades, +551, PF 3.46, max DD 56. Fewer trades, and the 15m first-half plateau pick lost 42 out of sample, so prefer the defaults."]),
   dict(tf="30m", verdict="SHIPPED DEFAULTS - change nothing", overrides={},
        stats="54 trades, +194 per oz, PF 1.65, max DD 104; first half +71 / second half +79; walk-forward out of sample +79. Recheck: 44 trades, +92, PF 1.34 (-3 / +51), so keep Follow here.",
        notes=["Pivot is the most robust source on 30m (82 to 84% of the grid positive); Donchian 20 is close (+109, PF 1.28) and the others are behind.",
               "Single-cell alternative: ATR 3.0 / 1.5R, pivot bars 3, buffer 2.0, Emulator trail: 35 trades, +389, PF 6.20, max DD 40. The 30m first-half plateau pick lost 13 out of sample; treat as optional."]),
   dict(tf="60m", verdict="Trade with Donchian 20", overrides={"Pivot levels (v2.01)": "off", "Donchian levels (prior N bars)": "on", "   Donchian length": "20"},
        stats="Donchian 20, ATR 1.5 / 2.5R, buffer 1.0, Emulator trail, Follow: 49 trades, +238 per oz, PF 1.52, max DD 100; first half +155 / second half +93.",
        notes=["Pivot defaults on 60m: 55 trades, +171, PF 1.31, max DD 146, but the first half is -5 (walk-forward out of sample +186). Donchian 20 is positive in both halves with a smaller drawdown.",
               "Donchian 50 is the highest PF on 60m: 33 trades, +258, PF 2.14, max DD 93 (+174 / +30), and 84% of the grid positive with Recheck. Fewer trades; either length is defensible.",
               "Single-cell alternative on pivots: ATR 3.0 / 2.5R, pivot bars 3, buffer 0.5, Script trail: 39 trades, +579, PF 2.50, max DD 106. The 60m first-half best cell lost 396 out of sample: single cells on 60m gold are not trustworthy."]),
   dict(tf="240m", verdict="Trade with Donchian 5", overrides={"Pivot levels (v2.01)": "off", "Donchian levels (prior N bars)": "on", "   Donchian length": "5"},
        stats="Donchian 5, ATR 1.5 / 2.5R, buffer 1.0, Emulator trail, Follow: 64 trades, +942 per oz, PF 1.73, max DD 236; first half +714 / second half +123. Donchian 5 and 10 are 92 to 99% positive across the grid on 240m.",
        notes=["Pivot defaults on 240m: 53 trades, +487, PF 1.40, max DD 422 (Recheck: 47 trades, +648, PF 1.59, +283 / +365).",
               "Pivot alternative with a tighter target: ATR 3.0 / 1.5R, pivot bars 3, buffer 1.0, Script trail: 34 trades, +1,526, PF 2.69, max DD 176; walk-forward out of sample +435.",
               "Swaps are not modelled: a 240m hold often spans the rollover, and gold swaps (triple on Wednesday) can exceed the round-trip cost."]),
  ]),
}

def para(t, st=S): return Paragraph(t, st)

def sheet(sym, meta, tfd, story):
    col = 0 if sym == "BTC" else 1
    spx = sym == "SPX"
    story.append(Paragraph(f"{meta['symbol']} - {tfd['tf']}: {tfd['verdict']}", H1))
    story.append(Paragraph(f"Script: {meta['script']}. Net figures {meta['unit']}. "
                           "Rows shaded yellow differ from the script defaults; everything else is left as the script loads it.", NOTE))
    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>Expected on the calibration data:</b> " + tfd["stats"], B))
    for n in tfd["notes"]:
        story.append(Paragraph("- " + n, NOTE))
    if not tfd["overrides"] and tfd["verdict"].startswith("DO NOT"):
        return
    story.append(Spacer(1, 5))
    rows = [[para("Group", SB), para("Input (as shown in the script)", SB), para("Set to", SB), para("Note", SB)]]
    shade = []
    for label, val, note in HEADER[sym]:
        rows.append([para("Strategy Tester Properties"), para(label), para(f"<b>{val}</b>"), para(note)])
    ov = dict(tfd["overrides"])
    for gname, items in GROUPS:
        for label, dB, dX, note in items:
            default = SPX_DEFAULTS.get(label, dB) if spx else (dB, dX)[col]
            val = ov.pop(label, default)
            changed = val != default
            if changed:
                shade.append(len(rows))
                val_txt = f"<b>{val}</b>  (default {default})"
            else:
                val_txt = val
            rows.append([para(gname), para(label), para(val_txt), para(note)])
    assert not ov, ov
    W = [30*mm, 62*mm, 34*mm, 64*mm]
    t = Table(rows, colWidths=W, repeatRows=1)
    st = TableStyle([
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#bbbbbb")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dde3ea")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 1.5), ("BOTTOMPADDING", (0,0), (-1,-1), 1.5),
    ])
    for r in range(1, 3):
        st.add("BACKGROUND", (0,r), (-1,r), colors.HexColor("#eef2f6"))
    for r in shade:
        st.add("BACKGROUND", (0,r), (-1,r), colors.HexColor("#fff3b0"))
    # group separators
    prev = None
    for r in range(3, len(rows)):
        g = rows[r][0].text
        if g != prev:
            st.add("LINEABOVE", (0,r), (-1,r), 0.8, colors.HexColor("#666666"))
            prev = g
    t.setStyle(st)
    story.append(t)

def cover(story):
    story.append(Paragraph("XPW Breakout v2.10 - settings by timeframe", H1))
    story.append(Paragraph("BTCUSD, XAUUSD and SPX500 builds, TradingView Pine v6. One sheet per timeframe listing every input of the script and what to set it to. "
                           "All numbers come from the calibration sweeps in CALIBRATION.md (sections 7, 13, 14 and 15) on the exports in calibration/data/: "
                           "CRYPTO:BTCUSD 15m to 240m (99 days), MEXC:BTCUSDT 5m, OANDA:XAUUSD 5m to 240m, SPCFD:SPX 15m to weekly (5 months to 52 years). Costs are the VT Markets MT5 account; SPX costs are a placeholder (0.5 point spread) until the spec is confirmed.", B))
    story.append(Paragraph("How to apply a sheet", H2))
    for t in [
        "1. Open the chart on the symbol you trade and the sheet's timeframe. Paste the build's .pine file into the Pine editor and add it to the chart.",
        "2. Strategy Tester > Properties > Defaults > <b>Reset settings</b>, so the header commission and slippage are the build's (BTC: cash 10.5 per contract, 500 ticks; gold: cash 0.13, 5 ticks). Bar Magnifier on if your plan has it.",
        "3. Open the strategy inputs. Leave every row at the script default except the yellow rows of the sheet, which are the only ones that change with the timeframe.",
        "4. Check the on-chart table: the 'Header slippage should be' row must equal the Properties slippage, and the Levels row must not read NONE.",
        "5. Both builds share one logic; only the symbol defaults differ (costs per BTC or per ounce, sizing units, SL/TP/buffer). Do not paste a BTC sheet on a gold chart.",
    ]:
        story.append(Paragraph(t, B))
    story.append(Paragraph("Summary", H2))
    rows = [[para("Symbol / TF", SB), para("Verdict", SB), para("Rows that change", SB), para("Trades", SB), para("Net", SB), para("PF", SB), para("Max DD", SB)]]
    summ = [
     ("BTCUSD 5m and below", "do not trade", "-", "109", "-6,519", "0.49", "-"),
     ("BTCUSD 15m", "trade", "Geometry Pct, SL 1.0%, TP 2.5%, Script trail", "29", "+5,957", "2.30", "2,387"),
     ("BTCUSD 30m", "trade (Donchian 50 variant better)", "Script trail  |  or Donchian 50", "24 | 24", "+5,660 | +7,585", "1.91 | 3.90", "4,625 | 1,277"),
     ("BTCUSD 60m", "shipped defaults", "none", "30", "+10,004", "2.35", "2,956"),
     ("BTCUSD 240m", "low confidence", "Donchian 20 instead of pivots", "27", "+5,850", "1.50", "5,683"),
     ("XAUUSD 5m", "do not trade", "-", "48", "-59/oz", "-", "-"),
     ("XAUUSD 10m", "trade", "Donchian 20 instead of pivots", "124", "+141/oz", "1.27", "85"),
     ("XAUUSD 15m", "shipped defaults", "none", "101", "+213/oz", "1.49", "94"),
     ("XAUUSD 30m", "shipped defaults", "none", "54", "+194/oz", "1.65", "104"),
     ("XAUUSD 60m", "trade", "Donchian 20 instead of pivots", "49", "+238/oz", "1.52", "100"),
     ("XAUUSD 240m", "trade", "Donchian 5 instead of pivots", "64", "+942/oz", "1.73", "236"),
     ("SPX500 5m and below", "not tested", "-", "-", "-", "-", "-"),
     ("SPX500 15m", "borderline", "Pct 0.1% / 0.25%, pivot bars 5, buffer 0.5", "173", "+400/pt", "1.49", "102"),
     ("SPX500 30m", "trade", "Geometry ATR (3.0 / 3R), pivot bars 8, buffer 2.0", "78", "+764/pt", "1.67", "296"),
     ("SPX500 60m", "shipped defaults", "none", "143", "+1,320/pt", "1.59", "333"),
     ("SPX500 120m", "shipped defaults", "none", "151", "+1,329/pt", "1.57", "225"),
     ("SPX500 180m", "trade", "Geometry ATR (3.0 / 3R), pivot bars 8", "82", "+1,838/pt", "2.03", "416"),
     ("SPX500 240m", "trade, few trades", "Geometry ATR (3.0 / 3R), pivot bars 8, buffer 1.0, trail off", "34", "+3,450/pt", "2.42", "803"),
     ("SPX500 daily", "trade", "Geometry ATR 2.0 / 2.5R, pivot bars 8, buffer 0.5, trail off", "56", "+4,767/pt", "2.66", "451"),
     ("SPX500 weekly", "context only", "daily block", "66", "+2,093/pt", "1.53", "1,027"),
    ]
    for r in summ: rows.append([para(x) for x in r])
    t = Table(rows, colWidths=[34*mm, 38*mm, 58*mm, 16*mm, 24*mm, 14*mm, 20*mm], repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#bbbbbb")), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dde3ea")),
                           ("VALIGN", (0,0), (-1,-1), "TOP"), ("TOPPADDING", (0,0), (-1,-1), 1.5), ("BOTTOMPADDING", (0,0), (-1,-1), 1.5)]))
    story.append(t)
    story.append(Paragraph("Net per 1 BTC, per 1 oz (x100 for one gold lot) or per 1 SPX contract at $1 per index point, fixed size, after costs. Trade counts are over the whole export: 99 days of BTC, 2 to 12 weeks of gold, 5 months (15m) to 52 years (weekly) of SPX.", NOTE))
    story.append(Paragraph("Reading the evidence", H2))
    for t in [
        "<b>Shipped defaults</b> (BTC 60m; gold 15m and 30m; SPX 60m and 120m) are the settings chosen to be positive across timeframes rather than best on one. SPX has no single geometry that works from 30m to daily: intraday wants a percent stop, 180m and above an ATR stop, so the sheets switch Geometry per timeframe. They are the only rows validated by a first-half / second-half split and, for gold, a walk-forward (5 of 5 timeframes positive out of sample).",
        "<b>Donchian rows</b> replace the pivot with a rolling prior-N high/low, so the buy stop and sell stop move every bar. They are recommended only where both halves of the export were positive and the level source was robust across the geometry grid. The wrong length is destructive (Donchian 50 on BTC 240m loses in every band).",
        "<b>Follow versus Recheck</b> (what a resting stop does when its level is replaced) is a wash across the grid: median PF difference under 0.1, more trades with Follow. Follow is the default because every calibration number was measured with it.",
        "<b>Single-cell alternatives</b> in the notes are the best plateau cell of that timeframe. They have 18 to 39 trades and the gold walk-forward showed per-timeframe picks failing out of sample 2 to 3 times in 5; use them with that in mind.",
        "<b>Not modelled:</b> swaps and financing, the gold maintenance break and weekend gap, exchange funding, and live spread widening at news.",
    ]:
        story.append(Paragraph(t, B))

story = []
cover(story)
for sym in ("BTC", "XAU", "SPX"):
    meta = SHEETS[sym]
    for tfd in meta["tfs"]:
        story.append(PageBreak())
        sheet(sym, meta, tfd, story)
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm,
                        title="XPW Breakout v2.10 settings by timeframe", author="XPW calibration")
doc.build(story)
print("wrote", OUT)
