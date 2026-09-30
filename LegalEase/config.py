"""Central configuration for LegalEase (values come from .env / environment)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = "LegalEase"

# --- Gemini -------------------------------------------------------------------
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash,gemini-1.5-flash").split(",")
    if m.strip()
]
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "120"))
# Set LEGALEASE_MOCK=1 to return a template document without calling Gemini.
MOCK_MODE = os.getenv("LEGALEASE_MOCK", "0").strip().lower() in {"1", "true", "yes"}

# --- Frontend -> backend -------------------------------------------------------
API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "180"))
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

# --- Branding / assets ---------------------------------------------------------
LOGO_PATH = BASE_DIR / "Image" / "Logo.png"            # dark logo for white documents
WEB_LOGO_PATH = BASE_DIR / "Image" / "inverseLogo.png"  # light logo for the dark web UI
FONT_PATH = BASE_DIR / "fonts" / "pdf_font.ttf"         # optional (Tamil/Hindi PDFs)
FONT_BOLD_PATH = BASE_DIR / "fonts" / "pdf_font_bold.ttf"
COMPANY_FOOTER = "LegalEase | AI-assisted legal drafts | All Rights Reserved."
DISCLAIMER = (
    "AI-generated drafts are for convenience only and are not legal advice. "
    "Have a qualified lawyer review any document before signing."
)
