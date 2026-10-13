@echo off
cd /d "%~dp0"
start "Backend (port 8000)" cmd /k "venv\Scripts\activate && uvicorn server:app --port 8000"
start "Frontend (port 5173)" cmd /k "cd frontend && npm run dev"
timeout /t 10 >nul
start http://127.0.0.1:5173
