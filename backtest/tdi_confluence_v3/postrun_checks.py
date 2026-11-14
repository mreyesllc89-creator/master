"""Checks added AFTER the confirmation test, by the second review (REVIEW_AFTER_RUN.md). Descriptive only: nothing here is
part of the registered test, nothing re-tunes the rule, and the registered code (engine.py, validate.py) is used unchanged.
Every figure that this review added to RESULTS.md and is not already in a committed output comes from here.

  1. The checks of the first T1 registered in PREREGISTRATION.md section 5 (week blocks, plain t-test), from validation.json.
  2. The BTC test trades in R (return / stop distance) by year.
  3. The 98% upper bound on the BTC test average with longer clusters than calendar months.
  4. The other coins after 2024-11 in R, and their change from before 2024-11.
  5. The pivot tie rule: engine.py gives a tie to the OLDER bar, TradingView's ta.pivotlow / ta.pivothigh to the NEWER one.
     The rule's signals are recomputed with TradingView's tie rule (the rest of the engine unchanged).

Usage: python3 postrun_checks.py > postrun_checks_out.txt     (about 1 minute; needs data/full/*.npz)"""
import json, math, os, sys, time
import numpy as np, pandas as pd
from numba import njit
import engine, validate as V

HERE = os.path.dirname(os.path.abspath(__file__))
t_start = time.time()
J = json.load(open(os.path.join(HERE, "validation.json")))
T = pd.read_csv(os.path.join(HERE, "trades_BTC_oos.csv"))
EXC = V.excluded_months("BTCUSDT")


def tr(r, t, span, months=1):
    """mean, month-clustered se, one-sided p, G and 98% upper bound with blocks of `months` calendar months"""
    blk, nb = V.month_blocks(t, span, months)
    ct, p, G, se = V.cluster_t(r, blk, nb)
    m = float(r.mean())
    return dict(mean=m, se=se, p=p, G=G, ucb=m + V.t_crit(V.ALPHA, G - 1) * se)


