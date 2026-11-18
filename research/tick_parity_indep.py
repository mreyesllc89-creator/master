#!/usr/bin/env python3
"""
Independent parity check: hump_tick.simulate_tick against the EA's own code (XAUUSD_Loma_TrendPullback.mq5 v1.35) on real
ticks with the constant VT spread, for setups that the builder's tick_parity.py did not run.

Independent of tick_data.py and tick_parity.py (neither is imported):
  quotes   own readers of the raw tick files (ticks/gold/XAUUSD_<YYYY-MM>.npz, ticks/btc/BTCUSDT_<YYYY-MM>.npz), own server
           clock (New York + 7 h; the second pass of a repeated server hour dropped), own constant-spread quotes:
             gold  bid = Dukascopy mid - 0.075 rounded half up to the cent in integer arithmetic, ask = bid + 0.15
             BTC   four points per second (open, the extreme nearer to the open (a tie: the low), the other extreme,
                   close), bid = price - 5, ask = price + 5; Binance's empty leading seconds of a minute removed by an own
                   implementation of the rule (the study's one-minute open differs from the previous close: the leading
                   flat seconds at that close are no trades), and the resulting bars asserted equal to the study's bars
  bars     the terminal gets the bid bars of the very same ticks (spread field = the constant spread in points); Python
           gets the mid bars (bid bars + half the spread) and the same ticks: K.tick_stream (gold) / K.second_stream (BTC),
           whose quotes are asserted equal to the ticks fed to the terminal
  inputs   the EA gets the shipped presets' mapping (make_v135_presets.ea_inputs, so a fixed-RR setup with min_rr = tp_rr
           gets MinRewardRisk = TP_RR - 0.05) plus HumpWarmupBars 1,000,000 (hump state from the first bar, as Python);
           Python gets tick_replay.engine_cfg(params, {}) (the replay's own settings) and tick_replay's EA execution
           settings for the 0.01 grid (TrailStep 0.10 gold / 2.00 BTC, point and tick 0.01, plan checks, fills at the tick)
  terminal <scratch>/tick/parity/indep/ea: v135.cpp translated from the EA by mq2rt.py (identical to the builder's), the
           builder's shim (the v1.35 shim plus fill_at_tick, read line by line), drv_px = the builder's drv_tick.cpp plus a
           log of every trade request
  compare  every trade matched by entry second and side: entry price, initial stop, target, exit second, exit price,
           exit reason, R, number of stop moves, last stop

Usage (from research/, env NUMBA_CACHE_DIR, PYTHONDONTWRITEBYTECODE=1):
  HUMP_SYMBOL=XAUUSD|BTCUSD python3 tick_parity_indep.py <out_dir> <series_start> <first_tick> <end> <setups> <modes>
      setups: 'auto:<n>[+key,key]' n per EA trailing system (not used by the builder, other timeframes first) plus extra
              keys, or a list of keys
      modes : clean,full,wk,wkHHMM (clean: no time exits and no weekend close on either side; full: the presets' time
              exits and Friday close; wk: gold, only the Friday close at 23:00; wkHHMM: only the Friday close at HH:MM)
  Every setup is compared twice where it matters: 'replay' = Python with tick_replay.engine_cfg as is; 'preset_rr' (only
  for fixed-RR picks with min_rr = tp_rr) = Python with min_rr = tp_rr - 0.05, the presets' MinRewardRisk rule.
  Output: <out_dir>/<sym>_<window>_indep.json (every differing trade with both sides' values), the EA's trades, journal
  and request log per run.
"""
import json, os, struct, subprocess, sys, time
import numpy as np, pandas as pd

