"""List active devices — what an operator's PWA picks from at shift start.

No device-registration flow here: devices are provisioned out of band
(seed data for now; a real deployment would add an admin endpoint before
Phase 9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from macenplast.api.deps import get_current_operator
from macenplast.api.schemas.devices import DeviceResponse
from macenplast.db.models import Device, Operator
from macenplast.db.session import get_db

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
def list_devices(
    operator: Operator = Depends(get_current_operator),
    db: Session = Depends(get_db),
) -> list[DeviceResponse]:
    devices = db.query(Device).filter(Device.active.is_(True)).all()
    return [DeviceResponse.model_validate(d) for d in devices]
