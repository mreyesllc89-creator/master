# XPW Shape Map v0.6 — cost-aware calibration (MEXC BTCUSDT)

`xpw.py` is a bar-by-bar Python replica of `xpw_shape_map_v0.6_strategy.pine`
(Turn ▲/▼, Predict entries, fail-exit, SL / TP / trailing stop, reversals).
Its armed-signal bars match the TradingView export 100% on every timeframe
(`check2.py`).

Data: TradingView CSV exports of MEXC:BTCUSDT, 1m / 15m / 30m / 60m / 2h / 3h /
4h / 1D / 1W (~890 bars each; 1W from 2017). Usage:

    python3 -I calibration/check2.py calibration <csv_dir>    # replica vs TV
    python3 -I calibration/calib.py  calibration <csv_dir> out.json   # per-TF grid
    python3 -I calibration/joint.py  calibration <csv_dir>    # one ATR rule, all TFs
    python3 -I calibration/final.py  calibration <csv_dir>    # chosen rule, cost sensitivity

## Costs modelled (per fill)
| | value | note |
|---|---|---|
| Commission | 0.02% | MEXC USDT-M futures taker (strategy default). Calibration selection ran at 0.05% spot and 0.02% futures: same winner. Funding not modelled. |
| Slippage | $5 | stop / market fills only, not TP limits |
| Spread | $1 (half = $0.50 per fill) | folded into TradingView `slippage = 550` ticks |

## Fill models
* `tv` – TradingView OHLC path (open → nearer extreme → other extreme → close).
* `pess` – trail can't activate and fire on the same candle; SL wins ties.
  Used for selection. Tight trails ($25) look very profitable in `tv`
  and lose in `pess`: that gap is the OHLC illusion, not edge.

## Selection
Grid over SL / TP / trail activation / trail distance in ATR(14) multiples of the
signal candle; score = sum over 2h–1W of min(first 60%, last 40%) net / ATR%.
Winner: **SL 6×ATR, trail activation 3×ATR, trail distance 1.5×ATR, no TP**
(TP 2–6×SL changed nothing). Re-running the selection at 0.02% gives the same rule.

## Result (chosen rule, `pess`, MEXC spot costs, % per trade at 1x summed)
| TF | trades | no costs | with costs | PF | futures fees | $20 slip |
|---|---|---|---|---|---|---|
| 1m | 56 | -0.5% | -6.5% | 0.15 | -3.2% | -8.7% |
| 15m | 96 | -2.1% | -12.7% | 0.40 | -6.9% | -16.1% |
| 30m | 77 | +4.7% | -4.0% | 0.78 | +0.6% | -6.7% |
| 60m | 52 | +5.2% | -0.7% | 0.95 | +2.4% | -2.6% |
| 2h | 52 | +4.1% | -1.9% | 0.93 | +1.3% | -3.9% |
| 3h | 35 | +14.7% | +10.6% | 1.64 | +12.7% | +9.2% |
| 4h | 47 | +12.4% | +7.0% | 1.38 | +9.8% | +4.3% |
| 1D | 53 | +63.8% | +57.7% | 1.82 | +60.9% | +55.7% |
| 1W | 15 | +37.5% | +34.8% | 1.21 | +35.8% | +31.7% |

Old `$` table (SL $150–2500, trail $25) with costs, `pess` model: negative on
every timeframe (e.g. 1D -5.3%, 1W -39.3%), despite PF 5–11 under `tv`.

Caveats: 1m–60m samples cover only 1–5 weeks; 1W has 15 trades and a deep
drawdown (2018–2022). Treat 3h / 4h / 1D as the evidence, the rest as hints.

---

# VT Markets (MT5 ticks): XAUUSD-ECNc and BTCUSD.c

Script: `xpw_shape_map_v0.6_strategy_vtmarkets.pine`.

`ticks.py` replays MT5 tick exports (`<DATE> <TIME> <BID> <ASK> ...`, tab separated):
bars are built from BID, buy stops trigger on ASK, sell stops on BID, long exits on BID,
short exits on ASK, and every stop / market order fills on the next tick. TP fills at its
limit price. Commission is charged per unit per side.

    python3 -I calibration/tick_merge.py  calibration <dir with MT5 csvs>   # -> <SYMBOL>.pkl
    python3 -I calibration/tick_calib.py  <SYMBOL>.pkl <tick> <comm/unit/side>
    python3 -I calibration/tick_robust.py <SYMBOL>.pkl <comm> 30min 3 0 1 1.5

Data: XAUUSD-ECNc 2026-07-01..08-07 (8.8M ticks, Jul 15-17 missing), BTCUSD.c
2026-07-01..08-13 (4.8M ticks). Measured spread: XAU median $0.12, BTC median $17.03
(0.027%). Commission assumed RAW ECN $6/lot round turn: $0.03/oz/side for gold,
$3/BTC/side for BTC (not confirmed for BTC).

| Symbol / TF | SL / act / dist (ATR) | trades | net | PF | train / test | neighbours positive |
|---|---|---|---|---|---|---|
| XAU 30m | 3 / 1 / 1.5 | 72 | +5.10% (+$206/oz) | 1.83 | +2.78 / +2.32 | 27 / 27 |
| BTC 2h | 3 / 0.5 / 1.5 | 30 | +2.53% (+$1592/BTC) | 1.28 | +1.02 / +1.51 | 23 / 27 |
| BTC 30m | 4 / 1 / 2, TP 2R | 144 | +2.65% | 1.14 | +1.45 / +1.20 | 5 / 27 (rejected) |

Best settings that still lost (or weren't robust): XAU 1m (+2.4%, PF 1.04, 1% of grid
positive), 5m, 15m, 60m; BTC 1m (-137%), 5m (-21%), 15m (-6%), 60m (-6%).
The MEXC rule (6 / 3 / 1.5) lost on both VT symbols at 30m-2h.
