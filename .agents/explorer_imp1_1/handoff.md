# Milestone IMP-1: Backend API & CRUD Handoff Report

## 1. Observation

### Existing Database Models
I observed that the SQLAlchemy models for `Project`, `Plate`, `PrintJob`, and `PrintJobSpool` are already defined in `/Users/yalazi/Documents/PROJECTS/software/Spoolman/spoolman/database/models.py` (lines 121-171):
```python
121: class Project(Base):
122:     __tablename__ = "project"
123: 
124:     id: Mapped[int] = mapped_column(primary_key=True, index=True)
125:     registered: Mapped[datetime] = mapped_column()
126:     name: Mapped[str] = mapped_column(String(256))
127:     description: Mapped[str | None] = mapped_column(String(1024))
128:     link: Mapped[str | None] = mapped_column(String(1024))
129:     plates: Mapped[list["Plate"]] = relationship(back_populates="project")
...
132: class Plate(Base):
133:     __tablename__ = "plate"
134: 
135:     id: Mapped[int] = mapped_column(primary_key=True, index=True)
136:     registered: Mapped[datetime] = mapped_column()
137:     project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
138:     project: Mapped["Project"] = relationship(back_populates="plates")
139:     name: Mapped[str] = mapped_column(String(256))
...
147: class PrintJob(Base):
148:     __tablename__ = "print_job"
149: 
150:     id: Mapped[int] = mapped_column(primary_key=True, index=True)
151:     registered: Mapped[datetime] = mapped_column()
152:     plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"))
153:     plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
154:     status: Mapped[str] = mapped_column(String(64))
155:     start_time: Mapped[datetime | None] = mapped_column()
156:     end_time: Mapped[datetime | None] = mapped_column()
157:     printer_name: Mapped[str | None] = mapped_column(String(256))
158:     comment: Mapped[str | None] = mapped_column(String(1024))
159:     spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
160: 
161: 
162: class PrintJobSpool(Base):
163:     __tablename__ = "print_job_spool"
164: 
165:     id: Mapped[int] = mapped_column(primary_key=True, index=True)
166:     print_job_id: Mapped[int] = mapped_column(ForeignKey("print_job.id"))
167:     print_job: Mapped["PrintJob"] = relationship(back_populates="spool_usages")
168:     spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"))
169:     spool: Mapped["Spool"] = relationship()
170:     weight_used: Mapped[float] = mapped_column()
```

### Integration Test Requirements
I reviewed the integration tests and identified the following requirements:
1. **Project CRUD Constraints** (`tests_integration/tests/project/test_crud.py`):
   - `test_create_project_empty_name`: Name cannot be empty (asserts 400/422 on `""`).
   - `test_create_project_long_name`: Name length limit of 256 characters (asserts 400/422 on 257 chars).
   - `test_list_projects`: Expects paginated response header `"x-total-count"`.
2. **Plate CRUD Constraints** (`tests_integration/tests/plate/test_boundaries.py` & `test_crud.py`):
   - `test_create_plate_invalid_project_id`: Asserts 400/404/422 when `project_id` does not exist.
   - `test_create_plate_negative_inputs`: Asserts 400/422 for negative `estimated_weight` and negative `estimated_time`.
   - `test_delete_project_fails_with_plates`: Asserts 400/409 when attempting to delete a project with associated plates.
3. **PrintJob CRUD Constraints** (`tests_integration/tests/print_job/test_boundaries.py` & `test_crud.py`):
   - `test_create_print_job_invalid_plate_id`: Asserts 400/404/422 when `plate_id` does not exist.
   - `test_create_print_job_invalid_spool_id`: Asserts 400/404/422 when `spool_id` in `spool_usages` does not exist.
   - `test_create_print_job_negative_weight`: Asserts 400/422 when `weight_used` in `spool_usages` is negative.
   - `test_create_print_job_chronological_time_validation`: Asserts 400/422 when `end_time` is before `start_time`.
   - `test_delete_plate_fails_with_print_jobs`: Asserts 400/409 when deleting a plate with associated print jobs.

