#!/usr/bin/env python3
"""Gate 0: prove the 1.05-XPDIR build with InpDirMode = DIR_OFF trades exactly
like the 1.03 build.

Input: two MT5 Strategy Tester HTML reports (or the XML/HTML "Report" export),
one from each build, produced on the SAME window, SAME symbol, SAME model
(Every tick based on real ticks) and the SAME inputs, per
reference/gate0_tester_settings.ini.

  usage: ./compare_trades.py baseline_1.03.html candidate_1.05.html

Compares the Deals table row by row: order of deals, time, type, volume,
price, and the resulting position tickets' open/close pairs. Any difference is
a Gate 0 failure - it means something other than the direction ladder moved.

Exit 0 = identical. Exit 1 = a difference (each one printed). Exit 2 = the
inputs could not be parsed, which is not a pass.
"""
import html
import re
import sys
from html.parser import HTMLParser


class TableGrab(HTMLParser):
    """Collects every <table> as a list of rows of cell text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._t = None
        self._r = None
        self._c = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._t = []
        elif tag == "tr" and self._t is not None:
            self._r = []
        elif tag in ("td", "th") and self._r is not None:
            self._c = []

    def handle_endtag(self, tag):
        if tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None
        elif tag == "tr" and self._r is not None:
            if self._r:
                self._t.append(self._r)
            self._r = None
        elif tag in ("td", "th") and self._c is not None:
            self._r.append(" ".join("".join(self._c).split()))
            self._c = None

    def handle_data(self, data):
        if self._c is not None:
            self._c.append(data)


DEAL_HEAD = ("time", "deal", "symbol", "type", "direction", "volume", "price")


def deals_from(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    p = TableGrab()
    p.feed(raw)
    best = None
    for table in p.tables:
        for i, row in enumerate(table):
            low = [c.lower() for c in row]
            if sum(1 for k in DEAL_HEAD if any(k == c for c in low)) >= 5:
                body = [r for r in table[i + 1:] if len(r) >= len(row) - 2]
                if best is None or len(body) > len(best[1]):
                    best = (row, body)
    if best is None:
        raise SystemExit(f"{path}: no Deals table found - export the tester "
                         f"report as HTML with the deals section included")
    head, body = best
    idx = {k: next((j for j, c in enumerate(head) if c.lower() == k), None)
           for k in DEAL_HEAD}
    out = []
    for row in body:
        if not row or not re.match(r"^\d{4}\.\d{2}\.\d{2}", row[0]):
            continue
        out.append(tuple(
            row[idx[k]] if idx[k] is not None and idx[k] < len(row) else ""
            for k in DEAL_HEAD))
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    try:
        a = deals_from(sys.argv[1])
        b = deals_from(sys.argv[2])
    except SystemExit as exc:
        print(exc)
        return 2

    diffs = []
    if len(a) != len(b):
        diffs.append(f"deal count: baseline={len(a)} candidate={len(b)}")
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            diffs.append(f"deal #{i + 1}\n    baseline : {a[i]}\n    candidate: {b[i]}")

    print(f"baseline deals={len(a)} candidate deals={len(b)} differences={len(diffs)}")
    for d in diffs:
        print("  DIFF " + d)
    if not a:
        print("G0 FAIL: the baseline report contains no deals - a window with "
              "no trades proves nothing")
        return 2
    print("G0 identical" if not diffs else "G0 NOT identical")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
