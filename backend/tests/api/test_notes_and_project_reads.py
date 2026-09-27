"""Personal notes CRUD + isolation, and the project participants/tasks reads."""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup


def _uid(c: AuthedClient) -> str:
    r = c.get("/api/v1/me")
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture
def alice(client):
    signup(client, "alice@example.org", "Alice")
    return AuthedClient(client, "alice@example.org")


@pytest.fixture
def bob(client):
    signup(client, "bob@example.org", "Bob")
    return AuthedClient(client, "bob@example.org")


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------


def test_create_and_list_notes(alice) -> None:
    r = alice.post("/api/v1/me/notes", json={"title": "Ideas", "content": "ship it"})
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["title"] == "Ideas"
    assert note["pinned"] is False

    listed = alice.get("/api/v1/me/notes")
    assert listed.status_code == 200, listed.text
    assert [n["id"] for n in listed.json()] == [note["id"]]


def test_note_defaults_to_empty_strings(alice) -> None:
    r = alice.post("/api/v1/me/notes", json={})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == ""
    assert body["content"] == ""


def test_update_note_fields_and_pinned_order(alice) -> None:
    first = alice.post("/api/v1/me/notes", json={"title": "A", "content": "a"}).json()
    second = alice.post("/api/v1/me/notes", json={"title": "B", "content": "b"}).json()

    r = alice.patch(f"/api/v1/me/notes/{first['id']}", json={"pinned": True, "content": "a2"})
    assert r.status_code == 200, r.text
    assert r.json()["pinned"] is True
    assert r.json()["content"] == "a2"

    listed = [n["id"] for n in alice.get("/api/v1/me/notes").json()]
    # Pinned first, then newest-first within the rest.
    assert listed[0] == first["id"]
    assert listed[1] == second["id"]




# --------------------------------------------------------------------------
# Project participants + flat task list (drives the assignee pickers)
# --------------------------------------------------------------------------


@pytest.fixture
def project(client):
    signup(client, "lead@example.org", "Lead")
    lead = AuthedClient(client, "lead@example.org")
    team_id = lead.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "mate@example.org", "Mate")
    mate = AuthedClient(client, "mate@example.org")
    inv = lead.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "mate@example.org"}
    ).json()
    mate.post(f"/api/v1/invitations/{inv['token']}/accept")
    ids = [_uid(lead), _uid(mate)]
    proj = lead.post(
        f"/api/v1/teams/{team_id}/projects",
        json={"kind": "general", "name": "Proj", "participant_user_ids": ids},
    ).json()
    return {"lead": lead, "team_id": team_id, "project_id": proj["id"], "ids": ids}


def test_get_project_participants(project) -> None:
    r = project["lead"].get(f"/api/v1/projects/{project['project_id']}/participants")
    assert r.status_code == 200, r.text
    assert sorted(r.json()) == sorted(project["ids"])


def test_get_project_participants_requires_membership(project, alice) -> None:
    r = alice.get(f"/api/v1/projects/{project['project_id']}/participants")
    assert r.status_code == 404, r.text  # non-members get team.not_found


def test_get_project_tasks_empty_when_no_goals(project) -> None:
    r = project["lead"].get(f"/api/v1/projects/{project['project_id']}/tasks")
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_get_project_tasks_404_for_unknown_project(project) -> None:
    assert project["lead"].get("/api/v1/projects/nope/tasks").status_code == 404


def _mk_task(lead, ms_id: str, assignee: str, title: str, due: str) -> None:
    r = lead.post(
        "/api/v1/tasks",
        json={
            "milestone_id": ms_id,
            "assignee_user_id": assignee,
            "title": title,
            "category_code": "software",
            "weight": 1,
            "est_hours": 1,
            "start_date": "2026-01-01",
            "due_date": due,
        },
    )
    assert r.status_code == 201, r.text


def test_get_project_tasks_is_flat_and_due_ordered(project) -> None:
    lead = project["lead"]
    g = lead.post(
        "/api/v1/goals",
        json={"project_id": project["project_id"], "title": "G", "target_date": "2026-12-31"},
    ).json()
    m1 = lead.post(
        f"/api/v1/goals/{g['id']}/milestones", json={"title": "M1", "due_date": "2026-06-30"}
    ).json()
    m2 = lead.post(
        f"/api/v1/goals/{g['id']}/milestones", json={"title": "M2", "due_date": "2026-05-31"}
    ).json()
    _mk_task(lead, m1["id"], project["ids"][0], "later", "2026-09-30")
    _mk_task(lead, m2["id"], project["ids"][0], "sooner", "2026-02-01")

    r = lead.get(f"/api/v1/projects/{project['project_id']}/tasks")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [t["title"] for t in rows] == ["sooner", "later"]
    assert rows[0]["assignee_user_id"] == project["ids"][0]


def test_get_project_tasks_visible_to_members(project) -> None:
    lead, mate_uid = project["lead"], project["ids"][1]
    g = lead.post(
        "/api/v1/goals",
        json={"project_id": project["project_id"], "title": "G", "target_date": "2026-12-31"},
    ).json()
    m = lead.post(
        f"/api/v1/goals/{g['id']}/milestones", json={"title": "M", "due_date": "2026-06-30"}
    ).json()
    _mk_task(lead, m["id"], mate_uid, "assigned to mate", "2026-03-01")

    r = project["lead"].get(f"/api/v1/projects/{project['project_id']}/tasks")
    assert r.status_code == 200
    assert [t["title"] for t in r.json()] == ["assigned to mate"]

def test_delete_note_is_204_and_idempotent(alice) -> None:
    note = alice.post("/api/v1/me/notes", json={"title": "temp"}).json()
    r = alice.delete(f"/api/v1/me/notes/{note['id']}")
    assert r.status_code == 204, r.text
    # Deleting again must not 500 (no row to delete).
    assert alice.delete(f"/api/v1/me/notes/{note['id']}").status_code == 204
    assert alice.get("/api/v1/me/notes").json() == []


def test_notes_are_private_per_user(alice, bob) -> None:
    note = alice.post("/api/v1/me/notes", json={"title": "Secret", "content": "nope"}).json()
    assert bob.get("/api/v1/me/notes").json() == []
    # Cross-user access by id is a 404, not a 403 — no existence leak.
    assert bob.patch(f"/api/v1/me/notes/{note['id']}", json={"title": "hacked"}).status_code == 404
    assert bob.delete(f"/api/v1/me/notes/{note['id']}").status_code == 204
    # Alice's note survived Bob's delete attempt.
    assert [n["id"] for n in alice.get("/api/v1/me/notes").json()] == [note["id"]]


def test_notes_require_auth(client) -> None:
    assert client.get("/api/v1/me/notes").status_code == 401
    assert client.post("/api/v1/me/notes", json={"title": "x"}).status_code == 401


def test_note_title_length_limit(alice) -> None:
    assert alice.post("/api/v1/me/notes", json={"title": "x" * 256}).status_code == 422
