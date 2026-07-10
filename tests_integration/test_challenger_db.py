import os
import shutil
import asyncio
from pathlib import Path
import logging

# Set env vars BEFORE importing spoolman modules
temp_data_dir = "/tmp/spoolman_test_challenger"
os.environ["SPOOLMAN_DIR_DATA"] = temp_data_dir
os.environ["SPOOLMAN_DB_TYPE"] = "sqlite"

from alembic.config import Config
from alembic import command
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from spoolman.database.database import get_connection_url, setup_db, get_db_session
from spoolman.database import models
from spoolman.database.models import Printer, PrintJob, Plate, Base

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_challenger_db")

def cleanup_temp_db():
    if os.path.exists(temp_data_dir):
        shutil.rmtree(temp_data_dir)

def run_alembic_command(cmd_name, *args, **kwargs):
    alembic_cfg = Config("alembic.ini")
    func = getattr(command, cmd_name)
    func(alembic_cfg, *args, **kwargs)

async def test_models():
    # Setup spoolman DB session
    url = get_connection_url()
    setup_db(url)
    
    # Yield a session
    async for session in get_db_session():
        # First, create a test Plate because PrintJob has plate_id FK
        from datetime import datetime
        project = models.Project(name="Test Project", registered=datetime.utcnow())
        session.add(project)
        await session.flush()
        
        plate = models.Plate(name="Test Plate", project_id=project.id, registered=datetime.utcnow())
        session.add(plate)
        await session.flush()
        
        from spoolman.database import printer as db_printer
        from spoolman.database import print_job as db_print_job

        # Test 1: Adding a print job with printer_id.
        logger.info("Testing: Adding a print job with printer_id...")
        p1 = await db_printer.create(
            db=session,
            name="Ender 3"
        )
        job1 = await db_print_job.create(
            db=session,
            plate_id=plate.id,
            status="pending",
            printer_id=p1.id,
        )
        
        assert job1.printer is not None, "Printer should be associated"
        assert job1.printer.name == "Ender 3"
        assert job1.printer_name == "Ender 3"
        assert job1.printer_id == p1.id
        
        # Test 2: Setting printer_id to None clears the printer.
        logger.info("Testing: Setting printer_id to None clears the printer...")
        job1 = await db_print_job.update(
            db=session,
            print_job_id=job1.id,
            data={"printer_id": None}
        )
        assert job1.printer is None
        assert job1.printer_name is None
        assert job1.printer_id is None
        
        # Test 3: Multiple print jobs can refer to the same printer.
        logger.info("Testing: Multiple print jobs can refer to the same printer...")
        shared_printer = await db_printer.create(db=session, name="Shared Prusa")
        
        job2 = await db_print_job.create(
            db=session,
            plate_id=plate.id,
            status="pending",
            printer_id=shared_printer.id,
        )
        job3 = await db_print_job.create(
            db=session,
            plate_id=plate.id,
            status="pending",
            printer_id=shared_printer.id,
        )
        
        assert job2.printer.id == shared_printer.id
        assert job3.printer.id == shared_printer.id
        assert job2.printer_name == "Shared Prusa"
        assert job3.printer_name == "Shared Prusa"
        
        # Test 4: Updating printer_id to a different printer.
        logger.info("Testing: Updating printer_id...")
        p2 = await db_printer.create(db=session, name="Modified Prusa")
        job2 = await db_print_job.update(
            db=session,
            print_job_id=job2.id,
            data={"printer_id": p2.id}
        )
        assert job2.printer_id == p2.id
        assert job2.printer_name == "Modified Prusa"
        # The other job must still refer to the original Shared Prusa printer
        assert job3.printer.id == shared_printer.id
        assert job3.printer_name == "Shared Prusa"
        
        # rollback to keep clean
        await session.rollback()
        break
    logger.info("Model tests PASSED successfully!")

