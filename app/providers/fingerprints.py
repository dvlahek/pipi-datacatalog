from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    """Return a stable SHA-256 content fingerprint."""

    return hashlib.sha256(content).hexdigest()


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a source file without loading the whole payload into memory.

    CSV, text, audio and other file providers can put this value into
    `CanonicalDataset.provenance.content_sha256`. A changed source file then
    changes the canonical snapshot fingerprint and creates a new catalog version
    on the next sync.
    """

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
