# Automation and scripting in Python

## When Python beats shell
Anything with parsing, dates, JSON, retries, or more than ~30 lines. Shell stays for
glue (`cd`, pipes, calling CLIs). Mixed jobs: Python calls the CLI via `subprocess`.

## subprocess
```python
import subprocess, shlex
r = subprocess.run(["metaeditor64.exe", "/compile:C:/path/EA.mq5", "/log"],
                   capture_output=True, text=True, timeout=120, check=False)
if r.returncode not in (0, 1):   # MetaEditor returns the number of compiled files
    raise RuntimeError(r.stderr or r.stdout)
```
- Always a list of arguments, never `shell=True` with user input.
- `check=True` when non-zero is an error; `timeout=` always.
- `text=True, encoding="utf-8", errors="replace"` for logs that may contain odd bytes.
  MetaEditor log files are UTF-16 LE: `Path(log).read_text(encoding="utf-16")`.

## Files and paths
- `Path.home() / "AppData/Roaming/MetaQuotes/Terminal"` on Windows; find the terminal data
  folder by globbing for `*/MQL5/Experts`.
- Atomic writes: write to `path.with_suffix(".tmp")` then `os.replace(tmp, path)`.
- Watch a folder: poll `stat().st_mtime` every few seconds, or `watchdog` if installed.

## Config and secrets
- Config in `pyproject.toml` `[tool.x]`, a `config.toml` (`tomllib` is stdlib), or env vars.
- Secrets (broker login, API keys) only from env vars or an OS keyring; never in the repo
  or in log output. Mask them when printing config.

## Logging
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler("run.log", encoding="utf-8")],
)
```
Use `log.info("filled %s at %.2f", side, price)` with lazy formatting. `log.exception` in
`except` blocks keeps the traceback.

## Scheduling and long-running loops
- One-shot jobs: cron / Windows Task Scheduler calling the script; the script exits non-zero
  on failure so the scheduler can alert.
- Polling loops (e.g. watching an MT5 account): `while True: ...; time.sleep(interval)`,
  catch and log exceptions per iteration, handle `KeyboardInterrupt` for a clean stop, and
  reconnect on failures with exponential backoff.
- `signal.signal(signal.SIGTERM, handler)` to flush state on shutdown (Linux).

## HTTP
- `httpx` (sync and async, timeouts by default) or `requests`. Set `timeout=10`, retry
  idempotent GETs with backoff (`tenacity` or a small loop), and validate JSON with
  `pydantic` or `TypedDict` before using it.

## Packaging a script for someone else
- Put the usage in the module docstring and let argparse print it (`description=__doc__`).
- `--dry-run` for anything destructive; print the plan, then do it only with the flag off.
- Exit codes: 0 ok, 1 generic failure, 2 bad usage/input. Shell wrappers rely on these.