def norm_p(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


print("=" * 100)
print("1. Checks of the first T1 registered in section 5 (validation.json, btc_oos)")
b = J["btc_oos"]
print(f"   week-block bootstrap p {b['p_week']:.4f} | plain t-test on single trades: t {b['t']:+.3f}, p {b['p_t']:.4f} | "
      f"month-block bootstrap p {b['p_month']:.4f}")

print("=" * 100)
print("2. BTC test trades (2017-12 -> 2024-10) in R by year")
ctx = V.Ctx(V.load("BTCUSDT", end=V.CUT), exclude=EXC)
fr = ctx.run_full(); r, t, R, sd = fr["r"], fr["t"], fr["R"], fr["side"]; span = ctx.span
same = (len(r) == len(T) and np.array_equal(np.round(r, 3), T.ret_bp.to_numpy()) and np.array_equal(sd, T.side.to_numpy())
        and bool((t.strftime("%Y-%m-%d %H:%M") == T.entry_time).all()))
print(f"   rebuilt {len(r)} trades; identical to trades_BTC_oos.csv: {same}")
assert same
risk = r / R                                   # stop distance at entry, bp of the fill price
sR = tr(R, t, span)
print(f"   all: {r.mean():+.2f} bp, {R.mean():+.4f} R per trade (month-clustered p {sR['p']:.4f}); total {r.sum():+,.0f} bp, {R.sum():+.2f} R; "
      f"stop distance median {np.median(risk):.0f} bp")
print("   year  trades  avg bp  total bp  share of bp loss | avg R   total R  share of R loss | median stop bp")
for y in sorted(set(t.year)):
    k = t.year == y
    print(f"   {y}  {k.sum():5d}  {r[k].mean():+7.1f}  {r[k].sum():+8.0f}  {r[k].sum() / r.sum():6.0%}           | {R[k].mean():+.3f}  "
          f"{R[k].sum():+7.1f}  {R[k].sum() / R.sum():6.0%}          | {np.median(risk[k]):6.0f}")
yrs = sorted(set(t.year))
print(f"   years with a negative average: in R {sum(R[t.year == y].mean() < 0 for y in yrs)} of {len(yrs)}, "
      f"in bp {sum(r[t.year == y].mean() < 0 for y in yrs)} of {len(yrs)}")
k = t.year != 2018; a = tr(R[k], t[k], span); ab = tr(r[k], t[k], span)
print(f"   without 2018: {ab['mean']:+.2f} bp (p {ab['p']:.3f}) | {a['mean']:+.4f} R (month-clustered p {a['p']:.3f}, 98% upper bound {a['ucb']:+.4f} R)")
k = ~np.isin(t.year, [2018, 2023]); a = tr(R[k], t[k], span)
print(f"   without 2018 and 2023 (the other six years): {a['mean']:+.4f} R (p {a['p']:.3f}); 2018 + 2023 hold "
      f"{R[np.isin(t.year, [2018, 2023])].sum() / R.sum():.0%} of the R loss")

print("=" * 100)
print("3. 98% one-sided upper bound on the BTC test average (bp per trade) by cluster size")
rr = T.ret_bp.to_numpy(float); tt = pd.DatetimeIndex(pd.to_datetime(T.entry_time, utc=True))
for lab, k in (("all trades", np.ones(len(rr), bool)), ("without 2018", np.asarray(tt.year != 2018))):
    parts = []
    for months, nm in ((1, "months"), (3, "3-month blocks"), (6, "6-month blocks (T1b)"), (12, "12-month blocks")):
        s = tr(rr[k], tt[k], span, months); parts.append(f"{nm} {s['ucb']:+.1f} (G {s['G']})")
    print(f"   {lab:12s}: " + " | ".join(parts))
blk, nb = V.month_blocks(tt, span, 6)
s6 = np.bincount(blk, weights=rr, minlength=nb); n6 = np.bincount(blk, minlength=nb); e2 = (s6 - rr.mean() * n6) ** 2
print(f"   6-month blocks: the block 2017-12 -> 2018-05 holds {e2[0] / e2.sum():.0%} of the sum of squared block residuals")
mb, nbm = V.month_blocks(tt, span, 1); hy = np.where(mb < 6, 0, mb - 5)        # months, but 2017-12 .. 2018-05 merged into one cluster
ct, p, G, se = V.cluster_t(rr, hy, int(hy.max()) + 1)
print(f"   months, with only 2017-12 -> 2018-05 merged into one cluster: upper bound {rr.mean() + V.t_crit(V.ALPHA, G - 1) * se:+.1f} (G {G})")
print(f"   lag-1 autocorrelation of the 83 monthly averages: "
      f"{pd.Series(rr).groupby(mb).mean().reindex(range(nbm)).autocorr(1):+.3f}")

print("=" * 100)
print("4. Other coins after 2024-11 (the BTC tuning window) against before (2017-12 -> 2024-10), pooled, month clusters")
A = pd.read_csv(os.path.join(HERE, "trades_alts.csv")); A["t"] = pd.to_datetime(A.entry_time, utc=True)


def pooled(P, col):
    ti = pd.DatetimeIndex(P.t); return V.summarize(P[col].to_numpy(float), ti, (ti.min(), ti.max()))


for lab, mask in (("all six coins", np.ones(len(A), bool)), ("without DOGE", (A.symbol != "DOGEUSDT").to_numpy())):
    for col, unit in (("ret_bp", "bp"), ("R", "R")):
        c = pooled(A[(A.period == "clean") & mask], col); f = pooled(A[(A.period == "after") & mask], col)
        d = f["mean_bp"] - c["mean_bp"]; se = math.hypot(f["se_month"], c["se_month"])
        print(f"   {lab:13s} [{unit:2s}]: before {c['mean_bp']:+8.3f} (p {c['p_cr_month']:.3f}) -> after {f['mean_bp']:+8.3f} "
              f"(p {f['p_cr_month']:.3f}); rise {d:+.3f}, z {d / se:+.2f}, one-sided p {norm_p(d / se):.3f}")
fi = V.Ctx(V.load("BTCUSDT_insample")).run_full(); si = V.summarize(fi["R"], fi["t"], (fi["t"].min(), fi["t"].max()))
print(f"   BTC on its tuning data, for comparison: {len(fi['r'])} trades, {fi['r'].mean():+.2f} bp, {fi['R'].mean():+.4f} R per trade (p {si['p_cr_month']:.3f})")
engine._cache.clear()

print("=" * 100)
print("5. Pivot tie rule: engine.py (tie -> older bar) against TradingView (tie -> newer bar)")
ORIG_DIV = engine._div


@njit(cache=True)
def _pivots_tv(osc, L, R):
    """engine._pivots with the two sides' strictness swapped: an equal bar on the left does not disqualify a pivot,
    an equal bar on the right does, so a tie goes to the newer bar (TradingView's ta.pivotlow / ta.pivothigh)"""
    n = osc.size
    pl = np.full(n, np.nan); ph = np.full(n, np.nan)
    for i in range(L + R, n):
        c = i - R; v = osc[c]
        if np.isnan(v):
            continue
        isl = True; ish = True
        for k in range(c - L, c + R + 1):
            if k == c:
                continue
            w = osc[k]
            if np.isnan(w):
                isl = False; ish = False; break
            if k < c:
                if not v <= w: isl = False
                if not v >= w: ish = False
            else:
                if not v < w: isl = False
                if not v > w: ish = False
        if isl: pl[i] = v
        if ish: ph[i] = v
    return pl, ph


@njit(cache=True)
def _div_tv(osc, lo, hi, L, R, mn, mx):
    """engine._div verbatim, with _pivots_tv"""
    n = osc.size
    pl, ph = _pivots_tv(osc, L, R)
    rb = np.zeros(n, np.bool_); rr = np.zeros(n, np.bool_)
    hb = np.zeros(n, np.bool_); hr = np.zeros(n, np.bool_)
    lastPlO = np.nan; lastPlP = np.nan; lastPhO = np.nan; lastPhP = np.nan
    bsPl = -1; bsPh = -1
    for i in range(n):
        prevBsPl = bsPl; prevBsPh = bsPh
        if not np.isnan(pl[i]):
            prevO = lastPlO; prevP = lastPlP; cp = lo[i - R]; v = pl[i]
            okb = prevBsPl >= 0 and mn <= prevBsPl and prevBsPl <= mx
            if not np.isnan(prevO) and okb:
                if cp < prevP and v > prevO: rb[i] = True
                if cp > prevP and v < prevO: hb[i] = True
            lastPlO = v; lastPlP = cp; bsPl = 0
        elif bsPl >= 0:
            bsPl += 1
        if not np.isnan(ph[i]):
            prevO = lastPhO; prevP = lastPhP; cp = hi[i - R]; v = ph[i]
            okb = prevBsPh >= 0 and mn <= prevBsPh and prevBsPh <= mx
            if not np.isnan(prevO) and okb:
                if cp > prevP and v < prevO: rr[i] = True
                if cp < prevP and v > prevO: hr[i] = True
            lastPhO = v; lastPhP = cp; bsPh = 0
        elif bsPh >= 0:
            bsPh += 1
    return rb, rr, hb, hr


def ctx_with(df, exclude, tv):
    engine._div = _div_tv if tv else ORIG_DIV
    engine._cache.clear()
    try:
        return V.Ctx(df, exclude=exclude)
    finally:
        engine._div = ORIG_DIV
        engine._cache.clear()


def fmt_s(s):
    return (f"{s['n']} trades, {s['mean_bp']:+.2f} bp | T1a p {s['p_cr_month']:.3f} | T1b p {s['p_cr_6m']:.3f} | "
            f"98% bounds {s['lcb98_cr']:+.1f} / {s['ucb98_cr']:+.1f}")


print("   Two ties with TradingView's own output:")
# (a) BINANCE:BTCUSDT 60m highs with a tie on the left, quoted with TradingView's value in PineTS's CHANGELOG (0.10.0)
x = np.array([80107.99, 80028.01, 80107.99, 79989.13, 79865.89])
print(f"     (a) highs {x.tolist()}, pivothigh(2, 2) on the last bar: TradingView 80107.99 | "
      f"engine {engine._pivots(x, 2, 2, x)[1][-1]} | TradingView rule {_pivots_tv(x, 2, 2)[1][-1]}")
# (b) BINANCE:BTCUSDT 30m highs 2025-01-05 05:30 .. 09:00 with a tie on the right, from PyneCore's TradingView export
#     tests/t01_lib/t20_ta/data/pivot_zero_strength.csv (column ph_0_5 = ta.pivothigh(high, 0, 5))
x = np.array([98500.00, 98393.94, 98500.00, 98464.84, 98355.83, 98268.78, 97941.97, 97943.02])
print(f"     (b) highs {x.tolist()}, pivothigh(0, 5) at 08:00 / 09:00: TradingView nan / 98500.0 | "
      f"engine {engine._pivots(x, 0, 5, x)[1][5]} / {engine._pivots(x, 0, 5, x)[1][7]} | "
      f"TradingView rule {_pivots_tv(x, 0, 5)[1][5]} / {_pivots_tv(x, 0, 5)[1][7]}")

df = V.load("BTCUSDT", end=V.CUT)
cb = ctx_with(df, EXC, False); ct_ = ctx_with(df, EXC, True)
d = np.flatnonzero(cb.allowed & ((ct_.L != cb.L) | (ct_.S != cb.S)))
print(f"   BTC test data: signal bars in tradable months: engine {int((cb.L & cb.allowed).sum())} long + {int((cb.S & cb.allowed).sum())} short; "
      f"{len(d)} differ under TradingView's rule:")
for i in d:
    print(f"     {cb.ch.index[i]}  engine long {int(cb.L[i])} short {int(cb.S[i])} -> TradingView rule long {int(ct_.L[i])} short {int(ct_.S[i])}")
res = {}
for nm, c in (("engine", cb), ("TradingView tie rule", ct_)):
    r_, t_, s_ = c.run(); s = V.summarize(r_, t_, c.span); ly = V.loyo(r_, t_, c.span)
    worst = max(v["p_cr_month"] for v in ly.values() if v.get("p_cr_month") is not None)
    res[nm] = pd.DataFrame(dict(t=t_, side=s_, r=r_))
    print(f"   BTC test, {nm:20s}: {fmt_s(s)} | T4 worst p {worst:.3f}")
m = res["engine"].merge(res["TradingView tie rule"], on=["t", "side"], how="outer", suffixes=("_engine", "_tv"), indicator=True)
ch = m[(m._merge != "both") | (np.abs(m.r_engine - m.r_tv) > 1e-9)]
print("   trades that differ (bp):")
for _, w in ch.iterrows():
    f = lambda v: "  no trade" if np.isnan(v) else f"{v:+10.2f}"
    print(f"     {w.t}  side {int(w.side):+d}  engine {f(w.r_engine)}  TradingView rule {f(w.r_tv)}")
del cb, ct_

dt = V.load("BTCUSDT_insample")
for nm, tv in (("engine", False), ("TradingView tie rule", True)):
    c = ctx_with(dt, (), tv); r_, t_, _ = c.run()
    print(f"   BTC tuning data, {nm:20s}: {fmt_s(V.summarize(r_, t_, c.span))}")

pool = {False: [], True: []}
for sym in V.ALTS:
    exa = V.excluded_months(sym); da = V.load(sym, end=V.CUT); line = f"   {sym:9s}"
    for tv in (False, True):
        c = ctx_with(da, exa, tv); r_, t_, _ = c.run(); s = V.summarize(r_, t_, c.span); pool[tv].append((r_, t_))
        line += f" | {'TradingView rule' if tv else 'engine'}: {len(r_)} trades {r_.mean():+8.2f} bp, p {s['p_cr_month']:.3f}"
    print(line)
for tv in (False, True):
    r_ = np.concatenate([x[0] for x in pool[tv]]); ti = pd.DatetimeIndex(np.concatenate([x[1].asi8 for x in pool[tv]])).tz_localize("UTC")
    s = V.summarize(r_, ti, (ti.min(), ti.max()))
    print(f"   other coins pooled, {'TradingView tie rule' if tv else 'engine':20s}: {s['n']} trades, {s['mean_bp']:+.2f} bp, "
          f"month-clustered p {s['p_cr_month']:.3f}")
print(f"\ndone in {time.time() - t_start:.0f} s")
