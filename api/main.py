# api/main.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.db import init_db
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

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recovery.router, prefix="/api/v1")
app.include_router(mandates.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(human_review.router, prefix="/api/v1")
app.include_router(webhooks.router)

# Phase 9: Prometheus metrics endpoint
if os.getenv("PROMETHEUS_ENABLED", "true").lower() in ("true", "1", "yes"):
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aegis"}
