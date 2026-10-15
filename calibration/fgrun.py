"""Driver: build the chart context of flashgold_v5_fdf_strategy.pine for one timeframe and run it."""
import numpy as np
import pandas as pd
import fgengine as E

DEFAULTS = dict(
    # core
    spread_pts=25.0, entry_dist_pts=50.0, hold_bars=0, hold_fav_pts=5.0, one_per_bar=True,
    atr_unit=True, burst_atr=0.5, entry_dist_atr=0.25, hold_fav_atr=0.1, burst_pts_in=172.0,
    use_burst=True, any_combo=False, drift_bars=60, use_drift=False,
    # zones
    use_zones=True, parent_tf=60, rsi_len=14, fast_len=2, slow_len=7, min_aligned=2,
    flat_parent=False, ignore_na=True, htf_no_repaint=True, parent_no_repaint=True,
    zones=((True, 60), (True, 120), (True, 240), (False, 480), (False, 1), (False, 2)),
    # strategy
    direction=0, entry_valid=3, allow_rev=True, exit_opp=False,
    exit_mode="Points", sl_pts=5000.0, tp_pts=50000.0, atr_len=14, sl_atr=2.0, tp_r=2.0,
    use_trail=True, trail_act_pts=4500.0, trail_pts=1000.0, trail_act_atr=4.0, trail_dst_atr=0.2,
    max_bars_held=0,
    # framework
    fd_on=True, fd_tf=60, fd_piv_l=5, fd_piv_r=3, fd_trade=True, fd_exit_break=True,
    fd_div_on=True, fd_div_bars=10, fd_pull_on=True, fd_pull_atr=0.5,
    fd_hurst_on=True, fd_hurst_min=0.5, fd_hurst_win=128, fd_width_on=False, fd_width_max=0.5,
    # re-entry (new) / costs
    re_mode=0, re_max=0, re_dist_atr=0.0, re_need_signal_side=True,
    slip_ticks=0.0, fee_pct=0.0, use_mag=False,
)


def tv_tf(m):
    """A timeframe in minutes as the Pine presets request it: up to a day as is, above a day the nearest whole
    number of days (TradingView has no intraday interval above 1440 minutes)."""
    m = int(m)
    return m if m <= 1440 else int(round(m / 1440.0)) * 1440


