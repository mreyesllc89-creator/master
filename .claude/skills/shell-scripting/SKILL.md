---
name: shell-scripting
description: Shell and automation scripting reference - robust Bash (set -euo pipefail, quoting, arrays, traps, getopts, shellcheck), POSIX sh portability, PowerShell and .bat/.cmd on Windows, cron and Task Scheduler jobs, and MetaTrader 5 automation from the command line (metaeditor64.exe /compile, terminal64.exe /config tester runs, locating the MQL5 data folder, deploying .ex5 files, reading UTF-16 logs). Use this whenever the user asks for a script, a one-liner, a Makefile target, a build/deploy/backup/cron job, "automate this", batch processing of files, or anything to be run in a terminal on Linux, macOS or Windows, including compiling or testing MQL5 EAs from the shell.
---

# Shell scripting

Shell is the glue: start processes, move files, chain CLIs. Once a script needs parsing,
dates, retries or more than ~50 lines, switch to Python (the `python` skill has the
automation reference). Pick the dialect from the target machine, not from habit:
MetaTrader 5 runs on Windows, so EA automation is PowerShell or `.cmd`.

| Need | Read |
|------|------|
| Bash patterns, safety, arrays, traps, argument parsing, portability | `references/bash.md` |
| PowerShell and cmd on Windows, Task Scheduler, paths, encodings | `references/powershell-windows.md` |
| MetaTrader 5: compile, deploy, headless tester runs, logs, data folder | `references/mt5-cli.md` |

## Defaults

- **Bash**: start every script with
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  IFS=$'\n\t'
  ```
  quote every expansion (`"$var"`, `"${arr[@]}"`), use `[[ ]]`, `$(...)`, `printf` over
  `echo` for data, and run `shellcheck script.sh` before handing it over.
- **PowerShell**: `Set-StrictMode -Version Latest; $ErrorActionPreference = 'Stop'`,
  `[CmdletBinding()] param(...)`, `Join-Path`, `-LiteralPath`, and `$LASTEXITCODE` after
  native executables.
- **Idempotent and dry-runnable**: a `--dry-run`/`-WhatIf` path that prints the plan.
  Scripts that delete or overwrite check the target first (`ls`, `Test-Path`) and refuse
  on surprises.
- **Exit codes** mean something: 0 ok, 1 failure, 2 usage. Print errors to stderr.
- **Logs**: timestamped lines, one per action, to stdout for cron to capture or to a file
  in the script's own folder; never swallow a failure with `|| true` unless the comment
  says why.
- **Secrets** come from environment variables or a credential store, never from the
  script body or command line (visible in `ps` and shell history).

## Review checklist for a script someone hands you
1. Unquoted variables, `for f in $(ls)`, word splitting on paths with spaces.
2. `cd` without checking, relative paths that depend on the caller's directory
   (`cd "$(dirname "$0")"` or use absolute paths from a `ROOT` variable).
3. `rm -rf "$DIR/"` where `DIR` can be empty → `rm -rf /`. Use `"${DIR:?}"`.
4. Pipelines that hide failures (`set -o pipefail`), `grep` returning 1 on no match
   under `set -e`.
5. Temp files without `mktemp` and a `trap ... EXIT` cleanup.
6. Windows line endings in a bash script (`file script.sh`, `dos2unix`).
