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
| `reference/fixtures/vote_rules.csv` | 31 hand-derived fixtures. |
| `reference/emu/` | Lifts `XPDIR_RULE_CORE_BEGIN…END` out of the `.mq5`, translates it to C++, compiles and runs it (the `XPMap/reference/emu/` approach). |
| `reference/compare_trades.py` | **Gate 0** trade-list comparison of two MT5 tester HTML reports. |
| `reference/gate0_tester_settings.ini` | Gate 0 tester settings (real ticks, fixed window). |
| `reference/ea_1.03_to_1.05_xpdir.diff` | The complete machine diff, 1.03 → 1.05-XPDIR (+765 / −7). |

## Reproduce Gate 1 (needs only python3 and g++)

```bash
cd XPDirection/reference && python3 run_fixtures.py
# stub lint: 0 errors 0 warnings
# fixtures=31 asserts=403 mismatches=0 emu=on
```

`--no-emu` skips the compile step and runs the Python reference against the fixtures
alone. A run with `asserts=0` is a failure, not a pass.

## State of the gates

- **G0** (DIR_OFF is trade-for-trade 1.03) — `BLOCKED_NO_TESTER`. Host run; settings
  and comparison script shipped.
- **G1** (vote logic) — passing, `asserts=403 mismatches=0`.
- **G2** (host smoke, DIR_LOCK) — pending. Host run.
- **G3** (host smoke, DIR_TRANSLATE) — pending. Host run.

## Open questions for the owner

1. **`XPDIR_POLARITY`** — the prompt defines the bullish vote as "fast above slow". In
   the map, with its default `invertFill = true`, that state renders **RED** on the
   panel and the LIME fill is `fast < slow`. If "the green line" meant LIME, every
   trade is backwards. One-line fix in `XPDir_RungVote`; nothing else moves.
2. `InpDirS1RequiredAgainstParent = true` — the owner's two statements about S1
   contradict each other; this default encodes one of them.
3. `InpDirMaxRunLenBars = 0` (off) — "just at the beginning of the green line" needs a
   number.

## Standing caveat

The ladder's direction is only as good as the map, and the map's Gate B (TradingView
export diff) and Gate C (mapdump diff) are still open. That is the host's to close.

## Do not

Modify `XPMap/XPW_ShapeMap_v0.4.mq5` — if it needs a change, name it as a defect.
Retune any of its 27 detector inputs. Add pending order types (`PHASE_3_PENDING_TYPES`
is named and stopped in the report). Touch the EA's gates, hold, money management,
trailing, CP filter or observers.
