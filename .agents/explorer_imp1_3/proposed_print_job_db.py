"""Helper functions for interacting with print job database objects."""

import logging
from datetime import datetime, timezone

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from spoolman.api.v1.models import EventType, PrintJob, PrintJobEvent
from spoolman.database import models, plate, spool
from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_str_opt
from spoolman.exceptions import ItemCreateError, ItemDeleteError, ItemNotFoundError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


def utc_timezone_naive(dt: datetime) -> datetime:
    """Convert a datetime object to UTC and remove timezone info."""
    return dt.astimezone(tz=timezone.utc).replace(tzinfo=None)


async def create(
    *,
    db: AsyncSession,
    plate_id: int,
    status: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    printer_name: str | None = None,
    comment: str | None = None,
    spool_usages: list[dict] | None = None,
) -> models.PrintJob:
    """Add a new print job to the database."""
    if start_time is not None and end_time is not None:
        if end_time < start_time:
            raise ItemCreateError("end_time cannot be before start_time.")

    plate_item = await plate.get_by_id(db, plate_id)

    db_spool_usages = []
    if spool_usages is not None:
        for usage in spool_usages:
            spool_item = await spool.get_by_id(db, usage["spool_id"])
            db_spool_usages.append(
                models.PrintJobSpool(
                    spool=spool_item,
                    weight_used=usage["weight_used"],
                )
            )

    print_job = models.PrintJob(
        plate=plate_item,
        status=status,
        registered=datetime.utcnow().replace(microsecond=0),
        start_time=utc_timezone_naive(start_time) if start_time is not None else None,
        end_time=utc_timezone_naive(end_time) if end_time is not None else None,
        printer_name=printer_name,
        comment=comment,
        spool_usages=db_spool_usages,
    )
    db.add(print_job)
    await db.commit()
    await print_job_changed(print_job, EventType.ADDED)
    return print_job


async def get_by_id(db: AsyncSession, print_job_id: int) -> models.PrintJob:
    """Get a print job object from the database by its unique ID."""
    print_job = await db.get(
        models.PrintJob,
        print_job_id,
        options=[
            joinedload(models.PrintJob.plate).joinedload(models.Plate.project),
            joinedload(models.PrintJob.spool_usages).joinedload(models.PrintJobSpool.spool).joinedload(models.Spool.filament),
        ],
    )
    if print_job is None:
        raise ItemNotFoundError(f"No print job with ID {print_job_id} found.")
    return print_job


async def find(
    *,
    db: AsyncSession,
    plate_id: int | None = None,
    status: str | None = None,
    printer_name: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.PrintJob], int]:
    """Find a list of print job objects by search criteria."""
    stmt = (
        select(models.PrintJob)
        .options(
            joinedload(models.PrintJob.plate).joinedload(models.Plate.project),
            joinedload(models.PrintJob.spool_usages).joinedload(models.PrintJobSpool.spool).joinedload(models.Spool.filament),
        )
    )

    if plate_id is not None:
        stmt = stmt.where(models.PrintJob.plate_id == plate_id)
    stmt = add_where_clause_str(stmt, models.PrintJob.status, status)
    stmt = add_where_clause_str_opt(stmt, models.PrintJob.printer_name, printer_name)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            if fieldstr.startswith("plate."):
                plate_fieldstr = fieldstr.split(".")[1]
                field = getattr(models.Plate, plate_fieldstr)
            else:
                field = getattr(models.PrintJob, fieldstr)

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
    print_job_id: int,
    data: dict,
) -> models.PrintJob:
    """Update fields of a print job object."""
    print_job = await get_by_id(db, print_job_id)

    # Check times chronologically
    new_start_time = data.get("start_time", print_job.start_time)
    new_end_time = data.get("end_time", print_job.end_time)
    if new_start_time is not None and new_end_time is not None:
        # Normalize timezones for comparison if they are datetime objects
        comp_start = utc_timezone_naive(new_start_time) if isinstance(new_start_time, datetime) else new_start_time
        comp_end = utc_timezone_naive(new_end_time) if isinstance(new_end_time, datetime) else new_end_time
        if comp_end < comp_start:
            raise ItemCreateError("end_time cannot be before start_time.")

    for k, v in data.items():
        if k == "plate_id":
            print_job.plate = await plate.get_by_id(db, v)
        elif k == "spool_usages":
            # Purge old usages
            await db.execute(
                sqlalchemy.delete(models.PrintJobSpool).where(models.PrintJobSpool.print_job_id == print_job_id)
            )
            # Create new ones
            new_usages = []
            for usage in v:
                spool_item = await spool.get_by_id(db, usage["spool_id"])
                new_usages.append(
                    models.PrintJobSpool(
                        spool=spool_item,
                        weight_used=usage["weight_used"],
                    )
                )
            print_job.spool_usages = new_usages
        elif k in ("start_time", "end_time"):
            setattr(print_job, k, utc_timezone_naive(v) if v is not None else None)
        else:
            setattr(print_job, k, v)

    await db.commit()
    await print_job_changed(print_job, EventType.UPDATED)
    return print_job


async def delete(db: AsyncSession, print_job_id: int) -> None:
    """Delete a print job object."""
    print_job = await get_by_id(db, print_job_id)
    # Purge usages first to ensure clean cascade
    await db.execute(
        sqlalchemy.delete(models.PrintJobSpool).where(models.PrintJobSpool.print_job_id == print_job_id)
    )
    await db.delete(print_job)
    try:
        await db.commit()
        await print_job_changed(print_job, EventType.DELETED)
    except IntegrityError as exc:
        await db.rollback()
        raise ItemDeleteError("Failed to delete print job.") from exc


async def print_job_changed(print_job: models.PrintJob, typ: EventType) -> None:
    """Notify websocket clients that a print job has changed."""
    try:
        await websocket_manager.send(
            ("print_job", str(print_job.id)),
            PrintJobEvent(
                type=typ,
                resource="print_job",
                date=datetime.utcnow(),
                payload=PrintJob.from_db(print_job),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
