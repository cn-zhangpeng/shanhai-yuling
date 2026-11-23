@echo off
chcp 65001 >nul
rem 山海遇灵 · 桌面生灵 启动器
cd /d "%~dp0"
start "" "%~dp0node_modules\electron\dist\electron.exe" "%~dp0"
