@echo off
setlocal
cd /d "%~dp0"

echo ====================================================================
echo             RESET LOCAL REPO TO REMOTE (ORIGIN/MAIN)
echo ====================================================================
echo.
echo Target Remote : https://github.com/ShashankBoddu/stock.git
echo Branch        : main
echo.
echo WARNING: This will discard all local changes and reset your
echo          working directory to exactly match origin/main.
echo.

choice /c YN /m "Do you want to proceed with resetting to origin/main? [Y/N]"
if errorlevel 2 (
    echo.
    echo Reset cancelled. No changes were made.
    goto :end
)

echo.
echo [1/4] Checking Git installation...
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not found in PATH. Please install Git or add it to PATH.
    goto :error
)

echo [2/4] Verifying remote URL...
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    git remote add origin https://github.com/ShashankBoddu/stock.git
) else (
    git remote set-url origin https://github.com/ShashankBoddu/stock.git
)

echo [3/4] Fetching latest commits from origin/main...
git fetch origin main
if errorlevel 1 (
    echo ERROR: Failed to fetch from origin/main. Check your internet connection.
    goto :error
)

echo [4/4] Resetting local repository to origin/main...
git checkout -B main origin/main
git reset --hard origin/main
git clean -fd -e reset_to_remote.bat

echo.
echo ====================================================================
echo SUCCESS: Repository has been completely reset to origin/main!
echo Current commit:
git log -1 --oneline
echo ====================================================================
goto :end

:error
echo.
echo ====================================================================
echo FAILED: Repository reset could not be completed.
echo ====================================================================

:end
echo.
pause
