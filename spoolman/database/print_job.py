"""Helper functions for interacting with print job database objects."""

import logging
from datetime import datetime, timezone

def utc_timezone_naive(dt: datetime) -> datetime:
    """Convert a datetime object to UTC and remove timezone info."""
    return dt.astimezone(tz=timezone.utc).replace(tzinfo=None)


import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, PrintJob, PrintJobEvent
from spoolman.database import models, plate, printer, spool
from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_int
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    plate_id: int,
    status: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    printer_name: str | None = None,
    printer_id: int | None = None,
    comment: str | None = None,
    spool_usages: list[dict] | None = None,
) -> models.PrintJob:
    """Add a new print job to the database."""
    if start_time is not None:
        start_time = utc_timezone_naive(start_time)
    if end_time is not None:
        end_time = utc_timezone_naive(end_time)

    if start_time is not None and end_time is not None:
        if end_time < start_time:
            raise ValueError("end_time must be after or equal to start_time")

    # Verify plate exists
    await plate.get_by_id(db, plate_id)

    # Verify all spools exist
    usages_data = spool_usages or []
    for usage in usages_data:
        await spool.get_by_id(db, usage["spool_id"])

    db_printer = None
    if printer_id is not None:
        db_printer = await printer.get_by_id(db, printer_id)
    elif printer_name:
        stmt = select(models.Printer).where(models.Printer.name == printer_name)
        db_printer = (await db.execute(stmt)).scalars().first()
        if db_printer is None:
            db_printer = models.Printer(name=printer_name)
            db.add(db_printer)
            await db.flush()

    # Create the PrintJob
    print_job = models.PrintJob(
        plate_id=plate_id,
        status=status,
        registered=datetime.utcnow().replace(microsecond=0),
        start_time=start_time,
        end_time=end_time,
        printer_id=db_printer.id if db_printer is not None else None,
        comment=comment,
    )
    db.add(print_job)
    await db.flush()

    # Create PrintJobSpool linkages
    for usage in usages_data:
        pjs = models.PrintJobSpool(
            print_job_id=print_job.id,
            spool_id=usage["spool_id"],
            weight_used=usage["weight_used"],
        )
        db.add(pjs)
    await db.flush()

    # Reload print job to make sure relationships are loaded
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job.id).options(joinedload("*"))
    print_job = (await db.execute(stmt)).unique().scalar_one()

    # If status is successful, deduct the weight
    if status == "successful":
        for usage in print_job.spool_usages:
            await spool.use_weight(db, usage.spool_id, usage.weight_used)

    await db.commit()

    # Reload to ensure all committed state is loaded
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job.id).options(joinedload("*"))
    print_job = (await db.execute(stmt)).unique().scalar_one()

    await print_job_changed(print_job, EventType.ADDED)
    return print_job


async def get_by_id(db: AsyncSession, print_job_id: int) -> models.PrintJob:
    """Get a print job object from the database by the unique ID."""
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job_id).options(joinedload("*"))
    result = await db.execute(stmt)
    print_job = result.unique().scalars().first()
    if print_job is None:
        raise ItemNotFoundError(f"No print job with ID {print_job_id} found.")
    return print_job


