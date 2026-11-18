#!/usr/bin/env python3
"""
Parity of hump_tick.simulate_tick with the EA itself on real ticks.

The simulated terminal of the v1.35 checks runs the EA's real OnInit / OnTick (XAUUSD_Loma_TrendPullback.mq5 v1.35,
translated by mq2rt.py, shim mql5_shim.h; copies in <scratchpad>/tick/builder/ea with a real-tick driver drv_tick.cpp
and the shim's fill_at_tick: stops and targets filled at the tick's own price). Both sides get the same quotes:
  BTCUSD  Binance seconds (empty leading seconds removed, tick_data), four points per second (open, the extreme
          nearer to the open, the other extreme, close), bid = price - 5, ask = price + 5
  XAUUSD  Dukascopy ticks, bid = (bid + ask) / 2 - 0.075 rounded to the cent, ask = bid + 0.15: VT's constant spread,
          quotes on the 0.01 grid as a broker's
The terminal's one-minute bars are the bid bars of these ticks (spread field = the constant spread); Python gets the
mid bars (bid + half the spread) and the same ticks. The bar series starts well before OnInit (the first tick fed),
so that the EA's indicator readiness (more than MACD_Slow + MACD_Signal + 3 bars of every timeframe it reads, the trend
filter's included: 38 D1 bars) holds from the first tick, and the EA replays the whole series at OnInit
(HumpWarmupBars 1,000,000), so that its hump state starts from the same first bar as Python's signals.
The EA gets the shipped presets' inputs (make_v135_presets.ea_inputs: a fixed-RR setup with MinRewardRisk = TP_RR gets
TP_RR - 0.05) plus HumpWarmupBars 1,000,000 and no news filter; Python gets tick_replay.engine_cfg (the same reward rule)
and the EA's entry rows after a market gap (hump_tick.ea_entry_rows). simulate_tick runs with the EA's settings: tick
grid 0.01 (stops and targets as NormalizePrice / TrailStopPrice), the presets' TrailStep (gold 10 points = 0.10, BTC 200
points = 2.00), fills at the tick price, plan checks, the EA's previous-hump target. Every EA trade is compared with
Python's: entry time and price, initial stop, target, exit time and price, R, number of stop moves and the last stop.

Usage (from research/):
  [HUMP_SYMBOL=BTCUSD] python3 tick_parity.py <out_dir> <picks_json_dir> <series_start> <first_tick> <end> [n_per_mode=2] [clean|full]
                       [extra pick keys TF:kind:rank,...] [output tag]
     clean: no time exits and no weekend close on either side (every exit is a stop, a target or the trailing)
     full : the setups' MaxHoldMinutes / CloseAtEndOfDay and (gold) the Friday close at 23:00, as the presets
"""
import json, os, struct, subprocess, sys, time
import numpy as np, pandas as pd

