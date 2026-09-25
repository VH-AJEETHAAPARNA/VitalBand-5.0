"""
VitalBand Alerts and Audit History Router (Multi-Tenant)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.database import get_db
from backend.models import Event, User
from backend.schemas import EventResponse
from backend.auth import get_current_user

router = APIRouter(tags=["Alerts"])


@router.get("/alerts", response_model=List[EventResponse])
async def list_alerts(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List the last 50 warning/critical events for the hospital.
    If anonymous, falls back to DEFAULT_HOSP.
    """
    hospital_id = current_user.hospital_id if current_user else "DEFAULT_HOSP"

    stmt = (
        select(Event)
        .where(
            Event.hospital_id == hospital_id,
            Event.severity.in_(["WARNING", "CRITICAL"])
        )
        .order_by(desc(Event.id))
        .limit(50)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/history", response_model=List[EventResponse])
async def list_history(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List the last 100 events of any severity for the hospital.
    If anonymous, falls back to DEFAULT_HOSP.
    """
    hospital_id = current_user.hospital_id if current_user else "DEFAULT_HOSP"

    stmt = (
        select(Event)
        .where(Event.hospital_id == hospital_id)
        .order_by(desc(Event.id))
        .limit(100)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
