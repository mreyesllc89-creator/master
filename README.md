# XPW Breakout (BTCUSD calibration)

TradingView Pine v6 rebuild of the "BTC Trading Robot" MT5 EA, recalibrated
for BTCUSD with an explicit cost model, an extended entry module and tick
execution.

| Path | What it is |
|---|---|
| `pine/XPW_Breakout_v2.10_BTCUSD.pine` | The strategy. Load it in the Pine editor on a BTCUSD chart. |
| `pine/XPW_Breakout_v2.10_XAUUSD.pine` | The same strategy with gold defaults (per-ounce costs, ounce sizing, SL 1.5 ATR / TP 2.5R from the gold sweep). See `CALIBRATION.md` section 13. |
| `pine/XPW_Breakout_v2.01_XAUUSD.pine` | The previous (gold) version, kept for diffing. |
| `CALIBRATION.md` | Cost presets, per-timeframe geometry, sweep results, what changed and why. |
| `docs/XPW_Settings_by_Timeframe.pdf` | Every input of both builds, one sheet per timeframe, with the numbers behind each choice. |
| `calibration/xpw_backtest.py` | Python replica of the TradingView broker emulator used for the sweep. |
| `calibration/data/BTCUSD_*.csv` | The five TradingView exports (1m, 15m, 30m, 60m, 240m) the BTC sweep ran on. |
| `calibration/data/XAUUSD_*.csv` | The six OANDA gold exports (5m to 240m) the gold sweep ran on. |
| `calibration/data/BTCUSDT_*.csv` | MEXC 5m, 30s and 15s BTC exports; see `CALIBRATION.md` section 14 (5m and below: do not). |
| `calibration/results/` | Sweep CSVs, `summary.json`, `SWEEP_NOTES.md`, `parity.json`; `latch/` for the v2.10 arming sweep, `xau/` for gold, `btc5/` for BTC 5m and sub-minute, `don_btc/` and `don_xau/` for the Donchian / Follow sweep (`CALIBRATION.md` section 15). |

## Quick start

1. Open the chart symbol you will actually trade (a broker feed such as
   `VTMARKETS:BTCUSD`, or an exchange symbol). `CRYPTO:BTCUSD` is an index
   with no real costs; fine for geometry, not for P&L.
2. Paste `pine/XPW_Breakout_v2.10_BTCUSD.pine` into the Pine editor and add
   it to the chart.
3. Strategy Tester > Properties > Defaults > **Reset settings**, so the
   header's BTC commission and slippage replace whatever the chart stored
   for gold. Turn Bar Magnifier on if your plan has it.
4. Set the cost inputs (group "2. Costs") to your venue preset from
   `CALIBRATION.md`, and check the on-chart table: the "Header slippage
   should be" row must equal the Properties slippage.
5. Pick the timeframe block in `CALIBRATION.md` and copy its geometry
   inputs, or use `docs/XPW_Settings_by_Timeframe.pdf`, which lists every
   input per timeframe for both builds. Pivot levels with `LvlMove` =
   Follow are the defaults; section 15 lists the timeframes where a
   rolling Donchian level did better.

## Reproduce the sweep

```bash
pip install pandas numpy
python3 calibration/xpw_backtest.py sweep      # writes calibration/results/
python3 calibration/xpw_backtest.py parity     # engine vs the TradingView Trail column
python3 calibration/xpw_backtest.py run --tf 60 --sl-mode atr --sl 1.5 --tp-r 2 --cost cfd_std
python3 calibration/xpw_backtest.py sweep --tfs 15,30,60,240 --arm latch,hold --levels pivot,don5,don10,don20,don50 --costs none,vt_btc --out don_btc   # writes calibration/results/don_btc/
```
