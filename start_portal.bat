@echo off
echo ========================================================
echo  Starting Med-Alert Recall Nexus Platform
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] Starting Backend FastAPI Server on http://localhost:8000 ...
start "Med-Alert Backend (Port 8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn server:app --host 0.0.0.0 --port 8000"

echo [2/2] Starting Frontend React Portal on http://localhost:3000 ...
start "Med-Alert Frontend (Port 3000)" cmd /k "cd /d %~dp0frontend && yarn start"

echo.
echo ========================================================
echo  Both services are starting!
echo  Backend:  http://localhost:8000 (API and Docs)
echo  Frontend: http://localhost:3000 (Recall Nexus Portal)
echo ========================================================
