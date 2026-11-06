# PowerShell and cmd on Windows

## PowerShell template (pwsh 7 or Windows PowerShell 5.1)
```powershell
<#
.SYNOPSIS  Compile an MQL5 file and report errors.
.EXAMPLE   .\compile-ea.ps1 -Source "C:\...\MQL5\Experts\FlashGold\FlashGold_v5.mq5"
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)] [string] $Source,
    [string] $MetaEditor = 'C:\Program Files\MetaTrader 5\metaeditor64.exe',
    [switch] $Quiet
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log([string] $Message) { if (-not $Quiet) { Write-Host ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message) } }

if (-not (Test-Path -LiteralPath $Source))     { throw "Source not found: $Source" }
if (-not (Test-Path -LiteralPath $MetaEditor)) { throw "MetaEditor not found: $MetaEditor" }

$log = [IO.Path]::ChangeExtension($Source, '.log')
if ($PSCmdlet.ShouldProcess($Source, 'Compile')) {
    & $MetaEditor "/compile:$Source" "/log:$log" | Out-Null
    # MetaEditor's exit code is the number of files compiled (1) and is NOT an error signal; read the log
    $text = Get-Content -LiteralPath $log -Encoding Unicode -Raw
    $errors = ($text -split "`r?`n") | Where-Object { $_ -match ' : error ' }
    if ($errors) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }
    Write-Log "compiled OK: $([IO.Path]::ChangeExtension($Source, '.ex5'))"
}
```
- `-LiteralPath` avoids wildcard surprises in paths with `[ ]`.
- Native executables do not throw: check `$LASTEXITCODE` (or the tool's log).
- `& "$exe" args` runs a program; `Start-Process -Wait -PassThru` when you need the
  process object or a different working directory.
- Strings: `"$var"` expands, `'literal'` does not; `"${var}text"`; `-f` formatting.
- Encodings: MetaEditor/terminal logs are UTF-16 LE (`-Encoding Unicode`); `.set` and
  `.ini` files are UTF-16 LE too in recent builds (check with `Format-Hex | Select -First 1`).
  Write them with `Set-Content -Encoding Unicode`.
- Paths: `Join-Path $env:APPDATA 'MetaQuotes\Terminal'`, `Resolve-Path`, `Split-Path -Leaf`.
- Arrays `@()`, hashtables `@{}`, `ForEach-Object`, `Where-Object`, `Select-Object`,
  `Sort-Object`, `Group-Object`, `Measure-Object`; objects flow through the pipeline, so
  `Import-Csv`/`Export-Csv -NoTypeInformation`, `ConvertFrom-Json`.
- Execution policy: run scripts with `pwsh -NoProfile -ExecutionPolicy Bypass -File x.ps1`
  from schedulers.

## Task Scheduler
```powershell
$action  = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\bots\nightly-backtest.ps1"'
$trigger = New-ScheduledTaskTrigger -Daily -At 02:15
Register-ScheduledTask -TaskName 'MT5 nightly backtest' -Action $action -Trigger $trigger -RunLevel Highest -User $env:USERNAME
```
Or `schtasks /Create /SC DAILY /ST 02:15 /TN "..." /TR "..."`. Log to a file; the
scheduler only records the exit code.

## cmd / .bat
```bat
@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "ME=C:\Program Files\MetaTrader 5\metaeditor64.exe"
set "SRC=%~1"
if "%SRC%"=="" ( echo usage: %~nx0 file.mq5 & exit /b 2 )
"%ME%" /compile:"%SRC%" /log
findstr /C:" : error " "%SRC:.mq5=.log%" >nul && ( echo compile errors & exit /b 1 )
echo ok
endlocal
```
`%~dp0` = script directory; `%~1` strips quotes; `exit /b N` sets the code without
closing the window. Prefer PowerShell for anything beyond a few lines.

## WSL / Git Bash interop
- From bash: `powershell.exe -NoProfile -Command "..."`, paths via `wslpath -w /mnt/c/...`.
- From PowerShell: `wsl bash -lc "..."`.
- Line endings: `git config core.autocrlf` or `.gitattributes` (`*.sh text eol=lf`,
  `*.ps1 text eol=crlf`, `*.mq5 text eol=crlf`).
