"""
STEP 1 - mt5_data.py

Connect to the running MetaTrader 5 terminal (VT Markets), read and log the
BTCUSD symbol spec, pull M30 bars and real ticks from 2022-01-01 to now into
data/mt5/, and write a step report.

Nothing here is hardcoded from the spec: every later script reads
data/mt5/<SYMBOL>_spec.json.

Usage (run from the project folder):
    python mt5_data.py
    python mt5_data.py --terminal "C:\\Program Files\\VT Markets MT5 Terminal\\terminal64.exe"
    python mt5_data.py --symbol BTCUSD --start 2022-01-01

Outputs:
    data/mt5/<SYMBOL>_spec.json          symbol + account spec (source of truth)
    data/mt5/<SYMBOL>_M30.csv            bars
    data/mt5/<SYMBOL>_ticks.parquet      ticks (CSV fallback if pyarrow is missing)
    outputs/step1_report.md              the step report
    outputs/step1_report.json            the same numbers, machine readable

Timestamps: MT5 returns broker server time as epoch seconds. They are stored
as naive datetimes labelled "server time" and NOT converted. parity_mt5.py
takes an explicit offset for the TradingView export.

ZERO-RESULT CONTINGENCY: a zero-bar or zero-tick pull is treated as a broken
run. One range swap is allowed (--fallback-start, default 2024-01-01). If the
rerun also zeros, the decision funnel is instrumented and the defect is named
(BLOCKED_NO_BARS / BLOCKED_NO_TICKS). Never a third range.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover
    print("DEFECT BLOCKED_NO_MT5_PACKAGE: pip install MetaTrader5 (Windows only)")
    sys.exit(2)

GAP_LIMIT = timedelta(hours=2)


# ----------------------------------------------------------------- helpers --
def log(msg: str) -> None:
    print(f"[mt5_data] {msg}", flush=True)


def last_error() -> str:
    code, text = mt5.last_error()
    return f"{code}: {text}"


def filling_mode_name(mode: int) -> str:
    names = []
    if mode & 1:
        names.append("FOK")
    if mode & 2:
        names.append("IOC")
    if mode & 4:
        names.append("BOC")
    return "|".join(names) if names else f"unknown({mode})"


def connect(terminal: str | None) -> dict:
    ok = mt5.initialize(terminal) if terminal else mt5.initialize()
    if not ok:
        raise SystemExit(f"DEFECT BLOCKED_NO_TERMINAL: mt5.initialize failed: {last_error()}")
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti is None or ai is None:
        raise SystemExit(f"DEFECT BLOCKED_NO_TERMINAL: terminal_info/account_info None: {last_error()}")
    info = {
        "terminal_path": ti.path,
        "terminal_company": ti.company,
        "terminal_name": ti.name,
        "terminal_connected": bool(ti.connected),
        "terminal_build": ti.build,
        "account_login": ai.login,
        "account_server": ai.server,
        "account_currency": ai.currency,
        "account_leverage": ai.leverage,
        "account_balance": ai.balance,
    }
    log(f"terminal: {ti.name} ({ti.company}) build {ti.build} path={ti.path} connected={ti.connected}")
    log(f"account : {ai.login}@{ai.server} currency={ai.currency} leverage={ai.leverage}")
    return info


def read_spec(symbol: str, acct: dict) -> dict:
    if not mt5.symbol_select(symbol, True):
        raise SystemExit(f"DEFECT BLOCKED_NO_SYMBOL: symbol_select({symbol}) failed: {last_error()}")
    si = mt5.symbol_info(symbol)
    if si is None:
        raise SystemExit(f"DEFECT BLOCKED_NO_SYMBOL: symbol_info({symbol}) None: {last_error()}")
    spec = {
        "symbol": symbol,
        "digits": si.digits,
        "point": si.point,
        "tick_size": si.trade_tick_size,
        "tick_value": si.trade_tick_value,
        "tick_value_profit": si.trade_tick_value_profit,
        "tick_value_loss": si.trade_tick_value_loss,
        "stops_level": si.trade_stops_level,
        "freeze_level": si.trade_freeze_level,
        "contract_size": si.trade_contract_size,
        "volume_min": si.volume_min,
        "volume_max": si.volume_max,
        "volume_step": si.volume_step,
        "filling_mode": si.filling_mode,
        "filling_mode_name": filling_mode_name(si.filling_mode),
        "trade_mode": si.trade_mode,
        "spread_current_points": si.spread,
        "spread_float": bool(si.spread_float),
        "currency_base": si.currency_base,
        "currency_profit": si.currency_profit,
        "currency_margin": si.currency_margin,
        "account_currency": acct["account_currency"],
        "account_leverage": acct["account_leverage"],
        "margin_initial": si.margin_initial,
        "swap_long": si.swap_long,
        "swap_short": si.swap_short,
        "read_at_utc": datetime.now(timezone.utc).isoformat(),
        "terminal": acct,
    }
    log("symbol spec:")
    for k in ("digits", "point", "tick_size", "stops_level", "freeze_level", "contract_size",
              "volume_min", "volume_max", "volume_step", "filling_mode_name", "account_currency"):
        log(f"  {k:18s} = {spec[k]}")
    return spec


def pull_bars(symbol: str, start: datetime, end: datetime, out_csv: Path) -> pd.DataFrame:
    """M30 bars, pulled in 60-day windows (copy_rates_range caps on big ranges)."""
    frames = []
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=60), end)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, cur, nxt)
        if rates is None:
            log(f"  bars {cur:%Y-%m-%d}..{nxt:%Y-%m-%d}: None ({last_error()})")
        elif len(rates):
            frames.append(pd.DataFrame(rates))
        cur = nxt
    if not frames:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
    df = pd.concat(frames, ignore_index=True).drop_duplicates("time").sort_values("time")
    df["time"] = pd.to_datetime(df["time"], unit="s")  # server time, naive
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return df.reset_index(drop=True)


def pull_ticks(symbol: str, start: datetime, end: datetime, out_path: Path) -> dict:
    """Real ticks (COPY_TICKS_ALL), one day per call, streamed to parquet.

    Returns the tick summary: count, first, last, gaps (> GAP_LIMIT) found
    across the whole stream, including across day boundaries.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        use_parquet = True
    except ImportError:
        use_parquet = False
        log("pyarrow not installed: writing ticks as CSV instead (slower, larger)")

    out_path = out_path if use_parquet else out_path.with_suffix(".csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    writer = None
    csv_header_written = False
    count = 0
    first_ms = None
    last_ms = None
    gaps: list[tuple[str, str, float]] = []
    days_empty = 0
    gap_ms = GAP_LIMIT.total_seconds() * 1000.0

    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=1), end)
        ticks = mt5.copy_ticks_range(symbol, cur, nxt, mt5.COPY_TICKS_ALL)
        if ticks is None or len(ticks) == 0:
            days_empty += 1
            cur = nxt
            continue
        t_ms = ticks["time_msc"].astype(np.int64)
        bid = ticks["bid"].astype(np.float64)
        ask = ticks["ask"].astype(np.float64)
        flags = ticks["flags"].astype(np.int32)

        # gaps inside the day and against the previous chunk's last tick
        if last_ms is not None and t_ms[0] - last_ms > gap_ms:
            gaps.append((_ms_str(last_ms), _ms_str(t_ms[0]), (t_ms[0] - last_ms) / 3.6e6))
        d = np.diff(t_ms)
        idx = np.nonzero(d > gap_ms)[0]
        for i in idx:
            gaps.append((_ms_str(t_ms[i]), _ms_str(t_ms[i + 1]), d[i] / 3.6e6))

        if first_ms is None:
            first_ms = int(t_ms[0])
        last_ms = int(t_ms[-1])
        count += len(t_ms)

        if use_parquet:
            table = pa.table({"time_msc": t_ms, "bid": bid, "ask": ask, "flags": flags})
            if writer is None:
                writer = pq.ParquetWriter(str(out_path), table.schema, compression="zstd")
            writer.write_table(table)
        else:
            chunk = pd.DataFrame({"time_msc": t_ms, "bid": bid, "ask": ask, "flags": flags})
            chunk.to_csv(out_path, mode="a", header=not csv_header_written, index=False)
            csv_header_written = True

        if cur.day == 1:
            log(f"  ticks through {cur:%Y-%m-%d}: {count:,}")
        cur = nxt

    if writer is not None:
        writer.close()

    return {
        "path": str(out_path),
        "format": "parquet" if use_parquet else "csv",
        "count": count,
        "first": _ms_str(first_ms) if first_ms is not None else None,
        "last": _ms_str(last_ms) if last_ms is not None else None,
        "days_empty": days_empty,
        "gaps_over_2h": [{"from": a, "to": b, "hours": round(h, 2)} for a, b, h in gaps],
    }


