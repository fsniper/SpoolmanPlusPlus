"""Printer related endpoints."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Printer, PrinterEvent
from spoolman.database import printer
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/printer",
    tags=["printer"],
)

# ruff: noqa: D103


class PrinterParameters(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
    model: str | None = Field(
        None,
        max_length=256,
        description="Optional printer model.",
        examples=["MK3S"],
    )
    location: str | None = Field(
        None,
        max_length=256,
        description="Optional printer location.",
        examples=["Lab 1"],
    )
    comment: str | None = Field(
        None,
        max_length=1024,
        description="Optional comment.",
        examples=["Needs calibration."],
    )


class PrinterUpdateParameters(PrinterParameters):
    name: str | None = Field(None, min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])

    @field_validator("name")
    @classmethod
    def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
        """Prevent name from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v


@router.get(
    "",
    name="Find printer",
    description=(
        "Get a list of printers that matches the search query. "
        "A websocket is served on the same path to listen for updates to any printer, or added or deleted printers. "
        "See the HTTP Response code 299 for the content of the websocket messages."
    ),
    response_model_exclude_none=True,
    responses={
        200: {"model": list[Printer]},
        299: {"model": PrinterEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    name: Annotated[
        str | None,
        Query(
            title="Printer Name",
            description=(
                "Partial case-insensitive search term for the printer name. Separate multiple terms with a comma. "
                "Surround a term with quotes to search for the exact term."
            ),
        ),
    ] = None,
    model: Annotated[
        str | None,
        Query(
            title="Printer Model",
            description=(
                "Partial case-insensitive search term for the printer model. Separate multiple terms with a comma. "
                "Surround a term with quotes to search for the exact term."
            ),
        ),
    ] = None,
    location: Annotated[
        str | None,
        Query(
            title="Printer Location",
            description=(
                "Partial case-insensitive search term for the printer location. Separate multiple terms with a comma. "
                "Surround a term with quotes to search for the exact term."
            ),
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description=(
                'Sort the results by the given field. Should be a comma-separate string with "field:direction" items.'
            ),
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
        db_items, total_count = await printer.find(
            db=db,
            name=name,
            model=model,
            location=location,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())

    return JSONResponse(
        content=jsonable_encoder(
            (Printer.from_db(db_item) for db_item in db_items),
            exclude_none=True,
        ),
        headers={"x-total-count": str(total_count)},
    )


@router.websocket(
    "",
    name="Listen to printer changes",
)
async def notify_any(
    websocket: WebSocket,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("printer",), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("printer",), websocket)


@router.get(
    "/{printer_id}",
    name="Get printer",
    description=(
        "Get a specific printer. A websocket is served on the same path to listen for changes to the printer. "
        "See the HTTP Response code 299 for the content of the websocket messages."
    ),
    response_model_exclude_none=True,
    responses={404: {"model": Message}, 299: {"model": PrinterEvent, "description": "Websocket message"}},
)
async def get(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    printer_id: int,
) -> Printer:
    db_item = await printer.get_by_id(db, printer_id)
    return Printer.from_db(db_item)


@router.websocket(
    "/{printer_id}",
    name="Listen to printer changes",
)
async def notify(
    websocket: WebSocket,
    printer_id: int,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("printer", str(printer_id)), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("printer", str(printer_id)), websocket)


@router.post(
    "",
    name="Add printer",
    description="Add a new printer to the database.",
    response_model_exclude_none=True,
    response_model=Printer,
    responses={400: {"model": Message}},
)
async def create(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: PrinterParameters,
):
    db_item = await printer.create(
        db=db,
        name=body.name,
        model=body.model,
        location=body.location,
        comment=body.comment,
    )
    return Printer.from_db(db_item)


@router.patch(
    "/{printer_id}",
    name="Update printer",
    description="Update any attribute of a printer. Only fields specified in the request will be affected.",
    response_model_exclude_none=True,
    response_model=Printer,
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def update(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    printer_id: int,
    body: PrinterUpdateParameters,
):
    patch_data = body.model_dump(exclude_unset=True)
    db_item = await printer.update(
        db=db,
        printer_id=printer_id,
        data=patch_data,
    )
    return Printer.from_db(db_item)


@router.delete(
    "/{printer_id}",
    name="Delete printer",
    description="Delete a printer.",
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    printer_id: int,
) -> Message:
    try:
        await printer.delete(db, printer_id)
    except ItemDeleteError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())
    return Message(message="Success!")
