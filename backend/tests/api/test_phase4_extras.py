"""Phase 4 smoke tests: files, notifications, schedules, chat REST."""
from __future__ import annotations

import io
import zipfile

import pytest

from _helpers import AuthedClient, signup


@pytest.fixture
def world(client):
    signup(client, "flead@example.org", "Leader")
    leader = AuthedClient(client, "flead@example.org")
    team_id = leader.post("/api/v1/teams", json={"name": "FT"}).json()["id"]
    signup(client, "fmem@example.org", "Member")
    member = AuthedClient(client, "fmem@example.org")
    inv = leader.post(f"/api/v1/teams/{team_id}/invitations", json={"email": "fmem@example.org"}).json()
    member.post(f"/api/v1/invitations/{inv['token']}/accept")
    return {"leader": leader, "member": member, "team_id": team_id}


def test_files_upload_list_download(client, world) -> None:
    leader = world["leader"]
    team_id = world["team_id"]
    # Upload text content (multipart)
    files = {"file": ("hello.txt", io.BytesIO(b"hello world"), "text/plain")}
    r = leader.post(f"/api/v1/teams/{team_id}/files", files=files)
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["current_version_no"] == 1
    # List
    r = leader.get(f"/api/v1/teams/{team_id}/files")
    assert r.status_code == 200, r.text
    assert any(x["id"] == f["id"] for x in r.json())
    # Versions
    r = leader.get(f"/api/v1/teams/{team_id}/files/{f['id']}/versions")
    assert r.status_code == 200, r.text
    assert len(r.json()) == 1
    # Download
    r = leader.get(f"/api/v1/teams/{team_id}/files/{f['id']}/download")
    assert r.status_code == 200, r.text
    assert r.content == b"hello world"


def test_files_zip_safety_check(client, world) -> None:
    leader = world["leader"]
    team_id = world["team_id"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", b"alpha")
        z.writestr("../escaped.txt", b"escape")
    files = {"file": ("bundle.zip", io.BytesIO(buf.getvalue()), "application/zip")}
    r = leader.post(f"/api/v1/teams/{team_id}/files/check-archive", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["safe"] is False or any("escaped" in m for m in body.get("bad_members", []))


def test_notifications_list_and_mark_all_read(client, world) -> None:
    leader = world["leader"]
    # Empty initially
    r = leader.get("/api/v1/notifications")
    assert r.status_code == 200, r.text
    assert r.json() == []
    # unread-count starts at 0
    r = leader.get("/api/v1/notifications/unread-count")
    assert r.status_code == 200, r.text
    assert r.json()["unread"] == 0
    # Mark all read is safe on empty
    r = leader.post("/api/v1/notifications/read-all")
    assert r.status_code == 204, r.text


def test_schedules_upsert_get_calendar_timeline(client, world) -> None:
    leader = world["leader"]
    member = world["member"]
    team_id = world["team_id"]
    m_id = member.get("/api/v1/me").json()["id"]
    payload = {
        "user_id": m_id,
        "weekly_cap_hours": 30,
        "slots": [
            {"weekday": 0, "start_minute": 9 * 60, "end_minute": 12 * 60},
            {"weekday": 1, "start_minute": 14 * 60, "end_minute": 17 * 60},
        ],
    }
    r = leader.put(f"/api/v1/teams/{team_id}/schedules", json=payload)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["weekly_cap_hours"] == 30
    assert len(plan["slots"]) == 2

    # Member reads own plan
    r = member.get(f"/api/v1/teams/{team_id}/schedules/{m_id}")
    assert r.status_code == 200, r.text
    assert r.json()["weekly_cap_hours"] == 30

    # Calendar (week range)
    r = leader.get(
        f"/api/v1/teams/{team_id}/calendar",
        params={"start": "2026-01-05", "end": "2026-01-11", "user_id": m_id},
    )
    assert r.status_code == 200, r.text

    # Timeline
    r = leader.get(
        f"/api/v1/teams/{team_id}/timeline",
        params={"start": "2026-01-01", "end": "2026-01-31", "user_id": m_id},
    )
    assert r.status_code == 200, r.text

    # Overload check
    r = leader.get(
        f"/api/v1/teams/{team_id}/overload",
        params={"week_start": "2026-01-05"},
    )
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_member_cannot_set_plan(client, world) -> None:
    member = world["member"]
    leader = world["leader"]
    team_id = world["team_id"]
    m_id = member.get("/api/v1/me").json()["id"]
    r = member.put(
        f"/api/v1/teams/{team_id}/schedules",
        json={"user_id": m_id, "weekly_cap_hours": 10, "slots": []},
    )
    assert r.status_code == 403, r.text


def test_chat_send_list_edit_delete(client, world) -> None:
    leader = world["leader"]
    team_id = world["team_id"]
    body = "Hello @everyone"
    r = leader.post(f"/api/v1/teams/{team_id}/messages", json={"body": body})
    assert r.status_code == 201, r.text
    m = r.json()
    assert m["body"] == body
    # List
    r = leader.get(f"/api/v1/teams/{team_id}/messages")
    assert r.status_code == 200, r.text
    assert any(x["id"] == m["id"] for x in r.json())
    # Edit
    r = leader.patch(
        f"/api/v1/teams/{team_id}/messages/{m['id']}", json={"body": "Edited"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "Edited"
    # Mark read
    r = leader.post(f"/api/v1/teams/{team_id}/read", params={"seq": m["seq"]})
    assert r.status_code == 200, r.text
    # Delete
    r = leader.delete(f"/api/v1/teams/{team_id}/messages/{m['id']}")
    assert r.status_code == 204, r.text
    # Verify deleted flag
    r = leader.get(f"/api/v1/teams/{team_id}/messages")
    msgs = r.json()
    assert any(x["id"] == m["id"] and x["deleted"] for x in msgs)
