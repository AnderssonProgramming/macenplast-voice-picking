"""Operator authentication: PIN-based login, no SSO (out of scope per
`PLAN.md` section 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.auth import LoginRequest, LoginResponse, OperatorProfile
from macenplast.db.models import Operator
from macenplast.db.session import get_db
from macenplast.security import create_access_token, verify_pin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    operator = db.query(Operator).filter_by(badge_code=payload.badge_code).one_or_none()
    if operator is None or not operator.active or not verify_pin(payload.pin, operator.pin_hash):
        raise HTTPException(status_code=401, detail="Invalid badge code or PIN")

    token = create_access_token(operator.id, operator.role)
    return LoginResponse(
        access_token=token,
        operator_id=operator.id,
        full_name=operator.full_name,
        role=operator.role,
    )


@router.get("/me")
def get_me(operator: Operator = Depends(get_current_operator)) -> OperatorProfile:
    """Lets a client confirm a stored token is still valid."""
    return OperatorProfile(
        operator_id=operator.id, full_name=operator.full_name, role=operator.role
    )
