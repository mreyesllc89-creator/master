"""Night-lab execution bot for Binance USDT-M perpetual TESTNET.

- streams 5m klines over websocket, evaluates the champion strategy from config.yaml on each closed bar
- enters with a LIMIT order at the close (post-only), attaches a reduce-only STOP_MARKET, cancels unfilled
  entries after `entry_timeout_s`
- logs every decision with its reason to decisions.jsonl; restarts itself after any crash (see deploy.md)
- Sentinel: halts for the day at -daily_halt_pct, after max_consecutive_losses, on a stale feed (> stale_s)
  or a fill further than max_fill_dev_pct from plan; halt = cancel all, close all, stop trading, log HALT
Keys come from the environment only (BINANCE_KEY / BINANCE_SECRET, trade-only, withdrawals off). Live
endpoints are refused unless config has testnet: false AND the environment has LIVE_TRADING=I_SAID_GO_LIVE.
"""
import asyncio
import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.parse
from collections import deque
from datetime import datetime, timezone

import requests
import websockets
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import pandas as pd  # noqa: E402
import strategies as st  # noqa: E402

TESTNET = ("https://testnet.binancefuture.com", "wss://stream.binancefuture.com/ws")  # chart tf comes from config (1h/4h)
LIVE = ("https://fapi.binance.com", "wss://fstream.binance.com/ws")


def log(path, **kv):
    kv["ts"] = datetime.now(timezone.utc).isoformat()
    with open(path, "a") as fh:
        fh.write(json.dumps(kv, default=str) + "\n")
    print(json.dumps(kv, default=str), flush=True)


class Exchange:
    def __init__(self, cfg):
        self.testnet = cfg.get("testnet", True)
        if not self.testnet and os.environ.get("LIVE_TRADING") != "I_SAID_GO_LIVE":
            raise SystemExit("live trading refused: config testnet=false but LIVE_TRADING is not set")
        self.rest, self.ws = TESTNET if self.testnet else LIVE
        self.key = os.environ.get("BINANCE_KEY", ""); self.secret = os.environ.get("BINANCE_SECRET", "")
        self.dry = cfg.get("dry_run", True) or not self.key
        self.s = requests.Session(); self.s.headers["X-MBX-APIKEY"] = self.key

    def _signed(self, method, path, **params):
        params["timestamp"] = int(time.time() * 1000); params["recvWindow"] = 5000
        q = urllib.parse.urlencode(params)
        sig = hmac.new(self.secret.encode(), q.encode(), hashlib.sha256).hexdigest()
        r = self.s.request(method, f"{self.rest}{path}?{q}&signature={sig}", timeout=10)
        if r.status_code >= 400:
            raise RuntimeError(f"{path} {r.status_code} {r.text[:200]}")
        return r.json()

    def public(self, path, **params):
        r = self.s.get(f"{self.rest}{path}", params=params, timeout=10); r.raise_for_status(); return r.json()

    def filters(self, symbol):
        info = self.public("/fapi/v1/exchangeInfo")
        s = next(x for x in info["symbols"] if x["symbol"] == symbol)
        f = {x["filterType"]: x for x in s["filters"]}
        return dict(tick=float(f["PRICE_FILTER"]["tickSize"]), step=float(f["LOT_SIZE"]["stepSize"]),
                    min_qty=float(f["LOT_SIZE"]["minQty"]), min_notional=float(f.get("MIN_NOTIONAL", {}).get("notional", 5)))

    def balance(self):
        if self.dry:
            return None
        for a in self._signed("GET", "/fapi/v2/balance"):
            if a["asset"] == "USDT":
                return float(a["availableBalance"])

    def place_entry(self, symbol, side, qty, price, stop_price):
        if self.dry:
            return {"orderId": "dry", "stopOrderId": "dry"}
        o = self._signed("POST", "/fapi/v1/order", symbol=symbol, side=side, type="LIMIT", timeInForce="GTX",
                         quantity=qty, price=price)
        stop = self._signed("POST", "/fapi/v1/order", symbol=symbol, side="SELL" if side == "BUY" else "BUY",
                            type="STOP_MARKET", stopPrice=stop_price, closePosition="true", workingType="MARK_PRICE")
        return {"orderId": o["orderId"], "stopOrderId": stop["orderId"]}

    def order_status(self, symbol, order_id):
        if self.dry:
            return {"status": "FILLED", "avgPrice": None}
        return self._signed("GET", "/fapi/v1/order", symbol=symbol, orderId=order_id)

    def cancel_all(self, symbol):
        if not self.dry:
            self._signed("DELETE", "/fapi/v1/allOpenOrders", symbol=symbol)

    def close_position(self, symbol):
        if self.dry:
            return
        for p in self._signed("GET", "/fapi/v2/positionRisk", symbol=symbol):
            amt = float(p["positionAmt"])
            if amt != 0:
                self._signed("POST", "/fapi/v1/order", symbol=symbol, side="SELL" if amt > 0 else "BUY",
                             type="MARKET", quantity=abs(amt), reduceOnly="true")

    def position(self, symbol):
        if self.dry:
            return 0.0, 0.0
        p = self._signed("GET", "/fapi/v2/positionRisk", symbol=symbol)[0]
        return float(p["positionAmt"]), float(p["entryPrice"])


