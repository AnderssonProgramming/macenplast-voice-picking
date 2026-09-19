"""Schemas for the Phase 4 minimal session summary.

Full KPI reporting (lines/hour, BASELINE vs. VOICE comparison, idle time)
is Phase 6's job (RF-07, R-01-R-03) — out of this build's scope. This is
just enough to prove events/incidents are queryable per session.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from macenplast.db.models import SessionMode


class SessionSummaryResponse(BaseModel):
    session_id: uuid.UUID
    mode: SessionMode
    started_at: datetime
    ended_at: datetime | None
    lines_completed: int
    mismatch_count: int
    incident_count: int
