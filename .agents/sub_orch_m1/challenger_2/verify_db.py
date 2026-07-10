import asyncio
import os
import sys
import tempfile
import sqlite3
from datetime import datetime

# Add project root to sys.path to allow imports of spoolman
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text
from alembic.config import Config
from alembic import command

# Import models
from spoolman.database.models import Base, Project, Plate, PrintJob, Printer

async def test_model_behavior():
    print("--- Testing Model Behavior ---")
    # Use in-memory SQLite database for model behavior testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as session:
        # Create prerequisite project and plate
        now = datetime.utcnow()
        project = Project(registered=now, name="Test Project")
        session.add(project)
        await session.flush()

        plate = Plate(registered=now, project_id=project.id, name="Test Plate")
        session.add(plate)
        await session.flush()

        print("1. Testing adding a print job with printer_name creates a printer automatically...")
        job1 = PrintJob(
            registered=now,
            plate_id=plate.id,
            status="printing",
            printer_name="Ender 3 Pro",
        )
        session.add(job1)
        await session.flush()
        
        assert job1.printer is not None, "Printer relationship should not be None"
        assert job1.printer.name == "Ender 3 Pro", "Printer name should match getter value"
        assert job1.printer_name == "Ender 3 Pro", "printer_name property should return Ender 3 Pro"

        print("2. Testing setting printer_name to None clears the printer...")
        job1.printer_name = None
        await session.flush()
        assert job1.printer is None, "Printer should be cleared"
        assert job1.printer_id is None, "Printer ID should be cleared"
        assert job1.printer_name is None, "printer_name getter should return None"

        print("3. Testing setting printer_name to empty string clears the printer...")
        job1.printer_name = "Ender 3 Pro"
        await session.flush()
        assert job1.printer is not None
        job1.printer_name = ""
        await session.flush()
        assert job1.printer is None, "Printer should be cleared"
        assert job1.printer_id is None, "Printer ID should be cleared"

        print("4. Testing multiple print jobs can refer to the same printer...")
        printer_instance = Printer(name="Shared Printer")
        session.add(printer_instance)
        await session.flush()

        job2 = PrintJob(
            registered=now,
            plate_id=plate.id,
            status="printing",
            printer=printer_instance,
        )
        job3 = PrintJob(
            registered=now,
            plate_id=plate.id,
            status="printing",
            printer=printer_instance,
        )
        session.add_all([job2, job3])
        await session.flush()

        assert job2.printer_id == printer_instance.id
        assert job3.printer_id == printer_instance.id
        assert job2.printer == job3.printer

        await session.commit()
        print("Model behavior tests PASSED!")
    
    await engine.dispose()

