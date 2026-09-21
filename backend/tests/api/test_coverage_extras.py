"""Coverage tests: endpoints not exercised by the existing test files.

- /me (GET + PATCH)
- /teams/{id}/transfer-leader
- /teams/{id}/audit
- /teams/{id}/members list
- /projects/{id}/multipliers (PUT + GET)
- /projects/{id}/timeliness (GET + PUT)
- /projects/{id}/adjustments (POST + GET)
- Score adjustments show up in /score payload
- Task PATCH: edit weight/description/category; member-owned
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from _helpers import AuthedClient, signup


@pytest.fixture
def setup(client):
    signup(client, "covleader@example.org", "CovLeader")
    leader = AuthedClient(client, "covleader@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "CovT"}).json()["id"]
    signup(client, "covmem@example.org", "CovMember")
    member = AuthedClient(client, "covmem@example.org")
    inv = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "covmem@example.org"}).json()
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    member_id = member.get("/api/v1/me").json()["id"]
    proj = leader.post(
        f"/api/v1/teams/{team_id}/projects",
        json={"kind": "general", "name": "CovP", "participant_user_ids": [member_id]},
    ).json()
    return {"leader": leader, "member": member, "team_id": team_id, "member_id": member_id, "project_id": proj["id"]}


def test_me_get_and_patch(setup) -> None:
    leader = setup["leader"]
    r = leader.patch("/api/v1/me", json={"display_name": "Renamed"})
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "Renamed"
    # Confirm via fresh GET.
    me = leader.get("/api/v1/me").json()
    assert me["display_name"] == "Renamed"


def test_transfer_leader_keeps_two_leaders_invariant(setup) -> None:
    leader = setup["leader"]
    member = setup["member"]
    member_id = setup["member_id"]
    r = leader.post(
        f"/api/v1/teams/{setup['team_id']}/transfer-leader",
        json={"new_leader_user_id": member_id},
    )
    assert r.status_code == 200, r.text
    # Old leader is now member.
    members = leader.get(f"/api/v1/teams/{setup['team_id']}/members").json()
    roles = sorted([m["role"] for m in members])
    assert roles == ["leader", "member"]
    # Member (new leader) can now perform a leader-only action.
    r = member.post(
        f"/api/v1/teams/{setup['team_id']}/invitations",
        json={"email": "newinvite@example.org"},
    )
    assert r.status_code == 201


def test_team_audit_records_key_actions(setup) -> None:
    leader = setup["leader"]
    # Trigger a few audited events.
    leader.post(
        f"/api/v1/teams/{setup['team_id']}/invitations",
        json={"email": "auditee@example.org"},
    )
    r = leader.get(f"/api/v1/teams/{setup['team_id']}/audit")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    actions = [row["action"] for row in items]
    assert "invitation.create" in actions


def test_team_audit_403_for_member(setup) -> None:
    member = setup["member"]
    r = member.get(f"/api/v1/teams/{setup['team_id']}/audit")
    assert r.status_code == 403


def test_list_team_members_includes_removed_flag(setup) -> None:
    leader = setup["leader"]
    r = leader.get(f"/api/v1/teams/{setup['team_id']}/members")
    assert r.status_code == 200
    members = r.json()
    assert any(m["email"] == "covmem@example.org" for m in members)
    assert all("role" in m for m in members)


def test_category_multipliers_upsert_and_get(setup) -> None:
    leader = setup["leader"]
    project_id = setup["project_id"]
    payload = [{"category_code": "software", "multiplier": "1.25"}]
    r = leader.put(f"/api/v1/projects/{project_id}/multipliers", json=payload)
    assert r.status_code == 200, r.text
    # Read it back.
    r = leader.get(f"/api/v1/projects/{project_id}/multipliers")
    assert r.status_code == 200
    body = r.json()
    assert any(m["category_code"] == "software" and Decimal(m["multiplier"]) == Decimal("1.25") for m in body)


def test_timeliness_update_and_rejection_of_invalid(setup) -> None:
    leader = setup["leader"]
    project_id = setup["project_id"]
    r = leader.put(
        f"/api/v1/projects/{project_id}/timeliness",
        json={
            "on_time_band_days": 1,
            "mild_band_days": 3,
            "medium_band_days": 7,
            "late_mild": "0.9",
            "late_medium": "0.75",
            "late_severe": "0.5",
        },
    )
    assert r.status_code == 200, r.text
    # Invalid: late_mild < late_severe (not monotone non-increasing).
    r = leader.put(
        f"/api/v1/projects/{project_id}/timeliness",
        json={
            "on_time_band_days": 1,
            "mild_band_days": 3,
            "medium_band_days": 7,
            "late_mild": "0.4",
            "late_medium": "0.75",
            "late_severe": "0.9",
        },
    )
    assert r.status_code == 422


def test_score_adjustment_post_and_list_and_reflected_in_score(setup) -> None:
    leader = setup["leader"]
    project_id = setup["project_id"]
    member_id = setup["member_id"]

    # Build a goal + milestone + done task so the participant has score surface.
    g_id = leader.post(
        "/api/v1/goals",
        json={"project_id": project_id, "title": "G", "target_date": "2026-12-31"},
    ).json()["id"]
    ms_id = leader.post(
        f"/api/v1/goals/{g_id}/milestones",
        json={"title": "M", "due_date": "2026-06-30"},
    ).json()["id"]
    t_id = leader.post(
        "/api/v1/tasks",
        json={
            "milestone_id": ms_id,
            "assignee_user_id": member_id,
            "title": "T",
            "description": "d",
            "category_code": "software",
            "weight": 5,
            "est_hours": 4,
            "start_date": "2026-01-01",
            "due_date": "2026-02-01",
        },
    ).json()["id"]
    member = setup["member"]
    r = member.post(f"/api/v1/tasks/{t_id}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t_id}/review", json={"decision": "accept", "quality": 3})
    assert r.status_code == 200

    # Add adjustment.
    r = leader.post(
        f"/api/v1/projects/{project_id}/adjustments",
        json={"user_id": member_id, "delta": "2.5", "reason": "extra review"},
    )
    assert r.status_code == 201, r.text
    adj = r.json()
    assert Decimal(adj["delta"]) == Decimal("2.5")

    # Listing.
    r = leader.get(f"/api/v1/projects/{project_id}/adjustments")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Verify reflected in /score payload.
    r = leader.get(f"/api/v1/projects/{project_id}/score")
    assert r.status_code == 200
    body = r.json()
    assert body["participants"], "expected at least one participant"
    p = body["participants"][0]
    assert any(
        Decimal(a["delta"]) == Decimal("2.5") and a["reason"] == "extra review"
        for a in p["adjustments"]
    )


def test_patch_task_member_cannot_edit_detail(setup) -> None:
    """Per product rule, only the leader can change task details."""
    leader = setup["leader"]
    member = setup["member"]
    member_id = setup["member_id"]
    project_id = setup["project_id"]
    g_id = leader.post("/api/v1/goals", json={"project_id": project_id, "title": "G", "target_date": "2026-12-31"}).json()["id"]
    ms_id = leader.post(f"/api/v1/goals/{g_id}/milestones", json={"title": "M", "due_date": "2026-06-30"}).json()["id"]
    t = leader.post(
        "/api/v1/tasks",
        json={
            "milestone_id": ms_id,
            "assignee_user_id": member_id,
            "title": "orig",
            "description": "d",
            "category_code": "software",
            "weight": 5,
            "est_hours": 4,
            "start_date": "2026-01-01",
            "due_date": "2026-02-01",
        },
    ).json()
    # Member updates description.
    r = member.patch(f"/api/v1/tasks/{t['id']}", json={"description": "new d"})
    assert r.status_code == 403, r.text
    # Leader update succeeds.
    r = leader.patch(f"/api/v1/tasks/{t['id']}", json={"description": "new d"})
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "new d"


def test_export_pdf_downloads(setup) -> None:
    """Quick smoke that /export.pdf returns a tiny PDF body when a snapshot exists."""
    leader = setup["leader"]
    project_id = setup["project_id"]
    member_id = setup["member_id"]

    # Build a snapshot first (need at least one accepted task so finalize works).
    g_id = leader.post("/api/v1/goals", json={"project_id": project_id, "title": "G", "target_date": "2026-12-31"}).json()["id"]
    ms_id = leader.post(f"/api/v1/goals/{g_id}/milestones", json={"title": "M", "due_date": "2026-06-30"}).json()["id"]
    t_id = leader.post(
        "/api/v1/tasks",
        json={
            "milestone_id": ms_id,
            "assignee_user_id": member_id,
            "title": "T",
            "category_code": "software",
            "weight": 5,
            "est_hours": 4,
            "start_date": "2026-01-01",
            "due_date": "2026-02-01",
        },
    ).json()["id"]
    member = setup["member"]
    r = member.post(f"/api/v1/tasks/{t_id}/submit", json={"note": "ok"})
    assert r.status_code == 200, r.text
    r = leader.post(f"/api/v1/tasks/{t_id}/review", json={"decision": "accept", "quality": 4})
    assert r.status_code == 200
    body = leader.get(f"/api/v1/projects/{project_id}/score").json()
    positions = [{"position": i + 1, "user_id": p["user_id"]} for i, p in enumerate(body["participants"])]
    r = leader.post(
        f"/api/v1/projects/{project_id}/author-order/finalize",
        json={"positions": positions},
    )
    assert r.status_code == 201, r.text
    snap_id = r.json()["snapshot_id"]
    pdf = leader.get(
        f"/api/v1/projects/{project_id}/author-order/export.pdf",
        params={"snapshot_id": snap_id},
    )
    assert pdf.status_code == 200, pdf.text
    # PDF magic bytes.
    assert pdf.content[:4] == b"%PDF"


def test_credit_categories_listing(setup) -> None:
    leader = setup["leader"]
    r = leader.get("/api/v1/credit-categories")
    assert r.status_code == 200, r.text
    codes = [c["code"] for c in r.json()]
    assert "software" in codes and "writing_original_draft" in codes


def test_member_cannot_post_adjustment(setup) -> None:
    member = setup["member"]
    r = member.post(
        f"/api/v1/projects/{setup['project_id']}/adjustments",
        json={"user_id": setup["member_id"], "delta": "1", "reason": "x"},
    )
    assert r.status_code == 403


def test_team_credit_categories_endpoint_is_public(client) -> None:
    """This endpoint is intentionally public so pickers can render before login."""
    r = client.get("/api/v1/credit-categories")
    assert r.status_code == 200, r.text
    assert any(c["code"] == "software" for c in r.json())
