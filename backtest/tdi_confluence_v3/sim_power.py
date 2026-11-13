"""Early exploration (superseded by sim_final.py and sim_regimes.py, which PREREGISTRATION.md cites): pass rate of
T1a (month-clustered t) and T1b (6-month-clustered t), both one-sided p < 0.02, without T4, in simulated 87-month
histories with about 9.2 trades a month and a trade sd of 340 bp (tuning-data values).
'shock' = sd of a common month effect; 0.0 = independent trades. A 60 bp effect gives a clustered/plain SE ratio of
about 1.13 (a variance ratio of about 1.27); the tuning data's calendar-month SE ratio is 1.27, its average over
month boundaries shifted 0-29 days about 1.12-1.13. ar = month-to-month carry-over of that effect. Trade returns are drawn from the 232 real
tuning trades (demeaned, so the shape is the real one) plus the edge."""
import sys, numpy as np, pandas as pd, validate as V
df = V.load("BTCUSDT_insample"); base = V.Ctx(df).run()[0]; base = base - base.mean()
rng = np.random.default_rng(5); M = 87
def world(edge, shock, ar):
    n = rng.poisson(9.2, M); g = np.repeat(np.arange(M), n)
    e = np.zeros(M); z = rng.normal(0, shock, M)
    for i in range(M): e[i] = (ar * e[i - 1] if i else 0) + z[i] * np.sqrt(1 - ar * ar)
    r = rng.choice(base, n.sum()) + edge + e[g]
    a = V.cluster_t(r, g, M)[1]; b = V.cluster_t(r, g // 6, (M + 5) // 6)[1]
    return a < 0.02, b < 0.02
if __name__ != "__main__":
    W = 0
else:
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
if W: print(f"{W} worlds per row")
for shock, ar, lab in ((0.0, 0.0, "independent trades"), (60.0, 0.0, "month effect 60 bp"),
                       (60.0, 0.3, "month effect, carry-over 0.3"), (60.0, 0.5, "month effect, carry-over 0.5")):
    for edge in ((0.0, 20.0, 35.0, 45.0, 62.9) if W else ()):
        res = np.array([world(edge, shock, ar) for _ in range(W)])
        print(f"  {lab:46s} edge {edge:5.1f} bp: T1a {100*res[:,0].mean():5.1f}%  T1b {100*res[:,1].mean():5.1f}%  both {100*(res[:,0]&res[:,1]).mean():5.1f}%")
