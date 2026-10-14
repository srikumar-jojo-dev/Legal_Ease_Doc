@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0..\.venv\Scripts\activate.bat" (
    call "%~dp0..\.venv\Scripts\activate.bat"
)
start "LegalEase API" cmd /k "uvicorn legalEaseAPI.main:app --host 0.0.0.0 --port 8000 --reload"
start "LegalEase Frontend" cmd /k "streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501"
exit /b 0
