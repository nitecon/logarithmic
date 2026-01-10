@echo off
setlocal

echo ========================================
echo Logarithmic Build Script
echo ========================================
echo.

REM --- 0. Get Version from Git Tag ---
for /f "delims=" %%i in ('git describe --tags --abbrev=0 2^>nul') do set GIT_TAG=%%i
if defined GIT_TAG (
    REM Remove 'v' prefix if present
    set APP_VERSION=%GIT_TAG:v=%
) else (
    set APP_VERSION=1.0.0
)
echo == Building version: %APP_VERSION% ==
echo.

REM --- 1. Check Prerequisites ---
echo [1/5] Checking prerequisites...

REM Check if .venv exists
if not exist ".venv\" (
    echo ERROR: Virtual environment not found.
    echo Please run: python -m venv .venv
    echo Then: .venv\Scripts\pip.exe install -r requirements.txt
    pause
    exit /b 1
)

REM Check if pyinstaller is installed
.venv\Scripts\pip.exe show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    .venv\Scripts\pip.exe install pyinstaller --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)
echo Prerequisites OK.
echo.

REM --- 2. Kill Running Instances ---
echo [2/5] Checking for running instances...
taskkill /F /IM Logarithmic.exe >nul 2>&1
if errorlevel 1 (
    echo No running instances found.
) else (
    echo Killed running instance.
    timeout /t 2 /nobreak >nul
)
echo.

REM --- 3. Clean Previous Build ---
echo [3/5] Cleaning previous build...
if exist "build\" (
    echo Removing build directory...
    rmdir /s /q build
)
if exist "dist\" (
    echo Removing dist directory...
    rmdir /s /q dist
)
echo Clean complete.
echo.

REM --- 4. Set Environment and Build ---
echo [4/5] Building executable...
set PYTHONPATH=%CD%\src
set APP_VERSION=%APP_VERSION%

.venv\Scripts\pyinstaller.exe Logarithmic.spec

if errorlevel 1 (
    echo ERROR: Failed to build executable
    pause
    exit /b 1
)
echo.

REM --- 5. Verify Build ---
echo [5/5] Verifying build...
if not exist "dist\Logarithmic.exe" (
    echo ERROR: Build verification failed - executable not found
    pause
    exit /b 1
)

for %%A in ("dist\Logarithmic.exe") do echo Executable size: %%~zA bytes
echo.

echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Executable location: %CD%\dist\Logarithmic.exe
echo.
echo To run:
echo   .\dist\Logarithmic.exe
echo.

endlocal
