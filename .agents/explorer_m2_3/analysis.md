# Analysis Report: Backend API and CRUD for Printer (Milestone 2)

## Executive Summary
This analysis details the implementation strategy for Milestone 2, which introduces the `Printer` entity into the Spoolman REST API, database helper layer, WebSocket server, and integration test suite. Additionally, the existing `PrintJob` model is integrated with the new `Printer` entity, providing support for both `printer_id` references and legacy `printer_name` lookups/updates.

---

## 1. Pydantic Models (`spoolman/api/v1/models.py`)

### Existing Conventions
- **Entity Models**: Defined in `spoolman/api/v1/models.py` (e.g., `Vendor`, `Filament`, `Spool`). They inherit from `pydantic.BaseModel` and map raw SQLAlchemy entities to serialized models using a static `from_db` method.
- **Input Parameters**: Usually defined in the router file (e.g., `VendorParameters` in `vendor.py`, `ProjectParameters` in `project.py`) to keep validation and endpoints localized.
- **Events**: Defined in `spoolman/api/v1/models.py` subclassing `Event` with a `resource` Literal and a typed `payload` field (e.g., `ProjectEvent`).

### Recommended Implementation
We recommend defining:
1. `Printer` and `PrinterEvent` in `spoolman/api/v1/models.py` to match the exact pattern of existing entities.
2. `PrinterParameters` and `PrinterUpdateParameters` in `spoolman/api/v1/printer.py` to keep endpoint models aligned with project conventions (e.g. `ProjectParameters` in `project.py`). *Alternatively, they can be defined directly in `models.py` if strict adherence to SCOPE.md layout is preferred.*

#### Proposed Pydantic Snippets

**In `spoolman/api/v1/models.py`:**
```python
class Printer(BaseModel):
    id: int = Field(description="Unique internal ID of this printer.")
    registered: SpoolmanDateTime = Field(description="When the printer was registered in the database. UTC Timezone.")
    name: str = Field(max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
    model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK3S"])
    location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Lab 1"])
    comment: str | None = Field(None, max_length=1024, description="Free text comment about this printer.", examples=[""])

    @staticmethod
    def from_db(item: models.Printer) -> "Printer":
        """Create a Pydantic Printer object from a database model."""
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

**In `spoolman/api/v1/printer.py`:**
```python
from pydantic import BaseModel, Field, field_validator

