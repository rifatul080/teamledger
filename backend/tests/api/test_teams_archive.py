"""Archive tests."""
from __future__ import annotations

import pytest

from _helpers import AuthedClient, signup


@pytest.mark.req_id("TEAM-06")
def test_archive_blocks_mutations(client) -> None:
    signup(client, "a@example.org")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    r = leader.post(f"/api/v1/teams/{team_id}/archive")
    assert r.status_code == 204
    r = leader.patch(f"/api/v1/teams/{team_id}", json={"name": "X"})
    assert r.status_code == 423
    r = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "new@example.org"})
    assert r.status_code == 423


@pytest.mark.req_id("TEAM-06")
def test_archive_requires_leader(client) -> None:
    signup(client, "a@example.org")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    member = AuthedClient(client, "b@example.org")
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    member = AuthedClient(client, "b@example.org")
    r = member.post(f"/api/v1/teams/{team_id}/archive")
    assert r.status_code == 403
