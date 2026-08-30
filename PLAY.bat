@echo off
cd /d "%~dp0"
title Pokemon Championship
color 0A

echo.
echo  =====================================================
echo   POKEMON CHAMPIONSHIP - Launcher
echo  =====================================================
echo.

REM --- Locate a usable Python interpreter, even if "python" isn't on PATH ---
REM     (a per-user install that skipped "Add Python to PATH" still leaves
REM     "python" unresolvable in a plain cmd/Explorer session even though
REM     it's right there on disk, and the "py" launcher isn't guaranteed
REM     either -- so fall back to the well-known per-user/per-machine
REM     install folders before giving up.)
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    py --version >nul 2>&1 && set "PY=py"
)
if not defined PY (
    for /f "delims=" %%P in ('dir /b /a:d /o:-n "%LOCALAPPDATA%\Programs\Python\Python3*" 2^>nul') do (
        if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%P\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\%%P\python.exe"
    )
)
if not defined PY (
    for /f "delims=" %%P in ('dir /b /a:d /o:-n "%ProgramFiles%\Python3*" 2^>nul') do (
        if not defined PY if exist "%ProgramFiles%\%%P\python.exe" set "PY=%ProgramFiles%\%%P\python.exe"
    )
)
if not defined PY (
    echo  [ERROR] Python is not installed, or not on your PATH.
    echo.
    echo  Download Python 3 from https://www.python.org/downloads/
    echo  During install, tick "Add Python to PATH" before continuing.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found ^(%PY%^).
echo.
echo  Installing required libraries ^(takes a few minutes the first time^)...
echo.

"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install pygame-ce numpy openpyxl pillow PySide6 --quiet

if errorlevel 1 (
    echo.
    echo  [ERROR] Something went wrong during installation.
    echo  Try running this file as Administrator ^(right-click ^> Run as administrator^).
    echo.
    pause
    exit /b 1
)

echo  [OK] All libraries installed!
echo.

REM --- Check PySide6 actually imports (covers unusual/broken installs) ---
"%PY%" -c "import PySide6" >nul 2>&1
set HAVE_QT=1
if errorlevel 1 set HAVE_QT=0

REM --- Straight into the game. There is no longer a choice to make: the
REM     command-line version has been removed, so PySide6 is required rather
REM     than preferred.
if "%HAVE_QT%"=="0" (
    echo  =====================================================
    echo   PySide6 did not install correctly
    echo  =====================================================
    echo.
    echo   Pokemon Championship needs PySide6 to run. Try this file again,
    echo   or run "pip install PySide6" yourself to see the real error.
    echo.
    pause
    exit /b 1
)

echo.
echo  Starting Pokemon Championship...
echo.
"%PY%" play.py

:END
if errorlevel 1 pause