---

## 2. Logic Chain

1. **Schema Design**: To support requests, updates, and query parameters, we must write Pydantic schemas in `spoolman/api/v1/models.py`. Pydantic fields will enforce constraints such as `min_length=1`, `max_length=256`, and `ge=0` (non-negative weight/time).
2. **Chronological Time Constraint**:
   - Pydantic level validation in `PrintJobParameters` and `PrintJobUpdateParameters` using a `@model_validator(mode="after")` to verify `end_time >= start_time`.
   - DB-helper level validation in `update` to catch cases where a partial update might submit only `end_time` or `start_time` that chronologically conflicts with the existing database value.
3. **Foreign Key Verification**:
   - In `plate.py` DB helper, check for project existence via `await project.get_by_id(...)` which raises an `ItemNotFoundError` (returning a `404` to the client).
   - In `print_job.py` DB helper, check for plate existence via `await plate.get_by_id(...)` and for spool existence in `spool_usages` via `await spool.get_by_id(...)`.
4. **Websockets & Changes**:
   - Define event classes (`ProjectEvent`, `PlateEvent`, `PrintJobEvent`) inheriting from the generic `Event` model in `api/v1/models.py`.
   - Integrate change tracking methods (`project_changed`, `plate_changed`, `print_job_changed`) into DB helpers and bind routers to the generic `websocket_manager`.
5. **Cascading / Constraints Blocks on Delete**:
   - If project is deleted but associated plates exist, SQLAlchemy raises `IntegrityError` because no cascade option is defined on `models.Project.plates`. We will catch `IntegrityError` in the DB helper and raise `ItemDeleteError`, allowing the API router to return status code `400` (which matches the integration tests).
   - Similarly, if a plate is deleted with print jobs present, it will raise `IntegrityError` and throw `ItemDeleteError`.
   - If a print job is deleted, the `PrintJobSpool` rows (spool usages) must be deleted first. We will perform manual table cleanup inside `spoolman/database/print_job.py` to prevent foreign key issues.

---

## 3. Caveats

- **No Caveats**: The existing models already contain all needed fields, which simplifies our implementation of the new files.

---

## 4. Conclusion

We can successfully implement IMP-1 by introducing three Pydantic models in `spoolman/api/v1/models.py`, three database helper modules in `spoolman/database/`, three FastAPI API routers in `spoolman/api/v1/`, and registering them in `router.py`.

Below is the proposed design code:

### 4.1. Modifications to `spoolman/api/v1/models.py`
Add the following classes to the bottom of the file:

