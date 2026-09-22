<#
.SYNOPSIS
  XP_Census.ps1 - P0.1 source census, P0.4 deployment map, P2 compiler census.  READ-ONLY (R1).

.DESCRIPTION
  Never writes inside any MQL5 folder, never opens bases\Custom\history, never touches a terminal
  process.  Log files are opened with FileShare ReadWrite|Delete so running terminals are not
  disturbed.  All output goes to -OutDir (default: <script dir>\out).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\XP_Census.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File .\XP_Census.ps1 -TerminalRoots 'D:\MT5' -MaxDepth 6
#>
param(
  [string[]]$Roots = @("$env:USERPROFILE\Documents\Codex", "$env:USERPROFILE\Documents\TradingSystems"),
  [string[]]$TerminalRoots = @("$env:APPDATA\MetaQuotes\Terminal", "C:\Program Files", "C:\Program Files (x86)", "C:\MT5", "D:\"),
  [string]$OutDir = "",
  [string]$BaseHash = "ddad0226f8d85be1010a452c6b1cb0d943cc70ddd5d63b695b1cee88c55fd9e0",
  [int]$MaxDepth = 8
)

$ErrorActionPreference = 'Continue'
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $PSScriptRoot 'out' }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

function Read-TextSafe([string]$path) {
  # read-only, shared open; handles UTF-8 BOM, UTF-16 LE/BE BOM, else UTF-8
  try {
    $fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
          ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try {
      $sr = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true)
      return $sr.ReadToEnd()
    } finally { $fs.Dispose() }
  } catch { return $null }
}

function Get-RawHash([string]$path) {
  try { return (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLower() } catch { return 'ERR' }
}

function Get-NormHash([string]$path) {
  # CRLF->LF, BOM stripped, UTF-8 re-encoded => comparable with the LF copy in the repo
  $txt = Read-TextSafe $path
  if ($null -eq $txt) { return 'ERR' }
  $txt = $txt -replace "`r`n", "`n"
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($txt)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  return ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLower()
}

function Find-Dirs([string[]]$roots, [string]$leaf, [string]$mustContain) {
  $found = @()
  foreach ($r in $roots) {
    if (-not (Test-Path -LiteralPath $r)) { continue }
    try {
      $found += Get-ChildItem -LiteralPath $r -Directory -Recurse -Depth $MaxDepth -Filter $leaf -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -like $mustContain } | Select-Object -ExpandProperty FullName
    } catch {}
  }
  return ($found | Sort-Object -Unique)
}

Write-Host "[census] $stamp  out=$OutDir"

# ---------------------------------------------------------------- terminals
$serviceDirs = Find-Dirs $TerminalRoots 'Services' '*\MQL5\Services'
$terminals = @()
foreach ($s in $serviceDirs) {
  $mql5 = Split-Path $s -Parent          # ...\MQL5
  $data = Split-Path $mql5 -Parent       # terminal data folder
  $terminals += [pscustomobject]@{ Data = $data; Services = $s }
}
Write-Host "[census] terminal data folders with MQL5\Services: $($terminals.Count)"

# ---------------------------------------------------------------- P0.1 source census
$searchRoots = @($Roots) + ($terminals | ForEach-Object { $_.Services })
$files = @()
foreach ($r in $searchRoots) {
  if (-not (Test-Path -LiteralPath $r)) { Write-Host "[census] missing root: $r"; continue }
  $files += Get-ChildItem -LiteralPath $r -Recurse -File -Depth $MaxDepth -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^XP[ _]?ChartEngine.*\.(mq5|ex5)$' }
}
$files = $files | Sort-Object FullName -Unique
$rows = foreach ($f in $files) {
  $norm = if ($f.Extension -ieq '.mq5') { Get-NormHash $f.FullName } else { '' }
  [pscustomobject]@{
    Path = $f.FullName; Bytes = $f.Length; LastWrite = $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
    RawSha256 = Get-RawHash $f.FullName; NormSha256 = $norm
    MatchesPromptBase = if ($norm -eq $BaseHash) { 'YES' } else { 'no' }
  }
}
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OutDir 'census_files.csv')
Write-Host "[census] XP ChartEngine files found: $($rows.Count)"

# divergences: group .mq5 by normalised hash; newest = base; diff every other group against it
$md = @("# XP ChartEngine source census - $stamp", "", "Prompt base (LF-normalised sha256): ``$BaseHash``", "")
$src = $rows | Where-Object { $_.Path -match '\.mq5$' -and $_.NormSha256 -ne 'ERR' }
if ($src.Count -gt 0) {
  $newest = $src | Sort-Object LastWrite -Descending | Select-Object -First 1
  $md += "Newest source (P0.1 base candidate): ``$($newest.Path)`` ($($newest.LastWrite), norm=$($newest.NormSha256))"
  $md += ""
  $md += "| norm sha256 | copies | newest write | matches prompt base |"
  $md += "|---|---|---|---|"
  $groups = $src | Group-Object NormSha256
  foreach ($g in $groups) {
    $nw = ($g.Group | Sort-Object LastWrite -Descending | Select-Object -First 1).LastWrite
    $m = if ($g.Name -eq $BaseHash) { 'YES' } else { 'no' }
    $md += "| $($g.Name) | $($g.Count) | $nw | $m |"
  }
  $md += ""
  $md += "## Copies"
  foreach ($r in $src) { $md += "- ``$($r.Path)`` $($r.LastWrite) norm=$($r.NormSha256)" }
  $md += ""
  $md += "## Diffs against newest"
  $git = Get-Command git -ErrorAction SilentlyContinue
  $newTxt = Read-TextSafe $newest.Path
  foreach ($g in $groups) {
    if ($g.Name -eq $newest.NormSha256) { continue }
    $rep = $g.Group[0]
    $md += ""; $md += "### ``$($rep.Path)`` vs newest"
    $md += '```diff'
    if ($git) {
      $a = Join-Path $env:TEMP 'xp_census_a.mq5'; $b = Join-Path $env:TEMP 'xp_census_b.mq5'
      [System.IO.File]::WriteAllText($a, ($newTxt -replace "`r`n", "`n"))
      [System.IO.File]::WriteAllText($b, ((Read-TextSafe $rep.Path) -replace "`r`n", "`n"))
      $md += (& git --no-pager diff --no-index -- $a $b 2>&1 | Out-String)
    } else {
      $x = ($newTxt -replace "`r`n", "`n") -split "`n"
      $y = ((Read-TextSafe $rep.Path) -replace "`r`n", "`n") -split "`n"
      $md += (Compare-Object $x $y | ForEach-Object { "$($_.SideIndicator) $($_.InputObject)" })
    }
    $md += '```'
  }
} else {
  $md += "NO .mq5 SOURCE FOUND under the searched roots."
}
$md | Set-Content -Encoding UTF8 (Join-Path $OutDir 'divergences.md')

