#!/usr/bin/env python3
"""
Trailing-stop calibration: every trailing start x distance from the tightest to the widest,
plus trailing off, on the calibrated presets, under the three same-bar fill assumptions.

  python3 trailing_sweep.py <data_dir> <out.json>                       (gold presets)
  XLZC_SYMBOL=BTCUSD XLZC_SPREAD_PTS=500 XLZC_SPREAD_CAP=1000 \
  python3 trailing_sweep.py <btc_data_dir> <out.json>                   (BTC presets)

Start and distance are in gold points; the simulation multiplies them by
sqrt(trigger minutes) x instrument scale, exactly like the presets.

Fill assumptions when a trailing level is set and touched inside the same M1 bar:
  next  - ignored until the next bar (optimistic)
  close - stop if the bar closes beyond it (certain hits; the default)
  worst - stop if the bar's high reaches it
  random- the low comes first in a seeded half of the bars; high-first bars use the close check
None of the three is a true bound: when the trailing distance is smaller than a typical M1 bar,
"worst" exits near the bar's low (a GOOD price) and "next" is the pessimistic one. One-minute
bars cannot tell the order of prices inside a bar, so a setting is only credible if it is good
under ALL three. The trailing setting is therefore chosen on 2025 only by the neighbourhood
median of its LOWEST worst-half-year PF across the three assumptions; 2026 is out of sample.
"""
import itertools
import json
import sys

import numpy as np

import fgf_backtest as FB
import xlzc_backtest as B
import xlzc_calibrate as C

STARTS = [0, 50, 100, 150, 200, 300, 400, 600, 800]
DISTS = [25, 50, 75, 100, 150, 200, 300, 400, 600]
MODES = ["next", "close", "worst", "random"]
PRESETS = {
    "XAUUSD": {
        "M2/H1 preset": dict(tf="M2/H1", N=15, S=4, buffer=40, NT=120, min_rr=1.5, fb=1.5, stoch="soft",
                             session="ny_12-1630"),
        "M3/H1 preset": dict(tf="M3/H1", N=40, S=2, buffer=120, NT=120, min_rr=1.5, fb=0.0, stoch="soft",
                             session="ny_12-1630"),
    },
    "BTCUSD": {
        "BTC M3/M30 preset": dict(tf="M3/M30", N=40, S=3, buffer=80, NT=120, min_rr=2.0, fb=0.0, stoch="soft",
                                  session="ny_12-1630"),
        "BTC M3/H1 preset": dict(tf="M3/H1", N=40, S=2, buffer=40, NT=60, min_rr=2.0, fb=0.0, stoch="soft",
                                 session="ny_12-1630"),
    },
}


def stats(tr):
    s = C.seg_stats(tr)
    r = np.array([x[1] for x in tr])
    out = {k: (None if not np.isfinite(v) else float(v)) for k, v in s.items()}
    out["win"] = float((r > 0).mean()) if len(r) else None
    out["avg_win"] = float(r[r > 0].mean()) if (r > 0).any() else None
    out["min25"] = min(x for x in (out["2025H1_pf"], out["2025H2_pf"]) if x is not None) \
        if out["2025H1_pf"] is not None and out["2025H2_pf"] is not None else None
    return out


def main():
    data_dir, out_path = sys.argv[1], sys.argv[2]
    presets = PRESETS[B.SYMBOL]
    p = FB.prepare(data_dir, sorted({c["tf"] for c in presets.values()}))
    FB.init_worker(p)
    k_note = {name: round(B.TF_MIN[c["tf"].split("/")[0]] ** 0.5 * B.INST["scale"], 3) for name, c in presets.items()}
    res = dict(symbol=B.SYMBOL, inst=B.INST, starts=STARTS, dists=DISTS, presets={})
    for name, base in presets.items():
        rows = []
        for mode in MODES:
            B.M1Path.TRAIL_MODE = mode
            C.G["cache"] = {}
            off = stats(C.run_cfg(dict(base, trail=False))[1])
            rows.append(dict(mode=mode, start=None, dist=None, **off))
            for st, di in itertools.product(STARTS, DISTS):
                s = stats(C.run_cfg(dict(base, trail=True, trail_start=st, trail_dist=di))[1])
                rows.append(dict(mode=mode, start=st, dist=di, **s))
        B.M1Path.TRAIL_MODE = "close"
        # ---- choose on 2025 only: neighbourhood median of the lowest (over fill assumptions) worst-half PF
        def get(mode, st, di, key):
            for r in rows:
                if r["mode"] == mode and r["start"] == st and r["dist"] == di:
                    return r[key]
        score = {}
        for st, di in itertools.product(STARTS, DISTS):
            v = [get(m, st, di, "min25") for m in MODES]
            score[(st, di)] = min(v) if all(x is not None for x in v) else np.nan
        smooth = {}
        for (st, di), v in score.items():
            i, j = STARTS.index(st), DISTS.index(di)
            nb = [v]
            for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                # reflect at the grid edges so edge settings get 4 neighbours like inner ones
                a = -a if a < 0 else (2 * (len(STARTS) - 1) - a if a >= len(STARTS) else a)
                b = -b if b < 0 else (2 * (len(DISTS) - 1) - b if b >= len(DISTS) else b)
                nb.append(score[(STARTS[a], DISTS[b])])
            nb = np.array(nb, float)
            smooth[(st, di)] = float(np.nanmedian(nb)) if np.isfinite(nb).any() else np.nan
        off_score = next(r for r in rows if r["mode"] == "close" and r["start"] is None)["min25"]
        best = max(smooth, key=lambda q: -np.inf if not np.isfinite(smooth[q]) else smooth[q])
        if off_score is not None and off_score >= smooth[best]:
            best = (None, None)                     # trailing off wins on 2025
        chosen = {m: next(r for r in rows if r["mode"] == m and r["start"] == best[0] and r["dist"] == best[1])
                  for m in MODES}
        smooth[(None, None)] = off_score
        current = {m: next(r for r in rows if r["mode"] == m and r["start"] == 150 and r["dist"] == 100) for m in MODES}
        offr = {m: next(r for r in rows if r["mode"] == m and r["start"] is None) for m in MODES}
        res["presets"][name] = dict(base=base, k=k_note[name], rows=rows, chosen=dict(start=best[0], dist=best[1],
                                    smooth25=smooth[best], stats=chosen), current=current, off=offr)
        lo = lambda d: min(d[m]["all_pf"] for m in MODES)
        lo26 = lambda d: min((d[m]["2026_pf"] if d[m]["2026_pf"] is not None else np.nan) for m in MODES)
        res["presets"][name]["summary"] = {lab: dict(pf_low=lo(d), pf_high=max(d[m]["all_pf"] for m in MODES), pf26_low=lo26(d))
                                           for lab, d in (("off", offr), ("current", current), ("chosen", chosen))}
        print(f"\n{name} (points x{k_note[name]}): chosen on 2025 -> start {best[0]}, distance {best[1]} gold pts "
              f"= {round(best[0] * k_note[name])} / {round(best[1] * k_note[name])} EA points")
        for label, d in (("trailing off", offr), ("current 150/100", current), (f"chosen {best[0]}/{best[1]}", chosen)):
            print(f"  {label:18s} " + " | ".join(
                f"{m}: PF {d[m]['all_pf']:.2f} ({d[m]['all_trades']:.0f} tr) 2026 {d[m]['2026_pf'] or float('nan'):.2f}"
                for m in MODES))
    json.dump(res, open(out_path, "w"), indent=1, default=float)
    print("written", out_path)


if __name__ == "__main__":
    main()
