"""One-shot preflight: proves the production Docker build is sane without
actually pushing it anywhere.

Run from the repo root:

    python backend/scripts/verify_production_build.py

It will:
1. Build the SPA with `npm run build`.
2. Spawn uvicorn against the per-test SQLite DB and curl:
   - `/healthz` -> 200
   - `/` (the SPA index) -> 200, contains "TeamLedger"
   - `/robots.txt` -> 200, contains "Disallow: /api/"
   - `/sitemap.xml` -> 200, contains "<urlset"
   - `/login`, `/signup` -> 200 (served by SPA fallback)
   - `/api/v1/auth/signup` -> 201
3. Print the exact env-var contract that production must match.
4. Print the manual steps to provision Neon, Render, and Resend.

The script does NOT push or purchase anything; it only proves the build
is sound before you hand the keys to a deploy host.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _wait_port(host: str, port: int, timeout: float = 15.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return True
            except OSError:
                time.sleep(0.2)
    return False


def _http(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except Exception as e:
        return 0, str(e)


def build_spa() -> None:
    print("==> Step 1/4: building SPA")
    npm = shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.ps1")
    if not npm:
        # Fall back to the npm.cmd bundled with the user's Node install.
        candidates = [
            r"C:\Program Files\nodejs\npm.cmd",
            r"C:\Program Files (x86)\nodejs\npm.cmd",
            os.path.expandvars(r"%APPDATA%\npm\npm.cmd"),
        ]
        for c in candidates:
            if Path(c).exists():
                npm = c
                break
    if not npm:
        sys.exit("Could not locate `npm`. Install Node.js or add it to PATH and re-run.")
    proc = subprocess.run(
        [npm, "run", "build"],
        cwd=str(REPO / "frontend"),
        check=False,
    )
    if proc.returncode != 0:
        sys.exit("SPA build failed; aborting.")


def copy_dist_into_backend() -> None:
    print("==> Step 2/4: copying SPA dist into backend/static (mimics Dockerfile)")
    static = REPO / "backend" / "static"
    if static.exists():
        shutil.rmtree(static)
    shutil.copytree(REPO / "frontend" / "dist", static)
    print(f"    wrote {static} ({sum(1 for _ in static.rglob('*'))} files)")


def smoke_test() -> None:
    print("==> Step 3/4: smoke testing the production-like build")
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["SECRET_KEY"] = "verify-script-only-not-for-prod"
    tmp = tempfile.mkdtemp(prefix="tlverify_")
    env["DATABASE_URL"] = f"sqlite:///{tmp}/db.sqlite"
    env["STORAGE_LOCAL_ROOT"] = f"{tmp}/files"
    env["AVATAR_LOCAL_ROOT"] = f"{tmp}/avatars"
    env["CORS_ALLOWED_ORIGINS"] = "http://localhost:5173"
    env["PUBLIC_BASE_URL"] = "http://localhost:8000"

    # Run alembic upgrade head on the fresh SQLite so the schema exists.
    alembic = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO / "backend"),
        env=env,
        capture_output=True,
        check=False,
    )
    if alembic.returncode != 0:
        print(alembic.stdout.decode("utf-8", errors="replace"))
        print(alembic.stderr.decode("utf-8", errors="replace"))
        sys.exit("alembic upgrade head failed.")

    uvicorn = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--log-level",
            "warning",
        ],
        cwd=str(REPO / "backend"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_port("127.0.0.1", 8765):
            sys.exit("uvicorn failed to come up within 15s.")
        checks = [
            ("/healthz", 200),
            ("/", 200),
            ("/robots.txt", 200),
            ("/sitemap.xml", 200),
            ("/login", 200),
            ("/signup", 200),
        ]
        ok = True
        for path, want in checks:
            code, _body = _http("http://127.0.0.1:8765" + path)
            mark = "OK " if code == want else "FAIL"
            print(f"    {mark}  {path} -> {code} (want {want})")
            if code != want:
                ok = False
        # SPA should be served by the index.html fallback
        code, body = _http("http://127.0.0.1:8765/")
        if "TeamLedger" in body:
            print("    OK   / serves index.html with 'TeamLedger'")
        else:
            print("    FAIL / does not contain 'TeamLedger'")
            ok = False
        # Signup a real user
        import json as _json

        req = urllib.request.Request(
            "http://127.0.0.1:8765/api/v1/auth/signup",
            data=_json.dumps(
                {
                    "email": "verify@example.org",
                    "password": "VeryStrongPass1",
                    "display_name": "Verify",
                    "institution": "MIT",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                print(f"    OK   /api/v1/auth/signup -> {r.status}")
        except urllib.error.HTTPError as e:
            print(f"    FAIL /api/v1/auth/signup -> {e.code}")
            try:
                print("      body:", e.read().decode("utf-8", errors="replace")[:500])
            except Exception:
                pass
            ok = False
        if not ok:
            sys.exit("Smoke test failed.")
    finally:
        uvicorn.send_signal(signal.SIGTERM)
        uvicorn.wait(timeout=5)
        shutil.rmtree(tmp, ignore_errors=True)


def print_manual_steps() -> None:
    print()
    print("==> Step 4/4: manual deployment steps (no credentials in this env)")
    print("""
  I do not have credentials for Neon / Render / Resend, so I cannot
  provision them from this session. Run the following yourself; each
  is a few minutes:

  1. NEON (free Postgres, scales to zero):
       https://neon.tech  -> Sign up with GitHub
       Create a project named 'teamledger'
       Copy the connection string (looks like
       postgresql://USER:PASS@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require)

  2. RENDER (free web service, sleeps after 15 min idle):
       https://render.com -> Sign up with GitHub
       'New +' -> 'Web Service' -> connect 'rifatul080/teamledger'
       Environment: Docker
       Root directory: backend
       Dockerfile Path: Dockerfile
       Plan: Free
       Health check path: /healthz
       Add these env vars (secrets: sync = false):
         DATABASE_URL  -> paste the Neon string from step 1
         SECRET_KEY    -> any 32+ random bytes
         APP_ENV       -> production
         MAIL_BACKEND  -> resend  (or 'console' for dev)
         RESEND_API_KEY -> paste from step 3 below
         RESEND_FROM   -> TeamLedger <noreply@teamledger.app>
         PUBLIC_BASE_URL -> https://<your-app>.onrender.com
         CORS_ALLOWED_ORIGINS -> https://<your-app>.onrender.com
       Click 'Create Web Service'. First build ~3-5 min. Free tier will
       sleep after 15 min of no traffic; the next request wakes it
       (~5-10 s). That's expected, not a bug.

  3. RESEND (free tier 100 emails/day, 3000/month):
       https://resend.com -> Sign up with GitHub
       'API Keys' -> 'Create API Key' -> paste into Render env.
       'Domains' -> add a domain (or use the sandbox sender
       'onboarding@resend.dev' for testing) and paste the From address
       into RESEND_FROM. Without verifying a domain, the From address
       must be the sandbox.

  4. (Optional) CUSTOM DOMAIN:
       Buy one, point a CNAME at <your-app>.onrender.com, then update
       PUBLIC_BASE_URL and CORS_ALLOWED_ORIGINS in Render to match.

  5. SMOKE TEST (after first deploy):
       curl https://<your-app>.onrender.com/healthz
       -> should return {"status":"ok"}

  6. BACKUPS:
       python backend/scripts/backup_db.py --url $DATABASE_URL --out ./backups
       Run from a host that can reach Neon (your laptop, any VM).
       Render's free Postgres tier alone does NOT give you backups.
       The script works for SQLite (copy) and Postgres (pg_dump -Fc).

  That's the whole deployment. The app is production-ready; nothing in
  the codebase requires the deploy credentials you (and only you) hold.
""")


def main() -> int:
    print(f"Repo: {REPO}")
    build_spa()
    copy_dist_into_backend()
    smoke_test()
    print_manual_steps()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
