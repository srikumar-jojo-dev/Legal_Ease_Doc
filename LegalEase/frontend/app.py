"""Streamlit UI:  streamlit run frontend/app.py"""
import sys
from datetime import date
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

st.set_page_config(page_title="LegalEase", page_icon="⚖️", layout="wide")


def api_get(path):
    return requests.get(f"{config.API_URL}{path}", timeout=15)


def error_text(resp):
    try:
        return resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text


with st.sidebar:
    if Path(config.WEB_LOGO_PATH).exists():
        st.image(str(config.WEB_LOGO_PATH), use_container_width=True)
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
        party_a = st.text_input("Party A (name)")
        party_b = st.text_input("Party B (name)")
        eff = st.date_input("Effective date", value=date.today())
        jurisdiction = st.text_input("Governing law / jurisdiction", value="India")
        language = st.selectbox("Language", meta["languages"])
        key_terms = st.text_area(
            "Key terms (one per line, e.g. `Rent: Rs. 15,000 per month`)", height=150)
        submitted = st.form_submit_button("Generate document", type="primary")

    if submitted:
        if not party_a.strip() or not party_b.strip():
            st.error("Please enter both party names.")
        else:
            payload = {"doc_type": doc_type, "party_a": party_a.strip(), "party_b": party_b.strip(),
                       "effective_date": eff.strftime("%d %B %Y"), "jurisdiction": jurisdiction.strip() or "India",
                       "key_terms": key_terms.strip(), "language": language}
            with st.spinner("Drafting your document..."):
                try:
                    r = requests.post(f"{config.API_URL}/generate", json=payload, timeout=config.REQUEST_TIMEOUT)
                except requests.RequestException as exc:
                    st.error(f"Request failed: {exc}")
                else:
                    if r.ok:
                        st.session_state["doc"] = r.json()
                        st.session_state["editor"] = r.json()["text"]
                    else:
                        st.error(error_text(r))

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
