"""Integration tests for Project CRUD."""

from typing import Any
import httpx

from ..conftest import URL


def test_create_project():
    """Test creating a project."""
    payload = {
        "name": "Spec Project",
        "description": "Desc",
        "link": "http://lnk",
    }
    result = httpx.post(f"{URL}/api/v1/project", json=payload)
    assert result.status_code in (200, 201)
    project = result.json()

    assert "id" in project
    assert "registered" in project
    assert project["name"] == payload["name"]
    assert project["description"] == payload["description"]
    assert project["link"] == payload["link"]

    # Clean up
    httpx.delete(f"{URL}/api/v1/project/{project['id']}").raise_for_status()


def test_get_project(random_project: dict[str, Any]):
    """Test getting a project."""
    result = httpx.get(f"{URL}/api/v1/project/{random_project['id']}")
    assert result.status_code == 200
    project = result.json()
    assert project["id"] == random_project["id"]
    assert project["name"] == random_project["name"]


def test_list_projects(random_project: dict[str, Any]):
    """Test listing projects."""
    result = httpx.get(f"{URL}/api/v1/project", params={"name": random_project["name"]})
    assert result.status_code == 200
    projects = result.json()
    assert isinstance(projects, list)
    assert len(projects) >= 1
    assert any(p["id"] == random_project["id"] for p in projects)
    assert "x-total-count" in result.headers


def test_patch_project(random_project: dict[str, Any]):
    """Test patching a project."""
    new_name = "Updated Project Name"
    result = httpx.patch(f"{URL}/api/v1/project/{random_project['id']}", json={"name": new_name})
    assert result.status_code == 200
    project = result.json()
    assert project["id"] == random_project["id"]
    assert project["name"] == new_name


def test_delete_project():
    """Test deleting a project."""
    result = httpx.post(
        f"{URL}/api/v1/project",
        json={"name": "Temporary Project"},
    )
    result.raise_for_status()
    project = result.json()

    del_res = httpx.delete(f"{URL}/api/v1/project/{project['id']}")
    assert del_res.status_code in (200, 204)

    get_res = httpx.get(f"{URL}/api/v1/project/{project['id']}")
    assert get_res.status_code == 404


def test_create_project_empty_name():
    """Test creating a project with an empty name."""
    result = httpx.post(
        f"{URL}/api/v1/project",
        json={"name": ""},
    )
    assert result.status_code in (400, 422)


def test_create_project_long_name():
    """Test creating a project with a name that is too long (257 chars)."""
    result = httpx.post(
        f"{URL}/api/v1/project",
        json={"name": "a" * 257},
    )
    assert result.status_code in (400, 422)
