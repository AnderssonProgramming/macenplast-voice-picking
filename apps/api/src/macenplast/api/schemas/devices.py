"""Schemas for devices."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class DeviceResponse(BaseModel):
    id: uuid.UUID
    device_code: str
    label: str

    model_config = {"from_attributes": True}
