"""Direct add-member + Discord-style invite-link + accept flow."""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup

# --- Direct add member (existing user, no email) --------------------------


@pytest.mark.req_id("TEAM-12")
def test_add_existing_user_succeeds(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "b@example.org", "B")
    r = leader.post(f"/api/v1/teams/{team_id}/members", json={"email": "b@example.org"})
    assert r.status_code == 201
    assert r.json()["email"] == "b@example.org"
    assert r.json()["role"] == "member"
    # And they're now in the members list.
    members = leader.get(f"/api/v1/teams/{team_id}/members").json()
    emails = {m["email"] for m in members}
    assert "b@example.org" in emails


@pytest.mark.req_id("TEAM-12")
def test_add_unknown_email_returns_404(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    r = leader.post(
        f"/api/v1/teams/{team_id}/members", json={"email": "nobody@example.org"}
    )
    assert r.status_code == 404
    assert r.json()["code"] == "team.user_unknown"


@pytest.mark.req_id("TEAM-12")
def test_add_self_rejected(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    r = leader.post(
        f"/api/v1/teams/{team_id}/members", json={"email": "a@example.org"}
    )
    assert r.status_code == 422


@pytest.mark.req_id("TEAM-12")
def test_add_already_member_conflict(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "b@example.org", "B")
    leader.post(f"/api/v1/teams/{team_id}/members", json={"email": "b@example.org"})
    r = leader.post(
        f"/api/v1/teams/{team_id}/members", json={"email": "b@example.org"}
    )
    assert r.status_code == 409


@pytest.mark.req_id("TEAM-12")
def test_add_member_requires_leader(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "b@example.org", "B")
    leader.post(f"/api/v1/teams/{team_id}/members", json={"email": "b@example.org"})
    member = AuthedClient(client, "b@example.org")
    signup(client, "c@example.org", "C")
    r = member.post(
        f"/api/v1/teams/{team_id}/members", json={"email": "c@example.org"}
    )
    assert r.status_code == 403


# --- Discord-style invite link --------------------------------------------


@pytest.mark.req_id("TEAM-13")
def test_create_invite_link_returns_url(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    r = leader.post(f"/api/v1/teams/{team_id}/invite-link")
    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["url"].endswith(f"/accept-invite?token={body['token']}")


@pytest.mark.req_id("TEAM-13")
def test_invite_link_any_user_can_accept(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    token = leader.post(f"/api/v1/teams/{team_id}/invite-link").json()["token"]
    # A brand-new user — different email entirely — accepts.
    signup(client, "stranger@example.org", "S")
    stranger = AuthedClient(client, "stranger@example.org")
    r = stranger.post(f"/api/v1/invitations/{token}/accept")
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    assert r.json()["team_id"] == team_id


@pytest.mark.req_id("TEAM-13")
def test_invite_link_used_only_once(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    token = leader.post(f"/api/v1/teams/{team_id}/invite-link").json()["token"]
    signup(client, "b@example.org", "B")
    AuthedClient(client, "b@example.org").post(
        f"/api/v1/invitations/{token}/accept"
    )
    # Second user tries the same token — should fail (consumed).
    signup(client, "c@example.org", "C")
    r = AuthedClient(client, "c@example.org").post(
        f"/api/v1/invitations/{token}/accept"
    )
    assert r.status_code == 409
    assert r.json()["code"] == "invitation.consumed"


@pytest.mark.req_id("TEAM-13")
def test_invite_link_preview_endpoint(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    token = leader.post(f"/api/v1/teams/{team_id}/invite-link").json()["token"]
    # Public preview — no auth.
    r = client.get(f"/api/v1/invitations/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["team_id"] == team_id
    assert body["team_name"] == "T"
    # No PII: no member list, no inviter email.
    assert "members" not in body
    assert "invited_by" not in body


@pytest.mark.req_id("TEAM-13")
def test_invite_link_expired(client, db_engine) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    token = leader.post(f"/api/v1/teams/{team_id}/invite-link").json()["token"]
    # Force expiry by direct DB write.
    from datetime import UTC, datetime, timedelta

    from app.models.invitation import Invitation
    from sqlalchemy.orm import sessionmaker

    SF = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SF() as db:
        inv = db.query(Invitation).filter(Invitation.token == token).one()
        inv.expires_at = datetime.now(tz=UTC) - timedelta(seconds=10)
        db.commit()
    signup(client, "b@example.org", "B")
    r = AuthedClient(client, "b@example.org").post(
        f"/api/v1/invitations/{token}/accept"
    )
    assert r.status_code == 422
    assert r.json()["code"] == "invitation.expired"


@pytest.mark.req_id("TEAM-13")
def test_invite_link_requires_leader(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "b@example.org", "B")
    inv_b = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    AuthedClient(client, "b@example.org").post(
        f"/api/v1/invitations/{inv_b['token']}/accept"
    )
    member = AuthedClient(client, "b@example.org")
    r = member.post(f"/api/v1/teams/{team_id}/invite-link")
    assert r.status_code == 403
