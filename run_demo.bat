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
REM Release port 8000 safely if occupied by a previous session
python -c "import subprocess, re; out = subprocess.run(['netstat', '-ano'], capture_output=True, text=True).stdout; [subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True) for pid in set(re.findall(r':8000\s+.*LISTENING\s+(\d+)', out))]"

echo.
echo =====================================================================
echo  Access Doctor Dashboard in your browser:
echo  URL: http://127.0.0.1:8000
echo  Patient Portal URL: http://127.0.0.1:8000/patient-portal
echo.
echo  Press CTRL+C to terminate the local server.
echo =====================================================================
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
