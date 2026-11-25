@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python virtualenv...
  py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv
  call .venv\Scripts\pip install -r requirements.txt
)
if not exist .env (
  copy .env.example .env
  echo Created .env — extractive + local embeddings are the default.
)
call .venv\Scripts\activate

REM Prefer 8001 when 8000 is occupied by another app (common on this machine)
set PORT=8000
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Port 8000 is in use — starting DocuMind on 8001
  set PORT=8001
)

echo.
echo DocuMind backend → http://localhost:%PORT%
echo API docs         → http://localhost:%PORT%/docs
echo Health           → http://localhost:%PORT%/api/v1/health
echo.
echo Tip: LLM_PROVIDER=extractive works offline. Set openai in .env for synthesis.
echo.
uvicorn backend.app.main:app --host 0.0.0.0 --port %PORT%
