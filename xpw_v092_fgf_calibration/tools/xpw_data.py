"""Load Binance Vision monthly 1m klines into numpy arrays and resample.

Server clock: timestamps are shifted by SERVER_OFFSET_SEC so that H1/H4 bar
boundaries mimic an EET (UTC+2) MetaTrader server.
"""
import glob, io, os, zipfile
import numpy as np

SERVER_OFFSET_SEC = 2 * 3600
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load_1m(symbol):
    cache = os.path.join(DATA_DIR, f"{symbol}_1m.npz")
    if os.path.exists(cache):
        z = np.load(cache)
        return z["t"], z["o"], z["h"], z["l"], z["c"]
    files = sorted(glob.glob(os.path.join(DATA_DIR, symbol, f"{symbol}-1m-*.zip")))
    ts, os_, hs, ls, cs = [], [], [], [], []
    for f in files:
        with zipfile.ZipFile(f) as zf:
            name = zf.namelist()[0]
            raw = zf.read(name)
        arr = np.genfromtxt(io.BytesIO(raw), delimiter=",", usecols=(0, 1, 2, 3, 4), dtype=np.float64)
        if arr.ndim == 1:
            arr = arr[None, :]
        t = arr[:, 0]
        # ms before 2025, microseconds afterwards
        t = np.where(t > 1e14, t / 1e6, t / 1e3)
        ts.append(t); os_.append(arr[:, 1]); hs.append(arr[:, 2]); ls.append(arr[:, 3]); cs.append(arr[:, 4])
    t = np.concatenate(ts); o = np.concatenate(os_); h = np.concatenate(hs); l = np.concatenate(ls); c = np.concatenate(cs)
    order = np.argsort(t, kind="stable")
    t, o, h, l, c = t[order], o[order], h[order], l[order], c[order]
    keep = np.ones(len(t), bool); keep[1:] = t[1:] > t[:-1]
    t, o, h, l, c = t[keep], o[keep], h[keep], l[keep], c[keep]
    t = t.astype(np.int64)
    np.savez(cache, t=t, o=o, h=h, l=l, c=c)
    return t, o, h, l, c


def gold_session_mask(t_utc):
    """Keep only bars inside a typical XAUUSD quote session on an EET server:
    Monday 01:00 .. Friday 23:59 server time, with a daily 00:00-00:59 break."""
    ts = t_utc + SERVER_OFFSET_SEC
    dow = ((ts // 86400) + 4) % 7  # 1970-01-01 was a Thursday -> 4
    hour = (ts % 86400) // 3600
    keep = np.ones(len(ts), bool)
    keep &= ~((dow == 6) | (dow == 0))  # Saturday, Sunday
    keep &= hour != 0                   # daily break
    return keep


def resample(t, o, h, l, c, minutes):
    """Resample 1m bars (already session-filtered) to `minutes` bars aligned to
    the server clock. Returns server-clock bar open time (seconds)."""
    ts = t + SERVER_OFFSET_SEC
    key = ts // (minutes * 60)
    # boundaries where key changes
    idx = np.flatnonzero(np.diff(key)) + 1
    starts = np.concatenate(([0], idx))
    ends = np.concatenate((idx, [len(key)]))
    bo = o[starts]
    bc = c[ends - 1]
    bh = np.maximum.reduceat(h, starts)
    bl = np.minimum.reduceat(l, starts)
    bt = key[starts] * minutes * 60
    return bt.astype(np.int64), bo, bh, bl, bc, starts.astype(np.int64), ends.astype(np.int64)


def prepare(symbol, minutes, gold=False):
    t, o, h, l, c = load_1m(symbol)
    if gold:
        m = gold_session_mask(t)
        t, o, h, l, c = t[m], o[m], h[m], l[m], c[m]
    return resample(t, o, h, l, c, minutes)


if __name__ == "__main__":
    import datetime as dt
    for sym, gold in (("BTCUSDT", False), ("PAXGUSDT", True)):
        t, o, h, l, c = load_1m(sym)
        print(sym, len(t), dt.datetime.utcfromtimestamp(t[0]), dt.datetime.utcfromtimestamp(t[-1]))
        # price granularity by month
        months = (t // 86400) // 30
        frac = np.abs(c - np.round(c)) > 1e-9
        for mo in np.unique(months)[::3]:
            sel = months == mo
            print("  ", dt.datetime.utcfromtimestamp(int(t[sel][0])).strftime("%Y-%m"), "frac-price share %.3f" % frac[sel].mean(), "bars", sel.sum())
        for m in (1, 5, 15, 30, 60, 240):
            bt, bo, bh, bl, bc, _, _ = prepare(sym, m, gold)
            print("  TF", m, "bars", len(bt))