class PrinterParameters(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
    model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK3S"])
    location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Lab 1"])
    comment: str | None = Field(None, max_length=1024, description="Free text comment about this printer.", examples=[""])


class PrinterUpdateParameters(PrinterParameters):
    name: str | None = Field(None, min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])

    @field_validator("name")
    @classmethod
    def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
        """Prevent name from being updated to None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v
```

---

## 2. DB CRUD Helper Routines (`spoolman/database/printer.py`)

A new module `spoolman/database/printer.py` needs to be created to implement basic CRUD functions.

### Query and Search Filters
The `find` function should allow partial, case-insensitive, or exact string matching via standard utils.
- `name` is a non-nullable string: use `add_where_clause_str`.
- `model` is an optional string: use `add_where_clause_str_opt`.
- `location` is an optional string: use `add_where_clause_str_opt`.

### Proposed DB CRUD Implementation
```python
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
    """Get a printer object from the database by its unique ID."""
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
```

---

## 3. WebSocket Notifications

The `printer_changed` utility triggers WebSocket notifications on mutations (`ADDED`, `UPDATED`, `DELETED`) by publishing to the subscription pool using `websocket_manager.send`.
- Specific subscriptions listen to `("printer", str(printer_id))`.
- General subscriptions listen to `("printer",)`.
This aligns directly with existing event propagation logic in Spoolman (e.g. `spool.py`, `project.py`).

---

## 4. REST API Router (`spoolman/api/v1/printer.py`)

A new REST router module `spoolman/api/v1/printer.py` must support basic REST operations and WebSocket streams.

### Endpoints
- `GET /api/v1/printer` - Searches for printers matching criteria (with limit, offset, and sort).
- `WEBSOCKET /api/v1/printer` - Connects to general changes stream.
- `POST /api/v1/printer` - Creates a new printer.
- `GET /api/v1/printer/{printer_id}` - Retrieves a printer.
- `WEBSOCKET /api/v1/printer/{printer_id}` - Connects to printer-specific changes stream.
- `PATCH /api/v1/printer/{printer_id}` - Updates printer fields.
- `DELETE /api/v1/printer/{printer_id}` - Deletes a printer (raises 400 Bad Request on integrity errors).

#### Proposed Router Implementation
```python
"""Printer related endpoints."""

import asyncio
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
# Assuming PrinterParameters & PrinterUpdateParameters are defined locally or imported
from .models import PrinterParameters, PrinterUpdateParameters

router = APIRouter(
    prefix="/printer",
    tags=["printer"],
)

# ruff: noqa: D103


@router.get(
    "",
    name="Find printer",
    description=(
        "Get a list of printers that match the search query. "
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
    name: Annotated[str | None, Query(title="Printer Name", description="Partial match for printer name.")] = None,
    model: Annotated[str | None, Query(title="Printer Model", description="Partial match for printer model.")] = None,
    location: Annotated[str | None, Query(title="Printer Location", description="Partial match for printer location.")] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description='Sort results by given field: e.g. "name:asc,id:desc".',
            examples=["name:asc,id:desc"],
        ),
    ] = None,
    limit: Annotated[int | None, Query(title="Limit", description="Maximum number of items.")] = None,
    offset: Annotated[int, Query(title="Offset", description="Offset.")] = 0,
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
async def notify_any(websocket: WebSocket) -> None:
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
async def notify(websocket: WebSocket, printer_id: int) -> None:
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
```

---

## 5. Router Registration (`spoolman/api/v1/router.py`)

The new printer router needs to be registered with the FastAPI application.

1. **Import** the module in `spoolman/api/v1/router.py`:
   ```python
   from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job, printer
   ```
2. **Register** the router at the end of the file:
   ```python
   app.include_router(printer.router)
   ```

---

## 6. PrintJob Integration & Schema Relationship

In Milestone 1, the `printer_name` column was removed and replaced with a nullable foreign key `printer_id` pointing to the `printer` table. To preserve backwards compatibility and expose the new relationship:
1. The REST API needs to support receiving both `printer_id` and `printer_name` in write/create calls.
2. The print job details payload returned by the server should contain `printer_id`, nested `printer` details, and the computed dynamic `printer_name` field.

### API/Model Integration (`spoolman/api/v1/models.py`)
Update the `PrintJob` model:
```python
class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered. UTC Timezone.")
    plate_id: int = Field(description="Associated plate ID.")
    status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
    start_time: SpoolmanDateTime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: SpoolmanDateTime | None = Field(None, description="End time. UTC Timezone.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.") # dynamic fallback
    printer_id: int | None = Field(None, description="Associated printer ID.")
    printer: Printer | None = Field(None, description="Associated printer details.")
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
            printer_name=item.printer_name,
            printer_id=item.printer_id,
            printer=Printer.from_db(item.printer) if item.printer is not None else None,
            comment=item.comment,
            spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
        )
```

### DB Layer Integration (`spoolman/database/print_job.py`)

#### Update `create` and `update` logic:
- Add support for resolving printer via `printer_id` first.
- Fall back to checking `printer_name` (looking up or dynamically creating the printer by name, preserving existing fallback behavior).

#### Updates in `find` logic:
- Support searching and filtering by `printer_id` using `add_where_clause_int_opt(stmt, models.PrintJob.printer_id, printer_id)`.

---

## 7. Integration Tests (`tests_integration/`)

Integration tests are run via the orchestrating python runner:
```bash
python tests_integration/run.py
```
This builds docker containers for the app and the tester, executing compose targets (`postgres`, `sqlite`, `mariadb`, `cockroachdb`).

### Recommended Test Additions
We should introduce new tests verifying printer operations.

#### A. conftest.py Updates
Define standard random printer fixtures:
```python
@contextmanager
def random_printer_impl():
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={
            "name": "Fixture Printer",
            "model": "MK3S+",
            "location": "Shelf A",
            "comment": "Fixture comments",
        },
    )
    result.raise_for_status()
    printer = result.json()
    yield printer
    httpx.delete(f"{URL}/api/v1/printer/{printer['id']}").raise_for_status()


@pytest.fixture
def random_printer():
    with random_printer_impl() as printer:
        yield printer
```

#### B. New File: `tests_integration/tests/printer/test_crud.py`
Verify CRUD operations:
- `test_create_printer`
- `test_get_printer`
- `test_list_printers`
- `test_patch_printer`
- `test_delete_printer`

#### C. Updates in `tests_integration/tests/print_job/test_crud.py`
Verify new associations:
1. `test_create_print_job_with_printer_id`: Create print job using `printer_id`. Verify it returns correct `printer_id`, nested `printer` details, and matches `printer_name`.
2. `test_delete_printer_with_print_job`: Verify attempting to delete a printer that has print jobs fails with `400 Bad Request` due to integrity constraints.
3. `test_create_print_job_with_printer_name`: Verify that passing only `printer_name` successfully executes name-based dynamic lookup/creation and prints returned.
