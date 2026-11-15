"""
STEP 2 - parity_mt5.py

Run xpw_engine.py (through engine_adapter) on the MT5 M30 bars and diff the
entry and exit signals against the TradingView export in outputs/.

Usage (from the project folder):
    python parity_mt5.py
    python parity_mt5.py --tv-export "outputs\\XPW-OTDI4 S_BTCUSD_30.csv" --tv-utc-offset-hours 3

TradingView facts the diff relies on:
  * TV "List of Trades" rows carry the FILL bar. Orders placed on the signal
    bar's close fill on the next bar's open, so signal bar = fill bar minus
    --tv-fill-lag-bars (default 1).
  * TV export times are in the chart's timezone. MT5 bars are broker server
    time. --tv-utc-offset-hours is added to the TV times to land them on
    server time. Default 0. Set it from the chart's timezone and the broker's
    server offset; the report prints the first TV time and the nearest MT5
    bar so a wrong offset is visible.
  * "trail TP" / "SL" exits are price exits, not engine signals. They are
    counted but excluded from the signal diff. Only "exit once" and
    "opp ENTER" exits are engine signals.

Report: outputs/step2_report.md + .json
  match rate, trade count on each side, first ten mismatches (bar time, cause)

ZERO-RESULT CONTINGENCY: zero engine signals -> one range swap (rerun the
engine on the TV overlap window only). If still zero -> funnel + defect
BLOCKED_NO_SIGNALS. Never a third range.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_adapter as ea  # noqa: E402

BAR = pd.Timedelta(minutes=30)
PRICE_EXIT_TAGS = ("trail", "sl", "stop")


def log(m):
    print(f"[parity] {m}", flush=True)


# ------------------------------------------------------------ TV export ----
def find_tv_export(out_dir: Path) -> Path | None:
    cands = sorted(list(out_dir.glob("*.csv")) + list(out_dir.glob("*.xlsx")), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in cands:
        if p.name.startswith("step") or p.name.startswith("ticks_") or p.name.startswith("parity_"):
            continue
        try:
            df = _read_any(p, nrows=5)
        except Exception:
            continue
        cols = [c.lower() for c in df.columns]
        if any("trade" in c for c in cols) and any("type" in c for c in cols):
            return p
    return None


def _read_any(p: Path, nrows=None) -> pd.DataFrame:
    if p.suffix.lower() == ".xlsx":
        x = pd.ExcelFile(p)
        sheet = next((s for s in x.sheet_names if "trade" in s.lower()), x.sheet_names[0])
        return x.parse(sheet, nrows=nrows)
    return pd.read_csv(p, nrows=nrows)


def load_tv(p: Path, offset_hours: float, lag_bars: int) -> pd.DataFrame:
    df = _read_any(p)
    cols = {c.lower().strip(): c for c in df.columns}
    tcol = next((cols[c] for c in cols if "date" in c or "time" in c), None)
    typecol = next((cols[c] for c in cols if c == "type" or c.endswith(" type")), None)
    sigcol = next((cols[c] for c in cols if "signal" in c or "comment" in c), None)
    pricecol = next((cols[c] for c in cols if "price" in c), None)
    if tcol is None or typecol is None:
        raise SystemExit(f"DEFECT TV_EXPORT_UNREADABLE: columns {list(df.columns)}")
    ev = pd.DataFrame({
        "fill_time": pd.to_datetime(df[tcol]) + pd.Timedelta(hours=offset_hours),
        "type": df[typecol].astype(str).str.strip().str.lower(),
        "signal": df[sigcol].astype(str).str.strip() if sigcol else "",
        "price": df[pricecol] if pricecol else float("nan"),
    })
    ev["bar_time"] = ev["fill_time"].dt.floor("30min") - lag_bars * BAR
    ev["kind"] = ev["type"].map(_kind)
    ev["side"] = ev["type"].apply(lambda s: "long" if "long" in s else ("short" if "short" in s else "?"))
    ev["is_price_exit"] = ev["signal"].str.lower().apply(lambda s: any(t in s for t in PRICE_EXIT_TAGS))
    return ev.dropna(subset=["kind"])


def _kind(t: str):
    if t.startswith("entry"):
        return "enter"
    if t.startswith("exit"):
        return "exit"
    return None


# -------------------------------------------------------------- compare ----
def events_from_engine(sig: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, kind, side in (("enter_long", "enter", "long"), ("enter_short", "enter", "short"),
                            ("exit_long", "exit", "long"), ("exit_short", "exit", "short")):
        for t in sig.loc[sig[col], "time"]:
            rows.append({"bar_time": pd.Timestamp(t), "kind": kind, "side": side})
    return pd.DataFrame(rows, columns=["bar_time", "kind", "side"])


def diff(eng: pd.DataFrame, tv: pd.DataFrame, bar_index: pd.DatetimeIndex) -> dict:
    tv_sig = tv[~tv["is_price_exit"]]
    lo = max(eng["bar_time"].min() if len(eng) else bar_index.min(), tv_sig["bar_time"].min() if len(tv_sig) else bar_index.min())
    hi = min(eng["bar_time"].max() if len(eng) else bar_index.max(), tv_sig["bar_time"].max() if len(tv_sig) else bar_index.max())
    e_in = eng[(eng["bar_time"] >= lo) & (eng["bar_time"] <= hi)]
    t_in = tv_sig[(tv_sig["bar_time"] >= lo) & (tv_sig["bar_time"] <= hi)]

    e_set = {(r.bar_time, r.kind, r.side) for r in e_in.itertuples()}
    t_set = {(r.bar_time, r.kind, r.side) for r in t_in.itertuples()}
    matched = e_set & t_set
    union = e_set | t_set
    e_by_tk = {(t, k): s for t, k, s in e_set}
    t_by_tk = {(t, k): s for t, k, s in t_set}
    bar_set = set(bar_index)

    mism = []
    for key in sorted(union - matched):
        t, k, s = key
        if key in e_set:
            if (t, k) in t_by_tk:
                cause = f"SIDE_DIFFERS engine={s} tv={t_by_tk[(t, k)]}"
            else:
                cause = "ENGINE_ONLY (engine fired, TV did not)"
        else:
            if t not in bar_set:
                cause = "TV_BAR_NOT_IN_MT5 (check --tv-utc-offset-hours / data gap)"
            elif (t, k) in e_by_tk:
                cause = f"SIDE_DIFFERS engine={e_by_tk[(t, k)]} tv={s}"
            else:
                cause = "TV_ONLY (TV fired, engine did not)"
        mism.append({"bar_time": str(t), "kind": k, "side": s, "cause": cause})

    return {
        "overlap": {"start": str(lo), "end": str(hi)},
        "match_rate": (len(matched) / len(union)) if union else None,
        "matched": len(matched), "union": len(union),
        "engine": {"entries_long": int(((e_in.kind == "enter") & (e_in.side == "long")).sum()),
                   "entries_short": int(((e_in.kind == "enter") & (e_in.side == "short")).sum()),
                   "exits": int((e_in.kind == "exit").sum()), "events": int(len(e_in))},
        "tv": {"entries_long": int(((t_in.kind == "enter") & (t_in.side == "long")).sum()),
               "entries_short": int(((t_in.kind == "enter") & (t_in.side == "short")).sum()),
               "signal_exits": int((t_in.kind == "exit").sum()),
               "price_exits_excluded": int(tv["is_price_exit"].sum()), "events": int(len(t_in))},
        "mismatches_total": len(mism),
        "mismatches_first10": mism[:10],
    }


def funnel(bars: pd.DataFrame, sig: pd.DataFrame | None, err: str | None) -> dict:
    f = {"bars_loaded": int(len(bars)), "engine_error": err}
    if sig is not None:
        f["engine_rows"] = int(len(sig))
        f["enter_long"] = int(sig["enter_long"].sum())
        f["enter_short"] = int(sig["enter_short"].sum())
        f["exit_long"] = int(sig["exit_long"].sum())
        f["exit_short"] = int(sig["exit_short"].sum())
    if len(bars) == 0:
        f["first_blocking_condition"] = "bars_loaded == 0 (run mt5_data.py first)"
    elif err:
        f["first_blocking_condition"] = f"engine raised: {err}"
    elif sig is not None and len(sig) == 0:
        f["first_blocking_condition"] = "engine returned 0 rows"
    else:
        f["first_blocking_condition"] = "engine returned rows but every enter/exit flag is False (check BIND 2 column names via `python engine_adapter.py --probe`)"
    return f


# ----------------------------------------------------------------- main ----
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--symbol", default="BTCUSD")
    ap.add_argument("--tv-export", default=None)
    ap.add_argument("--tv-utc-offset-hours", type=float, default=0.0)
    ap.add_argument("--tv-fill-lag-bars", type=int, default=1)
    a = ap.parse_args()

    project = Path(a.project)
    out_dir = project / "outputs"
    out_dir.mkdir(exist_ok=True)
    bars_csv = project / "data" / "mt5" / f"{a.symbol}_M30.csv"
    if not bars_csv.exists():
        raise SystemExit(f"DEFECT BLOCKED_NO_BARS: {bars_csv} missing, run mt5_data.py")
    bars = pd.read_csv(bars_csv, parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    log(f"bars: {len(bars):,}  {bars.time.iloc[0]} .. {bars.time.iloc[-1]}")

    tv_path = Path(a.tv_export) if a.tv_export else find_tv_export(out_dir)
    if tv_path is None or not tv_path.exists():
        raise SystemExit("DEFECT BLOCKED_NO_TV_EXPORT: no TradingView List-of-Trades export found in outputs/")
    tv = load_tv(tv_path, a.tv_utc_offset_hours, a.tv_fill_lag_bars)
    log(f"TV export: {tv_path.name}  events={len(tv)}  {tv.fill_time.min()} .. {tv.fill_time.max()} (after offset {a.tv_utc_offset_hours:+}h)")

    report = {"bars_path": str(bars_csv), "tv_export": str(tv_path), "tv_utc_offset_hours": a.tv_utc_offset_hours,
              "tv_fill_lag_bars": a.tv_fill_lag_bars, "defects": [], "range_swaps": 0}

    sig, err = None, None
    try:
        sig = ea.get_signals(bars)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        log(err)
    n_sig = 0 if sig is None else int(sig[["enter_long", "enter_short", "exit_long", "exit_short"]].values.sum())
    if n_sig == 0:
        log("ZERO signals on full range. One range swap: TV overlap window only.")
        report["range_swaps"] = 1
        lo, hi = tv["bar_time"].min() - 400 * BAR, tv["bar_time"].max() + BAR
        sub = bars[(bars.time >= lo) & (bars.time <= hi)].reset_index(drop=True)
        try:
            sig = ea.get_signals(sub)
            err = None
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
        n_sig = 0 if sig is None else int(sig[["enter_long", "enter_short", "exit_long", "exit_short"]].values.sum())
        if n_sig == 0:
            report["defects"].append({"name": "BLOCKED_NO_SIGNALS", "funnel": funnel(sub, sig, err)})

    if sig is not None and n_sig > 0:
        sig.to_csv(out_dir / "parity_engine_signals.csv", index=False)
        eng = events_from_engine(sig)
        report["diff"] = diff(eng, tv, pd.DatetimeIndex(bars["time"]))
        # a visible sanity row for the timezone offset
        first_tv = tv["bar_time"].min()
        near = bars.iloc[(bars.time - first_tv).abs().argsort()[:1]]
        report["diff"]["offset_check"] = {"first_tv_signal_bar": str(first_tv), "nearest_mt5_bar": str(near.time.iloc[0]),
                                          "tv_entry_price": float(tv.loc[tv.bar_time == first_tv, "price"].iloc[0]) if (tv.bar_time == first_tv).any() else None,
                                          "mt5_bar_open_next": float(bars.loc[bars.time == first_tv + BAR, "open"].iloc[0]) if (bars.time == first_tv + BAR).any() else None}

    (out_dir / "step2_report.json").write_text(json.dumps(report, indent=2, default=str))
    md = render_md(report)
    (out_dir / "step2_report.md").write_text(md)
    print(md)
    return 0 if not report["defects"] else 1


def render_md(r: dict) -> str:
    L = ["# STEP 2 - parity vs TradingView", ""]
    L.append(f"TV export: {r['tv_export']}  |  offset {r['tv_utc_offset_hours']:+}h  |  fill lag {r['tv_fill_lag_bars']} bar  |  range swaps {r['range_swaps']}")
    L.append("")
    d = r.get("diff")
    if d:
        mr = d["match_rate"]
        L.append(f"- overlap: {d['overlap']['start']} .. {d['overlap']['end']}")
        L.append(f"- **match rate: {mr * 100:.2f}%** ({d['matched']} of {d['union']} signal events)")
        L.append(f"- engine: {d['engine']['entries_long']} long entries, {d['engine']['entries_short']} short entries, {d['engine']['exits']} signal exits")
        L.append(f"- TradingView: {d['tv']['entries_long']} long entries, {d['tv']['entries_short']} short entries, {d['tv']['signal_exits']} signal exits, {d['tv']['price_exits_excluded']} trail/SL exits excluded from the diff")
        oc = d["offset_check"]
        L.append(f"- offset check: first TV signal bar {oc['first_tv_signal_bar']} vs nearest MT5 bar {oc['nearest_mt5_bar']}; TV fill price {oc['tv_entry_price']} vs MT5 next-bar open {oc['mt5_bar_open_next']}")
        L.append("")
        L.append(f"## First ten mismatches (of {d['mismatches_total']})")
        L.append("| bar time | kind | side | cause |")
        L.append("|---|---|---|---|")
        for m in d["mismatches_first10"]:
            L.append(f"| {m['bar_time']} | {m['kind']} | {m['side']} | {m['cause']} |")
    if r["defects"]:
        L.append("")
        L.append("## DEFECTS")
        for x in r["defects"]:
            L.append(f"- **{x['name']}**: first blocking condition = {x['funnel'].get('first_blocking_condition')}")
            L.append(f"  - funnel: `{json.dumps(x['funnel'], default=str)}`")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
