# Style, typing, idioms, errors

## Formatting and linting
- `ruff` does both lint and format (`ruff check --fix . && ruff format .`). Configure in
  `pyproject.toml` under `[tool.ruff]`: `line-length = 100`, `target-version = "py311"`,
  `[tool.ruff.lint] select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]`.
- Imports: stdlib, third-party, local, separated by blank lines; ruff's `I` rule sorts them.
- Names: `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants,
  `_private` for module internals. Avoid single letters outside comprehensions and maths.

## Typing
- Annotate public functions. Use builtin generics (`list[int]`, `dict[str, float]`),
  `X | None`, `collections.abc` for `Iterable`, `Sequence`, `Mapping`, `Callable`.
- `from __future__ import annotations` keeps annotations lazy and lets you reference
  classes defined later.
- Prefer `Protocol` for duck typing over inheritance; `TypedDict` for JSON-shaped dicts;
  `Literal["buy", "sell"]` for small fixed vocabularies; `enum.StrEnum` when the values
  also need behaviour.
- `@dataclass(frozen=True, slots=True)` for value objects. `pydantic.BaseModel` when you
  need validation of external input (config files, API payloads).
- Check with `mypy --strict` or `pyright`; fix the types, do not sprinkle `# type: ignore`.
- `typing.Any` is a last resort; `object` plus `isinstance` narrowing is usually what you mean.

## Idioms
- Comprehensions for simple transforms; a `for` loop once there is a condition plus a
  side effect. Generators (`yield`) for streams larger than memory.
- `pathlib.Path` for every filesystem path; `Path.read_text()`, `.write_text()`,
  `.glob()`, `/` to join.
- `with open(...)` always; `encoding="utf-8"` always.
- `enumerate`, `zip(strict=True)`, `itertools.pairwise`, `functools.cache`,
  `contextlib.suppress`, `operator.attrgetter` instead of hand-rolled versions.
- Unpacking and `match` for structured data:

```python
match order:
    case {"type": "stop", "side": "buy", "price": float(p)}:
        ...
    case {"type": "market", **rest}:
        ...
    case _:
        raise ValueError(f"unknown order {order!r}")
```

- Prefer returning values over mutating arguments. If a function mutates, say so in the
  name (`append_row`, `update_in_place`).

## Errors
- Raise specific exceptions; define a small hierarchy per package
  (`class BrokerError(Exception)`, `class RejectedOrder(BrokerError)`).
- Catch only what you can handle, as close to the source as sensible. Re-raise with
  context: `raise ConfigError("bad interval") from exc`.
- Never `except Exception: pass`. If you must continue, log with `log.exception(...)`.
- Validate at the boundary (CLI args, file contents, API responses) and trust internal
  code afterwards. Use `assert` for programmer invariants only; `python -O` strips them.
- Return early on bad input; keep the happy path at the lowest indentation.

## Docstrings and comments
- One-line docstring stating what the function returns or does; parameters only when
  their meaning is not obvious from the type and name.
- Comments explain *why* (a workaround, a domain rule, a calibration), not *what* the
  next line does. In trading code, cite the rule: `# Wilder RSI: seed with SMA, then RMA`.

## Concurrency
- I/O bound → `asyncio` with `httpx.AsyncClient` or `aiohttp`; CPU bound →
  `concurrent.futures.ProcessPoolExecutor`; mixed → `asyncio.to_thread`.
- `threading` only for simple background work with a `queue.Queue`. Remember the GIL.
- Always put a timeout on network calls and `await asyncio.wait_for(...)`.
