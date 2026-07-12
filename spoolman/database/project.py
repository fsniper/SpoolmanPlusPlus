"""Helper functions for interacting with project database objects."""

import logging
from datetime import datetime, timezone

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, Project, ProjectEvent
from spoolman.database import models
from spoolman.database.utils import SortOrder, add_where_clause_str
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    name: str,
    description: str | None = None,
    link: str | None = None,
) -> models.Project:
    """Add a new project to the database."""
    project = models.Project(
        name=name,
        registered=datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0),
        description=description,
        link=link,
    )
    db.add(project)
    await db.commit()
    await project_changed(project, EventType.ADDED)
    return project


async def get_by_id(db: AsyncSession, project_id: int) -> models.Project:
    """Get a project object from the database by the unique ID."""
    project = await db.get(models.Project, project_id)
    if project is None:
        raise ItemNotFoundError(f"No project with ID {project_id} found.")
    return project


async def find(
    *,
    db: AsyncSession,
    name: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Project], int]:
    """Find a list of project objects by search criteria.

    Returns a tuple containing the list of items and the total count of matching items.
    """
    stmt = select(models.Project)

    stmt = add_where_clause_str(stmt, models.Project.name, name)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            field = getattr(models.Project, fieldstr)
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
    project_id: int,
    data: dict,
) -> models.Project:
    """Update the fields of a project object."""
    project = await get_by_id(db, project_id)
    for k, v in data.items():
        setattr(project, k, v)
    await db.commit()
    await project_changed(project, EventType.UPDATED)
    return project


async def delete(db: AsyncSession, project_id: int) -> None:
    """Delete a project object."""
    project = await get_by_id(db, project_id)
    await db.delete(project)
    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError as e:
        await db.rollback()
        raise ItemDeleteError("Cannot delete project because it has associated plates.") from e
    await project_changed(project, EventType.DELETED)


async def project_changed(project: models.Project, typ: EventType) -> None:
    """Notify websocket clients that a project has changed."""
    try:
        await websocket_manager.send(
            ("project", str(project.id)),
            ProjectEvent(
                type=typ,
                resource="project",
                date=datetime.now(timezone.utc),
                payload=Project.from_db(project),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
