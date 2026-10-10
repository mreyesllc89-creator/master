"""
engine_adapter.py - the ONE place that touches xpw_engine.py.

xpw_engine.py is never modified. Every other new script calls:

    signals = get_signals(bars_df)            -> DataFrame, one row per bar
    params  = get_strategy_params()           -> trail/stop settings the engine uses
    costs   = get_engine_costs()              -> commission/slippage/qty the engine holds

The signal frame has these columns (bool unless noted):
    time          bar open time (same values as bars_df["time"])
    enter_long, enter_short, exit_long, exit_short
    sig           +1 enter long, -1 enter short, 0 none (after the same-bar
                  long+short cancel rule of the Pine strategy)

BINDING: the body of each function below first tries a list of likely
xpw_engine entry points. If none match, it raises NotBound with the probe
output so whoever runs this (Codex) can edit the three BIND blocks after
reading xpw_engine.py. Run `python engine_adapter.py --probe` to print the
engine's public API, signatures and any constant whose name mentions
commission, slippage, qty, quantity, spread, leverage, trail or stop.

Do not optimize anything here: pass the engine's own defaults through.
"""
from __future__ import annotations

import argparse
import inspect
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

try:
    import xpw_engine  # noqa: E402
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"DEFECT BLOCKED_NO_ENGINE: cannot import xpw_engine from {Path.cwd()}: {e}")


class NotBound(RuntimeError):
    pass


COST_TOKENS = re.compile(r"commission|slip|qty|quantity|contract|spread|leverage|trail|stop|sl_|tp_|risk|capital", re.I)


# ----------------------------------------------------------------- probe ----
def probe() -> str:
    lines = [f"xpw_engine file: {getattr(xpw_engine, '__file__', '?')}", ""]
    lines.append("## functions")
    for name, obj in inspect.getmembers(xpw_engine, inspect.isfunction):
        if obj.__module__ != xpw_engine.__name__:
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = "(?)"
        doc = (inspect.getdoc(obj) or "").splitlines()[:1]
        lines.append(f"- {name}{sig}  {doc[0] if doc else ''}")
    lines.append("")
    lines.append("## classes")
    for name, obj in inspect.getmembers(xpw_engine, inspect.isclass):
        if obj.__module__ != xpw_engine.__name__:
            continue
        try:
            sig = str(inspect.signature(obj))
        except (TypeError, ValueError):
            sig = "(?)"
        lines.append(f"- class {name}{sig}")
        for mname, m in inspect.getmembers(obj, inspect.isfunction):
            if mname.startswith("_") and mname != "__init__":
                continue
            try:
                msig = str(inspect.signature(m))
            except (TypeError, ValueError):
                msig = "(?)"
            lines.append(f"    .{mname}{msig}")
    lines.append("")
    lines.append("## module constants / defaults mentioning cost, qty, trail, stop")
    for name in dir(xpw_engine):
        if name.startswith("__"):
            continue
        val = getattr(xpw_engine, name)
        if inspect.isfunction(val) or inspect.isclass(val) or inspect.ismodule(val):
            continue
        if COST_TOKENS.search(name):
            lines.append(f"- {name} = {val!r}")
    # dataclass / dict style config objects
    for name in dir(xpw_engine):
        val = getattr(xpw_engine, name, None)
        if isinstance(val, dict):
            hits = {k: v for k, v in val.items() if isinstance(k, str) and COST_TOKENS.search(k)}
            if hits:
                lines.append(f"- dict {name}: {hits}")
    return "\n".join(lines)


def _first_attr(names: list[str]):
    for n in names:
        if hasattr(xpw_engine, n):
            return n, getattr(xpw_engine, n)
    return None, None


# --------------------------------------------------------------- signals ----
def get_signals(bars: pd.DataFrame, **overrides) -> pd.DataFrame:
    """Run the engine on M30 bars and normalise the output.

    bars: columns time, open, high, low, close (+ anything else), sorted.
    """
    bars = bars.copy()
    bars["time"] = pd.to_datetime(bars["time"])

    # ---- BIND 1: locate the engine entry point --------------------------
    name, fn = _first_attr([
        "run_engine", "run", "generate_signals", "compute_signals", "signals",
        "get_signals", "evaluate", "process_bars", "backtest_signals",
    ])
    raw = None
    if fn is not None and inspect.isfunction(fn):
        raw = _call_flex(fn, bars, overrides)
    else:
        cname, cls = _first_attr(["XPWEngine", "Engine", "XpwEngine", "Strategy", "OrientationTDI"])
        if cls is not None:
            inst = _construct_flex(cls, overrides)
            for m in ("run", "generate_signals", "compute", "signals", "process", "evaluate", "__call__"):
                if hasattr(inst, m):
                    raw = _call_flex(getattr(inst, m), bars, overrides)
                    break
    if raw is None:
        raise NotBound("engine entry point not found. Edit BIND 1 in engine_adapter.py.\n" + probe())
    # ---- end BIND 1 ----------------------------------------------------

    # ---- BIND 2: normalise whatever the engine returned -----------------
    sig = _normalise(raw, bars)
    # ---- end BIND 2 ----------------------------------------------------

    # Pine rule: long and short entry on the same bar cancel each other.
    both = sig["enter_long"] & sig["enter_short"]
    sig.loc[both, ["enter_long", "enter_short"]] = False
    sig["sig"] = sig["enter_long"].astype(int) - sig["enter_short"].astype(int)
    return sig


