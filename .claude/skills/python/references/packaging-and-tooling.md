# Packaging and tooling

## Minimal pyproject.toml (src layout)
```toml
[project]
name = "tdi-tools"
version = "0.1.0"
description = "Indicators and backtests for the TDI / FlashGold strategies"
requires-python = ">=3.11"
dependencies = ["pandas>=2.2", "numpy>=1.26"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.5", "mypy>=1.10"]
mt5 = ["MetaTrader5>=5.0.45"]   # Windows only

[project.scripts]
tdi-backtest = "tdi_tools.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "RUF"]
```

## Environments
- `uv` when available (fast, lockfile): `uv venv && source .venv/bin/activate`,
  `uv pip install -e ".[dev]"`, `uv lock`, `uv run pytest`.
- Plain tooling: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`.
- Pin for reproducibility in `requirements.txt` or `uv.lock`; never commit `.venv/`.
- Windows (MetaTrader machines): `py -3.11 -m venv .venv` then `.venv\Scripts\activate`.
  The `MetaTrader5` package only installs on Windows; guard imports with
  `sys.platform == "win32"` and make the dependency optional.

## Entry points and CLIs
- `argparse` for the stdlib; `typer` when there are many subcommands and you want
  help text for free. Either way, the CLI module only parses and prints; logic lives in
  a library module that tests import directly.
- Expose `main() -> int` and register it in `[project.scripts]`.

## Quality gates (put in CI or a Makefile)
```bash
ruff check . && ruff format --check .
mypy src
python -m pytest -q
```

## Notebooks
Keep notebooks for exploration only. Move anything reused into `src/` and import it. Clear
outputs before committing (`nbstripout`) so diffs stay readable.

## Versioning and releases
- Semantic versioning; bump in `pyproject.toml` only.
- `python -m build` produces wheel + sdist; `twine upload` or an internal index.
- Changelog entry per release with the behaviour change, not the file list.