async def find(
    *,
    db: AsyncSession,
    plate_id: int | None = None,
    status: str | None = None,
    printer_id: int | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.PrintJob], int]:
    """Find a list of print job objects by search criteria."""
    stmt = select(models.PrintJob).options(joinedload("*"))

    stmt = add_where_clause_int(stmt, models.PrintJob.plate_id, plate_id)
    stmt = add_where_clause_str(stmt, models.PrintJob.status, status)
    stmt = add_where_clause_int(stmt, models.PrintJob.printer_id, printer_id)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
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
    """Update the fields of a print job object."""
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job_id).options(joinedload("*"))
    result = await db.execute(stmt)
    print_job = result.unique().scalars().first()
    if print_job is None:
        raise ItemNotFoundError(f"No print job with ID {print_job_id} found.")

    if "start_time" in data and data["start_time"] is not None:
        data["start_time"] = utc_timezone_naive(data["start_time"])
    if "end_time" in data and data["end_time"] is not None:
        data["end_time"] = utc_timezone_naive(data["end_time"])

    new_start = data.get("start_time", print_job.start_time)
    new_end = data.get("end_time", print_job.end_time)
    if new_start is not None and new_end is not None:
        if new_end < new_start:
            raise ValueError("end_time must be after or equal to start_time")

    if "plate_id" in data:
        await plate.get_by_id(db, data["plate_id"])

    if "spool_usages" in data:
        for u in data["spool_usages"]:
            await spool.get_by_id(db, u["spool_id"])

    if "printer_id" in data:
        printer_id_val = data.pop("printer_id")
        if printer_id_val is None:
            print_job.printer = None
        else:
            db_printer = await printer.get_by_id(db, printer_id_val)
            print_job.printer = db_printer
    elif "printer_name" in data:
        printer_name_val = data.pop("printer_name")
        if printer_name_val is None or printer_name_val == "":
            print_job.printer = None
        else:
            stmt = select(models.Printer).where(models.Printer.name == printer_name_val)
            db_printer = (await db.execute(stmt)).scalars().first()
            if db_printer is None:
                db_printer = models.Printer(name=printer_name_val)
                db.add(db_printer)
                await db.flush()
            print_job.printer = db_printer

    old_status = print_job.status
    old_usages = [(u.spool_id, u.weight_used) for u in print_job.spool_usages]

    status_changed = ("status" in data and data["status"] != old_status)
    usages_changed = ("spool_usages" in data)

    if status_changed or usages_changed:
        # Refund old if it was successful
        if old_status == "successful":
            for old_spool_id, old_weight in old_usages:
                await spool.use_weight(db, old_spool_id, -old_weight)

        # Apply updates
        for k, v in data.items():
            if k == "spool_usages":
                # Delete old usages
                for u in print_job.spool_usages:
                    await db.delete(u)
                await db.flush()
                print_job.spool_usages = [
                    models.PrintJobSpool(
                        spool_id=u["spool_id"],
                        weight_used=u["weight_used"],
                    )
                    for u in v
                ]
            else:
                setattr(print_job, k, v)
        await db.flush()

        # Deduct new if it is successful
        if print_job.status == "successful":
            for usage in print_job.spool_usages:
                await spool.use_weight(db, usage.spool_id, usage.weight_used)
    else:
        # Just apply other updates
        for k, v in data.items():
            setattr(print_job, k, v)
        await db.flush()

    await db.commit()

    # Reload to ensure all changes and relationships are fully loaded
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job_id).options(joinedload("*"))
    result = await db.execute(stmt)
    print_job = result.unique().scalars().one()

    await print_job_changed(print_job, EventType.UPDATED)
    return print_job


async def delete(db: AsyncSession, print_job_id: int) -> None:
    """Delete a print job object."""
    stmt = select(models.PrintJob).where(models.PrintJob.id == print_job_id).options(joinedload("*"))
    result = await db.execute(stmt)
    print_job = result.unique().scalars().first()
    if print_job is None:
        raise ItemNotFoundError(f"No print job with ID {print_job_id} found.")

    # Convert to Pydantic payload before deleting from database
    pydantic_print_job = PrintJob.from_db(print_job)

    # If it was successful, refund the weight
    if print_job.status == "successful":
        for usage in print_job.spool_usages:
            await spool.use_weight(db, usage.spool_id, -usage.weight_used)

    # Delete all print_job_spool records
    for usage in print_job.spool_usages:
        await db.delete(usage)

    await db.delete(print_job)
    await db.commit()

    await print_job_changed_payload(pydantic_print_job, EventType.DELETED)


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


async def print_job_changed_payload(payload: PrintJob, typ: EventType) -> None:
    """Notify websocket clients with a pre-constructed payload."""
    try:
        await websocket_manager.send(
            ("print_job", str(payload.id)),
            PrintJobEvent(
                type=typ,
                resource="print_job",
                date=datetime.utcnow(),
                payload=payload,
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
