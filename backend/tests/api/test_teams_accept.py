"""Invitation accept tests."""
from __future__ import annotations

import pytest

from _helpers import AuthedClient, signup


@pytest.mark.req_id("TEAM-03")
def test_accept_unknown_token_404(client) -> None:
    signup(client, "a@example.org")
    a = AuthedClient(client, "a@example.org")
    r = a.post("/api/v1/invitations/nonexistent-token/accept")
    assert r.status_code == 404


@pytest.mark.req_id("TEAM-03")
def test_accept_in_app_invite_by_wrong_user_rejected(client) -> None:
    signup(client, "a@example.org", "Leader")
    leader = AuthedClient(client, "a@example.org")
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    signup(client, "b@example.org", "B")
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "b@example.org"}
    ).json()
    # The invitation kind is 'in_app' and has a (link-shaped) token too.
    signup(client, "c@example.org", "C")
    c = AuthedClient(client, "c@example.org")
    r = c.post(f"/api/v1/invitations/{inv['token']}/accept")
    assert r.status_code in (403, 404)
