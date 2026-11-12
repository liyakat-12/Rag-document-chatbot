"""Download optional public corpus files that are not committed to git.

Add entries to DOWNLOADS with a stable URL and expected sha256 when available.
Files with unclear licences stay here as download-only.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent

# (filename, url, expected_sha256 or None)
DOWNLOADS: list[tuple[str, str, str | None]] = [
    # Example (disabled):
    # (
    #   "sample_public.pdf",
    #   "https://example.com/sample_public.pdf",
    #   None,
    # ),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not DOWNLOADS:
        print(
            "No DOWNLOADS configured. Add public URLs to evals/corpus/download_corpus.py "
            "or copy your own PDFs into evals/corpus/."
        )
        return 0
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url, expected in DOWNLOADS:
        dest = CORPUS_DIR / name
        print(f"Fetching {url} → {dest.name}")
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        if expected and sha256_bytes(data) != expected:
            print(f"ERROR: sha256 mismatch for {name}", file=sys.stderr)
            return 1
        dest.write_bytes(data)
        print(f"  wrote {len(data)} bytes sha256={sha256_bytes(data)}")
    from evals.corpus_util import write_manifest

    print("manifest →", write_manifest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
