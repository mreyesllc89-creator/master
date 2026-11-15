# Tokio732_VolLab — XAUUSD and BTCUSD edition

`Tokio732_VolLab.mq5` is the author's engine 3614 source with one change: the symbol check in
`CheckAccount732` now accepts symbols that start with `XAUUSD` **or** `BTCUSD` (any broker suffix,
e.g. `BTCUSDm`). The trading logic is untouched (`git log -p -- Tokio732_VolLab.mq5` shows the
four changed lines: that check and three description strings).

It has not been compiled here: MetaEditor does not run in this environment. Compile it in
MetaEditor before use.

Why nothing else had to change for bitcoin: price distances, trailing levels and the volatility
reference are inputs, and the presets carry bitcoin values for them; the USD value of one lot per
1 USD price move is read from the symbol (`CalibrateUnits732`: contract size, 1 for Exness
BTCUSD), and lot rounding uses the symbol's minimum and step.

## Use

1. Copy `Tokio732_VolLab.mq5` to `MQL5\Experts`, compile, and copy the two news files from the
   original archive (`news_usd_high_2025_2026.bin`, `news_usd_high_2022_2026_LAB.bin`) to
   `MQL5\Files` (they are needed only if a news option is switched on).
2. Copy `../presets/TOKIO_VolLab_BTCUSD_BEST_H6.set` to `MQL5\Profiles\Tester`.
3. Strategy Tester: symbol `BTCUSDm` (or your broker's BTCUSD), M5 chart, every tick based on
   real ticks, USD account, hedging, 1,000 USD. Load the .set in the Inputs tab.

Still applies: the EA refuses to start outside the Strategy Tester (`OnInit`), and live it would
also require an Exness account.

## Check before trusting a bitcoin run

* `732_UNITS ... USD_price_value_per_lot=` in the Journal should print `1` for a 1 BTC contract.
  If your broker's contract differs, scale `LotsWithTrend` / `LotsAgainstTrend` by 1 / contract.
* `VolATRRef=81.22` is gold's 4.74 times 17.1, the bitcoin/gold ratio of median H1 true range on
  the July–August 2026 Octa data (257 USD vs 15 USD). With a bitcoin H1 ATR(14) near 257 USD the
  volatility factor is about 3.2, and the preset opens baskets only when it is at least 3
  (`MinVolFactor`). If your broker's bitcoin H1 ATR is far from that level, the factor, every
  distance and the lot size scale with it.
* `DeviationPoints=1000` is 10 USD on a 2-digit BTCUSD quote. Raise it if you see requotes.
* Bitcoin trades on weekends; the simulation included weekend data.
