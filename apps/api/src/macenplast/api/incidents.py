"""List and resolve incidents (RF-06). Created as a side effect of
`macenplast.api.events` handling `LogIncident` — no separate creation
endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from macenplast.api.deps import get_current_operator, require_supervisor
from macenplast.api.schemas.incidents import IncidentResponse
from macenplast.db.models import Incident, Operator
from macenplast.db.session import get_db

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    resolved: bool | None = None,
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> list[IncidentResponse]:
    query = db.query(Incident)
    if resolved is not None:
        query = query.filter(Incident.resolved == resolved)
    incidents = query.order_by(Incident.created_at.desc()).all()
    return [IncidentResponse.model_validate(i) for i in incidents]


@router.post("/{incident_id}/resolve")
def resolve_incident(
    incident_id: uuid.UUID,
    operator: Operator = require_supervisor,
    db: Session = Depends(get_db),
) -> IncidentResponse:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.resolved = True
    db.commit()
    db.refresh(incident)
    return IncidentResponse.model_validate(incident)
