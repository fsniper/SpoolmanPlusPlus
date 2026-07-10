# Analysis Report: Backend API and CRUD (Milestone 2)

This report details the investigation findings and presents a comprehensive strategy for implementing Milestone 2 of the Spoolman Printer Management project.

---

## 1. Pydantic Models for Printer and PrintJob Integration

### 1.1 Response and Event Models in `spoolman/api/v1/models.py`
We will add the response schema `Printer` and the WebSocket event wrapper `PrinterEvent` to `spoolman/api/v1/models.py` alongside other domain models:

```python
class Printer(BaseModel):
    id: int = Field(description="Unique internal ID of this printer.")
    registered: SpoolmanDateTime = Field(description="When the printer was registered in the database. UTC Timezone.")
    name: str = Field(min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
    model: str | None = Field(None, max_length=256, description="Optional printer model.", examples=["i3 MK3S"])
    location: str | None = Field(None, max_length=256, description="Optional printer location.", examples=["Lab 1"])
    comment: str | None = Field(
        None,
        max_length=1024,
        description="Optional comment.",
        examples=[""],
    )

    @staticmethod
    def from_db(item: models.Printer) -> "Printer":
        """Create a new Pydantic printer object from a database printer object."""
        return Printer(
            id=item.id,
            registered=item.registered,
            name=item.name,
            model=item.model,
            location=item.location,
            comment=item.comment,
        )


class PrinterEvent(Event):
    """Event payload for WebSocket updates."""

    payload: Printer = Field(description="Updated printer.")
    resource: Literal["printer"] = Field(description="Resource type.")
```

### 1.2 Request/Update Models in `spoolman/api/v1/models.py` (or locally in `printer.py`)
To keep consistency with other routers in the codebase (e.g. `vendor.py`, `filament.py`), request and update schemas are defined within their respective router files. If we follow this convention, they should be in `spoolman/api/v1/printer.py`. If we strictly follow the task instruction, they can be defined in `models.py`. 

```python
from pydantic import BaseModel, Field, field_validator

class PrinterParameters(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
    model: str | None = Field(None, max_length=256, description="Optional printer model.", examples=["i3 MK3S"])
    location: str | None = Field(None, max_length=256, description="Optional printer location.", examples=["Lab 1"])
    comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=[""])


class PrinterUpdateParameters(PrinterParameters):
    name: str | None = Field(None, min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])

    @field_validator("name")
    @classmethod
    def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
        """Prevent name from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v
```

### 1.3 PrintJob Model Updates
The `PrintJob` model in `spoolman/api/v1/models.py` must return `printer_id` and the nested `printer` details. We will keep `printer_name` for backward compatibility.

```python
class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered. UTC Timezone.")
    plate_id: int = Field(description="Associated plate ID.")
    status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
    start_time: SpoolmanDateTime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: SpoolmanDateTime | None = Field(None, description="End time. UTC Timezone.")
    printer_id: int | None = Field(None, description="Associated printer ID.")
    printer: Printer | None = Field(None, description="Associated printer details.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.")
    comment: str | None = Field(None, max_length=1024, description="Optional comment.")
    spool_usages: list[PrintJobSpool] = Field(default=[], description="Filament usage per spool.")

    @staticmethod
    def from_db(item: models.PrintJob) -> "PrintJob":
        return PrintJob(
            id=item.id,
            registered=item.registered,
            plate_id=item.plate_id,
            status=item.status,
            start_time=item.start_time,
            end_time=item.end_time,
            printer_id=item.printer_id,
            printer=Printer.from_db(item.printer) if item.printer is not None else None,
            printer_name=item.printer_name,
            comment=item.comment,
            spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
        )
```

And in `spoolman/api/v1/print_job.py`, update `PrintJobParameters` and `PrintJobUpdateParameters` to accept:
- `printer_id: int | None = Field(None, description="Associated printer ID.")`

---

## 2. Database CRUD Helper Routines (`spoolman/database/printer.py`)

A new module `spoolman/database/printer.py` will be created using `spoolman/database/project.py` as a reference.

```python
"""Helper functions for interacting with printer database objects."""

import logging
from datetime import datetime

import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, Printer, PrinterEvent
from spoolman.database import models
from spoolman.database.utils import (
    SortOrder,
    add_where_clause_int_in,
    add_where_clause_str,
    add_where_clause_str_opt,
)
from spoolman.exceptions import ItemDeleteError, ItemNotFoundError
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
    ids: list[int] | None = None,
    name: str | None = None,
    model: str | None = None,
    location: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Printer], int]:
    """Find a list of printer objects by search criteria.

    Returns a tuple containing the list of items and the total count of matching items.
    """
    stmt = select(models.Printer)

    stmt = add_where_clause_int_in(stmt, models.Printer.id, ids)
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
        raise ItemDeleteError("Cannot delete printer because it is associated with print jobs.") from e
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
```

