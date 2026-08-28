@echo off
setlocal
chcp 65001 >nul
title Elden Ring - Live Map

rem Run from this script's own folder, whatever the working directory is.
cd /d "%~dp0"

set PORT=8099

rem Pass extra server options straight through, e.g.
rem   "Start Map.bat" --lan        also serve to your local network
rem   node server\index.js --help  full list

where node >nul 2>nul
if errorlevel 1 goto :no_node
node -e "process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)" >nul 2>nul
if errorlevel 1 goto :old_node
if not exist "web\tiles\manifest.json" goto :no_tiles

netstat -ano | find ":%PORT% " | find "LISTENING" >nul
if not errorlevel 1 goto :port_busy

echo.
echo   Starting the map server on port %PORT% ...
echo   Leave this window open while you play. Close it to stop.
echo.

rem Give the server a moment to bind, then open the browser.
rem ping is the delay here because `timeout` fails when stdin is redirected.
start "" /b cmd /c "ping -n 3 127.0.0.1 >nul & start http://localhost:%PORT%"

node server\index.js --port %PORT% %*
set RC=%errorlevel%

echo.
if not "%RC%"=="0" echo   Server exited with code %RC%.
if "%RC%"=="0" echo   Server stopped.
pause
goto :eof

:old_node
echo.
echo   Your Node.js is too old - this needs 18 or newer.
for /f "delims=" %%v in ('node --version 2^>nul') do echo   Found: %%v
echo   Install the current LTS from https://nodejs.org, then open a NEW window.
echo.
pause & goto :eof

:no_node
echo.
echo   Node.js was not found on your PATH.
echo   Install it from https://nodejs.org ^(LTS is fine^), then run this again.
echo.
pause & goto :eof

:no_tiles
echo.
echo   Map tiles are missing.
echo   Run "Setup.bat" once first - it extracts them from your game install.
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
