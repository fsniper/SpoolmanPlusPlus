# Milestone 2 Backend API and CRUD for Printer Analysis Report

## 1. Executive Summary
This report presents the backend architecture and a detailed file-by-file implementation plan for Milestone 2: Backend API and CRUD for Printer. It establishes the necessary Pydantic models, SQLAlchemy-to-Pydantic conversions, CRUD operations with search/sorting/pagination, FastAPI routing, WebSocket event triggers, and integration tests to support the `Printer` entity and its relationship to `PrintJob`.

---

## 2. Architecture & Design Details

### Printer Schema and Database Mapping
- **Database Model**: `models.Printer` is already defined in `spoolman/database/models.py` with columns `id`, `registered`, `name`, `model`, `location`, and `comment`.
- **Pydantic Models**:
  - `Printer`: Represents the serialization of a printer.
  - `PrinterParameters`: Required attributes for creating a printer (`name` is required).
  - `PrinterUpdateParameters`: Attributes for updating a printer (all fields optional, but `name` cannot be set to `None`).
  - `PrinterEvent`: Used for streaming changes over WebSockets.
- **PrintJob Relationship**:
  - `PrintJob` has a foreign key `printer_id` mapping to `printer.id`.
  - It maintains a relationship with the `Printer` object, loading it optionally.
  - The API schemas for `PrintJob` will return both `printer_id` and the optional nested `printer` object.

---

## 3. File-by-File Implementation Strategy

### 3.1. `spoolman/api/v1/models.py`
Add the Pydantic models for `Printer` and update `PrintJob` to return printer relations.

**Proposed Changes**:
1. Add `field_validator` and `Literal` to the imports:
   ```python
   # Line 5
   from typing import Annotated, Literal
   # Line 7
   from pydantic import BaseModel, Field, PlainSerializer, field_validator
   ```
2. Define the new models below `SettingKV` or before `Filament`:
   ```python
   class Printer(BaseModel):
       id: int = Field(description="Unique internal ID of this printer.")
       registered: SpoolmanDateTime = Field(description="When the printer was registered in the database. UTC Timezone.")
       name: str = Field(max_length=256, description="Printer name.", examples=["Prusa MK4"])
       model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK4"])
       location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Lab 1"])
       comment: str | None = Field(
           None,
           max_length=1024,
           description="Free text comment about this printer.",
           examples=[""],
       )

       @staticmethod
       def from_db(item: models.Printer) -> "Printer":
           """Create a new Pydantic Printer object from a database Printer object."""
           return Printer(
               id=item.id,
               registered=item.registered,
               name=item.name,
               model=item.model,
               location=item.location,
               comment=item.comment,
           )


   class PrinterParameters(BaseModel):
       name: str = Field(max_length=256, description="Printer name.", examples=["Prusa MK4"])
       model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK4"])
       location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Lab 1"])
       comment: str | None = Field(
           None,
           max_length=1024,
           description="Free text comment about this printer.",
           examples=[""],
       )


   class PrinterUpdateParameters(BaseModel):
       name: str | None = Field(None, max_length=256, description="Printer name.", examples=["Prusa MK4"])
       model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK4"])
       location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Lab 1"])
       comment: str | None = Field(
           None,
           max_length=1024,
           description="Free text comment about this printer.",
           examples=[""],
       )

       @field_validator("name")
       @classmethod
       def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
           """Prevent name from being None."""
           if v is None:
               raise ValueError("Value must not be None.")
           return v


   class PrinterEvent(Event):
       """Event representing a change to a printer."""

       payload: Printer = Field(description="Updated printer.")
       resource: Literal["printer"] = Field(description="Resource type.")
   ```
3. Update `PrintJob` Pydantic model (lines 447-470) to include `printer_id` and the optional nested `printer` details:
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
       printer_name: str | None = Field(None, max_length=256, description="Printer name (for backward compatibility).")
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
               printer=Printer.from_db(item.printer) if item.printer else None,
               printer_name=item.printer_name,
               comment=item.comment,
               spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
           )
   ```

---

### 3.2. `spoolman/database/printer.py` (New File)
Implement database interactions for CRUD operations, search criteria matching, and WebSocket notifications.

```python
"""Helper functions for interacting with printer database objects."""

import logging
from datetime import datetime

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
    comment: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Printer], int]:
    """Find a list of printer objects by search criteria."""
    stmt = select(models.Printer)

    stmt = add_where_clause_str(stmt, models.Printer.name, name)
    stmt = add_where_clause_str_opt(stmt, models.Printer.model, model)
    stmt = add_where_clause_str_opt(stmt, models.Printer.location, location)
    stmt = add_where_clause_str_opt(stmt, models.Printer.comment, comment)

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

