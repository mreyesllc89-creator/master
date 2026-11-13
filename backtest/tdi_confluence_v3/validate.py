"""Confirmation test of the frozen 15m pick. The protocol is PREREGISTRATION.md (with Amendment 1) - read it first.

    python3 validate.py selftest   # engine + statistics checks on the tuning data (BTC 2024-11 .. 2026-11); touches no unseen data
    python3 validate.py dryrun     # plumbing test of the full run on the tuning data only (output files prefixed dryrun_)
    python3 validate.py run        # THE confirmation test on unseen data. Run once. Writes validation.json and trades_*.csv
"""
import hashlib, json, math, os, platform, subprocess, sys, time
import numpy as np, pandas as pd
import numba
from multiprocessing import get_context
import engine
from engine import signals, atr_on_chart, simulate_d, simulate_x

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
N_BOOT, N_NULL_BTC, N_NULL_ALT, PROCS = 20000, 10000, 1000, 4
ALPHA = 0.02
LONG_BLOCK = 6                                               # months per block in the regime-robust test T1b
ALPHA_LOYO = 0.05                                            # T4: month-clustered p with any one calendar year removed
REALISTIC = dict(comm=0.0005, stop_at_extreme=True, carry_bp_day=3.0)   # realistic-execution scenario (Amendment 1)
SHORTS_FROM = pd.Timestamp("2019-09-13", tz="UTC")          # first Binance BTCUSDT perpetual; before it, shorting on Binance was not generally available
EXCLUSIONS = os.path.join(HERE, "data_exclusions.json")
OUT = ""                                                     # file prefix; "dryrun_" for the plumbing test
MANIFEST = os.path.join(HERE, "data_manifest.sha256")
REGISTERED = ["engine.py", "validate.py", "PREREGISTRATION.md", "data_exclusions.json"]


def excluded_months(sym):
    """months (YYYY-MM) in which the rule does not trade on `sym` - see data_exclusions.py"""
    if sym is None or not os.path.exists(EXCLUSIONS):
        return set()
    return set(json.load(open(EXCLUSIONS))["excluded"].get(sym, []))


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

    def __init__(self, df, sig=FROZEN, ex=EXIT, exclude=()):
        self.df = df; self.exclude = set(exclude)
        self.ch, self.L, self.S = signals(df, **sig)
        self.o, self.h, self.l, self.c = (np.ascontiguousarray(df[k].to_numpy()) for k in "ohlc")
        self.t1 = df.index.values.astype("int64")
        self.pos = np.searchsorted(self.t1, self.ch.index.values.astype("int64") + CHART * 60_000_000_000) - 1
        assert self.pos[0] >= 0 and np.all(np.diff(self.pos) > 0)
        # the rule does not trade in excluded months (stale-price months, Amendment 1): no entry whose signal bar OR whose
        # fill bar (the next 1m bar, = the trade's entry time used by the statistics) lies in an excluded month.
        # A position already open when an excluded block starts is left to its stop / target (no reversal inside the block).
        mon = lambda ix: np.asarray(ix.tz_convert(None).to_period("M").astype(str).isin(self.exclude))
        fill = df.index[np.minimum(self.pos + 1, len(df) - 1)]
        self.allowed = ~(mon(self.ch.index) | mon(fill)) if self.exclude else np.ones(len(self.ch), bool)
        n1 = len(self.t1)
        self.L1 = np.zeros(n1, bool); self.S1 = np.zeros(n1, bool); self.Z = np.zeros(n1)
        self.set_exit(ex)

    def set_exit(self, ex):
        base = atr_on_chart(self.df, self.ch, CHART, ex["atr_tf"], ex["atr_len"]) * ex["sl_mult"]
        with np.errstate(invalid="ignore"):
            self.valid = ~np.isnan(base) & (base > 0) & self.allowed   # entry possible here (Pine: slDist > 0; month not excluded)
        self.SL = np.full(len(self.t1), np.nan); self.SL[self.pos] = np.where(self.valid, base, np.nan)
        self.TP = self.SL * ex["tp_r"]
        self.sigL = self.L & ~self.S & self.valid    # bars with both a long and a short signal are skipped by the rule
        self.sigS = self.S & ~self.L & self.valid

    def run(self, L=None, S=None, comm=COMM):
        """-> per-trade net return (bp of notional), entry time, side (+1 / -1)."""
        L = self.sigL if L is None else L; S = self.sigS if S is None else S
        self.L1[self.pos[L]] = True; self.S1[self.pos[S]] = True
        r, eb, sd = simulate_d(self.o, self.h, self.l, self.c, self.L1, self.S1, self.SL, self.TP, self.Z, self.Z, False, True, comm)
        self.L1[self.pos[L]] = False; self.S1[self.pos[S]] = False
        return r.copy(), self.df.index[eb], sd.copy()

    def run_full(self, comm=COMM, stop_at_extreme=False, carry_bp_day=0.0):
        """The rule's own trades with exit times, R multiples and optional realistic execution (simulate_x).
        With the defaults the returns equal run() exactly."""
        L1 = np.zeros(len(self.t1), bool); S1 = np.zeros(len(self.t1), bool)
        L1[self.pos[self.sigL]] = True; S1[self.pos[self.sigS]] = True
        r, eb, sd, xb = simulate_x(self.o, self.h, self.l, self.c, L1, S1, self.SL, self.TP, comm, stop_at_extreme)
        hold = (self.t1[xb] - self.t1[eb]) / 86400e9
        r = r - carry_bp_day * hold
        risk_bp = self.SL[eb - 1] / self.o[eb] * 1e4                # stop distance at entry, in bp of the fill price
        return dict(r=r, t=self.df.index[eb], side=sd, R=r / risk_bp, hold_days=hold)

    @property
    def span(self):
        """statistics span: from the first 15m bar on which the rule may trade to the last bar"""
        first = self.ch.index[np.flatnonzero(self.allowed)[0]] if self.allowed.any() else self.df.index[0]
        return max(first, self.df.index[0]), self.df.index[-1]


