import pandas as pd
import pytest

from pychart.data import CSVProvider, SyntheticProvider, load, normalize, resample, save_csv


def test_synthetic_contract():
    df = SyntheticProvider().fetch("DEMO", "1d", "6mo")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(df.index, pd.DatetimeIndex) and str(df.index.tz) == "UTC"
    assert df.index.is_monotonic_increasing and df.index.is_unique
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()
    assert 100 < len(df) < 140  # ~126 trading days


def test_synthetic_intraday_count():
    df = SyntheticProvider().fetch("DEMO", "1h", "5d")
    assert len(df) > 10
    assert df.index.freq is None
    assert (df.index.hour >= 14).all()


def test_synthetic_is_deterministic():
    a = SyntheticProvider(seed=3).fetch("X", "1d", "1y")
    b = SyntheticProvider(seed=3).fetch("X", "1d", "1y")
    pd.testing.assert_frame_equal(a, b)


def test_normalize_yfinance_multiindex():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    cols = pd.MultiIndex.from_product([["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["AAPL"]])
    raw = pd.DataFrame([[1, 2, 0.5, 1.5, 1.5, 100]] * 3, index=idx, columns=cols)
    df = normalize(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert str(df.index.tz) == "UTC"


def test_normalize_unix_seconds_and_dedup():
    raw = pd.DataFrame({"time": [1704067200, 1704067200, 1704153600], "o": [1, 1, 2], "h": [1, 1, 2],
                        "l": [1, 1, 2], "c": [1, 1.5, 2], "v": [1, 1, 1]})
    df = normalize(raw)
    assert len(df) == 2
    assert df["close"].iloc[0] == 1.5  # last duplicate wins


def test_normalize_rejects_garbage():
    with pytest.raises(ValueError):
        normalize(pd.DataFrame({"a": [1]}))


def test_csv_round_trip(tmp_path):
    df = SyntheticProvider().fetch("DEMO", "1d", "3mo")
    path = save_csv(df, tmp_path / "demo.csv")
    back = CSVProvider(path).fetch()
    pd.testing.assert_frame_equal(df, back, check_freq=False)
    via_load = load("DEMO", csv=path)
    assert len(via_load) == len(df)


def test_resample_to_weekly():
    df = SyntheticProvider().fetch("DEMO", "1d", "1y")
    w = resample(df, "1W")
    assert 45 <= len(w) <= 54
    assert (w["high"] >= w["low"]).all()
    assert w["volume"].sum() == pytest.approx(df["volume"].sum())


def test_load_validates_inputs():
    with pytest.raises(ValueError, match="unknown timeframe"):
        load("X", timeframe="7m", source="synthetic")
    with pytest.raises(ValueError, match="unknown source"):
        load("X", source="bloomberg")
