"""Plate boundary and relationship validation integration tests."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_plate_invalid_project_id():
    """Test creating a plate with a non-existent project ID."""
    result = httpx.post(
        f"{URL}/api/v1/plate",
        json={
            "project_id": 999999,
            "name": "Invalid Plate",
        },
    )
    assert result.status_code in (400, 404, 422)


def test_create_plate_negative_inputs(random_project: dict[str, Any]):
    """Test creating a plate with negative inputs."""
    # Negative weight
    result = httpx.post(
        f"{URL}/api/v1/plate",
        json={
            "project_id": random_project["id"],
            "name": "Plate Neg Weight",
            "estimated_weight": -10.0,
        },
    )
    assert result.status_code in (400, 422)

    # Negative time
    result = httpx.post(
        f"{URL}/api/v1/plate",
        json={
            "project_id": random_project["id"],
            "name": "Plate Neg Time",
            "estimated_time": -3600,
        },
    )
    assert result.status_code in (400, 422)


def test_delete_project_fails_with_plates(random_project: dict[str, Any]):
    """Test that deleting a project fails (or returns conflict) when it has associated plates."""
    # Create a plate under the project
    plate_res = httpx.post(
        f"{URL}/api/v1/plate",
        json={
            "project_id": random_project["id"],
            "name": "Blocking Plate",
        },
    )
    plate_res.raise_for_status()
    plate = plate_res.json()

    try:
        # Attempt to delete project
        del_res = httpx.delete(f"{URL}/api/v1/project/{random_project['id']}")
        assert del_res.status_code in (400, 409)
    finally:
        # Clean up plate, catching and ignoring HTTPError to avoid masking assertion failures
        try:
            httpx.delete(f"{URL}/api/v1/plate/{plate['id']}").raise_for_status()
        except httpx.HTTPError:
            pass
