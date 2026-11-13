"""Confirmation test of the frozen 15m pick. The protocol is PREREGISTRATION.md - read it first.

    python3 validate.py selftest   # reproduces the known result on the tuning data (BTC 2024-11 .. 2026-11); touches no unseen data
    python3 validate.py dryrun     # plumbing test of the full run on the tuning data only (output files prefixed dryrun_)
    python3 validate.py run        # THE confirmation test on unseen data. Run once. Writes validation.json and trades_*.csv
"""
import json, math, os, sys, time
import numpy as np, pandas as pd
from multiprocessing import get_context
import engine
from engine import signals, atr_on_chart, simulate_d

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.path.join(HERE, "data", "full")
CUT = pd.Timestamp("2024-11-01", tz="UTC")       # first timestamp of the period that was used for tuning
SEED = 20261113
CHART = 15
# ---- the frozen rule (identical to the TDI_Confluence_Strategy_v3.1.pine defaults) ----
FROZEN = dict(chart_tf=CHART, divL=5, divR=5, divMin=5, divMax=60, dayH=13, dayM=0, tfs_on=(1, 1, 1, 1, 1),
              regBull=True, regBear=False, hidBull=False, hidBear=False, req4=False,
              levels=True, buyLevel=42, sellLevel=58, fix_toggles=False)
EXIT = dict(atr_tf=60, atr_len=14, sl_mult=5.0, tp_r=2.0)   # stop 5 x ATR14(60m, last closed bar), target 2R, no trail
COMM = 0.0002                                                # 0.02 % per side
ALTS = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
N_BOOT, N_NULL_BTC, N_NULL_ALT, PROCS = 20000, 5000, 1000, 4
ALPHA = 0.02
OUT = ""                                                     # file prefix; "dryrun_" for the plumbing test


def load(name, start=None, end=None):
    z = np.load(os.path.join(FULL, f"{name}.npz"))
    idx = pd.to_datetime(z["t"], unit="ms", utc=True).as_unit("ns")
    df = pd.DataFrame({k: z[k] for k in "ohlc"}, index=idx)
    if start is not None: df = df[df.index >= start]
    if end is not None: df = df[df.index < end]
    return df


class Ctx:
    """One dataset: the rule's signals on the 15m chart and its exit distances laid out on the 1-minute bars.
    A 15m signal is placed on the 1m bar that closes its 15m bar, so the entry fills at the next 1m open
    (= the next 15m open) and stop / target are walked on real 1-minute bars."""

    def __init__(self, df, sig=FROZEN, ex=EXIT):
        self.df = df
        self.ch, self.L, self.S = signals(df, **sig)
        self.o, self.h, self.l, self.c = (np.ascontiguousarray(df[k].to_numpy()) for k in "ohlc")
        self.t1 = df.index.values.astype("int64")
        self.pos = np.searchsorted(self.t1, self.ch.index.values.astype("int64") + CHART * 60_000_000_000) - 1
        assert self.pos[0] >= 0 and np.all(np.diff(self.pos) > 0)
        n1 = len(self.t1)
        self.L1 = np.zeros(n1, bool); self.S1 = np.zeros(n1, bool); self.Z = np.zeros(n1)
        self.set_exit(ex)

    def set_exit(self, ex):
        base = atr_on_chart(self.df, self.ch, CHART, ex["atr_tf"], ex["atr_len"]) * ex["sl_mult"]
        self.SL = np.full(len(self.t1), np.nan); self.SL[self.pos] = base
        self.TP = self.SL * ex["tp_r"]
        self.valid = ~np.isnan(base)                 # 15m bars on which an entry can be placed
        self.sigL = self.L & ~self.S & self.valid    # bars with both a long and a short signal are skipped by the rule
        self.sigS = self.S & ~self.L & self.valid

    def run(self, L=None, S=None, comm=COMM):
        """-> per-trade net return (bp of notional), entry time, side (+1 / -1)."""
        L = self.sigL if L is None else L; S = self.sigS if S is None else S
        self.L1[self.pos[L]] = True; self.S1[self.pos[S]] = True
        r, eb, sd = simulate_d(self.o, self.h, self.l, self.c, self.L1, self.S1, self.SL, self.TP, self.Z, self.Z, False, True, comm)
        self.L1[self.pos[L]] = False; self.S1[self.pos[S]] = False
        return r.copy(), self.df.index[eb], sd.copy()

    @property
    def span(self):
        return self.df.index[0], self.df.index[-1]


