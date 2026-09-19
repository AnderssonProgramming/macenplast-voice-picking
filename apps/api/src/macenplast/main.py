"""FastAPI application entry point."""

from fastapi import FastAPI

from macenplast.api.health import router as health_router
from macenplast.config import get_settings

app = FastAPI(title=get_settings().app_name)

app.include_router(health_router)
