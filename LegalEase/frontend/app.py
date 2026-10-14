"""Streamlit UI:  streamlit run frontend/app.py"""
import sys
from datetime import date
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

st.set_page_config(page_title="LegalEase", page_icon="⚖️", layout="wide")

st.markdown(
    """
    <style>
    .stSelectbox, .stDateInput, .stTextInput, .stTextArea {
        margin-bottom: 0.35rem;
    }
    div[data-testid="stForm"] div[data-baseweb="select"] > div,
    div[data-testid="stForm"] div[data-baseweb="select"] input,
    div[data-testid="stForm"] div[data-testid="stTextInputRootElement"],
    div[data-testid="stForm"] textarea,
    div[data-testid="stForm"] input {
        background: rgba(15, 23, 42, 0.85) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(148, 163, 184, 0.55) !important;
        border-radius: 0.65rem !important;
        box-shadow: none !important;
    }
    div[data-testid="stForm"] label {
        color: #e2e8f0 !important;
        font-weight: 600;
        letter-spacing: 0.01em;
    }
    div[data-testid="stForm"] code {
        color: #e2e8f0 !important;
        background: transparent !important;
        font-family: inherit !important;
    }
    div[data-testid="stSidebar"] {
        background: #0f172a;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_get(path):
    return requests.get(f"{config.API_URL}{path}", timeout=15)


def error_text(resp):
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            if isinstance(detail, list):
                return detail[0].get("msg", str(detail)) if detail else resp.text
        return str(payload)
    except ValueError:
        return resp.text


def friendly_error_message(resp):
    if resp is None:
        return "The app could not reach the backend. Please try again in a moment."
    if resp.status_code == 429:
        return "The AI service is busy right now. Please wait a moment and try again."
    if resp.status_code == 504:
        return "The AI service timed out. Please try again in a moment."
    if resp.status_code == 503:
        return "The backend is missing a valid API key or is temporarily unavailable."
    if resp.status_code >= 500:
        return "The AI service is temporarily unavailable. Please try again in a moment."
    return error_text(resp)


with st.sidebar:
    if Path(config.WEB_LOGO_PATH).exists():
        st.image(str(config.WEB_LOGO_PATH), width="stretch")
    st.caption(config.DISCLAIMER)

st.title("⚖️ LegalEase")
st.write("Generate a professional legal document draft, edit it, and download it as PDF, DOCX or TXT.")

try:
    meta = api_get("/doc-types").json()
    health = api_get("/health").json()
except requests.RequestException:
    st.error(f"Cannot reach the backend at {config.API_URL}. Start it with: "
             "`uvicorn legalEaseAPI.main:app --port 8000`")
    st.stop()

if health.get("mock"):
    st.info("Mock mode is ON - documents are test templates, not AI output.")
elif not health.get("key_configured"):
    st.warning("No GEMINI_API_KEY found on the backend. Add it to .env and restart the backend.")

left, right = st.columns([1, 1.4], gap="large")

with left:
    st.subheader("1. Details")
    with st.form("doc_form"):
        doc_type = st.selectbox("Document type", meta["doc_types"])
        party_a_role = st.selectbox(
            "Role of Party A",
            ["Client", "Service Provider", "Employer", "Employee", "Landlord", "Tenant",
             "Disclosing Party", "Receiving Party", "Lender", "Borrower", "Partner A", "Party A"],
            index=0,
        )
        party_a = st.text_input("Party A (name)")
        party_b = st.text_input("Party B (name)")
        party_b_role = {
            "Client": "Service Provider",
            "Service Provider": "Client",
            "Employer": "Employee",
            "Employee": "Employer",
            "Landlord": "Tenant",
            "Tenant": "Landlord",
            "Disclosing Party": "Receiving Party",
            "Receiving Party": "Disclosing Party",
            "Lender": "Borrower",
            "Borrower": "Lender",
            "Partner A": "Partner B",
            "Party A": "Party B",
        }.get(party_a_role, "Party B")
        eff = st.date_input("Effective date", value=date.today())
        jurisdiction = st.text_input("Governing law / jurisdiction", value="India")
        place_of_signing = st.text_input("Place of signing (optional)")
        language = st.selectbox("Language", meta["languages"])
        key_terms = st.text_area(
            "Key terms (one per line, for example: Rent: Rs. 15,000 per month)", height=150)
        submitted = st.form_submit_button("Generate document", type="primary")

    if submitted:
        errors = []
        if not party_a.strip() or not party_b.strip():
            errors.append("Please enter both party names.")
        if party_a.strip() and party_b.strip() and party_a.strip().lower() == party_b.strip().lower():
            errors.append("Party A and Party B must be different people or entities.")
        try:
            _ = eff.strftime("%d %B %Y")
        except Exception:
            errors.append("Please enter a valid effective date.")
        if errors:
            for msg in errors:
                st.error(msg)
        else:
            payload = {
                "doc_type": doc_type,
                "party_a": party_a.strip(),
                "party_b": party_b.strip(),
                "party_a_role": party_a_role,
                "party_b_role": party_b_role,
                "effective_date": eff.strftime("%d %B %Y"),
                "jurisdiction": jurisdiction.strip() or "India",
                "place_of_signing": place_of_signing.strip(),
                "key_terms": key_terms.strip(),
                "language": language,
            }
            with st.spinner("Drafting your document..."):
                try:
                    r = requests.post(f"{config.API_URL}/generate", json=payload, timeout=config.REQUEST_TIMEOUT)
                except requests.RequestException:
                    st.error(friendly_error_message(None))
                else:
                    if r.ok:
                        payload = r.json()
                        st.session_state["doc"] = payload
                        st.session_state["editor"] = payload["text"]
                    else:
                        st.error(friendly_error_message(r))

with right:
    st.subheader("2. Preview, edit & download")
    doc = st.session_state.get("doc")
    if not doc:
        st.write("Your document will appear here.")
    else:
        if doc["terms"]:
            st.markdown("**Key terms**")
            st.table({"Term": [t[0] for t in doc["terms"]], "Detail": [t[1] for t in doc["terms"]]})
        text = st.text_area("Editable document", key="editor", height=420)
        logo = st.checkbox("Include logo", value=True)

        # Clear cached exports when the user edits the document or toggles logo
        current_sig = (text, logo)
        if st.session_state.get("_export_sig") != current_sig:
            st.session_state["_export_sig"] = current_sig
            for k in ["_export_pdf", "_export_docx", "_export_txt"]:
                st.session_state.pop(k, None)

        cols = st.columns(3)
        for col, fmt in zip(cols, ["pdf", "docx", "txt"]):
            cache_key = f"_export_{fmt}"
            if col.button(f"Export {fmt.upper()}", key=f"btn_{fmt}"):
                body = {"format": fmt, "title": doc["title"], "text": text,
                        "terms": doc["terms"], "include_logo": logo}
                with st.spinner(f"Exporting {fmt.upper()}..."):
                    try:
                        resp = requests.post(f"{config.API_URL}/export", json=body, timeout=60)
                    except requests.RequestException:
                        col.error("Backend unreachable")
                        continue
                if resp.ok:
                    st.session_state[cache_key] = {
                        "content": resp.content,
                        "file_name": f"{doc['title'][:40].replace(' ', '_')}.{fmt}",
                        "mime": resp.headers.get("content-type", "application/octet-stream"),
                    }
                else:
                    col.warning(f"{fmt.upper()}: {error_text(resp)}")

            # Show the download button if we have cached export data
            cached = st.session_state.get(cache_key)
            if cached:
                col.download_button(f"Download {fmt.upper()}", cached["content"],
                                    file_name=cached["file_name"], mime=cached["mime"])
