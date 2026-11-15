"""Independent implementation (auditor 'features') of every entry-condition feature of hump_wf.Feat, written from
the descriptions, on integer minute stamps with explicit loops. Nothing here is imported from hump_wf.

Conventions copied on purpose (they are design choices, not correctness questions): warm-up lengths (first 50 HTF
bars of the EMA trend, first n_ema of the slope, first 60 of the HTF MACD), ATR(14) / ADX(14) seeded with the first
value (a textbook Wilder seed is available with seed='sma'), percentile window 20 days of trigger bars."""
import numpy as np, numba as nb

TFM = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "M10": 10, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
NICE = np.array([1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000], float)


def minutes(index):
    """Server-time stamps -> integer minutes since 1970-01-01 00:00 (floor)."""
    return (index.values.astype("datetime64[m]")).astype(np.int64)


def bars(tm, o, h, l, c, v, tfm):
    """Bars of tfm minutes aligned to midnight (1440 % tfm == 0), only bins with data."""
    b = tm // tfm
    st = np.r_[0, np.flatnonzero(np.diff(b)) + 1]
    en = np.r_[st[1:], len(b)]
    return dict(T=b[st] * tfm, O=o[st], H=np.maximum.reduceat(h, st), L=np.minimum.reduceat(l, st), C=c[en - 1],
                V=np.add.reduceat(v, st), st=st, en=en)


@nb.njit(cache=True)
def ema(x, n):
    a = 2.0 / (n + 1.0)
    y = np.empty(len(x))
    for i in range(len(x)):
        y[i] = x[i] if i == 0 else a * x[i] + (1 - a) * y[i - 1]
    return y


@nb.njit(cache=True)
def wilder(x, n, seed_sma):
    """Wilder smoothing (alpha 1/n). seed_sma=0: seeded with the first value, NaN before n values;
    seed_sma=1: textbook, first value = mean of the first n, NaN before. Leading NaNs are skipped."""
    y = np.full(len(x), np.nan)
    k0 = 0
    while k0 < len(x) and x[k0] != x[k0]:
        k0 += 1
    if k0 >= len(x):
        return y
    if seed_sma == 0:
        s = x[k0]; cnt = 0
        for i in range(k0, len(x)):
            if x[i] == x[i]:
                cnt += 1
                if i > k0:
                    s = s + (x[i] - s) / n
            if cnt >= n:
                y[i] = s
    else:
        if k0 + n > len(x):
            return y
        s = 0.0
        for i in range(k0, k0 + n):
            s += x[i]
        s /= n
        y[k0 + n - 1] = s
        for i in range(k0 + n, len(x)):
            s = s + (x[i] - s) / n
            y[i] = s
    return y


def true_range(H, L, C):
    pc = np.r_[np.nan, C[:-1]]
    tr = H - L
    with np.errstate(invalid="ignore"):
        tr = np.where(np.isnan(pc), tr, np.maximum(tr, np.maximum(np.abs(H - pc), np.abs(L - pc))))
    return tr


def atr14(H, L, C, seed="first"):
    return wilder(true_range(H, L, C), 14, 1 if seed == "sma" else 0)


def adx14(H, L, C, seed="first"):
    sd = 1 if seed == "sma" else 0
    up = np.r_[np.nan, H[1:] - H[:-1]]; dn = np.r_[np.nan, L[:-1] - L[1:]]
    with np.errstate(invalid="ignore"):
        pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(H, L, C)
    if sd == 1:                                 # textbook: smoothing starts at the second bar (first difference)
        tr = tr.copy(); tr[0] = np.nan; pdm = pdm.copy(); pdm[0] = np.nan; mdm = mdm.copy(); mdm[0] = np.nan
    atr = wilder(tr, 14, sd); sp = wilder(pdm, 14, sd); sm = wilder(mdm, 14, sd)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100 * sp / atr; mdi = 100 * sm / atr
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return wilder(dx, 14, sd)


def last_closed(htf_T, htf_m, trig_close):
    """Index of the last HTF bar whose close (open + htf_m) is at or before each trigger close; -1 if none."""
    return np.searchsorted(htf_T + htf_m, trig_close, side="right") - 1


def htf_idx(hT, hm, close, mutant=None):
    if mutant == "htf_from_open":                      # look-ahead: the HTF bar that contains the trigger bar's last minute
        return np.searchsorted(hT, close - 1, side="right") - 1
    return last_closed(hT, hm, close)


def take(arr, k, fill=np.nan):
    out = np.full(len(k), fill, float)
    ok = k >= 0
    out[ok] = arr[k[ok]]
    return out


