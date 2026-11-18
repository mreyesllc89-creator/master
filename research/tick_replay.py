#!/usr/bin/env python3
"""
Tick-by-tick replay of the re-calibration's trailing picks (hump_tf_recal.py, successful_trailing.py) with the EA's
execution rules (hump_tick.simulate_tick), next to the one-minute engine (hump_trail2.simulate_y) on the same bars.

Steps
  picks   Re-derive the protocol's picks of every (timeframe, trailing kind) cell from the stored candidate trades,
          exactly as successful_trailing.py does (best in-sample scores, one per direction / session / trend filter,
          score >= 1.3, at most 10), and assert the stored figures of results/recal/<sym>_23_trailing_by_family.json
          (picks, unseen trades, unseen PF) and of <sym>_23_trailing.json (the timeframe level). The candidate files may
          be gzip-compressed (cand*.pkl.gz): they are read through gzip, nothing is written to disk.
          -> <out>/<sym>_picks.json (every pick with its settings and stored figures) and <sym>_picks_trades.npz (the
             stored base / stress trades of every pick: entry minute and R, to check the replay's one-minute engine).
  prep    One-minute mid bars and per-minute quote facts of a data span, built from the ticks (gold: month by month)
          or seconds (BTC), cached in <cache>/<sym>_<span>_*.  BTC bars must equal the study's Binance bars.
  run     For a list of cells and cost models: build the signals on the tick bars with MarketY (same settings as the
          study), then replay every pick with simulate_tick (ticks) and simulate_y (one-minute bars, the half spread of
          each minute's first tick under the same cost model). Per cell, period and cost model: trades, PF, net R of
          both; per trade: entry / exit time, R, exit reason.

Spans and periods (entry time, server clock)
  XAUUSD  pre  = 1 Jul - 31 Dec 2024 (Dukascopy ticks), period "earlier" from 15 Jul 2024 (two weeks of warm-up, as
               pretest_picks.py);  main = 2 Jan 2025 - 13 Nov 2026: "calibration" to IS_END (16 May 2026 03:00),
               "unseen" after it (the re-calibration used FTMO M1 before 16 May 2026 and Dukascopy M1 after: the tick
               bars differ from both, see tick_data.check_gold).
  BTCUSD  pre  = 2023-2024 (one series, as pretest_picks.py): "2023" from 15 Jan 2023, "2024";  main = Jan 2025 - 13
               Nov 2026: "calibration", "unseen" (the bars equal the study's, so simulate_y reproduces the stored trades).

Settings of a pick: the stored setup with the shipped presets' reward rule (preset_rr, make_v135_presets.ea_inputs,
LOMA_V135_CHANGES item 12): a fixed-RR setup with min_rr = tp_rr gets min_rr = tp_rr - 0.05 on both engines. At equality
floating point decides: the EA's tick-rounded target refuses some 20% of such trades (the tick engine without the rule:
BTC tie picks 17-24% fewer trades), and simulate_y itself refuses 17-29% of them at tp_rr 1.5, by 7e-12 or less
(tp - entry < 1.5 x risk after rounding; 0-1% at tp_rr 1.0). So the study's stored trades of the
tie picks with tp_rr 1.5 are short (BTC M5:step:3, M10:donchian:3; gold M5:ema:1, M10:profitlock:2, M15:pivots:2): their
one-minute figures here exceed the stored ones. For these picks the one-minute engine also runs with the stored setting
as is (engine '1m_raw'), which is what the stored-trade check compares.
Entries (simulate_tick): the EA's rule for a signal after a market gap (hump_tick.ea_entry_rows: entered when the market
reopens within two trigger periods after the signal bar's close; simulate_y within one).

Cost models
  XAUUSD vt         mid of Dukascopy's ticks -/+ 0.075 x (Dukascopy's spread / its monthly median), on the cent, spread
                    at least 0.01; $0.60 commission
         duk_raw    Dukascopy's own bid and ask; $0.60 commission
         vt_stress  vt, entry one minute late, $0.10 slippage on entries and stop / market exits, $0.67 commission
                    (one-minute side: also trail_worst = 1, the study's stress)
  BTCUSD vt         mid -/+ 5 USD (the study's 10 USD spread), no commission
         vt_stress  + one minute late, 3 USD slippage, 2 USD commission (one-minute side: trail_worst = 1)
EA execution settings of the presets: TrailStep_Points 10 (gold, 0.10 USD) / 200 (BTC, 2.00 USD), MaxSpread 0.60 gold
(the setups' max_spread, counted in whole points as SpreadOK; BTC none), stops level 0, the EA's time exits and Friday
close (gold), plan checks on, the EA's previous-hump target (item 13). Quotes and stops on the cost model's tick grid:
BTC and the VT gold models 0.01 (the VT quotes are rounded to the cent, the spread to whole cents, at least one), Dukascopy 0.001; the
EA's own arithmetic on them (NormalizePrice, TrailStopPrice, 1R = |fill - stop sent|, SpreadOK in whole points), which
tick_parity.py proves trade for trade against the EA's code. With unrounded stops the 1R carries float noise of the
spread arithmetic, and STEP's floor(profit / step) then breaks exact ties (BTC prices lie on the cent) differently from
the EA; run's last argument -1 gives unrounded stops all the same (simulate_y's arithmetic).
Gold's sell-side best price of a completed minute: lowest bid + the minute's smallest spread (the EA reads bid low +
MqlRates.spread, taken as the bar's minimum spread); TICK_SELL_BEST=ask_low uses the minute's lowest ask instead.

Usage (from research/, HUMP_SYMBOL=XAUUSD|BTCUSD):
  python3 tick_replay.py picks <recal_work_dir> <out_dir> [TFs]           # re-derive and assert the picks
  python3 tick_replay.py run <out_dir> <span: pre|main> <cells: ea | all | M5:atr,M10:percent,...> <models: all | vt,...>
                             [worker workers] [order 0|1] [grid: 0 = the cost model's (default), -1 = unrounded]
                             (ea = every cell of the 14 systems the EA has; a worker takes every workers-th pick)
  python3 tick_replay.py summary <out_dir> [file pattern]                 # per cell, model and period: ticks vs 1 minute
  python3 tick_replay.py stored <out_dir>                                 # BTC: one-minute trades = the study's stored
  python3 tick_replay.py order <out_dir> <span> <cells>                   # BTC: the other order inside a second

The full run (env: NUMBA_CACHE_DIR, PYTHONDONTWRITEBYTECODE=1; picks first, then two workers per span, at most two at a
time; BTC needs about 3 GB per worker, gold about 1.5 GB; every month file of a span must exist, else it stops with the
missing months (tick_data.require_months); the gold cache key holds the names, sizes and times of the span's files):
  HUMP_SYMBOL=BTCUSD python3 tick_replay.py picks <scratch>/recal/btc <out>
  HUMP_SYMBOL=BTCUSD python3 tick_replay.py run <out> main ea all 0 2   (and ... 1 2), then pre the same way
  HUMP_SYMBOL=BTCUSD python3 tick_replay.py stored <out>              (must say 326 of 326 for the 14 systems)
  HUMP_SYMBOL=XAUUSD python3 tick_replay.py picks <scratch>/recal/gold <out>; run <out> pre|main ea all 0 2 / 1 2
  HUMP_SYMBOL=<sym> python3 tick_replay.py summary <out>
"""
import gzip, hashlib, json, os, pickle, sys, time
import numpy as np, pandas as pd

