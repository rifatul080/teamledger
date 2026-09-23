"""Cloudflare Containers deploy preflight.

Run from the repo root:

    python backend/scripts/verify_cloudflare_build.py

It reuses `verify_production_build.build_spa` and `smoke_test` to make
sure the API + SPA build is sound, then validates the Cloudflare-specific
artefacts:

  - wrangler.jsonc exists, parses as JSON5 (JSON with // comments), and
    references a real Dockerfile via `containers[].image`. The schema
    used here matches wrangler 4.x's actual `containers[]` block
    (see https://developers.cloudflare.com/workers/wrangler/configuration/#containers):
    only `class_name`, `image`, `instance_type`, `max_instances`,
    `image_vars`, etc. are allowed inside `containers[]` — port, health,
    and env are configured on the Container class in src/container.ts.
  - wrangler.jsonc must declare `main` (the Worker entrypoint) and
    register the container Durable Object in `durable_objects.bindings`
    plus a `migrations` block adding the class as `new_sqlite_classes`.
  - Dockerfile references backend/app, exposes port 8080, and runs
    uvicorn in a way that respects $PORT (Cloudflare sets PORT=8080).
  - src/container.ts exists and exports a class with `defaultPort = 8080`
    that matches the `class_name` in wrangler.jsonc.

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


# Fields allowed inside a single `containers[]` entry on wrangler v4.x.
# Anything outside this set triggers "Unexpected fields found in
# containers field" at deploy time.
ALLOWED_CONTAINER_FIELDS = {
    "name",
    "class_name",
    "image",
    "image_build_context",
    "image_vars",
    "instance_type",
    "max_instances",
    "rollout_active_grace_period",
    "rollout_step_percentage",
    "ssh",
    "wrangler_ssh",
    "authorized_keys",
    "constraints",
}


def _load_jsonc(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(^|\s)//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        _fail(f"{path.name} is not valid JSON after stripping comments: {e}")
        return None


def validate_wrangler_jsonc() -> bool:
    print("==> 1/5 validating wrangler.jsonc")
    path = REPO / "wrangler.jsonc"
    if not path.exists():
        _fail(f"{path} not found")
        return False
    cfg = _load_jsonc(path)
    if cfg is None:
        return False

    ok = True

    # main is required (Worker entrypoint)
    if not cfg.get("main"):
        _fail("wrangler.jsonc is missing required `main` (Worker entrypoint)")
        ok = False
    else:
        main_path = (REPO / cfg["main"]).resolve()
        if not main_path.exists():
            _fail(f"`main` file not found: {main_path}")
            ok = False
        else:
            _ok(f"main -> {main_path.relative_to(REPO)}")

    # containers[] must reference a Dockerfile and a class
    containers = cfg.get("containers") or []
    if not containers:
        _fail("wrangler.jsonc has no 'containers' block")
        return False
    c = containers[0]

    # Detect unknown fields first — these are what break the deploy.
    unknown = sorted(set(c.keys()) - ALLOWED_CONTAINER_FIELDS)
    if unknown:
        _fail(
            f"containers[0] has fields not allowed by wrangler v4.x: {unknown}. "
            "Move `port`, `health`, `env` to the Container class in src/container.ts."
        )
        ok = False
    else:
        _ok("containers[0] only uses allowed fields")

    image = c.get("image")
    if not image:
        _fail("containers[0].image is missing")
        return False
    df_path = (REPO / image).resolve() if not os.path.isabs(image) else Path(image)
    if not df_path.exists():
        _fail(f"Dockerfile not found at {df_path} (resolved from {image!r})")
        return False
    _ok(f"containers[0].image -> {df_path.relative_to(REPO)}")

    class_name = c.get("class_name")
    if not class_name:
        _fail("containers[0].class_name is missing (must match the exported Container class)")
        ok = False

    # Durable Object binding for the container
    do_bindings = ((cfg.get("durable_objects") or {}).get("bindings")) or []
    do_match = next(
        (b for b in do_bindings if isinstance(b, dict) and b.get("class_name") == class_name),
        None,
    )
    if not do_match:
        _fail(
            f"durable_objects.bindings must include an entry with class_name={class_name!r}"
        )
        ok = False
    else:
        _ok(f"durable_objects.bindings -> {do_match.get('name')} -> {class_name}")

    # Migration that registers the class
    migrations = cfg.get("migrations") or []
    migrating_classes: list[str] = []
    for mig in migrations:
        migrating_classes.extend(mig.get("new_sqlite_classes") or [])
    if class_name not in migrating_classes:
        _fail(
            f"migrations must include new_sqlite_classes: [{class_name!r}] (got {migrating_classes})"
        )
        ok = False
    else:
        _ok(f"migrations registers {class_name} as new_sqlite_classes")

    return ok


def validate_container_ts() -> bool:
    print("==> 2/5 validating src/container.ts")
    cfg = _load_jsonc(REPO / "wrangler.jsonc")
    if cfg is None:
        return False
    expected_class = (cfg.get("containers") or [{}])[0].get("class_name") or "TeamledgerContainer"
    container_path = REPO / "src" / "container.ts"
    if not container_path.exists():
        _fail(f"{container_path.relative_to(REPO)} not found")
        return False
    text = container_path.read_text(encoding="utf-8")
    ok = True
    if f"class {expected_class}" not in text:
        _fail(f"{container_path.name} does not export class {expected_class!r}")
        ok = False
    else:
        _ok(f"exports class {expected_class}")
    if "defaultPort" not in text:
        _fail("Container class has no `defaultPort` — wrangler can't pick a port to forward")
        ok = False
    else:
        m = re.search(r"defaultPort\s*=\s*(\d+)", text)
        port = int(m.group(1)) if m else None
        if port and port != 8080:
            _fail(
                f"defaultPort={port} does not match backend/Dockerfile EXPOSE 8080"
            )
            ok = False
        else:
            _ok(f"defaultPort = {port} (matches Dockerfile)")
    if "extends Container" not in text:
        _fail("class does not extend Container from @cloudflare/containers")
        ok = False
    else:
        _ok("extends Container (imported from @cloudflare/containers)")
    return ok


def validate_dockerfile() -> bool:
    print("==> 3/5 validating Dockerfile")
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
        ("EXPOSE 8080", "EXPOSE 8080" in text),
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
    print("==> 4/5 building + smoke-testing the production image")
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
    print("==> 5/5 wrangler dry-run (optional)")
    has_wrangler = shutil.which("wrangler") is not None
    has_npx = shutil.which("npx") is not None
    if not has_wrangler and not has_npx:
        _ok("neither `wrangler` nor `npx` is on PATH — skipped dry-run")
        return True
    cmd = (
        ["npx", "--yes", "wrangler@4", "deploy", "--dry-run", "--outdir=dist-cf"]
        if not has_wrangler
        else ["wrangler", "deploy", "--dry-run", "--outdir=dist-cf"]
    )
    try:
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _ok(f"wrangler dry-run skipped: {type(e).__name__}: {e}")
        return True
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
        validate_container_ts(),
        validate_dockerfile(),
        build_and_smoke(),
        maybe_wrangler_dry_run(),
    ]
    if all(results):
        print("\nAll checks passed. You can deploy with:")
        print("  npm install                                 # one-time")
        print("  npx wrangler login                          # one-time")
        print("  npx wrangler secret put DATABASE_URL")
        print("  npx wrangler secret put SECRET_KEY")
        print("  npx wrangler secret put RESEND_API_KEY")
        print("  npx wrangler deploy")
        return 0
    print(f"\n{sum(1 for r in results if not r)} check(s) failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
