# LegalEase - AI-Powered Legal Document Generator

Generate employment contracts, lease agreements, NDAs, freelance, partnership and loan agreements from a simple form.
Edit the draft in the browser, then download it as **PDF, DOCX or TXT** with your logo, an automatic key-terms table and a footer.

**Stack:** FastAPI (backend) - Streamlit (frontend) - Google Gemini (AI) - python-docx / ReportLab (export)

## Quick start (VS Code terminal, from this folder)

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
```

Open `.env` and set `GEMINI_API_KEY=...` (get a key at https://aistudio.google.com/apikey).

Run the two servers (two terminals):

```bash
uvicorn legalEaseAPI.main:app --reload --port 8000    # backend  -> http://localhost:8000/docs
streamlit run frontend/app.py                         # frontend -> http://localhost:8501
```

Or just run `run.bat` (Windows) / `./run.sh` (macOS/Linux).

## Try it without an API key
Set `LEGALEASE_MOCK=1` in `.env` and restart the backend. A template document is returned instead of calling Gemini.

## Tests
```bash
pip install -r requirements-dev.txt
pytest -q
```

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Status, model, whether a key is configured |
| GET | `/doc-types` | Document types and languages |
| POST | `/generate` | Draft a document from the form fields |
| POST | `/export` | Convert (edited) text to `pdf`, `docx` or `txt` |

## Tamil / Hindi PDFs
Choose the language in the form. For **PDF** export of non-Latin scripts, put a Unicode font at `fonts/pdf_font.ttf`
(e.g. Noto Sans Tamil or Noto Sans Devanagari; optional `fonts/pdf_font_bold.ttf`). DOCX and TXT work without it.

## Your own logo
Replace `Image/Logo.png` (dark logo, used in documents) and `Image/inverseLogo.png` (light logo, used in the dark web UI),
or regenerate the placeholders with `python tools/generate_logo.py`.

## Project structure
```
LegalEase/
  ai_core/         gemini_generator.py (Gemini + mock), generator.py (PDF/DOCX/TXT), text_utils.py
  legalEaseAPI/    main.py, routes.py
  frontend/        app.py (Streamlit UI)
  tools/           generate_logo.py
  tests/           test_legalease.py
  Image/  fonts/  docs/  .streamlit/
  config.py  requirements.txt  requirements-dev.txt  .env.example  run.sh  run.bat
```

## Deploy (optional)
- **Backend on Render:** build `pip install -r requirements.txt`, start `uvicorn legalEaseAPI.main:app --host 0.0.0.0 --port $PORT`,
  add environment variable `GEMINI_API_KEY`.
- **Frontend on Streamlit Community Cloud:** main file `frontend/app.py`; in *Secrets* set `API_URL = "https://your-render-url"`.

## Security notes
- The API key lives only in `.env` (ignored by Git) or in your host's environment variables. Never commit it or paste it in chat.
- Document contents are not logged or stored by this app.
- If a key was ever exposed, delete it in Google AI Studio and create a new one.

## Disclaimer
AI output is a draft, not legal advice. Have a qualified lawyer review any document before signing.
