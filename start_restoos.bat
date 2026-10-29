@echo off
title RestoOS POS & Hotel Operations System
echo ===============================================================
echo   RestoOS — Modern Restaurant, Bar & Two-Tier Inventory Engine
echo   Koregaon Park, Pune (Bilingual English / Marathi)
echo ===============================================================
echo.
echo Starting RestoOS local server...

if exist "dist\RestoOS.exe" (
    echo Launching compiled Standalone Executable...
    start "" "dist\RestoOS.exe"
) else (
    echo Launching via Python desktop launcher...
    start "" python run_desktop.py
)

echo.
echo Application started! Your browser will open automatically at http://127.0.0.1:8000/
echo You can minimize this window.
timeout /t 3 >nul
