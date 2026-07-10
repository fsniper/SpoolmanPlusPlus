# Milestone 2: Backend API and CRUD for Printer — Analysis & Implementation Plan

This document outlines the recommended file-by-file implementation strategy for Milestone 2: Backend API and CRUD for Printer in the Spoolman project.

---

## 1. Summary of Strategy

To implement Milestone 2, we need to add a complete CRUD pipeline for the `Printer` entity (already defined in the SQLAlchemy database schema) and integrate it into the `PrintJob` model and endpoints:
1. **Pydantic Schemas**: Define `Printer`, `PrinterParameters`, `PrinterUpdateParameters`, and `PrinterEvent` in `spoolman/api/v1/models.py`. Update the `PrintJob` schema to return `printer_id` and `printer` details.
2. **Database CRUD**: Create `spoolman/database/printer.py` to support database operations: `create`, `update`, `get_by_id`, `find`, and `delete`. Integrate `printer_id` lookup into print job creation/updates in `spoolman/database/print_job.py`.
3. **REST API Routing**: Create `spoolman/api/v1/printer.py` and register it in `spoolman/api/v1/router.py`. Update `spoolman/api/v1/print_job.py` to accept `printer_id` in request body schemas.
4. **WebSocket Notifications**: Trigger real-time notifications on creation, update, and deletion of printers.
5. **Integration Verification**: Add printer integration tests in `tests_integration/tests/printer/test_crud.py` and update print job tests to verify printer association.

---

## 2. Detailed File-by-File Changes

### 2.1. `spoolman/api/v1/models.py` (Modify)

- **Purpose**: Define Pydantic models for request/response serialization.
- **Proposed Changes**:
  1. Add `field_validator` to Pydantic imports:
     ```python
     from pydantic import BaseModel, Field, PlainSerializer, field_validator
     ```
  2. Define `Printer`, `PrinterParameters`, `PrinterUpdateParameters`, and `PrinterEvent`:
     ```python
     class Printer(BaseModel):
         id: int = Field(description="Unique internal ID of this printer.")
         registered: SpoolmanDateTime = Field(description="When the printer was registered. UTC Timezone.")
         name: str = Field(max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
         model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK3S"])
         location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Maker space"])
         comment: str | None = Field(None, max_length=1024, description="Free text comment about this printer.", examples=[""])

         @staticmethod
         def from_db(item: models.Printer) -> "Printer":
             """Create a Pydantic Printer object from a database Printer object."""
             return Printer(
                 id=item.id,
                 registered=item.registered,
                 name=item.name,
                 model=item.model,
                 location=item.location,
                 comment=item.comment,
             )

     class PrinterParameters(BaseModel):
         name: str = Field(min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
         model: str | None = Field(None, max_length=256, description="Printer model.", examples=["MK3S"])
         location: str | None = Field(None, max_length=256, description="Printer location.", examples=["Maker space"])
         comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=[""])

     class PrinterUpdateParameters(BaseModel):
         name: str | None = Field(None, min_length=1, max_length=256, description="Printer name.", examples=["Prusa i3 MK3S"])
         model: str | None = Field(None, max_length=256, description="Printer model.")
         location: str | None = Field(None, max_length=256, description="Printer location.")
         comment: str | None = Field(None, max_length=1024, description="Optional comment.")

         @field_validator("name")
         @classmethod
         def prevent_none(cls: type["PrinterUpdateParameters"], v: str | None) -> str | None:
             """Prevent name from being None."""
             if v is None:
                 raise ValueError("Value must not be None.")
             return v

     class PrinterEvent(Event):
         payload: Printer = Field(description="Updated printer.")
         resource: Literal["printer"] = Field(description="Resource type.")
     ```
  3. Modify the `PrintJob` model to include `printer_id` and the optional nested `printer` details:
     ```python
     class PrintJob(BaseModel):
         # ... existing fields ...
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
                 printer=Printer.from_db(item.printer) if item.printer is not None else None,
                 comment=item.comment,
                 spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
             )
     ```

---

### 2.2. `spoolman/database/printer.py` (Create)

- **Purpose**: Provide helper database querying functions and WebSocket hook wrapper functions.
- **Proposed Changes**:
  Implement the following module content:
  ```python
  """Helper functions for interacting with printer database objects."""

  import logging
  from datetime import datetime

  import sqlalchemy
  from sqlalchemy import func, select
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy.orm import joinedload

  from spoolman.api.v1.models import EventType, Printer, PrinterEvent
  from spoolman.database import models
  from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_str_opt
  from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
  from spoolman.ws import websocket_manager

  logger = logging.getLogger(__name__)

  async def get_by_id(db: AsyncSession, printer_id: int) -> models.Printer:
      """Get a printer object from the database by the unique ID."""
      stmt = select(models.Printer).where(models.Printer.id == printer_id).options(joinedload("*"))
      result = await db.execute(stmt)
      printer = result.unique().scalars().first()
      if printer is None:
          raise ItemNotFoundError(f"No printer with ID {printer_id} found.")
      return printer

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
      pydantic_printer = Printer.from_db(printer)
      await db.delete(printer)
      try:
          await db.commit()
          await printer_changed_payload(pydantic_printer, EventType.DELETED)
      except sqlalchemy.exc.IntegrityError as exc:
          await db.rollback()
          raise ItemDeleteError("Failed to delete printer.") from exc

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

  async def printer_changed(printer: models.Printer, typ: EventType) -> None:
      """Notify websocket clients that a printer has changed."""
      await printer_changed_payload(Printer.from_db(printer), typ)

  async def printer_changed_payload(payload: Printer, typ: EventType) -> None:
      """Notify websocket clients with a pre-constructed payload."""
      try:
          await websocket_manager.send(
              ("printer", str(payload.id)),
              PrinterEvent(
                  type=typ,
                  resource="printer",
                  date=datetime.utcnow(),
                  payload=payload,
              ),
          )
      except Exception:
          logger.exception("Failed to send websocket message")
  ```

