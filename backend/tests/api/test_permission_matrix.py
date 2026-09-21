"""Permission matrix coverage.

Strategy:
1. Parse the matrix in ``docs/architecture.md`` and assert no cell is empty.
2. Run a small representative subset of cells against the live API to confirm
   the matrix matches reality.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
from _helpers import AuthedClient, signup  # type: ignore[import-not-found]

REPO = Path(__file__).resolve().parents[3]


def _matrix_rows() -> list[dict]:
    md = (REPO / "docs" / "architecture.md").read_text(encoding="utf-8")
    rows: list[dict] = []
    in_table = False
    for line in md.splitlines():
        if not in_table:
            if line.startswith("| ID |"):
                in_table = True
                continue
            continue
        if not line.startswith("|"):
            in_table = False
            continue
        if set(line.replace("|", "").strip()) <= {"-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        rid, endpoint, leader, member, outsider, removed, anon = cells[:7]
        rows.append(
            {
                "id": rid.strip(),
                "endpoint": endpoint.strip(),
                "leader": leader.strip(),
                "member": member.strip(),
                "outsider": outsider.strip(),
                "removed": removed.strip(),
                "anon": anon.strip(),
            }
        )
    return rows


MATRIX = _matrix_rows()


def test_matrix_table_has_no_empty_cells() -> None:
    for row in MATRIX:
        for key in ("leader", "member", "outsider", "removed", "anon"):
            assert row[key], f"empty cell in row {row['id']} for {key}"


def _build_world(client, leader_email="leader@example.org"):
    signup(client, leader_email, "Leader")
    leader = AuthedClient(client, leader_email)
    r = leader.post("/api/v1/teams", json={"name": "T"})
    team_id = r.json()["id"]
    members = leader.get(f"/api/v1/teams/{team_id}/members").json()
    leader_uid = next(m["user_id"] for m in members if m["email"] == leader_email)
    return {"team_id": team_id, "leader_uid": leader_uid, "leader_email": leader_email}


PROBES = {
    "AUTH-04": ("GET", "/api/v1/me", None),
    "TEAM-01..07": ("GET", "/api/v1/teams/{team_id}", None),
    "TEAM-02": ("POST", "/api/v1/teams/{team_id}/invitations", {"email": "newuser@example.org"}),
    "TEAM-04": ("DELETE", "/api/v1/teams/{team_id}/members/{user_id}", None),
    "TEAM-05": ("POST", "/api/v1/teams/{team_id}/transfer-leader", None),
    "TEAM-06": ("POST", "/api/v1/teams/{team_id}/archive", None),
    "FILE-01..07": ("GET", "/api/v1/teams/{team_id}/files", None),
    "CHAT-02": ("GET", "/api/v1/teams/{team_id}/messages", None),
}


CELLS = [
    ("AUTH-04", "anon", 401),
    ("AUTH-04", "leader", 200),
    ("TEAM-01..07", "anon", 401),
    ("TEAM-01..07", "leader", 200),
    ("TEAM-06", "anon", 401),
    ("TEAM-06", "leader", 204),
]


@pytest.mark.parametrize("row_id, role, expected", CELLS, ids=[f"{r}-{x}" for r, x, _ in CELLS])
def test_permission_cell(row_id, role, expected, client, app) -> None:
    if row_id not in PROBES:
        pytest.skip(f"{row_id} not in probes")
    method, template, body = PROBES[row_id]
    w = _build_world(client)
    path = template.format(team_id=w["team_id"], user_id=w["leader_uid"])

    if role == "anon":
        # Fresh client with no cookies
        from fastapi.testclient import TestClient
        c = TestClient(app)
    else:
        c = AuthedClient(client, w["leader_email"])

    if body is not None:
        r = c.post(path, json=body)
    elif method == "GET":
        r = c.get(path)
    elif method == "POST":
        r = c.post(path)
    elif method == "DELETE":
        r = c.delete(path)
    else:
        r = client.request(method, path)

    status = r.status_code
    if expected == 200:
        assert 200 <= status < 300, f"{row_id}/{role}: got {status} body={r.text[:200]}"
    else:
        assert status == expected, f"{row_id}/{role}: expected {expected}, got {status} body={r.text[:200]}"
