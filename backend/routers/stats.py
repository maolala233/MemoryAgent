"""Stats router: dashboard data."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..database import db
from ..models.schemas import OpenLoopItem, StatsDistribution, StatsOverview, TimelinePoint
from ..services.memory_service import memory_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview", response_model=StatsOverview)
def overview() -> StatsOverview:
    return StatsOverview(**memory_service.get_stats())


@router.get("/distribution", response_model=StatsDistribution)
def distribution() -> StatsDistribution:
    return StatsDistribution(**db.stats_distribution())


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline(days: int = Query(30, ge=1, le=365)) -> list[TimelinePoint]:
    return [TimelinePoint(**p) for p in db.stats_timeline(days=days)]


@router.get("/open-loops", response_model=list[OpenLoopItem])
def open_loops() -> list[OpenLoopItem]:
    return [OpenLoopItem(**o) for o in memory_service.get_open_loops()]
