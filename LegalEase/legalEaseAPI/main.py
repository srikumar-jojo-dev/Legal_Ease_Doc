"""FastAPI application entry point:  uvicorn legalEaseAPI.main:app --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from legalEaseAPI.routes import router

app = FastAPI(title="LegalEase API", version="1.0.0",
              description="AI-powered legal document generator")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(router)