```python
class Project(BaseModel):
    id: int = Field(description="Unique internal ID of this project.")
    registered: SpoolmanDateTime = Field(description="When the project was registered. UTC Timezone.")
    name: str = Field(min_length=1, max_length=256, description="Project name.", examples=["Spec Project"])
    description: str | None = Field(None, max_length=1024, description="Optional description of the project.", examples=[""])
    link: str | None = Field(None, max_length=1024, description="Optional URL link.", examples=["http://lnk"])

    @staticmethod
    def from_db(item: models.Project) -> "Project":
        return Project(
            id=item.id,
            registered=item.registered,
            name=item.name,
            description=item.description,
            link=item.link,
        )


class ProjectEvent(Event):
    payload: Project = Field(description="Updated project.")
    resource: Literal["project"] = Field(description="Resource type.")


class Plate(BaseModel):
    id: int = Field(description="Unique internal ID of this plate.")
    registered: SpoolmanDateTime = Field(description="When the plate was registered. UTC Timezone.")
    project_id: int = Field(description="Project ID.")
    name: str = Field(min_length=1, max_length=256, description="Plate name.", examples=["Plate Alpha"])
    file_path: str | None = Field(None, max_length=1024, description="Optional file path.", examples=["test.gcode"])
    estimated_weight: float | None = Field(None, ge=0, description="Estimated weight in grams.", examples=[45.5])
    estimated_time: int | None = Field(None, ge=0, description="Estimated time in seconds.", examples=[3600])
    comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=["Nice plate"])

    @staticmethod
    def from_db(item: models.Plate) -> "Plate":
        return Plate(
            id=item.id,
            registered=item.registered,
            project_id=item.project_id,
            name=item.name,
            file_path=item.file_path,
            estimated_weight=item.estimated_weight,
            estimated_time=item.estimated_time,
            comment=item.comment,
        )


class PlateEvent(Event):
    payload: Plate = Field(description="Updated plate.")
    resource: Literal["plate"] = Field(description="Resource type.")


class PrintJobSpool(BaseModel):
    spool_id: int = Field(description="Unique ID of the spool used.")
    weight_used: float = Field(ge=0, description="The filament weight used from this spool, in grams.", examples=[15.2])


class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered. UTC Timezone.")
    plate_id: int = Field(description="Plate ID.")
    status: str = Field(max_length=64, description="Status.", examples=["pending"])
    start_time: SpoolmanDateTime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: SpoolmanDateTime | None = Field(None, description="End time. UTC Timezone.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.", examples=["Ender 3"])
    comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=[""])
    spool_usages: list[PrintJobSpool] = Field(default_factory=list, description="Spools used in this print job.")

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
            comment=item.comment,
            spool_usages=[
                PrintJobSpool(spool_id=su.spool_id, weight_used=su.weight_used)
                for su in item.spool_usages
            ] if item.spool_usages else [],
        )


class PrintJobEvent(Event):
    payload: PrintJob = Field(description="Updated print job.")
    resource: Literal["print_job"] = Field(description="Resource type.")
```

### 4.2. Database CRUD Helpers
Create these files under `spoolman/database/`:

#### File: `spoolman/database/project.py`
```python
"""Helper functions for interacting with project database objects."""

import logging
from datetime import datetime
import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, Project, ProjectEvent
from spoolman.database import models
from spoolman.database.utils import SortOrder, add_where_clause_str
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    name: str,
    description: str | None = None,
    link: str | None = None,
) -> models.Project:
    """Add a new project to the database."""
    if not name or len(name) > 256:
        raise ValueError("Project name must be between 1 and 256 characters.")
    
    project = models.Project(
        name=name,
        registered=datetime.utcnow().replace(microsecond=0),
        description=description,
        link=link,
    )
    db.add(project)
    await db.commit()
    await project_changed(project, EventType.ADDED)
    return project


async def get_by_id(db: AsyncSession, project_id: int) -> models.Project:
    """Get a project object from the database by the unique ID."""
    project = await db.get(models.Project, project_id)
    if project is None:
        raise ItemNotFoundError(f"No project with ID {project_id} found.")
    return project


async def find(
    *,
    db: AsyncSession,
    name: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Project], int]:
    """Find a list of project objects by search criteria."""
    stmt = select(models.Project)

    stmt = add_where_clause_str(stmt, models.Project.name, name)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            field = getattr(models.Project, fieldstr)
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
    project_id: int,
    data: dict,
) -> models.Project:
    """Update the fields of a project object."""
    project = await get_by_id(db, project_id)
    
    if "name" in data:
        name = data["name"]
        if not name or len(name) > 256:
            raise ValueError("Project name must be between 1 and 256 characters.")

    for k, v in data.items():
        setattr(project, k, v)
        
    await db.commit()
    await project_changed(project, EventType.UPDATED)
    return project


async def delete(db: AsyncSession, project_id: int) -> None:
    """Delete a project object."""
    project = await get_by_id(db, project_id)
    await db.delete(project)
    try:
        await db.commit()
        await project_changed(project, EventType.DELETED)
    except IntegrityError as exc:
        await db.rollback()
        raise ItemDeleteError("Failed to delete project, it has associated plates.") from exc


async def project_changed(project: models.Project, typ: EventType) -> None:
    """Notify websocket clients that a project has changed."""
    try:
        await websocket_manager.send(
            ("project", str(project.id)),
            ProjectEvent(
                type=typ,
                resource="project",
                date=datetime.utcnow(),
                payload=Project.from_db(project),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
```