os.environ.setdefault("HUMP_SPACE", "2")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hump_engine as H, hump_search as X, xlzc_backtest as B
import hump_tf_recal as R
import hump_trail2 as T2
import hump_tick as K
import tick_data as D

SYM = R.SYM
BTC = SYM == "BTCUSD"
SP = D.SP
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "recal")
CACHE = os.environ.get("TICK_CACHE", os.path.join(SP, "tick", "cache"))
EA_KINDS = list(K.EA_MODE)                         # the 14 systems the EA has (TrailMode 0-13)
ENGINES = {"1m": 0, "tick": 1, "1m_raw": 2}         # trades files: simulate_y, simulate_tick, simulate_y with the stored setting


# ----------------------------------------------------------------------------- picks
def load_cands(work, prefix, tf):
    """hump_tf_recal.load_cands that also reads gzip-compressed files (<prefix>_<TF>.pkl.gz) without writing them out."""
    P, Bs, Ss = [], [], []
    for pre in prefix.split("+"):
        fn = os.path.join(work, f"{pre}_{tf}.pkl")
        if os.path.exists(fn):
            d = pickle.load(open(fn, "rb"))
        elif os.path.exists(fn + ".gz"):
            with gzip.open(fn + ".gz", "rb") as f:
                d = pickle.load(f)
        else:
            return None
        P += d["params"]; Bs += d["base"]; Ss += d["stress"]
        del d
    return P, Bs, Ss


def pick(P, sc, idx):
    """successful_trailing.pick: best in-sample scores, one per (direction, session, trend filter), score >= 1.3."""
    elig = idx[sc[idx] > 0]
    order = elig[np.argsort(-sc[elig], kind="stable")]
    out, fams = [], set()
    for i in order:
        if sc[i] < R.PASS_PF or len(out) >= R.TOPK:
            break
        fam = (P[i]["sides"], P[i]["session"], P[i]["htf"])
        if fam in fams:
            continue
        fams.add(fam); out.append(int(i))
    return out


