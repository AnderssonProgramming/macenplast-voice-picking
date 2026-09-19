#!/usr/bin/env python
"""Creates one fresh, unassigned order for Playwright e2e setup.

Used by `apps/web/e2e/global-setup.ts` — never call this in production.
Prints a JSON object with the new order's code and each line's expected
barcodes/quantity, so the e2e test can simulate correct scans without
querying the database itself.

    python scripts/create_test_order.py [num_lines]
"""

from __future__ import annotations

import json
import sys
import uuid

from macenplast.db import seed
from macenplast.db.base import Base
from macenplast.db.models import Location, PickLine, PickOrder, Sku, StockLevel
from macenplast.db.session import SessionLocal, engine
from macenplast.domain.pick_machine import PickState


def main(num_lines: int = 2) -> dict[str, object]:
    Base.metadata.create_all(bind=engine)
    seed.main()  # idempotent — guarantees SKUs/stock/operators/devices exist

    with SessionLocal() as db:
        skus = db.query(Sku).limit(num_lines).all()
        if len(skus) < num_lines:
            raise RuntimeError("Not enough seeded SKUs to build a test order")

        order = PickOrder(order_code=f"E2E-{uuid.uuid4().hex[:8]}")
        db.add(order)
        db.flush()

        lines_info: list[dict[str, object]] = []
        for i, sku in enumerate(skus):
            stock = db.query(StockLevel).filter_by(sku_id=sku.id).first()
            if stock is None:
                raise RuntimeError(f"No stock for seeded sku {sku.code}")
            location = db.get(Location, stock.location_id)
            if location is None:
                raise RuntimeError(f"Missing location {stock.location_id}")
            barcode = sku.barcodes[0].barcode if sku.barcodes else None
            if barcode is None:
                raise RuntimeError(f"SKU {sku.code} has no barcode")

            expected_qty = 3 + i
            db.add(
                PickLine(
                    order_id=order.id,
                    sku_id=sku.id,
                    location_id=location.id,
                    sequence=i,
                    expected_qty=expected_qty,
                    state=PickState.PENDING,
                )
            )
            lines_info.append(
                {
                    "expected_qty": expected_qty,
                    "location_barcode": location.barcode,
                    "sku_barcode": barcode,
                }
            )

        db.commit()
        return {"order_id": str(order.id), "order_code": order.order_code, "lines": lines_info}


if __name__ == "__main__":
    num_lines = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    print(json.dumps(main(num_lines)))
    sys.exit(0)
