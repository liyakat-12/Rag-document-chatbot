"""Primary vs synthetic corpus split."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_list_corpus_files_primary_excludes_synthetic():
    from evals.corpus_util import list_corpus_files

    primary = list_corpus_files(subset="primary")
    synthetic = list_corpus_files(subset="synthetic")
    assert primary, "expected real/ PDFs"
    assert synthetic, "expected synthetic/ PDFs"
    assert all("real" in str(p).replace("\\", "/") for p in primary)
    assert all("synthetic" in str(p).replace("\\", "/") for p in synthetic)
    assert {p.name for p in primary}.isdisjoint({p.name for p in synthetic})


def test_manifest_marks_synthetic_notice():
    from evals.corpus_util import build_manifest

    data = build_manifest()
    assert data.get("primary_corpus") == "real"
    synth = [f for f in data["files"] if f["path"].startswith("synthetic/")]
    real = [f for f in data["files"] if f["path"].startswith("real/")]
    assert synth and real
    assert all(f.get("synthetic_notice", "").startswith("SYNTHETIC:") for f in synth)
    assert all("pages" in f for f in real)


def test_questions_jsonl_targets_real_filenames():
    from evals.schema import load_questions

    qs = load_questions(ROOT / "evals" / "data" / "questions.jsonl")
    assert len(qs) >= 90
    answerable = [q for q in qs if q.answerable]
    names = {g.filename for q in answerable for g in q.gold}
    assert any(n.startswith("sid_") for n in names)
    assert not any(n.startswith("scheme_") for n in names)