def derive_picks(work, out_dir, tfs=None):
    """Every cell's picks, asserted against the stored figures. Writes <sym>_picks.json and <sym>_picks_trades.npz."""
    os.makedirs(out_dir, exist_ok=True)
    sym = SYM.lower()
    fam = json.load(open(os.path.join(RES, f"{sym}_23_trailing_by_family.json")))
    main = {x["tf"]: x for x in json.load(open(os.path.join(RES, f"{sym}_23_trailing.json")))["timeframes"]}
    cells = {(c["tf"], c["kind"]): c for c in fam["cells"]}
    out = dict(symbol=SYM, cells=[], timeframes=[], checked=[])
    arrays = {}
    for tf in (tfs or R.TFS):
        t0 = time.time()
        loaded = load_cands(work, "candx+candy", tf)
        if loaded is None:
            print(f"{SYM} {tf}: no candidate files", flush=True); continue
        P, Bs, Ss = loaded
        sc = np.array([R.is_score(Bs[i], Ss[i]) for i in range(len(P))])
        allidx = np.arange(len(P))
        kind_of = np.array([p["trail_kind"] for p in P])
        for kind in dict.fromkeys(kind_of):
            got = pick(P, sc, allidx[kind_of == kind])
            c = cells[(tf, kind)]
            if got:
                r = np.concatenate([R.split(*Bs[i])[2] for i in got])
                assert len(got) == c["picked"] and len(r) == c["oos_n"] and abs(R.pf(r) - c["oos_pf"]) < 1e-9, (tf, kind)
                out["checked"].append(f"{tf}:{kind} picks {len(got)}, unseen trades {len(r)}, unseen PF {R.pf(r):.4f} = stored")
            else:
                assert not c.get("picked"), (tf, kind)
            rows = []
            for rank, i in enumerate(got, 1):
                key = f"{tf}:{kind}:{rank}"
                isr, _, oor = R.split(*Bs[i]); _, _, oos = R.split(*Ss[i])
                rows.append(dict(key=key, rank=rank, cand_index=int(i), params=P[i], is_score=float(sc[i]),
                                 stored=dict(is_n=int(len(isr)), is_pf=R.pf(isr), unseen_n=int(len(oor)), unseen_pf=R.pf(oor),
                                             unseen_net_r=float(oor.sum()), unseen_stress_n=int(len(oos)), unseen_stress_pf=R.pf(oos))))
                arrays[key + ":base_t"] = Bs[i][0]; arrays[key + ":base_r"] = Bs[i][1]
                arrays[key + ":stress_t"] = Ss[i][0]; arrays[key + ":stress_r"] = Ss[i][1]
            out["cells"].append(dict(tf=tf, kind=kind, ea_mode=K.EA_MODE.get(kind), picked=len(got), picks=rows,
                                     stored=dict(oos_n=c.get("oos_n"), oos_pf=c.get("oos_pf"), oos_stress_pf=c.get("oos_stress_pf"))))
        m = main[tf]
        got = pick(P, sc, allidx)
        if m.get("picked"):
            r = np.concatenate([R.split(*Bs[i])[2] for i in got])
            assert len(got) == m["picked"] and len(r) == m["oos_n"] and abs(R.pf(r) - m["oos_pf"]) < 1e-9, tf
            out["checked"].append(f"{tf} (timeframe level) picks {len(got)}, unseen trades {len(r)}, unseen PF {R.pf(r):.4f} = stored")
        out["timeframes"].append(dict(tf=tf, picks=[P[i] for i in got], cand_index=[int(i) for i in got]))
        print(f"{SYM} {tf}: {len(P)} candidates, picks re-derived and asserted ({time.time() - t0:.0f}s)", flush=True)
        del P, Bs, Ss, loaded
    json.dump(out, open(os.path.join(out_dir, f"{sym}_picks.json"), "w"), indent=1, default=float)
    np.savez_compressed(os.path.join(out_dir, f"{sym}_picks_trades.npz"), **arrays)
    n = sum(c["picked"] for c in out["cells"])
    print(f"{SYM}: {len(out['cells'])} cells, {n} picks, {len(out['checked'])} stored figures asserted", flush=True)
    return out


# ----------------------------------------------------------------------------- spans, cost models
SPANS = {"XAUUSD": {"pre": ("2024-07-01 00:00", "2025-01-01 00:00"), "main": ("2025-01-01 00:00", "2026-11-14 00:00")},
         "BTCUSD": {"pre": ("2023-01-01 02:00", "2025-01-01 02:00"), "main": ("2025-01-01 02:00", "2026-11-14 02:00")}}
MODELS = {"XAUUSD": {"vt": dict(quotes="vt", grid=0.01, extra=dict(comm=R.VT_COMM), y_extra={}),
                     "duk_raw": dict(quotes="raw", grid=0.001, extra=dict(comm=R.VT_COMM), y_extra={}),
                     "vt_stress": dict(quotes="vt", grid=0.01, extra=dict(comm=R.VT_COMM + 0.07, slip=0.10, delay=1),
                                       y_extra=dict(trail_worst=1))},
          "BTCUSD": {"vt": dict(quotes="vt", grid=0.01, extra={}, y_extra={}),
                     "vt_stress": dict(quotes="vt", grid=0.01, extra=dict(comm=2.0, slip=3.0, delay=1), y_extra=dict(trail_worst=1))}}
# the EA's execution settings (presets): TrailStep 10 points (gold 0.10) / 200 points (BTC 2.00); point and tick grid of
# the quotes of the cost model (MODELS[..]["grid"]: the EA rounds stops and targets to it and counts the spread in it)
EA_EXEC = {"XAUUSD": dict(step=0.10, stops_level=0.0, fill_level=0, plan_checks=1, time_rules=1, server_exit_free=1, trail_open=1),
           "BTCUSD": dict(step=2.00, stops_level=0.0, fill_level=0, plan_checks=1, time_rules=1, server_exit_free=1, trail_open=1)}
SELL_BEST = os.environ.get("TICK_SELL_BEST", "bid_low_min_spread")   # gold: the sell side's best price of a closed minute


def periods(span, first_bar):
    """Entry-time periods of a span: (label, start, end) in server time."""
    if span == "main":
        a, b = SPANS[SYM]["main"]
        return [("calibration", np.datetime64(pd.Timestamp(a)), R.IS_END), ("unseen", R.IS_END, np.datetime64(pd.Timestamp(b)))]
    if BTC:
        return [("2023", np.datetime64("2023-01-15"), np.datetime64("2024-01-01")), ("2024", np.datetime64("2024-01-01"), np.datetime64("2025-01-01"))]
    return [("earlier", np.datetime64(first_bar + pd.Timedelta(days=14)), np.datetime64("2025-01-01"))]


