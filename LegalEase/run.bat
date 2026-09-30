@echo off
start "LegalEase API" cmd /k uvicorn legalEaseAPI.main:app --port 8000
streamlit run frontend/app.py
