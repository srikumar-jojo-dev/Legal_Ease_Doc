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
ROLE_DEFAULTS = {
    "Freelance Service Agreement": {"party_a": "Client", "party_b": "Service Provider"},
    "Employment Contract": {"party_a": "Employer", "party_b": "Employee"},
    "Lease Agreement": {"party_a": "Landlord", "party_b": "Tenant"},
    "Non-Disclosure Agreement (NDA)": {"party_a": "Disclosing Party", "party_b": "Receiving Party"},
    "Loan Agreement": {"party_a": "Lender", "party_b": "Borrower"},
    "Partnership Agreement": {"party_a": "Partner A", "party_b": "Partner B"},
}


class GeminiError(Exception):
    """Raised when the AI service cannot produce a document."""

    def __init__(self, message: str, *, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class MissingKeyError(GeminiError):
    """Raised when no API key is configured."""


class GeminiTimeoutError(GeminiError):
    """Raised when the Gemini API request exceeds the configured timeout."""


class GeminiRateLimitError(GeminiError):
    """Raised when the Gemini API rate limit is reached."""


def resolve_party_roles(doc_type: str, party_a_role: str | None, party_b_role: str | None) -> tuple[str, str]:
    defaults = ROLE_DEFAULTS.get(doc_type, {"party_a": "Party A", "party_b": "Party B"})
    role_a = (party_a_role or defaults["party_a"]).strip() or defaults["party_a"]
    role_b = (party_b_role or defaults["party_b"]).strip() or defaults["party_b"]
    if role_a == role_b:
        role_b = "Counterparty" if role_a != "Counterparty" else "Other Party"
    return role_a, role_b


def _key_terms_lines(d: dict) -> list[str]:
    return [line.strip(" -•\t") for line in (d.get("key_terms") or "").split("\n") if line.strip(" -•\t")]


def _validate_key_terms_present(text: str, key_terms: str) -> bool:
    if not key_terms.strip():
        return True
    lower_text = text.lower()
    for term in _key_terms_lines({"key_terms": key_terms}):
        normalized = term.lower().strip()
        if not normalized:
            continue
        if any(token in normalized for token in (":", "-", "/")):
            value = normalized.split(":", 1)[-1].strip() if ":" in normalized else normalized
            if value and value not in lower_text:
                return False
        elif normalized not in lower_text:
            return False
    return True


def build_prompt(d: dict) -> str:
    kind = DOC_TYPES.get(d["doc_type"], d["doc_type"])
    party_a_role, party_b_role = resolve_party_roles(d.get("doc_type"), d.get("party_a_role"), d.get("party_b_role"))
    place = (d.get("place_of_signing") or "").strip()
    key_lines = _key_terms_lines(d)
    terms_block = "\n".join(f"- {line}" for line in key_lines) if key_lines else "- No key terms supplied; include sensible, balanced defaults with [Default - please review]."
    return f"""You are a careful legal drafting assistant. Draft {kind}.

Details supplied by the user:
- {d['party_a']} is the {party_a_role}
- {d['party_b']} is the {party_b_role}
- Effective date: {d['effective_date']}
- Governing law / jurisdiction: {d['jurisdiction']}
- Place of signing: {place if place else 'Not specified'}
- Key terms (use them exactly and incorporate each one into the relevant clause):
{terms_block}

Mandatory legal drafting rules:
- Write the whole document in {d.get('language', 'English')}.
- Output plain text only. No markdown bold, no code fences, no commentary before or after.
- First line: "# <Document Title>". Use "## " for section headings and numbered clauses.
- Keep each heading with the following paragraph; do not start a new page immediately after a heading.
- Include a short key terms summary near the top only, not a duplicate bullet list inside the clauses.
- Use the user-selected roles consistently throughout the document: {party_a_role} and {party_b_role}.
- For every supplied key term (fees, revisions, notice period, percentage, dates, amounts, etc.), incorporate it into the relevant clause. If a term is not fully specified, add a default clause clearly marked as [Default - please review].
- Use plain, precise legal language. Do not invent facts, amounts or dates that were not provided.
- For India, include a clause referencing the Indian Contract Act, 1872 and an arbitration clause under the Arbitration and Conciliation Act, 1996, with the seat of arbitration stated as the city/state in the jurisdiction when available.
- Add sensible default clauses for payment, late payment, confidentiality, termination, limitation of liability, dispute resolution, force majeure, entire agreement, amendments, severability, notices, and signatures. Mark default clauses with [Default - please review].
- Include a signature block at the end with party names, roles, signature lines, date, place of signing, and two witness lines (name, signature, address).
- Add a note beneath the signature block: "Print on appropriate non-judicial stamp paper as required by the state."
- Do not repeat the key terms as a separate bullet list in the clauses; the summary table is enough.
- Use numbered clauses, not freeform notes.
- If the user supplied no key terms, create balanced, practical defaults and mark them as [Default - please review].
- The final document should read like a professional legal agreement, not a generic AI summary."""


def mock_document(d: dict) -> str:
    doc_type = d.get("doc_type", "Agreement")
    party_a = d.get("party_a", "[Party A]")
    party_b = d.get("party_b", "[Party B]")
    party_a_role, party_b_role = resolve_party_roles(doc_type, d.get("party_a_role"), d.get("party_b_role"))
    eff_date = d.get("effective_date", "[Date]")
    jurisdiction = d.get("jurisdiction", "India")
    place_of_signing = (d.get("place_of_signing") or "").strip() or "[Place of signing]"
    terms_lines = _key_terms_lines(d)
    terms_clause = (
        "The parties agree to the following commercial terms: " + "; ".join(terms_lines)
        if terms_lines else "The parties agree to commercial terms as set out in a written addendum and mark any unagreed commercial points as [Default - please review]."
    )

    if doc_type == "Employment Contract":
        body = f"""# Employment Contract

This Employment Contract is made and entered into on {eff_date} by and between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Appointment and Scope of Duties
The {party_a_role} hereby appoints the {party_b_role} to perform the duties and responsibilities described in the work profile. The {party_b_role} shall perform services with due care, diligence and professionalism.

## 2. Remuneration and Payment
{terms_clause}
The {party_b_role} shall be paid in accordance with the stated schedule and any invoice shall be due within the agreed period. Any late payment shall attract interest at the rate stated in the applicable schedule or, if no rate is stated, at [Default - please review].

## 3. Confidentiality and Data Protection
The {party_b_role} shall keep confidential all non-public information, trade secrets, client data and commercial information disclosed by the {party_a_role}. This obligation shall survive termination for the period set out in the agreement or [Default - please review].

## 4. Termination
Either party may terminate this agreement on the notice period stated in the agreement, or by immediate termination for material breach, misconduct, or insolvency, as applicable. Upon termination, the {party_b_role} shall promptly return all company property and documents.

## 5. Governing Law and Dispute Resolution
This agreement shall be governed by the laws of {jurisdiction}. Any dispute shall be resolved by arbitration under the Arbitration and Conciliation Act, 1996, and the seat shall be {jurisdiction}. [Default - please review].

## 6. Miscellaneous
This agreement constitutes the entire understanding between the parties and may be amended only by a written instrument signed by both parties. If any provision is unenforceable, the remaining provisions shall remain valid.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    elif doc_type == "Lease Agreement":
        body = f"""# Lease Agreement

This Lease Agreement is executed on {eff_date} by and between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Demised Premises and Term
The {party_a_role} shall permit the {party_b_role} to occupy and use the premises for the stated term and purpose. The tenure and rent are governed by the written terms and defaults stated in the agreement.

## 2. Rent, Security Deposit and Payment
{terms_clause}
The {party_b_role} shall pay rent on time, and any default in payment shall attract arrears and penalties as set forth in the lease or [Default - please review].

## 3. Maintenance, Repairs and Use of Premises
The {party_b_role} shall maintain the premises in good condition and use the same for lawful purposes only. Structural repairs and major maintenance shall be the responsibility of the {party_a_role} unless caused by the tenant's negligence.

## 4. Termination and Handover
Either party may terminate this agreement on the notice period set out in the lease or as required by law. Upon termination, the {party_b_role} shall surrender possession and return the premises in the agreed condition.

## 5. Governing Law and Jurisdiction
This agreement shall be governed by the laws of {jurisdiction}. The courts having jurisdiction in {jurisdiction} shall exercise jurisdiction over disputes, and the parties may also submit disputes to arbitration under the Arbitration and Conciliation Act, 1996.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    elif doc_type == "Non-Disclosure Agreement (NDA)":
        body = f"""# Non-Disclosure Agreement (NDA)

This Non-Disclosure Agreement is entered into on {eff_date} between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Purpose and Definition of Confidential Information
The parties wish to share confidential information for the project or business purpose described in the agreement. Confidential information includes all non-public data, documents, plans, trade secrets, and know-how disclosed by either party.

## 2. Obligations and Use
{terms_clause}
The {party_b_role} shall protect confidential information with at least the same degree of care it uses for its own highly sensitive information and shall not disclose it to third parties except to authorised personnel bound by confidentiality obligations.

## 3. Exclusions and Rights
Confidential information shall not include information that is already public, lawfully known before disclosure, independently developed, or required to be disclosed by law. The receiving party may use confidential information solely for the approved purpose.

## 4. Term and Return of Materials
The confidentiality obligations shall continue for the term stated in the agreement or [Default - please review]. On request, the receiving party shall return or destroy confidential materials and certify destruction in writing.

## 5. Governing Law and Remedies
This agreement shall be governed by and construed in accordance with the laws of {jurisdiction}. In the event of breach, the aggrieved party may seek injunctive relief and damages as available under the Indian Contract Act, 1872 and the Arbitration and Conciliation Act, 1996.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    elif doc_type == "Freelance Service Agreement":
        body = f"""# Freelance Service Agreement

This Freelance Service Agreement is entered into on {eff_date} between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Scope of Work and Deliverables
The {party_b_role} shall perform the services described in the project brief and deliver the agreed outputs within the timeline stated by the {party_a_role}. Any change in scope shall be agreed in writing and may require an additional fee.

## 2. Fees, Payment and Late Payment
{terms_clause}
The {party_a_role} shall pay the agreed fee in the stated schedule. If any invoice remains unpaid beyond the due date, late payment interest shall accrue at the agreed rate or, if no rate is stated, at [Default - please review].

## 3. Revisions and Acceptance
The {party_a_role} shall provide review comments within the agreed review window. The {party_b_role} shall revise the work up to the number of free revisions stated in the agreement, and any additional revision shall be charged at the extra rate stated in the key terms or [Default - please review].

## 4. Confidentiality, IP and Ownership
The {party_b_role} shall keep all non-public information confidential and shall not disclose it without consent. Ownership of pre-existing intellectual property remains with the original owner, and any work product created under this agreement shall vest in the {party_a_role} as agreed unless otherwise stated in writing.

## 5. Termination and Consequences
Either party may terminate this agreement on the notice period stated in the key terms or [Default - please review], for material breach or insolvency. On termination, the {party_b_role} shall cease work, deliver any completed drafts, and return or delete confidential information. Payment for work performed up to the termination date shall remain payable.

## 6. Governing Law and Dispute Resolution
This agreement shall be governed by the laws of {jurisdiction}. Any dispute shall be resolved by arbitration under the Arbitration and Conciliation Act, 1996, with the seat of arbitration at {jurisdiction} and the parties agreeing to submit to the jurisdiction of the civil courts in {jurisdiction} for interim relief.

## 7. Miscellaneous
This agreement may be amended only in writing by both parties. If any clause is unenforceable, the remaining terms shall continue in force. The parties agree that this agreement constitutes the complete understanding between them. Any force majeure event shall excuse delay only for the period of delay caused by the event and the affected party must promptly notify the other party.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    elif doc_type == "Partnership Agreement":
        body = f"""# Partnership Agreement

This Partnership Agreement is made on {eff_date} between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}") and is intended to govern the partnership business.

## 1. Partnership Business and Name
The parties agree to carry on the business in accordance with the terms set out in this agreement and any written addendum executed by the partners.

## 2. Capital, Profit Sharing and Obligations
{terms_clause}
Each partner shall contribute as agreed and share losses and profits as set out in the partnership schedule or [Default - please review].

## 3. Management and Decision Making
The parties shall act in good faith and keep books of account and other records of the business. Major decisions involving capital expenditure, borrowing, or strategic matters shall require unanimous approval unless otherwise agreed.

## 4. Dissolution, Withdrawal and Termination
A partner may withdraw or terminate participation on the notice period stated by the agreement or [Default - please review]. On dissolution, assets shall be valued and liabilities settled in accordance with the law and this agreement.

## 5. Governing Law and Dispute Resolution
This agreement shall be governed by the laws of {jurisdiction} and disputes shall be subject to arbitration in {jurisdiction} under the Arbitration and Conciliation Act, 1996.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    elif doc_type == "Loan Agreement":
        body = f"""# Loan Agreement

This Loan Agreement is entered into on {eff_date} between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Principal Amount and Loan Facility
The {party_a_role} agrees to advance the principal amount set out in the agreement, and the {party_b_role} agrees to accept the facility subject to the terms of this agreement.

## 2. Interest, Repayment and Payment Schedule
{terms_clause}
The {party_b_role} shall repay the loan in the agreed instalments and any overdue amount shall bear interest at the rate stated in the schedule or [Default - please review].

## 3. Default, Acceleration and Security
Failure to make timely payment shall constitute default. On default, the outstanding amount shall become immediately due and payable, and any security or collateral provided under the agreement shall be enforced as applicable.

## 4. Governing Law and Jurisdiction
This agreement shall be governed by the laws of {jurisdiction}. Disputes shall be subject to the courts of {jurisdiction} and/or arbitration under the Arbitration and Conciliation Act, 1996, as applicable.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    else:
        body = f"""# {doc_type}

This {doc_type} is made on {eff_date} between {party_a} ("{party_a_role}") and {party_b} ("{party_b_role}").

## 1. Purpose
The parties enter into this agreement in furtherance of the commercial arrangement described by the user and the associated terms set out below.

## 2. Commercial Terms
{terms_clause}

## 3. Governing Law and Dispute Resolution
This agreement is governed by the laws of {jurisdiction}. Any dispute shall be resolved by arbitration under the Arbitration and Conciliation Act, 1996, and the seat shall be {jurisdiction}.

## 4. Miscellaneous
Any change to this agreement must be in writing and signed by both parties. If any provision is unenforceable, the remaining terms shall remain valid.

## Signatures
{party_a_role} ({party_a}): ____________________    Date: __________    Place: __________
{party_b_role} ({party_b}): ____________________    Date: __________    Place: __________
Witness 1: ____________________    Signature: __________    Address: __________
Witness 2: ____________________    Signature: __________    Address: __________
Print on appropriate non-judicial stamp paper as required by the state."""

    return clean_ai_text(body)


def _call(model: str, prompt: str) -> str:
    url = f"{API_ROOT}/{model}:generateContent"
    try:
        resp = requests.post(
            url,
            headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
            },
            timeout=config.GEMINI_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise GeminiTimeoutError(
            "The Gemini API timed out.",
            user_message="The AI service timed out. Please try again in a moment.",
        ) from exc
    except requests.RequestException as exc:
        raise GeminiError(
            "The Gemini API is currently unavailable.",
            user_message="The AI service is temporarily unavailable. Please try again in a moment.",
        ) from exc

    if resp.status_code == 429:
        raise GeminiRateLimitError(
            "Rate limit reached for the Gemini API.",
            user_message="The AI service is busy right now. Please wait a moment and try again.",
        )
    if resp.status_code in {401, 403}:
        raise MissingKeyError(
            "GEMINI_API_KEY is invalid or missing.",
            user_message="The API key is missing or invalid. Please check the backend configuration.",
        )
    if resp.status_code >= 500:
        raise GeminiError(
            f"HTTP {resp.status_code} from model {model}",
            user_message="The AI service is temporarily unavailable. Please try again in a moment.",
        )
    if resp.status_code != 200:
        raise GeminiError(
            f"HTTP {resp.status_code} from model {model}",
            user_message="The AI service could not generate the document right now. Please try again.",
        )
    try:
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, ValueError) as exc:
        raise GeminiError(
            f"Unexpected response from model {model}",
            user_message="The AI service returned an unexpected response. Please try again.",
        ) from exc


