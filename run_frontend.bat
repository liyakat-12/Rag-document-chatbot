@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python virtualenv...
  py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv
  call .venv\Scripts\pip install -r requirements.txt
)
call .venv\Scripts\activate
echo Starting DocuMind UI on http://localhost:8501 ...
echo The UI auto-discovers the DocuMind backend on 8000 or 8001.
echo Make sure run_backend.bat is running first for a dedicated API process.
streamlit run streamlit_app/app.py --server.port 8501
