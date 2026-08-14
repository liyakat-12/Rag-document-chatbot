@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python 3.12 virtualenv...
  py -3.12 -m venv .venv
  call .venv\Scripts\pip install -r requirements.txt
)
call .venv\Scripts\activate
echo Starting Streamlit UI on http://localhost:8501 ...
echo Make sure the backend is running on http://localhost:8000
streamlit run streamlit_app/app.py --server.port 8501
