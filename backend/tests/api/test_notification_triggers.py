"""Event-driven notifications: task assignment and chat @mentions.

Email delivery is fire-and-forget on a worker thread, so these tests stub the
sender and assert on the in-app Notification rows (the durable part) plus the
arguments handed to the mailer.
"""
from __future__ import annotations

import pytest
from _helpers import AuthedClient, signup


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture outbound notification emails instead of sending them."""
    calls: list[dict] = []

    def _fake(fn, **kwargs):
        calls.append({"fn": fn.__name__, **kwargs})

    monkeypatch.setattr("app.notifications.triggers._run_email", _fake)
    return calls


@pytest.fixture
def world(client):
    """Two-member team with a project, a goal and a milestone."""
    signup(client, "lead@example.org", "Lead")
    lead = AuthedClient(client, "lead@example.org")
    team_id = lead.post("/api/v1/teams", json={"name": "T"}).json()["id"]
    signup(client, "mate@example.org", "Mate")
    mate = AuthedClient(client, "mate@example.org")
    inv = lead.post(
        f"/api/v1/teams/{team_id}/invitations", json={"email": "mate@example.org"}
    ).json()
    mate.post(f"/api/v1/invitations/{inv['token']}/accept")
    lead_uid = lead.get("/api/v1/me").json()["id"]
    mate_uid = mate.get("/api/v1/me").json()["id"]
    proj = lead.post(
        f"/api/v1/teams/{team_id}/projects",
        json={
            "kind": "general",
            "name": "Proj",
            "participant_user_ids": [lead_uid, mate_uid],
        },
    ).json()
    goal = lead.post(
        "/api/v1/goals",
        json={"project_id": proj["id"], "title": "Ship", "target_date": "2026-12-31"},
    ).json()
    ms = lead.post(
        f"/api/v1/goals/{goal['id']}/milestones", json={"title": "M1", "due_date": "2026-06-30"}
    ).json()
    return {
        "lead": lead,
        "mate": mate,
        "raw_client": client,
        "team_id": team_id,
        "project_id": proj["id"],
        "ms_id": ms["id"],
        "lead_uid": lead_uid,
        "mate_uid": mate_uid,
    }


def _task(world, assignee: str, title: str = "Write the draft") -> dict:
    r = world["lead"].post(
        "/api/v1/tasks",
        json={
            "milestone_id": world["ms_id"],
            "assignee_user_id": assignee,
            "title": title,
            "category_code": "writing_original_draft",
            "weight": 3,
            "est_hours": 4,
            "start_date": "2026-01-01",
            "due_date": "2026-03-15",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _notifs(c: AuthedClient) -> list[dict]:
    r = c.get("/api/v1/notifications")
    assert r.status_code == 200, r.text
    return r.json()


def _add_third_member(world) -> str:
    """Add a third participant and return their user id."""
    signup(world["raw_client"], "third@example.org", "Third")
    third = AuthedClient(world["raw_client"], "third@example.org")
    inv = world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/invitations", json={"email": "third@example.org"}
    ).json()
    third.post(f"/api/v1/invitations/{inv['token']}/accept")
    uid = third.get("/api/v1/me").json()["id"]
    r = world["lead"].post(
        f"/api/v1/projects/{world['project_id']}/participants",
        json={"user_ids": [world["lead_uid"], world["mate_uid"], uid]},
    )
    assert r.status_code == 204, r.text
    return uid


# --------------------------------------------------------------------------
# Task assignment
# --------------------------------------------------------------------------


def test_assignment_notifies_assignee_with_deadline(world, sent_emails) -> None:
    task = _task(world, world["mate_uid"])

    rows = _notifs(world["mate"])
    assert len(rows) == 1
    n = rows[0]
    assert n["type"] == "task_assigned"
    assert n["task_id"] == task["id"]
    assert n["project_id"] == world["project_id"]
    assert "Write the draft" in n["title"]
    assert "2026-03-15" in n["body"]
    assert n["read"] is False

    # The leader who assigned it gets nothing.
    assert _notifs(world["lead"]) == []


def test_assignment_sends_email_to_assignee(world, sent_emails) -> None:
    _task(world, world["mate_uid"])
    assert len(sent_emails) == 1
    mail = sent_emails[0]
    assert mail["fn"] == "send_task_assignment_email"
    assert mail["to"] == "mate@example.org"
    assert mail["assignee_name"] == "Mate"
    assert mail["assigner_name"] == "Lead"
    assert mail["task_title"] == "Write the draft"
    assert mail["project_name"] == "Proj"
    assert mail["due_date"] == "2026-03-15"


def test_self_assignment_creates_nothing(world, sent_emails) -> None:
    _task(world, world["lead_uid"])
    assert _notifs(world["lead"]) == []
    assert sent_emails == []


def test_reassignment_notifies_only_the_new_owner(world, sent_emails) -> None:
    task = _task(world, world["mate_uid"])
    before = list(sent_emails)

    # Reassigning to yourself must not ping you.
    r = world["lead"].patch(
        f"/api/v1/tasks/{task['id']}", json={"assignee_user_id": world["lead_uid"]}
    )
    assert r.status_code == 200, r.text
    assert sent_emails == before
    assert len(_notifs(world["mate"])) == 1

    third_uid = _add_third_member(world)
    r = world["lead"].patch(f"/api/v1/tasks/{task['id']}", json={"assignee_user_id": third_uid})
    assert r.status_code == 200, r.text
    assert [m["to"] for m in sent_emails if m["to"] == "third@example.org"]




# --------------------------------------------------------------------------
# Chat @mentions
# --------------------------------------------------------------------------


def test_mention_notifies_the_named_member(world, sent_emails) -> None:
    r = world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/messages",
        json={"body": "Hey @Mate can you take a look at the figures?"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["mentions"] == [world["mate_uid"]]

    rows = _notifs(world["mate"])
    assert len(rows) == 1
    assert rows[0]["type"] == "mention"
    assert "mentioned you" in rows[0]["title"]
    assert "Lead" in rows[0]["title"]
    assert "figures" in rows[0]["body"]
    assert rows[0]["team_id"] == world["team_id"]

    assert len(sent_emails) == 1
    assert sent_emails[0]["fn"] == "send_mention_email"
    assert sent_emails[0]["to"] == "mate@example.org"
    assert sent_emails[0]["sender_name"] == "Lead"
    assert sent_emails[0]["team_name"] == "T"


def test_mention_is_case_insensitive_and_deduped(world, sent_emails) -> None:
    world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/messages",
        json={"body": "@mate and @MATE please review"},
    )
    rows = _notifs(world["mate"])
    assert len(rows) == 1
    assert [m["to"] for m in sent_emails] == ["mate@example.org"]


def test_message_without_mention_notifies_nobody(world, sent_emails) -> None:
    world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/messages", json={"body": "shipping today"}
    )
    assert _notifs(world["mate"]) == []
    assert sent_emails == []


def test_mention_unknown_name_is_ignored(world, sent_emails) -> None:
    world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/messages", json={"body": "@Nobody here?"}
    )
    assert _notifs(world["mate"]) == []
    assert sent_emails == []


def test_self_mention_is_not_delivered(world, sent_emails) -> None:
    world["lead"].post(
        f"/api/v1/teams/{world['team_id']}/messages", json={"body": "note to self @Lead"}
    )
    assert _notifs(world["lead"]) == []
    assert sent_emails == []


def test_activity_feed_reports_task_assignment(world, sent_emails) -> None:
    task = _task(world, world["mate_uid"], title="Draft the abstract")
    feed = world["lead"].get("/api/v1/activity").json()["items"]
    row = next(i for i in feed if i.get("task_id") == task["id"])
    assert row["kind"] == "task_assigned"
    # The audit helper resolves the subject title, so the feed is readable.
    assert "Draft the abstract" in row["body"]
    assert row["actor_user_id"] == world["lead_uid"]
    assert row["self"] is True

def test_unread_count_tracks_assignment(world, sent_emails) -> None:
    assert world["mate"].get("/api/v1/notifications/unread-count").json()["unread"] == 0
    _task(world, world["mate_uid"])
    assert world["mate"].get("/api/v1/notifications/unread-count").json()["unread"] == 1
    world["mate"].post("/api/v1/notifications/read-all")
    assert world["mate"].get("/api/v1/notifications/unread-count").json()["unread"] == 0