---

### 2.3. `spoolman/api/v1/printer.py` (Create)

- **Purpose**: Implement the FastAPI router and endpoints for `/printer`.
- **Proposed Changes**:
  Create the endpoint file exposing standard CRUD operations and WebSocket subscriptions:
  ```python
  """Printer related endpoints."""

  import asyncio
  import logging
  from typing import Annotated

  from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
  from fastapi.encoders import jsonable_encoder
  from fastapi.responses import JSONResponse
  from sqlalchemy.ext.asyncio import AsyncSession

  from spoolman.api.v1.models import Message, Printer, PrinterParameters, PrinterUpdateParameters, PrinterEvent
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
              description="Partial case-insensitive search term for the printer model.",
          ),
      ] = None,
      location: Annotated[
          str | None,
          Query(
              title="Printer Location",
              description="Partial case-insensitive search term for the printer location.",
          ),
      ] = None,
      comment: Annotated[
          str | None,
          Query(
              title="Printer Comment",
              description="Partial case-insensitive search term for the printer comment.",
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
              comment=comment,
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
  async def create(  # noqa: ANN201
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
  async def update(  # noqa: ANN201
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

### 2.4. `spoolman/api/v1/router.py` (Modify)

- **Purpose**: Register the new printer API router under the `/printer` namespace.
- **Proposed Changes**:
  1. Add `printer` to imports on line 18:
     ```python
     from . import export, externaldb, field, filament, models, other, setting, spool, vendor, project, plate, print_job, printer
     ```
  2. Include the router near other registered endpoints:
     ```python
     app.include_router(printer.router)
     ```

---

### 2.5. `spoolman/database/print_job.py` (Modify)

- **Purpose**: Support the `printer_id` parameter during `PrintJob` creation and updates, resolving it from the printer table.
- **Proposed Changes**:
  1. Import `printer` from the database module on line 17:
     ```python
     from spoolman.database import models, plate, spool, printer
     ```
  2. Update `create` method signature to accept keyword-only `printer_id`:
     ```python
     async def create(
         *,
         db: AsyncSession,
         plate_id: int,
         status: str,
         start_time: datetime | None = None,
         end_time: datetime | None = None,
         printer_name: str | None = None,
         printer_id: int | None = None,
         comment: str | None = None,
         spool_usages: list[dict] | None = None,
     ) -> models.PrintJob:
     ```
  3. Resolve the `Printer` record inside `create`:
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
  4. In the `update` method, add the resolution block for `printer_id`:
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

### 2.6. `spoolman/api/v1/print_job.py` (Modify)

- **Purpose**: Update `PrintJob` parameters to accept `printer_id` in GET/POST/PATCH requests.
- **Proposed Changes**:
  1. Add `printer_id: int | None = Field(None, description="Printer ID.")` to `PrintJobParameters`:
     ```python
     class PrintJobParameters(BaseModel):
         plate_id: int = Field(description="Associated plate ID.")
         status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
         start_time: datetime | None = Field(None, description="Start time. UTC Timezone.")
         end_time: datetime | None = Field(None, description="End time. UTC Timezone.")
         printer_name: str | None = Field(None, max_length=256, description="Printer name.")
         printer_id: int | None = Field(None, description="Printer ID.")
         comment: str | None = Field(None, max_length=1024, description="Optional comment.")
         spool_usages: list[PrintJobSpoolParameters] = Field(default=[], description="Filament usage per spool.")
     ```
  2. Add `printer_id: int | None = Field(None, description="Printer ID.")` to `PrintJobUpdateParameters`:
     ```python
     class PrintJobUpdateParameters(BaseModel):
         plate_id: int | None = Field(None, description="Associated plate ID.")
         status: str | None = Field(None, max_length=64, description="Status of the print job.")
         start_time: datetime | None = Field(None, description="Start time. UTC Timezone.")
         end_time: datetime | None = Field(None, description="End time. UTC Timezone.")
         printer_name: str | None = Field(None, max_length=256, description="Printer name.")
         printer_id: int | None = Field(None, description="Printer ID.")
         comment: str | None = Field(None, max_length=1024, description="Optional comment.")
         spool_usages: list[PrintJobSpoolParameters] | None = Field(None, description="Filament usage per spool.")
     ```
  3. In the `create` endpoint, forward `printer_id` to the database CRUD `create` function:
     ```python
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
     ```

---

### 2.7. `tests_integration/tests/conftest.py` (Modify)

- **Purpose**: Add integration test fixtures for printers to use in `printer` and `print_job` CRUD tests.
- **Proposed Changes**:
  Add `random_printer_impl` and `random_printer`:
  ```python
  @contextmanager
  def random_printer_impl():
      """Return a random printer."""
      result = httpx.post(
          f"{URL}/api/v1/printer",
          json={
              "name": "Prusa MK3",
              "model": "MK3S+",
              "location": "Lab 1",
              "comment": "PLA only",
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

---

### 2.8. `tests_integration/tests/printer/test_crud.py` (Create)

- **Purpose**: Verify endpoints GET, POST, PATCH, DELETE for `/printer`.
- **Proposed Changes**:
  Write the integration test suite for printers:
  ```python
  """Integration tests for Printer CRUD."""

  from typing import Any
  import httpx

  from ..conftest import URL


  def test_create_printer():
      """Test creating a printer."""
      payload = {
          "name": "Prusa i3",
          "model": "MK3S+",
          "location": "Makerspace",
          "comment": "Works well",
      }
      result = httpx.post(f"{URL}/api/v1/printer", json=payload)
      assert result.status_code in (200, 201)
      printer = result.json()

      assert "id" in printer
      assert "registered" in printer
      assert printer["name"] == payload["name"]
      assert printer["model"] == payload["model"]
      assert printer["location"] == payload["location"]
      assert printer["comment"] == payload["comment"]

      # Clean up
      httpx.delete(f"{URL}/api/v1/printer/{printer['id']}").raise_for_status()


  def test_get_printer(random_printer: dict[str, Any]):
      """Test getting a printer."""
      result = httpx.get(f"{URL}/api/v1/printer/{random_printer['id']}")
      assert result.status_code == 200
      printer = result.json()
      assert printer["id"] == random_printer["id"]
      assert printer["name"] == random_printer["name"]


  def test_list_printers(random_printer: dict[str, Any]):
      """Test listing printers with filters."""
      result = httpx.get(f"{URL}/api/v1/printer", params={"name": random_printer["name"]})
      assert result.status_code == 200
      printers = result.json()
      assert isinstance(printers, list)
      assert len(printers) >= 1
      assert any(p["id"] == random_printer["id"] for p in printers)
      assert "x-total-count" in result.headers


  def test_patch_printer(random_printer: dict[str, Any]):
      """Test patching a printer."""
      new_location = "Office"
      result = httpx.patch(f"{URL}/api/v1/printer/{random_printer['id']}", json={"location": new_location})
      assert result.status_code == 200
      printer = result.json()
      assert printer["id"] == random_printer["id"]
      assert printer["location"] == new_location


  def test_delete_printer():
      """Test deleting a printer."""
      result = httpx.post(
          f"{URL}/api/v1/printer",
          json={"name": "Temporary Printer"},
      )
      result.raise_for_status()
      printer = result.json()

      del_res = httpx.delete(f"{URL}/api/v1/printer/{printer['id']}")
      assert del_res.status_code in (200, 204)

      get_res = httpx.get(f"{URL}/api/v1/printer/{printer['id']}")
      assert get_res.status_code == 404
  ```

---

### 2.9. `tests_integration/tests/print_job/test_crud.py` (Modify)

- **Purpose**: Verify `printer_id` and nested `printer` fields in print job responses.
- **Proposed Changes**:
  Add a test verifying creating, updating, and fetching a print job linked to a printer by ID:
  ```python
  def test_print_job_with_printer_id(random_plate: dict[str, Any], random_printer: dict[str, Any]):
      """Test print job CRUD operations using a specific printer_id."""
      payload = {
          "plate_id": random_plate["id"],
          "status": "pending",
          "printer_id": random_printer["id"],
          "comment": "Testing printer_id link",
          "spool_usages": [],
      }
      # Create
      result = httpx.post(f"{URL}/api/v1/print_job", json=payload)
      assert result.status_code in (200, 201)
      print_job = result.json()
      assert print_job["printer_id"] == random_printer["id"]
      assert print_job["printer"]["id"] == random_printer["id"]
      assert print_job["printer"]["name"] == random_printer["name"]

      # Patch to remove printer_id
      patch_res = httpx.patch(f"{URL}/api/v1/print_job/{print_job['id']}", json={"printer_id": None})
      assert patch_res.status_code == 200
      updated = patch_res.json()
      assert updated["printer_id"] is None
      assert updated["printer"] is None

      # Clean up
      httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}").raise_for_status()
  ```

---

## 3. Verification Method

To verify the implementation once coded, run:
```bash
python tests_integration/run.py sqlite
```
Ensure all 32+ tests pass, including the new printer suite and updated print job test suite.
