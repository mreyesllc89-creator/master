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


class ReviewRegressions(unittest.TestCase):
    """Cases found by the EVK review."""

    def write(self, text, encoding="utf-8"):
        f = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
        f.write(text.encode(encoding))
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def grid_rows(self, fast_vals, slow_vals, edge_at):
        rows, pid = [], 0
        t0 = int(pd.Timestamp("2025-01-01").timestamp())
        for fast in fast_vals:
            for slow in slow_vals:
                pid += 1
                for k in range(80):
                    good = (fast, slow) == edge_at
                    p = 100.0 if (k % 3 != 0 if good else k % 2 == 0) else -100.0
                    rows.append(trade(pid, fast, slow, "A", t0 + k * 86400 * 4, p))
        return rows

    def test_neighbours_mixed_int_float(self):
        path = make_csv(self.grid_rows((5, 10, 15), (0.5, 1.0, 1.5), (10, 1.0)))
        self.addCleanup(os.unlink, path)
        run = load(path)
        tab = A.pass_table(run, "auto", None)
        nb = A.neighbours(run, tab, "all_pf")
        centre = [q for q in tab.index if run.label(q) == "Fast=10, Slow=1"][0]
        self.assertEqual(nb.loc[centre, "nb_n"], 5)          # itself + 2 + 2 neighbours

    def test_hash_in_value_keeps_rows(self):
        head = HEAD.replace("p.Mode", "p.Comment")
        rows = [trade(1, 5, 20, "run#1", 1735689600 + k * 3600, 50.0 if k % 2 else -40.0) for k in range(10)]
        run = load(self.write(head + "\n".join(rows) + "\n"))
        self.assertEqual(len(run.trades), 10)

    def test_cp1252_file(self):
        head = HEAD.replace("TestEA", "EA_é")
        rows = [trade(1, 5, 20, "Ü", 1735689600 + k * 3600, 50.0 if k % 2 else -40.0) for k in range(5)]
        run = load(self.write(head + "\n".join(rows) + "\n", encoding="cp1252"))
        self.assertEqual(len(run.trades), 5)

    def test_empty_run(self):
        run = load(self.write(HEAD + "1,0,5,20,A,,,,,,,,,,,\n2,0,10,20,A,,,,,,,,,,,\n"))
        self.assertTrue(run.trades.empty)
        tab = A.pass_table(run, "auto", None)
        self.assertEqual(tab.all_trades.sum(), 0)

    def test_header_only_file_message(self):
        with self.assertRaises(ValueError):
            load(self.write("# EVK 1.0 | X | Y | Z | t\n"))

    def test_partial_r_uses_money(self):
        rows = [trade(1, 5, 20, "A", 1735689600 + k * 3600, 50.0 if k % 2 else -40.0, risk=0 if k == 3 else 100.0)
                for k in range(40)]
        run = load(self.write(HEAD + "\n".join(rows) + "\n"))
        self.assertFalse(run.has_r)
        self.assertEqual(run.r_missing, 1)
        x = run.trades["r"].to_numpy(float)       # forcing R: NaN must be ignored, not poison the score
        self.assertTrue(np.isfinite(score(None, x, "pf", 10)))

    def test_compare_refuses_different_grids(self):
        a = make_csv(self.grid_rows((5, 10), (20, 30), (5, 20)))
        rows_b = [r.replace(",A,", ",B,") for r in self.grid_rows((5, 10), (20,), (5, 20))]
        b = make_csv(rows_b)
        self.addCleanup(os.unlink, a)
        self.addCleanup(os.unlink, b)
        with self.assertRaises(ValueError):
            A.compare(load(a), load(b), "auto")


if __name__ == "__main__":
    unittest.main()