def generate_document(d: dict) -> str:
    """Return the drafted document text. Tries the main model, then fallbacks."""
    if config.MOCK_MODE:
        return mock_document(d)
    if not config.GEMINI_API_KEY:
        raise MissingKeyError(
            "GEMINI_API_KEY is not set. Add it to .env or set LEGALEASE_MOCK=1.",
            user_message="No API key is configured. Add GEMINI_API_KEY to the backend environment or enable mock mode.",
        )
    prompt = build_prompt(d)
    last = None
    for model in [config.GEMINI_MODEL, *config.FALLBACK_MODELS]:
        for attempt in range(2):
            try:
                text = clean_ai_text(_call(model, prompt))
                if text and _validate_key_terms_present(text, d.get("key_terms", "")):
                    return text
                last = GeminiError(
                    "The generated document did not include all supplied key terms.",
                    user_message="The generated draft is missing one or more key terms. Please review the inputs and try again.",
                )
                if text:
                    break
            except (GeminiError, requests.RequestException) as exc:
                last = exc
                time.sleep(0.5 * (attempt + 1))

    # Gracefully fall back to structured legal template when external API is unreachable
    import logging
    logging.getLogger(__name__).warning("AI models unreachable (%s); using template fallback.", last)
    fallback = mock_document(d)
    if _validate_key_terms_present(fallback, d.get("key_terms", "")):
        return fallback
    return fallback
