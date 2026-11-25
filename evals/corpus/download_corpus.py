"""Regenerate synthetic fixtures and refresh the corpus manifest.

Synthetic scheme/circular fixtures live under evals/corpus/synthetic/ and are
generated locally (no network). Real public PDFs under evals/corpus/real/ are
user-supplied; optional DOWNLOADS entries can fetch into real/.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import urllib.request
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
SYNTHETIC_DIR = CORPUS_DIR / "synthetic"
REAL_DIR = CORPUS_DIR / "real"

# (filename, url, expected_sha256 or None) → written under real/
DOWNLOADS: list[tuple[str, str, str | None]] = [
    # Add stable public URLs here when automating real-corpus fetches.
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    gen = SYNTHETIC_DIR / "_gen_public_fixtures.py"
    if gen.is_file():
        print("Generating synthetic public fixtures →", SYNTHETIC_DIR)
        subprocess.check_call([sys.executable, str(gen)], cwd=str(CORPUS_DIR.parent.parent))
    else:
        print("WARNING: missing", gen, file=sys.stderr)

    REAL_DIR.mkdir(parents=True, exist_ok=True)
    if DOWNLOADS:
        for name, url, expected in DOWNLOADS:
            dest = REAL_DIR / name
            print(f"Fetching {url} → {dest}")
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read()
            digest = sha256_bytes(data)
            if expected and digest != expected:
                print(f"ERROR: sha256 mismatch for {name}: {digest}", file=sys.stderr)
                return 1
            dest.write_bytes(data)
            print(f"  wrote {len(data)} bytes sha256={digest}")
    else:
        print("No remote DOWNLOADS configured (real PDFs expected under evals/corpus/real/).")

    from evals.corpus_util import write_manifest

    path = write_manifest()
    print("manifest →", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
