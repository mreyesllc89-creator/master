# BTCUSD calibration for `candle_entry_labels_strategy.pine`

Python replica of the strategy's order logic (decide at candle close, fill at the
next open, ATR stop as `loss` ticks from the fill, TradingView's O→H→L→C / O→L→H→C
intrabar path, 0.1% commission per side, 100% of equity per trade).

    pip install pandas numpy numba pyarrow
    python prep.py          # Bitstamp BTC/USD 1-minute data → 15m/1h/4h/1D
    python grid.py 4h       # 9,248 settings, train 2018-2022 / test 2023-2026 → grid_4h.csv

Settings were chosen on 2018-2022 only, then checked on 2023 – Oct 2026.

Defaults (EMA 21/55 close cross, EMA 200 trend filter, long only, stop 2×ATR(14)):

| TF | Period | Return | Max DD | Trades | Win | PF | Buy & hold |
|----|--------|-------:|-------:|-------:|----:|---:|-----------:|
| 4H | 2018-2022 (train) | +740% | 38% | 50 | 34% | 2.30 | +23% |
| 4H | 2023-2026 (test)  | +172% | 21% | 40 | 30% | 2.40 | +413% |
| 4H | Both directions, test | +73% | 40% | 83 | 25% | 1.37 | |
| 1D | 2023-2026 (test)  | +80% | 36% | 9 | 22% | 1.93 | |
| 1H | 2023-2026 (test)  | −53% | 65% | 186 | 19% | 0.74 | |

Neighbouring 4H long-only settings (EMA 20/50 to 50/100, stop 1.5–4 ATR) all
have test PF ≈ 1.6–3.4, so the defaults sit in a stable region. 1H does not
survive out of sample; the open-based EMA reading is less stable than the close
reading. TradingView's numbers will differ a little (feed, tick size, slippage).
