"""Print Job boundary and relationship validation integration tests."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_print_job_invalid_plate_id():
    """Test creating a print job with a non-existent plate ID."""
    result = httpx.post(
        f"{URL}/api/v1/print_job",
        json={
            "plate_id": 999999,
            "status": "pending",
        },
    )
    assert result.status_code in (400, 404, 422)


def test_create_print_job_invalid_spool_id(random_plate: dict[str, Any]):
    """Test creating a print job with a non-existent spool ID in usages."""
    result = httpx.post(
        f"{URL}/api/v1/print_job",
        json={
            "plate_id": random_plate["id"],
            "status": "printing",
            "spool_usages": [
                {
                    "spool_id": 999999,
                    "weight_used": 10.0,
                }
            ],
        },
    )
    assert result.status_code in (400, 404, 422)


def test_create_print_job_negative_weight(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test creating a print job with negative weight usage."""
    # Create spool
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()

    try:
        result = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": -5.0,
                    }
                ],
            },
        )
        assert result.status_code in (400, 422)
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_delete_plate_fails_with_print_jobs(random_plate: dict[str, Any]):
    """Test that deleting a plate fails (or returns conflict) when it has associated print jobs."""
    # Create a print job under the plate
    job_res = httpx.post(
        f"{URL}/api/v1/print_job",
        json={
            "plate_id": random_plate["id"],
            "status": "pending",
        },
    )
    job_res.raise_for_status()
    job = job_res.json()

    try:
        # Attempt to delete plate
        del_res = httpx.delete(f"{URL}/api/v1/plate/{random_plate['id']}")
        assert del_res.status_code in (400, 409)
    finally:
        # Clean up job
        try:
            httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_create_print_job_chronological_time_validation(random_plate: dict[str, Any]):
    """Test that end_time before start_time fails validation."""
    result = httpx.post(
        f"{URL}/api/v1/print_job",
        json={
            "plate_id": random_plate["id"],
            "status": "successful",
            "start_time": "2023-01-02T12:00:00Z",
            "end_time": "2023-01-02T11:00:00Z",
        },
    )
    assert result.status_code in (400, 422)
