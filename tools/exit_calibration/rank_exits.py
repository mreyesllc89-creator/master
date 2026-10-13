#!/usr/bin/env python3
"""Rank XPW ShapeMap v8 exit settings from MT5 Strategy Tester optimization exports.

Workflow
  1. In MT5 Strategy Tester run an optimization of the EA with a FIXED lot size
     over the exit inputs only (SL ATR multiple, time stop, trailing/TP).
  2. Right-click the Optimization Results tab -> Export to XML (Excel 2003 XML).
     Export the in-sample run and, if you ran one, the forward/out-of-sample run.
  3. python3 rank_exits.py --symbol XAUUSD --lots 0.10 --commission 0.6 \
         --exit-params "SlAtr,TimeStop,TrailOffset" in_sample.xml --oos forward.xml

Commission handling
  VT Markets quotes commission per lot. --commission is the charge for ONE lot
  on ONE side; --sides 2 (default) turns it into a round-turn cost. Pass
  --sides 1 if the 0.6 you were quoted is already the round-turn charge.
  If the tester already applied broker commission (the symbol specification in
  MT5 shows a non-zero commission and the Deals tab shows it), pass
  --tester-has-commission so it is not charged twice.

Scoring
  Every pass gets: round-turn cost per trade, net profit after cost, net
  expectancy per trade, and the edge ratio (net expectancy / round-turn cost).
  A pass is ranked by a robust score that uses the average of its
  neighbourhood in exit-parameter space (so a lonely spike does not win), and
  requires a minimum trade count. The out-of-sample file, when given, is
  matched by pass number and shown next to the in-sample numbers.
"""
import argparse
import csv
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Contract presets. Verify in MT5: right-click symbol -> Specification.
PRESETS = {
    # contract size, tick size, typical raw-account spread in PRICE units
    "XAUUSD": {"contract": 100.0, "tick": 0.01, "spread": 0.15},
    "BTCUSD": {"contract": 1.0, "tick": 0.01, "spread": 25.0},
}

MT5_METRIC_COLUMNS = {
    "pass": ["Pass"],
    "profit": ["Profit"],
    "payoff": ["Expected Payoff"],
    "pf": ["Profit Factor"],
    "rf": ["Recovery Factor"],
    "sharpe": ["Sharpe Ratio"],
    "custom": ["Custom", "Result"],
    "dd": ["Equity DD %", "Drawdown %", "Equity DD"],
    "trades": ["Trades"],
}


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def read_xml(path):
    """Read an MT5 'Export to XML' optimization report (Excel 2003 XML)."""
    rows = []
    root = ET.parse(path).getroot()
    for row in root.iter():
        if _local(row.tag) != "Row":
            continue
        cells = []
        for cell in row:
            if _local(cell.tag) != "Cell":
                continue
            data = next((d for d in cell if _local(d.tag) == "Data"), None)
            cells.append("" if data is None or data.text is None else data.text.strip())
        if cells:
            rows.append(cells)
    if not rows:
        raise SystemExit(f"{path}: no rows found; is this an MT5 Export-to-XML file?")
    header, body = rows[0], rows[1:]
    return [dict(zip(header, r)) for r in body if any(r)]


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return list(csv.DictReader(fh, dialect=dialect))


def read_report(path):
    p = Path(path)
    return read_xml(p) if p.suffix.lower() == ".xml" else read_csv(p)


def num(value, default=math.nan):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def pick(row, names):
    for n in names:
        if n in row:
            return row[n]
    return None


def parse_passes(rows, exit_params):
    passes = []
    for r in rows:
        p = {k: num(pick(r, v)) for k, v in MT5_METRIC_COLUMNS.items()}
        if math.isnan(p["profit"]) or math.isnan(p["trades"]):
            continue
        p["pass"] = int(p["pass"]) if not math.isnan(p["pass"]) else len(passes)
        p["params"] = {}
        for name in exit_params:
            if name not in r:
                raise SystemExit(f"exit parameter column '{name}' not in report; columns: {', '.join(r.keys())}")
            p["params"][name] = num(r[name])
        p["other"] = {k: v for k, v in r.items() if k not in exit_params and k not in sum(MT5_METRIC_COLUMNS.values(), [])}
        passes.append(p)
    return passes


def cost_model(symbol, lots, commission, sides, spread, tester_has_commission):
    spec = PRESETS[symbol]
    spread_price = spec["spread"] if spread is None else spread
    spread_cost = spread_price * spec["contract"] * lots          # paid once per round turn
    comm_cost = 0.0 if tester_has_commission else commission * sides * lots
    return {
        "symbol": symbol,
        "lots": lots,
        "spread_price": spread_price,
        "spread_cost": spread_cost,
        "commission_cost": comm_cost,
        "round_turn": spread_cost + comm_cost,
        "tick_value": spec["tick"] * spec["contract"] * lots,
        "tick": spec["tick"],
    }