def _ms_str(ms) -> str:
    return datetime.utcfromtimestamp(int(ms) / 1000.0).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def funnel(symbol: str, start: datetime, end: datetime) -> dict:
    """Instrument the decision funnel after a double zero result."""
    si = mt5.symbol_info(symbol)
    ti = mt5.terminal_info()
    probe_bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 10)
    probe_ticks = mt5.copy_ticks_from(symbol, end - timedelta(days=1), 1000, mt5.COPY_TICKS_ALL)
    out = {
        "terminal_connected": bool(ti.connected) if ti else None,
        "symbol_visible": bool(si.visible) if si else None,
        "symbol_trade_mode": si.trade_mode if si else None,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "last_10_bars_available": 0 if probe_bars is None else len(probe_bars),
        "last_1000_ticks_available": 0 if probe_ticks is None else len(probe_ticks),
        "last_error": last_error(),
    }
    if out["last_10_bars_available"]:
        out["newest_bar_time"] = _ms_str(int(probe_bars[-1]["time"]) * 1000)
    if out["last_1000_ticks_available"]:
        out["oldest_probe_tick"] = _ms_str(int(probe_ticks[0]["time_msc"]))
    # first blocking condition, top down
    if not out["terminal_connected"]:
        out["first_blocking_condition"] = "terminal_connected == False"
    elif not out["symbol_visible"]:
        out["first_blocking_condition"] = "symbol not visible in Market Watch"
    elif out["last_10_bars_available"] == 0:
        out["first_blocking_condition"] = "copy_rates_from_pos returned 0 bars"
    elif out["last_1000_ticks_available"] == 0:
        out["first_blocking_condition"] = "copy_ticks_from returned 0 ticks (tick history not downloaded in terminal)"
    else:
        out["first_blocking_condition"] = "data exists now but not in requested range (range earlier than history start)"
    return out


