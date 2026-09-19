"""Schemas for operator authentication."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from macenplast.db.models import OperatorRole


class LoginRequest(BaseModel):
    badge_code: str
    pin: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    operator_id: uuid.UUID
    full_name: str
    role: OperatorRole


class OperatorProfile(BaseModel):
    operator_id: uuid.UUID
    full_name: str
    role: OperatorRole