---

## 3. WebSocket Notifications
WebSockets will be driven via the `websocket_manager.send` utility already in place inside `spoolman/ws.py`.
- WS pool for general changes: `("printer",)`
- WS pool for specific printer changes: `("printer", str(printer_id))`
- Handled natively by `printer_changed` inside `spoolman/database/printer.py` on mutated states (`EventType.ADDED`, `EventType.UPDATED`, `EventType.DELETED`).

---

## 4. REST API Router (`spoolman/api/v1/printer.py`)

We will implement the REST API router in `spoolman/api/v1/printer.py`:

```python
"""Printer related endpoints."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Printer, PrinterEvent
from spoolman.database import printer
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager
# Assuming schemas are in printer.py (local parameters) or models.py (import from models):
from .models import PrinterParameters, PrinterUpdateParameters

router = APIRouter(
    prefix="/printer",
    tags=["printer"],
)

logger = logging.getLogger(__name__)

# D103: Missing docstring in public function (ignored in routers via noqa)
# ruff: noqa: D103


@router.get(
    "",
    name="Find printer",
    description="Get a list of printers that matches the search query.",
    response_model_exclude_none=True,
    responses={
        200: {"model": list[Printer]},
        299: {"model": PrinterEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    name: Annotated[str | None, Query(title="Printer Name", description="Partial search term.")] = None,
    model: Annotated[str | None, Query(title="Printer Model", description="Partial search term.")] = None,
    location: Annotated[str | None, Query(title="Printer Location", description="Partial search term.")] = None,
    sort: Annotated[str | None, Query(title="Sort field:dir")] = None,
    limit: Annotated[int | None, Query(title="Limit")] = None,
    offset: Annotated[int, Query(title="Offset")] = 0,
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
    description="Get a specific printer.",
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
    description="Add a new printer.",
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
    description="Update any attribute of a printer.",
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
```

---

## 5. Router Registration in `spoolman/api/v1/router.py`

Registration requires two lines in `spoolman/api/v1/router.py`:
1. Include `printer` in the v1 imports (line 18):
   ```python
   from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job, printer
   ```
2. Include the router at the end of the file (line 119):
   ```python
   app.include_router(printer.router)
   ```

---

## 6. PrintJob Integration Details (`spoolman/database/print_job.py`)

Ensure that `spoolman/database/print_job.py` imports `printer` database helpers:
```python
from spoolman.database import models, plate, spool, printer
```

Modify `create` and `update` logic:
- Inside `create`:
  ```python
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
  ```
- Inside `update`:
  ```python
  if "printer_id" in data:
      printer_id_val = data.pop("printer_id")
      if printer_id_val is None:
          print_job.printer = None
      else:
          print_job.printer = await printer.get_by_id(db, printer_id_val)
  elif "printer_name" in data:
      # (Existing printer_name resolution fallback)
  ```

This allows new API clients to use `printer_id` directly, while old clients sending `printer_name` are fully supported via auto-creation/lookup.

---

## 7. Integration Tests Strategy (`tests_integration/`)

### 7.1 Setup Fixtures in `tests_integration/tests/conftest.py`
Add context manager and fixture for printer creation:
```python
@contextmanager
def random_printer_impl():
    """Return a random printer."""
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={
            "name": "Prusa i3 MK3S",
            "model": "i3 MK3S",
            "location": "Lab 1",
            "comment": "Nice printer",
        },
    )
    result.raise_for_status()

    printer: dict[str, Any] = result.json()
    yield printer

    httpx.delete(f"{URL}/api/v1/printer/{printer['id']}").raise_for_status()

@pytest.fixture
def random_printer():
    """Return a random printer."""
    with random_printer_impl() as printer:
        yield printer
```

### 7.2 Implement `tests_integration/tests/printer/test_crud.py`
Verify CRUD, search query params, and websocket notifications on mutations.

### 7.3 Implement `tests_integration/tests/print_job/test_printer_relation.py`
1. Create a print job referencing a printer via `printer_id`.
2. Retrieve the print job and verify `printer_id` and the full `printer` details dictionary are returned.
3. Test compatibility by posting with `printer_name` and asserting that the backend auto-creates the printer entity.
