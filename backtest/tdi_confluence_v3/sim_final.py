"""False-positive rate and power of the amended statistical tests T1a, T1b and T4 (T2/T3 need engine runs; in
worlds with a real edge they pass together with T1, in no-edge worlds they can only lower the rate).
83 calendar months 2017-12 .. 2024-10, Poisson(9.2) trades a month, trade shapes from the 232 demeaned tuning
trades, optional common month effect with carry-over, optional volatility profile by year (bp scale of trades,
roughly BTC's realised volatility relative to 2024-26: an assumption, not measured on the test data)."""
import sys, numpy as np, pandas as pd, validate as V
df = V.load("BTCUSDT_insample"); base = V.Ctx(df).run()[0]; base = base - base.mean()
months = pd.period_range("2017-12", "2024-10", freq="M"); M = len(months); years = months.year.to_numpy()
VOL = {2017: 2.0, 2018: 1.8, 2019: 1.4, 2020: 1.5, 2021: 1.8, 2022: 1.3, 2023: 0.9, 2024: 1.0}
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 1)

def world(edge, shock=60.0, ar=0.0, vol=False, edge_in_R=False):
    n = rng.poisson(9.2, M); g = np.repeat(np.arange(M), n)
    e = np.zeros(M); z = rng.normal(0, shock, M)
    for i in range(M): e[i] = (ar * e[i - 1] if i else 0) + z[i] * np.sqrt(1 - ar * ar)
    sc = np.array([VOL[y] for y in years]) if vol else np.ones(M)
    ed = edge * (sc[g] if edge_in_R else 1.0)
    r = rng.choice(base, n.sum()) * sc[g] + ed + e[g] * sc[g]
    a = V.cluster_t(r, g, M)[1] < 0.02
    b = V.cluster_t(r, g // 6, (M + 5) // 6)[1] < 0.02
    yr = years[g]; c = True
    for y in np.unique(yr):
        k = yr != y; gg = g[k]
        if V.cluster_t(r[k], gg, M)[1] >= 0.05: c = False; break
    return a, b, c

W = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
print(f"{W} worlds per row; columns: T1a, T1b, T4, all three")
rows = [("no edge, month effect", dict(edge=0.0)), ("no edge, carry-over 0.5", dict(edge=0.0, ar=0.5)),
        ("no edge, vol profile", dict(edge=0.0, vol=True))]
rows += [(f"edge {e:g} bp, month effect", dict(edge=e)) for e in (20, 35, 45, 62.9)]
rows += [(f"edge {e:g} bp in 2024-26 units, scaled with volatility", dict(edge=e, vol=True, edge_in_R=True)) for e in (20, 35, 45, 62.9)]
rows += [(f"edge {e:g} bp constant, vol profile", dict(edge=e, vol=True)) for e in (35, 62.9)]
for lab, kw in rows:
    R = np.array([world(**kw) for _ in range(W)])
    print(f"  {lab:52s} {100*R[:,0].mean():5.1f}%  {100*R[:,1].mean():5.1f}%  {100*R[:,2].mean():5.1f}%  {100*R.all(1).mean():5.1f}%")
