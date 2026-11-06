# Testing with pytest

## Layout
```
project/
├── src/pkg/...
└── tests/
    ├── conftest.py        # shared fixtures
    ├── test_indicators.py
    └── data/              # small fixture files, never multi-MB
```
Run: `python -m pytest -q` (the `-m` form guarantees `src/` is importable when
`pyproject.toml` has `[tool.pytest.ini_options] pythonpath = ["src"]`).

## Writing tests
- Name tests by behaviour: `test_rsi_matches_reference_values`, `test_rejects_negative_qty`.
- One assertion idea per test; several `assert` lines are fine if they check one idea.
- Arrange / act / assert, separated by a blank line.
- `pytest.approx` or `numpy.testing.assert_allclose` for floats, with explicit `rel`/`abs`.
- `@pytest.mark.parametrize` for tables of inputs. Give ids:

```python
@pytest.mark.parametrize(
    ("side", "entry", "sl", "expected"),
    [("buy", 100.0, 99.0, 1.0), ("sell", 100.0, 101.0, 1.0)],
    ids=["long", "short"],
)
def test_risk_distance(side, entry, sl, expected):
    assert risk_distance(side, entry, sl) == pytest.approx(expected)
```

- `tmp_path` for files, `monkeypatch` for env vars and attributes, `capsys` for stdout,
  `caplog` for log records.
- `pytest.raises(ValueError, match="qty")` to assert on errors; always pass `match`.
- Mock at the boundary you own (`monkeypatch.setattr(mod, "fetch_rates", fake)`), not
  deep inside third-party code. Prefer handing a fake object to the function over
  `unittest.mock.patch` strings.
- Freeze time with a fixture that returns a fixed `datetime`, or inject a `now()` callable.

## Fixtures
```python
@pytest.fixture
def ohlc() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=300, freq="5min", tz="UTC")
    rng = np.random.default_rng(0)
    close = 100 + rng.standard_normal(300).cumsum()
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close}, index=idx)
```
Seed random data so failures reproduce. Scope fixtures `session` only when they are
expensive and immutable.

## Reference-value tests for indicators
Indicator code is where silent maths errors live. For each indicator keep a small table
of known values (hand-computed, or exported once from TradingView / MetaTrader) and
assert the last few rows match within `abs=1e-6` (or the symbol's tick size when the
source was a chart export). Document the origin of the table in the test.

## Property-style checks worth adding
- RSI stays within 0..100; ATR is non-negative; SMA(n) of a constant series is that constant.
- A backtest with zero signals produces zero trades and unchanged equity.
- Position sizing never exceeds the allowed risk, for a grid of prices and stops.

## Speed and flakiness
- Mark slow tests `@pytest.mark.slow` and deselect with `-m "not slow"` by default.
- Never depend on network, wall clock, or the user's home directory.
- `pytest -x --lf` reruns only last failures while iterating.
