# api/main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

from models.db import init_db
from api.middleware.auth import get_tenant_from_request
from api.routes import recovery, mandates, metrics, audit, human_review, webhooks

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aegis API starting — initialising database...")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Aegis API shutting down.")


app = FastAPI(
    title="Aegis — Mandate Recovery API",
    description="Compliant UPI Autopay / e-NACH failure diagnosis and recovery agent.",
    version="1.0.0",
    lifespan=lifespan,
)

# Standard HTTP Security Headers (OWASP recommendations)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


allowed_origins_raw = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://aegis-platform.duckdns.org",
)
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Enforce Bearer Token Authentication on all /api/v1/* routes
auth_dependency = [Depends(get_tenant_from_request)]

app.include_router(recovery.router, prefix="/api/v1", dependencies=auth_dependency)
app.include_router(mandates.router, prefix="/api/v1", dependencies=auth_dependency)
app.include_router(metrics.router, prefix="/api/v1", dependencies=auth_dependency)
app.include_router(audit.router, prefix="/api/v1", dependencies=auth_dependency)
app.include_router(human_review.router, prefix="/api/v1", dependencies=auth_dependency)

# Webhooks verify HMAC signature directly (do not require API key)
app.include_router(webhooks.router)

# Phase 9: Prometheus metrics endpoint
if os.getenv("PROMETHEUS_ENABLED", "true").lower() in ("true", "1", "yes"):
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aegis"}

