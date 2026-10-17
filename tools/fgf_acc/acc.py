"""FlashGold Direction Filter: search for higher direction ACCURACY, honestly.

From one TradingView export (5m recommended) it rebuilds the filter on each
filter timeframe and, at every filter candle close, reads a direction from
the filter's state. It scores many readings x conditions x timeframes x
horizons on the IN-SAMPLE part (default first 60%), picks the most accurate
ones there, and reports how they do on the OUT-OF-SAMPLE part it never saw.

Accuracy = buys and sells averaged (as the Pine status box): a market that
just drifts up does not count. 50% = coin flip. Every figure comes with its
number of calls and a 95% interval; a pick only counts if its out-of-sample
interval stays above 50%.

Usage:
    python -I tools/fgf_acc/acc.py <export_5m.csv> [--out acc_report.md]
"""
import argparse, itertools, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "fgf_ab"))
import fg5 as F
from fgf_ab import load_csv


def bars(ms, o, h, l, c, base_ms, mult):
    tf = base_ms * mult; key = ms // tf
    st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]]); en = np.r_[st[1:], len(ms)]
    return F.Bars(key[st] * tf, o[st], np.maximum.reduceat(h, st), np.minimum.reduceat(l, st), c[en - 1], tf)


def state(fb, tick, band_atr):
    """The filter at each filter candle close: zone, last signal side, its
    age, distance from the level in ATR, volatility regime."""
    f2 = F.resample(fb, 2); f4 = F.resample(fb, 4)
    s = F.signal(fb, f2, f4, F.SigParams(), tick)
    n = len(fb.t)
    sig = np.where(s["buy"], 1, np.where(s["sell"], -1, 0))
    lvl = np.full(n, np.nan); sdir = np.zeros(n, int); age = np.full(n, -1); satr = np.full(n, np.nan)
    sid = np.full(n, -1)
    cl, cd, ca, cb = np.nan, 0, np.nan, -1
    for k in range(n):
        if sig[k] != 0:
            cl = s["buy_px"][k] if sig[k] > 0 else s["sell_px"][k]; cd = sig[k]; ca = s["atr"][k]; cb = k
        lvl[k], sdir[k], satr[k], age[k], sid[k] = cl, cd, ca, (k - cb if cb >= 0 else -1), cb
    band = band_atr * np.nan_to_num(satr)
    up = np.where(band > 0, np.ceil((lvl + band) / tick - 1e-9) * tick, lvl)
    dn = np.where(band > 0, np.floor((lvl - band) / tick + 1e-9) * tick, lvl)
    c = fb.c
    zone = np.where(np.isnan(lvl), 0, np.where(c > up + tick / 2, 1, np.where(c < dn - tick / 2, -1, 0)))
    a = s["atr"]
    dist = np.where(np.isnan(lvl) | ~(satr > 0), np.nan, np.abs(c - lvl) / satr)
    a100 = pd.Series(a).rolling(100).mean().to_numpy()
    vol = a / a100
    return dict(zone=zone, sdir=sdir, age=age, dist=dist, vol=vol, atr=a, newsig=sig, parent=s["parent"], sid=sid)


def outcomes(fb, atr, horizons, barrier_atr, barrier_max):
    """+1 / -1 / 0 per candle: the close h candles later vs now, and which of
    close +- barrier_atr x ATR is touched first within barrier_max candles
    (both in one candle = counted against the call: worst case)."""
    c, h, l = fb.c, fb.h, fb.l; n = len(c); out = {}
    for hz in horizons:
        mv = np.full(n, np.nan); mv[:n - hz] = c[hz:] - c[:n - hz]
        out[f"close +{hz}"] = mv
    up_first = np.zeros(n); dn_first = np.zeros(n); both = np.zeros(n, bool); done = np.zeros(n, bool)
    for k in range(n - 1):
        if not atr[k] > 0: continue
        u = c[k] + barrier_atr * atr[k]; d = c[k] - barrier_atr * atr[k]
        for j in range(k + 1, min(n, k + 1 + barrier_max)):
            hu, hd = h[j] >= u, l[j] <= d
            if hu or hd:
                done[k] = True; up_first[k] = hu and not hd; dn_first[k] = hd and not hu; both[k] = hu and hd
                break
    out[f"{barrier_atr:g} ATR first"] = (up_first, dn_first, both, done)
    return out


