#!/usr/bin/env python3
"""
Write the TradingView strategy's presets from the MT5 preset files, so both platforms always use
the same values. Run from the repository root after research/make_presets.py:

  python3 research/make_pine_presets.py

It fills the two generated blocks in XLZC_Liquidity_ZeroCross_Bearish_Strategy.pine:
  // <<preset-input>> ... // <</preset-input>>    the Preset dropdown
  // <<preset-values>> ... // <</preset-values>>  one switch per parameter
Conversions: session hours (broker server time = New York + 7h) -> New York HHMM; MT5 timeframe
codes -> TradingView timeframe strings; enums -> the Pine option strings.
"""
import re

PINE = "XLZC_Liquidity_ZeroCross_Bearish_Strategy.pine"
# (dropdown name, preset file, default spread in price units)
PRESETS = [
    ("v1.20 Gold M2/H4", "XLZC_v120_Gold_M2_H4.set", 0.45),
    ("v1.20 Gold M3/H4", "XLZC_v120_Gold_M3_H4.set", 0.45),
    ("v1.20 Gold M3/M15", "XLZC_v120_Gold_M3_M15.set", 0.45),
    ("v1.20 Gold M3/H1", "XLZC_v120_Gold_M3_H1.set", 0.45),
    ("v1.20 Gold M2/H1", "XLZC_v120_Gold_M2_H1.set", 0.45),
    ("v1.20 BTC M1/M15 (low-cost)", "XLZC_v120_BTCUSD_M1_M15.set", 5.0),
    ("v1.20 BTC M5/H2 (low-cost)", "XLZC_v120_BTCUSD_M5_H2.set", 5.0),
    ("v1.20 BTC M3/D1 (low-cost)", "XLZC_v120_BTCUSD_M3_D1.set", 5.0),
    ("v1.10 Gold M3/H1", "XLZC_Bearish_M3_H1_NY.set", 0.45),
    ("v1.10 Gold M2/H1", "XLZC_Bearish_M2_H1_NY.set", 0.45),
    ("v1.10 Gold M3/H4", "XLZC_Bearish_M3_H4_NY.set", 0.45),
    ("v1.10 BTC M3/H1 (low-cost)", "XLZC_Bearish_BTCUSD_M3_H1.set", 5.0),
    ("v1.10 BTC M3/M30 (experimental)", "XLZC_Bearish_BTCUSD_M3_M30.set", 5.0),
]
DEFAULT = "v1.20 Gold M2/H4"
TF = {1: "1", 2: "2", 3: "3", 5: "5", 15: "15", 30: "30", 16385: "60", 16386: "120", 16388: "240", 16408: "D"}
COND = {0: "and", 1: "or", 2: "macd", 3: "ema"}


def read_set(path):
    vals = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith(";") and "=" in line:
            k, v = line.split("=", 1)
            vals[k] = v
    return vals


def ny_hhmm(server_hhmm):
    h, m = map(int, server_hhmm.split(":"))
    mins = (h * 60 + m - 7 * 60) % 1440
    return (mins // 60) * 100 + mins % 60


def preset_params(v, spread):
    b = lambda k: v[k].lower() == "true"
    return {
        "trigTf": ("string", f'"{TF[int(v["TriggerTimeframe"])]}"'),
        "htfTf": ("string", f'"{TF[int(v["HTF_Timeframe"])]}"'),
        "nBars": ("int", v["LiquidityLookbackBars"]),
        "sStr": ("int", v["SwingStrength"]),
        "bufPts": ("float", v["SL_Buffer_Points"]),
        "ntIn": ("int", v["TP_LookbackBars"]),
        "minRR": ("float", v["MinRewardRisk"]),
        "fbRR": ("float", v["TP_FallbackRR"]),
        "minSLPts": ("float", v["MinSL_Points"]),
        "maxSLPts": ("float", v["MaxSL_Points"]),
        "trailOn": ("bool", "true" if b("EnableTrailing") else "false"),
        "tStart": ("float", v["TrailingStart_Points"]),
        "tDist": ("float", v["TrailingDistance_Points"]),
        "sessFrom": ("int", str(ny_hhmm(v["TradingHoursStart"]))),
        "sessTo": ("int", str(ny_hhmm(v["TradingHoursEnd"]))),
        "condMode": ("string", f'"{COND[int(v["HTF_Condition"])]}"'),
        "stochHard": ("bool", "true" if b("StochHardBlock") else "false"),
        "stochRule": ("string", '"or"' if v["StochRule"] == "1" else '"and"'),
        "tpZone": ("bool", "true" if v["TP_Mode"] == "1" else "false"),
        "zoneTol": ("float", v["Zone_Tolerance_Points"]),
        "zoneMin": ("int", v["Zone_MinTouches"]),
        "tpBuf": ("float", v["TP_Buffer_Points"]),
        "spreadDef": ("float", str(spread)),
    }


CUSTOM = {"trigTf": "cTrig", "htfTf": "cHtf", "nBars": "cN", "sStr": "cS", "bufPts": "cBuf", "ntIn": "cNT",
          "minRR": "cRR", "fbRR": "cFb", "minSLPts": "cMinSL", "maxSLPts": "cMaxSL", "trailOn": "cTrail",
          "tStart": "cTStart", "tDist": "cTDist", "sessFrom": "cSessFrom", "sessTo": "cSessTo",
          "condMode": "cCond", "stochHard": "cStochH", "stochRule": "cStochR", "tpZone": "cZone",
          "zoneTol": "cZoneTol", "zoneMin": "cZoneMin", "tpBuf": "cTpBuf", "spreadDef": "0.0"}


def main():
    sets = [(name, preset_params(read_set(f"presets/{f}"), spread)) for name, f, spread in PRESETS]
    names = [n for n, _ in sets] + ["Custom"]
    opts = ", ".join(f'"{n}"' for n in names)
    inp = (f'preset = input.string("{DEFAULT}", "Preset", options = [{opts}], group = gPre,\n'
           '     tooltip = "v1.20 = final calibration (recommended). A preset overrides the Custom inputs below '
           '(except costs, risk %, display). Use Custom to set everything yourself.")')
    lines = []
    for key in sets[0][1]:
        typ = sets[0][1][key][0]
        lines.append(f"{typ} {key} = switch preset")
        for name, prm in sets:
            lines.append(f'    "{name}" => {prm[key][1]}')
        lines.append(f"    => {CUSTOM[key]}")
    s = open(PINE).read()
    s = re.sub(r"(// <<preset-input>>[^\n]*\n).*?(// <</preset-input>>)", lambda m: m.group(1) + inp + "\n" + m.group(2),
               s, flags=re.S)
    s = re.sub(r"(// <<preset-values>>[^\n]*\n).*?(// <</preset-values>>)",
               lambda m: m.group(1) + "\n".join(lines) + "\n" + m.group(2), s, flags=re.S)
    open(PINE, "w").write(s)
    print(f"{len(sets)} presets written to {PINE}")


if __name__ == "__main__":
    main()
