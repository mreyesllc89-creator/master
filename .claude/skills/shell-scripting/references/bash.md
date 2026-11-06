# Bash

## Template
```bash
#!/usr/bin/env bash
# Purpose: one line.  Usage: script.sh [-n] [-v] <input-dir>
set -euo pipefail
IFS=$'\n\t'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0; VERBOSE=0

usage() { sed -n '2,3p' "$0" | sed 's/^# //' >&2; exit 2; }
log()   { printf '%s %s\n' "$(date +'%F %T')" "$*" >&2; }
die()   { log "ERROR: $*"; exit 1; }

while getopts ':nvh' opt; do
  case "$opt" in
    n) DRY_RUN=1 ;;
    v) VERBOSE=1 ;;
    h|*) usage ;;
  esac
done
shift $((OPTIND - 1))
[[ $# -eq 1 ]] || usage
INPUT="$1"; [[ -d "$INPUT" ]] || die "not a directory: $INPUT"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

run() { if (( DRY_RUN )); then log "would: $*"; else "$@"; fi; }

main() {
  local f
  while IFS= read -r -d '' f; do
    run cp -- "$f" "$TMP/"
  done < <(find "$INPUT" -type f -name '*.pine' -print0)
  log "done"
}
main "$@"
```

## Safety idioms
- `set -e` stops on error, `-u` on unset variables, `-o pipefail` on any failed pipe
  stage. Expected non-zero (e.g. `grep` with no match): `grep ... || true` with a comment,
  or `if grep -q ...; then`.
- `"${VAR:?message}"` aborts if empty; essential before `rm -rf "$VAR/..."`.
- `--` before file arguments so names starting with `-` are not options.
- `find ... -print0 | while IFS= read -r -d '' f` for arbitrary filenames; never `for f in $(ls)`.
- `mktemp`, `trap cleanup EXIT INT TERM`.
- Lock a cron job against overlap: `exec 9>"/tmp/$(basename "$0").lock"; flock -n 9 || exit 0`.
- Prefer `[[ ]]` (no word splitting, pattern matching `==` with globs, `=~` regex).
- Arithmetic: `(( i++ ))`, `$(( a * b ))`; floats need `awk` or `bc`.

## Arrays and strings
```bash
files=(*.pine); echo "${#files[@]}"; for f in "${files[@]}"; do ...; done
declare -A map=([btc]=BTCUSD [gold]=XAUUSD); echo "${map[gold]}"; for k in "${!map[@]}"; do ...; done
name="${path##*/}"; stem="${name%.*}"; ext="${name##*.}"; dir="${path%/*}"
upper="${var^^}"; lower="${var,,}"; replaced="${var//old/new}"
IFS=',' read -r -a parts <<< "$csvline"
```

## Text processing
- `grep -E`, `sed -E 's/.../.../'`, `awk -F',' '{print $2}'`, `cut -d, -f2`, `sort -u`,
  `tr -d '\r'`, `paste`, `join`, `comm`. `jq` for JSON, `yq` for YAML.
- Here-doc to write files: `cat > file <<'EOF' ... EOF` (quoted delimiter = no expansion).
- `printf '%s\n' "${arr[@]}"` to print arrays one per line; `printf '%q'` to quote for reuse.

## Processes
- `cmd1 && cmd2`, `cmd || fallback`, `cmd &` + `wait`, `timeout 60 cmd`, `nohup cmd &`.
- Capture: `out="$(cmd)"`, status: `if cmd; then`, both: `if out="$(cmd 2>&1)"; then`.
- Parallel: `xargs -P 4 -n 1 cmd` or GNU `parallel`.
- Retry with backoff:
  ```bash
  retry() { local n=0 max=4 delay=2; until "$@"; do (( ++n >= max )) && return 1; sleep "$delay"; delay=$(( delay * 2 )); done; }
  retry git push -u origin "$BRANCH"
  ```

## Portability
- `#!/bin/sh` scripts: no arrays, no `[[ ]]`, no `local` guarantees, `=` not `==`,
  `$(...)` fine. Test with `dash` or `shellcheck -s sh`.
- macOS ships BSD `sed`/`date` (`sed -i ''`, `date -v`); GNU tools via `gsed`, `gdate`.
- Windows Git Bash: paths `/c/Users/...`; `winpty` for interactive programs; CRLF traps.

## Makefile targets as an interface
```make
.PHONY: test lint compile
test: ; python -m pytest -q
lint: ; ruff check . && shellcheck scripts/*.sh
compile: ; pwsh scripts/compile-ea.ps1 -Source Experts/FlashGold_v5.mq5
```
Tabs, not spaces, under targets.
