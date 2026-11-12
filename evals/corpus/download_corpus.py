"""Fetch optional public corpus files and regenerate synthetic fixtures.

Synthetic scheme/circular fixtures are generated locally (no network) via
`_gen_public_fixtures.py`. Add remote public URLs to DOWNLOADS when available.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import urllib.request
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent

# (filename, url, expected_sha256 or None)
# Prefer stable public URLs. Synthetic fixtures are generated, not downloaded.
DOWNLOADS: list[tuple[str, str, str | None]] = [
    # Placeholder for user-supplied public documents:
    # (
    #   "sebi_sample.pdf",
    #   "https://example.com/public/sebi_sample.pdf",
    #   None,
    # ),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    # Always regenerate synthetic public fixtures so hashes stay reproducible in-repo
    gen = CORPUS_DIR / "_gen_public_fixtures.py"
    if gen.is_file():
        print("Generating synthetic public fixtures…")
        subprocess.check_call([sys.executable, str(gen)], cwd=str(CORPUS_DIR.parent.parent))

    if DOWNLOADS:
        for name, url, expected in DOWNLOADS:
            dest = CORPUS_DIR / name
            print(f"Fetching {url} → {dest.name}")
            with urllib.request.urlopen(url, timeout=120) as resp:
                data = resp.read()
            digest = sha256_bytes(data)
            if expected and digest != expected:
                print(f"ERROR: sha256 mismatch for {name}: {digest}", file=sys.stderr)
                return 1
            dest.write_bytes(data)
            print(f"  wrote {len(data)} bytes sha256={digest}")
    else:
        print("No remote DOWNLOADS configured (synthetic fixtures only).")

    from evals.corpus_util import write_manifest

    path = write_manifest()
    print("manifest →", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
