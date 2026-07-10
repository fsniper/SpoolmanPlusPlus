"""Integration tests for spool weight deduction business logic."""

from typing import Any
import httpx
import pytest

from ..conftest import URL


def test_deduct_on_status_successful(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test that spool weight is deducted when print job status changes to successful."""
    # Create spool
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000.0,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()
    initial_used = spool.get("used_weight", 0.0)

    try:
        # Create Print Job with printing status
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": 150.0,
                    }
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # Verify spool remaining weight has not changed yet
            spool_check = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_check["remaining_weight"] == 1000.0

            # Update status to successful
            patch_res = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res.raise_for_status()

            # Verify spool weight is deducted
            spool_after = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after["remaining_weight"] == 850.0
            assert spool_after["used_weight"] == pytest.approx(initial_used + 150.0)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_deduct_on_creation_if_successful(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test that spool weight is deducted immediately if print job is created with successful status."""
    # Create spool
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000.0,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()
    initial_used = spool.get("used_weight", 0.0)

    try:
        # Create Print Job with successful status
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "successful",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": 200.0,
                    }
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # Verify spool weight is immediately deducted
            spool_after = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after["remaining_weight"] == 800.0
            assert spool_after["used_weight"] == pytest.approx(initial_used + 200.0)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_deduct_multiple_spools(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test weight deduction across multiple spools in the same print job."""
    # Spool A
    spool_a_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000.0,
        },
    )
    spool_a_res.raise_for_status()
    spool_a = spool_a_res.json()
    initial_used_a = spool_a.get("used_weight", 0.0)

    # Spool B
    spool_b_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 500.0,
        },
    )
    spool_b_res.raise_for_status()
    spool_b = spool_b_res.json()
    initial_used_b = spool_b.get("used_weight", 0.0)

    try:
        # Create Print Job with printing status
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {"spool_id": spool_a["id"], "weight_used": 100.0},
                    {"spool_id": spool_b["id"], "weight_used": 50.0},
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # Update status to successful
            patch_res = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res.raise_for_status()

            # Verify Spool A
            spool_a_after = httpx.get(f"{URL}/api/v1/spool/{spool_a['id']}").json()
            assert spool_a_after["remaining_weight"] == 900.0
            assert spool_a_after["used_weight"] == pytest.approx(initial_used_a + 100.0)

            # Verify Spool B
            spool_b_after = httpx.get(f"{URL}/api/v1/spool/{spool_b['id']}").json()
            assert spool_b_after["remaining_weight"] == 450.0
            assert spool_b_after["used_weight"] == pytest.approx(initial_used_b + 50.0)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool_a['id']}").raise_for_status()
        except httpx.HTTPError:
            pass
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool_b['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_deduction_idempotency(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test that updating a successful print job does not deduct weight again."""
    # Create spool
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000.0,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()
    initial_used = spool.get("used_weight", 0.0)

    try:
        # Create Print Job with printing status
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": 100.0,
                    }
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # First patch: status to successful
            patch_res1 = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res1.raise_for_status()

            spool_after1 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after1["remaining_weight"] == 900.0

            # Second patch: comment update, keeping status successful
            patch_res2 = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"comment": "Adding some details", "status": "successful"},
            )
            patch_res2.raise_for_status()

            # Verify spool remaining weight did NOT change further
            spool_after2 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after2["remaining_weight"] == 900.0
            assert spool_after2["used_weight"] == pytest.approx(initial_used + 100.0)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_deduction_greater_than_remaining_clamps(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test that weight deduction does not result in negative remaining weight (clamps to 0)."""
    # Create spool with small remaining weight
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 50.0,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()

    try:
        # Create Print Job with printing status, using 100g (more than remaining)
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": 100.0,
                    }
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # Update status to successful
            patch_res = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res.raise_for_status()

            # Verify remaining weight is clamped to 0.0
            spool_after = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after["remaining_weight"] == 0.0

            # Verify used weight matches expected value when clamped (initial_weight)
            expected_used = spool_after.get("initial_weight", random_filament["weight"])
            assert spool_after["used_weight"] == pytest.approx(expected_used)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass


def test_weight_refund_on_reversion_or_deletion(random_plate: dict[str, Any], random_filament: dict[str, Any]):
    """Test that transitioning status from successful to unsuccessful or deleting job refunds the weight."""
    # Create spool
    spool_res = httpx.post(
        f"{URL}/api/v1/spool",
        json={
            "filament_id": random_filament["id"],
            "remaining_weight": 1000.0,
        },
    )
    spool_res.raise_for_status()
    spool = spool_res.json()
    initial_used = spool.get("used_weight", 0.0)

    try:
        # Create Print Job with printing status
        job_res = httpx.post(
            f"{URL}/api/v1/print_job",
            json={
                "plate_id": random_plate["id"],
                "status": "printing",
                "spool_usages": [
                    {
                        "spool_id": spool["id"],
                        "weight_used": 150.0,
                    }
                ],
            },
        )
        job_res.raise_for_status()
        job = job_res.json()

        try:
            # Transition status: printing -> successful
            patch_res1 = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res1.raise_for_status()

            # Verify spool weight is deducted
            spool_after1 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after1["remaining_weight"] == 850.0

            # Transition back: successful -> printing
            patch_res2 = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "printing"},
            )
            patch_res2.raise_for_status()

            # Verify spool weight is refunded
            spool_after2 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after2["remaining_weight"] == 1000.0
            assert spool_after2["used_weight"] == pytest.approx(initial_used)

            # Transition: printing -> successful (again)
            patch_res3 = httpx.patch(
                f"{URL}/api/v1/print_job/{job['id']}",
                json={"status": "successful"},
            )
            patch_res3.raise_for_status()

            spool_after3 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after3["remaining_weight"] == 850.0

            # Delete the print job when it's successful
            httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()

            # Verify spool weight is refunded upon deletion
            spool_after4 = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
            assert spool_after4["remaining_weight"] == 1000.0
            assert spool_after4["used_weight"] == pytest.approx(initial_used)

        finally:
            try:
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()
            except httpx.HTTPError:
                pass
    finally:
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass
