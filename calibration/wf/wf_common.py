"""Frozen definitions of the BTC walk-forward direction study (see PREREG.md). Do not edit after the freeze commit."""
import numpy as np
import pandas as pd
import fgrun as R

# MT5 native intervals in minutes (M1..M4, M6 and M12 cannot be multiples of a 5m+ filter timeframe that we use)
NATIVE = [5, 10, 15, 20, 30, 60, 120, 180, 240, 360, 480, 720, 1440, 10080]
FILTER_TFS = [5, 15, 30, 60, 120, 240, 480, 1440]
NAMES = {5: "M5", 10: "M10", 15: "M15", 20: "M20", 30: "M30", 60: "H1", 120: "H2", 180: "H3", 240: "H4", 360: "H6",
         480: "H8", 720: "H12", 1440: "D1", 10080: "W1", 40: "40m(TV)", 960: "16H(TV)", 1920: "32H=D1(TV)", 2880: "2D(TV)", 5760: "4D(TV)"}
HS = (1, 3, 10)
BAND = 0.25
MAX_RATIO = 24

# native "x1/x2/x4" default: each multiple snapped to the nearest (log distance, ties -> lower) native interval that
# is a whole multiple of the filter timeframe, duplicates dropped; minimum aligned 2; parent = filter timeframe
NATIVE_DEFAULT = {5: (5, 10, 20), 15: (15, 30, 60), 30: (30, 60, 120), 60: (60, 120, 240), 120: (120, 240, 480),
                  240: (240, 480, 720), 480: (480, 1440), 1440: (1440, 10080)}


