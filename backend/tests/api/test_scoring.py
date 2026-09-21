"""Scoring + author order endpoints: live compute, finalize, exports."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from _helpers import AuthedClient, signup


def D(s: str | int | float) -> Decimal:
    return Decimal(str(s))


@pytest.fixture
def world(client):
    """Two members, leader sets participant list, project with one milestone."""
    signup(client, "sl@example.org", "Sadia")
    leader = AuthedClient(client, "sl@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "ScoreT"}).json()["id"]
    signup(client, "s1@example.org", "Aisha")
    aisha = AuthedClient(client, "s1@example.org")
    signup(client, "s2@example.org", "Bina")
    bina = AuthedClient(client, "s2@example.org")
    inv1 = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "s1@example.org"}).json()
    aisha.post(f"/api/v1/invitations/{inv1['token']}/accept")
    inv2 = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "s2@example.org"}).json()
    bina.post(f"/api/v1/invitations/{inv2['token']}/accept")
    a_uid = aisha.get("/api/v1/me").json()["id"]
    b_uid = bina.get("/api/v1/me").json()["id"]
    proj = leader.post(
        f"/api/v1/teams/{team_id}/projects",
        json={"kind": "general", "name": "ScoreProj", "participant_user_ids": [a_uid, b_uid]},
    ).json()
    return {"leader": leader, "aisha": aisha, "bina": bina, "team_id": team_id, "project_id": proj["id"], "a_uid": a_uid, "b_uid": b_uid}


def _ms(leader: AuthedClient, project_id: str) -> str:
    g_id = leader.post(
        f"/api/v1/goals",
        json={"project_id": project_id, "title": "G", "target_date": "2026-12-31"},
    ).json()["id"]
    return leader.post(
        f"/api/v1/goals/{g_id}/milestones",
        json={"title": "M", "due_date": "2026-06-30"},
    ).json()["id"]


def _task(leader: AuthedClient, ms_id: str, assignee: str, *, weight: int = 5, hours: int = 10) -> str:
    r = leader.post(
        "/api/v1/tasks",
        json={
            "milestone_id": ms_id,
            "assignee_user_id": assignee,
            "title": "T",
            "description": "d",
            "category_code": "software",
            "weight": weight,
            "est_hours": hours,
            "start_date": "2026-01-01",
            "due_date": "2026-02-01",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_live_score_shape_with_zero_tasks(client, world) -> None:
    leader = world["leader"]
    r = leader.get(f"/api/v1/projects/{world['project_id']}/score")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == world["project_id"]
    assert "formula_version" in body
    assert isinstance(body["participants"], list)
    assert isinstance(body["suggested_order"], list)


def test_live_score_includes_only_done_tasks(client, world) -> None:
    leader = world["leader"]
    aisha = world["aisha"]
    ms = _ms(leader, world["project_id"])
    # Two tasks; one accepted (counts), one not accepted (does not count).
    t1 = _task(leader, ms, world["a_uid"])
    t2 = _task(leader, ms, world["b_uid"])
    # Submit + accept t1
    a = AuthedClient(client, "s1@example.org")
    r = a.post(f"/api/v1/tasks/{t1}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t1}/review", json={"decision": "accept", "quality": 3})
    assert r.status_code == 200, r.text
    # Submit t2 but don't accept
    b = AuthedClient(client, "s2@example.org")
    r = b.post(f"/api/v1/tasks/{t2}/submit", json={"note": "ok"})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{world['project_id']}/score").json()
    # Aisha's total > 0, Bina's total = 0.
    by_user = {p["user_id"]: p for p in body["participants"]}
    assert D(by_user[world["a_uid"]]["total_points"]) > 0
    assert D(by_user[world["b_uid"]]["total_points"]) == 0
    # suggested_order sorted descending by points
    order = body["suggested_order"]
    assert order[0]["user_id"] == world["a_uid"]


def test_finalize_rejects_double_finalize(client, world) -> None:
    leader = world["leader"]
    a = AuthedClient(client, "s1@example.org")
    ms = _ms(leader, world["project_id"])
    t = _task(leader, ms, world["a_uid"])
    r = a.post(f"/api/v1/tasks/{t}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t}/review", json={"decision": "accept", "quality": 3})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{world['project_id']}/score").json()
    positions = [{"position": i + 1, "user_id": p["user_id"]} for i, p in enumerate(body["participants"])]
    r = leader.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 201, r.text
    r = leader.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 422


def test_finalize_persists_snapshot(client, world) -> None:
    leader = world["leader"]
    aisha = world["aisha"]
    ms = _ms(leader, world["project_id"])
    t = _task(leader, ms, world["a_uid"])
    a = AuthedClient(client, "s1@example.org")
    r = a.post(f"/api/v1/tasks/{t}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t}/review", json={"decision": "accept", "quality": 4})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{world['project_id']}/score").json()
    assert body["participants"], "expected at least one participant"
    positions = [{"position": i + 1, "user_id": p["user_id"]} for i, p in enumerate(body["participants"])]
    r = leader.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 201, r.text
    snap = r.json()
    assert snap["sha256"]
    assert len(snap["positions"]) == len(positions)


def test_snapshots_list_for_members(client, world) -> None:
    leader = world["leader"]
    aisha = world["aisha"]
    ms = _ms(leader, world["project_id"])
    t = _task(leader, ms, world["a_uid"])
    a = AuthedClient(client, "s1@example.org")
    r = a.post(f"/api/v1/tasks/{t}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t}/review", json={"decision": "accept", "quality": 3})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{world['project_id']}/score").json()
    positions = [{"position": i + 1, "user_id": p["user_id"]} for i, p in enumerate(body["participants"])]
    r = leader.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 201, r.text
    snap_id = r.json()["snapshot_id"]
    # Member can list snapshots.
    r = aisha.get(f"/api/v1/projects/{world['project_id']}/author-order/snapshots")
    assert r.status_code == 200, r.text
    listed = r.json()
    assert any(s["id"] == snap_id for s in listed)


def test_export_csv_and_statement(client, world) -> None:
    leader = world["leader"]
    aisha = world["aisha"]
    ms = _ms(leader, world["project_id"])
    t = _task(leader, ms, world["a_uid"])
    a = AuthedClient(client, "s1@example.org")
    r = a.post(f"/api/v1/tasks/{t}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t}/review", json={"decision": "accept", "quality": 4})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{world['project_id']}/score").json()
    positions = [{"position": i + 1, "user_id": p["user_id"]} for i, p in enumerate(body["participants"])]
    r = leader.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 201, r.text
    snap_id = r.json()["snapshot_id"]
    # CSV
    r = leader.get(
        f"/api/v1/projects/{world['project_id']}/author-order/export.csv",
        params={"snapshot_id": snap_id},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    text = r.text
    first = next(line for line in text.splitlines() if line.strip())
    assert first.startswith("position,user_id,note,total_points")
    # Statement
    r = leader.get(
        f"/api/v1/projects/{world['project_id']}/author-order/statement.txt",
        params={"snapshot_id": snap_id},
    )
    assert r.status_code == 200, r.text
    assert "Contribution statement" in r.text


def test_member_cannot_finalize(client, world) -> None:
    leader = world["leader"]
    aisha = world["aisha"]
    r = aisha.post(
        f"/api/v1/projects/{world['project_id']}/author-order/finalize",
        json={"positions": [{"position": 1, "user_id": world["a_uid"]}]},
    )
    assert r.status_code == 403
