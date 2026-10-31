# master

## XPW Shape Map v0.6 Strategy — BTC trailing / PF / DD calibration

File: `xpw_shape_map_v0.6_strategy.pine`. Entry: Turn ▲/▼, Predict (stop at cross price), Reverse, cross-fail exit (the defaults).
Data: BYBIT + OKX BTCUSDT exports in `calibration/data` (1m, 5m ×2, 15m, 60m; 840–1150 bars each).
The Python replica in `calibration/sim.py` reproduces the TradingView Fast/Slow lines and every blue-dot cross price exactly.

### Calibrated exits (`S2. Exits` → "BTC auto by timeframe", the default)

| TF   | SL     | Trail activation | Trail distance | Pine pts (0.1 tick) SL / act / dist |
|------|--------|------------------|----------------|-------------------------------------|
| 1m   | $150   | $0               | $25            | 1500 / 0 / 250                      |
| 5m   | $150   | $100             | $25            | 1500 / 1000 / 250                   |
| 15m  | $1500  | $25              | $25            | 15000 / 250 / 250                   |
| 60m+ | $2500  | $200             | $25            | 25000 / 2000 / 250                  |

TP: $5000 (50000 pts) on every timeframe. In practice it never fills; trades end on the trail, a reversal or a failed cross.

### Results per 1 BTC (results scale with quantity). PF is shown as OHLC fill model / conservative fill model

| TF        | Old default (SL $500, act $150, dist $10) | Calibrated, no fees           | Calibrated, 0.055 %/side fees |
|-----------|-------------------------------------------|-------------------------------|-------------------------------|
| 1m BYBIT  | PF 3.59 / 3.18, DD $109                   | PF 6.41 / 7.07, DD $57        | PF 0.11 / 0.13 (loses)        |
| 5m BYBIT  | PF 1.15 / 0.67, DD $632–1333              | PF 1.42 / 1.20, DD $312–350   | PF 0.11 / 0.07 (loses)        |
| 5m OKX    | PF 0.86 / 0.47, DD $628–1804              | PF 1.15 / 0.93, DD $315–354   | PF 0.08 / 0.05 (loses)        |
| 15m BYBIT | PF 1.98 / 1.42, DD $992–2754              | PF 4.08 / 2.43, DD $400–554   | PF 0.72 / 0.76 (loses)        |
| 60m OKX   | PF 2.02 / 1.64, DD $1126–1651             | PF 3.06 / 2.54, DD $1309–1316 | PF 1.35 / 1.42, DD $2124–2470 |

### What the calibration found

* **Tight trails ($10) are a backtest illusion.** With OHLC data the emulator assumes price runs entry → high → low, so a $10 trail banks almost the whole bar. Without fees the "best" 60m setting showed PF 348. Under a conservative fill model it drops to PF 1.6. BTC moves ~$12 inside a normal minute, so the grid only allows trail distances of $25 or more. A setting is only kept if it holds up under both fill models. `use_bar_magnifier = true` is now set (Premium plan) so TradingView's own report gets closer to real fills.
* **Fees decide it.** A round trip costs ~$95 per BTC at 0.055 % per side. That is more than the average gross trade on 1m ($37), 5m (~$5) and 15m ($67). Only 60m stays profitable after fees. Commission is now 0.055 % in the `strategy()` defaults. Set it to 0 in Properties to see the gross numbers.
* **Small samples.** In walk-forward tests (pick on the first 60 %, test on the last 40 %) only 1m held up, and only without fees. 5m, 15m and 60m varied a lot. Treat the table as a starting point and re-run on longer exports.
* **Position size.** The default of 10 contracts means 10 BTC (~$860k notional). The 60m DD of ~$2.5k per BTC would be ~$25k on a $10k account. For roughly 15–20 % max DD on $10k, use 0.6–0.8 BTC on 60m (`Quantity step` 0.01).

### Re-running

```
cd calibration
python3 sim.py            # replica check + old-default stats
python3 grid2.py 0        # calibration without fees
python3 grid2.py 0.00055  # calibration with taker fees
python3 mag.py            # OHLC vs conservative vs 1m-magnifier on the overlap window
```
Add new CSV exports (with the Fast / Slow / Predicted cross price columns) to `calibration/data` and to `FILES` in `sim.py`.
