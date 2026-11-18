#!/usr/bin/env python3
"""
The 2026 results of the tick replay, as the data files of the "Loma 2026 Results" page (a dashboard artifact).

Input: the replay outputs of tick_replay.py (run <dir> pre|main ea all <k> 2) for gold and BTC, read the same way as
make_best_trailing.py (every EA pick, every cost model, both spans; nothing missing or doubled), the re-calibration's
15 earlier trailing results (results/recal/<sym>_successful_trailing.json) and the choice of best_by_timeframe.json.
Months: 16 May - 13 Nov 2026 (server time), the months the setups never saw; the trailing of the best-per-timeframe
sets was chosen on them. Figures at VT costs ("vt"), the replay's tick engine, unless a column says otherwise.

Output (research/results/tick/page2026/), each a JSON {rows, meta} with this script's own text in meta:
  cells2026.json    every symbol x timeframe x EA trailing system with setups: trades, profit factor, net R, win rate,
                    average R, largest drawdown in R, months with a gain, stressed PF, the one-minute engine's PF,
                    Dukascopy's own spreads (gold), the earlier periods, flags (eligible, reached, chosen, t15)
  monthly2026.json  per combination shown on the page (reached or chosen) and month: trades, net R, profit factor
  equity2026.json   per combination shown and day: the running total of R at the end of the day (exits that day), from
                    0 on 15 May 2026, the eve of the period
Usage (repository root): python3 research/make_2026_page_data.py <gold_replay_dir> <btc_replay_dir>
"""
import json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "research"))
import make_best_trailing as BT                     # load_replay, pf, SYSTEM, SYMS

OUT = os.path.join(ROOT, "research", "results", "tick", "page2026")
START = np.datetime64("2026-05-16T03:00", "ms").astype(np.int64)         # hump_tf_recal.IS_END, server time
MONTHS = [("2026-05", "May (from 16th)"), ("2026-06", "Jun"), ("2026-07", "Jul"), ("2026-08", "Aug"), ("2026-09", "Sep"),
          ("2026-10", "Oct"), ("2026-11", "Nov (to 13th)")]
SYM_SHORT = {"XAUUSD": "Gold", "BTCUSD": "BTC"}
TF_ORDER = {tf: i for i, tf in enumerate(BT.TFS)}


