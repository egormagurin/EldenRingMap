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
rem
rem Route descriptions - "how do I actually get to this?" - are not in the game
rem files. They are something people write, so the last step can fetch them from
rem the Fextralife wiki's interactive map and attach them to your markers. It
rem asks first; answer here instead to keep setup unattended.
rem
rem   set TIPS=yes
rem ---------------------------------------------------------------------------
set GAMEDIR=
set MODDIR=
set TIPS=

rem The Python tools pick the mod up from the environment.
if not "%MODDIR%"=="" set "ER_MOD_DIR=%MODDIR%"

echo.
echo   Elden Ring Live Map - setup
echo   ===========================
echo.

rem Node and Python are checked by *running* them, not with "where". Windows
rem ships a zero-byte App Execution Alias at
rem %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe whose only job is to open
rem the Microsoft Store - it satisfies "where python" on a machine that has no
rem Python at all, so the old check passed and pip then failed confusingly.

where node >nul 2>nul
if errorlevel 1 goto :no_node
node -e "process.exit(parseInt(process.versions.node) >= 18 ? 0 : 1)" >nul 2>nul
if errorlevel 1 goto :old_node

set "PY="
set "PYOLD="
call :probe_python python
if not defined PY call :probe_python py -3
if defined PY goto :have_python
if defined PYOLD goto :old_python
goto :no_python

:have_python
%PY% -m pip --version >nul 2>nul
if errorlevel 1 goto :no_pip

echo   [1/8] Installing Python packages ...
%PY% -m pip install --quiet --disable-pip-version-check zstandard pycryptodome pillow texture2ddecoder numpy
if errorlevel 1 goto :pip_failed

echo   [2/8] Extracting map tiles from your game ^(a couple of minutes^) ...
if "%GAMEDIR%"=="" %PY% tools\extract_tiles.py
if not "%GAMEDIR%"=="" %PY% tools\extract_tiles.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :extract_failed

echo   [3/8] Building the marker dataset ...
if "%GAMEDIR%"=="" %PY% tools\build_markers.py
if not "%GAMEDIR%"=="" %PY% tools\build_markers.py "%GAMEDIR%"
if errorlevel 1 goto :markers_failed

echo   [4/8] Indexing the game's map files ...
%PY% tools\enumerate_maps.py >nul
if errorlevel 1 goto :items_failed

echo   [5/8] Extracting item locations ^(this reads 864 map files^) ...
if "%GAMEDIR%"=="" %PY% tools\extract_items.py
if not "%GAMEDIR%"=="" %PY% tools\extract_items.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :items_failed

echo   [6/8] Extracting the game's map icons ...
if "%GAMEDIR%"=="" %PY% tools\extract_icons.py
if not "%GAMEDIR%"=="" %PY% tools\extract_icons.py --game-dir "%GAMEDIR%"
if errorlevel 1 goto :icons_failed

rem Rune and Ember Pieces are Reforged collectibles - there are none to find in
rem an unmodded game, so this step only runs when MODDIR is set.
if "%MODDIR%"=="" goto :skip_pieces
echo   [7/8] Extracting Reforged rune/ember pieces ...
if "%GAMEDIR%"=="" %PY% tools\extract_pieces.py --mod-dir "%MODDIR%"
if not "%GAMEDIR%"=="" %PY% tools\extract_pieces.py --game-dir "%GAMEDIR%" --mod-dir "%MODDIR%"
if errorlevel 1 goto :pieces_failed
goto :done_pieces
:skip_pieces
echo   [7/8] Reforged rune/ember pieces - skipped ^(MODDIR not set^)
:done_pieces

rem Everything above this line was read out of your own copy of the game. This
rem step is the one exception, so it asks before it runs.
if /i "%TIPS%"=="yes" goto :do_tips
if /i "%TIPS%"=="no" goto :skip_tips
echo.
echo   [8/8] Route descriptions ^(optional^)
echo.
echo   Your markers can now say what a thing is and how high up it is. What
echo   they cannot say is how to get to it - that is not in the game files,
echo   it is something people write. The Fextralife wiki's interactive map
echo   has a written route for most of its markers, and this fetches them
echo   and attaches them to about 2,000 of yours.
echo.
echo   That text is theirs - not yours, and not the game's - and their terms
echo   ask that it is not fetched automatically. It stays on this PC for your
echo   own use: do not republish it or ship it with a copy of this tool. The
echo   map is complete without it.
echo.
set "ans="
set /p ans=  Fetch them? [y/N] 
if /i not "%ans%"=="y" goto :skip_tips
:do_tips
echo   Fetching route descriptions ...
%PY% tools\fetch_tips.py
if errorlevel 1 goto :tips_failed
goto :done_tips
:skip_tips
echo   [8/8] Route descriptions - skipped
:done_tips

echo.
echo   Done. Start it any time with "Start Map.bat".
echo.
pause
goto :eof

rem Try one Python command line. Sets PY if it runs and is 3.9+, PYOLD if it
rem runs but is too old, and neither if it is missing or is the Store stub.
:probe_python
if defined PY goto :eof
%* -c "import sys" >nul 2>nul
if errorlevel 1 goto :eof
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 (
  set "PYOLD=%*"
  goto :eof
)
set "PY=%*"
goto :eof

:no_node
echo   Node.js not found. Install it from https://nodejs.org, then run this again.
echo   Make sure you open a NEW window afterwards so PATH is picked up.
echo.
pause & goto :eof

:old_node
echo   Your Node.js is too old - this needs 18 or newer.
for /f "delims=" %%v in ('node --version 2^>nul') do echo   Found: %%v
echo   Install the current LTS from https://nodejs.org and open a NEW window.
echo.
pause & goto :eof

:no_python
echo   Python not found.
echo.
echo   If you think you installed it, this is usually one of two things:
echo     - it was installed without "Add Python to PATH" ticked, or
echo     - only the Microsoft Store placeholder is on PATH, which does nothing
echo       except offer to install Python.
echo.
echo   Install it from https://python.org, tick "Add Python to PATH" in the
echo   installer, then open a NEW window and run this again.
echo.
pause & goto :eof

:old_python
echo   Your Python is too old - this needs 3.9 or newer.
for /f "delims=" %%v in ('%PYOLD% --version 2^>^&1') do echo   Found: %%v
echo   Install a current version from https://python.org, tick "Add Python to
echo   PATH", then open a NEW window and run this again.
echo.
pause & goto :eof

:no_pip
echo   Python is installed but pip is missing, so the packages cannot be
echo   installed. Try repairing it with:
echo     %PY% -m ensurepip --upgrade
echo   then run this again.
echo.
pause & goto :eof

:pip_failed
echo.
echo   Installing the Python packages failed. Try it by hand to see the error:
echo     %PY% -m pip install zstandard pycryptodome pillow texture2ddecoder numpy
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

:tips_failed
echo.
echo   Fetching the route descriptions failed - no internet, or the wiki
echo   changed. Everything else is built and the map works; markers will just
echo   have no "how to get there" text. Re-run this file to try again.
echo.
pause & goto :eof

:pieces_failed
echo.
echo   Rune/ember piece extraction failed. The map still works - you will just
echo   have no piece markers. Check that MODDIR points at the Reforged mod
echo   folder containing regulation.bin.
echo.
pause & goto :eof
