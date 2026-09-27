@echo off
chcp 65001 >nul
title MediVault Local - Zero-Cloud Clinical Record Reviewer
color 0A

echo =====================================================================
echo  MediVault Local - Offline Clinical Reviewer (Zero-Cloud Mode)
echo  HIPAA Security Rule Section 164.312(b) ^& DPDP Compliant
echo =====================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking dependencies...
python -m pip install -r requirements.txt --quiet

echo.
echo [2/3] Initializing local database...
python -c "from backend.main import init_db; init_db(); print('SQLite database ready.')"

echo.
echo [3/3] Preparing MediVault Local offline server...
:: Free port 8000 if occupied by a previous session
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo  Releasing port 8000 from previous background process (PID %%a)...
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo  =====================================================================
echo  Access Doctor Dashboard in your browser:
echo  URL: http://127.0.0.1:8000
echo  Patient Portal URL: http://127.0.0.1:8000/patient-portal
echo.
echo  Press CTRL+C to terminate the local server.
echo  =====================================================================
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
