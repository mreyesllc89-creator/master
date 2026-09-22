# XPDirection — XPW Direction Ladder v1

FlashGold_Continuation_v2 gets its trade direction from a fractal ladder of XPW Shape
Map instances (1 s … 45 s, plus one parent timeframe). The EA keeps its trigger. It
stops choosing its side.

**Read `XPW_DIRECTION_LADDER_REPORT.md` first** — it carries the header line, the
three prompt-vs-file discrepancies (one of which can invert every trade), the exact
diff, and the host instructions for the three open gates.

## What is here

| Path | What it is |
|---|---|
| `FlashGold_Continuation_v2_XPDIR.mq5` | The `1.05-XPDIR` build. `InpDirMode = DIR_OFF` (the default) is 1.03 behaviour. |
| `XPW_DIRECTION_LADDER_REPORT.md` | The report. Start here. |
| `reference/vote_ref.py` | Independent Python transliteration of the §4 rules. |
| `reference/run_fixtures.py` | **Gate 1 runner.** Fixture expectation vs `vote_ref.py` vs the EA's own compiled rule core. |
| `reference/fixtures/vote_rules.csv` | 49 hand-derived fixtures. |
| `reference/emu/` | Lifts `XPDIR_RULE_CORE_BEGIN…END` out of the `.mq5`, translates it to C++, compiles and runs it (the `XPMap/reference/emu/` approach). |
| `reference/compare_trades.py` | **Gate 0** trade-list comparison of two MT5 tester HTML reports. |
| `reference/gate0_tester_settings.ini` | Gate 0 tester settings (real ticks, fixed window). |
| `reference/ea_1.03_to_1.05_xpdir.diff` | The complete machine diff, 1.03 → 1.05-XPDIR (+765 / −7). |

## Reproduce Gate 1 (needs only python3 and g++)

```bash
cd XPDirection/reference && python3 run_fixtures.py
# stub lint: 0 errors 0 warnings
# fixtures=49 asserts=833 mismatches=0 emu=on
```

`--no-emu` skips the compile step and runs the Python reference against the fixtures
alone. A run with `asserts=0` is a failure, not a pass.

## State of the gates

- **G0** (DIR_OFF is trade-for-trade 1.03) — `BLOCKED_NO_TESTER`. Host run; settings
  and comparison script shipped.
- **G1** (vote logic, including the whole cross reader) — passing, `asserts=833 mismatches=0`.
- **G2** (host smoke, DIR_LOCK) — pending. Host run.
- **G3** (host smoke, DIR_TRANSLATE) — pending. Host run.

## The cross is the signal

Direction is the cross of the fast line through the slow, not the fill colour. Every
rung reports `crossDir` (persisting until the next cross), `crossAge` in that rung's own
bars, `crossSep`, `sepNow` and the carried sign, and grades its vote `EARLY` / `FRESH` /
`STALE_STATE`. Ties inherit the carried sign — a touch is not a cross — and detection is
on closed bars only. Full rules in §1 of the report.

**Read the FINDING in §1 before tuning anything:** at the shipped defaults this ladder's
direction output is identical to a pure-colour ladder. `InpDirRequireFreshS1 = true` is
the switch that makes the cross decide something.

## Open questions for the owner

1. **`XPDIR_POLARITY`** — the cross up is taken as BUY. In the map, with its default
   `invertFill = true`, that is the cross **into the panel's RED fill**; the LIME fill
   is `fast < slow`. If "the green line" meant LIME, every trade is backwards. One sign
   in `XPDir_Sign`; nothing else moves.
2. **`InpDirEarlySepMult = 2.0`** — EQUIVALENT-ASSUMED. Answer it from the Gate 2/3 CSV
   (`c1_cross_sep` vs `c1_sep_now`), not from a guess.
3. **`InpDirRequireFreshS1 = false`** — see the FINDING above.
4. `InpDirS1RequiredAgainstParent = true` — the owner's two statements about S1
   contradict each other; this default encodes one of them.

## Map contract

`XPMap_ShapeMap_v0.4.zip` (sha256 `5653130d…b52120`) is byte-identical to the
repository's `XPMap/XPW_ShapeMap_v0.4.mq5` at commit `579cb33`. Buffer map: `1 FAST`,
`2 SLOW`, `22 STATE`, `23 RUNLEN`, `EMPTY_VALUE` = na; 30 inputs bound positionally in
declaration order. The 37-line `XPW_ShapeMap_v0.4.mq5` attached to the original prompt
is a stub with a **different** buffer map and was not used. The build re-checks the
contract at runtime per rung (`XPDIR BUF_CONTRACT`).

## Standing caveat

The ladder's direction is only as good as the map, and the map's Gate B (TradingView
export diff) and Gate C (mapdump diff) are still open. That is the host's to close.

## Do not

Modify `XPMap/XPW_ShapeMap_v0.4.mq5` — if it needs a change, name it as a defect.
Retune any of its 27 detector inputs. Read `STATE`/`isRedNow` for direction — it honours
`invertFill` and it is colour, not signal. Read the forming bar. Add pending order types
(`PHASE_3_PENDING_TYPES` is named and stopped in the report). Touch the EA's gates,
hold, money management, trailing, CP filter or observers.
