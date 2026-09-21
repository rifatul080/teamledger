"""Task lifecycle tests: create, submit, review, split, propose+approve."""
from __future__ import annotations

import pytest

from _helpers import AuthedClient, signup


@pytest.fixture
def world(client):
    """Returns (leader, member, team_id, project_id)."""
    signup(client, "lead@example.org", "Lead")
    leader = AuthedClient(client, "lead@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "mem@example.org", "Mem")
    member = AuthedClient(client, "mem@example.org")
    inv = leader.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "mem@example.org"}
    ).json()
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    leader_uid = _uid_simple(leader)
    mem_uid = _uid_simple(member)
    proj = leader.post(
        f"/api/v1/teams/{team_id}/projects",
        json={"kind": "general", "name": "Proj", "participant_user_ids": [leader_uid, mem_uid]},
    ).json()
    return leader, member, team_id, proj["id"]


def _uid_simple(c: AuthedClient) -> str:
    me = c.get("/api/v1/me")
    assert me.status_code == 200, me.text
    return me.json()["id"]


def _uid(c: AuthedClient) -> str:
    me = c.get("/api/v1/me")
    assert me.status_code == 200, me.text
    return me.json()["id"]


def _make_milestone(leader: AuthedClient, project_id: str) -> str:
    g = leader.post(
        f"/api/v1/goals",
        json={"project_id": project_id, "title": "G", "target_date": "2026-12-31"},
    ).json()
    m = leader.post(
        f"/api/v1/goals/{g['id']}/milestones",
        json={"title": "M", "due_date": "2026-06-30"},
    ).json()
    return m["id"]


def _task_base(ms_id: str, assignee: str, **overrides) -> dict:
    base = {
        "milestone_id": ms_id,
        "assignee_user_id": assignee,
        "title": "Write code",
        "description": "Implement X",
        "category_code": "software",
        "weight": 5,
        "est_hours": 10,
        "start_date": "2026-01-01",
        "due_date": "2026-02-01",
    }
    base.update(overrides)
    return base


def test_create_task_as_leader(client, world) -> None:
    leader, _, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    leader_uid = _uid(leader)
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, leader_uid))
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["title"] == "Write code"
    assert t["status"] == "todo"


def test_task_assignee_must_be_participant(client, world) -> None:
    leader, _, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    # Sign up someone who is NOT a member of the team
    signup(client, "outsider@example.org", "Out")
    outsider = AuthedClient(client, "outsider@example.org")
    out_uid = _uid_simple(outsider)
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, out_uid))
    assert r.status_code == 422
    assert "participant" in r.text.lower()


def test_propose_and_approve(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader.put(f"/api/v1/projects/{project_id}/participants", json={"user_ids": [mem_uid]})
    r = member.post(
        "/api/v1/tasks/propose",
        json={
            "milestone_id": ms_id,
            "title": "Idea",
            "category_code": "writing_original_draft",
            "weight": 2,
            "est_hours": 4,
            "start_date": "2026-01-01",
            "due_date": "2026-02-01",
        },
    )
    assert r.status_code == 201, r.text
    proposed = r.json()
    assert proposed["status"] == "proposed"
    r = leader.post(f"/api/v1/tasks/{proposed['id']}/approve-proposal")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "todo"


def test_submit_and_review_flow(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader_uid = _uid(leader)
    leader.put(f"/api/v1/projects/{project_id}/participants", json={"user_ids": [mem_uid]})
    r = leader.post(
        "/api/v1/tasks",
        json=_task_base(ms_id, mem_uid, title="Do it", category_code="investigation", weight=4),
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    r = member.post(f"/api/v1/tasks/{task_id}/submit", json={"note": "done!"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_review"
    r = leader.post(
        f"/api/v1/tasks/{task_id}/review",
        json={"decision": "accept", "quality": 3, "note": "ok"},
    )
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["status"] == "done"


def test_split_task(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader_uid = _uid(leader)
    leader.put(
        f"/api/v1/projects/{project_id}/participants",
        json={"user_ids": [mem_uid, leader_uid]},
    )
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, mem_uid, weight=10, est_hours=20))
    task_id = r.json()["id"]
    r = leader.post(
        f"/api/v1/tasks/{task_id}/split",
        json={
            "new_assignee_user_id": leader_uid,
            "weight": 5,
            "est_hours": 10,
            "category_code": "software",
            "title": "Half",
        },
    )
    assert r.status_code == 201, r.text
    new_task = r.json()
    assert new_task["assignee_user_id"] == leader_uid
    assert new_task["weight"] == 5


def test_member_cannot_change_assignee(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader_uid = _uid(leader)
    leader.put(f"/api/v1/projects/{project_id}/participants", json={"user_ids": [mem_uid]})
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, mem_uid))
    task_id = r.json()["id"]
    r = member.patch(f"/api/v1/tasks/{task_id}", json={"assignee_user_id": leader_uid})
    assert r.status_code == 403


def test_list_milestone_tasks(client, world) -> None:
    leader, _, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    leader_uid = _uid(leader)
    leader.post("/api/v1/tasks", json=_task_base(ms_id, leader_uid, title="T1"))
    r = leader.get(f"/api/v1/milestones/{ms_id}/tasks")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_anon_cannot_read_task(client, world, app) -> None:
    from fastapi.testclient import TestClient

    leader, _, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    leader_uid = _uid(leader)
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, leader_uid))
    task_id = r.json()["id"]
    anon = TestClient(app)
    r = anon.get(f"/api/v1/tasks/{task_id}")
    assert r.status_code == 401


def test_review_reject_sets_needs_rework_then_resubmit(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader.put(f"/api/v1/projects/{project_id}/participants", json={"user_ids": [mem_uid]})
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, mem_uid))
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]
    # First submission
    r = member.post(f"/api/v1/tasks/{task_id}/submit", json={"note": "v1"})
    assert r.status_code == 200, r.text
    # Leader rejects → needs_rework
    r = leader.post(
        f"/api/v1/tasks/{task_id}/review",
        json={"decision": "reject", "quality": 2, "note": "fix bugs"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "needs_rework"
    # Member resubmits → in_review
    r = member.post(f"/api/v1/tasks/{task_id}/submit", json={"note": "v2"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_review"
    # Leader accepts → done
    r = leader.post(
        f"/api/v1/tasks/{task_id}/review",
        json={"decision": "accept", "quality": 4, "note": "ok"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"


def test_member_cannot_review_others_task(client, world) -> None:
    leader, member, _, project_id = world
    ms_id = _make_milestone(leader, project_id)
    mem_uid = _uid(member)
    leader.put(f"/api/v1/projects/{project_id}/participants", json={"user_ids": [mem_uid]})
    r = leader.post("/api/v1/tasks", json=_task_base(ms_id, mem_uid))
    task_id = r.json()["id"]
    r = member.post(
        f"/api/v1/tasks/{task_id}/review",
        json={"decision": "accept", "quality": 3},
    )
    assert r.status_code == 403
