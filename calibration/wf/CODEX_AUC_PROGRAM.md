# Joint program (Claude + Codex): raising the BTC direction AUC

Status: round 1 design. Written by Claude for the user to hand to Codex. The user relays every message between the two
agents by pasting it, so every message is self-contained, names its commit, files and numbers, and never assumes an
answer in the same sitting. Nothing in this program changes a Pine or MT5 default; a change is proposed only after a
fresh test passes the reading rule below.

## 0. Where we stand (what the AUC is now, and what did not move it)
BTC, 5-minute filter candles, labels sign(close[t+H] - close[t]) on closed candles, H = 1 / 3 / 10 (mean reported;
H = 1 = the next 5 minutes). Figures from `HANDOFF_WF.md` sections 1-13 and `results/`:

| What | ROC-AUC | Where tested |
|---|---|---|
| zone alone (the filter's permission) | 0.51-0.52 | every timeframe, every window, fresh and broker |
| parent / child zone tuning | +0.005 at best (M5) | walk-forward 2021-2026, broker 2024-2025 |
| 17-input logistic score (continuous) | 0.53-0.545 Bitstamp; 0.523 broker (H = 3) | fresh 2018-19, 2021-22, broker 2024-25 |
| score veto (permission AUC) | +0.022 Bitstamp fresh; **+0.006 broker 2026** | `results/veto/` |
| adding W1 .. M15 readings at 5 min | +0.0003 | `results/fractal/` |
| the same 21 inputs at a 1-hour horizon | 0.577 (vs 0.557 at 5 min) | `results/fractal/ablation.csv`, exploratory |
| gradient boosting on price inputs | train 0.96, validation 0.50 (daily) | `calibration/direction/auc/` |

Every input so far is computed from the same price candles. That family saturates near 0.55 at 5 minutes. Raising the
AUC further needs **information the candles do not contain**, or **a target the candles predict better** (a longer
horizon), or **a model that tracks the regime** (the edge was +4 pts in 2018-19 and +1.4 in 2026).

## 1. Data each side can reach (checked 2026-10-13)
Claude's container reaches GitHub (and nothing else that matters: Binance, Bybit, Bitstamp, MEXC, Dukascopy and
Kaggle are blocked). Codex runs on the user's machine with the MT5 terminal and open internet.

| Source | Content | Who has it | Status |
|---|---|---|---|
| Bitstamp BTC/USD 1-minute, 2014-2026 (OHLCV) | the study's price data, UTC and server clock | Claude | in hand |
| Binance spot BTCUSDT 1-minute, 2017-08 .. 2026-10 (OHLCV, quote volume, **trade count, taker-buy volume**) | order-flow proxy: taker-buy share, trade intensity | Claude (public GitHub mirror `parshant231234-eng/BTCUSDT-Historical-Data`, 4.80 M candles, 34 gaps, 93.9 % same 5-minute direction as Bitstamp since 2024) | in hand, aggregated to 5 min |
| Funding rates BTC-USDT perpetual, 8-hourly: Binance and Gate 2020-2023, Bybit / HTX / KuCoin / **MEXC** 2021-2023, dYdX hourly 2022-2023 | positioning / carry | Claude (public GitHub `supervik/historical-funding-rates-fetcher`) | in hand; 2024-2026 missing |
| **MEXC** BTC_USDT perpetual and BTCUSDT spot: 1-minute klines, funding-rate history, open interest (current value only, to be recorded forward) | the user's own venue (TradingView charts are MEXC:BTCUSDT) | **Codex** (MEXC public API from the user's machine; Claude cannot reach MEXC) | to fetch |
| Broker BTCUSD.c: M1 from 2024-01, ticks from 2026-05, **tick volume, spread**; other symbols (XAUUSD) | execution venue, intraday liquidity | Codex | in hand (private, never in the repository) |
| Funding 2024-2026 (Binance, MEXC), open-interest history, liquidations | positioning | Codex (exchange APIs); no free history for liquidations was found | to fetch if round 1 says funding matters |