os.environ.setdefault("HUMP_SPACE", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, xlzc_backtest as B
import hump_trail2 as T2
import hump_tick as K
import tick_data as D
import tick_replay as TR
import make_v135_presets as MP

SYM = H.SYMBOL
BTC = SYM == "BTCUSD"
EA_DIR = os.path.join(D.SP, "tick", "builder", "ea")
HALF = D.BTC_HALF if BTC else D.VT_HALF
SPREAD_PTS = int(round(2 * HALF * 100))


def ea_inputs(p, clean=True):
    """EA inputs of a backtest setup: the shipped presets' mapping (make_v135_presets.ea_inputs, which also applies the
    MinRewardRisk = TP_RR - 0.05 rule of tie setups), the hump state replayed from the first bar, no news filter;
    clean: no time exits and no weekend close."""
    o = MP.ea_inputs(p, BTC, 777, "LOMA")
    o.update(HumpWarmupBars=1000000, UseNewsFilter="false")
    if clean:
        o.update(MaxHoldMinutes=0, CloseAtEndOfDay="false", CloseBeforeWeekend="false")
    return o


def py_cfg(p, clean=True):
    """simulate_tick's settings of the setup: tick_replay.engine_cfg (the presets' reward rule included)."""
    return TR.engine_cfg(p, dict(max_hold=0, eod=-1, weekend_close=0) if clean else {})


EA_PY = dict(step=2.0 if BTC else 0.10, point=0.01, tick=0.01, stops_level=0.0, fill_level=0, plan_checks=1, server_exit_free=1,
             trail_open=1, ea_tp=1)


class Window:
    """Quotes, bars and the files of the simulated terminal for [start, end) (server time)."""

    def __init__(self, out_dir, start, first_tick, end):
        os.makedirs(out_dir, exist_ok=True)
        tag = f"{SYM}_{pd.Timestamp(start):%Y%m%d}_{pd.Timestamp(first_tick):%Y%m%d}_{pd.Timestamp(end):%Y%m%d}"
        ft = pd.Timestamp(first_tick)
        self.m1_bin = os.path.join(out_dir, tag + "_m1.bin"); self.tick_bin = os.path.join(out_dir, tag + "_ticks.bin")
        if BTC:
            sec = D.load_btc(start, end)
            bars, st, en = D.btc_m1(sec)
            mid = bars.astype(np.float64) / D.BTC_DIV
            self.bars = mid
            bid = pd.DataFrame({k: bars[k].values / D.BTC_DIV - HALF for k in ("open", "high", "low", "close")}, index=bars.index)
            self.stream = K.second_stream(sec, st, en, HALF, D.BTC_DIV, 0)
            q = np.arange(4 * len(sec.t), dtype=np.int64)
            self.init_row = int(np.searchsorted(bars.index.values, ft.to_datetime64()))
            q0 = 4 * st[self.init_row]
            sub = q[q0:] & 3; s_ = q[q0:] >> 2                                # the four points per second, as the stream
            o, h, l, c = sec.o[s_], sec.h[s_], sec.l[s_], sec.c[s_]
            low_first = (o - l) <= (h - o)
            p = np.where(sub == 0, o, np.where(sub == 3, c, np.where((sub == 1) == low_first, l, h)))
            self.t_ms = sec.t[s_] * 1000
            self.bid = p / D.BTC_DIV - HALF; self.ask = p / D.BTC_DIV + HALF
            assert all(abs(self.stream.quote(int(q0 + i))[1] - self.bid[i]) < 1e-9 for i in range(0, len(self.bid), max(1, len(self.bid) // 997)))
        else:
            tk = D.GoldTicks(start, end)
            mid = (tk.bid.astype(np.int64) + tk.ask.astype(np.int64)) / (2 * D.GOLD_DIV)
            b_ = np.round(mid - HALF, 2); a_ = np.round(b_ + 2 * HALF, 2)
            st_, mins = D._groups(tk.t // 60000)
            en_ = np.r_[st_[1:], len(tk.t)]
            bid = pd.DataFrame(dict(open=b_[st_], high=np.maximum.reduceat(b_, st_), low=np.minimum.reduceat(b_, st_), close=b_[en_ - 1]),
                               index=pd.to_datetime(mins * 60000, unit="ms"))
            self.bars = bid + HALF
            self.stream = K.tick_stream(tk.t, b_, a_, st_, en_, sell_best="bid_low_min_spread")
            self.init_row = int(np.searchsorted(bid.index.values, ft.to_datetime64()))
            q0 = st_[self.init_row]
            self.t_ms, self.bid, self.ask = tk.t[q0:], b_[q0:], a_[q0:]
        self.init_s = int(self.bars.index[self.init_row].value // 10 ** 9)
        if not os.path.exists(self.m1_bin):
            t = bid.index.values.astype("datetime64[s]").astype(np.int64)
            rec = np.zeros(len(bid), dtype=[("t", "<i8"), ("o", "<f8"), ("h", "<f8"), ("l", "<f8"), ("c", "<f8"), ("s", "<i4"), ("p", "<i4")])
            rec["t"] = t; rec["o"] = bid["open"].values; rec["h"] = bid["high"].values; rec["l"] = bid["low"].values
            rec["c"] = bid["close"].values; rec["s"] = SPREAD_PTS
            with open(self.m1_bin, "wb") as f:
                f.write(struct.pack("<q", len(bid))); f.write(rec.tobytes())
        if not os.path.exists(self.tick_bin):
            rec = np.zeros(len(self.t_ms), dtype=[("t", "<i8"), ("b", "<f8"), ("a", "<f8")])
            rec["t"] = self.t_ms; rec["b"] = self.bid; rec["a"] = self.ask
            with open(self.tick_bin, "wb") as f:
                f.write(struct.pack("<q", len(rec))); f.write(rec.tobytes())
        self.mk = T2.MarketY(m1=self.bars, half_spread=np.full(len(self.bars), HALF))
        print(f"{SYM} window {self.bars.index[0]} .. {self.bars.index[-1]}: {len(self.bars):,} bars, {len(self.t_ms):,} ticks from "
              f"{pd.to_datetime(self.init_s, unit='s')} (OnInit)", flush=True)


def run_ea(win, p, out_prefix, clean):
    cfgp = out_prefix + ".cfg"
    with open(cfgp, "w") as f:
        for k, v in ea_inputs(p, clean).items():
            f.write(f"{k}={v}\n")
        for k, v in {"sim.symbol": SYM, "sim.digits": 2, "sim.contract": 1 if BTC else 100, "run.init": win.init_s}.items():
            f.write(f"{k}={v}\n")
    t0 = time.time()
    r = subprocess.run([os.path.join(EA_DIR, "drv_tick"), "tick", win.m1_bin, cfgp, out_prefix, win.tick_bin], capture_output=True, text=True)
    msg = (r.stdout + r.stderr).strip()
    if r.returncode != 0:
        raise SystemExit(f"EA run failed ({r.returncode}): {msg}")
    df = pd.read_csv(out_prefix + "_trades.csv")
    return df, msg, time.time() - t0


def compare(ea, py, init_s, t_end_s):
    """Every EA trade against simulate_tick's, matched by entry second and side."""
    ea = ea[ea.why != "OPEN"].copy()
    risk = (ea.p_in - ea.sl0).abs()
    ea["r"] = ea.side * (ea.p_out - ea.p_in) / risk
    py = py[(py.reason != 7)].copy()
    py["t_in"] = py.entry_ms // 1000; py["t_out"] = py.exit_ms // 1000
    ke = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(ea.t_in, ea.side))}
    kp = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(py.t_in, py.side))}
    rows = []
    for k in sorted(set(ke) | set(kp)):
        a = ea.iloc[ke[k]] if k in ke else None; b = py.iloc[kp[k]] if k in kp else None
        row = dict(t_in=str(pd.to_datetime(k[0], unit="s")), side=k[1])
        if a is not None:
            row.update(ea_p_in=float(a.p_in), ea_t_out=str(pd.to_datetime(int(a.t_out), unit="s")), ea_p_out=float(a.p_out), ea_r=float(a.r),
                       ea_why=a.why, ea_sl0=float(a.sl0), ea_tp=float(a.tp), ea_nmod=int(a.nmod), ea_sl_last=float(a.sl_last))
        if b is not None:
            row.update(py_p_in=float(b.entry_px), py_t_out=str(pd.to_datetime(int(b.t_out), unit="s")), py_p_out=float(b.exit_px), py_r=float(b.r),
                       py_why=K.REASON[int(b.reason)], py_sl0=float(b.sl0), py_tp=float(b.tp), py_nmod=int(b.nmod), py_sl_last=float(b.stop_last))
        if a is not None and b is not None:
            row["same"] = bool(abs(row["ea_p_in"] - row["py_p_in"]) < 1e-6 and int(a.t_out) == int(b.t_out)
                               and abs(row["ea_p_out"] - row["py_p_out"]) < 1e-6 and abs(row["ea_r"] - row["py_r"]) < 1e-9
                               and abs(row["ea_sl0"] - row["py_sl0"]) < 1e-6 and abs(row["ea_tp"] - row["py_tp"]) < 1e-6
                               and row["ea_nmod"] == row["py_nmod"] and abs(row["ea_sl_last"] - row["py_sl_last"]) < 1e-6)
        else:
            row["same"] = False
        rows.append(row)
    return rows


def pick_setups(picks_dir, n_per_mode, extra=()):
    """Per EA trailing system, n picks of the re-derived cells (most unseen trades first, different timeframes first),
    then the picks named in extra (keys TF:kind:rank)."""
    d = json.load(open(os.path.join(picks_dir, f"{SYM.lower()}_picks.json")))
    out = []
    for kind in (K.EA_MODE if n_per_mode > 0 else ()):           # n_per_mode 0: only the extra picks
        cand = sorted(((q["stored"]["unseen_n"], c["tf"], q) for c in d["cells"] if c["kind"] == kind for q in c["picks"]),
                      key=lambda x: -x[0])
        got, tfs = [], set()
        for _, tf, q in cand:
            if tf not in tfs:
                got.append(q); tfs.add(tf)
            if len(got) >= n_per_mode:
                break
        for _, tf, q in cand:
            if len(got) >= n_per_mode:
                break
            if q not in got:
                got.append(q)
        out += [(kind, q) for q in got]
    have = {q["key"] for _, q in out}
    byk = {q["key"]: (c["kind"], q) for c in d["cells"] for q in c["picks"]}
    out += [byk[k] for k in extra if k not in have]
    return out


def main(out_dir, picks_dir, start, first_tick, end, n_per_mode=2, mode="clean", extra=(), tag=""):
    clean = mode == "clean"
    win = Window(out_dir, start, first_tick, end)
    res = []
    for kind, q in pick_setups(picks_dir, n_per_mode, extra):
        p = q["params"]
        name = f"{SYM}_{q['key'].replace(':', '_')}_{mode}"
        ea, msg, sec = run_ea(win, p, os.path.join(out_dir, name), clean)
        c = py_cfg(p, clean)
        assert abs(float(ea_inputs(p, clean)["MinRewardRisk"]) - c["min_rr"]) < 1e-12      # the same reward test on both sides
        prep = K.prepare(win.mk, c, ea_rows=True)
        sel = np.where((prep["er"] >= 0) & (prep["er"] + int(prep["c"]["delay"]) >= win.init_row))[0]
        py = K.run_tick(win.mk, prep, win.stream, dict(EA_PY, time_rules=0 if clean else 1), sel=sel)
        rows = compare(ea, py, win.init_s, None)
        same = sum(r["same"] for r in rows)
        res.append(dict(name=name, kind=kind, ea_mode=K.EA_MODE[kind], tf=p["tf"], trail=(p["trail_start"], p["trail_dist"], p.get("trail_p", 0)),
                        tp_mode=p["tp_mode"], tie_rr=TR.is_tie(p), min_rr=c["min_rr"],
                        ea_trades=int((ea.why != "OPEN").sum()), py_trades=int((py.reason != 7).sum()), same=same,
                        differ=[r for r in rows if not r["same"]], ea_msg=msg, ea_seconds=round(sec, 1)))
        print(f"{name:42s} EA {res[-1]['ea_trades']:3d} py {res[-1]['py_trades']:3d} identical {same:3d} | {msg} ({sec:.0f}s)", flush=True)
    json.dump(res, open(os.path.join(out_dir, f"{SYM.lower()}_parity_{mode}{tag}.json"), "w"), indent=1, default=str)
    tot_ea = sum(r["ea_trades"] for r in res); tot_same = sum(r["same"] for r in res)
    print(f"{SYM} {mode}: {len(res)} setups, EA trades {tot_ea}, identical in entry, stop, target, exit (time, price), R, stop moves "
          f"and last stop: {tot_same}", flush=True)
    return res


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], a[3], a[4], a[5], int(a[6]) if len(a) > 6 else 2, a[7] if len(a) > 7 else "clean",
         [k for k in a[8].split(",") if k] if len(a) > 8 else (), a[9] if len(a) > 9 else "")
