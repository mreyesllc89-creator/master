---
name: python
description: Modern Python (3.11+) engineering reference - style, typing, project layout, packaging with pyproject/uv, pytest, ruff, CLI tools, async, error handling, data work with pandas/numpy, and automation scripts. Use this whenever the user asks to write, fix, review, refactor, test, or package ANY Python code or .py file, even a "quick script", a notebook cell, a one-off data clean-up, or a helper for the trading strategies in this repo. For indicators, backtests, or MetaTrader 5 from Python, also load the python-trading skill.
---

# Python

Write Python the way a careful senior engineer on a small team would: readable first,
typed, tested where it matters, and runnable with one command. The references below
hold the detail; read the one that matches the job.

| Job | Read |
|-----|------|
| Style, typing, idioms, error handling | `references/style-and-typing.md` |
| Tests with pytest (fixtures, parametrize, tmp_path, mocking) | `references/testing.md` |
| New project, pyproject.toml, uv/pip, ruff, entry points | `references/packaging-and-tooling.md` |
| pandas / numpy / time series / CSV / Parquet | `references/data-analysis.md` |
| CLI scripts, files, subprocess, scheduling, logging | `references/automation-scripts.md` |

## Defaults that save rework

- **Target Python 3.11+** unless the repo pins otherwise. Use `match`, `X | None`,
  `list[str]`, `dataclasses`, `pathlib`, f-strings, `zoneinfo`. Check with
  `python3 --version` before using 3.12-only syntax (PEP 695 generics, f-string nesting).
- **One file script** → add a `main()` guarded by `if __name__ == "__main__":`, take
  arguments with `argparse`, print progress to stderr via `logging`, return an exit code.
- **More than one file** → a package in `src/<name>/`, a `pyproject.toml`, `tests/`.
  Read the packaging reference before inventing a layout.
- **Dependencies**: prefer the standard library. When a third-party package is the right
  tool (pandas, numpy, requests, httpx, pydantic, typer), declare it in `pyproject.toml`
  and install with `uv pip install` or `pip install`; never import something you did not
  declare.
- **Run what you write.** Execute the script or `pytest -q` before reporting. If the
  environment lacks a package or network, say so with the exact error instead of
  guessing the result.
- **Never shadow stdlib names** (`json.py`, `test.py`, `types.py`) in a directory the
  interpreter searches. When a script reads untrusted downloaded files, run it with
  `python -I` from a different directory.

## Code shape

```python
"""One-line purpose. Longer notes if needed."""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Config:
    source: Path
    dry_run: bool = False


def run(cfg: Config) -> int:
    """Do the work; return a process exit code."""
    if not cfg.source.exists():
        log.error("missing %s", cfg.source)
        return 2
    ...
    return 0


def parse_args(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    return Config(source=a.source, dry_run=a.dry_run)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
```

Why this shape: `run()` is testable without touching argv or the filesystem layout,
logging goes to stderr so stdout stays usable in pipes, and the exit code tells a shell
script whether it worked.

## Reviewing or fixing existing Python

1. Reproduce the failure first (`python -m pytest tests/test_x.py -q -x` or run the
   script with the user's input). Quote the traceback.
2. Fix the cause, not the symptom. A bare `except:` that hides the error is not a fix.
3. Add or extend a test that fails before and passes after.
4. Run `ruff check . && ruff format --check .` if ruff is configured; otherwise do not
   reformat unrelated lines, it buries the real diff.

## Things that bite

- Mutable default arguments (`def f(x=[])`), late-binding closures in loops, and
  `is` vs `==` for strings and numbers.
- Floating point: compare with `math.isclose`, round money with `decimal.Decimal`.
- Timezones: store UTC, convert at the edge with `zoneinfo.ZoneInfo`. Naive datetimes
  are a bug waiting to happen in trading data (broker server time vs exchange time).
- `pandas` chained assignment and `SettingWithCopyWarning`: use `.loc[...] = ...` or
  `.assign()`; the data-analysis reference covers the modern copy-on-write behaviour.
- Blocking I/O inside `async def`; use `asyncio.to_thread` or an async client.
- Reading a large CSV with default dtypes doubles memory; pass `dtype=` and `usecols=`.
