@echo off
setlocal
chcp 65001 >nul
title Elden Ring - Live Map (real-time)

rem ---------------------------------------------------------------------------
rem Same as "Start Map.bat", plus a read-only reader attached to the running
rem game, so the player dot moves in real time instead of jumping once per save.
rem
rem Needs administrator rights: Elden Ring runs elevated, so reading its memory
rem requires the same. The reader only ever READS - it cannot modify the game
rem or your save. If it can't attach, the map still works from the save file.
rem
rem Note: `goto` is used instead of parenthesised if-blocks throughout, because
rem cmd expands %~f0 before parsing the block, and any bracket in the path would
rem terminate the block early.
rem ---------------------------------------------------------------------------

set PORT=8099

rem --- elevate if we aren't already -----------------------------------------
net session >nul 2>&1
if "%errorlevel%"=="0" goto :elevated

echo.
echo   Requesting administrator rights ^(needed to read the game^)...

rem Pass arguments through only when there are some: PowerShell rejects an
rem empty -ArgumentList, which silently killed the previous version of this file.
if "%~1"=="" goto :relaunch_plain
powershell -NoProfile -Command "Start-Process -FilePath \"%~f0\" -ArgumentList \"%*\" -Verb RunAs"
goto :eof
:relaunch_plain
powershell -NoProfile -Command "Start-Process -FilePath \"%~f0\" -Verb RunAs"
goto :eof

:elevated
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 goto :no_node
where python >nul 2>nul
if errorlevel 1 goto :no_python
if not exist "web\tiles\manifest.json" goto :no_tiles

rem --- is the port already taken? -------------------------------------------
netstat -ano | find ":%PORT% " | find "LISTENING" >nul
if not errorlevel 1 goto :port_busy

tasklist /fi "imagename eq eldenring.exe" 2>nul | find /i "eldenring.exe" >nul
if errorlevel 1 echo   Note: Elden Ring isn't running yet - the reader will wait and attach on its own.

echo.
echo   Starting in real-time mode on port %PORT% ...
echo   Leave this window open while you play. Close it to stop.
echo.

start "" /b cmd /c "ping -n 3 127.0.0.1 >nul & start http://localhost:%PORT%"

node server\index.js --port %PORT% --live-memory %*
set RC=%errorlevel%

echo.
if not "%RC%"=="0" echo   Server exited with code %RC%.
if "%RC%"=="0" echo   Server stopped.
pause
goto :eof

:no_node
echo.
echo   Node.js not found. Install it from https://nodejs.org and try again.
echo.
pause & goto :eof

:no_python
echo.
echo   Python not found. Install it from https://python.org and try again.
echo.
pause & goto :eof

:no_tiles
echo.
echo   Map tiles are missing. Run "Setup.bat" once first.
echo.
pause & goto :eof

:port_busy
echo.
echo   Port %PORT% is already in use - another copy of the map is probably
echo   still running. Close its window, or end node.exe in Task Manager,
echo   then run this again.
echo.
echo   Listening process:
netstat -ano | find ":%PORT% " | find "LISTENING"
echo.
pause & goto :eof
