"""Idempotent seed data: a small realistic warehouse for local dev and tests.

Running this twice must not duplicate rows — every entity is looked up by
its natural unique key before being created. Run with:

    python -m macenplast.db.seed
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from macenplast.db.models import (
    Device,
    Location,
    Operator,
    OperatorRole,
    OrderStatus,
    PickLine,
    PickOrder,
    Sku,
    SkuBarcode,
    StockLevel,
)
from macenplast.db.session import SessionLocal, engine
from macenplast.domain.pick_machine import PickState

AISLES = ["A", "B", "C"]
BAYS = ["1", "2", "3", "4"]
LEVELS = ["1", "2"]
SKU_COUNT = 30
ORDER_COUNT = 3
LINES_PER_ORDER = 5


def _hash_pin(pin: str) -> str:
    """Placeholder PIN hashing for seed data only.

    Phase 4 (operator auth) replaces this with a real password hash
    (e.g. argon2); this just avoids storing seed PINs as plain text.
    """
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def get_or_create[ModelT](
    session: Session,
    model: type[ModelT],
    defaults: dict[str, Any] | None = None,
    **lookup: Any,
) -> ModelT:
    """Return the row matching `lookup`, creating it (with `defaults`) if missing."""
    instance = session.query(model).filter_by(**lookup).one_or_none()
    if instance is not None:
        return instance
    instance = model(**lookup, **(defaults or {}))
    session.add(instance)
    session.flush()
    return instance


def seed_locations(session: Session) -> list[Location]:
    locations = []
    for x, aisle in enumerate(AISLES):
        for y, bay in enumerate(BAYS):
            for level in LEVELS:
                barcode = f"LOC-{aisle}{bay}-{level}"
                location = get_or_create(
                    session,
                    Location,
                    aisle=aisle,
                    bay=bay,
                    level=level,
                    defaults={"barcode": barcode, "pos_x": float(x), "pos_y": float(y)},
                )
                locations.append(location)
    return locations


def seed_skus(session: Session) -> list[Sku]:
    skus = []
    for i in range(1, SKU_COUNT + 1):
        code = f"SKU-{i:03d}"
        sku = get_or_create(
            session,
            Sku,
            code=code,
            defaults={
                "description": f"Producto {i:03d}",
                "voice_alias": f"Producto {i:03d}",
                "unit": "caja" if i % 3 == 0 else "unidad",
            },
        )
        get_or_create(session, SkuBarcode, barcode=f"BC-{code}", defaults={"sku_id": sku.id})
        skus.append(sku)
    return skus


def seed_stock(session: Session, skus: list[Sku], locations: list[Location]) -> None:
    for i, sku in enumerate(skus):
        location = locations[i % len(locations)]
        get_or_create(
            session,
            StockLevel,
            sku_id=sku.id,
            location_id=location.id,
            defaults={"quantity": 100},
        )


def seed_operators_and_devices(session: Session) -> None:
    get_or_create(
        session,
        Operator,
        badge_code="0001",
        defaults={
            "full_name": "Operador Demo",
            "pin_hash": _hash_pin("1234"),
            "role": OperatorRole.OPERATOR,
        },
    )
    get_or_create(
        session,
        Operator,
        badge_code="9001",
        defaults={
            "full_name": "Supervisor Demo",
            "pin_hash": _hash_pin("9999"),
            "role": OperatorRole.SUPERVISOR,
        },
    )
    get_or_create(
        session,
        Device,
        device_code="HANDHELD-01",
        defaults={"label": "Terminal 01"},
    )


def seed_orders(session: Session, skus: list[Sku], locations: list[Location]) -> None:
    for order_num in range(1, ORDER_COUNT + 1):
        order_code = f"ORD-{order_num:04d}"
        order = get_or_create(
            session,
            PickOrder,
            order_code=order_code,
            defaults={"status": OrderStatus.PENDING},
        )
        existing_lines = session.query(PickLine).filter_by(order_id=order.id).count()
        if existing_lines > 0:
            continue
        for line_num in range(LINES_PER_ORDER):
            sku = skus[(order_num * LINES_PER_ORDER + line_num) % len(skus)]
            location = locations[(order_num * LINES_PER_ORDER + line_num) % len(locations)]
            session.add(
                PickLine(
                    order_id=order.id,
                    sku_id=sku.id,
                    location_id=location.id,
                    sequence=line_num,
                    expected_qty=5 + line_num,
                    state=PickState.PENDING,
                )
            )
        session.flush()


def main() -> None:
    with SessionLocal() as session:
        locations = seed_locations(session)
        skus = seed_skus(session)
        seed_stock(session, skus, locations)
        seed_operators_and_devices(session)
        seed_orders(session, skus, locations)
        session.commit()


if __name__ == "__main__":
    from macenplast.db.base import Base

    Base.metadata.create_all(bind=engine)
    main()
