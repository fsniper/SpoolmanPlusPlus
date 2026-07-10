"""Integration tests for Printer CRUD."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_printer():
    """Test creating a printer."""
    payload = {
        "name": "Spec Printer",
        "model": "MK3S",
        "location": "Lab A",
        "comment": "Nice printer",
    }
    result = httpx.post(f"{URL}/api/v1/printer", json=payload)
    assert result.status_code in (200, 201)
    printer = result.json()

    assert "id" in printer
    assert "registered" in printer
    assert printer["name"] == payload["name"]
    assert printer["model"] == payload["model"]
    assert printer["location"] == payload["location"]
    assert printer["comment"] == payload["comment"]

    # Clean up
    httpx.delete(f"{URL}/api/v1/printer/{printer['id']}").raise_for_status()


def test_get_printer(random_printer: dict[str, Any]):
    """Test getting a printer."""
    result = httpx.get(f"{URL}/api/v1/printer/{random_printer['id']}")
    assert result.status_code == 200
    printer = result.json()
    assert printer["id"] == random_printer["id"]
    assert printer["name"] == random_printer["name"]


def test_list_printers(random_printer: dict[str, Any]):
    """Test listing printers."""
    result = httpx.get(f"{URL}/api/v1/printer", params={"name": random_printer["name"]})
    assert result.status_code == 200
    printers = result.json()
    assert isinstance(printers, list)
    assert len(printers) >= 1
    assert any(p["id"] == random_printer["id"] for p in printers)
    assert "x-total-count" in result.headers


def test_patch_printer(random_printer: dict[str, Any]):
    """Test patching a printer."""
    new_name = "Updated Printer Name"
    result = httpx.patch(f"{URL}/api/v1/printer/{random_printer['id']}", json={"name": new_name})
    assert result.status_code == 200
    printer = result.json()
    assert printer["id"] == random_printer["id"]
    assert printer["name"] == new_name


def test_delete_printer():
    """Test deleting a printer."""
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={"name": "Temporary Printer"},
    )
    result.raise_for_status()
    printer = result.json()

    del_res = httpx.delete(f"{URL}/api/v1/printer/{printer['id']}")
    assert del_res.status_code in (200, 204)

    get_res = httpx.get(f"{URL}/api/v1/printer/{printer['id']}")
    assert get_res.status_code == 404


def test_create_printer_empty_name():
    """Test creating a printer with an empty name."""
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={"name": ""},
    )
    assert result.status_code in (400, 422)


def test_create_printer_long_name():
    """Test creating a printer with a name that is too long (257 chars)."""
    result = httpx.post(
        f"{URL}/api/v1/printer",
        json={"name": "a" * 257},
    )
    assert result.status_code in (400, 422)
