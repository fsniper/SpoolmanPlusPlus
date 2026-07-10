"""Plate related endpoints."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Plate, PlateEvent, EventType
from spoolman.database import plate
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/plate",
    tags=["plate"],
)


class PlateParameters(BaseModel):
    project_id: int = Field(description="The ID of the project this plate belongs to.")
    name: str = Field(min_length=1, max_length=256, description="Plate name.", examples=["Spec Plate"])
    file_path: str | None = Field(
        None,
        max_length=1024,
        description="G-code file path of the plate.",
        examples=["test.gcode"],
    )
    estimated_weight: float | None = Field(
        None,
        ge=0.0,
        description="Estimated weight of filament used by this plate, in grams.",
        examples=[50.0],
    )
    estimated_time: int | None = Field(
        None,
        ge=0,
        description="Estimated print time in seconds.",
        examples=[3600],
    )
    comment: str | None = Field(
        None,
        max_length=1024,
        description="Free text comment about this plate.",
        examples=["Nice plate"],
    )


class PlateUpdateParameters(PlateParameters):
    project_id: int | None = Field(None, description="The ID of the project this plate belongs to.")
    name: str | None = Field(None, min_length=1, max_length=256, description="Plate name.", examples=["Spec Plate"])

    @field_validator("name", "project_id")
    @classmethod
    def prevent_none(cls, v):
        """Prevent name and project_id from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v


@router.get(
    "",
    name="Find plate",
    description="Get a list of plates that matches the search query.",
    response_model_exclude_none=True,
    responses={
        200: {"model": list[Plate]},
        299: {"model": PlateEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: Annotated[
        int | None,
        Query(
            title="Project ID",
            description="Match an exact project ID.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        Query(
            title="Plate Name",
            description="Partial case-insensitive search term for the plate name. Separate multiple terms with a comma.",
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description='Sort the results by the given field. Should be a comma-separate string with "field:direction" items.',
            examples=["name:asc,id:desc"],
        ),
    ] = None,
    limit: Annotated[
        int | None,
        Query(title="Limit", description="Maximum number of items in the response."),
    ] = None,
    offset: Annotated[int, Query(title="Offset", description="Offset in the full result set if a limit is set.")] = 0,
) -> JSONResponse:
    sort_by: dict[str, SortOrder] = {}
    if sort is not None:
        for sort_item in sort.split(","):
            field, direction = sort_item.split(":")
            sort_by[field] = SortOrder[direction.upper()]

    try:
        db_items, total_count = await plate.find(
            db=db,
            project_id=project_id,
            name=name,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())

    return JSONResponse(
        content=jsonable_encoder(
            (Plate.from_db(db_item) for db_item in db_items),
            exclude_none=True,
        ),
        headers={"x-total-count": str(total_count)},
    )


@router.websocket(
    "",
    name="Listen to plate changes",
)
async def notify_any(
    websocket: WebSocket,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("plate",), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("plate",), websocket)


@router.get(
    "/{plate_id}",
    name="Get plate",
    description="Get a specific plate.",
    response_model_exclude_none=True,
    responses={404: {"model": Message}, 299: {"model": PlateEvent, "description": "Websocket message"}},
)
async def get(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    plate_id: int,
) -> Plate:
    db_item = await plate.get_by_id(db, plate_id)
    return Plate.from_db(db_item)


@router.websocket(
    "/{plate_id}",
    name="Listen to plate changes",
)
async def notify(
    websocket: WebSocket,
    plate_id: int,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("plate", str(plate_id)), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("plate", str(plate_id)), websocket)


@router.post(
    "",
    name="Add plate",
    description="Add a new plate to the database.",
    response_model_exclude_none=True,
    response_model=Plate,
    responses={400: {"model": Message}},
)
async def create(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: PlateParameters,
):
    db_item = await plate.create(
        db=db,
        project_id=body.project_id,
        name=body.name,
        file_path=body.file_path,
        estimated_weight=body.estimated_weight,
        estimated_time=body.estimated_time,
        comment=body.comment,
    )
    return Plate.from_db(db_item)


@router.patch(
    "/{plate_id}",
    name="Update plate",
    description="Update any attribute of a plate. Only fields specified in the request will be affected.",
    response_model_exclude_none=True,
    response_model=Plate,
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def update(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    plate_id: int,
    body: PlateUpdateParameters,
):
    patch_data = body.model_dump(exclude_unset=True)
    db_item = await plate.update(
        db=db,
        plate_id=plate_id,
        data=patch_data,
    )
    return Plate.from_db(db_item)


@router.delete(
    "/{plate_id}",
    name="Delete plate",
    description="Delete a plate. Fails if the plate has associated print jobs.",
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    plate_id: int,
) -> Message:
    try:
        await plate.delete(db, plate_id)
    except ItemDeleteError:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to delete plate, it may have associated print jobs."},
        )
    return Message(message="Success!")
