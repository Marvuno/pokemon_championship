@echo off
cd /d "%~dp0"
title Pokemon Champion - Update Repository
color 0B

echo.
echo  =====================================================
echo   POKEMON CHAMPION - Update your git repository
echo  =====================================================
echo.

REM --- Locate a usable Python interpreter, even if "python" isn't on PATH ---
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY (
    echo  Python was not found. Install it, or run PLAY.bat first --
    echo  it knows how to find an interpreter this one cannot.
    echo.
    pause
    exit /b 1
)

REM No arguments: report only. Nothing is committed and nothing is pushed
REM unless a message is given, so double-clicking this file is always safe.
if "%~1"=="" (
    %PY% "Tools\update_repo.py"
    echo.
    echo  -----------------------------------------------------
    echo   That was a report. To actually commit, run from a
    echo   terminal in this folder:
    echo.
    echo     python Tools\update_repo.py -m "what you changed"
    echo.
    echo   Add --push to send it to your repository too, or
    echo   --remote ^<url^> the first time to connect it.
    echo  -----------------------------------------------------
    echo.
    pause
    exit /b 0
)

REM Anything passed to this file goes straight through, so
REM UPDATE.bat -m "message" --push works as well.
%PY% "Tools\update_repo.py" %*
echo.
pause
