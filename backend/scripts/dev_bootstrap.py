"""Local dev bootstrap — sets up SQLite DB and seeds demo data without Docker.

Equivalent to ``docker compose up && make migrate && make seed`` but using
SQLite so a developer without Docker can run the app in a single command.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def main() -> int:
    env_path = BACKEND.parent / ".env"
    if not env_path.exists():
        env_path.write_text(
            "APP_ENV=development\n"
            "SECRET_KEY=dev-secret-change-me-please\n"
            f"DATABASE_URL=sqlite:///{BACKEND / 'storage' / 'teamledger.db'}\n"
            "STORAGE_LOCAL_ROOT=./storage/files\n"
            "MAIL_BACKEND=console\n",
            encoding="utf-8",
        )
    storage = BACKEND / "storage"
    (storage / "files").mkdir(parents=True, exist_ok=True)
    print("Running alembic upgrade head ...")
    rc = subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    if rc != 0:
        return rc
    print("Seeding demo data ...")
    rc = subprocess.call([sys.executable, "-m", "scripts.seed_demo"], cwd=BACKEND)
    if rc != 0:
        return rc
    print("Run `make backend` to start the API.")
    return 0


if __name__ == "__main__":
    sys.exit(int(main() or 0))
