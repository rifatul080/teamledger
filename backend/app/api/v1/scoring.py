"""Author order finalization + exports."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found, validation
from ...core.ids import new_id
from ...models.author_order import AuthorOrderPosition, AuthorOrderSnapshot
from ...models.project import Project
from ...models.user import User
from ...schemas.scoring import FinalizeOrderRequest
from ...services import task_service

router = APIRouter(tags=["scoring"])


@router.post("/projects/{project_id}/author-order/finalize", status_code=201)
def finalize(
    project_id: str,
    payload: FinalizeOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    if proj.finalized_at is not None:
        raise validation("Order already finalized.", code="author.order_finalized")
    inputs = task_service.build_score_inputs(db, project_id)
    # Override the suggested order with the leader's picks.
    from ...scoring.engine import (
        FinalPosition,
        compute_project_score,
    )
    from ...scoring.engine import (
        ProjectInputs as PI,
    )

    # Re-bind with finalized positions.
    pi = PI(
        project_id=inputs.project_id,
        settings=inputs.settings,
        categories=inputs.categories,
        participants=inputs.participants,
        tasks=inputs.tasks,
        adjustments=inputs.adjustments,
        final_order=[FinalPosition(position=p.position, user_id=p.user_id, note=p.note) for p in payload.positions],
    )
    result = compute_project_score(pi)
    if result.final_order is None:
        raise validation("Final order empty.", code="author.order_empty")
    # Serialize snapshot
    snapshot_payload = json.dumps(
        {
            "project_id": proj.id,
            "formula_version": result.formula_version,
            "settings": {
                "on_time_band_days": inputs.settings.on_time_band_days,
                "mild_band_days": inputs.settings.mild_band_days,
                "medium_band_days": inputs.settings.medium_band_days,
                "late_mild": str(inputs.settings.late_mild),
                "late_medium": str(inputs.settings.late_medium),
                "late_severe": str(inputs.settings.late_severe),
            },
            "participants": [
                {
                    "user_id": p.user_id,
                    "display_name": p.display_name,
                    "total_points": str(p.total_points),
                    "by_category": {k: str(v) for k, v in p.by_category.items()},
                    "tasks": [
                        {
                            "task_id": t.task_id,
                            "weight": t.weight,
                            "quality": t.quality,
                            "days_late": t.days_late,
                            "timeliness": str(t.timeliness),
                            "category_multiplier": str(t.category_multiplier),
                            "points": str(t.points),
                        }
                        for t in p.tasks
                    ],
                    "adjustments": [
                        {"delta": str(a.delta), "reason": a.reason, "author_user_id": a.author_user_id}
                        for a in p.adjustments
                    ],
                }
                for p in result.participants
            ],
            "order": [
                {"position": o.position, "user_id": o.user_id, "suggested": o.suggested, "note": o.note}
                for o in result.final_order
            ],
            "tie_breaker": "display_name_ci_asc,user_id",
        },
        sort_keys=True,
        indent=2,
    )
    sha = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()
    now = datetime.now(tz=UTC)
    snap = AuthorOrderSnapshot(
        id=new_id(),
        project_id=proj.id,
        payload_json=snapshot_payload,
        sha256=sha,
        finalized_at=now,
        finalized_by=user.id,
    )
    db.add(snap)
    db.flush()
    for o in result.final_order:
        db.add(
            AuthorOrderPosition(
                id=new_id(),
                snapshot_id=snap.id,
                position=o.position,
                user_id=o.user_id,
                note=o.note,
            )
        )
    proj.finalized_at = now
    proj.finalized_by = user.id
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="author_order.finalize",
        subject_kind="project",
        subject_id=proj.id,
        payload={"sha256": sha, "positions": len(result.final_order)},
    )
    db.commit()
    return {
        "snapshot_id": snap.id,
        "sha256": sha,
        "positions": [
            {"position": o.position, "user_id": o.user_id, "note": o.note}
            for o in result.final_order
        ],
    }


@router.get("/projects/{project_id}/author-order/snapshots", response_model=list[dict])
def snapshots(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found()
    require_membership(proj.team_id, db, user.id)
    rows = (
        db.query(AuthorOrderSnapshot)
        .filter(AuthorOrderSnapshot.project_id == project_id)
        .order_by(AuthorOrderSnapshot.finalized_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "sha256": r.sha256,
            "finalized_at": r.finalized_at.isoformat(),
            "finalized_by": r.finalized_by,
        }
        for r in rows
    ]


def _render_pdf(snapshot: AuthorOrderSnapshot, proj: Project, db: Session) -> bytes:
    """Render the snapshot to a tiny PDF using reportlab Platypus."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    _width, height = LETTER
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, height - 72, f"Author Order — {proj.name}")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 90, f"Snapshot {snapshot.id}")
    c.drawString(72, height - 104, f"SHA-256: {snapshot.sha256}")
    payload = json.loads(snapshot.payload_json)
    c.drawString(72, height - 130, "Final order:")
    y = height - 150
    for pos in payload["order"]:
        c.drawString(80, y, f"{pos['position']}. user={pos['user_id']} note={pos.get('note') or '-'}")
        y -= 14
    y -= 10
    c.drawString(72, y, "Participants (points):")
    y -= 14
    for p in payload["participants"]:
        c.drawString(80, y, f"{p['display_name']} — {p['total_points']} pts")
        y -= 14
        if y < 72:
            c.showPage()
            y = height - 72
    c.showPage()
    c.save()
    return buf.getvalue()


