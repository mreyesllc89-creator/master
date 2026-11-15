#!/usr/bin/env python3
"""probe_flow_proxy.py -- can the live order-flow verdict (:FA / :FD / none on the order comment) be
reproduced from tick data?

usage:   python3 -I probe_flow_proxy.py <repo_path> [--boot 1000] [--seed 11] [--quick]
         python3 -I probe_flow_proxy.py --selftest                      (unit checks of the helpers, no data needed)
runtime  about 40 s on one core for --boot 1000 (about 13 s with --quick); the output is bit-identical for a given --seed

reads    <repo_path>/results/real/real_trades_sar.csv               (2,584 real trades, broker SERVER time = UTC+3)
         <repo_path>/data/raw/XAUUSD/YYYY-MM-DD/HH.bi5               (Dukascopy hourly ticks with quote sizes)
writes   probe_flow_proxy_features.csv   (one row per analysed real market entry: label, outcome, every feature, out-of-sample proxy)
         probe_flow_proxy_metrics.csv    (one row per reported number: section, n, estimate, 95% CI, note with the definition)
         both next to this script.  Nothing else is read or written.  Needs only numpy and pandas (no scipy / sklearn).
companions (same folder, no dependence on this script):  verify_flow_label_algebra.py (enumerates the EA's score/router/label rules),
         check_hf_sizes.py (do the data/hf quote sizes behave like the raw ones?)

What it measures (the notes column of the metrics file gives the exact definitions):
  1. base rates of the label overall, by scenario and by action, plus the timezone check of the trade stamps
  2. for market entries (BM/SM) whose entry hour exists in data/raw: ~350 candidate features from the ticks (mid change,
     tick-rule imbalance, quote-update imbalance, quote-size imbalance, microprice, their changes, combinations, the EA's own
     body / micro-break / 10 s gates) over windows of 0.5 .. 30 s ending at three candidate decision times, all sign-aligned
     with the trade side
  3. AUC of each feature for agrees-vs-disagrees and (|x|) none-vs-not-none (inside BM, where none can occur) with cluster
     bootstrap CIs (cluster = UTC hour), a family-wise label-permutation check, and a planted-signal power check
  4. the honest out-of-sample numbers: walk-forward select-then-test AUC (overall and per feature family), 3-class
     threshold-rule accuracy against three baselines, ridge-logistic and hour-of-day / label-history "stochastic label
     models" scored by log-loss against the base-rate model
  5. the selection structure (weak-flow gate: body and micro-break required for :FD and none), the share of entries with
     the 10 s move, serial and time-of-day structure of the labels
  6. whether the label predicts the trade result (realised points and the label-independent forward mid move) before and
     after controlling for the best out-of-sample proxy, split by buy/sell (the sign flips with the market drift), whether
     the feed's absolute buy/sell verdict predicts the next 5-30 s mid move, and the mean price path around the fill
  7. a lag scan (AUC against the window end time) and an exploratory block for stop-order entries

Timing facts the script is built around (verified in the EA source, see NOTES below):
  * the real order comment is built from the DirectionState captured when the entry hold was ARMED
    (ArmEntryHold stores `entryHoldDirectionState`; ProcessArmedEntryHold passes it to PlaceAction).  With
    InpUseEntryHold=true and InpEntryHoldMs=1100 (the account's inputs) the label describes the feed >= 1.1 s
    BEFORE the order was sent, not 150 ms before the fill.
  * open_time in the trade list has 1 s resolution (floor), so every decision time is uncertain by +-0.5 s.
  Three anchors are therefore evaluated (offsets in ms from the stamped second T, UTC):
      lit = T - 150          the literal brief:  entry time minus the 150 ms order round trip
      rel = T + 350          unbiased estimate of the order-send moment (fill ~ T+500 minus 150)
      arm = T - 900          unbiased estimate of the hold-arming moment (order send minus ~1.25 s)
"""
import argparse
import datetime as dt
import glob
import lzma
import os
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REC = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("av", ">f4"), ("bv", ">f4")])
SERVER_UTC_OFFSET_H = 3          # broker server time = UTC+3 (re-verified by the tz_check rows)
WINDOWS_MS = [500, 1000, 2000, 3000, 5000, 10000, 30000]
ANCHORS = {"lit": -150, "rel": 350, "arm": -900}
LAG_SCAN_MS = list(range(-3000, 1001, 250))
POINT = 10                       # 1 EA point = 0.01 USD = 10 units of the 1e-3 integer prices
MIN_BODY_PTS, MICRO_BUF_PTS = 21.0, 3.0   # MinCandleBodyPoints, MicroBreakBufferPoints (shipped values)
FEATS_SIGNED = ["mv", "mvs", "ti", "tin", "qa", "qb", "qd", "ql", "sim", "sil", "mpp", "mps", "dsi", "dsh"]
FEATS_UNSIGNED = ["nt", "rate", "spr", "rng"]
SIZE_FEATS = {"sim", "sil", "mpp", "mps", "dsi", "dsh", "call"}      # need Dukascopy quote sizes (absent in the MT5 tester)
FEAT_DOC = {
    "mv": "mid change over the window, points, x side",
    "mvs": "mid change / mean spread (Dukascopy spread), x side",
    "ti": "tick rule: (#mid up-ticks - #mid down-ticks), x side",
    "tin": "tick rule normalised: (up-down)/(up+down), x side",
    "qa": "ask quote updates: (#ask up - #ask down), x side",
    "qb": "bid quote updates: (#bid up - #bid down), x side",
    "qd": "quote-update direction imbalance: (qa+qb)/(#ask changes+#bid changes), x side",
    "ql": "ask-led minus bid-led: (qa-qb)/(#ask changes+#bid changes), x side",
    "sim": "size imbalance (bidsize-asksize)/(bidsize+asksize), mean over the window, x side",
    "sil": "size imbalance of the last tick, x side",
    "mpp": "microprice minus mid, points, x side",
    "mps": "microprice minus mid in spread units, x side (algebraically identical to sil/2: checked numerically)",
    "dsi": "change of the size imbalance: last tick minus the tick at window start, x side",
    "dsh": "change of the size imbalance: mean of 2nd half minus mean of 1st half of the window, x side",
    "nt": "number of ticks in the window (activity)",
    "rate": "ticks per second in the window",
    "spr": "mean Dukascopy spread in the window, points (wide: ~65 against ~12-15 at the broker)",
    "rng": "mid high-low range in the window, points",
    "cpx": "unit-weight sum of z(mvs)+z(tin)+z(qd) (z from the feature's own distribution, no label)",
    "call": "cpx + z(sim) + z(dsi)",
    "body": "EA gate: M1 body with the trade, points (mid now minus the bid at the minute start)",
    "micro": "EA gate: margin of the mid over the previous 10 s extreme (current tick excluded), points, with the trade",
    "mv10": "EA gate: 10 s mid move with the trade, points",
    "sprl": "spread of the last tick, points (Dukascopy)",
}

# --------------------------------------------------------------------------------------------------------------
# NOTES -- source facts (SpeedAlert_FlashGold_Micro.mq5 v1.501; PARENT_EA_SOURCE.txt v1.499 has identical code)
#   ScoreOrderFlow 2463-2493: used only if UseOrderFlow, OK>=0.5 and (GetTickCount64-HEARTBEAT)<=MaxFlowAgeMs (4000);
#       flowFresh=true; reads FORCE_IMB, NEAR_IMB, BOOK_IMB; AddFlowVote 2556: |v| >= MinFlowImbalance (5.0) -> buy vote
#       (v>0) or sell vote (v<0), each adding FlowComponentScore (1.0) to that side's score; buyVotes>=2 -> flowDir=+1,
#       else sellVotes>=2 -> -1, else 0.
#   BuildDirectionState 2344-2346: winner = WinnerSide (score >= MinDirectionScore 4.0 and lead >= MinScoreEdge 1.5);
#       flowAgreesWithWinner = (winner != 0 && flowDir == winner); flowDisagreesWithWinner = (winner != 0 && flowDir == -winner).
#       => the label is relative to the score WINNER: equal to the trade side for market and stop-with-burst entries,
#          NOT for limit (fade) entries.
#   ShortComment 3137-3143: ":FA" / ":FD" / nothing (nothing also when winner == 0, flowDir == 0, feed stale or absent).
#   DecideAction 2742-2767, MarketEntryAllowedByFlow 2770-2789: a market order needs speedDir == winner and follow21 or
#       follow37, then: strong flow (fresh and flowDir == winner) -> allowed; weak flow (neutral, stale or disagreeing) ->
#       only with body AND micro-break with the winner AND score >= 5.0 AND edge >= 2.0; a SELL with neutral flow is
#       downgraded to a stop (DowngradeNeutralSellMarketToStop=true on the account).  Hence: every market entry has >= 1
#       flow vote with the trade; market+FD <=> exactly (1 vote with, 2 against); market+none <=> fresh feed, exactly 1
#       vote with the trade, buys only; market+FA <=> >= 2 votes with the trade; no market entry with a stale feed.
#   ArmEntryHold 1770-1785, ProcessArmedEntryHold 1788-1883: with InpUseEntryHold the DirectionState (flow included) is
#       stored when the hold is armed and the order, comment included, is sent from that stored state after >= 1100 ms.
# --------------------------------------------------------------------------------------------------------------


# ============================== data ============================================================================
def read_hour(raw_root, base_ms):
    d = dt.datetime.fromtimestamp(base_ms / 1000, dt.timezone.utc)
    p = os.path.join(raw_root, d.strftime("%Y-%m-%d"), f"{d.hour:02d}.bi5")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    a = np.frombuffer(lzma.decompress(open(p, "rb").read()), dtype=REC)
    return (base_ms + a["ms"].astype(np.int64), a["bid"].astype(np.int64), a["ask"].astype(np.int64),
            a["bv"].astype(np.float64), a["av"].astype(np.float64))


