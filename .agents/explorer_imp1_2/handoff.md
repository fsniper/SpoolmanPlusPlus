# Backend API & CRUD Design Handoff Report (Milestone IMP-1)

## 1. Observation
Below are the direct observations from the Spoolman codebase, including database models, API structures, and integration tests:

### Database Models
- `spoolman/database/models.py` already contains the SQLAlchemy classes for `Project`, `Plate`, `PrintJob`, and `PrintJobSpool`.
  - **Project** (lines 121-130):
    ```python
    class Project(Base):
        __tablename__ = "project"
        id: Mapped[int] = mapped_column(primary_key=True, index=True)
        registered: Mapped[datetime] = mapped_column()
        name: Mapped[str] = mapped_column(String(256))
        description: Mapped[str | None] = mapped_column(String(1024))
        link: Mapped[str | None] = mapped_column(String(1024))
        plates: Mapped[list["Plate"]] = relationship(back_populates="project")
    ```
  - **Plate** (lines 132-145):
    ```python
    class Plate(Base):
        __tablename__ = "plate"
        id: Mapped[int] = mapped_column(primary_key=True, index=True)
        registered: Mapped[datetime] = mapped_column()
        project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
        project: Mapped["Project"] = relationship(back_populates="plates")
        name: Mapped[str] = mapped_column(String(256))
        file_path: Mapped[str | None] = mapped_column(String(1024))
        estimated_weight: Mapped[float | None] = mapped_column()
        estimated_time: Mapped[int | None] = mapped_column(comment="Estimated time in seconds")
        comment: Mapped[str | None] = mapped_column(String(1024))
        print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="plate")
    ```
  - **PrintJob** (lines 147-160):
    ```python
    class PrintJob(Base):
        __tablename__ = "print_job"
        id: Mapped[int] = mapped_column(primary_key=True, index=True)
        registered: Mapped[datetime] = mapped_column()
        plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"))
        plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
        status: Mapped[str] = mapped_column(String(64))
        start_time: Mapped[datetime | None] = mapped_column()
        end_time: Mapped[datetime | None] = mapped_column()
        printer_name: Mapped[str | None] = mapped_column(String(256))
        comment: Mapped[str | None] = mapped_column(String(1024))
        spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")
    ```
  - **PrintJobSpool** (lines 162-171):
    ```python
    class PrintJobSpool(Base):
        __tablename__ = "print_job_spool"
        id: Mapped[int] = mapped_column(primary_key=True, index=True)
        print_job_id: Mapped[int] = mapped_column(ForeignKey("print_job.id"))
        print_job: Mapped["PrintJob"] = relationship(back_populates="spool_usages")
        spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"))
        spool: Mapped["Spool"] = relationship()
        weight_used: Mapped[float] = mapped_column()
    ```

### Extra Field Registry
- `spoolman/extra_field_registry.py` defines custom entities in `EntityType`:
  ```python
  class EntityType(Enum):
      vendor = "vendor"
      filament = "filament"
      spool = "spool"
  ```
  Neither `project`, `plate`, nor `print_job` are registered as entities with extra fields.

### API Architecture and Routing
- `spoolman/api/v1/router.py` (lines 107-114) includes routers for various entities using:
  ```python
  app.include_router(filament.router)
  app.include_router(spool.router)
  app.include_router(vendor.router)
  ```
- Request/update Pydantic schemas (e.g. `VendorParameters`, `VendorUpdateParameters`) are defined within their respective router files (e.g. `vendor.py`), while primary models (e.g. `Vendor`, `Filament`, `Spool`) are defined in `spoolman/api/v1/models.py`.

### Integration Tests Requirements
- **Constraints / Inputs Validation**:
  - `tests_integration/tests/project/test_crud.py` requires names to be non-empty and at most 256 characters long. Empty names or 257-character names must return 400 or 422.
  - `tests_integration/tests/plate/test_boundaries.py` requires `estimated_weight` and `estimated_time` to be non-negative.
  - `tests_integration/tests/print_job/test_boundaries.py` requires chronological validation: `end_time` before `start_time` must fail.
- **Cascade Blocking**:
  - `tests_integration/tests/plate/test_boundaries.py` tests that deleting a project with associated plates fails with 400/409.
  - `tests_integration/tests/print_job/test_boundaries.py` tests that deleting a plate with associated print jobs fails with 400/409.
