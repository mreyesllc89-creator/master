import numpy as np
import pandas as pd
import pytest

from pychart.data import SyntheticProvider
from pychart.indicators import INDICATORS, compute, ema, parse_spec, rma, sma


@pytest.fixture
def df():
    return SyntheticProvider(seed=1).fetch("TEST", "1d", "1y")


def test_sma_matches_rolling_mean():
    s = pd.Series([1.0, 2, 3, 4, 5, 6])
    out = sma(s, 3)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[-1] == 5.0


def test_ema_is_sma_seeded():
    s = pd.Series([10.0, 11, 12, 13, 14, 15])
    out = ema(s, 3)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(11.0)           # seed = SMA(3)
    assert out.iloc[3] == pytest.approx(0.5 * 13 + 0.5 * 11)  # alpha = 2/(3+1)


def test_rma_wilder():
    s = pd.Series([1.0, 2, 3, 4, 5])
    out = rma(s, 2)
    assert out.iloc[1] == 1.5
    assert out.iloc[2] == pytest.approx(0.5 * 3 + 0.5 * 1.5)


def test_rsi_bounds_and_extremes(df):
    rsi = compute(df, "rsi:14")["RSI 14"].dropna()
    assert len(rsi) == len(df) - 14
    assert rsi.between(0, 100).all()

    up = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": np.arange(1, 40, dtype=float), "volume": 1})
    assert compute(up, "rsi:14")["RSI 14"].iloc[-1] == pytest.approx(100.0)


def test_macd_components(df):
    out = compute(df, "macd")
    assert set(out) == {"MACD", "Signal", "Histogram"}
    valid = out["Histogram"].dropna()
    assert len(valid) > 0
    diff = (out["MACD"] - out["Signal"]).dropna()
    pd.testing.assert_series_equal(diff, valid, check_names=False)


def test_bollinger_symmetric(df):
    out = compute(df, "bb:20:2")
    basis, upper, lower = out["BB basis 20"], out["BB upper 20"], out["BB lower 20"]
    np.testing.assert_allclose((upper - basis).dropna(), (basis - lower).dropna())
    assert (upper.dropna() >= lower.dropna()).all()


def test_vwap_resets_each_session():
    idx = pd.to_datetime(["2024-01-02 14:30", "2024-01-02 15:30", "2024-01-03 14:30"], utc=True)
    d = pd.DataFrame({"open": [10, 10, 20.0], "high": [10, 10, 20.0], "low": [10, 10, 20.0],
                      "close": [10, 10, 20.0], "volume": [1, 1, 1.0]}, index=idx)
    v = compute(d, "vwap")["VWAP"]
    assert v.tolist() == [10.0, 10.0, 20.0]


def test_atr_positive(df):
    atr = compute(df, "atr:14")["ATR 14"].dropna()
    assert (atr > 0).all()


def test_parse_spec_defaults_and_errors():
    assert parse_spec("ema").args == (20,)
    assert parse_spec("ema:50").args == (50,)
    assert parse_spec("bb:10:1.5").args == (10, 1.5)
    assert parse_spec("MACD:5:13:4").label == "macd:5:13:4"
    with pytest.raises(ValueError, match="unknown indicator"):
        parse_spec("nope:3")
    with pytest.raises(ValueError, match="must be int"):
        parse_spec("sma:abc")
    with pytest.raises(ValueError, match="at most"):
        parse_spec("sma:1:2")


def test_every_indicator_runs_with_defaults(df):
    for key in INDICATORS:
        out = compute(df, key)
        assert out, key
        for name, s in out.items():
            assert len(s) == len(df), (key, name)
            assert s.notna().any(), (key, name)