def run_migration_tests():
    print("\n--- Testing Alembic Migration ---")
    # Setup temporary file for SQLite database
    temp_db_fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(temp_db_fd)
    
    try:
        # Construct Alembic Config pointing to project root
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path}")

        print("1. Running upgrade to down_revision: fdc4cb99d052...")
        command.upgrade(alembic_cfg, "fdc4cb99d052")

        # Connect synchronously to insert test data before the target migration
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Check existing table print_job to verify printer_name column exists
        cursor.execute("PRAGMA table_info(print_job)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "printer_name" in columns, "printer_name should exist before migration"
        assert "printer_id" not in columns, "printer_id should not exist before migration"

        # Insert dummy project and plate records to satisfy foreign keys
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO project (registered, name) VALUES (?, ?)", (now_str, "Proj1"))
        project_id = cursor.lastrowid
        cursor.execute("INSERT INTO plate (registered, project_id, name) VALUES (?, ?, ?)", (now_str, project_id, "Plate1"))
        plate_id = cursor.lastrowid

        # Insert test jobs:
        # - Job 1: Valid printer_name 'Ender 3'
        # - Job 2: Valid printer_name 'Prusa i3'
        # - Job 3: Duplicate printer_name 'Ender 3'
        # - Job 4: NULL printer_name
        # - Job 5: Empty printer_name ''
        jobs = [
            (1, now_str, plate_id, "printing", "Ender 3", "Job 1 comment"),
            (2, now_str, plate_id, "printing", "Prusa i3", "Job 2 comment"),
            (3, now_str, plate_id, "printing", "Ender 3", "Job 3 comment"),
            (4, now_str, plate_id, "printing", None, "Job 4 comment"),
            (5, now_str, plate_id, "printing", "", "Job 5 comment"),
        ]
        cursor.executemany(
            "INSERT INTO print_job (id, registered, plate_id, status, printer_name, comment) VALUES (?, ?, ?, ?, ?, ?)",
            jobs
        )
        conn.commit()
        conn.close()

        print("2. Running upgrade to revision: c0e86b24d77b...")
        command.upgrade(alembic_cfg, "c0e86b24d77b")

        # Verify database state after upgrade
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Check printer table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='printer'")
        assert cursor.fetchone() is not None, "printer table should exist after migration"

        # Check distinct printer records were created
        cursor.execute("SELECT id, name FROM printer ORDER BY id")
        printers = cursor.fetchall()
        print(f"Created printers: {printers}")
        assert len(printers) == 2, "Only two distinct printers should be created"
        printer_names = [p[1] for p in printers]
        assert "Ender 3" in printer_names, "Ender 3 printer should be created"
        assert "Prusa i3" in printer_names, "Prusa i3 printer should be created"
        assert None not in printer_names and "" not in printer_names, "Null or empty printer names should be excluded"

        # Check print_job table columns
        cursor.execute("PRAGMA table_info(print_job)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "printer_name" not in columns, "printer_name should be dropped after migration"
        assert "printer_id" in columns, "printer_id should be added after migration"

        # Check updated print jobs and links to printer table
        cursor.execute("SELECT id, printer_id, comment FROM print_job ORDER BY id")
        updated_jobs = cursor.fetchall()
        print(f"Migrated print jobs: {updated_jobs}")
        # Job 1 and Job 3 should point to the same Ender 3 printer_id
        # Job 2 should point to Prusa i3
        # Job 4 and Job 5 should have NULL printer_id
        ender_printer_id = [p[0] for p in printers if p[1] == "Ender 3"][0]
        prusa_printer_id = [p[0] for p in printers if p[1] == "Prusa i3"][0]

        assert updated_jobs[0][1] == ender_printer_id, "Job 1 should link to Ender 3"
        assert updated_jobs[2][1] == ender_printer_id, "Job 3 should link to Ender 3"
        assert updated_jobs[1][1] == prusa_printer_id, "Job 2 should link to Prusa i3"
        assert updated_jobs[3][1] is None, "Job 4 (NULL printer_name) should have NULL printer_id"
        assert updated_jobs[4][1] is None, "Job 5 (empty printer_name) should have NULL printer_id"

        print("3. Running downgrade to down_revision: fdc4cb99d052...")
        command.downgrade(alembic_cfg, "fdc4cb99d052")

        # Verify database state after downgrade
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='printer'")
        assert cursor.fetchone() is None, "printer table should be dropped after downgrade"

        cursor.execute("PRAGMA table_info(print_job)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "printer_name" in columns, "printer_name column should be restored after downgrade"
        assert "printer_id" not in columns, "printer_id column should be dropped after downgrade"

        cursor.execute("SELECT id, printer_name, comment FROM print_job ORDER BY id")
        downgraded_jobs = cursor.fetchall()
        print(f"Downgraded print jobs: {downgraded_jobs}")
        assert downgraded_jobs[0][1] == "Ender 3", "Job 1 printer_name should be restored to Ender 3"
        assert downgraded_jobs[1][1] == "Prusa i3", "Job 2 printer_name should be restored to Prusa i3"
        assert downgraded_jobs[2][1] == "Ender 3", "Job 3 printer_name should be restored to Ender 3"
        assert downgraded_jobs[3][1] is None, "Job 4 printer_name should be restored to NULL"
        assert downgraded_jobs[4][1] is None, "Job 5 printer_name should be restored to NULL (or empty/NULL depending on mapping, original was empty but restored from null printer_id, so NULL is correct)"

        conn.close()
        print("Alembic migration upgrade/downgrade tests PASSED!")

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)

if __name__ == "__main__":
    asyncio.run(test_model_behavior())
    run_migration_tests()
