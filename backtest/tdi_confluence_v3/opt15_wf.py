"""Analysis of opt15 results: walk-forward selection, parameter marginals, half-vs-half stability."""
import numpy as np, pandas as pd
from opt15 import EXITS, MONTHS
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 200)
z = np.load("opt15.npz"); D = pd.read_pickle("opt15_sig.pkl")
NS, NE, NM = z["N"].shape
N = z["N"].reshape(-1, NM).astype(np.float64); S1 = z["S1"].reshape(-1, NM).astype(np.float64); S2 = z["S2"].reshape(-1, NM).astype(np.float64)
E = pd.DataFrame([dict(mode=m, atr_tf=a, x=x, rmult=r, trail=("off" if t is None else f"{t[0]}/{t[1]}")) for m, a, x, r, t in EXITS])
P = pd.concat([D.drop(columns=["h", "nsig"]).loc[np.repeat(np.arange(NS), NE)].reset_index(drop=True),
               E.loc[np.tile(np.arange(NE), NS)].reset_index(drop=True)], axis=1)
P["stop"] = np.where(P["mode"] == "atr", P.x.astype(str) + "xATR(" + P.atr_tf.map({0: "chart", 60: "60m", 240: "240m"}) + ")", P.x.astype(str) + "%")

def agg(ms):
    n = N[:, ms].sum(1); s1 = S1[:, ms].sum(1); s2 = S2[:, ms].sum(1)
    with np.errstate(all="ignore"):
        mean = s1 / n; t = mean / np.sqrt((s2 / n - mean ** 2) / np.maximum(n - 1, 1))
    return n, mean, t

def desc(i):
    r = P.iloc[i]
    return (f"piv{r.divL} swing{r.divMin}-{r.divMax} day{r.dayH:02d} lvl={r.levels} 4th={r.req4} "
            f"{'gated ' + r.tfs + '/' + r['div'] if r.fix else 'ungated'} | SL {r.stop} TP {r.rmult:g}R trail {r.trail}")