### 3.3. `spoolman/database/utils.py`
Add `printer` nested field parsing support in `parse_nested_field` to enable filtering/sorting print jobs by printer attributes:

```python
# Insert at line 34 (inside parse_nested_field):
    if fields[0] == "printer" and len(fields) == 1:
        raise ValueError("No field specified for printer")
    if fields[0] == "printer":
        return parse_nested_field(models.Printer, ".".join(fields[1:]))
```

---

### 3.4. `spoolman/database/print_job.py`
Replace `printer_name` parameters and processing logic with `printer_id` referencing:

**Proposed Changes**:
1. Update `create` method signature (lines 25-35):
   - Replace `printer_name: str | None = None` with `printer_id: int | None = None`.
2. Replace lines 54-62 in `create` (printer lookup by name) with validation for `printer_id`:
   ```python
       db_printer = None
       if printer_id is not None:
           db_printer = await db.get(models.Printer, printer_id)
           if db_printer is None:
               raise ItemNotFoundError(f"No printer with ID {printer_id} found.")
   ```
3. Update `update` method (lines 187-199):
   - Replace the `if "printer_name" in data:` check with:
   ```python
       if "printer_id" in data:
           printer_id_val = data["printer_id"]
           if printer_id_val is None:
               print_job.printer = None
           else:
               db_printer = await db.get(models.Printer, printer_id_val)
               if db_printer is None:
                   raise ItemNotFoundError(f"No printer with ID {printer_id_val} found.")
               print_job.printer = db_printer
           # Remove printer_id from raw data updates to avoid double-processing
           data.pop("printer_id", None)
   ```

---

### 3.5. `spoolman/api/v1/printer.py` (New File)
Implement the FastAPI router for Printer REST and WebSocket endpoints.

