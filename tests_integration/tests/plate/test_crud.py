"""Integration tests for Plate CRUD."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_plate(random_project: dict[str, Any]):
    """Test creating a plate."""
    payload = {
        "project_id": random_project["id"],
        "name": "Spec Plate",
        "file_path": "test.gcode",
        "estimated_weight": 50.0,
        "estimated_time": 3600,
        "comment": "Nice plate",
    }
    result = httpx.post(f"{URL}/api/v1/plate", json=payload)
    assert result.status_code in (200, 201)
    plate = result.json()

    assert "id" in plate
    assert "registered" in plate
    assert plate["project_id"] == random_project["id"]
    assert plate["name"] == payload["name"]
    assert plate["file_path"] == payload["file_path"]
    assert plate["estimated_weight"] == payload["estimated_weight"]
    assert plate["estimated_time"] == payload["estimated_time"]
    assert plate["comment"] == payload["comment"]

    # Clean up
    httpx.delete(f"{URL}/api/v1/plate/{plate['id']}").raise_for_status()


def test_get_plate(random_plate: dict[str, Any]):
    """Test getting a plate."""
    result = httpx.get(f"{URL}/api/v1/plate/{random_plate['id']}")
    assert result.status_code == 200
    plate = result.json()
    assert plate["id"] == random_plate["id"]
    assert plate["name"] == random_plate["name"]


def test_list_plates(random_plate: dict[str, Any]):
    """Test listing plates."""
    result = httpx.get(f"{URL}/api/v1/plate", params={"project_id": random_plate["project_id"]})
    assert result.status_code == 200
    plates = result.json()
    assert isinstance(plates, list)
    assert len(plates) >= 1
    assert any(p["id"] == random_plate["id"] for p in plates)
    assert "x-total-count" in result.headers


def test_patch_plate(random_plate: dict[str, Any]):
    """Test patching a plate."""
    new_weight = 60.0
    result = httpx.patch(f"{URL}/api/v1/plate/{random_plate['id']}", json={"estimated_weight": new_weight})
    assert result.status_code == 200
    plate = result.json()
    assert plate["id"] == random_plate["id"]
    assert plate["estimated_weight"] == new_weight


def test_delete_plate(random_project: dict[str, Any]):
    """Test deleting a plate."""
    result = httpx.post(
        f"{URL}/api/v1/plate",
        json={"project_id": random_project["id"], "name": "Temporary Plate"},
    )
    result.raise_for_status()
    plate = result.json()

    del_res = httpx.delete(f"{URL}/api/v1/plate/{plate['id']}")
    assert del_res.status_code in (200, 204)

    get_res = httpx.get(f"{URL}/api/v1/plate/{plate['id']}")
    assert get_res.status_code == 404
