"""Start/end a pick session (BASELINE or VOICE) for the current operator."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.sessions import SessionResponse, StartSessionRequest
from macenplast.db.models import Device, Operator, PickSession
from macenplast.db.session import get_db

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/start")
def start_session(
    payload: StartSessionRequest,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> SessionResponse:
    device = db.get(Device, payload.device_id)
    if device is None or not device.active:
        raise HTTPException(status_code=404, detail="Device not found or inactive")

    session = PickSession(operator_id=operator.id, device_id=device.id, mode=payload.mode)
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse.model_validate(session)


@router.post("/{session_id}/end")
def end_session(
    session_id: uuid.UUID,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> SessionResponse:
    session = db.get(PickSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.operator_id != operator.id:
        raise HTTPException(status_code=403, detail="Not your session")

    if session.ended_at is None:
        session.ended_at = datetime.now(UTC)
        db.commit()
        db.refresh(session)
    return SessionResponse.model_validate(session)