def _call_flex(fn, bars, overrides):
    """Call fn(bars, ...) with whichever keyword names its signature accepts."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(bars)
    kw = {k: v for k, v in overrides.items() if k in params}
    return fn(bars, **kw)


def _construct_flex(cls, overrides):
    try:
        params = inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return cls()
    kw = {k: v for k, v in overrides.items() if k in params}
    return cls(**kw)


def _normalise(raw, bars: pd.DataFrame) -> pd.DataFrame:
    """Accept the common shapes: a DataFrame with signal columns, a Series of
    +1/-1/0, a list of trade dicts, or a tuple (entries, exits)."""
    n = len(bars)
    out = pd.DataFrame({
        "time": bars["time"].values,
        "enter_long": False, "enter_short": False, "exit_long": False, "exit_short": False,
    })
    if isinstance(raw, tuple) and len(raw) == 2:
        raw = pd.DataFrame({"entries": raw[0], "exits": raw[1]})
    if isinstance(raw, pd.Series):
        v = raw.reindex(range(n)).fillna(0).astype(int).values if raw.index.dtype.kind in "iu" else raw.values
        out["enter_long"] = v > 0
        out["enter_short"] = v < 0
        return out
    if isinstance(raw, pd.DataFrame):
        cols = {c.lower(): c for c in raw.columns}
        aliases = {
            "enter_long": ["enter_long", "long_entry", "entry_long", "buy", "golong", "go_long", "longsig", "long_sig"],
            "enter_short": ["enter_short", "short_entry", "entry_short", "sell", "goshort", "go_short", "shortsig", "short_sig"],
            "exit_long": ["exit_long", "long_exit", "exitl", "exit_l", "closel", "close_long"],
            "exit_short": ["exit_short", "short_exit", "exits", "exit_s", "closes", "close_short"],
        }
        found = False
        for k, al in aliases.items():
            for a in al:
                if a in cols:
                    out[k] = raw[cols[a]].fillna(False).astype(bool).values[:n] if len(raw) >= n else _align(raw, cols[a], bars)
                    found = True
                    break
        if not found and "sig" in cols:
            v = raw[cols["sig"]].fillna(0).astype(int).values
            out["enter_long"] = v > 0
            out["enter_short"] = v < 0
            found = True
        if not found and "signal" in cols:
            v = raw[cols["signal"]]
            if v.dtype.kind in "if":
                out["enter_long"] = v.values > 0
                out["enter_short"] = v.values < 0
            else:
                s = v.astype(str).str.upper()
                out["enter_long"] = s.str.contains("ENTER LONG|BUY").values
                out["enter_short"] = s.str.contains("ENTER SHORT|SELL").values
                out["exit_long"] = s.str.contains("EXIT LONG|CLOSE LONG").values
                out["exit_short"] = s.str.contains("EXIT SHORT|CLOSE SHORT").values
            found = True
        if found:
            return out
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        # list of events: {"time":..., "type": "ENTER LONG"|...}
        tmap = {pd.Timestamp(t): i for i, t in enumerate(bars["time"])}
        for ev in raw:
            t = pd.Timestamp(ev.get("time") or ev.get("bar_time") or ev.get("timestamp"))
            typ = str(ev.get("type") or ev.get("signal") or ev.get("side") or "").upper()
            i = tmap.get(t)
            if i is None:
                continue
            if "ENTER" in typ and "LONG" in typ or typ in ("BUY", "LONG"):
                out.at[i, "enter_long"] = True
            elif "ENTER" in typ and "SHORT" in typ or typ in ("SELL", "SHORT"):
                out.at[i, "enter_short"] = True
            elif "EXIT" in typ and "LONG" in typ:
                out.at[i, "exit_long"] = True
            elif "EXIT" in typ and "SHORT" in typ:
                out.at[i, "exit_short"] = True
        return out
    raise NotBound(f"engine returned {type(raw)} which _normalise does not understand. Edit BIND 2.\n" + probe())


def _align(raw: pd.DataFrame, col: str, bars: pd.DataFrame):
    """raw indexed by time -> align to bars['time']."""
    idx = pd.to_datetime(raw.index) if "time" not in raw.columns else pd.to_datetime(raw["time"])
    s = pd.Series(raw[col].values, index=idx)
    return s.reindex(pd.to_datetime(bars["time"])).fillna(False).astype(bool).values


# ---------------------------------------------------------------- params ----
# Pine v2.4 defaults, used only when the engine exposes nothing by these names.
PINE_DEFAULTS = {
    "trail_on": True, "trail_unit": "price", "trail_act": 2.0, "trail_off": 1.0,
    "sl_on": False, "sl_dist": 3.0,
    "exit_on_end": True, "opp_closes": True, "trade_dir": "Both",
}


def get_strategy_params() -> dict:
    """Trailing TP / SL settings as the engine holds them."""
    # ---- BIND 3a: strategy parameter names in xpw_engine ---------------
    p = dict(PINE_DEFAULTS)
    p["_source"] = {}
    names = {
        "trail_on": ["TRAIL_ON", "trail_on", "trailOn", "USE_TRAIL"],
        "trail_unit": ["TRAIL_UNIT", "trail_unit", "trailUnit"],
        "trail_act": ["TRAIL_ACT", "trail_act", "trailAct", "TRAIL_ACTIVATION", "trail_activation"],
        "trail_off": ["TRAIL_OFF", "trail_off", "trailOff", "TRAIL_OFFSET", "trail_offset"],
        "sl_on": ["SL_ON", "sl_on", "slOn", "USE_SL", "use_stop"],
        "sl_dist": ["SL_DIST", "sl_dist", "slDist", "STOP_DIST", "stop_dist"],
        "exit_on_end": ["EXIT_ON_END", "exit_on_end", "exitOnEnd"],
        "opp_closes": ["OPP_CLOSES", "opp_closes", "oppCloses"],
        "trade_dir": ["TRADE_DIR", "trade_dir", "tradeDir"],
    }
    for key, cands in names.items():
        n, v = _first_attr(cands)
        if n is not None:
            p[key] = v
            p["_source"][key] = f"xpw_engine.{n}"
        else:
            p["_source"][key] = "PINE_DEFAULT (not found in xpw_engine)"
    # ---- end BIND 3a ---------------------------------------------------
    return p


def get_engine_costs() -> dict:
    """Commission / slippage / quantity as the engine or its config holds them."""
    # ---- BIND 3b: cost names in xpw_engine ----------------------------
    c = {"_source": {}}
    names = {
        "commission_type": ["COMMISSION_TYPE", "commission_type", "commissionType"],
        "commission_value": ["COMMISSION", "commission", "COMMISSION_PCT", "commission_pct", "COMMISSION_RATE", "commission_rate"],
        "slippage": ["SLIPPAGE", "slippage", "SLIPPAGE_USD", "slippage_usd", "SLIP"],
        "qty": ["QTY", "qty", "QUANTITY", "quantity", "CONTRACTS", "contracts", "FIXED_QTY", "fixed_qty", "DEFAULT_QTY", "default_qty"],
        "qty_type": ["QTY_TYPE", "qty_type", "qtyType"],
        "leverage": ["LEVERAGE", "leverage"],
        "spread": ["SPREAD", "spread", "SPREAD_USD", "spread_usd"],
        "risk_pct": ["RISK_PCT", "risk_pct", "RISK_PERCENT", "risk_percent"],
        "calc_qty": ["calcQty", "calc_qty", "position_size", "size_position"],
    }
    for key, cands in names.items():
        n, v = _first_attr(cands)
        if n is not None:
            c[key] = v if not callable(v) else f"<callable {n}>"
            c["_source"][key] = f"xpw_engine.{n}"
        else:
            c[key] = None
            c["_source"][key] = "not found in xpw_engine"
    # ---- end BIND 3b ---------------------------------------------------
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="print the engine API and cost constants")
    ap.add_argument("--bars", default=None, help="CSV of M30 bars: smoke-test get_signals")
    a = ap.parse_args()
    if a.probe or not a.bars:
        print(probe())
        print()
        print("strategy params:", get_strategy_params())
        print("engine costs   :", get_engine_costs())
    if a.bars:
        b = pd.read_csv(a.bars)
        s = get_signals(b)
        print(s[["enter_long", "enter_short", "exit_long", "exit_short"]].sum())
