"""TradingView -> MT5 bridge.

A self-hosted webhook receiver that runs on the same Windows machine as the
MT5 terminal and places orders through MetaQuotes' official MetaTrader5
Python package. No third-party relay sees your signals or account.

Each alert carries the strategy's *target* position (long / short / flat)
rather than a buy or sell instruction. The bridge makes MT5 match it, so a
repeated alert never doubles a position, and every exit
the TradingView strategy takes (END label, opposite ENTER, trailing TP, SL)
is mirrored without extra alert logic.

Standard library only, apart from MetaTrader5 (not needed with "dry_run").

    python tv_mt5_bridge.py               # uses config.json next to this file
    python tv_mt5_bridge.py my_conf.json
"""

import calendar
import hmac
import json
import logging
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_BODY = 4096
log = logging.getLogger("bridge")


# ---------------------------------------------------------------- config ----
def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg.setdefault("secret", "")
    if cfg["secret"].startswith("CHANGE_ME"):
        sys.exit("config: set 'secret' to a long random string, or \"\" for none while testing")
    cfg.setdefault("listen_host", "127.0.0.1")
    cfg.setdefault("listen_port", 8080)
    cfg.setdefault("path", "/hook")
    cfg.setdefault("allowed_ips", [])
    cfg.setdefault("dry_run", False)
    cfg.setdefault("magic", 240424)
    cfg.setdefault("deviation_points", 20)
    cfg.setdefault("max_alert_age_sec", 0)
    cfg.setdefault("symbols", {})
    return cfg


# ------------------------------------------------------------------- MT5 ----
class Broker:
    """All MT5 calls go through one lock: the MetaTrader5 package is not
    thread-safe and talks to a single terminal."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.mt5 = None
        if cfg["dry_run"]:
            self.dry_pos = {}
            log.warning("DRY RUN: no orders will be sent to MT5")
            return
        import MetaTrader5 as mt5  # Windows only

        self.mt5 = mt5
        self._connect()

    def _connect(self):
        mt5, c = self.mt5, self.cfg.get("mt5", {})
        kw = {k: c[k] for k in ("path", "login", "password", "server") if c.get(k)}
        if not mt5.initialize(**kw):
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        info = mt5.account_info()
        terminal = mt5.terminal_info()
        if info is None or terminal is None or not terminal.connected:
            raise RuntimeError(f"MT5 account unavailable or disconnected: {mt5.last_error()}")
        log.info("MT5 connected: account %s on %s", info.login, info.server)

    def _ensure(self):
        info = self.mt5.terminal_info()
        if info is None or not info.connected:
            log.warning("MT5 connection lost, reconnecting")
            self.mt5.shutdown()
            self._connect()

    def sync(self, symbol, target, lots, sl_dist):
        """Make the bridge's position on `symbol` equal `target`."""
        with self.lock:
            if self.mt5 is None:
                return self._dry_sync(symbol, target, lots)
            self._ensure()
            mt5 = self.mt5
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"symbol {symbol} not available: {mt5.last_error()}")
            positions = mt5.positions_get(symbol=symbol)
            if positions is None:
                raise RuntimeError(f"positions_get failed: {mt5.last_error()}")
            positions = [
                p for p in positions
                if p.magic == self.cfg["magic"]
            ]
            want = {"long": mt5.POSITION_TYPE_BUY, "short": mt5.POSITION_TYPE_SELL}.get(target)
            actions = []
            for p in positions:
                if p.type != want:
                    self._close(p)
                    actions.append(f"closed #{p.ticket}")
            if want is not None and not any(p.type == want for p in positions):
                ticket = self._open(symbol, want, lots, sl_dist)
                actions.append(f"opened {target} {lots} #{ticket}")
            return actions or ["already in sync"]

    def _filling(self, symbol):
        mt5 = self.mt5
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol_info failed: {mt5.last_error()}")
        if info.trade_exemode in (mt5.SYMBOL_TRADE_EXECUTION_REQUEST,
                                 mt5.SYMBOL_TRADE_EXECUTION_INSTANT):
            return mt5.ORDER_FILLING_FOK
        mode = info.filling_mode
        if mode & 1:  # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        if mode & 2:  # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        if info.trade_exemode == mt5.SYMBOL_TRADE_EXECUTION_MARKET:
            raise RuntimeError("market execution requires FOK or IOC filling")
        return mt5.ORDER_FILLING_RETURN

    def _send(self, req):
        mt5 = self.mt5
        req.update(
            action=mt5.TRADE_ACTION_DEAL,
            deviation=self.cfg["deviation_points"],
            magic=self.cfg["magic"],
            type_time=mt5.ORDER_TIME_GTC,
            type_filling=self._filling(req["symbol"]),
        )
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            err = res.comment if res else mt5.last_error()
            raise RuntimeError(f"order rejected ({getattr(res, 'retcode', '?')}): {err}")
        return res

    def _tick(self, symbol):
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask <= 0 or tick.bid <= 0:
            raise RuntimeError(f"no valid quote for {symbol}: {self.mt5.last_error()}")
        return tick

    def _open(self, symbol, ptype, lots, sl_dist):
        mt5 = self.mt5
        tick = self._tick(symbol)
        buy = ptype == mt5.POSITION_TYPE_BUY
        price = tick.ask if buy else tick.bid
        req = dict(
            symbol=symbol,
            volume=float(lots),
            type=mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL,
            price=price,
            comment="tv-bridge",
        )
        if sl_dist:
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"symbol_info failed: {mt5.last_error()}")
            req["sl"] = round(price - sl_dist if buy else price + sl_dist, info.digits)
        return self._send(req).order

    def _close(self, p):
        mt5 = self.mt5
        tick = self._tick(p.symbol)
        buy = p.type == mt5.POSITION_TYPE_BUY
        self._send(dict(
            symbol=p.symbol,
            volume=p.volume,
            type=mt5.ORDER_TYPE_SELL if buy else mt5.ORDER_TYPE_BUY,
            position=p.ticket,
            price=tick.bid if buy else tick.ask,
            comment="tv-bridge close",
        ))

    def _dry_sync(self, symbol, target, lots):
        cur = self.dry_pos.get(symbol, "flat")
        if cur == target:
            return ["already in sync (dry run)"]
        acts = [f"closed {cur} (dry run)"] if cur != "flat" else []
        if target != "flat":
            acts.append(f"opened {target} {lots} (dry run)")
        self.dry_pos[symbol] = target
        return acts


