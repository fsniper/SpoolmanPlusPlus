"""Project File related endpoints."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, UploadFile, Form, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from spoolman.api.v1.models import ProjectFile
from spoolman.database import database, project_file
from spoolman.exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/project/{project_id}/file",
    tags=["project_file"],
)


@router.post(
    "",
    description="Upload a new file to a project.",
    response_model=ProjectFile,
)
async def upload_file(
    project_id: int,
    file: Annotated[UploadFile, File(...)],
    name: Annotated[Optional[str], Form()] = None,
    db: AsyncSession = Depends(database.get_db_session),
) -> ProjectFile:
    db_item = await project_file.create(
        db=db,
        project_id=project_id,
        file=file,
        name=name,
    )
    return ProjectFile.from_db(db_item)


@router.post(
    "/link",
    description="Link an existing plate to a project as a file.",
    response_model=ProjectFile,
)
async def link_file(
    project_id: int,
    plate_id: Annotated[int, Form(...)],
    name: Annotated[Optional[str], Form()] = None,
    db: AsyncSession = Depends(database.get_db_session),
) -> ProjectFile:
    db_item = await project_file.create(
        db=db,
        project_id=project_id,
        plate_id=plate_id,
        name=name,
    )
    return ProjectFile.from_db(db_item)


@router.get(
    "",
    description="Get all files for a project.",
    response_model=list[ProjectFile],
)
async def get_files(
    project_id: int,
    db: AsyncSession = Depends(database.get_db_session),
) -> list[ProjectFile]:
    db_items = await project_file.find(db=db, project_id=project_id)
    return [ProjectFile.from_db(item) for item in db_items]


@router.get(
    "/{file_id}",
    description="Get a specific project file.",
    response_model=ProjectFile,
)
async def get_file(
    project_id: int,
    file_id: int,
    db: AsyncSession = Depends(database.get_db_session),
) -> ProjectFile:
    db_item = await project_file.get_by_id(db, file_id)
    if db_item.project_id != project_id:
        raise HTTPException(status_code=404, detail="File does not belong to this project")
    return ProjectFile.from_db(db_item)


@router.get(
    "/{file_id}/download",
    description="Download a specific project file.",
)
async def download_file(
    project_id: int,
    file_id: int,
    db: AsyncSession = Depends(database.get_db_session),
) -> FileResponse:
    db_item = await project_file.get_by_id(db, file_id)
    if db_item.project_id != project_id:
        raise HTTPException(status_code=404, detail="File does not belong to this project")
    
    if not db_item.file_path:
        raise HTTPException(status_code=404, detail="File path is not set for this file")

    file_path = Path(db_item.file_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Physical file not found on disk")

    return FileResponse(path=file_path, filename=db_item.name)


@router.delete(
    "/{file_id}",
    description="Delete a project file.",
)
async def delete_file(
    project_id: int,
    file_id: int,
    db: AsyncSession = Depends(database.get_db_session),
) -> dict:
    db_item = await project_file.get_by_id(db, file_id)
    if db_item.project_id != project_id:
        raise HTTPException(status_code=404, detail="File does not belong to this project")

    await project_file.delete(db, file_id)
    return {"message": "File deleted"}
