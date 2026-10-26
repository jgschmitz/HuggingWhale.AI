"""Text extraction only. Voyage owns chunking and embeddings."""
from io import BytesIO
from pathlib import Path

ALLOWED = {".pdf", ".txt", ".md", ".csv", ".json"}


def extract(data: bytes, filename: str, max_chars: int) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("Supported uploads: PDF, TXT, MD, CSV, JSON")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs must be decrypted before uploading")
        parts, size = [], 0
        for page in reader.pages:
            value = page.extract_text() or ""
            size += len(value) + 1
            if size > max_chars:
                raise ValueError("Extracted document exceeds configured character limit")
            parts.append(value)
        text = "\n".join(parts)
    else:
        text = data.decode("utf-8-sig")
    text = text.replace("\x00", "").strip()
    if not text:
        raise ValueError("No extractable text; scanned PDFs require OCR before ingestion")
    if len(text) > max_chars:
        raise ValueError("Extracted document exceeds configured character limit")
    return text