#### File: `spoolman/database/plate.py`
```python
"""Helper functions for interacting with plate database objects."""

import logging
from datetime import datetime
import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, Plate, PlateEvent
from spoolman.database import models, project
from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_int
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    project_id: int,
    name: str,
    file_path: str | None = None,
    estimated_weight: float | None = None,
    estimated_time: int | None = None,
    comment: str | None = None,
) -> models.Plate:
    """Add a new plate to the database."""
    await project.get_by_id(db, project_id)

    if not name or len(name) > 256:
        raise ValueError("Plate name must be between 1 and 256 characters.")

    if estimated_weight is not None and estimated_weight < 0:
        raise ValueError("Estimated weight must be greater than or equal to 0.")

    if estimated_time is not None and estimated_time < 0:
        raise ValueError("Estimated time must be greater than or equal to 0.")

    plate = models.Plate(
        project_id=project_id,
        name=name,
        registered=datetime.utcnow().replace(microsecond=0),
        file_path=file_path,
        estimated_weight=estimated_weight,
        estimated_time=estimated_time,
        comment=comment,
    )
    db.add(plate)
    await db.commit()
    await plate_changed(plate, EventType.ADDED)
    return plate


async def get_by_id(db: AsyncSession, plate_id: int) -> models.Plate:
    """Get a plate object from the database by the unique ID."""
    plate = await db.get(models.Plate, plate_id)
    if plate is None:
        raise ItemNotFoundError(f"No plate with ID {plate_id} found.")
    return plate


async def find(
    *,
    db: AsyncSession,
    project_id: int | None = None,
    name: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.Plate], int]:
    """Find a list of plate objects by search criteria."""
    stmt = select(models.Plate)

    if project_id is not None:
        stmt = add_where_clause_int(stmt, models.Plate.project_id, project_id)
    stmt = add_where_clause_str(stmt, models.Plate.name, name)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            field = getattr(models.Plate, fieldstr)
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
    plate_id: int,
    data: dict,
) -> models.Plate:
    """Update the fields of a plate object."""
    plate = await get_by_id(db, plate_id)

    if "project_id" in data:
        await project.get_by_id(db, data["project_id"])

    if "name" in data:
        name = data["name"]
        if not name or len(name) > 256:
            raise ValueError("Plate name must be between 1 and 256 characters.")

    if "estimated_weight" in data:
        w = data["estimated_weight"]
        if w is not None and w < 0:
            raise ValueError("Estimated weight must be greater than or equal to 0.")

    if "estimated_time" in data:
        t = data["estimated_time"]
        if t is not None and t < 0:
            raise ValueError("Estimated time must be greater than or equal to 0.")

    for k, v in data.items():
        setattr(plate, k, v)

    await db.commit()
    await plate_changed(plate, EventType.UPDATED)
    return plate


async def delete(db: AsyncSession, plate_id: int) -> None:
    """Delete a plate object."""
    plate = await get_by_id(db, plate_id)
    await db.delete(plate)
    try:
        await db.commit()
        await plate_changed(plate, EventType.DELETED)
    except IntegrityError as exc:
        await db.rollback()
        raise ItemDeleteError("Failed to delete plate, it has associated print jobs.") from exc


async def plate_changed(plate: models.Plate, typ: EventType) -> None:
    """Notify websocket clients that a plate has changed."""
    try:
        await websocket_manager.send(
            ("plate", str(plate.id)),
            PlateEvent(
                type=typ,
                resource="plate",
                date=datetime.utcnow(),
                payload=Plate.from_db(plate),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
```

