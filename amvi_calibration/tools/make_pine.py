"""Write a calibrated copy of the strategy for one chart timeframe: the template's code with
other input defaults, title, commission and header. Only defaults change, never the logic.

used by report.py; `python make_pine.py <setting.json> <chart_tf> <out.pine>` writes one file.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "..", "AMVI_FGF_Inverted_XAUUSD_15m.pine")
OLD_TIP = "Calibrated for XAUUSD 15m (see the header)."
AMVI_TOGGLES = {1: "en1", 5: "en5", 15: "en15", 30: "en30", 60: "en60", 240: "en240", 1440: "enD"}
TF_NAME = {1: "1m", 2: "2m", 3: "3m", 5: "5m", 10: "10m", 15: "15m", 30: "30m", 60: "1h", 120: "2h", 240: "4h", 480: "8h", 1440: "1D"}


def tf_str(minutes):
    return "D" if int(minutes) == 1440 else str(int(minutes))


def lit(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        s = repr(round(v, 6))
        return s if "." in s else s + ".0"
    return '"' + str(v) + '"'


def pine_inputs(p, chart_tf):
    """The Pine input defaults that reproduce engine setting p (name -> Python value)."""
    zones = list(p["zones"])[:6]
    d = {
        "fastATRPeriod": int(p["fast"]), "slowATRPeriod": int(p["slow"]), "stdDevPeriod": int(p["sd"]),
        "candleRangePeriod": int(p["cr"]), "normalizationPeriod": int(p["norm"]),
        "aatrWeight": float(p["wA"]), "vrWeight": float(p["wV"]), "nsdWeight": float(p["wS"]), "acrWeight": float(p["wC"]),
        "highVolThreshold": float(p["high"]), "lowVolThreshold": float(p["low"]), "minConfluence": int(p["conf"]),
        "amviTradeDir": "Inverted" if p["inverted"] else "Follow the filter",
        "amviWait": int(p["wait"]),
        "exitAtrLen": int(p["exit_atr"]), "slMult": float(p["sl"]), "tpMult": float(p["tp"]),
        "useTrail": bool(p["trail"]), "trailActMul": float(p["trail_act"]), "trailOffMul": float(p["trail_off"]),
        "useVolExit": bool(p["vol_exit"]), "maxBars": int(p["max_bars"]),
        "fgfTf": tf_str(p["f_tf"]), "fgfLvMode": "Signal close" if p["lv_mode"] == "close" else "Entry price",
        "fgfLast": "Candles" if p["perm_candles"] > 0 else "Until next signal",
        "fgfBars": int(p["perm_candles"]) if p["perm_candles"] > 0 else 1,
        "fgfCheckIn": "Level at candle open" if p["check_open"] else "Tick",
        "fgfBandAtr": float(p["band"]), "fgfAgainst": bool(p["against"]),
        "fgfAllowBuy": bool(p["allow_buy"]), "fgfAllowSell": bool(p["allow_sell"]),
        "fgfBurstAtr": float(p["burst_atr"]), "fgfEntryDistAtr": float(p["entry_dist_atr"]),
        "fgfUseBurst": bool(p["use_burst"]), "fgfAnyCombo": bool(p["any_combo"]),
        "fgfDriftBars": int(p["drift_bars"]), "fgfUseDrift": bool(p["use_drift"]),
        "fgfUseZones": bool(p["use_zones"]), "fgfParentTf": tf_str(p["parent_tf"]),
        "fgfRsiLen": int(p["rsi_len"]), "fgfFastLen": int(p["fast_len"]), "fgfMinAligned": int(p["min_aligned"]),
    }
    for tf, name in AMVI_TOGGLES.items():
        d[name] = tf in tuple(p["tfs"])
    for name in ("en1s", "en5s", "en15s", "en30s", "en45s"):
        d[name] = False
    template_zone_tf = {1: "60", 2: "120", 3: "240", 4: "480", 5: "1", 6: "2"}
    for k in range(1, 7):
        on = k <= len(zones)
        d[f"fgfUseZ{k}"] = on
        d[f"fgfZTf{k}"] = tf_str(zones[k - 1]) if on else template_zone_tf[k]
    return d


def read_defaults(src, names):
    """Current default of each input in the template (as written in the source)."""
    out = {}
    for name in names:
        m = re.search(r"^" + re.escape(name) + r"\s*=\s*input\.\w+\((\"[^\"]*\"|[^,]+),", src, re.M)
        if not m:
            raise KeyError(f"input {name} not found in the template")
        out[name] = m.group(1).strip()
    return out


def set_default(src, name, value, tip):
    pat = re.compile(r"^(" + re.escape(name) + r"\s*=\s*input\.\w+\()(\"[^\"]*\"|[^,]+)(,.*)$", re.M)
    m = pat.search(src)
    if not m:
        raise KeyError(f"input {name} not found in the template")
    old = m.group(2).strip()
    new = lit(value)
    rest = m.group(3)
    changed = old != new and not _same_number(old, new)
    if OLD_TIP in rest:
        rest = rest.replace(OLD_TIP, tip)
    elif changed and "tooltip=" not in rest and rest.rstrip().endswith(")"):
        rest = rest.rstrip()[:-1] + ', tooltip="' + tip + '")'
    return src[:m.start()] + m.group(1) + new + rest + src[m.end():], old, changed


def _same_number(a, b):
    try:
        return float(a) == float(b)
    except ValueError:
        return False


def build(p, chart_tf, header_lines, title, shorttitle, commission_pct=0.06, symbol="BTCUSDT.P"):
    """Source text of the calibrated file and the list of (input, template value, new value)."""
    src = open(TEMPLATE, encoding="utf-8").read()
    tip = f"Calibrated for {symbol} {TF_NAME[chart_tf]} (see the header)."
    changes = []
    for name, value in pine_inputs(p, chart_tf).items():
        src, old, changed = set_default(src, name, value, tip)
        if changed:
            changes.append((name, old, lit(value)))
    src = src.replace(OLD_TIP, tip)
    # header: everything between the first line (//@version=6) and the strategy() call
    a = src.index("\n") + 1
    b = src.index("strategy(")
    head = "\n".join("// " + ln if ln else "//" for ln in header_lines)
    bar = "// " + "=" * 85
    src = src[:a] + bar + "\n" + head + "\n" + bar + "\n" + src[b:]
    m = re.search(r'strategy\("[^"]*", shorttitle="[^"]*"', src)
    src = src[:m.start()] + f'strategy("{title}", shorttitle="{shorttitle}"' + src[m.end():]
    src, n = re.subn(r"commission_value=[0-9.]+", f"commission_value={commission_pct}", src, count=1)
    assert n == 1
    return src, changes


if __name__ == "__main__":
    p = json.load(open(sys.argv[1]))
    ctf = int(sys.argv[2])
    text, ch = build(p, ctf, ["test header"], "AMVI test", "AMVI test")
    open(sys.argv[3], "w", encoding="utf-8").write(text)
    for c in ch:
        print(c)
