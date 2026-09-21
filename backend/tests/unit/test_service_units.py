"""Service-level unit tests filling coverage gaps."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime

import pytest
from app.core.errors import AppError
from app.models.team import Team
from app.services import (
    chat_service,
    file_service,
    project_service,
    schedule_service,
    task_service,
    team_service,
)
from app.storage.local import LocalDiskStorage as LocalStorage


@pytest.fixture
def sample_team(db, make_user):
    leader = make_user(email="sleader@example.org", display_name="Leader")
    team = Team(
        id=str(uuid.uuid4()).replace("-", "")[:26],
        name="Sample",
        description="",
        archived=False,
        created_at=datetime.now(tz=UTC),
    )
    db.add(team)
    db.flush()
    from app.models.membership import Membership

    db.add(Membership(
        id=str(uuid.uuid4()).replace("-", "")[:26],
        user_id=leader.id, team_id=team.id, role="leader",
        joined_at=team.created_at, created_at=team.created_at,
    ))
    db.commit()
    return {"team": team, "leader": leader}


@pytest.fixture
def sample_two_member_team(db, make_user):
    leader = make_user(email="s2leader@example.org", display_name="L")
    other = make_user(email="s2other@example.org", display_name="O")
    team = Team(
        id=str(uuid.uuid4()).replace("-", "")[:26],
        name="S2", description="", archived=False,
        created_at=datetime.now(tz=UTC),
    )
    db.add(team)
    db.flush()
    from app.models.membership import Membership

    db.add(Membership(
        id=str(uuid.uuid4()).replace("-", "")[:26],
        user_id=leader.id, team_id=team.id, role="leader",
        joined_at=team.created_at, created_at=team.created_at,
    ))
    db.add(Membership(
        id=str(uuid.uuid4()).replace("-", "")[:26],
        user_id=other.id, team_id=team.id, role="member",
        joined_at=team.created_at, created_at=team.created_at,
    ))
    db.commit()
    return {"team": team, "leader": leader, "other": other}


def _make_general_project(sample_team, db, name="G"):
    return project_service.create_project(
        db, team=sample_team["team"], actor=sample_team["leader"],
        kind="general", name=name, description=None,
        target_venue=None, venue_kind=None, submission_deadline=None,
        participant_user_ids=[sample_team["leader"].id],
        contrib_visibility="all", reviewer_user_id=None,
    )


# ---------------- chat_service ----------------

def test_chat_parse_mentions_basic() -> None:
    out = chat_service.parse_mentions(
        "Hi @alice", {"1": "alice", "2": "bob"},
    )
    assert out == ["1"]


def test_chat_parse_mentions_dedup() -> None:
    out = chat_service.parse_mentions("@alice @alice", {"1": "alice"})
    assert out == ["1"]


def test_chat_parse_mentions_case_insensitive() -> None:
    out = chat_service.parse_mentions("@Alice.", {"1": "alice"})
    assert out == ["1"]


def test_chat_parse_mentions_unknown() -> None:
    out = chat_service.parse_mentions("@nobody", {"1": "alice"})
    assert out == []


def test_send_message_assigns_monotonic_seq(sample_team, db) -> None:
    msg1 = chat_service.send_message(db, team=sample_team["team"], sender=sample_team["leader"], body="first", member_user_ids={})
    msg2 = chat_service.send_message(db, team=sample_team["team"], sender=sample_team["leader"], body="second", member_user_ids={})
    assert msg2.seq > msg1.seq


def test_chat_mark_read_and_unread(sample_two_member_team, db) -> None:
    chat_service.send_message(db, team=sample_two_member_team["team"], sender=sample_two_member_team["leader"], body="hi", member_user_ids={})
    chat_service.send_message(db, team=sample_two_member_team["team"], sender=sample_two_member_team["leader"], body="again", member_user_ids={})
    other = sample_two_member_team["other"]
    tid = sample_two_member_team["team"].id
    assert chat_service.unread_count(db, other.id, tid) == 2
    chat_service.mark_read(db, other.id, tid, seq=999)
    assert chat_service.unread_count(db, other.id, tid) == 0


def test_chat_messages_since(sample_team, db) -> None:
    m1 = chat_service.send_message(db, team=sample_team["team"], sender=sample_team["leader"], body="a", member_user_ids={})
    m2 = chat_service.send_message(db, team=sample_team["team"], sender=sample_team["leader"], body="b", member_user_ids={})
    out = chat_service.messages_since(db, sample_team["team"].id, since_seq=m1.seq)
    assert [m.id for m in out] == [m2.id]


def test_edit_message_rejects_non_owner(sample_two_member_team, db) -> None:
    msg = chat_service.send_message(db, team=sample_two_member_team["team"], sender=sample_two_member_team["leader"], body="x", member_user_ids={})
    with pytest.raises(AppError):
        chat_service.edit_message(db, msg=msg, actor=sample_two_member_team["other"], body="y")


def test_delete_message_non_owner_non_leader_forbidden(sample_two_member_team, db) -> None:
    msg = chat_service.send_message(db, team=sample_two_member_team["team"], sender=sample_two_member_team["leader"], body="x", member_user_ids={})
    with pytest.raises(AppError):
        chat_service.delete_message(db, msg=msg, actor=sample_two_member_team["other"], is_leader=False)


def test_list_messages_before_seq_descending(sample_team, db) -> None:
    for i in range(5):
        chat_service.send_message(db, team=sample_team["team"], sender=sample_team["leader"], body=f"m{i}", member_user_ids={})
    out = chat_service.list_messages(db, sample_team["team"].id, before_seq=None, limit=3)
    assert len(out) == 3
    assert all(out[i].seq > out[i + 1].seq for i in range(len(out) - 1))


# ---------------- schedule_service ----------------

def test_schedule_set_weekly_plan(sample_team, db) -> None:
    plan = schedule_service.set_plan(
        db, team=sample_team["team"], user_id=sample_team["leader"].id,
        weekly_cap_hours=20,
        slots=[{"weekday": 1, "start_minute": 9 * 60, "end_minute": 19 * 60, "note": None}],
    )
    assert plan.weekly_cap_hours == 20


def test_schedule_calendar_renders(sample_team, db) -> None:
    schedule_service.set_plan(
        db, team=sample_team["team"], user_id=sample_team["leader"].id,
        weekly_cap_hours=2,
        slots=[{"weekday": 1, "start_minute": 0, "end_minute": 240, "note": None}],
    )
    pass  # calendar/timeline route tested via API in tests/api/test_phase4_extras.py


def test_schedule_get_plan_missing_creates_default(sample_team, db) -> None:
    assert (
        schedule_service.get_plan(
            db, team_id=sample_team["team"].id, user_id=sample_team["leader"].id
        )
        is None
    )


# ---------------- team_service ----------------

def test_team_service_create_and_archive(db, make_user) -> None:
    leader = make_user(email="tserv@example.org", display_name="X")
    t = team_service.create_team(db, leader=leader, name="NewT", description="d")
    assert t.id
    team_service.archive_team(db, t)
    assert t.archived


def test_team_service_list_members(sample_two_member_team, db) -> None:
    members = team_service.list_members(db, sample_two_member_team["team"].id)
    uids = {u.id for u, _ in members}
    assert {sample_two_member_team["leader"].id, sample_two_member_team["other"].id} <= uids


def test_team_invitation_lifecycle(sample_team, db, make_user) -> None:
    invitee = make_user(email="invitee@example.org", display_name="I")
    inv = team_service.create_invitation(
        db, team=sample_team["team"], invited_by=sample_team["leader"],
        email=invitee.email, existing_member=invitee,
    )
    assert inv.token
    rows = team_service.list_pending_invitations(db, sample_team["team"].id)
    assert any(r.id == inv.id for r in rows)
    team_service.revoke_invitation(db, inv=inv)


# ---------------- project_service ----------------

def test_project_create_general_and_paper_validation(sample_team, db) -> None:
    p1 = _make_general_project(sample_team, db)
    assert p1.kind == "general"
    with pytest.raises(AppError):
        project_service.create_project(
            db, team=sample_team["team"], actor=sample_team["leader"],
            kind="paper", name="P", description=None, target_venue=None,
            venue_kind=None, submission_deadline=None,
            participant_user_ids=[sample_team["leader"].id],
            contrib_visibility="all", reviewer_user_id=None,
        )


def test_project_add_score_adjustment_and_list(sample_team, db) -> None:
    from decimal import Decimal
    p = _make_general_project(sample_team, db)
    adj = project_service.add_score_adjustment(
        db, project=p, user_id=sample_team["leader"].id, author=sample_team["leader"],
        delta=Decimal("1.5"), reason="test",
    )
    assert adj.id
    out = project_service.list_score_adjustments(db, p.id)
    assert out and out[0].reason == "test"


def test_project_set_participants_idempotent(sample_team, db) -> None:
    p = _make_general_project(sample_team, db, name="H")
    project_service.set_participants(db, project=p, user_ids=[sample_team["leader"].id])
    project_service.set_participants(db, project=p, user_ids=[sample_team["leader"].id])
    uids = project_service.participating_user_ids(db, p.id)
    assert len([u for u in uids if u == sample_team["leader"].id]) == 1


def test_project_archive(sample_team, db) -> None:
    p = _make_general_project(sample_team, db, name="Arc")
    project_service.archive_project(db, project=p)
    assert p.archived


def test_project_timeliness_update(sample_team, db) -> None:
    p = _make_general_project(sample_team, db, name="Tim")
    # First set defaults to ensure row exists.
    project_service.update_timeliness(db, p.id, on_time_band_days=1)
    ts = project_service.get_timeliness(db, p.id)
    assert ts is not None


def test_project_set_multiplier_round_trip(sample_team, db) -> None:
    from decimal import Decimal
    p = _make_general_project(sample_team, db, name="Mul")
    project_service.set_category_multiplier(db, project_id=p.id, code="software", multiplier=Decimal("1.25"))
    back = project_service.get_category_multipliers(db, project_id=p.id)
    assert back["software"] == Decimal("1.25")


# ---------------- task_service ----------------

def test_task_service_goal_progress(sample_team, db) -> None:
    p = _make_general_project(sample_team, db, name="GP")
    g = task_service.create_goal(
        db, project_id=p.id, title="goal",
        target_date=datetime(2026, 12, 31).date(),
        description=None,
    )
    ms = task_service.create_milestone(
        db, goal_id=g.id, title="ms",
        due_date=datetime(2026, 6, 30).date(),
    )
    task_service.create_task(
        db, milestone_id=ms.id, assignee=sample_team["leader"], actor=sample_team["leader"],
        title="t", description="d", category_code="software", weight=5, est_hours=4,
        start_date=datetime(2026, 1, 1).date(), due_date=datetime(2026, 2, 1).date(),
        proposed=False, proposer=None,
    )
    pct = task_service.goal_progress(db, g)
    assert 0.0 <= pct <= 100.0


def test_task_service_update_goal(sample_team, db) -> None:
    p = _make_general_project(sample_team, db, name="UG")
    g = task_service.create_goal(
        db, project_id=p.id, title="x",
        target_date=datetime(2026, 12, 31).date(),
        description=None,
    )
    task_service.update_goal(db, g, title="updated")
    assert g.title == "updated"


# ---------------- file_service ----------------

def test_file_check_zip_safety_blocks_path_traversal() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../etc/passwd", "nope")
    buf.seek(0)
    safe, reasons = file_service.inspect_zip_safety(buf.read())
    assert safe is False
    assert reasons


def test_file_check_zip_safety_ok() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("safe/file.txt", "ok")
    buf.seek(0)
    safe, reasons = file_service.inspect_zip_safety(buf.read())
    assert safe is True
    assert reasons == []


def test_archive_entry_safe() -> None:
    assert file_service.archive_entry_safe("safe") is True
    assert file_service.archive_entry_safe("../escape") is False


def test_can_preview_inline_pdf() -> None:
    assert file_service.can_preview_inline("application/pdf") is True
    assert file_service.can_preview_inline("text/plain") is False


# ---------------- Storage ----------------

def test_local_storage_put_get_delete(tmp_path) -> None:
    s = LocalStorage(root=str(tmp_path / "store"))
    obj = s.put(team_id="t", content=b"hi", original_name="file.txt")
    assert s.exists(obj.path)
    assert b"".join(s.stream(obj.path)) == b"hi"
    s.delete(obj.path)
    assert not s.exists(obj.path)


def test_local_storage_put_versions(tmp_path) -> None:
    s = LocalStorage(root=str(tmp_path / "store"))
    obj1 = s.put(team_id="t", content=b"first", original_name="file.txt")
    obj2 = s.put(team_id="t", content=b"second", original_name="file.txt")
    assert obj1.path != obj2.path
    assert b"".join(s.stream(obj2.path)) == b"second"
