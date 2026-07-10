"""Integration tests for Printer CRUD."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_printer():
    """Test creating a printer."""
    payload = {
        "name": "Prusa i3",
        "model": "MK3S+",
        "location": "Makerspace",
        "comment": "Works well",
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
    """Test listing printers with filters."""
    result = httpx.get(f"{URL}/api/v1/printer", params={"name": random_printer["name"]})
    assert result.status_code == 200
    printers = result.json()
    assert isinstance(printers, list)
    assert len(printers) >= 1
    assert any(p["id"] == random_printer["id"] for p in printers)
    assert "x-total-count" in result.headers


def test_patch_printer(random_printer: dict[str, Any]):
    """Test patching a printer."""
    new_location = "Office"
    result = httpx.patch(f"{URL}/api/v1/printer/{random_printer['id']}", json={"location": new_location})
    assert result.status_code == 200
    printer = result.json()
    assert printer["id"] == random_printer["id"]
    assert printer["location"] == new_location


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


def test_delete_printer_with_print_jobs(random_printer: dict[str, Any], random_plate: dict[str, Any]):
    """Test that a printer cannot be deleted if it has print jobs."""
    # Create a print job referencing the printer
    payload = {
        "plate_id": random_plate["id"],
        "status": "pending",
        "printer_id": random_printer["id"],
        "spool_usages": [],
    }
    create_res = httpx.post(f"{URL}/api/v1/print_job", json=payload)
    create_res.raise_for_status()
    print_job = create_res.json()

    try:
        # Try to delete the printer
        del_res = httpx.delete(f"{URL}/api/v1/printer/{random_printer['id']}")
        # Should fail due to foreign key constraint
        assert del_res.status_code == 400
        assert "Cannot delete printer" in del_res.json()["message"]
    finally:
        # Clean up print job
        httpx.delete(f"{URL}/api/v1/print_job/{print_job['id']}").raise_for_status()


@pytest.mark.asyncio
async def test_printer_websocket_any():
    """Test WebSocket notifications for any printer changes."""
    import asyncio
    import websockets
    import json

    ws_url = URL.replace("http://", "ws://")
    async with websockets.connect(f"{ws_url}/api/v1/printer") as ws:
        async with httpx.AsyncClient() as client:
            # Create a printer
            create_res = await client.post(
                f"{URL}/api/v1/printer",
                json={"name": "WS Test Printer", "model": "WS-100"},
            )
            assert create_res.status_code == 200
            printer = create_res.json()

            try:
                # Receive added event
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                event = json.loads(msg)
                assert event["type"] == "added"
                assert event["resource"] == "printer"
                assert event["payload"]["id"] == printer["id"]
                assert event["payload"]["name"] == printer["name"]

                # Update the printer
                update_res = await client.patch(
                    f"{URL}/api/v1/printer/{printer['id']}",
                    json={"name": "WS Test Printer Updated"},
                )
                assert update_res.status_code == 200

                # Receive updated event
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                event = json.loads(msg)
                assert event["type"] == "updated"
                assert event["resource"] == "printer"
                assert event["payload"]["id"] == printer["id"]
                assert event["payload"]["name"] == "WS Test Printer Updated"

            finally:
                # Delete the printer
                await client.delete(f"{URL}/api/v1/printer/{printer['id']}")

                # Receive deleted event
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                event = json.loads(msg)
                assert event["type"] == "deleted"
                assert event["resource"] == "printer"
                assert event["payload"]["id"] == printer["id"]


@pytest.mark.asyncio
async def test_printer_websocket_specific(random_printer: dict[str, Any]):
    """Test WebSocket notifications for a specific printer's changes."""
    import asyncio
    import websockets
    import json

    ws_url = URL.replace("http://", "ws://")
    async with websockets.connect(f"{ws_url}/api/v1/printer/{random_printer['id']}") as ws:
        async with httpx.AsyncClient() as client:
            # Update the specific printer
            update_res = await client.patch(
                f"{URL}/api/v1/printer/{random_printer['id']}",
                json={"comment": "WS Specific Comment"},
            )
            assert update_res.status_code == 200

            # Receive updated event
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            event = json.loads(msg)
            assert event["type"] == "updated"
            assert event["resource"] == "printer"
            assert event["payload"]["id"] == random_printer["id"]
            assert event["payload"]["comment"] == "WS Specific Comment"
