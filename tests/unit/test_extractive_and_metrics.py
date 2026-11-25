"""Regression: extractive punctuation matching + latency metrics."""

from langchain_core.messages import HumanMessage

from backend.app.rag.llm_factory import ExtractiveChatModel
from backend.app.rag.qa_chain import confidence_label, compute_confidence
from backend.app.utils.metrics import get_latency_stats, record_chat_timings
from langchain_core.documents import Document


def test_extractive_handles_punctuated_metadata_words():
    human = HumanMessage(
        content=(
            "Conversation summary (optional):\n(none)\n\n"
            "Recent conversation (optional):\n(none)\n\n"
            "Document context:\n"
            "[Source 1]\nDocument: resume.pdf\nPage: 1\nSource id: c1\nRelevance: 1.000\n"
            "Content:\nCandidate: Ada Lovelace\nSkill: Analytical Engine\n\n"
            "User question: Who is the candidate in the resume?\n\n"
            "Write a grounded answer based only on the document context above:"
        )
    )
    out = ExtractiveChatModel._extract_answer([human])
    assert "couldn't find" not in out.lower()
    assert "ada" in out.lower() or "lovelace" in out.lower()


def test_extractive_summary_returns_bullets():
    human = HumanMessage(
        content=(
            "Conversation summary (optional):\n(none)\n\n"
            "Recent conversation (optional):\n(none)\n\n"
            "Document context:\n"
            "[Source 1]\nDocument: deepfake.pdf\nPage: 1\nSource id: a\nRelevance: 1.000\n"
            "Content:\n"
            "Deepfake detection is important for media authenticity. "
            "The methodology uses a deep learning pipeline for visual data.\n\n"
            "---\n\n"
            "[Source 2]\nDocument: deepfake.pdf\nPage: 4\nSource id: b\nRelevance: 0.900\n"
            "Content:\n"
            "Audio approaches analyze spectral features and pitch variations in speech signals.\n\n"
            "User question: Summarize the main points.\n\n"
            "Write a grounded answer based only on the document context above:"
        )
    )
    out = ExtractiveChatModel._extract_answer([human])
    assert "couldn't find" not in out.lower()
    assert "summary" in out.lower() or out.strip().startswith("**")
    assert "-" in out
    assert "deepfake" in out.lower() or "methodology" in out.lower() or "spectral" in out.lower()


def test_confidence_label_bands():
    assert confidence_label(0.0) == "Insufficient evidence"
    assert "Limited" in confidence_label(0.3)
    assert "Moderate" in confidence_label(0.6)
    assert "Strong" in confidence_label(0.9)
    doc = Document(page_content="x", metadata={})
    assert compute_confidence([(doc, 1.0)], "I couldn't find that information in the uploaded documents.") == 0.0


def test_latency_metrics_record():
    record_chat_timings(retrieval_ms=12.5, generation_ms=8.0, total_ms=25.0, faiss_ms=10.0, bm25_ms=3.0)
    stats = get_latency_stats()
    assert stats["retrieval"]["count"] >= 1
    assert stats["total"]["avg_ms"] is not None
