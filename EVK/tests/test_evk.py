"""Unit tests for the EVK Python tool:  python -m unittest discover -s EVK/tests"""
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from evk import analyze as A  # noqa: E402
from evk.io import load  # noqa: E402
from evk.metrics import max_drawdown, pf, score, stats  # noqa: E402

HEAD = ("# EVK 1.0 | TestEA | XAUUSD | USD | times are broker server time\n"
        "pass,criterion,p.Fast,p.Slow,p.Mode,open_time,close_time,side,volume,entry,exit,sl,profit,risk,r,magic\n")


def make_csv(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
    f.write(HEAD)
    for r in rows:
        f.write(r + "\n")
    f.close()
    return f.name


def trade(pid, fast, slow, mode, t, profit, risk=100.0):
    r = f"{profit / risk:.4f}" if risk else ""
    return f"{pid},1.0,{fast},{slow},{mode},{t},{t + 600},sell,0.10,2000,1999,2001,{profit},{risk if risk else 0},{r},7"


class Metrics(unittest.TestCase):
    def test_pf(self):
        self.assertAlmostEqual(pf([2, -1, 3, -1]), 2.5)
        self.assertEqual(pf([1, 2]), 100.0)          # no loss -> capped
        self.assertTrue(np.isnan(pf([])))

    def test_drawdown(self):
        self.assertEqual(max_drawdown([1, -2, 1, -3, 5]), 4.0)
        self.assertEqual(max_drawdown([1, 1]), 0.0)

    def test_stats_empty(self):
        s = stats([])
        self.assertEqual(s["trades"], 0)

    def test_score_min_period(self):
        t = pd.to_datetime(["2025-01-05", "2025-01-20", "2025-02-05", "2025-02-20"]).to_numpy()
        edges = np.array(pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]), "datetime64[ns]")
        self.assertAlmostEqual(score(t, np.array([2, -1, 1, -1.0]), "min_period_pf", 1, edges), 1.0)
        self.assertEqual(score(t, np.array([2, -1, 1, -1.0]), "pf", 10, edges), -np.inf)  # too few trades


class LoadAndAnalyze(unittest.TestCase):
    def setUp(self):
        rows = []
        t0 = int(pd.Timestamp("2025-01-01").timestamp())
        rng = np.random.default_rng(1)
        pid = 0
        for fast in (5, 10, 15):
            for slow in (20, 30):
                pid += 1
                edge = 0.15 if (fast, slow) == (10, 20) else -0.05
                for k in range(200):
                    p = 100.0 if rng.random() < 0.5 + edge else -100.0
                    rows.append(trade(pid, fast, slow, "A", t0 + k * 86400 * 2, p))
        rows.append(f"99,0,20,40,A" + ",,,,,,,,,,,")   # a pass with no trades
        self.path = make_csv(rows)
        self.run = load(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_load(self):
        self.assertEqual(len(self.run.passes), 7)
        self.assertEqual(set(self.run.varying), {"p.Fast", "p.Slow"})   # Mode is constant
        self.assertTrue(self.run.has_r)
        self.assertEqual(len(self.run.trades), 6 * 200)
        self.assertIn(99, self.run.passes.index)

    def test_holdout_finds_edge(self):
        ho = A.holdout(self.run, "auto", "2025-08-01", "pf", 30, smooth=False)
        self.assertEqual(self.run.label(ho["chosen"]), "Fast=10, Slow=20")
        self.assertGreater(ho["table"].loc[ho["chosen"], "oos_pf"], 1.0)
        self.assertEqual(ho["table"].loc[99, "all_trades"], 0)

    def test_neighbours(self):
        tab = A.pass_table(self.run, "auto", None)
        nb = A.neighbours(self.run, tab, "all_pf")
        p = [q for q in tab.index if self.run.label(q) == "Fast=10, Slow=20"][0]
        self.assertGreaterEqual(nb.loc[p, "nb_n"], 3)           # itself + Fast 5/15 + Slow 30

    def test_walkforward(self):
        wf = A.walkforward(self.run, "auto", 3, 1, "pf", 10, smooth=False)
        self.assertGreater(len(wf["windows"]), 5)
        self.assertGreater(wf["oos"]["trades"], 0)
        for w in wf["windows"]:
            if w.get("chosen"):
                self.assertLess(w["train"].split("..")[1], w["test"].split("..")[0])  # no overlap

    def test_stress(self):
        x = self.run.trades[self.run.trades["pass"] == 1]["r"]
        st = A.stress(x, n_sims=200)
        self.assertEqual(st["cost"][0]["pf"], pf(x))
        self.assertGreaterEqual(st["mc_drawdown"]["p95"], st["mc_drawdown"]["p50"])

    def test_compare_identical(self):
        c = A.compare(self.run, self.run, "auto", "A", "B")
        self.assertEqual(c["share_pf_up"], 0.0)
        self.assertAlmostEqual(c["pf_a"], c["pf_b"])

    def test_money_mode(self):
        rows = [trade(1, 5, 20, "A", 1735689600 + k * 3600, 50.0 if k % 3 else -40.0, risk=0) for k in range(60)]
        path = make_csv(rows)
        try:
            run = load(path)
            self.assertFalse(run.has_r)
            self.assertEqual(run.value_col("auto"), "profit")
        finally:
            os.unlink(path)

    def test_cli(self):
        from evk.__main__ import main
        out = self.path.replace(".csv", ".html")
        main(["analyze", self.path, "--split", "2025-08-01", "--criterion", "pf", "--out", out, "--no-smooth"])
        self.assertTrue(os.path.getsize(out) > 5000)
        os.unlink(out)


if __name__ == "__main__":
    unittest.main()