def test_migration_and_data_preservation():
    # Make sure we start fresh
    cleanup_temp_db()
    os.makedirs(temp_data_dir, exist_ok=True)
    
    # 1. Upgrade to the revision prior to c0e86b24d77b
    logger.info("Upgrading DB to fdc4cb99d052 (prior revision)...")
    run_alembic_command("upgrade", "fdc4cb99d052")
    
    # 2. Insert test data directly using SQL
    db_path = Path(temp_data_dir) / "spoolman.db"
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO project (id, registered, name) VALUES (1, '2026-07-10 12:00:00', 'Test Project')")
    cursor.execute("INSERT INTO plate (id, registered, project_id, name) VALUES (1, '2026-07-10 12:00:00', 1, 'Test Plate')")
    
    # Insert various print_jobs:
    # 1. Null printer_name
    # 2. Empty printer_name
    # 3. "Ender 3"
    # 4. "Ender 3" (duplicate)
    # 5. "Prusa i3"
    cursor.execute("""
        INSERT INTO print_job (id, registered, plate_id, status, printer_name)
        VALUES (1, '2026-07-10 12:00:00', 1, 'pending', NULL)
    """)
    cursor.execute("""
        INSERT INTO print_job (id, registered, plate_id, status, printer_name)
        VALUES (2, '2026-07-10 12:00:00', 1, 'pending', '')
    """)
    cursor.execute("""
        INSERT INTO print_job (id, registered, plate_id, status, printer_name)
        VALUES (3, '2026-07-10 12:00:00', 1, 'pending', 'Ender 3')
    """)
    cursor.execute("""
        INSERT INTO print_job (id, registered, plate_id, status, printer_name)
        VALUES (4, '2026-07-10 12:00:00', 1, 'pending', 'Ender 3')
    """)
    cursor.execute("""
        INSERT INTO print_job (id, registered, plate_id, status, printer_name)
        VALUES (5, '2026-07-10 12:00:00', 1, 'pending', 'Prusa i3')
    """)
    
    conn.commit()
    conn.close()
    
    # 3. Upgrade to revision c0e86b24d77b
    logger.info("Upgrading to c0e86b24d77b (add_printer_table)...")
    run_alembic_command("upgrade", "c0e86b24d77b")
    
    # 4. Verify post-upgrade data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verify printer table exists and has exact distinct printers
    cursor.execute("SELECT id, name FROM printer ORDER BY name")
    printers = cursor.fetchall()
    logger.info(f"Created printers: {printers}")
    assert len(printers) == 2, "There should be exactly 2 printers"
    assert printers[0][1] == "Ender 3"
    assert printers[1][1] == "Prusa i3"
    ender_id = printers[0][0]
    prusa_id = printers[1][0]
    
    # Verify print jobs printer_id
    cursor.execute("SELECT id, printer_id FROM print_job ORDER BY id")
    jobs = cursor.fetchall()
    logger.info(f"Print jobs after migration: {jobs}")
    # job 1: null -> printer_id null
    assert jobs[0][1] is None, f"Job 1 should have null printer_id, got {jobs[0][1]}"
    # job 2: empty -> printer_id null
    assert jobs[1][1] is None, f"Job 2 should have null printer_id, got {jobs[1][1]}"
    # job 3: Ender 3 -> printer_id of Ender 3
    assert jobs[2][1] == ender_id, f"Job 3 should point to Ender 3, got {jobs[2][1]}"
    # job 4: Ender 3 -> printer_id of Ender 3
    assert jobs[3][1] == ender_id, f"Job 4 should point to Ender 3, got {jobs[3][1]}"
    # job 5: Prusa i3 -> printer_id of Prusa i3
    assert jobs[4][1] == prusa_id, f"Job 5 should point to Prusa i3, got {jobs[4][1]}"
    
    # Verify column printer_name is dropped
    cursor.execute("PRAGMA table_info(print_job)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "printer_name" not in columns, "printer_name column should have been dropped"
    assert "printer_id" in columns, "printer_id column should have been added"
    
    # 5. Downgrade back to fdc4cb99d052
    logger.info("Downgrading to fdc4cb99d052...")
    run_alembic_command("downgrade", "fdc4cb99d052")
    
    # 6. Verify post-downgrade data
    cursor.execute("PRAGMA table_info(print_job)")
    columns_post_down = [row[1] for row in cursor.fetchall()]
    assert "printer_name" in columns_post_down, "printer_name column should be restored"
    assert "printer_id" not in columns_post_down, "printer_id column should be dropped"
    
    # Verify print_job printer_name data is restored correctly
    cursor.execute("SELECT id, printer_name FROM print_job ORDER BY id")
    jobs_post_down = cursor.fetchall()
    logger.info(f"Print jobs after downgrade: {jobs_post_down}")
    # job 1: NULL printer_id -> NULL printer_name
    assert jobs_post_down[0][1] is None
    # job 2: NULL printer_id -> NULL printer_name
    assert jobs_post_down[1][1] is None
    # job 3: Ender 3
    assert jobs_post_down[2][1] == "Ender 3"
    # job 4: Ender 3
    assert jobs_post_down[3][1] == "Ender 3"
    # job 5: Prusa i3
    assert jobs_post_down[4][1] == "Prusa i3"
    
    # Verify printer table is dropped
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='printer'")
    assert cursor.fetchone() is None, "printer table should be dropped"
    
    conn.close()
    logger.info("Migration tests PASSED successfully!")

def main():
    try:
        cleanup_temp_db()
        test_migration_and_data_preservation()
        asyncio.run(test_models())
    finally:
        cleanup_temp_db()

if __name__ == "__main__":
    main()
