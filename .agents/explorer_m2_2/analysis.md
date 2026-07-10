# Milestone 2 Analysis: Backend API and CRUD for Printer

This report outlines the codebase investigation and the recommended implementation strategy for Milestone 2 (Backend API and CRUD) for the `Printer` entity in Spoolman.

---

## 1. Pydantic Models for Printer

### Code Convention and Placement Analysis
In Spoolman, the standard model structure splits representation models and input parameters:
*   **Representation Models** (e.g., `Vendor`, `Filament`, `Spool`, `Project`, `Plate`, `PrintJob`) and their **WebSocket Events** (e.g., `VendorEvent`, `PrintJobEvent`) are defined in `spoolman/api/v1/models.py`.
*   **Input Parameters** (e.g., `VendorParameters`, `VendorUpdateParameters`) are defined locally inside the respective router files (e.g., `spoolman/api/v1/vendor.py`).

To match this convention exactly, we recommend:
1.  Defining the `Printer` and `PrinterEvent` models inside `spoolman/api/v1/models.py`.
2.  Defining `PrinterParameters` and `PrinterUpdateParameters` inside the router file `spoolman/api/v1/printer.py`.

### Proposed Models

#### Inside `spoolman/api/v1/models.py`
```python
from typing import Literal
from pydantic import BaseModel, Field
# Import or reference SpoolmanDateTime

class Printer(BaseModel):
    id: int = Field(description="Unique internal ID of this printer.")
    registered: SpoolmanDateTime = Field(description="When the printer was registered in the database. UTC Timezone.")
    name: str = Field(max_length=256, description="Printer name.", examples=["Voron 2.4"])
    model: str | None = Field(None, max_length=256, description="Printer model.", examples=["Voron 2.4 R2"])
    location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Living Room"])
    comment: str | None = Field(None, max_length=1024, description="Free text comment about this printer.", examples=["My favorite printer"])

    @staticmethod
    def from_db(item: models.Printer) -> "Printer":
        return Printer(
            id=item.id,
            registered=item.registered,
            name=item.name,
            model=item.model,
            location=item.location,
            comment=item.comment,
        )

class PrinterEvent(Event):
    """Event."""

    payload: Printer = Field(description="Updated printer.")
    resource: Literal["printer"] = Field(description="Resource type.")
```

#### Inside `spoolman/api/v1/printer.py`
```python
from pydantic import BaseModel, Field, field_validator

class PrinterParameters(BaseModel):
    name: str = Field(max_length=256, description="Printer name.", examples=["Voron 2.4"])
    model: str | None = Field(None, max_length=256, description="Printer model.", examples=["Voron 2.4 R2"])
    location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Living Room"])
    comment: str | None = Field(None, max_length=1024, description="Free text comment about this printer.", examples=["My favorite printer"])

class PrinterUpdateParameters(PrinterParameters):
    name: str | None = Field(None, max_length=256, description="Printer name.", examples=["Voron 2.4"])

    @field_validator("name")
    @classmethod
    def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
        """Prevent name from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v
```

---

## 2. DB CRUD Helper Routines (`spoolman/database/printer.py`)

Since the `Printer` entity does not support custom/extra fields, the CRUD methods can be kept clean and simple without extra field filter parsing. We should use `add_where_clause_str` (for `name`) and `add_where_clause_str_opt` (for `model` and `location`) from `spoolman.database.utils`.

### Proposed CRUD Routines
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
from spoolman.exceptions import ItemNotFoundError
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
    await db.commit()
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

Mutating API operations (Create, Update, Delete) trigger real-time updates over WebSockets using Spoolman's hierarchical `websocket_manager`. 
*   **Event structure**: The tree subscription targets both the general pool `("printer",)` (for any printer modification) and specific targets `("printer", str(printer_id))` (for matching ID subscriptions).
*   **Durable deletion notice**: In the `delete` routine, the notification `printer_changed(printer, EventType.DELETED)` is dispatched *after* the DB session has successfully committed, ensuring consistency.

---

## 4. REST API Router (`spoolman/api/v1/printer.py`)

A new FastAPI router should be created to define the REST endpoints and serve WebSocket connections matching the requirements.

