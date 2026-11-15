"""Pull the executed trades out of an MT5 saved chart (.chr) that was saved with trade history on.

usage: python -I chart_trades.py <saved_chart.chr> <out_csv> [comment_prefix=SAR]

MT5 stores each closed trade on the chart as three objects: an entry arrow and an exit arrow
("autotrade #ticket buy|sell 0.01 SYMBOL at price", description = order comment) and a line
"autotrade #in -> #out[, SL|TP], profit X" from (entry time, entry price) to (exit time, exit price).
Times are broker server time. Points are (exit - entry) * side / 0.01.
"""
import re
import sys

import numpy as np
import pandas as pd


def read_objects(path):
    raw = open(path, "rb").read()
    txt = raw.decode("utf-16", errors="ignore") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", errors="ignore")
    objs = []
    for block in txt.split("<object>")[1:]:
        d = {}
        for line in block.split("</object>")[0].strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k] = v
        objs.append(d)
    return objs


def trades(path, prefix="SAR"):
    objs = read_objects(path)
    arrows = {}
    for o in objs:
        m = re.match(r"autotrade #(\d+) (buy|sell) ([\d.]+) ", o.get("name", ""))
        if m and o.get("type") in ("31", "32"):
            arrows[int(m.group(1))] = dict(side=m.group(2), lots=float(m.group(3)), comment=o.get("descr", ""))
    rows = []
    for o in objs:
        if o.get("type") != "2":
            continue
        m = re.match(r"autotrade #(\d+) -> #(\d+)(?:, (SL|TP))?(?:, profit ([\-\d.]+))?", o.get("name", ""))
        if not m:
            continue
        a, b = arrows.get(int(m.group(1)), {}), arrows.get(int(m.group(2)), {})
        side = 1 if a.get("side") == "buy" else -1
        po, pc = float(o["value1"]), float(o["value2"])
        ec, xc = a.get("comment", ""), b.get("comment", "")
        if xc.startswith("[sl"):
            exit_kind = "SL"
        elif xc.startswith("[tp"):
            exit_kind = "TP"
        else:
            exit_kind = xc or "other"
        level = re.search(r"\[(?:sl|tp) ([\d.]+)\]", xc)
        rows.append(dict(open_time=pd.to_datetime(int(o["date1"]), unit="s"), close_time=pd.to_datetime(int(o["date2"]), unit="s"),
                         side=side, lots=a.get("lots"), entry=po, exit=pc, pts=round(side * (pc - po) / 0.01, 1),
                         hold_s=int(o["date2"]) - int(o["date1"]), entry_comment=ec,
                         exit_kind=exit_kind, exit_level=float(level.group(1)) if level else np.nan))
    df = pd.DataFrame(rows)
    df = df[df.entry_comment.str.startswith(prefix)].sort_values("open_time").reset_index(drop=True)
    parts = df.entry_comment.str.split(":")
    df["scenario"] = parts.str[1]
    df["action"] = parts.str[2]
    df["flow"] = np.where(df.entry_comment.str.contains(":FA"), "agrees", np.where(df.entry_comment.str.contains(":FD"), "disagrees", "none"))
    return df


if __name__ == "__main__":
    out = trades(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else "SAR")
    out.to_csv(sys.argv[2], index=False)
    print(len(out), "trades", out.open_time.min(), "->", out.open_time.max())
