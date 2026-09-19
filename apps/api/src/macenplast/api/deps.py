"""Shared FastAPI dependencies: DB session, current operator, role checks."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from macenplast.db.models import Operator, OperatorRole
from macenplast.db.session import get_db
from macenplast.security import InvalidTokenError, decode_access_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_operator(
    token: str = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> Operator:
    """Resolve the authenticated `Operator` from the bearer token.

    Raises:
        HTTPException: 401 if the token is missing/invalid/expired, or the
            operator it names no longer exists or is inactive.
    """
    try:
        payload = decode_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    operator = db.get(Operator, payload.operator_id)
    if operator is None or not operator.active:
        raise HTTPException(status_code=401, detail="Operator not found or inactive")
    return operator


def require_role(*roles: OperatorRole) -> Callable[[Operator], Operator]:
    """Dependency factory: 403s unless the current operator has one of `roles`.

    Used so an operator can't grant their own supervisor override — see
    `macenplast.api.events`.
    """

    def check(operator: Operator = Depends(get_current_operator)) -> Operator:
        if operator.role not in roles:
            raise HTTPException(status_code=403, detail="Not authorized for this action")
        return operator

    return check


# Predefined as a module-level singleton (rather than `Depends(require_role(...))`
# inline at each use site) so the dependency isn't rebuilt at every import of a
# router module — also sidesteps ruff B008 flagging a call in an argument default.
require_supervisor = Depends(require_role(OperatorRole.SUPERVISOR))
