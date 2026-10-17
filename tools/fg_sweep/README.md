# FlashGold v5: exits per timeframe (automated walk-forward)

`sweep.py` answers "which exits work on which chart timeframe, after costs?"
from one TradingView export, and can be re-run on every new export.

```
python -I tools/fg_sweep/sweep.py CRYPTO_BTCUSD_5.csv --out sweep_report.md
```

For each chart timeframe built from the export (a 5m export gives 5m, 15m,
30m, 1H and 2H; the export's candles are the intrabar path):

1. **In-sample** (first 60% after a 5-day warm-up): runs 112 settings
   (stop 0.1-3 ATR x target 1-5R x Fixed / Partial + runner x burst 0.5 / 1),
   worst-case fills, with costs.
2. **Choose** from a plateau: the setting whose neighbours (next stop, next
   target) are also good, among settings with >= 30 trades and both
   in-sample halves positive. Not the single best cell.
3. **Out-of-sample** (the last 40%, never used to choose): runs only the
   chosen setting, under all four conditions of `docs/rules/validation.md`.
   *holds* = worst case, with costs, positive in both halves with >= 20 trades.

Check the answer is stable before believing it: re-run with
`--is-frac 0.5` and `--is-frac 0.7` (other splits) and with your real fee
(`--comm-pct`). A setting that holds in one split only is luck.

Options: `--tfs` (multiples of the export's timeframe), `--qty`, `--comm-pct`,
`--slip-ticks`, `--tick`, `--min-trades`, `--warmup-days`, `--jobs`.
Engine: `tools/fgf_ab/fg5.py`. Filter off, default signal. About 30 s on 4
cores for a 5-month 5m export.