def score(d, outc, mask):
    """Balanced accuracy, calls, 95% interval (normal approx on the two shares)."""
    if isinstance(outc, tuple):
        upf, dnf, both, done = outc
        ok = mask & (d != 0) & done
        right = np.where(d > 0, upf, dnf).astype(bool) & ~both
    else:
        ok = mask & (d != 0) & ~np.isnan(outc) & (outc != 0)
        right = np.where(d > 0, outc > 0, outc < 0)
    r = []
    for side in (1, -1):
        m = ok & (d == side); nn = int(m.sum())
        r.append((right[m].mean() if nn else np.nan, nn))
    (pu, nu), (pd_, nd) = r
    if nu < 5 or nd < 5: return np.nan, nu + nd, np.nan, np.nan
    acc = 0.5 * (pu + pd_)
    se = 0.5 * np.sqrt(pu * (1 - pu) / nu + pd_ * (1 - pd_) / nd)
    return acc, nu + nd, acc - 1.96 * se, acc + 1.96 * se


def calls(d, outc, mask):
    """The scored calls: (index, side, right)."""
    if isinstance(outc, tuple):
        upf, dnf, both, done = outc
        ok = mask & (d != 0) & done
        right = np.where(d > 0, upf, dnf).astype(bool) & ~both
    else:
        ok = mask & (d != 0) & ~np.isnan(outc) & (outc != 0)
        right = np.where(d > 0, outc > 0, outc < 0)
    idx = np.flatnonzero(ok)
    return idx, d[idx], right[idx]