#### File: `spoolman/database/print_job.py`
```python
"""Helper functions for interacting with print_job database objects."""

import logging
from datetime import datetime
import sqlalchemy
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import EventType, PrintJob, PrintJobEvent
from spoolman.database import models, plate, spool
from spoolman.database.utils import SortOrder, add_where_clause_str, add_where_clause_int
from spoolman.exceptions import ItemNotFoundError, ItemDeleteError
from spoolman.ws import websocket_manager

logger = logging.getLogger(__name__)


async def create(
    *,
    db: AsyncSession,
    plate_id: int,
    status: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    printer_name: str | None = None,
    comment: str | None = None,
    spool_usages: list[dict] | None = None,
) -> models.PrintJob:
    """Add a new print job to the database."""
    await plate.get_by_id(db, plate_id)

    if start_time is not None and end_time is not None:
        if end_time < start_time:
            raise ValueError("end_time must be after or equal to start_time")

    spool_usages_db = []
    if spool_usages:
        for su in spool_usages:
            sp_id = su["spool_id"]
            w_used = su["weight_used"]
            if w_used < 0:
                raise ValueError("weight_used must be greater than or equal to 0.")
            await spool.get_by_id(db, sp_id)
            spool_usages_db.append(
                models.PrintJobSpool(
                    spool_id=sp_id,
                    weight_used=w_used,
                )
            )

    print_job = models.PrintJob(
        plate_id=plate_id,
        status=status,
        registered=datetime.utcnow().replace(microsecond=0),
        start_time=start_time,
        end_time=end_time,
        printer_name=printer_name,
        comment=comment,
        spool_usages=spool_usages_db,
    )
    db.add(print_job)
    await db.commit()
    await db.refresh(print_job, ["spool_usages"])
    await print_job_changed(print_job, EventType.ADDED)
    return print_job


async def get_by_id(db: AsyncSession, print_job_id: int) -> models.PrintJob:
    """Get a print job object from the database by the unique ID."""
    stmt = (
        select(models.PrintJob)
        .options(joinedload(models.PrintJob.spool_usages))
        .where(models.PrintJob.id == print_job_id)
    )
    rows = await db.execute(stmt)
    print_job = rows.unique().scalar_one_or_none()
    if print_job is None:
        raise ItemNotFoundError(f"No print job with ID {print_job_id} found.")
    return print_job


async def find(
    *,
    db: AsyncSession,
    status: str | None = None,
    sort_by: dict[str, SortOrder] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[models.PrintJob], int]:
    """Find a list of print job objects by search criteria."""
    stmt = select(models.PrintJob).options(joinedload(models.PrintJob.spool_usages))

    if status is not None:
        stmt = add_where_clause_str(stmt, models.PrintJob.status, status)

    total_count = None

    if sort_by is not None:
        for fieldstr, order in sort_by.items():
            field = getattr(models.PrintJob, fieldstr)
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
    print_job_id: int,
    data: dict,
) -> models.PrintJob:
    """Update the fields of a print job object."""
    print_job = await get_by_id(db, print_job_id)

    new_start = data.get("start_time", print_job.start_time)
    new_end = data.get("end_time", print_job.end_time)
    if new_start is not None and new_end is not None:
        if new_end < new_start:
            raise ValueError("end_time must be after or equal to start_time")

    if "plate_id" in data:
        await plate.get_by_id(db, data["plate_id"])

    if "spool_usages" in data:
        await db.execute(
            sqlalchemy.delete(models.PrintJobSpool).where(models.PrintJobSpool.print_job_id == print_job_id)
        )
        spool_usages_db = []
        for su in data["spool_usages"]:
            sp_id = su["spool_id"]
            w_used = su["weight_used"]
            if w_used < 0:
                raise ValueError("weight_used must be greater than or equal to 0.")
            await spool.get_by_id(db, sp_id)
            spool_usages_db.append(
                models.PrintJobSpool(
                    spool_id=sp_id,
                    weight_used=w_used,
                )
            )
        print_job.spool_usages = spool_usages_db

    for k, v in data.items():
        if k != "spool_usages":
            setattr(print_job, k, v)

    await db.commit()
    await print_job_changed(print_job, EventType.UPDATED)
    return print_job


async def delete(db: AsyncSession, print_job_id: int) -> None:
    """Delete a print job object."""
    print_job = await get_by_id(db, print_job_id)
    await db.execute(
        sqlalchemy.delete(models.PrintJobSpool).where(models.PrintJobSpool.print_job_id == print_job_id)
    )
    await db.delete(print_job)
    await db.commit()
    await print_job_changed(print_job, EventType.DELETED)


async def print_job_changed(print_job: models.PrintJob, typ: EventType) -> None:
    """Notify websocket clients that a print job has changed."""
    try:
        await websocket_manager.send(
            ("print_job", str(print_job.id)),
            PrintJobEvent(
                type=typ,
                resource="print_job",
                date=datetime.utcnow(),
                payload=PrintJob.from_db(print_job),
            ),
        )
    except Exception:
        logger.exception("Failed to send websocket message")
```

