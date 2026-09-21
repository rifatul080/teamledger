"""Invitations: create + accept."""
from __future__ import annotations

import pytest

from _helpers import AuthedClient, signup


@pytest.mark.req_id("TEAM-02")
def test_invite_existing_user_creates_in_app_invitation(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"})
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "in_app"
    assert body["email"] == "b@example.org"


@pytest.mark.req_id("TEAM-02")
def test_invite_unknown_email_creates_link(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "new@example.org"})
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "link"
    assert body["token"]


@pytest.mark.req_id("TEAM-02")
def test_invite_requires_leader(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "c@example.org"})
    inv_b = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv_b['token']}/accept")
    r = member.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "x@example.org"})
    assert r.status_code == 403


@pytest.mark.req_id("TEAM-02")
def test_invite_self_rejected(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "a@example.org"})
    assert r.status_code == 422


@pytest.mark.req_id("TEAM-02")
def test_invite_already_member_conflict(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    inv = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"})
    assert r.status_code == 409


@pytest.mark.req_id("TEAM-02")
def test_invite_link_accept_unknown_user_signup_then_accept(client) -> None:
    signup(client, "a@example.org", "A")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "new@example.org"}
    ).json()
    signup(client, "new@example.org", "New")
    new_user = AuthedClient(client, "new@example.org")
    r = new_user.post(f"/api/v1/invitations/{inv['token']}/accept")
    assert r.status_code == 200
    assert r.json()["role"] == "member"
