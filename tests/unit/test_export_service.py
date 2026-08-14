"""Unit tests for conversation PDF export."""

from backend.app.services.export_service import export_conversation_pdf


def test_export_pdf_with_ascii_content():
    pdf_bytes = export_conversation_pdf(
        "Simple chat",
        [
            {"role": "user", "content": "Hello there"},
            {"role": "assistant", "content": "Hi! How can I help?", "confidence": 0.8},
        ],
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0


def test_export_pdf_with_unicode_and_special_chars():
    """Regression test: header/content with em-dashes, curly quotes, etc.

    must not raise fpdf.errors.FPDFUnicodeEncodingException.
    """
    pdf_bytes = export_conversation_pdf(
        "Session — with an em dash and “curly quotes”",
        [
            {"role": "user", "content": "What about café résumé naïve — test?"},
            {
                "role": "assistant",
                "content": "Based on the uploaded documents (offline extractive mode) — here's the answer…",
                "confidence": 0.99,
            },
        ],
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0