# ---------------------------------------------------------------- statistics
def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def _betacf(a, b, x):
    """Continued fraction for the regularized incomplete beta function (modified Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny); h = d
    for m in range(1, 1000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        de = d * c; h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return h


def betainc(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """P(T > t) for a Student t distribution with df degrees of freedom (no scipy needed)."""
    if math.isnan(t): return float("nan")
    if math.isinf(t): return 0.0 if t > 0 else 1.0
    tail = 0.5 * betainc(df / 2.0, 0.5, df / (df + t * t))
    return tail if t > 0 else 1.0 - tail


def t_crit(alpha, df):
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_sf(mid, df) > alpha else (lo, mid)
    return (lo + hi) / 2


def month_index(t, span):
    y0, m0 = span[0].year, span[0].month
    return np.asarray((t.year - y0) * 12 + (t.month - m0)), (span[1].year - y0) * 12 + (span[1].month - m0) + 1


def month_blocks(t, span, months=1):
    """Calendar blocks of `months` months, counted from the first month of the span."""
    m, nm = month_index(t, span)
    return m // months, (nm + months - 1) // months


def week_blocks(t, span):
    w = 7 * 86400 * 10 ** 9
    return np.asarray((t.as_unit("ns").asi8 - span[0].value) // w), int((span[1].value - span[0].value) // w) + 1


def cluster_t(r, blk, nblk):
    """Cluster-robust t-test of 'mean bp per trade > 0' with calendar blocks as clusters:
    e_g = block sum - mean * block count, se = sqrt(G/(G-1) * sum e_g^2) / N, compared with Student t, G-1 df,
    G = number of blocks that contain trades. Returns t, one-sided p, G, se."""
    s = np.bincount(blk, weights=r, minlength=nblk); n = np.bincount(blk, minlength=nblk).astype(float)
    k = n > 0; s, n = s[k], n[k]; G = int(k.sum()); N = float(n.sum())
    if G < 3:
        return float("nan"), float("nan"), G, float("nan")
    m = float(s.sum() / N); e = s - m * n
    se = math.sqrt(G / (G - 1) * float((e * e).sum())) / N
    t = m / se if se > 0 else float("nan")
    return t, t_sf(t, G - 1), G, se


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
    m = float(r.mean()); sd = float(r.std(ddof=1)); tt = m / (sd / math.sqrt(len(r))) if sd > 0 else float("nan")
    loss = -r[r < 0].sum()
    out.update(mean_bp=m, sd_bp=sd, t=tt, p_t=norm_sf(tt) if math.isfinite(tt) else float("nan"), win_pct=float(100 * (r > 0).mean()),
               pf=float(r[r > 0].sum() / loss) if loss > 0 else float("inf"), total_bp=float(r.sum()))
    # verdict statistics (Amendment 1): cluster-robust t on calendar months (T1a) and on 6-month blocks (T1b)
    for key, months in (("month", 1), ("q", 3), ("6m", LONG_BLOCK)):
        blk, nb = month_blocks(t, span, months)
        ct, cp, G, se = cluster_t(r, blk, nb)
        out.update({f"crt_{key}": ct, f"p_cr_{key}": cp, f"G_{key}": G, f"se_{key}": se})
        if key == "month" and G >= 3:   # one-sided 98% bounds for the average bp per trade
            q = t_crit(ALPHA, G - 1); out.update(lcb98_cr=m - q * se, ucb98_cr=m + q * se)
    # originally registered T1 statistic and its sensitivity versions (reported, not part of the verdict)
    blk, nb = month_blocks(t, span); d = block_boot(r, blk, nb, seed=seed)
    out.update(p_month=float(np.mean(d <= 0)), lcb98_month=float(np.quantile(d, ALPHA)),
               ci95_month=[float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))], months=int(nb))
    blk, nb = week_blocks(t, span); d = block_boot(r, blk, nb, seed=seed + 1)
    out.update(p_week=float(np.mean(d <= 0)), lcb98_week=float(np.quantile(d, ALPHA)))
    return out


def fmt(s, pooled=False):
    if s["n"] < 3:
        return f"{s['n']} trades"
    nz = lambda v: float("nan") if v is None else v
    s = {k: nz(v) for k, v in s.items()}
    head = f"{s['n']:5d} trades  win {s['win_pct']:4.1f}%  avg {s['mean_bp']:+6.1f} bp"
    if not pooled:          # a trade-level t ignores the correlation between coins, so pooled rows leave it out
        head += f"  t {s['t']:+5.2f}"
    return (head + f"  PF {s['pf']:4.2f}  | month-clustered t {s['crt_month']:+5.2f} p {s['p_cr_month']:.4f}"
            f"  6-month-clustered t {s['crt_6m']:+5.2f} p {s['p_cr_6m']:.4f}  | bootstrap p {s['p_month']:.4f}")


# ---------------------------------------------------------------- null distributions
_CTX = None


def _null_chunk(args):
    kind, n, seed, comm = args
    ctx = _CTX; rng = np.random.default_rng(seed); nb = len(ctx.ch)
    out = np.full((n, 3), np.nan)                 # mean bp, trade-level t, number of trades
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
        if len(r) >= 3:
            sd = r.std(ddof=1)
            out[i] = (r.mean(), r.mean() / (sd / math.sqrt(len(r))) if sd > 0 else np.nan, len(r))
    return out


def null_dist(ctx, kind, n, comm=COMM, procs=PROCS):
    """n runs whose entries carry no information (kind = 'timing' or 'direction').
    Returns an array with columns mean bp/trade, trade-level t, number of trades."""
    global _CTX
    _CTX = ctx
    kid = {"timing": 1, "direction": 2}[kind]
    per = [n // procs + (1 if k < n % procs else 0) for k in range(procs)]
    with get_context("fork").Pool(procs) as P:
        parts = P.map(_null_chunk, [(kind, per[k], [SEED, kid, k], comm) for k in range(procs)])
    d = np.concatenate(parts)
    return d[~np.isnan(d[:, 1])]


def f6(v, nd=6):
    """number for console lines; '-' when missing"""
    return "-" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.{nd}f}"


def p_null(real, d):
    """(1 + number of null values >= real) / (N + 1); None when the real value does not exist."""
    if real is None or not np.isfinite(real):
        return None
    return (1 + int((d >= real).sum())) / (len(d) + 1)


def centered_p(s, m0):
    """T2 / T3 (Amendment 1): is the rule's average above the null runs' average m0? Month-clustered t of
    (average - m0), one-sided Student t with G - 1 df - the rule's own clustered spread, not the null runs' spread."""
    G, se, m = s.get("G_month"), s.get("se_month"), s.get("mean_bp")
    if m is None or G is None or G < 3 or se is None or not math.isfinite(se) or se <= 0:
        return None
    return t_sf((m - m0) / se, G - 1)


def finite(v):
    return v is not None and isinstance(v, (int, float, np.integer, np.floating)) and math.isfinite(v)


def below(p, a):
    """True only for a defined p-value below a (None / NaN never pass)"""
    return finite(p) and p < a


def null_summary(d, real_mean, real_t, s=None):
    if len(d) == 0:          # no usable null run (cannot happen with hundreds of trades; keeps the run from crashing)
        return dict(n=0, trades_avg=None, p_centered=None, t_centered=None, mean=None, sd=None, q98=None, max=None, t_mean=None,
                    t_q98=None, t_max=None, count_t_ge_real=None, p_t=None, count_mean_ge_real=None, p_mean=None)
    m0 = float(d[:, 0].mean()); se = (s or {}).get("se_month")
    return dict(n=int(len(d)), trades_avg=float(d[:, 2].mean()),
                p_centered=centered_p(s or {}, m0),                                                    # verdict statistic (T2 / T3)
                t_centered=(real_mean - m0) / se if finite(real_mean) and finite(se) and se > 0 else None,
                mean=m0, sd=float(d[:, 0].std()), q98=float(np.quantile(d[:, 0], 0.98)), max=float(d[:, 0].max()),
                t_mean=float(d[:, 1].mean()), t_q98=float(np.quantile(d[:, 1], 0.98)), t_max=float(d[:, 1].max()),
                # permutation p-values: reported only, not the verdict (miscalibrated, PREREGISTRATION 8.4)
                count_t_ge_real=int((d[:, 1] >= real_t).sum()) if finite(real_t) else None, p_t=p_null(real_t, d[:, 1]),
                count_mean_ge_real=int((d[:, 0] >= real_mean).sum()) if finite(real_mean) else None, p_mean=p_null(real_mean, d[:, 0]))


# ---------------------------------------------------------------- provenance
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


OUTPUTS = ("validation.json", "trades_BTC_oos.csv", "trades_alts.csv", "validation_out.txt")


def provenance(strict):
    """Ties the result to the registered code and data. strict=True (the real run) refuses to start if git cannot
    confirm that the registered files and the data manifest are committed and unchanged, if an output already
    exists, or if a data file differs from (or is missing in) data_manifest.sha256."""
    def git(*a):     # -> (exit code or None, stdout, stderr)
        try:
            r = subprocess.run(["git", "-C", HERE, *a], capture_output=True, text=True, timeout=30)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            return None, "", str(e)
    tracked = REGISTERED + ["data_manifest.sha256"]
    rc_h, head, err_h = git("rev-parse", "--verify", "HEAD")
    rc_s, dirty, err_s = git("status", "--porcelain", "--", *tracked)
    rc_l, _, err_l = git("ls-files", "--error-unmatch", "--", *tracked)
    pv = dict(started_utc=pd.Timestamp.now(tz="UTC").isoformat(), git_head=head if rc_h == 0 else f"unavailable: {err_h}",
              git_dirty_registered_files=dirty if rc_s == 0 else f"unavailable: {err_s}",
              code_sha256={f: sha256(os.path.join(HERE, f)) for f in tracked if os.path.exists(os.path.join(HERE, f))},
              versions=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__, numba=numba.__version__))
    if strict:
        problems = []
        if rc_h != 0 or len(head) not in (40, 64) or any(ch not in "0123456789abcdef" for ch in head):
            problems.append(f"cannot read the git commit (exit {rc_h}): {err_h or head!r}")
        if rc_s != 0:
            problems.append(f"git status failed (exit {rc_s}): {err_s}")
        elif dirty:
            problems.append("registered files have uncommitted changes:\n" + dirty)
        if rc_l != 0:
            problems.append(f"registered files are not all tracked by git (exit {rc_l}): {err_l}")
        for f in OUTPUTS:
            if os.path.exists(os.path.join(HERE, f)):
                problems.append(f"{f} already exists - the confirmation test is run once only")
        want = {}
        if os.path.exists(MANIFEST):
            for line in open(MANIFEST):
                if line.strip():
                    h, p = line.split(maxsplit=1); want[p.strip()] = h
        npz = sorted(p for p in want if p.endswith(".npz"))
        if not npz:
            problems.append("data_manifest.sha256 is missing or lists no .npz file")
        for name in ["BTCUSDT"] + ALTS:
            if f"data/full/{name}.npz" not in want:
                problems.append(f"data/full/{name}.npz is not listed in data_manifest.sha256")
        got = {}
        for p in npz:
            got[p] = sha256(os.path.join(HERE, p)) if os.path.exists(os.path.join(HERE, p)) else "missing"
            if got[p] != want[p]:
                problems.append(f"{p}: sha256 {got[p]} does not match the manifest {want[p]}")
        pv["data_sha256"] = got
        if problems:
            sys.exit("REFUSING TO RUN:\n- " + "\n- ".join(problems))
    return pv


# ---------------------------------------------------------------- the runs
def selftest():
    """Engine and statistics checks on data that was already used for tuning. Expected (opt15_pick_out.txt, setup P1):
    232 trades, +62.9 bp per trade, t +2.82."""
    df = load("BTCUSDT_insample"); ctx = Ctx(df)
    t0 = time.time(); r, t, sd = ctx.run(); dt = time.time() - t0
    s = summarize(r, t, ctx.span)
    print("in-sample BTC:", fmt(s)); print(f"one simulation on {len(df):,} one-minute bars: {dt * 1000:.0f} ms")
    assert s["n"] == 232 and abs(s["mean_bp"] - 62.9) < 0.1 and abs(s["t"] - 2.82) < 0.01, "does not reproduce the known in-sample result"
    d1 = null_dist(ctx, "timing", 400); d2 = null_dist(ctx, "direction", 400)
    for nm, d in (("random timing", d1), ("shuffled sides", d2)):
        print(f"{nm:15s}: mean {d[:, 0].mean():+.1f} bp (sd {d[:, 0].std():.1f}), {d[:, 2].mean():.0f} trades per run; "
              f"centered month-clustered p {centered_p(s, float(d[:, 0].mean())):.4f}; permutation p on t {p_null(s['t'], d[:, 1]):.4f}, on mean {p_null(s['mean_bp'], d[:, 0]):.4f}")
    assert abs(centered_p(s, 0.0) - s["p_cr_month"]) < 1e-12      # centred at 0 the T2/T3 statistic is T1a
    # degenerate inputs must not crash the one-shot run
    tt0 = pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC")
    z0 = summarize(np.full(6, 25.0), tt0, (tt0[0], tt0[-1])); assert z0["n"] == 6 and not math.isfinite(z0["t"])
    # Student t tail against scipy.stats.t.sf
    for tv, dfree, ref in [(2.0, 5, 0.050969739414929174), (2.264, 14, 0.01999174024701682), (2.085, 86, 0.020017089714804148),
                           (2.154, 28, 0.019997211787651712), (1.0, 3, 0.19550110947788524), (3.5, 40, 0.0005788533073787349),
                           (0.3, 120, 0.3823481055875932), (-1.2, 14, 0.8749736195858374), (6.0, 7, 0.00027112917100140525)]:
        assert abs(t_sf(tv, dfree) - ref) < 1e-10, (tv, dfree, t_sf(tv, dfree), ref)
    assert abs(t_crit(0.02, 14) - 2.263781279011907) < 1e-8 and abs(t_crit(0.02, 86) - 2.085367163266363) < 1e-8
    # cluster-robust t: equals the plain t when every trade is its own block (up to the G/(G-1) factor)
    rng = np.random.default_rng(1); x = rng.normal(10, 100, 500)
    ct, cp, G, se = cluster_t(x, np.arange(500), 500)
    assert G == 500 and abs(ct - x.mean() / (x.std(ddof=1) / math.sqrt(500))) < 1e-9
    # a strong true edge must be flagged, a zero-mean series must not (synthetic daily trades over 600 days)
    tt = pd.date_range("2020-01-01", periods=600, freq="D", tz="UTC"); sp = (tt[0], tt[-1])
    a = summarize(np.random.default_rng(7).normal(120, 300, 600), tt, sp); b = summarize(np.random.default_rng(8).normal(0, 300, 600), tt, sp)
    assert a["p_cr_month"] < 0.001 and a["p_cr_6m"] < 0.02 and 0.05 < b["p_cr_month"] < 0.95, (a, b)
    assert a["G_month"] == 20 and a["G_6m"] == 4 and a["G_q"] == 7
    # the dataset is part of the signal cache key: a sub-range must not get the full range's signals back ...
    half = df[df.index < pd.Timestamp("2025-11-01", tz="UTC")]; c2 = Ctx(half)
    r2 = c2.run()[0]; k = len(r2)
    assert len(c2.ch) < len(ctx.ch) and 100 < k < 232 and np.allclose(r2[:k - 1], r[:k - 1]), "sub-range run disagrees with the full run"
    # ... and neither must a copy with the same length and end points but modified prices inside
    d3 = df.copy(); w = (d3.index >= "2025-06-01") & (d3.index < "2025-06-15"); d3.loc[w, ["o", "h", "l", "c"]] *= 1.05
    c3 = Ctx(d3); assert (c3.ch.c.values != ctx.ch.c.values).sum() > 1000, "modified copy got the cached signals"
    # off-grid timestamps (Binance 2017-12 / 2018-02 style, +14.789 s) must not change any signal or trade
    d4 = df.copy(); w = (d4.index >= "2025-06-01") & (d4.index < "2025-06-15")
    d4.index = d4.index + pd.to_timedelta(np.where(w, 14789, 0), unit="ms"); c4 = Ctx(d4); r4 = c4.run()[0]
    assert (c4.L == ctx.L).all() and (c4.S == ctx.S).all() and np.array_equal(r4, r), "off-grid stamps change the rule's signals"
    # run_full (simulate_x, used for R multiples and realistic execution) equals run() with default options
    fr = ctx.run_full(); assert np.array_equal(fr["r"], r) and np.array_equal(fr["side"], sd) and (fr["t"] == t).all()
    assert np.all(fr["hold_days"] >= 0) and np.allclose(np.sign(fr["R"]), np.sign(r)) and 0.05 < np.median(np.abs(fr["R"])) < 5
    rx = ctx.run_full(**REALISTIC); assert len(rx["r"]) == len(r) and rx["r"].mean() < r.mean() - 5, "realistic execution should cost more than 5 bp/trade"
    # excluded months: no entry in them. Trades entered before them are unchanged, except possibly the last one, which a
    # reversal signal inside the excluded month would otherwise have closed (it is left to its stop / target instead)
    ce = Ctx(df, exclude={"2025-06"}); re_, te_, _ = ce.run()
    assert not ((te_.year == 2025) & (te_.month == 6)).any()
    kb = t < pd.Timestamp("2025-06-01", tz="UTC"); nkb = int(kb.sum())
    assert np.array_equal(re_[:nkb - 1], r[:nkb - 1]), "exclusion changed trades entered before the excluded month"
    ce2 = Ctx(df, exclude={"2024-11", "2024-12"}); assert ce2.span[0] == pd.Timestamp("2025-01-01", tz="UTC"), ce2.span
    # a real month-end signal (2025-11-30 23:45, filled 2025-12-01 00:00) must not open a trade in an excluded 2025-12
    assert ((t.year == 2025) & (t.month == 12) & (t.day == 1) & (t.hour == 0) & (t.minute == 0)).any(), "test case missing"
    te3 = Ctx(df, exclude={"2025-12"}).run()[1]; assert not ((te3.year == 2025) & (te3.month == 12)).any(), "entry in an excluded month"
    # verdict helpers: an undefined p-value never passes; an empty null distribution does not crash the summary
    assert below(0.01, 0.02) and not below(0.02, 0.02) and not below(None, 0.02) and not below(float("nan"), 0.02)
    assert null_summary(np.empty((0, 3)), None, None, {"n": 0})["p_centered"] is None
    assert null_summary(np.array([[1.0, 0.5, 5.0]]), None, None, {"n": 2})["p_t"] is None
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


def phase_range(r, t, span):
    """month-clustered p with the month boundaries shifted by 0..29 days (descriptive sensitivity)"""
    ps = []
    for d in range(30):
        sh = pd.Timedelta(days=d)
        blk, nb = month_index(t - sh, (span[0] - sh, span[1] - sh))
        ps.append(cluster_t(r, blk, nb)[1])
    ps = np.array(ps, float)
    return dict(min=float(np.nanmin(ps)), median=float(np.nanmedian(ps)), max=float(np.nanmax(ps)), share_below_alpha=float(np.mean(ps < ALPHA)))


def loyo(r, t, span):
    """leave one calendar year out: month-clustered result of the remaining trades"""
    out = {}
    for y in sorted(set(t.year)):
        k = t.year != y
        ss = summarize(r[k], t[k], span) if k.sum() >= 3 else dict(n=int(k.sum()))
        out[int(y)] = dict(n=ss["n"], mean_bp=ss.get("mean_bp"), p_cr_month=ss.get("p_cr_month"), p_cr_6m=ss.get("p_cr_6m"))
    return out


class _Tee:
    """Console output also written to a log file, flushed on every write (also keeps forked workers from
    re-writing buffered text). In the real run the log is created exclusively: an existing file is never overwritten."""

    def __init__(self, path, stream, mode):
        self.f = open(path, mode, encoding="utf-8"); self.s = stream

    def write(self, x):
        self.s.write(x); self.f.write(x); self.f.flush(); return len(x)

    def flush(self):
        self.s.flush(); self.f.flush()


def run(strict=True):
    pv = provenance(strict)                       # refuses before anything is written if the run is not clean
    sys.stdout = _Tee(os.path.join(HERE, OUT + "validation_out.txt"), sys.stdout, "x" if strict else "w")
    res = dict(protocol="PREREGISTRATION.md incl. Amendment 1", provenance=pv,
               frozen=dict(FROZEN, tfs_on=list(FROZEN["tfs_on"])), exit=EXIT, comm=COMM, seed=SEED, alpha=ALPHA,
               alpha_loyo=ALPHA_LOYO, long_block_months=LONG_BLOCK, realistic=REALISTIC)
    print("provenance:", json.dumps({k: v for k, v in res["provenance"].items() if k != "data_sha256"}))
    print("=" * 100); print("PRIMARY: BTCUSDT, unseen history (listing .. 2024-10-31), frozen rule, exits on 1-minute bars"); print("=" * 100)
    df = load("BTCUSDT", end=CUT); exc = excluded_months("BTCUSDT"); ctx = Ctx(df, exclude=exc)
    res["btc_excluded_months"] = sorted(exc)
    print(f"data: {len(df):,} one-minute bars, {df.index[0]} -> {df.index[-1]}; excluded months (stale prices): {', '.join(sorted(exc)) or 'none'}")
    print(f"statistics span {ctx.span[0]} -> {ctx.span[1]}; signals on valid bars: {int(ctx.sigL.sum())} long, {int(ctx.sigS.sum())} short")
    r, t, sd = ctx.run(); s = summarize(r, t, ctx.span); res["btc_oos"] = s
    btc_trades = pd.DataFrame({"entry_time": t.strftime("%Y-%m-%d %H:%M"), "side": sd, "ret_bp": np.round(r, 3)})   # written at the end
    print("result        :", fmt(s))
    costs = {}
    for cm in (0.0, 0.0002, 0.0005, 0.001):
        rc, tc, _ = ctx.run(comm=cm); costs[f"{cm * 100:.2f}%"] = summarize(rc, tc, ctx.span)
        print(f"   at {cm * 100:.2f}% per side:", fmt(costs[f"{cm * 100:.2f}%"]))
    res["btc_oos_costs"] = costs
    rx = ctx.run_full(**REALISTIC); sx = summarize(rx["r"], rx["t"], ctx.span); res["btc_oos_realistic"] = sx
    print(f"   realistic execution (0.05%/side, stops at the bar's worst price, {REALISTIC['carry_bp_day']:g} bp/day holding cost):", fmt(sx))
    d1 = null_dist(ctx, "timing", N_NULL_BTC); n1 = null_summary(d1, s.get("mean_bp"), s.get("t"), s)
    d2 = null_dist(ctx, "direction", N_NULL_BTC); n2 = null_summary(d2, s.get("mean_bp"), s.get("t"), s)
    res["btc_null_timing"], res["btc_null_direction"] = n1, n2
    for lab, nn in (("T2 vs random timing ", n1), ("T3 vs shuffled sides", n2)):
        print(f"{lab} ({nn['n']} runs, {f6(nn['trades_avg'], 0)} trades per run vs {s['n']} real): null average {f6(nn['mean'], 2)} bp vs real {f6(s.get('mean_bp'), 2)} bp "
              f"-> month-clustered t {f6(nn['t_centered'], 2)}, p = {f6(nn['p_centered'])} (verdict) | permutation p, reported only: on t {f6(nn['p_t'])} "
              f"({nn['count_t_ge_real']} runs), on the average {f6(nn['p_mean'])} ({nn['count_mean_ge_real']} runs)")
    lo = loyo(r, t, ctx.span); res["btc_oos_leave_one_year_out"] = lo
    lo_p = [v.get("p_cr_month") for v in lo.values()]
    t4_ok = len(lo_p) > 0 and all(below(p, ALPHA_LOYO) for p in lo_p)     # "below 0.05 every time"; an undefined p fails
    p_loyo_max = max((p for p in lo_p if finite(p)), default=None)
    tests = dict(T1a_month_clustered=s.get("p_cr_month"), T1b_6month_clustered=s.get("p_cr_6m"),
                 T2_random_timing=n1["p_centered"], T3_shuffled_sides=n2["p_centered"])
    passed = all(below(p, ALPHA) for p in tests.values()) and t4_ok
    realistic_ok = passed and below(sx.get("p_cr_month"), ALPHA) and below(sx.get("p_cr_6m"), ALPHA)
    verdict = (("PASSED: edge significant at the 98% level" + (", also under realistic execution" if realistic_ok else " (not under realistic execution)"))
               if passed else "NOT PASSED: edge not significant at the 98% level")
    res["verdict"] = dict(tests=tests, T4_worst_leave_one_year_out_p=p_loyo_max, T4_all_years_defined=all(finite(p) for p in lo_p),
                          T4_passed=bool(t4_ok), realistic_tests=dict(T1a=sx.get("p_cr_month"), T1b=sx.get("p_cr_6m")),
                          passed=bool(passed), realistic=bool(realistic_ok), text=verdict)
    print(f"\nVERDICT (pre-registered, Amendment 1: T1a, T1b, T2, T3 below {ALPHA} and T4 below {ALPHA_LOYO}):")
    for k, v in tests.items():
        print(f"   {k:22s} p = {f6(v)}  {'pass' if below(v, ALPHA) else 'FAIL'}")
    print(f"   {'T4_consistency':22s} worst p with one year removed = {f6(p_loyo_max)}  {'pass' if t4_ok else 'FAIL'}"
          f"   ({'  '.join(f'{y}: {f6(v.get('p_cr_month'), 3)}' for y, v in lo.items())})")
    print(f"   realistic execution: T1a p = {f6(sx.get('p_cr_month'))}, T1b p = {f6(sx.get('p_cr_6m'))}")
    print(f"   -> {verdict}")
    if s.get("lcb98_cr") is not None:
        print(f"   98% one-sided bounds on the average: above {s['lcb98_cr']:+.1f} bp, below {s['ucb98_cr']:+.1f} bp (month-clustered)\n")

    print("-- by year --"); yr = {}
    for y in sorted(set(t.year)):
        k = t.year == y; yr[int(y)] = dict(n=int(k.sum()), mean_bp=float(r[k].mean()), total_bp=float(r[k].sum()), win_pct=float(100 * (r[k] > 0).mean()))
        print(f"   {y}: {k.sum():4d} trades  avg {r[k].mean():+7.1f} bp  win {100 * (r[k] > 0).mean():4.1f}%  total {r[k].sum():+8.0f} bp")
    res["btc_oos_years"] = yr
    for nm, k in (("long", sd > 0), ("short", sd < 0)):
        res[f"btc_oos_{nm}"] = summarize(r[k], t[k], ctx.span); print(f"   {nm:5s}:", fmt(res[f"btc_oos_{nm}"]))
    k = (sd > 0) | (t >= SHORTS_FROM)
    res["btc_oos_long_only_before_2019_09_13"] = summarize(r[k], t[k], ctx.span)
    print("   shorts dropped before 2019-09-13:", fmt(res["btc_oos_long_only_before_2019_09_13"]))
    fr = ctx.run_full(); sR = summarize(fr["R"], fr["t"], ctx.span)
    res["btc_oos_R"] = sR
    print(f"   in R (return / stop distance): {sR['n']} trades, avg {sR.get('mean_bp', float('nan')):+.3f} R, month-clustered p {f6(sR.get('p_cr_month'), 4)}, 6-month p {f6(sR.get('p_cr_6m'), 4)}")
    res["btc_oos_phase_shift"] = phase_range(r, t, ctx.span)
    ph = res["btc_oos_phase_shift"]
    print(f"   month boundaries shifted 0..29 days: month-clustered p from {ph['min']:.4f} to {ph['max']:.4f} (median {ph['median']:.4f}), below {ALPHA} in {100 * ph['share_below_alpha']:.0f}% of shifts")
    eq = np.r_[0.0, np.cumsum(r)]; res["btc_oos_maxdd_bp"] = float((np.maximum.accumulate(eq) - eq).max()); res["btc_oos_worst_trade_bp"] = float(r.min())
    print(f"   max drawdown {res['btc_oos_maxdd_bp']:.0f} bp of notional, worst trade {r.min():.0f} bp")
    if s["n"] >= 3:   # edge that a single test would detect 80% of the time: (t_crit(0.02) + t_0.80) x its standard error
        mde = lambda se, G: float((t_crit(ALPHA, max(G - 1, 1)) + t_crit(0.20, max(G - 1, 1))) * se) if finite(se) else None
        res["power"] = dict(mde80_T1a_alone_bp=mde(s.get("se_month"), s.get("G_month") or 0),
                            mde80_T1b_alone_bp=mde(s.get("se_6m"), s.get("G_6m") or 0),
                            mde80_iid_bp=mde(s["sd_bp"] / math.sqrt(s["n"]), s["n"]),
                            note="each test alone; the full verdict needs all five tests and has lower power (PREREGISTRATION 8.5)")
        print(f"   power, each test alone: an edge of about {f6(res['power']['mde80_T1a_alone_bp'], 0)} bp (T1a) / {f6(res['power']['mde80_T1b_alone_bp'], 0)} bp (T1b) "
              f"would pass that test 80% of the time ({f6(res['power']['mde80_iid_bp'], 0)} bp if trades were independent); the full verdict has lower power")
    engine._cache.clear()
    cu = Ctx(df); ru, tu, _ = cu.run(); res["btc_oos_no_exclusion"] = summarize(ru, tu, cu.span)
    print("   without the stale-price exclusion:", fmt(res["btc_oos_no_exclusion"]))

    print("\n-- neighbours of the frozen rule on the same unseen BTC data (descriptive, not part of the verdict) --"); nb = {}
    for nm, sg, ex in NEIGHBOURS:
        c = ctx if not sg else Ctx(df, dict(FROZEN, **sg), exclude=exc)
        if ex: c.set_exit(dict(EXIT, **ex))
        rr, tt_, _ = c.run(); nb[nm] = summarize(rr, tt_, c.span); print(f"   {nm:24s}", fmt(nb[nm]))
        if ex: c.set_exit(EXIT)
    res["btc_oos_neighbours"] = nb
    npos = sum(1 for v in nb.values() if (v.get("mean_bp") or 0) > 0)
    res["neighbours_reading"] = dict(positive=npos, of=len(nb), label="plateau" if npos >= 9 else "isolated peak")
    print(f"   {npos} of {len(nb)} neighbours have a positive average -> pre-set reading: {res['neighbours_reading']['label']} (plateau needs at least 9)")
    engine._cache.clear()

    print("\n" + "=" * 100); print("OTHER COINS (surviving large caps): frozen rule. Clean = before 2024-11-01, same calendar period as the BTC test. After = descriptive"); print("=" * 100)
    rows = []; alt = {}
    for sym in ALTS:
        exa = excluded_months(sym)
        dfa = load(sym, end=CUT); ca = Ctx(dfa, exclude=exa); ra, ta, sa = ca.run(); sa_ = summarize(ra, ta, ca.span)
        da = null_dist(ca, "timing", N_NULL_ALT)
        sa_["p_random_timing"] = centered_p(sa_, float(da[:, 0].mean())); sa_["random_avg_bp"] = float(da[:, 0].mean())
        sa_["span"] = [str(ca.span[0]), str(ca.span[1])]; sa_["excluded_months"] = sorted(exa)
        Ra = ca.run_full()["R"]; sa_["mean_R"] = float(Ra.mean()) if len(Ra) else None
        print(f"   {sym:9s} clean:", fmt(sa_), f"| vs random timing p {f6(sa_['p_random_timing'], 4)}")
        rows.append(pd.DataFrame({"symbol": sym, "period": "clean", "entry_time": ta, "side": sa, "ret_bp": ra, "R": Ra}))
        engine._cache.clear()
        dff = load(sym); cf = Ctx(dff, exclude=exa); rf, tf_, sf = cf.run(); Rf = cf.run_full()["R"]; k = tf_ >= CUT
        post = summarize(rf[k], tf_[k], (CUT, dff.index[-1]))
        print(f"   {sym:9s} after:", fmt(post))
        rows.append(pd.DataFrame({"symbol": sym, "period": "after", "entry_time": tf_[k], "side": sf[k], "ret_bp": rf[k], "R": Rf[k]}))
        alt[sym] = dict(clean=sa_, after=post); engine._cache.clear()
    T = pd.concat(rows, ignore_index=True)
    for per in ("clean", "after"):
        P = T[T.period == per]; ti = pd.DatetimeIndex(P.entry_time)
        sp = (ti.min(), ti.max()); ps = summarize(P.ret_bp.to_numpy(), ti, sp)   # clusters = calendar months across all coins
        by = P.groupby("symbol").ret_bp.mean(); ps["equal_weight_by_coin_bp"] = float(by.mean()); ps["coins_positive"] = int((by > 0).sum())
        pR = summarize(P.R.to_numpy(), ti, sp); ps["R_mean"] = pR.get("mean_bp"); ps["R_p_cr_month"] = pR.get("p_cr_month")
        alt[f"pooled_{per}"] = ps
        print(f"   POOLED {per:5s}:", fmt(ps, pooled=True), f"| coins positive {ps['coins_positive']}/{len(by)} | in R: avg {f6(ps['R_mean'], 3)}, p {f6(ps['R_p_cr_month'], 4)}")
    res["alts"] = alt
    pc = alt["pooled_clean"]
    cons = below(pc.get("p_cr_month"), ALPHA) and below(pc.get("p_cr_6m"), ALPHA)
    P = T[T.period == "clean"]; mb = pd.Series(r, index=t.tz_convert(None).to_period("M")).groupby(level=0).mean()
    ma = P.groupby(pd.DatetimeIndex(P.entry_time).tz_convert(None).to_period("M")).ret_bp.mean()
    j = mb.index.intersection(ma.index); corr = float(np.corrcoef(mb[j], ma[j])[0, 1]) if len(j) > 3 else None
    res["other_coins"] = dict(p_cr_month=pc.get("p_cr_month"), p_cr_6m=pc.get("p_cr_6m"), consistent=bool(cons),
                              monthly_corr_with_btc=corr, reading="consistent with an edge" if cons else "BTC-only or no edge")
    print(f"\nOTHER COINS (supporting, same period as the BTC test, so not independent confirmation): pooled clean month-clustered p "
          f"{f6(pc.get('p_cr_month'), 4)}, 6-month p {f6(pc.get('p_cr_6m'), 4)} -> {res['other_coins']['reading']}; "
          f"correlation of monthly average bp with BTC {f6(corr, 2)}")
    res["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    # all result files are written together at the end, so a crash part-way leaves only the console log
    btc_trades.to_csv(os.path.join(HERE, OUT + "trades_BTC_oos.csv"), index=False)
    T.assign(entry_time=T.entry_time.dt.strftime("%Y-%m-%d %H:%M"), ret_bp=T.ret_bp.round(3), R=T.R.round(5)).to_csv(os.path.join(HERE, OUT + "trades_alts.csv"), index=False)
    with open(os.path.join(HERE, OUT + "validation.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(f"\nwritten: {OUT}validation.json, {OUT}trades_BTC_oos.csv, {OUT}trades_alts.csv, {OUT}validation_out.txt")
    sys.stdout.flush()


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
    run(strict=False)
    json.load(open(os.path.join(HERE, "dryrun_validation.json")))
    print("\ndryrun OK (numbers above are from the tuning data and mean nothing)")


if __name__ == "__main__":
    {"selftest": selftest, "run": run, "dryrun": dryrun}[sys.argv[1]]()
