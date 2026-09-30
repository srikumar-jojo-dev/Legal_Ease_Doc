"""Small helpers: clean AI output, parse it into blocks, build the terms table."""
import re
from xml.sax.saxutils import escape as _xml_escape

_FENCE = re.compile(r"^```[a-zA-Z]*\s*$", re.M)


def clean_ai_text(text: str) -> str:
    """Remove code fences / markdown emphasis and tidy blank lines."""
    text = (text or "").replace("\r\n", "\n")
    text = _FENCE.sub("", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_blocks(text: str):
    """Yield (kind, text) where kind is h1, h2, bullet or para."""
    blocks = []
    for raw in clean_ai_text(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith(("- ", "• ")):
            blocks.append(("bullet", line[2:].strip()))
        elif re.match(r"^(ARTICLE|SECTION|CLAUSE)\s+\d+", line, re.I) and len(line) < 90:
            blocks.append(("h2", line))
        else:
            blocks.append(("para", line))
    return blocks


def xml_escape(text: str) -> str:
    return _xml_escape(text or "")


def safe_filename(title: str, ext: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", (title or "document")).strip("_")[:60] or "document"
    return f"{stem}.{ext}"


def build_terms_table(data: dict):
    """Automatic terms table built from the form inputs."""
    rows = [
        ("Document type", data.get("doc_type", "")),
        ("Party A", data.get("party_a", "")),
        ("Party B", data.get("party_b", "")),
        ("Effective date", data.get("effective_date", "")),
        ("Governing law / jurisdiction", data.get("jurisdiction", "")),
    ]
    for line in (data.get("key_terms") or "").split("\n"):
        line = line.strip(" -•\t")
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append((k.strip()[:60], v.strip()))
        else:
            rows.append(("Term", line))
    return [(k, v) for k, v in rows if v]
