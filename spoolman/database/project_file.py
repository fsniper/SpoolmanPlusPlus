"""Helper functions for interacting with project file database objects."""

import logging
from datetime import datetime, timezone
import os
import shutil
from typing import Optional
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from spoolman.api.v1.models import EventType, ProjectFileEvent
from spoolman.database import models, project, plate
from spoolman.env import get_data_dir
from spoolman.exceptions import ItemNotFoundError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


def get_uploads_dir() -> Path:
    """Get the uploads directory."""
    path = get_data_dir().joinpath("uploads")
    path.mkdir(parents=True, exist_ok=True)
    return path


async def create(
    *,
    db: AsyncSession,
    project_id: int,
    file: Optional[UploadFile] = None,
    name: Optional[str] = None,
    plate_id: Optional[int] = None,
) -> models.ProjectFile:
    """Add a new project file to the database."""
    # Verify project exists
    await project.get_by_id(db, project_id)

    db_item = models.ProjectFile(
        registered=datetime.now(tz=timezone.utc).replace(microsecond=0, tzinfo=None),
        project_id=project_id,
        name=name or "",
    )

    if plate_id is not None:
        db_plate = await plate.get_by_id(db, plate_id)
        db_item.plate_id = plate_id
        db_item.file_path = db_plate.file_path
        if not name:
            db_item.name = f"Linked from Plate: {db_plate.name}"
    elif file is not None:
        if not name:
            db_item.name = file.filename or "unknown_file"

        uploads_dir = get_uploads_dir()
        file_path = uploads_dir.joinpath(f"project_{project_id}_{db_item.name}")
        
        # Save the file physically
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        db_item.file_path = str(file_path)
        db_item.size = file_path.stat().st_size
    else:
        raise ValueError("Either file or plate_id must be provided")

    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)

    await websocket_manager.send(
        ("project_file", str(db_item.id)),
        ProjectFileEvent(
            type=EventType.ADDED,
            resource="project_file",
            payload=db_item,
            date=datetime.now(tz=timezone.utc),
        ),
    )

    return db_item


async def get_by_id(db: AsyncSession, file_id: int) -> models.ProjectFile:
    """Get a project file object from the database by the unique ID."""
    db_item = await db.get(models.ProjectFile, file_id)
    if db_item is None:
        raise ItemNotFoundError(f"No project file with ID {file_id} found.")
    return db_item


async def find(
    *,
    db: AsyncSession,
    project_id: Optional[int] = None,
) -> list[models.ProjectFile]:
    """Find a list of project files by search criteria."""
    stmt = select(models.ProjectFile)
    if project_id is not None:
        stmt = stmt.where(models.ProjectFile.project_id == project_id)

    stmt = stmt.order_by(models.ProjectFile.id.asc())
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def delete(db: AsyncSession, file_id: int) -> None:
    """Delete a project file object from the database."""
    db_item = await get_by_id(db, file_id)
    
    # Try to delete physical file if it exists in uploads dir
    if db_item.file_path and db_item.plate_id is None:
        file_path = Path(db_item.file_path)
        if file_path.exists() and str(get_uploads_dir()) in str(file_path):
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete physical file {file_path}: {e}")

    await db.delete(db_item)
    await db.commit()

    await websocket_manager.send(
        ("project_file", str(db_item.id)),
        ProjectFileEvent(
            type=EventType.DELETED,
            resource="project_file",
            payload=db_item,
            date=datetime.now(tz=timezone.utc),
        ),
    )