os.environ.setdefault("HUMP_SPACE", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H
import hump_trail2 as T2
import hump_tick as K
import tick_replay as TR
import make_v135_presets as MP

SYM = H.SYMBOL
BTC = SYM == "BTCUSD"
SP = os.environ.get("LOMA_SCRATCH", "/tmp/claude-0/-workspace-master/53e0ea5b-b347-50b9-8f48-3f5cae086c17/scratchpad")   # LOMA_SCRATCH: the scratch folder of the data
TICKS = os.path.join(SP, "ticks")
EA_DIR = os.path.join(SP, "tick", "parity", "indep", "ea")
PICKS = os.path.join(SP, "tick", "replay", f"{SYM.lower()}_picks.json")
USED = os.path.join(SP, "tick", "parity", "indep", "builder_used.txt")
HALF_C = 500 if BTC else 7.5          # half spread in cents
SPREAD_PTS = 1000 if BTC else 15      # MqlRates.spread of every bar (points of 0.01)
HALF = HALF_C / 100.0
EA_MODE = dict(R=0, atr=1, percent=2, profitlock=3, step=4, chandelier=5, candles=6, ema=7, sma=8, psar=9, bollinger=10,
               htfcandle=11, pivots=12, hump=13)


# ----------------------------------------------------------------------------- server clock (own implementation)
def _nth_sunday(y, m, n):
    d = pd.Timestamp(year=y, month=m, day=1)
    first = d + pd.Timedelta(days=(6 - d.dayofweek) % 7)
    return first + pd.Timedelta(days=7 * (n - 1))


def server_offset_s(t_utc_s):
    """Seconds to add to UTC: 3 h while New York is on summer time (from 2nd Sunday of March 02:00 EST = 07:00 UTC to
    1st Sunday of November 02:00 EDT = 06:00 UTC), else 2 h."""
    t = np.asarray(t_utc_s, np.int64)
    off = np.full(len(t), 7200, np.int64)
    y0 = pd.Timestamp(int(t.min()), unit="s").year if len(t) else 2024
    y1 = pd.Timestamp(int(t.max()), unit="s").year if len(t) else 2024
    for y in range(y0, y1 + 1):
        a = int((_nth_sunday(y, 3, 2) + pd.Timedelta(hours=7)).value // 10 ** 9)
        b = int((_nth_sunday(y, 11, 1) + pd.Timedelta(hours=6)).value // 10 ** 9)
        off[(t >= a) & (t < b)] = 10800
    return off


def _months(a, b):
    a = pd.Timestamp(a) - pd.Timedelta(days=1); b = pd.Timestamp(b) + pd.Timedelta(days=1)
    out = []
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append(f"{y}-{m:02d}"); y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _s(x):
    return int(pd.Timestamp(x).value // 10 ** 9)


# ----------------------------------------------------------------------------- quotes and bars
class Window:
    """Ticks (server ms, bid, ask), bid bars for the terminal, mid bars and a K stream for Python, [start, end)."""

    def __init__(self, out_dir, start, first_tick, end):
        os.makedirs(out_dir, exist_ok=True)
        self.tag = f"{SYM}_{pd.Timestamp(start):%Y%m%d}_{pd.Timestamp(first_tick):%Y%m%d}_{pd.Timestamp(end):%Y%m%d}"
        a_s, b_s, f_s = _s(start), _s(end), _s(first_tick)
        t0 = time.time()
        if BTC:
            self._btc(a_s, b_s)
        else:
            self._gold(a_s, b_s)
        idx = pd.to_datetime(self.minute * 60, unit="s")
        cols = ("open", "high", "low", "close")
        if BTC:                                       # bid = price / 100 - 5: the terminal's bars with the feed's arithmetic
            self.bid_bars = pd.DataFrame({k: self.mid_c[k] / 100.0 - HALF for k in cols}, index=idx)
            self.mid = pd.DataFrame({k: self.mid_c[k] / 100.0 for k in cols}, index=idx)
        else:                                         # bid in whole cents; mid = bid + 0.075
            self.bid_bars = pd.DataFrame({k: self.bid_bar_c[k] / 100.0 for k in cols}, index=idx)
            self.mid = pd.DataFrame({k: (self.bid_bar_c[k] + HALF_C) / 100.0 for k in cols}, index=idx)
        self.init_row = int(np.searchsorted(self.minute * 60, f_s))
        assert self.minute[self.init_row] * 60 >= f_s
        self.init_s = int(self.minute[self.init_row] * 60)
        self.q_init = int(self.rq0[self.init_row])
        self._check_feed()
        self.m1_bin = os.path.join(out_dir, self.tag + "_m1.bin")
        self.tick_bin = os.path.join(out_dir, self.tag + "_ticks.bin")
        rec = np.zeros(len(self.bid_bars), dtype=[("t", "<i8"), ("o", "<f8"), ("h", "<f8"), ("l", "<f8"), ("c", "<f8"), ("s", "<i4"), ("p", "<i4")])
        rec["t"] = self.minute * 60
        for k, c in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close")):
            rec[k] = self.bid_bars[c].values
        rec["s"] = SPREAD_PTS
        with open(self.m1_bin, "wb") as f:
            f.write(struct.pack("<q", len(rec))); f.write(rec.tobytes())
        tq_ms, tq_b, tq_a = self.feed()
        rec = np.zeros(len(tq_ms), dtype=[("t", "<i8"), ("b", "<f8"), ("a", "<f8")])
        rec["t"] = tq_ms; rec["b"] = tq_b; rec["a"] = tq_a
        with open(self.tick_bin, "wb") as f:
            f.write(struct.pack("<q", len(rec))); f.write(rec.tobytes())
        self.n_feed = len(rec)
        del rec, tq_ms, tq_b, tq_a
        self.mk = T2.MarketY(m1=self.mid, half_spread=np.full(len(self.mid), HALF))
        print(f"{SYM} window {self.mid.index[0]} .. {self.mid.index[-1]}: {len(self.mid):,} bars; {self.n_feed:,} ticks fed from "
              f"{pd.to_datetime(self.init_s, unit='s')} (OnInit, row {self.init_row}) ({time.time() - t0:.0f}s)", flush=True)

    # ---- gold
    def _gold(self, a_s, b_s):
        ts, bs, as_ = [], [], []
        for ym in _months(pd.to_datetime(a_s, unit="s"), pd.to_datetime(b_s, unit="s")):
            fn = os.path.join(TICKS, "gold", f"XAUUSD_{ym}.npz")
            if not os.path.exists(fn):
                continue
            d = np.load(fn)
            t = d["t"].astype(np.int64)
            srv = t + server_offset_s(t // 1000) * 1000
            ts.append(srv); bs.append(d["bid"].astype(np.int64)); as_.append(d["ask"].astype(np.int64))
        srv = np.concatenate(ts); bid = np.concatenate(bs); ask = np.concatenate(as_)
        del ts, bs, as_
        assert np.all(np.diff(srv) >= -3600 * 1000), "files out of order"
        run = np.maximum.accumulate(srv)
        keep = np.r_[True, srv[1:] >= run[:-1]]                 # repeated server hour: keep the first pass
        self.dropped_repeat = int((~keep).sum())
        keep &= (srv >= a_s * 1000) & (srv < b_s * 1000)
        srv, bid, ask = srv[keep], bid[keep], ask[keep]
        assert np.all(np.diff(srv) >= 0)
        s2 = bid + ask                                          # 2 x mid x 1000 (exact)
        bc = np.floor_divide(s2 - 140, 20)                      # (mid - 0.075) x 100 rounded half up, in cents
        self.t_ms = srv
        self.bid_c = bc.astype(np.int64)
        self.ask_c = self.bid_c + 15
        mins = srv // 60000
        st = np.r_[0, np.where(np.diff(mins) != 0)[0] + 1].astype(np.int64)
        en = np.r_[st[1:], len(srv)].astype(np.int64)
        self.minute = mins[st]
        self.rq0, self.rq1 = st, en
        self.bid_bar_c = dict(open=self.bid_c[st], high=np.maximum.reduceat(self.bid_c, st), low=np.minimum.reduceat(self.bid_c, st),
                              close=self.bid_c[en - 1])
        self.bid = self.bid_c / 100.0
        self.ask = self.ask_c / 100.0
        self.stream = K.tick_stream(self.t_ms, self.bid, self.ask, st, en, sell_best="bid_low_min_spread")

    # ---- BTC
    def _btc(self, a_s, b_s):
        ts, cols = [], {k: [] for k in "ohlc"}
        for ym in _months(pd.to_datetime(a_s, unit="s"), pd.to_datetime(b_s, unit="s")):
            fn = os.path.join(TICKS, "btc", f"BTCUSDT_{ym}.npz")
            if not os.path.exists(fn):
                continue
            d = np.load(fn)
            t = d["t"].astype(np.int64)
            ts.append(t + server_offset_s(t))
            for k in "ohlc":
                cols[k].append(d[k].astype(np.int64))
        srv = np.concatenate(ts); sec = {k: np.concatenate(v) for k, v in cols.items()}
        run = np.maximum.accumulate(srv)
        keep = np.r_[True, srv[1:] > run[:-1]]
        self.dropped_repeat = int((~keep).sum())
        keep &= (srv >= a_s) & (srv < b_s)
        srv = srv[keep]; sec = {k: v[keep] for k, v in sec.items()}
        assert np.all(np.diff(srv) > 0)
        # Binance's empty leading seconds: the reference one-minute open differs from the previous close
        ref = pd.read_pickle(os.path.join(SP, "recal", "btc", "m1.pkl"))
        mins = srv // 60
        st = np.r_[0, np.where(np.diff(mins) != 0)[0] + 1]
        en = np.r_[st[1:], len(srv)]
        ro = (ref["open"].reindex(pd.to_datetime(mins[st] * 60, unit="s")) * 100).round()
        assert not ro.isna().any(), "minutes without a reference bar"
        ro = ro.values.astype(np.int64)
        flat = (sec["o"] == sec["h"]) & (sec["h"] == sec["l"]) & (sec["l"] == sec["c"])
        drop = np.zeros(len(srv), bool)
        for k in range(1, len(st)):
            pc = sec["c"][st[k] - 1]
            if ro[k] != pc:
                q = st[k]
                while q < en[k] and flat[q] and sec["o"][q] == pc:
                    drop[q] = True; q += 1
        self.empty_dropped = int(drop.sum())
        srv = srv[~drop]; sec = {k: v[~drop] for k, v in sec.items()}
        mins = srv // 60
        st = np.r_[0, np.where(np.diff(mins) != 0)[0] + 1].astype(np.int64)
        en = np.r_[st[1:], len(srv)].astype(np.int64)
        self.minute = mins[st]
        self.mid_c = dict(open=sec["o"][st], high=np.maximum.reduceat(sec["h"], st), low=np.minimum.reduceat(sec["l"], st), close=sec["c"][en - 1])
        r = (ref.reindex(pd.to_datetime(self.minute * 60, unit="s")) * 100).round()
        same = np.ones(len(st), bool)
        for k in ("open", "high", "low", "close"):
            same &= r[k].values == self.mid_c[k]
        self.bars_vs_ref = dict(minutes=int(len(st)), identical=int(same.sum()),
                                ref_minutes_in_span=int(((ref.index >= pd.to_datetime(srv[0], unit="s")) & (ref.index <= pd.to_datetime(srv[-1], unit="s"))).sum()))
        assert same.all(), self.bars_vs_ref
        self.bid_bar_c = {k: v - HALF_C for k, v in self.mid_c.items()}
        self.sec_t = srv; self.sec = sec
        self.rq0, self.rq1 = 4 * st, 4 * en
        ns = type("S", (), {})()
        ns.t = srv; ns.o = sec["o"].astype(np.int32); ns.h = sec["h"].astype(np.int32); ns.l = sec["l"].astype(np.int32); ns.c = sec["c"].astype(np.int32)
        self.stream = K.second_stream(ns, st, en, HALF, 100.0, 0)

    def feed(self):
        """The ticks of the terminal from OnInit on: (ms, bid, ask)."""
        if not BTC:
            q0 = self.q_init
            return self.t_ms[q0:], self.bid[q0:], self.ask[q0:]
        s0 = self.q_init // 4
        o, h, l, c = (self.sec[k][s0:] for k in "ohlc")
        low_first = (o - l) <= (h - o)
        n = len(o)
        p = np.empty(4 * n, np.int64)
        p[0::4] = o; p[1::4] = np.where(low_first, l, h); p[2::4] = np.where(low_first, h, l); p[3::4] = c
        px = p / 100.0
        return np.repeat(self.sec_t[s0:] * 1000, 4), px - HALF, px + HALF

    def _check_feed(self):
        """The bars are the bid bars of the ticks; the K stream gives the terminal's quotes (sampled) and bar extremes."""
        tq_ms, tq_b, tq_a = self.feed()
        q0 = self.q_init
        n = len(tq_ms)
        rng = np.random.default_rng(1)
        sample = np.unique(np.r_[0, n - 1, rng.integers(0, n, 30000)])
        for i in sample:
            t, b, a = self.stream.quote(q0 + int(i))
            assert t == tq_ms[i] and b == tq_b[i] and a == tq_a[i], (i, t, b, a, tq_ms[i], tq_b[i], tq_a[i])
        rows = np.arange(self.init_row, len(self.minute))
        bb = self.bid_bars
        assert np.array_equal(self.stream.bar_bh[rows], bb["high"].values[rows]), "stream highest bid != bid bar high"
        al = bb["low"].values[rows] + SPREAD_PTS * 0.01
        d = np.abs(self.stream.bar_al[rows] - al)
        self.al_max_diff = float(d.max())
        assert self.al_max_diff < 1e-9, self.al_max_diff
        # bars from the fed ticks (bid) equal the terminal's bars
        mins = tq_ms // 60000
        st = np.r_[0, np.where(np.diff(mins) != 0)[0] + 1]
        en = np.r_[st[1:], n]
        assert np.array_equal(mins[st], self.minute[self.init_row:])
        for k, v in (("open", tq_b[st]), ("high", np.maximum.reduceat(tq_b, st)), ("low", np.minimum.reduceat(tq_b, st)), ("close", tq_b[en - 1])):
            assert np.array_equal(v, bb[k].values[self.init_row:]), k
        assert np.allclose(tq_a - tq_b, 2 * HALF, atol=1e-9) and np.abs(tq_a - tq_b - 2 * HALF).max() < 1e-9
        del tq_ms, tq_b, tq_a


# ----------------------------------------------------------------------------- setups
def select_setups(n_per_kind, extra_keys=()):
    d = json.load(open(PICKS))
    used = {ln.split()[1] for ln in open(USED) if ln.split()[0] == SYM}
    used_tf = {}
    for k in used:
        tf, kind, _ = k.split(":"); used_tf.setdefault(kind, set()).add(tf)
    out = []
    for kind in EA_MODE:
        cand = [(q["stored"]["unseen_n"], c["tf"], q) for c in d["cells"] if c["kind"] == kind for q in c["picks"] if q["key"] not in used]
        cand.sort(key=lambda x: (x[1] in used_tf.get(kind, set()), -x[0]))        # other timeframes first, most trades
        got, tfs = [], set()
        for _, tf, q in cand:
            if tf not in tfs and len(got) < n_per_kind:
                got.append(q); tfs.add(tf)
        for _, tf, q in cand:
            if len(got) >= n_per_kind:
                break
            if q not in got:
                got.append(q)
        out += [(kind, q) for q in got]
    keys = {q["key"] for _, q in out}
    for c in d["cells"]:
        for q in c["picks"]:
            if q["key"] in extra_keys and q["key"] not in keys and q["key"] not in used:
                out.append((c["kind"], q)); keys.add(q["key"])
    return out


def ea_inputs(p, clean):
    """clean: True (no time exits, no weekend close), False (the presets'), or "wk" (gold: only the Friday close)."""
    o = MP.ea_inputs(p, BTC, 777, "LOMA")
    o.update(HumpWarmupBars=1000000, UseNewsFilter="false", VerboseLog="true", ShowLevels="false", ShowStatusPanel="false",
             MarkSignals="false", ShowHumpLabels="false")
    if clean:
        o.update(MaxHoldMinutes=0, CloseAtEndOfDay="false", CloseBeforeWeekend="false")
    if isinstance(clean, str) and clean.startswith("wk") and not BTC:          # wk: 23:00, wkHHMM: that time
        o.update(CloseBeforeWeekend="true", WeekendCloseTime="23:00" if clean == "wk" else f"{clean[2:4]}:{clean[4:6]}")
    return o


def py_cfg(p, clean, preset_rr=False):
    c = TR.engine_cfg(p, {})
    if clean:
        c.update(max_hold=0, eod=-1, weekend_close=0)
    if isinstance(clean, str) and clean.startswith("wk") and not BTC:
        c.update(weekend_close=1, weekend_min=1380 if clean == "wk" else int(clean[2:4]) * 60 + int(clean[4:6]))
    if preset_rr and int(c["tp_mode"]) == 1 and abs(c["min_rr"] - c["tp_rr"]) < 1e-9:
        c["min_rr"] = round(c["tp_rr"] - 0.05, 2)
    return c


def ea_exec():
    return dict(TR.EA_EXEC[SYM], tick=0.01, point=0.01)


def run_ea(win, p, prefix, clean):
    with open(prefix + ".cfg", "w") as f:
        for k, v in ea_inputs(p, clean).items():
            f.write(f"{k}={v}\n")
        for k, v in {"sim.symbol": SYM, "sim.digits": 2, "sim.contract": 1 if BTC else 100, "run.init": win.init_s}.items():
            f.write(f"{k}={v}\n")
    t0 = time.time()
    r = subprocess.run([os.path.join(EA_DIR, "drv_px"), "tick", win.m1_bin, prefix + ".cfg", prefix, win.tick_bin], capture_output=True, text=True)
    msg = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise SystemExit(f"EA run failed ({r.returncode}): {msg}")
    return pd.read_csv(prefix + "_trades.csv"), pd.read_csv(prefix + "_reqs.csv"), msg, time.time() - t0


WHY = {1: "SL", 2: "TP", 3: "EA", 4: "EA", 5: "EA", 6: "EA"}


def compare(ea, py):
    ea = ea[ea.why != "OPEN"].copy()
    py = py[py.reason != 7].copy()
    ea["r"] = ea.side * (ea.p_out - ea.p_in) / (ea.p_in - ea.sl0).abs()
    ke = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(ea.t_in, ea.side))}
    kp = {(int(a) // 1000, int(b)): i for i, (a, b) in enumerate(zip(py.entry_ms, py.side))}
    rows = []
    for k in sorted(set(ke) | set(kp)):
        a = ea.iloc[ke[k]] if k in ke else None
        b = py.iloc[kp[k]] if k in kp else None
        row = dict(t_in=str(pd.to_datetime(k[0], unit="s")), side=k[1])
        if a is not None:
            row.update(ea_p_in=float(a.p_in), ea_sl0=float(a.sl0), ea_tp=float(a.tp), ea_t_out=str(pd.to_datetime(int(a.t_out), unit="s")),
                       ea_p_out=float(a.p_out), ea_why=a.why, ea_r=float(a.r), ea_nmod=int(a.nmod), ea_sl_last=float(a.sl_last))
        if b is not None:
            row.update(py_p_in=float(b.entry_px), py_sl0=float(b.sl0), py_tp=float(b.tp), py_t_out=str(pd.to_datetime(int(b.exit_ms) // 1000, unit="s")),
                       py_p_out=float(b.exit_px), py_why=K.REASON[int(b.reason)], py_r=float(b.r), py_nmod=int(b.nmod), py_sl_last=float(b.stop_last))
        diffs = []
        if a is None:
            diffs.append("only python")
        elif b is None:
            diffs.append("only EA")
        else:
            for f, x, y in (("entry price", a.p_in, b.entry_px), ("initial stop", a.sl0, b.sl0), ("target", a.tp, b.tp),
                            ("exit price", a.p_out, b.exit_px), ("last stop", a.sl_last, b.stop_last)):
                if abs(float(x) - float(y)) > 1e-9:
                    diffs.append(f)
            if int(a.t_out) != int(b.exit_ms) // 1000:
                diffs.append("exit second")
            if abs(float(a.r) - float(b.r)) > 1e-9:
                diffs.append("R")
            if a.why != WHY[int(b.reason)]:
                diffs.append("exit reason")
            if int(a.nmod) != int(b.nmod):
                diffs.append("stop moves")
        row["diffs"] = diffs
        rows.append(row)
    return rows


def main(out_dir, start, first_tick, end, setups, modes):
    os.makedirs(out_dir, exist_ok=True)
    win = Window(out_dir, start, first_tick, end)
    info = dict(window=win.tag, bars=len(win.mid), feed_ticks=win.n_feed, init=str(pd.to_datetime(win.init_s, unit="s")),
                dropped_repeat=win.dropped_repeat)
    if BTC:
        info.update(bars_vs_ref=win.bars_vs_ref, empty_leading_seconds=win.empty_dropped)
    print(json.dumps(info), flush=True)
    if setups.startswith("auto:"):
        n, *extra = setups[5:].split("+")
        sel = select_setups(int(n), set(extra[0].split(",")) if extra else ())
    else:
        want = setups.split(",")
        d = json.load(open(PICKS))
        sel = [(c["kind"], q) for c in d["cells"] for q in c["picks"] if q["key"] in want]
    res = []
    for mode in modes.split(","):
        clean = True if mode == "clean" else (mode if mode.startswith("wk") else False)
        for kind, q in sel:
            p = q["params"]
            name = f"{SYM}_{q['key'].replace(':', '_')}_{mode}"
            ea, reqs, msg, sec = run_ea(win, p, os.path.join(out_dir, name), clean)
            out = dict(name=name, key=q["key"], kind=kind, ea_mode=EA_MODE[kind], tf=p["tf"], mode=mode,
                       trail=(p["trail_start"], p["trail_dist"], p.get("trail_p", 0)), tp_mode=p["tp_mode"], min_rr=p["min_rr"], tp_rr=p["tp_rr"],
                       ea_msg=msg)
            for variant, preset_rr in (("replay", False), ("preset_rr", True)):
                c = py_cfg(p, clean, preset_rr)
                if variant == "preset_rr" and c["min_rr"] == p["min_rr"]:
                    continue
                prep = K.prepare(win.mk, c)
                s_ = np.where((prep["er"] >= 0) & (prep["er"] + int(prep["c"]["delay"]) >= win.init_row))[0]
                py = K.run_tick(win.mk, prep, win.stream, ea_exec(), sel=s_)
                rows = compare(ea, py)
                out[variant] = dict(ea_trades=int((ea.why != "OPEN").sum()), py_trades=int((py.reason != 7).sum()),
                                    identical=sum(not r["diffs"] for r in rows), differ=[r for r in rows if r["diffs"]],
                                    ea_open=int((ea.why == "OPEN").sum()), py_open=int((py.reason == 7).sum()),
                                    ea_mods=int(((reqs.kind == "MODIFY") & (reqs.ok == 1)).sum()), ea_closes=int((reqs.kind == "CLOSE").sum()),
                                    py_mods=int(py.nmod.sum()), by_reason=py.reason.map(K.REASON).value_counts().to_dict())
                v = out[variant]
                print(f"{name:40s} {variant:9s} EA {v['ea_trades']:3d} py {v['py_trades']:3d} identical {v['identical']:3d} "
                      f"differ {len(v['differ']):2d} | mods EA {v['ea_mods']} py {v['py_mods']} | {msg[:90]} ({sec:.0f}s)", flush=True)
            res.append(out)
            json.dump(dict(info=info, setups=res), open(os.path.join(out_dir, f"{SYM.lower()}_{win.tag}_indep.json"), "w"), indent=1, default=str)
    for f in (win.tick_bin,):
        os.remove(f)
    tot = {}
    for r in res:
        v = r["replay"]
        t = tot.setdefault(r["mode"], [0, 0, 0, 0])
        t[0] += 1; t[1] += v["ea_trades"]; t[2] += v["identical"]; t[3] += len(v["differ"])
    print(f"{SYM} {win.tag}: " + "; ".join(f"{m}: {t[0]} setups, EA trades {t[1]}, identical {t[2]}, differing {t[3]}" for m, t in tot.items()), flush=True)
    return res


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], a[4], a[5], a[6] if len(a) > 6 else "clean,full")
