"""Helper functions for interacting with plate database objects."""

import logging
from datetime import datetime

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager
from sqlalchemy.exc import IntegrityError

from spoolman.api.v1.models import EventType, Plate, PlateEvent
from spoolman.database import models, project
from spoolman.database.utils import SortOrder, add_where_clause_str
from spoolman.exceptions import ItemDeleteError, ItemNotFoundError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    project_id: int,
    name: str,
    file_path: str | None = None,
    estimated_weight: float | None = None,
    estimated_time: int | None = None,
    comment: str | None = None,
) -> models.Plate:
    """Add a new plate to the database."""
    project_item = await project.get_by_id(db, project_id)

    plate = models.Plate(
        project=project_item,
        name=name,
        registered=datetime.utcnow().replace(microsecond=0),
        file_path=file_path,
        estimated_weight=estimated_weight,
        estimated_time=estimated_time,
        comment=comment,
    )
    db.add(plate)
    await db.commit()
    await plate_changed(plate, EventType.ADDED)
    return plate


async def get_by_id(db: AsyncSession, plate_id: int) -> models.Plate:
    """Get a plate object from the database by its unique ID."""
    plate = await db.get(
        models.Plate,
        plate_id,
        options=[sqlalchemy.orm.joinedload(models.Plate.project)],
    )
    if plate is None:
        raise ItemNotFoundError(f"No plate with ID {plate_id} found.")
    return plate


async def find(
    *,
    db: AsyncSession,
    project_id: int | None = None,
    name: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Plate], int]:
    """Find a list of plate objects by search criteria."""
    stmt = (
        select(models.Plate)
        .join(models.Plate.project, isouter=True)
        .options(contains_eager(models.Plate.project))
    )

    if project_id is not None:
        stmt = stmt.where(models.Plate.project_id == project_id)
    stmt = add_where_clause_str(stmt, models.Plate.name, name)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            if fieldstr.startswith("project."):
                proj_fieldstr = fieldstr.split(".")[1]
                field = getattr(models.Project, proj_fieldstr)
            else:
                field = getattr(models.Plate, fieldstr)

            if order == SortOrder.ASC:
                stmt = stmt.order_by(field.asc())
            elif order == SortOrder.DESC:
                stmt = stmt.order_by(field.desc())

    if limit is not None:
        total_count_stmt = stmt.with_only_columns(func.count(), maintain_column_froms=True).order_by(None)
        total_count = (await db.execute(total_count_stmt)).scalar()
        stmt = stmt.offset(offset).limit(limit)

    rows = await db.execute(
        stmt,
        execution_options={"populate_existing": True},
    )
    result = list(rows.unique().scalars().all())
    if total_count is None:
        total_count = len(result)

    return result, total_count


async def update(
    *,
    db: AsyncSession,
    plate_id: int,
    data: dict,
) -> models.Plate:
    """Update fields of a plate object."""
    plate = await get_by_id(db, plate_id)
    for k, v in data.items():
        if k == "project_id":
            plate.project = await project.get_by_id(db, v)
        else:
            setattr(plate, k, v)
    await db.commit()
    await plate_changed(plate, EventType.UPDATED)
    return plate


async def delete(db: AsyncSession, plate_id: int) -> None:
    """Delete a plate object."""
    plate = await get_by_id(db, plate_id)
    await db.delete(plate)
    try:
        await db.commit()
        await plate_changed(plate, EventType.DELETED)
    except IntegrityError as exc:
        await db.rollback()
        raise ItemDeleteError("Failed to delete plate.") from exc


async def plate_changed(plate: models.Plate, typ: EventType) -> None:
    """Notify websocket clients that a plate has changed."""
    try:
        await websocket_manager.send(
            ("plate", str(plate.id)),
            PlateEvent(
                type=typ,
                resource="plate",
                date=datetime.utcnow(),
                payload=Plate.from_db(plate),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
