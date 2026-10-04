"""Send a fake TradingView alert to the bridge.

    python send_test_alert.py long
    python send_test_alert.py flat --symbol EURUSD --url http://127.0.0.1:8080/hook
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("position", choices=["long", "short", "flat"])
ap.add_argument("--symbol", default="XAUUSD")
ap.add_argument("--url", default="http://127.0.0.1:8080/hook")
ap.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
args = ap.parse_args()

secret = json.loads(Path(args.config).read_text(encoding="utf-8"))["secret"]
body = json.dumps({
    "secret": secret,
    "symbol": args.symbol,
    "position": args.position,
    "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}).encode()
req = urllib.request.Request(args.url, body, {"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
