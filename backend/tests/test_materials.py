import io
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_upload_txt_material(client):
    content = b"Metformin is a biguanide used as first-line treatment for type 2 diabetes."

    # Background task uses real DB session — patch it so tests stay isolated
    with patch("app.routes.materials._process_and_store_text", new=AsyncMock(return_value=None)):
        response = await client.post(
            "/api/materials/upload",
            data={"title": "Metformin Overview", "description": "Test material"},
            files={"file": ("metformin.txt", io.BytesIO(content), "text/plain")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Metformin Overview"
    assert data["file_type"] == "txt"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_materials(client):
    response = await client.get("/api/materials")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_upload_invalid_extension(client):
    response = await client.post(
        "/api/materials/upload",
        data={"title": "Bad file"},
        files={"file": ("malware.exe", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_material(client):
    response = await client.get("/api/materials/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