def cluster_ci(d, outc, mask, sid, B=2000, seed=11):
    """Balanced accuracy re-sampled by whole signals (all calls made under one
    signal move together), so overlapping calls do not fake precision.
    Returns (signals, low, high)."""
    idx, side, right = calls(d, outc, mask)
    if len(idx) == 0: return 0, np.nan, np.nan
    g = sid[idx]; ug, inv = np.unique(g, return_inverse=True); k = len(ug)
    if k < 5: return k, np.nan, np.nan
    up = np.bincount(inv, weights=(side > 0) & right, minlength=k); un = np.bincount(inv, weights=side > 0, minlength=k)
    dn = np.bincount(inv, weights=(side < 0) & right, minlength=k); dnn = np.bincount(inv, weights=side < 0, minlength=k)
    rng = np.random.default_rng(seed); acc = []
    for _ in range(B):
        w = np.bincount(rng.integers(0, k, k), minlength=k)
        a_, b_ = (w * un).sum(), (w * dnn).sum()
        if a_ > 0 and b_ > 0: acc.append(0.5 * ((w * up).sum() / a_ + (w * dn).sum() / b_))
    return k, float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="acc_report.md")
    ap.add_argument("--tfs", default="3,6,12,24,48", help="filter timeframes as multiples of the export (5m: 15m,30m,1H,2H,4H)")
    ap.add_argument("--is-frac", type=float, default=0.6)
    ap.add_argument("--tick", type=float, default=0.01)
    ap.add_argument("--band-atr", type=float, default=0.25)
    ap.add_argument("--min-calls", type=int, default=150, help="in-sample calls a candidate needs")
    ap.add_argument("--warmup-days", type=float, default=5.0)
    a = ap.parse_args()

    ms, o, h, l, c = load_csv(a.csv)
    base = int(np.median(np.diff(ms)))
    t0 = ms[0] + int(a.warmup_days * 86400000); ts = t0 + int((ms[-1] - t0) * a.is_frac)
    rows = []; keep = {}
    for m in [int(x) for x in a.tfs.split(",")]:
        fb = bars(ms, o, h, l, c, base, m); S = state(fb, a.tick, a.band_atr)
        O = outcomes(fb, S["atr"], (1, 3, 6, 12), 1.0, 24)
        isp = (fb.t >= t0) & (fb.t + fb.tf_ms <= ts); oos = fb.t >= ts
        z, sd, par = S["zone"], S["sdir"], S["parent"]
        readings = {
            "zone (level side + band)": z,
            "signal direction": sd,
            "signal reversed": -sd,
            "zone agreeing with the signal": np.where(z == sd, z, 0),
            "zone against the signal": np.where((z != 0) & (z == -sd), z, 0),
            "TDI parent": par,
            "zone agreeing with TDI parent": np.where(z == par, z, 0),
            "zone reversed": -z,
        }
        dist, age, vol = S["dist"], S["age"], S["vol"]
        conds = {"all": np.ones(len(z), bool),
                 "dist < 0.5 ATR": dist < 0.5, "dist 0.5-1 ATR": (dist >= 0.5) & (dist < 1),
                 "dist 1-2 ATR": (dist >= 1) & (dist < 2), "dist >= 2 ATR": dist >= 2,
                 "signal age 0-2": (age >= 0) & (age <= 2), "signal age 3-8": (age >= 3) & (age <= 8),
                 "signal age 9+": age >= 9,
                 "vol < 0.8": vol < 0.8, "vol 0.8-1.2": (vol >= 0.8) & (vol < 1.2), "vol >= 1.2": vol >= 1.2}
        for (rn, d), (cn, cm), (on, oc) in itertools.product(readings.items(), conds.items(), O.items()):
            ai, ni, li, hi = score(d, oc, cm & isp)
            ao, no, lo, ho = score(d, oc, cm & oos)
            keep[(f"{m * base // 60000}m", rn, cn, on)] = (d, oc, cm, isp, oos, S["sid"])
            rows.append(dict(tf=f"{m * base // 60000}m", reading=rn, condition=cn, outcome=on,
                             is_acc=ai, is_calls=ni, is_lo=li, oos_acc=ao, oos_calls=no, oos_lo=lo, oos_hi=ho))
    R = pd.DataFrame(rows)
    R.to_csv(os.path.splitext(a.out)[0] + "_all.csv", index=False)
    E = R[(R.is_calls >= a.min_calls) & R.is_acc.notna()].sort_values("is_acc", ascending=False)
    top = E.head(15).copy()
    cc = [cluster_ci(*(lambda d, oc, cm, isp, oos, sid: (d, oc, cm & oos, sid))(*keep[(r.tf, r.reading, r.condition, r.outcome)]))
          for _, r in top.iterrows()]
    ci = [cluster_ci(*(lambda d, oc, cm, isp, oos, sid: (d, oc, cm & isp, sid))(*keep[(r.tf, r.reading, r.condition, r.outcome)]))
          for _, r in top.iterrows()]
    top["is_sig"] = [x[0] for x in ci]; top["oos_sig"] = [x[0] for x in cc]
    top["oos_clo"] = [x[1] for x in cc]; top["oos_chi"] = [x[2] for x in cc]
    base_rows = R[(R.reading == "zone (level side + band)") & (R.condition == "all") & (R.outcome == "close +1")]
    d = lambda x: pd.to_datetime(x, unit="ms", utc=True).strftime("%Y-%m-%d")
    pct = lambda v: "-" if pd.isna(v) else f"{v * 100:.1f}%"
    L = ["# FlashGold Direction Filter: accuracy search", "",
         f"Data: {os.path.basename(a.csv)}. In-sample {d(t0)} to {d(ts)}, out-of-sample {d(ts)} to {d(ms[-1])} "
         "(never used to choose). Accuracy = buys and sells averaged, 50% = coin flip.", "",
         f"Searched: {R.tf.nunique()} filter timeframes x {R.reading.nunique()} readings x {R.condition.nunique()} conditions x "
         f"{R.outcome.nunique()} outcomes = {len(R)} candidates; {len(E)} had >= {a.min_calls} in-sample calls. "
         "With this many tries, the best in-sample figures are inflated by luck: only the out-of-sample column counts.", "",
         "## Baseline: the zone, next candle", "", "| Filter TF | In-sample | Out-of-sample (95% interval) |", "|---|---|---|"]
    for _, r in base_rows.iterrows():
        L.append(f"| {r.tf} | {pct(r.is_acc)} ({r.is_calls}) | {pct(r.oos_acc)} ({r.oos_calls}; {pct(r.oos_lo)} - {pct(r.oos_hi)}) |")
    L += ["", "## The 15 most accurate in-sample, and what they did out of sample", "",
          "| Filter TF | Reading | Condition | Outcome | In-sample (calls / signals) | Out-of-sample (calls / signals) | OOS 95% interval, by signal | Holds? |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in top.iterrows():
        held = (r.oos_clo > 0.5) and r.oos_sig >= 20 if not pd.isna(r.oos_clo) else False
        L.append(f"| {r.tf} | {r.reading} | {r.condition} | {r.outcome} | {pct(r.is_acc)} ({r.is_calls} / {r.is_sig}) | "
                 f"{pct(r.oos_acc)} ({r.oos_calls} / {r.oos_sig}) | {pct(r.oos_clo)} - {pct(r.oos_chi)} | {'**yes**' if held else 'no'} |")
    nheld = int(((top.oos_clo > 0.5) & (top.oos_sig >= 20)).sum())
    L += ["", f"**{nheld} of the top 15 hold**: out-of-sample interval, re-sampled by whole signals, entirely above 50%, "
          "from at least 20 different signals. Calls made under the same signal overlap and move together, so the "
          "number of signals, not of calls, is the real sample size.",
          "", "Outcomes: *close +h* = the close h filter candles later is on the called side; *1 ATR first* = price "
          "reaches 1 ATR on the called side before 1 ATR on the other (within 24 candles; both in one candle counts as wrong).",
          "Conditions: *dist* = distance from the level in ATR of the signal candle; *signal age* = filter candles since "
          "the last signal; *vol* = ATR(14) over its 100-candle average.",
          "", "The full table of every candidate is in the `_all.csv` next to this report."]
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