```python
"""Printer related endpoints."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Printer, PrinterEvent, PrinterParameters, PrinterUpdateParameters
from spoolman.database import printer
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/printer",
    tags=["printer"],
)

# ruff: noqa: D103


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
    comment: Annotated[
        str | None,
        Query(
            title="Printer Comment",
            description=(
                "Partial case-insensitive search term for the printer comment. Separate multiple terms with a comma. "
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

    db_items, total_count = await printer.find(
        db=db,
        name=name,
        model=model,
        location=location,
        comment=comment,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

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

### 3.6. `spoolman/api/v1/print_job.py`
Update schemas and endpoints for Print Jobs to replace `printer_name` input with `printer_id`.

**Proposed Changes**:
1. Update `PrintJobParameters` and `PrintJobUpdateParameters`:
   - Replace `printer_name: str | None = Field(None, max_length=256, description="Printer name.")` with `printer_id: int | None = Field(None, description="Printer ID.")`.
2. Update the `create` endpoint (line 204 onwards):
   - Change `printer_name=body.printer_name` parameter to `printer_id=body.printer_id`.
3. Update the `update` endpoint (line 235 onwards):
   - The standard `body.model_dump(exclude_unset=True)` will naturally extract `printer_id` if set. It is passed into `print_job.update(..., data=patch_data)` which resolves and maps it to the db model relationship.

---

### 3.7. `spoolman/api/v1/router.py`
Register the new `/printer` router under the FastAPI app.

**Proposed Changes**:
1. Update imports:
   ```python
   # Line 18
   from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job, printer
   ```
2. Include the router at the end of the file:
   ```python
   # Add printer router
   app.include_router(printer.router)
   ```

---

### 3.8. `tests_integration/tests/conftest.py`
Incorporate `random_printer` fixtures for test runs.

**Proposed Changes**:
1. Implement the following context manager and fixtures:
   ```python
   @contextmanager
   def random_printer_impl():
       """Return a random printer."""
       result = httpx.post(
           f"{URL}/api/v1/printer",
           json={
               "name": "Integration Test Printer",
               "model": "Prusa MK4",
               "location": "Lab 1",
               "comment": "Default printer for integration tests",
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
2. Update `random_print_job_impl` and `random_print_job` fixture:
   - Accept an optional `printer_id` and pass it instead of `printer_name`:
   ```python
   @contextmanager
   def random_print_job_impl(plate_id: int, printer_id: int | None = None):
       """Return a random print job."""
       json_data = {
           "plate_id": plate_id,
           "status": "pending",
           "comment": "Initial test job",
           "spool_usages": [],
       }
       if printer_id is not None:
           json_data["printer_id"] = printer_id

       result = httpx.post(
           f"{URL}/api/v1/print_job",
           json=json_data,
       )
       result.raise_for_status()

       print_job: dict[str, Any] = result.json()
       yield print_job

       httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}").raise_for_status()


   @pytest.fixture
   def random_print_job(random_plate, random_printer):
       """Return a random print job."""
       with random_print_job_impl(random_plate["id"], random_printer["id"]) as print_job:
           yield print_job
   ```

---

### 3.9. `tests_integration/tests/print_job/test_crud.py`
Update integration tests to verify the `printer_id` and relational `printer` object output fields.

**Proposed Changes**:
- Update `test_create_print_job` to pass `printer_id` instead of `printer_name`. Validate that the returned print job includes the expected `printer_id`, `printer` object details, and `printer_name` (backward-compatibility field).
- Update `test_patch_print_job` to perform updates via `printer_id`.

---

### 3.10. `tests_integration/tests/printer/` (New Integration Tests)
Create a full CRUD and boundary testing suite for the Printer API.

#### `tests_integration/tests/printer/__init__.py`
Empty initializer file.

#### `tests_integration/tests/printer/test_add.py`
```python
"""Integration tests for the Printer API endpoint."""

from datetime import datetime, timezone
import httpx
from ..conftest import URL, assert_dicts_compatible

def test_add_printer():
    name = "Prusa MK4"
    model = "MK4"
    location = "Lab 1"
    comment = "Integration test printer"

    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={
            "name": name,
            "model": model,
            "location": location,
            "comment": comment,
        },
    )
    result.raise_for_status()
    printer = result.json()

    assert_dicts_compatible(
        printer,
        {
            "id": printer["id"],
            "registered": printer["registered"],
            "name": name,
            "model": model,
            "location": location,
            "comment": comment,
        },
    )

    diff = abs((datetime.now(tz=timezone.utc) - datetime.fromisoformat(printer["registered"])).total_seconds())
    assert diff < 60

    httpx.delete(f"{URL}/api/v1/printer/{printer['id']}").raise_for_status()
```

#### `tests_integration/tests/printer/test_get.py`
```python
"""Integration tests for the Printer API endpoint."""

import httpx
from ..conftest import URL

def test_get_printer(random_printer):
    result = httpx.get(f"{URL}/api/v1/printer/{random_printer['id']}")
    assert result.status_code == 200
    printer = result.json()
    assert printer["id"] == random_printer["id"]
    assert printer["name"] == random_printer["name"]
```

#### `tests_integration/tests/printer/test_find.py`
```python
"""Integration tests for the Printer API endpoint."""

from dataclasses import dataclass
from typing import Any
import httpx
import pytest
from ..conftest import URL, assert_lists_compatible

@dataclass
class Fixture:
    printers: list[dict[str, Any]]

@pytest.fixture(scope="module")
def printers():
    p1 = httpx.post(f"{URL}/api/v1/printer", json={"name": "Prusa MK4", "model": "MK4", "location": "Lab 1"}).json()
    p2 = httpx.post(f"{URL}/api/v1/printer", json={"name": "Ender 3", "model": "Ender", "location": "Lab 2"}).json()
    yield Fixture(printers=[p1, p2])
    httpx.delete(f"{URL}/api/v1/printer/{p1['id']}").raise_for_status()
    httpx.delete(f"{URL}/api/v1/printer/{p2['id']}").raise_for_status()

def test_find_all_printers(printers):
    result = httpx.get(f"{URL}/api/v1/printer")
    result.raise_for_status()
    items = result.json()
    assert len(items) >= 2

def test_find_printers_by_name(printers):
    result = httpx.get(f"{URL}/api/v1/printer", params={"name": "Prusa"})
    result.raise_for_status()
    items = result.json()
    assert any(p["name"] == "Prusa MK4" for p in items)
```

#### `tests_integration/tests/printer/test_update.py`
```python
"""Integration tests for the Printer API endpoint."""

import httpx
from ..conftest import URL

def test_update_printer(random_printer):
    new_location = "Lab 9"
    result = httpx.patch(
        f"{URL}/api/v1/printer/{random_printer['id']}",
        json={"location": new_location},
    )
    assert result.status_code == 200
    printer = result.json()
    assert printer["location"] == new_location
```

#### `tests_integration/tests/printer/test_delete.py`
```python
"""Integration tests for the Printer API endpoint."""

import httpx
from ..conftest import URL

def test_delete_printer():
    p = httpx.post(f"{URL}/api/v1/printer", json={"name": "Delete Me"}).json()
    res = httpx.delete(f"{URL}/api/v1/printer/{p['id']}")
    assert res.status_code in (200, 204)

    get_res = httpx.get(f"{URL}/api/v1/printer/{p['id']}")
    assert get_res.status_code == 404
```

---

## 4. Verification Methods
Run the full integration suite utilizing SQLite:
```bash
python tests_integration/run.py sqlite
```
Ensure all 32 current tests plus new printer CRUD tests pass with an exit code of 0.
