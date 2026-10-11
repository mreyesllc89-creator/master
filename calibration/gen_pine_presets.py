"""Generate the Pine preset block from presets.json (ternary chains on the chart bucket pTf, all simple values)."""
import json, sys

ORDER = [1, 5, 15, 30, 60, 120, 240, 480, 1440]


def chain(name, typ, vals, fmt):
    parts = [f"pTf == {tf} ? {fmt(v)}" for tf, v in zip(ORDER[:-1], vals[:-1])]
    return f"{typ} {name} = " + " : ".join(parts) + f" : {fmt(vals[-1])}"


def load(path):
    """presets.json (one dict keyed by timeframe) or a results directory of preset_<tf>.json files."""
    import os
    if os.path.isdir(path):
        P = {}
        for tf in ORDER:
            f = os.path.join(path, f"preset_{tf}.json")
            if os.path.exists(f):
                P[str(tf)] = json.load(open(f))
        return P
    return json.load(open(path))


def main(path="presets.json"):
    P = load(path)
    rows = []
    for tf in ORDER:
        k = str(tf)
        if k in P:
            e, f, x = P[k]["entry"], P[k]["filter"], P[k]["exits"]
        else:   # not calibrated: neutral values (the strategy's own defaults)
            e = dict(pm=4, ma=2, fm=1); f = dict(parent=1, hurst=0, bmin=0, bmax=100, smin=0, smax=100, pbmin=0, psmax=100, areg=0)
            x = dict(sl=2.0, tpr=2.0, act=4.0, dst=0.2, rm=0, rmax=0, xopp=False, xbrk=True)
        res = P[k]["results"]["preset"] if k in P and "results" in P[k] else {}
        rows.append((e, f, x, res))
    i = lambda v: str(int(v))
    fl = lambda v: f"{float(v):g}" if float(v) != int(float(v)) else f"{float(v):.1f}"
    b = lambda v: "true" if v else "false"
    lines = ["// preset table, one value per chart bucket (1, 5, 15, 30, 60, 120, 240, 480 minutes, 1D)",
             chain("pPm", "int", [r[0]["pm"] for r in rows], i),
             chain("pMa", "int", [r[0]["ma"] for r in rows], i),
             chain("pFm", "int", [r[0]["fm"] for r in rows], i),
             chain("pBurst", "float", [r[1].get("burst", 0.5) for r in rows], fl),
             chain("pParent", "bool", [r[1]["parent"] for r in rows], b),
             chain("pHurst", "int", [r[1]["hurst"] for r in rows], i),
             chain("pBuyFastMin", "float", [r[1]["bmin"] for r in rows], fl),
             chain("pBuyFastMax", "float", [r[1]["bmax"] for r in rows], fl),
             chain("pSellFastMin", "float", [r[1]["smin"] for r in rows], fl),
             chain("pSellFastMax", "float", [r[1]["smax"] for r in rows], fl),
             chain("pBuyPFastMin", "float", [r[1]["pbmin"] for r in rows], fl),
             chain("pSellPFastMax", "float", [r[1]["psmax"] for r in rows], fl),
             chain("pAtrReg", "float", [r[1]["areg"] for r in rows], fl),
             chain("pSl", "float", [r[2]["sl"] for r in rows], fl),
             chain("pTpR", "float", [r[2]["tpr"] for r in rows], fl),
             chain("pTrailAct", "float", [r[2]["act"] for r in rows], fl),
             chain("pTrailDst", "float", [r[2]["dst"] for r in rows], fl),
             chain("pReMode", "int", [r[2]["rm"] for r in rows], i),
             chain("pReMax", "int", [r[2]["rmax"] for r in rows], i),
             chain("pExitOpp", "bool", [r[2]["xopp"] for r in rows], b),
             chain("pExitBreak", "bool", [r[2]["xbrk"] for r in rows], b),
             "// the preset's test results, 1-minute intrabar fills, 0.05% fee per side: profit factor in-sample (2023-01..2025-06) and out-of-sample (2025-07..2026-10)",
             chain("pIsPf", "float", [round(r[3].get("is_pf", 0.0), 2) for r in rows], fl),
             chain("pOosPf", "float", [round(r[3].get("oos_pf", 0.0), 2) for r in rows], fl),
             ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "presets.json"))
