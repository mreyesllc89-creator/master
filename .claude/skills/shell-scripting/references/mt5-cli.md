# MetaTrader 5 automation from the shell

## Locations
- Program: `C:\Program Files\MetaTrader 5\` (`terminal64.exe`, `metaeditor64.exe`);
  broker builds live under `C:\Program Files\<Broker> MetaTrader 5\`.
- Data folder (per install): `%APPDATA%\MetaQuotes\Terminal\<32-hex-id>\` with `MQL5\`
  (`Experts`, `Indicators`, `Include`, `Files`, `Logs`), `config\`, `logs\`, `tester\`.
  Find it: `Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Directory | Where-Object { Test-Path "$($_.FullName)\MQL5" }`.
- Portable mode (`terminal64.exe /portable`) keeps data next to the program instead.
- Common folder shared by all terminals: `%APPDATA%\MetaQuotes\Terminal\Common\Files`.

## Compile
```powershell
& 'C:\Program Files\MetaTrader 5\metaeditor64.exe' /compile:"C:\...\MQL5\Experts\FlashGold\FlashGold_v5.mq5" /log
```
- `/compile:<file or folder>` compiles one file or every source in a folder;
  `/inc:<path>` adds an include root; `/log` or `/log:<file>` writes the UTF-16 log beside
  the source; `/s` syntax check only.
- The exit code is the number of compiled files, not success. Parse the log for
  ` : error ` and ` : warning `; the last lines read `Result: N errors, M warnings`.
- Output `.ex5` sits next to the `.mq5`. The terminal picks it up on its next scan; an EA
  already on a chart is reloaded automatically.

## Deploy
```powershell
$data = (Get-ChildItem "$env:APPDATA\MetaQuotes\Terminal" -Directory | Where-Object { Test-Path "$($_.FullName)\MQL5\Experts" } | Select-Object -First 1).FullName
Copy-Item -LiteralPath .\src\FlashGold_v5.mq5 -Destination "$data\MQL5\Experts\FlashGold\" -Force
```
Keep sources in the repo and copy (or symlink with `New-Item -ItemType SymbolicLink`) into
the data folder; never edit only the copy in `AppData`.

## Headless backtest / optimisation
`tester.ini` (UTF-16 LE or ANSI both accepted; keep ASCII content):
```ini
[Tester]
Expert=FlashGold\FlashGold_v5.ex5      ; relative to MQL5\Experts
ExpertParameters=flashgold.set         ; from MQL5\Profiles\Tester\
Symbol=BTCUSD
Period=M5
Model=1                                ; 0 every tick, 1 1-min OHLC, 2 open prices, 3 math, 4 real ticks
Optimization=0                         ; 0 off, 1 slow complete, 2 genetic, 3 all symbols in Market Watch
OptimizationCriterion=0                ; 0 balance max, 6 custom (OnTester)
FromDate=2024.01.01
ToDate=2024.12.31
ForwardMode=0                          ; 0 off, 1 1/2, 2 1/3, 3 1/4, 4 custom (ForwardDate=)
Deposit=10000
Currency=USD
Leverage=100
ExecutionMode=0                        ; delay ms
Report=reports\flashgold_2024          ; relative to the data folder; .htm written
ReplaceReport=1
ShutdownTerminal=1
Visual=0
```
Run (the terminal must not already be running with the same data folder):
```powershell
& 'C:\Program Files\MetaTrader 5\terminal64.exe' /config:C:\bots\tester.ini
```
`.set` files are saved from the tester's Inputs tab (right-click → Save) and contain
`Name=value||start||step||stop||Y/N` lines; edit with `Set-Content -Encoding Unicode`.
Results: the HTML report, `tester\logs\*.log`, and for optimisations the `*.xml`/`*.opt`
cache under `tester\cache`.

## Start the terminal with a profile / login
`terminal64.exe /login:12345678 /password:... /server:Broker-Server /profile:MyProfile`
or a `[Common]` section in a `/config` ini (`Login=`, `Password=`, `Server=`,
`AutoConfiguration=`, `EnableNews=0`). Passwords on a command line are visible in Task
Manager; prefer a one-time manual login with saved credentials.

## Logs
- Terminal journal: `logs\YYYYMMDD.log`; EA output: `MQL5\Logs\YYYYMMDD.log`; tester:
  `tester\logs\YYYYMMDD.log` (all UTF-16 LE).
- Tail with `Get-Content -Encoding Unicode -Wait -Tail 50 <file>`; grep with
  `Select-String -Encoding Unicode 'retcode|error'`.

## Wine / Linux
MT5 runs under Wine (`wine terminal64.exe`); the data folder is then
`~/.wine/drive_c/users/<user>/AppData/Roaming/MetaQuotes/Terminal/...`. The Python
`MetaTrader5` package needs Windows Python under the same Wine prefix. Expect `/config`
tester runs to work; GUI automation is unreliable.