class Sentinel:
    def __init__(self, cfg, logpath):
        self.cfg = cfg["sentinel"]; self.log = logpath
        self.day = None; self.day_start_equity = None; self.losses = 0; self.halted = False; self.last_tick = time.time()

    def new_day(self, equity):
        d = datetime.now(timezone.utc).date()
        if d != self.day:
            self.day, self.day_start_equity, self.losses, self.halted = d, equity, 0, False

    def check(self, equity, reason_prefix=""):
        if self.halted:
            return True
        if self.day_start_equity and equity <= self.day_start_equity * (1 - self.cfg["daily_halt_pct"] / 100):
            return self.halt(f"{reason_prefix}daily loss {100 * (1 - equity / self.day_start_equity):.2f}%")
        if self.losses >= self.cfg["max_consecutive_losses"]:
            return self.halt(f"{reason_prefix}{self.losses} consecutive losses")
        if time.time() - self.last_tick > self.cfg["stale_s"]:
            return self.halt(f"{reason_prefix}stale feed {time.time() - self.last_tick:.0f}s")
        return False

    def fill_ok(self, planned, actual):
        dev = abs(actual - planned) / planned * 100
        if dev > self.cfg["max_fill_dev_pct"]:
            self.halt(f"fill {dev:.2f}% off plan ({actual} vs {planned})"); return False
        return True

    def halt(self, why):
        self.halted = True; log(self.log, event="HALT", why=why); return True


def size(equity, risk_pct, stop_dist, price, max_lev, step, min_qty, min_notional):
    q = equity * risk_pct / 100 / stop_dist
    q = min(q, equity * max_lev / price)
    decimals = max(0, -int(round(math.log10(step))))
    q = math.floor(q / step + 1e-9) * step
    q = round(q, decimals)
    if q < min_qty or q * price < min_notional:
        return 0.0
    return q


async def run(cfg_path):
    cfg = yaml.safe_load(open(cfg_path))
    logpath = cfg.get("log", "decisions.jsonl")
    ex = Exchange(cfg); sym = cfg["symbol"]; tf = cfg.get("tf", "5m")
    strat = getattr(st, cfg["strategy"]); params = cfg.get("params", {})
    sentinel = Sentinel(cfg, logpath)
    filt = ex.filters(sym)
    bars = deque(maxlen=cfg.get("history_bars", 3000))
    # seed history from REST klines so indicators are warm
    for k in ex.public("/fapi/v1/klines", symbol=sym, interval=tf, limit=1500):
        bars.append(dict(time=pd.Timestamp(k[0], unit="ms", tz="UTC"), open=float(k[1]), high=float(k[2]), low=float(k[3]), close=float(k[4]), volume=float(k[5])))
    log(logpath, event="START", symbol=sym, tf=tf, strategy=cfg["strategy"], params=params, dry_run=ex.dry, testnet=ex.testnet, seeded=len(bars))
    open_order = None
    async for ws in websockets.connect(f"{ex.ws}/{sym.lower()}@kline_{tf}", ping_interval=20):
        try:
            async for raw in ws:
                sentinel.last_tick = time.time()
                k = json.loads(raw)["k"]
                if not k["x"]:
                    continue  # only closed bars
                bars.append(dict(time=pd.Timestamp(k["t"], unit="ms", tz="UTC"), open=float(k["o"]), high=float(k["h"]), low=float(k["l"]), close=float(k["c"]), volume=float(k["v"])))
                df = pd.DataFrame(list(bars)).set_index("time")
                equity = ex.balance() or cfg["paper_equity"]
                sentinel.new_day(equity)
                if sentinel.check(equity):
                    ex.cancel_all(sym); ex.close_position(sym); continue
                sig = strat(df, **params).iloc[-1]
                target, stop_dist = int(sig.target), float(sig.stop)
                amt, entry = ex.position(sym)
                have = 1 if amt > 0 else -1 if amt < 0 else 0
                price = df.close.iloc[-1]
                if open_order and time.time() - open_order["t"] > cfg.get("entry_timeout_s", 240):
                    ex.cancel_all(sym); log(logpath, event="CANCEL_STALE_ENTRY", order=open_order); open_order = None
                if target == have:
                    log(logpath, event="HOLD", target=target, price=price); continue
                if have != 0 and target != have:
                    ex.cancel_all(sym); ex.close_position(sym)
                    log(logpath, event="CLOSE", side=have, price=price, reason="signal flipped" if target else "signal flat")
                    pnl_sign = (price - entry) * have
                    sentinel.losses = sentinel.losses + 1 if pnl_sign < 0 else 0
                if target != 0 and stop_dist == stop_dist and stop_dist > 0:
                    q = size(equity, cfg["risk_pct"], stop_dist, price, cfg["max_leverage"], filt["step"], filt["min_qty"], filt["min_notional"])
                    if q == 0:
                        log(logpath, event="SKIP", reason="size below exchange minimum", price=price, stop=stop_dist); continue
                    side = "BUY" if target > 0 else "SELL"
                    px = round(price / filt["tick"]) * filt["tick"]
                    sp = round((price - target * stop_dist) / filt["tick"]) * filt["tick"]
                    o = ex.place_entry(sym, side, q, f"{px:.8f}".rstrip("0").rstrip("."), f"{sp:.8f}".rstrip("0").rstrip("."))
                    open_order = dict(t=time.time(), **o, planned=px)
                    log(logpath, event="ENTRY", side=side, qty=q, price=px, stop=sp, risk_usd=q * stop_dist, reason=f"{cfg['strategy']} target={target}", order=o)
        except websockets.ConnectionClosed:
            log(logpath, event="WS_RECONNECT"); continue


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "config.yaml")))
