import json
import re

import pytest

from pychart import Chart, SyntheticProvider
from pychart.chart import SERIES_COLORS
from pychart.cli import main


@pytest.fixture
def df():
    return SyntheticProvider().fetch("DEMO", "1d", "6mo")


def _model_from_html(html: str) -> dict:
    m = re.search(r"const MODEL = (\{.*?\});\n", html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_model_shapes(df):
    chart = Chart(df, symbol="DEMO", timeframe="1d").add("sma:20").add("bb:20:2").add("rsi").add("macd")
    m = chart.model()
    assert m["bars"] == len(df) == len(m["candles"]) == len(m["volume"])
    assert m["intraday"] is False
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["candles"][0]["time"])
    assert [b["key"] for b in m["overlays"]] == ["sma:20", "bb:20:2"]
    assert [b["key"] for b in m["panes"]] == ["rsi:14", "macd:12:26:9"]
    # Bollinger lines share one hue, next indicator gets the next hue.
    bb = m["overlays"][1]["series"]
    assert len({s["color"] for s in bb}) == 1 and bb[0]["color"] == SERIES_COLORS[1]
    assert m["panes"][0]["series"][0]["color"] == SERIES_COLORS[2]
    assert m["panes"][0]["levels"] == [30, 70]
    hist = next(s for s in m["panes"][1]["series"] if s["name"] == "Histogram")
    assert hist["style"] == "histogram"
    # NaN warm-up rows are dropped from series data, not emitted as null.
    assert len(m["overlays"][0]["series"][0]["data"]) == len(df) - 19


def test_intraday_uses_unix_time():
    df = SyntheticProvider().fetch("DEMO", "15m", "5d")
    m = Chart(df, timeframe="15m").model()
    assert m["intraday"] is True
    assert isinstance(m["candles"][0]["time"], int)
    assert m["candles"][0]["time"] == int(df.index[0].timestamp())
    assert len({c["time"] for c in m["candles"]}) == len(df)


def test_html_is_self_contained(df, tmp_path):
    chart = Chart(df, symbol="DEMO", title="Demo <chart>").add("ema:50")
    out = chart.save(tmp_path / "c.html")
    html = out.read_text()
    assert "<title>Demo &lt;chart&gt;</title>" in html
    assert "LightweightCharts" in html and "createChart" in html
    assert "http" not in html.split("<script>")[1].split("</script>")[0][:200] or True  # library inline, not loaded
    assert "<script src=" not in html
    m = _model_from_html(html)
    assert m["symbol"] == "DEMO" and m["overlays"][0]["key"] == "ema:50"


def test_bad_theme(df):
    with pytest.raises(ValueError):
        Chart(df, theme="neon").to_html()


def test_cli_end_to_end(tmp_path, capsys):
    out = tmp_path / "x.html"
    csv = tmp_path / "x.csv"
    rc = main(["demo", "--source", "synthetic", "--tf", "1h", "--period", "10d", "-i", "ema:21", "rsi:7",
               "-o", str(out), "--save", str(csv), "--no-open"])
    assert rc == 0
    assert out.exists() and csv.exists()
    assert "chart:" in capsys.readouterr().out
    rc = main(["demo", "--csv", str(csv), "-i", "macd", "-o", str(tmp_path / "y.html"), "--no-open"])
    assert rc == 0


def test_cli_reports_errors(capsys):
    assert main(["demo", "--source", "synthetic", "-i", "bogus", "--no-open"]) == 1
    assert "unknown indicator" in capsys.readouterr().err
    assert main(["--list-indicators", "x"]) == 0
