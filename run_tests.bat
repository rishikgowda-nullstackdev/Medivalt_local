@echo off
title MediVault Local - Complete Verification & Compliance Test Suite
color 0B

echo =====================================================================
echo  MediVault Local - Automated Clinical Compliance Suite
echo  117 Tests across 17 Modules (HIPAA § 164.312(b) & DPDP Compliant)
echo =====================================================================
echo.

cd /d "%~dp0"

echo Running full unittest suite...
echo.
python -m unittest discover -s tests -p "*.py" -v

echo.
echo =====================================================================
echo  Verification complete. Press any key to exit.
echo =====================================================================
pause
