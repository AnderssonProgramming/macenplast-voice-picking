"""ORM models for every table in `PLAN.md` section 6.

Enum columns reuse the pick machine's own `PickState`/`BlockedOn`/
`IncidentReason` types (`macenplast.domain.pick_machine`) so the database
and the pure state machine never define the same vocabulary twice. Enums
are stored as `VARCHAR` (`native_enum=False`) rather than Postgres native
enum types, so adding a value later is a plain column-constraint migration
instead of an `ALTER TYPE`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from macenplast.db.base import Base, TimestampedBase
from macenplast.domain.pick_machine import BlockedOn, IncidentReason, PickState


class OperatorRole(StrEnum):
    """Who an operator is for access-control purposes (Phase 4)."""

    OPERATOR = "operator"
    SUPERVISOR = "supervisor"


class SessionMode(StrEnum):
    """Whether a session is the spoken, blocking flow or the on-screen baseline."""

    BASELINE = "BASELINE"
    VOICE = "VOICE"


class OrderStatus(StrEnum):
    """Lifecycle of a pick order."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Operator(TimestampedBase):
    """A warehouse operator or supervisor who can run a picking session."""

    __tablename__ = "operators"

    badge_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    pin_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[OperatorRole] = mapped_column(Enum(OperatorRole, native_enum=False, length=20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Device(TimestampedBase):
    """A handheld/scanner device an operator can sign in on."""

    __tablename__ = "devices"

    device_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Location(TimestampedBase):
    """One storage slot: aisle/bay/level plus x/y for routing."""

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("aisle", "bay", "level", name="uq_location_position"),)

    aisle: Mapped[str] = mapped_column(String(16))
    bay: Mapped[str] = mapped_column(String(16))
    level: Mapped[str] = mapped_column(String(16))
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    barcode: Mapped[str] = mapped_column(String(64), unique=True, index=True)


class Sku(TimestampedBase):
    """A stock keeping unit."""

    __tablename__ = "skus"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(300))
    voice_alias: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="unidad")

    barcodes: Mapped[list[SkuBarcode]] = relationship(
        back_populates="sku", cascade="all, delete-orphan"
    )


class SkuBarcode(TimestampedBase):
    """One of possibly several barcodes that identify a SKU."""

    __tablename__ = "sku_barcodes"

    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skus.id"))
    barcode: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    sku: Mapped[Sku] = relationship(back_populates="barcodes")


class StockLevel(TimestampedBase):
    """On-hand and reserved quantity of a SKU at a location.

    `quantity` is physical on-hand stock; `reserved_qty` is stock already
    allocated to an in-progress pick line but not yet committed. Available
    stock for new reservations is `quantity - reserved_qty` (see
    `macenplast.ports.wms_port.WmsPort.get_stock`).
    """

    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("sku_id", "location_id", name="uq_stock_sku_location"),)

    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skus.id"))
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_qty: Mapped[int] = mapped_column(Integer, default=0)


class MovementType(StrEnum):
    """What a `StockMovement` ledger row represents."""

    RESERVE = "RESERVE"
    COMMIT = "COMMIT"
    RELEASE = "RELEASE"


class StockMovement(TimestampedBase):
    """Append-only ledger of WMS operations, keyed for idempotency.

    `(movement_type, idempotency_key)` is unique: replaying the same
    reserve/commit/release call twice (e.g. a retried offline sync) is a
    no-op the second time. See `macenplast.adapters.mock_wms`.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint("movement_type", "idempotency_key", name="uq_movement_idempotency"),
    )

    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skus.id"))
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, native_enum=False, length=20)
    )
    quantity: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)


class PickSession(TimestampedBase):
    """One operator's run on one device, tagged BASELINE or VOICE."""

    __tablename__ = "pick_sessions"

    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"))
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    mode: Mapped[SessionMode] = mapped_column(Enum(SessionMode, native_enum=False, length=20))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)


class PickOrder(TimestampedBase):
    """A customer/dispatch order to be picked, made up of pick lines."""

    __tablename__ = "pick_orders"

    order_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pick_sessions.id"), nullable=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=20), default=OrderStatus.PENDING
    )


class PickLine(TimestampedBase):
    """One SKU/location/quantity line within an order.

    `state`, `attempts`, `blocked_on`, and `last_qty` mirror the pick
    machine's `PickContext` (`macenplast.domain.pick_machine`) — the API
    layer (Phase 4) is what actually calls `transition()` and persists the
    result here; this table never runs the machine itself.
    """

    __tablename__ = "pick_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_orders.id"))
    sku_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skus.id"))
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    expected_qty: Mapped[int] = mapped_column(Integer)
    scan_each_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[PickState] = mapped_column(
        Enum(PickState, native_enum=False, length=20), default=PickState.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    blocked_on: Mapped[BlockedOn | None] = mapped_column(
        Enum(BlockedOn, native_enum=False, length=20), nullable=True
    )
    last_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    sku: Mapped[Sku] = relationship()
    location: Mapped[Location] = relationship()


class PickEvent(TimestampedBase):
    """Append-only audit log entry for one pick line.

    `client_event_id` is generated by whichever client created the event
    (the offline PWA, most of the time) and is what makes batched sync
    idempotent: replaying the same event twice must not double-apply it.
    """

    __tablename__ = "pick_events"

    pick_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_lines.id"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_sessions.id"))
    client_event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Incident(TimestampedBase):
    """A reported exception (short/empty location/damaged) on a pick line."""

    __tablename__ = "incidents"

    pick_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_lines.id"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_sessions.id"))
    reason: Mapped[IncidentReason] = mapped_column(
        Enum(IncidentReason, native_enum=False, length=20)
    )
    reported_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class VoiceClip(TimestampedBase):
    """A synthesized audio clip, cached by content hash (Phase 3).

    Audio bytes live in the row itself (`audio_data`), not on local disk:
    the deployed target (Vercel Functions) has no persistent filesystem
    between invocations, so a `file_path` written by one instance would be
    invisible to the next. Clips are small (a few KB of speech each), so
    Postgres storage is the simpler choice over adding a blob store.
    """

    __tablename__ = "voice_clips"

    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    text: Mapped[str] = mapped_column(String(500))
    voice_id: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(64))
    audio_format: Mapped[str] = mapped_column(String(16), default="mp3")
    audio_data: Mapped[bytes] = mapped_column(LargeBinary)


class Survey(TimestampedBase):
    """A post-shift fatigue/effort survey response (Phase 6)."""

    __tablename__ = "surveys"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pick_sessions.id"))
    operator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("operators.id"))
    effort_score: Mapped[int] = mapped_column(Integer)
    fatigue_score: Mapped[int] = mapped_column(Integer)
    comments: Mapped[str | None] = mapped_column(String(1000), nullable=True)


__all__ = [
    "Base",
    "Device",
    "Incident",
    "Location",
    "MovementType",
    "Operator",
    "OperatorRole",
    "OrderStatus",
    "PickEvent",
    "PickLine",
    "PickOrder",
    "PickSession",
    "SessionMode",
    "Sku",
    "SkuBarcode",
    "StockLevel",
    "StockMovement",
    "Survey",
    "VoiceClip",
]
