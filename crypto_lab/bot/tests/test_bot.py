import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bot  # noqa: E402


def test_size_respects_risk_and_leverage():
    # $10k, 0.5 % risk ($50), $200 stop -> 0.25 BTC ($25k notional, 2.5x); leverage cap 5x -> 0.5 max
    assert bot.size(10000, 0.5, 200, 100000, 5, 0.001, 0.001, 5) == 0.25  # $50 risk / $200 stop
    # tiny stop would give a huge size: capped by leverage, floored to step
    assert bot.size(10000, 0.5, 1, 100000, 5, 0.001, 0.001, 5) == 0.5
    # below min notional -> no trade
    assert bot.size(100, 0.5, 200, 100000, 5, 0.001, 0.001, 500) == 0.0  # $200 notional < $500 minimum


def test_sentinel_daily_halt_and_streak(tmp_path):
    s = bot.Sentinel({"sentinel": dict(daily_halt_pct=3, max_consecutive_losses=3, stale_s=30, max_fill_dev_pct=0.5)}, str(tmp_path / "l.jsonl"))
    s.new_day(10000)
    assert not s.check(9800)
    assert s.check(9699)            # -3.01 %
    s2 = bot.Sentinel({"sentinel": dict(daily_halt_pct=3, max_consecutive_losses=3, stale_s=30, max_fill_dev_pct=0.5)}, str(tmp_path / "l2.jsonl"))
    s2.new_day(10000); s2.losses = 3
    assert s2.check(10000)


def test_sentinel_stale_feed_and_fill_deviation(tmp_path):
    s = bot.Sentinel({"sentinel": dict(daily_halt_pct=3, max_consecutive_losses=3, stale_s=30, max_fill_dev_pct=0.5)}, str(tmp_path / "l.jsonl"))
    s.new_day(10000); s.last_tick = time.time() - 31
    assert s.check(10000)
    s = bot.Sentinel({"sentinel": dict(daily_halt_pct=3, max_consecutive_losses=3, stale_s=30, max_fill_dev_pct=0.5)}, str(tmp_path / "l3.jsonl"))
    assert s.fill_ok(100.0, 100.4)
    assert not s.fill_ok(100.0, 100.6) and s.halted


def test_live_refused_without_env(monkeypatch):
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    try:
        bot.Exchange({"testnet": False})
        assert False, "live endpoint must be refused"
    except SystemExit:
        pass


def test_dry_run_without_keys(monkeypatch):
    monkeypatch.delenv("BINANCE_KEY", raising=False)
    ex = bot.Exchange({"testnet": True, "dry_run": False})
    assert ex.dry  # no key -> never sends an order


def test_testnet_public_endpoints():
    ex = bot.Exchange({"testnet": True, "dry_run": True})
    f = ex.filters("BTCUSDT")
    assert f["tick"] > 0 and f["step"] > 0
    k = ex.public("/fapi/v1/klines", symbol="BTCUSDT", interval="5m", limit=3)
    assert len(k) == 3
