"""Vercel Python entrypoint shim.

Vercel's Python builder auto-detects `main.py` at the service root and
expects it to expose a top-level ASGI/WSGI `app`. The actual application
lives in the `src/macenplast` package (installed as `macenplast` for local
dev/Docker, but not necessarily pip-installed in Vercel's build), so this
adds `src` to the import path and re-exports the real app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from macenplast.main import app  # noqa: E402

__all__ = ["app"]
