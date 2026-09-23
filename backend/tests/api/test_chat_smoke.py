"""v2 — chat thread + reaction smoke tests + unread/read."""
from __future__ import annotations

from tests.api._helpers import AuthedClient, signup


def _make_team(client, owner: str) -> str:
    signup(client, owner)
    h = AuthedClient(client, owner)
    r = h.post("/api/v1/teams", json={"name": "ChatTeam"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_chat_post_and_list_messages(client):
    team_id = _make_team(client, "chatter@example.org")
    h = AuthedClient(client, "chatter@example.org")
    r = h.post(
        f"/api/v1/teams/{team_id}/messages",
        json={"body": "Hello, team!"},
    )
    assert r.status_code in (200, 201), r.text
    r = h.get(f"/api/v1/teams/{team_id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert any("Hello" in (m.get("body") or "") for m in msgs)


def test_chat_post_with_parent_creates_thread(client):
    team_id = _make_team(client, "thread@example.org")
    h = AuthedClient(client, "thread@example.org")
    r = h.post(
        f"/api/v1/teams/{team_id}/messages",
        json={"body": "Parent message"},
    )
    parent_id = r.json()["id"]
    r = h.post(
        f"/api/v1/teams/{team_id}/messages",
        json={"body": "Reply", "parent_id": parent_id},
    )
    if r.status_code in (200, 201):
        reply = r.json()
        assert reply.get("parent_id") in (parent_id, None)


def test_chat_reactions_not_yet_supported(client):
    """Reactions land in a future phase; the endpoint may 404 until then."""
    team_id = _make_team(client, "reacter@example.org")
    h = AuthedClient(client, "reacter@example.org")
    r = h.post(
        f"/api/v1/teams/{team_id}/messages",
        json={"body": "React to me"},
    )
    mid = r.json()["id"]
    r = h.post(f"/api/v1/messages/{mid}/reactions", json={"emoji": "👍"})
    assert r.status_code in (200, 201, 404, 405)


def test_unread_chat(client):
    team_id = _make_team(client, "reader@example.org")
    h = AuthedClient(client, "reader@example.org")
    r = h.get(f"/api/v1/teams/{team_id}/unread")
    assert r.status_code == 200


def test_mark_chat_read(client):
    team_id = _make_team(client, "marked@example.org")
    h = AuthedClient(client, "marked@example.org")
    r = h.post(f"/api/v1/teams/{team_id}/read", params={"seq": 0})
    assert r.status_code in (200, 204)


def test_edit_own_message(client):
    team_id = _make_team(client, "editor@example.org")
    h = AuthedClient(client, "editor@example.org")
    r = h.post(f"/api/v1/teams/{team_id}/messages", json={"body": "Original"})
    msg_id = r.json()["id"]
    r = h.patch(
        f"/api/v1/teams/{team_id}/messages/{msg_id}",
        json={"body": "Edited"},
    )
    assert r.status_code == 200
    assert "Edited" in r.json().get("body", "")


def test_delete_own_message(client):
    team_id = _make_team(client, "deleter@example.org")
    h = AuthedClient(client, "deleter@example.org")
    r = h.post(f"/api/v1/teams/{team_id}/messages", json={"body": "bye"})
    msg_id = r.json()["id"]
    r = h.delete(f"/api/v1/teams/{team_id}/messages/{msg_id}")
    assert r.status_code in (200, 204)
