"""Corpus manifest helpers: hashing and reproducible inventory.

Primary eval corpus: evals/corpus/real/
Synthetic CI fixture: evals/corpus/synthetic/ (Phase 4)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
REAL_DIR = CORPUS_DIR / "real"
SYNTHETIC_DIR = CORPUS_DIR / "synthetic"

CorpusSubset = Literal["primary", "synthetic", "all"]

SYNTHETIC_NOTICE = (
    "SYNTHETIC: generated / fictional content. Not real fund, regulatory, or personal "
    "data. Reserved as the Phase 4 CI fixture."
)

# Known provenance for synthetic fixtures (basename keys).
KNOWN_SYNTHETIC_META: dict[str, dict[str, str]] = {
    "policy_leave_entitlement.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated leave policy for eval",
    },
    "invoice_fixture_q3.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated invoice for eval",
    },
    "api_error_codes.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated API error codes for eval",
    },
    "qa_design.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated QA design note",
    },
    "smoke_ada2.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Tiny smoke resume",
    },
    "_smoke_perf.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Tiny performance resume",
    },
    "circular_amc_disclosure_2024.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "SYNTHETIC: synthetic regulatory circular — fictional",
    },
    "comparative_note_equity_schemes.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Long comparative note (no TER numbers)",
    },
}

# Real public PDFs — source_url filled where known; user may amend.
KNOWN_REAL_META: dict[str, dict[str, str]] = {
    "sebi_circular_commodity_overseas_fm_2024-04.pdf": {
        "origin": "public_download",
        "source_url": "https://www.sebi.gov.in/sebi_data/attachdocs/apr-2024/1714500252013.pdf",
        "license": "SEBI public circular",
        "notes": "SEBI circular Apr 30, 2024 — commodity/overseas fund manager ease",
    },
    "sebi_mf_master_circular_2024-06.pdf": {
        "origin": "public_download",
        "source_url": "https://www.sebi.gov.in/sebi_data/attachdocs/jun-2024/1719488538007.pdf",
        "license": "SEBI public circular",
        "notes": "SEBI Master Circular for Mutual Funds dated June 27, 2024",
    },
    "sid_hdfc_midcap.pdf": {
        "origin": "public_download",
        "source_url": "https://portal.amfiindia.com/spages/2526.pdf",
        "license": "AMC/AMFI public scheme document — verify redistribution rights",
        "notes": "HDFC Mid Cap Fund SID (AMFI portal)",
    },
    "sid_kotak_midcap.pdf": {
        "origin": "public_download",
        "source_url": "https://portal.amfiindia.com/spages/2191.pdf",
        "license": "AMC/AMFI public scheme document — verify redistribution rights",
        "notes": "Kotak Midcap Fund / Emerging Equity SID (AMFI portal)",
    },
    "sid_motilal_midcap.pdf": {
        "origin": "public_download",
        "source_url": "https://portal.amfiindia.com/spages/7913.pdf",
        "license": "AMC/AMFI public scheme document — verify redistribution rights",
        "notes": "Motilal Oswal Midcap Fund SID (AMFI portal)",
    },
    "sid_nippon_growth_midcap.pdf": {
        "origin": "public_download",
        "source_url": "https://portal.amfiindia.com/spages/139.pdf",
        "license": "AMC/AMFI public scheme document — verify redistribution rights",
        "notes": "Nippon India Growth Mid Cap Fund SID (AMFI portal)",
    },
    "sid_ppfas_flexicap.pdf": {
        "origin": "public_download",
        "source_url": "https://amc.ppfas.com/downloads/parag-parikh-flexi-cap-fund/SID_PPFCF.pdf",
        "license": "AMC public scheme document — verify redistribution rights",
        "notes": "Parag Parikh Flexi Cap Fund SID (PPFAS AMC)",
    },
}


def _scheme_meta(_path_name: str) -> dict[str, str]:
    return {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Near-identical fund SID for disambiguation questions",
    }


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def pdf_page_count(path: Path) -> int:
    """Fast page count without full text extraction."""
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        try:
            from backend.app.rag.ingest import load_pdf

            return len(load_pdf(path))
        except Exception:
            return 0


def _is_skippable(name: str) -> bool:
    skip = {
        "manifest.json",
        "README.md",
        ".gitkeep",
        "download_corpus.py",
        "_gen_public_fixtures.py",
    }
    if name in skip:
        return True
    if name.startswith("_") and name.endswith(".py"):
        return True
    return False


def _list_pdfs_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(folder.iterdir()):
        if not p.is_file() or _is_skippable(p.name):
            continue
        if p.suffix.lower() in {".pdf", ".txt"}:
            files.append(p)
    return files


def list_corpus_files(
    corpus_dir: Path | None = None,
    *,
    subset: CorpusSubset = "primary",
) -> list[Path]:
    """List corpus PDFs. Default subset=primary → evals/corpus/real/ only."""
    root = corpus_dir or CORPUS_DIR
    if corpus_dir is not None and corpus_dir.resolve() != CORPUS_DIR.resolve():
        # Explicit alternate root: list all PDFs under it
        return [
            p
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and not _is_skippable(p.name)
            and p.suffix.lower() in {".pdf", ".txt"}
        ]

    if subset == "primary":
        return _list_pdfs_in(REAL_DIR)
    if subset == "synthetic":
        return _list_pdfs_in(SYNTHETIC_DIR)
    # all
    return _list_pdfs_in(REAL_DIR) + _list_pdfs_in(SYNTHETIC_DIR)


def find_corpus_pdf(filename: str, *, subset: CorpusSubset = "all") -> Path | None:
    """Resolve a basename to a path under real/ or synthetic/."""
    key = Path(filename).name.lower()
    for p in list_corpus_files(subset=subset):
        if p.name.lower() == key:
            return p
    return None


def corpus_hash(
    corpus_dir: Path | None = None,
    *,
    subset: CorpusSubset = "primary",
) -> str:
    """Hash file contents. Primary/synthetic hashes use basename keys so moving
    trees under real/ or synthetic/ does not invalidate existing eval indexes.
    The combined ``all`` hash uses paths relative to CORPUS_DIR.
    """
    root = corpus_dir or CORPUS_DIR
    files = list_corpus_files(root if corpus_dir else None, subset=subset)
    h = hashlib.sha256()
    for p in files:
        if subset == "all":
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name
        else:
            # Stable across real/ vs synthetic/ layout: basename only
            rel = p.name
        digest = sha256_file(p)
        h.update(f"{rel}:{digest}\n".encode("utf-8"))
    return h.hexdigest() if files else "empty"


def _meta_for(path: Path, rel: str) -> dict[str, str]:
    name = path.name
    if rel.startswith("synthetic/") or "synthetic" in path.parts:
        meta = KNOWN_SYNTHETIC_META.get(name)
        if meta is None and name.startswith("scheme_"):
            meta = _scheme_meta(name)
        if meta is None:
            meta = {
                "origin": "synthetic_fixture",
                "source_url": "generated://evals/corpus/synthetic/_gen_public_fixtures.py",
                "license": "CC0-equivalent original fixture (DocuMind)",
                "notes": "Synthetic fixture",
            }
        return {**meta, "synthetic_notice": SYNTHETIC_NOTICE}

    meta = KNOWN_REAL_META.get(name)
    if meta is None:
        meta = {
            "origin": "public_download",
            "source_url": "",  # user to fill
            "license": "unknown — review before publishing",
            "notes": "Add source_url when known",
        }
    return dict(meta)


def build_manifest(corpus_dir: Path | None = None) -> dict[str, Any]:
    root = corpus_dir or CORPUS_DIR
    entries = []
    for p in list_corpus_files(root if corpus_dir else None, subset="all"):
        rel = p.relative_to(root).as_posix()
        meta = _meta_for(p, rel)
        entry: dict[str, Any] = {
            "path": rel,
            "sha256": sha256_file(p),
            "bytes": p.stat().st_size,
            "pages": pdf_page_count(p) if p.suffix.lower() == ".pdf" else None,
            "origin": meta["origin"],
            "source_url": meta.get("source_url", ""),
            "license": meta["license"],
            "notes": meta.get("notes", ""),
        }
        if "synthetic_notice" in meta:
            entry["synthetic_notice"] = meta["synthetic_notice"]
        entries.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "primary_corpus": "real",
        "primary_corpus_hash": corpus_hash(subset="primary"),
        "synthetic_corpus_hash": corpus_hash(subset="synthetic"),
        "corpus_hash": corpus_hash(subset="all"),
        "file_count": len(entries),
        "files": entries,
    }


def write_manifest(corpus_dir: Path | None = None) -> Path:
    root = corpus_dir or CORPUS_DIR
    root.mkdir(parents=True, exist_ok=True)
    data = build_manifest(root)
    path = root / "manifest.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