# --------------------------------------------------------------- handler ----
def parse_alert(body, cfg):
    """Validate an alert body. Returns (broker_symbol, target, lots, sl_dist)."""
    msg = json.loads(body)
    if not isinstance(msg, dict):
        raise ValueError("alert must be a JSON object")
    if cfg["secret"] and not hmac.compare_digest(str(msg.get("secret", "")).encode(), cfg["secret"].encode()):
        raise PermissionError("bad secret")

    ticker = str(msg.get("symbol", "")).split(":")[-1].upper()
    sym_cfg = cfg["symbols"].get(ticker)
    if sym_cfg is None:
        raise ValueError(f"symbol {ticker!r} is not in config 'symbols'")

    target = str(msg.get("position", "")).lower()
    if target not in ("long", "short", "flat"):
        raise ValueError(f"position must be long/short/flat, got {target!r}")

    try:
        lots = float(msg.get("lots", sym_cfg["lots"]))
    except (TypeError, ValueError):
        raise ValueError("lots must be a number") from None
    if not 0 < lots <= sym_cfg.get("max_lots", sym_cfg["lots"]):
        raise ValueError(f"lots {lots} outside (0, max_lots]")

    max_age = cfg["max_alert_age_sec"]
    if max_age and msg.get("time"):
        if not isinstance(msg["time"], str):
            raise ValueError("time must be a timestamp string")
        sent = calendar.timegm(time.strptime(msg["time"][:19], "%Y-%m-%dT%H:%M:%S"))
        if time.time() - sent > max_age:
            raise ValueError(f"alert is older than {max_age}s")

    return sym_cfg.get("mt5_symbol", ticker), target, lots, sym_cfg.get("sl_distance")


def make_handler(cfg, broker):
    class Handler(BaseHTTPRequestHandler):
        server_version = "bridge"
        sys_version = ""

        def log_message(self, fmt, *args):  # route http.server noise to our log
            log.debug("%s " + fmt, self.client_address[0], *args)

        def reply(self, code, text):
            data = text.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.reply(404, "not found")

        def do_POST(self):
            # Behind Caddy every request comes from 127.0.0.1; Caddy does the
            # IP filtering there. This list is for running without a proxy.
            ip = self.client_address[0]
            if cfg["allowed_ips"] and ip not in cfg["allowed_ips"]:
                log.warning("rejected %s: ip not allowed", ip)
                return self.reply(403, "forbidden")
            if self.path != cfg["path"]:
                return self.reply(404, "not found")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self.reply(413, "bad length")
            if not 0 < length <= MAX_BODY:
                return self.reply(413, "bad length")
            body = self.rfile.read(length)

            try:
                symbol, target, lots, sl = parse_alert(body, cfg)
            except PermissionError:
                log.warning("rejected %s: bad secret", ip)
                return self.reply(403, "forbidden")
            except (ValueError, KeyError) as e:
                log.warning("rejected %s: %s", ip, e)
                return self.reply(400, str(e))

            t0 = time.perf_counter()
            try:
                actions = broker.sync(symbol, target, lots, sl)
            except Exception as e:
                log.error("%s -> %s FAILED: %s", symbol, target, e)
                return self.reply(500, "order failed")
            ms = (time.perf_counter() - t0) * 1000
            log.info("%s -> %s: %s (%.0f ms)", symbol, target, "; ".join(actions), ms)
            self.reply(200, "ok")

    return Handler


def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else HERE / "config.json"
    cfg = load_config(cfg_path)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(HERE / "bridge.log", encoding="utf-8")],
    )
    if not cfg["secret"]:
        log.warning("NO SECRET SET: any alert that reaches the bridge will be accepted. "
                    "Fine for testing; set 'secret' before trading real money.")
    broker = Broker(cfg)
    srv = ThreadingHTTPServer((cfg["listen_host"], cfg["listen_port"]),
                              make_handler(cfg, broker))
    log.info("listening on http://%s:%s%s", cfg["listen_host"], cfg["listen_port"], cfg["path"])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if broker.mt5:
            broker.mt5.shutdown()


if __name__ == "__main__":
    main()
