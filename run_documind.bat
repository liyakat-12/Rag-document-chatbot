@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ── DocuMind AI — one-command local startup (Windows) ─────────────────────
REM Starts FastAPI backend + Streamlit UI. Skips services that are already up.
REM Logs: .uvicorn_out.log / .uvicorn_err.log / .streamlit_out.log / .streamlit_err.log

if not exist .venv (
  echo Creating Python virtualenv...
  py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv
  if not exist .venv\Scripts\python.exe (
    echo ERROR: Could not create .venv. Install Python 3.11+ and retry.
    exit /b 1
  )
  call .venv\Scripts\pip install -r requirements.txt
  if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
  )
)
if not exist .env (
  copy .env.example .env >nul
  echo Created .env — extractive + local embeddings are the default.
)

call .venv\Scripts\activate

REM Prefer 8001 when 8000 is occupied by another app
set PORT=8000
netstat -ano | findstr ":8000 " | findstr LISTENING >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Port 8000 is in use — DocuMind backend will use 8001
  set PORT=8001
)

set UI_PORT=8501
set BACKEND_URL=http://127.0.0.1:%PORT%/api/v1/health
set UI_URL=http://127.0.0.1:%UI_PORT%

REM Detect already-running DocuMind backend
set BACKEND_UP=0
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200 -and $r.Content -match 'DocuMind') { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL%==0 set BACKEND_UP=1

if "%BACKEND_UP%"=="1" (
  echo Backend already healthy at %BACKEND_URL%
) else (
  echo Starting backend on port %PORT%...
  start "DocuMind Backend" /MIN cmd /c "cd /d ""%~dp0"" && call .venv\Scripts\activate && uvicorn backend.app.main:app --host 127.0.0.1 --port %PORT% >> .uvicorn_out.log 2>> .uvicorn_err.log"
  REM Wait for health (up to ~45s)
  set /a WAIT=0
  :wait_backend
  powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri '%BACKEND_URL%' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
  if %ERRORLEVEL%==0 goto backend_ready
  set /a WAIT+=1
  if %WAIT% GEQ 45 (
    echo ERROR: Backend did not become healthy. Check .uvicorn_err.log
    exit /b 1
  )
  timeout /t 1 /nobreak >nul
  goto wait_backend
  :backend_ready
  echo Backend ready → %BACKEND_URL%
)

REM Detect Streamlit already listening
set UI_UP=0
netstat -ano | findstr ":%UI_PORT% " | findstr LISTENING >nul 2>&1
if %ERRORLEVEL%==0 set UI_UP=1

if "%UI_UP%"=="1" (
  echo Streamlit already listening on %UI_PORT%
) else (
  echo Starting Streamlit UI on port %UI_PORT%...
  start "DocuMind UI" cmd /c "cd /d ""%~dp0"" && call .venv\Scripts\activate && streamlit run streamlit_app/app.py --server.port %UI_PORT% >> .streamlit_out.log 2>> .streamlit_err.log"
  timeout /t 3 /nobreak >nul
)

echo.
echo ────────────────────────────────────────────
echo  DocuMind AI
echo  UI      %UI_URL%
echo  API     http://127.0.0.1:%PORT%/docs
echo  Health  %BACKEND_URL%
echo  Logs    .uvicorn_*.log  .streamlit_*.log
echo ────────────────────────────────────────────
echo.
echo Tip: LLM_PROVIDER=extractive works offline. Existing run_backend.bat / run_frontend.bat still work.
start "" "%UI_URL%"
endlocal
exit /b 0
