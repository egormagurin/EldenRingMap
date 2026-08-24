@echo off
setlocal
chcp 65001 >nul
title Elden Ring - live mode diagnostic

rem ---------------------------------------------------------------------------
rem One-shot check that the live reader can attach to your game and that the
rem byte signatures still match this game version. Reads only; changes nothing.
rem Writes cache\live-probe.log.
rem
rem Run this with Elden Ring running and a character loaded (not the title
rem screen) for a meaningful result.
rem ---------------------------------------------------------------------------

net session >nul 2>&1
if "%errorlevel%"=="0" goto :elevated

echo   Requesting administrator rights...
powershell -NoProfile -Command "Start-Process -FilePath \"%~f0\" -Verb RunAs"
goto :eof

:elevated
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :no_python

tasklist /fi "imagename eq eldenring.exe" 2>nul | find /i "eldenring.exe" >nul
if errorlevel 1 goto :not_running

echo.
python tools\live_memory.py --probe
echo.
pause
goto :eof

:not_running
echo.
echo   Elden Ring is not running. Start it, load your character, then run this again.
echo.
pause & goto :eof

:no_python
echo.
echo   Python not found. Install it from https://python.org and try again.
echo.
pause & goto :eof
