import time
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
from collections import deque


load_dotenv()
from app.config_loader import load_rules_with_metadata
from app.router import RoutingEngine
from app.routes import router as parcel_router
from app.logging_config import setup_logging
from app.limiter import limiter
from app.feature_flags import FeatureFlags
from app.metrics import MetricsStore
from app.security import get_allowed_origins, get_trusted_hosts

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    loaded = load_rules_with_metadata()
    app.state.engine = RoutingEngine(loaded.rules, version=loaded.version)
    app.state.limiter = limiter
    app.state.flags = FeatureFlags.from_env()
    app.state.metrics = MetricsStore()
    app.state.parcel_history = deque(maxlen=100)  # In-memory history (last 100 parcels)
    logger.info(
        "routing_engine_started",
        total_rules=len(loaded.rules),
        ruleset_version=loaded.version,
        feature_flags=app.state.flags.model_dump(),
    )
    yield
    logger.info("routing_engine_stopped")


app = FastAPI(
    title="Parcel Routing System",
    description="Routes parcels to departments based on configurable business rules.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=get_trusted_hosts(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
)


@app.middleware("http")
async def reject_large_json_requests(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and request.url.path in {"/api/v1/route", "/api/v1/route/simulate"}:
        if int(content_length) > 1024 * 1024:
            return JSONResponse(status_code=413, content={"detail": "Request too large."})
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'; "
    "base-uri 'none';"
)
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. The incident has been logged."},
    )


app.include_router(parcel_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check(request: Request):
    engine: RoutingEngine = request.app.state.engine
    return {
        "status": "healthy",
        "rules_loaded": len(engine.rules),
        "ruleset_version": engine.version,
        "version": "1.0.0",
        "feature_flags": request.app.state.flags.model_dump(),
        "trusted_hosts": get_trusted_hosts(),
        "allowed_origins": get_allowed_origins(),
    }