@router.get("/projects/{project_id}/author-order/export.pdf")
def export_pdf(
    project_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found()
    require_membership(proj.team_id, db, user.id)
    snap = db.get(AuthorOrderSnapshot, snapshot_id)
    if snap is None or snap.project_id != project_id:
        raise not_found()
    pdf = _render_pdf(snap, proj, db)
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="author-order-{project_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/projects/{project_id}/author-order/export.csv")
def export_csv(
    project_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found()
    require_membership(proj.team_id, db, user.id)
    snap = db.get(AuthorOrderSnapshot, snapshot_id)
    if snap is None or snap.project_id != project_id:
        raise not_found()
    payload = json.loads(snap.payload_json)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["position", "user_id", "note", "total_points"])
    totals = {p["user_id"]: p["total_points"] for p in payload["participants"]}
    for pos in payload["order"]:
        w.writerow([pos["position"], pos["user_id"], pos.get("note") or "", totals.get(pos["user_id"], "")])
    for p in payload["participants"]:
        if p["user_id"] not in {pos["user_id"] for pos in payload["order"]}:
            w.writerow(["", p["user_id"], "(unplaced)", p["total_points"]])
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="author-order-{project_id}.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/projects/{project_id}/author-order/statement.txt")
def export_statement(
    project_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Plain text contribution statement using CRediT roles."""
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found()
    require_membership(proj.team_id, db, user.id)
    snap = db.get(AuthorOrderSnapshot, snapshot_id)
    if snap is None or snap.project_id != project_id:
        raise not_found()
    payload = json.loads(snap.payload_json)
    buf = io.StringIO()
    buf.write(f"Contribution statement — {proj.name}\n")
    buf.write(f"Snapshot SHA-256: {snap.sha256}\n\n")
    for pos in payload["order"]:
        participant = next(
            (p for p in payload["participants"] if p["user_id"] == pos["user_id"]), None
        )
        if participant is None:
            continue
        buf.write(f"{pos['position']}. {participant['display_name']}\n")
        cats = sorted(participant["by_category"].items(), key=lambda kv: -Decimal(kv[1]))
        for code, val in cats:
            buf.write(f"   - {code}: {val} pts\n")
        if pos.get("note"):
            buf.write(f"   note: {pos['note']}\n")
        buf.write("\n")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="contribution-statement-{project_id}.txt"',
            "X-Content-Type-Options": "nosniff",
        },
    )
