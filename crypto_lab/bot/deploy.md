# Deploying the bot on the $6 server (testnet)

```bash
sudo apt-get install -y python3-venv git
git clone https://github.com/mreyesllc89-creator/master.git && cd master/crypto_lab/bot
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q tests          # must be all green
```

Create `/etc/crypto-bot.env` (root only, `chmod 600`) with the TESTNET keys from
https://testnet.binancefuture.com (trade-only; no withdrawal permission exists on testnet):

```
BINANCE_KEY=...
BINANCE_SECRET=...
```

Then set `dry_run: false` in `config.yaml` and install the service so it restarts after any crash:

```ini
# /etc/systemd/system/crypto-bot.service
[Unit]
Description=night-lab crypto bot (testnet)
After=network-online.target
[Service]
WorkingDirectory=/root/master/crypto_lab/bot
EnvironmentFile=/etc/crypto-bot.env
ExecStart=/root/master/crypto_lab/bot/.venv/bin/python bot.py config.yaml
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now crypto-bot
journalctl -u crypto-bot -f          # every decision and its reason; also in decisions.jsonl
```

New champion = `git pull` (only `config.yaml` changes) and `sudo systemctl restart crypto-bot`.
A cron line `*/10 * * * * cd /root/master && git pull -q && systemctl restart crypto-bot` keeps it in sync
with what the Engineer role commits at 04:00 NY. Live trading is refused unless `testnet: false` AND
`LIVE_TRADING=I_SAID_GO_LIVE` is in the env file: do not set it until the owner says "go live".

## Sending the decision log back to the lab
The 07:30 brief reads `crypto_lab/bot/logs/*.jsonl` from the repo. On the server, push the log hourly:

```bash
# crontab -e
5 * * * * cd /root/master && mkdir -p crypto_lab/bot/logs && cp crypto_lab/bot/decisions.jsonl crypto_lab/bot/logs/$(hostname).jsonl && git add crypto_lab/bot/logs && git commit -qm "bot log $(date -u +\%FT\%H)" && git push -q origin claude/intelligent-turing-7uhnvg
```
The log never contains keys (the bot logs decisions and order ids only).