- **Pagination & Response Headers**:
  - Lists must return standard Python lists of the entities.
  - The HTTP header `x-total-count` containing the total match count must be present in the response headers.
- **Spool Weight Deduction**:
  - Status transitions to `successful` (either at creation time or during update) deduct `weight_used` from spools.
  - Transitions away from `successful` or deleting a successful print job refund the weight.

---

## 2. Logic Chain
Based on the observations:
1. Since `Project`, `Plate`, and `PrintJob` models already exist in the database models, we do not need to create new SQLAlchemy models or run migrations for tables.
2. Since there are no extra fields for project/plate/print_job, we do not need to integrate custom fields validation (`get_extra_fields`, `validate_extra_field_dict`) or custom field query/sorting logic in database search.
3. FastAPI's Pydantic validation can automatically return a 422 Unprocessable Entity error if we configure parameter schemas with appropriate constraints:
   - For names: `min_length=1, max_length=256`
   - For numbers: `ge=0`
   - For `PrintJobParameters` and `PrintJobUpdateParameters`: a class-level `@model_validator(mode="after")` to verify `end_time >= start_time` when both are provided.
4. Database helper functions should catch `sqlalchemy.exc.IntegrityError` during deletion and raise `ItemDeleteError`, which the API router catches and returns as a 409 status code to satisfy cascade blocking tests.
5. In print_job creation, update, and deletion, we need to inspect the status of the print job to manage weight deductions and refunds.
   - Deduction condition: `status == "successful"`.
   - On create: if successful, call `spool.use_weight(db, usage.spool_id, usage.weight_used)` for each usage.
   - On update: if transitioning from non-successful to successful, apply deductions. If transitioning from successful to non-successful, refund by calling `use_weight(db, usage.spool_id, -usage.weight_used)`.
   - On delete: if current status is successful, refund by calling `use_weight(db, usage.spool_id, -usage.weight_used)` for each usage before deleting the database records.

---

## 3. Caveats
- **Automatic Weight Deduction Logic**: The weight deduction logic is formally part of IMP-2, but the database schema and CRUD operations implemented in IMP-1 must be fully prepared to support it (meaning the relationship mapping, creation/deletion of `PrintJobSpool`, and endpoints must exist).
- **Timezone Handling**: Ensure datetimes are serialized to UTC/naive ISO strings with a `Z` suffix. Using `SpoolmanDateTime` alias handles this automatically.

---

## 4. Conclusion
We propose the following concrete implementation design for Milestone IMP-1:

### A. Modifications & Additions to `spoolman/api/v1/models.py`

Add the following Pydantic schemas:

```python
from typing import Literal

# --- Project Models ---

class Project(BaseModel):
    id: int = Field(description="Unique internal ID of this project.")
    registered: SpoolmanDateTime = Field(description="When the project was registered in the database. UTC Timezone.")
    name: str = Field(max_length=256, description="Project name.", examples=["Spec Project"])
    description: str | None = Field(None, max_length=1024, description="Optional description.")
    link: str | None = Field(None, max_length=1024, description="Optional URL link.")

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


# --- Plate Models ---

class Plate(BaseModel):
    id: int = Field(description="Unique internal ID of this build plate.")
    registered: SpoolmanDateTime = Field(description="When the plate was registered. UTC Timezone.")
    project_id: int = Field(description="Associated project ID.")
    name: str = Field(max_length=256, description="Plate name.", examples=["Plate Alpha"])
    file_path: str | None = Field(None, max_length=1024, description="Optional G-code file path.")
    estimated_weight: float | None = Field(None, ge=0, description="Estimated filament weight in grams.")
    estimated_time: int | None = Field(None, ge=0, description="Estimated printing time in seconds.")
    comment: str | None = Field(None, max_length=1024, description="Optional comment.")

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


# --- Print Job Models ---

class PrintJobSpool(BaseModel):
    spool_id: int = Field(description="Spool ID used.")
    weight_used: float = Field(ge=0, description="Weight used from this spool in grams.")

    @staticmethod
    def from_db(item: models.PrintJobSpool) -> "PrintJobSpool":
        return PrintJobSpool(
            spool_id=item.spool_id,
            weight_used=item.weight_used,
        )

class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered. UTC Timezone.")
    plate_id: int = Field(description="Associated plate ID.")
    status: str = Field(max_length=64, description="Status of the print job (e.g. successful, pending).")
    start_time: SpoolmanDateTime | None = Field(None, description="Start time. UTC Timezone.")
    end_time: SpoolmanDateTime | None = Field(None, description="End time. UTC Timezone.")
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
            printer_name=item.printer_name,
            comment=item.comment,
            spool_usages=[PrintJobSpool.from_db(u) for u in item.spool_usages] if item.spool_usages else [],
        )

class PrintJobEvent(Event):
    payload: PrintJob = Field(description="Updated print job.")
    resource: Literal["print_job"] = Field(description="Resource type.")
```