@nb.njit(cache=True)
def rank_pct(x, w, minp):
    """Percentile rank of x[i] among the last w values (incl. x[i]), ties averaged; NaN if fewer than minp valid."""
    n = len(x); out = np.full(n, np.nan)
    for i in range(n):
        if x[i] != x[i]:
            continue
        lo = max(0, i - w + 1)
        cnt = 0; less = 0; eq = 0
        for j in range(lo, i + 1):
            v = x[j]
            if v == v:
                cnt += 1
                if v < x[i]:
                    less += 1
                elif v == x[i]:
                    eq += 1
        if cnt >= minp:
            out[i] = (less + (eq + 1) / 2.0) / cnt
    return out


@nb.njit(cache=True)
def pivots(H, L, w):
    """Last pivot high / low with w bars on each side (strict), known w bars after the pivot."""
    n = len(H); ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    lh = np.nan; ll = np.nan
    for i in range(n):
        j = i - w
        if j - w >= 0:
            okh = True; okl = True
            for q in range(j - w, j + w + 1):
                if q == j:
                    continue
                if not (H[q] < H[j]):
                    okh = False
                if not (L[q] > L[j]):
                    okl = False
            if okh:
                lh = H[j]
            if okl:
                ll = L[j]
        ph[i] = lh; pl[i] = ll
    return ph, pl


@nb.njit(cache=True)
def stoch_main(H, L, C, k):
    n = len(C); m = np.full(n, np.nan)
    for i in range(k - 1, n):
        hh = -1e300; ll = 1e300
        for j in range(i - k + 1, i + 1):
            if H[j] > hh: hh = H[j]
            if L[j] < ll: ll = L[j]
        if hh > ll:
            m[i] = 100.0 * (C[i] - ll) / (hh - ll)
    return m


@nb.njit(cache=True)
def sma_strict(x, n):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        s = 0.0; ok = True
        for j in range(i - n + 1, i + 1):
            if x[j] != x[j]:
                ok = False; break
            s += x[j]
        if ok:
            out[i] = s / n
    return out


@nb.njit(cache=True)
def roll_ext_strict(x, n, mx):
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        ok = True; e = -1e300 if mx else 1e300
        for j in range(i - n + 1, i + 1):
            if x[j] != x[j]:
                ok = False; break
            if mx and x[j] > e: e = x[j]
            if (not mx) and x[j] < e: e = x[j]
        if ok:
            out[i] = e
    return out


