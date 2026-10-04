# TradingView → MT5 bridge (self-hosted)

```
TradingView alert ──HTTPS──▶ Caddy :443 ──▶ tv_mt5_bridge.py ──▶ MT5 terminal ──▶ broker
                             (TLS + IP filter)  (127.0.0.1:8080)   (same Windows box)
```

- **Cost:** free software. You pay only for a Windows machine that stays on.
  Many brokers give you a free VPS once the account is funded. Otherwise a
  small Windows VPS costs about $5–15/mo, or you can use a home PC that
  stays on.
- **Speed:** there's no third-party relay hop. Orders go straight from the
  webhook into the terminal through MetaQuotes' own Python API, and the
  bridge itself takes a few milliseconds. Most of the delay is TradingView
  sending the webhook, which is usually under a second to a few seconds.
- **Privacy:** no third-party bridge service sees your signals, your account
  or your login. The webhook travels over HTTPS and needs a secret. Caddy
  drops everything that isn't from TradingView's four published webhook IPs.
  The only outside party is DuckDNS. It just maps your hostname to your IP
  and never sees any traffic.

## How it trades

Each alert sends the strategy's **target position** (`long`, `short` or
`flat`) instead of a "buy" or "sell" order. The bridge then makes MT5 match:

| MT5 has | Alert says | Bridge does |
|---|---|---|
| nothing | long | opens a buy |
| buy | long | nothing (duplicates are harmless) |
| buy | short | closes the buy, opens a sell |
| anything | flat | closes it |

So every exit the XPW strategy makes is copied automatically: END labels,
opposite ENTER, trailing TP and SL. No extra alerts are needed. The bridge
only touches positions that carry its own `magic` number, so your manual
trades and other EAs are left alone.

## Setup (on the Windows machine)

1. **MT5:** log in. Under *Tools → Options → Expert Advisors*, tick
   **Allow algorithmic trading**, and turn on the **Algo Trading** button in
   the toolbar.
2. **Python 3.10+** from python.org (tick "Add to PATH"), then run:
   `pip install -r requirements.txt`
3. **Config:** copy `config.example.json` to `config.json`.
   - Set `secret` to a long random string. One way to get one:
     `python -c "import secrets;print(secrets.token_urlsafe(32))"`
   - Under `symbols`, list each TradingView ticker you trade. Set
     `mt5_symbol` to your broker's exact name for it (e.g. `XAUUSD.m`,
     `GOLD`), along with `lots` and a hard `max_lots` cap.
   - `sl_distance` (price units, `0` = off) places a safety stop at the
     broker. Use it so you stay protected if the PC or the network goes
     down.
   - Leave `dry_run: true` for now.
4. **Hostname:** create a free subdomain at duckdns.org and point it at the
   machine's public IP. Put the name in `Caddyfile`.
5. **Caddy:** download `caddy.exe` from caddyserver.com into this folder.
   Open inbound TCP **80 and 443** in Windows Firewall. On a home PC, also
   forward them on your router. Caddy uses port 80 only to get the free
   certificate.
6. **Run** `start_bridge.bat`. Test from the same machine:
   `python send_test_alert.py long`, then `python send_test_alert.py flat`.
   Each should print `200 ok` and show up in `bridge.log`.
7. **TradingView:** this needs a paid plan for webhooks, and 2FA turned on.
   Add the strategy to the chart and create an alert:
   - Condition: *XPW Orientation TDI v2.4 Strategy* → **Order fills only**
   - Webhook URL: `https://yourname.duckdns.org/hook`
   - Message (paste exactly, with your secret):
     ```json
     {"secret":"YOUR_SECRET","symbol":"{{ticker}}","position":"{{strategy.market_position}}","time":"{{timenow}}"}
     ```
8. Watch `bridge.log` while a few signals come through in dry run. Then set
   `"dry_run": false`, restart, and run it on a **demo account** before
   going live.
9. **Auto-start:** create a Task Scheduler task to run `start_bridge.bat` at
   log on. Set Windows to auto-login so it survives reboots.

## Notes

- **Lot size** comes from `config.json`, not from the strategy's "% of
  equity" setting. An alert may send `"lots": "0.05"` to override it, but it
  can never go above `max_lots`.
- **Trailing TP/SL** is simulated by TradingView on its own price feed. MT5
  closes at market when that alert arrives, so expect small slippage
  compared with the backtest. `sl_distance` is the broker-side backstop.
- **`max_alert_age_sec`** rejects alerts that arrive late, so a delayed
  webhook can't open a trade at a stale price. Keep the Windows clock
  synced.
- **Running without Caddy** works too: set `listen_host` to `0.0.0.0` and
  `listen_port` to `80`, and add TradingView's IPs to `allowed_ips`. Plain
  HTTP sends your secret unencrypted, though, so only use this for a quick
  test.
- **Firewall:** never expose port 8080 itself. Only Caddy should be
  reachable from outside.
