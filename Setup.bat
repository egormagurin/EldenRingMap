@echo off
setlocal
chcp 65001 >nul
title Elden Ring Live Map - setup

cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem Your Elden Ring install is found automatically by scanning your Steam
rem libraries. Only fill this in if that fails - it must be the folder that
rem contains eldenring.exe and regulation.bin.
rem
rem   set GAMEDIR=D:\Games\Steam\steamapps\common\ELDEN RING\Game
rem ---------------------------------------------------------------------------
set GAMEDIR=

echo.
echo   Elden Ring Live Map - setup
echo   ===========================
echo.

where node >nul 2>nul
if errorlevel 1 goto :no_node
where python >nul 2>nul
if errorlevel 1 goto :no_python

echo   [1/3] Installing Python packages ...
python -m pip install --quiet --disable-pip-version-check zstandard pycryptodome pillow texture2ddecoder numpy
if errorlevel 1 goto :pip_failed

echo   [2/3] Extracting map tiles from your game ^(a couple of minutes^) ...
if "%GAMEDIR%"=="" python tools\extract_tiles.py
if not "%GAMEDIR%"=="" python tools\extract_tiles.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :extract_failed

echo   [3/3] Building the marker dataset ...
if "%GAMEDIR%"=="" python tools\build_markers.py
if not "%GAMEDIR%"=="" python tools\build_markers.py "%GAMEDIR%"
if errorlevel 1 goto :markers_failed

echo.
echo   Done. Start it any time with "Start Map.bat".
echo.
pause
goto :eof

:no_node
echo   Node.js not found. Install it from https://nodejs.org, then run this again.
echo   Make sure you open a NEW window afterwards so PATH is picked up.
echo.
pause & goto :eof

:no_python
echo   Python not found. Install it from https://python.org, then run this again.
echo   Tick "Add Python to PATH" in the installer, and open a NEW window afterwards.
echo.
pause & goto :eof

:pip_failed
echo.
echo   Installing the Python packages failed. Try it by hand to see the error:
echo     python -m pip install zstandard pycryptodome pillow texture2ddecoder numpy
echo.
pause & goto :eof

:extract_failed
echo.
echo   Tile extraction failed.
echo   If it could not find your game, set GAMEDIR at the top of this file to the
echo   folder containing eldenring.exe and regulation.bin, then run this again.
echo.
pause & goto :eof

:markers_failed
echo.
echo   Building the marker dataset failed. See the message above.
echo.
pause & goto :eof