### B. New Database Helpers

#### `spoolman/database/project.py`
Helper routines for interacting with the Project table:
- **`create`**: Instantiates `models.Project`, registered time, saves, commits, and sends `project_changed` event.
- **`get_by_id`**: Fetches Project by ID or raises `ItemNotFoundError`.
- **`find`**: Fetches all projects matching filter `name`, implements pagination (`limit`, `offset`) and sorting. Returns `list[models.Project]` and total count.
- **`update`**: Updates attributes and triggers changed event.
- **`delete`**: Deletes project; catches `IntegrityError` and raises `ItemDeleteError`.

#### `spoolman/database/plate.py`
Helper routines for interacting with the Plate table:
- **`create`**: Validates `project_id` exists, instantiates `models.Plate`, registered time, saves, commits, and sends `plate_changed` event.
- **`get_by_id`**: Fetches Plate by ID or raises `ItemNotFoundError`.
- **`find`**: Fetches plates matching filter `project_id` and/or `name`, implements pagination and sorting. Returns `list[models.Plate]` and total count.
- **`update`**: Updates attributes, validates `project_id` if changed, and triggers changed event.
- **`delete`**: Deletes plate; catches `IntegrityError` and raises `ItemDeleteError`.

#### `spoolman/database/print_job.py`
Helper routines for interacting with the PrintJob table:
- **`create`**: Validates `plate_id` and all `spool_id`s exist, validates chronological times. Saves `PrintJob` and `PrintJobSpool` records. If status is `"successful"`, applies weight deduction to spools using `spool.use_weight`.
- **`get_by_id`**: Fetches PrintJob, preloading `spool_usages` via `joinedload(models.PrintJob.spool_usages)`.
- **`find`**: Fetches print jobs matching `plate_id` and/or `status`, implements pagination and sorting.
- **`update`**: Updates attributes. Handles transitioning of status to/from `"successful"` to deduct/refund spool weight, and updates `spool_usages` collection.
- **`delete`**: If current status is `"successful"`, refunds weight to spools. Deletes child `PrintJobSpool` records, then deletes `PrintJob`.

### C. New API Router Files

Create `project.py`, `plate.py`, and `print_job.py` under `spoolman/api/v1/`. They will implement:
- `GET`: find matching records, serialize output using the respective `from_db` helper, and return the pagination header `x-total-count`.
- `POST`: parse incoming parameters (e.g. `ProjectParameters`), execute creation, and return 201/200.
- `GET /{id}`: fetch detailed item.
- `PATCH /{id}`: validate fields and perform updates.
- `DELETE /{id}`: execute deletion, catching `ItemDeleteError` to return 409 Conflict.
- `WebSocket`: websocket routing for live notifications.

### D. Registration in `spoolman/api/v1/router.py`

Import new routers:
```python
from . import project, plate, print_job
```
And add inclusion statements:
```python
app.include_router(project.router)
app.include_router(plate.router)
app.include_router(print_job.router)
```

---

## 5. Verification Method
Verify the design and implementation by executing the integration test suite:

```bash
# Execute integration tests for the project, plate, and print_job modules
python tests_integration/run.py sqlite
```

### Invalidation Conditions
- If the integration test commands fail due to any schema validation discrepancies.
- If the `x-total-count` header is missing in any list responses.
- If status code for deleted parent entities with active children is not 400 or 409.
- If print job times are not checked for chronological validity.
