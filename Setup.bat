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
rem
rem Playing a loose-file mod such as Elden Ring Reforged? Point MODDIR at its
rem mod folder - the one containing the mod's own regulation.bin - and the
rem setup reads the mod's data over the game's archives.
rem
rem   set MODDIR=D:\Games\ELDEN RING Reforged\mod
rem ---------------------------------------------------------------------------
set GAMEDIR=
set MODDIR=

rem The Python tools pick the mod up from the environment.
if not "%MODDIR%"=="" set "ER_MOD_DIR=%MODDIR%"

echo.
echo   Elden Ring Live Map - setup
echo   ===========================
echo.

where node >nul 2>nul
if errorlevel 1 goto :no_node
where python >nul 2>nul
if errorlevel 1 goto :no_python

echo   [1/7] Installing Python packages ...
python -m pip install --quiet --disable-pip-version-check zstandard pycryptodome pillow texture2ddecoder numpy
if errorlevel 1 goto :pip_failed

echo   [2/7] Extracting map tiles from your game ^(a couple of minutes^) ...
if "%GAMEDIR%"=="" python tools\extract_tiles.py
if not "%GAMEDIR%"=="" python tools\extract_tiles.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :extract_failed

echo   [3/7] Building the marker dataset ...
if "%GAMEDIR%"=="" python tools\build_markers.py
if not "%GAMEDIR%"=="" python tools\build_markers.py "%GAMEDIR%"
if errorlevel 1 goto :markers_failed

echo   [4/7] Indexing the game's map files ...
python tools\enumerate_maps.py >nul
if errorlevel 1 goto :items_failed

echo   [5/7] Extracting item locations ^(this reads 864 map files^) ...
if "%GAMEDIR%"=="" python tools\extract_items.py
if not "%GAMEDIR%"=="" python tools\extract_items.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :items_failed

echo   [6/7] Extracting the game's map icons ...
if "%GAMEDIR%"=="" python tools\extract_icons.py
if not "%GAMEDIR%"=="" python tools\extract_icons.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :icons_failed

rem Rune and Ember Pieces are Reforged collectibles - there are none to find in
rem an unmodded game, so this step only runs when MODDIR is set.
if "%MODDIR%"=="" goto :skip_pieces
echo   [7/7] Extracting Reforged rune/ember pieces ...
if "%GAMEDIR%"=="" python tools\extract_pieces.py --mod-dir "%MODDIR%"
if not "%GAMEDIR%"=="" python tools\extract_pieces.py --game-dir "%GAMEDIR%" --mod-dir "%MODDIR%"
if errorlevel 1 goto :pieces_failed
goto :done_pieces
:skip_pieces
echo   [7/7] Reforged rune/ember pieces - skipped ^(MODDIR not set^)
:done_pieces

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

:icons_failed
echo.
echo   Icon extraction failed. The map still works - markers will use coloured
echo   dots instead of the game's own icons.
echo.
pause & goto :eof

:items_failed
echo.
echo   Item extraction failed. The map still works without it - you will just
echo   have no item markers. Re-run this file to try again.
echo.
pause & goto :eof

:pieces_failed
echo.
echo   Rune/ember piece extraction failed. The map still works - you will just
echo   have no piece markers. Check that MODDIR points at the Reforged mod
echo   folder containing regulation.bin.
echo.
pause & goto :eof
