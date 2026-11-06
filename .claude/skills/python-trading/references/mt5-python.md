# MetaTrader 5 from Python (`MetaTrader5` package)

Windows only; the package talks to a running MT5 terminal on the same machine
(`pip install MetaTrader5`). On Linux/macOS, either run MT5 under Wine with a Windows
Python, or export data from MT5 and process offline.

## Connect
```python
import MetaTrader5 as mt5
if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
                      login=12345678, password=os.environ["MT5_PASSWORD"], server="Broker-Server"):
    raise SystemExit(f"initialize failed: {mt5.last_error()}")
try:
    ...
finally:
    mt5.shutdown()
```
`path/login/password/server` are optional when the terminal is already open and logged in.
Call `mt5.symbol_select(symbol, True)` before requesting data for a symbol not in Market Watch.

## Candles and ticks
```python
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 5000)   # newest 5000 bars, index 0 = forming bar
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)          # broker server time stamped as if UTC
df = df.set_index("time")[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
```
- `copy_rates_range(symbol, tf, date_from, date_to)` with tz-aware UTC datetimes.
- `copy_ticks_from(symbol, date_from, count, mt5.COPY_TICKS_ALL)` for bid/ask ticks.
- Timeframes: `TIMEFRAME_M1, M5, M15, M30, H1, H4, D1, W1, MN1`.
- Rates `time` is server time, not UTC. Find the offset with
  `mt5.symbol_info_tick(symbol).time` vs `datetime.now(timezone.utc)` and document it.
- The last row is the forming bar; drop it for closed-bar logic.

## Symbol properties
```python
si = mt5.symbol_info("BTCUSD")
si.point, si.digits, si.trade_tick_size, si.trade_tick_value, si.volume_min, si.volume_step, si.volume_max
si.trade_stops_level   # min distance (points) for SL/TP/pending from current price
si.filling_mode        # bitmask: 1 FOK, 2 IOC, 4 RETURN... pick one the broker allows
```

## Orders
```python
req = {
    "action": mt5.TRADE_ACTION_PENDING,              # TRADE_ACTION_DEAL for market
    "symbol": "BTCUSD", "volume": 0.10,
    "type": mt5.ORDER_TYPE_BUY_STOP,                  # ORDER_TYPE_BUY / SELL / SELL_STOP / BUY_LIMIT ...
    "price": round(entry, si.digits), "sl": round(sl, si.digits), "tp": round(tp, si.digits),
    "deviation": 20, "magic": 240501, "comment": "FlashGold BUY",
    "type_time": mt5.ORDER_TIME_GTC,                  # ORDER_TIME_SPECIFIED + "expiration": datetime
    "type_filling": mt5.ORDER_FILLING_RETURN,         # pending orders: RETURN; market: IOC or FOK per broker
}
chk = mt5.order_check(req)
if chk.retcode != 0: raise RuntimeError(f"check failed {chk.retcode} {chk.comment}")
res = mt5.order_send(req)
if res.retcode not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
    raise RuntimeError(f"order_send {res.retcode} {res.comment}")
```
- Modify a position's SL/TP: `action=TRADE_ACTION_SLTP, position=ticket, sl=, tp=`.
- Close a position: opposite `TRADE_ACTION_DEAL` with `position=ticket` and the same volume
  (partial close: smaller volume).
- Delete a pending: `action=TRADE_ACTION_REMOVE, order=ticket`.
- Hedging vs netting account: `mt5.account_info().margin_mode`
  (`ACCOUNT_MARGIN_MODE_RETAIL_HEDGING` = 2). On netting, an opposite deal nets the position.
- Respect `trade_stops_level` and `trade_freeze_level`; price distances must be multiples
  of `trade_tick_size`.

## State
- `mt5.positions_get(symbol=...)`, `mt5.orders_get(...)`, `mt5.history_deals_get(from, to)`.
  Filter by `magic` to see only this strategy's trades.
- `mt5.account_info().equity`, `.balance`, `.margin_free` for sizing.
- Poll on a timer (`time.sleep`) or on new-bar detection: compare the time of
  `copy_rates_from_pos(..., 0, 1)[0]["time"]` with the last seen bar time.

## Robustness
- Wrap each cycle in try/except, log, `mt5.shutdown()` + `mt5.initialize()` on connection
  loss (`mt5.last_error()` returns a tuple code/description).
- Never block on `input()`; run as a service/Task Scheduler job with a log file.
- Dry-run flag that logs the request instead of sending it; test on a demo account
  first.