### 4.3. API Routers
Create these files under `spoolman/api/v1/`:

#### File: `spoolman/api/v1/project.py`
```python
"""Project related endpoints."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Project, ProjectEvent
from spoolman.database import project
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/project",
    tags=["project"],
)

logger = logging.getLogger(__name__)


class ProjectParameters(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Project name.", examples=["Spec Project"])
    description: str | None = Field(None, max_length=1024, description="Optional description of the project.", examples=[""])
    link: str | None = Field(None, max_length=1024, description="Optional URL link.", examples=["http://lnk"])


class ProjectUpdateParameters(ProjectParameters):
    name: str | None = Field(None, min_length=1, max_length=256, description="Project name.", examples=["Spec Project"])

    @field_validator("name")
    @classmethod
    def prevent_none(cls: type["ProjectUpdateParameters"], v: str | None) -> str | None:
        """Prevent name from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v


@router.get(
    "",
    name="Find project",
    description="Get a list of projects.",
    response_model_exclude_none=True,
    responses={
        200: {"model": list[Project]},
        299: {"model": ProjectEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    name: Annotated[
        str | None,
        Query(
            title="Project Name",
            description="Partial case-insensitive search term for the project name.",
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description='Sort the results by the given field.',
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
        db_items, total_count = await project.find(
            db=db,
            name=name,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())

    return JSONResponse(
        content=jsonable_encoder(
            (Project.from_db(db_item) for db_item in db_items),
            exclude_none=True,
        ),
        headers={"x-total-count": str(total_count)},
    )


@router.websocket(
    "",
    name="Listen to project changes",
)
async def notify_any(
    websocket: WebSocket,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("project",), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("project",), websocket)


@router.get(
    "/{project_id}",
    name="Get project",
    description="Get a specific project.",
    response_model_exclude_none=True,
    responses={404: {"model": Message}, 299: {"model": ProjectEvent, "description": "Websocket message"}},
)
async def get(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: int,
) -> Project:
    db_item = await project.get_by_id(db, project_id)
    return Project.from_db(db_item)


@router.websocket(
    "/{project_id}",
    name="Listen to project changes",
)
async def notify(
    websocket: WebSocket,
    project_id: int,
) -> None:
    await websocket.accept()
    websocket_manager.connect(("project", str(project_id)), websocket)
    try:
        while True:
            await asyncio.sleep(0.5)
            if await websocket.receive_text():
                await websocket.send_json({"status": "healthy"})
    except WebSocketDisconnect:
        websocket_manager.disconnect(("project", str(project_id)), websocket)


@router.post(
    "",
    name="Add project",
    description="Add a new project to the database.",
    response_model_exclude_none=True,
    response_model=Project,
    responses={400: {"model": Message}},
)
async def create(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: ProjectParameters,
):
    try:
        db_item = await project.create(
            db=db,
            name=body.name,
            description=body.description,
            link=body.link,
        )
        return Project.from_db(db_item)
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.patch(
    "/{project_id}",
    name="Update project",
    description="Update any attribute of a project.",
    response_model_exclude_none=True,
    response_model=Project,
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def update(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: int,
    body: ProjectUpdateParameters,
):
    patch_data = body.model_dump(exclude_unset=True)
    try:
        db_item = await project.update(
            db=db,
            project_id=project_id,
            data=patch_data,
        )
        return Project.from_db(db_item)
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.delete(
    "/{project_id}",
    name="Delete project",
    description="Delete a project.",
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    project_id: int,
):
    try:
        await project.delete(db, project_id)
        return Message(message="Success!")
    except ItemDeleteError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e)},
        )
```