# ---------------------------------------------------------------- statistics
def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def month_blocks(t, span):
    y0, m0 = span[0].year, span[0].month
    return np.asarray((t.year - y0) * 12 + (t.month - m0)), (span[1].year - y0) * 12 + (span[1].month - m0) + 1


def week_blocks(t, span):
    w = 7 * 86400 * 10 ** 9
    return np.asarray((t.as_unit("ns").asi8 - span[0].value) // w), int((span[1].value - span[0].value) // w) + 1


def block_boot(r, blk, nblk, B=N_BOOT, seed=SEED):
    """Bootstrap distribution of the mean bp per trade when whole calendar blocks are resampled
    (all trades of a block stay together, so clustering inside a block is respected)."""
    s = np.bincount(blk, weights=r, minlength=nblk); n = np.bincount(blk, minlength=nblk).astype(float)
    rng = np.random.default_rng(seed); out = []
    for b0 in range(0, B, 500):
        idx = rng.integers(0, nblk, size=(min(500, B - b0), nblk))
        den = n[idx].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.append(np.where(den > 0, s[idx].sum(1) / den, np.nan))
    out = np.concatenate(out)
    return out[~np.isnan(out)]


def summarize(r, t, span, seed=SEED):
    out = dict(n=int(len(r)))
    if len(r) < 3:
        return out
    m = float(r.mean()); sd = float(r.std(ddof=1)); tt = m / (sd / math.sqrt(len(r)))
    loss = -r[r < 0].sum()
    out.update(mean_bp=m, sd_bp=sd, t=tt, p_t=norm_sf(tt), win_pct=float(100 * (r > 0).mean()),
               pf=float(r[r > 0].sum() / loss) if loss > 0 else float("inf"), total_bp=float(r.sum()))
    blk, nb = month_blocks(t, span); d = block_boot(r, blk, nb, seed=seed)
    out.update(p_month=float(np.mean(d <= 0)), lcb98_month=float(np.quantile(d, ALPHA)),
               ci95_month=[float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))], months=int(nb))
    blk, nb = week_blocks(t, span); d = block_boot(r, blk, nb, seed=seed + 1)
    out.update(p_week=float(np.mean(d <= 0)), lcb98_week=float(np.quantile(d, ALPHA)))
    return out


def fmt(s):
    if s["n"] < 3:
        return f"{s['n']} trades"
    return (f"{s['n']:5d} trades  win {s['win_pct']:4.1f}%  avg {s['mean_bp']:+6.1f} bp  t {s['t']:+5.2f}  PF {s['pf']:4.2f}"
            f"  | p(month-block) {s['p_month']:.4f}  98% lower bound {s['lcb98_month']:+6.1f} bp  | p(week-block) {s['p_week']:.4f}  p(t-test) {s['p_t']:.4f}")


# ---------------------------------------------------------------- null distributions
_CTX = None


def _null_chunk(args):
    kind, n, seed, comm = args
    ctx = _CTX; rng = np.random.default_rng(seed); nb = len(ctx.ch); means = np.full(n, np.nan)
    nL, nS = int(ctx.sigL.sum()), int(ctx.sigS.sum())
    cand = np.flatnonzero(ctx.valid)
    sig = np.flatnonzero(ctx.sigL | ctx.sigS); lab = ctx.sigL[sig]
    for i in range(n):
        L = np.zeros(nb, bool); S = np.zeros(nb, bool)
        if kind == "timing":            # same number of long and short entries, at random 15m bars
            pick = rng.choice(cand, nL + nS, replace=False)
            L[pick[:nL]] = True; S[pick[nL:]] = True
        else:                           # "direction": the real signal bars, long/short labels shuffled
            p = rng.permutation(lab)
            L[sig[p]] = True; S[sig[~p]] = True
        r = ctx.run(L, S, comm)[0]
        if len(r): means[i] = r.mean()
    return means


