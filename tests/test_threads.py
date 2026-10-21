"""Tests for OpenAI Assistants / Threads API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from karaagy.config import settings
from karaagy.core.prompt import _process_image_url
from karaagy.models.openai import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionMessage,
    ChatCompletionResponse,
    UsageInfo,
)


def test_create_and_get_thread(client: TestClient) -> None:
    """Test creating a thread and fetching its details."""
    response = client.post("/v1/threads", json={"metadata": {"test_key": "test_val"}})
    assert response.status_code == 201
    data = response.json()
    assert data["object"] == "thread"
    assert "id" in data
    assert data["metadata"]["test_key"] == "test_val"
    thread_id = data["id"]

    # Get thread
    get_res = client.get(f"/v1/threads/{thread_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == thread_id


def test_thread_messages_flow(client: TestClient) -> None:
    """Test adding messages and listing them in a thread."""
    # Create thread
    t_res = client.post("/v1/threads")
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # Add message
    msg_res = client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"role": "user", "content": "Bonjour !"},
    )
    assert msg_res.status_code == 201
    msg_data = msg_res.json()
    assert msg_data["object"] == "thread.message"
    assert msg_data["role"] == "user"
    assert msg_data["content"][0]["text"]["value"] == "Bonjour !"

    # List messages
    list_res = client.get(f"/v1/threads/{thread_id}/messages")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["object"] == "list"
    assert len(list_data["data"]) == 1
    assert list_data["data"][0]["id"] == msg_data["id"]


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_sync(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test running a thread synchronously."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-thread123",
        model="gemini-3.7-flash-low",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content="Salut ! Que puis-je faire pour toi ?"
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )

    # 1. Create thread with message
    t_res = client.post(
        "/v1/threads",
        json={"messages": [{"role": "user", "content": "Salut !"}]},
    )
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # 2. Run thread
    run_res = client.post(
        f"/v1/threads/{thread_id}/runs",
        json={"model": "gemini-3.7-flash-low", "instructions": "Tu es Voizoche."},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["object"] == "thread.run"
    assert run_data["status"] == "completed"
    assert run_data["thread_id"] == thread_id

    # 3. Check assistant message was added
    list_res = client.get(f"/v1/threads/{thread_id}/messages?order=asc")
    assert list_res.status_code == 200
    msgs = list_res.json()["data"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"][0]["text"]["value"] == "Salut ! Que puis-je faire pour toi ?"


def test_delete_thread(client: TestClient) -> None:
    """Test deleting a thread."""
    t_res = client.post("/v1/threads")
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # Delete thread
    del_res = client.delete(f"/v1/threads/{thread_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Check 404
    get_res = client.get(f"/v1/threads/{thread_id}")
    assert get_res.status_code == 404


def test_thread_path_traversal_protection(client: TestClient) -> None:
    """Test that path traversal attempts in thread_id return 404 or error safely."""
    res_get = client.get("/v1/threads/..%2F..%2Fetc%2Fpasswd")
    assert res_get.status_code in {400, 404}

    res_del = client.delete("/v1/threads/..%2F..%2Fetc%2Fpasswd")
    assert res_del.status_code in {400, 404}


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_error_sanitization(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test that thread run failure sanitizes last_error without leaking sensitive internal details."""
    mock_execute.side_effect = RuntimeError("Fatal DB crash at /etc/secret_token password=123")

    t_res = client.post("/v1/threads", json={"messages": [{"role": "user", "content": "Test"}]})
    thread_id = t_res.json()["id"]

    run_res = client.post(f"/v1/threads/{thread_id}/runs", json={"model": "gemini-3.7-flash-low"})
    assert run_res.status_code == 500
    err_data = run_res.json()
    assert "password=123" not in err_data["error"]["message"]
    assert "Internal server error" in err_data["error"]["message"]


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_workspace_isolation_and_cleanup(
    mock_execute: AsyncMock, client: TestClient
) -> None:
    """Test that thread runs execute in an isolated workspace and are cleaned up on deletion."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-ws",
        model="gemini-3.7-flash-low",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="OK"),
                finish_reason="stop",
            )
        ],
    )
    t_res = client.post("/v1/threads", json={"messages": [{"role": "user", "content": "Hi"}]})
    thread_id = t_res.json()["id"]

    run_res = client.post(f"/v1/threads/{thread_id}/runs", json={"model": "gemini-3.7-flash-low"})
    assert run_res.status_code == 200

    # Verify cwd was passed as the isolated workspace
    call_kwargs = mock_execute.call_args.kwargs
    assert "cwd" in call_kwargs
    cwd_path: Path = call_kwargs["cwd"]
    assert str(cwd_path).endswith(f"workspaces/{thread_id}")
    assert cwd_path.exists() and cwd_path.is_dir()

    # Verify deleting thread removes workspace
    del_res = client.delete(f"/v1/threads/{thread_id}")
    assert del_res.status_code == 200
    assert not cwd_path.exists()


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_native_image_detection_and_cache_migration(
    mock_execute: AsyncMock, client: TestClient, tmp_path: Path
) -> None:
    """Test that native image files created during thread run are detected, migrated to cache, and returned as image_url."""
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_THREAD_IMG"

    async def fake_execute(*args, **kwargs) -> ChatCompletionResponse:
        cwd: Path = kwargs["cwd"]
        # Simulate AGY tool saving image into workspace
        (cwd / "generated_dish.png").write_bytes(fake_png)
        return ChatCompletionResponse(
            id="chatcmpl-img",
            model="gemini-3.8-flash-high",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="Voici la délicieuse photo du plat demandée !",
                    ),
                    finish_reason="stop",
                )
            ],
        )

    mock_execute.side_effect = fake_execute

    with patch.object(settings, "image_cache_dir", tmp_path / "cache"):
        t_res = client.post(
            "/v1/threads",
            json={"messages": [{"role": "user", "content": "Génère un plat de pâtes"}]},
        )
        thread_id = t_res.json()["id"]

        run_res = client.post(
            f"/v1/threads/{thread_id}/runs", json={"model": "gemini-3.8-flash-high"}
        )
        assert run_res.status_code == 200

        # Check messages
        msg_res = client.get(f"/v1/threads/{thread_id}/messages?order=asc")
        assert msg_res.status_code == 200
        msgs = msg_res.json()["data"]
        assert len(msgs) == 2
        asst_msg = msgs[1]
        assert asst_msg["role"] == "assistant"
        content_parts = asst_msg["content"]
        assert len(content_parts) == 2
        assert content_parts[0]["type"] == "text"
        assert "Voici la délicieuse photo" in content_parts[0]["text"]["value"]
        assert content_parts[1]["type"] == "image_url"
        img_url = content_parts[1]["image_url"]["url"]
        assert "/v1/images/files/img_" in img_url

        # Check image exists in cache and is retrievable via GET /v1/images/files/{filename}
        filename = img_url.split("/")[-1]
        file_res = client.get(f"/v1/images/files/{filename}")
        assert file_res.status_code == 200
        assert file_res.content == fake_png


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_local_path_rewriting(
    mock_execute: AsyncMock, client: TestClient, tmp_path: Path
) -> None:
    """Test that explicit filesystem paths in assistant text are replaced with public URLs."""
    fake_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    img_file = tmp_path / "dish.jpg"
    img_file.write_bytes(fake_jpg)

    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-rewrite",
        model="gemini-3.8-flash-high",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=f"Illustration prête: [Image saved at {img_file}]",
                ),
                finish_reason="stop",
            )
        ],
    )

    with patch.object(settings, "image_cache_dir", tmp_path / "cache"):
        t_res = client.post(
            "/v1/threads", json={"messages": [{"role": "user", "content": "Draw food"}]}
        )
        thread_id = t_res.json()["id"]

        run_res = client.post(
            f"/v1/threads/{thread_id}/runs", json={"model": "gemini-3.8-flash-high"}
        )
        assert run_res.status_code == 200

        msg_res = client.get(f"/v1/threads/{thread_id}/messages?order=asc")
        asst_msg = msg_res.json()["data"][1]
        text_val = asst_msg["content"][0]["text"]["value"]
        assert str(img_file) not in text_val
        assert "/v1/images/files/img_" in text_val


def test_prompt_builder_local_cached_image_shortcut(tmp_path: Path) -> None:
    """Test that local cached image URLs resolve directly to local files without downloading."""
    cached_file = tmp_path / "img_shortcut.jpg"
    cached_file.write_bytes(b"DATA")

    with patch.object(settings, "image_cache_dir", tmp_path):
        url = "http://192.168.1.3:8000/v1/images/files/img_shortcut.jpg"
        resolved = _process_image_url(url)
        assert resolved == f"[Attached Image File: {cached_file}]"


@patch("karaagy.core.threads._execute_agy_stream_internal")
def test_thread_run_stream_native_image_markdown_delta(
    mock_stream, client: TestClient, tmp_path: Path
) -> None:
    """Test that streaming runs yield markdown image deltas and store multimodal message content."""
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_STREAM"

    async def fake_stream_generator(*args, **kwargs):
        cwd: Path = kwargs["cwd"]
        (cwd / "stream_art.png").write_bytes(fake_png)
        chunk = ChatCompletionChunk(
            id="chatcmpl-s1",
            model="gemini-3.8-flash-high",
            choices=[
                ChatCompletionChunkChoice(
                    index=0,
                    delta=ChatCompletionChunkDelta(content="Voici le croquis:"),
                    finish_reason=None,
                )
            ],
        )
        yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
        yield "data: [DONE]\n\n"

    mock_stream.side_effect = fake_stream_generator

    with patch.object(settings, "image_cache_dir", tmp_path / "cache"):
        t_res = client.post(
            "/v1/threads", json={"messages": [{"role": "user", "content": "Croque une pomme"}]}
        )
        thread_id = t_res.json()["id"]

        run_res = client.post(
            f"/v1/threads/{thread_id}/runs",
            json={"model": "gemini-3.8-flash-high", "stream": True},
        )
        assert run_res.status_code == 200
        raw_sse = run_res.text
        assert "Voici le croquis:" in raw_sse
        assert "![Generated Image]" in raw_sse
        assert "/v1/images/files/img_" in raw_sse

        # Check message stored multimodally
        msg_res = client.get(f"/v1/threads/{thread_id}/messages?order=asc")
        asst_msg = msg_res.json()["data"][1]
        assert asst_msg["content"][1]["type"] == "image_url"
