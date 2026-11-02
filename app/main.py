
import asyncio
import os
import random
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from fastapi.responses import Response


# --------------------------------------------------
# Application Configuration
# --------------------------------------------------

APP_NAME = "orders-api"

APP_VERSION = os.getenv("APP_VERSION", "v1").strip()

try:
    ERROR_RATE = float(os.getenv("ERROR_RATE", "0"))
    DELAY_MS = int(os.getenv("DELAY_MS", "0"))
except ValueError as exc:
    raise RuntimeError("Invalid application configuration") from exc

if not 0 <= ERROR_RATE <= 1:
    raise RuntimeError("ERROR_RATE must be between 0 and 1")

if not 0 <= DELAY_MS <= 10000:
    raise RuntimeError("DELAY_MS must be between 0 and 10000")


POD_NAME = os.getenv("HOSTNAME", "local")


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title="Orders API",
    description="Progressive Delivery Demo Application",
    version=APP_VERSION,
)


# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["app", "version", "method", "status"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["app", "version", "method"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.2,
        0.3,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
    ),
)


# --------------------------------------------------
# HTTP Middleware
# --------------------------------------------------

@app.middleware("http")
async def collect_metrics(request: Request, call_next):

    # Ignore health checks and Prometheus scrapes
    if request.url.path in ("/healthz", "/readyz", "/metrics"):
        return await call_next(request)

    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    REQUEST_COUNT.labels(
        app=APP_NAME,
        version=APP_VERSION,
        method=request.method,
        status=str(response.status_code),
    ).inc()

    REQUEST_DURATION.labels(
        app=APP_NAME,
        version=APP_VERSION,
        method=request.method,
    ).observe(duration)

    return response


# --------------------------------------------------
# Endpoints
# --------------------------------------------------

@app.get("/")
async def root():
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
    }


@app.get("/version")
async def get_version():
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "pod": POD_NAME,
    }


@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
    }


@app.get("/readyz")
async def readiness_check():
    return {
        "status": "ready",
    }


@app.get("/process")
async def process_order():

    # Simulate processing delay
    if DELAY_MS > 0:
        await asyncio.sleep(DELAY_MS / 1000)

    # Simulate application failure
    if random.random() < ERROR_RATE:
        raise HTTPException(
            status_code=500,
            detail="Simulated internal server error",
        )

    return {
        "status": "processed",
        "order_id": str(uuid4()),
        "version": APP_VERSION,
        "pod": POD_NAME,
    }


@app.get("/metrics")
async def metrics():

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
