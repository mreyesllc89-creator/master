# XPChart — XP ChartEngine v2 (plumbing)

Start with `XP_CHARTENGINE_REPORT.md` (line 1 = verdict; §11 = run order). `P0_REPORT.md` is the pre-edit diagnosis of v1.

| File | What |
|---|---|
| `XP ChartEngine.mq5` | v1, as supplied, unchanged (last known good) |
| `XP ChartEngine v2.mq5` | v2 service: CopyTicks cursor, tick-anchored bars, spec sync, restart-safe, heartbeat, lock |
| `XP_AxisCheck.mq5` | read-only Gate 1 script: which time axis an existing `*_S1` custom symbol really holds |
| `tools/XP_Census.ps1` | read-only census of the Windows trees and MT5 installs (hashes, divergences, deployment map, compilers) |
| `tools/XP_Compile.ps1` | compile with `metaeditor64.exe /compile` |
| `tools/XP_LineageSweep.ps1` | grep both trees for the v1 patterns |

Hard rules honoured: running terminals are read-only, no tick backfill, nothing broker-specific hardcoded, the agent never attaches v2 to a live terminal.