# -------------------------------------------------------------------- main --
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".", help="project folder (holds data/ and outputs/)")
    ap.add_argument("--symbol", default="BTCUSD")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default=None, help="default: now (UTC)")
    ap.add_argument("--fallback-start", default="2024-01-01", help="the ONE allowed range swap")
    ap.add_argument("--terminal", default=None, help="terminal64.exe path if several terminals are open")
    ap.add_argument("--skip-ticks", action="store_true")
    args = ap.parse_args()

    project = Path(args.project)
    data_dir = project / "data" / "mt5"
    out_dir = project / "outputs"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end) if args.end else datetime.utcnow()

    acct = connect(args.terminal)
    spec = read_spec(args.symbol, acct)
    spec_path = data_dir / f"{args.symbol}_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2))
    log(f"spec written: {spec_path}")

    report: dict = {"symbol": args.symbol, "spec_path": str(spec_path), "defects": [],
                    "range_used": {"start": start.isoformat(), "end": end.isoformat()}, "range_swaps": 0}

    # ---- bars
    bars_csv = data_dir / f"{args.symbol}_M30.csv"
    log(f"pulling M30 bars {start:%Y-%m-%d} .. {end:%Y-%m-%d %H:%M}")
    bars = pull_bars(args.symbol, start, end, bars_csv)
    if len(bars) == 0:
        log("ZERO bars. One range swap allowed.")
        start = datetime.fromisoformat(args.fallback_start)
        report["range_swaps"] = 1
        report["range_used"]["start"] = start.isoformat()
        bars = pull_bars(args.symbol, start, end, bars_csv)
        if len(bars) == 0:
            report["defects"].append({"name": "BLOCKED_NO_BARS", "funnel": funnel(args.symbol, start, end)})
    report["bars"] = {
        "path": str(bars_csv),
        "count": int(len(bars)),
        "first": None if len(bars) == 0 else str(bars["time"].iloc[0]),
        "last": None if len(bars) == 0 else str(bars["time"].iloc[-1]),
    }
    log(f"bars: {len(bars):,}  {report['bars']['first']} .. {report['bars']['last']}")

    # ---- ticks
    if args.skip_ticks:
        report["ticks"] = {"skipped": True}
    else:
        tick_path = data_dir / f"{args.symbol}_ticks.parquet"
        log(f"pulling ticks {start:%Y-%m-%d} .. {end:%Y-%m-%d %H:%M} (this takes a while)")
        ticks = pull_ticks(args.symbol, start, end, tick_path)
        if ticks["count"] == 0 and report["range_swaps"] == 0:
            log("ZERO ticks. One range swap allowed.")
            start = datetime.fromisoformat(args.fallback_start)
            report["range_swaps"] = 1
            report["range_used"]["start"] = start.isoformat()
            ticks = pull_ticks(args.symbol, start, end, tick_path)
        if ticks["count"] == 0:
            report["defects"].append({"name": "BLOCKED_NO_TICKS", "funnel": funnel(args.symbol, start, end)})
        report["ticks"] = ticks
        log(f"ticks: {ticks['count']:,}  {ticks['first']} .. {ticks['last']}  gaps>2h: {len(ticks['gaps_over_2h'])}")

    mt5.shutdown()

    (out_dir / "step1_report.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / "step1_report.md").write_text(render_md(report, spec))
    print(render_md(report, spec))
    return 0 if not report["defects"] else 1


def render_md(r: dict, spec: dict) -> str:
    L = ["# STEP 1 - MT5 data", ""]
    L.append(f"Symbol {r['symbol']}  |  range used {r['range_used']['start']} .. {r['range_used']['end']}  |  range swaps {r['range_swaps']}")
    L.append("")
    L.append("## Symbol spec (data/mt5/*_spec.json)")
    L.append("| field | value |")
    L.append("|---|---|")
    for k in ("digits", "point", "tick_size", "tick_value", "stops_level", "freeze_level", "contract_size",
              "volume_min", "volume_max", "volume_step", "filling_mode_name", "account_currency", "account_leverage"):
        L.append(f"| {k} | {spec[k]} |")
    L.append("")
    L.append("## Bars (M30)")
    L.append(f"- count: {r['bars']['count']:,}")
    L.append(f"- first: {r['bars']['first']}  last: {r['bars']['last']}  (server time)")
    L.append("")
    t = r.get("ticks", {})
    L.append("## Ticks")
    if t.get("skipped"):
        L.append("- skipped")
    else:
        L.append(f"- file: {t['path']} ({t['format']})")
        L.append(f"- count: {t['count']:,}")
        L.append(f"- first: {t['first']}  last: {t['last']}  (server time)")
        L.append(f"- empty days: {t['days_empty']}")
        g = t["gaps_over_2h"]
        L.append(f"- gaps > 2h: {len(g)}")
        for x in g[:50]:
            L.append(f"  - {x['from']} -> {x['to']}  ({x['hours']} h)")
        if len(g) > 50:
            L.append(f"  - ... {len(g) - 50} more in step1_report.json")
    L.append("")
    if r["defects"]:
        L.append("## DEFECTS")
        for d in r["defects"]:
            L.append(f"- **{d['name']}**: first blocking condition = {d['funnel'].get('first_blocking_condition')}")
            L.append(f"  - funnel: `{json.dumps(d['funnel'], default=str)}`")
    else:
        L.append("No defects.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