# ---------------------------------------------------------------- P0.4 deployment map
$dm = @("# Deployment map - $stamp", "", "Directory listing only; no file under bases\Custom is opened.", "")
foreach ($t in $terminals) {
  $dm += "## $($t.Data)"
  $svc = Get-ChildItem -LiteralPath $t.Services -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -match '\.(ex5|mq5)$' }
  $dm += ""; $dm += "Services ($($svc.Count)):"
  foreach ($f in $svc) { $dm += "- $($f.Name)  $($f.Length) B  $($f.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))  sha256=$(Get-RawHash $f.FullName)" }
  $custom = Join-Path $t.Data 'bases\Custom'
  $dm += ""; $dm += "Custom symbols (bases\Custom, dirs containing XPChart):"
  if (Test-Path -LiteralPath $custom) {
    $xd = Get-ChildItem -LiteralPath $custom -Directory -Recurse -Depth 3 -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'XPChart' }
    if ($xd.Count -eq 0) { $dm += "- (none)" }
    foreach ($d in $xd) { $dm += "- $($d.FullName.Substring($t.Data.Length))  $($d.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))" }
  } else { $dm += "- (no bases\Custom folder)" }
  $dm += ""; $dm += "Last 'XP ChartEngine Active' line in logs\*.log (newest 5 files scanned):"
  $logs = Get-ChildItem -LiteralPath (Join-Path $t.Data 'logs') -File -Filter '*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5
  $hit = $null
  foreach ($lg in $logs) {
    $txt = Read-TextSafe $lg.FullName
    if ($null -eq $txt) { continue }
    $m = [regex]::Matches($txt, '.*XP ChartEngine Active.*')
    if ($m.Count -gt 0) { $hit = "$($lg.Name): $($m[$m.Count-1].Value.Trim())"; break }
  }
  $dm += "- " + $(if ($hit) { $hit } else { '(none)' })
  $dm += ""
}
if ($terminals.Count -eq 0) { $dm += "NO terminal data folders found under: $($TerminalRoots -join ', ')" }
$dm | Set-Content -Encoding UTF8 (Join-Path $OutDir 'deployment_map.md')

# ---------------------------------------------------------------- P2 compiler census
$compilers = @()
foreach ($r in ($TerminalRoots + @("$env:ProgramFiles", "${env:ProgramFiles(x86)}")) | Sort-Object -Unique) {
  if (-not (Test-Path -LiteralPath $r)) { continue }
  $compilers += Get-ChildItem -LiteralPath $r -Recurse -Depth $MaxDepth -File -Filter 'metaeditor64.exe' -ErrorAction SilentlyContinue |
     ForEach-Object { [pscustomobject]@{ Path = $_.FullName; Version = $_.VersionInfo.FileVersion; LastWrite = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') } }
}
$compilers = $compilers | Sort-Object Path -Unique
$compilers | Export-Csv -NoTypeInformation -Encoding UTF8 (Join-Path $OutDir 'compilers.csv')
Write-Host "[census] metaeditor64.exe found: $($compilers.Count)"

# ---------------------------------------------------------------- R6 D-drive convention
$dd = @()
foreach ($r in $Roots) {
  if (-not (Test-Path -LiteralPath $r)) { continue }
  $dd += Get-ChildItem -LiteralPath $r -Recurse -File -Depth $MaxDepth -Include *.mq5,*.mqh,*.py,*.ps1,*.json,*.md,*.txt,*.ini -ErrorAction SilentlyContinue |
         Select-String -Pattern '[Dd]:\\[^"''\s]+' -ErrorAction SilentlyContinue | Select-Object -First 200 |
         ForEach-Object { "$($_.Path):$($_.LineNumber): $($_.Matches[0].Value)" }
}
if ($dd.Count -eq 0) { $dd = @('(no D:\ path literal found in the trees -> R6 fallback MQL5\Files\XPChart applies)') }
$dd | Set-Content -Encoding UTF8 (Join-Path $OutDir 'ddrive_convention.txt')

# ---------------------------------------------------------------- summary
$sum = @(
  "# XP census summary - $stamp",
  "- roots searched: $($searchRoots -join '; ')",
  "- terminal data folders: $($terminals.Count)",
  "- XP ChartEngine files: $($rows.Count)  (see census_files.csv, divergences.md)",
  "- compilers: $($compilers.Count)  (see compilers.csv)",
  "- deployment map: deployment_map.md",
  "- D-drive convention hits: $($dd.Count)  (see ddrive_convention.txt)"
)
$sum | Set-Content -Encoding UTF8 (Join-Path $OutDir 'census_summary.md')
$sum | ForEach-Object { Write-Host $_ }