#### File: `spoolman/api/v1/plate.py`
```python
"""Plate related endpoints."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, Plate, PlateEvent
from spoolman.database import plate
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/plate",
    tags=["plate"],
)

logger = logging.getLogger(__name__)


class PlateParameters(BaseModel):
    project_id: int = Field(description="Project ID.")
    name: str = Field(min_length=1, max_length=256, description="Plate name.", examples=["Plate Alpha"])
    file_path: str | None = Field(None, max_length=1024, description="Optional file path.", examples=["test.gcode"])
    estimated_weight: float | None = Field(None, ge=0, description="Estimated weight in grams.", examples=[45.5])
    estimated_time: int | None = Field(None, ge=0, description="Estimated time in seconds.", examples=[3600])
    comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=[""])


class PlateUpdateParameters(PlateParameters):
    project_id: int | None = Field(None, description="Project ID.")
    name: str | None = Field(None, min_length=1, max_length=256, description="Plate name.", examples=["Plate Alpha"])

    @field_validator("project_id", "name")
    @classmethod
    def prevent_none(cls: type["PlateUpdateParameters"], v: any) -> any:
        """Prevent values from being None."""
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
            description="Filter by project ID.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        Query(
            title="Plate Name",
            description="Partial case-insensitive search term for the plate name.",
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description='Sort the results by the given field.',
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
    try:
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
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.patch(
    "/{plate_id}",
    name="Update plate",
    description="Update any attribute of a plate.",
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
    try:
        db_item = await plate.update(
            db=db,
            plate_id=plate_id,
            data=patch_data,
        )
        return Plate.from_db(db_item)
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.delete(
    "/{plate_id}",
    name="Delete plate",
    description="Delete a plate.",
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    plate_id: int,
):
    try:
        await plate.delete(db, plate_id)
        return Message(message="Success!")
    except ItemDeleteError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e)},
        )
```

