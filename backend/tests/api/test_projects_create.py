"""Project creation and listing tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def team_with_user(client):
    """Returns a team where the caller is the leader."""
    r1 = client.post(
        "/api/v1/auth/signup",
        json={"email": "p@example.org", "password": "Password1Demo", "display_name": "P", "timezone": "UTC"},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/auth/login", json={"email": "p@example.org", "password": "Password1Demo"})
    assert r2.status_code == 200, r2.text
    r = client.post("/api/v1/teams", json={"name": "T"})
    assert r.status_code == 201, f"create_team failed {r.status_code} {r.text}"
    return r.json()["id"]


@pytest.fixture
def make_project(team_with_user, client):
    def _factory(**kw):
        payload = {"kind": "general", "name": "P"}
        payload.update(kw)
        r = client.post(f"/api/v1/teams/{team_with_user}/projects", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return _factory


@pytest.mark.req_id("PROJ-01")
def test_create_general_project(client, team_with_user) -> None:
    r = client.post(f"/api/v1/teams/{team_with_user}/projects", json={"kind": "general", "name": "P"})
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "general"


@pytest.mark.req_id("PROJ-01")
def test_paper_requires_target_venue(client, team_with_user) -> None:
    r = client.post(
        f"/api/v1/teams/{team_with_user}/projects",
        json={"kind": "paper", "name": "P", "venue_kind": "journal"},
    )
    assert r.status_code == 422


@pytest.mark.req_id("PROJ-01")
def test_paper_venue_kind_required(client, team_with_user) -> None:
    r = client.post(
        f"/api/v1/teams/{team_with_user}/projects",
        json={"kind": "paper", "name": "P", "target_venue": "Nature"},
    )
    assert r.status_code == 422


@pytest.mark.req_id("PROJ-01")
def test_happy_paper_project(client, team_with_user) -> None:
    r = client.post(
        f"/api/v1/teams/{team_with_user}/projects",
        json={"kind": "paper", "name": "Paper P", "target_venue": "Nature", "venue_kind": "journal"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["target_venue"] == "Nature"
    assert body["venue_kind"] == "journal"


@pytest.mark.req_id("PROJ-02")
def test_set_participants_rejects_non_member(client, team_with_user, make_user) -> None:
    proj = make_user.__self__ if False else None  # type: ignore[attr-defined]
    r = client.post(f"/api/v1/teams/{team_with_user}/projects", json={"kind": "general", "name": "P"})
    pid = r.json()["id"]
    # Sign up an outsider
    client.post(
        "/api/v1/auth/logout"
    )
    client.post(
        "/api/v1/auth/signup",
        json={"email": "nobody@example.org", "password": "Password1Demo", "display_name": "N", "timezone": "UTC"},
    )
    # get their user id
    client.post("/api/v1/auth/login", json={"email": "nobody@example.org", "password": "Password1Demo"})
    me = client.get("/api/v1/me").json()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"email": "p@example.org", "password": "Password1Demo"})
    r = client.post(f"/api/v1/projects/{pid}/participants", json=[me["id"]])
    assert r.status_code == 422


@pytest.mark.req_id("PROJ-04")
def test_upsert_multipliers_round_trip(client, team_with_user) -> None:
    r = client.post(f"/api/v1/teams/{team_with_user}/projects", json={"kind": "general", "name": "P"})
    pid = r.json()["id"]
    r = client.put(
        f"/api/v1/projects/{pid}/multipliers",
        json=[{"category_code": "software", "multiplier": "2.5"}],
    )
    assert r.status_code == 200, r.text
    r = client.get(f"/api/v1/projects/{pid}/multipliers")
    data = r.json()
    assert any(m["category_code"] == "software" and float(m["multiplier"]) == 2.5 for m in data)


@pytest.mark.req_id("PROJ-05")
def test_update_timeliness_rejects_invalid(client, team_with_user) -> None:
    r = client.post(f"/api/v1/teams/{team_with_user}/projects", json={"kind": "general", "name": "P"})
    pid = r.json()["id"]
    # late_mild must be ≥ late_medium; here we send 0.5 < 0.7 to violate the rule
    r = client.put(
        f"/api/v1/projects/{pid}/timeliness?on_time_band_days=0&mild_band_days=2&medium_band_days=7&late_mild=0.5&late_medium=0.7&late_severe=0.3",
    )
    assert r.status_code == 422


@pytest.mark.req_id("PROJ-08")
def test_get_credit_categories(client) -> None:
    # login first
    client.post(
        "/api/v1/auth/signup",
        json={"email": "cat@example.org", "password": "Password1Demo", "display_name": "C", "timezone": "UTC"},
    )
    client.post("/api/v1/auth/login", json={"email": "cat@example.org", "password": "Password1Demo"})
    r = client.get("/api/v1/credit-categories")
    assert r.status_code == 200
    codes = {c["code"] for c in r.json()}
    expected = {
        "conceptualization",
        "data_curation",
        "formal_analysis",
        "funding_acquisition",
        "investigation",
        "methodology",
        "project_administration",
        "resources",
        "software",
        "supervision",
        "validation",
        "visualization",
        "writing_original_draft",
        "writing_review_editing",
    }
    assert expected <= codes
