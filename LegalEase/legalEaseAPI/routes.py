"""API routes: /health, /doc-types, /generate, /export."""
import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

import config
from ai_core import generator
from ai_core.gemini_generator import (DOC_TYPES, LANGUAGES, GeminiError,
                                      MissingKeyError, generate_document)
from ai_core.text_utils import build_terms_table, safe_filename

logger = logging.getLogger(__name__)
router = APIRouter()


class GenerateRequest(BaseModel):
    doc_type: str = Field(..., max_length=80)
    party_a: str = Field(..., min_length=1, max_length=200)
    party_b: str = Field(..., min_length=1, max_length=200)
    effective_date: str = Field(..., min_length=1, max_length=60)
    jurisdiction: str = Field("India", max_length=120)
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
    data = req.model_dump()
    try:
        text = generate_document(data)
    except MissingKeyError as exc:
        raise HTTPException(503, str(exc))
    except GeminiError as exc:
        logger.error("Document generation failed: %s", exc)
        raise HTTPException(502, f"The AI service could not generate the document: {exc}")
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
