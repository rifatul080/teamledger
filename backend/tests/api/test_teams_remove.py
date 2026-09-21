"""Team member removal and chat disconnect."""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup


def _member_id(client, team_id: str, email: str, as_client: AuthedClient | None = None) -> str:
    caller = as_client or client
    r = caller.get(f"/api/v1/teams/{team_id}/members")
    data = r.json()
    if isinstance(data, dict):
        raise AssertionError(f"unexpected payload: {data}")
    for m in data:
        if m["email"] == email:
            return m["user_id"]
    raise AssertionError(email)


@pytest.mark.req_id("TEAM-04")
def test_leader_can_remove_member(client) -> None:
    signup(client, "a@example.org", "Leader")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    leader = AuthedClient(client, "a@example.org")
    b_uid = _member_id(client, team_id, "b@example.org", as_client=leader)
    r = leader.delete(f"/api/v1/teams/{team_id}/members/{b_uid}")
    assert r.status_code == 204


@pytest.mark.req_id("TEAM-04")
def test_member_cannot_remove_others(client) -> None:
    signup(client, "a@example.org", "Leader")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    signup(client, "c@example.org", "C")
    inv_b = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv_b['token']}/accept")
    leader = AuthedClient(client, "a@example.org")
    a_uid = _member_id(client, team_id, "a@example.org", as_client=leader)
    member = AuthedClient(client, "b@example.org")
    r = member.delete(f"/api/v1/teams/{team_id}/members/{a_uid}")
    assert r.status_code == 403


@pytest.mark.req_id("TEAM-05")
def test_leader_cannot_be_removed(client) -> None:
    signup(client, "a@example.org", "Leader")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    a_uid = _member_id(client, team_id, "a@example.org", as_client=leader)
    r = leader.delete(f"/api/v1/teams/{team_id}/members/{a_uid}")
    assert r.status_code == 422


@pytest.mark.req_id("TEAM-05")
def test_transfer_leadership_keeps_one_leader(client) -> None:
    signup(client, "a@example.org", "Leader")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    leader = AuthedClient(client, "a@example.org")
    b_uid = _member_id(client, team_id, "b@example.org", as_client=leader)
    r = leader.post(f"/api/v1/teams/{team_id}/transfer-leader", json={"new_leader_user_id": b_uid})
    assert r.status_code == 200
    r = leader.get(f"/api/v1/teams/{team_id}/members")
    roles = {m["email"]: m["role"] for m in r.json()}
    assert roles["a@example.org"] == "member"
    assert roles["b@example.org"] == "leader"
