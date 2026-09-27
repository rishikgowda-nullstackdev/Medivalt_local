@echo off
chcp 65001 >nul
title MediVault Local - Zero-Cloud Clinical Record Reviewer
color 0A

cd /d "%~dp0"

echo =====================================================================
echo  MediVault Local - Offline Clinical Reviewer (Zero-Cloud Mode)
echo  HIPAA Security Rule Section 164.312(b) ^& DPDP Compliant
echo =====================================================================
echo.

echo [1/2] Checking Python environment and dependencies...
python -m pip install -r requirements.txt --quiet

echo.
echo [2/2] Launching MediVault Local workstation...
python run_server.py

pause