def null_dist(ctx, kind, n, comm=COMM, procs=PROCS):
    """Mean bp/trade of n runs with entries that carry no information (kind = 'timing' or 'direction')."""
    global _CTX
    _CTX = ctx
    kid = {"timing": 1, "direction": 2}[kind]
    per = [n // procs + (1 if k < n % procs else 0) for k in range(procs)]
    with get_context("fork").Pool(procs) as P:
        parts = P.map(_null_chunk, [(kind, per[k], [SEED, kid, k], comm) for k in range(procs)])
    d = np.concatenate(parts)
    return d[~np.isnan(d)]


def p_null(real, d):
    return (1 + int((d >= real).sum())) / (len(d) + 1)


# ---------------------------------------------------------------- the runs
def selftest():
    """Engine check on the data that was already used for tuning. Expected (opt15_pick_out.txt, setup P1):
    232 trades, +62.9 bp per trade, t +2.82."""
    df = load("BTCUSDT_insample"); ctx = Ctx(df)
    t0 = time.time(); r, t, sd = ctx.run(); dt = time.time() - t0
    s = summarize(r, t, ctx.span)
    print("in-sample BTC:", fmt(s)); print(f"one simulation on {len(df):,} one-minute bars: {dt * 1000:.0f} ms")
    assert s["n"] == 232 and abs(s["mean_bp"] - 62.9) < 0.1 and abs(s["t"] - 2.82) < 0.01, "does not reproduce the known in-sample result"
    d1 = null_dist(ctx, "timing", 400); d2 = null_dist(ctx, "direction", 400)
    print(f"random timing   : mean {d1.mean():+.1f} bp, sd {d1.std():.1f}, max {d1.max():+.1f}; p = {p_null(s['mean_bp'], d1):.4f}")
    print(f"shuffled sides  : mean {d2.mean():+.1f} bp, sd {d2.std():.1f}, max {d2.max():+.1f}; p = {p_null(s['mean_bp'], d2):.4f}")
    # the dataset must be part of the signal cache key: a sub-range must not get the full range's signals back
    half = df[df.index < pd.Timestamp("2025-11-01", tz="UTC")]; c2 = Ctx(half)
    r2 = c2.run()[0]; k = len(r2)
    assert len(c2.ch) < len(ctx.ch) and 100 < k < 232 and np.allclose(r2[:k - 1], r[:k - 1]), "sub-range run disagrees with the full run"
    # bootstrap sanity: a series with a strong true edge must be flagged, a zero-mean one must not
    rng = np.random.default_rng(1); tt = pd.date_range("2020-01-01", periods=600, freq="D", tz="UTC"); sp = (tt[0], tt[-1])
    a = summarize(rng.normal(60, 300, 600), tt, sp); b = summarize(rng.normal(0, 300, 600), tt, sp)
    assert a["p_month"] < 0.001 and 0.05 < b["p_month"] < 0.95, (a["p_month"], b["p_month"])
    print("selftest OK")


NEIGHBOURS = [  # descriptive only - not part of the verdict
    ("pivot 3", dict(divL=3, divR=3), {}), ("pivot 4", dict(divL=4, divR=4), {}), ("pivot 6", dict(divL=6, divR=6), {}),
    ("pivot 8", dict(divL=8, divR=8), {}), ("swing 10-120", dict(divMin=10, divMax=120), {}),
    ("levels off", dict(levels=False), {}), ("levels 38/62", dict(buyLevel=38, sellLevel=62), {}),
    ("levels 45/55", dict(buyLevel=45, sellLevel=55), {}),
    ("day start 00:00", dict(dayH=0), {}), ("day start 12:00", dict(dayH=12), {}), ("day start 14:00", dict(dayH=14), {}),
    ("stop 3xATR(60m) TP 2R", {}, dict(sl_mult=3.0)), ("stop 8xATR(60m) TP 3R", {}, dict(sl_mult=8.0, tp_r=3.0)),
    ("stop 5xATR(240m) TP 2R", {}, dict(atr_tf=240)),
]


def run():
    res = dict(protocol="PREREGISTRATION.md", frozen=dict(FROZEN, tfs_on=list(FROZEN["tfs_on"])), exit=EXIT, comm=COMM, seed=SEED)
    print("=" * 100); print("PRIMARY: BTCUSDT, unseen history (listing .. 2024-10-31), frozen rule, exits on 1-minute bars"); print("=" * 100)
    df = load("BTCUSDT", end=CUT); ctx = Ctx(df)
    print(f"data: {len(df):,} one-minute bars, {df.index[0]} -> {df.index[-1]}; signals on valid bars: {int(ctx.sigL.sum())} long, {int(ctx.sigS.sum())} short")
    r, t, sd = ctx.run(); s = summarize(r, t, ctx.span); res["btc_oos"] = s
    pd.DataFrame({"entry_time": t.strftime("%Y-%m-%d %H:%M"), "side": sd, "ret_bp": np.round(r, 3)}).to_csv(os.path.join(HERE, OUT + "trades_BTC_oos.csv"), index=False)
    print("T1 profit     :", fmt(s))
    costs = {}
    for cm in (0.0, 0.0002, 0.0005, 0.001):
        rc, tc, _ = ctx.run(comm=cm); costs[f"{cm * 100:.2f}%"] = summarize(rc, tc, ctx.span)
        print(f"   at {cm * 100:.2f}% per side:", fmt(costs[f"{cm * 100:.2f}%"]))
    res["btc_oos_costs"] = costs
    d1 = null_dist(ctx, "timing", N_NULL_BTC); p2 = p_null(s["mean_bp"], d1)
    d2 = null_dist(ctx, "direction", N_NULL_BTC); p3 = p_null(s["mean_bp"], d2)
    res["btc_null_timing"] = dict(n=len(d1), mean=float(d1.mean()), sd=float(d1.std()), q98=float(np.quantile(d1, 0.98)), max=float(d1.max()), p=p2)
    res["btc_null_direction"] = dict(n=len(d2), mean=float(d2.mean()), sd=float(d2.std()), q98=float(np.quantile(d2, 0.98)), max=float(d2.max()), p=p3)
    print(f"T2 vs random timing ({len(d1)} runs): random avg {d1.mean():+.1f} bp, 98th pct {np.quantile(d1, 0.98):+.1f}, best {d1.max():+.1f}  -> p = {p2:.4f}")
    print(f"T3 vs shuffled sides ({len(d2)} runs): shuffled avg {d2.mean():+.1f} bp, 98th pct {np.quantile(d2, 0.98):+.1f}, best {d2.max():+.1f}  -> p = {p3:.4f}")
    p1, p1c = s["p_month"], costs["0.05%"]["p_month"]
    proven = p1 < ALPHA and p2 < ALPHA
    verdict = ("PROVEN at 98% confidence" + (" and COST-ROBUST" if p1c < ALPHA else " (not cost-robust at 0.05% per side)")) if proven else "NOT PROVEN at 98% confidence"
    res["verdict"] = dict(p1_profit=p1, p2_random_timing=p2, p3_direction=p3, p1_at_0p05pct=p1c, alpha=ALPHA, proven=bool(proven), text=verdict)
    print(f"\nVERDICT (pre-registered rule: p1 < {ALPHA} and p2 < {ALPHA}):  p1 = {p1:.4f}, p2 = {p2:.4f}  ->  {verdict}\n")

    print("-- by year --"); yr = {}
    for y in sorted(set(t.year)):
        k = t.year == y; yr[int(y)] = dict(n=int(k.sum()), mean_bp=float(r[k].mean()), total_bp=float(r[k].sum()), win_pct=float(100 * (r[k] > 0).mean()))
        print(f"   {y}: {k.sum():4d} trades  avg {r[k].mean():+7.1f} bp  win {100 * (r[k] > 0).mean():4.1f}%  total {r[k].sum():+8.0f} bp")
    res["btc_oos_years"] = yr
    for nm, k in (("long", sd > 0), ("short", sd < 0)):
        res[f"btc_oos_{nm}"] = summarize(r[k], t[k], ctx.span); print(f"   {nm:5s}:", fmt(res[f"btc_oos_{nm}"]))
    eq = np.cumsum(r); res["btc_oos_maxdd_bp"] = float((np.maximum.accumulate(eq) - eq).max()); res["btc_oos_worst_trade_bp"] = float(r.min())
    print(f"   max drawdown {res['btc_oos_maxdd_bp']:.0f} bp of notional, worst trade {r.min():.0f} bp")
    sdv = s["sd_bp"]; z = 2.0537 + 0.8416
    res["power"] = dict(mde80_bp=float(z * sdv / math.sqrt(s["n"])), trades_needed_for_observed=float((z * sdv / s["mean_bp"]) ** 2) if s["mean_bp"] > 0 else None)
    print(f"   power: with {s['n']} trades the test detects a true edge of {res['power']['mde80_bp']:.0f} bp or more 80% of the time")

    print("\n-- neighbours of the frozen rule on the same unseen BTC data (descriptive, not part of the verdict) --"); nb = {}
    for nm, sg, ex in NEIGHBOURS:
        c = ctx if not sg else Ctx(df, dict(FROZEN, **sg))
        if ex: c.set_exit(dict(EXIT, **ex))
        rr, tt_, _ = c.run(); nb[nm] = summarize(rr, tt_, c.span); print(f"   {nm:24s}", fmt(nb[nm]))
        if ex: c.set_exit(EXIT)
    res["btc_oos_neighbours"] = nb
    engine._cache.clear()

    print("\n" + "=" * 100); print("REPLICATION: six other coins, frozen rule. Clean = before 2024-11-01. After = descriptive only"); print("=" * 100)
    rows = []; alt = {}
    for sym in ALTS:
        dfa = load(sym, end=CUT); ca = Ctx(dfa); ra, ta, sa = ca.run(); sa_ = summarize(ra, ta, ca.span)
        da = null_dist(ca, "timing", N_NULL_ALT); sa_["p_random_timing"] = p_null(sa_.get("mean_bp", float("nan")), da); sa_["random_avg_bp"] = float(da.mean())
        sa_["span"] = [str(dfa.index[0]), str(dfa.index[-1])]
        print(f"   {sym:9s} clean:", fmt(sa_), f"| vs random timing p {sa_['p_random_timing']:.4f}")
        rows.append(pd.DataFrame({"symbol": sym, "period": "clean", "entry_time": ta, "side": sa, "ret_bp": ra}))
        engine._cache.clear()
        dff = load(sym); cf = Ctx(dff); rf, tf_, sf = cf.run(); k = tf_ >= CUT
        post = summarize(rf[k], tf_[k], (CUT, dff.index[-1]))
        print(f"   {sym:9s} after:", fmt(post))
        rows.append(pd.DataFrame({"symbol": sym, "period": "after", "entry_time": tf_[k], "side": sf[k], "ret_bp": rf[k]}))
        alt[sym] = dict(clean=sa_, after=post); engine._cache.clear()
    T = pd.concat(rows, ignore_index=True)
    T.assign(entry_time=T.entry_time.dt.strftime("%Y-%m-%d %H:%M"), ret_bp=T.ret_bp.round(3)).to_csv(os.path.join(HERE, OUT + "trades_alts.csv"), index=False)
    for per in ("clean", "after"):
        P = T[T.period == per]; ti = pd.DatetimeIndex(P.entry_time)
        sp = (ti.min(), ti.max()); ps = summarize(P.ret_bp.to_numpy(), ti, sp)
        by = P.groupby("symbol").ret_bp.mean(); ps["equal_weight_by_coin_bp"] = float(by.mean()); ps["coins_positive"] = int((by > 0).sum())
        alt[f"pooled_{per}"] = ps
        print(f"   POOLED {per:5s}:", fmt(ps), f"| coins positive {ps['coins_positive']}/{len(by)}")
    res["alts"] = alt
    rep = alt["pooled_clean"]["p_month"] < ALPHA
    res["replication"] = dict(p_pooled_clean=alt["pooled_clean"]["p_month"], replicates=bool(rep))
    print(f"\nREPLICATION (pre-registered: pooled clean p < {ALPHA}): p = {alt['pooled_clean']['p_month']:.4f} -> {'REPLICATES' if rep else 'DOES NOT REPLICATE'}")
    json.dump(res, open(os.path.join(HERE, OUT + "validation.json"), "w"), indent=1)


def dryrun():
    """Plumbing test of run() that touches NO unseen data: every symbol is served from the tuning data
    (BTC 2024-11 .. 2026-11, shifted start per symbol), the cut is moved to 2025-11-01, few resamples."""
    global load, CUT, N_NULL_BTC, N_NULL_ALT, OUT
    real_load = load

    def fake_load(name, start=None, end=None):
        df = real_load("BTCUSDT_insample", start, end)
        k = ([""] + ALTS).index("" if name == "BTCUSDT" else name)
        return df.iloc[k * 20000:]

    load, CUT, N_NULL_BTC, N_NULL_ALT, OUT = fake_load, pd.Timestamp("2025-11-01", tz="UTC"), 200, 100, "dryrun_"
    run()
    json.load(open(os.path.join(HERE, "dryrun_validation.json")))
    print("\ndryrun OK (numbers above are from the tuning data and mean nothing)")


if __name__ == "__main__":
    {"selftest": selftest, "run": run, "dryrun": dryrun}[sys.argv[1]]()
