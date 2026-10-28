# Python emulation of the XPW v0.9.2 + FlashGold EA (PF preset)

`xpw_emulator.py` replays the EA's PF-preset logic on an MT5 chart export so you
can see roughly what a tester run looks like without MetaTrader. It is **not** the
MT5 tester: no tick fills, fixed spread, signal on the chart bars (no `SigTF=10`
relay), Turn-mode only, FlashGold filter simplified. Use it for a first look and for
sanity-checking parameter ranges; trust only the MT5 tester for final numbers.

## Export the bars from MT5 (VT Markets)

1. Open the chart: `XAUUSD` on **M5**, or `BTCUSD` on **M15**.
2. Load enough history: Tools > Options > Charts > "Max bars in chart" = Unlimited,
   then press Home on the chart until a year or more is loaded.
3. File > **Save As** (Ctrl+S) > `XAUUSD_M5.csv`. It is tab-separated with the
   `<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> ...` header the script expects.

## Run

```bash
python3 xpw_emulator.py --csv XAUUSD_M5.csv --symbol XAUUSD --trades-csv xau_trades.csv
```

```bash
python3 xpw_emulator.py --csv BTCUSD_M15.csv --symbol BTCUSD --trades-csv btc_trades.csv
```

Options: `--spread <pts>` (your broker's typical spread), `--sl-atr`, `--tp-r`,
`--no-filter` (FlashGold off), `--synthetic XAUUSD|BTCUSD` (random-walk layout demo).

## Demo reports

`demo_report_XAUUSD_synthetic.txt` and `demo_report_BTCUSD_synthetic.txt` were produced
from random-walk bars. They show the report layout only; their numbers carry no
information about the strategy.
