"""Storage backend interface and helpers.

Implementations must:
- never trust user-provided filenames for path construction;
- generate their own paths (ULID-based);
- return safe ``Content-Disposition`` headers at download time;
- never execute or unpack archives.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    path: str
    size_bytes: int
    sha256: str


class StorageBackend(Protocol):
    def put(self, *, team_id: str, content: bytes, original_name: str) -> StoredObject:
        """Persist content. Generates path; returns storage metadata."""

    def head(self, path: str) -> StoredObject:
        """Return metadata for an existing object."""

    def stream(self, path: str) -> Iterator[bytes]:
        """Yield the object's bytes."""

    def delete(self, path: str) -> None:
        """Remove the object. Idempotent."""

    def exists(self, path: str) -> bool:
        ...


# ---------------------------------------------------------------------------
# Filename + content-type helpers (shared by all backends)


# Strip path separators and control characters.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-\u00A0-\uFFFF]+")


def safe_basename(name: str, *, max_len: int = 200) -> str:
    """Return a basename that is safe to embed in a storage path or
    ``Content-Disposition``. Strips directory parts and disallowed chars.
    """
    # 1) strip path separators
    name = name.replace("\\", "/").split("/")[-1]
    name = name.strip().strip(".") or "file"
    name = _SAFE_NAME_RE.sub("_", name)
    if len(name) > max_len:
        # keep extension if any
        if "." in name:
            stem, _, ext = name.rpartition(".")
            stem = stem[: max(0, max_len - len(ext) - 1)]
            name = f"{stem}.{ext}" if ext else stem[:max_len]
        else:
            name = name[:max_len]
    return name


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sniff_content_type(content: bytes, fallback: str = "application/octet-stream") -> str:
    """Sniff content type from the first bytes. Falls back to ``fallback``.

    Uses signatures only — no libmagic dependency. Covers PDF, PNG, JPEG,
    GIF, ZIP, gzip, tar+gzip, JSON, UTF-8/UTF-16 BOMs. Anything else gets
    ``application/octet-stream``.
    """
    if not content:
        return fallback
    head = content[:16]
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"PK\x03\x04" or head[:4] == b"PK\x05\x06" or head[:4] == b"PK\x07\x08":
        return "application/zip"
    if head[:2] == b"\x1f\x8b":
        return "application/gzip"
    if head[:6] == b"7z\xbc\xaf\x27\x1c":
        return "application/x-7z-compressed"
    if head[:5] == b"Rar!\x1a\x07":
        return "application/vnd.rar"
    if head[:3] == b"BZh":
        return "application/x-bzip2"
    if head[:5] == b"ustar":
        return "application/x-tar"
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "text/plain; charset=utf-16"
    if head[:3] == b"\xef\xbb\xbf":
        return "text/plain; charset=utf-8"
    stripped = content.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return "application/json"
    if head[:4] == b"%PDF":
        return "application/pdf"
    return fallback


def safe_inline_preview(content_type: str) -> bool:
    """Only PDFs can be previewed inline per spec."""
    return content_type.startswith("application/pdf")


# ---------------------------------------------------------------------------
# Archive entry safety (used to refuse names that try to escape on download)


_TRAVERSAL_RE = re.compile(r"(\.\.[/\\]|^\.|[/\\]\.\.|/\\.\\.|\\\\)")


def safe_member_name(name: str) -> bool:
    """Return True if a name inside an archive would be safe to display."""
    if not name:
        return False
    if name.startswith("/") or name.startswith("\\"):
        return False
    if _TRAVERSAL_RE.search(name):
        return False
    return "\x00" not in name
