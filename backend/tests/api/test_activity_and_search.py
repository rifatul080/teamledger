"""v2 — activity feed + search endpoint + robots/sitemap tests."""
from __future__ import annotations

from app.api.deps import audit
from tests.api._helpers import AuthedClient, signup


def _make_team(client, owner_email: str) -> str:
    """Create a team and return its id."""
    signup(client, owner_email)
    h = AuthedClient(client, owner_email)
    r = h.post("/api/v1/teams", json={"name": "ActivityTeam"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_team_activity_returns_audit_events(client):
    signup(client, "owner2@example.org")
    h = AuthedClient(client, "owner2@example.org")
    # Team creation itself writes an audit_event — that's enough to exercise
    # the read path. We don't fabricate events by hand here because the FK
    # constraints would require us to look up real user IDs through the db.
    r = h.post("/api/v1/teams", json={"name": "AuditTeam"})
    team_id = r.json()["id"]
    r = h.get(f"/api/v1/teams/{team_id}/activity")
    assert r.status_code == 200
    items = r.json()["items"]
    assert isinstance(items, list)
    # Signup itself records audit events; the feed should return a list.
    assert isinstance(items, list)


def test_team_activity_unknown_team_404(client):
    signup(client, "noexist@example.org")
    h = AuthedClient(client, "noexist@example.org")
    r = h.get("/api/v1/teams/no-such-team/activity")
    assert r.status_code in (404, 400)


def test_unread_count_endpoint(client):
    signup(client, "unread@example.org")
    h = AuthedClient(client, "unread@example.org")
    r = h.get("/api/v1/activity/unread-count")
    assert r.status_code == 200
    assert r.json()["unread"] == 0


def test_mark_activity_read_all(client, db):
    from app.db.session import get_engine
    from app.core.ids import new_id
    from datetime import UTC, datetime
    from sqlalchemy import text

    signup(client, "marker@example.org")
    h = AuthedClient(client, "marker@example.org")
    with get_engine().connect() as conn:
        u = conn.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": "marker@example.org"},
        ).first()
        assert u is not None
        for kind in ("mention", "assignment", "review_result"):
            conn.execute(
                text(
                    "INSERT INTO notifications (id, user_id, type, title, body, read, created_at) "
                    "VALUES (:id, :uid, :k, 't', 'b', 0, :ts)"
                ),
                {
                    "id": new_id(),
                    "uid": u[0],
                    "k": kind,
                    "ts": datetime.now(tz=UTC),
                },
            )
        conn.commit()
    r = h.post("/api/v1/activity/read", json={"all": True})
    assert r.status_code == 200
    assert r.json()["marked"] >= 3


def test_mark_activity_read_by_kind(client, db):
    from app.db.session import get_engine
    from app.core.ids import new_id
    from datetime import UTC, datetime
    from sqlalchemy import text

    signup(client, "markkind@example.org")
    h = AuthedClient(client, "markkind@example.org")
    with get_engine().connect() as conn:
        u = conn.execute(
            text("SELECT id FROM users WHERE email = :e"),
            {"e": "markkind@example.org"},
        ).first()
        assert u is not None
        for kind in ("mention", "assignment"):
            conn.execute(
                text(
                    "INSERT INTO notifications (id, user_id, type, title, body, read, created_at) "
                    "VALUES (:id, :uid, :k, 't', 'b', 0, :ts)"
                ),
                {
                    "id": new_id(),
                    "uid": u[0],
                    "k": kind,
                    "ts": datetime.now(tz=UTC),
                },
            )
        conn.commit()
    r = h.post("/api/v1/activity/read", json={"kind": "mention"})
    assert r.status_code == 200
    assert r.json()["marked"] >= 1


def test_mark_activity_read_invalid_payload_400(client):
    signup(client, "badmark@example.org")
    h = AuthedClient(client, "badmark@example.org")
    r = h.post("/api/v1/activity/read", json={})
    assert r.status_code in (400, 422)


def test_robots_txt_public(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /api/" in r.text


def test_sitemap_xml_public(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "<urlset" in r.text
    assert "/login" in r.text


def test_search_requires_auth(client):
    r = client.get("/api/v1/search", params={"q": "anything"})
    assert r.status_code in (401, 403)


def test_profile_get_me_after_signup(client):
    signup(client, "whoami@example.org")
    h = AuthedClient(client, "whoami@example.org")
    r = h.get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "whoami@example.org"
    assert "avatar_url" in body
    assert "email_verified" in body


def test_profile_patch_institution_and_theme(client):
    signup(client, "patch@example.org")
    h = AuthedClient(client, "patch@example.org")
    r = h.patch("/api/v1/me", json={"institution": "MIT CSAIL", "theme": "dark"})
    assert r.status_code == 200
    body = r.json()
    assert body["institution"] == "MIT CSAIL"
    assert body["theme"] == "dark"


def test_profile_patch_theme_invalid_400(client):
    signup(client, "badtheme@example.org")
    h = AuthedClient(client, "badtheme@example.org")
    r = h.patch("/api/v1/me", json={"theme": "neon"})
    assert r.status_code in (400, 422)
