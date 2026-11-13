"""Early exploration (superseded by sim_final.py and sim_regimes.py): no-edge pass rate of T1a / T1b in 87-month histories, without T4."""
import numpy as np, validate as V
from sim_power import world   # reuses the 232 demeaned tuning trades
import sim_power
sim_power.rng = np.random.default_rng(11)
W = 20000
for shock, ar, lab in ((0.0, 0.0, "independent trades"), (60.0, 0.0, "month effect"), (60.0, 0.3, "carry-over 0.3"), (60.0, 0.5, "carry-over 0.5")):
    res = np.array([world(0.0, shock, ar) for _ in range(W)])
    a, b, c = 100 * res[:, 0].mean(), 100 * res[:, 1].mean(), 100 * (res[:, 0] & res[:, 1]).mean()
    se = 100 * np.sqrt(0.02 * 0.98 / W)
    print(f"no edge, {lab:20s}: T1a {a:4.2f}%  T1b {b:4.2f}%  both {c:4.2f}%   (+-{se:.2f} Monte Carlo)")
