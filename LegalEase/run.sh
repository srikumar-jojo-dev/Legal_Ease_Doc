#!/usr/bin/env bash
# Starts backend (port 8000) and frontend (port 8501). Run from the project folder.
uvicorn legalEaseAPI.main:app --port 8000 &
BACK=$!
trap "kill $BACK" EXIT
streamlit run frontend/app.py