#### File: `spoolman/api/v1/print_job.py`
```python
"""PrintJob related endpoints."""

import asyncio
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from spoolman.api.v1.models import Message, PrintJob, PrintJobEvent, PrintJobSpool
from spoolman.database import print_job
from spoolman.database.database import get_db_session
from spoolman.database.utils import SortOrder
from spoolman.exceptions import ItemDeleteError
from spoolman.ws import websocket_manager

router = APIRouter(
    prefix="/print_job",
    tags=["print_job"],
)

logger = logging.getLogger(__name__)


class PrintJobParameters(BaseModel):
    plate_id: int = Field(description="Plate ID.")
    status: str = Field(max_length=64, description="Status.", examples=["printing"])
    start_time: datetime | None = Field(None, description="Start time.")
    end_time: datetime | None = Field(None, description="End time.")
    printer_name: str | None = Field(None, max_length=256, description="Printer name.", examples=["Ender 3"])
    comment: str | None = Field(None, max_length=1024, description="Optional comment.", examples=[""])
    spool_usages: list[PrintJobSpool] = Field(default_factory=list, description="Spools used in this print job.")

    @model_validator(mode="after")  # type: ignore[]
    def validate(self) -> "PrintJobParameters":
        """Validate chronological time order."""
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must be after or equal to start_time")
        return self


class PrintJobUpdateParameters(PrintJobParameters):
    plate_id: int | None = Field(None, description="Plate ID.")
    status: str | None = Field(None, max_length=64, description="Status.", examples=["printing"])

    @field_validator("plate_id", "status")
    @classmethod
    def prevent_none(cls: type["PrintJobUpdateParameters"], v: any) -> any:
        """Prevent values from being None."""
        if v is None:
            raise ValueError("Value must not be None.")
        return v

    @model_validator(mode="after")  # type: ignore[]
    def validate(self) -> "PrintJobUpdateParameters":
        """Validate chronological time order."""
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must be after or equal to start_time")
        return self


@router.get(
    "",
    name="Find print job",
    description="Get a list of print jobs.",
    response_model_exclude_none=True,
    responses={
        200: {"model": list[PrintJob]},
        299: {"model": PrintJobEvent, "description": "Websocket message"},
    },
)
async def find(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status: Annotated[
        str | None,
        Query(
            title="Status",
            description="Filter by print job status.",
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Query(
            title="Sort",
            description='Sort the results by the given field.',
            examples=["id:asc,registered:desc"],
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
            status=status,
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
    description="Get a specific print job.",
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
async def create(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    body: PrintJobParameters,
):
    try:
        spool_usages_data = [
            {"spool_id": su.spool_id, "weight_used": su.weight_used}
            for su in body.spool_usages
        ]

        db_item = await print_job.create(
            db=db,
            plate_id=body.plate_id,
            status=body.status,
            start_time=body.start_time,
            end_time=body.end_time,
            printer_name=body.printer_name,
            comment=body.comment,
            spool_usages=spool_usages_data,
        )
        return PrintJob.from_db(db_item)
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.patch(
    "/{print_job_id}",
    name="Update print job",
    description="Update any attribute of a print job.",
    response_model_exclude_none=True,
    response_model=PrintJob,
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def update(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    print_job_id: int,
    body: PrintJobUpdateParameters,
):
    patch_data = body.model_dump(exclude_unset=True)

    if "spool_usages" in patch_data:
        patch_data["spool_usages"] = [
            {"spool_id": su.spool_id, "weight_used": su.weight_used}
            for su in body.spool_usages
        ]

    try:
        db_item = await print_job.update(
            db=db,
            print_job_id=print_job_id,
            data=patch_data,
        )
        return PrintJob.from_db(db_item)
    except ValueError as e:
        return JSONResponse(status_code=400, content=Message(message=str(e)).model_dump())


@router.delete(
    "/{print_job_id}",
    name="Delete print job",
    description="Delete a print job.",
    responses={
        400: {"model": Message},
        404: {"model": Message},
    },
)
async def delete(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    print_job_id: int,
):
    try:
        await print_job.delete(db, print_job_id)
        return Message(message="Success!")
    except ItemDeleteError as e:
        return JSONResponse(
            status_code=400,
            content={"message": str(e)},
        )
```

### 4.4. Registration in `spoolman/api/v1/router.py`
Add the imports and registrations inside `spoolman/api/v1/router.py`:

```python
# Import the new routers:
from . import project, plate, print_job

# Include the new routers:
app.include_router(project.router)
app.include_router(plate.router)
app.include_router(print_job.router)
```

---

## 5. Verification Method

Once the implementer writes these files, the entire project functionality can be verified by running:
```bash
python tests_integration/run.py sqlite
```
This script runs the integration tests against a temporary SQLite instance.
Expected result: The 15 tests for CRUD (Tiers 1-3) for Project, Plate, and PrintJob should pass with exit code 0.
Invalidation conditions: If any test throws a validation or response mismatch error, verify that Pydantic properties (`min_length=1`, `ge=0`, etc.) are exact, and confirm headers like `"x-total-count"` are present in the response headers.