def score_passes(passes, cost, min_trades):
    for p in passes:
        n = p["trades"]
        charge = (cost["commission_cost"]) * n          # tester already paid the spread
        p["net_profit"] = p["profit"] - charge
        p["net_expectancy"] = p["net_profit"] / n if n else math.nan
        p["edge_ratio"] = p["net_expectancy"] / cost["round_turn"] if cost["round_turn"] else math.nan
        dd = p["dd"] if not math.isnan(p["dd"]) else 0.0
        p["raw_score"] = (p["net_expectancy"] * math.sqrt(n)) / (1.0 + dd / 10.0) if n >= min_trades else -math.inf
    # Neighbourhood smoothing: for each exit parameter, the adjacent grid value
    # on either side counts as a neighbour. Score = mean of self + neighbours.
    grids = {}
    for name in passes[0]["params"] if passes else []:
        grids[name] = sorted({p["params"][name] for p in passes})
    index = {tuple(p["params"][k] for k in grids): p for p in passes}

    def neighbours(p):
        out = []
        keys = list(grids)
        for i, k in enumerate(keys):
            g = grids[k]
            pos = g.index(p["params"][k])
            for step in (-1, 1):
                j = pos + step
                if 0 <= j < len(g):
                    key = tuple(p["params"][kk] if kk != k else g[j] for kk in keys)
                    if key in index:
                        out.append(index[key])
        return out

    for p in passes:
        nb = [q["raw_score"] for q in neighbours(p) if q["raw_score"] > -math.inf]
        own = p["raw_score"]
        p["robust_score"] = own if own == -math.inf else (own + sum(nb)) / (1 + len(nb))
        p["neighbours"] = len(nb)
    return passes


def fmt(v, nd=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "-"
    return f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", help="in-sample MT5 optimization export (.xml or .csv)")
    ap.add_argument("--oos", help="out-of-sample / forward export to show next to each pass")
    ap.add_argument("--symbol", required=True, choices=sorted(PRESETS))
    ap.add_argument("--lots", type=float, required=True, help="fixed lot size used in the optimization")
    ap.add_argument("--commission", type=float, default=0.6, help="commission per lot per side (default 0.6)")
    ap.add_argument("--sides", type=int, default=2, choices=[1, 2], help="2 = charged on open and close (default); 1 = quote is already round turn")
    ap.add_argument("--spread", type=float, help="override typical spread in price units (XAUUSD 0.15 = 15 cents)")
    ap.add_argument("--tester-has-commission", action="store_true", help="tester deals already include broker commission")
    ap.add_argument("--exit-params", required=True, help="comma-separated input column names that were optimized")
    ap.add_argument("--min-trades", type=int, default=100)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--csv-out", help="write the full scored table to this CSV")
    a = ap.parse_args()

    exit_params = [s.strip() for s in a.exit_params.split(",") if s.strip()]
    cost = cost_model(a.symbol, a.lots, a.commission, a.sides, a.spread, a.tester_has_commission)
    passes = score_passes(parse_passes(read_report(a.report), exit_params), cost, a.min_trades)
    if not passes:
        raise SystemExit("no passes with Profit and Trades columns found")
    oos = {}
    if a.oos:
        for p in parse_passes(read_report(a.oos), exit_params):
            oos[tuple(p["params"][k] for k in exit_params)] = p

    print(f"Cost model {cost['symbol']} @ {cost['lots']} lot: spread {cost['spread_price']} price units = "
          f"{cost['spread_cost']:.2f}, commission {cost['commission_cost']:.2f} per round turn "
          f"(0 means the tester already charged it), total round turn {cost['round_turn']:.2f}, "
          f"1 tick = {cost['tick_value']:.4f}")
    print(f"Passes: {len(passes)}, exit params: {', '.join(exit_params)}, min trades {a.min_trades}\n")

    ranked = sorted(passes, key=lambda p: p["robust_score"], reverse=True)
    head = ["rank", "pass"] + exit_params + ["trades", "net_profit", "net_exp", "edge", "PF", "DD%", "robust"]
    if oos:
        head += ["oos_trades", "oos_net", "oos_edge"]
    print("\t".join(head))
    for i, p in enumerate(ranked[: a.top], 1):
        row = [str(i), str(p["pass"])] + [fmt(p["params"][k], 4).rstrip("0").rstrip(".") for k in exit_params]
        row += [str(int(p["trades"])), fmt(p["net_profit"]), fmt(p["net_expectancy"]), fmt(p["edge_ratio"]),
                fmt(p["pf"]), fmt(p["dd"]), fmt(p["robust_score"])]
        if oos:
            q = oos.get(tuple(p["params"][k] for k in exit_params))
            if q:
                n = q["trades"]
                net = q["profit"] - cost["commission_cost"] * n
                edge = (net / n / cost["round_turn"]) if n and cost["round_turn"] else math.nan
                row += [str(int(n)), fmt(net), fmt(edge)]
            else:
                row += ["-", "-", "-"]
        print("\t".join(row))

    best = ranked[0]
    print("\nRecommended exit set (highest robust score):")
    for k in exit_params:
        print(f"  {k} = {fmt(best['params'][k], 4).rstrip('0').rstrip('.')}")
    print(f"  net expectancy {fmt(best['net_expectancy'])} per trade = {fmt(best['edge_ratio'])} x round-turn cost "
          f"over {int(best['trades'])} trades; neighbours averaged: {best['neighbours']}")
    if best["edge_ratio"] < 1.0:
        print("  WARNING: edge below 1x the round-turn cost. Spread or commission eats the exit; widen targets or skip.")

    if a.csv_out:
        with open(a.csv_out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["pass"] + exit_params + ["trades", "profit", "net_profit", "net_expectancy", "edge_ratio",
                                                "pf", "dd_pct", "raw_score", "robust_score", "neighbours"])
            for p in ranked:
                w.writerow([p["pass"]] + [p["params"][k] for k in exit_params] +
                           [p["trades"], p["profit"], p["net_profit"], p["net_expectancy"], p["edge_ratio"],
                            p["pf"], p["dd"], p["raw_score"], p["robust_score"], p["neighbours"]])
        print(f"\nFull table written to {a.csv_out}")


if __name__ == "__main__":
    sys.exit(main())
