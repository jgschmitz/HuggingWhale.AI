import pytest

from whale_core.parsing import extract


def test_text_markdown_and_size_limit():
    assert extract(b"# hello", "notes.md", 100) == "# hello"
    with pytest.raises(ValueError):
        extract(b"too long", "notes.txt", 3)
    with pytest.raises(ValueError):
        extract(b"", "empty.txt", 100)
    with pytest.raises(ValueError):
        extract(b"x", "audio.mp3", 100)


def test_ui_starts_without_connections():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(timeout=15)
    assert not app.exception
    assert "connect" in app.info[0].value.lower()


def test_pdf_without_extractable_text_fails_clearly():
    from io import BytesIO
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    with pytest.raises(ValueError, match="OCR"):
        extract(buf.getvalue(), "scan.pdf", 1000)
