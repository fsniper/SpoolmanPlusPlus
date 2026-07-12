"""SQLAlchemy data models."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Vendor(Base):
    __tablename__ = "vendor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(64))
    empty_spool_weight: Mapped[float | None] = mapped_column(comment="The weight of an empty spool.")
    comment: Mapped[str | None] = mapped_column(String(1024))
    filaments: Mapped[list["Filament"]] = relationship(back_populates="vendor")
    external_id: Mapped[str | None] = mapped_column(String(256))
    extra: Mapped[list["VendorField"]] = relationship(
        back_populates="vendor",
        cascade="save-update, merge, delete, delete-orphan",
        lazy="joined",
    )


class Filament(Base):
    __tablename__ = "filament"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str | None] = mapped_column(String(64))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendor.id"))
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="filaments")
    spools: Mapped[list["Spool"]] = relationship(back_populates="filament")
    material: Mapped[str | None] = mapped_column(String(64))
    price: Mapped[float | None] = mapped_column()
    density: Mapped[float] = mapped_column()
    diameter: Mapped[float] = mapped_column()
    weight: Mapped[float | None] = mapped_column(comment="The filament weight of a full spool (net weight).")
    spool_weight: Mapped[float | None] = mapped_column(comment="The weight of an empty spool.")
    article_number: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(String(1024))
    settings_extruder_temp: Mapped[int | None] = mapped_column(comment="Overridden extruder temperature.")
    settings_bed_temp: Mapped[int | None] = mapped_column(comment="Overridden bed temperature.")
    color_hex: Mapped[str | None] = mapped_column(String(8))
    multi_color_hexes: Mapped[str | None] = mapped_column(String(128))
    multi_color_direction: Mapped[str | None] = mapped_column(String(16))
    external_id: Mapped[str | None] = mapped_column(String(256))
    extra: Mapped[list["FilamentField"]] = relationship(
        back_populates="filament",
        cascade="save-update, merge, delete, delete-orphan",
        lazy="joined",
    )


class Spool(Base):
    __tablename__ = "spool"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    first_used: Mapped[datetime | None] = mapped_column()
    last_used: Mapped[datetime | None] = mapped_column()
    price: Mapped[float | None] = mapped_column()
    filament_id: Mapped[int] = mapped_column(ForeignKey("filament.id"))
    filament: Mapped["Filament"] = relationship(back_populates="spools")
    initial_weight: Mapped[float | None] = mapped_column()
    spool_weight: Mapped[float | None] = mapped_column()
    used_weight: Mapped[float] = mapped_column()
    location: Mapped[str | None] = mapped_column(String(64))
    lot_nr: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(String(1024))
    archived: Mapped[bool | None] = mapped_column()
    extra: Mapped[list["SpoolField"]] = relationship(
        back_populates="spool",
        cascade="save-update, merge, delete, delete-orphan",
        lazy="joined",
    )


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text())
    last_updated: Mapped[datetime] = mapped_column()


class VendorField(Base):
    __tablename__ = "vendor_field"

    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor.id"), primary_key=True, index=True)
    vendor: Mapped["Vendor"] = relationship(back_populates="extra")
    key: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text())


class FilamentField(Base):
    __tablename__ = "filament_field"

    filament_id: Mapped[int] = mapped_column(ForeignKey("filament.id"), primary_key=True, index=True)
    filament: Mapped["Filament"] = relationship(back_populates="extra")
    key: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text())


class SpoolField(Base):
    __tablename__ = "spool_field"

    spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"), primary_key=True, index=True)
    spool: Mapped["Spool"] = relationship(back_populates="extra")
    key: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(Text())


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(1024))
    link: Mapped[str | None] = mapped_column(String(1024))
    plates: Mapped[list["Plate"]] = relationship(back_populates="project")
    files: Mapped[list["ProjectFile"]] = relationship(back_populates="project")


class ProjectFile(Base):
    __tablename__ = "project_file"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    project: Mapped["Project"] = relationship(back_populates="files")
    name: Mapped[str] = mapped_column(String(256))
    
    file_path: Mapped[str | None] = mapped_column(String(1024))
    size: Mapped[int | None] = mapped_column()


class Plate(Base):
    __tablename__ = "plate"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), index=True)
    project: Mapped["Project"] = relationship(back_populates="plates")
    name: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str | None] = mapped_column(String(1024))
    project_file_id: Mapped[int | None] = mapped_column(ForeignKey("project_file.id"), index=True)
    project_file: Mapped[Optional["ProjectFile"]] = relationship()
    estimated_weight: Mapped[float | None] = mapped_column()
    estimated_time: Mapped[int | None] = mapped_column(comment="Estimated time in seconds")
    comment: Mapped[str | None] = mapped_column(String(1024))
    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="plate")


class Printer(Base):
    __tablename__ = "printer"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0))
    name: Mapped[str] = mapped_column(String(256))
    model: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(256))
    comment: Mapped[str | None] = mapped_column(String(1024))

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")


class PrintJob(Base):
    __tablename__ = "print_job"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    registered: Mapped[datetime] = mapped_column()
    plate_id: Mapped[int] = mapped_column(ForeignKey("plate.id"), index=True)
    plate: Mapped["Plate"] = relationship(back_populates="print_jobs")
    status: Mapped[str] = mapped_column(String(64))
    start_time: Mapped[datetime | None] = mapped_column()
    end_time: Mapped[datetime | None] = mapped_column()
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printer.id"), index=True)
    printer: Mapped[Optional["Printer"]] = relationship(back_populates="print_jobs")
    comment: Mapped[str | None] = mapped_column(String(1024))
    spool_usages: Mapped[list["PrintJobSpool"]] = relationship(back_populates="print_job")



class PrintJobSpool(Base):
    __tablename__ = "print_job_spool"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    print_job_id: Mapped[int] = mapped_column(ForeignKey("print_job.id"), index=True)
    print_job: Mapped["PrintJob"] = relationship(back_populates="spool_usages")
    spool_id: Mapped[int] = mapped_column(ForeignKey("spool.id"), index=True)
    spool: Mapped["Spool"] = relationship()
    weight_used: Mapped[float] = mapped_column()