### Proposed Router Implementation
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
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/printer",
    tags=["printer"],
)


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
    name: Annotated[str | None, Query(title="Printer Name")] = None,
    model: Annotated[str | None, Query(title="Printer Model")] = None,
    location: Annotated[str | None, Query(title="Printer Location")] = None,
    sort: Annotated[str | None, Query(title="Sort", examples=["name:asc,id:desc"])] = None,
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
        return JSONResponse(status_code=400, content=Message(message=str(e)).dict())

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
    response_model_exclude_none=True,
    response_model=Printer,
    responses={400: {"model": Message}, 404: {"model": Message}},
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
    responses={404: {"model": Message}},
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    printer_id: int,
) -> Message:
    await printer.delete(db, printer_id)
    return Message(message="Success!")
```

---

## 5. Router Registration

In `spoolman/api/v1/router.py`:
1.  Import `printer` along with other endpoints at line 18:
    ```python
    from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job, printer
    ```
2.  Include the printer router in FastAPI at the bottom:
    ```python
    app.include_router(printer.router)
    ```

---

## 6. PrintJob Integration & Relationships

The `PrintJob` entity must return `printer_id` and the nested `printer` details.

### Schema Updates (`spoolman/api/v1/models.py`)
Update the `PrintJob` model definition to return both the raw `printer_id` and the optional nested `Printer` model.

```python
class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered. UTC Timezone.")
    plate_id: int = Field(description="Associated plate ID.")
    status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
    start_time: SpoolmanDateTime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: SpoolmanDateTime | None = Field(None, description="End time. UTC Timezone.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.")
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
            printer=Printer.from_db(item.printer) if item.printer else None,
            comment=item.comment,
            spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
        )
```

### API Parameters Updates (`spoolman/api/v1/print_job.py`)
Allow linking to an existing printer directly using `printer_id` during creation or updates.
*   Update `PrintJobParameters` with `printer_id: int | None = Field(None, description="Associated printer ID.")`.
*   Update `PrintJobUpdateParameters` with `printer_id: int | None = Field(None, description="Associated printer ID.")`.

### CRUD Updates (`spoolman/database/print_job.py`)
Modify the `create` and `update` logic to handle linking of printers via either `printer_id` or `printer_name` (maintaining backward compatibility).

#### In `create`:
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

#### In `update`:
```python
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
```

---

## 7. Integration Testing Strategy

The integration tests run in a dedicated container against a built Spoolman image running multiple databases.

### 1. Fixture Definitions (`tests_integration/tests/conftest.py`)
Add support for generating/tearing down printers in the fixtures.
```python
@contextmanager
def random_printer_impl():
    """Return a random printer."""
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={
            "name": "Voron 2.4",
            "model": "Voron 2.4 R2",
            "location": "Living Room",
            "comment": "Nice printer",
        },
    )
    result.raise_for_status()
    prt = result.json()
    yield prt
    httpx.delete(f"{URL}/api/v1/printer/{prt['id']}").raise_for_status()

@pytest.fixture
def random_printer():
    """Return a random printer."""
    with random_printer_impl() as prt:
        yield prt
```

### 2. Printer CRUD Tests (`tests_integration/tests/printer/test_crud.py`)
Create a new file with tests covering:
*   `test_create_printer`: POST `/api/v1/printer`, assert ID is generated, default values are correct, and name constraints are enforced.
*   `test_get_printer`: GET `/api/v1/printer/{id}`, assert data matches.
*   `test_find_printers`: GET `/api/v1/printer` with filtering/sorting queries.
*   `test_patch_printer`: PATCH `/api/v1/printer/{id}`, assert modified properties update.
*   `test_delete_printer`: DELETE `/api/v1/printer/{id}` and check for 404 response.

### 3. PrintJob and Printer Relationship Tests (`tests_integration/tests/print_job/test_crud.py`)
Add relationship assertions to PrintJob tests:
*   `test_create_print_job_with_printer_name`: Verify passing a name creates a printer dynamically and links it (`printer_id` is populated in the returned payload).
*   `test_create_print_job_with_printer_id`: Verify linking a print job to an existing printer directly using its ID.
*   `test_printer_deletion_nullifies_print_job`: Verify that deleting a printer sets the associated print job's `printer_id` and `printer` object to `null`.
