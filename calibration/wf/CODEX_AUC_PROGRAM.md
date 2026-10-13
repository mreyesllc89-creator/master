# Joint program (Claude + Codex): raising the BTC direction AUC

> **Paste-ready prompt for Codex: section 10 at the end of this file** (also posted as a comment on
> [mreyesllc89-creator/master#6](https://github.com/mreyesllc89-creator/master/pull/6)). Everything above it is the
> program the prompt refers to.

Status: round 1 design (designed by three independent planners and two judges on 2026-10-13; the judges' synthesis is what follows). Written by Claude for the user to hand to Codex. The user relays every message between the two
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

## 5. Round 1: five blocks, each nested on the frozen 17-input score
Every block is a small, fixed set of inputs appended to the 17 inputs of the frozen score (`VETO_PORT_CONTRACT.md`
section 2), refitted by the identical procedure (L2 = 1 logistic, 30 Newton steps, standardised on training rows, one
model per horizon) on identical training rows, and compared with the 17-input model on **identical candles** (rows
where every input of both models is defined, the candle H steps ahead opens exactly H x 5 minutes later, the label is
non-zero and ends inside the window). No trees, no tuned hyper-parameters, no search over lookbacks: the trailing
windows are 100 (as `vol`) and 288 candles (one day of M5), fixed. Missing input: not scored, never imputed; the
excluded share is a reported column. On Codex's broker rows (history from 2024-01, too short to refit the 17) the block
is **stacked** on the period-wise frozen score logit (`results/g2_broker/` weights for 2024H2-2025H2 rows, the 2026
bank from 2026-01) and compared with the same stacking without the block (REF-K).

| # | Block | Inputs (exact formulas are pinned in `PREREG_R1.md` before the freeze) | Who | Honest prior at H = 1 | Portable to |
|---|---|---|---|---|---|
| B1 | **Order flow** (the ceiling of the whole volume family) | from the five Binance 1-minute klines inside the M5 candle: `ofi5` = 2 x taker-buy / volume - 1; `ofi20` over the last 4 candles; `ofi_z` = ofi5 / its trailing-288 sd; `tcnt` = ln(trades / trailing-288 median); `relvol` = ln(volume / trailing-288 median); `ofi5 x vol` | Claude | +0.004 .. +0.012 on Bitstamp / Binance labels, less on broker labels | MT5 only via a live external feed; Pine never (TradingView has no taker side). Research value even if not portable: if B1 adds < +0.003, every volume proxy is dead |
| B2 | **1-minute sub-structure** (the portable version of B1) | from the venue's own 1-minute candles: `relvol` (volume; broker: tick volume); `bvc5` = sum over the 5 minutes of volume x (close - open) / (high - low), over candle volume (0 when high = low); `bvc20` over 4 candles; `r_last1` = (close - close of minute 4) / ATR14; `cloc` = (close - low) / (high - low) - 0.5; `nzero` = zero-volume (zero-tick) minutes, 0-5 | both | +0.001 .. +0.005 | Pine (volume of the chart symbol), MT5 (tick volume) |
| B3 | **Clock** | 7 fixed terms on the server clock from UTC instants: sin / cos of minute-of-day and its second harmonic, weekend, the 30 minutes before a perpetual funding settlement (00 / 08 / 16 UTC), the US cash session (New York 09:30-16:00 with its DST) ; plus the 7 interactions with the standardised score logit (14 parameters) | both | main effects +0.000 .. +0.002; the interactions are where any value is | Pine and MT5, for free |
| B4 | **Broker microstructure** | `spr_c` = ln(spread at the close / trailing-288 median), `spr_d` = ln(spread / previous candle's), `spr_max` = ln(max spread in the candle / median), `tick5`, `tick_last` (tick volume of the candle and of its last minute, over their trailing-288 medians), `nzero`. The spread field's semantics are measured against the 2026-05 .. 10 ticks and written into the PREREG before the inputs are defined; the 2026-05 construction seam (server-built M1 vs tick-rebuilt) gets its parity table before anything is pooled across it | Codex | +0.000 .. +0.003; spread and tick volume track volatility, which `vol` already has | MT5 only |
| B5 | **Extremes-only permission and calibration** (no new information; the one deployable threshold change this round can deliver) | the frozen score's accuracy-coverage curve at 5 / 10 / 15 / 20 / 25 / 30 / 35 / 41.5 % per side, each against the equal-coverage distance baseline (|dist| >= k); decile monotonicity (Spearman); Brier score and calibration error of the raw sigmoid vs Platt scaling fitted on training rows | both | raw accuracy at 20 % coverage 53.5-55 % on broker 2026 (vs 52.1 % at 53 %); the continuous AUC does not move | Pine and MT5 as an optional threshold pair, off by default |

Pre-check facts Codex reports **without** a slot: the monthly median and sd of the minute-scale price gap Binance vs the
broker and MEXC vs the broker. If the median |gap| is below 1 basis point the cross-venue gap hypothesis is closed
without ever being scored; otherwise it is queued for round 2 with the -1-minute offset as the deployable column and a
+1-minute offset on the dry window only as the positive control for look-ahead.

MEXC, the user's own venue (TradingView charts MEXC:BTCUSDT): Codex fetches from the user's machine MEXC BTCUSDT spot
and BTC_USDT perpetual 1-minute klines (as far back as the API serves them), the full funding-rate history and records
open interest forward (the API gives the current value only). Uses in round 1: (a) MEXC closes as a **replication label
venue** for B1-B3 (2026-01 .. 10, labelled inspected because the calendar was seen through Bitstamp), (b) the MEXC-vs-
broker gap pre-check, (c) MEXC funding to anchor the archived funding timestamps (round 2). MEXC candles never enter
the repository (size and provenance); they travel as a zip whose SHA-256 is quoted in the message.

## 6. Windows, metric, reading rule
- **Primary quantity**: M5, H = 1, the paired increment of the continuous ROC-AUC (ties half) of the block model over
  the 17-input model on identical candles, server clock (UTC as a sensitivity on Claude's side). H = 3 and 10 are
  reported columns. Always printed next to it: the permission AUC of G2P + block vs G2P, the raw accuracy and coverage
  of R2s + block vs R2s (the veto with the block), balanced precision and recall, label counts, n scored, excluded
  share, the zone alone (P0) as the reference row, per-fold flags.
- **Bootstrap**: paired, deterministic blocks on the UTC grid from the window's start, `block_seconds = max(172800,
  4 x H x 300)`, seed = 20261101 + window index, B = 2,000, blocks shared across H, scores and rules. The primary CI
  at level 1 - 0.05 / k with k = blocks actually run in the round (five -> 99 %); everything else at 95 %. CI widths
  are sized from the development window's actual paired variance before the freeze, so the minimum effect below is
  known to be resolvable.
- **Windows** (every label written into the PREREG): DRY = Bitstamp 2017H2 and broker 2024-03 .. 06 (code checks,
  never reported). DEV = Bitstamp 2018-2019 (formula looks allowed, each logged; the bounce era). Claude's primary
  TEST-A = **Bitstamp 2020** in two half-year folds (never a test window for any rule so far; training rows of every
  earlier fit; the March 2020 crash inside). Replication TEST-B = 2021-2022 (inspected labels, fresh inputs);
  2023-2026 descriptive only. Codex's primary TEST-D = **broker 2026-01-01 .. 2026-10-12** by quarter (inspected labels
  via Bitstamp and the veto test; fresh inputs), stacking training from 2024-07-01. TEST-M = MEXC 2026-01 .. 10 as
  the replication venue for B1-B3 (inspected labels, fresh inputs). **FORWARD** = broker candles from the freeze push,
  closed at the later of 35,000 clock-contiguous scorable M5 candles and a named date about four months out, read once.
- **Admitted** (historical): the Bonferroni CI above 0 **and** point increment >= +0.003 **and** a positive point
  increment in every replication fold **and** R2s + block raw accuracy >= R2s at |coverage difference| <= 0.05 **and**
  every guard passes (truncation test at two cuts, timestamp audit on both clocks, seam tables, the normaliser formula
  pinned as "trailing N candles" or "same slot over N days"). A block with the CI above 0 but a point below +0.003 is
  **CLOSED-TOO-SMALL** (the fractal nested check was +0.0003 with a CI above 0: a pass by significance alone is not a
  result).
- **Confirmed** (forward): the forward CI above 0 **and** point >= +0.002 **and** the R2s + block raw-accuracy CI above
  0 at matched coverage **and** the sign replicated on Claude's Bitstamp / Binance run of the same calendar window.
  Tier-1 port (an optional switch, off by default, in MT5 and, where the input exists, Pine) only when confirmed and
  the parity fixture matches; the existing modules and their defaults stay hash-verified unchanged.
- **Closed** blocks are not retried with variants in the same round; a variant is a new hypothesis in a later PREREG.

## 7. Operations
- `calibration/wf/auc_program/`: `LEDGER.md` (every window on every source with its status, every hypothesis with its
  status; Claude appends, Codex's messages are logged verbatim), `PREREG_R1.md` (the freeze), `schemas/` (feature,
  scoring and aggregate column lists with units and clocks), `fixtures/bitstamp_fixture_2017H2_M5.csv` (2,000 public
  Bitstamp M5 candles from the dry window with every input of the 17 and of B1-B3, zone, logits, permissions: both
  sides match it row by row before any number is exchanged; tolerance 1e-6 relative on inputs, identical permissions),
  `check_no_raw.py` (fails a commit that adds any per-candle file with more than 5,000 rows or any broker / MEXC
  candle file), `results/R1/` (aggregates only).
- **Runner is never the verifier.** Each side recomputes the other's headline numbers from the frozen definitions on
  its own copy of the data; a disagreement is settled by a third computation on the public fixture. Agreement
  tolerance: AUC to 5e-6 on the fixture, aggregates to 1e-4.
- **Forward archive** (Codex): a daily job from the freeze date storing the day's broker M1 bars and ticks privately
  with a manifest line (date, row count, first and last millisecond, SHA-256) committed to `results/R1/forward_manifest.csv`.
- Messages follow section 4; every message ends with NEXT (what the sender does without waiting) and carries the
  commit SHA, the file paths and, for any file exchanged, its SHA-256. A message that needs a same-sitting reply is
  malformed.

## 8. First week
**Claude** (days 1-7): `PREREG_R1.md` draft with the exact formulas of B1-B5, the windows and the reading rule;
`auc_program/ni_common.py` (a resampler that carries volume, taker-buy volume, trade count, the sub-candle path and the
zero-minute count from 1-minute to M5 / M10 / M20 without touching the frozen `wf_common` / `fgrun`); the data audit
tables (Bitstamp zero-volume share by year, Binance gaps, the funding archive's timestamp offset question); the public
fixture; `ni_claude.py` with modes dry / dev / real / forward (nested fit, bootstrap, truncation test, timestamp audit);
`ni_codex.py`, a reference scorer that reads a private M5 feature table with the spec's columns and writes only
aggregates, tested on a synthetic fixture and on Bitstamp server-clock data; the freeze commit, hash quoted to Codex.

**Codex** (days 1-7): (1) data inventory **as facts, no metrics**: BTCUSD.c M1 range and gap list 2024-01 .. today,
fields present (tick volume, whether real volume is non-zero, spread), the spread field's semantics measured against
the 2026-05 .. 10 ticks, the server-M1 vs tick-rebuilt M1 overlap parity for 2026-05 .. 10, monthly spread / tick-volume
/ missing-minute tables, a per-day DST-edge audit around 2026-03-08 and 2026-11-01; (2) start the daily tick and M1
archive with its manifest immediately; (3) fetch MEXC spot and perpetual 1-minute klines, the MEXC funding history and
start recording MEXC open interest; report ranges, gaps and SHA-256s; (4) the gap pre-check facts (Binance vs broker,
MEXC vs broker, monthly median and sd of the minute-scale gap); (5) the broker feature extractor per the schema (M1 ->
M5 on the server clock, the 17 contract inputs from the existing veto code, B2 / B3 / B4 inputs); (6) the dry run on
broker 2024-03 .. 06 with `ni_codex.py` as soon as the freeze hash arrives, aggregates only.

**Both, end of week 1**: fixture parity matched on both sides, dry aggregates exchanged, PREREG_R1 revised once with
Codex's data facts and frozen (commit pushed, SHA quoted by both), the forward window's start timestamp written into
the PREREG. Then TEST-A / TEST-B (Claude) and TEST-D / TEST-M (Codex, Claude) run and are cross-verified; the forward
window is read once at its close.

## 9. Round-2 queue (no computation on any evaluation window until its own PREREG) and what not to do
Queued: perpetual funding as a positioning input (after the archive's timestamp offset is anchored: its Binance rows
sit at 03 / 11 / 19 UTC all year against the documented 00 / 08 / 16 settlements, so a +3 h or a -5 h stamp both fit;
anchor one externally dated rate via MEXC or Codex, or lag every rate by one settlement); the 1-hour horizon as its own
product (H = 12 on M5: the same inputs score 0.577 there vs 0.557 at 5 minutes on 2018-19, exploratory; needs a
lifetime and re-arming rule, so a separate PREREG); refit cadence for the MT5 port (quarterly expanding vs rolling
8 quarters vs fixed); magnitude-aware targets; a two-head filter (local head at H = 3, stack head at H = 12); the
tick-rule quote imbalance once the tick archive is six months long; MEXC open interest once recorded; the cross-venue
gap if the pre-check shows >= 1 basis point.

Not to do: more price-derived indicators from the same candles (other RSI / TDI lengths, more return horizons, more
structure readings, Hurst, divergence); the fractal stack as a 5-minute hypothesis (measured: +0.0003); gradient
boosting or any tuned model (train 0.75-0.96 vs test 0.52 in the feature study); re-tuning the zone grid, parent /
child timeframes or minimum aligned (6,640 candidates gave at best +0.005 with broker CIs through 0); the distance-only
veto as a baseline; quoting Bitstamp 2018-19 H = 1 numbers as effect sizes (1-2 points are last-trade bounce);
reading a Bitstamp-labelled cross-venue gap as broker evidence (it is label-venue staleness); picking lookbacks,
thresholds or dummies on a test window; pooling broker rows across the 2026-05 seam before the parity table; mixing
XAUUSD or cross-asset legs into the BTC verdicts (a separate program); any Pine or MT5 default change; any message that
stalls the other agent.

## 10. Paste-ready prompt for Codex
```
Codex, this is the joint research program with Claude to raise the BTC direction AUC. It is written up in the
repository mreyesllc89-creator/master, branch claude/jolly-rubin-xk3c4b, file calibration/wf/CODEX_AUC_PROGRAM.md
(https://github.com/mreyesllc89-creator/master/blob/claude/jolly-rubin-xk3c4b/calibration/wf/CODEX_AUC_PROGRAM.md).
Read it fully, then HANDOFF_WF.md sections 1-13 and VETO_PORT_CONTRACT.md in the same folder for the frozen
definitions. The human user relays every message between us by pasting it; write each message so that it stands on
its own, carries the commit SHA, file paths, data ranges and the SHA-256 of any file you exchange, and ends with
NEXT (what you do without waiting). Never wait for a reply to continue.

Where we are: the zone alone scores AUC 0.51-0.52; the frozen 17-input logistic score 0.53-0.545 (0.523 on your
broker data at H = 3); the veto adds +0.006 permission AUC on fresh broker 2026. Everything so far is computed from
the same price candles and saturates near 0.55 at 5 minutes. Round 1 tests five fixed blocks, each nested on the
frozen 17 inputs by the identical L2 logistic procedure on identical candles: B1 Binance taker-buy order flow
(Claude), B2 1-minute sub-structure from volume / tick volume (both), B3 clock harmonics and session dummies with
interactions (both), B4 broker spread and tick intensity (you), B5 extremes-only permission and calibration of the
frozen score (both). Primary quantity: M5, H = 1, paired increment of continuous ROC-AUC on identical candles, server
clock, deterministic 48-hour block bootstrap, Bonferroni CI; admitted only with CI above 0 AND point >= +0.003 AND
replication in every fold AND no loss of raw accuracy at matched coverage; confirmed only on a forward broker window
read once. Nothing is picked on a test window; nothing changes a Pine or MT5 default; raw broker, MEXC or exchange
candles never enter the repository (aggregates, definitions, code and hashes only).

Your first message back (NI-codex-001), facts only, no metrics:
1. Data inventory of BTCUSD.c: M1 range and gap list 2024-01 .. today; fields present (tick volume; is real volume
   non-zero?; spread); the spread field's semantics measured against the 2026-05 .. 10 native ticks (bid-ask at the
   close? average? max?); the overlap parity table server-built M1 vs tick-rebuilt M1 for 2026-05 .. 10 (OHLC,
   tick count); monthly tables of median spread, tick volume and missing minutes; a per-day audit around the DST
   edges 2026-03-08 / 09 and 2026-11-01 / 02 (bar times vs UTC).
2. Start today, before anything else, a daily archive of BTCUSD.c ticks and M1 bars on your machine with a manifest
   line per day (date, row count, first / last millisecond, SHA-256). The manifest, not the data, goes to the
   repository later.
3. MEXC (the user's venue): fetch BTCUSDT spot and BTC_USDT perpetual 1-minute klines as far back as the public API
   serves them, the full funding-rate history, and start recording open interest at every candle close (the API
   gives only the current value). Report ranges, gaps, clock, SHA-256s. Keep the data on the user's machine; it will
   travel as a zip with its SHA-256 when Claude asks for it.
4. Gap pre-check: monthly median and sd of the minute-scale price gap, Binance vs the broker (Binance 1-minute
   closes from the public GitHub mirror parshant231234-eng/BTCUSDT-Historical-Data, which Claude also uses; quote the
   file SHA-256s) and MEXC vs the broker. If the median |gap| is below 1 basis point, say so: the gap hypothesis is
   then closed without a slot.
5. Confirm whether the MT5 terminal can read an external REST feed with WebRequest (needed only if B1 ever ports),
   and list the broker's other symbols with ticks (for later rounds; not used in round 1).
6. Answer any point of the program you disagree with as a numbered objection with the evidence; do not change the
   design silently.

Then, when Claude's freeze message arrives with the commit SHA of PREREG_R1.md, the schema and the reference scorer
ni_codex.py: match the public fixture (2,000 Bitstamp M5 candles, every input) row by row to 1e-6 and identical
permissions before any number; build the broker feature extractor (M1 -> M5 on the server clock, the 17 contract
inputs from your veto code, the B2 / B3 / B4 inputs exactly as pinned); run the dry window broker 2024-03 .. 06 and
send only aggregates; then TEST-D (broker 2026-01-01 .. 2026-10-12 by quarter, stacking trained from 2024-07-01) and
the MEXC replication, each as aggregates with n, excluded share, CIs, seeds and the hashes of the scripts you ran.
You verify Claude's TEST-A / TEST-B numbers from the frozen definitions on your copy of the public data, and Claude
verifies yours; the forward window is read once at its close. Use the message format of section 4 of the program
file. Do not run anything on the forward window, and do not change the veto module's numerics or any default.
```
