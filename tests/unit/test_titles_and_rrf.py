"""Unit tests for titles, follow-up expansion, and weighted RRF."""

from langchain_core.documents import Document

from backend.app.rag.hybrid_search import reciprocal_rank_fusion
from backend.app.rag.qa_chain import expand_followup_query
from backend.app.utils.titles import make_conversation_title


def test_conversation_title_sentence_case():
    assert make_conversation_title("what is candidates name?") == "What is candidates name?"


def test_conversation_title_truncates():
    long = "a" * 100
    title = make_conversation_title(long, max_len=40)
    assert len(title) <= 40
    assert title.endswith("…")


def test_followup_expansion_for_short_questions():
    q = expand_followup_query(
        "Which of them are used in the projects?",
        ["What technologies are mentioned?"],
    )
    assert "technologies" in q.lower()
    assert "projects" in q.lower()


def test_weighted_rrf_prefers_dense_when_weight_high():
    a = Document(page_content="alpha", metadata={"chunk_id": "a"})
    b = Document(page_content="beta", metadata={"chunk_id": "b"})
    dense = [(a, 0.9), (b, 0.1)]
    sparse = [(b, 9.0), (a, 0.1)]
    fused = reciprocal_rank_fusion([dense, sparse], weights=[0.9, 0.1])
    assert fused[0][0].metadata["chunk_id"] == "a"
