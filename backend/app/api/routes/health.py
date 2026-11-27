import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis

logger = logging.getLogger("huntme.health")
router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict[str, str]:
    """Process is up. No dependency checks (used by container liveness probes)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(session: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)) -> JSONResponse:
    """Dependencies reachable: PostgreSQL (with PostGIS) and Redis."""
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("readiness_database_failed")
        checks["database"] = "error"
    try:
        version = (await session.execute(text("SELECT PostGIS_Version()"))).scalar_one()
        checks["postgis"] = f"ok ({version.split()[0]})"
    except Exception:
        await session.rollback()
        checks["postgis"] = "missing"
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("readiness_redis_failed")
        checks["redis"] = "error"
    healthy = all(v.startswith("ok") for v in checks.values())
    return JSONResponse({"status": "ok" if healthy else "degraded", "checks": checks}, status_code=200 if healthy else 503)
