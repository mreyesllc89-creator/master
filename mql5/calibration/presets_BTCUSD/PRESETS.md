# Best 10 EA presets — BTCUSD, point 0.01, 1798 bars 2026-09-04T00:30:00-04:00 .. 2026-10-11T11:00:00-04:00
Risk 1.0% per trade, $10000 start, spread 20.0 per unit. 'half 1 / half 2' = net % on each half of the data.

| # | mode | dir | opp | SL $ | act $ | dis $ | pred buf | CONT big/pinch/after | trades | win | PF | net | maxDD | half 1 / half 2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | turn_predict | long | reverse | 300 | 100 | 10 | 200 | 1.0/1.0/6 | 72 | 81% | 2.62 | 26.9% | 1.8% | 11.7% / 15.3% | `01_BTCUSD_turn_predict_long_SL300.set`
| 2 | turn_predict | long | reverse | 300 | 800 | 10 | 200 | 1.0/1.0/6 | 48 | 40% | 2.03 | 32.8% | 7.3% | 3.2% / 29.7% | `02_BTCUSD_turn_predict_long_SL300.set`
| 3 | turn_predict | long | reverse | 300 | 200 | 10 | 200 | 1.0/1.0/6 | 63 | 70% | 2.14 | 25.1% | 2.4% | 8.8% / 16.3% | `03_BTCUSD_turn_predict_long_SL300.set`
| 4 | cont_stop | both | reverse | 300 | 100 | 10 | 0 | 0.8/1.5/6 | 97 | 69% | 1.81 | 26.5% | 5.5% | 15.2% / 11.3% | `04_BTCUSD_cont_stop_both_SL300.set`
| 5 | cont | both | reverse | 500 | 100 | 10 | 0 | 0.8/1.5/4 | 107 | 87% | 2.66 | 21.8% | 2.4% | 10.1% / 11.8% | `05_BTCUSD_cont_both_SL500.set`
| 6 | cont | both | reverse | 500 | 100 | 10 | 0 | 0.8/1.5/6 | 112 | 86% | 2.37 | 21.2% | 2.1% | 10.0% / 11.3% | `06_BTCUSD_cont_both_SL500.set`
| 7 | cont_stop | both | reverse | 300 | 100 | 10 | 0 | 0.8/1.5/4 | 92 | 70% | 1.88 | 27.2% | 6.4% | 17.4% / 9.9% | `07_BTCUSD_cont_stop_both_SL300.set`
| 8 | cont | both | close | 500 | 100 | 10 | 0 | 0.8/1.5/4 | 103 | 86% | 2.61 | 21.1% | 2.4% | 9.9% / 11.2% | `08_BTCUSD_cont_both_SL500.set`
| 9 | cont_stop | long | reverse | 300 | 800 | 10 | 0 | 0.8/1.5/4 | 39 | 38% | 1.93 | 25.8% | 6.2% | 8.4% / 17.5% | `09_BTCUSD_cont_stop_long_SL300.set`
| 10 | square | long | reverse | 300 | 100 | 10 | 0 | 1.0/1.0/6 | 71 | 75% | 2.12 | 20.6% | 3.9% | 10.6% / 9.9% | `10_BTCUSD_square_long_SL300.set`
