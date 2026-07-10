# Proposed additions to spoolman/api/v1/models.py

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from spoolman.api.v1.models import SpoolmanDateTime, Spool, Event, EventType
from spoolman.database import models


class Project(BaseModel):
    id: int = Field(description="Unique internal ID of this project.")
    registered: SpoolmanDateTime = Field(description="When the project was registered in the database. UTC Timezone.")
    name: str = Field(max_length=256, description="Project name.", examples=["Spec Project"])
    description: str | None = Field(
        None,
        max_length=1024,
        description="Free text description about this project.",
        examples=["Desc"],
    )
    link: str | None = Field(
        None,
        max_length=1024,
        description="URL link related to this project.",
        examples=["http://lnk"],
    )

    @staticmethod
    def from_db(item: models.Project) -> "Project":
        """Create a Pydantic project object from a database project object."""
        return Project(
            id=item.id,
            registered=item.registered,
            name=item.name,
            description=item.description,
            link=item.link,
        )


class Plate(BaseModel):
    id: int = Field(description="Unique internal ID of this plate.")
    registered: SpoolmanDateTime = Field(description="When the plate was registered in the database. UTC Timezone.")
    project_id: int = Field(description="The ID of the project this plate belongs to.")
    project: Project | None = Field(None, description="The project this plate belongs to.")
    name: str = Field(max_length=256, description="Plate name.", examples=["Spec Plate"])
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

    @staticmethod
    def from_db(item: models.Plate) -> "Plate":
        """Create a Pydantic plate object from a database plate object."""
        return Plate(
            id=item.id,
            registered=item.registered,
            project_id=item.project_id,
            project=Project.from_db(item.project) if getattr(item, "project", None) is not None else None,
            name=item.name,
            file_path=item.file_path,
            estimated_weight=item.estimated_weight,
            estimated_time=item.estimated_time,
            comment=item.comment,
        )


class PrintJobSpool(BaseModel):
    spool_id: int = Field(description="The ID of the spool used.")
    spool: Spool | None = Field(None, description="The spool used.")
    weight_used: float = Field(ge=0.0, description="The weight of filament consumed from the spool in grams.", examples=[150.0])

    @staticmethod
    def from_db(item: models.PrintJobSpool) -> "PrintJobSpool":
        """Create a Pydantic print job spool object from a database print job spool object."""
        return PrintJobSpool(
            spool_id=item.spool_id,
            spool=Spool.from_db(item.spool) if getattr(item, "spool", None) is not None else None,
            weight_used=item.weight_used,
        )


class PrintJob(BaseModel):
    id: int = Field(description="Unique internal ID of this print job.")
    registered: SpoolmanDateTime = Field(description="When the print job was registered in the database. UTC Timezone.")
    plate_id: int = Field(description="The ID of the plate printed.")
    plate: Plate | None = Field(None, description="The plate printed.")
    status: str = Field(description="Status of the print job (e.g. pending, printing, successful, failed).", examples=["printing"])
    start_time: SpoolmanDateTime | None = Field(None, description="When the print job started.")
    end_time: SpoolmanDateTime | None = Field(None, description="When the print job ended.")
    printer_name: str | None = Field(None, max_length=256, description="Name of the printer that executed the job.", examples=["Ender 3"])
    comment: str | None = Field(None, max_length=1024, description="Free text comment about the job.")
    spool_usages: list[PrintJobSpool] = Field(default=[], description="Filament consumption per spool.")

    @staticmethod
    def from_db(item: models.PrintJob) -> "PrintJob":
        """Create a Pydantic print job object from a database print job object."""
        return PrintJob(
            id=item.id,
            registered=item.registered,
            plate_id=item.plate_id,
            plate=Plate.from_db(item.plate) if getattr(item, "plate", None) is not None else None,
            status=item.status,
            start_time=item.start_time,
            end_time=item.end_time,
            printer_name=item.printer_name,
            comment=item.comment,
            spool_usages=[PrintJobSpool.from_db(usage) for usage in (item.spool_usages or [])],
        )


# Websocket events for Project, Plate, and PrintJob

class ProjectEvent(Event):
    payload: Project = Field(description="Updated project.")
    resource: Literal["project"] = Field(description="Resource type.")


class PlateEvent(Event):
    payload: Plate = Field(description="Updated plate.")
    resource: Literal["plate"] = Field(description="Resource type.")


class PrintJobEvent(Event):
    payload: PrintJob = Field(description="Updated print job.")
    resource: Literal["print_job"] = Field(description="Resource type.")
