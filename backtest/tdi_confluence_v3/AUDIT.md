# Audit of the confirmation test, before it was run

Two blinded review rounds checked the pre-registered test (`PREREGISTRATION.md`, `validate.py`, `engine.py`, the data pipeline) before `validate.py run` was executed.

**Blinding rule.** Reviewers could run the strategy only on the tuning data (BTC 2024-11 → 2026-11) or on synthetic data. They could read the unseen files only for timestamps, trading volume and byte-for-byte equality checks.

**Where the changes are.** Every change made because of a finding is in Amendment 1 (`PREREGISTRATION.md` section 8). All of them were committed before the run.

## Round 1: six reviewers

**Reviewers:** leakage, simulation code, statistical validity, statistics code, data pipeline, and a skeptic. Adversarial verifiers began checking the findings. A usage limit stopped that step after four verdicts, all on statistical validity. Every finding was nonetheless fixed or answered.

| # | Lens | Finding | Kind | Disposition |
|---|---|---|---|---|
| 1 | leakage | Header said the test data had never been loaded and existed only as zips | defect, low | Header corrected (8.1) |
| 2 | leakage | "Unseen" needs a qualifier: BTC/USD 2023-01 → 2026-10 was analysed earlier for another indicator | suggestion | Disclosed (8.1) |
| 3 | leakage | Off-grid stretches: 1-minute series read one bar late; one clock minute holds two bars | suggestion | Fixed in `engine.py` (8.3) |
| 4 | leakage | Result not tied to the registered code and data | suggestion | Provenance in `validation.json`, data manifest, strict start (8.1, 8.6) |
| 5 | sim-code | Off-grid stretches: most entry signals there are not the frozen rule's | defect, medium | Fixed (8.3) |
| 6 | sim-code | Signal cache key does not see the inside of a dataset | defect, low | Fixed (8.3) |
| 7 | sim-code | A stop distance of exactly 0 counted as valid (Pine needs `slDist > 0`) | defect, low | Fixed (8.3) |
| 8 | sim-code | In runs of unchanged 1-minute closes, crossings and pivots are decided by floating-point noise | suggestion | Stale-price exclusion (8.2) |
| 9 | stat-validity | T1 is valid only if months are independent: 4–11% false positives with multi-month regimes | defect, medium; **verified real** | Replaced by T1a + T1b + T4 (8.4). Remaining regime sensitivity stated in round 2 |
| 10 | stat-validity | T2 is not a 2% test of entry skill (passes 4.5% with no skill) | defect, medium; **verified real, lower size** | Replaced by the centred T2, and T3 made binding (8.4) |
| 11 | stat-validity | Bootstrap p1 runs slightly hot (2.2–2.5%) | defect, low; verified not material | Replaced anyway (8.4) |
| 12 | stat-validity | Power overstated once month clustering is counted | defect, low; **verified real** | Corrected (8.5) |
| 13 | stat-validity | "PROVEN at 98%" will be read as "98% sure the edge is real" | suggestion | Reworded to "significant at the 98% level", meaning spelled out (8.4) |
| 14 | stat-validity | The six-coin "replication" is not independent confirmation | suggestion | Reframed as a supporting reading (8.4) |
| 15 | stats-code | Random-timing null is narrower than the real statistic's no-skill spread | suggestion | As #10 |
| 16 | stats-code | Power and minimum detectable edge assume independent trades | suggestion | Corrected (8.5). The printed line is labelled per test |
| 17 | stats-code | Max drawdown ignores the starting equity | defect, low | Fixed (8.3) |
| 18 | stats-code | A coin with fewer than 3 trades would get random-timing p = 0.0010 | defect, low | Fixed (8.3) |
| 19 | stats-code | Pooled rows print a naive t across correlated coins | suggestion | Removed (8.3) |
| 20 | stats-code | p2 could print as 0.0200 next to PROVEN | defect, low | 6 decimals and counts (8.3) |
| 21 | data-build | Header said the test data was not loaded | defect, low | As #1 |
| 22 | data-build | `data_quality.txt` understates missing minutes by 3 for BTC, ETH and BNB | defect, low | Corrected; formula fixed in `build_npz.py` (8.1) |
| 23 | data-build | Test data not pinned by the pre-registration commit | suggestion | `data_manifest.sha256` committed (8.1) |
| 24 | data-build | Pipeline checks would miss some failures | suggestion | All 782 zips checked against Binance's published checksums (8.1) |
| 25 | skeptic | Costs and fills are optimistic | suggestion, high | "Also under realistic execution" qualifier (8.4) |
| 26 | skeptic | A pass can rest on one volatile regime or year | suggestion, high | T4 consistency and T1b 6-month blocks (8.4) |
| 27 | skeptic | T2 does not test the long/short calls; T3 not binding | suggestion, medium | T3 binding (8.4) |
| 28 | skeptic | T1's p depends on where months start and is anti-conservative with regimes | suggestion, medium | Month boundaries shifted 0–29 days reported; T1b; regime caveat (8.4) |
| 29 | skeptic | bp of notional over-weights volatile trades; results in R may differ | suggestion, medium | R results reported; volatility-scaled power (8.4, 8.5) |
| 30 | skeptic | Power claim optimistic | suggestion, medium | As #12 |
| 31 | skeptic | Other coins are survivors, drift-exposed, same calendar | suggestion, low | Stated in the other-coins reading (8.4) |
| 32 | skeptic | Blinding sentence inaccurate; the run does not verify its inputs | defect, low | Header corrected; strict start checks (8.1, 8.6) |
| 33 | skeptic | `p_null` returned the most significant p for a NaN statistic | defect, low | Fixed: returns no value |
| 34 | skeptic | "PROVEN" wording; neighbours have no pre-set reading | suggestion, low | Reworded; plateau reading fixed in advance (8.4) |

