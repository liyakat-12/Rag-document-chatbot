@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python 3.12 virtualenv...
  py -3.12 -m venv .venv
  call .venv\Scripts\pip install -r requirements.txt
)
if not exist .env (
  copy .env.example .env
  echo Created .env — free local mode is the default.
)
call .venv\Scripts\activate
echo.
echo Free mode: EMBEDDING_PROVIDER=local + LLM_PROVIDER=extractive
echo Starting backend on http://localhost:8000 ...
echo.
REM --reload disabled so installing packages into .venv does not crash the server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
