@echo off
REM SearchX - Run Script (Windows)
REM Auto-fixes code, runs quality checks, then launches the application

setlocal enabledelayedexpansion

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist ".venv" (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -e ".[dev]"
) else (
    call .venv\Scripts\activate.bat
)

REM Parse command line arguments
set "MODE=%~1"
if "%MODE%"=="" set "MODE=ui"

REM Skip checks if --no-check flag is passed
set "SKIP_CHECKS=0"
if /i "%~2"=="--no-check" set "SKIP_CHECKS=1"
if /i "%~1"=="--no-check" (
    set "SKIP_CHECKS=1"
    set "MODE=ui"
)

if %SKIP_CHECKS%==1 goto :run_app

echo ==========================================
echo Running Quality Checks (with auto-fix)...
echo ==========================================

echo.
echo [1/4] Auto-fixing code formatting (ruff format)...
ruff format . || goto :fmt_failed
echo [DONE] Formatting applied

echo.
echo [2/4] Auto-fixing lint issues (ruff check --fix)...
ruff check --fix . || goto :lint_failed
echo [DONE] Linting OK

echo.
echo [3/4] Running python tests 
python -m pytest tests/ -v || goto :tests_failed
echo [DONE] Tests passed

echo.
echo [4/4] Running type checker (mypy)...
mypy src/ || goto :mypy_failed
echo [PASS] Type checking OK
goto :checks_passed

:fmt_failed
echo [FAIL] Formatting failed
goto :checks_failed

:lint_failed
echo [FAIL] Linting errors remain (cannot auto-fix)
goto :checks_failed

:mypy_failed
echo [FAIL] Type checking failed
goto :checks_failed

:tests_failed
echo [FAIL] Tests are currently failing
goto :checks_failed

:checks_passed

echo.
echo ==========================================
echo All checks passed! Starting application...
echo ==========================================

:run_app
echo.
if /i "%MODE%"=="ui" goto :run_ui
goto :usage

:run_ui
echo Starting desktop application...
python -m logarithmic
goto :end

:checks_failed
echo.
echo ==========================================
echo Quality checks failed. Fix errors above.
echo ==========================================
exit /b 1

:usage
echo Usage: %~nx0 [ui^|server] [--no-check]
echo   ui         - Run the desktop application (default)
echo   --no-check - Skip quality checks (ruff, mypy)
exit /b 1

:end
endlocal
