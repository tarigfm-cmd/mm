import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import Base, engine
from app.routes import analytics as analytics_router
from app.routes import auth as auth_router
from app.routes import billing as billing_router
from app.routes import content as content_router
from app.routes import evidence as evidence_router
from app.routes import health as health_router
from app.routes import learn as learn_router
from app.routes import materials as materials_router
from app.routes import organizations as orgs_router
from app.routes import progress as progress_router
from app.routes import scenarios as scenarios_router

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

# ── Sentry (optional) ─────────────────────────────────────────────────────────
if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


async def _seed_subscription_plans() -> None:
    """Idempotent seed for the 4 default subscription plans."""
    from app.database import SessionLocal
    from app.models.billing import SubscriptionPlan

    plans = [
        dict(
            code="free",
            name="Free",
            price_monthly_cents=0,
            max_training_sessions_per_month=20,
            max_published_content_access_per_month=100,
            allows_admin_governance=False,
            allows_bulk_import=False,
            allows_institution_dashboard=False,
            allows_ai_tutor=False,
            allows_osce=False,
            allows_games=False,
        ),
        dict(
            code="pro",
            name="Pro",
            price_monthly_cents=1999,
            max_training_sessions_per_month=1000,
            max_published_content_access_per_month=10000,
            allows_admin_governance=False,
            allows_bulk_import=False,
            allows_institution_dashboard=False,
            allows_ai_tutor=False,
            allows_osce=True,
            allows_games=True,
        ),
        dict(
            code="institution",
            name="Institution",
            price_monthly_cents=9900,
            max_training_sessions_per_month=100000,
            max_published_content_access_per_month=None,
            allows_admin_governance=False,
            allows_bulk_import=False,
            allows_institution_dashboard=True,
            allows_ai_tutor=False,
            allows_osce=True,
            allows_games=True,
        ),
        dict(
            code="enterprise",
            name="Enterprise",
            price_monthly_cents=49900,
            max_training_sessions_per_month=None,
            max_published_content_access_per_month=None,
            allows_admin_governance=True,
            allows_bulk_import=True,
            allows_institution_dashboard=True,
            allows_ai_tutor=False,
            allows_osce=True,
            allows_games=True,
        ),
    ]

    from sqlalchemy import select
    async with SessionLocal() as db:
        for plan_data in plans:
            existing = (
                await db.execute(
                    select(SubscriptionPlan).where(SubscriptionPlan.code == plan_data["code"])
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(SubscriptionPlan(**plan_data))
        await db.commit()
    logger.info("Subscription plans seeded.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up — creating database tables…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")
    await _seed_subscription_plans()
    yield
    logger.info("Shutting down — disposing database engine…")
    await engine.dispose()


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "PharmLearn AI — Community Pharmacy Training Platform. "
        "A world-class SaaS platform supporting clinical cases, OTC triage, prescription screening, "
        "drug interaction detection, OSCE stations, adaptive assessments, pharmacy games, "
        "and AI-powered tutoring for community pharmacy education."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(materials_router.router)
app.include_router(scenarios_router.router)
app.include_router(orgs_router.router)
app.include_router(orgs_router.roles_router)
app.include_router(progress_router.router)
app.include_router(content_router.router)
app.include_router(evidence_router.router)
app.include_router(analytics_router.router)
app.include_router(learn_router.router)
app.include_router(billing_router.router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )
