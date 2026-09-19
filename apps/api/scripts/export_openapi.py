#!/usr/bin/env python
"""Exports the FastAPI app's OpenAPI schema to `apps/api/openapi.json`.

Committed so Phase 5's web app can generate a typed client against it
without needing a running server. CI re-runs this and fails the build if
the committed file is stale (see `.github/workflows/ci.yml`).

    python scripts/export_openapi.py [--check]

`--check` exits non-zero if the file on disk doesn't match a fresh
export, without writing anything — used by CI as a drift check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from macenplast.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def render_schema() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if openapi.json is out of date, without writing it.",
    )
    args = parser.parse_args()

    fresh_schema = render_schema()

    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
        if current != fresh_schema:
            print(f"{OUTPUT_PATH} is out of date. Run `python scripts/export_openapi.py`.")
            return 1
        print(f"{OUTPUT_PATH} is up to date.")
        return 0

    OUTPUT_PATH.write_text(fresh_schema, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
