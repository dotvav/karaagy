"""Tests for POST /v1/images/generations and GET /v1/images/files/{filename}."""

import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from karaagy.config import settings
from karaagy.core.images import _generate_single_image


def test_images_generations_missing_prompt(client: TestClient) -> None:
    """Test 400 when prompt is empty or whitespace."""
    response = client.post("/v1/images/generations", json={"prompt": "   "})
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "missing_required_field"


def test_images_generations_invalid_n_range(client: TestClient) -> None:
    """Test 400 when n is out of valid bounds."""
    response_low = client.post("/v1/images/generations", json={"prompt": "A cute cat", "n": 0})
    assert response_low.status_code == 400
    assert response_low.json()["error"]["code"] == "invalid_parameter_range"

    response_high = client.post("/v1/images/generations", json={"prompt": "A cute cat", "n": 11})
    assert response_high.status_code == 400
    assert response_high.json()["error"]["code"] == "invalid_parameter_range"


@patch("karaagy.core.images._generate_single_image", new_callable=AsyncMock)
def test_images_generations_b64_json(mock_gen: AsyncMock, client: TestClient) -> None:
    """Test successful image generation returning b64_json."""
    fake_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    mock_gen.return_value = (fake_png_bytes, "image/png")

    payload = {
        "prompt": "A kitten cactus",
        "n": 1,
        "response_format": "b64_json",
        "size": "512x512",
    }
    response = client.post("/v1/images/generations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["b64_json"] == base64.b64encode(fake_png_bytes).decode("utf-8")
    assert data["data"][0]["revised_prompt"] == "A kitten cactus"


@patch("karaagy.core.images._generate_single_image", new_callable=AsyncMock)
def test_images_generations_url_and_fetch(
    mock_gen: AsyncMock, client: TestClient, tmp_path: Path
) -> None:
    """Test successful image generation returning URL and verify retrieval of cached image."""
    fake_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    mock_gen.return_value = (fake_jpeg_bytes, "image/jpeg")

    with patch.object(settings, "image_cache_dir", tmp_path):
        payload = {
            "prompt": "Cyberpunk cityscape",
            "n": 1,
            "response_format": "url",
        }
        response = client.post("/v1/images/generations", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1

        img_url = data["data"][0]["url"]
        assert "/v1/images/files/img_" in img_url
        filename = img_url.split("/")[-1]

        # Verify fetching the image from the GET and HEAD endpoints
        head_res = client.head(f"/v1/images/files/{filename}")
        assert head_res.status_code == 200
        assert head_res.headers["content-type"].startswith("image/jpeg")

        file_res = client.get(f"/v1/images/files/{filename}")
        assert file_res.status_code == 200
        assert file_res.headers["content-type"].startswith("image/jpeg")
        assert file_res.content == fake_jpeg_bytes


def test_get_cached_image_not_found(client: TestClient) -> None:
    """Test 404 when requesting a non-existent cached image."""
    response = client.get("/v1/images/files/img_non_existent.png")
    assert response.status_code == 404


def test_get_cached_image_path_traversal(client: TestClient) -> None:
    """Test 400 when attempting path traversal in filename."""
    response = client.get("/v1/images/files/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code in {400, 404}


@patch("karaagy.core.images._generate_single_image", new_callable=AsyncMock)
def test_images_generations_failure_handling(mock_gen: AsyncMock, client: TestClient) -> None:
    """Test 500 when image generator throws an exception."""
    mock_gen.side_effect = RuntimeError("Antigravity CLI execution timeout")

    payload = {"prompt": "A sunset over mountains"}
    response = client.post("/v1/images/generations", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert data["error"]["code"] == "image_generation_failed"
    assert "Antigravity CLI execution timeout" in data["error"]["message"]


@pytest.mark.asyncio
async def test_generate_single_image_success(tmp_path: Path) -> None:
    """Test _generate_single_image subprocess execution mock."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0

    async def fake_communicate() -> tuple[bytes, bytes]:
        # Create a fake image file in the temp directory
        for dir_path in Path(tempfile.gettempdir()).glob("karaagy_img_gen_*"):
            if dir_path.is_dir():
                (dir_path / "test_out.png").write_bytes(b"PNGDATA")
        return b"Generated image at test_out.png", b""

    mock_proc.communicate = fake_communicate

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        img_bytes, mime_type = await _generate_single_image(
            prompt_text="A blue bird",
            model="gemini-3.8-flash-high",
        )
        assert img_bytes == b"PNGDATA"
        assert mime_type == "image/png"


def test_prune_expired_cached_images(tmp_path: Path) -> None:
    """Test pruning of files older than TTL."""
    import os
    import time

    from karaagy.core.images import prune_expired_cached_images

    old_file = tmp_path / "img_old.jpg"
    old_file.write_bytes(b"old")
    # Set mtime to 2 days ago
    os.utime(str(old_file), (time.time() - 172800, time.time() - 172800))

    new_file = tmp_path / "img_new.jpg"
    new_file.write_bytes(b"new")

    with patch.object(settings, "image_cache_dir", tmp_path):
        with patch.object(settings, "image_cache_ttl_seconds", 86400.0):
            pruned = prune_expired_cached_images()
            assert pruned == 1
            assert not old_file.exists()
            assert new_file.exists()


def test_get_cached_image_expired(client: TestClient, tmp_path: Path) -> None:
    """Test 404 when requested image has expired past TTL."""
    import os
    import time

    expired_file = tmp_path / "img_expired.jpg"
    expired_file.write_bytes(b"expired")
    os.utime(str(expired_file), (time.time() - 100000, time.time() - 100000))

    with patch.object(settings, "image_cache_dir", tmp_path):
        with patch.object(settings, "image_cache_ttl_seconds", 86400.0):
            response = client.get("/v1/images/files/img_expired.jpg")
            assert response.status_code == 404
            assert not expired_file.exists()