Portability rule for any new input: TradingView can read OHLCV of any TradingView symbol inside the Pine filter (one
`request.security` each, 40 per script); it cannot read taker volume, funding or open interest. MT5 reads the broker's
symbols and can fetch public APIs with `WebRequest` (so an EA could read MEXC funding / open interest live). So an input
that only exists off-chart can be ported to MT5, not to Pine; the research still measures it, because knowing that the
information is there (or is not) is the point.

## 2. Ground rules (unchanged from the study)
1. **Freeze before you look.** Every round has a `PREREG_<round>.md` naming the hypotheses (at most five), the inputs
   exactly, the windows, the horizons, the metrics and the reading rule, committed and pushed before the first
   evaluation on anything but the dry window. Code checks run on the dry window only (2017H2 for Bitstamp-era inputs;
   for inputs that start later, the first three months of their history).
2. **Fresh means fresh.** A window counts as fresh for an input only if nothing about that input was ever computed on
   it. Windows already inspected for the price inputs (2021-2026) stay usable as *secondary* windows for a new input the
   first time it is evaluated, and are labelled as inspected everywhere.
3. **One primary metric per round**: ROC-AUC of the continuous score at H = 1 on the fresh window, paired 48-hour
   block bootstrap, 95 % CI. Always also reported: the permission AUC and raw accuracy with coverage (so a result can
   be read as a trading rule), balanced precision and recall, label counts, H = 3 and 10.
4. **Purging.** Training labels end before the test window starts; at long horizons the overlap of labels is handled
   by the block bootstrap (blocks of at least 4 x the label span) and by thinning when a judge asks.
5. **Nothing from the broker or from MEXC order data enters the public repository as raw candles.** Aggregates,
   feature definitions, code, model files and SHA-256 hashes do. Public exchange candles that Claude already holds
   from public mirrors are also kept out of the repository (size), with the source named instead.
6. **Independent verification.** The agent that did not run the evaluation recomputes the headline numbers from the
   frozen definitions (as both did for the veto: `verify_veto/`, `codex_fresh_broker_2026.md`). A number is reported
   as verified only after that.
7. **No default change** in Pine or MT5 without: a fresh window with the CI of the AUC gain above 0 **and** the CI of
   the raw-accuracy gain above 0 at the same coverage, and a second fresh test on the deployment venue's own data.
8. **Stop rule per round**: a hypothesis whose fresh gain has a CI containing 0 is closed, not retried with variants.

## 3. Division of labour
- **Claude**: Bitstamp and Binance features, fitting and evaluation code in `calibration/wf/`, pre-registration files,
  bootstrap and verification scripts, the Pine side, the handoff documents.
- **Codex**: MEXC and broker data extraction into *feature tables* (aggregates per closed candle, not raw candles, when
  they are shared; raw data stays on the user's machine), independent recomputation of Claude's headline numbers from
  the frozen definitions on its own copy of the data, the MT5 ports, live-recording jobs (open interest) that only
  Codex's machine can run.
- **The user**: relays messages, uploads the files the two agents exchange (zips of feature tables), and decides on
  any default change.

## 4. Message format (both directions; paste as is)
```
FROM: Claude | Codex        TO: Codex | Claude        DATE: YYYY-MM-DD
RE: <round / hypothesis id>
COMMIT: <sha of the repository state this refers to>   FILES: <repo paths>
DATA: <source, symbol, timeframe, first/last timestamp, clock, row count, SHA-256 of any file exchanged>
RESULT: <window> <n candles> <metric> <value> [95 % CI] vs <baseline> <value>; coverage; H = 1 / 3 / 10
STATUS: frozen | dry-run | fresh result | verification | question
ASKS: <numbered, each answerable in one message>
NEXT: <what the sender does without waiting>
```
