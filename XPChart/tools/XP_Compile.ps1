<#
.SYNOPSIS
  XP_Compile.ps1 - P2 compile with metaeditor64.exe /compile.  Launches ONLY metaeditor64.exe (never terminal64.exe).

.DESCRIPTION
  Finds metaeditor64.exe (-MetaEditor, else out\compilers.csv from XP_Census.ps1, else Program Files search),
  compiles each source in place, parses the UTF-16 log, prints "Result: N errors, M warnings" per file and
  copies the .ex5 next to the source into <OutDir>\build\.  Nothing is copied into any terminal.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\XP_Compile.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\XP_Compile.ps1 -MetaEditor 'C:\Program Files\MetaTrader 5\metaeditor64.exe'
#>
param(
  [string]$MetaEditor = "",
  [string[]]$Sources = @((Join-Path $PSScriptRoot '..\XP ChartEngine v2.mq5'), (Join-Path $PSScriptRoot '..\XP_AxisCheck.mq5')),
  [string]$OutDir = ""
)
$ErrorActionPreference = 'Continue'
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PSScriptRoot 'out' }
$build = Join-Path $OutDir 'build'
New-Item -ItemType Directory -Force -Path $build | Out-Null

$searched = @()
if ([string]::IsNullOrWhiteSpace($MetaEditor)) {
  $csv = Join-Path $OutDir 'compilers.csv'
  if (Test-Path -LiteralPath $csv) {
    $searched += $csv
    $c = Import-Csv $csv | Sort-Object Version -Descending | Select-Object -First 1
    if ($c) { $MetaEditor = $c.Path }
  }
}
if ([string]::IsNullOrWhiteSpace($MetaEditor)) {
  foreach ($r in @("$env:ProgramFiles", "${env:ProgramFiles(x86)}", "C:\MT5", "D:\")) {
    if (-not (Test-Path -LiteralPath $r)) { continue }
    $searched += $r
    $hit = Get-ChildItem -LiteralPath $r -Recurse -Depth 4 -File -Filter 'metaeditor64.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { $MetaEditor = $hit.FullName; break }
  }
}
if ([string]::IsNullOrWhiteSpace($MetaEditor) -or -not (Test-Path -LiteralPath $MetaEditor)) {
  Write-Host "BLOCKED_NO_COMPILER: metaeditor64.exe not found. Searched: $($searched -join '; ')"
  exit 2
}
Write-Host "[compile] using $MetaEditor"

$total_err = 0
foreach ($src in $Sources) {
  $src = (Resolve-Path -LiteralPath $src).Path
  $log = [System.IO.Path]::ChangeExtension($src, '.log')
  if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }   # our own previous log, outside MQL5\Files
  $p = Start-Process -FilePath $MetaEditor -ArgumentList @("/compile:`"$src`"", "/log:`"$log`"") -Wait -PassThru
  $txt = if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Raw -Encoding Unicode } else { '' }
  $result = ([regex]::Matches($txt, 'Result:.*') | Select-Object -Last 1).Value
  $errors = ([regex]::Match($result, '(\d+) error')).Groups[1].Value
  $warnings = ([regex]::Match($result, '(\d+) warning')).Groups[1].Value
  Write-Host "[compile] $([System.IO.Path]::GetFileName($src)) exit=$($p.ExitCode) $result"
  $txt -split "`n" | Where-Object { $_ -match 'error|warning' } | ForEach-Object { Write-Host "    $($_.Trim())" }
  if ($errors -and [int]$errors -gt 0) { $total_err += [int]$errors }
  $ex5 = [System.IO.Path]::ChangeExtension($src, '.ex5')
  if (Test-Path -LiteralPath $ex5) { Copy-Item -LiteralPath $ex5 -Destination $build -Force; Write-Host "    -> $build\$([System.IO.Path]::GetFileName($ex5))" }
  if (Test-Path -LiteralPath $log) { Copy-Item -LiteralPath $log -Destination $build -Force }
}
if ($total_err -gt 0) { Write-Host "[compile] FAILED with $total_err error(s)"; exit 1 }
Write-Host "[compile] OK - deploy by copying the .ex5 from $build into <SMOKE_TERMINAL data>\MQL5\Services\ (Ghost, by hand; R5)"
