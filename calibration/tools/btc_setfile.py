"""MT5 .set writer for BTCSignalFlow_Test_EA (v1.10 inputs + v1.11 additions)."""
import btc_model as bm

TF_ENUM = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
MAP = [
    ("InpMethod", "method", "i"), ("InpSignalPeriod", "chart_tf", "tf"), ("InpBreakoutBars", "length", "i"),
    ("InpExitBars", "exit_bars", "i"), ("InpMinER", "efficiency", "f"), ("InpPullbackEMA", "pullback_ema", "i"),
    ("InpClearanceATR", "clearance", "f"),
    ("InpRiskPercent", "risk_pct", "f"), ("InpStopATR", "stop_atr", "f"), ("InpTrailATR", "trail_atr", "f"),
    ("InpTakeProfitR", "tp_r", "f"), ("InpMaxHoldBars", "max_hold_bars", "i"), ("InpMaxSpreadATR", "max_spread_atr", "f"),
    ("InpMaxMarginPct", "max_margin_pct", "f"), ("InpSlippagePoints", 1000, "i"), ("InpMagic", 2026101103, "i"),
    # v1.11
    ("InpUseSignalExit", "_signal_exit", "b"), ("InpTrailSource", "_trail_source", "i"), ("InpTrailActivateR", "trail_activate_r", "f"),
    ("InpUseBreakEven", "use_be", "b"), ("InpBreakEvenR", "be_r", "f"), ("InpLockTriggerR", "lock_trigger_r", "f"),
    ("InpLockR", "lock_r", "f"), ("InpPartialR", "partial_r", "f"), ("InpPartialPercent", "partial_pct", "f"),
    ("InpErExit", "er_exit", "f"), ("InpTradeDirection", "_direction", "i"),
]


def _fmt(v, kind):
    if kind == "b":
        return "true" if float(v) > 0 else "false"
    if kind == "i":
        return str(int(round(float(v))))
    if kind == "tf":
        return str(TF_ENUM[v])
    return f"{float(v):g}"


def write_set(path, sig, ea, opt_ranges=None, comment=""):
    p = dict(bm.SIG_DEFAULTS); p.update(sig)
    e = dict(bm.EA_DEFAULTS); e.update(ea)
    e["_signal_exit"] = 0 if int(e["exit_rule"]) == 1 else 1
    e["_trail_source"] = 1 if int(e["trail_mode"]) == 2 else 0
    e["_direction"] = 1 if e["long_only"] else (2 if e["short_only"] else 0)
    opt_ranges = opt_ranges or {}
    lines = [f"; BTCSignalFlow_Test_EA v1.11 settings - {comment}", f"; chart timeframe: {p['chart_tf']}", ""]
    for name, key, kind in MAP:
        v = (p[key] if key in p else e[key]) if isinstance(key, str) else key
        val = _fmt(v, kind)
        if name in opt_ranges:
            a, s, b = opt_ranges[name]
            lines.append(f"{name}={val}||{_fmt(a, kind)}||{_fmt(s, kind)}||{_fmt(b, kind)}||Y")
        elif kind == "tf":
            lines.append(f"{name}={val}||0||0||0||N")
        elif kind == "b":
            lines.append(f"{name}={val}||false||0||true||N")
        else:
            lines.append(f"{name}={val}||{val}||0||{val}||N")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path
