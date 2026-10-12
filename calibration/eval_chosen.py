"""Handoff metrics for the chosen parent / child-zone settings per filter timeframe (and the default and the
tuned-best for comparison): ROC-AUC, directional accuracy (raw and balanced) and coverage of the filter's zone
output, at 1, 3 and 10 filter candles, on train (2023), validation (2024-01 .. 2025-06) and final test
(2025-07 .. 2026-10). The choice itself (results_auc2/auc_pick.json) used train + validation only."""
import json, sys
import numpy as np
import pandas as pd
import fgrun as R
import dir_auc as A

SPLITS = (("train_2023", "2023-01-01", "2024-01-01"), ("valid_2024_2025H1", "2024-01-01", "2025-07-01"),
          ("test_2025H2_2026", "2025-07-01", "2026-10-12"))
NAMES = {5: "5m", 15: "15m", 30: "30m", 60: "1H", 120: "2H", 240: "4H", 480: "8H", 1440: "1D"}


def zone_series(S, tf, pm, zs, ma, band=A.BAND):
    p = R.params(parent_tf=tf * pm, zones=A.zones(tf, zs), min_aligned=ma, use_zones=True, burst_atr=0.5, fd_tf=tf)
    ctx = R.context(S, tf, p)
    c = ctx["ch"]["c"]
    L, At, D = A.held(c, ctx["atr14"], ctx["buy"], ctx["sell"], ctx["bpx"], ctx["spx"])
    b = band * np.nan_to_num(At)
    z = np.where(c > L + b, 1, np.where(c < L - b, -1, 0)).astype(np.int8)
    z[np.isnan(L)] = 0
    return ctx["ch"], z


def metrics(ch, z, warm=300):
    c, t = ch["c"], ch["t_open"]
    N = len(c)
    rows = []
    for name, a, b in SPLITS:
        m = (t >= int(pd.Timestamp(a, tz="UTC").timestamp())) & (t < int(pd.Timestamp(b, tz="UTC").timestamp())) & (np.arange(N) >= warm)
        r = dict(split=name, bars=int(m.sum()), coverage=float((z[m] != 0).mean()), buy_zone_share=float((z[m] == 1).mean()), sell_zone_share=float((z[m] == -1).mean()))
        for H in A.HS:
            fwd = np.full(N, np.nan); fwd[:-H] = c[H:] - c[:-H]
            ok = m & ~np.isnan(fwd) & (fwd != 0)
            y = (fwd > 0).astype(int)
            r[f"auc_h{H}"] = A.auc_counts(z[ok], y[ok])
            called = ok & (z != 0)
            hit = ((z == 1) & (fwd > 0)) | ((z == -1) & (fwd < 0))
            r[f"acc_h{H}"] = float(hit[called].mean()) if called.any() else np.nan
            pu = float((fwd[ok & (z == 1)] > 0).mean()) if (ok & (z == 1)).any() else np.nan
            pdn = float((fwd[ok & (z == -1)] < 0).mean()) if (ok & (z == -1)).any() else np.nan
            r[f"bal_acc_h{H}"] = 0.5 * (pu + pdn)
            r[f"up_rate_h{H}"] = float(y[ok].mean())
            r[f"calls_h{H}"] = int(called.sum())
        r["auc_mean"] = np.mean([r[f"auc_h{H}"] for H in A.HS])
        r["acc_mean"] = np.mean([r[f"acc_h{H}"] for H in A.HS])
        r["bal_acc_mean"] = np.mean([r[f"bal_acc_h{H}"] for H in A.HS])
        rows.append(r)
    return rows


if __name__ == "__main__":
    pick = json.load(open("results_auc2/auc_pick.json"))
    S = R.Source(pd.read_parquet("btc_1m.parquet"), 1)
    out = []
    for tf_s, pk in pick.items():
        tf = int(tf_s)
        variants = {"chosen": (pk["pm"], pk["zones"], pk["ma"]), "default": (1, "x1/x2/x4", 2)}
        bt = pk["best_tuned"]
        if (bt["pm"], bt["zones"], bt["ma"]) != variants["chosen"]:
            variants["tuned_best_not_chosen"] = (bt["pm"], bt["zones"], bt["ma"])
        for vname, (pm, zstr, ma) in variants.items():
            zs = tuple(int(x[1:]) for x in zstr.split("/")) if zstr != "none" else ()
            if not zs:
                continue
            ch, z = zone_series(S, tf, pm, zs, ma)
            for r in metrics(ch, z):
                out.append(dict(filter_tf=NAMES[tf], filter_tf_min=tf, variant=vname, parent=f"x{pm}", parent_tf_min=tf * pm,
                                child_zones=zstr, child_zone_tfs_min="/".join(str(R.tv_tf(tf * int(x[1:]))) for x in zstr.split("/")),
                                min_aligned=ma, chosen_by_rule=("tuned" if pk["tuned"] else "default"), insample_rank_corr=pk["insample_rank_corr"], **r))
        print("done", tf, flush=True)
    df = pd.DataFrame(out)
    df.to_csv(sys.argv[1], index=False, float_format="%.4f")
    print(df[df.variant == "chosen"][["filter_tf", "parent_tf_min", "child_zone_tfs_min", "min_aligned", "split", "auc_mean", "acc_mean", "bal_acc_mean", "coverage"]].round(3).to_string(index=False))
