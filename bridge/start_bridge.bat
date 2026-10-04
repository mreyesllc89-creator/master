@echo off
rem Starts the bridge and Caddy. Point a Windows Task Scheduler task
rem ("At log on", "Run with highest privileges") at this file to auto-start.
cd /d "%~dp0"
start "caddy" caddy.exe run --config Caddyfile
python tv_mt5_bridge.py