def mults(tf):
    """native intervals usable as parent / child zone of filter timeframe tf: whole multiples, ratio 1..24"""
    return [n for n in NATIVE if n % tf == 0 and n // tf <= MAX_RATIO]


def snap(tf, m):
    c = mults(tf)
    d = [abs(np.log(x / (tf * m))) for x in c]
    best = min(d)
    return [x for x, e in zip(c, d) if abs(e - best) < 1e-12][0]


def candidates(tf):
    """the frozen grid: parent in mults(tf); child-zone sets = every subset of mults(tf) of size 1..3; minimum aligned
    1..size; plus zones off (parent unused). Returns a DataFrame with cid, parent, zones (tuple), ma, use_zones."""
    from itertools import combinations
    M = mults(tf)
    rows = []
    for par in M:
        for k in (1, 2, 3):
            for zs in combinations(M, k):
                for ma in range(1, k + 1):
                    rows.append(dict(parent=par, zones=zs, ma=ma, use_zones=True, kind="grid"))
    rows.append(dict(parent=tf, zones=(tf,), ma=1, use_zones=False, kind="grid"))
    return rows


def baselines(tf):
    """baselines outside or inside the grid, scored on identical horizons"""
    b = [dict(parent=tf, zones=NATIVE_DEFAULT[tf], ma=2, use_zones=True, kind="native_default"),
         dict(parent=tf, zones=(tf, 2 * tf, 4 * tf), ma=2, use_zones=True, kind="tv_default_x124"),
         dict(parent=60, zones=(60, 120, 240), ma=2, use_zones=True, kind="input_default_H1_H1H2H4"),
         dict(parent=tf, zones=(tf,), ma=1, use_zones=False, kind="zones_off")]
    return b


def label(r):
    if not r["use_zones"]:
        return "zones off"
    return f"P {NAMES.get(r['parent'], r['parent'])} | Z " + "/".join(NAMES.get(z, str(z)) for z in r["zones"]) + f" | min {r['ma']}"


class WSource(R.Source):
    """R.Source plus MT5-style weekly bars (Sunday 00:00 of the data clock)."""

    def bars(self, tf_req):
        if tf_req == 10080 and 10080 not in self._bars:
            t = self.base.index.as_unit("s").asi8.astype(np.int64)
            start = t - ((t - 259200) % 604800)       # 1970-01-04 00:00 was a Sunday
            agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
            b = self.base.groupby(start).agg(agg).dropna()
            t_open = b.index.to_numpy().astype(np.int64)
            d = dict(t_open=t_open, t_close=t_open + 604800, o=b["open"].to_numpy(np.float64),
                     h=b["high"].to_numpy(np.float64), l=b["low"].to_numpy(np.float64),
                     c=b["close"].to_numpy(np.float64), tf=10080, n=len(b))
            self._bars[10080] = d
            return d
        return super().bars(tf_req)


def server_clock(df):
    """UTC 1m frame re-stamped to the common MT5 'New York close' server clock (UTC+2 winter / UTC+3 summer, with US
    DST): server time = New York local time + 7h. The repeated hour at the autumn change is dropped (first kept)."""
    ny = df.index.tz_convert("America/New_York")
    srv = ny.tz_localize(None) + pd.Timedelta(hours=7)
    out = df.copy()
    out.index = pd.DatetimeIndex(srv).tz_localize("UTC")
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def load_broker(path):
    """MT5 broker M5 candles (epoch seconds = broker server clock) as a 5-minute base; kept outside the repository"""
    d = pd.read_csv(path)
    d.index = pd.to_datetime(d["time"], unit="s", utc=True)
    d = d[["open", "high", "low", "close"]].astype("float64")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return WSource(d, 5)


def load(clock="utc", path="btc_1m_long.parquet"):
    df = pd.read_parquet(path)
    if clock == "server":
        df = server_clock(df)
    return WSource(df, 1)


def held(c, atr, buy, sell, bpx, spx):
    """level, band unit (ATR at the signal) and side of the last signal, per candle (as dir_auc.held)"""
    N = len(c)
    L = np.full(N, np.nan); A = np.full(N, np.nan); D = np.zeros(N, np.int8)
    idx = np.where(buy | sell)[0]
    if len(idx) == 0:
        return L, A, D
    lv = np.where(buy[idx], bpx[idx], spx[idx])
    lv = np.where(np.isnan(lv), c[idx], lv)
    pos = np.searchsorted(idx, np.arange(N), side="right") - 1
    ok = pos >= 0
    L[ok] = lv[pos[ok]]; A[ok] = atr[idx][pos[ok]]; D[ok] = np.where(buy[idx], 1, -1)[pos[ok]]
    return L, A, D


# Bug fix 1 (after the freeze, reported by the MT5 port's audit): the v1.2 indicator (Pine and MT5) rounds the zone
# edges OUTWARD to the tick grid and needs the price to clear the rounded edge by more than half a tick. The frozen
# code compared close with level +- band directly. EXACT_TICK = 0.01 (BTCUSD point) applies the indicator's rule;
# None restores the frozen comparison (kept for the before / after count).
EXACT_TICK = 0.01


def zone_edges(c, L, b, exact_tick=None):
    """+1 BUY ZONE / -1 SELL ZONE / 0 NO TRADE from close c, level L and band b (b = 0.25 x ATR of the signal)"""
    if exact_tick:
        mt = exact_tick
        with np.errstate(invalid="ignore"):
            up = np.where(b > 0, np.ceil((L + b) / mt - 1e-9) * mt, L)
            dn = np.where(b > 0, np.floor((L - b) / mt + 1e-9) * mt, L)
            inup = np.where(b > 0, c > up + mt / 2, c > L)
            indn = np.where(b > 0, c < dn - mt / 2, c < L)
    else:
        with np.errstate(invalid="ignore"):
            inup = c > L + b
            indn = c < L - b
    z = np.where(inup, 1, np.where(indn, -1, 0)).astype(np.int8)
    z[np.isnan(L)] = 0
    return z


READS = {
    # primary - the MT5 port's reads: parent = last parent bar closed by the filter candle's CLOSE; higher child zones =
    # last child bar closed by the filter candle's OPEN; child zones equal to / lower than the filter TF: closed by close
    "mt5": dict(parent_no_repaint=False, htf_no_repaint=True),
    # the earlier calibration: parent and higher child zones both from the bar closed by the filter candle's open
    "closed_prev": dict(parent_no_repaint=True, htf_no_repaint=True),
    # everything from the last bar closed by the filter candle's close
    "closed_at_close": dict(parent_no_repaint=False, htf_no_repaint=False),
}


def zone_of(S, tf, r, read="mt5"):
    """the filter's zone (+1 BUY ZONE, -1 SELL ZONE, 0 NO TRADE) and the graded distance (close - level) / ATR_signal
    at each closed filter candle, with the higher-timeframe reads of READS[read]."""
    zl = list(r["zones"]) + [tf] * (6 - len(r["zones"]))
    zones = tuple((i < len(r["zones"]), z) for i, z in enumerate(zl))
    p = R.params(parent_tf=r["parent"], zones=zones, min_aligned=r["ma"], use_zones=r["use_zones"], burst_atr=0.5,
                 fd_tf=tf, **READS[read])
    ctx = R.context(S, tf, p)
    ch = ctx["ch"]; c = ch["c"]
    L, A, D = held(c, ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
    z = zone_edges(c, L, BAND * np.nan_to_num(A), exact_tick=EXACT_TICK)
    g = (c - L) / A
    g = np.clip(np.where(np.isfinite(g), g, 0.0), -5, 5)
    return z, g, ctx


def month_id(t):
    d = pd.to_datetime(t, unit="s", utc=True)
    return (d.year * 12 + d.month - 1).to_numpy().astype(np.int64)


def mid_name(m):
    return f"{m // 12}-{m % 12 + 1:02d}"


def auc_table(nu, nd):
    """AUC of a 3-valued score from counts: nu / nd = (count at -1, 0, +1) of up / down labels; ties counted half"""
    nu = np.asarray(nu, float); nd = np.asarray(nd, float)
    NU = nu.sum(-1); ND = nd.sum(-1)
    gt = nu[..., 1] * nd[..., 0] + nu[..., 2] * (nd[..., 0] + nd[..., 1])
    tie = (nu * nd).sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where((NU > 0) & (ND > 0), (gt + 0.5 * tie) / (NU * ND), np.nan)


def perm_metrics(nu, nd):
    """permission metrics from counts (index 0 = SELL ZONE, 1 = NO TRADE, 2 = BUY ZONE)"""
    nu = np.asarray(nu, float); nd = np.asarray(nd, float)
    buy = nu[2] + nd[2]; sell = nu[0] + nd[0]; allc = nu.sum() + nd.sum()
    hit_b = nu[2] / buy if buy else np.nan
    hit_s = nd[0] / sell if sell else np.nan
    upz = nu[0] + nu[2]; dnz = nd[0] + nd[2]           # up / down labels on candles with a zone
    rec_u = nu[2] / upz if upz else np.nan                # P(BUY | up, zone != 0)
    rec_d = nd[0] / dnz if dnz else np.nan                # P(SELL | down, zone != 0)
    with np.errstate(invalid="ignore"):
        return dict(auc=float(auc_table(nu, nd)), acc=(nu[2] + nd[0]) / (buy + sell) if buy + sell else np.nan,
                # 'bal_acc' = the PREREG's "balanced accuracy" = direction-balanced PRECISION (mean of P(up | BUY),
                # P(down | SELL)); 'bal_recall' = mean class recall on candles with a zone (the MT5 study's balanced_accuracy)
                bal_acc=np.nanmean([hit_b, hit_s]), bal_recall=np.nanmean([rec_u, rec_d]), p_up_buy=hit_b, p_dn_sell=hit_s,
                up_rate=nu.sum() / allc if allc else np.nan, coverage=(buy + sell) / allc if allc else np.nan,
                n_up=int(nu.sum()), n_down=int(nd.sum()), n_buy=int(buy), n_sell=int(sell), n_none=int(nu[1] + nd[1]))


def rank_auc(s, y):
    """ROC-AUC of a continuous score (ties counted half)"""
    s = np.asarray(s, float); y = np.asarray(y).astype(bool)
    n1 = y.sum(); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = pd.Series(s).rank(method="average").to_numpy()
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
