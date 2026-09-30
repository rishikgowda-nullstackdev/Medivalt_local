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

@echo off
chcp 65001 >nul
title MediVault Local - Zero-Cloud Clinical Reviewer
color 0A

cd /d "%~dp0"

echo =====================================================================
echo  MediVault Local - Offline Clinical Reviewer (Zero-Cloud Mode)
echo =====================================================================
echo.
echo Starting local environment...
echo.

python run_server.py

pause


