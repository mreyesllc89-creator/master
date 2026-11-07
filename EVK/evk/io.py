"""Read EVK CSV files written by EVK.mqh (or by any tool using the same format).

Format (one row per closed trade; a pass with no trades has one row with empty trade fields):
    # EVK <version> | <EA> | <symbol> | <currency> | times are broker server time
    pass,criterion,p.<input1>,p.<input2>,...,open_time,close_time,side,volume,entry,exit,sl,profit,risk,r,magic
Times are Unix seconds in broker server time.
"""
import pandas as pd

TRADE_COLS = ["open_time", "close_time", "side", "volume", "entry", "exit", "sl", "profit", "risk", "r", "magic"]


class Run:
    """One optimization (or single test): passes, their inputs and their trades."""

    def __init__(self, df, meta=""):
        self.meta = meta
        self.param_cols = [c for c in df.columns if c.startswith("p.")]
        # inputs that actually vary between passes are the optimized ones
        self.varying = [c for c in self.param_cols if df[c].nunique(dropna=False) > 1]
        has_trade = df["close_time"].notna()
        self.trades = df[has_trade].copy()
        for c in ("open_time", "close_time"):
            self.trades[c] = pd.to_datetime(self.trades[c].astype("int64"), unit="s")
        self.trades = self.trades.sort_values(["pass", "close_time"]).reset_index(drop=True)
        self.passes = df.drop_duplicates("pass")[["pass", "criterion"] + self.param_cols].set_index("pass")
        # R needs an initial stop loss; fall back to money when no trade has one
        self.has_r = self.trades["r"].notna().mean() > 0.5 if len(self.trades) else False

    def value_col(self, value):
        if value == "auto":
            return "r" if self.has_r else "profit"
        return value

    def label(self, p):
        row = self.passes.loc[p]
        def fmt(v):
            if isinstance(v, float) and v.is_integer():
                return str(int(v))
            return str(v)
        return ", ".join(f"{c[2:]}={fmt(row[c])}" for c in self.varying) or f"pass {p}"


def load(path):
    meta = ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline()
        if first.startswith("#"):
            meta = first[1:].strip()
    df = pd.read_csv(path, comment="#", dtype={"side": "string"})
    missing = {"pass", "criterion"} - set(df.columns) | (set(TRADE_COLS) - set(df.columns))
    if missing:
        raise ValueError(f"{path}: not an EVK file (missing columns {sorted(missing)})")
    return Run(df, meta)
