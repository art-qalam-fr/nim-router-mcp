@echo off
TITLE AGENT Monitor ^& Ingestion
echo 🚀 Starting AGENT Monitor ^& Ingestion...
echo Port: 3055
echo.

REM Lancer le monitor en arrière-plan
start "AGENT Monitor" /B node .agent/scripts/monitor.js

REM Lancer l'ingestion automatique (PowerShell)
echo 🔍 Starting Auto-Ingestion...
start "AGENT Ingestion" /B powershell -ExecutionPolicy Bypass -File .agent/scripts/auto-ingest.ps1 -Mode auto

REM Lancer le Memory Bridge (Synchronisation unifiée)
echo 🌉 Starting Memory Bridge...
start "Memory Bridge" /B node .agent/scripts/memory-bridge.js

echo.
echo ✅ System is running.
echo Dashboard: http://localhost:3055
echo.
pause
