"""
STEP 3 - backtest_ticks.py

Replay xpw_engine.py signals (M30 bars) on the real MT5 ticks.

Fill rule
    An order is raised at the close of the signal bar (bar open + 30 min).
    It fills on the FIRST tick at or after that moment whose price is at or
    beyond the trigger on the correct side of the book:
        buy  -> ask >= trigger
        sell -> bid <= trigger
    Trigger = the signal bar's close (--trigger close) or the label extreme
    (--trigger extreme: low for long, high for short). The search is bounded
    to the next bar; an order with no qualifying tick is counted UNFILLED.
    A reversal (long -> short on one bar) closes and opens on the same tick.

Exits
    Trailing TP and SL are evaluated on every tick, with the engine's own
    settings (engine_adapter.get_strategy_params; Pine defaults otherwise).
    Long: tracks bid; arms when bid >= entry + act; stop = best_bid - off.
    Short: mirrored on ask.
    Signal exits (END labels / opposite ENTER) are orders as above.

Costs (fixed by the task, never read from the engine)
    commission 0.02 % of notional per side
    slippage   5 USD of price per side (fill price worsened by 5 USD)
    leverage   10 (margin = notional / 10, checked against equity, reported)
    quantity   fixed contracts (--qty; default = the engine's own qty constant
               if the audit found one, else 1.0). No risk-percent sizing.
    notional   qty * contract_size * price, contract_size from the spec file.

Report: outputs/step3_report.md (+ .json), outputs/ticks_trades.csv
    profit factor, win rate, max drawdown, trade count, largest single winner
    as a share of net profit, same-bar trade count, break-even slippage per
    side, unfilled orders.

ZERO-RESULT CONTINGENCY: zero ticks in range -> one range swap
(--fallback-start). Still zero, or zero signals, or zero trades with
signals present -> instrument the funnel and name the defect.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_adapter as ea  # noqa: E402

BAR_MS = 30 * 60 * 1000
CHUNK = 2_000_000


def log(m):
    print(f"[ticks] {m}", flush=True)


# ------------------------------------------------------------ load ticks --
def load_ticks(path: Path, start_ms: int, end_ms: int):
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        import pyarrow.compute as pc
        t = pq.read_table(str(path), columns=["time_msc", "bid", "ask"],
                          filters=[("time_msc", ">=", start_ms), ("time_msc", "<=", end_ms)])
        return (t["time_msc"].to_numpy().astype(np.int64), t["bid"].to_numpy().astype(np.float64),
                t["ask"].to_numpy().astype(np.float64))
    df = pd.read_csv(path, usecols=["time_msc", "bid", "ask"])
    df = df[(df.time_msc >= start_ms) & (df.time_msc <= end_ms)]
    return df.time_msc.values.astype(np.int64), df.bid.values.astype(np.float64), df.ask.values.astype(np.float64)


# ------------------------------------------------------------- replay -----
class Replay:
    def __init__(self, t, bid, ask, spec, params, costs):
        self.t, self.bid, self.ask = t, bid, ask
        self.cs = float(spec["contract_size"])
        self.tick_size = float(spec["tick_size"])
        self.p = params
        self.c = costs
        self.trades = []
        self.unfilled = []
        self.pos = None
        self.cursor = 0  # first tick index not yet scanned for trail/SL
        self.funnel = {"signals_fired": 0, "orders_attempted": 0, "orders_filled": 0, "orders_unfilled": 0,
                       "trail_exits": 0, "sl_exits": 0, "signal_exits": 0, "first_blocking_condition": None}

    # distances in price units, following Pine toTicks() then back to price
    def _dist(self, d, ref):
        u = self.p["trail_unit"]
        if u == "ticks":
            return d * self.tick_size
        if u == "percent":
            return ref * d / 100.0
        return d  # price

    def _fill(self, side, trigger, from_ms, until_ms):
        """First tick in [from_ms, until_ms) with ask>=trigger (buy) / bid<=trigger (sell)."""
        a = int(np.searchsorted(self.t, from_ms, side="left"))
        b = int(np.searchsorted(self.t, until_ms, side="left"))
        if a >= b:
            return None
        px = self.ask[a:b] if side == "buy" else self.bid[a:b]
        hit = (px >= trigger) if side == "buy" else (px <= trigger)
        if not hit.any():
            return None
        k = a + int(np.argmax(hit))
        return k

    def _scan_exit(self, until_ms):
        """Advance the trail/SL scan for the open position up to until_ms. Returns tick index of exit or None."""
        pos = self.pos
        if pos is None or (not self.p["trail_on"] and not self.p["sl_on"]):
            self.cursor = int(np.searchsorted(self.t, until_ms, side="left"))
            return None
        end = int(np.searchsorted(self.t, until_ms, side="left"))
        long = pos["side"] == "long"
        entry = pos["entry_px_raw"]
        act = self._dist(self.p["trail_act"], entry)
        off = max(self._dist(self.p["trail_off"], entry), self.tick_size)
        sl = max(self._dist(self.p["sl_dist"], entry), self.tick_size) if self.p["sl_on"] else None
        i = self.cursor
        while i < end:
            j = min(i + CHUNK, end)
            px = self.bid[i:j] if long else self.ask[i:j]
            if long:
                run = np.maximum.accumulate(np.concatenate(([pos["best"]], px)))[1:]
                armed = pos["armed_flag"] | (run >= entry + act) if self.p["trail_on"] else np.zeros(len(px), bool)
                stop = run - off
                hit = armed & (px <= stop)
                if sl is not None:
                    hit |= px <= entry - sl
            else:
                run = np.minimum.accumulate(np.concatenate(([pos["best"]], px)))[1:]
                armed = pos["armed_flag"] | (run <= entry - act) if self.p["trail_on"] else np.zeros(len(px), bool)
                stop = run + off
                hit = armed & (px >= stop)
                if sl is not None:
                    hit |= px >= entry + sl
            if hit.any():
                k = int(np.argmax(hit))
                pos["best"] = float(run[k])
                reason = "SL" if (sl is not None and ((px[k] <= entry - sl) if long else (px[k] >= entry + sl)) and not (armed[k] and ((px[k] <= stop[k]) if long else (px[k] >= stop[k])))) else "trail TP"
                self.cursor = i + k + 1
                return i + k, reason
            pos["best"] = float(run[-1])
            pos["armed_flag"] = bool(armed[-1]) if self.p["trail_on"] else False
            i = j
        self.cursor = end
        return None

    def _open(self, side, k, bar_time_ms):
        raw = self.ask[k] if side == "long" else self.bid[k]
        slip = self.c["slippage"]
        eff = raw + slip if side == "long" else raw - slip
        self.pos = {"side": side, "entry_idx": k, "entry_ms": int(self.t[k]), "entry_px_raw": float(raw),
                    "entry_px_eff": float(eff), "best": float(raw), "armed_flag": False, "signal_bar_ms": bar_time_ms}
        self.cursor = k + 1

    def _close(self, k, reason):
        pos = self.pos
        long = pos["side"] == "long"
        raw = self.bid[k] if long else self.ask[k]
        slip = self.c["slippage"]
        eff = raw - slip if long else raw + slip
        qty, cs = self.c["qty"], self.cs
        d = 1.0 if long else -1.0
        gross_no_slip = (raw - pos["entry_px_raw"]) * d * qty * cs
        comm = self.c["commission_pct"] / 100.0 * qty * cs * (pos["entry_px_raw"] + raw)
        net = (eff - pos["entry_px_eff"]) * d * qty * cs - comm
        self.trades.append({
            "side": pos["side"], "entry_time": pd.Timestamp(pos["entry_ms"], unit="ms"), "exit_time": pd.Timestamp(int(self.t[k]), unit="ms"),
            "entry_px": pos["entry_px_raw"], "exit_px": float(raw), "entry_px_eff": pos["entry_px_eff"], "exit_px_eff": float(eff),
            "qty": qty, "notional": qty * cs * pos["entry_px_raw"], "margin": qty * cs * pos["entry_px_raw"] / self.c["leverage"],
            "gross_no_slip": gross_no_slip, "commission": comm, "slippage_cost": 2 * slip * qty * cs, "net": net, "reason": reason,
            "same_bar": (pos["entry_ms"] // BAR_MS) == (int(self.t[k]) // BAR_MS),
        })
        self.pos = None
        self.cursor = k + 1

    def run(self, bars: pd.DataFrame, sig: pd.DataFrame):
        p = self.p
        allow_long = p["trade_dir"] != "Short only (sell only)"
        allow_short = p["trade_dir"] != "Long only (buy only)"
        bar_ms = bars["time"].values.astype("datetime64[ms]").astype(np.int64)
        close = bars["close"].values
        low, high = bars["low"].values, bars["high"].values
        eL, eS = sig["enter_long"].values, sig["enter_short"].values
        xL, xS = sig["exit_long"].values, sig["exit_short"].values
        n = len(bars)
        t_end = int(self.t[-1]) + 1
        for i in range(n):
            c_ms = int(bar_ms[i]) + BAR_MS
            until = int(bar_ms[i + 1]) + BAR_MS if i + 1 < n else t_end
            # 1. price exits on ticks up to this bar's close
            r = self._scan_exit(c_ms)
            if r is not None:
                k, reason = r
                self._close(k, reason)
                self.funnel["trail_exits" if reason == "trail TP" else "sl_exits"] += 1
            # 2. the bar-close decision, mirrored from the Pine strategy block
            long_sig, short_sig = bool(eL[i]), bool(eS[i])
            if long_sig or short_sig or xL[i] or xS[i]:
                self.funnel["signals_fired"] += 1
            exit_l = p["exit_on_end"] and bool(xL[i])
            exit_s = p["exit_on_end"] and bool(xS[i])
            go_long = long_sig and allow_long
            go_short = short_sig and allow_short
            opp_l = p["opp_closes"] and short_sig and not allow_short
            opp_s = p["opp_closes"] and long_sig and not allow_long
            has_long = self.pos is not None and self.pos["side"] == "long"
            has_short = self.pos is not None and self.pos["side"] == "short"
            close_l = has_long and not go_long and not go_short and (exit_l or opp_l)
            close_s = has_short and not go_short and not go_long and (exit_s or opp_s)
            trig_buy = close[i] if self.trigger == "close" else low[i]
            trig_sell = close[i] if self.trigger == "close" else high[i]

            if close_l or close_s:
                side = "sell" if close_l else "buy"
                self.funnel["orders_attempted"] += 1
                k = self._fill(side, trig_sell if close_l else trig_buy, c_ms, until)
                if k is None:
                    self._unfilled(i, bars, side, "close", trig_sell if close_l else trig_buy)
                else:
                    r = self._scan_exit(int(self.t[k]))  # trail may fire before the close order fills
                    if r is not None:
                        self._close(r[0], r[1]); self.funnel["trail_exits" if r[1] == "trail TP" else "sl_exits"] += 1
                    else:
                        self._close(k, "exit once" if (exit_l or exit_s) else "opp ENTER"); self.funnel["signal_exits"] += 1
            if go_long and not has_long or go_short and not has_short:
                side = "buy" if go_long else "sell"
                self.funnel["orders_attempted"] += 1
                k = self._fill(side, trig_buy if go_long else trig_sell, c_ms, until)
                if k is None:
                    self._unfilled(i, bars, side, "entry", trig_buy if go_long else trig_sell)
                    continue
                if self.pos is not None:  # reversal: close the other side on the same tick
                    r = self._scan_exit(int(self.t[k]))
                    if r is not None:
                        self._close(r[0], r[1]); self.funnel["trail_exits" if r[1] == "trail TP" else "sl_exits"] += 1
                    else:
                        self._close(k, "reverse"); self.funnel["signal_exits"] += 1
                self.funnel["orders_filled"] += 1
                self._open("long" if go_long else "short", k, int(bar_ms[i]))
        # end of data: close any open position on the last tick, flagged
        if self.pos is not None:
            self._close(len(self.t) - 1, "end of data")
        return pd.DataFrame(self.trades)

    def _unfilled(self, i, bars, side, kind, trigger):
        self.funnel["orders_unfilled"] += 1
        self.unfilled.append({"bar_time": str(bars["time"].iloc[i]), "side": side, "kind": kind, "trigger": float(trigger)})


# ------------------------------------------------------------ metrics ----
def metrics(tr: pd.DataFrame, costs: dict, cs: float) -> dict:
    if len(tr) == 0:
        return {"trade_count": 0}
    net = tr["net"]
    wins, losses = net[net > 0], net[net <= 0]
    eq = net.cumsum()
    peak = eq.cummax()
    dd = eq - peak
    dd_pct = (dd / (costs["capital"] + peak)).min()
    total = float(net.sum())
    qty = costs["qty"]
    n = len(tr)
    be_slip = costs["slippage"] + total / (2.0 * n * qty * cs)  # USD of price per side at which net == 0
    return {
        "trade_count": int(n),
        "net_profit": total,
        "gross_profit": float(wins.sum()), "gross_loss": float(-losses.sum()),
        "profit_factor": (float(wins.sum() / -losses.sum()) if losses.sum() < 0 else float("inf")),
        "win_rate": float((net > 0).mean()),
        "max_drawdown_usd": float(-dd.min()),
        "max_drawdown_pct_of_equity": float(-dd_pct),
        "largest_winner": float(net.max()),
        "largest_winner_share_of_net": (float(net.max() / total) if total > 0 else None),
        "same_bar_trades": int(tr["same_bar"].sum()),
        "break_even_slippage_usd_per_side": float(be_slip),
        "break_even_slippage_flat_usd_per_side": float(be_slip * qty * cs),
        "total_commission": float(tr["commission"].sum()),
        "total_slippage_cost": float(tr["slippage_cost"].sum()),
        "margin_exceeds_equity_count": int((tr["margin"] > costs["capital"] + eq.shift(1).fillna(0)).sum()),
        "exit_reasons": tr["reason"].value_counts().to_dict(),
        "end_of_data_close": int((tr["reason"] == "end of data").sum()),
    }


# --------------------------------------------------------------- main ----
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    ap.add_argument("--symbol", default="BTCUSD")
    ap.add_argument("--commission-pct", type=float, default=0.02)
    ap.add_argument("--slippage-usd", type=float, default=5.0)
    ap.add_argument("--leverage", type=float, default=10.0)
    ap.add_argument("--qty", type=float, default=None, help="fixed contracts; default = engine qty constant else 1.0")
    ap.add_argument("--capital", type=float, default=10000.0)
    ap.add_argument("--trigger", choices=["close", "extreme"], default="close")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--fallback-start", default="2024-01-01", help="the ONE allowed range swap")
    a = ap.parse_args()

    project = Path(a.project)
    data = project / "data" / "mt5"
    out = project / "outputs"
    out.mkdir(exist_ok=True)
    spec = json.loads((data / f"{a.symbol}_spec.json").read_text())
    bars = pd.read_csv(data / f"{a.symbol}_M30.csv", parse_dates=["time"]).sort_values("time").reset_index(drop=True)
    tick_path = data / f"{a.symbol}_ticks.parquet"
    if not tick_path.exists():
        tick_path = tick_path.with_suffix(".csv")
    if not tick_path.exists():
        raise SystemExit("DEFECT BLOCKED_NO_TICKS: no tick file in data/mt5, run mt5_data.py")

    params = ea.get_strategy_params()
    eng_costs = ea.get_engine_costs()
    qty = a.qty if a.qty is not None else (float(eng_costs["qty"]) if isinstance(eng_costs.get("qty"), (int, float)) else 1.0)
    costs = {"commission_pct": a.commission_pct, "slippage": a.slippage_usd, "leverage": a.leverage, "qty": qty, "capital": a.capital,
             "qty_source": "--qty" if a.qty is not None else eng_costs["_source"].get("qty")}
    log(f"params: {params}")
    log(f"costs : {costs}")

    report = {"spec_path": str(data / f"{a.symbol}_spec.json"), "params": params, "costs": costs, "trigger": a.trigger,
              "defects": [], "range_swaps": 0, "funnel": None}

    start = pd.Timestamp(a.start) if a.start else bars.time.iloc[0]
    end = pd.Timestamp(a.end) if a.end else bars.time.iloc[-1] + pd.Timedelta(minutes=30)

    def run_range(s, e):
        b = bars[(bars.time >= s - pd.Timedelta(days=120)) & (bars.time < e)].reset_index(drop=True)  # warm-up kept for the engine
        sig = ea.get_signals(b)
        keep = b.time >= s
        b, sig = b[keep].reset_index(drop=True), sig[keep.values].reset_index(drop=True)
        t, bid, ask = load_ticks(tick_path, int(s.value // 10**6), int(e.value // 10**6))
        return b, sig, t, bid, ask

    b, sig, t, bid, ask = run_range(start, end)
    n_sig = int(sig[["enter_long", "enter_short", "exit_long", "exit_short"]].values.sum())
    log(f"bars {len(b):,}  signals {n_sig}  ticks {len(t):,}")
    if len(t) == 0 or n_sig == 0:
        log("ZERO ticks or signals. One range swap.")
        report["range_swaps"] = 1
        start = pd.Timestamp(a.fallback_start)
        b, sig, t, bid, ask = run_range(start, end)
        n_sig = int(sig[["enter_long", "enter_short", "exit_long", "exit_short"]].values.sum())
        log(f"bars {len(b):,}  signals {n_sig}  ticks {len(t):,}")
    report["range_used"] = {"start": str(start), "end": str(end)}
    report["tick_count"] = int(len(t))
    report["signal_count"] = n_sig
    if len(t) == 0:
        report["defects"].append({"name": "BLOCKED_NO_TICKS", "funnel": {"ticks_in_range": 0, "first_blocking_condition": f"no ticks between {start} and {end} in {tick_path.name}"}})
    if n_sig == 0:
        report["defects"].append({"name": "BLOCKED_NO_SIGNALS", "funnel": {"bars": int(len(b)), "first_blocking_condition": "engine produced no enter/exit flags (see engine_adapter --probe)"}})
    if report["defects"]:
        _write(out, report, None)
        return 1

    rp = Replay(t, bid, ask, spec, params, costs)
    rp.trigger = a.trigger
    tr = rp.run(b, sig)
    report["funnel"] = rp.funnel
    report["unfilled_first10"] = rp.unfilled[:10]
    if len(tr) == 0:
        f = dict(rp.funnel)
        if f["orders_attempted"] == 0:
            f["first_blocking_condition"] = f"signals fired ({f['signals_fired']}) but no order attempted: trade_dir={params['trade_dir']} blocks the side, or every bar had long+short together"
        elif f["orders_filled"] == 0:
            f["first_blocking_condition"] = f"orders attempted ({f['orders_attempted']}) but none filled within the next bar; first unfilled = {rp.unfilled[0] if rp.unfilled else None}"
        else:
            f["first_blocking_condition"] = "orders filled but no trade closed"
        report["defects"].append({"name": "BLOCKED_NO_TRADES", "funnel": f})
    else:
        tr.to_csv(out / "ticks_trades.csv", index=False)
        report["metrics"] = metrics(tr, costs, float(spec["contract_size"]))
        report["same_bar_trades_first20"] = tr[tr["same_bar"]].head(20)[["side", "entry_time", "exit_time", "net", "reason"]].astype(str).to_dict("records")
    _write(out, report, tr)
    return 0 if not report["defects"] else 1


def _write(out: Path, r: dict, tr):
    (out / "step3_report.json").write_text(json.dumps(r, indent=2, default=str))
    L = ["# STEP 3 - tick replay", ""]
    L.append(f"range {r.get('range_used')}  |  range swaps {r['range_swaps']}  |  ticks {r.get('tick_count', 0):,}  |  signals {r.get('signal_count', 0)}  |  trigger {r['trigger']}")
    L.append(f"costs: commission {r['costs']['commission_pct']}% per side, slippage {r['costs']['slippage']} USD per side, leverage {r['costs']['leverage']}, qty {r['costs']['qty']} contracts (source: {r['costs']['qty_source']}), capital {r['costs']['capital']}")
    L.append(f"trail: on={r['params']['trail_on']} unit={r['params']['trail_unit']} act={r['params']['trail_act']} off={r['params']['trail_off']}  SL on={r['params']['sl_on']} dist={r['params']['sl_dist']}")
    L.append("")
    m = r.get("metrics")
    if m:
        L.append("| metric | value |")
        L.append("|---|---|")
        L.append(f"| profit factor | {m['profit_factor']:.3f} |")
        L.append(f"| win rate | {m['win_rate'] * 100:.1f}% |")
        L.append(f"| max drawdown | {m['max_drawdown_usd']:.2f} USD ({m['max_drawdown_pct_of_equity'] * 100:.1f}% of equity) |")
        L.append(f"| trade count | {m['trade_count']} |")
        L.append(f"| net profit | {m['net_profit']:.2f} USD |")
        lw = m['largest_winner_share_of_net']
        L.append(f"| largest winner / net profit | {('%.1f%%' % (lw * 100)) if lw is not None else 'n/a (net <= 0)'} ({m['largest_winner']:.2f} USD) |")
        L.append(f"| same-bar trades (enter and exit inside one M30 bar) | {m['same_bar_trades']} |")
        L.append(f"| break-even slippage per side | {m['break_even_slippage_usd_per_side']:.2f} USD of price ({m['break_even_slippage_flat_usd_per_side']:.2f} USD flat) |")
        L.append(f"| commission paid / slippage paid | {m['total_commission']:.2f} / {m['total_slippage_cost']:.2f} USD |")
        L.append(f"| unfilled orders | {r['funnel']['orders_unfilled']} |")
        L.append(f"| margin > equity events | {m['margin_exceeds_equity_count']} |")
        L.append(f"| exit reasons | {m['exit_reasons']} |")
        if m["end_of_data_close"]:
            L.append(f"| forced close at end of data | {m['end_of_data_close']} |")
        L.append("")
        if r.get("same_bar_trades_first20"):
            L.append("## Same-bar trades (first 20, flagged)")
            for x in r["same_bar_trades_first20"]:
                L.append(f"- {x['side']} {x['entry_time']} -> {x['exit_time']} net {x['net']} ({x['reason']})")
    if r.get("funnel"):
        L.append("")
        L.append(f"funnel: `{json.dumps(r['funnel'])}`")
    if r["defects"]:
        L.append("")
        L.append("## DEFECTS")
        for d in r["defects"]:
            L.append(f"- **{d['name']}**: first blocking condition = {d['funnel'].get('first_blocking_condition')}")
            L.append(f"  - funnel: `{json.dumps(d['funnel'], default=str)}`")
    md = "\n".join(L) + "\n"
    (out / "step3_report.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    sys.exit(main())
