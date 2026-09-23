# XPW Breakout (BTCUSD calibration)

TradingView Pine v6 rebuild of the "BTC Trading Robot" MT5 EA, recalibrated
for BTCUSD with an explicit cost model, an extended entry module and tick
execution.

| Path | What it is |
|---|---|
| `pine/XPW_Breakout_v2.10_BTCUSD.pine` | The strategy. Load it in the Pine editor on a BTCUSD chart. |
| `pine/XPW_Breakout_v2.01_XAUUSD.pine` | The previous (gold) version, kept for diffing. |
| `CALIBRATION.md` | Cost presets, per-timeframe geometry, sweep results, what changed and why. |
| `calibration/xpw_backtest.py` | Python replica of the TradingView broker emulator used for the sweep. |
| `calibration/data/BTCUSD_*.csv` | The five TradingView exports (1m, 15m, 30m, 60m, 240m) the sweep ran on. |
| `calibration/results/` | Sweep CSVs, `summary.json`, `SWEEP_NOTES.md`, `parity.json`. |

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
   inputs.

## Reproduce the sweep

```bash
pip install pandas numpy
python3 calibration/xpw_backtest.py sweep      # writes calibration/results/
python3 calibration/xpw_backtest.py parity     # engine vs the TradingView Trail column
python3 calibration/xpw_backtest.py run --tf 60 --sl-mode atr --sl 1.5 --tp-r 2 --cost cfd_std
```