class GoldSpan:
    """Gold ticks of a span, by UTC month file: one-minute mid bars of the whole span (for the signals) and, per cost
    model, the half spread of every minute's first tick (simulate_y), its highest bid and its sell-side best price
    (simulate_tick's completed minutes). Tick windows of whole files are loaded on demand."""

    def __init__(self, span, cache=CACHE):
        self.a, self.b = SPANS[SYM][span]
        self.a_ms = D._sec(self.a) * 1000; self.b_ms = D._sec(self.b) * 1000
        D.require_months("gold", self.a, self.b)          # every month of the span on disk, or stop
        self.files = [D.month_file("gold", y, m) for (y, m) in D._months(self.a, self.b)]
        self.files = [f for f in self.files if os.path.exists(f)]     # (the margin months outside the data may be absent)
        os.makedirs(cache, exist_ok=True)
        sig = hashlib.sha1("|".join(f"{os.path.basename(f)}:{os.path.getsize(f)}:{os.stat(f).st_mtime_ns}"
                                    for f in self.files).encode()).hexdigest()[:12]           # a changed file: new bars
        key = os.path.join(cache, f"xauusd_{span}_{os.path.basename(self.files[0])[7:14]}_{os.path.basename(self.files[-1])[7:14]}"
                                  f"_{SELL_BEST}_vtfloor_{sig}")
        if os.path.exists(key + "_bars.pkl"):
            self.bars = pd.read_pickle(key + "_bars.pkl")
            z = np.load(key + "_facts.npz", allow_pickle=True)
            self.row_file = z["row_file"]; self.row_q0 = z["row_q0"]; self.row_q1 = z["row_q1"]
            self.facts = {q: dict(hs=z[f"{q}_hs"], bh=z[f"{q}_bh"], al=z[f"{q}_al"]) for q in ("vt", "raw")}
            self.medians = json.loads(str(z["medians"]))
        else:
            self._build(key)
        self.n = len(self.bars)
        self.file_rows = [np.where(self.row_file == i)[0] for i in range(len(self.files))]

    def _ticks(self, i):
        """Server time (ms), Dukascopy bid and ask (int, x 1000) of file i inside the span."""
        d = np.load(self.files[i])
        t = d["t"]
        srv = (D.utc_to_server_s(t // 1000) - t // 1000) * 1000 + t
        keep = D._keep_first_ms(srv) & (srv >= self.a_ms) & (srv < self.b_ms)
        return srv[keep], d["bid"][keep], d["ask"][keep]

    def quotes(self, i, which):
        """bid, ask (float64) of file i under a quote model: 'raw' Dukascopy's own (0.001 grid), 'vt' the VT model: mid
        -/+ 0.075 x the tick's spread / the file's median spread, bid rounded to the cent, spread to whole cents, at
        least one (Dukascopy's spreads under about a thirtieth of its median, some 400-800 ticks a month, would give
        bid = ask, a quote VT never makes; the EA would then read a bar spread of 0)."""
        t, b, a = self._ticks(i)
        if which == "raw":
            return t, b / D.GOLD_DIV, a / D.GOLD_DIV
        spr = (a.astype(np.int64) - b.astype(np.int64)).astype(np.float64)
        med = self.medians[os.path.basename(self.files[i])]
        hs = D.VT_HALF * spr / med
        mid = (b.astype(np.int64) + a.astype(np.int64)) / (2 * D.GOLD_DIV)
        bid = np.round(mid - hs, 2)                      # VT quotes on the cent: bid to the cent, spread in whole points
        return t, bid, np.round(bid + np.maximum(np.round(2 * hs, 2), 0.01), 2)

    def _build(self, key):
        bars, rf, q0, q1 = [], [], [], []
        facts = {q: dict(hs=[], bh=[], al=[]) for q in ("vt", "raw")}
        self.medians = {}
        for i, fn in enumerate(self.files):
            t, b, a = self._ticks(i)
            if len(t) == 0:
                continue
            self.medians[os.path.basename(fn)] = float(np.median(a.astype(np.int64) - b.astype(np.int64)))
            st, mins = D._groups(t // 60000)
            en = np.r_[st[1:], len(t)]
            mid = (b.astype(np.int64) + a.astype(np.int64)) / (2 * D.GOLD_DIV)
            bars.append(pd.DataFrame(dict(open=mid[st], high=np.maximum.reduceat(mid, st), low=np.minimum.reduceat(mid, st),
                                          close=mid[en - 1]), index=pd.to_datetime(mins * 60000, unit="ms")))
            rf.append(np.full(len(st), i, np.int32)); q0.append(st); q1.append(en)
            for q in ("vt", "raw"):
                _, bid, ask = self.quotes(i, q)
                facts[q]["hs"].append(0.5 * (ask[st] - bid[st]))
                facts[q]["bh"].append(np.maximum.reduceat(bid, st))
                if SELL_BEST == "ask_low":
                    facts[q]["al"].append(np.minimum.reduceat(ask, st))
                else:
                    facts[q]["al"].append(np.minimum.reduceat(bid, st) + np.minimum.reduceat(ask - bid, st))
            print(f"  {os.path.basename(fn)}: {len(t):,} ticks, {len(st):,} minutes", flush=True)
        self.bars = pd.concat(bars)
        assert self.bars.index.is_monotonic_increasing and not self.bars.index.duplicated().any()
        self.row_file = np.concatenate(rf); self.row_q0 = np.concatenate(q0); self.row_q1 = np.concatenate(q1)
        self.facts = {q: {k: np.concatenate(v) for k, v in f.items()} for q, f in facts.items()}
        self.bars.to_pickle(key + "_bars.pkl")
        np.savez(key + "_facts.npz", row_file=self.row_file, row_q0=self.row_q0, row_q1=self.row_q1, medians=json.dumps(self.medians),
                 **{f"{q}_{k}": v for q, f in self.facts.items() for k, v in f.items()})

    def chunks(self):
        """(entry rows, files of the tick window) per UTC month: entries of file i, ticks of files i and i + 1."""
        for i in range(len(self.files)):
            rows = self.file_rows[i]
            if len(rows):
                yield i, rows, [i, i + 1] if i + 1 < len(self.files) else [i]

    def window(self, files, which):
        """Stream (mode 0) over the rows of the given files; rows outside are empty."""
        ts, bs, as_ = [], [], []
        rq0 = np.zeros(self.n, np.int64); rq1 = np.zeros(self.n, np.int64)
        off = 0
        last = 0
        for i in files:
            rows = self.file_rows[i]
            if not len(rows):                    # a file without ticks inside the span
                continue
            t, b, a = self.quotes(i, which)
            rq0[rows] = self.row_q0[rows] + off; rq1[rows] = self.row_q1[rows] + off
            ts.append(t); bs.append(b); as_.append(a); off += len(t)
            last = rows[-1] + 1 if len(rows) else last
        f = self.facts[which]
        st = K.Stream(0, rq0[:last], rq1[:last], f["bh"][:last], f["al"][:last], at=np.concatenate(ts), ab=np.concatenate(bs),
                      aa=np.concatenate(as_))
        used = [i for i in files if len(self.file_rows[i])]
        st.file_offsets = {i: int(o) for i, o in zip(used, np.cumsum([0] + [len(x) for x in ts])[:-1])}
        return st


class BtcSpan:
    """BTC seconds of a span (empty leading seconds removed), their one-minute bars (asserted equal to the study's
    Binance bars from April 2023 on; Jan - Mar 2023 lack some seconds) and one stream over the whole span."""

    def __init__(self, span, order=0):
        self.a, self.b = SPANS[SYM][span]
        ref = D.btc_reference_m1(self.a, self.b)
        self.sec = D.load_btc(self.a, self.b, ref)
        bars, st, en = D.btc_m1(self.sec)
        r = (ref.reindex(bars.index) * D.BTC_DIV).round()
        same = (bars.values == r.values).all(axis=1)
        self.bars_vs_ref = dict(minutes=int(len(bars)), identical=int(same.sum()), differ=int((~same).sum()),
                                differ_after_2023_03=int((~same & (bars.index >= pd.Timestamp("2023-04-01"))).sum()),
                                only_ref=int(len(ref.index.difference(bars.index))))
        assert self.bars_vs_ref["differ_after_2023_03"] == 0 and self.bars_vs_ref["only_ref"] == 0, self.bars_vs_ref
        self.bars = bars.astype(np.float64) / D.BTC_DIV
        self.n = len(self.bars)
        self.st, self.en = st, en
        self.order = order
        self.stream = K.second_stream(self.sec, st, en, D.BTC_HALF, D.BTC_DIV, order)
        self.facts = {"vt": dict(hs=np.full(self.n, D.BTC_HALF))}

    def chunks(self):
        yield 0, np.arange(self.n), [0]

    def window(self, files, which):
        return self.stream


# ----------------------------------------------------------------------------- the replay
def preset_rr(p):
    """The shipped presets' reward test (make_v135_presets.ea_inputs, LOMA_V135_CHANGES item 12): a fixed-RR setup whose
    minimum reward equals its target (tp_mode 1, min_rr = tp_rr) gets min_rr = tp_rr - 0.05, since at equality the
    floating-point arithmetic decides (module docstring). A copy of the settings."""
    q = dict(p)
    if int(q.get("tp_mode", 0)) == 1 and abs(float(q["min_rr"]) - float(q["tp_rr"])) < 1e-9:
        q["min_rr"] = round(float(q["tp_rr"]) - 0.05, 2)
    return q


def is_tie(p):
    return preset_rr(p)["min_rr"] != p["min_rr"]


def engine_cfg(p, extra, rr_rule=True):
    """Engine settings of a pick under a cost model's extras; rr_rule: with the presets' reward rule (preset_rr),
    False: the stored setting as is (the study's)."""
    c = dict(X.BASE); c.update(preset_rr(p) if rr_rule else p); c.update(extra)
    return X.engine_cfg(c)


def pf(r):
    return R.pf(np.asarray(r, float)) if len(r) else float("nan")


def replay(out_dir, span, cells="ea", models=None, worker=0, workers=1, order=0, tick_grid=0.0, max_picks=None):
    """Replay the picks of the cells ('ea': every cell of the EA's 14 systems; 'all': every cell; or a list of
    'TF:kind') on a span."""
    sym = SYM.lower()
    pk = json.load(open(os.path.join(out_dir, f"{sym}_picks.json")))
    if cells in (None, "ea"):
        ok = lambda c: c["kind"] in EA_KINDS
    elif cells == "all":
        ok = lambda c: True
    else:
        want = set(cells)
        ok = lambda c: f"{c['tf']}:{c['kind']}" in want
    picks = [(c["tf"], c["kind"], q) for c in pk["cells"] for q in c["picks"] if ok(c)]
    picks = picks[worker::workers]
    if max_picks:
        picks = picks[:max_picks]
    models = models or list(MODELS[SYM])

    def ea_of(m):                                        # tick_grid < 0: unrounded stops (simulate_y's arithmetic)
        g = MODELS[SYM][m]["grid"] if tick_grid == 0 else max(tick_grid, 0.0)
        return dict(EA_EXEC[SYM], tick=g, point=g if g > 0 else 0.01)
    t0 = time.time()
    sp = BtcSpan(span, order) if BTC else GoldSpan(span)
    print(f"{SYM} {span}: {sp.n:,} one-minute bars {sp.bars.index[0]} .. {sp.bars.index[-1]} ({time.time() - t0:.0f}s)", flush=True)
    per = periods(span, sp.bars.index[0])
    mks = {}
    for m in models:
        q = MODELS[SYM][m]["quotes"]
        if q not in mks:
            mks[q] = T2.MarketY(m1=sp.bars, half_spread=sp.facts[q]["hs"])
    tsec = sp.bars.index.values.astype("datetime64[ms]").astype(np.int64)
    # signals and one-minute trades of every pick and model
    jobs = {}
    for tf, kind, q in picks:
        for m in models:
            M = MODELS[SYM][m]
            mk = mks[M["quotes"]]
            prep_t = K.prepare(mk, engine_cfg(q["params"], M["extra"]), ea_rows=True)
            prep_y = K.prepare(mk, engine_cfg(q["params"], dict(M["extra"], **M["y_extra"])))
            y = K.run_y(mk, prep_y)
            y_raw = (K.run_y(mk, K.prepare(mk, engine_cfg(q["params"], dict(M["extra"], **M["y_extra"]), rr_rule=False)))
                     if is_tie(q["params"]) else None)    # the study's own setting (the stored trades)
            jobs[(q["key"], m)] = dict(tf=tf, kind=kind, q=q, prep=prep_t, y=y, y_raw=y_raw, state=(-1, 0, -1), tick=[])
    print(f"  {len(picks)} picks x {len(models)} models: signals and one-minute trades ({time.time() - t0:.0f}s)", flush=True)
    # ticks, chunk by chunk
    for ci, rows, files in sp.chunks():
        lo, hi = rows[0], rows[-1] + 1
        streams = {}
        for m in models:
            qn = MODELS[SYM][m]["quotes"]
            if qn not in streams:
                streams[qn] = sp.window(files, qn)
        for (key, m), J in jobs.items():
            st = streams[MODELS[SYM][m]["quotes"]]
            prep = J["prep"]
            e = prep["er"] + int(prep["c"]["delay"])
            sel = np.where((prep["er"] >= 0) & (e >= lo) & (e < hi))[0]
            if not len(sel):
                continue
            busy_file, busy_q, block = J["state"]
            bq = -1
            if busy_file >= 0 and BTC:
                bq = busy_q
            elif busy_file >= 0 and busy_file in getattr(st, "file_offsets", {}):
                bq = st.file_offsets[busy_file] + busy_q
            df = K.run_tick(mks[MODELS[SYM][m]["quotes"]], prep, st, ea_of(m), sel=sel, busy=(bq, block))
            if not len(df):
                continue
            last = df.iloc[-1]
            if int(last.reason) == 7 and len(st.rq0) < sp.n:
                raise SystemExit(f"{key} {m}: a trade is still open at the end of the tick window {files} (entry {last.entry_time})")
            if BTC:
                J["state"] = (0, int(last.exit_q), int(int(last.reason) in (3, 4, 5)))
            else:
                offs = st.file_offsets
                f = max(i for i, o in offs.items() if o <= int(last.exit_q))
                J["state"] = (f, int(last.exit_q) - offs[f], int(int(last.reason) in (3, 4, 5)))
            J["tick"].append(df)
        print(f"  chunk {ci}: rows {lo}..{hi}, files {files} ({time.time() - t0:.0f}s)", flush=True)
    # results
    rows_out, trades = [], []

    def one_minute(y):                                   # entry and exit times (ms) of simulate_y's trades
        return (y.entry_time.values.astype("datetime64[ms]").astype(np.int64),
                tsec[y.exit_row.astype(int).values] if len(y) else np.zeros(0, np.int64))
    for (key, m), J in jobs.items():
        tk = pd.concat(J["tick"]) if J["tick"] else pd.DataFrame(columns=K.COLS + ["entry_time"])
        engines = [("tick", tk, tk.entry_ms.values.astype(np.int64) if len(tk) else np.zeros(0, np.int64),
                    tk.exit_ms.values.astype(np.int64) if len(tk) else np.zeros(0, np.int64)), ("1m", J["y"], *one_minute(J["y"]))]
        if J["y_raw"] is not None:                       # tie picks: also the study's own setting (stored-trade check)
            engines.append(("1m_raw", J["y_raw"], *one_minute(J["y_raw"])))
        for eng, d, ent, ext in engines:
            r = d.r.values.astype(float) if len(d) else np.zeros(0)
            plab = np.full(len(ent), -1, np.int8)
            for pi, (lab, a, b) in enumerate(per):
                plab[(ent >= a.astype("datetime64[ms]").astype(np.int64)) & (ent < b.astype("datetime64[ms]").astype(np.int64))] = pi
            trades.append(pd.DataFrame(dict(key=key, model=m, engine=eng, entry_ms=ent, exit_ms=ext,
                                            side=d.side.values.astype(int) if len(d) else np.zeros(0, int), r=r,
                                            reason=d.reason.values.astype(int) if eng == "tick" and len(d) else np.zeros(len(d), int),
                                            period=plab)))
            for lab, a, b in per:
                sel = (ent >= a.astype("datetime64[ms]").astype(np.int64)) & (ent < b.astype("datetime64[ms]").astype(np.int64))
                rows_out.append(dict(key=key, tf=J["tf"], kind=J["kind"], model=m, engine=eng, period=lab, n=int(sel.sum()),
                                     pf=pf(r[sel]), net_r=float(r[sel].sum()), wins=int((r[sel] > 0).sum()),
                                     tie_rr=int(J["y_raw"] is not None)))
    res = pd.DataFrame(rows_out)
    tr = pd.concat(trades, ignore_index=True)
    tag = f"{sym}_{span}_w{worker}of{workers}" + (f"_order{order}" if order else "") + (f"_grid{tick_grid:g}" if tick_grid else "")
    res.to_csv(os.path.join(out_dir, f"{tag}_picks.csv"), index=False)
    keys = sorted(tr.key.unique()); kix = {k: i for i, k in enumerate(keys)}
    mods = sorted(tr.model.unique()); mix = {k: i for i, k in enumerate(mods)}
    np.savez_compressed(os.path.join(out_dir, f"{tag}_trades.npz"), keys=np.array(keys), models=np.array(mods),
                        periods=np.array([p_[0] for p_ in per]), period=tr.period.values.astype(np.int8),
                        key=tr.key.map(kix).values.astype(np.int32), model=tr.model.map(mix).values.astype(np.int8),
                        engine=tr.engine.map(ENGINES).values.astype(np.int8), entry_ms=tr.entry_ms.values.astype(np.int64),
                        exit_ms=tr.exit_ms.values.astype(np.int64), side=tr.side.values.astype(np.int8), r=tr.r.values.astype(np.float64),
                        reason=tr.reason.values.astype(np.int8))
    print(f"{SYM} {span}: {len(picks)} picks, {len(tr):,} trades written ({time.time() - t0:.0f}s)", flush=True)
    return res, tr


def load_trades(out_dir, pattern="*"):
    """Every trades file of the symbol (spans, workers) as one DataFrame with the key, model and period names."""
    import glob
    parts = []
    for fn in sorted(glob.glob(os.path.join(out_dir, f"{SYM.lower()}_{pattern}_trades.npz"))):
        z = np.load(fn)
        if "keys" not in z.files:                    # <sym>_picks_trades.npz: the stored trades of the picks
            continue
        keys, mods, pers = list(z["keys"]), list(z["models"]), list(z["periods"])
        df = pd.DataFrame(dict(key=np.array(keys, dtype=object)[z["key"]], model=np.array(mods, dtype=object)[z["model"]],
                               engine=np.array(list(ENGINES), dtype=object)[z["engine"]], entry_ms=z["entry_ms"], exit_ms=z["exit_ms"],
                               side=z["side"], r=z["r"], reason=z["reason"],
                               period=np.where(z["period"] >= 0, np.array(pers + ["none"], dtype=object)[z["period"]], "none"),
                               file=os.path.basename(fn)))
        parts.append(df)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def summarize(out_dir, pattern="*"):
    """Per cell (timeframe, trailing kind), cost model and period: pooled trades, PF and net R of the picks, ticks
    against one minute, and the change. Writes <sym>_cells.json / .csv."""
    tr = load_trades(out_dir, pattern)
    if not len(tr):
        print("no trades files"); return None
    tr["cell"] = tr.key.str.rsplit(":", n=1).str[0]
    pk = json.load(open(os.path.join(out_dir, f"{SYM.lower()}_picks.json")))
    tie = {q["key"] for c in pk["cells"] for q in c["picks"] if is_tie(q["params"])}
    rows = []
    for (cell, model, period), g in tr[tr.period != "none"].groupby(["cell", "model", "period"]):
        row = dict(cell=cell, tf=cell.split(":")[0], kind=cell.split(":")[1], model=model, period=period, picks=int(g.key.nunique()),
                   tie_picks=int(len(set(g.key) & tie)))         # picks run with the presets' reward rule (preset_rr)
        for eng in ("1m", "tick"):
            r = g[g.engine == eng].r.values
            row.update({f"{eng}_n": int(len(r)), f"{eng}_pf": pf(r), f"{eng}_net_r": float(r.sum()), f"{eng}_avg_r": float(r.mean()) if len(r) else float("nan")})
        row["d_net_r"] = row["tick_net_r"] - row["1m_net_r"]
        rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(out_dir, f"{SYM.lower()}_cells.csv"), index=False)
    json.dump(rows, open(os.path.join(out_dir, f"{SYM.lower()}_cells.json"), "w"), indent=1, default=float)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    print(res[["cell", "model", "period", "picks", "tie_picks", "1m_n", "tick_n", "1m_pf", "tick_pf", "1m_net_r", "tick_net_r",
               "d_net_r"]].round(3).to_string(index=False))
    return res


def verify_stored(out_dir, pattern="main_*"):
    """BTC, main span: the replay's one-minute trades must be the study's stored candidate trades (same Binance bars):
    model vt = the stored base trades, vt_stress = the stored stress trades (entry minute exactly, R to 2e-6). Tie
    picks (preset_rr changes min_rr) are checked on their run with the stored setting ('1m_raw'); the line under the
    check gives their trades with the presets' rule against the stored ones (the stored ones are short at tp_rr 1.5)."""
    tr = load_trades(out_dir, pattern)
    st = np.load(os.path.join(out_dir, f"{SYM.lower()}_picks_trades.npz"))
    pk = json.load(open(os.path.join(out_dir, f"{SYM.lower()}_picks.json")))
    tie = {q["key"]: q["params"]["tp_rr"] for c in pk["cells"] for q in c["picks"] if is_tie(q["params"])}
    ok = bad = 0; bad_keys = []; tie_rows = []
    for (key, model), g0 in tr[tr.engine.isin(["1m", "1m_raw"])].groupby(["key", "model"]):
        typ = {"vt": "base", "vt_stress": "stress"}.get(model)
        if typ is None:
            continue
        g = g0[g0.engine == ("1m_raw" if key in tie else "1m")]
        t_st = st[f"{key}:{typ}_t"].astype(np.int64); r_st = st[f"{key}:{typ}_r"].astype(np.float64)
        t_y = g.entry_ms.values // 60000
        same = len(t_y) == len(t_st) and np.array_equal(t_y, t_st) and np.allclose(g.r.values, r_st, rtol=0, atol=2e-6)
        ok += same; bad += not same
        if not same:
            bad_keys.append((key, model, len(t_y), len(t_st)))
        if key in tie:
            tie_rows.append(f"{key} (tp_rr {tie[key]:g}) {model}: {int((g0.engine == '1m').sum())} trades with the presets' rule, "
                            f"{len(t_st)} stored")
    line = f"{SYM}: one-minute trades of the replay equal to the stored candidate trades in {ok} of {ok + bad} pick x model runs"
    print(line, flush=True)
    for b in bad_keys[:20]:
        print("   differs:", b)
    for t in tie_rows:
        print("   tie pick:", t)
    return ok, bad, bad_keys


def order_check(out_dir, span, cells, model="vt"):
    """BTC: the four points of a second in the other order (the farther extreme first) against the replay's order
    (the nearer extreme first): trades whose exit time, exit price or R change."""
    assert BTC
    pk = json.load(open(os.path.join(out_dir, f"{SYM.lower()}_picks.json")))
    want = set(cells)
    picks = [(c["tf"], c["kind"], q) for c in pk["cells"] for q in c["picks"] if f"{c['tf']}:{c['kind']}" in want]
    sp = BtcSpan(span, 0)
    mk = T2.MarketY(m1=sp.bars, half_spread=sp.facts["vt"]["hs"])
    s1 = sp.stream.with_order(1)
    M = MODELS[SYM][model]
    ea = dict(EA_EXEC[SYM], tick=M["grid"], point=M["grid"])
    tot = changed = moved = 0; by = {}
    for tf, kind, q in picks:
        prep = K.prepare(mk, engine_cfg(q["params"], M["extra"]), ea_rows=True)
        a = K.run_tick(mk, prep, sp.stream, ea); b = K.run_tick(mk, prep, s1, ea)
        m = a.merge(b, on=["entry_q", "side"], how="outer", suffixes=("_a", "_b"), indicator=True)
        diff = ((m["_merge"] != "both") | ((m.exit_ms_a // 1000) != (m.exit_ms_b // 1000)) | ((m.exit_px_a - m.exit_px_b).abs() > 1e-9)
                | ((m.r_a - m.r_b).abs() > 1e-9))
        n = int(len(a)); c = int(diff.sum())
        tot += n; changed += c; moved += int(((m.exit_ms_a // 60000) != (m.exit_ms_b // 60000)).sum())
        by.setdefault(kind, [0, 0]); by[kind][0] += n; by[kind][1] += c
    line = (f"{SYM} {span}: order of the two extremes inside a second: {changed} of {tot} trades change (exit second, price or R; "
            f"{moved} leave in another minute) when the farther extreme comes first; by kind " +
            ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in by.items()))
    print(line, flush=True)
    json.dump(dict(span=span, cells=cells, model=model, trades=tot, changed=changed, other_minute=moved, by_kind=by, line=line),
              open(os.path.join(out_dir, f"{SYM.lower()}_{span}_order_check.json"), "w"), indent=1)
    return line


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "summary":
        summarize(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "*")
    elif cmd == "stored":                # stored <out_dir> [pattern]: BTC main span, one-minute trades = the study's
        verify_stored(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "main_*")
    elif cmd == "order":                 # order <out_dir> <span> <cells>
        order_check(sys.argv[2], sys.argv[3], sys.argv[4].split(","))
    elif cmd == "picks":
        derive_picks(sys.argv[2], sys.argv[3], sys.argv[4].split(",") if len(sys.argv) > 4 else None)
    elif cmd == "run":                   # run <out_dir> <span> <cells|all|ea> <models|all> [worker workers] [order] [tick_grid]
        cells = sys.argv[4] if sys.argv[4] in ("all", "ea") else sys.argv[4].split(",")
        models = None if sys.argv[5] == "all" else sys.argv[5].split(",")
        w, ws = (int(sys.argv[6]), int(sys.argv[7])) if len(sys.argv) > 7 else (0, 1)
        replay(sys.argv[2], sys.argv[3], cells, models, w, ws, int(sys.argv[8]) if len(sys.argv) > 8 else 0,
               float(sys.argv[9]) if len(sys.argv) > 9 else 0.0)
