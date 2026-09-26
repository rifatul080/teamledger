"""Local-disk implementation of the storage backend."""
from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ..core.ids import new_id
from .base import StoredObject, safe_basename, sha256_bytes


class LocalDiskStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def _resolve(self, path: str) -> Path:
        p = (self.root / path).resolve()
        # Defence in depth: ensure p stays under root.
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"path escapes root: {path}")
        return p

    def _build_path(self, team_id: str, original_name: str) -> tuple[str, str]:
        now = datetime.now(tz=UTC)
        safe = safe_basename(original_name)
        path = f"teams/{team_id}/{now:%Y/%m}/{new_id()}_{safe}"
        return path, safe

    def put(self, *, team_id: str, content: bytes, original_name: str) -> StoredObject:
        path, _ = self._build_path(team_id, original_name)
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        sha = sha256_bytes(content)
        # Write atomically: tmp then rename.
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, target)
        return StoredObject(path=path, size_bytes=len(content), sha256=sha)

    def head(self, path: str) -> StoredObject:
        target = self._resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        size = target.stat().st_size
        sha = sha256_bytes(target.read_bytes())
        return StoredObject(path=path, size_bytes=size, sha256=sha)

    def stream(self, path: str) -> Iterator[bytes]:
        target = self._resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        with target.open("rb") as fh:
            while True:
                chunk = fh.read(64 * 1024)
                if not chunk:
                    return
                yield chunk

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.exists() and target.is_file():
            target.unlink()

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except ValueError:
            return False


def make_storage(backend: str, root: str) -> LocalDiskStorage:
    """Factory; only the local backend is implemented today."""
    if backend != "local":
        raise NotImplementedError(f"storage backend not implemented: {backend}")
    return LocalDiskStorage(root=root)
