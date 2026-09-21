"""Goal and milestone endpoint tests."""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup


@pytest.fixture
def project(client):
    signup(client, "p@example.org", "P")
    leader = AuthedClient(client, "p@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    proj = leader.post(
        f"/api/v1/teams/{team_id}/projects",
        json={"kind": "general", "name": "Proj"},
    ).json()
    return leader, team_id, proj["id"]


def test_create_goal_get_list_delete(client, project) -> None:
    leader, _team_id, project_id = project
    r = leader.post(
        "/api/v1/goals",
        json={"project_id": project_id, "title": "G1", "description": "d", "target_date": "2026-12-31"},
    )
    assert r.status_code == 201, r.text
    g = r.json()
    g_id = g["id"]
    assert g["title"] == "G1"
    assert g["progress_pct"] == 0.0

    # Get
    r = leader.get(f"/api/v1/goals/{g_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "G1"

    # List
    r = leader.get(f"/api/v1/projects/{project_id}/goals")
    assert r.status_code == 200
    assert any(g2["id"] == g_id for g2 in r.json())

    # Delete
    r = leader.delete(f"/api/v1/goals/{g_id}")
    assert r.status_code == 204
    r = leader.get(f"/api/v1/goals/{g_id}")
    assert r.status_code == 404


def test_create_milestone_get_list_delete(client, project) -> None:
    leader, _, project_id = project
    g_id = leader.post(
        "/api/v1/goals",
        json={"project_id": project_id, "title": "G1", "target_date": "2026-12-31"},
    ).json()["id"]
    r = leader.post(
        f"/api/v1/goals/{g_id}/milestones",
        json={"title": "M1", "due_date": "2026-06-30"},
    )
    assert r.status_code == 201
    m = r.json()
    assert m["title"] == "M1"
    assert m["completed_at"] is None

    # Toggle complete
    r = leader.patch(f"/api/v1/milestones/{m['id']}", json={"complete": True})
    assert r.status_code == 200
    assert r.json()["completed_at"] is not None

    # List milestones
    r = leader.get(f"/api/v1/goals/{g_id}/milestones")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Delete
    r = leader.delete(f"/api/v1/milestones/{m['id']}")
    assert r.status_code == 204


def test_member_cannot_create_goal(client, project) -> None:
    leader, team_id, project_id = project
    signup(client, "b@example.org", "B")
    member = AuthedClient(client, "b@example.org")
    r = leader.post(
        f"/api/v1/teams/{team_id}/invitations",
        json={"email": "b@example.org"},
    ).json()
    member.post(f"/api/v1/invitations/{r['token']}/accept")
    r = member.post(
        "/api/v1/goals",
        json={"project_id": project_id, "title": "G1", "target_date": "2026-12-31"},
    )
    assert r.status_code == 403


def test_anon_cannot_read_goals(client, project, app) -> None:
    _leader, _, project_id = project
    # Use a fresh client with no cookies
    from fastapi.testclient import TestClient

    anon = TestClient(app)
    r = anon.get(f"/api/v1/projects/{project_id}/goals")
    assert r.status_code == 401


def test_milestone_toggle_complete(client, project) -> None:
    leader, _, project_id = project
    g_id = leader.post(
        "/api/v1/goals",
        json={"project_id": project_id, "title": "G1", "target_date": "2026-12-31"},
    ).json()["id"]
    m_id = leader.post(
        f"/api/v1/goals/{g_id}/milestones",
        json={"title": "M1", "due_date": "2026-06-30"},
    ).json()["id"]
    # Toggle on
    r = leader.patch(f"/api/v1/milestones/{m_id}", json={"complete": True})
    assert r.status_code == 200
    assert r.json()["completed_at"] is not None
    # Toggle off
    r = leader.patch(f"/api/v1/milestones/{m_id}", json={"complete": False})
    assert r.status_code == 200
    assert r.json()["completed_at"] is None
