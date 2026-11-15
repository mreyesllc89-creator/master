# Tokio732_VolLab — XAUUSD and BTCUSD edition

`Tokio732_VolLab.mq5` is the author's engine 3614 source with these changes
(`git log -p -- Tokio732_VolLab.mq5` shows every line):

1. The symbol check in `CheckAccount732` accepts symbols that start with `XAUUSD` **or** `BTCUSD`
   (any broker suffix, e.g. `BTCUSDm`).
2. New input `LiveTradingEnabled` (group 00, default `false`). With `false` the EA behaves as the
   author shipped it: it refuses to start on a chart and sends no orders outside the Strategy
   Tester. With `true` it starts on a chart and sends real orders.
3. Live-only fixes needed for (2):
   * The volatility state of an open basket (distance and trailing multiplier) and the cooldown,
     flat-since and cushion state are saved with the rest of the live state, so a terminal
     restart in the middle of a basket continues with the same distances. Before, a restart
     reset them to 1, i.e. about one third of the intended distances and trailing levels.
     State files from the old build are not read (new signature 7321202).
   * If the H1 history needed for the ATR is missing, no basket is opened (dashboard state
     `ESPERA_HISTORIAL_ATR`). Before, the factor silently fell back to 1, which with the gold H6
     preset (volatility switch off, lot ∝ factor^-1.5) would open a basket about 5 times too large.
   * The dashboard header shows the symbol and the current volatility factor.

The order logic is unchanged.

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

## Live (chart) use

Set `LiveTradingEnabled=true` in the Inputs tab, allow algo trading, and attach the EA to an
M5 chart of the symbol. Still enforced by the author's code and not changed: the account must be
an **Exness** account (`CheckAccount732`), in **USD**, with **hedging**; one copy per
account/symbol/magic (a lock file in `Common\Files`); no new baskets while positions with another
Tokio magic are open on the symbol. The EA writes its state, panel and logs to `Common\Files`;
do not delete the `.state` file while a basket is open.

Before real money: run it on an Exness demo account for several weeks, and compare its basket log
(`Common\Files\Tokio732_USD_<login>_..._baskets.csv`) with a Strategy Tester run over the same
dates. The calibration behind the presets is a simulation (`../REPORT.md`,
`../REPORT_TIMEFRAMES.md`); the gold and bitcoin H6 presets were flat and −19 % on the only recent
data, July–August 2026. The EA has no hard stop per position; the basket stop is a percentage of
balance checked on every tick, so a gap, a disconnection or a weekend can take the loss past it.

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

## VT Markets and cent (USC) accounts

Added inputs (group 00), all defaulting to the author's original behaviour:

| Input | Default | Use |
|---|---|---|
| `RequireExnessBroker` | `false` | `true` restores the Exness-only check. With `false` any broker works. |
| `EntryHourClock` | `0` server time | `1`: `EntryHourFrom/To` are UTC and the server runs on GMT+2 winter / GMT+3 summer (European DST), as VT Markets does. The calibrated hours are UTC (Exness servers are UTC), so on VT Markets use `1`. |
| `ReferencePriceValueLotUSD` | `0` auto | The real-USD value of 1.0 lot per 1.0 price move that the preset lots were written for: 100 for gold (100 oz), 1 for bitcoin (1 BTC). At start-up the EA reads the broker's real value (`OrderCalcProfit`, converted from USC to USD) and multiplies every lot by reference / actual. On Exness USD accounts the factor is 1 (no change). |

USC (cent) accounts are accepted. All money inputs (`ReferenceBalanceUSD`, `TrailArmUSD`, …)
stay in **real USD**; the EA divides the USC balance by 100 internally, as the author's code
already did. The lot conversion keeps the real-dollar exposure equal to the calibration: for
example, a cent gold symbol with a 100 oz contract quoted in USC is worth 1 real USD per lot per
1 USD of gold, so lots are multiplied by 100. The Journal prints this at start-up:

```
732_UNITS currency=USC factor=100 USD_price_value_per_lot=1 lot_conversion=100 ...
```

Check that line on your first run. If `lot_conversion` is not what your account's contract implies,
set `ReferencePriceValueLotUSD` explicitly or stop.

Presets for VT Markets: `../presets/TOKIO_VolLab_XAUUSD_H6_VTMARKETS.set` and
`../presets/TOKIO_VolLab_BTCUSD_H6_VTMARKETS.set` (H6 presets with `EntryHourClock=1`).

VT Markets' server clock also changes when H6 bars start (server midnight instead of UTC
midnight). Re-simulated with EET-aligned H6 bars, the presets give the same picture
(`../results/broker_clock.csv`; out-of-sample median of monthly 1,000 USD starts: gold 1,797 vs
1,798, bitcoin 1,854 vs 1,674, no ruined starts).

Not handled: the historical news files are GMT+0 and are compared with server time, so on a
GMT+2/+3 server a news filter would be shifted by 2–3 hours. Both presets have the news options
off. Cent account spreads, commissions and minimum lots differ by broker; set
`ExtraCommissionRTperLot` (real USD per standard-equivalent lot) if your account charges one.
