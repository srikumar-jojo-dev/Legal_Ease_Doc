"""Run with:  pytest -q   (no API key needed - uses mock mode)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from ai_core import gemini_generator, generator, text_utils  # noqa: E402
from legalEaseAPI.main import app  # noqa: E402

client = TestClient(app)
PAYLOAD = {"doc_type": "Lease Agreement", "party_a": "Asha Rao", "party_b": "Ravi Kumar",
           "effective_date": "01 October 2026", "jurisdiction": "Tamil Nadu, India",
           "key_terms": "Rent: Rs. 15,000 per month\nDeposit: Rs. 45,000", "language": "English"}


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", True)


def test_health_and_types():
    assert client.get("/health").json()["status"] == "ok"
    assert "Lease Agreement" in client.get("/doc-types").json()["doc_types"]


def test_generate_returns_text_and_terms():
    r = client.post("/generate", json=PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert "Asha Rao" in body["text"]
    assert ("Rent", "Rs. 15,000 per month") in [tuple(t) for t in body["terms"]]


def test_generate_validation():
    assert client.post("/generate", json={**PAYLOAD, "doc_type": "Nope"}).status_code == 422
    assert client.post("/generate", json={**PAYLOAD, "party_a": ""}).status_code == 422


@pytest.mark.parametrize("fmt,magic", [("pdf", b"%PDF"), ("docx", b"PK"), ("txt", b"LEASE")])
def test_export_formats(fmt, magic):
    g = client.post("/generate", json=PAYLOAD).json()
    r = client.post("/export", json={"format": fmt, "title": g["title"], "text": g["text"], "terms": g["terms"]})
    assert r.status_code == 200 and r.content.startswith(magic)


def test_pdf_special_characters_do_not_break():
    r = client.post("/export", json={"format": "pdf", "title": "A & B <Test>",
                                     "text": "# T\n\n## 1. Clause\nPay R&D <fees> & more.", "terms": [["a", "b<c"]]})
    assert r.status_code == 200


def test_pdf_non_latin_without_font_gives_clear_error(monkeypatch):
    monkeypatch.setattr(config, "FONT_PATH", Path("does_not_exist.ttf"))
    r = client.post("/export", json={"format": "pdf", "title": "தலைப்பு", "text": "வணக்கம்", "terms": []})
    assert r.status_code == 422 and "font" in r.json()["detail"].lower()


def test_missing_key_gives_503(monkeypatch):
    monkeypatch.setattr(config, "MOCK_MODE", False)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    assert client.post("/generate", json=PAYLOAD).status_code == 503


def test_clean_ai_text_and_blocks():
    cleaned = text_utils.clean_ai_text("```\n**Bold** text\n```\n\n\n\nnext")
    assert cleaned == "Bold text\n\nnext"
    kinds = [k for k, _ in text_utils.parse_blocks("# T\n## H\n- b\nplain")]
    assert kinds == ["h1", "h2", "bullet", "para"]


def test_prompt_contains_inputs():
    p = gemini_generator.build_prompt({**PAYLOAD})
    assert "Asha Rao" in p and "Rent: Rs. 15,000" in p
