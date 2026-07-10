"""Integration tests for Print Job CRUD."""

from typing import Any
import httpx

from ..conftest import URL, random_printer_impl


def test_create_print_job(random_plate: dict[str, Any], random_printer: dict[str, Any]):
    """Test creating a print job."""
    payload = {
        "plate_id": random_plate["id"],
        "status": "printing",
        "printer_id": random_printer["id"],
        "comment": "Initial test job",
        "spool_usages": [],
    }
    result = httpx.post(f"{URL}/api/v1/print_job", json=payload)
    assert result.status_code in (200, 201)
    print_job = result.json()

    assert "id" in print_job
    assert "registered" in print_job
    assert print_job["plate_id"] == random_plate["id"]
    assert print_job["status"] == payload["status"]
    assert print_job["printer_id"] == random_printer["id"]
    assert print_job["printer_name"] == random_printer["name"]
    assert print_job["comment"] == payload["comment"]
    assert print_job["spool_usages"] == payload["spool_usages"]

    # Clean up
    httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}").raise_for_status()


def test_get_print_job(random_print_job: dict[str, Any]):
    """Test getting a print job."""
    result = httpx.get(f"{URL}/api/v1/print_job/{random_print_job['id']}")
    assert result.status_code == 200
    print_job = result.json()
    assert print_job["id"] == random_print_job["id"]
    assert print_job["printer_id"] == random_print_job["printer_id"]
    assert print_job["printer_name"] == random_print_job["printer_name"]


def test_list_print_jobs(random_print_job: dict[str, Any]):
    """Test listing print jobs."""
    result = httpx.get(f"{URL}/api/v1/print_job", params={"status": random_print_job["status"]})
    assert result.status_code == 200
    print_jobs = result.json()
    assert isinstance(print_jobs, list)
    assert len(print_jobs) >= 1
    assert any(pj["id"] == random_print_job["id"] for pj in print_jobs)
    assert "x-total-count" in result.headers


def test_patch_print_job(random_print_job: dict[str, Any]):
    """Test patching a print job."""
    with random_printer_impl() as another_printer:
        result = httpx.patch(
            f"{URL}/api/v1/print_job/{random_print_job['id']}",
            json={"printer_id": another_printer["id"]},
        )
        assert result.status_code == 200
        print_job = result.json()
        assert print_job["id"] == random_print_job["id"]
        assert print_job["printer_id"] == another_printer["id"]
        assert print_job["printer_name"] == another_printer["name"]


def test_delete_print_job(random_plate: dict[str, Any]):
    """Test deleting a print job."""
    result = httpx.post(
        f"{URL}/api/v1/print_job",
        json={"plate_id": random_plate["id"], "status": "pending"},
    )
    result.raise_for_status()
    print_job = result.json()

    del_res = httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}")
    assert del_res.status_code in (200, 204)

    get_res = httpx.get(f"{URL}/api/v1/print_job/{print_job['id']}")
    assert get_res.status_code == 404


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

