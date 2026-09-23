"""Cloudflare Containers deploy preflight.

Run from the repo root:

    python backend/scripts/verify_cloudflare_build.py

It reuses `verify_production_build.build_spa` and `smoke_test` to make
sure the API + SPA build is sound, then validates the Cloudflare-specific
artefacts:

  - wrangler.jsonc exists, parses as JSON (JSON5 tolerated), and points
    at a real Dockerfile.
  - Dockerfile references backend/app, exposes a port, and runs uvicorn
    in a way that respects $PORT (Cloudflare sets PORT=8080).

If `wrangler` is on PATH, this script also tries `wrangler deploy --dry-run`
so you see the deploy errors locally before pushing.

Nothing here talks to Cloudflare unless you run `wrangler deploy` yourself.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _ok(msg: str) -> None:
    print(f"  ok  {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL {msg}")


def validate_wrangler_jsonc() -> bool:
    print("==> 1/4 validating wrangler.jsonc")
    path = REPO / "wrangler.jsonc"
    if not path.exists():
        _fail(f"{path} not found — copy from the repo and edit your subdomain")
        return False
    # JSONC: strip // and /* */ comments + line/block strings naively.
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    text_no_trail = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        cfg = json.loads(text_no_trail)
    except json.JSONDecodeError as e:
        _fail(f"wrangler.jsonc is not valid JSON after stripping comments: {e}")
        return False
    containers = cfg.get("containers") or []
    if not containers:
        _fail("wrangler.jsonc has no 'containers' block")
        return False
    c = containers[0]
    image = c.get("image")
    if not image:
        _fail("containers[0].image is missing")
        return False
    df_path = (REPO / image).resolve() if not os.path.isabs(image) else Path(image)
    if not df_path.exists():
        _fail(f"Dockerfile not found at {df_path} (resolved from {image!r})")
        return False
    _ok(f"wrangler.jsonc -> {df_path.relative_to(REPO)}")
    port = c.get("port")
    _ok(f"container.port = {port}")
    health = c.get("health") or {}
    _ok(f"health.path = {health.get('path')!r}")
    return True


def validate_dockerfile() -> bool:
    print("==> 2/4 validating Dockerfile")
    df = REPO / "backend" / "Dockerfile"
    text = df.read_text(encoding="utf-8")
    checks = [
        ("non-root user", "useradd" in text and "USER app" in text),
        (
            "PORT-aware CMD",
            "${PORT" in text or "PORT:-" in text,
        ),
        ("alembic migration in CMD", "alembic upgrade head" in text),
        ("uvicorn in CMD", "uvicorn" in text),
        ("two-stage build", text.count("FROM ") >= 2),
        ("tini as ENTRYPOINT", "tini" in text),
    ]
    ok = True
    for name, cond in checks:
        if cond:
            _ok(name)
        else:
            _fail(name)
            ok = False
    return ok


def build_and_smoke() -> bool:
    print("==> 3/4 building + smoke-testing the production image")
    # Reuse the existing preflight — same SPA build + same route checks.
    sys.path.insert(0, str(REPO / "backend" / "scripts"))
    try:
        from verify_production_build import build_spa, copy_dist_into_backend, smoke_test
    except ImportError as e:
        _fail(f"could not import verify_production_build helpers: {e}")
        return False
    try:
        build_spa()
    except SystemExit as e:
        _fail(f"SPA build failed: {e}")
        return False
    try:
        copy_dist_into_backend()
    except Exception as e:
        _fail(f"copy_dist_into_backend failed: {e}")
        return False
    try:
        smoke_test()
    except SystemExit as e:
        _fail(f"smoke test failed: {e}")
        return False
    _ok("SPA built and all 8 routes return expected status codes")
    return True


def maybe_wrangler_dry_run() -> bool:
    print("==> 4/4 wrangler dry-run (optional)")
    if not shutil.which("wrangler"):
        _ok("wrangler not on PATH — skipped dry-run. Install with: npm i -g wrangler")
        return True
    proc = subprocess.run(
        ["wrangler", "deploy", "--dry-run", "--outdir=dist-cf"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        _ok("wrangler dry-run succeeded")
        return True
    print("    wrangler dry-run output:")
    print(proc.stdout)
    print(proc.stderr)
    _fail("wrangler dry-run failed — fix wrangler.jsonc before deploying")
    return False


def main() -> int:
    print(f"Repo: {REPO}")
    results = [
        validate_wrangler_jsonc(),
        validate_dockerfile(),
        build_and_smoke(),
        maybe_wrangler_dry_run(),
    ]
    if all(results):
        print("\nAll checks passed. You can deploy with:")
        print("  wrangler secret put DATABASE_URL")
        print("  wrangler secret put SECRET_KEY")
        print("  wrangler secret put RESEND_API_KEY")
        print("  wrangler deploy")
        return 0
    print(f"\n{sum(1 for r in results if not r)} check(s) failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
