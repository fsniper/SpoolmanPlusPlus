"""Helper functions for interacting with printer database objects."""

import logging
from datetime import datetime

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, Printer, PrinterEvent
from spoolman.database import models
from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_str_opt
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    name: str,
    model: str | None = None,
    location: str | None = None,
    comment: str | None = None,
) -> models.Printer:
    """Add a new printer to the database."""
    printer = models.Printer(
        name=name,
        registered=datetime.utcnow().replace(microsecond=0),
        model=model,
        location=location,
        comment=comment,
    )
    db.add(printer)
    await db.commit()
    await printer_changed(printer, EventType.ADDED)
    return printer


async def get_by_id(db: AsyncSession, printer_id: int) -> models.Printer:
    """Get a printer object from the database by the unique ID."""
    printer = await db.get(models.Printer, printer_id)
    if printer is None:
        raise ItemNotFoundError(f"No printer with ID {printer_id} found.")
    return printer


async def find(
    *,
    db: AsyncSession,
    name: str | None = None,
    model: str | None = None,
    location: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Printer], int]:
    """Find a list of printer objects by search criteria."""
    stmt = select(models.Printer)

    stmt = add_where_clause_str(stmt, models.Printer.name, name)
    stmt = add_where_clause_str_opt(stmt, models.Printer.model, model)
    stmt = add_where_clause_str_opt(stmt, models.Printer.location, location)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            field = getattr(models.Printer, fieldstr)
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
    printer_id: int,
    data: dict,
) -> models.Printer:
    """Update the fields of a printer object."""
    printer = await get_by_id(db, printer_id)
    for k, v in data.items():
        setattr(printer, k, v)
    await db.commit()
    await printer_changed(printer, EventType.UPDATED)
    return printer


async def delete(db: AsyncSession, printer_id: int) -> None:
    """Delete a printer object."""
    printer = await get_by_id(db, printer_id)
    await db.delete(printer)
    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError as e:
        await db.rollback()
        raise ItemDeleteError("Cannot delete printer because it has associated print jobs.") from e
    await printer_changed(printer, EventType.DELETED)


async def printer_changed(printer: models.Printer, typ: EventType) -> None:
    """Notify websocket clients that a printer has changed."""
    try:
        await websocket_manager.send(
            ("printer", str(printer.id)),
            PrinterEvent(
                type=typ,
                resource="printer",
                date=datetime.utcnow(),
                payload=Printer.from_db(printer),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
