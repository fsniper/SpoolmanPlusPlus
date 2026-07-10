"""Print job related endpoints."""

import asyncio
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, PrintJob, PrintJobEvent
from spoolman.database import print_job
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/print_job",
    tags=["print_job"],
)

# ruff: noqa: D103


class PrintJobSpoolParameters(BaseModel):
    spool_id: int = Field(description="Spool ID.")
    weight_used: float = Field(ge=0, description="Weight used from this spool in grams.")


class PrintJobParameters(BaseModel):
    plate_id: int = Field(description="Associated plate ID.")
    status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
    start_time: datetime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: datetime | None = Field(None, description="End time. UTC Timezone.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.")
    printer_id: int | None = Field(None, description="Printer ID.")
    comment: str | None = Field(None, max_length=1024, description="Optional comment.")
    spool_usages: list[PrintJobSpoolParameters] = Field(default=[], description="Filament usage per spool.")

    @model_validator(mode="after")
    def validate_times(self) -> "PrintJobParameters":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must be after or equal to start_time")
        return self


class PrintJobUpdateParameters(BaseModel):
    plate_id: int | None = Field(None, description="Associated plate ID.")
    status: str | None = Field(None, max_length=64, description="Status of the print job.")
    start_time: datetime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: datetime | None = Field(None, description="End time. UTC Timezone.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.")
    printer_id: int | None = Field(None, description="Printer ID.")
    comment: str | None = Field(None, max_length=1024, description="Optional comment.")
    spool_usages: list[PrintJobSpoolParameters] | None = Field(None, description="Filament usage per spool.")

    @model_validator(mode="after")
    def validate_times(self) -> "PrintJobUpdateParameters":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must be after or equal to start_time")
        return self


@router.get(
    "",
    name="Find print job",
    description=(
        "Get a list of print jobs that matches the search query. "
        "A websocket is served on the same path to listen for updates to any print job, or added or deleted print jobs. "
        "See the HTTP Response code 299 for the content of the websocket messages."
    ),
    response_model_exclude_none=True,
    responses={
        200: {"model": list[PrintJob]},
        299: {"model": PrintJobEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    plate_id: Annotated[
        int | None,
        Query(
            title="Plate ID",
            description="Filter by plate ID.",
        ),
    ] = None,
    status: Annotated[
        str | None,
        Query(
            title="Status",
            description="Filter by print job status.",
        ),
    ] = None,
    printer_id: Annotated[
        int | None,
        Query(
            title="Printer ID",
            description="Filter by printer ID.",
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description=(
                'Sort the results by the given field. Should be a comma-separate string with "field:direction" items.'
            ),
            examples=["status:asc,id:desc"],
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
        db_items, total_count = await print_job.find(
            db=db,
            plate_id=plate_id,
            status=status,
            printer_id=printer_id,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())

    return JSONResponse(
        content=jsonable_encoder(
            (PrintJob.from_db(db_item) for db_item in db_items),
            exclude_none=True,
        ),
        headers={"x-total-count": str(total_count)},
    )


@router.websocket(
    "",
    name="Listen to print job changes",
)
async def notify_any(
    websocket: WebSocket,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("print_job",), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("print_job",), websocket)


@router.get(
    "/{print_job_id}",
    name="Get print job",
    description=(
        "Get a specific print job. A websocket is served on the same path to listen for changes to the print job. "
        "See the HTTP Response code 299 for the content of the websocket messages."
    ),
    response_model_exclude_none=True,
    responses={404: {"model": Message}, 299: {"model": PrintJobEvent, "description": "Websocket message"}},
)
async def get(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    print_job_id: int,
) -> PrintJob:
    db_item = await print_job.get_by_id(db, print_job_id)
    return PrintJob.from_db(db_item)


@router.websocket(
    "/{print_job_id}",
    name="Listen to print job changes",
)
async def notify(
    websocket: WebSocket,
    print_job_id: int,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("print_job", str(print_job_id)), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("print_job", str(print_job_id)), websocket)


@router.post(
    "",
    name="Add print job",
    description="Add a new print job to the database.",
    response_model_exclude_none=True,
    response_model=PrintJob,
    responses={400: {"model": Message}},
)
async def create(  # noqa: ANN201
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: PrintJobParameters,
):
    try:
        db_item = await print_job.create(
            db=db,
            plate_id=body.plate_id,
            status=body.status,
            start_time=body.start_time,
            end_time=body.end_time,
            printer_name=body.printer_name,
            printer_id=body.printer_id,
            comment=body.comment,
            spool_usages=[u.model_dump() for u in body.spool_usages],
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())
    return PrintJob.from_db(db_item)


@router.patch(
    "/{print_job_id}",
    name="Update print job",
    description="Update any attribute of a print job. Only fields specified in the request will be affected.",
    response_model_exclude_none=True,
    response_model=PrintJob,
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def update(  # noqa: ANN201
    db: Annotated[AsyncSession, Depends(get_db_session)],
    print_job_id: int,
    body: PrintJobUpdateParameters,
):
    patch_data = body.model_dump(exclude_unset=True)
    if "spool_usages" in patch_data and patch_data["spool_usages"] is not None:
        patch_data["spool_usages"] = [u.model_dump() for u in body.spool_usages]

    try:
        db_item = await print_job.update(
            db=db,
            print_job_id=print_job_id,
            data=patch_data,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())
    return PrintJob.from_db(db_item)


@router.delete(
    "/{print_job_id}",
    name="Delete print job",
    description="Delete a print job.",
    responses={404: {"model": Message}},
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    print_job_id: int,
) -> Message:
    await print_job.delete(db, print_job_id)
    return Message(message="Success!")
