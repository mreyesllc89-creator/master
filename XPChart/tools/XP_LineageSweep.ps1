<#
.SYNOPSIS
  XP_LineageSweep.ps1 - P3 lineage sweep.  READ-ONLY (R1).  Greps both trees and every MQL5\Services
  folder for the v1 patterns and classifies each file.  Output: <OutDir>\lineage_sweep.csv + .md

.PATTERNS
  P1 SymbolInfoTick polling      SymbolInfoTick( ... together with Sleep( in the same file
  P2 tick_volume hardcoded       tick_volume = 1;
  P3 StringFind first-match      StringFind(...) >= 0   (substring anywhere, first hit)
  P4 TimeCurrent bar anchoring   TimeCurrent() /  or  = (TimeCurrent()  or  = TimeCurrent();  or  bar_time = ... TimeCurrent
  P5 unchecked Custom* returns   a statement that STARTS with CustomRatesUpdate( / CustomTicksAdd( / CustomTicksReplace( ...
  Named suspects: XPW_MT5_Tick_Publisher, ContinuousCopyTicksRecorder, *Recorder*, *Observer*, *Publisher*
  Class: CHARTENGINE_CLONE (P1+P4+P5 all present -> identical fix applies as a v2 sibling),
         PARTIAL (some patterns -> report line only), CLEAN
#>
param(
  [string[]]$Roots = @("$env:USERPROFILE\Documents\Codex", "$env:USERPROFILE\Documents\TradingSystems"),
  [string[]]$TerminalRoots = @("$env:APPDATA\MetaQuotes\Terminal", "C:\Program Files", "C:\Program Files (x86)", "C:\MT5", "D:\"),
  [string]$OutDir = "",
  [int]$MaxDepth = 8
)
$ErrorActionPreference = 'Continue'
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PSScriptRoot 'out' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

function Read-TextSafe([string]$path) {
  try {
    $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try { $sr = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true); return $sr.ReadToEnd() } finally { $fs.Dispose() }
  } catch { return $null }
}

$patterns = [ordered]@{
  'P1_SymbolInfoTick'   = 'SymbolInfoTick\s*\('
  'P1b_Sleep'           = '\bSleep\s*\('
  'P2_tick_volume_1'    = 'tick_volume\s*=\s*1\s*;'
  'P3_StringFind_first' = 'StringFind\s*\([^;]*\)\s*>=\s*0'
  'P4_TimeCurrent_anchor' = '(TimeCurrent\s*\(\s*\)\s*/)|(=\s*\(\s*TimeCurrent\s*\(\s*\))|(=\s*TimeCurrent\s*\(\s*\)\s*;)|(bar_time\s*=.*TimeCurrent)'
  'P5_unchecked_Custom' = '^\s*Custom(RatesUpdate|RatesReplace|TicksAdd|TicksReplace|SymbolSetInteger|SymbolSetDouble|SymbolSetString)\s*\('
}
$suspectRx = 'XPW_MT5_Tick_Publisher|ContinuousCopyTicksRecorder|Recorder|Observer|Publisher'

$roots = @($Roots)
foreach ($r in $TerminalRoots) {
  if (-not (Test-Path -LiteralPath $r)) { continue }
  $roots += Get-ChildItem -LiteralPath $r -Directory -Recurse -Depth $MaxDepth -Filter 'Services' -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like '*\MQL5\Services' } | Select-Object -ExpandProperty FullName
}
$roots = $roots | Sort-Object -Unique

$files = @()
foreach ($r in $roots) {
  if (-not (Test-Path -LiteralPath $r)) { Write-Host "[sweep] missing root: $r"; continue }
  $files += Get-ChildItem -LiteralPath $r -Recurse -File -Depth $MaxDepth -Include *.mq5,*.mqh,*.mq4 -ErrorAction SilentlyContinue
}
$files = $files | Sort-Object FullName -Unique
Write-Host "[sweep] roots=$($roots.Count) source files=$($files.Count)"

$rows = @()
$summary = @()
foreach ($f in $files) {
  $txt = Read-TextSafe $f.FullName
  if ($null -eq $txt) { continue }
  $lines = $txt -replace "`r`n", "`n" -split "`n"
  $hits = @{}
  foreach ($k in $patterns.Keys) {
    $rx = [regex]$patterns[$k]
    for ($i = 0; $i -lt $lines.Count; $i++) {
      if ($rx.IsMatch($lines[$i])) {
        if (-not $hits.ContainsKey($k)) { $hits[$k] = @() }
        $hits[$k] += ($i + 1)
        $rows += [pscustomobject]@{ Path = $f.FullName; Line = ($i + 1); Pattern = $k; Text = $lines[$i].Trim(); Suspect = ($f.Name -match $suspectRx) }
      }
    }
  }
  # P1 = SymbolInfoTick( inside a polling loop: a while( within the 40 lines before it and a Sleep( within the 60 lines after it
  $hasP1 = $false
  if ($hits.ContainsKey('P1_SymbolInfoTick')) {
    foreach ($ln in $hits['P1_SymbolInfoTick']) {
      $i = $ln - 1
      $before = $lines[[Math]::Max(0, $i - 40)..$i] -join "`n"
      $after  = $lines[$i..[Math]::Min($lines.Count - 1, $i + 60)] -join "`n"
      if ($before -match 'while\s*\(' -and $after -match '\bSleep\s*\(') { $hasP1 = $true }
    }
  }
  $hasP4 = $hits.ContainsKey('P4_TimeCurrent_anchor')
  $hasP5 = $hits.ContainsKey('P5_unchecked_Custom')
  $class = if ($hasP1 -and $hasP4 -and $hasP5) { 'CHARTENGINE_CLONE' } elseif ($hits.Count -gt 0) { 'PARTIAL' } else { 'CLEAN' }
  if ($class -ne 'CLEAN' -or ($f.Name -match $suspectRx)) {
    $summary += [pscustomobject]@{ Path = $f.FullName; Class = $class; Suspect = ($f.Name -match $suspectRx); Patterns = (($hits.Keys | Sort-Object) -join ' ') }
  }
}
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OutDir 'lineage_sweep.csv')
$md = @("# Lineage sweep - $stamp", "", "Roots: $($roots -join '; ')", "Files scanned: $($files.Count)", "",
        "| file | class | named suspect | patterns |", "|---|---|---|---|")
foreach ($s in ($summary | Sort-Object Class, Path)) { $md += "| ``$($s.Path)`` | $($s.Class) | $($s.Suspect) | $($s.Patterns) |" }
$md += ""; $md += "Proposed fix per pattern: P1 -> CopyTicks cursor (v2 F1); P2 -> count ticks (F3); P3 -> deterministic candidates (F6); P4 -> tick.time_msc slot (F2); P5 -> check return + GetLastError + rate-limited print + fail limit (F8)."
$md += "CHARTENGINE_CLONE files get the identical v2 loop as a sibling file; PARTIAL files are report-only (path, line, pattern in lineage_sweep.csv)."
$md | Set-Content -Encoding UTF8 (Join-Path $OutDir 'lineage_sweep.md')
Write-Host "[sweep] flagged files: $($summary.Count)  rows: $($rows.Count)  -> $OutDir"