class TickStore:
    def __init__(self, raw_root):
        self.root, self.cache = raw_root, {}

    def hour(self, base):
        if base not in self.cache:
            if len(self.cache) > 6:
                self.cache.pop(next(iter(self.cache)))
            self.cache[base] = read_hour(self.root, base)
        return self.cache[base]

    def window(self, lo_ms, hi_ms):
        parts, b = [], (lo_ms // 3600000) * 3600000
        while b <= hi_ms:
            h = self.hour(b)
            if h is not None:
                parts.append(h)
            b += 3600000
        if not parts:
            return None
        tk = tuple(np.concatenate([p[k] for p in parts]) for k in range(5))
        m = (tk[0] >= lo_ms) & (tk[0] <= hi_ms)
        return tuple(x[m] for x in tk) if m.any() else None


def hours_available(raw_root):
    out = set()
    for p in glob.glob(os.path.join(raw_root, "*", "*.bi5")):
        day, hh = os.path.basename(os.path.dirname(p)), int(os.path.basename(p)[:2])
        out.add(int(dt.datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), hh, tzinfo=dt.timezone.utc).timestamp() * 1000))
    return out


# ============================== features ========================================================================
def window_raw(tk, a, W):
    """Unsigned base quantities for the window (a-W, a]; None when the quote is stale or the window is not covered."""
    t, bid, ask, bv, av = tk
    je = np.searchsorted(t, a, side="right") - 1
    j0 = np.searchsorted(t, a - W, side="right") - 1
    if je < 0 or j0 < 0 or a - t[je] > 3000 or (a - W) - t[j0] > 60000:
        return None
    sl = slice(j0, je + 1)                       # index 0 = the quote prevailing at the window start, then the ticks inside
    b, k = bid[sl], ask[sl]
    mid2 = b + k
    d = np.diff(mid2)
    da, db = np.diff(k), np.diff(b)
    si = (bv[sl] - av[sl]) / np.maximum(bv[sl] + av[sl], 1e-12)
    tt = t[sl]
    sim = si[1:].mean() if len(si) > 1 else si[-1]
    jm = np.searchsorted(tt, a - W // 2, side="right") - 1          # last quote at/before the half point (>= 0)
    first = si[1:jm + 1] if jm >= 1 else si[:1]
    second = si[jm + 1:] if jm + 1 < len(si) else si[jm:jm + 1]
    bl, kl, bvl, avl = b[-1], k[-1], bv[sl][-1], av[sl][-1]
    micro = (bl * avl + kl * bvl) / max(avl + bvl, 1e-12)             # standard microprice: ask price weighted by BID size
    mid_l = (bl + kl) / 2.0
    spread = (k - b).astype(float)
    return dict(dmid=(mid2[-1] - mid2[0]) / 2.0 / POINT, up=int((d > 0).sum()), dn=int((d < 0).sum()),
                qa=int((da > 0).sum() - (da < 0).sum()), qb=int((db > 0).sum() - (db < 0).sum()),
                na=int((da != 0).sum()), nb=int((db != 0).sum()),
                sim=sim, sil=si[-1], dsi=si[-1] - si[0], dsh=second.mean() - first.mean(),
                mpp=(micro - mid_l) / POINT, mps=(micro - mid_l) / max(kl - bl, 1.0),
                nt=int(je - j0), spr=(spread[1:].mean() if len(spread) > 1 else spread[-1]) / POINT,
                rng=(mid2.max() - mid2.min()) / 2.0 / POINT, sprl=spread[-1] / POINT)


def align(raw, side, W):
    """Side-aligned features: positive = 'with the trade'."""
    spr = max(raw["spr"], 0.1)
    n_ch = max(raw["na"] + raw["nb"], 1)
    return {"mv": side * raw["dmid"], "mvs": side * raw["dmid"] / spr,
            "ti": side * (raw["up"] - raw["dn"]), "tin": side * (raw["up"] - raw["dn"]) / max(raw["up"] + raw["dn"], 1),
            "qa": side * raw["qa"], "qb": side * raw["qb"],
            "qd": side * (raw["qa"] + raw["qb"]) / n_ch, "ql": side * (raw["qa"] - raw["qb"]) / n_ch,
            "sim": side * raw["sim"], "sil": side * raw["sil"], "mpp": side * raw["mpp"], "mps": side * raw["mps"],
            "dsi": side * raw["dsi"], "dsh": side * raw["dsh"],
            "nt": raw["nt"], "rate": raw["nt"] / (W / 1000.0), "spr": raw["spr"], "rng": raw["rng"]}


def pattern(tk, a, side):
    """The EA's price gates at time a from Dukascopy ticks (an approximation of the broker feed): M1 body against the bar
    open (MT5 bars are built from the bid), break of the previous 10 s high/low (current tick excluded), 10 s move."""
    t, bid, ask = tk[0], tk[1], tk[2]
    j = np.searchsorted(t, a, side="right") - 1
    if j < 0 or a - t[j] > 3000:
        return None
    mid2 = (bid + ask).astype(float)
    k = min(np.searchsorted(t, (a // 60000) * 60000, side="left"), j)
    body = (mid2[j] / 2.0 - bid[k]) / POINT * side
    i10 = np.searchsorted(t, a - 10000, side="left")
    if j - 1 >= i10:
        hi, lo = mid2[i10:j].max() / 2.0, mid2[i10:j].min() / 2.0
        micro = ((mid2[j] / 2.0 - hi) if side > 0 else (lo - mid2[j] / 2.0)) / POINT
    else:
        micro = np.nan
    j10 = np.searchsorted(t, a - 10000, side="right") - 1
    mv10 = (mid2[j] - mid2[j10]) / 2.0 / POINT * side if j10 >= 0 else np.nan
    return {"body": body, "micro": micro, "mv10": mv10, "sprl": (ask[j] - bid[j]) / POINT}


def mid_at(tk, a):
    """mid in 1e-3 price units of the last tick at/before a (None-safe)."""
    if tk is None:
        return np.nan
    j = np.searchsorted(tk[0], a, side="right") - 1
    if j < 0 or a - tk[0][j] > 3000:
        return np.nan
    return (tk[1][j] + tk[2][j]) / 2.0


# ============================== statistics ======================================================================
class Presorted:
    """AUC of one candidate on a fixed row set, re-evaluable under integer row weights without re-sorting."""

    def __init__(self, x, y):
        vi = np.flatnonzero(np.isfinite(x))
        o = np.argsort(x[vi], kind="mergesort")
        self.vo = vi[o]
        xs = x[self.vo]
        self.y = np.asarray(y, float)[self.vo]
        self.g = np.flatnonzero(np.r_[True, xs[1:] != xs[:-1]]) if len(xs) else np.array([], int)

    def auc(self, w=None):
        if len(self.vo) == 0:
            return np.nan
        ws = np.ones(len(self.vo)) if w is None else np.asarray(w)[self.vo].astype(float)
        wp = np.add.reduceat(ws * self.y, self.g)
        wn = np.add.reduceat(ws * (1.0 - self.y), self.g)
        Wp, Wn = wp.sum(), wn.sum()
        if Wp <= 0 or Wn <= 0:
            return np.nan
        cn = np.cumsum(wn) - wn
        return float((wp * (cn + 0.5 * wn)).sum() / (Wp * Wn))

    def auc_y(self, ynew):
        """Same sort order, different labels (label-permutation null)."""
        yv = np.asarray(ynew, float)[self.vo]
        wp = np.add.reduceat(yv, self.g)
        wn = np.add.reduceat(1.0 - yv, self.g)
        Wp, Wn = wp.sum(), wn.sum()
        if Wp <= 0 or Wn <= 0:
            return np.nan
        cn = np.cumsum(wn) - wn
        return float((wp * (cn + 0.5 * wn)).sum() / (Wp * Wn))


def auc_plain(x, y):
    return Presorted(np.asarray(x, float), np.asarray(y, float)).auc()


def boot_weights(cluster, B, rng):
    """Cluster bootstrap weights: B x n (row weight = number of times its cluster was drawn)."""
    u, inv = np.unique(cluster, return_inverse=True)
    K = len(u)
    W = np.empty((B, len(cluster)), dtype=np.int32)
    for b in range(B):
        W[b] = np.bincount(rng.integers(0, K, K), minlength=K)[inv]
    return W


def ci(vals):
    v = np.asarray(vals, float)
    v = v[np.isfinite(v)]
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if len(v) >= 20 else (np.nan, np.nan)


def fit_logit(X, y, lam, iters=40):
    """Ridge logistic regression by IRLS; X standardised, intercept unpenalised."""
    n, p = X.shape
    Z = np.c_[np.ones(n), X]
    beta = np.zeros(p + 1)
    pen = np.r_[0.0, np.full(p, lam)]
    for _ in range(iters):
        mu = 1.0 / (1.0 + np.exp(-np.clip(Z @ beta, -30, 30)))
        wv = np.maximum(mu * (1 - mu), 1e-6)
        step = np.linalg.solve(Z.T @ (Z * wv[:, None]) + np.diag(pen), Z.T @ (y - mu) - pen * beta)
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def predict_logit(beta, X):
    return 1.0 / (1.0 + np.exp(-np.clip(np.c_[np.ones(len(X)), X] @ beta, -30, 30)))


def logloss_vec(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def wilson(k, n):
    if n == 0:
        return (np.nan, np.nan)
    p, z = k / n, 1.96
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (float(c - h), float(c + h))


class Out:
    def __init__(self):
        self.rows = []

    def add(self, section, name, est=np.nan, lo=np.nan, hi=np.nan, n=np.nan, n_pos=np.nan, n_neg=np.nan,
            anchor="", window_s=np.nan, note=""):
        self.rows.append(dict(section=section, name=name, anchor=anchor, window_s=window_s, n=n, n_pos=n_pos,
                              n_neg=n_neg, estimate=est, ci_lo=lo, ci_hi=hi, note=note))

    def frame(self):
        return pd.DataFrame(self.rows)


# ============================== self-test =======================================================================
def selftest():
    rs = np.random.default_rng(5)
    # 1. AUC with ties and integer weights against the O(n^2) definition
    x = rs.integers(0, 6, 200).astype(float)
    y = (rs.random(200) < 0.3 + 0.1 * x / 5).astype(float)
    w = rs.integers(0, 4, 200)
    xp, xn = np.repeat(x[y == 1], w[y == 1]), np.repeat(x[y == 0], w[y == 0])
    brute = ((xp[:, None] > xn[None, :]).sum() + 0.5 * (xp[:, None] == xn[None, :]).sum()) / (len(xp) * len(xn))
    assert abs(Presorted(x, y).auc(w) - brute) < 1e-12, "weighted AUC"
    assert abs(Presorted(x, y).auc_y(y) - Presorted(x, y).auc()) < 1e-12, "auc_y"
    # 2. window features on a hand-made tape (units: 1e-3 price integers, ms)
    t = np.array([0, 100, 200, 300, 400, 500], dtype=np.int64)
    bid = np.array([1000, 1010, 1010, 1000, 1020, 1030], dtype=np.int64)
    ask = bid + 50
    bv = np.array([1, 2, 3, 4, 5, 6], dtype=float) * 1e-4
    av = np.array([1, 1, 1, 1, 1, 1], dtype=float) * 1e-4
    r = window_raw((t, bid, ask, bv, av), 500, 300)            # window (200, 500]: base = tick at t=200, then 300, 400, 500
    assert r["nt"] == 3 and r["up"] == 2 and r["dn"] == 1, r        # mids: 1035 -> 1025 -> 1045 -> 1055
    assert r["qa"] == 1 and r["qb"] == 1 and r["na"] == 3 and r["nb"] == 3, r          # ask/bid: -10, +20, +10
    assert abs(r["dmid"] - (1055 - 1035) / POINT) < 1e-12
    si = (bv - av) / (bv + av)
    assert abs(r["sim"] - si[3:6].mean()) < 1e-12 and abs(r["sil"] - si[5]) < 1e-12 and abs(r["dsi"] - (si[5] - si[2])) < 1e-12
    assert abs(r["mps"] - r["sil"] / 2.0) < 1e-12, "microprice identity"
    assert align(r, -1, 300)["mv"] == -r["dmid"] and align(r, 1, 300)["ti"] == 1
    assert window_raw((t, bid, ask, bv, av), 500, 900) is None        # no quote before the window start
    # 3. wilson and the ridge logistic fit
    lo, hi = wilson(50, 100)
    assert abs(lo - 0.4038) < 1e-3 and abs(hi - 0.5962) < 1e-3
    X = rs.normal(size=(2000, 2))
    yy = (rs.random(2000) < 1 / (1 + np.exp(-(0.5 + 1.5 * X[:, 0])))).astype(float)
    beta = fit_logit(X, yy, 1e-6)
    assert abs(beta[1] - 1.5) < 0.3 and abs(beta[2]) < 0.3 and abs(beta[0] - 0.5) < 0.2, beta
    print("selftest passed")


# ============================== main ============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--quick", action="store_true", help="B=200, no lag scan / stop-order block (smoke test)")
    ap.add_argument("--selftest", action="store_true", help="run the unit checks of the helpers and exit")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.repo:
        ap.error("repo path required")
    B = 200 if args.quick else args.boot
    rng = np.random.default_rng(args.seed)
    t_start = time.time()
    raw_root = os.path.join(args.repo, "data", "raw", "XAUUSD")
    out = Out()

    def log(msg):
        print(f"[{time.time() - t_start:6.1f}s] {msg}", flush=True)

    # ---------------------------------------------------------------- trades and coverage
    tr = pd.read_csv(os.path.join(args.repo, "results", "real", "real_trades_sar.csv"), parse_dates=["open_time", "close_time"])
    tr["T"] = (tr.open_time - pd.Timedelta(hours=SERVER_UTC_OFFSET_H)).astype("datetime64[s]").astype("int64") * 1000
    assert ((tr.action.isin(["BM", "BS", "BL"])) == (tr.side == 1)).all(), "side/action mismatch"
    tr["lab"] = tr.flow.map({"agrees": 1, "disagrees": -1, "none": 0}).astype(int)
    avail = hours_available(raw_root)
    store = TickStore(raw_root)
    out.add("sample", "real trades in csv", n=len(tr), note="7 Sep - 8 Oct 2026, server time UTC+3")

    def rates(df, section, tag):
        n = len(df)
        for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
            k = int((df.lab == lab_v).sum())
            lo, hi = wilson(k, n)
            out.add(section, f"{tag}: share {nm}", est=k / n if n else np.nan, lo=lo, hi=hi, n=n, n_pos=k,
                    note="Wilson 95% interval; trades the EA actually took (conditional sample)")

    rates(tr, "base_rate_all", "all real trades")
    for sc in ["FOLM", "FLXQ", "EXHL"]:
        rates(tr[tr.scenario == sc], "base_rate_scenario", f"scenario {sc}")
    rates(tr[tr.scenario != "FOLM"], "base_rate_scenario", "scenario not FOLM")
    rates(tr[tr.scenario.isin(["CONT", "BNO", "OTHER"])], "base_rate_scenario", "scenario CONT/BNO/OTHER")
    for ac in ["BM", "SM", "BS", "SS", "BL", "SL"]:
        rates(tr[tr.action == ac], "base_rate_action", f"action {ac}")
    mk_all = tr[tr.action.isin(["BM", "SM"])].copy()
    rates(mk_all, "base_rate_market", "market entries BM+SM, all")

    def covered(r):
        hb = (r["T"] // 3600000) * 3600000
        hours = [hb] + ([hb - 3600000] if (r["T"] - hb) < 60000 else [])
        if not any(h in avail for h in hours):
            return False
        return store.window(r["T"] - 3000, r["T"] + 3000) is not None

    tr = tr.sort_values("T").reset_index(drop=True)
    tr["covered"] = tr.apply(covered, axis=1)
    mk = tr[tr.action.isin(["BM", "SM"]) & tr.covered].copy().reset_index(drop=True)
    pend = tr[tr.action.isin(["BS", "SS"]) & tr.covered].copy().reset_index(drop=True)
    out.add("sample", "market entries with ticks (analysed)", n=len(mk),
            note="BM/SM, entry hour (or the previous hour for entries in the first 60 s) in data/raw, >= 1 tick within 3 s of the stamped second")
    rates(mk, "base_rate_market", "market entries covered by ticks")
    rates(mk[mk.action == "BM"], "base_rate_market", "covered BM")
    rates(mk[mk.action == "SM"], "base_rate_market", "covered SM")
    out.add("sample", "stop-order entries BS/SS with ticks (exploratory block)", n=len(pend))
    out.add("sample", "distinct UTC hours (bootstrap clusters), analysed market sample", n=int(mk["T"].floordiv(3600000).nunique()))

    # timezone check: |entry price - Dukascopy mid| if the server offset were 2, 3 or 4 hours
    cov_tr = tr[tr.covered].sample(min(400, int(tr.covered.sum())), random_state=3)
    for off in (2, 3, 4):
        e = []
        for _, r in cov_tr.iterrows():
            Tm = int((r.open_time - pd.Timedelta(hours=off)).tz_localize("UTC").timestamp() * 1000) + 500
            m = mid_at(store.window(Tm - 3000, Tm + 3000), Tm)
            if np.isfinite(m):
                e.append(abs(r.entry - m / 1000.0))
        out.add("tz_check", f"median |entry price - Dukascopy mid| if server time = UTC+{off}", est=float(np.median(e)) if e else np.nan,
                n=len(e), note="USD; UTC+3 gives ~0.08 (about half the broker spread), the others ~9-12")

    # ---------------------------------------------------------------- per-trade features
    log(f"building features for {len(mk)} market entries ...")
    rows, mps_err = [], 0.0
    for _, r in mk.iterrows():
        T, sd = int(r["T"]), int(r["side"])
        tk = store.window(T - 125000, T + 40000)
        row = dict(open_time_server=str(r.open_time), T_utc_ms=T, hour_id=T // 3600000, side=sd, action=r.action,
                   scenario=r.scenario, flow=r.flow, lab=int(r.lab), pts=r.pts, exit_kind=r.exit_kind, hold_s=r.hold_s,
                   entry=r.entry)
        m0 = mid_at(tk, T + 500)
        for k in (5, 10, 30):
            m1 = mid_at(tk, T + 500 + k * 1000)
            row[f"fwd{k}"] = (m1 - m0) / POINT * sd if np.isfinite(m0) and np.isfinite(m1) else np.nan
        for nm_, (o1, o2) in (("leg_a", (-3400, -2150)), ("leg_b", (-2150, -900)), ("leg_c", (-900, 350)), ("leg_d", (350, 1600)), ("leg_e", (1600, 2850))):
            ma_, mb_ = mid_at(tk, T + o1), mid_at(tk, T + o2)
            row[nm_] = (mb_ - ma_) / POINT * sd if np.isfinite(ma_) and np.isfinite(mb_) else np.nan
        grid = [pattern(tk, T + o, sd) for o in range(-1400, -399, 100)]       # the weak-flow gate is evaluated at the arming tick
        grid = [g for g in grid if g]
        if grid:
            row["armgrid_g_body_max"] = max(g["body"] for g in grid)
            row["armgrid_g_micro_max"] = np.nanmax([g["micro"] for g in grid]) if np.isfinite([g["micro"] for g in grid]).any() else np.nan
        for an, off in ANCHORS.items():
            a = T + off
            pt = pattern(tk, a, sd)
            if pt:
                row.update({f"{an}_g_{k}": v for k, v in pt.items()})
            for W in WINDOWS_MS:
                raw = window_raw(tk, a, W)
                if raw is None:
                    continue
                mps_err = max(mps_err, abs(raw["mps"] - raw["sil"] / 2.0))
                row.update({f"{an}_{W}_{k}": v for k, v in align(raw, sd, W).items()})
        rows.append(row)
    F = pd.DataFrame(rows).sort_values("T_utc_ms").reset_index(drop=True)
    out.add("check", "max |microprice minus mid in spread units - size imbalance/2| over all rows and windows", est=mps_err, n=len(F),
            note="~1e-12: exact algebraic identity, so feature (5) is redundant with the last size imbalance of (4)")
    for an in ANCHORS:
        F[f"{an}_g_body_ok"] = (F[f"{an}_g_body"] >= MIN_BODY_PTS).astype(float).where(F[f"{an}_g_body"].notna())
        F[f"{an}_g_micro_ok"] = (F[f"{an}_g_micro"] > MICRO_BUF_PTS).astype(float).where(F[f"{an}_g_micro"].notna())
        for W in WINDOWS_MS:
            def z(c):
                v = F[f"{an}_{W}_{c}"]
                return (v - v.mean()) / (v.std() + 1e-12)
            F[f"{an}_{W}_cpx"] = z("mvs") + z("tin") + z("qd")
            F[f"{an}_{W}_call"] = F[f"{an}_{W}_cpx"] + z("sim") + z("dsi")
    n = len(F)
    clus = F["hour_id"].values
    lab = F["lab"].values.astype(int)
    isBM = (F["action"] == "BM").values
    K, FIRST_TEST = 6, 2                                   # chronological blocks; blocks 0-1 are train-only
    blk = (np.arange(n) * K) // n                          # F is sorted by time
    log(f"features done: {n} rows x {F.shape[1]} columns")

    sig_cols = [f"{an}_{W}_{f}" for an in ANCHORS for W in WINDOWS_MS for f in FEATS_SIGNED + ["cpx", "call"]]
    uns_cols = [f"{an}_{W}_{f}" for an in ANCHORS for W in WINDOWS_MS for f in FEATS_UNSIGNED]
    gate_cols = [f"{an}_g_{k}" for an in ANCHORS for k in ("body", "micro", "mv10", "sprl")]

    def parse(c):
        p = c.split("_")
        return p[0], (np.nan if p[1] == "g" else int(p[1]) / 1000.0), p[2]

    def mt5_ok(c):
        return "yes" if parse(c)[2] not in SIZE_FEATS else "no (needs quote sizes)"

    FA, FD, FN = lab == 1, lab == -1, lab == 0
    out.add("sample", "analysed market entries: n_pos = agrees, n_neg = disagrees", n=n, n_pos=int(FA.sum()), n_neg=int(FD.sum()),
            note=f"none = {int(FN.sum())}; none occurs only for BM (a SELL market with neutral flow is downgraded to a stop)")

    t1 = FA | FD                                           # task 1 rows
    y1 = FA[t1].astype(float)
    w1 = boot_weights(clus[t1], B, rng)
    t2 = isBM                                              # task 2 rows (none is only possible for buys)
    y2 = FN[t2].astype(float)
    w2 = boot_weights(clus[t2], B, rng)
    wall = boot_weights(clus, B, rng)                     # all analysed rows
    # label history: label of the previous real trade (any route) if it happened within 10 minutes (a feed-regime proxy; not a quote feature)
    Tall, Lall = tr["T"].values, tr["lab"].values
    pidx = np.searchsorted(Tall, F["T_utc_ms"].values, side="left") - 1
    pgap = F["T_utc_ms"].values - Tall[np.maximum(pidx, 0)]
    pok = (pidx >= 0) & (pgap <= 600000)
    for nm_, v_ in (("prev_FA", 1), ("prev_FD", -1), ("prev_none", 0)):
        F[nm_] = (pok & (Lall[np.maximum(pidx, 0)] == v_)).astype(float)

    # ---------------------------------------------------------------- descriptive AUCs (unselected, with CIs)
    def describe(cols, mask, y, WB, section, absval, extra, base):
        res = []
        for c in cols:
            x = F[c].values[mask].astype(float)
            x = np.abs(x) if absval else x
            ps = Presorted(x, y)
            a = ps.auc()
            if not np.isfinite(a):
                continue
            lo, hi = ci([ps.auc(WB[b]) for b in range(B)])
            an, wsec, fe = parse(c)
            fin = np.isfinite(x)
            out.add(section, f"{base} {c}", est=a, lo=lo, hi=hi, n=int(fin.sum()), n_pos=int(y[fin].sum()), n_neg=int(fin.sum() - y[fin].sum()),
                    anchor=an, window_s=wsec, note=f"{FEAT_DOC.get(fe, fe)}; MT5-tester-computable: {mt5_ok(c)}; {extra}")
            res.append((c, a, lo, hi))
        return pd.DataFrame(res, columns=["col", "auc", "lo", "hi"])

    log("descriptive AUCs, agrees vs disagrees ...")
    d1 = describe(sig_cols + gate_cols, t1, y1, w1, "auc_agrees_vs_disagrees", False,
                  "positive class = agrees; AUC < 0.5 = the feature is LOWER when the feed agrees; unselected, ~350 strongly correlated candidates", "AUC")
    log("descriptive AUCs, none vs not-none (BM only) ...")
    d2 = pd.concat([describe(sig_cols, t2, y2, w2, "auc_none_vs_not_BM_only", True,
                             "positive class = none, feature = |x|, BM only; AUC > 0.5 = a LARGER |x| when none", "AUC|x|"),
                    describe(uns_cols, t2, y2, w2, "auc_none_vs_not_BM_only", False,
                             "positive class = none, unsigned activity feature, BM only", "AUC")], ignore_index=True)
    out.add("check", "AUC of 'is a buy' for none vs not-none, all market rows", est=auc_plain(isBM.astype(float), FN.astype(float)), n=n,
            note="none exists only for buys, so none-vs-not is evaluated inside BM and with |x| (a signed feature would pick up the side)")
    se0 = np.sqrt((FA.sum() + FD.sum() + 1) / (12.0 * FA.sum() * FD.sum()))
    nsig = int(((d1.auc < 0.5 - 1.96 * se0) | (d1.auc > 0.5 + 1.96 * se0)).sum())
    out.add("auc_agrees_vs_disagrees", "candidates with AUC outside 0.5 +- 1.96 SE(null)", est=nsig / max(len(d1), 1), n=len(d1),
            note=f"{nsig} of {len(d1)}; SE under the null {se0:.3f}; ~5% expected by chance, candidates are strongly correlated")
    pss = [Presorted(F[c].values[t1].astype(float), y1) for c in sig_cols + gate_cols]
    pss = [ps for ps in pss if np.isfinite(ps.auc())]
    obs_max = max(abs(ps.auc() - 0.5) for ps in pss)
    nulls = [max(abs(ps.auc_y(rng.permutation(y1)) - 0.5) for ps in pss) for _ in range(60 if args.quick else 300)]
    out.add("auc_agrees_vs_disagrees", "family-wise check: largest |AUC-0.5| over all candidates, observed", est=float(obs_max), lo=float(np.percentile(nulls, 2.5)),
            hi=float(np.percentile(nulls, 97.5)), n=len(pss),
            note=f"interval = 95% range of the same maximum when the agrees/disagrees labels are shuffled ({len(nulls)} shuffles, rows treated as independent, so slightly anti-conservative); "
                 f"permutation p = {(1 + sum(v >= obs_max for v in nulls)) / (len(nulls) + 1):.3f}")
    key_cols = [f"{an}_{W}_{f}" for an in ("lit", "arm") for W in (1000, 2000, 5000) for f in ("mvs", "tin", "qd")]
    describe(key_cols, np.ones(n, bool), FN.astype(float), wall, "auc_none_vs_not_all_market", True,
             "positive class = none, |x|, ALL market rows (the literal brief); none exists only for buys so this also mixes BM and SM regimes", "AUC|x|")
    out.add("power", "SE of an AUC under the null, agrees vs disagrees (independent rows)", est=float(se0), n=int(t1.sum()), n_pos=int(FA.sum()), n_neg=int(FD.sum()),
            note=f"an AUC must differ from 0.5 by about {1.96 * se0:.3f} (more with clustering and with the ~350 candidates) to be distinguishable from noise; a deterministic proxy needs AUC >~ 0.9")
    se0b = np.sqrt((int(FN[isBM].sum()) + int((~FN[isBM]).sum()) + 1) / (12.0 * FN[isBM].sum() * (~FN[isBM]).sum()))
    out.add("power", "SE of an AUC under the null, none vs not-none (BM only)", est=float(se0b), n=int(isBM.sum()), n_pos=int(FN[isBM].sum()), n_neg=int((~FN[isBM]).sum()),
            note=f"detectable deviation about {1.96 * se0b:.3f}")

    # ---------------------------------------------------------------- walk-forward select-then-test
    def nested_auc(cols, mask, yv, absval, section, label, WB):
        """Walk-forward select-then-test AUC. WB=None skips the bootstrap and the output row (used by the planted-signal check)."""
        idx = np.flatnonzero(mask)
        bk = blk[idx]
        X = np.column_stack([np.abs(F[c].values[idx]) if absval else F[c].values[idx] for c in cols]).astype(float)
        folds = []
        for k in range(FIRST_TEST, K):
            tri, tei = np.flatnonzero(bk < k), np.flatnonzero(bk == k)
            best, bj, bo = 0.0, None, 1
            for j in range(len(cols)):
                x = X[tri, j]
                if np.isfinite(x).sum() < 100 or yv[tri][np.isfinite(x)].sum() < 8:
                    continue
                a = auc_plain(x, yv[tri])
                if np.isfinite(a) and abs(a - 0.5) > best:
                    best, bj, bo = abs(a - 0.5), j, (1 if a >= 0.5 else -1)
            if bj is not None:
                folds.append((k, bj, tei, bo, Presorted(X[:, bj], yv)))
        fa, fp = [], []
        for (k, bj, tei, bo, ps) in folds:
            wm = np.zeros(len(yv))
            wm[tei] = 1.0
            a = ps.auc(wm)
            fa.append(a if bo > 0 else 1.0 - a)
            fp.append(yv[tei].sum() * (len(tei) - yv[tei].sum()))
        fa, fp = np.array(fa), np.array(fp, float)
        pooled = float((fa * fp).sum() / fp.sum())
        if WB is None:
            return pooled, np.nan, np.nan
        bs = []
        for b in range(B):
            num = den = 0.0
            for (k, bj, tei, bo, ps) in folds:
                wm = np.zeros(len(yv))
                wm[tei] = 1.0
                ww = WB[b] * wm
                a = ps.auc(ww)
                n1, n0 = (ww * yv).sum(), (ww * (1 - yv)).sum()
                if np.isfinite(a) and n1 > 0 and n0 > 0:
                    num += (a if bo > 0 else 1.0 - a) * n1 * n0
                    den += n1 * n0
            bs.append(num / den if den > 0 else np.nan)
        lo, hi = ci(bs)
        te = np.concatenate([f[2] for f in folds])
        picks = "; ".join(f"block{f[0] + 1}: {cols[f[1]]}({'+' if f[3] > 0 else '-'}) test AUC {a:.3f}" for f, a in zip(folds, fa))
        out.add(section, label, est=pooled, lo=lo, hi=hi, n=len(te), n_pos=int(yv[te].sum()), n_neg=int(len(te) - yv[te].sum()),
                note=f"walk-forward, {K} chronological blocks, train on blocks < k and test on block k = {FIRST_TEST + 1}..{K}; pooled = fold AUCs weighted by pair counts; "
                     f"CI = cluster bootstrap of the test rows with the selection held fixed (slightly narrow); picks: {picks}")
        return pooled, lo, hi

    log("walk-forward selection ...")
    mt5_sig = [c for c in sig_cols if parse(c)[2] not in SIZE_FEATS]
    mt5_gate = gate_cols
    for scope, cols in (("all signed candidates + gates", sig_cols + gate_cols),
                        ("MT5-computable only (no quote sizes)", mt5_sig + mt5_gate),
                        ("quote-size features only (Dukascopy sizes; not available in the MT5 tester)", [c for c in sig_cols if parse(c)[2] in SIZE_FEATS and parse(c)[2] != "call"]),
                        ("anchor lit only (literal brief: T-150 ms)", [c for c in sig_cols if c.startswith("lit_")]),
                        ("anchor rel only (order-send estimate)", [c for c in sig_cols if c.startswith("rel_")]),
                        ("anchor arm only (hold-arming estimate)", [c for c in sig_cols if c.startswith("arm_")])):
        nested_auc(cols, t1, y1, False, "nested_agrees_vs_disagrees", f"nested out-of-sample AUC agrees-vs-disagrees; candidates: {scope}", w1)
    for fam in FEATS_SIGNED + ["cpx", "call"]:
        cols_f = [f"{an}_{W}_{fam}" for an in ANCHORS for W in WINDOWS_MS]
        nested_auc(cols_f, t1, y1, False, "nested_by_family", f"nested out-of-sample AUC agrees-vs-disagrees, family {fam}", w1)
        nested_auc(cols_f, t2, y2, True, "nested_by_family", f"nested out-of-sample AUC none-vs-not (BM only, |x|), family {fam}", w2)
    for fam in FEATS_UNSIGNED:
        cols_f = [f"{an}_{W}_{fam}" for an in ANCHORS for W in WINDOWS_MS]
        nested_auc(cols_f, t2, y2, True, "nested_by_family", f"nested out-of-sample AUC none-vs-not (BM only), unsigned family {fam}", w2)
    for scope, cols in (("all |signed| + activity candidates", sig_cols + uns_cols),
                        ("MT5-computable only", mt5_sig + [c for c in uns_cols])):
        nested_auc(cols, t2, y2, True, "nested_none_vs_not_BM_only", f"nested out-of-sample AUC none-vs-not (BM only, |x|); candidates: {scope}", w2)

    # ---------------------------------------------------------------- power check: plant a known signal, see whether the pipeline finds it
    log("planted-signal power check ...")
    zc = F["lit_2000_mvs"].values.astype(float)
    zz = (zc - np.nanmean(zc)) / np.nanstd(zc)
    rs = np.random.default_rng(args.seed + 1)
    base_cols = sig_cols + gate_cols
    for b1 in ((0.0, 0.3, 0.8, 1.5) if args.quick else (0.0, 0.15, 0.3, 0.5, 0.8, 1.2, 2.0)):
        pl_auc, rec_auc = [], []
        for rep in range(3 if args.quick else 6):
            pr = 1.0 / (1.0 + np.exp(-(1.9 + b1 * zz[t1])))
            ysyn = (rs.random(int(t1.sum())) < pr).astype(float)
            pl_auc.append(auc_plain(zz[t1], ysyn))
            rec_auc.append(nested_auc(base_cols, t1, ysyn, False, "", "", None)[0])
        out.add("power_planted", f"planted logit slope {b1:g} on lit_2000_mvs: nested out-of-sample AUC recovered by the same pipeline", est=float(np.mean(rec_auc)),
                lo=float(np.min(rec_auc)), hi=float(np.max(rec_auc)), n=int(t1.sum()), n_pos=int(FA.sum()), n_neg=int(FD.sum()),
                note=f"synthetic labels drawn with P(agree)=logistic(1.9+{b1:g}*z) on the REAL feature rows (same class balance); planted in-sample AUC of the true feature "
                     f"{np.mean(pl_auc):.3f}; lo/hi = min/max over {len(rec_auc)} draws; slope 0 is the no-leakage control (should be ~0.5)")

    # ---------------------------------------------------------------- 3-class threshold rule and baselines
    log("3-class rules and baselines ...")
    cls = np.where(FA, 0, np.where(FD, 1, 2))

    def best_rule(x, c):
        """x > hi -> agrees, x <= lo -> disagrees, in between -> none; thresholds on a 5..95% quantile grid, either orientation."""
        m = np.isfinite(x)
        if m.sum() < 150:
            return None
        x, c = x[m], c[m]
        best = (-1.0, None)
        for sgn in (1, -1):
            xs = sgn * x
            cuts = np.r_[-np.inf, np.quantile(xs, np.linspace(0.05, 0.95, 19)), np.inf]
            xa, xd, xn = np.sort(xs[c == 0]), np.sort(xs[c == 1]), np.sort(xs[c == 2])
            cA, cD, cN = (np.searchsorted(v, cuts, side="right") for v in (xa, xd, xn))
            acc = (cD[:, None] + (cN[None, :] - cN[:, None]) + (len(xa) - cA[None, :])) / len(xs)
            acc = np.where(np.triu(np.ones_like(acc, bool)), acc, -1)
            i, j = np.unravel_index(np.argmax(acc), acc.shape)
            if acc[i, j] > best[0]:
                best = (float(acc[i, j]), (cuts[i], cuts[j], sgn))
        return best[1]

    def apply_rule(x, rule):
        lo_, hi_, sgn = rule
        xs = sgn * x
        pred = np.zeros(len(x), int)
        fin = np.isfinite(xs)
        pred[fin & (xs <= lo_)] = 1
        pred[fin & (xs > lo_) & (xs <= hi_)] = 2
        return pred

    def walk_rule(cols_):
        Xc = np.column_stack([F[c].values for c in cols_]).astype(float)
        pred = np.full(n, -1)
        picks = []
        for k in range(FIRST_TEST, K):
            tri, tei = np.flatnonzero(blk < k), np.flatnonzero(blk == k)
            best, bj, brule = -1.0, None, None
            for j in range(len(cols_)):
                r = best_rule(Xc[tri, j], cls[tri])
                if r is None:
                    continue
                acc = (apply_rule(Xc[tri, j], r) == cls[tri]).mean()
                if acc > best:
                    best, bj, brule = acc, j, r
            picks.append((k, cols_[bj], best))
            pred[tei] = apply_rule(Xc[tei, bj], brule)
        return pred, picks

    pred_rule, chosen = walk_rule(sig_cols)
    coin_p = np.zeros(n)
    test_rows = np.zeros(n, bool)
    sgn10 = np.where(F["lit_g_mv10"].fillna(1.0).values > 0, 0, 1)
    for k in range(FIRST_TEST, K):
        tri, tei = np.flatnonzero(blk < k), np.flatnonzero(blk == k)
        pr = np.array([(cls[tri] == q).mean() for q in range(3)])
        coin_p[tei] = pr[cls[tei]]
        test_rows[tei] = True
    ti = np.flatnonzero(test_rows)
    wcl = wall

    def acc_ci(correct, label, note):
        v = np.asarray(correct, float)[ti]
        bs = [np.average(v, weights=wcl[b][ti]) for b in range(B)]
        lo, hi = ci(bs)
        out.add("three_class", label, est=float(v.mean()), lo=lo, hi=hi, n=len(ti), note=note)
        return float(v.mean()), np.array(bs)

    a_rule, b_rule = acc_ci(pred_rule == cls, "3-class accuracy: best single-feature threshold rule, fitted on earlier blocks",
                            "feature + two thresholds + orientation chosen by training accuracy over all signed candidates (degenerate always-agrees included); picks: "
                            + "; ".join(f"block{k + 1}: {c} (train acc {a:.3f})" for k, c, a in chosen))
    a_alw, b_alw = acc_ci(np.zeros(n, int) == cls, "baseline: always 'agrees'", "share of agrees in the same test blocks")
    a_s10, b_s10 = acc_ci(sgn10 == cls, "baseline: sign of the 10 s price move (agrees if with the trade side)",
                          "10 s move at the lit anchor; the EA only trades with the burst, so this is ~always-agrees")
    a_coin, b_coin = acc_ci(coin_p, "baseline: coin weighted by the training base rate (expected accuracy)", "probability of drawing the true class, averaged over test rows")
    lo, hi = ci(b_rule - b_alw)
    out.add("three_class", "accuracy gain of the threshold rule over always-agrees", est=a_rule - a_alw, lo=lo, hi=hi, n=len(ti),
            note="paired cluster bootstrap; > 0 means the rule beats always-agrees")
    for q, nm in enumerate(("agrees", "disagrees", "none")):
        mq = cls[ti] == q
        out.add("three_class", f"recall of the selected rule for {nm}", est=float((pred_rule[ti][mq] == q).mean()), n=int(mq.sum()),
                note="share of the true class predicted correctly (test blocks)")
    for fam in FEATS_SIGNED + ["cpx", "call"]:
        cols_f = [f"{an}_{W}_{fam}" for an in ANCHORS for W in WINDOWS_MS]
        pf, pk = walk_rule(cols_f)
        v = (pf == cls).astype(float)[ti]
        bs = np.array([np.average(v, weights=wcl[b][ti]) for b in range(B)])
        lo, hi = ci(bs)
        glo, ghi = ci(bs - b_alw)
        out.add("three_class_by_family", f"3-class accuracy of the best threshold rule, family {fam} (all anchors and windows)", est=float(v.mean()), lo=lo, hi=hi, n=len(ti),
                note=f"gain over always-agrees {v.mean() - a_alw:+.4f} (95% CI {glo:+.4f} .. {ghi:+.4f}); MT5-computable: {'no (needs quote sizes)' if fam in SIZE_FEATS else 'yes'}; "
                     + "picks: " + "; ".join(f"block{k + 1}: {c} (train acc {a:.3f})" for k, c, a in pk))

    # ---------------------------------------------------------------- stochastic label model (ridge logistic)
    log("stochastic label model ...")

    def fset(an, sizes):
        base = [f"{an}_2000_mvs", f"{an}_10000_mvs", f"{an}_2000_tin", f"{an}_2000_qd", f"{an}_2000_rate", f"{an}_2000_spr",
                f"{an}_g_body", f"{an}_g_micro", f"{an}_g_mv10"]
        return base + ([f"{an}_2000_sim", f"{an}_5000_dsi", f"{an}_2000_mpp"] if sizes else [])

    def walk_logit(cols, mask, yfull, lam):
        """Train on mask rows of earlier blocks, predict every row of block k (so 'none' rows also get a T1 score)."""
        X = np.column_stack([F[c].values for c in cols]).astype(float)
        p_all, p_base = np.full(n, np.nan), np.full(n, np.nan)
        for k in range(FIRST_TEST, K):
            tri, tei = np.flatnonzero(mask & (blk < k)), np.flatnonzero(blk == k)
            med = np.nanmedian(X[tri], axis=0)
            Xtr, Xte = (np.where(np.isfinite(X[i]), X[i], med) for i in (tri, tei))
            mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
            beta = fit_logit((Xtr - mu) / sd, yfull[tri], lam)
            p_all[tei] = predict_logit(beta, (Xte - mu) / sd)
            p_base[tei] = yfull[tri].mean()
        return p_all, p_base

    def auc_txt(pm, yy, WB, pos):
        ps = Presorted(pm, yy)
        lo_, hi_ = ci([ps.auc(WB[b][pos]) for b in range(B)])
        return f"{ps.auc():.3f} (95% CI {lo_:.3f} .. {hi_:.3f})"

    res_ll = {}
    for task, mask, yfull, nm, WB in (("T1", t1, np.where(FA, 1.0, 0.0), "P(agrees | not none)", w1),
                                      ("T2", t2, np.where(FN, 1.0, 0.0), "P(none | BM)", w2)):
        mpos = np.flatnonzero(mask)
        for an in ("lit", "arm"):
            for sizes in (False, True):
                for lam in (3.0, 30.0):
                    cols = fset(an, sizes)
                    p_all, p_base = walk_logit(cols, mask, yfull, lam)
                    sel = mask & np.isfinite(p_all)
                    ii = np.flatnonzero(sel)
                    pos = np.searchsorted(mpos, ii)
                    yy, pm, pb = yfull[ii], p_all[ii], p_base[ii]
                    lm, lb = logloss_vec(pm, yy), logloss_vec(pb, yy)
                    est = 1.0 - lm.mean() / lb.mean()
                    bs = [1.0 - np.average(lm, weights=WB[b][pos]) / np.average(lb, weights=WB[b][pos]) for b in range(B) if WB[b][pos].sum() > 0]
                    lo, hi = ci(bs)
                    a_oos = auc_plain(pm, yy)
                    a_txt = auc_txt(pm, yy, WB, pos)
                    out.add("stochastic_model", f"{nm}: log-loss improvement over the base-rate model, anchor {an}, "
                            f"{'with sizes' if sizes else 'price/quote only'}, ridge {lam:g}", est=est, lo=lo, hi=hi, n=len(yy),
                            n_pos=int(yy.sum()), n_neg=int(len(yy) - yy.sum()), anchor=an,
                            note=f"1 - LL_model/LL_baserate on walk-forward test blocks; out-of-sample AUC of the model {a_txt}; features: {','.join(cols)}")
                    res_ll[(task, an, sizes, lam)] = (est, lo, hi, a_oos, p_all)

    hod_all = ((F["T_utc_ms"].values // 3600000) % 24).astype(int)
    for task, mask, yfull, nm, WB in (("T1", t1, np.where(FA, 1.0, 0.0), "P(agrees | not none)", w1), ("T2", t2, np.where(FN, 1.0, 0.0), "P(none | BM)", w2)):
        mpos = np.flatnonzero(mask)
        for m_shr in (10.0, 30.0):
            p_all, p_base = np.full(n, np.nan), np.full(n, np.nan)
            for k in range(FIRST_TEST, K):
                trm, tem = mask & (blk < k), blk == k
                p0 = yfull[trm].mean()
                p_base[tem] = p0
                for h in range(24):
                    th = trm & (hod_all == h)
                    p_all[tem & (hod_all == h)] = (yfull[th].sum() + m_shr * p0) / (th.sum() + m_shr)
            ii = np.flatnonzero(mask & np.isfinite(p_all))
            pos = np.searchsorted(mpos, ii)
            yy, pm, pb = yfull[ii], p_all[ii], p_base[ii]
            lm, lb = logloss_vec(pm, yy), logloss_vec(pb, yy)
            bs = [1.0 - np.average(lm, weights=WB[b][pos]) / np.average(lb, weights=WB[b][pos]) for b in range(B) if WB[b][pos].sum() > 0]
            lo, hi = ci(bs)
            out.add("stochastic_model", f"{nm}: log-loss improvement over the base-rate model, UTC hour-of-day table shrunk to the base rate (m={m_shr:g})",
                    est=float(1.0 - lm.mean() / lb.mean()), lo=lo, hi=hi, n=len(yy), n_pos=int(yy.sum()), n_neg=int(len(yy) - yy.sum()), anchor="hour-of-day",
                    note=f"empirical-Bayes hour table trained on earlier blocks; out-of-sample AUC {auc_txt(pm, yy, WB, pos)}")

    for task, mask, yfull, nm, WB in (("T1", t1, np.where(FA, 1.0, 0.0), "P(agrees | not none)", w1), ("T2", t2, np.where(FN, 1.0, 0.0), "P(none | BM)", w2)):
        mpos = np.flatnonzero(mask)
        for lam in (3.0, 30.0):
            p_all, p_base = walk_logit(["prev_FA", "prev_FD", "prev_none"], mask, yfull, lam)
            ii = np.flatnonzero(mask & np.isfinite(p_all))
            pos = np.searchsorted(mpos, ii)
            yy, pm, pb = yfull[ii], p_all[ii], p_base[ii]
            lm, lb = logloss_vec(pm, yy), logloss_vec(pb, yy)
            bs = [1.0 - np.average(lm, weights=WB[b][pos]) / np.average(lb, weights=WB[b][pos]) for b in range(B) if WB[b][pos].sum() > 0]
            lo, hi = ci(bs)
            out.add("stochastic_model", f"{nm}: log-loss improvement over the base-rate model, label of the previous real trade within 10 min (regime proxy), ridge {lam:g}",
                    est=float(1.0 - lm.mean() / lb.mean()), lo=lo, hi=hi, n=len(yy), n_pos=int(yy.sum()), n_neg=int(len(yy) - yy.sum()), anchor="label-history",
                    note=f"one-hot previous label (agrees/disagrees/none, zero if none within 600 s); out-of-sample AUC {auc_txt(pm, yy, WB, pos)}; not computable by a replay without a label generator")

    # ---------------------------------------------------------------- gates (selection structure), momentum share
    log("gates and momentum ...")
    for an in ANCHORS:
        for g, what, thr in (("body_ok", "M1 body >= 21 pts with the trade", "weak-flow market entries (FD and none) must have body AND micro-break with the trade; body from the Dukascopy bid at the minute start (approximation of the broker bar)"),
                             ("micro_ok", "break of the previous 10 s extreme by > 3 pts with the trade", "exact only at the decision tick on the broker feed; at 1 s resolution on Dukascopy ticks it is much noisier than the body test")):
            for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
                v = F[f"{an}_g_{g}"].values
                m = (lab == lab_v) & np.isfinite(v)
                k = int(v[m].sum())
                lo, hi = wilson(k, int(m.sum()))
                out.add("gates", f"share with {what}, label {nm}", est=k / max(int(m.sum()), 1), lo=lo, hi=hi, n=int(m.sum()), n_pos=k, anchor=an, note=thr)
        mv10 = F[f"{an}_g_mv10"].values
        okm = np.isfinite(mv10)
        with_move, against = okm & (mv10 > 0), okm & (mv10 < 0)
        for nm, m in (("trade side == direction of the last 10 s move", with_move), ("trade side opposite to the last 10 s move", against)):
            lo, hi = wilson(int(m.sum()), int(okm.sum()))
            out.add("momentum", f"share of market entries: {nm}", est=m.sum() / max(okm.sum(), 1), lo=lo, hi=hi, n=int(okm.sum()), n_pos=int(m.sum()), anchor=an,
                    note="the EA only trades market entries in the burst direction (speedDir == winner)")
        for nm, m in (("trade side == 10 s move direction", with_move), ("trade side opposite to the 10 s move", against)):
            den = int((t1 & m).sum())
            k = int((FA & m).sum())
            lo, hi = wilson(k, den)
            out.add("momentum", f"share agrees among agrees+disagrees when {nm}", est=k / den if den else np.nan, lo=lo, hi=hi, n=den, n_pos=k, anchor=an,
                    note="momentum-explains-the-label check; the second group is tiny because market entries almost never go against the 10 s move")
    # the weak-flow gate is evaluated at the arming tick, which is only known to +-0.5 s: take the best value over a 1 s grid
    for g, what in (("body_max", "M1 body >= 21 pts with the trade"), ("micro_max", "break of the previous 10 s extreme by > 3 pts with the trade")):
        v = F[f"armgrid_g_{g}"].values
        ok_flag = (v >= MIN_BODY_PTS) if g == "body_max" else (v > MICRO_BUF_PTS)
        for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
            m = (lab == lab_v) & np.isfinite(v)
            k = int(ok_flag[m].sum())
            lo, hi = wilson(k, int(m.sum()))
            out.add("gates", f"share with {what} at ANY time in [T-1.4 s, T-0.4 s], label {nm}", est=k / max(int(m.sum()), 1), lo=lo, hi=hi, n=int(m.sum()), n_pos=k, anchor="armgrid",
                    note="grid of 100 ms steps around the arming-time estimate; weak-flow entries (disagrees, none) must pass body AND micro-break at the arming tick, strong-flow (agrees) entries need neither")
    for an in ("lit", "arm"):
        m = t1 & (F[f"{an}_g_body_ok"].values == 1)
        yy = FA[m].astype(float)
        wsub = boot_weights(clus[m], B, rng)
        for c in (f"{an}_2000_mvs", f"{an}_2000_tin", f"{an}_5000_mv", f"{an}_10000_mv"):
            ps = Presorted(F[c].values[m].astype(float), yy)
            lo, hi = ci([ps.auc(wsub[b]) for b in range(B)])
            out.add("gates", f"AUC agrees-vs-disagrees inside the body>=21 subset: {c}", est=ps.auc(), lo=lo, hi=hi, n=int(m.sum()), n_pos=int(yy.sum()),
                    n_neg=int(len(yy) - yy.sum()), anchor=an, note="if the weak-flow gate (body AND micro required for FD/none) causes the sub-0.5 AUC of momentum features it should move towards 0.5 here")

    both = t1 & (F["armgrid_g_body_max"].values >= MIN_BODY_PTS) & (F["armgrid_g_micro_max"].values > MICRO_BUF_PTS)
    yb = FA[both].astype(float)
    wb_ = boot_weights(clus[both], B, rng)
    for c in ("lit_2000_mvs", "lit_3000_mvs", "arm_2000_mvs", "arm_3000_mvs", "lit_2000_tin", "arm_2000_tin", "arm_5000_mv", "lit_10000_mv"):
        ps = Presorted(F[c].values[both].astype(float), yb)
        lo, hi = ci([ps.auc(wb_[b]) for b in range(B)])
        out.add("gates", f"AUC agrees-vs-disagrees inside the subset where BOTH weak-flow gates hold at some tick of the arming window: {c}", est=ps.auc(), lo=lo, hi=hi,
                n=int(both.sum()), n_pos=int(yb.sum()), n_neg=int(len(yb) - yb.sum()), anchor=c.split("_")[0],
                note="FD and none trades must pass these gates; if the sub-0.5 AUC of the momentum features is a selection effect of the gate it should move to 0.5 here (score >= 5 and edge >= 2 are not reproducible from prices)")

    # ---------------------------------------------------------------- regime / serial structure
    def chi2(g, lbl):
        gi = pd.factorize(g)[0]
        tab = np.zeros((gi.max() + 1, 3))
        np.add.at(tab, (gi, lbl), 1)
        exp = tab.sum(1, keepdims=True) * tab.sum(0, keepdims=True) / tab.sum()
        return float(((tab - exp) ** 2 / np.maximum(exp, 1e-9)).sum())

    for nm, g in (("UTC hour of day", ((F["T_utc_ms"].values // 3600000) % 24).astype(int)), ("calendar day", (F["T_utc_ms"].values // 86400000).astype(int))):
        o = chi2(g, cls)
        p = (1 + sum(chi2(g, rng.permutation(cls)) >= o for _ in range(1000))) / 1001
        out.add("regime", f"label heterogeneity across {nm} (chi-square statistic)", est=o, n=n, note=f"groups = {len(np.unique(g))}; permutation p = {p:.3f}; a small p would mean the feed state is a function of time")
        out.add("regime", f"label heterogeneity across {nm} (permutation p-value)", est=float(p), n=n, note="1000 label permutations")
    # serial structure on ALL 1,911 market trades (no ticks needed): does the label persist from one trade to the next?
    ma_ = mk_all.sort_values("T").reset_index(drop=True)
    la = ma_.lab.values.astype(int)
    gap = np.diff(ma_["T"].values) / 1000.0
    perms = [rng.permutation(la) for _ in range(1000)]

    def serial(l, mask_gap, cond=None):
        eq = (l[1:] == l[:-1])
        sel = mask_gap if cond is None else (mask_gap & (l[:-1] == cond))
        return eq[sel].mean() if sel.any() else np.nan

    for nm, mg in (("any gap", np.ones(len(gap), bool)), ("gap < 30 s", gap < 30), ("gap 30-120 s", (gap >= 30) & (gap < 120)), ("gap 120-600 s", (gap >= 120) & (gap < 600)), ("gap >= 600 s", gap >= 600)):
        for cond, cn in ((None, "any label"), (-1, "previous = disagrees"), (0, "previous = none")):
            sel = mg if cond is None else (mg & (la[:-1] == cond))
            if sel.sum() < 15:
                continue
            o = serial(la, mg, cond)
            nullv = [serial(pm, mg, cond) for pm in perms]
            p = (1 + sum(v >= o for v in nullv)) / 1001
            out.add("regime", f"P(next trade has the SAME label | {cn}, {nm})", est=float(o), lo=float(np.nanpercentile(nullv, 2.5)), hi=float(np.nanpercentile(nullv, 97.5)),
                    n=int(sel.sum()), note=f"all 1911 market trades in time order; interval = 95% range if the order were random; one-sided permutation p = {p:.3f}")

    # ---------------------------------------------------------------- label vs outcome
    log("outcome analysis ...")

    def wmean(v, m):
        ok = m & np.isfinite(v)
        bs = [np.average(v[ok], weights=wall[b][ok]) for b in range(B) if wall[b][ok].sum() > 0]
        return float(v[ok].mean()), ci(bs), int(ok.sum())

    for outcome, col, note in (("realised result, points per 0.01 lot", "pts", "includes the EA's own exits (:FD trades get defensive exits) and slippage"),
                               ("forward mid move 5 s after the fill, points, with the trade", "fwd5", "label-independent: not touched by the exit rules"),
                               ("forward mid move 10 s after the fill, points, with the trade", "fwd10", "label-independent"),
                               ("forward mid move 30 s after the fill, points, with the trade", "fwd30", "label-independent")):
        v = F[col].values.astype(float)
        for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
            est, (lo, hi), nn = wmean(v, lab == lab_v)
            out.add("outcome", f"{outcome}: mean for label {nm}", est=est, lo=lo, hi=hi, n=nn, note=note)
        okv = np.isfinite(v)
        vz = np.where(okv, v, 0.0)
        bs = []
        for b in range(B):
            wa, wd = wall[b] * (FA & okv), wall[b] * (FD & okv)
            if wa.sum() > 0 and wd.sum() > 0:
                bs.append((wa * vz).sum() / wa.sum() - (wd * vz).sum() / wd.sum())
        lo, hi = ci(bs)
        out.add("outcome", f"{outcome}: agrees minus disagrees", est=float(v[FA & okv].mean() - v[FD & okv].mean()), lo=lo, hi=hi, n=int((t1 & okv).sum()), note=note)
    # all 1,911 market trades (no ticks needed)
    mkc = mk_all.reset_index(drop=True)
    wall2 = boot_weights((mkc["T"] // 3600000).values, B, rng)
    for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
        m = (mkc.lab == lab_v).values
        v = mkc.pts.values.astype(float)
        bs = [np.average(v[m], weights=wall2[b][m]) for b in range(B) if wall2[b][m].sum() > 0]
        lo, hi = ci(bs)
        out.add("outcome_all_market", f"realised points, label {nm} (all 1911 market trades, no ticks needed)", est=float(v[m].mean()), lo=lo, hi=hi, n=int(m.sum()),
                note="cluster bootstrap by UTC hour")
    # side split: the label-outcome relation can flip with the market drift (gold fell ~7% over the window); interaction = buys minus sells
    def dmean(v, W, mA, mD):
        ok = np.isfinite(v)
        mA, mD = mA & ok, mD & ok
        vz = np.where(ok, v, 0.0)
        bs = []
        for b in range(B):
            wa, wd = W[b] * mA, W[b] * mD
            if wa.sum() > 0 and wd.sum() > 0:
                bs.append((wa * vz).sum() / wa.sum() - (wd * vz).sum() / wd.sum())
        return float(v[mA].mean() - v[mD].mean()), ci(bs), int(mA.sum()), int(mD.sum())

    def interaction(v, W, bm, fa, fd):
        ok = np.isfinite(v)
        vz = np.where(ok, v, 0.0)

        def mm(mask, w):
            ww = w * (mask & ok)
            return (ww * vz).sum() / ww.sum()
        est = (mm(bm & fa, 1) - mm(bm & fd, 1)) - (mm(~bm & fa, 1) - mm(~bm & fd, 1))
        bs = [(mm(bm & fa, W[b]) - mm(bm & fd, W[b])) - (mm(~bm & fa, W[b]) - mm(~bm & fd, W[b])) for b in range(B)]
        return est, ci(bs)

    mkc_bm = (mkc["side"].values == 1)
    mkc_fa, mkc_fd = (mkc.lab.values == 1), (mkc.lab.values == -1)
    sets = [("realised points, all 1911 market trades", mkc.pts.values.astype(float), wall2, mkc_bm, mkc_fa, mkc_fd, "no ticks needed"),
            ("realised points, covered sample", F["pts"].values.astype(float), wall, isBM, FA, FD, "1260 rows"),
            ("forward mid move 10 s with the trade, covered sample", F["fwd10"].values.astype(float), wall, isBM, FA, FD, "label-independent")]
    for tag, v, W_, bm_, fa_, fd_, nt in sets:
        for sd_nm, mside in (("buys (BM)", bm_), ("sells (SM)", ~bm_)):
            est, (lo, hi), na, nd = dmean(v, W_, mside & fa_, mside & fd_)
            out.add("outcome_by_side", f"{tag}: agrees minus disagrees, {sd_nm}", est=est, lo=lo, hi=hi, n=na + nd, n_pos=na, n_neg=nd,
                    note=f"n_pos = agrees, n_neg = disagrees; {nt}; cluster bootstrap by UTC hour; the pooled difference mixes two opposite signs when the market trends")
        est, (lo, hi) = interaction(v, W_, bm_, fa_, fd_)
        out.add("outcome_by_side", f"{tag}: interaction (agrees minus disagrees on buys) minus (same on sells)", est=est, lo=lo, hi=hi, n=int((fa_ | fd_).sum()),
                note=f"{nt}; entry price fell from 4430.8 to 4113.5 (-7.2%) over the trade window, so sells were the profitable side")
    # does the ABSOLUTE direction of the feed (buy vs sell verdict) predict the next price move?  unaligned forward move by flow direction
    fdir = lab * F["side"].values                                  # +1 = feed says buy, -1 = feed says sell
    for k in (5, 10, 30):
        raw_ = F[f"fwd{k}"].values.astype(float) * F["side"].values
        for fv, nm in ((1, "feed says BUY"), (-1, "feed says SELL")):
            est, (lo, hi), nn = wmean(raw_, (fdir == fv) & (lab != 0))
            out.add("feed_direction_vs_price", f"raw mid move {k} s after the fill (points, + = price up), {nm}", est=est, lo=lo, hi=hi, n=nn,
                    note="feed direction = trade side x label (agrees/disagrees); conditional on the EA's market entries; no alignment with the trade side")
        est, (lo, hi), na, nd = dmean(raw_, wall, (fdir == 1) & (lab != 0), (fdir == -1) & (lab != 0))
        out.add("feed_direction_vs_price", f"raw mid move {k} s after the fill: feed says BUY minus feed says SELL", est=est, lo=lo, hi=hi, n=na + nd, n_pos=na, n_neg=nd,
                note="> 0 would mean the feed's buy/sell verdict predicts the direction of the next move; n_pos = feed says buy, n_neg = feed says sell")

    for lab_v, nm in ((1, "agrees"), (-1, "disagrees"), (0, "none")):
        m = lab == lab_v
        k = int((F["exit_kind"].values[m] == "SL").sum())
        lo, hi = wilson(k, int(m.sum()))
        out.add("outcome", f"share of trades closed at the stop loss, label {nm}", est=k / max(int(m.sum()), 1), lo=lo, hi=hi, n=int(m.sum()), n_pos=k,
                note="the :FD label changes the EA's defensive exits (FOLMFlowDisagreeDangerLossPoints, FlowDisagreeMakesDefenseImmediate), so realised points are not a clean test of direction")

    for nm_, desc in (("leg_a", "T-3.40 s to T-2.15 s"), ("leg_b", "T-2.15 s to T-0.90 s"), ("leg_c", "T-0.90 s to T+0.35 s (arm estimate to order-send estimate)"),
                      ("leg_d", "T+0.35 s to T+1.60 s (after the order)"), ("leg_e", "T+1.60 s to T+2.85 s")):
        v = F[nm_].values.astype(float)
        ok = np.isfinite(v)
        bs = [np.average(v[ok], weights=wall[b][ok]) for b in range(B) if wall[b][ok].sum() > 0]
        lo, hi = ci(bs)
        out.add("price_path", f"mean mid move with the trade, {desc}, points", est=float(v[ok].mean()), lo=lo, hi=hi, n=int(ok.sum()),
                note=f"share of trades with a move < +5 points: {float((v[ok] < 5).mean()):.3f}, < 0: {float((v[ok] < 0).mean()):.3f}; Dukascopy mid, +-0.5 s timing noise from the 1 s stamp; the entry hold requires >= +5 points between arming and sending")

    t1keys = [k for k in res_ll if k[0] == "T1"]
    best_key = max(t1keys, key=lambda k: res_ll[k][3] if np.isfinite(res_ll[k][3]) else -1)
    proxy_p = res_ll[best_key][4]
    proxy = np.log(np.clip(proxy_p, 1e-4, 1 - 1e-4) / (1 - np.clip(proxy_p, 1e-4, 1 - 1e-4)))

    def ols(Xm, yv):
        return np.linalg.lstsq(Xm, yv, rcond=None)[0]

    for col in ("pts", "fwd10"):
        v = F[col].values.astype(float)
        idx = np.flatnonzero(np.isfinite(proxy) & np.isfinite(v))
        X0 = np.c_[np.ones(len(idx)), FA[idx].astype(float), FN[idx].astype(float)]      # reference class = disagrees
        X1 = np.c_[X0, proxy[idx], isBM[idx].astype(float)]
        for nm, Xm in (("label only", X0), ("label + best out-of-sample proxy logit + BM dummy", X1)):
            beta = ols(Xm, v[idx])
            bs = []
            for b in range(B):
                ww = np.sqrt(wall[b][idx].astype(float))
                if (ww > 0).sum() >= 30:
                    bs.append(ols(Xm * ww[:, None], v[idx] * ww))
            bs = np.array(bs)
            for j, nmj in ((1, "agrees minus disagrees"), (2, "none minus disagrees")):
                lo, hi = ci(bs[:, j])
                out.add("outcome_control", f"{col}: coefficient {nmj} ({nm})", est=float(beta[j]), lo=lo, hi=hi, n=len(idx),
                        note=f"OLS on rows with an out-of-sample proxy (blocks {FIRST_TEST + 1}-{K}); proxy = logit of the {best_key[0]} ridge model, anchor {best_key[1]}, "
                             f"sizes={best_key[2]}, lambda={best_key[3]:g} (chosen by label AUC, never by outcome); cluster bootstrap by UTC hour")
            if Xm.shape[1] > 3:
                lo, hi = ci(bs[:, 3])
                out.add("outcome_control", f"{col}: coefficient of the proxy logit per +1 logit ({nm})", est=float(beta[3]), lo=lo, hi=hi, n=len(idx),
                        note="effect of the proxy on the outcome, holding the label fixed")

    # ---------------------------------------------------------------- lag scan (descriptive)
    if not args.quick:
        log("lag scan ...")
        keyf = [("mvs", 2000), ("tin", 2000), ("qd", 2000), ("sim", 2000), ("spr", 2000)]
        wl = boot_weights(clus[t1], 300, rng)
        store2 = TickStore(raw_root)
        vals = {(f, W, L): np.full(n, np.nan) for f, W in keyf for L in LAG_SCAN_MS}
        for i, r in F.iterrows():
            T, sd = int(r["T_utc_ms"]), int(r["side"])
            tk = store2.window(T - 45000, T + 40000)
            for L in LAG_SCAN_MS:
                for f, W in keyf:
                    raw = window_raw(tk, T + L, W)
                    if raw is not None:
                        vals[(f, W, L)][i] = align(raw, sd, W)[f]
        for (f, W, L), v in vals.items():
            x = v[t1]
            ps = Presorted(x, y1)
            lo, hi = ci([ps.auc(wl[b]) for b in range(wl.shape[0])])
            fin = np.isfinite(x)
            out.add("lag_scan", f"AUC agrees-vs-disagrees {f}@{W / 1000:g}s, window ends at T{L:+d} ms", est=ps.auc(), lo=lo, hi=hi, n=int(fin.sum()),
                    n_pos=int(y1[fin].sum()), n_neg=int(fin.sum() - y1[fin].sum()), anchor=f"T{L:+d}", window_s=W / 1000.0,
                    note="descriptive, 300 bootstrap draws; T = stamped second (UTC); under the entry-hold code path the label is frozen near T-900")

    # ---------------------------------------------------------------- exploratory: stop-order entries
    if not args.quick and len(pend) > 30:
        log("stop-order block ...")
        P = []
        for _, r in pend.iterrows():
            T, sd = int(r["T"]), int(r["side"])
            tk = store.window(T - 50000, T + 5000)
            row = dict(lab=int(r.lab), hour_id=T // 3600000)
            for L in (500, 1500, 2500, 3500, 4500, 6000):
                for f in ("mvs", "tin", "qd", "rate", "spr"):
                    raw = window_raw(tk, T - L, 2000)
                    row[f"{f}_{L}"] = align(raw, sd, 2000)[f] if raw else np.nan
            P.append(row)
        P = pd.DataFrame(P)
        m = P.lab.isin([-1, 0]).values
        yp = (P.lab.values[m] == -1).astype(float)
        wp = boot_weights(P.hour_id.values[m], 300, rng)
        out.add("stop_orders", "stop-order entries with ticks: n_pos = agrees, n_neg = disagrees", n=len(P), n_pos=int((P.lab == 1).sum()), n_neg=int((P.lab == -1).sum()),
                note=f"none = {int((P.lab == 0).sum())}; agrees is too rare for a model; the decision was frozen 1.1 s (hold) + up to 5 s (pending lifetime) before the stop triggered")
        for L in (500, 1500, 2500, 3500, 4500, 6000):
            for f in ("mvs", "tin", "qd", "rate", "spr"):
                x = P[f"{f}_{L}"].values[m]
                ps = Presorted(x, yp)
                lo, hi = ci([ps.auc(wp[b]) for b in range(wp.shape[0])])
                fin = np.isfinite(x)
                out.add("stop_orders", f"AUC disagrees-vs-none {f}@2s ending {L} ms before the stamped second", est=ps.auc(), lo=lo, hi=hi, n=int(fin.sum()),
                        n_pos=int(yp[fin].sum()), n_neg=int(fin.sum() - yp[fin].sum()), anchor=f"T-{L}", window_s=2.0,
                        note="exploratory; BS/SS entries only; positive class = disagrees; 300 bootstrap draws")

    # ---------------------------------------------------------------- write and summarise
    F["block"] = blk
    F["proxy_oos_logit"] = proxy
    F.to_csv(os.path.join(HERE, "probe_flow_proxy_features.csv"), index=False, float_format="%.6g")
    M = out.frame()
    M.to_csv(os.path.join(HERE, "probe_flow_proxy_metrics.csv"), index=False, float_format="%.6g")
    log(f"wrote {len(F)} feature rows and {len(M)} metric rows to {HERE}")

    pd.set_option("display.width", 230, "display.max_colwidth", 120, "display.max_rows", 500)

    def show(sec, top=None):
        d = M[M.section == sec]
        print(f"\n== {sec} ({len(d)} rows)")
        print((d.head(top) if top else d)[["name", "estimate", "ci_lo", "ci_hi", "n", "n_pos", "n_neg"]].round(3).to_string(index=False))

    for s in ("sample", "tz_check", "check", "power", "power_planted", "base_rate_all", "base_rate_scenario", "base_rate_action", "base_rate_market",
              "nested_agrees_vs_disagrees", "nested_none_vs_not_BM_only", "nested_by_family", "auc_none_vs_not_all_market", "three_class", "three_class_by_family", "stochastic_model", "gates", "momentum", "regime",
              "price_path", "outcome", "outcome_all_market", "outcome_by_side", "feed_direction_vs_price", "outcome_control"):
        show(s)
    d = M[(M.section == "auc_agrees_vs_disagrees") & M.name.str.startswith("family-wise")]
    print("\n== family-wise check")
    print(d[["name", "estimate", "ci_lo", "ci_hi", "n"]].round(3).to_string(index=False))
    for sec in ("auc_agrees_vs_disagrees", "auc_none_vs_not_BM_only"):
        d = M[M.section == sec].copy()
        d = d[d.name.str.startswith("AUC")]
        d["dev"] = (d.estimate - 0.5).abs()
        print(f"\n== {sec}: top 12 by |AUC-0.5| (unselected, optimistic)")
        print(d.sort_values("dev", ascending=False).head(12)[["name", "estimate", "ci_lo", "ci_hi", "n"]].round(3).to_string(index=False))
    if not args.quick:
        show("lag_scan")
        show("stop_orders")


if __name__ == "__main__":
    main()
