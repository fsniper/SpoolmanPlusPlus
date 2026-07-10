"""Multi-entity workflow integration tests."""

from typing import Any
import httpx

from ..conftest import URL


def test_integrated_print_workflow(random_filament: dict[str, Any]):
    """Test a full integrated workflow from project/plate creation to printing with a spool."""
    # Setup spool
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
        # Step 1: Create a Project
        proj_res = httpx.post(
            f"{URL}/api/v1/project",
            json={
                "name": "Workflow Project",
                "description": "Project for workflow test",
            },
        )
        proj_res.raise_for_status()
        project = proj_res.json()

        try:
            # Step 2: Create a Plate under that project
            plate_res = httpx.post(
                f"{URL}/api/v1/plate",
                json={
                    "project_id": project["id"],
                    "name": "Workflow Plate",
                    "estimated_weight": 250.0,
                },
            )
            plate_res.raise_for_status()
            plate = plate_res.json()

            try:
                # Step 3: Create a Print Job with status "printing", usage of 250g
                job_res = httpx.post(
                    f"{URL}/api/v1/print_job",
                    json={
                        "plate_id": plate["id"],
                        "status": "printing",
                        "spool_usages": [
                            {
                                "spool_id": spool["id"],
                                "weight_used": 250.0,
                            }
                        ],
                    },
                )
                job_res.raise_for_status()
                job = job_res.json()

                # Verify print job lists spool usages correctly
                assert len(job["spool_usages"]) == 1
                assert job["spool_usages"][0]["spool_id"] == spool["id"]
                assert job["spool_usages"][0]["weight_used"] == 250.0

                # Step 4: Verify spool's remaining weight is still 1000g
                spool_check = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
                assert spool_check["remaining_weight"] == 1000.0

                # Step 5: Update print job to "failed" and verify spool remains 1000g
                job_patch = httpx.patch(
                    f"{URL}/api/v1/print_job/{job['id']}",
                    json={"status": "failed"},
                )
                job_patch.raise_for_status()
                spool_check = httpx.get(f"{URL}/api/v1/spool/{spool['id']}").json()
                assert spool_check["remaining_weight"] == 1000.0

                # Step 6: Cleanup print job
                httpx.delete(f"{URL}/api/v1/print_job/{job['id']}").raise_for_status()

            finally:
                # Cleanup plate
                try:
                    httpx.delete(f"{URL}/api/v1/plate/{plate['id']}").raise_for_status()
                except httpx.HTTPError:
                    pass

        finally:
            # Cleanup project
            try:
                httpx.delete(f"{URL}/api/v1/project/{project['id']}").raise_for_status()
            except httpx.HTTPError:
                pass

    finally:
        # Cleanup spool
        try:
            httpx.delete(f"{URL}/api/v1/spool/{spool['id']}").raise_for_status()
        except httpx.HTTPError:
            pass
