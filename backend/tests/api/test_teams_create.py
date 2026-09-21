"""Team creation and listing."""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup


@pytest.fixture
def auth(client):
    def _factory(email: str = "leader@example.org") -> AuthedClient:
        signup(client, email)
        return AuthedClient(client, email)

    return _factory


@pytest.mark.req_id("TEAM-01")
def test_create_team_as_authed_user_makes_leader(client, auth) -> None:
    c = auth()
    r = c.post("/api/v1/teams", json={"name": "Test Team", "description": "first team"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "Test Team"
    assert body["role"] == "leader"
    assert body["archived"] is False


@pytest.mark.req_id("TEAM-01")
def test_create_team_requires_auth(client) -> None:
    r = client.post("/api/v1/teams", json={"name": "X"})
    assert r.status_code == 401


@pytest.mark.req_id("TEAM-01")
def test_create_team_rejects_empty_name(client, auth) -> None:
    c = auth()
    r = c.post("/api/v1/teams", json={"name": ""})
    assert r.status_code == 422


@pytest.mark.req_id("TEAM-01")
def test_list_my_teams(client, auth) -> None:
    c = auth()
    c.post("/api/v1/teams", json={"name": "A"})
    c.post("/api/v1/teams", json={"name": "B"})
    r = c.get("/api/v1/teams")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert {"A", "B"} <= names


@pytest.mark.req_id("TEAM-07")
def test_create_team_sets_exactly_one_leader(client, auth) -> None:
    c = auth()
    r = c.post("/api/v1/teams", json={"name": "L"})
    assert r.status_code == 201
    team_id = r.json()["id"]
    r = c.get(f"/api/v1/teams/{team_id}/members")
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 1
    assert members[0]["role"] == "leader"
