"""Export conversation history as a PDF download."""

from __future__ import annotations

import io
from datetime import datetime

from fpdf import FPDF


class ConversationPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, _safe("RAG Document Chatbot - Conversation"), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def export_conversation_pdf(
    title: str,
    messages: list[dict],
) -> bytes:
    """Render a chat transcript to PDF bytes."""
    pdf = ConversationPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, _safe(title))
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = _safe(msg.get("content", ""))
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, role, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, content)
        confidence = msg.get("confidence")
        if confidence is not None and role == "ASSISTANT":
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, f"Confidence: {confidence:.0%}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()


def _safe(text: str) -> str:
    """FPDF core fonts need latin-1; replace unsupported chars."""
    return (text or "").encode("latin-1", "replace").decode("latin-1")
