"""Data-snooping check for the 15m search on the tuning data (opt15m.npz, exits on 1-minute bars).

White's reality check: if NO setting had any edge, how good would the best-looking of all tried settings be?
Calendar months are resampled with replacement; every setting's mean bp/trade is recomputed, re-centred on its
own full-sample mean (so the bootstrap world has zero edge everywhere) and divided by its standard error; the
largest value over all settings is kept. The pick's t-statistic is then compared with that distribution.
Only the tuning data (BTC 2024-11 .. 2026-11) is used here."""
import pickle, numpy as np, pandas as pd

z = np.load("opt15m.npz"); D = pd.read_pickle("opt15m_sig.pkl"); EXITS = pickle.load(open("opt15m_exits.pkl", "rb"))
NS, NE, NM = z["N"].shape
N = z["N"].reshape(-1, NM).astype(float); S1 = z["S1"].reshape(-1, NM).astype(float); S2 = z["S2"].reshape(-1, NM).astype(float)
n = N.sum(1)
with np.errstate(all="ignore"):
    mean = S1.sum(1) / n; se = np.sqrt((S2.sum(1) / n - mean ** 2) / np.maximum(n - 1, 1)); t = mean / se
ok = (n >= 200) & np.isfinite(t) & (se > 0)
sig = D.drop(columns=["h", "nsig"]).reset_index(drop=True)
si = sig.index[(sig.divL == 5) & (sig.divMin == 5) & (sig.dayH == 13) & (sig.levels == "42/58")]
ei = [i for i, e in enumerate(EXITS) if e == ("atr", 60, 5, 2, None)]
assert len(si) == 1 and len(ei) == 1
pick = si[0] * NE + ei[0]
print(f"settings tried with >=200 trades: {ok.sum():,} of {len(n):,}")
print(f"the pick: {n[pick]:.0f} trades, {mean[pick]:+.1f} bp/trade, t = {t[pick]:.2f}  (rank {int((t[ok] > t[pick]).sum()) + 1} by t)")
print(f"best t among all settings: {t[ok].max():.2f}")
assert ok[pick] and abs(mean[pick] - 62.9) < 0.2 and abs(t[pick] - 2.82) < 0.02

Nk, S1k, mk, sek = N[ok], S1[ok], mean[ok], se[ok]
rng = np.random.default_rng(20261113); B = 5000; T = np.empty(B)
for b in range(B):
    w = rng.multinomial(NM, np.full(NM, 1.0 / NM)).astype(float)
    with np.errstate(all="ignore"):
        m = (S1k @ w) / (Nk @ w)
    T[b] = np.nanmax((m - mk) / sek)
q = np.quantile(T, [0.5, 0.9, 0.98])
print(f"\nbest t-statistic expected from the search alone (no real edge anywhere), {B} month-resamples:")
print(f"  median {q[0]:.2f}, 90th percentile {q[1]:.2f}, 98th percentile {q[2]:.2f}")
print(f"  share of no-edge worlds whose best setting reaches the pick's t ({t[pick]:.2f}): {np.mean(T >= t[pick]):.3f}")
print(f"  share whose best setting reaches the best t found ({t[ok].max():.2f}): {np.mean(T >= t[ok].max()):.3f}")
print(f"  -> a setting needed t >= {q[2]:.2f} on the tuning data to count as significant at 98% after the search")
