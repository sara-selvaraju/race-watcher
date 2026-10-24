from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from race_watcher.api.v1.routers import admin, alerts, meetings, status
from race_watcher.api.v1.schemas.responses import ErrorOut
from race_watcher.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("api")

app = FastAPI(
    title="race-watcher",
    version="0.1.0",
    description="Multi-meeting race-day dashboard API.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exc(_: Request, exc: Exception) -> JSONResponse:
    log.error("api.unhandled", error=str(exc), type=exc.__class__.__name__)
    return JSONResponse(
        status_code=500,
        content=ErrorOut(error="internal_server_error", detail=str(exc)).model_dump(),
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(meetings.router, prefix="/api/v1")
app.include_router(meetings.meetings_router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
