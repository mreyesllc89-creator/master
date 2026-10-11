"""Write MT5 Strategy Tester .set files for RegimeTrend_EA v1.50.

Each line: Name=value||start||step||stop||Y/N  (Y = optimise this input).
"""
import rt_model as rt

TF_ENUM = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}

# EA input name -> (python key, formatter)
MAP = [
    # indicator settings
    ("InpRegimeTF", "regime_tf", "tf"), ("InpErPeriod", "er_period", "i"), ("InpEnterTrend", "enter", "f"),
    ("InpExitTrend", "exit", "f"), ("InpAtrPeriod", "atr_period", "i"), ("InpAtrMult", "atr_mult", "f"),
    ("InpMinDwell", "min_dwell", "i"), ("InpShockMult", "shock_mult", "f"), ("InpUseClosedBars", True, "b"),
    ("InpMacroTF", "macro_tf", "tf"), ("InpMacroEmaPeriod", "macro_ema", "i"), ("InpMacroSlopeBars", "macro_slope", "i"),
    ("InpMacroDeadbandPct", "macro_deadband", "f"), ("InpMacroMinDwell", "macro_min_dwell", "i"),
    # money management
    ("InpRiskMode", 1, "i"), ("InpRiskPercent", "risk_pct", "f"), ("InpLotSize", 0.10, "f"),
    ("InpMinStopAtr", "min_stop_atr", "f"), ("InpMinStopPoints", "min_stop_pts", "i"), ("InpMaxLots", "max_lots", "f"),
    ("InpMaxMarginPct", 25.0, "f"), ("InpMagic", 20260922, "i"), ("InpSlippagePoints", 20, "i"),
    # risk / trailing
    ("InpUseSuperTrendSL", "use_st_sl", "b"), ("InpTrailSuperTrend", "_trail_on", "b"),
    ("InpTrailStepPoints", "trail_step_pts", "i"), ("InpUseBreakEven", "use_be", "b"), ("InpBreakEvenR", "be_r", "f"),
    ("InpBreakEvenBuffer", "be_buffer_pts", "f"), ("InpTakeProfitR", "tp_r", "f"), ("InpExitMode", "exit_mode", "i"),
    ("InpExitOrderTimeout", 120, "i"),
    # filters
    ("InpTradeDirection", "trade_direction", "i"), ("InpUseMacroFilter", "use_macro_filter", "b"),
    ("InpStrictMacroShorts", "strict_shorts", "b"), ("InpStrictMacroLongs", "strict_longs", "b"),
    ("InpUseSessionFilter", "use_session", "b"), ("InpStartHourGMT", "start_hour", "i"), ("InpEndHourGMT", "end_hour", "i"),
    ("InpTesterGMTOffset", 2, "i"), ("InpTesterDst", 1, "i"),
    # v1.50 entry
    ("InpMaxSpreadPoints", "max_spread_pts", "i"), ("InpMinErEntry", "min_er_entry", "f"),
    ("InpEntryPrevState", "entry_prev_state", "i"), ("InpLateEntryBars", "late_entry_bars", "i"),
    ("InpReentryAfterStop", "reentry_after_stop", "b"), ("InpSlAtrMult", "sl_atr_mult", "f"), ("InpMaxStopAtr", "max_stop_atr", "f"),
    # v1.50 exit
    ("InpExitOnStFlip", "exit_on_st_flip", "b"), ("InpErExit", "er_exit", "f"), ("InpMaxBarsInTrade", "max_bars_in_trade", "i"),
    ("InpCloseFridayHour", "close_friday_hour", "i"),
    # v1.50 trailing
    ("InpTrailSource", "_trail_source", "i"), ("InpTrailAtrMult", "trail_atr_mult", "f"), ("InpTrailAtrK", "trail_atr_k", "f"),
    ("InpTrailActivateR", "trail_activate_r", "f"), ("InpLockTriggerR", "lock_trigger_r", "f"), ("InpLockR", "lock_r", "f"),
    ("InpPartialR", "partial_r", "f"), ("InpPartialPercent", "partial_pct", "f"),
    # gauge
    ("InpShowGauge", True, "b"), ("InpGaugeCorner", 2, "i"), ("InpGaugeX", 20, "i"), ("InpGaugeY", 20, "i"), ("InpGaugeSize", 220, "i"),
]


def _fmt(v, kind):
    if kind == "b":
        return "true" if (v is True or (not isinstance(v, bool) and float(v) > 0)) else "false"
    if kind == "i":
        return str(int(round(float(v))))
    if kind == "tf":
        return str(TF_ENUM[v])
    return f"{float(v):g}"


def write_set(path, ind, ea, opt_ranges=None, comment=""):
    """ind: indicator dict; ea: EA dict (python keys). opt_ranges: {InpName: (start, step, stop)}."""
    p = dict(rt.IND_DEFAULTS); p.update(ind)
    e = dict(rt.EA_DEFAULTS); e.update(ea)
    tm = int(e["trail_mode"])
    e["_trail_on"] = 1 if tm > 0 else 0
    e["_trail_source"] = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3}[tm]
    opt_ranges = opt_ranges or {}
    lines = [f"; RegimeTrend_EA v1.50 settings - {comment}", f"; chart timeframe: {p['chart_tf']}", ""]
    for name, key, kind in MAP:
        if isinstance(key, str):
            v = p[key] if key in p else e[key]
        else:
            v = key
        val = _fmt(v, kind)
        if name in opt_ranges:
            a, s, b = opt_ranges[name]
            lines.append(f"{name}={val}||{_fmt(a, kind)}||{_fmt(s, kind)}||{_fmt(b, kind)}||Y")
        else:
            if kind == "tf":
                lines.append(f"{name}={val}||0||0||0||N")
            else:
                lines.append(f"{name}={val}||{val}||{val}||{val}||N")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path