if __name__ == "__main__":
    print(f"{NS} signal sets x {NE} exits = {NS*NE} backtests, {NM} months")
    allm = list(range(NM)); n, m, t = agg(allm); P["n"] = n; P["bp"] = m; P["t"] = t
    h1 = list(range(0, 12)); h2 = list(range(12, NM))
    n1, m1, t1 = agg(h1); n2, m2, t2 = agg(h2); P["bp_h1"] = m1; P["bp_h2"] = m2; P["t_h1"] = t1; P["t_h2"] = t2; P["n_h1"] = n1; P["n_h2"] = n2
    ok = (n >= 200)
    print(f"\ncombos with >=200 trades: {ok.sum()}; profitable after fees: {100*(m[ok]>0).mean():.1f}%; median {np.median(m[ok]):+.1f}bp; t>2: {100*(t[ok]>2).mean():.2f}%  t>3: {100*(t[ok]>3).mean():.3f}%")
    q = P[ok & (n1 >= 80) & (n2 >= 80)]
    print(f"first year vs second year rank correlation of bp: {q[['bp_h1','bp_h2']].corr('spearman').iloc[0,1]:.3f}; of t: {q[['t_h1','t_h2']].corr('spearman').iloc[0,1]:.3f}")
    print(f"profitable in year 1: {100*(q.bp_h1>0).mean():.0f}%; of those also profitable in year 2: {100*(q[q.bp_h1>0].bp_h2>0).mean():.0f}%; year-2 base rate {100*(q.bp_h2>0).mean():.0f}%")

    print("\n=== Walk-forward: expanding train, 3-month test blocks ===")
    dflt = np.where((P.divL == 5) & (P.divMin == 5) & (P.dayH == 13) & (P.levels == "off") & (~P.req4) & (~P.fix) & (P.stop == "5xATR(60m)") & (P.rmult == 2) & (P.trail == "off"))[0]
    print("default row:", dflt, desc(dflt[0]) if len(dflt) else "")
    rows = []; picks = {"t": [], "mean": []}
    for k in (9, 12, 15, 18, 21):
        tr = list(range(0, k)); te = list(range(k, k + 3 if k < 21 else NM))
        ntr, mtr, ttr = agg(tr); nte, mte, _ = agg(te)
        good = ntr >= 7 * len(tr)
        lab = f"{MONTHS[te[0]]}..{MONTHS[te[-1]]}"
        row = dict(test=lab, combos=int(good.sum()))
        for name, sc in (("t", ttr), ("mean", mtr)):
            s = np.where(good, sc, -np.inf); b = int(np.nanargmax(s)); picks[name].append((b, te))
            row[f"best_{name}: train bp"] = mtr[b]; row[f"best_{name}: test bp"] = mte[b]; row[f"best_{name}: test n"] = nte[b]
            if name == "t": print(f" {lab}: best-t pick -> {desc(b)}  (train {ntr[b]:.0f} tr {mtr[b]:+.1f}bp t={ttr[b]:.2f}; test {nte[b]:.0f} tr {mte[b]:+.1f}bp)")
        top = np.argsort(np.where(good, ttr, -np.inf))[::-1]
        for frac, nm in ((0.001, "top0.1%"), (0.01, "top1%"), (0.1, "top10%")):
            idx = top[: max(1, int(good.sum() * frac))]
            row[f"{nm} by t: test bp"] = S1[idx][:, te].sum() / N[idx][:, te].sum()
        row["all combos: test bp"] = S1[good][:, te].sum() / N[good][:, te].sum()
        row["default: test bp"] = mte[dflt[0]] if len(dflt) else np.nan
        rows.append(row)
    W = pd.DataFrame(rows).set_index("test"); print(W.round(1).T.to_string())
    for name in ("t", "mean"):
        nn = sum(N[b, te].sum() for b, te in picks[name]); ss = sum(S1[b, te].sum() for b, te in picks[name]); s2 = sum(S2[b, te].sum() for b, te in picks[name])
        mu = ss / nn; print(f" walk-forward best-{name}: {nn:.0f} test trades, {mu:+.1f}bp/trade, t={mu/np.sqrt((s2/nn-mu*mu)/(nn-1)):.2f}")
    if len(dflt):
        te = list(range(9, NM)); d0 = dflt[0]; nn = N[d0, te].sum(); mu = S1[d0, te].sum() / nn
        print(f" default over the same test months: {nn:.0f} trades, {mu:+.1f}bp/trade, t={mu/np.sqrt((S2[d0, te].sum()/nn-mu*mu)/(nn-1)):.2f}")

    print("\n=== Marginals: median bp over all combos with >=200 trades [all 2y | year1 | year2 | share profitable] ===")
    Q = P[ok]
    for col in ["divL", "divMin", "dayH", "levels", "req4", "fix", "tfs", "div", "mode", "stop", "rmult", "trail"]:
        g = Q.groupby(col).agg(combos=("bp", "size"), trades=("n", "median"), bp=("bp", "median"), y1=("bp_h1", "median"), y2=("bp_h2", "median"), prof=("bp", lambda x: 100 * (x > 0).mean()), t=("t", "median"))
        print(f"\n{col}:"); print(g.round(2).to_string())
    U = Q[~Q.fix]
    print("\n=== Ungated only: stop x TP (median bp, trail off) ===")
    print(U[U.trail == "off"].pivot_table(index="stop", columns="rmult", values="bp", aggfunc="median").round(1).to_string())
    print("\n=== Ungated only: pivot x levels (median bp) ==="); print(U.pivot_table(index="divL", columns="levels", values="bp", aggfunc="median").round(1).to_string())
    print("\n=== Top 25 by 2-year t (>=250 trades, both years >=80 trades) ===")
    top = P[(P.n >= 250) & (P.n_h1 >= 80) & (P.n_h2 >= 80)].sort_values("t", ascending=False).head(25)
    for i, r in top.iterrows(): print(f" t={r.t:.2f} n={r.n:.0f} {r.bp:+.1f}bp | y1 {r.bp_h1:+.1f} y2 {r.bp_h2:+.1f} :: {desc(i)}")
    P.to_pickle("opt15_summary.pkl")
