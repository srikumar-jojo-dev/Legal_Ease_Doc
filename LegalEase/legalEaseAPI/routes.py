"""API routes: /health, /doc-types, /generate, /export."""
import logging
from datetime import datetime
from typing import List, Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

import config
from ai_core import generator
from ai_core.gemini_generator import (DOC_TYPES, LANGUAGES, GeminiError,
                                      GeminiRateLimitError, GeminiTimeoutError,
                                      MissingKeyError, generate_document)
from ai_core.text_utils import build_terms_table, safe_filename

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    doc_type: str = Field(..., max_length=80)
    party_a: str = Field(..., min_length=1, max_length=200)
    party_b: str = Field(..., min_length=1, max_length=200)
    party_a_role: str = Field("Party A", max_length=80)
    party_b_role: str = Field("Party B", max_length=80)
    effective_date: str = Field(..., min_length=1, max_length=60)
    jurisdiction: str = Field("India", max_length=120)
    place_of_signing: str = Field("", max_length=200)
    key_terms: str = Field("", max_length=4000)
    language: str = Field("English", max_length=20)


class ExportRequest(BaseModel):
    format: Literal["pdf", "docx", "txt"]
    title: str = Field(..., max_length=200)
    text: str = Field(..., min_length=1, max_length=60000)
    terms: List[List[str]] = []
    include_logo: bool = True


@router.get("/health")
def health():
    return {"status": "ok", "mock": config.MOCK_MODE, "model": config.GEMINI_MODEL,
            "key_configured": bool(config.GEMINI_API_KEY)}


@router.get("/doc-types")
def doc_types():
    return {"doc_types": list(DOC_TYPES), "languages": LANGUAGES,
            "pdf_unicode_font": generator.custom_font_available()}


@router.post("/generate")
def generate(req: GenerateRequest):
    if req.doc_type not in DOC_TYPES:
        raise HTTPException(422, f"Unknown document type. Choose one of: {list(DOC_TYPES)}")
    if req.language not in LANGUAGES:
        raise HTTPException(422, f"Unsupported language. Choose one of: {LANGUAGES}")

    trimmed = {
        "doc_type": req.doc_type.strip(),
        "party_a": req.party_a.strip(),
        "party_b": req.party_b.strip(),
        "party_a_role": req.party_a_role.strip() or "Party A",
        "party_b_role": req.party_b_role.strip() or "Party B",
        "effective_date": req.effective_date.strip(),
        "jurisdiction": req.jurisdiction.strip() or "India",
        "place_of_signing": req.place_of_signing.strip(),
        "key_terms": req.key_terms.strip(),
        "language": req.language.strip(),
    }
    if not trimmed["party_a"] or not trimmed["party_b"]:
        raise HTTPException(422, "Both party names are required.")
    if trimmed["party_a"].lower() == trimmed["party_b"].lower():
        raise HTTPException(422, "Party A and Party B must be different people or entities.")
    if not trimmed["effective_date"]:
        raise HTTPException(422, "Effective date is required.")
    try:
        datetime.strptime(trimmed["effective_date"], "%d %B %Y")
    except ValueError:
        try:
            datetime.strptime(trimmed["effective_date"], "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(422, "Effective date must be a valid date.") from exc

    data = trimmed
    try:
        text = generate_document(data)
    except MissingKeyError as exc:
        logger.warning("Gemini key missing: %s", exc)
        raise HTTPException(503, exc.user_message)
    except GeminiError as exc:
        logger.error("Document generation failed: %s", exc)
        status_code = 429 if isinstance(exc, GeminiRateLimitError) else 504 if isinstance(exc, GeminiTimeoutError) else 502
        raise HTTPException(status_code, exc.user_message)
    title = next((l[2:].strip() for l in text.split("\n") if l.startswith("# ")), req.doc_type)
    return {"title": title, "text": text, "terms": build_terms_table(data)}


@router.post("/export")
def export(req: ExportRequest):
    terms = [(r[0], r[1]) for r in req.terms if len(r) >= 2]
    try:
        if req.format == "txt":
            data, mime = generator.build_txt(req.title, req.text, terms), "text/plain; charset=utf-8"
        elif req.format == "docx":
            data = generator.build_docx(req.title, req.text, terms, req.include_logo)
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            data, mime = generator.build_pdf(req.title, req.text, terms, req.include_logo), "application/pdf"
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception as exc:
        logger.error("Export (%s) failed: %s", req.format, exc, exc_info=True)
        raise HTTPException(500, f"Export failed: {exc}")
    name = safe_filename(req.title, req.format)
    return Response(content=data, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