def features(tm, o, h, l, c, v, tf, htf_up, seed="first", mutant=None):
    """Every feature at each trigger bar of tf. tm: integer minutes; o h l c v: M1 arrays."""
    m = TFM[tf]
    t = bars(tm, o, h, l, c, v, m)
    T, O, H, L, C = t["T"], t["O"], t["H"], t["L"], t["C"]
    close = T + m
    F = {}
    for htf, key in (("H4", "h4"), ("D1", "d1")):
        hb = bars(tm, o, h, l, c, v, TFM[htf])
        e50 = ema(hb["C"], 50); e50[:50] = np.nan
        n_ema, lag = (50, 5) if htf == "H4" else (20, 3)
        es = ema(hb["C"], n_ema); es[:n_ema] = np.nan
        es_lag = np.r_[np.full(lag, np.nan), es[:-lag]]
        k = htf_idx(hb["T"], TFM[htf], close, mutant)
        with np.errstate(invalid="ignore"):
            F["tr_" + key] = np.nan_to_num(take(np.sign(hb["C"] - e50), k)).astype(np.int8)
            F["sl_" + key] = np.nan_to_num(take(np.sign(es - es_lag), k)).astype(np.int8)
    for htf in ("H1", "H4"):
        hb = bars(tm, o, h, l, c, v, TFM[htf])
        k = htf_idx(hb["T"], TFM[htf], close, mutant)
        F["adx_" + htf.lower()] = take(adx14(hb["H"], hb["L"], hb["C"], seed), k)
    atr = atr14(H, L, C, seed)
    w = int(20 * 1440 / m)
    F["atrp"] = rank_pct(atr, w, w // 2)
    # days
    dayk = tm // 1440
    db = bars(tm, o, h, l, c, v, 1440)                 # days with data, in order
    dD = db["T"] // 1440
    rng = db["H"] - db["L"]
    nd = len(dD)
    adr = np.full(nd, np.nan)                           # mean range of the 20 trading days before
    cs = np.r_[0.0, np.cumsum(rng)]
    for d in range(20, nd):
        adr[d] = (cs[d] - cs[d - 20]) / 20.0
    bd = T // 1440
    di = np.searchsorted(dD, bd)                         # trading-day index of each trigger bar
    assert (dD[di] == bd).all()
    pv = di - 1                                         # previous trading day
    if mutant == "today_not_yesterday":
        pv = di
    pdh = take(db["H"], pv); pdl = take(db["L"], pv); pdc = take(db["C"], pv)
    with np.errstate(invalid="ignore", divide="ignore"):
        F["pdr"] = take(rng, pv) / take(adr, pv)
    # running range of the day over the trigger bars up to this one
    run_hi = np.empty(len(T)); run_lo = np.empty(len(T))
    for i in range(len(T)):
        if i == 0 or bd[i] != bd[i - 1]:
            run_hi[i] = H[i]; run_lo[i] = L[i]
        else:
            run_hi[i] = max(run_hi[i - 1], H[i]); run_lo[i] = min(run_lo[i - 1], L[i])
    with np.errstate(invalid="ignore", divide="ignore"):
        F["tdr"] = (run_hi - run_lo) / take(adr, di)
        F["pdpos"] = (C - pdl) / (pdh - pdl)
    F["dopen"] = np.sign(C - db["O"][di]).astype(np.int8)
    tod_m1 = tm % 1440
    otod = T % 1440
    for key, a, b in (("asia", 60, 540), ("nyor", 990, 1050)):
        sel = (tod_m1 >= a) & (tod_m1 < b)
        rd = dayk[sel]
        ud, st = np.unique(rd, return_index=True)
        rh = np.maximum.reduceat(h[sel], st); rl = np.minimum.reduceat(l[sel], st)
        j = np.searchsorted(ud, bd); j = np.where((j < len(ud)) & (ud[np.clip(j, 0, len(ud) - 1)] == bd), j, -1)
        ok = (otod >= a) & (otod + m >= b)
        if mutant == "range_before_complete":
            ok = otod >= a
        with np.errstate(invalid="ignore", divide="ignore"):
            F[key + "_pos"] = np.where(ok, (C - take(rl, j)) / (take(rh, j) - take(rl, j)), np.nan)
    grid = np.full(len(T), np.nan)
    okp = pdc > 0
    for i in np.flatnonzero(okp):
        grid[i] = NICE[np.argmin(np.abs(np.log(NICE) - np.log(0.005 * pdc[i])))]
    with np.errstate(invalid="ignore"):
        q = C / grid
        F["rn"] = np.where(okp, np.abs(C - np.round(q) * grid) / (grid / 2.0), np.nan)
    ph, pl = pivots(H, L, 3)
    if mutant == "pivot_unconfirmed":                  # a pivot known at its own bar
        ph = np.r_[ph[3:], np.full(3, np.nan)]; pl = np.r_[pl[3:], np.full(3, np.nan)]
    with np.errstate(invalid="ignore"):
        F["bos_up"] = C > ph; F["bos_dn"] = C < pl
    for kk, htf in enumerate(htf_up):
        hb = bars(tm, o, h, l, c, v, TFM[htf])
        mac = ema(hb["C"], 12) - ema(hb["C"], 26); mac[:60] = np.nan
        k = htf_idx(hb["T"], TFM[htf], close, mutant)
        with np.errstate(invalid="ignore"):
            F[f"hm{kk + 1}"] = np.nan_to_num(take(np.sign(mac), k)).astype(np.int8)
    V = t["V"]
    mv = np.full(len(V), np.nan)
    csv = np.r_[0.0, np.cumsum(V)]
    for i in range(20, len(V)):
        mv[i] = (csv[i] - csv[i - 20]) / 20.0          # bars i-20 .. i-1
    with np.errstate(invalid="ignore", divide="ignore"):
        F["volr"] = V / mv
    F["body_dir"] = np.sign(C - O).astype(np.int8)
    with np.errstate(invalid="ignore", divide="ignore"):
        F["body_frac"] = np.where(H > L, np.abs(C - O) / (H - L), np.nan)
        F["rng_atr"] = (H - L) / atr
    sm = stoch_main(H, L, C, 7); ss = sma_strict(sm, 7)
    hi5 = roll_ext_strict(sm, 5, True); lo5 = roll_ext_strict(sm, 5, False)
    with np.errstate(invalid="ignore"):
        F["xs_dn"] = (hi5 >= 80) & ((sm < ss) | (sm < 80))
        F["xs_up"] = (lo5 <= 20) & ((sm > ss) | (sm > 20))
    if mutant == "shift_forward":
        for k2 in list(F):
            a = F[k2]
            F[k2] = np.r_[a[1:], np.array([np.nan if a.dtype.kind == "f" else 0], dtype=a.dtype)]
    t["F"] = F
    return t
