"""FastAPI application entry point."""

from fastapi import FastAPI

from macenplast.api.auth import router as auth_router
from macenplast.api.events import router as events_router
from macenplast.api.health import router as health_router
from macenplast.api.incidents import router as incidents_router
from macenplast.api.orders import router as orders_router
from macenplast.api.reports import router as reports_router
from macenplast.api.sessions import router as sessions_router
from macenplast.api.sse import router as sse_router
from macenplast.api.voice import router as voice_router
from macenplast.config import get_settings

app = FastAPI(title=get_settings().app_name)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(orders_router)
app.include_router(events_router)
app.include_router(incidents_router)
app.include_router(reports_router)
app.include_router(sse_router)
app.include_router(voice_router)