def num(x, nd=6):
    """JSON-safe number: None for NaN and for an infinite profit factor (no losing trade)."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), nd)


def max_drawdown(t):
    """Deepest fall of the running total of R from its high; trades closing in the same millisecond count as one step."""
    r_by_exit = t.groupby("exit_ms").r.sum().values
    eq = np.concatenate([[0.0], np.cumsum(r_by_exit)])
    return float((np.maximum.accumulate(eq) - eq).max())


def main(gold_dir, btc_dir):
    os.makedirs(OUT, exist_ok=True)
    best = json.load(open(os.path.join(ROOT, "research", "results", "tick", "best_by_timeframe.json")))["timeframes"]
    chosen = {(b["symbol"], b["tf"], b["chosen"]["trailing"]) for b in best if b["chosen"]}
    cells_rows, monthly_rows, equity_rows = [], [], []
    for sym, rdir in (("XAUUSD", gold_dir), ("BTCUSD", btc_dir)):
        cells, tr = BT.load_replay(rdir, sym)
        t15 = {(c["timeframe"], c["trailing"]) for c in
               json.load(open(os.path.join(ROOT, "research", "results", "recal", f"{sym.lower()}_successful_trailing.json")))["combinations"]}
        for c in cells:
            if not c["picked"]:
                continue
            keys = [q["key"] for q in c["picks"]]
            g = tr[tr.key.isin(keys) & (tr.period == "unseen")]
            t = g[(g.model == "vt") & (g.engine == "tick")].sort_values(["exit_ms", "entry_ms"], kind="mergesort")
            r = t.r.values
            assert len(r) == 0 or t.entry_ms.min() >= START
            s = BT.stats(tr, keys, "vt_stress", "unseen")
            y = BT.stats(tr, keys, "vt", "unseen", "1m")
            mon = pd.to_datetime(t.entry_ms, unit="ms").dt.strftime("%Y-%m")
            by_m = {m: r[(mon == m).values] for m, _ in MONTHS}
            combo = f"{sym}_{c['tf']}_{c['kind']}"
            label = f"{SYM_SHORT[sym]} {c['tf']} {BT.SYSTEM[c['kind']]}"
            pfv = BT.pf(r)
            row = dict(combo=combo, label=label, symbol=sym, tf=c["tf"], tf_order=TF_ORDER[c["tf"]], trailing=c["kind"],
                       trailing_name=BT.SYSTEM[c["kind"]], trail_mode=BT.MP.TRAIL_MODE[c["kind"]], setups=len(keys),
                       trades=int(len(r)), pf=num(pfv), no_losses=bool(np.isinf(pfv)), net_r=num(r.sum(), 4),
                       win_pct=num(100 * (r > 0).mean(), 4) if len(r) else None, avg_r=num(r.mean(), 4) if len(r) else None,
                       max_dd_r=num(max_drawdown(t), 4) if len(r) else None,
                       months_up=int(sum(v.sum() > 0 for v in by_m.values())), months_traded=int(sum(len(v) > 0 for v in by_m.values())),
                       stress_pf=num(s["pf"]), stress_trades=s["n"], one_minute_pf=num(y["pf"]), one_minute_trades=y["n"])
            if sym == "XAUUSD":
                d = BT.stats(tr, keys, "duk_raw", "unseen")
                row.update(dukascopy_pf=num(d["pf"]), dukascopy_trades=d["n"])
            else:
                row.update(dukascopy_pf=None, dukascopy_trades=None)
            for p in ("earlier", "2024", "2023"):
                e = BT.stats(tr, keys, "vt", p) if p in BT.SYMS[sym]["earlier"] else None
                col = BT.COL[p]
                row[f"before_{col}_pf"] = num(e["pf"]) if e else None
                row[f"before_{col}_trades"] = e["n"] if e else None
            cal = BT.stats(tr, keys, "vt", "calibration")
            row.update(picked_on_pf=num(cal["pf"]), picked_on_trades=cal["n"],
                       eligible=bool(len(r) >= BT.MIN_N), reached=bool(len(r) >= BT.MIN_N and (np.isinf(pfv) or pfv >= 1.3)),
                       chosen=(sym, c["tf"], c["kind"]) in chosen, t15=(c["tf"], c["kind"]) in t15)
            cells_rows.append(row)
            if row["reached"] or row["chosen"]:
                for m, mlab in MONTHS:
                    v = by_m[m]
                    monthly_rows.append(dict(combo=combo, label=label, month=m, month_label=mlab, trades=int(len(v)),
                                             net_r=num(v.sum(), 4), pf=num(BT.pf(v)) if len(v) else None))
                day = pd.to_datetime(t.exit_ms, unit="ms").dt.strftime("%Y-%m-%d").values
                cum = np.cumsum(r)
                equity_rows.append(dict(combo=combo, label=label, date="2026-05-15", cum_r=0.0, trades=0))      # the eve of the period
                for dd in dict.fromkeys(day):
                    i = np.where(day == dd)[0][-1]
                    equity_rows.append(dict(combo=combo, label=label, date=str(dd), cum_r=num(cum[i], 4), trades=int(i + 1)))
    src = open(os.path.abspath(__file__)).read()
    meta = [dict(label="make_2026_page_data.py", value=src, type="code", lang="python"),
            dict(label="Input", value="Tick replay of the re-calibration's picks (research/tick_replay.py run ... ea all), "
                                      "gold: Dukascopy ticks, BTC: Binance one-second prices; research/results/tick/best_by_timeframe.json; "
                                      "research/results/recal/<sym>_successful_trailing.json"),
            dict(label="Costs", value="vt: gold Dukascopy mid with VT's 0.15 spread scaled by Dukascopy's own spread, 0.60 USD commission "
                                      "per ounce; BTC mid with a 10 USD spread. vt_stress: one minute late, slippage (gold 0.10, BTC 3 USD), "
                                      "commission (gold 0.67, BTC 2 USD). duk_raw: Dukascopy's own bid and ask, 0.60 USD."),
            dict(label="Months", value="16 May - 13 Nov 2026, server time (New York + 7 h), by entry time; equity by exit day")]
    for name, rows in (("cells2026", cells_rows), ("monthly2026", monthly_rows), ("equity2026", equity_rows)):
        json.dump(dict(rows=rows, meta=meta), open(os.path.join(OUT, f"{name}.json"), "w"), separators=(",", ":"))
        print(f"{name}: {len(rows)} rows, {os.path.getsize(os.path.join(OUT, name + '.json')):,} bytes")
    d = pd.DataFrame(cells_rows)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(d[d.reached | d.chosen].sort_values("pf", ascending=False)[["label", "setups", "trades", "pf", "net_r", "win_pct", "max_dd_r",
                                                                      "months_up", "stress_pf", "reached", "chosen", "t15"]].to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