## Round 2: final review of the amended code and text

**Reviewers:** the code path, the statistics, and an end-to-end rehearsal of the strict run on synthetic data.

**Verifiers:** an adversarial verifier checked every defect claim. "Real" meant it would change a result or the verdict, misstate a number in the amendment, or crash the run.

**Coverage:** the reviewers also reported more than 50 passed checks, among them:
- `simulate_x` matches `simulate_d` and an independent reference;
- `t_sf` matches scipy over 800,000 points;
- the strict refusals work;
- a full strict rehearsal on synthetic data takes about 10 minutes and is deterministic.

| # | Finding | Kind | Verdict | Disposition |
|---|---|---|---|---|
| 1 | The "about 1 in 50" false-positive rate assumes short memory in monthly results; the comparison with the registered T1 was not like for like | defect, high | **real** | 8.4 rewritten: conditions stated, regime and carry-over rows added with the registered T1 alongside (`sim_regimes.py`, 40,000 histories a row), and what a pass shows under regimes. Verdict rule unchanged: the extra guards tried cost 9–15 points of power and still miss 2% |
| 2 | The centred T2 passes 2.4–3% of no-skill histories, not about 2% | defect, low | **real** (cause corrected by the verifier) | 8.4 wording corrected: T3 is calibrated, and the full verdict passes 0.4–0.8% of these histories. Rule unchanged |
| 3 | The power table's month effect is weaker than the tuning data's | defect, medium | not established | 60 bp matches the boundary-averaged clustering. The 90 bp sensitivity (38% / 62% power) and the T2/T3 cost were added to 8.5 |
| 4 | Exclusion keyed on the signal bar's month, so a month-end signal could fill on the 1st of an excluded month | defect, low | not material (BTC unaffected) | Adopted the verifier's tested fix: no entry whose signal bar or fill is in an excluded month. Dryrun bit-identical; selftest check added (8.2, 8.3) |
| 5 | Excluded months also suppress reversal exits | defect, low | not material; code matches 8.2 | Rule stated explicitly in 8.2; `data_exclusions.py` docstring and selftest comment corrected |
| 6 | `null_summary` crashes if BTC has fewer than 3 trades | defect, low | unreachable | Guard added (8.3) |
| 7 | T4 skipped undefined leave-one-year-out p-values, depending on year order | defect, low | unreachable | Undefined now counts as a fail (8.4, 8.3) |
| 8 | Strict start passed when git failed | defect, low | unreachable in the planned run | Fixed: exit codes and a valid commit required, files must be tracked (8.6) |
| 9 | Strict start trusted the manifest as it sat on disk | defect, medium | unreachable in the planned run | `data_manifest.sha256` included in the git check; every test file must be listed (8.6) |
| 10 | Strict start passed outside a git repository | defect, low | as #8 | As #8 |
| 11 | Entry possible in an excluded month (end-to-end view of #4) | defect, low | as #4 | As #4 |
| 12 | Report printed the old permutation p under "T3" | suggestion | n/a | Relabelled "reported only"; centred t and p printed next to it |
| 13 | Realistic execution: a gap through the stop fills at the open, not the bar's worst price | suggestion | n/a | Text aligned with the code (8.4). It was not seen once in 232 tuning trades |
| 14 | T1b / T4 wording does not match the code | suggestion | n/a | 8.4 table corrected: blocks start 2017-12; "2017" is one month |
| 15 | Small inaccuracies in 8.2 (zero-volume shares, per-coin counts, threshold dependence) | suggestion | n/a | 8.2 corrected |
| 16 | Printed power line is for T1a alone and uses normal quantiles | suggestion | n/a | Student t quantiles; labelled "each test alone" |
| 17 | A crash after the BTC section blocks a re-run; the console log depends on `tee` | suggestion | n/a | All result files written together at the end; the run writes its own log and never overwrites it; recovery rule in 8.6 |
| 18–20 | Duplicates of #12 and #13 from a second reviewer | – | – | As above |

## After round 2 (checked before committing)

- `python3 validate.py selftest` passes: 232 trades, +62.9 bp, t +2.82, plus the new month-boundary check.
- `python3 validate.py dryrun` gives trades bit-identical to the dryrun of the code before the round-2 changes. Only the renamed power fields, the two new T4 fields and the provenance differ.
- Strict refusals were rehearsed in a throwaway git repository with dummy data. Each of these is refused, and a clean tree passes:
  - an edited registered file;
  - an existing log;
  - a re-hashed but uncommitted manifest;
  - a changed `.npz`;
  - an `.npz` missing from the manifest;
  - a copy outside git.
