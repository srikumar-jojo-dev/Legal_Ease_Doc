"""Gemini-powered document generation (with a mock mode for testing without a key)."""
import time

import requests

import config
from ai_core.text_utils import clean_ai_text

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"

DOC_TYPES = {
    "Employment Contract": "an employment contract covering role, duties, salary, probation, working hours, leave, confidentiality, notice period and termination",
    "Lease Agreement": "a residential or commercial lease covering premises, rent, security deposit, term, maintenance, use of premises, renewal and termination",
    "Non-Disclosure Agreement (NDA)": "a mutual or one-way NDA covering definition of confidential information, obligations, exclusions, term, return of materials and remedies",
    "Freelance Service Agreement": "a freelance/service agreement covering scope of work, deliverables, timeline, fees, payment schedule, revisions, IP ownership and termination",
    "Partnership Agreement": "a partnership agreement covering capital contribution, profit sharing, roles, decision making, withdrawal and dissolution",
    "Loan Agreement": "a loan agreement covering principal, interest, repayment schedule, default, prepayment and governing law",
}
LANGUAGES = ["English", "Tamil", "Hindi"]


class GeminiError(Exception):
    """Raised when the AI service cannot produce a document."""


class MissingKeyError(GeminiError):
    """Raised when no API key is configured."""


def build_prompt(d: dict) -> str:
    kind = DOC_TYPES.get(d["doc_type"], d["doc_type"])
    return f"""You are a careful legal drafting assistant. Draft {kind}.

Details supplied by the user:
- Party A: {d['party_a']}
- Party B: {d['party_b']}
- Effective date: {d['effective_date']}
- Governing law / jurisdiction: {d['jurisdiction']}
- Key terms (use them exactly):
{d.get('key_terms') or '(none given - use sensible, balanced defaults)'}

Rules:
- Write the whole document in {d.get('language', 'English')}.
- Output plain text only. No markdown bold, no code fences, no commentary before or after.
- First line: "# <Document Title>". Use "## " for section headings and numbered clauses.
- Use "- " for bullet lists. Include a signature block for both parties at the end.
- Do not invent facts (names, amounts, addresses) that were not given; use [BLANK] placeholders instead.
- Keep the language clear and professional."""


def mock_document(d: dict) -> str:
    return clean_ai_text(f"""# {d['doc_type']}

This {d['doc_type']} is made on {d['effective_date']} between {d['party_a']} ("Party A") and {d['party_b']} ("Party B").

## 1. Purpose
The parties enter into this agreement on the terms set out below.

## 2. Key Terms
{d.get('key_terms') or '- To be agreed between the parties.'}

## 3. Governing Law
This agreement is governed by the laws of {d['jurisdiction']}.

## 4. General
- Any change must be in writing and signed by both parties.
- This is a MOCK template generated for testing.

## Signatures
Party A: ____________________    Date: __________
Party B: ____________________    Date: __________""")


def _call(model: str, prompt: str) -> str:
    url = f"{API_ROOT}/{model}:generateContent"
    resp = requests.post(
        url,
        headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
        },
        timeout=config.GEMINI_TIMEOUT,
    )
    if resp.status_code != 200:
        raise GeminiError(f"HTTP {resp.status_code} from model {model}")
    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, ValueError) as exc:
        raise GeminiError(f"Unexpected response from model {model}") from exc


def generate_document(d: dict) -> str:
    """Return the drafted document text. Tries the main model, then fallbacks."""
    if config.MOCK_MODE:
        return mock_document(d)
    if not config.GEMINI_API_KEY:
        raise MissingKeyError("GEMINI_API_KEY is not set. Add it to .env or set LEGALEASE_MOCK=1.")
    prompt = build_prompt(d)
    last = None
    for model in [config.GEMINI_MODEL, *config.FALLBACK_MODELS]:
        for attempt in range(2):
            try:
                text = clean_ai_text(_call(model, prompt))
                if text:
                    return text
                last = GeminiError("Empty response")
            except (GeminiError, requests.RequestException) as exc:
                last = exc
                time.sleep(1.0 * (attempt + 1))
    raise GeminiError(f"All models failed. Last error: {last}")
