"""Minimal per-session summary (RF-07). See `schemas/reports.py` on scope:
the full KPI/BASELINE-vs-VOICE comparison is Phase 6."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.reports import SessionSummaryResponse
from macenplast.db.models import Incident, Operator, PickEvent, PickSession
from macenplast.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


def _effects(event: PickEvent) -> list[dict[str, object]]:
    result: list[dict[str, object]] = event.payload.get("result", {}).get("effects", [])
    return result


@router.get("/sessions/{session_id}/summary")
def get_session_summary(
    session_id: uuid.UUID,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> SessionSummaryResponse:
    session = db.get(PickSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    events = db.query(PickEvent).filter_by(session_id=session_id).all()
    lines_completed = sum(
        1 for e in events if any(eff.get("type") == "QUEUE_SYNC" for eff in _effects(e))
    )
    mismatch_count = sum(
        1 for e in events if any(eff.get("type") == "PLAY_ALERT" for eff in _effects(e))
    )
    incident_count = db.query(Incident).filter_by(session_id=session_id).count()

    return SessionSummaryResponse(
        session_id=session.id,
        mode=session.mode,
        started_at=session.started_at,
        ended_at=session.ended_at,
        lines_completed=lines_completed,
        mismatch_count=mismatch_count,
        incident_count=incident_count,
    )
