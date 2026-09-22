"""Backup script: dump the database to ./storage/backups/.

Usage:
    python scripts/backup_db.py [--url postgres://…] [--out ./storage/backups]

Strategy:
- Postgres (production): `pg_dump -Fc` produces a portable custom-format dump.
- SQLite (dev): copy the file atomically.

The script does NOT depend on the application's own libraries — it's pure
stdlib + shelling out to pg_dump — so it can run during an outage.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _sqlite_backup(src: Path, out_dir: Path) -> Path:
    if not src.exists():
        sys.exit(f"No SQLite db at {src}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    dst = out_dir / f"teamledger-sqlite-{stamp}.db"
    shutil.copy2(src, dst)
    return dst


def _postgres_backup(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    dst = out_dir / f"teamledger-pg-{stamp}.dump"
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        sys.exit("pg_dump not found in PATH — install postgresql-client.")
    cmd = [pg_dump, "-Fc", "-f", str(dst), url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr or "pg_dump failed")
    return dst


def main() -> int:
    p = argparse.ArgumentParser(description="TeamLedger DB backup")
    p.add_argument(
        "--url",
        default=os.environ.get("DATABASE_URL", "sqlite:///./storage/teamledger.db"),
        help="Database URL (defaults to env DATABASE_URL)",
    )
    p.add_argument(
        "--out",
        default="./storage/backups",
        help="Output directory",
    )
    args = p.parse_args()
    out_dir = Path(args.out)
    if args.url.startswith("postgres://") or args.url.startswith("postgresql://"):
        dst = _postgres_backup(args.url, out_dir)
    elif args.url.startswith("sqlite:"):
        path = args.url.replace("sqlite:///", "").replace("sqlite://", "")
        dst = _sqlite_backup(Path(path), out_dir)
    else:
        sys.exit(f"Unsupported URL scheme: {args.url}")
    print(f"Wrote backup: {dst} ({dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