class Source:
    """Bars per timeframe, resampled from a base frame (1m data or a TradingView export)."""

    def __init__(self, base, base_tf):
        self.base = base
        self.base_tf = base_tf
        self._bars = {}
        self._tdi = {}
        self._fdf = {}
        self._hurst = {}
        self._atr = {}

    def bars(self, tf_req):
        """Bars of a timeframe as TradingView builds them on a 24/7 symbol: an intraday interval that does not
        divide the day restarts at 00:00 UTC (the day's last bar is shorter); above a day the interval is a
        whole number of days (tv_tf)."""
        if tf_req in self._bars:
            return self._bars[tf_req]
        tf = tv_tf(tf_req)
        if tf in self._bars:
            self._bars[tf_req] = self._bars[tf]
            return self._bars[tf]
        agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
        if tf == self.base_tf:
            b = self.base
            t_open = b.index.as_unit("s").asi8.astype(np.int64)
            t_close = t_open + tf * 60
        elif tf < 1440 and 1440 % tf != 0:
            t = self.base.index.as_unit("s").asi8.astype(np.int64)
            day = t - t % 86400
            start = day + ((t - day) // (tf * 60)) * (tf * 60)
            b = self.base.groupby(start).agg(agg).dropna()
            t_open = b.index.to_numpy().astype(np.int64)
            t_close = np.minimum(t_open + tf * 60, t_open - t_open % 86400 + 86400)
        else:
            assert tf % self.base_tf == 0, (tf, self.base_tf)
            rule = "1D" if tf == 1440 else f"{tf}min"
            b = self.base.resample(rule, label="left", closed="left").agg(agg).dropna()
            t_open = b.index.as_unit("s").asi8.astype(np.int64)
            t_close = t_open + tf * 60
        d = dict(t_open=t_open, t_close=t_close,
                 o=b["open"].to_numpy(np.float64), h=b["high"].to_numpy(np.float64),
                 l=b["low"].to_numpy(np.float64), c=b["close"].to_numpy(np.float64), tf=tf, n=len(b))
        self._bars[tf] = d
        self._bars[tf_req] = d
        return d

    def tdi(self, tf, rsi_len, fast_len):
        key = (tf, rsi_len, fast_len)
        if key not in self._tdi:
            self._tdi[key] = E.tdi_dir(self.bars(tf)["c"], rsi_len, fast_len)
        return self._tdi[key]

    def atr(self, tf, n):
        key = (tf, n)
        if key not in self._atr:
            b = self.bars(tf)
            self._atr[key] = E.atr_pine(b["h"], b["l"], b["c"], n)
        return self._atr[key]

    def fdf(self, tf, piv_l, piv_r, div_bars, rsi_len, fast_len):
        key = (tf, piv_l, piv_r, div_bars, rsi_len, fast_len)
        if key not in self._fdf:
            b = self.bars(tf)
            ph, pl = E.pivots(b["h"], b["l"], piv_l, piv_r)
            mom = self.tdi(tf, rsi_len, fast_len)[1]
            lo_piv = E.lowest_pine(b["l"], piv_r + 1)
            hi_piv = E.highest_pine(b["h"], piv_r + 1)
            self._fdf[key] = E.fdf_structure(b["h"], b["l"], b["c"], mom, ph, pl, lo_piv, hi_piv, piv_r, div_bars)
        return self._fdf[key]

    def hurst(self, tf, win):
        key = (tf, win)
        if key not in self._hurst:
            self._hurst[key] = E.hurst_pine(self.bars(tf)["c"], win)
        return self._hurst[key]


def parent_index(S, tf, p):
    par = S.bars(p["parent_tf"])
    ch = S.bars(tf)
    higher = tv_tf(p["parent_tf"]) > tv_tf(tf)
    return _map(par, ch, p.get("parent_no_repaint", True) and higher)


def _map(src, ctx, higher_prev):
    return E.map_prev_on(src, ctx) if higher_prev else E.map_off(src, ctx)


def context(S, tf, p):
    """All per-bar series the strategy needs on chart timeframe tf (minutes)."""
    ch = S.bars(tf)
    N = ch["n"]
    pt = E.PT
    # parent (lookahead_off always)
    # parent: last CLOSED parent bar when it is higher than the chart (no repaint), else the plain read
    pdir = E.take(S.tdi(p["parent_tf"], p["rsi_len"], p["fast_len"])[0], parent_index(S, tf, p), E.NA)
    # zones
    zdir = np.full((6, N), E.NA, np.int64)
    zuse = np.zeros(6, np.bool_)
    for z, (use, ztf) in enumerate(p["zones"]):
        zuse[z] = use
        if not use:
            continue
        zb = S.bars(ztf)
        idx = _map(zb, ch, p["htf_no_repaint"] and tv_tf(ztf) > tv_tf(tf))
        zdir[z] = E.take(S.tdi(ztf, p["rsi_len"], p["fast_len"])[0], idx, E.NA)
    atr14 = S.atr(tf, 14)
    buy, sell, bpx, spx, zbuy, zsell, pside = E.flashgold_signal(
        ch["c"], atr14, pdir, zdir, zuse, pt, p["spread_pts"], p["entry_dist_pts"], p["hold_bars"],
        p["hold_fav_pts"], p["one_per_bar"], p["atr_unit"], p["burst_atr"], p["entry_dist_atr"],
        p["hold_fav_atr"], p["burst_pts_in"], p["use_burst"], p["any_combo"], p["drift_bars"],
        p["use_drift"], p["use_zones"], p["min_aligned"], p["flat_parent"], p["ignore_na"])
    # framework
    fb = S.bars(p["fd_tf"])
    fidx = _map(fb, ch, tv_tf(p["fd_tf"]) > tv_tf(tf))
    fdir_s, fpl_s, fph_s, fwu_s, fwd_s = S.fdf(p["fd_tf"], p["fd_piv_l"], p["fd_piv_r"], p["fd_div_bars"], p["rsi_len"], p["fast_len"])
    fdir = E.take(fdir_s, fidx, 0)
    fpl = E.take(fpl_s, fidx, np.nan)
    fph = E.take(fph_s, fidx, np.nan)
    fwu = E.take(fwu_s, fidx, False)
    fwd = E.take(fwd_s, fidx, False)
    h2_s, w_s = S.hurst(p["fd_tf"], p["fd_hurst_win"])
    fh = E.take(h2_s, fidx, np.nan)
    fw = E.take(w_s, fidx, np.nan)
    fprev = np.concatenate(([0], fdir[:-1]))
    flip_up = (fdir == 1) & (fprev == -1)
    flip_dn = (fdir == -1) & (fprev == 1)
    depth = E.fdf_pullback(ch["h"], ch["l"], ch["c"], fdir)
    pull_ok = depth >= p["fd_pull_atr"] * atr14          # false when atr is nan
    hurst_ok = (not p["fd_hurst_on"]) | (~np.isnan(fh) & (fh >= p["fd_hurst_min"]))
    width_ok = (not p["fd_width_on"]) | (~np.isnan(fw) & (fw <= p["fd_width_max"]))
    common = ((not p["fd_pull_on"]) | pull_ok) & hurst_ok & width_ok
    fd_buy_ok = (not p["fd_on"]) | (((not p["fd_trade"]) | (fdir == 1)) & ((not p["fd_div_on"]) | ~fwu) & common)
    fd_sell_ok = (not p["fd_on"]) | (((not p["fd_trade"]) | (fdir == -1)) & ((not p["fd_div_on"]) | ~fwd) & common)
    sl_t, tp_t, act_t, dst_t = exit_geometry(S, tf, p, atr14)
    return dict(ch=ch, N=N, buy=buy, sell=sell, bpx=bpx, spx=spx, zbuy=zbuy, zsell=zsell, pside=pside,
                pdir=pdir, zdir=zdir, fdir=fdir, fpl=fpl, fph=fph, fwu=fwu, fwd=fwd, fh=fh, fw=fw,
                flip_up=flip_up, flip_dn=flip_dn, depth=depth, pull_ok=pull_ok, fd_buy_ok=fd_buy_ok,
                fd_sell_ok=fd_sell_ok, sl_t=sl_t, tp_t=tp_t, act_t=act_t, dst_t=dst_t, atr14=atr14)


def exit_geometry(S, tf, p, atr14):
    """sl / tp / trail activation / trail distance per bar, in ticks, as the Pine strategy computes them."""
    N = len(atr14)
    pt = E.PT
    if p["exit_mode"] == "Points":
        return (np.full(N, p["sl_pts"]), np.full(N, p["tp_pts"]), np.full(N, p["trail_act_pts"]), np.full(N, p["trail_pts"]))
    atr_pts = atr14 / pt
    atrv = S.atr(tf, p["atr_len"])
    sl_t = p["sl_atr"] * atrv / pt
    return sl_t, sl_t * p["tp_r"], p["trail_act_atr"] * atr_pts, np.maximum(p["trail_dst_atr"] * atr_pts, 1.0)


def run(S, tf, p, ctx=None, mag=None):
    """Simulate; returns a trades DataFrame. The exit geometry is taken from p (not from the context)."""
    if ctx is None:
        ctx = context(S, tf, p)
    ch = ctx["ch"]
    N = ctx["N"]
    sl_t, tp_t, act_t, dst_t = exit_geometry(S, tf, p, ctx["atr14"])
    use_mag = bool(p["use_mag"]) and mag is not None
    if use_mag:
        m = mag
        m_start = np.searchsorted(m["t_open"], ch["t_open"], side="left")
        m_end = np.searchsorted(m["t_open"], ch["t_close"], side="left")
        m_o, m_h, m_l, m_c = m["o"], m["h"], m["l"], m["c"]
    else:
        m_start = np.zeros(N, np.int64); m_end = np.ones(N, np.int64)
        m_o = m_h = m_l = m_c = np.zeros(1)
    allow_l = p["direction"] != -1
    allow_s = p["direction"] != 1
    re_dist = p["re_dist_atr"] * ctx["atr14"]
    re_dist = np.where(np.isnan(re_dist), 0.0, re_dist)
    if "re_ok_l" in ctx:
        re_ok_l = ctx["re_ok_l"]
        re_ok_s = ctx["re_ok_s"]
    elif p["re_need_signal_side"]:
        re_ok_l = ctx["fd_buy_ok"] & ctx["zbuy"]
        re_ok_s = ctx["fd_sell_ok"] & ctx["zsell"]
    else:
        re_ok_l = ctx["fd_buy_ok"]
        re_ok_s = ctx["fd_sell_ok"]
    out = E.simulate(ch["t_open"], ch["o"], ch["h"], ch["l"], ch["c"], m_o, m_h, m_l, m_c, m_start, m_end, use_mag,
                     ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"], ctx["fd_buy_ok"], ctx["fd_sell_ok"],
                     ctx["flip_up"], ctx["flip_dn"], p["fd_on"], p["fd_exit_break"],
                     sl_t, tp_t, act_t, dst_t, p["use_trail"], p["entry_valid"],
                     p["allow_rev"], p["exit_opp"], allow_l, allow_s, p["max_bars_held"],
                     p["re_mode"], p["re_max"], re_ok_l, re_ok_s, re_dist, E.PT, p["slip_ticks"], p["fee_pct"])
    t_dir, t_eb, t_ep, t_xb, t_xp, t_rs, t_pnl, t_re = out
    return pd.DataFrame(dict(dir=t_dir, ebar=t_eb, epx=t_ep, xbar=t_xb, xpx=t_xp, reason=t_rs, pnl=t_pnl, reentry=t_re,
                             etime=pd.to_datetime(ch["t_open"][t_eb], unit="s", utc=True),
                             xtime=pd.to_datetime(ch["t_open"][t_xb], unit="s", utc=True)))


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p
