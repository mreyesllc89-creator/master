"""PLAN prototype of the forward-outcome kernel: for each decision tick, both sides, no EA-side management.

  * mid path: signed move at horizons H (zero-order hold, NaN past the end of the chunk)
  * mfe / mae of the signed mid move inside the first HM ms
  * server-side bracket from a market entry under the calibrated fill model (the same arithmetic as engine.py lines
    410-425 and 1381-1389): the order is sent at tick i, fills on the first tick at or after t+latency at ask / bid,
    SL / TP are placed from the quote of the DECISION tick, the position is checked from the tick after the fill
    on; stop loss fills at the level when the touch is within `snap` points, else it slips slmult times the quoted gap;
    take profit fills at the market (lim_mkt) ; still open at hmax -> closed at the market.
"""
import numpy as np
from numba import njit

PT = 0.01
H_MS = np.array([500, 1000, 2000, 3000, 5000, 10000, 20000, 30000, 60000], np.int64)
HM_MS = np.array([5000, 10000, 30000, 60000], np.int64)
BRACKETS = np.array([[90, 180], [90, 600], [130, 600], [200, 600], [60, 180], [80, 160]], np.float64)
NH, NM, NK = len(H_MS), len(HM_MS), len(BRACKETS)
R_NONE, R_SL, R_TP, R_HORIZON = 0, 1, 2, 3


@njit(cache=True, nogil=True)
def forward_outcomes(T, B, A, rows, latency, snap_pts, slmult, slip_pts, lim_mkt, hmax,
                     mv, mfe, mae, br_pts, br_reason, br_ms):
    n = len(T)
    snap = snap_pts * PT + PT * 1e-6
    slip = slip_pts * PT
    for r in range(len(rows)):
        i = rows[r]
        t0 = T[i]
        mid0 = (B[i] + A[i]) * 0.5
        # ---- mid path at the horizons, mfe / mae
        j = i
        for h in range(NH):
            lim = t0 + H_MS[h]
            if lim > T[n - 1]:
                for s in range(2):
                    mv[r, s, h] = np.nan
                continue
            while j + 1 < n and T[j + 1] <= lim:
                j += 1
            d = ((B[j] + A[j]) * 0.5 - mid0) / PT
            mv[r, 0, h] = d
            mv[r, 1, h] = -d
        hi = 0.0
        lo = 0.0
        k = i
        for h in range(NM):
            lim = t0 + HM_MS[h]
            if lim > T[n - 1]:
                for s in range(2):
                    mfe[r, s, h] = np.nan
                    mae[r, s, h] = np.nan
                continue
            while k + 1 < n and T[k + 1] <= lim:
                k += 1
                d = ((B[k] + A[k]) * 0.5 - mid0) / PT
                if d > hi:
                    hi = d
                if d < lo:
                    lo = d
            mfe[r, 0, h] = hi
            mae[r, 0, h] = lo
            mfe[r, 1, h] = -lo
            mae[r, 1, h] = -hi
        # ---- server-side brackets from a market entry
        e = i
        while e < n and T[e] < t0 + latency:
            e += 1
        for s in range(2):
            side = 1 if s == 0 else -1
            ref = A[i] if side > 0 else B[i]
            if e >= n:
                for q in range(NK):
                    br_reason[r, s, q] = R_NONE
                    br_pts[r, s, q] = np.nan
                    br_ms[r, s, q] = 0
                continue
            entry = (A[e] + slip) if side > 0 else (B[e] - slip)
            for q in range(NK):
                sl = round((ref - side * BRACKETS[q, 0] * PT) / PT) * PT
                tp = round((ref + side * BRACKETS[q, 1] * PT) / PT) * PT
                reason = R_NONE
                px = 0.0
                tx = 0
                m = e + 1
                while m < n and T[m] - t0 <= hmax:
                    if side > 0:
                        if B[m] <= sl:
                            gap = sl - B[m]
                            px = (sl if gap <= snap else sl - np.floor(gap / PT * slmult + 0.5) * PT) - slip
                            reason = R_SL
                        elif B[m] >= tp:
                            px = B[m] if lim_mkt else tp
                            reason = R_TP
                    else:
                        if A[m] >= sl:
                            gap = A[m] - sl
                            px = (sl if gap <= snap else sl + np.floor(gap / PT * slmult + 0.5) * PT) + slip
                            reason = R_SL
                        elif A[m] <= tp:
                            px = A[m] if lim_mkt else tp
                            reason = R_TP
                    if reason != R_NONE:
                        tx = T[m]
                        break
                    m += 1
                if reason == R_NONE:
                    if m < n and T[m] - t0 > hmax:
                        mm = m - 1
                        px = B[mm] if side > 0 else A[mm]
                        tx = T[mm]
                        reason = R_HORIZON
                if reason == R_NONE:
                    br_pts[r, s, q] = np.nan
                    br_ms[r, s, q] = 0
                else:
                    br_pts[r, s, q] = side * (px - entry) / PT
                    br_ms[r, s, q] = tx - t0
                br_reason[r, s, q] = reason


def alloc(nrows):
    return (np.zeros((nrows, 2, NH), np.float32), np.zeros((nrows, 2, NM), np.float32), np.zeros((nrows, 2, NM), np.float32),
            np.zeros((nrows, 2, NK), np.float32), np.zeros((nrows, 2, NK), np.int8), np.zeros((nrows, 2, NK), np.int32))
